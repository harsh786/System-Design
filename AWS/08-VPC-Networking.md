# AWS VPC & Networking - Complete Guide

## 1. VPC Fundamentals

### What is a VPC?

A **Virtual Private Cloud (VPC)** is a logically isolated virtual network within AWS where you launch AWS resources. It gives you complete control over:

- IP address range (CIDR block)
- Subnets (public/private)
- Route tables
- Network gateways
- Security settings (Security Groups, NACLs)

Think of it as your own private data center in the cloud.

### CIDR Blocks

**CIDR (Classless Inter-Domain Routing)** defines the IP address range for your VPC.

| CIDR | Subnet Mask | Total IPs | Usable IPs |
|------|-------------|-----------|------------|
| /16 | 255.255.0.0 | 65,536 | 65,531 |
| /20 | 255.255.240.0 | 4,096 | 4,091 |
| /24 | 255.255.255.0 | 256 | 251 |
| /28 | 255.255.255.240 | 16 | 11 |

**RFC 1918 Private Ranges (recommended):**

```
10.0.0.0/8       → 10.0.0.0 – 10.255.255.255   (16M addresses)
172.16.0.0/12    → 172.16.0.0 – 172.31.255.255  (1M addresses)
192.168.0.0/16   → 192.168.0.0 – 192.168.255.255 (65K addresses)
```

**Rules:**
- Minimum: /28 (16 IPs)
- Maximum: /16 (65,536 IPs)
- Cannot be changed after VPC creation (but can add secondary CIDRs)
- Must not overlap with other VPCs you plan to peer with

### Default VPC vs Custom VPC

| Feature | Default VPC | Custom VPC |
|---------|-------------|------------|
| Created by | AWS automatically (one per region) | You |
| CIDR | 172.31.0.0/16 | You choose |
| Subnets | One public subnet per AZ | You define |
| Internet access | Yes (IGW + public IPs) | You configure |
| Use case | Quick testing, learning | Production workloads |
| DNS hostnames | Enabled | Disabled by default |

### VPC Components Overview

```
VPC
├── Subnets (public/private, per AZ)
├── Route Tables (main + custom)
├── Internet Gateway (IGW)
├── NAT Gateway / NAT Instance
├── Security Groups (instance-level firewall)
├── Network ACLs (subnet-level firewall)
├── VPC Endpoints (private access to AWS services)
├── VPN Gateway / Direct Connect
├── VPC Peering / Transit Gateway
├── Flow Logs
└── DNS settings
```

---

## 2. Subnets

### Public vs Private Subnets

| Aspect | Public Subnet | Private Subnet |
|--------|--------------|----------------|
| Internet access | Direct (via IGW) | No direct access |
| Route table | Has route to IGW (0.0.0.0/0 → igw-xxx) | No route to IGW |
| Use case | Web servers, bastion hosts, ALBs | Databases, app servers, internal services |
| Public IP | Auto-assigned or Elastic IP | No public IP needed |
| Outbound internet | Via IGW | Via NAT Gateway in public subnet |

### Reserved IPs per Subnet (5 IPs)

For a subnet with CIDR `10.0.1.0/24`:

| IP | Reserved For |
|----|-------------|
| 10.0.1.0 | Network address |
| 10.0.1.1 | VPC router |
| 10.0.1.2 | AWS DNS server |
| 10.0.1.3 | Reserved for future use |
| 10.0.1.255 | Broadcast (not supported but reserved) |

**Usable IPs = Total IPs - 5**

### Availability Zone Mapping

- Each subnet resides in exactly **one** Availability Zone
- Subnets cannot span multiple AZs
- For high availability, create subnets in multiple AZs

```
VPC: 10.0.0.0/16
├── AZ-a
│   ├── Public Subnet:  10.0.1.0/24  (251 usable IPs)
│   └── Private Subnet: 10.0.2.0/24  (251 usable IPs)
├── AZ-b
│   ├── Public Subnet:  10.0.3.0/24
│   └── Private Subnet: 10.0.4.0/24
└── AZ-c
    ├── Public Subnet:  10.0.5.0/24
    └── Private Subnet: 10.0.6.0/24
```

### Subnet Sizing Best Practices

1. **Plan for growth** – use /20 or larger for production subnets
2. **Consistent sizing** – same CIDR size across AZs for simplicity
3. **Leave room** – don't allocate the entire VPC CIDR to subnets immediately
4. **Tiered approach** – separate subnets for web, app, data, and management tiers
5. **Consider ENI usage** – Lambda in VPC, EKS pods, ECS tasks all consume IPs

**Example production layout (10.0.0.0/16):**

```
Public:   10.0.0.0/20, 10.0.16.0/20, 10.0.32.0/20    (3 AZs × 4091 IPs)
Private:  10.0.48.0/19, 10.0.80.0/19, 10.0.112.0/19   (3 AZs × 8187 IPs)
Data:     10.0.144.0/20, 10.0.160.0/20, 10.0.176.0/20  (3 AZs × 4091 IPs)
Spare:    10.0.192.0/18                                  (reserved for future)
```

---

## 3. Route Tables

