# Amazon RDS & Database Services - Complete Guide

## 1. RDS Overview

### What is RDS (Relational Database Service)?

Amazon RDS is a fully managed relational database service that automates time-consuming administration tasks such as hardware provisioning, database setup, patching, and backups. It allows you to focus on application logic rather than database infrastructure.

### Supported Engines

| Engine | Versions | Notes |
|--------|----------|-------|
| MySQL | 5.7, 8.0 | Most popular open-source RDBMS |
| PostgreSQL | 12-16 | Advanced open-source with extensions |
| MariaDB | 10.4-10.11 | MySQL fork with enhancements |
| Oracle | 12c, 19c, 21c | Enterprise and Standard Edition |
| SQL Server | 2016-2022 | Express, Web, Standard, Enterprise |
| Aurora | MySQL 5.7/8.0, PostgreSQL 13-16 | AWS-native, cloud-optimized |

### Managed vs Self-Managed (EC2-hosted)

**What AWS handles in RDS:**
- OS and engine patching (configurable maintenance window)
- Automated backups and point-in-time recovery
- High availability (Multi-AZ failover)
- Storage scaling
- Hardware failure detection and recovery
- Monitoring and metrics

**What you still manage:**
- Schema design and optimization
- Query tuning
- Index management
- Application-level connection handling
- Parameter tuning (via Parameter Groups)

### RDS vs EC2-Hosted Database Decision

| Factor | RDS | EC2-Hosted |
|--------|-----|------------|
| Admin overhead | Low | High |
| OS access | None (no SSH) | Full root/admin |
| Engine choice | 6 supported engines | Any engine |
| Custom software | No | Yes (agents, tools) |
| Replication | Managed | Manual setup |
| Cost | Higher per-instance | Lower per-instance, higher ops cost |
| Compliance | Some features locked | Full control |

**Choose EC2 when:** you need OS-level access, unsupported engine (e.g., Db2, CockroachDB), specific version not available, or custom replication topology.

**Choose RDS when:** you want reduced operational burden, standard engine requirements, built-in HA/DR, and automated backups.

---

## 2. RDS Architecture

### DB Instance Classes

Instance classes determine compute and memory capacity:

**Burstable (db.t3, db.t4g):**
- Variable workloads with baseline + burst
- CPU credits model (accumulate during low usage)
- Good for: dev/test, small production workloads
- Example: db.t3.medium (2 vCPU, 4 GiB RAM)

**Memory-Optimized (db.r5, db.r6g, db.r7g):**
- High memory-to-CPU ratio
- For memory-intensive workloads (large datasets in buffer pool)
- Graviton (g suffix): 20% better price-performance
- Example: db.r6g.2xlarge (8 vCPU, 64 GiB RAM)

**General Purpose (db.m5, db.m6g, db.m7g):**
- Balanced compute and memory
- Good default choice for most workloads
- Example: db.m6g.large (2 vCPU, 8 GiB RAM)

### Storage Types

**gp3 (General Purpose SSD) - Recommended:**
- Baseline: 3,000 IOPS, 125 MiB/s throughput
- Scalable: up to 16,000 IOPS, 1,000 MiB/s (independent of size)
- Size: 20 GiB - 64 TiB
- Cost-effective for most workloads

**gp2 (General Purpose SSD) - Legacy:**
- IOPS tied to volume size: 3 IOPS/GiB (burst to 3,000)
- Must increase storage to get more IOPS
- Size: 20 GiB - 64 TiB

**io1/io2 (Provisioned IOPS):**
- Consistent high-performance I/O
- Up to 256,000 IOPS (io2 Block Express)
- For I/O-intensive workloads (OLTP, large databases)
- io2: 99.999% durability (vs io1: 99.9%)

**Magnetic (standard) - Legacy:**
- Previous generation, not recommended
- Up to 1,000 IOPS
- Only for backward compatibility

### Storage Auto Scaling

Automatically increases storage when running low:

```
Configuration:
- Free storage threshold: < 10% of allocated
- Low storage lasts > 5 minutes
- At least 6 hours since last modification
- Scales in increments: max(5 GiB, 10% of current)
- Maximum storage threshold: you set the upper limit
```

**Best practice:** Set maximum storage threshold to prevent runaway costs. Monitor `FreeStorageSpace` metric.

### DB Subnet Group

A DB Subnet Group defines which subnets (and AZs) RDS can place instances in:

```
DB Subnet Group: "prod-db-subnets"
├── subnet-abc123 (us-east-1a, 10.0.10.0/24)
├── subnet-def456 (us-east-1b, 10.0.11.0/24)
└── subnet-ghi789 (us-east-1c, 10.0.12.0/24)
```

- Must include subnets in at least 2 AZs
- Use private subnets (no internet gateway route)
- Multi-AZ deployment places primary and standby in different subnets/AZs

### Parameter Groups

Engine-level configuration (equivalent to my.cnf, postgresql.conf):

```
DB Parameter Group: "prod-mysql80-params"
├── max_connections = 1000
├── innodb_buffer_pool_size = {DBInstanceClassMemory*3/4}
├── slow_query_log = 1
├── long_query_time = 2
└── character_set_server = utf8mb4
```

- **Dynamic parameters:** Applied immediately without reboot
- **Static parameters:** Require reboot to apply
- Default parameter group is not modifiable; create custom

### Option Groups

Engine-specific optional features:

- **Oracle:** TDE (Transparent Data Encryption), Spatial, XMLDB, Statspack
- **SQL Server:** Native Backup/Restore, TDE, SSAS, SSIS
- **MySQL:** Memcached plugin, MariaDB audit plugin

---

## 3. High Availability - Multi-AZ

### Synchronous Replication

Multi-AZ creates a standby replica in a different AZ with synchronous replication:

