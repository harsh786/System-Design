# Saga Pattern

## 1. Problem Statement

In a monolithic architecture, a single database transaction guarantees ACID properties across multiple tables. When we decompose into microservices, each service owns its database (Database-per-Service pattern). A single business operation now spans multiple services and their databases.

**The fundamental problem**: How do we maintain data consistency across multiple services without distributed transactions?

### Why Not 2PC (Two-Phase Commit)?

```
Problems with 2PC in Microservices:

┌─────────────────────────────────────────────────────────┐
│  1. Synchronous & Blocking                              │
│     - All participants locked until commit/abort        │
│     - Latency = sum of all participant latencies        │
│                                                         │
│  2. Single Point of Failure                             │
│     - Coordinator crash = all participants blocked      │
│     - Requires complex recovery protocols               │
│                                                         │
│  3. Reduced Availability                                │
│     - System availability = product of all availabilities│
│     - 3 services at 99.9% = 99.7% combined             │
│                                                         │
│  4. Not Supported Across Heterogeneous Systems          │
│     - NoSQL databases often don't support XA            │
│     - Message brokers, REST APIs can't participate      │
│                                                         │
│  5. Scalability Bottleneck                              │
│     - Locks held across network boundaries              │
│     - Throughput limited by slowest participant         │
└─────────────────────────────────────────────────────────┘
```

### Long-Lived Business Transactions

Consider an e-commerce order that involves:
- Order Service → creates order
- Inventory Service → reserves stock
- Payment Service → charges customer
- Shipping Service → dispatches package
- Notification Service → sends confirmation

This transaction may span seconds to days. Holding distributed locks for this duration is impractical.

---

## 2. Definition

> **A Saga is a sequence of local transactions where each local transaction updates a single service's database and publishes an event/message to trigger the next local transaction. If any local transaction fails, the saga executes a series of compensating transactions to undo the changes made by the preceding local transactions.**

```
                          SAGA CONCEPTUAL MODEL

    T1          T2          T3          T4          T5
  ┌─────┐    ┌─────┐    ┌─────┐    ┌─────┐    ┌─────┐
  │Local│───▶│Local│───▶│Local│───▶│Local│───▶│Local│
  │Txn 1│    │Txn 2│    │Txn 3│    │Txn 4│    │Txn 5│
  └─────┘    └─────┘    └─────┘    └─────┘    └─────┘
     │           │           │
     ▼           ▼           ▼
  ┌─────┐    ┌─────┐    ┌─────┐
  │Comp │    │Comp │    │Comp │        (T4, T5 are retriable -
  │C1   │◀───│C2   │◀───│C3   │         no compensation needed)
  └─────┘    └─────┘    └─────┘

  ─────────────────────────────────────────────────────────────
  HAPPY PATH:   T1 → T2 → T3 → T4 → T5 → SUCCESS

  FAILURE AT T3: T1 → T2 → T3(fail) → C2 → C1 → ABORTED
```

### Key Properties

| Property | Description |
|----------|-------------|
| **ACD** | Atomicity, Consistency, Durability (no Isolation) |
| **Eventually Consistent** | System reaches consistent state after saga completes |
| **Local ACID** | Each step is a local ACID transaction |
| **Semantic Undo** | Compensations are business-level reversals |

---

## 3. Two Coordination Approaches

### 3a. Choreography (Event-Based)

Each service listens for events and decides locally what to do next. There is no central coordinator — services react to domain events published by other services.

```
              CHOREOGRAPHY - EVENT-BASED SAGA

  ┌──────────┐   OrderCreated   ┌───────────────┐
  │  Order   │─────────────────▶│   Inventory   │
  │ Service  │                  │   Service     │
  └──────────┘                  └───────────────┘
       ▲                              │
       │                              │ InventoryReserved
       │                              ▼
       │                        ┌───────────────┐
       │                        │   Payment     │
       │                        │   Service     │
       │                        └───────────────┘
       │                              │
       │                              │ PaymentProcessed
       │                              ▼
       │                        ┌───────────────┐
       │   OrderCompleted       │   Shipping    │
       │◀───────────────────────│   Service     │
       │                        └───────────────┘
       │
       │         FAILURE SCENARIO (Payment Fails)
       │
  ┌──────────┐  PaymentFailed   ┌───────────────┐
  │  Order   │◀─────────────────│   Payment     │
  │ Service  │                  │   Service     │
  │(cancels) │                  └───────────────┘
  └──────────┘                        │
                                      │ PaymentFailed
                                      ▼
                                ┌───────────────┐
                                │   Inventory   │
                                │   Service     │
                                │  (releases)   │
                                └───────────────┘
```

**Detailed Event Flow:**

