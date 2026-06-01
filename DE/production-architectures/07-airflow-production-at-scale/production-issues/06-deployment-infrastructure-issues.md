# Production Issues 76-90: Deployment & Infrastructure Issues

---

## Issue #76: GitSync Delay Causing Stale DAGs

**Symptoms:**
- DAG changes deployed to Git but not visible in Airflow for minutes
- Different scheduler/worker pods running different DAG versions
- Merge to main → expected behavior change not happening
- Users confused: "I deployed but nothing changed"

**Root Cause:**
- GitSync `wait` interval too long (default 60s)
- GitSync sidecar crashed silently (not restarting)
- Git repo authentication expired (token/SSH key)
- Large repo takes time to clone (shallow clone not configured)

**Fix:**
```yaml
# Helm values - optimize GitSync
dags:
  gitSync:
    enabled: true
    repo: git@github.com:company/airflow-dags.git
    branch: main
    rev: HEAD
    depth: 1                             # Shallow clone (MUCH faster)
    maxFailures: 3                       # Restart sidecar after 3 consecutive failures
    wait: 30                             # Sync every 30 seconds
    subPath: "dags"                      # Only sync dags/ directory
    resources:
      requests:
        cpu: 50m
        memory: 64Mi
      limits:
        cpu: 200m
        memory: 256Mi
    # SSH key for private repo
    sshKeySecret: airflow-git-ssh-key
```

```yaml
# Monitor GitSync health
# Sidecar liveness probe (custom):
containers:
- name: git-sync
  livenessProbe:
    exec:
      command:
      - sh
      - -c
      - "test $(find /dags -maxdepth 1 -mmin -5 | wc -l) -gt 0"
    periodSeconds: 60
    failureThreshold: 3
```

---

## Issue #77: Helm Upgrade Causes Downtime

**Symptoms:**
- During Helm upgrade, scheduler pods restart simultaneously
- 30-60 second gap where no scheduling happens
- Workers lose connection to broker during upgrade
- UI unavailable during webserver restart

**Fix:**
```yaml
# Rolling update strategy - zero downtime
scheduler:
  replicas: 3
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxUnavailable: 1              # Only 1 scheduler down at a time
      maxSurge: 0

webserver:
  replicas: 3
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxUnavailable: 1
      maxSurge: 1                    # Extra pod during transition

worker:
  replicas: 20
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxUnavailable: 5              # 5 workers at a time
      maxSurge: 5                    # 5 extra during transition
  terminationGracePeriodSeconds: 7200  # 2h to finish tasks
```

```bash
# Safe upgrade procedure:
#!/bin/bash
set -e

echo "Step 1: Upgrade with controlled rollout..."
helm upgrade airflow apache-airflow/airflow \
  --namespace airflow \
  --values values-prod.yaml \
  --wait \
  --timeout 30m \
  --atomic                           # Rollback if upgrade fails

echo "Step 2: Verify health..."
kubectl rollout status deployment/airflow-scheduler -n airflow --timeout=300s
kubectl rollout status deployment/airflow-webserver -n airflow --timeout=300s

echo "Step 3: Check for import errors..."
kubectl exec deployment/airflow-scheduler -n airflow -- airflow dags list-import-errors
```

---

## Issue #78: Database Migration Breaking During Upgrade

**Symptoms:**
- `airflow db upgrade` fails with constraint violation
- Scheduler won't start: "database needs migration"
- Partial migration left database in broken state
- Helm upgrade stuck in "pending-install"

**Fix:**
```yaml
# Helm: Use migration job (runs before component startup)
migrateDatabaseJob:
  enabled: true                          # Run db upgrade as a pre-upgrade Job
  jobAnnotations:
    "helm.sh/hook": pre-upgrade
    "helm.sh/hook-weight": "1"
    "helm.sh/hook-delete-policy": before-hook-creation
  resources:
    requests:
      memory: "1Gi"
      cpu: "500m"
```

