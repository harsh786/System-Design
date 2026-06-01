# Connectivity & Network Issues (#41-50)

> Network issues are the **most frustrating** Glue problems because they're intermittent,
> hard to reproduce, and often misdiagnosed as application bugs. At scale, network becomes
> the bottleneck before compute does.

---

## Issue #41: JDBC Connection Pool Exhaustion

### Severity: P1 | Frequency: Weekly with concurrent jobs

### Symptoms
```
# Error: Cannot get a connection, pool error Timeout waiting for idle object
# OR: Communications link failure - The last packet sent to the server was X ms ago
# OR: Too many connections (max_connections=151 for MySQL/Aurora)

# Multiple Glue jobs hitting same RDS instance simultaneously
# Database slow for application traffic during Glue runs
```

### Root Cause
```
┌─────────────────────────────────────────────────────────────────────┐
│  CONNECTION EXHAUSTION SCENARIO                                      │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Glue Job (100 workers) × 4 connections/executor = 400 connections  │
│  + 2 concurrent jobs = 800 connections                               │
│  + Application connections = 100                                     │
│  Total: 900 connections                                              │
│                                                                      │
│  Aurora max_connections = 1000 (for db.r5.2xlarge)                  │
│  Available: 1000 - 900 = 100 (dangerously close to limit)          │
│                                                                      │
│  When 3rd Glue job starts: BOOM → connection refused                │
└─────────────────────────────────────────────────────────────────────┘
```

### Fix
```python
# Fix 1: Limit connections per executor
jdbc_options = {
    "url": "jdbc:mysql://aurora-cluster:3306/db",
    "dbtable": "large_table",
    "user": "etl_user",
    "password": "***",
    "numPartitions": "20",  # Only 20 parallel connections (not 400!)
    "fetchsize": "10000",
    "connectionPool": "HikariCP",
    "connectionPoolSize": "2"  # Max 2 connections per executor
}

df = spark.read.format("jdbc").options(**jdbc_options).load()

# Fix 2: Use JDBC with explicit partition bounds (controlled parallelism)
df = spark.read.format("jdbc").options(
    url="jdbc:mysql://aurora:3306/db",
    dbtable="orders",
    partitionColumn="order_id",
    lowerBound="1",
    upperBound="100000000",
    numPartitions="10",  # Exactly 10 concurrent connections
    fetchsize="50000"
).load()

# Fix 3: Export to S3 first, then read from S3 (zero ongoing DB pressure)
# Use DMS or Aurora export to S3 → Glue reads from S3
# Zero JDBC connections during processing!

# Fix 4: Use Glue Connection with pool settings
connection_options = {
    "useConnectionProperties": "true",
    "connectionName": "aurora-connection",
    "connectionType": "mysql",
    "sampleSize": "1000",
    # Pool settings in Glue Connection properties:
    # maxConnectionLifetime=600000 (10 min)
    # maxPoolSize=5
}
```

---

## Issue #42: VPC DNS Resolution Failure

### Severity: P1 | Frequency: Monthly (infra changes trigger it)

### Symptoms
```
# Error: UnknownHostException: my-rds-cluster.cluster-xxx.us-east-1.rds.amazonaws.com
# OR: Name or service not known
# Job was working yesterday, nothing in Glue code changed
# VPC changes were made by networking team
```

### Root Cause
```
Glue jobs in VPC use VPC DNS settings. Failures happen when:
1. VPC DNS hostnames disabled (enableDnsHostnames=false)
2. VPC DNS resolution disabled (enableDnsSupport=false)
3. Custom DNS (Route53 Resolver) rules changed
4. Subnet has no NAT Gateway (can't reach public DNS)
5. DHCP option set changed (removed AmazonProvidedDNS)
6. Security group blocks DNS port 53
```

### Fix
```python
# Fix 1: Verify VPC DNS settings (via Terraform/CDK)
# vpc.enable_dns_hostnames = true
# vpc.enable_dns_support = true

# Fix 2: Verify Glue connection uses correct subnet
# Subnet must have:
# - NAT Gateway (for internet access to Glue service endpoints)
# - S3 VPC endpoint (for S3 access without NAT)
# - Route to DNS (port 53 UDP/TCP in security group)

# Fix 3: Use IP address instead of hostname (workaround)
jdbc_url = "jdbc:mysql://10.0.1.50:3306/db"  # Direct IP

# Fix 4: Add VPC endpoints for AWS services
# Required VPC Endpoints for Glue in VPC:
# - com.amazonaws.region.s3 (Gateway endpoint)
# - com.amazonaws.region.glue (Interface endpoint)
# - com.amazonaws.region.logs (Interface endpoint - for CloudWatch)
# - com.amazonaws.region.sts (Interface endpoint - for IAM)

# Terraform:
# resource "aws_vpc_endpoint" "s3" {
#   vpc_id       = aws_vpc.main.id
#   service_name = "com.amazonaws.us-east-1.s3"
#   route_table_ids = [aws_route_table.private.id]
# }
```

