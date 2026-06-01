# 06 — Cancel & Void

> Order cancellation, payment cancellation, force cancellation, and void mechanics

---

## Cancel vs Void vs Refund

| Operation | When | Effect | Reversible? |
|-----------|------|--------|-------------|
| **Cancel** | Before capture (PENDING/ATTEMPTED) | Stops payment processing | No |
| **Void** | After authorization, before capture (AUTHORIZED) | Releases auth hold | No |
| **Refund** | After capture (PROCESSED) | Returns funds to customer | Creates refund order |

---

## Flow 1: Cancel Order (Standard — PENDING/ATTEMPTED)

Merchant cancels an order that has pending or attempted payments.

```mermaid
sequenceDiagram
    participant M as Merchant
    participant OMS as OMS
    participant Lock as Redis Lock
    participant SDK as PaymentSDK
    participant GW as Gateway
    participant Risk as Risk Service
    participant DB as PostgreSQL

    M->>OMS: PUT /api/pay/v1/orders/{orderId}/cancel
    activate OMS

    OMS->>Lock: acquireLock(orderId)
    Lock-->>OMS: Acquired

    OMS->>DB: SELECT order
    DB-->>OMS: Order (status: PENDING)

    OMS->>OMS: Validate: order is cancellable<br/>(not terminal, not AUTHORIZED for this path)

    loop For each non-terminal payment
        alt Payment is INITIATED/AUTH_CHALLENGED
            OMS->>OMS: Mark payment CANCEL_REQUESTED
            OMS->>SDK: cancelPayment(paymentId)
            SDK->>GW: Cancel request
            GW-->>SDK: {status: CANCELLED}
            SDK-->>OMS: Success
            OMS->>OMS: Mark payment CANCELLED
        else Payment is AUTHENTICATED
            OMS->>OMS: Mark payment FORCE_CANCEL_REQUESTED
            OMS->>OMS: Mark payment CANCELLED
        end
    end

    OMS->>Risk: cancelRiskCheck(orderId)
    Risk-->>OMS: OK

    OMS->>OMS: Mark order CANCELLED
    OMS->>DB: UPDATE + outbox
    OMS->>Lock: releaseLock
    OMS-->>M: 200 {status: CANCELLED}
    deactivate OMS
```

---

## Flow 2: Void Order (AUTHORIZED — Pre-Auth)

When a pre-auth order needs its authorization released.

```mermaid
sequenceDiagram
    participant M as Merchant
    participant OMS as OMS
    participant SDK as PaymentSDK
    participant GW as Card Gateway
    participant Acquirer as Acquirer

    M->>OMS: PUT /api/pay/v1/orders/{orderId}/cancel
    Note over OMS: Order status = AUTHORIZED<br/>This triggers VOID path

    OMS->>OMS: Mark order CANCEL_REQUESTED

    loop For each AUTHORIZED payment
        OMS->>OMS: Mark payment VOID_REQUESTED
        OMS->>SDK: voidPayment(paymentId)
        SDK->>GW: Void authorization request
        GW->>Acquirer: Reverse auth hold
        Acquirer-->>GW: Void confirmed
        GW-->>SDK: {status: VOIDED}
        SDK-->>OMS: Right(VOIDED)
        OMS->>OMS: Mark payment VOID
    end

    OMS->>OMS: All voided → Mark order CANCELLED
    OMS-->>M: 200 {status: CANCELLED}
```

---

## Flow 3: Cancel Pending Payments (Keep Order Open)

Cancel only the current pending payment without cancelling the order — allows merchant to retry with different method.

```mermaid
sequenceDiagram
    participant M as Merchant
    participant OMS as OMS
    participant SDK as PaymentSDK

    M->>OMS: PUT /api/pay/v1/orders/{orderId}/cancel-payments
    activate OMS

    OMS->>OMS: Fetch order (must be PENDING)
    OMS->>OMS: Find all non-terminal payments

    loop For each active payment
        OMS->>SDK: cancelPayment(paymentId)
        SDK-->>OMS: Cancelled
        OMS->>OMS: Mark payment CANCELLED
    end

    OMS->>OMS: Mark order ATTEMPTED<br/>(not CANCELLED — can retry)
    OMS-->>M: 200 {status: ATTEMPTED}
    deactivate OMS

    Note over M: Merchant can now POST new payment
```

---

## Flow 4: Void During Capture Failure (Split Payments)

When capturing multiple payments and one fails — already-captured payments must be reversed.

```mermaid
sequenceDiagram
    participant OMS as OMS
    participant SDK as PaymentSDK

    Note over OMS: Capturing split payment order<br/>Payment A: AUTHORIZED<br/>Payment B: AUTHORIZED

    OMS->>SDK: capturePayment(A, amount_A)
    SDK-->>OMS: CAPTURED ✓

    OMS->>SDK: capturePayment(B, amount_B)
    SDK-->>OMS: FAILED ✗ (logical error)

    Note over OMS: Payment B failed → must reverse A

    OMS->>OMS: initiateReversal for Payment A
    OMS->>SDK: refundPayment(A, amount_A)
    SDK-->>OMS: Refund initiated

    OMS->>OMS: Create refund order for reversal
    OMS->>OMS: Mark original order appropriately
```

