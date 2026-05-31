# CDN Architecture Deep Dive

## How CDNs Work Internally

### Core Components

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         CDN Architecture                                 │
│                                                                         │
│  User ──▶ DNS ──▶ Anycast/GeoDNS ──▶ Nearest PoP                      │
│                                          │                              │
│                                    ┌─────▼─────┐                       │
│                                    │ Edge Server│ (L1 Cache)            │
│                                    │   (PoP)   │                       │
│                                    └─────┬─────┘                       │
│                                          │ MISS                        │
│                                    ┌─────▼─────┐                       │
│                                    │ Mid-Tier  │ (L2 Cache / Regional) │
│                                    │   Cache   │                       │
│                                    └─────┬─────┘                       │
│                                          │ MISS                        │
│                                    ┌─────▼─────┐                       │
│                                    │  Origin   │ (L3 Cache)            │
│                                    │  Shield   │                       │
│                                    └─────┬─────┘                       │
│                                          │ MISS                        │
│                                    ┌─────▼─────┐                       │
│                                    │  Origin   │                       │
│                                    │  Server   │                       │
│                                    └───────────┘                       │
└─────────────────────────────────────────────────────────────────────────┘
```

### PoP (Point of Presence)

A PoP is a physical data center location containing CDN edge servers.

```
┌─────────────────── PoP (e.g., Mumbai) ───────────────────┐
│                                                           │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐              │
│  │Edge Srv 1│  │Edge Srv 2│  │Edge Srv 3│  ...         │
│  │ Cache:2TB│  │ Cache:2TB│  │ Cache:2TB│              │
│  └──────────┘  └──────────┘  └──────────┘              │
│       │              │              │                    │
│       └──────────────┼──────────────┘                    │
│                      │                                   │
│              ┌───────▼───────┐                          │
│              │  Load Balancer │                          │
│              │  (L4/L7)      │                          │
│              └───────┬───────┘                          │
│                      │                                   │
│              ┌───────▼───────┐                          │
│              │  Router/Switch │                          │
│              │  (Anycast IP) │                          │
│              └───────────────┘                          │
└───────────────────────────────────────────────────────────┘
```

**Typical PoP contains:**
- 10-1000s of edge servers
- SSD/NVMe storage for hot cache
- RAM cache for ultra-hot objects
- Local load balancers
- BGP routers announcing anycast prefixes

### Edge Servers

Each edge server handles:
1. **TLS termination** - decrypt HTTPS at edge
2. **Cache lookup** - check local SSD/RAM cache
3. **Content negotiation** - serve correct variant (gzip, brotli, webp)
4. **Request routing** - forward cache misses upstream
5. **Connection pooling** - reuse connections to origin

### Origin Shield

A designated PoP that acts as a single point of contact to origin:

```
Without Origin Shield:              With Origin Shield:
                                    
PoP-1 ──┐                         PoP-1 ──┐
PoP-2 ──┼──▶ Origin               PoP-2 ──┼──▶ Origin Shield ──▶ Origin
PoP-3 ──┘    (3 requests)         PoP-3 ──┘    (1 request)
```

**Benefits:**
- Reduces origin load by 90%+
- Single cache fill even during stampede
- Enables request collapsing (coalescing)

### Mid-Tier / Regional Caches

```
         Americas Region                    Europe Region
┌──────────────────────────┐      ┌──────────────────────────┐
│  NYC PoP    LAX PoP      │      │  LON PoP    FRA PoP     │
│    │          │           │      │    │          │          │
│    └────┬─────┘           │      │    └────┬─────┘          │
│         ▼                 │      │         ▼                │
│   Regional Cache          │      │   Regional Cache         │
│   (Chicago)               │      │   (Amsterdam)            │
└────────────┬──────────────┘      └────────────┬─────────────┘
             │                                   │
             └──────────────┬────────────────────┘
                            ▼
                     Origin Shield
                     (US-East)
                            │
                            ▼
                        Origin
```

---

## Anycast Routing Explained

### What is Anycast?

Multiple servers share the **same IP address**. BGP routing directs packets to the nearest server.

```
                    User in Tokyo
                         │
                         ▼
                   Internet (BGP)
                   ┌─────┴─────┐
                   │ Shortest  │
                   │ AS Path   │
                   └─────┬─────┘
                         ▼
          ┌─────────────────────────────┐
          │  IP: 1.2.3.4 announced from │
          │  all these locations:        │
          │                             │
  ┌───────┼────────┬──────────┐        │
  ▼       ▼        ▼          ▼        │
Tokyo   Mumbai   London    New York    │
PoP     PoP      PoP       PoP        │
          └─────────────────────────────┘
          
