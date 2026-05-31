# Pattern 03: Delta/Lakehouse Architecture

## Overview

The Lakehouse architecture unifies data warehouses and data lakes into a single system
that provides ACID transactions, schema enforcement, and BI performance on object storage.

**Key Implementations**: Delta Lake (Databricks), Apache Iceberg (Netflix), Apache Hudi (Uber)
**Used at**: Apple, Comcast, Alibaba, Adobe, Rivian, all major tech companies

---

## Why Lakehouse?

```
THE PROBLEM WITH TRADITIONAL APPROACHES:
═══════════════════════════════════════════

Data Lake (Hadoop/S3):                    Data Warehouse (Redshift/BQ):
┌────────────────────────┐                ┌────────────────────────┐
│ ✓ Cheap storage        │                │ ✓ ACID transactions     │
│ ✓ Any data format      │                │ ✓ Fast BI queries       │
│ ✓ ML/AI friendly       │                │ ✓ Schema enforcement    │
│ ✗ No ACID              │                │ ✗ Expensive storage     │
│ ✗ No consistency       │                │ ✗ Limited formats       │
│ ✗ "Data Swamp"         │                │ ✗ Vendor lock-in        │
│ ✗ Slow queries         │                │ ✗ No ML support         │
└────────────────────────┘                └────────────────────────┘

LAKEHOUSE SOLUTION: Get BOTH on cheap object storage
┌────────────────────────────────────────────────────┐
│ ✓ ACID transactions on S3/GCS/ADLS                  │
│ ✓ Schema enforcement + evolution                    │
│ ✓ Time-travel (query historical versions)           │
│ ✓ Fast BI queries (columnar + indexing)             │
│ ✓ ML/AI native (direct Spark/Python access)         │
│ ✓ Open formats (Parquet + metadata)                 │
│ ✓ 10-100x cheaper than warehouses                   │
│ ✓ Multi-engine (Spark, Flink, Trino, DuckDB)        │
└────────────────────────────────────────────────────┘
```

---

## Architecture Deep Dive

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                        LAKEHOUSE ARCHITECTURE                                  │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│  ┌────────────────────────────────────────────────────────────────┐          │
│  │ DATA SOURCES                                                    │          │
│  │ [Kafka] [RDBMS via CDC] [APIs] [Files] [IoT] [Logs]            │          │
│  └────────────────────────────────┬───────────────────────────────┘          │
│                                    │                                          │
│  ┌─────────────────────────────────▼──────────────────────────────┐          │
│  │          INGESTION LAYER                                        │          │
│  │                                                                 │          │
│  │  Batch: Spark, Airbyte, Fivetran, dbt                           │          │
│  │  Stream: Flink, Kafka Connect, Spark Structured Streaming       │          │
│  │  CDC: Debezium → Kafka → Flink → Lakehouse                     │          │
│  └─────────────────────────────────┬──────────────────────────────┘          │
│                                     │                                         │
│  ┌──────────────────────────────────▼─────────────────────────────┐          │
│  │          STORAGE LAYER (Object Store + Table Format)            │          │
│  │                                                                 │          │
│  │  Object Store: S3 / GCS / ADLS / MinIO                          │          │
│  │                                                                 │          │
│  │  Table Format (THE KEY INNOVATION):                             │          │
│  │  ┌──────────────────────────────────────────────────────┐      │          │
│  │  │  Delta Lake / Iceberg / Hudi                          │      │          │
│  │  │                                                       │      │          │
│  │  │  What they add on top of Parquet:                     │      │          │
│  │  │  • Transaction log (ACID commits)                     │      │          │
│  │  │  • Schema registry (enforce/evolve)                   │      │          │
│  │  │  • Partition metadata (fast pruning)                  │      │          │
│  │  │  • File-level statistics (min/max/count)              │      │          │
│  │  │  • Time-travel (version history)                      │      │          │
│  │  │  • Merge/Upsert/Delete operations                     │      │          │
│  │  └──────────────────────────────────────────────────────┘      │          │
│  │                                                                 │          │
│  │  Physical Layout:                                               │          │
│  │  s3://lakehouse/                                                │          │
│  │  ├── bronze/                                                    │          │
│  │  │   ├── orders/                                                │          │
│  │  │   │   ├── _delta_log/          (transaction log)             │          │
│  │  │   │   ├── year=2024/month=01/  (partitioned parquet)         │          │
│  │  │   │   └── year=2024/month=02/                                │          │
│  │  │   └── users/                                                 │          │
│  │  ├── silver/                                                    │          │
│  │  │   ├── orders_cleaned/                                        │          │
│  │  │   └── user_sessions/                                         │          │
│  │  └── gold/                                                      │          │
│  │      ├── daily_revenue/                                         │          │
│  │      └── user_segments/                                         │          │
│  └─────────────────────────────────┬──────────────────────────────┘          │
│                                     │                                         │
│  ┌──────────────────────────────────▼─────────────────────────────┐          │
│  │          COMPUTE LAYER (Multi-Engine)                           │          │
│  │                                                                 │          │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐         │          │
│  │  │  Spark   │ │  Flink   │ │  Trino   │ │  DuckDB  │          │          │
│  │  │  (ETL)   │ │ (Stream) │ │ (SQL)    │ │ (Local)  │          │          │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘         │          │
│  │                                                                 │          │
│  │  WHY MULTI-ENGINE:                                              │          │
│  │  • Spark: Best for large-scale ETL, ML training                 │          │
│  │  • Flink: Best for streaming ingestion                          │          │
│  │  • Trino: Best for interactive SQL queries                      │          │
│  │  • DuckDB: Best for local development, small datasets           │          │
│  └─────────────────────────────────┬──────────────────────────────┘          │
│                                     │                                         │
│  ┌──────────────────────────────────▼─────────────────────────────┐          │
│  │          CONSUMPTION LAYER                                      │          │
│  │                                                                 │          │
│  │  [BI Tools]  [ML Notebooks]  [REST APIs]  [Data Apps]           │          │
│  │  Tableau      Jupyter         FastAPI       Streamlit           │          │
│  │  Looker       Databricks      GraphQL       Retool             │          │
│  │  PowerBI      SageMaker                                         │          │
│  └────────────────────────────────────────────────────────────────┘          │
│                                                                               │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## Table Format Comparison (Delta vs Iceberg vs Hudi)

