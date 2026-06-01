# CDC Replication Lag Monitoring

## Problem Statement

Change Data Capture (CDC) pipelines replicate operational databases to data lakes and warehouses, enabling analytics without impacting production systems. At scale — 10K+ tables, 500K+ changes/second — monitoring becomes critical:

- **Replication lag** means analysts see stale data, leading to wrong decisions
- **Schema drift** causes silent pipeline failures or data corruption
- **Consistency gaps** mean source and target diverge without anyone knowing
- **Replication slot bloat** can crash production PostgreSQL instances

Companies operating CDC at massive scale:
- **Uber**: 10K+ tables replicated via Debezium across multiple data centers
- **Netflix**: Real-time CDC feeds powering recommendation pipelines
- **LinkedIn**: Databus/Brooklin replicating petabytes daily
- **Shopify**: CDC-based event sourcing for commerce analytics

Without comprehensive monitoring, CDC becomes a ticking time bomb — working fine until it catastrophically fails.

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        CDC REPLICATION PIPELINE                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  SOURCE DATABASES              CAPTURE LAYER           TRANSPORT            │
│  ┌──────────────┐            ┌──────────────┐       ┌──────────────┐       │
│  │ PostgreSQL   │──WAL──────▶│  Debezium    │──────▶│    Kafka     │       │
│  │ (slots)      │            │  Connector   │       │   Cluster    │       │
│  └──────────────┘            └──────────────┘       └──────┬───────┘       │
│  ┌──────────────┐            ┌──────────────┐              │               │
│  │   MySQL      │──binlog──▶│   Maxwell/   │──────▶       │               │
│  │ (GTID)      │            │   Debezium   │              │               │
│  └──────────────┘            └──────────────┘              │               │
│  ┌──────────────┐            ┌──────────────┐              │               │
│  │  MongoDB     │──oplog───▶│  Debezium    │──────▶       │               │
│  │ (change str) │            │  Connector   │              │               │
│  └──────────────┘            └──────────────┘              │               │
│                                                            ▼               │
│  SINK LAYER                   TARGET STORAGE                               │
│  ┌──────────────┐            ┌──────────────┐                              │
│  │ S3 Sink      │◀───────────│              │                              │
│  │ Connector    │            │    Kafka     │                              │
│  └──────┬───────┘            │   Consumer   │                              │
│         │                    │    Groups    │                              │
│  ┌──────▼───────┐            │              │                              │
│  │  Snowflake   │◀───────────│              │                              │
│  │  Sink        │            └──────────────┘                              │
│  └──────┬───────┘                                                          │
│         │                                                                  │
│  ┌──────▼───────┐                                                          │
│  │  ClickHouse  │                                                          │
│  │  Target      │                                                          │
│  └──────────────┘                                                          │
│                                                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│  WHERE LAG ACCUMULATES:                                                     │
│                                                                             │
│  [L1: Source]     [L2: Capture]    [L3: Kafka]     [L4: Sink]              │
│   WAL/binlog       Debezium         Consumer        Write to               │
│   read delay       processing       group lag       target delay            │
│                                                                             │
│  Total E2E Lag = L1 + L2 + L3 + L4                                        │
└─────────────────────────────────────────────────────────────────────────────┘
```

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    MONITORING OVERLAY                                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────┐    ┌──────────────┐    ┌─────────────┐    ┌───────────┐      │
│  │ JMX     │───▶│  Prometheus  │───▶│   Grafana   │───▶│  Alerts   │      │
│  │ Exporter│    │              │    │  Dashboards │    │ PagerDuty │      │
│  └─────────┘    └──────────────┘    └─────────────┘    └───────────┘      │
│                                                                             │
│  ┌─────────┐    ┌──────────────┐    ┌─────────────┐                       │
│  │ Schema  │───▶│  Drift       │───▶│  Slack      │                       │
│  │ Registry│    │  Detector    │    │  Alerts     │                       │
│  └─────────┘    └──────────────┘    └─────────────┘                       │
│                                                                             │
│  ┌─────────┐    ┌──────────────┐    ┌─────────────┐                       │
│  │ Recon   │───▶│  Consistency │───▶│  Dashboard  │                       │
│  │ Jobs    │    │  Reports     │    │  + Alerts   │                       │
│  └─────────┘    └──────────────┘    └─────────────┘                       │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Lag Monitoring Dimensions

### 1. Source Capture Lag (L1)

The delay between a transaction committing in the source database and the CDC connector reading it.

**PostgreSQL**: Measured via replication slot lag
```sql
-- PostgreSQL: Check replication slot lag
SELECT
    slot_name,
    pg_size_pretty(pg_wal_lsn_diff(pg_current_wal_lsn(), confirmed_flush_lsn)) AS lag_bytes,
    pg_wal_lsn_diff(pg_current_wal_lsn(), confirmed_flush_lsn) AS lag_bytes_raw,
    active
