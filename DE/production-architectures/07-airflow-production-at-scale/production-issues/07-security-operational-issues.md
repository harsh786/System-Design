# Production Issues 91-100: Security, Compliance & Operational Issues

---

## Issue #91: RBAC Misconfiguration Exposing Sensitive DAGs

**Symptoms:**
- Users can see/trigger DAGs they shouldn't have access to
- Intern accidentally triggered production pipeline
- Connection credentials visible to unauthorized users
- Audit shows unauthorized DAG modifications

**Root Cause:**
- Default Airflow has no DAG-level access control
- All users get `Admin` role (lazy setup)
- RBAC not configured or too permissive
- Custom roles not created per team

**Fix:**
```python
# Create team-based RBAC roles
# 1. Via Airflow CLI:
# airflow roles create TeamA_Editor
# airflow roles add-perms TeamA_Editor --resource DAG:team_a_* --action can_read
# airflow roles add-perms TeamA_Editor --resource DAG:team_a_* --action can_edit

# 2. Via webserver_config.py (FAB-based RBAC)
from airflow.security import permissions
from airflow.www.fab_security.manager import AUTH_DB

AUTH_TYPE = AUTH_DB  # Or AUTH_OAUTH, AUTH_LDAP

# Define custom roles programmatically
CUSTOM_ROLES = {
    'TeamA_Editor': {
        'permissions': [
            (permissions.ACTION_CAN_READ, permissions.RESOURCE_DAG),
            (permissions.ACTION_CAN_EDIT, permissions.RESOURCE_DAG),
            (permissions.ACTION_CAN_READ, permissions.RESOURCE_TASK_INSTANCE),
        ],
        'dag_access': ['team_a_*'],  # Only DAGs with this prefix
    },
    'TeamA_Viewer': {
        'permissions': [
            (permissions.ACTION_CAN_READ, permissions.RESOURCE_DAG),
            (permissions.ACTION_CAN_READ, permissions.RESOURCE_TASK_INSTANCE),
            (permissions.ACTION_CAN_READ, permissions.RESOURCE_DAG_RUN),
        ],
        'dag_access': ['team_a_*'],
    },
}
```

```python
# DAG-level access control
with DAG(
    'team_a_revenue_pipeline',
    access_control={
        'TeamA_Editor': {'can_read', 'can_edit', 'can_delete'},
        'TeamA_Viewer': {'can_read'},
        'Admin': {'can_read', 'can_edit', 'can_delete'},
    },
) as dag:
    pass
```

---

## Issue #92: Secrets Leaked in Logs/XCom

**Symptoms:**
- Database passwords visible in task logs
- API keys stored in XCom table (readable by anyone with DB access)
- Credentials printed in exception tracebacks
- Audit finds secrets in S3 log files

**Root Cause:**
- Developers logging connection strings with passwords
- Exception handling printing full context (includes secrets)
- Environment variables with secrets logged at startup
- No masking configuration for sensitive patterns

**Fix:**
```python
# BAD: Logging secrets
def my_task():
    password = Variable.get('db_password')
    logger.info(f"Connecting with password: {password}")  # LEAKED!
    conn_str = f"postgresql://user:{password}@host/db"
    logger.info(f"Connection string: {conn_str}")         # LEAKED!

# GOOD: Never log secrets
def my_task():
    hook = PostgresHook(postgres_conn_id='warehouse')  # Hook manages secrets
    with hook.get_conn() as conn:
        logger.info("Connected to warehouse successfully")  # No secrets
```

```ini
# airflow.cfg - hide sensitive values
[core]
hide_sensitive_var_conn_fields = True    # Mask in UI and API
sensitive_var_conn_names = password,secret,token,key,api_key,access_key

# Custom filter to mask patterns in logs
[logging]
# Use custom filter:
colored_log_format = [%%(asctime)s] {%%(filename)s:%%(lineno)d} %%(levelname)s - %%(message)s
```

