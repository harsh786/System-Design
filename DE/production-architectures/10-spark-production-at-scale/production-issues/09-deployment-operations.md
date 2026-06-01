# Category 9: Deployment & Operations Issues (Issues 81-90)

> Operational issues kill production reliability. A perfectly tuned Spark job is worthless if deployment, dependency management, or CI/CD is broken.

---

## Issue #81: Dependency Conflicts (JAR Hell)

**Frequency**: High  
**Severity**: High - NoSuchMethodError at runtime  
**Spark Component**: ClassLoader, SparkSubmit

### Symptoms
```
java.lang.NoSuchMethodError: com.google.common.collect.ImmutableMap.of(...)
java.lang.ClassNotFoundException: org.apache.hadoop.fs.s3a.S3AFileSystem
java.lang.LinkageError: loader constraint violation
# Different behavior locally vs cluster (different JARs available)
# "It works on my machine" syndrome
```

### Root Cause
- Application JAR bundles a library version different from cluster's
- Spark's Guava version conflicts with application's Guava
- Hadoop/AWS SDK version on cluster differs from compile time
- Multiple JARs providing same class (first one wins, non-deterministic)

### Solution
```python
# 1. Use "provided" scope for Spark/Hadoop dependencies
# pom.xml:
# <dependency>
#   <groupId>org.apache.spark</groupId>
#   <artifactId>spark-sql_2.12</artifactId>
#   <scope>provided</scope>  <!-- Don't bundle with app -->
# </dependency>

# 2. Shade conflicting dependencies
# maven-shade-plugin: relocate com.google → shaded.com.google
# sbt-assembly: assemblyShadeRules += ShadeRule.rename("com.google.**" -> "shaded.@0")

# 3. Use --packages for runtime resolution (avoid bundling)
# spark-submit --packages org.apache.iceberg:iceberg-spark-runtime-3.4_2.12:1.4.2

# 4. Isolate user classes from Spark classes
spark.conf.set("spark.driver.userClassPathFirst", "true")
spark.conf.set("spark.executor.userClassPathFirst", "true")
# Your JARs load before Spark's → your versions win

# 5. For PySpark: pin exact dependency versions
# requirements.txt:
# pandas==2.0.3
# pyarrow==12.0.1
# numpy==1.24.3
# Use: spark-submit --archives venv.tar.gz#venv

# 6. Docker-based isolation (K8s)
# Bundle ALL dependencies in Docker image
# No cluster-level JARs to conflict with
# Dockerfile:
# FROM spark:3.4.1-python3
# COPY app.jar /opt/spark/jars/
# COPY requirements.txt .
# RUN pip install -r requirements.txt
```

---

## Issue #82: Job Scheduling Failures (Airflow/Orchestrator Issues)

**Frequency**: High  
**Severity**: High - missed SLAs  
**Spark Component**: External (Airflow, Dagster, Step Functions)

### Symptoms
```
# Airflow task stuck in "queued" state for hours
# spark-submit returns success but job actually failed
# Retry logic retries wrong granularity (reruns entire DAG vs one task)
# Sensor timeout waiting for upstream data
# DAG dependency deadlock (circular waits)
```

### Root Cause
- Airflow worker pool exhausted
- spark-submit exit code doesn't reflect actual job success
- No data-aware triggering (time-based schedule, data not ready)
- Overly aggressive retry (compounds failure)
- Resource contention between orchestrator and Spark

