# Caching, Scaling, Rate Limiting, and Resilience

_Split from `../world_class_pro_architect_master_roadmap.md`. The original source file is intentionally untouched._

---


## Redis Architecture & Internals

### Data Structures (Beyond Basics)
- **Strings**: binary-safe up to 512MB; used for counters (INCR atomic), serialized objects, bitmaps.
- **Hashes**: field-value maps; memory-efficient for objects with many fields (ziplist encoding <128 fields).
- **Lists**: doubly-linked or ziplist; LPUSH/RPOP for queues, LRANGE for pagination.
- **Sets**: unique unordered; SINTER for mutual friends, SUNION for feed aggregation.
- **Sorted Sets (ZSets)**: skip list + hash table; ZRANGEBYSCORE for leaderboards, rate limiting windows.
- **Streams**: append-only log with consumer groups; Kafka-like semantics for event sourcing.
- **HyperLogLog**: probabilistic cardinality counting (~0.81% error, 12KB per key regardless of cardinality).
- **Bitmaps**: BITCOUNT/BITOP for daily active users, feature flags across millions of users.
- **Geospatial**: GEOADD/GEORADIUS for proximity search (sorted set internally with geohash).

### Memory Management
- **Eviction policies**: noeviction, allkeys-lru, volatile-lru, allkeys-lfu, volatile-lfu, allkeys-random, volatile-ttl.
- **LRU approximation**: samples 5 keys (configurable), evicts best candidate. Not true LRU.
- **LFU (Least Frequently Used)**: counter with logarithmic decay; better for access-pattern caches.
- **Memory fragmentation**: `INFO memory` → `mem_fragmentation_ratio`; use `MEMORY PURGE` or restart.
- **Key expiration**: passive (check on access) + active (periodic sampling of keys with TTL).
- **Lazy freeing**: `UNLINK` instead of `DEL` for large keys (async deletion in background thread).

### Cluster Architecture
- **Hash slots**: 16384 slots distributed across masters; CRC16(key) % 16384 determines slot.
- **Resharding**: `MIGRATE` moves slots between nodes; during migration, ASK/MOVED redirects.
- **Gossip protocol**: nodes exchange cluster state via ping/pong every 1 second.
- **Failover**: replica promotes when master is PFAIL (suspected fail) → FAIL (confirmed by majority).
- **Multi-key operations**: only work when all keys map to same slot; use hash tags `{user:1}:profile`.

### Redis Sentinel vs Cluster

| Feature | Sentinel | Cluster |
|---------|----------|---------|
| Sharding | No (single master) | Yes (16384 hash slots) |
| Max data | Single node RAM | Sum of all node RAM |
| Failover | Automatic (consensus) | Automatic (gossip) |
| Multi-key ops | All keys accessible | Same-slot only |
| Complexity | Low | High |
| Use case | HA for <50GB | Scale beyond single node |

### Advanced Patterns
- **Lua scripting**: atomic multi-command operations; EVAL/EVALSHA; used for rate limiters, locks.
- **Distributed lock (Redlock)**: acquire lock on N/2+1 instances; controversial (see Martin Kleppmann critique).
- **Pub/Sub**: fire-and-forget messaging; no persistence, no replay, no acknowledgment.
- **Streams with Consumer Groups**: persistent, acknowledged, replayable message processing.
- **Pipeline**: batch multiple commands in one round-trip; 5-10x throughput improvement.
- **Redis Functions**: server-side stored procedures replacing Lua EVAL (Redis 7+).

### Caching Strategies

| Strategy | Description | Consistency | Use Case |
|----------|-------------|-------------|----------|
| Cache-Aside | App reads/writes cache explicitly | Eventual | General purpose |
| Read-Through | Cache loads from DB on miss | Eventual | Read-heavy, simple |
| Write-Through | Write to cache and DB synchronously | Strong | Read-after-write needed |
| Write-Behind | Write to cache, async flush to DB | Eventual | Write-heavy, can tolerate lag |
| Refresh-Ahead | Proactively refresh before expiry | Eventual | Predictable access patterns |

### Cache Invalidation Patterns
- **TTL-based**: simple but stale data during TTL window.
- **Event-driven**: DB change events (CDC) trigger cache invalidation.
- **Version stamping**: include version in cache key; increment on change.
- **Tag-based**: associate keys with tags; invalidate all keys with a tag.

