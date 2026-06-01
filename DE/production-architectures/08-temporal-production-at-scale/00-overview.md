# Temporal Production at Scale - Complete Guide

## Table of Contents

| # | Topic | File |
|---|-------|------|
| 0 | Overview & Core Concepts | `00-overview.md` |
| 1 | Payment Processing & Money Transfer | `01-payment-processing-money-transfer.md` |
| 2 | Order Fulfillment Pipeline | `02-order-fulfillment-pipeline.md` |
| 3 | Subscription Billing System | `03-subscription-billing-system.md` |
| 4 | Data Pipeline Orchestration | `04-data-pipeline-orchestration.md` |
| 5 | User Onboarding & KYC | `05-user-onboarding-kyc.md` |
| 6 | Infrastructure Provisioning | `06-infrastructure-provisioning.md` |
| 7 | Batch Processing at Scale | `07-batch-processing.md` |
| 8 | Multi-Region Deployment | `08-multi-region.md` |
| 9 | Testing Strategies | `09-testing-strategies.md` |
| 10 | Observability & Monitoring | `10-observability.md` |
| 11 | Performance Tuning | `11-performance-tuning.md` |
| 12 | Security & Compliance | `12-security-compliance.md` |
| 13 | Migration Guide | `13-migration-guide.md` |

---

## What is Temporal

### Durable Execution Engine

Temporal is a **durable execution engine** that guarantees your code will run to completion regardless of failures. It persists the state of your program at every step, allowing it to resume exactly where it left off after any crash, network partition, or deployment.

The key insight: instead of writing defensive code with retries, state machines, queues, and recovery logic, you write straightforward procedural code. Temporal handles durability transparently.

```
Traditional approach:
  Write code → Add retry logic → Add state persistence → Add recovery →
  Add idempotency → Add monitoring → Add dead letter queues → Pray

Temporal approach:
  Write code → Done (Temporal handles the rest)
```

### History: From Uber Cadence to Temporal

```
Timeline:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
2015    │ Uber builds "Cherami" (durable task queue)
2016    │ Uber starts "Cadence" project (Maxim Fateev, Samar Abbas)
2017    │ Cadence goes to production at Uber (100+ use cases)
2018    │ Cadence open-sourced, adopted by HashiCorp, Coinbase, others
2019    │ Maxim & Samar leave Uber, found Temporal Technologies
2020    │ Temporal v1.0 released (fork of Cadence with major improvements)
2021    │ Temporal raises $103M Series B, Temporal Cloud launches
2022    │ Temporal raises $75M Series C at $1.5B valuation
2023    │ Temporal Cloud GA, Nexus (cross-namespace) announced
2024    │ Temporal Cloud handles 1B+ workflow executions/month
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### Why Temporal vs Alternatives

| Dimension | Temporal | Airflow | AWS Step Functions | Prefect |
|-----------|----------|---------|-------------------|---------|
| **Model** | Code-first (Go/Java/TS/Python) | DAG-based (Python) | JSON/YAML state machine | Code-first (Python) |
| **Durability** | Event-sourced, survives any crash | Task-level retry | State machine persistence | Checkpoint-based |
| **Latency** | Sub-second dispatch | Minutes (scheduler loop) | Seconds | Seconds |
| **Scale** | 100M+ concurrent workflows | 10K-100K DAG runs | Limited by account quotas | 10K-100K flows |
| **Long-running** | Years (continue-as-new) | Not designed for | 1 year max | Not designed for |
| **Human-in-loop** | Signals + timers (native) | Sensors (polling) | Callback tasks | Pause/resume |
| **Self-hosted** | Yes (full control) | Yes | No (AWS only) | Yes (limited) |
| **Versioning** | Worker-based versioning | DAG versioning | Version ARNs | Deployment-based |
| **Cost at scale** | Infrastructure cost only | Infrastructure + overhead | Per-transition pricing ($$$) | Infrastructure + cloud pricing |
| **Child workflows** | Native, unlimited nesting | SubDAGs (limited) | Nested state machines (limited) | Subflows |
| **Dynamic workflows** | Fully dynamic at runtime | Static DAGs | Static definition | Dynamic |

**When to choose Temporal:**
- Mission-critical business processes (payments, orders)
- Long-running workflows (days to years)
- Complex failure handling with compensations
- High throughput (>10K workflows/second)
- Microservice orchestration
- When you need exactly-once semantics

---

## Core Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         TEMPORAL CLUSTER                                      │
│                                                                              │
│  ┌─────────────────┐    ┌──────────────────┐    ┌─────────────────────┐    │
│  │  Frontend        │    │  History Service  │    │  Matching Service   │    │
│  │  Service         │    │                  │    │                     │    │
│  │  ┌────────────┐ │    │  ┌────────────┐  │    │  ┌───────────────┐ │    │
│  │  │ gRPC API   │ │    │  │ Shard 1    │  │    │  │ Task Queue A  │ │    │
│  │  │ Rate Limit │ │    │  │ Shard 2    │  │    │  │ Task Queue B  │ │    │
│  │  │ Auth/TLS   │ │    │  │ ...        │  │    │  │ Task Queue C  │ │    │
│  │  │ Routing    │ │    │  │ Shard N    │  │    │  │ ...           │ │    │
│  │  └────────────┘ │    │  └────────────┘  │    │  └───────────────┘ │    │
│  └────────┬────────┘    └────────┬─────────┘    └──────────┬──────────┘    │
│           │                      │                          │               │
│  ┌────────┴──────────────────────┴──────────────────────────┴────────────┐  │
│  │                     Internal Ring (Ringpop/Membership)                 │  │
│  └───────────────────────────────┬───────────────────────────────────────┘  │
│                                  │                                           │
│  ┌───────────────────────────────┴───────────────────────────────────────┐  │
│  │                        Persistence Layer                               │  │
│  │                                                                        │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌─────────────────────────────┐ │  │
│  │  │ Cassandra/   │  │ Visibility   │  │ Advanced Visibility          │ │  │
│  │  │ MySQL/       │  │ Store        │  │ (Elasticsearch/OpenSearch)   │ │  │
│  │  │ PostgreSQL   │  │              │  │                              │ │  │
│  │  │              │  │              │  │ - Custom search attributes   │ │  │
│  │  │ - Executions │  │ - Basic list │  │ - Complex queries            │ │  │
│  │  │ - History    │  │ - Open/Close │  │ - Aggregations               │ │  │
│  │  │ - Tasks      │  │              │  │                              │ │  │
│  │  └──────────────┘  └──────────────┘  └─────────────────────────────┘ │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐  │
│  │  Internal Worker Service (system workflows: archival, replication)      │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
        │                              │                        │
        │ gRPC                         │ gRPC                   │ gRPC
        ▼                              ▼                        ▼
┌───────────────┐            ┌───────────────┐         ┌───────────────┐
│  Worker Pool  │            │  Worker Pool  │         │  Worker Pool  │
│  (Service A)  │            │  (Service B)  │         │  (Service C)  │
│               │            │               │         │               │
│ - Workflows   │            │ - Workflows   │         │ - Activities  │
│ - Activities  │            │ - Activities  │         │   only        │
│               │            │               │         │               │
│ Polls:        │            │ Polls:        │         │ Polls:        │
│  payment-tq   │            │  order-tq     │         │  heavy-tq     │
└───────────────┘            └───────────────┘         └───────────────┘
```

