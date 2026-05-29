# Disaster Recovery & Multi-Region Architecture - Complete Guide

---

## 1. DR Fundamentals

### Key Metrics
| Metric | Definition | Example |
|--------|-----------|---------|
| **RTO** (Recovery Time Objective) | Max acceptable downtime | "Back online within 1 hour" |
| **RPO** (Recovery Point Objective) | Max acceptable data loss | "Lose at most 5 minutes of data" |
| **MTTR** (Mean Time to Recovery) | Average time to restore service | Measured over incidents |
| **MTBF** (Mean Time Between Failures) | Average uptime between incidents | Higher = more reliable |

### Cost vs. Recovery Time Trade-off
```
Cost ↑                               RTO/RPO ↓
  │                                      │
  │  Multi-Site                          │  seconds
  │  Active-Active ──────────────────────│
  │                                      │
  │  Warm Standby ──────────────────────│  minutes
  │                                      │
  │  Pilot Light ────────────────────────│  10s of minutes
  │                                      │
  │  Backup & Restore ──────────────────│  hours
  │                                      │
  └──────────────────────────────────────┘
```

---

## 2. DR Strategies

### Strategy 1: Backup & Restore
- **RTO:** Hours (1-24 hours)
- **RPO:** Hours (last backup)
- **Cost:** Lowest ($)
```
Normal Operation:
  Production (us-east-1): Running workloads
  DR region: Nothing running
  Backups: S3 cross-region replication, RDS automated backups, EBS snapshots
  
Recovery:
  1. Restore RDS from backup/snapshot in DR region (30-60 min)
  2. Launch EC2/ECS from AMI/container image (10-20 min)
  3. Update DNS to DR region (depends on TTL)
  4. Total: 1-4 hours typical
  
Cost: Only S3 storage + snapshot storage (no running infrastructure in DR)
```

### Strategy 2: Pilot Light
- **RTO:** 10s of minutes
- **RPO:** Minutes (continuous replication)
- **Cost:** Low-Medium ($$)
```
Normal Operation:
  Production (us-east-1): Full infrastructure running
  DR region (us-west-2): 
    - RDS read replica (continuously replicated)
    - Core infrastructure deployed but NOT running (AMIs ready, ECS task defs, ASG with 0 instances)
    - Data layer active, compute layer off
    
Recovery:
  1. Promote RDS read replica to primary (1-2 min)
  2. Scale ASG from 0 → desired count (5-10 min)
  3. Start ECS services (2-5 min)
  4. Update Route 53 (health check failover - automatic)
  5. Total: 10-30 minutes
  
Cost: RDS replica + minimal infra (no compute running)
```

### Strategy 3: Warm Standby
- **RTO:** Minutes
- **RPO:** Seconds (async replication)
- **Cost:** Medium-High ($$$)
```
Normal Operation:
  Production (us-east-1): Full capacity (e.g., 10 instances)
  DR region (us-west-2): 
    - RDS Multi-Region read replica OR Aurora Global Database
    - Reduced capacity running (e.g., 2 instances, scaled-down ECS services)
    - All services running but at minimum capacity
    - Handles some read traffic (offload from primary)
    
Recovery:
  1. Scale up DR resources (ASG 2→10, ECS desired +) (3-5 min)
  2. Promote database replica (Aurora Global: <1 min, RDS: 1-2 min)
  3. Route 53 failover (automatic via health check)
  4. Total: 5-15 minutes
  
Cost: ~30-40% of production (always running minimal stack)
```

### Strategy 4: Multi-Site Active-Active
- **RTO:** Seconds (near-zero)
- **RPO:** Zero (synchronous) or near-zero (async with conflict resolution)
- **Cost:** Highest ($$$$)
```
Normal Operation:
  Region A (us-east-1): Full capacity, serves users
  Region B (eu-west-1): Full capacity, serves users
  Both active, both handling production traffic
  
  Data: DynamoDB Global Tables (multi-master, conflict resolution)
  DNS: Route 53 latency-based routing (users → nearest region)
  Static: CloudFront (global, origin in both regions)
  
Failure:
  Region A down → Route 53 health check fails → All traffic routes to Region B
  No recovery action needed (already active)
  Total failover time: Health check interval + DNS TTL = 30-90 seconds
  
Cost: 2× production cost (full infrastructure in both regions)
```

---

## 3. AWS DR Services

