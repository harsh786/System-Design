# Production Monitoring, Alerting & Observability for AWS Glue at Scale

## 1. The Problem: 500+ Glue Jobs Running 24/7 with 99.9% SLA

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

### Business Context

Enterprise data platform powering analytics, ML models, and regulatory reporting.
Silent failures cost $50K+/hour in delayed decisions and compliance risk.

### Scale Parameters

| Dimension              | Value                    |
|------------------------|--------------------------|
| Total Glue Jobs        | 537                      |
| Daily Job Runs         | 2,100+                   |
| Data Processed/Day     | 52 TB                    |
| Critical Pipelines     | 42 (revenue-impacting)   |
| p99 Latency SLA        | < 45 minutes             |
| Availability Target    | 99.9% (8.7h downtime/yr) |
| Monthly Glue Spend     | $180K                    |
| On-Call Engineers       | 8 (rotation)             |

### Requirements

1. **Proactive Alerting** - Know before stakeholders notice
2. **Root Cause Analysis** - From alert to fix in < 15 minutes
3. **Cost Visibility** - Per-job, per-team cost attribution
4. **SLA Tracking** - Real-time SLA burn-down with forecasting
5. **Self-Healing** - Auto-remediate known failure patterns

---

## 2. Observability Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        OBSERVABILITY ARCHITECTURE                            │
└─────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────── DATA SOURCES ────────────────────────┐
│                                                               │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────────┐  │
│  │ CloudWatch  │  │  Spark UI    │  │  Custom Metrics    │  │
│  │ Logs        │  │  Metrics     │  │  (in-job publish)  │  │
│  └──────┬──────┘  └──────┬───────┘  └─────────┬──────────┘  │
│         │                 │                     │             │
│  ┌──────┴──────┐  ┌──────┴───────┐  ┌─────────┴──────────┐  │
│  │ S3 Access   │  │  Glue Data   │  │  Job Bookmark      │  │
│  │ Logs        │  │  Catalog     │  │  State             │  │
│  └──────┬──────┘  └──────┬───────┘  └─────────┬──────────┘  │
│         │                 │                     │             │
└─────────┼─────────────────┼─────────────────────┼─────────────┘
          │                 │                     │
          ▼                 ▼                     ▼
┌──────────────────── COLLECTION LAYER ────────────────────────┐
│                                                               │
│  ┌───────────────────┐  ┌────────────────┐  ┌────────────┐  │
│  │ CloudWatch Agent  │  │ Metric Filter  │  │  Firehose  │  │
│  │ (built-in)        │  │ Patterns       │  │  Stream    │  │
│  └─────────┬─────────┘  └───────┬────────┘  └─────┬──────┘  │
│            │                     │                  │         │
│  ┌─────────┴─────────────────────┴──────────────────┴──────┐ │
│  │              Kinesis Data Firehose                        │ │
│  └─────────────────────────┬────────────────────────────────┘ │
└────────────────────────────┼──────────────────────────────────┘
                             │
                             ▼
┌──────────────────── STORAGE LAYER ───────────────────────────┐
│                                                               │
│  ┌───────────────┐  ┌───────────────┐  ┌─────────────────┐  │
│  │  CloudWatch   │  │  OpenSearch   │  │  S3 (Audit &    │  │
│  │  Metrics      │  │  (Log Index)  │  │  Long-term)     │  │
│  └───────┬───────┘  └───────┬───────┘  └────────┬────────┘  │
└──────────┼───────────────────┼────────────────────┼───────────┘
           │                   │                    │
           ▼                   ▼                    ▼
┌──────────────────── VISUALIZATION ───────────────────────────┐
│                                                               │
│  ┌───────────────┐  ┌───────────────┐  ┌─────────────────┐  │
│  │  CloudWatch   │  │   Grafana     │  │    DataDog      │  │
│  │  Dashboards   │  │   (Self-host) │  │    (SaaS)       │  │
│  └───────────────┘  └───────────────┘  └─────────────────┘  │
└──────────────────────────────────────────────────────────────┘

┌──────────────────── ALERTING LAYER ──────────────────────────┐
│                                                               │
│  CloudWatch Alarms ──► SNS Topics ──┬──► PagerDuty (P1/P2)  │
│                                     ├──► OpsGenie (P3)       │
│                                     ├──► Slack (P4/Info)     │
│                                     └──► Lambda (Auto-fix)   │
└──────────────────────────────────────────────────────────────┘

┌──────────────────── AUTO-REMEDIATION ────────────────────────┐
│                                                               │
│  Lambda ──► Step Functions ──┬──► Restart Failed Job         │
│                              ├──► Scale Up DPUs              │
│                              ├──► Clear Stuck Bookmark       │
│                              └──► Notify if unresolvable     │
└──────────────────────────────────────────────────────────────┘
```

---

## 3. Key Metrics to Monitor

### Job-Level Metrics

| Metric                        | Source               | Threshold (Alert)       | Priority |
|-------------------------------|----------------------|-------------------------|----------|
| `glue.driver.aggregate.elapsedTime` | CloudWatch    | > 2x baseline           | P2       |
| `glue.driver.aggregate.numFailedTasks` | CloudWatch | > 0                     | P2       |
| `glue.ALL.system.cpuSystemLoad` | CloudWatch       | > 90% for 10 min        | P3       |
| Records processed/sec        | Custom               | < 50% of baseline       | P2       |
| Job bookmark progress         | Custom               | Stalled > 30 min        | P1       |
| DPU utilization               | Custom               | < 20% (waste) or 100%   | P3       |
| Error rate (records)          | Custom               | > 1%                    | P1       |

### Data Quality Metrics

| Metric                    | Source            | Threshold             | Priority |
|---------------------------|-------------------|-----------------------|----------|
| Row count delta           | Custom            | > 30% deviation       | P2       |
| Null rate per column      | DQDL / Custom     | > configured limit    | P2       |
| Schema drift detected     | Crawler / Custom  | Any unexpected column | P1       |
| Data freshness            | Custom            | > SLA window          | P1       |
| Duplicate rate            | Custom            | > 0.1%                | P3       |

### System-Level Metrics

| Metric                              | Source         | Threshold          | Priority |
|-------------------------------------|----------------|--------------------|----------|
| `glue.driver.jvm.heap.usage`       | CloudWatch     | > 85%              | P2       |
| `glue.executor.jvm.heap.usage`     | CloudWatch     | > 85%              | P2       |
| `glue.driver.system.cpuSystemLoad` | CloudWatch     | > 90%              | P3       |
| Shuffle bytes spilled to disk       | Spark UI       | > 1 GB             | P3       |
| GC time percentage                  | CloudWatch     | > 20%              | P2       |

### Cost Metrics

| Metric                  | Source       | Threshold                  | Priority |
|-------------------------|-------------|----------------------------|----------|
| Daily DPU-hours         | Custom      | > 120% of 7-day average    | P3       |
| Cost per job run        | Custom      | > 150% of baseline         | P3       |
| Monthly projected spend | Custom      | > budget threshold         | P2       |
| Idle DPU time           | Custom      | > 30% of allocated         | P4       |

### SLA Metrics

| Metric                       | Source   | Threshold                    | Priority |
|------------------------------|----------|------------------------------|----------|
| Time to SLA deadline         | Custom   | < 15 min remaining           | P1       |
| SLA breach count (rolling)   | Custom   | > 0                          | P1       |
| Pipeline backlog depth       | Custom   | > 3x normal                  | P2       |
| Dependency completion        | Custom   | Upstream late > 10 min       | P3       |

---

## 4. CloudWatch Integration

### Built-in Glue Metrics

AWS Glue publishes metrics under the `Glue` namespace automatically:

```
Namespace: Glue
Dimensions: JobName, JobRunId, Type (count|gauge)

