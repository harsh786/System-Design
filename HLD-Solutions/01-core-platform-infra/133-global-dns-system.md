# Global DNS System (Route53 / Cloudflare DNS)

## 1. Functional Requirements

| # | Requirement | Details |
|---|-------------|---------|
| FR-1 | Authoritative DNS Serving | Respond authoritatively for hosted zones with all standard record types (A, AAAA, CNAME, MX, TXT, SRV, NS, SOA, CAA) |
| FR-2 | Recursive Resolver with Caching | Full recursive resolution with aggressive caching respecting TTLs |
| FR-3 | Zone Management CRUD | Create/update/delete zones and resource records via API and console |
| FR-4 | DNSSEC Signing & Validation | Automatic zone signing (KSK/ZSK), RRSIG generation, NSEC/NSEC3, DS record management |
| FR-5 | Anycast Routing | Same IP announced from 200+ global PoPs via BGP anycast |
| FR-6 | Health-Check Based Failover | Active health checks with automatic DNS failover on failure |
| FR-7 | Routing Policies | Weighted, latency-based, geolocation, failover, multivalue answer |
| FR-8 | DNS over HTTPS (DoH) / DNS over TLS (DoT) | RFC 8484 DoH, RFC 7858 DoT for privacy |
| FR-9 | DDoS Protection | Rate limiting, response rate limiting (RRL), anycast absorption |
| FR-10 | Zone Transfer | AXFR/IXFR with NOTIFY for secondary nameservers |

## 2. Non-Functional Requirements

| Requirement | Target |
|-------------|--------|
| Availability | 99.9999% (six nines) |
| Query Latency | < 5ms from nearest PoP (cache hit) |
| Query Throughput | 100M+ queries/sec globally |
| Zone Scale | Millions of zones, billions of records |
| Propagation Time | < 60 seconds zone changes globally |
| DNSSEC Validation | < 1ms overhead |
| PoP Count | 200+ global points of presence |
| DDoS Absorption | 10+ Tbps |

## 3. Capacity Estimation

```
Query Volume:
  - 100M queries/sec peak globally
  - Per PoP (200 PoPs): 500K queries/sec average
  - Cache hit ratio: 85% → 15M queries/sec to authoritative
  - Average query size: 50 bytes, response: 200 bytes
  - Bandwidth: 100M × 250 bytes = 25 GB/sec = 200 Gbps aggregate

Zone Data:
  - 5M zones, average 50 records each = 250M resource records
  - Average record size: 200 bytes → 50 GB total zone data
  - With DNSSEC (RRSIG, NSEC3): 3x → 150 GB
  - Per PoP: full copy = 150 GB (fits in RAM)

Health Checks:
  - 10M configured health checks
  - Check interval: 10 seconds
  - Health check traffic: 1M checks/sec distributed across checkers

Storage:
  - Zone data: 150 GB per PoP × 200 PoPs (served from RAM)
  - Control plane DB: 500 GB (zone configs, policies, audit logs)
  - Query logs: 100M/sec × 200 bytes × 86400 = 1.7 PB/day (sampled to 1%)
```

## 4. Data Modeling

### 4.1 Zones and Records

```sql
CREATE TABLE zones (
    zone_id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    zone_name           VARCHAR(255) NOT NULL UNIQUE,  -- "example.com."
    account_id          UUID NOT NULL,
    status              VARCHAR(20) NOT NULL DEFAULT 'active',
    dnssec_enabled      BOOLEAN DEFAULT FALSE,
    dnssec_status       VARCHAR(20),  -- 'signing', 'active', 'disabled'
    serial_number       BIGINT NOT NULL DEFAULT 1,
    refresh_seconds     INTEGER DEFAULT 7200,
    retry_seconds       INTEGER DEFAULT 900,
    expire_seconds      INTEGER DEFAULT 1209600,
    min_ttl             INTEGER DEFAULT 300,
    ns_records          JSONB NOT NULL,  -- assigned nameservers
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_zones_name ON zones(zone_name);
CREATE INDEX idx_zones_account ON zones(account_id);

CREATE TABLE resource_records (
    record_id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    zone_id             UUID NOT NULL REFERENCES zones(zone_id),
    name                VARCHAR(255) NOT NULL,  -- "www.example.com."
    record_type         VARCHAR(10) NOT NULL,   -- 'A', 'AAAA', 'CNAME', 'MX', etc.
    ttl                 INTEGER NOT NULL DEFAULT 300,
    rdata               JSONB NOT NULL,         -- record-type-specific data
    -- For routing policies:
    routing_policy      VARCHAR(20) DEFAULT 'simple',  -- 'simple', 'weighted', 'latency', 'geo', 'failover', 'multivalue'
    routing_config      JSONB,
    health_check_id     UUID,
    set_identifier      VARCHAR(128),  -- for multi-value routing
    weight              INTEGER,       -- for weighted routing
    region              VARCHAR(50),   -- for latency/geo routing
    failover_role       VARCHAR(10),   -- 'primary' or 'secondary'
    enabled             BOOLEAN DEFAULT TRUE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_records_zone ON resource_records(zone_id);
CREATE INDEX idx_records_lookup ON resource_records(zone_id, name, record_type);
CREATE INDEX idx_records_name_type ON resource_records(name, record_type) WHERE enabled = TRUE;
CREATE INDEX idx_records_health ON resource_records(health_check_id) WHERE health_check_id IS NOT NULL;
```

