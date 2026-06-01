# Data Replication for Disaster Recovery

## Problem Statement

At billion-scale, a single region failure can cause catastrophic data loss and extended outages costing millions per hour. Organizations need cross-region data replication with defined RPO (Recovery Point Objective) and RTO (Recovery Time Objective) targets. The challenge: replicating petabytes of data across regions with minimal lag, automating failover without data loss, and handling the complexity of multiple data stores (databases, object storage, streaming platforms, warehouses) that must all fail over consistently.

## Architecture Diagram

```mermaid
graph TB
    subgraph "Primary Region (us-east-1)"
        subgraph "Data Stores - Primary"
            RDS_P[(RDS PostgreSQL<br/>Primary)]
            S3_P[S3 Bucket<br/>Data Lake Primary]
            KAFKA_P[Kafka Cluster<br/>Primary]
            REDIS_P[Redis Cluster<br/>Primary]
            RS_P[(Redshift<br/>Primary)]
        end
        
        subgraph "Replication Agents"
            DMS_P[AWS DMS<br/>DB Replication]
            S3REP[S3 Cross-Region<br/>Replication]
            MM2[Kafka MirrorMaker 2]
            REDIS_REP[Redis Global<br/>Datastore]
        end
        
        subgraph "Orchestration"
            HEALTH[Health Monitor]
            FAILOVER[Failover Automator]
            DNS[Route53<br/>Health Checks]
        end
    end

    subgraph "DR Region (us-west-2)"
        subgraph "Data Stores - Standby"
            RDS_S[(RDS PostgreSQL<br/>Read Replica)]
            S3_S[S3 Bucket<br/>Data Lake Standby]
            KAFKA_S[Kafka Cluster<br/>Standby]
            REDIS_S[Redis Cluster<br/>Standby]
            RS_S[(Redshift<br/>Snapshot Restore)]
        end
        
        subgraph "DR Services (Warm)"
            APP_DR[Application<br/>Servers (scaled down)]
            FLINK_DR[Flink Jobs<br/>(paused)]
        end
    end

    subgraph "Global"
        R53[Route53<br/>DNS Failover]
        CF[CloudFront<br/>Global CDN]
        GLOBAL_DB[Aurora Global<br/>Database]
    end

    RDS_P --> DMS_P --> RDS_S
    S3_P --> S3REP --> S3_S
    KAFKA_P --> MM2 --> KAFKA_S
    REDIS_P --> REDIS_REP --> REDIS_S
    RS_P -.->|Snapshots every 4hr| RS_S

    HEALTH --> DNS
    HEALTH --> FAILOVER
    FAILOVER --> RDS_S
    FAILOVER --> APP_DR
    FAILOVER --> FLINK_DR

    R53 --> CF
    GLOBAL_DB --> RDS_P
    GLOBAL_DB --> RDS_S
```

## Component Breakdown

### RPO/RTO Targets by Tier

| Tier | Data Store | RPO Target | RTO Target | Replication Method |
|------|-----------|------------|------------|-------------------|
| Tier 1 (Critical) | PostgreSQL (orders, payments) | < 1 second | < 60 seconds | Aurora Global / Synchronous |
| Tier 1 | Redis (sessions, carts) | < 5 seconds | < 30 seconds | Global Datastore |
| Tier 2 (Important) | Kafka (events) | < 30 seconds | < 5 minutes | MirrorMaker 2 |
| Tier 2 | S3 (data lake) | < 15 minutes | < 15 minutes | Cross-Region Replication |
| Tier 3 (Analytics) | Redshift | < 4 hours | < 1 hour | Cross-region snapshots |
| Tier 3 | Elasticsearch | Rebuild | < 30 minutes | Reindex from source |

### Aurora Global Database Configuration

```yaml
# CloudFormation
AuroraGlobalCluster:
  Type: AWS::RDS::GlobalCluster
  Properties:
    GlobalClusterIdentifier: prod-global-orders
    Engine: aurora-postgresql
    EngineVersion: '15.4'
    StorageEncrypted: true

PrimaryCluster:
  Type: AWS::RDS::DBCluster
  Properties:
    GlobalClusterIdentifier: !Ref AuroraGlobalCluster
    Engine: aurora-postgresql
    DBClusterInstanceClass: db.r6g.4xlarge
    AvailabilityZones: [us-east-1a, us-east-1b, us-east-1c]
    BackupRetentionPeriod: 35
    
SecondaryCluster:
  Type: AWS::RDS::DBCluster
  Properties:
    GlobalClusterIdentifier: !Ref AuroraGlobalCluster
    Engine: aurora-postgresql
    Region: us-west-2
    DBClusterInstanceClass: db.r6g.4xlarge
    # RPO: typically < 1 second
    # RTO: < 1 minute with managed failover
```

### Kafka MirrorMaker 2 Configuration

