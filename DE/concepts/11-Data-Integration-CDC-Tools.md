# Data Integration & CDC Tools - Deep Dive

## Table of Contents
1. [CDC Fundamentals](#1-cdc-fundamentals)
2. [Debezium Deep Dive](#2-debezium-deep-dive)
3. [AWS DMS Deep Dive](#3-aws-dms-deep-dive)
4. [Flink CDC Deep Dive](#4-flink-cdc-deep-dive)
5. [Airbyte Deep Dive](#5-airbyte-deep-dive)
6. [Meltano & Singer](#6-meltano--singer)
7. [Integration Patterns at Scale](#7-integration-patterns-at-scale)
8. [Decision Framework](#8-decision-framework)
9. [Production Checklist](#9-production-checklist)

---

## 1. CDC Fundamentals

### What is CDC?
Change Data Capture (CDC) tracks row-level changes in databases and propagates them downstream as events.

### CDC Approaches

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        CDC Implementation Methods                        │
├──────────────────┬──────────────────┬──────────────────┬────────────────┤
│   Log-Based      │   Query-Based    │  Trigger-Based   │ Outbox Pattern │
├──────────────────┼──────────────────┼──────────────────┼────────────────┤
│ Read DB WAL/     │ Poll source with │ DB triggers write│ Application    │
│ binlog/oplog     │ timestamp/version│ to change table  │ writes to      │
│                  │ column           │                  │ outbox table   │
├──────────────────┼──────────────────┼──────────────────┼────────────────┤
│ ✅ No source     │ ❌ Misses deletes│ ❌ Performance   │ ✅ App control │
│    impact        │ ❌ Source load   │    overhead      │ ✅ Transactional│
│ ✅ All changes   │ ✅ Simple setup  │ ✅ All changes   │ ❌ App changes │
│ ✅ Low latency   │ ❌ High latency  │ ❌ Schema coupling│ ✅ Event design│
│ ❌ DB-specific   │ ✅ DB-agnostic   │ ❌ Maintenance   │ ❌ Extra table │
└──────────────────┴──────────────────┴──────────────────┴────────────────┘
```

### CDC Guarantees

| Guarantee | Log-Based | Query-Based | Outbox |
|-----------|-----------|-------------|--------|
| Ordering | Per-partition (same PK) | No guarantee | Per-aggregate |
| Exactly-once | With snapshots + offsets | At-least-once | At-least-once (needs dedup) |
| Completeness | All DML (INSERT/UPDATE/DELETE) | Misses deletes | App-defined events |
| Latency | Milliseconds | Seconds-minutes | Milliseconds |

### Schema Evolution in CDC Streams

```
Problem: Source schema changes (ALTER TABLE) must propagate to consumers

Strategies:
1. Schema Registry + Compatibility Modes
   - BACKWARD: new schema can read old data
   - FORWARD: old schema can read new data  
   - FULL: both directions

2. Schema History Topic (Debezium approach)
   - DDL changes recorded in separate topic
   - Consumers can react to schema changes

3. Breaking vs Non-Breaking Changes
   Non-breaking: ADD COLUMN (nullable), WIDEN column type
   Breaking: DROP COLUMN, RENAME COLUMN, CHANGE type (narrowing)
   
4. Dual-write migration pattern:
   Old schema → write both → new schema → deprecate old
```

---

## 2. Debezium Deep Dive

### Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                     Kafka Connect Cluster                          │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │              Debezium Source Connector                       │  │
│  │  ┌──────────┐  ┌───────────┐  ┌──────────┐  ┌──────────┐ │  │
│  │  │ Snapshot │  │  Binlog/  │  │  Schema  │  │  Offset  │ │  │
│  │  │  Engine  │  │  WAL/Oplog│  │  History │  │  Storage │ │  │
│  │  └──────────┘  └───────────┘  └──────────┘  └──────────┘ │  │
│  └────────────────────────────────────────────────────────────┘  │
│                              │                                     │
│                              ▼                                     │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │              SMTs (Single Message Transforms)                │  │
│  │  • Route by table name                                      │  │
│  │  • Filter columns                                           │  │
│  │  • Flatten nested structures                                │  │
│  └────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│                        Apache Kafka                                │
│  ┌─────────────┐ ┌──────────────┐ ┌───────────────────────────┐ │
│  │ Data Topics │ │Schema History│ │  Schema Registry (Avro/   │ │
│  │ (per table) │ │    Topic     │ │  Protobuf/JSON Schema)    │ │
│  └─────────────┘ └──────────────┘ └───────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
```

### Database-Specific Internals

#### MySQL (Binlog)
```json
// Connector config
{
  "name": "mysql-cdc-connector",
  "config": {
    "connector.class": "io.debezium.connector.mysql.MySqlConnector",
    "database.hostname": "mysql-primary.prod",
    "database.port": "3306",
    "database.user": "debezium",
    "database.password": "${secrets:mysql/password}",
    "database.server.id": "184054",
    "topic.prefix": "prod-mysql",
    "database.include.list": "inventory,orders",
    "table.include.list": "inventory.products,orders.order_items",
    "schema.history.internal.kafka.bootstrap.servers": "kafka:9092",
    "schema.history.internal.kafka.topic": "schema-changes.prod-mysql",
    
    // Snapshot configuration
    "snapshot.mode": "when_needed",
    "snapshot.locking.mode": "minimal",
    
    // Binlog reading
    "include.schema.changes": "true",
    "binlog.buffer.size": "0",
    "gtid.source.includes": "",
    
    // Performance
    "max.batch.size": "2048",
    "max.queue.size": "8192",
    "poll.interval.ms": "100",
    
    // Heartbeat (prevents slot/binlog growth during idle)
    "heartbeat.interval.ms": "10000",
    "heartbeat.action.query": "INSERT INTO heartbeat (ts) VALUES (NOW()) ON DUPLICATE KEY UPDATE ts=NOW()",
    
    // Signal table for incremental snapshots
    "signal.data.collection": "inventory.debezium_signal",
    "signal.enabled.channels": "source",
    
    // Transforms
    "transforms": "route,unwrap",
    "transforms.route.type": "io.debezium.transforms.ByLogicalTableRouter",
    "transforms.route.topic.regex": "(.*)\\.(.*)",
    "transforms.route.topic.replacement": "cdc.$1.$2",
    "transforms.unwrap.type": "io.debezium.transforms.ExtractNewRecordState",
    "transforms.unwrap.drop.tombstones": "false",
    "transforms.unwrap.delete.handling.mode": "rewrite",
    "transforms.unwrap.add.fields": "op,source.ts_ms,source.db,source.table"
  }
}
```

**MySQL Requirements:**
- binlog_format = ROW
- binlog_row_image = FULL
- User needs: SELECT, RELOAD, SHOW DATABASES, REPLICATION SLAVE, REPLICATION CLIENT

#### PostgreSQL (WAL / Logical Replication)
```json
{
  "name": "postgres-cdc-connector",
  "config": {
    "connector.class": "io.debezium.connector.postgresql.PostgresConnector",
    "database.hostname": "pg-primary.prod",
    "database.port": "5432",
    "database.user": "debezium",
    "database.dbname": "orders_db",
    "topic.prefix": "prod-pg",
    "schema.include.list": "public,inventory",
    
    // Plugin selection
    "plugin.name": "pgoutput",  // Built-in (PG 10+), vs decoderbufs, wal2json
    "publication.name": "dbz_publication",
    "publication.autocreate.mode": "filtered",
    
    // Slot management (CRITICAL for production)
    "slot.name": "debezium_orders",
    "slot.drop.on.stop": "false",  // Keep slot on graceful stop
    
    // WAL disk pressure prevention
    "heartbeat.interval.ms": "10000",  // Prevents WAL accumulation
    "heartbeat.action.query": "UPDATE debezium_heartbeat SET last_heartbeat = now()",
    
    // Snapshot
    "snapshot.mode": "initial",
    "snapshot.lock.timeout.ms": "10000",
    
    // Decimal handling
    "decimal.handling.mode": "string",
    
    // TOAST columns
    "column.include.list": "public.orders.id,public.orders.status,public.orders.amount"
  }
}
```

**PostgreSQL Critical Production Concerns:**
```
WAL Disk Pressure Problem:
─────────────────────────
When connector is down/lagging, WAL segments accumulate because the 
replication slot prevents WAL recycling.

Monitoring queries:
  SELECT slot_name, pg_size_pretty(pg_wal_lsn_diff(pg_current_wal_lsn(), restart_lsn)) 
  AS slot_lag FROM pg_replication_slots;

Mitigation:
  1. heartbeat.interval.ms = 10000 (advances slot even with no changes)
  2. Alert on slot_lag > 1GB
  3. max_wal_size tuning
  4. Automated slot dropping if lag > threshold (emergency)
  
TOAST Columns:
─────────────
Large columns stored in TOAST tables don't appear in WAL for unchanged-toast-datum.
Solution: replica identity FULL (but increases WAL volume)
  ALTER TABLE orders REPLICA IDENTITY FULL;
```

### Snapshot Modes

| Mode | Behavior | Use Case |
|------|----------|----------|
| `initial` | Full snapshot on first start, then stream | New connector, need all existing data |
| `schema_only` | Capture schema only, stream from current position | Only need future changes |
| `never` | No snapshot, start from last offset | Resuming after crash |
| `when_needed` | Snapshot if no offset exists or offset is invalid | Self-healing |
| `initial_only` | Full snapshot, then stop | One-time migration |

### Incremental Snapshots (Signal Table)

```sql
-- Create signal table
CREATE TABLE debezium_signal (
  id VARCHAR(42) PRIMARY KEY,
  type VARCHAR(32) NOT NULL,
  data VARCHAR(2048) NULL
);

-- Trigger incremental snapshot of specific table
INSERT INTO debezium_signal (id, type, data) VALUES (
  'ad-hoc-1',
  'execute-snapshot',
  '{"data-collections": ["inventory.products"], "type": "incremental"}'
);

-- Stop incremental snapshot
INSERT INTO debezium_signal (id, type, data) VALUES (
  'ad-hoc-2',
  'stop-snapshot',
  '{"data-collections": ["inventory.products"], "type": "incremental"}'
);
```

**How Incremental Snapshots Work:**
```
1. Signal received → mark watermarks
2. Chunk-based reading (SELECT * FROM table WHERE pk > ? AND pk <= ? ORDER BY pk LIMIT chunk_size)
3. Interleave chunks with streaming events
4. Deduplicate: if streaming event for same PK arrives during chunk → streaming wins
5. No locks, no blocking, production-safe
```

### Outbox Pattern Implementation

```sql
-- Outbox table
CREATE TABLE outbox (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  aggregatetype VARCHAR(255) NOT NULL,
  aggregateid VARCHAR(255) NOT NULL,
  type VARCHAR(255) NOT NULL,
  payload JSONB NOT NULL,
  created_at TIMESTAMP DEFAULT now()
);

-- Application writes (within same transaction as business data)
BEGIN;
  INSERT INTO orders (id, customer_id, amount, status) 
  VALUES ('order-123', 'cust-456', 99.99, 'CREATED');
  
  INSERT INTO outbox (aggregatetype, aggregateid, type, payload) 
  VALUES ('Order', 'order-123', 'OrderCreated', 
    '{"orderId": "order-123", "customerId": "cust-456", "amount": 99.99}');
COMMIT;
```

```json
// Connector config for outbox pattern
{
  "transforms": "outbox",
  "transforms.outbox.type": "io.debezium.transforms.outbox.EventRouter",
  "transforms.outbox.table.fields.additional.placement": "type:header:eventType",
  "transforms.outbox.table.field.event.id": "id",
  "transforms.outbox.table.field.event.key": "aggregateid",
  "transforms.outbox.table.field.event.payload": "payload",
  "transforms.outbox.route.by.field": "aggregatetype",
  "transforms.outbox.route.topic.replacement": "events.${routedByValue}"
}
```

### Tombstone Events and Log Compaction

```
Event sequence for DELETE:
1. Delete event (op: "d", before: {full row data})
2. Tombstone (key: {PK}, value: null)  ← enables Kafka log compaction

Config:
  "tombstones.on.delete": "true"     // Generate tombstone after delete
  "drop.tombstones": "false"         // Keep tombstones in output

Why it matters:
  - Kafka log compaction removes records with null values
  - This is how deleted records get purged from compacted topics
  - Without tombstones, deleted records persist forever in compacted topics
```

### Monitoring and Alerting

```yaml
# Key Debezium metrics (JMX → Prometheus)
metrics:
  # Streaming metrics
  - debezium_metrics_MilliSecondsBehindSource   # CDC lag
  - debezium_metrics_NumberOfEventsFiltered
  - debezium_metrics_TotalNumberOfEventsSeen
  - debezium_metrics_QueueTotalCapacity
  - debezium_metrics_QueueRemainingCapacity
  
  # Snapshot metrics
  - debezium_metrics_SnapshotCompleted
  - debezium_metrics_RemainingTableCount
  - debezium_metrics_RowsScanned
  
  # Connection metrics  
  - debezium_metrics_Connected
  - debezium_metrics_NumberOfDisconnects

# Alert rules
alerts:
  - name: CDCLagHigh
    expr: debezium_metrics_MilliSecondsBehindSource > 60000
    severity: warning
    
  - name: CDCLagCritical  
    expr: debezium_metrics_MilliSecondsBehindSource > 300000
    severity: critical
    
  - name: ConnectorDisconnected
    expr: debezium_metrics_Connected == 0
    for: 2m
    severity: critical
    
  - name: PostgreSQLSlotLag
    expr: pg_replication_slot_lag_bytes > 1073741824  # 1GB
    severity: warning
```

### Failure Modes and Recovery

| Failure | Symptom | Recovery |
|---------|---------|----------|
| Connector OOM | Task FAILED status | Increase memory, reduce batch size, add table filters |
| WAL/Binlog purged | Offset no longer available | Re-snapshot (signal table incremental) |
| Schema incompatible | Serialization error | Fix schema registry, update compatibility |
| PG slot bloat | Disk full on source DB | Emergency: drop slot, re-create connector |
| Network partition | Lag increases, then recovery | Auto-recovery via offset tracking |
| Source DB failover | Connector loses connection | GTID-based recovery (MySQL), slot on replica (PG) |

---

## 3. AWS DMS Deep Dive

### Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        AWS DMS Architecture                           │
│                                                                       │
│  ┌──────────┐    ┌─────────────────────────────┐    ┌────────────┐  │
│  │  Source   │───▶│    Replication Instance      │───▶│   Target   │  │
│  │ Endpoint  │    │  ┌───────────────────────┐  │    │  Endpoint  │  │
│  │           │    │  │   Replication Task     │  │    │            │  │
│  │ • RDS     │    │  │  ┌─────┐  ┌────────┐  │  │    │ • S3      │  │
│  │ • Aurora  │    │  │  │Full │  │Ongoing │  │  │    │ • Kinesis │  │
│  │ • On-prem │    │  │  │Load │  │Replicat│  │  │    │ • Redshift│  │
│  │ • Oracle  │    │  │  └─────┘  └────────┘  │  │    │ • RDS     │  │
│  │ • SQL Srv │    │  └───────────────────────┘  │    │ • DynamoDB│  │
│  └──────────┘    │                               │    └────────────┘  │
│                  │  Instance Class: dms.r5.large  │                    │
│                  │  Multi-AZ: Yes/No              │                    │
│                  └─────────────────────────────────┘                    │
└─────────────────────────────────────────────────────────────────────┘
```

### Migration Types

| Type | Behavior | Use Case |
|------|----------|----------|
| Full Load | One-time bulk copy | Migration, initial load |
| CDC Only | Ongoing change capture | Real-time replication after initial load |
| Full Load + CDC | Bulk copy then switch to CDC | Complete migration with zero downtime |

### Task Settings Deep Dive

```json
{
  "TargetMetadata": {
    "TargetSchema": "",
    "SupportLobs": true,
    "FullLobMode": false,
    "LobChunkSize": 64,
    "LimitedSizeLobMode": true,
    "LobMaxSize": 32768,
    "InlineLobMaxSize": 0,
    "LoadMaxFileSize": 0,
    "ParallelLoadThreads": 8,
    "ParallelLoadBufferSize": 500,
    "BatchApplyEnabled": true,
    "TaskRecoveryTableEnabled": false,
    "ParallelLoadQueuesPerThread": 0,
    "ParallelApplyThreads": 4,
    "ParallelApplyBufferSize": 1000
  },
  "FullLoadSettings": {
    "TargetTablePrepMode": "DROP_AND_CREATE",
    "CreatePkAfterFullLoad": true,
    "StopTaskCachedChangesApplied": false,
    "StopTaskCachedChangesNotApplied": false,
    "MaxFullLoadSubTasks": 8,
    "TransactionConsistencyTimeout": 600,
    "CommitRate": 10000
  },
  "Logging": {
    "EnableLogging": true,
    "LogComponents": [
      {"Id": "TRANSFORMATION", "Severity": "LOGGER_SEVERITY_DEFAULT"},
      {"Id": "SOURCE_UNLOAD", "Severity": "LOGGER_SEVERITY_DEFAULT"},
      {"Id": "TARGET_LOAD", "Severity": "LOGGER_SEVERITY_DETAILED"},
      {"Id": "SOURCE_CAPTURE", "Severity": "LOGGER_SEVERITY_DEFAULT"},
      {"Id": "TARGET_APPLY", "Severity": "LOGGER_SEVERITY_DEFAULT"}
    ]
  },
  "ChangeProcessingTuning": {
    "BatchApplyPreserveTransaction": true,
    "BatchApplyTimeoutMin": 1,
    "BatchApplyTimeoutMax": 30,
    "BatchApplyMemoryLimit": 500,
    "BatchSplitSize": 0,
    "MinTransactionSize": 1000,
    "CommitTimeout": 1,
    "MemoryLimitTotal": 1024,
    "MemoryKeepTime": 60,
    "StatementCacheSize": 50
  }
}
```

### DMS with S3 as Target (Parquet Output)

```json
// S3 target endpoint settings
{
  "EndpointType": "target",
  "EngineName": "s3",
  "S3Settings": {
    "BucketName": "data-lake-raw",
    "BucketFolder": "cdc/mysql-orders",
    "ServiceAccessRoleArn": "arn:aws:iam::123456789:role/dms-s3-role",
    "DataFormat": "parquet",
    "ParquetVersion": "parquet-2-0",
    "EnableStatistics": true,
    "IncludeOpForFullLoad": true,
    "CdcInsertsAndUpdates": true,
    "TimestampColumnName": "_dms_ingestion_timestamp",
    "ParquetTimestampInMillisecond": true,
    "DatePartitionEnabled": true,
    "DatePartitionSequence": "YYYYMMDD",
    "DatePartitionDelimiter": "SLASH",
    "AddColumnName": true,
    "CdcMaxBatchInterval": 60,
    "CdcMinFileSize": 32000,
    "CompressionType": "GZIP"
  }
}
```

**S3 output structure:**
```
s3://data-lake-raw/cdc/mysql-orders/
├── LOAD00000001.parquet          # Full load files
├── LOAD00000002.parquet
├── 2024/01/15/
│   ├── 20240115-093045-123.parquet  # CDC files (date-partitioned)
│   └── 20240115-094045-456.parquet
└── 2024/01/16/
    └── ...

CDC file columns: Op (I/U/D), _dms_ingestion_timestamp, + all source columns
```

### DMS with Kinesis as Target

```json
{
  "EngineName": "kinesis",
  "KinesisSettings": {
    "StreamArn": "arn:aws:kinesis:us-east-1:123456789:stream/cdc-stream",
    "ServiceAccessRoleArn": "arn:aws:iam::123456789:role/dms-kinesis-role",
    "MessageFormat": "json-unformatted",
    "IncludePartitionValue": true,
    "PartitionIncludeSchemaTable": true,
    "IncludeTableAlterOperations": true,
    "IncludeControlDetails": true,
    "IncludeNullAndEmpty": true
  }
}
```

### DMS Serverless vs Provisioned

| Aspect | Provisioned | Serverless |
|--------|-------------|------------|
| Sizing | Manual (dms.r5.large etc) | Auto (1-128 DCU) |
| Scaling | Manual resize (downtime) | Automatic |
| Multi-AZ | Optional | Built-in |
| Cost | Per-hour (instance) | Per-DCU-hour (usage) |
| Use case | Predictable, high-volume | Variable, burstable |
| Limitations | Manual ops | Max 128 DCU, no VPC peering |

### DMS Limitations

```
Critical Limitations:
1. No DDL replication for most source/target combos
2. LOB columns: full LOB mode is slow; limited mode truncates
3. PostgreSQL: logical replication doesn't capture:
   - TRUNCATE (before PG 11)
   - Sequences
   - Large Objects
4. Oracle: supplemental logging required
5. Partitioned tables: may need special handling
6. Binary/BLOB data: encoding issues possible
7. Computed columns: not replicated
8. Triggers on target: may cause issues (disable recommended)
```

### DMS Monitoring

```python
# boto3 monitoring example
import boto3

client = boto3.client('dms')

# Get replication task statistics
response = client.describe_table_statistics(
    ReplicationTaskArn='arn:aws:dms:...',
    Filters=[{'Name': 'schema-name', 'Values': ['public']}]
)

for table in response['TableStatistics']:
    print(f"Table: {table['TableName']}")
    print(f"  Full Load Rows: {table['FullLoadRows']}")
    print(f"  Inserts: {table['Inserts']}")
    print(f"  Updates: {table['Updates']}")
    print(f"  Deletes: {table['Deletes']}")
    print(f"  DDLs: {table['Ddls']}")
    print(f"  Validation State: {table['ValidationState']}")

# CloudWatch metrics to monitor:
# - CDCLatencySource: lag at source
# - CDCLatencyTarget: lag at target
# - CDCIncomingChanges: pending changes
# - CDCThroughputRowsSource: rows/sec from source
# - CDCThroughputRowsTarget: rows/sec to target
# - FreeMemory, SwapUsage, CPUUtilization
```

---

## 4. Flink CDC Deep Dive

### Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    Flink CDC Pipeline                          │
│                                                                │
│  ┌────────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │  CDC Source     │───▶│  Flink Job   │───▶│    Sink      │  │
│  │  Connector      │    │              │    │              │  │
│  │                 │    │  • Filter    │    │  • Kafka     │  │
│  │  • MySQL CDC   │    │  • Transform │    │  • Iceberg   │  │
│  │  • PG CDC      │    │  • Aggregate │    │  • JDBC      │  │
│  │  • MongoDB CDC │    │  • Join      │    │  • ES        │  │
│  │  • Oracle CDC  │    │  • Window    │    │  • S3        │  │
│  └────────────────┘    └──────────────┘    └──────────────┘  │
│                                                                │
│  Key: Source connector reads binlog/WAL directly               │
│  (No Kafka Connect required - runs inside Flink)              │
└──────────────────────────────────────────────────────────────┘
```

### MySQL CDC Connector - Chunk-Based Snapshot

```java
// Flink SQL - MySQL CDC source
CREATE TABLE orders (
    order_id INT,
    customer_id INT,
    amount DECIMAL(10,2),
    status STRING,
    created_at TIMESTAMP(3),
    updated_at TIMESTAMP(3),
    PRIMARY KEY (order_id) NOT ENFORCED
) WITH (
    'connector' = 'mysql-cdc',
    'hostname' = 'mysql.prod.internal',
    'port' = '3306',
    'username' = 'flink_cdc',
    'password' = '${mysql.password}',
    'database-name' = 'orders_db',
    'table-name' = 'orders',
    'server-id' = '5400-5404',  -- Range for parallel readers
    'scan.incremental.snapshot.enabled' = 'true',
    'scan.incremental.snapshot.chunk.size' = '8096',
    'scan.snapshot.fetch.size' = '1024',
    'connect.timeout' = '30s',
    'debezium.min.row.count.to.stream.results' = '1000'
);
```

**Chunk-Based Snapshot Algorithm (Lock-Free):**
```
Phase 1: Chunk Splitting
  1. Read MIN(pk), MAX(pk) from table
  2. Split into chunks: [min, min+chunk_size), [min+chunk_size, min+2*chunk_size), ...
  3. Distribute chunks across parallel readers

Phase 2: Chunk Reading (per chunk, per reader)
  1. Record LOW watermark (current binlog position)
  2. SELECT * FROM table WHERE pk >= chunk_start AND pk < chunk_end
  3. Record HIGH watermark (current binlog position)
  4. Read binlog between LOW and HIGH watermarks for this chunk's PKs
  5. Merge: snapshot data + binlog changes = consistent chunk state

Phase 3: Streaming
  After all chunks complete → switch to pure binlog streaming

Benefits:
  - No global locks (no FTWRL)
  - Parallel snapshot reading
  - Checkpoint-able (resume from any chunk)
  - Exactly-once with Flink checkpointing
```

### PostgreSQL CDC Connector

```sql
-- Flink SQL
CREATE TABLE pg_orders (
    order_id INT,
    status STRING,
    amount DECIMAL(10,2),
    PRIMARY KEY (order_id) NOT ENFORCED
) WITH (
    'connector' = 'postgres-cdc',
    'hostname' = 'pg.prod.internal',
    'port' = '5432',
    'username' = 'flink_cdc',
    'password' = '${pg.password}',
    'database-name' = 'orders',
    'schema-name' = 'public',
    'table-name' = 'orders',
    'slot.name' = 'flink_slot_orders',
    'decoding.plugin.name' = 'pgoutput',
    'debezium.snapshot.mode' = 'initial'
);
```

### Exactly-Once with Checkpointing

```java
// Java DataStream API example
import org.apache.flink.cdc.connectors.mysql.source.MySqlSource;
import org.apache.flink.cdc.debezium.JsonDebeziumDeserializationSchema;

MySqlSource<String> mySqlSource = MySqlSource.<String>builder()
    .hostname("mysql.prod")
    .port(3306)
    .databaseList("orders_db")
    .tableList("orders_db.orders", "orders_db.order_items")
    .username("flink_cdc")
    .password("password")
    .deserializer(new JsonDebeziumDeserializationSchema())
    .startupOptions(StartupOptions.initial())
    .splitSize(8096)
    .fetchSize(1024)
    .connectTimeout(Duration.ofSeconds(30))
    .build();

StreamExecutionEnvironment env = StreamExecutionEnvironment.getExecutionEnvironment();
env.enableCheckpointing(60000); // 60s checkpoint interval
env.getCheckpointConfig().setCheckpointingMode(CheckpointingMode.EXACTLY_ONCE);
env.getCheckpointConfig().setMinPauseBetweenCheckpoints(30000);

env.fromSource(mySqlSource, WatermarkStrategy.noWatermarks(), "MySQL CDC Source")
    .setParallelism(4)  // 4 parallel readers for snapshot
    .map(new TransformFunction())
    .sinkTo(icebergSink);

env.execute("MySQL CDC to Iceberg");
```

### Flink CDC vs Debezium

| Dimension | Flink CDC | Debezium (Kafka Connect) |
|-----------|-----------|--------------------------|
| Infrastructure | Flink cluster only | Kafka Connect + Kafka |
| Snapshot | Parallel, chunk-based, lock-free | Single-threaded, may lock |
| Processing | Full Flink (SQL, joins, windows) | SMTs only (limited) |
| Exactly-once | Flink checkpoints | Kafka Connect offsets |
| Target | Any Flink sink (Iceberg, JDBC, Kafka, ES) | Kafka topics (then downstream) |
| Latency | Sub-second | Sub-second |
| Scalability | Scale Flink parallelism | Single task per table partition |
| Complexity | More moving parts (Flink cluster) | Simpler (Kafka Connect) |
| Schema evolution | Via Flink SQL DDL | Schema Registry + history topic |
| Community | Growing | Mature, large ecosystem |

**When to use which:**
- **Debezium**: CDC → Kafka → multiple consumers (pub/sub pattern)
- **Flink CDC**: CDC → complex processing → specific sink (ETL pattern)
- **Both**: Debezium → Kafka → Flink (decoupled, replayable)

---

## 5. Airbyte Deep Dive

### Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                       Airbyte Platform                             │
│                                                                    │
│  ┌──────────┐    ┌───────────────────────────────────────────┐   │
│  │  Web UI  │    │           Airbyte Server                   │   │
│  │          │───▶│  ┌──────────┐  ┌──────────┐  ┌────────┐  │   │
│  └──────────┘    │  │Scheduler │  │Config API│  │  Cron  │  │   │
│                  │  └──────────┘  └──────────┘  └────────┘  │   │
│  ┌──────────┐    └───────────────────┬───────────────────────┘   │
│  │Config DB │                        │                            │
│  │(Postgres)│                        ▼                            │
│  └──────────┘    ┌───────────────────────────────────────────┐   │
│                  │              Worker Pool                    │   │
│  ┌──────────┐    │  ┌─────────────────────────────────────┐  │   │
│  │  Logs    │    │  │         Sync Job (Pod/Container)     │  │   │
│  │ (S3/Min.)│    │  │  ┌──────────┐  ┌────┐  ┌────────┐  │  │   │
│  └──────────┘    │  │  │  Source  │─▶│Norm│─▶│  Dest  │  │  │   │
│                  │  │  │Connector │  │    │  │Connect.│  │  │   │
│                  │  │  └──────────┘  └────┘  └────────┘  │  │   │
│                  │  └─────────────────────────────────────┘  │   │
│                  └───────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────┘
```

### Airbyte Protocol (Core)

```python
# AirbyteMessage types
class AirbyteMessage:
    type: str  # RECORD, STATE, LOG, CATALOG, SPEC, CONNECTION_STATUS, CONTROL
    
# RECORD message
{
  "type": "RECORD",
  "record": {
    "stream": "orders",
    "data": {"id": 1, "amount": 99.99, "status": "shipped"},
    "emitted_at": 1704067200000,
    "namespace": "public"
  }
}

# STATE message (for incremental sync checkpointing)
{
  "type": "STATE",
  "state": {
    "type": "STREAM",
    "stream": {
      "stream_descriptor": {"name": "orders", "namespace": "public"},
      "stream_state": {"cursor_field": "updated_at", "cursor": "2024-01-01T00:00:00Z"}
    }
  }
}

# CATALOG (discovered schema)
{
  "type": "CATALOG",
  "catalog": {
    "streams": [{
      "name": "orders",
      "namespace": "public",
      "json_schema": {"properties": {"id": {"type": "integer"}, ...}},
      "supported_sync_modes": ["full_refresh", "incremental"],
      "source_defined_cursor": true,
      "default_cursor_field": ["updated_at"],
      "source_defined_primary_key": [["id"]]
    }]
  }
}
```

### Sync Modes

| Mode | Source Reads | Destination Writes | Use Case |
|------|-------------|-------------------|----------|
| Full Refresh \| Overwrite | All records | Drop + recreate | Small tables, no cursor |
| Full Refresh \| Append | All records | Append (snapshot versioning) | Audit/history of snapshots |
| Incremental \| Append | New/changed records (cursor) | Append only | Event logs, append-only |
| Incremental \| Dedup | New/changed records (cursor) | Upsert (dedup by PK) | Mutable source tables |

### Building Custom Connectors (CDK)

```python
# Airbyte CDK - Custom source connector
from airbyte_cdk.sources import AbstractSource
from airbyte_cdk.sources.streams import Stream
from airbyte_cdk.sources.streams.http import HttpStream

class OrdersStream(HttpStream):
    url_base = "https://api.example.com/v1/"
    primary_key = "id"
    cursor_field = "updated_at"
    
    def path(self, **kwargs) -> str:
        return "orders"
    
    def request_params(self, stream_state=None, **kwargs):
        params = {"page_size": 100}
        if stream_state and self.cursor_field in stream_state:
            params["updated_after"] = stream_state[self.cursor_field]
        return params
    
    def parse_response(self, response, **kwargs):
        for record in response.json()["data"]:
            yield record
    
    def get_updated_state(self, current_state, latest_record):
        latest_cursor = latest_record.get(self.cursor_field, "")
        current_cursor = current_state.get(self.cursor_field, "")
        return {self.cursor_field: max(latest_cursor, current_cursor)}

class MySource(AbstractSource):
    def check_connection(self, logger, config):
        # Verify connection works
        return True, None
    
    def streams(self, config):
        return [OrdersStream(authenticator=self._get_auth(config))]
```

### Airbyte on K8s (Helm)

```yaml
# values.yaml for airbyte helm chart
global:
  storageClass: "gp3"
  
webapp:
  replicaCount: 2
  resources:
    requests:
      cpu: "500m"
      memory: "1Gi"

server:
  replicaCount: 2
  resources:
    requests:
      cpu: "1"
      memory: "2Gi"

worker:
  replicaCount: 4  # Parallel sync capacity
  resources:
    requests:
      cpu: "2"
      memory: "4Gi"
  extraEnv:
    - name: MAX_SYNC_WORKERS
      value: "8"
    - name: SYNC_JOB_MAX_TIMEOUT_DAYS
      value: "3"

# Use separate pods for source/destination (K8s)
airbyte-bootloader:
  enabled: true

postgresql:
  enabled: true
  persistence:
    size: 50Gi

minio:  # For logs storage
  enabled: true
  persistence:
    size: 100Gi
```

### Airbyte vs Fivetran vs Custom

| Dimension | Airbyte | Fivetran | Custom Pipeline |
|-----------|---------|----------|-----------------|
| Cost | Free (self-hosted) / Cloud pricing | Per-MAR pricing (expensive at scale) | Engineering time |
| Connectors | 300+ (varying quality) | 200+ (high quality, SLA-backed) | Build what you need |
| Maintenance | Self-managed infra (K8s) | Zero ops | Full ownership |
| Customization | CDK for custom sources | Limited transforms | Full control |
| Reliability | Connector-dependent | Enterprise SLA | Your responsibility |
| Schema handling | Auto-detect, propagate | Auto-detect, propagate | Manual |
| Best for | Mid-size, cost-sensitive, tech-capable | Enterprise, budget available, ops-averse | Unique sources, extreme scale |

---

## 6. Meltano & Singer

### Singer Protocol

```
┌─────────────┐    stdout (JSON lines)    ┌─────────────┐
│     Tap     │ ───────────────────────▶  │   Target    │
│ (Source)    │                            │ (Dest)      │
│             │  RECORD, STATE, SCHEMA     │             │
└─────────────┘    messages                └─────────────┘
       │                                          │
       ▼                                          ▼
  catalog.json                              state.json
  (discovered schema)                       (bookmark for incremental)
```

### Meltano Project Structure

```yaml
# meltano.yml
version: 1
project_id: my-data-platform

plugins:
  extractors:
    - name: tap-postgres
      variant: meltanolabs
      pip_url: meltanolabs-tap-postgres
      config:
        host: pg.prod.internal
        port: 5432
        user: meltano
        database: production
        filter_schemas: [public, inventory]
        default_replication_method: INCREMENTAL
        
  loaders:
    - name: target-s3-parquet
      variant: crowemi
      pip_url: crowemi-target-s3-parquet
      config:
        aws_access_key_id: ${AWS_ACCESS_KEY_ID}
        aws_secret_access_key: ${AWS_SECRET_ACCESS_KEY}
        s3_bucket: data-lake-raw
        s3_key_prefix: meltano/postgres/
        format_type: parquet
        compression: snappy

  utilities:
    - name: dbt-postgres
      variant: dbt-labs
      pip_url: dbt-core dbt-postgres

schedules:
  - name: postgres-to-s3-daily
    extractor: tap-postgres
    loader: target-s3-parquet
    transform: skip
    interval: "@daily"
    start_date: "2024-01-01"

environments:
  - name: dev
  - name: staging
  - name: production
```

### When to Use Meltano vs Airbyte

| Dimension | Meltano | Airbyte |
|-----------|---------|---------|
| Philosophy | CLI-first, Git-native, dbt-integrated | UI-first, platform approach |
| Config | YAML in repo (GitOps-friendly) | Database (UI-configured) |
| Deployment | Lightweight (pip install) | Heavy (K8s/Docker Compose) |
| Best for | dbt-centric teams, simple EL | Complex pipelines, non-technical users |
| Connector quality | Variable (Singer ecosystem) | Generally higher (dedicated QA) |

---

## 7. Integration Patterns at Scale

### Fan-In Ingestion (100s of Sources → Lake)

```
┌───────┐  ┌───────┐  ┌───────┐  ┌───────┐
│MySQL 1│  │MySQL 2│  │PG 1   │  │API 1  │  ... (hundreds)
└───┬───┘  └───┬───┘  └───┬───┘  └───┬───┘
    │          │          │          │
    ▼          ▼          ▼          ▼
┌──────────────────────────────────────────┐
│         CDC / EL Layer                    │
│  (Debezium / DMS / Airbyte fleet)        │
└──────────────────────┬───────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────┐
│            Apache Kafka                   │
│  (Schema Registry + Partitioned topics)  │
└──────────────────────┬───────────────────┘
                       │
            ┌──────────┼──────────┐
            ▼          ▼          ▼
    ┌──────────┐ ┌──────────┐ ┌──────────┐
    │S3 (Raw)  │ │Real-time │ │Search    │
    │Iceberg   │ │Analytics │ │(ES/OS)   │
    └──────────┘ └──────────┘ └──────────┘
```

### Idempotent Ingestion Pattern

```python
# Idempotent write to S3/Iceberg using deterministic file naming
def write_batch_idempotent(records, source_table, batch_id):
    """
    Deterministic file path ensures re-processing same batch
    overwrites same file (idempotent).
    """
    # Deterministic path from batch metadata
    partition = records[0]['_partition_date']
    file_path = f"s3://lake/raw/{source_table}/dt={partition}/batch_{batch_id}.parquet"
    
    # Write (overwrites if exists = idempotent)
    df = spark.createDataFrame(records)
    df.write.mode("overwrite").parquet(file_path)
    
    # Alternative: Iceberg with merge (dedup by PK)
    df.createOrReplaceTempView("incoming")
    spark.sql(f"""
        MERGE INTO iceberg_catalog.raw.{source_table} t
        USING incoming s
        ON t.id = s.id
        WHEN MATCHED AND s._op = 'D' THEN DELETE
        WHEN MATCHED THEN UPDATE SET *
        WHEN NOT MATCHED AND s._op != 'D' THEN INSERT *
    """)
```

### Small File Problem from CDC

```
Problem: 
  CDC produces many small files (one per flush interval)
  e.g., 1 file per minute × 1440 minutes = 1440 files/day per table

Solutions:
  1. Increase buffer/flush interval (trade-off: latency)
  2. Compaction job (periodic):
     - Spark: df.coalesce(target_files).write.parquet(path)
     - Iceberg: CALL catalog.system.rewrite_data_files(table => 'db.table')
     - Delta: OPTIMIZE table WHERE date = '2024-01-15'
  3. Iceberg bin-pack:
     Actions.forTable(table)
       .rewriteDataFiles()
       .option("target-file-size-bytes", "536870912")  // 512MB
       .execute()
  4. Streaming micro-batch with larger intervals:
     Flink sink: 'sink.rolling-policy.file-size' = '256MB'
                 'sink.rolling-policy.rollover-interval' = '15min'
```

### Exactly-Once Delivery to S3

```
Challenge: S3 doesn't support transactions

Pattern 1: Write-Ahead + Rename
  1. Write to staging prefix: s3://bucket/staging/{job_id}/file.parquet
  2. On commit: copy to final location
  3. Cleanup staging on failure
  
Pattern 2: Iceberg/Delta Transactions
  1. Write data files to data/ directory
  2. Commit metadata atomically (manifest/delta log)
  3. Uncommitted data files = garbage (cleaned by expireSnapshots)

Pattern 3: Flink + FileSink (Two-Phase Commit)
  1. In-progress files: .part-{subtask}-{count}.inprogress
  2. On checkpoint: rename to pending
  3. On checkpoint confirmation: rename to committed
  4. Recovery: rollback pending files
```

---

## 8. Decision Framework

### Comparison Matrix

| Dimension | Debezium | AWS DMS | Flink CDC | Airbyte |
|-----------|----------|---------|-----------|---------|
| **Type** | Log-based CDC | Log-based CDC + full load | Log-based CDC | EL(T) platform |
| **Infrastructure** | Kafka Connect + Kafka | Managed service | Flink cluster | Self-hosted / Cloud |
| **Sources** | 15+ databases | 20+ databases | 6 databases | 300+ (DB + SaaS + API) |
| **Targets** | Kafka topics | DB, S3, Kinesis, Redshift | Any Flink sink | DB, warehouse, lake |
| **Latency** | Sub-second | Seconds | Sub-second | Minutes (batch-based) |
| **Exactly-once** | With Kafka transactions | At-least-once | Flink checkpoints | At-least-once + dedup |
| **Snapshot** | Sequential / Incremental | Parallel full load | Parallel chunk-based | Full refresh / cursor |
| **Transforms** | SMTs (limited) | Table mappings + rules | Full Flink (SQL, joins) | dbt / custom |
| **Schema evolution** | Schema Registry | Limited (manual DDL) | Flink SQL DDL | Auto-detect |
| **Cost** | Kafka infra | Per-instance-hour | Flink infra | Free (OSS) / per-row |
| **Ops complexity** | Medium | Low (managed) | High | Medium |
| **Best for** | CDC → Kafka ecosystem | DB migration, CDC → AWS | Complex CDC processing | SaaS/API → warehouse |

### Decision Tree

```
Need CDC from databases?
├── Yes → Need complex transformations (joins, windows, aggregations)?
│   ├── Yes → Flink CDC
│   └── No → Need data in Kafka for multiple consumers?
│       ├── Yes → Debezium
│       └── No → On AWS? Budget for managed?
│           ├── Yes → AWS DMS
│           └── No → Debezium (simpler, more control)
│
Need SaaS/API data integration?
├── Yes → Airbyte or Fivetran
│
Need both CDC + SaaS in one platform?
├── Yes → Airbyte (has CDC connectors too, but less robust than Debezium)
│
Hybrid recommendation for large platforms:
  • Debezium → Kafka (for all database CDC, real-time consumers)
  • AWS DMS (for one-time migrations + S3 CDC landing)
  • Airbyte (for SaaS sources → warehouse)
  • Flink CDC (for specific complex ETL from DB)
```

---

## 9. Production Checklist

### Debezium
- [ ] Heartbeat configured (prevent WAL/binlog bloat)
- [ ] Signal table created (for incremental snapshots)
- [ ] Schema history topic with sufficient retention
- [ ] Monitoring: lag, connector status, slot size (PG)
- [ ] Alert: slot lag > 1GB, connector FAILED state
- [ ] Dead letter topic configured for poison messages
- [ ] Connector restart policy (exponential backoff)
- [ ] Schema Registry with appropriate compatibility mode
- [ ] Source DB user with minimal required privileges
- [ ] Test: connector failover and recovery
- [ ] Test: source DB failover (GTID/slot behavior)

### AWS DMS
- [ ] Right-sized replication instance (monitor CPU/memory)
- [ ] Multi-AZ for production workloads
- [ ] Validation enabled for critical tables
- [ ] LOB handling mode appropriate for data sizes
- [ ] Table mappings and transformation rules tested
- [ ] CloudWatch alarms: CDCLatencySource, FreeMemory, SwapUsage
- [ ] Pre-migration assessment completed
- [ ] Supplemental logging enabled (Oracle)
- [ ] Replication slot monitoring (PostgreSQL source)
- [ ] Test: instance failover behavior

### Flink CDC
- [ ] Checkpoint interval configured (balance latency vs overhead)
- [ ] State backend sized appropriately (RocksDB for large state)
- [ ] Parallelism matches source table partition count
- [ ] Server-id range allocated (MySQL, avoids conflicts)
- [ ] Replication slot named and monitored (PostgreSQL)
- [ ] Savepoint taken before upgrades
- [ ] Metrics: checkpoint duration, backpressure, record lag
- [ ] Exactly-once sink configured (2PC or idempotent)
- [ ] Test: checkpoint recovery after failure
- [ ] Test: schema change handling

### Airbyte
- [ ] Worker pool sized for connection parallelism
- [ ] Sync timeout configured per connection
- [ ] Alerting on sync failures (webhook / email)
- [ ] State management: verify incremental sync cursors
- [ ] Log storage (S3/MinIO) with retention policy
- [ ] Schema change detection notifications enabled
- [ ] Resource limits per sync (memory, CPU)
- [ ] Test: large table sync (memory pressure)
- [ ] Test: source unavailability and retry behavior
- [ ] Backup: config DB (PostgreSQL) regular snapshots