### 4.2 Health Checks

```sql
CREATE TABLE health_checks (
    health_check_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id          UUID NOT NULL,
    name                VARCHAR(200),
    protocol            VARCHAR(10) NOT NULL,  -- 'HTTP', 'HTTPS', 'TCP'
    endpoint            VARCHAR(255) NOT NULL,
    port                INTEGER NOT NULL DEFAULT 443,
    path                VARCHAR(500),          -- for HTTP/HTTPS
    search_string       VARCHAR(255),          -- response body must contain
    check_interval_sec  INTEGER NOT NULL DEFAULT 30,
    failure_threshold   INTEGER NOT NULL DEFAULT 3,
    success_threshold   INTEGER NOT NULL DEFAULT 2,
    timeout_sec         INTEGER NOT NULL DEFAULT 5,
    regions             JSONB NOT NULL,        -- checker regions
    invert_healthcheck  BOOLEAN DEFAULT FALSE,
    current_status      VARCHAR(10) DEFAULT 'unknown',  -- 'healthy', 'unhealthy', 'unknown'
    last_check_at       TIMESTAMPTZ,
    status_changed_at   TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_health_account ON health_checks(account_id);
CREATE INDEX idx_health_status ON health_checks(current_status);
CREATE INDEX idx_health_next_check ON health_checks(last_check_at);
```

### 4.3 DNSSEC Keys