### Main Route Table vs Custom Route Tables

- **Main route table**: automatically created with VPC, applies to subnets not explicitly associated with a custom table
- **Custom route table**: explicitly created and associated with specific subnets
- Best practice: leave main route table with only local route; use custom tables for all subnets

### Route Priority

- **Most specific route wins** (longest prefix match)
- Example: if you have `0.0.0.0/0 → NAT` and `10.1.0.0/16 → Peering`, traffic to 10.1.0.5 goes via peering

### Local Route

```
Destination: 10.0.0.0/16  Target: local
```

- Always present, cannot be removed
- Enables communication within the VPC
- Highest priority for VPC CIDR traffic

### Route Targets

| Destination | Target | Use Case |
|------------|--------|----------|
| 0.0.0.0/0 | igw-xxx | Internet access (public subnet) |
| 0.0.0.0/0 | nat-xxx | Internet access (private subnet) |
| 10.1.0.0/16 | pcx-xxx | VPC Peering |
| 10.0.0.0/8 | tgw-xxx | Transit Gateway |
| pl-xxx (S3 prefix list) | vpce-xxx | Gateway Endpoint |
| 192.168.0.0/16 | vgw-xxx | VPN Gateway |
| 0.0.0.0/0 | eni-xxx | Network appliance |

**Example Public Subnet Route Table:**

```
Destination      Target       Status
10.0.0.0/16      local        active
0.0.0.0/0        igw-abc123   active
```

**Example Private Subnet Route Table:**

```
Destination      Target        Status
10.0.0.0/16      local         active
0.0.0.0/0        nat-xyz789    active
10.1.0.0/16      pcx-peer01    active
```

---

## 4. Internet Connectivity

### Internet Gateway (IGW)

- **One per VPC** (horizontally scaled, redundant, HA by design)
- No bandwidth constraints
- Performs NAT for instances with public IPv4 addresses
- No single point of failure
- **Free** (no hourly charge, only data transfer costs)

**To make a subnet public:**
1. Create and attach IGW to VPC
2. Add route: `0.0.0.0/0 → igw-xxx` in subnet's route table
3. Ensure instances have public IP or Elastic IP
4. Security Group allows inbound traffic

### NAT Gateway

- **Managed service** by AWS (no patching, HA within a single AZ)
- Placed in a **public subnet**
- Requires an **Elastic IP**
- Allows private subnet instances to reach the internet (outbound only)
- Scales automatically up to **100 Gbps**
- **Per AZ deployment** – for HA, deploy one NAT Gateway per AZ

**Pricing:**
- $0.045/hour (~$32/month) per NAT Gateway
- $0.045/GB data processed
- For HA: multiply by number of AZs

**Cost optimization:**
- Use NAT Gateway in one AZ for non-critical workloads (accept cross-AZ traffic cost)
- Use VPC endpoints for S3/DynamoDB to avoid NAT charges
- Consider NAT Instance for dev/test environments

### NAT Instance (Legacy)

| Feature | NAT Gateway | NAT Instance |
|---------|-------------|--------------|
| Managed | Yes | No (you manage) |
| Availability | HA within AZ | Manual failover |
| Bandwidth | Up to 100 Gbps | Depends on instance type |
| Maintenance | AWS handles | You patch/update |
| Cost | ~$32/month + data | Instance cost (can be t3.micro) |
| Security Groups | No | Yes |
| Source/Dest check | N/A | Must disable |
| Bastion host | No | Can double as bastion |

### Egress-Only Internet Gateway

- **IPv6 only** – equivalent of NAT Gateway for IPv6
- Allows outbound IPv6 traffic, blocks inbound initiated connections
- Stateful (return traffic is allowed)
- Free (no hourly charge)

---

## 5. Security

### Security Groups (SGs)

- **Stateful** – if inbound is allowed, outbound response is automatically allowed
- Operates at **instance/ENI level**
- **Allow rules only** (no deny rules)
- Default: all outbound allowed, all inbound denied
- Can reference other security groups (powerful for tiered architectures)
- Up to 5 SGs per ENI
- Evaluated as a whole (all rules aggregated)

**Example:**

```
Web Server SG (Inbound):
  HTTP  (80)   from 0.0.0.0/0
  HTTPS (443)  from 0.0.0.0/0
  SSH   (22)   from Bastion-SG

App Server SG (Inbound):
  Custom (8080) from Web-Server-SG

Database SG (Inbound):
  MySQL (3306) from App-Server-SG
```

### Network ACLs (NACLs)

- **Stateless** – must define both inbound and outbound rules
- Operates at **subnet level**
- **Allow AND deny rules**
- Rules evaluated in **number order** (lowest number first)
- Default NACL: allows all inbound/outbound
- Custom NACL: denies all by default
- One NACL per subnet (but one NACL can be associated with multiple subnets)

**Example:**

