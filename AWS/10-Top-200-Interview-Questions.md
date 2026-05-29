# Top 200+ Interview Questions - AWS, Kubernetes, IaC & CI/CD

> Comprehensive interview preparation covering all major topics with detailed answers.

---

## EC2 & Compute (Q1-Q25)

### Q1: What are the different EC2 instance families and when to use each?
**Answer:**
- **General Purpose (T/M):** Balanced CPU/memory. T-series for burstable (web servers, dev), M-series for steady (app servers)
- **Compute Optimized (C):** High CPU-to-memory ratio. Batch processing, gaming, ML inference, HPC
- **Memory Optimized (R/X/z):** High memory. In-memory databases, Redis, SAP HANA, real-time analytics
- **Storage Optimized (I/D/H):** High sequential read/write. Data warehousing, HDFS, distributed filesystems
- **Accelerated (P/G/Inf/Trn):** GPU/custom chips. ML training (P5), inference (Inf2), graphics (G5)

### Q2: Explain On-Demand vs Reserved vs Spot vs Savings Plans
**Answer:**
- **On-Demand:** Pay per second, no commitment, highest cost. Use for unpredictable/short workloads
- **Reserved (RI):** 1-3yr commitment, up to 72% discount. Standard (fixed family) vs Convertible (can change family, up to 66%)
- **Spot:** Up to 90% discount, 2-min interruption notice. Use for fault-tolerant: batch, CI/CD, data analysis
- **Savings Plans:** Commit $/hr for 1-3yr. Compute SP (any family/region/OS) vs EC2 SP (specific family+region, deeper discount)

### Q3: How does EC2 Auto Scaling work?
**Answer:**
- **Components:** Launch Template + Auto Scaling Group + Scaling Policy
- **Policies:** Target Tracking (keep CPU at 50%), Step (add 2 if CPU>80%), Scheduled (cron), Predictive (ML forecasts)
- **Key settings:** min/max/desired, cooldown (300s default), health check grace period
- **Health checks:** EC2 status checks, ELB health checks, or custom
- **Advanced:** Warm pools (pre-initialized stopped instances), lifecycle hooks (run scripts before InService)

### Q4: What is the difference between horizontal and vertical scaling?
**Answer:**
- **Vertical (scale up):** Increase instance size (t3.small → t3.xlarge). Requires downtime, has upper limit
- **Horizontal (scale out):** Add more instances. No downtime, theoretically unlimited, requires stateless design
- **AWS implementation:** Vertical = change instance type (stop required). Horizontal = Auto Scaling Group + Load Balancer
- **Best practice:** Design for horizontal scaling. Use vertical only for databases or legacy apps

### Q5: Explain placement groups - cluster, spread, partition
**Answer:**
- **Cluster:** All instances in same rack/AZ. Lowest latency (10 Gbps between instances). Use: HPC, tightly-coupled apps
- **Spread:** Each instance on different hardware. Max 7 instances per AZ. Use: critical instances needing HA
- **Partition:** Groups in separate racks (up to 7 partitions/AZ). Use: HDFS, Cassandra, Kafka (partition-aware)
- Cannot merge placement groups. Can span peered VPCs (same region)

### Q6: How does CPU credit system work for T-series?
**Answer:**
- T-series instances have a **baseline** CPU performance (e.g., t3.micro = 10%)
- Earn credits when below baseline, spend credits when bursting above
- **Standard mode:** Instance throttled to baseline when credits exhausted
- **Unlimited mode (T3 default):** Can burst beyond credits at extra cost ($0.05/vCPU-hour)
- Credit earn rate: t3.micro = 12 credits/hr, t3.large = 36 credits/hr
- 1 credit = 1 vCPU at 100% for 1 minute
- **Key interview tip:** If CPUCreditBalance consistently at 0, upgrade to M-series

### Q7: What is the difference between EBS and Instance Store?
**Answer:**
| Feature | EBS | Instance Store |
|---------|-----|----------------|
| Persistence | Persists after stop/terminate (if set) | Lost on stop/terminate/hardware failure |
| Performance | Up to 256K IOPS (io2 Block Express) | Millions of IOPS (NVMe) |
| Detachable | Yes (move between instances) | No (physically attached) |
| Snapshot | Yes (incremental, S3) | No |
| Encryption | KMS supported | Hardware-level |
| **Use case** | Boot volumes, databases | Caches, buffers, temp processing |

### Q8: Explain EBS volume types and when to use each
**Answer:**
- **gp3:** Default SSD. 3000 IOPS baseline, up to 16K. Most workloads. Independent IOPS/throughput scaling
- **gp2:** Legacy SSD. 3 IOPS/GiB (burst to 3000). Use gp3 instead (20% cheaper)
- **io2/io2 Block Express:** Up to 64K/256K IOPS. Critical databases (Oracle, SQL Server)
- **st1:** Throughput HDD, 500 MB/s. Big data, log processing, data warehouses
- **sc1:** Cold HDD, 250 MB/s. Infrequent access, lowest cost
- **Decision:** Random I/O → SSD (gp3/io2). Sequential I/O → HDD (st1). Archive → sc1

### Q9: How would you troubleshoot an unresponsive EC2 instance?
**Answer:**
1. Check **Status Checks**: System (AWS hardware issue) vs Instance (OS issue)
2. View **System Log** (console output): kernel panic, fsck errors, boot issues
3. Check **Security Groups**: Inbound rules for SSH/RDP port
4. Check **NACLs**: Both inbound AND outbound (stateless)
5. Check **Route Table**: Route to Internet Gateway exists
6. Verify **Elastic IP** / Public IP didn't change after stop/start
7. Check **disk space** (if instance was running): could cause OS hang
8. **Recovery:** Detach root EBS → attach to healthy instance → fix → reattach
9. Enable **EC2 Auto Recovery** CloudWatch alarm for future

### Q10: What is IMDSv2 and why use it?
**Answer:**
- **IMDSv1:** Simple GET to http://169.254.169.254 — vulnerable to SSRF attacks (attacker can steal IAM credentials)
- **IMDSv2:** Requires session token (PUT request with TTL → use token in subsequent GET)
- **Protection:** Token can't be forwarded via SSRF (PUT requests typically blocked by WAFs/proxies, X-Forwarded-For headers limit token hop)
- **Enforcement:** Set `HttpTokens: required` in instance metadata options
- **Best practice:** Enforce IMDSv2, set hop limit to 1 (blocks container-level SSRF)

### Q11: Security Group vs NACL - what's the difference?
**Answer:**
| Feature | Security Group | NACL |
|---------|---------------|------|
| Level | Instance (ENI) | Subnet |
| State | Stateful (return traffic auto-allowed) | Stateless (must allow both directions) |
| Rules | Allow only | Allow + Deny |
| Evaluation | All rules evaluated together | Rules evaluated in number order |
| Default | Deny all inbound, allow all outbound | Allow all inbound and outbound |
| Association | Multiple SGs per instance | One NACL per subnet |

### Q12: How do you achieve high availability with EC2?
**Answer:**
- **Multi-AZ:** Deploy across 2-3 AZs (ASG with AZ-balanced distribution)
- **Auto Scaling:** Automatically replace failed instances
- **Load Balancer:** ALB/NLB distributes traffic, detects unhealthy instances
- **Health Checks:** ELB + custom health checks for faster detection
- **Spread Placement Group:** Ensure instances on different hardware
- **Auto Recovery:** CloudWatch alarm triggers instance recovery on hardware failure
- **Cross-Region:** Route 53 failover for regional HA (multi-region)

### Q13: What is an AMI and how do you manage them?
**Answer:**
- **AMI (Amazon Machine Image):** Template with OS + software + config for launching instances
- **Types:** Public, Private (your account), Marketplace (vendors)
- **Creation:** Instance → Stop → Create Image (or from snapshot)
- **Components:** Root volume snapshot + launch permissions + block device mapping
- **Sharing:** Cross-account (modify permissions), Cross-region (copy AMI)
- **Best practice:** Golden AMI pipeline with EC2 Image Builder (build → test → distribute)
- **Lifecycle:** Version AMIs, deregister old ones, delete associated snapshots

### Q14: Explain EC2 hibernation
**Answer:**
- **What:** RAM contents saved to encrypted EBS root volume. On resume, RAM reloaded → processes continue
- **Benefits:** Faster startup than cold boot (seconds vs minutes for heavy apps)
- **Requirements:** EBS root volume (must be encrypted), RAM < 150 GB, supported instance families
- **Limitations:** Cannot hibernate > 60 days, not supported for all OS versions
- **Use cases:** Long-running processing that you want to pause, pre-warmed instances, development environments
- **vs Stop/Start:** Stop loses RAM state. Hibernate preserves it

### Q15: Dedicated Hosts vs Dedicated Instances - what's the difference?
**Answer:**
- **Dedicated Instance:** Your instances run on hardware not shared with other accounts. No visibility into hardware
- **Dedicated Host:** Entire physical server for you. Visibility into sockets, cores, host ID
- **Use Dedicated Host when:** BYOL (Bring Your Own License) for per-socket/per-core licensing (Windows Server, SQL Server, Oracle)
- **Use Dedicated Instance when:** Compliance requires hardware isolation but no licensing needs
- **Cost:** Dedicated Host = per-host pricing. Dedicated Instance = per-instance + $2/hr/region fee

### Q16: How do Spot Fleet strategies work?
**Answer:**
- **lowestPrice:** Launches from lowest-price pool. Risk: all in one pool → mass interruption
- **diversified:** Spreads across all pools. Best for availability, reduces interruption impact
- **capacityOptimized:** Launches from pool with most available capacity. Lowest interruption probability
- **priceCapacityOptimized (recommended):** Balances price + capacity. Best overall strategy
- **Allocation strategy** determines which pool to launch from when multiple meet criteria
- **Best practice:** Use priceCapacityOptimized + multiple instance types (6+) + multiple AZs

### Q17: Launch Templates vs Launch Configurations
**Answer:**
- **Launch Configuration:** Legacy, immutable (must recreate to change), no versioning
- **Launch Template:** Current, supports versioning, can modify, supports mixed instances
- **Template advantages:** Spot + On-Demand mix, multiple instance types, T2/T3 Unlimited, placement groups, capacity reservations, Dedicated Hosts
- **Must use Template for:** Latest ASG features, mixed instance policies, Spot diversification
- **Migration:** Create template from existing config, update ASG to reference template

### Q18: What is EBS Multi-Attach?
**Answer:**
- Attach single io1/io2 volume to up to 16 Nitro-based instances simultaneously (same AZ)
- **Use cases:** Clustered applications (Oracle RAC), high-availability file systems
- **Requirements:** io1/io2 only, Nitro instances, same AZ, provisioned IOPS
- **Limitations:** Not supported with boot volumes, no cross-AZ, application must manage concurrent writes (cluster-aware filesystem)
- **Alternative:** EFS for shared file storage (NFS-based, simpler)

### Q19: How does predictive scaling work?
**Answer:**
- Uses **ML** to analyze 14 days of historical CloudWatch data
- Forecasts future demand and pre-provisions capacity
- Schedules scaling actions ahead of predicted peaks
- **Modes:** Forecast only (view predictions) or Forecast and scale (automatic)
- **Best for:** Workloads with recurring daily/weekly patterns (e.g., 8am-6pm business apps)
- Combine with target tracking for unexpected spikes
- Requires at least 24 hours of data, works best with 14+ days

### Q20: What are warm pools in Auto Scaling?
**Answer:**
- Pool of **pre-initialized** instances in Stopped/Running/Hibernated state
- On scale-out: use warm pool instance (seconds) instead of launching new (minutes)
- **Benefit:** Faster scaling for instances with long boot/initialization times
- **States:** Stopped (no compute charge, just EBS), Running (full charge), Hibernated (fastest resume)
- **Lifecycle:** Warm pool → Warmed:Pending → Warmed:Stopped → Pending:Wait → InService
- **Use case:** Applications needing 5-10 min initialization (data loading, cache warming)

### Q21: What are Nitro Enclaves?
**Answer:**
- Isolated compute environments within EC2 (separate CPU, memory, no storage, no network)
- **Purpose:** Process highly sensitive data (PII, financial, healthcare, cryptographic operations)
- **Security:** No admin access, no SSH, no persistent storage, attestation-based access
- **Attestation:** Cryptographic proof that enclave is running expected code
- **Use cases:** Tokenization, key management, secure multi-party computation
- Integration with KMS: condition key validates enclave identity before releasing data keys

### Q22: How do you right-size EC2 instances?
**Answer:**
1. **AWS Compute Optimizer:** ML-based recommendations from 14 days of CloudWatch data
2. **CloudWatch metrics:** CPU utilization, memory (custom metric), network, disk I/O
3. **Rules of thumb:** CPU < 40% avg → downsize. CPU > 80% → upsize. Memory similar
4. **Process:** Monitor 2-4 weeks → identify over-provisioned → test smaller size → validate performance
5. **Tools:** Compute Optimizer, Cost Explorer, Trusted Advisor, third-party (Spot.io, CloudHealth)
6. **Consider:** Peak vs average usage, Graviton migration (20% savings), generation upgrade (better price/perf)

### Q23: What is EC2 Image Builder?
**Answer:**
- Fully managed service to automate AMI creation, testing, and distribution
- **Pipeline:** Source AMI → Build components → Test components → Distribute
- **Components:** Build (install software, configure) and Test (validate) using YAML/shell
- **Distribution:** Cross-region, cross-account, share with organizations
- **Triggers:** Schedule (cron), manual, or event-based
- **Integration:** SSM documents, custom scripts, CIS benchmarks
- **Output:** AMI, Docker image, or both

### Q24: Explain lifecycle hooks in Auto Scaling
**Answer:**
- Pause instance at launch or termination for custom actions
- **Launch hook:** Instance in `Pending:Wait` state → run initialization → `Pending:Proceed` → InService
- **Termination hook:** Instance in `Terminating:Wait` → save logs/deregister → `Terminating:Proceed` → Terminated
- **Timeout:** Default 1 hour (max 48 hours with heartbeat)
- **Notification:** SNS, SQS, EventBridge, or CloudWatch Events → Lambda
- **Use cases:** Install software, register with config management, pull data, drain connections, upload logs

### Q25: How do you handle frequent Spot interruptions?
**Answer:**
1. **Diversify:** Use 6+ instance types across 3+ AZs (priceCapacityOptimized strategy)
2. **Checkpointing:** Save progress to S3/DynamoDB every few minutes
3. **Interruption handling:** Poll metadata endpoint every 5s, use EventBridge for 2-min warning
4. **Architecture:** Stateless workers + SQS queue (another instance picks up interrupted work)
5. **Mixed fleet:** On-Demand for baseline (20-30%) + Spot for burst (70-80%)
6. **Fallback:** Configure ASG to fall back to On-Demand if no Spot capacity
7. **Spot placement score:** Check capacity availability before launching


---

## ECS & Fargate (Q26-Q50)

### Q26: ECS EC2 launch type vs Fargate - when to use which?
**Answer:**
- **Fargate:** No server management, pay per task, good for variable workloads, faster time-to-market
- **EC2:** More control (GPU, custom AMI, larger instances), cheaper for steady-state high-utilization, access to instance store
- **Choose Fargate when:** Startups, variable traffic, small teams, don't want to manage infra
- **Choose EC2 when:** GPU workloads, Windows containers (cheaper), high-CPU/memory needs beyond Fargate limits, cost optimization at scale

### Q27: Explain ECS Task Definition components
**Answer:**
- **Family:** Name + revision number (myapp:3)
- **Container Definitions:** image, cpu, memory, portMappings, essential, environment, secrets, logConfiguration, healthCheck, dependsOn, mountPoints
- **Task-level settings:** cpu, memory (required for Fargate), networkMode, executionRoleArn, taskRoleArn, volumes
- **Network modes:** awsvpc (each task gets ENI), bridge (Docker default), host (use host ports)
- **Volumes:** EFS (shared persistent), bind mounts (ephemeral shared between containers)

### Q28: Task Role vs Execution Role - what's the difference?
**Answer:**
- **Task Role:** What your application containers can do (S3 access, DynamoDB, SQS). Your app code uses this
- **Execution Role:** What the ECS agent can do (pull images from ECR, push logs to CloudWatch, fetch secrets from Secrets Manager)
- **Analogy:** Execution role = IT admin setting up computer. Task role = employee using computer
- Both are IAM roles with trust policy for ecs-tasks.amazonaws.com

### Q29: How does ECS Service Discovery work?
**Answer:**
- Uses **AWS Cloud Map** to register task IPs in DNS (Route 53 private hosted zone)
- **A records:** Task private IP (awsvpc mode)
- **SRV records:** IP + port (bridge mode with dynamic ports)
- **DNS resolution:** service-name.namespace-name → task IPs
- **Health checks:** Route 53 health checks or ECS task health
- **Alternative:** ECS Service Connect (newer, built-in client-side load balancing, no DNS propagation delay)

### Q30: Explain ECS deployment strategies
**Answer:**
- **Rolling update (ECS):** Replace tasks gradually. minimumHealthyPercent=50, maximumPercent=200 means: start new tasks first, then drain old
- **Blue/Green (CodeDeploy):** Two target groups, shift traffic (all-at-once, linear 10%/min, canary 10%+90%). Instant rollback
- **External:** Third-party controller manages deployment
- **Circuit breaker:** If deployment fails N times, auto-rollback to last stable version
- **Best practice:** Blue/Green for production (instant rollback), Rolling for staging (simpler)

### Q31: What are valid Fargate CPU/memory combinations?
**Answer:**
| CPU (vCPU) | Memory Options (GB) |
|------------|-------------------|
| 0.25 | 0.5, 1, 2 |
| 0.5 | 1, 2, 3, 4 |
| 1 | 2, 3, 4, 5, 6, 7, 8 |
| 2 | 4-16 (1 GB increments) |
| 4 | 8-30 (1 GB increments) |
| 8 | 16-60 (4 GB increments) |
| 16 | 32-120 (8 GB increments) |

Ephemeral storage: 20 GiB default, expandable to 200 GiB.

### Q32: How do you handle secrets in ECS?
**Answer:**
- **Secrets Manager:** Store secret → reference in task def as `valueFrom` with ARN → injected as env var at task start
- **SSM Parameter Store:** Same pattern, cheaper for simple key-value (SecureString with KMS)
- **Execution role** must have permission to read the secret
- **Never:** Hardcode in task def, pass as plain environment variable, store in image
- **Rotation:** Secrets Manager supports auto-rotation with Lambda. Task must be restarted to pick up new value
- **Init container pattern:** Fetch secrets at startup, write to shared volume

