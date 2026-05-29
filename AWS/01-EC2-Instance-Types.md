# EC2 Instance Types & Sizes - Complete Guide

## 1. What is Amazon EC2?

Amazon Elastic Compute Cloud (EC2) provides resizable compute capacity in the cloud. It allows you to launch virtual servers (instances) on demand.

### Key Concepts
- **Hypervisor**: AWS uses the Nitro Hypervisor (lightweight KVM-based) replacing the older Xen hypervisor
- **Bare Metal**: Some instances (`.metal`) provide direct access to hardware
- **AMI (Amazon Machine Image)**: Template containing OS, application server, and applications

### EC2 Instance Lifecycle

```
Pending → Running → Stopping → Stopped → Terminated
                  → Shutting-down → Terminated
                  → Running (Reboot)
```

| State | Description | Billing |
|-------|-------------|---------|
| Pending | Instance is launching | No charge |
| Running | Instance is active | Charged |
| Stopping | Instance is stopping | No charge (EBS-backed) |
| Stopped | Instance is off | No compute charge (EBS charges apply) |
| Terminated | Instance deleted | No charge |

### Tenancy Models
- **Shared (default)**: Multiple AWS accounts share same physical hardware
- **Dedicated Instance**: Hardware dedicated to your account, may share with other instances in same account
- **Dedicated Host**: Entire physical server dedicated to you, visibility into sockets/cores (for licensing)

---

## 2. Instance Families - Complete Breakdown

### Instance Naming Convention

```
m5a.2xlarge
│││  │
││├── a = AMD processor (other attributes: n=network, d=local disk, g=Graviton)
│├─── 5 = generation number
├──── m = family (General Purpose)
     2xlarge = size
```

### Attributes in Instance Names
| Letter | Meaning |
|--------|---------|
| a | AMD processors |
| g | AWS Graviton (ARM-based) |
| i | Intel processors |
| d | Local NVMe storage |
| n | Network optimized |
| b | Block storage optimized |
| e | Extra storage or memory |
| z | High frequency |
| flex | Flexible (choose vCPU/memory) |

---

### 2.1 General Purpose (T, M series)

**Use Cases**: Web servers, code repositories, development environments, small databases

#### T-Series (Burstable Performance)

| Instance | vCPU | Memory | Network | Use Case |
|----------|------|--------|---------|----------|
| t3.nano | 2 | 0.5 GiB | Up to 5 Gbps | Micro workloads |
| t3.micro | 2 | 1 GiB | Up to 5 Gbps | Low-traffic sites |
| t3.small | 2 | 2 GiB | Up to 5 Gbps | Small apps |
| t3.medium | 2 | 4 GiB | Up to 5 Gbps | Light production |
| t3.large | 2 | 8 GiB | Up to 5 Gbps | Standard apps |
| t3.xlarge | 4 | 16 GiB | Up to 5 Gbps | Medium apps |
| t3.2xlarge | 8 | 32 GiB | Up to 5 Gbps | Larger apps |

**CPU Credits System**:
- Instances earn credits when idle (below baseline)
- Spend credits when bursting above baseline
- T2: Standard mode (stop when credits exhausted) or Unlimited mode
- T3/T3a/T4g: Unlimited mode by default
- Baseline performance: t3.micro = 10%, t3.small = 20%, t3.medium = 20%

#### M-Series (Fixed Performance)

| Instance | vCPU | Memory | Network | Processor |
|----------|------|--------|---------|-----------|
| m5.large | 2 | 8 GiB | Up to 10 Gbps | Intel Xeon Platinum |
| m5.xlarge | 4 | 16 GiB | Up to 10 Gbps | Intel Xeon Platinum |
| m5.2xlarge | 8 | 32 GiB | Up to 10 Gbps | Intel Xeon Platinum |
| m5.4xlarge | 16 | 64 GiB | Up to 10 Gbps | Intel Xeon Platinum |
| m5a.large | 2 | 8 GiB | Up to 10 Gbps | AMD EPYC (10% cheaper) |
| m6i.large | 2 | 8 GiB | Up to 12.5 Gbps | Intel Xeon 3rd Gen |
| m6g.large | 2 | 8 GiB | Up to 10 Gbps | Graviton2 (20% better price/perf) |
| m7g.large | 2 | 8 GiB | Up to 12.5 Gbps | Graviton3 (25% better than m6g) |