Key metrics:
  glue.driver.aggregate.bytesRead
  glue.driver.aggregate.bytesWritten
  glue.driver.aggregate.elapsedTime
  glue.driver.aggregate.numCompletedStages
  glue.driver.aggregate.numFailedTasks
  glue.driver.aggregate.recordsRead
  glue.driver.aggregate.recordsWritten
  glue.driver.BlockManager.disk.diskSpaceUsed_MB
  glue.driver.ExecutorAllocationManager.executors.numberAllExecutors
  glue.driver.jvm.heap.usage
  glue.driver.jvm.heap.used
  glue.driver.system.cpuSystemLoad
  glue.ALL.jvm.heap.usage
  glue.ALL.system.cpuSystemLoad
```

### Custom Metric Publishing Pattern

```python
# Publish custom metrics from within a Glue job at regular intervals
# Use a background thread to avoid blocking ETL processing

import boto3
import time
import threading
from datetime import datetime


class GlueMetricPublisher:
    """Publishes custom CloudWatch metrics from within a Glue job."""

    def __init__(self, job_name: str, job_run_id: str, namespace: str = "GlueCustom"):
        self.job_name = job_name
        self.job_run_id = job_run_id
        self.namespace = namespace
        self.client = boto3.client("cloudwatch")
        self._buffer = []
        self._lock = threading.Lock()
        self._running = True
        self._flush_thread = threading.Thread(target=self._periodic_flush, daemon=True)
        self._flush_thread.start()

    def put_metric(self, metric_name: str, value: float, unit: str = "None",
                   dimensions: dict = None):
        """Buffer a metric for batch publishing."""
        dims = [
            {"Name": "JobName", "Value": self.job_name},
            {"Name": "JobRunId", "Value": self.job_run_id},
        ]
        if dimensions:
            dims.extend([{"Name": k, "Value": str(v)} for k, v in dimensions.items()])

        metric_data = {
            "MetricName": metric_name,
            "Dimensions": dims,
            "Timestamp": datetime.utcnow(),
            "Value": value,
            "Unit": unit,
        }

        with self._lock:
            self._buffer.append(metric_data)

    def put_records_processed(self, count: int):
        self.put_metric("RecordsProcessed", count, "Count")

    def put_error_count(self, count: int):
        self.put_metric("ErrorCount", count, "Count")

    def put_processing_latency(self, seconds: float):
        self.put_metric("ProcessingLatencySeconds", seconds, "Seconds")

    def put_data_quality_score(self, score: float, dataset: str):
        self.put_metric("DataQualityScore", score, "None",
                        dimensions={"Dataset": dataset})

    def put_bookmark_progress(self, progress_pct: float):
        self.put_metric("BookmarkProgress", progress_pct, "Percent")

    def _periodic_flush(self):
        """Flush metrics every 60 seconds."""
        while self._running:
            time.sleep(60)
            self._flush()

    def _flush(self):
        with self._lock:
            if not self._buffer:
                return
            batch = self._buffer[:20]  # CW limit: 20 metrics per call
            self._buffer = self._buffer[20:]

        try:
            self.client.put_metric_data(
                Namespace=self.namespace,
                MetricData=batch,
            )
        except Exception as e:
            print(f"[METRIC_PUBLISH_ERROR] {e}")

    def close(self):
        self._running = False
        self._flush()
```

### Structured Logging Setup

```python
import json
import logging
import sys
from datetime import datetime


class GlueStructuredLogger:
    """Structured JSON logging for Glue jobs - enables metric filters and search."""

    def __init__(self, job_name: str, job_run_id: str):
        self.job_name = job_name
        self.job_run_id = job_run_id
        self.logger = logging.getLogger("glue_structured")
        self.logger.setLevel(logging.INFO)

        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("%(message)s"))
        self.logger.addHandler(handler)

    def _emit(self, level: str, event: str, **kwargs):
        record = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": level,
            "job_name": self.job_name,
            "job_run_id": self.job_run_id,
            "event": event,
            **kwargs,
        }
        self.logger.info(json.dumps(record))

    def info(self, event: str, **kwargs):
        self._emit("INFO", event, **kwargs)

    def error(self, event: str, **kwargs):
        self._emit("ERROR", event, **kwargs)

    def metric(self, metric_name: str, value: float, **kwargs):
        self._emit("METRIC", f"metric.{metric_name}", value=value, **kwargs)

    def sla_checkpoint(self, checkpoint: str, deadline_remaining_sec: float):
        self._emit("SLA", f"sla.checkpoint.{checkpoint}",
                   deadline_remaining_sec=deadline_remaining_sec)

    def data_quality(self, dataset: str, check: str, passed: bool, details: dict = None):
        self._emit("DQ", f"dq.{check}",
                   dataset=dataset, passed=passed, details=details or {})


