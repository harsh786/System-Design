# 08 — Lifecycle Management Workflow

> Pause, resume, cancel, upgrade, and downgrade subscription flows

---

## Functional Overview

Subscription lifecycle management covers all non-billing state changes that alter a subscription's operational state, plan configuration, or billing trajectory. These operations are merchant-initiated (via API) or system-initiated (via scheduled jobs or policy enforcement).

### Lifecycle Operations

| # | Operation | Description | Trigger |
|---|-----------|-------------|---------|
| 1 | **Pause** | Temporarily suspend billing; service may continue | Merchant API / Customer portal |
| 2 | **Resume** | Reactivate after pause | Merchant API / Scheduled auto-resume |
| 3 | **Cancel (Immediate)** | Terminate subscription now | Merchant API / System (fraud, dunning exhaustion) |
| 4 | **Cancel (End-of-Term)** | Mark for termination at period end | Merchant API / Customer portal |
| 5 | **Upgrade** | Move to higher-tier plan | Merchant API |
| 6 | **Downgrade** | Move to lower-tier plan | Merchant API |
| 7 | **Quantity Change** | Add/remove seats or units | Merchant API |

---

## Architecture Context

```
┌─────────────────────────────────────────────────────────────────────┐
│                     Lifecycle Management Layer                        │
├─────────────┬──────────────┬──────────────┬─────────────────────────┤
│ PauseService│ ResumeService│ CancelService│ PlanChangeService       │
├─────────────┴──────────────┴──────────────┴─────────────────────────┤
│                     LifecycleOrchestrator                             │
├─────────────────────────────────────────────────────────────────────┤
│  StateGuard  │  ProrationEngine  │  DistributedLockManager          │
├─────────────────────────────────────────────────────────────────────┤
│  SubscriptionRepository  │  BillingScheduleRepository  │  Outbox    │
├─────────────────────────────────────────────────────────────────────┤
│            PostgreSQL             │  Redis  │  Kafka (CDC)           │
└─────────────────────────────────────────────────────────────────────┘
```

### Key Dependencies

- **DistributedLockManager** — Redis-based (Redlock) to prevent concurrent mutations
- **ProrationEngine** — Calculates credits/charges for mid-cycle changes
- **BillingScheduleService** — Manages future billing events
- **MandateService** — Pause/revoke recurring payment mandates
- **OutboxWriter** — Transactional outbox for CDC-based event publishing
- **DunningService** — Cancel/pause dunning retries on lifecycle changes

---

## Flow 1: Pause Subscription

### 1.1 Functional Sequence

```mermaid
sequenceDiagram
    participant M as Merchant API
    participant GW as Subscription Gateway
    participant V as Validator
    participant PS as PauseService
    participant DB as PostgreSQL
    participant N as Notification

    M->>GW: POST /subscriptions/{id}/pause
    GW->>V: Validate request & state
    V-->>GW: Validation passed
    GW->>PS: Execute pause
    PS->>DB: Update subscription state
    PS->>DB: Write outbox event
    PS-->>GW: Paused subscription
    GW-->>M: 200 OK (subscription)
    Note over DB,N: CDC picks up outbox event
    DB--)N: subscription.paused webhook
```

### 1.2 Technical Sequence

```mermaid
sequenceDiagram
    participant Client as Merchant
    participant API as SubscriptionAPI (Ktor)
    participant Guard as StateGuard
    participant Lock as RedisLock
    participant PS as PauseService
    participant Prorate as ProrationEngine
    participant Billing as BillingScheduleService
    participant Dunning as DunningService
    participant Repo as SubscriptionRepository
    participant Outbox as OutboxWriter
    participant DB as PostgreSQL

    Client->>API: POST /api/subscriptions/v1/subscriptions/{id}/pause
    API->>API: Authenticate & authorize (merchant_id, scope)
    API->>Repo: findById(subscriptionId)
    Repo-->>API: Subscription entity

    API->>Guard: validateTransition(subscription, PAUSED)
    Guard->>Guard: Assert current state ∈ {ACTIVE, PAST_DUE}
    Guard->>Guard: Assert pause_count < max_pauses (if configured)
    Guard->>Guard: Assert no active plan change pending
    Guard-->>API: ✓ Transition allowed

    API->>Lock: acquire("sub:lifecycle:{id}", ttl=30s)
    Lock-->>API: Lock acquired

    API->>PS: executePause(subscription, pauseRequest)

    alt pause_behavior = CREDIT_UNUSED
        PS->>Prorate: calculateUnusedCredit(subscription)
        Prorate->>Prorate: days_remaining = period_end - today
        Prorate->>Prorate: daily_rate = base_amount / period_days
        Prorate->>Prorate: credit = daily_rate × days_remaining
        Prorate-->>PS: CreditAmount(166.33)
        PS->>Repo: createCreditNote(subscription, credit)
    end

    PS->>Billing: cancelPendingSchedules(subscriptionId)
    Billing->>DB: UPDATE billing_schedules SET status='CANCELLED' WHERE subscription_id=? AND status='SCHEDULED'
    Billing-->>PS: Cancelled 2 schedules

    PS->>Dunning: cancelActiveRetries(subscriptionId)
    Dunning->>DB: UPDATE dunning_attempts SET status='CANCELLED' WHERE subscription_id=? AND status IN ('PENDING','SCHEDULED')
    Dunning-->>PS: Done

    PS->>Repo: updateSubscription(subscription)
    Note over PS,DB: Single transaction begins
    Repo->>DB: UPDATE subscriptions SET status='PAUSED', paused_at=NOW(), pause_reason=?, paused_by=?, resume_at=?
    Repo->>DB: INSERT INTO subscription_status_history (subscription_id, from_status, to_status, changed_at, changed_by, metadata)

    PS->>Outbox: write(subscription.paused, payload)
    Outbox->>DB: INSERT INTO outbox_events (aggregate_id, event_type, payload, created_at)
    Note over PS,DB: Transaction commits

    PS-->>API: PausedSubscription

    API->>Lock: release("sub:lifecycle:{id}")
    API-->>Client: 200 OK { subscription with status=PAUSED }

    Note over DB: Debezium CDC captures outbox INSERT
    DB--)Outbox: CDC → Kafka topic: subscription.lifecycle.events
    Note over Outbox: Webhook dispatcher delivers subscription.paused
```

### 1.3 API Contract

```json
POST /api/subscriptions/v1/subscriptions/{id}/pause
Authorization: Bearer {merchant_api_key}
Content-Type: application/json
Idempotency-Key: {unique-key}

{
  "reason": "customer_request",
  "pause_behavior": "CREDIT_UNUSED",
  "resume_at": "2024-04-01T00:00:00Z",
  "preserve_billing_anchor": true,
  "metadata": {
    "requested_by": "customer_support",
    "ticket_id": "SUP-12345"
  }
}
```

**Response:**
```json
{
  "id": "sub_01HQXK...",
  "status": "PAUSED",
  "paused_at": "2024-01-25T10:30:00Z",
  "resume_at": "2024-04-01T00:00:00Z",
  "pause_behavior": "CREDIT_UNUSED",
  "credit_note_id": "cn_01HQXL...",
  "credit_amount": 16633,
  "current_period_start": "2024-01-15T00:00:00Z",
  "current_period_end": "2024-02-15T00:00:00Z",
  "plan": { "id": "plan_basic", "name": "Basic" },
  "billing_anchor_preserved": true
}
```

### 1.4 Pause Options & Behavior Matrix

| Option | Value | Behavior |
|--------|-------|----------|
| `pause_behavior` | `CREDIT_UNUSED` | Calculate credit for unused days in current period |
| `pause_behavior` | `NO_CREDIT` | No credit issued; customer loses unused days |
| `resume_at` | ISO datetime | System auto-resumes at this date via scheduled job |
| `resume_at` | `null` | Indefinite pause (subject to max_pause_duration) |
| `preserve_billing_anchor` | `true` | On resume, billing date stays the same (e.g., 15th of month) |
| `preserve_billing_anchor` | `false` | On resume, new billing cycle starts from resume date |

### 1.5 Kotlin Implementation

