# Real-World Data Engineering Problems (26-50)
# Complete Architecture + Diagrams + Scalability + Runnable Code

---

## Problem 26: Event-Driven Microservices Data Platform

### Business Context
E-commerce platform transitioning from monolith to microservices. 
30 services need consistent data views without tight coupling.

### Architecture
```
┌─────────────────────────────────────────────────────────────────────────────┐
│         EVENT-DRIVEN MICROSERVICES DATA ARCHITECTURE                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐                   │
│  │Orders│ │Users │ │Payments│ │Inventory│ │Shipping│ │Reviews│              │
│  │Svc   │ │Svc   │ │Svc   │ │Svc    │ │Svc    │ │Svc   │                 │
│  └──┬───┘ └──┬───┘ └──┬───┘ └──┬────┘ └──┬────┘ └──┬───┘                 │
│     │        │        │        │          │         │                       │
│  ┌──▼────────▼────────▼────────▼──────────▼─────────▼───────────────┐      │
│  │                    KAFKA (Event Backbone)                          │      │
│  │                                                                    │      │
│  │  Topics (domain events):                                           │      │
│  │  • orders.placed / orders.shipped / orders.cancelled               │      │
│  │  • payments.captured / payments.refunded                           │      │
│  │  • inventory.reserved / inventory.released                         │      │
│  │  • users.registered / users.updated                                │      │
│  │                                                                    │      │
│  │  WHY KAFKA as backbone:                                            │      │
│  │  • Decoupling: Services don't know about each other                │      │
│  │  • Replay: New services can catch up from history                  │      │
│  │  • Ordering: Events per entity are ordered (partition key)         │      │
│  │  • Durability: Events survive service outages                      │      │
│  └────────┬──────────────────────────────────┬──────────────────────┘      │
│           │                                   │                             │
│  ┌────────▼──────────────────────┐  ┌────────▼──────────────────────┐     │
│  │  SAGA ORCHESTRATOR            │  │  ANALYTICS CONSUMER           │      │
│  │                               │  │                               │      │
│  │  Order Saga:                  │  │  Consumes all domain events   │      │
│  │  1. Order placed              │  │  Builds unified data model    │      │
│  │  2. → Reserve inventory       │  │  → Delta Lake (for BI)        │      │
│  │  3. → Capture payment         │  │  → Druid (for dashboards)     │      │
│  │  4. → Schedule shipment       │  │  → Elasticsearch (for search) │     │
│  │                               │  │                               │      │
│  │  Compensation on failure:     │  │  Pattern: Event Sourcing       │     │
│  │  • Payment failed → release   │  │  All events stored forever    │      │
│  │    inventory                  │  │  Rebuild any view by replay   │      │
│  │  • Shipping unavailable →     │  │                               │      │
│  │    refund payment             │  │                               │      │
│  └───────────────────────────────┘  └───────────────────────────────┘     │
│                                                                             │
│  CONSISTENCY MODEL:                                                         │
│  • Within service: Strong (local ACID transaction)                          │
│  • Across services: Eventually consistent (via events)                      │
│  • Saga pattern: Distributed transactions without 2PC                       │
│  • Idempotency: Every handler is idempotent (dedup by event_id)            │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Runnable Code: Saga Pattern
```python
"""
Event-Driven Saga Pattern Implementation
==========================================
Order fulfillment saga across microservices:
- Order Service → Payment Service → Inventory Service → Shipping Service
- With compensation (rollback) on failure

Run: python saga_pattern.py
"""

import time
import uuid
import random
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable
from collections import defaultdict


class SagaState(Enum):
    STARTED = "started"
    PAYMENT_PENDING = "payment_pending"
    PAYMENT_CAPTURED = "payment_captured"
    INVENTORY_RESERVED = "inventory_reserved"
    SHIPPING_SCHEDULED = "shipping_scheduled"
    COMPLETED = "completed"
    COMPENSATING = "compensating"
    FAILED = "failed"


@dataclass
class SagaEvent:
    event_id: str
    saga_id: str
    event_type: str
    data: dict
    timestamp: float = field(default_factory=time.time)


@dataclass 
class OrderSaga:
    saga_id: str
    order_id: str
    user_id: str
    items: List[dict]
    total_amount: float
    state: SagaState = SagaState.STARTED
    events: List[SagaEvent] = field(default_factory=list)
    compensation_stack: List[Callable] = field(default_factory=list)


