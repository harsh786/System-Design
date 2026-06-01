# Cross-Region Disaster Recovery Monitoring

## Problem Statement

Global data platforms must survive entire region failures (AWS us-east-1 outage, Azure region unavailability). Having DR infrastructure is necessary but insufficient — **you must continuously monitor that your DR actually works**.

Without DR monitoring:
- Replication silently falls behind, making RPO unmeetable
- Standby components degrade without anyone noticing
- Failover scripts break due to infrastructure drift
- You discover DR is broken only during an actual disaster
- Data inconsistency between regions goes undetected for weeks

**RPO** (Recovery Point Objective): Maximum acceptable data loss (time). "We can lose at most 5 minutes of data."
**RTO** (Recovery Time Objective): Maximum acceptable downtime. "We must be back online within 15 minutes."

Both must be **continuously verified**, not just designed-for.

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    CROSS-REGION DR ARCHITECTURE                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  PRIMARY REGION (us-east-1)              SECONDARY REGION (us-west-2)       │
│  ┌───────────────────────────┐          ┌───────────────────────────┐      │
│  │                           │          │                           │      │
│  │  ┌─────────────────────┐ │          │  ┌─────────────────────┐ │      │
│  │  │  Kafka Cluster      │ │ ──MM2──▶ │  │  Kafka Cluster      │ │      │
│  │  │  (30 brokers)       │ │          │  │  (30 brokers)       │ │      │
│  │  └─────────────────────┘ │          │  └─────────────────────┘ │      │
│  │                           │          │                           │      │
│  │  ┌─────────────────────┐ │          │  ┌─────────────────────┐ │      │
│  │  │  Flink Cluster      │ │          │  │  Flink Cluster      │ │      │
│  │  │  (Active)           │ │          │  │  (Standby/Warm)     │ │      │
│  │  └─────────────────────┘ │          │  └─────────────────────┘ │      │
│  │                           │          │                           │      │
│  │  ┌─────────────────────┐ │          │  ┌─────────────────────┐ │      │
│  │  │  S3 Data Lake       │ │ ──CRR──▶ │  │  S3 Data Lake       │ │      │
│  │  │  (Primary)          │ │          │  │  (Replica)          │ │      │
│  │  └─────────────────────┘ │          │  └─────────────────────┘ │      │
│  │                           │          │                           │      │
│  │  ┌─────────────────────┐ │          │  ┌─────────────────────┐ │      │
│  │  │  PostgreSQL (RDS)   │ │ ──rep──▶ │  │  PostgreSQL (RDS)   │ │      │
│  │  │  (Primary)          │ │          │  │  (Read Replica)     │ │      │
│  │  └─────────────────────┘ │          │  └─────────────────────┘ │      │
│  │                           │          │                           │      │
│  │  ┌─────────────────────┐ │          │  ┌─────────────────────┐ │      │
│  │  │  Airflow            │ │          │  │  Airflow            │ │      │
│  │  │  (Active scheduler) │ │          │  │  (Standby)          │ │      │
│  │  └─────────────────────┘ │          │  └─────────────────────┘ │      │
│  │                           │          │                           │      │
│  └───────────────────────────┘          └───────────────────────────┘      │
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                    DR MONITORING LAYER                                 │  │
│  │                                                                       │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌────────────┐ │  │
│  │  │ Replication │  │ Consistency │  │  Failover   │  │ Health     │ │  │
│  │  │ Lag Monitor │  │ Checker     │  │  Readiness  │  │ Probes     │ │  │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └────────────┘ │  │
│  │                                                                       │  │
│  │  ┌─────────────────────────────────────────────────────────────────┐ │  │
│  │  │              FAILOVER CONTROLLER                                 │ │  │
│  │  │  • Automated failover decision (with human approval gate)       │ │  │
│  │  │  • DNS cutover (Route 53)                                       │ │  │
│  │  │  • Consumer group offset translation                            │ │  │
│  │  │  • Split-brain prevention                                       │ │  │
│  │  └─────────────────────────────────────────────────────────────────┘ │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

