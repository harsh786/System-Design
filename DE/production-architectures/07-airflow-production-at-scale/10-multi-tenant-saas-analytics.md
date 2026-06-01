# Problem 10: Multi-Tenant SaaS Analytics (10K Tenants)

## The Problem

A SaaS company (think Salesforce, HubSpot, Mixpanel) provides analytics dashboards to 10,000+ enterprise customers. Each tenant has:

- Their own data sources, schemas, and ETL logic
- Their own schedule (daily, hourly, or every 15 minutes depending on tier)
- Strict data isolation — tenants must NEVER see each other's data, DAGs, or logs
- Self-service onboarding: add a config row → DAG appears automatically
- Tenant-specific failures must not cascade to other tenants

You cannot write 10,000 DAG files by hand. You need dynamic generation, strict RBAC, resource isolation, and a scheduler that won't collapse under 10K DAGs.

## Scale Numbers

| Metric | Value |
|--------|-------|
| Tenants | 10,000+ |
| DAGs | 10,000+ (dynamically generated) |
| Task instances/day | 500,000+ |
| Basic tier | 1 run/day |
| Pro tier | 1 run/hour |
| Enterprise tier | Every 15 minutes |
| Scheduler parse target | < 30s for full DAG bag |

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Tenant Config Store                           │
│  (PostgreSQL table / YAML in S3 / API endpoint)                     │
│  tenant_id | tier | schedule | connections | namespace | pool        │
└──────────────────────────────────┬──────────────────────────────────┘
                                   │
                    ┌──────────────▼──────────────┐
                    │      DAG Factory Module      │
                    │  (reads config, emits DAGs)  │
                    └──────────────┬──────────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              │                    │                    │
    ┌─────────▼─────────┐ ┌───────▼───────┐ ┌─────────▼─────────┐
    │ tenant_001_etl    │ │tenant_002_etl │ │ tenant_N_etl      │
    │ (Basic: daily)    │ │(Pro: hourly)  │ │ (Ent: 15min)      │
    └─────────┬─────────┘ └───────┬───────┘ └─────────┬─────────┘
              │                    │                    │
              ▼                    ▼                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    KubernetesExecutor                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │ ns: tenant-1 │  │ ns: tenant-2 │  │ ns: tenant-N │              │
│  │ pool: basic  │  │ pool: pro    │  │ pool: ent    │              │
│  │ cpu: 0.5     │  │ cpu: 1       │  │ cpu: 2       │              │
│  └──────────────┘  └──────────────┘  └──────────────┘              │
└─────────────────────────────────────────────────────────────────────┘
              │                    │                    │
              ▼                    ▼                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    Isolated Storage (S3)                             │
│  s3://analytics/tenant-001/   s3://analytics/tenant-002/   ...      │
│  s3://logs/tenant-001/        s3://logs/tenant-002/        ...      │
└─────────────────────────────────────────────────────────────────────┘
```

## Airflow Concepts Taught

### 1. Dynamic DAG Generation

The core technique: a single Python file that generates thousands of DAGs at parse time.

#### Factory Pattern (Production)

```python
# dags/tenant_dag_factory.py
"""
DAG Factory — generates one DAG per active tenant.
This file is parsed by the scheduler. It must be FAST.
"""
import json
import hashlib
from datetime import timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.amazon.aws.operators.s3 import S3CopyObjectOperator
from airflow.utils.dates import days_ago

# CRITICAL: Cache tenant configs. Do NOT query DB on every parse.
# Use Airflow Variables with a short TTL or a local file synced by a separate DAG.
import os

TENANT_CONFIG_PATH = os.environ.get(
    "TENANT_CONFIG_PATH", "/opt/airflow/config/tenants.json"
)

TIER_SCHEDULES = {
    "basic": "@daily",
    "pro": "@hourly",
    "enterprise": "*/15 * * * *",
}

TIER_POOLS = {
    "basic": "basic_pool",
    "pro": "pro_pool",
    "enterprise": "enterprise_pool",
}


