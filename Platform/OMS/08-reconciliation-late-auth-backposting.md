# 08 — Reconciliation, Late Auth & Backposting

> Recon pipelines, late auth expiry handling, force close, and bank-side settlement backposting

---

## Reconciliation Architecture

```mermaid
graph TB
    subgraph Trigger Layer
        SCHED[Cron Scheduler]
        ADMIN[Admin Dashboard]
    end

    subgraph Order-Recon Service
        SYNC[Sync API<br/>POST /sync]
        SCROLL[OHS Scroll/Filter]
        CLASSIFY[Classify Orders]
        SQS_PROD[SQS Producer]
    end

    subgraph Kafka Topics
        KT_ORDER[order-recon]
        KT_REFUND[refund-recon]
        KT_EMI[emi-recon]
        KT_LP[long-pending]
        KT_LPR[long-pending-refund]
    end

    subgraph SQS Pipeline
        SQS_Q[SQS Queue]
        POLLER[SqsPollerWorker]
        DLQ[Dead Letter Queue]
    end

    subgraph Processing
        OMS[OMS reconcileOrder]
        RMS[RMS reconcile]
        GW[Gateway inquirePayment]
    end

    SCHED --> SYNC
    ADMIN --> SYNC
    SYNC --> SCROLL
    SCROLL --> CLASSIFY

    CLASSIFY -->|Merchant refund| KT_REFUND
    CLASSIFY -->|EMI order| KT_EMI
    CLASSIFY -->|Regular order| KT_ORDER

    KT_ORDER --> SQS_PROD
    KT_REFUND --> SQS_PROD
    SQS_PROD --> SQS_Q

    SQS_Q --> POLLER
    POLLER -->|KAFKA path| KT_ORDER
    POLLER -->|DIRECT path| RMS
    POLLER -->|DIRECT path| OMS
    POLLER -->|Exhausted| DLQ

    RMS --> OMS
    OMS --> GW
```

---

## Flow 1: Standard Order Reconciliation

```mermaid
sequenceDiagram
    participant SCHED as Scheduler
    participant RECON as Order-Recon
    participant OHS as Order History
    participant SQS as SQS Queue
    participant POLLER as SqsPollerWorker
    participant OMS as OMS
    participant SDK as PaymentSDK
    participant GW as Gateway
    participant DB as OMS DB

    SCHED->>RECON: POST /api/internal/v1/orders/sync<br/>{scenario: ORDER_RECON, dateRange}
    RECON->>OHS: Scroll pending orders in date range
    OHS-->>RECON: List of pending orders

    loop For each order
        RECON->>SQS: Enqueue {orderId, ruleId: INQUIRY_RECON}
    end

    Note over SQS,POLLER: SQS pipeline with step-based delays

    POLLER->>SQS: ReceiveMessage
    SQS-->>POLLER: {orderId, step=0, retryCount=0}

    POLLER->>OHS: GET order status
    OHS-->>POLLER: Order (still PENDING)

    POLLER->>OMS: POST /reconcile/{orderId}
    activate OMS

    OMS->>DB: Fetch order (with lock)
    OMS->>OMS: Find payment to reconcile<br/>(first non-terminal payment)
    OMS->>OMS: Check late auth expiry

    OMS->>SDK: inquirePayment(paymentId)
    SDK->>GW: Status inquiry
    GW-->>SDK: {status: CAPTURED, rrn: "..."}
    SDK-->>OMS: Right(CAPTURED)

    OMS->>OMS: handleReconcileResponse()
    OMS->>OMS: Mark payment CAPTURED
    OMS->>OMS: Mark order PROCESSED
    OMS->>DB: UPDATE + outbox
    OMS-->>POLLER: Right(Order) — terminal
    deactivate OMS

    POLLER->>SQS: DeleteMessage (resolved)
```

---

## Flow 2: SQS Pipeline Step Progression

The SQS pipeline uses a step-based approach with configurable delays between steps.

