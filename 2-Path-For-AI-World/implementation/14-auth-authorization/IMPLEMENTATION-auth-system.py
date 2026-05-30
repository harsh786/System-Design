"""
Authentication System for AI Agents
====================================
Complete implementation covering:
- JWT validation middleware
- OAuth2/OIDC integration
- Token exchange (user → agent → tool)
- On-behalf-of flow
- Permission extraction
- User context propagation
- Service-to-service auth
- Short-lived token generation
- Auth caching with invalidation
"""

import asyncio
import hashlib
import hmac
import json
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Optional
from urllib.parse import urlencode

import httpx
import jwt
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.x509 import load_pem_x509_certificate


# =============================================================================
# Core Data Models
# =============================================================================

class TokenType(Enum):
    USER = "user"
    AGENT = "agent"
    TOOL = "tool"
    SERVICE = "service"
    REFRESH = "refresh"


@dataclass
class TokenClaims:
    """Decoded and validated token claims."""
    subject: str
    issuer: str
    audience: str
    token_type: TokenType
    scopes: list[str]
    tenant_id: str
    expires_at: datetime
    issued_at: datetime
    jti: str  # JWT ID for revocation tracking
    delegation_chain: list[dict] = field(default_factory=list)
    agent_id: Optional[str] = None
    tool_permissions: list[str] = field(default_factory=list)
    original_user: Optional[str] = None
    custom_claims: dict = field(default_factory=dict)

    @property
    def is_expired(self) -> bool:
        return datetime.now(timezone.utc) >= self.expires_at

    @property
    def effective_user(self) -> str:
        """The user whose permissions should be enforced."""
        return self.original_user or self.subject

    @property
    def remaining_ttl(self) -> timedelta:
        return self.expires_at - datetime.now(timezone.utc)


@dataclass
class UserContext:
    """Propagated through the entire agent pipeline."""
    user_id: str
    tenant_id: str
    roles: list[str]
    permissions: list[str]
    groups: list[str]
    token_claims: TokenClaims
    session_id: str
    request_id: str
    delegation_chain: list[dict] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def has_permission(self, permission: str) -> bool:
        """Check if user has a specific permission (supports wildcards)."""
        for p in self.permissions:
            if p == permission:
                return True
            if p.endswith(":*"):
                prefix = p[:-2]
                if permission.startswith(prefix + ":"):
                    return True
            if p == "*":
                return True
        return False

    def has_all_permissions(self, permissions: list[str]) -> bool:
        return all(self.has_permission(p) for p in permissions)

    def has_any_permission(self, permissions: list[str]) -> bool:
        return any(self.has_permission(p) for p in permissions)


# =============================================================================
# JWKS (JSON Web Key Set) Manager
# =============================================================================

class JWKSManager:
    """Manages OIDC provider public keys with caching and rotation."""

    def __init__(self, jwks_uri: str, cache_ttl: int = 3600):
        self.jwks_uri = jwks_uri
        self.cache_ttl = cache_ttl
        self._keys: dict[str, Any] = {}
        self._last_fetch: float = 0
        self._lock = asyncio.Lock()

    async def get_signing_key(self, kid: str) -> Any:
        """Get the signing key for a given key ID."""
        if self._should_refresh() or kid not in self._keys:
            await self._refresh_keys()
        
        if kid not in self._keys:
            # Key not found even after refresh - possible key rotation
            await self._refresh_keys(force=True)
        
        if kid not in self._keys:
            raise AuthenticationError(f"Unknown signing key: {kid}")
        
        return self._keys[kid]

    def _should_refresh(self) -> bool:
        return time.time() - self._last_fetch > self.cache_ttl

    async def _refresh_keys(self, force: bool = False):
        async with self._lock:
            if not force and not self._should_refresh():
                return
            
            async with httpx.AsyncClient() as client:
                response = await client.get(self.jwks_uri, timeout=10)
                response.raise_for_status()
                jwks = response.json()

            self._keys = {}
            for key_data in jwks.get("keys", []):
                kid = key_data.get("kid")
                if kid:
                    self._keys[kid] = self._parse_jwk(key_data)
            
            self._last_fetch = time.time()

    def _parse_jwk(self, key_data: dict) -> Any:
        """Parse JWK to usable public key."""
        from jwt.algorithms import RSAAlgorithm
        return RSAAlgorithm.from_jwk(json.dumps(key_data))