### Q33: What is Fargate Spot?
**Answer:**
- Up to **70% discount** over regular Fargate pricing
- Tasks can be interrupted with **30-second warning** (SIGTERM)
- Uses spare AWS Fargate capacity
- **Use for:** Fault-tolerant workloads, batch jobs, CI/CD builds, data processing
- **Not for:** Latency-sensitive, stateful, long-running critical tasks
- **Implementation:** Set `capacityProviderStrategy` with FARGATE_SPOT and optionally FARGATE as base

### Q34: Explain ECS capacity providers
**Answer:**
- **What:** Abstraction for infrastructure. Strategies determine what % runs on which provider
- **Built-in:** FARGATE, FARGATE_SPOT
- **Custom (EC2):** ASG-backed, managed scaling (target tracking on CapacityProviderReservation metric), managed termination protection
- **Strategy example:** base=2 on FARGATE + weight=3 FARGATE_SPOT, weight=1 FARGATE → 75% Spot, 25% regular after base
- **Benefit:** Decouple service from infrastructure decisions

### Q35: How does dynamic port mapping work with ALB?
**Answer:**
- In **bridge** network mode: container port maps to random host port (e.g., 80→32768)
- ALB target group uses **instance** target type
- ECS registers instance:dynamic-port with ALB automatically
- Multiple tasks on same instance each get different host port
- ALB routes to correct port based on registration
- **Note:** In awsvpc mode, each task has own IP → port mapping is static (use IP target type)

### Q36: What is ECS Service Connect?
**Answer:**
- Simplified service mesh built into ECS (announced re:Invent 2022)
- **Features:** Service discovery + client-side load balancing + traffic metrics + retry/timeout
- Uses **Envoy proxy** as sidecar (managed by ECS)
- **vs Cloud Map:** No DNS propagation delay, connection-level load balancing, built-in metrics
- **vs App Mesh:** Simpler setup, fewer features but sufficient for most use cases
- Configure per-service in ECS service definition with namespace and port alias

### Q37: How to debug a failing Fargate task?
**Answer:**
1. **Stopped task reason:** Check ECS console → Stopped Tasks → "Stopped reason" field
2. **CloudWatch Logs:** Check container logs (ensure awslogs driver configured)
3. **Exit codes:** 0=success, 1=app error, 137=OOMKilled (memory), 139=segfault
4. **ECS Exec:** Enable execute-command → `aws ecs execute-command --interactive --command /bin/sh`
5. **Common issues:** ECR pull failure (check execution role), secret fetch failure, health check timeout
6. **Task metadata endpoint:** http://169.254.170.2/v4/metadata for task-level debugging

### Q38: Explain ECS task networking modes
**Answer:**
- **awsvpc (required for Fargate):** Each task gets own ENI + private IP + security group. Best isolation
- **bridge (EC2 only):** Docker bridge network. Tasks share host IP. Dynamic port mapping needed
- **host (EC2 only):** Container uses host network directly. Best performance, port conflicts possible
- **none:** No networking (isolated batch processing)
- **Recommendation:** Always use awsvpc for new workloads (better security, simpler networking)

### Q39: What is ECS Exec?
**Answer:**
- Interactive shell access into running containers (like `docker exec` but for ECS)
- Uses **SSM Session Manager** under the hood
- **Enable:** Set `enableExecuteCommand: true` in service + task role needs SSM permissions
- **Command:** `aws ecs execute-command --cluster X --task Y --container Z --command "/bin/sh" --interactive`
- **Use cases:** Debugging, troubleshooting, one-off commands in running container
- **Security:** Audit via CloudTrail, can restrict with IAM conditions

### Q40: How to implement auto-scaling for ECS services?
**Answer:**
- **Target Tracking:** Keep CPU/memory at target (e.g., CPU 60%). Recommended for most cases
- **Step Scaling:** Add/remove tasks based on CloudWatch alarm thresholds
- **Scheduled:** Scale at known times (cron expression)
- **Custom metrics:** Scale on SQS queue depth, request count per target, custom CloudWatch metrics
- **Configuration:** Min=2, Max=20, Target=CPU 60%, scale-in cooldown=300s, scale-in protection for long tasks
- **Combine with:** Capacity providers (auto-scale EC2 underneath)

### Q41: Explain circuit breaker in ECS deployments
**Answer:**
- Automatically detects failing deployments and rolls back
- **How:** If tasks repeatedly fail to reach RUNNING state, deployment marked as failed
- **Threshold:** Configurable failure count before rollback triggers
- **Rollback:** Reverts to last stable task definition (previous deployment)
- **Enable:** `deploymentCircuitBreaker: { enable: true, rollback: true }` in service
- **Without circuit breaker:** Failed deployment hangs indefinitely, requires manual intervention

### Q42: What is FireLens for ECS?
**Answer:**
- Log router (Fluent Bit or Fluentd) as sidecar container managed by ECS
- **Benefits:** Route logs to multiple destinations (CloudWatch, S3, Elasticsearch, Datadog, Splunk) from single config
- **vs awslogs:** awslogs only goes to CloudWatch. FireLens is multi-destination with filtering/transformation
- **Configuration:** `logDriver: awsfirelens` in container def, FireLens config in separate file or inline
- **Recommendation:** Use Fluent Bit (lighter, faster) over Fluentd

### Q43: Blue/Green deployment with CodeDeploy on ECS
**Answer:**
1. **Setup:** Two target groups (Blue=active, Green=new), ALB with production + test listener
2. **Deploy:** CodeDeploy creates new task set (Green target group) with new task definition
3. **Test:** Traffic routes to test listener → validate Green
4. **Shift:** Move production traffic (AllAtOnce, Linear 10%/10min, Canary 10%+90%)
5. **Rollback:** Shift traffic back to Blue (instant via ALB)
6. **Cleanup:** Terminate Blue task set after validation period
7. **Hooks:** BeforeInstall, AfterInstall, BeforeAllowTraffic, AfterAllowTraffic (Lambda validation)

### Q44: What are ECS container dependencies (dependsOn)?
**Answer:**
- Control container startup/shutdown order within a task
- **Conditions:** START (wait for container to start), HEALTHY (wait for health check pass), SUCCESS (wait for exit 0), COMPLETE (wait for exit)
- **Example:** App container `dependsOn` DB migration container with condition=SUCCESS
- **Use case:** Init containers (run migration before app starts), sidecar readiness (wait for Envoy proxy)
- Without dependsOn, containers start simultaneously (race conditions)

### Q45: How to optimize Fargate costs?
**Answer:**
1. **Fargate Spot:** 70% discount for fault-tolerant workloads
2. **Right-size:** Monitor CPU/memory with Container Insights → reduce if over-provisioned
3. **Savings Plans:** Compute Savings Plan covers Fargate (1yr: ~37% discount, 3yr: ~52%)
4. **ARM (Graviton):** Use ARM-based Fargate (linux/arm64) for 20% lower price + better performance
5. **Scale to zero:** For non-production, schedule tasks to 0 at night
6. **Shared resources:** Split CPU-bound and memory-bound containers to use full allocation
7. **Spot + regular mix:** FARGATE_SPOT base + FARGATE for critical minimum

### Q46: Explain ECR lifecycle policies
**Answer:**
- Automatically clean up old/unused images to reduce storage costs
- **Rules based on:** Image age (sinceImagePushed > 30 days), count (keep last 10), tag status (untagged)
- **Priority:** Lower number = higher priority. Evaluated in priority order
- **Example policy:** Keep last 5 tagged "release-*", keep last 30 days of "dev-*", expire all untagged after 1 day
- **Preview:** Test rules before applying (dry-run)
- **Best practice:** Always have lifecycle policy to prevent unlimited image accumulation

### Q47: What is ECR image scanning?
**Answer:**
- **Basic scanning:** Uses Clair (open-source). Scans on push or manual trigger. CVE database
- **Enhanced scanning (Inspector):** Continuous monitoring, OS + programming language vulnerabilities, automatic re-scanning when new CVEs discovered
- **Findings:** Severity (Critical/High/Medium/Low/Informational), CVE ID, fix available
- **Integration:** EventBridge rules to notify/block on critical findings
- **Best practice:** Enable scan on push, fail CI/CD pipeline on Critical/High findings

### Q48: How to handle stateful applications on ECS?
**Answer:**
- **EFS volumes:** Shared persistent storage across tasks and instances
- **EBS (EC2 launch type):** Per-instance storage, not shared
- **External state:** Prefer externalizing state to RDS, DynamoDB, ElastiCache, S3
- **Service Discovery:** Stable endpoints for stateful services
- **Placement constraints:** Sticky to specific instances (memberOf attribute)
- **Best practice:** Design stateless where possible. If stateful required, consider EKS StatefulSets instead

### Q49: ECS task placement strategies and constraints
**Answer:**
- **Strategies (EC2 launch type only):**
  - `binpack`: Pack tasks onto fewest instances (cost optimization)
  - `spread`: Distribute across AZs or instances (availability)
  - `random`: Random placement
  - Can combine: spread by AZ, then binpack by memory
- **Constraints:**
  - `distinctInstance`: Each task on different instance
  - `memberOf`: Expression-based (e.g., attribute:ecs.instance-type =~ t3.*)
- **Fargate:** AWS handles placement (always spread across AZs)

### Q50: How to migrate from Docker Compose to ECS?
**Answer:**
1. **ECS CLI (legacy):** `ecs-cli compose` translates docker-compose.yml to ECS task definitions
2. **Docker Compose ECS integration:** `docker context create ecs` + `docker compose up`
3. **Manual approach:** Map each service → ECS service/task definition, volumes → EFS, networks → security groups
4. **Considerations:** Replace Docker volumes with EFS, replace Docker networks with security groups/service discovery, replace depends_on with ECS dependsOn
5. **Copilot CLI:** AWS tool that simplifies ECS deployment from Dockerfile


---

## EKS & Kubernetes (Q51-Q90)

### Q51: Explain Kubernetes architecture
**Answer:**
- **Control Plane:** API Server (REST frontend), etcd (distributed key-value store), Scheduler (assigns pods to nodes), Controller Manager (reconciliation loops)
- **Worker Node:** kubelet (pod lifecycle), kube-proxy (network rules via iptables/IPVS), Container Runtime (containerd)
- **Communication:** kubectl → API Server (HTTPS), API Server → kubelet (HTTPS), kubelet → container runtime (CRI)
- **EKS:** AWS manages control plane (HA across 3 AZs), you manage worker nodes

### Q52: What is a Pod? Multi-container patterns?
**Answer:**
- Smallest deployable unit. One or more containers sharing network namespace + storage
- **Sidecar:** Logging agent, monitoring, proxy (Envoy) alongside main container
- **Init container:** Runs before main containers (DB migration, config download, wait for dependency)
- **Ambassador:** Proxy outbound connections (simplify connecting to external services)
- **Adapter:** Transform output format (normalize logs/metrics)
- Containers in pod share localhost, can communicate via volumes

### Q53: Deployment vs StatefulSet vs DaemonSet
**Answer:**
- **Deployment:** Stateless apps, any pod can be replaced, rolling updates, scale up/down freely
- **StatefulSet:** Stateful apps, ordered deploy/delete (pod-0 first), stable network ID (pod-0.service), dedicated PVC per pod. Use for: databases, Kafka, ZooKeeper
- **DaemonSet:** One pod per node automatically. Use for: log collection (Fluent Bit), monitoring (node exporter), kube-proxy, CSI drivers
- **Decision:** Default → Deployment. Need stable identity/storage → StatefulSet. Need on every node → DaemonSet

### Q54: Kubernetes Service types explained
**Answer:**
- **ClusterIP (default):** Internal-only virtual IP. Accessible within cluster. Use for inter-service communication
- **NodePort:** Exposes on each node's IP at static port (30000-32767). External access via NodeIP:NodePort
- **LoadBalancer:** Provisions cloud provider LB (ALB/NLB in AWS). External access with single endpoint
- **ExternalName:** CNAME to external DNS name. No proxying. Use for: external database references
- **Headless (ClusterIP: None):** No virtual IP. DNS returns pod IPs directly. Use with StatefulSets

### Q55: How does Ingress work?
**Answer:**
- **Ingress resource:** Rules for HTTP/HTTPS routing (host-based, path-based)
- **Ingress Controller:** Implements rules (NGINX, AWS ALB Ingress Controller / AWS Load Balancer Controller)
- **Features:** TLS termination, path rewrites, rate limiting, authentication
- **AWS:** ALB Ingress Controller creates ALB per Ingress (or shared with IngressGroup)
- **vs Service LoadBalancer:** Ingress handles multiple services on one LB with routing rules (cost-effective)

### Q56: ConfigMaps vs Secrets
**Answer:**
- **ConfigMap:** Non-sensitive configuration (feature flags, URLs, config files). Stored as plain text
- **Secret:** Sensitive data (passwords, tokens, keys). Base64 encoded (NOT encrypted by default!)
- **Usage:** Environment variables or volume mounts
- **Encryption:** Enable encryption at rest (KMS in EKS) for Secrets. Or use External Secrets Operator
- **Hot reload:** Volume-mounted ConfigMaps auto-update (~1 min). Env vars require pod restart
- **Limit:** 1 MB max size for both

### Q57: Resource Requests vs Limits and QoS classes
**Answer:**
- **Requests:** Minimum guaranteed resources. Used by scheduler for placement decisions
- **Limits:** Maximum allowed. Exceeding CPU → throttled. Exceeding memory → OOMKilled
- **QoS Classes:**
  - **Guaranteed:** requests == limits (for both CPU+memory). Last to be evicted
  - **Burstable:** requests < limits. Evicted after BestEffort
  - **BestEffort:** No requests or limits set. First to be evicted under pressure
- **Best practice:** Always set requests. Set limits for memory. CPU limits optional (debated)

### Q58: How does HPA (Horizontal Pod Autoscaler) work?
**Answer:**
- Controller loop every 15s: current metric / desired metric = ratio → scale
- **Metrics:** CPU utilization (default), memory, custom (Prometheus), external (SQS depth)
- **Formula:** desiredReplicas = ceil(currentReplicas * currentMetric / targetMetric)
- **Behavior:** scaleUp/scaleDown policies (stabilizationWindow, rate limiting)
- **Example:** Target CPU 50%, current 80%, replicas 3 → desired = ceil(3 * 80/50) = 5
- **Cooldown:** stabilizationWindowSeconds (default 300s for scale-down, 0 for scale-up)

### Q59: Cluster Autoscaler vs Karpenter
**Answer:**
- **Cluster Autoscaler:** Works with ASG/managed node groups. Scales node groups up (pending pods) / down (underutilized nodes). Slower (minutes)
- **Karpenter:** AWS-native, no ASGs needed. Provisions right-sized nodes directly. Faster (seconds). Supports consolidation (bin-packing running pods to fewer nodes)
- **Karpenter advantages:** Instance type flexibility, faster provisioning, automatic node consolidation, drift detection
- **When to use CA:** Non-AWS clusters, existing ASG-based infrastructure
- **When to use Karpenter:** New EKS clusters, need cost optimization, heterogeneous workloads

### Q60: Explain RBAC in Kubernetes
**Answer:**
- **Role:** Permissions within a namespace (verbs: get, list, create, update, delete, patch, watch)
- **ClusterRole:** Cluster-wide permissions (nodes, PVs, namespaces)
- **RoleBinding:** Grants Role to user/group/SA in a namespace
- **ClusterRoleBinding:** Grants ClusterRole cluster-wide
- **Subjects:** User, Group, ServiceAccount
- **EKS:** aws-auth ConfigMap maps IAM users/roles to K8s groups. Or use EKS access entries (newer)
- **Best practice:** Least privilege, use namespace-scoped Roles where possible

### Q61: Network Policies - how do they work?
**Answer:**
- Default: All pods can communicate with all pods (flat network)
- Network Policies restrict traffic at pod level (L3/L4)
- **Spec:** podSelector (which pods policy applies to), ingress/egress rules (from/to + ports)
- **Selectors:** podSelector, namespaceSelector, ipBlock (CIDR)
- **Enforcement:** Requires CNI that supports it (Calico, Cilium, AWS VPC CNI with network policy support)
- **Default deny:** Create policy selecting all pods with empty ingress = deny all incoming

### Q62: Debug a pod in CrashLoopBackOff
**Answer:**
1. `kubectl describe pod <name>` → check Events, Last State, Exit Code
2. `kubectl logs <pod> --previous` → logs from crashed container
3. **Exit codes:** 1=app error, 137=OOMKilled (check memory limits), 139=segfault, 126=permission denied, 127=command not found
4. Check if **readiness/liveness probes** failing too aggressively
5. Check **ConfigMaps/Secrets** exist and are correct
6. Check **image** is correct and pullable (ImagePullBackOff is different)
7. `kubectl debug` → run ephemeral container for live debugging
8. Common causes: missing env vars, wrong config, insufficient resources, dependency not ready

### Q63: Pod Disruption Budgets (PDB)
**Answer:**
- Limit number of pods disrupted simultaneously during **voluntary disruptions** (node drain, cluster upgrade)
- **minAvailable:** Minimum pods that must remain running (number or percentage)
- **maxUnavailable:** Maximum pods that can be down simultaneously
- Set one, not both
- **Does NOT protect against:** OOMKill, node failure, container crash (involuntary)
- **Use case:** `minAvailable: 2` for 3-replica service ensures at least 2 always running during upgrades
- Blocks `kubectl drain` if violation would occur