```sql
CREATE TABLE dnssec_keys (
    key_id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    zone_id             UUID NOT NULL REFERENCES zones(zone_id),
    key_type            VARCHAR(5) NOT NULL,   -- 'KSK' or 'ZSK'
    algorithm           VARCHAR(20) NOT NULL,  -- 'ECDSAP256SHA256', 'RSASHA256'
    key_tag             INTEGER NOT NULL,
    public_key          TEXT NOT NULL,
    private_key_ref     TEXT NOT NULL,         -- HSM reference
    status              VARCHAR(20) NOT NULL,  -- 'active', 'published', 'retired', 'revoked'
    activate_at         TIMESTAMPTZ,
    deactivate_at       TIMESTAMPTZ,
    ds_record           TEXT,                  -- for KSK: DS record to publish at parent
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_dnssec_zone_active ON dnssec_keys(zone_id, status) WHERE status = 'active';

CREATE TABLE routing_policies (
    policy_id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    zone_id             UUID NOT NULL,
    name                VARCHAR(200) NOT NULL,
    policy_type         VARCHAR(20) NOT NULL,
    config              JSONB NOT NULL,
    -- weighted: {"records": [{"set_id": "us-east", "weight": 70}, {"set_id": "eu-west", "weight": 30}]}
    -- latency: {"records": [{"set_id": "us-east", "region": "us-east-1"}, ...]}
    -- geo: {"records": [{"set_id": "europe", "continent": "EU"}, {"set_id": "default", "continent": "*"}]}
    -- failover: {"primary": "record-id-1", "secondary": "record-id-2"}
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

## 5. High-Level Design (HLD)

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                              GLOBAL DNS SYSTEM                                           │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                         │
│  CLIENT LAYER                                                                           │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐                       │
│  │   Stub     │  │   DoH      │  │   DoT      │  │  ISP       │                       │
│  │  Resolver  │  │  Client    │  │  Client    │  │ Recursive  │                       │
│  └─────┬──────┘  └─────┬──────┘  └─────┬──────┘  └─────┬──────┘                       │
│        │                │               │               │                               │
│  ┌─────▼────────────────▼───────────────▼───────────────▼──────────────────────────┐   │
│  │                         ANYCAST NETWORK (200+ PoPs)                              │   │
│  │                    All PoPs announce same IP via BGP                             │   │
│  │                    Client routes to geographically nearest                       │   │
│  └─────────────────────────────────┬───────────────────────────────────────────────┘   │
│                                    │                                                    │
│  EDGE PoP (× 200+)               │                                                    │
│  ┌─────────────────────────────────▼───────────────────────────────────────────────┐   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌────────────────────┐  │   │
│  │  │   DDoS       │  │   Query      │  │   Response   │  │   Zone Data        │  │   │
│  │  │  Mitigation  │──▶  Parser &    │──▶   Builder    │──▶   (In-Memory)      │  │   │
│  │  │  (RRL/BPF)   │  │  Router      │  │  + DNSSEC    │  │   150GB RAM        │  │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘  └────────────────────┘  │   │
│  │                                                                                  │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                          │   │
│  │  │  Recursive   │  │   Cache      │  │  Health      │                          │   │
│  │  │  Resolver    │  │  (LRU/ARC)   │  │  Check Agent │                          │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘                          │   │
│  └─────────────────────────────────────────────────────────────────────────────────┘   │
│                                    │                                                    │
│  CONTROL PLANE                     │                                                    │
│  ┌─────────────────────────────────▼───────────────────────────────────────────────┐   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌────────────────────┐  │   │
│  │  │   Zone       │  │   DNSSEC     │  │   Health     │  │   Routing Policy   │  │   │
│  │  │  Management  │  │   Signer     │  │   Check      │  │   Engine           │  │   │
│  │  │   API        │  │  (HSM)       │  │  Orchestrator│  │                    │  │   │
│  │  └──────┬───────┘  └──────────────┘  └──────────────┘  └────────────────────┘  │   │
│  │         │                                                                        │   │
│  │  ┌──────▼───────┐  ┌──────────────┐  ┌──────────────────────────────────────┐   │   │
│  │  │  Zone DB     │  │   Config     │  │   Zone Propagation Service           │   │   │
│  │  │ (PostgreSQL) │  │   Store      │  │   (Push to all PoPs < 60s)           │   │   │
│  │  └──────────────┘  └──────────────┘  └──────────────────────────────────────┘   │   │
│  └─────────────────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

## 6. Low-Level Design (LLD) – APIs

### 6.1 Zone Management APIs

```
POST /api/v1/zones
Request:
{
    "name": "example.com",
    "description": "Production zone for example.com",
    "dnssec": true
}
Response (201):
{
    "zone_id": "zone-uuid-123",
    "name": "example.com.",
    "status": "active",
    "nameservers": [
        "ns1.dns-provider.com.",
        "ns2.dns-provider.com.",
        "ns3.dns-provider.com.",
        "ns4.dns-provider.com."
    ],
    "dnssec": {
        "status": "signing",
        "ds_record": "example.com. IN DS 12345 13 2 ABC123...",
        "key_tag": 12345,
        "algorithm": "ECDSAP256SHA256"
    },
    "serial": 1,
    "created_at": "2024-01-15T10:00:00Z"
}

POST /api/v1/zones/{zone_id}/records
Request:
{
    "name": "www.example.com",
    "type": "A",
    "ttl": 300,
    "records": ["192.0.2.1", "192.0.2.2"],
    "routing_policy": "weighted",
    "routing_config": {
        "set_identifier": "us-east",
        "weight": 70,
        "health_check_id": "hc-uuid-456"
    }
}
Response (201):
{
    "record_id": "rec-uuid-789",
    "name": "www.example.com.",
    "type": "A",
    "ttl": 300,
    "records": ["192.0.2.1", "192.0.2.2"],
    "routing_policy": "weighted",
    "change_id": "change-uuid-101",
    "propagation_status": "pending"
}