### Frontend Service

The **Frontend Service** is the gRPC gateway that all clients (workers, CLI, UI) connect to.

**Responsibilities:**
- gRPC API serving (StartWorkflowExecution, SignalWorkflow, QueryWorkflow, etc.)
- Rate limiting (per-namespace, per-API)
- Request validation and authorization
- Request routing to appropriate History shard
- TLS termination
- DC redirection for multi-cluster

**Key configuration:**
```yaml
frontend:
  rps: 2400                    # Max requests per second per instance
  namespaceRPS: 1200           # Max RPS per namespace
  maxBadBinaries: 10           # Binary checksum denylist size
  enableGRPCHealthCheck: true
  keepAliveTime: 30s
```

### History Service

The **History Service** is the brain of Temporal. It owns workflow execution state.

**Responsibilities:**
- Workflow state machine execution (event sourcing)
- Mutable state management (pending activities, timers, child workflows)
- Transfer/timer/replication task generation
- Sharding (workflows distributed across shards via hash ring)
- Event history persistence
- Workflow task scheduling

**Sharding model:**
```
WorkflowID → hash(namespaceID + workflowID) → shard number → History host

Default: 4096 shards distributed across History instances
Each shard owns ~N/4096 workflows (where N = total workflows)
```

### Matching Service

The **Matching Service** manages task queues and dispatches tasks to workers.

**Responsibilities:**
- Task queue management (workflow tasks + activity tasks)
- Task dispatch to polling workers (sync match or persistence)
- Load balancing across workers
- Task forwarding (partitioned task queues)
- Rate limiting task dispatch

**Sync match optimization:**
```
Worker polls → If task already waiting → Immediate dispatch (no DB write)
                                          ↓
                              Latency: ~1-5ms (sync match)
                              vs ~20-50ms (persistence path)
```

### Worker Service (Internal)

Runs internal system workflows:
- **Archival** - Moving completed workflow histories to blob storage
- **Replication** - Cross-cluster replication for multi-cluster
- **Batch operations** - Bulk signal, terminate, cancel
- **Scheduler** - Cron-like schedule execution

---

## Core Concepts with Go Code Examples

### 1. Workflows - Deterministic Durable Functions

A workflow is a **deterministic function** whose execution is durable. If the process crashes, the workflow replays from its event history and continues exactly where it left off.

```go
package workflows

import (
	"fmt"
	"time"

	"go.temporal.io/sdk/temporal"
	"go.temporal.io/sdk/workflow"
)

// TransferInput represents a money transfer request
type TransferInput struct {
	TransferID    string
	SourceAccount string
	DestAccount   string
	Amount        int64 // cents
	Currency      string
	IdempotencyKey string
}

// TransferResult represents the outcome
type TransferResult struct {
	TransferID     string
	Status         string
	DebitRef       string
	CreditRef      string
	CompletedAt    time.Time
}

// MoneyTransferWorkflow orchestrates a money transfer with saga compensation
func MoneyTransferWorkflow(ctx workflow.Context, input TransferInput) (*TransferResult, error) {
	logger := workflow.GetLogger(ctx)
	logger.Info("Starting money transfer", "transferID", input.TransferID, "amount", input.Amount)

	// Activity options with retry policy
	activityOpts := workflow.ActivityOptions{
		StartToCloseTimeout: 30 * time.Second,
		HeartbeatTimeout:    10 * time.Second,
		RetryPolicy: &temporal.RetryPolicy{
			InitialInterval:    time.Second,
			BackoffCoefficient: 2.0,
			MaximumInterval:    30 * time.Second,
			MaximumAttempts:    5,
			NonRetryableErrorTypes: []string{
				"InsufficientFundsError",
				"AccountClosedError",
				"InvalidAccountError",
			},
		},
	}
	ctx = workflow.WithActivityOptions(ctx, activityOpts)

	// Step 1: Validate accounts
	var validation ValidationResult
	err := workflow.ExecuteActivity(ctx, ValidateAccounts, input).Get(ctx, &validation)
	if err != nil {
		return nil, fmt.Errorf("validation failed: %w", err)
	}

	// Step 2: Debit source account
	var debitRef string
	err = workflow.ExecuteActivity(ctx, DebitAccount, DebitRequest{
		AccountID:      input.SourceAccount,
		Amount:         input.Amount,
		Currency:       input.Currency,
		IdempotencyKey: input.IdempotencyKey + "-debit",
	}).Get(ctx, &debitRef)
	if err != nil {
		return nil, fmt.Errorf("debit failed: %w", err)
	}

	// Step 3: Credit destination (with compensation on failure)
	var creditRef string
	err = workflow.ExecuteActivity(ctx, CreditAccount, CreditRequest{
		AccountID:      input.DestAccount,
		Amount:         input.Amount,
		Currency:       input.Currency,
		IdempotencyKey: input.IdempotencyKey + "-credit",
	}).Get(ctx, &creditRef)
	if err != nil {
		// COMPENSATE: Reverse the debit
		logger.Error("Credit failed, compensating debit", "error", err)
		compensateErr := workflow.ExecuteActivity(ctx, ReverseDebit, ReverseDebitRequest{
			OriginalRef:    debitRef,
			AccountID:      input.SourceAccount,
			Amount:         input.Amount,
			IdempotencyKey: input.IdempotencyKey + "-reverse",
		}).Get(ctx, nil)
		if compensateErr != nil {
			// Compensation failed - this needs human intervention
			logger.Error("CRITICAL: Compensation failed", "error", compensateErr)
			// Signal ops team, the workflow will remain open for manual resolution
			return nil, fmt.Errorf("compensation failed: credit=%w, reverse=%v", err, compensateErr)
		}
		return nil, fmt.Errorf("transfer failed, debit reversed: %w", err)
	}

	return &TransferResult{
		TransferID:  input.TransferID,
		Status:      "COMPLETED",
		DebitRef:    debitRef,
		CreditRef:   creditRef,
		CompletedAt: workflow.Now(ctx),
	}, nil
}
```