FROM pg_replication_slots
WHERE slot_type = 'logical';
```

**MySQL**: Measured via binlog position delta
```sql
-- MySQL: Check binlog position
SHOW MASTER STATUS;
-- Compare with connector's last read position
SHOW SLAVE STATUS\G  -- seconds_behind_master equivalent
```

### 2. Kafka Transit Lag (L2 + L3)

Time from Debezium producing a record to the sink connector consuming it.

```
Consumer Group Lag = Latest Offset - Committed Offset (per partition)
```

### 3. Sink Write Lag (L4)

Time from consuming a Kafka record to it being queryable in the target system.

- **S3**: Time to flush Parquet file + manifest update
- **Snowflake**: Time to COPY INTO + metadata refresh
- **ClickHouse**: Time to insert + merge

### 4. End-to-End Replication Lag

The only metric that truly matters from a business perspective:

```
E2E Lag = Time(record queryable in target) - Time(record committed in source)
```

### 5. Per-Table Lag Tracking

Not all tables are equal. Classification:

| Tier | Tables | Max Lag | Example |
|------|--------|---------|---------|
| P0 - Critical | 50 | < 30s | orders, payments |
| P1 - Important | 200 | < 5min | users, inventory |
| P2 - Standard | 2000 | < 30min | logs, events |
| P3 - Cold | 8000 | < 4hr | archives, configs |

### 6. Replication Slot/Binlog Position Monitoring

**Critical for PostgreSQL**: Replication slots prevent WAL cleanup. If a connector is down, WAL files accumulate and can fill the disk, crashing the database.

```
WAL Growth Rate = current_wal_lsn - slot_confirmed_lsn (over time)
Disk Exhaustion ETA = available_disk / wal_growth_rate
```

---

## Schema Drift Detection

### DDL Event Capture

Debezium captures DDL events. Configure it to emit schema change events:

```json
{
  "connector.class": "io.debezium.connector.postgresql.PostgresConnector",
  "schema.history.internal.kafka.topic": "schema-changes.inventory",
  "include.schema.changes": "true",
  "schema.history.internal.store.only.captured.tables.ddl": "true"
}
```

### Schema Registry Compatibility

```
┌────────────────────────────────────────────────────┐
│          SCHEMA COMPATIBILITY MATRIX                │
├────────────────────────────────────────────────────┤
│                                                    │
│  BACKWARD  ──▶ New schema can read old data       │
│                (safe for consumers)                │
│                                                    │
│  FORWARD   ──▶ Old schema can read new data       │
│                (safe for producers)                │
│                                                    │
│  FULL      ──▶ Both backward and forward          │
│                (safest, most restrictive)          │
│                                                    │
│  BREAKING  ──▶ Requires coordinated migration     │
│                (rename, type change, drop column)  │
└────────────────────────────────────────────────────┘
```

### Breaking Change Detection Rules

| Change Type | Impact | Detection |
|-------------|--------|-----------|
| Column added (nullable) | Safe | Auto-evolve |
| Column added (non-null) | Breaking | Block + alert |
| Column dropped | Breaking (for consumers) | Alert |
| Column renamed | Breaking | Block + alert |
| Type widening (int→bigint) | Usually safe | Validate |
| Type narrowing (bigint→int) | Breaking | Block + alert |
| Table dropped | Critical | Emergency alert |

---

## Consistency Verification

### Row Count Reconciliation

```
┌───────────────────────────────────────────────────────────────┐
│                 RECONCILIATION FLOW                             │
├───────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────┐    ┌───────────────┐    ┌──────────────┐       │
│  │  Source   │    │  Reconciler   │    │   Target     │       │
│  │  DB       │    │  (Spark Job)  │    │   (Lake)     │       │
│  └────┬─────┘    └───────┬───────┘    └──────┬───────┘       │
│       │                  │                    │               │
│       │  COUNT(*)        │                    │               │
│       │◀─────────────────│                    │               │
│       │──────────────────▶                    │               │
│       │                  │   COUNT(*)         │               │
│       │                  │───────────────────▶│               │
│       │                  │◀───────────────────│               │
│       │                  │                    │               │
│       │                  │  Compare & Alert   │               │
│       │                  │  if drift > 0.01%  │               │
│       │                  │                    │               │
└───────┴──────────────────┴────────────────────┴───────────────┘
```

### Verification Strategies

| Method | Overhead | Accuracy | Frequency |
|--------|----------|----------|-----------|
| Row count | Low | Medium | Every 15 min |
| Checksum (CRC32) | Medium | High | Hourly |
| Full row comparison | Very High | Perfect | Daily (sampled) |
| Watermark canary | Minimal | For lag only | Continuous |

---

## Production Code Examples

### 1. Debezium Metrics Exporter for Prometheus

```python
#!/usr/bin/env python3
"""
Debezium JMX metrics exporter for Prometheus.
Exposes CDC-specific lag and throughput metrics.
"""

import time
import json
import requests
from prometheus_client import start_http_server, Gauge, Counter, Histogram
from typing import Dict, Any

# Metrics
SOURCE_LAG_MS = Gauge(
    'cdc_source_lag_milliseconds',
    'Lag between source DB commit and Debezium capture',
    ['connector', 'database', 'table']
)

KAFKA_LAG_RECORDS = Gauge(
    'cdc_kafka_consumer_lag_records',
    'Consumer group lag in number of records',
    ['connector', 'topic', 'partition']
)

E2E_LAG_MS = Gauge(
    'cdc_end_to_end_lag_milliseconds',
    'End-to-end replication lag from source to target',
    ['connector', 'database', 'table']
)