```mermaid
sequenceDiagram
    participant SQS as SQS Queue
    participant POLLER as SqsPollerWorker
    participant OMS as OMS

    Note over SQS: Step 0 (delay: 30s)
    SQS-->>POLLER: Message {step=0}
    POLLER->>OMS: reconcile(orderId)
    OMS-->>POLLER: Still PENDING

    POLLER->>SQS: Send new message {step=1, delay=60s}
    POLLER->>SQS: Delete original

    Note over SQS: Step 1 (delay: 60s)
    SQS-->>POLLER: Message {step=1}
    POLLER->>OMS: reconcile(orderId)
    OMS-->>POLLER: Still PENDING

    POLLER->>SQS: Send new message {step=2, delay=120s}
    POLLER->>SQS: Delete original

    Note over SQS: Step 2 (delay: 120s)
    SQS-->>POLLER: Message {step=2}
    POLLER->>OMS: reconcile(orderId)
    OMS-->>POLLER: CAPTURED → terminal

    POLLER->>SQS: Delete (resolved)
```

### Delay Configuration

| Step | Delay | Cumulative |
|------|-------|-----------|
| 0 | 30s | 30s |
| 1 | 60s | 1.5 min |
| 2 | 120s | 3.5 min |
| 3 | 240s | 7.5 min |
| 4 | 480s | 15.5 min |
| 5+ | Custom per rule | Varies |

### Failure Handling

- **Same-step retry**: On transient failure, retry same step (max 5 times with backoff: 30→60→120→240→480s)
- **DLQ**: After all steps + retries exhausted, message goes to Dead Letter Queue
- **Deferred messages**: For delays > 900s, uses SQS visibility timeout (max 12h)

---

## Late Auth Handling

### What is Late Auth?

When a payment callback arrives **after** the configured time window, it's considered "late auth." This protects customers from indefinite fund holds.

### Late Auth Detection

```kotlin
fun isLateAuthTimeExpired(paymentModel: PaymentModel, merchantConfig: MerchantConfig): Boolean {
    val cutoffMinutes = merchantConfig.lateAuthCutoff[paymentModel.method]
        ?: globalLateAuthInMinutes  // fallback to global config

    val expiryTime = paymentModel.createdAt + cutoffMinutes.minutes
    return Clock.System.now() > expiryTime
}
```

### Flow: Late Auth During Authorization

```mermaid
sequenceDiagram
    participant GW as Gateway
    participant OMS as OMS
    participant SDK as PaymentSDK
    participant DB as PostgreSQL

    Note over GW,OMS: Payment created at T=0<br/>Late auth cutoff = 30 min<br/>Callback arrives at T=45 min

    GW->>OMS: POST /internal/payments/{paymentId}/authorize<br/>{status: AUTHORIZED}
    activate OMS

    OMS->>OMS: isLateAuthTimeExpired?
    OMS->>OMS: createdAt + 30min < now → TRUE

    OMS->>OMS: Mark order CANCEL_REQUESTED
    OMS->>OMS: Mark payment FAILED
    OMS->>OMS: Cancel risk check
    OMS->>DB: UPDATE + outbox
    OMS-->>GW: Right(order) — cancelled due to late auth
    deactivate OMS
```

### Flow: Late Auth During Process Payment (UPI Success)

When UPI collect succeeds after late auth window — must capture then immediately reverse.

```mermaid
sequenceDiagram
    participant UPI as UPI Gateway
    participant OMS as OMS
    participant SDK as PaymentSDK
    participant DB as PostgreSQL

    Note over UPI,OMS: UPI collect sent at T=0<br/>Late auth cutoff = 10 min<br/>User pays at T=15 min

    UPI->>OMS: POST /payments/{paymentId}/process<br/>{status: PROCESSED, rrn: "123"}
    activate OMS

    OMS->>OMS: isLateAuthTimeExpired? → TRUE
    OMS->>OMS: Payment succeeded but too late

    Note over OMS: Cannot reject successful debit<br/>Must capture then reverse

    OMS->>OMS: Mark payment CAPTURED
    OMS->>OMS: Persist capture

    OMS->>OMS: Initiate reversal
    OMS->>SDK: refundPayment(full amount)
    SDK-->>OMS: Refund initiated

    OMS->>OMS: Mark order CANCEL_REQUESTED → CANCELLED
    OMS->>DB: UPDATE + outbox
    OMS-->>UPI: OK
    deactivate OMS

    Note over OMS: Customer gets refund automatically
```

### Flow: Late Auth During Reconciliation