# =============================================================================
# Token Validator
# =============================================================================

class TokenValidator:
    """Validates JWTs with full security checks."""

    def __init__(
        self,
        jwks_manager: JWKSManager,
        issuer: str,
        audience: str,
        clock_skew_seconds: int = 30,
        revocation_checker: Optional["TokenRevocationChecker"] = None,
    ):
        self.jwks_manager = jwks_manager
        self.issuer = issuer
        self.audience = audience
        self.clock_skew_seconds = clock_skew_seconds
        self.revocation_checker = revocation_checker

    async def validate(self, token: str) -> TokenClaims:
        """Validate token and return claims. Raises on any failure."""
        # Decode header without verification to get kid
        try:
            unverified_header = jwt.get_unverified_header(token)
        except jwt.exceptions.DecodeError as e:
            raise AuthenticationError(f"Malformed token header: {e}")

        kid = unverified_header.get("kid")
        if not kid:
            raise AuthenticationError("Token missing 'kid' header")

        algorithm = unverified_header.get("alg")
        if algorithm not in ("RS256", "RS384", "RS512", "ES256", "ES384"):
            raise AuthenticationError(f"Unsupported algorithm: {algorithm}")

        # Get signing key
        signing_key = await self.jwks_manager.get_signing_key(kid)

        # Verify and decode
        try:
            payload = jwt.decode(
                token,
                signing_key,
                algorithms=[algorithm],
                issuer=self.issuer,
                audience=self.audience,
                leeway=self.clock_skew_seconds,
                options={
                    "verify_exp": True,
                    "verify_iat": True,
                    "verify_nbf": True,
                    "require": ["exp", "iat", "sub", "iss", "aud", "jti"],
                },
            )
        except jwt.ExpiredSignatureError:
            raise AuthenticationError("Token expired")
        except jwt.InvalidIssuerError:
            raise AuthenticationError("Invalid token issuer")
        except jwt.InvalidAudienceError:
            raise AuthenticationError("Invalid token audience")
        except jwt.InvalidTokenError as e:
            raise AuthenticationError(f"Invalid token: {e}")

        # Check revocation
        jti = payload["jti"]
        if self.revocation_checker:
            if await self.revocation_checker.is_revoked(jti):
                raise AuthenticationError("Token has been revoked")

        # Build claims
        claims = TokenClaims(
            subject=payload["sub"],
            issuer=payload["iss"],
            audience=payload["aud"] if isinstance(payload["aud"], str) else payload["aud"][0],
            token_type=TokenType(payload.get("token_type", "user")),
            scopes=payload.get("scope", "").split() if isinstance(payload.get("scope"), str) else payload.get("scope", []),
            tenant_id=payload.get("tenant_id", "default"),
            expires_at=datetime.fromtimestamp(payload["exp"], tz=timezone.utc),
            issued_at=datetime.fromtimestamp(payload["iat"], tz=timezone.utc),
            jti=jti,
            delegation_chain=payload.get("delegation_chain", []),
            agent_id=payload.get("agent_id"),
            tool_permissions=payload.get("tool_permissions", []),
            original_user=payload.get("original_user"),
            custom_claims={k: v for k, v in payload.items() if k not in {
                "sub", "iss", "aud", "exp", "iat", "nbf", "jti", "scope",
                "token_type", "tenant_id", "delegation_chain", "agent_id",
                "tool_permissions", "original_user"
            }},
        )

        return claims


# =============================================================================
# Token Revocation
# =============================================================================

class TokenRevocationChecker:
    """Check if tokens have been revoked. Uses Redis-like store in production."""

    def __init__(self):
        self._revoked: set[str] = set()
        self._revoked_users: set[str] = set()  # Revoke all tokens for a user

    async def is_revoked(self, jti: str) -> bool:
        return jti in self._revoked

    async def revoke_token(self, jti: str, expires_at: datetime):
        """Revoke a specific token. Store until its natural expiry."""
        self._revoked.add(jti)

    async def revoke_all_user_tokens(self, user_id: str):
        """Revoke all tokens for a user (e.g., password change, security incident)."""
        self._revoked_users.add(user_id)

    async def is_user_revoked(self, user_id: str) -> bool:
        return user_id in self._revoked_users