```
Inbound Rules:
Rule# | Type  | Port  | Source       | Allow/Deny
100   | HTTP  | 80    | 0.0.0.0/0   | ALLOW
110   | HTTPS | 443   | 0.0.0.0/0   | ALLOW
120   | SSH   | 22    | 10.0.0.0/16 | ALLOW
130   | Custom| 1024-65535 | 0.0.0.0/0 | ALLOW (ephemeral ports)
*     | All   | All   | 0.0.0.0/0   | DENY

Outbound Rules:
Rule# | Type  | Port  | Dest         | Allow/Deny
100   | HTTP  | 80    | 0.0.0.0/0   | ALLOW
110   | HTTPS | 443   | 0.0.0.0/0   | ALLOW
120   | Custom| 1024-65535 | 0.0.0.0/0 | ALLOW (ephemeral ports)
*     | All   | All   | 0.0.0.0/0   | DENY
```

### SG vs NACL Comparison

| Feature | Security Group | NACL |
|---------|---------------|------|
| Level | Instance (ENI) | Subnet |
| Statefulness | Stateful | Stateless |
| Rules | Allow only | Allow + Deny |
| Evaluation | All rules evaluated | Rules in order (first match) |
| Default | Deny all inbound | Allow all (default NACL) |
| Association | Multiple SGs per instance | One NACL per subnet |
| Rule target | IPs or other SGs | IPs/CIDRs only |
| Return traffic | Automatically allowed | Must explicitly allow |

### Layered Security Approach

```
Internet
    │
    ▼
┌─── NACL (subnet boundary) ───────────────┐
│   ┌─── Security Group (instance) ────┐   │
│   │                                   │   │
│   │   EC2 Instance / ENI              │   │
│   │                                   │   │
│   └───────────────────────────────────┘   │
└───────────────────────────────────────────┘
```

- NACL: broad subnet-level filtering (block known bad IPs, rate limiting)
- SG: fine-grained instance-level access control
- OS firewall (iptables): application-specific rules

### VPC Flow Logs

- Capture information about IP traffic going to/from network interfaces
- Can be created at: **VPC, Subnet, or ENI level**
- Published to: **CloudWatch Logs** or **S3**
- Includes: source/dest IPs, ports, protocol, packets, bytes, action (ACCEPT/REJECT)
- Does NOT capture: DNS traffic to Route 53 Resolver, DHCP, metadata (169.254.169.254), license activation traffic

**Flow Log Record Format:**

```
<version> <account-id> <interface-id> <srcaddr> <dstaddr> <srcport> <dstport> <protocol> <packets> <bytes> <start> <end> <action> <log-status>
```

**Analysis with Athena:**

```sql
SELECT srcaddr, dstaddr, dstport, action, COUNT(*) as count
FROM vpc_flow_logs
WHERE action = 'REJECT'
GROUP BY srcaddr, dstaddr, dstport, action
ORDER BY count DESC
LIMIT 20;
```

---

## 6. VPC Connectivity

### VPC Peering

- **Point-to-point** connection between two VPCs
- Works **cross-region** and **cross-account**
- **Non-transitive** – if A peers with B and B peers with C, A cannot reach C through B
- Uses AWS backbone (not public internet)
- No single point of failure, no bandwidth bottleneck
- **No overlapping CIDR blocks** allowed
- Route table entries required on both sides
- Security groups can reference peered VPC SGs (same region only)

**Limitations:**
- Max 125 active peering connections per VPC
- Cannot have more than one peering between same two VPCs
- DNS resolution must be enabled explicitly for cross-account

### Transit Gateway (TGW)

- **Hub-and-spoke** model – single gateway connecting thousands of VPCs and on-prem networks
- **Transitive routing** – VPCs connected to TGW can communicate with each other
- Supports: VPC attachments, VPN attachments, Direct Connect Gateway, peering with other TGWs
- **Regional** resource (but supports cross-region peering)
- Route tables within TGW for segmentation
- Scales to **50 Gbps per VPC attachment** (burst)
- Supports **multicast**

**When to use TGW vs VPC Peering:**

| Criteria | VPC Peering | Transit Gateway |
|----------|-------------|-----------------|
| # of VPCs | Few (< 10) | Many (10+) |
| Routing | Simple point-to-point | Complex, centralized |
| Cost | Free (data transfer only) | Per attachment + per GB |
| Transitivity | No | Yes |
| Bandwidth | No limit | 50 Gbps per attachment |
| On-prem | Not directly | VPN/DX integration |

### VPC Endpoints (AWS PrivateLink)

**Interface Endpoint:**
- Creates an **ENI with private IP** in your subnet
- Powered by **AWS PrivateLink**
- Supports most AWS services (SQS, SNS, KMS, Secrets Manager, API Gateway, etc.)
- Costs: ~$0.01/hour per AZ + $0.01/GB processed
- DNS entry created (can override public service endpoint)
- Security Group controlled

**Gateway Endpoint:**
- A **route table entry** pointing to the service
- **S3 and DynamoDB only**
- **Free** (no hourly or data processing charges)
- Specified in route table using prefix list
- VPC endpoint policy for access control
- Cannot be extended out of VPC (no peering, VPN, TGW access)

**Gateway Load Balancer Endpoint:**
- For routing traffic through third-party virtual appliances
- Firewalls, IDS/IPS, deep packet inspection
- Uses GENEVE encapsulation

### VPN

