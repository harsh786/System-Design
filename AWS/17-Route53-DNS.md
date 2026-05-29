# Amazon Route 53 - DNS & Traffic Management Complete Guide

---

## 1. Route 53 Overview
- **What:** Highly available (100% SLA) and scalable DNS web service
- **Functions:** Domain registration, DNS routing, health checking, traffic management
- **Name origin:** Port 53 = DNS port
- **Pricing:** $0.50/hosted zone/month + $0.40 per 1M standard queries

---

## 2. DNS Fundamentals

### Record Types
| Type | Purpose | Example |
|------|---------|---------|
| A | IPv4 address | example.com → 1.2.3.4 |
| AAAA | IPv6 address | example.com → 2001:db8::1 |
| CNAME | Canonical name (alias) | www.example.com → example.com |
| MX | Mail exchange | example.com → mail.example.com (priority 10) |
| TXT | Text (verification, SPF, DKIM) | example.com → "v=spf1 include:..." |
| NS | Name servers for zone | example.com → ns-1.awsdns-01.org |
| SOA | Start of authority (zone info) | Serial, refresh, retry, expire |
| SRV | Service locator | _sip._tcp.example.com → server:port |
| CAA | Certificate authority authorization | Which CAs can issue certs |
| PTR | Reverse DNS | IP → hostname |

### CNAME vs Alias
| | CNAME | Alias (Route 53 specific) |
|--|---|---|
| Zone apex (naked domain) | NO (example.com) | YES |
| Target | Any DNS name | AWS resources only |
| Charges | Standard DNS query charge | FREE for alias to AWS resources |
| Health checks | Via routing policy | Via routing policy |
| **Use** | Non-apex, external targets | AWS resources (ALB, CF, S3, etc.) |

### Alias Targets (AWS resources)
- ELB (ALB, NLB, CLB)
- CloudFront distribution
- API Gateway
- S3 website endpoint
- VPC Interface Endpoint
- Global Accelerator
- Another Route 53 record in same hosted zone
- **NOT supported:** EC2 public IP (use A record), RDS endpoint (use CNAME)

---

## 3. Hosted Zones

### Public Hosted Zone
- Contains records for how to route traffic on the internet
- Created automatically when registering domain
- NS records point to Route 53 name servers (4 per zone)
- **Use case:** Public-facing websites, APIs

### Private Hosted Zone
- Contains records for routing within VPC(s)
- Only accessible from associated VPCs
- Must enable DNS hostnames and DNS support in VPC
- Can associate multiple VPCs (same or different accounts/regions)
- **Use case:** Internal service discovery, private APIs

### Split-View DNS
- Same domain name → different records for public vs private
- Public hosted zone: example.com → public ALB (internet users)
- Private hosted zone: example.com → internal ALB (VPC users)
- **Use case:** Internal users hit internal endpoints, external users hit public

---

## 4. Routing Policies

### Simple Routing
- One record → one or multiple IP addresses
- If multiple values: Client receives all, chooses randomly (client-side load balancing)
- **No health checks** on individual records
- **Use case:** Single resource, no special routing needs

### Weighted Routing
- Split traffic by percentage (weights 0-255)
- Example: Record A weight 70, Record B weight 30 → 70/30 traffic split
- Weight 0 = no traffic. All weights 0 = equal distribution
- **Health check:** If unhealthy, removed from responses (traffic shifts to healthy)
- **Use case:** Blue/green deployment (shift traffic gradually), A/B testing, load distribution

### Latency-Based Routing
- Route to region with lowest latency for the user
- Route 53 uses latency measurements between users and AWS regions
- Combines with health checks (failover to next-best region)
- **Use case:** Multi-region active-active deployment

### Failover Routing
- **Primary/Secondary:** Active-passive failover
- Primary record with health check → if unhealthy → return Secondary
- Secondary can be: standby resource, static S3 website (error page)
- **Use case:** DR setup, maintenance page

### Geolocation Routing
- Route based on user's geographic location (continent, country, or US state)
- **Most specific match wins:** State > Country > Continent > Default
- Must set "Default" record (for unmatched locations)
- **Use case:** Content localization, compliance (keep traffic in country), restrict access

### Geoproximity Routing (Traffic Flow only)
- Route based on geographic location of resources AND users
- **Bias:** Expand (+) or shrink (-) geographic region for a resource
- Bias: -99 to +99. Higher bias = more traffic routed to that resource
- **Use case:** Shift traffic between regions without changing infrastructure
- Requires Route 53 Traffic Flow (visual editor)

### Multi-Value Answer Routing
- Return up to 8 healthy records per query
- Each record has its own health check
- **Not a substitute for ELB** but provides client-side health-aware DNS
- **Use case:** Simple load distribution with health checking (no LB needed)

### IP-Based Routing
- Route based on client's IP address (CIDR blocks you define)
- Create IP collections (CIDR → location mapping)
- **Use case:** Route ISP users to specific endpoints, optimize network costs

---

