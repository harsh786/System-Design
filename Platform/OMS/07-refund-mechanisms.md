# 07 — Refund Mechanisms

> Full/partial refunds, retry on acquirer decline, settlement reversal, and multi-service orchestration

---

## Refund Architecture Overview

Refunds in Platform V3 involve three services working together:

```mermaid
graph LR
    M[Merchant] -->|POST /refunds| RMS[Refund Management<br/>Service]
    RMS -->|PATCH /orders/{id}/refund| OMS[Payment Order<br/>Service]
    OMS -->|refundPayment| SDK[PaymentSDK]
    SDK --> GW[Gateway / Acquirer]

    RECON[Order-Recon] -->|reconcile| RMS
    RMS -->|reconcileOrder| OMS
    OMS -->|inquirePayment| SDK
```

| Service | Responsibility |
|---------|---------------|
| **RMS** | Validation, deduplication, lock management, refund entity storage |
| **OMS** | Refund order creation, gateway interaction, state management |
| **Order-Recon** | Async reconciliation of pending refunds |

---

## Flow 1: Merchant Initiates Refund (Full)

```mermaid
sequenceDiagram
    participant M as Merchant
    participant RMS as RMS
    participant Redis as Redis (Lock)
    participant OHS as Order History Service
    participant OMS as OMS
    participant SDK as PaymentSDK
    participant ACQ as Acquirer
    participant DB_RMS as RMS PostgreSQL
    participant DB_OMS as OMS PostgreSQL

    M->>RMS: POST /api/pay/v1/refunds/{orderId}<br/>{amount: 10000, reason: "customer_request"}
    activate RMS

    %% Validation Phase
    RMS->>RMS: Validate Merchant-ID header
    RMS->>RMS: Validate order ID format
    RMS->>DB_RMS: Check duplicate (merchantRefundReference)
    DB_RMS-->>RMS: No duplicate

    %% Lock + Fetch
    RMS->>Redis: acquireLock(parentOrderId)
    Redis-->>RMS: Lock acquired

    RMS->>OHS: GET parent order
    OHS-->>RMS: Parent Order (proto)

    %% Business Validation
    RMS->>RMS: Validate: captured payments exist
    RMS->>RMS: Validate: bank transfer not supported
    RMS->>RMS: Validate: currency match
    RMS->>RMS: Validate: refund window (not expired)
    RMS->>RMS: Validate: refund amount ≤ captured - already_refunded
    RMS->>RMS: Calculate refundType (FULL vs PARTIAL)

    %% Create + Process
    RMS->>DB_RMS: Create refund entity
    RMS->>OMS: PATCH /api/internal/pay/v1/orders/{parentOrderId}/refund<br/>{payments, refundType, additionalRefundData}
    activate OMS

    OMS->>DB_OMS: Create refund order (type=REFUND, parentOrderId)
    OMS->>OMS: processRefund()
    OMS->>SDK: refundPayment(refundRequest)
    SDK->>ACQ: Refund request
    ACQ-->>SDK: {status: REFUNDED}
    SDK-->>OMS: Right(response)

    OMS->>OMS: Mark refund payment CAPTURED
    OMS->>OMS: Mark refund order PROCESSED
    OMS->>DB_OMS: UPDATE + outbox
    OMS-->>RMS: Right(order)
    deactivate OMS

    RMS->>DB_RMS: Update refund status = PROCESSED
    RMS->>Redis: releaseLock
    RMS-->>M: 200 {refundId, status: PROCESSED}
    deactivate RMS
```

---

## Flow 2: Partial Refund

```mermaid
sequenceDiagram
    participant M as Merchant
    participant RMS as RMS
    participant OMS as OMS
    participant SDK as PaymentSDK

    M->>RMS: POST /refunds/{orderId}<br/>{amount: 3000}
    Note over RMS: Original order amount = 10000<br/>Already refunded = 0<br/>Remaining refundable = 10000

    RMS->>RMS: refundType = PARTIAL (3000 < 10000)
    RMS->>OMS: PATCH /orders/{orderId}/refund<br/>{amount: 3000, refundType: PARTIAL}

    OMS->>OMS: Create refund order (amount: 3000)
    OMS->>SDK: refundPayment(3000)
    SDK-->>OMS: REFUNDED
    OMS-->>RMS: PROCESSED

    RMS-->>M: 200 {refundAmount: 3000, status: PROCESSED}

    Note over M: Merchant can issue more partial refunds<br/>up to remaining 7000
```

---

## Flow 3: Refund Retry on Acquirer Decline

