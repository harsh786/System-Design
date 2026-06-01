# 02 — State Machines

> Subscription, Billing Cycle, Invoice, Payment, and Mandate lifecycle state diagrams with all transitions

---

## 1. Subscription Lifecycle State Machine

```mermaid
stateDiagram-v2
    [*] --> CREATED: Merchant creates subscription

    CREATED --> PENDING_MANDATE: Mandate registration initiated
    CREATED --> ACTIVE: Immediate activation (free trial / no mandate needed)
    CREATED --> CANCELLED: Merchant cancels before activation

    PENDING_MANDATE --> ACTIVE: Mandate registered successfully
    PENDING_MANDATE --> MANDATE_FAILED: Mandate registration failed
    PENDING_MANDATE --> EXPIRED: Mandate not completed within TTL

    MANDATE_FAILED --> PENDING_MANDATE: Retry mandate registration
    MANDATE_FAILED --> CANCELLED: Merchant/customer cancels

    ACTIVE --> TRIAL: Free trial period starts
    ACTIVE --> BILLING: Billing cycle triggered
    ACTIVE --> PAUSED: Merchant/customer pauses
    ACTIVE --> PENDING_CANCELLATION: Cancel requested (end of period)
    ACTIVE --> CANCELLED: Immediate cancellation
    ACTIVE --> PLAN_CHANGE_PENDING: Upgrade/downgrade initiated

    TRIAL --> ACTIVE: Trial ends, billing starts
    TRIAL --> CANCELLED: Customer cancels during trial
    TRIAL --> TRIAL_EXPIRED: Trial ends, no payment method

    TRIAL_EXPIRED --> ACTIVE: Payment method added
    TRIAL_EXPIRED --> CANCELLED: Grace period expired

    BILLING --> ACTIVE: Payment successful
    BILLING --> PAST_DUE: Payment failed, entering dunning
    BILLING --> CANCELLED: Hard decline (stolen card, closed account)

    PAST_DUE --> ACTIVE: Dunning recovery successful
    PAST_DUE --> CANCELLED: All retries exhausted
    PAST_DUE --> PAUSED: Merchant pauses during dunning

    PAUSED --> ACTIVE: Resumed by merchant/customer
    PAUSED --> CANCELLED: Cancelled while paused

    PENDING_CANCELLATION --> CANCELLED: End of billing period reached

    PLAN_CHANGE_PENDING --> ACTIVE: Plan change effective

    CANCELLED --> [*]
    EXPIRED --> [*]
```

### Subscription State Definitions

| State | Description | Billable | Mandate Active |
|-------|-------------|----------|----------------|
| `CREATED` | Subscription created, awaiting setup | No | No |
| `PENDING_MANDATE` | Waiting for customer to complete mandate registration | No | Pending |
| `MANDATE_FAILED` | Mandate registration failed, awaiting retry or cancel | No | Failed |
| `ACTIVE` | Subscription live, can be billed | Yes | Yes |
| `TRIAL` | In free trial period, no charges | No | Optional |
| `TRIAL_EXPIRED` | Trial ended without payment method | No | No |
| `BILLING` | Billing cycle in progress (transient) | Charging | Yes |
| `PAST_DUE` | Payment failed, in dunning/retry window | Grace | Yes |
| `PAUSED` | Temporarily suspended (no billing) | No | Held |
| `PENDING_CANCELLATION` | Active until end of current period | Yes (until EOT) | Yes |
| `PLAN_CHANGE_PENDING` | Upgrade/downgrade processing | Yes (old plan) | Yes |
| `CANCELLED` | Permanently terminated | No | Revoked |
| `EXPIRED` | Mandate expired, subscription invalid | No | Expired |

### Transition Rules