### Q64: Taints and Tolerations
**Answer:**
- **Taint on Node:** "Don't schedule pods here unless they tolerate me"
- **Toleration on Pod:** "I can be scheduled on tainted nodes"
- **Effects:** NoSchedule (hard), PreferNoSchedule (soft), NoExecute (evict existing + prevent new)
- **Use cases:** Dedicated nodes for team/workload, GPU nodes only for ML pods, node maintenance
- **Example:** Taint GPU nodes → only pods with GPU toleration get scheduled there
- Taints REPEL, Tolerations ALLOW (but don't guarantee - use with nodeAffinity for that)

### Q65: Node Affinity vs Pod Affinity/Anti-Affinity
**Answer:**
- **Node Affinity:** Schedule pod on specific nodes (by labels). Replaces nodeSelector with more expressions
  - requiredDuringSchedulingIgnoredDuringExecution (hard)
  - preferredDuringSchedulingIgnoredDuringExecution (soft/weighted)
- **Pod Affinity:** Schedule pod near other pods (same node/AZ). Use: co-locate app + cache
- **Pod Anti-Affinity:** Schedule pod away from other pods. Use: spread replicas across nodes/AZs
- **topologyKey:** node, AZ, region (defines "near/away" boundary)

### Q66: How does EKS manage the control plane?
**Answer:**
- AWS runs control plane across **3 AZs** (HA by default)
- Managed components: API server (2+ instances behind NLB), etcd (3 instances), scheduler, controller manager
- **Automatic:** Patching, scaling, etcd backup, certificate rotation
- **SLA:** 99.95% uptime for API server
- **Access:** Via public endpoint (default), private endpoint, or both
- **Logging:** Control plane logs to CloudWatch (API server, audit, authenticator, controller manager, scheduler)

### Q67: What is IRSA (IAM Roles for Service Accounts)?
**Answer:**
- Fine-grained IAM permissions at pod level (not node level)
- **How:** EKS OIDC provider + IAM role trust policy + ServiceAccount annotation
- **Flow:** Pod uses SA → projected service account token (JWT) → AWS STS AssumeRoleWithWebIdentity → temporary credentials
- **Benefits:** Least privilege (different pods get different permissions), no node-level Instance Profile needed
- **Setup:** 1) Create OIDC provider 2) Create IAM role with trust for SA 3) Annotate SA with role ARN 4) Use SA in pod
- **Newer alternative:** EKS Pod Identity (simpler, no OIDC setup needed)

### Q68: EKS node types - Managed vs Self-managed vs Fargate
**Answer:**
- **Managed Node Groups:** AWS manages provisioning, AMI updates, draining on updates. Uses ASGs. Best for most cases
- **Self-managed:** Full control over AMI, bootstrap, instance types. Use for custom requirements
- **Fargate Profiles:** Serverless pods, no node management. Match pods by namespace+labels. Each pod = own microVM
- **Fargate limitations:** No DaemonSets, no privileged containers, no GPU, no EBS (only EFS), limited to 4 vCPU/30 GB

