# Problem 1: Payment Processing & Money Transfer System

## The Problem

Design and implement a production payment processing system handling:
- **50M+ daily transactions** (~580 TPS average, 2000+ TPS peak)
- **Exactly-once money movement** across banks and payment processors
- **Failure resilience** at every point without losing or duplicating money
- **Regulatory compliance** (PCI-DSS, SOX, AML/KYC)
- **Multi-currency** with real-time FX rate locking
- **Sub-second p99 latency** for domestic transfers
- **Complete audit trail** for every cent moved

## Architecture

```
┌────────────────────────────────────────────────────────────────────────────────┐
│                      PAYMENT PROCESSING ARCHITECTURE                            │
├────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ┌─────────────┐     ┌──────────────────────────────────────────────────────┐  │
│  │  API Gateway │────►│              TEMPORAL CLUSTER                         │  │
│  │  (gRPC/REST) │     │                                                      │  │
│  │              │     │  Namespace: payments-prod                             │  │
│  │  - Auth      │     │  ┌───────────────────────────────────────────────┐   │  │
│  │  - Rate Limit│     │  │  Task Queues:                                 │   │  │
│  │  - Idempotent│     │  │                                               │   │  │
│  │    Key Check │     │  │  payment-priority-tq (VIP/large transfers)    │   │  │
│  └─────────────┘     │  │  payment-standard-tq (normal transfers)       │   │  │
│                       │  │  payment-batch-tq    (batch/bulk operations)  │   │  │
│                       │  │  payment-compliance-tq (AML/sanctions check)  │   │  │
│                       │  └───────────────────────────────────────────────┘   │  │
│                       └──────────────────────────────────────────────────────┘  │
│                                          │                                      │
│           ┌──────────────────────────────┼───────────────────────────────┐      │
│           │                              │                               │      │
│           ▼                              ▼                               ▼      │
│  ┌─────────────────┐    ┌─────────────────────────┐    ┌──────────────────┐   │
│  │  Payment Workers │    │  Compliance Workers      │    │  Notification    │   │
│  │  (20 pods)       │    │  (5 pods)                │    │  Workers (10)    │   │
│  │                  │    │                          │    │                  │   │
│  │  - Debit         │    │  - AML Screening        │    │  - Email         │   │
│  │  - Credit        │    │  - Sanctions Check      │    │  - SMS           │   │
│  │  - FX Convert    │    │  - Fraud Detection      │    │  - Push          │   │
│  │  - Ledger Update │    │  - PEP Check            │    │  - Webhook       │   │
│  └────────┬─────────┘    └────────────┬─────────────┘    └────────┬─────────┘   │
│           │                           │                           │              │
│           ▼                           ▼                           ▼              │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                        EXTERNAL INTEGRATIONS                             │   │
│  │                                                                          │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────┐ │   │
│  │  │  Bank A  │  │  Bank B  │  │  Stripe  │  │  SWIFT   │  │Sanctions│ │   │
│  │  │  API     │  │  API     │  │  Connect │  │  Network │  │  DB     │ │   │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘  └─────────┘ │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                        DATA STORES                                       │   │
│  │                                                                          │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌────────────┐ │   │
│  │  │  Ledger DB   │  │  Idempotency │  │  Audit Log   │  │  FX Rate   │ │   │
│  │  │  (PostgreSQL)│  │  Store (Redis)│  │  (Immutable) │  │  Cache     │ │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘  └────────────┘ │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────────────────────────┘
```

## Payment Flow - Saga Pattern

```
                    HAPPY PATH                          COMPENSATION PATH
                    ──────────                          ─────────────────

Start ──► Validate ──► Compliance ──► Lock FX ──► Debit ──► Credit ──► Ledger ──► Notify ──► Done
              │              │            │          │          │          │
              │ fail         │ fail       │ fail    │ fail     │ fail     │ fail
              ▼              ▼            ▼          ▼          ▼          ▼
           Reject      Flag for       Release    (nothing    Reverse   Reverse
                       Review         FX Lock    to undo)    Debit     Debit +
                                                                       Release FX
```

## Complete Go Implementation

### Domain Types

```go
package payments

import (
	"time"
)

// TransferRequest represents an incoming money transfer request
type TransferRequest struct {
	TransferID     string    `json:"transfer_id"`
	IdempotencyKey string    `json:"idempotency_key"`
	SourceAccount  Account   `json:"source_account"`
	DestAccount    Account   `json:"dest_account"`
	Amount         Money     `json:"amount"`
	Metadata       Metadata  `json:"metadata"`
	RequestedAt    time.Time `json:"requested_at"`
	Priority       Priority  `json:"priority"`
}

type Account struct {
	ID          string `json:"id"`
	BankCode    string `json:"bank_code"`
	AccountNum  string `json:"account_num"`
	RoutingNum  string `json:"routing_num"`
	HolderName  string `json:"holder_name"`
	Country     string `json:"country"`
	Currency    string `json:"currency"`
}

type Money struct {
	AmountCents int64  `json:"amount_cents"` // Always in smallest unit
	Currency    string `json:"currency"`
}

type Metadata struct {
	Reference     string            `json:"reference"`
	Description   string            `json:"description"`
	Category      string            `json:"category"`
	Tags          map[string]string `json:"tags"`
	InitiatedBy   string            `json:"initiated_by"`
	IPAddress     string            `json:"ip_address"`
}

type Priority int
const (
	PriorityStandard Priority = iota
	PriorityHigh
	PriorityCritical
)

// TransferState tracks the full state of a transfer
type TransferState struct {
	TransferID     string
	Status         TransferStatus
	Steps          []StepRecord
	DebitRef       string
	CreditRef      string
	FXRate         *FXRate
	ComplianceRef  string
	LedgerEntryID  string
	Error          string
	StartedAt      time.Time
	CompletedAt    time.Time
}

type TransferStatus string
const (
	StatusPending         TransferStatus = "PENDING"
	StatusValidating      TransferStatus = "VALIDATING"
	StatusComplianceCheck TransferStatus = "COMPLIANCE_CHECK"
	StatusFXLocking       TransferStatus = "FX_LOCKING"
	StatusDebiting        TransferStatus = "DEBITING"
	StatusCrediting       TransferStatus = "CREDITING"
	StatusReconciling     TransferStatus = "RECONCILING"
	StatusCompleted       TransferStatus = "COMPLETED"
	StatusFailed          TransferStatus = "FAILED"
	StatusCompensating    TransferStatus = "COMPENSATING"
	StatusCompensated     TransferStatus = "COMPENSATED"
	StatusManualReview    TransferStatus = "MANUAL_REVIEW"
)

type StepRecord struct {
	Step        string
	Status      string
	StartedAt   time.Time
	CompletedAt time.Time
	Reference   string
	Error       string
}

type FXRate struct {
	FromCurrency string
	ToCurrency   string
	Rate         float64
	LockedUntil  time.Time
	QuoteID      string
}

type ComplianceResult struct {
	Approved     bool
	RiskScore    float64
	Flags        []string
	ReviewNeeded bool
	Reference    string
}

type DebitResult struct {
	Reference   string
	BalanceAfter int64
	ProcessedAt time.Time
}

type CreditResult struct {
	Reference   string
	ProcessedAt time.Time
}

type LedgerEntry struct {
	EntryID     string
	DebitRef    string
	CreditRef   string
	Amount      Money
	FXRate      *FXRate
	CreatedAt   time.Time
}
```