**Key rules:**
- Workflow code MUST be deterministic (same inputs → same outputs on replay)
- No direct I/O, network calls, or random number generation
- Use `workflow.Now(ctx)` instead of `time.Now()`
- Use `workflow.SideEffect()` for non-deterministic values
- Use activities for all side effects

### 2. Activities - Non-Deterministic Side Effects

Activities are where you perform actual work: HTTP calls, database operations, file I/O.

```go
package activities

import (
	"context"
	"fmt"
	"net/http"
	"time"

	"go.temporal.io/sdk/activity"
	"go.temporal.io/sdk/temporal"
)

type PaymentActivities struct {
	bankClient   BankAPIClient
	ledgerDB     *sql.DB
	httpClient   *http.Client
}

func NewPaymentActivities(bankClient BankAPIClient, db *sql.DB) *PaymentActivities {
	return &PaymentActivities{
		bankClient: bankClient,
		ledgerDB:   db,
		httpClient: &http.Client{Timeout: 10 * time.Second},
	}
}

// DebitAccount performs the actual bank debit via API
func (a *PaymentActivities) DebitAccount(ctx context.Context, req DebitRequest) (string, error) {
	logger := activity.GetLogger(ctx)
	info := activity.GetInfo(ctx)

	logger.Info("Debiting account",
		"accountID", req.AccountID,
		"amount", req.Amount,
		"attempt", info.Attempt,
		"idempotencyKey", req.IdempotencyKey,
	)

	// Heartbeat for long-running operations
	activity.RecordHeartbeat(ctx, "initiating_debit")

	// Call bank API with idempotency key
	resp, err := a.bankClient.Debit(ctx, BankDebitRequest{
		AccountID:      req.AccountID,
		AmountCents:    req.Amount,
		Currency:       req.Currency,
		IdempotencyKey: req.IdempotencyKey,
		RequestID:      fmt.Sprintf("%s-%d", info.WorkflowExecution.ID, info.Attempt),
	})
	if err != nil {
		// Classify errors for retry policy
		if isInsufficientFunds(err) {
			return "", temporal.NewNonRetryableApplicationError(
				"insufficient funds",
				"InsufficientFundsError",
				err,
				req.AccountID,
			)
		}
		if isTransient(err) {
			return "", fmt.Errorf("transient bank error: %w", err) // Will be retried
		}
		return "", temporal.NewNonRetryableApplicationError(
			"permanent bank error",
			"BankPermanentError",
			err,
		)
	}

	activity.RecordHeartbeat(ctx, "debit_completed")
	return resp.ReferenceID, nil
}

// CreditAccount performs the actual bank credit
func (a *PaymentActivities) CreditAccount(ctx context.Context, req CreditRequest) (string, error) {
	activity.RecordHeartbeat(ctx, "initiating_credit")

	resp, err := a.bankClient.Credit(ctx, BankCreditRequest{
		AccountID:      req.AccountID,
		AmountCents:    req.Amount,
		Currency:       req.Currency,
		IdempotencyKey: req.IdempotencyKey,
	})
	if err != nil {
		return "", fmt.Errorf("credit failed: %w", err)
	}

	return resp.ReferenceID, nil
}
```

### 3. Workers - Poll Task Queues, Execute Code

```go
package main

import (
	"log"
	"os"
	"os/signal"
	"syscall"

	"go.temporal.io/sdk/client"
	"go.temporal.io/sdk/worker"
	"go.temporal.io/sdk/workflow"
)

func main() {
	// Create Temporal client
	c, err := client.Dial(client.Options{
		HostPort:  os.Getenv("TEMPORAL_HOST"),
		Namespace: "payments-prod",
		// mTLS for production
		ConnectionOptions: client.ConnectionOptions{
			TLS: loadTLSConfig(),
		},
	})
	if err != nil {
		log.Fatalf("Failed to create Temporal client: %v", err)
	}
	defer c.Close()

	// Create worker
	w := worker.New(c, "payment-processing-tq", worker.Options{
		MaxConcurrentWorkflowTaskPollers:  5,
		MaxConcurrentActivityTaskPollers:  10,
		MaxConcurrentWorkflowTaskExecutionSize: 200,
		MaxConcurrentActivityExecutionSize:     50,
		WorkerStopTimeout:                      30 * time.Second,
		// Sticky workflow cache for faster replay
		StickyScheduleToStartTimeout: 5 * time.Second,
		// Enable session for ordered activities
		EnableSessionWorker: true,
	})

	// Register workflows
	w.RegisterWorkflow(MoneyTransferWorkflow)
	w.RegisterWorkflow(BatchTransferWorkflow)

	// Register activities
	activities := NewPaymentActivities(bankClient, db)
	w.RegisterActivity(activities)

	// Graceful shutdown
	sigCh := make(chan os.Signal, 1)
	signal.Notify(sigCh, syscall.SIGINT, syscall.SIGTERM)

	go func() {
		<-sigCh
		log.Println("Shutting down worker gracefully...")
		w.Stop()
	}()

	// Start worker (blocks until stopped)
	err = w.Run(worker.InterruptCh())
	if err != nil {
		log.Fatalf("Worker failed: %v", err)
	}
}
```

### 4. Task Queues - Named Queues for Routing

```go
// Task queues allow routing work to specific worker pools
const (
	PaymentTaskQueue    = "payment-processing-tq"
	HighPriorityTQ      = "payment-priority-tq"
	NotificationTQ      = "notification-tq"
	HeavyComputeTQ      = "heavy-compute-tq"
)

// Route activities to different task queues
func OrderWorkflow(ctx workflow.Context, order Order) error {
	// Payment activities go to payment workers
	paymentCtx := workflow.WithActivityOptions(ctx, workflow.ActivityOptions{
		TaskQueue:           PaymentTaskQueue,
		StartToCloseTimeout: 30 * time.Second,
	})
	err := workflow.ExecuteActivity(paymentCtx, ChargeCustomer, order).Get(ctx, nil)
	if err != nil {
		return err
	}

	// Heavy compute goes to GPU workers
	computeCtx := workflow.WithActivityOptions(ctx, workflow.ActivityOptions{
		TaskQueue:           HeavyComputeTQ,
		StartToCloseTimeout: 5 * time.Minute,
	})
	err = workflow.ExecuteActivity(computeCtx, GenerateInvoicePDF, order).Get(ctx, nil)
	if err != nil {
		return err
	}

	return nil
}
```