```kotlin
// PauseService.kt
class PauseService(
    private val subscriptionRepo: SubscriptionRepository,
    private val billingScheduleService: BillingScheduleService,
    private val dunningService: DunningService,
    private val prorationEngine: ProrationEngine,
    private val outboxWriter: OutboxWriter,
    private val creditNoteService: CreditNoteService,
    private val clock: Clock
) {
    suspend fun executePause(
        subscription: Subscription,
        request: PauseRequest
    ): PauseResult = withContext(Dispatchers.IO) {

        val now = clock.instant()

        // Calculate credit if applicable
        val creditNote = when (request.pauseBehavior) {
            PauseBehavior.CREDIT_UNUSED -> {
                val credit = prorationEngine.calculateUnusedCredit(
                    subscription = subscription,
                    effectiveDate = now
                )
                if (credit.amount > 0) {
                    creditNoteService.create(
                        subscriptionId = subscription.id,
                        amount = credit.amount,
                        currency = subscription.currency,
                        reason = "Pause credit: ${credit.daysRemaining} unused days",
                        applyTo = CreditApplication.NEXT_INVOICE
                    )
                } else null
            }
            PauseBehavior.NO_CREDIT -> null
        }

        // Cancel future billing
        billingScheduleService.cancelPendingSchedules(subscription.id)
        dunningService.cancelActiveRetries(subscription.id)

        // Persist state change
        val pausedSubscription = subscription.copy(
            status = SubscriptionStatus.PAUSED,
            pausedAt = now,
            pauseReason = request.reason,
            pausedBy = request.pausedBy,
            resumeAt = request.resumeAt,
            preserveBillingAnchor = request.preserveBillingAnchor,
            pauseCount = subscription.pauseCount + 1,
            updatedAt = now
        )

        subscriptionRepo.transactional {
            subscriptionRepo.update(pausedSubscription)
            subscriptionRepo.insertStatusHistory(
                StatusHistoryEntry(
                    subscriptionId = subscription.id,
                    fromStatus = subscription.status,
                    toStatus = SubscriptionStatus.PAUSED,
                    changedAt = now,
                    changedBy = request.pausedBy,
                    metadata = mapOf(
                        "reason" to request.reason.name,
                        "credit_note_id" to creditNote?.id,
                        "resume_at" to request.resumeAt?.toString()
                    )
                )
            )
            outboxWriter.write(
                aggregateId = subscription.id,
                eventType = "subscription.paused",
                payload = SubscriptionPausedEvent(
                    subscriptionId = subscription.id,
                    merchantId = subscription.merchantId,
                    customerId = subscription.customerId,
                    pausedAt = now,
                    reason = request.reason,
                    resumeAt = request.resumeAt,
                    creditNoteId = creditNote?.id,
                    creditAmount = creditNote?.amount
                )
            )
        }

        PauseResult(
            subscription = pausedSubscription,
            creditNote = creditNote
        )
    }
}
```

---

## Flow 2: Resume Subscription

### 2.1 Functional Sequence

```mermaid
sequenceDiagram
    participant M as Merchant API
    participant GW as Subscription Gateway
    participant V as Validator
    participant RS as ResumeService
    participant BS as BillingScheduleService
    participant DB as PostgreSQL
    participant N as Notification

    M->>GW: POST /subscriptions/{id}/resume
    GW->>V: Validate state = PAUSED
    V-->>GW: Valid
    GW->>RS: Execute resume
    RS->>RS: Determine billing behavior
    RS->>BS: Recompute billing schedule
    RS->>DB: Update subscription → ACTIVE
    RS->>DB: Write outbox event
    RS-->>GW: Resumed subscription
    GW-->>M: 200 OK
    DB--)N: subscription.resumed webhook
```

### 2.2 Technical Sequence

```mermaid
sequenceDiagram
    participant Client as Merchant
    participant API as SubscriptionAPI
    participant Guard as StateGuard
    participant Lock as RedisLock
    participant RS as ResumeService
    participant BS as BillingScheduleService
    participant MS as MandateService
    participant Prorate as ProrationEngine
    participant Repo as SubscriptionRepository
    participant Outbox as OutboxWriter
    participant DB as PostgreSQL

    Client->>API: POST /api/subscriptions/v1/subscriptions/{id}/resume
    API->>Repo: findById(subscriptionId)
    Repo-->>API: Subscription (status=PAUSED)

    API->>Guard: validateTransition(subscription, ACTIVE)
    Guard->>Guard: Assert current state = PAUSED
    Guard->>Guard: Assert mandate still valid (not revoked)
    Guard-->>API: ✓ Allowed

    API->>Lock: acquire("sub:lifecycle:{id}", ttl=30s)
    Lock-->>API: Lock acquired

    API->>RS: executeResume(subscription, resumeRequest)

    RS->>RS: Determine resume billing mode
    Note over RS: Based on preserve_billing_anchor<br/>and resume_billing_mode in request

    alt resume_billing_mode = IMMEDIATE_CHARGE
        RS->>Prorate: calculateResumeCharge(subscription)
        Prorate-->>RS: Full period charge from today
        RS->>RS: new_period_start = today, new_period_end = today + interval
        RS->>BS: scheduleImmediate(subscription, amount)
    else resume_billing_mode = NEXT_ANCHOR_DATE
        RS->>RS: next_billing = next occurrence of billing_anchor after today
        RS->>RS: If credit exists, apply to first invoice
        RS->>BS: scheduleAt(subscription, next_billing, amount)
    else resume_billing_mode = EXTEND_PERIOD
        RS->>RS: pause_duration = today - paused_at
        RS->>RS: new_period_end = original_period_end + pause_duration
        RS->>BS: scheduleAt(subscription, new_period_end, amount)
    end

    RS->>MS: reactivateMandate(subscription.mandateId)
    MS-->>RS: Mandate reactivated

    Note over RS,DB: Transaction begins
    RS->>Repo: UPDATE subscriptions SET status='ACTIVE', paused_at=NULL, resume_at=NULL, current_period_start=?, current_period_end=?
    RS->>Repo: INSERT status_history
    RS->>Outbox: write(subscription.resumed, payload)
    Note over RS,DB: Transaction commits

    RS-->>API: ResumedSubscription
    API->>Lock: release
    API-->>Client: 200 OK { subscription with status=ACTIVE, next_billing_date }
```

### 2.3 Resume Billing Scenarios

```mermaid
gantt
    title Scenario A: Paused mid-cycle, resumed same cycle (EXTEND_PERIOD)
    dateFormat  YYYY-MM-DD
    axisFormat  %b %d

    section Original Period
    Active (Jan 15 - Jan 25)    :done, a1, 2024-01-15, 2024-01-25
    Paused (Jan 25 - Feb 5)     :crit, a2, 2024-01-25, 2024-02-05
    Extended Active (Feb 5 - Feb 25) :active, a3, 2024-02-05, 2024-02-25

    section Billing
    No charge during pause       :milestone, 2024-01-25, 0d
    Next charge (extended end)   :milestone, 2024-02-25, 0d
```

```mermaid
gantt
    title Scenario B: Paused full cycle, resumed (IMMEDIATE_CHARGE)
    dateFormat  YYYY-MM-DD
    axisFormat  %b %d

    section Period
    Active (Jan 15 - Feb 15)    :done, b1, 2024-01-15, 2024-02-15
    Paused (Feb 15 - Mar 20)    :crit, b2, 2024-02-15, 2024-03-20
    New Period (Mar 20 - Apr 20) :active, b3, 2024-03-20, 2024-04-20

    section Billing
    Immediate charge on resume   :milestone, 2024-03-20, 0d
    Next regular charge          :milestone, 2024-04-20, 0d
```

```mermaid
gantt
    title Scenario C: Auto-resume on scheduled date (NEXT_ANCHOR_DATE)
    dateFormat  YYYY-MM-DD
    axisFormat  %b %d

    section Period
    Active                       :done, c1, 2024-01-15, 2024-01-25
    Paused                       :crit, c2, 2024-01-25, 2024-04-01
    Auto-Resume                  :milestone, 2024-04-01, 0d
    Wait for anchor (15th)       :active, c3, 2024-04-01, 2024-04-15
    New Period (Apr 15 - May 15) :active, c4, 2024-04-15, 2024-05-15

    section Billing
    No charge during wait        :milestone, 2024-04-01, 0d
    Charge on anchor date        :milestone, 2024-04-15, 0d
```

### 2.4 API Contract

```json
POST /api/subscriptions/v1/subscriptions/{id}/resume
Authorization: Bearer {merchant_api_key}
Content-Type: application/json
Idempotency-Key: {unique-key}

{
  "resume_billing_mode": "NEXT_ANCHOR_DATE",
  "metadata": {
    "resumed_by": "customer_support"
  }
}
```