```kotlin
enum class SubscriptionTransition(
    val from: Set<SubscriptionStatus>,
    val to: SubscriptionStatus,
    val trigger: String
) {
    INITIATE_MANDATE(
        from = setOf(CREATED),
        to = PENDING_MANDATE,
        trigger = "mandate.registration.initiated"
    ),
    ACTIVATE(
        from = setOf(PENDING_MANDATE, TRIAL_EXPIRED, PAST_DUE, PAUSED, PLAN_CHANGE_PENDING),
        to = ACTIVE,
        trigger = "subscription.activated"
    ),
    START_TRIAL(
        from = setOf(ACTIVE),
        to = TRIAL,
        trigger = "trial.started"
    ),
    ENTER_BILLING(
        from = setOf(ACTIVE),
        to = BILLING,
        trigger = "billing.cycle.started"
    ),
    PAYMENT_FAILED(
        from = setOf(BILLING),
        to = PAST_DUE,
        trigger = "payment.failed"
    ),
    PAUSE(
        from = setOf(ACTIVE, PAST_DUE),
        to = PAUSED,
        trigger = "subscription.paused"
    ),
    CANCEL_IMMEDIATE(
        from = setOf(CREATED, ACTIVE, TRIAL, PAST_DUE, PAUSED, PENDING_MANDATE, MANDATE_FAILED),
        to = CANCELLED,
        trigger = "subscription.cancelled"
    ),
    CANCEL_END_OF_TERM(
        from = setOf(ACTIVE),
        to = PENDING_CANCELLATION,
        trigger = "subscription.cancellation.scheduled"
    ),
    INITIATE_PLAN_CHANGE(
        from = setOf(ACTIVE),
        to = PLAN_CHANGE_PENDING,
        trigger = "plan.change.initiated"
    );
}
```

---

## 2. Billing Cycle State Machine

```mermaid
stateDiagram-v2
    [*] --> SCHEDULED: Billing schedule computed

    SCHEDULED --> PRE_DEBIT_NOTIFIED: Pre-debit notification sent (T-24h)
    SCHEDULED --> GENERATING: Notification not required (card-on-file)

    PRE_DEBIT_NOTIFIED --> GENERATING: Notification period elapsed
    PRE_DEBIT_NOTIFIED --> CUSTOMER_OPTED_OUT: Customer declined charge

    GENERATING --> INVOICE_CREATED: Invoice generated successfully
    GENERATING --> GENERATION_FAILED: Calculation error

    GENERATION_FAILED --> GENERATING: Retry generation
    GENERATION_FAILED --> SKIPPED: Manual intervention required

    INVOICE_CREATED --> PAYMENT_INITIATED: Payment execution started
    INVOICE_CREATED --> WAIVED: Invoice waived (credit applied)

    PAYMENT_INITIATED --> COMPLETED: Payment successful
    PAYMENT_INITIATED --> FAILED: Payment declined
    PAYMENT_INITIATED --> PENDING: Async payment (UPI mandate)

    PENDING --> COMPLETED: Async confirmation received
    PENDING --> FAILED: Async timeout / decline

    FAILED --> DUNNING: Entering retry flow
    FAILED --> COMPLETED: Manual payment by customer

    DUNNING --> COMPLETED: Retry successful
    DUNNING --> EXHAUSTED: All retries failed

    EXHAUSTED --> SUBSCRIPTION_CANCELLED: Auto-cancel triggered
    EXHAUSTED --> COMPLETED: Manual intervention / payment

    CUSTOMER_OPTED_OUT --> SKIPPED: Cycle skipped

    COMPLETED --> [*]
    SKIPPED --> [*]
    WAIVED --> [*]
    SUBSCRIPTION_CANCELLED --> [*]
```

### Billing Cycle State Definitions

| State | Description | Duration |
|-------|-------------|----------|
| `SCHEDULED` | Future billing cycle computed and stored | Until T-24h |
| `PRE_DEBIT_NOTIFIED` | 24h pre-debit notification sent (RBI mandate) | 24 hours |
| `GENERATING` | Invoice being calculated (plan + usage + tax + discounts) | Seconds |
| `GENERATION_FAILED` | Invoice generation error (missing usage data, FX failure) | Until retry |
| `INVOICE_CREATED` | Invoice finalized, ready for payment | Until charge |
| `PAYMENT_INITIATED` | Payment request sent to gateway | Seconds-minutes |
| `PENDING` | Awaiting async payment confirmation | Up to 30 min |
| `COMPLETED` | Payment successful, cycle complete | Terminal |
| `FAILED` | Payment declined | Transient |
| `DUNNING` | In retry/dunning flow | 3-7 days |
| `EXHAUSTED` | All retries failed | Terminal trigger |
| `SKIPPED` | Cycle intentionally skipped | Terminal |
| `WAIVED` | Invoice waived (credits covered full amount) | Terminal |
| `CUSTOMER_OPTED_OUT` | Customer declined pre-debit notification | Terminal |
| `SUBSCRIPTION_CANCELLED` | Subscription cancelled due to payment failure | Terminal |