```python
# Custom log filter to mask secrets
import logging
import re

class SecretMaskingFilter(logging.Filter):
    """Mask potential secrets in log messages."""
    PATTERNS = [
        (re.compile(r'password["\s:=]+["\']?([^"\'\s,}]+)'), 'password=***'),
        (re.compile(r'(api[_-]?key)["\s:=]+["\']?([^"\'\s,}]+)'), r'\1=***'),
        (re.compile(r'(token)["\s:=]+["\']?([^"\'\s,}]+)'), r'\1=***'),
        (re.compile(r'(secret)["\s:=]+["\']?([^"\'\s,}]+)'), r'\1=***'),
    ]
    
    def filter(self, record):
        for pattern, replacement in self.PATTERNS:
            record.msg = pattern.sub(replacement, str(record.msg))
        return True
```

---

## Issue #93: No Audit Trail for DAG/Connection Changes

**Symptoms:**
- Cannot determine who modified a connection credential
- No history of DAG pause/unpause actions
- Compliance audit fails: "show me who triggered this pipeline"
- Unauthorized changes undetectable

**Fix:**
```python
# Custom audit logging via Airflow events
from airflow.listeners import hookspec

@hookspec
def on_dag_run_running(dag_run, msg):
    """Log who triggered what."""
    audit_logger.info({
        'event': 'dag_run_started',
        'dag_id': dag_run.dag_id,
        'run_id': dag_run.run_id,
        'triggered_by': dag_run.external_trigger,
        'conf': dag_run.conf,
        'timestamp': datetime.utcnow().isoformat(),
    })
```

```python
# Complete audit DAG for compliance
from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta

def audit_changes(**context):
    """Export audit events to compliance system."""
    from airflow.models import Log
    from airflow.utils.session import provide_session
    
    @provide_session
    def get_recent_events(session=None):
        cutoff = datetime.utcnow() - timedelta(hours=24)
        events = session.query(Log).filter(
            Log.dttm > cutoff,
            Log.event.in_(['trigger', 'cli_task_run', 'delete', 
                          'variable.create', 'variable.edit',
                          'connection.create', 'connection.edit'])
        ).all()
        
        for event in events:
            send_to_compliance_system({
                'timestamp': event.dttm.isoformat(),
                'user': event.owner,
                'action': event.event,
                'dag_id': event.dag_id,
                'extra': event.extra,
            })
    
    get_recent_events()

with DAG('compliance_audit_export', schedule='@hourly', catchup=False) as dag:
    PythonOperator(task_id='export_audit', python_callable=audit_changes)
```

---

## Issue #94: Airflow API Exposed Without Authentication

**Symptoms:**
- Anyone on the network can trigger DAGs via API
- No API key requirement
- Bots/scrapers hitting Airflow API
- Unauthorized DAG triggers from unknown sources

**Fix:**
```ini
# airflow.cfg - enable authentication on API
[api]
auth_backends = airflow.api.auth.backend.basic_auth
# OR for production:
# auth_backends = airflow.api.auth.backend.session
# Use with OAuth/OIDC frontend authentication
```

```yaml
# K8s: Network policy restricting API access
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: airflow-api-access
  namespace: airflow
spec:
  podSelector:
    matchLabels:
      component: webserver
  ingress:
  - from:
    # Only allow from CI/CD namespace and internal networks
    - namespaceSelector:
        matchLabels:
          name: cicd
    - ipBlock:
        cidr: 10.0.0.0/8           # Internal only
    ports:
    - port: 8080
      protocol: TCP
```

```python
# Service account tokens for CI/CD (not shared passwords)
# Create dedicated API user:
# airflow users create --username cicd-bot --role Admin --password $(openssl rand -hex 32)

# CI/CD usage:
import requests

response = requests.post(
    'https://airflow.internal/api/v1/dags/my_dag/dagRuns',
    auth=('cicd-bot', os.environ['AIRFLOW_API_TOKEN']),
    json={'logical_date': '2024-06-01T00:00:00Z'},
)
```

---

## Issue #95: SLA Breach Goes Unnoticed (Silent Failure)

**Symptoms:**
- Pipeline missed its deadline hours ago, no one noticed
- SLA miss recorded in metadata DB but no alert sent
- Dashboard shows green but data is stale
- Business users discover issue before data team

**Root Cause:**
- `sla_miss_callback` not configured
- SLA monitoring depends on scheduler checking (can lag)
- Email-based alerts going to spam or unmonitored mailbox
- No integration with on-call system (PagerDuty)