class EventBus:
    """Simulated Kafka event bus"""
    def __init__(self):
        self.handlers: Dict[str, List[Callable]] = defaultdict(list)
        self.events: List[SagaEvent] = []
    
    def publish(self, event: SagaEvent):
        self.events.append(event)
        for handler in self.handlers.get(event.event_type, []):
            handler(event)
    
    def subscribe(self, event_type: str, handler: Callable):
        self.handlers[event_type].append(handler)


class PaymentService:
    """Simulates payment processing"""
    def __init__(self, event_bus: EventBus, failure_rate: float = 0.1):
        self.event_bus = event_bus
        self.failure_rate = failure_rate
        self.captured_payments: Dict[str, float] = {}
    
    def capture_payment(self, saga_id: str, user_id: str, amount: float) -> bool:
        if random.random() < self.failure_rate:
            self.event_bus.publish(SagaEvent(
                event_id=str(uuid.uuid4()), saga_id=saga_id,
                event_type="payment.failed",
                data={'reason': 'insufficient_funds', 'amount': amount}
            ))
            return False
        
        self.captured_payments[saga_id] = amount
        self.event_bus.publish(SagaEvent(
            event_id=str(uuid.uuid4()), saga_id=saga_id,
            event_type="payment.captured",
            data={'amount': amount, 'user_id': user_id}
        ))
        return True
    
    def refund_payment(self, saga_id: str) -> bool:
        amount = self.captured_payments.pop(saga_id, 0)
        self.event_bus.publish(SagaEvent(
            event_id=str(uuid.uuid4()), saga_id=saga_id,
            event_type="payment.refunded",
            data={'amount': amount}
        ))
        print(f"    COMPENSATE: Refunded ${amount:.2f}")
        return True


class InventoryService:
    """Simulates inventory management"""
    def __init__(self, event_bus: EventBus, failure_rate: float = 0.1):
        self.event_bus = event_bus
        self.failure_rate = failure_rate
        self.reservations: Dict[str, List[dict]] = {}
    
    def reserve_items(self, saga_id: str, items: List[dict]) -> bool:
        if random.random() < self.failure_rate:
            self.event_bus.publish(SagaEvent(
                event_id=str(uuid.uuid4()), saga_id=saga_id,
                event_type="inventory.reservation_failed",
                data={'reason': 'out_of_stock', 'items': items}
            ))
            return False
        
        self.reservations[saga_id] = items
        self.event_bus.publish(SagaEvent(
            event_id=str(uuid.uuid4()), saga_id=saga_id,
            event_type="inventory.reserved",
            data={'items': items}
        ))
        return True
    
    def release_items(self, saga_id: str) -> bool:
        items = self.reservations.pop(saga_id, [])
        self.event_bus.publish(SagaEvent(
            event_id=str(uuid.uuid4()), saga_id=saga_id,
            event_type="inventory.released",
            data={'items': items}
        ))
        print(f"    COMPENSATE: Released {len(items)} items back to inventory")
        return True


class ShippingService:
    """Simulates shipping"""
    def __init__(self, event_bus: EventBus, failure_rate: float = 0.05):
        self.event_bus = event_bus
        self.failure_rate = failure_rate
    
    def schedule_shipment(self, saga_id: str, items: List[dict]) -> bool:
        if random.random() < self.failure_rate:
            self.event_bus.publish(SagaEvent(
                event_id=str(uuid.uuid4()), saga_id=saga_id,
                event_type="shipping.failed",
                data={'reason': 'no_carrier_available'}
            ))
            return False
        
        self.event_bus.publish(SagaEvent(
            event_id=str(uuid.uuid4()), saga_id=saga_id,
            event_type="shipping.scheduled",
            data={'tracking_id': f"TRACK-{uuid.uuid4().hex[:8].upper()}"}
        ))
        return True