```
┌─────────────────┐         Synchronous          ┌─────────────────┐
│   Primary DB    │ ──────── Replication ───────► │   Standby DB    │
│  (us-east-1a)  │                               │  (us-east-1b)   │
│  Read/Write     │                               │  No client      │
│                 │                               │  access          │
└─────────────────┘                               └─────────────────┘
        ▲
        │ DNS CNAME
        │
  mydb.xxx.us-east-1.rds.amazonaws.com
```

### Automatic Failover

Failover triggers:
- Primary instance failure
- AZ outage
- Instance type change
- Manual failover (for testing/maintenance)
- OS patching on primary

**Failover process (1-2 minutes):**
1. Standby promoted to primary
2. DNS record updated (same endpoint)
3. Old primary becomes new standby (when recovered)

**Key point:** Application uses the same DNS endpoint; no connection string change needed.

### Multi-AZ Deployment Options

| Feature | Single-AZ | Multi-AZ Instance | Multi-AZ Cluster |
|---------|-----------|-------------------|-------------------|
| Standby instances | 0 | 1 | 2 |
| Replication | None | Synchronous (block-level) | Synchronous (transaction log) |
| Failover time | N/A | 1-2 minutes | ~35 seconds |
| Read from standby | No | No | Yes (readers) |
| Engines | All | All | MySQL, PostgreSQL |
| Endpoints | 1 (instance) | 1 (instance) | 3 (writer, reader, instance) |

### Multi-AZ Cluster (db.r6gd instances)

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   Writer     │     │   Reader 1   │     │   Reader 2   │
│ (us-east-1a) │     │ (us-east-1b) │     │ (us-east-1c) │
└──────────────┘     └──────────────┘     └──────────────┘
       │                     │                     │
       ▼                     ▼                     ▼
  Writer Endpoint       Reader Endpoint (load-balanced)
```

- Transaction log-based replication (faster than block-level)
- Readers serve read traffic (unlike Multi-AZ Instance standby)
- Local NVMe SSD for write caching (d suffix instances)
- Faster failover: ~35 seconds vs 1-2 minutes

### Maintenance Windows

- Defined per instance (e.g., Sun 03:00-04:00 UTC)
- Multi-AZ: maintenance applied to standby first, then failover, then old primary
- Can result in brief outage during failover
- Use `apply-immediately` for urgent patches (causes immediate failover)

---

## 4. Read Replicas

### Asynchronous Replication

```
┌──────────────┐     Async        ┌──────────────┐
│   Primary    │ ──── Repl ─────► │  Replica 1   │ (same AZ)
│              │ ──── Repl ─────► │  Replica 2   │ (different AZ)
│              │ ──── Repl ─────► │  Replica 3   │ (different Region)
└──────────────┘                  └──────────────┘
  Reads+Writes                      Reads only
```

### Limits

| Engine | Max Replicas | Cross-Region | Cross-Account |
|--------|-------------|--------------|---------------|
| Aurora | 15 | Yes (Global DB) | No |
| MySQL | 5 | Yes | Yes |
| PostgreSQL | 5 | Yes | Yes |
| MariaDB | 5 | Yes | Yes |
| Oracle | 5 | Yes (limited) | No |
| SQL Server | 5 | No | No |

### Key Characteristics

- **Asynchronous:** Replica may lag behind primary (seconds to minutes)
- **Independent endpoint:** Each replica has its own DNS endpoint
- **Writable (some engines):** MySQL replicas can be writable (use carefully)
- **Cascading replicas:** A replica can have its own replicas (MySQL, PostgreSQL)
- **Network cost:** Same-region replicas = free data transfer; cross-region = charged

### Promotion to Standalone

```bash
aws rds promote-read-replica --db-instance-identifier my-replica
```

- Breaks replication link permanently
- Replica becomes independent read/write instance
- Use case: DR promotion, creating dev copy from production

### Cross-Region Replicas

- Encrypted at rest (uses KMS key in destination region)
- Used for: disaster recovery, geographic read distribution, migration
- Promotion in DR scenario: promote cross-region replica to primary

### Replica Lag Monitoring

```
CloudWatch Metrics:
- ReplicaLag (seconds) - Aurora
- ReplicaLag (seconds) - MySQL/MariaDB (Seconds_Behind_Master)
- ReplicaLag (bytes) - PostgreSQL (replay lag in bytes)
```

**Causes of high lag:** Write-heavy primary, replica instance too small, long-running queries on replica, network issues.

### Use Cases

1. **Reporting/Analytics:** Offload heavy queries from production
2. **Geographic distribution:** Replicas near users for lower latency reads
3. **Disaster recovery:** Cross-region replica as warm standby
4. **Read scaling:** Distribute read load across multiple replicas
5. **Blue-green deployments:** Create replica, promote, switch traffic

---

## 5. Amazon Aurora

### Performance Claims

- **5x throughput of MySQL** on same hardware
- **3x throughput of PostgreSQL** on same hardware
- Achieved through: storage-level replication, parallel query, read replicas share storage

### Architecture: Shared Distributed Storage

```
┌─────────────────────────────────────────────────┐
│              Aurora Cluster                       │
│                                                  │
│  ┌─────────┐   ┌─────────┐   ┌─────────┐      │
│  │ Writer  │   │Reader 1 │   │Reader 2 │  ... │
│  │Instance │   │Instance │   │Instance │      │
│  └────┬────┘   └────┬────┘   └────┬────┘      │
│       │              │              │            │
└───────┼──────────────┼──────────────┼────────────┘
        │              │              │
        ▼              ▼              ▼