```
  Order        Event Bus       Inventory      Payment       Shipping
  Service                      Service        Service       Service
    │                              │              │              │
    │──OrderCreated───────────────▶│              │              │
    │                              │              │              │
    │                              │──InventoryReserved─────────▶│ (ignored)
    │                              │──InventoryReserved──▶│      │
    │                              │              │       │      │
    │                              │              │◀──────┘      │
    │                              │              │              │
    │◀─────────────PaymentProcessed───────────────│              │
    │                              │              │──PaymentProcessed──▶│
    │                              │              │              │
    │◀────────────────────────────────────────OrderShipped───────│
    │                              │              │              │
    ▼                              ▼              ▼              ▼
```

**Advantages:**
- Loose coupling — services only know about events, not each other
- Simple to implement for 2-4 step sagas
- No single point of failure in coordination
- Each service is autonomous and independently deployable
- Natural fit for event-driven architectures

**Disadvantages:**
- Difficult to understand the overall flow (scattered across services)
- Risk of cyclic event dependencies
- Hard to debug — requires distributed tracing (correlation IDs)
- Adding new steps requires modifying existing services' event handlers
- No single place to see saga state or progress
- Testing requires complex integration test setups

---

### 3b. Orchestration (Command-Based)

A central **Saga Orchestrator** (sometimes called Saga Execution Coordinator - SEC) tells each participant what to do and when. It maintains a state machine representing the saga's progress.

```
              ORCHESTRATION - COMMAND-BASED SAGA

                    ┌─────────────────────┐
                    │   SAGA ORCHESTRATOR  │
                    │                     │
                    │  ┌───────────────┐  │
                    │  │ State Machine │  │
                    │  │               │  │
                    │  │ Step1 ──────┐ │  │
                    │  │ Step2 ──────┤ │  │
                    │  │ Step3 ──────┤ │  │
                    │  │ Step4 ──────┘ │  │
                    │  └───────────────┘  │
                    └─────────┬───────────┘
                              │
            ┌─────────────────┼─────────────────┐
            │                 │                 │
            ▼                 ▼                 ▼
     ┌────────────┐   ┌────────────┐   ┌────────────┐
     │  Order     │   │ Inventory  │   │  Payment   │
     │  Service   │   │  Service   │   │  Service   │
     └────────────┘   └────────────┘   └────────────┘


  COMMAND/REPLY FLOW:

  Orchestrator          Order           Inventory        Payment
       │                  │                 │               │
       │──CreateOrder────▶│                 │               │
       │◀─OrderCreated────│                 │               │
       │                  │                 │               │
       │──ReserveInventory──────────────────▶               │
       │◀─InventoryReserved─────────────────│               │
       │                  │                 │               │
       │──ProcessPayment────────────────────────────────────▶
       │◀─PaymentProcessed──────────────────────────────────│
       │                  │                 │               │
       │──ApproveOrder───▶│                 │               │
       │◀─OrderApproved───│                 │               │
       │                  │                 │               │
       ▼                  ▼                 ▼               ▼


  COMPENSATION FLOW (Payment Fails):

  Orchestrator          Order           Inventory        Payment
       │                  │                 │               │
       │──CreateOrder────▶│                 │               │
       │◀─OrderCreated────│                 │               │
       │                  │                 │               │
       │──ReserveInventory──────────────────▶               │
       │◀─InventoryReserved─────────────────│               │
       │                  │                 │               │
       │──ProcessPayment────────────────────────────────────▶
       │◀─PaymentFailed─────────────────────────────────────│
       │                  │                 │               │
       │──ReleaseInventory──────────────────▶  (Compensate) │
       │◀─InventoryReleased─────────────────│               │
       │                  │                 │               │
       │──CancelOrder────▶│                 │  (Compensate) │
       │◀─OrderCancelled──│                 │               │
       │                  │                 │               │
       ▼                  ▼                 ▼               ▼
```

**Advantages:**
- Clear, centralized view of the entire saga flow
- Easy to add/remove/reorder steps
- Simpler to test — orchestrator logic is in one place
- Better error handling and monitoring
- Saga state is always queryable
- Avoids cyclic dependencies between services

**Disadvantages:**
- Risk of centralizing too much business logic in the orchestrator
- Orchestrator is a coordination single point of failure (mitigate with HA)
- Services become somewhat coupled to the orchestrator's command protocol
- Additional infrastructure component to deploy and maintain

---

## 4. Compensating Transactions

Compensating transactions are the mechanism by which sagas achieve atomicity without distributed locks. They are **semantic undos** — not database rollbacks.

### Properties of Compensating Transactions