---

### 2.2 Compute Optimized (C series)

**Use Cases**: Batch processing, media transcoding, HPC, scientific modeling, gaming servers, ML inference, ad serving

| Instance | vCPU | Memory | Network | Notes |
|----------|------|--------|---------|-------|
| c5.large | 2 | 4 GiB | Up to 10 Gbps | Intel Xeon Platinum 8000 |
| c5.9xlarge | 36 | 72 GiB | 10 Gbps | High compute |
| c5.18xlarge | 72 | 144 GiB | 25 Gbps | Maximum compute |
| c5n.18xlarge | 72 | 192 GiB | 100 Gbps | Network intensive |
| c6g.large | 2 | 4 GiB | Up to 10 Gbps | Graviton2 |
| c7g.16xlarge | 64 | 128 GiB | 30 Gbps | Graviton3 |

**Key**: 2:1 vCPU-to-memory ratio (vs 4:1 for M-series)

---

### 2.3 Memory Optimized (R, X, z series)

**Use Cases**: In-memory databases (Redis, Memcached), real-time big data analytics, SAP HANA

| Instance | vCPU | Memory | Network | Notes |
|----------|------|--------|---------|-------|
| r5.large | 2 | 16 GiB | Up to 10 Gbps | Standard memory |
| r5.24xlarge | 96 | 768 GiB | 25 Gbps | Large in-memory |
| r6g.large | 2 | 16 GiB | Up to 10 Gbps | Graviton2 |
| x1.16xlarge | 64 | 976 GiB | 10 Gbps | SAP HANA |
| x1e.32xlarge | 128 | 3,904 GiB | 25 Gbps | Extreme memory |
| x2idn.32xlarge | 128 | 2,048 GiB | 100 Gbps | Latest gen |
| z1d.12xlarge | 48 | 384 GiB | 25 Gbps | High frequency (4.0 GHz) |

**Key**: 8:1 memory-to-vCPU ratio for R-series, 15:1+ for X-series

---

### 2.4 Storage Optimized (I, D, H series)

**Use Cases**: Data warehousing, distributed file systems (HDFS), high sequential read/write

| Instance | vCPU | Memory | Storage | Network |
|----------|------|--------|---------|---------|
| i3.large | 2 | 15.25 GiB | 1x475 NVMe SSD | Up to 10 Gbps |
| i3.16xlarge | 64 | 488 GiB | 8x1900 NVMe SSD | 25 Gbps |
| i3en.24xlarge | 96 | 768 GiB | 8x7500 NVMe SSD | 100 Gbps |
| d2.8xlarge | 36 | 244 GiB | 24x2000 HDD | 10 Gbps |
| d3.8xlarge | 32 | 256 GiB | 24x2000 NVMe HDD | 25 Gbps |
| h1.16xlarge | 64 | 256 GiB | 8x2000 HDD | 25 Gbps |

---

### 2.5 Accelerated Computing (P, G, Inf, Trn series)

**Use Cases**: Machine learning training/inference, graphics rendering, video encoding

| Instance | GPUs | GPU Memory | Use Case |
|----------|------|-----------|----------|
| p3.2xlarge | 1x V100 | 16 GiB | ML training |
| p3.16xlarge | 8x V100 | 128 GiB | Large-scale ML |
| p4d.24xlarge | 8x A100 | 320 GiB | Advanced ML/HPC |
| p5.48xlarge | 8x H100 | 640 GiB | Foundation models |
| g4dn.xlarge | 1x T4 | 16 GiB | ML inference, graphics |
| g5.48xlarge | 8x A10G | 192 GiB | Graphics-intensive |
| inf1.xlarge | 1x Inferentia | - | ML inference (cost-effective) |
| inf2.48xlarge | 12x Inferentia2 | - | Large model inference |
| trn1.32xlarge | 16x Trainium | - | ML training (cost-effective) |

---

### 2.6 HPC Optimized

| Instance | vCPU | Memory | Network | Use Case |
|----------|------|--------|---------|----------|
| hpc6a.48xlarge | 96 | 384 GiB | 100 Gbps EFA | Computational fluid dynamics |
| hpc7g.16xlarge | 64 | 128 GiB | 200 Gbps EFA | Weather modeling |

---

## 3. Instance Sizes

