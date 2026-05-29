# Identity and Access Management (IAM) System

## 1. Requirements

### Functional Requirements
- **User Management**: CRUD operations for users with profile, credentials, MFA enrollment
- **Group Management**: Hierarchical groups with membership inheritance
- **Role Management**: Predefined and custom roles with permission boundaries
- **Policy-Based Access Control**: RBAC + ABAC with policy composition
- **Authentication**: Password, MFA (TOTP/WebAuthn/SMS), SSO (SAML 2.0, OIDC)
- **Authorization Evaluation**: Real-time policy evaluation for access decisions
- **Session Management**: Stateful sessions with configurable timeouts and step-up auth
- **API Key Management**: Create, rotate, scope, and revoke API keys
- **Audit Logging**: Immutable log of all authentication and authorization events
- **Federation**: Trust external IdPs, attribute mapping, JIT provisioning
- **Service Accounts**: Non-human identities with key rotation and least-privilege

### Non-Functional Requirements
- **Availability**: 99.999% (authorization decisions are critical path)
- **Latency**: Policy evaluation <5ms p99 for cached decisions, <50ms cold
- **Scale**: 100M users, 1B policy evaluations/day
- **Security**: Zero-trust, defense in depth, FIPS 140-2 compliant crypto
- **Compliance**: SOC2, GDPR, FedRAMP compatible audit trail
- **Consistency**: Strong consistency for permission changes (no stale allows)

## 2. Capacity Estimation

### Traffic
- Authentication requests: 50M/day (login, token refresh)
- Authorization evaluations: 1B/day (~12K QPS avg, 50K peak)
- User CRUD: 500K/day
- Audit events: 2B/day (every auth + authz event)

### Storage
- User records: 100M × 5KB = 500GB
- Policies: 10M policies × 2KB = 20GB
- Sessions: 20M active × 1KB = 20GB (Redis)
- Audit logs: 2B/day × 500 bytes = 1TB/day → 30TB/month (cold storage)
- API keys: 50M × 500 bytes = 25GB

### Compute
- Policy evaluation: 50K QPS × 5ms = 250 CPU-seconds/s → ~250 cores
- Token signing: 5K QPS × 2ms = 10 cores
- Password hashing (bcrypt): 500/s × 100ms = 50 cores

## 3. Data Modeling

### Database Schemas