**Site-to-Site VPN:**
- IPsec encrypted tunnel over public internet
- AWS side: Virtual Private Gateway (VGW) or Transit Gateway
- Customer side: Customer Gateway (CGW) device
- Two tunnels per connection for HA
- Supports BGP (dynamic) or static routing
- Up to 1.25 Gbps per tunnel
- Quick to set up (minutes vs weeks for Direct Connect)

**Client VPN:**
- OpenVPN-based managed service
- Remote user access to AWS and on-prem resources
- Supports Active Directory / SAML authentication
- Split-tunnel or full-tunnel modes
- Per-connection pricing

**CloudHub:**
- Multiple Site-to-Site VPN connections to same VGW
- Enables branch-to-branch communication via AWS
- Hub-and-spoke model for multiple remote offices
- Low-cost option for branch connectivity

### Direct Connect (DX)

- **Dedicated physical connection** from on-prem to AWS
- Speeds: 1 Gbps, 10 Gbps, 100 Gbps (dedicated) or 50 Mbps to 10 Gbps (hosted)
- Consistent latency, bypasses public internet
- Supports 802.1Q VLANs
- Takes **weeks to months** to establish

**Connection Types:**

| Feature | Dedicated | Hosted |
|---------|-----------|--------|
| Bandwidth | 1/10/100 Gbps | 50 Mbps – 10 Gbps |
| Physical port | You own | Partner owns |
| VLANs | Multiple VIFs | Typically one VIF |
| Lead time | Weeks–months | Days–weeks |

**Virtual Interfaces (VIFs):**

| VIF Type | Purpose | Connects To |
|----------|---------|-------------|
| Public VIF | Access AWS public services (S3, DynamoDB) | AWS public endpoints |
| Private VIF | Access VPC resources | VGW or DX Gateway |
| Transit VIF | Access VPCs via Transit Gateway | Transit Gateway |

**Direct Connect Gateway:**
- Connect DX to multiple VPCs in **different regions**
- Single DX connection → DX Gateway → multiple VGWs or TGWs
- Global resource (not region-specific)

**LAG (Link Aggregation Group):**
- Bundle multiple DX connections (same speed) into one logical connection
- Active-active using LACP
- All connections must be same bandwidth and terminate at same DX location
- Max 4 connections per LAG (or 2 for 100 Gbps)

---

## 7. DNS and Route 53

### VPC DNS Settings

- **enableDnsSupport** (default: true) – enables DNS resolution in VPC via AWS-provided DNS server (VPC CIDR + 2)
- **enableDnsHostnames** (default: false for custom VPC) – assigns public DNS hostnames to instances with public IPs
- Both must be enabled for VPC Peering DNS resolution and Private Hosted Zones

### Route 53 Overview

- AWS managed DNS service (100% SLA)
- Domain registrar + DNS hosting
- Supports both **public** and **private** hosted zones

**Record Types:**

| Record | Purpose | Example |
|--------|---------|---------|
| A | IPv4 address | example.com → 1.2.3.4 |
| AAAA | IPv6 address | example.com → 2001:db8::1 |
| CNAME | Canonical name (alias to another domain) | www.example.com → example.com |
| Alias | AWS-specific, maps to AWS resources | example.com → d123.cloudfront.net |
| MX | Mail exchange | mail.example.com |
| NS | Name server | ns-123.awsdns-45.com |
| SOA | Start of authority | Admin info |
| TXT | Text record | Verification, SPF |
| SRV | Service locator | _sip._tcp.example.com |

**Alias vs CNAME:**

| Feature | Alias | CNAME |
|---------|-------|-------|
| Zone apex (naked domain) | Yes | No |
| Cost | Free queries | Charged |
| Targets | AWS resources only | Any domain |
| TTL | Set by AWS | You control |
| Health checks | Yes | Yes |

### Routing Policies

| Policy | Description | Use Case |
|--------|-------------|----------|
| Simple | Single resource, no health check | Single server |
| Weighted | Split traffic by percentage | A/B testing, gradual migration |
| Latency | Route to lowest-latency region | Global applications |
| Failover | Active-passive with health checks | Disaster recovery |
| Geolocation | Route by user's geographic location | Content localization, compliance |
| Geoproximity | Route by geographic distance + bias | Shift traffic between regions |
| Multi-Value | Multiple healthy resources (up to 8) | Simple load balancing with health checks |
| IP-based | Route based on client IP CIDR | ISP-specific routing |

### Health Checks

- Monitor endpoints (IP or domain), other health checks, or CloudWatch alarms
- Interval: 30s (standard) or 10s (fast, extra cost)
- Threshold: configurable consecutive failures (default 3)
- Types: HTTP, HTTPS, TCP
- String matching: check response body (first 5120 bytes)
- Calculated health checks: combine multiple checks (AND/OR)

### Route 53 Resolver

- **Inbound Endpoint**: allows on-prem DNS to resolve AWS private hosted zones
- **Outbound Endpoint**: allows VPC resources to resolve on-prem DNS
- **Resolver Rules**: forward specific domains to target DNS servers
- Supports hybrid DNS resolution patterns

