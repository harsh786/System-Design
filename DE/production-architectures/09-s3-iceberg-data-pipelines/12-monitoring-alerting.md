# Monitoring, Alerting & Observability for Iceberg Data Pipelines

## Architecture Overview

```
+-------------------+     +-------------------+     +-------------------+
|  Iceberg Tables   |     |  Spark/Flink/Trino|     |  AWS Services     |
|  (S3 + Catalog)   |     |  (JMX Metrics)    |     |  (CloudWatch)     |
+--------+----------+     +--------+----------+     +--------+----------+
         |                          |                          |
         v                          v                          v
+--------+----------+     +--------+----------+     +--------+----------+
| Iceberg Metadata  |     |   JMX Exporter    |     | CloudWatch        |
| Exporter (Custom) |     |   (Prometheus)    |     | Exporter          |
+--------+----------+     +--------+----------+     +--------+----------+
         |                          |                          |
         +------------+-------------+--------------------------+
                      |
                      v
         +------------+-------------+
         |       Prometheus         |
         |   (Metrics Storage)      |
         +------------+-------------+
                      |
         +------------+-------------+------------+
         |            |             |             |
         v            v             v             v
+--------+--+ +------+------+ +----+-----+ +----+--------+
|  Grafana  | | AlertManager| |  PagerDuty| |  OpsGenie   |
| Dashboards| |  (Rules)    | |           | |             |
+-----------+ +-------------+ +----------+ +-------------+
                                    |
                      +-------------+-------------+
                      |                           |
                      v                           v
              +-------+-------+         +---------+---------+
              |   Runbooks    |         |   Slack/Teams     |
              | (Confluence)  |         |   Notifications   |
              +---------------+         +-------------------+
```

---

## 1. What to Monitor for Iceberg Tables

### Critical Iceberg-Specific Metrics

| Metric | Why It Matters | Threshold (Example) |
|--------|---------------|-------------------|
| Snapshot count growth | Unbounded growth = missing expiration | > 1000 snapshots |
| File count per partition | Too many small files = slow queries | > 500 files/partition |
| Average file size | Small files degrade scan performance | < 32MB average |
| Delete file accumulation | MoR read amplification | > 100 delete files |
| Manifest count | Too many manifests = slow planning | > 200 manifests |
| Orphan files | Wasted storage cost | > 0 after cleanup window |
| Commit latency | Catalog contention | > 5s p99 |
| Conflict/retry rate | Write contention | > 5% retries |
| Data freshness | Time since last successful commit | Depends on SLA |
| Table size growth rate | Capacity planning | Anomaly detection |
| Partition count | Unbounded partition growth | > 10,000 partitions |

### Merge-on-Read (MoR) Read Amplification

```
Read Amplification = (data_files_scanned + delete_files_applied) / data_files_scanned

Warning: ratio > 1.5
Critical: ratio > 3.0
```

When delete files accumulate, every read must apply positional or equality deletes, dramatically increasing I/O and CPU usage.

---

## 2. Prometheus Iceberg Metadata Exporter (Python)

### Complete Exporter Implementation

