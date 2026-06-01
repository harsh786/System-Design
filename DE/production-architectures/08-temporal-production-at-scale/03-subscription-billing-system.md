# Problem 3: Subscription Billing System

## The Problem

Design a production subscription billing system managing:
- **100M+ active subscriptions** running perpetually
- **Monthly/annual billing cycles** with automatic renewal
- **Plan changes** (upgrades, downgrades, prorations mid-cycle)
- **Dunning management** (failed payment retry with escalating actions)
- **Usage-based billing** aggregation from metered events
- **Revenue recognition** (ASC 606 compliance)
- **Multi-currency, multi-region** billing
- **Trial-to-paid conversion** with configurable trial periods

## Architecture

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                    SUBSCRIPTION BILLING ARCHITECTURE                               │
├──────────────────────────────────────────────────────────────────────────────────┤
│                                                                                    │
│  ┌────────────────┐  ┌────────────────────────────────────────────────────────┐  │
│  │ Billing API    │  │                 TEMPORAL CLUSTER                         │  │
│  │ (Plan mgmt,   │──│   Namespace: billing-prod                               │  │
│  │  Subscription  │  │                                                         │  │
│  │  lifecycle)    │  │   ┌──────────────────────────────────────────────────┐  │  │
│  └────────────────┘  │   │  ONE WORKFLOW PER SUBSCRIPTION                   │  │  │
│                       │   │  (100M+ concurrent workflows using CAN)          │  │  │
│  ┌────────────────┐  │   │                                                   │  │  │
│  │ Usage Events   │  │   │  SubscriptionLifecycleWorkflow                    │  │  │
│  │ (Kafka → Agg)  │──│   │   └── BillingCycleWorkflow (child, per period)   │  │  │
│  │                │  │   │       └── DunningWorkflow (child, on failure)     │  │  │
│  └────────────────┘  │   └──────────────────────────────────────────────────┘  │  │
│                       │                                                         │  │
│  ┌────────────────┐  │   Task Queues:                                          │  │
│  │ Schedules      │  │   ├── subscription-lifecycle-tq (main workflow)         │  │
│  │ (Batch billing │──│   ├── billing-cycle-tq (invoice calculation)            │  │
│  │  triggers)     │  │   ├── dunning-tq (payment retries)                     │  │
│  └────────────────┘  │   ├── usage-aggregation-tq (metered billing)           │  │
│                       │   ├── revenue-recognition-tq (ASC 606)                 │  │
│                       │   └── notification-tq (emails, in-app)                 │  │
│                       └────────────────────────────────────────────────────────┘  │
│                                            │                                      │
│     ┌──────────────────────────────────────┼──────────────────────────────────┐  │
│     │                                      │                                   │  │
│     ▼                                      ▼                                   ▼  │
│  ┌──────────────────┐  ┌──────────────────────────────┐  ┌─────────────────────┐│
│  │ Lifecycle Workers │  │    Billing Workers             │  │ Dunning Workers     ││
│  │ (30 pods)         │  │    (20 pods)                   │  │ (10 pods)           ││
│  │                   │  │                                │  │                     ││
│  │ - Plan changes    │  │  - Invoice calculation        │  │ - Payment retries   ││
│  │ - State machine   │  │  - Payment charging           │  │ - Escalation logic  ││
│  │ - Continue-as-new │  │  - Proration math             │  │ - Account actions   ││
│  └──────────────────┘  │  - Revenue recognition        │  │ - Recovery flows    ││
│                         └──────────────────────────────────┘  └─────────────────────┘│
│                                                                                    │
│  ┌────────────────────────────────────────────────────────────────────────────┐  │
│  │                           DATA STORES                                       │  │
│  │                                                                             │  │
│  │  ┌────────────┐ ┌──────────────┐ ┌─────────────┐ ┌──────────────────────┐ │  │
│  │  │Subscription│ │   Invoice    │ │  Payment    │ │  Usage Events        │ │  │
│  │  │ Store      │ │   Ledger     │ │  Gateway    │ │  (TimescaleDB)       │ │  │
│  │  │(PostgreSQL)│ │  (PostgreSQL)│ │  (Stripe/   │ │                      │ │  │
│  │  │            │ │              │ │   Braintree)│ │  - Metered usage     │ │  │
│  │  │- Plans     │ │- Invoices    │ │             │ │  - API calls         │ │  │
│  │  │- Subs      │ │- Line items  │ │             │ │  - Storage GB        │ │  │
│  │  │- History   │ │- Adjustments │ │             │ │  - Compute hours     │ │  │
│  │  └────────────┘ └──────────────┘ └─────────────┘ └──────────────────────┘ │  │
│  └────────────────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────────────┘
```

## Subscription Lifecycle

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    SUBSCRIPTION LIFECYCLE                                 │
└─────────────────────────────────────────────────────────────────────────┘

  ┌───────┐     ┌────────┐     ┌────────┐     ┌────────┐
  │ TRIAL │────►│ ACTIVE │────►│ PAST   │────►│CANCELED│
  │       │     │        │     │ DUE    │     │        │
  └───┬───┘     └───┬────┘     └───┬────┘     └────────┘
      │             │              │
      │ expires     │ signal:      │ payment
      │ (no pay)    │ ChangePlan   │ recovered
      ▼             ▼              ▼
  ┌───────┐     ┌────────┐     ┌────────┐
  │EXPIRED│     │ACTIVE  │     │ ACTIVE │  (back to active)
  │(trial)│     │(new    │     │        │
  └───────┘     │ plan)  │     └────────┘
                └────────┘

  Signals at ANY state:
  ─────────────────────
  PauseSubscription   → PAUSED (billing stops, timer for auto-resume)
  ResumeSubscription  → ACTIVE (resume billing)
  CancelSubscription  → end of current period → CANCELED
  UpdatePaymentMethod → update stored payment, retry if past_due
  ChangePlan          → immediate or end-of-period plan change
```

## Complete Go Implementation

### Domain Types