---

## 3. Invoice State Machine

```mermaid
stateDiagram-v2
    [*] --> DRAFT: Invoice calculation started

    DRAFT --> OPEN: Invoice finalized and issued
    DRAFT --> VOID: Cancelled before issuing

    OPEN --> PAYMENT_PENDING: Payment initiated
    OPEN --> PAID: Immediate payment success
    OPEN --> VOID: Voided by merchant

    PAYMENT_PENDING --> PAID: Payment confirmed
    PAYMENT_PENDING --> FAILED: Payment declined
    PAYMENT_PENDING --> PARTIALLY_PAID: Partial amount collected

    FAILED --> PAYMENT_PENDING: Retry payment
    FAILED --> UNCOLLECTIBLE: Marked uncollectible after dunning
    FAILED --> PAID: Customer pays manually

    PARTIALLY_PAID --> PAID: Remaining amount collected
    PARTIALLY_PAID --> UNCOLLECTIBLE: Write-off remaining

    PAID --> REFUNDED: Full refund issued
    PAID --> PARTIALLY_REFUNDED: Partial refund issued
    PAID --> CREDITED: Credit note issued

    UNCOLLECTIBLE --> PAID: Late payment received
    UNCOLLECTIBLE --> WRITTEN_OFF: Accounting write-off

    REFUNDED --> [*]
    PARTIALLY_REFUNDED --> [*]
    CREDITED --> [*]
    VOID --> [*]
    WRITTEN_OFF --> [*]
```

### Invoice State Definitions

| State | Description | Revenue Recognized |
|-------|-------------|-------------------|
| `DRAFT` | Being calculated, not yet final | No |
| `OPEN` | Finalized, awaiting payment | Accrued |
| `PAYMENT_PENDING` | Payment in progress | Accrued |
| `PAID` | Successfully collected | Yes |
| `PARTIALLY_PAID` | Partial amount collected | Partial |
| `FAILED` | Payment attempt failed | Accrued |
| `UNCOLLECTIBLE` | Marked as bad debt after dunning exhaustion | Reversed |
| `VOID` | Cancelled/voided | No |
| `REFUNDED` | Full amount refunded | Reversed |
| `PARTIALLY_REFUNDED` | Partial refund issued | Partial reversal |
| `CREDITED` | Credit note applied to account | Deferred |
| `WRITTEN_OFF` | Written off in accounting | Loss |

---

## 4. Mandate State Machine

```mermaid
stateDiagram-v2
    [*] --> INITIATED: Mandate creation requested

    INITIATED --> PENDING_CUSTOMER_AUTH: Awaiting customer authorization
    INITIATED --> FAILED: Validation/setup failure

    PENDING_CUSTOMER_AUTH --> REGISTERED: Customer authorized successfully
    PENDING_CUSTOMER_AUTH --> REJECTED: Customer rejected mandate
    PENDING_CUSTOMER_AUTH --> EXPIRED: Authorization window expired

    REGISTERED --> ACTIVE: First successful debit (confirmed)
    REGISTERED --> REVOKED: Customer revoked before first use

    ACTIVE --> PAUSED: Temporarily paused
    ACTIVE --> REVOKED: Customer/merchant revoked
    ACTIVE --> EXPIRED: Mandate validity period ended
    ACTIVE --> AMOUNT_EXCEEDED: Debit exceeds registered max

    PAUSED --> ACTIVE: Resumed
    PAUSED --> REVOKED: Cancelled while paused

    AMOUNT_EXCEEDED --> ACTIVE: Within limits again (next cycle)
    AMOUNT_EXCEEDED --> MODIFIED: Mandate amount updated

    MODIFIED --> PENDING_CUSTOMER_AUTH: Re-authorization required
    MODIFIED --> ACTIVE: Modification accepted (within rules)

    FAILED --> INITIATED: Retry registration
    FAILED --> [*]

    REVOKED --> [*]
    EXPIRED --> [*]
    REJECTED --> [*]
```

### Mandate Types & Rules