### Transfer Workflow - Full Saga Implementation

```go
package workflows

import (
	"fmt"
	"time"

	"go.temporal.io/sdk/temporal"
	"go.temporal.io/sdk/workflow"

	"github.com/company/payments/activities"
	"github.com/company/payments/domain"
)

// MoneyTransferWorkflow orchestrates a complete money transfer with saga compensation.
// This workflow guarantees exactly-once money movement even across failures.
func MoneyTransferWorkflow(ctx workflow.Context, req domain.TransferRequest) (*domain.TransferState, error) {
	logger := workflow.GetLogger(ctx)
	logger.Info("Starting money transfer",
		"transferID", req.TransferID,
		"amount", req.Amount,
		"source", req.SourceAccount.ID,
		"dest", req.DestAccount.ID,
	)

	// Initialize state
	state := &domain.TransferState{
		TransferID: req.TransferID,
		Status:     domain.StatusPending,
		StartedAt:  workflow.Now(ctx),
	}

	// Set search attributes for visibility
	_ = workflow.UpsertSearchAttributes(ctx, map[string]interface{}{
		"TransferID":     req.TransferID,
		"SourceAccount":  req.SourceAccount.ID,
		"DestAccount":    req.DestAccount.ID,
		"AmountCents":    req.Amount.AmountCents,
		"Currency":       req.Amount.Currency,
		"Status":         string(state.Status),
		"Priority":       int(req.Priority),
	})

	// Register query handler for real-time status
	err := workflow.SetQueryHandler(ctx, "get-transfer-state", func() (*domain.TransferState, error) {
		return state, nil
	})
	if err != nil {
		return nil, fmt.Errorf("failed to register query handler: %w", err)
	}

	// Compensation stack (LIFO)
	var compensations []func(workflow.Context) error

	// Helper to update state and search attributes
	updateStatus := func(status domain.TransferStatus) {
		state.Status = status
		_ = workflow.UpsertSearchAttributes(ctx, map[string]interface{}{
			"Status": string(status),
		})
	}

	// Helper to run compensations in reverse order
	runCompensations := func(ctx workflow.Context) {
		updateStatus(domain.StatusCompensating)
		logger.Info("Running compensations", "count", len(compensations))

		// Use disconnected context so compensations run even if workflow is cancelled
		compensateCtx, _ := workflow.NewDisconnectedContext(ctx)
		compensateOpts := workflow.ActivityOptions{
			StartToCloseTimeout:    60 * time.Second,
			HeartbeatTimeout:       15 * time.Second,
			ScheduleToCloseTimeout: 5 * time.Minute,
			RetryPolicy: &temporal.RetryPolicy{
				InitialInterval:    2 * time.Second,
				BackoffCoefficient: 2.0,
				MaximumInterval:    time.Minute,
				MaximumAttempts:    20, // Try very hard to compensate
			},
		}
		compensateCtx = workflow.WithActivityOptions(compensateCtx, compensateOpts)

		for i := len(compensations) - 1; i >= 0; i-- {
			if err := compensations[i](compensateCtx); err != nil {
				logger.Error("CRITICAL: Compensation failed",
					"step", i,
					"error", err,
					"transferID", req.TransferID,
				)
				updateStatus(domain.StatusManualReview)
				// Alert on-call: this needs human intervention
				_ = workflow.ExecuteActivity(compensateCtx,
					activities.AlertOpsTeam,
					domain.OpsAlert{
						Severity:   "CRITICAL",
						TransferID: req.TransferID,
						Message:    fmt.Sprintf("Compensation step %d failed: %v", i, err),
					},
				).Get(compensateCtx, nil)
				return
			}
		}
		updateStatus(domain.StatusCompensated)
	}

	// ─────────────────────────────────────────────────────────────────────────
	// STEP 1: Validate Accounts
	// ─────────────────────────────────────────────────────────────────────────
	updateStatus(domain.StatusValidating)
	state.Steps = append(state.Steps, domain.StepRecord{Step: "validate", Status: "started", StartedAt: workflow.Now(ctx)})

	validateOpts := workflow.ActivityOptions{
		StartToCloseTimeout: 10 * time.Second,
		RetryPolicy: &temporal.RetryPolicy{
			InitialInterval:    500 * time.Millisecond,
			BackoffCoefficient: 2.0,
			MaximumInterval:    5 * time.Second,
			MaximumAttempts:    3,
			NonRetryableErrorTypes: []string{
				"InvalidAccountError",
				"AccountClosedError",
				"AccountFrozenError",
			},
		},
	}
	validateCtx := workflow.WithActivityOptions(ctx, validateOpts)

	var validationResult domain.ValidationResult
	err = workflow.ExecuteActivity(validateCtx, activities.ValidateAccounts, domain.ValidateRequest{
		Source:      req.SourceAccount,
		Destination: req.DestAccount,
		Amount:      req.Amount,
	}).Get(ctx, &validationResult)
	if err != nil {
		state.Error = fmt.Sprintf("validation failed: %v", err)
		updateStatus(domain.StatusFailed)
		return state, nil // Don't return error - workflow completed, transfer failed
	}
	state.Steps[len(state.Steps)-1].Status = "completed"
	state.Steps[len(state.Steps)-1].CompletedAt = workflow.Now(ctx)

	// ─────────────────────────────────────────────────────────────────────────
	// STEP 2: Compliance Check (AML, Sanctions, Fraud)
	// ─────────────────────────────────────────────────────────────────────────
	updateStatus(domain.StatusComplianceCheck)
	state.Steps = append(state.Steps, domain.StepRecord{Step: "compliance", Status: "started", StartedAt: workflow.Now(ctx)})

	complianceOpts := workflow.ActivityOptions{
		TaskQueue:           "payment-compliance-tq",
		StartToCloseTimeout: 30 * time.Second,
		RetryPolicy: &temporal.RetryPolicy{
			InitialInterval: time.Second,
			MaximumAttempts: 5,
		},
	}
	complianceCtx := workflow.WithActivityOptions(ctx, complianceOpts)

	var complianceResult domain.ComplianceResult
	err = workflow.ExecuteActivity(complianceCtx, activities.RunComplianceChecks, domain.ComplianceRequest{
		Source:      req.SourceAccount,
		Destination: req.DestAccount,
		Amount:      req.Amount,
		Metadata:    req.Metadata,
	}).Get(ctx, &complianceResult)
	if err != nil {
		state.Error = fmt.Sprintf("compliance check failed: %v", err)
		updateStatus(domain.StatusFailed)
		return state, nil
	}

	// Handle human review requirement
	if complianceResult.ReviewNeeded {
		logger.Info("Transfer requires compliance review", "riskScore", complianceResult.RiskScore)
		updateStatus(domain.StatusManualReview)

		// Wait for approval signal (with timeout)
		approvalCh := workflow.GetSignalChannel(ctx, "compliance-approval")
		timerCtx, cancelTimer := workflow.WithCancel(ctx)
		timer := workflow.NewTimer(timerCtx, 24*time.Hour)

		selector := workflow.NewSelector(ctx)
		var approved bool

		selector.AddReceive(approvalCh, func(ch workflow.ReceiveChannel, more bool) {
			var decision domain.ComplianceDecision
			ch.Receive(ctx, &decision)
			approved = decision.Approved
			cancelTimer()
		})
		selector.AddFuture(timer, func(f workflow.Future) {
			approved = false // Timeout = reject
		})
		selector.Select(ctx)

		if !approved {
			state.Error = "compliance review rejected or timed out"
			updateStatus(domain.StatusFailed)
			return state, nil
		}
	}

	state.ComplianceRef = complianceResult.Reference
	state.Steps[len(state.Steps)-1].Status = "completed"
	state.Steps[len(state.Steps)-1].CompletedAt = workflow.Now(ctx)
	state.Steps[len(state.Steps)-1].Reference = complianceResult.Reference

	// ─────────────────────────────────────────────────────────────────────────
	// STEP 3: Lock FX Rate (if cross-currency)
	// ─────────────────────────────────────────────────────────────────────────
	if req.SourceAccount.Currency != req.DestAccount.Currency {
		updateStatus(domain.StatusFXLocking)
		state.Steps = append(state.Steps, domain.StepRecord{Step: "fx_lock", Status: "started", StartedAt: workflow.Now(ctx)})

		fxOpts := workflow.ActivityOptions{
			StartToCloseTimeout: 5 * time.Second,
			RetryPolicy: &temporal.RetryPolicy{
				InitialInterval: 200 * time.Millisecond,
				MaximumAttempts: 3,
			},
		}
		fxCtx := workflow.WithActivityOptions(ctx, fxOpts)

		var fxRate domain.FXRate
		err = workflow.ExecuteActivity(fxCtx, activities.LockFXRate, domain.FXRequest{
			FromCurrency: req.SourceAccount.Currency,
			ToCurrency:   req.DestAccount.Currency,
			Amount:       req.Amount,
			LockDuration: 5 * time.Minute,
		}).Get(ctx, &fxRate)
		if err != nil {
			state.Error = fmt.Sprintf("FX rate lock failed: %v", err)
			updateStatus(domain.StatusFailed)
			return state, nil
		}

		state.FXRate = &fxRate
		state.Steps[len(state.Steps)-1].Status = "completed"
		state.Steps[len(state.Steps)-1].CompletedAt = workflow.Now(ctx)
		state.Steps[len(state.Steps)-1].Reference = fxRate.QuoteID

		// Add FX compensation
		compensations = append(compensations, func(compCtx workflow.Context) error {
			return workflow.ExecuteActivity(compCtx, activities.ReleaseFXLock, fxRate.QuoteID).Get(compCtx, nil)
		})
	}

	// ─────────────────────────────────────────────────────────────────────────
	// STEP 4: Debit Source Account
	// ─────────────────────────────────────────────────────────────────────────
	updateStatus(domain.StatusDebiting)
	state.Steps = append(state.Steps, domain.StepRecord{Step: "debit", Status: "started", StartedAt: workflow.Now(ctx)})

	debitOpts := workflow.ActivityOptions{
		StartToCloseTimeout: 30 * time.Second,
		HeartbeatTimeout:    10 * time.Second,
		RetryPolicy: &temporal.RetryPolicy{
			InitialInterval:    time.Second,
			BackoffCoefficient: 2.0,
			MaximumInterval:    30 * time.Second,
			MaximumAttempts:    5,
			NonRetryableErrorTypes: []string{
				"InsufficientFundsError",
				"AccountFrozenError",
				"DailyLimitExceededError",
			},
		},
	}
	debitCtx := workflow.WithActivityOptions(ctx, debitOpts)

	var debitResult domain.DebitResult
	err = workflow.ExecuteActivity(debitCtx, activities.DebitAccount, domain.DebitRequest{
		Account:        req.SourceAccount,
		Amount:         req.Amount,
		IdempotencyKey: fmt.Sprintf("%s-debit", req.IdempotencyKey),
		Reference:      req.TransferID,
	}).Get(ctx, &debitResult)
	if err != nil {
		state.Error = fmt.Sprintf("debit failed: %v", err)
		runCompensations(ctx) // Release FX lock if held
		if state.Status != domain.StatusManualReview {
			updateStatus(domain.StatusFailed)
		}
		return state, nil
	}

	state.DebitRef = debitResult.Reference
	state.Steps[len(state.Steps)-1].Status = "completed"
	state.Steps[len(state.Steps)-1].CompletedAt = workflow.Now(ctx)
	state.Steps[len(state.Steps)-1].Reference = debitResult.Reference

	// Add debit compensation (reverse the debit)
	compensations = append(compensations, func(compCtx workflow.Context) error {
		return workflow.ExecuteActivity(compCtx, activities.ReverseDebit, domain.ReverseDebitRequest{
			OriginalRef:    debitResult.Reference,
			Account:        req.SourceAccount,
			Amount:         req.Amount,
			IdempotencyKey: fmt.Sprintf("%s-reverse-debit", req.IdempotencyKey),
			Reason:         "Transfer compensation",
		}).Get(compCtx, nil)
	})

	// ─────────────────────────────────────────────────────────────────────────
	// STEP 5: Credit Destination Account
	// ─────────────────────────────────────────────────────────────────────────
	updateStatus(domain.StatusCrediting)
	state.Steps = append(state.Steps, domain.StepRecord{Step: "credit", Status: "started", StartedAt: workflow.Now(ctx)})

	creditAmount := req.Amount
	if state.FXRate != nil {
		creditAmount = domain.Money{
			AmountCents: int64(float64(req.Amount.AmountCents) * state.FXRate.Rate),
			Currency:    req.DestAccount.Currency,
		}
	}

	creditOpts := workflow.ActivityOptions{
		StartToCloseTimeout: 30 * time.Second,
		HeartbeatTimeout:    10 * time.Second,
		RetryPolicy: &temporal.RetryPolicy{
			InitialInterval:    time.Second,
			BackoffCoefficient: 2.0,
			MaximumInterval:    30 * time.Second,
			MaximumAttempts:    10, // Try harder - money already debited!
			NonRetryableErrorTypes: []string{
				"AccountClosedError",
				"InvalidAccountError",
			},
		},
	}
	creditCtx := workflow.WithActivityOptions(ctx, creditOpts)

	var creditResult domain.CreditResult
	err = workflow.ExecuteActivity(creditCtx, activities.CreditAccount, domain.CreditRequest{
		Account:        req.DestAccount,
		Amount:         creditAmount,
		IdempotencyKey: fmt.Sprintf("%s-credit", req.IdempotencyKey),
		Reference:      req.TransferID,
		SourceRef:      debitResult.Reference,
	}).Get(ctx, &creditResult)
	if err != nil {
		state.Error = fmt.Sprintf("credit failed: %v", err)
		logger.Error("CRITICAL: Credit failed after debit succeeded, compensating",
			"debitRef", debitResult.Reference,
			"error", err,
		)
		runCompensations(ctx)
		if state.Status != domain.StatusManualReview {
			updateStatus(domain.StatusFailed)
		}
		return state, nil
	}

	state.CreditRef = creditResult.Reference
	state.Steps[len(state.Steps)-1].Status = "completed"
	state.Steps[len(state.Steps)-1].CompletedAt = workflow.Now(ctx)
	state.Steps[len(state.Steps)-1].Reference = creditResult.Reference

	// ─────────────────────────────────────────────────────────────────────────
	// STEP 6: Record in Ledger
	// ─────────────────────────────────────────────────────────────────────────
	updateStatus(domain.StatusReconciling)
	state.Steps = append(state.Steps, domain.StepRecord{Step: "ledger", Status: "started", StartedAt: workflow.Now(ctx)})

	ledgerOpts := workflow.ActivityOptions{
		StartToCloseTimeout: 10 * time.Second,
		RetryPolicy: &temporal.RetryPolicy{
			InitialInterval: 500 * time.Millisecond,
			MaximumAttempts: 10,
		},
	}
	ledgerCtx := workflow.WithActivityOptions(ctx, ledgerOpts)

	var ledgerEntry domain.LedgerEntry
	err = workflow.ExecuteActivity(ledgerCtx, activities.RecordLedgerEntry, domain.LedgerRequest{
		TransferID:  req.TransferID,
		DebitRef:    debitResult.Reference,
		CreditRef:   creditResult.Reference,
		Amount:      req.Amount,
		CreditAmount: creditAmount,
		FXRate:      state.FXRate,
		Metadata:    req.Metadata,
	}).Get(ctx, &ledgerEntry)
	if err != nil {
		// Ledger write failed but money already moved - this is reconciliation debt
		logger.Error("Ledger write failed - money moved but not recorded",
			"debitRef", debitResult.Reference,
			"creditRef", creditResult.Reference,
			"error", err,
		)
		// Don't compensate - money moved successfully, just log the discrepancy
		_ = workflow.ExecuteActivity(ledgerCtx, activities.RecordReconciliationGap, domain.ReconciliationGap{
			TransferID: req.TransferID,
			DebitRef:   debitResult.Reference,
			CreditRef:  creditResult.Reference,
			Error:      err.Error(),
		}).Get(ctx, nil)
	} else {
		state.LedgerEntryID = ledgerEntry.EntryID
	}
	state.Steps[len(state.Steps)-1].Status = "completed"
	state.Steps[len(state.Steps)-1].CompletedAt = workflow.Now(ctx)

	// ─────────────────────────────────────────────────────────────────────────
	// STEP 7: Send Notifications (fire-and-forget, don't block on failure)
	// ─────────────────────────────────────────────────────────────────────────
	notifyOpts := workflow.ActivityOptions{
		TaskQueue:           "notification-tq",
		StartToCloseTimeout: 10 * time.Second,
		RetryPolicy: &temporal.RetryPolicy{
			MaximumAttempts: 3,
		},
	}
	notifyCtx := workflow.WithActivityOptions(ctx, notifyOpts)

	// Fire notifications in parallel, don't wait
	workflow.Go(ctx, func(gCtx workflow.Context) {
		_ = workflow.ExecuteActivity(notifyCtx, activities.NotifySender, domain.NotifyRequest{
			AccountID:  req.SourceAccount.ID,
			TransferID: req.TransferID,
			Type:       "DEBIT",
			Amount:     req.Amount,
		}).Get(gCtx, nil)
	})
	workflow.Go(ctx, func(gCtx workflow.Context) {
		_ = workflow.ExecuteActivity(notifyCtx, activities.NotifyRecipient, domain.NotifyRequest{
			AccountID:  req.DestAccount.ID,
			TransferID: req.TransferID,
			Type:       "CREDIT",
			Amount:     creditAmount,
		}).Get(gCtx, nil)
	})

	// Wait briefly for notifications (but don't block completion)
	_ = workflow.Sleep(ctx, 2*time.Second)

	// ─────────────────────────────────────────────────────────────────────────
	// DONE
	// ─────────────────────────────────────────────────────────────────────────
	state.CompletedAt = workflow.Now(ctx)
	updateStatus(domain.StatusCompleted)

	logger.Info("Transfer completed successfully",
		"transferID", req.TransferID,
		"duration", state.CompletedAt.Sub(state.StartedAt),
		"debitRef", state.DebitRef,
		"creditRef", state.CreditRef,
	)

	return state, nil
}
```

