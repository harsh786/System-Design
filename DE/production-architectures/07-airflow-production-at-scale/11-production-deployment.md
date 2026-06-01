# Production Deployment - Airflow at Billions Scale

## Deployment Architecture

### Option Comparison

| Criteria | Self-Managed (K8s) | AWS MWAA | GCP Cloud Composer | Astronomer |
|----------|-------------------|----------|-------------------|------------|
| Control | Full | Limited | Limited | High |
| Ops Burden | High | Low | Low | Medium |
| Cost (at scale) | Lowest | Highest | High | Medium |
| Customization | Unlimited | Constrained | Constrained | High |
| Upgrade Speed | You decide | AWS timeline | GCP timeline | Fast |
| Multi-cloud | Yes | No | No | Yes |
| SLA | Self-managed | 99.9% | 99.5% | 99.95% |

### Decision Matrix

```
Choose Self-Managed K8s when:
  - Running 10,000+ DAG runs/day
  - Need custom executors or plugins
  - Multi-cloud or hybrid requirement
  - Cost optimization is critical at scale
  - Team has strong K8s expertise

Choose MWAA when:
  - AWS-native shop, moderate scale
  - Small platform team (< 3 engineers)
  - Standard Airflow usage patterns
  - Willing to pay premium for less ops

Choose Cloud Composer when:
  - GCP-native, heavy BigQuery/Dataflow usage
  - Want tight GCP IAM integration
  - Moderate scale (< 5000 DAG runs/day)

Choose Astronomer when:
  - Want managed but need customization
  - Multi-cloud strategy
  - Need enterprise support + SLAs
  - Want faster version upgrades than cloud providers
```

---

## Kubernetes Deployment with Helm

### 1. Official Helm Chart Configuration

