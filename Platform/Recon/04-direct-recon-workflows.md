# 04 — Direct Recon Workflows

## Overview

When the SQS poller processes a message and the pipeline rule's `reconModeConfig` routes it to the **direct path** (vs Kafka), the service calls downstream services directly via HTTP to drive reconciliation. There are four `DirectReconStrategy` options:

| Strategy | Target Service | Endpoint | Purpose |
|----------|---------------|----------|---------|
| `OMS_RECONCILE_PAYMENTS` | OMS (nxt-payments-service) | `POST /api/internal/pay/v1/orders/reconcile-payments/{orderId}` | Sync payment state with acquirer |
| `RMS_RECONCILE_REFUND` | RMS (nxt-refund-management-service) | `POST /api/internal/pay/v1/refunds/reconcile/{orderId}` | Sync refund state with acquirer |
| `OMS_TERMINATE_ORDER` | OMS (nxt-payments-service) | `POST /api/internal/pay/v1/orders/terminate/{orderId}` | Force-close long-pending orders |
| `CYBS_RISK_DECISION` | CyberSource Card Connector | `POST /connectors/cybs/v1/cards/decision-action` | Submit risk decision for reviewed payments |

## OMS_RECONCILE_PAYMENTS

### Purpose

Triggers OMS to query the acquirer/gateway for the current payment status and update the order state accordingly. Used for orders stuck in intermediate states (AUTHENTICATED, AUTHENTICATION_CHALLENGED, CAPTURE_REQUESTED).

### Workflow

```mermaid
sequenceDiagram
    participant Poller as SqsPollerWorker
    participant OMS as OMS (nxt-payments-service)
    participant Acquirer as Acquirer / Gateway
    participant DB as OMS Database

    Poller->>OMS: POST /reconcile-payments/{orderId}

    OMS->>DB: Load order + active payment
    OMS->>Acquirer: GET payment status<br/>(provider reference ID)
    Acquirer-->>OMS: {status: CAPTURED/FAILED/PENDING}

    alt Acquirer says CAPTURED
        OMS->>DB: Update payment → CAPTURED<br/>Update order → PROCESSED
        OMS-->>Poller: 200 {reconResult: TERMINAL_SETTLED}
    else Acquirer says FAILED
        OMS->>DB: Update payment → FAILED<br/>Update order → ATTEMPTED/FAILED
        OMS-->>Poller: 200 {reconResult: TERMINAL_CANCELLED}
    else Acquirer says PENDING
        OMS-->>Poller: 200 {reconResult: PENDING}
    else Acquirer unreachable
        OMS-->>Poller: 200 {reconResult: FAILURE}
    end
```

### Response Handling

```mermaid
flowchart TD
    RESPONSE[OMS Response] --> STATUS{reconResult}

    STATUS -->|TERMINAL_SETTLED| DELETE[Delete SQS message ✓<br/>Order reconciled successfully]
    STATUS -->|TERMINAL_CANCELLED| DELETE
    STATUS -->|PENDING| ADVANCE{More steps?}
    STATUS -->|FAILURE| RETRY[Same-step retry<br/>with backoff]

    ADVANCE -->|Yes| NEXT[Enqueue next step<br/>retryCount++]
    ADVANCE -->|No| DLQ[Send to DLQ]

    RETRY --> MAX{sameStepRetryCount < max?}
    MAX -->|Yes| REENQUEUE[Re-enqueue same step<br/>sameStepRetryCount++]
    MAX -->|No| ADVANCE
```

### Circuit Breaker Protection

All OMS calls are wrapped in an Arrow Resilience circuit breaker:

```kotlin
// Circuit breaker config for OMS client
CircuitBreaker(
    maxFailures = 200,         // Open after 200 consecutive failures
    resetTimeout = 10.seconds, // Half-open after 10s
    exponentialBackoffFactor = 1.2,
    maxResetTimeout = 60.seconds
)
```

**When circuit is OPEN**: Messages are not processed — they return to the queue via visibility timeout and will be retried when the circuit transitions to HALF_OPEN.