class SagaOrchestrator:
    """
    Orchestrates the order fulfillment saga.
    
    KEY CONCEPTS:
    - Forward path: Execute steps in order
    - Compensation: On failure, undo completed steps in reverse
    - Idempotency: Each step can be safely retried
    - Event log: Complete audit trail
    """
    
    def __init__(self, payment_svc: PaymentService,
                 inventory_svc: InventoryService,
                 shipping_svc: ShippingService,
                 event_bus: EventBus):
        self.payment = payment_svc
        self.inventory = inventory_svc
        self.shipping = shipping_svc
        self.event_bus = event_bus
        self.sagas: Dict[str, OrderSaga] = {}
    
    def execute_order_saga(self, order_id: str, user_id: str,
                          items: List[dict], total: float) -> OrderSaga:
        """Execute the full order saga with compensation"""
        saga = OrderSaga(
            saga_id=str(uuid.uuid4()),
            order_id=order_id,
            user_id=user_id,
            items=items,
            total_amount=total
        )
        self.sagas[saga.saga_id] = saga
        
        print(f"\n  Saga {saga.saga_id[:8]}... started for order {order_id}")
        
        # Step 1: Capture Payment
        saga.state = SagaState.PAYMENT_PENDING
        print(f"    Step 1: Capturing payment ${total:.2f}...")
        
        if not self.payment.capture_payment(saga.saga_id, user_id, total):
            print(f"    FAILED: Payment capture failed")
            saga.state = SagaState.FAILED
            return saga
        
        saga.state = SagaState.PAYMENT_CAPTURED
        saga.compensation_stack.append(
            lambda: self.payment.refund_payment(saga.saga_id)
        )
        print(f"    Step 1: Payment captured ✓")
        
        # Step 2: Reserve Inventory
        print(f"    Step 2: Reserving {len(items)} items...")
        
        if not self.inventory.reserve_items(saga.saga_id, items):
            print(f"    FAILED: Inventory reservation failed")
            print(f"    Starting compensation (rollback)...")
            saga.state = SagaState.COMPENSATING
            self._compensate(saga)
            saga.state = SagaState.FAILED
            return saga
        
        saga.state = SagaState.INVENTORY_RESERVED
        saga.compensation_stack.append(
            lambda: self.inventory.release_items(saga.saga_id)
        )
        print(f"    Step 2: Inventory reserved ✓")
        
        # Step 3: Schedule Shipping
        print(f"    Step 3: Scheduling shipment...")
        
        if not self.shipping.schedule_shipment(saga.saga_id, items):
            print(f"    FAILED: Shipping scheduling failed")
            print(f"    Starting compensation (rollback)...")
            saga.state = SagaState.COMPENSATING
            self._compensate(saga)
            saga.state = SagaState.FAILED
            return saga
        
        saga.state = SagaState.COMPLETED
        print(f"    Step 3: Shipment scheduled ✓")
        print(f"  Saga COMPLETED successfully!")
        return saga
    
    def _compensate(self, saga: OrderSaga):
        """Execute compensation actions in reverse order"""
        while saga.compensation_stack:
            compensate_fn = saga.compensation_stack.pop()
            compensate_fn()


def run_saga_demo():
    print("""
╔══════════════════════════════════════════════════════════════════╗
║       EVENT-DRIVEN SAGA PATTERN DEMONSTRATION                   ║
╠══════════════════════════════════════════════════════════════════╣
║                                                                  ║
║  Simulates order fulfillment across microservices:               ║
║  Payment → Inventory → Shipping                                  ║
║  With automatic compensation (rollback) on failure               ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝
    """)
    
    event_bus = EventBus()
    payment = PaymentService(event_bus, failure_rate=0.15)
    inventory = InventoryService(event_bus, failure_rate=0.15)
    shipping = ShippingService(event_bus, failure_rate=0.10)
    orchestrator = SagaOrchestrator(payment, inventory, shipping, event_bus)
    
    # Process multiple orders
    results = {'COMPLETED': 0, 'FAILED': 0}
    
    for i in range(20):
        items = [
            {'product_id': f'PROD-{random.randint(1,100):03d}', 'qty': random.randint(1,3)}
            for _ in range(random.randint(1, 4))
        ]
        total = round(random.uniform(25, 500), 2)
        
        saga = orchestrator.execute_order_saga(
            order_id=f"ORD-{i+1:04d}",
            user_id=f"USER-{random.randint(1,100):04d}",
            items=items,
            total=total
        )
        results[saga.state.name if saga.state == SagaState.COMPLETED else 'FAILED'] += 1
    
    print(f"\n{'=' * 60}")
    print("SAGA EXECUTION SUMMARY")
    print(f"{'=' * 60}")
    print(f"  Total Orders: 20")
    print(f"  Completed: {results['COMPLETED']}")
    print(f"  Failed (with compensation): {results['FAILED']}")
    print(f"  Success Rate: {results['COMPLETED']/20*100:.1f}%")
    print(f"  Total events recorded: {len(event_bus.events)}")