### Redis vs Memcached

| Feature | Redis | Memcached |
|---------|-------|-----------|
| Data structures | Rich (strings, lists, sets, hashes, streams) | Strings only |
| Persistence | RDB snapshots + AOF | None |
| Replication | Built-in master-replica | None (client-side) |
| Clustering | Redis Cluster (16384 slots) | Client-side consistent hashing |
| Scripting | Lua / Redis Functions | None |
| Memory efficiency | Higher overhead per key | Slab allocator, efficient for uniform sizes |
| Max value size | 512MB | 1MB default |
| Multithreading | I/O threads (Redis 6+), single command thread | Fully multithreaded |
| Use case | Complex data, persistence needed | Simple KV, session store, uniform objects |

### Interview Questions
1. Explain Redis cluster hash slot migration. What happens to requests during resharding?
2. Design a distributed rate limiter using Redis sorted sets. Handle the race condition.
3. Why is Redlock controversial? Explain the Kleppmann vs Antirez debate on distributed locks.
4. How does Redis achieve persistence with RDB and AOF? What are the tradeoffs of each?
5. Design a real-time leaderboard for 50M users with Redis. How do you handle ties?
6. Explain Redis memory fragmentation. How do you detect and fix it in production?
7. Compare Redis Streams vs Kafka for event sourcing. When would you choose each?
8. How do you handle cache stampede (thundering herd) when a popular key expires?
9. Design a session store with Redis. How do you handle Redis failures without losing sessions?
10. Explain the Redis single-threaded model. How does it achieve 100K+ ops/sec?
11. How do you implement cache warming for a new service deployment?
12. Design a pub/sub notification system with Redis. How do you handle subscriber failures?

---

# 16.7 Time-Series Databases

## TimescaleDB

### Architecture
- Extension on PostgreSQL: full SQL support, joins with relational tables, existing tooling.
- **Hypertables**: automatic partitioning by time (and optionally space/device_id).
- **Chunks**: each time partition is a separate PostgreSQL table; transparent to queries.
- Typically partition by 1 day or 1 week depending on ingestion rate.

### Key Features
- **Continuous Aggregates**: materialized views that auto-update as new data arrives; query pre-computed rollups.
- **Compression**: columnar compression on older chunks (90-95% compression ratio typical).
- **Data retention policies**: automatic DROP of chunks older than threshold (e.g., raw data 30 days, aggregates 1 year).
- **Real-time aggregates**: combine materialized aggregate with recent unmaterialized data.
- **Distributed hypertables**: shard across multiple PostgreSQL nodes for horizontal scale.

### Query Patterns
```sql
-- Time-bucket aggregation (TimescaleDB-specific)
SELECT time_bucket('5 minutes', time) AS bucket,
       device_id,
       AVG(temperature) AS avg_temp,
       MAX(temperature) AS max_temp
FROM sensor_data
WHERE time > NOW() - INTERVAL '24 hours'
GROUP BY bucket, device_id
ORDER BY bucket DESC;

-- Continuous aggregate definition
CREATE MATERIALIZED VIEW hourly_metrics
WITH (timescaledb.continuous) AS
SELECT time_bucket('1 hour', time) AS hour,
       device_id,
       AVG(value), MIN(value), MAX(value), COUNT(*)
FROM raw_metrics
GROUP BY hour, device_id;
```

### TimescaleDB vs InfluxDB vs Prometheus

| Feature | TimescaleDB | InfluxDB | Prometheus |
|---------|-------------|----------|------------|
| Query language | SQL | InfluxQL / Flux | PromQL |
| Data model | Relational (wide table) | Tags + fields | Labels + metrics |
| Joins | Full SQL joins | Limited | None |
| Cardinality | Handles high cardinality well | Struggles at high cardinality | Struggles at high cardinality |
| Compression | 90-95% columnar | 80-90% | ~1.3 bytes/sample |
| Retention | Policy-based chunk drop | Retention policies | Block-based compaction |
| Scale | Distributed hypertables | Clustered (enterprise) | Federation / Thanos |
| Best for | IoT, analytics with joins | Metrics, events | Infrastructure monitoring |