# Usage in Glue job:
# log = GlueStructuredLogger("order_aggregation", args["JOB_RUN_ID"])
# log.info("partition_processing_start", partition="2024-01-15", records=150000)
# log.metric("records_per_second", 12500.0)
# log.data_quality("orders", "null_check", passed=True, details={"null_pct": 0.001})
```

### CloudWatch Metric Filter Patterns

```
# Extract error counts from structured logs
Filter Pattern: { $.level = "ERROR" }
Metric: GlueCustom/ErrorCount

# Extract processing throughput
Filter Pattern: { $.event = "metric.records_per_second" }
Metric: GlueCustom/Throughput

# SLA deadline warnings
Filter Pattern: { $.level = "SLA" && $.deadline_remaining_sec < 900 }
Metric: GlueCustom/SLAAtRisk

# Data quality failures
Filter Pattern: { $.level = "DQ" && $.passed = false }
Metric: GlueCustom/DQFailure

# OOM indicators
Filter Pattern: "java.lang.OutOfMemoryError"
Metric: GlueCustom/OOMError
```

---

## 5. Implementation Code

### CloudWatch Alarms (Terraform)

```hcl
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CloudWatch Alarms for Glue Job Monitoring
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

variable "critical_jobs" {
  type = list(object({
    name          = string
    max_duration  = number  # seconds
    team          = string
  }))
  default = [
    { name = "order_aggregation", max_duration = 2700, team = "data-platform" },
    { name = "fraud_features",    max_duration = 1800, team = "ml-engineering" },
    { name = "regulatory_report", max_duration = 3600, team = "compliance" },
  ]
}

# SNS Topics for alert routing
resource "aws_sns_topic" "pagerduty_p1" {
  name = "glue-alerts-p1-pagerduty"
}

resource "aws_sns_topic" "opsgenie_p2" {
  name = "glue-alerts-p2-opsgenie"
}

resource "aws_sns_topic" "slack_p3" {
  name = "glue-alerts-p3-slack"
}

resource "aws_sns_topic" "auto_remediation" {
  name = "glue-alerts-auto-remediation"
}

# PagerDuty integration
resource "aws_sns_topic_subscription" "pagerduty" {
  topic_arn = aws_sns_topic.pagerduty_p1.arn
  protocol  = "https"
  endpoint  = "https://events.pagerduty.com/integration/${var.pagerduty_integration_key}/enqueue"
}

# Job failure alarm (P1)
resource "aws_cloudwatch_metric_alarm" "job_failure" {
  for_each = { for job in var.critical_jobs : job.name => job }

  alarm_name          = "glue-job-failure-${each.key}"
  alarm_description   = "Glue job ${each.key} has failed. Runbook: https://wiki/runbooks/glue/${each.key}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  threshold           = 0
  treat_missing_data  = "notBreaching"

  metric_name = "glue.driver.aggregate.numFailedTasks"
  namespace   = "Glue"
  statistic   = "Sum"
  period      = 300

  dimensions = {
    JobName = each.key
    Type    = "count"
  }

  alarm_actions = [
    aws_sns_topic.pagerduty_p1.arn,
    aws_sns_topic.auto_remediation.arn,
  ]

  tags = {
    Team     = each.value.team
    Severity = "P1"
  }
}

# Job duration exceeded (P2)
resource "aws_cloudwatch_metric_alarm" "job_duration" {
  for_each = { for job in var.critical_jobs : job.name => job }

  alarm_name          = "glue-job-long-running-${each.key}"
  alarm_description   = "Job ${each.key} exceeded ${each.value.max_duration}s (normal max). Check Spark UI."
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  threshold           = each.value.max_duration
  treat_missing_data  = "notBreaching"

  metric_name = "glue.driver.aggregate.elapsedTime"
  namespace   = "Glue"
  statistic   = "Maximum"
  period      = 300

  dimensions = {
    JobName = each.key
    Type    = "gauge"
  }

  alarm_actions = [aws_sns_topic.opsgenie_p2.arn]

  tags = {
    Team     = each.value.team
    Severity = "P2"
  }
}

# Heap memory critical (P2)
resource "aws_cloudwatch_metric_alarm" "heap_critical" {
  for_each = { for job in var.critical_jobs : job.name => job }

  alarm_name          = "glue-heap-critical-${each.key}"
  alarm_description   = "Job ${each.key} heap > 85%. OOM risk. Consider scaling DPUs."
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  threshold           = 0.85

  metric_name = "glue.ALL.jvm.heap.usage"
  namespace   = "Glue"
  statistic   = "Maximum"
  period      = 60

  dimensions = {
    JobName = each.key
    Type    = "gauge"
  }

  alarm_actions = [aws_sns_topic.opsgenie_p2.arn]
}

# Cost anomaly alarm (P3)
resource "aws_cloudwatch_metric_alarm" "cost_anomaly" {
  alarm_name          = "glue-daily-cost-anomaly"
  alarm_description   = "Daily Glue DPU-hours exceed 120% of 7-day average."
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  threshold           = 0  # Uses anomaly detection

  metric_query {
    id          = "dpu_hours"
    return_data = false
    metric {
      metric_name = "DPUHoursConsumed"
      namespace   = "GlueCustom"
      stat        = "Sum"
      period      = 86400
    }
  }

  metric_query {
    id          = "anomaly_band"
    expression  = "ANOMALY_DETECTION_BAND(dpu_hours, 2)"
    label       = "Expected DPU Hours"
    return_data = true
  }

  alarm_actions = [aws_sns_topic.slack_p3.arn]
}

# SLA at risk (P1)
resource "aws_cloudwatch_metric_alarm" "sla_risk" {
  alarm_name          = "glue-sla-breach-imminent"
  alarm_description   = "Pipeline SLA deadline < 15 min away and job still running."
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  threshold           = 0

  metric_name = "SLAAtRisk"
  namespace   = "GlueCustom"
  statistic   = "Sum"
  period      = 60

  alarm_actions = [aws_sns_topic.pagerduty_p1.arn]
}
```

### SLA Tracking Lambda

```python
"""
SLA Tracking Lambda - Checks pipeline completion against deadlines.
Triggered every 5 minutes by EventBridge rule.
"""
import boto3
import json
from datetime import datetime, timezone, timedelta