┌─────────────────────────────────────────────────┐
│         Shared Cluster Storage Volume            │
│                                                  │
│  ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ │
│  │Copy1│ │Copy2│ │Copy3│ │Copy4│ │Copy5│ │Copy6│ │
│  │AZ-a │ │AZ-a │ │AZ-b │ │AZ-b │ │AZ-c │ │AZ-c │ │
│  └─────┘ └─────┘ └─────┘ └─────┘ └─────┘ └─────┘ │
│                                                  │
│  6 copies across 3 AZs                          │
│  4/6 quorum for writes, 3/6 quorum for reads    │
└─────────────────────────────────────────────────┘
```

### Storage

- **Auto-growing:** 10 GiB to 128 TiB (no pre-provisioning)
- **Auto-healing:** Data blocks continuously scanned and repaired
- **Replication:** 6 copies across 3 AZs (can tolerate loss of 2 copies for writes, 3 for reads)
- **No I/O penalty for replicas:** Replicas read from same storage
- **Striped across 100s of volumes:** 10 GiB protection groups

### Aurora Replicas

- Up to 15 read replicas (vs 5 for standard RDS)
- **Sub-10ms replica lag** (shared storage, no replication needed)
- Auto-failover with priority tiers (0-15, lower = higher priority)
- Same storage volume = no data replication overhead

### Cluster Endpoints

| Endpoint | Purpose | Example |
|----------|---------|---------|
| Writer | Reads and writes to primary | `mydb.cluster-xxx.region.rds.amazonaws.com` |
| Reader | Load-balanced reads across replicas | `mydb.cluster-ro-xxx.region.rds.amazonaws.com` |
| Custom | Subset of instances (e.g., analytics replicas) | `myendpoint.cluster-custom-xxx.region.rds.amazonaws.com` |
| Instance | Specific instance (debugging) | `mydb-instance-1.xxx.region.rds.amazonaws.com` |

### Aurora Serverless v2

```
Scaling: 0.5 ACU ──────────────────────► 128 ACU
         (1 GiB RAM)                     (256 GiB RAM)

1 ACU = ~2 GiB RAM + proportional CPU + networking
```

**Features:**
- Scales in increments of 0.5 ACU
- Instant scaling (no cold start like v1)
- Per-second billing
- Can mix with provisioned instances in same cluster
- Supports: Multi-AZ, read replicas, Global Database

**Use cases:** Variable/unpredictable workloads, development, multi-tenant, infrequent access

### Aurora Global Database

```
┌────────────────────────┐          ┌────────────────────────┐
│    Primary Region      │   <1s    │   Secondary Region 1   │
│    (us-east-1)        │ ───────► │   (eu-west-1)          │
│                        │  repl    │                        │
│  Writer + Readers     │          │  Read-only Readers      │
└────────────────────────┘          └────────────────────────┘
                                    ┌────────────────────────┐
                            ──────► │   Secondary Region 2   │
                                    │   (ap-southeast-1)     │
                                    └────────────────────────┘
```

- 1 primary region (read/write) + up to 5 secondary regions (read-only)
- **Replication lag < 1 second** (typically ~200ms)
- **RPO < 1 second** for unplanned failover
- **RTO < 1 minute** for planned failover (managed planned failover)
- Storage-level replication (no performance impact on primary)
- Up to 16 reader instances per secondary region

### Backtrack

```bash
aws rds backtrack-db-cluster \
  --db-cluster-identifier mydb \
  --backtrack-to "2024-01-15T10:30:00Z"
```

- "Rewind" the database in-place (no new instance)
- Up to 72 hours backtrack window (configurable)
- Costs: per-hour charge based on change records stored
- Use cases: undo accidental DELETE/DROP, recover from bad deployment
- **Aurora MySQL only** (not PostgreSQL)
- Must be enabled at cluster creation

### Aurora Machine Learning

Invoke ML models directly from SQL:

```sql
SELECT product_name,
       aws_sagemaker.predict_rating(product_id) as predicted_rating
FROM products
WHERE category = 'electronics';

SELECT comment_text,
       aws_comprehend.detect_sentiment(comment_text) as sentiment
FROM customer_reviews;
```

Integrates with: Amazon SageMaker, Amazon Comprehend, Amazon Bedrock

### Aurora Zero-ETL Integration with Redshift

- Automatically replicates Aurora data to Redshift
- Near real-time (seconds of latency)
- No ETL pipeline to build or maintain
- Use case: Run analytics on transactional data without impacting Aurora

---

## 6. Backup & Recovery

### Automated Backups

| Feature | Detail |
|---------|--------|
| Frequency | Daily full snapshot during backup window |
| Transaction logs | Every 5 minutes to S3 |
| Retention | 0-35 days (0 = disabled) |
| Storage | Free up to DB size; excess charged |
| Performance impact | Brief I/O suspension (Single-AZ) or none (Multi-AZ) |
| Deletion | Deleted when DB instance is deleted (unless final snapshot taken) |

### Manual Snapshots

- User-initiated, persist indefinitely (until you delete)
- Can share with other AWS accounts or make public
- Can copy to another region
- Encrypted snapshots can only be shared if using customer-managed KMS key

### Point-in-Time Recovery (PITR)

```
Backup window: Jan 1 ─────────────────────────── Jan 15 (today)
                │                                        │
                ▼                                        ▼
          Oldest restorable                    Latest restorable
          time                                 (5 min ago)
          