| Size | Relative | Typical vCPU | Typical Memory |
|------|----------|--------------|----------------|
| nano | 1x | 1-2 | 0.5 GiB |
| micro | 2x | 1-2 | 1 GiB |
| small | 4x | 1-2 | 2 GiB |
| medium | 8x | 1-2 | 4 GiB |
| large | 16x | 2 | 8 GiB |
| xlarge | 32x | 4 | 16 GiB |
| 2xlarge | 64x | 8 | 32 GiB |
| 4xlarge | 128x | 16 | 64 GiB |
| 8xlarge | 256x | 32 | 128 GiB |
| 12xlarge | 384x | 48 | 192 GiB |
| 16xlarge | 512x | 64 | 256 GiB |
| 24xlarge | 768x | 96 | 384 GiB |
| metal | Full host | All cores | All memory |

---

## 4. Pricing Models

### 4.1 On-Demand
- Pay by the second (minimum 60 seconds) for Linux
- Pay by the hour for Windows
- No upfront commitment
- **Best for**: Unpredictable workloads, short-term, testing

### 4.2 Reserved Instances (RI)

| Payment Option | Discount | Cash Flow |
|---------------|----------|-----------|
| All Upfront | Up to 72% | Pay everything now |
| Partial Upfront | Up to 66% | Pay some now + monthly |
| No Upfront | Up to 40% | Monthly only |

**Types**:
- **Standard RI**: Cannot change instance family; can change AZ, size, networking
- **Convertible RI**: Can change family, OS, tenancy; less discount (up to 66%)
- **Term**: 1 year or 3 years

### 4.3 Savings Plans

| Type | Flexibility | Discount |
|------|-------------|----------|
| Compute Savings Plan | Any region, family, OS, tenancy | Up to 66% |
| EC2 Instance Savings Plan | Specific family in a region | Up to 72% |

### 4.4 Spot Instances
- Up to **90% discount** vs On-Demand
- Can be interrupted with 2-minute warning
- **Spot Fleet**: Collection of Spot + optional On-Demand instances
- **Strategies**: lowestPrice, diversified, capacityOptimized, priceCapacityOptimized

**Handling Interruptions**:
```bash
# Check for interruption notice (poll every 5 seconds)
TOKEN=$(curl -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 21600")
curl -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/spot/instance-action
```

### 4.5 Dedicated Hosts
- Entire physical server
- Visibility into sockets, cores, host ID
- **Use case**: Compliance, server-bound software licenses (Windows Server, SQL Server, SUSE)
- Can use with RI for cost savings

### 4.6 Capacity Reservations
- Reserve capacity in a specific AZ
- No billing discount (combine with RI/Savings Plans)
- Ensures capacity availability

---

## 5. EC2 Networking

### Elastic Network Interface (ENI)
- Virtual network card
- Attributes: Primary private IPv4, secondary IPv4s, one Elastic IP per private IP, one public IP, security groups, MAC address
- Can attach/detach and move between instances (same AZ)

### Enhanced Networking (ENA)
- Higher bandwidth, higher PPS, lower latency
- Uses SR-IOV (Single Root I/O Virtualization)
- Up to 100 Gbps
- No additional charge

### Elastic Fabric Adapter (EFA)
- For HPC and ML workloads
- OS-bypass for lower latency
- Only supported on specific instance types
- Works with MPI (Message Passing Interface)

### Placement Groups

| Type | Description | Use Case |
|------|-------------|----------|
| **Cluster** | Instances in same rack, same AZ | Low-latency HPC, tightly coupled |
| **Spread** | Each instance on different hardware (max 7/AZ) | High availability, critical instances |
| **Partition** | Groups of instances in different partitions/racks | HDFS, HBase, Cassandra |

### IP Addresses
- **Private IP**: Retained until instance terminated
- **Public IP**: Changes on stop/start (dynamic)
- **Elastic IP**: Static public IP, persists, $0.005/hr when NOT attached

---

## 6. EC2 Storage

### EBS Volume Types