# =============================================================================
# OAuth2/OIDC Client
# =============================================================================

@dataclass
class OIDCConfig:
    """OpenID Connect provider configuration."""
    issuer: str
    authorization_endpoint: str
    token_endpoint: str
    userinfo_endpoint: str
    jwks_uri: str
    scopes_supported: list[str]
    client_id: str
    client_secret: str
    redirect_uri: str


class OIDCClient:
    """Full OIDC client for user authentication."""

    def __init__(self, config: OIDCConfig):
        self.config = config
        self._http = httpx.AsyncClient(timeout=30)

    @classmethod
    async def from_discovery(cls, issuer: str, client_id: str, client_secret: str, redirect_uri: str) -> "OIDCClient":
        """Create client from OIDC discovery endpoint."""
        async with httpx.AsyncClient() as client:
            discovery_url = f"{issuer.rstrip('/')}/.well-known/openid-configuration"
            response = await client.get(discovery_url)
            response.raise_for_status()
            metadata = response.json()

        config = OIDCConfig(
            issuer=issuer,
            authorization_endpoint=metadata["authorization_endpoint"],
            token_endpoint=metadata["token_endpoint"],
            userinfo_endpoint=metadata["userinfo_endpoint"],
            jwks_uri=metadata["jwks_uri"],
            scopes_supported=metadata.get("scopes_supported", ["openid"]),
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
        )
        return cls(config)

    def get_authorization_url(self, state: str, nonce: str, scopes: list[str] = None) -> str:
        """Generate authorization URL for user login."""
        params = {
            "response_type": "code",
            "client_id": self.config.client_id,
            "redirect_uri": self.config.redirect_uri,
            "scope": " ".join(scopes or ["openid", "profile", "email"]),
            "state": state,
            "nonce": nonce,
            "prompt": "consent",
        }
        return f"{self.config.authorization_endpoint}?{urlencode(params)}"

    async def exchange_code(self, code: str) -> dict:
        """Exchange authorization code for tokens."""
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.config.redirect_uri,
            "client_id": self.config.client_id,
            "client_secret": self.config.client_secret,
        }
        response = await self._http.post(self.config.token_endpoint, data=data)
        response.raise_for_status()
        return response.json()

    async def refresh_token(self, refresh_token: str) -> dict:
        """Refresh an expired access token."""
        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": self.config.client_id,
            "client_secret": self.config.client_secret,
        }
        response = await self._http.post(self.config.token_endpoint, data=data)
        response.raise_for_status()
        return response.json()

    async def get_userinfo(self, access_token: str) -> dict:
        """Get user profile from OIDC provider."""
        headers = {"Authorization": f"Bearer {access_token}"}
        response = await self._http.get(self.config.userinfo_endpoint, headers=headers)
        response.raise_for_status()
        return response.json()


# =============================================================================
# Token Exchange Service (RFC 8693)
# =============================================================================