### Solution
```python
# 1. Use SparkSubmitOperator properly (not BashOperator)
from airflow.providers.apache.spark.operators.spark_submit import SparkSubmitOperator

submit_task = SparkSubmitOperator(
    task_id="run_etl",
    application="/path/to/app.py",
    conn_id="spark_default",
    conf={
        "spark.executor.memory": "16g",
        "spark.dynamicAllocation.maxExecutors": "100",
    },
    # Important: deploy mode cluster → job runs independently of Airflow worker
    deploy_mode="cluster",
)

# 2. Validate job success (not just exit code)
def verify_output(**context):
    """Validate job actually produced correct output."""
    output = spark.read.parquet("s3://output/date=2024-01-01/")
    row_count = output.count()
    if row_count < 1000000:
        raise ValueError(f"Expected >1M rows, got {row_count}")

verify_task = PythonOperator(
    task_id="verify_output",
    python_callable=verify_output,
)

# 3. Data-aware scheduling (instead of fixed schedule)
# Use Airflow Sensors or Data-Aware Scheduling:
wait_for_data = S3KeySensor(
    task_id="wait_for_source",
    bucket_key="input/date={{ ds }}/_SUCCESS",
    timeout=7200,  # Wait up to 2 hours
    poke_interval=300,  # Check every 5 min
)

# 4. Idempotent tasks (safe to retry)
# Each task should produce same result regardless of retry count
# Use: overwrite mode, MERGE, or dynamic partition overwrite

# 5. Retry strategy
submit_task = SparkSubmitOperator(
    retries=3,
    retry_delay=timedelta(minutes=10),
    retry_exponential_backoff=True,
    max_retry_delay=timedelta(hours=1),
)
```

---

## Issue #83: Environment Parity (Dev/Staging/Prod Differences)

**Frequency**: High  
**Severity**: Medium-High - "works in dev, fails in prod"  
**Spark Component**: Configuration, Runtime Environment

### Symptoms
```
# Job passes in dev with 1GB sample, fails in prod with 10TB
# Different Spark versions between environments
# Config tuned for dev doesn't scale to prod
# Secrets/credentials not available in prod but hardcoded in dev
# Python packages differ between environments
```

### Root Cause
- Different cluster sizes/configurations per environment
- Data volume differences masking issues (OOM only at scale)
- Hardcoded paths, credentials, or configs per environment
- No infrastructure-as-code for Spark configurations
- Different library versions between environments

### Solution
```python
# 1. Environment-aware configuration
import os

ENV = os.getenv("ENVIRONMENT", "dev")

configs = {
    "dev": {
        "spark.executor.memory": "4g",
        "spark.executor.instances": "4",
        "spark.sql.shuffle.partitions": "50",
    },
    "staging": {
        "spark.executor.memory": "8g",
        "spark.executor.instances": "20",
        "spark.sql.shuffle.partitions": "200",
    },
    "prod": {
        "spark.executor.memory": "16g",
        "spark.dynamicAllocation.maxExecutors": "200",
        "spark.sql.shuffle.partitions": "2000",
    }
}

for key, value in configs[ENV].items():
    spark.conf.set(key, value)

# 2. Docker-based environments (identical everywhere)
# Same Docker image in dev/staging/prod
# Only difference: resource allocation and data volume
# Dockerfile pins ALL versions exactly

# 3. Scale testing in staging
# Monthly: run prod-scale data through staging pipeline
# Catch: OOM, timeouts, skew issues before they hit prod

# 4. Configuration as code (version controlled)
# spark-config/
#   base.conf          # Shared across all envs
#   dev.conf           # Dev overrides
#   prod.conf          # Prod overrides
# Deployed via CI/CD pipeline

# 5. Secret management
# Never hardcode! Use:
# - AWS Secrets Manager
# - K8s Secrets
# - Airflow Variables/Connections
spark.conf.set("spark.hadoop.fs.s3a.access.key", 
    os.getenv("AWS_ACCESS_KEY_ID"))  # From environment/vault

# 6. Data contracts for test data
# Generate realistic test data at appropriate scale:
# dev: 0.1% of prod (representative sample)
# staging: 10% of prod (scale-meaningful)
```

---

## Issue #84: Rolling Deployments Breaking Running Jobs

**Frequency**: Medium  
**Severity**: Critical - production job failures during deploy  
**Spark Component**: External (K8s, YARN)

### Symptoms
```
# New version deployed → running Spark jobs fail
# Executor pods terminated during rolling update
# Shared Hive Metastore schema migration during job execution
# JAR update on HDFS while executors using old version
# Config change takes effect mid-execution
```