```go
package billing

import "time"

type Subscription struct {
	ID                string            `json:"id"`
	CustomerID        string            `json:"customer_id"`
	PlanID            string            `json:"plan_id"`
	Status            SubStatus         `json:"status"`
	BillingInterval   BillingInterval   `json:"billing_interval"`
	CurrentPeriodStart time.Time        `json:"current_period_start"`
	CurrentPeriodEnd   time.Time        `json:"current_period_end"`
	TrialEnd          *time.Time        `json:"trial_end,omitempty"`
	PaymentMethodID   string            `json:"payment_method_id"`
	Currency          string            `json:"currency"`
	Region            string            `json:"region"`
	Metadata          map[string]string `json:"metadata"`
	CreatedAt         time.Time         `json:"created_at"`
	CanceledAt        *time.Time        `json:"canceled_at,omitempty"`
	CancelAtPeriodEnd bool              `json:"cancel_at_period_end"`
}

type SubStatus string
const (
	SubStatusTrialing  SubStatus = "TRIALING"
	SubStatusActive    SubStatus = "ACTIVE"
	SubStatusPastDue   SubStatus = "PAST_DUE"
	SubStatusPaused    SubStatus = "PAUSED"
	SubStatusCanceled  SubStatus = "CANCELED"
	SubStatusExpired   SubStatus = "EXPIRED"
)

type BillingInterval string
const (
	IntervalMonthly  BillingInterval = "MONTHLY"
	IntervalQuarterly BillingInterval = "QUARTERLY"
	IntervalAnnual   BillingInterval = "ANNUAL"
)

type Plan struct {
	ID              string      `json:"id"`
	Name            string      `json:"name"`
	BasePrice       int64       `json:"base_price_cents"`
	Currency        string      `json:"currency"`
	Interval        BillingInterval `json:"interval"`
	UsageTiers      []UsageTier `json:"usage_tiers,omitempty"`
	Features        []string    `json:"features"`
	TrialDays       int         `json:"trial_days"`
}

type UsageTier struct {
	Metric    string `json:"metric"` // e.g., "api_calls", "storage_gb"
	UpTo      int64  `json:"up_to"` // 0 = unlimited
	UnitPrice int64  `json:"unit_price_cents"`
}

// SubscriptionState is the workflow's persistent state
type SubscriptionState struct {
	Subscription     Subscription      `json:"subscription"`
	CurrentPlan      Plan              `json:"current_plan"`
	BillingCycle     int               `json:"billing_cycle"`
	TotalRevenue     int64             `json:"total_revenue_cents"`
	FailedAttempts   int               `json:"failed_attempts"`
	LastPaymentAt    *time.Time        `json:"last_payment_at,omitempty"`
	LastInvoiceID    string            `json:"last_invoice_id"`
	PendingPlanChange *PlanChange      `json:"pending_plan_change,omitempty"`
	UsageThisPeriod  map[string]int64  `json:"usage_this_period"`
	PauseResumeDate  *time.Time        `json:"pause_resume_date,omitempty"`
	DunningState     *DunningState     `json:"dunning_state,omitempty"`
}

type PlanChange struct {
	NewPlanID   string `json:"new_plan_id"`
	EffectiveAt string `json:"effective_at"` // "immediate" or "end_of_period"
	RequestedAt time.Time `json:"requested_at"`
}

type DunningState struct {
	Attempts       int       `json:"attempts"`
	LastAttemptAt  time.Time `json:"last_attempt_at"`
	NextAttemptAt  time.Time `json:"next_attempt_at"`
	EscalationLevel int     `json:"escalation_level"`
}

type Invoice struct {
	ID              string        `json:"id"`
	SubscriptionID  string        `json:"subscription_id"`
	CustomerID      string        `json:"customer_id"`
	PeriodStart     time.Time     `json:"period_start"`
	PeriodEnd       time.Time     `json:"period_end"`
	LineItems       []LineItem    `json:"line_items"`
	Subtotal        int64         `json:"subtotal_cents"`
	Tax             int64         `json:"tax_cents"`
	Total           int64         `json:"total_cents"`
	Currency        string        `json:"currency"`
	Status          InvoiceStatus `json:"status"`
	PaidAt          *time.Time    `json:"paid_at,omitempty"`
}

type LineItem struct {
	Description string `json:"description"`
	Quantity    int64  `json:"quantity"`
	UnitPrice   int64  `json:"unit_price_cents"`
	Amount      int64  `json:"amount_cents"`
	Type        string `json:"type"` // "base", "usage", "proration_credit", "proration_debit"
}

type InvoiceStatus string
const (
	InvoiceStatusDraft   InvoiceStatus = "DRAFT"
	InvoiceStatusOpen    InvoiceStatus = "OPEN"
	InvoiceStatusPaid    InvoiceStatus = "PAID"
	InvoiceStatusVoid    InvoiceStatus = "VOID"
	InvoiceStatusUncollectible InvoiceStatus = "UNCOLLECTIBLE"
)

// Signal types
type ChangePlanSignal struct {
	NewPlanID   string `json:"new_plan_id"`
	Immediate   bool   `json:"immediate"`
}

type UpdatePaymentSignal struct {
	PaymentMethodID string `json:"payment_method_id"`
}

type PauseSignal struct {
	ResumeAfter time.Duration `json:"resume_after"`
	Reason      string        `json:"reason"`
}

type CancelSignal struct {
	Reason        string `json:"reason"`
	AtPeriodEnd   bool   `json:"at_period_end"`
	FeedbackScore int    `json:"feedback_score"`
}
```

### Subscription Lifecycle Workflow