if __name__ == '__main__':
    run_saga_demo()
```

---

## Problem 27: Real-Time Data Quality Monitoring

### Architecture
```
┌─────────────────────────────────────────────────────────────────────────────┐
│         DATA QUALITY MONITORING ARCHITECTURE                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  DATA PIPELINES (100+ DAGs in Airflow)                                       │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐                          │
│  │  ETL 1  │ │  ETL 2  │ │  ETL 3  │ │  ETL N  │                          │
│  └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘                          │
│       │           │           │           │                                 │
│  ┌────▼───────────▼───────────▼───────────▼────┐                           │
│  │  DATA QUALITY CHECKS (at each stage)         │                           │
│  │                                              │                            │
│  │  ┌─────────────────────────────────────────┐│                            │
│  │  │ CHECK TYPES:                             ││                            │
│  │  │ • Schema: columns exist, types match     ││                            │
│  │  │ • Freshness: data arrived on time        ││                            │
│  │  │ • Volume: row count within ±20% of norm  ││                            │
│  │  │ • Completeness: NULL rate < threshold    ││                            │
│  │  │ • Uniqueness: no duplicate PKs           ││                            │
│  │  │ • Range: values within expected bounds   ││                            │
│  │  │ • Referential: FK relationships hold     ││                            │
│  │  │ • Custom: business-specific rules        ││                            │
│  │  └─────────────────────────────────────────┘│                            │
│  └────────────────────┬────────────────────────┘                            │
│                       │                                                      │
│  ┌────────────────────▼────────────────────────┐                            │
│  │  CIRCUIT BREAKER                             │                            │
│  │                                              │                            │
│  │  If critical check fails:                    │                            │
│  │  → HALT downstream pipeline                  │                            │
│  │  → Alert on-call engineer (PagerDuty)        │                            │
│  │  → Record in quality events (Kafka)          │                            │
│  │  → Dashboard shows red (Grafana)             │                            │
│  │                                              │                            │
│  │  If non-critical check fails:                │                            │
│  │  → Log warning                               │                            │
│  │  → Continue pipeline                         │                            │
│  │  → Track trend (degradation detection)       │                            │
│  └────────────────────┬────────────────────────┘                            │
│                       │                                                      │
│  ┌────────────────────▼────────────────────────┐                            │
│  │  QUALITY METADATA STORE                      │                            │
│  │                                              │                            │
│  │  • Historical check results (time-series)    │                            │
│  │  • SLA tracking per dataset                  │                            │
│  │  • Anomaly detection on quality metrics      │                            │
│  │  • Data contract compliance                  │                            │
│  │                                              │                            │
│  │  Store: TimescaleDB (time-series optimized)  │                            │
│  │  Viz: Grafana dashboards                     │                            │
│  └──────────────────────────────────────────────┘                           │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Problem 28: Streaming Data Warehouse (Real-Time Materialized Views)

