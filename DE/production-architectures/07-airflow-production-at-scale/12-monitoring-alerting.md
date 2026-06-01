# Monitoring & Alerting - Airflow at Billions Scale

## Why Airflow Monitoring is Critical

At production scale, Airflow orchestrates hundreds of thousands of task instances daily. Without comprehensive monitoring:

- **500K+ task instances/day** - manual oversight is physically impossible
- **Pipeline failures at 2 AM** need automated detection and response
- **Resource waste** costs $10K+/month if undetected (idle workers, oversized pods)
- **SLA breaches** = regulatory fines, lost revenue, or broken downstream contracts
- **Cascading failures** - one stuck DAG can starve the entire scheduler queue

The monitoring stack must answer three questions instantly:
1. Is everything running on time?
2. What failed, and why?
3. What's about to fail?

---

## Metrics Architecture

### StatsD Integration

Airflow natively emits metrics via StatsD protocol. Every scheduler loop, task state change, and executor action produces a metric.

**Configuration in `airflow.cfg`:**

```ini
[metrics]
statsd_on = True
statsd_host = statsd-exporter.monitoring.svc.cluster.local
statsd_port = 9125
statsd_prefix = airflow
statsd_allow_list = scheduler,executor,dagrun,dag_processing,task_instance,pool
statsd_custom_client_path =
```

**Key metrics Airflow produces automatically:**

| Category | Metric | Type |
|----------|--------|------|
| Scheduler | `scheduler_heartbeat` | Counter |
| Scheduler | `dagrun.schedule_delay.<dag_id>` | Timing |
| Tasks | `task_instance_duration.<dag_id>.<task_id>` | Timing |
| Tasks | `task_instance_successes` | Counter |
| Tasks | `task_instance_failures` | Counter |
| Executor | `executor.queued_tasks` | Gauge |
| Executor | `executor.running_tasks` | Gauge |
| Pool | `pool.open_slots.<pool_name>` | Gauge |
| DAG Processing | `dag_processing.total_parse_time` | Timing |

**Custom metrics from within DAGs:**

```python
from airflow.metrics.base import Stats

def emit_custom_metrics(**context):
    """Emit business-level metrics from tasks."""
    records_processed = context['ti'].xcom_pull(key='record_count')
    
    Stats.gauge('custom.records_processed.{dag_id}'.format(
        dag_id=context['dag'].dag_id
    ), records_processed)
    
    Stats.incr('custom.pipeline_completions', 1, tags={
        'dag_id': context['dag'].dag_id,
        'environment': 'production'
    })
```

### Prometheus Setup

**StatsD Exporter deployment (Kubernetes):**

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: statsd-exporter
  namespace: monitoring
spec:
  replicas: 2
  selector:
    matchLabels:
      app: statsd-exporter
  template:
    metadata:
      labels:
        app: statsd-exporter
      annotations:
        prometheus.io/scrape: "true"
        prometheus.io/port: "9102"
    spec:
      containers:
      - name: statsd-exporter
        image: prom/statsd-exporter:v0.26.0
        args:
          - --statsd.listen-udp=:9125
          - --statsd.listen-tcp=:9125
          - --web.listen-address=:9102
          - --statsd.mapping-config=/etc/statsd/mapping.yml
          - --statsd.cache-size=10000
        ports:
        - containerPort: 9125
          protocol: UDP
          name: statsd-udp
        - containerPort: 9102
          name: metrics
        volumeMounts:
        - name: mapping-config
          mountPath: /etc/statsd
        resources:
          requests:
            cpu: 200m
            memory: 256Mi
          limits:
            cpu: 500m
            memory: 512Mi
      volumes:
      - name: mapping-config
        configMap:
          name: statsd-mapping
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: statsd-mapping
  namespace: monitoring