```
┌─────────────────────────────────────────────────────────────────┐
│                  COMPENSATING TRANSACTION RULES                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  1. IDEMPOTENT                                                    │
│     - Must produce same result if executed multiple times         │
│     - Network failures may cause retries                          │
│     - Use idempotency keys / deduplication                        │
│                                                                   │
│  2. COMMUTATIVE (ideally)                                         │
│     - Order of compensation shouldn't affect final state          │
│     - In practice, reverse order is preferred but not mandatory   │
│                                                                   │
│  3. SEMANTIC UNDO                                                 │
│     - "Refund $50" not "DELETE FROM payments WHERE..."            │
│     - Creates NEW compensating record, doesn't delete original    │
│     - Maintains audit trail                                       │
│                                                                   │
│  4. CANNOT FAIL (must eventually succeed)                         │
│     - Must be retriable until success                             │
│     - If compensation fails, manual intervention needed           │
│     - Design compensations to be simpler than forward actions     │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

### Semantic Undo Examples

| Forward Transaction | Compensation (Semantic Undo) | NOT This (Rollback) |
|---|---|---|
| Charge credit card $100 | Refund $100 to card | Delete payment record |
| Reserve 5 items in stock | Release 5 items back to available | Set stock = old value |
| Create shipping label | Cancel shipment, void label | Delete shipping record |
| Send reservation confirmation | Send cancellation notice | — (can't unsend) |
| Debit account | Credit account | Revert balance |

### Non-Compensatable Operations

Some operations cannot be undone:
- **Sending emails/SMS** — can only send follow-up "please disregard"
- **Physical shipment dispatched** — can only initiate return
- **Third-party API calls with side effects** — depends on their API
- **Published events consumed by external systems** — can only publish correction events

**Strategy**: Place non-compensatable operations as late as possible in the saga (after the pivot transaction).

### Forward Recovery vs Backward Recovery

```
  BACKWARD RECOVERY (Compensation):
  ─────────────────────────────────
  T1 → T2 → T3(FAIL) → C2 → C1 → ABORTED

  Used when: a step fails BEFORE the pivot transaction.
  Undoes all previously completed steps in reverse order.


  FORWARD RECOVERY (Retry):
  ─────────────────────────
  T1 → T2 → T3(pivot) → T4(FAIL) → retry T4 → T5 → COMPLETED

  Used when: a step fails AFTER the pivot transaction.
  The saga is committed to completing; retriable steps are retried
  until they succeed (with backoff + dead letter after max retries).
```

---

## 5. Saga Execution States

```
                    SAGA STATE MACHINE

                        ┌───────┐
                        │STARTED│
                        └───┬───┘
                            │
                            ▼
                  ┌─────────────────────┐
             ┌───│      RUNNING        │───┐
             │   │  (executing steps)   │   │
             │   └─────────────────────┘   │
             │              │               │
        Step Fails     All Steps        Network
        (before pivot) Succeed          Timeout
             │              │               │
             ▼              ▼               ▼
    ┌────────────────┐ ┌────────┐  ┌──────────────┐
    │  COMPENSATING  │ │COMPLETED│  │   UNKNOWN    │
    │(running comps) │ │(success)│  │(needs check) │
    └───────┬────────┘ └────────┘  └──────┬───────┘
            │                              │
            ├──────────────────────────────┘
            │         (resolved after check)
            ▼
   ┌────────────────────┐
   │  All compensations │──YES──▶ ┌────────┐
   │  succeeded?        │         │ ABORTED│
   └────────┬───────────┘         │(rolled │
            │                     │ back)  │
            NO                    └────────┘
            │
            ▼
   ┌─────────────────┐
   │  FAILED         │
   │  (compensation  │
   │   failed -      │
   │   MANUAL FIX)   │
   └─────────────────┘


  DETAILED STATE TRANSITIONS:
  ═══════════════════════════

  STARTED ──────────────▶ RUNNING
                            │
                ┌───────────┼────────────────┐
                │           │                │
                ▼           ▼                ▼
          COMPENSATING   COMPLETED       TIMED_OUT
                │                           │
                ├───────────────────────────▶│
                ▼                            ▼
          ┌──────────┐               ┌────────────┐
          │ ABORTED  │               │   FAILED   │
          │(clean)   │               │(dirty-needs│
          └──────────┘               │ manual fix)│
                                     └────────────┘
```

### State Descriptions

| State | Description | Actions |
|-------|-------------|---------|
| **STARTED** | Saga instance created, not yet executing | Initialize state, persist saga ID |
| **RUNNING** | Forward transactions executing sequentially | Execute next step, handle responses |
| **COMPENSATING** | A step failed; running compensations in reverse | Execute compensations, track progress |
| **COMPLETED** | All forward transactions succeeded | Mark complete, cleanup |
| **ABORTED** | All compensations succeeded; saga cleanly rolled back | Log outcome, notify |
| **FAILED** | Compensation itself failed; inconsistent state | Alert ops, manual intervention |
| **TIMED_OUT** | No response within deadline | Check participant, decide retry or compensate |

---

## 6. Transaction Classification

Every step in a saga is classified into one of three types:

```
  ┌─────────────────────────────────────────────────────────────────┐
  │                    TRANSACTION TYPES IN A SAGA                    │
  ├─────────────────────────────────────────────────────────────────┤
  │                                                                   │
  │   COMPENSATABLE        PIVOT              RETRIABLE               │
  │   TRANSACTIONS      TRANSACTION          TRANSACTIONS             │
  │                                                                   │
  │   ┌───┐ ┌───┐       ┌───────┐          ┌───┐ ┌───┐             │
  │   │T1 │ │T2 │       │  T3   │          │T4 │ │T5 │             │
  │   └─┬─┘ └─┬─┘       └───┬───┘          └─┬─┘ └─┬─┘             │
  │     │     │              │                │     │               │
  │     ▼     ▼              ▼                │     │               │
  │   ┌───┐ ┌───┐      GO/NO-GO             │     │               │
  │   │C1 │ │C2 │       POINT               No compensation        │
  │   └───┘ └───┘                            needed - will          │
  │                                          eventually succeed      │
  │   Can be undone     If succeeds:         with retries           │
  │   via compensation  saga WILL complete                           │
  │                     If fails:                                     │
  │                     saga compensates                              │
  │                                                                   │
  └─────────────────────────────────────────────────────────────────┘

  TIMELINE:
  ═════════

  ◀──── COMPENSATABLE ────▶◀─ PIVOT ─▶◀──── RETRIABLE ────▶

       Can go backward         ↕          Must go forward
       (undo allowed)      Decision       (retry until success)
                            Point