GET /api/v1/zones/{zone_id}/records?name=www&type=A
Response (200):
{
    "records": [
        {
            "record_id": "rec-uuid-789",
            "name": "www.example.com.",
            "type": "A",
            "ttl": 300,
            "records": ["192.0.2.1", "192.0.2.2"],
            "routing_policy": "weighted",
            "weight": 70,
            "set_identifier": "us-east",
            "health_check_id": "hc-uuid-456",
            "health_status": "healthy"
        }
    ]
}
```

### 6.2 Health Check APIs

```
POST /api/v1/healthchecks
Request:
{
    "name": "web-server-us-east",
    "protocol": "HTTPS",
    "endpoint": "www.example.com",
    "port": 443,
    "path": "/health",
    "search_string": "\"status\":\"ok\"",
    "check_interval_sec": 10,
    "failure_threshold": 3,
    "regions": ["us-east-1", "eu-west-1", "ap-southeast-1"]
}
Response (201):
{
    "health_check_id": "hc-uuid-456",
    "status": "unknown",
    "next_check_at": "2024-01-15T10:00:10Z"
}

GET /api/v1/healthchecks/{id}/status
Response (200):
{
    "health_check_id": "hc-uuid-456",
    "current_status": "healthy",
    "last_check_at": "2024-01-15T10:05:00Z",
    "region_status": {
        "us-east-1": {"status": "healthy", "latency_ms": 45, "last_check": "2024-01-15T10:05:00Z"},
        "eu-west-1": {"status": "healthy", "latency_ms": 120, "last_check": "2024-01-15T10:04:58Z"},
        "ap-southeast-1": {"status": "healthy", "latency_ms": 200, "last_check": "2024-01-15T10:04:55Z"}
    },
    "status_history": [
        {"timestamp": "2024-01-15T09:00:00Z", "status": "healthy"},
        {"timestamp": "2024-01-14T22:15:00Z", "status": "unhealthy"},
        {"timestamp": "2024-01-14T22:00:00Z", "status": "healthy"}
    ]
}
```

## 7. Deep Dives

### 7.1 Query Resolution Path

```
┌─────────────────────────────────────────────────────────────────────┐
│                    DNS QUERY RESOLUTION PATH                         │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Client: "What is the IP of www.example.com?"                      │
│                                                                     │
│  ┌──────────┐                                                      │
│  │  Stub    │─── Query: www.example.com A ──▶ Recursive Resolver   │
│  │ Resolver │                                                      │
│  └──────────┘                                                      │
│                                                                     │
│  Recursive Resolver Algorithm:                                      │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ 1. Check local cache → HIT? Return immediately              │  │
│  │                                                              │  │
│  │ 2. MISS → Check if authoritative for zone                   │  │
│  │    YES → Look up in zone data → Return                      │  │
│  │                                                              │  │
│  │ 3. Start iterative resolution:                               │  │
│  │    a. Query Root NS (.) → "Try .com TLD at 192.5.6.30"     │  │
│  │    b. Query .com TLD NS → "Try example.com at 198.51.100.1"│  │
│  │    c. Query example.com NS → "www.example.com A 93.184.1.1"│  │
│  │                                                              │  │
│  │ 4. Cache all intermediate answers with TTL                   │  │
│  │ 5. Return final answer to client                             │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  DNSSEC Validation Chain:                                          │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                                                              │  │
│  │  Trust Anchor (Root KSK)                                     │  │
│  │       │                                                      │  │
│  │       ▼ DS record validates                                  │  │
│  │  Root ZSK ──signs──▶ .com NS + DS record                   │  │
│  │       │                                                      │  │
│  │       ▼ DS record validates                                  │  │
│  │  .com KSK → .com ZSK ──signs──▶ example.com NS + DS        │  │
│  │       │                                                      │  │
│  │       ▼ DS record validates                                  │  │
│  │  example.com KSK → ZSK ──signs──▶ www A record + RRSIG     │  │
│  │                                                              │  │
│  │  Validation: Verify RRSIG with ZSK → verify ZSK with KSK   │  │
│  │              → verify KSK with parent DS → chain to root    │  │
│  │                                                              │  │
│  │  NSEC3 (Negative cache / authenticated denial):             │  │
│  │  "nonexist.example.com" → NSEC3 proves name doesn't exist  │  │
│  │  Hash(nonexist) falls between two NSEC3 records = NXDOMAIN │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