class TokenExchangeService:
    """
    Implements RFC 8693 token exchange for delegation chains.
    
    Flow: User Token → Agent Token → Tool Token
    Each exchange REDUCES privilege scope and TTL.
    """

    def __init__(
        self,
        token_endpoint: str,
        signing_key: rsa.RSAPrivateKey,
        issuer: str,
        validator: TokenValidator,
    ):
        self.token_endpoint = token_endpoint
        self.signing_key = signing_key
        self.issuer = issuer
        self.validator = validator

    async def exchange_for_agent_token(
        self,
        user_token: str,
        agent_id: str,
        requested_scopes: list[str],
        max_ttl: int = 900,  # 15 minutes max
    ) -> str:
        """Exchange user token for agent-scoped token."""
        # Validate the incoming user token
        user_claims = await self.validator.validate(user_token)

        # Agent scopes must be subset of user scopes
        allowed_scopes = set(user_claims.scopes) & set(requested_scopes)
        if not allowed_scopes:
            raise AuthorizationError("No overlapping scopes between user and requested agent scopes")

        # Calculate TTL: minimum of requested and remaining user token TTL
        user_remaining = (user_claims.expires_at - datetime.now(timezone.utc)).total_seconds()
        ttl = min(max_ttl, int(user_remaining))
        if ttl <= 0:
            raise AuthenticationError("User token about to expire, cannot delegate")

        # Build delegation chain
        delegation_chain = user_claims.delegation_chain + [
            {
                "entity": user_claims.subject,
                "entity_type": "user",
                "delegated_at": datetime.now(timezone.utc).isoformat(),
                "scopes_granted": list(allowed_scopes),
            }
        ]

        # Mint agent token
        now = datetime.now(timezone.utc)
        payload = {
            "sub": agent_id,
            "iss": self.issuer,
            "aud": self.issuer,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(seconds=ttl)).timestamp()),
            "nbf": int(now.timestamp()),
            "jti": str(uuid.uuid4()),
            "token_type": TokenType.AGENT.value,
            "scope": list(allowed_scopes),
            "tenant_id": user_claims.tenant_id,
            "original_user": user_claims.subject,
            "agent_id": agent_id,
            "delegation_chain": delegation_chain,
        }

        token = jwt.encode(payload, self.signing_key, algorithm="RS256", headers={"kid": "agent-key-1"})
        return token

    async def exchange_for_tool_token(
        self,
        agent_token: str,
        tool_name: str,
        required_permissions: list[str],
        max_ttl: int = 30,  # 30 seconds max for tool tokens
    ) -> str:
        """Exchange agent token for single-use tool token."""
        agent_claims = await self.validator.validate(agent_token)

        if agent_claims.token_type != TokenType.AGENT:
            raise AuthorizationError("Only agent tokens can be exchanged for tool tokens")

        # Tool permissions must be subset of agent scopes
        allowed = set(agent_claims.scopes) & set(required_permissions)
        if set(required_permissions) - set(agent_claims.scopes):
            missing = set(required_permissions) - set(agent_claims.scopes)
            raise AuthorizationError(f"Agent lacks permissions for tool: {missing}")

        # Very short TTL for tool tokens
        agent_remaining = (agent_claims.expires_at - datetime.now(timezone.utc)).total_seconds()
        ttl = min(max_ttl, int(agent_remaining))

        delegation_chain = agent_claims.delegation_chain + [
            {
                "entity": agent_claims.subject,
                "entity_type": "agent",
                "delegated_at": datetime.now(timezone.utc).isoformat(),
                "tool": tool_name,
                "scopes_granted": list(allowed),
            }
        ]

        now = datetime.now(timezone.utc)
        payload = {
            "sub": f"tool:{tool_name}",
            "iss": self.issuer,
            "aud": self.issuer,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(seconds=ttl)).timestamp()),
            "nbf": int(now.timestamp()),
            "jti": str(uuid.uuid4()),
            "token_type": TokenType.TOOL.value,
            "scope": list(allowed),
            "tenant_id": agent_claims.tenant_id,
            "original_user": agent_claims.original_user,
            "agent_id": agent_claims.agent_id,
            "tool_name": tool_name,
            "delegation_chain": delegation_chain,
            "single_use": True,
        }

        token = jwt.encode(payload, self.signing_key, algorithm="RS256", headers={"kid": "agent-key-1"})
        return token


# =============================================================================
# On-Behalf-Of Flow
# =============================================================================

class OnBehalfOfFlow:
    """
    Implements On-Behalf-Of (OBO) flow.
    Agent acts AS the user with the user's permissions (reduced scope).
    Downstream services see both agent identity and user identity.
    """

    def __init__(self, token_endpoint: str, client_id: str, client_secret: str):
        self.token_endpoint = token_endpoint
        self.client_id = client_id
        self.client_secret = client_secret
        self._http = httpx.AsyncClient(timeout=30)

    async def get_obo_token(
        self,
        user_assertion: str,
        scopes: list[str],
        resource: str,
    ) -> dict:
        """
        Exchange user's token for an OBO token targeting a downstream resource.
        
        The resulting token:
        - Has the user as subject
        - Has the agent as actor (act claim)
        - Is scoped to the requested resource
        - Has reduced permissions
        """
        data = {
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
            "assertion": user_assertion,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "scope": " ".join(scopes),
            "requested_token_use": "on_behalf_of",
            "resource": resource,
        }

        response = await self._http.post(self.token_endpoint, data=data)
        if response.status_code != 200:
            error = response.json()
            raise AuthenticationError(
                f"OBO token request failed: {error.get('error_description', error.get('error'))}"
            )
        
        return response.json()