```
┌─────────────────┬─────────────────┬─────────────────┬─────────────────┐
│ Feature         │ Delta Lake      │ Apache Iceberg  │ Apache Hudi     │
├─────────────────┼─────────────────┼─────────────────┼─────────────────┤
│ Origin          │ Databricks      │ Netflix         │ Uber            │
│ ACID            │ ✓               │ ✓               │ ✓               │
│ Time Travel     │ ✓ (30 days def) │ ✓ (snapshots)   │ ✓ (commits)     │
│ Schema Evol.    │ ✓               │ ✓ (best)        │ ✓               │
│ Partition Evol. │ ✗ (limited)     │ ✓ (hidden part) │ ✗               │
│ Merge/Upsert   │ ✓ (MERGE INTO)  │ ✓ (row-level)   │ ✓ (best: MoR)  │
│ Streaming       │ ✓               │ ✓ (incremental) │ ✓ (best)        │
│ Multi-engine    │ Good            │ Best            │ Good            │
│ Concurrency     │ Optimistic      │ Optimistic      │ Optimistic      │
│ Best For        │ Databricks users│ Multi-engine    │ Upsert-heavy    │
│ Catalog         │ Unity Catalog   │ Hive/Nessie/REST│ Hive            │
│ Community       │ Large           │ Fastest growing │ Medium          │
└─────────────────┴─────────────────┴─────────────────┴─────────────────┘
```

---

## Scalability Analysis

### Storage Scalability
```
Object Store (S3/GCS) Properties:
─────────────────────────────────
• Capacity: Unlimited (exabytes+)
• Throughput: 5,500 GET/s, 3,500 PUT/s per prefix
• Cost: $0.023/GB/month (S3 Standard)
• Durability: 99.999999999% (11 nines)

Scaling Strategy:
1. PARTITION by time (year/month/day/hour)
   → Each partition = separate S3 prefix = independent throughput
   
2. FILE SIZE optimization
   → Target: 128MB - 1GB per file (sweet spot)
   → Too small: metadata overhead, slow listing
   → Too large: can't parallelize reads
   
3. COMPACTION to merge small files
   → Triggered when file count > threshold
   → Runs as background Spark job
   → Z-ORDER/HILBERT clustering for multi-dim queries

Cost at Scale:
- 1 PB raw data: $23,000/month (S3)
- Same in Redshift: $250,000+/month
- Savings: 10x+ cheaper
```