---

## Flow 5: Force Cancel (Internal — Admin/Recon)

For stuck orders that can't be cancelled via normal flow.

```mermaid
sequenceDiagram
    participant Admin as Admin Dashboard
    participant RECON as Order-Recon
    participant OMS as OMS
    participant DB as PostgreSQL

    Admin->>RECON: POST /api/internal/v1/orders/terminate<br/>{orderId, status: CANCELLED}
    RECON->>OMS: POST /api/internal/pay/v1/orders/terminate/{orderId}
    activate OMS

    OMS->>DB: SELECT order
    OMS->>OMS: Validate: order is terminable<br/>(CREATED/PENDING/ATTEMPTED)

    OMS->>OMS: Mark all non-terminal payments CANCELLED
    OMS->>OMS: Mark order CANCELLED
    OMS->>DB: UPDATE + outbox
    OMS-->>RECON: 200 {status: CANCELLED}
    deactivate OMS

    RECON-->>Admin: Success
```

---

## Flow 6: Cancel with Late Auth Race Condition

When a payment callback arrives while cancellation is in progress:

```mermaid
sequenceDiagram
    participant M as Merchant
    participant OMS_Cancel as OMS (Cancel Thread)
    participant OMS_Callback as OMS (Callback Thread)
    participant Lock as Redis Lock
    participant SDK as PaymentSDK

    M->>OMS_Cancel: PUT /orders/{orderId}/cancel
    OMS_Cancel->>Lock: acquireLock(orderId)
    Lock-->>OMS_Cancel: Acquired

    Note over OMS_Callback: Gateway callback arrives
    OMS_Callback->>Lock: acquireLock(orderId)
    Note over OMS_Callback: BLOCKED — waiting for lock

    OMS_Cancel->>OMS_Cancel: Mark CANCEL_REQUESTED
    OMS_Cancel->>SDK: cancelPayment(paymentId)
    SDK-->>OMS_Cancel: Cancelled
    OMS_Cancel->>OMS_Cancel: Mark CANCELLED
    OMS_Cancel->>Lock: releaseLock

    Lock-->>OMS_Callback: Acquired (finally)
    OMS_Callback->>OMS_Callback: Re-fetch order under lock
    OMS_Callback->>OMS_Callback: Payment already CANCELLED<br/>→ Idempotent return

    OMS_Callback->>Lock: releaseLock
```

---

## Cancellation Decision Matrix

```mermaid
flowchart TD
    A[Cancel Request Received] --> B{Order Status?}

    B -->|CREATED| C[Mark order CANCELLED<br/>No payments to cancel]
    B -->|PENDING / ATTEMPTED| D{Has active payments?}
    B -->|AUTHORIZED| E[Void Path]
    B -->|PROCESSED| F[Error: Use Refund API]
    B -->|CANCELLED/FAILED| G[Idempotent: Already terminal]

    D -->|Yes| H[Cancel each payment via gateway]
    D -->|No| I[Mark order CANCELLED directly]

    H --> J{All cancelled?}
    J -->|Yes| K[Mark order CANCELLED]
    J -->|No - some failed to cancel| L{Payment type?}

    L -->|UPI INITIATED| M[Gateway may not support cancel<br/>Wait for timeout/recon]
    L -->|CARD AUTH_CHALLENGED| N[Cancel confirmed by gateway]

    E --> O[Void each AUTHORIZED payment]
    O --> P{All voided?}
    P -->|Yes| Q[Mark order CANCELLED]
    P -->|No| R[Park for recon<br/>CANCEL_REQUESTED state]
```

---

## State Transitions for Cancel/Void

| Scenario | Order: Before → After | Payment: Before → After |
|----------|----------------------|-------------------------|
| Cancel CREATED order | CREATED → CANCELLED | (none) |
| Cancel PENDING order | PENDING → CANCEL_REQUESTED → CANCELLED | INITIATED/AUTH_CHALLENGED → CANCEL_REQUESTED → CANCELLED |
| Cancel ATTEMPTED order | ATTEMPTED → CANCELLED | Already-failed stays FAILED |
| Void AUTHORIZED order | AUTHORIZED → CANCEL_REQUESTED → CANCELLED | AUTHORIZED → VOID_REQUESTED → VOID |
| Cancel-payments only | PENDING → ATTEMPTED | Active → CANCELLED |
| Terminate (admin) | PENDING → CANCELLED | Active → CANCELLED |
| Late auth + cancel race | PENDING → CANCELLED | AUTH_CHALLENGED → CANCELLED (idempotent) |
