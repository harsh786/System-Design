# Security and Cloud Architecture

_Split from `../world_class_pro_architect_master_roadmap.md`. The original source file is intentionally untouched._

---


## Security Foundation

- Authentication.
- Authorization.
- OAuth2.
- OIDC.
- JWT.
- Sessions.
- RBAC.
- ABAC.
- Zero trust.
- Secrets management.
- Encryption in transit.
- Encryption at rest.
- Key management.
- Network segmentation.
- API security.
- WAF.
- DDoS protection.
- Audit logging.
- Threat modeling.

## Cloud Architecture

- VPC design.
- Subnets.
- NAT gateway.
- Private endpoints.
- IAM.
- Managed databases.
- Object storage.
- Load balancers.
- CDN.
- Autoscaling.
- Multi-AZ design.
- Multi-region design.
- Disaster recovery.
- Cost controls.
- Tagging strategy.
- Cloud security posture.

## AWS Architect Roadmap Pointer

Use [40-aws-architecture-concepts-roadmap.md](40-aws-architecture-concepts-roadmap.md) for the dedicated AWS architecture track covering Route 53, CloudFront, VPC, ALB/NLB, API Gateway, EKS, ECS, Fargate, EC2 worker node strategy, RDS/Aurora, DynamoDB, ElastiCache, KMS, IAM, federation, messaging, observability, deployment, DR, and AWS cost governance.

## Supply-Chain Security

- SBOM.
- Image scanning.
- Dependency scanning.
- Signed images.
- Provenance.
- Policy as code.
- Admission controls.

---

---


## 16.11 Security Deep Dive

### OAuth 2.0 & OpenID Connect

```
┌──────────┐     ┌───────────────┐     ┌──────────────┐
│  Client  │────▶│ Authorization │────▶│   Resource   │
│   App    │◀────│    Server     │◀────│    Server    │
└──────────┘     └───────────────┘     └──────────────┘
      │                  │
      │  Authorization   │  Token
      │  Code Flow       │  Introspection
      ▼                  ▼
┌──────────┐     ┌───────────────┐
│  User    │     │  Token Store  │
│  Agent   │     │  (Redis/DB)   │
└──────────┘     └───────────────┘
```

#### OAuth 2.0 Grant Types

| Grant Type | Use Case | Security Level |
|---|---|---|
| Authorization Code + PKCE | SPAs, Mobile Apps | High |
| Client Credentials | Service-to-Service | High |
| Device Code | Smart TVs, CLI tools | Medium |
| Refresh Token | Long-lived sessions | Medium-High |
| ~~Implicit~~ (Deprecated) | Legacy SPAs | Low |
| ~~Resource Owner Password~~ (Deprecated) | Legacy migration | Low |

#### OIDC Token Types

| Token | Purpose | Format | Lifetime |
|---|---|---|---|
| ID Token | User identity assertion | JWT (signed) | 5-15 min |
| Access Token | API authorization | JWT or opaque | 5-60 min |
| Refresh Token | Obtain new access tokens | Opaque | 7-30 days |

#### PKCE (Proof Key for Code Exchange)

```
1. Client generates: code_verifier (random 43-128 chars)
2. Client computes: code_challenge = BASE64URL(SHA256(code_verifier))
3. Auth request includes: code_challenge + code_challenge_method=S256
4. Token request includes: code_verifier
5. Server verifies: SHA256(code_verifier) == stored code_challenge
```

### JWT Best Practices

#### JWT Structure & Validation

```json
// Header
{ "alg": "RS256", "typ": "JWT", "kid": "key-2026-01" }

// Payload
{
  "iss": "https://auth.example.com",
  "sub": "user-123",
  "aud": ["api.example.com"],
  "exp": 1737000000,
  "iat": 1736999100,
  "nbf": 1736999100,
  "jti": "unique-token-id",
  "scope": "read:users write:orders",
  "roles": ["admin"]
}

// Signature
RSASHA256(base64UrlEncode(header) + "." + base64UrlEncode(payload), privateKey)
```

#### JWT Security Checklist

| Practice | Rationale |
|---|---|
| Use RS256/ES256, never HS256 for public APIs | Asymmetric allows verification without secret |
| Validate `iss`, `aud`, `exp`, `nbf` | Prevents token misuse across services |
| Short expiry (5-15 min) | Limits window of compromise |
| Use `kid` for key rotation | Enables zero-downtime key changes |
| Store in HttpOnly cookies, not localStorage | Prevents XSS token theft |
| Implement token revocation list | Handles logout/compromise |
| Never store sensitive data in payload | JWTs are base64, not encrypted |
| Use `jti` claim for replay prevention | Detects reused tokens |