```sql
-- Users
CREATE TABLE users (
    user_id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id              UUID NOT NULL,
    username            VARCHAR(255) NOT NULL,
    email               VARCHAR(255),
    email_verified      BOOLEAN DEFAULT false,
    phone               VARCHAR(50),
    display_name        VARCHAR(255),
    status              VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    user_type           VARCHAR(20) NOT NULL DEFAULT 'HUMAN', -- HUMAN, SERVICE
    password_hash       VARCHAR(255),           -- bcrypt/argon2
    password_changed_at TIMESTAMPTZ,
    mfa_enabled         BOOLEAN DEFAULT false,
    mfa_methods         JSONB DEFAULT '[]',
    federated_ids       JSONB DEFAULT '[]',     -- [{provider, external_id}]
    attributes          JSONB DEFAULT '{}',     -- Custom ABAC attributes
    login_count         INT DEFAULT 0,
    last_login_at       TIMESTAMPTZ,
    locked_until        TIMESTAMPTZ,
    failed_attempts     INT DEFAULT 0,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW(),
    CHECK (status IN ('ACTIVE','INACTIVE','SUSPENDED','PENDING_VERIFICATION')),
    UNIQUE(org_id, username),
    UNIQUE(org_id, email)
);

CREATE INDEX idx_users_org_status ON users(org_id, status);
CREATE INDEX idx_users_email ON users(email) WHERE email IS NOT NULL;
CREATE INDEX idx_users_federated ON users USING GIN(federated_ids);
CREATE INDEX idx_users_attributes ON users USING GIN(attributes);

-- Groups
CREATE TABLE groups (
    group_id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id              UUID NOT NULL,
    name                VARCHAR(255) NOT NULL,
    description         TEXT,
    parent_group_id     UUID REFERENCES groups(group_id),
    path                LTREE NOT NULL,          -- Materialized path for hierarchy
    attributes          JSONB DEFAULT '{}',
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(org_id, name)
);

CREATE INDEX idx_groups_path ON groups USING GIST(path);
CREATE INDEX idx_groups_parent ON groups(parent_group_id);

-- Group Membership
CREATE TABLE group_memberships (
    group_id            UUID NOT NULL REFERENCES groups(group_id),
    user_id             UUID NOT NULL REFERENCES users(user_id),
    membership_type     VARCHAR(20) DEFAULT 'MEMBER', -- MEMBER, ADMIN
    added_by            UUID,
    expires_at          TIMESTAMPTZ,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (group_id, user_id)
);

CREATE INDEX idx_membership_user ON group_memberships(user_id);

-- Roles
CREATE TABLE roles (
    role_id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id              UUID NOT NULL,
    name                VARCHAR(255) NOT NULL,
    description         TEXT,
    role_type           VARCHAR(20) NOT NULL DEFAULT 'CUSTOM', -- SYSTEM, CUSTOM
    permissions         JSONB NOT NULL,          -- Array of permission strings
    permission_boundary JSONB,                   -- Maximum allowed permissions
    max_session_duration INT DEFAULT 3600,
    trust_policy        JSONB,                   -- Who can assume this role
    is_active           BOOLEAN DEFAULT true,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(org_id, name)
);

CREATE INDEX idx_roles_org ON roles(org_id, is_active);
CREATE INDEX idx_roles_permissions ON roles USING GIN(permissions);

-- Role Assignments
CREATE TABLE role_assignments (
    assignment_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    role_id             UUID NOT NULL REFERENCES roles(role_id),
    principal_type      VARCHAR(10) NOT NULL,    -- USER, GROUP, SERVICE
    principal_id        UUID NOT NULL,
    resource_scope      VARCHAR(500),            -- Resource ARN pattern (optional)
    condition           JSONB,                   -- Conditional assignment
    assigned_by         UUID NOT NULL,
    expires_at          TIMESTAMPTZ,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_role_assign_principal ON role_assignments(principal_type, principal_id);
CREATE INDEX idx_role_assign_role ON role_assignments(role_id);
CREATE INDEX idx_role_assign_scope ON role_assignments(resource_scope);

-- Policies
CREATE TABLE policies (
    policy_id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id              UUID NOT NULL,
    name                VARCHAR(255) NOT NULL,
    description         TEXT,
    policy_type         VARCHAR(20) NOT NULL,    -- IDENTITY, RESOURCE, SCP, BOUNDARY
    version             INT NOT NULL DEFAULT 1,
    statements          JSONB NOT NULL,          -- Policy statements array
    is_active           BOOLEAN DEFAULT true,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(org_id, name, version)
);

CREATE INDEX idx_policies_org_type ON policies(org_id, policy_type, is_active);
CREATE INDEX idx_policies_statements ON policies USING GIN(statements);

-- Policy Attachments
CREATE TABLE policy_attachments (
    attachment_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    policy_id           UUID NOT NULL REFERENCES policies(policy_id),
    target_type         VARCHAR(20) NOT NULL,    -- USER, GROUP, ROLE, RESOURCE
    target_id           VARCHAR(500) NOT NULL,   -- ID or ARN
    attached_by         UUID NOT NULL,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_policy_attach_target ON policy_attachments(target_type, target_id);
CREATE INDEX idx_policy_attach_policy ON policy_attachments(policy_id);

-- Sessions
CREATE TABLE sessions (
    session_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES users(user_id),
    org_id              UUID NOT NULL,
    auth_method         VARCHAR(50) NOT NULL,    -- PASSWORD, SSO_SAML, SSO_OIDC, API_KEY
    auth_level          INT NOT NULL DEFAULT 1,  -- 1=basic, 2=MFA, 3=hardware key
    ip_address          INET,
    user_agent          TEXT,
    device_fingerprint  VARCHAR(64),
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    expires_at          TIMESTAMPTZ NOT NULL,
    last_activity_at    TIMESTAMPTZ DEFAULT NOW(),
    is_revoked          BOOLEAN DEFAULT false,
    revoked_reason      VARCHAR(100)
);

CREATE INDEX idx_sessions_user ON sessions(user_id, is_revoked);
CREATE INDEX idx_sessions_expiry ON sessions(expires_at) WHERE NOT is_revoked;

-- API Keys
CREATE TABLE api_keys (
    key_id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id              UUID NOT NULL,
    owner_id            UUID NOT NULL REFERENCES users(user_id),
    key_prefix          VARCHAR(8) NOT NULL,     -- First 8 chars for identification
    key_hash            VARCHAR(64) NOT NULL,    -- SHA-256 of full key
    name                VARCHAR(255) NOT NULL,
    scopes              TEXT[] NOT NULL,          -- Permission scopes
    rate_limit          INT DEFAULT 1000,        -- Requests per minute
    allowed_ips         INET[],
    last_used_at        TIMESTAMPTZ,
    expires_at          TIMESTAMPTZ,
    is_active           BOOLEAN DEFAULT true,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_api_keys_prefix ON api_keys(key_prefix) WHERE is_active;
CREATE INDEX idx_api_keys_owner ON api_keys(owner_id);
CREATE INDEX idx_api_keys_hash ON api_keys(key_hash);

-- Audit Log (append-only)
CREATE TABLE audit_log (
    event_id            UUID DEFAULT gen_random_uuid(),
    event_time          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    org_id              UUID NOT NULL,
    actor_id            UUID,
    actor_type          VARCHAR(20) NOT NULL,    -- USER, SERVICE, SYSTEM
    event_type          VARCHAR(50) NOT NULL,    -- LOGIN, LOGOUT, POLICY_EVAL, etc.
    action              VARCHAR(100) NOT NULL,
    resource_type       VARCHAR(50),
    resource_id         VARCHAR(500),
    result              VARCHAR(20) NOT NULL,    -- ALLOW, DENY, ERROR
    ip_address          INET,
    user_agent          TEXT,
    details             JSONB,
    request_id          VARCHAR(100)
) PARTITION BY RANGE (event_time);

-- Create monthly partitions
CREATE TABLE audit_log_2024_01 PARTITION OF audit_log
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');

CREATE INDEX idx_audit_org_time ON audit_log(org_id, event_time DESC);
CREATE INDEX idx_audit_actor ON audit_log(actor_id, event_time DESC);
CREATE INDEX idx_audit_resource ON audit_log(resource_type, resource_id, event_time DESC);
CREATE INDEX idx_audit_event_type ON audit_log(event_type, event_time DESC);

-- MFA Devices
CREATE TABLE mfa_devices (
    device_id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES users(user_id),
    device_type         VARCHAR(20) NOT NULL,    -- TOTP, WEBAUTHN, SMS, EMAIL
    device_name         VARCHAR(100),
    secret_encrypted    BYTEA,                   -- Encrypted TOTP secret or WebAuthn credential
    credential_id       VARCHAR(500),            -- WebAuthn credential ID
    public_key          BYTEA,                   -- WebAuthn public key
    counter             BIGINT DEFAULT 0,        -- WebAuthn signature counter
    is_primary          BOOLEAN DEFAULT false,
    last_used_at        TIMESTAMPTZ,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_mfa_user ON mfa_devices(user_id);
CREATE INDEX idx_mfa_credential ON mfa_devices(credential_id) WHERE credential_id IS NOT NULL;
```

### Kafka Topics

```yaml
topics:
  iam-auth-events:
    partitions: 64
    replication-factor: 3
    retention.ms: 604800000       # 7 days
    cleanup.policy: delete
    
  iam-policy-changes:
    partitions: 16
    replication-factor: 3
    retention.ms: -1              # Infinite (compacted)
    cleanup.policy: compact
    
  iam-audit-stream:
    partitions: 128
    replication-factor: 3
    retention.ms: 2592000000     # 30 days
    max.message.bytes: 1048576

  iam-session-events:
    partitions: 32
    replication-factor: 3
    retention.ms: 86400000       # 1 day
```