### Root Cause
- Kubernetes rolling update kills executor pods
- Shared infrastructure (metastore, shuffle service) updated while jobs running
- No blue-green deployment for Spark applications
- Library update breaks running jobs that loaded old version

### Solution
```python
# 1. Blue-Green deployment for batch jobs
# Version A running → Deploy Version B alongside (don't kill A)
# Version B starts processing next batch
# Version A finishes its current batch → terminate
# Never interrupt running Spark applications

# 2. K8s: Use pod disruption budgets
# PodDisruptionBudget:
#   maxUnavailable: 0  # Never kill running Spark executor pods
#   selector: app=spark-executor

# 3. Canary deployment with data validation
# Deploy new version processing 1% of data
# Validate output quality
# Gradually increase to 100%

# 4. Deployment windows (schedule around critical jobs)
# Only deploy during maintenance windows
# Critical jobs: 02:00-06:00 → deploy between 10:00-14:00

# 5. Graceful shutdown handling
def shutdown_handler(signal, frame):
    """Handle SIGTERM during shutdown."""
    print("Received shutdown signal, completing current batch...")
    # Finish current micro-batch
    # Commit checkpoint
    # Then exit gracefully
    query.stop()
    spark.stop()
    sys.exit(0)

import signal
signal.signal(signal.SIGTERM, shutdown_handler)

# 6. Version pinning for shared services
# Pin metastore schema version (don't auto-migrate during deploys)
# Pin shuffle service version per Spark version
# Use separate shuffle services for different app versions
```

---

## Issue #85: Log Management at Scale (Debugging Impossible)

**Frequency**: High  
**Severity**: Medium - can't diagnose production issues  
**Spark Component**: Log4j, EventLog, Spark UI

### Symptoms
```
# 500+ Spark jobs generate TBs of logs per day
# Can't find relevant log line for a specific task failure
# Event logs too large for History Server (>10GB per app)
# Log rotation deleting useful history before investigation
# Structured logging not implemented (grep-unfriendly)
```

### Root Cause
- Default DEBUG logging too verbose for production
- No structured logging (everything is unstructured text)
- Event logs not pruned (every RDD lineage recorded)
- Executor logs not aggregated to central location
- No correlation between log entries and specific job/task

### Solution
```python
# 1. Set appropriate log levels for production
# log4j2.properties:
"""
rootLogger.level = WARN
logger.spark.name = org.apache.spark
logger.spark.level = WARN
logger.sql.name = org.apache.spark.sql
logger.sql.level = WARN
# Only your app at INFO:
logger.myapp.name = com.mycompany
logger.myapp.level = INFO
"""

# 2. Structured logging in application code
import json
import logging

logger = logging.getLogger("pipeline")

def log_metric(pipeline_id, stage, metric_name, value):
    logger.info(json.dumps({
        "pipeline_id": pipeline_id,
        "stage": stage,
        "metric": metric_name,
        "value": value,
        "timestamp": datetime.utcnow().isoformat(),
    }))

# Usage:
log_metric("daily_etl", "transform", "records_processed", 15000000)

# 3. Limit event log size
spark.conf.set("spark.eventLog.enabled", "true")
spark.conf.set("spark.eventLog.rolling.enabled", "true")
spark.conf.set("spark.eventLog.rolling.maxFileSize", "128m")
spark.conf.set("spark.eventLog.logStageExecutorMetrics", "true")

# 4. Aggregate executor logs to central location
# Fluentd/Fluent Bit DaemonSet → Loki/Elasticsearch
# Tag logs with: app_name, executor_id, stage_id, task_id

# 5. Correlation IDs through pipeline
pipeline_run_id = str(uuid.uuid4())
spark.conf.set("spark.app.id", pipeline_run_id)
# Include in all log entries for end-to-end tracing

# 6. Post-mortem log extraction (for failed jobs)
# Automatically archive executor logs for failed jobs to S3
# Retain for 30 days for investigation
```

---