### Interview Questions
1. How does TimescaleDB's hypertable partitioning differ from standard PostgreSQL partitioning?
2. Design a sensor data pipeline ingesting 1M data points/second. Which time-series DB and why?
3. Explain continuous aggregates. How do they handle late-arriving data?
4. How do you handle high-cardinality dimensions in time-series databases?
5. Compare chunk-based retention (TimescaleDB) vs block compaction (Prometheus). Tradeoffs?
6. Design a multi-tenant metrics platform. How do you isolate tenant data and queries?
7. How does columnar compression work in TimescaleDB? Why is it effective for time-series?
8. When would you use TimescaleDB over InfluxDB? Give three architectural reasons.


---


## 16.10 Scaling Patterns Deep Dive

### Horizontal vs Vertical Scaling

| Aspect | Horizontal (Scale Out) | Vertical (Scale Up) |
|--------|----------------------|---------------------|
| Method | Add more machines | Add more resources to one machine |
| Limit | Theoretically unlimited | Hardware ceiling |
| Complexity | High (distributed systems) | Low (single machine) |
| Downtime | Zero (add/remove nodes) | Usually required for hardware changes |
| Cost Curve | Linear | Exponential at high end |
| Data Consistency | Requires coordination | Naturally consistent |
| Failure Impact | Partial degradation | Total failure |
| Best For | Stateless services, web tier | Databases, single-threaded workloads |

### Database Scaling Patterns

**Sharding Strategies:**
| Strategy | How It Works | Pros | Cons |
|----------|--------------|------|------|
| Range-based | Shard by value range (A-M, N-Z) | Simple, range queries work | Hotspots if data is skewed |
| Hash-based | Hash key to determine shard | Even distribution | Range queries span all shards |
| Geographic | Shard by region/location | Data locality, compliance | Cross-region queries expensive |
| Directory-based | Lookup table maps key→shard | Flexible rebalancing | Lookup table is SPOF |
| Consistent Hashing | Hash ring with virtual nodes | Minimal redistribution on scale | More complex implementation |

**Read Scaling Architecture:**
```
┌──────────┐     ┌──────────┐
│  Writes  │────▶│  Primary │
└──────────┘     └────┬─────┘
                      │ Replication
              ┌───────┼───────┐
              ▼       ▼       ▼
         ┌────────┐┌────────┐┌────────┐
         │Replica1││Replica2││Replica3│
         └────┬───┘└───┬────┘└───┬────┘
              └────────┼─────────┘
                       ▼
              ┌──────────────┐
              │    Reads     │
              └──────────────┘
```

**Replication Types:**
| Type | Consistency | Latency | Use Case |
|------|-------------|---------|----------|
| Synchronous | Strong | Higher write latency | Financial transactions |
| Asynchronous | Eventual | Lower write latency | Read-heavy workloads |
| Semi-synchronous | Middle ground | Moderate | Balance of both |
| Multi-master | Conflict resolution needed | Varies | Multi-region writes |

### CQRS (Command Query Responsibility Segregation)

```
┌───────────────────────────────────────────────────┐
│                   Commands                         │
│  ┌──────────┐    ┌───────────┐    ┌───────────┐  │
│  │  Client  │───▶│  Command  │───▶│  Write    │  │
│  │          │    │  Handler  │    │  Model    │  │
│  └──────────┘    └───────────┘    └─────┬─────┘  │
└─────────────────────────────────────────┼─────────┘
                                          │ Events
                                          ▼
                                   ┌─────────────┐
                                   │ Event Store │
                                   └──────┬──────┘
                                          │ Projection
                                          ▼
┌───────────────────────────────────────────────────┐
│                    Queries                          │
│  ┌──────────┐    ┌───────────┐    ┌───────────┐  │
│  │  Client  │◀───│  Query    │◀───│  Read     │  │
│  │          │    │  Handler  │    │  Model    │  │
│  └──────────┘    └───────────┘    └───────────┘  │
└───────────────────────────────────────────────────┘
```

**When to Use CQRS:**
| Use CQRS When | Avoid CQRS When |
|---------------|-----------------|
| Read/write patterns differ significantly | Simple CRUD application |
| Need different read/write models | Small team, limited complexity budget |
| High read:write ratio | Strong consistency required everywhere |
| Complex domain with event sourcing | Data model is simple and flat |
| Multiple read representations needed | Tight coupling between read/write is acceptable |