When an acquirer returns a retryable error code (e.g., `MRR000`), OMS parks the order for retry during reconciliation.

```mermaid
sequenceDiagram
    participant M as Merchant
    participant RMS as RMS
    participant OMS as OMS
    participant SDK as PaymentSDK
    participant ACQ as Acquirer
    participant DB as OMS DB
    participant RECON as Order-Recon SQS

    %% Initial attempt
    M->>RMS: POST /refunds/{orderId}
    RMS->>OMS: processRefund()
    OMS->>SDK: refundPayment()
    SDK->>ACQ: Refund request
    ACQ-->>SDK: Error (code: MRR000)
    SDK-->>OMS: Left(error)

    %% Error code check
    OMS->>OMS: handleRefundResponse()
    OMS->>OMS: isAcquirerDecline(MRR000) = true

    %% Park the order
    OMS->>OMS: handleAcquirerFailure()
    OMS->>OMS: Create new INITIATED payment<br/>Mark original FAILED
    OMS->>DB: failPendingPaymentAndCreateNewPayment()
    OMS-->>RMS: Right(order) — parked
    RMS-->>M: 200 {status: REQUESTED}

    Note over RECON: SQS pipeline picks up after delay

    %% Retry 1 (via recon)
    RECON->>RMS: reconcile(orderId)
    RMS->>OMS: reconcileOrder(isParked=false)
    OMS->>OMS: handleRefundParkedOrder()
    OMS->>OMS: retryCount = paymentModels.size = 2
    OMS->>OMS: validRetryCount(2 ≤ 6) = true
    OMS->>OMS: resumeOrder() → processRefund()
    OMS->>SDK: refundPayment() (retry)
    SDK->>ACQ: Refund request

    alt Success
        ACQ-->>SDK: REFUNDED
        OMS->>OMS: Mark PROCESSED
    else MRR000 again
        ACQ-->>SDK: Error MRR000
        OMS->>OMS: Park again (payment 3 created)
        Note over RECON: Continues until retry 6
    else Non-retryable error
        ACQ-->>SDK: Error (other code)
        OMS->>OMS: Mark FAILED permanently
    end
```

### Retry Configuration

```yaml
acquirer_error_code_config:
  card_acquirer_error_codes: "MRR000"      # For CARD, CREDIT_EMI
  sdk_acquirer_error_codes: "MRR000"       # For UPI, NB, Wallet, etc.

acquirer_decline_attempt_config:
  max_attempts: 6                          # Max payment models on order
```

### Retry State Machine

```mermaid
stateDiagram-v2
    [*] --> ATTEMPT_1: processRefund()

    ATTEMPT_1 --> PARKED_1: Acquirer returns MRR000
    PARKED_1 --> ATTEMPT_2: Recon triggered<br/>retryCount=2 ≤ 6

    ATTEMPT_2 --> PARKED_2: MRR000 again
    PARKED_2 --> ATTEMPT_3: retryCount=3 ≤ 6

    ATTEMPT_3 --> SUCCESS: Acquirer success
    ATTEMPT_3 --> PARKED_3: MRR000 again

    PARKED_3 --> ATTEMPT_N: ...continues...

    state ATTEMPT_6 {
        [*] --> CHECK: retryCount=6
        CHECK --> RETRY: 6 ≤ 6 ✓
        RETRY --> RESULT: processRefund()
    }

    ATTEMPT_6 --> PARKED_6: MRR000
    PARKED_6 --> EXHAUSTED: retryCount=7 > 6

    SUCCESS --> [*]: Order PROCESSED
    EXHAUSTED --> [*]: RETRIES_EXHAUSTED logged<br/>Order stays parked

    note right of PARKED_1
        Each park creates new
        INITIATED payment.
        retryCount = paymentModels.size
    end note
```

---

## Flow 4: Settlement Reversal (Auto-Refund)

When MIS settlement processing detects a `SETTLEMENT_REJECTED` status, OMS automatically creates a refund.