| Mandate Type | Max Amount | Frequency | Pre-debit Notice | Validity |
|-------------|-----------|-----------|-----------------|----------|
| UPI Autopay | INR 1,00,000 | Daily/Weekly/Monthly/Yearly | 24h mandatory | Up to 5 years |
| eNACH/NACH | INR 1,00,00,000 | Monthly/Quarterly/Yearly | 24h mandatory | Perpetual (with renewal) |
| Card-on-File | No RBI limit (acquirer limit applies) | Any | Optional (best practice) | Until card expiry |
| SI (Standing Instruction) | INR 15,000 (no AFA) / unlimited (with AFA) | Any | 24h mandatory | As registered |

### Mandate Debit Rules

```kotlin
data class MandateDebitValidation(
    val maxAmountPerDebit: Money,        // Cannot exceed registered max
    val frequencyRule: FrequencyRule,     // Cannot debit more frequently than registered
    val preDebitHours: Int = 24,          // Pre-debit notification window
    val cooldownAfterFailure: Duration,   // Wait time after failed debit
    val maxRetriesPerCycle: Int = 3,      // Retry limit per billing cycle
    val requiresAFA: Boolean,            // Additional Factor of Authentication
    val validUntil: LocalDate            // Mandate expiry date
)
```

---

## 5. Payment (Subscription Charge) State Machine

```mermaid
stateDiagram-v2
    [*] --> CREATED: Charge initiated for invoice

    CREATED --> PROCESSING: Sent to payment gateway
    CREATED --> BLOCKED: Risk/fraud check failed

    PROCESSING --> AUTHORIZED: Pre-auth successful (if applicable)
    PROCESSING --> CAPTURED: Direct capture successful
    PROCESSING --> FAILED: Gateway declined
    PROCESSING --> PENDING: Awaiting async response

    AUTHORIZED --> CAPTURED: Capture executed
    AUTHORIZED --> VOIDED: Authorization voided

    PENDING --> CAPTURED: Async success callback
    PENDING --> FAILED: Async failure / timeout

    CAPTURED --> SETTLED: Settlement confirmed
    CAPTURED --> REFUND_INITIATED: Refund requested

    FAILED --> RETRY_SCHEDULED: Queued for dunning retry
    FAILED --> ABANDONED: No retry (hard decline)

    RETRY_SCHEDULED --> PROCESSING: Retry executed
    RETRY_SCHEDULED --> ABANDONED: Max retries reached

    REFUND_INITIATED --> REFUNDED: Refund confirmed
    REFUND_INITIATED --> REFUND_FAILED: Refund failed

    BLOCKED --> PROCESSING: Manual release
    BLOCKED --> ABANDONED: Permanently blocked

    SETTLED --> [*]
    REFUNDED --> [*]
    ABANDONED --> [*]
    VOIDED --> [*]
```

### Decline Code Classification

```kotlin
enum class DeclineCategory(
    val retryable: Boolean,
    val suggestedDelay: Duration,
    val maxRetries: Int,
    val action: String
) {
    // Soft Declines — Retryable
    INSUFFICIENT_FUNDS(true, 4.hours, 5, "Retry with backoff"),
    ISSUER_UNAVAILABLE(true, 1.hours, 3, "Retry soon"),
    PROCESSING_ERROR(true, 30.minutes, 3, "Immediate retry"),
    RATE_LIMIT(true, 2.hours, 3, "Backoff retry"),
    TIMEOUT(true, 1.hours, 3, "Retry with timeout increase"),

    // Hard Declines — Non-retryable
    STOLEN_CARD(false, Duration.ZERO, 0, "Cancel mandate, notify merchant"),
    CLOSED_ACCOUNT(false, Duration.ZERO, 0, "Cancel mandate, notify merchant"),
    FRAUD_SUSPECTED(false, Duration.ZERO, 0, "Block + notify"),
    INVALID_CARD(false, Duration.ZERO, 0, "Request payment method update"),
    DO_NOT_HONOR(false, Duration.ZERO, 0, "Notify customer to contact bank"),

    // Action Required — Customer intervention
    AUTHENTICATION_REQUIRED(false, Duration.ZERO, 0, "Send payment link to customer"),
    MANDATE_REVOKED(false, Duration.ZERO, 0, "Request new mandate"),
    AMOUNT_EXCEEDS_LIMIT(false, Duration.ZERO, 0, "Split charge or update mandate");
}
```