data:
  mapping.yml: |
    mappings:
    - match: "airflow.dagrun.schedule_delay.*"
      name: "airflow_dagrun_schedule_delay"
      labels:
        dag_id: "$1"
      timer_type: histogram
      buckets: [1, 5, 10, 30, 60, 120, 300, 600]
    - match: "airflow.task_instance_duration.*.*"
      name: "airflow_task_instance_duration"
      labels:
        dag_id: "$1"
        task_id: "$2"
      timer_type: histogram
      buckets: [10, 30, 60, 120, 300, 600, 1800, 3600]
    - match: "airflow.executor.queued_tasks"
      name: "airflow_executor_queued_tasks"
    - match: "airflow.executor.running_tasks"
      name: "airflow_executor_running_tasks"
    - match: "airflow.pool.open_slots.*"
      name: "airflow_pool_open_slots"
      labels:
        pool: "$1"
    - match: "airflow.scheduler_heartbeat"
      name: "airflow_scheduler_heartbeat_total"
    - match: "airflow.dag_processing.total_parse_time"
      name: "airflow_dag_processing_total_parse_time"
      timer_type: histogram
    - match: "airflow.zombie_tasks_killed"
      name: "airflow_zombie_tasks_killed_total"
```

**ServiceMonitor for Kubernetes:**

```yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: airflow-statsd
  namespace: monitoring
  labels:
    release: prometheus
spec:
  namespaceSelector:
    matchNames:
    - monitoring
  selector:
    matchLabels:
      app: statsd-exporter
  endpoints:
  - port: metrics
    interval: 15s
    scrapeTimeout: 10s
```

---

## Critical Metrics to Monitor

### 1. Scheduler Health

```promql
# Scheduler is alive - heartbeat should increment every 5s
rate(airflow_scheduler_heartbeat_total[1m]) == 0  # ALERT: scheduler dead

# DAG parsing taking too long (blocks scheduling)
airflow_dag_processing_total_parse_time > 120  # seconds

# Import errors prevent DAGs from being scheduled
airflow_dag_processing_import_errors > 0

# Tasks waiting to be scheduled (starvation)
airflow_scheduler_tasks_starving > 50

# Delay between scheduled time and actual execution start
histogram_quantile(0.95, airflow_dagrun_schedule_delay_bucket) > 300
```

### 2. Task Execution

```promql
# Task duration percentiles (detect performance regression)
histogram_quantile(0.50, airflow_task_instance_duration_bucket{dag_id="critical_pipeline"})
histogram_quantile(0.95, airflow_task_instance_duration_bucket{dag_id="critical_pipeline"})
histogram_quantile(0.99, airflow_task_instance_duration_bucket{dag_id="critical_pipeline"})

# Failure rate (rolling 5 min window)
rate(airflow_task_instance_failures_total[5m]) /
  (rate(airflow_task_instance_successes_total[5m]) + rate(airflow_task_instance_failures_total[5m]))

# Zombie tasks (tasks marked running but worker died)
rate(airflow_zombie_tasks_killed_total[5m]) > 0
```

### 3. Worker/Executor

```promql
# Celery worker availability
airflow_celery_worker_online < 3  # below minimum threshold

# Queue depth growing (tasks backing up)
airflow_executor_queued_tasks > 200

# KubernetesExecutor pod launch failures
rate(airflow_kubernetes_executor_pod_launch_errors_total[5m]) > 0

# Pool exhaustion
airflow_pool_open_slots{pool="default_pool"} == 0
```

### 4. System Resources

```promql
# Metadata DB connection pool saturation
airflow_db_pool_connections_used / airflow_db_pool_connections_max > 0.85

# Metadata DB query latency
histogram_quantile(0.95, airflow_db_query_duration_seconds_bucket) > 2

# Worker memory usage (per pod in K8s)
container_memory_usage_bytes{namespace="airflow", container="worker"} /
  container_spec_memory_limit_bytes{namespace="airflow", container="worker"} > 0.85