---

## Issue #43: ENI (Elastic Network Interface) Limit Exceeded

### Severity: P1 | Frequency: When scaling up rapidly

### Symptoms
```
# Error: Insufficient network interfaces (ENI) in subnet
# Glue job fails to start or starts with fewer workers than requested
# Other services in same subnet also can't launch (Lambda, ECS)
```

### Root Cause
```
Each Glue worker needs 1 ENI. A 200-worker job needs 200 ENIs.
VPC subnets have limited IPs, and AWS accounts have ENI limits:
- Default limit: 5000 ENIs per region
- Each VPC subnet: limited by CIDR (e.g., /24 = 251 usable IPs)

3 concurrent Glue jobs × 200 workers = 600 ENIs in one subnet!
Add Lambda, ECS, EKS = subnet exhaustion.
```

### Fix
```bash
# Fix 1: Use larger subnets
# /24 subnet: 251 IPs → supports ~250 workers total
# /20 subnet: 4091 IPs → supports ~4000 workers total

# Fix 2: Spread across multiple subnets (Glue connection allows multiple)
# Configure Glue Connection with multiple subnets:
# Subnet A: /24 in AZ-a (251 IPs)
# Subnet B: /24 in AZ-b (251 IPs)
# Total: 502 worker capacity

# Fix 3: Request ENI limit increase
aws service-quotas request-service-quota-increase \
    --service-code ec2 \
    --quota-code L-DF5E4CA3 \
    --desired-value 10000

# Fix 4: Stagger Glue job start times
# Don't start 5 × 200-worker jobs simultaneously
# Offset by 5 minutes each to allow ENI release from scaling events

# Fix 5: Use Glue without VPC connection (if possible)
# If only accessing S3/Glue Catalog (public endpoints):
# Don't configure VPC connection → no ENI needed
# VPC connection only needed for RDS, Redshift, Kafka in VPC
```

---

## Issue #44: NAT Gateway Throughput Bottleneck

### Severity: P2 | Frequency: Common at >10Gbps data transfer

### Symptoms
```
# Job progressively slows down during data transfer
# CloudWatch NAT Gateway: BytesProcessed flat at 45 Gbps
# ErrorPortAllocation increasing
# Packets dropped
# S3 reads/writes timing out intermittently
```

### Root Cause
```
NAT Gateway limit: 45 Gbps burst, 5 Gbps sustained per gateway.
100 workers each reading/writing at 500 Mbps = 50 Gbps > NAT capacity.

Also: 55,000 simultaneous connections per destination (port exhaustion).
```

### Fix
```python
# Fix 1: Use S3 VPC Gateway Endpoint (bypasses NAT entirely!)
# S3 Gateway Endpoint: FREE, unlimited bandwidth, zero NAT
# MUST have this for any Glue job doing significant S3 I/O

# Fix 2: Use Interface VPC Endpoints for AWS services
# Glue, CloudWatch, STS → Interface endpoints (bypass NAT)

# Fix 3: Multiple NAT Gateways
# Deploy NAT Gateway per AZ, route each subnet to its own NAT
# Scales NAT bandwidth linearly with AZ count

# Fix 4: Avoid NAT for service-to-service traffic
# If accessing RDS in same VPC → no NAT needed (private routing)
# Only need NAT for: internet access, cross-account, public endpoints

# Fix 5: Use PrivateLink for cross-account access
# Instead of NAT → Internet → Other account
# Use VPC PrivateLink for direct private connectivity
```

---

## Issue #45: S3 Connection Timeout on Large Reads

### Severity: P2 | Frequency: Common during S3 high-traffic periods

### Symptoms
```
# Error: Connection timed out after 50000ms
# OR: Slow down: Please reduce your request rate
# OR: AmazonS3Exception: Connection pool shut down

# Happens especially during:
# - Month-end processing (everyone runs big jobs)
# - Re:Invent week (AWS infra under strain)
# - Concurrent large-scale reads from same prefix
```