EVENTS_PROCESSED = Counter(
    'cdc_events_processed_total',
    'Total CDC events processed',
    ['connector', 'database', 'table', 'operation']
)

SNAPSHOT_PROGRESS = Gauge(
    'cdc_snapshot_progress_ratio',
    'Snapshot completion progress (0-1)',
    ['connector', 'database']
)

REPLICATION_SLOT_LAG_BYTES = Gauge(
    'cdc_replication_slot_lag_bytes',
    'PostgreSQL replication slot lag in bytes',
    ['slot_name', 'database']
)

SCHEMA_CHANGES_TOTAL = Counter(
    'cdc_schema_changes_total',
    'Total schema changes detected',
    ['connector', 'database', 'change_type']
)


class DebeziumMetricsCollector:
    """Collects metrics from Debezium via Kafka Connect REST API and JMX."""

    def __init__(self, connect_url: str, pg_conn_string: str = None):
        self.connect_url = connect_url
        self.pg_conn_string = pg_conn_string

    def collect_connector_metrics(self):
        """Fetch metrics from all running connectors."""
        connectors = requests.get(f"{self.connect_url}/connectors").json()

        for connector in connectors:
            status = requests.get(
                f"{self.connect_url}/connectors/{connector}/status"
            ).json()

            # Fetch task-level metrics
            for task in status.get('tasks', []):
                if task['state'] == 'RUNNING':
                    self._collect_task_metrics(connector, task['id'])

    def _collect_task_metrics(self, connector: str, task_id: int):
        """Collect metrics for a specific connector task."""
        # Fetch JMX metrics via Jolokia (if configured)
        jolokia_url = f"{self.connect_url}/jolokia"

        # Source connector metrics
        metrics_beans = [
            f"debezium.{connector}:type=connector-metrics,context=streaming,server={connector}",
        ]

        for bean in metrics_beans:
            try:
                resp = requests.post(jolokia_url, json={
                    "type": "read",
                    "mbean": bean
                })
                data = resp.json().get('value', {})

                if 'MilliSecondsBehindSource' in data:
                    SOURCE_LAG_MS.labels(
                        connector=connector,
                        database=data.get('DatabaseName', 'unknown'),
                        table='all'
                    ).set(data['MilliSecondsBehindSource'])

                if 'TotalNumberOfEventsSeen' in data:
                    # Track throughput via events seen
                    pass

            except Exception as e:
                print(f"Error collecting metrics for {connector}: {e}")

    def collect_replication_slot_metrics(self):
        """Monitor PostgreSQL replication slot growth."""
        if not self.pg_conn_string:
            return

        import psycopg2
        conn = psycopg2.connect(self.pg_conn_string)
        cur = conn.cursor()

        cur.execute("""
            SELECT
                slot_name,
                database,
                pg_wal_lsn_diff(pg_current_wal_lsn(), confirmed_flush_lsn) AS lag_bytes,
                active
            FROM pg_replication_slots
            WHERE slot_type = 'logical'
        """)

        for row in cur.fetchall():
            slot_name, database, lag_bytes, active = row
            REPLICATION_SLOT_LAG_BYTES.labels(
                slot_name=slot_name,
                database=database
            ).set(lag_bytes or 0)

        cur.close()
        conn.close()


def main():
    collector = DebeziumMetricsCollector(
        connect_url="http://kafka-connect:8083",
        pg_conn_string="host=postgres dbname=app user=monitor"
    )

    start_http_server(9090)
    print("Debezium metrics exporter started on :9090")

    while True:
        try:
            collector.collect_connector_metrics()
            collector.collect_replication_slot_metrics()
        except Exception as e:
            print(f"Collection cycle error: {e}")
        time.sleep(15)


if __name__ == "__main__":
    main()
```

### 2. Custom Lag Calculator

```python
#!/usr/bin/env python3
"""
CDC Lag Calculator - Computes precise end-to-end replication lag
by comparing source WAL/binlog position with committed Kafka offsets
and target table freshness.
"""

import time
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional
from confluent_kafka.admin import AdminClient, ConsumerGroupTopicPartitions
from confluent_kafka import TopicPartition
import psycopg2
import snowflake.connector


@dataclass
class TableLagMetrics:
    table: str
    source_latest_ts: Optional[datetime] = None
    kafka_latest_ts: Optional[datetime] = None
    target_latest_ts: Optional[datetime] = None
    source_lag_ms: float = 0
    kafka_lag_ms: float = 0
    sink_lag_ms: float = 0
    e2e_lag_ms: float = 0
    kafka_offset_lag: int = 0
    tier: str = "P2"