```

### Detailed Definitions

**Compensatable Transactions:**
- Occur before the pivot
- Each has a corresponding compensating transaction
- If the saga needs to abort, these are undone in reverse order
- Example: Reserve inventory (compensate: release inventory)

**Pivot Transaction:**
- The point of no return — the go/no-go decision
- If it succeeds, the saga is committed to completing
- If it fails, the saga compensates all prior steps
- Often the most critical business decision (e.g., charging payment)
- There is exactly ONE pivot transaction per saga

**Retriable Transactions:**
- Occur after the pivot
- Guaranteed to eventually succeed (by design)
- No compensation needed — if they fail, they are retried
- Must be idempotent (will be retried on failure)
- Example: Send confirmation email, update read model

---

## 7. Detailed Example: E-Commerce Order Saga

### Saga Definition

```
  E-COMMERCE ORDER SAGA
  ═════════════════════

  Step │ Service     │ Action              │ Type          │ Compensation
  ─────┼─────────────┼─────────────────────┼───────────────┼──────────────────
   1   │ Order       │ Create Order        │ Compensatable │ Cancel Order
   2   │ Inventory   │ Reserve Items       │ Compensatable │ Release Items
   3   │ Payment     │ Process Payment     │ PIVOT         │ Refund Payment
   4   │ Shipping    │ Create Shipment     │ Retriable     │ — (retry)
   5   │ Notification│ Send Confirmation   │ Retriable     │ — (retry)
```

### Happy Path

```
  HAPPY PATH - ALL STEPS SUCCEED
  ═══════════════════════════════

  Orchestrator     Order      Inventory    Payment     Shipping   Notification
       │             │            │           │            │            │
       │─CreateOrder▶│            │           │            │            │
       │◀─Created────│            │           │            │            │
       │             │            │           │            │            │
       │─ReserveItems────────────▶│           │            │            │
       │◀─Reserved───────────────│           │            │            │
       │             │            │           │            │            │
       │─ProcessPayment──────────────────────▶│            │            │
       │◀─PaymentOK──────────────────────────│            │            │
       │             │            │           │            │            │
       │    ═══════ PIVOT PASSED - COMMITTED TO COMPLETION ═══════     │
       │             │            │           │            │            │
       │─CreateShipment──────────────────────────────────▶│            │
       │◀─ShipmentCreated────────────────────────────────│            │
       │             │            │           │            │            │
       │─SendConfirmation─────────────────────────────────────────────▶│
       │◀─Sent────────────────────────────────────────────────────────│
       │             │            │           │            │            │
       │─ApproveOrder▶│           │           │            │            │
       │◀─Approved────│           │           │            │            │
       │             │            │           │            │            │
      ╔═╗           ╔═╗         ╔═╗         ╔═╗          ╔═╗          ╔═╗
      ║C║           ║ ║         ║ ║         ║ ║          ║ ║          ║ ║
      ║O║           ║ ║         ║ ║         ║ ║          ║ ║          ║ ║
      ║M║           ║ ║         ║ ║         ║ ║          ║ ║          ║ ║
      ║P║           ║ ║         ║ ║         ║ ║          ║ ║          ║ ║
      ╚═╝           ╚═╝         ╚═╝         ╚═╝          ╚═╝          ╚═╝