```python
#!/usr/bin/env python3
"""
Prometheus exporter for Apache Iceberg table metadata.
Queries the Iceberg catalog and exposes table health metrics.

Requirements:
    pip install pyiceberg prometheus-client boto3 schedule
"""

import time
import logging
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional
from dataclasses import dataclass

from prometheus_client import (
    start_http_server,
    Gauge,
    Counter,
    Histogram,
    Info,
    REGISTRY,
)
from pyiceberg.catalog import load_catalog
from pyiceberg.table import Table
from pyiceberg.manifest import ManifestFile
import schedule
import threading

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ─── Configuration ───────────────────────────────────────────────────────────

CATALOG_NAME = os.getenv("ICEBERG_CATALOG_NAME", "glue")
CATALOG_URI = os.getenv("ICEBERG_CATALOG_URI", "")
WAREHOUSE = os.getenv("ICEBERG_WAREHOUSE", "s3://my-warehouse/")
NAMESPACES = os.getenv("ICEBERG_NAMESPACES", "analytics,raw,curated").split(",")
SCRAPE_INTERVAL_SECONDS = int(os.getenv("SCRAPE_INTERVAL", "300"))
EXPORTER_PORT = int(os.getenv("EXPORTER_PORT", "9101"))

# ─── Prometheus Metrics ──────────────────────────────────────────────────────

# Table-level metrics
SNAPSHOT_COUNT = Gauge(
    "iceberg_table_snapshot_count",
    "Number of snapshots in the table",
    ["namespace", "table"],
)
CURRENT_SNAPSHOT_AGE_SECONDS = Gauge(
    "iceberg_table_current_snapshot_age_seconds",
    "Age of the current snapshot in seconds (data freshness)",
    ["namespace", "table"],
)
TOTAL_DATA_FILES = Gauge(
    "iceberg_table_total_data_files",
    "Total number of data files",
    ["namespace", "table"],
)
TOTAL_DELETE_FILES = Gauge(
    "iceberg_table_total_delete_files",
    "Total number of delete files (MoR)",
    ["namespace", "table"],
)
TOTAL_RECORDS = Gauge(
    "iceberg_table_total_records",
    "Total number of records in the table",
    ["namespace", "table"],
)
TOTAL_SIZE_BYTES = Gauge(
    "iceberg_table_total_size_bytes",
    "Total size of data files in bytes",
    ["namespace", "table"],
)
AVG_FILE_SIZE_BYTES = Gauge(
    "iceberg_table_avg_file_size_bytes",
    "Average data file size in bytes",
    ["namespace", "table"],
)
MANIFEST_COUNT = Gauge(
    "iceberg_table_manifest_count",
    "Number of manifest files",
    ["namespace", "table"],
)
PARTITION_COUNT = Gauge(
    "iceberg_table_partition_count",
    "Number of partitions with data",
    ["namespace", "table"],
)
READ_AMPLIFICATION = Gauge(
    "iceberg_table_read_amplification_ratio",
    "Ratio of (data_files + delete_files) / data_files",
    ["namespace", "table"],
)
MAX_FILES_PER_PARTITION = Gauge(
    "iceberg_table_max_files_per_partition",
    "Maximum file count in any single partition",
    ["namespace", "table"],
)
SCHEMA_VERSION = Gauge(
    "iceberg_table_schema_version",
    "Current schema version ID",
    ["namespace", "table"],
)
LAST_COMMIT_TIMESTAMP = Gauge(
    "iceberg_table_last_commit_timestamp_seconds",
    "Unix timestamp of last commit",
    ["namespace", "table"],
)

# Exporter health
SCRAPE_DURATION = Histogram(
    "iceberg_exporter_scrape_duration_seconds",
    "Time taken to scrape all tables",
    buckets=[1, 5, 10, 30, 60, 120, 300],
)
SCRAPE_ERRORS = Counter(
    "iceberg_exporter_scrape_errors_total",
    "Total scrape errors",
    ["namespace", "table"],
)
TABLES_SCRAPED = Gauge(
    "iceberg_exporter_tables_scraped",
    "Number of tables successfully scraped in last run",
)


@dataclass
class TableMetrics:
    namespace: str
    table_name: str
    snapshot_count: int
    current_snapshot_age_seconds: float
    total_data_files: int
    total_delete_files: int
    total_records: int
    total_size_bytes: int
    avg_file_size_bytes: float
    manifest_count: int
    partition_count: int
    read_amplification: float
    max_files_per_partition: int
    schema_version: int
    last_commit_ts: float


class IcebergMetricsCollector:
    def __init__(self):
        self.catalog = load_catalog(
            CATALOG_NAME,
            **{
                "uri": CATALOG_URI,
                "warehouse": WAREHOUSE,
                "type": "glue",  # or "rest", "hive", etc.
            },
        )

    def collect_table_metrics(self, namespace: str, table_name: str) -> Optional[TableMetrics]:
        """Collect all metrics for a single Iceberg table."""
        try:
            table = self.catalog.load_table(f"{namespace}.{table_name}")
            metadata = table.metadata
            current_snapshot = table.current_snapshot()

            if current_snapshot is None:
                logger.warning(f"Table {namespace}.{table_name} has no snapshots")
                return None

            # Snapshot count
            snapshot_count = len(metadata.snapshots)

            # Data freshness
            snapshot_ts = current_snapshot.timestamp_ms / 1000.0
            age_seconds = time.time() - snapshot_ts

            # File statistics from the snapshot summary
            summary = current_snapshot.summary or {}
            total_data_files = int(summary.get("total-data-files", 0))
            total_delete_files = int(summary.get("total-delete-files", 0))
            total_records = int(summary.get("total-records", 0))
            total_size_bytes = int(summary.get("total-files-size", 0))

            # Average file size
            avg_file_size = (
                total_size_bytes / total_data_files if total_data_files > 0 else 0
            )

            # Manifest count
            manifest_list = current_snapshot.manifests(table.io)
            manifest_count = len(manifest_list)

            # Partition stats (simplified - count unique partitions from manifests)
            partition_count = self._count_partitions(manifest_list, table)
            max_files_partition = self._max_files_per_partition(manifest_list, table)

            # Read amplification
            read_amp = (
                (total_data_files + total_delete_files) / total_data_files
                if total_data_files > 0
                else 1.0
            )

            # Schema version
            schema_version = metadata.current_schema_id

            return TableMetrics(
                namespace=namespace,
                table_name=table_name,
                snapshot_count=snapshot_count,
                current_snapshot_age_seconds=age_seconds,
                total_data_files=total_data_files,
                total_delete_files=total_delete_files,
                total_records=total_records,
                total_size_bytes=total_size_bytes,
                avg_file_size_bytes=avg_file_size,
                manifest_count=manifest_count,
                partition_count=partition_count,
                read_amplification=read_amp,
                max_files_per_partition=max_files_partition,
                schema_version=schema_version,
                last_commit_ts=snapshot_ts,
            )

        except Exception as e:
            logger.error(f"Error collecting metrics for {namespace}.{table_name}: {e}")
            SCRAPE_ERRORS.labels(namespace=namespace, table=table_name).inc()
            return None

    def _count_partitions(self, manifests: List, table: Table) -> int:
        """Count distinct partitions across all manifests."""
        partitions = set()
        for manifest in manifests:
            if manifest.partitions:
                for partition_summary in manifest.partitions:
                    partitions.add(str(partition_summary))
        return len(partitions) if partitions else 0

    def _max_files_per_partition(self, manifests: List, table: Table) -> int:
        """Find the maximum file count in any partition."""
        partition_files: Dict[str, int] = {}
        for manifest in manifests:
            if manifest.partitions:
                key = str(manifest.partitions)
                partition_files[key] = partition_files.get(key, 0) + manifest.existing_files_count
        return max(partition_files.values()) if partition_files else 0

    def scrape_all(self):
        """Scrape metrics for all configured tables."""
        start = time.time()
        tables_scraped = 0

        for namespace in NAMESPACES:
            try:
                table_names = self.catalog.list_tables(namespace)
                for _, table_name in table_names:
                    metrics = self.collect_table_metrics(namespace, table_name)
                    if metrics:
                        self._publish_metrics(metrics)
                        tables_scraped += 1
            except Exception as e:
                logger.error(f"Error listing tables in namespace {namespace}: {e}")

        TABLES_SCRAPED.set(tables_scraped)
        duration = time.time() - start
        SCRAPE_DURATION.observe(duration)
        logger.info(f"Scraped {tables_scraped} tables in {duration:.2f}s")

    def _publish_metrics(self, m: TableMetrics):
        """Publish collected metrics to Prometheus gauges."""
        labels = {"namespace": m.namespace, "table": m.table_name}

        SNAPSHOT_COUNT.labels(**labels).set(m.snapshot_count)
        CURRENT_SNAPSHOT_AGE_SECONDS.labels(**labels).set(m.current_snapshot_age_seconds)
        TOTAL_DATA_FILES.labels(**labels).set(m.total_data_files)
        TOTAL_DELETE_FILES.labels(**labels).set(m.total_delete_files)
        TOTAL_RECORDS.labels(**labels).set(m.total_records)
        TOTAL_SIZE_BYTES.labels(**labels).set(m.total_size_bytes)
        AVG_FILE_SIZE_BYTES.labels(**labels).set(m.avg_file_size_bytes)
        MANIFEST_COUNT.labels(**labels).set(m.manifest_count)
        PARTITION_COUNT.labels(**labels).set(m.partition_count)
        READ_AMPLIFICATION.labels(**labels).set(m.read_amplification)
        MAX_FILES_PER_PARTITION.labels(**labels).set(m.max_files_per_partition)
        SCHEMA_VERSION.labels(**labels).set(m.schema_version)
        LAST_COMMIT_TIMESTAMP.labels(**labels).set(m.last_commit_ts)


def run_scheduler(collector: IcebergMetricsCollector):
    """Run the scrape loop on a schedule."""
    collector.scrape_all()  # Initial scrape
    schedule.every(SCRAPE_INTERVAL_SECONDS).seconds.do(collector.scrape_all)
    while True:
        schedule.run_pending()
        time.sleep(1)


def main():
    logger.info(f"Starting Iceberg metrics exporter on port {EXPORTER_PORT}")
    logger.info(f"Scrape interval: {SCRAPE_INTERVAL_SECONDS}s")
    logger.info(f"Namespaces: {NAMESPACES}")

    collector = IcebergMetricsCollector()
    start_http_server(EXPORTER_PORT)

    scheduler_thread = threading.Thread(target=run_scheduler, args=(collector,), daemon=True)
    scheduler_thread.start()

    # Keep main thread alive
    while True:
        time.sleep(60)


if __name__ == "__main__":
    main()
```

### Dockerfile for Exporter

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY iceberg_exporter.py .

ENV EXPORTER_PORT=9101
ENV SCRAPE_INTERVAL=300
EXPOSE 9101

CMD ["python", "iceberg_exporter.py"]
```

### Kubernetes Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: iceberg-metrics-exporter
  namespace: monitoring
spec:
  replicas: 1
  selector:
    matchLabels:
      app: iceberg-metrics-exporter
  template:
    metadata:
      labels:
        app: iceberg-metrics-exporter
      annotations:
        prometheus.io/scrape: "true"
        prometheus.io/port: "9101"
    spec:
      serviceAccountName: iceberg-exporter-sa
      containers:
        - name: exporter
          image: myregistry/iceberg-metrics-exporter:latest
          ports:
            - containerPort: 9101
          env:
            - name: ICEBERG_CATALOG_NAME
              value: "glue"
            - name: ICEBERG_WAREHOUSE
              value: "s3://data-lakehouse-prod/"
            - name: ICEBERG_NAMESPACES
              value: "raw,curated,analytics,ml_features"
            - name: SCRAPE_INTERVAL
              value: "300"
          resources:
            requests:
              memory: "256Mi"
              cpu: "100m"
            limits:
              memory: "512Mi"
              cpu: "500m"
          livenessProbe:
            httpGet:
              path: /metrics
              port: 9101
            initialDelaySeconds: 30
            periodSeconds: 60
---
apiVersion: v1
kind: Service
metadata:
  name: iceberg-metrics-exporter
  namespace: monitoring
  labels:
    app: iceberg-metrics-exporter
spec:
  ports:
    - port: 9101
      targetPort: 9101
  selector:
    app: iceberg-metrics-exporter
```