You can restore to ANY SECOND within this window
```

- Creates a **new** DB instance (new endpoint)
- Uses: latest snapshot + replay transaction logs to target time
- Recovery time: depends on DB size and log volume

### Cross-Region Automated Backups

- Replicate automated backups and transaction logs to another region
- Enables PITR in the destination region
- Separate retention period in destination
- Use case: DR without maintaining a read replica

### Aurora Backup

- **Continuous** backup to S3 (no performance impact)
- Point-in-time recovery to any second within retention period
- No backup window needed (always backing up)
- Retention: 1-35 days

---

## 7. Security

### Network Security (VPC)

```
┌─────────────── VPC ────────────────────────────┐
│                                                  │
│  ┌──── Public Subnet ────┐                      │
│  │  ALB / NAT Gateway    │                      │
│  └───────────┬───────────┘                      │
│              │                                   │
│  ┌──── Private Subnet (App) ────┐               │
│  │  EC2 / Lambda / ECS         │               │
│  │  SG: allow outbound to DB    │               │
│  └───────────┬──────────────────┘               │
│              │                                   │
│  ┌──── Private Subnet (DB) ─────┐               │
│  │  RDS Instance                 │               │
│  │  SG: allow 3306 from App SG  │               │
│  │  No public access            │               │
│  └───────────────────────────────┘               │
└─────────────────────────────────────────────────┘
```

**Best practices:**
- Deploy in private subnets (no public IP)
- Set `PubliclyAccessible = false`
- Security group: restrict to application tier only
- No internet access for DB (use VPC endpoints for AWS services)

### Encryption at Rest

- Uses AWS KMS (AES-256)
- **Must be enabled at creation** (cannot enable on existing unencrypted DB)
- Encrypts: storage, snapshots, backups, replicas, logs
- Read replicas must use same or different KMS key
- To encrypt existing DB: snapshot → copy with encryption → restore

```bash
# Encrypt an existing unencrypted database
aws rds create-db-snapshot --db-instance-identifier mydb --db-snapshot-identifier mydb-snap
aws rds copy-db-snapshot --source-db-snapshot-identifier mydb-snap \
  --target-db-snapshot-identifier mydb-snap-encrypted --kms-key-id alias/my-key
aws rds restore-db-instance-from-db-snapshot \
  --db-instance-identifier mydb-encrypted --db-snapshot-identifier mydb-snap-encrypted
# Update application to use new endpoint, then delete old instance
```

### Encryption in Transit

- SSL/TLS supported for all engines
- Download RDS CA certificate bundle from AWS
- Force SSL:
  - MySQL: `rds.force_ssl = 1` (parameter group)
  - PostgreSQL: `rds.force_ssl = 1` (parameter group)
  - Oracle: Native Network Encryption or SSL
  - SQL Server: `rds.force_ssl = 1`

### IAM Database Authentication

```python
import boto3

client = boto3.client('rds')
token = client.generate_db_auth_token(
    DBHostname='mydb.xxx.us-east-1.rds.amazonaws.com',
    Port=3306,
    DBUsername='iam_user',
    Region='us-east-1'
)
# Token valid for 15 minutes
# Use token as password in connection string
```

- Supported: MySQL, PostgreSQL, Aurora
- Token generated via IAM API (15-minute validity)
- No password stored in application
- Centralized access control via IAM policies
- **Limitation:** Max ~200 new connections/second (throttling)

### Secrets Manager Integration

```
┌──────────┐     ┌───────────────┐     ┌─────────┐
│   App    │────►│ Secrets       │────►│   RDS   │
│          │     │ Manager       │     │         │
└──────────┘     └───────┬───────┘     └─────────┘
                         │
                  Auto-rotation
                  (Lambda function)
                  every N days
```

- Stores credentials securely (encrypted with KMS)
- Automatic rotation: Lambda rotates password on schedule
- Rotation strategies: single-user, alternating-user
- SDKs cache credentials to avoid API calls on every connection

---

## 8. Performance & Monitoring

### Performance Insights

A dashboard for database performance analysis:

```
┌─────────────────────────────────────────────┐
│ DB Load (Average Active Sessions)           │
│                                              │
│ ████████████████████                         │  ← Wait events
│ ████████████                                 │  ← CPU
│ ████                                         │  ← I/O
│                                              │
│ Max vCPU line: ────────────────────          │
│                                              │
│ Top SQL:                                     │
│ 1. SELECT * FROM orders WHERE... (45%)       │
│ 2. UPDATE inventory SET... (20%)             │
│ 3. INSERT INTO audit_log... (15%)            │
└─────────────────────────────────────────────┘
```

**Key concepts:**
- **DB Load:** Average Active Sessions (AAS)
- **Wait events:** What queries are waiting on (I/O, lock, CPU, network)
- **Top SQL:** Queries consuming most resources
- Free tier: 7 days retention; paid: up to 2 years

### Enhanced Monitoring

OS-level metrics at 1-second granularity:

- CPU: user, system, idle, wait, steal
- Memory: free, cached, buffers, total
- Disk: read/write IOPS, latency, throughput
- Network: receive/transmit bytes
- Process list: top processes by CPU/memory
- File system: used space

Published to CloudWatch Logs (costs for log storage).

### Key CloudWatch Metrics

| Metric | Description | Alert Threshold |
|--------|-------------|-----------------|
| CPUUtilization | Percent CPU used | > 80% sustained |
| FreeableMemory | Available RAM (bytes) | < 10% of total |
| DatabaseConnections | Active connections | > 80% of max |
| ReadIOPS / WriteIOPS | I/O operations per second | Near provisioned limit |
| DiskQueueDepth | Pending I/O requests | > 10 sustained |
| ReplicaLag | Seconds behind primary | > 30s (app-dependent) |
| FreeStorageSpace | Available storage | < 20% or < 10 GiB |
| SwapUsage | Swap used (bytes) | > 0 sustained |

### Connection Pooling with RDS Proxy

See dedicated section below (Section 9).

---

## 9. RDS Proxy

### Overview

Fully managed, highly available database proxy that sits between application and RDS:

```
┌─────────┐     ┌─────────┐     ┌─────────────┐     ┌─────────┐
│ Lambda  │────►│         │     │             │     │         │
│ (100s)  │     │         │     │             │     │         │
├─────────┤     │  RDS    │────►│  Connection │────►│   RDS   │
│   ECS   │────►│  Proxy  │     │    Pool     │     │ Primary │
│ (50s)   │     │         │     │  (reused)   │     │         │
├─────────┤     │         │     │             │     │         │
│   EC2   │────►│         │     │             │     │         │
└─────────┘     └─────────┘     └─────────────┘     └─────────┘
  1000s of               Multiplexed to              100 actual
  connections            fewer connections            connections