```
On-prem DNS ──→ Inbound Endpoint ──→ Route 53 Resolver ──→ Private Hosted Zone
                                                                     
VPC Resources ──→ Outbound Endpoint ──→ On-prem DNS servers (for corp.internal)
```

---

## 8. Load Balancing

### Application Load Balancer (ALB)

- **Layer 7** (HTTP/HTTPS/gRPC/WebSocket)
- Content-based routing: path, host header, HTTP headers, query strings, source IP
- Native support for containers (ECS, EKS) and Lambda
- Supports HTTP/2, WebSocket, gRPC
- Sticky sessions (cookie-based)
- Authentication integration (Cognito, OIDC)
- Redirects and fixed responses
- WAF integration
- Slow start mode for targets

**Routing examples:**
```
example.com/api/*       → API target group
example.com/images/*    → Image service target group
api.example.com         → API target group (host-based)
Header: X-Custom=mobile → Mobile target group
```

### Network Load Balancer (NLB)

- **Layer 4** (TCP/UDP/TLS)
- Ultra-low latency (~100μs vs ~400ms for ALB)
- **Static IP per AZ** (or Elastic IP)
- Handles millions of requests per second
- Preserves source IP address
- Supports long-lived TCP connections (IoT, gaming, WebSocket)
- Health checks: TCP, HTTP, HTTPS
- Can front an ALB (for static IPs + L7 routing)
- No Security Groups on NLB itself (use target SGs)

### Gateway Load Balancer (GLB)

- **Layer 3** (IP packets)
- Transparent network gateway + load balancer
- GENEVE encapsulation (port 6081)
- Use case: deploy third-party virtual appliances (firewalls, IDS/IPS)
- Single entry/exit for all traffic
- Scales with demand

```
Internet → IGW → GLB Endpoint → GLB → Appliance fleet → GLB → Application
```

### Classic Load Balancer (CLB)

- Legacy (Layer 4 + some Layer 7)
- No path-based routing
- No host-based routing
- Limited to EC2-Classic and VPC
- **Avoid for new deployments**

### Target Types

| Target Type | ALB | NLB | GLB |
|-------------|-----|-----|-----|
| Instance | ✓ | ✓ | ✓ |
| IP address | ✓ | ✓ | ✓ |
| Lambda | ✓ | ✗ | ✗ |
| ALB | ✗ | ✓ | ✗ |

### Cross-Zone Load Balancing

- **Enabled**: distributes traffic evenly across all targets in all AZs
- **Disabled**: traffic stays within the AZ of the load balancer node
- ALB: always enabled (free)
- NLB: disabled by default (charges for cross-AZ data if enabled)
- GLB: disabled by default

### Sticky Sessions (Session Affinity)

- Binds a user's session to a specific target
- ALB: application-based cookie (custom or AWSALB) or duration-based
- CLB: duration-based only
- NLB: source IP affinity
- Consider impact on even distribution

### Connection Draining (Deregistration Delay)

- Time to complete in-flight requests before deregistering a target
- Default: 300 seconds
- Range: 0–3600 seconds
- Set to 0 for short-lived requests

### SSL/TLS

- **Termination**: decrypt at load balancer, forward unencrypted to targets (offloads CPU)
- **Pass-through** (NLB only): forward encrypted traffic to targets
- **End-to-end encryption**: re-encrypt between LB and targets
- **SNI (Server Name Indication)**: multiple TLS certs on one listener, route to correct target group
- SSL policies: predefined sets of ciphers and protocols (e.g., ELBSecurityPolicy-TLS13-1-2-2021-06)
- ACM (AWS Certificate Manager) integration for free public certificates

---

## 9. Advanced Networking

### IPv6 in VPC

- **Dual-stack**: instances get both IPv4 and IPv6 addresses
- IPv6 CIDR assigned by AWS (/56 per VPC, /64 per subnet)
- All IPv6 addresses are publicly routable (no NAT needed)
- Use **Egress-Only IGW** for outbound-only IPv6 internet access
- Security Groups and NACLs support IPv6 rules

### VPC Sharing (AWS RAM)

- Share subnets across accounts within an AWS Organization
- Owner account manages VPC, subnets, route tables, gateways
- Participant accounts launch resources in shared subnets
- Reduces VPC count and IP address waste
- Resources in shared subnet can communicate via private IPs

### Multiple CIDR Blocks

- Add up to **5 secondary IPv4 CIDR blocks** per VPC (adjustable via quota)
- Cannot overlap with existing CIDRs or peered VPC CIDRs
- Useful when running out of IPs
- New CIDRs can be from different RFC 1918 ranges

### AWS Network Firewall

- Managed **stateful and stateless** firewall for VPC
- Intrusion Detection/Prevention (IDS/IPS) with Suricata-compatible rules
- Domain name filtering (allow/deny list)
- Protocol detection and filtering
- Centralized deployment via Transit Gateway or distributed per-VPC
- Logs to S3, CloudWatch, Kinesis Firehose
- Integrates with AWS Firewall Manager for multi-account management

### Traffic Mirroring