### Redis Configuration

```yaml
redis:
  sessions:
    cluster: true
    nodes: 6
    maxmemory: 32gb
    maxmemory-policy: volatile-ttl
    data-structures:
      - hash: "session:{session_id}"
      - set: "user:sessions:{user_id}"
      - string: "token:blacklist:{jti}"         # Revoked tokens

  policy-cache:
    cluster: true
    nodes: 6
    maxmemory: 16gb
    maxmemory-policy: allkeys-lru
    data-structures:
      - hash: "policy:effective:{principal_hash}"
      - string: "eval:cache:{request_hash}"     # Cached decisions
      - set: "principal:roles:{user_id}"
      - sorted-set: "rate:limit:{key_id}"
```

## 4. High-Level Design

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                           IAM SYSTEM ARCHITECTURE                                  │
├──────────────────────────────────────────────────────────────────────────────────┤
│                                                                                    │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐                 │
│  │  Web App   │  │  Mobile    │  │  API Client│  │  Service   │                 │
│  │  (OIDC)    │  │  (OAuth2)  │  │  (API Key) │  │  (mTLS)    │                 │
│  └─────┬──────┘  └─────┬──────┘  └─────┬──────┘  └─────┬──────┘                 │
│        │                │                │                │                        │
│        └────────────────┴────────────────┴────────────────┘                        │
│                                    │                                               │
│                                    ▼                                               │
│  ┌─────────────────────────────────────────────────────────────────────────┐      │
│  │                         API Gateway / Auth Proxy                          │      │
│  │  ┌──────────┐  ┌──────────────┐  ┌───────────┐  ┌──────────────────┐   │      │
│  │  │Rate Limit│  │Token Validate│  │IP Allowlist│  │Request Signing   │   │      │
│  │  └──────────┘  └──────────────┘  └───────────┘  └──────────────────┘   │      │
│  └───────────────────────────────────┬─────────────────────────────────────┘      │
│                                      │                                             │
│          ┌───────────────────────────┼───────────────────────────┐                │
│          ▼                           ▼                           ▼                  │
│  ┌───────────────┐      ┌────────────────────┐      ┌───────────────────┐         │
│  │ Authentication│      │  Authorization     │      │  Management       │         │
│  │ Service       │      │  Service           │      │  Service          │         │
│  │               │      │                    │      │                   │         │
│  │ • Login       │      │ • Policy Engine    │      │ • Users/Groups    │         │
│  │ • MFA         │      │ • Role Resolution  │      │ • Roles/Policies  │         │
│  │ • SSO/SAML    │      │ • Decision Cache   │      │ • API Keys        │         │
│  │ • Token Issue │      │ • Condition Eval   │      │ • Federation      │         │
│  │ • Session Mgmt│      │ • Audit            │      │ • Audit Config    │         │
│  └───────┬───────┘      └─────────┬──────────┘      └─────────┬─────────┘         │
│          │                         │                            │                   │
│          └─────────────────────────┼────────────────────────────┘                   │
│                                    ▼                                                │
│  ┌─────────────────────────────────────────────────────────────────────────┐      │
│  │                          Data Layer                                       │      │
│  │  ┌──────────┐  ┌─────────┐  ┌──────────┐  ┌─────────┐  ┌───────────┐  │      │
│  │  │PostgreSQL│  │  Redis  │  │  Kafka   │  │  HSM    │  │ S3 (Audit)│  │      │
│  │  │(Users,   │  │(Sessions│  │(Events,  │  │(Key Mgmt│  │           │  │      │
│  │  │ Policies)│  │ Cache)  │  │ Audit)   │  │ Signing)│  │           │  │      │
│  │  └──────────┘  └─────────┘  └──────────┘  └─────────┘  └───────────┘  │      │
│  └─────────────────────────────────────────────────────────────────────────┘      │
│                                                                                    │
│  ┌─────────────────────────────────────────────────────────────────────────┐      │
│  │                       Federation Layer                                    │      │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                   │      │
│  │  │ SAML IdPs    │  │ OIDC Providers│  │ LDAP/AD      │                   │      │
│  │  │ (Okta,Azure) │  │ (Google,GitHub)│  │ (On-premise) │                   │      │
│  │  └──────────────┘  └──────────────┘  └──────────────┘                   │      │
│  └─────────────────────────────────────────────────────────────────────────┘      │
└──────────────────────────────────────────────────────────────────────────────────┘
```

## 5. Low-Level Design (APIs)

### Authentication APIs

```yaml
# Login with password
POST /api/v1/auth/login
Request:
  {
    "username": "john.doe@company.com",
    "password": "***",
    "org_id": "org_abc123",
    "device_fingerprint": "fp_xyz789"
  }
Response: 200 (if no MFA) or 202 (MFA required)
  {
    "session_id": "sess_a1b2c3",
    "access_token": "eyJhbGciOiJSUzI1...",
    "refresh_token": "rt_opaque_d4e5f6",
    "token_type": "Bearer",
    "expires_in": 3600,
    "mfa_required": true,
    "mfa_challenge": {
      "challenge_id": "chal_g7h8i9",
      "methods_available": ["TOTP", "WEBAUTHN"],
      "expires_in": 300
    }
  }

# MFA Verification
POST /api/v1/auth/mfa/verify
Request:
  {
    "challenge_id": "chal_g7h8i9",
    "method": "TOTP",
    "code": "123456"
  }
Response: 200
  {
    "session_id": "sess_a1b2c3",
    "access_token": "eyJhbGciOiJSUzI1...",  # New token with elevated auth_level
    "auth_level": 2,
    "expires_in": 3600
  }

# OAuth2 Authorization Code + PKCE
GET /api/v1/oauth/authorize?
    response_type=code&
    client_id=client_abc&
    redirect_uri=https://app.example.com/callback&
    scope=read:users+write:reports&
    state=random_state_value&
    code_challenge=BASE64URL(SHA256(code_verifier))&
    code_challenge_method=S256
Response: 302 → redirect_uri?code=auth_code_xyz&state=random_state_value