### Activities Implementation

```go
package activities

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"time"

	"go.temporal.io/sdk/activity"
	"go.temporal.io/sdk/temporal"

	"github.com/company/payments/domain"
)

// PaymentActivities holds dependencies for payment activities
type PaymentActivities struct {
	bankClients    map[string]BankClient  // bank_code -> client
	complianceSvc  ComplianceService
	fxService      FXService
	ledgerDB       LedgerRepository
	idempotencyStore IdempotencyStore
	notificationSvc NotificationService
	metricsClient  MetricsClient
}

// ValidateAccounts checks that both accounts exist, are active, and can transact
func (a *PaymentActivities) ValidateAccounts(ctx context.Context, req domain.ValidateRequest) (*domain.ValidationResult, error) {
	logger := activity.GetLogger(ctx)

	// Validate source account
	sourceClient, ok := a.bankClients[req.Source.BankCode]
	if !ok {
		return nil, temporal.NewNonRetryableApplicationError(
			fmt.Sprintf("unsupported bank: %s", req.Source.BankCode),
			"InvalidAccountError",
			nil,
		)
	}

	sourceStatus, err := sourceClient.GetAccountStatus(ctx, req.Source.AccountNum)
	if err != nil {
		return nil, fmt.Errorf("failed to check source account: %w", err)
	}
	if sourceStatus != "ACTIVE" {
		return nil, temporal.NewNonRetryableApplicationError(
			fmt.Sprintf("source account not active: %s", sourceStatus),
			"AccountClosedError",
			nil,
		)
	}

	// Validate destination account
	destClient, ok := a.bankClients[req.Destination.BankCode]
	if !ok {
		return nil, temporal.NewNonRetryableApplicationError(
			fmt.Sprintf("unsupported bank: %s", req.Destination.BankCode),
			"InvalidAccountError",
			nil,
		)
	}

	destStatus, err := destClient.GetAccountStatus(ctx, req.Destination.AccountNum)
	if err != nil {
		return nil, fmt.Errorf("failed to check dest account: %w", err)
	}
	if destStatus != "ACTIVE" {
		return nil, temporal.NewNonRetryableApplicationError(
			fmt.Sprintf("destination account not active: %s", destStatus),
			"AccountClosedError",
			nil,
		)
	}

	// Check daily limits
	dailyTotal, err := a.ledgerDB.GetDailyTransferTotal(ctx, req.Source.ID)
	if err != nil {
		return nil, fmt.Errorf("failed to check daily limit: %w", err)
	}
	if dailyTotal+req.Amount.AmountCents > 1_000_000_00 { // $1M daily limit
		return nil, temporal.NewNonRetryableApplicationError(
			"daily transfer limit exceeded",
			"DailyLimitExceededError",
			nil,
		)
	}

	logger.Info("Validation passed",
		"source", req.Source.ID,
		"dest", req.Destination.ID,
	)

	return &domain.ValidationResult{
		Valid:         true,
		SourceStatus:  sourceStatus,
		DestStatus:    destStatus,
		DailyRemaining: 1_000_000_00 - dailyTotal,
	}, nil
}

// RunComplianceChecks performs AML, sanctions, and fraud checks
func (a *PaymentActivities) RunComplianceChecks(ctx context.Context, req domain.ComplianceRequest) (*domain.ComplianceResult, error) {
	activity.RecordHeartbeat(ctx, "starting_compliance_checks")

	// Run checks in parallel (within the activity)
	type checkResult struct {
		name   string
		passed bool
		score  float64
		err    error
	}

	results := make(chan checkResult, 3)

	// AML check
	go func() {
		passed, score, err := a.complianceSvc.CheckAML(ctx, req.Source, req.Destination, req.Amount)
		results <- checkResult{"aml", passed, score, err}
	}()

	// Sanctions check
	go func() {
		passed, score, err := a.complianceSvc.CheckSanctions(ctx, req.Source.HolderName, req.Destination.HolderName)
		results <- checkResult{"sanctions", passed, score, err}
	}()

	// Fraud check
	go func() {
		passed, score, err := a.complianceSvc.CheckFraud(ctx, req.Source, req.Amount, req.Metadata)
		results <- checkResult{"fraud", passed, score, err}
	}()

	activity.RecordHeartbeat(ctx, "waiting_for_checks")

	var maxRiskScore float64
	var flags []string
	for i := 0; i < 3; i++ {
		r := <-results
		if r.err != nil {
			return nil, fmt.Errorf("%s check failed: %w", r.name, r.err)
		}
		if !r.passed {
			flags = append(flags, r.name+"_flagged")
		}
		if r.score > maxRiskScore {
			maxRiskScore = r.score
		}
	}

	needsReview := maxRiskScore > 0.7 || len(flags) > 0

	ref := generateComplianceRef(req)
	return &domain.ComplianceResult{
		Approved:     !needsReview || maxRiskScore < 0.9,
		RiskScore:    maxRiskScore,
		Flags:        flags,
		ReviewNeeded: needsReview,
		Reference:    ref,
	}, nil
}

// DebitAccount performs the actual debit against the bank API
func (a *PaymentActivities) DebitAccount(ctx context.Context, req domain.DebitRequest) (*domain.DebitResult, error) {
	logger := activity.GetLogger(ctx)
	info := activity.GetInfo(ctx)

	logger.Info("Debiting account",
		"account", req.Account.ID,
		"amount", req.Amount.AmountCents,
		"attempt", info.Attempt,
		"idempotencyKey", req.IdempotencyKey,
	)

	// Check idempotency - have we already processed this?
	existing, err := a.idempotencyStore.Get(ctx, req.IdempotencyKey)
	if err == nil && existing != nil {
		logger.Info("Debit already processed (idempotent)", "ref", existing.Reference)
		return &domain.DebitResult{
			Reference:   existing.Reference,
			ProcessedAt: existing.ProcessedAt,
		}, nil
	}

	activity.RecordHeartbeat(ctx, "calling_bank_api")

	// Call the bank API
	bankClient := a.bankClients[req.Account.BankCode]
	resp, err := bankClient.Debit(ctx, BankDebitRequest{
		AccountNumber:  req.Account.AccountNum,
		RoutingNumber:  req.Account.RoutingNum,
		AmountCents:    req.Amount.AmountCents,
		Currency:       req.Amount.Currency,
		Reference:      req.Reference,
		IdempotencyKey: req.IdempotencyKey,
	})
	if err != nil {
		// Classify the error
		if isInsufficientFunds(err) {
			return nil, temporal.NewNonRetryableApplicationError(
				"insufficient funds",
				"InsufficientFundsError",
				err,
			)
		}
		if isAccountFrozen(err) {
			return nil, temporal.NewNonRetryableApplicationError(
				"account frozen",
				"AccountFrozenError",
				err,
			)
		}
		// Transient error - will be retried
		return nil, fmt.Errorf("bank debit failed (transient): %w", err)
	}

	// Record idempotency
	_ = a.idempotencyStore.Set(ctx, req.IdempotencyKey, &IdempotencyRecord{
		Reference:   resp.Reference,
		ProcessedAt: time.Now(),
	}, 72*time.Hour)

	// Record metrics
	a.metricsClient.RecordCounter("payment_debit_success", 1,
		"bank", req.Account.BankCode,
		"currency", req.Amount.Currency,
	)

	return &domain.DebitResult{
		Reference:    resp.Reference,
		BalanceAfter: resp.BalanceAfter,
		ProcessedAt:  time.Now(),
	}, nil
}

// CreditAccount performs the actual credit to destination bank
func (a *PaymentActivities) CreditAccount(ctx context.Context, req domain.CreditRequest) (*domain.CreditResult, error) {
	logger := activity.GetLogger(ctx)

	// Idempotency check
	existing, err := a.idempotencyStore.Get(ctx, req.IdempotencyKey)
	if err == nil && existing != nil {
		logger.Info("Credit already processed (idempotent)", "ref", existing.Reference)
		return &domain.CreditResult{
			Reference:   existing.Reference,
			ProcessedAt: existing.ProcessedAt,
		}, nil
	}

	activity.RecordHeartbeat(ctx, "calling_bank_api")

	bankClient := a.bankClients[req.Account.BankCode]
	resp, err := bankClient.Credit(ctx, BankCreditRequest{
		AccountNumber:  req.Account.AccountNum,
		RoutingNumber:  req.Account.RoutingNum,
		AmountCents:    req.Amount.AmountCents,
		Currency:       req.Amount.Currency,
		Reference:      req.Reference,
		SourceRef:      req.SourceRef,
		IdempotencyKey: req.IdempotencyKey,
	})
	if err != nil {
		if isAccountClosed(err) {
			return nil, temporal.NewNonRetryableApplicationError(
				"destination account closed",
				"AccountClosedError",
				err,
			)
		}
		return nil, fmt.Errorf("bank credit failed (transient): %w", err)
	}

	_ = a.idempotencyStore.Set(ctx, req.IdempotencyKey, &IdempotencyRecord{
		Reference:   resp.Reference,
		ProcessedAt: time.Now(),
	}, 72*time.Hour)

	return &domain.CreditResult{
		Reference:   resp.Reference,
		ProcessedAt: time.Now(),
	}, nil
}

// ReverseDebit reverses a previously completed debit (compensation)
func (a *PaymentActivities) ReverseDebit(ctx context.Context, req domain.ReverseDebitRequest) error {
	logger := activity.GetLogger(ctx)
	logger.Info("Reversing debit",
		"originalRef", req.OriginalRef,
		"account", req.Account.ID,
		"reason", req.Reason,
	)

	// Idempotency check for reversal
	existing, err := a.idempotencyStore.Get(ctx, req.IdempotencyKey)
	if err == nil && existing != nil {
		logger.Info("Reversal already processed", "ref", existing.Reference)
		return nil
	}

	activity.RecordHeartbeat(ctx, "reversing_debit")

	bankClient := a.bankClients[req.Account.BankCode]
	_, err = bankClient.Reverse(ctx, BankReverseRequest{
		OriginalReference: req.OriginalRef,
		AmountCents:       req.Amount.AmountCents,
		Reason:            req.Reason,
		IdempotencyKey:    req.IdempotencyKey,
	})
	if err != nil {
		return fmt.Errorf("reversal failed: %w", err)
	}

	_ = a.idempotencyStore.Set(ctx, req.IdempotencyKey, &IdempotencyRecord{
		Reference:   req.OriginalRef + "-reversed",
		ProcessedAt: time.Now(),
	}, 72*time.Hour)

	a.metricsClient.RecordCounter("payment_reversal", 1,
		"bank", req.Account.BankCode,
		"reason", req.Reason,
	)

	return nil
}

// LockFXRate locks an exchange rate for a specified duration
func (a *PaymentActivities) LockFXRate(ctx context.Context, req domain.FXRequest) (*domain.FXRate, error) {
	quote, err := a.fxService.GetQuote(ctx, req.FromCurrency, req.ToCurrency, req.Amount.AmountCents)
	if err != nil {
		return nil, fmt.Errorf("FX quote failed: %w", err)
	}

	locked, err := a.fxService.LockRate(ctx, quote.QuoteID, req.LockDuration)
	if err != nil {
		return nil, fmt.Errorf("FX lock failed: %w", err)
	}

	return &domain.FXRate{
		FromCurrency: req.FromCurrency,
		ToCurrency:   req.ToCurrency,
		Rate:         locked.Rate,
		LockedUntil:  locked.ExpiresAt,
		QuoteID:      locked.QuoteID,
	}, nil
}

// ReleaseFXLock releases a previously locked FX rate
func (a *PaymentActivities) ReleaseFXLock(ctx context.Context, quoteID string) error {
	return a.fxService.ReleaseLock(ctx, quoteID)
}

// RecordLedgerEntry creates a double-entry ledger record
func (a *PaymentActivities) RecordLedgerEntry(ctx context.Context, req domain.LedgerRequest) (*domain.LedgerEntry, error) {
	entry, err := a.ledgerDB.CreateEntry(ctx, LedgerEntryRow{
		TransferID:      req.TransferID,
		DebitRef:        req.DebitRef,
		CreditRef:       req.CreditRef,
		DebitAmount:     req.Amount.AmountCents,
		DebitCurrency:   req.Amount.Currency,
		CreditAmount:    req.CreditAmount.AmountCents,
		CreditCurrency:  req.CreditAmount.Currency,
		FXQuoteID:       getFXQuoteID(req.FXRate),
		FXRate:          getFXRateValue(req.FXRate),
		Description:     req.Metadata.Description,
		Reference:       req.Metadata.Reference,
		CreatedAt:       time.Now(),
	})
	if err != nil {
		return nil, fmt.Errorf("ledger write failed: %w", err)
	}

	return &domain.LedgerEntry{
		EntryID:   entry.ID,
		DebitRef:  req.DebitRef,
		CreditRef: req.CreditRef,
		Amount:    req.Amount,
		FXRate:    req.FXRate,
		CreatedAt: entry.CreatedAt,
	}, nil
}

// AlertOpsTeam sends a critical alert requiring human intervention
func (a *PaymentActivities) AlertOpsTeam(ctx context.Context, alert domain.OpsAlert) error {
	return a.notificationSvc.SendOpsAlert(ctx, alert)
}

func generateComplianceRef(req domain.ComplianceRequest) string {
	h := sha256.New()
	h.Write([]byte(fmt.Sprintf("%s-%s-%d", req.Source.ID, req.Destination.ID, req.Amount.AmountCents)))
	return "CMP-" + hex.EncodeToString(h.Sum(nil))[:16]
}
```