def _load_tenant_configs():
    """Load tenant configs from a local JSON file (synced by a config-sync DAG)."""
    try:
        with open(TENANT_CONFIG_PATH, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _create_tenant_dag(tenant: dict) -> DAG:
    """Create a single tenant DAG with isolation settings."""
    tenant_id = tenant["tenant_id"]
    tier = tenant["tier"]
    dag_id = f"tenant_{tenant_id}_analytics"

    default_args = {
        "owner": f"tenant_{tenant_id}",
        "retries": 2 if tier == "enterprise" else 1,
        "retry_delay": timedelta(minutes=2),
        "execution_timeout": timedelta(hours=1),
        "pool": TIER_POOLS[tier],
    }

    dag = DAG(
        dag_id=dag_id,
        default_args=default_args,
        schedule_interval=TIER_SCHEDULES[tier],
        start_date=days_ago(1),
        catchup=False,
        tags=[f"tier:{tier}", f"tenant:{tenant_id}"],
        # Access control — ties DAG to tenant's role
        access_control={
            f"tenant_{tenant_id}_role": {"can_read", "can_edit"},
            "admin_role": {"can_read", "can_edit", "can_delete"},
        },
        doc_md=f"Analytics pipeline for tenant {tenant_id} ({tier} tier)",
    )

    with dag:
        extract = PythonOperator(
            task_id="extract",
            python_callable=_extract_tenant_data,
            op_kwargs={"tenant_id": tenant_id, "config": tenant},
            # KubernetesExecutor: run in tenant's namespace
            executor_config={
                "KubernetesExecutor": {
                    "namespace": f"tenant-{tenant_id}",
                    "labels": {"tenant": tenant_id, "tier": tier},
                    "annotations": {"iam.amazonaws.com/role": tenant.get("iam_role", "")},
                }
            },
        )

        transform = PythonOperator(
            task_id="transform",
            python_callable=_transform_tenant_data,
            op_kwargs={"tenant_id": tenant_id},
            executor_config={
                "KubernetesExecutor": {
                    "namespace": f"tenant-{tenant_id}",
                    "request_memory": "512Mi" if tier == "basic" else "2Gi",
                    "request_cpu": "500m" if tier == "basic" else "1000m",
                }
            },
        )

        load = PythonOperator(
            task_id="load",
            python_callable=_load_tenant_data,
            op_kwargs={"tenant_id": tenant_id, "target": tenant.get("target_schema")},
            executor_config={
                "KubernetesExecutor": {"namespace": f"tenant-{tenant_id}"}
            },
        )

        extract >> transform >> load

    return dag


def _extract_tenant_data(tenant_id: str, config: dict, **kwargs):
    """Extract data using tenant-scoped connection."""
    from airflow.hooks.base import BaseHook
    conn = BaseHook.get_connection(f"tenant_{tenant_id}_source")
    # ... extraction logic using tenant's own credentials
    pass


def _transform_tenant_data(tenant_id: str, **kwargs):
    pass


def _load_tenant_data(tenant_id: str, target: str, **kwargs):
    pass


# --- Generate all DAGs ---
tenants = _load_tenant_configs()
for tenant in tenants:
    dag_obj = _create_tenant_dag(tenant)
    # Register in global namespace so Airflow discovers it
    globals()[dag_obj.dag_id] = dag_obj
```

#### Performance: Config Sync DAG

Never query a database inside the DAG factory during parse time. Instead, sync configs periodically:

```python
# dags/sync_tenant_configs.py
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.utils.dates import days_ago
import json

dag = DAG(
    "sync_tenant_configs",
    schedule_interval="*/5 * * * *",  # Every 5 minutes
    start_date=days_ago(1),
    catchup=False,
    tags=["platform", "internal"],
)


def sync_configs(**kwargs):
    """Pull tenant configs from control plane DB and write to local JSON."""
    from sqlalchemy import create_engine
    import os

    engine = create_engine(os.environ["CONTROL_PLANE_DB_URL"])
    with engine.connect() as conn:
        result = conn.execute(
            "SELECT tenant_id, tier, schedule, iam_role, target_schema, "
            "is_active FROM tenants WHERE is_active = true"
        )
        tenants = [dict(row) for row in result]

    config_path = os.environ.get(
        "TENANT_CONFIG_PATH", "/opt/airflow/config/tenants.json"
    )
    with open(config_path, "w") as f:
        json.dump(tenants, f)

    kwargs["ti"].xcom_push(key="tenant_count", value=len(tenants))


PythonOperator(task_id="sync", python_callable=sync_configs, dag=dag)
```

### 2. RBAC (Role-Based Access Control)

Airflow uses Flask-AppBuilder for its security model. For multi-tenancy, you create a role per tenant that can only see their DAGs.

#### Automated Role Provisioning

```python
# scripts/provision_tenant_rbac.py
"""
Run as part of tenant onboarding. Creates RBAC role + user for the tenant.
"""
from airflow import settings
from airflow.www.security import AirflowSecurityManager
from airflow.models import DagModel
from flask_appbuilder.security.sqla.models import Role, Permission, ViewMenu


def provision_tenant_access(tenant_id: str):
    """Create role with DAG-level permission for a single tenant."""
    session = settings.Session()
    security_manager = AirflowSecurityManager(appbuilder=None)

    role_name = f"tenant_{tenant_id}_role"
    dag_id = f"tenant_{tenant_id}_analytics"

    # Create the role
    role = security_manager.find_role(role_name)
    if not role:
        role = security_manager.add_role(role_name)

    # Grant read/edit on this specific DAG only
    dag_resource = f"DAG:{dag_id}"
    for action in ["can_read", "can_edit"]:
        perm = security_manager.find_permission_view_menu(action, dag_resource)
        if perm and perm not in role.permissions:
            security_manager.add_permission_role(role, perm)

    # Grant read on basic views (DAGs list, task instances, logs)
    base_views = ["DAGs", "Task Instances", "Task Logs"]
    for view in base_views:
        perm = security_manager.find_permission_view_menu("can_read", view)
        if perm:
            security_manager.add_permission_role(role, perm)

    session.commit()
    return role_name


def create_tenant_user(tenant_id: str, email: str):
    """Create a user bound to the tenant role."""
    from airflow.www.app import create_app
    app = create_app()
    with app.app_context():
        sm = app.appbuilder.sm
        role = sm.find_role(f"tenant_{tenant_id}_role")
        user = sm.add_user(
            username=f"tenant_{tenant_id}",
            first_name="Tenant",
            last_name=tenant_id,
            email=email,
            role=role,
            password=None,  # Use OAuth/OIDC instead
        )
    return user
```

### 3. Multi-Tenancy Patterns

#### Pattern A: Namespace Isolation (KubernetesExecutor)

Each tenant's tasks run in a dedicated Kubernetes namespace with network policies:

```yaml
# k8s/tenant-namespace-template.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: tenant-{{ tenant_id }}
  labels:
    app: airflow-tenant
    tenant: "{{ tenant_id }}"
    tier: "{{ tier }}"
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: deny-cross-tenant
  namespace: tenant-{{ tenant_id }}
spec:
  podSelector: {}
  policyTypes:
    - Ingress
    - Egress
  ingress:
    - from:
        - namespaceSelector:
            matchLabels:
              app: airflow-scheduler
  egress:
    - to:
        - namespaceSelector:
            matchLabels:
              name: tenant-{{ tenant_id }}
    - to:  # Allow external data source access
        - ipBlock:
            cidr: 0.0.0.0/0
            except:
              - 10.0.0.0/8  # Block internal cross-tenant traffic
---
apiVersion: v1
kind: ResourceQuota
metadata:
  name: tenant-quota
  namespace: tenant-{{ tenant_id }}
spec:
  hard:
    requests.cpu: "{{ '2' if tier == 'basic' else '8' if tier == 'pro' else '16' }}"
    requests.memory: "{{ '4Gi' if tier == 'basic' else '16Gi' if tier == 'pro' else '64Gi' }}"
    pods: "{{ '5' if tier == 'basic' else '20' if tier == 'pro' else '50' }}"
```

#### Pattern B: Queue-Based Isolation (CeleryExecutor)

```python
# For CeleryExecutor deployments, isolate via dedicated queues
TIER_QUEUES = {
    "basic": "basic_queue",
    "pro": "pro_queue",
    "enterprise": "enterprise_queue",
}

# In DAG factory, set queue per task:
extract = PythonOperator(
    task_id="extract",
    python_callable=_extract_tenant_data,
    queue=TIER_QUEUES[tier],  # Routes to tier-specific workers
)
```

Worker deployment per queue:

```yaml
# docker-compose or Helm values
celery_workers:
  basic:
    replicas: 5
    queues: "basic_queue"
    resources:
      cpu: "1"
      memory: "2Gi"
  pro:
    replicas: 10
    queues: "pro_queue"
    resources:
      cpu: "2"
      memory: "4Gi"
  enterprise:
    replicas: 20
    queues: "enterprise_queue"
    resources:
      cpu: "4"
      memory: "8Gi"
```

#### Pool Configuration for Noisy Neighbor Prevention

```python
# scripts/setup_pools.py
from airflow.models import Pool
from airflow import settings

def configure_tenant_pools():
    session = settings.Session()
    pools = {
        "basic_pool": 50,       # Max 50 concurrent basic tasks
        "pro_pool": 200,        # Max 200 concurrent pro tasks
        "enterprise_pool": 500, # Max 500 concurrent enterprise tasks
    }
    for pool_name, slots in pools.items():
        pool = session.query(Pool).filter(Pool.pool == pool_name).first()
        if not pool:
            pool = Pool(pool=pool_name, slots=slots)
            session.add(pool)
        else:
            pool.slots = slots
    session.commit()
```

### 4. Security Deep Dive

#### Secrets Backend (AWS Secrets Manager)

```python
# airflow.cfg or environment variable
# AIRFLOW__SECRETS__BACKEND=airflow.providers.amazon.aws.secrets.secrets_manager.SecretsManagerBackend
# AIRFLOW__SECRETS__BACKEND_KWARGS={"connections_prefix": "airflow/connections", "variables_prefix": "airflow/variables"}

# Secret naming convention per tenant:
# airflow/connections/tenant_001_source  → tenant's source DB creds
# airflow/connections/tenant_001_target  → tenant's warehouse creds
# airflow/variables/tenant_001_config    → tenant-specific config

# In the DAG, retrieve with standard Airflow API:
from airflow.hooks.base import BaseHook
conn = BaseHook.get_connection(f"tenant_{tenant_id}_source")
# Airflow resolves this from Secrets Manager — tenant never sees another's secrets
```

#### Connection Isolation Enforcement

```python
# plugins/tenant_isolation_plugin.py
"""
Plugin that validates tasks only access their own tenant's connections.
"""
from airflow.plugins_manager import AirflowPlugin
from airflow.listeners import hookimpl


class TenantIsolationListener:
    @hookimpl
    def on_task_instance_running(self, task_instance, session):
        """Verify task only uses connections scoped to its tenant."""
        dag_id = task_instance.dag_id
        if not dag_id.startswith("tenant_"):
            return

        tenant_id = dag_id.split("_")[1]
        # Audit: log which connections this task attempts to use
        # In production, wrap BaseHook.get_connection to enforce prefix


class TenantIsolationPlugin(AirflowPlugin):
    name = "tenant_isolation"
    listeners = [TenantIsolationListener()]
```

### 5. Performance at 10K DAGs

#### Critical airflow.cfg Settings

```ini
[core]
# MUST enable for 10K DAGs — stores serialized DAGs in DB
# so webserver doesn't need to parse DAG files
store_serialized_dags = True
min_serialization_update_interval = 30

[scheduler]
# Number of processes to parse DAG files in parallel
parsing_processes = 8

# How often to re-scan the DAG directory for new files
dag_dir_list_interval = 300  # 5 minutes (not default 5 seconds!)

# How often to re-parse a DAG file
min_file_process_interval = 60  # Don't re-parse more than once per minute

# Max DAGs per file parsing loop
file_parsing_sort_mode = modified_time  # Parse recently changed first

[webserver]
# With serialization, webserver reads from DB — much faster
store_dag_code = True
```

#### .airflowignore

```
# .airflowignore — exclude non-DAG files from parsing
tests/
scripts/
plugins/
__pycache__/
*.pyc
README.md
```

#### DAG File Optimization

```python
# BAD — imports heavy libraries at module level (happens on every parse)
import pandas as pd
import numpy as np
from great_expectations import ...

# GOOD — import inside the callable (only runs at task execution time)
def _transform_tenant_data(tenant_id: str, **kwargs):
    import pandas as pd  # Only imported when task actually runs
    import numpy as np
    # ... transform logic
```

## Production Implementation: Tenant Onboarding Flow

```python
# dags/tenant_onboarding.py
"""
Triggered via API when a new tenant signs up.
Provisions all isolation infrastructure for the tenant.
"""
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.cncf.kubernetes.operators.kubernetes_pod import KubernetesPodOperator
from airflow.utils.dates import days_ago
from datetime import timedelta

dag = DAG(
    "tenant_onboarding",
    schedule_interval=None,  # Triggered via API only
    start_date=days_ago(1),
    catchup=False,
    tags=["platform", "onboarding"],
)


def create_namespace(tenant_id: str, tier: str, **kwargs):
    """Create K8s namespace with network policies and resource quotas."""
    from kubernetes import client, config
    config.load_incluster_config()
    v1 = client.CoreV1Api()

    ns = client.V1Namespace(
        metadata=client.V1ObjectMeta(
            name=f"tenant-{tenant_id}",
            labels={"tenant": tenant_id, "tier": tier},
        )
    )
    v1.create_namespace(body=ns)


def create_secrets(tenant_id: str, **kwargs):
    """Store tenant credentials in secrets backend."""
    import boto3
    sm = boto3.client("secretsmanager")
    # Create placeholder — tenant fills via self-service UI
    sm.create_secret(
        Name=f"airflow/connections/tenant_{tenant_id}_source",
        SecretString='{"conn_type": "postgres", "host": "", "login": "", "password": ""}',
        Tags=[{"Key": "tenant", "Value": tenant_id}],
    )


def register_in_config(tenant_id: str, tier: str, **kwargs):
    """Add tenant to the config store so DAG factory picks it up."""
    from sqlalchemy import create_engine
    import os
    engine = create_engine(os.environ["CONTROL_PLANE_DB_URL"])
    with engine.begin() as conn:
        conn.execute(
            "INSERT INTO tenants (tenant_id, tier, is_active, created_at) "
            "VALUES (%s, %s, true, NOW())",
            (tenant_id, tier),
        )


def provision_rbac(tenant_id: str, **kwargs):
    """Create RBAC role for the tenant."""
    from scripts.provision_tenant_rbac import provision_tenant_access
    provision_tenant_access(tenant_id)


with dag:
    t_ns = PythonOperator(
        task_id="create_namespace",
        python_callable=create_namespace,
        op_kwargs={"tenant_id": "{{ dag_run.conf['tenant_id'] }}", "tier": "{{ dag_run.conf['tier'] }}"},
    )
    t_secrets = PythonOperator(
        task_id="create_secrets",
        python_callable=create_secrets,
        op_kwargs={"tenant_id": "{{ dag_run.conf['tenant_id'] }}"},
    )
    t_config = PythonOperator(
        task_id="register_config",
        python_callable=register_in_config,
        op_kwargs={"tenant_id": "{{ dag_run.conf['tenant_id'] }}", "tier": "{{ dag_run.conf['tier'] }}"},
    )
    t_rbac = PythonOperator(
        task_id="provision_rbac",
        python_callable=provision_rbac,
        op_kwargs={"tenant_id": "{{ dag_run.conf['tenant_id'] }}"},
    )

    [t_ns, t_secrets] >> t_config >> t_rbac
```

Trigger via API:
```bash
curl -X POST "https://airflow.internal/api/v1/dags/tenant_onboarding/dagRuns" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"conf": {"tenant_id": "acme_corp", "tier": "pro"}}'
```

## Production Handling

### Tenant-Specific Failure Isolation

```python
# In the DAG factory, configure callbacks per tenant
def _on_failure(context):
    """Tenant-scoped failure handling — never alert other tenants."""
    tenant_id = context["dag"].dag_id.split("_")[1]
    # Route to tenant's Slack/PagerDuty, not the platform team
    webhook = get_tenant_webhook(tenant_id)
    send_alert(webhook, context)


