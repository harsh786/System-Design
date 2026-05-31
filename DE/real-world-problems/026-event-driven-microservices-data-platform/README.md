# Problem 26: Event-Driven Microservices Data Platform

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