### Worker Setup

```go
package main

import (
	"context"
	"fmt"
	"log"
	"os"
	"os/signal"
	"syscall"
	"time"

	"go.temporal.io/sdk/client"
	"go.temporal.io/sdk/interceptor"
	"go.temporal.io/sdk/worker"

	"github.com/company/payments/activities"
	"github.com/company/payments/workflows"
)

func main() {
	// Create Temporal client with mTLS
	c, err := client.Dial(client.Options{
		HostPort:  os.Getenv("TEMPORAL_HOST_PORT"),
		Namespace: "payments-prod",
		ConnectionOptions: client.ConnectionOptions{
			TLS: loadMTLSConfig(),
		},
		MetricsHandler: newPrometheusMetricsHandler(),
		Interceptors: []interceptor.ClientInterceptor{
			NewTracingInterceptor(),
		},
	})
	if err != nil {
		log.Fatalf("Failed to create client: %v", err)
	}
	defer c.Close()

	// Initialize dependencies
	bankClients := initBankClients()
	complianceSvc := initComplianceService()
	fxService := initFXService()
	ledgerDB := initLedgerDB()
	idempotencyStore := initRedisIdempotencyStore()
	notificationSvc := initNotificationService()
	metricsClient := initMetricsClient()

	acts := &activities.PaymentActivities{
		// ... inject all dependencies
	}

	// Create workers for different task queues
	standardWorker := worker.New(c, "payment-standard-tq", worker.Options{
		MaxConcurrentWorkflowTaskPollers:       5,
		MaxConcurrentActivityTaskPollers:       10,
		MaxConcurrentActivityExecutionSize:     50,
		MaxConcurrentWorkflowTaskExecutionSize: 200,
		WorkerStopTimeout:                      60 * time.Second,
		DeadlockDetectionTimeout:               30 * time.Second,
	})
	standardWorker.RegisterWorkflow(workflows.MoneyTransferWorkflow)
	standardWorker.RegisterActivity(acts)

	priorityWorker := worker.New(c, "payment-priority-tq", worker.Options{
		MaxConcurrentWorkflowTaskPollers:       8,
		MaxConcurrentActivityTaskPollers:       15,
		MaxConcurrentActivityExecutionSize:     100,
		MaxConcurrentWorkflowTaskExecutionSize: 400,
		WorkerStopTimeout:                      60 * time.Second,
	})
	priorityWorker.RegisterWorkflow(workflows.MoneyTransferWorkflow)
	priorityWorker.RegisterActivity(acts)

	// Start workers
	errCh := make(chan error, 2)
	go func() { errCh <- standardWorker.Run(worker.InterruptCh()) }()
	go func() { errCh <- priorityWorker.Run(worker.InterruptCh()) }()

	// Wait for shutdown
	sigCh := make(chan os.Signal, 1)
	signal.Notify(sigCh, syscall.SIGINT, syscall.SIGTERM)

	select {
	case sig := <-sigCh:
		log.Printf("Received signal %v, shutting down", sig)
		standardWorker.Stop()
		priorityWorker.Stop()
	case err := <-errCh:
		log.Fatalf("Worker error: %v", err)
	}
}
```