- Copy network traffic from ENIs for analysis
- Filter by protocol, port, direction
- Send to NLB or another ENI (running analysis tools: Suricata, Zeek)
- Use cases: threat detection, content inspection, troubleshooting
- Does not affect source instance performance significantly

### VPC Reachability Analyzer

- Network diagnostics tool – verify connectivity **without sending traffic**
- Analyzes route tables, SGs, NACLs, peering connections
- Identifies the failing component in the path
- Source/destination can be: ENI, IGW, VPN Gateway, Transit Gateway, VPC Endpoint

### VPC Lattice

- Application-layer service networking (L7 service-to-service)
- Handles service discovery, connectivity, traffic management, and access control
- Works across VPCs and accounts
- Weighted routing for deployments
- Built-in authentication and authorization
- Alternative to service mesh for simpler use cases

---

## 10. Scenario-Based Interview Questions

### Q1: Design VPC architecture for a 3-tier web application

**Answer:**

```
VPC: 10.0.0.0/16 (3 AZs for HA)

Public Subnets (3):
  - ALB, NAT Gateways, Bastion Host
  - 10.0.1.0/24, 10.0.2.0/24, 10.0.3.0/24

Private App Subnets (3):
  - Application servers (EC2/ECS/EKS)
  - 10.0.11.0/24, 10.0.12.0/24, 10.0.13.0/24

Private Data Subnets (3):
  - RDS (Multi-AZ), ElastiCache
  - 10.0.21.0/24, 10.0.22.0/24, 10.0.23.0/24

Security:
  - ALB SG: 80/443 from 0.0.0.0/0
  - App SG: 8080 from ALB-SG only
  - DB SG: 3306 from App-SG only
  - Bastion SG: 22 from corporate IP only
  - NACLs: block known malicious CIDRs

Connectivity:
  - IGW for public subnets
  - NAT Gateway per AZ for private subnet internet access
  - S3 Gateway Endpoint (free, avoid NAT charges)
  - VPC Flow Logs enabled
```

### Q2: Connect 100 VPCs with on-prem – what solution?

**Answer:** AWS Transit Gateway

- Hub-and-spoke topology
- Single Transit Gateway supports up to 5,000 attachments
- Attach all 100 VPCs + VPN/Direct Connect for on-prem
- Use TGW route tables for segmentation (e.g., production vs dev)
- Enable route propagation for VPN/DX connections
- For multi-region: TGW peering between regions
- Cost: per-attachment hourly + per-GB data processing

VPC Peering is impractical: would require 4,950 peering connections (n*(n-1)/2) and is non-transitive.

### Q3: Private subnet needs internet for package updates – how?

**Answer:**

1. **NAT Gateway** (recommended):
   - Deploy NAT Gateway in public subnet
   - Add route in private subnet: `0.0.0.0/0 → nat-gw-xxx`
   - Attach Elastic IP to NAT Gateway
   - One per AZ for HA

2. **Alternatives:**
   - NAT Instance (cheaper, less reliable)
   - VPC Endpoint for specific services (S3, ECR)
   - AWS Systems Manager Session Manager (no internet needed for management)
   - Squid proxy in public subnet (more control, whitelist URLs)

### Q4: Troubleshoot EC2 instance not reachable from internet

**Answer – systematic checklist:**

1. **Instance**: Is it running? Does it have a public IP or Elastic IP?
2. **Subnet**: Is it in a public subnet? (Route table has `0.0.0.0/0 → igw-xxx`)
3. **Route table**: Is the route table associated with the correct subnet?
4. **IGW**: Is Internet Gateway attached to the VPC?
5. **Security Group**: Does inbound allow traffic on the required port from the source?
6. **NACL**: Does subnet NACL allow inbound AND outbound (ephemeral ports) traffic?
7. **OS firewall**: Is the service running and OS firewall (iptables/Windows Firewall) allows it?
8. **Elastic IP**: If using EIP, is it associated with the correct ENI?
9. **VPC Flow Logs**: Check for REJECT entries to identify where traffic is blocked

### Q5: Design hybrid DNS resolution (on-prem + AWS)

**Answer:**

```
Requirements:
- On-prem resources resolve AWS private hosted zones
- AWS resources resolve on-prem DNS domains

Solution:
1. Route 53 Resolver Inbound Endpoint (in 2 AZs)
   - On-prem DNS servers forward *.aws.company.com to inbound endpoint IPs
   
2. Route 53 Resolver Outbound Endpoint (in 2 AZs)
   - Create Resolver Rules: forward *.corp.internal to on-prem DNS IPs
   
3. Private Hosted Zone associated with VPC

4. Connectivity: Direct Connect or Site-to-Site VPN

5. DNS flow:
   EC2 → Route 53 Resolver → check rules → forward to on-prem DNS (for corp.internal)
   On-prem → forward to Inbound Endpoint → Route 53 → Private Hosted Zone
```

### Q6: VPC Peering vs Transit Gateway – when to use which?

**Answer:**

**Use VPC Peering when:**
- Few VPCs (< 10) with simple connectivity
- Need lowest latency (no hop through TGW)
- Cost-sensitive (no per-attachment fee)
- No need for transitive routing
- Bandwidth-intensive workloads (no per-GB TGW processing fee)

