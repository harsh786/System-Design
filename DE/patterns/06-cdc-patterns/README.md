# Pattern 06: Change Data Capture (CDC)

## Overview

CDC captures row-level changes (INSERT, UPDATE, DELETE) from databases and streams 
them as events. It's the bridge between OLTP (operational) and OLAP (analytical) worlds.

**Key Tools**: Debezium, AWS DMS, Fivetran, Airbyte, Maxwell, Oracle GoldenGate
**Used at**: Every company syncing databases to data warehouses/lakes

---

## Why CDC?

```
THE PROBLEM:
═══════════
How do you keep your analytics database in sync with your operational database?

APPROACH 1: Full Extract (Naive)
  Every hour: SELECT * FROM orders → Write to warehouse
  Problems:
  • Slow (scan entire table each time)
  • Expensive (read load on production DB)
  • Misses deletes (row gone = never captured)
  • High latency (hour-old data)

APPROACH 2: Timestamp-based Incremental
  SELECT * FROM orders WHERE updated_at > last_run
  Problems:
  • Misses deletes (no updated_at on deleted rows)
  • Requires updated_at on every table
  • Can miss concurrent updates
  • Still has latency (batch intervals)

APPROACH 3: CDC (Log-based) ← THE ANSWER
  Read database's transaction log (binlog/WAL)
  Stream every change as an event in real-time
  Benefits:
  ✓ Captures EVERYTHING (insert, update, delete)
  ✓ Real-time (millisecond latency)
  ✓ No load on production DB (reads log, not tables)
  ✓ Exactly the changes (no full scans)
  ✓ Preserves order (transaction log is ordered)
```

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                        CDC ARCHITECTURE                                        │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│  SOURCE DATABASES                                                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                          │
│  │  PostgreSQL  │  │   MySQL     │  │  MongoDB    │                           │
│  │             │  │             │  │             │                            │
│  │  WAL (Write │  │  Binlog     │  │  Oplog      │                           │
│  │  Ahead Log) │  │  (Binary    │  │  (Operations│                           │
│  │             │  │   Log)      │  │   Log)      │                           │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘                          │
│         │                 │                 │                                  │
│  ┌──────▼─────────────────▼─────────────────▼──────┐                         │
│  │              DEBEZIUM (CDC Engine)                │                         │
│  │                                                   │                        │
│  │  HOW IT WORKS:                                    │                        │
│  │  1. Connects as a replication client              │                        │
│  │  2. Reads transaction log in real-time            │                        │
│  │  3. Converts log entries to structured events     │                        │
│  │  4. Publishes to Kafka (one topic per table)      │                        │
│  │                                                   │                        │
│  │  WHY DEBEZIUM:                                    │                        │
│  │  • Log-based: zero impact on source DB            │                        │
│  │  • Captures deletes (unlike query-based)          │                        │
│  │  • Preserves transaction boundaries               │                        │
│  │  • Handles schema changes                         │                        │
│  │  • Exactly-once with Kafka Connect                │                        │
│  └──────────────────────┬────────────────────────────┘                       │
│                          │                                                    │
│  ┌───────────────────────▼───────────────────────────┐                       │
│  │              KAFKA (Change Events Stream)          │                       │
│  │                                                    │                       │
│  │  Topic: db.schema.orders                           │                       │
│  │  ┌─────────────────────────────────────────┐      │                       │
│  │  │ Key: {"order_id": 12345}                 │      │                       │
│  │  │ Value: {                                 │      │                       │
│  │  │   "before": {"status": "pending", ...},  │      │                       │
│  │  │   "after": {"status": "shipped", ...},   │      │                       │
│  │  │   "op": "u",  // c=create, u=update, d=delete   │                      │
│  │  │   "ts_ms": 1234567890,                   │      │                       │
│  │  │   "source": {"db": "shop", "table": "orders"}   │                      │
│  │  │ }                                        │      │                       │
│  │  └─────────────────────────────────────────┘      │                       │
│  └───────────────┬──────────────────┬────────────────┘                       │
│                   │                  │                                         │
│    ┌──────────────▼───────┐  ┌──────▼──────────────────┐                     │
│    │  SINK: Data Lake     │  │  SINK: Search Index      │                    │
│    │  (S3/Delta Lake)     │  │  (Elasticsearch)         │                    │
│    │                      │  │                          │                     │
│    │  • Flink/Spark       │  │  • Kafka Connect Sink    │                    │
│    │  • Apply CDC ops     │  │  • Near real-time search │                    │
│    │  • Maintain latest   │  │  • Full-text indexing    │                    │
│    │    state in lake     │  │                          │                     │
│    └──────────────────────┘  └──────────────────────────┘                    │
│                                                                               │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## CDC Event Format (Debezium)