default_args = {
    "on_failure_callback": _on_failure,
    # Tenant failures don't trigger platform-wide alerts
}
```

### SLA Monitoring Per Tier

```python
# dags/sla_monitor.py
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.utils.dates import days_ago
from airflow.models import DagRun
from airflow import settings
from datetime import datetime, timedelta

dag = DAG("sla_monitor", schedule_interval="*/10 * * * *", start_date=days_ago(1), catchup=False)

SLA_THRESHOLDS = {
    "basic": timedelta(hours=6),      # Must complete within 6h of schedule
    "pro": timedelta(hours=1),        # Must complete within 1h
    "enterprise": timedelta(minutes=30),  # Must complete within 30min
}


def check_slas(**kwargs):
    session = settings.Session()
    now = datetime.utcnow()

    for tier, threshold in SLA_THRESHOLDS.items():
        # Find running DAGs of this tier that exceed SLA
        breached = (
            session.query(DagRun)
            .filter(DagRun.dag_id.like("tenant_%"))
            .filter(DagRun.state == "running")
            .filter(DagRun.execution_date < now - threshold)
            .all()
        )
        for run in breached:
            tenant_id = run.dag_id.split("_")[1]
            alert_sla_breach(tenant_id, tier, run)


PythonOperator(task_id="check", python_callable=check_slas, dag=dag)
```

### Scaling the Scheduler

For 10K DAGs, a single scheduler is insufficient. Use multiple schedulers (Airflow 2.x+):

```yaml
# Helm values for Airflow chart
scheduler:
  replicas: 3  # Multiple schedulers with HA
  resources:
    requests:
      cpu: "4"
      memory: "8Gi"
  env:
    - name: AIRFLOW__SCHEDULER__PARSING_PROCESSES
      value: "8"
    - name: AIRFLOW__SCHEDULER__MIN_FILE_PROCESS_INTERVAL
      value: "60"
    - name: AIRFLOW__SCHEDULER__DAG_DIR_LIST_INTERVAL
      value: "300"
    - name: AIRFLOW__CORE__STORE_SERIALIZED_DAGS
      value: "True"
