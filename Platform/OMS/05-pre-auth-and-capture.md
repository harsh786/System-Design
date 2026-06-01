# 05 — Pre-Auth & Capture

> Authorization holds, partial/full capture, capture priority for split payments

---

## Concept

Pre-authorization (pre-auth) is a two-phase payment flow:

1. **Authorization** — Places a hold on the customer's funds without capturing
2. **Capture** — Transfers the held funds to the merchant (full or partial)

This is used for:
- Hotels / travel (capture at checkout, amount may change)
- E-commerce (capture on shipment)
- Marketplaces (capture per seller fulfillment)
- Subscriptions (authorize then capture on billing date)

---

## Pre-Auth Order Settings

Pre-auth is enabled at order creation time:

```json
{
  "amount": 10000,
  "currency": "INR",
  "orderSettings": {
    "preAuth": true,
    "autoCapture": false,
    "lateAuthCutoffMinutes": 30
  }
}
```

### Supported Payment Methods for Pre-Auth

| Method | Pre-Auth Support |
|--------|-----------------|
| CARD | Yes (all card networks) |
| UPI | Yes (UPI 2.0 mandate) |
| NETBANKING | No |
| WALLET | No |
| BNPL | Provider-dependent |
| EMI | No |

---

## Flow 1: Pre-Auth — Authorization Phase

```mermaid
sequenceDiagram
    participant M as Merchant
    participant OMS as OMS
    participant SDK as PaymentSDK
    participant GW as Card Gateway
    participant Bank as Issuing Bank
    participant User as Cardholder

    M->>OMS: POST /orders/{orderId}/payments<br/>{method: CARD, cardData: {...}}
    Note over OMS: Order has preAuth=true

    OMS->>SDK: createPayment(card, preAuth=true)
    SDK->>GW: Create pre-auth transaction
    GW->>Bank: Authorization request (3DS)
    Bank-->>GW: Challenge URL
    GW-->>SDK: {status: PENDING, challengeUrl}
    SDK-->>OMS: PENDING + challengeUrl
    OMS->>OMS: Mark payment AUTH_CHALLENGED
    OMS->>OMS: Mark order PENDING
    OMS-->>M: 200 {status: PENDING, challengeUrl}

    Note over User,Bank: User completes 3DS

    Bank->>GW: Auth success callback
    GW->>OMS: POST /internal/payments/{paymentId}/process<br/>{status: AUTHORIZED}

    OMS->>OMS: isPreAuth(order) == true
    OMS->>OMS: Mark payment AUTHORIZED
    OMS->>OMS: Mark order AUTHORIZED
    OMS->>OMS: Persist + outbox
    OMS-->>GW: 200 OK

    Note over OMS,M: Webhook: order.status = AUTHORIZED
```

---

## Flow 2: Capture (Full)

```mermaid
sequenceDiagram
    participant M as Merchant
    participant OMS as OMS
    participant Lock as Redis Lock
    participant SDK as PaymentSDK
    participant GW as Card Gateway
    participant DB as PostgreSQL

    M->>OMS: PUT /api/pay/v1/orders/{orderId}/capture<br/>{amount: 10000}
    activate OMS

    OMS->>Lock: acquireLock(orderId)
    Lock-->>OMS: Acquired

    OMS->>DB: SELECT order WHERE order_id = ?
    DB-->>OMS: Order (status=AUTHORIZED)

    OMS->>OMS: Validate: canCapturePayments == true
    OMS->>OMS: Validate: capture amount ≤ authorized amount
    OMS->>OMS: Sort payments by capture priority

    loop For each AUTHORIZED payment
        OMS->>OMS: Mark payment CAPTURE_REQUESTED
        OMS->>SDK: capturePayment(paymentId, amount)
        SDK->>GW: Capture request
        GW-->>SDK: {status: CAPTURED}
        SDK-->>OMS: Right(CAPTURED)
        OMS->>OMS: Mark payment CAPTURED
    end

    OMS->>OMS: All payments captured → Mark order PROCESSED
    OMS->>DB: UPDATE orders + INSERT outbox
    DB-->>OMS: Committed

    OMS->>Lock: releaseLock(orderId)
    OMS-->>M: 200 {status: PROCESSED}
    deactivate OMS
```

---

## Flow 3: Partial Capture

Partial capture allows capturing less than the authorized amount. Only supported for **single-payment orders** (not split payments).

```mermaid
sequenceDiagram
    participant M as Merchant
    participant OMS as OMS
    participant SDK as PaymentSDK
    participant GW as Gateway

    M->>OMS: PUT /orders/{orderId}/capture<br/>{amount: 7000}
    Note over OMS: Authorized amount = 10000

    OMS->>OMS: Validate: NOT split payment
    OMS->>OMS: Validate: capture amount (7000) ≤ auth amount (10000)

    OMS->>OMS: Mark payment CAPTURE_REQUESTED
    OMS->>SDK: capturePayment(paymentId, amount=7000)
    SDK->>GW: Partial capture (7000 of 10000)
    GW-->>SDK: {status: CAPTURED, capturedAmount: 7000}
    SDK-->>OMS: CAPTURED

    OMS->>OMS: Mark payment CAPTURED (amount: 7000)
    OMS->>OMS: Mark order PROCESSED
    OMS-->>M: 200 {status: PROCESSED, capturedAmount: 7000}

    Note over GW: Remaining 3000 auto-released by acquirer
```