**Use Transit Gateway when:**
- Many VPCs (10+)
- Need transitive routing
- Centralized network management
- Connecting VPN/Direct Connect to multiple VPCs
- Need network segmentation via multiple route tables
- Need multicast support
- Centralized traffic inspection (Network Firewall)

### Q7: How to restrict S3 access to only from VPC?

**Answer:**

1. **S3 Gateway Endpoint** in VPC route table
2. **S3 Bucket Policy** with VPC/endpoint condition:

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Deny",
    "Principal": "*",
    "Action": "s3:*",
    "Resource": ["arn:aws:s3:::my-bucket", "arn:aws:s3:::my-bucket/*"],
    "Condition": {
      "StringNotEquals": {
        "aws:sourceVpce": "vpce-abc123"
      }
    }
  }]
}
```

Or restrict by VPC:
```json
"Condition": {
  "StringNotEquals": {
    "aws:sourceVpc": "vpc-xyz789"
  }
}
```

3. **VPC Endpoint Policy** to restrict which buckets can be accessed from the VPC

### Q8: Design multi-region network architecture

**Answer:**

```
Region A (Primary)                 Region B (DR)
┌─────────────────┐              ┌─────────────────┐
│  VPCs (Prod)    │              │  VPCs (Prod)    │
│       │         │              │       │         │
│  Transit GW A   │──TGW Peer──│  Transit GW B   │
│       │         │              │       │         │
│  DX Gateway     │              │  DX Gateway     │
└───────┼─────────┘              └───────┼─────────┘
        │                                │
   Direct Connect                   Direct Connect
   (Primary)                        (Backup)
        │                                │
   ┌────┴────────────────────────────────┴────┐
   │            On-Premises DC                  │
   └────────────────────────────────────────────┘

Key decisions:
- TGW Peering for cross-region VPC-to-VPC
- Direct Connect at both regions (resilience)
- Route 53 latency/failover routing for traffic steering
- Shared services VPC (DNS, monitoring) in each region
- Network Firewall for centralized inspection
```

### Q9: NLB vs ALB – detailed decision criteria

**Answer:**

| Criteria | Choose ALB | Choose NLB |
|----------|-----------|-----------|
| Protocol | HTTP/HTTPS/gRPC | TCP/UDP/TLS |
| Latency | Acceptable (~ms) | Ultra-low required (~μs) |
| IP type | Dynamic | Static IP per AZ needed |
| Routing | Path/host/header-based | Port-based only |
| Targets | Instances, IPs, Lambda | Instances, IPs, ALB |
| Source IP | X-Forwarded-For header | Preserved natively |
| WebSocket | Native support | Native support |
| TLS | Terminates | Terminates or passthrough |
| WAF | Yes (integrates) | No |
| Auth | Cognito/OIDC built-in | No |
| Scale | Millions of RPS | Millions of RPS |
| Use case | Web apps, microservices, APIs | IoT, gaming, VoIP, financial trading |
| Pricing | Per LCU (complex) | Per NLCU (simpler) |

### Q10: How to achieve 99.99% availability for network connectivity?

**Answer:**

1. **Multi-AZ deployment** – resources across 3+ AZs
2. **Redundant NAT Gateways** – one per AZ
3. **Direct Connect resilience:**
   - Two DX connections at different DX locations
   - Plus Site-to-Site VPN as backup (over internet)
   - Maximum resilience: 4 connections (2 locations × 2 connections)
4. **Multi-region** – active-active or active-passive with Route 53 failover
5. **Transit Gateway** – redundant attachments
6. **Health checks** – Route 53 health checks + automated failover
7. **Load balancers** – cross-zone enabled, multi-AZ
8. **No single points of failure** – no single NAT, no single path

### Q11: Troubleshoot intermittent connectivity between VPCs

**Answer:**

1. **Check VPC Peering/TGW status** – is the connection active?
2. **Route tables** – verify routes exist in BOTH VPCs (peering is not automatic)
3. **Security Groups** – verify rules allow traffic on required ports from peer CIDR
4. **NACLs** – check both inbound AND outbound (ephemeral ports!) in both subnets
5. **CIDR overlap** – ensure no overlapping ranges
6. **Bandwidth** – check if hitting TGW/peering bandwidth limits
7. **VPC Flow Logs** – look for REJECT entries with timestamps matching issues
8. **DNS resolution** – if using hostnames, ensure DNS resolution across peering is enabled
9. **MTU issues** – jumbo frames (9001) may not be supported across peering; test with lower MTU
10. **Asymmetric routing** – in complex topologies, return path may differ

### Q12: Design zero-trust network in AWS

**Answer:**

```
Principles:
- Never trust, always verify
- Least privilege access
- Micro-segmentation
- Continuous monitoring

Implementation:
1. Micro-segmentation:
   - One Security Group per workload/service (not per tier)
   - SG rules reference other SGs (not broad CIDRs)
   - Deny all, explicitly allow only required flows

2. Network isolation:
   - Separate VPCs per environment/trust boundary
   - Private subnets for everything (no public except LBs)
   - VPC Endpoints for AWS service access (no internet)