```
┌─────────────────────────────────────────────────────────────────┐
│              REPLICATION FLOW DETAIL                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Source (Primary)          Replication           Target (DR)    │
│  ┌──────────────┐                              ┌────────────┐  │
│  │ Kafka Topic  │ ──MirrorMaker 2────────────▶ │ Kafka Topic│  │
│  │ events.v1    │    (async, ~2s lag)          │ events.v1  │  │
│  └──────────────┘                              └────────────┘  │
│                                                                 │
│  ┌──────────────┐                              ┌────────────┐  │
│  │ S3 bucket    │ ──Cross-Region Replication──▶│ S3 bucket  │  │
│  │ data-lake-e1 │    (async, ~15min lag)       │ data-lake-w2│ │
│  └──────────────┘                              └────────────┘  │
│                                                                 │
│  ┌──────────────┐                              ┌────────────┐  │
│  │ RDS Primary  │ ──Async Replica─────────────▶│ RDS Read   │  │
│  │              │    (~1-5s lag)                │ Replica    │  │
│  └──────────────┘                              └────────────┘  │
│                                                                 │
│  RPO Requirement: 5 minutes                                     │
│  Actual RPO (measured): max(kafka_lag, s3_lag, rds_lag)        │
│                                                                 │
│  ⚠️ If actual_rpo > 0.5 * target_rpo → ALERT                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## DR Monitoring Dimensions

### 1. Replication Lag Between Regions

| Component | Replication Method | Expected Lag | Critical Threshold |
|-----------|-------------------|-------------|-------------------|
| Kafka | MirrorMaker 2 | 1-5 seconds | > 30 seconds |
| S3 | Cross-Region Replication | 5-15 minutes | > 30 minutes |
| RDS PostgreSQL | Async replica | 1-5 seconds | > 30 seconds |
| Metadata DB | Logical replication | 1-10 seconds | > 60 seconds |

### 2. Standby System Health

Every component in the DR region must be continuously validated:

```
┌────────────────────────────────────────────────────────────────┐
│              STANDBY HEALTH CHECKLIST                            │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  Component              Check                     Status       │
│  ─────────────────────────────────────────────────────────────│
│  Kafka (DR)             Brokers online            ✓ 30/30     │
│  Kafka (DR)             Topics replicated         ✓ 2450/2450 │
│  Kafka (DR)             ISR healthy               ✓            │
│  Flink (DR)             Cluster reachable         ✓            │
│  Flink (DR)             Savepoints fresh (<1hr)   ✓            │
│  S3 (DR)                Objects replicating       ✓            │
│  S3 (DR)                Replication lag < 30min   ⚠️ 22min     │
│  RDS (DR)               Replica lag < 30s         ✓ 3s        │
│  RDS (DR)               Promotable                ✓            │
│  Airflow (DR)           Scheduler standby ready   ✓            │
│  Airflow (DR)           DAG definitions synced    ✓            │
│  DNS                    Health check passing      ✓            │
│  Network                Cross-region VPN up       ✓            │
│  IAM                    DR roles valid            ✓            │
│                                                                │
│  COMPOSITE READINESS SCORE: 0.94 / 1.00                       │
│  Status: READY (with S3 lag warning)                          │
└────────────────────────────────────────────────────────────────┘
```

### 3. Failover Readiness Score

A composite metric that answers: "Can we fail over right now?"

```
Readiness Score = weighted_average(
    kafka_replication_health * 0.3,
    data_consistency_score * 0.25,
    standby_component_health * 0.25,
    network_connectivity * 0.1,
    rpo_compliance * 0.1
)

READY:     Score >= 0.9
DEGRADED:  Score 0.7 - 0.9 (can failover with some data loss)
NOT READY: Score < 0.7 (failover will cause significant issues)
```

### 4. Split-Brain Prevention

```
┌────────────────────────────────────────────────────────────────┐
│              SPLIT-BRAIN SCENARIO                                │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  DANGER: Both regions think they are primary                   │
│                                                                │
│  Primary (us-east-1)        Secondary (us-west-2)             │
│  "I am primary"             "I am primary"                    │
│        ↓                          ↓                           │
│  Accepts writes             Accepts writes                    │
│        ↓                          ↓                           │
│  DATA DIVERGENCE → UNRECOVERABLE WITHOUT MANUAL MERGE         │
│                                                                │
│  PREVENTION:                                                   │
│  • Distributed lock (DynamoDB global table / Consul)          │
│  • Fencing tokens (epoch-based)                               │
│  • Quorum-based decision (3+ regions vote)                    │
│  • Human approval gate for failover                           │
│  • Read-only mode on contested region                         │
└────────────────────────────────────────────────────────────────┘
```

---

## RPO/RTO Monitoring

### Continuous RPO Measurement

```
Actual RPO = max(
    kafka_mirrormaker_lag_seconds,
    s3_crr_replication_lag_seconds,
    rds_replica_lag_seconds,
    metadata_replication_lag_seconds
)

RPO Target: 300 seconds (5 minutes)
Alert if: actual_rpo > 150 seconds (50% of target)
```

### Simulated RTO Measurement

RTO can only be truly measured by performing failovers. Automated DR drills:

```
DR Drill Cadence:
  • Full failover test: Monthly (off-peak hours)
  • Component-level test: Weekly
  • Health check validation: Continuous

DR Drill Steps:
  1. Verify all replication streams caught up
  2. Stop primary region producers (simulate failure)
  3. Trigger failover automation
  4. Measure time until DR region serves traffic
  5. Validate data consistency post-failover
  6. Fail back to primary
  
Measured RTO = time(step 4) - time(step 2)
```

---

## Multi-Region Kafka Monitoring

### MirrorMaker 2 Monitoring

```
┌────────────────────────────────────────────────────────────────┐
│           MIRRORMAKER 2 METRICS TO MONITOR                      │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  REPLICATION LAG                                               │
│  • kafka_connect_mirror_source_connector_replication_latency   │
│    (ms between source produce and target produce)              │
│                                                                │
│  THROUGHPUT                                                     │
│  • kafka_connect_mirror_source_connector_record_count          │
│  • kafka_connect_mirror_source_connector_byte_rate             │
│                                                                │
│  TOPIC SYNC                                                    │
│  • Source topics - Target topics = Missing topics              │
│  • Source partitions - Target partitions = Partition mismatch  │
│                                                                │
│  CONSUMER GROUP SYNC (Offset translation)                      │
│  • kafka_connect_mirror_checkpoint_connector_*                 │
│  • Translated offset accuracy                                  │
│                                                                │
│  CONNECTOR HEALTH                                              │
│  • Task state (RUNNING vs FAILED)                             │
│  • Rebalance frequency                                         │
│  • Error rate                                                  │
└────────────────────────────────────────────────────────────────┘
```

### Consumer Group Offset Synchronization

When failing over, consumers in the DR region must resume from the correct offset:

```
Source offset: 1,000,000 (us-east-1)
    ↓ MM2 offset translation
Target offset: 999,850 (us-west-2)
    ↓ 
Gap: 150 records (acceptable if < RPO worth of records)
```

---

## Production Code Examples

### 1. RPO Monitoring Script

```python
#!/usr/bin/env python3
"""
RPO Monitor - Continuously measures actual Recovery Point Objective
by comparing latest data timestamps across regions.
"""