```

### Failure Path — Payment Fails (Before Pivot)

```
  FAILURE PATH - PAYMENT FAILS (BACKWARD RECOVERY)
  ═════════════════════════════════════════════════

  Orchestrator     Order      Inventory    Payment     Shipping   Notification
       │             │            │           │            │            │
       │─CreateOrder▶│            │           │            │            │
       │◀─Created────│            │           │            │            │
       │             │            │           │            │            │
       │─ReserveItems────────────▶│           │            │            │
       │◀─Reserved───────────────│           │            │            │
       │             │            │           │            │            │
       │─ProcessPayment──────────────────────▶│            │            │
       │◀─PAYMENT DECLINED───────────────────│            │            │
       │             │            │           │            │            │
       │    ═══════ PIVOT FAILED - COMPENSATING ═══════════════════     │
       │             │            │           │            │            │
       │─ReleaseItems────────────▶│           │            │            │
       │◀─Released───────────────│           │            │            │
       │             │            │           │            │            │
       │─CancelOrder▶│            │           │            │            │
       │◀─Cancelled──│            │           │            │            │
       │             │            │           │            │            │
      ╔═╗           ╔═╗         ╔═╗         ╔═╗                       
      ║A║           ║ ║         ║ ║         ║ ║                       
      ║B║           ║ ║         ║ ║         ║ ║                       
      ║O║           ║ ║         ║ ║         ║ ║                       
      ║R║           ║ ║         ║ ║         ║ ║                       
      ║T║           ║ ║         ║ ║         ║ ║                       
      ╚═╝           ╚═╝         ╚═╝         ╚═╝                       
```

### Failure Path — Shipping Fails (After Pivot, Forward Recovery)

```
  FAILURE PATH - SHIPPING FAILS (FORWARD RECOVERY / RETRY)
  ════════════════════════════════════════════════════════

  Orchestrator     Order      Inventory    Payment     Shipping
       │             │            │           │            │
       │  ... (steps 1-3 succeed, pivot passes) ...       │
       │             │            │           │            │
       │─CreateShipment──────────────────────────────────▶│
       │◀─SHIPPING_UNAVAILABLE───────────────────────────│
       │             │            │           │            │
       │  (wait 5s, retry)       │           │            │
       │─CreateShipment──────────────────────────────────▶│
       │◀─SHIPPING_UNAVAILABLE───────────────────────────│
       │             │            │           │            │
       │  (wait 15s, exponential backoff)    │            │
       │─CreateShipment──────────────────────────────────▶│
       │◀─ShipmentCreated────────────────────────────────│
       │             │            │           │            │
       │  (continues to step 5)  │           │            │
       ▼             ▼            ▼           ▼            ▼