### Starting a Transfer (API Handler)

```go
package api

import (
	"context"
	"fmt"
	"net/http"
	"time"

	"go.temporal.io/sdk/client"

	"github.com/company/payments/domain"
	"github.com/company/payments/workflows"
)

type PaymentHandler struct {
	temporalClient client.Client
}

func (h *PaymentHandler) InitiateTransfer(w http.ResponseWriter, r *http.Request) {
	var req domain.TransferRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "invalid request", http.StatusBadRequest)
		return
	}

	// Generate workflow ID from idempotency key (ensures exactly-once)
	workflowID := fmt.Sprintf("transfer-%s", req.IdempotencyKey)

	// Select task queue based on priority
	taskQueue := "payment-standard-tq"
	if req.Priority >= domain.PriorityHigh || req.Amount.AmountCents > 100_000_00 {
		taskQueue = "payment-priority-tq"
	}

	// Start the workflow
	workflowOpts := client.StartWorkflowOptions{
		ID:                    workflowID,
		TaskQueue:             taskQueue,
		WorkflowRunTimeout:    10 * time.Minute,
		WorkflowIDReusePolicy: enums.WORKFLOW_ID_REUSE_POLICY_REJECT_DUPLICATE,
		SearchAttributes: map[string]interface{}{
			"TransferID":    req.TransferID,
			"SourceAccount": req.SourceAccount.ID,
			"DestAccount":   req.DestAccount.ID,
			"AmountCents":   req.Amount.AmountCents,
			"Currency":      req.Amount.Currency,
			"Priority":      int(req.Priority),
		},
		// Memo for non-indexed data
		Memo: map[string]interface{}{
			"initiated_by": req.Metadata.InitiatedBy,
			"ip_address":   req.Metadata.IPAddress,
		},
	}

	run, err := h.temporalClient.ExecuteWorkflow(
		context.Background(),
		workflowOpts,
		workflows.MoneyTransferWorkflow,
		req,
	)
	if err != nil {
		// If workflow already exists (duplicate idempotency key), return existing
		if isWorkflowAlreadyStarted(err) {
			// Return the existing workflow's status
			w.WriteHeader(http.StatusConflict)
			json.NewEncoder(w).Encode(map[string]string{
				"workflow_id": workflowID,
				"status":     "ALREADY_EXISTS",
			})
			return
		}
		http.Error(w, fmt.Sprintf("failed to start transfer: %v", err), http.StatusInternalServerError)
		return
	}

	w.WriteHeader(http.StatusAccepted)
	json.NewEncoder(w).Encode(map[string]string{
		"workflow_id": run.GetID(),
		"run_id":     run.GetRunID(),
		"status":     "ACCEPTED",
	})
}

// GetTransferStatus queries a running workflow for its current state
func (h *PaymentHandler) GetTransferStatus(w http.ResponseWriter, r *http.Request) {
	workflowID := r.URL.Query().Get("workflow_id")

	resp, err := h.temporalClient.QueryWorkflow(
		context.Background(),
		workflowID,
		"",
		"get-transfer-state",
	)
	if err != nil {
		http.Error(w, fmt.Sprintf("query failed: %v", err), http.StatusInternalServerError)
		return
	}

	var state domain.TransferState
	if err := resp.Get(&state); err != nil {
		http.Error(w, fmt.Sprintf("decode failed: %v", err), http.StatusInternalServerError)
		return
	}

	json.NewEncoder(w).Encode(state)
}
```