```bash
# Manual recovery from failed migration:
# 1. Find current Alembic revision
kubectl exec -it postgres-pod -- psql -U airflow -d airflow -c "SELECT * FROM alembic_version;"

# 2. Check what migrations are pending
airflow db check-migrations

# 3. If stuck, manually stamp to known good version and retry
airflow db downgrade --to-revision <last_good_revision> --yes
airflow db upgrade

# 4. Nuclear option: restore from backup
pg_restore -h $DB_HOST -U airflow -d airflow_restored backup.dump
# Then swap databases
```

---

## Issue #79: Docker Image Build Too Slow (30+ Minutes)

**Symptoms:**
- CI/CD pipeline takes 30+ minutes due to image build
- Every DAG change requires full image rebuild
- Layer cache invalidated by requirements.txt changes
- Image size 5GB+ (includes unnecessary packages)

**Fix:**
```dockerfile
# Multi-stage optimized Dockerfile
# Stage 1: Build dependencies (cached unless requirements change)
FROM apache/airflow:2.7.0-python3.11 AS builder

USER root
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

USER airflow
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --user -r /tmp/requirements.txt

# Stage 2: Production image (lean)
FROM apache/airflow:2.7.0-python3.11

# Copy only installed packages from builder
COPY --from=builder /home/airflow/.local /home/airflow/.local

# Copy DAGs last (changes most frequently → better layer caching)
COPY --chown=airflow:root dags/ /opt/airflow/dags/
COPY --chown=airflow:root plugins/ /opt/airflow/plugins/

USER airflow
```

```yaml
# Use GitSync instead of baking DAGs into image
# DAGs change daily, image changes monthly
# Separate concerns: Image = runtime, GitSync = DAGs
dags:
  gitSync:
    enabled: true    # DAGs from Git, not from image
```

---

## Issue #80: Secret Rotation Breaking Connections

**Symptoms:**
- After secret rotation (automated or manual), all DAGs fail
- `OperationalError: authentication failed`
- Connections cached with old credentials
- No mechanism to pick up new secrets without restart

**Fix:**
```ini
# Use secrets backend (not metadata DB) for connections
[secrets]
backend = airflow.providers.amazon.aws.secrets.secrets_manager.SecretsManagerBackend
backend_kwargs = {
    "connections_prefix": "airflow/connections",
    "variables_prefix": "airflow/variables",
    "connections_lookup_pattern": null,
    "full_url_mode": false
}
```

```python
# AWS Secrets Manager: rotation-safe pattern
# Secret name: airflow/connections/warehouse
# Secret value:
{
    "conn_type": "postgres",
    "host": "prod-warehouse.rds.amazonaws.com",
    "schema": "analytics",
    "login": "airflow_user",
    "password": "rotated_password_v2",
    "port": 5432
}
# Airflow fetches from Secrets Manager on EACH connection request
# No caching of secrets by default → rotation is transparent
```

```ini
# If caching is enabled, set TTL
[secrets]
backend_kwargs = {
    "connections_prefix": "airflow/connections",
    "connections_lookup_pattern": null,
    "full_url_mode": false,
    "cache_ttl": 300           # Re-fetch secret every 5 minutes
}
```

---

## Issue #81: Multi-Environment Promotion (Dev→Staging→Prod) Broken

**Symptoms:**
- DAG works in dev, fails in staging due to different connections
- Environment-specific configs hardcoded in DAG files
- Promoting a DAG requires manual changes
- No confidence that staging validates prod behavior