import time
import json
from datetime import datetime, timezone
from typing import Dict, Optional
from dataclasses import dataclass
from prometheus_client import start_http_server, Gauge
import boto3
from confluent_kafka.admin import AdminClient
from confluent_kafka import Consumer, TopicPartition
import psycopg2


RPO_ACTUAL_SECONDS = Gauge(
    'dr_rpo_actual_seconds',
    'Actual RPO (max replication lag across all components)',
    ['component']
)

RPO_COMPLIANCE = Gauge(
    'dr_rpo_compliance_ratio',
    'RPO compliance ratio (0=at limit, 1=fully compliant)',
    []
)

REPLICATION_LAG_SECONDS = Gauge(
    'dr_replication_lag_seconds',
    'Replication lag per component',
    ['component', 'primary_region', 'dr_region']
)


@dataclass
class RPOConfig:
    target_rpo_seconds: int = 300  # 5 minutes
    primary_region: str = "us-east-1"
    dr_region: str = "us-west-2"
    kafka_primary_brokers: str = "kafka-east:9092"
    kafka_dr_brokers: str = "kafka-west:9092"
    primary_pg_conn: str = "host=rds-east.amazonaws.com dbname=app"
    dr_pg_conn: str = "host=rds-west.amazonaws.com dbname=app"
    s3_primary_bucket: str = "data-lake-east"
    s3_dr_bucket: str = "data-lake-west"
    canary_topic: str = "dr-canary"


class RPOMonitor:
    """Monitors actual RPO across all replicated components."""

    def __init__(self, config: RPOConfig):
        self.config = config

    def measure_kafka_lag(self) -> float:
        """Measure MirrorMaker 2 replication lag via canary records."""
        # Produce a canary record to primary
        from confluent_kafka import Producer

        canary_ts = time.time()
        producer = Producer({'bootstrap.servers': self.config.kafka_primary_brokers})
        producer.produce(
            self.config.canary_topic,
            key=b'canary',
            value=json.dumps({'ts': canary_ts, 'region': 'primary'}).encode()
        )
        producer.flush()

        # Check when it arrives in DR region
        consumer = Consumer({
            'bootstrap.servers': self.config.kafka_dr_brokers,
            'group.id': 'rpo-monitor-canary',
            'auto.offset.reset': 'latest'
        })

        # Also get MirrorMaker metrics directly
        # Check the replicated topic in DR
        dr_topic = f"{self.config.primary_region}.{self.config.canary_topic}"
        consumer.subscribe([dr_topic])

        max_wait = 30  # Wait up to 30 seconds for canary
        start = time.time()
        lag_seconds = self.config.target_rpo_seconds  # Assume worst case

        while time.time() - start < max_wait:
            msg = consumer.poll(1.0)
            if msg and not msg.error():
                value = json.loads(msg.value())
                if value.get('ts') == canary_ts:
                    lag_seconds = time.time() - canary_ts
                    break

        consumer.close()
        return lag_seconds

    def measure_rds_lag(self) -> float:
        """Measure PostgreSQL cross-region replica lag."""
        # Write canary to primary
        primary_conn = psycopg2.connect(self.config.primary_pg_conn)
        primary_cur = primary_conn.cursor()

        canary_ts = datetime.now(timezone.utc)
        primary_cur.execute("""
            INSERT INTO dr_canary (canary_time, region)
            VALUES (%s, 'primary')
            ON CONFLICT (id) DO UPDATE SET canary_time = %s
        """, (canary_ts, canary_ts))
        primary_conn.commit()
        primary_cur.close()
        primary_conn.close()

        # Read from DR replica
        time.sleep(2)  # Brief wait for replication
        dr_conn = psycopg2.connect(self.config.dr_pg_conn)
        dr_cur = dr_conn.cursor()

        dr_cur.execute("""
            SELECT canary_time FROM dr_canary ORDER BY canary_time DESC LIMIT 1
        """)
        row = dr_cur.fetchone()
        dr_cur.close()
        dr_conn.close()

        if row and row[0]:
            lag = (datetime.now(timezone.utc) - row[0]).total_seconds()
            return lag
        return self.config.target_rpo_seconds  # Assume worst case

    def measure_s3_lag(self) -> float:
        """Measure S3 Cross-Region Replication lag."""
        s3_primary = boto3.client('s3', region_name=self.config.primary_region)
        s3_dr = boto3.client('s3', region_name=self.config.dr_region)

        # Write canary object to primary
        canary_key = "dr-monitoring/canary.json"
        canary_ts = time.time()
        s3_primary.put_object(
            Bucket=self.config.s3_primary_bucket,
            Key=canary_key,
            Body=json.dumps({'ts': canary_ts}).encode()
        )

        # Check replication metrics
        metrics = s3_primary.get_bucket_replication(
            Bucket=self.config.s3_primary_bucket
        )

        # Also check if canary arrived in DR
        max_wait = 60
        start = time.time()
        while time.time() - start < max_wait:
            try:
                resp = s3_dr.get_object(
                    Bucket=self.config.s3_dr_bucket,
                    Key=canary_key
                )
                body = json.loads(resp['Body'].read())
                if body.get('ts') == canary_ts:
                    return time.time() - canary_ts
            except s3_dr.exceptions.NoSuchKey:
                pass
            time.sleep(5)

        return max_wait  # Didn't replicate within window

    def compute_actual_rpo(self) -> Dict[str, float]:
        """Compute actual RPO across all components."""
        kafka_lag = self.measure_kafka_lag()
        rds_lag = self.measure_rds_lag()
        s3_lag = self.measure_s3_lag()

        components = {
            'kafka': kafka_lag,
            'rds': rds_lag,
            's3': s3_lag,
        }

        # Update Prometheus metrics
        for component, lag in components.items():
            RPO_ACTUAL_SECONDS.labels(component=component).set(lag)
            REPLICATION_LAG_SECONDS.labels(
                component=component,
                primary_region=self.config.primary_region,
                dr_region=self.config.dr_region
            ).set(lag)

        # Actual RPO = max lag across all components
        actual_rpo = max(components.values())
        compliance = max(0, 1.0 - (actual_rpo / self.config.target_rpo_seconds))
        RPO_COMPLIANCE.set(compliance)

        return components

    def run(self):
        start_http_server(9094)
        print("RPO Monitor started on :9094")
        print(f"Target RPO: {self.config.target_rpo_seconds}s")

        while True:
            try:
                components = self.compute_actual_rpo()
                actual_rpo = max(components.values())
                print(f"Actual RPO: {actual_rpo:.1f}s | "
                      f"Kafka: {components['kafka']:.1f}s | "
                      f"RDS: {components['rds']:.1f}s | "
                      f"S3: {components['s3']:.1f}s")

                if actual_rpo > self.config.target_rpo_seconds * 0.5:
                    print(f"WARNING: RPO at {actual_rpo/self.config.target_rpo_seconds*100:.0f}% of target!")

            except Exception as e:
                print(f"Error measuring RPO: {e}")

            time.sleep(60)  # Measure every minute


