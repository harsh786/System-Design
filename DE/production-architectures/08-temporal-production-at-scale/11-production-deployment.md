# Production Deployment Guide — Temporal at Scale

## Table of Contents
1. [Deployment Options](#deployment-options)
2. [Kubernetes Deployment](#kubernetes-deployment-complete)
3. [Database Setup](#database-setup)
4. [Elasticsearch/OpenSearch Setup](#elasticsearchopensearch-setup)
5. [Worker Deployment](#worker-deployment)
6. [Network Configuration](#network-configuration)
7. [Configuration Management](#configuration-management)
8. [CI/CD Pipeline](#cicd-pipeline)
9. [Security](#security)

---

## Deployment Options

### Decision Matrix

| Criteria | Self-Hosted (K8s) | Temporal Cloud | Hybrid |
|----------|-------------------|----------------|--------|
| Control | Full | Limited | Mixed |
| Operational burden | High | None | Medium |
| Cost at scale | Lower (>10K WF/s) | Higher | Optimized |
| Multi-region | Manual | Built-in | Both |
| Compliance | Full control | SOC2/HIPAA | Flexible |
| Time to production | Weeks | Hours | Days |

### When to Self-Host
- Regulatory requirements (data residency, air-gapped environments)
- Scale exceeding 50K workflow starts/second (cost optimization)
- Custom persistence backends
- Deep integration with existing infrastructure

### When to Use Temporal Cloud
- Teams < 20 engineers using Temporal
- Rapid time-to-value needed
- No dedicated platform/SRE team for Temporal
- Multi-region out of the box

### Hybrid Architecture
```
┌─────────────────────────────────────────────────────────┐
│                    Production Traffic                      │
├─────────────────────┬───────────────────────────────────┤
│  Temporal Cloud     │     Self-Hosted Cluster            │
│  (namespace: prod)  │     (namespace: batch-processing)  │
│                     │     (namespace: data-pipelines)    │
│  - Critical paths   │     - High-volume batch            │
│  - Low-latency      │     - Cost-sensitive               │
│  - SLA-backed       │     - Custom requirements          │
└─────────────────────┴───────────────────────────────────┘
```

---

## Kubernetes Deployment (Complete)

### Architecture Overview

```
┌──────────────────────────────────────────────────────────────────┐
│                         Kubernetes Cluster                         │
│                                                                    │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │  Frontend   │  │  Frontend   │  │  Frontend   │              │
│  │  (gRPC LB)  │  │  (gRPC LB)  │  │  (gRPC LB)  │              │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘              │
│         │                 │                 │                      │
│  ┌──────┴─────────────────┴─────────────────┴──────┐             │
│  │              Internal gRPC Mesh                    │             │
│  └──────┬─────────────────┬─────────────────┬──────┘             │
│         │                 │                 │                      │
│  ┌──────┴──────┐  ┌──────┴──────┐  ┌──────┴──────┐              │
│  │   History   │  │  Matching   │  │   Worker    │              │
│  │  (6 pods)   │  │  (4 pods)   │  │  (2 pods)   │              │
│  └──────┬──────┘  └──────┬──────┘  └─────────────┘              │
│         │                 │                                        │
│  ┌──────┴─────────────────┴──────────────────────┐               │
│  │              Persistence Layer                   │               │
│  │  ┌────────────┐  ┌─────────────────────────┐  │               │
│  │  │ Cassandra  │  │  Elasticsearch/OpenSearch│  │               │
│  │  │ (6 nodes)  │  │  (3 master + 6 data)    │  │               │
│  │  └────────────┘  └─────────────────────────┘  │               │
│  └────────────────────────────────────────────────┘               │
└──────────────────────────────────────────────────────────────────┘
```

### Helm Chart Configuration — Complete Production values.yaml

```yaml
# File: temporal-production-values.yaml
# Temporal Helm Chart Production Configuration
# Chart version: 0.45.0+ (temporal-helm-charts)

global:
  image:
    tag: 1.24.2  # Pin to specific version, never use 'latest'

server:
  image:
    repository: temporalio/server
    tag: 1.24.2
    pullPolicy: IfNotPresent

  config:
    persistence:
      default:
        driver: cassandra
        cassandra:
          hosts: "cassandra-0.cassandra.temporal.svc.cluster.local,cassandra-1.cassandra.temporal.svc.cluster.local,cassandra-2.cassandra.temporal.svc.cluster.local"
          port: 9042
          keyspace: temporal
          user: temporal_user
          existingSecret: temporal-cassandra-credentials
          consistency:
            default:
              consistency: local_quorum
              serialConsistency: local_serial
          connectTimeout: 10s
          timeout: 10s
          numHistoryShards: 512  # CRITICAL: Cannot change after deployment
          maxConns: 20
          tls:
            enabled: true
            certFile: /etc/temporal/cassandra-tls/tls.crt
            keyFile: /etc/temporal/cassandra-tls/tls.key
            caFile: /etc/temporal/cassandra-tls/ca.crt
            enableHostVerification: true

      visibility:
        driver: elasticsearch
        elasticsearch:
          version: v7
          url:
            scheme: https
            host: "elasticsearch-master.temporal.svc.cluster.local:9200"
          username: temporal_visibility
          existingSecret: temporal-es-credentials
          indices:
            visibility: temporal_visibility_v1
          closeIdleConnectionsInterval: 15s
          tls:
            enabled: true
            caFile: /etc/temporal/es-tls/ca.crt

  # Frontend Service Configuration
  frontend:
    replicaCount: 3
    resources:
      requests:
        cpu: "2"
        memory: "4Gi"
      limits:
        cpu: "4"
        memory: "8Gi"
    
    service:
      type: ClusterIP
      port: 7233
      annotations:
        service.beta.kubernetes.io/aws-load-balancer-type: "nlb"
        service.beta.kubernetes.io/aws-load-balancer-cross-zone-load-balancing-enabled: "true"
    
    podAnnotations:
      prometheus.io/scrape: "true"
      prometheus.io/port: "9090"
    
    autoscaling:
      enabled: true
      minReplicas: 3
      maxReplicas: 10
      targetCPUUtilizationPercentage: 70
      targetMemoryUtilizationPercentage: 75
      behavior:
        scaleUp:
          stabilizationWindowSeconds: 60
          policies:
            - type: Pods
              value: 2
              periodSeconds: 60
        scaleDown:
          stabilizationWindowSeconds: 300
          policies:
            - type: Pods
              value: 1
              periodSeconds: 120
    
    podDisruptionBudget:
      enabled: true
      minAvailable: 2
    
    affinity:
      podAntiAffinity:
        requiredDuringSchedulingIgnoredDuringExecution:
          - labelSelector:
              matchExpressions:
                - key: app.kubernetes.io/component
                  operator: In
                  values:
                    - frontend
            topologyKey: kubernetes.io/hostname
        preferredDuringSchedulingIgnoredDuringExecution:
          - weight: 100
            podAffinityTerm:
              labelSelector:
                matchExpressions:
                  - key: app.kubernetes.io/component
                    operator: In
                    values:
                      - frontend
              topologyKey: topology.kubernetes.io/zone
    
    topologySpreadConstraints:
      - maxSkew: 1
        topologyKey: topology.kubernetes.io/zone
        whenUnsatisfiable: DoNotSchedule
        labelSelector:
          matchLabels:
            app.kubernetes.io/component: frontend
    
    nodeSelector:
      node-role: temporal
      node-class: general
    
    tolerations:
      - key: "dedicated"
        operator: "Equal"
        value: "temporal"
        effect: "NoSchedule"

  # History Service Configuration (MOST CRITICAL)
  history:
    replicaCount: 6
    resources:
      requests:
        cpu: "4"
        memory: "8Gi"
      limits:
        cpu: "8"
        memory: "16Gi"
    
    autoscaling:
      enabled: true
      minReplicas: 6
      maxReplicas: 20
      targetCPUUtilizationPercentage: 60  # Lower threshold - history is latency-sensitive
      targetMemoryUtilizationPercentage: 70
      behavior:
        scaleUp:
          stabilizationWindowSeconds: 30  # Scale up quickly
          policies:
            - type: Pods
              value: 3
              periodSeconds: 30
        scaleDown:
          stabilizationWindowSeconds: 600  # Scale down slowly
          policies:
            - type: Pods
              value: 1
              periodSeconds: 180
    
    podDisruptionBudget:
      enabled: true
      maxUnavailable: 1  # Strict for history
    
    affinity:
      podAntiAffinity:
        requiredDuringSchedulingIgnoredDuringExecution:
          - labelSelector:
              matchExpressions:
                - key: app.kubernetes.io/component
                  operator: In
                  values:
                    - history
            topologyKey: kubernetes.io/hostname
        preferredDuringSchedulingIgnoredDuringExecution:
          - weight: 100
            podAffinityTerm:
              labelSelector:
                matchExpressions:
                  - key: app.kubernetes.io/component
                    operator: In
                    values:
                      - history
              topologyKey: topology.kubernetes.io/zone
    
    topologySpreadConstraints:
      - maxSkew: 1
        topologyKey: topology.kubernetes.io/zone
        whenUnsatisfiable: DoNotSchedule
        labelSelector:
          matchLabels:
            app.kubernetes.io/component: history
    
    nodeSelector:
      node-role: temporal
      node-class: high-memory  # History benefits from more memory for caching
    
    tolerations:
      - key: "dedicated"
        operator: "Equal"
        value: "temporal-history"
        effect: "NoSchedule"

  # Matching Service Configuration
  matching:
    replicaCount: 4
    resources:
      requests:
        cpu: "2"
        memory: "4Gi"
      limits:
        cpu: "4"
        memory: "8Gi"
    
    autoscaling:
      enabled: true
      minReplicas: 4
      maxReplicas: 12
      targetCPUUtilizationPercentage: 65
      targetMemoryUtilizationPercentage: 70
    
    podDisruptionBudget:
      enabled: true
      minAvailable: 3
    
    affinity:
      podAntiAffinity:
        requiredDuringSchedulingIgnoredDuringExecution:
          - labelSelector:
              matchExpressions:
                - key: app.kubernetes.io/component
                  operator: In
                  values:
                    - matching
            topologyKey: kubernetes.io/hostname

  # Internal Worker Configuration
  worker:
    replicaCount: 2
    resources:
      requests:
        cpu: "1"
        memory: "2Gi"
      limits:
        cpu: "2"
        memory: "4Gi"
    
    podDisruptionBudget:
      enabled: true
      minAvailable: 1

# Prometheus monitoring
prometheus:
  enabled: true
  nodeExporter:
    enabled: false

# Grafana dashboards
grafana:
  enabled: true
  dashboardProviders:
    dashboardproviders.yaml:
      apiVersion: 1
      providers:
        - name: temporal
          orgId: 1
          folder: Temporal
          type: file
          disableDeletion: false
          editable: true
          options:
            path: /var/lib/grafana/dashboards/temporal

# Elasticsearch (if deploying within same chart)
elasticsearch:
  enabled: false  # We manage ES separately for production

# Cassandra (if deploying within same chart)
cassandra:
  enabled: false  # We manage Cassandra separately for production
```

### Component Sizing Reference Table

```
┌────────────┬──────────┬─────┬────────┬──────────────────────────────────────┐
│ Component  │ Replicas │ CPU │ Memory │ Notes                                │
├────────────┼──────────┼─────┼────────┼──────────────────────────────────────┤
│ Frontend   │ 3-10     │ 2-4 │ 4-8GB  │ Scales with client connections       │
│ History    │ 6-20     │ 4-8 │ 8-16GB │ Most critical, scales with workflows │
│ Matching   │ 4-12     │ 2-4 │ 4-8GB  │ Scales with task dispatch rate       │
│ Worker     │ 2-4      │ 1-2 │ 2-4GB  │ Internal workers (archival, etc.)    │
│ Cassandra  │ 6+       │ 8   │ 32GB   │ 3+ per DC, NVMe SSDs required       │
│ ES Master  │ 3        │ 2   │ 4GB    │ Dedicated master nodes               │
│ ES Data    │ 6+       │ 8   │ 32GB   │ SSD storage, scale with retention    │
└────────────┴──────────┴─────┴────────┴──────────────────────────────────────┘
```

---

## Database Setup

### Cassandra Schema and Configuration

#### Cassandra Cluster Configuration (cassandra.yaml excerpts)

```yaml
# cassandra.yaml - Production configuration for Temporal
cluster_name: 'temporal-production'
num_tokens: 256
allocate_tokens_for_local_replication_factor: 3

# Storage
data_file_directories:
  - /var/lib/cassandra/data  # NVMe SSD mount
commitlog_directory: /var/lib/cassandra/commitlog  # Separate NVMe
saved_caches_directory: /var/lib/cassandra/saved_caches

# Memory
memtable_allocation_type: offheap_objects
memtable_heap_space_in_mb: 2048
memtable_offheap_space_in_mb: 2048

# Compaction
compaction_throughput_mb_per_sec: 128
concurrent_compactors: 4

# Networking
listen_address: # Pod IP
rpc_address: 0.0.0.0
broadcast_rpc_address: # Pod IP
native_transport_port: 9042

# Consistency
endpoint_snitch: GossipingPropertyFileSnitch
request_timeout_in_ms: 10000
read_request_timeout_in_ms: 5000
write_request_timeout_in_ms: 2000

# GC (G1GC recommended)
# Set in jvm.options:
# -Xms16G -Xmx16G
# -XX:+UseG1GC
# -XX:G1RSetUpdatingPauseTimePercent=5
# -XX:MaxGCPauseMillis=300

# TLS
client_encryption_options:
  enabled: true
  optional: false
  keystore: /etc/cassandra/tls/keystore.jks
  keystore_password: ${KEYSTORE_PASSWORD}
  truststore: /etc/cassandra/tls/truststore.jks
  truststore_password: ${TRUSTSTORE_PASSWORD}
  protocol: TLS
  algorithm: SunX509
  cipher_suites:
    - TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384
    - TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256

server_encryption_options:
  internode_encryption: all
  keystore: /etc/cassandra/tls/keystore.jks
  keystore_password: ${KEYSTORE_PASSWORD}
  truststore: /etc/cassandra/tls/truststore.jks
  truststore_password: ${TRUSTSTORE_PASSWORD}
```

#### Temporal Cassandra Keyspace Setup

```sql
-- Create keyspace for Temporal (NetworkTopologyStrategy for multi-DC)
CREATE KEYSPACE IF NOT EXISTS temporal
WITH replication = {
  'class': 'NetworkTopologyStrategy',
  'us-east-1': 3,
  'us-west-2': 3
}
AND durable_writes = true;

-- Create visibility keyspace
CREATE KEYSPACE IF NOT EXISTS temporal_visibility
WITH replication = {
  'class': 'NetworkTopologyStrategy',
  'us-east-1': 3,
  'us-west-2': 3
}
AND durable_writes = true;
```

#### Schema Migrations

```bash
#!/bin/bash
# schema-migration.sh - Run Temporal schema migrations
set -euo pipefail

TEMPORAL_VERSION="1.24.2"
CASSANDRA_HOSTS="cassandra-0.cassandra.temporal.svc.cluster.local"
CASSANDRA_PORT=9042
CASSANDRA_USER="temporal_admin"
CASSANDRA_KEYSPACE="temporal"
VISIBILITY_KEYSPACE="temporal_visibility"

# Download schema tool
SCHEMA_DIR="/tmp/temporal-schema"
mkdir -p "${SCHEMA_DIR}"

# Run default schema migration
temporal-cassandra-tool \
  --ep "${CASSANDRA_HOSTS}" \
  --port "${CASSANDRA_PORT}" \
  --user "${CASSANDRA_USER}" \
  --password "${CASSANDRA_PASSWORD}" \
  --keyspace "${CASSANDRA_KEYSPACE}" \
  --tls \
  --tls-ca-file /etc/temporal/cassandra-tls/ca.crt \
  --tls-cert-file /etc/temporal/cassandra-tls/tls.crt \
  --tls-key-file /etc/temporal/cassandra-tls/tls.key \
  update-schema \
  --schema-dir "/temporal/schema/cassandra/temporal/versioned" \
  --target-version "${TEMPORAL_VERSION}"

# Run visibility schema migration
temporal-cassandra-tool \
  --ep "${CASSANDRA_HOSTS}" \
  --port "${CASSANDRA_PORT}" \
  --user "${CASSANDRA_USER}" \
  --password "${CASSANDRA_PASSWORD}" \
  --keyspace "${VISIBILITY_KEYSPACE}" \
  --tls \
  --tls-ca-file /etc/temporal/cassandra-tls/ca.crt \
  --tls-cert-file /etc/temporal/cassandra-tls/tls.crt \
  --tls-key-file /etc/temporal/cassandra-tls/tls.key \
  update-schema \
  --schema-dir "/temporal/schema/cassandra/visibility/versioned" \
  --target-version "${TEMPORAL_VERSION}"

echo "Schema migration completed successfully"
```

### PostgreSQL Setup with Connection Pooling

#### PostgreSQL Configuration (postgresql.conf excerpts)

```ini
# postgresql.conf - Optimized for Temporal workload
# Connection Settings
max_connections = 200  # PgBouncer handles pooling, keep this moderate
superuser_reserved_connections = 5

# Memory
shared_buffers = 8GB           # 25% of RAM
effective_cache_size = 24GB    # 75% of RAM
work_mem = 64MB
maintenance_work_mem = 2GB
wal_buffers = 64MB

# Write-Ahead Log
wal_level = replica
max_wal_size = 4GB
min_wal_size = 1GB
checkpoint_completion_target = 0.9
checkpoint_timeout = 15min

# Query Planning
random_page_cost = 1.1  # SSD storage
effective_io_concurrency = 200
default_statistics_target = 100

# Replication
max_wal_senders = 10
wal_keep_size = 2GB
synchronous_commit = on
synchronous_standby_names = 'ANY 1 (standby1, standby2)'

# Autovacuum (critical for Temporal's high-churn tables)
autovacuum_max_workers = 6
autovacuum_naptime = 10s
autovacuum_vacuum_threshold = 50
autovacuum_vacuum_scale_factor = 0.02  # More aggressive than default
autovacuum_analyze_threshold = 50
autovacuum_analyze_scale_factor = 0.01
autovacuum_vacuum_cost_delay = 2ms
autovacuum_vacuum_cost_limit = 2000

# Logging
log_min_duration_statement = 100  # Log queries > 100ms
log_checkpoints = on
log_lock_waits = on
log_temp_files = 0
```

#### PgBouncer Configuration

```ini
; pgbouncer.ini - Production configuration
[databases]
temporal = host=pg-primary.temporal.svc.cluster.local port=5432 dbname=temporal
temporal_visibility = host=pg-primary.temporal.svc.cluster.local port=5432 dbname=temporal_visibility

; Read replicas for visibility queries
temporal_visibility_ro = host=pg-replica.temporal.svc.cluster.local port=5432 dbname=temporal_visibility

[pgbouncer]
listen_addr = 0.0.0.0
listen_port = 6432
auth_type = scram-sha-256
auth_file = /etc/pgbouncer/userlist.txt

; Pool settings
pool_mode = transaction  # Transaction pooling for Temporal
max_client_conn = 1000
default_pool_size = 40
min_pool_size = 10
reserve_pool_size = 10
reserve_pool_timeout = 3

; Timeouts
server_connect_timeout = 5
server_idle_timeout = 300
server_lifetime = 3600
client_idle_timeout = 0
client_login_timeout = 60
query_timeout = 30
query_wait_timeout = 60

; Logging
log_connections = 0
log_disconnections = 0
log_pooler_errors = 1
stats_period = 30

; TLS
client_tls_sslmode = require
client_tls_cert_file = /etc/pgbouncer/tls/server.crt
client_tls_key_file = /etc/pgbouncer/tls/server.key
server_tls_sslmode = verify-full
server_tls_ca_file = /etc/pgbouncer/tls/ca.crt
```

#### Backup Strategy

```yaml
# PostgreSQL backup CronJob
apiVersion: batch/v1
kind: CronJob
metadata:
  name: temporal-pg-backup
  namespace: temporal
spec:
  schedule: "0 */6 * * *"  # Every 6 hours
  concurrencyPolicy: Forbid
  successfulJobsHistoryLimit: 3
  failedJobsHistoryLimit: 3
  jobTemplate:
    spec:
      backoffLimit: 2
      template:
        spec:
          serviceAccountName: temporal-backup
          containers:
            - name: pg-backup
              image: postgres:15-alpine
              command:
                - /bin/sh
                - -c
                - |
                  set -euo pipefail
                  TIMESTAMP=$(date +%Y%m%d_%H%M%S)
                  BACKUP_FILE="temporal_backup_${TIMESTAMP}.sql.gz"
                  
                  echo "Starting backup at ${TIMESTAMP}"
                  
                  pg_dump \
                    --host="${PG_HOST}" \
                    --port=5432 \
                    --username="${PG_USER}" \
                    --dbname=temporal \
                    --format=custom \
                    --compress=9 \
                    --verbose \
                    --file="/backups/${BACKUP_FILE}"
                  
                  # Upload to S3
                  aws s3 cp "/backups/${BACKUP_FILE}" \
                    "s3://${BACKUP_BUCKET}/temporal/daily/${BACKUP_FILE}" \
                    --storage-class STANDARD_IA
                  
                  # Verify backup
                  pg_restore --list "/backups/${BACKUP_FILE}" > /dev/null 2>&1
                  
                  echo "Backup completed successfully: ${BACKUP_FILE}"
                  
                  # Cleanup old local backups
                  find /backups -name "*.sql.gz" -mtime +2 -delete
              env:
                - name: PG_HOST
                  value: "pg-primary.temporal.svc.cluster.local"
                - name: PG_USER
                  valueFrom:
                    secretKeyRef:
                      name: temporal-pg-credentials
                      key: username
                - name: PGPASSWORD
                  valueFrom:
                    secretKeyRef:
                      name: temporal-pg-credentials
                      key: password
                - name: BACKUP_BUCKET
                  value: "company-temporal-backups"
              volumeMounts:
                - name: backup-storage
                  mountPath: /backups
          volumes:
            - name: backup-storage
              emptyDir:
                sizeLimit: 50Gi
          restartPolicy: OnFailure
```

---

## Elasticsearch/OpenSearch Setup

### Index Template

```json
{
  "index_patterns": ["temporal_visibility_v1*"],
  "template": {
    "settings": {
      "number_of_shards": 12,
      "number_of_replicas": 1,
      "index.refresh_interval": "1s",
      "index.max_result_window": 100000,
      "index.lifecycle.name": "temporal-visibility-ilm",
      "index.lifecycle.rollover_alias": "temporal_visibility_v1",
      "analysis": {
        "analyzer": {
          "workflow_id_analyzer": {
            "type": "custom",
            "tokenizer": "keyword",
            "filter": ["lowercase"]
          }
        }
      }
    },
    "mappings": {
      "dynamic": "false",
      "properties": {
        "NamespaceId": { "type": "keyword" },
        "WorkflowId": { "type": "keyword" },
        "RunId": { "type": "keyword" },
        "WorkflowType": { "type": "keyword" },
        "StartTime": { "type": "date" },
        "CloseTime": { "type": "date" },
        "ExecutionTime": { "type": "date" },
        "ExecutionStatus": { "type": "keyword" },
        "TaskQueue": { "type": "keyword" },
        "HistoryLength": { "type": "long" },
        "ExecutionDuration": { "type": "long" },
        "StateTransitionCount": { "type": "long" },
        "CustomKeywordField": { "type": "keyword" },
        "CustomStringField": { "type": "text" },
        "CustomIntField": { "type": "long" },
        "CustomDoubleField": { "type": "double" },
        "CustomBoolField": { "type": "boolean" },
        "CustomDatetimeField": { "type": "date" }
      }
    }
  }
}
```

### ILM Policy

```json
{
  "policy": {
    "phases": {
      "hot": {
        "min_age": "0ms",
        "actions": {
          "rollover": {
            "max_size": "50gb",
            "max_age": "7d",
            "max_docs": 100000000
          },
          "set_priority": {
            "priority": 100
          }
        }
      },
      "warm": {
        "min_age": "14d",
        "actions": {
          "shrink": {
            "number_of_shards": 3
          },
          "forcemerge": {
            "max_num_segments": 1
          },
          "allocate": {
            "number_of_replicas": 1,
            "require": {
              "data_type": "warm"
            }
          },
          "set_priority": {
            "priority": 50
          }
        }
      },
      "cold": {
        "min_age": "90d",
        "actions": {
          "allocate": {
            "number_of_replicas": 0,
            "require": {
              "data_type": "cold"
            }
          },
          "set_priority": {
            "priority": 0
          }
        }
      },
      "delete": {
        "min_age": "365d",
        "actions": {
          "delete": {}
        }
      }
    }
  }
}
```

### Elasticsearch Cluster Sizing

```yaml
# Elasticsearch master nodes
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: elasticsearch-master
  namespace: temporal
spec:
  replicas: 3
  selector:
    matchLabels:
      app: elasticsearch
      role: master
  template:
    spec:
      containers:
        - name: elasticsearch
          image: docker.elastic.co/elasticsearch/elasticsearch:7.17.18
          resources:
            requests:
              cpu: "2"
              memory: "4Gi"
            limits:
              cpu: "4"
              memory: "4Gi"
          env:
            - name: node.roles
              value: "master"
            - name: ES_JAVA_OPTS
              value: "-Xms2g -Xmx2g"
            - name: cluster.name
              value: "temporal-es"
---
# Elasticsearch data nodes
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: elasticsearch-data
  namespace: temporal
spec:
  replicas: 6
  selector:
    matchLabels:
      app: elasticsearch
      role: data
  template:
    spec:
      containers:
        - name: elasticsearch
          image: docker.elastic.co/elasticsearch/elasticsearch:7.17.18
          resources:
            requests:
              cpu: "8"
              memory: "32Gi"
            limits:
              cpu: "16"
              memory: "32Gi"
          env:
            - name: node.roles
              value: "data,ingest"
            - name: ES_JAVA_OPTS
              value: "-Xms16g -Xmx16g"
          volumeMounts:
            - name: data
              mountPath: /usr/share/elasticsearch/data
  volumeClaimTemplates:
    - metadata:
        name: data
      spec:
        accessModes: ["ReadWriteOnce"]
        storageClassName: gp3-ssd
        resources:
          requests:
            storage: 1Ti
```

---

## Worker Deployment

### Go Worker Application — Complete Production main.go

```go
// main.go - Production Temporal Worker
package main

import (
	"context"
	"crypto/tls"
	"crypto/x509"
	"fmt"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"runtime"
	"syscall"
	"time"

	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promhttp"
	prom "go.temporal.io/sdk/contrib/opentelemetry"
	"go.temporal.io/sdk/client"
	sdktally "go.temporal.io/sdk/contrib/tally"
	"go.temporal.io/sdk/interceptor"
	"go.temporal.io/sdk/worker"
	"go.temporal.io/sdk/workflow"
	ubertally "github.com/uber-go/tally/v4"
	tallyprom "github.com/uber-go/tally/v4/prometheus"
	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracegrpc"
	"go.opentelemetry.io/otel/sdk/resource"
	sdktrace "go.opentelemetry.io/otel/sdk/trace"
	semconv "go.opentelemetry.io/otel/semconv/v1.21.0"
)

// Config holds all worker configuration
type Config struct {
	// Temporal connection
	TemporalHost      string
	Namespace         string
	TaskQueue         string
	Identity          string

	// TLS
	TLSCertFile       string
	TLSKeyFile        string
	TLSCaFile         string
	TLSServerName     string

	// Worker tuning
	MaxConcurrentActivities        int
	MaxConcurrentWorkflowTasks     int
	MaxConcurrentLocalActivities   int
	MaxActivityPollers             int
	MaxWorkflowTaskPollers         int
	WorkerActivitiesPerSecond      float64
	TaskQueueActivitiesPerSecond   float64
	StickyScheduleToStartTimeout   time.Duration
	DeadlockDetectionTimeout       time.Duration

	// Observability
	MetricsPort       int
	HealthPort        int
	OTelEndpoint      string

	// Application
	WorkerType        string // "all", "workflow-only", "activity-only"
}

func LoadConfig() Config {
	return Config{
		TemporalHost:                   getEnv("TEMPORAL_HOST", "temporal-frontend.temporal.svc.cluster.local:7233"),
		Namespace:                      getEnv("TEMPORAL_NAMESPACE", "production"),
		TaskQueue:                      getEnv("TEMPORAL_TASK_QUEUE", "default-task-queue"),
		Identity:                       fmt.Sprintf("%s-%s-%s", getEnv("POD_NAME", "worker"), getEnv("POD_NAMESPACE", "default"), getEnv("NODE_NAME", "unknown")),
		TLSCertFile:                    getEnv("TEMPORAL_TLS_CERT", "/etc/temporal/tls/tls.crt"),
		TLSKeyFile:                     getEnv("TEMPORAL_TLS_KEY", "/etc/temporal/tls/tls.key"),
		TLSCaFile:                      getEnv("TEMPORAL_TLS_CA", "/etc/temporal/tls/ca.crt"),
		TLSServerName:                  getEnv("TEMPORAL_TLS_SERVER_NAME", "temporal-frontend.temporal.svc.cluster.local"),
		MaxConcurrentActivities:        getEnvInt("MAX_CONCURRENT_ACTIVITIES", 200),
		MaxConcurrentWorkflowTasks:     getEnvInt("MAX_CONCURRENT_WORKFLOW_TASKS", 200),
		MaxConcurrentLocalActivities:   getEnvInt("MAX_CONCURRENT_LOCAL_ACTIVITIES", 200),
		MaxActivityPollers:             getEnvInt("MAX_ACTIVITY_POLLERS", 20),
		MaxWorkflowTaskPollers:         getEnvInt("MAX_WORKFLOW_TASK_POLLERS", 10),
		WorkerActivitiesPerSecond:      getEnvFloat("WORKER_ACTIVITIES_PER_SECOND", 0), // 0 = unlimited
		TaskQueueActivitiesPerSecond:   getEnvFloat("TASK_QUEUE_ACTIVITIES_PER_SECOND", 0),
		StickyScheduleToStartTimeout:   getEnvDuration("STICKY_SCHEDULE_TO_START_TIMEOUT", 5*time.Second),
		DeadlockDetectionTimeout:       getEnvDuration("DEADLOCK_DETECTION_TIMEOUT", 5*time.Second),
		MetricsPort:                    getEnvInt("METRICS_PORT", 9090),
		HealthPort:                     getEnvInt("HEALTH_PORT", 8080),
		OTelEndpoint:                   getEnv("OTEL_EXPORTER_OTLP_ENDPOINT", "otel-collector.observability.svc.cluster.local:4317"),
		WorkerType:                     getEnv("WORKER_TYPE", "all"),
	}
}

func main() {
	cfg := LoadConfig()

	// Setup structured logging
	logger := slog.New(slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{
		Level: slog.LevelInfo,
	}))
	slog.SetDefault(logger)

	logger.Info("Starting Temporal worker",
		"taskQueue", cfg.TaskQueue,
		"namespace", cfg.Namespace,
		"identity", cfg.Identity,
		"maxConcurrentActivities", cfg.MaxConcurrentActivities,
		"goMaxProcs", runtime.GOMAXPROCS(0),
	)

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	// Initialize OpenTelemetry tracing
	tp, err := initTracer(ctx, cfg)
	if err != nil {
		logger.Error("Failed to initialize tracer", "error", err)
		os.Exit(1)
	}
	defer func() {
		shutdownCtx, shutdownCancel := context.WithTimeout(context.Background(), 10*time.Second)
		defer shutdownCancel()
		tp.Shutdown(shutdownCtx)
	}()

	// Initialize metrics
	metricsHandler, metricsCloser := initMetrics(cfg)
	defer metricsCloser.Close()

	// Create TLS config
	tlsConfig, err := createTLSConfig(cfg)
	if err != nil {
		logger.Error("Failed to create TLS config", "error", err)
		os.Exit(1)
	}

	// Create Temporal client
	tracingInterceptor, err := prom.NewTracingInterceptor(prom.TracerOptions{
		Tracer: otel.Tracer("temporal-worker"),
	})
	if err != nil {
		logger.Error("Failed to create tracing interceptor", "error", err)
		os.Exit(1)
	}

	c, err := client.Dial(client.Options{
		HostPort:  cfg.TemporalHost,
		Namespace: cfg.Namespace,
		Identity:  cfg.Identity,
		ConnectionOptions: client.ConnectionOptions{
			TLS: tlsConfig,
		},
		MetricsHandler: metricsHandler,
		Interceptors:   []interceptor.ClientInterceptor{tracingInterceptor},
		Logger:         NewTemporalSlogAdapter(logger),
	})
	if err != nil {
		logger.Error("Failed to create Temporal client", "error", err)
		os.Exit(1)
	}
	defer c.Close()

	// Create worker
	w := worker.New(c, cfg.TaskQueue, worker.Options{
		Identity:                          cfg.Identity,
		MaxConcurrentActivityExecutionSize:     cfg.MaxConcurrentActivities,
		MaxConcurrentWorkflowTaskExecutionSize: cfg.MaxConcurrentWorkflowTasks,
		MaxConcurrentLocalActivityExecutionSize: cfg.MaxConcurrentLocalActivities,
		MaxConcurrentActivityTaskPollers:       cfg.MaxActivityPollers,
		MaxConcurrentWorkflowTaskPollers:       cfg.MaxWorkflowTaskPollers,
		WorkerActivitiesPerSecond:              cfg.WorkerActivitiesPerSecond,
		TaskQueueActivitiesPerSecond:           cfg.TaskQueueActivitiesPerSecond,
		StickyScheduleToStartTimeout:           cfg.StickyScheduleToStartTimeout,
		DeadlockDetectionTimeout:               cfg.DeadlockDetectionTimeout,
		EnableSessionWorker:                    true,
		MaxConcurrentSessionExecutionSize:      200,
		WorkerStopTimeout:                      30 * time.Second,
	})

	// Register workflows and activities based on worker type
	registerWorkflowsAndActivities(w, cfg)

	// Start health check server
	healthServer := startHealthServer(cfg, c)
	defer healthServer.Close()

	// Start metrics server
	metricsServer := startMetricsServer(cfg)
	defer metricsServer.Close()

	// Start worker
	errCh := make(chan error, 1)
	go func() {
		errCh <- w.Run(worker.InterruptCh())
	}()

	// Wait for shutdown signal
	sigCh := make(chan os.Signal, 1)
	signal.Notify(sigCh, syscall.SIGINT, syscall.SIGTERM)

	select {
	case sig := <-sigCh:
		logger.Info("Received shutdown signal", "signal", sig)
		cancel()
		w.Stop()
	case err := <-errCh:
		if err != nil {
			logger.Error("Worker stopped with error", "error", err)
			os.Exit(1)
		}
	}

	logger.Info("Worker shutdown complete")
}

func createTLSConfig(cfg Config) (*tls.Config, error) {
	cert, err := tls.LoadX509KeyPair(cfg.TLSCertFile, cfg.TLSKeyFile)
	if err != nil {
		return nil, fmt.Errorf("loading TLS cert: %w", err)
	}

	caCert, err := os.ReadFile(cfg.TLSCaFile)
	if err != nil {
		return nil, fmt.Errorf("reading CA cert: %w", err)
	}

	caCertPool := x509.NewCertPool()
	if !caCertPool.AppendCertsFromPEM(caCert) {
		return nil, fmt.Errorf("failed to add CA cert to pool")
	}

	return &tls.Config{
		Certificates: []tls.Certificate{cert},
		RootCAs:      caCertPool,
		ServerName:   cfg.TLSServerName,
		MinVersion:   tls.VersionTLS12,
	}, nil
}

func initTracer(ctx context.Context, cfg Config) (*sdktrace.TracerProvider, error) {
	exporter, err := otlptracegrpc.New(ctx,
		otlptracegrpc.WithEndpoint(cfg.OTelEndpoint),
		otlptracegrpc.WithInsecure(),
	)
	if err != nil {
		return nil, err
	}

	tp := sdktrace.NewTracerProvider(
		sdktrace.WithBatcher(exporter,
			sdktrace.WithMaxExportBatchSize(512),
			sdktrace.WithBatchTimeout(5*time.Second),
		),
		sdktrace.WithResource(resource.NewWithAttributes(
			semconv.SchemaURL,
			semconv.ServiceName("temporal-worker"),
			semconv.ServiceVersion("1.0.0"),
			semconv.DeploymentEnvironment("production"),
		)),
		sdktrace.WithSampler(sdktrace.ParentBased(sdktrace.TraceIDRatioBased(0.01))), // 1% sampling
	)
	otel.SetTracerProvider(tp)
	return tp, nil
}

func initMetrics(cfg Config) (client.MetricsHandler, ubertally.Scope) {
	reporter := tallyprom.NewReporter(tallyprom.Options{
		Registerer: prometheus.DefaultRegisterer,
	})

	scope, closer := ubertally.NewRootScope(ubertally.ScopeOptions{
		Prefix:         "temporal",
		Tags:           map[string]string{"task_queue": cfg.TaskQueue, "namespace": cfg.Namespace},
		CachedReporter: reporter,
		Separator:      "_",
	}, 1*time.Second)

	return sdktally.NewMetricsHandler(scope), closer
}

func startHealthServer(cfg Config, c client.Client) *http.Server {
	mux := http.NewServeMux()

	// Liveness probe - worker process is alive
	mux.HandleFunc("/healthz", func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		w.Write([]byte("ok"))
	})

	// Readiness probe - can connect to Temporal
	mux.HandleFunc("/readyz", func(w http.ResponseWriter, r *http.Request) {
		ctx, cancel := context.WithTimeout(r.Context(), 3*time.Second)
		defer cancel()

		// Check connection by describing namespace
		_, err := c.WorkflowService().GetSystemInfo(ctx, nil)
		if err != nil {
			w.WriteHeader(http.StatusServiceUnavailable)
			w.Write([]byte(fmt.Sprintf("not ready: %v", err)))
			return
		}
		w.WriteHeader(http.StatusOK)
		w.Write([]byte("ready"))
	})

	server := &http.Server{
		Addr:    fmt.Sprintf(":%d", cfg.HealthPort),
		Handler: mux,
	}
	go server.ListenAndServe()
	return server
}

func startMetricsServer(cfg Config) *http.Server {
	mux := http.NewServeMux()
	mux.Handle("/metrics", promhttp.Handler())

	server := &http.Server{
		Addr:    fmt.Sprintf(":%d", cfg.MetricsPort),
		Handler: mux,
	}
	go server.ListenAndServe()
	return server
}

func registerWorkflowsAndActivities(w worker.Worker, cfg Config) {
	switch cfg.WorkerType {
	case "workflow-only":
		registerWorkflows(w)
	case "activity-only":
		registerActivities(w)
	default: // "all"
		registerWorkflows(w)
		registerActivities(w)
	}
}

func registerWorkflows(w worker.Worker) {
	// Register all workflow functions
	w.RegisterWorkflowWithOptions(OrderWorkflow, workflow.RegisterOptions{Name: "OrderWorkflow"})
	w.RegisterWorkflowWithOptions(PaymentWorkflow, workflow.RegisterOptions{Name: "PaymentWorkflow"})
	w.RegisterWorkflowWithOptions(FulfillmentWorkflow, workflow.RegisterOptions{Name: "FulfillmentWorkflow"})
	// Add all workflows...
}

func registerActivities(w worker.Worker) {
	// Register activity structs (allows dependency injection)
	activities := &Activities{
		// Initialize with connections, clients, etc.
	}
	w.RegisterActivity(activities)
}

// Helper functions
func getEnv(key, defaultValue string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return defaultValue
}

func getEnvInt(key string, defaultValue int) int {
	if v := os.Getenv(key); v != "" {
		var i int
		fmt.Sscanf(v, "%d", &i)
		return i
	}
	return defaultValue
}

func getEnvFloat(key string, defaultValue float64) float64 {
	if v := os.Getenv(key); v != "" {
		var f float64
		fmt.Sscanf(v, "%f", &f)
		return f
	}
	return defaultValue
}

func getEnvDuration(key string, defaultValue time.Duration) time.Duration {
	if v := os.Getenv(key); v != "" {
		d, err := time.ParseDuration(v)
		if err == nil {
			return d
		}
	}
	return defaultValue
}
```

### Kubernetes Deployment for Workers

```yaml
# worker-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: temporal-worker-default
  namespace: temporal-workers
  labels:
    app: temporal-worker
    task-queue: default-task-queue
    team: platform
spec:
  replicas: 5
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxUnavailable: 1
      maxSurge: 2
  selector:
    matchLabels:
      app: temporal-worker
      task-queue: default-task-queue
  template:
    metadata:
      labels:
        app: temporal-worker
        task-queue: default-task-queue
        version: v1.2.3
      annotations:
        prometheus.io/scrape: "true"
        prometheus.io/port: "9090"
        prometheus.io/path: "/metrics"
        cluster-autoscaler.kubernetes.io/safe-to-evict: "false"
    spec:
      serviceAccountName: temporal-worker
      terminationGracePeriodSeconds: 120  # Allow activities to complete
      
      initContainers:
        # Wait for Temporal Frontend to be available
        - name: wait-for-temporal
          image: busybox:1.36
          command: ['sh', '-c']
          args:
            - |
              echo "Waiting for Temporal Frontend..."
              until nc -z temporal-frontend.temporal.svc.cluster.local 7233; do
                echo "Temporal not ready, waiting..."
                sleep 5
              done
              echo "Temporal Frontend is available"
        
        # Wait for database migrations
        - name: wait-for-schema
          image: curlimages/curl:8.4.0
          command: ['sh', '-c']
          args:
            - |
              until curl -sf http://temporal-frontend.temporal.svc.cluster.local:7233/health; do
                sleep 5
              done

      containers:
        - name: worker
          image: registry.company.com/temporal-workers:v1.2.3
          imagePullPolicy: IfNotPresent
          
          resources:
            requests:
              cpu: "2"
              memory: "4Gi"
            limits:
              cpu: "4"
              memory: "8Gi"
          
          ports:
            - name: metrics
              containerPort: 9090
              protocol: TCP
            - name: health
              containerPort: 8080
              protocol: TCP
          
          livenessProbe:
            httpGet:
              path: /healthz
              port: health
            initialDelaySeconds: 15
            periodSeconds: 10
            timeoutSeconds: 5
            failureThreshold: 3
          
          readinessProbe:
            httpGet:
              path: /readyz
              port: health
            initialDelaySeconds: 10
            periodSeconds: 5
            timeoutSeconds: 3
            failureThreshold: 3
          
          env:
            - name: TEMPORAL_HOST
              value: "temporal-frontend.temporal.svc.cluster.local:7233"
            - name: TEMPORAL_NAMESPACE
              value: "production"
            - name: TEMPORAL_TASK_QUEUE
              value: "default-task-queue"
            - name: WORKER_TYPE
              value: "all"
            - name: MAX_CONCURRENT_ACTIVITIES
              value: "200"
            - name: MAX_CONCURRENT_WORKFLOW_TASKS
              value: "200"
            - name: MAX_ACTIVITY_POLLERS
              value: "20"
            - name: MAX_WORKFLOW_TASK_POLLERS
              value: "10"
            - name: OTEL_EXPORTER_OTLP_ENDPOINT
              value: "otel-collector.observability.svc.cluster.local:4317"
            - name: POD_NAME
              valueFrom:
                fieldRef:
                  fieldPath: metadata.name
            - name: POD_NAMESPACE
              valueFrom:
                fieldRef:
                  fieldPath: metadata.namespace
            - name: NODE_NAME
              valueFrom:
                fieldRef:
                  fieldPath: spec.nodeName
            - name: GOMAXPROCS
              valueFrom:
                resourceFieldRef:
                  resource: limits.cpu
          
          envFrom:
            - configMapRef:
                name: temporal-worker-config
            - secretRef:
                name: temporal-worker-secrets
          
          volumeMounts:
            - name: tls-certs
              mountPath: /etc/temporal/tls
              readOnly: true
            - name: tmp
              mountPath: /tmp
      
      volumes:
        - name: tls-certs
          secret:
            secretName: temporal-worker-tls
        - name: tmp
          emptyDir:
            sizeLimit: 1Gi
      
      affinity:
        podAntiAffinity:
          preferredDuringSchedulingIgnoredDuringExecution:
            - weight: 100
              podAffinityTerm:
                labelSelector:
                  matchExpressions:
                    - key: app
                      operator: In
                      values:
                        - temporal-worker
                    - key: task-queue
                      operator: In
                      values:
                        - default-task-queue
                topologyKey: kubernetes.io/hostname
      
      topologySpreadConstraints:
        - maxSkew: 2
          topologyKey: topology.kubernetes.io/zone
          whenUnsatisfiable: ScheduleAnyway
          labelSelector:
            matchLabels:
              app: temporal-worker
              task-queue: default-task-queue

---
# HPA based on custom metrics
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: temporal-worker-default-hpa
  namespace: temporal-workers
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: temporal-worker-default
  minReplicas: 3
  maxReplicas: 50
  metrics:
    # Scale on schedule-to-start latency (primary signal)
    - type: External
      external:
        metric:
          name: temporal_workflow_task_schedule_to_start_latency_seconds
          selector:
            matchLabels:
              task_queue: "default-task-queue"
              namespace: "production"
        target:
          type: AverageValue
          averageValue: "5"  # Target 5s schedule-to-start
    
    # Also scale on CPU as a secondary signal
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
    
    # Memory pressure
    - type: Resource
      resource:
        name: memory
        target:
          type: Utilization
          averageUtilization: 75
  
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 30
      policies:
        - type: Percent
          value: 50
          periodSeconds: 60
        - type: Pods
          value: 5
          periodSeconds: 60
      selectPolicy: Max
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
        - type: Pods
          value: 2
          periodSeconds: 120
      selectPolicy: Min

---
# KEDA ScaledObject (alternative to HPA for more advanced scaling)
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: temporal-worker-batch-keda
  namespace: temporal-workers
spec:
  scaleTargetRef:
    name: temporal-worker-batch
  pollingInterval: 15
  cooldownPeriod: 300
  minReplicaCount: 0  # Scale to zero for batch workers
  maxReplicaCount: 100
  triggers:
    - type: prometheus
      metadata:
        serverAddress: http://prometheus.observability.svc.cluster.local:9090
        metricName: temporal_matching_tasks_added_rate
        query: |
          sum(rate(temporal_matching_tasks_added_total{
            task_queue="batch-task-queue",
            namespace="production"
          }[5m]))
        threshold: "10"  # Scale up when > 10 tasks/sec being added
        activationThreshold: "1"  # Activate (from 0) when any tasks

---
# ConfigMap
apiVersion: v1
kind: ConfigMap
metadata:
  name: temporal-worker-config
  namespace: temporal-workers
data:
  LOG_LEVEL: "info"
  METRICS_PORT: "9090"
  HEALTH_PORT: "8080"
  STICKY_SCHEDULE_TO_START_TIMEOUT: "5s"
  DEADLOCK_DETECTION_TIMEOUT: "5s"

---
# Network Policy
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: temporal-worker-netpol
  namespace: temporal-workers
spec:
  podSelector:
    matchLabels:
      app: temporal-worker
  policyTypes:
    - Egress
    - Ingress
  ingress:
    # Allow Prometheus scraping
    - from:
        - namespaceSelector:
            matchLabels:
              name: observability
      ports:
        - port: 9090
          protocol: TCP
  egress:
    # Allow connecting to Temporal Frontend
    - to:
        - namespaceSelector:
            matchLabels:
              name: temporal
      ports:
        - port: 7233
          protocol: TCP
    # Allow connecting to downstream services
    - to:
        - namespaceSelector:
            matchLabels:
              name: services
      ports:
        - port: 443
          protocol: TCP
        - port: 8080
          protocol: TCP
    # Allow DNS
    - to:
        - namespaceSelector: {}
      ports:
        - port: 53
          protocol: UDP
        - port: 53
          protocol: TCP
    # Allow OTel collector
    - to:
        - namespaceSelector:
            matchLabels:
              name: observability
      ports:
        - port: 4317
          protocol: TCP
```

---

## Network Configuration

### mTLS Setup Between Components

```yaml
# cert-manager ClusterIssuer for Temporal internal certs
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: temporal-ca-issuer
spec:
  ca:
    secretName: temporal-ca-key-pair

---
# Certificate for Temporal Frontend
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: temporal-frontend-tls
  namespace: temporal
spec:
  secretName: temporal-frontend-tls
  duration: 8760h  # 1 year
  renewBefore: 720h  # 30 days before expiry
  privateKey:
    algorithm: ECDSA
    size: 256
  usages:
    - server auth
    - client auth
  dnsNames:
    - temporal-frontend
    - temporal-frontend.temporal
    - temporal-frontend.temporal.svc
    - temporal-frontend.temporal.svc.cluster.local
    - "*.temporal-frontend.temporal.svc.cluster.local"
  issuerRef:
    name: temporal-ca-issuer
    kind: ClusterIssuer

---
# Certificate for Workers
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: temporal-worker-tls
  namespace: temporal-workers
spec:
  secretName: temporal-worker-tls
  duration: 8760h
  renewBefore: 720h
  privateKey:
    algorithm: ECDSA
    size: 256
  usages:
    - client auth
  dnsNames:
    - "*.temporal-workers.svc.cluster.local"
  issuerRef:
    name: temporal-ca-issuer
    kind: ClusterIssuer
```

### Ingress Configuration for gRPC

```yaml
# Ingress for external gRPC access (e.g., workers outside the cluster)
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: temporal-grpc-ingress
  namespace: temporal
  annotations:
    kubernetes.io/ingress.class: "nginx"
    nginx.ingress.kubernetes.io/backend-protocol: "GRPC"
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
    nginx.ingress.kubernetes.io/grpc-backend: "true"
    nginx.ingress.kubernetes.io/proxy-body-size: "16m"
    nginx.ingress.kubernetes.io/proxy-read-timeout: "3600"
    nginx.ingress.kubernetes.io/proxy-send-timeout: "3600"
    nginx.ingress.kubernetes.io/server-snippet: |
      grpc_read_timeout 3600s;
      grpc_send_timeout 3600s;
      client_body_timeout 3600s;
    # mTLS client verification
    nginx.ingress.kubernetes.io/auth-tls-verify-client: "on"
    nginx.ingress.kubernetes.io/auth-tls-secret: "temporal/temporal-ca-cert"
    nginx.ingress.kubernetes.io/auth-tls-verify-depth: "2"
spec:
  tls:
    - hosts:
        - temporal.company.internal
      secretName: temporal-ingress-tls
  rules:
    - host: temporal.company.internal
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: temporal-frontend
                port:
                  number: 7233
```

---

## Configuration Management

### Dynamic Configuration (Complete Example)

```yaml
# dynamic-config.yaml - Temporal Server Dynamic Configuration
# This file is hot-reloaded by Temporal server (no restart needed)
# Place in ConfigMap mounted to /etc/temporal/dynamic-config/

# Global limits
system.maxTaskQueueIdleTime:
  - value: 300s  # 5 minutes

# Frontend rate limiting
frontend.rps:
  - value: 2400
    constraints: {}
  - value: 600
    constraints:
      namespace: "batch-processing"  # Lower limit for batch namespace

frontend.namespaceRPS:
  - value: 1200
    constraints: {}
  - value: 200
    constraints:
      namespace: "dev-testing"

frontend.maxNamespaceVisibilityRPSPerInstance:
  - value: 50
    constraints: {}

frontend.maxNamespaceCountPerInstance:
  - value: 10
    constraints: {}

# History service
history.maxAutoResetPoints:
  - value: 20
    constraints: {}

history.defaultActivityRetryPolicy:
  - value:
      InitialIntervalInSeconds: 1
      MaximumIntervalCoefficient: 100.0
      BackoffCoefficient: 2.0
      MaximumAttempts: 0

history.maximumSignalsPerExecution:
  - value: 10000
    constraints: {}

history.defaultWorkflowExecutionTimeout:
  - value: 86400s  # 24 hours
    constraints: {}

history.defaultWorkflowRunTimeout:
  - value: 86400s
    constraints: {}

history.defaultWorkflowTaskTimeout:
  - value: 10s
    constraints: {}

# Critical: History size limits
limit.maxIDLength:
  - value: 1000
    constraints: {}

limit.blobSize.error:
  - value: 2097152  # 2MB
    constraints: {}

limit.blobSize.warn:
  - value: 524288  # 512KB
    constraints: {}

limit.historySize.error:
  - value: 52428800  # 50MB
    constraints: {}

limit.historySize.warn:
  - value: 10485760  # 10MB
    constraints: {}

limit.historyCount.error:
  - value: 50000
    constraints: {}

limit.historyCount.warn:
  - value: 10000
    constraints: {}

# Matching service
matching.numTaskqueueReadPartitions:
  - value: 4
    constraints: {}
  - value: 16
    constraints:
      taskQueueName: "high-throughput-queue"

matching.numTaskqueueWritePartitions:
  - value: 4
    constraints: {}
  - value: 16
    constraints:
      taskQueueName: "high-throughput-queue"

matching.forwarderMaxOutstandingPolls:
  - value: 1
    constraints: {}

matching.forwarderMaxRatePerSecond:
  - value: 10
    constraints: {}

# Archival
system.archivalStatus:
  - value: "enabled"
    constraints: {}

system.enableArchivalCompression:
  - value: true
    constraints: {}

# Visibility
system.enableReadVisibilityFromES:
  - value: true
    constraints: {}

system.advancedVisibilityWritingMode:
  - value: "on"
    constraints: {}

# Worker tuning
worker.replicatorConcurrency:
  - value: 256
    constraints: {}

worker.replicatorActivityBufferRetryCount:
  - value: 8
    constraints: {}

# Search attributes
limit.numSearchAttributes:
  - value: 100
    constraints: {}
```

---

## CI/CD Pipeline

### Workflow Determinism Testing

```go
// determinism_test.go - Test workflow replay determinism
package workflows_test

import (
	"context"
	"encoding/json"
	"os"
	"path/filepath"
	"testing"

	"github.com/stretchr/testify/require"
	"go.temporal.io/sdk/client"
	"go.temporal.io/sdk/worker"
	"go.temporal.io/sdk/testsuite"
)

// TestWorkflowReplay replays all recorded workflow histories
// to ensure code changes don't break determinism.
func TestWorkflowReplay(t *testing.T) {
	replayer := worker.NewWorkflowReplayer()

	// Register all workflows
	replayer.RegisterWorkflow(OrderWorkflow)
	replayer.RegisterWorkflow(PaymentWorkflow)
	replayer.RegisterWorkflow(FulfillmentWorkflow)

	// Replay all recorded histories
	historyDir := "testdata/workflow-histories"
	entries, err := os.ReadDir(historyDir)
	require.NoError(t, err)

	for _, entry := range entries {
		if entry.IsDir() || filepath.Ext(entry.Name()) != ".json" {
			continue
		}
		t.Run(entry.Name(), func(t *testing.T) {
			historyFile := filepath.Join(historyDir, entry.Name())
			err := replayer.ReplayWorkflowHistoryFromJSONFile(nil, historyFile)
			require.NoError(t, err, "Replay failed for %s - NON-DETERMINISM DETECTED", entry.Name())
		})
	}
}

// TestWorkflowReplayFromCluster downloads and replays recent histories
// Run this in CI against staging cluster before deploying to production
func TestWorkflowReplayFromCluster(t *testing.T) {
	if os.Getenv("TEMPORAL_REPLAY_TEST") != "true" {
		t.Skip("Set TEMPORAL_REPLAY_TEST=true to run cluster replay tests")
	}

	c, err := client.Dial(client.Options{
		HostPort:  os.Getenv("TEMPORAL_HOST"),
		Namespace: os.Getenv("TEMPORAL_NAMESPACE"),
	})
	require.NoError(t, err)
	defer c.Close()

	replayer := worker.NewWorkflowReplayer()
	replayer.RegisterWorkflow(OrderWorkflow)
	replayer.RegisterWorkflow(PaymentWorkflow)

	// List recent completed workflows
	ctx := context.Background()
	iter, err := c.ListWorkflow(ctx, &client.ListWorkflowExecutionsRequest{
		Query:    "ExecutionStatus = 'Completed' AND CloseTime > '2024-01-01T00:00:00Z'",
		PageSize: 100,
	})
	require.NoError(t, err)

	count := 0
	for iter.HasNext() {
		wf, err := iter.Next()
		require.NoError(t, err)

		// Get workflow history
		histIter := c.GetWorkflowHistory(ctx, wf.GetExecution().GetWorkflowId(),
			wf.GetExecution().GetRunId(), false, 0)

		var history client.WorkflowExecutionHistory
		for histIter.HasNext() {
			event, err := histIter.Next()
			require.NoError(t, err)
			history.Events = append(history.Events, event)
		}

		err = replayer.ReplayWorkflowHistory(nil, &history)
		require.NoError(t, err, "Non-determinism in workflow %s/%s",
			wf.GetExecution().GetWorkflowId(), wf.GetExecution().GetRunId())
		count++
	}
	t.Logf("Successfully replayed %d workflow histories", count)
}
```

### CI/CD Pipeline (GitHub Actions)

```yaml
# .github/workflows/temporal-workers.yaml
name: Temporal Worker CI/CD

on:
  push:
    branches: [main, release/*]
    paths:
      - 'services/temporal-workers/**'
  pull_request:
    branches: [main]
    paths:
      - 'services/temporal-workers/**'

env:
  GO_VERSION: "1.22"
  REGISTRY: registry.company.com
  IMAGE_NAME: temporal-workers

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - uses: actions/setup-go@v5
        with:
          go-version: ${{ env.GO_VERSION }}
      
      - name: Unit Tests
        run: go test ./... -race -coverprofile=coverage.out
        working-directory: services/temporal-workers
      
      - name: Workflow Determinism Tests
        run: go test ./workflows/... -run TestWorkflowReplay -v
        working-directory: services/temporal-workers
      
      - name: Replay Against Staging
        if: github.event_name == 'push' && github.ref == 'refs/heads/main'
        env:
          TEMPORAL_REPLAY_TEST: "true"
          TEMPORAL_HOST: ${{ secrets.STAGING_TEMPORAL_HOST }}
          TEMPORAL_NAMESPACE: "staging"
        run: go test ./workflows/... -run TestWorkflowReplayFromCluster -v -timeout 10m
        working-directory: services/temporal-workers

  build:
    needs: test
    runs-on: ubuntu-latest
    outputs:
      image-tag: ${{ steps.meta.outputs.tags }}
    steps:
      - uses: actions/checkout@v4
      
      - name: Build and push
        uses: docker/build-push-action@v5
        with:
          context: services/temporal-workers
          push: true
          tags: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:${{ github.sha }}

  deploy-canary:
    needs: build
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    steps:
      - name: Deploy canary (10% traffic)
        run: |
          kubectl set image deployment/temporal-worker-canary \
            worker=${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:${{ github.sha }} \
            -n temporal-workers
          kubectl rollout status deployment/temporal-worker-canary -n temporal-workers --timeout=300s

      - name: Verify canary (5 min soak)
        run: |
          sleep 300
          # Check error rate
          ERROR_RATE=$(curl -s "http://prometheus:9090/api/v1/query" \
            --data-urlencode 'query=rate(temporal_activity_execution_failed_total{deployment="canary"}[5m]) / rate(temporal_activity_execution_total{deployment="canary"}[5m])' \
            | jq -r '.data.result[0].value[1]')
          if (( $(echo "$ERROR_RATE > 0.01" | bc -l) )); then
            echo "Canary error rate too high: $ERROR_RATE"
            kubectl rollout undo deployment/temporal-worker-canary -n temporal-workers
            exit 1
          fi

  deploy-production:
    needs: deploy-canary
    runs-on: ubuntu-latest
    steps:
      - name: Rolling update production
        run: |
          kubectl set image deployment/temporal-worker-default \
            worker=${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:${{ github.sha }} \
            -n temporal-workers
          kubectl rollout status deployment/temporal-worker-default -n temporal-workers --timeout=600s
```

---

## Security

### Custom Data Converter (Encryption at Rest)

```go
// encryption.go - Custom Data Converter for payload encryption
package encryption

import (
	"crypto/aes"
	"crypto/cipher"
	"crypto/rand"
	"fmt"
	"io"

	commonpb "go.temporal.io/api/common/v1"
	"go.temporal.io/sdk/converter"
)

const (
	MetadataEncodingEncrypted = "binary/encrypted"
	MetadataEncryptionKeyID   = "encryption-key-id"
)

// Codec implements PayloadCodec for encrypting/decrypting payloads
type Codec struct {
	keyID   string
	key     []byte  // 32 bytes for AES-256
	fetchKey func(keyID string) ([]byte, error)  // For key rotation support
}

func NewCodec(keyID string, key []byte) *Codec {
	return &Codec{keyID: keyID, key: key}
}

func (c *Codec) Encode(payloads []*commonpb.Payload) ([]*commonpb.Payload, error) {
	result := make([]*commonpb.Payload, len(payloads))
	for i, p := range payloads {
		origBytes, err := p.Marshal()
		if err != nil {
			return nil, fmt.Errorf("marshal payload: %w", err)
		}

		encrypted, err := encrypt(origBytes, c.key)
		if err != nil {
			return nil, fmt.Errorf("encrypt: %w", err)
		}

		result[i] = &commonpb.Payload{
			Metadata: map[string][]byte{
				"encoding":             []byte(MetadataEncodingEncrypted),
				MetadataEncryptionKeyID: []byte(c.keyID),
			},
			Data: encrypted,
		}
	}
	return result, nil
}

func (c *Codec) Decode(payloads []*commonpb.Payload) ([]*commonpb.Payload, error) {
	result := make([]*commonpb.Payload, len(payloads))
	for i, p := range payloads {
		if string(p.Metadata["encoding"]) != MetadataEncodingEncrypted {
			result[i] = p
			continue
		}

		key := c.key
		if c.fetchKey != nil {
			keyID := string(p.Metadata[MetadataEncryptionKeyID])
			var err error
			key, err = c.fetchKey(keyID)
			if err != nil {
				return nil, fmt.Errorf("fetch key %s: %w", keyID, err)
			}
		}

		decrypted, err := decrypt(p.Data, key)
		if err != nil {
			return nil, fmt.Errorf("decrypt: %w", err)
		}

		result[i] = &commonpb.Payload{}
		if err := result[i].Unmarshal(decrypted); err != nil {
			return nil, fmt.Errorf("unmarshal: %w", err)
		}
	}
	return result, nil
}

func encrypt(plaintext, key []byte) ([]byte, error) {
	block, err := aes.NewCipher(key)
	if err != nil {
		return nil, err
	}
	aesGCM, err := cipher.NewGCM(block)
	if err != nil {
		return nil, err
	}
	nonce := make([]byte, aesGCM.NonceSize())
	if _, err := io.ReadFull(rand.Reader, nonce); err != nil {
		return nil, err
	}
	return aesGCM.Seal(nonce, nonce, plaintext, nil), nil
}

func decrypt(ciphertext, key []byte) ([]byte, error) {
	block, err := aes.NewCipher(key)
	if err != nil {
		return nil, err
	}
	aesGCM, err := cipher.NewGCM(block)
	if err != nil {
		return nil, err
	}
	nonceSize := aesGCM.NonceSize()
	if len(ciphertext) < nonceSize {
		return nil, fmt.Errorf("ciphertext too short")
	}
	nonce, ciphertext := ciphertext[:nonceSize], ciphertext[nonceSize:]
	return aesGCM.Open(nil, nonce, ciphertext, nil)
}

// NewEncryptedDataConverter wraps the default converter with encryption
func NewEncryptedDataConverter(keyID string, key []byte) converter.DataConverter {
	return converter.NewCodecDataConverter(
		converter.GetDefaultDataConverter(),
		NewCodec(keyID, key),
	)
}
```

### Namespace-Level RBAC

```yaml
# Temporal authorization configuration
# Part of Temporal server config
authorization:
  # JWT-based authorizer
  jwtKeyProvider:
    keySourceURIs:
      - "https://auth.company.com/.well-known/jwks.json"
    refreshInterval: 5m
  
  # Claim mapper maps JWT claims to Temporal permissions
  claimMapper:
    # Plugin-based claim mapper
    plugin:
      name: "custom-claim-mapper"
  
  # Authorizer configuration
  authorizer:
    # Default deny
    defaultAllow: false

---
# Example: Kubernetes RBAC for tctl access
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: temporal-admin
rules:
  - apiGroups: [""]
    resources: ["secrets"]
    resourceNames: ["temporal-admin-tls"]
    verbs: ["get"]

---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: temporal-admin-binding
subjects:
  - kind: Group
    name: "platform-team"
    apiGroup: rbac.authorization.k8s.io
roleRef:
  kind: ClusterRole
  name: temporal-admin
  apiGroup: rbac.authorization.k8s.io
```

### Audit Logging

```go
// audit.go - Audit logging interceptor for Temporal workers
package audit

import (
	"context"
	"log/slog"
	"time"

	"go.temporal.io/sdk/interceptor"
	"go.temporal.io/sdk/workflow"
)

type AuditInterceptor struct {
	interceptor.WorkerInterceptorBase
	logger *slog.Logger
}

func NewAuditInterceptor(logger *slog.Logger) *AuditInterceptor {
	return &AuditInterceptor{logger: logger}
}

func (a *AuditInterceptor) InterceptActivity(ctx context.Context, next interceptor.ActivityInboundInterceptor) interceptor.ActivityInboundInterceptor {
	return &auditActivityInbound{
		ActivityInboundInterceptorBase: interceptor.ActivityInboundInterceptorBase{Next: next},
		logger:                         a.logger,
	}
}

type auditActivityInbound struct {
	interceptor.ActivityInboundInterceptorBase
	logger *slog.Logger
}

func (a *auditActivityInbound) ExecuteActivity(ctx context.Context, in *interceptor.ExecuteActivityInput) (interface{}, error) {
	info := workflow.GetActivityInfo(ctx)
	
	a.logger.Info("activity.started",
		"workflowID", info.WorkflowExecution.ID,
		"runID", info.WorkflowExecution.RunID,
		"activityType", info.ActivityType.Name,
		"taskQueue", info.TaskQueue,
		"attempt", info.Attempt,
		"timestamp", time.Now().UTC().Format(time.RFC3339),
	)

	result, err := a.Next.ExecuteActivity(ctx, in)

	if err != nil {
		a.logger.Warn("activity.failed",
			"workflowID", info.WorkflowExecution.ID,
			"activityType", info.ActivityType.Name,
			"error", err.Error(),
		)
	} else {
		a.logger.Info("activity.completed",
			"workflowID", info.WorkflowExecution.ID,
			"activityType", info.ActivityType.Name,
		)
	}

	return result, err
}
```

---

## Summary Checklist

Before going to production, verify:

- [ ] `numHistoryShards` set correctly (cannot change later) — use 512+ for scale
- [ ] mTLS enabled between all components
- [ ] Dynamic config loaded and validated
- [ ] Database backups automated and tested restore
- [ ] Elasticsearch ILM configured
- [ ] Worker HPA configured with custom metrics
- [ ] Pod Disruption Budgets on all Temporal server components
- [ ] Anti-affinity rules spread pods across AZs
- [ ] Health checks configured (liveness + readiness)
- [ ] Prometheus scraping configured
- [ ] Grafana dashboards imported
- [ ] Alerting rules deployed
- [ ] Network policies applied
- [ ] Data encryption via custom data converter
- [ ] CI/CD pipeline includes replay tests
- [ ] Graceful shutdown timeout >= max activity duration
- [ ] `terminationGracePeriodSeconds` >= worker stop timeout