## RMS_RECONCILE_REFUND

### Purpose

Triggers the Refund Management Service to check refund status with the acquirer. Used for refunds stuck in CAPTURE_REQUESTED (refund initiated but not confirmed by bank).

### Workflow

```mermaid
sequenceDiagram
    participant Poller as SqsPollerWorker
    participant RMS as Refund Management Service
    participant Acquirer as Acquirer / Bank
    participant DB as RMS Database

    Poller->>RMS: POST /reconcile/{orderId}

    RMS->>DB: Load refund order + payment
    RMS->>Acquirer: GET refund status (ARN/RRN)
    Acquirer-->>RMS: {status: PROCESSED/FAILED/PENDING}

    alt Refund confirmed
        RMS->>DB: Update payment → CAPTURED<br/>Update order → PROCESSED
        RMS-->>Poller: 200 {reconResult: TERMINAL_SETTLED}
    else Refund rejected
        RMS->>DB: Update payment → FAILED
        Note over RMS: May park for retry if retriable error
        RMS-->>Poller: 200 {reconResult: TERMINAL_CANCELLED}
    else Still processing
        RMS-->>Poller: 200 {reconResult: PENDING}
    end
```

### Parked Refund Handling

For scenarios like `AGGREGATOR_REFUNDS` and `ACQUIRER_FAILURE`, the refund is "parked" with a reason:

```mermaid
flowchart TD
    PARKED[Parked Refund] --> REASON{parkedReason}

    REASON -->|AGGREGATOR_SALE_CHECK_FAILURE| AGG[Aggregator sale check failed<br/>Need to verify original sale exists]
    REASON -->|ACQUIRER_DECLINE| ACQ[Acquirer declined refund<br/>Retry with backoff]

    AGG --> RMS_CALL[RMS reconcile<br/>Verifies sale + retries refund]
    ACQ --> ATTEMPT_CHECK{attempt count < max?}
    ATTEMPT_CHECK -->|Yes| RMS_CALL
    ATTEMPT_CHECK -->|No| MANUAL[Escalate for manual review]

    RMS_CALL --> RESULT{Result}
    RESULT -->|Success| UNPARK[Unpark + process refund]
    RESULT -->|Still failing| REQUEUE[Re-enqueue with next step delay]
```

## OMS_TERMINATE_ORDER

### Purpose

Force-closes orders that have been stuck beyond the maximum lifecycle threshold. This is the "nuclear option" — the order is moved to a terminal state regardless of acquirer response.

### Workflow

```mermaid
sequenceDiagram
    participant Poller as SqsPollerWorker
    participant OMS as OMS (nxt-payments-service)
    participant OHS as Order History (verify)
    participant DB as OMS Database

    Note over Poller: Order stuck for >2h (LONG_PENDING scenario)

    Poller->>OMS: POST /terminate/{orderId}

    OMS->>DB: Load order
    OMS->>OMS: Validate order is still non-terminal

    alt Order is terminable
        OMS->>DB: Update order → FAILED<br/>Update payment → CANCELLED
        OMS->>OMS: Trigger webhook (order.failed)
        OMS-->>Poller: 200 {terminated: true}
    else Order already terminal
        OMS-->>Poller: 200 {terminated: false, reason: "ALREADY_TERMINAL"}
    else Order in non-terminable state
        OMS-->>Poller: 409 Conflict
    end

    Note over Poller: Verify in OHS (eventual consistency)
    Poller->>OHS: GET /orders/{orderId}
    OHS-->>Poller: {orderStatus: FAILED}

    alt Reflected in OHS
        Poller->>Poller: Delete SQS message ✓
    else Not yet reflected
        Poller->>Poller: Re-enqueue with verification delay
    end
```

### Termination Decision Tree

