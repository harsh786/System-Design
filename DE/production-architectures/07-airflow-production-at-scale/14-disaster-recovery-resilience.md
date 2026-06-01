# Disaster Recovery & Resilience - Airflow at Billions Scale

## Why DR Matters for Airflow

Airflow is the **BRAIN** of data operations. Unlike a microservice that handles one domain, Airflow orchestrates everything:

- **If Airflow goes down, ALL pipelines stop** - ingestion, transformation, ML training, reporting
- At billions scale: 1 hour of downtime = millions of unprocessed transactions
- Regulatory pipelines (SOX, GDPR, AML) can't miss deadlines regardless of infrastructure failures
- Data SLAs cascade: late raw data → late transforms → late dashboards → late business decisions

### What You Must Handle

```
┌─────────────────────────────────────────────────────────┐
│              Failure Scenarios to Plan For               │
├─────────────────────────────────────────────────────────┤
│  1. Single component failure (scheduler, worker, DB)    │
│  2. Complete region failure (AWS us-east-1 goes down)   │
│  3. Database corruption (bad migration, disk failure)   │
│  4. Deployment gone wrong (broken DAGs, bad config)     │
│  5. Network partition (components can't communicate)    │
│  6. Dependency failure (S3, external APIs, Kafka)       │
│  7. Security incident (compromised credentials)         │
│  8. Human error (deleted DAGs, wrong variable change)   │
└─────────────────────────────────────────────────────────┘
```

### Cost of Downtime Calculator

```
Hourly cost = (revenue_per_hour × pipeline_dependency_factor) + SLA_penalty + recovery_labor

Example at scale:
- Revenue pipelines: $50K/hour in delayed billing
- SLA penalties: $10K per missed window
- Engineering time: 5 engineers × $150/hr = $750/hr
- Reputation cost: immeasurable

Total: ~$60K+ per hour of complete Airflow outage
```

---

## Failure Modes & Mitigation

### 1. Scheduler Failure

| Aspect | Detail |
|--------|--------|
| **Symptoms** | Tasks stuck in "scheduled" state, no new DAG runs created |
| **Detection** | `scheduler_heartbeat` metric missing for > 30s |
| **Root Causes** | OOM kill, deadlock on DB, crashed process, node failure |
| **Mitigation** | HA schedulers (2-3 active instances) |
| **Recovery** | Automatic - other schedulers take over |
| **RTO** | < 30 seconds with HA |

```yaml
# HA Scheduler Configuration (Helm)
scheduler:
  replicas: 3
  resources:
    requests:
      memory: "4Gi"
      cpu: "2"
    limits:
      memory: "6Gi"
      cpu: "4"
  livenessProbe:
    initialDelaySeconds: 10
    periodSeconds: 10
    failureThreshold: 3
    exec:
      command:
        - sh
        - -c
        - "airflow jobs check --job-type SchedulerJob --hostname $(hostname)"
  podDisruptionBudget:
    minAvailable: 2
  topologySpreadConstraints:
    - maxSkew: 1
      topologyKey: topology.kubernetes.io/zone
      whenUnsatisfiable: DoNotSchedule
```

```python
# airflow.cfg - Scheduler HA settings
[scheduler]
num_runs = -1                    # Run forever
scheduler_heartbeat_sec = 5      # Frequent heartbeats
orphaned_tasks_check_interval = 60
max_threads = 4
```

### 2. Worker Failure

| Aspect | Detail |
|--------|--------|
| **Symptoms** | Tasks stuck in "running" state, no heartbeat from worker |
| **Detection** | Zombie task detection (scheduler monitors task heartbeats) |
| **Root Causes** | OOM kill, spot instance termination, node crash |
| **Mitigation** | Task retries, worker auto-scaling, graceful termination |
| **Recovery** | Zombie tasks detected and re-queued automatically |
| **RTO** | `retry_delay` (typically 1-5 minutes) |

```yaml
# Worker resilience configuration
workers:
  replicas: 10
  autoscaling:
    enabled: true
    minReplicas: 5
    maxReplicas: 50
  terminationGracePeriodSeconds: 600  # 10min for graceful shutdown
  strategy:
    rollingUpdate:
      maxSurge: 5
      maxUnavailable: 2
  # Handle spot interruptions
  lifecycle:
    preStop:
      exec:
        command:
          - "sh"
          - "-c"
          - "celery -A airflow.executors.celery_executor.app inspect active -j | python /opt/drain_worker.py"
```