Result: User → Tokyo PoP (nearest by BGP hops)
```

### How BGP Anycast Works

1. CDN announces same IP prefix (e.g., `104.16.0.0/12`) from all PoPs
2. Each PoP's router announces to upstream ISPs via BGP
3. Internet routers select shortest AS path
4. Packets flow to geographically/topologically nearest PoP

```
BGP Announcement from each PoP:

Tokyo Router:    "104.16.0.0/12 via AS13335 (path: AS13335)"
Mumbai Router:   "104.16.0.0/12 via AS13335 (path: AS13335)"
London Router:   "104.16.0.0/12 via AS13335 (path: AS13335)"

ISP in Japan sees:
  - Tokyo: 1 hop
  - Mumbai: 3 hops
  - London: 5 hops
  → Routes to Tokyo
```

### Anycast Challenges

| Challenge | Solution |
|-----------|----------|
| TCP session persistence | Anycast is stable within same BGP path |
| Route flapping | ECMP, connection migration (QUIC) |
| Uneven load | BGP community manipulation, prepending |
| Failover | Withdraw BGP route from unhealthy PoP |

---

## GeoDNS vs Anycast vs Latency-Based Routing

### Comparison

```
┌────────────────────────────────────────────────────────────────────┐
│                    Routing Strategy Comparison                       │
├──────────────┬──────────────┬──────────────────┬───────────────────┤
│              │   GeoDNS     │    Anycast       │  Latency-Based    │
├──────────────┼──────────────┼──────────────────┼───────────────────┤
│ Layer        │ DNS (L7)     │ Network (L3)     │ DNS (L7)          │
│ Granularity  │ Country/City │ BGP topology     │ Measured latency  │
│ Failover     │ DNS TTL wait │ Instant (BGP)    │ Health check dep  │
│ Accuracy     │ GeoIP DB     │ Network topology │ Real measurements │
│ TCP sticky   │ Yes (same IP)│ Yes (stable BGP) │ Yes (same IP)     │
│ Setup        │ Simple       │ Complex (BGP)    │ Moderate          │
│ Used by      │ AWS Route53  │ Cloudflare       │ AWS Route53       │
│              │              │ Google Cloud CDN  │ Latency routing   │
└──────────────┴──────────────┴──────────────────┴───────────────────┘
```

### GeoDNS

```
User DNS Query → Authoritative DNS
                      │
                      ├─ Source IP: 203.x.x.x (India)
                      │  → GeoIP lookup → India
                      │  → Return: mumbai-cdn.example.com (1.2.3.4)
                      │
                      ├─ Source IP: 72.x.x.x (US)
                      │  → GeoIP lookup → US-East
                      │  → Return: nyc-cdn.example.com (5.6.7.8)
```

**Limitations:**
- GeoIP databases can be inaccurate
- DNS resolvers may not be near user (e.g., Google 8.8.8.8)
- EDNS Client Subnet (ECS) helps but not universal

### Latency-Based Routing (AWS Route 53)

```
AWS Route 53 continuously measures latency from regions:

User → DNS Query → Route 53
                      │
                      ├─ Checks latency measurements:
                      │   Mumbai: 15ms
                      │   Singapore: 45ms
                      │   Frankfurt: 180ms
                      │
                      └─ Returns: Mumbai endpoint IP
```

---

## TCP/TLS Optimization at Edge

### Connection Reuse

```
Without CDN:                        With CDN Edge:
                                    
User ──TCP+TLS──▶ Origin           User ──TCP+TLS──▶ Edge (nearby)
     (200ms RTT × 3 = 600ms)                (20ms RTT × 3 = 60ms)
                                    
                                    Edge ──persistent──▶ Origin
                                         (pre-established, pooled)
```

**Optimization techniques:**

| Technique | Benefit |
|-----------|---------|
| TCP connection pooling | Reuse connections to origin, avoid 3-way handshake |
| TCP Fast Open (TFO) | Send data in SYN packet |
| TLS session resumption | Skip full TLS handshake on reconnect |
| TLS 1.3 0-RTT | Send data immediately on resumed sessions |
| OCSP stapling | Avoid separate OCSP check (saves 1 RTT) |
| HTTP keepalive | Reuse TCP connection for multiple requests |

### TLS Session Resumption

```
First Connection:                    Resumed Connection:
                                    
Client → ClientHello               Client → ClientHello + SessionTicket
Server → ServerHello + Cert        Server → ServerHello + Finished
Client → KeyExchange               (Data flows immediately)
Server → Finished                  
(2 RTT)                            (1 RTT, or 0-RTT with TLS 1.3)
```

### OCSP Stapling

```
Without Stapling:                   With Stapling:

Client ──▶ Server                  Client ──▶ Server
Client ──▶ OCSP Responder         Server includes OCSP response
  (extra DNS + TCP + HTTP)          in TLS handshake (stapled)
  (adds 100-500ms)                  (0ms extra)
```

---

## HTTP/2 and HTTP/3 at Edge

### HTTP/2 Server Push (deprecated but educational)

```
Client requests: /index.html

Server pushes:
  PUSH_PROMISE: /style.css
  PUSH_PROMISE: /app.js

Result: Client gets CSS/JS without requesting them
```

### HTTP/3 (QUIC) at Edge

```
┌──────────────────────────────────────────────────────┐
│              HTTP/3 (QUIC) Benefits at CDN            │
├──────────────────────────────────────────────────────┤
│                                                      │
│  Traditional (TCP+TLS):                              │
│  ┌───┐    ┌───┐    ┌───┐                           │
│  │SYN│───▶│TLS│───▶│REQ│  = 3 RTT before data     │
│  └───┘    └───┘    └───┘                           │
│                                                      │
│  QUIC (0-RTT resumption):                           │
│  ┌─────────────┐                                    │
│  │REQ + 0-RTT  │  = 0 RTT before data              │
│  └─────────────┘                                    │
│                                                      │
│  Key advantages:                                     │
│  • No head-of-line blocking (per-stream)            │
│  • Connection migration (WiFi → cellular)           │
│  • Built-in encryption (always encrypted)           │
│  • Faster loss recovery                             │
└──────────────────────────────────────────────────────┘
```

---

## Multi-CDN Architecture

### Why Multi-CDN?

- **Redundancy** - survive CDN outages
- **Performance** - route to fastest CDN per user
- **Cost** - use cheapest CDN for each region
- **Compliance** - data sovereignty requirements

### Architecture Patterns

```
Pattern 1: DNS-Based Failover

User → DNS → Traffic Manager (health checks)
                    │
         ┌─────────┼─────────┐
         ▼         ▼         ▼
     CloudFront  Cloudflare  Fastly
     (Primary)   (Secondary) (Tertiary)
         │         │         │
         └─────────┼─────────┘
                   ▼
               Origin


Pattern 2: RUM-Based (Real User Monitoring)

User → JavaScript beacon measures latency to each CDN
                    │
         ┌─────────▼─────────┐
         │  Decision Engine   │
         │  (Cedexis/Citrix)  │
         └─────────┬─────────┘
                   │
    Routes to fastest CDN for THIS user
```

### Multi-CDN Configuration Example

```yaml
# Citrix ITM / NS1 / Route53 weighted routing
primary:
  provider: cloudfront
  weight: 60
  health_check: /health
  failover_threshold: 3

secondary:
  provider: cloudflare
  weight: 30
  health_check: /health

tertiary:
  provider: fastly
  weight: 10
  health_check: /health