### Q69: How does AWS VPC CNI plugin work?
**Answer:**
- Each pod gets a **real VPC IP address** (from subnet CIDR)
- Uses ENIs attached to nodes: each ENI has multiple secondary IPs assigned to pods
- **Benefit:** No overlay network, native VPC routing, security groups apply directly
- **Limitation:** Max pods per node = (# ENIs * IPs per ENI) - 1. E.g., m5.large = 29 pods max
- **Prefix delegation:** Assign /28 prefixes instead of individual IPs → more pods per node (110+ pods)
- **Custom networking:** Use different subnet CIDR for pods than nodes (conserve node subnet IPs)

### Q70: AWS Load Balancer Controller
**Answer:**
- Manages ALBs and NLBs for Kubernetes Services and Ingresses
- **Ingress → ALB:** HTTP/HTTPS routing, path-based, host-based, WAF integration
- **Service type LoadBalancer → NLB:** L4 TCP/UDP, static IPs, high performance
- **Features:** Target group binding, IngressGroup (share ALB), SSL redirect, WAF, Shield
- **Annotations:** Control LB behavior (subnets, scheme, SSL cert, target type: ip vs instance)
- **Install:** Helm chart + IAM role (IRSA) with required permissions

### Q71: Explain Helm charts
**Answer:**
- Package manager for Kubernetes (like apt/yum for OS)
- **Chart structure:** Chart.yaml (metadata), values.yaml (defaults), templates/ (K8s manifests with Go templating)
- **Commands:** helm install, upgrade, rollback, uninstall, repo add, search, list
- **Concepts:** Release (installed instance), Repository (chart storage), Values (configuration)
- **Features:** Dependency management, hooks (pre/post install/upgrade), tests
- **Best practice:** Use values.yaml for environment differences, version charts semantically

### Q72: What is ArgoCD and GitOps?
**Answer:**
- **GitOps:** Git as single source of truth for infrastructure/app state. Reconcile cluster to match git
- **ArgoCD:** Kubernetes-native GitOps controller
- **How:** Watch Git repo → compare with cluster state → sync (auto or manual)
- **Features:** UI dashboard, RBAC, SSO, multi-cluster, app-of-apps pattern, sync waves
- **Benefits:** Audit trail (git history), rollback (git revert), declarative, self-healing
- **vs kubectl apply in CI:** ArgoCD detects drift and self-heals. CI-based doesn't

### Q73: Canary deployments in Kubernetes
**Answer:**
- **Basic:** Two Deployments (stable + canary) with same label. Service routes to both. Control ratio by replica count
- **Istio/App Mesh:** VirtualService with weighted routing (95% stable, 5% canary). Fine-grained control
- **Argo Rollouts:** Native canary strategy with steps (setWeight, pause, analysis). Automated promotion/rollback based on metrics
- **Flagger:** Progressive delivery with metrics analysis (Prometheus, Datadog). Auto-promote or rollback
- **AWS:** App Mesh + EKS, or ALB weighted target groups

### Q74: Init containers and use cases
**Answer:**
- Run to completion before main containers start. Sequential (init1 → init2 → main)
- **Use cases:** Wait for dependency (DB ready), download config from S3, database migration, git clone
- **Characteristics:** Run once, must succeed (exit 0) for pod to proceed, separate resource limits
- **vs Sidecar:** Init runs once and exits. Sidecar runs alongside main container continuously
- **Example:** Init container runs `until nc -z db-service 5432; do sleep 2; done` to wait for DB

### Q75: Persistent Volumes (PV) and Claims (PVC)
**Answer:**
- **PV:** Cluster-level storage resource (actual disk). Created by admin or dynamically via StorageClass
- **PVC:** Namespace-level request for storage. Pod references PVC, PVC binds to suitable PV
- **StorageClass:** Dynamic provisioning template (provisioner, parameters, reclaimPolicy)
- **Reclaim Policy:** Retain (keep data), Delete (remove PV+disk), Recycle (deprecated)
- **Access Modes:** ReadWriteOnce (single node), ReadOnlyMany, ReadWriteMany (EFS), ReadWriteOncePod (single pod)
- **Binding:** PVC matches PV by capacity, access mode, storage class, labels

### Q76: EBS CSI Driver in EKS
**Answer:**
- **What:** Enables EBS volumes as Kubernetes persistent storage
- **Install:** EKS add-on or Helm chart + IRSA with EC2/EBS permissions
- **StorageClass:** provisioner = ebs.csi.aws.com, parameters (type: gp3, encrypted: true, iops, throughput)
- **volumeBindingMode:** WaitForFirstConsumer (bind when pod scheduled, ensures same AZ)
- **Snapshots:** VolumeSnapshot CRD for point-in-time backups
- **Limitation:** EBS = ReadWriteOnce (single node). For ReadWriteMany use EFS CSI

### Q77: Namespaces and Resource Quotas
**Answer:**
- **Namespaces:** Logical cluster division. Isolation boundary for RBAC, network policies, resource quotas
- **ResourceQuota:** Limit total resources per namespace (cpu, memory, pods count, PVCs, services)
- **LimitRange:** Default and max/min per container in namespace
- **Best practice:** Namespace per team/environment + ResourceQuota to prevent noisy neighbor
- **Default namespaces:** default, kube-system, kube-public, kube-node-lease

### Q78: Service Mesh comparison - Istio vs Linkerd vs App Mesh
**Answer:**
| Feature | Istio | Linkerd | App Mesh |
|---------|-------|---------|----------|
| Proxy | Envoy | linkerd2-proxy (Rust) | Envoy |
| Complexity | High | Low | Medium |
| Performance | Good | Best (lightest proxy) | Good |
| Features | Most complete | Core features | AWS-integrated |
| mTLS | Yes | Yes (auto) | Yes |
| AWS Integration | Manual | Manual | Native |
| **Best for** | Feature-rich needs | Simplicity | AWS-native |

### Q79: Zero-downtime rolling updates
**Answer:**
1. **Readiness probe:** New pods must pass before receiving traffic
2. **Rolling update strategy:** maxSurge=1, maxUnavailable=0 (always have full capacity)
3. **preStop hook:** Add sleep (5s) to allow load balancer to deregister
4. **PDB:** Ensure minimum available during update
5. **Graceful shutdown:** Handle SIGTERM, drain connections, finish in-flight requests
6. **Health check grace period:** Give new pods time to warm up
7. **Progressive:** Use canary or blue/green for safer updates

### Q80: Sidecar pattern with examples
**Answer:**
- **What:** Helper container running alongside main container in same pod
- **Examples:**
  - Envoy proxy (service mesh traffic management)
  - Fluent Bit (log forwarding to CloudWatch/ES)
  - CloudWatch agent (custom metrics)
  - Vault agent (secrets injection)
  - X-Ray daemon (distributed tracing)
- **Communication:** Via localhost (shared network) or shared volume (filesystem)
- **Lifecycle:** Runs for entire pod lifetime. Issue: sidecar may outlive main container (KEP-753 sidecar containers feature)

### Q81: What are Kubernetes Operators?
**Answer:**
- **Pattern:** Custom controller + CRD that encodes operational knowledge
- **Purpose:** Automate complex application lifecycle (install, scale, backup, upgrade, failover)
- **Examples:** Prometheus Operator, MySQL Operator, Elasticsearch Operator, cert-manager
- **Build with:** Operator SDK (Go), kubebuilder, KUDO, Ansible/Helm-based operators
- **Maturity levels:** Basic install → Seamless upgrades → Full lifecycle → Deep insights → Auto pilot
- **When to use:** Complex stateful applications that need operational automation

### Q82: Secrets management in EKS
**Answer:**
- **Built-in:** K8s Secrets (base64, not encrypted by default) + enable encryption at rest (KMS envelope encryption)
- **External Secrets Operator:** Sync from AWS Secrets Manager/SSM → K8s Secrets automatically
- **AWS Secrets Store CSI Driver:** Mount secrets as files directly from Secrets Manager/SSM
- **Sealed Secrets (Bitnami):** Encrypt secrets for git storage, only controller can decrypt
- **HashiCorp Vault:** Full secret lifecycle management, dynamic secrets, Agent injector sidecar
- **Best practice:** Never commit secrets to git. Use external secret store + sync operator

### Q83: Liveness, readiness, and startup probes
**Answer:**
- **Liveness:** Is container alive? Failure → container restart. Use: detect deadlocks
- **Readiness:** Is container ready to serve traffic? Failure → remove from Service endpoints. Use: detect temporary inability
- **Startup:** Is container started? Failure → restart. Use: slow-starting containers (prevents liveness from killing during startup)
- **Types:** httpGet (path, port), tcpSocket (port), exec (command), grpc
- **Config:** initialDelaySeconds, periodSeconds, failureThreshold, timeoutSeconds
- **Common mistake:** Using liveness where readiness should be used (causes unnecessary restarts)

### Q84: What is KEDA?
**Answer:**
- **Kubernetes Event-Driven Autoscaling** - scales based on event sources
- **How:** KEDA operator + ScaledObject CRD → creates/manages HPA with external metrics
- **Scalers (60+):** AWS SQS (queue depth), Kafka (consumer lag), Prometheus (query), Cron, Azure Service Bus, RabbitMQ, Redis, HTTP
- **Scale to zero:** Unlike HPA, KEDA can scale deployments to 0 replicas (save costs)
- **Use cases:** Event-driven microservices, job processors, queue consumers, scheduled workloads
- **Example:** Scale pods based on SQS ApproximateNumberOfMessages

### Q85: How to monitor a Kubernetes cluster?
**Answer:**
- **Metrics:** metrics-server (kubectl top), Prometheus + Grafana (full solution), CloudWatch Container Insights
- **Logging:** Fluent Bit DaemonSet → CloudWatch Logs/S3/Elasticsearch
- **Tracing:** AWS X-Ray, Jaeger, OpenTelemetry (ADOT collector)
- **Key metrics:** Pod CPU/memory, node utilization, API server latency, etcd health, pod restarts, pending pods
- **Alerting:** Prometheus Alertmanager, CloudWatch Alarms
- **Dashboards:** Grafana with Kubernetes mixin dashboards

### Q86: Pod Security Standards
**Answer:**
- **Privileged:** Unrestricted (allow everything). For system workloads (kube-system)
- **Baseline:** Prevent known privilege escalations. Blocks: hostNetwork, hostPID, privileged containers, hostPath
- **Restricted:** Heavily restricted. Requires: non-root, drop ALL capabilities, read-only root filesystem, seccomp
- **Enforcement:** Pod Security Admission controller (built-in since 1.25) with modes: enforce, audit, warn
- **Per namespace:** Label `pod-security.kubernetes.io/enforce: restricted`

### Q87: cert-manager in Kubernetes
**Answer:**
- Automates TLS certificate management (issue, renew, revoke)
- **Issuers:** Let's Encrypt (ACME), Vault, self-signed, CA, Venafi
- **CRDs:** Issuer/ClusterIssuer, Certificate, CertificateRequest
- **ACME challenges:** HTTP-01 (Ingress), DNS-01 (Route 53, CloudFlare)
- **Auto-renewal:** Renews before expiry (configurable, default 30 days before)
- **Integration:** Annotate Ingress with `cert-manager.io/cluster-issuer` for automatic cert creation

### Q88: Multi-tenancy in Kubernetes
**Answer:**
- **Namespace-based (soft):** Namespace per tenant + RBAC + ResourceQuota + NetworkPolicy + LimitRange
- **Cluster-based (hard):** Separate cluster per tenant (most isolation, highest cost)
- **Virtual clusters (vcluster):** Virtual K8s clusters inside namespaces (balance of isolation + efficiency)
- **Key controls:** RBAC (strict per-namespace), Network Policies (deny cross-namespace by default), Pod Security (restrict privileges), Resource Quotas (fair sharing)
- **Tools:** Capsule, Loft, Hierarchical Namespaces Controller

### Q89: kubectl apply vs kubectl create
**Answer:**
- **create:** Imperative. Creates resource. Fails if already exists. No tracking of previous state
- **apply:** Declarative. Creates if not exists, updates if exists. Tracks last-applied annotation for 3-way merge
- **apply benefits:** Idempotent, GitOps-friendly, tracks changes, supports partial updates
- **create use case:** One-off resources, scripts that should fail on duplicates
- **Best practice:** Always use `apply` for production workflows, `create` only for debugging/one-offs

### Q90: Disaster recovery for EKS
**Answer:**
- **Control plane:** AWS manages HA (3 AZs). For regional failure → multi-region clusters
- **etcd:** AWS manages backups. For cluster recreation → backup CRDs and configs with Velero
- **Workloads:** Velero (backup K8s resources + PVs), GitOps (redeploy from git to new cluster)
- **Data:** EBS snapshots (cross-region), EFS replication, application-level backup to S3
- **Strategy:** Active-Passive (standby cluster) or Active-Active (Route 53 weighted/failover)
- **RTO/RPO:** GitOps + Velero PV backups = RPO minutes, RTO 15-30 min (depends on app startup)
- **Multi-region tools:** EKS Blueprints, ArgoCD multi-cluster


---

## API Gateway & Service Mesh (Q91-Q110)

### Q91: AWS API Gateway types - REST vs HTTP API
**Answer:**
| Feature | REST API | HTTP API |
|---------|----------|----------|
| Price | $3.50/million | $1.00/million |
| Latency | Higher (~29ms) | Lower (~10ms) |
| Caching | Yes | No |
| WAF | Yes | No |
| Request Validation | Yes | No |
| Resource Policies | Yes | No |
| Lambda Authorizer | Yes | Yes |
| JWT Authorizer | No | Yes (native) |
| **Choose REST** for full features. **Choose HTTP** for simple, fast, cheap APIs.

### Q92: API Gateway authorization options
**Answer:**
- **IAM Authorization:** SigV4 signed requests. For AWS-to-AWS or SDK-based clients
- **Lambda Authorizer:** Custom logic (validate JWT, call external IdP). Return IAM policy. Caching available
- **Cognito Authorizer (REST):** Validates JWT from Cognito User Pool. Zero code auth
- **JWT Authorizer (HTTP):** Native JWT validation (any OIDC provider). Simplest for HTTP API
- **API Keys:** Not for auth (just tracking/throttling). Combine with usage plans
- **Resource Policy:** IP/VPC/account restrictions (like S3 bucket policy)

### Q93: How does Lambda Authorizer work?
**Answer:**
- **Token-based:** Receives token (Authorization header) → Lambda validates → returns IAM policy + principal
- **Request-based:** Receives entire request (headers, query strings, context) → Lambda evaluates → returns policy
- **Response format:** `{ principalId, policyDocument: { Statement: [{ Effect, Action, Resource }] }, context: {} }`
- **Caching:** TTL 0-3600s. Cached by token value (token-based) or request parameters (request-based)
- **Use cases:** Custom JWT validation, API key lookup in DynamoDB, IP-based rules, multi-factor checks

### Q94: API Gateway throttling and rate limiting
**Answer:**
- **Account level:** 10,000 RPS across all APIs, 5,000 burst
- **Stage/Method level:** Override with lower limits per API/method
- **Usage Plans + API Keys:** Per-customer rate limiting (rate + burst + quota)
- **Algorithm:** Token bucket (rate = refill speed, burst = bucket size)
- **Response:** 429 Too Many Requests
- **Handling:** Client-side exponential backoff, SQS queue for smoothing, caching to reduce calls
- **Note:** Cannot increase beyond account limit without AWS support request

### Q95: API Gateway caching
**Answer:**
- Stage-level cache (REST API only): 0.5 GB to 237 GB
- **TTL:** 0-3600 seconds (default 300s)
- **Cache key:** Resource path + configured headers/query strings
- **Invalidation:** Client sends `Cache-Control: max-age=0` (requires IAM permission), or flush from console
- **Per-key caching:** Use Lambda authorizer context to cache per-user
- **Cost:** $0.020/hr (0.5 GB) to $3.80/hr (237 GB). Not free!
- **Best practice:** Cache stable responses, exclude user-specific endpoints

### Q96: What are VPC Links?
**Answer:**
- Connect API Gateway to private resources in VPC (ALB, NLB, EC2, ECS)
- **REST API:** VPC Link backed by NLB (Network Load Balancer)
- **HTTP API:** VPC Link backed by ALB, NLB, or Cloud Map service
- **Flow:** API Gateway → VPC Link → NLB/ALB → private service
- **Use case:** Expose internal microservices publicly without putting them in public subnet
- **Security:** Private services stay private, only accessible via API Gateway

### Q97: API versioning strategies
**Answer:**
- **URL path:** /v1/users, /v2/users (most common, clear, separate deployments)
- **Query parameter:** /users?version=2 (flexible, single endpoint)
- **Header:** Accept: application/vnd.api.v2+json (HTTP standard, but hidden)
- **Stage-based (API Gateway):** Different stages (v1, v2) pointing to different backends
- **Custom domain + base path:** api.com/v1/ → REST API v1, api.com/v2/ → REST API v2
- **Best practice:** URL path versioning for public APIs. Header versioning for internal APIs

### Q98: WebSocket API use cases
**Answer:**
- **What:** Persistent two-way connection between client and backend
- **Routes:** $connect (on connect), $disconnect (on close), $default (unmatched), custom routes (matched by JSON field)
- **Management:** @connections API to send messages to specific clients (connectionId)
- **Use cases:** Real-time chat, live dashboards, gaming, IoT telemetry, collaborative editing, notifications
- **Backend:** Lambda, HTTP, or AWS service integration per route
- **Scaling:** Managed by AWS, handles thousands of concurrent connections

### Q99: API Gateway stages and stage variables
**Answer:**
- **Stages:** Named references to deployment (dev, staging, prod). Each has own URL
- **Stage variables:** Key-value pairs per stage (like env vars). Access via `${stageVariables.varName}`
- **Use cases:** Point to different Lambda aliases (dev→$LATEST, prod→stable), different backend URLs, feature flags
- **Deployment:** Create deployment → deploy to stage. Can enable canary on stage
- **Canary:** Split traffic % between current and canary deployment on same stage

### Q100: Canary deployments in API Gateway
**Answer:**
- Enable canary on a stage → new deployment goes to canary (% of traffic)
- **Steps:** Deploy to canary → monitor metrics/logs → promote (replace stage) or rollback (delete canary)
- **Configuration:** canarySettings { percentTraffic: 10, stageVariableOverrides, useStageCache }
- **Monitoring:** Separate CloudWatch metrics for canary vs stable
- **Limitation:** REST API only. HTTP API uses Lambda aliases + weighted routing instead

### Q101: What is AWS App Mesh?
**Answer:**
- Managed service mesh using Envoy proxy sidecars
- **Components:** Mesh, Virtual Service, Virtual Node, Virtual Router, Virtual Gateway, Routes
- **Features:** Traffic routing (weighted, path, header), retries, timeouts, circuit breaking, mTLS, observability
- **Integration:** ECS (sidecar in task def), EKS (controller + sidecar injection), EC2
- **Benefit:** Standardized service communication without code changes

### Q102: How does Envoy proxy work in App Mesh?
**Answer:**
- **Sidecar:** Runs alongside application container, intercepts all inbound/outbound traffic
- **Config:** App Mesh control plane pushes configuration to Envoy via xDS API
- **Features:** Load balancing, circuit breaking, retry, timeout, TLS, observability (metrics/tracing/logging)
- **Traffic interception:** iptables rules redirect traffic through Envoy (application unaware)
- **Health checking:** Envoy performs active health checks to upstream services

### Q103: Circuit breaking in service mesh
**Answer:**
- **Purpose:** Prevent cascade failures by stopping requests to unhealthy service
- **App Mesh config:** maxConnections, maxPendingRequests, maxRequests per virtual node
- **States:** Closed (normal) → Open (all requests fail fast) → Half-Open (probe with limited requests)
- **When triggers:** Connection limit exceeded, pending request limit exceeded
- **Effect:** Client gets immediate 503 instead of waiting for timeout
- **Complement with:** Retries (for transient failures) + timeouts (for slow responses)

### Q104: What is mutual TLS (mTLS)?
**Answer:**
- Both client AND server authenticate each other via certificates (normal TLS = only client verifies server)
- **In App Mesh:** Configure TLS validation contexts on virtual nodes, certificates from ACM or file-based
- **Benefits:** Zero-trust networking, service identity verification, encrypted traffic between services
- **Implementation:** Mesh-level (all services) or per-virtual-node (selective)
- **Certificate sources:** ACM Private CA (managed), file-based (cert-manager, Vault)

### Q105: Traffic routing in App Mesh
**Answer:**
- **Weighted routing:** 90% v1, 10% v2 (canary/blue-green)
- **Path-based:** /api/v1/* → service-v1, /api/v2/* → service-v2
- **Header-based:** x-version: beta → beta-service (A/B testing)
- **Retry policy:** maxRetries, perRetryTimeout, httpRetryEvents (5xx, connection-error)
- **Timeout:** per-request timeout, idle timeout
- **Configuration:** Virtual Router → Routes with match conditions and weighted targets

### Q106: API Gateway vs Service Mesh - when to use which?
**Answer:**
- **API Gateway:** External/edge traffic (internet → services). Authentication, rate limiting, request transformation, public API management
- **Service Mesh:** Internal traffic (service → service). mTLS, circuit breaking, observability, canary routing between internal services
- **Both in architecture:** Internet → API Gateway → Service A → (App Mesh) → Service B
- **Overlap:** Both do routing, retries, timeouts. But different scope (north-south vs east-west)
- **Simple rule:** API Gateway for ingress, Service Mesh for internal communication

### Q107: Retry policies in App Mesh
**Answer:**
- **Configure per-route:** maxRetries, perRetryTimeout, retryOn (httpRetryEvents + tcpRetryEvents)
- **HTTP retry events:** server-error (5xx), gateway-error (502/503/504), client-error (4xx), stream-error
- **TCP retry events:** connection-error
- **perRetryTimeout:** Max time to wait for each retry attempt
- **Backoff:** Envoy uses exponential backoff with jitter between retries
- **Best practice:** Retry idempotent operations only (GET, PUT with idempotency key). Don't retry POST blindly

### Q108: Virtual Gateway in App Mesh
**Answer:**
- Entry point for traffic coming INTO the mesh from outside
- Replaces the need for a separate ingress load balancer + manual routing
- **Features:** TLS termination, routing to virtual services inside mesh
- **Use case:** External ALB → Virtual Gateway → routes to internal services
- Works with ECS and EKS
- Essentially an Envoy proxy running as the mesh ingress point

### Q109: Observability in service mesh
**Answer:**
- **Metrics:** Envoy emits metrics (request count, latency, error rate) → CloudWatch or Prometheus
- **Tracing:** X-Ray or Jaeger (Envoy generates spans automatically for all proxied requests)
- **Logging:** Access logs per virtual node/gateway (format customizable)
- **Benefits:** No code instrumentation needed - proxy captures everything automatically
- **CloudWatch Container Insights:** ECS/EKS App Mesh metrics integration
- **Third-party:** Datadog, New Relic, Dynatrace can scrape Envoy metrics

### Q110: Design multi-tenant SaaS API
**Answer:**
- **Authentication:** Cognito User Pool per tenant OR shared pool with custom attributes (tenantId)
- **Authorization:** Lambda authorizer extracts tenantId from JWT → inject into context
- **Isolation:** API Gateway Usage Plans (per-tenant API keys with individual rate limits/quotas)
- **Routing:** Custom domain per tenant (tenant1.api.com) with base path mapping
- **Backend:** tenantId in request context → DynamoDB partition key / RDS row-level security
- **Throttling:** Different tiers (Free: 100 RPS, Pro: 1000 RPS, Enterprise: 10000 RPS)
- **Monitoring:** Per-tenant metrics via API key dimension in CloudWatch

---

## CloudFront & WAF (Q111-Q130)

### Q111: How does CloudFront work?
**Answer:**
- **Flow:** User → nearest Edge Location (400+) → Regional Edge Cache (13) → Origin (S3/ALB/EC2)
- Cache hit: serve from edge (lowest latency). Cache miss: fetch from origin, cache at edge
- **Benefits:** Reduce latency (serve from edge), reduce origin load, DDoS protection, HTTPS termination
- **Distribution:** Configuration entity. Contains origins, behaviors (path patterns), cache settings, security

### Q112: CloudFront Functions vs Lambda@Edge
**Answer:**
| | CloudFront Functions | Lambda@Edge |
|---|---|---|
| Events | Viewer request/response only | All 4 (viewer + origin req/resp) |
| Runtime | JavaScript (ES 5.1) | Node.js, Python |
| Duration | <1ms | 5-30 seconds |
| Memory | 2 MB | 128-10240 MB |
| Network/FS | No | Yes |
| Scale | Millions RPS | Thousands RPS |
| Price | $0.10/million | $0.60/million + duration |
| **Use CF Functions:** URL rewrites, header manipulation, cache key normalization |
| **Use Lambda@Edge:** Auth with external IdP, image resize, origin selection, SEO |

### Q113: CloudFront cache key and policies
**Answer:**
- **Cache key:** Determines what makes a unique cached object (URL + specified headers/cookies/query strings)
- **Cache Policy:** What's in cache key + TTL settings. Minimizing cache key = better hit ratio
- **Origin Request Policy:** What's forwarded to origin (separate from cache key). Can forward without affecting caching
- **Best practice:** Minimal cache key (URL + few query params), forward other needed headers via Origin Request Policy
- **Default:** Only URL path is cache key. Adding headers/cookies reduces hit ratio

### Q114: Signed URLs vs Signed Cookies
**Answer:**
- **Signed URLs:** Per-file access. New URL for each file. Contains policy (expiry, IP). Good for: individual file downloads, S3 direct access
- **Signed Cookies:** Multi-file access. Set cookie once → access multiple files. Good for: video streaming (multiple segments), entire website sections
- **Creating:** Use CloudFront key pair (trusted signer) or trusted key group
- **Policy:** Custom (IP range, date/time range, path pattern) or Canned (simpler, single file)
- **Choose Signed URL when:** RTMP, client doesn't support cookies, restrict per-file

### Q115: What is Origin Access Control (OAC)?
**Answer:**
- Restricts S3 bucket access to ONLY CloudFront (users can't bypass CDN to access S3 directly)
- **Replaces:** OAI (Origin Access Identity) - legacy, limited features
- **OAC advantages:** Supports all S3 features (SSE-KMS, all regions), better security model
- **Setup:** Create OAC → assign to distribution origin → update S3 bucket policy to allow CloudFront service principal
- **Bucket policy:** Allow `s3:GetObject` for `cloudfront.amazonaws.com` with condition on distribution ARN

### Q116: How to improve cache hit ratio?
**Answer:**
1. **Minimize cache key:** Remove unnecessary headers/cookies/query strings from cache key
2. **Origin Shield:** Additional caching layer between edge and origin (centralizes origin requests)
3. **Normalize:** Sort query strings, normalize Accept-Encoding (CloudFront does this by default)
4. **Versioned URLs:** Use /v2/style.css instead of cache invalidation
5. **Increase TTL:** Longer cache = more hits (if content doesn't change frequently)
6. **Remove Vary header:** Or ensure consistent values (Vary causes cache fragmentation)
7. **Forward only needed cookies:** Whitelist specific cookies instead of all

### Q117: What is Origin Shield?
**Answer:**
- Additional caching layer between regional edge caches and your origin
- **Single point:** All cache misses go through one region before hitting origin
- **Benefits:** Higher cache hit ratio, reduced origin load, reduced origin costs (fewer requests)
- **Best for:** Origins with high cost (compute-heavy), multi-region viewers, origins not near an edge location
- **Selection:** Choose Origin Shield region closest to your origin
- **Cost:** Additional per-request charges ($0.0090/10K requests)

### Q118: CloudFront Origin Groups (failover)
**Answer:**
- Primary origin + Secondary (failover) origin
- **Trigger:** CloudFront fails over when primary returns specified error codes (500, 502, 503, 504, 403, 404)
- **Use case:** S3 primary (us-east-1) + S3 secondary (eu-west-1) for regional failover
- **Limitation:** Origin group within single distribution. Not cross-distribution
- **Health:** CloudFront doesn't actively health-check origins. Failover is per-request based on response code

### Q119: What is AWS WAF?
**Answer:**
- Web Application Firewall: protects against common web exploits (SQL injection, XSS, bot attacks)
- **Where:** Attach to CloudFront, ALB, API Gateway, AppSync, Cognito User Pool
- **Structure:** Web ACL → Rule Groups → Rules → Match Statements → Actions
- **Actions:** Allow, Block, Count (monitoring), CAPTCHA, Challenge
- **Pricing:** $5/Web ACL + $1/rule + $0.60/million requests

### Q120: WAF rule types
**Answer:**
- **Regular rules:** Match conditions (IP, geo, string match, regex, size, SQL injection, XSS)
- **Rate-based rules:** Block IPs exceeding threshold per 5-minute window (min 100 requests). Auto-DDoS protection
- **Managed Rule Groups:** Pre-built (AWS Core, SQL, XSS, Bad Inputs, Bot Control, ATP)
- **Rule group:** Collection of rules (reusable, managed or custom)
- **Priority:** Lower number evaluated first. First matching rule action applies (exception: Count continues evaluation)

### Q121: How to protect against DDoS?
**Answer:**
- **Layer 3/4:** AWS Shield Standard (free, automatic), Shield Advanced ($3000/mo, DRT support)
- **Layer 7:** WAF rate-based rules, Bot Control, Challenge/CAPTCHA
- **Architecture:** Route 53 (anycast) → CloudFront (absorb at edge) → WAF (filter) → ALB → EC2
- **Best practices:** All resources behind CloudFront, rate limiting, geo-blocking, IP reputation lists
- **Shield Advanced:** DDoS cost protection (won't charge for scaling during attack), 24/7 DRT team, health-based detection

### Q122: AWS Shield Standard vs Advanced
**Answer:**
| Feature | Standard | Advanced |
|---------|----------|----------|
| Cost | Free | $3,000/month |
| Protection | L3/L4 | L3/L4/L7 |
| Detection | Always-on | Enhanced (health-based) |
| Mitigation | Automatic | Automatic + DRT team |
| Visibility | None | Real-time metrics, attack forensics |
| Cost protection | No | Yes (scaling cost absorbed) |
| WAF included | No | Yes (WAF fees included) |
| SLA credits | No | Yes |

### Q123: Bot management with WAF
**Answer:**
- **Bot Control (managed rule group):** Categorizes bots (verified: GoogleBot, unverified, automated browser)
- **Common level:** Block known bad bots, allow verified (search engines)
- **Targeted level:** Detect sophisticated bots (distributed, rotating IPs, browser mimicking)
- **Actions:** Block, CAPTCHA, Challenge (silent browser challenge), Count
- **Challenge token:** Verify browser legitimacy without user interaction
- **Custom:** Combine rate-based + IP reputation + request pattern rules for custom bot detection

### Q124: WAF rule priority and evaluation
**Answer:**
- Rules evaluated in **priority order** (lower number = first)
- First rule with matching condition **takes action** (Allow/Block terminates evaluation)
- **Count** action: Logs match but continues evaluation (monitoring mode)
- **Labels:** Rule can add label → subsequent rules can match on labels (chaining logic)
- **Default action:** Applied if no rule matches (usually Allow)
- **Best practice:** Deny rules first (lower priority number), allow rules after, default action = allow

### Q125: WAF blocking legitimate traffic - troubleshooting
**Answer:**
1. **Enable logging:** WAF logs to S3/CloudWatch/Kinesis Firehose with full request details
2. **Count mode:** Switch blocking rule to Count to see matches without blocking
3. **Sampled requests:** View matched requests in WAF console (last 3 hours)
4. **Identify rule:** terminatingRuleId in logs shows which rule blocked
5. **Scope down:** Add exclusions (whitelist IPs, specific paths, specific user-agents)
6. **Custom response:** Return 200 with info instead of 403 for debugging
7. **Label match:** Use labels to add exceptions for specific traffic patterns

### Q126: WAF labels
**Answer:**
- **What:** Tags added to requests by rules. Don't take action themselves
- **Purpose:** Enable rule chaining logic (match in one rule, act in another)
- **Namespace:** `awswaf:managed:aws:core-rule-set:SizeRestrictions_Body`
- **Use case:** Bot Control labels as "bot:verified:googlebot" → subsequent rule allows labeled requests
- **Custom labels:** Your rules can apply labels. Format: `awswaf:<account>:<webacl>:<custom-label>`
- **Power:** Combine multiple signals before taking action (IP + pattern + rate = block)

### Q127: Serving dynamic content via CloudFront
**Answer:**
- CloudFront accelerates ALL content, not just static (TCP optimization, connection reuse, edge SSL termination)
- **TTL=0:** Forward to origin every time BUT reuses persistent connection (still faster than direct)
- **Dynamic content benefits:** Reduced round trips (edge SSL), optimized routes (AWS backbone), connection reuse to origin
- **Headers/Cookies forwarding:** Forward needed ones via Origin Request Policy (without caching them)
- **Cache behavior:** Static (.js, .css) → long TTL. Dynamic (API, HTML) → short/zero TTL

### Q128: CloudFront price classes
**Answer:**
- **All (default):** All edge locations globally (best performance, highest cost)
- **200:** All except South America, Australia, some Asia ($0.020-$0.120/GB)
- **100:** Only North America + Europe (cheapest, $0.020-$0.085/GB)
- **Use case:** Price Class 100 for audience primarily in US/EU (significant cost savings)
- **Trade-off:** Higher latency for users in excluded regions (served from farther edge)

### Q129: A/B testing at CDN edge
**Answer:**
- **CloudFront Functions:** Read/set cookie in viewer request → route to different origin path based on cookie. Lightweight
- **Lambda@Edge:** More complex logic (weighted random assignment, persist variant, external config lookup)
- **Implementation:** Viewer request: assign variant (set cookie) → Origin request: modify path/host based on variant
- **Sticky:** Use cookie so user always sees same variant after initial assignment
- **Alternatives:** Feature flag service (LaunchDarkly) at application level

### Q130: Secure premium video content delivery
**Answer:**
- **Signed URLs/Cookies:** Time-limited access, prevent URL sharing
- **Origin Access Control:** S3 only accessible via CloudFront
- **Token authentication:** Lambda@Edge validates token before serving content
- **AES-128 encryption:** HLS encryption (DRM-lite, key rotation)
- **Full DRM:** AWS Elemental MediaConvert + MediaPackage (Widevine, FairPlay, PlayReady)
- **Geo-restriction:** Block countries where no license
- **Watermarking:** Forensic watermarking to trace leaks


---

## IAM & Cognito (Q131-Q155)

### Q131: IAM policy evaluation logic
**Answer:**
- **Order:** Explicit Deny → SCP (Organization) → Permission Boundary → Session Policy → Identity-based + Resource-based policies
- **Result:** Default DENY → check all applicable policies → Explicit DENY overrides everything → Must have explicit ALLOW from applicable policy
- **Key rule:** Any explicit Deny = denied. Need explicit Allow (implicit deny by default)
- **Resource-based + Identity-based:** Either one allowing is sufficient (cross-account: BOTH must allow)

### Q132: IAM Roles vs IAM Users
**Answer:**
- **User:** Long-term credentials (password + access keys). For humans or long-running apps on-prem
- **Role:** Temporary credentials (STS). For services (EC2, Lambda), cross-account, federation
- **Best practice:** Use roles everywhere possible. Users only for console access with MFA
- **Key difference:** Roles don't have passwords/permanent keys. Credentials auto-expire and rotate
- **AssumeRole:** Any entity assumes role → gets temporary credentials (15min-12hr)

### Q133: Cross-account access patterns
**Answer:**
- **IAM Role (recommended):** Account B creates role with trust policy for Account A → Account A users assume it
- **Resource-based policy:** S3 bucket policy, KMS key policy grant access to other account's principal
- **Organizations:** SCPs control what accounts can do. Share resources via RAM
- **Use cases:** Centralized logging (all accounts push to central S3), shared services (central ECR), security account access
- **aws-auth ConfigMap (EKS):** Map IAM roles from other accounts to K8s RBAC

### Q134: Confused deputy problem and prevention
**Answer:**
- **What:** Service A (deputy) is tricked into accessing resources in your account on behalf of attacker
- **Example:** Third-party service assumes your IAM role. Attacker provides their ARN to same service → service accesses YOUR resources
- **Prevention:** External ID condition in trust policy. Service passes External ID → your role checks it matches
- **Trust policy condition:** `"Condition": {"StringEquals": {"sts:ExternalId": "unique-secret-per-customer"}}`
- **Also applies to:** AWS services passing roles (use aws:SourceArn condition)

### Q135: Permission Boundaries
**Answer:**
- **What:** Maximum permissions an IAM entity CAN have (ceiling). Effective = intersection of boundary + identity policy
- **Use case:** Allow developers to create IAM roles but constrain what those roles can do (delegation)
- **Example:** Dev can create Lambda roles, but boundary ensures they can never have S3 admin access
- **Types:** AWS managed or customer managed policy attached as boundary
- **Effective permissions:** Identity policy ∩ Permission boundary ∩ SCP (all must allow)

### Q136: Service Control Policies (SCPs)
**Answer:**
- **What:** Organization-level policies. Set maximum permissions for member accounts/OUs
- **Key:** SCPs don't grant permissions (only restrict). Account still needs identity policies
- **Don't affect:** Management account (even if attached)
- **Use cases:** Prevent regions usage, enforce tagging, prevent certain services, require encryption
- **Strategy:** Deny-list (allow all, deny specific) OR Allow-list (deny all, allow specific - more restrictive)
- **Example:** Deny ec2:RunInstances unless instance type in approved list

### Q137: IAM Identity Center (AWS SSO)
**Answer:**
- Centralized access management for multiple AWS accounts + SAML business apps
- **Features:** Single sign-on, central permission management, multi-account access
- **Identity source:** Built-in, Active Directory (AD Connector/AWS Managed AD), external IdP (Okta, Azure AD)
- **Permission Sets:** Collection of policies → assign to users/groups → specific accounts
- **Portal:** Users see all assigned accounts/apps in one place
- **Replaces:** Managing IAM users in each account separately

### Q138: ABAC (Attribute-Based Access Control)
**Answer:**
- Access based on **tags** (attributes) rather than explicit resource ARNs
- **Example:** Allow action if `aws:PrincipalTag/team` == `aws:ResourceTag/team` (team can only access their resources)
- **Benefits:** Scalable (new resources auto-covered if tagged correctly), fewer policies needed
- **Condition keys:** aws:PrincipalTag/*, aws:ResourceTag/*, aws:RequestTag/*
- **Use case:** Multi-team environment where each team manages own resources without separate policies
- **Requirement:** Consistent tagging strategy + tag-based conditions in policies

### Q139: IAM Federation with SAML
**Answer:**
- **Flow:** User → Corporate IdP (login) → SAML assertion → AWS STS (AssumeRoleWithSAML) → Temporary credentials → Console/API
- **Setup:** Create SAML provider in IAM, create role with trust for SAML provider, configure IdP
- **IdPs:** Active Directory (via ADFS), Okta, Azure AD, OneLogin, Ping Identity
- **Duration:** Session 1-12 hours (configurable)
- **Attributes:** SAML assertion contains roles (user can assume), session duration, custom attributes

### Q140: Cognito User Pools vs Identity Pools
**Answer:**
- **User Pool:** User directory. Sign-up/sign-in, tokens (JWT). Think: "Who is this user?"
- **Identity Pool:** Exchange tokens for AWS credentials. Think: "What can this user do in AWS?"
- **Common flow:** User authenticates with User Pool → gets tokens → exchanges via Identity Pool → gets AWS credentials → accesses S3/DynamoDB
- **User Pool alone:** Sufficient for API Gateway (JWT authorizer), application-level auth
- **Identity Pool alone:** Can federate with Google/Facebook directly (no User Pool needed)

### Q141: Cognito authentication flow
**Answer:**
1. **Sign-up:** User registers (email/phone) → verification (code via email/SMS)
2. **Sign-in:** User submits credentials → Cognito validates → returns tokens (ID, Access, Refresh)
3. **Token refresh:** Access token expires (1hr default) → use Refresh token to get new Access token
4. **Auth flows:** USER_SRP_AUTH (default, secure), CUSTOM_AUTH (Lambda challenges), USER_PASSWORD_AUTH (migration)
5. **MFA:** Optional/required, SMS or TOTP (authenticator app)
6. **Advanced Security:** Risk-based adaptive auth (block/MFA for suspicious logins)

### Q142: Cognito Lambda Triggers
**Answer:**
- **Pre-signup:** Validate, auto-confirm, auto-verify
- **Post-confirmation:** Welcome email, create user record in DB
- **Pre-authentication:** Custom validation, block sign-in, log attempts
- **Post-authentication:** Analytics, sync user data
- **Custom message:** Customize verification/MFA messages
- **Pre-token-generation:** Add/remove claims in JWT tokens
- **User migration:** Seamless migration from legacy auth system (authenticate against old system)
- **Define/Create/Verify auth challenge:** Custom MFA flow (security questions, etc.)

### Q143: Implementing MFA in Cognito
**Answer:**
- **Types:** SMS (text message), TOTP (authenticator app like Google Authenticator)
- **Enforcement:** Optional (user choice), Required (all users), Adaptive (risk-based)
- **Setup TOTP:** Associate software token (user scans QR) → verify with code → set as preferred
- **Adaptive MFA:** Advanced Security feature. MFA required only for suspicious sign-ins (new device, new IP, impossible travel)
- **Custom MFA:** Use Lambda triggers (Define/Create/Verify auth challenge) for custom factor (email OTP, security questions)

### Q144: OAuth 2.0 flows in Cognito
**Answer:**
- **Authorization Code:** Server-side apps. User redirected to login → code returned → exchange code for tokens (most secure)
- **Authorization Code + PKCE:** Mobile/SPA apps. Same as above but with code_verifier/challenge (prevents interception)
- **Implicit (deprecated):** Tokens returned directly in URL fragment. Legacy, insecure
- **Client Credentials:** Machine-to-machine. No user involved. Client ID + Secret → Access Token with scopes
- **Resource Server:** Define custom scopes (read:data, write:data) → clients request specific scopes

### Q145: Fine-grained access control
**Answer:**
- **Cognito Identity Pool + IAM policy variables:** `${cognito-identity.amazonaws.com:sub}` in policy
- **Example:** S3 policy allowing access only to `s3://bucket/${sub}/*` (user-specific folder)
- **DynamoDB:** Condition key = `cognito-identity.amazonaws.com:sub` → user only reads own items
- **API Gateway:** Lambda authorizer extracts user context → passes to backend → backend enforces
- **AppSync:** @auth directive with owner field in GraphQL schema
- **ABAC pattern:** User attributes as tags → resource tag conditions in policies

### Q146: ID Token vs Access Token vs Refresh Token
**Answer:**
- **ID Token:** Contains user identity claims (email, name, groups, custom attributes). For application to know who user is. Short-lived (1hr)
- **Access Token:** Contains scopes and groups. For API authorization (sent to backend). Short-lived (1hr)
- **Refresh Token:** Exchange for new ID + Access tokens without re-authentication. Long-lived (30 days default, up to 10 years)
- **Storage:** Never store in localStorage (XSS). Use httpOnly secure cookies or in-memory
- **Validation:** Verify JWT signature (RS256) + issuer + audience + expiry

### Q147: API Gateway + Cognito integration
**Answer:**
- **REST API:** Cognito User Pool Authorizer. Pass ID/Access token in Authorization header. Gateway validates JWT automatically
- **HTTP API:** JWT Authorizer (works with Cognito or any OIDC provider). Validates issuer, audience, scopes
- **Scopes enforcement:** Require specific scopes per method (e.g., `read:orders` for GET /orders)
- **Groups:** Token contains `cognito:groups` → use in Lambda authorizer for group-based access
- **No code needed:** Configuration-only auth for simple cases

### Q148: Cognito Hosted UI
**Answer:**
- Pre-built, customizable sign-in/sign-up UI hosted by AWS
- **Endpoints:** /login, /signup, /oauth2/authorize, /oauth2/token, /logout, /forgotPassword
- **Customization:** Logo, CSS (limited), custom domain (auth.yourapp.com)
- **Features:** Social login buttons, MFA, password recovery, sign-up
- **Custom UI:** Use Cognito APIs directly (Amplify library) for full control
- **When to use Hosted UI:** MVP, internal tools, quick start. Custom UI: production consumer apps

### Q149: Social identity providers in Cognito
**Answer:**
- **Supported:** Google, Facebook, Apple, Amazon, SAML, OIDC
- **Setup:** Register app with provider → get client ID/secret → configure in Cognito → map attributes
- **Flow:** User clicks "Sign in with Google" → redirected to Google → consent → Cognito creates/links user → tokens issued
- **Attribute mapping:** Map provider claims to Cognito attributes (Google email → Cognito email)
- **Linking:** Link multiple providers to single Cognito user (admin:link-provider-for-user API)

### Q150: Mobile app accessing AWS resources - auth design
**Answer:**
1. **Authentication:** Cognito User Pool (sign-up/sign-in, social login, MFA)
2. **Token exchange:** Cognito Identity Pool (federated identities) exchanges User Pool token for AWS credentials
3. **IAM Role:** Authenticated role with scoped permissions (S3 per-user folder, DynamoDB per-user items)
4. **AWS SDK:** Use temporary credentials to call AWS services directly from mobile (S3 upload, DynamoDB query)
5. **Policy variables:** `${cognito-identity.amazonaws.com:sub}` limits access to own data
6. **Token refresh:** SDK handles refresh automatically

### Q151: What is PassRole and why important?
**Answer:**
- **iam:PassRole:** Permission required to assign (pass) an IAM role to an AWS service
- **Why:** Prevents privilege escalation. Without this check, user with Lambda create permission could pass Admin role to Lambda → execute with admin privileges
- **Example:** To create Lambda with execution role, user needs: lambda:CreateFunction AND iam:PassRole (on that specific role)
- **Best practice:** Restrict PassRole to specific role ARNs (Resource condition)
- **Common:** EC2 RunInstances + PassRole for instance profile, ECS CreateService + PassRole for task role

### Q152: Auditing IAM permissions
**Answer:**
- **Access Analyzer:** Find unused permissions (not used in 90 days), generate least-privilege policies from CloudTrail
- **Credential Report:** CSV of all IAM users, last activity, MFA status, key age
- **CloudTrail:** Log all API calls (who did what, when, from where)
- **Service Last Accessed:** Shows when each service was last used by entity
- **IAM Policy Simulator:** Test policies without making real calls
- **Access Advisor:** Tab in IAM showing services accessed and when (per user/role)
- **Best practice:** Regular access reviews, automated alerts on unused permissions, revoke quarterly

### Q153: IAM Access Analyzer
**Answer:**
- **External access findings:** Identifies resources shared with external entities (S3 buckets, IAM roles, KMS keys, Lambda, SQS)
- **Unused access findings:** Identifies unused permissions, roles, access keys (based on CloudTrail analysis)
- **Policy generation:** Generate least-privilege policy from CloudTrail activity logs
- **Policy validation:** Check policies for errors, security warnings, suggestions
- **Custom policy checks:** Validate against your organization's standards
- **Scope:** Account-level or Organization-level analyzer

### Q154: What are session policies?
**Answer:**
- Inline policies passed during AssumeRole or federation (GetFederationToken)
- **Effect:** Further restrict permissions of assumed role (intersection of role policy + session policy)
- **Cannot exceed:** Permissions of the role itself (only reduce, never expand)
- **Use case:** Different users assume same role but need different permissions (restrict per-session)
- **Example:** Role has S3 full access. Session policy limits to specific bucket → session only has that bucket

### Q155: Temporary elevated access (break-glass)
**Answer:**
- **Pattern:** Low-privilege default → request elevated access → approval → time-limited elevated role
- **Implementation:** Step Functions workflow: user requests → SNS notification → approver → assume elevated role (short session)
- **AWS SSO:** Permission sets with time-limited assignments (grant admin for 4 hours only)
- **Tools:** Temporary Elevated Access Management (TEAM) solution, CyberArk, HashiCorp Boundary
- **Audit:** CloudTrail logs all AssumeRole calls, SNS alerts on elevated access usage
- **Best practice:** Require MFA for elevated access, log everything, auto-expire sessions

---

## RDS & Databases (Q156-Q175)

### Q156: RDS Multi-AZ vs Read Replicas
**Answer:**
| Feature | Multi-AZ | Read Replica |
|---------|----------|--------------|
| Purpose | High availability | Read scaling |
| Replication | Synchronous | Asynchronous |
| Failover | Automatic (1-2 min) | Manual promotion |
| Readable | No (standby only) | Yes |
| Cross-region | No (same region) | Yes |
| Endpoint | Same (DNS switch) | Separate endpoint |
| Cost | 2x instance cost | Additional instance cost |
| **Use Multi-AZ for:** HA/DR. **Use Read Replicas for:** read scaling, reporting, cross-region |

### Q157: How does Aurora differ from standard RDS?
**Answer:**
- **Performance:** 5x MySQL, 3x PostgreSQL
- **Storage:** Distributed (6 copies across 3 AZs), auto-grows 10 GiB-128 TiB, self-healing
- **Replicas:** Up to 15 (vs 5), sub-10ms lag (vs seconds), auto-failover
- **Endpoints:** Writer, Reader (load-balanced), Custom, Instance
- **Features:** Backtrack, Global Database, Serverless v2, zero-ETL to Redshift
- **Cost:** ~20% more than RDS MySQL/PostgreSQL but better performance and HA

### Q158: Aurora Serverless v2
**Answer:**
- Scales compute automatically (0.5 to 128 ACU in 0.5 ACU increments)
- **ACU (Aurora Capacity Unit):** ~2 GiB memory each
- **Scaling speed:** Instant (within existing capacity), seconds (for new capacity)
- **Pricing:** Per-ACU-second ($0.12/ACU-hour). Pay for actual usage
- **Use cases:** Variable/unpredictable workloads, dev/test, multi-tenant
- **vs Provisioned:** Serverless = variable cost, zero management. Provisioned = fixed cost, more predictable
- **Can mix:** Some readers Serverless v2, writer provisioned (or all serverless)

### Q159: Aurora Global Database
**Answer:**
- 1 primary region (read/write) + up to 5 secondary regions (read-only)
- **Replication lag:** < 1 second typical (vs minutes for cross-region read replicas)
- **Failover:** RTO < 1 minute, RPO < 1 second
- **Managed planned failover:** Zero data loss switchover for maintenance
- **Unplanned failover:** Promote secondary (minimal data loss)
- **Use cases:** Disaster recovery, low-latency global reads, regional compliance
- **Write forwarding:** Secondary can forward writes to primary (reduces app complexity)

### Q160: RDS Proxy - how it works
**Answer:**
- Fully managed connection pooler between application and database
- **Benefits:** Connection multiplexing (1000s of app connections → 100s DB connections), 66% faster failover (warm connections), IAM auth
- **How:** Application connects to proxy endpoint → proxy maintains connection pool to DB → multiplexes
- **Pinning:** Some operations require dedicated connection (SET statements, prepared statements, temporary tables)
- **Supports:** MySQL, PostgreSQL, MariaDB, SQL Server
- **Use case:** Lambda → RDS (ephemeral connections), microservices (many small pools)

### Q161: RDS backup and recovery
**Answer:**
- **Automated backups:** Daily snapshot + transaction logs (every 5 min). RPO = 5 minutes. Retention 0-35 days
- **Manual snapshots:** On-demand, persist until deleted, can share/copy cross-region/account
- **Point-in-time recovery:** Restore to any second within retention window. Creates NEW instance
- **Cross-region:** Automated backup replication to another region
- **Aurora:** Continuous backup to S3, no performance impact. Backtrack (rewind without new instance)
- **Restore:** Always creates new DB instance (new endpoint). Update application connection string

### Q162: Encrypt existing unencrypted RDS instance
**Answer:**
1. Create snapshot of unencrypted instance
2. Copy snapshot with encryption enabled (select KMS key)
3. Restore new instance from encrypted snapshot
4. Update application to use new endpoint
5. Verify functionality
6. Delete old unencrypted instance
- **Cannot:** Enable encryption on existing instance directly
- **Downtime:** Required (new endpoint, application switch)
- **Read Replicas:** Cannot create encrypted replica from unencrypted source

### Q163: Performance Insights
**Answer:**
- Database performance monitoring tool (included with RDS, 7 days free retention)
- **DB Load:** Top metric - active sessions vs vCPU count. If load > vCPU = bottleneck
- **Wait events:** What sessions are waiting on (I/O, lock, CPU, network)
- **Top SQL:** Queries causing most load (identify slow queries)
- **Dimensions:** Slice by wait event, SQL, user, host, database
- **Use:** Identify bottleneck → Top wait event → Top SQL → Optimize query or scale resources

### Q164: DynamoDB vs RDS - when to use which?
**Answer:**
- **DynamoDB:** Key-value/document, single-digit ms, serverless, infinite scale, no joins, schema-flexible
- **RDS:** Relational, complex queries, joins, transactions, ACID, SQL, fixed schema
- **Choose DynamoDB:** High traffic, simple access patterns, known query patterns upfront, need auto-scaling
- **Choose RDS:** Complex queries, ad-hoc reporting, many-to-many relationships, ACID transactions across tables
- **Hybrid:** DynamoDB for hot data (user sessions, carts) + RDS for complex relational data (orders, inventory)

### Q165: ElastiCache Redis vs Memcached
**Answer:**
| Feature | Redis | Memcached |
|---------|-------|-----------|
| Data structures | Strings, lists, sets, hashes, sorted sets | Strings only |
| Persistence | Yes (AOF, RDB) | No |
| Replication | Yes (primary-replica, Multi-AZ) | No |
| Cluster mode | Yes (partitioning) | Yes (auto-discovery) |
| Pub/Sub | Yes | No |
| Lua scripting | Yes | No |
| Multi-threaded | No (single-threaded) | Yes |
| **Choose Redis:** Complex data, persistence, HA. **Choose Memcached:** Simple caching, multi-threaded |

### Q166: DynamoDB partition keys, sort keys, GSI/LSI
**Answer:**
- **Partition key:** Determines partition placement. Must be high-cardinality for even distribution
- **Sort key:** Orders items within partition. Enables range queries (begins_with, between)
- **GSI (Global Secondary Index):** Different partition/sort key. Own throughput. Eventually consistent. Up to 20
- **LSI (Local Secondary Index):** Same partition key, different sort key. Shares table throughput. Strongly consistent. Up to 5. Must create at table creation
- **Hot partition:** Single partition key getting disproportionate traffic → throttling. Fix: better key design, write sharding

### Q167: DynamoDB DAX
**Answer:**
- In-memory cache for DynamoDB (microsecond reads vs millisecond)
- **How:** DAX cluster sits between app and DynamoDB. Cache hit → microseconds. Miss → reads from DynamoDB
- **Write-through:** Writes go through DAX to DynamoDB (items cached on write)
- **Nodes:** 1-11 nodes (Multi-AZ for HA). T-type (burstable) or R-type (memory-optimized)
- **Use when:** Read-heavy, need microsecond latency, hot key patterns
- **Not suitable for:** Write-heavy, need strongly consistent reads (DAX = eventually consistent)

### Q168: Database migration with DMS
**Answer:**
- **DMS (Database Migration Service):** Migrate databases with minimal downtime
- **Migration types:** Full load, Full load + CDC (Change Data Capture), CDC only
- **Homogeneous:** Same engine (MySQL → MySQL). Direct migration
- **Heterogeneous:** Different engines (Oracle → PostgreSQL). Need SCT (Schema Conversion Tool) first
- **Replication Instance:** EC2 that runs migration tasks (size based on data volume)
- **Ongoing replication:** CDC keeps target in sync until cutover (near-zero downtime migration)
- **Validation:** Data validation feature compares source vs target

### Q169: Aurora Backtrack
**Answer:**
- "Rewind" database to any point in time (up to 72 hours) WITHOUT creating new instance
- **Speed:** Seconds (vs hours for point-in-time restore which creates new instance)
- **Use cases:** Undo accidental DELETE/UPDATE, recover from bad deployment, testing
- **Limitation:** MySQL-compatible only, must enable at creation, costs per change record stored
- **vs PITR:** Backtrack = in-place, seconds, same endpoint. PITR = new instance, minutes/hours, new endpoint

### Q170: Point-in-time recovery (PITR)
**Answer:**
- Restore database to any second within backup retention period (1-35 days)
- **How:** Automated backup (daily snapshot) + transaction logs (every 5 min) = any point
- **Creates:** New DB instance (new endpoint, new parameter group association)
- **RTO:** Minutes to hours (depends on DB size and transaction logs to replay)
- **RPO:** Up to 5 minutes (transaction log frequency)
- **Use case:** Recover from corruption, accidental deletion, bad migration

### Q171: Lambda + RDS connection management
**Answer:**
- **Problem:** Lambda scales to 1000s of concurrent executions, each opens DB connection → overwhelms RDS (max_connections limit)
- **Solution 1: RDS Proxy** (recommended) - Connection pooling, multiplexes Lambda connections
- **Solution 2:** Reduce Lambda concurrency (reserved concurrency matching DB capacity)
- **Solution 3:** Connection pooling in Lambda (reuse across warm invocations within same instance)
- **Solution 4:** DynamoDB instead of RDS (no connection limit)
- **RDS Proxy benefits for Lambda:** Faster connections (warm pool), IAM auth, no connection exhaustion

### Q172: RDS storage types and auto-scaling
**Answer:**
- **gp3:** Baseline 3000 IOPS + 125 MB/s, scale independently. Best general-purpose choice
- **gp2:** 3 IOPS/GiB (burst to 3000). Legacy, use gp3 instead
- **io1/io2:** Provisioned IOPS (up to 64K). High-performance OLTP databases
- **Auto-scaling:** Set maximum storage limit. Scales up when: free storage < 10% AND low storage lasts 5+ min AND 6+ hours since last increase
- **Scaling:** Only increases (never decreases). No downtime during scale. One modification at a time

### Q173: Multi-AZ DB Cluster (new)
**Answer:**
- 1 writer + 2 reader instances across 3 AZs (vs Multi-AZ Instance: 1 writer + 1 standby)
- **Readers are readable** (unlike standby in Multi-AZ Instance)
- **Replication:** Synchronous using transaction log shipping
- **Failover:** ~35 seconds (faster than Multi-AZ Instance)
- **Supports:** MySQL 8.0, PostgreSQL 13+
- **Endpoints:** Cluster endpoint (writer), Reader endpoint (load-balanced readers), Instance endpoints
- **vs Aurora:** Lower cost, fewer features, standard MySQL/PostgreSQL compatibility

### Q174: Design for 99.99% database availability
**Answer:**
- **Aurora Global Database:** Multi-region (survive regional failure). RPO<1s, RTO<1min
- OR **Multi-AZ DB Cluster** + Cross-region Read Replica + automated failover
- **Application:** Connection retry logic, circuit breaker, read from replicas during failover
- **Monitoring:** Enhanced monitoring, CloudWatch alarms on lag/connections/CPU
- **Backups:** Automated + cross-region snapshots
- **Testing:** Regular DR drills (force failover and measure RTO)
- **Math:** 99.99% = max 52 minutes downtime/year. Need automated failover + health checks

### Q175: Database migration strategies
**Answer:**
- **Homogeneous (same engine):** DMS full load + CDC → cutover when caught up. Simple, minimal downtime
- **Heterogeneous (different engine):** SCT (schema conversion) → DMS (data migration) → validate → cutover
- **Strategies:**
  - Big bang: Downtime window, migrate all at once. Simplest but requires downtime
  - Trickle: Gradual migration, dual-write, read from both. Complex but zero-downtime
  - Strangler: New features on new DB, migrate old features incrementally
- **Validation:** Row count comparison, data validation with DMS, application testing
- **Rollback plan:** Keep source DB running and in-sync until confident (dual-write or CDC reverse)

---

## VPC & Networking (Q176-Q190)

### Q176: VPC components explained
**Answer:**
- **VPC:** Isolated virtual network (CIDR block, e.g., 10.0.0.0/16)
- **Subnet:** Segment of VPC in single AZ. Public (has route to IGW) or Private
- **Route Table:** Rules determining traffic destination. Attached to subnets
- **Internet Gateway (IGW):** VPC-level gateway to internet (HA, scaled by AWS)
- **NAT Gateway:** Allows private subnet outbound internet (managed, per-AZ, Elastic IP)
- **Security Group:** Instance-level stateful firewall (allow rules only)
- **NACL:** Subnet-level stateless firewall (allow + deny, numbered rules)

### Q177: Public vs Private subnet
**Answer:**
- **Public:** Has route to Internet Gateway (0.0.0.0/0 → igw-xxx). Instances can have public IPs
- **Private:** No route to IGW. Instances can't be reached from internet. Outbound via NAT Gateway
- **Design pattern:** Public: Load balancers, bastion hosts. Private: Application servers, databases
- **3-tier:** Public subnet (ALB) → Private subnet (App) → Private subnet (Database)
- **IP allocation:** Public instances get auto-assigned public IP (or Elastic IP)

### Q178: VPC Peering vs Transit Gateway
**Answer:**
- **VPC Peering:** Direct connection between 2 VPCs. Non-transitive (A↔B, B↔C doesn't mean A↔C). Free same-AZ, cross-AZ/region charged
- **Transit Gateway:** Hub-and-spoke. Transitive routing. Connect thousands of VPCs + VPN + Direct Connect. $0.05/hr + $0.02/GB
- **Choose Peering:** Few VPCs (<10), simple topology, cross-region
- **Choose TGW:** Many VPCs, hub-spoke, need transitive routing, centralized control
- **Peering limit:** 125 per VPC. No overlapping CIDR. Manual route table entries

### Q179: VPC Endpoints (Interface vs Gateway)
**Answer:**
- **Gateway Endpoint:** Route table entry → S3 or DynamoDB. Free. No ENI
- **Interface Endpoint (PrivateLink):** ENI with private IP in your subnet. Most AWS services. Charged ($0.01/hr + $0.01/GB)
- **Gateway LB Endpoint:** For third-party appliances (firewalls, IDS) via GWLB
- **Benefits:** Traffic stays on AWS network (no internet), no NAT/IGW needed, policy-controlled
- **Interface Endpoint DNS:** Uses private hosted zone to override public service endpoint → resolves to private IP

### Q180: How does Direct Connect work?
**Answer:**
- Dedicated physical connection from on-prem to AWS (bypasses internet)
- **Speeds:** 1 Gbps, 10 Gbps (dedicated), 50 Mbps-10 Gbps (hosted via partner)
- **VIF (Virtual Interface):** Public (AWS public services), Private (VPC), Transit (TGW)
- **Direct Connect Gateway:** Connect to multiple VPCs in multiple regions via single connection
- **LAG:** Bundle multiple connections for bandwidth (Link Aggregation Group)
- **Redundancy:** Two connections from different DX locations for HA
- **Setup time:** Weeks to months (physical installation)

### Q181: What is AWS PrivateLink?
**Answer:**
- Expose your service to other VPCs/accounts without VPC peering or internet
- **Provider:** Create NLB + VPC Endpoint Service → share service name
- **Consumer:** Create Interface VPC Endpoint → connect to provider's service privately
- **Benefits:** No VPC peering (no CIDR overlap issues), service-level access (not network-level), scalable
- **Use cases:** SaaS provider exposing API to customers, shared services within organization
- **Unidirectional:** Consumer initiates connection to provider (not bidirectional)

### Q182: NLB vs ALB vs GLB
**Answer:**
| Feature | ALB | NLB | GLB |
|---------|-----|-----|-----|
| Layer | 7 (HTTP/HTTPS) | 4 (TCP/UDP/TLS) | 3 (IP packets) |
| Routing | Path, host, header, query | Port-based | Transparent |
| Latency | ~400ms added | ~100μs added | Transparent |
| Static IP | No (use Global Accelerator) | Yes (per AZ) | N/A |
| WebSocket | Yes | Yes (pass-through) | N/A |
| gRPC | Yes | Pass-through | N/A |
| Use case | Web apps, microservices | Ultra-low latency, non-HTTP | Firewalls, IDS/IPS |

### Q183: Security Groups + NACLs working together
**Answer:**
- **Layered defense:** NACL (subnet boundary) + Security Group (instance boundary)
- **Request flow:** Internet → NACL inbound rules → SG inbound rules → Instance
- **Response flow:** Instance → SG (stateful, auto-allows) → NACL outbound rules (stateless, must allow)
- **NACL gotcha:** Must allow ephemeral ports (1024-65535) outbound for responses
- **Strategy:** NACL for broad deny (block known bad IPs, block ports), SG for specific allow (port 443 from ALB SG)

### Q184: VPC Flow Logs
**Answer:**
- Capture IP traffic information for ENI, subnet, or VPC
- **Fields:** srcaddr, dstaddr, srcport, dstport, protocol, packets, bytes, action (ACCEPT/REJECT)
- **Destination:** CloudWatch Logs, S3, Kinesis Data Firehose
- **Analysis:** Athena queries on S3, CloudWatch Insights, third-party (Splunk, Datadog)
- **Use cases:** Security analysis (rejected traffic), troubleshooting (why traffic blocked), compliance
- **Limitation:** Does NOT capture: DNS traffic to Route 53, DHCP, metadata (169.254.169.254), NTP

### Q185: Multi-AZ, multi-region network design
**Answer:**
- **Multi-AZ:** Subnets in 2-3 AZs, ALB cross-zone, ASG spanning AZs, Multi-AZ RDS
- **Multi-region:** Transit Gateway inter-region peering OR VPC Peering cross-region
- **DNS:** Route 53 latency-based routing (send users to nearest region)
- **Data sync:** S3 replication, Aurora Global Database, DynamoDB Global Tables
- **Failover:** Route 53 health checks → failover routing to healthy region
- **Global Accelerator:** Anycast IPs → route to nearest healthy regional endpoint

### Q186: DNS in VPC (Route 53 Resolver)
**Answer:**
- **VPC DNS:** AmazonProvidedDNS at VPC CIDR + 2 (e.g., 10.0.0.2)
- **enableDnsSupport:** Enables DNS resolution in VPC
- **enableDnsHostnames:** Assigns DNS hostnames to instances
- **Route 53 Resolver:** Handles DNS queries for VPC
- **Inbound endpoint:** On-prem can resolve AWS private hosted zones (forward to VPC)
- **Outbound endpoint:** VPC can resolve on-prem domains (forward to on-prem DNS)
- **Resolver rules:** Forward specific domains (corp.internal) to on-prem DNS servers

### Q187: AWS Network Firewall
**Answer:**
- Managed stateful firewall for VPC (L3-L7 filtering)
- **Features:** Stateful/stateless rules, IDS/IPS (Suricata-compatible), domain filtering, TLS inspection
- **vs NACL:** Network Firewall = deep inspection, domain filtering, IDS. NACL = simple L3/L4
- **vs WAF:** Network Firewall = VPC-level, any protocol. WAF = HTTP/HTTPS, CloudFront/ALB
- **Deployment:** Firewall endpoint in subnet, route tables direct traffic through it
- **Use cases:** Centralized egress filtering, IDS/IPS, domain-based allowlist, compliance

### Q188: Traffic mirroring
**Answer:**
- Copy network traffic from ENI to monitoring/analytics tools
- **Source:** Any ENI (EC2, RDS, ELB). **Target:** ENI or NLB
- **Filter:** Select traffic by protocol, port, CIDR (don't mirror everything)
- **Use cases:** Security analysis (IDS/IPS), network troubleshooting, compliance monitoring
- **Limitations:** Same VPC or peered VPC. Nitro instances only. Adds no latency to source

### Q189: IPv6 in AWS VPC
**Answer:**
- **Dual-stack:** VPC can have both IPv4 CIDR + IPv6 CIDR (/56 from AWS pool)
- **Subnet:** /64 IPv6 CIDR per subnet (auto-assigned from VPC /56)
- **Instances:** Get IPv6 address in addition to IPv4 (dual-stack)
- **Egress-only IGW:** For IPv6 outbound only (like NAT for IPv4 but for IPv6)
- **Key:** IPv6 addresses are all public (no NAT concept for IPv6). Use security groups/NACLs to restrict
- **When:** IoT (billions of devices), future-proofing, avoid IPv4 exhaustion

### Q190: VPC design for 3-tier application
**Answer:**
```
VPC: 10.0.0.0/16
├── Public Subnet (10.0.1.0/24, 10.0.2.0/24) - AZ-a, AZ-b
│   └── ALB, NAT Gateway, Bastion Host
├── Private App Subnet (10.0.10.0/24, 10.0.11.0/24) - AZ-a, AZ-b
│   └── EC2/ECS application servers (ASG)
├── Private DB Subnet (10.0.20.0/24, 10.0.21.0/24) - AZ-a, AZ-b
│   └── RDS Multi-AZ, ElastiCache
```
- **Security:** ALB SG (443 from 0.0.0.0/0) → App SG (from ALB SG only) → DB SG (from App SG only, port 3306/5432)
- **Internet:** Public subnet routes to IGW. Private routes to NAT Gateway
- **Endpoints:** S3 Gateway endpoint, ECR/CloudWatch Interface endpoints (avoid NAT charges)


---

## Terraform & IaC (Q191-Q210)

### Q191: What is Terraform state and why important?
**Answer:**
- **State file (terraform.tfstate):** JSON file mapping config resources to real-world resources
- **Why needed:** Terraform needs to know what it manages (which EC2 = which config block)
- **Contains:** Resource IDs, attributes, dependencies, metadata
- **Risks:** Contains sensitive data (passwords, keys), concurrent modification can corrupt
- **Best practice:** Remote backend (S3+DynamoDB locking), never commit to git, enable encryption
- **Without state:** Terraform would try to create everything from scratch every time

### Q192: terraform plan vs apply
**Answer:**
- **plan:** Preview changes WITHOUT making them. Shows: create, update, destroy, replace
- **apply:** Execute changes to reach desired state. By default shows plan first (confirm yes)
- **plan -out=file:** Save plan to file → `apply file` ensures exact plan is applied (CI/CD best practice)
- **Key difference:** Plan is read-only and safe. Apply mutates infrastructure
- **Tips:** Always plan before apply, review destroy operations carefully, use -target for focused changes

### Q193: Remote state management
**Answer:**
- **S3 backend (most common):**
  ```hcl
  backend "s3" {
    bucket         = "tf-state-bucket"
    key            = "prod/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "tf-locks"  # state locking
    encrypt        = true
  }
  ```
- **DynamoDB:** Provides state locking (prevent concurrent apply)
- **Terraform Cloud:** Managed backend with remote execution, policy enforcement
- **Benefits:** Team collaboration, locking, encryption, versioning (S3 bucket versioning)
- **State per environment:** Separate state files (separate S3 keys or workspaces)

### Q194: Terraform modules best practices
**Answer:**
- **What:** Reusable infrastructure packages (main.tf, variables.tf, outputs.tf)
- **Sources:** Local path, Terraform Registry, GitHub, S3
- **Structure:** Small, focused modules (one module = one concern: VPC, EKS, RDS)
- **Versioning:** Pin module versions (`source = "...", version = "~> 3.0"`)
- **Interface:** Clear variables (with descriptions, types, validation), meaningful outputs
- **Composition:** Root module calls child modules, passes outputs between them
- **Testing:** terratest (Go), terraform test (HCL), plan validation in CI

### Q195: count vs for_each
**Answer:**
- **count:** Integer-based. `count = 3` creates resource[0], resource[1], resource[2]
  - Problem: Removing item from middle reorders indexes → Terraform destroys/recreates
- **for_each:** Map/set-based. Key is stable identifier
  - `for_each = toset(["web", "app", "db"])` → resource["web"], resource["app"]
  - Removing "app" only affects that resource
- **Best practice:** Use for_each for most cases (stable addressing). Count only for identical resources
- **Conversion:** `for_each = { for s in var.subnets : s.name => s }`

### Q196: How to handle secrets in Terraform
**Answer:**
- **Never:** Hardcode in .tf files or tfvars committed to git
- **Options:**
  1. **Environment variables:** TF_VAR_db_password (not in files)
  2. **terraform.tfvars (gitignored):** Local only, not committed
  3. **AWS Secrets Manager/SSM:** Reference via data source, Terraform creates secret but value set externally
  4. **Vault provider:** HashiCorp Vault dynamic secrets
  5. **SOPS:** Encrypted tfvars files in git
- **State concern:** Sensitive values end up in state file → encrypt state, restrict access
- **sensitive = true:** Hides value in plan output (but still in state file)

### Q197: State locking
**Answer:**
- **What:** Prevents concurrent terraform apply from corrupting state
- **Without locking:** Two people apply simultaneously → race condition → corrupted state
- **DynamoDB (S3 backend):** Lock acquired at start of operation, released at end. Table stores lock ID
- **Terraform Cloud:** Built-in locking (automatic)
- **Force unlock:** `terraform force-unlock LOCK_ID` (dangerous, only if stuck)
- **Best practice:** Always enable locking. If lock stuck, verify no one else is running, then force-unlock

### Q198: Terraform workspaces
**Answer:**
- **What:** Multiple state files from same configuration (like branches for state)
- **Commands:** `terraform workspace new dev`, `workspace select prod`, `workspace list`
- **Use in config:** `terraform.workspace` variable → conditionals (e.g., instance size per workspace)
- **Limitation:** Same backend config, same code. Only state differs
- **vs Directory-based:** Directories = separate configs + states + variables. More flexible, more files
- **vs Terragrunt:** Terragrunt = DRY configurations across environments with inheritance
- **When to use:** Simple environment differences (dev/staging/prod with same infra, different sizes)

### Q199: Import existing resources
**Answer:**
- **terraform import:** `terraform import aws_instance.web i-12345` → adds to state
- **Process:** 1) Write resource block in .tf, 2) Run import, 3) Run plan to verify (should show no changes), 4) Adjust config until plan is clean
- **Import block (newer):** Declarative import in config
  ```hcl
  import {
    to = aws_instance.web
    id = "i-12345"
  }
  ```
- **Bulk import:** Scripts or tools (terraformer, former2 for AWS)
- **Limitation:** State updated but config must be written manually (terraform plan shows drift until config matches)

### Q200: What is Terragrunt?
**Answer:**
- **What:** Wrapper around Terraform for DRY configurations and remote state management
- **Key features:**
  - DRY backend configuration (define once, inherit)
  - DRY provider/variable configurations
  - Dependency management between modules (dependency blocks)
  - Run modules across directories (`run-all plan`)
  - Generate files (providers, backends) dynamically
- **Use when:** Managing many environments/modules with shared configuration
- **Structure:** `live/dev/vpc/terragrunt.hcl`, `live/prod/vpc/terragrunt.hcl` → both reference same module
- **Alternative:** Terraform workspaces (simpler) or CDK (different paradigm)

### Q201: Terraform plan shows unexpected destroy - troubleshooting
**Answer:**
1. **State drift:** Someone changed resource outside Terraform → `terraform refresh` to sync state
2. **Resource recreate (replacement):** Force-new attribute changed (e.g., AMI ID, name)
3. **Count/for_each index change:** Removed item from middle of count list
4. **Provider version change:** Breaking change in provider behavior
5. **State corruption:** Compare state with `terraform state show` and actual resource
6. **Fix:** Use `lifecycle { prevent_destroy = true }` for critical resources, review plan carefully
7. **moved blocks:** Refactor without destroy using `moved { from = ... to = ... }`

### Q202: Design Terraform structure for microservices
**Answer:**
```
infrastructure/
├── modules/
│   ├── vpc/
│   ├── ecs-cluster/
│   ├── ecs-service/    (reusable per service)
│   ├── rds/
│   └── monitoring/
├── environments/
│   ├── dev/
│   │   ├── main.tf (references modules)
│   │   ├── variables.tf
│   │   └── terraform.tfvars
│   ├── staging/
│   └── prod/
└── services/
    ├── user-service/   (per-service state)
    ├── order-service/
    └── payment-service/
```
- **Key principles:** Blast radius reduction (separate state per service/layer), DRY (shared modules), team ownership (service team owns their directory)

### Q203: Terraform vs CDK - decision criteria
**Answer:**
| Criteria | Terraform | CDK |
|----------|-----------|-----|
| Language | HCL (DSL) | TypeScript, Python, Java, Go |
| Multi-cloud | Yes (500+ providers) | AWS only (primarily) |
| State | Self-managed (S3) | CloudFormation (managed) |
| Ecosystem | Largest (registry, community) | Growing |
| Testing | terratest, built-in test | CDK assertions, unit tests |
| Learning curve | New language (HCL) | Existing language skills |
| **Choose Terraform:** Multi-cloud, team knows HCL, large community, mature |
| **Choose CDK:** AWS-only, complex logic in infra code, existing dev team, type safety |

### Q204: Zero-downtime infrastructure changes
**Answer:**
- **create_before_destroy:** New resource created before old destroyed (lifecycle block)
- **Blue/Green:** Create new infra → switch traffic → destroy old (separate Terraform states or modules)
- **Rolling (ASG):** Instance refresh with min_healthy_percentage
- **Database:** Use read replica → promote → switch endpoint (not pure Terraform)
- **DNS:** Weighted Route 53 records → shift traffic gradually
- **Terraform approach:** Apply creates new → health check passes → destroy old (ordered via depends_on)

### Q205: Multi-region deployment with Terraform
**Answer:**
- **Provider aliases:** Define multiple AWS providers with different regions
  ```hcl
  provider "aws" { region = "us-east-1" }
  provider "aws" { alias = "eu", region = "eu-west-1" }
  ```
- **Module per region:** Pass provider to module `providers = { aws = aws.eu }`
- **State:** Single state or separate state per region (separate = less blast radius)
- **Challenges:** Cross-region dependencies (replication), resource naming, consistent configuration
- **Terragrunt approach:** Separate directory per region, shared modules

---

## CI/CD & GitHub Actions (Q206-Q230)

### Q206: GitHub Actions workflow components
**Answer:**
- **Workflow:** YAML file in .github/workflows/ triggered by events
- **Event:** Trigger (push, pull_request, schedule, workflow_dispatch, workflow_call)
- **Job:** Set of steps running on same runner. Jobs run in parallel by default (use `needs:` for dependencies)
- **Step:** Individual task. Uses action (`uses:`) or runs command (`run:`)
- **Action:** Reusable unit of code (marketplace or custom)
- **Runner:** Machine that executes jobs (GitHub-hosted or self-hosted)

### Q207: Self-hosted vs GitHub-hosted runners
**Answer:**
| Feature | GitHub-hosted | Self-hosted |
|---------|---------------|-------------|
| Management | Zero (AWS managed) | You manage (updates, security) |
| Cost | Per-minute billing | Your infrastructure cost |
| Specs | 2-core, 7GB RAM (standard) | Custom (any spec) |
| Network | Public internet | Private network access |
| Clean state | Fresh VM every job | Persistent (or ephemeral with config) |
| Security | Isolated | Risk of code execution (avoid for public repos) |
| **Use self-hosted:** Need VPC access, GPU, custom tools, cost optimization at scale |

### Q208: Matrix strategy in GitHub Actions
**Answer:**
```yaml
strategy:
  matrix:
    os: [ubuntu-latest, windows-latest]
    node: [16, 18, 20]
    exclude:
      - os: windows-latest
        node: 16
    include:
      - os: ubuntu-latest
        node: 20
        experimental: true
  fail-fast: false  # don't cancel all on single failure
  max-parallel: 4
```
- **Creates:** Combination of all values (6 jobs in example above minus exclusion)
- **Use cases:** Cross-platform testing, multi-version testing, parallel deployments

### Q209: OIDC authentication for AWS from GitHub Actions
**Answer:**
- **What:** Federated credentials (no stored AWS secrets). GitHub issues JWT → AWS STS validates → temporary credentials
- **Setup:**
  1. Create OIDC identity provider in AWS IAM (issuer: token.actions.githubusercontent.com)
  2. Create IAM role with trust policy matching GitHub org/repo/branch
  3. Use aws-actions/configure-aws-credentials with role-to-assume
- **Benefits:** No long-lived secrets, auto-rotated, branch/environment-scoped, audit trail
- **Trust policy condition:** `sub: "repo:org/repo:ref:refs/heads/main"` (restrict to specific repo/branch)

### Q210: Secrets management in GitHub Actions
**Answer:**
- **Levels:** Repository secrets, Environment secrets (with protection rules), Organization secrets
- **Access:** `${{ secrets.MY_SECRET }}` in workflow. Masked in logs automatically
- **GITHUB_TOKEN:** Automatic, scoped to repo, expires after job. Use for: git push, PR comments, package publish
- **Best practices:** OIDC over stored secrets, minimal secret scope, rotate regularly, environment-specific secrets
- **Never:** Echo secrets, pass to untrusted actions, use in PR workflows from forks

### Q211: Reusable workflows
**Answer:**
- **What:** Workflow that can be called from other workflows (like functions)
- **Trigger:** `on: workflow_call` with defined inputs, secrets, outputs
- **Call:** `uses: ./.github/workflows/reusable.yml` or `uses: org/repo/.github/workflows/x.yml@main`
- **Benefits:** DRY (standardize CI across repos), maintainability (update once), governance
- **Limitations:** Max 4 levels of nesting, called workflow runs in caller's context
- **vs Composite Actions:** Reusable workflow = full workflow (multiple jobs). Composite = reusable steps

### Q212: GitHub Actions caching
**Answer:**
```yaml
- uses: actions/cache@v4
  with:
    path: ~/.npm
    key: ${{ runner.os }}-npm-${{ hashFiles('**/package-lock.json') }}
    restore-keys: |
      ${{ runner.os }}-npm-
```
- **Key:** Exact match → use cache. No match → try restore-keys (prefix match) → fallback to fresh
- **Paths:** node_modules, ~/.npm, ~/.m2, ~/.cache/pip, ~/.cargo
- **Limits:** 10 GB per repo, LRU eviction, 7-day expiry
- **Impact:** Can reduce CI time by 50-80% (skip dependency installation)
- **setup-* actions:** Many have built-in caching (actions/setup-node with cache: 'npm')

### Q213: Manual approvals (environments)
**Answer:**
```yaml
jobs:
  deploy-prod:
    environment:
      name: production
      url: https://myapp.com
    runs-on: ubuntu-latest
```
- **Environment protection rules:** Required reviewers (1-6 people), wait timer (0-43200 min), deployment branches (restrict which branches can deploy)
- **Flow:** Job reaches environment → paused → reviewers notified → approve/reject → continue/cancel
- **Use cases:** Production deployments, infrastructure changes, database migrations
- **Audit:** Deployment history per environment in GitHub UI

### Q214: Actions Runner Controller (ARC)
**Answer:**
- Kubernetes-native way to run self-hosted GitHub Actions runners
- **Components:** Controller (manages runner pods), RunnerDeployment/RunnerSet (desired state), HRA (Horizontal Runner Autoscaler)
- **Scaling:** Scale-to-zero, webhook-based (instant) or polling-based (periodic check)
- **Benefits:** Dynamic scaling, ephemeral runners (fresh per job), cost optimization
- **Setup:** Install ARC via Helm in K8s cluster → register with GitHub App or PAT
- **vs EC2 runners:** Better scaling, K8s-native, container isolation, cost efficient

### Q215: Design CI/CD for microservices monorepo
**Answer:**
- **Path filters:** Trigger only affected service's pipeline
  ```yaml
  on:
    push:
      paths: ['services/user-service/**']
  ```
- **Shared workflows:** Common build/test/deploy workflow called per service
- **Matrix:** Deploy multiple services in parallel after change detection
- **Tools:** Nx, Turborepo, or custom change detection script
- **Challenges:** Shared libraries (trigger all dependents), integration tests, deployment ordering
- **Deployment:** Independent deployments per service (loose coupling)

### Q216: Reduce CI pipeline from 30 min to 5 min
**Answer:**
1. **Caching:** Dependencies, build artifacts, Docker layers (actions/cache)
2. **Parallelization:** Split tests across matrix jobs (test splitting by timing)
3. **Skip unnecessary:** Path filters, skip CI for docs-only changes
4. **Faster runners:** Larger runners (8-core), self-hosted with SSDs
5. **Docker:** Multi-stage build, cache mount, BuildKit
6. **Incremental:** Only build/test changed code (Nx affected, Turborepo)
7. **Test optimization:** Remove flaky tests, mock external services, parallel test execution
8. **Pre-built images:** Base Docker images with dependencies pre-installed

### Q217: Zero-downtime ECS deployment in CI/CD
**Answer:**
```yaml
- name: Deploy to ECS
  uses: aws-actions/amazon-ecs-deploy-task-definition@v1
  with:
    task-definition: task-def.json
    service: my-service
    cluster: my-cluster
    wait-for-service-stability: true
```
- **Strategy:** Rolling update (minimumHealthyPercent=100, maximumPercent=200)
- **Health check:** ALB health check must pass before old tasks terminate
- **Circuit breaker:** Enable to auto-rollback if new tasks keep failing
- **Blue/Green alternative:** CodeDeploy + two target groups for instant rollback
- **Verification:** wait-for-service-stability ensures deployment complete before pipeline continues

### Q218: Rollback strategy for failed deployment
**Answer:**
- **Immediate rollback:** Revert commit + re-deploy (git revert → push → pipeline runs)
- **ECS:** Redeploy previous task definition revision (`aws ecs update-service --task-definition old:rev`)
- **K8s:** `kubectl rollout undo deployment/app` (reverts to previous ReplicaSet)
- **Blue/Green:** Switch traffic back to blue target group (instant)
- **Feature flags:** Disable feature remotely without deployment
- **Automation:** Set up alerts (5XX spike) → trigger rollback workflow (workflow_dispatch)
- **Prevention:** Canary deployments, smoke tests post-deploy, health checks

### Q219: Implement canary with automated rollback
**Answer:**
```yaml
steps:
  - name: Deploy canary (10%)
    run: # update target group weight to 10% canary
  - name: Monitor (5 min)
    run: |
      sleep 300
      ERROR_RATE=$(aws cloudwatch get-metric-statistics ...)
      if [ $ERROR_RATE -gt 5 ]; then exit 1; fi
  - name: Promote to 100%
    if: success()
    run: # update to 100%
  - name: Rollback
    if: failure()
    run: # revert to 0% canary
```
- **Metrics to watch:** Error rate, latency p99, CPU/memory anomalies
- **Tools:** Argo Rollouts, Flagger (Kubernetes), CodeDeploy canary (ECS)

### Q220: Design CI/CD for Terraform
**Answer:**
```yaml
# On PR: Plan
- name: Terraform Plan
  run: terraform plan -out=plan.tfplan
- name: Comment Plan on PR
  uses: actions/github-script@v6  # Post plan output as PR comment

# On merge to main: Apply
- name: Terraform Apply
  run: terraform apply plan.tfplan
```
- **Security:** OIDC for AWS auth, plan file as artifact, restrict apply to main branch
- **Review:** Plan output in PR comment for review before merge
- **Environments:** Separate workflows per environment or use environment protection rules
- **Drift detection:** Scheduled workflow running `terraform plan` → alert if drift detected
- **Blast radius:** Separate pipelines per module/service (independent state files)

---

## SonarQube & Code Quality (Q221-Q240)

### Q221: What is SonarQube and what does it analyze?
**Answer:**
- Static code analysis platform detecting: bugs, vulnerabilities, code smells, security hotspots, duplications
- **Metrics:** Reliability (bugs), Security (vulnerabilities), Maintainability (code smells), Coverage, Duplications
- **Ratings:** A-E scale (A = best). Based on count and severity
- **Languages:** 25+ (Java, JS/TS, Python, C#, Go, C++, PHP, Kotlin, Ruby)
- **Clean as You Code:** Focus on new code quality (not legacy debt)

### Q222: Quality Gates explained
**Answer:**
- Pass/fail criteria for code analysis (deployment gate)
- **Default conditions:** New code coverage > 80%, new bugs = 0, new vulnerabilities = 0, duplications < 3%
- **Custom gates:** Different criteria for different project types
- **Integration:** Fail CI/CD pipeline if quality gate fails
- **Best practice:** Don't lower the gate for legacy projects. Focus on new code instead
- **PR decoration:** Show quality gate status directly on PR (pass/fail with details)

### Q223: SonarQube vs CodeQL vs Semgrep
**Answer:**
| Tool | Type | Strength |
|------|------|----------|
| SonarQube | Comprehensive SAST | Code quality + security, IDE integration, 25+ languages |
| CodeQL | Semantic SAST | Deep data flow analysis, security-focused, query language |
| Semgrep | Pattern SAST | Fast, custom rules easy, lightweight, good for custom patterns |
- **Use together:** SonarQube for quality gate + CodeQL for deep security + Semgrep for custom rules
- **CodeQL:** Free for public repos (GitHub Advanced Security), expensive for private

### Q224: SAST vs DAST vs SCA
**Answer:**
- **SAST (Static):** Analyze source code without running. Early in pipeline. SonarQube, CodeQL, Semgrep, Checkmarx
- **DAST (Dynamic):** Test running application. Find runtime issues. OWASP ZAP, Burp Suite
- **SCA (Software Composition Analysis):** Analyze dependencies for known vulnerabilities. Dependabot, Snyk, WhiteSource
- **When:** SAST at build, SCA at build, DAST at staging/pre-prod
- **Complete pipeline:** SAST (code) + SCA (deps) + DAST (running app) + container scan (images)

### Q225: Code coverage best practices
**Answer:**
- **Target:** 80% for new code (enforced), 60% overall (aspirational)
- **Quality over quantity:** Cover critical paths, not just lines. Branch coverage > line coverage
- **Don't chase 100%:** Diminishing returns after 80%. Test getters/setters = waste
- **Tools:** JaCoCo (Java), Istanbul/c8 (JS), pytest-cov (Python), coverlet (.NET)
- **Integration:** Coverage report → SonarQube → quality gate → fail if below threshold
- **Exclusions:** Generated code, DTOs/models (no logic), test utilities, vendor code

---

## Scenario-Based Questions (Q241-Q270)

### Q241: Design auto-scaling for e-commerce Black Friday traffic (10x normal)
**Answer:**
- **Pre-scaling:** Scheduled scaling 2 hours before (predictive based on last year)
- **Warm pools:** Pre-initialized instances ready to serve immediately
- **CDN:** Cache static content aggressively (reduce origin load by 80%)
- **Database:** Aurora Serverless v2 (auto-scale) + ElastiCache (absorb read load)
- **Queue-based:** SQS for checkout (decouple, handle burst gracefully)
- **Spot + On-Demand:** Reserved for baseline, Spot for burst (with On-Demand fallback)
- **Testing:** Load test at 2x expected peak beforehand

### Q242: Migrate monolith to microservices on EKS
**Answer:**
1. **Strangler pattern:** Don't rewrite everything. Peel off services one at a time
2. **Start with:** Identify bounded contexts (DDD). Extract simplest/most independent service first
3. **Infrastructure:** Set up EKS cluster, CI/CD pipelines, observability stack
4. **Data:** Start with shared database → move to per-service database eventually
5. **Communication:** API Gateway (external), service mesh (internal), event bus (async)
6. **Cutover per service:** Route traffic via API Gateway to new service, keep old code as fallback
7. **Timeline:** 6-18 months depending on monolith size

### Q243: Design multi-region disaster recovery (RTO<5min, RPO<1min)
**Answer:**
- **Active-Active:** Both regions serve traffic simultaneously
- **Data:** Aurora Global Database (RPO<1s), DynamoDB Global Tables, S3 Cross-Region Replication
- **Compute:** EKS/ECS in both regions, independent auto-scaling
- **DNS:** Route 53 latency-based routing with health checks (automatic failover)
- **State:** Externalize all state (no local state in compute)
- **Deployment:** Deploy to both regions simultaneously (GitOps)
- **Testing:** Regular chaos engineering (simulate region failure monthly)

### Q244: Reduce AWS bill by 60% without sacrificing performance
**Answer:**
1. **Right-size (20%):** Compute Optimizer recommendations, downsize over-provisioned instances
2. **Savings Plans/RI (30%):** Commit for steady-state workloads (1yr Compute SP)
3. **Spot (15%):** Batch processing, CI/CD runners, non-critical workloads
4. **Graviton (10%):** ARM instances are 20% cheaper with better performance
5. **Storage:** S3 lifecycle policies (IA after 30d, Glacier after 90d), GP3 over GP2
6. **Serverless:** Lambda for sporadic workloads vs always-on EC2
7. **Clean up:** Delete unused EBS, unattached EIPs, idle load balancers, old snapshots
8. **NAT:** VPC endpoints for S3/DynamoDB (avoid NAT Gateway data charges)

### Q245: Design secure multi-tenant SaaS platform
**Answer:**
- **Authentication:** Cognito User Pool (per-tenant or shared with tenant attribute)
- **Authorization:** Tenant context in JWT → enforce at every layer
- **Data isolation:** DynamoDB (partition key = tenantId), RDS (row-level security or schema per tenant)
- **Network:** Shared infrastructure, isolation via IAM/security context (not VPC per tenant)
- **API:** API Gateway + Usage Plans (per-tenant rate limiting, quotas)
- **Compute:** Shared EKS cluster, namespace per tenant OR shared namespace with RBAC
- **Billing:** Track per-tenant usage via tags + Cost Allocation Tags
- **Compliance:** Encryption per tenant (per-tenant KMS keys), audit logging

### Q246: Implement zero-downtime deployment pipeline
**Answer:**
- **Strategy:** Blue/Green with automated health checks
- **Pipeline:** Build → Test → Deploy to Green → Health check → Shift traffic (canary 10%→50%→100%) → Cleanup Blue
- **Rollback trigger:** Error rate > 1% OR latency > p99 threshold → auto shift back to Blue
- **Database:** Backward-compatible migrations only (add column, never rename/remove in same release)
- **Feature flags:** Deploy code without activating features (decouple deploy from release)
- **Verification:** Synthetic monitoring, smoke tests against new deployment

### Q247: Handle a production database outage
**Answer:**
1. **Detect:** CloudWatch alarm on connections/latency/errors (PagerDuty alert)
2. **Assess:** Multi-AZ failover (automatic, 1-2 min) vs RDS crash vs data corruption
3. **If Multi-AZ:** Automatic failover should handle. Monitor DNS switch
4. **If data issue:** Point-in-time recovery to moment before corruption
5. **Communication:** Status page update, incident channel
6. **Application:** Circuit breaker activates, queue writes if possible, serve from cache
7. **Post-mortem:** Root cause, improve monitoring, test DR runbook

### Q248: Design logging architecture for 1000-microservice platform
**Answer:**
- **Collection:** Fluent Bit sidecar per pod (lightweight, low CPU)
- **Structure:** JSON structured logs with: traceId, spanId, service, timestamp, level, message
- **Routing:** Fluent Bit → Kinesis Data Firehose → S3 (archive) + OpenSearch (search)
- **Real-time:** CloudWatch Logs (critical services only, expensive at scale)
- **Correlation:** Distributed tracing (OpenTelemetry) with trace IDs in all logs
- **Retention:** Hot (OpenSearch): 7 days, Warm: 30 days, Cold (S3): 1 year
- **Cost:** S3 for long-term is 90% cheaper than CloudWatch Logs

### Q249: Kubernetes cluster upgrade strategy (zero-downtime)
**Answer:**
1. **Pre-check:** Review changelog, check deprecated APIs (kubent), verify PDB configured
2. **Control plane:** EKS handles this (one-click upgrade, rolling)
3. **Add-ons:** Upgrade CoreDNS, kube-proxy, VPC CNI to compatible versions
4. **Data plane:** Create new node group (new version) → cordon old → drain old (respects PDB) → delete old
5. **Validation:** Run conformance tests, check all deployments healthy
6. **Rollback plan:** If issues, keep old node group, rollback control plane (not easy, prefer fix-forward)
7. **Schedule:** Upgrade every quarter, never skip more than 1 minor version

### Q250: Design CI/CD for mobile app (iOS + Android)
**Answer:**
- **Build:** Matrix strategy (ios + android), macOS runner for iOS (required), Linux for Android
- **iOS:** Fastlane (build, sign, TestFlight upload), code signing (match)
- **Android:** Gradle build, APK/AAB signing, Google Play upload
- **Testing:** Unit tests per platform, E2E (Detox, Appium), Screenshot tests
- **Distribution:** TestFlight (iOS beta), Firebase App Distribution (Android beta), then stores
- **Versioning:** Auto-increment build number in CI, semantic version for marketing
- **Challenges:** Large build times (cache Pods/Gradle), code signing secrets, device testing (device farms)

### Q251: Implement GitOps for infrastructure and applications
**Answer:**
- **Repo structure:** infra-repo (Terraform) + app-repo (Kubernetes manifests/Helm)
- **Infrastructure:** PR → Terraform plan (comment on PR) → merge → apply (GitHub Actions)
- **Applications:** Commit manifest change → ArgoCD detects → syncs to cluster
- **Image update:** CI builds image → pushes to ECR → updates image tag in manifests → ArgoCD deploys
- **ArgoCD config:** App-of-apps pattern (one root app manages all service apps)
- **Benefits:** Git = audit trail, PR = change approval, revert = rollback, drift detection

### Q252: Troubleshoot high latency in microservices
**Answer:**
1. **Identify:** Distributed tracing (X-Ray/Jaeger) → find slow span in request chain
2. **Isolate:** Which service is slow? Network? Database? External dependency?
3. **Database:** Check slow queries (Performance Insights), connection pool exhaustion, lock contention
4. **Network:** Check DNS resolution time, TCP connection time, TLS handshake
5. **Service mesh:** Envoy metrics show per-hop latency
6. **Code:** CPU profiling (flame graph), memory pressure (GC pauses), thread pool saturation
7. **Fix:** Caching, connection pooling, query optimization, async processing, circuit breaker on slow deps

### Q253: Design event-driven architecture on AWS
**Answer:**
- **Event bus:** EventBridge (rule-based routing), SNS (fan-out), SQS (queuing)
- **Pattern:** API Gateway → Lambda → EventBridge → Multiple consumers (Lambda, SQS, Step Functions)
- **Event sourcing:** DynamoDB Streams or Kinesis as event store
- **CQRS:** Write path (API→Lambda→DynamoDB) separate from Read path (DynamoDB Streams→Lambda→ElastiCache/OpenSearch)
- **Saga pattern:** Step Functions for distributed transactions (compensation on failure)
- **Benefits:** Loose coupling, independent scaling, replay capability, easier to add consumers

### Q254: Implement secrets rotation without downtime
**Answer:**
- **AWS Secrets Manager:** Built-in rotation with Lambda (30/60/90 day schedule)
- **Dual-secret pattern:** 
  1. Create new secret version (AWSPENDING)
  2. Update target service to accept both old and new
  3. Test new credential works
  4. Set new as AWSCURRENT, old as AWSPREVIOUS
- **Application:** Always fetch latest from Secrets Manager (cache with short TTL)
- **Database:** Alternating user strategy (user1 active, rotate user2 in background, switch)
- **K8s:** External Secrets Operator syncs rotated secret → pod restart on secret change

### Q255: Design a cost-effective dev/staging environment
**Answer:**
- **Schedules:** Stop non-prod environments outside business hours (8pm-8am, weekends = 60% savings)
- **Sizing:** Dev = 1/4 production size, Staging = 1/2 production
- **Spot:** All dev/staging compute on Spot instances
- **Serverless:** Fargate + Aurora Serverless (scale to zero idle)
- **Shared services:** Single RDS for multiple dev environments (separate databases)
- **Cleanup:** Auto-delete resources older than 7 days (Lambda scheduled)
- **Savings:** Typically 80% less than production cost

---

## Additional Questions (Q256-Q270)

### Q256: How do you handle configuration management across environments?
**Answer:**
- **Terraform:** Variable files per environment (dev.tfvars, prod.tfvars)
- **Application:** SSM Parameter Store (hierarchical: /app/prod/db_host) or ConfigMaps in K8s
- **Secrets:** AWS Secrets Manager with environment prefixes
- **Feature flags:** LaunchDarkly or AWS AppConfig for runtime configuration
- **Principle:** Same artifact deployed everywhere, configuration changes behavior

### Q257: Design observability for microservices (metrics, logs, traces)
**Answer:**
- **Three Pillars:** Metrics (Prometheus/CloudWatch), Logs (Fluent Bit→OpenSearch), Traces (OpenTelemetry→X-Ray)
- **Correlation:** Trace ID in all logs, metrics tagged with service/environment
- **Dashboards:** Grafana - RED method per service (Rate, Errors, Duration)
- **Alerting:** SLO-based alerts (error budget burn rate), not threshold-based
- **Cost:** Sample traces (10%), aggregate metrics, tier log storage
- **Culture:** Every service must emit standard metrics and structured logs (enforced in CI)

### Q258: How do you handle database schema migrations in CI/CD?
**Answer:**
- **Tools:** Flyway, Liquibase (Java), Alembic (Python), migrate (Go), Prisma migrate
- **Principles:** Forward-only migrations, backward-compatible (expand/contract pattern)
- **Expand/Contract:** 
  1. Add new column (expand) - deploy
  2. Backfill data - deploy code that writes to both
  3. Switch reads to new column - deploy
  4. Remove old column (contract) - deploy
- **CI/CD:** Run migration as pre-deploy step (init container in K8s, pre-hook in Helm)
- **Rollback:** Separate "undo" migration scripts (never auto-rollback schema changes)

### Q259: What is your approach to infrastructure testing?
**Answer:**
- **Static analysis:** tflint (Terraform lint), tfsec/checkov (security), terraform validate
- **Unit tests:** CDK assertions, Terraform test blocks (mock-free validation)
- **Integration tests:** Terratest (Go) - deploy real resources, validate, destroy
- **Contract tests:** Verify module interfaces don't break
- **Compliance tests:** OPA/Sentinel policies (enforce tagging, encryption, approved regions)
- **Pipeline:** Lint → Validate → Plan → Test (non-prod) → Apply

### Q260: How do you implement blue/green for databases?
**Answer:**
- **Read Replica promotion:** Create replica → sync → promote → switch app endpoint
- **Aurora clone:** Clone production database → make changes → switch endpoint
- **DMS:** Continuous replication from old to new → cutover
- **Challenge:** Database changes are hardest part of blue/green (state is the problem)
- **Best practice:** Keep schema backward-compatible, expand/contract, separate schema deploy from app deploy

### Q261: Design auto-healing infrastructure
**Answer:**
- **EC2:** Auto Scaling health checks → unhealthy → terminate → ASG launches new
- **ECS:** Service scheduler maintains desired count → failed task → new task launched
- **K8s:** Deployment controller → pod crash → restart. Node failure → pod rescheduled
- **Database:** Multi-AZ automatic failover
- **Load Balancer:** Health checks → unhealthy target removed from rotation
- **DNS:** Route 53 health checks → failover to healthy region
- **Self-healing code:** Circuit breakers, connection retry, graceful degradation

### Q262: How do you manage Terraform at scale (50+ engineers)?
**Answer:**
- **Structure:** Separate repos/states per team/domain (blast radius)
- **Modules:** Central module registry (private Terraform Registry or Git)
- **Governance:** Sentinel/OPA policies enforced in Terraform Cloud
- **PR workflow:** Auto-plan on PR, require approval + policy pass, auto-apply on merge
- **State:** Terraform Cloud or S3 with strict IAM (teams can only access their states)
- **Standards:** Module template, naming conventions, tagging standards (enforced via policy)
- **Training:** Inner-source contribution model for shared modules

### Q263: Explain your incident response process
**Answer:**
1. **Detect:** Monitoring alert (PagerDuty/OpsGenie) from CloudWatch/Prometheus
2. **Triage:** Severity classification (SEV1-4), assign incident commander
3. **Communicate:** Status page update, Slack incident channel
4. **Investigate:** Check dashboards, logs, recent deployments, trace errors
5. **Mitigate:** Rollback deployment, scale up, failover, block bad traffic
6. **Resolve:** Root fix after stabilization
7. **Post-mortem:** Timeline, root cause, action items (blameless), improve monitoring

### Q264: Design a CI/CD pipeline with security gates
**Answer:**
```
Commit → [SAST: SonarQube + CodeQL] → [SCA: Snyk/Dependabot] →
Build → [Container Scan: Trivy] → [Sign Image: Cosign] →
Deploy to Staging → [DAST: OWASP ZAP] → [Smoke Tests] →
Manual Approval (prod) → [Deploy Prod] → [Verify + Monitor]
```
- **Gates:** Fail on Critical/High vulnerabilities, coverage below threshold, quality gate failure
- **Compliance:** SBOM generation, provenance attestation (SLSA), audit trail
- **Secrets:** OIDC for cloud auth, no stored credentials, secret scanning in pre-commit

### Q265: How would you implement cost allocation and showback?
**Answer:**
- **Tagging strategy:** Mandatory tags: Team, Service, Environment, CostCenter
- **Enforcement:** SCP/IAM denying untagged resource creation, tfsec/Checkov in CI
- **AWS tools:** Cost Explorer (filter by tags), Budgets (alerts), Cost Allocation Tags
- **Showback reports:** Weekly per-team cost reports (Lambda + Cost Explorer API + email/Slack)
- **Optimization opportunities:** Per-team Compute Optimizer recommendations
- **Accountability:** Each team owns their cost, quarterly review with optimization targets

### Q266: Design pod-level autoscaling for mixed workloads
**Answer:**
- **CPU-bound (web servers):** HPA on CPU utilization (target 60%)
- **Memory-bound (caches):** HPA on memory utilization
- **Queue-based (workers):** KEDA with SQS scaler (scale on queue depth, scale to zero when empty)
- **Request-based (API):** HPA on requests-per-second custom metric (Prometheus adapter)
- **Scheduled (reports):** KEDA cron scaler (scale up during business hours)
- **Combine:** Different HPA per deployment, Karpenter for node auto-provisioning underneath

### Q267: Implement compliance as code
**Answer:**
- **IaC policies:** OPA/Rego for Terraform (conftest), Sentinel (Terraform Cloud), Checkov
- **K8s policies:** OPA Gatekeeper or Kyverno (enforce pod security, resource limits, labels)
- **AWS:** Config Rules (detect non-compliant resources), Security Hub (aggregate findings)
- **CI/CD:** Policy checks as pipeline stage (fail build on violation)
- **Automated remediation:** Config Rules → Lambda → auto-fix (e.g., encrypt unencrypted bucket)
- **Audit:** CloudTrail + Config Recorder + regular compliance reports
- **Standards:** CIS Benchmarks, SOC2, PCI-DSS mapped to automated checks

### Q268: How do you handle cross-cutting concerns in microservices?
**Answer:**
- **Authentication/Authorization:** API Gateway (edge) + service mesh (internal mTLS)
- **Logging:** Sidecar pattern (Fluent Bit), structured JSON, correlation IDs
- **Tracing:** OpenTelemetry SDK or auto-instrumentation, sidecar collector
- **Rate limiting:** API Gateway (external), Envoy/Istio (internal service-to-service)
- **Circuit breaking:** Service mesh (App Mesh/Istio) or library (Resilience4j, Polly)
- **Configuration:** Centralized config service (AWS AppConfig, Consul)
- **Key insight:** Push cross-cutting to infrastructure layer (mesh/gateway), not application code

### Q269: Design a disaster recovery test (game day)
**Answer:**
1. **Plan:** Define scope (AZ failure, region failure, DB failure), success criteria, rollback plan
2. **Preparation:** Ensure monitoring/alerting working, team on standby, customer notification
3. **Execute:** Simulate failure (terminate instances, block AZ routes, failover DB)
4. **Observe:** Monitor recovery time (RTO), data loss (RPO), system behavior during degradation
5. **Validate:** Applications recovered? Data consistent? Performance acceptable?
6. **Debrief:** Document gaps, update runbooks, fix issues found
7. **Frequency:** Quarterly for critical systems. Automate with AWS FIS (Fault Injection Simulator)

### Q270: What is your approach to technical debt management?
**Answer:**
- **Track:** SonarQube technical debt metric + manual tracking in backlog
- **Classify:** Security debt (fix NOW), reliability debt (fix this sprint), maintainability debt (schedule)
- **Prevent:** Quality gates (no new debt merged), code reviews, linting
- **Reduce:** 20% sprint capacity reserved for tech debt, tech debt sprints quarterly
- **Measure:** Debt ratio trending over time, new debt vs resolved debt
- **Prioritize:** Risk × frequency of change × customer impact = priority score
- **Culture:** "Leave code better than you found it" (Boy Scout Rule), celebrate debt reduction