## Issue #86: Spark History Server Performance

**Frequency**: Medium  
**Severity**: Medium - can't investigate past failures  
**Spark Component**: SparkHistoryServer, FsHistoryProvider

### Symptoms
```
# History Server UI takes 2+ minutes to load
# OOM on History Server JVM (100+ applications to parse)
# Event log files too large (>10GB) → parser timeout
# History Server crashes when loading complex streaming apps
```

### Root Cause
- Too many applications retained (hundreds with large event logs)
- Large event logs from long-running streaming applications
- Insufficient memory for History Server JVM
- No event log compaction

### Solution
```python
# 1. Increase History Server memory
# spark-env.sh:
# SPARK_DAEMON_MEMORY=8g  (default 1g)
# SPARK_HISTORY_OPTS="-Xmx8g -XX:+UseG1GC"

# 2. Limit retention
spark.conf.set("spark.history.fs.cleaner.enabled", "true")
spark.conf.set("spark.history.fs.cleaner.maxAge", "7d")  # Keep 7 days
spark.conf.set("spark.history.fs.cleaner.interval", "1h")
spark.conf.set("spark.history.retainedApplications", "100")

# 3. Reduce event log verbosity
spark.conf.set("spark.eventLog.logBlockUpdates.enabled", "false")
spark.conf.set("spark.eventLog.longForm.enabled", "false")

# 4. Compress event logs
spark.conf.set("spark.eventLog.compress", "true")
spark.conf.set("spark.eventLog.compression.codec", "zstd")

# 5. Use rolling event logs
spark.conf.set("spark.eventLog.rolling.enabled", "true")
spark.conf.set("spark.eventLog.rolling.maxFileSize", "128m")

# 6. Alternative: use Spark UI live during execution
# For production debugging, use live Spark UI (port 4040)
# History Server is for post-mortem only
# Consider: Grafana dashboards for real-time monitoring instead
```

---

## Issue #87: Spark Job Idempotency Failures

**Frequency**: Medium-High  
**Severity**: High - unsafe to retry, manual intervention needed  
**Spark Component**: Application Logic, Write Operations

### Symptoms
```
# Job fails midway → retry produces duplicates
# Same job run twice → double the output
# Airflow retries task → inconsistent state
# Can't "just rerun" a failed pipeline safely
```

### Root Cause
- Append mode writes are NOT idempotent (two runs = double data)
- No write barriers between stages
- External side effects (API calls, emails) re-executed on retry
- No state tracking (which batches/partitions already processed)

### Solution
```python
# 1. Use overwrite at partition level (inherently idempotent)
spark.conf.set("spark.sql.sources.partitionOverwriteMode", "dynamic")
df.write.mode("overwrite") \
    .partitionBy("date") \
    .parquet("s3://output/")
# Rerun overwrites same partitions → same result

# 2. Use MERGE for idempotent upserts
spark.sql("""
    MERGE INTO target t
    USING source s ON t.id = s.id
    WHEN MATCHED THEN UPDATE SET *
    WHEN NOT MATCHED THEN INSERT *
""")
# Rerun: matched records just get updated → no duplicates

# 3. Track processed state externally
def process_batch(date):
    # Check if already processed
    if batch_already_processed(pipeline_id, date):
        logger.info(f"Skipping {date} - already processed")
        return
    
    # Process
    result = transform(read_source(date))
    result.write.mode("overwrite").save(f"s3://output/date={date}/")
    
    # Mark as processed (only after successful write)
    mark_processed(pipeline_id, date)

# 4. Fence external side effects
def send_notifications(batch_df, batch_id):
    """Only send notifications for truly new events."""
    # Check which events were already notified
    already_notified = spark.read.table("notification_log")
    new_events = batch_df.join(already_notified, "event_id", "left_anti")
    
    # Send only new
    notify(new_events)
    
    # Log as notified
    new_events.select("event_id", F.current_timestamp().alias("notified_at")) \
        .write.mode("append").saveAsTable("notification_log")

# 5. Adopt "exactly-once" pipeline pattern
# Input (committed offset) → Process → Output (atomic write) → Commit offset
# If any step fails: restart from last committed offset
# Output is idempotent (overwrite or merge)
```