```python
class RecursiveResolver:
    def __init__(self, cache, root_hints, dnssec_validator):
        self.cache = cache  # LRU with TTL-aware eviction
        self.root_hints = root_hints
        self.validator = dnssec_validator
    
    def resolve(self, qname: str, qtype: str, do_bit: bool = True) -> DNSResponse:
        # 1. Check cache
        cached = self.cache.get(qname, qtype)
        if cached and not cached.expired():
            return cached
        
        # 2. Check negative cache (NXDOMAIN / NODATA)
        neg_cached = self.cache.get_negative(qname, qtype)
        if neg_cached and not neg_cached.expired():
            return neg_cached
        
        # 3. Iterative resolution
        nameservers = self.root_hints
        closest_zone = "."
        
        labels = qname.rstrip('.').split('.')
        for i in range(len(labels)):
            zone = '.'.join(labels[i:]) + '.'
            cached_ns = self.cache.get(zone, 'NS')
            if cached_ns:
                nameservers = cached_ns
                closest_zone = zone
        
        # Walk from closest known delegation
        response = self._iterate(qname, qtype, nameservers)
        
        # 4. DNSSEC validation if DO bit set
        if do_bit and response.has_rrsig():
            validation_result = self.validator.validate_chain(response)
            if validation_result == ValidationResult.BOGUS:
                return DNSResponse(rcode=SERVFAIL, flags=["AD=0"])
            response.set_flag("AD", validation_result == ValidationResult.SECURE)
        
        # 5. Cache and return
        self.cache.put(qname, qtype, response, ttl=response.min_ttl())
        return response
    
    def _iterate(self, qname, qtype, nameservers):
        max_referrals = 10  # prevent loops
        for _ in range(max_referrals):
            ns = self._select_nameserver(nameservers)  # prefer lowest RTT
            response = self._query_nameserver(ns, qname, qtype)
            
            if response.is_answer():
                return response
            elif response.is_referral():
                nameservers = response.authority_ns()
                # Cache glue records
                for glue in response.additional():
                    self.cache.put(glue.name, glue.type, glue, glue.ttl)
            elif response.is_nxdomain():
                # Cache negative with SOA minimum TTL
                self.cache.put_negative(qname, qtype, response, response.soa_minimum())
                return response
        
        raise ResolutionError("Max referrals exceeded")
```

### 7.2 Anycast Network Design

```
┌─────────────────────────────────────────────────────────────────────┐
│                    ANYCAST NETWORK DESIGN                            │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  SAME IP (198.51.100.1) ANNOUNCED FROM ALL PoPs:                   │
│                                                                     │
│  ┌─────────┐   BGP    ┌──────────┐   BGP    ┌─────────────┐      │
│  │ PoP     │─announce─│ Transit  │──────────▶│   Client    │      │
│  │ Tokyo   │  /24     │ Provider │  shortest │   in Japan  │      │
│  │ 198.51. │          │ (NTT)    │  AS path  │   routes to │      │
│  │ 100.0/24│          └──────────┘           │   Tokyo PoP │      │
│  └─────────┘                                 └─────────────┘      │
│                                                                     │
│  ┌─────────┐   BGP    ┌──────────┐   BGP    ┌─────────────┐      │
│  │ PoP     │─announce─│ Transit  │──────────▶│   Client    │      │
│  │ London  │  /24     │ Provider │  shortest │   in UK     │      │
│  │ 198.51. │          │ (Telia)  │  AS path  │   routes to │      │
│  │ 100.0/24│          └──────────┘           │   London PoP│      │
│  └─────────┘                                 └─────────────┘      │
│                                                                     │
│  FAILOVER (PoP goes down):                                         │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  1. PoP health monitor detects failure                       │  │
│  │  2. BGP session withdrawn from failed PoP                    │  │
│  │  3. Routes converge (30-90 seconds)                          │  │
│  │  4. Traffic shifts to next-nearest PoP                       │  │
│  │  5. No client-side changes needed (same anycast IP)          │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  TRAFFIC ENGINEERING:                                              │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  - BGP communities to control announcement scope             │  │
│  │    community:100 = announce to all peers                     │  │
│  │    community:200 = announce to regional peers only           │  │
│  │    community:300 = prepend 3x (de-prefer this path)         │  │
│  │                                                              │  │
│  │  - AS path prepending to shift traffic away from overloaded  │  │
│  │    PoPs without full withdrawal                              │  │
│  │                                                              │  │
│  │  - Catchment area optimization:                              │  │
│  │    Monitor which client prefixes route to which PoP          │  │
│  │    Adjust communities/prepending to balance load             │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  ANYCAST + TCP (DoH/DoT):                                          │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  Challenge: BGP route change mid-TCP-connection = RST        │  │
│  │                                                              │  │
│  │  Solutions:                                                  │  │
│  │  1. Stable anycast: avoid unnecessary withdrawals            │  │
│  │  2. TCP keepalive with short idle timeout (30s)             │  │
│  │  3. QUIC/HTTP3: connection migration handles path changes    │  │
│  │  4. Client retry logic with connection pooling              │  │
│  │  5. Long-lived connections (DoT): use unicast IPs           │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

```python
class AnycastManager:
    def __init__(self, bgp_daemon, health_monitor):
        self.bgp = bgp_daemon
        self.health = health_monitor
        self.announced_prefixes = {}
    
    def announce_prefix(self, prefix: str, communities: list):
        """Announce anycast prefix via BGP"""
        self.bgp.announce(
            prefix=prefix,
            next_hop="self",
            communities=communities,
            origin="IGP",
            med=0
        )
        self.announced_prefixes[prefix] = {
            "status": "announced",
            "communities": communities,
            "announced_at": time.time()
        }
    
    def withdraw_prefix(self, prefix: str, reason: str):
        """Withdraw prefix (failover trigger)"""
        self.bgp.withdraw(prefix=prefix)
        self.announced_prefixes[prefix]["status"] = "withdrawn"
        self.announced_prefixes[prefix]["withdrawn_reason"] = reason
        logger.critical(f"Prefix {prefix} withdrawn: {reason}")
    
    def adjust_catchment(self, prefix: str, action: str):
        """Adjust traffic engineering"""
        if action == "depref":
            # Add AS prepends to shift traffic to other PoPs
            self.bgp.update(prefix, prepend_count=3)
        elif action == "restrict_regional":
            # Only announce to regional peers
            self.bgp.update(prefix, communities=["regional_only"])
        elif action == "full_announce":
            self.bgp.update(prefix, communities=["global"], prepend_count=0)