### Database DR Options
| Service | DR Mechanism | RPO | RTO | Cross-Region |
|---------|-------------|-----|-----|-------------|
| RDS | Multi-AZ (sync standby) | 0 (within region) | 1-2 min | Read Replica (async, minutes RPO) |
| Aurora | Multi-AZ (6 copies) | 0 (within region) | < 30 sec | Global Database (< 1 sec RPO, < 1 min RTO) |
| DynamoDB | Global Tables | Near-zero | Automatic | Multi-region active-active |
| ElastiCache | Global Datastore | < 1 sec | < 2 min | Cross-region replica |
| Redshift | Cross-region snapshots | Hours | 30-60 min | Restore from snapshot |
| S3 | CRR (Cross-Region Replication) | Minutes (async) | Immediate | Automatic |
| EFS | Replication | Minutes | Minutes | Cross-region replication |

### Aurora Global Database
```
Primary Region (us-east-1):
  Writer instance: All writes
  Reader instances: Read replicas (same region)
  
Secondary Region (eu-west-1):
  Read-only cluster: < 1 second replication lag
  Up to 5 secondary regions
  
Failover:
  Planned: Graceful switchover (RTO < 1 min, RPO = 0)
  Unplanned: Force promote secondary (RTO < 1 min, RPO < 1 sec typically)
  Write forwarding: Secondary can forward writes to primary (for global apps)
```

### DynamoDB Global Tables
```
Table replicated across regions (active-active):
  us-east-1: Read + Write
  eu-west-1: Read + Write
  ap-southeast-1: Read + Write
  
Conflict resolution: Last writer wins (timestamp-based)
Replication lag: Usually < 1 second
Consistency: Eventually consistent across regions, strongly consistent within region

Best for: Active-active, low-latency global access, simple conflict model
Not ideal for: Strict consistency requirements across regions
```

### Compute DR
| Service | DR Approach |
|---------|-------------|
| EC2 | AMI copy cross-region, ASG in DR region (0 or min instances) |
| ECS/Fargate | ECR replication, service definition in DR (desired 0 or min) |
| EKS | GitOps (same manifests applied to DR cluster), cluster in DR region |
| Lambda | Deploy same function to DR region (multi-region deployment pipeline) |

### Networking DR
- **Route 53:** Health check → automatic DNS failover
- **Global Accelerator:** Instant failover (no DNS TTL dependency), anycast static IPs
- **CloudFront:** Multi-origin failover (origin group: primary → secondary)
- **Transit Gateway:** Inter-region peering for cross-region connectivity

---

## 4. Multi-Region Architecture Patterns

### Pattern 1: Active-Passive with Route 53 Failover
```
Route 53 (Failover policy):
  PRIMARY: us-east-1 ALB (health check: /health)
  SECONDARY: us-west-2 ALB (health check: /health)

us-east-1 (Active):
  ALB → ECS → Aurora Writer (primary) → S3

us-west-2 (Passive):
  ALB → ECS (minimal) → Aurora Reader (global DB secondary) → S3 (CRR)

Failover triggers:
  - Route 53 health check fails (30 sec interval × 3 failures = 90 sec)
  - Or: CloudWatch Alarm → Lambda → Route 53 API (faster, programmatic)
```

### Pattern 2: Active-Active with Latency Routing
```
Route 53 (Latency-based routing):
  us-east-1: ALB (latency record)
  eu-west-1: ALB (latency record)
  ap-southeast-1: ALB (latency record)

Each region: Full stack, independent operations
Data: DynamoDB Global Tables (multi-master) + S3 CRR

Challenges:
  - Data consistency (eventual consistency between regions)
  - Conflict resolution (last-writer-wins or application-level)
  - Unique ID generation (UUID, or region-prefixed IDs)
  - Session management (sticky sessions or replicated session store)
```

### Pattern 3: Follow-the-Sun
```
Business hours routing:
  06:00-18:00 US → us-east-1 (full capacity)
  06:00-18:00 EU → eu-west-1 (full capacity)
  06:00-18:00 APAC → ap-southeast-1 (full capacity)
  
Off-hours: Scale down, failover to active region

Benefits: Cost optimization (not full capacity 24/7 everywhere)
Implementation: Scheduled scaling + geolocation routing
```

### Pattern 4: Cell-Based Architecture
```
Each cell is independent, self-contained unit:
  Cell 1 (us-east-1a): Handles customers A-M
  Cell 2 (us-east-1b): Handles customers N-Z
  Cell 3 (us-west-2a): Handles overflow + DR for Cell 1
  
Routing: API Gateway → Cell Router (customer → cell mapping)

Benefits:
  - Blast radius limited to one cell
  - Independent scaling, deployment, failure
  - Can evacuate cell (reroute to DR cell)
  
AWS example: Route 53 ARC (Application Recovery Controller) for cell-level failover
```

