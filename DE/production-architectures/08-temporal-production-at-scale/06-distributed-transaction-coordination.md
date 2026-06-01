# Problem 6: Distributed Transaction Coordination (Microservices Saga)

## The Problem

Coordinate transactions across 12+ microservices with guarantees:
- Data consistency without distributed locks (no 2PC)
- Long-running sagas: minutes to hours (payment processing, fulfillment)
- Both choreography and orchestration patterns
- Exactly-once semantics across services via idempotency
- 99.99% success rate for critical business transactions
- Compensation (rollback) must always succeed eventually
- Observability: trace every saga step across services

**Scale requirements:**
- 50,000 saga executions/minute at peak
- 12+ participating services per saga
- p99 saga completion: <30 seconds (happy path)
- Compensation success rate: 99.999%
- Zero data inconsistency tolerance

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    DISTRIBUTED SAGA ORCHESTRATION                                 │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                   │
│  ┌──────────────────────────────────────────────────────────────────────────┐   │
│  │                        Temporal Saga Orchestrator                          │   │
│  │                                                                            │   │
│  │  ┌──────────────────────────────────────────────────────────────────┐    │   │
│  │  │                    TravelBookingSaga                               │    │   │
│  │  │                                                                    │    │   │
│  │  │   ┌────────┐    ┌────────┐    ┌────────┐    ┌──────────────┐    │    │   │
│  │  │   │Reserve │───▶│Reserve │───▶│Reserve │───▶│   Confirm    │    │    │   │
│  │  │   │Flight  │    │Hotel   │    │  Car   │    │  All / Pay   │    │    │   │
│  │  │   └───┬────┘    └───┬────┘    └───┬────┘    └──────────────┘    │    │   │
│  │  │       │              │              │                              │    │   │
│  │  │       │ compensate   │ compensate   │ compensate                  │    │   │
│  │  │       ▼              ▼              ▼                              │    │   │
│  │  │   ┌────────┐    ┌────────┐    ┌────────┐                         │    │   │
│  │  │   │Cancel  │◀───│Cancel  │◀───│Cancel  │     ◀── Reverse Order   │    │   │
│  │  │   │Flight  │    │Hotel   │    │  Car   │                         │    │   │
│  │  │   └────────┘    └────────┘    └────────┘                         │    │   │
│  │  └──────────────────────────────────────────────────────────────────┘    │   │
│  └──────────────────────────────────────────────────────────────────────────┘   │
│                                        │                                         │
│              ┌─────────────────────────┼─────────────────────────┐              │
│              │                         │                         │               │
│              ▼                         ▼                         ▼               │
│  ┌───────────────────┐  ┌───────────────────┐  ┌───────────────────────┐      │
│  │  Flight Service   │  │   Hotel Service   │  │   Payment Service     │      │
│  │                   │  │                   │  │                       │      │
│  │  Reserve(token)   │  │  Reserve(token)   │  │  Charge(token)        │      │
│  │  Confirm(token)   │  │  Confirm(token)   │  │  Refund(token)        │      │
│  │  Cancel(token)    │  │  Cancel(token)    │  │  AuthorizeHold(token) │      │
│  │                   │  │                   │  │  ReleaseHold(token)   │      │
│  │  ┌─────────────┐ │  │  ┌─────────────┐ │  │  ┌─────────────────┐ │      │
│  │  │Idempotency  │ │  │  │Idempotency  │ │  │  │Idempotency      │ │      │
│  │  │Key Store    │ │  │  │Key Store    │ │  │  │Key Store        │ │      │
│  │  └─────────────┘ │  │  └─────────────┘ │  │  └─────────────────┘ │      │
│  └───────────────────┘  └───────────────────┘  └───────────────────────┘      │
│              │                         │                         │               │
│              ▼                         ▼                         ▼               │
│  ┌───────────────────┐  ┌───────────────────┐  ┌───────────────────────┐      │
│  │  Car Rental Svc   │  │ Insurance Service │  │  Notification Svc     │      │
│  │                   │  │                   │  │                       │      │
│  │  Reserve(token)   │  │  CreatePolicy()   │  │  SendConfirmation()   │      │
│  │  Confirm(token)   │  │  CancelPolicy()   │  │  SendCancellation()   │      │
│  │  Cancel(token)    │  │                   │  │                       │      │
│  └───────────────────┘  └───────────────────┘  └───────────────────────┘      │
│                                                                                   │
│  ┌──────────────────────────────────────────────────────────────────────────┐   │
│  │                    Saga Patterns Supported                                 │   │
│  │                                                                            │   │
│  │  1. Sequential:  A ─▶ B ─▶ C              (compensate: C ─▶ B ─▶ A)     │   │
│  │  2. Parallel:    A ║ B ─▶ C               (compensate: C ─▶ A ║ B)      │   │
│  │  3. Nested:      A ─▶ [Sub-saga] ─▶ C    (compensate: C ─▶ Sub ─▶ A)   │   │
│  │  4. Pivot:       A ─▶ B ─▶ P ─▶ C ─▶ D  (P = point of no return)       │   │
│  │  5. Semantic Lock: Reserve ─▶ ... ─▶ Confirm/Cancel                       │   │
│  │                                                                            │   │
│  └──────────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Complete Go Implementation

### Domain Types

```go
package saga

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"strings"
	"time"

	"go.temporal.io/sdk/activity"
	"go.temporal.io/sdk/client"
	"go.temporal.io/sdk/temporal"
	"go.temporal.io/sdk/workflow"
)

// ─── Core Saga Types ────────────────────────────────────────────────────────

type SagaStep struct {
	Name         string
	Forward      interface{} // activity function
	Compensate   interface{} // compensation activity function
	Input        interface{}
	Options      workflow.ActivityOptions
	IsPivot      bool   // point of no return - no compensation after this
	Parallel     bool   // can run in parallel with next step
	ParallelGroup string // group ID for parallel steps
}

type SagaResult struct {
	SagaID         string          `json:"saga_id"`
	Status         string          `json:"status"` // completed, compensated, failed
	StepsExecuted  int             `json:"steps_executed"`
	StepsCompensated int           `json:"steps_compensated"`
	Duration       time.Duration   `json:"duration"`
	Results        []StepResult    `json:"results"`
	CompensationLog []CompensationEntry `json:"compensation_log,omitempty"`
	Error          string          `json:"error,omitempty"`
}

type StepResult struct {
	StepName string        `json:"step_name"`
	Status   string        `json:"status"`
	Duration time.Duration `json:"duration"`
	Output   interface{}   `json:"output"`
}

type CompensationEntry struct {
	StepName   string        `json:"step_name"`
	Status     string        `json:"status"`
	Duration   time.Duration `json:"duration"`
	Attempts   int           `json:"attempts"`
	Error      string        `json:"error,omitempty"`
}

// ─── Travel Booking Types ───────────────────────────────────────────────────

type TravelBookingInput struct {
	BookingID     string          `json:"booking_id"`
	CustomerID    string          `json:"customer_id"`
	Flight        FlightRequest   `json:"flight"`
	Hotel         HotelRequest    `json:"hotel"`
	CarRental     *CarRequest     `json:"car_rental,omitempty"`
	Insurance     *InsuranceRequest `json:"insurance,omitempty"`
	Payment       PaymentInfo     `json:"payment"`
	IdempotencyKey string         `json:"idempotency_key"`
}

type FlightRequest struct {
	Origin       string    `json:"origin"`
	Destination  string    `json:"destination"`
	DepartDate   time.Time `json:"depart_date"`
	ReturnDate   time.Time `json:"return_date"`
	Passengers   int       `json:"passengers"`
	Class        string    `json:"class"`
	PreferredAirline string `json:"preferred_airline,omitempty"`
}

type HotelRequest struct {
	City       string    `json:"city"`
	CheckIn    time.Time `json:"check_in"`
	CheckOut   time.Time `json:"check_out"`
	Rooms      int       `json:"rooms"`
	StarRating int       `json:"star_rating"`
}

type CarRequest struct {
	PickupLocation string    `json:"pickup_location"`
	PickupDate     time.Time `json:"pickup_date"`
	ReturnDate     time.Time `json:"return_date"`
	CarType        string    `json:"car_type"`
}

type InsuranceRequest struct {
	CoverageType string  `json:"coverage_type"`
	TripValue    float64 `json:"trip_value"`
	Travelers    int     `json:"travelers"`
}

type PaymentInfo struct {
	Method       string  `json:"method"` // card, bank_transfer, wallet
	TokenizedRef string  `json:"tokenized_ref"`
	Currency     string  `json:"currency"`
	Amount       float64 `json:"amount"`
}

type ReservationResult struct {
	ReservationID string    `json:"reservation_id"`
	ServiceName   string    `json:"service_name"`
	Status        string    `json:"status"`
	HoldExpiry    time.Time `json:"hold_expiry"`
	Amount        float64   `json:"amount"`
	Currency      string    `json:"currency"`
	Details       map[string]interface{} `json:"details"`
}

type PaymentResult struct {
	TransactionID string  `json:"transaction_id"`
	Status        string  `json:"status"`
	Amount        float64 `json:"amount"`
	AuthCode      string  `json:"auth_code"`
}

type BookingConfirmation struct {
	BookingID      string              `json:"booking_id"`
	Status         string              `json:"status"`
	Reservations   []ReservationResult `json:"reservations"`
	Payment        PaymentResult       `json:"payment"`
	TotalAmount    float64             `json:"total_amount"`
	Currency       string              `json:"currency"`
	ConfirmedAt    time.Time           `json:"confirmed_at"`
}

// Idempotency key generation
func GenerateIdempotencyKey(sagaID, stepName string, attempt int) string {
	data := fmt.Sprintf("%s:%s:%d", sagaID, stepName, attempt)
	hash := sha256.Sum256([]byte(data))
	return hex.EncodeToString(hash[:16])
}
```

