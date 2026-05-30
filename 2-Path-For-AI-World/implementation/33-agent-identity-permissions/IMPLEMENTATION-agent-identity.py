"""
Agent Identity System
====================
Production-grade agent identity registration, credential management,
and authentication for AI agent systems.
"""

import uuid
import hashlib
import secrets
import json
import time
from datetime import datetime, timedelta, timezone
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Set, Any
from abc import ABC, abstractmethod
import hmac
import base64
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding, ec
from cryptography.x509 import CertificateBuilder, Name, NameAttribute
from cryptography.x509.oid import NameOID
import jwt  # PyJWT


# =============================================================================
# ENUMS AND CONSTANTS
# =============================================================================

class AgentType(Enum):
    AUTONOMOUS = "autonomous"         # Runs without real-time user interaction
    INTERACTIVE = "interactive"       # User is in the loop
    BATCH = "batch"                   # Scheduled/batch processing
    ORCHESTRATOR = "orchestrator"     # Coordinates other agents


class TrustLevel(Enum):
    INTERNAL = "internal"                   # Same org, same platform
    VERIFIED_EXTERNAL = "verified_external" # Third-party, verified
    UNVERIFIED_EXTERNAL = "unverified_external"  # Unknown


class CredentialType(Enum):
    CLIENT_SECRET = "client_secret"
    CERTIFICATE = "certificate"
    SIGNED_JWT = "signed_jwt"
    MTLS = "mtls"


class CredentialStatus(Enum):
    ACTIVE = "active"
    ROTATED = "rotated"       # Replaced by newer credential
    REVOKED = "revoked"
    EXPIRED = "expired"