---

## 5. Route 53 Application Recovery Controller (ARC)

### Overview
- **What:** Manage and coordinate recovery across regions/AZs
- **Components:** Readiness checks, Routing controls, Cluster (5-node control plane)
- **Use case:** Orchestrated failover with safety checks

### Features
```
Readiness Check:
  - Verify DR region is ready BEFORE you need it
  - Check: Resource configurations match, capacity sufficient, dependencies healthy
  
Routing Control:
  - On/off switch for traffic routing (backed by health checks)
  - Grouped in control panels
  - Safety rules: Prevent routing to both off, or all to one cell

Zonal Shift:
  - Shift traffic away from unhealthy AZ (within minutes)
  - Temporary (set duration, auto-reverts)
  - Use case: AZ impairment detected before AWS declares outage
```

---

## 6. Data Replication Patterns

### Synchronous Replication
- **How:** Write confirmed only after replicated to DR
- **RPO:** Zero
- **Trade-off:** Added latency (cross-region round trip ~20-100ms)
- **Where:** RDS Multi-AZ (within region), Aurora local replicas
- **NOT practical cross-region** (latency too high for synchronous)

### Asynchronous Replication
- **How:** Write confirmed on primary, replicated in background
- **RPO:** Seconds to minutes (replication lag)
- **Trade-off:** Possible data loss = replication lag at failure time
- **Where:** Aurora Global (< 1 sec lag), RDS Read Replica, S3 CRR, DynamoDB Global Tables

### Conflict Resolution
| Strategy | How | Use Case |
|----------|-----|----------|
| Last writer wins (LWW) | Timestamp comparison | Simple, acceptable data loss |
| Application-level | Custom merge logic | Complex business rules |
| CRDT | Conflict-free data types | Counters, sets (mathematical guarantee) |
| Region-pinning | Write only in home region | Avoid conflicts entirely |

---

## 7. DR Testing & Automation

### Testing Approaches
| Type | Description | Frequency |
|------|-------------|-----------|
| Tabletop exercise | Walk through runbook verbally | Monthly |
| DR drill (non-disruptive) | Spin up DR, verify, tear down | Quarterly |
| Failover test | Actually failover traffic to DR | Semi-annually |
| Chaos engineering | Inject failures in production | Continuous |
| Game day | Full team exercise with real failover | Annually |

### Automated Failover Architecture
```
Detection:
  Route 53 Health Check (every 10 sec)
  + CloudWatch Alarms (application metrics)
  + Synthetics Canary (user-journey failure)

Decision:
  All three agree "unhealthy" → trigger failover
  (Avoid: single signal causing unnecessary failover)

Execution:
  EventBridge → Step Functions workflow:
    1. Verify DR readiness (ARC readiness check)
    2. Promote database (Aurora Global failover API)
    3. Scale compute (update ASG/ECS desired count)
    4. Update routing (ARC routing control → Route 53)
    5. Verify (Synthetics canary on DR endpoint)
    6. Notify (SNS → PagerDuty + Slack)
    
Safeguards:
  - ARC safety rules prevent dual-off
  - Circuit breaker: Don't failover back within 1 hour (stability)
  - Manual approval for failback (human verifies primary is stable)
```

### Runbook Template
```markdown
## Failover Runbook: Region Failure

### Pre-conditions
- [ ] DR region readiness check: PASS
- [ ] Last DR test: < 90 days ago
- [ ] On-call engineer confirmed primary is truly down (not false alarm)

### Failover Steps
1. [ ] Enable routing to DR region (ARC routing control)
2. [ ] Promote Aurora Global DB secondary (aws rds failover-global-cluster)
3. [ ] Verify database accepting writes (test write → read)
4. [ ] Scale ECS services to production capacity (update desired count)
5. [ ] Verify health checks passing in DR region
6. [ ] Monitor error rates and latency for 15 minutes
7. [ ] Notify stakeholders (StatusPage update)

### Failback Steps (after primary restored)
1. [ ] Verify primary region fully healthy (all services, network)
2. [ ] Re-establish replication (primary → secondary direction reversed)
3. [ ] Wait for replication lag = 0
4. [ ] Planned switchover (Aurora Global planned failover)
5. [ ] Gradually shift traffic back (Route 53 weighted: 10% → 50% → 100%)
6. [ ] Verify primary handling full load
7. [ ] Re-establish original topology (primary = original region)
```