---

## 3. JMX Metrics from Spark/Flink/Trino

### Spark Metrics Configuration

```properties
# metrics.properties (placed in Spark conf directory)
*.sink.prometheusServlet.class=org.apache.spark.metrics.sink.PrometheusServlet
*.sink.prometheusServlet.path=/metrics/prometheus
master.source.jvm.class=org.apache.spark.metrics.source.JvmSource
worker.source.jvm.class=org.apache.spark.metrics.source.JvmSource
driver.source.jvm.class=org.apache.spark.metrics.source.JvmSource
executor.source.jvm.class=org.apache.spark.metrics.source.JvmSource
```

### Flink Metrics Reporter

```yaml
# flink-conf.yaml
metrics.reporters: prom
metrics.reporter.prom.factory.class: org.apache.flink.metrics.prometheus.PrometheusReporterFactory
metrics.reporter.prom.port: 9249
metrics.scope.jm: flink.jobmanager
metrics.scope.jm.job: flink.jobmanager.<job_name>
metrics.scope.tm: flink.taskmanager.<tm_id>
metrics.scope.tm.job: flink.taskmanager.<tm_id>.<job_name>
metrics.scope.task: flink.taskmanager.<tm_id>.<job_name>.<task_name>.<subtask_index>
```

### Trino JMX Exporter

```yaml
# jmx_exporter_config.yaml
---
startDelaySeconds: 0
hostPort: 127.0.0.1:9080
rules:
  - pattern: "trino.plugin.iceberg<type=IcebergMetadata, catalog=(.+)><>(.*)"
    name: "trino_iceberg_metadata_$2"
    labels:
      catalog: "$1"
  - pattern: "trino.execution<name=QueryManager><>(RunningQueries|QueuedQueries|CompletedQueries.TotalCount)"
    name: "trino_query_manager_$1"
  - pattern: "trino.memory<type=ClusterMemoryPool, name=general><>(FreeBytes|TotalBytes|ReservedBytes)"
    name: "trino_cluster_memory_$1"
  - pattern: "trino.execution<name=QueryExecution><>(Splits.*|WallTime.*|CpuTime.*)"
    name: "trino_query_execution_$1"
```

---

## 4. Prometheus Alert Rules

```yaml
# iceberg-alerts.yml
groups:
  - name: iceberg_table_health
    rules:
      # ─── Snapshot Growth ────────────────────────────────────────────────
      - alert: IcebergSnapshotCountHigh
        expr: iceberg_table_snapshot_count > 1000
        for: 10m
        labels:
          severity: warning
          team: data-platform
        annotations:
          summary: "Iceberg table {{ $labels.namespace }}.{{ $labels.table }} has {{ $value }} snapshots"
          description: "Snapshot expiration may not be running. Expected < 1000."
          runbook_url: "https://wiki.internal/runbooks/iceberg-snapshot-growth"

      - alert: IcebergSnapshotCountCritical
        expr: iceberg_table_snapshot_count > 5000
        for: 5m
        labels:
          severity: critical
          team: data-platform
        annotations:
          summary: "CRITICAL: {{ $labels.namespace }}.{{ $labels.table }} has {{ $value }} snapshots"
          description: "Table metadata is dangerously large. Immediate action required."
          runbook_url: "https://wiki.internal/runbooks/iceberg-snapshot-growth"

      # ─── Data Freshness ────────────────────────────────────────────────
      - alert: IcebergDataStale
        expr: iceberg_table_current_snapshot_age_seconds > 3600
        for: 15m
        labels:
          severity: warning
          team: data-platform
        annotations:
          summary: "Table {{ $labels.namespace }}.{{ $labels.table }} has no commits in {{ $value | humanizeDuration }}"
          description: "Pipeline may be stalled. Check upstream DAGs."
          runbook_url: "https://wiki.internal/runbooks/iceberg-data-freshness"

      - alert: IcebergDataStaleCritical
        expr: iceberg_table_current_snapshot_age_seconds > 14400
        for: 5m
        labels:
          severity: critical
          team: data-platform
        annotations:
          summary: "CRITICAL: {{ $labels.namespace }}.{{ $labels.table }} stale for {{ $value | humanizeDuration }}"
          runbook_url: "https://wiki.internal/runbooks/iceberg-data-freshness"

      # ─── Small Files ───────────────────────────────────────────────────
      - alert: IcebergSmallFiles
        expr: iceberg_table_avg_file_size_bytes < 33554432  # 32MB
        for: 30m
        labels:
          severity: warning
          team: data-platform
        annotations:
          summary: "Table {{ $labels.namespace }}.{{ $labels.table }} avg file size is {{ $value | humanize1024 }}B"
          description: "Small files degrade query performance. Compaction may be needed."
          runbook_url: "https://wiki.internal/runbooks/iceberg-small-files"

      - alert: IcebergTooManyFilesPerPartition
        expr: iceberg_table_max_files_per_partition > 500
        for: 15m
        labels:
          severity: warning
          team: data-platform
        annotations:
          summary: "Partition in {{ $labels.namespace }}.{{ $labels.table }} has {{ $value }} files"
          runbook_url: "https://wiki.internal/runbooks/iceberg-small-files"

      # ─── Delete File Accumulation (MoR) ────────────────────────────────
      - alert: IcebergDeleteFileAccumulation
        expr: iceberg_table_total_delete_files > 100
        for: 15m
        labels:
          severity: warning
          team: data-platform
        annotations:
          summary: "{{ $labels.namespace }}.{{ $labels.table }} has {{ $value }} delete files"
          description: "Read amplification is increasing. Run compaction to merge deletes."
          runbook_url: "https://wiki.internal/runbooks/iceberg-delete-files"

      - alert: IcebergReadAmplificationHigh
        expr: iceberg_table_read_amplification_ratio > 2.0
        for: 15m
        labels:
          severity: critical
          team: data-platform
        annotations:
          summary: "Read amplification for {{ $labels.namespace }}.{{ $labels.table }} is {{ $value }}x"
          runbook_url: "https://wiki.internal/runbooks/iceberg-delete-files"

      # ─── Manifest Bloat ────────────────────────────────────────────────
      - alert: IcebergManifestCountHigh
        expr: iceberg_table_manifest_count > 200
        for: 30m
        labels:
          severity: warning
          team: data-platform
        annotations:
          summary: "{{ $labels.namespace }}.{{ $labels.table }} has {{ $value }} manifests"
          description: "Query planning time will degrade. Rewrite manifests."
          runbook_url: "https://wiki.internal/runbooks/iceberg-manifest-rewrite"

      # ─── Schema Drift ─────────────────────────────────────────────────
      - alert: IcebergSchemaChanged
        expr: changes(iceberg_table_schema_version[1h]) > 0
        labels:
          severity: info
          team: data-platform
        annotations:
          summary: "Schema changed for {{ $labels.namespace }}.{{ $labels.table }}"
          description: "Schema version is now {{ $value }}. Verify downstream compatibility."

  - name: iceberg_pipeline_health
    rules:
      - alert: IcebergCommitLatencyHigh
        expr: histogram_quantile(0.99, rate(iceberg_commit_duration_seconds_bucket[5m])) > 5
        for: 10m
        labels:
          severity: warning
          team: data-platform
        annotations:
          summary: "Iceberg commit p99 latency is {{ $value }}s"
          description: "Catalog may be experiencing contention."

      - alert: IcebergCommitConflictRateHigh
        expr: rate(iceberg_commit_conflicts_total[5m]) / rate(iceberg_commits_total[5m]) > 0.05
        for: 10m
        labels:
          severity: warning
          team: data-platform
        annotations:
          summary: "Commit conflict rate is {{ $value | humanizePercentage }}"
          description: "Multiple writers may be conflicting. Check partitioning strategy."
```