---

## Failure Scenarios

### Scenario 1: Bank API Timeout During Debit

```
Timeline:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
t=0s    │ Workflow starts, validation passes, compliance passes
t=5s    │ DebitAccount activity starts (attempt 1)
t=35s   │ StartToCloseTimeout fires (30s) → activity times out
t=36s   │ DebitAccount activity retried (attempt 2)
t=37s   │ Bank API responds quickly this time
t=37s   │ BUT: Did attempt 1 actually succeed at the bank?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

PROTECTION: IdempotencyKey ensures the bank only processes once.
- Attempt 1: Bank receives debit with key "txn-123-debit"
- If bank processed it → attempt 2 with same key returns "already done"
- If bank didn't process it → attempt 2 processes it fresh
- RESULT: Exactly one debit regardless of retries
```

### Scenario 2: Network Partition After Debit, Before Credit

```
Timeline:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
t=0s    │ DebitAccount succeeds, result={ref: "dbt-789"}
t=0.1s  │ Worker records ActivityTaskCompleted to Temporal
t=0.2s  │ *** WORKER CRASHES / NETWORK PARTITION ***
        │
        │ ... time passes ...
        │
t=30s   │ Workflow task times out (no worker completed it)
t=30s   │ Temporal reschedules workflow task to another worker
t=31s   │ New worker picks up workflow task
t=31s   │ Temporal replays: validation ✓, compliance ✓, debit={ref: "dbt-789"} ✓
t=31s   │ Replay catches up → CreditAccount starts (LIVE execution)
t=32s   │ Credit succeeds
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

KEY INSIGHT: The debit result is stored in Temporal's event history.
On replay, the debit activity is NOT re-executed - its recorded result is used.
Money is NEVER debited twice.
```