### 2.5 Auto-Resume Scheduled Job

```kotlin
// AutoResumeJob.kt — runs every hour via pg_cron or Quartz
class AutoResumeJob(
    private val subscriptionRepo: SubscriptionRepository,
    private val resumeService: ResumeService,
    private val lockManager: DistributedLockManager
) {
    suspend fun execute() {
        val now = Clock.System.now()
        val candidates = subscriptionRepo.findByStatusAndResumeAtBefore(
            status = SubscriptionStatus.PAUSED,
            resumeAtBefore = now,
            limit = 100
        )

        candidates.forEach { subscription ->
            lockManager.withLock("sub:lifecycle:${subscription.id}") {
                try {
                    resumeService.executeResume(
                        subscription = subscription,
                        request = ResumeRequest(
                            resumeBillingMode = ResumeBillingMode.NEXT_ANCHOR_DATE,
                            triggeredBy = "system:auto_resume"
                        )
                    )
                    logger.info { "Auto-resumed subscription ${subscription.id}" }
                } catch (e: Exception) {
                    logger.error(e) { "Failed to auto-resume ${subscription.id}" }
                    // Will retry on next job execution
                }
            }
        }
    }
}
```

---

## Flow 3: Cancel Subscription (Immediate)

### 3.1 Functional Sequence

```mermaid
sequenceDiagram
    participant M as Merchant / Customer
    participant GW as Subscription Gateway
    participant V as Validator
    participant CS as CancelService
    participant Prorate as ProrationEngine
    participant MS as MandateService
    participant DB as PostgreSQL
    participant WH as Webhook

    M->>GW: POST /subscriptions/{id}/cancel (mode=IMMEDIATE)
    GW->>V: Validate state & cancellation policy
    V-->>GW: Allowed
    GW->>CS: Execute immediate cancellation
    CS->>Prorate: Calculate refund/credit
    Prorate-->>CS: Credit amount
    CS->>CS: Cancel billing schedules
    CS->>CS: Cancel in-flight payments
    CS->>MS: Revoke mandate
    MS-->>CS: Mandate revoked
    CS->>DB: Update subscription → CANCELLED
    CS->>DB: Write outbox event
    CS-->>GW: Cancelled subscription
    GW-->>M: 200 OK
    DB--)WH: subscription.cancelled
```

### 3.2 Technical Sequence

```mermaid
sequenceDiagram
    participant Client as Merchant
    participant API as SubscriptionAPI
    participant Guard as StateGuard
    participant Policy as CancellationPolicyEngine
    participant Lock as RedisLock
    participant CS as CancelService
    participant Prorate as ProrationEngine
    participant CN as CreditNoteService
    participant Refund as RefundService
    participant Billing as BillingScheduleService
    participant Payment as PaymentService
    participant Mandate as MandateService
    participant Repo as SubscriptionRepository
    participant Outbox as OutboxWriter
    participant DB as PostgreSQL

    Client->>API: POST /subscriptions/{id}/cancel
    Note over Client,API: { "cancel_mode": "IMMEDIATE",<br/>"reason": "CUSTOMER_REQUEST",<br/>"refund_mode": "PRORATE" }

    API->>Repo: findById(subscriptionId)
    Repo-->>API: Subscription

    API->>Guard: validateTransition(subscription, CANCELLED)
    Guard->>Guard: Assert state ∈ {ACTIVE, PAUSED, PAST_DUE, PENDING_CANCELLATION}
    Guard-->>API: ✓

    API->>Policy: checkCancellationAllowed(subscription)
    Policy->>Policy: Check merchant cancellation_policy
    Policy->>Policy: Check minimum_commitment (e.g., 6-month lock-in)
    Policy->>Policy: Check notice_period_days
    alt Policy violation
        Policy-->>API: CancellationDeniedException(reason)
        API-->>Client: 422 Cancellation not allowed
    end
    Policy-->>API: ✓ Allowed

    API->>Lock: acquire("sub:lifecycle:{id}", ttl=60s)
    Lock-->>API: Acquired

    API->>CS: executeImmediateCancel(subscription, request)

    %% Refund/Credit calculation
    alt refund_mode = PRORATE
        CS->>Prorate: calculateUnusedCredit(subscription)
        Prorate->>Prorate: days_remaining = period_end - today
        Prorate->>Prorate: credit = (base_amount / total_days) × days_remaining
        Prorate-->>CS: ProrationResult(amount=16633, days=10)

        alt merchant prefers refund
            CS->>Refund: initiateRefund(lastPaymentId, amount)
            Refund-->>CS: Refund initiated (async)
        else merchant prefers credit note
            CS->>CN: create(subscriptionId, amount)
            CN-->>CS: CreditNote created
        end
    else refund_mode = NONE
        Note over CS: No refund/credit issued
    else refund_mode = FULL_PERIOD
        CS->>Refund: initiateRefund(lastPaymentId, fullAmount)
    end

    %% Cancel pending operations
    CS->>Billing: cancelAllSchedules(subscriptionId)
    Billing->>DB: UPDATE billing_schedules SET status='CANCELLED'
    Billing-->>CS: Done

    CS->>Payment: cancelInFlightPayments(subscriptionId)
    Payment-->>CS: Cancelled 0 payments

    %% Revoke mandate
    CS->>Mandate: revoke(subscription.mandateId, reason="subscription_cancelled")
    Mandate-->>CS: Mandate revoked

    %% Persist
    Note over CS,DB: Transaction begins
    CS->>Repo: UPDATE subscriptions SET status='CANCELLED', cancelled_at=NOW(), cancellation_reason=?, cancelled_by=?, effective_cancellation_date=NOW()
    CS->>Repo: INSERT status_history
    CS->>Repo: UPDATE subscription_items SET status='CANCELLED'
    CS->>Outbox: write("subscription.cancelled", event)
    Note over CS,DB: Transaction commits

    CS-->>API: CancelResult
    API->>Lock: release
    API-->>Client: 200 OK { subscription, refund_id?, credit_note_id? }

    Note over DB: Debezium CDC → Kafka
    DB--)Client: Webhook: subscription.cancelled
```

### 3.3 Cancellation Reasons

```kotlin
enum class CancellationReason {
    CUSTOMER_REQUEST,        // Customer asked to cancel
    PAYMENT_FAILURE,         // Dunning exhausted, auto-cancel
    MERCHANT_REQUEST,        // Merchant-initiated cancellation
    FRAUD_DETECTED,          // Fraud system triggered cancellation
    MANDATE_REVOKED,         // Customer revoked payment mandate externally
    PLAN_DISCONTINUED,       // Plan no longer available
    ACCOUNT_CLOSED,          // Customer account deleted
    REGULATORY_COMPLIANCE,   // Legal/regulatory requirement
    TERMS_VIOLATION,         // Customer violated terms of service
    SYSTEM_MIGRATION,        // Migrated to different subscription
    TRIAL_EXPIRED            // Trial ended without conversion
}
```

### 3.4 API Contract

```json
POST /api/subscriptions/v1/subscriptions/{id}/cancel
Authorization: Bearer {merchant_api_key}
Content-Type: application/json
Idempotency-Key: {unique-key}

{
  "cancel_mode": "IMMEDIATE",
  "reason": "CUSTOMER_REQUEST",
  "refund_mode": "PRORATE",
  "cancellation_note": "Customer moving to competitor",
  "metadata": {
    "retention_offered": true,
    "retention_declined": true
  }
}
```

**Response:**
```json
{
  "id": "sub_01HQXK...",
  "status": "CANCELLED",
  "cancelled_at": "2024-01-25T10:30:00Z",
  "cancellation_reason": "CUSTOMER_REQUEST",
  "effective_cancellation_date": "2024-01-25T10:30:00Z",
  "refund": {
    "id": "rfnd_01HQX...",
    "amount": 16633,
    "currency": "INR",
    "status": "PROCESSING"
  },
  "mandate_status": "REVOKED",
  "final_invoice_id": null
}
```

---

## Flow 4: Cancel Subscription (End of Term)

### 4.1 Functional Sequence