```yaml
# values-prod.yaml - Production Airflow Helm Configuration
# Chart: apache-airflow/airflow (official)

# ============================================================
# EXECUTOR CONFIGURATION
# ============================================================
executor: CeleryKubernetesExecutor
# CeleryKubernetes: Celery for fast small tasks, K8s for heavy/isolated tasks

# ============================================================
# SCHEDULER
# ============================================================
scheduler:
  replicas: 3  # HA scheduler (requires Airflow 2.x)
  resources:
    requests:
      cpu: "2"
      memory: "4Gi"
    limits:
      cpu: "4"
      memory: "8Gi"
  
  podDisruptionBudget:
    enabled: true
    minAvailable: 2
  
  args: ["bash", "-c", "exec airflow scheduler"]
  
  livenessProbe:
    initialDelaySeconds: 30
    timeoutSeconds: 20
    failureThreshold: 5
    periodSeconds: 60
    command:
      - sh
      - -c
      - |
        CONNECTION_CHECK_MAX_COUNT=0 exec airflow jobs check --job-type SchedulerJob --local
  
  extraEnv:
    - name: AIRFLOW__SCHEDULER__MIN_FILE_PROCESS_INTERVAL
      value: "30"
    - name: AIRFLOW__SCHEDULER__DAG_DIR_LIST_INTERVAL
      value: "60"
    - name: AIRFLOW__SCHEDULER__PARSING_PROCESSES
      value: "4"
    - name: AIRFLOW__SCHEDULER__MAX_DAGRUNS_TO_CREATE_PER_LOOP
      value: "20"
    - name: AIRFLOW__SCHEDULER__MAX_DAGRUNS_PER_LOOP_TO_SCHEDULE
      value: "40"
  
  nodeSelector:
    node-role: airflow-control-plane
  tolerations:
    - key: "dedicated"
      operator: "Equal"
      value: "airflow"
      effect: "NoSchedule"

# ============================================================
# WEBSERVER
# ============================================================
webserver:
  replicas: 3
  resources:
    requests:
      cpu: "1"
      memory: "2Gi"
    limits:
      cpu: "2"
      memory: "4Gi"
  
  service:
    type: ClusterIP
    ports:
      - name: airflow-ui
        port: 8080
  
  podDisruptionBudget:
    enabled: true
    minAvailable: 2
  
  defaultUser:
    enabled: false  # Disable default user in production
  
  extraEnv:
    - name: AIRFLOW__WEBSERVER__WORKERS
      value: "4"
    - name: AIRFLOW__WEBSERVER__WEB_SERVER_WORKER_TIMEOUT
      value: "300"
    - name: AIRFLOW__WEBSERVER__EXPOSE_CONFIG
      value: "False"
    - name: AIRFLOW__WEBSERVER__RBAC
      value: "True"

# ============================================================
# WORKERS (Celery)
# ============================================================
workers:
  replicas: 5
  
  resources:
    requests:
      cpu: "2"
      memory: "4Gi"
    limits:
      cpu: "4"
      memory: "8Gi"
  
  keda:
    enabled: true
    minReplicaCount: 3
    maxReplicaCount: 50
    pollingInterval: 10
    triggers:
      - type: celery
        metadata:
          broker: "redis"
          queueName: "default"
          queueLength: "5"  # Scale up when queue > 5
  
  podDisruptionBudget:
    enabled: true
    minAvailable: 3
  
  terminationGracePeriodSeconds: 600  # Allow running tasks to finish
  
  extraEnv:
    - name: AIRFLOW__CELERY__WORKER_CONCURRENCY
      value: "16"
    - name: AIRFLOW__CELERY__WORKER_AUTOSCALE
      value: "24,8"
  
  nodeSelector:
    node-role: airflow-worker
  tolerations:
    - key: "workload"
      operator: "Equal"
      value: "airflow-worker"
      effect: "NoSchedule"

# ============================================================
# TRIGGERER (for deferrable operators)
# ============================================================
triggerer:
  replicas: 2
  resources:
    requests:
      cpu: "500m"
      memory: "1Gi"
    limits:
      cpu: "1"
      memory: "2Gi"
  
  podDisruptionBudget:
    enabled: true
    minAvailable: 1
  
  extraEnv:
    - name: AIRFLOW__TRIGGERER__DEFAULT_CAPACITY
      value: "1000"

# ============================================================
# REDIS
# ============================================================
redis:
  enabled: false  # Use external ElastiCache

# ============================================================
# POSTGRESQL
# ============================================================
postgresql:
  enabled: false  # Use external RDS

# ============================================================
# DATABASE (External)
# ============================================================
data:
  metadataConnection:
    user: airflow_prod
    pass: ""  # Pulled from secret
    protocol: postgresql+psycopg2
    host: airflow-prod.cluster-xxxxx.us-east-1.rds.amazonaws.com
    port: 5432
    db: airflow_metadata
    sslmode: require
  
  brokerUrl: ""  # Pulled from secret
  brokerUrlSecretName: airflow-redis-secret

# ============================================================
# PGBOUNCER
# ============================================================
pgbouncer:
  enabled: true
  replicas: 3
  maxClientConn: 200
  metadataPoolSize: 15
  resultBackendPoolSize: 10
  
  resources:
    requests:
      cpu: "250m"
      memory: "256Mi"
    limits:
      cpu: "500m"
      memory: "512Mi"

# ============================================================
# GITSYNC
# ============================================================
dags:
  gitSync:
    enabled: true
    repo: git@github.com:company/airflow-dags.git
    branch: main
    subPath: "dags"
    depth: 1
    wait: 30  # seconds between syncs
    
    sshKeySecret: airflow-git-ssh-secret
    knownHosts: |
      github.com ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQ...
    
    containerName: git-sync
    resources:
      requests:
        cpu: "100m"
        memory: "128Mi"
      limits:
        cpu: "200m"
        memory: "256Mi"

# ============================================================
# LOGGING
# ============================================================
logs:
  persistence:
    enabled: false  # Use remote logging
  
env:
  - name: AIRFLOW__LOGGING__REMOTE_LOGGING
    value: "True"
  - name: AIRFLOW__LOGGING__REMOTE_BASE_LOG_FOLDER
    value: "s3://company-airflow-logs/prod"
  - name: AIRFLOW__LOGGING__REMOTE_LOG_CONN_ID
    value: "aws_default"
```

---

### 2. Multi-Environment Setup