```go
package workflows

import (
	"fmt"
	"time"

	"go.temporal.io/sdk/temporal"
	"go.temporal.io/sdk/workflow"

	"github.com/company/billing/activities"
	"github.com/company/billing/domain"
)

const (
	SignalChangePlan         = "change-plan"
	SignalUpdatePayment      = "update-payment"
	SignalPauseSubscription  = "pause-subscription"
	SignalResumeSubscription = "resume-subscription"
	SignalCancelSubscription = "cancel-subscription"
	SignalUsageEvent         = "usage-event"

	QueryGetState       = "get-subscription-state"
	QueryGetNextBilling = "get-next-billing-date"
	QueryGetInvoiceHistory = "get-invoice-history"
)

// SubscriptionLifecycleWorkflow manages a single subscription for its entire lifetime.
// Uses continue-as-new after each billing cycle to prevent unbounded history growth.
// One instance per subscription = 100M+ concurrent workflows.
func SubscriptionLifecycleWorkflow(ctx workflow.Context, state domain.SubscriptionState) error {
	logger := workflow.GetLogger(ctx)
	logger.Info("Subscription lifecycle",
		"subID", state.Subscription.ID,
		"status", state.Subscription.Status,
		"cycle", state.BillingCycle,
	)

	// Search attributes for visibility
	_ = workflow.UpsertSearchAttributes(ctx, map[string]interface{}{
		"SubscriptionID": state.Subscription.ID,
		"CustomerID":     state.Subscription.CustomerID,
		"PlanID":         state.Subscription.PlanID,
		"Status":         string(state.Subscription.Status),
		"BillingCycle":   state.BillingCycle,
		"Region":         state.Subscription.Region,
		"MRR":            state.CurrentPlan.BasePrice,
	})

	// Register query handlers
	_ = workflow.SetQueryHandler(ctx, QueryGetState, func() (*domain.SubscriptionState, error) {
		return &state, nil
	})
	_ = workflow.SetQueryHandler(ctx, QueryGetNextBilling, func() (time.Time, error) {
		return state.Subscription.CurrentPeriodEnd, nil
	})

	// Signal channels
	changePlanCh := workflow.GetSignalChannel(ctx, SignalChangePlan)
	updatePaymentCh := workflow.GetSignalChannel(ctx, SignalUpdatePayment)
	pauseCh := workflow.GetSignalChannel(ctx, SignalPauseSubscription)
	resumeCh := workflow.GetSignalChannel(ctx, SignalResumeSubscription)
	cancelCh := workflow.GetSignalChannel(ctx, SignalCancelSubscription)

	// ─────────────────────────────────────────────────────────────────────────
	// TRIAL PERIOD HANDLING
	// ─────────────────────────────────────────────────────────────────────────
	if state.Subscription.Status == domain.SubStatusTrialing && state.Subscription.TrialEnd != nil {
		trialRemaining := state.Subscription.TrialEnd.Sub(workflow.Now(ctx))
		if trialRemaining > 0 {
			logger.Info("In trial period", "remaining", trialRemaining)

			// Wait for trial to end (or signals)
			trialTimer := workflow.NewTimer(ctx, trialRemaining)
			trialEnded := false

			for !trialEnded {
				selector := workflow.NewSelector(ctx)

				selector.AddFuture(trialTimer, func(f workflow.Future) {
					trialEnded = true
				})

				selector.AddReceive(cancelCh, func(ch workflow.ReceiveChannel, more bool) {
					var signal domain.CancelSignal
					ch.Receive(ctx, &signal)
					state.Subscription.Status = domain.SubStatusCanceled
					now := workflow.Now(ctx)
					state.Subscription.CanceledAt = &now
					trialEnded = true
				})

				selector.AddReceive(changePlanCh, func(ch workflow.ReceiveChannel, more bool) {
					var signal domain.ChangePlanSignal
					ch.Receive(ctx, &signal)
					state.PendingPlanChange = &domain.PlanChange{
						NewPlanID:   signal.NewPlanID,
						EffectiveAt: "end_of_trial",
						RequestedAt: workflow.Now(ctx),
					}
				})

				selector.Select(ctx)
			}

			if state.Subscription.Status == domain.SubStatusCanceled {
				return finalizeSubscription(ctx, &state, "trial_cancelled")
			}

			// Trial ended - convert to paid
			if state.Subscription.PaymentMethodID == "" {
				// No payment method - expire
				state.Subscription.Status = domain.SubStatusExpired
				return finalizeSubscription(ctx, &state, "trial_expired_no_payment")
			}

			// Apply pending plan change if any
			if state.PendingPlanChange != nil {
				state.CurrentPlan = loadPlan(state.PendingPlanChange.NewPlanID)
				state.Subscription.PlanID = state.PendingPlanChange.NewPlanID
				state.PendingPlanChange = nil
			}

			state.Subscription.Status = domain.SubStatusActive
			state.Subscription.CurrentPeriodStart = workflow.Now(ctx)
			state.Subscription.CurrentPeriodEnd = calculatePeriodEnd(
				workflow.Now(ctx), state.Subscription.BillingInterval,
			)
			logger.Info("Trial converted to paid", "plan", state.Subscription.PlanID)
		}
	}

	// ─────────────────────────────────────────────────────────────────────────
	// MAIN BILLING LOOP (one cycle per continue-as-new)
	// ─────────────────────────────────────────────────────────────────────────
	if state.Subscription.Status == domain.SubStatusActive ||
		state.Subscription.Status == domain.SubStatusPastDue {

		// Calculate time until next billing
		timeUntilBilling := state.Subscription.CurrentPeriodEnd.Sub(workflow.Now(ctx))
		if timeUntilBilling < 0 {
			timeUntilBilling = 0 // Bill immediately if overdue
		}

		logger.Info("Waiting for billing cycle",
			"nextBilling", state.Subscription.CurrentPeriodEnd,
			"waitDuration", timeUntilBilling,
		)

		billingTimer := workflow.NewTimer(ctx, timeUntilBilling)
		billingReady := false
		cancelled := false
		paused := false

		for !billingReady && !cancelled && !paused {
			selector := workflow.NewSelector(ctx)

			selector.AddFuture(billingTimer, func(f workflow.Future) {
				billingReady = true
			})

			// Handle plan change signal
			selector.AddReceive(changePlanCh, func(ch workflow.ReceiveChannel, more bool) {
				var signal domain.ChangePlanSignal
				ch.Receive(ctx, &signal)
				logger.Info("Plan change requested", "newPlan", signal.NewPlanID, "immediate", signal.Immediate)

				if signal.Immediate {
					// Immediate plan change with proration
					handleImmediatePlanChange(ctx, &state, signal.NewPlanID)
				} else {
					// Schedule for end of period
					state.PendingPlanChange = &domain.PlanChange{
						NewPlanID:   signal.NewPlanID,
						EffectiveAt: "end_of_period",
						RequestedAt: workflow.Now(ctx),
					}
				}
			})

			// Handle payment method update
			selector.AddReceive(updatePaymentCh, func(ch workflow.ReceiveChannel, more bool) {
				var signal domain.UpdatePaymentSignal
				ch.Receive(ctx, &signal)
				state.Subscription.PaymentMethodID = signal.PaymentMethodID
				logger.Info("Payment method updated", "newMethod", signal.PaymentMethodID)

				// If past due, retry payment immediately
				if state.Subscription.Status == domain.SubStatusPastDue {
					billingReady = true
				}
			})

			// Handle pause
			selector.AddReceive(pauseCh, func(ch workflow.ReceiveChannel, more bool) {
				var signal domain.PauseSignal
				ch.Receive(ctx, &signal)
				state.Subscription.Status = domain.SubStatusPaused
				resumeAt := workflow.Now(ctx).Add(signal.ResumeAfter)
				state.PauseResumeDate = &resumeAt
				paused = true
				logger.Info("Subscription paused", "resumeAt", resumeAt)
			})

			// Handle cancel
			selector.AddReceive(cancelCh, func(ch workflow.ReceiveChannel, more bool) {
				var signal domain.CancelSignal
				ch.Receive(ctx, &signal)
				if signal.AtPeriodEnd {
					state.Subscription.CancelAtPeriodEnd = true
					logger.Info("Will cancel at period end")
				} else {
					cancelled = true
					state.Subscription.Status = domain.SubStatusCanceled
					now := workflow.Now(ctx)
					state.Subscription.CanceledAt = &now
				}
			})

			// Collect usage events
			selector.AddReceive(workflow.GetSignalChannel(ctx, SignalUsageEvent), func(ch workflow.ReceiveChannel, more bool) {
				var event domain.UsageEvent
				ch.Receive(ctx, &event)
				if state.UsageThisPeriod == nil {
					state.UsageThisPeriod = make(map[string]int64)
				}
				state.UsageThisPeriod[event.Metric] += event.Quantity
			})

			selector.Select(ctx)
		}

		if cancelled {
			// Immediate cancellation
			return finalizeSubscription(ctx, &state, "cancelled_immediately")
		}

		if paused {
			// Wait for resume or auto-resume timer
			return handlePausedState(ctx, &state)
		}

		if billingReady {
			// ─────────────────────────────────────────────────────────────────
			// BILLING CYCLE: Run as child workflow
			// ─────────────────────────────────────────────────────────────────
			billingChildOpts := workflow.ChildWorkflowOptions{
				WorkflowID:         fmt.Sprintf("billing-cycle-%s-%d", state.Subscription.ID, state.BillingCycle),
				TaskQueue:          "billing-cycle-tq",
				WorkflowRunTimeout: 30 * time.Minute,
				RetryPolicy: &temporal.RetryPolicy{
					MaximumAttempts: 1, // Don't auto-retry billing - use dunning
				},
			}
			billingChildCtx := workflow.WithChildOptions(ctx, billingChildOpts)

			var billingResult domain.BillingCycleResult
			err := workflow.ExecuteChildWorkflow(billingChildCtx, BillingCycleWorkflow, domain.BillingCycleInput{
				Subscription:    state.Subscription,
				Plan:            state.CurrentPlan,
				Usage:           state.UsageThisPeriod,
				BillingCycle:    state.BillingCycle,
			}).Get(ctx, &billingResult)

			if err != nil || !billingResult.PaymentSuccessful {
				// Payment failed - enter dunning
				logger.Warn("Payment failed, entering dunning",
					"cycle", state.BillingCycle,
					"error", err,
				)
				state.Subscription.Status = domain.SubStatusPastDue
				state.FailedAttempts++

				// Launch dunning workflow
				dunningResult := handleDunning(ctx, &state)
				if !dunningResult.Recovered {
					// Dunning exhausted - cancel subscription
					state.Subscription.Status = domain.SubStatusCanceled
					now := workflow.Now(ctx)
					state.Subscription.CanceledAt = &now
					return finalizeSubscription(ctx, &state, "dunning_exhausted")
				}
				// Payment recovered during dunning
				state.Subscription.Status = domain.SubStatusActive
				state.FailedAttempts = 0
			} else {
				// Payment successful
				state.LastInvoiceID = billingResult.InvoiceID
				now := workflow.Now(ctx)
				state.LastPaymentAt = &now
				state.TotalRevenue += billingResult.AmountCharged
				state.FailedAttempts = 0
			}

			// Apply pending plan change if cancelling at period end
			if state.Subscription.CancelAtPeriodEnd {
				state.Subscription.Status = domain.SubStatusCanceled
				now := workflow.Now(ctx)
				state.Subscription.CanceledAt = &now
				return finalizeSubscription(ctx, &state, "cancelled_at_period_end")
			}

			// Apply pending plan change
			if state.PendingPlanChange != nil {
				logger.Info("Applying pending plan change", "newPlan", state.PendingPlanChange.NewPlanID)
				state.CurrentPlan = loadPlan(state.PendingPlanChange.NewPlanID)
				state.Subscription.PlanID = state.PendingPlanChange.NewPlanID
				state.PendingPlanChange = nil
				_ = workflow.UpsertSearchAttributes(ctx, map[string]interface{}{
					"PlanID": state.Subscription.PlanID,
					"MRR":    state.CurrentPlan.BasePrice,
				})
			}

			// Advance to next period
			state.BillingCycle++
			state.Subscription.CurrentPeriodStart = state.Subscription.CurrentPeriodEnd
			state.Subscription.CurrentPeriodEnd = calculatePeriodEnd(
				state.Subscription.CurrentPeriodStart,
				state.Subscription.BillingInterval,
			)
			state.UsageThisPeriod = make(map[string]int64) // Reset usage
			state.DunningState = nil

			_ = workflow.UpsertSearchAttributes(ctx, map[string]interface{}{
				"Status":       string(state.Subscription.Status),
				"BillingCycle": state.BillingCycle,
			})
		}
	}

	// ─────────────────────────────────────────────────────────────────────────
	// CONTINUE-AS-NEW: Reset history for next billing cycle
	// ─────────────────────────────────────────────────────────────────────────
	if state.Subscription.Status == domain.SubStatusActive {
		logger.Info("Continuing as new for next cycle",
			"cycle", state.BillingCycle,
			"nextBilling", state.Subscription.CurrentPeriodEnd,
		)
		return workflow.NewContinueAsNewError(ctx, SubscriptionLifecycleWorkflow, state)
	}

	return nil
}
```