```mermaid
sequenceDiagram
    participant M as Merchant
    participant GW as Subscription Gateway
    participant CS as CancelService
    participant DB as PostgreSQL
    participant Job as pg_cron Job
    participant WH as Webhook

    M->>GW: POST /subscriptions/{id}/cancel (mode=END_OF_TERM)
    GW->>CS: Mark for cancellation
    CS->>DB: status → PENDING_CANCELLATION, set cancel_at
    CS->>DB: Write outbox (cancellation_scheduled)
    CS-->>GW: Subscription (pending cancellation)
    GW-->>M: 200 OK
    DB--)WH: subscription.cancellation_scheduled

    Note over Job: Daily job: check cancel_at <= today
    Job->>DB: SELECT subscriptions WHERE cancel_at <= NOW()
    Job->>CS: executeImmediateCancel(subscription)
    CS->>DB: status → CANCELLED
    CS->>DB: Write outbox (subscription.cancelled)
    DB--)WH: subscription.cancelled
```

### 4.2 Technical Sequence

```mermaid
sequenceDiagram
    participant Client as Merchant
    participant API as SubscriptionAPI
    participant Guard as StateGuard
    participant Lock as RedisLock
    participant CS as CancelService
    participant Billing as BillingScheduleService
    participant Repo as SubscriptionRepository
    participant Outbox as OutboxWriter
    participant DB as PostgreSQL
    participant Job as EndOfTermCancelJob

    Client->>API: POST /subscriptions/{id}/cancel
    Note over Client,API: { "cancel_mode": "END_OF_TERM" }

    API->>Repo: findById(subscriptionId)
    Repo-->>API: Subscription (status=ACTIVE)

    API->>Guard: validateTransition(subscription, PENDING_CANCELLATION)
    Guard-->>API: ✓

    API->>Lock: acquire("sub:lifecycle:{id}")

    API->>CS: scheduleEndOfTermCancel(subscription, request)

    CS->>CS: cancel_at = subscription.current_period_end
    CS->>Billing: preventRenewalScheduling(subscriptionId)
    Note over CS,Billing: Don't create billing schedule for next period

    Note over CS,DB: Transaction
    CS->>Repo: UPDATE subscriptions SET status='PENDING_CANCELLATION', cancel_at=current_period_end, cancellation_reason=?
    CS->>Repo: INSERT status_history
    CS->>Outbox: write("subscription.cancellation_scheduled", { cancel_at, reason })
    Note over CS,DB: Commit

    CS-->>API: ScheduledCancellation
    API->>Lock: release
    API-->>Client: 200 OK { status: "PENDING_CANCELLATION", cancel_at: "2024-02-15" }

    Note over Job: Runs daily at 00:05 UTC
    Job->>Repo: findByStatusAndCancelAtBefore(PENDING_CANCELLATION, now)
    Repo-->>Job: [sub_01, sub_02, ...]

    loop Each subscription
        Job->>Lock: acquire("sub:lifecycle:{sub.id}")
        Job->>CS: executeImmediateCancel(subscription, SystemCancelRequest)
        Note over CS: Same flow as Immediate Cancel (Flow 3)
        Job->>Lock: release
    end
```

### 4.3 End-of-Term Cancel Behavior

```
Timeline Example:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Jan 15          Jan 25                Feb 15
│────────────────│─────────────────────│
│  Period Start  │  Cancel Requested   │  Period End (cancel_at)
│                │                     │
│  ACTIVE        │  PENDING_CANCEL     │  CANCELLED
│                │  (service continues)│  (mandate revoked)
│                │  (no new billing)   │
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### 4.4 Reactivation (Undo End-of-Term Cancel)

Merchants can undo a pending cancellation before it takes effect:

```json
POST /api/subscriptions/v1/subscriptions/{id}/reactivate
{
  "reason": "customer_changed_mind"
}
```

This transitions `PENDING_CANCELLATION → ACTIVE`, clears `cancel_at`, and reschedules billing.

---

## Flow 5: Upgrade Plan

### 5.1 Functional Sequence

```mermaid
sequenceDiagram
    participant M as Merchant
    participant GW as Subscription Gateway
    participant V as Validator
    participant PC as PlanChangeService
    participant Prorate as ProrationEngine
    participant Billing as BillingScheduleService
    participant Pay as PaymentService
    participant DB as PostgreSQL
    participant WH as Webhook

    M->>GW: POST /subscriptions/{id}/change-plan
    GW->>V: Validate new plan (higher tier, compatible)
    V-->>GW: Valid
    GW->>PC: Execute upgrade
    PC->>Prorate: Calculate proration (credit old + charge new)
    Prorate-->>PC: Net charge amount
    PC->>Billing: Update billing schedule
    PC->>Pay: Execute prorated payment (if immediate)
    Pay-->>PC: Payment result
    PC->>DB: Update subscription plan
    PC->>DB: Write outbox event
    PC-->>GW: Upgraded subscription
    GW-->>M: 200 OK
    DB--)WH: subscription.plan_changed
```

### 5.2 Technical Sequence

```mermaid
sequenceDiagram
    participant Client as Merchant
    participant API as SubscriptionAPI
    participant Guard as StateGuard
    participant Lock as RedisLock
    participant PC as PlanChangeService
    participant PlanRepo as PlanRepository
    participant Prorate as ProrationEngine
    participant Invoice as InvoiceService
    participant Payment as PaymentExecutor
    participant Billing as BillingScheduleService
    participant Repo as SubscriptionRepository
    participant Outbox as OutboxWriter
    participant DB as PostgreSQL

    Client->>API: POST /subscriptions/{id}/change-plan
    Note over Client,API: { "new_plan_id": "plan_pro",<br/>"proration_mode": "IMMEDIATE",<br/>"effective": "NOW" }

    API->>Repo: findById(subscriptionId)
    Repo-->>API: Subscription (plan=Basic, INR 499/mo)

    API->>Guard: validateTransition(subscription, PLAN_CHANGE)
    Guard->>Guard: Assert state = ACTIVE (not PAST_DUE, not in dunning)
    Guard->>Guard: Assert no pending plan change
    Guard-->>API: ✓

    API->>PlanRepo: findById("plan_pro")
    PlanRepo-->>API: Plan (Pro, INR 999/mo)

    API->>PC: validatePlanChange(oldPlan, newPlan)
    PC->>PC: Assert same billing_interval (monthly)
    PC->>PC: Assert same currency
    PC->>PC: Assert newPlan.tier > oldPlan.tier (upgrade)
    PC->>PC: Assert newPlan.status = ACTIVE
    PC-->>API: ✓ Valid upgrade

    API->>Lock: acquire("sub:lifecycle:{id}")

    API->>PC: executeUpgrade(subscription, newPlan, request)

    %% Proration
    PC->>Prorate: calculateUpgradeProration(subscription, newPlan)
    Note over Prorate: period_start: Jan 15<br/>today: Jan 25<br/>period_end: Feb 15<br/>days_used: 10, days_remaining: 21<br/>total_days: 31

    Prorate->>Prorate: old_credit = (499/31) × 21 = 337.97
    Prorate->>Prorate: new_charge = (999/31) × 21 = 676.74
    Prorate->>Prorate: net_amount = 676.74 - 337.97 = 338.77
    Prorate-->>PC: ProrationResult(credit=33797, charge=67674, net=33877)

    alt proration_mode = IMMEDIATE
        PC->>Invoice: createProratedInvoice(subscription, prorationResult)
        Invoice-->>PC: Invoice(id=inv_01, amount=33877, status=PENDING)

        PC->>Payment: executePayment(invoice, subscription.mandateId)
        Payment-->>PC: PaymentResult(status=SUCCESS)

        PC->>Invoice: markPaid(invoiceId)
    else proration_mode = NEXT_INVOICE
        PC->>PC: Store proration as line item for next invoice
        PC->>Billing: addLineItem(subscriptionId, prorationLineItem)
    end

    %% Update subscription
    Note over PC,DB: Transaction begins
    PC->>Repo: UPDATE subscriptions SET plan_id='plan_pro', base_amount=99900, updated_at=NOW()
    PC->>Repo: UPDATE subscription_items SET plan_item_id=?, unit_price=?
    PC->>Repo: INSERT plan_change_history (sub_id, old_plan, new_plan, change_type='UPGRADE', proration_amount, effective_at)
    PC->>Billing: updateScheduleAmount(subscriptionId, 99900)
    PC->>Outbox: write("subscription.plan_changed", event)
    Note over PC,DB: Transaction commits

    PC-->>API: UpgradeResult
    API->>Lock: release
    API-->>Client: 200 OK { subscription, proration_invoice, payment_status }