```python
# Task-level resilience
default_args = {
    'retries': 3,
    'retry_delay': timedelta(minutes=2),
    'retry_exponential_backoff': True,
    'max_retry_delay': timedelta(minutes=30),
    'execution_timeout': timedelta(hours=2),
}

# Zombie detection tuning
[scheduler]
scheduler_zombie_task_threshold = 300  # 5 minutes
zombie_detection_interval = 30
```

### 3. Metadata Database Failure

| Aspect | Detail |
|--------|--------|
| **Symptoms** | EVERYTHING stops - scheduler, webserver, workers all need DB |
| **Detection** | Connection refused errors, health check failures across all components |
| **Root Causes** | Storage failure, network issue, overloaded connections, corruption |
| **Mitigation** | Multi-AZ RDS with automated failover |
| **Recovery** | RDS failover (30-60s), PgBouncer reconnects |
| **RTO** | 60-120 seconds with Multi-AZ |

```hcl
# Terraform - Highly Available RDS for Airflow
resource "aws_db_instance" "airflow_metadata" {
  identifier     = "airflow-metadata-prod"
  engine         = "postgres"
  engine_version = "15.4"
  instance_class = "db.r6g.2xlarge"

  # HA Configuration
  multi_az               = true
  storage_type           = "gp3"
  allocated_storage      = 500
  max_allocated_storage  = 2000
  storage_encrypted      = true

  # Backup Configuration
  backup_retention_period   = 30
  backup_window            = "03:00-04:00"
  maintenance_window       = "Mon:04:00-Mon:05:00"
  copy_tags_to_snapshot    = true
  delete_automated_backups = false

  # Performance
  performance_insights_enabled = true
  monitoring_interval         = 10

  # Network
  db_subnet_group_name   = aws_db_subnet_group.airflow.name
  vpc_security_group_ids = [aws_security_group.airflow_db.id]

  # Protection
  deletion_protection = true
  skip_final_snapshot = false
  final_snapshot_identifier = "airflow-metadata-final-${formatdate("YYYY-MM-DD", timestamp())}"
}

# Cross-region read replica for DR
resource "aws_db_instance" "airflow_metadata_dr" {
  provider = aws.dr_region

  identifier          = "airflow-metadata-dr"
  replicate_source_db = aws_db_instance.airflow_metadata.arn
  instance_class      = "db.r6g.xlarge"  # Smaller until promoted
  multi_az            = true

  backup_retention_period = 7
}
```

```yaml
# PgBouncer for connection resilience
pgbouncer:
  enabled: true
  replicas: 3
  maxClientConn: 500
  defaultPoolSize: 40
  reservePoolSize: 10
  reservePoolTimeout: 3
  serverResetQuery: "DISCARD ALL"
  serverCheckDelay: 10
  serverLifetime: 3600
  serverIdleTimeout: 600
```

### 4. Redis/Broker Failure

| Aspect | Detail |
|--------|--------|
| **Symptoms** | Tasks not dispatched to workers, queue backlog grows |
| **Detection** | `broker_connection_retry_on_startup`, Celery connection errors |
| **Root Causes** | Memory exhaustion, network issue, node failure |
| **Mitigation** | Redis cluster with automatic failover (ElastiCache) |
| **Recovery** | Redis Sentinel/Cluster automatic failover |
| **RTO** | 10-30 seconds |

```hcl
# ElastiCache Redis Cluster for Airflow
resource "aws_elasticache_replication_group" "airflow_broker" {
  replication_group_id       = "airflow-broker"
  description               = "Airflow Celery broker"
  engine                    = "redis"
  engine_version            = "7.0"
  node_type                 = "cache.r6g.xlarge"
  num_cache_clusters        = 3
  port                      = 6379

  automatic_failover_enabled = true
  multi_az_enabled          = true
  at_rest_encryption_enabled = true
  transit_encryption_enabled = true

  # Maintenance
  maintenance_window        = "sun:05:00-sun:06:00"
  snapshot_retention_limit  = 7
  snapshot_window           = "03:00-04:00"

  parameter_group_name = aws_elasticache_parameter_group.airflow.name
}

resource "aws_elasticache_parameter_group" "airflow" {
  name   = "airflow-redis-params"
  family = "redis7"

  parameter {
    name  = "maxmemory-policy"
    value = "noeviction"  # Critical: don't evict task messages
  }
  parameter {
    name  = "tcp-keepalive"
    value = "60"
  }
}
```

### 5. Complete Region Failure

| Aspect | Detail |
|--------|--------|
| **Symptoms** | Everything in the region is unavailable |
| **Detection** | Cross-region health checks (Route53 health checks) |
| **Root Causes** | AWS region outage (rare but happens), natural disaster |
| **Mitigation** | Multi-region setup with warm standby |
| **Recovery** | DNS failover to secondary region |
| **RTO** | 5-15 minutes (depends on DNS TTL and data sync) |