glue = boto3.client("glue")
cw = boto3.client("cloudwatch")
sns = boto3.client("sns")

# SLA definitions: job_name -> deadline (UTC hour:minute)
SLA_DEFINITIONS = {
    "order_aggregation": {"deadline": "06:00", "owner": "data-platform", "severity": "P1"},
    "fraud_features": {"deadline": "05:30", "owner": "ml-engineering", "severity": "P1"},
    "regulatory_daily": {"deadline": "07:00", "owner": "compliance", "severity": "P1"},
    "marketing_attribution": {"deadline": "08:00", "owner": "marketing-data", "severity": "P2"},
    "inventory_sync": {"deadline": "04:00", "owner": "supply-chain", "severity": "P2"},
}

P1_TOPIC = "arn:aws:sns:us-east-1:123456789:glue-alerts-p1-pagerduty"
P2_TOPIC = "arn:aws:sns:us-east-1:123456789:glue-alerts-p2-opsgenie"


def lambda_handler(event, context):
    now = datetime.now(timezone.utc)
    today = now.date()

    for job_name, sla in SLA_DEFINITIONS.items():
        deadline_time = datetime.strptime(sla["deadline"], "%H:%M").time()
        deadline = datetime.combine(today, deadline_time, tzinfo=timezone.utc)

        # Check if job completed today
        runs = glue.get_job_runs(JobName=job_name, MaxResults=5)["JobRuns"]
        completed_today = any(
            r["CompletedOn"].date() == today and r["JobRunState"] == "SUCCEEDED"
            for r in runs if "CompletedOn" in r
        )

        if completed_today:
            # Publish healthy metric
            cw.put_metric_data(
                Namespace="GlueCustom",
                MetricData=[{
                    "MetricName": "SLAMet",
                    "Dimensions": [{"Name": "JobName", "Value": job_name}],
                    "Value": 1, "Unit": "Count",
                }]
            )
            continue

        # Calculate time remaining
        remaining = (deadline - now).total_seconds()

        # Publish remaining time metric
        cw.put_metric_data(
            Namespace="GlueCustom",
            MetricData=[{
                "MetricName": "SLADeadlineRemainingSeconds",
                "Dimensions": [{"Name": "JobName", "Value": job_name}],
                "Value": max(remaining, 0), "Unit": "Seconds",
            }]
        )

        # Alert if breached or at risk
        if remaining < 0:
            _send_alert(job_name, sla, "BREACHED", abs(remaining))
        elif remaining < 900:  # 15 minutes
            _send_alert(job_name, sla, "AT_RISK", remaining)


def _send_alert(job_name, sla, status, seconds):
    topic = P1_TOPIC if sla["severity"] == "P1" else P2_TOPIC
    message = {
        "alert": f"SLA {status}: {job_name}",
        "job_name": job_name,
        "owner": sla["owner"],
        "deadline": sla["deadline"],
        "status": status,
        "seconds": int(seconds),
        "runbook": f"https://wiki/runbooks/sla/{job_name}",
    }
    sns.publish(TopicArn=topic, Message=json.dumps(message),
                Subject=f"[{sla['severity']}] SLA {status}: {job_name}")
```

### Auto-Remediation Lambda

```python
"""
Auto-remediation Lambda - Handles known failure patterns automatically.
Triggered by SNS from CloudWatch alarms.
"""
import boto3
import json
import time

glue = boto3.client("glue")
sns = boto3.client("sns")

MAX_RETRIES = 2
ESCALATION_TOPIC = "arn:aws:sns:us-east-1:123456789:glue-alerts-p1-pagerduty"
SLACK_TOPIC = "arn:aws:sns:us-east-1:123456789:glue-alerts-p3-slack"


def lambda_handler(event, context):
    for record in event["Records"]:
        message = json.loads(record["Sns"]["Message"])
        alarm_name = message.get("AlarmName", "")
        job_name = _extract_job_name(alarm_name)

        if not job_name:
            return

        # Get latest run details
        runs = glue.get_job_runs(JobName=job_name, MaxResults=3)["JobRuns"]
        if not runs:
            return

        latest = runs[0]
        error_msg = latest.get("ErrorMessage", "")

        # Decision tree for auto-remediation
        if "OutOfMemoryError" in error_msg:
            _handle_oom(job_name, latest)
        elif "Connection reset" in error_msg or "timeout" in error_msg.lower():
            _handle_transient(job_name, latest, runs)
        elif "bookmark" in error_msg.lower():
            _handle_bookmark_issue(job_name)
        else:
            _escalate(job_name, error_msg)


def _handle_oom(job_name, run):
    """Scale up DPUs and restart."""
    job = glue.get_job(JobName=job_name)["Job"]
    current_dpus = job.get("NumberOfWorkers", job.get("MaxCapacity", 10))
    new_dpus = min(int(current_dpus * 1.5), 100)

    glue.update_job(
        JobName=job_name,
        JobUpdate={"NumberOfWorkers": new_dpus}
    )
    glue.start_job_run(JobName=job_name)

    _notify_slack(f"Auto-remediation: Scaled {job_name} from {current_dpus} to "
                  f"{new_dpus} workers and restarted due to OOM.")


def _handle_transient(job_name, latest_run, all_runs):
    """Retry transient failures up to MAX_RETRIES."""
    recent_failures = sum(1 for r in all_runs if r["JobRunState"] == "FAILED")

    if recent_failures <= MAX_RETRIES:
        time.sleep(30)  # Brief backoff
        glue.start_job_run(JobName=job_name)
        _notify_slack(f"Auto-remediation: Retrying {job_name} (attempt {recent_failures}/{MAX_RETRIES}) "
                      f"after transient error.")
    else:
        _escalate(job_name, f"Transient failure persisted after {MAX_RETRIES} retries")


def _handle_bookmark_issue(job_name):
    """Reset bookmark and restart."""
    glue.reset_job_bookmark(JobName=job_name)
    glue.start_job_run(JobName=job_name)
    _notify_slack(f"Auto-remediation: Reset bookmark and restarted {job_name}.")


