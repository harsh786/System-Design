# Disaster Recovery & Resilience — Temporal at Scale

## Table of Contents
1. [Failure Modes](#failure-modes)
2. [High Availability Architecture](#high-availability-architecture)
3. [Backup & Restore](#backup--restore)
4. [Disaster Recovery Procedures](#disaster-recovery-procedures)
5. [Chaos Engineering](#chaos-engineering)
6. [Workflow Recovery Patterns](#workflow-recovery-patterns)
7. [Resilience Patterns in Code](#resilience-patterns-in-code)
8. [SLA Management](#sla-management)

---

## Failure Modes

### Component Failure Matrix

```
┌─────────────────────┬───────────┬───────────────────────────────────────────────┐
│ Failure             │ Impact    │ Temporal's Built-in Handling                  │
├─────────────────────┼───────────┼───────────────────────────────────────────────┤
│ Single History pod  │ Low       │ Shards redistribute in 5-30s automatically   │
│ All History pods    │ Critical  │ Total outage until pods recover              │
│ Frontend pod        │ None      │ LB routes to other pods                      │
│ All Frontend pods   │ Critical  │ No new requests accepted                     │
│ Matching pod        │ Low       │ Task queues redistribute                     │
│ All Matching pods   │ High      │ No task dispatch (activities stuck)           │
│ Single DB node      │ None      │ Quorum still met (RF=3)                      │
│ DB quorum loss      │ Critical  │ All persistence operations fail              │
│ Single AZ           │ Low       │ Anti-affinity spreads across AZs             │
│ Entire region       │ High      │ Multi-cluster failover needed                │
│ Worker pod crash    │ None      │ Activity retried on another worker           │
│ All workers crash   │ High      │ Tasks queue up, resume when workers return   │
│ Network partition   │ Variable  │ Split-brain protection via shard ownership   │
├─────────────────────┼───────────┼───────────────────────────────────────────────┤
│ Non-determinism bug │ High      │ Workflow tasks fail, activities not retried   │
│ Activity panic      │ Low       │ Retry policy handles it                      │
│ Bad deployment      │ High      │ Rollback needed                              │
│ Config error        │ Variable  │ Dynamic config hot-reloaded on fix           │
└─────────────────────┴───────────┴───────────────────────────────────────────────┘
```

### Failure Blast Radius

```
                    Blast Radius Diagram
                    
     Small ◄──────────────────────────────────► Large
     
     │ Worker    │ Single  │ Matching │ History │ Database │ Region │
     │ pod       │ History │ service  │ service │ quorum   │ failure│
     │ crash     │ pod     │ pod      │ fleet   │ loss     │        │
     │           │         │          │         │          │        │
     │ 1 activity│ ~100    │ Some     │ ALL     │ ALL      │ ALL    │
     │ retried   │ workflows│ queues  │ workflows│ workflows│ workflows│
     │           │ delayed │ delayed  │ stuck   │ fail     │ in region│
     │           │ 5-30s   │ 5-30s   │         │          │        │
```

---

## High Availability Architecture

```
┌──────────────────────────────────────────────────────────────────────────┐
│                    Multi-AZ High Availability Design                       │
│                                                                            │
│  ┌────────────────────┐ ┌────────────────────┐ ┌────────────────────┐    │
│  │       AZ-1          │ │       AZ-2          │ │       AZ-3          │    │
│  │                      │ │                      │ │                      │    │
│  │  Frontend (2)        │ │  Frontend (2)        │ │  Frontend (2)        │    │
│  │  History (3)         │ │  History (3)         │ │  History (3)         │    │
│  │  Matching (2)        │ │  Matching (2)        │ │  Matching (2)        │    │
│  │  Worker (1)          │ │  Worker (1)          │ │  Worker (1)          │    │
│  │                      │ │                      │ │                      │    │
│  │  Cassandra (2)       │ │  Cassandra (2)       │ │  Cassandra (2)       │    │
│  │  ES Data (2)         │ │  ES Data (2)         │ │  ES Data (2)         │    │
│  │  ES Master (1)       │ │  ES Master (1)       │ │  ES Master (1)       │    │
│  └────────────────────┘ └────────────────────┘ └────────────────────┘    │
│                                                                            │
│  HA Properties:                                                            │
│  • Loss of any single AZ: service continues with degraded capacity        │
│  • Cassandra: LOCAL_QUORUM met with 2/3 AZs (RF=3, need 2 for quorum)    │
│  • ES: 1 replica, survives 1 AZ loss                                      │
│  • Temporal: shards redistribute, PDB prevents simultaneous pod kills     │
│  • Workers: anti-affinity ensures no single-AZ concentration              │
└──────────────────────────────────────────────────────────────────────────┘
```

### PDB Configuration (Preventing Unsafe Disruptions)

```yaml
# Pod Disruption Budgets - prevent Kubernetes from killing too many pods

# History - most critical, very strict
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: temporal-history-pdb
  namespace: temporal
spec:
  maxUnavailable: 1  # Only 1 history pod can be disrupted at a time
  selector:
    matchLabels:
      app.kubernetes.io/component: history

---
# Frontend - at least 2 must always be running
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: temporal-frontend-pdb
  namespace: temporal
spec:
  minAvailable: 2
  selector:
    matchLabels:
      app.kubernetes.io/component: frontend

---
# Matching
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: temporal-matching-pdb
  namespace: temporal
spec:
  minAvailable: "75%"
  selector:
    matchLabels:
      app.kubernetes.io/component: matching

---
# Workers - allow more disruption (activities are retried)
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: temporal-worker-pdb
  namespace: temporal-workers
spec:
  maxUnavailable: "25%"
  selector:
    matchLabels:
      app: temporal-worker
```

---

## Backup & Restore

### Database Backup Strategy

#### Cassandra Snapshot Strategy

```bash
#!/bin/bash
# cassandra-backup.sh - Automated Cassandra backup for Temporal
set -euo pipefail

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
KEYSPACES="temporal temporal_visibility"
BACKUP_BUCKET="s3://company-temporal-backups"
RETENTION_DAYS=30

for KEYSPACE in $KEYSPACES; do
  echo "=== Snapshotting keyspace: $KEYSPACE ==="
  
  # Take snapshot on all nodes (run via parallel SSH or K8s job)
  SNAPSHOT_NAME="${KEYSPACE}_${TIMESTAMP}"
  nodetool snapshot --tag "$SNAPSHOT_NAME" "$KEYSPACE"
  
  # Upload snapshot files to S3
  SNAPSHOT_DIR="/var/lib/cassandra/data/${KEYSPACE}"
  for TABLE_DIR in "${SNAPSHOT_DIR}"/*/; do
    TABLE_NAME=$(basename "$TABLE_DIR")
    SNAP_PATH="${TABLE_DIR}snapshots/${SNAPSHOT_NAME}"
    
    if [ -d "$SNAP_PATH" ]; then
      aws s3 sync "$SNAP_PATH" \
        "${BACKUP_BUCKET}/cassandra/${TIMESTAMP}/${KEYSPACE}/${TABLE_NAME}/" \
        --storage-class STANDARD_IA \
        --quiet
    fi
  done
  
  # Clear old snapshots from disk
  nodetool clearsnapshot --tag "$SNAPSHOT_NAME" "$KEYSPACE"
done

# Cleanup old backups from S3
aws s3 ls "${BACKUP_BUCKET}/cassandra/" | while read -r line; do
  BACKUP_DATE=$(echo "$line" | awk '{print $2}' | tr -d '/')
  if [ "$(date -d "$BACKUP_DATE" +%s 2>/dev/null || echo 0)" -lt "$(date -d "-${RETENTION_DAYS} days" +%s)" ]; then
    echo "Deleting old backup: ${BACKUP_DATE}"
    aws s3 rm "${BACKUP_BUCKET}/cassandra/${BACKUP_DATE}/" --recursive
  fi
done

echo "=== Backup complete: ${TIMESTAMP} ==="
```

#### PostgreSQL WAL Archiving with pgBackRest

```ini
# /etc/pgbackrest/pgbackrest.conf
[global]
repo1-type=s3
repo1-s3-bucket=company-temporal-backups
repo1-s3-region=us-east-1
repo1-s3-endpoint=s3.amazonaws.com
repo1-path=/pgbackrest
repo1-retention-full=4
repo1-retention-diff=14
repo1-cipher-type=aes-256-cbc
repo1-cipher-pass=${PGBACKREST_CIPHER_PASS}
compress-type=zst
compress-level=3
process-max=4

[temporal]
pg1-path=/var/lib/postgresql/15/main
pg1-port=5432
pg1-user=temporal_backup
pg1-database=temporal
```

```yaml
# Backup CronJobs
apiVersion: batch/v1
kind: CronJob
metadata:
  name: pg-full-backup
  namespace: temporal
spec:
  schedule: "0 2 * * 0"  # Weekly full backup Sunday 2am
  jobTemplate:
    spec:
      template:
        spec:
          containers:
            - name: pgbackrest
              image: pgbackrest/pgbackrest:2.48
              command: ["pgbackrest", "--stanza=temporal", "backup", "--type=full"]
---
apiVersion: batch/v1
kind: CronJob
metadata:
  name: pg-diff-backup
  namespace: temporal
spec:
  schedule: "0 2 * * 1-6"  # Daily diff backup Mon-Sat 2am
  jobTemplate:
    spec:
      template:
        spec:
          containers:
            - name: pgbackrest
              image: pgbackrest/pgbackrest:2.48
              command: ["pgbackrest", "--stanza=temporal", "backup", "--type=diff"]
```

### Backup Verification Automation

```yaml
# Monthly backup restore test
apiVersion: batch/v1
kind: CronJob
metadata:
  name: backup-verify
  namespace: temporal-test
spec:
  schedule: "0 4 1 * *"  # First of month, 4am
  jobTemplate:
    spec:
      template:
        spec:
          containers:
            - name: verify
              image: registry.company.com/temporal-backup-verifier:latest
              command:
                - /bin/sh
                - -c
                - |
                  set -euo pipefail
                  
                  echo "=== Starting backup verification ==="
                  
                  # Restore to temporary instance
                  pgbackrest --stanza=temporal restore \
                    --target-action=promote \
                    --type=time \
                    --target="$(date -d '1 hour ago' +%Y-%m-%d\ %H:%M:%S)" \
                    --pg1-path=/tmp/pgdata
                  
                  # Start temporary PostgreSQL
                  pg_ctl -D /tmp/pgdata start -w
                  
                  # Verify data integrity
                  psql -h localhost -d temporal -c "
                    SELECT COUNT(*) as workflow_count FROM executions;
                    SELECT MAX(close_time) as latest_close FROM executions WHERE close_time IS NOT NULL;
                  "
                  
                  # Verify Temporal schema version
                  psql -h localhost -d temporal -c "
                    SELECT * FROM schema_version ORDER BY version_partition DESC LIMIT 1;
                  "
                  
                  # Cleanup
                  pg_ctl -D /tmp/pgdata stop
                  rm -rf /tmp/pgdata
                  
                  echo "=== Backup verification PASSED ==="
                  
                  # Send success notification
                  curl -X POST "${SLACK_WEBHOOK}" \
                    -H 'Content-type: application/json' \
                    -d '{"text":"✅ Monthly Temporal backup verification passed"}'
```

---

## Disaster Recovery Procedures

### Scenario 1: Single AZ Failure

```
═══════════════════════════════════════════════════════════════
DR PROCEDURE: Single Availability Zone Failure
RTO: < 5 minutes (automatic)
RPO: 0 (no data loss with quorum replication)
═══════════════════════════════════════════════════════════════

DETECTION:
  - CloudWatch/monitoring detects AZ connectivity loss
  - Multiple pod NotReady alerts fire simultaneously
  - Cassandra gossip detects nodes unreachable

AUTOMATIC RECOVERY (no human intervention needed):
  
  1. Kubernetes:
     - Pods in failed AZ become NotReady (30s)
     - New pods scheduled in remaining AZs (if resource available)
     - PDB ensures remaining pods are not disrupted

  2. Temporal History:
     - History pods in failed AZ lose shard ownership
     - Ringpop membership protocol detects failure (~10s)
     - Shards redistribute to history pods in healthy AZs (~5-30s)
     - In-flight workflow tasks are retried

  3. Cassandra:
     - LOCAL_QUORUM still achievable (2/3 AZ nodes respond)
     - Read/write operations continue without interruption
     - Gossip marks failed nodes as DOWN

  4. Elasticsearch:
     - Primary shards on failed nodes: replica promoted (automatic)
     - Yellow status until replicas rebuilt on remaining nodes

HUMAN VERIFICATION:
  
  $ kubectl get nodes --selector topology.kubernetes.io/zone
  # Verify remaining AZs have capacity
  
  $ kubectl get pods -n temporal -o wide | grep -v Running
  # Check all Temporal pods healthy
  
  $ tctl cluster health
  # Verify cluster reports healthy
  
  # Check schedule-to-start latency (may spike briefly)
  # Query: histogram_quantile(0.99, ...) 

POST-RECOVERY (when AZ returns):
  
  1. Verify Cassandra nodes rejoin (nodetool status → UN)
  2. Wait for Cassandra streaming to complete (nodetool netstats)
  3. Temporal pods auto-schedule back to recovered AZ
  4. Shards rebalance automatically
  5. Monitor for 1 hour, then close incident

═══════════════════════════════════════════════════════════════
```

### Scenario 2: Database Corruption

```
═══════════════════════════════════════════════════════════════
DR PROCEDURE: Database Corruption Detected
RTO: 15-60 minutes
RPO: Depends on backup frequency (minutes to hours)
═══════════════════════════════════════════════════════════════

DETECTION SIGNALS:
  - Cassandra: ReadFailureException, CorruptSSTableException
  - PostgreSQL: "invalid page in block" errors, checksum failures
  - Temporal: persistence errors in history service logs
  - Data inconsistency: workflow state doesn't match history

IMMEDIATE ACTIONS (first 5 minutes):

  1. ASSESS SCOPE:
     - Is corruption on one node or multiple?
     - Is it one table/keyspace or all?
     - Are writes still succeeding to healthy replicas?

  2. IF SINGLE CASSANDRA NODE:
     # Stop the corrupted node
     $ nodetool drain
     $ systemctl stop cassandra
     
     # Wipe corrupted data
     $ rm -rf /var/lib/cassandra/data/temporal/
     
     # Restart - will stream from replicas
     $ systemctl start cassandra
     # Monitor: nodetool netstats (streaming progress)

  3. IF QUORUM AFFECTED (multiple nodes corrupt):
     # This is critical - cannot serve traffic
     
     # Option A: Point-in-time recovery
     # Stop Temporal server (prevent further corruption)
     $ kubectl scale deployment -n temporal --replicas=0 --all
     
     # Restore from backup
     # For Cassandra:
     $ ./restore-cassandra-snapshot.sh <backup_timestamp>
     
     # For PostgreSQL:
     $ pgbackrest --stanza=temporal restore \
       --type=time \
       --target="2024-01-15 14:30:00" \  # Last known good time
       --target-action=promote
     
     # Restart Temporal
     $ kubectl scale deployment -n temporal --replicas=<original> --all

  4. IF CROSS-CLUSTER REPLICATION AVAILABLE:
     # Failover to standby cluster (fastest recovery)
     $ ./failover-namespace.sh production us-west-2 "database corruption in us-east-1"
     
     # Then fix primary at leisure

RECONCILIATION (after restore):
  
  - Some workflows may have progressed beyond the restore point
  - These workflows will replay from the restored history
  - Activities that already ran will be retried (ensure idempotency!)
  - Check for duplicate side effects (payments, emails)
  
  # List workflows that were running during corruption window:
  $ tctl workflow list --query \
    "StartTime > '2024-01-15T14:00:00Z' AND CloseTime IS NULL"

═══════════════════════════════════════════════════════════════
```

### Scenario 3: Region Failure

```
═══════════════════════════════════════════════════════════════
DR PROCEDURE: Complete Region Failure
RTO: < 5 minutes (with pre-configured multi-cluster)
RPO: Seconds (async replication lag)
═══════════════════════════════════════════════════════════════

PREREQUISITES:
  - Multi-cluster replication configured
  - Global namespaces registered
  - Workers deployed in standby region
  - DNS TTL set low (60s)

PROCEDURE:

  1. DETECT (automated or manual):
     # Monitoring detects: all pods in region unreachable
     # Health checks failing from external probe
     # AWS status page confirms regional issue

  2. FAILOVER NAMESPACES (< 1 minute):
     # For each global namespace:
     $ tctl --address temporal.us-west-2.internal:7233 \
       namespace update \
       --namespace production \
       --active-cluster us-west-2 \
       --reason "us-east-1 region failure"
     
     $ tctl --address temporal.us-west-2.internal:7233 \
       namespace update \
       --namespace payments \
       --active-cluster us-west-2 \
       --reason "us-east-1 region failure"

  3. UPDATE DNS (< 1 minute):
     # Update Route53 to point to us-west-2
     $ aws route53 change-resource-record-sets \
       --hosted-zone-id Z1234567890 \
       --change-batch '{
         "Changes": [{
           "Action": "UPSERT",
           "ResourceRecordSet": {
             "Name": "temporal.company.internal",
             "Type": "CNAME",
             "TTL": 60,
             "ResourceRecords": [{"Value": "temporal-frontend.us-west-2.internal"}]
           }
         }]
       }'

  4. VERIFY WORKERS CONNECTED:
     # Workers in us-west-2 should already be polling
     # Workers in us-east-1 will reconnect after DNS update
     $ tctl --namespace production taskqueue describe \
       --task-queue default-task-queue
     # Verify pollerCount > 0

  5. VERIFY WORKFLOW RESUMPTION:
     # In-flight workflows resume from last replicated state
     # Some workflows may re-execute recent activities (idempotency critical)
     
     # Check for stuck workflows:
     $ tctl workflow list --query "ExecutionStatus='Running'" --limit 10
     
     # Verify new workflows can start:
     $ tctl workflow start --workflow-type HealthCheckWorkflow \
       --task-queue default-task-queue --workflow-id dr-verification

  6. MONITOR (next 30 minutes):
     - schedule-to-start latency normalizing
     - Error rate returning to baseline
     - No data inconsistency alerts
     - Verify cross-region worker connectivity

POST-REGION-RECOVERY:
  
  When us-east-1 returns:
  1. DO NOT immediately failback (verify stability first)
  2. Let replication catch up (monitor replication lag)
  3. Schedule failback during maintenance window
  4. Failback: repeat steps 2-5 in reverse
  5. Verify original region stable for 24h

═══════════════════════════════════════════════════════════════
```

### Scenario 4: Non-Determinism Bug in Production

```
═══════════════════════════════════════════════════════════════
DR PROCEDURE: Non-Determinism Bug Detected
RTO: 30 minutes (deploy fix) + variable (recovery per workflow)
RPO: 0 (workflow state preserved, just stuck)
═══════════════════════════════════════════════════════════════

DETECTION:
  - Worker logs: "non-determinism detected" errors
  - Metric: temporal_workflow_task_execution_failed increasing
  - Affected workflows stuck (workflow task keeps failing and retrying)

DIAGNOSIS:

  1. Identify affected workflow type:
     $ kubectl logs -n temporal-workers -l app=temporal-worker --tail=500 | \
       grep "non-determinism" | jq -r '.workflowType' | sort | uniq -c

  2. Get error details:
     $ tctl workflow describe --workflow-id <affected-wf-id>
     # Look at pendingWorkflowTask - will show failure reason

  3. Download history and compare with code:
     $ tctl workflow show --workflow-id <affected-wf-id> \
       --output_filename /tmp/history.json
     
     # Run replay test locally to reproduce:
     $ go test ./... -run TestWorkflowReplay -v \
       -args -history=/tmp/history.json

COMMON CAUSES:
  - Removed/reordered activity calls without versioning
  - Changed signal/query handler registration order
  - Added side effects outside workflow.SideEffect()
  - Changed timer durations for in-flight workflows
  - Switched from activity to local activity (or vice versa)

FIX:

  1. Apply versioning to the workflow code:
     
     ```go
     func MyWorkflow(ctx workflow.Context, input Input) error {
         v := workflow.GetVersion(ctx, "fix-non-determinism-2024-01-15", 
             workflow.DefaultVersion, 1)
         
         if v == workflow.DefaultVersion {
             // Old behavior (for existing executions)
             err := workflow.ExecuteActivity(ctx, OldActivity, input).Get(ctx, nil)
         } else {
             // New behavior (for new executions)
             err := workflow.ExecuteActivity(ctx, NewActivity, input).Get(ctx, nil)
         }
         return err
     }
     ```

  2. Deploy the fix (standard rolling update):
     $ kubectl set image deployment/temporal-worker-default \
       worker=registry.company.com/workers:v1.2.4-hotfix \
       -n temporal-workers

  3. Verify fix - affected workflows should resume:
     $ tctl workflow list --query \
       "WorkflowType='MyWorkflow' AND ExecutionStatus='Running'" --limit 10
     # Workflows should be progressing again

  4. If workflows are still stuck (history corrupted beyond repair):
     # Reset to a point before the non-determinism
     $ tctl workflow reset --workflow-id <wf-id> \
       --reason "non-determinism recovery" \
       --reset-type LastWorkflowTask \
       --namespace production

BULK RECOVERY (if many workflows affected):

  ```go
  // reset_workflows.go - Bulk reset tool
  func resetAffectedWorkflows(ctx context.Context, c client.Client) error {
      iter, err := c.ListWorkflow(ctx, &client.ListWorkflowExecutionsRequest{
          Query: "WorkflowType='MyWorkflow' AND ExecutionStatus='Running' AND CustomKeywordField='stuck'",
      })
      
      for iter.HasNext() {
          wf, _ := iter.Next()
          _, err := c.ResetWorkflowExecution(ctx, &workflowservice.ResetWorkflowExecutionRequest{
              Namespace: "production",
              WorkflowExecution: &commonpb.WorkflowExecution{
                  WorkflowId: wf.Execution.WorkflowId,
                  RunId:      wf.Execution.RunId,
              },
              Reason:                "non-determinism bug fix",
              WorkflowTaskFinishEventId: findLastGoodEventId(wf),
          })
          if err != nil {
              log.Printf("Failed to reset %s: %v", wf.Execution.WorkflowId, err)
          }
      }
      return nil
  }
  ```

PREVENTION:
  - Mandatory replay tests in CI (test with production histories)
  - Code review checklist: workflow changes require versioning
  - Canary deployment catches non-determinism before full rollout

═══════════════════════════════════════════════════════════════
```

---

## Chaos Engineering

### Experiments Catalog

```yaml
# chaos-experiments.yaml - LitmusChaos experiments for Temporal

# Experiment 1: Kill random history pod
apiVersion: litmuschaos.io/v1alpha1
kind: ChaosEngine
metadata:
  name: temporal-history-pod-kill
  namespace: temporal
spec:
  engineState: active
  appinfo:
    appns: temporal
    applabel: app.kubernetes.io/component=history
    appkind: deployment
  chaosServiceAccount: litmus-admin
  experiments:
    - name: pod-delete
      spec:
        components:
          env:
            - name: TOTAL_CHAOS_DURATION
              value: "60"
            - name: CHAOS_INTERVAL
              value: "30"  # Kill a pod every 30s
            - name: FORCE
              value: "true"
            - name: PODS_AFFECTED_PERC
              value: "10"  # Kill 10% of pods
        probe:
          - name: "workflow-start-succeeds"
            type: cmdProbe
            mode: Continuous
            runProperties:
              probeTimeout: 10
              interval: 5
              retry: 3
            cmdProbe/inputs:
              command: |
                tctl workflow start --workflow-type HealthCheck \
                  --task-queue chaos-test --workflow-id "chaos-$(date +%s)"
              comparator:
                type: string
                criteria: contains
                value: "Started"

---
# Experiment 2: Network partition between history and database
apiVersion: litmuschaos.io/v1alpha1
kind: ChaosEngine
metadata:
  name: temporal-network-partition
  namespace: temporal
spec:
  engineState: active
  appinfo:
    appns: temporal
    applabel: app.kubernetes.io/component=history
  experiments:
    - name: pod-network-loss
      spec:
        components:
          env:
            - name: TOTAL_CHAOS_DURATION
              value: "120"
            - name: NETWORK_INTERFACE
              value: "eth0"
            - name: NETWORK_PACKET_LOSS_PERCENTAGE
              value: "100"
            - name: DESTINATION_IPS
              value: "cassandra-0.cassandra.temporal.svc.cluster.local"
            - name: PODS_AFFECTED_PERC
              value: "30"  # Partition 30% of history pods from DB

---
# Experiment 3: Database latency injection
apiVersion: litmuschaos.io/v1alpha1
kind: ChaosEngine
metadata:
  name: temporal-db-latency
  namespace: temporal
spec:
  experiments:
    - name: pod-network-latency
      spec:
        components:
          env:
            - name: TOTAL_CHAOS_DURATION
              value: "300"
            - name: NETWORK_LATENCY
              value: "500"  # 500ms additional latency
            - name: JITTER
              value: "200"  # ±200ms jitter
            - name: DESTINATION_IPS
              value: "cassandra-0.cassandra,cassandra-1.cassandra"
        probe:
          - name: "persistence-latency-check"
            type: promProbe
            mode: Continuous
            runProperties:
              probeTimeout: 10
              interval: 10
            promProbe/inputs:
              endpoint: "http://prometheus:9090"
              query: |
                histogram_quantile(0.99,
                  sum(rate(temporal_persistence_latency_bucket[1m])) by (le))
              comparator:
                type: float
                criteria: "<="
                value: "5"  # p99 should stay under 5s even with injection

---
# Experiment 4: Worker crash during activity execution
apiVersion: litmuschaos.io/v1alpha1
kind: ChaosEngine
metadata:
  name: temporal-worker-crash
  namespace: temporal-workers
spec:
  experiments:
    - name: pod-delete
      spec:
        components:
          env:
            - name: TOTAL_CHAOS_DURATION
              value: "600"  # 10 minutes of chaos
            - name: CHAOS_INTERVAL
              value: "60"   # Kill worker every 60s
            - name: FORCE
              value: "true"
            - name: PODS_AFFECTED_PERC
              value: "20"
        probe:
          - name: "workflows-complete-successfully"
            type: promProbe
            mode: Edge
            runProperties:
              probeTimeout: 30
              interval: 30
            promProbe/inputs:
              endpoint: "http://prometheus:9090"
              query: |
                rate(temporal_workflow_failed_total{namespace="chaos-test"}[5m])
                / rate(temporal_workflow_completed_total{namespace="chaos-test"}[5m])
              comparator:
                type: float
                criteria: "<="
                value: "0.01"  # < 1% failure rate even during chaos
```

### Game Day Runbook

```
═══════════════════════════════════════════════════════════════
GAME DAY: Temporal Resilience Verification
Schedule: Quarterly
Duration: 4 hours
Participants: Platform team + on-call SRE
═══════════════════════════════════════════════════════════════

PRE-GAME (30 min before):
  □ Notify stakeholders (not the on-call team - they should practice)
  □ Verify monitoring/alerting is active
  □ Confirm no critical deployments in progress
  □ Start background workload (constant workflow starts)
  □ Record baseline metrics

ROUND 1: Component Failure (45 min)
  □ Kill 1 history pod - verify shard redistribution (< 30s recovery)
  □ Kill all matching pods in 1 AZ - verify task dispatch continues
  □ Kill 50% of worker pods - verify HPA scales up
  □ Observation: Do alerts fire? Do runbooks work?

ROUND 2: Database Stress (45 min)
  □ Inject 200ms latency to all DB connections
  □ Observe: persistence_latency alerts fire?
  □ Increase to 2s latency - does Temporal degrade gracefully?
  □ Remove latency - does it recover automatically?

ROUND 3: Network Partition (30 min)
  □ Partition history from matching (block internal gRPC)
  □ Observe: which workflows are affected?
  □ Remove partition - do stuck workflows resume?

ROUND 4: Application Failure (30 min)
  □ Deploy a worker with a simulated non-determinism bug
  □ Observe: detection time? Alert fires?
  □ Execute runbook: version, deploy fix, reset workflows
  □ Verify recovery

ROUND 5: Full AZ Failure Simulation (30 min)
  □ Cordon all nodes in one AZ
  □ Delete all pods in that AZ
  □ Observe: automatic recovery, time to stabilize
  □ Uncordon AZ - verify rebalancing

POST-GAME (30 min):
  □ Review: what went well, what didn't
  □ Document any runbook improvements needed
  □ File tickets for any gaps found
  □ Update detection/alerting if blind spots found

SUCCESS CRITERIA:
  □ All alerts fired within expected timeframe
  □ Runbooks were sufficient to resolve issues
  □ No data loss during any experiment
  □ Recovery time within stated RTO for each scenario
  □ On-call team could handle without escalation

═══════════════════════════════════════════════════════════════
```

---

## Workflow Recovery Patterns

### Reset Workflow

```go
// reset.go - Workflow reset utilities
package recovery

import (
	"context"
	"fmt"
	"log"

	"go.temporal.io/api/enums/v1"
	"go.temporal.io/api/workflowservice/v1"
	"go.temporal.io/sdk/client"
)

// ResetWorkflow resets a workflow to a specific point in history
func ResetWorkflow(ctx context.Context, c client.Client, opts ResetOptions) error {
	// Find the event ID to reset to
	eventID, err := findResetPoint(ctx, c, opts)
	if err != nil {
		return fmt.Errorf("finding reset point: %w", err)
	}

	log.Printf("Resetting workflow %s to event %d (reason: %s)",
		opts.WorkflowID, eventID, opts.Reason)

	_, err = c.WorkflowService().ResetWorkflowExecution(ctx,
		&workflowservice.ResetWorkflowExecutionRequest{
			Namespace: opts.Namespace,
			WorkflowExecution: &common.WorkflowExecution{
				WorkflowId: opts.WorkflowID,
				RunId:      opts.RunID,
			},
			Reason:                    opts.Reason,
			WorkflowTaskFinishEventId: eventID,
			RequestId:                 fmt.Sprintf("reset-%s-%d", opts.WorkflowID, eventID),
		})
	if err != nil {
		return fmt.Errorf("reset failed: %w", err)
	}

	log.Printf("Workflow %s reset successfully", opts.WorkflowID)
	return nil
}

type ResetOptions struct {
	Namespace  string
	WorkflowID string
	RunID      string
	Reason     string
	ResetType  string // "LastWorkflowTask", "FirstWorkflowTask", "BadBinary"
}

func findResetPoint(ctx context.Context, c client.Client, opts ResetOptions) (int64, error) {
	iter := c.GetWorkflowHistory(ctx, opts.WorkflowID, opts.RunID, false, enums.HISTORY_EVENT_FILTER_TYPE_ALL_EVENT)

	var lastGoodWFTaskCompleted int64
	
	for iter.HasNext() {
		event, err := iter.Next()
		if err != nil {
			return 0, err
		}

		switch opts.ResetType {
		case "LastWorkflowTask":
			if event.GetEventType() == enums.EVENT_TYPE_WORKFLOW_TASK_COMPLETED {
				lastGoodWFTaskCompleted = event.GetEventId()
			}
		case "FirstWorkflowTask":
			if event.GetEventType() == enums.EVENT_TYPE_WORKFLOW_TASK_COMPLETED {
				return event.GetEventId(), nil
			}
		}
	}

	if lastGoodWFTaskCompleted == 0 {
		return 0, fmt.Errorf("no suitable reset point found")
	}
	return lastGoodWFTaskCompleted, nil
}

// BulkResetByQuery resets all workflows matching a visibility query
func BulkResetByQuery(ctx context.Context, c client.Client, namespace, query, reason string) (int, int, error) {
	iter, err := c.ListWorkflow(ctx, &client.ListWorkflowExecutionsRequest{
		Namespace: namespace,
		Query:     query,
	})
	if err != nil {
		return 0, 0, err
	}

	var success, failed int
	for iter.HasNext() {
		wf, err := iter.Next()
		if err != nil {
			failed++
			continue
		}

		err = ResetWorkflow(ctx, c, ResetOptions{
			Namespace:  namespace,
			WorkflowID: wf.Execution.WorkflowId,
			RunID:      wf.Execution.RunId,
			Reason:     reason,
			ResetType:  "LastWorkflowTask",
		})
		if err != nil {
			log.Printf("Failed to reset %s: %v", wf.Execution.WorkflowId, err)
			failed++
		} else {
			success++
		}
	}

	return success, failed, nil
}
```

---

## Resilience Patterns in Code

### Circuit Breaker in Activities

```go
// circuit_breaker.go - Circuit breaker for external service calls
package activities

import (
	"context"
	"fmt"
	"time"

	"github.com/sony/gobreaker/v2"
)

// ServiceCircuitBreakers manages circuit breakers per downstream service
type ServiceCircuitBreakers struct {
	breakers map[string]*gobreaker.CircuitBreaker[[]byte]
}

func NewServiceCircuitBreakers() *ServiceCircuitBreakers {
	scb := &ServiceCircuitBreakers{
		breakers: make(map[string]*gobreaker.CircuitBreaker[[]byte]),
	}

	// Payment service - conservative (financial operations)
	scb.breakers["payment-service"] = gobreaker.NewCircuitBreaker[[]byte](gobreaker.Settings{
		Name:        "payment-service",
		MaxRequests: 3,                    // Allow 3 requests in half-open state
		Interval:    60 * time.Second,     // Reset failure count every 60s
		Timeout:     30 * time.Second,     // Stay open for 30s before half-open
		ReadyToTrip: func(counts gobreaker.Counts) bool {
			failureRatio := float64(counts.TotalFailures) / float64(counts.Requests)
			return counts.Requests >= 10 && failureRatio >= 0.5 // 50% failure rate
		},
		OnStateChange: func(name string, from, to gobreaker.State) {
			slog.Warn("Circuit breaker state change",
				"service", name,
				"from", from.String(),
				"to", to.String(),
			)
			// Emit metric
			CircuitBreakerStateGauge.WithLabelValues(name, to.String()).Set(1)
		},
	})

	// Email service - more lenient
	scb.breakers["email-service"] = gobreaker.NewCircuitBreaker[[]byte](gobreaker.Settings{
		Name:        "email-service",
		MaxRequests: 5,
		Interval:    30 * time.Second,
		Timeout:     15 * time.Second,
		ReadyToTrip: func(counts gobreaker.Counts) bool {
			return counts.ConsecutiveFailures >= 10
		},
	})

	return scb
}

// CallWithBreaker wraps an external call with circuit breaker
func (scb *ServiceCircuitBreakers) CallWithBreaker(
	ctx context.Context,
	service string,
	fn func(ctx context.Context) ([]byte, error),
) ([]byte, error) {
	cb, ok := scb.breakers[service]
	if !ok {
		return fn(ctx)
	}

	result, err := cb.Execute(func() ([]byte, error) {
		return fn(ctx)
	})
	if err != nil {
		if err == gobreaker.ErrOpenState {
			return nil, fmt.Errorf("circuit breaker OPEN for %s: service unavailable", service)
		}
		return nil, err
	}
	return result, nil
}

// Activity using circuit breaker
func (a *Activities) ChargePayment(ctx context.Context, req PaymentRequest) (*PaymentResult, error) {
	resultBytes, err := a.circuitBreakers.CallWithBreaker(ctx, "payment-service",
		func(ctx context.Context) ([]byte, error) {
			return a.paymentClient.Charge(ctx, req)
		},
	)
	if err != nil {
		// If circuit is open, return a retryable error
		// Temporal will retry based on retry policy
		return nil, fmt.Errorf("payment service call failed: %w", err)
	}

	var result PaymentResult
	json.Unmarshal(resultBytes, &result)
	return &result, nil
}
```

### Bulkhead Pattern (Activity Isolation)

```go
// bulkhead.go - Resource isolation between activity types
package activities

import (
	"context"
	"fmt"
	"time"

	"golang.org/x/sync/semaphore"
)

// BulkheadManager provides per-service concurrency limits
type BulkheadManager struct {
	semaphores map[string]*semaphore.Weighted
}

func NewBulkheadManager() *BulkheadManager {
	return &BulkheadManager{
		semaphores: map[string]*semaphore.Weighted{
			"database":       semaphore.NewWeighted(50),   // Max 50 concurrent DB calls
			"payment-api":    semaphore.NewWeighted(20),   // Max 20 concurrent payment calls
			"email-service":  semaphore.NewWeighted(100),  // Max 100 concurrent emails
			"s3-upload":      semaphore.NewWeighted(30),   // Max 30 concurrent uploads
			"ml-inference":   semaphore.NewWeighted(5),    // Max 5 concurrent ML calls (expensive)
		},
	}
}

// Acquire acquires a slot in the named bulkhead
func (bm *BulkheadManager) Acquire(ctx context.Context, name string) error {
	sem, ok := bm.semaphores[name]
	if !ok {
		return nil // No limit configured
	}

	// Add timeout to prevent indefinite blocking
	timeoutCtx, cancel := context.WithTimeout(ctx, 30*time.Second)
	defer cancel()

	if err := sem.Acquire(timeoutCtx, 1); err != nil {
		return fmt.Errorf("bulkhead %s exhausted (all slots busy): %w", name, err)
	}
	return nil
}

// Release releases a slot
func (bm *BulkheadManager) Release(name string) {
	if sem, ok := bm.semaphores[name]; ok {
		sem.Release(1)
	}
}

// Usage in activity:
func (a *Activities) ProcessOrder(ctx context.Context, order Order) error {
	// Acquire database bulkhead
	if err := a.bulkhead.Acquire(ctx, "database"); err != nil {
		return err  // Will be retried
	}
	defer a.bulkhead.Release("database")

	// Database operations here...
	return a.db.SaveOrder(ctx, order)
}
```

### Timeout Hierarchy and Deadline Propagation

```go
// timeouts.go - Proper timeout hierarchy for Temporal workflows
package workflows

import (
	"time"

	"go.temporal.io/sdk/temporal"
	"go.temporal.io/sdk/workflow"
)

/*
TIMEOUT HIERARCHY (must be: outer > inner):

WorkflowExecutionTimeout (entire workflow)
  └── WorkflowRunTimeout (single run, before ContinueAsNew)
       └── WorkflowTaskTimeout (single decision task, default 10s)

ActivityScheduleToCloseTimeout (total time for activity)
  ├── ActivityScheduleToStartTimeout (time waiting in queue)
  └── ActivityStartToCloseTimeout (time for execution)
       └── ActivityHeartbeatTimeout (time between heartbeats)

RULES:
1. ScheduleToClose >= ScheduleToStart + StartToClose
2. HeartbeatTimeout < StartToClose
3. Activity timeout < Workflow timeout (obvious but often violated)
4. Leave headroom for retries: total_time = timeout * max_attempts
*/

func OrderWorkflowWithProperTimeouts(ctx workflow.Context, order Order) error {
	// Workflow-level: entire order must complete in 1 hour
	// (Set at start time, not here - this is informational)
	// WorkflowExecutionTimeout: 1 hour

	// Payment: critical path, must be fast
	paymentCtx := workflow.WithActivityOptions(ctx, workflow.ActivityOptions{
		StartToCloseTimeout:    30 * time.Second,
		ScheduleToStartTimeout: 10 * time.Second,  // If no worker in 10s, something's wrong
		HeartbeatTimeout:       5 * time.Second,
		RetryPolicy: &temporal.RetryPolicy{
			InitialInterval:    1 * time.Second,
			BackoffCoefficient: 2.0,
			MaximumInterval:    30 * time.Second,
			MaximumAttempts:    3,
			// Total time: 30s * 3 = 90s worst case
		},
		// WaitForCancellation: if workflow cancels, wait for payment to confirm
		WaitForCancellation: true,
	})

	var paymentResult PaymentResult
	err := workflow.ExecuteActivity(paymentCtx, ChargePayment, order.Payment).Get(ctx, &paymentResult)
	if err != nil {
		return err
	}

	// Fulfillment: can take longer, less critical
	fulfillCtx := workflow.WithActivityOptions(ctx, workflow.ActivityOptions{
		StartToCloseTimeout:    5 * time.Minute,
		ScheduleToStartTimeout: 30 * time.Second,
		HeartbeatTimeout:       30 * time.Second,  // Long-running, heartbeat every 30s
		RetryPolicy: &temporal.RetryPolicy{
			InitialInterval:    5 * time.Second,
			BackoffCoefficient: 2.0,
			MaximumInterval:    2 * time.Minute,
			MaximumAttempts:    5,
			NonRetryableErrorTypes: []string{"FulfillmentImpossibleError"},
		},
	})

	return workflow.ExecuteActivity(fulfillCtx, FulfillOrder, order, paymentResult).Get(ctx, nil)
}
```

---

## SLA Management

### SLO Definitions

```yaml
# slo-definitions.yaml - Temporal Platform SLOs
apiVersion: sloth.slok.dev/v1
kind: PrometheusServiceLevel
metadata:
  name: temporal-platform-slos
spec:
  service: "temporal-platform"
  labels:
    team: platform
    tier: "0"
  slos:
    # SLO 1: Workflow operations availability
    - name: "workflow-operations-availability"
      objective: 99.99  # Four nines
      description: "Workflow start, signal, query operations succeed"
      sli:
        events:
          errorQuery: |
            sum(rate(temporal_service_errors_total{
              operation=~"StartWorkflowExecution|SignalWorkflowExecution|QueryWorkflow"
            }[{{.window}}]))
          totalQuery: |
            sum(rate(temporal_service_requests_total{
              operation=~"StartWorkflowExecution|SignalWorkflowExecution|QueryWorkflow"
            }[{{.window}}]))
      alerting:
        name: TemporalAvailabilitySLOBreach
        labels:
          severity: critical
        annotations:
          summary: "Temporal availability SLO at risk"
        pageAlert:
          labels:
            severity: critical
        ticketAlert:
          labels:
            severity: warning

    # SLO 2: Schedule-to-start latency
    - name: "schedule-to-start-latency"
      objective: 99.9  # Three nines
      description: "99.9% of workflow tasks start within 5 seconds"
      sli:
        events:
          errorQuery: |
            sum(rate(temporal_workflow_task_schedule_to_start_latency_bucket{le="5"}[{{.window}}]))
            -
            sum(rate(temporal_workflow_task_schedule_to_start_latency_bucket{le="+Inf"}[{{.window}}]))
          totalQuery: |
            sum(rate(temporal_workflow_task_schedule_to_start_latency_bucket{le="+Inf"}[{{.window}}]))

    # SLO 3: Persistence latency
    - name: "persistence-latency"
      objective: 99.95
      description: "Database operations complete within 500ms"
      sli:
        events:
          errorQuery: |
            sum(rate(temporal_persistence_latency_bucket{le="0.5"}[{{.window}}]))
            -
            sum(rate(temporal_persistence_latency_bucket{le="+Inf"}[{{.window}}]))
          totalQuery: |
            sum(rate(temporal_persistence_latency_bucket{le="+Inf"}[{{.window}}]))
```

### Error Budget Tracking

```
═══════════════════════════════════════════════════════════════
ERROR BUDGET DASHBOARD (30-day rolling window)
═══════════════════════════════════════════════════════════════

SLO: 99.99% availability (workflow operations)
  Budget: 4.32 minutes of downtime per 30 days
  Consumed: 1.2 minutes (28% of budget)
  Remaining: 3.12 minutes (72% of budget)
  Status: ✅ HEALTHY

SLO: 99.9% schedule-to-start < 5s
  Budget: 43.2 minutes of violation per 30 days
  Consumed: 12.5 minutes (29% of budget)  
  Remaining: 30.7 minutes (71% of budget)
  Status: ✅ HEALTHY

SLO: 99.95% persistence < 500ms
  Budget: 21.6 minutes of violation per 30 days
  Consumed: 18.2 minutes (84% of budget)
  Remaining: 3.4 minutes (16% of budget)
  Status: ⚠️ AT RISK - investigate database performance

POLICIES:
  Budget > 50% remaining: Normal development velocity
  Budget 25-50% remaining: Reduce risky changes
  Budget < 25% remaining: Freeze non-critical changes, focus on reliability
  Budget exhausted: All hands on reliability until budget recovers

═══════════════════════════════════════════════════════════════
```

### Incident Classification

```
┌──────────┬────────────────────────────────────────────────────────────────┐
│ Severity │ Criteria                                                       │
├──────────┼────────────────────────────────────────────────────────────────┤
│ SEV-1    │ Complete Temporal platform outage                              │
│          │ All workflows unable to progress                              │
│          │ Data loss confirmed                                           │
│          │ Response: 5 min, Bridge: 15 min, Resolution: 1 hour target   │
├──────────┼────────────────────────────────────────────────────────────────┤
│ SEV-2    │ Partial outage (one namespace, one task queue)                │
│          │ Significant degradation (latency > 10x normal)               │
│          │ Error budget at risk of exhaustion                            │
│          │ Response: 15 min, Resolution: 4 hour target                  │
├──────────┼────────────────────────────────────────────────────────────────┤
│ SEV-3    │ Minor degradation (elevated latency, increased errors)        │
│          │ Non-production environment outage                             │
│          │ Single workflow type affected                                 │
│          │ Response: 1 hour, Resolution: next business day              │
├──────────┼────────────────────────────────────────────────────────────────┤
│ SEV-4    │ Cosmetic issues, monitoring gaps                              │
│          │ Performance optimization opportunities                        │
│          │ Response: next business day, Resolution: sprint planning      │
└──────────┴────────────────────────────────────────────────────────────────┘
```

### Post-Incident Review Template

```markdown
# Post-Incident Review: [Title]

## Summary
- **Date/Time:** YYYY-MM-DD HH:MM - HH:MM UTC
- **Duration:** X hours Y minutes
- **Severity:** SEV-X
- **Impact:** [Number of affected workflows, users, revenue impact]
- **Error budget consumed:** X minutes (Y% of monthly budget)

## Timeline
| Time (UTC) | Event |
|------------|-------|
| HH:MM | First alert fired |
| HH:MM | On-call acknowledged |
| HH:MM | Root cause identified |
| HH:MM | Mitigation applied |
| HH:MM | Service fully recovered |
| HH:MM | Incident resolved |

## Root Cause
[Technical description of what caused the incident]

## Detection
- How was the incident detected? (alert/customer report/manual observation)
- Detection latency: time from failure to first alert
- Were the right people notified?

## Response
- What actions were taken?
- What worked well?
- What could have been faster?

## Impact
- Workflows affected: [count]
- Failed workflows: [count]
- Data loss: [yes/no, details]
- Revenue impact: [$]
- Customer-facing: [yes/no]

## Action Items
| Priority | Action | Owner | Due Date |
|----------|--------|-------|----------|
| P1 | [Fix root cause] | @engineer | YYYY-MM-DD |
| P2 | [Improve detection] | @sre | YYYY-MM-DD |
| P3 | [Update runbook] | @oncall | YYYY-MM-DD |

## Lessons Learned
1. [Key insight 1]
2. [Key insight 2]
3. [Key insight 3]
```

---

## Summary: DR Readiness Checklist

### Must Have (Before Production)
- [ ] Multi-AZ deployment with anti-affinity
- [ ] Database replication (RF=3 minimum)
- [ ] Automated backups (verified monthly)
- [ ] PDB on all critical components
- [ ] Runbooks for top-5 failure scenarios
- [ ] On-call rotation with escalation path
- [ ] Activity idempotency for all side effects

### Should Have (Within 3 Months)
- [ ] Multi-cluster replication for critical namespaces
- [ ] Automated failover procedures (scripted)
- [ ] Chaos engineering experiments running monthly
- [ ] Error budget tracking and policies
- [ ] Bulk workflow reset tooling
- [ ] Non-determinism detection in CI

### Nice to Have (Mature Operations)
- [ ] Automated region failover (no human intervention)
- [ ] Continuous chaos (always running in staging)
- [ ] ML-based anomaly detection
- [ ] Automated capacity scaling based on forecasting
- [ ] Cross-team game days
- [ ] Formal SLA with internal customers