### 6. Deployment Failure (Bad Code/Config)

| Aspect | Detail |
|--------|--------|
| **Symptoms** | `dag_processing.import_errors` spike, tasks failing with new errors |
| **Detection** | Import error count metric > threshold within 5 minutes of deploy |
| **Root Causes** | Syntax error in DAG, missing dependency, bad config change |
| **Mitigation** | CI/CD validation, canary deployment, GitSync with branch control |
| **Recovery** | Rollback GitSync branch, redeploy previous image |
| **RTO** | 2-5 minutes |

```yaml
# Automated rollback on import errors
apiVersion: argoproj.io/v1alpha1
kind: AnalysisTemplate
metadata:
  name: airflow-deploy-health
spec:
  metrics:
    - name: dag-import-errors
      interval: 30s
      count: 5
      successCondition: result[0] <= 2  # Allow max 2 import errors
      provider:
        prometheus:
          address: http://prometheus:9090
          query: |
            airflow_dag_processing_import_errors
    - name: scheduler-heartbeat
      interval: 10s
      count: 10
      successCondition: result[0] > 0
      provider:
        prometheus:
          address: http://prometheus:9090
          query: |
            up{job="airflow-scheduler"}
```

---

## Multi-Region Architecture

### Active-Passive Setup

```
┌─────────────── Primary Region (us-east-1) ──────────────┐
│                                                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────────┐  │
│  │Scheduler │  │Scheduler │  │     Workers (20)      │  │
│  │  (HA-1)  │  │  (HA-2)  │  │  Auto-scaling 5-50   │  │
│  └────┬─────┘  └────┬─────┘  └──────────┬───────────┘  │
│       │              │                    │              │
│       └──────────────┼────────────────────┘              │
│                      │                                   │
│              ┌───────▼────────┐                          │
│              │  RDS Primary   │──── async replication ───┼──┐
│              │  (Multi-AZ)    │                          │  │
│              └────────────────┘                          │  │
│                                                          │  │
│              ┌────────────────┐                          │  │
│              │ Redis Cluster  │                          │  │
│              └────────────────┘                          │  │
└──────────────────────────────────────────────────────────┘  │
                                                              │
┌─────────────── DR Region (us-west-2) ───────────────────┐  │
│                                                          │  │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────────┐  │  │
│  │Scheduler │  │Scheduler │  │   Workers (STOPPED)   │  │  │
│  │ (STOPPED)│  │ (STOPPED)│  │   (Scale to 0)       │  │  │
│  └──────────┘  └──────────┘  └──────────────────────┘  │  │
│                                                          │  │
│              ┌────────────────┐                          │  │
│              │  RDS Replica   │◄─────────────────────────┼──┘
│              │  (Read-only)   │                          │
│              └────────────────┘                          │
│                                                          │
│              ┌────────────────┐                          │
│              │ Redis (STOPPED)│                          │
│              └────────────────┘                          │
└──────────────────────────────────────────────────────────┘

DNS: Route53 health-check based failover
Git: Same repo, both regions have GitSync configured
```

#### Failover Procedure (Step by Step)