# Token Exchange
POST /api/v1/oauth/token
Request: (application/x-www-form-urlencoded)
  grant_type=authorization_code&
  code=auth_code_xyz&
  redirect_uri=https://app.example.com/callback&
  client_id=client_abc&
  code_verifier=original_code_verifier
Response: 200
  {
    "access_token": "eyJhbGciOiJSUzI1...",
    "token_type": "Bearer",
    "expires_in": 3600,
    "refresh_token": "rt_j1k2l3",
    "scope": "read:users write:reports",
    "id_token": "eyJhbGciOiJSUzI1..."  # If openid scope
  }

# SAML SSO Initiation
GET /api/v1/auth/saml/login?org_id=org_abc123
Response: 302 → IdP SSO URL with SAMLRequest

# SAML Assertion Consumer Service (ACS)
POST /api/v1/auth/saml/acs
Request: (SAMLResponse from IdP POST binding)
Response: 302 → App redirect with session cookie

# Authorization Check
POST /api/v1/auth/authorize
Request:
  {
    "principal": {
      "type": "USER",
      "id": "user_a1b2c3",
      "session_id": "sess_x1y2z3"
    },
    "action": "s3:GetObject",
    "resource": "arn:company:s3:us-east-1:123456:bucket/reports/*",
    "context": {
      "ip_address": "10.0.1.50",
      "time": "2024-01-15T14:30:00Z",
      "mfa_authenticated": true
    }
  }
Response: 200
  {
    "decision": "ALLOW",
    "matched_statements": [
      {
        "policy_id": "pol_admin_access",
        "statement_id": "AllowS3Read",
        "effect": "Allow"
      }
    ],
    "evaluation_time_ms": 3
  }

# Policy Simulation
POST /api/v1/policies/simulate
Request:
  {
    "principal": "user_a1b2c3",
    "actions": ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"],
    "resources": ["arn:company:s3:*:*:bucket/reports/*"],
    "context": {}
  }
Response: 200
  {
    "results": [
      {"action": "s3:GetObject", "resource": "...", "decision": "ALLOW", "reason": "..."},
      {"action": "s3:PutObject", "resource": "...", "decision": "ALLOW", "reason": "..."},
      {"action": "s3:DeleteObject", "resource": "...", "decision": "DENY", "reason": "Explicit deny in policy pol_restrict_delete"}
    ]
  }
```

## 6. Deep Dive: Policy Evaluation Engine

### Policy Language

```json
{
  "Version": "2024-01-01",
  "Statement": [
    {
      "Sid": "AllowS3ReadReports",
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:ListBucket"],
      "Resource": ["arn:company:s3:*:*:reports-bucket/*"],
      "Condition": {
        "IpAddress": { "aws:SourceIp": ["10.0.0.0/8"] },
        "Bool": { "aws:MultiFactorAuthPresent": "true" },
        "DateGreaterThan": { "aws:CurrentTime": "2024-01-01T00:00:00Z" },
        "StringLike": { "s3:prefix": ["${aws:username}/*"] }
      }
    },
    {
      "Sid": "DenyDeleteAlways",
      "Effect": "Deny",
      "Action": ["s3:DeleteObject"],
      "Resource": ["arn:company:s3:*:*:reports-bucket/archived/*"]
    }
  ]
}
```

### Evaluation Algorithm

```python
from dataclasses import dataclass
from typing import List, Optional, Set
from enum import Enum
import fnmatch
import ipaddress