```yaml
# values-dev.yaml (overrides)
scheduler:
  replicas: 1
  resources:
    requests: { cpu: "500m", memory: "1Gi" }
    limits: { cpu: "1", memory: "2Gi" }

workers:
  replicas: 2
  keda:
    enabled: false

webserver:
  replicas: 1

triggerer:
  replicas: 1

# Reduced parsing for faster iteration
extraEnv:
  - name: AIRFLOW__SCHEDULER__MIN_FILE_PROCESS_INTERVAL
    value: "10"
```

```yaml
# values-staging.yaml (overrides)
scheduler:
  replicas: 2

workers:
  replicas: 3
  keda:
    enabled: true
    maxReplicaCount: 10

webserver:
  replicas: 2
```

```bash
# Deployment commands per environment
helm upgrade --install airflow apache-airflow/airflow \
  -f values-prod.yaml \
  -f values-${ENV}.yaml \
  --namespace airflow-${ENV} \
  --version 1.11.0 \
  --timeout 10m \
  --wait
```

---

### 3. GitSync for DAG Deployment

**How it works:** A sidecar container (`git-sync`) runs alongside scheduler/workers, periodically pulling from a Git repo and exposing DAG files via a shared volume.

```
┌─────────────────────────────────────────────┐
│  Scheduler Pod                              │
│  ┌──────────────┐    ┌──────────────────┐   │
│  │  Scheduler   │◄───│  git-sync        │   │
│  │  Container   │    │  (sidecar)       │   │
│  └──────────────┘    └────────┬─────────┘   │
│         ▲                     │             │
│         │    Shared Volume    │             │
│         └─────────────────────┘             │
└─────────────────────────────────────────────┘
                                │
                                ▼
                    ┌──────────────────┐
                    │  Git Repository  │
                    │  (main branch)   │
                    └──────────────────┘
```

**Branch Strategy:**
```
feature/* → develop → staging → main
                         │          │
                         ▼          ▼
                    staging env  production env
```

**Private Repo Authentication (SSH):**
```bash
# Create SSH key secret
kubectl create secret generic airflow-git-ssh-secret \
  --from-file=gitSshKey=/path/to/deploy_key \
  -n airflow-prod
```

---

### 4. CI/CD Pipeline

```yaml
# .github/workflows/airflow-dags.yml
name: Airflow DAG CI/CD

on:
  pull_request:
    paths: ['dags/**', 'plugins/**', 'tests/**']
  push:
    branches: [main, staging]

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install apache-airflow==2.8.1 pytest pylint
          pip install -r requirements.txt
      
      - name: DAG Import Validation
        run: |
          python -c "
          import sys
          from airflow.models import DagBag
          dag_bag = DagBag(dag_folder='dags/', include_examples=False)
          if dag_bag.import_errors:
              for path, error in dag_bag.import_errors.items():
                  print(f'ERROR in {path}: {error}')
              sys.exit(1)
          print(f'Successfully loaded {len(dag_bag.dags)} DAGs')
          "
      
      - name: Lint DAGs
        run: pylint dags/ --disable=C0114,C0115,C0116 --fail-under=8
      
      - name: Run Tests
        run: pytest tests/ -v --tb=short
      
      - name: Check DAG complexity
        run: |
          python scripts/check_dag_complexity.py \
            --max-tasks 100 \
            --max-dag-duration 24h

  deploy-staging:
    needs: validate
    if: github.ref == 'refs/heads/staging'
    runs-on: ubuntu-latest
    steps:
      - name: Trigger GitSync
        run: echo "GitSync auto-pulls from staging branch"
      
      - name: Smoke Test
        run: |
          # Wait for sync, then validate via API
          sleep 60
          curl -sf https://airflow-staging.internal/api/v1/dags | jq '.total_entries'

  deploy-prod:
    needs: validate
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    steps:
      - name: Notify
        run: |
          echo "Production DAGs will sync via GitSync in ~30s"
      
      - name: Monitor Deployment
        run: |
          # Check for import errors post-deploy
          sleep 90
          ERRORS=$(curl -sf https://airflow.internal/api/v1/importErrors | jq '.total_entries')
          if [ "$ERRORS" -gt 0 ]; then
            echo "::error::Import errors detected post-deploy"
            exit 1
          fi
```