| Type | IOPS | Throughput | Size | Use Case |
|------|------|------------|------|----------|
| gp3 | 3,000-16,000 | 125-1,000 MB/s | 1 GiB-16 TiB | General SSD (default) |
| gp2 | 100-16,000 (3 IOPS/GiB) | 250 MB/s | 1 GiB-16 TiB | Legacy general SSD |
| io2 Block Express | Up to 256,000 | 4,000 MB/s | 4 GiB-64 TiB | Critical databases |
| io2 | Up to 64,000 | 1,000 MB/s | 4 GiB-16 TiB | High-performance DB |
| io1 | Up to 64,000 | 1,000 MB/s | 4 GiB-16 TiB | Legacy high-perf |
| st1 | 500 | 500 MB/s | 125 GiB-16 TiB | Big data, log processing |
| sc1 | 250 | 250 MB/s | 125 GiB-16 TiB | Cold storage, infrequent |

### EBS Key Features
- **Multi-Attach**: io1/io2 can attach to up to 16 Nitro instances (same AZ)
- **Encryption**: AES-256, minimal latency impact, KMS keys
- **Snapshots**: Incremental, stored in S3, can copy cross-region
- **EBS-Optimized**: Dedicated bandwidth for EBS I/O

### Instance Store
- Physically attached to host
- Highest I/O performance (millions of IOPS)
- Data LOST on stop/terminate/hardware failure
- Cannot be detached/reattached
- **Use case**: Buffers, caches, temp data, scratch data

---

## 7. Auto Scaling

### Components
1. **Launch Template** (recommended) / Launch Configuration (legacy)
2. **Auto Scaling Group (ASG)**
3. **Scaling Policies**

### Scaling Policy Types

| Policy | How it Works | Best For |
|--------|-------------|----------|
| Target Tracking | Maintain metric at target value (e.g., CPU at 50%) | Most workloads |
| Step Scaling | Add/remove based on alarm thresholds | Variable scaling needs |
| Simple Scaling | Single adjustment, cooldown period | Basic scaling |
| Scheduled | Scale at specific times | Predictable patterns |
| Predictive | ML-based, forecasts and pre-scales | Recurring patterns |

### Key Concepts
- **Desired Capacity**: Target number of instances
- **Min/Max**: Boundaries for scaling
- **Cooldown**: Period after scaling before next action (default 300s)
- **Warm Pool**: Pre-initialized instances for faster scale-out
- **Instance Refresh**: Rolling replacement of instances (for AMI updates)

### Lifecycle Hooks
```
Pending → Pending:Wait → Pending:Proceed → InService
InService → Terminating:Wait → Terminating:Proceed → Terminated
```
Use for: Installing software, pulling data, registering with services before going live

### Health Checks
- **EC2**: Instance status checks (default)
- **ELB**: Load balancer health checks
- **Custom**: Your own health check logic

---

## 8. EC2 Security

### Security Groups
- **Stateful**: Return traffic automatically allowed
- **Default**: All inbound denied, all outbound allowed
- Can reference other security groups
- Changes take effect immediately
- Multiple SGs per instance, multiple instances per SG

### Key Pairs
- RSA or ED25519
- Public key stored by AWS, private key by you
- Linux: SSH access
- Windows: Decrypt administrator password

### IAM Roles for EC2
- Never store credentials on instances
- Instance profile wraps the IAM role
- Temporary credentials via instance metadata
- Automatically rotated

### Instance Metadata Service (IMDS)
```bash
# IMDSv1 (less secure - vulnerable to SSRF)
curl http://169.254.169.254/latest/meta-data/

# IMDSv2 (requires token - recommended)
TOKEN=$(curl -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 21600")
curl -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/
```

**Available metadata**: instance-id, ami-id, public-hostname, iam/security-credentials/, placement/availability-zone

### Nitro Enclaves
- Isolated compute environment within EC2
- No persistent storage, no admin access, no external networking
- Use for: Processing sensitive data (PII, financial, healthcare)
- Cryptographic attestation

---

## 9. Advanced EC2

### AMI (Amazon Machine Image)
- Template for root volume + launch permissions + block device mapping
- Types: Public, Private, Marketplace
- Regional (can copy cross-region)
- **Creation**: Instance → Stop → Create AMI → Launch new instances

### User Data
```bash
#!/bin/bash
yum update -y
yum install -y httpd
systemctl start httpd
echo "Hello from $(hostname)" > /var/www/html/index.html
```
- Runs only on first boot (by default)
- Runs as root
- Maximum 16 KB
- Base64 encoded

### EC2 Hibernation
- RAM contents saved to EBS root volume
- Instance must be EBS-backed, encrypted root volume
- RAM < 150 GiB
- Faster startup vs cold start
- Cannot hibernate for more than 60 days