class CDCLagCalculator:
    """Calculates multi-dimensional lag for CDC pipelines."""

    def __init__(self, config: Dict):
        self.config = config
        self.kafka_admin = AdminClient({
            'bootstrap.servers': config['kafka_brokers']
        })

    def calculate_kafka_consumer_lag(self, group_id: str, topics: List[str]) -> Dict[str, int]:
        """Calculate consumer group lag per topic-partition."""
        lag_by_topic = {}

        # Get committed offsets for the consumer group
        group_partitions = []
        for topic in topics:
            metadata = self.kafka_admin.list_topics(topic=topic)
            for partition_id in metadata.topics[topic].partitions:
                group_partitions.append(TopicPartition(topic, partition_id))

        # Fetch committed offsets
        committed = self.kafka_admin.list_consumer_group_offsets(
            [ConsumerGroupTopicPartitions(group_id, group_partitions)]
        )

        # Fetch latest offsets (high watermarks)
        for tp_result in committed:
            for tp in tp_result.topic_partitions:
                # Get high watermark
                hw = self._get_high_watermark(tp.topic, tp.partition)
                lag = hw - tp.offset if tp.offset >= 0 else hw
                key = f"{tp.topic}-{tp.partition}"
                lag_by_topic[key] = lag

        return lag_by_topic

    def calculate_source_lag(self, tables: List[str]) -> Dict[str, TableLagMetrics]:
        """Calculate lag from source DB perspective."""
        results = {}
        conn = psycopg2.connect(self.config['source_pg_conn'])
        cur = conn.cursor()

        for table in tables:
            # Get latest committed timestamp from source
            cur.execute(f"""
                SELECT MAX(updated_at) as latest_ts
                FROM {table}
                WHERE updated_at > NOW() - INTERVAL '1 hour'
            """)
            row = cur.fetchone()
            source_ts = row[0] if row and row[0] else None

            metrics = TableLagMetrics(table=table, source_latest_ts=source_ts)
            results[table] = metrics

        cur.close()
        conn.close()
        return results

    def calculate_target_freshness(self, tables: List[str]) -> Dict[str, datetime]:
        """Check data freshness in target (Snowflake)."""
        freshness = {}
        conn = snowflake.connector.connect(**self.config['snowflake'])
        cur = conn.cursor()

        for table in tables:
            cur.execute(f"""
                SELECT MAX(_cdc_updated_at) as latest_ts
                FROM raw.cdc.{table}
            """)
            row = cur.fetchone()
            if row and row[0]:
                freshness[table] = row[0]

        cur.close()
        conn.close()
        return freshness

    def compute_e2e_lag(self, tables: List[str]) -> List[TableLagMetrics]:
        """Compute end-to-end lag combining all dimensions."""
        now = datetime.now(timezone.utc)

        source_metrics = self.calculate_source_lag(tables)
        target_freshness = self.calculate_target_freshness(tables)

        results = []
        for table in tables:
            metrics = source_metrics.get(table, TableLagMetrics(table=table))

            target_ts = target_freshness.get(table)
            if metrics.source_latest_ts and target_ts:
                metrics.e2e_lag_ms = (
                    metrics.source_latest_ts - target_ts
                ).total_seconds() * 1000

            # Classify by tier
            metrics.tier = self._classify_table_tier(table)
            results.append(metrics)

        return results

    def _classify_table_tier(self, table: str) -> str:
        """Classify table into monitoring tier."""
        critical_tables = {'orders', 'payments', 'transactions'}
        important_tables = {'users', 'products', 'inventory'}

        base_name = table.split('.')[-1]
        if base_name in critical_tables:
            return "P0"
        elif base_name in important_tables:
            return "P1"
        return "P2"

    def _get_high_watermark(self, topic: str, partition: int) -> int:
        """Get high watermark for a topic-partition."""
        from confluent_kafka import Consumer
        c = Consumer({
            'bootstrap.servers': self.config['kafka_brokers'],
            'group.id': '__lag_checker__'
        })
        tp = TopicPartition(topic, partition)
        lo, hi = c.get_watermark_offsets(tp)
        c.close()
        return hi


# Usage
if __name__ == "__main__":
    config = {
        'kafka_brokers': 'kafka:9092',
        'source_pg_conn': 'host=pg dbname=app user=cdc_monitor',
        'snowflake': {
            'account': 'xy12345',
            'user': 'CDC_MONITOR',
            'password': '...',
            'warehouse': 'MONITORING_WH',
            'database': 'RAW'
        }
    }

    calc = CDCLagCalculator(config)
    tables = ['public.orders', 'public.users', 'public.payments']
    lag_results = calc.compute_e2e_lag(tables)

    for m in lag_results:
        print(f"[{m.tier}] {m.table}: E2E lag = {m.e2e_lag_ms:.0f}ms")
```

### 3. Schema Drift Detector

```python
#!/usr/bin/env python3
"""
Schema Drift Detector - Monitors CDC topics for schema changes
and validates compatibility with downstream consumers.
"""

import json
import hashlib
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum
import requests


class ChangeType(Enum):
    COLUMN_ADDED = "column_added"
    COLUMN_REMOVED = "column_removed"
    COLUMN_RENAMED = "column_renamed"
    TYPE_CHANGED = "type_changed"
    NULLABLE_CHANGED = "nullable_changed"
    TABLE_CREATED = "table_created"
    TABLE_DROPPED = "table_dropped"


class Severity(Enum):
    INFO = "info"           # Safe change, auto-evolve
    WARNING = "warning"     # Needs review
    CRITICAL = "critical"   # Breaking change, block pipeline