```mermaid
sequenceDiagram
    participant RECON as Recon Pipeline
    participant OMS as OMS
    participant SDK as PaymentSDK

    RECON->>OMS: reconcileOrder(orderId)
    OMS->>OMS: Fetch order (PENDING)
    OMS->>OMS: isLateAuthTimeExpired? → TRUE

    alt UPI payment method
        OMS->>OMS: Resolve post-auth convenience fee → null
        OMS->>OMS: Mark order CANCEL_REQUESTED
        OMS->>OMS: Do NOT call inquiry (skip gateway)
        OMS-->>RECON: Order cancelled (late auth)
    else Other methods
        OMS->>SDK: inquirePayment()
        SDK-->>OMS: {status: ...}
        alt Inquiry shows SUCCESS
            OMS->>OMS: Capture then reverse
        else Inquiry shows FAILED
            OMS->>OMS: Mark CANCELLED
        end
    end
```

---

## Backposting

### What is Backposting?

Backposting occurs when a bank settles a transaction that OMS considers failed/cancelled. The bank-side settlement arrives via MIS/recon file, creating a state mismatch that must be resolved.

### Backposting Scenarios

```mermaid
flowchart TD
    A[forceCloseOrder Called<br/>Bank-side settlement detected] --> B{OMS Order Status?}

    B -->|PENDING| C{Payment Status?}
    B -->|CANCELLED / FAILED| D{Payment Status?}
    B -->|AUTHORIZED| E{Payment Status?}
    B -->|PROCESSED| F{Payment Status?}

    C -->|AUTH_CHALLENGED /<br/>AUTHENTICATED| G[Capture backposted payment<br/>Void/refund others]
    C -->|CAPTURED| H[Initiate reversal<br/>Create refund order]

    D -->|FAILED / CANCELLED| I[initiateForceBackpostReversal<br/>Update acquirer details<br/>Create refund order]
    D -->|CAPTURED| J[Already has reversal OR<br/>Return error]

    E -->|CAPTURE_REQUESTED| K[Capture backposted<br/>Void other authorized]

    F -->|FAILED / CANCELLED| L[Initiate forced<br/>backpost reversal]
```

### Flow: Backposting on Failed Order

The most common backpost scenario — order is FAILED/CANCELLED in OMS but bank actually settled.

```mermaid
sequenceDiagram
    participant RECON as Order-Recon / Admin
    participant OMS as OMS
    participant SDK as PaymentSDK
    participant DB as OMS DB

    RECON->>OMS: PUT /orders/{orderId}/close<br/>{status: BACKPOST, acquirerDetails: {rrn, authCode}}
    activate OMS

    OMS->>DB: Fetch order
    Note over OMS: Order: CANCELLED<br/>Payment: CANCELLED

    OMS->>OMS: forceCloseOrder()
    OMS->>OMS: Scenario: CANCELLED + CANCELLED/FAILED

    OMS->>OMS: initiateForceBackpostReversal()
    OMS->>OMS: Update payment with bank's acquirer details<br/>(rrn, authCode from settlement file)
    OMS->>OMS: Mark payment as bank-settled

    OMS->>OMS: Create REFUND order<br/>(parentOrderId = this order)
    OMS->>SDK: refundPayment(amount, acquirerDetails)
    SDK-->>OMS: Refund initiated (or pending)

    OMS->>DB: Persist refund order + outbox
    OMS-->>RECON: Success — reversal initiated
    deactivate OMS

    Note over OMS: Customer will receive refund<br/>for the unintended settlement
```

### Flow: Backposting on PENDING Order (Split Payment)

When one payment in a split order settles at bank but OMS shows it as pending.

```mermaid
sequenceDiagram
    participant RECON as Recon
    participant OMS as OMS
    participant SDK as PaymentSDK

    RECON->>OMS: forceCloseOrder(orderId, paymentId, status=BACKPOST)
    Note over OMS: Order: PENDING<br/>Payment A: AUTH_CHALLENGED (backposted)<br/>Payment B: AUTHORIZED

    OMS->>OMS: Identify backposted payment (A)
    OMS->>OMS: Mark A as CAPTURED

    OMS->>OMS: Handle other payments
    alt Other payments are AUTHORIZED
        OMS->>SDK: voidPayment(B)
        SDK-->>OMS: Voided
    else Other payments are PENDING
        OMS->>SDK: cancelPayment(B)
        SDK-->>OMS: Cancelled
    end

    OMS->>OMS: Mark order based on result<br/>(PROCESSED if capture stands, else reverse)
```