```properties
# mm2.properties
clusters = primary, dr
primary.bootstrap.servers = kafka-primary-1:9092,kafka-primary-2:9092
dr.bootstrap.servers = kafka-dr-1:9092,kafka-dr-2:9092

# Primary -> DR replication
primary->dr.enabled = true
primary->dr.topics = orders\..*, payments\..*, inventory\..*
primary->dr.topics.exclude = .*\.internal, __.*

# Replication settings
replication.factor = 3
sync.topic.configs.enabled = true
sync.topic.acls.enabled = true
refresh.topics.interval.seconds = 30
refresh.groups.interval.seconds = 30

# Offset sync for consumer failover
emit.checkpoints.enabled = true
emit.checkpoints.interval.seconds = 10
sync.group.offsets.enabled = true
sync.group.offsets.interval.seconds = 10

# Performance
tasks.max = 8
producer.batch.size = 131072
producer.linger.ms = 10
producer.compression.type = lz4
consumer.max.poll.records = 1000
offset.lag.max = 100
```

### S3 Cross-Region Replication

```json
{
  "ReplicationConfiguration": {
    "Role": "arn:aws:iam::123456789:role/s3-replication-role",
    "Rules": [
      {
        "ID": "ReplicateDataLake",
        "Status": "Enabled",
        "Priority": 1,
        "Filter": {
          "Prefix": "data-lake/"
        },
        "Destination": {
          "Bucket": "arn:aws:s3:::data-lake-dr-us-west-2",
          "StorageClass": "STANDARD_IA",
          "ReplicationTime": {
            "Status": "Enabled",
            "Time": {"Minutes": 15}
          },
          "Metrics": {
            "Status": "Enabled",
            "EventThreshold": {"Minutes": 15}
          }
        },
        "DeleteMarkerReplication": {"Status": "Enabled"},
        "SourceSelectionCriteria": {
          "SseKmsEncryptedObjects": {"Status": "Enabled"}
        }
      }
    ]
  }
}
```

### Automated Failover Orchestrator

```python
import boto3
import time

class DisasterRecoveryOrchestrator:
    """
    Automated failover orchestration across all data stores.
    Executes failover runbook in correct order with verification.
    """
    
    def __init__(self, config):
        self.config = config
        self.rds = boto3.client('rds', region_name='us-west-2')
        self.route53 = boto3.client('route53')
        self.ecs = boto3.client('ecs', region_name='us-west-2')
    
    async def execute_failover(self, trigger: str):
        """
        Failover sequence:
        1. Verify primary is truly down (avoid false positive)
        2. Promote database replicas
        3. Activate Kafka consumers in DR
        4. Scale up application fleet
        5. Switch DNS
        6. Verify traffic flowing
        """
        
        # Step 1: Confirm outage (prevent split-brain)
        if not await self._confirm_primary_down(checks=3, interval=10):
            log.info("Primary recovered, aborting failover")
            return
        
        log.critical(f"FAILOVER INITIATED. Trigger: {trigger}")
        
        # Step 2: Promote Aurora Global Database
        await self._promote_aurora_secondary()
        
        # Step 3: Promote Redis Global Datastore
        await self._promote_redis_secondary()
        
        # Step 4: Start Kafka consumers in DR region
        await self._activate_kafka_consumers()
        
        # Step 5: Scale up application servers
        await self._scale_up_applications()
        
        # Step 6: Switch DNS (Route53)
        await self._switch_dns()
        
        # Step 7: Verify
        await self._verify_dr_healthy()
        
        log.critical("FAILOVER COMPLETE. DR region now serving traffic.")
    
    async def _promote_aurora_secondary(self):
        """Promote Aurora secondary to standalone primary"""
        response = self.rds.failover_global_cluster(
            GlobalClusterIdentifier='prod-global-orders',
            TargetDbClusterIdentifier='arn:aws:rds:us-west-2:123456789:cluster:orders-dr'
        )
        
        # Wait for promotion (typically < 60 seconds)
        waiter = self.rds.get_waiter('db_cluster_available')
        waiter.wait(DBClusterIdentifier='orders-dr', WaiterConfig={'Delay': 5, 'MaxAttempts': 30})
    
    async def _switch_dns(self):
        """Atomic DNS switch to DR region"""
        self.route53.change_resource_record_sets(
            HostedZoneId=self.config['hosted_zone_id'],
            ChangeBatch={
                'Changes': [{
                    'Action': 'UPSERT',
                    'ResourceRecordSet': {
                        'Name': 'api.mycompany.com',
                        'Type': 'A',
                        'AliasTarget': {
                            'HostedZoneId': self.config['dr_alb_zone_id'],
                            'DNSName': self.config['dr_alb_dns'],
                            'EvaluateTargetHealth': True
                        }
                    }
                }]
            }
        )
    
    async def _confirm_primary_down(self, checks: int, interval: int) -> bool:
        """Multiple checks to avoid false positive failover"""
        failures = 0
        for _ in range(checks):
            try:
                # Check multiple endpoints
                health_checks = [
                    self._check_rds_primary(),
                    self._check_app_health(),
                    self._check_region_connectivity()
                ]
                results = await asyncio.gather(*health_checks, return_exceptions=True)
                if all(isinstance(r, Exception) for r in results):
                    failures += 1
            except Exception:
                failures += 1
            await asyncio.sleep(interval)
        
        return failures >= checks
```