# =============================================================================
# Permission Extractor
# =============================================================================

class PermissionExtractor:
    """Extract and expand permissions from token claims and external sources."""

    def __init__(self, role_permission_map: dict[str, list[str]] = None):
        # Role → permissions mapping (loaded from config/DB in production)
        self.role_permission_map = role_permission_map or {
            "admin": ["*"],
            "editor": ["docs:read", "docs:write", "tools:execute", "calendar:read", "calendar:write"],
            "viewer": ["docs:read", "calendar:read"],
            "agent_basic": ["docs:read", "tools:execute"],
        }

    async def extract_permissions(self, claims: TokenClaims) -> tuple[list[str], list[str], list[str]]:
        """
        Extract roles, permissions, and groups from token claims.
        Returns: (roles, permissions, groups)
        """
        # Roles from token
        roles = claims.custom_claims.get("roles", [])
        if isinstance(roles, str):
            roles = [roles]

        # Groups from token
        groups = claims.custom_claims.get("groups", [])
        if isinstance(groups, str):
            groups = [groups]

        # Expand role → permissions
        permissions = set(claims.scopes)  # Start with token scopes
        for role in roles:
            role_perms = self.role_permission_map.get(role, [])
            permissions.update(role_perms)

        # Tool permissions from token (if agent token)
        if claims.tool_permissions:
            permissions.update(claims.tool_permissions)

        return roles, list(permissions), groups

    async def build_user_context(
        self,
        claims: TokenClaims,
        request_id: str = None,
        session_id: str = None,
    ) -> UserContext:
        """Build complete user context from validated token claims."""
        roles, permissions, groups = await self.extract_permissions(claims)

        return UserContext(
            user_id=claims.effective_user,
            tenant_id=claims.tenant_id,
            roles=roles,
            permissions=permissions,
            groups=groups,
            token_claims=claims,
            session_id=session_id or str(uuid.uuid4()),
            request_id=request_id or str(uuid.uuid4()),
            delegation_chain=claims.delegation_chain,
        )


# =============================================================================
# Auth Cache with Invalidation
# =============================================================================

class AuthCache:
    """
    Caches auth decisions with proper invalidation.
    In production, use Redis with pub/sub for distributed invalidation.
    """

    def __init__(self, default_ttl: int = 300):
        self.default_ttl = default_ttl
        self._cache: dict[str, tuple[Any, float]] = {}  # key → (value, expires_at)
        self._invalidation_subscriptions: list[callable] = []

    def get(self, key: str) -> Optional[Any]:
        """Get cached value if not expired."""
        if key in self._cache:
            value, expires_at = self._cache[key]
            if time.time() < expires_at:
                return value
            del self._cache[key]
        return None

    def set(self, key: str, value: Any, ttl: int = None):
        """Cache a value with TTL."""
        expires_at = time.time() + (ttl or self.default_ttl)
        self._cache[key] = (value, expires_at)

    def invalidate(self, key: str):
        """Invalidate a specific cache entry."""
        self._cache.pop(key, None)

    def invalidate_prefix(self, prefix: str):
        """Invalidate all entries matching a prefix (e.g., user permissions change)."""
        keys_to_remove = [k for k in self._cache if k.startswith(prefix)]
        for key in keys_to_remove:
            del self._cache[key]

    def invalidate_user(self, user_id: str):
        """Invalidate all cached data for a user."""
        self.invalidate_prefix(f"user:{user_id}:")

    def invalidate_tenant(self, tenant_id: str):
        """Invalidate all cached data for a tenant."""
        self.invalidate_prefix(f"tenant:{tenant_id}:")

    def clear(self):
        """Clear entire cache (nuclear option)."""
        self._cache.clear()


# =============================================================================
# Service-to-Service Authentication
# =============================================================================