```

### 7.3 Traffic Management Policies

```python
class TrafficPolicyEngine:
    def __init__(self, health_checker, geo_db, latency_db):
        self.health = health_checker
        self.geo_db = geo_db          # MaxMind GeoIP2
        self.latency_db = latency_db  # Resolver IP → region latency map
    
    def resolve_weighted(self, records: list, query_context: QueryContext) -> list:
        """Weighted routing with deterministic hashing for stickiness"""
        # Filter healthy records
        healthy = [r for r in records if self.health.is_healthy(r.health_check_id)]
        if not healthy:
            healthy = records  # fall back to all if none healthy
        
        # Deterministic selection based on resolver IP for stickiness
        # Same resolver always gets same answer (until weights change)
        hash_input = f"{query_context.resolver_ip}:{query_context.qname}"
        hash_val = mmh3.hash(hash_input, signed=False) % 100
        
        # Build cumulative weight ranges
        total_weight = sum(r.weight for r in healthy)
        cumulative = 0
        for record in healthy:
            cumulative += (record.weight / total_weight) * 100
            if hash_val < cumulative:
                return [record]
        
        return [healthy[-1]]
    
    def resolve_latency(self, records: list, query_context: QueryContext) -> list:
        """Latency-based routing using passive measurements"""
        resolver_ip = query_context.resolver_ip
        
        # Look up resolver's approximate location
        resolver_region = self.geo_db.get_region(resolver_ip)
        
        # Get measured latencies from this region to each endpoint region
        best_record = None
        best_latency = float('inf')
        
        for record in records:
            if not self.health.is_healthy(record.health_check_id):
                continue
            
            latency = self.latency_db.get_latency(resolver_region, record.region)
            if latency < best_latency:
                best_latency = latency
                best_record = record
        
        return [best_record] if best_record else [records[0]]
    
    def resolve_geolocation(self, records: list, query_context: QueryContext) -> list:
        """Geolocation routing: continent → country → subdivision"""
        resolver_ip = query_context.resolver_ip
        geo = self.geo_db.lookup(resolver_ip)
        
        # Try most specific first
        for specificity in ['subdivision', 'country', 'continent', 'default']:
            matching = [r for r in records if self._geo_matches(r, geo, specificity)]
            if matching:
                healthy = [r for r in matching if self.health.is_healthy(r.health_check_id)]
                return healthy if healthy else matching
        
        return records  # fallback
    
    def resolve_failover(self, records: list, query_context: QueryContext) -> list:
        """Active-passive failover"""
        primary = [r for r in records if r.failover_role == 'primary']
        secondary = [r for r in records if r.failover_role == 'secondary']
        
        for p in primary:
            if self.health.is_healthy(p.health_check_id):
                return [p]
        
        # Primary unhealthy, use secondary
        for s in secondary:
            if self.health.is_healthy(s.health_check_id):
                return [s]
        
        return primary  # last resort: return primary even if unhealthy