```

### 5.3 Proration Calculation Detail

```
┌─────────────────────────────────────────────────────────────────┐
│                    UPGRADE PRORATION EXAMPLE                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  Current Plan: Basic (INR 499/month)                             │
│  New Plan:     Pro   (INR 999/month)                             │
│  Billing Period: Jan 15 → Feb 15 (31 days)                       │
│  Upgrade Date:   Jan 25 (10 days used, 21 days remaining)        │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────┐     │
│  │ Jan 15        Jan 25                    Feb 15          │     │
│  │ ├──────────────┼──────────────────────────┤             │     │
│  │ │◄─ 10 days ─►│◄────── 21 days ────────►│             │     │
│  │ │  Basic @499  │       Pro @999           │             │     │
│  │ │  (already    │                          │             │     │
│  │ │   paid)      │                          │             │     │
│  └─────────────────────────────────────────────────────────┘     │
│                                                                   │
│  CALCULATION:                                                     │
│  ─────────────                                                    │
│  Old plan daily rate:  499 / 31 = INR 16.10/day                  │
│  New plan daily rate:  999 / 31 = INR 32.23/day                  │
│                                                                   │
│  Credit for unused Basic: 16.10 × 21 = INR 338.10               │
│  Charge for Pro remainder: 32.23 × 21 = INR 676.83              │
│                                                                   │
│  NET CHARGE: 676.83 - 338.10 = INR 338.73                       │
│                                                                   │
│  Next full cycle (Feb 15): INR 999 (full Pro price)              │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

### 5.4 API Contract

```json
POST /api/subscriptions/v1/subscriptions/{id}/change-plan
Authorization: Bearer {merchant_api_key}
Content-Type: application/json
Idempotency-Key: {unique-key}

{
  "new_plan_id": "plan_pro_monthly",
  "proration_mode": "IMMEDIATE",
  "effective": "NOW",
  "metadata": {
    "upgrade_reason": "customer_needs_more_features"
  }
}
```

**Response:**
```json
{
  "id": "sub_01HQXK...",
  "status": "ACTIVE",
  "plan": {
    "id": "plan_pro_monthly",
    "name": "Pro",
    "amount": 99900,
    "currency": "INR",
    "interval": "MONTHLY"
  },
  "plan_change": {
    "type": "UPGRADE",
    "previous_plan_id": "plan_basic_monthly",
    "effective_at": "2024-01-25T10:30:00Z",
    "proration": {
      "credit_amount": 33810,
      "charge_amount": 67683,
      "net_amount": 33873,
      "invoice_id": "inv_01HQX..."
    },
    "payment": {
      "id": "pay_01HQX...",
      "status": "SUCCESS",
      "amount": 33873
    }
  },
  "next_billing_date": "2024-02-15T00:00:00Z",
  "next_billing_amount": 99900
}
```

---

## Flow 6: Downgrade Plan

### 6.1 Functional Sequence

```mermaid
sequenceDiagram
    participant M as Merchant
    participant GW as Subscription Gateway
    participant PC as PlanChangeService
    participant Feature as FeatureUsageService
    participant DB as PostgreSQL
    participant WH as Webhook

    M->>GW: POST /subscriptions/{id}/change-plan (lower tier)
    GW->>PC: Validate downgrade
    PC->>Feature: Check feature usage vs new plan limits
    Feature-->>PC: Usage report (within/exceeds limits)
    alt Usage exceeds new plan
        PC-->>GW: 422 with usage_warning
        GW-->>M: 422 (must reduce usage first)
    end
    PC->>PC: Schedule downgrade (end of period by default)
    PC->>DB: Store pending plan change
    PC->>DB: Write outbox event
    PC-->>GW: Downgrade scheduled
    GW-->>M: 200 OK
    DB--)WH: subscription.plan_change_scheduled
```

### 6.2 Technical Sequence

```mermaid
sequenceDiagram
    participant Client as Merchant
    participant API as SubscriptionAPI
    participant Guard as StateGuard
    participant Lock as RedisLock
    participant PC as PlanChangeService
    participant PlanRepo as PlanRepository
    participant Feature as FeatureUsageService
    participant Prorate as ProrationEngine
    participant Repo as SubscriptionRepository
    participant Outbox as OutboxWriter
    participant DB as PostgreSQL
    participant Job as PlanChangeJob

    Client->>API: POST /subscriptions/{id}/change-plan
    Note over Client,API: { "new_plan_id": "plan_starter",<br/>"effective": "END_OF_PERIOD" }

    API->>Repo: findById(subscriptionId)
    Repo-->>API: Subscription (plan=Pro, INR 999/mo)

    API->>PlanRepo: findById("plan_starter")
    PlanRepo-->>API: Plan (Starter, INR 299/mo)

    API->>Guard: validateTransition(subscription, PLAN_CHANGE)
    Guard-->>API: ✓

    API->>PC: validatePlanChange(oldPlan=Pro, newPlan=Starter)
    PC->>PC: Assert newPlan.tier < oldPlan.tier (downgrade)

    %% Feature usage check
    PC->>Feature: checkUsageCompatibility(subscription, newPlan)
    Feature->>Feature: Current: 50 users, Pro allows 100
    Feature->>Feature: Starter allows: 25 users
    Feature-->>PC: UsageReport(compatible=false, violations=[{feature: "users", current: 50, limit: 25}])

    alt Force downgrade not requested
        PC-->>API: DowngradeBlockedException(violations)
        API-->>Client: 422 { "error": "usage_exceeds_plan_limits", "violations": [...] }
    end

    Note over API: Assume force=true or usage is compatible

    API->>Lock: acquire("sub:lifecycle:{id}")

    alt effective = END_OF_PERIOD (default for downgrades)
        PC->>PC: effective_date = subscription.current_period_end
        Note over PC,DB: Transaction
        PC->>Repo: INSERT pending_plan_changes (sub_id, new_plan_id, effective_at, change_type='DOWNGRADE')
        PC->>Repo: UPDATE subscriptions SET pending_plan_change_id=?
        PC->>Outbox: write("subscription.plan_change_scheduled", event)
        Note over PC,DB: Commit

    else effective = NOW (immediate downgrade)
        PC->>Prorate: calculateDowngradeCredit(subscription, newPlan)
        Prorate->>Prorate: credit = unused_old - unused_new (net credit)
        Prorate-->>PC: CreditResult(amount=15000)
        PC->>PC: Apply credit to account balance

        Note over PC,DB: Transaction
        PC->>Repo: UPDATE subscriptions SET plan_id='plan_starter', base_amount=29900
        PC->>Repo: INSERT plan_change_history
        PC->>Repo: INSERT credit_notes (if credit > 0)
        PC->>Outbox: write("subscription.plan_changed", event)
        Note over PC,DB: Commit
    end

    PC-->>API: DowngradeResult
    API->>Lock: release
    API-->>Client: 200 OK

    Note over Job: On current_period_end, PlanChangeJob executes
    Job->>Repo: findPendingPlanChanges(effectiveAt <= now)
    Job->>PC: applyPlanChange(subscription, pendingChange)
    PC->>Repo: UPDATE subscriptions SET plan_id=new, base_amount=new
    PC->>Outbox: write("subscription.plan_changed")
```

### 6.3 Downgrade Guardrails

```kotlin
data class UsageViolation(
    val feature: String,
    val currentUsage: Long,
    val newPlanLimit: Long,
    val requiredReduction: Long,
    val gracePeriodDays: Int? = null
)

class FeatureUsageService(
    private val usageRepo: UsageRepository,
    private val planRepo: PlanRepository
) {
    suspend fun checkUsageCompatibility(
        subscription: Subscription,
        newPlan: Plan
    ): UsageCompatibilityReport {
        val currentUsage = usageRepo.getCurrentUsage(subscription.id)
        val newLimits = planRepo.getPlanLimits(newPlan.id)

        val violations = newLimits.mapNotNull { (feature, limit) ->
            val usage = currentUsage[feature] ?: 0
            if (usage > limit) {
                UsageViolation(
                    feature = feature,
                    currentUsage = usage,
                    newPlanLimit = limit,
                    requiredReduction = usage - limit,
                    gracePeriodDays = newPlan.downgradeGracePeriodDays
                )
            } else null
        }

        return UsageCompatibilityReport(
            compatible = violations.isEmpty(),
            violations = violations
        )
    }
}
```