class ServiceAuthenticator:
    """
    Handles service-to-service authentication using client credentials.
    Each service has its own identity and credential set.
    """

    def __init__(
        self,
        service_id: str,
        token_endpoint: str,
        client_id: str,
        client_secret: str,
    ):
        self.service_id = service_id
        self.token_endpoint = token_endpoint
        self.client_id = client_id
        self.client_secret = client_secret
        self._http = httpx.AsyncClient(timeout=30)
        self._token_cache: dict[str, tuple[str, float]] = {}  # resource → (token, expires_at)

    async def get_service_token(self, resource: str, scopes: list[str]) -> str:
        """Get a service-to-service token for accessing a resource."""
        cache_key = f"{resource}:{','.join(sorted(scopes))}"
        
        # Check cache (with 60s buffer before expiry)
        if cache_key in self._token_cache:
            token, expires_at = self._token_cache[cache_key]
            if time.time() < expires_at - 60:
                return token

        # Request new token
        data = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "scope": " ".join(scopes),
            "resource": resource,
        }

        response = await self._http.post(self.token_endpoint, data=data)
        response.raise_for_status()
        token_data = response.json()

        access_token = token_data["access_token"]
        expires_in = token_data.get("expires_in", 3600)
        self._token_cache[cache_key] = (access_token, time.time() + expires_in)

        return access_token


# =============================================================================
# Authentication Middleware
# =============================================================================

class AuthMiddleware:
    """
    Middleware that validates tokens and builds user context for every request.
    Integrates with web frameworks (FastAPI, Flask, etc.)
    """

    def __init__(
        self,
        validator: TokenValidator,
        permission_extractor: PermissionExtractor,
        cache: AuthCache,
        revocation_checker: TokenRevocationChecker,
    ):
        self.validator = validator
        self.permission_extractor = permission_extractor
        self.cache = cache
        self.revocation_checker = revocation_checker

    async def authenticate(self, authorization_header: str, request_id: str = None) -> UserContext:
        """
        Authenticate a request from its Authorization header.
        Returns UserContext or raises AuthenticationError.
        """
        if not authorization_header:
            raise AuthenticationError("Missing Authorization header")

        parts = authorization_header.split(" ", 1)
        if len(parts) != 2 or parts[0].lower() != "bearer":
            raise AuthenticationError("Invalid Authorization header format. Expected: Bearer <token>")

        token = parts[1]

        # Check cache first (keyed by token hash to avoid storing tokens)
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        cached_context = self.cache.get(f"auth:{token_hash}")
        if cached_context:
            # Even with cache hit, check revocation
            if await self.revocation_checker.is_revoked(cached_context.token_claims.jti):
                self.cache.invalidate(f"auth:{token_hash}")
                raise AuthenticationError("Token has been revoked")
            if await self.revocation_checker.is_user_revoked(cached_context.user_id):
                self.cache.invalidate(f"auth:{token_hash}")
                raise AuthenticationError("All user tokens have been revoked")
            return cached_context

        # Validate token
        claims = await self.validator.validate(token)

        # Check user-level revocation
        if await self.revocation_checker.is_user_revoked(claims.effective_user):
            raise AuthenticationError("All user tokens have been revoked")

        # Build user context
        context = await self.permission_extractor.build_user_context(
            claims, request_id=request_id
        )

        # Cache the result (TTL = min of token remaining TTL and cache default)
        cache_ttl = min(
            int(claims.remaining_ttl.total_seconds()),
            self.cache.default_ttl,
        )
        if cache_ttl > 0:
            self.cache.set(f"auth:{token_hash}", context, ttl=cache_ttl)

        return context


# =============================================================================
# Agent Auth Pipeline
# =============================================================================