```json
{
  "schema": {...},
  "payload": {
    "before": {
      "order_id": 12345,
      "customer_id": 678,
      "status": "pending",
      "amount": 99.99,
      "updated_at": "2024-01-15T10:00:00Z"
    },
    "after": {
      "order_id": 12345,
      "customer_id": 678,
      "status": "shipped",
      "amount": 99.99,
      "updated_at": "2024-01-15T10:05:00Z"
    },
    "source": {
      "version": "2.4.0",
      "connector": "postgresql",
      "name": "production-db",
      "db": "ecommerce",
      "schema": "public",
      "table": "orders",
      "txId": 987654,
      "lsn": 123456789,
      "xmin": null
    },
    "op": "u",
    "ts_ms": 1705312500000,
    "transaction": {
      "id": "987654",
      "total_order": 3,
      "data_collection_order": 1
    }
  }
}
```

---

## Runnable Example

```python
"""
Change Data Capture (CDC) Implementation
==========================================
Simulates a complete CDC pipeline:
- Source database with transaction log
- CDC engine that reads the log
- Kafka-like event stream
- Multiple sinks (data lake, search, cache)

Run: python cdc_pipeline.py
"""

import time
import json
import threading
from datetime import datetime
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from collections import defaultdict
from enum import Enum
import copy
import random


# ============================================================================
# SOURCE DATABASE (with Transaction Log)
# ============================================================================

class Operation(Enum):
    INSERT = "c"   # create
    UPDATE = "u"   # update
    DELETE = "d"   # delete


@dataclass
class WALEntry:
    """Write-Ahead Log entry (simulates PostgreSQL WAL)"""
    lsn: int  # Log Sequence Number
    transaction_id: int
    table: str
    operation: Operation
    before: Optional[dict]  # Row state before change
    after: Optional[dict]   # Row state after change
    timestamp: float


class SourceDatabase:
    """
    Simulates a PostgreSQL database with WAL.
    
    In production:
    - PostgreSQL uses WAL (Write-Ahead Log)
    - MySQL uses binlog (Binary Log)
    - MongoDB uses oplog (Operations Log)
    
    The transaction log records EVERY change BEFORE it's applied.
    This ensures durability and enables CDC.
    """
    
    def __init__(self, name: str):
        self.name = name
        self.tables: Dict[str, Dict[Any, dict]] = defaultdict(dict)
        self.wal: List[WALEntry] = []
        self.lsn_counter = 0
        self.tx_counter = 0
        self._lock = threading.Lock()
    
    def insert(self, table: str, primary_key: Any, row: dict) -> WALEntry:
        """INSERT INTO table VALUES (...)"""
        with self._lock:
            self.lsn_counter += 1
            self.tx_counter += 1
            
            row_with_pk = {**row, '_pk': primary_key}
            
            # Write to WAL first (Write-Ahead!)
            entry = WALEntry(
                lsn=self.lsn_counter,
                transaction_id=self.tx_counter,
                table=table,
                operation=Operation.INSERT,
                before=None,
                after=copy.deepcopy(row_with_pk),
                timestamp=time.time()
            )
            self.wal.append(entry)
            
            # Then apply to table
            self.tables[table][primary_key] = row_with_pk
            return entry
    
    def update(self, table: str, primary_key: Any, changes: dict) -> WALEntry:
        """UPDATE table SET ... WHERE pk = ..."""
        with self._lock:
            self.lsn_counter += 1
            self.tx_counter += 1
            
            before = copy.deepcopy(self.tables[table].get(primary_key))
            if before is None:
                raise ValueError(f"Row {primary_key} not found in {table}")
            
            after = {**before, **changes}
            
            entry = WALEntry(
                lsn=self.lsn_counter,
                transaction_id=self.tx_counter,
                table=table,
                operation=Operation.UPDATE,
                before=before,
                after=after,
                timestamp=time.time()
            )
            self.wal.append(entry)
            
            self.tables[table][primary_key] = after
            return entry
    
    def delete(self, table: str, primary_key: Any) -> WALEntry:
        """DELETE FROM table WHERE pk = ..."""
        with self._lock:
            self.lsn_counter += 1
            self.tx_counter += 1
            
            before = copy.deepcopy(self.tables[table].get(primary_key))
            
            entry = WALEntry(
                lsn=self.lsn_counter,
                transaction_id=self.tx_counter,
                table=table,
                operation=Operation.DELETE,
                before=before,
                after=None,
                timestamp=time.time()
            )
            self.wal.append(entry)
            
            del self.tables[table][primary_key]
            return entry
    
    def get_wal_entries(self, after_lsn: int = 0) -> List[WALEntry]:
        """Read WAL entries after given LSN (for CDC)"""
        return [e for e in self.wal if e.lsn > after_lsn]


# ============================================================================
# CDC ENGINE (Simulates Debezium)
# ============================================================================

@dataclass
class CDCEvent:
    """Structured CDC event (Debezium format)"""
    event_id: str
    source_db: str
    source_table: str
    operation: str  # c, u, d
    before: Optional[dict]
    after: Optional[dict]
    timestamp: float
    lsn: int
    transaction_id: int


class CDCEngine:
    """
    Simulates Debezium CDC connector.
    
    How Debezium works in production:
    1. Initial Snapshot: Reads entire table to establish baseline
    2. Streaming: Connects as replication client, reads WAL continuously
    3. Event Production: Converts WAL entries to Kafka messages
    
    Key features:
    - Exactly-once delivery (with Kafka transactions)
    - Schema change handling (DDL events)
    - Heartbeat (detect idle sources)
    - Tombstone events (for Kafka log compaction)
    """
    
    def __init__(self, source_db: SourceDatabase, event_stream: 'EventStream'):
        self.source_db = source_db
        self.event_stream = event_stream
        self.last_lsn = 0
        self.running = False
        self.events_captured = 0
        self.snapshot_complete = False
    
    def initial_snapshot(self):
        """
        Step 1: Capture initial state of all tables.
        
        WHY: When CDC starts, it needs a baseline.
        The WAL only has recent changes, not full history.
        
        Process:
        1. Lock table briefly (or use consistent snapshot)
        2. SELECT * FROM table
        3. Record current WAL position
        4. Publish as INSERT events
        5. Start streaming from recorded position
        """
        print(f"  [CDC] Starting initial snapshot of '{self.source_db.name}'...")
        
        for table_name, rows in self.source_db.tables.items():
            for pk, row in rows.items():
                event = CDCEvent(
                    event_id=f"snapshot_{table_name}_{pk}",
                    source_db=self.source_db.name,
                    source_table=table_name,
                    operation='r',  # 'r' = read (snapshot)
                    before=None,
                    after=copy.deepcopy(row),
                    timestamp=time.time(),
                    lsn=0,
                    transaction_id=0
                )
                self.event_stream.publish(
                    topic=f"{self.source_db.name}.{table_name}",
                    key=str(pk),
                    event=event
                )
                self.events_captured += 1
        
        self.last_lsn = self.source_db.lsn_counter
        self.snapshot_complete = True
        print(f"  [CDC] Snapshot complete. Starting from LSN {self.last_lsn}")
    
    def capture_changes(self) -> int:
        """
        Step 2: Stream changes from WAL.
        Called periodically to capture new changes.
        """
        new_entries = self.source_db.get_wal_entries(self.last_lsn)
        
        for entry in new_entries:
            event = CDCEvent(
                event_id=f"cdc_{entry.lsn}",
                source_db=self.source_db.name,
                source_table=entry.table,
                operation=entry.operation.value,
                before=entry.before,
                after=entry.after,
                timestamp=entry.timestamp,
                lsn=entry.lsn,
                transaction_id=entry.transaction_id
            )
            
            # Determine key for partitioning
            key = str(entry.after.get('_pk') if entry.after 
                     else entry.before.get('_pk'))
            
            self.event_stream.publish(
                topic=f"{self.source_db.name}.{entry.table}",
                key=key,
                event=event
            )
            self.events_captured += 1
            self.last_lsn = entry.lsn
        
        return len(new_entries)


# ============================================================================
# EVENT STREAM (Simulates Kafka)
# ============================================================================

class EventStream:
    """Simulated Kafka for CDC events"""
    
    def __init__(self):
        self.topics: Dict[str, List[CDCEvent]] = defaultdict(list)
        self.subscribers: Dict[str, List[Callable]] = defaultdict(list)
    
    def publish(self, topic: str, key: str, event: CDCEvent):
        self.topics[topic].append(event)
        for subscriber in self.subscribers.get(topic, []):
            subscriber(event)
    
    def subscribe(self, topic: str, handler: Callable):
        self.subscribers[topic].append(handler)
    
    def get_events(self, topic: str) -> List[CDCEvent]:
        return self.topics.get(topic, [])


# ============================================================================
# SINKS (Consumers of CDC events)
# ============================================================================

class DataLakeSink:
    """
    Applies CDC events to a data lake table.
    Maintains current state by applying changes.
    
    In production: Flink CDC → Delta Lake / Iceberg / Hudi
    """
    
    def __init__(self, name: str):
        self.name = name
        self.records: Dict[str, dict] = {}
        self.events_applied = 0
    
    def handle_event(self, event: CDCEvent):
        if event.operation in ('c', 'r'):  # Create or snapshot read
            pk = str(event.after.get('_pk'))
            self.records[pk] = event.after
        elif event.operation == 'u':
            pk = str(event.after.get('_pk'))
            self.records[pk] = event.after
        elif event.operation == 'd':
            pk = str(event.before.get('_pk'))
            self.records.pop(pk, None)
        self.events_applied += 1
    
    def get_record_count(self) -> int:
        return len(self.records)
    
    def query(self, filters: Dict[str, Any] = None) -> List[dict]:
        results = list(self.records.values())
        if filters:
            results = [
                r for r in results
                if all(r.get(k) == v for k, v in filters.items())
            ]
        return results


class SearchIndexSink:
    """
    Applies CDC to search index (Elasticsearch).
    Enables full-text search on database records.
    """
    
    def __init__(self):
        self.index: Dict[str, dict] = {}
        self.events_applied = 0
    
    def handle_event(self, event: CDCEvent):
        if event.operation in ('c', 'r', 'u'):
            pk = str(event.after.get('_pk'))
            self.index[pk] = event.after
        elif event.operation == 'd':
            pk = str(event.before.get('_pk'))
            self.index.pop(pk, None)
        self.events_applied += 1
    
    def search(self, field: str, value: str) -> List[dict]:
        """Simple search (production: Elasticsearch full-text)"""
        return [
            doc for doc in self.index.values()
            if value.lower() in str(doc.get(field, '')).lower()
        ]


class CacheSink:
    """Keeps Redis cache in sync via CDC"""
    
    def __init__(self):
        self.cache: Dict[str, dict] = {}
        self.events_applied = 0
    
    def handle_event(self, event: CDCEvent):
        if event.operation in ('c', 'r', 'u'):
            pk = str(event.after.get('_pk'))
            self.cache[pk] = event.after
        elif event.operation == 'd':
            pk = str(event.before.get('_pk'))
            self.cache.pop(pk, None)
        self.events_applied += 1


# ============================================================================
# DEMONSTRATION
# ============================================================================

def run_cdc_demo():
    print("""
╔══════════════════════════════════════════════════════════════════╗
║       CHANGE DATA CAPTURE (CDC) - COMPLETE PIPELINE DEMO        ║
╠══════════════════════════════════════════════════════════════════╣
║                                                                  ║
║  Source: PostgreSQL (simulated with WAL)                         ║
║  CDC Engine: Debezium-like (reads WAL, produces events)          ║
║  Stream: Kafka-like (ordered, partitioned)                       ║
║  Sinks: Data Lake + Search Index + Cache                         ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝
    """)
    
    # Setup
    db = SourceDatabase("ecommerce_prod")
    stream = EventStream()
    cdc = CDCEngine(db, stream)
    
    # Sinks
    lake_sink = DataLakeSink("analytics_lake")
    search_sink = SearchIndexSink()
    cache_sink = CacheSink()
    
    # Subscribe sinks
    stream.subscribe("ecommerce_prod.orders", lake_sink.handle_event)
    stream.subscribe("ecommerce_prod.orders", search_sink.handle_event)
    stream.subscribe("ecommerce_prod.orders", cache_sink.handle_event)
    
    # ─── Step 1: Create initial data ───
    print("=" * 60)
    print("STEP 1: Populate Source Database")
    print("=" * 60)
    
    orders = [
        (1001, {'order_id': 1001, 'customer': 'Alice', 'product': 'Laptop', 'amount': 999.99, 'status': 'placed'}),
        (1002, {'order_id': 1002, 'customer': 'Bob', 'product': 'Phone', 'amount': 699.99, 'status': 'placed'}),
        (1003, {'order_id': 1003, 'customer': 'Charlie', 'product': 'Tablet', 'amount': 399.99, 'status': 'placed'}),
        (1004, {'order_id': 1004, 'customer': 'Diana', 'product': 'Watch', 'amount': 299.99, 'status': 'placed'}),
        (1005, {'order_id': 1005, 'customer': 'Eve', 'product': 'Headphones', 'amount': 149.99, 'status': 'placed'}),
    ]
    
    for pk, row in orders:
        db.insert("orders", pk, row)
    print(f"  Inserted {len(orders)} orders into source database")
    
    # ─── Step 2: Initial Snapshot ───
    print(f"\n{'=' * 60}")
    print("STEP 2: CDC Initial Snapshot")
    print("=" * 60)
    
    cdc.initial_snapshot()
    print(f"  Lake sink records: {lake_sink.get_record_count()}")
    print(f"  Search index docs: {len(search_sink.index)}")
    print(f"  Cache entries: {len(cache_sink.cache)}")
    
    # ─── Step 3: Make changes in source ───
    print(f"\n{'=' * 60}")
    print("STEP 3: Source Database Changes (Simulating Application Writes)")
    print("=" * 60)
    
    # Updates
    db.update("orders", 1001, {'status': 'shipped', 'shipped_at': '2024-01-15'})
    print("  UPDATE: Order 1001 shipped")
    
    db.update("orders", 1002, {'status': 'shipped', 'shipped_at': '2024-01-15'})
    print("  UPDATE: Order 1002 shipped")
    
    # New insert
    db.insert("orders", 1006, {
        'order_id': 1006, 'customer': 'Frank', 
        'product': 'Camera', 'amount': 549.99, 'status': 'placed'
    })
    print("  INSERT: New order 1006 (Frank, Camera)")
    
    # Delete
    db.delete("orders", 1005)
    print("  DELETE: Order 1005 cancelled and removed")
    
    # More updates
    db.update("orders", 1003, {'status': 'delivered', 'delivered_at': '2024-01-16'})
    print("  UPDATE: Order 1003 delivered")
    
    # ─── Step 4: CDC captures changes ───
    print(f"\n{'=' * 60}")
    print("STEP 4: CDC Captures Changes from WAL")
    print("=" * 60)
    
    captured = cdc.capture_changes()
    print(f"  Captured {captured} change events from WAL")
    print(f"  Total CDC events: {cdc.events_captured}")
    
    # ─── Step 5: Verify all sinks are in sync ───
    print(f"\n{'=' * 60}")
    print("STEP 5: Verify Sinks Are In Sync")
    print("=" * 60)
    
    print(f"\n  Source DB orders: {len(db.tables['orders'])}")
    print(f"  Lake sink records: {lake_sink.get_record_count()}")
    print(f"  Search index docs: {len(search_sink.index)}")
    print(f"  Cache entries: {len(cache_sink.cache)}")
    
    # Verify specific record
    print(f"\n  Verification - Order 1001:")
    source = db.tables['orders'].get(1001)
    lake = lake_sink.records.get('1001')
    print(f"    Source DB: status={source['status']}")
    print(f"    Lake Sink: status={lake['status']}")
    print(f"    In sync: {source['status'] == lake['status']}")
    
    # Verify delete propagated
    print(f"\n  Verification - Order 1005 (deleted):")
    print(f"    Source DB: {'exists' if 1005 in db.tables['orders'] else 'DELETED'}")
    print(f"    Lake Sink: {'exists' if '1005' in lake_sink.records else 'DELETED'}")
    
    # Search demonstration
    print(f"\n  Search Index Query: products containing 'lap'")
    results = search_sink.search('product', 'lap')
    for r in results:
        print(f"    Found: {r['customer']} - {r['product']} (${r['amount']})")
    
    print(f"\n{'=' * 60}")
    print("CDC PIPELINE SUMMARY")
    print("=" * 60)
    print(f"""
  Source Changes:  {len(db.wal)} WAL entries
  CDC Events:      {cdc.events_captured} events captured
  Latency:         <1ms (simulated, production: 10-100ms)
  
  All 3 sinks perfectly in sync with source:
  • Data Lake: For analytics/reporting
  • Search: For full-text queries  
  • Cache: For low-latency lookups
  
  KEY: Source DB has ZERO extra load (CDC reads WAL only)
    """)


if __name__ == '__main__':
    run_cdc_demo()
```