---

## Flow 7: Quantity Change (Seat-Based)

### 7.1 Functional Sequence

```mermaid
sequenceDiagram
    participant M as Merchant
    participant GW as Subscription Gateway
    participant QS as QuantityChangeService
    participant Prorate as ProrationEngine
    participant Invoice as InvoiceService
    participant DB as PostgreSQL
    participant WH as Webhook

    M->>GW: PATCH /subscriptions/{id} (quantity change)
    GW->>QS: Process quantity change
    alt Adding seats
        QS->>Prorate: Calculate prorated charge
        Prorate-->>QS: Charge for remaining days
        QS->>Invoice: Create prorated invoice
    else Removing seats
        QS->>Prorate: Calculate credit
        Prorate-->>QS: Credit for remaining days
        QS->>Invoice: Create credit note
    end
    QS->>DB: Update subscription_items quantity
    QS->>DB: Write outbox event
    QS-->>GW: Updated subscription
    GW-->>M: 200 OK
    DB--)WH: subscription.updated
```

### 7.2 Technical Sequence

```mermaid
sequenceDiagram
    participant Client as Merchant
    participant API as SubscriptionAPI
    participant Guard as StateGuard
    participant Lock as RedisLock
    participant QS as QuantityChangeService
    participant Prorate as ProrationEngine
    participant Invoice as InvoiceService
    participant Payment as PaymentExecutor
    participant Billing as BillingScheduleService
    participant Repo as SubscriptionRepository
    participant Outbox as OutboxWriter
    participant DB as PostgreSQL

    Client->>API: PATCH /subscriptions/{id}
    Note over Client,API: { "items": [{ "id": "si_01",<br/>"quantity": 15 }] }

    API->>Repo: findById(subscriptionId)
    Repo-->>API: Subscription (items: [{id: si_01, quantity: 10, unit_price: 20000}])

    API->>Guard: validateTransition(subscription, QUANTITY_CHANGE)
    Guard->>Guard: Assert state = ACTIVE
    Guard->>Guard: Assert quantity within plan min/max
    Guard-->>API: ✓

    API->>Lock: acquire("sub:lifecycle:{id}")

    API->>QS: processQuantityChange(subscription, items)

    QS->>QS: delta = new_quantity(15) - old_quantity(10) = +5
    QS->>QS: Determine: INCREASE (delta > 0)

    alt INCREASE (adding seats)
        QS->>Prorate: calculateAdditionalQuantity(subscription, delta=5)
        Prorate->>Prorate: days_remaining = period_end - today = 15
        Prorate->>Prorate: total_days = 30
        Prorate->>Prorate: prorated_charge = 5 × (20000/30) × 15 = 50000
        Prorate-->>QS: ProrationResult(amount=50000)

        QS->>Invoice: createProratedInvoice(subscription, amount=50000)
        Note over Invoice: Line item: "5 additional seats (Jan 15 - Feb 15, prorated)"
        Invoice-->>QS: Invoice(id=inv_02, amount=50000)

        QS->>Payment: executePayment(invoice, mandateId)
        Payment-->>QS: PaymentResult(SUCCESS)

    else DECREASE (removing seats)
        QS->>QS: delta = old_quantity(10) - new_quantity(7) = -3
        QS->>Prorate: calculateRemovedQuantity(subscription, delta=3)
        Prorate->>Prorate: credit = 3 × (20000/30) × 15 = 30000
        Prorate-->>QS: CreditResult(amount=30000)

        QS->>Invoice: createCreditNote(subscription, amount=30000)
        Invoice-->>QS: CreditNote(id=cn_03, amount=30000)
    end

    %% Update subscription
    Note over QS,DB: Transaction
    QS->>Repo: UPDATE subscription_items SET quantity=15 WHERE id='si_01'
    QS->>Repo: UPDATE subscriptions SET base_amount = 15 × 20000 = 300000
    QS->>Billing: updateScheduleAmount(subscriptionId, 300000)
    QS->>Outbox: write("subscription.updated", { old_quantity: 10, new_quantity: 15, proration_amount: 50000 })
    Note over QS,DB: Commit

    QS-->>API: QuantityChangeResult
    API->>Lock: release
    API-->>Client: 200 OK { subscription, prorated_invoice?, credit_note? }
```

### 7.3 Quantity Change Example

```
┌─────────────────────────────────────────────────────────────────┐
│              SEAT-BASED QUANTITY CHANGE EXAMPLE                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  Plan: Per-Seat @ INR 200/seat/month                             │
│  Current: 10 seats (INR 2,000/month)                             │
│  Period: Jan 1 → Jan 31 (31 days)                                │
│  Change Date: Jan 16 (15 days remaining)                         │
│                                                                   │
│  ADDING 5 SEATS:                                                  │
│  ─────────────────                                                │
│  Prorated charge = 5 × (200/31) × 15 = INR 483.87               │
│  → Immediate invoice for INR 483.87                              │
│  → Next cycle (Feb 1): 15 × INR 200 = INR 3,000                 │
│                                                                   │
│  REMOVING 3 SEATS:                                                │
│  ─────────────────                                                │
│  Credit = 3 × (200/31) × 15 = INR 290.32                        │
│  → Credit note applied to next invoice                           │
│  → Next cycle (Feb 1): 7 × INR 200 = INR 1,400                  │
│  → Net next invoice: INR 1,400 - 290.32 = INR 1,109.68          │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

### 7.4 API Contract

```json
PATCH /api/subscriptions/v1/subscriptions/{id}
Authorization: Bearer {merchant_api_key}
Content-Type: application/json
Idempotency-Key: {unique-key}

{
  "items": [
    {
      "id": "si_01HQXK...",
      "quantity": 15
    }
  ],
  "proration_mode": "IMMEDIATE",
  "metadata": {
    "reason": "team_expansion"
  }
}
```

---

## Cancellation Policies

### Policy Configuration (per merchant/plan)

```kotlin
data class CancellationPolicy(
    val mode: CancellationMode,
    val minimumCommitmentMonths: Int? = null,
    val noticePeriodDays: Int? = null,
    val earlyTerminationFee: Long? = null,
    val prorateOnCancel: Boolean = true,
    val refundMode: RefundMode = RefundMode.CREDIT_NOTE,
    val allowReactivation: Boolean = true,
    val reactivationWindowDays: Int = 30
)

enum class CancellationMode {
    IMMEDIATE,      // Cancel right now
    END_OF_TERM,    // Cancel at period end
    CUSTOM_NOTICE,  // Requires N days notice
    NO_CANCEL       // Cannot cancel during commitment
}