```

### Benefits

1. **Connection multiplexing:** 1000s of app connections → few DB connections
2. **Faster failover:** Detects failure and routes to new primary (~66% faster)
3. **IAM authentication:** Enforce IAM at proxy level
4. **Secrets Manager:** Centralized credential management
5. **Connection warmup:** Maintains warm pool for instant connection acquisition

### Supported Engines

- MySQL (5.6, 5.7, 8.0)
- PostgreSQL (10-16)
- MariaDB (10.3-10.11)
- SQL Server (2012-2022)
- Aurora MySQL and Aurora PostgreSQL

### Use Cases

**Lambda functions:**
- Lambda scales to 1000s of concurrent executions
- Each execution opens a DB connection
- Without proxy: connection exhaustion
- With proxy: multiplexed to manageable number

**Microservices:**
- Many services × many instances = too many connections
- Proxy consolidates connections

**Connection management:**
- Applications that don't pool well (PHP, legacy apps)
- Reduce `max_connections` pressure on DB

### Connection Pinning

Situations where a connection gets "pinned" (can't be reused by another client):

- Session-level variables (SET commands)
- Prepared statements
- Temporary tables
- User-defined variables
- Active transactions
- LOCK TABLES

**Impact:** Pinned connections reduce multiplexing effectiveness.
**Mitigation:** Avoid session-state-changing commands, use transaction-level pinning.

### Configuration

```
Idle client connection timeout: 1800s (default)
Max connections percent: 100 (percent of max_connections on target)
Connection borrow timeout: 120s
Init query: "SET NAMES utf8mb4" (optional)
```

---

## 10. Other AWS Database Services

### DynamoDB (NoSQL)

| Feature | Detail |
|---------|--------|
| Type | Key-value and document |
| Latency | Single-digit milliseconds |
| Scaling | Serverless (on-demand) or provisioned |
| DAX | In-memory cache (microsecond reads) |
| Streams | Change data capture (ordered, 24h retention) |
| Global Tables | Multi-region, multi-active replication |
| Transactions | ACID across multiple items/tables |
| TTL | Auto-delete expired items |
| Max item size | 400 KB |

**Use cases:** Session stores, user profiles, gaming leaderboards, IoT data, shopping carts

### ElastiCache

| Feature | Redis | Memcached |
|---------|-------|-----------|
| Data structures | Strings, hashes, lists, sets, sorted sets | Simple key-value |
| Persistence | Yes (RDB, AOF) | No |
| Replication | Yes (up to 5 replicas) | No |
| Cluster mode | Yes (sharding) | Yes (sharding) |
| Multi-AZ | Yes (failover) | No |
| Pub/Sub | Yes | No |
| Lua scripting | Yes | No |
| Max item | 512 MB | 1 MB (default) |
| Use case | Complex caching, sessions, queues | Simple caching, sessions |

**Eviction policies:** volatile-lru, allkeys-lru, volatile-ttl, noeviction, etc.

### DocumentDB (MongoDB-compatible)

- Fully managed document database
- Compatible with MongoDB 3.6, 4.0, 5.0 API
- Storage: up to 128 TiB, 6 copies across 3 AZs (like Aurora)
- Up to 15 read replicas
- Use case: migrate MongoDB workloads to AWS managed service

### Neptune (Graph Database)

- Supports: Gremlin (property graph), SPARQL (RDF), openCypher
- Up to 15 read replicas, Multi-AZ
- Use cases: social networks, fraud detection, knowledge graphs, recommendation engines

### Amazon Keyspaces (Cassandra-compatible)

- Serverless, Apache Cassandra-compatible
- CQL (Cassandra Query Language)
- On-demand or provisioned capacity
- Use case: migrate Cassandra workloads, IoT time-series

### Amazon Timestream

- Purpose-built time-series database
- Automatic tiering (memory → magnetic storage)
- 1000x faster and 1/10th cost of relational for time-series
- Built-in time-series analytics functions
- Use cases: IoT telemetry, DevOps metrics, clickstream analytics

### Amazon QLDB (Quantum Ledger Database)

- Immutable, transparent, cryptographically verifiable
- Central trusted authority (not decentralized like blockchain)
- Journal: append-only, hash-chained
- Use cases: financial transactions, supply chain, regulatory compliance

### Amazon MemoryDB for Redis

- Redis-compatible, **durable** in-memory database
- Unlike ElastiCache: data is durable (survives node restarts)
- Multi-AZ transactional log for durability
- Ultra-fast (microsecond reads, single-digit ms writes)
- Use case: primary database for Redis-based applications requiring durability

### Amazon Redshift (Data Warehouse)

- Columnar storage, massively parallel processing (MPP)
- Petabyte-scale, SQL-based
- Spectrum: query S3 data directly
- Serverless mode available
- Concurrency scaling: auto-adds clusters for burst queries
- Use case: analytics, BI, data warehousing

---

## 11. Database Migration

### AWS Database Migration Service (DMS)

```
┌──────────────┐     ┌─────────────────┐     ┌──────────────┐
│    Source    │────►│  Replication    │────►│   Target     │
│   Database   │     │   Instance      │     │   Database   │
│ (on-prem/    │     │  (EC2-based,    │     │ (RDS/Aurora/ │
│  cloud/RDS)  │     │   managed)      │     │  Redshift)   │
└──────────────┘     └─────────────────┘     └──────────────┘
```

**Migration types:**

| Type | Description | Use Case |
|------|-------------|----------|
| Full load | Migrate existing data | Initial migration |
| Full load + CDC | Migrate + capture ongoing changes | Zero-downtime migration |
| CDC only | Replicate ongoing changes | Already migrated, maintain sync |

### Homogeneous vs Heterogeneous

**Homogeneous** (same engine): MySQL → Aurora MySQL
- Direct DMS migration
- No schema conversion needed

**Heterogeneous** (different engine): Oracle → PostgreSQL
- Requires SCT (Schema Conversion Tool) first
- Convert schema, stored procedures, triggers
- Then DMS for data migration

### Schema Conversion Tool (SCT)

Converts:
- Table definitions, indexes, constraints
- Stored procedures, functions, triggers
- Views, sequences
- Package bodies (Oracle)

Produces assessment report: % automatically convertible, items needing manual conversion.

### Migration Architecture (Zero-Downtime)

```
Phase 1: Full Load
  Source ──── DMS ────► Target (bulk copy)