@dataclass
class SchemaChange:
    table: str
    change_type: ChangeType
    severity: Severity
    description: str
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    detected_at: datetime = None
    has_migration_ticket: bool = False

    def __post_init__(self):
        if self.detected_at is None:
            self.detected_at = datetime.utcnow()


class SchemaDriftDetector:
    """Detects and classifies schema changes in CDC streams."""

    def __init__(self, schema_registry_url: str, alert_webhook: str):
        self.registry_url = schema_registry_url
        self.alert_webhook = alert_webhook
        self.known_schemas: Dict[str, dict] = {}
        self.change_history: List[SchemaChange] = []

    def get_latest_schema(self, subject: str) -> dict:
        """Fetch latest schema from Confluent Schema Registry."""
        resp = requests.get(f"{self.registry_url}/subjects/{subject}/versions/latest")
        resp.raise_for_status()
        return json.loads(resp.json()['schema'])

    def compare_schemas(self, table: str, old_schema: dict, new_schema: dict) -> List[SchemaChange]:
        """Compare two Avro schemas and detect changes."""
        changes = []

        old_fields = {f['name']: f for f in old_schema.get('fields', [])}
        new_fields = {f['name']: f for f in new_schema.get('fields', [])}

        # Detect removed columns
        for name in old_fields:
            if name not in new_fields:
                changes.append(SchemaChange(
                    table=table,
                    change_type=ChangeType.COLUMN_REMOVED,
                    severity=Severity.CRITICAL,
                    description=f"Column '{name}' removed from {table}",
                    old_value=json.dumps(old_fields[name])
                ))

        # Detect added columns
        for name in new_fields:
            if name not in old_fields:
                field = new_fields[name]
                # Check if nullable (has null in union type)
                is_nullable = self._is_nullable(field.get('type'))
                has_default = 'default' in field

                severity = Severity.INFO if (is_nullable or has_default) else Severity.CRITICAL
                changes.append(SchemaChange(
                    table=table,
                    change_type=ChangeType.COLUMN_ADDED,
                    severity=severity,
                    description=f"Column '{name}' added to {table} (nullable={is_nullable})",
                    new_value=json.dumps(field)
                ))

        # Detect type changes
        for name in old_fields:
            if name in new_fields:
                old_type = self._normalize_type(old_fields[name].get('type'))
                new_type = self._normalize_type(new_fields[name].get('type'))
                if old_type != new_type:
                    severity = self._classify_type_change(old_type, new_type)
                    changes.append(SchemaChange(
                        table=table,
                        change_type=ChangeType.TYPE_CHANGED,
                        severity=severity,
                        description=f"Column '{name}' type changed: {old_type} → {new_type}",
                        old_value=str(old_type),
                        new_value=str(new_type)
                    ))

        return changes

    def check_compatibility(self, subject: str, schema: dict) -> Tuple[bool, str]:
        """Check schema compatibility via Schema Registry."""
        resp = requests.post(
            f"{self.registry_url}/compatibility/subjects/{subject}/versions/latest",
            json={"schema": json.dumps(schema)},
            headers={"Content-Type": "application/vnd.schemaregistry.v1+json"}
        )
        result = resp.json()
        is_compatible = result.get('is_compatible', False)
        messages = result.get('messages', [])
        return is_compatible, '; '.join(messages)

    def monitor_loop(self, subjects: List[str]):
        """Continuously monitor subjects for schema changes."""
        # Initialize known schemas
        for subject in subjects:
            try:
                self.known_schemas[subject] = self.get_latest_schema(subject)
            except Exception:
                pass

        while True:
            for subject in subjects:
                try:
                    current = self.get_latest_schema(subject)
                    previous = self.known_schemas.get(subject)

                    if previous and current != previous:
                        table = subject.replace('-value', '').replace('.', '_')
                        changes = self.compare_schemas(table, previous, current)

                        for change in changes:
                            self._handle_change(change)

                        self.known_schemas[subject] = current

                except Exception as e:
                    print(f"Error checking {subject}: {e}")

            time.sleep(30)

    def _handle_change(self, change: SchemaChange):
        """Handle a detected schema change."""
        self.change_history.append(change)

        if change.severity == Severity.CRITICAL:
            self._send_alert(
                title=f"🚨 BREAKING SCHEMA CHANGE: {change.table}",
                message=change.description,
                severity="critical"
            )
        elif change.severity == Severity.WARNING:
            self._send_alert(
                title=f"⚠️ Schema Change: {change.table}",
                message=change.description,
                severity="warning"
            )
        else:
            print(f"[INFO] Schema evolution: {change.description}")

    def _send_alert(self, title: str, message: str, severity: str):
        """Send alert to webhook."""
        requests.post(self.alert_webhook, json={
            "title": title,
            "message": message,
            "severity": severity,
            "timestamp": datetime.utcnow().isoformat()
        })

    def _is_nullable(self, avro_type) -> bool:
        if isinstance(avro_type, list):
            return "null" in avro_type
        return False

    def _normalize_type(self, avro_type):
        if isinstance(avro_type, list):
            return [t for t in avro_type if t != "null"]
        return avro_type

    def _classify_type_change(self, old_type, new_type) -> Severity:
        safe_widenings = {
            ('int', 'long'), ('float', 'double'), ('int', 'float')
        }
        if (str(old_type), str(new_type)) in safe_widenings:
            return Severity.WARNING
        return Severity.CRITICAL