```bash
#!/bin/bash
# failover-to-dr.sh - Execute region failover

set -euo pipefail

PRIMARY_REGION="us-east-1"
DR_REGION="us-west-2"
CLUSTER_NAME="airflow-prod-dr"

echo "=== AIRFLOW DR FAILOVER INITIATED ==="
echo "Time: $(date -u)"
echo "Failing over from ${PRIMARY_REGION} to ${DR_REGION}"

# Step 1: Promote RDS read replica
echo "[1/7] Promoting RDS read replica..."
aws rds promote-read-replica \
  --db-instance-identifier airflow-metadata-dr \
  --region ${DR_REGION}

# Wait for promotion
aws rds wait db-instance-available \
  --db-instance-identifier airflow-metadata-dr \
  --region ${DR_REGION}
echo "  ✓ RDS promoted successfully"

# Step 2: Enable Multi-AZ on promoted instance
echo "[2/7] Enabling Multi-AZ on promoted instance..."
aws rds modify-db-instance \
  --db-instance-identifier airflow-metadata-dr \
  --multi-az \
  --apply-immediately \
  --region ${DR_REGION}

# Step 3: Start Redis cluster
echo "[3/7] Starting Redis cluster..."
aws elasticache modify-replication-group \
  --replication-group-id airflow-broker-dr \
  --apply-immediately \
  --region ${DR_REGION}

# Step 4: Scale up workers
echo "[4/7] Scaling up workers in DR region..."
kubectl --context ${CLUSTER_NAME} scale deployment airflow-worker --replicas=10
kubectl --context ${CLUSTER_NAME} scale deployment airflow-scheduler --replicas=3

# Step 5: Wait for components to be healthy
echo "[5/7] Waiting for health checks..."
for i in $(seq 1 60); do
  HEALTH=$(kubectl --context ${CLUSTER_NAME} get pods -l component=scheduler \
    -o jsonpath='{.items[*].status.phase}' | tr ' ' '\n' | grep -c "Running" || true)
  if [ "$HEALTH" -ge 2 ]; then
    echo "  ✓ Schedulers healthy"
    break
  fi
  sleep 5
done

# Step 6: Update DNS
echo "[6/7] Updating Route53 DNS..."
aws route53 change-resource-record-sets \
  --hosted-zone-id ${HOSTED_ZONE_ID} \
  --change-batch '{
    "Changes": [{
      "Action": "UPSERT",
      "ResourceRecordSet": {
        "Name": "airflow.internal.company.com",
        "Type": "CNAME",
        "TTL": 60,
        "ResourceRecords": [{"Value": "airflow-dr.us-west-2.elb.amazonaws.com"}]
      }
    }]
  }'

# Step 7: Verify
echo "[7/7] Running verification..."
sleep 30
curl -f https://airflow.internal.company.com/health || {
  echo "CRITICAL: Health check failed after failover!"
  exit 1
}

echo "=== FAILOVER COMPLETE ==="
echo "Action items:"
echo "  1. Verify DAG runs are being created"
echo "  2. Check for stale task instances and clear them"
echo "  3. Notify stakeholders"
echo "  4. Create incident ticket"
```

### Active-Active Setup (Advanced)

```
┌────── Region A (us-east-1) ──────┐    ┌────── Region B (eu-west-1) ──────┐
│                                   │    │                                   │
│  DAGs: US pipelines               │    │  DAGs: EU pipelines               │
│  - us_billing_*                   │    │  - eu_billing_*                   │
│  - us_compliance_*                │    │  - eu_gdpr_*                      │
│  - global_ml_training             │    │  - eu_compliance_*                │
│                                   │    │                                   │
│  ┌─────────┐  ┌─────────────┐   │    │   ┌─────────┐  ┌─────────────┐  │
│  │Scheduler│  │  Workers    │   │    │   │Scheduler│  │  Workers    │  │
│  └─────────┘  └─────────────┘   │    │   └─────────┘  └─────────────┘  │
│       │                          │    │        │                         │
│  ┌────▼──────┐                   │    │   ┌────▼──────┐                  │
│  │ RDS (own) │                   │    │   │ RDS (own) │                  │
│  └───────────┘                   │    │   └───────────┘                  │
│                                   │    │                                   │
└───────────────────────────────────┘    └───────────────────────────────────┘
         │                                          │
         └──────── Cross-Region Events ─────────────┘
              (SNS/EventBridge for triggers)
```

**When to use Active-Active:**
- GDPR/data residency requirements (EU data must stay in EU)
- Global operations with regional SLAs
- Extremely high availability requirements (99.99%+)
- Typically only for organizations with 1000+ DAGs across regions

---

## Backup Strategy

### Metadata Database Backup

```hcl
# Automated backup configuration
resource "aws_db_instance" "airflow_metadata" {
  # ... other config ...

  # Automated backups
  backup_retention_period = 30        # 30 days of automated backups
  backup_window          = "03:00-04:00"  # During low activity

  # Enable PITR
  # (enabled automatically when backup_retention_period > 0)
}

# Cross-region backup
resource "aws_db_instance_automated_backups_replication" "dr" {
  provider               = aws.dr_region
  source_db_instance_arn = aws_db_instance.airflow_metadata.arn
  retention_period       = 14
}
```

```bash
# Manual backup script (for pre-maintenance)
#!/bin/bash
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Create manual snapshot
aws rds create-db-snapshot \
  --db-instance-identifier airflow-metadata-prod \
  --db-snapshot-identifier "airflow-pre-maintenance-${TIMESTAMP}"

# Export critical tables for fast restore
pg_dump -h $DB_HOST -U airflow -d airflow \
  --table=dag --table=dag_run --table=task_instance \
  --table=connection --table=variable \
  -F c -f "/tmp/airflow_critical_${TIMESTAMP}.dump"

# Upload to S3
aws s3 cp "/tmp/airflow_critical_${TIMESTAMP}.dump" \
  "s3://airflow-backups-prod/manual/${TIMESTAMP}/"
```

### Monthly Backup Validation