def _escalate(job_name, error_msg):
    """Escalate to on-call when auto-remediation cannot handle."""
    sns.publish(
        TopicArn=ESCALATION_TOPIC,
        Subject=f"[P1] Glue job {job_name} failed - manual intervention needed",
        Message=json.dumps({
            "job_name": job_name,
            "error": error_msg[:500],
            "runbook": f"https://wiki/runbooks/glue/{job_name}",
            "auto_remediation": "failed_or_not_applicable",
        })
    )


def _notify_slack(message):
    sns.publish(TopicArn=SLACK_TOPIC, Message=message,
                Subject="Glue Auto-Remediation")


def _extract_job_name(alarm_name):
    # alarm format: glue-job-failure-{job_name}
    parts = alarm_name.split("glue-job-failure-")
    return parts[1] if len(parts) > 1 else None
```

### Grafana Dashboard JSON (Key Panels)

```json
{
  "dashboard": {
    "title": "AWS Glue Production Overview",
    "tags": ["glue", "production", "data-platform"],
    "refresh": "1m",
    "panels": [
      {
        "title": "Job Success Rate (24h Rolling)",
        "type": "gauge",
        "gridPos": { "x": 0, "y": 0, "w": 6, "h": 4 },
        "targets": [{
          "namespace": "GlueCustom",
          "metricName": "JobSuccessRate",
          "stat": "Average",
          "period": "86400"
        }],
        "fieldConfig": {
          "defaults": {
            "thresholds": {
              "steps": [
                { "value": 0, "color": "red" },
                { "value": 95, "color": "yellow" },
                { "value": 99, "color": "green" }
              ]
            },
            "min": 0, "max": 100, "unit": "percent"
          }
        }
      },
      {
        "title": "Active SLA Breaches",
        "type": "stat",
        "gridPos": { "x": 6, "y": 0, "w": 4, "h": 4 },
        "targets": [{
          "namespace": "GlueCustom",
          "metricName": "SLABreachCount",
          "stat": "Sum",
          "period": "86400"
        }],
        "fieldConfig": {
          "defaults": {
            "thresholds": {
              "steps": [
                { "value": 0, "color": "green" },
                { "value": 1, "color": "red" }
              ]
            }
          }
        }
      },
      {
        "title": "Daily DPU-Hours & Cost",
        "type": "timeseries",
        "gridPos": { "x": 0, "y": 4, "w": 12, "h": 6 },
        "targets": [
          {
            "namespace": "GlueCustom",
            "metricName": "DPUHoursConsumed",
            "stat": "Sum",
            "period": "3600",
            "alias": "DPU-Hours"
          },
          {
            "namespace": "GlueCustom",
            "metricName": "EstimatedCostUSD",
            "stat": "Sum",
            "period": "3600",
            "alias": "Cost ($)"
          }
        ]
      },
      {
        "title": "Job Duration Heatmap",
        "type": "heatmap",
        "gridPos": { "x": 0, "y": 10, "w": 12, "h": 6 },
        "targets": [{
          "namespace": "Glue",
          "metricName": "glue.driver.aggregate.elapsedTime",
          "stat": "Average",
          "period": "300"
        }]
      },
      {
        "title": "Top 10 Most Expensive Jobs (7d)",
        "type": "barchart",
        "gridPos": { "x": 12, "y": 0, "w": 12, "h": 8 },
        "targets": [{
          "rawQuery": true,
          "query": "SELECT job_name, SUM(dpu_hours * 0.44) as cost FROM glue_runs WHERE run_date > NOW() - INTERVAL 7 DAY GROUP BY job_name ORDER BY cost DESC LIMIT 10"
        }]
      },
      {
        "title": "Data Quality Score by Dataset",
        "type": "timeseries",
        "gridPos": { "x": 12, "y": 8, "w": 12, "h": 6 },
        "targets": [{
          "namespace": "GlueCustom",
          "metricName": "DataQualityScore",
          "stat": "Average",
          "period": "300",
          "dimensions": { "Dataset": "*" }
        }]
      }
    ]
  }
}
```

---

## 6. Alerting Strategy

### Severity Levels

```
┌──────────┬──────────────────────────────────────────────────────────────────┐
│ Severity │ Definition                                                       │
├──────────┼──────────────────────────────────────────────────────────────────┤
│ P1       │ Revenue-impacting. SLA breach imminent/occurred.                 │
│          │ Response: < 5 min. Auto-page on-call.                            │
│          │ Examples: Critical job failed, SLA breach, data corruption       │
├──────────┼──────────────────────────────────────────────────────────────────┤
│ P2       │ Service degraded. Risk of cascade failure.                       │
│          │ Response: < 30 min. Page during business hours.                  │
│          │ Examples: Job running 2x normal, heap > 85%, DQ check failed    │
├──────────┼──────────────────────────────────────────────────────────────────┤
│ P3       │ Attention needed. No immediate business impact.                  │
│          │ Response: < 4 hours. Slack notification.                         │
│          │ Examples: Cost anomaly, non-critical job failure, schema drift   │
├──────────┼──────────────────────────────────────────────────────────────────┤
│ P4       │ Informational. Track for trends.                                 │
│          │ Response: Next business day. Dashboard only.                     │
│          │ Examples: Low DPU utilization, minor latency increase            │
└──────────┴──────────────────────────────────────────────────────────────────┘
```

### Escalation Policy

```
Time 0        ──► On-call engineer (PagerDuty)
Time +10 min  ──► Secondary on-call
Time +30 min  ──► Engineering Manager
Time +60 min  ──► VP Engineering + Incident Commander
```

### Alert Fatigue Prevention

```python
# Alert deduplication and intelligent grouping configuration

ALERT_RULES = {
    "deduplication": {
        "window_minutes": 15,           # Same alert suppressed for 15 min
        "group_by": ["job_name", "error_type"],  # Group related alerts
    },
    "rate_limiting": {
        "max_alerts_per_hour": 10,      # Per-team limit
        "cooldown_after_ack_minutes": 60,
    },
    "intelligent_grouping": {
        # If 3+ jobs fail within 5 min, create single "cascade" alert
        "cascade_threshold": 3,
        "cascade_window_minutes": 5,
        "cascade_message": "Multiple job failures detected - likely upstream issue",
    },
    "auto_resolve": {
        # Auto-resolve if next run succeeds
        "enabled": True,
        "notify_on_resolve": True,
    },
}
```

### Runbook Integration

Every alert includes:
- Direct link to runbook: `https://wiki/runbooks/glue/{job_name}`
- Spark UI link for the failed run
- CloudWatch Logs Insights query link
- Last 5 run history summary
- Suggested remediation steps