### EC2 Image Builder
- Automate creation, maintenance, validation of AMIs
- Pipeline: Source image → Build → Test → Distribute
- Schedule-based or trigger-based
- Cross-account, cross-region distribution

---

## 10. Scenario-Based Interview Questions

### Q1: Your application needs consistent low-latency performance. Which instance type?
**Answer**: Use **C5 or C6i** (Compute Optimized) for CPU-bound workloads, or **z1d** for highest single-thread performance (4.0 GHz). If memory-bound, use **R6i**. Avoid T-series as burstable performance is inconsistent. Use **Cluster Placement Group** for inter-instance low latency. Enable **Enhanced Networking (ENA)** for lower network latency.

### Q2: How to reduce EC2 costs by 70% for batch processing?
**Answer**:
1. Use **Spot Instances** (up to 90% discount)
2. Implement **Spot Fleet** with diversified strategy across multiple instance types/AZs
3. Use **checkpointing** to save progress and resume on interruption
4. Combine with **SQS** for job queue - workers process from queue, if interrupted another picks up
5. Use **Graviton instances** (20% cheaper for compatible workloads)
6. Right-size instances using **CloudWatch** metrics and **Compute Optimizer**

### Q3: Spot instance about to terminate - how to handle gracefully?
**Answer**:
1. Poll metadata endpoint every 5 seconds for interruption notice (2-min warning)
2. Register instance for **Spot interruption notices** via CloudWatch Events/EventBridge
3. On notice: drain connections from load balancer, save state to S3/DynamoDB, send SQS message for another instance to pick up
4. Use **Spot Instance interruption handler** (open source solution)
5. Architecture: Make workloads stateless, use external state stores
6. Consider **Spot blocks** for defined-duration workloads (1-6 hours)

### Q4: Design auto-scaling for predictable daily traffic spikes
**Answer**:
1. **Scheduled Scaling**: Pre-scale before known peak (e.g., 8 AM scale to 10 instances)
2. **Predictive Scaling**: Let AWS ML forecast and pre-provision
3. **Target Tracking**: CPU at 60% as baseline
4. **Warm Pool**: Keep stopped instances ready for instant scale-out
5. Combine: Scheduled for known peaks + Target Tracking for unexpected + Warm Pool for speed
6. Set appropriate cooldowns to prevent flapping

### Q5: How to choose between T3 and M5 for a web server?
**Answer**:
- **T3**: If average CPU < 20-30%, traffic is bursty, cost-sensitive, development/staging
- **M5**: If consistent CPU usage > 40%, production with steady load, cannot tolerate throttling
- **Analysis**: Use CloudWatch CPUUtilization + CPUCreditBalance. If credits consistently depleted → switch to M5
- **Cost**: T3.large ($0.0832/hr) vs M5.large ($0.096/hr) - T3 cheaper if truly burstable

### Q6: Instance is unreachable after reboot - troubleshooting steps?
**Answer**:
1. Check **Instance Status Checks**: System (hardware) vs Instance (OS) failures
2. Get **System Log** (console output) from EC2 console - check for kernel panic, fsck errors
3. Check **Security Group**: Was it modified? Port 22/3389 open?
4. Check **NACL**: Stateless - both inbound AND outbound rules needed
5. Check **Route Table**: Is there a route to IGW for public instances?
6. Check **Elastic IP**: Did public IP change on restart? (Use Elastic IP)
7. Check **Key Pair**: Correct .pem file?
8. **Recovery**: Detach root volume → attach to working instance → fix → reattach

### Q7: How to migrate from on-prem to EC2?
**Answer**:
1. **Assessment**: Use AWS Migration Hub + Application Discovery Service
2. **VM Import**: Use `aws ec2 import-image` or AWS Server Migration Service (SMS)
3. **CloudEndure/MGN (Application Migration Service)**: Continuous block-level replication
4. **Strategy**: Rehost (lift-and-shift), Replatform (minor optimizations), or Refactor
5. **Steps**: Install replication agent → continuous sync → test → cutover
6. **Network**: Set up VPN/Direct Connect for hybrid connectivity during migration