### Mutual TLS (mTLS)

```
┌────────┐                    ┌────────┐
│ Client │─────TLS Handshake──│ Server │
└────────┘                    └────────┘
    │                              │
    │ 1. ClientHello               │
    │─────────────────────────────▶│
    │                              │
    │ 2. ServerHello + ServerCert  │
    │◀─────────────────────────────│
    │                              │
    │ 3. CertificateRequest        │
    │◀─────────────────────────────│
    │                              │
    │ 4. ClientCert + Verify       │
    │─────────────────────────────▶│
    │                              │
    │ 5. Mutual Authentication ✓   │
    │◀────────────────────────────▶│
```

#### mTLS vs One-Way TLS

| Aspect | One-Way TLS | Mutual TLS |
|---|---|---|
| Server authenticated | Yes | Yes |
| Client authenticated | No (uses tokens) | Yes (certificate) |
| Use case | Public APIs | Service-to-service |
| Certificate management | Simple | Complex (both sides) |
| Performance overhead | Low | Medium (extra handshake) |
| Revocation | N/A for client | CRL/OCSP required |

### OWASP Top 10 (2021)

| # | Vulnerability | Mitigation |
|---|---|---|
| A01 | Broken Access Control | RBAC/ABAC, deny by default, server-side enforcement |
| A02 | Cryptographic Failures | TLS 1.3, AES-256-GCM, Argon2id for passwords |
| A03 | Injection | Parameterized queries, input validation, ORM usage |
| A04 | Insecure Design | Threat modeling, secure design patterns, abuse cases |
| A05 | Security Misconfiguration | Hardened defaults, automated scanning, IaC templates |
| A06 | Vulnerable Components | SCA scanning, dependency updates, SBOM |
| A07 | Auth Failures | MFA, credential stuffing protection, session management |
| A08 | Data Integrity Failures | Code signing, CI/CD pipeline security, SBOM verification |
| A09 | Logging & Monitoring | Centralized logging, alerting on auth failures, SIEM |
| A10 | SSRF | URL allowlists, network segmentation, disable redirects |

### API Security Patterns

#### Defense in Depth Layers

```
┌─────────────────────────────────────────────────────────┐
│                    WAF (Layer 7)                         │
│  DDoS protection, SQL injection, XSS filtering          │
├─────────────────────────────────────────────────────────┤
│                  API Gateway                            │
│  Rate limiting, authentication, request validation      │
├─────────────────────────────────────────────────────────┤
│                Service Mesh (mTLS)                       │
│  Service identity, encryption in transit                │
├─────────────────────────────────────────────────────────┤
│              Application Layer                           │
│  Authorization (RBAC/ABAC), input validation            │
├─────────────────────────────────────────────────────────┤
│                 Data Layer                               │
│  Encryption at rest, field-level encryption, masking    │
└─────────────────────────────────────────────────────────┘
```

#### API Security Headers

| Header | Value | Purpose |
|---|---|---|
| Strict-Transport-Security | max-age=31536000; includeSubDomains | Force HTTPS |
| Content-Security-Policy | default-src 'self' | Prevent XSS |
| X-Content-Type-Options | nosniff | Prevent MIME sniffing |
| X-Frame-Options | DENY | Prevent clickjacking |
| X-Request-Id | UUID | Request tracing |
| Cache-Control | no-store | Prevent caching sensitive data |

### Secrets Management

#### Architecture

```
┌──────────────┐     ┌─────────────────┐     ┌──────────────┐
│  Application │────▶│  Secrets Agent  │────▶│    Vault     │
│              │◀────│  (Sidecar/Lib)  │◀────│   (KMS/HSM)  │
└──────────────┘     └─────────────────┘     └──────────────┘
                            │                        │
                     Lease Renewal            Audit Log
                     Auto-rotation            Access Policy
```

#### Secrets Management Comparison

| Solution | Type | Key Features | Best For |
|---|---|---|---|
| HashiCorp Vault | Self-hosted/Cloud | Dynamic secrets, PKI, encryption | Multi-cloud |
| AWS Secrets Manager | Cloud | Auto-rotation, RDS integration | AWS-native |
| Azure Key Vault | Cloud | HSM-backed, managed identities | Azure-native |
| GCP Secret Manager | Cloud | IAM-based, versioning | GCP-native |
| Doppler | SaaS | Universal sync, CLI-friendly | Startups |