### Auto-Scaling Patterns

**Scaling Signals:**
| Signal | Metric | Threshold Example | Lag |
|--------|--------|-------------------|-----|
| CPU | Utilization % | Scale up > 70%, down < 30% | 2-3 min |
| Memory | Usage % | Scale up > 80% | 1-2 min |
| Request Rate | RPS per instance | Scale up > 1000 RPS/instance | 30s |
| Queue Depth | Messages pending | Scale up > 100 messages/worker | 10s |
| Response Time | p95 latency | Scale up > 500ms | 1-2 min |
| Custom | Business metric | Scale based on active users | Varies |

**Back-Pressure Mechanisms:**
| Mechanism | Implementation | Effect |
|-----------|---------------|--------|
| Request Queuing | Bounded queue with rejection | Producers slow down when queue full |
| Rate Limiting | Token bucket at ingress | Shed excess load early |
| Load Shedding | Drop low-priority requests | Protect critical paths |
| Circuit Breaker | Stop calling failing downstream | Prevent cascade |
| Adaptive Concurrency | Dynamic limit based on latency | Self-tuning capacity |
| Backoff Signals | HTTP 429 + Retry-After | Client-side cooperation |

### Connection Pooling

```
┌──────────────────────────────────────────┐
│            Application Server             │
│  ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐       │
│  │Req 1│ │Req 2│ │Req 3│ │Req N│       │
│  └──┬──┘ └──┬──┘ └──┬──┘ └──┬──┘       │
│     └────────┼───────┼───────┘           │
│              ▼                            │
│     ┌─────────────────┐                  │
│     │ Connection Pool │                  │
│     │ (min:5, max:20) │                  │
│     └────────┬────────┘                  │
└──────────────┼───────────────────────────┘
               ▼
    ┌─────────────────────┐
    │    Database Server   │
    │  max_connections=100 │
    └─────────────────────┘
```

**Pool Sizing Formula:**
```
Pool Size = (Core Count * 2) + Effective Spindle Count
Example: 4 cores, SSD → (4 * 2) + 1 = 9 connections
```

### Scaling Interview Questions

1. Design an auto-scaling system that handles traffic spikes 10x normal within 60 seconds.
2. How would you implement database sharding for a social media platform with 500M users?
3. Explain the CAP theorem trade-offs when scaling a distributed database. Give real examples.
4. Design a CQRS system for an e-commerce platform. What consistency guarantees would you provide?
5. How do you handle connection pool exhaustion under load? What are the symptoms and fixes?
6. Compare horizontal scaling strategies for stateful vs stateless services.
7. Design a back-pressure system that gracefully degrades under 10x expected load.
8. How would you migrate from a monolithic database to a sharded architecture with zero downtime?
9. Explain read replica lag and its impact on user experience. How would you mitigate it?
10. Design a multi-region active-active database architecture. How do you handle conflicts?
11. What's the difference between load shedding and rate limiting? When would you use each?
12. How would you scale a WebSocket server to handle 10M concurrent connections?

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

## 16.12 Rate Limiting & Resilience Patterns

### Rate Limiting Algorithms

#### Token Bucket

```
┌─────────────────────────────────────────┐
│            Token Bucket                  │
│                                         │
│  Capacity: 10 tokens                    │
│  Refill Rate: 2 tokens/second           │
│                                         │
│  ┌─────────────────────────────────┐    │
│  │ [●][●][●][●][●][●][ ][ ][ ][ ] │    │
│  │  6 tokens available              │    │
│  └─────────────────────────────────┘    │
│                                         │
│  Request arrives:                       │
│  - Token available → consume, allow     │
│  - No token → reject (429)             │
│                                         │
│  Allows bursts up to bucket capacity    │
└─────────────────────────────────────────┘
```

**Characteristics:**
- Allows burst traffic up to bucket size
- Smooth long-term rate enforcement
- Memory: O(1) per key (counter + timestamp)
- Used by: AWS API Gateway, Stripe

#### Leaky Bucket