```bash
#!/bin/bash
# backup-validation.sh - Run monthly to verify backups are restorable

echo "=== Monthly Backup Restore Test ==="

# Restore latest snapshot to test instance
LATEST_SNAPSHOT=$(aws rds describe-db-snapshots \
  --db-instance-identifier airflow-metadata-prod \
  --query 'DBSnapshots | sort_by(@, &SnapshotCreateTime) | [-1].DBSnapshotIdentifier' \
  --output text)

echo "Restoring snapshot: ${LATEST_SNAPSHOT}"

aws rds restore-db-instance-from-db-snapshot \
  --db-instance-identifier airflow-backup-test \
  --db-snapshot-identifier "${LATEST_SNAPSHOT}" \
  --db-instance-class db.t3.large \
  --no-multi-az

aws rds wait db-instance-available \
  --db-instance-identifier airflow-backup-test

# Validate data integrity
ENDPOINT=$(aws rds describe-db-instances \
  --db-instance-identifier airflow-backup-test \
  --query 'DBInstances[0].Endpoint.Address' --output text)

psql -h ${ENDPOINT} -U airflow -d airflow -c "
  SELECT 'dag_count' as check, count(*) as value FROM dag
  UNION ALL
  SELECT 'recent_runs', count(*) FROM dag_run WHERE execution_date > now() - interval '7 days'
  UNION ALL
  SELECT 'connections', count(*) FROM connection;
"

# Cleanup
aws rds delete-db-instance \
  --db-instance-identifier airflow-backup-test \
  --skip-final-snapshot

echo "=== Backup validation complete ==="
```

### DAG Code Backup

```yaml
# Git mirror to secondary region (GitHub Actions)
name: Mirror DAGs to DR
on:
  push:
    branches: [main, production]
jobs:
  mirror:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - name: Push to DR mirror
        run: |
          git remote add dr ${DR_REPO_URL}
          git push dr --all --force
          git push dr --tags --force
```

### Connections & Variables Backup

```python
"""Export Airflow connections and variables for DR scenarios."""
import json
from airflow.models import Connection, Variable
from airflow.utils.session import create_session

def export_metadata():
    """Export connections and variables to JSON (excluding secrets)."""
    with create_session() as session:
        connections = session.query(Connection).all()
        conn_export = [{
            'conn_id': c.conn_id,
            'conn_type': c.conn_type,
            'host': c.host,
            'port': c.port,
            'schema': c.schema,
            'login': c.login,
            'extra': c.extra,
            # Password NOT exported - stored in secrets manager
        } for c in connections]

        variables = session.query(Variable).all()
        var_export = [{
            'key': v.key,
            'val': v.val,
            'description': v.description,
        } for v in variables if not v.key.startswith('secret_')]

    return {'connections': conn_export, 'variables': var_export}

def import_metadata(data):
    """Import connections and variables from backup."""
    with create_session() as session:
        for conn in data['connections']:
            existing = session.query(Connection).filter_by(conn_id=conn['conn_id']).first()
            if not existing:
                session.add(Connection(**conn))

        for var in data['variables']:
            Variable.set(var['key'], var['val'], description=var.get('description'))
```

---

## Recovery Procedures

### Runbook: Complete Metadata DB Recovery