---

## 5. Grafana Dashboard Definitions

### Table Health Overview Dashboard

```json
{
  "dashboard": {
    "id": null,
    "uid": "iceberg-table-health",
    "title": "Iceberg Table Health Overview",
    "tags": ["iceberg", "data-platform", "lakehouse"],
    "timezone": "browser",
    "refresh": "5m",
    "time": { "from": "now-24h", "to": "now" },
    "panels": [
      {
        "id": 1,
        "title": "Data Freshness (Hours Since Last Commit)",
        "type": "table",
        "gridPos": { "h": 8, "w": 24, "x": 0, "y": 0 },
        "targets": [
          {
            "expr": "sort_desc(iceberg_table_current_snapshot_age_seconds / 3600)",
            "legendFormat": "{{ namespace }}.{{ table }}",
            "format": "table",
            "instant": true
          }
        ],
        "fieldConfig": {
          "overrides": [
            {
              "matcher": { "id": "byName", "options": "Value" },
              "properties": [
                {
                  "id": "thresholds",
                  "value": {
                    "mode": "absolute",
                    "steps": [
                      { "color": "green", "value": null },
                      { "color": "yellow", "value": 1 },
                      { "color": "red", "value": 4 }
                    ]
                  }
                }
              ]
            }
          ]
        }
      },
      {
        "id": 2,
        "title": "Snapshot Count by Table",
        "type": "bargauge",
        "gridPos": { "h": 8, "w": 12, "x": 0, "y": 8 },
        "targets": [
          {
            "expr": "topk(20, iceberg_table_snapshot_count)",
            "legendFormat": "{{ namespace }}.{{ table }}"
          }
        ],
        "fieldConfig": {
          "defaults": {
            "thresholds": {
              "steps": [
                { "color": "green", "value": null },
                { "color": "yellow", "value": 500 },
                { "color": "red", "value": 1000 }
              ]
            }
          }
        }
      },
      {
        "id": 3,
        "title": "Read Amplification (Delete File Impact)",
        "type": "gauge",
        "gridPos": { "h": 8, "w": 12, "x": 12, "y": 8 },
        "targets": [
          {
            "expr": "topk(10, iceberg_table_read_amplification_ratio)",
            "legendFormat": "{{ namespace }}.{{ table }}"
          }
        ],
        "fieldConfig": {
          "defaults": {
            "thresholds": {
              "steps": [
                { "color": "green", "value": null },
                { "color": "yellow", "value": 1.5 },
                { "color": "red", "value": 3.0 }
              ]
            },
            "max": 5,
            "min": 1
          }
        }
      },
      {
        "id": 4,
        "title": "Average File Size Distribution",
        "type": "timeseries",
        "gridPos": { "h": 8, "w": 12, "x": 0, "y": 16 },
        "targets": [
          {
            "expr": "iceberg_table_avg_file_size_bytes / 1048576",
            "legendFormat": "{{ namespace }}.{{ table }}"
          }
        ],
        "fieldConfig": {
          "defaults": {
            "unit": "decmbytes",
            "custom": {
              "thresholdsStyle": { "mode": "line" }
            },
            "thresholds": {
              "steps": [
                { "color": "red", "value": null },
                { "color": "green", "value": 32 }
              ]
            }
          }
        }
      },
      {
        "id": 5,
        "title": "Total Storage by Table (GB)",
        "type": "piechart",
        "gridPos": { "h": 8, "w": 12, "x": 12, "y": 16 },
        "targets": [
          {
            "expr": "topk(15, iceberg_table_total_size_bytes / 1073741824)",
            "legendFormat": "{{ namespace }}.{{ table }}"
          }
        ]
      },
      {
        "id": 6,
        "title": "Table File Counts Over Time",
        "type": "timeseries",
        "gridPos": { "h": 8, "w": 24, "x": 0, "y": 24 },
        "targets": [
          {
            "expr": "iceberg_table_total_data_files{namespace=~\"$namespace\", table=~\"$table\"}",
            "legendFormat": "data files - {{ table }}"
          },
          {
            "expr": "iceberg_table_total_delete_files{namespace=~\"$namespace\", table=~\"$table\"}",
            "legendFormat": "delete files - {{ table }}"
          }
        ]
      }
    ],
    "templating": {
      "list": [
        {
          "name": "namespace",
          "type": "query",
          "query": "label_values(iceberg_table_snapshot_count, namespace)",
          "multi": true,
          "includeAll": true
        },
        {
          "name": "table",
          "type": "query",
          "query": "label_values(iceberg_table_snapshot_count{namespace=~\"$namespace\"}, table)",
          "multi": true,
          "includeAll": true
        }
      ]
    }
  }
}
```

### Compaction Status Dashboard

```json
{
  "dashboard": {
    "uid": "iceberg-compaction",
    "title": "Iceberg Compaction Status",
    "panels": [
      {
        "id": 1,
        "title": "Tables Needing Compaction (Small Files)",
        "type": "stat",
        "gridPos": { "h": 4, "w": 8, "x": 0, "y": 0 },
        "targets": [
          {
            "expr": "count(iceberg_table_avg_file_size_bytes < 33554432)"
          }
        ]
      },
      {
        "id": 2,
        "title": "Tables with High Delete Files",
        "type": "stat",
        "gridPos": { "h": 4, "w": 8, "x": 8, "y": 0 },
        "targets": [
          {
            "expr": "count(iceberg_table_total_delete_files > 50)"
          }
        ]
      },
      {
        "id": 3,
        "title": "Compaction Job Duration (Last 24h)",
        "type": "timeseries",
        "gridPos": { "h": 8, "w": 24, "x": 0, "y": 4 },
        "targets": [
          {
            "expr": "iceberg_compaction_job_duration_seconds",
            "legendFormat": "{{ table }} - {{ compaction_type }}"
          }
        ]
      },
      {
        "id": 4,
        "title": "Files Rewritten by Compaction",
        "type": "timeseries",
        "gridPos": { "h": 8, "w": 12, "x": 0, "y": 12 },
        "targets": [
          {
            "expr": "rate(iceberg_compaction_files_rewritten_total[1h])",
            "legendFormat": "{{ table }}"
          }
        ]
      },
      {
        "id": 5,
        "title": "Bytes Rewritten by Compaction",
        "type": "timeseries",
        "gridPos": { "h": 8, "w": 12, "x": 12, "y": 12 },
        "targets": [
          {
            "expr": "rate(iceberg_compaction_bytes_rewritten_total[1h])",
            "legendFormat": "{{ table }}"
          }
        ]
      }
    ]
  }
}
```

### Cost Tracking Dashboard