class HealthCheckOrchestrator:
    """Distributed health checks with multi-region voting"""
    
    def __init__(self, checker_regions: list, voting_threshold: float = 0.5):
        self.regions = checker_regions
        self.threshold = voting_threshold
    
    def evaluate_health(self, health_check_id: str) -> str:
        """Collect results from all checker regions and vote"""
        results = {}
        for region in self.regions:
            result = self._get_region_result(health_check_id, region)
            results[region] = result
        
        healthy_count = sum(1 for r in results.values() if r.status == "healthy")
        total = len(results)
        
        if healthy_count / total >= self.threshold:
            return "healthy"
        else:
            return "unhealthy"
    
    def _probe(self, check_config: HealthCheck) -> ProbeResult:
        """Execute single health check probe"""
        start = time.time()
        try:
            if check_config.protocol == "HTTP" or check_config.protocol == "HTTPS":
                resp = requests.get(
                    f"{check_config.protocol.lower()}://{check_config.endpoint}:{check_config.port}{check_config.path}",
                    timeout=check_config.timeout_sec
                )
                success = resp.status_code == 200
                if success and check_config.search_string:
                    success = check_config.search_string in resp.text
            elif check_config.protocol == "TCP":
                sock = socket.create_connection(
                    (check_config.endpoint, check_config.port),
                    timeout=check_config.timeout_sec
                )
                sock.close()
                success = True
            
            return ProbeResult(success=success, latency_ms=(time.time()-start)*1000)
        except Exception as e:
            return ProbeResult(success=False, error=str(e))
```

## 8. Component Optimization

### In-Memory Zone Serving

```c
// Zone data structure optimized for query performance
// RCU (Read-Copy-Update) for lock-free reads

typedef struct zone_node {
    char *name;              // "www.example.com."
    uint16_t type;           // RR type
    uint32_t ttl;
    uint16_t rdlength;
    uint8_t *rdata;          // wire-format rdata
    struct zone_node *next;  // hash chain
    struct rrsig *sig;       // DNSSEC signature
} zone_node_t;

// Hash table: ~250M records, load factor 0.7
// Slots: 357M × 8 bytes (pointer) = 2.8 GB
// Records: 250M × ~300 bytes avg = 75 GB
// Total per PoP: ~80 GB RAM for zone data
```

### Zone Transfer (IXFR) with NOTIFY

```yaml
zone_propagation:
  # Control plane pushes changes to all PoPs
  method: "push_with_ixfr"
  protocol: "NOTIFY → IXFR"
  
  flow:
    1_api_change: "Zone record updated via API"
    2_serial_increment: "SOA serial incremented"
    3_notify: "NOTIFY sent to all PoP agents"
    4_ixfr: "PoPs request IXFR (incremental transfer)"
    5_apply: "PoP applies diff to in-memory zone"
    6_ack: "PoP acknowledges propagation"
  
  target_latency: "<60 seconds global"
  
  # Optimization: parallel push to all PoPs
  # Fallback: full AXFR if IXFR delta too large
```

### Response Rate Limiting (RRL)

```yaml
rrl:
  # Mitigate DNS amplification attacks
  responses_per_second: 5        # per identical response tuple
  window_seconds: 15
  slip: 2                        # send truncated (TC) every Nth dropped
  
  # Tuple: (qname, qtype, response_code, source_prefix)
  # Source prefix: /24 for IPv4, /56 for IPv6
  
  # Implementation: token bucket per tuple
  # Memory: 1M active tuples × 32 bytes = 32 MB