Phase 2: CDC (Change Data Capture)
  Source ──── DMS ────► Target (real-time replication)
  App still points to Source

Phase 3: Cutover
  - Verify data consistency
  - Stop application briefly
  - Confirm CDC caught up (zero lag)
  - Point application to Target
  - Resume application
  
Total downtime: seconds to minutes
```

### Replication Instance Sizing

- Compute: Based on number of tables, transaction volume
- Storage: Enough for cached changes during full load
- Multi-AZ replication instance for production migrations
- Monitor: `CDCLatencySource`, `CDCLatencyTarget`, `FullLoadThroughputBandwidthTarget`

---

## 12. Scenario-Based Interview Questions

### Q1: Design Highly Available Database for E-Commerce (99.99% Uptime)

**Answer:**

```
Architecture:
├── Aurora PostgreSQL (Multi-AZ cluster)
│   ├── Writer instance (db.r6g.2xlarge)
│   ├── Reader 1 (us-east-1b) - application reads
│   └── Reader 2 (us-east-1c) - reporting
├── Aurora Global Database
│   └── Secondary region (us-west-2) for DR
├── RDS Proxy
│   └── Connection pooling + faster failover
├── Automated backups (35-day retention)
└── Read replicas via reader endpoint
```

**Why this achieves 99.99%:**
- Multi-AZ: survives single AZ failure (~35s failover)
- Global Database: survives region failure (RPO <1s, RTO <1min)
- RDS Proxy: reduces failover detection time
- Aurora storage: tolerates 2 copy failures for writes, 3 for reads

---

### Q2: Application Has Connection Timeout Errors - Troubleshoot

**Answer:**

1. **Check CloudWatch:** `DatabaseConnections` vs `max_connections`
2. **Likely causes:**
   - Connection exhaustion (too many open connections)
   - Application not closing connections / connection pool leak
   - Security group blocking traffic
   - DB CPU at 100% (queries not completing)
   - DNS resolution issues after failover

3. **Solutions:**
   - Implement RDS Proxy for connection pooling
   - Increase `max_connections` (parameter group)
   - Scale up instance class (more memory = higher max_connections)
   - Fix application connection pool settings (max pool size, idle timeout)
   - Check Enhanced Monitoring for OS-level bottlenecks

---

### Q3: Migrate Oracle to PostgreSQL on AWS with Minimal Downtime

**Answer:**

```
Step 1: Schema Conversion
  └── AWS SCT: Convert Oracle schema → PostgreSQL
      - Assessment report: identify manual conversions
      - Convert packages, procedures, synonyms

Step 2: Full Load + CDC
  └── AWS DMS:
      - Replication instance (dms.r5.2xlarge, Multi-AZ)
      - Source endpoint: Oracle (on-prem via DMS VPN/Direct Connect)
      - Target endpoint: Aurora PostgreSQL
      - Migration task: Full load + CDC

Step 3: Application Changes
  └── Update SQL: Oracle-specific syntax → PostgreSQL
      - DECODE → CASE, NVL → COALESCE, ROWNUM → LIMIT
      - Test thoroughly

Step 4: Cutover (minutes of downtime)
  └── Stop app → verify CDC lag=0 → switch endpoint → start app
```

---

### Q4: Read-Heavy Application with Occasional Writes

**Answer:**

```
Architecture:
├── Aurora PostgreSQL Cluster
│   ├── Writer: handles writes (1 instance)
│   └── Reader endpoint: load-balanced across 3-5 replicas
├── ElastiCache Redis
│   └── Cache frequently read data (TTL-based invalidation)
├── Application layer
│   ├── Write path → Writer endpoint
│   └── Read path → Cache first → Reader endpoint (on miss)
└── Custom endpoint for analytics-heavy queries
```

**Key points:**
- Aurora reader endpoint auto-distributes across replicas
- Cache reduces DB load by 80-90% for hot data
- Replicas share storage (no replica lag concern for most reads)
- Scale readers horizontally as read load grows

---

### Q5: Database Hitting IOPS Limits

**Answer:**

1. **Immediate:** Switch from gp2 to gp3 (provision specific IOPS up to 16,000)
2. **If >16K IOPS needed:** Switch to io1/io2 (up to 256K IOPS)
3. **Query optimization:** Fix slow queries generating excessive I/O
   - Add indexes for common WHERE clauses
   - Eliminate full table scans
4. **Caching:** Add ElastiCache to reduce read IOPS
5. **Read replicas:** Distribute reads to replicas
6. **Archive old data:** Move cold data to S3 / Glacier (reduce working set)
7. **Scale up instance:** Larger instances have higher IOPS ceilings

**Monitoring:** `ReadIOPS`, `WriteIOPS`, `DiskQueueDepth` (>1 means I/O backlog)

---

### Q6: Design Multi-Region Active-Active Database Strategy

**Answer:**

**Option A: DynamoDB Global Tables**
```
┌─── us-east-1 ───┐     ┌─── eu-west-1 ───┐
│  DynamoDB Table  │◄───►│  DynamoDB Table  │
│  (read/write)   │     │  (read/write)    │
└──────────────────┘     └──────────────────┘
- Sub-second replication
- Last writer wins (conflict resolution)
- Best for: key-value, document workloads
```

**Option B: Aurora Global Database + Application Routing**
```
- Primary region: read/write
- Secondary region: reads only (promote for writes in DR)
- NOT true active-active for writes
- Use application-level routing for write affinity
```

**Option C: CockroachDB or Spanner-like on EC2**
- True multi-region ACID writes
- Higher complexity, self-managed

**Recommendation:** DynamoDB Global Tables for active-active. Aurora Global Database for active-passive with read distribution.

---

### Q7: Lambda Functions Overwhelming RDS Connections

**Answer:**

**Problem:** Lambda scales to 1000+ concurrent executions, each opening a DB connection. RDS max_connections is typically 100-2000.

**Solution: RDS Proxy**

```
Lambda (1000 concurrent) ──► RDS Proxy ──► RDS (100 connections)
                               │
                    Connection multiplexing
                    IAM authentication
                    Secrets Manager integration