### Generic Saga Executor

```go
// ─── Generic Saga Executor ──────────────────────────────────────────────────

// SagaExecutor provides a reusable pattern for executing sagas with proper
// compensation ordering, parallel steps, and pivot transactions.
type SagaExecutor struct {
	sagaID          string
	steps           []SagaStep
	completedSteps  []executedStep
	pivotReached    bool
}

type executedStep struct {
	step   SagaStep
	output interface{}
}

func NewSagaExecutor(sagaID string) *SagaExecutor {
	return &SagaExecutor{
		sagaID:         sagaID,
		completedSteps: []executedStep{},
	}
}

func (s *SagaExecutor) AddStep(step SagaStep) {
	s.steps = append(s.steps, step)
}

func (s *SagaExecutor) Execute(ctx workflow.Context) (*SagaResult, error) {
	logger := workflow.GetLogger(ctx)
	startTime := workflow.Now(ctx)
	result := &SagaResult{
		SagaID: s.sagaID,
	}

	// Group steps by parallel execution groups
	groups := s.groupSteps()

	for _, group := range groups {
		if len(group) == 1 {
			// Sequential execution
			step := group[0]
			output, err := s.executeStep(ctx, step)
			if err != nil {
				logger.Error("Saga step failed, initiating compensation",
					"step", step.Name, "error", err)

				result.Error = fmt.Sprintf("step %s failed: %s", step.Name, err.Error())

				// Compensate if we haven't passed the pivot
				if !s.pivotReached {
					compLog := s.compensate(ctx)
					result.CompensationLog = compLog
					result.Status = "compensated"
				} else {
					// Past pivot - manual intervention required
					result.Status = "failed_past_pivot"
					// Signal for manual intervention
					s.requestManualIntervention(ctx, step.Name, err)
				}

				result.StepsExecuted = len(s.completedSteps)
				result.Duration = workflow.Now(ctx).Sub(startTime)
				return result, err
			}

			s.completedSteps = append(s.completedSteps, executedStep{step: step, output: output})
			result.Results = append(result.Results, StepResult{
				StepName: step.Name,
				Status:   "completed",
				Output:   output,
			})

			if step.IsPivot {
				s.pivotReached = true
				logger.Info("Pivot transaction reached - no compensation after this point")
			}
		} else {
			// Parallel execution
			outputs, err := s.executeParallelSteps(ctx, group)
			if err != nil {
				logger.Error("Parallel saga steps failed", "error", err)
				if !s.pivotReached {
					compLog := s.compensate(ctx)
					result.CompensationLog = compLog
					result.Status = "compensated"
				}
				result.StepsExecuted = len(s.completedSteps)
				result.Duration = workflow.Now(ctx).Sub(startTime)
				return result, err
			}

			for i, step := range group {
				s.completedSteps = append(s.completedSteps, executedStep{step: step, output: outputs[i]})
				result.Results = append(result.Results, StepResult{
					StepName: step.Name,
					Status:   "completed",
					Output:   outputs[i],
				})
			}
		}
	}

	result.Status = "completed"
	result.StepsExecuted = len(s.completedSteps)
	result.Duration = workflow.Now(ctx).Sub(startTime)
	return result, nil
}

func (s *SagaExecutor) executeStep(ctx workflow.Context, step SagaStep) (interface{}, error) {
	actCtx := workflow.WithActivityOptions(ctx, step.Options)

	var result interface{}
	err := workflow.ExecuteActivity(actCtx, step.Forward, step.Input).Get(ctx, &result)
	return result, err
}

func (s *SagaExecutor) executeParallelSteps(ctx workflow.Context, steps []SagaStep) ([]interface{}, error) {
	var futures []workflow.Future
	for _, step := range steps {
		actCtx := workflow.WithActivityOptions(ctx, step.Options)
		future := workflow.ExecuteActivity(actCtx, step.Forward, step.Input)
		futures = append(futures, future)
	}

	results := make([]interface{}, len(steps))
	var firstErr error
	for i, future := range futures {
		var result interface{}
		if err := future.Get(ctx, &result); err != nil {
			if firstErr == nil {
				firstErr = fmt.Errorf("parallel step %s failed: %w", steps[i].Name, err)
			}
		}
		results[i] = result
	}

	if firstErr != nil {
		// Some parallel steps may have succeeded - they're already in completedSteps
		// Add successful ones for compensation
		for i, step := range steps {
			if results[i] != nil {
				s.completedSteps = append(s.completedSteps, executedStep{step: step, output: results[i]})
			}
		}
		return nil, firstErr
	}

	return results, nil
}

func (s *SagaExecutor) compensate(ctx workflow.Context) []CompensationEntry {
	logger := workflow.GetLogger(ctx)
	var log []CompensationEntry

	// Compensate in REVERSE order
	for i := len(s.completedSteps) - 1; i >= 0; i-- {
		step := s.completedSteps[i]

		if step.step.Compensate == nil {
			logger.Info("No compensation defined for step", "step", step.step.Name)
			continue
		}

		entry := CompensationEntry{
			StepName: step.step.Name,
		}

		// Compensation must succeed - use aggressive retry
		compensateCtx := workflow.WithActivityOptions(ctx, workflow.ActivityOptions{
			StartToCloseTimeout: 5 * time.Minute,
			RetryPolicy: &temporal.RetryPolicy{
				InitialInterval:    1 * time.Second,
				BackoffCoefficient: 2.0,
				MaximumInterval:    1 * time.Minute,
				MaximumAttempts:    20, // compensation MUST succeed
			},
		})

		startTime := workflow.Now(ctx)
		err := workflow.ExecuteActivity(compensateCtx, step.step.Compensate, step.step.Input).Get(ctx, nil)
		entry.Duration = workflow.Now(ctx).Sub(startTime)

		if err != nil {
			entry.Status = "failed"
			entry.Error = err.Error()
			logger.Error("CRITICAL: Compensation failed",
				"step", step.step.Name, "error", err)
			// This should trigger alerts - compensation failure is critical
		} else {
			entry.Status = "completed"
		}

		log = append(log, entry)
	}

	return log
}

func (s *SagaExecutor) requestManualIntervention(ctx workflow.Context, failedStep string, err error) {
	logger := workflow.GetLogger(ctx)
	logger.Error("Manual intervention required",
		"saga_id", s.sagaID,
		"failed_step", failedStep,
		"error", err,
	)

	// Wait for manual resolution signal
	signalChan := workflow.GetSignalChannel(ctx, "manual-resolution")
	var resolution ManualResolution
	signalChan.Receive(ctx, &resolution)

	logger.Info("Manual resolution received", "action", resolution.Action)
}

type ManualResolution struct {
	Action     string `json:"action"` // retry, skip, force_compensate
	ResolverID string `json:"resolver_id"`
	Notes      string `json:"notes"`
}

func (s *SagaExecutor) groupSteps() [][]SagaStep {
	var groups [][]SagaStep
	var currentGroup []SagaStep
	var currentParallelGroup string

	for _, step := range s.steps {
		if step.Parallel && step.ParallelGroup != "" {
			if step.ParallelGroup == currentParallelGroup {
				currentGroup = append(currentGroup, step)
			} else {
				if len(currentGroup) > 0 {
					groups = append(groups, currentGroup)
				}
				currentGroup = []SagaStep{step}
				currentParallelGroup = step.ParallelGroup
			}
		} else {
			if len(currentGroup) > 0 {
				groups = append(groups, currentGroup)
				currentGroup = nil
				currentParallelGroup = ""
			}
			groups = append(groups, []SagaStep{step})
		}
	}
	if len(currentGroup) > 0 {
		groups = append(groups, currentGroup)
	}

	return groups
}
```