```json
{
  "dashboard": {
    "uid": "iceberg-costs",
    "title": "Iceberg Cost Tracking",
    "panels": [
      {
        "id": 1,
        "title": "Estimated Monthly S3 Storage Cost by Table",
        "description": "Based on $0.023/GB/month for S3 Standard",
        "type": "bargauge",
        "gridPos": { "h": 10, "w": 12, "x": 0, "y": 0 },
        "targets": [
          {
            "expr": "topk(20, (iceberg_table_total_size_bytes / 1073741824) * 0.023)",
            "legendFormat": "{{ namespace }}.{{ table }}"
          }
        ],
        "fieldConfig": { "defaults": { "unit": "currencyUSD" } }
      },
      {
        "id": 2,
        "title": "Total Lakehouse Storage Cost (Monthly)",
        "type": "stat",
        "gridPos": { "h": 4, "w": 12, "x": 12, "y": 0 },
        "targets": [
          {
            "expr": "sum(iceberg_table_total_size_bytes) / 1073741824 * 0.023"
          }
        ],
        "fieldConfig": { "defaults": { "unit": "currencyUSD" } }
      },
      {
        "id": 3,
        "title": "S3 Request Costs (from CloudWatch)",
        "type": "timeseries",
        "gridPos": { "h": 8, "w": 12, "x": 12, "y": 4 },
        "targets": [
          {
            "expr": "sum by (bucket) (rate(aws_s3_requests_total{request_type=\"GET\"}[1h])) * 0.0000004",
            "legendFormat": "GET - {{ bucket }}"
          },
          {
            "expr": "sum by (bucket) (rate(aws_s3_requests_total{request_type=\"PUT\"}[1h])) * 0.000005",
            "legendFormat": "PUT - {{ bucket }}"
          }
        ],
        "fieldConfig": { "defaults": { "unit": "currencyUSD" } }
      },
      {
        "id": 4,
        "title": "Compute Cost by Job Type (Daily)",
        "type": "timeseries",
        "gridPos": { "h": 8, "w": 24, "x": 0, "y": 12 },
        "targets": [
          {
            "expr": "sum by (job_type) (increase(emr_job_cost_dollars_total[24h]))",
            "legendFormat": "{{ job_type }}"
          }
        ],
        "fieldConfig": { "defaults": { "unit": "currencyUSD" } }
      }
    ]
  }
}
```

---

## 6. PagerDuty / OpsGenie Alert Configuration

### AlertManager Configuration

```yaml
# alertmanager.yml
global:
  resolve_timeout: 5m
  pagerduty_url: "https://events.pagerduty.com/v2/enqueue"
  opsgenie_api_url: "https://api.opsgenie.com/"

route:
  receiver: "default-slack"
  group_by: ["alertname", "namespace", "table"]
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 4h
  routes:
    - match:
        severity: critical
      receiver: "pagerduty-critical"
      repeat_interval: 1h
    - match:
        severity: warning
      receiver: "opsgenie-warning"
      repeat_interval: 4h
    - match:
        severity: info
      receiver: "slack-info"
      repeat_interval: 24h

receivers:
  - name: "pagerduty-critical"
    pagerduty_configs:
      - routing_key: "<PD_ROUTING_KEY>"
        severity: critical
        description: "{{ .CommonAnnotations.summary }}"
        details:
          namespace: "{{ .CommonLabels.namespace }}"
          table: "{{ .CommonLabels.table }}"
          runbook: "{{ .CommonAnnotations.runbook_url }}"
        links:
          - href: "{{ .CommonAnnotations.runbook_url }}"
            text: "Runbook"
          - href: "https://grafana.internal/d/iceberg-table-health"
            text: "Dashboard"

  - name: "opsgenie-warning"
    opsgenie_configs:
      - api_key: "<OPSGENIE_API_KEY>"
        message: "{{ .CommonAnnotations.summary }}"
        priority: "P3"
        tags: "iceberg,data-platform,{{ .CommonLabels.namespace }}"
        description: |
          {{ .CommonAnnotations.description }}

          Runbook: {{ .CommonAnnotations.runbook_url }}
          Dashboard: https://grafana.internal/d/iceberg-table-health
        responders:
          - type: "team"
            name: "data-platform"

  - name: "slack-info"
    slack_configs:
      - api_url: "<SLACK_WEBHOOK_URL>"
        channel: "#data-platform-alerts"
        title: "{{ .CommonAnnotations.summary }}"
        text: "{{ .CommonAnnotations.description }}"
        send_resolved: true

  - name: "default-slack"
    slack_configs:
      - api_url: "<SLACK_WEBHOOK_URL>"
        channel: "#data-platform-alerts"

inhibit_rules:
  - source_match:
      severity: "critical"
    target_match:
      severity: "warning"
    equal: ["alertname", "namespace", "table"]
```

### OpsGenie Alert Policy (Terraform)

```hcl
resource "opsgenie_alert_policy" "iceberg_critical" {
  name    = "Iceberg Critical Alerts"
  enabled = true

  filter {
    type = "match-all-conditions"
    conditions {
      field          = "tags"
      operation      = "contains"
      expected_value = "iceberg"
    }
    conditions {
      field          = "priority"
      operation      = "equals"
      expected_value = "P1"
    }
  }

  time_restriction {
    type = "weekday-and-time-of-day"
    restrictions {
      start_hour = 0
      start_min  = 0
      end_hour   = 23
      end_min    = 59
      start_day  = "monday"
      end_day    = "sunday"
    }
  }

  message    = "{{message}}"
  priority   = "P1"
  continue_policy = false

  tags = ["iceberg", "critical", "auto-escalate"]
}
```

---

## 7. Data Quality Monitoring

### Freshness SLA Checks

```python
"""
Data freshness SLA monitor.
Checks that tables meet their committed freshness SLAs.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict
import time

class FreshnessTier(Enum):
    REAL_TIME = 300        # 5 minutes
    NEAR_REAL_TIME = 900   # 15 minutes
    HOURLY = 3600          # 1 hour
    DAILY = 86400          # 24 hours
    WEEKLY = 604800        # 7 days

@dataclass
class TableSLA:
    namespace: str
    table: str
    freshness_tier: FreshnessTier
    owner_team: str
    escalation_channel: str

# SLA Registry
TABLE_SLAS: Dict[str, TableSLA] = {
    "raw.clickstream": TableSLA(
        "raw", "clickstream", FreshnessTier.NEAR_REAL_TIME,
        "ingestion-team", "#ingestion-oncall"
    ),
    "curated.user_sessions": TableSLA(
        "curated", "user_sessions", FreshnessTier.HOURLY,
        "data-engineering", "#de-oncall"
    ),
    "analytics.daily_revenue": TableSLA(
        "analytics", "daily_revenue", FreshnessTier.DAILY,
        "analytics-eng", "#analytics-oncall"
    ),
    "ml_features.user_embeddings": TableSLA(
        "ml_features", "user_embeddings", FreshnessTier.DAILY,
        "ml-platform", "#ml-oncall"
    ),
}


def check_freshness_sla(table_key: str, last_commit_ts: float) -> dict:
    """Check if a table meets its freshness SLA."""
    sla = TABLE_SLAS.get(table_key)
    if not sla:
        return {"status": "unknown", "message": "No SLA defined"}

    age_seconds = time.time() - last_commit_ts
    threshold = sla.freshness_tier.value

    if age_seconds <= threshold:
        return {
            "status": "healthy",
            "age_seconds": age_seconds,
            "threshold_seconds": threshold,
            "margin_seconds": threshold - age_seconds,
        }
    else:
        return {
            "status": "breached",
            "age_seconds": age_seconds,
            "threshold_seconds": threshold,
            "breach_seconds": age_seconds - threshold,
            "owner": sla.owner_team,
            "escalation": sla.escalation_channel,
        }
```