### Scenario 3: Worker Crash Mid-Workflow

```
Timeline:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
t=0s    │ Worker-01 executing MoneyTransferWorkflow
t=5s    │ Validation activity completed
t=10s   │ Compliance activity completed  
t=15s   │ *** Worker-01 OOM killed ***
        │
t=25s   │ Workflow task timeout triggers
t=25s   │ Temporal dispatches workflow task to Worker-02
t=25.1s │ Worker-02 loads event history (23 events)
t=25.2s │ Worker-02 replays workflow code:
        │   - ExecuteActivity(Validate) → history: result={valid: true} ✓
        │   - ExecuteActivity(Compliance) → history: result={approved: true} ✓
        │   - ExecuteActivity(LockFX) → NO HISTORY → execute for real
t=26s   │ FX lock activity starts fresh
t=27s   │ Workflow continues normally from this point
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ZERO DATA LOSS. Workflow resumes exactly where it was.
```

### Scenario 4: Duplicate Payment Detection

```
Scenario: User clicks "Pay" twice rapidly
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Click 1 → API receives transfer with IdempotencyKey="user-123-order-456"
        → WorkflowID = "transfer-user-123-order-456"
        → StartWorkflow succeeds → workflow begins

Click 2 → API receives same IdempotencyKey
        → Same WorkflowID = "transfer-user-123-order-456"
        → StartWorkflow returns WorkflowExecutionAlreadyStartedError
        → API returns 409 Conflict with existing workflow reference
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

THREE layers of protection:
1. WorkflowID uniqueness (Temporal level)
2. IdempotencyKey at activity level (Bank API level)
3. IdempotencyStore (Redis) for fast rejection before bank call
```

### Scenario 5: Credit Fails After Debit - Compensation

```
Timeline:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
t=0s    │ Debit succeeds: $5000 removed from source account
t=1s    │ Credit attempt 1: destination bank returns 503
t=2s    │ Credit attempt 2: destination bank returns 503
t=4s    │ Credit attempt 3: destination bank returns 503
...     │ (retries with backoff)
t=120s  │ Credit attempt 10: "AccountClosedError" (non-retryable!)
        │
        │ COMPENSATION TRIGGERED:
t=121s  │ ReverseDebit starts with IdempotencyKey="txn-123-reverse-debit"
t=122s  │ Bank API returns credit reversal confirmation
t=122s  │ $5000 returned to source account
t=123s  │ Workflow completes with Status=COMPENSATED
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

The customer's money is NEVER lost. Worst case: temporary hold that gets reversed.
```