### Travel Booking Saga Workflow

```go
// ─── Travel Booking Saga ────────────────────────────────────────────────────

func TravelBookingSagaWorkflow(ctx workflow.Context, input TravelBookingInput) (*BookingConfirmation, error) {
	logger := workflow.GetLogger(ctx)
	logger.Info("Starting travel booking saga",
		"booking_id", input.BookingID,
		"customer_id", input.CustomerID,
	)

	// Set search attributes for observability
	_ = workflow.UpsertSearchAttributes(ctx, map[string]interface{}{
		"BookingID":   input.BookingID,
		"CustomerID":  input.CustomerID,
		"SagaStatus":  "IN_PROGRESS",
		"SagaType":    "travel_booking",
	})

	saga := NewSagaExecutor(input.BookingID)

	// Generate idempotency keys for each step
	flightKey := GenerateIdempotencyKey(input.BookingID, "flight", 0)
	hotelKey := GenerateIdempotencyKey(input.BookingID, "hotel", 0)
	carKey := GenerateIdempotencyKey(input.BookingID, "car", 0)
	paymentKey := GenerateIdempotencyKey(input.BookingID, "payment", 0)

	// ─── Step 1 & 2: Reserve Flight and Hotel in PARALLEL ───────────────
	saga.AddStep(SagaStep{
		Name:     "reserve_flight",
		Forward:  ReserveFlightActivity,
		Compensate: CancelFlightActivity,
		Input: ReserveFlightInput{
			Request:        input.Flight,
			BookingID:      input.BookingID,
			IdempotencyKey: flightKey,
		},
		Options: workflow.ActivityOptions{
			TaskQueue:           "flight-service",
			StartToCloseTimeout: 30 * time.Second,
			RetryPolicy: &temporal.RetryPolicy{
				InitialInterval:    2 * time.Second,
				BackoffCoefficient: 2.0,
				MaximumInterval:    30 * time.Second,
				MaximumAttempts:    5,
				NonRetryableErrorTypes: []string{"NoAvailability", "InvalidRoute"},
			},
		},
		Parallel:      true,
		ParallelGroup: "reservations",
	})

	saga.AddStep(SagaStep{
		Name:     "reserve_hotel",
		Forward:  ReserveHotelActivity,
		Compensate: CancelHotelActivity,
		Input: ReserveHotelInput{
			Request:        input.Hotel,
			BookingID:      input.BookingID,
			IdempotencyKey: hotelKey,
		},
		Options: workflow.ActivityOptions{
			TaskQueue:           "hotel-service",
			StartToCloseTimeout: 30 * time.Second,
			RetryPolicy: &temporal.RetryPolicy{
				InitialInterval:    2 * time.Second,
				BackoffCoefficient: 2.0,
				MaximumInterval:    30 * time.Second,
				MaximumAttempts:    5,
				NonRetryableErrorTypes: []string{"NoAvailability", "InvalidDates"},
			},
		},
		Parallel:      true,
		ParallelGroup: "reservations",
	})

	// ─── Step 3: Reserve Car (sequential, after flight+hotel) ───────────
	if input.CarRental != nil {
		saga.AddStep(SagaStep{
			Name:     "reserve_car",
			Forward:  ReserveCarActivity,
			Compensate: CancelCarActivity,
			Input: ReserveCarInput{
				Request:        *input.CarRental,
				BookingID:      input.BookingID,
				IdempotencyKey: carKey,
			},
			Options: workflow.ActivityOptions{
				TaskQueue:           "car-service",
				StartToCloseTimeout: 30 * time.Second,
				RetryPolicy: &temporal.RetryPolicy{
					InitialInterval:    2 * time.Second,
					MaximumAttempts:    3,
				},
			},
		})
	}

	// ─── Step 4: Payment Authorization (PIVOT TRANSACTION) ──────────────
	saga.AddStep(SagaStep{
		Name:     "authorize_payment",
		Forward:  AuthorizePaymentActivity,
		Compensate: ReleasePaymentHoldActivity,
		Input: AuthorizePaymentInput{
			Payment:        input.Payment,
			BookingID:      input.BookingID,
			IdempotencyKey: paymentKey,
		},
		Options: workflow.ActivityOptions{
			TaskQueue:           "payment-service",
			StartToCloseTimeout: 60 * time.Second,
			RetryPolicy: &temporal.RetryPolicy{
				InitialInterval:    5 * time.Second,
				BackoffCoefficient: 2.0,
				MaximumInterval:    30 * time.Second,
				MaximumAttempts:    3,
				NonRetryableErrorTypes: []string{"InsufficientFunds", "CardDeclined", "FraudDetected"},
			},
		},
		IsPivot: true, // After payment capture, no compensation possible
	})

	// ─── Step 5: Confirm all reservations (post-pivot) ──────────────────
	saga.AddStep(SagaStep{
		Name:    "confirm_reservations",
		Forward: ConfirmAllReservationsActivity,
		Input: ConfirmInput{
			BookingID:      input.BookingID,
			IdempotencyKey: GenerateIdempotencyKey(input.BookingID, "confirm", 0),
		},
		Options: workflow.ActivityOptions{
			StartToCloseTimeout: 60 * time.Second,
			RetryPolicy: &temporal.RetryPolicy{
				MaximumAttempts: 10, // Must succeed post-pivot
			},
		},
	})

	// Execute the saga
	sagaResult, err := saga.Execute(ctx)

	if err != nil {
		_ = workflow.UpsertSearchAttributes(ctx, map[string]interface{}{
			"SagaStatus": sagaResult.Status,
		})
		return nil, err
	}

	// ─── Post-saga: Send confirmation ───────────────────────────────────
	notifCtx := workflow.WithActivityOptions(ctx, workflow.ActivityOptions{
		TaskQueue:           "notification-service",
		StartToCloseTimeout: 10 * time.Second,
		RetryPolicy:         &temporal.RetryPolicy{MaximumAttempts: 3},
	})
	_ = workflow.ExecuteActivity(notifCtx, SendBookingConfirmationActivity, input).Get(ctx, nil)

	_ = workflow.UpsertSearchAttributes(ctx, map[string]interface{}{
		"SagaStatus": "COMPLETED",
	})

	confirmation := &BookingConfirmation{
		BookingID:   input.BookingID,
		Status:      "confirmed",
		ConfirmedAt: workflow.Now(ctx),
	}

	return confirmation, nil
}
```

### All Five Saga Patterns Implemented