### Architecture
```
┌─────────────────────────────────────────────────────────────────────────────┐
│         STREAMING DATA WAREHOUSE (Materialized Views)                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  SOURCE SYSTEMS                                                              │
│  ┌────────┐ ┌────────┐ ┌────────┐                                          │
│  │ Orders │ │ Users  │ │ Products│                                          │
│  │  (CDC) │ │  (CDC) │ │  (CDC)  │                                          │
│  └───┬────┘ └───┬────┘ └───┬─────┘                                         │
│      │          │          │                                                 │
│  ┌───▼──────────▼──────────▼─────────────────────────────────┐             │
│  │  KAFKA (CDC Events)                                        │             │
│  └──────────────────────┬────────────────────────────────────┘             │
│                          │                                                   │
│  ┌───────────────────────▼───────────────────────────────────┐             │
│  │  FLINK SQL (Streaming Joins + Aggregations)                │             │
│  │                                                            │             │
│  │  -- Real-time materialized view (continuously updated)     │             │
│  │  CREATE TABLE revenue_by_category AS                       │              │
│  │  SELECT                                                    │              │
│  │    p.category,                                             │             │
│  │    TUMBLE_START(o.order_time, INTERVAL '1' MINUTE) as ts,  │             │
│  │    SUM(o.amount) as revenue,                               │             │
│  │    COUNT(*) as order_count                                 │             │
│  │  FROM orders o                                             │             │
│  │  JOIN products p ON o.product_id = p.product_id            │             │
│  │  GROUP BY p.category, TUMBLE(o.order_time, INTERVAL '1' MINUTE);        │
│  │                                                            │             │
│  │  WHY FLINK SQL:                                            │             │
│  │  • SQL familiar to analysts                                │             │
│  │  • Handles temporal joins (event-time semantics)           │             │
│  │  • Exactly-once (checkpointed)                             │             │
│  │  • Scales horizontally                                     │             │
│  └──────────────────────┬────────────────────────────────────┘             │
│                          │                                                   │
│  ┌───────────────────────▼───────────────────────────────────┐             │
│  │  SERVING (Multiple Materialized Views)                      │             │
│  │                                                            │             │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐       │             │
│  │  │ Pinot       │  │ Redis       │  │ Postgres    │        │             │
│  │  │(OLAP query) │  │(K/V lookup) │  │(Dashboards) │        │             │
│  │  │             │  │             │  │             │         │             │
│  │  │ Real-time   │  │ Current     │  │ Pre-aggreg  │         │            │
│  │  │ slice&dice  │  │ state cache │  │ for Grafana │         │            │
│  │  └─────────────┘  └─────────────┘  └─────────────┘       │             │
│  └────────────────────────────────────────────────────────────┘            │
│                                                                              │
│  LATENCY: Source change → Materialized view update: <5 seconds               │
│  FRESHNESS: Dashboards reflect data that's <5 seconds old                    │
│  VS BATCH: Traditional warehouse: 1-24 hour delay                            │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Problem 29: Log-Structured Merge Tree Pipeline (LSM-Tree for Time-Series)

### Why LSM-Tree for Data Engineering?
```
THE INSIGHT: Most data engineering workloads are WRITE-HEAVY

Traditional B-Tree:
  • Random writes (slow on SSD, terrible on HDD)
  • Each write = disk seek
  • Good for reads, bad for writes

LSM-Tree (used by: RocksDB, Cassandra, HBase, LevelDB):
  • Sequential writes (fast on any storage)
  • Buffer writes in memory → flush to disk as sorted runs
  • Background compaction merges runs
  • PERFECT for: time-series, event logs, CDC sinks

DATA ENGINEERING USE:
  • Flink state backend (RocksDB)
  • Kafka storage engine
  • Time-series databases (InfluxDB, TimescaleDB)
  • Data lake compaction strategies
