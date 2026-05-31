# 02 — State Machines

> Complete lifecycle state diagrams for Orders and Payments in the OMS platform

---

## Order State Machine

### States

| State | Description | Terminal? |
|-------|-------------|-----------|
| `CREATED` | Order created, no payment initiated | No |
| `PENDING` | Payment in progress (auth challenged, UPI collect sent) | No |
| `ATTEMPTED` | Previous payment failed, merchant can retry | No |
| `AUTHORIZED` | Pre-auth successful, awaiting capture | No |
| `PROCESSED` | Payment captured successfully | Yes* |
| `CANCEL_REQUESTED` | Cancellation in progress | No |
| `CANCELLED` | Fully cancelled / voided | Yes |
| `FAILED` | Terminal failure (all attempts exhausted) | Yes |
| `SETTLED` | Post-capture settlement confirmed by acquirer | Yes |
| `SETTLEMENT_REJECTED` | Settlement rejected — triggers auto-reversal | Yes |

*PROCESSED is functionally terminal but can transition to SETTLED/SETTLEMENT_REJECTED via MIS settlement events.

### Order State Diagram

```mermaid
stateDiagram-v2
    [*] --> CREATED: POST /orders (Create Order)

    CREATED --> PENDING: Payment initiated<br/>(challenge/collect)
    CREATED --> PROCESSED: Payment captured<br/>(instant success)
    CREATED --> FAILED: Validation failure

    PENDING --> PROCESSED: Payment authorized + captured
    PENDING --> AUTHORIZED: Pre-auth success
    PENDING --> ATTEMPTED: Payment failed<br/>(retryable)
    PENDING --> CANCEL_REQUESTED: Cancel requested
    PENDING --> FAILED: All attempts exhausted

    ATTEMPTED --> PENDING: Retry payment initiated
    ATTEMPTED --> CANCEL_REQUESTED: Cancel requested
    ATTEMPTED --> FAILED: Terminate (long pending)

    AUTHORIZED --> PROCESSED: Capture success
    AUTHORIZED --> CANCEL_REQUESTED: Void requested
    AUTHORIZED --> FAILED: Capture failed<br/>(non-retryable)

    CANCEL_REQUESTED --> CANCELLED: Void/cancel confirmed
    CANCEL_REQUESTED --> PROCESSED: Cancel failed<br/>(already captured)

    PROCESSED --> SETTLED: MIS settlement confirmed
    PROCESSED --> SETTLEMENT_REJECTED: MIS settlement rejected<br/>(triggers auto-refund)

    FAILED --> [*]
    CANCELLED --> [*]
    SETTLED --> [*]
    SETTLEMENT_REJECTED --> [*]
```

### Order State Transition Rules

```mermaid
graph LR
    subgraph "Can Initiate Payment"
        CREATED
        PENDING
        ATTEMPTED
    end

    subgraph "Can Capture"
        AUTHORIZED
    end

    subgraph "Can Cancel/Void"
        CREATED_C[CREATED]
        PENDING_C[PENDING]
        ATTEMPTED_C[ATTEMPTED]
        AUTHORIZED_C[AUTHORIZED]
    end

    subgraph "Can Terminate"
        CREATED_T[CREATED]
        PENDING_T[PENDING]
        ATTEMPTED_T[ATTEMPTED]
    end

    subgraph "Terminal States"
        PROCESSED_T[PROCESSED]
        CANCELLED_T[CANCELLED]
        FAILED_T[FAILED]
        SETTLED_T[SETTLED]
    end
```

### Transition Guards (from code)

| From | To | Guard Condition |
|------|-----|-----------------|
| `CREATED` → `PENDING` | Payment created with challenge URL |
| `CREATED` → `PROCESSED` | Synchronous payment success (no 3DS/OTP) |
| `PENDING` → `PENDING` | New payment on same order (cancel old + create new) |
| `PENDING` → `AUTHORIZED` | `order.preAuth == true` AND authorization success |
| `PENDING` → `ATTEMPTED` | Payment failed but order allows retry |
| `PENDING` → `PROCESSED` | `order.preAuth == false` AND authorization success |
| `AUTHORIZED` → `PROCESSED` | `capturePayment()` success |
| `AUTHORIZED` → `CANCEL_REQUESTED` | Void initiated OR late auth expired |
| `CANCEL_REQUESTED` → `CANCELLED` | All payments voided/cancelled |
| `PROCESSED` → `SETTLED` | MIS settlement event status = SUCCESS |
| `PROCESSED` → `SETTLEMENT_REJECTED` | MIS settlement event status = REJECTED |