```
RUNBOOK: Metadata Database Full Recovery
========================================
Severity: P1
RTO Target: 30 minutes
RPO Target: 5 minutes (PITR)

PRE-REQUISITES:
- AWS Console access with RDS admin permissions
- kubectl access to Airflow cluster
- Access to backup S3 bucket

PROCEDURE:

1. ASSESS THE SITUATION (2 min)
   □ Confirm DB is unrecoverable (not just a failover)
   □ Check: aws rds describe-db-instances --db-instance-identifier airflow-metadata-prod
   □ Determine RPO: what's the latest recoverable point?

2. STOP AIRFLOW COMPONENTS (2 min)
   □ kubectl scale deployment airflow-scheduler --replicas=0
   □ kubectl scale deployment airflow-webserver --replicas=0
   □ kubectl scale deployment airflow-worker --replicas=0
   □ kubectl scale deployment airflow-triggerer --replicas=0

3. RESTORE DATABASE (10-20 min)
   Option A: Point-in-Time Recovery (preferred)
   □ aws rds restore-db-instance-to-point-in-time \
       --source-db-instance-identifier airflow-metadata-prod \
       --target-db-instance-identifier airflow-metadata-restored \
       --restore-time "2024-01-15T10:30:00Z" \
       --db-instance-class db.r6g.2xlarge \
       --multi-az

   Option B: From Snapshot
   □ aws rds restore-db-instance-from-db-snapshot \
       --db-instance-identifier airflow-metadata-restored \
       --db-snapshot-identifier <latest-snapshot-id> \
       --db-instance-class db.r6g.2xlarge \
       --multi-az

4. WAIT FOR RESTORE (5-15 min)
   □ aws rds wait db-instance-available \
       --db-instance-identifier airflow-metadata-restored

5. UPDATE CONNECTION STRING (2 min)
   □ Get new endpoint:
     aws rds describe-db-instances --db-instance-identifier airflow-metadata-restored \
       --query 'DBInstances[0].Endpoint.Address'
   □ Update Kubernetes secret:
     kubectl edit secret airflow-metadata-connection
   □ Or update Parameter Store:
     aws ssm put-parameter --name /airflow/prod/db-host --value <new-endpoint> --overwrite

6. VERIFY DATABASE INTEGRITY (3 min)
   □ Connect to new DB and run:
     SELECT count(*) FROM dag;
     SELECT count(*) FROM dag_run WHERE state='running';
     SELECT max(execution_date) FROM dag_run;
   □ Check alembic version:
     SELECT * FROM alembic_version;

7. CLEAR STALE STATE (2 min)
   □ Mark running tasks as failed (they were interrupted):
     UPDATE task_instance SET state='failed'
     WHERE state='running' AND end_date IS NULL;
   □ Mark queued tasks as scheduled (need re-queue):
     UPDATE task_instance SET state='scheduled'
     WHERE state='queued';

8. RESTART COMPONENTS (in order) (3 min)
   □ kubectl scale deployment airflow-scheduler --replicas=3
   □ Wait 30s for scheduler to register
   □ kubectl scale deployment airflow-triggerer --replicas=2
   □ kubectl scale deployment airflow-worker --replicas=10
   □ kubectl scale deployment airflow-webserver --replicas=3

9. VERIFY RECOVERY (5 min)
   □ Check scheduler heartbeat: curl airflow:8080/health
   □ Verify DAG runs are being created
   □ Check no import errors
   □ Verify task instances are progressing
   □ Check worker registration in Flower

10. POST-RECOVERY
    □ Create incident report
    □ Set up new cross-region replica
    □ Rename/cleanup old DB instance
    □ Update monitoring if endpoints changed
    □ Notify stakeholders of any data loss window
```

### Runbook: Region Failover

```
RUNBOOK: Complete Region Failover
=================================
Severity: P1
RTO Target: 15 minutes
Trigger: Primary region health check failing for > 5 minutes

PROCEDURE:

1. CONFIRM REGION FAILURE (2 min)
   □ Verify it's not a transient issue
   □ Check AWS status page: https://health.aws.amazon.com/
   □ Try accessing other services in the region
   □ Decision: proceed with failover? (requires 2 engineers to confirm)

2. EXECUTE FAILOVER SCRIPT (5 min)
   □ ./scripts/failover-to-dr.sh
   □ Monitor script output for errors
   □ If script fails, proceed with manual steps below

3. MANUAL STEPS (if script fails)
   □ Promote RDS replica in DR region
   □ Start Redis/ElastiCache in DR region
   □ Scale up Kubernetes deployments
   □ Update DNS records (TTL should already be 60s)

4. VERIFY DR REGION (3 min)
   □ Health endpoint responding
   □ DAGs are listed in webserver
   □ New DAG runs being created
   □ Workers processing tasks

5. HANDLE DATA GAP (5 min)
   □ Identify last successful run per DAG in primary
   □ Compare with DR state
   □ Clear and backfill any gaps:
     airflow dags backfill <dag_id> -s <start> -e <end> --reset-dagruns

6. COMMUNICATION
   □ Notify: #incident-channel
   □ Update status page
   □ Email stakeholders with:
     - What happened
     - Impact window
     - Data gap (if any)
     - Expected recovery of primary
```

### Runbook: Rollback Bad Deployment