---

## Flow 4: Capture with Priority List (Split/Part Payments)

For orders with multiple authorized payments (split payment), capture order matters.

```mermaid
sequenceDiagram
    participant M as Merchant
    participant OMS as OMS
    participant SDK as PaymentSDK

    M->>OMS: PUT /orders/{orderId}/capture<br/>{capturePriorityList: ["pay_001", "pay_002"]}
    Note over OMS: Order has 2 AUTHORIZED payments

    OMS->>OMS: Sort payments by priority list
    OMS->>OMS: Map capture amounts to payments

    OMS->>SDK: capturePayment(pay_001, amount_1)
    SDK-->>OMS: CAPTURED

    OMS->>SDK: capturePayment(pay_002, amount_2)
    SDK-->>OMS: CAPTURED

    OMS->>OMS: All payments captured
    OMS->>OMS: Mark order PROCESSED
    OMS-->>M: 200 OK
```

### Capture Amount Mapping Rules

```
If capturePriorityList provided:
  - Payments are captured in specified order
  - Each payment captures up to its authorized amount
  - Total capture = sum(min(payment.amount, remaining))

If no priority list:
  - CARD payments captured first (sorted by creation time)
  - Then other methods in creation order
```

---

## Flow 5: Void (Cancel Authorization)

When a pre-auth order needs to be cancelled before capture:

```mermaid
sequenceDiagram
    participant M as Merchant
    participant OMS as OMS
    participant SDK as PaymentSDK
    participant GW as Gateway

    M->>OMS: PUT /api/pay/v1/orders/{orderId}/cancel
    Note over OMS: Order status = AUTHORIZED

    OMS->>OMS: Mark order CANCEL_REQUESTED

    loop For each AUTHORIZED payment
        OMS->>OMS: Mark payment VOID_REQUESTED
        OMS->>SDK: voidPayment(paymentId)
        SDK->>GW: Void authorization
        GW-->>SDK: {status: VOIDED}
        SDK-->>OMS: Right(VOIDED)
        OMS->>OMS: Mark payment VOID
    end

    OMS->>OMS: All payments voided → Mark order CANCELLED
    OMS->>OMS: Cancel risk check
    OMS-->>M: 200 {status: CANCELLED}
```

---

## Capture Failure Handling

```mermaid
flowchart TD
    A[capturePayment Response] --> B{Response Type?}
    
    B -->|Success| C[Mark CAPTURED]
    B -->|Server Error| D[Park for retry<br/>Keep CAPTURE_REQUESTED]
    B -->|Logical Error| E{Retryable?}
    
    E -->|Yes| D
    E -->|No| F[Initiate reversal]
    
    F --> G[Call paymentSDK.refundPayment<br/>for already-captured payments]
    G --> H[Mark order as per reversal result]
    
    D --> I[Order-Recon picks up<br/>reconcileOrder triggers retry]
    I --> J[handlePostAuthReconcileResponse]
    J --> K{Inquiry result?}
    K -->|CAPTURED| C
    K -->|FAILED| F
    K -->|PENDING| I
```

---

## Pre-Auth Timeline

```
┌─────────────────────────────────────────────────────────────────────┐
│                     PRE-AUTH TIMELINE                                │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  T=0          T=0+3DS       T+30min(late auth)    T+N days          │
│   │              │                │                    │            │
│   ▼              ▼                ▼                    ▼            │
│ CREATE        AUTH SUCCESS     LATE AUTH           CAPTURE          │
│ PAYMENT       → AUTHORIZED    EXPIRY CHECK        WINDOW           │
│                               (if not captured)   CLOSES           │
│                                                                     │
│  If payment callback arrives AFTER late auth cutoff:                │
│  → Capture succeeds → Immediate reversal (refund)                   │
│  → This prevents holding customer funds indefinitely                │
│                                                                     │
│  Late Auth Cutoff Sources (priority):                               │
│  1. Merchant config per payment method                              │
│  2. Global config (globalLateAuthInMinutes)                         │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## State Transitions Summary

| Trigger | Order Before | Order After | Payment Before | Payment After |
|---------|-------------|-------------|----------------|---------------|
| Auth success (pre-auth) | PENDING | AUTHORIZED | AUTH_CHALLENGED | AUTHORIZED |
| Capture success | AUTHORIZED | PROCESSED | AUTHORIZED | CAPTURED |
| Partial capture | AUTHORIZED | PROCESSED | AUTHORIZED | CAPTURED |
| Capture failure (non-retryable) | AUTHORIZED | FAILED | AUTHORIZED | FAILED |
| Void success | AUTHORIZED | CANCELLED | AUTHORIZED | VOID |
| Late auth → auto-reversal | PENDING | CANCELLED | AUTH_CHALLENGED | FAILED → CAPTURED → refund |