### Backposting Decision Matrix

| Order Status | Payment Status | Action |
|-------------|---------------|--------|
| PENDING | AUTH_CHALLENGED / AUTHENTICATED | Capture backposted, void/refund others |
| PENDING | CAPTURED | Create refund (reversal) |
| CANCELLED | FAILED / CANCELLED | Force backpost reversal (update acquirer details + refund) |
| CANCELLED | CAPTURED | Already reversed OR error |
| AUTHORIZED | CAPTURE_REQUESTED | Capture the backposted, void other authorized |
| PROCESSED | FAILED / CANCELLED | Forced backpost reversal |
| FAILED | FAILED | Force backpost reversal |

### Exception Merchants

Some merchants are configured to **accept** backposted payments instead of reversing:

```kotlin
if (merchantId in exceptionMerchantList) {
    // Capture all pending payments instead of reversing
    captureAllPendingPayments(order)
} else {
    // Standard: reverse the backposted payment
    initiateForceBackpostReversal(order, payment)
}
```

---

## Reconcile Payments (Payment-Level Recon)

For cancelled orders where individual payments may have succeeded bank-side:

```mermaid
sequenceDiagram
    participant RECON as Order-Recon
    participant OMS as OMS
    participant SDK as PaymentSDK

    RECON->>OMS: POST /reconcile-payments/{orderId}
    OMS->>OMS: Fetch order (CANCELLED)

    loop For each CANCELLED payment
        OMS->>SDK: inquirePayment(paymentId)
        SDK-->>OMS: Current status from gateway

        alt Gateway says AUTHORIZED/PROCESSED
            Note over OMS: Bank settled this payment!
            alt Pre-auth order
                OMS->>SDK: voidPayment(paymentId)
            else Non-pre-auth
                OMS->>OMS: Create refund order
                OMS->>SDK: refundPayment(paymentId)
            end
        else Gateway says FAILED/CANCELLED
            Note over OMS: Consistent — no action needed
        end
    end
```

---

## Post-Auth Reconciliation (Capture/Void Retry)

For orders stuck in CAPTURE_REQUESTED or VOID_REQUESTED:

```mermaid
sequenceDiagram
    participant RECON as Recon
    participant OMS as OMS
    participant SDK as PaymentSDK

    RECON->>OMS: reconcileOrder(orderId)
    Note over OMS: Order: AUTHORIZED<br/>Payment: CAPTURE_REQUESTED (stuck)

    OMS->>SDK: inquirePayment()
    SDK-->>OMS: Gateway status

    alt Gateway says CAPTURED
        OMS->>OMS: Mark payment CAPTURED
        OMS->>OMS: Mark order PROCESSED
    else Gateway says still PENDING
        OMS->>SDK: capturePayment() (retry)
        SDK-->>OMS: Result
    else Gateway says FAILED
        OMS->>OMS: Initiate reversal for any captured payments
    end
```

---

## Reconciliation Timeline

```
T=0          T+30s       T+90s       T+210s      T+450s      T+930s
 │            │           │            │           │           │
 ▼            ▼           ▼            ▼           ▼           ▼
Payment     Step 0      Step 1       Step 2      Step 3      Step 4
Created     Inquiry     Inquiry      Inquiry     Inquiry     Inquiry
            (first)     (30s gap)    (60s gap)   (120s gap)  (240s gap)

If still pending after all steps → DLQ (manual investigation)
```

---

## Force Close via Admin

```mermaid
flowchart TD
    A[Admin triggers force close] --> B{Order Type?}

    B -->|CHARGE| C[OMS directly:<br/>PUT /orders/{id}/close]
    B -->|REFUND| D[Route via RMS:<br/>PUT /refunds/{id}/close]

    C --> E{Desired status?}
    D --> F[RMS acquires lock<br/>Delegates to OMS]

    E -->|CANCELLED| G[Mark all payments CANCELLED<br/>Mark order CANCELLED]
    E -->|FAILED| H[Mark all payments FAILED<br/>Mark order FAILED]
    E -->|PROCESSED| I[Mark payment CAPTURED<br/>Mark order PROCESSED<br/>Update acquirer details]

    F --> E
```