```

---

## Grafana Dashboards

### Dashboard 1: Executive Overview

```json
{
  "dashboard": {
    "title": "Airflow - Executive Overview",
    "uid": "airflow-executive",
    "timezone": "UTC",
    "refresh": "30s",
    "panels": [
      {
        "title": "Task Success Rate (24h)",
        "type": "gauge",
        "gridPos": {"h": 6, "w": 6, "x": 0, "y": 0},
        "targets": [{
          "expr": "sum(increase(airflow_task_instance_successes_total[24h])) / (sum(increase(airflow_task_instance_successes_total[24h])) + sum(increase(airflow_task_instance_failures_total[24h]))) * 100",
          "legendFormat": "Success %"
        }],
        "fieldConfig": {
          "defaults": {
            "thresholds": {
              "steps": [
                {"value": 0, "color": "red"},
                {"value": 95, "color": "yellow"},
                {"value": 99, "color": "green"}
              ]
            },
            "min": 0, "max": 100, "unit": "percent"
          }
        }
      },
      {
        "title": "Active DAG Runs",
        "type": "stat",
        "gridPos": {"h": 6, "w": 6, "x": 6, "y": 0},
        "targets": [{
          "expr": "airflow_executor_running_tasks",
          "legendFormat": "Running"
        }]
      },
      {
        "title": "SLA Breaches (Today)",
        "type": "stat",
        "gridPos": {"h": 6, "w": 6, "x": 12, "y": 0},
        "targets": [{
          "expr": "sum(increase(airflow_sla_missed_total[24h]))",
          "legendFormat": "SLA Misses"
        }],
        "fieldConfig": {
          "defaults": {
            "thresholds": {
              "steps": [
                {"value": 0, "color": "green"},
                {"value": 1, "color": "red"}
              ]
            }
          }
        }
      },
      {
        "title": "Task Failures (Last Hour)",
        "type": "timeseries",
        "gridPos": {"h": 8, "w": 24, "x": 0, "y": 6},
        "targets": [{
          "expr": "sum by (dag_id) (increase(airflow_task_instance_failures_total[5m]))",
          "legendFormat": "{{dag_id}}"
        }]
      },
      {
        "title": "Scheduler Latency (p95)",
        "type": "timeseries",
        "gridPos": {"h": 8, "w": 12, "x": 0, "y": 14},
        "targets": [{
          "expr": "histogram_quantile(0.95, sum(rate(airflow_dagrun_schedule_delay_bucket[5m])) by (le))",
          "legendFormat": "p95 Schedule Delay"
        }]
      }
    ]
  }
}
```

### Dashboard 2: Scheduler Deep Dive

Key panels:
- DAG parse time trend (line chart, per-file breakdown)
- Scheduling latency heatmap (shows spikes during peak hours)
- Executor queue depth over time
- Scheduler heartbeat gaps (indicates GC pauses or crashes)
- Import errors table (sortable by DAG file)

### Dashboard 3: Worker Performance

Key panels:
- Task duration distribution (histogram heatmap)
- CPU/memory usage per worker pod
- Queue backlog by pool name
- Worker restart events
- Task slot utilization percentage

### Dashboard 4: DAG-Level Detail

Variable: `$dag_id` (dropdown populated from label values)

Key panels:
- Run history (success/fail timeline)
- Task duration box plot per task_id
- SLA tracking vs threshold line
- Upstream dependency wait times

---

## Alerting Rules

### Prometheus Alerting Rules

```yaml
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: airflow-alerts
  namespace: monitoring
  labels:
    release: prometheus