if __name__ == "__main__":
    config = RPOConfig()
    monitor = RPOMonitor(config)
    monitor.run()
```

### 2. DR Readiness Health Check (Composite Score)

```python
#!/usr/bin/env python3
"""
DR Readiness Score - Composite health metric answering:
"Can we failover right now with acceptable data loss?"
"""

from dataclasses import dataclass
from typing import Dict, List, Tuple
from enum import Enum
import requests
import boto3
from prometheus_client import start_http_server, Gauge


DR_READINESS_SCORE = Gauge(
    'dr_readiness_score',
    'Composite DR readiness (0=not ready, 1=fully ready)',
    ['dr_region']
)

DR_COMPONENT_HEALTH = Gauge(
    'dr_component_health',
    'Individual component health',
    ['component', 'dr_region']
)


class ReadinessLevel(Enum):
    READY = "ready"           # Score >= 0.9
    DEGRADED = "degraded"     # Score 0.7-0.9
    NOT_READY = "not_ready"   # Score < 0.7


@dataclass
class ComponentCheck:
    name: str
    weight: float
    healthy: bool
    score: float  # 0-1
    details: str = ""


class DRReadinessChecker:
    """Comprehensive DR readiness assessment."""

    def __init__(self, config: Dict):
        self.config = config

    def check_all(self) -> Tuple[float, List[ComponentCheck]]:
        """Run all checks and compute composite score."""
        checks = [
            self.check_kafka_replication(),
            self.check_rds_replica(),
            self.check_s3_replication(),
            self.check_flink_standby(),
            self.check_airflow_standby(),
            self.check_network_connectivity(),
            self.check_dns_health(),
            self.check_iam_roles(),
        ]

        # Weighted score
        total_weight = sum(c.weight for c in checks)
        weighted_score = sum(c.score * c.weight for c in checks) / total_weight

        # Update metrics
        DR_READINESS_SCORE.labels(
            dr_region=self.config['dr_region']
        ).set(weighted_score)

        for check in checks:
            DR_COMPONENT_HEALTH.labels(
                component=check.name,
                dr_region=self.config['dr_region']
            ).set(check.score)

        return weighted_score, checks

    def check_kafka_replication(self) -> ComponentCheck:
        """Verify MirrorMaker 2 is replicating all topics."""
        try:
            # Query Kafka Connect for MM2 status
            resp = requests.get(
                f"{self.config['kafka_connect_dr_url']}/connectors/mirror-source/status"
            )
            status = resp.json()

            tasks_running = sum(
                1 for t in status['tasks'] if t['state'] == 'RUNNING'
            )
            total_tasks = len(status['tasks'])

            # Check replication lag from Prometheus
            lag_resp = requests.get(
                f"{self.config['prometheus_url']}/api/v1/query",
                params={'query': 'max(dr_replication_lag_seconds{component="kafka"})'}
            )
            lag_data = lag_resp.json()['data']['result']
            lag_seconds = float(lag_data[0]['value'][1]) if lag_data else 999

            score = (tasks_running / total_tasks) * max(0, 1 - lag_seconds / 300)

            return ComponentCheck(
                name="kafka_replication",
                weight=0.3,
                healthy=score > 0.8,
                score=min(1.0, score),
                details=f"Tasks: {tasks_running}/{total_tasks}, Lag: {lag_seconds:.1f}s"
            )
        except Exception as e:
            return ComponentCheck(
                name="kafka_replication", weight=0.3,
                healthy=False, score=0, details=f"Error: {e}"
            )

    def check_rds_replica(self) -> ComponentCheck:
        """Verify RDS read replica is healthy and caught up."""
        try:
            rds = boto3.client('rds', region_name=self.config['dr_region'])
            instances = rds.describe_db_instances(
                DBInstanceIdentifier=self.config['dr_rds_instance']
            )
            instance = instances['DBInstances'][0]

            status = instance['DBInstanceStatus']
            replica_lag = instance.get('StatusInfos', [{}])

            # Check replica lag from CloudWatch
            cw = boto3.client('cloudwatch', region_name=self.config['dr_region'])
            lag_metric = cw.get_metric_statistics(
                Namespace='AWS/RDS',
                MetricName='ReplicaLag',
                Dimensions=[{'Name': 'DBInstanceIdentifier',
                           'Value': self.config['dr_rds_instance']}],
                Period=60, Statistics=['Average'],
                StartTime=datetime.utcnow() - timedelta(minutes=5),
                EndTime=datetime.utcnow()
            )

            lag_seconds = 0
            if lag_metric['Datapoints']:
                lag_seconds = lag_metric['Datapoints'][-1]['Average']

            healthy = status == 'available' and lag_seconds < 30
            score = 1.0 if healthy else max(0, 1 - lag_seconds / 300)

            return ComponentCheck(
                name="rds_replica", weight=0.25,
                healthy=healthy, score=score,
                details=f"Status: {status}, Lag: {lag_seconds:.1f}s"
            )
        except Exception as e:
            return ComponentCheck(
                name="rds_replica", weight=0.25,
                healthy=False, score=0, details=f"Error: {e}"
            )

    def check_s3_replication(self) -> ComponentCheck:
        """Verify S3 CRR is operational."""
        try:
            s3 = boto3.client('s3', region_name=self.config['primary_region'])
            replication = s3.get_bucket_replication(
                Bucket=self.config['primary_s3_bucket']
            )

            rules = replication['ReplicationConfiguration']['Rules']
            enabled_rules = [r for r in rules if r['Status'] == 'Enabled']

            # Check replication metrics from CloudWatch
            score = len(enabled_rules) / max(len(rules), 1)

            return ComponentCheck(
                name="s3_replication", weight=0.15,
                healthy=score >= 1.0, score=score,
                details=f"Rules: {len(enabled_rules)}/{len(rules)} enabled"
            )
        except Exception as e:
            return ComponentCheck(
                name="s3_replication", weight=0.15,
                healthy=False, score=0, details=f"Error: {e}"
            )

    def check_flink_standby(self) -> ComponentCheck:
        """Verify Flink standby cluster is ready with fresh savepoints."""
        try:
            resp = requests.get(f"{self.config['flink_dr_url']}/overview")
            overview = resp.json()

            taskmanagers = overview.get('taskmanagers', 0)
            slots_available = overview.get('slots-available', 0)

            # Check savepoint freshness
            # In production: query savepoint metadata store
            healthy = taskmanagers >= self.config['min_taskmanagers']
            score = min(1.0, taskmanagers / self.config['min_taskmanagers'])

            return ComponentCheck(
                name="flink_standby", weight=0.15,
                healthy=healthy, score=score,
                details=f"TaskManagers: {taskmanagers}, Slots: {slots_available}"
            )
        except Exception as e:
            return ComponentCheck(
                name="flink_standby", weight=0.15,
                healthy=False, score=0, details=f"Error: {e}"
            )

    def check_airflow_standby(self) -> ComponentCheck:
        """Verify Airflow standby has synced DAGs."""
        try:
            resp = requests.get(
                f"{self.config['airflow_dr_url']}/api/v1/health",
                auth=('admin', self.config['airflow_password'])
            )
            health = resp.json()
            scheduler_healthy = health['scheduler']['status'] == 'healthy'

            return ComponentCheck(
                name="airflow_standby", weight=0.05,
                healthy=scheduler_healthy,
                score=1.0 if scheduler_healthy else 0,
                details=f"Scheduler: {health['scheduler']['status']}"
            )
        except Exception as e:
            return ComponentCheck(
                name="airflow_standby", weight=0.05,
                healthy=False, score=0, details=f"Error: {e}"
            )

    def check_network_connectivity(self) -> ComponentCheck:
        """Verify cross-region network (VPN/peering) is up."""
        try:
            # Ping DR region endpoint
            resp = requests.get(
                f"{self.config['dr_health_endpoint']}/ping",
                timeout=5
            )
            latency_ms = resp.elapsed.total_seconds() * 1000
            healthy = resp.status_code == 200 and latency_ms < 200

            return ComponentCheck(
                name="network", weight=0.05,
                healthy=healthy, score=1.0 if healthy else 0,
                details=f"Latency: {latency_ms:.0f}ms"
            )
        except Exception as e:
            return ComponentCheck(
                name="network", weight=0.05,
                healthy=False, score=0, details=f"Unreachable: {e}"
            )

    def check_dns_health(self) -> ComponentCheck:
        """Verify DNS failover is configured correctly."""
        try:
            route53 = boto3.client('route53')
            # Check health check status
            checks = route53.list_health_checks()
            dr_checks = [
                c for c in checks['HealthChecks']
                if 'dr-failover' in c.get('HealthCheckConfig', {}).get('FullyQualifiedDomainName', '')
            ]

            healthy_count = sum(
                1 for c in dr_checks
                if c.get('HealthCheckStatus', {}) == 'Healthy'
            )

            score = healthy_count / max(len(dr_checks), 1)
            return ComponentCheck(
                name="dns_health", weight=0.03,
                healthy=score >= 1.0, score=score,
                details=f"Health checks: {healthy_count}/{len(dr_checks)} passing"
            )
        except Exception as e:
            return ComponentCheck(
                name="dns_health", weight=0.03,
                healthy=False, score=0, details=f"Error: {e}"
            )

    def check_iam_roles(self) -> ComponentCheck:
        """Verify DR IAM roles and permissions are valid."""
        try:
            sts = boto3.client('sts', region_name=self.config['dr_region'])
            # Try to assume the DR failover role
            resp = sts.assume_role(
                RoleArn=self.config['dr_failover_role_arn'],
                RoleSessionName='dr-readiness-check',
                DurationSeconds=900
            )
            healthy = 'Credentials' in resp

            return ComponentCheck(
                name="iam_roles", weight=0.02,
                healthy=healthy, score=1.0 if healthy else 0,
                details="DR role assumable" if healthy else "Cannot assume DR role"
            )
        except Exception as e:
            return ComponentCheck(
                name="iam_roles", weight=0.02,
                healthy=False, score=0, details=f"Error: {e}"
            )