**Rollback Strategy:**
```bash
# Revert DAG deployment (git revert + push)
git revert HEAD --no-edit && git push origin main

# For infrastructure rollback
helm rollback airflow <revision> -n airflow-prod
```

---

### 5. Blue-Green / Canary Deployments

**Blue-Green for Version Upgrades:**

```bash
# 1. Deploy green environment alongside blue
helm install airflow-green apache-airflow/airflow \
  -f values-prod.yaml \
  --set webserver.service.type=ClusterIP \
  -n airflow-green

# 2. Run database migration (alembic)
kubectl exec -it deploy/airflow-green-scheduler -n airflow-green -- \
  airflow db migrate

# 3. Validate green (run subset of DAGs)
# 4. Switch ingress to green
kubectl patch ingress airflow-ingress -p '
  {"spec":{"rules":[{"host":"airflow.company.com",
    "http":{"paths":[{"path":"/","pathType":"Prefix",
      "backend":{"service":{"name":"airflow-green-webserver","port":{"number":8080}}}}]}}]}}'

# 5. Drain and decommission blue
helm uninstall airflow-blue -n airflow-blue
```

**Database Migration Strategy:**
```bash
# Always backup before migration
pg_dump -h $RDS_HOST -U airflow_prod airflow_metadata > backup_$(date +%s).sql

# Run migration with timeout
airflow db migrate --timeout 300

# Verify
airflow db check-migrations
```

---

### 6. Docker Image Management

```dockerfile
# Dockerfile.airflow-prod
# Multi-stage build for optimized production image

# Stage 1: Build dependencies
FROM apache/airflow:2.8.1-python3.11 AS builder

USER root
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

USER airflow
COPY requirements.txt /tmp/
RUN pip install --no-cache-dir --user -r /tmp/requirements.txt

# Stage 2: Production image
FROM apache/airflow:2.8.1-python3.11

USER root
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

USER airflow

# Copy installed packages from builder
COPY --from=builder /home/airflow/.local /home/airflow/.local

# Copy plugins and config
COPY plugins/ /opt/airflow/plugins/
COPY config/airflow.cfg /opt/airflow/airflow.cfg

# Health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
  CMD curl -f http://localhost:8080/health || exit 1

ENV PATH="/home/airflow/.local/bin:${PATH}"
```

```yaml
# Image CI pipeline
# .github/workflows/build-image.yml
name: Build Airflow Image

on:
  push:
    paths: ['Dockerfile*', 'requirements.txt', 'plugins/**']
    branches: [main]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Build Image
        run: |
          docker build -t $ECR_REPO:${{ github.sha }} -f Dockerfile.airflow-prod .
      
      - name: Security Scan (Trivy)
        uses: aquasecurity/trivy-action@master
        with:
          image-ref: '${{ env.ECR_REPO }}:${{ github.sha }}'
          severity: 'CRITICAL,HIGH'
          exit-code: '1'
      
      - name: Push to ECR
        run: |
          aws ecr get-login-password | docker login --username AWS --password-stdin $ECR_REPO
          docker push $ECR_REPO:${{ github.sha }}
          docker tag $ECR_REPO:${{ github.sha }} $ECR_REPO:latest
          docker push $ECR_REPO:latest
```

---

## Configuration Management

### airflow.cfg Production Settings

```ini
[core]
executor = CeleryKubernetesExecutor
parallelism = 256                    # Max concurrent task instances globally
max_active_tasks_per_dag = 64        # Per-DAG concurrency
max_active_runs_per_dag = 16
dagbag_import_timeout = 120
dag_file_processor_timeout = 180
killed_task_cleanup_time = 300

[scheduler]
min_file_process_interval = 30       # Don't re-parse DAG files too frequently
dag_dir_list_interval = 60
parsing_processes = 4
max_dagruns_to_create_per_loop = 20
schedule_after_task_execution = True  # Faster scheduling

[celery]
worker_concurrency = 16
worker_prefetch_multiplier = 1       # Prevent task hoarding
operation_timeout = 10
task_track_started = True
broker_connection_retry_on_startup = True

[webserver]
expose_config = False
rbac = True
session_lifetime_minutes = 720
workers = 4
worker_refresh_interval = 1800

[logging]
remote_logging = True
colored_console_log = False
log_fetch_timeout_sec = 10

[metrics]
statsd_on = True
statsd_host = datadog-agent.monitoring.svc.cluster.local
statsd_port = 8125
statsd_prefix = airflow
```