### Billing Cycle Workflow (Child)

```go
// BillingCycleWorkflow handles a single billing period:
// calculate invoice → charge payment → record revenue → send receipt
func BillingCycleWorkflow(ctx workflow.Context, input domain.BillingCycleInput) (*domain.BillingCycleResult, error) {
	logger := workflow.GetLogger(ctx)
	logger.Info("Processing billing cycle",
		"subID", input.Subscription.ID,
		"cycle", input.BillingCycle,
		"plan", input.Plan.Name,
	)

	actOpts := workflow.ActivityOptions{
		StartToCloseTimeout: 30 * time.Second,
		RetryPolicy: &temporal.RetryPolicy{
			MaximumAttempts:    3,
			InitialInterval:    time.Second,
			BackoffCoefficient: 2.0,
		},
	}
	ctx = workflow.WithActivityOptions(ctx, actOpts)

	// Step 1: Calculate invoice
	var invoice domain.Invoice
	err := workflow.ExecuteActivity(ctx, activities.CalculateInvoice, domain.InvoiceCalculationInput{
		Subscription: input.Subscription,
		Plan:         input.Plan,
		Usage:        input.Usage,
		PeriodStart:  input.Subscription.CurrentPeriodStart,
		PeriodEnd:    input.Subscription.CurrentPeriodEnd,
	}).Get(ctx, &invoice)
	if err != nil {
		return nil, fmt.Errorf("invoice calculation failed: %w", err)
	}

	logger.Info("Invoice calculated",
		"invoiceID", invoice.ID,
		"total", invoice.Total,
		"lineItems", len(invoice.LineItems),
	)

	// Step 2: Apply any credits/discounts
	var adjustedInvoice domain.Invoice
	err = workflow.ExecuteActivity(ctx, activities.ApplyCreditsAndDiscounts, domain.AdjustmentInput{
		Invoice:        invoice,
		CustomerID:     input.Subscription.CustomerID,
		SubscriptionID: input.Subscription.ID,
	}).Get(ctx, &adjustedInvoice)
	if err != nil {
		// Non-critical - proceed with unadjusted invoice
		logger.Warn("Credit adjustment failed, proceeding", "error", err)
		adjustedInvoice = invoice
	}

	// Step 3: Charge payment
	if adjustedInvoice.Total <= 0 {
		// Nothing to charge (credits covered everything)
		logger.Info("Invoice fully covered by credits")
		return &domain.BillingCycleResult{
			InvoiceID:         adjustedInvoice.ID,
			AmountCharged:     0,
			PaymentSuccessful: true,
		}, nil
	}

	chargeOpts := workflow.ActivityOptions{
		StartToCloseTimeout: 30 * time.Second,
		HeartbeatTimeout:    10 * time.Second,
		RetryPolicy: &temporal.RetryPolicy{
			MaximumAttempts: 3,
			InitialInterval: 2 * time.Second,
			NonRetryableErrorTypes: []string{
				"CardDeclinedError",
				"InsufficientFundsError",
				"PaymentMethodExpiredError",
			},
		},
	}
	chargeCtx := workflow.WithActivityOptions(ctx, chargeOpts)

	var chargeResult domain.ChargeResult
	err = workflow.ExecuteActivity(chargeCtx, activities.ChargePaymentMethod, domain.ChargeInput{
		CustomerID:      input.Subscription.CustomerID,
		PaymentMethodID: input.Subscription.PaymentMethodID,
		Amount:          adjustedInvoice.Total,
		Currency:        adjustedInvoice.Currency,
		InvoiceID:       adjustedInvoice.ID,
		Description:     fmt.Sprintf("%s - %s", input.Plan.Name, input.Subscription.BillingInterval),
		IdempotencyKey:  fmt.Sprintf("sub-%s-cycle-%d", input.Subscription.ID, input.BillingCycle),
	}).Get(ctx, &chargeResult)
	if err != nil {
		// Payment failed
		logger.Error("Payment charge failed", "error", err)
		// Mark invoice as open (unpaid)
		_ = workflow.ExecuteActivity(ctx, activities.UpdateInvoiceStatus,
			adjustedInvoice.ID, domain.InvoiceStatusOpen).Get(ctx, nil)
		return &domain.BillingCycleResult{
			InvoiceID:         adjustedInvoice.ID,
			PaymentSuccessful: false,
			FailureReason:     err.Error(),
		}, nil
	}

	// Step 4: Mark invoice as paid
	_ = workflow.ExecuteActivity(ctx, activities.UpdateInvoiceStatus,
		adjustedInvoice.ID, domain.InvoiceStatusPaid).Get(ctx, nil)

	// Step 5: Revenue recognition (ASC 606)
	revenueOpts := workflow.ActivityOptions{
		TaskQueue:           "revenue-recognition-tq",
		StartToCloseTimeout: 15 * time.Second,
		RetryPolicy:         &temporal.RetryPolicy{MaximumAttempts: 5},
	}
	revenueCtx := workflow.WithActivityOptions(ctx, revenueOpts)

	_ = workflow.ExecuteActivity(revenueCtx, activities.RecognizeRevenue, domain.RevenueInput{
		InvoiceID:      adjustedInvoice.ID,
		SubscriptionID: input.Subscription.ID,
		Amount:         chargeResult.AmountCharged,
		Currency:       adjustedInvoice.Currency,
		PeriodStart:    input.Subscription.CurrentPeriodStart,
		PeriodEnd:      input.Subscription.CurrentPeriodEnd,
		PlanID:         input.Plan.ID,
	}).Get(ctx, nil)

	// Step 6: Send receipt
	notifyOpts := workflow.ActivityOptions{
		TaskQueue:           "notification-tq",
		StartToCloseTimeout: 10 * time.Second,
		RetryPolicy:         &temporal.RetryPolicy{MaximumAttempts: 3},
	}
	notifyCtx := workflow.WithActivityOptions(ctx, notifyOpts)

	_ = workflow.ExecuteActivity(notifyCtx, activities.SendInvoiceReceipt, domain.ReceiptInput{
		CustomerID: input.Subscription.CustomerID,
		Invoice:    adjustedInvoice,
		ChargeRef:  chargeResult.Reference,
	}).Get(ctx, nil)

	// Step 7: Update MRR metrics
	_ = workflow.ExecuteActivity(ctx, activities.UpdateMRRMetrics, domain.MRRUpdate{
		SubscriptionID: input.Subscription.ID,
		CustomerID:     input.Subscription.CustomerID,
		Amount:         chargeResult.AmountCharged,
		PlanID:         input.Plan.ID,
		Event:          "renewal",
	}).Get(ctx, nil)

	return &domain.BillingCycleResult{
		InvoiceID:         adjustedInvoice.ID,
		AmountCharged:     chargeResult.AmountCharged,
		PaymentSuccessful: true,
		ChargeReference:   chargeResult.Reference,
	}, nil
}
```

### Dunning Workflow