class Decision(Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    IMPLICIT_DENY = "IMPLICIT_DENY"

@dataclass
class EvalContext:
    principal_id: str
    action: str
    resource: str
    conditions: dict  # ip, time, mfa, custom attributes

@dataclass
class EvalResult:
    decision: Decision
    matched_statements: List[dict]
    evaluation_path: List[str]  # For debugging

class PolicyEvaluationEngine:
    """
    Implements AWS IAM-style policy evaluation logic:
    1. Gather all applicable policies
    2. Evaluate each statement
    3. Explicit Deny wins over everything
    4. At least one explicit Allow required
    5. Otherwise implicit deny
    """
    
    def __init__(self, policy_store, cache, audit_logger):
        self.policy_store = policy_store
        self.cache = cache
        self.audit = audit_logger
    
    async def evaluate(self, ctx: EvalContext) -> EvalResult:
        """Main evaluation entry point."""
        # Check cache first
        cache_key = self._compute_eval_cache_key(ctx)
        cached = await self.cache.get(f"eval:cache:{cache_key}")
        if cached:
            return cached
        
        evaluation_path = []
        
        # 1. Resolve all policies applicable to this principal
        policies = await self._gather_applicable_policies(ctx.principal_id)
        evaluation_path.append(f"Gathered {len(policies)} policies")
        
        # 2. Evaluate all statements
        explicit_allows = []
        explicit_denies = []
        
        for policy in policies:
            for statement in policy.statements:
                match_result = self._evaluate_statement(statement, ctx)
                
                if match_result == StatementMatch.MATCH_ALLOW:
                    explicit_allows.append({
                        'policy_id': policy.policy_id,
                        'statement_id': statement.get('Sid', 'unnamed'),
                        'effect': 'Allow'
                    })
                elif match_result == StatementMatch.MATCH_DENY:
                    explicit_denies.append({
                        'policy_id': policy.policy_id,
                        'statement_id': statement.get('Sid', 'unnamed'),
                        'effect': 'Deny'
                    })
        
        # 3. Apply evaluation logic: Deny > Allow > Implicit Deny
        if explicit_denies:
            result = EvalResult(
                decision=Decision.DENY,
                matched_statements=explicit_denies,
                evaluation_path=evaluation_path
            )
        elif explicit_allows:
            # 4. Check permission boundary (if set)
            if await self._check_permission_boundary(ctx):
                result = EvalResult(
                    decision=Decision.ALLOW,
                    matched_statements=explicit_allows,
                    evaluation_path=evaluation_path
                )
            else:
                result = EvalResult(
                    decision=Decision.DENY,
                    matched_statements=[{'reason': 'Permission boundary exceeded'}],
                    evaluation_path=evaluation_path
                )
        else:
            result = EvalResult(
                decision=Decision.IMPLICIT_DENY,
                matched_statements=[],
                evaluation_path=evaluation_path
            )
        
        # Cache the decision (short TTL for security)
        await self.cache.set(f"eval:cache:{cache_key}", result, ttl=60)
        
        # Audit log
        await self.audit.log_authz_decision(ctx, result)
        
        return result
    
    def _evaluate_statement(self, statement: dict, ctx: EvalContext) -> 'StatementMatch':
        """Evaluate a single policy statement against the request context."""
        effect = statement['Effect']
        
        # Check action match
        if not self._matches_action(statement.get('Action', []), 
                                     statement.get('NotAction', []), ctx.action):
            return StatementMatch.NO_MATCH
        
        # Check resource match
        if not self._matches_resource(statement.get('Resource', []),
                                       statement.get('NotResource', []), ctx.resource):
            return StatementMatch.NO_MATCH
        
        # Check conditions
        if 'Condition' in statement:
            if not self._evaluate_conditions(statement['Condition'], ctx.conditions):
                return StatementMatch.NO_MATCH
        
        return StatementMatch.MATCH_ALLOW if effect == 'Allow' else StatementMatch.MATCH_DENY
    
    def _matches_action(self, actions: list, not_actions: list, requested: str) -> bool:
        """Match action with wildcard support (e.g., s3:Get* matches s3:GetObject)."""
        if actions:
            return any(fnmatch.fnmatch(requested, pattern) for pattern in actions)
        if not_actions:
            return not any(fnmatch.fnmatch(requested, pattern) for pattern in not_actions)
        return True
    
    def _matches_resource(self, resources: list, not_resources: list, requested: str) -> bool:
        """Match resource ARN with wildcard and variable substitution."""
        if resources:
            return any(fnmatch.fnmatch(requested, pattern) for pattern in resources)
        if not_resources:
            return not any(fnmatch.fnmatch(requested, pattern) for pattern in not_resources)
        return True
    
    def _evaluate_conditions(self, conditions: dict, context: dict) -> bool:
        """Evaluate all condition blocks (AND between blocks, OR within values)."""
        for operator, condition_map in conditions.items():
            for key, expected_values in condition_map.items():
                actual_value = context.get(key)
                if actual_value is None:
                    return False
                
                if not isinstance(expected_values, list):
                    expected_values = [expected_values]
                
                if not self._evaluate_condition_operator(operator, actual_value, expected_values):
                    return False
        return True
    
    def _evaluate_condition_operator(self, operator: str, actual, expected: list) -> bool:
        """Support condition operators: StringEquals, IpAddress, DateGreaterThan, etc."""
        evaluators = {
            'StringEquals': lambda a, e: a in e,
            'StringNotEquals': lambda a, e: a not in e,
            'StringLike': lambda a, e: any(fnmatch.fnmatch(a, p) for p in e),
            'IpAddress': lambda a, e: any(
                ipaddress.ip_address(a) in ipaddress.ip_network(n) for n in e
            ),
            'Bool': lambda a, e: str(a).lower() in [str(v).lower() for v in e],
            'NumericLessThan': lambda a, e: float(a) < float(e[0]),
            'NumericGreaterThan': lambda a, e: float(a) > float(e[0]),
            'DateGreaterThan': lambda a, e: a > e[0],
            'DateLessThan': lambda a, e: a < e[0],
        }
        evaluator = evaluators.get(operator)
        if not evaluator:
            raise ValueError(f"Unknown condition operator: {operator}")
        return evaluator(actual, expected)
    
    async def _gather_applicable_policies(self, principal_id: str) -> List:
        """
        Gather all policies for a principal:
        1. Identity-based policies (attached to user/group/role)
        2. Resource-based policies (attached to target resource)
        3. Permission boundaries
        4. Service Control Policies (org-level)
        """
        # Get user's direct policies
        user_policies = await self.policy_store.get_user_policies(principal_id)
        
        # Get policies from group memberships
        groups = await self.policy_store.get_user_groups(principal_id)
        group_policies = []
        for group in groups:
            group_policies.extend(await self.policy_store.get_group_policies(group.group_id))
        
        # Get policies from assigned roles
        roles = await self.policy_store.get_user_roles(principal_id)
        role_policies = []
        for role in roles:
            role_policies.extend(role.permissions_as_policy())
        
        return user_policies + group_policies + role_policies
    
    def _compute_eval_cache_key(self, ctx: EvalContext) -> str:
        """Compute cache key for evaluation result."""
        import hashlib
        key_str = f"{ctx.principal_id}:{ctx.action}:{ctx.resource}"
        return hashlib.sha256(key_str.encode()).hexdigest()[:32]
```

### Policy Evaluation Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Policy Evaluation Flow                             │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  Request(principal, action, resource, context)                       │
│       │                                                               │
│       ▼                                                               │
│  ┌─────────────────┐   HIT                                          │
│  │  Decision Cache  │──────────▶ Return Cached Decision              │
│  └────────┬────────┘                                                 │
│           │ MISS                                                      │
│           ▼                                                           │
│  ┌─────────────────────────────────────────────────┐                 │
│  │  Gather Applicable Policies                      │                 │
│  │  ┌─────────┐ ┌──────────┐ ┌─────────┐ ┌──────┐ │                 │
│  │  │Identity │ │ Resource │ │ SCP     │ │Boundary│ │                 │
│  │  │Policies │ │ Policies │ │(Org)    │ │       │ │                 │
│  │  └─────────┘ └──────────┘ └─────────┘ └──────┘ │                 │
│  └────────────────────────┬────────────────────────┘                 │
│                           ▼                                           │
│  ┌─────────────────────────────────────────────────┐                 │
│  │  For each statement: Match action + resource     │                 │
│  │  + Evaluate conditions                           │                 │
│  └────────────────────────┬────────────────────────┘                 │
│                           ▼                                           │
│  ┌──────────────────────────────────────────┐                        │
│  │  Any EXPLICIT DENY matched?               │                        │
│  │  YES → DENY (explicit deny always wins)   │                        │
│  │  NO  → Check for ALLOW                    │                        │
│  └──────────────────┬───────────────────────┘                        │
│                     ▼                                                 │
│  ┌──────────────────────────────────────────┐                        │
│  │  Any EXPLICIT ALLOW matched?              │                        │
│  │  YES → Check permission boundary          │                        │
│  │        → ALLOW (if within boundary)        │                        │
│  │  NO  → IMPLICIT DENY (default)            │                        │
│  └──────────────────────────────────────────┘                        │
│                                                                       │
└─────────────────────────────────────────────────────────────────────┘
```

## 7. Deep Dive: Authentication Flows

### OAuth2 Authorization Code + PKCE Flow

```python
import secrets
import hashlib
import base64
import jwt
from datetime import datetime, timedelta

class OAuth2AuthorizationServer:
    """Full OAuth2 implementation with PKCE for public clients."""
    
    def __init__(self, key_store, session_store, client_registry):
        self.key_store = key_store
        self.sessions = session_store
        self.clients = client_registry
        self.auth_codes = {}  # Short-lived, should be Redis in production
    
    async def authorize(self, request: AuthorizeRequest) -> AuthorizeResponse:
        """Handle /authorize endpoint."""
        # 1. Validate client
        client = await self.clients.get(request.client_id)
        if not client:
            raise InvalidClientError()
        
        if request.redirect_uri not in client.allowed_redirect_uris:
            raise InvalidRedirectError()
        
        # 2. Validate PKCE (required for public clients)
        if client.client_type == 'public' and not request.code_challenge:
            raise PKCERequiredError()
        
        # 3. Authenticate user (redirect to login if no session)
        user = await self._get_authenticated_user(request)
        if not user:
            return RedirectToLogin(return_url=request.full_url)
        
        # 4. Check consent (skip if previously granted)
        if not await self._has_consent(user, client, request.scopes):
            return ShowConsentScreen(user, client, request.scopes)
        
        # 5. Generate authorization code
        code = secrets.token_urlsafe(32)
        await self._store_auth_code(code, {
            'user_id': user.user_id,
            'client_id': request.client_id,
            'redirect_uri': request.redirect_uri,
            'scopes': request.scopes,
            'code_challenge': request.code_challenge,
            'code_challenge_method': request.code_challenge_method,
            'nonce': request.nonce,
            'created_at': datetime.utcnow(),
            'expires_at': datetime.utcnow() + timedelta(minutes=5)
        })
        
        return RedirectResponse(
            url=f"{request.redirect_uri}?code={code}&state={request.state}"
        )
    
    async def token_exchange(self, request: TokenRequest) -> TokenResponse:
        """Handle /token endpoint - exchange code for tokens."""
        if request.grant_type == 'authorization_code':
            return await self._handle_auth_code(request)
        elif request.grant_type == 'refresh_token':
            return await self._handle_refresh(request)
        elif request.grant_type == 'client_credentials':
            return await self._handle_client_credentials(request)
        raise UnsupportedGrantTypeError()
    
    async def _handle_auth_code(self, request: TokenRequest) -> TokenResponse:
        """Exchange authorization code for tokens."""
        # 1. Retrieve and validate code
        code_data = await self._get_auth_code(request.code)
        if not code_data:
            raise InvalidGrantError("Authorization code expired or invalid")
        
        # 2. Validate PKCE
        if code_data.get('code_challenge'):
            if not request.code_verifier:
                raise PKCEVerifierRequiredError()
            
            # S256: BASE64URL(SHA256(code_verifier)) must match code_challenge
            computed = base64.urlsafe_b64encode(
                hashlib.sha256(request.code_verifier.encode()).digest()
            ).rstrip(b'=').decode()
            
            if computed != code_data['code_challenge']:
                raise InvalidGrantError("PKCE verification failed")
        
        # 3. Validate redirect_uri matches
        if request.redirect_uri != code_data['redirect_uri']:
            raise InvalidGrantError("Redirect URI mismatch")
        
        # 4. Invalidate code (one-time use)
        await self._invalidate_auth_code(request.code)
        
        # 5. Issue tokens
        user = await self.user_store.get(code_data['user_id'])
        access_token = self._issue_access_token(user, code_data['scopes'])
        refresh_token = self._issue_refresh_token(user, code_data['client_id'])
        id_token = self._issue_id_token(user, code_data) if 'openid' in code_data['scopes'] else None
        
        return TokenResponse(
            access_token=access_token,
            token_type='Bearer',
            expires_in=3600,
            refresh_token=refresh_token,
            id_token=id_token,
            scope=' '.join(code_data['scopes'])
        )
    
    def _issue_access_token(self, user, scopes: list) -> str:
        """Issue JWT access token with claims."""
        now = datetime.utcnow()
        claims = {
            'iss': 'https://auth.example.com',
            'sub': user.user_id,
            'aud': 'https://api.example.com',
            'exp': int((now + timedelta(hours=1)).timestamp()),
            'iat': int(now.timestamp()),
            'jti': secrets.token_urlsafe(16),
            'scope': ' '.join(scopes),
            'org_id': user.org_id,
            'auth_level': user.current_auth_level,
            'groups': user.group_ids[:10],  # Limit JWT size
        }
        
        private_key = self.key_store.get_signing_key()
        return jwt.encode(claims, private_key, algorithm='RS256',
                         headers={'kid': private_key.kid})
    
    def _issue_refresh_token(self, user, client_id: str) -> str:
        """Issue opaque refresh token (stored server-side)."""
        token = secrets.token_urlsafe(48)
        # Store in Redis with long TTL
        self.sessions.store_refresh_token(token, {
            'user_id': user.user_id,
            'client_id': client_id,
            'issued_at': datetime.utcnow().isoformat(),
            'rotation_count': 0
        }, ttl=86400 * 30)  # 30 days
        return token


class SAMLServiceProvider:
    """SAML 2.0 Service Provider implementation."""
    
    async def process_assertion(self, saml_response: str) -> AuthResult:
        """Process SAML Response from IdP."""
        # 1. Decode and parse
        response = self._decode_saml_response(saml_response)
        
        # 2. Validate signature (IdP's certificate)
        idp_config = await self.get_idp_config(response.issuer)
        if not self._verify_signature(response, idp_config.certificate):
            raise SAMLValidationError("Invalid signature")
        
        # 3. Validate conditions (time, audience)
        self._validate_conditions(response.conditions)
        
        # 4. Extract attributes
        attributes = self._extract_attributes(response.assertion)
        
        # 5. JIT (Just-In-Time) provisioning
        user = await self._jit_provision(attributes, idp_config)
        
        # 6. Create session
        session = await self.session_manager.create(user, auth_method='SSO_SAML')
        
        return AuthResult(user=user, session=session)
    
    async def _jit_provision(self, attributes: dict, idp_config) -> User:
        """Create or update user from SAML attributes."""
        external_id = attributes[idp_config.name_id_attribute]
        
        user = await self.user_store.find_by_federated_id(
            provider=idp_config.entity_id,
            external_id=external_id
        )
        
        if not user:
            # Create new user
            user = await self.user_store.create(
                username=attributes.get('email', external_id),
                email=attributes.get('email'),
                display_name=attributes.get('displayName'),
                federated_ids=[{
                    'provider': idp_config.entity_id,
                    'external_id': external_id
                }],
                org_id=idp_config.org_id
            )
            
            # Auto-assign groups based on IdP attributes
            if 'groups' in attributes:
                await self._sync_group_membership(user, attributes['groups'])
        
        return user


class WebAuthnAuthenticator:
    """FIDO2/WebAuthn for passwordless authentication."""
    
    async def begin_registration(self, user_id: str) -> dict:
        """Generate WebAuthn registration options."""
        user = await self.user_store.get(user_id)
        
        # Get existing credentials to exclude
        existing = await self.mfa_store.get_webauthn_credentials(user_id)
        
        options = {
            'rp': {'id': 'example.com', 'name': 'Example Corp'},
            'user': {
                'id': base64.urlsafe_b64encode(user_id.encode()).decode(),
                'name': user.username,
                'displayName': user.display_name
            },
            'challenge': base64.urlsafe_b64encode(secrets.token_bytes(32)).decode(),
            'pubKeyCredParams': [
                {'type': 'public-key', 'alg': -7},   # ES256
                {'type': 'public-key', 'alg': -257},  # RS256
            ],
            'authenticatorSelection': {
                'authenticatorAttachment': 'cross-platform',
                'userVerification': 'preferred',
                'residentKey': 'preferred'
            },
            'excludeCredentials': [
                {'type': 'public-key', 'id': c.credential_id} for c in existing
            ],
            'timeout': 60000
        }
        
        # Store challenge for verification
        await self.cache.set(f"webauthn:reg:{user_id}", options['challenge'], ttl=300)
        return options
```

## 8. Deep Dive: Token Management

### Token Lifecycle

```python
class TokenManager:
    """
    Manages JWT access tokens + opaque refresh tokens
    with rotation, revocation, and distributed blacklist.
    """
    
    def __init__(self, redis, key_store):
        self.redis = redis
        self.key_store = key_store
    
    async def refresh_access_token(self, refresh_token: str) -> TokenPair:
        """
        Refresh token rotation:
        - Issue new access token + new refresh token
        - Invalidate old refresh token
        - Detect replay (reuse of rotated token = compromise)
        """
        # 1. Validate refresh token
        token_data = await self.redis.get(f"refresh:{refresh_token}")
        if not token_data:
            raise InvalidTokenError("Refresh token expired or revoked")
        
        token_data = json.loads(token_data)
        
        # 2. Check for token reuse (potential theft)
        if token_data.get('rotated'):
            # This token was already rotated - possible token theft!
            # Revoke the entire token family
            await self._revoke_token_family(token_data['family_id'])
            await self.audit.log_security_event('TOKEN_REUSE_DETECTED', token_data)
            raise SecurityError("Refresh token reuse detected - all sessions revoked")
        
        # 3. Mark old token as rotated (but keep briefly for race conditions)
        token_data['rotated'] = True
        await self.redis.set(f"refresh:{refresh_token}", json.dumps(token_data), ex=60)
        
        # 4. Issue new token pair
        user = await self.user_store.get(token_data['user_id'])
        new_access = self._issue_access_token(user, token_data.get('scopes', []))
        new_refresh = secrets.token_urlsafe(48)
        
        await self.redis.set(f"refresh:{new_refresh}", json.dumps({
            'user_id': token_data['user_id'],
            'client_id': token_data['client_id'],
            'family_id': token_data.get('family_id', refresh_token),
            'rotation_count': token_data.get('rotation_count', 0) + 1,
            'issued_at': datetime.utcnow().isoformat()
        }), ex=86400 * 30)
        
        return TokenPair(access_token=new_access, refresh_token=new_refresh)
    
    async def revoke_token(self, token: str, token_type: str = 'access'):
        """
        Revoke a token using distributed blacklist.
        Access tokens: Add JTI to blacklist until expiry.
        Refresh tokens: Delete from store immediately.
        """
        if token_type == 'access':
            # Decode without verification to get JTI and exp
            claims = jwt.decode(token, options={"verify_signature": False})
            jti = claims['jti']
            exp = claims['exp']
            ttl = exp - int(datetime.utcnow().timestamp())
            
            if ttl > 0:
                # Add to distributed blacklist
                await self.redis.set(f"token:blacklist:{jti}", "1", ex=ttl)
                # Publish to all nodes for local cache invalidation
                await self.redis.publish("token:revocations", jti)
        
        elif token_type == 'refresh':
            await self.redis.delete(f"refresh:{token}")
    
    async def _revoke_token_family(self, family_id: str):
        """Revoke all tokens in a family (used on theft detection)."""
        # Scan for all refresh tokens in this family
        # In production, maintain a family→tokens index
        pattern = "refresh:*"
        async for key in self.redis.scan_iter(match=pattern):
            data = await self.redis.get(key)
            if data:
                parsed = json.loads(data)
                if parsed.get('family_id') == family_id:
                    await self.redis.delete(key)
    
    def validate_access_token(self, token: str) -> dict:
        """
        Validate JWT access token:
        1. Verify signature
        2. Check expiry
        3. Check blacklist
        4. Return claims
        """
        # Get signing key by kid
        header = jwt.get_unverified_header(token)
        public_key = self.key_store.get_verification_key(header['kid'])
        
        # Verify and decode
        claims = jwt.decode(
            token, 
            public_key, 
            algorithms=['RS256'],
            audience='https://api.example.com',
            issuer='https://auth.example.com'
        )
        
        # Check blacklist (local cache + Redis fallback)
        if self._is_blacklisted(claims['jti']):
            raise TokenRevokedError()
        
        return claims
```

## 9. Component Optimization

### Key Rotation

```python
class KeyRotationManager:
    """
    Automatic key rotation for signing keys.
    Supports overlapping validity for zero-downtime rotation.
    """
    
    ROTATION_INTERVAL = timedelta(days=90)
    OVERLAP_PERIOD = timedelta(days=7)  # Old key valid during transition
    
    async def rotate_signing_keys(self):
        """Generate new signing key pair, phase out old."""
        # 1. Generate new RSA key pair
        new_key = self._generate_rsa_key(bits=2048)
        new_kid = f"key_{secrets.token_hex(8)}"
        
        # 2. Store in HSM
        await self.hsm.store_key(new_kid, new_key.private_bytes)
        
        # 3. Publish new public key to JWKS endpoint
        await self.jwks_store.add_key(new_kid, new_key.public_key, 
                                       active_from=datetime.utcnow())
        
        # 4. Set new key as primary signing key
        await self.key_store.set_primary(new_kid)
        
        # 5. Mark old key for deactivation after overlap period
        old_kid = await self.key_store.get_previous_primary()
        await self.key_store.schedule_deactivation(
            old_kid, 
            at=datetime.utcnow() + self.OVERLAP_PERIOD
        )
```

### Session Store Architecture

```yaml
# Session storage in Redis Cluster
session_config:
  absolute_timeout: 24h          # Max session lifetime
  idle_timeout: 30min            # Inactivity timeout
  sliding_window: true           # Reset idle on activity
  max_sessions_per_user: 10      # Prevent session flooding
  
  step_up_auth:
    sensitive_operations:
      - "iam:DeleteUser"
      - "iam:ModifyPolicy"
      - "billing:*"
    required_auth_level: 2       # Requires MFA
    step_up_validity: 15min      # Re-prompt after 15min
```

## 10. Observability

### Metrics

```yaml
metrics:
  - iam.auth.login.total:           Counter (tags: method, result, org_id)
  - iam.auth.login.duration_ms:     Histogram (tags: method)
  - iam.auth.mfa.attempts:          Counter (tags: method, result)
  - iam.authz.evaluations:          Counter (tags: decision, cached)
  - iam.authz.latency_ms:           Histogram (tags: policy_count)
  - iam.tokens.issued:              Counter (tags: type, grant_type)
  - iam.tokens.revoked:             Counter (tags: reason)
  - iam.sessions.active:            Gauge (tags: org_id)
  - iam.sessions.expired:           Counter (tags: reason)
  - iam.federation.assertions:      Counter (tags: idp, result)
  - iam.keys.rotation:              Counter
  - iam.audit.events:               Counter (tags: event_type)
  - iam.brute_force.blocked:        Counter (tags: org_id)

alerts:
  - name: HighAuthFailureRate
    condition: rate(iam.auth.login.total{result=FAILURE}) > 100/min
    severity: critical
  - name: PolicyEvalLatencyHigh
    condition: p99(iam.authz.latency_ms) > 50
    severity: warning
  - name: TokenReuse
    condition: iam.tokens.revoked{reason=REUSE_DETECTED} > 0
    severity: critical
```

### Security Monitoring

```
Trace: Authentication(user=john@company.com)
├── [5ms]    RateLimit: Check (OK, 3/5 attempts)
├── [2ms]    User: Lookup by email
├── [150ms]  Password: Argon2 verify (PASS)
├── [1ms]    Account: Check lockout status (OK)
├── [3ms]    MFA: Check requirement (REQUIRED)
├── [user]   MFA: TOTP prompt sent
├── [8000ms] MFA: User enters TOTP code
├── [1ms]    MFA: Verify TOTP (PASS, drift=0)
├── [2ms]    Session: Create (auth_level=2)
├── [3ms]    Token: Issue JWT access + refresh
├── [1ms]    Audit: Log LOGIN_SUCCESS
└── [1ms]    Event: Publish to iam-auth-events
Total: ~8.2s (user interaction time dominant)
```

## 11. Considerations

### Trade-offs
| Decision | Chosen | Alternative | Rationale |
|----------|--------|-------------|-----------|
| Token Format | JWT (access) + Opaque (refresh) | All JWT / All opaque | JWT = stateless validation; Opaque refresh = revocable |
| Policy Cache | 60s TTL | No cache / Longer TTL | Balance: security (stale permits) vs latency |
| Password Hash | Argon2id | bcrypt | Memory-hard, resistant to GPU/ASIC attacks |
| Key Storage | HSM | Software vault | FIPS compliance, tamper-resistant key material |
| Session Store | Redis Cluster | PostgreSQL | Low-latency for per-request session validation |

### Security Hardening
- Constant-time comparison for all secret comparisons
- Account lockout after 5 failed attempts (progressive: 1min, 5min, 30min, 24h)
- Credential stuffing detection via device fingerprint + velocity checks
- All secrets encrypted with envelope encryption (data key + master key in HSM)
- Certificate pinning for federation connections

### Failure Handling
- Redis cluster failure: Fall back to DB-backed sessions (degraded latency)
- HSM unavailable: Queue token signing, serve cached JWKS (no new keys)
- Policy store failure: Fail-closed (deny all) for security-critical paths
- IdP federation timeout: Show error, offer local auth fallback if configured

### Compliance
- GDPR: Right to erasure includes all session data, audit pseudonymization
- SOC2: Immutable audit trail, access reviews, key rotation evidence
- FedRAMP: FIPS 140-2 crypto, continuous monitoring, incident response SLA