```

### 4. Reconciliation Spark Job

```python
#!/usr/bin/env python3
"""
CDC Reconciliation Spark Job - Validates consistency between
source databases and target data lake.
"""

from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import StructType, StructField, StringType, LongType, TimestampType
from datetime import datetime, timedelta
import hashlib


class CDCReconciler:
    """Reconciles source database with target data lake."""

    def __init__(self, spark: SparkSession, config: dict):
        self.spark = spark
        self.config = config
        self.results = []

    def reconcile_table(self, source_table: str, target_path: str,
                        key_columns: list, check_columns: list = None):
        """
        Full reconciliation for a single table.
        Checks: row count, key coverage, value consistency (sampled).
        """
        # Read source (JDBC)
        source_df = self.spark.read.format("jdbc").options(
            url=self.config['source_jdbc_url'],
            dbtable=source_table,
            driver="org.postgresql.Driver",
            user=self.config['source_user'],
            password=self.config['source_password'],
            fetchsize="10000"
        ).load()

        # Read target (Delta Lake / Parquet)
        target_df = self.spark.read.format("delta").load(target_path)

        # 1. Row count check
        source_count = source_df.count()
        target_count = target_df.count()
        count_diff = abs(source_count - target_count)
        count_drift_pct = (count_diff / max(source_count, 1)) * 100

        self.results.append({
            'table': source_table,
            'check': 'row_count',
            'source_value': source_count,
            'target_value': target_count,
            'drift_pct': count_drift_pct,
            'passed': count_drift_pct < 0.01,
            'timestamp': datetime.utcnow().isoformat()
        })

        # 2. Key coverage check (are all source PKs in target?)
        source_keys = source_df.select(key_columns).distinct()
        target_keys = target_df.select(key_columns).distinct()

        missing_in_target = source_keys.subtract(target_keys).count()
        extra_in_target = target_keys.subtract(source_keys).count()

        self.results.append({
            'table': source_table,
            'check': 'key_coverage',
            'missing_in_target': missing_in_target,
            'extra_in_target': extra_in_target,
            'passed': missing_in_target == 0,
            'timestamp': datetime.utcnow().isoformat()
        })

        # 3. Sampled value comparison (hash-based)
        if check_columns:
            sample_rate = min(10000 / max(source_count, 1), 1.0)
            self._check_value_consistency(
                source_df, target_df, key_columns,
                check_columns, sample_rate, source_table
            )

        return self.results

    def _check_value_consistency(self, source_df, target_df,
                                  key_columns, check_columns,
                                  sample_rate, table_name):
        """Hash-based value consistency check on sampled rows."""
        all_cols = key_columns + check_columns
        hash_expr = F.md5(F.concat_ws('|', *[F.col(c).cast('string') for c in check_columns]))

        source_hashed = (
            source_df
            .select(key_columns + check_columns)
            .sample(fraction=sample_rate, seed=42)
            .withColumn('_row_hash', hash_expr)
            .select(key_columns + ['_row_hash'])
        )

        target_hashed = (
            target_df
            .select(key_columns + check_columns)
            .withColumn('_row_hash', hash_expr)
            .select(key_columns + ['_row_hash'])
        )

        # Join on keys and compare hashes
        comparison = source_hashed.alias('s').join(
            target_hashed.alias('t'),
            on=key_columns,
            how='inner'
        ).withColumn(
            'hash_match',
            F.col('s._row_hash') == F.col('t._row_hash')
        )

        total_compared = comparison.count()
        mismatches = comparison.filter(~F.col('hash_match')).count()
        mismatch_rate = (mismatches / max(total_compared, 1)) * 100

        self.results.append({
            'table': table_name,
            'check': 'value_consistency',
            'total_compared': total_compared,
            'mismatches': mismatches,
            'mismatch_rate_pct': mismatch_rate,
            'passed': mismatch_rate < 0.1,
            'timestamp': datetime.utcnow().isoformat()
        })

    def run_full_reconciliation(self, table_configs: list):
        """Run reconciliation across all configured tables."""
        all_results = []
        for tc in table_configs:
            results = self.reconcile_table(
                source_table=tc['source'],
                target_path=tc['target'],
                key_columns=tc['keys'],
                check_columns=tc.get('check_columns')
            )
            all_results.extend(results)

        # Write results
        results_df = self.spark.createDataFrame(all_results)
        results_df.write.mode("append").format("delta").save(
            self.config['results_path']
        )

        # Alert on failures
        failures = [r for r in all_results if not r['passed']]
        if failures:
            self._send_alerts(failures)

        return all_results

    def _send_alerts(self, failures):
        """Send alerts for reconciliation failures."""
        import requests
        for f in failures:
            requests.post(self.config['alert_webhook'], json={
                "title": f"CDC Reconciliation Failed: {f['table']}",
                "check": f['check'],
                "details": f,
                "severity": "high"
            })