enum class RefundMode {
    PRORATE_REFUND,    // Refund to original payment method
    CREDIT_NOTE,       // Issue credit on account
    NO_REFUND          // No refund issued
}
```

### Policy Matrix

| Policy | Behavior | Refund | Use Case |
|--------|----------|--------|----------|
| `IMMEDIATE` | Cancel right now, stop access immediately | Prorated credit/refund | Self-serve SaaS |
| `END_OF_TERM` | Active until period end, no renewal | No refund (already paid) | Standard subscriptions |
| `CUSTOM_NOTICE` | Requires N days notice before effective | Per contract terms | Enterprise contracts |
| `NO_CANCEL` | Cannot cancel during commitment term | Penalty fee if forced | Annual lock-in plans |

### Commitment Period Enforcement

```kotlin
fun validateCancellationPolicy(
    subscription: Subscription,
    policy: CancellationPolicy,
    request: CancelRequest
): CancellationValidation {
    // Check minimum commitment
    if (policy.minimumCommitmentMonths != null) {
        val commitmentEnd = subscription.startDate
            .plus(policy.minimumCommitmentMonths, DateTimeUnit.MONTH)
        val now = Clock.System.now()

        if (now < commitmentEnd) {
            if (request.forceCancel) {
                // Allow but charge early termination fee
                return CancellationValidation.AllowedWithPenalty(
                    fee = policy.earlyTerminationFee ?: 0,
                    commitmentEnd = commitmentEnd,
                    remainingMonths = commitmentEnd.monthsUntil(now)
                )
            }
            return CancellationValidation.Denied(
                reason = "Minimum commitment not met",
                commitmentEnd = commitmentEnd,
                earliestCancelDate = commitmentEnd
            )
        }
    }

    // Check notice period
    if (policy.noticePeriodDays != null && policy.noticePeriodDays > 0) {
        val earliestEffective = Clock.System.now()
            .plus(policy.noticePeriodDays, DateTimeUnit.DAY)
        return CancellationValidation.AllowedWithNotice(
            effectiveDate = earliestEffective,
            noticeDays = policy.noticePeriodDays
        )
    }

    return CancellationValidation.Allowed
}
```

---

## State Transition Guard Rails

### Valid Transitions Matrix

```
┌───────────────────────────────────────────────────────────────────────────┐
│                    STATE TRANSITION VALIDATION                              │
├───────────────────┬───────────────────────────────────────────────────────┤
│ Current State     │ Allowed Transitions                                    │
├───────────────────┼───────────────────────────────────────────────────────┤
│ ACTIVE            │ PAUSED, PENDING_CANCELLATION, CANCELLED, PLAN_CHANGE  │
│ PAUSED            │ ACTIVE (resume), CANCELLED                             │
│ PAST_DUE          │ ACTIVE (payment cleared), PAUSED, CANCELLED           │
│ PENDING_CANCEL    │ ACTIVE (reactivate), CANCELLED                         │
│ CANCELLED         │ ─ (terminal state, no transitions)                     │
│ EXPIRED           │ ─ (terminal state, no transitions)                     │
└───────────────────┴───────────────────────────────────────────────────────┘
```

### Guard Implementation

```kotlin
class StateGuard {
    private val allowedTransitions: Map<SubscriptionStatus, Set<SubscriptionStatus>> = mapOf(
        ACTIVE to setOf(PAUSED, PENDING_CANCELLATION, CANCELLED),
        PAUSED to setOf(ACTIVE, CANCELLED),
        PAST_DUE to setOf(ACTIVE, PAUSED, CANCELLED),
        PENDING_CANCELLATION to setOf(ACTIVE, CANCELLED),
        // Terminal states
        CANCELLED to emptySet(),
        EXPIRED to emptySet()
    )

    private val planChangeAllowedFrom: Set<SubscriptionStatus> = setOf(ACTIVE)
    private val quantityChangeAllowedFrom: Set<SubscriptionStatus> = setOf(ACTIVE)

    fun validateTransition(
        subscription: Subscription,
        targetState: SubscriptionStatus
    ): ValidationResult {
        val currentState = subscription.status
        val allowed = allowedTransitions[currentState] ?: emptySet()

        if (targetState !in allowed) {
            return ValidationResult.Denied(
                "Cannot transition from $currentState to $targetState"
            )
        }

        return ValidationResult.Allowed
    }

    fun validatePlanChange(subscription: Subscription): ValidationResult {
        if (subscription.status !in planChangeAllowedFrom) {
            return ValidationResult.Denied(
                "Plan changes not allowed in ${subscription.status} state. " +
                "Clear outstanding dues first."
            )
        }
        if (subscription.pendingPlanChangeId != null) {
            return ValidationResult.Denied(
                "A plan change is already pending (${subscription.pendingPlanChangeId})"
            )
        }
        if (subscription.activeDunningCycleId != null) {
            return ValidationResult.Denied(
                "Cannot change plan during active dunning cycle"
            )
        }
        return ValidationResult.Allowed
    }

    fun validatePause(subscription: Subscription): ValidationResult {
        val base = validateTransition(subscription, PAUSED)
        if (base is ValidationResult.Denied) return base

        // Additional pause-specific checks
        val maxPauses = subscription.plan.maxPausesPerYear ?: Int.MAX_VALUE
        if (subscription.pauseCountThisYear >= maxPauses) {
            return ValidationResult.Denied(
                "Maximum pauses ($maxPauses) reached for this year"
            )
        }

        val maxDuration = subscription.plan.maxPauseDurationDays ?: 90
        // Check if previous pauses exceeded limit (informational)

        return ValidationResult.Allowed
    }
}
```

### Enforcement Rules Summary

| Rule | Description | Error Code |
|------|-------------|------------|
| No self-transition | Cannot pause a PAUSED subscription | `INVALID_STATE_TRANSITION` |
| No resume if active | Cannot resume an ACTIVE subscription | `INVALID_STATE_TRANSITION` |
| Terminal states immutable | Cannot modify CANCELLED/EXPIRED | `SUBSCRIPTION_TERMINATED` |
| Clear dues before change | Upgrade/downgrade blocked during PAST_DUE | `OUTSTANDING_DUES` |
| No change during dunning | Plan/quantity changes blocked in dunning | `ACTIVE_DUNNING_CYCLE` |
| Pause limits | Max 3 pauses per year (configurable) | `PAUSE_LIMIT_REACHED` |
| Pause duration | Max 90 days (configurable) | `PAUSE_DURATION_EXCEEDED` |
| Single pending change | Only one plan change can be pending | `PLAN_CHANGE_PENDING` |
| Commitment enforcement | Cannot cancel during lock-in period | `COMMITMENT_NOT_MET` |

---

## Webhook Events Emitted

### Event Catalog

| Action | Event Type | Trigger |
|--------|-----------|---------|
| Pause | `subscription.paused` | Subscription paused successfully |
| Resume | `subscription.resumed` | Subscription resumed (manual or auto) |
| Cancel (immediate) | `subscription.cancelled` | Subscription cancelled immediately |
| Cancel (scheduled) | `subscription.cancellation_scheduled` | End-of-term cancellation scheduled |
| Cancel (executed) | `subscription.cancelled` | Scheduled cancellation executed |
| Reactivate | `subscription.reactivated` | Pending cancellation undone |
| Upgrade | `subscription.plan_changed` | Plan upgraded (immediate or scheduled) |
| Downgrade scheduled | `subscription.plan_change_scheduled` | Downgrade scheduled for end of period |
| Downgrade applied | `subscription.plan_changed` | Downgrade applied at period end |
| Quantity change | `subscription.updated` | Seats/units added or removed |

### Event Payloads

```json
// subscription.paused
{
  "event_type": "subscription.paused",
  "subscription_id": "sub_01HQXK...",
  "merchant_id": "mer_01HQ...",
  "customer_id": "cus_01HQ...",
  "data": {
    "pause_reason": "CUSTOMER_REQUEST",
    "paused_at": "2024-01-25T10:30:00Z",
    "resume_at": "2024-04-01T00:00:00Z",
    "pause_behavior": "CREDIT_UNUSED",
    "credit_note_id": "cn_01HQ...",
    "credit_amount": 16633,
    "previous_status": "ACTIVE"
  }
}

// subscription.resumed
{
  "event_type": "subscription.resumed",
  "subscription_id": "sub_01HQXK...",
  "data": {
    "resumed_at": "2024-04-01T00:00:00Z",
    "resume_trigger": "AUTO_RESUME",
    "next_billing_date": "2024-04-15T00:00:00Z",
    "next_billing_amount": 49900,
    "pause_duration_days": 66,
    "previous_status": "PAUSED"
  }
}

// subscription.cancelled
{
  "event_type": "subscription.cancelled",
  "subscription_id": "sub_01HQXK...",
  "data": {
    "cancelled_at": "2024-01-25T10:30:00Z",
    "cancellation_reason": "CUSTOMER_REQUEST",
    "cancel_mode": "IMMEDIATE",
    "refund_amount": 16633,
    "refund_id": "rfnd_01HQ...",
    "mandate_revoked": true,
    "final_period_end": "2024-02-15T00:00:00Z",
    "previous_status": "ACTIVE"
  }
}

// subscription.cancellation_scheduled
{
  "event_type": "subscription.cancellation_scheduled",
  "subscription_id": "sub_01HQXK...",
  "data": {
    "scheduled_at": "2024-01-25T10:30:00Z",
    "cancel_at": "2024-02-15T00:00:00Z",
    "cancellation_reason": "CUSTOMER_REQUEST",
    "service_continues_until": "2024-02-15T00:00:00Z",
    "can_reactivate": true
  }
}

// subscription.plan_changed
{
  "event_type": "subscription.plan_changed",
  "subscription_id": "sub_01HQXK...",
  "data": {
    "change_type": "UPGRADE",
    "old_plan": {
      "id": "plan_basic",
      "name": "Basic",
      "amount": 49900
    },
    "new_plan": {
      "id": "plan_pro",
      "name": "Pro",
      "amount": 99900
    },
    "effective_at": "2024-01-25T10:30:00Z",
    "proration": {
      "credit_amount": 33810,
      "charge_amount": 67683,
      "net_amount": 33873,
      "invoice_id": "inv_01HQ..."
    }
  }
}