rules:
  - region: APAC
    primary: cloudflare  # Better APAC coverage
  - region: NA
    primary: cloudfront  # AWS integration
  - content: video/*
    primary: fastly      # Better streaming
```

---

## CDN Origin Architecture

### Tiered Distribution

```
┌─────────────────────────────────────────────────────────────────┐
│                    Tiered CDN Architecture                        │
│                                                                  │
│  Tier 1 (Edge):     200+ PoPs globally                         │
│  ┌───┐┌───┐┌───┐┌───┐┌───┐┌───┐┌───┐┌───┐                   │
│  │   ││   ││   ││   ││   ││   ││   ││   │  ... (small cache) │
│  └─┬─┘└─┬─┘└─┬─┘└─┬─┘└─┬─┘└─┬─┘└─┬─┘└─┬─┘                   │
│    │     │     │     │     │     │     │     │                   │
│  Tier 2 (Regional): 10-20 regional caches                      │
│    └──┬──┘     └──┬──┘     └──┬──┘     └──┬──┘                 │
│       │           │           │           │    (medium cache)    │
│       ▼           ▼           ▼           ▼                     │
│    ┌─────┐     ┌─────┐    ┌─────┐    ┌─────┐                  │
│    │US-E │     │EU-W │    │APAC │    │US-W │                  │
│    └──┬──┘     └──┬──┘    └──┬──┘    └──┬──┘                  │
│       │           │           │           │                     │
│  Tier 3 (Origin Shield): 1-3 locations                         │
│       └───────────┼───────────┼───────────┘                     │
│                   ▼                                              │
│              ┌─────────┐                                        │
│              │ Origin  │  (large cache, request collapsing)     │
│              │ Shield  │                                        │
│              └────┬────┘                                        │
│                   │                                              │
│              ┌────▼────┐                                        │
│              │ Origin  │                                        │
│              └─────────┘                                        │
└─────────────────────────────────────────────────────────────────┘
```

---

## Complete Request Lifecycle

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    Full CDN Request Lifecycle                             │
│                                                                         │
│  1. User types: https://cdn.example.com/image.jpg                       │
│                                                                         │
│  2. DNS Resolution:                                                     │
│     User → Local DNS Resolver                                           │
│          → Root NS → .com NS → example.com NS                          │
│          → CNAME: cdn.example.com → d123.cloudfront.net                 │
│          → CloudFront DNS (anycast) → PoP IP: 54.230.x.x               │
│                                                                         │
│  3. TCP + TLS Handshake (to nearest edge):                              │
│     User ←──TCP SYN/ACK──→ Edge (20ms RTT)                             │
│     User ←──TLS 1.3───────→ Edge (1 RTT with resumption)               │
│                                                                         │
│  4. HTTP Request:                                                       │
│     GET /image.jpg HTTP/2                                               │
│     Host: cdn.example.com                                               │
│     Accept: image/webp,image/*                                          │
│                                                                         │
│  5a. Cache HIT:                                                         │
│      Edge has fresh copy → Return immediately                           │
│      X-Cache: Hit from cloudfront                                       │
│      Age: 3600                                                          │
│                                                                         │
│  5b. Cache MISS:                                                        │
│      Edge → Regional Cache (L2)                                         │
│        HIT? → Return + cache at edge                                    │
│        MISS → Origin Shield (L3)                                        │
│          HIT? → Return + cache at regional + edge                       │
│          MISS → Origin Server                                           │
│            Origin returns + Cache-Control: public, max-age=86400        │
│            Cache at all tiers                                           │
│                                                                         │
│  6. Response to User:                                                   │
│     HTTP/2 200 OK                                                       │
│     Content-Type: image/webp                                            │
│     Cache-Control: public, max-age=86400                                │
│     X-Cache: Miss from cloudfront                                       │
│     X-Amz-Cf-Pop: BOM50-C1 (Mumbai)                                    │
│                                                                         │
│  Total time: HIT = ~25ms | MISS = ~200ms                               │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## DNS Resolution Flow for CDN

```
User Browser                Local Resolver         Authoritative DNS
    │                            │                       │
    │─── A? cdn.example.com ────▶│                       │
    │                            │── A? cdn.example.com ▶│
    │                            │                       │
    │                            │◀─ CNAME: d123.cf.net ─│
    │                            │                       │
    │                            │── A? d123.cf.net ────▶│ (CloudFront DNS)
    │                            │                       │
    │                            │   [CloudFront DNS checks:          ]
    │                            │   [  - Client IP / EDNS subnet     ]
    │                            │   [  - Latency maps                ]
    │                            │   [  - PoP health                  ]
    │                            │   [  - Returns nearest healthy PoP ]
    │                            │                       │
    │                            │◀─ A: 54.230.1.100 ───│ (Mumbai PoP)
    │                            │   TTL: 60s            │
    │◀── A: 54.230.1.100 ───────│                       │
    │                            │                       │
```

**Key DNS optimizations:**
- Low TTL (60s) for fast failover
- EDNS Client Subnet for accurate geo-routing
- DNS prefetch (`<link rel="dns-prefetch">`)
- Multiple A records for client-side failover

---

## CDN Data Plane vs Control Plane

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                  │
│  CONTROL PLANE (Configuration & Management)                     │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ • Distribution/Zone configuration                          │ │
│  │ • Cache invalidation commands                              │ │
│  │ • SSL certificate deployment                               │ │
│  │ • WAF rule updates                                         │ │
│  │ • Edge function deployment                                 │ │
│  │ • Health check configuration                               │ │
│  │ • Propagation: minutes (eventually consistent)             │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  DATA PLANE (Request Handling - Hot Path)                       │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ • TLS termination                                          │ │
│  │ • Cache lookup/store                                       │ │
│  │ • Request routing                                          │ │
│  │ • Compression (gzip/brotli)                                │ │
│  │ • Header manipulation                                      │ │
│  │ • Edge function execution                                  │ │
│  │ • Origin fetch                                             │ │
│  │ • Latency: microseconds-milliseconds                      │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

| Aspect | Control Plane | Data Plane |
|--------|--------------|------------|
| Consistency | Eventually consistent | Real-time |
| Latency tolerance | Seconds-minutes | Microseconds |
| Failure impact | Can't update config | Users can't access content |
| Scale | Low throughput | Millions of RPS |
| Examples | API calls, console | HTTP requests from users |