---

## Production Configuration

### Timeout Configuration by Activity Type

```go
var TimeoutConfigs = map[string]workflow.ActivityOptions{
	"validate": {
		StartToCloseTimeout:    10 * time.Second,
		ScheduleToStartTimeout: 5 * time.Second,
		RetryPolicy: &temporal.RetryPolicy{
			MaximumAttempts: 3,
		},
	},
	"compliance": {
		StartToCloseTimeout:    30 * time.Second,
		ScheduleToStartTimeout: 10 * time.Second,
		HeartbeatTimeout:       15 * time.Second,
		RetryPolicy: &temporal.RetryPolicy{
			MaximumAttempts: 5,
			InitialInterval: time.Second,
		},
	},
	"bank_debit": {
		StartToCloseTimeout:    30 * time.Second,
		ScheduleToStartTimeout: 5 * time.Second,
		HeartbeatTimeout:       10 * time.Second,
		ScheduleToCloseTimeout: 3 * time.Minute,
		RetryPolicy: &temporal.RetryPolicy{
			MaximumAttempts:    5,
			InitialInterval:    time.Second,
			BackoffCoefficient: 2.0,
			MaximumInterval:    30 * time.Second,
		},
	},
	"bank_credit": {
		StartToCloseTimeout:    30 * time.Second,
		ScheduleToStartTimeout: 5 * time.Second,
		HeartbeatTimeout:       10 * time.Second,
		ScheduleToCloseTimeout: 5 * time.Minute, // More patient - money already debited
		RetryPolicy: &temporal.RetryPolicy{
			MaximumAttempts:    10,
			InitialInterval:    time.Second,
			BackoffCoefficient: 2.0,
			MaximumInterval:    time.Minute,
		},
	},
	"compensation": {
		StartToCloseTimeout:    60 * time.Second,
		ScheduleToCloseTimeout: 10 * time.Minute,
		HeartbeatTimeout:       15 * time.Second,
		RetryPolicy: &temporal.RetryPolicy{
			MaximumAttempts:    20,
			InitialInterval:    2 * time.Second,
			BackoffCoefficient: 2.0,
			MaximumInterval:    2 * time.Minute,
		},
	},
}
```

### Rate Limiting with Activity Semaphores

```go
// Limit concurrent bank API calls to prevent overwhelming the bank
func TransferWithRateLimiting(ctx workflow.Context, req domain.TransferRequest) error {
	// Use a semaphore to limit concurrent debits to bank
	// This prevents overwhelming the bank API
	semaphoreOpts := workflow.ActivityOptions{
		StartToCloseTimeout: 5 * time.Minute, // Wait up to 5 min for semaphore
	}
	semCtx := workflow.WithActivityOptions(ctx, semaphoreOpts)

	// Acquire semaphore (implemented as a separate workflow/activity pattern)
	var permit SemaphorePermit
	err := workflow.ExecuteActivity(semCtx, AcquireBankRateLimit, req.SourceAccount.BankCode).Get(ctx, &permit)
	if err != nil {
		return fmt.Errorf("rate limit acquisition failed: %w", err)
	}
	defer func() {
		// Release on completion
		_ = workflow.ExecuteActivity(ctx, ReleaseBankRateLimit, permit).Get(ctx, nil)
	}()

	// Now safe to call bank API
	return workflow.ExecuteActivity(ctx, DebitAccount, req).Get(ctx, nil)
}
```

---

## Metrics & SLAs

### Key Metrics to Monitor

| Metric | Target | Alert | Dashboard |
|--------|--------|-------|-----------|
| Transfer success rate | > 99.5% | < 99% | Payment Health |
| p50 transfer latency | < 2s | > 5s | Latency |
| p99 transfer latency | < 10s | > 30s | Latency |
| Compensation rate | < 0.5% | > 2% | Saga Health |
| Manual review rate | < 0.1% | > 1% | Compliance |
| Schedule-to-start (payment-tq) | < 100ms | > 1s | Worker Health |
| Failed activity rate | < 1% | > 5% | Activity Health |
| Daily transfer volume | ~50M | < 40M (anomaly) | Volume |
| FX lock timeout rate | < 0.01% | > 0.1% | FX Health |

### Prometheus Metrics (exposed by workers)

```go
// Custom metrics emitted from workflow/activity code
temporal_transfer_started_total{priority, currency}
temporal_transfer_completed_total{priority, currency, status}
temporal_transfer_duration_seconds{priority, currency, quantile}
temporal_transfer_compensation_total{reason}
temporal_bank_api_latency_seconds{bank, operation, quantile}
temporal_bank_api_errors_total{bank, operation, error_type}
temporal_compliance_check_duration_seconds{check_type, quantile}
temporal_compliance_flagged_total{flag_type}

// Temporal SDK built-in metrics
temporal_workflow_task_execution_latency
temporal_activity_execution_latency
temporal_workflow_task_schedule_to_start_latency
temporal_activity_schedule_to_start_latency
temporal_sticky_cache_hit
temporal_worker_task_slots_available{task_type}
```

### SLA Definition

```
Payment Processing SLA:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Domestic same-bank:     p99 < 5s,    success rate > 99.9%
Domestic cross-bank:    p99 < 15s,   success rate > 99.5%
International:          p99 < 60s,   success rate > 99.0%
Batch/bulk:             p99 < 5min,  success rate > 99.5%

Compensation SLA:
  Funds returned to source within 5 minutes of failure detection.
  If compensation fails: human alert within 30 seconds.
  Manual resolution SLA: 4 hours (business hours).
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### Alerting Rules

```yaml
# Prometheus alerting rules
groups:
  - name: payment_alerts
    rules:
      - alert: PaymentSuccessRateLow
        expr: |
          rate(temporal_transfer_completed_total{status="COMPLETED"}[5m]) /
          rate(temporal_transfer_started_total[5m]) < 0.99
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Payment success rate below 99%"

      - alert: PaymentLatencyHigh
        expr: |
          histogram_quantile(0.99, rate(temporal_transfer_duration_seconds_bucket[5m])) > 30
        for: 3m
        labels:
          severity: warning
        annotations:
          summary: "p99 payment latency above 30s"

      - alert: CompensationRateHigh
        expr: |
          rate(temporal_transfer_compensation_total[15m]) /
          rate(temporal_transfer_started_total[15m]) > 0.02
        for: 10m
        labels:
          severity: critical
        annotations:
          summary: "Compensation rate above 2% - possible systemic failure"

      - alert: WorkerStarvation
        expr: |
          histogram_quantile(0.99,
            rate(temporal_activity_schedule_to_start_latency_bucket{task_queue="payment-standard-tq"}[5m])
          ) > 1
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "Payment workers starving - scale up immediately"

      - alert: ManualReviewBacklog
        expr: |
          count(temporal_workflow_running{workflow_type="MoneyTransferWorkflow", status="MANUAL_REVIEW"}) > 50
        for: 15m
        labels:
          severity: warning
        annotations:
          summary: "Manual review backlog growing"
```