**Fix:**
```python
from airflow import DAG
from datetime import timedelta

def sla_breach_pagerduty(dag, task_list, blocking_task_list, slas, blocking_tis):
    """Immediately page on-call for SLA breach on critical pipelines."""
    import pypd
    
    pypd.api_key = Variable.get('pagerduty_api_key')
    pypd.EventV2.create(data={
        'routing_key': Variable.get('pagerduty_routing_key'),
        'event_action': 'trigger',
        'payload': {
            'summary': f'SLA BREACH: {dag.dag_id} - Tasks: {[t.task_id for t in task_list]}',
            'severity': 'critical',
            'source': 'airflow',
            'custom_details': {
                'dag_id': dag.dag_id,
                'missed_tasks': [t.task_id for t in task_list],
                'blocking_tasks': [t.task_id for t in blocking_tis] if blocking_tis else [],
                'sla_definitions': str(slas),
            }
        }
    })

with DAG(
    'critical_revenue_report',
    sla_miss_callback=sla_breach_pagerduty,     # Page immediately
    default_args={
        'sla': timedelta(hours=4),               # Each task has 4h SLA
        'on_failure_callback': task_failure_alert,
    },
) as dag:
    pass
```

```python
# Pre-SLA warning (alert at 80% of time budget consumed)
def sla_warning_check(**context):
    """Check if we're running out of time for SLA."""
    dag_run = context['dag_run']
    elapsed = (datetime.utcnow() - dag_run.start_date).total_seconds()
    sla_seconds = 4 * 3600  # 4-hour SLA
    
    if elapsed > sla_seconds * 0.8:  # 80% consumed
        send_slack_warning(f"WARNING: {dag_run.dag_id} has used 80% of SLA time budget!")
```

---

## Issue #96: Unauthorized DAG Trigger via REST API

**Symptoms:**
- DAGs triggered at unexpected times
- Unknown `run_id` patterns in DagRun history
- API access logs show requests from unexpected IPs
- Production pipeline triggered during maintenance window

**Fix:**
```python
# 1. API token-based auth with rotation
# Use service accounts with limited permissions

# 2. Webhook validation for external triggers
from airflow.decorators import dag, task
import hmac
import hashlib

@task
def validate_webhook(request_data: dict, signature: str):
    """Validate webhook came from authorized source."""
    secret = Variable.get('webhook_secret')
    expected_sig = hmac.new(
        secret.encode(), 
        json.dumps(request_data).encode(), 
        hashlib.sha256
    ).hexdigest()
    
    if not hmac.compare_digest(signature, expected_sig):
        raise AirflowFailException("Invalid webhook signature!")
```

```yaml
# 3. Restrict API access via ingress annotations
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  annotations:
    # IP whitelist for API endpoints
    nginx.ingress.kubernetes.io/whitelist-source-range: "10.0.0.0/8,172.16.0.0/12"
    # Rate limiting
    nginx.ingress.kubernetes.io/limit-rps: "10"
spec:
  rules:
  - host: airflow-api.internal.com
    http:
      paths:
      - path: /api/
        pathType: Prefix
        backend:
          service:
            name: airflow-webserver
            port: {number: 8080}
```

---

## Issue #97: Runaway DAG Consuming All Cluster Resources

**Symptoms:**
- One DAG creating thousands of pods (dynamic task explosion)
- Cluster resources completely consumed
- All other DAGs blocked waiting for resources
- No limit on what a single DAG can consume

**Fix:**
```python
# 1. Mandatory resource limits per DAG
with DAG(
    'potentially_explosive_dag',
    max_active_runs=1,                   # Only 1 run at a time
    max_active_tasks=20,                 # Max 20 concurrent tasks from this DAG
) as dag:
    pass
```

```yaml
# 2. K8s: LimitRange prevents any single pod from going crazy
apiVersion: v1
kind: LimitRange
metadata:
  name: airflow-limit-range
  namespace: airflow
spec:
  limits:
  - type: Container
    default:
      cpu: "2"
      memory: "4Gi"
    defaultRequest:
      cpu: "500m"
      memory: "1Gi"
    max:
      cpu: "8"
      memory: "32Gi"           # No pod can request more than 32Gi
  - type: Pod
    max:
      cpu: "16"
      memory: "64Gi"
```