---

## Payment State Machine

### States

| State | Description | Terminal? |
|-------|-------------|-----------|
| `INITIATED` | Payment record created | No |
| `AUTHENTICATION_CHALLENGED` | 3DS/OTP/UPI collect pending user action | No |
| `AUTHENTICATED` | User completed auth (3DS success, OTP verified) | No |
| `AUTHORIZED` | Pre-auth hold placed on card | No |
| `CAPTURE_REQUESTED` | Capture API called, awaiting confirmation | No |
| `CAPTURED` | Funds captured successfully | Yes |
| `CANCEL_REQUESTED` | Cancel in progress | No |
| `CANCELLED` | Payment cancelled | Yes |
| `VOID_REQUESTED` | Void in progress (pre-auth reversal) | No |
| `VOID` | Authorization voided | Yes |
| `FAILED` | Payment failed | Yes |
| `REFUND_REQUESTED` | Refund initiated | No |

### Payment State Diagram

```mermaid
stateDiagram-v2
    [*] --> INITIATED: Payment created

    INITIATED --> AUTHENTICATION_CHALLENGED: Challenge URL returned<br/>(3DS / OTP / UPI Collect)
    INITIATED --> CAPTURED: Instant capture<br/>(no auth required)
    INITIATED --> FAILED: Gateway error /<br/>validation failure
    INITIATED --> CANCELLED: Cancelled before processing

    AUTHENTICATION_CHALLENGED --> AUTHENTICATED: User completes auth<br/>(3DS callback / OTP submit)
    AUTHENTICATION_CHALLENGED --> FAILED: Auth timeout / user abort
    AUTHENTICATION_CHALLENGED --> CANCEL_REQUESTED: User/merchant cancels

    AUTHENTICATED --> AUTHORIZED: Pre-auth mode
    AUTHENTICATED --> CAPTURED: Non-pre-auth mode<br/>(direct capture)
    AUTHENTICATED --> FAILED: Authorization declined

    AUTHORIZED --> CAPTURE_REQUESTED: Merchant calls capture
    AUTHORIZED --> VOID_REQUESTED: Merchant voids / late auth
    AUTHORIZED --> FAILED: Auth expired

    CAPTURE_REQUESTED --> CAPTURED: Capture confirmed
    CAPTURE_REQUESTED --> FAILED: Capture declined
    CAPTURE_REQUESTED --> CAPTURE_REQUESTED: Retry (server error)

    VOID_REQUESTED --> VOID: Void confirmed
    VOID_REQUESTED --> VOID_REQUESTED: Retry (server error)

    CANCEL_REQUESTED --> CANCELLED: Cancel confirmed
    CANCEL_REQUESTED --> FAILED: Cancel failed

    CAPTURED --> REFUND_REQUESTED: Refund initiated
    REFUND_REQUESTED --> CAPTURED: Refund processed<br/>(on refund ORDER)

    FAILED --> [*]
    CANCELLED --> [*]
    VOID --> [*]
    CAPTURED --> [*]
```

### Payment State Transition Matrix

| Current State | Allowed Next States | Trigger |
|---------------|-------------------|---------|
| `INITIATED` | `AUTHENTICATION_CHALLENGED`, `CAPTURED`, `FAILED`, `CANCELLED` | `paymentSDK.createPayment()` response |
| `AUTHENTICATION_CHALLENGED` | `AUTHENTICATED`, `FAILED`, `CANCEL_REQUESTED` | Auth callback / timeout / cancel |
| `AUTHENTICATED` | `AUTHORIZED`, `CAPTURED`, `FAILED` | `paymentSDK.authorizePayment()` response |
| `AUTHORIZED` | `CAPTURE_REQUESTED`, `VOID_REQUESTED`, `FAILED` | Merchant capture / void / expiry |
| `CAPTURE_REQUESTED` | `CAPTURED`, `FAILED` | `paymentSDK.capturePayment()` response |
| `VOID_REQUESTED` | `VOID` | `paymentSDK.voidPayment()` response |
| `CANCEL_REQUESTED` | `CANCELLED`, `FAILED` | `paymentSDK.cancelPayment()` response |
| `CAPTURED` | `REFUND_REQUESTED` | Refund order created |