**Fix:**
```python
# Environment-aware DAG pattern
import os

ENV = os.environ.get('AIRFLOW_ENV', 'dev')  # Set via Helm values per env

# Connection IDs are same name across environments
# But resolve to different actual connections per env
CONN_WAREHOUSE = 'warehouse'  # Same conn_id everywhere
# Dev: points to dev DB, Prod: points to prod DB

# Environment-specific configuration
CONFIG = {
    'dev': {
        'schedule': None,                    # Manual trigger only
        'max_active_runs': 1,
        'pool': 'dev_pool',
        'email_on_failure': False,
    },
    'staging': {
        'schedule': '@daily',
        'max_active_runs': 2,
        'pool': 'staging_pool',
        'email_on_failure': True,
    },
    'prod': {
        'schedule': '0 6 * * *',
        'max_active_runs': 3,
        'pool': 'prod_pool',
        'email_on_failure': True,
    },
}[ENV]

with DAG(
    'etl_pipeline',
    schedule=CONFIG['schedule'],
    max_active_runs=CONFIG['max_active_runs'],
) as dag:
    pass
```

```yaml
# Helm values per environment:
# values-dev.yaml
env:
- name: AIRFLOW_ENV
  value: "dev"
- name: AIRFLOW__CORE__DAGS_ARE_PAUSED_AT_CREATION
  value: "True"

# values-prod.yaml
env:
- name: AIRFLOW_ENV
  value: "prod"
- name: AIRFLOW__CORE__DAGS_ARE_PAUSED_AT_CREATION
  value: "False"
```

---

## Issue #82: Terraform/IaC Drift from Manual Airflow Changes

**Symptoms:**
- Variables/Connections created in UI not in Terraform state
- Next Terraform apply deletes manually created resources
- Team members making ad-hoc changes through UI
- No audit trail of configuration changes

**Fix:**
```hcl
# Terraform: manage Airflow resources as code
resource "airflow_pool" "warehouse" {
  name        = "warehouse_pool"
  slots       = 10
  description = "Limit concurrent warehouse connections"
}

resource "airflow_variable" "config" {
  key   = "pipeline_config"
  value = jsonencode({
    tables = ["orders", "customers", "products"]
    batch_size = 10000
  })
}

# Import existing resources:
# terraform import airflow_pool.warehouse warehouse_pool
```

```yaml
# Alternative: GitOps approach
# Store pools/variables/connections in YAML, apply via DAG
# configs/pools.yaml:
pools:
  warehouse_pool:
    slots: 10
    description: "Warehouse connection limit"
  api_pool:
    slots: 5
    description: "External API rate limit"
```

---

## Issue #83: Certificate Expiry Breaking HTTPS/TLS Connections

**Symptoms:**
- All external API calls suddenly fail with SSL errors
- `SSLCertVerificationError: certificate has expired`
- Happens at 3 AM when cert expires (no one watching)
- Multiple DAGs affected simultaneously

**Fix:**
```yaml
# cert-manager for automatic renewal (K8s)
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: airflow-tls
  namespace: airflow
spec:
  secretName: airflow-tls
  issuerRef:
    name: letsencrypt-prod
    kind: ClusterIssuer
  dnsNames:
  - airflow.company.com
  renewBefore: 720h              # Renew 30 days before expiry
```

```promql
# Alert on certificate expiry (30 days before)
(cert_manager_certificate_expiration_timestamp_seconds - time()) / 86400 < 30
```

```python
# For client certificates in connections:
# Store in Secrets Manager with rotation policy
# Set Airflow connection extra:
{
    "ssl_cert": "/path/to/client.crt",
    "ssl_key": "/path/to/client.key",
    "ssl_ca": "/path/to/ca.crt"
}
# Mount from K8s Secret (auto-rotated by cert-manager)
```

---

## Issue #84: Log Storage Costs Exploding

**Symptoms:**
- S3/GCS bill for Airflow logs: $5K+/month
- Logs stored in STANDARD storage class indefinitely
- Debug-level logging in production
- Large tasks writing GB of logs per run

**Fix:**
```ini
# 1. Set appropriate log level
[logging]
logging_level = INFO                     # Not DEBUG in production!
fab_logging_level = WARNING
```

```json
// 2. S3 lifecycle policy for logs
{
    "Rules": [
        {
            "ID": "AirflowLogLifecycle",
            "Status": "Enabled",
            "Filter": {"Prefix": "task-logs/"},
            "Transitions": [
                {
                    "Days": 7,
                    "StorageClass": "STANDARD_IA"
                },
                {
                    "Days": 30,
                    "StorageClass": "GLACIER"
                }
            ],
            "Expiration": {
                "Days": 90
            }
        }
    ]
}
```