---

## 8. Multi-Region Challenges

### Data Consistency
- **Problem:** Async replication means DR region may be behind
- **Solutions:**
  - Accept eventual consistency (most common)
  - Use DynamoDB Global Tables with conditional writes
  - Region-pin writes (each entity owned by one region)
  - Track consistency with vector clocks or version numbers

### Unique ID Generation
- **Problem:** Two regions generating IDs simultaneously → collisions
- **Solutions:**
  - UUIDs (random, no coordination needed)
  - Region-prefixed: `us-east-1-12345`, `eu-west-1-12345`
  - Snowflake IDs: Timestamp + machine ID + sequence (unique, sortable)
  - DynamoDB atomic counter in home region (if entity has home region)

### Session Management
- **Problem:** User failover to different region → session lost
- **Solutions:**
  - Stateless (JWT tokens, session data in token) — preferred
  - DynamoDB Global Tables as session store (replicated)
  - ElastiCache Global Datastore (Redis replication)
  - Cookie-based sessions (encrypted session in browser)

### DNS & Routing
- **Problem:** DNS TTL means some clients still hit failed region
- **Solutions:**
  - Low TTL (60 sec) — most clients refresh within 60s
  - Global Accelerator (anycast, no DNS dependency, instant reroute)
  - Client-side retry logic (retry to different endpoint on failure)
  - Health-aware SDKs (AWS SDK auto-retries to different region)

---

## 9. Scenario-Based Interview Questions

### Q1: Design DR for a banking application (RTO 5 min, RPO 0)
**Answer:**
```
RPO = 0 means NO data loss → Requires synchronous replication

Architecture: Multi-Region Warm Standby with Aurora Global Database
  
Primary (us-east-1):
  ALB → ECS Fargate (10 tasks) → Aurora PostgreSQL (writer)
  
Secondary (us-west-2):  
  ALB → ECS Fargate (3 tasks, warm) → Aurora Global DB (reader, < 1 sec lag)
  
Data:
  - Aurora Global Database: RPO < 1 second (async but near-synchronous)
  - For TRUE RPO=0: Use Aurora with write forwarding + 
    Application-level confirmation (write to both regions, confirm both)
  - OR: DynamoDB Global Tables (transactions within single region, replicated)
  
Failover (< 5 min RTO):
  1. Route 53 health check detects primary down (30 sec)
  2. Automated Step Functions workflow triggers
  3. Aurora Global failover (~30 sec)
  4. ECS scale up in DR (2-3 min, tasks already warm)
  5. Route 53 routing control switches traffic
  Total: < 4 minutes

For TRUE RPO=0 (no loss even of 1 second lag):
  - Synchronous multi-region writes (write to DynamoDB Global Tables, 
    transaction confirmed only when replicated)
  - Trade-off: Higher write latency (~100ms added)
  - Alternative: Write to both regions simultaneously from application layer
```

### Q2: Application runs in single region. CEO wants "five nines" (99.999%). What do you recommend?
**Answer:**
```
99.999% = 5.26 minutes downtime per YEAR

Analysis:
  - Single region CANNOT achieve 99.999%:
    - AWS region availability SLA: 99.99% (52 min/year)
    - Individual services: 99.95-99.99%
    - Compound: Multiple services = lower combined availability
    
  Requirements for 99.999%:
    1. Multi-region active-active (eliminate single region as SPOF)
    2. Automated failover (no human in the loop - too slow)
    3. Zero-downtime deployments (rolling, canary)
    4. No single points of failure at any layer
    
  Architecture:
    - 2+ active regions with automated health-based routing
    - Global Accelerator (instant failover, faster than DNS)
    - DynamoDB Global Tables (multi-master, no failover needed for data)
    - Stateless compute (ECS/EKS, auto-scaled in both regions)
    - CloudFront (caches requests, absorbs failures)
    - Circuit breakers (graceful degradation vs hard failure)
    
  Operational requirements:
    - Fully automated deployment (humans don't push buttons at 3 AM)
    - Chaos engineering (continuously test failure scenarios)
    - SLO burn rate alerting (detect issues before they compound)
    - Sub-minute detection and failover
    
  Cost: ~2.5× single region (active-active + tooling + testing overhead)
  
  Trade-off conversation with CEO:
    - 99.99% → 52 min/year → multi-AZ single region → 1.2× cost
    - 99.999% → 5 min/year → multi-region active-active → 2.5× cost
    - Are we sure the BUSINESS needs 99.999%? What's the cost of 52 min downtime/year?
```

