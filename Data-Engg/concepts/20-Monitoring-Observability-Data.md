# Monitoring & Observability for Data Platforms - Deep Dive

## Table of Contents
1. [Data Observability Fundamentals](#1-data-observability-fundamentals)
2. [Prometheus for Data Pipelines](#2-prometheus-for-data-pipelines)
3. [Grafana Dashboards](#3-grafana-dashboards)
4. [OpenTelemetry for Data](#4-opentelemetry-for-data)
5. [Burrow - Kafka Consumer Lag](#5-burrow)
6. [Cruise Control - Kafka Operations](#6-cruise-control)
7. [Soda Core](#7-soda-core)
8. [Elementary (dbt)](#8-elementary)
9. [AWS CloudWatch for Data](#9-aws-cloudwatch)
10. [Data SLA/SLO Framework](#10-data-slaslo-framework)
11. [Incident Management](#11-incident-management)
12. [End-to-End Architecture](#12-end-to-end-architecture)
13. [Production Checklist](#13-production-checklist)

---

## 1. Data Observability Fundamentals

### Three Pillars Applied to Data Pipelines

```
┌─────────────────────────────────────────────────────────────┐
│              Observability for Data Platforms                 │
├───────────────────┬─────────────────────┬───────────────────┤
│     METRICS       │       LOGS          │      TRACES       │
├───────────────────┼─────────────────────┼───────────────────┤
│ • Pipeline lag    │ • Job stdout/stderr │ • Request flow    │
│ • Record count    │ • Error stacktraces │   across pipeline │
│ • Processing time │ • Schema change logs│   stages          │
│ • Data freshness  │ • DQ test results   │ • Lineage (which  │
│ • Error rate      │ • Partition info    │   dataset touched)│
│ • Resource usage  │ • Checkpoint info   │ • Latency per hop │
│ • Cost metrics    │ • CDC lag details   │ • Bottleneck ID   │
└───────────────────┴─────────────────────┴───────────────────┘
```

### Five Pillars of Data Observability

| Pillar | What It Measures | How to Detect Issues |
|--------|-----------------|---------------------|
| **Freshness** | Is data arriving on time? | Last update timestamp vs SLO |
| **Volume** | Is expected amount arriving? | Row count anomaly detection |
| **Schema** | Has structure changed unexpectedly? | Schema diff against baseline |
| **Distribution** | Are values within expected ranges? | Statistical tests (KS, chi-squared) |
| **Lineage** | Where does data come from/go? | Dependency graph, impact analysis |

### Alert Fatigue Reduction

```
Problem: Too many alerts → team ignores ALL alerts

Solutions:
1. Tiered alerting (P0 pages, P1 Slack, P2 ticket, P3 dashboard-only)
2. Error budgets (only alert when budget is burning fast)
3. Composite alerts (multiple conditions must be true)
4. Anomaly-based (alert on unexpected changes, not fixed thresholds)
5. Routing (right alert to right person based on ownership)
6. Suppression (silence during maintenance windows)
7. Deduplication (group related alerts into single notification)
```

---

## 2. Prometheus for Data Pipelines

### Architecture

```
┌───────────────────────────────────────────────────────────────┐
│                 Prometheus Stack for Data                       │
│                                                                 │
│  Data Services              Prometheus          Alerting        │
│  ┌──────────┐              ┌──────────┐       ┌───────────┐  │
│  │Kafka(JMX)│──exporters──▶│Prometheus│──────▶│Alertmanager│  │
│  │Flink(JMX)│              │  Server  │       │            │  │
│  │Spark(JMX)│              │          │       │ • Slack    │  │
│  │Airflow   │              │  PromQL  │       │ • PagerDuty│  │
│  │Glue(CW)  │──push──────▶│  (query) │       │ • Email    │  │
│  └──────────┘  (pushgw)   └────┬─────┘       └───────────┘  │
│                                 │                              │
│                                 ▼                              │
│                          ┌──────────┐    ┌─────────────────┐ │
│                          │ Thanos/  │    │    Grafana       │ │
│                          │ Mimir    │    │  (dashboards)    │ │
│                          │(long-term)│    └─────────────────┘ │
│                          └──────────┘                         │
└───────────────────────────────────────────────────────────────┘
```

### Key Metrics Per Technology

#### Kafka Metrics
```yaml
# kafka-metrics-config.yml (JMX Exporter)
rules:
  # Consumer lag (CRITICAL)
  - pattern: kafka.consumer<type=consumer-fetch-manager-metrics, client-id=(.+), topic=(.+), partition=(.+)><>records-lag-max
    name: kafka_consumer_lag_max
    labels:
      client_id: "$1"
      topic: "$2"
      partition: "$3"

  # Under-replicated partitions (cluster health)
  - pattern: kafka.server<type=ReplicaManager, name=UnderReplicatedPartitions><>Value
    name: kafka_server_under_replicated_partitions

  # ISR shrink/expand rate
  - pattern: kafka.server<type=ReplicaManager, name=IsrShrinksPerSec><>OneMinuteRate
    name: kafka_server_isr_shrinks_per_sec

  # Request rate
  - pattern: kafka.network<type=RequestMetrics, name=RequestsPerSec, request=(.+), version=(.+)><>OneMinuteRate
    name: kafka_network_requests_per_sec
    labels:
      request: "$1"

  # Log flush latency
  - pattern: kafka.log<type=LogFlushStats, name=LogFlushRateAndTimeMs><>99thPercentile
    name: kafka_log_flush_time_ms_p99
```

```promql
# PromQL Alert Rules for Kafka

# Consumer lag alert (records behind)
- alert: KafkaConsumerLagHigh
  expr: sum by (consumer_group, topic) (kafka_consumergroup_lag) > 100000
  for: 5m
  labels:
    severity: warning
  annotations:
    summary: "Consumer group {{ $labels.consumer_group }} lag on {{ $labels.topic }}: {{ $value }}"

# Under-replicated partitions
- alert: KafkaUnderReplicatedPartitions
  expr: kafka_server_under_replicated_partitions > 0
  for: 2m
  labels:
    severity: critical

# Broker offline
- alert: KafkaBrokerOffline
  expr: count(kafka_server_broker_state{state="3"}) < 3
  for: 1m
  labels:
    severity: critical
```

#### Spark Metrics
```promql
# Executor memory pressure
- alert: SparkExecutorMemoryHigh
  expr: (spark_executor_memory_used_bytes / spark_executor_memory_max_bytes) > 0.9
  for: 5m
  labels:
    severity: warning

# Shuffle spill (disk I/O - performance issue)
- alert: SparkShuffleSpillHigh
  expr: rate(spark_executor_shuffle_spill_disk_bytes_total[5m]) > 1073741824
  for: 10m
  labels:
    severity: warning
  annotations:
    summary: "Spark spilling >1GB/s to disk - consider increasing executor memory"

# Task failures
- alert: SparkTaskFailureRate
  expr: rate(spark_executor_tasks_failed_total[5m]) / rate(spark_executor_tasks_completed_total[5m]) > 0.05
  for: 5m
  labels:
    severity: critical
```

#### Flink Metrics
```promql
# Checkpoint duration
- alert: FlinkCheckpointSlow
  expr: flink_jobmanager_job_lastCheckpointDuration > 120000
  for: 3m
  labels:
    severity: warning
  annotations:
    summary: "Checkpoint taking >2min ({{ $value }}ms)"

# Backpressure (most critical for streaming)
- alert: FlinkBackpressure
  expr: flink_taskmanager_job_task_backPressuredTimeMsPerSecond > 500
  for: 5m
  labels:
    severity: critical
  annotations:
    summary: "Task {{ $labels.task_name }} backpressured >500ms/s"

# Records lag (end-to-end latency)
- alert: FlinkRecordsLag
  expr: flink_taskmanager_job_task_operator_pendingRecords > 1000000
  for: 5m
  labels:
    severity: warning
```

#### Airflow Metrics
```promql
# DAG run duration exceeds SLA
- alert: AirflowDAGSLAMiss
  expr: airflow_dag_run_duration_seconds > airflow_dag_sla_seconds
  labels:
    severity: warning

# Task failure rate
- alert: AirflowTaskFailureRate
  expr: rate(airflow_task_fail_total[1h]) > 5
  for: 10m
  labels:
    severity: critical

# Scheduler heartbeat (scheduler health)
- alert: AirflowSchedulerDown
  expr: time() - airflow_scheduler_heartbeat_timestamp > 30
  labels:
    severity: critical

# Pool utilization
- alert: AirflowPoolExhausted
  expr: airflow_pool_running_slots / airflow_pool_total_slots > 0.9
  for: 5m
  labels:
    severity: warning
```

### Recording Rules (Pre-aggregation)

```yaml
groups:
  - name: data_pipeline_recording_rules
    rules:
      # Pre-compute pipeline freshness
      - record: pipeline:data_freshness_seconds
        expr: time() - max by (pipeline, dataset) (last_successful_update_timestamp)
      
      # Pre-compute error rate
      - record: pipeline:error_rate_5m
        expr: rate(pipeline_records_failed_total[5m]) / rate(pipeline_records_processed_total[5m])
      
      # Pre-compute throughput
      - record: pipeline:throughput_records_per_second
        expr: rate(pipeline_records_processed_total[5m])
```

### Alertmanager Routing

```yaml
# alertmanager.yml
route:
  receiver: default-slack
  group_by: ['alertname', 'cluster', 'service']
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 4h
  
  routes:
    # P0: Page on-call immediately
    - match:
        severity: critical
        priority: P0
      receiver: pagerduty-oncall
      group_wait: 0s
      repeat_interval: 5m
    
    # P1: Slack alert to team channel
    - match:
        severity: critical
      receiver: slack-data-critical
      repeat_interval: 30m
    
    # P2: Slack notification
    - match:
        severity: warning
      receiver: slack-data-alerts
      repeat_interval: 4h
    
    # Data quality failures → specific channel
    - match:
        type: data_quality
      receiver: slack-data-quality

receivers:
  - name: pagerduty-oncall
    pagerduty_configs:
      - service_key: "${PD_SERVICE_KEY}"
        severity: critical
  
  - name: slack-data-critical
    slack_configs:
      - channel: '#data-platform-critical'
        title: '{{ .GroupLabels.alertname }}'
        text: '{{ range .Alerts }}{{ .Annotations.summary }}{{ end }}'
  
  - name: slack-data-alerts
    slack_configs:
      - channel: '#data-platform-alerts'
```

### Prometheus Operator (K8s)

```yaml
# ServiceMonitor for Kafka (auto-discovers pods)
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: kafka-metrics
  namespace: monitoring
spec:
  selector:
    matchLabels:
      strimzi.io/kind: Kafka
  endpoints:
    - port: tcp-prometheus
      interval: 15s
      path: /metrics

---
# PrometheusRule for alerts
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: data-pipeline-alerts
spec:
  groups:
    - name: kafka.rules
      rules:
        - alert: KafkaConsumerLagCritical
          expr: sum by (group) (kafka_consumergroup_lag) > 500000
          for: 5m
          labels:
            severity: critical
            team: data-platform
```

---

## 3. Grafana Dashboards

### Dashboard Design Principles for Data

```
1. Executive View (top-level):
   • Overall platform health (green/yellow/red)
   • SLA compliance percentage
   • Total cost (this month vs budget)
   • Active incidents count

2. Pipeline View (per-pipeline):
   • Freshness (time since last success)
   • Throughput (records/sec)
   • Error rate
   • Processing latency (P50, P95, P99)
   • Cost attribution

3. Infrastructure View (per-service):
   • Kafka: lag, throughput, partition health
   • Spark/Flink: executor utilization, checkpoint times
   • Storage: S3 request rate, Redshift queue depth

4. Data Quality View:
   • Test pass/fail rates
   • Anomaly detection results
   • Schema changes detected
   • Freshness scores per dataset
```

### Grafana + Loki (Log Aggregation)

```yaml
# Loki query: find Glue job errors
{namespace="glue", job_name="daily-etl"} |= "ERROR" | json | line_format "{{.message}}"

# Loki query: Airflow task failures with context
{namespace="airflow", container="worker"} | json | status="failed" 
  | line_format "DAG={{.dag_id}} Task={{.task_id}} Error={{.exception}}"

# Dashboard-as-code (Grafonnet / Terraform)
resource "grafana_dashboard" "kafka" {
  config_json = file("dashboards/kafka.json")
  folder      = grafana_folder.data_platform.id
}
```

---

## 4. OpenTelemetry for Data

### Instrumenting an Airflow DAG

```python
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from airflow.decorators import task

# Setup
resource = Resource.create({"service.name": "data-pipeline", "service.version": "1.0"})
provider = TracerProvider(resource=resource)
provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint="otel-collector:4317")))
trace.set_tracer_provider(provider)
tracer = trace.get_tracer("data-pipeline")

@task
def extract_orders(date: str):
    with tracer.start_as_current_span("extract_orders") as span:
        span.set_attribute("pipeline.name", "daily-orders")
        span.set_attribute("pipeline.partition_date", date)
        span.set_attribute("source.type", "mysql")
        span.set_attribute("source.table", "orders")
        
        df = spark.read.jdbc(url, "orders", predicates=[f"dt='{date}'"])
        
        span.set_attribute("data.record_count", df.count())
        span.set_attribute("data.size_bytes", df._jdf.queryExecution().optimizedPlan().stats().sizeInBytes())
        
        output_path = f"s3://lake/raw/orders/dt={date}/"
        df.write.parquet(output_path)
        span.set_attribute("output.path", output_path)
        
        return output_path

@task
def validate(path: str):
    with tracer.start_as_current_span("validate_orders") as span:
        span.set_attribute("input.path", path)
        # ... validation logic
        span.set_attribute("validation.passed", True)
        span.set_attribute("validation.null_rate", 0.001)
```

### OTel Collector Configuration

```yaml
# otel-collector-config.yaml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317
      http:
        endpoint: 0.0.0.0:4318

processors:
  batch:
    timeout: 10s
    send_batch_size: 1024
  
  attributes:
    actions:
      - key: environment
        value: production
        action: upsert

  # Sampling (reduce volume for high-throughput pipelines)
  tail_sampling:
    policies:
      - name: errors-always
        type: status_code
        status_code: {status_codes: [ERROR]}
      - name: slow-traces
        type: latency
        latency: {threshold_ms: 30000}
      - name: probabilistic
        type: probabilistic
        probabilistic: {sampling_percentage: 10}

exporters:
  otlp/tempo:
    endpoint: tempo:4317
    tls:
      insecure: true
  
  prometheus:
    endpoint: 0.0.0.0:8889  # Expose as Prometheus metrics

service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [batch, attributes, tail_sampling]
      exporters: [otlp/tempo]
    metrics:
      receivers: [otlp]
      processors: [batch]
      exporters: [prometheus]
```

---

## 5. Burrow

### Lag Evaluation Algorithm

```
Burrow evaluates consumer lag using a sliding window:

Window: last 10 data points (lag measurements)

States:
┌──────────┬────────────────────────────────────────────────────┐
│  State   │  Condition                                          │
├──────────┼────────────────────────────────────────────────────┤
│  OK      │  Lag is zero OR lag is decreasing                  │
│  WARNING │  Lag is non-zero and increasing                    │
│  STALLED │  Lag is non-zero and not changing (consumer alive  │
│          │  but not making progress)                           │
│  STOPPED │  No offset commits for extended period             │
│  ERR     │  Evaluation error (missing data)                   │
└──────────┴────────────────────────────────────────────────────┘

Algorithm per partition:
  1. Collect last N lag measurements (timestamp, offset, lag)
  2. If all lags == 0 → OK
  3. If lag trend is DOWN → OK (catching up)
  4. If lag trend is UP → WARNING
  5. If lag is FLAT (not changing) and > 0 → STALLED
  6. If no new offsets committed → STOPPED

Consumer Group status = WORST status across all partitions
```

### Lag-Based Autoscaling

```python
# Use Burrow lag to trigger Kubernetes HPA for consumers
# Custom metrics adapter: Burrow → Prometheus → HPA

# Prometheus query from Burrow exporter:
# burrow_kafka_consumer_partition_lag{group="orders-consumer"}

# HPA definition:
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: orders-consumer-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: orders-consumer
  minReplicas: 2
  maxReplicas: 24  # Match partition count
  metrics:
    - type: External
      external:
        metric:
          name: kafka_consumer_lag
          selector:
            matchLabels:
              consumer_group: orders-consumer
        target:
          type: AverageValue
          averageValue: "50000"  # Scale up if lag > 50K per pod
```

---

## 6. Cruise Control

### Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                    LinkedIn Cruise Control                         │
│                                                                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐   │
│  │ Load Monitor │  │   Analyzer   │  │      Executor         │   │
│  │              │  │              │  │                        │   │
│  │ Collects     │  │ Generates    │  │ Executes partition    │   │
│  │ broker       │──▶│ optimization│──▶│ reassignment plans    │   │
│  │ metrics      │  │ proposals    │  │ (throttled)           │   │
│  │ (CPU, disk,  │  │ based on     │  │                        │   │
│  │  network)    │  │ goals        │  │                        │   │
│  └──────────────┘  └──────────────┘  └──────────────────────┘   │
│                                                                    │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │              Anomaly Detector                              │    │
│  │  • Broker failure detection                               │    │
│  │  • Metric anomaly (sudden throughput change)             │    │
│  │  • Goal violation (capacity exceeded)                     │    │
│  │  • Disk failure                                           │    │
│  │  → Auto-triggers rebalance or alert                       │    │
│  └──────────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────────┘
```

### Cruise Control Goals

```yaml
# Goals (ordered by priority, highest first):
goals:
  hard:  # Must be satisfied
    - RackAwareGoal              # Replicas spread across racks/AZs
    - MinTopicLeadersPerBrokerGoal
    - ReplicaCapacityGoal        # Don't exceed broker replica limit
    - DiskCapacityGoal           # Don't exceed disk capacity
  
  soft:  # Best effort
    - NetworkInboundCapacityGoal
    - NetworkOutboundCapacityGoal
    - CpuCapacityGoal
    - ReplicaDistributionGoal    # Even replica count across brokers
    - LeaderBytesInDistributionGoal  # Even leader traffic
    - TopicReplicaDistributionGoal
    - DiskUsageDistributionGoal

# REST API operations:
# GET  /kafkacruisecontrol/state          - Cluster state
# POST /kafkacruisecontrol/rebalance      - Trigger rebalance
# POST /kafkacruisecontrol/add_broker     - Integrate new broker
# POST /kafkacruisecontrol/remove_broker  - Decommission broker
# POST /kafkacruisecontrol/demote_broker  - Move leaders away
# GET  /kafkacruisecontrol/proposals      - View rebalance proposals
```

### Self-Healing with Strimzi

```yaml
# Strimzi Kafka with Cruise Control auto-rebalancing
apiVersion: kafka.strimzi.io/v1beta2
kind: Kafka
metadata:
  name: production
spec:
  cruiseControl:
    config:
      # Auto-fix goal violations
      anomaly.detection.goals: >
        com.linkedin.kafka.cruisecontrol.analyzer.goals.RackAwareGoal,
        com.linkedin.kafka.cruisecontrol.analyzer.goals.DiskCapacityGoal
      self.healing.enabled: true
      self.healing.broker.failure.enabled: true
      self.healing.disk.failure.enabled: true
      anomaly.notifier.class: com.linkedin.kafka.cruisecontrol.detector.notifier.SelfHealingNotifier
    
    # Resource constraints for rebalancing
    brokerCapacity:
      inboundNetwork: 100MB/s
      outboundNetwork: 100MB/s
      disk:
        - size: 1Ti
          type: gp3

---
# KafkaRebalance CRD (manual trigger)
apiVersion: kafka.strimzi.io/v1beta2
kind: KafkaRebalance
metadata:
  name: full-rebalance
  labels:
    strimzi.io/cluster: production
spec:
  mode: full
  goals:
    - RackAwareGoal
    - ReplicaDistributionGoal
    - LeaderBytesInDistributionGoal
  skipHardGoalCheck: false
  rebalanceDisk: true
```

---

## 7. Soda Core

### SodaCL Syntax

```yaml
# checks/orders.yml
checks for orders:
  # Row count checks
  - row_count > 0
  - row_count between 1000 and 10000000
  
  # Freshness
  - freshness(updated_at) < 1h
  
  # Completeness (null checks)
  - missing_count(order_id) = 0
  - missing_percent(amount) < 1%
  - missing_percent(customer_id) < 0.1%
  
  # Validity
  - invalid_count(email) = 0:
      valid format: email
  - invalid_percent(status) = 0:
      valid values: [pending, shipped, delivered, cancelled]
  
  # Uniqueness
  - duplicate_count(order_id) = 0
  
  # Statistical
  - avg(amount) between 10 and 500
  - max(amount) < 100000
  - stddev(amount) < 1000
  
  # Anomaly detection (ML-based, no threshold needed!)
  - anomaly detection for row_count
  - anomaly detection for avg(amount)
  - anomaly detection for missing_percent(customer_id)
  
  # Distribution check (KS test vs reference)
  - distribution_difference(amount) < 0.1:
      distribution reference file: ./reference/amount_distribution.yml
      method: ks  # Kolmogorov-Smirnov
  
  # Schema check
  - schema:
      warn:
        when schema changes: any
      fail:
        when required column missing: [order_id, amount, status]
        when wrong type:
          order_id: integer
          amount: decimal
  
  # Custom SQL
  - failed rows:
      fail query: |
        SELECT * FROM orders 
        WHERE amount < 0 
        OR (status = 'delivered' AND delivery_date IS NULL)
  
  # Reference check (cross-table validation)
  - values in (customer_id) must exist in customers (id)

# Freshness for streaming
checks for streaming_orders:
  - freshness(event_time) < 5m:
      name: "Streaming freshness SLA"
```

### Soda + Airflow Integration

```python
from airflow import DAG
from airflow.operators.python import PythonOperator
from soda.scan import Scan

def run_soda_checks(table: str, checks_file: str, **context):
    scan = Scan()
    scan.set_data_source_name("production_warehouse")
    scan.add_configuration_yaml_file("soda/configuration.yml")
    scan.add_sodacl_yaml_file(checks_file)
    scan.set_scan_definition_name(f"{table}_quality")
    
    scan.execute()
    
    # Fail task if critical checks fail
    if scan.has_check_fails():
        failed_checks = [c for c in scan.get_checks_fail()]
        raise Exception(f"Soda checks failed: {[c.name for c in failed_checks]}")
    
    # Log results
    context['ti'].xcom_push(key='soda_results', value={
        'passed': len(scan.get_checks_pass()),
        'warned': len(scan.get_checks_warn()),
        'failed': len(scan.get_checks_fail()),
    })

with DAG('data_quality_pipeline', schedule='@hourly') as dag:
    quality_gate = PythonOperator(
        task_id='soda_quality_check',
        python_callable=run_soda_checks,
        op_kwargs={'table': 'orders', 'checks_file': 'checks/orders.yml'}
    )
    
    transform_task >> quality_gate >> load_task
```

### Soda vs Great Expectations vs dbt tests

| Dimension | Soda Core | Great Expectations | dbt tests |
|-----------|-----------|-------------------|-----------|
| Config format | YAML (SodaCL) | Python/YAML | YAML (schema.yml) |
| Learning curve | Low | Medium-High | Low |
| Anomaly detection | Built-in (ML) | Custom expectation | Elementary package |
| Distribution checks | Built-in (KS test) | Custom | No |
| Freshness | Built-in | Custom | dbt_utils.recency |
| Cross-table checks | Built-in (reference) | Custom | relationships test |
| Schema monitoring | Built-in | Great Expectations | dbt-osmosis |
| CI/CD | CLI-friendly | Checkpoint-based | dbt test command |
| Alerting | Soda Cloud or webhook | Custom | Elementary or custom |
| Best for | SQL-first, simple setup | Python teams, complex validation | dbt-native teams |

---

## 8. Elementary

### Configuration

```yaml
# packages.yml (dbt project)
packages:
  - package: elementary-data/elementary
    version: 0.13.0

# models/elementary_config.yml
models:
  elementary:
    +schema: elementary  # Separate schema for elementary tables
```

```yaml
# models/schema.yml - Elementary tests on models
models:
  - name: orders
    tests:
      # Volume anomaly (alerts if row count is unusual)
      - elementary.volume_anomaly:
          timestamp_column: updated_at
          where: "status != 'test'"
          severity: warn
      
      # Freshness anomaly
      - elementary.freshness_anomaly:
          timestamp_column: updated_at
          severity: critical
      
      # Schema changes detection
      - elementary.schema_changes:
          severity: warn
    
    columns:
      - name: amount
        tests:
          # Column-level anomaly (distribution shift)
          - elementary.column_anomalies:
              column_anomalies:
                - null_count
                - null_percent
                - zero_count
                - average
                - standard_deviation
                - min
                - max
              timestamp_column: updated_at
              severity: warn
      
      - name: status
        tests:
          - elementary.dimension_anomalies:
              dimensions:
                - status
              timestamp_column: updated_at
              # Alerts if distribution of status values changes significantly
```

### Elementary vs Monte Carlo

| Dimension | Elementary | Monte Carlo |
|-----------|-----------|-------------|
| Cost | Free (OSS) / Cloud paid | Enterprise SaaS ($$$) |
| Setup | dbt package (minutes) | Managed service (days) |
| Integration | dbt-native (best for dbt shops) | Multi-tool (dbt, Spark, Airflow, etc.) |
| Detection | Statistical (dbt test based) | ML + rules (more sophisticated) |
| Lineage | dbt lineage only | Cross-platform lineage |
| Alert quality | Good | Better (fewer false positives) |
| Best for | dbt-centric teams, cost-sensitive | Enterprise, multi-platform, budget available |

---

## 9. AWS CloudWatch

### Custom Metrics for Glue Jobs

```python
# Publish custom metrics from Glue job
import boto3
from datetime import datetime

cloudwatch = boto3.client('cloudwatch')

def publish_pipeline_metrics(job_name, metrics):
    cloudwatch.put_metric_data(
        Namespace='DataPlatform/Pipelines',
        MetricData=[
            {
                'MetricName': 'RecordsProcessed',
                'Value': metrics['record_count'],
                'Unit': 'Count',
                'Dimensions': [
                    {'Name': 'JobName', 'Value': job_name},
                    {'Name': 'Environment', 'Value': 'production'}
                ]
            },
            {
                'MetricName': 'ProcessingLatencySeconds',
                'Value': metrics['duration_seconds'],
                'Unit': 'Seconds',
                'Dimensions': [
                    {'Name': 'JobName', 'Value': job_name}
                ]
            },
            {
                'MetricName': 'DataQualityScore',
                'Value': metrics['quality_score'],
                'Unit': 'Percent',
                'Dimensions': [
                    {'Name': 'JobName', 'Value': job_name},
                    {'Name': 'Dataset', 'Value': metrics['dataset']}
                ]
            }
        ]
    )

# Composite alarm (multiple conditions)
cloudwatch.put_composite_alarm(
    AlarmName='pipeline-sla-breach',
    AlarmRule='ALARM(freshness-critical) AND ALARM(quality-degraded)',
    ActionsEnabled=True,
    AlarmActions=['arn:aws:sns:us-east-1:123:data-platform-critical']
)
```

---

## 10. Data SLA/SLO Framework

### SLI Definitions

```yaml
# slo-definitions.yml
slis:
  freshness:
    description: "Time since last successful pipeline completion"
    measurement: "now() - last_successful_run_timestamp"
    unit: minutes
    
  completeness:
    description: "Percentage of expected records that arrived"
    measurement: "actual_record_count / expected_record_count * 100"
    unit: percent
    
  accuracy:
    description: "Percentage of records passing all quality checks"
    measurement: "passed_records / total_records * 100"
    unit: percent
    
  latency:
    description: "End-to-end processing time from source to destination"
    measurement: "destination_write_time - source_event_time"
    unit: minutes
    
  availability:
    description: "Percentage of scheduled runs that complete successfully"
    measurement: "successful_runs / total_scheduled_runs * 100"
    unit: percent
```

### Tiered Pipeline Priority

```
┌────────────────────────────────────────────────────────────────────┐
│                   Pipeline Priority Tiers                            │
├──────┬─────────────────────┬───────────┬───────────┬──────────────┤
│ Tier │ Description         │ Freshness │ Avail SLO │ On-call      │
│      │                     │ SLO       │           │ Response     │
├──────┼─────────────────────┼───────────┼───────────┼──────────────┤
│ P0   │ Revenue-impacting   │ ≤ 5 min   │ 99.99%   │ 5 min page   │
│      │ (payment, fraud)    │           │           │              │
├──────┼─────────────────────┼───────────┼───────────┼──────────────┤
│ P1   │ Customer-facing     │ ≤ 15 min  │ 99.9%    │ 15 min page  │
│      │ (dashboards, search)│           │           │              │
├──────┼─────────────────────┼───────────┼───────────┼──────────────┤
│ P2   │ Internal reporting  │ ≤ 1 hour  │ 99.5%    │ Business hrs │
│      │ (analytics, BI)     │           │           │              │
├──────┼─────────────────────┼───────────┼───────────┼──────────────┤
│ P3   │ Experimental        │ Best      │ 95%      │ Next day     │
│      │ (prototypes, adhoc) │ effort    │           │              │
└──────┴─────────────────────┴───────────┴───────────┴──────────────┘
```

### Error Budget and Burn-Rate Alerting

```promql
# Error budget calculation
# SLO: 99.9% availability over 30 days
# Budget: 0.1% × 30 days × 24h × 60min = 43.2 minutes of downtime allowed

# Current error budget remaining:
1 - (
  sum(pipeline_failures_minutes_total{priority="P1"}) 
  / (30 * 24 * 60 * 0.001)
)

# Multi-window burn-rate alerts:
# Fast burn (consuming budget 14.4x faster than sustainable)
- alert: SLOBurnRateFast
  expr: |
    (
      sum(rate(pipeline_sli_errors_total{priority="P1"}[1h]))
      / sum(rate(pipeline_sli_total{priority="P1"}[1h]))
    ) > (14.4 * 0.001)
  for: 2m
  labels:
    severity: critical
    window: 1h
  annotations:
    summary: "P1 pipeline SLO burning 14.4x budget rate (1h window)"

# Slow burn (consuming budget 3x faster)
- alert: SLOBurnRateSlow
  expr: |
    (
      sum(rate(pipeline_sli_errors_total{priority="P1"}[6h]))
      / sum(rate(pipeline_sli_total{priority="P1"}[6h]))
    ) > (3 * 0.001)
  for: 30m
  labels:
    severity: warning
    window: 6h

# Error budget exhaustion
- alert: ErrorBudgetExhausted
  expr: |
    slo:error_budget_remaining{priority="P1"} < 0
  labels:
    severity: critical
  annotations:
    summary: "P1 error budget exhausted - freeze non-critical changes"
```

---

## 11. Incident Management

### Severity Classification for Data

| Severity | Criteria | Response | Example |
|----------|----------|----------|---------|
| **SEV1** | P0 pipeline down, revenue impact, data loss | Page immediately, all hands | Payment processing pipeline down |
| **SEV2** | P1 pipeline delayed, customer-facing impact | Page on-call, 15min response | Customer dashboard stale > 30min |
| **SEV3** | P2 pipeline issue, internal impact only | Business hours, ticket | Daily report delayed 2 hours |
| **SEV4** | Non-urgent, cosmetic, optimization | Backlog, next sprint | Dashboard slow but functional |

### Runbook Template

```markdown
# Runbook: [Pipeline Name] - [Failure Scenario]

## Quick Facts
- **Owner**: data-platform-team
- **Priority**: P1
- **On-call**: #data-oncall Slack channel
- **Dashboards**: [link to Grafana]
- **Logs**: [link to Loki/CloudWatch]

## Symptoms
- [ ] Consumer lag > 100K for > 5 minutes
- [ ] No new records in destination for > 15 minutes
- [ ] Alert: KafkaConsumerLagCritical firing

## Diagnosis Steps
1. Check consumer status: `kafka-consumer-groups --describe --group orders-consumer`
2. Check broker health: Grafana Kafka dashboard → Under-replicated partitions
3. Check source: Is MySQL replication healthy? `SHOW SLAVE STATUS`
4. Check Flink: Is job running? Dashboard → Job Manager

## Resolution Steps
### Scenario A: Consumer rebalancing
1. Wait 5 minutes (rebalance settling)
2. If still lagging: restart consumer pods `kubectl rollout restart deployment/orders-consumer`

### Scenario B: Broker failure
1. Check Cruise Control proposal: `curl cruise-control:9090/kafkacruisecontrol/state`
2. If broker is down: trigger rebalance `POST /kafkacruisecontrol/rebalance`

### Scenario C: Source database issue
1. Check DMS task status: AWS Console → DMS → Tasks
2. If DMS stopped: restart task `aws dms start-replication-task`

## Escalation
- After 15 min without resolution → Escalate to tech lead
- After 30 min without resolution → Escalate to engineering manager
- If data loss suspected → Notify data governance team immediately

## Post-Incident
- [ ] Post-mortem within 48 hours
- [ ] Update this runbook with learnings
- [ ] Create preventive automation ticket
```

---

## 12. End-to-End Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│              Complete Data Observability Stack                        │
│                                                                       │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                    Data Services                              │    │
│  │  Kafka │ Flink │ Spark │ Airflow │ Glue │ Redshift │ S3   │    │
│  └────┬──────┬──────┬──────┬────────┬────────┬──────────┬─────┘    │
│       │      │      │      │        │        │          │           │
│       ▼      ▼      ▼      ▼        ▼        ▼          ▼           │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  Collection Layer                                             │   │
│  │  • JMX Exporters (Kafka, Flink) → Prometheus                │   │
│  │  • StatsD (Airflow) → Prometheus                             │   │
│  │  • OTel Collector (traces + metrics) → Tempo + Prometheus    │   │
│  │  • CloudWatch Agent (Glue, EMR) → CloudWatch + Prometheus    │   │
│  │  • Loki Promtail (logs from all services)                    │   │
│  └──────────────────────────────────────────────────────────────┘   │
│       │              │              │              │                  │
│       ▼              ▼              ▼              ▼                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐       │
│  │Prometheus│  │  Loki    │  │  Tempo   │  │  Soda Core/  │       │
│  │(metrics) │  │  (logs)  │  │ (traces) │  │  Elementary  │       │
│  │          │  │          │  │          │  │  (DQ metrics)│       │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └──────┬───────┘       │
│       │              │              │              │                  │
│       └──────────────┴──────────────┴──────────────┘                 │
│                              │                                        │
│                              ▼                                        │
│                     ┌──────────────────┐                             │
│                     │     Grafana      │                             │
│                     │  (unified view)  │                             │
│                     │  • Dashboards    │                             │
│                     │  • Alerts        │                             │
│                     │  • Explore       │                             │
│                     └────────┬─────────┘                             │
│                              │                                        │
│                              ▼                                        │
│                     ┌──────────────────┐                             │
│                     │  Alertmanager    │                             │
│                     │  → PagerDuty     │                             │
│                     │  → Slack         │                             │
│                     │  → Email         │                             │
│                     └──────────────────┘                             │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 13. Production Checklist

### Per-Technology
- [ ] **Kafka**: consumer lag, under-replicated partitions, broker CPU/disk, ISR shrink rate
- [ ] **Flink**: checkpoint duration/failures, backpressure, restart count, watermark lag
- [ ] **Spark**: executor OOM, shuffle spill, task failure rate, stage duration
- [ ] **Airflow**: scheduler heartbeat, DAG parse time, task duration, pool usage
- [ ] **Glue**: DPU utilization, job duration, bookmark progress, error count
- [ ] **S3**: request rate (throttling), storage growth rate
- [ ] **Redshift**: query queue depth, disk usage, WLM queue wait time

### Alerting Hierarchy
- [ ] P0: PagerDuty page (5min response SLA)
- [ ] P1: Slack critical channel + PagerDuty (15min)
- [ ] P2: Slack alerts channel (business hours)
- [ ] P3: Dashboard only (no notification)
- [ ] Error budget burn-rate alerts configured
- [ ] Composite alerts for SLA breach (freshness + quality combined)

### Data Quality
- [ ] Soda Core or Elementary configured for all silver/gold tables
- [ ] Anomaly detection enabled (no manual thresholds)
- [ ] Schema change monitoring active
- [ ] Quality gate integrated in pipeline (fail fast)
- [ ] Quality dashboard visible to stakeholders

### Infrastructure
- [ ] Prometheus HA (2+ replicas)
- [ ] Long-term storage (Thanos/Mimir) for historical metrics
- [ ] Loki for log aggregation (structured logging enforced)
- [ ] OTel Collector deployed as DaemonSet
- [ ] Dashboard-as-code (version controlled)
- [ ] Runbooks for top 10 failure scenarios
- [ ] On-call rotation established and tested