spec:
  groups:
  # ============================================
  # CRITICAL - PagerDuty (immediate response)
  # ============================================
  - name: airflow.critical
    rules:
    - alert: AirflowSchedulerDown
      expr: |
        increase(airflow_scheduler_heartbeat_total[2m]) == 0
      for: 60s
      labels:
        severity: critical
        team: data-platform
      annotations:
        summary: "Airflow scheduler is not responding"
        description: "Scheduler heartbeat has not incremented for 60s. No new tasks will be scheduled."
        runbook_url: "https://runbooks.internal/airflow/scheduler-down"

    - alert: AirflowHighTaskFailureRate
      expr: |
        (
          sum(rate(airflow_task_instance_failures_total[5m]))
          / (sum(rate(airflow_task_instance_successes_total[5m])) + sum(rate(airflow_task_instance_failures_total[5m])))
        ) > 0.10
      for: 5m
      labels:
        severity: critical
        team: data-platform
      annotations:
        summary: "Task failure rate exceeds 10%"
        description: "{{ $value | humanizePercentage }} of tasks are failing over the last 5 minutes."
        runbook_url: "https://runbooks.internal/airflow/high-failure-rate"

    - alert: AirflowSLABreachTier1
      expr: |
        increase(airflow_sla_missed_total{dag_id=~"tier1_.*"}[5m]) > 0
      for: 0s
      labels:
        severity: critical
        team: data-platform
      annotations:
        summary: "SLA breach on Tier-1 pipeline: {{ $labels.dag_id }}"
        description: "Critical pipeline has missed its SLA deadline."
        runbook_url: "https://runbooks.internal/airflow/sla-breach"

    - alert: AirflowMetadataDBConnectionFailure
      expr: |
        airflow_db_pool_connections_used >= airflow_db_pool_connections_max
      for: 30s
      labels:
        severity: critical
        team: data-platform
      annotations:
        summary: "Metadata DB connection pool exhausted"
        description: "All {{ $value }} connections are in use. New tasks cannot be scheduled."
        runbook_url: "https://runbooks.internal/airflow/db-connections"

    - alert: AirflowWorkerPoolExhausted
      expr: |
        airflow_pool_open_slots{pool="default_pool"} == 0
        and airflow_executor_queued_tasks > 50
      for: 2m
      labels:
        severity: critical
        team: data-platform
      annotations:
        summary: "Worker pool exhausted with tasks queued"
        description: "No available slots in default_pool and {{ $value }} tasks queued."
        runbook_url: "https://runbooks.internal/airflow/pool-exhausted"

  # ============================================
  # WARNING - Slack (investigate within 1 hour)
  # ============================================
  - name: airflow.warning
    rules:
    - alert: AirflowDAGParsingErrors
      expr: |
        airflow_dag_processing_import_errors > 0
      for: 5m
      labels:
        severity: warning
        team: data-platform
      annotations:
        summary: "{{ $value }} DAG parsing errors detected"
        description: "Some DAG files have import errors and are not being scheduled."

    - alert: AirflowTaskDurationAnomaly
      expr: |
        histogram_quantile(0.95, rate(airflow_task_instance_duration_bucket[30m]))
        > 2 * histogram_quantile(0.95, rate(airflow_task_instance_duration_bucket[7d] offset 1h))
      for: 15m
      labels:
        severity: warning
        team: data-platform
      annotations:
        summary: "Task duration 2x above normal for {{ $labels.dag_id }}.{{ $labels.task_id }}"
        description: "Current p95 duration is significantly above the 7-day baseline."

    - alert: AirflowPoolHighUtilization
      expr: |
        1 - (airflow_pool_open_slots / (airflow_pool_open_slots + airflow_pool_used_slots)) > 0.80
      for: 10m
      labels:
        severity: warning
        team: data-platform
      annotations:
        summary: "Pool {{ $labels.pool }} at {{ $value | humanizePercentage }} utilization"

    - alert: AirflowTaskRepeatedFailures
      expr: |
        increase(airflow_task_instance_failures_total[30m]) > 3
      for: 0s
      labels:
        severity: warning
        team: data-platform
      annotations:
        summary: "Task {{ $labels.dag_id }}.{{ $labels.task_id }} failed {{ $value }} times in 30m"

    - alert: AirflowScheduleDelayHigh
      expr: |
        histogram_quantile(0.95, sum(rate(airflow_dagrun_schedule_delay_bucket[10m])) by (le)) > 300
      for: 10m
      labels:
        severity: warning
        team: data-platform
      annotations:
        summary: "Scheduling delay p95 is {{ $value }}s (threshold: 300s)"

  # ============================================
  # Recording Rules (pre-compute expensive queries)
  # ============================================
  - name: airflow.recording
    rules:
    - record: airflow:task_success_rate_5m
      expr: |
        sum(rate(airflow_task_instance_successes_total[5m]))
        / (sum(rate(airflow_task_instance_successes_total[5m])) + sum(rate(airflow_task_instance_failures_total[5m])))

    - record: airflow:task_duration_p95_by_dag
      expr: |
        histogram_quantile(0.95, sum(rate(airflow_task_instance_duration_bucket[5m])) by (le, dag_id))

    - record: airflow:pool_utilization
      expr: |
        1 - (airflow_pool_open_slots / (airflow_pool_open_slots + airflow_pool_used_slots + airflow_pool_queued_slots))