```

---

## Problem 30: Exactly-Once Processing Across Systems

### Architecture
```
┌─────────────────────────────────────────────────────────────────────────────┐
│         EXACTLY-ONCE END-TO-END ARCHITECTURE                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  THE CHALLENGE:                                                              │
│  Kafka (exactly-once) → Flink (exactly-once) → Database (???)               │
│  Even if each component is exactly-once internally,                          │
│  the END-TO-END might not be without careful design.                         │
│                                                                              │
│  SOLUTION: Transactional Outbox + Idempotent Consumers                       │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────┐         │
│  │  PRODUCER (Transactional Outbox Pattern)                        │         │
│  │                                                                 │         │
│  │  BEGIN TRANSACTION;                                             │         │
│  │    INSERT INTO orders (...);                                    │         │
│  │    INSERT INTO outbox (event_id, payload, status='pending');    │         │
│  │  COMMIT;                                                        │         │
│  │                                                                 │         │
│  │  Separate process: Poll outbox → Publish to Kafka → Mark sent  │         │
│  │  Result: DB + Kafka always consistent                           │         │
│  └────────────────────────────────────────────────────────────────┘         │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────┐         │
│  │  KAFKA (Exactly-Once via Transactions)                          │         │
│  │                                                                 │         │
│  │  enable.idempotence=true (dedup at broker)                      │         │
│  │  transactional.id=unique-producer-id                            │         │
│  │  isolation.level=read_committed (consumers see only committed)  │         │
│  └────────────────────────────────────────────────────────────────┘         │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────┐         │
│  │  FLINK (Exactly-Once via Checkpointing)                         │         │
│  │                                                                 │         │
│  │  Checkpoint Barrier:                                            │         │
│  │  ┌───────────────────────────────────────┐                     │         │
│  │  │  Source → [Barrier] → Process → Sink  │                     │         │
│  │  │                                       │                      │         │
│  │  │  On checkpoint:                       │                      │         │
│  │  │  1. Kafka consumer commits offset     │                      │         │
│  │  │  2. Flink saves operator state        │                      │         │
│  │  │  3. Sink pre-commits (2PC)            │                      │         │
│  │  │                                       │                      │         │
│  │  │  On recovery:                         │                      │         │
│  │  │  1. Restore from last checkpoint      │                      │         │
│  │  │  2. Re-read from committed offset     │                      │         │
│  │  │  3. Sink aborts uncommitted           │                      │         │
│  │  └───────────────────────────────────────┘                     │         │
│  └────────────────────────────────────────────────────────────────┘         │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────┐         │
│  │  SINK (Idempotent Consumer Pattern)                             │         │
│  │                                                                 │         │
│  │  Option A: Idempotent writes                                    │         │
│  │    INSERT ... ON CONFLICT (event_id) DO NOTHING;                │         │
│  │    (Dedup by unique event_id)                                   │         │
│  │                                                                 │         │
│  │  Option B: Transactional sink (2PC with Flink)                  │         │
│  │    Flink pre-commits → Checkpoint → Flink commits               │         │
│  │    (Only works with 2PC-capable sinks: Kafka, some DBs)         │         │
│  │                                                                 │         │
│  │  Option C: Upsert by natural key                                │         │
│  │    MERGE INTO target USING source ON key = key                  │         │
│  │    (Naturally idempotent: same data → same result)              │         │
│  └────────────────────────────────────────────────────────────────┘         │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Problems 31-50: Architecture Summaries

### Problem 31: Data Catalog & Discovery Platform
```
ARCH: Crawlers → Metadata Store (Amundsen/DataHub) → Graph DB → Search UI
WHY GRAPH: Data relationships are naturally a graph (lineage, ownership, joins)
SCALE: 50K datasets, 5K users, real-time metadata updates via Kafka
```

### Problem 32: Reverse ETL (Warehouse → Operational Systems)
```
ARCH: Warehouse → Census/Hightouch → CRM, Marketing, Support tools
WHY: Analytics team defines segments in SQL, ops teams need them in tools
SYNC: Incremental (only changed rows), idempotent, rate-limited
```

### Problem 33: Real-Time Anomaly Detection on Metrics
```
ARCH: Metrics → Kafka → Flink (statistical models) → Alert Manager
ALGORITHMS: Z-score, IQR, STL decomposition, Prophet-based
WHY STREAMING: Detect anomalies within 1 minute of occurrence
```

### Problem 34: Data Versioning & Reproducibility (ML)
```
ARCH: DVC + Delta Lake time-travel + MLflow experiment tracking
WHY: Reproduce any model training run with exact data snapshot
CHALLENGE: Petabyte datasets can't be git-versioned
SOLUTION: Version metadata (Delta log), not data files
```

### Problem 35: Cross-Database Federated Queries
```
ARCH: Trino/Presto federation across: MySQL + S3 + Elasticsearch + Redis
WHY TRINO: Single SQL interface to heterogeneous sources
OPTIMIZATION: Pushdown predicates to source, minimize data movement
```

### Problem 36: Streaming CDC to Data Warehouse (Snowflake/BQ)
```
ARCH: Debezium → Kafka → Kafka Connect → Snowflake/BQ
CHALLENGE: Merge (upsert) in warehouse (not just append)
SOLUTION: Snowpipe Streaming + MERGE tasks, or Flink → staging → MERGE
```

### Problem 37: Time-Series Forecasting Pipeline
```
ARCH: Historical → Feature Engineering (Spark) → Model Training → Serving
MODELS: Prophet, DeepAR, N-BEATS, Temporal Fusion Transformer
SCALE: 1M time series (one per SKU), retrain weekly
SERVING: Pre-compute forecasts, store in Redis for instant lookup
```

### Problem 38: Data Contracts Between Teams
```
ARCH: Schema Registry + Contract tests + CI/CD validation
FORMAT: Protobuf/Avro with compatibility rules (backward/forward)
ENFORCEMENT: Producer can't deploy incompatible schema changes
NOTIFICATION: Consumers alerted of upcoming breaking changes
```