### Secrets Management

```python
# AWS Secrets Manager Backend
# In airflow.cfg or environment:
# AIRFLOW__SECRETS__BACKEND=airflow.providers.amazon.aws.secrets.secrets_manager.SecretsManagerBackend
# AIRFLOW__SECRETS__BACKEND_KWARGS={"connections_prefix": "airflow/connections", "variables_prefix": "airflow/variables"}

# Store a connection:
aws secretsmanager create-secret \
  --name airflow/connections/my_postgres \
  --secret-string "postgresql://user:pass@host:5432/db"

# HashiCorp Vault Backend
# AIRFLOW__SECRETS__BACKEND=airflow.providers.hashicorp.secrets.vault.VaultBackend
# AIRFLOW__SECRETS__BACKEND_KWARGS={"connections_path": "airflow/connections", "url": "https://vault.internal:8200", "auth_type": "kubernetes"}
```

---

## Database Setup

### PostgreSQL for Metadata (Terraform)

```hcl
# terraform/rds.tf
resource "aws_db_instance" "airflow_metadata" {
  identifier     = "airflow-prod-metadata"
  engine         = "postgres"
  engine_version = "15.4"
  instance_class = "db.r6g.2xlarge"  # 8 vCPU, 64 GB RAM

  allocated_storage     = 500
  max_allocated_storage = 2000
  storage_type          = "gp3"
  storage_encrypted     = true
  kms_key_id            = aws_kms_key.airflow.arn

  db_name  = "airflow_metadata"
  username = "airflow_admin"
  password = random_password.rds_password.result

  multi_az               = true
  db_subnet_group_name   = aws_db_subnet_group.airflow.name
  vpc_security_group_ids = [aws_security_group.airflow_rds.id]

  backup_retention_period = 14
  backup_window           = "03:00-04:00"
  maintenance_window      = "sun:04:00-sun:05:00"

  performance_insights_enabled = true
  monitoring_interval          = 60

  parameter_group_name = aws_db_parameter_group.airflow.name

  deletion_protection = true

  tags = {
    Environment = "production"
    Service     = "airflow"
  }
}

resource "aws_db_parameter_group" "airflow" {
  family = "postgres15"
  name   = "airflow-prod"

  parameter {
    name  = "max_connections"
    value = "500"
  }
  parameter {
    name  = "shared_buffers"
    value = "{DBInstanceClassMemory/4}"  # 25% of RAM
  }
  parameter {
    name  = "work_mem"
    value = "65536"  # 64MB
  }
  parameter {
    name  = "log_min_duration_statement"
    value = "1000"  # Log queries > 1s
  }
}

# Read replica for UI queries
resource "aws_db_instance" "airflow_read_replica" {
  identifier          = "airflow-prod-metadata-ro"
  replicate_source_db = aws_db_instance.airflow_metadata.identifier
  instance_class      = "db.r6g.xlarge"
  
  performance_insights_enabled = true
}
```

### Redis for Celery Broker

```hcl
# terraform/elasticache.tf
resource "aws_elasticache_replication_group" "airflow_broker" {
  replication_group_id = "airflow-prod-broker"
  description          = "Airflow Celery broker"

  engine               = "redis"
  engine_version       = "7.0"
  node_type            = "cache.r6g.large"
  num_cache_clusters   = 3  # 1 primary + 2 replicas

  automatic_failover_enabled = true
  multi_az_enabled           = true
  at_rest_encryption_enabled = true
  transit_encryption_enabled = true

  subnet_group_name  = aws_elasticache_subnet_group.airflow.name
  security_group_ids = [aws_security_group.airflow_redis.id]

  parameter_group_name = "default.redis7"

  snapshot_retention_limit = 7
  snapshot_window          = "02:00-03:00"
  maintenance_window       = "sun:03:00-sun:04:00"
}
```