class AgentStatus(Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    REVOKED = "revoked"
    PENDING_VERIFICATION = "pending_verification"


# =============================================================================
# CORE DATA MODELS
# =============================================================================

@dataclass
class PermissionBoundary:
    """Maximum permissions an agent can ever have, regardless of delegation."""
    allowed_scopes: Set[str]          # e.g., {"repo:read", "repo:write:branch"}
    denied_scopes: Set[str]           # Explicit denials override allows
    allowed_resources: List[str]      # Glob patterns
    denied_resources: List[str]       # Glob patterns (override allows)
    max_token_lifetime_seconds: int = 900  # 15 min max
    max_actions_per_hour: int = 1000
    allowed_tools: Optional[Set[str]] = None  # None = all tools within scopes
    require_approval_above_risk: int = 7      # Risk score 0-10

    def allows_scope(self, scope: str) -> bool:
        if scope in self.denied_scopes:
            return False
        # Check if scope matches any allowed scope (prefix matching)
        for allowed in self.allowed_scopes:
            if scope == allowed or scope.startswith(allowed + ":"):
                return True
        return False

    def allows_resource(self, resource: str) -> bool:
        import fnmatch
        for denied in self.denied_resources:
            if fnmatch.fnmatch(resource, denied):
                return False
        for allowed in self.allowed_resources:
            if fnmatch.fnmatch(resource, allowed):
                return True
        return False


@dataclass
class AgentCredential:
    """A single credential associated with an agent identity."""
    credential_id: str
    agent_id: str
    credential_type: CredentialType
    status: CredentialStatus
    created_at: datetime
    expires_at: datetime
    rotated_from: Optional[str] = None  # Previous credential ID
    last_used_at: Optional[datetime] = None
    use_count: int = 0
    # Sensitive material stored encrypted; never exposed to agent
    _secret_hash: str = ""  # For client_secret type
    _certificate_thumbprint: str = ""  # For certificate type
    _public_key_pem: str = ""  # For signed_jwt type

    @property
    def is_valid(self) -> bool:
        now = datetime.now(timezone.utc)
        return (
            self.status == CredentialStatus.ACTIVE
            and self.created_at <= now
            and self.expires_at > now
        )


@dataclass
class AgentIdentity:
    """Complete agent identity record."""
    agent_id: str
    agent_name: str
    agent_type: AgentType
    owner_id: str                    # User or org that owns this agent
    tenant_id: str
    trust_level: TrustLevel
    status: AgentStatus
    permission_boundary: PermissionBoundary
    created_at: datetime
    updated_at: datetime
    credentials: List[AgentCredential] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    # Version tracking
    version: str = "1.0.0"
    description: str = ""
    # Network constraints
    allowed_ip_ranges: List[str] = field(default_factory=list)

    @property
    def active_credentials(self) -> List[AgentCredential]:
        return [c for c in self.credentials if c.is_valid]

    @property
    def is_active(self) -> bool:
        return self.status == AgentStatus.ACTIVE


# =============================================================================
# AGENT IDENTITY STORE (Abstract + In-Memory Implementation)
# =============================================================================

class AgentIdentityStore(ABC):
    """Abstract store for agent identities."""

    @abstractmethod
    async def create(self, identity: AgentIdentity) -> AgentIdentity:
        pass

    @abstractmethod
    async def get(self, agent_id: str) -> Optional[AgentIdentity]:
        pass

    @abstractmethod
    async def update(self, identity: AgentIdentity) -> AgentIdentity:
        pass

    @abstractmethod
    async def revoke(self, agent_id: str, reason: str) -> None:
        pass

    @abstractmethod
    async def list_by_owner(self, owner_id: str) -> List[AgentIdentity]:
        pass

    @abstractmethod
    async def list_by_tenant(self, tenant_id: str) -> List[AgentIdentity]:
        pass


class InMemoryAgentIdentityStore(AgentIdentityStore):
    """In-memory implementation for development/testing."""

    def __init__(self):
        self._agents: Dict[str, AgentIdentity] = {}
        self._revocation_log: List[Dict] = []

    async def create(self, identity: AgentIdentity) -> AgentIdentity:
        if identity.agent_id in self._agents:
            raise ValueError(f"Agent {identity.agent_id} already exists")
        self._agents[identity.agent_id] = identity
        return identity

    async def get(self, agent_id: str) -> Optional[AgentIdentity]:
        return self._agents.get(agent_id)

    async def update(self, identity: AgentIdentity) -> AgentIdentity:
        if identity.agent_id not in self._agents:
            raise ValueError(f"Agent {identity.agent_id} not found")
        identity.updated_at = datetime.now(timezone.utc)
        self._agents[identity.agent_id] = identity
        return identity

    async def revoke(self, agent_id: str, reason: str) -> None:
        agent = self._agents.get(agent_id)
        if not agent:
            raise ValueError(f"Agent {agent_id} not found")
        agent.status = AgentStatus.REVOKED
        agent.updated_at = datetime.now(timezone.utc)
        # Revoke all credentials
        for cred in agent.credentials:
            cred.status = CredentialStatus.REVOKED
        self._revocation_log.append({
            "agent_id": agent_id,
            "reason": reason,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    async def list_by_owner(self, owner_id: str) -> List[AgentIdentity]:
        return [a for a in self._agents.values() if a.owner_id == owner_id]

    async def list_by_tenant(self, tenant_id: str) -> List[AgentIdentity]:
        return [a for a in self._agents.values() if a.tenant_id == tenant_id]


# =============================================================================
# CREDENTIAL MANAGER
# =============================================================================

class CredentialManager:
    """Manages agent credential lifecycle: creation, rotation, revocation."""

    def __init__(self, store: AgentIdentityStore, signing_key: str):
        self._store = store
        self._signing_key = signing_key
        # Secret storage (in production, this would be a Vault/HSM)
        self._secret_store: Dict[str, str] = {}

    async def create_client_secret_credential(
        self, agent_id: str, lifetime_days: int = 90
    ) -> Dict[str, str]:
        """Create a client_secret credential. Returns the secret ONCE."""
        agent = await self._store.get(agent_id)
        if not agent or not agent.is_active:
            raise ValueError("Agent not found or not active")

        # Generate cryptographically secure secret
        raw_secret = secrets.token_urlsafe(48)  # 64 chars, 384 bits entropy
        secret_hash = hashlib.sha256(raw_secret.encode()).hexdigest()

        credential = AgentCredential(
            credential_id=str(uuid.uuid4()),
            agent_id=agent_id,
            credential_type=CredentialType.CLIENT_SECRET,
            status=CredentialStatus.ACTIVE,
            created_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(days=lifetime_days),
            _secret_hash=secret_hash,
        )

        agent.credentials.append(credential)
        await self._store.update(agent)

        # Store secret hash for validation (never store raw secret)
        self._secret_store[credential.credential_id] = secret_hash

        # Return raw secret to caller (shown once, never stored in plaintext)
        return {
            "credential_id": credential.credential_id,
            "client_id": agent_id,
            "client_secret": raw_secret,
            "expires_at": credential.expires_at.isoformat(),
            "warning": "Store this secret securely. It will not be shown again.",
        }

    async def create_certificate_credential(
        self, agent_id: str, lifetime_days: int = 365
    ) -> Dict[str, str]:
        """Create a certificate credential. Returns public cert + private key."""
        agent = await self._store.get(agent_id)
        if not agent or not agent.is_active:
            raise ValueError("Agent not found or not active")

        # Generate RSA key pair
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )
        public_key = private_key.public_key()

        # Create self-signed certificate (in production, use proper CA)
        subject = Name([
            NameAttribute(NameOID.COMMON_NAME, f"agent-{agent_id}"),
            NameAttribute(NameOID.ORGANIZATION_NAME, agent.tenant_id),
        ])

        now = datetime.now(timezone.utc)
        cert = (
            CertificateBuilder()
            .subject_name(subject)
            .issuer_name(subject)
            .public_key(public_key)
            .serial_number(int(uuid.uuid4().int))
            .not_valid_before(now)
            .not_valid_after(now + timedelta(days=lifetime_days))
            .sign(private_key, hashes.SHA256())
        )

        # Compute thumbprint
        thumbprint = hashlib.sha256(
            cert.public_bytes(serialization.Encoding.DER)
        ).hexdigest()

        credential = AgentCredential(
            credential_id=str(uuid.uuid4()),
            agent_id=agent_id,
            credential_type=CredentialType.CERTIFICATE,
            status=CredentialStatus.ACTIVE,
            created_at=now,
            expires_at=now + timedelta(days=lifetime_days),
            _certificate_thumbprint=thumbprint,
            _public_key_pem=public_key.public_bytes(
                serialization.Encoding.PEM,
                serialization.PublicFormat.SubjectPublicKeyInfo,
            ).decode(),
        )

        agent.credentials.append(credential)
        await self._store.update(agent)

        return {
            "credential_id": credential.credential_id,
            "certificate_pem": cert.public_bytes(serialization.Encoding.PEM).decode(),
            "private_key_pem": private_key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            ).decode(),
            "thumbprint": thumbprint,
            "expires_at": credential.expires_at.isoformat(),
            "warning": "Store the private key securely. It will not be shown again.",
        }

    async def rotate_credential(
        self, agent_id: str, old_credential_id: str, grace_period_hours: int = 24
    ) -> Dict[str, str]:
        """Rotate a credential. Old credential remains valid during grace period."""
        agent = await self._store.get(agent_id)
        if not agent:
            raise ValueError("Agent not found")

        old_cred = next(
            (c for c in agent.credentials if c.credential_id == old_credential_id),
            None,
        )
        if not old_cred:
            raise ValueError("Credential not found")

        # Create new credential of same type
        if old_cred.credential_type == CredentialType.CLIENT_SECRET:
            new_cred_info = await self.create_client_secret_credential(agent_id)
        elif old_cred.credential_type == CredentialType.CERTIFICATE:
            new_cred_info = await self.create_certificate_credential(agent_id)
        else:
            raise ValueError(f"Rotation not supported for {old_cred.credential_type}")

        # Mark old credential as rotated (still valid during grace period)
        old_cred.status = CredentialStatus.ROTATED
        old_cred.expires_at = min(
            old_cred.expires_at,
            datetime.now(timezone.utc) + timedelta(hours=grace_period_hours),
        )

        # Link new credential to old
        new_cred_id = new_cred_info["credential_id"]
        new_cred = next(c for c in agent.credentials if c.credential_id == new_cred_id)
        new_cred.rotated_from = old_credential_id

        await self._store.update(agent)
        return new_cred_info

    async def revoke_credential(self, agent_id: str, credential_id: str) -> None:
        """Immediately revoke a credential."""
        agent = await self._store.get(agent_id)
        if not agent:
            raise ValueError("Agent not found")

        cred = next(
            (c for c in agent.credentials if c.credential_id == credential_id), None
        )
        if not cred:
            raise ValueError("Credential not found")

        cred.status = CredentialStatus.REVOKED
        await self._store.update(agent)

    async def validate_client_secret(
        self, agent_id: str, client_secret: str
    ) -> Optional[AgentCredential]:
        """Validate a client_secret credential. Returns credential if valid."""
        agent = await self._store.get(agent_id)
        if not agent or not agent.is_active:
            return None

        secret_hash = hashlib.sha256(client_secret.encode()).hexdigest()

        for cred in agent.active_credentials:
            if cred.credential_type == CredentialType.CLIENT_SECRET:
                stored_hash = self._secret_store.get(cred.credential_id)
                if stored_hash and hmac.compare_digest(stored_hash, secret_hash):
                    cred.last_used_at = datetime.now(timezone.utc)
                    cred.use_count += 1
                    return cred
        return None


# =============================================================================
# AGENT IDENTITY SERVICE
# =============================================================================

class AgentIdentityService:
    """
    High-level service for agent identity management.
    Handles registration, authentication, and identity verification.
    """

    def __init__(
        self,
        store: AgentIdentityStore,
        credential_manager: CredentialManager,
        jwt_signing_key: str,
        jwt_issuer: str = "agent-identity-service",
    ):
        self._store = store
        self._credentials = credential_manager
        self._jwt_signing_key = jwt_signing_key
        self._jwt_issuer = jwt_issuer

    # -------------------------------------------------------------------------
    # Registration
    # -------------------------------------------------------------------------

    async def register_agent(
        self,
        agent_name: str,
        agent_type: AgentType,
        owner_id: str,
        tenant_id: str,
        permission_boundary: PermissionBoundary,
        trust_level: TrustLevel = TrustLevel.INTERNAL,
        description: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AgentIdentity:
        """Register a new agent identity."""
        now = datetime.now(timezone.utc)
        identity = AgentIdentity(
            agent_id=str(uuid.uuid4()),
            agent_name=agent_name,
            agent_type=agent_type,
            owner_id=owner_id,
            tenant_id=tenant_id,
            trust_level=trust_level,
            status=AgentStatus.ACTIVE if trust_level == TrustLevel.INTERNAL
                   else AgentStatus.PENDING_VERIFICATION,
            permission_boundary=permission_boundary,
            created_at=now,
            updated_at=now,
            description=description,
            metadata=metadata or {},
        )
        return await self._store.create(identity)

    # -------------------------------------------------------------------------
    # Authentication
    # -------------------------------------------------------------------------

    async def authenticate_agent(
        self,
        agent_id: str,
        credential_type: CredentialType,
        credential_value: str,
    ) -> Optional[str]:
        """
        Authenticate an agent and return an identity token (JWT).
        Returns None if authentication fails.
        """
        agent = await self._store.get(agent_id)
        if not agent or not agent.is_active:
            return None

        # Validate credential based on type
        valid_credential = None
        if credential_type == CredentialType.CLIENT_SECRET:
            valid_credential = await self._credentials.validate_client_secret(
                agent_id, credential_value
            )
        elif credential_type == CredentialType.SIGNED_JWT:
            valid_credential = await self._validate_signed_jwt(agent, credential_value)
        # Add other credential types as needed

        if not valid_credential:
            return None

        # Issue identity token
        return self._issue_identity_token(agent, valid_credential)

    def _issue_identity_token(
        self, agent: AgentIdentity, credential: AgentCredential
    ) -> str:
        """Issue a short-lived JWT identity token for the authenticated agent."""
        now = datetime.now(timezone.utc)
        payload = {
            "iss": self._jwt_issuer,
            "sub": agent.agent_id,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=30)).timestamp()),
            "jti": str(uuid.uuid4()),
            # Agent claims
            "agent_name": agent.agent_name,
            "agent_type": agent.agent_type.value,
            "tenant_id": agent.tenant_id,
            "trust_level": agent.trust_level.value,
            "credential_id": credential.credential_id,
            # Permission boundary summary (not full policy)
            "max_scopes": list(agent.permission_boundary.allowed_scopes)[:20],
        }
        return jwt.encode(payload, self._jwt_signing_key, algorithm="HS256")

    async def _validate_signed_jwt(
        self, agent: AgentIdentity, assertion: str
    ) -> Optional[AgentCredential]:
        """Validate a signed JWT assertion from the agent."""
        for cred in agent.active_credentials:
            if cred.credential_type == CredentialType.SIGNED_JWT and cred._public_key_pem:
                try:
                    public_key = serialization.load_pem_public_key(
                        cred._public_key_pem.encode()
                    )
                    decoded = jwt.decode(
                        assertion,
                        public_key,
                        algorithms=["RS256", "ES256"],
                        audience=self._jwt_issuer,
                    )
                    # Verify the subject matches
                    if decoded.get("sub") == agent.agent_id:
                        cred.last_used_at = datetime.now(timezone.utc)
                        cred.use_count += 1
                        return cred
                except (jwt.InvalidTokenError, Exception):
                    continue
        return None

    # -------------------------------------------------------------------------
    # Identity Verification
    # -------------------------------------------------------------------------

    async def verify_identity_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Verify an agent identity token. Returns claims if valid."""
        try:
            payload = jwt.decode(
                token, self._jwt_signing_key, algorithms=["HS256"],
                issuer=self._jwt_issuer,
            )
            # Additional checks
            agent = await self._store.get(payload["sub"])
            if not agent or not agent.is_active:
                return None
            return payload
        except jwt.InvalidTokenError:
            return None

    # -------------------------------------------------------------------------
    # User Context Injection
    # -------------------------------------------------------------------------

    async def create_agent_session_with_user_context(
        self,
        agent_identity_token: str,
        user_id: str,
        user_roles: List[str],
        user_tenant_id: str,
        delegation_id: str,
        delegation_scopes: List[str],
        session_id: Optional[str] = None,
    ) -> Optional[str]:
        """
        Create a session token that binds agent identity + user context.
        This is the token used for all subsequent operations.
        """
        agent_claims = await self.verify_identity_token(agent_identity_token)
        if not agent_claims:
            return None

        # Verify tenant match
        if agent_claims["tenant_id"] != user_tenant_id:
            raise PermissionError("Agent and user must be in the same tenant")

        now = datetime.now(timezone.utc)
        session_payload = {
            "iss": self._jwt_issuer,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=15)).timestamp()),
            "jti": str(uuid.uuid4()),
            "type": "agent_session",
            # Agent identity
            "agent_id": agent_claims["sub"],
            "agent_name": agent_claims["agent_name"],
            "agent_type": agent_claims["agent_type"],
            "trust_level": agent_claims["trust_level"],
            # User context (on-behalf-of)
            "user_id": user_id,
            "user_roles": user_roles,
            "tenant_id": user_tenant_id,
            # Delegation
            "delegation_id": delegation_id,
            "delegation_scopes": delegation_scopes,
            # Session
            "session_id": session_id or str(uuid.uuid4()),
            "correlation_id": str(uuid.uuid4()),
        }
        return jwt.encode(session_payload, self._jwt_signing_key, algorithm="HS256")

    # -------------------------------------------------------------------------
    # Multi-Agent Identity Management
    # -------------------------------------------------------------------------

    async def register_sub_agent(
        self,
        parent_agent_id: str,
        sub_agent_name: str,
        sub_agent_type: AgentType,
        scope_subset: Set[str],
    ) -> AgentIdentity:
        """
        Register a sub-agent under a parent agent.
        Sub-agent's permission boundary is a subset of parent's.
        """
        parent = await self._store.get(parent_agent_id)
        if not parent or not parent.is_active:
            raise ValueError("Parent agent not found or not active")

        if parent.agent_type != AgentType.ORCHESTRATOR:
            raise ValueError("Only orchestrator agents can register sub-agents")

        # Sub-agent boundary is intersection of requested scopes with parent boundary
        allowed_scopes = scope_subset & parent.permission_boundary.allowed_scopes
        if not allowed_scopes:
            raise ValueError("No valid scopes for sub-agent")

        sub_boundary = PermissionBoundary(
            allowed_scopes=allowed_scopes,
            denied_scopes=parent.permission_boundary.denied_scopes,
            allowed_resources=parent.permission_boundary.allowed_resources,
            denied_resources=parent.permission_boundary.denied_resources,
            max_token_lifetime_seconds=min(
                300, parent.permission_boundary.max_token_lifetime_seconds
            ),
            max_actions_per_hour=parent.permission_boundary.max_actions_per_hour // 2,
        )

        return await self.register_agent(
            agent_name=sub_agent_name,
            agent_type=sub_agent_type,
            owner_id=parent.owner_id,
            tenant_id=parent.tenant_id,
            permission_boundary=sub_boundary,
            trust_level=parent.trust_level,
            metadata={"parent_agent_id": parent_agent_id},
        )

    # -------------------------------------------------------------------------
    # Suspension and Revocation
    # -------------------------------------------------------------------------

    async def suspend_agent(self, agent_id: str, reason: str) -> None:
        """Temporarily suspend an agent (can be reactivated)."""
        agent = await self._store.get(agent_id)
        if not agent:
            raise ValueError("Agent not found")
        agent.status = AgentStatus.SUSPENDED
        agent.metadata["suspension_reason"] = reason
        agent.metadata["suspended_at"] = datetime.now(timezone.utc).isoformat()
        await self._store.update(agent)

    async def revoke_agent(self, agent_id: str, reason: str) -> None:
        """Permanently revoke an agent identity (cannot be reactivated)."""
        await self._store.revoke(agent_id, reason)

    async def reactivate_agent(self, agent_id: str) -> None:
        """Reactivate a suspended agent."""
        agent = await self._store.get(agent_id)
        if not agent:
            raise ValueError("Agent not found")
        if agent.status != AgentStatus.SUSPENDED:
            raise ValueError("Only suspended agents can be reactivated")
        agent.status = AgentStatus.ACTIVE
        agent.metadata.pop("suspension_reason", None)
        agent.metadata.pop("suspended_at", None)
        await self._store.update(agent)


# =============================================================================
# REMOTE AGENT TRUST VERIFICATION
# =============================================================================

class RemoteAgentVerifier:
    """Verifies and authenticates remote/external agents."""

    def __init__(self, trusted_issuers: Dict[str, str]):
        """
        trusted_issuers: mapping of issuer_id -> public_key_pem
        """
        self._trusted_issuers = trusted_issuers

    async def verify_remote_agent(
        self, identity_assertion: str
    ) -> Optional[Dict[str, Any]]:
        """
        Verify a remote agent's identity assertion.
        The assertion is a JWT signed by the remote agent's platform.
        """
        # Decode header to get issuer
        try:
            unverified = jwt.decode(
                identity_assertion, options={"verify_signature": False}
            )
        except jwt.InvalidTokenError:
            return None

        issuer = unverified.get("iss")
        if issuer not in self._trusted_issuers:
            return None

        # Verify signature with trusted issuer's public key
        public_key_pem = self._trusted_issuers[issuer]
        try:
            public_key = serialization.load_pem_public_key(public_key_pem.encode())
            verified = jwt.decode(
                identity_assertion,
                public_key,
                algorithms=["RS256", "ES256"],
                issuer=issuer,
            )
            return {
                "remote_agent_id": verified["sub"],
                "issuer": issuer,
                "trust_level": TrustLevel.VERIFIED_EXTERNAL,
                "claims": verified,
            }
        except jwt.InvalidTokenError:
            return None


# =============================================================================
# USAGE EXAMPLE
# =============================================================================

async def example_usage():
    """Demonstrates the agent identity system."""

    # Setup
    store = InMemoryAgentIdentityStore()
    cred_manager = CredentialManager(store, signing_key="super-secret-key")
    identity_service = AgentIdentityService(
        store=store,
        credential_manager=cred_manager,
        jwt_signing_key="jwt-signing-key-change-in-production",
    )

    # 1. Register an agent
    boundary = PermissionBoundary(
        allowed_scopes={"repo:read", "repo:write:branch", "issue:create", "issue:read"},
        denied_scopes={"repo:delete", "admin:*"},
        allowed_resources=["org/myteam/**"],
        denied_resources=["org/myteam/secrets/**"],
    )

    agent = await identity_service.register_agent(
        agent_name="code-review-bot-v2",
        agent_type=AgentType.INTERACTIVE,
        owner_id="user-123",
        tenant_id="tenant-abc",
        permission_boundary=boundary,
        description="Automated code review agent",
    )
    print(f"Registered agent: {agent.agent_id}")

    # 2. Create credentials
    cred_info = await cred_manager.create_client_secret_credential(agent.agent_id)
    print(f"Credential created: {cred_info['credential_id']}")

    # 3. Authenticate agent
    identity_token = await identity_service.authenticate_agent(
        agent_id=agent.agent_id,
        credential_type=CredentialType.CLIENT_SECRET,
        credential_value=cred_info["client_secret"],
    )
    print(f"Identity token issued: {identity_token[:50]}...")

    # 4. Create session with user context
    session_token = await identity_service.create_agent_session_with_user_context(
        agent_identity_token=identity_token,
        user_id="user-456",
        user_roles=["developer", "reviewer"],
        user_tenant_id="tenant-abc",
        delegation_id="delegation-789",
        delegation_scopes=["repo:read", "issue:create"],
    )
    print(f"Session token: {session_token[:50]}...")

    # 5. Verify session
    claims = await identity_service.verify_identity_token(identity_token)
    print(f"Verified agent: {claims['agent_name']}")

    # 6. Rotate credentials
    new_cred = await cred_manager.rotate_credential(
        agent.agent_id, cred_info["credential_id"]
    )
    print(f"Rotated to new credential: {new_cred['credential_id']}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(example_usage())