```python
# 3. Reduce log verbosity in tasks
import logging

def data_processing_task(**context):
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)  # Not DEBUG
    
    # BAD: Logging every row
    for row in million_rows:
        logger.debug(f"Processing row: {row}")  # 1M log lines!
    
    # GOOD: Log summary
    logger.info(f"Processing {len(million_rows)} rows...")
    process_all(million_rows)
    logger.info(f"Completed. Processed {len(million_rows)} rows successfully.")
```

---

## Issue #85: Airflow Version Pinning and Dependency Hell

**Symptoms:**
- `pip install` conflicts between Airflow and user packages
- `apache-airflow-providers-*` version mismatch
- Import errors after adding new Python package
- "Works on my machine" but fails in Airflow image

**Fix:**
```
# Use constraints file (CRITICAL for Airflow)
# Airflow has very specific dependency requirements

# requirements.txt
--constraint "https://raw.githubusercontent.com/apache/airflow/constraints-2.7.0/constraints-3.11.txt"

apache-airflow==2.7.0
apache-airflow-providers-amazon==8.7.0
apache-airflow-providers-postgres==5.6.0
pandas==2.1.0
pyarrow==13.0.0
```

```dockerfile
# Install with constraints
RUN pip install --no-cache-dir \
    --constraint "https://raw.githubusercontent.com/apache/airflow/constraints-${AIRFLOW_VERSION}/constraints-${PYTHON_VERSION}.txt" \
    -r /requirements.txt
```

```bash
# Check for conflicts before deploying:
pip check  # Reports broken dependencies
pip list --outdated  # Shows available updates
```

---

## Issue #86: Load Balancer Health Check Failing (503 Errors)

**Symptoms:**
- ALB/NLB returning 503 to users
- Webserver pods marked unhealthy
- Health check endpoint timing out
- UI works directly but not through load balancer

**Fix:**
```yaml
# Airflow webserver health check endpoint: /health
webserver:
  livenessProbe:
    httpGet:
      path: /health
      port: 8080
    initialDelaySeconds: 30          # Give webserver time to start
    periodSeconds: 10
    timeoutSeconds: 5
    failureThreshold: 5              # 5 failures before killing pod
  readinessProbe:
    httpGet:
      path: /health
      port: 8080
    initialDelaySeconds: 15
    periodSeconds: 5
    timeoutSeconds: 3
    failureThreshold: 3
```

```yaml
# ALB target group settings (AWS)
# If using AWS ALB Ingress Controller:
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  annotations:
    alb.ingress.kubernetes.io/healthcheck-path: /health
    alb.ingress.kubernetes.io/healthcheck-interval-seconds: "15"
    alb.ingress.kubernetes.io/healthcheck-timeout-seconds: "5"
    alb.ingress.kubernetes.io/healthy-threshold-count: "2"
    alb.ingress.kubernetes.io/unhealthy-threshold-count: "3"
    alb.ingress.kubernetes.io/target-type: ip
```

---

## Issue #87: PodDisruptionBudget Not Set (Voluntary Eviction Kills All)

**Symptoms:**
- Cluster upgrade/maintenance evicts ALL Airflow pods simultaneously
- Node drain kills all schedulers at once
- Zero availability during routine maintenance

**Fix:**
```yaml
# PodDisruptionBudget for each component
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: airflow-scheduler-pdb
  namespace: airflow
spec:
  minAvailable: 2                        # Always keep 2 schedulers running
  selector:
    matchLabels:
      component: scheduler
---
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: airflow-webserver-pdb
  namespace: airflow
spec:
  minAvailable: 1                        # At least 1 webserver always up
  selector:
    matchLabels:
      component: webserver
---
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: airflow-worker-pdb
  namespace: airflow
spec:
  maxUnavailable: "25%"                  # Max 25% of workers evicted at once
  selector:
    matchLabels:
      component: worker
```