---

## Issue #88: Secret/Credential Exposure in Spark Configs

**Frequency**: Medium  
**Severity**: Critical - security breach  
**Spark Component**: SparkConf, Environment, Spark UI

### Symptoms
```
# Database password visible in Spark UI "Environment" tab
# AWS keys in spark-submit command visible to all users
# Secrets in event log files (stored on S3 indefinitely)
# Credentials in driver/executor logs
```

### Root Cause
- Credentials passed as spark.conf properties (visible in UI)
- Secrets in spark-submit --conf arguments (visible in process list)
- JDBC URLs with embedded passwords
- No secret masking in log files

### Solution
```python
# 1. Use secret managers (never pass in spark-submit)
import boto3
def get_secret(secret_name):
    client = boto3.client("secretsmanager")
    return client.get_secret_value(SecretId=secret_name)["SecretString"]

db_password = get_secret("prod/db/password")
# Use in JDBC without exposing in conf:
df = spark.read.format("jdbc") \
    .option("url", "jdbc:postgresql://host:5432/db") \
    .option("user", "app_user") \
    .option("password", db_password) \  # Retrieved at runtime, not in conf
    .load()

# 2. Mask secrets in Spark UI
spark.conf.set("spark.redaction.regex", 
    "(?i)secret|password|token|key|credential")
# Any property matching these patterns shows as "********" in UI

# 3. For S3/cloud access: use IAM roles (no keys needed)
# EMR: Instance Profile → no access keys in config
# K8s: IRSA (IAM Roles for Service Accounts)
# Never: spark.hadoop.fs.s3a.access.key in config!

# 4. K8s Secrets mounted as files
# Mount secret as file, read at runtime:
spark.conf.set("spark.kubernetes.driver.secretKeyRef.DB_PASSWORD", 
    "db-secret:password")
# Access: os.getenv("DB_PASSWORD")

# 5. Exclude secrets from event logs
spark.conf.set("spark.eventLog.redactedKeys", 
    "spark.hadoop.fs.s3a.access.key,spark.hadoop.fs.s3a.secret.key")

# 6. Audit: scan configs for exposed secrets
# CI/CD check: grep for hardcoded passwords/keys in spark configs
# Fail build if found
```

---

## Issue #89: Spark Upgrade / Migration Failures

**Frequency**: Low (but painful when it happens)  
**Severity**: High - extended downtime  
**Spark Component**: API changes, Configuration, Behavior changes

### Symptoms
```
# After Spark 3.2 → 3.4 upgrade:
# Queries return different results (behavior change!)
# AnalysisException for previously valid queries
# Performance regression (optimizer change)
# UDFs not compatible (API change)
# Streaming checkpoints can't be read by new version
```

### Root Cause
- Breaking behavior changes between Spark versions
- Deprecated APIs removed in new version
- Default configuration values changed
- Catalyst optimizer changes affecting query plans
- Streaming checkpoint format not backward compatible