### Q8: Your application needs 1 million IOPS. Design the storage solution.
**Answer**:
1. Single EBS: **io2 Block Express** supports up to 256,000 IOPS
2. For 1M IOPS: Use **Instance Store** (i3en instances provide 2M+ random IOPS)
3. Alternative: RAID 0 across multiple io2 volumes (stripe for performance)
4. If data must persist: io2 Block Express + application-level replication
5. Consider: Is this sequential or random? Sequential → multiple st1 in RAID 0

### Q9: Design a cost-effective architecture for a startup with variable traffic (10 to 10,000 users)
**Answer**:
1. **Minimum**: 2 On-Demand t3.medium (RI for baseline) across 2 AZs
2. **Auto Scaling**: Target tracking at 60% CPU, min=2, max=20
3. **Mix**: Reserved for min capacity + Spot for scaling (with fallback to On-Demand)
4. **Savings**: Compute Savings Plan for baseline, Spot for variable
5. **Graviton**: Use t4g/m6g for 20% savings if app supports ARM
6. **Right-size**: Start small, monitor with Compute Optimizer, adjust quarterly

### Q10: How do you ensure high availability for EC2 instances?
**Answer**:
1. **Multi-AZ**: Distribute across at least 2-3 AZs
2. **Auto Scaling Group**: Automatically replace unhealthy instances
3. **Load Balancer**: ALB/NLB distributes traffic, health checks detect failures
4. **Spread Placement Group**: Ensure instances on different hardware
5. **Auto-recovery**: CloudWatch alarm → EC2 auto-recovery action
6. **Data**: EBS Multi-AZ replication or application-level replication
7. **DNS**: Route 53 failover routing for cross-region HA

### Q11: How do you handle a security breach on an EC2 instance?
**Answer**:
1. **Isolate**: Change security group to block all inbound/outbound (keep for forensics)
2. **Snapshot**: Create EBS snapshots immediately for forensic analysis
3. **Metadata**: Check CloudTrail for unauthorized API calls
4. **Memory**: If possible, capture memory dump before stopping
5. **Investigate**: Look at VPC Flow Logs, instance system log
6. **Remediate**: Rotate all credentials, patch AMIs, update security groups
7. **Prevent**: Enable GuardDuty, use IMDSv2, restrict IAM roles

### Q12: You need to run a Windows SQL Server workload with BYOL. What's the approach?
**Answer**:
1. Use **Dedicated Hosts** (required for BYOL with per-core/per-socket licensing)
2. Instance type: **r5.4xlarge** or larger (memory optimized for SQL Server)
3. Storage: **io2** volumes for database files, gp3 for logs
4. License tracking: Use **AWS License Manager**
5. Alternative: Use **Amazon RDS for SQL Server** with License Included (no BYOL hassle)
6. HA: Always On Availability Groups across AZs on Dedicated Hosts

### Q13: Your batch job processes 1TB of data. Design for minimum cost.
**Answer**:
1. Use **Spot Instances** (c5.4xlarge or c6g.4xlarge for compute-heavy processing)
2. Data in **S3** - pull chunks, process, push results back
3. **Checkpointing**: Save progress to S3 every 5 minutes
4. Use **SQS** to partition work into messages
5. **Spot Fleet** with diversified strategy (6+ instance types to reduce interruption)
6. Estimated cost: ~90% less than On-Demand

### Q14: How do you implement blue/green deployments with EC2?
**Answer**:
1. **Two ASGs**: Blue (current) and Green (new version)
2. Green ASG launches with new AMI/Launch Template
3. Test Green independently (internal ALB or weighted target group)
4. **Switch**: Update ALB listener rules OR swap Route 53 weighted records
5. **Rollback**: Switch back to Blue if issues detected
6. **Cleanup**: Terminate Blue ASG after validation period
7. Alternative: Use **CodeDeploy** with blue/green deployment type

### Q15: Your application running on m5.2xlarge has memory pressure. What do you do?
**Answer**:
1. **Verify**: Check CloudWatch memory metrics (custom metric via CloudWatch Agent)
2. **Quick fix**: Vertical scale to m5.4xlarge (double memory: 32→64 GiB)
3. **Better**: Identify memory leak in application (heap dumps, profiling)
4. **Alternatives**: 
   - Switch to **r5.2xlarge** (same vCPU, more memory: 64 GiB)
   - Add swap space on EBS (not recommended for production)
   - Scale horizontally (add more instances + distribute load)
5. **Long-term**: Use **Compute Optimizer** for right-sizing recommendations