```ini
# 3. Global limits
[core]
max_active_tasks_per_dag = 32            # No DAG can run more than 32 tasks simultaneously
max_active_runs_per_dag = 16             # No DAG can have more than 16 concurrent runs
max_map_length = 1024                    # Dynamic task mapping limit
```

---

## Issue #98: Compliance: GDPR/CCPA Data Retention in Airflow

**Symptoms:**
- Task logs contain PII (customer names, emails in error messages)
- XCom stores customer data references beyond retention period
- Metadata DB holds execution details of data processing pipelines
- Data deletion request cannot be fulfilled (logs still exist)

**Fix:**
```python
# 1. PII scrubbing in logs
import re
import logging

class PIIFilter(logging.Filter):
    """Remove PII from log messages."""
    PATTERNS = [
        (re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'), '[EMAIL_REDACTED]'),
        (re.compile(r'\b\d{3}-\d{2}-\d{4}\b'), '[SSN_REDACTED]'),
        (re.compile(r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b'), '[CARD_REDACTED]'),
        (re.compile(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b'), '[PHONE_REDACTED]'),
    ]
    
    def filter(self, record):
        msg = str(record.msg)
        for pattern, replacement in self.PATTERNS:
            msg = pattern.sub(replacement, msg)
        record.msg = msg
        return True

# Add to logging config
logging.getLogger('airflow.task').addFilter(PIIFilter())
```

```python
# 2. Automated data retention enforcement
with DAG('compliance_data_retention', schedule='@daily') as dag:
    
    @task
    def enforce_log_retention():
        """Delete logs older than retention policy."""
        import boto3
        s3 = boto3.client('s3')
        # Delete task logs older than 90 days
        # (In addition to S3 lifecycle policy as defense in depth)
        
    @task
    def enforce_xcom_retention():
        """Purge XCom entries that might reference customer data."""
        from airflow.models import XCom
        from airflow.utils.session import provide_session
        
        @provide_session
        def purge(session=None):
            cutoff = datetime.utcnow() - timedelta(days=30)
            session.query(XCom).filter(XCom.timestamp < cutoff).delete()
            session.commit()
        purge()
```

---

## Issue #99: On-Call Burnout from Alert Noise

**Symptoms:**
- 200+ Airflow alerts per week
- On-call engineer ignoring alerts (alert fatigue)
- Real issues missed because buried in noise
- Team morale suffering

**Root Cause:**
- Every task failure generates an alert
- No severity differentiation (retryable error = same alert as data loss)
- Alerts for expected behavior (DAG paused intentionally)
- No deduplication or grouping

**Fix:**
```python
# Tiered alerting: only page for genuinely critical issues
def smart_failure_callback(context):
    """Route alerts based on severity and context."""
    ti = context['task_instance']
    dag_tier = context['dag'].tags  # ['tier1'] or ['tier2']
    
    # Don't alert if task will retry
    if ti.try_number < ti.max_tries:
        # Only log, don't alert (it will retry)
        logger.warning(f"Task {ti.task_id} failed, attempt {ti.try_number}/{ti.max_tries}")
        return
    
    # Final failure - determine severity
    if 'tier1' in dag_tier:
        send_pagerduty(context)       # Page immediately
    elif 'tier2' in dag_tier:
        send_slack_critical(context)  # Slack #critical channel
    else:
        send_slack_info(context)      # Slack #airflow-info (low noise)
```

```yaml
# Alertmanager: group and deduplicate
route:
  group_by: ['dag_id', 'alertname']
  group_wait: 60s                    # Wait 60s to group related alerts
  group_interval: 10m                # Don't re-fire for 10 min
  repeat_interval: 4h                # Don't repeat for 4 hours
  
  routes:
  - match:
      severity: critical
    receiver: pagerduty
    group_wait: 10s                  # Critical: fast grouping
    repeat_interval: 30m
  
  - match:
      severity: warning
    receiver: slack-warning
    group_wait: 5m                   # Warning: longer grouping (reduce noise)
    repeat_interval: 24h             # Don't repeat for 24h
```

---

## Issue #100: Post-Incident Review: No Way to Reproduce DAG Run State