```go
// DunningWorkflow implements escalating retry logic for failed payments.
// Retry schedule: Day 1, Day 3, Day 5, Day 7, Day 10, Day 14 → Cancel
func handleDunning(ctx workflow.Context, state *domain.SubscriptionState) domain.DunningResult {
	logger := workflow.GetLogger(ctx)

	// Dunning schedule: delays between retry attempts
	dunningSchedule := []struct {
		Delay           time.Duration
		EscalationLevel int
		Action          string
	}{
		{24 * time.Hour, 1, "retry_silent"},           // Day 1: silent retry
		{2 * 24 * time.Hour, 2, "retry_email"},        // Day 3: retry + email
		{2 * 24 * time.Hour, 3, "retry_email_urgent"}, // Day 5: urgent email
		{2 * 24 * time.Hour, 4, "retry_sms"},          // Day 7: SMS + email
		{3 * 24 * time.Hour, 5, "retry_final"},        // Day 10: final notice
		{4 * 24 * time.Hour, 6, "cancel"},             // Day 14: cancel
	}

	if state.DunningState == nil {
		state.DunningState = &domain.DunningState{
			Attempts: 0,
		}
	}

	notifyOpts := workflow.ActivityOptions{
		TaskQueue:           "notification-tq",
		StartToCloseTimeout: 10 * time.Second,
		RetryPolicy:         &temporal.RetryPolicy{MaximumAttempts: 3},
	}
	notifyCtx := workflow.WithActivityOptions(ctx, notifyOpts)

	chargeOpts := workflow.ActivityOptions{
		TaskQueue:           "billing-cycle-tq",
		StartToCloseTimeout: 30 * time.Second,
		RetryPolicy: &temporal.RetryPolicy{
			MaximumAttempts: 2,
			NonRetryableErrorTypes: []string{
				"CardDeclinedError",
				"InsufficientFundsError",
				"PaymentMethodExpiredError",
			},
		},
	}
	chargeCtx := workflow.WithActivityOptions(ctx, chargeOpts)

	updatePaymentCh := workflow.GetSignalChannel(ctx, SignalUpdatePayment)

	for i := state.DunningState.Attempts; i < len(dunningSchedule); i++ {
		step := dunningSchedule[i]
		state.DunningState.Attempts = i + 1
		state.DunningState.EscalationLevel = step.EscalationLevel

		logger.Info("Dunning step",
			"attempt", i+1,
			"level", step.EscalationLevel,
			"action", step.Action,
		)

		// Wait for the delay (or payment method update signal)
		waitTimer := workflow.NewTimer(ctx, step.Delay)
		paymentUpdated := false

		selector := workflow.NewSelector(ctx)
		selector.AddFuture(waitTimer, func(f workflow.Future) {})
		selector.AddReceive(updatePaymentCh, func(ch workflow.ReceiveChannel, more bool) {
			var signal domain.UpdatePaymentSignal
			ch.Receive(ctx, &signal)
			state.Subscription.PaymentMethodID = signal.PaymentMethodID
			paymentUpdated = true
		})
		selector.Select(ctx)

		// Send notification based on escalation level
		switch step.Action {
		case "retry_email":
			_ = workflow.ExecuteActivity(notifyCtx, activities.SendDunningEmail, domain.DunningNotification{
				CustomerID: state.Subscription.CustomerID,
				Level:      step.EscalationLevel,
				InvoiceID:  state.LastInvoiceID,
				Amount:     state.CurrentPlan.BasePrice,
			}).Get(ctx, nil)
		case "retry_email_urgent":
			_ = workflow.ExecuteActivity(notifyCtx, activities.SendDunningEmailUrgent, domain.DunningNotification{
				CustomerID: state.Subscription.CustomerID,
				Level:      step.EscalationLevel,
				InvoiceID:  state.LastInvoiceID,
				Amount:     state.CurrentPlan.BasePrice,
			}).Get(ctx, nil)
		case "retry_sms":
			_ = workflow.ExecuteActivity(notifyCtx, activities.SendDunningSMS, domain.DunningNotification{
				CustomerID: state.Subscription.CustomerID,
				Level:      step.EscalationLevel,
			}).Get(ctx, nil)
		case "retry_final":
			_ = workflow.ExecuteActivity(notifyCtx, activities.SendFinalNotice, domain.DunningNotification{
				CustomerID: state.Subscription.CustomerID,
				Level:      step.EscalationLevel,
				InvoiceID:  state.LastInvoiceID,
			}).Get(ctx, nil)
		case "cancel":
			// All retries exhausted
			return domain.DunningResult{Recovered: false, Attempts: i + 1}
		}

		// Attempt charge
		var chargeResult domain.ChargeResult
		err := workflow.ExecuteActivity(chargeCtx, activities.ChargePaymentMethod, domain.ChargeInput{
			CustomerID:      state.Subscription.CustomerID,
			PaymentMethodID: state.Subscription.PaymentMethodID,
			Amount:          state.CurrentPlan.BasePrice,
			Currency:        state.Subscription.Currency,
			InvoiceID:       state.LastInvoiceID,
			IdempotencyKey:  fmt.Sprintf("dunning-%s-%d", state.Subscription.ID, i),
		}).Get(ctx, &chargeResult)

		if err == nil {
			// Payment succeeded!
			logger.Info("Dunning recovered payment", "attempt", i+1)
			_ = workflow.ExecuteActivity(notifyCtx, activities.SendPaymentRecoveredEmail, domain.RecoveryNotification{
				CustomerID: state.Subscription.CustomerID,
				Amount:     state.CurrentPlan.BasePrice,
			}).Get(ctx, nil)
			return domain.DunningResult{
				Recovered:      true,
				Attempts:       i + 1,
				ChargeRef:      chargeResult.Reference,
				RecoveredAt:    workflow.Now(ctx),
			}
		}

		logger.Warn("Dunning charge failed", "attempt", i+1, "error", err)
	}

	return domain.DunningResult{Recovered: false, Attempts: len(dunningSchedule)}
}
```

### Paused State Handling

```go
func handlePausedState(ctx workflow.Context, state *domain.SubscriptionState) error {
	logger := workflow.GetLogger(ctx)

	resumeCh := workflow.GetSignalChannel(ctx, SignalResumeSubscription)
	cancelCh := workflow.GetSignalChannel(ctx, SignalCancelSubscription)

	// Auto-resume timer
	var autoResumeTimer workflow.Future
	if state.PauseResumeDate != nil {
		remaining := state.PauseResumeDate.Sub(workflow.Now(ctx))
		if remaining > 0 {
			autoResumeTimer = workflow.NewTimer(ctx, remaining)
		}
	}
	if autoResumeTimer == nil {
		// Default: auto-resume after 90 days max
		autoResumeTimer = workflow.NewTimer(ctx, 90*24*time.Hour)
	}

	selector := workflow.NewSelector(ctx)
	resumed := false

	selector.AddReceive(resumeCh, func(ch workflow.ReceiveChannel, more bool) {
		ch.Receive(ctx, nil)
		resumed = true
	})
	selector.AddFuture(autoResumeTimer, func(f workflow.Future) {
		resumed = true
		logger.Info("Auto-resuming subscription after pause period")
	})
	selector.AddReceive(cancelCh, func(ch workflow.ReceiveChannel, more bool) {
		var signal domain.CancelSignal
		ch.Receive(ctx, &signal)
		state.Subscription.Status = domain.SubStatusCanceled
		now := workflow.Now(ctx)
		state.Subscription.CanceledAt = &now
	})

	selector.Select(ctx)

	if !resumed {
		return finalizeSubscription(ctx, state, "cancelled_while_paused")
	}

	// Resume: reset period and continue
	state.Subscription.Status = domain.SubStatusActive
	state.Subscription.CurrentPeriodStart = workflow.Now(ctx)
	state.Subscription.CurrentPeriodEnd = calculatePeriodEnd(
		workflow.Now(ctx), state.Subscription.BillingInterval,
	)
	state.PauseResumeDate = nil

	_ = workflow.UpsertSearchAttributes(ctx, map[string]interface{}{
		"Status": string(state.Subscription.Status),
	})

	return workflow.NewContinueAsNewError(ctx, SubscriptionLifecycleWorkflow, *state)
}
```

### Immediate Plan Change with Proration