### Root Cause
```
S3 per-prefix rate limit: 5,500 GET/s, 3,500 PUT/s per prefix.
"Prefix" = everything up to the last "/" before the object key.

100 workers × 50 files each = 5,000 concurrent GETs (near limit).
Add LIST operations for partition discovery: exceeds 5,500/s.
```

### Fix
```python
# Fix 1: Distribute data across multiple S3 prefixes
# BAD (all under one prefix):
# s3://bucket/data/2024/01/15/file_001.parquet through file_50000.parquet
# All 50K files share prefix "data/2024/01/15/" → 5500 GET/s limit

# GOOD (hash-distributed prefixes):
# s3://bucket/data/a1/2024/01/15/file_001.parquet
# s3://bucket/data/b7/2024/01/15/file_002.parquet
# Each hash prefix gets its own 5500 GET/s quota

# Fix 2: Enable S3 request retry with backoff
spark.conf.set("spark.hadoop.fs.s3a.retry.limit", "20")
spark.conf.set("spark.hadoop.fs.s3a.retry.interval", "500ms")
spark.conf.set("spark.hadoop.fs.s3a.attempts.maximum", "20")
spark.conf.set("spark.hadoop.fs.s3a.connection.timeout", "200000")
spark.conf.set("spark.hadoop.fs.s3a.connection.establish.timeout", "50000")

# Fix 3: Throttle read rate
spark.conf.set("spark.hadoop.fs.s3a.threads.max", "64")  # Limit concurrent S3 connections
spark.conf.set("spark.hadoop.fs.s3a.connection.maximum", "100")  # Total pool size

# Fix 4: Use S3 Transfer Acceleration for large reads
spark.conf.set("spark.hadoop.fs.s3a.endpoint", "s3-accelerate.amazonaws.com")

# Fix 5: Enable S3 Intelligent Tiering for frequently accessed data
# Ensures data stays in Standard tier (fastest access)
```

---

## Issue #46: Cross-AZ Data Transfer Costs and Latency

### Severity: P3 | Frequency: Constant (cost accumulation)

### Symptoms
```
# AWS bill shows $5000/month in data transfer charges
# All traffic is within same region but cross-AZ
# Glue workers in AZ-a reading from RDS in AZ-b
# $0.01/GB cross-AZ × 500TB/month = $5,000
```

### Root Cause
```
Glue job workers may be placed in different AZ than data sources.
Cross-AZ data transfer: $0.01/GB in, $0.01/GB out = $0.02/GB round trip.

For 500TB monthly processing with cross-AZ:
500,000 GB × $0.02 = $10,000/month in transfer alone!
```

### Fix
```python
# Fix 1: Co-locate Glue connection in same AZ as RDS
# Specify subnet in SAME AZ as RDS primary endpoint
# Glue Connection → Security Group → Subnet in AZ-a (same as RDS)

# Fix 2: S3 access is free within region (regardless of AZ)
# S3 doesn't have AZ concept → no cross-AZ charges
# Export from RDS → S3 first, then process from S3

# Fix 3: Use multi-AZ subnet list with preference
# Configure Glue Connection availability zone to match primary data source

# Fix 4: For inter-VPC traffic, use VPC peering or PrivateLink
# Instead of going through internet gateway
```

---

## Issue #47: Kafka Consumer Connection Drops (Streaming ETL)

### Severity: P1 | Frequency: Weekly with Glue Streaming

### Symptoms
```
# Glue Streaming job stops consuming from Kafka
# No errors in Glue logs (silent failure!)
# Lag increases on Kafka consumer group
# Job reports 0 records processed for hours

# Kafka broker logs:
# "Disconnecting consumer group etl-consumer-group due to session timeout"
```

### Root Cause
```
Glue Streaming executor dies silently → consumer leaves group →
partition rebalance → other consumers pick up partitions →
BUT if all executors are failing: no consumer remains → lag grows.

Common causes:
1. session.timeout.ms too short (executor GC pause triggers timeout)
2. max.poll.interval.ms exceeded (processing takes too long)
3. Network blip between Glue VPC and MSK VPC
4. MSK broker maintenance (rolling restart)
```