```

### 3. Automated DR Drill Framework

```python
#!/usr/bin/env python3
"""
Automated DR Drill - Periodically tests failover capability
without impacting production traffic.
"""

import time
import json
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from enum import Enum


class DrillStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    ABORTED = "aborted"


@dataclass
class DrillStep:
    name: str
    status: DrillStatus = DrillStatus.PENDING
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration_seconds: float = 0
    details: str = ""
    error: Optional[str] = None


@dataclass
class DRDrillResult:
    drill_id: str
    drill_type: str  # "full", "component", "read-only"
    start_time: datetime = None
    end_time: datetime = None
    status: DrillStatus = DrillStatus.PENDING
    measured_rto_seconds: float = 0
    measured_rpo_seconds: float = 0
    steps: List[DrillStep] = field(default_factory=list)
    data_loss_records: int = 0


class DRDrillFramework:
    """Orchestrates automated DR drills."""

    def __init__(self, config: Dict):
        self.config = config
        self.drill_history: List[DRDrillResult] = []

    def run_read_only_drill(self) -> DRDrillResult:
        """
        Read-only DR drill: Verify DR region data is queryable
        without actually failing over. Safe to run anytime.
        """
        result = DRDrillResult(
            drill_id=f"drill-{int(time.time())}",
            drill_type="read-only",
            start_time=datetime.now(timezone.utc)
        )

        steps = [
            ("verify_kafka_dr_readable", self._verify_kafka_readable),
            ("verify_s3_dr_readable", self._verify_s3_readable),
            ("verify_rds_dr_readable", self._verify_rds_readable),
            ("verify_data_freshness", self._verify_data_freshness),
            ("verify_data_consistency", self._verify_consistency_sample),
        ]

        for step_name, step_fn in steps:
            step = DrillStep(name=step_name, start_time=datetime.now(timezone.utc))
            try:
                step_fn(result)
                step.status = DrillStatus.PASSED
            except Exception as e:
                step.status = DrillStatus.FAILED
                step.error = str(e)
                result.status = DrillStatus.FAILED
            step.end_time = datetime.now(timezone.utc)
            step.duration_seconds = (step.end_time - step.start_time).total_seconds()
            result.steps.append(step)

        if result.status != DrillStatus.FAILED:
            result.status = DrillStatus.PASSED

        result.end_time = datetime.now(timezone.utc)
        self.drill_history.append(result)
        self._report_drill_result(result)
        return result

    def run_full_failover_drill(self, approval_token: str) -> DRDrillResult:
        """
        Full failover drill: Actually fail over to DR region.
        Requires human approval token. Run during maintenance window.
        """
        if not self._validate_approval(approval_token):
            raise ValueError("Invalid approval token. Full drills require human approval.")

        result = DRDrillResult(
            drill_id=f"drill-full-{int(time.time())}",
            drill_type="full",
            start_time=datetime.now(timezone.utc)
        )

        steps = [
            ("pre_check_readiness", self._pre_check),
            ("record_baseline_offsets", self._record_baseline),
            ("stop_primary_producers", self._stop_primary),
            ("wait_for_replication_drain", self._wait_drain),
            ("execute_failover", self._execute_failover),
            ("verify_dr_serving", self._verify_serving),
            ("measure_rto", self._measure_rto),
            ("verify_data_loss", self._verify_data_loss),
            ("failback_to_primary", self._failback),
            ("verify_primary_restored", self._verify_primary),
        ]

        for step_name, step_fn in steps:
            step = DrillStep(name=step_name, start_time=datetime.now(timezone.utc))
            result.steps.append(step)

            try:
                step_fn(result)
                step.status = DrillStatus.PASSED
            except Exception as e:
                step.status = DrillStatus.FAILED
                step.error = str(e)
                result.status = DrillStatus.FAILED
                # Abort remaining steps and attempt failback
                self._emergency_failback()
                break

            step.end_time = datetime.now(timezone.utc)
            step.duration_seconds = (step.end_time - step.start_time).total_seconds()

        if result.status != DrillStatus.FAILED:
            result.status = DrillStatus.PASSED

        result.end_time = datetime.now(timezone.utc)
        result.measured_rto_seconds = self._calculate_rto(result)
        self.drill_history.append(result)
        self._report_drill_result(result)
        return result

    def _verify_kafka_readable(self, result: DRDrillResult):
        """Consume latest records from DR Kafka cluster."""
        from confluent_kafka import Consumer
        consumer = Consumer({
            'bootstrap.servers': self.config['kafka_dr_brokers'],
            'group.id': f'dr-drill-{result.drill_id}',
            'auto.offset.reset': 'latest'
        })
        consumer.subscribe([self.config['canary_topic']])
        msg = consumer.poll(10.0)
        consumer.close()
        if msg is None:
            raise Exception("No messages readable from DR Kafka")

    def _verify_s3_readable(self, result: DRDrillResult):
        """Verify latest objects exist in DR S3."""
        s3 = boto3.client('s3', region_name=self.config['dr_region'])
        resp = s3.list_objects_v2(
            Bucket=self.config['dr_s3_bucket'],
            Prefix='data/',
            MaxKeys=1
        )
        if resp.get('KeyCount', 0) == 0:
            raise Exception("No objects in DR S3 bucket")

    def _verify_rds_readable(self, result: DRDrillResult):
        """Query DR RDS replica."""
        import psycopg2
        conn = psycopg2.connect(self.config['dr_pg_conn'])
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM information_schema.tables")
        count = cur.fetchone()[0]
        cur.close()
        conn.close()
        if count == 0:
            raise Exception("DR RDS has no tables")

    def _verify_data_freshness(self, result: DRDrillResult):
        """Verify DR data is fresh (within RPO)."""
        # Check latest record timestamp in DR matches within RPO
        pass

    def _verify_consistency_sample(self, result: DRDrillResult):
        """Sample-based consistency check between regions."""
        pass

    def _pre_check(self, result: DRDrillResult):
        """Verify readiness before full drill."""
        pass

    def _record_baseline(self, result: DRDrillResult):
        """Record current offsets/positions for data loss measurement."""
        pass

    def _stop_primary(self, result: DRDrillResult):
        """Stop producers in primary region (simulating failure)."""
        pass

    def _wait_drain(self, result: DRDrillResult):
        """Wait for in-flight records to replicate."""
        time.sleep(10)

    def _execute_failover(self, result: DRDrillResult):
        """Execute the actual failover (DNS, promote replica, etc.)."""
        pass

    def _verify_serving(self, result: DRDrillResult):
        """Verify DR region is serving traffic."""
        pass

    def _measure_rto(self, result: DRDrillResult):
        """Calculate actual RTO from this drill."""
        pass

    def _verify_data_loss(self, result: DRDrillResult):
        """Calculate actual data loss (records produced but not replicated)."""
        pass

    def _failback(self, result: DRDrillResult):
        """Fail back to primary region."""
        pass

    def _verify_primary(self, result: DRDrillResult):
        """Verify primary region is fully restored."""
        pass

    def _emergency_failback(self):
        """Emergency failback if drill goes wrong."""
        print("EMERGENCY: Attempting failback to primary")

    def _validate_approval(self, token: str) -> bool:
        """Validate human approval for full drill."""
        return token.startswith("APPROVED-")

    def _calculate_rto(self, result: DRDrillResult) -> float:
        """Calculate RTO from drill steps."""
        failover_step = next(
            (s for s in result.steps if s.name == "execute_failover"), None
        )
        serving_step = next(
            (s for s in result.steps if s.name == "verify_dr_serving"), None
        )
        if failover_step and serving_step and serving_step.end_time and failover_step.start_time:
            return (serving_step.end_time - failover_step.start_time).total_seconds()
        return 0

    def _report_drill_result(self, result: DRDrillResult):
        """Report drill results."""
        status_emoji = "PASS" if result.status == DrillStatus.PASSED else "FAIL"
        print(f"\nDR DRILL RESULT: {status_emoji}")
        print(f"  Type: {result.drill_type}")
        print(f"  Duration: {(result.end_time - result.start_time).total_seconds():.1f}s")
        if result.measured_rto_seconds:
            print(f"  Measured RTO: {result.measured_rto_seconds:.1f}s")
        print(f"  Steps:")
        for step in result.steps:
            s = "PASS" if step.status == DrillStatus.PASSED else "FAIL"
            print(f"    [{s}] {step.name} ({step.duration_seconds:.1f}s)")
            if step.error:
                print(f"         Error: {step.error}")