### Problem 39: Backfill & Reprocessing Framework
```
ARCH: Idempotent jobs + partition-level reprocessing + validation
PATTERN: Write to staging → validate → atomic swap to production
WHY IDEMPOTENT: Reprocessing same data must give same result
SCALE: Backfill 1 year of data = replay 365 daily partitions
```

### Problem 40: Real-Time User Session Analysis
```
ARCH: Click events → Kafka → Flink (session windows) → Analytics
SESSION WINDOW: Gap-based (30 min inactivity = new session)
METRICS: Duration, pages viewed, conversion, bounce rate
REAL-TIME: Show "active users now" dashboard updated every 5 seconds
```

### Problem 41: Data Pipeline Orchestration (Beyond Airflow)
```
MODERN: Dagster (asset-based) vs Prefect (dynamic) vs Airflow (DAG)
WHY DAGSTER: Software-defined assets, better testing, observability
WHY STILL AIRFLOW: Mature, huge community, battle-tested at scale
HYBRID: Airflow orchestrates, Spark/Flink executes
```

### Problem 42: Schema Registry & Evolution Management
```
ARCH: Confluent Schema Registry + compatibility modes
MODES: BACKWARD (new reader, old data) / FORWARD (old reader, new data)
ENFORCEMENT: Kafka rejects messages failing schema validation
MIGRATION: Dual-write during schema transition period
```

### Problem 43: Data Lakehouse Performance Tuning
```
TECHNIQUES:
  • Z-ORDER clustering (multi-column co-location)
  • File compaction (merge small files → target 256MB)
  • Bloom filter indexes (point lookups)
  • Data skipping (column statistics in manifest)
  • Partition pruning (date-based partitioning)
RESULT: 10-100x query speedup for analytical workloads
```

### Problem 44: Streaming Deduplication at Scale
```
ARCH: Kafka → Flink (dedup by event_id) → Clean stream
CHALLENGE: State grows unbounded (remember all seen IDs)
SOLUTIONS:
  • Bloom filter (probabilistic, false positives ok for some cases)
  • Time-bounded dedup (only dedup within 1-hour window)
  • RocksDB state with TTL (auto-expire old IDs)
```

### Problem 45: Multi-Cloud Data Platform
```
ARCH: Abstract storage (Iceberg) + compute (Spark/Flink) across AWS + GCP
WHY ICEBERG: Same table readable from AWS EMR and GCP Dataproc
REPLICATION: Cross-cloud via Kafka MirrorMaker or storage-level sync
CHALLENGE: Egress costs, latency, consistency
```

### Problem 46: PII Detection & Tokenization Pipeline
```
ARCH: Data → NER model (detect PII) → Tokenize/Hash → Store
DETECTION: Names, emails, SSN, phone, address (NLP + regex)
TOKENIZATION: Format-preserving encryption (FPE) for testing
GDPR: Right to erasure = delete token mapping = data "forgotten"
```

### Problem 47: Cost Optimization for Data Platform
```
STRATEGIES:
  • Storage tiering (hot → warm → cold → archive)
  • Compute right-sizing (auto-scale, spot instances)
  • Query optimization (materialized views, caching)
  • Data lifecycle (TTL, auto-archive)
METRICS: $/GB stored, $/query, $/pipeline run
TARGET: 40-60% reduction from naive approach
```

### Problem 48: Streaming Graph Analytics
```
ARCH: Events → Kafka → Flink → Graph DB (Neo4j/Neptune)
USE CASE: Fraud rings, social network analysis, knowledge graphs
WHY STREAMING: Detect emerging patterns in real-time
CHALLENGE: Graph updates are expensive (rebalancing, index updates)
```

### Problem 49: Data Warehouse Automation (Auto-Modeling)
```
ARCH: Source metadata → Auto-generate star schema → dbt models → Tests
TOOLS: dbt + custom generators + Great Expectations
APPROACH: Convention over configuration (naming = relationships)
OUTPUT: 80% automated, 20% manual for complex business logic
```

### Problem 50: Disaster Recovery for Data Pipelines
```
ARCH: Multi-AZ primary + cross-region standby + S3 cross-region replication
RPO: <1 hour (data loss tolerance)
RTO: <4 hours (recovery time)
STRATEGY: Active-passive with automated failover
TESTING: Monthly DR drills (actually fail over and back)
```