### Fix
```python
# Fix 1: Tune consumer timeouts
kafka_options = {
    "kafka.bootstrap.servers": "broker1:9092,broker2:9092,broker3:9092",
    "subscribe": "events",
    "kafka.session.timeout.ms": "60000",  # 60s (default: 10s too short)
    "kafka.heartbeat.interval.ms": "10000",
    "kafka.max.poll.interval.ms": "600000",  # 10 min (for slow batches)
    "kafka.request.timeout.ms": "60000",
    "kafka.connections.max.idle.ms": "600000",
    "startingOffsets": "latest",
    "failOnDataLoss": "false"  # Don't crash on expired offsets
}

df = spark.readStream.format("kafka").options(**kafka_options).load()

# Fix 2: Add health check/alert for streaming lag
# CloudWatch Alarm on: MSK ConsumerLag > threshold
# Triggers: restart job, page on-call

# Fix 3: Enable auto-restart on stall
# Monitor processingTime metric
# If processingTime == 0 for > 5 minutes: restart job
```

---

## Issue #48: S3 Access Denied After IAM Policy Change

### Severity: P1 | Frequency: On every IAM/policy deployment

### Symptoms
```
# Error: Access Denied (Service: Amazon S3; Status Code: 403)
# Job was working, suddenly fails after "unrelated" infrastructure change
# Partial access: can read but not write, or vice versa

# Common after:
# - SCP policy update
# - Bucket policy change
# - IAM role boundary change
# - S3 Block Public Access change
# - KMS key policy update
```

### Root Cause
```
AWS IAM policy evaluation chain (ALL must allow):

1. SCP (Organization level) → ALLOW?
2. IAM User/Role policy → ALLOW?
3. Permission boundary → ALLOW?
4. Resource policy (bucket policy) → ALLOW?
5. Session policy (if assumed role) → ALLOW?
6. VPC Endpoint policy → ALLOW?
7. S3 Block Public Access → NOT BLOCKED?
8. KMS key policy (for encrypted buckets) → ALLOW?

If ANY layer denies → Access Denied.
And the error message doesn't tell you WHICH layer denied it!
```

### Fix
```python
# Debugging: Use IAM Policy Simulator
# aws iam simulate-principal-policy \
#   --policy-source-arn arn:aws:iam::123:role/GlueJobRole \
#   --action-names s3:GetObject s3:PutObject \
#   --resource-arns arn:aws:s3:::bucket/path/*

# Fix: Minimum IAM policy for Glue S3 access:
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "s3:GetObject",
                "s3:PutObject",
                "s3:DeleteObject",
                "s3:ListBucket",
                "s3:GetBucketLocation"
            ],
            "Resource": [
                "arn:aws:s3:::my-data-bucket",
                "arn:aws:s3:::my-data-bucket/*"
            ]
        },
        {
            "Effect": "Allow",
            "Action": [
                "kms:Decrypt",
                "kms:GenerateDataKey"
            ],
            "Resource": "arn:aws:kms:us-east-1:123:key/xxx"
        }
    ]
}

# Common gotcha: ListBucket on bucket ARN (no /*)
# GetObject/PutObject on bucket/* (with /*)
# Both required!

# VPC Endpoint policy must also allow the bucket:
# {
#   "Statement": [{
#     "Effect": "Allow",
#     "Principal": "*",
#     "Action": "s3:*",
#     "Resource": ["arn:aws:s3:::my-bucket", "arn:aws:s3:::my-bucket/*"]
#   }]
# }
```

---

## Issue #49: Glue Connection Test Succeeds But Job Fails

### Severity: P2 | Frequency: Common (misleading test)

### Symptoms
```
# "Test Connection" in Glue Console: ✓ SUCCESS
# Actual Glue job: Connection refused / timeout

# Why? The test runs from a DIFFERENT network context than the job.
```

### Root Cause
```
Glue "Test Connection" uses a single connection from Glue service.
Actual job uses MANY connections from worker nodes in YOUR VPC.

Differences:
- Test: single IP → DB (passes security group check for Glue service IP)
- Job: 200 IPs from your subnet → DB (must pass for subnet CIDR range)
- Test: no concurrency stress
- Job: 200 concurrent connections (may exceed DB max_connections)
- Test: no VPC endpoint needed (uses Glue service network)
- Job: needs proper VPC endpoints for Glue/S3/CloudWatch
```