### Solution
```python
# 1. Read migration guide THOROUGHLY
# https://spark.apache.org/docs/latest/migration-guide.html
# Key areas: SQL behavior, timestamp handling, type coercion

# 2. Run comprehensive test suite against new version
# Unit tests: all transformation logic
# Integration tests: end-to-end with realistic data
# Performance tests: compare timing on same dataset (both versions)
# Result comparison: exact output comparison (old vs new version)

# 3. Handle known behavior changes
# Spark 3.0: TIMESTAMP_NTZ vs TIMESTAMP_LTZ
spark.conf.set("spark.sql.timestampType", "TIMESTAMP_LTZ")  # Legacy behavior

# Spark 3.1: CHAR/VARCHAR semantics changed
spark.conf.set("spark.sql.charVarcharAsString", "true")  # Legacy behavior

# Spark 3.2: Adaptive query execution enabled by default
spark.conf.set("spark.sql.adaptive.enabled", "true")  # Was false before

# 4. Streaming: checkpoint compatibility
# CRITICAL: Streaming checkpoints are NOT guaranteed compatible across versions!
# Strategy:
# a) Stop streaming query gracefully with old version
# b) Note final committed offsets
# c) Start new version with NEW checkpoint location
# d) Set startingOffsets to pick up from where old version left off

# 5. Gradual rollout
# Week 1: Upgrade non-critical adhoc workloads
# Week 2: Upgrade staging pipelines
# Week 3: Upgrade prod batch pipelines (during maintenance window)
# Week 4: Upgrade prod streaming (with fallback plan)

# 6. Keep fallback ready
# Docker image: pin to old version for rollback
# spark-submit: version-specific submission scripts
# Rollback plan: < 15 minutes to revert to old version
```

---

## Issue #90: Cost Overruns from Unmonitored Jobs

**Frequency**: Very High  
**Severity**: High - budget blown, no visibility  
**Spark Component**: Resource consumption (cluster cost)

### Symptoms
```
# Monthly bill: expected $50K, actual $200K
# One runaway job consumed $30K in a weekend
# Notebook left running for 2 weeks with 100 executors
# No attribution: which team/pipeline caused cost spike?
# Spot instances expired, fell back to on-demand silently
```

### Root Cause
- No per-job cost tracking
- No resource limits per user/team
- Clusters not auto-scaling down
- Abandoned notebooks/queries holding resources
- No alerts on cost anomalies

### Solution
```python
# 1. Tag all Spark applications for cost attribution
spark.conf.set("spark.app.name", "team-a/daily-etl/revenue-pipeline")
# EMR: tag instances with team/pipeline
# K8s: labels on pods

# 2. Set hard limits per job
spark.conf.set("spark.dynamicAllocation.maxExecutors", "100")
spark.conf.set("spark.executor.instances", "50")  # Cap

# 3. Auto-terminate idle resources
spark.conf.set("spark.dynamicAllocation.executorIdleTimeout", "60s")
# EMR: auto-terminate cluster after idle
# Notebooks: auto-stop after 2 hours inactive

# 4. Cost alerting
# Monitor: daily cost per application tag
# Alert: cost exceeds 2x historical average for same pipeline
# Alert: executor-hours per job exceeds budget threshold

# 5. Spot instance strategy
# Use Spot for batch (accept interruption, retry logic)
# Use On-Demand for streaming (can't tolerate interruption)
# Monitor: Spot vs On-Demand ratio (target 80% Spot)

# 6. Right-sizing audit (monthly)
# For each pipeline:
#   actual_executor_utilization = CPU_time / (allocated_cores * wall_time)
#   if utilization < 30%: reduce executor count/size
#   if utilization > 80%: consider scaling up (avoiding timeouts)

# 7. Budget enforcement
# K8s ResourceQuota per namespace (team)
# YARN: max capacity per queue
# Auto-kill: jobs exceeding cost threshold
```

---

## Summary: Deployment & Operations Decision Tree

```
Operational issue
├── Code/dependency issues?
│   ├── JAR conflicts at runtime → Issue #81 (shade, userClassPathFirst)
│   ├── Version mismatch (dev vs prod) → Issue #83 (Docker, env config)
│   ├── Spark upgrade broke things → Issue #89 (migration guide, gradual rollout)
│   └── Secrets exposed → Issue #88 (secret manager, IAM roles)
├── Job management?
│   ├── Scheduling failures → Issue #82 (proper operators, data-aware)
│   ├── Can't safely retry → Issue #87 (idempotent writes, MERGE)
│   ├── Deploy breaks running jobs → Issue #84 (blue-green, PDB)
│   └── Cost overruns → Issue #90 (tagging, limits, alerts)
└── Observability?
    ├── Can't find relevant logs → Issue #85 (structured logging, levels)
    └── History Server unusable → Issue #86 (memory, retention, rolling)
```