```go
func handleImmediatePlanChange(ctx workflow.Context, state *domain.SubscriptionState, newPlanID string) {
	logger := workflow.GetLogger(ctx)
	newPlan := loadPlan(newPlanID)
	oldPlan := state.CurrentPlan
	now := workflow.Now(ctx)

	// Calculate proration
	periodTotal := state.Subscription.CurrentPeriodEnd.Sub(state.Subscription.CurrentPeriodStart)
	periodUsed := now.Sub(state.Subscription.CurrentPeriodStart)
	periodRemaining := state.Subscription.CurrentPeriodEnd.Sub(now)

	usedFraction := float64(periodUsed) / float64(periodTotal)
	remainingFraction := float64(periodRemaining) / float64(periodTotal)

	// Credit for unused portion of old plan
	oldPlanCredit := int64(float64(oldPlan.BasePrice) * remainingFraction)
	// Charge for remaining portion of new plan
	newPlanCharge := int64(float64(newPlan.BasePrice) * remainingFraction)

	prorationAmount := newPlanCharge - oldPlanCredit

	logger.Info("Plan change proration",
		"oldPlan", oldPlan.ID,
		"newPlan", newPlan.ID,
		"credit", oldPlanCredit,
		"charge", newPlanCharge,
		"netAmount", prorationAmount,
		"usedFraction", usedFraction,
	)

	actOpts := workflow.ActivityOptions{
		StartToCloseTimeout: 30 * time.Second,
		RetryPolicy:         &temporal.RetryPolicy{MaximumAttempts: 3},
	}
	actCtx := workflow.WithActivityOptions(ctx, actOpts)

	if prorationAmount > 0 {
		// Charge the difference (upgrade)
		_ = workflow.ExecuteActivity(actCtx, activities.ChargeProration, domain.ProrationCharge{
			SubscriptionID: state.Subscription.ID,
			CustomerID:     state.Subscription.CustomerID,
			Amount:         prorationAmount,
			Currency:       state.Subscription.Currency,
			OldPlanID:      oldPlan.ID,
			NewPlanID:      newPlan.ID,
			IdempotencyKey: fmt.Sprintf("proration-%s-%d-%s", state.Subscription.ID, state.BillingCycle, newPlanID),
		}).Get(ctx, nil)
	} else if prorationAmount < 0 {
		// Issue credit (downgrade)
		_ = workflow.ExecuteActivity(actCtx, activities.IssueCredit, domain.CreditIssue{
			SubscriptionID: state.Subscription.ID,
			CustomerID:     state.Subscription.CustomerID,
			Amount:         -prorationAmount,
			Currency:       state.Subscription.Currency,
			Reason:         fmt.Sprintf("proration: %s → %s", oldPlan.ID, newPlan.ID),
		}).Get(ctx, nil)
	}

	// Apply plan change
	state.CurrentPlan = newPlan
	state.Subscription.PlanID = newPlanID
	state.PendingPlanChange = nil
}
```

### Activities

```go
package activities

import (
	"context"
	"fmt"
	"time"

	"go.temporal.io/sdk/activity"
)

type BillingActivities struct {
	paymentGateway PaymentGateway
	invoiceDB      InvoiceRepository
	subscriptionDB SubscriptionRepository
	usageDB        UsageRepository
	revenueDB      RevenueRepository
	notificationSvc NotificationService
	metricsClient  MetricsClient
}

// CalculateInvoice generates an invoice with line items for the billing period
func (a *BillingActivities) CalculateInvoice(ctx context.Context, input domain.InvoiceCalculationInput) (*domain.Invoice, error) {
	logger := activity.GetLogger(ctx)

	invoice := &domain.Invoice{
		ID:             generateInvoiceID(),
		SubscriptionID: input.Subscription.ID,
		CustomerID:     input.Subscription.CustomerID,
		PeriodStart:    input.PeriodStart,
		PeriodEnd:      input.PeriodEnd,
		Currency:       input.Subscription.Currency,
		Status:         domain.InvoiceStatusDraft,
	}

	// Base plan charge
	invoice.LineItems = append(invoice.LineItems, domain.LineItem{
		Description: fmt.Sprintf("%s (%s)", input.Plan.Name, input.Subscription.BillingInterval),
		Quantity:    1,
		UnitPrice:   input.Plan.BasePrice,
		Amount:      input.Plan.BasePrice,
		Type:        "base",
	})

	// Usage-based charges
	for _, tier := range input.Plan.UsageTiers {
		usage, exists := input.Usage[tier.Metric]
		if !exists || usage <= 0 {
			continue
		}

		// Calculate tiered pricing
		var chargeableUnits int64
		if tier.UpTo > 0 && usage > tier.UpTo {
			chargeableUnits = tier.UpTo
		} else {
			chargeableUnits = usage
		}

		amount := chargeableUnits * tier.UnitPrice
		invoice.LineItems = append(invoice.LineItems, domain.LineItem{
			Description: fmt.Sprintf("Usage: %s (%d units)", tier.Metric, chargeableUnits),
			Quantity:    chargeableUnits,
			UnitPrice:   tier.UnitPrice,
			Amount:      amount,
			Type:        "usage",
		})
	}

	// Calculate totals
	var subtotal int64
	for _, item := range invoice.LineItems {
		subtotal += item.Amount
	}
	invoice.Subtotal = subtotal

	// Tax calculation
	taxRate := getTaxRate(input.Subscription.Region)
	invoice.Tax = int64(float64(subtotal) * taxRate)
	invoice.Total = subtotal + invoice.Tax

	// Persist invoice
	err := a.invoiceDB.Create(ctx, invoice)
	if err != nil {
		return nil, fmt.Errorf("failed to persist invoice: %w", err)
	}

	logger.Info("Invoice calculated",
		"invoiceID", invoice.ID,
		"subtotal", invoice.Subtotal,
		"tax", invoice.Tax,
		"total", invoice.Total,
	)

	return invoice, nil
}

// ChargePaymentMethod charges the customer's stored payment method
func (a *BillingActivities) ChargePaymentMethod(ctx context.Context, input domain.ChargeInput) (*domain.ChargeResult, error) {
	logger := activity.GetLogger(ctx)
	info := activity.GetInfo(ctx)

	logger.Info("Charging payment method",
		"customer", input.CustomerID,
		"amount", input.Amount,
		"currency", input.Currency,
		"attempt", info.Attempt,
	)

	activity.RecordHeartbeat(ctx, fmt.Sprintf("charging %d %s", input.Amount, input.Currency))

	result, err := a.paymentGateway.Charge(ctx, ChargeRequest{
		CustomerID:      input.CustomerID,
		PaymentMethodID: input.PaymentMethodID,
		AmountCents:     input.Amount,
		Currency:        input.Currency,
		Description:     input.Description,
		InvoiceID:       input.InvoiceID,
		IdempotencyKey:  input.IdempotencyKey,
		Metadata: map[string]string{
			"subscription_id": input.InvoiceID,
		},
	})
	if err != nil {
		a.metricsClient.RecordCounter("billing_charge_failed", 1,
			"reason", classifyPaymentError(err),
		)
		return nil, classifyAndWrapError(err)
	}

	a.metricsClient.RecordCounter("billing_charge_success", 1,
		"currency", input.Currency,
	)
	a.metricsClient.RecordHistogram("billing_charge_amount", float64(input.Amount),
		"currency", input.Currency,
	)

	return &domain.ChargeResult{
		Reference:     result.ChargeID,
		AmountCharged: input.Amount,
		ProcessedAt:   time.Now(),
	}, nil
}

// RecognizeRevenue records revenue per ASC 606 requirements
func (a *BillingActivities) RecognizeRevenue(ctx context.Context, input domain.RevenueInput) error {
	// ASC 606: Revenue recognized over the service period
	// For subscription: recognize ratably over the billing period
	periodDays := int(input.PeriodEnd.Sub(input.PeriodStart).Hours() / 24)
	dailyRevenue := input.Amount / int64(periodDays)

	entries := make([]RevenueEntry, periodDays)
	for i := 0; i < periodDays; i++ {
		date := input.PeriodStart.AddDate(0, 0, i)
		amount := dailyRevenue
		if i == periodDays-1 {
			// Last day gets remainder to avoid rounding issues
			amount = input.Amount - (dailyRevenue * int64(periodDays-1))
		}
		entries[i] = RevenueEntry{
			Date:           date,
			Amount:         amount,
			Currency:       input.Currency,
			SubscriptionID: input.SubscriptionID,
			InvoiceID:      input.InvoiceID,
			PlanID:         input.PlanID,
			Type:           "subscription_revenue",
		}
	}

	return a.revenueDB.BatchInsert(ctx, entries)
}

// SendDunningEmail sends payment failure notification
func (a *BillingActivities) SendDunningEmail(ctx context.Context, notif domain.DunningNotification) error {
	template := selectDunningTemplate(notif.Level)
	return a.notificationSvc.SendEmail(ctx, EmailRequest{
		CustomerID: notif.CustomerID,
		Template:   template,
		Data: map[string]interface{}{
			"invoice_id": notif.InvoiceID,
			"amount":     notif.Amount,
			"update_url": fmt.Sprintf("https://app.example.com/billing/update-payment?sub=%s", notif.InvoiceID),
		},
	})
}

// UpdateMRRMetrics records MRR changes for business analytics
func (a *BillingActivities) UpdateMRRMetrics(ctx context.Context, update domain.MRRUpdate) error {
	return a.metricsClient.RecordMRREvent(ctx, MRREvent{
		SubscriptionID: update.SubscriptionID,
		CustomerID:     update.CustomerID,
		Amount:         update.Amount,
		PlanID:         update.PlanID,
		EventType:      update.Event, // "new", "renewal", "upgrade", "downgrade", "churn"
		Timestamp:      time.Now(),
	})
}
```