## 5. Health Checks

### Types
| Type | What it Checks |
|------|----------------|
| Endpoint | HTTP/HTTPS/TCP to IP or domain (every 30s standard, 10s fast) |
| Calculated | Combine multiple health checks (AND/OR/threshold) |
| CloudWatch Alarm | Health status based on CloudWatch alarm state |

### Endpoint Health Check Configuration
- **Protocol:** HTTP, HTTPS, TCP
- **Interval:** 30 seconds (standard) or 10 seconds (fast, $1/month)
- **Failure threshold:** 1-10 consecutive failures to mark unhealthy (default 3)
- **Regions:** 15+ health checker locations worldwide
- **String matching (HTTP/HTTPS):** Response body must contain string (first 5120 bytes)
- **Healthy threshold:** Minimum % of health checkers that must report healthy (default 18%)

### Health Check + Routing
- Associate health check with DNS record
- Unhealthy record → removed from DNS responses
- Traffic automatically routes to healthy records
- **Failover:** Primary unhealthy → Secondary returned

### Private Resources Health Checks
- **Problem:** Route 53 health checkers are on the public internet (can't reach private IPs)
- **Solution:** Create CloudWatch Alarm monitoring the private resource → Health check monitors the alarm
- Example: EC2 in private subnet → CloudWatch Alarm on StatusCheck → Health Check on Alarm

### Calculated Health Checks
- Combine multiple child health checks into parent
- **Logic:** All must be healthy, At least N must be healthy, or any one must be healthy
- **Use case:** Consider service "healthy" only if 2 of 3 endpoints pass

---

## 6. Route 53 Traffic Flow
- **Visual policy editor:** Create complex routing trees
- **Traffic policy:** Reusable routing configuration (version-controlled)
- **Policy record:** Associates traffic policy with a DNS name
- **Use case:** Complex multi-layer routing (geolocation → latency → weighted → failover)
- **Pricing:** $50/month per policy record (expensive)

### Traffic Flow Example
```
User request → Geolocation rule:
  ├── Europe → Latency rule:
  │     ├── eu-west-1 (healthy?) → ALB eu-west-1
  │     └── eu-central-1 → ALB eu-central-1
  ├── Americas → Weighted rule:
  │     ├── 80% → us-east-1 ALB
  │     └── 20% → us-west-2 ALB
  └── Default → Failover:
        ├── Primary → ap-southeast-1 ALB
        └── Secondary → Static S3 error page
```

---

## 7. Route 53 Resolver

### What
- DNS resolution for hybrid environments (AWS VPC ↔ on-premises)
- **Inbound Endpoint:** On-prem DNS can resolve AWS private hosted zones
- **Outbound Endpoint:** VPC resources can resolve on-prem DNS domains
- **Rules:** Forward specific domains to specific DNS servers

### Architecture
```
On-Premises (10.0.0.0/8):
  DNS Server: 10.0.0.53
  Needs to resolve: api.internal.aws (private hosted zone)
  
AWS VPC (172.16.0.0/16):
  Resolver Inbound Endpoint: 172.16.1.10, 172.16.2.10
  Needs to resolve: ldap.corp.internal (on-prem domain)
  Resolver Outbound Endpoint → Forwarding Rule → 10.0.0.53

Configuration:
  On-prem DNS: Forward *.aws queries → 172.16.1.10 (inbound endpoint)
  Route 53: Forwarding rule *.corp.internal → 10.0.0.53 (via outbound endpoint)
```

### Resolver DNS Firewall
- Filter DNS queries from VPC (block malicious domains)
- **Rules:** Allow/block/alert on domain lists
- **Managed rule groups:** AWS provides lists (botnet, malware C&C)
- **Use case:** Prevent data exfiltration via DNS tunneling, block known-bad domains

---

## 8. Domain Registration & DNSSEC
- **Registration:** Register domains directly in Route 53 (auto-creates hosted zone)
- **Transfer:** Transfer existing domains to Route 53 (unlock at registrar, get auth code)
- **DNSSEC:** Sign DNS records with cryptographic signatures (prevent DNS spoofing)
  - Route 53 supports DNSSEC signing for public hosted zones
  - Uses KMS key (asymmetric, ECC_NIST_P256)
  - Must establish chain of trust (DS record at parent zone)

---

## 9. Route 53 Patterns & Best Practices

### Multi-Region Active-Active
```
example.com:
  Latency-based routing:
    us-east-1: ALB (health check: /health)
    eu-west-1: ALB (health check: /health)
    ap-southeast-1: ALB (health check: /health)
    
  Health check fails → automatic failover to next-lowest-latency region
  TTL: 60 seconds (balance between freshness and DNS caching)
```

### Blue-Green Deployment
```
app.example.com:
  Weighted routing:
    Blue (current): weight 100 → ALB-blue
    Green (new): weight 0 → ALB-green
    
  Deployment steps:
    1. Deploy to Green (weight 0, no traffic)
    2. Test Green directly (via direct ALB DNS)
    3. Shift: Blue 90, Green 10 (canary)
    4. Monitor errors, latency
    5. Shift: Blue 0, Green 100
    6. Cleanup Blue
```

### Disaster Recovery
```
Primary region (us-east-1):
  Health check: /health endpoint every 10 seconds
  Failover: PRIMARY record

DR region (us-west-2):
  Always running (warm standby) or scaled down (pilot light)
  Failover: SECONDARY record

RTO depends on:
  - Health check interval (10-30 seconds)
  - Failure threshold (2-3 checks = 20-90 seconds)
  - DNS TTL (60 seconds typical)
  - Total: 1.5 - 3 minutes for DNS failover
```

### Service Discovery
```
Private hosted zone: internal.myapp
  
  payment.internal.myapp → internal NLB (gRPC service)
  orders.internal.myapp → internal ALB (REST service)
  cache.internal.myapp → ElastiCache endpoint
  db.internal.myapp → RDS endpoint (CNAME)
  
  OR use Cloud Map (AWS service discovery) for dynamic:
    - ECS services auto-register/deregister
    - API: DiscoverInstances() for client-side discovery
```

---

## 10. Scenario-Based Interview Questions

### Q1: Global application needs < 100ms latency for all users worldwide
**Answer:**
- **Architecture:** Multi-region deployment (us-east-1, eu-west-1, ap-southeast-1)
- **DNS:** Latency-based routing in Route 53 (users → nearest region)
- **Data:** DynamoDB Global Tables (multi-region replication, < 1 second)
- **Static content:** CloudFront with origins in each region
- **Health checks:** Each region health-checked, auto-failover
- **Why not Geolocation?** Latency-based is better because same country users may have different latency to regions
- **Enhancement:** Global Accelerator for non-HTTP (TCP/UDP) traffic (static IPs, anycast)

### Q2: Route 53 failover taking too long (users seeing errors for 5+ minutes)
**Answer:**
- **Root causes of slow failover:**
  - TTL too high (300s default) → clients cache stale DNS for 5 min
  - Health check interval 30s + threshold 3 = 90s to detect failure
  - Client-side DNS caching (OS, browser, resolver)
- **Fix:**
  1. Reduce TTL to 60 seconds (trade-off: more DNS queries = slightly more cost/latency)
  2. Fast health checks: 10-second interval (instead of 30)
  3. Lower failure threshold: 2 instead of 3 (20s to detect)
  4. Total: 20s detection + 60s TTL propagation ≈ 80 seconds
- **Additional:** Use Global Accelerator (instant failover, no DNS TTL dependency)

### Q3: Migrate DNS from GoDaddy to Route 53 with zero downtime
**Answer:**
```
Step 1: Create hosted zone in Route 53 (get 4 NS records)
Step 2: Export all DNS records from GoDaddy
Step 3: Import/recreate all records in Route 53 hosted zone
Step 4: Lower TTL on all records at GoDaddy to 60 seconds (wait 1 TTL period)
Step 5: Verify Route 53 records resolve correctly (dig @ns-xxx.awsdns-xx.org)
Step 6: Update NS records at GoDaddy registrar → Route 53 NS servers
   (or transfer domain to Route 53 registrar)
Step 7: Wait 48 hours for full propagation
Step 8: Monitor for any resolution failures
Step 9: After stable, set appropriate TTLs (300-3600 seconds)
```

### Q4: How to implement canary deployments using Route 53?
**Answer:**
- **Weighted routing:** 95% to stable, 5% to canary
- **Problem with DNS canary:**
  - Granularity: DNS-level (not request-level). A user gets canary for TTL duration
  - Uneven distribution (DNS caching means some resolvers get all-canary or all-stable)
  - No request-level metrics correlation
- **Better approaches:**
  - ALB weighted target groups (request-level routing, more precise)
  - CloudFront + Lambda@Edge (cookie-based routing)
  - API Gateway canary deployment (stage-level %)
- **Route 53 weighted still useful for:** Region-level canary (deploy to one region first)

### Q5: Design DNS architecture for multi-account AWS organization
**Answer:**
```
Architecture:
  Shared Services Account:
    - Public hosted zone: example.com
    - Delegation: dev.example.com NS → Dev account Route 53
    - Delegation: staging.example.com NS → Staging account Route 53
    - Delegation: api.example.com → handled in shared (production API)
    
  Per-Environment Account:
    - Subdomain hosted zone (delegated)
    - Private hosted zone: internal.{env}.example.com
    - Associated with VPCs in that account
    
  DNS Resolution (Hybrid):
    - Route 53 Resolver in shared services VPC
    - Inbound endpoint: on-prem resolves AWS private zones
    - Outbound rules: shared across organization (RAM)
    - Forward *.corp.internal → on-prem DNS servers
    
  Governance:
    - IAM: Only specific roles can modify production DNS
    - CloudTrail: Audit all DNS changes
    - Config rule: Alert on public hosted zone modifications
```