class AgentAuthPipeline:
    """
    Complete auth pipeline for an AI agent system.
    Handles the full flow: user auth → agent delegation → tool authorization.
    """

    def __init__(
        self,
        auth_middleware: AuthMiddleware,
        token_exchange: TokenExchangeService,
        obo_flow: OnBehalfOfFlow,
        service_auth: ServiceAuthenticator,
    ):
        self.auth_middleware = auth_middleware
        self.token_exchange = token_exchange
        self.obo_flow = obo_flow
        self.service_auth = service_auth
        self._audit_log: list[dict] = []

    async def authenticate_user_request(
        self,
        authorization_header: str,
        request_id: str,
    ) -> UserContext:
        """Step 1: Authenticate the incoming user request."""
        context = await self.auth_middleware.authenticate(authorization_header, request_id)
        self._audit("user_authenticated", context)
        return context

    async def create_agent_session(
        self,
        user_context: UserContext,
        agent_id: str,
        required_scopes: list[str],
    ) -> str:
        """Step 2: Create delegated agent token for this session."""
        # Reconstruct user token from context (in practice, pass the original token)
        # Here we use token exchange
        agent_token = await self.token_exchange.exchange_for_agent_token(
            user_token=self._get_user_token(user_context),
            agent_id=agent_id,
            requested_scopes=required_scopes,
        )
        self._audit("agent_session_created", user_context, extra={
            "agent_id": agent_id,
            "scopes": required_scopes,
        })
        return agent_token

    async def authorize_tool_execution(
        self,
        agent_token: str,
        tool_name: str,
        required_permissions: list[str],
        user_context: UserContext,
    ) -> str:
        """Step 3: Create short-lived tool token for specific tool execution."""
        # Verify user still has required permissions
        if not user_context.has_all_permissions(required_permissions):
            raise AuthorizationError(
                f"User {user_context.user_id} lacks permissions for tool {tool_name}: "
                f"required={required_permissions}"
            )

        tool_token = await self.token_exchange.exchange_for_tool_token(
            agent_token=agent_token,
            tool_name=tool_name,
            required_permissions=required_permissions,
        )
        self._audit("tool_authorized", user_context, extra={
            "tool": tool_name,
            "permissions": required_permissions,
        })
        return tool_token

    def _get_user_token(self, context: UserContext) -> str:
        """In production, store and retrieve the original token securely."""
        # This is a placeholder - real implementation stores token in secure session
        return context.metadata.get("original_token", "")

    def _audit(self, event: str, context: UserContext, extra: dict = None):
        """Audit log entry for every auth decision."""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": event,
            "user_id": context.user_id,
            "tenant_id": context.tenant_id,
            "session_id": context.session_id,
            "request_id": context.request_id,
            "delegation_chain": context.delegation_chain,
        }
        if extra:
            entry.update(extra)
        self._audit_log.append(entry)


# =============================================================================
# Exceptions
# =============================================================================

class AuthenticationError(Exception):
    """Raised when authentication fails (401)."""
    pass


class AuthorizationError(Exception):
    """Raised when authorization fails (403)."""
    pass


# =============================================================================
# FastAPI Integration Example
# =============================================================================

"""
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.security import HTTPBearer

app = FastAPI()
security = HTTPBearer()

# Initialize auth components
jwks_manager = JWKSManager(jwks_uri="https://auth.example.com/.well-known/jwks.json")
revocation_checker = TokenRevocationChecker()
validator = TokenValidator(
    jwks_manager=jwks_manager,
    issuer="https://auth.example.com",
    audience="ai-agent-api",
    revocation_checker=revocation_checker,
)
permission_extractor = PermissionExtractor()
cache = AuthCache(default_ttl=300)
middleware = AuthMiddleware(validator, permission_extractor, cache, revocation_checker)


async def get_user_context(request: Request) -> UserContext:
    auth_header = request.headers.get("Authorization", "")
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    try:
        return await middleware.authenticate(auth_header, request_id)
    except AuthenticationError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except AuthorizationError as e:
        raise HTTPException(status_code=403, detail=str(e))


@app.post("/agent/query")
async def agent_query(query: str, context: UserContext = Depends(get_user_context)):
    # User context flows through entire pipeline
    # Retrieval filtered by context.permissions
    # Tools authorized against context.permissions
    pass
"""


# =============================================================================
# Usage Example
# =============================================================================

async def example_flow():
    """Demonstrates the complete auth flow."""
    
    # 1. Setup (normally done at app startup)
    jwks_manager = JWKSManager("https://auth.example.com/.well-known/jwks.json")
    revocation_checker = TokenRevocationChecker()
    validator = TokenValidator(
        jwks_manager=jwks_manager,
        issuer="https://auth.example.com",
        audience="ai-agent-api",
        revocation_checker=revocation_checker,
    )
    permission_extractor = PermissionExtractor()
    cache = AuthCache()
    middleware = AuthMiddleware(validator, permission_extractor, cache, revocation_checker)
    
    print("Auth system initialized")
    print("Flow: User Token → Agent Token (15min) → Tool Token (30s)")
    print("Each hop reduces privilege and TTL")
    print("Every decision is audited with full delegation chain")


if __name__ == "__main__":
    asyncio.run(example_flow())