### Q3: How to handle database failover when you have read replicas and writes in progress?
**Answer:**
```
Scenario: Primary DB fails, transactions in-flight

Challenges:
  1. In-flight writes on primary: LOST (not committed, not replicated)
  2. Replication lag: Committed writes not yet on replica also LOST
  3. Application connections: All break simultaneously
  4. Replica promotion: Takes 1-2 minutes
  5. Application reconnection: Needs to discover new primary

Solutions by layer:

  Database:
    - Aurora: 6 copies across 3 AZs. Failover < 30 sec. Near-zero data loss
    - Aurora Global: Managed planned failover (0 RPO) or unplanned (< 1 sec RPO)
    - RDS Multi-AZ: Synchronous replication → 0 RPO within region
    
  Application:
    - Use RDS Proxy: Handles connection pooling + transparent failover
      - Application doesn't know DB failed over
      - Multiplexing: Existing connections rerouted to new primary
    - Retry logic: Failed writes → retry after 2 seconds (exponential backoff)
    - Idempotent writes: Use idempotency key so retry doesn't duplicate
    
  Connection management:
    - Connection timeout: 5 seconds (fail fast, reconnect)
    - DNS TTL: Use RDS Proxy endpoint (handles routing internally)
    - Health check: Application checks DB connectivity periodically
    
  Data integrity:
    - After failover: Application verifies critical transactions
    - Compensation: If transaction lost → detect (checksum/reconciliation) → retry
    - Event sourcing: Replay events from last known good state
```

### Q4: Design a multi-region deployment pipeline
**Answer:**
```
Pipeline: Single pipeline deploys to all regions safely

Strategy: Progressive rollout (one region at a time)

  GitHub → GitHub Actions:
    1. Build + Test (unit, integration) → Docker image → ECR
    2. Deploy to CANARY region (us-west-2, lowest traffic):
       - ECS blue/green deployment
       - Synthetic tests run against canary
       - Monitor 15 minutes (error rate, latency)
       - Gate: Continue only if metrics healthy
    3. Deploy to PRIMARY region (us-east-1):
       - Same blue/green deployment
       - Monitor 30 minutes (carries most traffic)
       - Gate: Automated quality gate (CloudWatch Alarm = ALARM → rollback)
    4. Deploy to REMAINING regions (eu-west-1, ap-southeast-1):
       - Parallel deployment to remaining regions
       - Monitor 15 minutes each
       
  Rollback:
    - Automated: If alarm triggers during bake time → CodeDeploy rollback
    - Manual: On-call can trigger rollback via ChatOps (Slack command)
    - Blast radius: Only one region affected at a time
    
  Infrastructure:
    - Terraform: Same modules, per-region state files
    - Deploy infra changes in same progressive order
    - Feature flags: Decouple deploy from release (dark launch)
    
  Database migrations:
    - Forward-compatible only (old code works with new schema)
    - Multi-phase: Add column → backfill → deploy new code → remove old column
    - Aurora Global: Schema changes replicate automatically
```

### Q5: During an AWS regional outage, what fails and what still works?
**Answer:**
```
GLOBAL services (NOT affected by single region outage):
  - Route 53 (DNS) — global, highly distributed
  - CloudFront (CDN) — edge locations independent
  - IAM (identity) — global (but regional endpoints may be affected)
  - S3 (data replicated to DR via CRR is fine in other region)
  - Global Accelerator — anycast, routes around failed region

REGIONAL services (AFFECTED if region is down):
  - EC2, ECS, EKS, Lambda — all regional
  - RDS, Aurora, DynamoDB (single-region tables) — regional
  - ALB/NLB — regional
  - SQS, SNS, EventBridge — regional
  - Kinesis, Firehose — regional
  - API Gateway — regional (unless edge-optimized with CloudFront)

IMPORTANT GOTCHAS:
  - us-east-1 is special: Many global services have control plane there
    - If us-east-1 degrades: CloudFront config changes may fail
    - IAM policy changes may be slow
    - S3 new bucket creation (global namespace) may fail
  - Console may be affected (some console features depend on us-east-1)
  - Programmatic access (SDK/CLI) is more resilient than console
  
Mitigation:
  - Pre-provision everything (don't need to create resources during outage)
  - Cache IAM credentials (don't assume role at time of failure)
  - DNS records already in place (Route 53 health checks trigger automatically)
  - Avoid us-east-1 as sole region for critical workloads (or use as secondary)
```