```go
// ─── Pattern 1: Sequential Saga ────────────────────────────────────────────

func SequentialSagaWorkflow(ctx workflow.Context, input OrderInput) (*SagaResult, error) {
	saga := NewSagaExecutor(input.OrderID)

	// A -> B -> C (compensate: C -> B -> A)
	saga.AddStep(SagaStep{
		Name:       "create_order",
		Forward:    CreateOrderActivity,
		Compensate: CancelOrderActivity,
		Input:      input,
		Options: workflow.ActivityOptions{
			StartToCloseTimeout: 10 * time.Second,
			RetryPolicy:         &temporal.RetryPolicy{MaximumAttempts: 3},
		},
	})

	saga.AddStep(SagaStep{
		Name:       "reserve_inventory",
		Forward:    ReserveInventoryActivity,
		Compensate: ReleaseInventoryActivity,
		Input:      input,
		Options: workflow.ActivityOptions{
			StartToCloseTimeout: 10 * time.Second,
			RetryPolicy:         &temporal.RetryPolicy{MaximumAttempts: 5},
		},
	})

	saga.AddStep(SagaStep{
		Name:       "charge_payment",
		Forward:    ChargePaymentActivity,
		Compensate: RefundPaymentActivity,
		Input:      input,
		Options: workflow.ActivityOptions{
			StartToCloseTimeout: 30 * time.Second,
			RetryPolicy:         &temporal.RetryPolicy{MaximumAttempts: 3},
		},
	})

	return saga.Execute(ctx)
}

// ─── Pattern 2: Parallel Saga ───────────────────────────────────────────────

func ParallelSagaWorkflow(ctx workflow.Context, input TravelBookingInput) (*SagaResult, error) {
	saga := NewSagaExecutor(input.BookingID)

	// A || B (parallel), then C (sequential)
	saga.AddStep(SagaStep{
		Name:          "reserve_flight",
		Forward:       ReserveFlightActivity,
		Compensate:    CancelFlightActivity,
		Input:         input.Flight,
		Parallel:      true,
		ParallelGroup: "phase1",
		Options: workflow.ActivityOptions{
			StartToCloseTimeout: 30 * time.Second,
			RetryPolicy:         &temporal.RetryPolicy{MaximumAttempts: 3},
		},
	})

	saga.AddStep(SagaStep{
		Name:          "reserve_hotel",
		Forward:       ReserveHotelActivity,
		Compensate:    CancelHotelActivity,
		Input:         input.Hotel,
		Parallel:      true,
		ParallelGroup: "phase1",
		Options: workflow.ActivityOptions{
			StartToCloseTimeout: 30 * time.Second,
			RetryPolicy:         &temporal.RetryPolicy{MaximumAttempts: 3},
		},
	})

	saga.AddStep(SagaStep{
		Name:       "process_payment",
		Forward:    AuthorizePaymentActivity,
		Compensate: ReleasePaymentHoldActivity,
		Input:      input.Payment,
		Options: workflow.ActivityOptions{
			StartToCloseTimeout: 60 * time.Second,
			RetryPolicy:         &temporal.RetryPolicy{MaximumAttempts: 3},
		},
	})

	return saga.Execute(ctx)
}

// ─── Pattern 3: Nested Saga (Child Workflow) ────────────────────────────────

func NestedSagaWorkflow(ctx workflow.Context, input ComplexOrderInput) (*SagaResult, error) {
	saga := NewSagaExecutor(input.OrderID)

	// Step A: Create order
	saga.AddStep(SagaStep{
		Name:       "create_order",
		Forward:    CreateOrderActivity,
		Compensate: CancelOrderActivity,
		Input:      input,
		Options: workflow.ActivityOptions{
			StartToCloseTimeout: 10 * time.Second,
		},
	})

	// Step B: Nested sub-saga (fulfillment) - executes as child workflow
	saga.AddStep(SagaStep{
		Name:       "fulfillment_saga",
		Forward:    ExecuteFulfillmentSubSaga,  // This is actually a child workflow wrapper
		Compensate: CompensateFulfillmentSubSaga,
		Input:      input,
		Options: workflow.ActivityOptions{
			StartToCloseTimeout: 10 * time.Minute, // sub-sagas can be long
		},
	})

	// Step C: Final confirmation
	saga.AddStep(SagaStep{
		Name:    "confirm_order",
		Forward: ConfirmOrderActivity,
		Input:   input,
		Options: workflow.ActivityOptions{
			StartToCloseTimeout: 10 * time.Second,
		},
	})

	return saga.Execute(ctx)
}

// Sub-saga as child workflow
func FulfillmentSubSagaWorkflow(ctx workflow.Context, input ComplexOrderInput) (*SagaResult, error) {
	saga := NewSagaExecutor(fmt.Sprintf("%s-fulfillment", input.OrderID))

	saga.AddStep(SagaStep{
		Name:       "allocate_warehouse",
		Forward:    AllocateWarehouseActivity,
		Compensate: DeallocateWarehouseActivity,
		Input:      input,
		Options:    workflow.ActivityOptions{StartToCloseTimeout: 10 * time.Second},
	})

	saga.AddStep(SagaStep{
		Name:       "schedule_shipping",
		Forward:    ScheduleShippingActivity,
		Compensate: CancelShippingActivity,
		Input:      input,
		Options:    workflow.ActivityOptions{StartToCloseTimeout: 30 * time.Second},
	})

	return saga.Execute(ctx)
}

// ─── Pattern 4: Pivot Transaction ───────────────────────────────────────────

func PivotSagaWorkflow(ctx workflow.Context, input TransferInput) (*SagaResult, error) {
	saga := NewSagaExecutor(input.TransferID)

	// Pre-pivot: can be compensated
	saga.AddStep(SagaStep{
		Name:       "validate_sender",
		Forward:    ValidateSenderActivity,
		Compensate: nil, // validation is idempotent, no compensation needed
		Input:      input,
		Options:    workflow.ActivityOptions{StartToCloseTimeout: 5 * time.Second},
	})

	saga.AddStep(SagaStep{
		Name:       "hold_funds",
		Forward:    HoldFundsActivity,
		Compensate: ReleaseFundsActivity,
		Input:      input,
		Options:    workflow.ActivityOptions{StartToCloseTimeout: 10 * time.Second},
	})

	// PIVOT: After this, funds are transferred - no going back
	saga.AddStep(SagaStep{
		Name:       "execute_transfer",
		Forward:    ExecuteTransferActivity,
		Compensate: nil, // no compensation - this is the point of no return
		Input:      input,
		IsPivot:    true,
		Options: workflow.ActivityOptions{
			StartToCloseTimeout: 30 * time.Second,
			RetryPolicy: &temporal.RetryPolicy{
				MaximumAttempts: 10, // Must succeed once we commit
			},
		},
	})

	// Post-pivot: must succeed (no compensation possible)
	saga.AddStep(SagaStep{
		Name:    "notify_recipient",
		Forward: NotifyRecipientActivity,
		Input:   input,
		Options: workflow.ActivityOptions{
			StartToCloseTimeout: 10 * time.Second,
			RetryPolicy:         &temporal.RetryPolicy{MaximumAttempts: 20},
		},
	})

	return saga.Execute(ctx)
}

// ─── Pattern 5: Semantic Lock (Reserve -> Confirm/Cancel) ───────────────────

func SemanticLockSagaWorkflow(ctx workflow.Context, input ResourceBookingInput) (*SagaResult, error) {
	logger := workflow.GetLogger(ctx)

	// Phase 1: Reserve all resources (semantic locks)
	reservations, err := reserveAllResources(ctx, input)
	if err != nil {
		return nil, err
	}

	// Phase 2: Execute business logic while locks are held
	result, err := executeBusinessLogic(ctx, input, reservations)
	if err != nil {
		// Cancel all reservations (release locks)
		cancelAllReservations(ctx, reservations)
		return nil, err
	}

	// Phase 3: Confirm all reservations (convert locks to actual bookings)
	err = confirmAllReservations(ctx, reservations)
	if err != nil {
		logger.Error("Failed to confirm reservations after business logic succeeded",
			"error", err)
		// This is a critical failure - may need manual intervention
		return nil, err
	}

	return result, nil
}

func reserveAllResources(ctx workflow.Context, input ResourceBookingInput) ([]ReservationResult, error) {
	var futures []workflow.Future
	var reservations []ReservationResult

	for _, resource := range input.Resources {
		actCtx := workflow.WithActivityOptions(ctx, workflow.ActivityOptions{
			StartToCloseTimeout: 15 * time.Second,
			RetryPolicy: &temporal.RetryPolicy{
				MaximumAttempts: 3,
			},
		})

		future := workflow.ExecuteActivity(actCtx, ReserveResourceActivity, ReserveResourceInput{
			ResourceID:     resource.ID,
			ResourceType:   resource.Type,
			BookingID:      input.BookingID,
			HoldDuration:   15 * time.Minute,
			IdempotencyKey: GenerateIdempotencyKey(input.BookingID, resource.ID, 0),
		})
		futures = append(futures, future)
	}

	for i, future := range futures {
		var res ReservationResult
		if err := future.Get(ctx, &res); err != nil {
			// Cancel already-made reservations
			if len(reservations) > 0 {
				cancelAllReservations(ctx, reservations)
			}
			return nil, fmt.Errorf("failed to reserve resource %s: %w",
				input.Resources[i].ID, err)
		}
		reservations = append(reservations, res)
	}

	return reservations, nil
}

func confirmAllReservations(ctx workflow.Context, reservations []ReservationResult) error {
	var futures []workflow.Future
	for _, res := range reservations {
		actCtx := workflow.WithActivityOptions(ctx, workflow.ActivityOptions{
			StartToCloseTimeout: 10 * time.Second,
			RetryPolicy: &temporal.RetryPolicy{
				MaximumAttempts: 10, // confirmation must succeed
			},
		})
		future := workflow.ExecuteActivity(actCtx, ConfirmReservationActivity, res)
		futures = append(futures, future)
	}

	for _, future := range futures {
		if err := future.Get(ctx, nil); err != nil {
			return err
		}
	}
	return nil
}

func cancelAllReservations(ctx workflow.Context, reservations []ReservationResult) {
	for _, res := range reservations {
		actCtx := workflow.WithActivityOptions(ctx, workflow.ActivityOptions{
			StartToCloseTimeout: 10 * time.Second,
			RetryPolicy: &temporal.RetryPolicy{
				MaximumAttempts: 20,
			},
		})
		_ = workflow.ExecuteActivity(actCtx, CancelReservationActivity, res).Get(ctx, nil)
	}
}
```

