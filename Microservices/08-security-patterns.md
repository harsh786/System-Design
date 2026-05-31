# Security Patterns in Microservices

## Authentication & Authorization

### OAuth 2.0 Flows

**What it is:** An authorization framework that enables applications to obtain limited access to user accounts on third-party services.

#### Authorization Code Flow (with PKCE)
**Threat it addresses:** Token theft, authorization code interception.

```
User → Client → Authorization Server (/authorize)
     ← Redirect with authorization code
Client → Authorization Server (/token) + code + code_verifier
     ← Access Token + Refresh Token
Client → Resource Server + Access Token
```

**PKCE (Proof Key for Code Exchange):**
```python
import hashlib, base64, secrets

# Client generates code_verifier (random string)
code_verifier = secrets.token_urlsafe(43)

# Client creates code_challenge
code_challenge = base64.urlsafe_b64encode(
    hashlib.sha256(code_verifier.encode()).digest()
).rstrip(b'=').decode()

# Send code_challenge in /authorize request
# Send code_verifier in /token request
# Server verifies: SHA256(code_verifier) == code_challenge
```

**Use for:** Web apps, mobile apps, SPAs (always use PKCE).

#### Client Credentials Flow
**Use for:** Service-to-service communication (no user involved).

```python
# Service A gets token to call Service B
response = requests.post("https://auth-server/token", data={
    "grant_type": "client_credentials",
    "client_id": "service-a",
    "client_secret": "secret",
    "scope": "orders:read"
})
access_token = response.json()["access_token"]
```

---

### OpenID Connect (OIDC)

**What it is:** Identity layer on top of OAuth 2.0. OAuth gives authorization; OIDC adds authentication (who the user is).

**Key addition:** ID Token (JWT containing user identity claims).

```json
{
  "iss": "https://auth.example.com",
  "sub": "user-42",
  "aud": "my-app",
  "exp": 1704067200,
  "iat": 1704063600,
  "name": "John Doe",
  "email": "john@example.com"
}
```

**Best practices:**
- Always validate ID token signature, issuer, audience, expiry
- Use the `sub` claim as the stable user identifier (not email)
- Implement token refresh before expiry

---

### JWT (JSON Web Tokens)

**Structure:** `header.payload.signature` (base64url encoded)

```
eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiJ1c2VyLTQyIiwicm9sZXMiOlsiYWRtaW4iXX0.signature
```

**Validation checklist:**
1. Verify signature (RS256 preferred over HS256)
2. Check `exp` (expiry) - reject expired tokens
3. Check `iss` (issuer) - must match expected auth server
4. Check `aud` (audience) - must match this service
5. Check `nbf` (not before) if present
6. Check `iat` (issued at) - reject too old tokens

**Refresh Token strategy:**
```
Access Token: Short-lived (5-15 min)
Refresh Token: Long-lived (hours/days), stored securely, rotated on use

Client → /token (refresh_token grant) → New Access Token + New Refresh Token
```