---

## Network Architecture

```hcl
# terraform/vpc.tf
resource "aws_vpc" "airflow" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true
}

# Private subnets for workers and databases
resource "aws_subnet" "private" {
  count             = 3
  vpc_id            = aws_vpc.airflow.id
  cidr_block        = "10.0.${count.index + 1}.0/24"
  availability_zone = data.aws_availability_zones.available.names[count.index]
  
  tags = { Name = "airflow-private-${count.index}" }
}

# Public subnets for ALB only
resource "aws_subnet" "public" {
  count                   = 3
  vpc_id                  = aws_vpc.airflow.id
  cidr_block              = "10.0.${count.index + 10}.0/24"
  availability_zone       = data.aws_availability_zones.available.names[count.index]
  map_public_ip_on_launch = true
}

# NAT Gateway for worker external access
resource "aws_nat_gateway" "main" {
  allocation_id = aws_eip.nat.id
  subnet_id     = aws_subnet.public[0].id
}
```

```yaml
# Kubernetes NetworkPolicy
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: airflow-worker-policy
  namespace: airflow-prod
spec:
  podSelector:
    matchLabels:
      component: worker
  policyTypes: [Ingress, Egress]
  ingress:
    - from:
        - podSelector:
            matchLabels:
              component: scheduler
      ports:
        - port: 8793  # log serving
  egress:
    - to:
        - podSelector:
            matchLabels:
              component: redis
      ports:
        - port: 6379
    - to:  # Allow external API calls via NAT
        - ipBlock:
            cidr: 0.0.0.0/0
            except: [169.254.169.254/32]  # Block metadata endpoint
```

---

## Production Checklist (Pre-Launch)

```markdown
### Infrastructure
- [ ] Multi-AZ RDS with automated backups (14-day retention)
- [ ] ElastiCache Redis with automatic failover
- [ ] PgBouncer deployed and tested under load
- [ ] VPC with private subnets, NAT, security groups locked down
- [ ] KMS encryption for secrets, RDS, ElastiCache, S3 logs
- [ ] Terraform state in S3 with DynamoDB locking

### Airflow Configuration
- [ ] Remote logging to S3 configured and verified
- [ ] Secrets backend (Vault/SecretsManager) working
- [ ] RBAC enabled, default user disabled
- [ ] Fernet key rotated from defaults, stored in secrets manager
- [ ] expose_config = False
- [ ] Parallelism and concurrency tuned for expected load

### Kubernetes / Helm
- [ ] PodDisruptionBudgets on all components
- [ ] Resource requests AND limits set on every container
- [ ] KEDA or HPA configured for workers
- [ ] Node affinity separates control plane from workers
- [ ] terminationGracePeriodSeconds allows task completion
- [ ] GitSync with SSH key (not token) for DAG delivery
- [ ] Liveness and readiness probes configured

### CI/CD
- [ ] DAG import validation in PR checks
- [ ] Automated tests for critical DAGs
- [ ] Image security scanning (zero critical CVEs)
- [ ] Rollback procedure documented and tested
- [ ] Database migration tested in staging first

### Monitoring & Alerting
- [ ] StatsD/Datadog metrics flowing
- [ ] Alerts: scheduler heartbeat, task failures > threshold
- [ ] Alerts: worker queue depth, DB connections, disk usage
- [ ] Log aggregation (CloudWatch/ELK) configured
- [ ] Runbooks for common failure scenarios

### Security
- [ ] Network policies restrict pod-to-pod traffic
- [ ] IAM roles for service accounts (IRSA) — no static credentials
- [ ] TLS everywhere (ingress, Redis, RDS)
- [ ] Webserver behind VPN or IP allowlist
- [ ] Image pulled from private ECR only
- [ ] No secrets in DAG code or environment variables

### Operational Readiness
- [ ] Load test completed (2x expected peak)
- [ ] Failover tested: kill scheduler, kill worker, RDS failover
- [ ] Backup restoration tested (RDS snapshot → restore)
- [ ] On-call rotation established
- [ ] Upgrade runbook documented (minor + major versions)
- [ ] Capacity planning for next 6 months
```