### 5. Signals - Async External Events

```go
// Signals allow sending data to a running workflow from outside
func LongRunningOrderWorkflow(ctx workflow.Context, order Order) error {
	logger := workflow.GetLogger(ctx)

	// Define signal channels
	cancelCh := workflow.GetSignalChannel(ctx, "cancel-order")
	modifyCh := workflow.GetSignalChannel(ctx, "modify-order")
	statusUpdateCh := workflow.GetSignalChannel(ctx, "status-update")

	// Process order with signal handling
	orderState := NewOrderState(order)

	for !orderState.IsTerminal() {
		// Use selector to wait for multiple events
		selector := workflow.NewSelector(ctx)

		// Handle cancellation signal
		selector.AddReceive(cancelCh, func(ch workflow.ReceiveChannel, more bool) {
			var reason string
			ch.Receive(ctx, &reason)
			logger.Info("Order cancelled", "reason", reason)
			orderState.Cancel(reason)
		})

		// Handle modification signal
		selector.AddReceive(modifyCh, func(ch workflow.ReceiveChannel, more bool) {
			var modification OrderModification
			ch.Receive(ctx, &modification)
			logger.Info("Order modified", "modification", modification)
			orderState.Modify(modification)
		})

		// Handle status updates from child workflows
		selector.AddReceive(statusUpdateCh, func(ch workflow.ReceiveChannel, more bool) {
			var update StatusUpdate
			ch.Receive(ctx, &update)
			orderState.UpdateStatus(update)
		})

		// Timeout - check if order is stale
		selector.AddReceive(workflow.NewTimer(ctx, 24*time.Hour), func(f workflow.Future) {
			logger.Warn("Order idle for 24 hours, checking status")
		})

		selector.Select(ctx)
	}

	return nil
}

// Sending a signal from external code (e.g., API handler)
func HandleCancelRequest(c client.Client, workflowID string, reason string) error {
	return c.SignalWorkflow(context.Background(), workflowID, "", "cancel-order", reason)
}
```

### 6. Queries - Synchronous Read-Only Inspection

```go
func OrderWorkflowWithQuery(ctx workflow.Context, order Order) error {
	state := &OrderState{
		OrderID: order.ID,
		Status:  "PENDING",
		Items:   order.Items,
	}

	// Register query handler - must be read-only, no side effects
	err := workflow.SetQueryHandler(ctx, "get-order-status", func() (*OrderState, error) {
		return state, nil
	})
	if err != nil {
		return err
	}

	err = workflow.SetQueryHandler(ctx, "get-shipment-info", func(itemID string) (*ShipmentInfo, error) {
		info, ok := state.Shipments[itemID]
		if !ok {
			return nil, fmt.Errorf("no shipment for item %s", itemID)
		}
		return info, nil
	})
	if err != nil {
		return err
	}

	// ... workflow logic that updates state ...
	state.Status = "PROCESSING"
	// ... more logic ...

	return nil
}

// Querying from external code
func GetOrderStatus(c client.Client, workflowID string) (*OrderState, error) {
	resp, err := c.QueryWorkflow(context.Background(), workflowID, "", "get-order-status")
	if err != nil {
		return nil, err
	}
	var state OrderState
	err = resp.Get(&state)
	return &state, err
}
```

### 7. Updates - Synchronous Mutations (New)

```go
// Updates combine signals (mutation) with queries (synchronous response)
func WorkflowWithUpdates(ctx workflow.Context, input Input) error {
	state := &WorkflowState{Balance: 1000}

	// Register update handler with validator
	err := workflow.SetUpdateHandlerWithOptions(ctx, "withdraw",
		func(ctx workflow.Context, amount int64) (int64, error) {
			state.Balance -= amount
			// Can execute activities inside update handler
			err := workflow.ExecuteActivity(ctx, RecordTransaction, amount).Get(ctx, nil)
			if err != nil {
				state.Balance += amount // rollback
				return 0, err
			}
			return state.Balance, nil
		},
		workflow.UpdateHandlerOptions{
			Validator: func(ctx workflow.Context, amount int64) error {
				if amount <= 0 {
					return fmt.Errorf("amount must be positive")
				}
				if amount > state.Balance {
					return fmt.Errorf("insufficient balance: have %d, want %d", state.Balance, amount)
				}
				return nil
			},
		},
	)
	if err != nil {
		return err
	}

	// Block workflow until done signal
	workflow.GetSignalChannel(ctx, "done").Receive(ctx, nil)
	return nil
}

// Calling update from external code - synchronous!
func WithdrawFromWorkflow(c client.Client, workflowID string, amount int64) (int64, error) {
	handle, err := c.UpdateWorkflow(context.Background(), client.UpdateWorkflowOptions{
		WorkflowID:   workflowID,
		UpdateName:   "withdraw",
		Args:         []interface{}{amount},
		WaitForStage: client.WorkflowUpdateStageCompleted,
	})
	if err != nil {
		return 0, err
	}
	var newBalance int64
	err = handle.Get(context.Background(), &newBalance)
	return newBalance, err
}
```

### 8. Child Workflows - Decomposition

```go
func ParentWorkflow(ctx workflow.Context, input ParentInput) error {
	// Child workflow options
	childOpts := workflow.ChildWorkflowOptions{
		WorkflowID:            fmt.Sprintf("child-%s-%s", input.ID, "payment"),
		TaskQueue:             "payment-tq",
		WorkflowRunTimeout:    5 * time.Minute,
		ParentClosePolicy:     enums.PARENT_CLOSE_POLICY_TERMINATE,
		WorkflowIDReusePolicy: enums.WORKFLOW_ID_REUSE_POLICY_ALLOW_DUPLICATE_FAILED_ONLY,
		RetryPolicy: &temporal.RetryPolicy{
			MaximumAttempts: 3,
		},
	}
	childCtx := workflow.WithChildOptions(ctx, childOpts)

	// Start child workflow
	future := workflow.ExecuteChildWorkflow(childCtx, PaymentWorkflow, PaymentInput{
		OrderID: input.ID,
		Amount:  input.Total,
	})

	// Can do other work while child runs...
	// ...

	// Wait for child result
	var paymentResult PaymentResult
	err := future.Get(ctx, &paymentResult)
	if err != nil {
		return fmt.Errorf("payment child failed: %w", err)
	}

	return nil
}

// Fan-out pattern: multiple children in parallel
func FanOutWorkflow(ctx workflow.Context, items []Item) ([]Result, error) {
	var futures []workflow.ChildWorkflowFuture
	for _, item := range items {
		childCtx := workflow.WithChildOptions(ctx, workflow.ChildWorkflowOptions{
			WorkflowID: fmt.Sprintf("process-item-%s", item.ID),
		})
		future := workflow.ExecuteChildWorkflow(childCtx, ProcessItemWorkflow, item)
		futures = append(futures, future)
	}

	// Collect results
	results := make([]Result, len(items))
	for i, future := range futures {
		err := future.Get(ctx, &results[i])
		if err != nil {
			return nil, fmt.Errorf("item %d failed: %w", i, err)
		}
	}
	return results, nil
}
```