### Fix
```python
# Fix 1: Test from WITHIN the job's network context
# Add diagnostic code at job start:
import socket
import pymysql

def test_connectivity(host, port, user, password):
    """Test actual connectivity from job worker."""
    try:
        # DNS resolution
        ip = socket.gethostbyname(host)
        logger.info(f"DNS resolved: {host} → {ip}")
        
        # TCP connection
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)
        result = sock.connect_ex((host, port))
        sock.close()
        logger.info(f"TCP connect to {host}:{port} → {'OK' if result == 0 else f'FAILED ({result})'}")
        
        # Actual DB connection
        conn = pymysql.connect(host=host, port=port, user=user, password=password)
        conn.close()
        logger.info("Database connection: OK")
        
    except Exception as e:
        logger.error(f"Connectivity test failed: {e}")
        raise

# Fix 2: Ensure security group allows CIDR of Glue subnet
# Inbound rule on RDS security group:
# Type: MySQL/Aurora, Port: 3306, Source: 10.0.1.0/24 (Glue subnet CIDR)
# NOT just the Glue service IP!

# Fix 3: Verify route table has path to target
# Private subnet → NAT Gateway → RDS (if cross-VPC)
# Private subnet → VPC Peering → RDS (if in peered VPC)
# Private subnet → Direct connect (if on-premises)
```

---

## Issue #50: Intermittent Network Timeouts Under Load

### Severity: P2 | Frequency: During peak hours / month-end

### Symptoms
```
# Sporadic errors: "Connection timed out" or "Read timed out"
# Happens randomly across different executors
# Same job succeeds on retry
# More frequent during business hours
# CloudWatch: no clear pattern, but correlated with VPC flow logs showing drops
```

### Root Cause
```
Micro-bursting: 200 workers simultaneously initiate S3/JDBC connections.
Network infrastructure (NAT, ENI, security group state tracking) overwhelmed.

State tracking table overflow:
- Each ENI: tracks connection state (SYN, ESTABLISHED, FIN-WAIT)
- Default: 65,535 tracked connections per ENI
- 200 workers × 500 connections each = 100K connections (exceeds per-ENI limit)
```

### Fix
```python
# Fix 1: Add retry logic with exponential backoff
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, max=60))
def read_with_retry(path):
    return spark.read.parquet(path)

# Fix 2: Stagger connection initialization
import time
import random

def staggered_read(paths, max_concurrent=20):
    """Read paths with staggered start to avoid thundering herd."""
    results = []
    for batch in chunks(paths, max_concurrent):
        time.sleep(random.uniform(0.5, 2.0))  # Random delay between batches
        for path in batch:
            results.append(spark.read.parquet(path))
    return results

# Fix 3: Increase connection and socket timeouts
spark.conf.set("spark.network.timeout", "600s")  # Default: 120s
spark.conf.set("spark.executor.heartbeatInterval", "60s")
spark.conf.set("spark.hadoop.fs.s3a.connection.timeout", "300000")  # 5 min
spark.conf.set("spark.hadoop.fs.s3a.socket.timeout", "300000")

# Fix 4: Enable connection pooling and keepalive
spark.conf.set("spark.hadoop.fs.s3a.connection.maximum", "200")
spark.conf.set("spark.hadoop.fs.s3a.threads.keepalivetime", "60")

# Fix 5: Use dedicated subnet for Glue (isolation from other services)
# Prevents connection state table competition with Lambda/ECS
```

---

## Connectivity Troubleshooting Flowchart

```
┌─────────────────────────────────────────────────────────────────────┐
│                    CONNECTIVITY DIAGNOSIS                             │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Can't connect?                                                      │
│  ├── DNS failure?                                                    │
│  │   ├── VPC DNS enabled? → Issue #42                               │
│  │   └── VPC endpoint present? → Issue #42                          │
│  │                                                                   │
│  ├── TCP connection refused?                                         │
│  │   ├── Security group allows Glue subnet? → Issue #49            │
│  │   ├── ENI limit? → Issue #43                                     │
│  │   └── Route table correct? → Issue #42                           │
│  │                                                                   │
│  ├── Connection timeout?                                             │
│  │   ├── NAT Gateway bottleneck? → Issue #44                       │
│  │   ├── S3 throttling? → Issue #45                                 │
│  │   └── Intermittent under load? → Issue #50                       │
│  │                                                                   │
│  ├── Access denied?                                                  │
│  │   └── IAM/bucket/KMS/VPC endpoint policy? → Issue #48           │
│  │                                                                   │
│  └── Connection drops after running?                                 │
│      ├── JDBC pool exhausted? → Issue #41                           │
│      └── Kafka session timeout? → Issue #47                         │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```