3. Access control:
   - AWS Verified Access for application access (no VPN needed)
   - IAM policies for service-to-service auth
   - mTLS between services (App Mesh / service mesh)
   - PrivateLink for cross-account service exposure

4. Inspection:
   - Network Firewall for IDS/IPS
   - Traffic Mirroring for deep packet inspection
   - VPC Flow Logs → Security Lake → analytics

5. Monitoring:
   - GuardDuty for threat detection
   - CloudTrail for API activity
   - Config Rules for compliance
   - Security Hub for centralized findings
```

### Q13: How does traffic flow when EC2 in private subnet accesses the internet?

**Answer:**

```
Step-by-step:
1. EC2 (10.0.2.5) sends packet to destination (e.g., 52.1.2.3)
2. VPC router checks private subnet route table
3. Matches 0.0.0.0/0 → nat-gateway-xxx (in public subnet)
4. NAT Gateway replaces source IP (10.0.2.5) with its Elastic IP (54.x.x.x)
5. NAT Gateway sends via public subnet route table
6. Matches 0.0.0.0/0 → igw-xxx
7. IGW sends packet to internet
8. Response returns to NAT Gateway's Elastic IP
9. NAT Gateway performs reverse NAT → forwards to 10.0.2.5
10. Packet arrives at EC2
```

### Q14: How to expose internal service to another AWS account privately?

**Answer:** AWS PrivateLink

```
Provider Account:
1. Service behind NLB (Network Load Balancer)
2. Create VPC Endpoint Service pointing to NLB
3. Whitelist consumer account IDs
4. Accept connection requests

Consumer Account:
1. Create Interface VPC Endpoint for the service
2. Gets private IP in their subnet
3. Access service via endpoint DNS name
4. Traffic stays on AWS network (never public internet)

Benefits:
- No VPC peering needed
- No CIDR overlap issues
- Unidirectional (consumer → provider only)
- Provider controls who can connect
- Scales independently
```

### Q15: What happens if NAT Gateway AZ goes down?

**Answer:**

- NAT Gateway is **NOT** multi-AZ – it's HA only within its own AZ
- If the AZ fails, all private subnets routing through that NAT Gateway lose internet access

**Solution:**
```
Deploy one NAT Gateway per AZ:

AZ-a: NAT-GW-a in public-subnet-a
  → Private-subnet-a route: 0.0.0.0/0 → NAT-GW-a

AZ-b: NAT-GW-b in public-subnet-b
  → Private-subnet-b route: 0.0.0.0/0 → NAT-GW-b

AZ-c: NAT-GW-c in public-subnet-c
  → Private-subnet-c route: 0.0.0.0/0 → NAT-GW-c
```

Cost: 3× NAT Gateway hourly charges, but ensures AZ independence.

### Q16: VPC limits to know for interviews

| Resource | Default Limit | Max (adjustable) |
|----------|--------------|-------------------|
| VPCs per region | 5 | 100+ |
| Subnets per VPC | 200 | 200 |
| Route tables per VPC | 200 | 200 |
| Routes per route table | 50 | 1,000 |
| IGWs per region | 5 | Tied to VPC limit |
| NAT Gateways per AZ | 5 | Adjustable |
| Elastic IPs per region | 5 | Adjustable |
| Security Groups per VPC | 2,500 | Adjustable |
| Rules per Security Group | 60 inbound + 60 outbound | 120 each |
| VPC Peering per VPC | 50 | 125 |
| TGW attachments | 5,000 | 5,000 |

---

## Quick Reference: Key Networking Costs

| Service | Pricing Model |
|---------|---------------|
| VPC | Free |
| IGW | Free (data transfer charged) |
| NAT Gateway | $0.045/hr + $0.045/GB |
| VPC Peering | Free (cross-AZ data transfer charged) |
| Transit Gateway | $0.05/hr per attachment + $0.02/GB |
| Interface Endpoint | $0.01/hr per AZ + $0.01/GB |
| Gateway Endpoint | Free |
| Site-to-Site VPN | $0.05/hr + data transfer |
| Direct Connect | Port-hour fee + data transfer |
| ALB | $0.0225/hr + LCU charges |
| NLB | $0.0225/hr + NLCU charges |
| VPC Flow Logs | CloudWatch/S3 ingestion rates |

---

## Summary Cheat Sheet

```
VPC = Your private network in AWS
Subnet = Segment within an AZ (public or private)
Route Table = Rules for where traffic goes
IGW = Door to the internet (public subnets)
NAT GW = Internet for private subnets (outbound only)
SG = Instance firewall (stateful, allow only)
NACL = Subnet firewall (stateless, allow + deny)
VPC Peering = Direct VPC-to-VPC (non-transitive)
TGW = Hub for connecting many VPCs + on-prem
PrivateLink = Private access to services (no internet)
DX = Dedicated physical connection to AWS
VPN = Encrypted tunnel over internet
ALB = HTTP/HTTPS smart routing
NLB = TCP/UDP ultra-fast routing
Flow Logs = Network traffic audit trail
```