```mermaid
flowchart TD
    ORDER[Long-pending order] --> TYPE{orderType}

    TYPE -->|CHARGE| CHARGE_STATUS{orderStatus}
    TYPE -->|REFUND| REFUND_TERM[RMS force-close refund]

    CHARGE_STATUS -->|CREATED| TERMINATE[Terminate → FAILED<br/>No payment ever attempted]
    CHARGE_STATUS -->|PENDING| CHECK_PAY{paymentStatus}
    CHARGE_STATUS -->|ATTEMPTED| TERMINATE
    CHARGE_STATUS -->|CANCEL_REQUESTED| TERMINATE

    CHECK_PAY -->|INITIATED| TERMINATE
    CHECK_PAY -->|AUTHENTICATED| TERMINATE_AUTH[Terminate → FAILED<br/>Was authorized but never captured]
    CHECK_PAY -->|AUTHENTICATION_CHALLENGED| TERMINATE
    CHECK_PAY -->|CANCELLED/FAILED| TERMINATE

    REFUND_TERM --> KAFKA[Publish to long-pending-refund-orders<br/>RMS handles closure]
```

### Force Close (vs Terminate)

There are two related but distinct operations:

| Operation | Endpoint | Use Case | Who Calls |
|-----------|----------|----------|-----------|
| **Terminate** | `POST /terminate/{orderId}` | Long-pending orders with no acquirer response | Recon service |
| **Force Close** | `PUT /force-close/{orderId}` | Back-posting — late auth from acquirer | Recon service (backpost flow) |

Force close includes payment details from the acquirer (providerReferenceId, RRN, status):

```kotlin
data class OMSForceCloseRequest(
    val orderId: String,
    val paymentId: String,
    val providerReferenceId: String?,
    val rrn: String?,
    val paymentStatus: String,  // CAPTURED | FAILED
    val acquirerCode: String?,
    val acquirerMessage: String?
)
```

## CYBS_RISK_DECISION

### Purpose

For CyberSource-processed payments where risk review status is `PENDING_REVIEW`, this strategy submits the final decision (accept/reject) to CyberSource based on the payment's terminal state.

### Workflow

```mermaid
sequenceDiagram
    participant Poller as SqsPollerWorker
    participant Handler as RiskDecisionHandler
    participant Redis as Redis (Dedup)
    participant OHS as Order History
    participant CYBS as CyberSource Connector

    Poller->>Handler: handleRiskDecision(payload)

    Handler->>OHS: GET /orders/{orderId}
    OHS-->>Handler: Order with payments

    Handler->>Handler: Find payments with<br/>riskStatus=PENDING_REVIEW<br/>in acquirerDetails.rawData

    loop For each candidate payment
        Handler->>Handler: Check: terminal status + within 24h?

        alt Payment is CAPTURED/PROCESSED
            Handler->>Redis: EXISTS CYBS:DECISION:{riskId}
            alt Not sent yet
                Handler->>CYBS: POST /decision-action<br/>{id: riskId, result: SUCCESS}
                CYBS-->>Handler: 200 OK
                Handler->>Redis: SETEX CYBS:DECISION:{riskId} 600 "1"
            end

        else Payment is FAILED/CANCELLED/VOID
            Handler->>Redis: EXISTS CYBS:DECISION:{riskId}
            alt Not sent yet
                Handler->>CYBS: POST /decision-action<br/>{id: riskId, result: FAILURE}
                CYBS-->>Handler: 200 OK
                Handler->>Redis: SETEX CYBS:DECISION:{riskId} 600 "1"
            end
        end
    end

    alt All decisions sent successfully
        Handler-->>Poller: TERMINAL_SETTLED
    else Some failed
        Handler-->>Poller: FAILURE (retry)
    end
```

### Decision Mapping

| Payment Terminal Status | CyberSource Decision | Message |
|------------------------|---------------------|---------|
| CAPTURED | SUCCESS | "Payment captured successfully" |
| PROCESSED | SUCCESS | "Payment processed successfully" |
| FAILED | FAILURE | "Payment failed" |
| CANCELLED | FAILURE | "Payment cancelled" |
| VOID | FAILURE | "Payment voided" |

### Dedup TTL

Redis key: `CYBS:DECISION:{riskId}` with **10-minute TTL** (600s). This is shorter than the standard 24h dedup because CyberSource decisions are idempotent and we want faster retry on transient failures.