---

## 7. Debugging Production Issues

### Spark UI Analysis Playbook

```
┌─────────────────────────────────────────────────────────┐
│          SLOW JOB INVESTIGATION FLOWCHART               │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Job running slow?                                      │
│       │                                                 │
│       ▼                                                 │
│  Check Spark UI → Stages tab                            │
│       │                                                 │
│       ├─► One stage taking 90%+ time?                   │
│       │       │                                         │
│       │       ├─► Tasks tab: One task >> others?         │
│       │       │       └─► DATA SKEW                     │
│       │       │           Fix: salting, repartition     │
│       │       │                                         │
│       │       └─► All tasks slow equally?               │
│       │               └─► RESOURCE CONSTRAINED          │
│       │                   Fix: more DPUs, tune memory   │
│       │                                                 │
│       ├─► Shuffle read/write very high?                  │
│       │       └─► EXCESSIVE SHUFFLE                     │
│       │           Fix: broadcast join, coalesce         │
│       │                                                 │
│       └─► GC time > 20%?                                │
│               └─► MEMORY PRESSURE                       │
│                   Fix: increase memory fraction,        │
│                        reduce partition size            │
└─────────────────────────────────────────────────────────┘
```

### Memory Profiling

```python
# Add to Glue job for memory diagnostics

import psutil
import os

def log_memory_state(logger, stage_name):
    """Log current memory state for debugging OOM issues."""
    process = psutil.Process(os.getpid())
    mem = process.memory_info()

    logger.info("memory_snapshot", **{
        "stage": stage_name,
        "rss_mb": mem.rss / 1024 / 1024,
        "vms_mb": mem.vms / 1024 / 1024,
        "percent": process.memory_percent(),
    })

    # Check if approaching OOM
    if process.memory_percent() > 80:
        logger.error("memory_critical", stage=stage_name,
                     percent=process.memory_percent(),
                     action="Consider increasing workers or reducing partition size")
```

### Job Bookmark Debugging

```python
"""
Job Bookmark Health Monitor - detects stuck/corrupted bookmarks.
"""
import boto3
from datetime import datetime, timezone, timedelta

glue = boto3.client("glue")


def check_bookmark_health(job_name: str) -> dict:
    """Analyze bookmark state for anomalies."""
    # Get bookmark
    try:
        bookmark = glue.get_job_bookmark(JobName=job_name)["JobBookmarkEntry"]
    except glue.exceptions.EntityNotFoundException:
        return {"status": "NO_BOOKMARK", "action": "normal_for_new_jobs"}

    # Get recent runs
    runs = glue.get_job_runs(JobName=job_name, MaxResults=10)["JobRuns"]
    successful_runs = [r for r in runs if r["JobRunState"] == "SUCCEEDED"]

    issues = []

    # Check 1: Bookmark not advancing
    if len(successful_runs) >= 2:
        # Compare records processed between last 2 successful runs
        last_records = successful_runs[0].get("NumberOfWorkers", 0)  # placeholder
        # In reality, compare bookmark values between runs

    # Check 2: Bookmark timestamp vs last successful run
    bookmark_version = bookmark.get("Version", 0)
    if successful_runs:
        last_success = successful_runs[0]["CompletedOn"]
        if (datetime.now(timezone.utc) - last_success) > timedelta(hours=24):
            issues.append("STALE: No successful run in 24h, bookmark may be stuck")

    # Check 3: Repeated failures after bookmark advance
    recent_failures = [r for r in runs[:5] if r["JobRunState"] == "FAILED"]
    if len(recent_failures) >= 3:
        issues.append("CORRUPTION_RISK: 3+ consecutive failures, bookmark may reference bad data")

    return {
        "status": "UNHEALTHY" if issues else "HEALTHY",
        "bookmark_version": bookmark_version,
        "issues": issues,
        "recommendation": "reset_bookmark" if "CORRUPTION" in str(issues) else "monitor",
    }
```

---

## 8. Data Quality Monitoring

### Integrated DQ Monitoring

```python
"""
Data Quality monitoring that publishes results as CloudWatch metrics
and triggers alerts on failures.
"""
from awsglue.context import GlueContext
from pyspark.sql import functions as F


class DataQualityMonitor:
    """Runs DQ checks and publishes results as metrics."""

    def __init__(self, glue_context: GlueContext, metric_publisher, logger):
        self.gc = glue_context
        self.metrics = metric_publisher
        self.logger = logger

    def check_completeness(self, df, column: str, max_null_pct: float, dataset: str):
        """Check null rate for a column."""
        total = df.count()
        nulls = df.where(F.col(column).isNull()).count()
        null_pct = nulls / total if total > 0 else 0

        passed = null_pct <= max_null_pct
        self.metrics.put_metric(f"NullRate_{column}", null_pct, "None",
                                {"Dataset": dataset})
        self.logger.data_quality(dataset, f"null_check_{column}", passed,
                                 {"null_pct": null_pct, "threshold": max_null_pct})
        return passed

    def check_volume(self, df, dataset: str, min_records: int, max_records: int):
        """Check record count within expected range."""
        count = df.count()
        passed = min_records <= count <= max_records
        self.metrics.put_metric("RecordCount", count, "Count", {"Dataset": dataset})
        self.logger.data_quality(dataset, "volume_check", passed,
                                 {"count": count, "min": min_records, "max": max_records})
        return passed

    def check_freshness(self, df, timestamp_col: str, max_age_hours: float, dataset: str):
        """Check that newest record is within acceptable age."""
        from datetime import datetime, timezone, timedelta

        max_ts = df.agg(F.max(timestamp_col)).collect()[0][0]
        if max_ts is None:
            self.logger.data_quality(dataset, "freshness_check", False,
                                     {"error": "no_timestamps"})
            return False

        age_hours = (datetime.now(timezone.utc) - max_ts).total_seconds() / 3600
        passed = age_hours <= max_age_hours
        self.metrics.put_metric("DataAgeHours", age_hours, "None", {"Dataset": dataset})
        self.logger.data_quality(dataset, "freshness_check", passed,
                                 {"age_hours": age_hours, "max_hours": max_age_hours})
        return passed

    def check_uniqueness(self, df, key_columns: list, dataset: str):
        """Check for duplicate records on key columns."""
        total = df.count()
        distinct = df.select(key_columns).distinct().count()
        dup_rate = 1 - (distinct / total) if total > 0 else 0

        passed = dup_rate < 0.001  # < 0.1% duplicates
        self.metrics.put_metric("DuplicateRate", dup_rate, "None", {"Dataset": dataset})
        self.logger.data_quality(dataset, "uniqueness_check", passed,
                                 {"dup_rate": dup_rate, "total": total})
        return passed
```