```

### PagerDuty / OpsGenie Integration

**Alertmanager configuration:**

```yaml
# alertmanager.yml
global:
  resolve_timeout: 5m

route:
  receiver: 'default-slack'
  group_by: ['alertname', 'dag_id']
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 4h
  routes:
  - match:
      severity: critical
    receiver: 'pagerduty-data-platform'
    continue: true
  - match:
      severity: critical
    receiver: 'slack-critical'
  - match:
      severity: warning
    receiver: 'slack-warning'

receivers:
- name: 'pagerduty-data-platform'
  pagerduty_configs:
  - routing_key: '<PAGERDUTY_INTEGRATION_KEY>'
    severity: '{{ .CommonLabels.severity }}'
    description: '{{ .CommonAnnotations.summary }}'
    details:
      runbook: '{{ .CommonAnnotations.runbook_url }}'
      dag_id: '{{ .CommonLabels.dag_id }}'
      firing: '{{ .Alerts.Firing | len }}'

- name: 'slack-critical'
  slack_configs:
  - api_url: '<SLACK_WEBHOOK_URL>'
    channel: '#airflow-critical'
    title: ':rotating_light: {{ .CommonAnnotations.summary }}'
    text: '{{ .CommonAnnotations.description }}'
    actions:
    - type: button
      text: 'Runbook'
      url: '{{ .CommonAnnotations.runbook_url }}'
    - type: button
      text: 'Airflow UI'
      url: 'https://airflow.internal/home'

- name: 'slack-warning'
  slack_configs:
  - api_url: '<SLACK_WEBHOOK_URL>'
    channel: '#airflow-alerts'
    title: ':warning: {{ .CommonAnnotations.summary }}'
    text: '{{ .CommonAnnotations.description }}'

- name: 'default-slack'
  slack_configs:
  - api_url: '<SLACK_WEBHOOK_URL>'
    channel: '#airflow-info'
```

### Slack Integration - Custom Airflow Callback

```python
"""Custom Airflow callback for rich Slack alerting."""
import json
from datetime import datetime
from airflow.providers.slack.hooks.slack_webhook import SlackWebhookHook


def task_failure_slack_alert(context):
    """Send rich Slack notification on task failure."""
    ti = context['task_instance']
    dag_id = ti.dag_id
    task_id = ti.task_id
    execution_date = context['execution_date'].isoformat()
    log_url = ti.log_url
    exception = context.get('exception', 'Unknown')

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"Task Failure: {dag_id}.{task_id}"}
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*DAG:*\n{dag_id}"},
                {"type": "mrkdwn", "text": f"*Task:*\n{task_id}"},
                {"type": "mrkdwn", "text": f"*Execution Date:*\n{execution_date}"},
                {"type": "mrkdwn", "text": f"*Try Number:*\n{ti.try_number}"},
            ]
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Error:*\n```{str(exception)[:500]}```"}
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "View Logs"},
                    "url": log_url,
                    "style": "danger"
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "View DAG"},
                    "url": f"https://airflow.internal/dags/{dag_id}/grid"
                }
            ]
        }
    ]

    hook = SlackWebhookHook(slack_webhook_conn_id='slack_alerts')
    hook.send(blocks=blocks)