### Redshift DR Strategy

```python
class RedshiftDR:
    def setup_cross_region_snapshots(self):
        """Configure automated cross-region snapshot copy"""
        self.redshift.enable_snapshot_copy(
            ClusterIdentifier='analytics-prod',
            DestinationRegion='us-west-2',
            RetentionPeriod=7,
            SnapshotCopyGrantName='dr-snapshot-grant'
        )
    
    def restore_in_dr(self, snapshot_id: str):
        """Restore Redshift from latest cross-region snapshot"""
        self.redshift_dr.restore_from_cluster_snapshot(
            ClusterIdentifier='analytics-dr',
            SnapshotIdentifier=snapshot_id,
            NodeType='ra3.4xlarge',
            NumberOfNodes=4,
            AvailabilityZone='us-west-2a'
        )
        # RTO: ~30-45 minutes for restore
        # Then replay CDC events from Kafka to fill gap
```

## Data Flow

```
Normal Operation:
- All writes go to primary region
- Asynchronous replication to DR region continuously
- DR region serves read-only queries (reporting, analytics)
- Health monitors check primary every 5 seconds

During Failover:
1. Primary detected as down (3 consecutive failures)
2. Failover automation triggered
3. Aurora promoted (RPO < 1s, RTO < 60s)
4. Redis promoted (RPO < 5s, RTO < 30s)
5. Kafka consumers started in DR (resume from replicated offsets)
6. App fleet scaled from 2 → 20 instances (60s)
7. DNS switched (TTL 60s, propagation ~2-3 min)
8. Traffic starts flowing to DR region

Post-Failover:
- Monitor DR region stability
- Plan failback when primary region recovers
- Replicate DR writes back to original primary
- Perform controlled failback during low-traffic window
```

## Scaling Strategies

| Component | Primary | DR (Standby) | DR (Active) |
|-----------|---------|--------------|-------------|
| Aurora | r6g.4xlarge × 3 | r6g.2xlarge × 2 | Promote + scale |
| Kafka | 6 brokers | 3 brokers | Scale to 6 |
| App servers | 20 instances | 2 instances | Scale to 20 |
| Redis | 6 shards | 6 shards (auto) | Already sized |
| Flink | 8 task managers | 0 (paused) | Start 8 |

## Failure Handling

| Scenario | RPO Achieved | RTO Achieved | Notes |
|----------|-------------|-------------|-------|
| Single AZ failure | 0 (Multi-AZ) | < 30s | Automatic, no DR activation |
| Full region failure | < 1s (Aurora) | < 5 min | Automated failover |
| Network partition | < 30s (Kafka lag) | < 5 min | DNS-based routing |
| Cascading failure | Varies | < 15 min | Manual decision may be needed |
| Data corruption | Point-in-time recovery | < 1 hour | Restore from backup |

### Failover Testing (Game Days)
```yaml
quarterly_dr_test:
  - name: "Full Region Failover Drill"
    steps:
      - simulate_primary_failure: true
      - verify_auto_detection: timeout_30s
      - verify_aurora_promotion: timeout_90s
      - verify_app_scaling: timeout_120s
      - verify_dns_switch: timeout_180s
      - run_integration_tests: timeout_300s
      - verify_data_consistency: compare_primary_dr
      - failback_to_primary: controlled
    success_criteria:
      total_rto: < 5 minutes
      data_loss: 0 transactions
      error_rate_during: < 1%
```

## Cost Optimization

| Component | Primary Cost | DR Cost (warm) | Notes |
|-----------|-------------|----------------|-------|
| Aurora Global | $8,000/mo | $3,000/mo | Smaller DR instances |
| S3 Replication | - | $500/mo | Storage + transfer |
| Kafka (DR) | - | $2,400/mo | 3 brokers minimum |
| Redis Global | $3,600/mo | $0 (included) | Global Datastore |
| App servers (DR) | - | $200/mo | 2 minimum instances |
| Redshift snapshots | - | $400/mo | Storage only |
| **Total DR cost** | | **~$6,500/month** | ~30% of primary cost |

### Cost vs RPO/RTO Tradeoffs
```
Hot Standby (RPO <1s, RTO <1min): ~60% of primary cost
Warm Standby (RPO <30s, RTO <5min): ~30% of primary cost
Cold Standby (RPO <4hr, RTO <1hr): ~10% of primary cost
Pilot Light (RPO varies, RTO <4hr): ~5% of primary cost
```

## Real-World Companies

| Company | Strategy | Scale |
|---------|----------|-------|
| **Netflix** | Active-active multi-region | No single point of failure |
| **AWS** | Multi-region, cell-based | Region isolation |
| **Stripe** | Active-passive with < 5s RPO | Financial data critical |
| **Slack** | Multi-region with regional routing | Message availability |
| **GitHub** | Active-passive with MySQL replication | Code repository DR |
| **Capital One** | Multi-region active-active | Banking compliance |
| **Uber** | Active-active across regions | Ride availability |