### 9. Continue-As-New - Prevent Unbounded History

```go
// For long-running workflows (subscriptions, monitoring), use continue-as-new
// to prevent history from growing unboundedly (limit: 50K events / 50MB)
func SubscriptionWorkflow(ctx workflow.Context, state SubscriptionState) error {
	logger := workflow.GetLogger(ctx)

	// Register query handler
	workflow.SetQueryHandler(ctx, "get-state", func() (*SubscriptionState, error) {
		return &state, nil
	})

	// Process one billing cycle
	signalCh := workflow.GetSignalChannel(ctx, "subscription-event")
	timerFuture := workflow.NewTimer(ctx, state.NextBillingIn())

	selector := workflow.NewSelector(ctx)

	selector.AddFuture(timerFuture, func(f workflow.Future) {
		// Time to bill
		err := workflow.ExecuteActivity(ctx, ProcessBilling, state).Get(ctx, nil)
		if err != nil {
			logger.Error("Billing failed", "error", err)
			state.FailedAttempts++
		} else {
			state.LastBilledAt = workflow.Now(ctx)
			state.BillingCycle++
		}
	})

	selector.AddReceive(signalCh, func(ch workflow.ReceiveChannel, more bool) {
		var event SubscriptionEvent
		ch.Receive(ctx, &event)
		state.ApplyEvent(event)
	})

	selector.Select(ctx)

	// Check if we should continue-as-new (e.g., every 1000 events)
	info := workflow.GetInfo(ctx)
	if info.GetCurrentHistoryLength() > 1000 {
		logger.Info("Continuing as new to reset history",
			"historyLength", info.GetCurrentHistoryLength(),
			"billingCycle", state.BillingCycle,
		)
		return workflow.NewContinueAsNewError(ctx, SubscriptionWorkflow, state)
	}

	// Otherwise, keep processing in same execution
	return workflow.NewContinueAsNewError(ctx, SubscriptionWorkflow, state)
}
```

### 10. Timers & Sleep - Durable Timers

```go
func ReminderWorkflow(ctx workflow.Context, userID string) error {
	// This sleep survives process restarts, deployments, everything
	// It's stored as a timer event in history
	err := workflow.Sleep(ctx, 7*24*time.Hour) // Sleep for 7 days
	if err != nil {
		return err // Cancelled
	}

	// Send reminder after 7 days
	return workflow.ExecuteActivity(ctx, SendReminder, userID).Get(ctx, nil)
}

// Timer with cancellation
func TimeoutPatternWorkflow(ctx workflow.Context, input Input) error {
	// Create a timer
	timerCtx, cancelTimer := workflow.WithCancel(ctx)
	timerFuture := workflow.NewTimer(timerCtx, 30*time.Minute)

	// Start the actual work
	actFuture := workflow.ExecuteActivity(ctx, DoWork, input)

	// Race: work vs timeout
	selector := workflow.NewSelector(ctx)

	var result Result
	selector.AddFuture(actFuture, func(f workflow.Future) {
		cancelTimer() // Cancel the timer since work completed
		f.Get(ctx, &result)
	})

	selector.AddFuture(timerFuture, func(f workflow.Future) {
		// Timeout reached
		result.TimedOut = true
	})

	selector.Select(ctx)

	if result.TimedOut {
		return fmt.Errorf("operation timed out after 30 minutes")
	}
	return nil
}
```

### 11. Side Effects - Non-Deterministic Values

```go
func WorkflowWithSideEffects(ctx workflow.Context) error {
	// Generate UUID deterministically (recorded in history, replayed on recovery)
	var requestID string
	encodedID := workflow.SideEffect(ctx, func(ctx workflow.Context) interface{} {
		return uuid.New().String()
	})
	err := encodedID.Get(&requestID)
	if err != nil {
		return err
	}

	// Use requestID in activities - will be same value on replay
	return workflow.ExecuteActivity(ctx, DoSomething, requestID).Get(ctx, nil)
}
```

### 12. Local Activities - Short Activities Without Full Persistence

```go
func WorkflowWithLocalActivity(ctx workflow.Context, input Input) error {
	// Local activities run in the workflow worker process
	// Faster but: no independent retry, no heartbeat, no separate task queue
	// Use for: quick validations, local cache lookups, simple transformations
	localCtx := workflow.WithLocalActivityOptions(ctx, workflow.LocalActivityOptions{
		ScheduleToCloseTimeout: 5 * time.Second,
		RetryPolicy: &temporal.RetryPolicy{
			MaximumAttempts: 3,
		},
	})

	var validationResult ValidationResult
	err := workflow.ExecuteLocalActivity(localCtx, ValidateInput, input).Get(ctx, &validationResult)
	if err != nil {
		return err
	}

	// Continue with normal activities for actual I/O
	return workflow.ExecuteActivity(ctx, ProcessInput, validationResult).Get(ctx, nil)
}
```

### 13. Heartbeating - Progress Reporting

```go
// Long-running activity that processes a large file
func ProcessLargeFile(ctx context.Context, filePath string) error {
	file, err := os.Open(filePath)
	if err != nil {
		return err
	}
	defer file.Close()

	scanner := bufio.NewScanner(file)
	lineCount := 0

	for scanner.Scan() {
		lineCount++
		// Process line...

		// Heartbeat every 100 lines with progress
		if lineCount%100 == 0 {
			activity.RecordHeartbeat(ctx, HeartbeatProgress{
				LinesProcessed: lineCount,
				LastLine:        scanner.Text(),
			})

			// Check if cancelled
			if ctx.Err() != nil {
				return ctx.Err()
			}
		}
	}

	return scanner.Err()
}

// On retry after crash, get last heartbeat details to resume
func ProcessLargeFileResumable(ctx context.Context, filePath string) error {
	// Check if we have heartbeat details from a previous attempt
	if activity.HasHeartbeatDetails(ctx) {
		var progress HeartbeatProgress
		if err := activity.GetHeartbeatDetails(ctx, &progress); err == nil {
			// Resume from where we left off
			return processFromLine(ctx, filePath, progress.LinesProcessed)
		}
	}
	// Start from beginning
	return processFromLine(ctx, filePath, 0)
}
```