### Completeness Checks

```python
"""
Data completeness checker.
Validates that expected data arrived for each time window.
"""

from pyiceberg.catalog import load_catalog
from pyiceberg.expressions import GreaterThanOrEqual, LessThan, And


def check_hourly_completeness(
    catalog, namespace: str, table_name: str, 
    partition_field: str, expected_hour: str
) -> dict:
    """
    Check that data exists for an expected hourly partition.
    expected_hour format: "2024-01-15-14" (YYYY-MM-DD-HH)
    """
    table = catalog.load_table(f"{namespace}.{table_name}")
    scan = table.scan(
        row_filter=And(
            GreaterThanOrEqual(partition_field, f"{expected_hour}:00:00"),
            LessThan(partition_field, f"{expected_hour}:59:59"),
        ),
    )
    
    # Count records in the partition
    record_count = sum(1 for _ in scan.to_arrow().to_batches())
    
    return {
        "table": f"{namespace}.{table_name}",
        "partition": expected_hour,
        "has_data": record_count > 0,
        "record_count": record_count,
    }


def check_record_count_anomaly(
    current_count: int, historical_avg: float, threshold_pct: float = 0.5
) -> dict:
    """Detect anomalous drops in record counts."""
    if historical_avg == 0:
        return {"status": "no_baseline"}
    
    ratio = current_count / historical_avg
    if ratio < threshold_pct:
        return {
            "status": "anomaly",
            "current": current_count,
            "expected_avg": historical_avg,
            "ratio": ratio,
            "message": f"Record count dropped to {ratio:.0%} of average",
        }
    return {"status": "healthy", "ratio": ratio}
```

### Schema Drift Detection

```python
"""
Schema drift detector.
Compares current schema against a registered contract.
"""

from pyiceberg.catalog import load_catalog
from pyiceberg.schema import Schema
from typing import List, Dict


def detect_schema_drift(
    catalog, namespace: str, table_name: str,
    expected_schema: Dict[str, str]
) -> List[dict]:
    """
    Compare table's current schema against expected contract.
    expected_schema: {"column_name": "type_string", ...}
    Returns list of drift events.
    """
    table = catalog.load_table(f"{namespace}.{table_name}")
    current_schema = table.schema()
    
    drifts = []
    current_fields = {field.name: str(field.field_type) for field in current_schema.fields}
    
    # Check for removed columns
    for col, expected_type in expected_schema.items():
        if col not in current_fields:
            drifts.append({
                "type": "column_removed",
                "column": col,
                "expected_type": expected_type,
            })
        elif current_fields[col] != expected_type:
            drifts.append({
                "type": "type_changed",
                "column": col,
                "expected_type": expected_type,
                "actual_type": current_fields[col],
            })
    
    # Check for new columns (informational)
    for col, actual_type in current_fields.items():
        if col not in expected_schema:
            drifts.append({
                "type": "column_added",
                "column": col,
                "actual_type": actual_type,
            })
    
    return drifts
```

---

## 8. Pipeline Monitoring

### Airflow DAG Metrics

```python
"""
Custom Airflow metrics for Iceberg pipeline monitoring.
Add to airflow plugins directory.
"""

from airflow.plugins_manager import AirflowPlugin
from airflow.listeners import hookimpl
from prometheus_client import Counter, Histogram, Gauge
import time

DAG_SUCCESS = Counter(
    "airflow_dag_success_total",
    "Total successful DAG runs",
    ["dag_id"],
)
DAG_FAILURE = Counter(
    "airflow_dag_failure_total",
    "Total failed DAG runs",
    ["dag_id"],
)
DAG_DURATION = Histogram(
    "airflow_dag_duration_seconds",
    "DAG run duration",
    ["dag_id"],
    buckets=[60, 300, 600, 1800, 3600, 7200, 14400],
)
TASK_PROCESSING_LAG = Gauge(
    "airflow_task_processing_lag_seconds",
    "Time between scheduled and actual execution",
    ["dag_id", "task_id"],
)


@hookimpl
def on_dag_run_success(dag_run, msg):
    DAG_SUCCESS.labels(dag_id=dag_run.dag_id).inc()
    duration = (dag_run.end_date - dag_run.start_date).total_seconds()
    DAG_DURATION.labels(dag_id=dag_run.dag_id).observe(duration)


@hookimpl
def on_dag_run_failed(dag_run, msg):
    DAG_FAILURE.labels(dag_id=dag_run.dag_id).inc()
```

### Flink Pipeline Metrics

```yaml
# Prometheus rules for Flink Iceberg sink monitoring
groups:
  - name: flink_iceberg_pipeline
    rules:
      - alert: FlinkCheckpointFailing
        expr: increase(flink_jobmanager_job_lastCheckpointFailed[10m]) > 3
        labels:
          severity: critical
        annotations:
          summary: "Flink job {{ $labels.job_name }} checkpoints failing"

      - alert: FlinkBackpressureHigh
        expr: flink_taskmanager_job_task_backPressuredTimeMsPerSecond > 500
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Flink task {{ $labels.task_name }} backpressured >50%"

      - alert: FlinkConsumerLagHigh
        expr: flink_taskmanager_job_task_operator_KafkaSourceReader_KafkaConsumer_records_lag_max > 100000
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Kafka consumer lag is {{ $value }} records"

      - alert: FlinkIcebergCommitFailed
        expr: increase(flink_taskmanager_job_task_operator_IcebergStreamWriter_commitFailures[5m]) > 0
        labels:
          severity: critical
        annotations:
          summary: "Iceberg commits failing in Flink job {{ $labels.job_name }}"
```

---

## 9. Runbook Examples

### Runbook: Iceberg Snapshot Growth

```markdown
# Runbook: Iceberg Snapshot Growth

**Alert:** IcebergSnapshotCountHigh / IcebergSnapshotCountCritical
**Severity:** Warning (>1000) / Critical (>5000)
**Owner:** data-platform team

## Impact
- Metadata file size grows linearly with snapshot count
- Query planning time increases
- Catalog operations slow down
- Eventually metadata file exceeds max size limits

## Diagnosis

1. Check if snapshot expiration job is running:
   ```bash
   # Airflow
   airflow dags list-runs -d iceberg_maintenance --state running
   
   # Check last successful run
   airflow dags list-runs -d iceberg_maintenance --state success -l 5
   ```

2. Check snapshot expiration configuration:
   ```sql
   -- In Spark SQL
   DESCRIBE EXTENDED <namespace>.<table>;
   -- Look for: history.expire.max-snapshot-age-ms
   ```

3. Check if expire_snapshots is actually removing snapshots:
   ```python
   from pyiceberg.catalog import load_catalog
   catalog = load_catalog("glue")
   table = catalog.load_table("namespace.table")
   print(f"Snapshot count: {len(table.metadata.snapshots)}")
   print(f"Oldest: {table.metadata.snapshots[0].timestamp_ms}")
   ```

## Resolution

1. **Run manual snapshot expiration:**
   ```sql
   CALL system.expire_snapshots(
     table => 'namespace.table',
     older_than => TIMESTAMP '2024-01-01 00:00:00',
     retain_last => 100
   );
   ```

2. **If expiration job was disabled, re-enable:**
   ```bash
   airflow dags unpause iceberg_maintenance
   ```

3. **Set proper retention in table properties:**
   ```sql
   ALTER TABLE namespace.table SET TBLPROPERTIES (
     'history.expire.max-snapshot-age-ms' = '432000000',  -- 5 days
     'history.expire.min-snapshots-to-keep' = '50'
   );
   ```

## Prevention
- Ensure maintenance DAG runs on schedule (every 6h recommended)
- Set table-level retention policies at creation time
- Monitor this metric with warning threshold at 500
```