```

## 9. Observability

### Metrics

```yaml
metrics:
  query:
    - dns_queries_total{pop, qtype, rcode, protocol}
    - dns_query_latency_ms{pop, cache_hit, qtype}
    - dns_cache_hit_ratio{pop}
    - dns_cache_size_entries{pop}
    - dns_recursive_queries_total{pop}
    - dns_upstream_latency_ms{upstream_ns}
  
  zone:
    - dns_zone_count_total
    - dns_record_count_total{zone}
    - dns_zone_propagation_latency_ms{pop}
    - dns_zone_serial{zone, pop}
    - dns_ixfr_transfers_total{pop, status}
  
  health:
    - dns_healthcheck_status{check_id, region}
    - dns_healthcheck_latency_ms{check_id, region}
    - dns_failover_events_total{zone, record}
  
  dnssec:
    - dns_dnssec_validations_total{result}  # secure, insecure, bogus
    - dns_dnssec_key_age_days{zone, key_type}
    - dns_dnssec_signing_latency_ms
  
  network:
    - dns_rrl_drops_total{pop}
    - dns_ddos_mitigation_active{pop}
    - dns_bgp_announcements{pop, prefix, status}
    - dns_anycast_catchment_prefixes{pop}

alerts:
  - name: PopUnhealthy
    condition: dns_queries_total{pop=X} == 0 for 1m
    severity: critical
    action: verify BGP, check hardware
  
  - name: PropagationLag
    condition: dns_zone_propagation_latency_ms > 120000
    severity: warning
  
  - name: CacheHitDrop
    condition: dns_cache_hit_ratio < 0.70
    severity: warning
  
  - name: DNSSECKeyExpiry
    condition: dns_dnssec_key_age_days{key_type="ZSK"} > 80
    severity: warning
    action: trigger automatic ZSK rollover
  
  - name: DDoSDetected
    condition: dns_rrl_drops_total rate > 100000/sec
    severity: critical
```

### Query Logging (Sampled)

```yaml
query_log:
  sample_rate: 0.01  # 1% of queries
  fields:
    - timestamp
    - pop_id
    - source_ip (truncated /24)
    - qname
    - qtype
    - rcode
    - latency_us
    - cache_hit
    - dnssec_validated
    - protocol (udp/tcp/doh/dot)
  storage: s3
  retention: 30d
  format: parquet (columnar, compressed)
```

## 10. Failure Analysis & Considerations

### Failure Scenarios

| Scenario | Impact | Mitigation |
|----------|--------|------------|
| PoP failure | Traffic reroutes to next PoP (30-90s) | BGP withdrawal + anycast auto-failover |
| Control plane failure | No zone updates; serving continues | PoPs serve from local zone cache; multi-AZ control plane |
| BGP hijack | Traffic misdirected | RPKI ROA validation, BGP monitoring |
| Zone propagation failure | Stale records at some PoPs | Serial number monitoring; alert on drift |
| HSM failure (DNSSEC) | Cannot sign new records | HSM cluster with automatic failover |
| Resolver cache poisoning | Wrong answers served | DNSSEC validation; source port randomization; 0x20 encoding |
| DDoS on single zone | Resource exhaustion | Per-zone rate limiting; anycast absorption |

### Considerations

1. **Consistency vs. Availability**: DNS favors availability (serve stale over SERVFAIL); RFC 8767 (serving stale data)
2. **TTL Trade-offs**: Low TTL = faster failover but higher query load; High TTL = better caching but slow changes
3. **DNSSEC Key Rollover**: ZSK every 90 days, KSK annually; double-signature during rollover period
4. **IPv6 Fragmentation**: Large DNSSEC responses may fragment; use TCP fallback or EDNS0 buffer size negotiation
5. **Privacy**: DoH/DoT prevent ISP snooping but shift trust to resolver operator; consider EDNS Client Subnet privacy
6. **Negative Caching**: NSEC3 with opt-out for large unsigned delegations; prevent zone walking attacks
7. **Resolver Selection**: EDNS Client Subnet (ECS) leaks client subnet to authoritative for better geo answers
8. **Multi-CDN**: DNS as a load balancer across CDN providers; complex health checking and failover logic
9. **Root Zone Local Copy**: RFC 8806 — local root server copy reduces latency for cold cache queries
10. **Anycast Stability**: Avoid flapping (rapid announce/withdraw cycles) which causes route instability

## 11. References

- RFC 1035 (DNS), RFC 4034/4035 (DNSSEC), RFC 8484 (DoH), RFC 7858 (DoT)
- RFC 8767 (Serving Stale Data), RFC 8806 (Running a Root Server Local)
- Cloudflare architecture blog, AWS Route 53 documentation