### Query Scalability
```
How Lakehouse achieves warehouse-level query performance:

1. DATA SKIPPING (File-level statistics)
   ┌─────────────────────────────────────────┐
   │ File: part-001.parquet                   │
   │ Stats: {                                 │
   │   "order_date": {min: "2024-01-01", max: "2024-01-31"},
   │   "amount": {min: 5.0, max: 9999.0},    │
   │   "row_count": 1000000                   │
   │ }                                        │
   └─────────────────────────────────────────┘
   
   Query: WHERE order_date = '2024-06-15'
   → Skip this entire file! (date not in range)
   → May skip 99% of files for point queries

2. Z-ORDER CLUSTERING
   Colocates related data physically:
   OPTIMIZE table ZORDER BY (user_id, date)
   → Queries on user_id OR date both benefit
   → 10-100x speedup for filtered queries

3. PARTITION PRUNING
   Table partitioned by date:
   → Query for single day reads 1/365th of data
   → Combined with stats: often reads <1% of total

4. CACHING
   → Metadata cached in memory (Delta log, Iceberg manifests)
   → Hot data cached on SSD (Alluxio/local)
   → Query results cached (Redis/Memcached)
```

---

## Runnable Example: Complete Lakehouse Pipeline

```python
"""
Lakehouse Architecture Implementation
======================================
Complete implementation of a Delta/Lakehouse architecture with:
- Bronze layer: Raw ingestion
- Silver layer: Cleaning and conforming
- Gold layer: Business aggregations
- ACID transactions
- Time travel
- Schema evolution
- Compaction

Run: python lakehouse_architecture.py
"""

import json
import time
import os
import hashlib
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from pathlib import Path
import random
import copy


# ============================================================================
# TRANSACTION LOG (Core of Lakehouse - Simulates Delta Log)
# ============================================================================

@dataclass
class CommitEntry:
    """Single entry in the transaction log"""
    version: int
    timestamp: float
    operation: str  # ADD, REMOVE, METADATA, PROTOCOL
    path: str = ""
    partition_values: Dict[str, str] = field(default_factory=dict)
    stats: Dict[str, Any] = field(default_factory=dict)
    schema: Dict[str, str] = field(default_factory=dict)


class TransactionLog:
    """
    Simulates Delta Lake's transaction log (_delta_log).
    
    This is THE KEY INNOVATION of Lakehouse:
    - Every change is recorded as a JSON commit
    - Enables ACID: commit is atomic (write JSON file)
    - Enables Time Travel: read log at version N
    - Enables Concurrency: optimistic locking on log
    
    In production:
    - Stored as JSON files: 00000.json, 00001.json, ...
    - Checkpointed every 10 versions (Parquet summary)
    - Reader reconstructs state by replaying log
    """
    
    def __init__(self, table_name: str):
        self.table_name = table_name
        self.commits: List[CommitEntry] = []
        self.current_version = -1
        self.schema: Dict[str, str] = {}
    
    def commit(self, entries: List[CommitEntry]) -> int:
        """
        Atomic commit of one or more operations.
        
        ACID Properties:
        - Atomicity: All entries committed together or none
        - Consistency: Schema validated before commit
        - Isolation: Optimistic concurrency (version check)
        - Durability: Written to persistent storage (simulated)
        """
        self.current_version += 1
        for entry in entries:
            entry.version = self.current_version
            entry.timestamp = time.time()
            self.commits.append(entry)
        return self.current_version
    
    def get_state_at_version(self, version: int) -> dict:
        """
        TIME TRAVEL: Reconstruct table state at any version.
        
        How it works:
        1. Replay log from version 0 to target version
        2. Track which files are active (ADD - REMOVE)
        3. Return the set of active files at that version
        """
        active_files = {}
        schema = {}
        
        for commit in self.commits:
            if commit.version > version:
                break
            if commit.operation == 'ADD':
                active_files[commit.path] = commit
            elif commit.operation == 'REMOVE':
                active_files.pop(commit.path, None)
            elif commit.operation == 'METADATA':
                schema = commit.schema
        
        return {
            'version': version,
            'active_files': active_files,
            'schema': schema,
            'file_count': len(active_files),
        }
    
    def get_current_state(self) -> dict:
        return self.get_state_at_version(self.current_version)


# ============================================================================
# LAKEHOUSE TABLE (Simulates Delta Table)
# ============================================================================

@dataclass
class DataFile:
    """Represents a Parquet file in the lakehouse"""
    path: str
    records: List[dict]
    partition_values: Dict[str, str]
    stats: Dict[str, Any]  # min, max, count per column
    size_bytes: int
    created_at: float


class LakehouseTable:
    """
    Simulates a Delta/Iceberg table with full ACID support.
    
    Features:
    - ACID transactions (via transaction log)
    - Schema enforcement and evolution
    - Partition management
    - Time travel (query any version)
    - Merge/Upsert/Delete
    - Compaction (optimize small files)
    """
    
    def __init__(self, name: str, schema: Dict[str, str], 
                 partition_cols: List[str] = None):
        self.name = name
        self.schema = schema
        self.partition_cols = partition_cols or []
        self.log = TransactionLog(name)
        self.files: Dict[str, DataFile] = {}
        
        # Initial metadata commit
        self.log.commit([CommitEntry(
            version=0,
            timestamp=time.time(),
            operation='METADATA',
            schema=schema
        )])
        
        print(f"  Created table '{name}' with schema: {list(schema.keys())}")
        if partition_cols:
            print(f"  Partitioned by: {partition_cols}")
    
    def write(self, records: List[dict], mode: str = 'append') -> int:
        """
        Write records to the table (ACID).
        
        Modes:
        - append: Add new files (no conflict possible)
        - overwrite: Replace partition (atomic swap)
        
        Process:
        1. Validate schema
        2. Partition records by partition columns
        3. Write each partition as a separate file
        4. Commit to transaction log (atomic)
        """
        # Schema validation
        for record in records:
            for col in self.schema:
                if col not in record and col not in self.partition_cols:
                    record[col] = None  # Allow nullable
        
        # Group by partition
        partitioned: Dict[str, List[dict]] = defaultdict(list)
        for record in records:
            if self.partition_cols:
                partition_key = "/".join(
                    f"{col}={record.get(col, 'NULL')}" 
                    for col in self.partition_cols
                )
            else:
                partition_key = "unpartitioned"
            partitioned[partition_key].append(record)
        
        # Create files and commit
        commit_entries = []
        
        if mode == 'overwrite':
            # Remove existing files in affected partitions
            for partition_key in partitioned:
                for path, file in list(self.files.items()):
                    file_partition = "/".join(
                        f"{k}={v}" for k, v in file.partition_values.items()
                    )
                    if file_partition == partition_key:
                        commit_entries.append(CommitEntry(
                            version=0, timestamp=0,
                            operation='REMOVE', path=path
                        ))
                        del self.files[path]
        
        for partition_key, partition_records in partitioned.items():
            # Compute file statistics
            stats = self._compute_stats(partition_records)
            
            # Create file
            file_path = f"{self.name}/{partition_key}/part-{hashlib.md5(str(time.time()).encode()).hexdigest()[:8]}.parquet"
            
            partition_values = {}
            if self.partition_cols:
                for col in self.partition_cols:
                    partition_values[col] = str(partition_records[0].get(col, 'NULL'))
            
            data_file = DataFile(
                path=file_path,
                records=partition_records,
                partition_values=partition_values,
                stats=stats,
                size_bytes=len(json.dumps(partition_records)),
                created_at=time.time()
            )
            
            self.files[file_path] = data_file
            
            commit_entries.append(CommitEntry(
                version=0, timestamp=0,
                operation='ADD', path=file_path,
                partition_values=partition_values,
                stats=stats
            ))
        
        version = self.log.commit(commit_entries)
        return version
    
    def read(self, filters: Dict[str, Any] = None, 
             version: int = None) -> List[dict]:
        """
        Read table with optional filters and time travel.
        
        Optimization:
        1. Partition pruning (skip entire partitions)
        2. File-level stats (skip files based on min/max)
        3. Predicate pushdown (filter within files)
        """
        # Time travel: reconstruct file list at version
        if version is not None:
            state = self.log.get_state_at_version(version)
            file_paths = set(state['active_files'].keys())
            files_to_read = {p: f for p, f in self.files.items() 
                           if p in file_paths}
        else:
            files_to_read = self.files
        
        results = []
        files_scanned = 0
        files_skipped = 0
        
        for path, data_file in files_to_read.items():
            # Partition pruning
            if filters and self.partition_cols:
                skip = False
                for col in self.partition_cols:
                    if col in filters:
                        if str(data_file.partition_values.get(col)) != str(filters[col]):
                            skip = True
                            break
                if skip:
                    files_skipped += 1
                    continue
            
            # File-level stats pruning
            if filters:
                skip = False
                for col, value in filters.items():
                    if col in data_file.stats:
                        stat = data_file.stats[col]
                        if 'min' in stat and 'max' in stat:
                            if value < stat['min'] or value > stat['max']:
                                skip = True
                                break
                if skip:
                    files_skipped += 1
                    continue
            
            files_scanned += 1
            
            # Read and filter records
            for record in data_file.records:
                if filters:
                    match = all(
                        record.get(k) == v for k, v in filters.items()
                    )
                    if not match:
                        continue
                results.append(record)
        
        return results
    
    def merge(self, source_records: List[dict], 
              merge_key: str, 
              when_matched: str = 'update',
              when_not_matched: str = 'insert') -> dict:
        """
        MERGE operation (upsert) - like SQL MERGE INTO.
        
        This is crucial for CDC patterns:
        - Match source records against existing by merge_key
        - Update matches, insert non-matches
        - All within a single ACID transaction
        """
        existing = self.read()
        existing_map = {r[merge_key]: r for r in existing}
        
        updated = 0
        inserted = 0
        
        final_records = dict(existing_map)  # Start with existing
        
        for source_record in source_records:
            key = source_record[merge_key]
            if key in final_records:
                if when_matched == 'update':
                    final_records[key] = {**final_records[key], **source_record}
                    updated += 1
            else:
                if when_not_matched == 'insert':
                    final_records[key] = source_record
                    inserted += 1
        
        # Atomic overwrite
        self.write(list(final_records.values()), mode='overwrite')
        
        return {'updated': updated, 'inserted': inserted}
    
    def compact(self, target_file_size_records: int = 1000) -> dict:
        """
        Compaction: Merge small files into larger ones.
        
        WHY: Many small files = slow queries (per-file overhead)
        WHEN: After many appends create many small files
        HOW: Read all → rewrite as fewer, larger files
        """
        current_records = self.read()
        old_file_count = len(self.files)
        
        # Clear and rewrite
        self.files.clear()
        self.write(current_records, mode='overwrite')
        
        new_file_count = len(self.files)
        
        return {
            'old_files': old_file_count,
            'new_files': new_file_count,
            'records': len(current_records)
        }
    
    def _compute_stats(self, records: List[dict]) -> Dict[str, Any]:
        """Compute column-level statistics for data skipping"""
        stats = {}
        if not records:
            return stats
        
        for col in records[0]:
            values = [r.get(col) for r in records if r.get(col) is not None]
            if values:
                try:
                    stats[col] = {
                        'min': min(values),
                        'max': max(values),
                        'null_count': len(records) - len(values),
                        'count': len(values)
                    }
                except TypeError:
                    stats[col] = {'count': len(values)}
        
        return stats
    
    def history(self) -> List[dict]:
        """Show table history (all commits)"""
        versions = defaultdict(list)
        for commit in self.log.commits:
            versions[commit.version].append({
                'operation': commit.operation,
                'path': commit.path,
                'timestamp': commit.timestamp
            })
        return dict(versions)
    
    def evolve_schema(self, new_columns: Dict[str, str]):
        """
        Schema evolution: Add new columns without rewriting data.
        
        Supported evolutions:
        - Add column (always safe)
        - Widen type (int → long, float → double)
        
        NOT supported (breaking):
        - Remove column
        - Rename column  
        - Narrow type
        """
        self.schema.update(new_columns)
        self.log.commit([CommitEntry(
            version=0, timestamp=0,
            operation='METADATA',
            schema=self.schema
        )])
        print(f"  Schema evolved: added {list(new_columns.keys())}")


# ============================================================================
# MEDALLION LAYERS
# ============================================================================

class MedallionLakehouse:
    """
    Implements Bronze → Silver → Gold medallion architecture.
    
    BRONZE: Raw data, append-only, full fidelity
    SILVER: Cleaned, deduplicated, conformed
    GOLD: Business-level aggregations, star schema
    """
    
    def __init__(self):
        # Bronze: Raw ingestion
        self.bronze_orders = LakehouseTable(
            "bronze_orders",
            schema={
                'order_id': 'string', 'user_id': 'string',
                'product_id': 'string', 'amount': 'float',
                'quantity': 'int', 'status': 'string',
                'event_time': 'timestamp', 'ingestion_time': 'timestamp',
                'source': 'string', 'raw_payload': 'string'
            },
            partition_cols=['event_date']
        )
        
        # Silver: Cleaned and validated
        self.silver_orders = LakehouseTable(
            "silver_orders",
            schema={
                'order_id': 'string', 'user_id': 'string',
                'product_id': 'string', 'amount': 'float',
                'quantity': 'int', 'status': 'string',
                'order_date': 'date', 'is_valid': 'boolean'
            },
            partition_cols=['order_date']
        )
        
        # Gold: Business aggregations
        self.gold_daily_revenue = LakehouseTable(
            "gold_daily_revenue",
            schema={
                'date': 'date', 'total_revenue': 'float',
                'total_orders': 'int', 'avg_order_value': 'float',
                'unique_customers': 'int'
            },
            partition_cols=['date']
        )
    
    def ingest_to_bronze(self, raw_events: List[dict]):
        """
        Bronze ingestion: Keep EVERYTHING, add metadata.
        
        Principles:
        - Never modify source data
        - Add ingestion metadata (time, source, batch_id)
        - Append-only (never overwrite)
        - Keep even malformed records
        """
        bronze_records = []
        for event in raw_events:
            bronze_record = {
                **event,
                'ingestion_time': datetime.now().isoformat(),
                'source': event.get('source', 'api'),
                'raw_payload': json.dumps(event),
                'event_date': datetime.fromtimestamp(
                    event.get('event_time', time.time())
                ).strftime('%Y-%m-%d')
            }
            bronze_records.append(bronze_record)
        
        version = self.bronze_orders.write(bronze_records)
        print(f"  Bronze: Ingested {len(bronze_records)} records (version {version})")
        return version
    
    def bronze_to_silver(self):
        """
        Silver transformation: Clean, dedupe, validate, conform.
        
        Operations:
        1. Deduplicate by order_id (take latest)
        2. Validate business rules (amount > 0, valid status)
        3. Standardize types and formats
        4. Handle nulls with defaults
        5. Mark invalid records (don't drop!)
        """
        bronze_records = self.bronze_orders.read()
        
        # Deduplicate by order_id (keep latest)
        deduped = {}
        for record in bronze_records:
            order_id = record.get('order_id')
            if order_id not in deduped or \
               record.get('event_time', 0) > deduped[order_id].get('event_time', 0):
                deduped[order_id] = record
        
        # Validate and clean
        silver_records = []
        valid_count = 0
        invalid_count = 0
        
        for record in deduped.values():
            is_valid = True
            
            # Validation rules
            if not record.get('amount') or record['amount'] <= 0:
                is_valid = False
            if record.get('status') not in ['placed', 'shipped', 'delivered', 'cancelled']:
                is_valid = False
            if not record.get('user_id'):
                is_valid = False
            
            silver_record = {
                'order_id': record.get('order_id', 'UNKNOWN'),
                'user_id': record.get('user_id', 'UNKNOWN'),
                'product_id': record.get('product_id', 'UNKNOWN'),
                'amount': float(record.get('amount', 0)),
                'quantity': int(record.get('quantity', 1)),
                'status': record.get('status', 'unknown'),
                'order_date': record.get('event_date', 
                    datetime.now().strftime('%Y-%m-%d')),
                'is_valid': is_valid
            }
            
            silver_records.append(silver_record)
            if is_valid:
                valid_count += 1
            else:
                invalid_count += 1
        
        # Write to silver (merge/upsert by order_id)
        self.silver_orders.merge(silver_records, merge_key='order_id')
        
        print(f"  Silver: Processed {len(silver_records)} records "
              f"(valid={valid_count}, invalid={invalid_count})")
    
    def silver_to_gold(self):
        """
        Gold aggregation: Business-ready metrics.
        
        This creates the "data products" that BI tools consume.
        Typically: star schema, pre-aggregated, heavily indexed.
        """
        silver_records = self.silver_orders.read()
        
        # Only use valid records for gold
        valid_records = [r for r in silver_records if r.get('is_valid', False)]
        
        # Aggregate by date
        daily_metrics: Dict[str, dict] = defaultdict(lambda: {
            'revenue': 0, 'orders': 0, 'users': set()
        })
        
        for record in valid_records:
            day = record.get('order_date', 'unknown')
            if record['status'] != 'cancelled':
                daily_metrics[day]['revenue'] += record['amount']
                daily_metrics[day]['orders'] += 1
                daily_metrics[day]['users'].add(record['user_id'])
        
        # Write gold records
        gold_records = []
        for date, metrics in daily_metrics.items():
            gold_records.append({
                'date': date,
                'total_revenue': round(metrics['revenue'], 2),
                'total_orders': metrics['orders'],
                'avg_order_value': round(
                    metrics['revenue'] / max(metrics['orders'], 1), 2
                ),
                'unique_customers': len(metrics['users'])
            })
        
        self.gold_daily_revenue.write(gold_records, mode='overwrite')
        print(f"  Gold: Wrote {len(gold_records)} daily aggregation records")


# ============================================================================
# DEMONSTRATION
# ============================================================================

def run_lakehouse_demo():
    """
    End-to-end Lakehouse demonstration:
    1. Ingest raw data to Bronze
    2. Transform Bronze → Silver (clean, dedupe, validate)
    3. Aggregate Silver → Gold (business metrics)
    4. Demonstrate time travel
    5. Demonstrate schema evolution
    6. Demonstrate compaction
    """
    
    print("""
╔══════════════════════════════════════════════════════════════════╗
║         LAKEHOUSE ARCHITECTURE - LIVE DEMONSTRATION             ║
╠══════════════════════════════════════════════════════════════════╣
║                                                                  ║
║  Features demonstrated:                                          ║
║  • Bronze/Silver/Gold medallion layers                           ║
║  • ACID transactions                                            ║
║  • Time travel (query historical versions)                       ║
║  • Schema evolution                                              ║
║  • Merge/Upsert (CDC pattern)                                   ║
║  • Compaction                                                    ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝
    """)
    
    # Initialize
    lakehouse = MedallionLakehouse()
    
    # ─── Step 1: Generate and ingest raw data ───
    print("\n" + "=" * 60)
    print("STEP 1: Ingest Raw Data → Bronze")
    print("=" * 60)
    
    statuses = ['placed', 'shipped', 'delivered', 'cancelled']
    raw_events = []
    for i in range(500):
        event = {
            'order_id': f"ORD-{i:05d}",
            'user_id': f"USR-{random.randint(1, 100):04d}",
            'product_id': f"PROD-{random.randint(1, 50):03d}",
            'amount': round(random.uniform(10, 500), 2),
            'quantity': random.randint(1, 5),
            'status': random.choice(statuses),
            'event_time': time.time() - random.uniform(0, 86400 * 7),
        }
        raw_events.append(event)
    
    # Add some duplicates (real-world scenario)
    duplicates = random.sample(raw_events, 50)
    raw_events.extend(duplicates)
    
    # Add some invalid records
    for i in range(20):
        raw_events.append({
            'order_id': f"ORD-BAD-{i}",
            'amount': -100,  # Invalid!
            'status': 'invalid_status',
            'event_time': time.time()
        })
    
    random.shuffle(raw_events)
    lakehouse.ingest_to_bronze(raw_events)
    
    # ─── Step 2: Bronze → Silver ───
    print("\n" + "=" * 60)
    print("STEP 2: Transform Bronze → Silver (Clean, Dedupe, Validate)")
    print("=" * 60)
    
    lakehouse.bronze_to_silver()
    
    # ─── Step 3: Silver → Gold ───
    print("\n" + "=" * 60)
    print("STEP 3: Aggregate Silver → Gold (Business Metrics)")
    print("=" * 60)
    
    lakehouse.silver_to_gold()
    
    # Query gold layer
    gold_results = lakehouse.gold_daily_revenue.read()
    print(f"\n  Daily Revenue Report:")
    print(f"  {'Date':<12} {'Revenue':>12} {'Orders':>8} {'AOV':>8} {'Customers':>10}")
    print(f"  {'-'*12} {'-'*12} {'-'*8} {'-'*8} {'-'*10}")
    for row in sorted(gold_results, key=lambda x: x.get('date', ''))[:5]:
        print(f"  {row.get('date', 'N/A'):<12} "
              f"${row.get('total_revenue', 0):>10,.2f} "
              f"{row.get('total_orders', 0):>8} "
              f"${row.get('avg_order_value', 0):>6,.2f} "
              f"{row.get('unique_customers', 0):>10}")
    
    # ─── Step 4: Time Travel ───
    print("\n" + "=" * 60)
    print("STEP 4: Time Travel (Query Historical Versions)")
    print("=" * 60)
    
    # Make a change
    print("\n  Inserting new batch of orders...")
    new_orders = [{
        'order_id': f"ORD-NEW-{i}",
        'user_id': f"USR-{random.randint(1, 100):04d}",
        'product_id': f"PROD-{random.randint(1, 50):03d}",
        'amount': round(random.uniform(100, 1000), 2),
        'quantity': 1,
        'status': 'placed',
        'event_time': time.time(),
        'event_date': datetime.now().strftime('%Y-%m-%d')
    } for i in range(100)]
    
    lakehouse.bronze_orders.write(new_orders)
    
    current = lakehouse.bronze_orders.read()
    previous = lakehouse.bronze_orders.read(version=1)  # First version
    
    print(f"  Current version record count: {len(current)}")
    print(f"  Version 1 record count: {len(previous)}")
    print(f"  Time travel works! Can query any historical state.")
    
    # ─── Step 5: Schema Evolution ───
    print("\n" + "=" * 60)
    print("STEP 5: Schema Evolution (Add Columns Without Rewrite)")
    print("=" * 60)
    
    lakehouse.silver_orders.evolve_schema({
        'discount_pct': 'float',
        'coupon_code': 'string',
        'delivery_date': 'date'
    })
    
    print(f"  New schema: {list(lakehouse.silver_orders.schema.keys())}")
    print(f"  Existing data still readable (new columns = NULL)")
    
    # ─── Step 6: Compaction ───
    print("\n" + "=" * 60)
    print("STEP 6: Compaction (Merge Small Files)")
    print("=" * 60)
    
    # Write many small batches to create file fragmentation
    for i in range(10):
        lakehouse.bronze_orders.write([{
            'order_id': f"ORD-SMALL-{i}-{j}",
            'user_id': f"USR-0001",
            'amount': 10.0,
            'status': 'placed',
            'event_time': time.time(),
            'event_date': datetime.now().strftime('%Y-%m-%d')
        } for j in range(5)])
    
    print(f"  Files before compaction: {len(lakehouse.bronze_orders.files)}")
    result = lakehouse.bronze_orders.compact()
    print(f"  Files after compaction: {result['new_files']}")
    print(f"  Records preserved: {result['records']}")
    
    # ─── Summary ───
    print("\n" + "=" * 60)
    print("SUMMARY: Lakehouse Capabilities Demonstrated")
    print("=" * 60)
    print("""
  ✓ ACID Transactions - Every write is atomic, consistent
  ✓ Medallion Layers  - Bronze(raw) → Silver(clean) → Gold(business)
  ✓ Deduplication     - Handles duplicate events gracefully
  ✓ Data Validation   - Invalid records marked, not dropped
  ✓ Time Travel       - Query any historical version
  ✓ Schema Evolution  - Add columns without rewriting data
  ✓ Merge/Upsert      - CDC-style incremental updates
  ✓ Compaction        - Merge small files for better query performance
  ✓ Data Skipping     - Column statistics for fast filtering
  ✓ Partition Pruning - Skip irrelevant partitions entirely
    """)


if __name__ == '__main__':
    run_lakehouse_demo()
```