# Entrypoint
if __name__ == "__main__":
    spark = SparkSession.builder \
        .appName("cdc-reconciliation") \
        .config("spark.jars.packages", "io.delta:delta-core_2.12:2.4.0") \
        .getOrCreate()

    config = {
        'source_jdbc_url': 'jdbc:postgresql://prod-pg:5432/app',
        'source_user': 'recon_reader',
        'source_password': '...',
        'results_path': 's3://data-lake/monitoring/cdc-reconciliation/',
        'alert_webhook': 'https://hooks.slack.com/services/...'
    }

    tables = [
        {'source': 'public.orders', 'target': 's3://lake/cdc/orders/', 'keys': ['id'], 'check_columns': ['status', 'total', 'updated_at']},
        {'source': 'public.users', 'target': 's3://lake/cdc/users/', 'keys': ['id'], 'check_columns': ['email', 'name']},
        {'source': 'public.payments', 'target': 's3://lake/cdc/payments/', 'keys': ['id'], 'check_columns': ['amount', 'status']},
    ]

    reconciler = CDCReconciler(spark, config)
    reconciler.run_full_reconciliation(tables)
```

### 5. PostgreSQL Replication Slot Monitor

```python
#!/usr/bin/env python3
"""
PostgreSQL Replication Slot Monitor
Prevents WAL disk exhaustion by monitoring slot lag growth.
"""

import time
import psycopg2
from prometheus_client import start_http_server, Gauge, Counter
from datetime import datetime


SLOT_LAG_BYTES = Gauge(
    'pg_replication_slot_lag_bytes',
    'Replication slot lag in bytes',
    ['slot_name', 'database', 'plugin']
)

SLOT_ACTIVE = Gauge(
    'pg_replication_slot_active',
    'Whether replication slot is active (1=active, 0=inactive)',
    ['slot_name', 'database']
)

WAL_DISK_USAGE_BYTES = Gauge(
    'pg_wal_disk_usage_bytes',
    'Total WAL disk usage in bytes',
    ['instance']
)

SLOT_GROWTH_RATE = Gauge(
    'pg_replication_slot_growth_rate_bytes_per_sec',
    'Rate of slot lag growth (bytes/sec)',
    ['slot_name']
)

DISK_EXHAUSTION_ETA_SECONDS = Gauge(
    'pg_wal_disk_exhaustion_eta_seconds',
    'Estimated time until WAL fills available disk',
    ['instance']
)


class ReplicationSlotMonitor:
    def __init__(self, pg_conn_string: str, instance_name: str,
                 available_disk_bytes: int):
        self.pg_conn_string = pg_conn_string
        self.instance_name = instance_name
        self.available_disk_bytes = available_disk_bytes
        self.previous_lag: dict = {}
        self.previous_ts: float = time.time()

    def check_slots(self):
        conn = psycopg2.connect(self.pg_conn_string)
        cur = conn.cursor()

        cur.execute("""
            SELECT
                slot_name,
                database,
                plugin,
                active,
                pg_wal_lsn_diff(pg_current_wal_lsn(), confirmed_flush_lsn) AS lag_bytes,
                pg_wal_lsn_diff(pg_current_wal_lsn(), restart_lsn) AS retained_bytes
            FROM pg_replication_slots
            WHERE slot_type = 'logical'
        """)

        now = time.time()
        elapsed = now - self.previous_ts
        total_retained = 0

        for row in cur.fetchall():
            slot_name, database, plugin, active, lag_bytes, retained_bytes = row
            lag_bytes = lag_bytes or 0
            retained_bytes = retained_bytes or 0

            SLOT_LAG_BYTES.labels(
                slot_name=slot_name, database=database, plugin=plugin
            ).set(lag_bytes)

            SLOT_ACTIVE.labels(
                slot_name=slot_name, database=database
            ).set(1 if active else 0)

            # Calculate growth rate
            prev_lag = self.previous_lag.get(slot_name, lag_bytes)
            growth_rate = (lag_bytes - prev_lag) / max(elapsed, 1)
            SLOT_GROWTH_RATE.labels(slot_name=slot_name).set(max(growth_rate, 0))

            self.previous_lag[slot_name] = lag_bytes
            total_retained = max(total_retained, retained_bytes)

            # Alert if slot is inactive and growing
            if not active and lag_bytes > 1_000_000_000:  # > 1GB
                self._alert_inactive_slot(slot_name, lag_bytes)

        # Disk exhaustion ETA
        WAL_DISK_USAGE_BYTES.labels(instance=self.instance_name).set(total_retained)

        if total_retained > 0 and elapsed > 0:
            max_growth = max(self.previous_lag.values()) if self.previous_lag else 0
            if max_growth > 0:
                eta = (self.available_disk_bytes - total_retained) / (max_growth / elapsed)
                DISK_EXHAUSTION_ETA_SECONDS.labels(
                    instance=self.instance_name
                ).set(max(eta, 0))

        self.previous_ts = now
        cur.close()
        conn.close()

    def _alert_inactive_slot(self, slot_name: str, lag_bytes: int):
        lag_gb = lag_bytes / (1024**3)
        print(f"CRITICAL: Inactive slot '{slot_name}' has {lag_gb:.2f}GB lag!")
        # In production: send PagerDuty/Slack alert