```
┌─────────────────────────────────────────┐
│            Leaky Bucket                  │
│                                         │
│  Queue Size: 10 requests                │
│  Drain Rate: 2 requests/second          │
│                                         │
│  ┌─────────────────────────────────┐    │
│  │ [R][R][R][R][R][ ][ ][ ][ ][ ] │    │
│  │  5 requests queued               │    │
│  └──────────────────────────┬──────┘    │
│                             │ drain     │
│                             ▼           │
│                     Process at fixed    │
│                     rate (2 req/s)      │
│                                         │
│  Queue full → reject (429)              │
│  Enforces strict output rate            │
└─────────────────────────────────────────┘
```

**Characteristics:**
- Strict constant output rate (no bursts)
- Smooths traffic shape completely
- Memory: O(1) per key (queue pointer + timestamp)
- Used by: Nginx (`limit_req`), network traffic shaping

#### Sliding Window Log

```
┌─────────────────────────────────────────┐
│        Sliding Window Log               │
│                                         │
│  Window: 60 seconds                     │
│  Limit: 100 requests                    │
│                                         │
│  Timestamps: [t1, t2, t3, ..., t87]    │
│                                         │
│  On request at time T:                  │
│  1. Remove entries where ts < T - 60s   │
│  2. Count remaining entries             │
│  3. If count < 100 → add T, allow      │
│  4. If count >= 100 → reject (429)     │
│                                         │
│  Memory: O(n) per key (all timestamps)  │
│  Most accurate but memory intensive     │
└─────────────────────────────────────────┘
```

#### Sliding Window Counter

```
┌─────────────────────────────────────────┐
│      Sliding Window Counter             │
│                                         │
│  Window: 60 seconds, Limit: 100        │
│  Current window: 40 requests            │
│  Previous window: 80 requests           │
│  Position in current window: 25%        │
│                                         │
│  Weighted count =                       │
│    current + previous × (1 - position)  │
│    40 + 80 × 0.75 = 100               │
│                                         │
│  100 >= limit → reject (429)           │
│                                         │
│  Memory: O(1) per key (2 counters)     │
│  Approximate but memory efficient       │
└─────────────────────────────────────────┘
```

#### Fixed Window Counter

```
┌─────────────────────────────────────────┐
│        Fixed Window Counter             │
│                                         │
│  Window: 60 seconds, Limit: 100        │
│                                         │
│  ┌──────────┐  ┌──────────┐            │
│  │ Window 1 │  │ Window 2 │            │
│  │ 0:00-1:00│  │ 1:00-2:00│            │
│  │ Count: 95│  │ Count: 23│            │
│  └──────────┘  └──────────┘            │
│                                         │
│  Problem: boundary burst                │
│  50 req at 0:59 + 50 req at 1:01       │
│  = 100 req in 2 seconds (passes!)      │
│                                         │
│  Memory: O(1) per key (counter)         │
│  Simple but has edge case at boundary   │
└─────────────────────────────────────────┘
```

#### Algorithm Comparison

| Algorithm | Burst Handling | Memory | Accuracy | Complexity |
|---|---|---|---|---|
| Token Bucket | Allows controlled bursts | O(1) | High | Low |
| Leaky Bucket | No bursts (strict rate) | O(1) | High | Low |
| Fixed Window | Boundary burst problem | O(1) | Low | Very Low |
| Sliding Window Log | No bursts | O(n) | Exact | Medium |
| Sliding Window Counter | Minimal boundary issue | O(1) | Approximate | Low |

### Distributed Rate Limiting

#### Architecture

```
┌──────────┐     ┌──────────┐     ┌──────────┐
│ Server 1 │     │ Server 2 │     │ Server 3 │
└────┬─────┘     └────┬─────┘     └────┬─────┘
     │                │                │
     └────────────────┼────────────────┘
                      │
              ┌───────▼───────┐
              │  Redis Cluster │
              │               │
              │  MULTI        │
              │  INCR key     │
              │  EXPIRE key   │
              │  EXEC         │
              └───────────────┘
```

#### Redis Lua Script for Sliding Window