```

### 4. Split-Brain Detector

```python
#!/usr/bin/env python3
"""
Split-Brain Detector - Prevents both regions from accepting writes
simultaneously during network partitions.
"""

import time
import json
import hashlib
from typing import Optional
import boto3
from datetime import datetime, timezone


class SplitBrainDetector:
    """
    Uses a DynamoDB global table as a distributed lock to prevent split-brain.
    Only one region can hold the 'primary' lock at a time.
    """

    def __init__(self, table_name: str, region: str, ttl_seconds: int = 30):
        self.table_name = table_name
        self.region = region
        self.ttl_seconds = ttl_seconds
        self.dynamodb = boto3.resource('dynamodb', region_name=region)
        self.table = self.dynamodb.Table(table_name)
        self.node_id = f"{region}-{hashlib.md5(region.encode()).hexdigest()[:8]}"

    def try_acquire_primary(self) -> bool:
        """
        Attempt to acquire or renew primary lock.
        Returns True if this region is the valid primary.
        """
        now = int(time.time())
        expiry = now + self.ttl_seconds

        try:
            self.table.put_item(
                Item={
                    'lock_key': 'primary_region',
                    'holder': self.node_id,
                    'region': self.region,
                    'acquired_at': now,
                    'expires_at': expiry,
                    'ttl': expiry
                },
                ConditionExpression=(
                    'attribute_not_exists(lock_key) OR '
                    'holder = :me OR '
                    'expires_at < :now'
                ),
                ExpressionAttributeValues={
                    ':me': self.node_id,
                    ':now': now
                }
            )
            return True
        except self.dynamodb.meta.client.exceptions.ConditionalCheckFailedException:
            return False

    def check_for_split_brain(self) -> Optional[dict]:
        """
        Check if multiple regions believe they are primary.
        Returns details if split-brain detected.
        """
        try:
            resp = self.table.get_item(Key={'lock_key': 'primary_region'})
            item = resp.get('Item')

            if not item:
                return {'status': 'no_primary', 'details': 'No region holds primary lock'}

            lock_holder = item['region']
            lock_expiry = item['expires_at']
            now = int(time.time())

            if lock_expiry < now:
                return {
                    'status': 'expired_lock',
                    'details': f'Primary lock expired {now - lock_expiry}s ago',
                    'last_holder': lock_holder
                }

            if lock_holder != self.region:
                # Another region is primary — we should be standby
                return None  # No split-brain

            return None  # We are correctly primary

        except Exception as e:
            # Cannot reach DynamoDB — potential network partition
            return {
                'status': 'network_partition_suspected',
                'details': f'Cannot verify lock: {e}',
                'action': 'ENTER READ-ONLY MODE'
            }

    def enter_read_only_mode(self):
        """
        Safety measure: If we can't verify we're primary,
        stop accepting writes to prevent data divergence.
        """
        print(f"CRITICAL: Entering read-only mode in {self.region}")
        # In production:
        # 1. Set feature flag to reject writes
        # 2. Pause Kafka consumers (stop processing)
        # 3. Alert on-call immediately
        # 4. Wait for human decision

    def monitor_loop(self):
        """Continuously monitor for split-brain conditions."""
        consecutive_failures = 0

        while True:
            # Try to maintain primary lock (if we're primary)
            is_primary = self.try_acquire_primary()

            if is_primary:
                consecutive_failures = 0
            else:
                # Check for split-brain
                issue = self.check_for_split_brain()
                if issue:
                    if issue['status'] == 'network_partition_suspected':
                        consecutive_failures += 1
                        if consecutive_failures >= 3:
                            self.enter_read_only_mode()
                    print(f"SPLIT-BRAIN CHECK: {json.dumps(issue)}")

            time.sleep(10)  # Check every 10 seconds