def sla_miss_slack_alert(dag, task_list, blocking_task_list, slas, blocking_tis):
    """SLA miss callback with ownership routing."""
    dag_owner = dag.owner
    channel_map = {
        'data-team-a': '#team-a-alerts',
        'data-team-b': '#team-b-alerts',
        'platform': '#platform-alerts',
    }
    channel = channel_map.get(dag_owner, '#airflow-alerts')

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"SLA BREACH: {dag.dag_id}"}
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"*Missed tasks:* {', '.join(t.task_id for t in task_list)}\n"
                    f"*Blocking tasks:* {', '.join(t.task_id for t in blocking_tis) if blocking_tis else 'None'}\n"
                    f"*Owner:* {dag_owner}"
                )
            }
        }
    ]

    hook = SlackWebhookHook(slack_webhook_conn_id='slack_alerts')
    hook.send(channel=channel, blocks=blocks)
```

**DAG-level usage:**

```python
default_args = {
    'owner': 'data-team-a',
    'on_failure_callback': task_failure_slack_alert,
    'sla': timedelta(hours=2),
}

dag = DAG(
    'tier1_revenue_pipeline',
    default_args=default_args,
    sla_miss_callback=sla_miss_slack_alert,
    schedule_interval='@hourly',
)
```

---

## Log Management

### Structured Logging

**Remote logging configuration (`airflow.cfg`):**

```ini
[logging]
remote_logging = True
remote_log_conn_id = aws_default
remote_base_log_folder = s3://airflow-logs-prod/task-logs
encrypt_s3_logs = True
logging_level = INFO
fab_logging_level = WARNING

[logging]
log_format = [%%(asctime)s] {%%(filename)s:%%(lineno)d} %%(levelname)s - dag_id=%%(dag_id)s | task_id=%%(task_id)s | run_id=%%(run_id)s | %%(message)s
```

**FluentBit DaemonSet for log aggregation:**

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: fluent-bit-config
  namespace: airflow
data:
  fluent-bit.conf: |
    [SERVICE]
        Flush         5
        Log_Level     info
        Parsers_File  parsers.conf

    [INPUT]
        Name              tail
        Path              /var/log/containers/airflow-worker*.log
        Parser            docker
        Tag               airflow.worker.*
        Refresh_Interval  5
        Mem_Buf_Limit     50MB

    [FILTER]
        Name          parser
        Match         airflow.*
        Key_Name      log
        Parser        airflow_structured
        Reserve_Data  On

    [OUTPUT]
        Name            opensearch
        Match           airflow.*
        Host            opensearch.monitoring.svc.cluster.local
        Port            9200
        Index           airflow-logs
        Type            _doc
        Suppress_Type_Name On

  parsers.conf: |
    [PARSER]
        Name        airflow_structured
        Format      regex
        Regex       ^\[(?<timestamp>[^\]]+)\] \{(?<source>[^}]+)\} (?<level>\w+) - dag_id=(?<dag_id>[^ |]*) \| task_id=(?<task_id>[^ |]*) \| run_id=(?<run_id>[^ |]*) \| (?<message>.*)$
        Time_Key    timestamp
        Time_Format %Y-%m-%d %H:%M:%S,%L
```

### Distributed Tracing

**OpenTelemetry integration:**

```python
# In airflow.cfg or environment
# OTEL_TRACES_EXPORTER=otlp
# OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317

# Custom span creation in tasks
from opentelemetry import trace

tracer = trace.get_tracer("airflow.custom")

def traced_etl_task(**context):
    """Task with custom tracing spans."""
    with tracer.start_as_current_span("extract") as span:
        span.set_attribute("source.system", "postgres")
        span.set_attribute("dag_id", context['dag'].dag_id)
        data = extract_data()
        span.set_attribute("records.extracted", len(data))

    with tracer.start_as_current_span("transform"):
        transformed = transform_data(data)

    with tracer.start_as_current_span("load") as span:
        span.set_attribute("destination", "bigquery")
        load_data(transformed)
        span.set_attribute("records.loaded", len(transformed))
```

---

## Incident Response

### Runbooks for Common Issues

#### Scheduler Not Scheduling