```

---

## 8. Isolation Challenges

Sagas lack the **I** (Isolation) from ACID. Multiple sagas executing concurrently can interfere with each other.

### Anomalies

```
  ┌─────────────────────────────────────────────────────────────┐
  │                    ISOLATION ANOMALIES                        │
  ├─────────────────────────────────────────────────────────────┤
  │                                                               │
  │  1. DIRTY READS                                               │
  │     Saga A writes data, Saga B reads it, Saga A compensates  │
  │     → Saga B operated on data that was "rolled back"          │
  │                                                               │
  │     Timeline:                                                 │
  │     Saga A: ──[Reserve 5]──────────[Release 5 (compensate)]── │
  │     Saga B: ────────[Read stock: sees reserved]───────────    │
  │                                                               │
  │  2. LOST UPDATES                                              │
  │     Two sagas read same value, both update, one overwrites    │
  │                                                               │
  │     Saga A: ──[Read qty=10]────[Set qty=8]────────            │
  │     Saga B: ────[Read qty=10]──────[Set qty=7]────            │
  │     Result: qty=7 (Saga A's deduction lost)                   │
  │                                                               │
  │  3. NON-REPEATABLE READS (Fuzzy Reads)                        │
  │     Saga reads value twice, gets different results            │
  │                                                               │
  │     Saga A: ──[Read X=5]───────────[Read X=3]──── (confused)  │
  │     Saga B: ────────[Update X=3]──────────────────            │
  │                                                               │
  └─────────────────────────────────────────────────────────────┘
```

### Countermeasures

| Countermeasure | Description | Trade-off |
|---|---|---|
| **Semantic Lock** | Set a flag (e.g., `status=PENDING`) indicating data is part of an in-flight saga. Other sagas check this flag. | Requires application-level lock management |
| **Commutative Updates** | Design updates to be order-independent. E.g., `increment(5)` instead of `set(15)` | Not always possible |
| **Pessimistic View** | Reorder saga steps so reads happen in a safe order; read from services that have already committed | Limits saga step ordering |
| **Reread Value** | Before updating, reread the value and check it hasn't changed (optimistic locking) | Requires versioning support |
| **Version File** | Record operations in a log; reorder them for commutativity at apply time | Complex implementation |
| **By Value** | Use business risk as a criterion — low-risk requests use sagas, high-risk use distributed locks | Hybrid approach, harder to reason about |

### Semantic Lock Pattern Example

```
  ORDER STATUS AS SEMANTIC LOCK:
  ══════════════════════════════

  Create Order:   status = APPROVAL_PENDING   ← Semantic lock set
  Reserve Stock:  (checks order.status == APPROVAL_PENDING)
  Process Payment: ...
  Approve Order:  status = APPROVED           ← Lock released

  If another saga tries to modify this order:
    → Sees status = APPROVAL_PENDING
    → Knows a saga is in-flight
    → Either waits, retries later, or fails fast
```

---

## 9. Implementation Patterns

### 9.1 Transactional Outbox Pattern

Ensures reliable event publishing: the event is written to an outbox table in the SAME local transaction as the business data change.

```
  TRANSACTIONAL OUTBOX PATTERN
  ════════════════════════════

  ┌─────────────────────────────────────────────┐
  │           Service Database                   │
  │                                             │
  │   BEGIN TRANSACTION                         │
  │   ┌─────────────────────────────────────┐   │
  │   │ 1. UPDATE orders SET status='PAID'  │   │
  │   │ 2. INSERT INTO outbox (             │   │
  │   │      event_type='OrderPaid',        │   │
  │   │      payload='{"orderId": 123}',    │   │
  │   │      status='PENDING'               │   │
  │   │    )                                │   │
  │   └─────────────────────────────────────┘   │
  │   COMMIT                                    │
  │                                             │
  └──────────────────────┬──────────────────────┘
                         │
                         │  Outbox Relay (polling or CDC)
                         ▼
              ┌──────────────────────┐
              │    Message Broker    │
              │   (Kafka/RabbitMQ)   │
              └──────────────────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │   Next Service       │
              └──────────────────────┘

  Relay options:
  • Polling Publisher: SELECT * FROM outbox WHERE status='PENDING'
  • CDC (Change Data Capture): Debezium reads DB transaction log
```

### 9.2 Event Sourcing with Sagas

```
  EVENT SOURCING + SAGA
  ═════════════════════

  ┌─────────────────────────────────────────────────────────┐
  │                    Event Store                            │
  │                                                         │
  │  OrderAggregate-123:                                    │
  │    [OrderCreated] → [InventoryReserved] → [PaymentOK]  │
  │                                                         │
  │  Saga-456:                                              │
  │    [SagaStarted] → [Step1Done] → [Step2Done] → ...     │
  │                                                         │
  └─────────────────────────────────────────────────────────┘
       │
       │  Event handlers / projections
       ▼
  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
  │ Saga Manager│────▶│ Command Bus │────▶│  Services   │
  └─────────────┘     └─────────────┘     └─────────────┘

  Benefits:
  • Complete audit trail of saga execution
  • Replay capability for debugging
  • Natural event-driven flow
  • Saga state reconstructable from events
```

### 9.3 Saga State Store

```
  SAGA STATE STORE SCHEMA
  ═══════════════════════

  Table: saga_instances
  ┌──────────────┬────────────────┬───────────┬──────────────────┐
  │ saga_id (PK) │ saga_type      │ state     │ current_step     │
  ├──────────────┼────────────────┼───────────┼──────────────────┤
  │ uuid-001     │ OrderSaga      │ RUNNING   │ 3 (Payment)      │
  │ uuid-002     │ OrderSaga      │ COMPENSATE│ 2 (Inventory)    │
  │ uuid-003     │ OrderSaga      │ COMPLETED │ 5 (Done)         │
  └──────────────┴────────────────┴───────────┴──────────────────┘

  Table: saga_steps
  ┌──────────┬──────────┬───────────────┬────────┬─────────────────┐
  │ saga_id  │ step_num │ service       │ status │ response        │
  ├──────────┼──────────┼───────────────┼────────┼─────────────────┤
  │ uuid-001 │ 1        │ OrderService  │ DONE   │ {orderId: 42}   │
  │ uuid-001 │ 2        │ InventorySvc  │ DONE   │ {reserved: true}│
  │ uuid-001 │ 3        │ PaymentSvc    │ PENDING│ null            │
  └──────────┴──────────┴───────────────┴────────┴─────────────────┘
```

### 9.4 Idempotency Keys

```
  IDEMPOTENCY PATTERN
  ═══════════════════

  Client/Orchestrator                    Service
       │                                    │
       │─── Request ────────────────────────▶
       │    Header: Idempotency-Key: abc-123│
       │                                    │
       │    Service checks:                 │
       │    ┌────────────────────────────┐  │
       │    │ SELECT * FROM processed    │  │
       │    │ WHERE key = 'abc-123'      │  │
       │    │                            │  │
       │    │ IF EXISTS → return cached  │  │
       │    │ IF NOT   → process + store │  │
       │    └────────────────────────────┘  │
       │                                    │
       │◀── Response (same every time) ─────│
       │                                    │

  Table: idempotency_store
  ┌──────────────────┬──────────────┬───────────────┬───────────┐
  │ idempotency_key  │ created_at   │ response_body │ status    │
  ├──────────────────┼──────────────┼───────────────┼───────────┤
  │ abc-123          │ 2024-01-15   │ {"ok": true}  │ COMPLETED │
  │ def-456          │ 2024-01-15   │ null          │ PROCESSING│
  └──────────────────┴──────────────┴───────────────┴───────────┘
```

---

## 10. Real-World Implementations

### Uber — Cadence/Temporal

- **Use case**: Ride lifecycle (match driver → start ride → end ride → charge → pay driver)
- **Technology**: Cadence (later Temporal.io), built in-house
- **Scale**: Millions of concurrent workflows
- **Key insight**: Treat the saga as a durable function — code looks sequential but is persisted across failures

### Netflix — Conductor

- **Use case**: Media encoding pipelines, content onboarding
- **Technology**: Netflix Conductor (open-source orchestration engine)
- **Pattern**: JSON-defined workflow DAGs with compensation
- **Key insight**: Separation of workflow definition from execution

### Axon Framework (Java)

- **Use case**: Java/Kotlin enterprise applications
- **Technology**: CQRS + Event Sourcing + Saga support built-in
- **Pattern**: `@SagaEventHandler` annotations, automatic state management
- **Key insight**: Framework handles saga lifecycle, persistence, and correlation

### Eventuate Tram

- **Use case**: Microservices with relational databases
- **Technology**: Transactional outbox + saga orchestration
- **Pattern**: `SagaDefinition` DSL for defining steps and compensations
- **Key insight**: Combines outbox pattern with saga orchestration

### AWS Step Functions

- **Use case**: Cloud-native serverless sagas
- **Technology**: State machine as JSON (Amazon States Language)
- **Pattern**: Each state invokes Lambda; Catch/Retry for compensation
- **Key insight**: Fully managed — no infrastructure to run
- **Limitation**: 25,000 event history limit, cold starts

### Temporal.io

- **Use case**: Any long-running business process
- **Technology**: Durable execution engine (evolved from Uber Cadence)
- **Pattern**: Write workflows as normal code; framework handles persistence
- **Key insight**: Developer writes linear code, framework handles retries, timeouts, compensation
- **Scale**: Used by Stripe, HashiCorp, Snap, Datadog

### MassTransit (.NET)

- **Use case**: .NET microservices
- **Technology**: State machine-based sagas on top of RabbitMQ/Azure Service Bus
- **Pattern**: `MassTransitStateMachine<TState>` with Automatonymous
- **Key insight**: Saga state machine defined as code, persisted in DB

### Booking.com — Reservation Saga

- **Use case**: Multi-component booking (hotel + flight + car + insurance)
- **Pattern**: Orchestrated saga with deadlines and partial completion support
- **Key insight**: Not all-or-nothing — supports partial bookings with user choice

---

## 11. Saga vs 2PC vs TCC

### Comparison Table

```
  ┌─────────────────┬────────────────────┬────────────────────┬────────────────────┐
  │ Dimension       │ SAGA               │ 2PC                │ TCC                │
  ├─────────────────┼────────────────────┼────────────────────┼────────────────────┤
  │ Consistency     │ Eventually         │ Strong (ACID)      │ Eventually         │
  │                 │ consistent         │                    │ consistent         │
  ├─────────────────┼────────────────────┼────────────────────┼────────────────────┤
  │ Isolation       │ None (anomalies    │ Full (locks held   │ Partial (resources │
  │                 │ possible)          │ until commit)      │ reserved/frozen)   │
  ├─────────────────┼────────────────────┼────────────────────┼────────────────────┤
  │ Availability    │ High               │ Low (blocking)     │ Medium             │
  ├─────────────────┼────────────────────┼────────────────────┼────────────────────┤
  │ Latency         │ Low (async)        │ High (synchronous) │ Medium (3 phases)  │
  ├─────────────────┼────────────────────┼────────────────────┼────────────────────┤
  │ Scalability     │ High               │ Low                │ Medium             │
  ├─────────────────┼────────────────────┼────────────────────┼────────────────────┤
  │ Complexity      │ Business logic     │ Infrastructure     │ Both               │
  │                 │ (compensations)    │ (XA protocol)      │                    │
  ├─────────────────┼────────────────────┼────────────────────┼────────────────────┤
  │ Lock Duration   │ None (no locks)    │ Until commit       │ Until confirm/     │
  │                 │                    │                    │ cancel (short)     │
  ├─────────────────┼────────────────────┼────────────────────┼────────────────────┤
  │ Failure Mode    │ Compensation       │ Blocking (coord    │ Cancel phase       │
  │                 │ (eventually)       │ failure = stuck)   │ (timeout-based)    │
  ├─────────────────┼────────────────────┼────────────────────┼────────────────────┤
  │ Heterogeneous   │ Yes (any service)  │ No (XA required)   │ Yes (any service)  │
  │ Systems         │                    │                    │                    │
  ├─────────────────┼────────────────────┼────────────────────┼────────────────────┤
  │ Long-running    │ Yes (hours/days)   │ No (seconds max)   │ No (seconds max)   │
  │ Transactions    │                    │                    │                    │
  └─────────────────┴────────────────────┴────────────────────┴────────────────────┘
```

### TCC (Try-Confirm-Cancel) Explained

```
  TCC PATTERN:
  ════════════

  Phase 1: TRY       → Reserve/freeze resources (tentative)
  Phase 2: CONFIRM   → Commit all reservations (if all Try succeeded)
       OR: CANCEL    → Release all reservations (if any Try failed)

  Example (Transfer $100 from A to B):
    Try:     A.freeze($100), B.freeze(space for $100)
    Confirm: A.debit($100),  B.credit($100)
    Cancel:  A.unfreeze($100), B.unfreeze()
```

### When to Use Which

| Scenario | Recommended | Reason |
|----------|-------------|--------|
| Microservices, long-running (>seconds) | **Saga** | Non-blocking, handles long durations |
| Single database cluster, short txn | **2PC** | Simplest if infra supports XA |
| Financial transfers, short-lived | **TCC** | Better isolation than saga for money |
| Mixed async services (REST + queues) | **Saga** | Works across heterogeneous systems |
| Need strong consistency, can tolerate latency | **2PC** | Guarantees ACID |
| High throughput, eventual consistency OK | **Saga** | No locks = higher throughput |

---

## 12. Architect's Guide

### Design Principles

1. **Design compensations first** — Before implementing a saga step, define its compensation. If you can't define a compensation, reconsider the design.

2. **Minimize the number of saga participants** — Each participant adds complexity and failure modes. Combine steps where possible.

3. **Place non-compensatable steps after the pivot** — Emails, external notifications, and physical actions should occur only after the saga is committed.

4. **Make compensations simpler than forward actions** — A compensation that can fail is a nightmare. Keep them trivial.

5. **Use correlation IDs everywhere** — Every message in a saga must carry the saga ID for tracing and debugging.

6. **Set timeouts on every step** — No step should wait indefinitely. Define what happens on timeout (retry or compensate).

7. **Persist saga state before acting** — Write the intent to the saga store before sending commands to participants (crash recovery).

### Testing Strategies

```
  TESTING PYRAMID FOR SAGAS
  ═════════════════════════

          ╱╲
         ╱  ╲          End-to-End Tests
        ╱ E2E╲         • Full saga happy/failure paths
       ╱──────╲        • Real services, real messaging
      ╱        ╲
     ╱Integration╲     Integration Tests
    ╱──────────────╲   • Orchestrator + message broker
   ╱                ╲  • Verify compensation triggers
  ╱   Unit Tests     ╲ 
 ╱────────────────────╲ Unit Tests
╱                      ╲• Saga state machine transitions
                        • Individual compensation logic
                        • Idempotency of each step
```

**Key test scenarios:**
- Happy path completion
- Failure at each step → verify correct compensations fire
- Duplicate message delivery → verify idempotency
- Out-of-order messages → verify correct handling
- Timeout at each step → verify timeout behavior
- Concurrent sagas → verify isolation countermeasures
- Crash recovery → restart orchestrator mid-saga, verify resumption

### Monitoring & Observability

| Metric | Purpose |
|--------|---------|
| Saga completion rate | % of sagas that complete vs abort |
| Saga duration (p50, p95, p99) | Detect slowdowns |
| Compensation rate | How often sagas need to roll back |
| Step failure rate (per service) | Identify unreliable participants |
| Stuck sagas (no progress > threshold) | Alert for manual intervention |
| Compensation failure rate | Critical — indicates inconsistency |

**Required observability:**
- Distributed tracing with saga correlation ID
- Saga state dashboard (running, compensating, stuck, failed)
- Dead letter queue monitoring
- Alerting on compensation failures (these need immediate attention)

### Common Pitfalls

| Pitfall | Consequence | Mitigation |
|---------|-------------|------------|
| Non-idempotent compensations | Double-refunds, duplicate releases | Idempotency keys on all operations |
| Missing timeout handling | Sagas stuck forever in RUNNING state | Deadline per step + overall saga timeout |
| Compensation that can fail permanently | Inconsistent state, data corruption | Design compensations to always succeed; dead letter + manual fallback |
| Too many saga participants | Exponential failure modes | Combine services or break into sub-sagas |
| Forgetting semantic locks | Dirty reads between concurrent sagas | Status fields as application-level locks |
| No observability | Can't debug production issues | Correlation IDs, saga state store, dashboards |
| Orchestrator as monolith | All business logic migrates to orchestrator | Keep orchestrator thin — coordination only, no business rules |
| Ignoring partial failures | Inconsistent user experience | Always handle: success, failure, and unknown/timeout |

### Decision Framework

```
  SHOULD YOU USE A SAGA?
  ══════════════════════

  Does the operation span multiple services?
    NO  → Use local transaction
    YES ↓

  Is strong consistency absolutely required?
    YES → Consider 2PC (if feasible) or TCC
    NO  ↓

  Is the transaction long-running (>1 second)?
    YES → Saga (2PC would hold locks too long)
    NO  ↓

  Can you define compensations for each step?
    NO  → Reconsider service boundaries
    YES → Saga ✓

  Few steps (<4) with loose coupling?
    YES → Choreography
    NO  → Orchestration
```

---

## Summary

The Saga pattern trades ACID isolation for availability and scalability in distributed systems. It requires careful design of compensating transactions, awareness of isolation anomalies, and robust observability. Choose choreography for simple, loosely-coupled flows and orchestration for complex, multi-step business processes that need centralized monitoring and error handling.

**The golden rule**: If you can't define a reliable compensation for a step, you can't safely include it in a saga before the pivot point.