---

## Refund Order State Machine

Refund orders use the same `OrderStatus` enum but with refund-specific semantics:

```mermaid
stateDiagram-v2
    [*] --> CREATED: Refund order created<br/>(via RMS or settlement reversal)

    CREATED --> PENDING: processRefund() called

    PENDING --> PROCESSED: Acquirer confirms refund
    PENDING --> FAILED: Acquirer declines<br/>(non-retryable error)
    PENDING --> PENDING: Parked for retry<br/>(acquirer decline MRR000)
    PENDING --> CANCELLED: Terminated<br/>(long pending)

    state PARKED_STATE {
        [*] --> WAITING: Parked with new INITIATED payment
        WAITING --> RETRY: Recon triggered + retries available
        RETRY --> [*]: resumeOrder() → processRefund()
        WAITING --> EXHAUSTED: retryCount > maxAttempts (6)
    }

    PENDING --> PARKED_STATE: Acquirer decline<br/>(retryable code)
    PARKED_STATE --> PENDING: Retry attempt
    PARKED_STATE --> FAILED: Retries exhausted

    PROCESSED --> [*]
    FAILED --> [*]
    CANCELLED --> [*]
```

### Refund Payment States

| State | Meaning |
|-------|---------|
| `INITIATED` | Refund payment created (or retry payment for parked orders) |
| `REFUND_REQUESTED` | Sent to acquirer |
| `CAPTURED` | Refund confirmed by acquirer (mapped from REFUNDED) |
| `FAILED` | Refund declined |

---

## Combined Order + Payment State Correlation

```
┌─────────────────────────────────────────────────────────────────────────┐
│  ORDER STATE        │  PAYMENT STATE(S)         │  BUSINESS MEANING     │
├─────────────────────┼───────────────────────────┼───────────────────────┤
│  CREATED            │  (none)                   │  Order awaiting       │
│                     │                           │  first payment        │
├─────────────────────┼───────────────────────────┼───────────────────────┤
│  PENDING            │  INITIATED /              │  Payment in flight    │
│                     │  AUTH_CHALLENGED /        │                       │
│                     │  AUTHENTICATED            │                       │
├─────────────────────┼───────────────────────────┼───────────────────────┤
│  ATTEMPTED          │  FAILED + (previous)      │  Last attempt failed  │
│                     │                           │  can retry            │
├─────────────────────┼───────────────────────────┼───────────────────────┤
│  AUTHORIZED         │  AUTHORIZED               │  Pre-auth hold active │
├─────────────────────┼───────────────────────────┼───────────────────────┤
│  PROCESSED          │  CAPTURED                 │  Money collected      │
├─────────────────────┼───────────────────────────┼───────────────────────┤
│  CANCEL_REQUESTED   │  CANCEL_REQUESTED /       │  Cancellation in      │
│                     │  VOID_REQUESTED           │  progress             │
├─────────────────────┼───────────────────────────┼───────────────────────┤
│  CANCELLED          │  CANCELLED / VOID         │  Fully reversed       │
├─────────────────────┼───────────────────────────┼───────────────────────┤
│  FAILED             │  FAILED                   │  Terminal failure     │
└─────────────────────┴───────────────────────────┴───────────────────────┘
```

---

## Order Type Classification

```mermaid
graph TD
    subgraph "Order Types"
        CHARGE[CHARGE<br/>Standard purchase order]
        REFUND[REFUND<br/>References parent charge]
        ADD_MONEY[ADD_MONEY<br/>Brand wallet top-up]
    end

    subgraph "CHARGE Sub-types (via additionalDetails)"
        PRE_AUTH[Pre-Auth Order<br/>preAuth=true]
        SPLIT[Split Payment<br/>partPayment=true]
        DCC[DCC Order<br/>internationalCard=true]
        MCC[MCC Order<br/>mcc=true]
        PA_CB[Cross-Border<br/>paCb=true]
        MANDATE[UPI Mandate<br/>mandateInfo present]
    end

    CHARGE --> PRE_AUTH
    CHARGE --> SPLIT
    CHARGE --> DCC
    CHARGE --> MCC
    CHARGE --> PA_CB
    CHARGE --> MANDATE
```