```mermaid
sequenceDiagram
    participant MIS as MIS Settlement Event
    participant OMS as OMS
    participant SRS as SettlementReversalService
    participant SDK as PaymentSDK
    participant DB as PostgreSQL

    MIS->>OMS: processMisSettlement(event)
    OMS->>OMS: Order status: PROCESSED
    OMS->>OMS: Settlement status: REJECTED
    OMS->>OMS: Mark order SETTLEMENT_REJECTED
    OMS->>DB: UPDATE order

    OMS->>SRS: initiateReversal(order)
    activate SRS
    SRS->>SRS: Find CAPTURED payment
    SRS->>SRS: Build refund order<br/>(type=REFUND, source=SETTLEMENT_REJECTED)
    SRS->>OMS: createRefundOrder(refundOrder)
    OMS->>DB: INSERT refund order

    SRS->>OMS: processRefund(refundOrder)
    OMS->>SDK: refundPayment(amount)
    SDK-->>OMS: REFUNDED
    OMS->>OMS: Mark refund PROCESSED
    OMS->>DB: UPDATE + outbox
    SRS-->>OMS: Done
    deactivate SRS
```

---

## Flow 5: Force Close Refund (Admin)

For stuck refund orders that need manual resolution.

```mermaid
sequenceDiagram
    participant Admin as Admin
    participant RECON as Order-Recon
    participant RMS as RMS
    participant OMS as OMS
    participant DB as OMS DB

    Admin->>RECON: POST /terminate<br/>{orderId, status: FAILED}
    RECON->>RMS: PUT /refunds/{orderId}/close<br/>{status: FAILED}
    RMS->>OMS: PUT /orders/{orderId}/close<br/>{status: FAILED}

    OMS->>DB: Fetch order
    OMS->>OMS: Validate terminable state
    OMS->>OMS: Mark all payments FAILED
    OMS->>OMS: Mark order FAILED
    OMS->>DB: UPDATE + outbox
    OMS-->>RMS: Success
    RMS->>RMS: Update local refund entity
    RMS-->>RECON: OK
    RECON-->>Admin: Done
```

---

## Refund Validation Rules

| Rule | Check | Error |
|------|-------|-------|
| Duplicate check | merchantRefundReference must be unique per merchant | 409 Conflict |
| Order must be captured | At least one CAPTURED payment on parent order | 422 |
| Bank transfer not supported | Payment method ≠ BANK_TRANSFER | 422 |
| Currency match | Refund currency = order currency | 422 |
| Amount validation | refundAmount ≤ (capturedAmount - alreadyRefunded) | 422 |
| Refund window | Current time within merchant's refund window config | 422 |
| Partner MID | Merchant's partner MID must match | 403 |
| Offer eligibility | If offer applied, validate refund allowed | 422 |

---

## Refund Types

| Type | Trigger | Behavior |
|------|---------|----------|
| **FULL** | refundAmount == capturedAmount | Refunds entire captured amount |
| **PARTIAL** | refundAmount < capturedAmount | Refunds specified amount only |
| **SETTLEMENT_REJECTED** | MIS event with rejected status | Auto-initiated, full amount |
| **BACKPOST_REVERSAL** | Bank-side settlement on failed order | Force-created to reverse unintended capture |
| **CONVENIENCE_FEE** | Fee refund on main txn refund | Separate refund for fee component |

---

## Multi-Payment Refund (Split Order)

For orders with multiple captured payments:

```mermaid
sequenceDiagram
    participant RMS as RMS
    participant OMS as OMS
    participant SDK as PaymentSDK

    Note over OMS: Parent order has 2 captured payments:<br/>pay_A: 6000 (CARD)<br/>pay_B: 4000 (UPI)

    RMS->>OMS: PATCH /refund {amount: 10000, refundType: FULL}

    OMS->>OMS: Create refund order with 2 refund payments
    OMS->>OMS: Payment 1: refund 6000 (parent: pay_A)
    OMS->>OMS: Payment 2: refund 4000 (parent: pay_B)

    OMS->>SDK: refundPayment(pay_A, 6000)
    SDK-->>OMS: REFUNDED

    OMS->>SDK: refundPayment(pay_B, 4000)
    SDK-->>OMS: REFUNDED

    OMS->>OMS: All refund payments processed
    OMS->>OMS: Mark refund order PROCESSED
    OMS-->>RMS: Success
```

---

## Refund Event Flow (CDC)

```
Refund Order Created/Updated
         │
         ▼
┌─────────────────┐
│  orders table   │ ← Refund order inserted (type=REFUND)
│  outbox table   │ ← Proto event with refund details
└────────┬────────┘
         │ Debezium CDC
         ▼
┌─────────────────┐
│  Kafka Topic    │ orders.public.outbox
└────────┬────────┘
         │
    ┌────┴────┐
    ▼         ▼
┌────────┐ ┌──────────┐
│  OHS   │ │ Webhook  │
│ Update │ │ Merchant │
│ parent │ │ callback │
│ + child│ │ refund   │
│ orders │ │ event    │
└────────┘ └──────────┘
```