```
RUNBOOK: Rollback Bad Deployment
================================
Severity: P2
RTO Target: 5 minutes
Trigger: import_errors spike OR task failure rate spike post-deploy

PROCEDURE:

1. IDENTIFY THE ISSUE (1 min)
   □ Check: airflow dags list-import-errors
   □ Check recent deploy: kubectl rollout history deployment/airflow-scheduler
   □ Check git log for DAG repo: git log --oneline -5

2. DETERMINE ROLLBACK TYPE
   □ Bad DAG code → rollback GitSync
   □ Bad Airflow image → rollback deployment
   □ Bad config/env → rollback configmap/secret
   □ Bad DB migration → rollback migration (DANGER)

3a. ROLLBACK DAG CODE (most common)
    □ git revert HEAD  (or reset to known good commit)
    □ git push origin production
    □ Wait for GitSync (30-60s)
    □ Verify import errors cleared

3b. ROLLBACK AIRFLOW IMAGE
    □ kubectl rollout undo deployment/airflow-scheduler
    □ kubectl rollout undo deployment/airflow-worker
    □ kubectl rollout undo deployment/airflow-webserver
    □ kubectl rollout undo deployment/airflow-triggerer

3c. ROLLBACK DB MIGRATION
    □ CAUTION: Only if migration just ran and is reversible
    □ airflow db downgrade --to-revision <previous_revision>
    □ Verify: airflow db check-migrations

4. VERIFY RECOVERY (2 min)
   □ Import errors = 0
   □ Task success rate returning to normal
   □ No scheduler errors in logs

5. POST-MORTEM
   □ Why did CI/CD not catch this?
   □ Add test case to prevent recurrence
   □ Update canary deployment rules
```

---

## Chaos Engineering

### Testing Resilience

```python
"""
Chaos experiments for Airflow resilience validation.
Run in staging environment on a regular schedule.
"""

# Experiment 1: Kill random worker during task execution
def chaos_kill_worker():
    """
    Hypothesis: Tasks on killed worker will be detected as zombies
    and retried on another worker within scheduler_zombie_task_threshold.
    """
    import subprocess
    import random

    # Get running worker pods
    result = subprocess.run(
        ["kubectl", "get", "pods", "-l", "component=worker",
         "--field-selector=status.phase=Running", "-o", "name"],
        capture_output=True, text=True
    )
    workers = result.stdout.strip().split('\n')

    # Kill a random worker
    target = random.choice(workers)
    print(f"Killing worker: {target}")
    subprocess.run(["kubectl", "delete", target, "--grace-period=0", "--force"])

    # Expected: zombie detection kicks in within 5 minutes
    # Verify: task retried and succeeded on another worker


# Experiment 2: Database latency injection
def chaos_db_latency():
    """
    Hypothesis: Airflow degrades gracefully with 5s DB latency.
    Tasks already running should continue. New scheduling slows but doesn't stop.
    """
    # Using toxiproxy or tc netem
    subprocess.run([
        "kubectl", "exec", "toxiproxy-pod", "--",
        "toxiproxy-cli", "toxic", "add",
        "--type=latency", "--attribute=latency=5000",
        "--upstream", "postgres-proxy"
    ])
    # Monitor for 10 minutes, then remove toxic
    # Expected: scheduler loop time increases but doesn't crash


# Experiment 3: Redis memory exhaustion
def chaos_redis_full():
    """
    Hypothesis: When Redis is full, new tasks queue locally
    and are dispatched when Redis recovers.
    """
    # Fill Redis to maxmemory
    # With noeviction policy, writes should fail
    # Expected: Celery raises OperationalError, scheduler retries dispatch
```

### Chaos Schedule

```yaml
# CronJob for regular chaos testing (staging only)
apiVersion: batch/v1
kind: CronJob
metadata:
  name: airflow-chaos-weekly
  namespace: airflow-staging
spec:
  schedule: "0 10 * * 3"  # Every Wednesday at 10am
  jobTemplate:
    spec:
      template:
        spec:
          containers:
            - name: chaos
              image: chaos-toolkit:latest
              command: ["chaos", "run", "/experiments/airflow-resilience.json"]
              env:
                - name: CHAOS_TARGET
                  value: "staging"
          restartPolicy: Never
```

---

## Data Consistency During Failures

### The Problem

```
Timeline of a failure:
  T+0s:  Task starts, begins writing to target table
  T+30s: Worker processes 500K of 1M rows
  T+31s: Worker OOM killed
  T+5m:  Zombie detected, task retried
  T+5m1s: Task starts again... but 500K rows already written!

Without idempotency: DUPLICATE DATA
```

### Solutions

```python
# Pattern 1: Write-then-swap (atomic)
def idempotent_load(**context):
    """Write to temp table, then atomic swap."""
    run_id = context['run_id']
    temp_table = f"staging.load_{run_id.replace(':', '_')}"

    # Always write to a unique temp table
    spark.write.mode("overwrite").saveAsTable(temp_table)

    # Atomic swap (this is the commit point)
    spark.sql(f"""
        ALTER TABLE production.target
        SWAP WITH {temp_table}
    """)


# Pattern 2: Checkpoint/resume for long tasks
def resumable_processing(**context):
    """Process with checkpoints - can resume from where it left off."""
    ti = context['task_instance']
    checkpoint_key = f"checkpoint_{ti.dag_id}_{ti.task_id}_{ti.run_id}"

    # Check for existing checkpoint
    last_offset = Variable.get(checkpoint_key, default_var=0, deserialize_json=True)

    # Resume from checkpoint
    for batch_offset in range(last_offset, total_records, BATCH_SIZE):
        process_batch(batch_offset, BATCH_SIZE)

        # Save checkpoint every N batches
        if batch_offset % (BATCH_SIZE * 10) == 0:
            Variable.set(checkpoint_key, batch_offset, serialize_json=True)

    # Cleanup checkpoint on success
    Variable.delete(checkpoint_key)
```

