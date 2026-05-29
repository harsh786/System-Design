# Elastic Load Balancing - ALB, NLB, GLB Deep Dive

---

## 1. ELB Overview
- **What:** Distributes incoming traffic across multiple targets (EC2, containers, Lambda, IPs)
- **Managed:** AWS handles scaling, HA, health checks, TLS termination
- **Types:** Application Load Balancer (ALB), Network Load Balancer (NLB), Gateway Load Balancer (GLB), Classic (legacy)
- **Scope:** Regional service. Operates across multiple AZs (minimum 2 recommended)

---

## 2. Application Load Balancer (ALB) - Layer 7

### Overview
- **Layer:** 7 (HTTP/HTTPS/gRPC/WebSocket)
- **Target types:** Instance, IP, Lambda
- **Use case:** Web applications, microservices, container-based, REST APIs

### Listeners & Rules
- **Listener:** Checks for connection requests (port + protocol: HTTP 80, HTTPS 443)
- **Rules:** Evaluated in priority order. Conditions + Actions
- **Default rule:** Required (catch-all if no rules match)

### Rule Conditions (matching)
| Condition | Example |
|-----------|---------|
| Host header | api.example.com, *.example.com |
| Path pattern | /api/*, /images/*, /v2/* |
| HTTP method | GET, POST, PUT |
| Source IP | 10.0.0.0/8, specific CIDR |
| Query string | ?platform=mobile |
| HTTP header | X-Custom-Header: value |

### Rule Actions
| Action | Description |
|--------|-------------|
| Forward | Route to target group(s) |
| Redirect | Return 301/302 (HTTP→HTTPS, domain redirect) |
| Fixed response | Return static response (maintenance page, health check) |
| Authenticate (OIDC) | Cognito or any OIDC provider (Google, Okta) |
| Weighted forward | Split traffic across multiple target groups (%) |

### Target Groups
- **Instance:** Register EC2 instances by ID (uses primary private IP)
- **IP:** Register by IP address (private IPs, on-prem via Direct Connect, other VPCs)
- **Lambda:** Invoke Lambda function (ALB handles serialization/deserialization)
- **Cross-zone:** Enabled by default (traffic distributed evenly across all targets in all AZs)

### Health Checks
```yaml
HealthCheckProtocol: HTTP/HTTPS
HealthCheckPath: /health
HealthCheckPort: traffic-port or override
HealthyThreshold: 5 (consecutive successes)
UnhealthyThreshold: 2 (consecutive failures)
Timeout: 5 seconds
Interval: 30 seconds
SuccessCodes: 200-299 (or specific: 200,201)
```
- **Slow start mode:** New targets receive increasing traffic over 30-900 seconds (avoid overwhelming)
- **Deregistration delay:** 300 seconds default (in-flight requests complete before target removed)

### Sticky Sessions (Session Affinity)
- **Duration-based:** AWSALB cookie (ALB-generated), 1 second - 7 days
- **Application-based:** Custom cookie name (app sets cookie, ALB routes by it)
- **Use case:** Stateful applications (shopping cart in memory, WebSocket connections)
- **Problem:** Uneven load distribution, failover loses session

### ALB Advanced Features
- **gRPC support:** HTTP/2 target groups (content-type: application/grpc)
- **WebSocket:** Native support (connection upgrade handled transparently)
- **HTTP/2:** Supported on frontend. Backend: HTTP/1.1 or HTTP/2 (configurable)
- **Desync mitigation:** Protection against HTTP desync attacks (monitor/defensive/strictest)
- **Client IP preservation:** X-Forwarded-For, X-Forwarded-Proto, X-Forwarded-Port headers
- **Request tracing:** X-Amzn-Trace-Id header (for debugging in downstream services)
- **WAF integration:** Attach AWS WAF Web ACL for Layer 7 protection

### ALB Authentication
```
User → ALB → Authenticates via Cognito/OIDC → If valid → Forward to target
  - Cognito User Pool: Built-in user management
  - OIDC: Any provider (Google, Azure AD, Okta, Auth0)
  - Returns: user claims in headers (X-Amzn-Oidc-*)
  - Use case: Add auth to legacy apps without code changes
```

---

## 3. Network Load Balancer (NLB) - Layer 4

### Overview
- **Layer:** 4 (TCP/UDP/TLS)
- **Performance:** Millions of requests/sec, ultra-low latency (< 100 microseconds)
- **Static IPs:** One static IP per AZ (or attach Elastic IP). Crucial for allowlisting
- **Target types:** Instance, IP, ALB (NLB → ALB chaining)
- **Use case:** High performance, TCP/UDP protocols, static IP required, gaming, IoT, financial

### Key Differences from ALB
| Feature | ALB | NLB |
|---------|-----|-----|
| Layer | 7 (HTTP) | 4 (TCP/UDP) |
| Performance | Good | Extreme (millions RPS) |
| Latency | ms | µs (microseconds) |
| IP | Dynamic (use DNS) | Static per AZ |
| TLS termination | Yes | Yes (TLS listener) |
| Client IP | X-Forwarded-For header | Preserved natively (proxy protocol v2 option) |
| Target | Instance, IP, Lambda | Instance, IP, ALB |
| Cross-zone | Default ON (free) | Default OFF (charged if enabled) |
| Health check | HTTP/HTTPS path | TCP, HTTP, HTTPS |
| Security Group | Yes (on ALB) | Optional (new - 2023) |
| WAF | Yes | No (chain with ALB) |
| Sticky | Cookie-based | Source IP/port based |

### NLB Features
- **Proxy Protocol v2:** Passes client connection info (source IP, dest IP, port) to target
- **TLS passthrough:** Forward encrypted TLS without termination (end-to-end encryption)
- **TLS termination:** NLB decrypts TLS, forwards TCP to targets
- **Connection idle timeout:** 350 seconds (TCP), not configurable
- **Cross-zone:** Disabled by default (avoid cross-AZ charges). Enable for even distribution
- **PrivateLink:** Create VPC endpoint service (expose NLB to other VPCs/accounts)

### NLB + ALB (chaining)
```
Internet → NLB (static IP, allowlisted by partners)
  → ALB target (Layer 7 routing, WAF, auth)
    → Target groups (microservices)

Use case: Need static IP + advanced HTTP routing + WAF
```

---

## 4. Gateway Load Balancer (GLB) - Layer 3

### Overview
- **Layer:** 3 (IP packets) with GENEVE encapsulation
- **Purpose:** Deploy, scale, manage third-party virtual appliances
- **Appliances:** Firewalls (Palo Alto, Fortinet), IDS/IPS, deep packet inspection
- **Architecture:** Transparent to applications (bump-in-the-wire)

### How It Works
```
Traffic flow:
  1. User → IGW → Route table sends to GLB endpoint
  2. GLB → GENEVE tunnel → Security appliance (inspect/filter)
  3. Appliance → GENEVE tunnel → GLB → Route table → Application
  
Components:
  - Gateway Load Balancer: Distributes to appliance fleet
  - GLB Endpoint (GWLBE): VPC endpoint where traffic enters/exits
  - Appliance: EC2 instances running security software (target group)
```

### GLB Use Cases
- Centralized firewall inspection across VPCs
- IDS/IPS for all ingress/egress traffic
- DDoS mitigation appliances
- SSL/TLS inspection
- Transparent network monitoring

### GLB Features
- **GENEVE protocol:** Port 6081, preserves original packet headers
- **Health checks:** TCP, HTTP, HTTPS to appliance
- **Cross-zone:** Disabled by default
- **5-tuple hash:** Source IP, Dest IP, Protocol, Source Port, Dest Port (same flow → same appliance)
- **Stickiness:** 3-tuple (Source IP, Dest IP, Protocol) or 5-tuple

---

## 5. TLS/SSL Configuration

### Certificate Management
- **ACM (AWS Certificate Manager):** Free public TLS certificates, auto-renewal
- **Listener certificate:** Default cert + SNI (Server Name Indication) for multiple domains
- **SNI:** Multiple TLS certs on single listener (client indicates hostname in TLS handshake)
- **Security policies:** Control which TLS versions and ciphers allowed
  - TLS 1.2+ minimum recommended (ELBSecurityPolicy-TLS13-1-2-2021-06)
  - Custom policies for compliance requirements

### Certificate on Load Balancers
| | ALB | NLB |
|--|---|---|
| TLS Termination | HTTPS listener | TLS listener |
| TLS Passthrough | N/A (always terminates) | TCP listener (no termination) |
| Client cert (mTLS) | Supported (Trust Store) | Not directly (passthrough to app) |
| ACM cert | Yes | Yes |
| Backend TLS | Optional (target group HTTPS) | Optional (TLS to target) |

---

## 6. Cross-Zone Load Balancing

### What
- **Enabled:** Traffic distributed evenly across ALL targets in ALL AZs
- **Disabled:** Traffic stays within the AZ it entered (each AZ gets equal share from DNS)

### Impact
```
Example: 2 AZs, AZ-A has 2 instances, AZ-B has 8 instances

Cross-zone ON:  Each instance gets 10% of total traffic (even)
Cross-zone OFF: AZ-A instances get 25% each, AZ-B instances get 6.25% each (uneven)
```

### Configuration per LB Type
| LB | Default | Cost |
|----|---------|------|
| ALB | Always ON (target group level: can disable) | Free |
| NLB | OFF | Charged for cross-AZ data transfer |
| GLB | OFF | Charged for cross-AZ data transfer |
| Classic | OFF | Free |

---

## 7. Connection Draining / Deregistration Delay
- **What:** Time to complete in-flight requests before removing target
- **Default:** 300 seconds
- **Range:** 0-3600 seconds
- **Set 0:** For short-lived requests (disable draining, immediately remove)
- **Set higher:** For long-lived connections (WebSocket, file upload)
- During draining: No new connections, existing connections complete or timeout

---

## 8. Auto Scaling Integration

### Target Tracking Scaling
```yaml
ASG Policy:
  TargetTrackingScaling:
    TargetValue: 50  # requests per target
    PredefinedMetric: ALBRequestCountPerTarget
    
    # OR
    TargetValue: 70  # percent CPU
    PredefinedMetric: ASGAverageCPUUtilization
```

### ECS Service + ALB
```yaml
Service:
  LoadBalancers:
    - TargetGroupArn: arn:aws:elasticloadbalancing:...
      ContainerName: web
      ContainerPort: 8080
  DesiredCount: 3
  
Auto Scaling:
  Target tracking: ALBRequestCountPerTarget = 100
  Min: 2, Max: 20
```

---

## 9. Load Balancer Patterns

### Multi-Service Routing (ALB)
```
Single ALB, multiple target groups:
  /api/users/* → User Service (ECS)
  /api/orders/* → Order Service (ECS)
  /api/payments/* → Payment Service (ECS)
  api.example.com → API target group
  www.example.com → Web target group
  admin.example.com → Admin target group (with Cognito auth)
```

### Internal + External Split
```
External ALB (public subnet):
  Internet-facing → public services
  WAF attached, Cognito auth
  
Internal ALB (private subnet):
  Service-to-service communication
  No internet access
  Private DNS (Route 53 private zone)
```

### Blue-Green with ALB
```
ALB Listener Rules:
  Production (weight 100%): → Blue target group
  Canary (weight 0%): → Green target group

Deployment:
  1. Deploy to Green target group
  2. Shift: Blue 90%, Green 10%
  3. Monitor for errors (CloudWatch, X-Ray)
  4. Full shift: Blue 0%, Green 100%
  5. Swap: Green becomes new "Blue"
```

### Global Load Balancing
```
Route 53 (Latency-based routing):
  us-east-1 → Regional ALB → ECS/EKS
  eu-west-1 → Regional ALB → ECS/EKS
  ap-southeast-1 → Regional ALB → ECS/EKS

OR

Global Accelerator:
  Static IPs → Anycast → Nearest edge → Regional ALB
  Instant failover (no DNS TTL wait)
  Better for non-HTTP or when static IPs needed
```

---

## 10. Troubleshooting

### Common Issues
| Issue | Cause | Fix |
|-------|-------|-----|
| 502 Bad Gateway | Target closed connection, response malformed | Check target health, increase idle timeout |
| 503 Service Unavailable | No healthy targets | Fix target health checks, check security groups |
| 504 Gateway Timeout | Target didn't respond in time | Increase target timeout, check target performance |
| Connection timeout | Security group, NACL, or routing issue | Verify SG allows LB → target on correct port |
| Uneven distribution | Cross-zone disabled, sticky sessions | Enable cross-zone, evaluate stickiness need |
| Intermittent 5XX | Target failing health checks, going in/out | Stabilize targets, check resource exhaustion |

### Health Check Debugging
```
Target shows "unhealthy":
1. Can LB reach target? (SG: allow LB SG/CIDR → target port)
2. Is app listening on health check port? (netstat, curl from target itself)
3. Does /health return 200? (app may return 500 during startup)
4. Timeout too short? (increase if app is slow to respond)
5. Check VPC routing (targets must be in routable subnets)
```

---

## 11. Scenario-Based Interview Questions

### Q1: Choose ALB vs NLB for a real-time gaming backend
**Answer:**
- **NLB** for gaming backend:
  - UDP support (game state updates)
  - Ultra-low latency (microseconds vs milliseconds)
  - Static IP (firewall allowlisting for game clients)
  - Millions of concurrent connections
  - TCP keepalive for persistent game sessions
- **ALB if:** HTTP-based game API (login, matchmaking, leaderboards)
- **Hybrid:** NLB for game traffic (UDP/TCP) + ALB for HTTP APIs

### Q2: Millions of IoT devices connecting via TLS. Design load balancing
**Answer:**
```
Architecture:
  NLB (static IP, TLS listener):
    - TLS 1.2+ termination at NLB
    - ACM certificate (auto-renewal)
    - Target: ECS/EKS MQTT brokers
    - Connection idle timeout: 350 seconds (NLB default, enough for MQTT keepalive)
    
  OR for mTLS (device certificates):
    NLB (TCP passthrough) → Application handles TLS + client cert verification
    
  Scaling:
    - NLB: Handles millions of connections natively
    - Target: EKS pods with HPA based on connection count
    
  Why not ALB?
    - MQTT is not HTTP (ALB only supports HTTP/HTTPS/gRPC)
    - Need TCP/TLS level handling
    - Need static IPs for device firmware (can't use DNS easily on constrained devices)
```

### Q3: Migrate from Classic Load Balancer to ALB with zero downtime
**Answer:**
```
Step 1: Create ALB with same listeners and rules
Step 2: Create target groups, register same instances
Step 3: Test ALB directly (use ALB DNS, verify routing)
Step 4: Route 53 weighted routing:
  - CLB DNS: weight 90
  - ALB DNS: weight 10
Step 5: Monitor metrics (error rates, latency)
Step 6: Gradually shift: 50/50, then 90 ALB / 10 CLB
Step 7: 100% ALB, remove CLB
Step 8: Update any hardcoded references, security groups

Key considerations:
  - TCP listeners (CLB) → need NLB (ALB doesn't do TCP)
  - Sticky sessions (CLB cookie) → ALB cookie (different name, test compatibility)
  - Security groups: ALB gets own SG (update target SG to allow ALB SG)
```

### Q4: Application behind ALB experiences 502 errors during deployments
**Answer:**
- **Root cause:** During rolling deployment, old containers stop (close connections), new containers not yet healthy
- **Fix:**
  1. Deregistration delay: 30-60 seconds (allow in-flight to complete)
  2. Health check grace period: Allow new containers time to start (ECS: healthCheckGracePeriodSeconds)
  3. Prestart health check: Container reports healthy only when ready
  4. Rolling update: minHealthyPercent 100, maxPercent 200 (new starts before old stops)
  5. ALB idle timeout: Ensure shorter than container shutdown timeout
- **CodeDeploy Blue/Green:** Even better. Deploy new task set, test, shift traffic atomically

### Q5: Design a load balancing solution for hybrid environment (AWS + on-prem)
**Answer:**
```
Architecture:
  NLB (hybrid target group):
    - Target type: IP
    - Register: AWS instance IPs + on-prem IPs (via Direct Connect/VPN)
    - Health checks: Verify both AWS and on-prem targets
    
  Traffic distribution:
    - Weighted target groups: 70% AWS, 30% on-prem (gradual migration)
    - OR: Use on-prem as failover only (priority target group in ALB)
    
  Connectivity:
    - Direct Connect (1/10 Gbps) for production
    - VPN backup (encrypted, lower bandwidth)
    - On-prem targets: private IPs reachable via DX/VPN
    
  Considerations:
    - Latency: On-prem targets have higher latency (DX adds 1-5ms)
    - Cross-zone: Disable (to avoid unnecessary cross-network traffic)
    - Health check interval: Increase timeout for on-prem (network jitter)
    - Monitoring: Track target response time per target group
```