**Symptoms:**
- Incident occurred 3 days ago, need to understand what happened
- What data was processed? What version of DAG code ran?
- What were the input parameters? Connection targets?
- Cannot prove to auditors what happened during an incident

**Fix:**
```python
# Comprehensive run metadata capture
from airflow.decorators import task, dag
from datetime import datetime
import json

@task
def capture_run_metadata(**context) -> dict:
    """Capture everything needed to reproduce this run."""
    import subprocess
    
    metadata = {
        'dag_id': context['dag'].dag_id,
        'run_id': context['run_id'],
        'logical_date': str(context['logical_date']),
        'start_date': str(context['dag_run'].start_date),
        'triggered_by': 'schedule' if not context['dag_run'].external_trigger else 'manual',
        'conf': context['dag_run'].conf or {},
        
        # Code version
        'git_commit': subprocess.check_output(
            ['git', 'rev-parse', 'HEAD'], 
            cwd='/opt/airflow/dags'
        ).decode().strip(),
        
        # Runtime environment
        'airflow_version': airflow.__version__,
        'python_version': sys.version,
        'image_tag': os.environ.get('AIRFLOW_IMAGE_TAG', 'unknown'),
        
        # Connections used (without secrets)
        'connections': {
            'warehouse': get_conn_metadata('warehouse'),
            'source_db': get_conn_metadata('source_db'),
        },
        
        # Capture time
        'captured_at': datetime.utcnow().isoformat(),
    }
    
    # Store in immutable audit storage
    store_to_s3(
        f's3://audit-trail/airflow/{context["dag"].dag_id}/{context["run_id"]}/metadata.json',
        json.dumps(metadata, indent=2)
    )
    return metadata

def get_conn_metadata(conn_id: str) -> dict:
    """Get connection metadata without secrets."""
    from airflow.hooks.base import BaseHook
    conn = BaseHook.get_connection(conn_id)
    return {
        'conn_type': conn.conn_type,
        'host': conn.host,
        'schema': conn.schema,
        'port': conn.port,
        # Never include password/login
    }
```

```python
# Immutable execution history for compliance
@task
def record_execution_result(**context):
    """Record what this pipeline produced (for auditability)."""
    result = {
        'dag_id': context['dag'].dag_id,
        'run_id': context['run_id'],
        'logical_date': str(context['logical_date']),
        'completion_time': datetime.utcnow().isoformat(),
        'status': 'success',
        'outputs': {
            'table': 'warehouse.orders',
            'partition': context['ds'],
            'row_count': context['ti'].xcom_pull(key='row_count'),
            'checksum': context['ti'].xcom_pull(key='data_checksum'),
        },
        'data_lineage': {
            'sources': ['s3://raw/orders/', 'pg://source/orders'],
            'transformations': ['deduplicate', 'currency_convert', 'aggregate'],
            'destination': 'redshift://warehouse/orders',
        }
    }
    
    # Write to append-only audit log (S3 with object lock)
    store_to_s3_immutable(
        f's3://audit-trail/execution-records/{context["ds"]}/{context["dag"].dag_id}.json',
        json.dumps(result)
    )
```

---

## Summary: Security & Operational Prevention Checklist

```
[ ] RBAC configured with team-specific roles (not everyone is Admin)
[ ] DAG-level access_control set on all DAGs
[ ] Secrets never logged (PIIFilter + hide_sensitive_var_conn_fields)
[ ] API authentication enabled (not default deny_all or allow_all)
[ ] Network policies restricting API access to known sources
[ ] Audit logging for all administrative actions
[ ] SLA miss callback configured with PagerDuty/OpsGenie integration
[ ] Pre-SLA warning at 80% time budget consumed
[ ] Tiered alerting (critical/warning/info) to reduce noise
[ ] GDPR/CCPA log retention policies enforced automatically
[ ] Run metadata captured for post-incident reproducibility
[ ] Data lineage recorded per execution
[ ] Webhook signature validation for external triggers
[ ] Resource limits (LimitRange + max_active_tasks) preventing runaway DAGs
[ ] On-call alert deduplication and grouping configured
[ ] Fernet key stored in secrets management, rotation tested
[ ] Compliance audit DAG running hourly
[ ] Post-incident review possible from stored metadata
```