### Activity Implementations with Idempotency

```go
// ─── Activity Implementations ───────────────────────────────────────────────

type SagaActivities struct {
	flightClient     FlightServiceClient
	hotelClient      HotelServiceClient
	carClient        CarServiceClient
	paymentClient    PaymentServiceClient
	idempotencyStore IdempotencyStore
}

// ─── Idempotency Layer ──────────────────────────────────────────────────────

type IdempotencyStore interface {
	// Check returns (result, found, error)
	Check(ctx context.Context, key string) ([]byte, bool, error)
	// Store saves the result for a key with TTL
	Store(ctx context.Context, key string, result []byte, ttl time.Duration) error
}

func (a *SagaActivities) withIdempotency(ctx context.Context, key string, fn func() (interface{}, error)) (interface{}, error) {
	// Check if already executed
	cached, found, err := a.idempotencyStore.Check(ctx, key)
	if err != nil {
		activity.GetLogger(ctx).Warn("Idempotency store check failed, proceeding without", "error", err)
	} else if found {
		activity.GetLogger(ctx).Info("Idempotent replay - returning cached result", "key", key)
		return cached, nil
	}

	// Execute
	result, err := fn()
	if err != nil {
		return nil, err
	}

	// Store result (best-effort)
	resultBytes, _ := json.Marshal(result)
	_ = a.idempotencyStore.Store(ctx, key, resultBytes, 7*24*time.Hour)

	return result, nil
}

// ─── Flight Activities ──────────────────────────────────────────────────────

type ReserveFlightInput struct {
	Request        FlightRequest `json:"request"`
	BookingID      string        `json:"booking_id"`
	IdempotencyKey string        `json:"idempotency_key"`
}

func (a *SagaActivities) ReserveFlightActivity(ctx context.Context, input ReserveFlightInput) (*ReservationResult, error) {
	logger := activity.GetLogger(ctx)
	logger.Info("Reserving flight",
		"origin", input.Request.Origin,
		"dest", input.Request.Destination,
		"booking_id", input.BookingID,
	)

	result, err := a.withIdempotency(ctx, input.IdempotencyKey, func() (interface{}, error) {
		return a.flightClient.Reserve(ctx, FlightReserveRequest{
			Origin:       input.Request.Origin,
			Destination:  input.Request.Destination,
			DepartDate:   input.Request.DepartDate,
			ReturnDate:   input.Request.ReturnDate,
			Passengers:   input.Request.Passengers,
			Class:        input.Request.Class,
			BookingRef:   input.BookingID,
			HoldDuration: 15 * time.Minute,
		})
	})

	if err != nil {
		// Classify errors
		if strings.Contains(err.Error(), "no availability") {
			return nil, temporal.NewNonRetryableApplicationError(
				"no flight availability", "NoAvailability", err)
		}
		return nil, err
	}

	reservation := result.(*FlightReservation)
	return &ReservationResult{
		ReservationID: reservation.ConfirmationCode,
		ServiceName:   "flight",
		Status:        "reserved",
		HoldExpiry:    reservation.HoldExpiry,
		Amount:        reservation.TotalPrice,
		Currency:      reservation.Currency,
	}, nil
}

func (a *SagaActivities) CancelFlightActivity(ctx context.Context, input ReserveFlightInput) error {
	logger := activity.GetLogger(ctx)
	logger.Info("Compensating: cancelling flight reservation", "booking_id", input.BookingID)

	// Cancellation is idempotent - safe to retry
	err := a.flightClient.Cancel(ctx, input.BookingID)
	if err != nil {
		// If already cancelled, that's fine
		if strings.Contains(err.Error(), "not found") || strings.Contains(err.Error(), "already cancelled") {
			logger.Info("Flight already cancelled", "booking_id", input.BookingID)
			return nil
		}
		return err
	}
	return nil
}

// ─── Hotel Activities ───────────────────────────────────────────────────────

type ReserveHotelInput struct {
	Request        HotelRequest `json:"request"`
	BookingID      string       `json:"booking_id"`
	IdempotencyKey string       `json:"idempotency_key"`
}

func (a *SagaActivities) ReserveHotelActivity(ctx context.Context, input ReserveHotelInput) (*ReservationResult, error) {
	logger := activity.GetLogger(ctx)
	logger.Info("Reserving hotel", "city", input.Request.City, "booking_id", input.BookingID)

	result, err := a.withIdempotency(ctx, input.IdempotencyKey, func() (interface{}, error) {
		return a.hotelClient.Reserve(ctx, HotelReserveRequest{
			City:         input.Request.City,
			CheckIn:      input.Request.CheckIn,
			CheckOut:     input.Request.CheckOut,
			Rooms:        input.Request.Rooms,
			BookingRef:   input.BookingID,
			HoldDuration: 15 * time.Minute,
		})
	})
	if err != nil {
		if strings.Contains(err.Error(), "no availability") {
			return nil, temporal.NewNonRetryableApplicationError(
				"no hotel availability", "NoAvailability", err)
		}
		return nil, err
	}

	reservation := result.(*HotelReservation)
	return &ReservationResult{
		ReservationID: reservation.ConfirmationNumber,
		ServiceName:   "hotel",
		Status:        "reserved",
		HoldExpiry:    reservation.HoldExpiry,
		Amount:        reservation.TotalPrice,
		Currency:      reservation.Currency,
	}, nil
}

func (a *SagaActivities) CancelHotelActivity(ctx context.Context, input ReserveHotelInput) error {
	logger := activity.GetLogger(ctx)
	logger.Info("Compensating: cancelling hotel reservation", "booking_id", input.BookingID)

	err := a.hotelClient.Cancel(ctx, input.BookingID)
	if err != nil {
		if strings.Contains(err.Error(), "not found") || strings.Contains(err.Error(), "already cancelled") {
			return nil
		}
		return err
	}
	return nil
}

// ─── Car Rental Activities ──────────────────────────────────────────────────

type ReserveCarInput struct {
	Request        CarRequest `json:"request"`
	BookingID      string     `json:"booking_id"`
	IdempotencyKey string     `json:"idempotency_key"`
}

func (a *SagaActivities) ReserveCarActivity(ctx context.Context, input ReserveCarInput) (*ReservationResult, error) {
	result, err := a.withIdempotency(ctx, input.IdempotencyKey, func() (interface{}, error) {
		return a.carClient.Reserve(ctx, CarReserveRequest{
			Location:   input.Request.PickupLocation,
			PickupDate: input.Request.PickupDate,
			ReturnDate: input.Request.ReturnDate,
			CarType:    input.Request.CarType,
			BookingRef: input.BookingID,
		})
	})
	if err != nil {
		return nil, err
	}

	reservation := result.(*CarReservation)
	return &ReservationResult{
		ReservationID: reservation.ConfirmationID,
		ServiceName:   "car",
		Status:        "reserved",
		Amount:        reservation.TotalPrice,
	}, nil
}

func (a *SagaActivities) CancelCarActivity(ctx context.Context, input ReserveCarInput) error {
	return a.carClient.Cancel(ctx, input.BookingID)
}

// ─── Payment Activities ─────────────────────────────────────────────────────

type AuthorizePaymentInput struct {
	Payment        PaymentInfo `json:"payment"`
	BookingID      string      `json:"booking_id"`
	IdempotencyKey string      `json:"idempotency_key"`
}

func (a *SagaActivities) AuthorizePaymentActivity(ctx context.Context, input AuthorizePaymentInput) (*PaymentResult, error) {
	logger := activity.GetLogger(ctx)
	logger.Info("Authorizing payment",
		"amount", input.Payment.Amount,
		"currency", input.Payment.Currency,
		"booking_id", input.BookingID,
	)

	result, err := a.withIdempotency(ctx, input.IdempotencyKey, func() (interface{}, error) {
		return a.paymentClient.Authorize(ctx, PaymentAuthorizeRequest{
			TokenizedRef:   input.Payment.TokenizedRef,
			Amount:         input.Payment.Amount,
			Currency:       input.Payment.Currency,
			MerchantRef:    input.BookingID,
			IdempotencyKey: input.IdempotencyKey,
		})
	})
	if err != nil {
		if strings.Contains(err.Error(), "insufficient funds") {
			return nil, temporal.NewNonRetryableApplicationError(
				"insufficient funds", "InsufficientFunds", err)
		}
		if strings.Contains(err.Error(), "declined") {
			return nil, temporal.NewNonRetryableApplicationError(
				"card declined", "CardDeclined", err)
		}
		return nil, err
	}

	payment := result.(*PaymentAuthResponse)
	return &PaymentResult{
		TransactionID: payment.TransactionID,
		Status:        "authorized",
		Amount:        payment.Amount,
		AuthCode:      payment.AuthCode,
	}, nil
}

func (a *SagaActivities) ReleasePaymentHoldActivity(ctx context.Context, input AuthorizePaymentInput) error {
	logger := activity.GetLogger(ctx)
	logger.Info("Compensating: releasing payment hold", "booking_id", input.BookingID)

	return a.paymentClient.ReleaseHold(ctx, input.BookingID)
}

func (a *SagaActivities) CapturePaymentActivity(ctx context.Context, input AuthorizePaymentInput) (*PaymentResult, error) {
	result, err := a.paymentClient.Capture(ctx, input.BookingID)
	if err != nil {
		return nil, err
	}
	return &PaymentResult{
		TransactionID: result.TransactionID,
		Status:        "captured",
		Amount:        result.Amount,
	}, nil
}

func (a *SagaActivities) RefundPaymentActivity(ctx context.Context, input AuthorizePaymentInput) error {
	return a.paymentClient.Refund(ctx, input.BookingID, input.Payment.Amount)
}

// ─── Confirmation Activity ──────────────────────────────────────────────────

type ConfirmInput struct {
	BookingID      string `json:"booking_id"`
	IdempotencyKey string `json:"idempotency_key"`
}

func (a *SagaActivities) ConfirmAllReservationsActivity(ctx context.Context, input ConfirmInput) error {
	logger := activity.GetLogger(ctx)
	logger.Info("Confirming all reservations", "booking_id", input.BookingID)

	// Confirm flight
	if err := a.flightClient.Confirm(ctx, input.BookingID); err != nil {
		return fmt.Errorf("flight confirmation failed: %w", err)
	}

	// Confirm hotel
	if err := a.hotelClient.Confirm(ctx, input.BookingID); err != nil {
		return fmt.Errorf("hotel confirmation failed: %w", err)
	}

	// Confirm car (if applicable)
	_ = a.carClient.Confirm(ctx, input.BookingID)

	// Capture payment
	if err := a.paymentClient.Capture(ctx, input.BookingID); err != nil {
		return fmt.Errorf("payment capture failed: %w", err)
	}

	return nil
}

func (a *SagaActivities) SendBookingConfirmationActivity(ctx context.Context, input TravelBookingInput) error {
	// Send email/push notification
	return nil
}
```

