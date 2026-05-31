# Pattern 05: Event Sourcing + CQRS

## Overview

**Event Sourcing**: Store ALL state changes as an immutable sequence of events.
The current state is derived by replaying events.

**CQRS** (Command Query Responsibility Segregation): Separate read and write models.
Writes go to event store, reads come from optimized materialized views.

**Used at**: Banking (all), Event Store Ltd, Axon Framework users, DDD practitioners

---

## Why Event Sourcing + CQRS?

```
TRADITIONAL APPROACH (CRUD):
════════════════════════════
State: { balance: 1000 }
UPDATE accounts SET balance = 1000 WHERE id = 'user1'

Problems:
- Lost history: WHY is balance 1000? What happened?
- No audit trail: Compliance nightmare
- No replay: Can't reconstruct past states
- Coupling: Read/write optimized for same model

EVENT SOURCING APPROACH:
═══════════════════════
Events:
1. AccountOpened(user1, initial_deposit=500)
2. MoneyDeposited(user1, amount=300)
3. MoneyWithdrawn(user1, amount=100)
4. InterestApplied(user1, amount=300)

Current state = replay(events) → balance = 1000

Benefits:
✓ Complete audit trail (every change recorded)
✓ Time travel (state at any point)
✓ Replay (fix bugs, build new views)
✓ Event-driven (react to changes)
✓ Debugging (exactly what happened, when)
```

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────────────┐
│                    EVENT SOURCING + CQRS ARCHITECTURE                      │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  COMMAND SIDE (Write)                    QUERY SIDE (Read)                 │
│  ═══════════════════                     ════════════════                  │
│                                                                           │
│  ┌──────────────┐                        ┌──────────────────┐            │
│  │   Command    │                        │   Query API       │            │
│  │   (Write)    │                        │   (Read)          │            │
│  └──────┬───────┘                        └──────┬───────────┘            │
│         │                                        │                        │
│  ┌──────▼───────┐                        ┌──────▼───────────┐            │
│  │  Command     │                        │  Read Model       │            │
│  │  Handler     │                        │  (Optimized for   │            │
│  │  • Validate  │                        │   specific query)  │           │
│  │  • Business  │                        │                    │           │
│  │    rules     │                        │  • Denormalized    │            │
│  └──────┬───────┘                        │  • Pre-computed    │            │
│         │                                │  • Cached          │            │
│  ┌──────▼───────┐                        └──────▲───────────┘            │
│  │  Event       │                               │                         │
│  │  Store       │───── Events published ────────┘                         │
│  │  (Append     │      via Event Bus                                      │
│  │   Only)      │      (Kafka/EventStore)                                 │
│  │              │                                                         │
│  │  • Immutable │        ┌───────────────────────────┐                    │
│  │  • Ordered   │        │  PROJECTION (Event Handler)│                   │
│  │  • Complete  │        │  • Listens to events       │                   │
│  └──────────────┘        │  • Updates read model      │                   │
│                          │  • Eventually consistent   │                    │
│                          └───────────────────────────┘                    │
│                                                                           │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## Scalability

```
WRITE SIDE:
- Event store is append-only → sequential writes → FAST
- Partition by aggregate ID → independent streams
- Kafka as event store: millions of writes/sec
- No contention between different aggregates

READ SIDE:
- Multiple read models for different query patterns
- Each read model independently scalable
- Cache-friendly (immutable events → predictable updates)
- Can rebuild any read model by replaying events

EVENTUAL CONSISTENCY:
- Write confirmed immediately (event stored)
- Read model updated asynchronously (milliseconds typical)
- For strong consistency: read from event store directly
```

---

## Runnable Example