### 14. Retry Policies

```go
// Different retry policies for different activity types
var (
	// For idempotent network calls
	NetworkRetryPolicy = &temporal.RetryPolicy{
		InitialInterval:        time.Second,
		BackoffCoefficient:     2.0,
		MaximumInterval:        time.Minute,
		MaximumAttempts:        10,
		NonRetryableErrorTypes: []string{"InvalidInputError", "AuthenticationError"},
	}

	// For database operations
	DBRetryPolicy = &temporal.RetryPolicy{
		InitialInterval:    100 * time.Millisecond,
		BackoffCoefficient: 1.5,
		MaximumInterval:    5 * time.Second,
		MaximumAttempts:    5,
	}

	// For external partner APIs (more patient)
	PartnerAPIRetryPolicy = &temporal.RetryPolicy{
		InitialInterval:    5 * time.Second,
		BackoffCoefficient: 3.0,
		MaximumInterval:    5 * time.Minute,
		MaximumAttempts:    20,
	}

	// No retry - for non-idempotent operations
	NoRetryPolicy = &temporal.RetryPolicy{
		MaximumAttempts: 1,
	}
)
```

### 15. Timeouts

```go
// Four timeout types - understand them all
func WorkflowWithTimeouts(ctx workflow.Context) error {
	ctx = workflow.WithActivityOptions(ctx, workflow.ActivityOptions{
		// Schedule-to-Start: max time task sits in queue waiting for a worker
		// Detects: no workers available, worker pool too small
		ScheduleToStartTimeout: 10 * time.Second,

		// Start-to-Close: max time for a single attempt of the activity
		// Detects: activity hanging, slow external service
		StartToCloseTimeout: 30 * time.Second,

		// Schedule-to-Close: max total time including all retries
		// Detects: overall SLA breach, all retries exhausted
		ScheduleToCloseTimeout: 5 * time.Minute,

		// Heartbeat: max time between heartbeat calls
		// Detects: activity worker crashed mid-execution
		HeartbeatTimeout: 10 * time.Second,

		RetryPolicy: &temporal.RetryPolicy{
			MaximumAttempts: 5,
		},
	})

	return workflow.ExecuteActivity(ctx, MyActivity, input).Get(ctx, nil)
}

/*
Timeline visualization:
                                                     ScheduleToClose (5m)
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ScheduleToStart (10s)   StartToClose (30s)                                 │
│  ├────────────────────┤  ├───────────────────────────────┤                  │
│  │ In queue waiting   │  │ Activity executing            │                  │
│  │ for worker         │  │                               │                  │
│  └────────────────────┘  │  HB    HB    HB    HB        │                  │
│                          │  ├──┤  ├──┤  ├──┤  ├──┤      │  (retry)...      │
│                          │  10s   10s   10s   10s        │                  │
│                          └───────────────────────────────┘                  │
└──────────────────────────────────────────────────────────────────────────────┘
*/
```

### 16. Cancellation - Cooperative Propagation

```go
func CancellableWorkflow(ctx workflow.Context, input Input) error {
	// Cleanup on cancellation
	defer func() {
		if ctx.Err() != nil {
			// Use disconnected context for cleanup (won't be cancelled)
			cleanupCtx, _ := workflow.NewDisconnectedContext(ctx)
			cleanupCtx = workflow.WithActivityOptions(cleanupCtx, workflow.ActivityOptions{
				StartToCloseTimeout: 30 * time.Second,
			})
			workflow.ExecuteActivity(cleanupCtx, CleanupResources, input).Get(cleanupCtx, nil)
		}
	}()

	// This activity will receive cancellation
	err := workflow.ExecuteActivity(ctx, LongRunningProcess, input).Get(ctx, nil)
	if err != nil {
		if temporal.IsCanceledError(err) {
			// Workflow was cancelled
			return err
		}
		return fmt.Errorf("activity failed: %w", err)
	}
	return nil
}
```

### 17. Namespaces - Multi-Tenancy

```go
// Production namespace strategy
// Namespace per environment + domain:
//   payments-prod, payments-staging, payments-dev
//   orders-prod, orders-staging, orders-dev

// Create client for specific namespace
func createClient(namespace string) (client.Client, error) {
	return client.Dial(client.Options{
		HostPort:  "temporal.internal:7233",
		Namespace: namespace,
		// Namespace-specific metrics
		MetricsHandler: newMetricsHandler(namespace),
	})
}
```

### 18. Search Attributes - Custom Queryable Metadata

```go
func WorkflowWithSearchAttributes(ctx workflow.Context, order Order) error {
	// Set search attributes at workflow start (or via UpsertSearchAttributes)
	err := workflow.UpsertSearchAttributes(ctx, map[string]interface{}{
		"CustomerId":    order.CustomerID,
		"OrderAmount":   order.TotalCents,
		"OrderStatus":   "PROCESSING",
		"Region":        order.Region,
		"PaymentMethod": order.PaymentMethod,
		"IsVIP":         order.IsVIP,
	})
	if err != nil {
		return err
	}

	// ... process order ...

	// Update as status changes
	workflow.UpsertSearchAttributes(ctx, map[string]interface{}{
		"OrderStatus": "SHIPPED",
	})

	return nil
}

// Query workflows using search attributes (SQL-like syntax)
// "CustomerId = 'cust-123' AND OrderStatus = 'PROCESSING' AND OrderAmount > 10000"
// "Region = 'us-east-1' AND IsVIP = true ORDER BY OrderAmount DESC"
```

### 19. Interceptors - Cross-Cutting Concerns