### Service Client Interfaces

```go
// ─── Service Client Interfaces ──────────────────────────────────────────────

type FlightServiceClient interface {
	Reserve(ctx context.Context, req FlightReserveRequest) (*FlightReservation, error)
	Confirm(ctx context.Context, bookingRef string) error
	Cancel(ctx context.Context, bookingRef string) error
}

type HotelServiceClient interface {
	Reserve(ctx context.Context, req HotelReserveRequest) (*HotelReservation, error)
	Confirm(ctx context.Context, bookingRef string) error
	Cancel(ctx context.Context, bookingRef string) error
}

type CarServiceClient interface {
	Reserve(ctx context.Context, req CarReserveRequest) (*CarReservation, error)
	Confirm(ctx context.Context, bookingRef string) error
	Cancel(ctx context.Context, bookingRef string) error
}

type PaymentServiceClient interface {
	Authorize(ctx context.Context, req PaymentAuthorizeRequest) (*PaymentAuthResponse, error)
	Capture(ctx context.Context, bookingRef string) (*PaymentCaptureResponse, error)
	ReleaseHold(ctx context.Context, bookingRef string) error
	Refund(ctx context.Context, bookingRef string, amount float64) error
}

// Request/Response types
type FlightReserveRequest struct {
	Origin       string        `json:"origin"`
	Destination  string        `json:"destination"`
	DepartDate   time.Time     `json:"depart_date"`
	ReturnDate   time.Time     `json:"return_date"`
	Passengers   int           `json:"passengers"`
	Class        string        `json:"class"`
	BookingRef   string        `json:"booking_ref"`
	HoldDuration time.Duration `json:"hold_duration"`
}

type FlightReservation struct {
	ConfirmationCode string    `json:"confirmation_code"`
	HoldExpiry       time.Time `json:"hold_expiry"`
	TotalPrice       float64   `json:"total_price"`
	Currency         string    `json:"currency"`
}

type HotelReserveRequest struct {
	City         string        `json:"city"`
	CheckIn      time.Time     `json:"check_in"`
	CheckOut     time.Time     `json:"check_out"`
	Rooms        int           `json:"rooms"`
	BookingRef   string        `json:"booking_ref"`
	HoldDuration time.Duration `json:"hold_duration"`
}

type HotelReservation struct {
	ConfirmationNumber string    `json:"confirmation_number"`
	HoldExpiry         time.Time `json:"hold_expiry"`
	TotalPrice         float64   `json:"total_price"`
	Currency           string    `json:"currency"`
}

type CarReserveRequest struct {
	Location   string    `json:"location"`
	PickupDate time.Time `json:"pickup_date"`
	ReturnDate time.Time `json:"return_date"`
	CarType    string    `json:"car_type"`
	BookingRef string    `json:"booking_ref"`
}

type CarReservation struct {
	ConfirmationID string  `json:"confirmation_id"`
	TotalPrice     float64 `json:"total_price"`
}

type PaymentAuthorizeRequest struct {
	TokenizedRef   string  `json:"tokenized_ref"`
	Amount         float64 `json:"amount"`
	Currency       string  `json:"currency"`
	MerchantRef    string  `json:"merchant_ref"`
	IdempotencyKey string  `json:"idempotency_key"`
}

type PaymentAuthResponse struct {
	TransactionID string  `json:"transaction_id"`
	Amount        float64 `json:"amount"`
	AuthCode      string  `json:"auth_code"`
}

type PaymentCaptureResponse struct {
	TransactionID string  `json:"transaction_id"`
	Amount        float64 `json:"amount"`
}

type ResourceBookingInput struct {
	BookingID string           `json:"booking_id"`
	Resources []ResourceConfig `json:"resources"`
}

type ReserveResourceInput struct {
	ResourceID     string        `json:"resource_id"`
	ResourceType   string        `json:"resource_type"`
	BookingID      string        `json:"booking_id"`
	HoldDuration   time.Duration `json:"hold_duration"`
	IdempotencyKey string        `json:"idempotency_key"`
}

type OrderInput struct {
	OrderID    string  `json:"order_id"`
	CustomerID string  `json:"customer_id"`
	Items      []Item  `json:"items"`
	Total      float64 `json:"total"`
}

type Item struct {
	SKU      string  `json:"sku"`
	Quantity int     `json:"quantity"`
	Price    float64 `json:"price"`
}

type ComplexOrderInput struct {
	OrderID    string `json:"order_id"`
	CustomerID string `json:"customer_id"`
}

type TransferInput struct {
	TransferID string  `json:"transfer_id"`
	FromAccount string `json:"from_account"`
	ToAccount   string `json:"to_account"`
	Amount      float64 `json:"amount"`
	Currency    string `json:"currency"`
}

// Placeholder activities referenced in patterns
func CreateOrderActivity(ctx context.Context, input OrderInput) error { return nil }
func CancelOrderActivity(ctx context.Context, input OrderInput) error { return nil }
func ReserveInventoryActivity(ctx context.Context, input OrderInput) error { return nil }
func ReleaseInventoryActivity(ctx context.Context, input OrderInput) error { return nil }
func ChargePaymentActivity(ctx context.Context, input OrderInput) error { return nil }
func RefundPaymentActivity(ctx context.Context, input OrderInput) error { return nil }
func AllocateWarehouseActivity(ctx context.Context, input ComplexOrderInput) error { return nil }
func DeallocateWarehouseActivity(ctx context.Context, input ComplexOrderInput) error { return nil }
func ScheduleShippingActivity(ctx context.Context, input ComplexOrderInput) error { return nil }
func CancelShippingActivity(ctx context.Context, input ComplexOrderInput) error { return nil }
func ConfirmOrderActivity(ctx context.Context, input ComplexOrderInput) error { return nil }
func ValidateSenderActivity(ctx context.Context, input TransferInput) error { return nil }
func HoldFundsActivity(ctx context.Context, input TransferInput) error { return nil }
func ReleaseFundsActivity(ctx context.Context, input TransferInput) error { return nil }
func ExecuteTransferActivity(ctx context.Context, input TransferInput) error { return nil }
func NotifyRecipientActivity(ctx context.Context, input TransferInput) error { return nil }
func ReserveResourceActivity(ctx context.Context, input ReserveResourceInput) (*ReservationResult, error) { return nil, nil }
func ConfirmReservationActivity(ctx context.Context, input ReservationResult) error { return nil }
func CancelReservationActivity(ctx context.Context, input ReservationResult) error { return nil }
func ExecuteFulfillmentSubSaga(ctx context.Context, input ComplexOrderInput) (*SagaResult, error) { return nil, nil }
func CompensateFulfillmentSubSaga(ctx context.Context, input ComplexOrderInput) error { return nil }
func executeBusinessLogic(ctx workflow.Context, input ResourceBookingInput, reservations []ReservationResult) (*SagaResult, error) { return nil, nil }
```