```lua
-- Sliding window rate limiter in Redis
local key = KEYS[1]
local window = tonumber(ARGV[1])  -- window size in ms
local limit = tonumber(ARGV[2])   -- max requests
local now = tonumber(ARGV[3])     -- current timestamp ms

-- Remove expired entries
redis.call('ZREMRANGEBYSCORE', key, 0, now - window)

-- Count current entries
local count = redis.call('ZCARD', key)

if count < limit then
    -- Allow: add current timestamp
    redis.call('ZADD', key, now, now .. '-' .. math.random())
    redis.call('PEXPIRE', key, window)
    return {1, limit - count - 1}  -- allowed, remaining
else
    return {0, 0}  -- denied, remaining
end
```

#### Multi-Dimensional Rate Limiting

| Dimension | Limit | Purpose |
|---|---|---|
| Per User | 1000 req/min | Fair usage per account |
| Per IP | 100 req/min | Prevent anonymous abuse |
| Per Endpoint | 50 req/min | Protect expensive operations |
| Per Tenant | 10000 req/min | SaaS plan enforcement |
| Global | 100000 req/min | System protection |

### Circuit Breaker Pattern

#### State Machine

```
                 failure threshold
                    exceeded
    ┌──────────┐ ──────────────▶ ┌──────────┐
    │  CLOSED  │                 │   OPEN   │
    │          │ ◀────────────── │          │
    └──────────┘   reset after   └──────────┘
         ▲         success            │
         │                            │ timeout
         │                            │ expires
         │    ┌───────────────┐       │
         └────│  HALF-OPEN    │◀──────┘
   success    │               │
              │ (allow 1 req) │
              └───────────────┘
                    │
                    │ failure
                    ▼
              Back to OPEN
```

#### Circuit Breaker Configuration

| Parameter | Typical Value | Purpose |
|---|---|---|
| Failure Threshold | 5 failures in 60s | When to open circuit |
| Success Threshold | 3 consecutive | When to close from half-open |
| Timeout | 30-60 seconds | How long to stay open |
| Half-Open Max | 1-3 requests | Probe requests in half-open |
| Failure Types | 5xx, timeouts, connection errors | What counts as failure |
| Excluded | 4xx (client errors) | What does NOT count |

#### Circuit Breaker vs Retry

| Aspect | Retry | Circuit Breaker |
|---|---|---|
| Purpose | Handle transient failures | Prevent cascade failures |
| Behavior | Retry N times with backoff | Fail fast when service is down |
| Best for | Occasional failures | Sustained outages |
| Risk | Amplifies load on failing service | May reject during recovery |
| Combination | Retry inside circuit breaker | Open circuit after retries exhaust |

### Bulkhead Pattern

```
┌─────────────────────────────────────────────────────────┐
│                   Service Instance                       │
│                                                         │
│  ┌─────────────────┐  ┌─────────────────┐             │
│  │  Payment Pool   │  │  Catalog Pool   │             │
│  │  Max: 20 threads│  │  Max: 50 threads│             │
│  │  Queue: 10      │  │  Queue: 30      │             │
│  │                 │  │                 │             │
│  │  [████████░░]   │  │  [██████░░░░]   │             │
│  │  16/20 active   │  │  30/50 active   │             │
│  └─────────────────┘  └─────────────────┘             │
│                                                         │
│  Payment failure does NOT affect Catalog availability   │
└─────────────────────────────────────────────────────────┘
```

#### Bulkhead Types

| Type | Isolation | Use Case | Implementation |
|---|---|---|---|
| Thread Pool | Thread-level | Blocking I/O calls | Separate thread pools per dependency |
| Semaphore | Concurrency limit | Async/non-blocking | Counting semaphore per dependency |
| Process | Process-level | Critical workloads | Separate container/pod per dependency |
| Connection Pool | Connection-level | Database/HTTP | Dedicated pools per downstream |

### Resilience Pattern Combinations

```
┌─────────────────────────────────────────────────────────┐
│                Request Flow                             │
│                                                         │
│  Client                                                 │
│    │                                                    │
│    ▼                                                    │
│  [Timeout] ─── 5s max wait                             │
│    │                                                    │
│    ▼                                                    │
│  [Bulkhead] ─── max 20 concurrent                      │
│    │                                                    │
│    ▼                                                    │
│  [Circuit Breaker] ─── fail fast if open               │
│    │                                                    │
│    ▼                                                    │
│  [Retry] ─── 3 attempts, exponential backoff           │
│    │                                                    │
│    ▼                                                    │
│  [Rate Limiter] ─── respect downstream limits          │
│    │                                                    │
│    ▼                                                    │
│  Downstream Service                                     │
└─────────────────────────────────────────────────────────┘

Order matters: Timeout > Bulkhead > Circuit Breaker > Retry > Rate Limit
```