### Schema Drift Detection

```python
def detect_schema_drift(glue_client, database: str, table: str,
                        expected_columns: dict, logger) -> list:
    """
    Compare current catalog schema against expected.
    expected_columns: {"col_name": "data_type", ...}
    """
    response = glue_client.get_table(DatabaseName=database, Name=table)
    actual_columns = {
        col["Name"]: col["Type"]
        for col in response["Table"]["StorageDescriptor"]["Columns"]
    }

    drift_events = []

    # New columns
    for col, dtype in actual_columns.items():
        if col not in expected_columns:
            drift_events.append({"type": "COLUMN_ADDED", "column": col, "dtype": dtype})

    # Removed columns
    for col in expected_columns:
        if col not in actual_columns:
            drift_events.append({"type": "COLUMN_REMOVED", "column": col})

    # Type changes
    for col, dtype in actual_columns.items():
        if col in expected_columns and expected_columns[col] != dtype:
            drift_events.append({
                "type": "TYPE_CHANGED", "column": col,
                "expected": expected_columns[col], "actual": dtype,
            })

    if drift_events:
        logger.error("schema_drift_detected", database=database, table=table,
                     drift_count=len(drift_events), events=drift_events)

    return drift_events
```

---

## 9. Cost Observability

### Per-Job Cost Attribution

```python
"""
Cost attribution Lambda - runs daily to compute per-job and per-team costs.
Publishes to CloudWatch and writes to cost tracking table.
"""
import boto3
from datetime import datetime, timezone, timedelta

glue = boto3.client("glue")
cw = boto3.client("cloudwatch")
dynamodb = boto3.resource("dynamodb")
cost_table = dynamodb.Table("glue-job-costs")

DPU_COST_PER_HOUR = 0.44  # Standard worker
FLEX_DPU_COST_PER_HOUR = 0.29


def compute_daily_costs(date_str: str):
    """Compute costs for all job runs on a given date."""
    target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    team_costs = {}

    # Paginate through all jobs
    paginator = glue.get_paginator("get_jobs")
    for page in paginator.paginate():
        for job in page["Jobs"]:
            job_name = job["Name"]
            team = job.get("Tags", {}).get("Team", "untagged")
            execution_class = job.get("ExecutionClass", "STANDARD")
            cost_rate = FLEX_DPU_COST_PER_HOUR if execution_class == "FLEX" else DPU_COST_PER_HOUR

            # Get runs for this date
            runs = glue.get_job_runs(JobName=job_name, MaxResults=50)["JobRuns"]
            daily_runs = [
                r for r in runs
                if r.get("CompletedOn") and r["CompletedOn"].date() == target_date
            ]

            job_cost = 0
            for run in daily_runs:
                duration_hours = run.get("ExecutionTime", 0) / 3600
                workers = run.get("NumberOfWorkers", run.get("MaxCapacity", 10))
                run_cost = duration_hours * workers * cost_rate
                job_cost += run_cost

            if job_cost > 0:
                # Publish per-job cost metric
                cw.put_metric_data(
                    Namespace="GlueCustom",
                    MetricData=[{
                        "MetricName": "JobCostUSD",
                        "Dimensions": [
                            {"Name": "JobName", "Value": job_name},
                            {"Name": "Team", "Value": team},
                        ],
                        "Value": job_cost,
                        "Unit": "None",
                        "Timestamp": datetime.combine(target_date,
                                                      datetime.min.time(),
                                                      tzinfo=timezone.utc),
                    }]
                )

                # Track team costs
                team_costs[team] = team_costs.get(team, 0) + job_cost

                # Write to DynamoDB for historical tracking
                cost_table.put_item(Item={
                    "pk": f"JOB#{job_name}",
                    "sk": date_str,
                    "cost_usd": str(round(job_cost, 4)),
                    "team": team,
                    "run_count": len(daily_runs),
                })

    # Publish team-level costs
    for team, cost in team_costs.items():
        cw.put_metric_data(
            Namespace="GlueCustom",
            MetricData=[{
                "MetricName": "TeamCostUSD",
                "Dimensions": [{"Name": "Team", "Value": team}],
                "Value": cost, "Unit": "None",
            }]
        )

    return team_costs
```

### Cost Anomaly Detection

```python
def detect_cost_anomaly(job_name: str, today_cost: float, lookback_days: int = 7) -> dict:
    """Simple anomaly detection based on rolling average + stddev."""
    import statistics

    # Get historical costs from DynamoDB
    from datetime import date, timedelta
    history = []
    for i in range(1, lookback_days + 1):
        d = (date.today() - timedelta(days=i)).isoformat()
        item = cost_table.get_item(Key={"pk": f"JOB#{job_name}", "sk": d}).get("Item")
        if item:
            history.append(float(item["cost_usd"]))

    if len(history) < 3:
        return {"anomaly": False, "reason": "insufficient_history"}

    mean = statistics.mean(history)
    stddev = statistics.stdev(history) if len(history) > 1 else 0
    threshold = mean + (2 * stddev)  # 2-sigma

    is_anomaly = today_cost > threshold and today_cost > mean * 1.5

    return {
        "anomaly": is_anomaly,
        "today_cost": today_cost,
        "mean_7d": round(mean, 2),
        "threshold": round(threshold, 2),
        "pct_over": round((today_cost - mean) / mean * 100, 1) if mean > 0 else 0,
    }
```

---

## 10. Production Dashboards