```

---

## Alert Rules

```yaml
groups:
  - name: dr_monitoring
    rules:
      # RPO at risk
      - alert: DRReplicationLagExceedsHalfRPO
        expr: |
          max(dr_replication_lag_seconds) > 150
        for: 2m
        labels:
          severity: critical
          team: platform
        annotations:
          summary: "DR replication lag {{ $value }}s exceeds 50% of RPO (300s)"
          description: "Component {{ $labels.component }} in {{ $labels.dr_region }}"
          runbook: "https://wiki/runbooks/dr-lag-critical"

      # Standby unhealthy
      - alert: DRComponentUnhealthy
        expr: |
          dr_component_health < 0.5
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "DR component {{ $labels.component }} unhealthy (score: {{ $value }})"

      # Overall readiness degraded
      - alert: DRReadinessDegraded
        expr: |
          dr_readiness_score < 0.7
        for: 10m
        labels:
          severity: critical
        annotations:
          summary: "DR readiness score {{ $value }} - FAILOVER NOT SAFE"
          action: "Investigate degraded components immediately"

      # Network partition
      - alert: CrossRegionNetworkPartition
        expr: |
          probe_success{job="cross-region-probe"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Cross-region connectivity lost"
          action: "Check VPN/peering. Risk of split-brain."

      # DR drill failure
      - alert: DRDrillFailed
        expr: |
          dr_drill_status{status="failed"} > 0
        labels:
          severity: critical
        annotations:
          summary: "DR drill failed: {{ $labels.drill_type }}"
          description: "DR may not work in actual disaster"

      # MirrorMaker 2 lag
      - alert: MirrorMaker2LagHigh
        expr: |
          kafka_connect_mirror_source_connector_replication_latency_ms_avg > 30000
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "MirrorMaker 2 replication lag > 30s"

      # S3 CRR replication pending
      - alert: S3ReplicationBacklog
        expr: |
          aws_s3_replication_pending_operations > 10000
        for: 15m
        labels:
          severity: warning
        annotations:
          summary: "S3 CRR has {{ $value }} pending operations"
```

---

## DR Runbook

```
┌─────────────────────────────────────────────────────────────────┐
│              FAILOVER DECISION MATRIX                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Is primary region completely down?                             │
│  ├── YES → Check DR readiness score                            │
│  │         ├── Score >= 0.9 → PROCEED with failover            │
│  │         ├── Score 0.7-0.9 → Failover with KNOWN DATA LOSS  │
│  │         └── Score < 0.7 → DO NOT failover (worse outcome)  │
│  │                                                             │
│  └── NO (partial outage) →                                     │
│       ├── Can we mitigate without failover?                    │
│       │   ├── YES → Mitigate (restart, scale, reroute)        │
│       │   └── NO → Evaluate partial failover                  │
│       └── How long until recovery?                             │
│           ├── < RTO → Wait for primary recovery               │
│           └── > RTO → Initiate failover                       │
│                                                                 │
│  FAILOVER STEPS:                                                │
│  1. Get human approval (unless automated for P0)               │
│  2. Verify DR readiness score                                  │
│  3. Record current offsets (for data loss accounting)          │
│  4. Promote DR databases (RDS promote read replica)            │
│  5. Start DR Flink jobs (from latest savepoint)                │
│  6. Update DNS (Route 53 failover)                             │
│  7. Verify DR serving traffic                                  │
│  8. Notify stakeholders                                        │
│                                                                 │
│  POST-FAILOVER:                                                 │
│  1. Assess data loss (compare offsets)                         │
│  2. Plan failback when primary recovers                        │
│  3. Reconcile any data gaps                                    │
│  4. Write incident report                                      │
└─────────────────────────────────────────────────────────────────┘
```

---

## Technologies Summary

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Kafka replication | MirrorMaker 2 / Confluent Replicator | Cross-region topic replication |
| Object storage | S3 Cross-Region Replication | Data lake DR |
| Database | RDS Read Replicas (cross-region) | Metadata DB DR |
| DNS failover | Route 53 health checks + failover | Traffic routing |
| Distributed lock | DynamoDB Global Tables | Split-brain prevention |
| Service discovery | Consul (multi-DC) | Component registration |
| Infrastructure | Terraform (multi-region) | DR infrastructure as code |
| Monitoring | Prometheus + Thanos (multi-region) | Unified observability |
| DR drills | Custom framework | Continuous verification |

---

## Key Takeaways

1. **Monitor your DR continuously** — Untested DR is not DR
2. **Measure actual RPO, don't assume it** — Replication lag drifts silently
3. **Automate DR drills** — Monthly full drills, weekly component drills
4. **Split-brain prevention is critical** — Use distributed locks with fencing
5. **Composite readiness score** gives instant go/no-go for failover decisions
6. **RTO includes human decision time** — Automate what you can, gate what you must
7. **Failback is harder than failover** — Plan and test it too
8. **DR monitoring must itself be multi-region** — Don't monitor DR from only the primary