### Finalization

```go
func finalizeSubscription(ctx workflow.Context, state *domain.SubscriptionState, reason string) error {
	logger := workflow.GetLogger(ctx)
	logger.Info("Finalizing subscription",
		"subID", state.Subscription.ID,
		"reason", reason,
		"totalRevenue", state.TotalRevenue,
		"cycles", state.BillingCycle,
	)

	actOpts := workflow.ActivityOptions{
		StartToCloseTimeout: 15 * time.Second,
		RetryPolicy:         &temporal.RetryPolicy{MaximumAttempts: 5},
	}
	actCtx := workflow.WithActivityOptions(ctx, actOpts)

	// Record cancellation
	_ = workflow.ExecuteActivity(actCtx, activities.RecordCancellation, domain.CancellationRecord{
		SubscriptionID: state.Subscription.ID,
		CustomerID:     state.Subscription.CustomerID,
		Reason:         reason,
		TotalRevenue:   state.TotalRevenue,
		BillingCycles:  state.BillingCycle,
		FinalStatus:    string(state.Subscription.Status),
	}).Get(ctx, nil)

	// Send cancellation confirmation
	_ = workflow.ExecuteActivity(
		workflow.WithActivityOptions(ctx, workflow.ActivityOptions{
			TaskQueue:           "notification-tq",
			StartToCloseTimeout: 10 * time.Second,
		}),
		activities.SendCancellationEmail, domain.CancellationNotification{
			CustomerID:     state.Subscription.CustomerID,
			SubscriptionID: state.Subscription.ID,
			Reason:         reason,
			EffectiveDate:  workflow.Now(ctx),
		},
	).Get(ctx, nil)

	// Update search attributes
	_ = workflow.UpsertSearchAttributes(ctx, map[string]interface{}{
		"Status": string(state.Subscription.Status),
	})

	// Record churn in MRR
	_ = workflow.ExecuteActivity(actCtx, activities.UpdateMRRMetrics, domain.MRRUpdate{
		SubscriptionID: state.Subscription.ID,
		CustomerID:     state.Subscription.CustomerID,
		Amount:         -state.CurrentPlan.BasePrice,
		PlanID:         state.CurrentPlan.ID,
		Event:          "churn",
	}).Get(ctx, nil)

	return nil
}

func calculatePeriodEnd(start time.Time, interval domain.BillingInterval) time.Time {
	switch interval {
	case domain.IntervalMonthly:
		return start.AddDate(0, 1, 0)
	case domain.IntervalQuarterly:
		return start.AddDate(0, 3, 0)
	case domain.IntervalAnnual:
		return start.AddDate(1, 0, 0)
	default:
		return start.AddDate(0, 1, 0)
	}
}

func loadPlan(planID string) domain.Plan {
	// In production: load from plan service/database
	// Plans are loaded at activity level, not workflow level
	return domain.Plan{ID: planID}
}
```

---

## Advanced Patterns

### Pattern 1: Usage Aggregation with Periodic Snapshots

```go
// Usage events arrive via Kafka → aggregated → signaled to subscription workflow
// This prevents overwhelming the workflow with individual events

// UsageAggregatorWorkflow runs per customer, batches usage, signals subscription
func UsageAggregatorWorkflow(ctx workflow.Context, customerID string) error {
	usageCh := workflow.GetSignalChannel(ctx, "raw-usage")
	buffer := make(map[string]int64) // metric → accumulated count

	flushInterval := 5 * time.Minute
	flushTimer := workflow.NewTimer(ctx, flushInterval)

	for {
		selector := workflow.NewSelector(ctx)

		// Collect usage events
		selector.AddReceive(usageCh, func(ch workflow.ReceiveChannel, more bool) {
			var event domain.UsageEvent
			ch.Receive(ctx, &event)
			buffer[event.Metric] += event.Quantity
		})

		// Periodic flush to subscription workflow
		selector.AddFuture(flushTimer, func(f workflow.Future) {
			if len(buffer) > 0 {
				// Signal the subscription workflow with aggregated usage
				subWorkflowID := fmt.Sprintf("sub-%s", customerID)
				for metric, qty := range buffer {
					_ = workflow.SignalExternalWorkflow(ctx, subWorkflowID, "", SignalUsageEvent,
						domain.UsageEvent{Metric: metric, Quantity: qty},
					).Get(ctx, nil)
				}
				buffer = make(map[string]int64)
			}
			flushTimer = workflow.NewTimer(ctx, flushInterval)
		})

		selector.Select(ctx)

		// Continue-as-new periodically
		info := workflow.GetInfo(ctx)
		if info.GetCurrentHistoryLength() > 2000 {
			return workflow.NewContinueAsNewError(ctx, UsageAggregatorWorkflow, customerID)
		}
	}
}
```

### Pattern 2: Cohort-Based Billing (Thundering Herd Prevention)

```go
// Instead of billing all customers at once, distribute across the month.
// Use Temporal Schedules to trigger batch billing for each cohort.

func createBillingSchedules(c client.Client) error {
	// 31 cohorts (one per day of month)
	for day := 1; day <= 31; day++ {
		_, err := c.ScheduleClient().Create(context.Background(), client.ScheduleOptions{
			ID: fmt.Sprintf("billing-cohort-day-%02d", day),
			Spec: client.ScheduleSpec{
				// Run at 2 AM UTC on the specific day of each month
				Calendars: []client.ScheduleCalendarSpec{{
					DayOfMonth: []client.ScheduleRange{{Start: day, End: day}},
					Hour:       []client.ScheduleRange{{Start: 2, End: 2}},
					Minute:     []client.ScheduleRange{{Start: 0, End: 0}},
				}},
			},
			Action: &client.ScheduleWorkflowAction{
				ID:        fmt.Sprintf("batch-billing-day-%02d", day),
				Workflow:  BatchBillingWorkflow,
				TaskQueue: "billing-cycle-tq",
				Args:      []interface{}{day},
			},
			Overlap: enums.SCHEDULE_OVERLAP_POLICY_SKIP,
		})
		if err != nil {
			return fmt.Errorf("failed to create schedule for day %d: %w", day, err)
		}
	}
	return nil
}

// BatchBillingWorkflow processes all subscriptions in a cohort
func BatchBillingWorkflow(ctx workflow.Context, cohortDay int) error {
	logger := workflow.GetLogger(ctx)

	actOpts := workflow.ActivityOptions{
		StartToCloseTimeout: 5 * time.Minute,
		HeartbeatTimeout:    30 * time.Second,
	}
	ctx = workflow.WithActivityOptions(ctx, actOpts)

	// Get all subscriptions due today
	var subscriptions []string
	err := workflow.ExecuteActivity(ctx, activities.GetSubscriptionsDueOnDay, cohortDay).Get(ctx, &subscriptions)
	if err != nil {
		return err
	}

	logger.Info("Batch billing starting",
		"cohortDay", cohortDay,
		"count", len(subscriptions),
	)

	// Signal each subscription workflow to trigger billing
	// Rate limit: 100 signals per second to avoid overwhelming Temporal
	batchSize := 100
	for i := 0; i < len(subscriptions); i += batchSize {
		end := i + batchSize
		if end > len(subscriptions) {
			end = len(subscriptions)
		}
		batch := subscriptions[i:end]

		for _, subID := range batch {
			workflowID := fmt.Sprintf("subscription-%s", subID)
			_ = workflow.SignalExternalWorkflow(ctx, workflowID, "", "billing-trigger", nil).Get(ctx, nil)
		}

		// Rate limit between batches
		_ = workflow.Sleep(ctx, time.Second)
	}

	logger.Info("Batch billing complete", "processed", len(subscriptions))
	return nil
}
```

### Pattern 3: Trial-to-Paid Conversion with Reminder Sequence