### Executive Overview Dashboard

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    GLUE PLATFORM - EXECUTIVE OVERVIEW                        │
├───────────────────┬───────────────────┬───────────────────┬─────────────────┤
│  SUCCESS RATE     │  SLA BREACHES     │  DAILY COST       │  ACTIVE JOBS    │
│                   │                   │                   │                 │
│    ██ 99.4%       │     ● 0           │    $6,230         │     47          │
│   ████████████    │   (target: 0)     │   ($180K/mo)      │  (of 537 total) │
│   (target 99.9%) │                   │                   │                 │
├───────────────────┴───────────────────┴───────────────────┴─────────────────┤
│                                                                             │
│  COST TREND (30 DAYS)                        TOP COST JOBS (7d)             │
│  $8K ┤                                      ┌────────────────────────────┐  │
│      │    ╭─╮                               │ fraud_features    $2,100   │  │
│  $6K ┤───╯   ╰──────────────               │ order_agg         $1,850   │  │
│      │                                      │ regulatory_daily  $1,200   │  │
│  $4K ┤                                      │ clickstream       $980     │  │
│      │                                      │ inventory_sync    $740     │  │
│  $2K ┤                                      └────────────────────────────┘  │
│      └──────────────────────────                                            │
│       1    5    10   15   20   25  30                                       │
│                                                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│  SLA BURN-DOWN (TODAY)                                                      │
│                                                                             │
│  order_aggregation    [████████████████████░░] 06:00 ✓ Complete 05:42       │
│  fraud_features       [██████████████████████] 05:30 ✓ Complete 05:18       │
│  regulatory_daily     [████████████████░░░░░░] 07:00   Running (est 06:45) │
│  marketing_attrib     [██████░░░░░░░░░░░░░░░░] 08:00   Queued              │
│  inventory_sync       [████████████████████░░] 04:00 ✓ Complete 03:51       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Operations Dashboard

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    GLUE PLATFORM - OPERATIONS VIEW                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  JOB HEALTH (LAST 24H)                                                      │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ ■ Succeeded: 2,087  ■ Failed: 8  ■ Running: 12  ■ Timeout: 3      │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                             │
│  FAILURE BREAKDOWN                     RESOURCE UTILIZATION                  │
│  ┌───────────────────────────┐        ┌─────────────────────────────────┐  │
│  │ OOM Errors         3      │        │ Avg Heap Usage:    62%          │  │
│  │ Timeout            3      │        │ Avg CPU Load:      45%          │  │
│  │ Connection Error   1      │        │ Shuffle Spill:     2.1 GB       │  │
│  │ Data Quality Fail  1      │        │ Avg DPU Util:      71%          │  │
│  └───────────────────────────┘        └─────────────────────────────────┘  │
│                                                                             │
│  DURATION HEATMAP (JOBS × HOUR)                                             │
│        00  02  04  06  08  10  12  14  16  18  20  22                       │
│  job1  ·   ·   ░   █   ·   ·   ·   ·   ·   ·   ·   ·                      │
│  job2  ·   ·   ·   ·   ░   ░   ·   ·   ·   ·   ░   ░                      │
│  job3  █   ·   ·   ·   ·   ·   █   ·   ·   ·   ·   ·                      │
│  job4  ·   ░   ·   ·   ·   ·   ·   ░   ·   ·   ·   ·                      │
│  Legend: · none  ░ normal  ▒ slow  █ critical                               │
│                                                                             │
│  ACTIVE ALERTS                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ [P2] glue-heap-critical-fraud_features    Firing 12 min   @alice   │    │
│  │ [P3] glue-daily-cost-anomaly              Firing 2h       ack'd    │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Data Quality Dashboard

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    DATA QUALITY OBSERVABILITY                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  OVERALL DQ SCORE: 97.2%                                                    │
│  ████████████████████████████████████████████████░░  (target: 99%)          │
│                                                                             │
│  DATASET HEALTH                                                             │
│  ┌─────────────────────┬──────────┬──────────┬──────────┬──────────────┐   │
│  │ Dataset             │ Complete │ Fresh    │ Unique   │ Volume OK    │   │
│  ├─────────────────────┼──────────┼──────────┼──────────┼──────────────┤   │
│  │ orders              │    ✓     │    ✓     │    ✓     │    ✓         │   │
│  │ transactions        │    ✓     │    ✓     │    ✓     │    ✗ (low)   │   │
│  │ user_events         │    ✗     │    ✓     │    ✓     │    ✓         │   │
│  │ inventory           │    ✓     │    ✓     │    ✓     │    ✓         │   │
│  │ fraud_features      │    ✓     │    ✗     │    ✓     │    ✓         │   │
│  └─────────────────────┴──────────┴──────────┴──────────┴──────────────┘   │
│                                                                             │
│  FRESHNESS TRACKER                                                          │
│  orders:          Last update 12 min ago  [████████████████████] OK         │
│  transactions:    Last update 8 min ago   [████████████████████] OK         │
│  fraud_features:  Last update 47 min ago  [████████░░░░░░░░░░░░] WARNING   │
│  regulatory:      Last update 2h ago      [███░░░░░░░░░░░░░░░░░] STALE     │
│                                                                             │
│  SCHEMA CHANGES (7 DAYS)                                                    │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ Jun 28: user_events +column "device_model" (string)     [approved] │    │
│  │ Jun 26: transactions type change "amount" float→double  [approved] │    │
│  │ Jun 25: orders +column "promo_code" (string)            [approved] │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Summary: Observability Maturity Model

```
┌───────────┬────────────────────────────────────────────────────────────────┐
│ Level     │ Capabilities                                                   │
├───────────┼────────────────────────────────────────────────────────────────┤
│ L1 Basic  │ CloudWatch built-in metrics, manual log inspection,            │
│           │ email alerts on failure                                        │
├───────────┼────────────────────────────────────────────────────────────────┤
│ L2 Active │ Custom metrics, structured logging, SLA tracking,              │
│           │ PagerDuty integration, basic dashboards                        │
├───────────┼────────────────────────────────────────────────────────────────┤
│ L3 Mature │ Auto-remediation, anomaly detection, cost attribution,         │
│           │ data quality monitoring, Grafana/DataDog dashboards            │
├───────────┼────────────────────────────────────────────────────────────────┤
│ L4 Elite  │ Predictive alerting (ML-based), self-healing pipelines,        │
│           │ capacity planning, chaos engineering, full audit trail          │
└───────────┴────────────────────────────────────────────────────────────────┘
```

Target: Reach L3 within 6 months, L4 within 12 months for critical pipelines.