```python
"""
Event Sourcing + CQRS for Banking System
==========================================
Complete implementation showing:
- Event store with append-only semantics
- Command handlers with validation
- Multiple read models (projections)
- Event replay for state reconstruction
- Snapshot optimization

Run: python event_sourcing_cqrs.py
"""

import time
import json
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from collections import defaultdict
from enum import Enum
import uuid


# ============================================================================
# EVENTS (Immutable facts that happened)
# ============================================================================

@dataclass(frozen=True)
class Event:
    """Base event - immutable record of something that happened"""
    event_id: str
    aggregate_id: str  # Which entity this event belongs to
    event_type: str
    data: dict
    timestamp: float
    version: int  # Sequence number within aggregate
    metadata: dict = field(default_factory=dict)


# Domain Events
class EventTypes:
    ACCOUNT_OPENED = "AccountOpened"
    MONEY_DEPOSITED = "MoneyDeposited"
    MONEY_WITHDRAWN = "MoneyWithdrawn"
    TRANSFER_INITIATED = "TransferInitiated"
    TRANSFER_COMPLETED = "TransferCompleted"
    ACCOUNT_FROZEN = "AccountFrozen"
    INTEREST_APPLIED = "InterestApplied"


# ============================================================================
# EVENT STORE (Append-only, immutable log)
# ============================================================================

class EventStore:
    """
    Append-only event store.
    
    Production implementations:
    - EventStoreDB (purpose-built)
    - Apache Kafka (with compacted topics)
    - PostgreSQL (with append-only table)
    - DynamoDB (with version as sort key)
    
    Key guarantees:
    - Immutable: Events never modified after write
    - Ordered: Events within aggregate have total order
    - Optimistic Concurrency: Version check prevents conflicts
    """
    
    def __init__(self):
        # Events stored by aggregate_id for fast lookup
        self.streams: Dict[str, List[Event]] = defaultdict(list)
        # Global ordered log (for projections)
        self.global_log: List[Event] = []
        # Subscribers (for CQRS projections)
        self.subscribers: List[callable] = []
        # Snapshots for performance
        self.snapshots: Dict[str, dict] = {}
    
    def append(self, aggregate_id: str, events: List[Event], 
               expected_version: int) -> None:
        """
        Append events with optimistic concurrency control.
        
        expected_version: The version we expect the aggregate to be at.
        If another write happened since we read, this will fail.
        This prevents lost updates without locking.
        """
        current_version = len(self.streams[aggregate_id])
        
        if current_version != expected_version:
            raise ConcurrencyError(
                f"Expected version {expected_version}, "
                f"but current is {current_version}. "
                f"Another command modified this aggregate."
            )
        
        for event in events:
            self.streams[aggregate_id].append(event)
            self.global_log.append(event)
            
            # Notify subscribers (projections)
            for subscriber in self.subscribers:
                subscriber(event)
    
    def get_events(self, aggregate_id: str, 
                   after_version: int = 0) -> List[Event]:
        """Get events for an aggregate, optionally after a version"""
        return self.streams[aggregate_id][after_version:]
    
    def get_all_events(self, after_position: int = 0) -> List[Event]:
        """Get all events globally (for rebuilding projections)"""
        return self.global_log[after_position:]
    
    def subscribe(self, handler: callable):
        """Subscribe to new events (for projections)"""
        self.subscribers.append(handler)
    
    def save_snapshot(self, aggregate_id: str, state: dict, version: int):
        """Save snapshot for performance (avoid replaying all events)"""
        self.snapshots[aggregate_id] = {
            'state': state,
            'version': version
        }
    
    def get_snapshot(self, aggregate_id: str) -> Optional[dict]:
        return self.snapshots.get(aggregate_id)


class ConcurrencyError(Exception):
    pass


# ============================================================================
# AGGREGATE (Domain model - rebuilds state from events)
# ============================================================================

class BankAccount:
    """
    Aggregate Root: BankAccount
    
    State is NEVER stored directly.
    State is computed by replaying events.
    
    Pattern:
    1. Load events from store
    2. Replay to get current state
    3. Validate command against current state
    4. If valid: produce new events
    5. Store new events (state updated lazily)
    """
    
    def __init__(self, account_id: str):
        self.account_id = account_id
        self.balance = 0.0
        self.is_frozen = False
        self.owner = ""
        self.opened_at = None
        self.transaction_count = 0
        self.version = 0
        self._pending_events: List[Event] = []
    
    def apply_event(self, event: Event):
        """Apply event to rebuild state (no side effects!)"""
        if event.event_type == EventTypes.ACCOUNT_OPENED:
            self.balance = event.data['initial_deposit']
            self.owner = event.data['owner']
            self.opened_at = event.timestamp
        
        elif event.event_type == EventTypes.MONEY_DEPOSITED:
            self.balance += event.data['amount']
            self.transaction_count += 1
        
        elif event.event_type == EventTypes.MONEY_WITHDRAWN:
            self.balance -= event.data['amount']
            self.transaction_count += 1
        
        elif event.event_type == EventTypes.ACCOUNT_FROZEN:
            self.is_frozen = True
        
        elif event.event_type == EventTypes.INTEREST_APPLIED:
            self.balance += event.data['amount']
        
        self.version = event.version
    
    @classmethod
    def load_from_events(cls, account_id: str, events: List[Event]) -> 'BankAccount':
        """Reconstruct account state by replaying events"""
        account = cls(account_id)
        for event in events:
            account.apply_event(event)
        return account
    
    # ─── Commands (business logic + validation) ───
    
    def deposit(self, amount: float, reference: str = "") -> List[Event]:
        """Command: Deposit money"""
        if self.is_frozen:
            raise ValueError("Account is frozen, cannot deposit")
        if amount <= 0:
            raise ValueError("Deposit amount must be positive")
        
        event = Event(
            event_id=str(uuid.uuid4()),
            aggregate_id=self.account_id,
            event_type=EventTypes.MONEY_DEPOSITED,
            data={'amount': amount, 'reference': reference},
            timestamp=time.time(),
            version=self.version + 1
        )
        self._pending_events.append(event)
        self.apply_event(event)
        return [event]
    
    def withdraw(self, amount: float, reference: str = "") -> List[Event]:
        """Command: Withdraw money"""
        if self.is_frozen:
            raise ValueError("Account is frozen, cannot withdraw")
        if amount <= 0:
            raise ValueError("Withdrawal amount must be positive")
        if amount > self.balance:
            raise ValueError(
                f"Insufficient funds. Balance: {self.balance}, Requested: {amount}"
            )
        
        event = Event(
            event_id=str(uuid.uuid4()),
            aggregate_id=self.account_id,
            event_type=EventTypes.MONEY_WITHDRAWN,
            data={'amount': amount, 'reference': reference},
            timestamp=time.time(),
            version=self.version + 1
        )
        self._pending_events.append(event)
        self.apply_event(event)
        return [event]
    
    def get_pending_events(self) -> List[Event]:
        events = self._pending_events[:]
        self._pending_events.clear()
        return events


# ============================================================================
# COMMAND HANDLER (Orchestrates command execution)
# ============================================================================

class BankCommandHandler:
    """
    Handles commands by:
    1. Loading aggregate from event store
    2. Executing command (produces events)
    3. Persisting events to store
    
    This is the "write side" of CQRS.
    """
    
    def __init__(self, event_store: EventStore):
        self.event_store = event_store
    
    def open_account(self, account_id: str, owner: str, 
                     initial_deposit: float) -> str:
        """Command: Open new account"""
        # Check account doesn't exist
        existing = self.event_store.get_events(account_id)
        if existing:
            raise ValueError(f"Account {account_id} already exists")
        
        event = Event(
            event_id=str(uuid.uuid4()),
            aggregate_id=account_id,
            event_type=EventTypes.ACCOUNT_OPENED,
            data={'owner': owner, 'initial_deposit': initial_deposit},
            timestamp=time.time(),
            version=0
        )
        
        self.event_store.append(account_id, [event], expected_version=0)
        return account_id
    
    def deposit(self, account_id: str, amount: float, 
                reference: str = "") -> None:
        """Command: Deposit to account"""
        events = self.event_store.get_events(account_id)
        account = BankAccount.load_from_events(account_id, events)
        
        new_events = account.deposit(amount, reference)
        self.event_store.append(
            account_id, new_events, expected_version=len(events)
        )
    
    def withdraw(self, account_id: str, amount: float, 
                 reference: str = "") -> None:
        """Command: Withdraw from account"""
        events = self.event_store.get_events(account_id)
        account = BankAccount.load_from_events(account_id, events)
        
        new_events = account.withdraw(amount, reference)
        self.event_store.append(
            account_id, new_events, expected_version=len(events)
        )


# ============================================================================
# READ MODELS / PROJECTIONS (CQRS Query Side)
# ============================================================================

class AccountBalanceProjection:
    """
    Read Model 1: Current balances (optimized for balance queries).
    
    This is a denormalized, pre-computed view that updates
    whenever new events arrive. Queries are O(1) lookups.
    """
    
    def __init__(self):
        self.balances: Dict[str, float] = {}
        self.owners: Dict[str, str] = {}
    
    def handle_event(self, event: Event):
        """Update projection when events occur"""
        if event.event_type == EventTypes.ACCOUNT_OPENED:
            self.balances[event.aggregate_id] = event.data['initial_deposit']
            self.owners[event.aggregate_id] = event.data['owner']
        elif event.event_type == EventTypes.MONEY_DEPOSITED:
            self.balances[event.aggregate_id] = \
                self.balances.get(event.aggregate_id, 0) + event.data['amount']
        elif event.event_type == EventTypes.MONEY_WITHDRAWN:
            self.balances[event.aggregate_id] = \
                self.balances.get(event.aggregate_id, 0) - event.data['amount']
    
    def get_balance(self, account_id: str) -> float:
        return self.balances.get(account_id, 0)
    
    def get_total_deposits(self) -> float:
        return sum(self.balances.values())


class TransactionHistoryProjection:
    """
    Read Model 2: Transaction history (optimized for statement queries).
    Different structure than balance projection - that's the power of CQRS.
    """
    
    def __init__(self):
        self.transactions: Dict[str, List[dict]] = defaultdict(list)
    
    def handle_event(self, event: Event):
        if event.event_type in [EventTypes.MONEY_DEPOSITED, 
                                 EventTypes.MONEY_WITHDRAWN]:
            self.transactions[event.aggregate_id].append({
                'type': 'credit' if event.event_type == EventTypes.MONEY_DEPOSITED else 'debit',
                'amount': event.data['amount'],
                'reference': event.data.get('reference', ''),
                'timestamp': datetime.fromtimestamp(event.timestamp).isoformat(),
            })
    
    def get_statement(self, account_id: str, last_n: int = 10) -> List[dict]:
        return self.transactions[account_id][-last_n:]


class DailyVolumeProjection:
    """
    Read Model 3: Daily transaction volumes (optimized for analytics).
    A completely different view of the same events.
    """
    
    def __init__(self):
        self.daily_volume: Dict[str, float] = defaultdict(float)
        self.daily_count: Dict[str, int] = defaultdict(int)
    
    def handle_event(self, event: Event):
        if event.event_type in [EventTypes.MONEY_DEPOSITED, 
                                 EventTypes.MONEY_WITHDRAWN]:
            day = datetime.fromtimestamp(event.timestamp).strftime('%Y-%m-%d')
            self.daily_volume[day] += event.data['amount']
            self.daily_count[day] += 1
    
    def get_daily_report(self) -> Dict[str, dict]:
        return {
            day: {'volume': vol, 'count': self.daily_count[day]}
            for day, vol in self.daily_volume.items()
        }


# ============================================================================
# DEMONSTRATION
# ============================================================================

def run_event_sourcing_demo():
    print("""
╔══════════════════════════════════════════════════════════════════╗
║       EVENT SOURCING + CQRS - BANKING SYSTEM DEMO               ║
╠══════════════════════════════════════════════════════════════════╣
║                                                                  ║
║  Demonstrates:                                                   ║
║  • Event sourcing (state from events)                            ║
║  • CQRS (separate read/write models)                             ║
║  • Multiple projections (same events, different views)           ║
║  • Time travel (state at any point)                              ║
║  • Audit trail (complete history)                                ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝
    """)
    
    # Setup
    store = EventStore()
    balance_view = AccountBalanceProjection()
    history_view = TransactionHistoryProjection()
    volume_view = DailyVolumeProjection()
    
    # Subscribe projections to events
    store.subscribe(balance_view.handle_event)
    store.subscribe(history_view.handle_event)
    store.subscribe(volume_view.handle_event)
    
    handler = BankCommandHandler(store)
    
    # ─── Execute commands ───
    print("=" * 60)
    print("EXECUTING COMMANDS (Write Side)")
    print("=" * 60)
    
    # Open accounts
    handler.open_account("ACC-001", "Alice Johnson", 5000.00)
    print("  Opened ACC-001 (Alice) with $5,000")
    
    handler.open_account("ACC-002", "Bob Smith", 3000.00)
    print("  Opened ACC-002 (Bob) with $3,000")
    
    # Transactions
    handler.deposit("ACC-001", 1500.00, "Salary")
    print("  Alice: Deposited $1,500 (Salary)")
    
    handler.withdraw("ACC-001", 200.00, "Coffee")
    print("  Alice: Withdrew $200 (Coffee)")
    
    handler.deposit("ACC-002", 800.00, "Freelance")
    print("  Bob: Deposited $800 (Freelance)")
    
    handler.withdraw("ACC-001", 500.00, "Rent")
    print("  Alice: Withdrew $500 (Rent)")
    
    handler.deposit("ACC-001", 3000.00, "Bonus")
    print("  Alice: Deposited $3,000 (Bonus)")
    
    # ─── Query projections (Read Side) ───
    print(f"\n{'=' * 60}")
    print("QUERYING PROJECTIONS (Read Side - CQRS)")
    print("=" * 60)
    
    # Balance view
    print(f"\n  [Projection 1: Account Balances]")
    print(f"  Alice balance: ${balance_view.get_balance('ACC-001'):,.2f}")
    print(f"  Bob balance: ${balance_view.get_balance('ACC-002'):,.2f}")
    print(f"  Total deposits in system: ${balance_view.get_total_deposits():,.2f}")
    
    # Transaction history
    print(f"\n  [Projection 2: Transaction History]")
    statement = history_view.get_statement("ACC-001")
    for txn in statement:
        print(f"    {txn['type']:>6}: ${txn['amount']:>8,.2f} - {txn['reference']}")
    
    # Volume analytics
    print(f"\n  [Projection 3: Daily Volume Analytics]")
    report = volume_view.get_daily_report()
    for day, data in report.items():
        print(f"    {day}: ${data['volume']:,.2f} across {data['count']} transactions")
    
    # ─── Time Travel ───
    print(f"\n{'=' * 60}")
    print("TIME TRAVEL (Reconstruct Past State)")
    print("=" * 60)
    
    events = store.get_events("ACC-001")
    print(f"\n  Alice's complete event history ({len(events)} events):")
    for i, event in enumerate(events):
        print(f"    [{i}] {event.event_type}: {event.data}")
    
    # Reconstruct state at different points
    for version in [1, 3, len(events)]:
        account = BankAccount.load_from_events("ACC-001", events[:version])
        print(f"\n  State at version {version}: balance = ${account.balance:,.2f}")
    
    # ─── Demonstrate conflict detection ───
    print(f"\n{'=' * 60}")
    print("CONCURRENCY CONTROL (Optimistic Locking)")
    print("=" * 60)
    
    try:
        # Simulate concurrent modification
        store.append("ACC-001", [Event(
            event_id=str(uuid.uuid4()),
            aggregate_id="ACC-001",
            event_type=EventTypes.MONEY_DEPOSITED,
            data={'amount': 100},
            timestamp=time.time(),
            version=2  # Wrong! Current version is higher
        )], expected_version=2)  # Stale version
    except ConcurrencyError as e:
        print(f"  Conflict detected: {e}")
        print(f"  This prevents lost updates without pessimistic locking!")
    
    print(f"\n{'=' * 60}")
    print("KEY INSIGHTS")
    print("=" * 60)
    print("""
  1. EVENT STORE is the single source of truth
  2. READ MODELS are disposable - rebuild anytime by replaying events
  3. DIFFERENT QUERIES get different optimized models (CQRS)
  4. TIME TRAVEL is free - just replay to any point
  5. AUDIT TRAIL is complete - every change recorded
  6. SCALING: Write side scales by partitioning aggregates
             Read side scales independently (replicas, caching)
    """)


if __name__ == '__main__':
    run_event_sourcing_demo()
```