```
SYMPTOMS:
- airflow_scheduler_heartbeat_total not incrementing
- New DAG runs not being created
- executor.queued_tasks = 0 despite pending runs

DIAGNOSIS:
1. Check scheduler pod status: kubectl get pods -l component=scheduler -n airflow
2. Check scheduler logs: kubectl logs -l component=scheduler -n airflow --tail=100
3. Check metadata DB connectivity: kubectl exec scheduler-pod -- airflow db check
4. Check DAG parsing: kubectl exec scheduler-pod -- airflow dags list-import-errors

RESOLUTION:
- If OOM killed: increase memory limits, reduce DAG bag size
- If DB connection refused: check PgBouncer/RDS status
- If stuck in loop: restart scheduler (kubectl rollout restart deployment/airflow-scheduler)
- If parsing stuck: identify problematic DAG file from import errors, move to quarantine
```

#### Workers Not Picking Up Tasks

```
SYMPTOMS:
- executor.queued_tasks growing steadily
- executor.running_tasks = 0 or below normal
- Tasks stuck in "queued" state

DIAGNOSIS:
1. Check worker pods: kubectl get pods -l component=worker -n airflow
2. Check Celery broker (Redis): redis-cli -h redis-host ping
3. Check worker connectivity: kubectl exec worker-pod -- celery -A airflow.executors.celery_executor inspect active
4. Check pool slots: airflow pools list

RESOLUTION:
- If Redis down: failover to Redis replica, restart workers after recovery
- If workers CrashLooping: check resource limits, recent DAG changes
- If pool full: increase pool slots or identify stuck tasks consuming slots
```

#### Metadata DB Slow/Full

```
SYMPTOMS:
- airflow_db_query_duration increasing
- Scheduler loop time increasing
- UI extremely slow or timing out

DIAGNOSIS:
1. Check DB metrics: CPU, connections, disk I/O, storage
2. Check long-running queries: SELECT * FROM pg_stat_activity WHERE state = 'active'
3. Check table sizes: SELECT relname, pg_size_pretty(pg_total_relation_size(relid)) FROM pg_catalog.pg_statio_user_tables ORDER BY pg_total_relation_size(relid) DESC

RESOLUTION:
- Run airflow db clean (remove old task instances, DAG runs)
- Increase DB instance size
- Add read replicas for UI queries
- Tune connection pool (pgbouncer max_client_conn)
- Vacuum/analyze large tables
```

#### Redis Broker Disconnect

```
SYMPTOMS:
- Workers reporting broker connection errors
- Tasks queued but not delivered
- Celery flower showing disconnected workers

RESOLUTION:
1. Verify Redis health: redis-cli -h $REDIS_HOST info replication
2. Check memory: redis-cli info memory (maxmemory-policy should be noeviction for broker)
3. If failover needed: update broker_url to replica, restart workers
4. After recovery: clear stale messages with celery purge (carefully)
```

---

## Production Monitoring Checklist

### Initial Setup

- [ ] StatsD exporter deployed and receiving metrics
- [ ] Prometheus scraping StatsD exporter every 15s
- [ ] All four Grafana dashboards imported and functional
- [ ] Alert rules loaded into Prometheus
- [ ] Alertmanager routing configured (critical → PagerDuty, warning → Slack)
- [ ] Remote logging configured and verified (S3/GCS)
- [ ] FluentBit/Fluentd shipping logs to OpenSearch
- [ ] On-call rotation defined for data-platform team

### Per-DAG Onboarding

- [ ] DAG has `on_failure_callback` configured
- [ ] DAG has `sla` defined for critical paths
- [ ] DAG owner matches alerting routing rules
- [ ] DAG pool assignment is correct
- [ ] DAG appears in Grafana dashboard with correct `dag_id` label

### Weekly Review

- [ ] Review task failure trends (any new patterns?)
- [ ] Check scheduler latency trending (degradation over time?)
- [ ] Verify alert noise ratio (too many false positives?)
- [ ] Confirm all Tier-1 pipelines met SLA
- [ ] Review metadata DB growth and plan cleanup
- [ ] Check worker resource utilization (right-size pods)

### Quarterly

- [ ] Load test scheduler at 2x current DAG count
- [ ] Validate PagerDuty escalation actually pages (fire drill)
- [ ] Review and update runbooks based on recent incidents
- [ ] Archive old metrics (retention policy enforcement)
- [ ] Update alerting thresholds based on new baselines