```

**Implementation:**
1. Create RDS Proxy targeting your RDS instance
2. Configure Secrets Manager for DB credentials
3. Update Lambda to connect to Proxy endpoint (not DB endpoint)
4. Place Lambda in same VPC as Proxy
5. Grant Lambda IAM role `rds-db:connect` permission

**Additional measures:**
- Set Lambda reserved concurrency to cap concurrent executions
- Use connection timeout and retry logic in Lambda code

---

### Q8: Implement Zero-Downtime Database Schema Migration

**Answer:**

**Strategy: Expand-Contract Pattern**

```
Phase 1: Expand (backward-compatible change)
  - Add new column (nullable, with default)
  - Create new table/index
  - Deploy application that writes to BOTH old and new schema

Phase 2: Migrate
  - Backfill existing rows (batch UPDATE in small chunks)
  - Verify data consistency

Phase 3: Contract (remove old)
  - Deploy application using only new schema
  - Drop old column/table (after verification period)
```

**Tools:**
- `pt-online-schema-change` (Percona, MySQL) - creates shadow table
- `pg_repack` (PostgreSQL) - repacks tables without locks
- Aurora Blue/Green Deployments - create green env with new schema, switchover

**Aurora Blue/Green Deployment:**
```
Blue (current) ──── staging replication ──── Green (new schema)
                         │
                    Apply DDL to Green
                    Verify
                    Switchover (seconds of downtime)
```

---

### Q9: Choose Between DynamoDB and RDS for a New Microservice

**Decision Framework:**

| Factor | Choose DynamoDB | Choose RDS |
|--------|----------------|------------|
| Access pattern | Known, key-based lookups | Complex queries, JOINs |
| Schema | Flexible, evolving | Structured, relational |
| Scale | Massive scale, unpredictable | Moderate, predictable |
| Transactions | Single-table or simple multi-item | Complex multi-table |
| Latency | <10ms required at any scale | <100ms acceptable |
| Cost model | Pay-per-request preferred | Fixed instance cost OK |
| Data model | Key-value, document | Relational, normalized |

**Choose DynamoDB:** Shopping cart, session store, user preferences, IoT ingestion, gaming scores

**Choose RDS/Aurora:** Order management, financial ledger, inventory with complex queries, reporting

---

### Q10: Encrypt an Existing Unencrypted RDS Instance

**Answer:**

You **cannot** enable encryption on an existing unencrypted instance directly. Process:

```
1. Create snapshot of unencrypted instance
   aws rds create-db-snapshot --db-instance-identifier mydb \
     --db-snapshot-identifier mydb-unencrypted-snap

2. Copy snapshot with encryption enabled
   aws rds copy-db-snapshot \
     --source-db-snapshot-identifier mydb-unencrypted-snap \
     --target-db-snapshot-identifier mydb-encrypted-snap \
     --kms-key-id alias/my-rds-key

3. Restore from encrypted snapshot
   aws rds restore-db-instance-from-db-snapshot \
     --db-instance-identifier mydb-new \
     --db-snapshot-identifier mydb-encrypted-snap

4. Update application connection string to new endpoint

5. Verify and delete old instance
```

**Downtime:** Duration of restore + DNS propagation. Minimize by using CNAME in Route 53.

---

### Q11: Design Database DR with RPO < 1 min and RTO < 5 min

**Answer:**

```
┌─── Primary Region (us-east-1) ──────────┐
│  Aurora PostgreSQL Cluster               │
│  ├── Writer (db.r6g.4xlarge)            │
│  ├── Reader (db.r6g.2xlarge)            │
│  └── Automated backups (35 days)         │
└──────────────────────────────────────────┘
              │
              │ Storage-level replication (<1s lag)
              ▼