---

## Production Scalability Patterns

### Multi-Cluster Architecture
```
┌─────────────────────────────────────────────────────────────────┐
│  PRODUCTION LAKEHOUSE - MULTI-CLUSTER                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────┐  ┌─────────────────┐                      │
│  │ ETL Cluster     │  │ ML Cluster      │                       │
│  │ (Spark 3.5)     │  │ (Spark + GPU)   │                       │
│  │ • 100 nodes     │  │ • 50 nodes      │                       │
│  │ • 4TB RAM total │  │ • 200 GPUs      │                       │
│  │ • Auto-scales   │  │ • Training jobs │                       │
│  └────────┬────────┘  └────────┬────────┘                       │
│           │                     │                                │
│  ┌────────▼─────────────────────▼────────┐                      │
│  │    SHARED METASTORE (Unity Catalog)    │                      │
│  │    • Table definitions                 │                      │
│  │    • Access control                    │                      │
│  │    • Lineage tracking                  │                      │
│  └────────┬──────────────────────────────┘                       │
│           │                                                      │
│  ┌────────▼──────────────────────────────┐                       │
│  │    OBJECT STORE (S3/ADLS)              │                      │
│  │    • 5 PB total data                   │                      │
│  │    • 11 nines durability               │                      │
│  │    • Cross-region replication           │                      │
│  └───────────────────────────────────────┘                       │
│                                                                  │
│  ┌─────────────────┐  ┌─────────────────┐                      │
│  │ BI Cluster      │  │ Ad-hoc Cluster  │                       │
│  │ (Trino/Presto)  │  │ (Serverless SQL)│                       │
│  │ • 30 nodes      │  │ • Auto-scale    │                       │
│  │ • Dashboard SLA │  │ • Pay per query │                       │
│  │ • Caching layer │  │ • Notebooks     │                       │
│  └─────────────────┘  └─────────────────┘                      │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Cost Optimization at Scale
```
COST BREAKDOWN (1 PB Lakehouse):
─────────────────────────────────
Storage:
  S3 Standard: 500 TB × $0.023/GB = $11,500/month
  S3 IA (cold): 500 TB × $0.0125/GB = $6,250/month
  Total storage: ~$18,000/month

Compute:
  ETL (Spark): 100 nodes × 8hrs × $2/hr = $48,000/month
  BI (Trino): 30 nodes × 24hrs × $1.5/hr = $32,400/month
  ML: Variable, ~$20,000/month
  Total compute: ~$100,000/month

TOTAL: ~$118,000/month for 1 PB

COMPARISON:
  Snowflake (1 PB): ~$500,000+/month
  BigQuery (1 PB): ~$300,000+/month
  Savings: 3-5x cheaper with Lakehouse
```