---

## Recovery Time & Point Objectives

| Component | RTO | RPO | Strategy | Cost |
|-----------|-----|-----|----------|------|
| Scheduler | 30s | 0 | HA (multiple instances) | Low |
| Workers | 5min | 0 | Auto-retry + autoscale | Low |
| Metadata DB | 60s | 0 | Multi-AZ failover | Medium |
| Redis/Broker | 30s | ~1min | Cluster failover | Medium |
| Full Region | 15min | ~5min | Cross-region failover | High |
| Bad Deploy | 5min | 0 | Rollback | Low |
| DB Corruption | 30min | 5min | PITR restore | Medium |
| Security Incident | 1hr | 0 | Credential rotation + redeploy | High |

---

## Production DR Checklist

### Infrastructure

- [ ] Metadata DB: Multi-AZ enabled
- [ ] Metadata DB: Automated backups (30 day retention)
- [ ] Metadata DB: Cross-region read replica
- [ ] Metadata DB: PITR enabled
- [ ] Redis: Cluster mode with automatic failover
- [ ] Redis: `maxmemory-policy` set to `noeviction`
- [ ] Scheduler: 2+ replicas with PodDisruptionBudget
- [ ] Workers: Autoscaling configured (min 5, handles 10x spike)
- [ ] Workers: Graceful termination handling (SIGTERM → drain)
- [ ] DNS: Low TTL (60s) for failover speed
- [ ] DNS: Health-check based routing configured

### Monitoring & Alerting

- [ ] Alert: Scheduler heartbeat missing > 60s
- [ ] Alert: Import errors > 0 (new errors)
- [ ] Alert: Task failure rate > 10% (5 min window)
- [ ] Alert: DB connection errors
- [ ] Alert: Redis connection failures
- [ ] Alert: Worker count below minimum
- [ ] Alert: DAG processing time > 60s
- [ ] Dashboard: DR readiness status

### Operational Readiness

- [ ] Runbook: DB recovery documented and tested
- [ ] Runbook: Region failover documented and tested
- [ ] Runbook: Deployment rollback documented and tested
- [ ] Failover script tested quarterly
- [ ] Backup restore tested monthly
- [ ] Chaos experiments running weekly (staging)
- [ ] DR drill conducted quarterly with full team
- [ ] On-call rotation with DR-trained engineers
- [ ] Communication templates ready (Slack, email, status page)

### Application Resilience

- [ ] All tasks have retry configuration
- [ ] Critical tasks are idempotent
- [ ] Long-running tasks have checkpoints
- [ ] External dependency failures are handled (timeouts, retries)
- [ ] Circuit breakers for flaky external services
- [ ] Graceful degradation: non-critical DAGs can be paused

### Recovery Validation Metrics

```python
# Prometheus alerts for DR readiness
groups:
  - name: airflow_dr_readiness
    rules:
      - alert: DRReplicaLagHigh
        expr: aws_rds_replica_lag_seconds{instance="airflow-metadata-dr"} > 60
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "DR database replica lag exceeds 60 seconds"

      - alert: BackupAge
        expr: (time() - aws_rds_last_snapshot_timestamp{instance="airflow-metadata-prod"}) > 86400
        for: 1h
        labels:
          severity: critical
        annotations:
          summary: "No backup in the last 24 hours"

      - alert: DRRegionUnhealthy
        expr: probe_success{job="dr-region-healthcheck"} == 0
        for: 10m
        labels:
          severity: critical
        annotations:
          summary: "DR region health check failing"
```

---

## Key Takeaways

1. **HA is not DR** - HA handles component failures; DR handles catastrophic failures
2. **Test your recovery** - Untested backups are not backups
3. **Automate failover** - Manual procedures under stress lead to errors
4. **RPO determines cost** - 0 RPO (synchronous replication) is expensive; decide what you can lose
5. **Practice regularly** - Quarterly DR drills keep the muscle memory fresh
6. **Idempotency is your safety net** - When recovery means re-running tasks, they must be safe to re-run