// subscription.updated (quantity change)
{
  "event_type": "subscription.updated",
  "subscription_id": "sub_01HQXK...",
  "data": {
    "change_type": "QUANTITY_CHANGE",
    "items_changed": [
      {
        "item_id": "si_01HQ...",
        "old_quantity": 10,
        "new_quantity": 15,
        "unit_price": 20000
      }
    ],
    "old_total_amount": 200000,
    "new_total_amount": 300000,
    "proration_amount": 50000,
    "proration_invoice_id": "inv_01HQ..."
  }
}
```

---

## Distributed Locking Strategy

All lifecycle operations acquire a distributed lock to prevent race conditions (e.g., concurrent pause + cancel).

```kotlin
class DistributedLockManager(
    private val redis: RedisCoroutinesCommands<String, String>,
    private val instanceId: String = UUID.randomUUID().toString()
) {
    suspend fun <T> withLock(
        key: String,
        ttl: Duration = 30.seconds,
        block: suspend () -> T
    ): T {
        val lockKey = "lock:$key"
        val lockValue = "$instanceId:${Clock.System.now().toEpochMilliseconds()}"

        // Acquire with retry
        val acquired = retryWithBackoff(maxAttempts = 5, baseDelay = 100.milliseconds) {
            redis.set(lockKey, lockValue, SetArgs().nx().px(ttl.inWholeMilliseconds)) == "OK"
        }

        if (!acquired) {
            throw ConcurrentModificationException(
                "Failed to acquire lock for $key. Another operation is in progress."
            )
        }

        try {
            return block()
        } finally {
            // Release only if we still own the lock (Lua script for atomicity)
            val script = """
                if redis.call("get", KEYS[1]) == ARGV[1] then
                    return redis.call("del", KEYS[1])
                else
                    return 0
                end
            """.trimIndent()
            redis.eval(script, ScriptOutputType.INTEGER, arrayOf(lockKey), lockValue)
        }
    }
}
```

---

## Idempotency

All lifecycle endpoints require an `Idempotency-Key` header to prevent duplicate operations:

```kotlin
class IdempotencyInterceptor(
    private val redis: RedisCoroutinesCommands<String, String>
) {
    suspend fun <T> executeIdempotent(
        key: String,
        ttl: Duration = 24.hours,
        block: suspend () -> T
    ): T {
        val idempotencyKey = "idempotency:$key"

        // Check if already processed
        val cached = redis.get(idempotencyKey)
        if (cached != null) {
            return Json.decodeFromString(cached)
        }

        // Execute operation
        val result = block()

        // Cache result
        redis.setex(idempotencyKey, ttl.inWholeSeconds, Json.encodeToString(result))

        return result
    }
}
```

---

## Error Handling

### Error Response Format

```json
{
  "error": {
    "code": "INVALID_STATE_TRANSITION",
    "message": "Cannot pause subscription in PAUSED state",
    "details": {
      "subscription_id": "sub_01HQXK...",
      "current_status": "PAUSED",
      "requested_action": "PAUSE",
      "allowed_actions": ["RESUME", "CANCEL"]
    }
  },
  "request_id": "req_01HQX..."
}
```

### Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `INVALID_STATE_TRANSITION` | 409 | Current state doesn't allow this operation |
| `SUBSCRIPTION_NOT_FOUND` | 404 | Subscription ID doesn't exist |
| `SUBSCRIPTION_TERMINATED` | 409 | Subscription is cancelled/expired |
| `OUTSTANDING_DUES` | 409 | Must clear past-due amount first |
| `ACTIVE_DUNNING_CYCLE` | 409 | Operation blocked during dunning |
| `PAUSE_LIMIT_REACHED` | 422 | Max pauses per year exhausted |
| `PAUSE_DURATION_EXCEEDED` | 422 | Would exceed max pause duration |
| `PLAN_CHANGE_PENDING` | 409 | Another plan change is scheduled |
| `COMMITMENT_NOT_MET` | 422 | Minimum commitment period not completed |
| `USAGE_EXCEEDS_PLAN` | 422 | Current usage exceeds new plan limits |
| `INCOMPATIBLE_PLAN` | 422 | Plans have different intervals/currencies |
| `MANDATE_REVOKED` | 409 | Payment mandate no longer valid |
| `CONCURRENT_MODIFICATION` | 409 | Another operation is in progress |
| `IDEMPOTENCY_CONFLICT` | 409 | Same idempotency key, different payload |

---

## Database Schema (Lifecycle-Specific)

```sql
-- Pause/resume metadata
ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS
    paused_at TIMESTAMPTZ,
    pause_reason VARCHAR(50),
    paused_by VARCHAR(100),
    resume_at TIMESTAMPTZ,
    preserve_billing_anchor BOOLEAN DEFAULT true,
    pause_count INT DEFAULT 0;

-- Cancellation metadata
ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS
    cancelled_at TIMESTAMPTZ,
    cancellation_reason VARCHAR(50),
    cancelled_by VARCHAR(100),
    cancel_at TIMESTAMPTZ,  -- scheduled cancellation date
    effective_cancellation_date TIMESTAMPTZ;

-- Plan change tracking
CREATE TABLE pending_plan_changes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    subscription_id UUID NOT NULL REFERENCES subscriptions(id),
    old_plan_id UUID NOT NULL,
    new_plan_id UUID NOT NULL,
    change_type VARCHAR(20) NOT NULL,  -- UPGRADE, DOWNGRADE
    effective_at TIMESTAMPTZ NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING',  -- PENDING, APPLIED, CANCELLED
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    applied_at TIMESTAMPTZ,
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX idx_pending_plan_changes_status_effective
    ON pending_plan_changes(status, effective_at)
    WHERE status = 'PENDING';

-- Plan change history (audit trail)
CREATE TABLE plan_change_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    subscription_id UUID NOT NULL REFERENCES subscriptions(id),
    old_plan_id UUID NOT NULL,
    new_plan_id UUID NOT NULL,
    change_type VARCHAR(20) NOT NULL,
    proration_credit BIGINT DEFAULT 0,
    proration_charge BIGINT DEFAULT 0,
    net_amount BIGINT DEFAULT 0,
    invoice_id UUID,
    effective_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Status history (full audit log)
CREATE TABLE subscription_status_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    subscription_id UUID NOT NULL REFERENCES subscriptions(id),
    from_status VARCHAR(30) NOT NULL,
    to_status VARCHAR(30) NOT NULL,
    changed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    changed_by VARCHAR(100) NOT NULL,
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX idx_status_history_sub_id
    ON subscription_status_history(subscription_id, changed_at DESC);
```

---

## Observability

### Key Metrics

| Metric | Type | Labels |
|--------|------|--------|
| `subscription.lifecycle.operation.total` | Counter | `operation`, `status`, `merchant_id` |
| `subscription.lifecycle.operation.duration_ms` | Histogram | `operation` |
| `subscription.pause.active` | Gauge | `merchant_id` |
| `subscription.cancel.reason` | Counter | `reason`, `mode` |
| `subscription.plan_change.total` | Counter | `direction` (upgrade/downgrade) |
| `subscription.proration.amount` | Histogram | `operation` |
| `subscription.lock.acquisition.duration_ms` | Histogram | — |
| `subscription.lock.timeout.total` | Counter | — |

### Structured Log Events

```json
{
  "level": "INFO",
  "message": "Subscription lifecycle operation completed",
  "subscription_id": "sub_01HQXK...",
  "merchant_id": "mer_01HQ...",
  "operation": "PAUSE",
  "from_status": "ACTIVE",
  "to_status": "PAUSED",
  "duration_ms": 145,
  "proration_amount": 16633,
  "trace_id": "abc123...",
  "span_id": "def456..."
}
```

---

## Summary

The lifecycle management workflow provides a robust, transactional system for managing subscription state changes with:

- **Atomic state transitions** via distributed locks and PostgreSQL transactions
- **Proration engine** for fair billing on mid-cycle changes
- **Policy enforcement** via configurable cancellation policies and state guards
- **Event-driven architecture** with Debezium CDC for reliable webhook delivery
- **Idempotent operations** to handle retries safely
- **Full audit trail** via status history and plan change history tables