## Direct Recon Result Contract

All direct recon strategies return one of these outcomes:

```kotlin
enum class ReconResult {
    TERMINAL_SETTLED,     // Order reached terminal success state
    TERMINAL_CANCELLED,   // Order reached terminal failure state
    PENDING,              // Still in intermediate state, retry later
    FAILURE               // Recon call itself failed (transient error)
}
```

### Result → Action Mapping

```mermaid
flowchart LR
    RESULT[ReconResult] --> R1[TERMINAL_SETTLED]
    RESULT --> R2[TERMINAL_CANCELLED]
    RESULT --> R3[PENDING]
    RESULT --> R4[FAILURE]

    R1 --> DELETE[Delete message<br/>Done ✓]
    R2 --> DELETE
    R3 --> ADVANCE[Advance step<br/>or DLQ if exhausted]
    R4 --> SAME_STEP[Same-step retry<br/>with backoff]
```

## Error Handling & Retries

### HTTP Error Responses

| HTTP Status | Interpretation | Action |
|-------------|---------------|--------|
| 200 | Success (check body for reconResult) | Per result mapping above |
| 404 | Order not found in OMS | Delete message (stale) |
| 409 | Conflict (concurrent modification) | Same-step retry |
| 429 | Rate limited | Same-step retry with longer backoff |
| 5xx | Server error | Same-step retry |
| Timeout | Network timeout (10s) | Same-step retry |
| Circuit OPEN | Service unhealthy | Message returns via visibility timeout |

### Backoff Strategy

Same-step retries use exponential backoff:

```
delay = min(baseDelay * 2^(sameStepRetryCount), maxBackoff)

baseDelay = 5s
maxBackoff = 300s (5 min)

Attempt 0: 5s
Attempt 1: 10s
Attempt 2: 20s
Attempt 3: 40s
Attempt 4: 80s
Attempt 5: 160s
Attempt 6: 300s (capped)
```

## End-to-End Direct Recon Example

### AUTHZ Order: Card Payment Authorized but Not Captured

```mermaid
sequenceDiagram
    participant Cron as AUTHZ Cron (every 2min)
    participant OHS as Order History
    participant Redis as Redis
    participant SQS as sqs-authz
    participant Poller as SqsPollerWorker
    participant OMS as nxt-payments-service
    participant Acquirer as HDFC Gateway

    Note over Cron: Discover: order_status=PENDING,<br/>payment_status=AUTHENTICATED,<br/>updated_at between 5-60 min ago

    Cron->>OHS: Scroll query (AUTHZ filters)
    OHS-->>Cron: [Order-123, Order-456, ...]

    Cron->>Redis: EXISTS dedup:Order-123:AUTHZ_RECON
    Redis-->>Cron: 0 (new)
    Cron->>Redis: SETEX dedup:Order-123:AUTHZ_RECON 86460
    Cron->>SQS: SendMessage(delay=30s)<br/>orderId=Order-123, retryCount=0

    Note over SQS: 30s delay...

    SQS-->>Poller: Receive Order-123
    Note over Poller: Rule=AUTHZ_RECON, directPercent=80%<br/>Random roll → DIRECT path

    Poller->>OMS: POST /reconcile-payments/Order-123
    OMS->>Acquirer: GET payment status (ref=HDFC_TXN_789)
    Acquirer-->>OMS: {status: PENDING}
    OMS-->>Poller: {reconResult: PENDING}

    Note over Poller: Still pending. Advance to step 1 (delay=60s)
    Poller->>SQS: SendMessage(delay=60s)<br/>retryCount=1

    Note over SQS: 60s delay...

    SQS-->>Poller: Receive Order-123 (step 1)
    Poller->>OMS: POST /reconcile-payments/Order-123
    OMS->>Acquirer: GET payment status
    Acquirer-->>OMS: {status: CAPTURED, rrn: "123456789012"}
    OMS-->>Poller: {reconResult: TERMINAL_SETTLED}

    Poller->>SQS: DeleteMessage ✓
    Note over Poller: Order-123 reconciled successfully!
```