```go
// During trial, send timed reminders to encourage conversion
func trialReminderSequence(ctx workflow.Context, state *domain.SubscriptionState) {
	if state.Subscription.TrialEnd == nil {
		return
	}

	trialDays := int(state.Subscription.TrialEnd.Sub(state.Subscription.CreatedAt).Hours() / 24)

	notifyCtx := workflow.WithActivityOptions(ctx, workflow.ActivityOptions{
		TaskQueue:           "notification-tq",
		StartToCloseTimeout: 10 * time.Second,
		RetryPolicy:         &temporal.RetryPolicy{MaximumAttempts: 3},
	})

	// Send reminders at specific points in the trial
	reminders := []struct {
		DaysBeforeEnd int
		Template      string
	}{
		{7, "trial_7_days_left"},
		{3, "trial_3_days_left"},
		{1, "trial_last_day"},
	}

	for _, reminder := range reminders {
		sendAt := state.Subscription.TrialEnd.AddDate(0, 0, -reminder.DaysBeforeEnd)
		waitDuration := sendAt.Sub(workflow.Now(ctx))
		if waitDuration <= 0 {
			continue
		}

		_ = workflow.Sleep(ctx, waitDuration)

		// Check if still in trial (might have converted or cancelled)
		if state.Subscription.Status != domain.SubStatusTrialing {
			return
		}

		_ = workflow.ExecuteActivity(notifyCtx, activities.SendTrialReminder, domain.TrialReminder{
			CustomerID:     state.Subscription.CustomerID,
			SubscriptionID: state.Subscription.ID,
			Template:       reminder.Template,
			DaysRemaining:  reminder.DaysBeforeEnd,
		}).Get(ctx, nil)
	}
}
```

---

## Failure Scenarios

### Scenario 1: Payment Gateway Outage During Billing Window

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Context: It's the 1st of the month. 2M subscriptions in this cohort.
         Stripe goes down at 2:00 AM during batch billing.

t=2:00 AM │ BatchBillingWorkflow triggers 2M subscription signals
t=2:01    │ Subscription workflows wake up, start BillingCycleWorkflow children
t=2:02    │ ChargePaymentMethod activities start hitting Stripe
t=2:02    │ Stripe returns 503 for all requests
t=2:02    │ Activities retry (attempt 1→2→3) with backoff
t=2:05    │ After 3 attempts, activities fail with transient error
t=2:05    │ BillingCycleWorkflow returns PaymentSuccessful=false
t=2:05    │ Parent enters dunning state (status=PAST_DUE)
          │
          │ Dunning schedule: first retry in 24 hours
          │
t=Next day│ Stripe is back up
t=2:00+24h│ Dunning attempts retry silently
t=2:01    │ Charges succeed for 99.5% of subscriptions
t=2:01    │ Status returns to ACTIVE, dunning cleared
          │
          │ For 0.5% that still fail (actual card issues):
          │ Dunning continues through escalation steps...
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

KEY: Gateway outage ≠ lost revenue. Dunning recovers automatically.
     No manual intervention needed for transient outages.
     Customer impact: brief PAST_DUE status, no service interruption.
```

### Scenario 2: Plan Change During Active Billing Cycle

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Customer on $49/mo plan, 15 days into cycle.
Upgrades to $99/mo immediately.

t=0  │ Signal: ChangePlan{NewPlanID: "pro-99", Immediate: true}
t=0  │ Workflow receives signal, calls handleImmediatePlanChange()
     │
     │ PRORATION CALCULATION:
     │ - Period: 30 days, Used: 15 days, Remaining: 15 days
     │ - Credit for unused Basic: $49 × (15/30) = $24.50
     │ - Charge for remaining Pro: $99 × (15/30) = $49.50
     │ - Net charge: $49.50 - $24.50 = $25.00
     │
t=1  │ ChargeProration activity: charges $25.00
t=2  │ Plan updated in state: currentPlan = "pro-99"
t=2  │ Search attributes updated: MRR = $99
     │
     │ At next billing cycle (15 days later):
     │ Full $99 charge for new period
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### Scenario 3: Subscription Workflow Running for 3+ Years

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Subscription created: Jan 2022
Monthly billing
Now: July 2025 (42 billing cycles)

WITHOUT continue-as-new:
  - 42 billing cycles × ~50 events per cycle = 2,100+ events
  - Approaching 50,000 event limit
  - Replay gets slower with each cycle

WITH continue-as-new (our approach):
  - Each billing cycle: ~50 events
  - Continue-as-new resets after each cycle
  - History always stays at ~50 events
  - Replay takes <10ms regardless of subscription age

  Cycle 1: Start → Bill → CAN(state)
  Cycle 2: Start → Bill → CAN(state)
  ...
  Cycle 42: Start → Bill → CAN(state)  ← current execution

  State carries forward: totalRevenue, billingCycle=42, all settings
  History does NOT carry forward: stays small and fast
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## Production Configuration for 100M Subscriptions

### Namespace Isolation

```
billing-prod-us      → US customers (40M subs)
billing-prod-eu      → EU customers (30M subs)
billing-prod-apac    → APAC customers (20M subs)
billing-prod-latam   → LATAM customers (10M subs)

Benefits:
- Failure isolation (EU outage doesn't affect US)
- Compliance (EU data stays in EU)
- Independent scaling per region
- Regional maintenance windows
```

### Worker Fleet Sizing

```
Per-region (US - 40M subscriptions):

Subscription Lifecycle Workers:
  - 40M workflows, mostly sleeping (waiting for next billing)
  - Peak: cohort billing day → 1.3M workflows active simultaneously
  - Required: 30 pods (8 CPU, 16GB each)
  - MaxConcurrentWorkflowTaskExecution: 500 per pod
  - Effective capacity: 15,000 concurrent workflow tasks

Billing Cycle Workers:
  - 1.3M billing cycle child workflows during peak
  - Each runs for 30-60 seconds
  - Required: 20 pods (4 CPU, 8GB each)
  - MaxConcurrentActivityExecution: 100 per pod

Dunning Workers:
  - ~1% of subscriptions enter dunning = 400K
  - Spread over 14-day dunning period
  - Required: 10 pods (4 CPU, 8GB each)

Usage Aggregation Workers:
  - Receives high-volume usage signals
  - Required: 15 pods (4 CPU, 8GB each)
```

### Database Partition Strategy

```
Temporal Persistence (Cassandra):
  - 4096 history shards
  - 40M workflows distributed across shards
  - ~10K workflows per shard
  - 6 Cassandra nodes (16 CPU, 64GB, NVMe SSD)
  - Replication factor: 3

Visibility (Elasticsearch):
  - Index per namespace + monthly rollover
  - billing-prod-us-2025-01, billing-prod-us-2025-02, ...
  - 3 data nodes (8 CPU, 32GB, SSD)
  - Custom search attributes indexed:
    SubscriptionID, CustomerID, PlanID, Status, Region, MRR, BillingCycle
```

### Batch Scheduling (Thundering Herd Prevention)

```
Strategy: Distribute 40M US subscriptions across 31 daily cohorts

Cohort assignment: hash(customerID) % 31 + 1 = billing day

  Day 1:  ~1.29M subscriptions
  Day 2:  ~1.29M subscriptions
  ...
  Day 31: ~1.29M subscriptions

Peak billing rate: 1.29M / (billing window of 4 hours) = 90 workflows/second

Schedule Configuration:
  - 31 Temporal Schedules, one per cohort day
  - Run at 2 AM UTC in respective region timezone
  - Overlap policy: SKIP (if yesterday's billing overran)
  - Rate limit signals: 500/second to Temporal frontend

This prevents:
  ✗ 40M workflows all billing at once → overwhelms payment gateway
  ✓ Smooth 90/second rate that payment gateway handles easily
```

### Monitoring & Metrics

```
Key Billing Metrics:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MRR (Monthly Recurring Revenue):      $XXM ± 0.1%
Billing success rate:                  > 98.5% first attempt
Dunning recovery rate:                 > 60% (industry: 40-50%)
Involuntary churn rate:                < 2% monthly
Average dunning resolution time:       4.3 days
Revenue recognition accuracy:          99.99%
Invoice generation latency (p99):      < 5s
Payment processing latency (p99):      < 10s
Continue-as-new frequency:             Once per billing cycle

Alerts:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
billing_success_rate < 95%          → CRITICAL (payment gateway issue)
dunning_recovery_rate < 40%         → WARNING (payment method issues)
schedule_to_start_latency > 5s      → CRITICAL (worker starvation)
batch_billing_completion_time > 6h   → WARNING (capacity issue)
involuntary_churn_rate > 3%         → CRITICAL (systemic failure)
```