### Runbook: Data Freshness Breach

```markdown
# Runbook: Data Freshness SLA Breach

**Alert:** IcebergDataStale / IcebergDataStaleCritical
**Severity:** Warning (>1h) / Critical (>4h)

## Triage Steps

1. **Identify the upstream pipeline:**
   ```bash
   # Check which DAG writes to this table
   grep -r "table_name" airflow/dags/ 
   ```

2. **Check DAG status:**
   ```bash
   airflow dags list-runs -d <dag_id> --state failed -l 5
   airflow tasks failed-deps <dag_id> <task_id> <execution_date>
   ```

3. **Check for upstream source issues:**
   - Kafka: Check consumer lag in Grafana
   - S3 landing zone: Check if new files are arriving
   - API sources: Check source system health

4. **Check for Iceberg commit failures:**
   ```bash
   # Check Spark driver logs
   kubectl logs -n spark deployment/spark-driver --tail=500 | grep -i "commit\|conflict\|error"
   ```

5. **Check for resource issues:**
   - EMR/Spark cluster health
   - S3 throttling (503 SlowDown)
   - Glue catalog throttling

## Common Root Causes

| Cause | Fix |
|-------|-----|
| DAG disabled/paused | `airflow dags unpause <dag_id>` |
| Upstream Kafka down | Escalate to streaming team |
| Spark OOM | Increase executor memory, check for data skew |
| S3 throttling | Add request prefix spreading |
| Commit conflicts | Check concurrent writers, adjust retry config |
| Schema mismatch | Check source schema changes |

## Escalation
- After 15min of triage without resolution: page on-call data engineer
- After 1h: escalate to team lead
- SLA breach > 2x threshold: incident commander + stakeholder notification
```

### Runbook: Small Files / Compaction Needed

```markdown
# Runbook: Small Files Accumulation

**Alert:** IcebergSmallFiles / IcebergTooManyFilesPerPartition

## Quick Fix

Run targeted compaction:
```sql
CALL system.rewrite_data_files(
  table => 'namespace.table',
  strategy => 'binpack',
  options => map(
    'target-file-size-bytes', '134217728',   -- 128MB
    'min-file-size-bytes', '67108864',       -- 64MB (50% of target)
    'max-file-size-bytes', '201326592',      -- 192MB (150% of target)
    'partial-progress.enabled', 'true',
    'partial-progress.max-commits', '10'
  )
);
```

## Root Cause Investigation

- Streaming job with too-frequent commits → increase checkpoint interval
- Partition granularity too fine → consider partition evolution
- Frequent small updates → batch updates or use MoR with scheduled compaction

## Prevention
- Schedule automatic compaction every 4-6 hours
- Set write distribution mode: `write.distribution-mode = hash`
- Configure target file size: `write.target-file-size-bytes = 134217728`
```

---

## 10. SLA Definitions and Tracking

### SLA Tiers

```yaml
# sla-definitions.yml
sla_tiers:
  platinum:
    freshness: 5m
    availability: 99.9%
    query_p99_latency: 5s
    data_completeness: 99.99%
    recovery_time_objective: 15m
    tables:
      - raw.clickstream
      - raw.transactions

  gold:
    freshness: 1h
    availability: 99.5%
    query_p99_latency: 30s
    data_completeness: 99.9%
    recovery_time_objective: 1h
    tables:
      - curated.user_sessions
      - curated.order_facts
      - analytics.funnel_metrics

  silver:
    freshness: 24h
    availability: 99.0%
    query_p99_latency: 120s
    data_completeness: 99.0%
    recovery_time_objective: 4h
    tables:
      - analytics.daily_revenue
      - analytics.weekly_cohorts
      - ml_features.user_embeddings

  bronze:
    freshness: 7d
    availability: 95.0%
    query_p99_latency: 300s
    data_completeness: 95.0%
    recovery_time_objective: 24h
    tables:
      - archive.*
      - experimental.*
```

### SLA Tracking Prometheus Rules

```yaml
groups:
  - name: sla_tracking
    rules:
      # SLA compliance recording rules
      - record: iceberg:sla_freshness_compliance:ratio
        expr: |
          (
            iceberg_table_current_snapshot_age_seconds{namespace="raw",table="clickstream"} <= 300
          ) or vector(0)

      - record: iceberg:sla_compliance_daily:ratio
        expr: |
          avg_over_time(
            (iceberg_table_current_snapshot_age_seconds < bool 3600)[24h:5m]
          )

      # Monthly SLA calculation
      - record: iceberg:sla_monthly_uptime:ratio
        expr: |
          avg_over_time(
            (iceberg_table_current_snapshot_age_seconds < bool on(namespace, table) 
              group_left iceberg_table_sla_threshold_seconds
            )[30d:5m]
          )

      # Error budget burn rate
      - alert: SLAErrorBudgetBurning
        expr: |
          (1 - iceberg:sla_compliance_daily:ratio) > 0.1
        for: 30m
        labels:
          severity: critical
        annotations:
          summary: "SLA error budget burning fast for {{ $labels.namespace }}.{{ $labels.table }}"
          description: "Daily compliance is {{ $value | humanizePercentage }}. Error budget will exhaust."
```

---

## 11. Cost Monitoring

### S3 Cost Calculator

```python
"""
S3 cost estimator per Iceberg table using CloudWatch metrics and Iceberg metadata.
"""

# AWS S3 Pricing (us-east-1, as of 2024)
S3_STORAGE_PER_GB_MONTH = 0.023        # Standard
S3_STORAGE_IA_PER_GB_MONTH = 0.0125    # Infrequent Access
S3_GET_PER_1000 = 0.0004               # GET, SELECT
S3_PUT_PER_1000 = 0.005                # PUT, COPY, POST, LIST
S3_LIFECYCLE_TRANSITION_PER_1000 = 0.01


def estimate_table_monthly_cost(
    total_size_bytes: int,
    monthly_get_requests: int,
    monthly_put_requests: int,
    monthly_list_requests: int,
    storage_class: str = "STANDARD",
) -> dict:
    """Estimate monthly S3 costs for an Iceberg table."""
    size_gb = total_size_bytes / (1024**3)

    storage_rate = (
        S3_STORAGE_PER_GB_MONTH if storage_class == "STANDARD"
        else S3_STORAGE_IA_PER_GB_MONTH
    )
    storage_cost = size_gb * storage_rate
    get_cost = (monthly_get_requests / 1000) * S3_GET_PER_1000
    put_cost = (monthly_put_requests / 1000) * S3_PUT_PER_1000
    list_cost = (monthly_list_requests / 1000) * S3_PUT_PER_1000  # LIST = same as PUT pricing

    total = storage_cost + get_cost + put_cost + list_cost

    return {
        "storage_cost": round(storage_cost, 2),
        "get_request_cost": round(get_cost, 2),
        "put_request_cost": round(put_cost, 2),
        "list_request_cost": round(list_cost, 2),
        "total_monthly_cost": round(total, 2),
        "size_gb": round(size_gb, 2),
    }
```

### Cost Alert Rules