```go
// Interceptor for logging, metrics, and tracing on every workflow/activity
type MetricsInterceptor struct {
	interceptor.WorkerInterceptorBase
	metricsClient metrics.Client
}

func (i *MetricsInterceptor) InterceptActivity(
	ctx context.Context,
	next interceptor.ActivityInboundInterceptor,
) interceptor.ActivityInboundInterceptor {
	return &activityMetricsInterceptor{
		ActivityInboundInterceptorBase: interceptor.ActivityInboundInterceptorBase{Next: next},
		metricsClient:                  i.metricsClient,
	}
}

type activityMetricsInterceptor struct {
	interceptor.ActivityInboundInterceptorBase
	metricsClient metrics.Client
}

func (i *activityMetricsInterceptor) Execute(
	ctx context.Context,
	input *interceptor.ExecuteActivityInput,
) (interface{}, error) {
	start := time.Now()
	activityType := activity.GetInfo(ctx).ActivityType.Name

	result, err := i.Next.Execute(ctx, input)

	duration := time.Since(start)
	i.metricsClient.RecordTimer("activity_execution_duration", duration,
		metrics.Tag("activity_type", activityType),
		metrics.Tag("success", fmt.Sprintf("%t", err == nil)),
	)

	if err != nil {
		i.metricsClient.IncCounter("activity_execution_failed",
			metrics.Tag("activity_type", activityType),
		)
	}

	return result, err
}

// Register interceptor with worker
func createWorkerWithInterceptor(c client.Client) worker.Worker {
	w := worker.New(c, "my-task-queue", worker.Options{
		Interceptors: []interceptor.WorkerInterceptor{
			&MetricsInterceptor{metricsClient: statsClient},
		},
	})
	return w
}
```

### 20. Schedules - Cron-Like Scheduling

```go
// Create a schedule (replaces old cron workflows)
func createSchedule(c client.Client) error {
	handle, err := c.ScheduleClient().Create(context.Background(), client.ScheduleOptions{
		ID: "daily-report-schedule",
		Spec: client.ScheduleSpec{
			CronExpressions: []string{"0 9 * * MON-FRI"}, // 9am weekdays
			// Or use structured intervals:
			// Intervals: []client.ScheduleIntervalSpec{
			//     {Every: 1 * time.Hour},
			// },
		},
		Action: &client.ScheduleWorkflowAction{
			ID:        "daily-report",
			Workflow:  DailyReportWorkflow,
			TaskQueue: "reports-tq",
			Args:      []interface{}{ReportInput{Type: "daily"}},
		},
		Overlap: enums.SCHEDULE_OVERLAP_POLICY_SKIP, // Skip if previous still running
		// Other policies: BUFFER_ONE, BUFFER_ALL, CANCEL_OTHER, TERMINATE_OTHER
	})
	if err != nil {
		return err
	}
	_ = handle
	return nil
}
```

### 21. Versioning - Workflow Code Evolution

```go
// Strategy 1: GetVersion (patch-based)
func MyWorkflow(ctx workflow.Context, input Input) error {
	// v1 behavior
	v := workflow.GetVersion(ctx, "add-notification-step", workflow.DefaultVersion, 1)

	err := workflow.ExecuteActivity(ctx, ProcessData, input).Get(ctx, nil)
	if err != nil {
		return err
	}

	if v == 1 {
		// New step added in v1 - old workflows skip this
		err = workflow.ExecuteActivity(ctx, SendNotification, input).Get(ctx, nil)
		if err != nil {
			return err
		}
	}

	return nil
}

// Strategy 2: Worker Versioning (Build ID based) - recommended for new code
// Register worker with build ID
func createVersionedWorker(c client.Client) worker.Worker {
	w := worker.New(c, "my-task-queue", worker.Options{
		BuildID:                 "v2.3.1",
		UseBuildIDForVersioning: true,
	})
	return w
}
```

### 22. Visibility - Listing/Searching Workflows

```go
// List workflows with filters
func listFailedPayments(c client.Client) error {
	iter, err := c.ListWorkflow(context.Background(), &workflowservice.ListWorkflowExecutionsRequest{
		Namespace: "payments-prod",
		Query:     `WorkflowType = "MoneyTransferWorkflow" AND ExecutionStatus = "Failed" AND CloseTime > "2024-01-01"`,
	})

	for iter.HasNext() {
		exec, err := iter.Next()
		if err != nil {
			return err
		}
		fmt.Printf("Failed: %s (started: %v)\n",
			exec.Execution.WorkflowId,
			exec.StartTime,
		)
	}
	return nil
}
```

### 23. Data Converters - Custom Serialization/Encryption

```go
// Encrypt all workflow data at rest
type EncryptionCodec struct {
	key []byte
}

func (c *EncryptionCodec) Encode(payloads []*commonpb.Payload) ([]*commonpb.Payload, error) {
	result := make([]*commonpb.Payload, len(payloads))
	for i, p := range payloads {
		encrypted, err := encrypt(c.key, p.Data)
		if err != nil {
			return nil, err
		}
		result[i] = &commonpb.Payload{
			Metadata: map[string][]byte{
				"encoding": []byte("binary/encrypted"),
			},
			Data: encrypted,
		}
	}
	return result, nil
}

func (c *EncryptionCodec) Decode(payloads []*commonpb.Payload) ([]*commonpb.Payload, error) {
	result := make([]*commonpb.Payload, len(payloads))
	for i, p := range payloads {
		decrypted, err := decrypt(c.key, p.Data)
		if err != nil {
			return nil, err
		}
		result[i] = &commonpb.Payload{
			Metadata: map[string][]byte{
				"encoding": []byte("binary/plain"),
			},
			Data: decrypted,
		}
	}
	return result, nil
}

// Use with client
func createEncryptedClient() (client.Client, error) {
	return client.Dial(client.Options{
		HostPort:  "temporal:7233",
		Namespace: "secure-ns",
		DataConverter: converter.NewCodecDataConverter(
			converter.GetDefaultDataConverter(),
			&EncryptionCodec{key: loadEncryptionKey()},
		),
	})
}
```

---

## Event Sourcing Model

### How Temporal Stores State

Temporal does NOT store current workflow state. It stores the **complete history of events** and rebuilds state by replaying them.