┌─── DR Region (us-west-2) ───────────────┐
│  Aurora Global Database (Secondary)      │
│  ├── Reader (db.r6g.4xlarge) - headroom │
│  └── Reader (db.r6g.2xlarge)            │
└──────────────────────────────────────────┘
```

**RPO < 1 minute:** Aurora Global Database replication lag < 1 second (RPO < 1s achieved)

**RTO < 5 minutes:**
1. Automated detection via CloudWatch alarm on primary health
2. Lambda triggers managed planned failover (or detach + promote for unplanned)
3. Aurora promotes secondary to primary (~1 minute)
4. Route 53 health check failover updates DNS (~30-60 seconds)
5. Application reconnects to new primary

**Total RTO: ~2-3 minutes** (well within 5-minute target)

---

### Q12: Cost Optimization for Non-Production Databases

**Answer:**

| Strategy | Savings | Implementation |
|----------|---------|----------------|
| Stop instances off-hours | ~65% | Lambda + EventBridge: stop at 7 PM, start at 7 AM |
| Aurora Serverless v2 | 50-90% | Scale to 0.5 ACU when idle |
| Reserved Instances | ~40-60% | 1-year or 3-year RI for stable dev/staging |
| Smaller instance class | Variable | db.t4g.micro for dev (burstable, Graviton) |
| Single-AZ | 50% less | No Multi-AZ for non-prod |
| Reduce storage | Variable | gp3 with minimum IOPS, reduce allocated size |
| Snapshot + restore | ~90% | Delete instance, keep snapshot, restore when needed |
| Share read replicas | Variable | Use prod read replica for staging reads |

**Automation example (stop/start):**
```python
# EventBridge rule: cron(0 19 ? * MON-FRI *)
# Lambda function:
import boto3
rds = boto3.client('rds')
rds.stop_db_instance(DBInstanceIdentifier='dev-database')
# Auto-starts after 7 days if not manually started
```

---

### Q13: Database Connection Failing After Multi-AZ Failover

**Answer:**

**Root cause options:**
1. Application caching DNS (not respecting TTL)
2. Connection pool holding stale connections to old IP
3. Application using IP address instead of DNS endpoint

**Solutions:**
- Set DNS TTL to 5 seconds (RDS default) - ensure app/resolver honors it
- Configure connection pool to validate connections before use (`testOnBorrow`)
- Implement connection retry logic with exponential backoff
- Use RDS Proxy (handles failover transparently, 66% faster)
- Set connection pool max lifetime (e.g., 15 minutes) to cycle connections

```java
// HikariCP example
HikariConfig config = new HikariConfig();
config.setMaxLifetime(900000); // 15 min
config.setConnectionTimeout(5000); // 5s timeout
config.setValidationTimeout(3000);
config.setConnectionTestQuery("SELECT 1");
```

---

### Q14: Designing Database Strategy for Multi-Tenant SaaS

**Answer:**

| Approach | Isolation | Cost | Complexity | Use When |
|----------|-----------|------|------------|----------|
| Shared DB, shared schema | Low | Lowest | Low | Small tenants, cost-sensitive |
| Shared DB, schema per tenant | Medium | Low | Medium | Medium tenants, need some isolation |
| Database per tenant | High | Highest | High | Enterprise, compliance, large tenants |

**Recommended for most SaaS: Shared DB with Row-Level Security**

```sql
-- PostgreSQL RLS example
ALTER TABLE orders ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON orders
  USING (tenant_id = current_setting('app.tenant_id')::int);

-- Application sets tenant context per request
SET app.tenant_id = '42';
SELECT * FROM orders; -- Only sees tenant 42's orders
```

**Scaling:**
- Start shared, graduate large tenants to dedicated instances
- Use Aurora with connection-level tenant routing
- Shard by tenant_id when single instance insufficient

---

### Q15: Choosing Between Aurora Serverless v2 and Provisioned

**Answer:**

| Factor | Serverless v2 | Provisioned |
|--------|---------------|-------------|
| Workload pattern | Variable, spiky, unpredictable | Steady, predictable |
| Cost at steady load | Higher (ACU premium) | Lower |
| Cost at variable load | Lower (scale to minimum) | Higher (pay for peak) |
| Scaling speed | Instant (sub-second) | Minutes (instance modification) |
| Minimum cost | 0.5 ACU always running | Instance always running |
| Mix with provisioned | Yes (in same cluster) | N/A |

**Hybrid approach (best of both):**
```
Aurora Cluster:
├── Writer: Provisioned db.r6g.xlarge (steady baseline writes)
├── Reader 1: Provisioned db.r6g.large (steady baseline reads)
└── Reader 2: Serverless v2 (0.5-64 ACU) (handles traffic spikes)
```

**Choose Serverless v2:** Dev/test, infrequent access, new applications with unknown load, scaling buffer in mixed cluster.

**Choose Provisioned:** Well-understood steady workloads, cost optimization with Reserved Instances, maximum performance consistency.

---

## Quick Reference: Database Selection Cheat Sheet

```
Need SQL + complex queries?
├── Yes → Need >64 TiB or extreme performance?
│         ├── Yes → Aurora
│         └── No → RDS (MySQL/PostgreSQL/etc.)
└── No → What's the access pattern?
          ├── Key-value / document → DynamoDB
          ├── Graph traversals → Neptune
          ├── Time-series → Timestream
          ├── Caching (ephemeral) → ElastiCache
          ├── Caching (durable) → MemoryDB
          ├── Ledger / audit → QLDB
          ├── Wide column → Keyspaces
          ├── Search → OpenSearch
          └── Analytics / warehouse → Redshift
```

---

## Key Exam Tips

1. **Multi-AZ ≠ Read Replicas:** Multi-AZ is for HA (standby not readable), Read Replicas are for scaling reads
2. **Aurora storage:** 6 copies, 3 AZs, auto-healing, auto-growing
3. **Encryption:** Cannot encrypt existing DB in-place; must snapshot → copy encrypted → restore
4. **RDS Proxy:** Always the answer for "Lambda + RDS connection issues"
5. **Global Database:** Always the answer for "cross-region DR with <1s RPO"
6. **DMS + SCT:** Heterogeneous migration requires SCT first
7. **PITR:** Creates a NEW instance (new endpoint)
8. **Backtrack:** Aurora MySQL only, rewinds in-place (no new instance)
9. **Read Replica promotion:** Breaks replication permanently, becomes standalone
10. **Multi-AZ Cluster:** Faster failover (~35s), readers are usable (unlike Multi-AZ Instance)