---

## Issue #88: Namespace Resource Quota Hit

**Symptoms:**
- KubernetesExecutor can't create worker pods
- Error: `forbidden: exceeded quota`
- Suddenly no tasks can run despite having pool slots
- Admin unaware quota was set/hit

**Fix:**
```yaml
# Set appropriate resource quota for Airflow namespace
apiVersion: v1
kind: ResourceQuota
metadata:
  name: airflow-quota
  namespace: airflow
spec:
  hard:
    requests.cpu: "200"                  # 200 CPU cores total
    requests.memory: "800Gi"            # 800 GB memory total
    limits.cpu: "400"
    limits.memory: "1600Gi"
    pods: "500"                          # Max 500 pods
    persistentvolumeclaims: "50"
```

```promql
# Monitor quota usage
kube_resourcequota{namespace="airflow", type="used"} / 
kube_resourcequota{namespace="airflow", type="hard"} > 0.80
```

---

## Issue #89: Init Container Failures Blocking Pod Start

**Symptoms:**
- Worker pods stuck in `Init:CrashLoopBackOff`
- GitSync init container failing
- DB check init container timing out
- Pods never reach `Running` state

**Fix:**
```yaml
# Increase init container timeouts and add retry logic
initContainers:
- name: wait-for-db
  image: busybox:latest
  command: ['sh', '-c', 
    'for i in $(seq 1 60); do nc -z postgres-service 5432 && exit 0 || sleep 5; done; exit 1']
  # Retry 60 times with 5s interval = 5 min max wait

- name: wait-for-redis  
  image: busybox:latest
  command: ['sh', '-c',
    'for i in $(seq 1 30); do nc -z redis-service 6379 && exit 0 || sleep 5; done; exit 1']

- name: db-migrations
  image: apache/airflow:2.7.0
  command: ['airflow', 'db', 'check-migrations']
  # Only checks, doesn't run migrations (handled by separate Job)
```

---

## Issue #90: Terraform State Lock Preventing Airflow Infrastructure Changes

**Symptoms:**
- `terraform apply` hangs waiting for state lock
- Previous apply crashed leaving stale lock
- Emergency infrastructure change blocked
- Team members stepping on each other's changes

**Fix:**
```bash
# Force unlock (use with caution!)
terraform force-unlock <LOCK_ID>

# Prevention: Use remote state with proper locking
# backend.tf
terraform {
  backend "s3" {
    bucket         = "company-terraform-state"
    key            = "airflow/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "terraform-locks"        # DynamoDB for locking
    encrypt        = true
  }
}
```

```yaml
# Better: Use separate state files per component
# airflow-infra/   → RDS, Redis, VPC (rarely changes)
# airflow-app/     → Helm release, configs (changes often)
# airflow-monitoring/ → Prometheus rules, dashboards

# This reduces lock contention and blast radius
```

---

## Summary: Deployment & Infrastructure Prevention Checklist

```
[ ] GitSync with depth=1, wait=30, and health monitoring
[ ] Rolling update strategy with maxUnavailable=1 for control plane
[ ] Database migration as pre-upgrade Helm hook
[ ] Multi-stage Docker builds, DAGs via GitSync not image
[ ] Secrets backend (Secrets Manager/Vault) not metadata DB
[ ] Environment-aware DAG configuration (env vars, not hardcoded)
[ ] Infrastructure as Code for pools/variables/connections
[ ] Certificate auto-renewal with 30-day advance alerts
[ ] Log lifecycle policies (IA after 7 days, Glacier after 30)
[ ] Pin Airflow version with constraints file
[ ] Health check endpoints properly configured for LB
[ ] PodDisruptionBudgets on all components
[ ] Namespace resource quotas with monitoring
[ ] Init container retry logic with reasonable timeouts
[ ] Separate Terraform state per component
```