def main():
    monitor = ReplicationSlotMonitor(
        pg_conn_string="host=prod-pg dbname=app user=monitor",
        instance_name="prod-pg-primary",
        available_disk_bytes=500 * 1024**3  # 500GB
    )

    start_http_server(9091)
    print("Replication slot monitor started on :9091")

    while True:
        try:
            monitor.check_slots()
        except Exception as e:
            print(f"Error: {e}")
        time.sleep(10)


if __name__ == "__main__":
    main()
```

---

## Alert Rules

### Prometheus Alert Rules

```yaml
groups:
  - name: cdc_replication
    rules:
      # Critical table lag
      - alert: CDCReplicationLagCritical
        expr: |
          cdc_end_to_end_lag_milliseconds{tier="P0"} > 30000
        for: 2m
        labels:
          severity: critical
          team: data-platform
        annotations:
          summary: "Critical table {{ $labels.table }} replication lag > 30s"
          description: "E2E lag: {{ $value | humanizeDuration }}"
          runbook: "https://wiki/runbooks/cdc-lag-critical"

      # Important table lag
      - alert: CDCReplicationLagHigh
        expr: |
          cdc_end_to_end_lag_milliseconds{tier="P1"} > 300000
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Table {{ $labels.table }} replication lag > 5 min"

      # Replication slot growing dangerously
      - alert: ReplicationSlotLagDangerous
        expr: |
          pg_replication_slot_lag_bytes > 10737418240
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Replication slot {{ $labels.slot_name }} lag > 10GB"
          description: "WAL retention growing. Risk of disk exhaustion."
          action: "Check connector health. Consider dropping slot if abandoned."

      # Inactive replication slot
      - alert: ReplicationSlotInactive
        expr: |
          pg_replication_slot_active == 0
          and pg_replication_slot_lag_bytes > 1073741824
        for: 10m
        labels:
          severity: critical
        annotations:
          summary: "Inactive slot {{ $labels.slot_name }} retaining > 1GB WAL"

      # Schema change without ticket
      - alert: UnplannedSchemaChange
        expr: |
          increase(cdc_schema_changes_total{change_type=~"column_removed|type_changed"}[5m]) > 0
        labels:
          severity: warning
        annotations:
          summary: "Breaking schema change detected on {{ $labels.table }}"

      # Row count drift
      - alert: CDCRowCountDrift
        expr: |
          abs(cdc_reconciliation_source_count - cdc_reconciliation_target_count)
          / cdc_reconciliation_source_count > 0.0001
        for: 30m
        labels:
          severity: warning
        annotations:
          summary: "Row count drift > 0.01% for {{ $labels.table }}"

      # Connector task failure
      - alert: CDCConnectorTaskFailed
        expr: |
          kafka_connect_connector_task_state{state="FAILED"} > 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "CDC connector task failed: {{ $labels.connector }}"
          action: "Restart task or investigate error in connector logs"

      # Disk exhaustion ETA
      - alert: WALDiskExhaustionImminent
        expr: |
          pg_wal_disk_exhaustion_eta_seconds < 3600
        labels:
          severity: critical
        annotations:
          summary: "WAL disk exhaustion in < 1 hour on {{ $labels.instance }}"
```

---

## Operational Runbook

### Handling High Replication Lag

```
┌─────────────────────────────────────────────────────────┐
│              LAG INVESTIGATION FLOWCHART                  │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Lag Alert Fires                                        │
│       │                                                 │
│       ▼                                                 │
│  Check connector status ──▶ FAILED? ──▶ Restart task   │
│       │                                                 │
│       ▼ (RUNNING)                                       │
│  Check consumer lag ──▶ High? ──▶ Scale consumers      │
│       │                                                 │
│       ▼ (Normal)                                        │
│  Check source slot lag ──▶ Growing? ──▶ Check source   │
│       │                          load / long queries    │
│       ▼ (Normal)                                        │
│  Check sink performance ──▶ Slow? ──▶ Scale sink /     │
│       │                          check target load      │
│       ▼                                                 │
│  Check for schema change ──▶ Yes? ──▶ Fix schema       │
│       │                          compatibility          │
│       ▼                                                 │
│  Escalate to on-call                                    │
└─────────────────────────────────────────────────────────┘
```

---

## Technologies Summary

| Component | Technology | Purpose |
|-----------|-----------|---------|
| CDC Capture | Debezium, Maxwell | Read WAL/binlog |
| Transport | Apache Kafka | Event streaming |
| Schema Management | Confluent Schema Registry | Schema evolution |
| Sink | Kafka Connect S3/Snowflake/ClickHouse | Write to targets |
| Metrics | Prometheus + Grafana | Monitoring & dashboards |
| Reconciliation | Apache Spark | Consistency verification |
| Alerting | PagerDuty, Slack | Incident notification |
| Slot Monitoring | Custom Python + psycopg2 | PostgreSQL WAL safety |

---

## Key Takeaways

1. **Measure E2E lag, not just consumer lag** — Consumer lag alone misses source and sink delays
2. **Monitor replication slots religiously** — An abandoned slot can crash your production database
3. **Automate schema drift detection** — Breaking changes should never reach production silently
4. **Run reconciliation continuously** — Don't wait for someone to notice missing data
5. **Classify tables by tier** — Not all tables deserve the same monitoring intensity
6. **Test your CDC monitoring** — Inject artificial lag to verify alerts fire correctly