```

### Noisy Neighbor Prevention Checklist

| Control | Mechanism |
|---------|-----------|
| CPU/Memory limits | K8s ResourceQuota per namespace |
| Concurrent tasks | Airflow Pools per tier |
| DB connections | PgBouncer with per-pool limits |
| Storage | S3 prefix isolation + IAM policies |
| Network | K8s NetworkPolicy per namespace |
| Scheduling priority | `priority_weight` in DAG factory |

```python
# Priority weight in DAG factory
default_args = {
    "priority_weight": {"basic": 1, "pro": 5, "enterprise": 10}[tier],
    "weight_rule": "absolute",
}
```

## Key Takeaways

1. **Never query external systems during DAG parsing** — sync configs to a local file, read that file in the factory. Parsing must be fast and side-effect-free.

2. **DAG serialization is non-negotiable at scale** — without it, every webserver/scheduler process parses all 10K DAGs independently.

3. **Isolation is layered** — RBAC for UI visibility, namespaces for compute, secrets backend for credentials, S3 prefixes for data, network policies for network.

4. **Pools prevent noisy neighbors** — a misbehaving basic tenant cannot consume all executor slots and starve enterprise tenants.

5. **Self-service onboarding is a DAG itself** — triggered via API, it provisions namespace, secrets, config entry, and RBAC in one atomic workflow.

6. **Monitor per-tier SLAs separately** — a basic tenant missing a 6-hour window is not the same severity as an enterprise tenant missing a 30-minute window.

7. **Multiple schedulers + tuned intervals** — `min_file_process_interval=60`, `dag_dir_list_interval=300`, `parsing_processes=8`, and 3 scheduler replicas keep 10K DAGs responsive.