```
Event History for workflow "transfer-123":
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Event# │ Type                           │ Details
━━━━━━━┼━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┼━━━━━━━━━━━━━━━━━━━━━━━━━━━
1      │ WorkflowExecutionStarted       │ input={amount: 5000, ...}
2      │ WorkflowTaskScheduled          │ taskQueue="payment-tq"
3      │ WorkflowTaskStarted            │ worker="worker-01"
4      │ WorkflowTaskCompleted          │ commands=[ScheduleActivity]
5      │ ActivityTaskScheduled          │ activityType="ValidateAccounts"
6      │ ActivityTaskStarted            │ worker="worker-02"
7      │ ActivityTaskCompleted          │ result={valid: true}
8      │ WorkflowTaskScheduled          │
9      │ WorkflowTaskStarted            │
10     │ WorkflowTaskCompleted          │ commands=[ScheduleActivity]
11     │ ActivityTaskScheduled          │ activityType="DebitAccount"
12     │ ActivityTaskStarted            │
13     │ ActivityTaskCompleted          │ result={ref: "dbt-789"}
14     │ WorkflowTaskScheduled          │
15     │ WorkflowTaskStarted            │
16     │ WorkflowTaskCompleted          │ commands=[ScheduleActivity]
17     │ ActivityTaskScheduled          │ activityType="CreditAccount"
18     │ ActivityTaskStarted            │
19     │ ActivityTaskCompleted          │ result={ref: "crd-456"}
20     │ WorkflowTaskScheduled          │
21     │ WorkflowTaskStarted            │
22     │ WorkflowTaskCompleted          │ commands=[CompleteWorkflow]
23     │ WorkflowExecutionCompleted     │ result={status: "COMPLETED"}
━━━━━━━┼━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┼━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### Replay Mechanism

When a workflow needs to resume (worker crash, new workflow task):
1. Load full event history from persistence
2. Re-execute workflow code from the beginning
3. Instead of executing activities again, return recorded results from history
4. When replay catches up to last recorded event, switch to live execution

```
Replay:
  Code: result = ExecuteActivity(Validate)  → History says: result={valid: true} ✓
  Code: result = ExecuteActivity(Debit)     → History says: result={ref: "dbt-789"} ✓
  Code: result = ExecuteActivity(Credit)    → No history! Execute for real now.
```

### History Limits

| Limit | Value | Mitigation |
|-------|-------|------------|
| Max events | 50,000 | Continue-as-new |
| Max history size | 50 MB | Continue-as-new, smaller payloads |
| Warning threshold | 10,000 events | Monitor, plan CAN |
| Recommended CAN trigger | 1,000-5,000 events | Depends on payload sizes |

---

## Determinism Rules

### What You CAN'T Do in Workflow Code

```go
// ❌ FORBIDDEN in workflows:
time.Now()                    // Use workflow.Now(ctx)
time.Sleep(d)                 // Use workflow.Sleep(ctx, d)
rand.Intn(n)                  // Use workflow.SideEffect()
uuid.New()                    // Use workflow.SideEffect()
http.Get(url)                 // Use activities
db.Query(sql)                 // Use activities
os.Getenv("VAR")              // Use activities or workflow input
go func() {}()                // Use workflow.Go(ctx, func(ctx))
select {}                     // Use workflow.NewSelector(ctx)
sync.Mutex{}                  // Use workflow.Mutex (if needed)
map iteration (non-det order) // Sort keys first or use slices
```

### Common Non-Determinism Bugs

```go
// BUG 1: Map iteration order
func BadWorkflow(ctx workflow.Context, items map[string]Item) error {
	for k, v := range items { // ❌ Order may differ on replay!
		workflow.ExecuteActivity(ctx, Process, k, v).Get(ctx, nil)
	}
	return nil
}
// FIX: Sort keys
func GoodWorkflow(ctx workflow.Context, items map[string]Item) error {
	keys := make([]string, 0, len(items))
	for k := range items { keys = append(keys, k) }
	sort.Strings(keys)
	for _, k := range keys {
		workflow.ExecuteActivity(ctx, Process, k, items[k]).Get(ctx, nil)
	}
	return nil
}

// BUG 2: Goroutines
func BadWorkflow2(ctx workflow.Context) error {
	go func() { /* ❌ */ }()
	return nil
}
// FIX: Use workflow.Go
func GoodWorkflow2(ctx workflow.Context) error {
	workflow.Go(ctx, func(gCtx workflow.Context) {
		// Safe concurrent execution within workflow
	})
	return nil
}
```

---

## Production Topology

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        PRODUCTION DEPLOYMENT                             │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  Region: us-east-1                    Region: eu-west-1                 │
│  ┌──────────────────────┐             ┌──────────────────────┐          │
│  │  Temporal Cluster     │◄───────────►│  Temporal Cluster     │         │
│  │  (Primary)            │ Replication │  (Standby)            │         │
│  │                       │             │                       │         │
│  │  Frontend: 3 pods     │             │  Frontend: 3 pods     │         │
│  │  History:  6 pods     │             │  History:  6 pods     │         │
│  │  Matching: 3 pods     │             │  Matching: 3 pods     │         │
│  │  Worker:   2 pods     │             │  Worker:   2 pods     │         │
│  └───────────┬───────────┘             └───────────┬───────────┘         │
│              │                                      │                    │
│  ┌───────────┴───────────┐             ┌───────────┴───────────┐        │
│  │  Cassandra (3-node)   │             │  Cassandra (3-node)   │        │
│  │  Elasticsearch (3)    │             │  Elasticsearch (3)    │        │
│  └───────────────────────┘             └───────────────────────┘        │
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │  Worker Fleets                                                    │   │
│  │                                                                   │   │
│  │  Payment Workers:    20 pods (8 CPU, 16GB each)                  │   │
│  │  Order Workers:      15 pods (4 CPU, 8GB each)                   │   │
│  │  Notification Workers: 10 pods (2 CPU, 4GB each)                 │   │
│  │  Heavy Compute:       5 pods (16 CPU, 32GB each)                 │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### Resource Requirements

| Component | CPU | Memory | Instances | Notes |
|-----------|-----|--------|-----------|-------|
| Frontend | 2 cores | 4 GB | 3+ | Stateless, scale by RPS |
| History | 4 cores | 8 GB | 4-16 | Scale by workflow volume |
| Matching | 2 cores | 4 GB | 3+ | Scale by task dispatch rate |
| Worker (internal) | 2 cores | 4 GB | 2-3 | System workflows |
| Cassandra | 8 cores | 32 GB | 3+ (RF=3) | Scale by storage/throughput |
| Elasticsearch | 4 cores | 16 GB | 3+ | Scale by search volume |

### Key Production Metrics

| Metric | Target | Alert Threshold |
|--------|--------|-----------------|
| Workflow start latency (p99) | < 100ms | > 500ms |
| Activity dispatch latency (p99) | < 50ms | > 200ms |
| Schedule-to-start latency (p99) | < 100ms | > 1s (worker starvation) |
| History service errors | 0 | > 0.1% |
| Persistence latency (p99) | < 20ms | > 100ms |
| Workflow task replay latency | < 100ms | > 1s |
| Transfer task lag | 0 | > 100 |
| Timer task lag | < 1s | > 10s |