**Best practices:**
- Use asymmetric keys (RS256/ES256) so services can verify without the signing key
- Keep JWTs small (don't embed entire permission sets)
- Implement token revocation via short expiry + deny-list for logout

**Common mistakes:**
- Using HS256 (shared secret across services)
- JWTs that never expire
- Storing sensitive data in JWT payload (it's base64, not encrypted)
- Not validating all claims

---

### API Key Management

**Threat it addresses:** Unauthorized API access, usage tracking.

**Implementation:**
```python
# Generate API keys
import secrets
api_key = f"sk_live_{secrets.token_urlsafe(32)}"

# Store hash only (never store plaintext keys)
key_hash = hashlib.sha256(api_key.encode()).hexdigest()

# Validation
def validate_api_key(provided_key):
    provided_hash = hashlib.sha256(provided_key.encode()).hexdigest()
    return db.api_keys.find_one({"hash": provided_hash, "revoked": False})
```

**Best practices:**
- Prefix keys for identification (`sk_live_`, `sk_test_`)
- Support key rotation (multiple active keys per client)
- Rate limit per key
- Log key usage but never log the key itself
- Support scoped keys (read-only, specific resources)

---

### mTLS (Mutual TLS) Between Services

**Threat it addresses:** Service impersonation, eavesdropping on east-west traffic.

**What it is:** Both client and server present certificates to authenticate each other.

```
Regular TLS:    Client verifies Server's cert
Mutual TLS:     Client verifies Server's cert AND Server verifies Client's cert
```

**Implementation with Istio:**
```yaml
apiVersion: security.istio.io/v1beta1
kind: PeerAuthentication
metadata:
  name: default
  namespace: production
spec:
  mtls:
    mode: STRICT  # All traffic must be mTLS
```

**Certificate management:**
- Use short-lived certificates (24h) with automatic rotation
- SPIFFE/SPIRE for workload identity
- Service mesh handles this transparently

---

### Token Relay Pattern

**What it is:** The API gateway or BFF receives a user token and relays it (or an exchanged version) to downstream services.

```
User → API Gateway (validates token) → Service A (receives token or claims)
                                      → Service B (receives token or claims)
```

**Implementation approaches:**
1. **Pass-through:** Forward the original JWT to all services
2. **Token exchange:** Exchange external token for internal token with different claims
3. **Claims header:** Gateway validates token, passes claims as trusted headers

---

### Token Exchange (RFC 8693)

**What it is:** A service exchanges one token for another with different scope/audience.

**Use case:** Service A has a user token but needs to call Service B with a token scoped specifically for B.

```http
POST /token HTTP/1.1
Content-Type: application/x-www-form-urlencoded

grant_type=urn:ietf:params:oauth:grant-type:token-exchange
&subject_token=<original_token>
&subject_token_type=urn:ietf:params:oauth:token-type:access_token
&audience=service-b
&scope=orders:read
```

---

## API Security

### API Gateway as Security Enforcement Point

**Threat it addresses:** Inconsistent security enforcement, direct service access.

**Responsibilities:**
- Authentication (validate tokens before routing)
- Rate limiting
- Input validation (schema validation)
- IP allowlisting/blocklisting
- Request/response transformation
- TLS termination

**Configuration (Kong):**
```yaml
services:
  - name: order-service
    url: http://order-service:8080
    routes:
      - paths: ["/api/v1/orders"]
    plugins:
      - name: jwt
      - name: rate-limiting
        config:
          minute: 100
          policy: redis
      - name: request-size-limiting
        config:
          allowed_payload_size: 1  # MB
```

---

### Rate Limiting and Throttling

**Threat it addresses:** DDoS, brute force, resource exhaustion, cost abuse.

**Algorithms:**
| Algorithm | Behavior | Best For |
|-----------|----------|----------|
| Token Bucket | Burst-friendly, refills over time | API rate limits |
| Sliding Window | Smooth, no burst spikes | Fair usage |
| Fixed Window | Simple, can have boundary spikes | Basic protection |
| Leaky Bucket | Smooth output rate | Queue processing |

**Implementation (Redis + Token Bucket):**
```python
import redis, time

def is_rate_limited(client_id, limit=100, window=60):
    r = redis.Redis()
    key = f"ratelimit:{client_id}"
    current = r.get(key)
    if current and int(current) >= limit:
        return True
    pipe = r.pipeline()
    pipe.incr(key)
    pipe.expire(key, window)
    pipe.execute()
    return False
```

**Best practices:**
- Return `429 Too Many Requests` with `Retry-After` header
- Rate limit by: API key, user ID, IP, or combination
- Different limits per tier (free: 100/min, pro: 10000/min)
- Apply at gateway AND per-service (defense in depth)

---

### OWASP API Security Top 10

1. **Broken Object Level Authorization** - Check user owns the resource
2. **Broken Authentication** - Weak auth mechanisms
3. **Broken Object Property Level Authorization** - Mass assignment
4. **Unrestricted Resource Consumption** - No rate limits
5. **Broken Function Level Authorization** - Missing role checks
6. **Unrestricted Access to Sensitive Business Flows** - No bot protection
7. **Server Side Request Forgery** - Unvalidated URLs
8. **Security Misconfiguration** - Default configs, verbose errors
9. **Improper Inventory Management** - Shadow/zombie APIs
10. **Unsafe Consumption of APIs** - Trusting third-party responses

---

### Input Validation and Sanitization

**Threat it addresses:** Injection attacks, data corruption, crashes.

```python
from pydantic import BaseModel, validator, constr
from typing import Optional

class CreateOrderRequest(BaseModel):
    product_id: constr(pattern=r'^[a-zA-Z0-9\-]{1,50}$')
    quantity: int
    shipping_address: str

    @validator('quantity')
    def quantity_valid(cls, v):
        if v < 1 or v > 1000:
            raise ValueError('Quantity must be between 1 and 1000')
        return v

    @validator('shipping_address')
    def address_length(cls, v):
        if len(v) > 500:
            raise ValueError('Address too long')
        return v
```

**Best practices:**
- Validate at API gateway (schema) AND at service (business rules)
- Allowlist valid input patterns, don't blocklist bad patterns
- Limit request body size
- Sanitize output to prevent stored XSS

---

## Network Security

### Zero Trust Architecture

**What it is:** "Never trust, always verify." Every request is authenticated and authorized regardless of network location.

**Principles:**
1. No implicit trust based on network location
2. Least privilege access
3. Continuous verification (not just at connection time)
4. Assume breach (encrypt everything, limit blast radius)

**Implementation in microservices:**
- mTLS between all services (even in same cluster)
- Per-request authorization (not just at gateway)
- Short-lived credentials
- Micro-segmentation via network policies

---

### Service Mesh Security (Istio mTLS)

**What it is:** Infrastructure-layer security handled by sidecar proxies.

**Capabilities:**
- Automatic mTLS between all services
- Fine-grained authorization policies
- Certificate rotation
- Traffic encryption without application changes

**Authorization Policy:**
```yaml
apiVersion: security.istio.io/v1beta1
kind: AuthorizationPolicy
metadata:
  name: order-service-policy
  namespace: production
spec:
  selector:
    matchLabels:
      app: order-service
  rules:
    - from:
        - source:
            principals: ["cluster.local/ns/production/sa/api-gateway"]
            principals: ["cluster.local/ns/production/sa/payment-service"]
      to:
        - operation:
            methods: ["GET", "POST"]
            paths: ["/api/v1/orders*"]
```

---

### Network Policies (Kubernetes)

**Threat it addresses:** Lateral movement after compromise.

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: order-service-netpol
  namespace: production
spec:
  podSelector:
    matchLabels:
      app: order-service
  policyTypes:
    - Ingress
    - Egress
  ingress:
    - from:
        - podSelector:
            matchLabels:
              app: api-gateway
      ports:
        - port: 8080
  egress:
    - to:
        - podSelector:
            matchLabels:
              app: postgres
      ports:
        - port: 5432
    - to:  # DNS
        - namespaceSelector: {}
          podSelector:
            matchLabels:
              k8s-app: kube-dns
      ports:
        - port: 53
          protocol: UDP
```

**Best practices:**
- Default deny all, then allowlist
- Separate namespaces per team/environment
- Restrict egress (prevent data exfiltration)

---

### East-West vs North-South Traffic

| | North-South | East-West |
|--|-------------|-----------|
| Direction | External ↔ Cluster | Service ↔ Service |
| Security | API Gateway, WAF, TLS termination | mTLS, Network Policies |
| Tools | Ingress controller, CDN, DDoS protection | Service mesh, NetworkPolicy |

---

## Data Security

### Encryption at Rest and in Transit

**In transit:**
- TLS 1.3 for external traffic
- mTLS for service-to-service
- Encrypted connections to databases (SSL mode=verify-full)

**At rest:**
- Database encryption (AWS RDS encryption, Azure TDE)
- Application-level encryption for sensitive fields
- Encrypted backups

```python
# Application-level field encryption
from cryptography.fernet import Fernet

class EncryptedField:
    def __init__(self, key):
        self.cipher = Fernet(key)

    def encrypt(self, plaintext: str) -> str:
        return self.cipher.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        return self.cipher.decrypt(ciphertext.encode()).decode()

# Use for PII fields
ssn_encrypted = encrypted_field.encrypt("123-45-6789")
```

---

### Secrets Management

**Threat it addresses:** Credential exposure in code, config, or environment variables.

#### HashiCorp Vault
```python
import hvac

client = hvac.Client(url='https://vault.internal:8200')
# Authenticate via Kubernetes service account
client.auth.kubernetes.login(role='order-service', jwt=sa_token)

# Read secret
secret = client.secrets.kv.v2.read_secret_version(path='order-service/db')
db_password = secret['data']['data']['password']
```

#### AWS Secrets Manager
```python
import boto3

client = boto3.client('secretsmanager')
response = client.get_secret_value(SecretId='prod/order-service/db')
secret = json.loads(response['SecretString'])
```

**Key rotation strategies:**
- Automatic rotation (Vault dynamic secrets, AWS rotation lambda)
- Dual-read period: Both old and new credentials valid during rotation
- Short-lived credentials (Vault leases, AWS STS temporary credentials)

**Best practices:**
- Never commit secrets to git (use pre-commit hooks: gitleaks, trufflehog)
- Rotate secrets regularly (90 days max, prefer shorter)
- Audit secret access
- Use dynamic secrets where possible (generated on demand, auto-expire)

---

### Data Masking and Tokenization

**Threat it addresses:** PII exposure in logs, analytics, non-production environments.

**Tokenization:** Replace sensitive data with non-reversible tokens.
```
Credit Card: 4111-1111-1111-1111 → tok_abc123def456
SSN: 123-45-6789 → tok_xyz789
```

**Data masking for logs:**
```python
import re

MASK_PATTERNS = [
    (r'\b\d{3}-\d{2}-\d{4}\b', '***-**-****'),           # SSN
    (r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b', '****-****-****-****'),  # CC
    (r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', '***@***.***'),      # Email
]

def mask_pii(text: str) -> str:
    for pattern, replacement in MASK_PATTERNS:
        text = re.sub(pattern, replacement, text)
    return text
```

---

### GDPR/CCPA Compliance in Microservices

**Challenges:**
- User data scattered across many services and databases
- Right to deletion requires coordinating across services
- Data lineage tracking is complex

**Implementation patterns:**
- **Data catalog:** Map which services store what PII
- **Deletion choreography:** Event-driven deletion across services
  ```
  UserDeletionRequested → order-service (anonymize) 
                        → payment-service (delete tokens)
                        → analytics-service (anonymize)
                        → UserDeletionCompleted
  ```
- **Consent management service:** Centralized consent tracking
- **Data retention policies:** Automated expiry per data category

---

## Security Patterns

### Defense in Depth

**What it is:** Multiple layers of security so that if one fails, others still protect.

```
Layer 1: CDN/WAF (DDoS protection, bot detection)
Layer 2: API Gateway (auth, rate limiting, input validation)
Layer 3: Network Policies (restrict lateral movement)
Layer 4: Service Mesh (mTLS, authorization policies)
Layer 5: Application (business logic authorization)
Layer 6: Data (encryption, masking, access controls)
```

---

### Sidecar Security Pattern

**What it is:** Offload security concerns to a sidecar container that intercepts all traffic.

**Responsibilities:**
- TLS termination/origination
- Token validation
- Policy enforcement
- Audit logging

**Why it matters:** Application code doesn't need security libraries. Consistent enforcement. Language-agnostic.

---

### Security as Code (OPA/Rego Policies)

**What it is:** Define authorization policies as code, version-controlled and testable.

**Open Policy Agent (OPA) with Rego:**
```rego
# policy.rego
package authz

default allow = false

# Allow if user has required role
allow {
    input.method == "GET"
    input.path == ["api", "v1", "orders"]
    "orders:read" == input.user.permissions[_]
}

# Allow users to access only their own orders
allow {
    input.method == "GET"
    input.path == ["api", "v1", "orders", order_id]
    data.orders[order_id].user_id == input.user.sub
}

# Deny access outside business hours for non-admins
allow {
    input.user.role == "admin"
}
```

**Integration:**
- API Gateway: OPA plugin for Kong/Envoy
- Kubernetes: OPA Gatekeeper for admission control
- Service-level: OPA sidecar or library

---

### Principle of Least Privilege

**Implementation in microservices:**
- Each service has its own database credentials (not shared)
- Service accounts with minimal permissions
- Network policies restrict which services can communicate
- JWT scopes limit what a token can access
- Read replicas for read-only services

```yaml
# Kubernetes RBAC - service account with minimal permissions
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: order-service-role
rules:
  - apiGroups: [""]
    resources: ["configmaps"]
    resourceNames: ["order-service-config"]
    verbs: ["get"]
  - apiGroups: [""]
    resources: ["secrets"]
    resourceNames: ["order-service-db"]
    verbs: ["get"]
```

---

## Identity Propagation

### Edge-to-Service Token Propagation

**Pattern:**
```
External User (JWT) → API Gateway (validate, decode)
  → Internal services receive:
    Option A: Original JWT (forwarded)
    Option B: Internal JWT (re-signed, enriched)
    Option C: Trusted headers (X-User-Id, X-User-Roles)
```

**Tradeoffs:**
| Approach | Pros | Cons |
|----------|------|------|
| Forward JWT | Simple, standard | Services need public key, token may be too broad |
| Internal JWT | Scoped, enriched | Token exchange complexity |
| Trusted headers | Simplest for services | Must trust network (mTLS required) |

---

### Service Mesh Identity (SPIFFE/SPIRE)

**What it is:** SPIFFE (Secure Production Identity Framework For Everyone) provides cryptographic identities to workloads.

**SPIFFE ID format:**
```
spiffe://trust-domain/path
spiffe://production.example.com/ns/default/sa/order-service
```

**SPIRE:** The implementation of SPIFFE. Issues short-lived X.509 certificates (SVIDs) to workloads.

**Why it matters:** Platform-agnostic workload identity. Works across Kubernetes, VMs, bare metal. No secrets to manage.

---

### Short-Lived Certificates

**What it is:** Certificates with very short validity (hours, not years).

**Benefits:**
- Compromised cert is valid briefly
- No need for CRL/OCSP (revocation infrastructure)
- Automatic rotation eliminates manual renewal

**Implementation:** SPIRE issues 1-hour SVIDs, automatically rotated.

---

## Threat Modeling

### STRIDE Methodology for Microservices

| Threat | Description | Microservice Example | Mitigation |
|--------|-------------|---------------------|------------|
| **S**poofing | Impersonating another entity | Service impersonation | mTLS, SPIFFE |
| **T**ampering | Modifying data/code | Message modification in transit | Encryption, signatures |
| **R**epudiation | Denying actions | Service denies making a call | Audit logs, tracing |
| **I**nformation Disclosure | Exposing data | Logs containing PII | Masking, encryption |
| **D**enial of Service | Disrupting availability | Overwhelming a service | Rate limiting, bulkhead |
| **E**levation of Privilege | Gaining unauthorized access | Exploiting service account | Least privilege, RBAC |

**Process:**
1. Diagram the system (data flow diagrams)
2. Identify trust boundaries (gateway, namespace, service mesh)
3. Apply STRIDE to each component crossing a boundary
4. Prioritize threats (likelihood × impact)
5. Define mitigations and track implementation

---

### Attack Surface Analysis

**Microservice-specific attack surfaces:**
- API endpoints (each service exposes APIs)
- Message queues (poison messages)
- Shared databases (SQL injection via one service affects all)
- Container images (vulnerable base images)
- Service mesh control plane
- Secrets in environment variables
- Admin/debug endpoints accidentally exposed

**Reduction strategies:**
- Minimize exposed ports and endpoints
- Remove debug endpoints in production
- Use internal-only services (no external route)
- Regular API inventory audits

---

### Dependency Vulnerability Scanning

**Tools:**
| Tool | Scope | Integration |
|------|-------|-------------|
| Snyk | Code + dependencies + containers | CI/CD, IDE |
| Dependabot | Dependency updates | GitHub native |
| Trivy | Container images + IaC + filesystems | CI/CD, Kubernetes |
| Aqua Security | Full container lifecycle | Runtime + CI |
| Grype | Container image scanning | CI/CD |

**CI/CD Integration:**
```yaml
# GitHub Actions example
- name: Run Trivy vulnerability scanner
  uses: aquasecurity/trivy-action@master
  with:
    image-ref: 'myapp:${{ github.sha }}'
    format: 'sarif'
    severity: 'CRITICAL,HIGH'
    exit-code: '1'  # Fail build on critical/high
```

**Best practices:**
- Scan in CI (block merges with critical vulns)
- Scan in registry (detect newly discovered CVEs)
- Scan at runtime (admission controllers)
- Automate patching for non-breaking updates

---

### Runtime Security (Falco)

**What it is:** Runtime security tool that detects anomalous behavior in containers using system call monitoring.

**Detects:**
- Shell spawned in container
- Unexpected network connections
- File access in sensitive directories
- Privilege escalation attempts
- Cryptomining processes

**Falco rules:**
```yaml
- rule: Terminal shell in container
  desc: Detect shell spawned in container
  condition: >
    spawned_process and container and
    proc.name in (bash, sh, zsh)
  output: >
    Shell spawned in container
    (user=%user.name container=%container.name shell=%proc.name)
  priority: WARNING

- rule: Unexpected outbound connection
  desc: Detect container connecting to unexpected IP
  condition: >
    outbound and container and
    not (fd.sip in (allowed_outbound_ips))
  output: >
    Unexpected outbound connection
    (container=%container.name ip=%fd.sip)
  priority: CRITICAL
```

**Best practices:**
- Start in audit mode (log, don't block)
- Tune rules to reduce false positives
- Integrate with alerting (PagerDuty, Slack)
- Combine with network policies for enforcement