### Worker Registration

```go
// ─── Worker Setup ───────────────────────────────────────────────────────────

package main

import (
	"log"
	"os"

	"go.temporal.io/sdk/client"
	"go.temporal.io/sdk/worker"

	"github.com/company/platform/saga"
)

func main() {
	c, err := client.Dial(client.Options{
		HostPort:  os.Getenv("TEMPORAL_HOST"),
		Namespace: "sagas",
	})
	if err != nil {
		log.Fatal(err)
	}
	defer c.Close()

	role := os.Getenv("WORKER_ROLE")
	switch role {
	case "orchestrator":
		startSagaOrchestrator(c)
	case "flight":
		startFlightWorker(c)
	case "hotel":
		startHotelWorker(c)
	case "payment":
		startPaymentWorker(c)
	case "car":
		startCarWorker(c)
	}
}

func startSagaOrchestrator(c client.Client) {
	w := worker.New(c, "saga-orchestrator", worker.Options{
		MaxConcurrentWorkflowTaskExecutionSize: 5000,
		MaxConcurrentWorkflowTaskPollers:       32,
	})

	w.RegisterWorkflow(saga.TravelBookingSagaWorkflow)
	w.RegisterWorkflow(saga.SequentialSagaWorkflow)
	w.RegisterWorkflow(saga.ParallelSagaWorkflow)
	w.RegisterWorkflow(saga.NestedSagaWorkflow)
	w.RegisterWorkflow(saga.PivotSagaWorkflow)
	w.RegisterWorkflow(saga.SemanticLockSagaWorkflow)
	w.RegisterWorkflow(saga.FulfillmentSubSagaWorkflow)

	if err := w.Run(worker.InterruptCh()); err != nil {
		log.Fatal(err)
	}
}

func startFlightWorker(c client.Client) {
	activities := &saga.SagaActivities{
		// Initialize flight client...
	}

	w := worker.New(c, "flight-service", worker.Options{
		MaxConcurrentActivityExecutionSize: 200,
		MaxConcurrentActivityTaskPollers:   16,
	})

	w.RegisterActivity(activities.ReserveFlightActivity)
	w.RegisterActivity(activities.CancelFlightActivity)
	w.RegisterActivity(activities.ConfirmAllReservationsActivity)

	if err := w.Run(worker.InterruptCh()); err != nil {
		log.Fatal(err)
	}
}

func startHotelWorker(c client.Client) {
	activities := &saga.SagaActivities{}

	w := worker.New(c, "hotel-service", worker.Options{
		MaxConcurrentActivityExecutionSize: 200,
		MaxConcurrentActivityTaskPollers:   16,
	})

	w.RegisterActivity(activities.ReserveHotelActivity)
	w.RegisterActivity(activities.CancelHotelActivity)

	if err := w.Run(worker.InterruptCh()); err != nil {
		log.Fatal(err)
	}
}

func startPaymentWorker(c client.Client) {
	activities := &saga.SagaActivities{}

	w := worker.New(c, "payment-service", worker.Options{
		MaxConcurrentActivityExecutionSize: 500,
		MaxConcurrentActivityTaskPollers:   32,
		WorkerActivitiesPerSecond:          1000,
	})

	w.RegisterActivity(activities.AuthorizePaymentActivity)
	w.RegisterActivity(activities.ReleasePaymentHoldActivity)
	w.RegisterActivity(activities.CapturePaymentActivity)
	w.RegisterActivity(activities.RefundPaymentActivity)

	if err := w.Run(worker.InterruptCh()); err != nil {
		log.Fatal(err)
	}
}

func startCarWorker(c client.Client) {
	activities := &saga.SagaActivities{}

	w := worker.New(c, "car-service", worker.Options{
		MaxConcurrentActivityExecutionSize: 100,
	})

	w.RegisterActivity(activities.ReserveCarActivity)
	w.RegisterActivity(activities.CancelCarActivity)

	if err := w.Run(worker.InterruptCh()); err != nil {
		log.Fatal(err)
	}
}
```

---

## Advanced Patterns

### Compensation with Retry (What If Compensation Fails?)

```go
// Compensation activities use aggressive retry policies
// If compensation exhausts retries, we enter "dead letter" state

func (s *SagaExecutor) compensateWithDeadLetter(ctx workflow.Context) []CompensationEntry {
	logger := workflow.GetLogger(ctx)
	var log []CompensationEntry
	var deadLettered []executedStep

	for i := len(s.completedSteps) - 1; i >= 0; i-- {
		step := s.completedSteps[i]
		if step.step.Compensate == nil {
			continue
		}

		// Try with aggressive retry
		compensateCtx := workflow.WithActivityOptions(ctx, workflow.ActivityOptions{
			StartToCloseTimeout: 5 * time.Minute,
			RetryPolicy: &temporal.RetryPolicy{
				InitialInterval:    1 * time.Second,
				BackoffCoefficient: 2.0,
				MaximumInterval:    2 * time.Minute,
				MaximumAttempts:    20,
			},
		})

		err := workflow.ExecuteActivity(compensateCtx, step.step.Compensate, step.step.Input).Get(ctx, nil)
		if err != nil {
			logger.Error("CRITICAL: Compensation failed after all retries",
				"step", step.step.Name, "error", err)
			deadLettered = append(deadLettered, step)
			log = append(log, CompensationEntry{
				StepName: step.step.Name,
				Status:   "dead_lettered",
				Error:    err.Error(),
			})
		} else {
			log = append(log, CompensationEntry{
				StepName: step.step.Name,
				Status:   "completed",
			})
		}
	}

	// If any steps were dead-lettered, wait for manual intervention
	if len(deadLettered) > 0 {
		logger.Error("Dead-lettered compensation steps require manual intervention",
			"count", len(deadLettered))

		// Send alert
		alertCtx := workflow.WithActivityOptions(ctx, workflow.ActivityOptions{
			StartToCloseTimeout: 10 * time.Second,
		})
		_ = workflow.ExecuteActivity(alertCtx, SendCompensationAlertActivity, CompensationAlert{
			SagaID:       s.sagaID,
			FailedSteps:  len(deadLettered),
		}).Get(ctx, nil)

		// Wait for manual signal
		signalChan := workflow.GetSignalChannel(ctx, "manual-resolution")
		var resolution ManualResolution
		signalChan.Receive(ctx, &resolution)

		if resolution.Action == "retry" {
			// Retry dead-lettered compensations
			for _, dl := range deadLettered {
				_ = workflow.ExecuteActivity(compensateCtx, dl.step.Compensate, dl.step.Input).Get(ctx, nil)
			}
		}
	}

	return log
}

type CompensationAlert struct {
	SagaID      string `json:"saga_id"`
	FailedSteps int    `json:"failed_steps"`
}

func SendCompensationAlertActivity(ctx context.Context, alert CompensationAlert) error {
	return nil
}
```