```yaml
groups:
  - name: cost_alerts
    rules:
      - alert: TableStorageCostAnomaly
        expr: |
          (iceberg_table_total_size_bytes / 1073741824 * 0.023) 
          > 1.5 * avg_over_time((iceberg_table_total_size_bytes / 1073741824 * 0.023)[7d:1h])
        for: 1h
        labels:
          severity: warning
        annotations:
          summary: "Storage cost anomaly for {{ $labels.namespace }}.{{ $labels.table }}"
          description: "Current estimated cost ${{ $value }}/month, 50% above 7-day average"

      - alert: OrphanFileCostWaste
        expr: iceberg_orphan_files_size_bytes / 1073741824 * 0.023 > 10
        for: 24h
        labels:
          severity: warning
        annotations:
          summary: "Orphan files costing >$10/month for {{ $labels.namespace }}.{{ $labels.table }}"
```

---

## 12. Log Aggregation Strategy

### ELK Stack Configuration

```yaml
# filebeat.yml - Ship Spark/Flink/Airflow logs
filebeat.inputs:
  - type: container
    paths:
      - /var/log/containers/spark-*.log
      - /var/log/containers/flink-*.log
      - /var/log/containers/airflow-*.log
    processors:
      - add_kubernetes_metadata: ~
      - dissect:
          tokenizer: "%{timestamp} %{level} %{logger} - %{message}"
          field: "message"

  - type: log
    paths:
      - /var/log/iceberg-exporter/*.log
    fields:
      service: iceberg-exporter

output.elasticsearch:
  hosts: ["elasticsearch:9200"]
  indices:
    - index: "iceberg-pipelines-%{+yyyy.MM.dd}"
      when.contains:
        fields.service: "iceberg"
    - index: "spark-jobs-%{+yyyy.MM.dd}"
      when.contains:
        kubernetes.container.name: "spark"
    - index: "flink-jobs-%{+yyyy.MM.dd}"
      when.contains:
        kubernetes.container.name: "flink"
```

### CloudWatch Log Insights Queries

```
# Find Iceberg commit failures
fields @timestamp, @message
| filter @message like /CommitFailedException|commit.*failed|conflict/
| sort @timestamp desc
| limit 50

# Track S3 throttling
fields @timestamp, @message
| filter @message like /503|SlowDown|throttl/
| stats count() as throttle_count by bin(5m)

# Query latency analysis
fields @timestamp, duration_ms, table_name, query_type
| filter service = "trino" and table_name like /iceberg/
| stats avg(duration_ms) as avg_ms, p99(duration_ms) as p99_ms by table_name, bin(1h)
| sort p99_ms desc
```

### Structured Logging Standard

```python
"""
Standard structured logging for all Iceberg pipeline components.
"""
import structlog
import logging

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    logger_factory=structlog.stdlib.LoggerFactory(),
)

logger = structlog.get_logger()

# Usage in pipeline code:
logger.info(
    "iceberg_commit_success",
    table="raw.clickstream",
    snapshot_id=12345,
    added_files=42,
    added_records=1_500_000,
    commit_duration_ms=234,
    partition="2024-01-15",
)

logger.warning(
    "iceberg_commit_retry",
    table="raw.clickstream",
    attempt=2,
    conflict_reason="concurrent_append",
    retry_delay_ms=500,
)

logger.error(
    "iceberg_commit_failed",
    table="raw.clickstream",
    error_type="CommitFailedException",
    attempts_exhausted=4,
    error_message="Cannot commit: found conflicting files",
)
```

---

## 13. End-to-End Observability Checklist

| Layer | Tool | Metrics |
|-------|------|---------|
| Source (Kafka) | Prometheus + Burrow | Consumer lag, throughput, partition count |
| Ingestion (Flink/Spark) | JMX Exporter | Checkpoint duration, backpressure, records/sec |
| Storage (S3) | CloudWatch Exporter | Request count, latency, errors, bytes transferred |
| Catalog (Glue/HMS) | Custom exporter | API latency, throttling, error rate |
| Table Health | Iceberg exporter | All metrics from Section 1 |
| Query Engine (Trino) | JMX Exporter | Query latency, queue depth, memory usage |
| Orchestration (Airflow) | StatsD exporter | DAG duration, task failures, pool utilization |
| Cost | Custom + CUR | Storage, compute, requests by table |
| Data Quality | Great Expectations / custom | Freshness, completeness, schema, anomalies |

### Correlation IDs

Propagate trace IDs through the entire pipeline to correlate logs across systems:

```python
import uuid

# Generate at source
correlation_id = str(uuid.uuid4())

# Propagate through Kafka headers
producer.send(
    topic="events",
    value=payload,
    headers=[("X-Correlation-ID", correlation_id.encode())],
)

# Include in Iceberg commit properties
table.append(df, snapshot_properties={"correlation-id": correlation_id})

# Include in all log lines
logger.info("processing_complete", correlation_id=correlation_id, records=count)
```

---

## 14. Monitoring Infrastructure as Code (Terraform)

```hcl
# monitoring-stack.tf

module "prometheus" {
  source  = "terraform-aws-modules/managed-service-prometheus/aws"
  version = "~> 2.0"

  workspace_alias = "iceberg-monitoring"

  alert_manager_definition = file("${path.module}/alertmanager.yml")

  rule_group_namespaces = {
    iceberg_health = {
      name = "iceberg-health"
      data = file("${path.module}/iceberg-alerts.yml")
    }
    pipeline_health = {
      name = "pipeline-health"
      data = file("${path.module}/pipeline-alerts.yml")
    }
    cost_alerts = {
      name = "cost-alerts"
      data = file("${path.module}/cost-alerts.yml")
    }
  }
}

module "grafana" {
  source  = "terraform-aws-modules/managed-service-grafana/aws"
  version = "~> 2.0"

  name                      = "iceberg-dashboards"
  associate_license         = false
  account_access_type       = "CURRENT_ACCOUNT"
  authentication_providers  = ["AWS_SSO"]
  permission_type           = "SERVICE_MANAGED"

  data_sources = ["PROMETHEUS", "CLOUDWATCH"]

  role_associations = {
    ADMIN = {
      group_ids = [var.admin_group_id]
    }
    VIEWER = {
      group_ids = [var.viewer_group_id]
    }
  }
}

resource "aws_cloudwatch_metric_alarm" "s3_throttling" {
  alarm_name          = "iceberg-s3-throttling"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "5xxErrors"
  namespace           = "AWS/S3"
  period              = 300
  statistic           = "Sum"
  threshold           = 100
  alarm_description   = "S3 returning 5xx errors (likely throttling)"

  dimensions = {
    BucketName = var.lakehouse_bucket
    FilterId   = "AllMetrics"
  }

  alarm_actions = [var.sns_topic_arn]
  ok_actions    = [var.sns_topic_arn]
}
```

---

## Summary

A production Iceberg monitoring stack requires coverage at every layer:

1. **Table metadata health** - Custom Prometheus exporter reading Iceberg catalog
2. **Engine metrics** - JMX exporters on Spark, Flink, Trino
3. **Infrastructure** - CloudWatch for S3, Glue, EMR
4. **Alerting** - Tiered severity with PagerDuty/OpsGenie routing
5. **Dashboards** - Grafana with table health, compaction, and cost views
6. **Data quality** - Freshness SLAs, completeness, schema drift
7. **Cost tracking** - Per-table storage and request cost attribution
8. **Runbooks** - Actionable remediation steps for every alert
9. **Log aggregation** - Structured logging with correlation IDs
10. **SLA tracking** - Error budgets and monthly compliance reporting

The key principle: **every alert must have a runbook, and every metric must inform a decision**.