#### Secret Rotation Strategy

| Secret Type | Rotation Frequency | Method |
|---|---|---|
| Database passwords | 30 days | Dynamic credentials (Vault) |
| API keys | 90 days | Dual-key rotation |
| TLS certificates | 90 days (Let's Encrypt auto) | ACME protocol |
| Encryption keys | 365 days | Key versioning with re-wrap |
| Service account tokens | 24 hours | Short-lived + auto-refresh |

### Zero Trust Architecture

#### Principles

```
┌─────────────────────────────────────────────────────────┐
│                  Zero Trust Pillars                      │
├──────────┬──────────┬──────────┬──────────┬────────────┤
│ Identity │ Device   │ Network  │ App/     │ Data       │
│          │          │          │ Workload │            │
├──────────┼──────────┼──────────┼──────────┼────────────┤
│ MFA      │ Health   │ Micro-   │ Runtime  │ Classifi-  │
│ SSO      │ Posture  │ segment  │ Integrity│ cation     │
│ RBAC     │ MDM      │ mTLS     │ SBOM     │ Encryption │
│ JIT      │ Zero-day │ East-West│ Secrets  │ DLP        │
│ Access   │ Patching │ Controls │ Mgmt     │ Masking    │
└──────────┴──────────┴──────────┴──────────┴────────────┘
```

#### Zero Trust vs Perimeter Security

| Aspect | Perimeter Security | Zero Trust |
|---|---|---|
| Trust model | Trust inside, verify outside | Never trust, always verify |
| Network access | VPN = full access | Per-resource access |
| Lateral movement | Easy once inside | Blocked by micro-segmentation |
| Authentication | Once at perimeter | Continuous, per request |
| Data protection | Network boundary | Data-centric, everywhere |

### Security Interview Questions

1. **Design a secure API authentication system for a multi-tenant SaaS platform**
   - How do you isolate tenant data? Token structure? Key rotation?
   - How do you handle compromised credentials at scale?

2. **Implement OAuth 2.0 + PKCE flow for a mobile application**
   - Why not implicit flow? How do you handle token refresh?
   - What happens when refresh tokens are stolen?

3. **Design a secrets management system for 500+ microservices**
   - Dynamic vs static secrets? Rotation strategy? Emergency revocation?
   - How do you audit secret access? Handle leaked secrets?

4. **Explain how to prevent and detect SSRF in a cloud environment**
   - What is the metadata service attack? Network-level vs application-level mitigations?
   - How do you handle user-provided URLs safely?

5. **Design a zero-trust architecture for a hybrid cloud deployment**
   - How do you authenticate service-to-service calls? Handle legacy systems?
   - What is the identity provider architecture? Network segmentation strategy?

6. **How would you implement field-level encryption for PII data?**
   - Key management? Searchable encryption? Performance impact?
   - How do you handle key rotation with encrypted data at rest?

7. **Design a WAF rule set for an API that accepts user-generated content**
   - How do you balance security with false positives?
   - What are the bypass techniques and how do you mitigate them?

8. **Explain mTLS certificate lifecycle management for a Kubernetes cluster**
   - Certificate issuance? Rotation? Revocation? Trust chain?
   - What happens when the CA is compromised?

9. **Design a comprehensive API rate limiting and abuse prevention system**
   - Multiple dimensions (user, IP, endpoint)? Distributed coordination?
   - How do you handle legitimate traffic spikes vs attacks?

10. **How do you implement secure multi-tenancy in a shared database?**
    - Row-level security? Schema isolation? Connection pooling?
    - How do you prevent cross-tenant data leakage?

---

## 20.8 Security Depth for Architects

- Authentication: sessions, OAuth2, OIDC, device flows, token exchange.
- Authorization: RBAC, ABAC, ReBAC, policy engines.
- Identity propagation across microservices.
- mTLS and service identity.
- Secrets: rotation, dynamic secrets, envelope encryption.
- Data protection: classification, encryption, masking, tokenization.
- API security: rate limits, WAF, schema validation, replay protection.
- Threat modeling: STRIDE, attack trees, abuse cases.
- Supply chain: SBOM, SLSA concepts, signed artifacts, dependency scanning.
- Kubernetes security: admission policies, runtime security, image provenance, least privilege.
- Cloud security: IAM boundaries, private networking, logging, guardrails.
- Compliance: audit trails, data retention, deletion, residency, access reviews.

---