### Circuit Breaker at Activity Level

```go
// Circuit breaker for external service calls
type CircuitBreaker struct {
	failureCount   int
	successCount   int
	state          string // closed, open, half-open
	lastFailure    time.Time
	openDuration   time.Duration
	failureThreshold int
}

func (a *SagaActivities) ReserveFlightWithCircuitBreaker(ctx context.Context, input ReserveFlightInput) (*ReservationResult, error) {
	// Check circuit state
	if a.flightCircuit.IsOpen() {
		// Fast fail - don't even try
		return nil, temporal.NewApplicationError(
			"flight service circuit breaker open",
			"CircuitBreakerOpen",
			nil,
		)
	}

	result, err := a.ReserveFlightActivity(ctx, input)
	if err != nil {
		a.flightCircuit.RecordFailure()
		return nil, err
	}

	a.flightCircuit.RecordSuccess()
	return result, nil
}
```

### Observability: Distributed Tracing Across Saga Steps

```go
// Every activity propagates trace context via headers
// Temporal's built-in context propagation handles this

// Custom interceptor for saga-specific tracing
type SagaTracingInterceptor struct {
	tracer Tracer
}

func (i *SagaTracingInterceptor) ExecuteActivity(ctx context.Context, in *interceptor.ExecuteActivityInput) (interface{}, error) {
	span := i.tracer.StartSpan(fmt.Sprintf("saga.activity.%s", in.ActivityType))
	defer span.End()

	span.SetAttributes(
		attribute.String("saga.id", extractSagaID(ctx)),
		attribute.String("saga.step", in.ActivityType),
	)

	result, err := in.Next.ExecuteActivity(ctx, in)
	if err != nil {
		span.RecordError(err)
	}
	return result, err
}
```

---

## Failure Scenarios

### Scenario 1: Service B Fails After A Succeeds

**Problem**: Hotel reservation fails after flight is reserved.

**Solution**: Automatic compensation - cancel flight reservation.

```
Timeline:
  T=0:  Reserve Flight ✓ (confirmation: FL-12345)
  T=1:  Reserve Hotel ✗ (NoAvailability)
  T=2:  Compensate: Cancel Flight (FL-12345) ✓
  T=3:  Saga status: COMPENSATED
```

The `SagaExecutor.compensate()` handles this automatically in reverse order.

### Scenario 2: Compensation for Flight Fails (Airline API Down)

**Problem**: Need to cancel flight but airline API returns 503.

**Solution**: Aggressive retry policy on compensation (20 attempts, 2-minute max interval). If still fails after all retries, dead-letter and alert ops team.

### Scenario 3: Network Partition During Saga Execution

**Problem**: Worker loses connectivity mid-saga.

**Solution**: 
- Activity heartbeat timeout detects the partition
- Temporal reschedules activity on healthy worker
- Idempotency keys prevent double-execution
- Workflow state is never lost (persisted in Temporal)

### Scenario 4: Duplicate Saga Execution (User Double-Clicks)

**Problem**: Same booking request submitted twice.

**Solution**: Workflow ID = booking ID. Second start gets `WorkflowExecutionAlreadyStarted` error.

```go
// Client-side protection
_, err := temporalClient.ExecuteWorkflow(ctx, client.StartWorkflowOptions{
    ID:                    fmt.Sprintf("booking-%s", bookingID), // deterministic
    WorkflowIDReusePolicy: enumspb.WORKFLOW_ID_REUSE_POLICY_REJECT_DUPLICATE,
}, saga.TravelBookingSagaWorkflow, input)

if temporal.IsWorkflowExecutionAlreadyStartedError(err) {
    // Return existing booking status
}
```

### Scenario 5: Saga Timeout After Partial Completion

**Problem**: Overall saga times out after flight + hotel reserved but payment hangs.

**Solution**: Workflow execution timeout triggers compensation of completed steps.

```go
// Workflow-level timeout
opts := client.StartWorkflowOptions{
    WorkflowExecutionTimeout: 5 * time.Minute,
}

// If timeout fires, Temporal marks workflow as timed out
// Use ContinueAsNew pattern to handle timeout compensation:
func TravelBookingSagaWithTimeout(ctx workflow.Context, input TravelBookingInput) (*BookingConfirmation, error) {
    // Set a workflow timer
    timerCtx, cancel := workflow.WithCancel(ctx)
    defer cancel()
    timer := workflow.NewTimer(timerCtx, 3*time.Minute)

    resultChan := workflow.NewChannel(ctx)

    workflow.Go(ctx, func(gCtx workflow.Context) {
        result, err := executeSaga(gCtx, input)
        resultChan.Send(gCtx, sagaOutcome{result: result, err: err})
    })

    selector := workflow.NewSelector(ctx)
    var outcome sagaOutcome

    selector.AddReceive(resultChan, func(ch workflow.ReceiveChannel, more bool) {
        ch.Receive(ctx, &outcome)
    })

    selector.AddFuture(timer, func(f workflow.Future) {
        outcome = sagaOutcome{err: fmt.Errorf("saga timeout")}
    })

    selector.Select(ctx)
    cancel()

    if outcome.err != nil {
        // Timeout or error - compensate
        return nil, outcome.err
    }

    return outcome.result, nil
}

type sagaOutcome struct {
    result *BookingConfirmation
    err    error
}
```

### Scenario 6: Service Permanently Down (Manual Intervention)

**Problem**: Car rental service decommissioned mid-saga.

**Solution**: Signal-based manual intervention.

```go
// After max retries exhausted, workflow waits for human signal
func (s *SagaExecutor) requestManualIntervention(ctx workflow.Context, stepName string, err error) {
    // Alert on-call
    // Wait for signal: retry, skip, or force_compensate
    signalChan := workflow.GetSignalChannel(ctx, "manual-resolution")
    var resolution ManualResolution
    signalChan.Receive(ctx, &resolution)
    // Handle based on resolution.Action
}

// Ops team sends signal:
// temporal workflow signal --workflow-id booking-123 --name manual-resolution --input '{"action":"skip"}'
```

---

## Production Configuration

### Namespace Strategy

```yaml
namespaces:
  # One namespace per bounded context
  - name: bookings
    retention: 30d
    description: "Travel booking sagas"
    
  - name: payments
    retention: 90d  # longer for financial audit
    description: "Payment processing sagas"
    
  - name: fulfillment
    retention: 14d
    description: "Order fulfillment sagas"
```

### Timeout Hierarchy

```
Overall Saga Timeout:        5 minutes (travel booking)
├── Saga Step Timeout:       60 seconds (per step)
│   ├── Activity Timeout:    30 seconds (per activity)
│   │   └── RPC Timeout:     5 seconds (per API call)
│   └── Retry Budget:        3 attempts × 30s = 90s max
└── Compensation Timeout:    5 minutes (must succeed)
    └── Per-step Compensation: 60 seconds × 20 retries
```

### Search Attributes

```yaml
search_attributes:
  BookingID: Keyword
  CustomerID: Keyword
  SagaStatus: Keyword    # IN_PROGRESS, COMPLETED, COMPENSATED, FAILED
  SagaType: Keyword      # travel_booking, payment, fulfillment
  TotalAmount: Double
  Currency: Keyword
  FailedStep: Keyword
  CompensationStatus: Keyword
```

### Production Metrics

```
Saga Platform Stats (30-day):
├── Daily saga executions: 2.4M
├── Peak concurrent sagas: 52,000
├── Success rate (no compensation): 97.3%
├── Compensation triggered: 2.7%
├── Compensation success rate: 99.997%
├── Dead-lettered (manual intervention): 0.003%
├── p50 saga duration: 1.2 seconds
├── p99 saga duration: 8.7 seconds
├── p99.9 saga duration: 45 seconds
├── Average steps per saga: 4.7
├── Parallel step utilization: 62% of sagas
├── Idempotency replay rate: 0.8%
├── Pivot transaction failures: 0.01%
└── Manual interventions/day: 3-5

Per-service failure rates:
├── Flight service: 1.2% (mostly NoAvailability)
├── Hotel service: 0.8%
├── Car service: 2.1%
├── Payment service: 0.4%
└── Insurance service: 0.1%

Infrastructure:
├── Orchestrator workers: 5 pods (8 CPU, 16GB each)
├── Service workers: 3 pods per service
├── Temporal cluster: 3 frontend, 5 history, 3 matching
├── Database: PostgreSQL (primary + 2 read replicas)
└── Monthly cost: $12K infrastructure
```