### Back-Pressure Mechanisms

| Mechanism | Implementation | When to Use |
|---|---|---|
| Load Shedding | Return 503 when queue > threshold | Protect from overload |
| Throttling | Delay responses progressively | Gradual degradation |
| Admission Control | Reject low-priority requests | Under resource pressure |
| Queue Limits | Bounded queues with rejection | Prevent memory exhaustion |
| Flow Control | TCP/gRPC window-based | Stream processing |
| Priority Queues | Process critical requests first | Mixed-priority traffic |

### Graceful Degradation Strategies

| Strategy | Description | Example |
|---|---|---|
| Feature Flags | Disable non-critical features | Turn off recommendations during peak |
| Fallback Data | Return cached/stale data | Show cached search results |
| Reduced Quality | Lower resolution/precision | Smaller images, approximate counts |
| Queue Deferral | Defer non-urgent work | Batch emails instead of real-time |
| Static Content | Serve pre-rendered pages | Static product pages during outage |
| Read-Only Mode | Disable writes | Allow browsing, block purchases |

### Chaos Engineering

#### Principles

| Principle | Description |
|---|---|
| Build Hypothesis | Define steady-state behavior and expected impact |
| Vary Real-World Events | Inject failures that could actually happen |
| Run in Production | Staging cannot replicate production complexity |
| Minimize Blast Radius | Start small, automated rollback, kill switch |
| Automate Experiments | Run continuously as part of CI/CD |

#### Chaos Tools

| Tool | Focus | Key Features |
|---|---|---|
| Chaos Monkey | Instance failure | Random instance termination |
| Litmus | Kubernetes | CRD-based, GitOps native |
| Gremlin | Enterprise | Attack catalog, gamedays, safety |
| Toxiproxy | Network | Latency, bandwidth, connection issues |
| Chaos Mesh | Kubernetes | Pod, network, I/O, time chaos |

### Rate Limiting & Resilience Interview Questions

1. **Design a distributed rate limiter for a global API serving 1M req/s**
   - How do you handle cross-region coordination?
   - What happens when Redis is unavailable? Local fallback?

2. **Implement a circuit breaker for a payment gateway integration**
   - What metrics trigger the open state? How do you handle partial failures?
   - How do you test the circuit breaker in production?

3. **Design a multi-tier rate limiting system (user → tenant → global)**
   - How do you handle limit inheritance? Priority overrides?
   - What is the race condition risk and how do you solve it?

4. **Explain how you would implement back-pressure in an event-driven system**
   - How does Kafka consumer lag signal back-pressure?
   - What is the relationship between partition count and back-pressure?

5. **Design a load shedding strategy for a system with mixed-priority traffic**
   - How do you classify requests? What signals determine shed priority?
   - How do you prevent priority inversion?

6. **Implement graceful degradation for an e-commerce checkout during Black Friday**
   - What features can be safely degraded? In what order?
   - How do you monitor degradation and auto-recover?

7. **Compare token bucket vs sliding window for API rate limiting**
   - When would you choose one over the other?
   - How does each handle burst traffic differently?

8. **Design a chaos engineering program for a microservices platform**
   - How do you start? What are the first experiments?
   - How do you prevent chaos experiments from causing real outages?

9. **Implement retry with exponential backoff and jitter for a distributed system**
   - Why is jitter important? Full vs decorrelated jitter?
   - How do you prevent retry storms across multiple clients?

10. **Design a bulkhead pattern for a service calling 10 downstream dependencies**
    - How do you size each bulkhead? What signals drive resizing?
    - How do you handle when multiple bulkheads are saturated simultaneously?

11. **How would you implement adaptive rate limiting that adjusts based on system load?**
    - What metrics drive the adaptation? CPU, queue depth, latency?
    - How do you prevent oscillation in the adaptive algorithm?

12. **Design an end-to-end resilience testing strategy for pre-production validation**
    - Load testing vs chaos testing vs fault injection?
    - How do you establish performance baselines and detect regressions?