---

## 6. Coupon / Discount State Machine

```mermaid
stateDiagram-v2
    [*] --> CREATED: Coupon defined

    CREATED --> ACTIVE: Activation date reached / immediately
    CREATED --> SCHEDULED: Future activation date

    SCHEDULED --> ACTIVE: Start date reached

    ACTIVE --> FULLY_REDEEMED: Max redemption count reached
    ACTIVE --> EXPIRED: Expiry date reached
    ACTIVE --> DEACTIVATED: Manually deactivated

    FULLY_REDEEMED --> [*]
    EXPIRED --> [*]
    DEACTIVATED --> ACTIVE: Re-activated
    DEACTIVATED --> [*]
```

---

## 7. Composite State: Subscription + Billing Timeline

```mermaid
gantt
    title Subscription Lifecycle Timeline
    dateFormat  YYYY-MM-DD
    axisFormat  %b %d

    section Subscription
    Created             :done, s1, 2024-01-01, 1d
    Mandate Pending     :done, s2, 2024-01-01, 3d
    Trial Period        :active, s3, 2024-01-04, 14d
    Active (Billing)    :s4, 2024-01-18, 90d

    section Billing Cycles
    Pre-debit Notice    :crit, b1, 2024-01-17, 1d
    Cycle 1 (Invoice)   :b2, 2024-01-18, 1d
    Cycle 1 (Payment)   :b3, 2024-01-18, 1d
    Pre-debit Notice    :crit, b4, 2024-02-16, 1d
    Cycle 2 (Invoice)   :b5, 2024-02-17, 1d
    Cycle 2 (Payment)   :b6, 2024-02-17, 1d
    Pre-debit Notice    :crit, b7, 2024-03-17, 1d
    Cycle 3 (Invoice)   :b8, 2024-03-18, 1d

    section Dunning (if failed)
    Payment Failed      :crit, d1, 2024-03-18, 1d
    Retry 1 (4h)        :d2, 2024-03-18, 1d
    Retry 2 (24h)       :d3, 2024-03-19, 1d
    Retry 3 (48h)       :d4, 2024-03-21, 1d
    Grace Period        :d5, 2024-03-18, 7d
    Cancel (if failed)  :crit, d6, 2024-03-25, 1d
```

---

## 8. Event Emission per State Transition

| Transition | Event Emitted | Kafka Topic | Webhook Event |
|-----------|--------------|-------------|---------------|
| → CREATED | `subscription.created` | `subscription.lifecycle` | Yes |
| → PENDING_MANDATE | `subscription.mandate.initiated` | `subscription.mandate` | Yes |
| → ACTIVE | `subscription.activated` | `subscription.lifecycle` | Yes |
| → TRIAL | `subscription.trial.started` | `subscription.lifecycle` | Yes |
| TRIAL → ACTIVE | `subscription.trial.ended` | `subscription.lifecycle` | Yes |
| → BILLING | `billing.cycle.started` | `subscription.billing` | No |
| → INVOICE_CREATED | `invoice.created` | `subscription.invoice` | Yes |
| → PAID | `invoice.paid` | `subscription.invoice` | Yes |
| → FAILED | `invoice.payment_failed` | `subscription.invoice` | Yes |
| → PAST_DUE | `subscription.past_due` | `subscription.lifecycle` | Yes |
| → DUNNING | `dunning.started` | `subscription.dunning` | Yes |
| → PAUSED | `subscription.paused` | `subscription.lifecycle` | Yes |
| → ACTIVE (from pause) | `subscription.resumed` | `subscription.lifecycle` | Yes |
| → PENDING_CANCELLATION | `subscription.cancellation.scheduled` | `subscription.lifecycle` | Yes |
| → CANCELLED | `subscription.cancelled` | `subscription.lifecycle` | Yes |
| → PLAN_CHANGE_PENDING | `subscription.plan_change.initiated` | `subscription.lifecycle` | Yes |
| Plan change done | `subscription.plan_change.completed` | `subscription.lifecycle` | Yes |
| Mandate → ACTIVE | `mandate.activated` | `subscription.mandate` | Yes |
| Mandate → REVOKED | `mandate.revoked` | `subscription.mandate` | Yes |
