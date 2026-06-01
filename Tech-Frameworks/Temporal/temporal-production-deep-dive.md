# Temporal - Production Deep Dive for Billions of Transactions

## Architecture Overview

```text
+------------------------------------------------------------------+
|                     TEMPORAL CLUSTER                               |
|                                                                    |
|  +------------------+  +------------------+  +------------------+ |
|  |  Frontend Service|  |  History Service |  |  Matching Service| |
|  |  (gRPC Gateway)  |  |  (Workflow State)|  |  (Task Routing)  | |
|  +--------+---------+  +--------+---------+  +--------+---------+ |
|           |                      |                      |          |
|  +--------+---------+  +--------+---------+  +--------+---------+ |
|  |  Worker Service  |  |  Internal Worker |  | Visibility Service| |
|  |  (Replication)   |  |  (System Tasks)  |  | (Search/Query)   | |
|  +--------+---------+  +--------+---------+  +--------+---------+ |
|           |                      |                      |          |
+-----------|----------------------|----------------------|-----------+
            |                      |                      |
    +-------v------+      +-------v------+      +--------v-----+
    | Persistence  |      | Visibility   |      |  Elasticsearch|
    | (Cassandra/  |      | Store        |      |  /OpenSearch   |
    |  PostgreSQL/ |      | (Advanced    |      |               |
    |  MySQL)      |      |  Queries)    |      +---------------+
    +--------------+      +--------------+

+------------------------------------------------------------------+
|                       WORKER FLEET                                 |
|                                                                    |
|  +----------------+  +----------------+  +----------------+       |
|  | Worker Pod 1   |  | Worker Pod 2   |  | Worker Pod N   |       |
|  | - Workflows    |  | - Workflows    |  | - Workflows    |       |
|  | - Activities   |  | - Activities   |  | - Activities   |       |
|  | - Task Queue   |  | - Task Queue   |  | - Task Queue   |       |
|  +----------------+  +----------------+  +----------------+       |
+------------------------------------------------------------------+
```

---

## 1. Core Concepts

### 1.1 Workflow
A **durable function** that orchestrates activities. Survives process crashes, server restarts, and even datacenter failures. The workflow code is deterministic - given the same inputs and history, it produces the same commands.

```go
// Payment Processing Workflow
func PaymentWorkflow(ctx workflow.Context, payment PaymentRequest) (PaymentResult, error) {
    // Retry policy for activities
    ao := workflow.ActivityOptions{
        StartToCloseTimeout: 30 * time.Second,
        RetryPolicy: &temporal.RetryPolicy{
            InitialInterval:    time.Second,
            BackoffCoefficient: 2.0,
            MaximumInterval:    time.Minute,
            MaximumAttempts:    5,
        },
    }
    ctx = workflow.WithActivityOptions(ctx, ao)

    // Step 1: Validate payment
    var validation ValidationResult
    err := workflow.ExecuteActivity(ctx, ValidatePayment, payment).Get(ctx, &validation)
    if err != nil {
        return PaymentResult{}, err
    }

    // Step 2: Reserve funds (saga compensation pattern)
    var reservation ReservationResult
    err = workflow.ExecuteActivity(ctx, ReserveFunds, payment).Get(ctx, &reservation)
    if err != nil {
        return PaymentResult{}, err
    }

    // Step 3: Process with payment gateway
    var gatewayResult GatewayResult
    err = workflow.ExecuteActivity(ctx, ChargeGateway, payment).Get(ctx, &gatewayResult)
    if err != nil {
        // Compensate: release reserved funds
        _ = workflow.ExecuteActivity(ctx, ReleaseFunds, reservation).Get(ctx, nil)
        return PaymentResult{}, err
    }

    // Step 4: Update ledger
    err = workflow.ExecuteActivity(ctx, UpdateLedger, gatewayResult).Get(ctx, nil)
    if err != nil {
        // Compensate: refund via gateway + release funds
        _ = workflow.ExecuteActivity(ctx, RefundGateway, gatewayResult).Get(ctx, nil)
        _ = workflow.ExecuteActivity(ctx, ReleaseFunds, reservation).Get(ctx, nil)
        return PaymentResult{}, err
    }

    return PaymentResult{
        TransactionID: gatewayResult.TransactionID,
        Status:        "COMPLETED",
    }, nil
}
```

### 1.2 Activities
Activities are the **side-effecting** operations - HTTP calls, database writes, file I/O. They can be retried independently without re-executing the entire workflow.

### 1.3 Task Queues
Named queues that route workflow tasks and activity tasks to specific workers. Enables:
- **Priority routing**: Different task queues for high/low priority
- **Resource isolation**: GPU workers on separate queues
- **Geographic routing**: Route to nearest datacenter

### 1.4 Signals
External async events sent to a running workflow:
```go
func OrderWorkflow(ctx workflow.Context, order Order) error {
    // Wait for payment confirmation signal
    var paymentConfirmed bool
    signalChan := workflow.GetSignalChannel(ctx, "payment-confirmed")
    signalChan.Receive(ctx, &paymentConfirmed)
    
    if !paymentConfirmed {
        return workflow.ExecuteActivity(ctx, CancelOrder, order).Get(ctx, nil)
    }
    // Continue processing...
}
```

### 1.5 Queries
Synchronous read-only operations to inspect workflow state without affecting execution:
```go
func (w *OrderWorkflow) QueryStatus() (OrderStatus, error) {
    return w.currentStatus, nil
}
```

### 1.6 Child Workflows
Workflows that spawn sub-workflows for modularity and independent lifecycle management.

### 1.7 Timers & Sleep
Durable timers that survive restarts. `workflow.Sleep(ctx, 30*24*time.Hour)` -- sleeps for 30 days without consuming resources.

### 1.8 Continue-As-New
Resets workflow history to prevent unbounded growth. Critical for long-running workflows (subscription renewals, monitoring loops).

### 1.9 Saga Pattern (Compensations)
Built-in support for distributed transactions via compensation logic.

### 1.10 Visibility & Search Attributes
Custom indexed fields for querying workflows:
```go
workflow.UpsertSearchAttributes(ctx, map[string]interface{}{
    "CustomerId":  payment.CustomerID,
    "Amount":      payment.Amount,
    "Region":      payment.Region,
})
```

---

## 2. Top 10 Production Problems Solved by Temporal

### Problem 1: E-Commerce Order Fulfillment (Amazon-Scale)

```text
Sequence Diagram: Order Fulfillment

Customer        API Gateway       Temporal        Inventory       Payment       Shipping       Notification
   |                |                |               |               |              |              |
   |---PlaceOrder-->|                |               |               |              |              |
   |                |--StartWorkflow->               |               |              |              |
   |                |                |--ReserveStock->               |              |              |
   |                |                |<--Reserved----|               |              |              |
   |                |                |                               |              |              |
   |                |                |---ChargePayment-------------->|              |              |
   |                |                |<--PaymentOK------------------|              |              |
   |                |                |                               |              |              |
   |                |                |---CreateShipment----------------------------->              |
   |                |                |<--ShipmentCreated-----------------------------|              |
   |                |                |                               |              |              |
   |                |                |---SendNotification------------------------------------------->
   |                |                |<--Sent---------------------------------------------------|
   |                |                |                               |              |              |
   |                |                |---[Timer: 7 days]             |              |              |
   |                |                |                               |              |              |
   |                |                |---CheckDelivery------------------------------->              |
   |                |                |<--Delivered------------------------------------|              |
   |                |                |                               |              |              |
   |<--OrderComplete|                |               |               |              |              |
```

```go
func OrderFulfillmentWorkflow(ctx workflow.Context, order Order) error {
    // Saga compensations
    var compensations []func(workflow.Context) error
    defer func() {
        if ctx.Err() != nil {
            // Execute compensations in reverse order
            for i := len(compensations) - 1; i >= 0; i-- {
                compensations[i](ctx)
            }
        }
    }()

    // Step 1: Reserve inventory
    err := workflow.ExecuteActivity(ctx, ReserveInventory, order).Get(ctx, nil)
    if err != nil { return err }
    compensations = append(compensations, func(c workflow.Context) error {
        return workflow.ExecuteActivity(c, ReleaseInventory, order).Get(c, nil)
    })

    // Step 2: Charge payment
    err = workflow.ExecuteActivity(ctx, ChargePayment, order).Get(ctx, nil)
    if err != nil { return err }
    compensations = append(compensations, func(c workflow.Context) error {
        return workflow.ExecuteActivity(c, RefundPayment, order).Get(c, nil)
    })

    // Step 3: Create shipment
    var shipment Shipment
    err = workflow.ExecuteActivity(ctx, CreateShipment, order).Get(ctx, &shipment)
    if err != nil { return err }

    // Step 4: Wait for delivery (up to 14 days)
    deliveryCh := workflow.GetSignalChannel(ctx, "delivery-confirmed")
    timerCtx, cancel := workflow.WithCancel(ctx)
    timer := workflow.NewTimer(timerCtx, 14*24*time.Hour)

    selector := workflow.NewSelector(ctx)
    var delivered bool
    selector.AddReceive(deliveryCh, func(c workflow.Channel, more bool) {
        c.Receive(ctx, &delivered)
        cancel() // Cancel timer
    })
    selector.AddFuture(timer, func(f workflow.Future) {
        // Escalate: delivery timeout
        workflow.ExecuteActivity(ctx, EscalateDeliveryIssue, shipment)
    })
    selector.Select(ctx)

    return nil
}
```

**Scale**: Flipkart/Amazon process 10M+ orders/day. Each order is one workflow with guaranteed completion.

---

### Problem 2: Payment Processing & Reconciliation (PhonePe/Razorpay Scale)

```text
Workflow Diagram: Payment Lifecycle

    +----------+     +-----------+     +----------+     +-----------+
    | Initiate |---->| Authorize |---->| Capture  |---->| Settle    |
    | Payment  |     | (Bank/UPI)|     | (Hold)   |     | (T+1/T+2)|
    +----------+     +-----------+     +----------+     +-----------+
         |                |                 |                 |
         v                v                 v                 v
    +---------+     +-----------+     +----------+     +-----------+
    | Timeout |     | Retry w/  |     | Partial  |     | Reconcile |
    | Cancel  |     | Backoff   |     | Capture  |     | with Bank |
    +---------+     +-----------+     +----------+     +-----------+
                          |                                   |
                          v                                   v
                    +-----------+                       +-----------+
                    | Fallback  |                       | Dispute   |
                    | Gateway   |                       | Resolution|
                    +-----------+                       +-----------+
```

```go
func PaymentReconciliationWorkflow(ctx workflow.Context, batch ReconciliationBatch) error {
    // Run daily at T+1
    for _, txn := range batch.Transactions {
        // Fan-out: each transaction reconciled independently
        workflow.Go(ctx, func(gCtx workflow.Context) {
            ReconcileSingleTransaction(gCtx, txn)
        })
    }

    // Wait for all to complete (with timeout)
    // Use child workflows for massive batches (100K+ txns)
    if batch.Size > 100000 {
        // Split into child workflows of 10K each
        for i := 0; i < batch.Size; i += 10000 {
            childCtx := workflow.WithChildOptions(ctx, workflow.ChildWorkflowOptions{
                WorkflowID: fmt.Sprintf("recon-batch-%s-%d", batch.ID, i),
            })
            workflow.ExecuteChildWorkflow(childCtx, ReconcileBatchChild, batch.Slice(i, i+10000))
        }
    }
    return nil
}

func ReconcileSingleTransaction(ctx workflow.Context, txn Transaction) error {
    // Fetch bank statement
    var bankRecord BankRecord
    err := workflow.ExecuteActivity(ctx, FetchBankRecord, txn.ReferenceID).Get(ctx, &bankRecord)
    if err != nil {
        // Mark as unreconciled for manual review
        return workflow.ExecuteActivity(ctx, MarkUnreconciled, txn).Get(ctx, nil)
    }

    // Compare amounts
    if bankRecord.Amount != txn.Amount {
        return workflow.ExecuteActivity(ctx, RaiseDiscrepancy, txn, bankRecord).Get(ctx, nil)
    }

    return workflow.ExecuteActivity(ctx, MarkReconciled, txn).Get(ctx, nil)
}
```

**Scale**: PhonePe processes 500M+ transactions/month. Each requires guaranteed state tracking.

---

### Problem 3: Subscription Billing (Netflix/Spotify Scale)

```go
func SubscriptionWorkflow(ctx workflow.Context, sub Subscription) error {
    for {
        // Sleep until next billing date (durable timer - survives restarts)
        nextBilling := sub.NextBillingDate.Sub(workflow.Now(ctx))
        workflow.Sleep(ctx, nextBilling)

        // Attempt charge with retry
        var result ChargeResult
        err := workflow.ExecuteActivity(ctx, ChargSubscription, sub).Get(ctx, &result)
        
        if err != nil {
            // Dunning: retry 3 times over 7 days
            for attempt := 1; attempt <= 3; attempt++ {
                workflow.Sleep(ctx, time.Duration(attempt*2)*24*time.Hour)
                err = workflow.ExecuteActivity(ctx, ChargeSubscription, sub).Get(ctx, &result)
                if err == nil { break }
                workflow.ExecuteActivity(ctx, SendDunningEmail, sub, attempt)
            }
            if err != nil {
                workflow.ExecuteActivity(ctx, CancelSubscription, sub)
                return nil
            }
        }

        // Update next billing
        sub.NextBillingDate = sub.NextBillingDate.AddDate(0, 1, 0)
        
        // Continue-as-new to prevent history growth
        if workflow.GetInfo(ctx).GetCurrentHistoryLength() > 1000 {
            return workflow.NewContinueAsNewError(ctx, SubscriptionWorkflow, sub)
        }
    }
}
```

**Scale**: Netflix has 230M+ subscribers. Each subscription is a long-running workflow with monthly billing cycles.

---

### Problem 4: Distributed Saga - Travel Booking (MakeMyTrip/Booking.com)

```text
Sequence Diagram: Travel Booking Saga

Client          Temporal           FlightSvc       HotelSvc        CarSvc         PaymentSvc
  |                |                   |               |              |               |
  |--BookTrip----->|                   |               |              |               |
  |                |--BookFlight------->               |              |               |
  |                |<-FlightBooked-----|               |              |               |
  |                |                   |               |              |               |
  |                |--BookHotel----------------------->|              |               |
  |                |<-HotelBooked---------------------|              |               |
  |                |                   |               |              |               |
  |                |--BookCar------------------------------------------->             |
  |                |<-CarBooked-----------------------------------------|             |
  |                |                   |               |              |               |
  |                |--ChargePayment--------------------------------------------------->
  |                |<-PaymentFailed----------------------------------------------------|
  |                |                   |               |              |               |
  |                |  ** COMPENSATE ** |               |              |               |
  |                |--CancelCar------------------------------------------->             |
  |                |--CancelHotel-------------------->|              |               |
  |                |--CancelFlight---->|               |              |               |
  |                |                   |               |              |               |
  |<-BookingFailed-|                   |               |              |               |
```

```go
func TravelBookingSaga(ctx workflow.Context, booking TravelBooking) (BookingResult, error) {
    saga := NewSaga()

    // Book flight
    var flight FlightConfirmation
    err := workflow.ExecuteActivity(ctx, BookFlight, booking.Flight).Get(ctx, &flight)
    if err != nil { return BookingResult{}, err }
    saga.AddCompensation(ctx, CancelFlight, flight)

    // Book hotel
    var hotel HotelConfirmation
    err = workflow.ExecuteActivity(ctx, BookHotel, booking.Hotel).Get(ctx, &hotel)
    if err != nil {
        saga.Compensate(ctx) // Cancels flight
        return BookingResult{}, err
    }
    saga.AddCompensation(ctx, CancelHotel, hotel)

    // Book car
    var car CarConfirmation
    err = workflow.ExecuteActivity(ctx, BookCar, booking.Car).Get(ctx, &car)
    if err != nil {
        saga.Compensate(ctx) // Cancels hotel + flight
        return BookingResult{}, err
    }
    saga.AddCompensation(ctx, CancelCar, car)

    // Charge payment (final step - no compensation needed on success)
    err = workflow.ExecuteActivity(ctx, ChargePayment, booking.Payment).Get(ctx, nil)
    if err != nil {
        saga.Compensate(ctx) // Cancels car + hotel + flight
        return BookingResult{}, err
    }

    return BookingResult{Flight: flight, Hotel: hotel, Car: car}, nil
}
```

---

### Problem 5: User Onboarding & KYC (Fintech - Zerodha/Groww Scale)

```go
func KYCOnboardingWorkflow(ctx workflow.Context, user User) error {
    // Step 1: Collect documents (wait for user signal - up to 7 days)
    var docs Documents
    docChannel := workflow.GetSignalChannel(ctx, "documents-uploaded")
    
    timerCtx, cancel := workflow.WithCancel(ctx)
    timer := workflow.NewTimer(timerCtx, 7*24*time.Hour)

    selector := workflow.NewSelector(ctx)
    selector.AddReceive(docChannel, func(c workflow.Channel, more bool) {
        c.Receive(ctx, &docs)
        cancel()
    })
    selector.AddFuture(timer, func(f workflow.Future) {
        workflow.ExecuteActivity(ctx, SendReminder, user)
    })
    selector.Select(ctx)

    if docs.IsEmpty() { return errors.New("documents not received") }

    // Step 2: OCR extraction
    var extractedData ExtractedData
    workflow.ExecuteActivity(ctx, ExtractDocumentData, docs).Get(ctx, &extractedData)

    // Step 3: Third-party verification (parallel)
    var panVerified, aadhaarVerified bool
    workflow.Go(ctx, func(gCtx workflow.Context) {
        workflow.ExecuteActivity(gCtx, VerifyPAN, extractedData.PAN).Get(gCtx, &panVerified)
    })
    workflow.Go(ctx, func(gCtx workflow.Context) {
        workflow.ExecuteActivity(gCtx, VerifyAadhaar, extractedData.Aadhaar).Get(gCtx, &aadhaarVerified)
    })
    // Wait for both
    workflow.Await(ctx, func() bool { return panVerified && aadhaarVerified })

    // Step 4: Risk scoring
    var riskScore float64
    workflow.ExecuteActivity(ctx, CalculateRiskScore, user, extractedData).Get(ctx, &riskScore)

    if riskScore > 0.8 {
        // Manual review required
        workflow.ExecuteActivity(ctx, AssignToReviewer, user)
        var approved bool
        reviewCh := workflow.GetSignalChannel(ctx, "manual-review-complete")
        reviewCh.Receive(ctx, &approved)
        if !approved { return errors.New("rejected by reviewer") }
    }

    // Step 5: Account creation
    return workflow.ExecuteActivity(ctx, CreateAccount, user, extractedData).Get(ctx, nil)
}
```

---

### Problem 6: Data Pipeline Orchestration (ETL at Scale)

```go
func DataPipelineWorkflow(ctx workflow.Context, pipeline PipelineConfig) error {
    // Fan-out: Extract from multiple sources in parallel
    var extractResults []ExtractResult
    futures := make([]workflow.Future, len(pipeline.Sources))
    
    for i, source := range pipeline.Sources {
        actCtx := workflow.WithActivityOptions(ctx, workflow.ActivityOptions{
            StartToCloseTimeout: 2 * time.Hour, // Large data extraction
            HeartbeatTimeout:    30 * time.Second,
        })
        futures[i] = workflow.ExecuteActivity(actCtx, ExtractData, source)
    }

    for _, f := range futures {
        var result ExtractResult
        if err := f.Get(ctx, &result); err != nil {
            return fmt.Errorf("extraction failed: %w", err)
        }
        extractResults = append(extractResults, result)
    }

    // Transform (using child workflow for large datasets)
    var transformResult TransformResult
    childCtx := workflow.WithChildOptions(ctx, workflow.ChildWorkflowOptions{
        WorkflowExecutionTimeout: 4 * time.Hour,
    })
    err := workflow.ExecuteChildWorkflow(childCtx, TransformWorkflow, extractResults).Get(ctx, &transformResult)
    if err != nil { return err }

    // Load with idempotency
    return workflow.ExecuteActivity(ctx, LoadData, transformResult).Get(ctx, nil)
}
```

---

### Problem 7: Microservice Orchestration - Food Delivery (Swiggy/DoorDash)

```text
Workflow: Food Delivery Order

  +---------+    +----------+    +----------+    +---------+    +----------+
  | Order   |--->| Restaurant|-->| Assign   |--->| Pickup  |--->| Delivery |
  | Placed  |    | Accepted |    | Driver   |    | Food    |    | Complete |
  +---------+    +----------+    +----------+    +---------+    +----------+
       |              |               |               |              |
       v              v               v               v              v
  +---------+    +----------+    +----------+    +---------+    +----------+
  | Timeout |    | Rejected |    | No Driver|    | Delayed |    | Failed   |
  | Cancel  |    | Refund   |    | Expand   |    | Notify  |    | Refund   |
  +---------+    +----------+    | Radius   |    +---------+    +----------+
                                 +----------+
```

```go
func FoodDeliveryWorkflow(ctx workflow.Context, order DeliveryOrder) error {
    // Wait for restaurant acceptance (5 min timeout)
    acceptCh := workflow.GetSignalChannel(ctx, "restaurant-accepted")
    accepted := workflow.AwaitWithTimeout(ctx, 5*time.Minute, func() bool {
        var accepted bool
        acceptCh.Receive(ctx, &accepted)
        return accepted
    })
    if !accepted {
        return workflow.ExecuteActivity(ctx, CancelAndRefund, order).Get(ctx, nil)
    }

    // Find delivery partner (expanding radius)
    var driver Driver
    for radius := 3.0; radius <= 15.0; radius += 2.0 {
        err := workflow.ExecuteActivity(ctx, FindDriver, order, radius).Get(ctx, &driver)
        if err == nil { break }
        workflow.Sleep(ctx, 30*time.Second)
    }
    if driver.ID == "" {
        return workflow.ExecuteActivity(ctx, CancelAndRefund, order).Get(ctx, nil)
    }

    // Track delivery with periodic location updates
    deliveredCh := workflow.GetSignalChannel(ctx, "delivered")
    locationCh := workflow.GetSignalChannel(ctx, "location-update")
    
    for {
        selector := workflow.NewSelector(ctx)
        selector.AddReceive(deliveredCh, func(c workflow.Channel, more bool) {
            // Complete
        })
        selector.AddReceive(locationCh, func(c workflow.Channel, more bool) {
            var loc Location
            c.Receive(ctx, &loc)
            workflow.ExecuteActivity(ctx, UpdateCustomerETA, order, loc)
        })
        selector.Select(ctx)
        
        if order.IsDelivered { break }
    }

    return workflow.ExecuteActivity(ctx, CompleteDelivery, order).Get(ctx, nil)
}
```

---

### Problem 8: Infrastructure Provisioning (Terraform + Multi-Cloud)

```go
func InfraProvisioningWorkflow(ctx workflow.Context, infra InfraRequest) error {
    // Step 1: Plan
    var plan TerraformPlan
    err := workflow.ExecuteActivity(ctx, TerraformPlan, infra).Get(ctx, &plan)
    if err != nil { return err }

    // Step 2: Human approval for production
    if infra.Environment == "production" {
        workflow.ExecuteActivity(ctx, RequestApproval, plan)
        approvalCh := workflow.GetSignalChannel(ctx, "approval")
        var approved bool
        // Wait up to 24 hours for approval
        ctx2, cancel := workflow.WithCancel(ctx)
        timer := workflow.NewTimer(ctx2, 24*time.Hour)
        selector := workflow.NewSelector(ctx)
        selector.AddReceive(approvalCh, func(c workflow.Channel, more bool) {
            c.Receive(ctx, &approved)
            cancel()
        })
        selector.AddFuture(timer, func(f workflow.Future) {
            approved = false
        })
        selector.Select(ctx)
        if !approved { return errors.New("approval denied/timeout") }
    }

    // Step 3: Apply with heartbeat (long-running)
    actCtx := workflow.WithActivityOptions(ctx, workflow.ActivityOptions{
        StartToCloseTimeout: 30 * time.Minute,
        HeartbeatTimeout:    1 * time.Minute, // Detect stuck applies
    })
    return workflow.ExecuteActivity(actCtx, TerraformApply, plan).Get(ctx, nil)
}
```

---

### Problem 9: Batch Processing - Credit Score Calculation (CIBIL/Experian)

```go
func CreditScoreBatchWorkflow(ctx workflow.Context, batch CreditBatch) error {
    // Process millions of credit records
    batchSize := 10000
    var childFutures []workflow.ChildWorkflowFuture

    for i := 0; i < len(batch.Records); i += batchSize {
        end := min(i+batchSize, len(batch.Records))
        childCtx := workflow.WithChildOptions(ctx, workflow.ChildWorkflowOptions{
            WorkflowID: fmt.Sprintf("credit-batch-%s-%d", batch.ID, i),
            ParentClosePolicy: enumspb.PARENT_CLOSE_POLICY_ABANDON,
        })
        future := workflow.ExecuteChildWorkflow(childCtx, ProcessCreditBatchChild, batch.Records[i:end])
        childFutures = append(childFutures, future)
    }

    // Collect results
    var failures int
    for _, f := range childFutures {
        if err := f.Get(ctx, nil); err != nil {
            failures++
        }
    }

    // Report
    return workflow.ExecuteActivity(ctx, ReportBatchResults, batch.ID, failures).Get(ctx, nil)
}

func ProcessCreditBatchChild(ctx workflow.Context, records []CreditRecord) error {
    for _, record := range records {
        err := workflow.ExecuteActivity(ctx, CalculateCreditScore, record).Get(ctx, nil)
        if err != nil {
            workflow.ExecuteActivity(ctx, LogFailedRecord, record)
        }
        // Continue-as-new if history gets large
        if workflow.GetInfo(ctx).GetCurrentHistoryLength() > 5000 {
            return workflow.NewContinueAsNewError(ctx, ProcessCreditBatchChild, records[i:])
        }
    }
    return nil
}
```

---

### Problem 10: Event-Driven Automation - Fraud Detection (Real-Time)

```go
func FraudDetectionWorkflow(ctx workflow.Context, txn Transaction) error {
    // Real-time scoring
    var score FraudScore
    err := workflow.ExecuteActivity(ctx, MLFraudScore, txn).Get(ctx, &score)
    if err != nil { return err }

    if score.Risk > 0.9 {
        // Immediate block
        workflow.ExecuteActivity(ctx, BlockTransaction, txn)
        workflow.ExecuteActivity(ctx, NotifyFraudTeam, txn, score)
        
        // Wait for analyst decision (SLA: 4 hours)
        decisionCh := workflow.GetSignalChannel(ctx, "analyst-decision")
        var decision string
        timerCtx, cancel := workflow.WithCancel(ctx)
        timer := workflow.NewTimer(timerCtx, 4*time.Hour)
        
        selector := workflow.NewSelector(ctx)
        selector.AddReceive(decisionCh, func(c workflow.Channel, more bool) {
            c.Receive(ctx, &decision)
            cancel()
        })
        selector.AddFuture(timer, func(f workflow.Future) {
            decision = "auto-reject" // SLA breach
        })
        selector.Select(ctx)

        if decision == "approve" {
            workflow.ExecuteActivity(ctx, UnblockTransaction, txn)
        } else {
            workflow.ExecuteActivity(ctx, PermanentBlock, txn)
            workflow.ExecuteActivity(ctx, FileSAR, txn) // Suspicious Activity Report
        }
    } else if score.Risk > 0.6 {
        // Step-up authentication
        workflow.ExecuteActivity(ctx, RequestOTP, txn)
        otpCh := workflow.GetSignalChannel(ctx, "otp-verified")
        verified := false
        workflow.AwaitWithTimeout(ctx, 5*time.Minute, func() bool {
            otpCh.Receive(ctx, &verified)
            return verified
        })
        if !verified {
            workflow.ExecuteActivity(ctx, BlockTransaction, txn)
        }
    }
    // Low risk: auto-approve (no action needed)
    return nil
}
```

---

## 3. Production Deployment Architecture

### 3.1 Kubernetes Deployment (Billions Scale)

```text
Architecture: Production Temporal Deployment

+-----------------------------------------------------------------------------------+
|                            KUBERNETES CLUSTER                                      |
|                                                                                    |
|  +--- Namespace: temporal-system ------------------------------------------------+|
|  |                                                                                ||
|  |  +------------------+  +------------------+  +------------------+             ||
|  |  | Frontend (3+pods)|  | History (10+pods)|  | Matching (5+pods)|             ||
|  |  | HPA: CPU 70%    |  | HPA: CPU 60%    |  | HPA: CPU 65%    |             ||
|  |  | Memory: 2Gi     |  | Memory: 8Gi     |  | Memory: 4Gi     |             ||
|  |  +------------------+  +------------------+  +------------------+             ||
|  |                                                                                ||
|  |  +------------------+  +------------------+                                   ||
|  |  | Worker Svc(3pods)|  | Internal Worker  |                                   ||
|  |  +------------------+  +------------------+                                   ||
|  |                                                                                ||
|  +--------------------------------------------------------------------------------+|
|                                                                                    |
|  +--- Namespace: temporal-workers ------------------------------------------------+|
|  |                                                                                ||
|  |  +------------------+  +------------------+  +------------------+             ||
|  |  | Payment Workers  |  | Order Workers   |  | Notification     |             ||
|  |  | (20 pods, HPA)  |  | (15 pods, HPA)  |  | Workers (10 pods)|             ||
|  |  | CPU: 4 cores    |  | CPU: 2 cores    |  | CPU: 1 core     |             ||
|  |  | Mem: 4Gi        |  | Mem: 2Gi        |  | Mem: 1Gi        |             ||
|  |  +------------------+  +------------------+  +------------------+             ||
|  |                                                                                ||
|  +--------------------------------------------------------------------------------+|
+-----------------------------------------------------------------------------------+

+-----------------------------------------------------------------------------------+
|                         PERSISTENCE LAYER                                          |
|                                                                                    |
|  +------------------+  +------------------+  +------------------+                 |
|  | Cassandra Cluster|  | Elasticsearch    |  | Kafka (Events)   |                 |
|  | 9 nodes, RF=3   |  | 3 nodes          |  | 6 brokers        |                 |
|  | 32 cores, 128Gi |  | 16 cores, 64Gi  |  | 16 cores, 64Gi  |                 |
|  +------------------+  +------------------+  +------------------+                 |
+-----------------------------------------------------------------------------------+
```

### 3.2 Helm Chart Configuration

```yaml
# values-production.yaml
server:
  replicaCount:
    frontend: 5
    history: 20
    matching: 10
    worker: 3

  resources:
    frontend:
      requests:
        cpu: "2"
        memory: "4Gi"
      limits:
        cpu: "4"
        memory: "8Gi"
    history:
      requests:
        cpu: "4"
        memory: "8Gi"
      limits:
        cpu: "8"
        memory: "16Gi"

  config:
    persistence:
      default:
        driver: cassandra
        cassandra:
          hosts: "cassandra-0.cassandra,cassandra-1.cassandra,cassandra-2.cassandra"
          keyspace: temporal
          consistency: LOCAL_QUORUM
      visibility:
        driver: elasticsearch
        elasticsearch:
          url: "http://elasticsearch:9200"
          indices:
            visibility: temporal_visibility_v1

    # Critical for billions of transactions
    numHistoryShards: 16384  # Max shards for scale
    
    # Rate limiting
    frontend:
      rps: 10000
      namespaceRPS: 5000
    
    # History cache
    history:
      cacheMaxSize: 65536
      cacheTTL: "1h"

  autoscaling:
    enabled: true
    minReplicas: 5
    maxReplicas: 50
    targetCPUUtilizationPercentage: 65

cassandra:
  config:
    cluster_size: 9
    num_tokens: 256
    max_heap_size: 8G
    heap_new_size: 2G
```

### 3.3 Multi-Region Deployment

```text
                    +-------------------+
                    |   Global DNS      |
                    |  (Route53/GCP LB) |
                    +---------+---------+
                              |
              +---------------+---------------+
              |                               |
    +---------v---------+           +---------v---------+
    |  Region: US-East  |           |  Region: EU-West  |
    |                   |           |                   |
    | Temporal Cluster  |<--XDC-->  | Temporal Cluster  |
    | (Active)          | Repl.     | (Standby/Active)  |
    |                   |           |                   |
    | Cassandra (RF=3)  |<-------->| Cassandra (RF=3)  |
    | Workers (50 pods) |           | Workers (50 pods) |
    +-------------------+           +-------------------+
              |                               |
              +---------------+---------------+
                              |
                    +---------v---------+
                    |  Region: AP-South |
                    |                   |
                    | Temporal Cluster  |
                    | (Active)          |
                    |                   |
                    | Cassandra (RF=3)  |
                    | Workers (30 pods) |
                    +-------------------+
```

---

## 4. Monitoring & Observability

### 4.1 Key Metrics (Prometheus + Grafana)

```yaml
# Critical Temporal Metrics to Monitor

# Workflow Execution
- temporal_workflow_completed_total          # Success rate
- temporal_workflow_failed_total             # Failure rate
- temporal_workflow_canceled_total           # Cancellations
- temporal_workflow_continued_as_new_total   # CAN events
- temporal_workflow_endtoend_latency_seconds # E2E latency

# Activity Execution
- temporal_activity_execution_failed_total   # Activity failures
- temporal_activity_schedule_to_start_latency_seconds  # Queue wait time (CRITICAL)
- temporal_activity_execution_latency_seconds

# Task Queue Health
- temporal_task_queue_depth                  # Backlog (alert if growing)
- temporal_sticky_cache_hit_rate             # Cache efficiency
- temporal_poll_success_rate                 # Worker utilization

# Server Health
- temporal_persistence_latency_seconds       # DB latency
- temporal_history_size_bytes               # Workflow history size
- temporal_history_count                    # Event count per workflow

# Alerts Configuration
groups:
  - name: temporal-critical
    rules:
      - alert: TaskQueueBacklogGrowing
        expr: rate(temporal_task_queue_depth[5m]) > 100
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Task queue backlog growing - workers may be overwhelmed"

      - alert: WorkflowFailureRateHigh
        expr: rate(temporal_workflow_failed_total[5m]) / rate(temporal_workflow_completed_total[5m]) > 0.05
        for: 3m
        labels:
          severity: critical

      - alert: ActivityScheduleToStartHigh
        expr: histogram_quantile(0.99, temporal_activity_schedule_to_start_latency_seconds) > 30
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Activities waiting too long in queue - scale workers"

      - alert: PersistenceLatencyHigh
        expr: histogram_quantile(0.99, temporal_persistence_latency_seconds) > 2
        for: 3m
        labels:
          severity: critical
        annotations:
          summary: "Database latency too high - check Cassandra cluster"
```

### 4.2 Distributed Tracing (OpenTelemetry)

```go
// Worker with OpenTelemetry tracing
func NewTracedWorker() {
    tp := initTracer() // Jaeger/Tempo exporter
    
    w := worker.New(client, "payment-task-queue", worker.Options{
        MaxConcurrentActivityExecutionSize: 200,
        MaxConcurrentWorkflowTaskExecutionSize: 100,
        Interceptors: []interceptor.WorkerInterceptor{
            temporalotel.NewTracingInterceptor(temporalotel.TracerOptions{
                Tracer: tp.Tracer("temporal-worker"),
            }),
        },
    })
}
```

### 4.3 Grafana Dashboard Layout

```text
+------------------------------------------------------------------+
| TEMPORAL PRODUCTION DASHBOARD                                      |
+------------------------------------------------------------------+
| Workflow Success Rate | Active Workflows | Task Queue Depth       |
|     99.97%          |    1.2M          |    Low: 23             |
+------------------------------------------------------------------+
| Activity Latency P99 | Schedule-to-Start| Persistence Latency    |
|     450ms            |    12ms          |    8ms                 |
+------------------------------------------------------------------+
| [Graph: Workflow Starts/min]  | [Graph: Task Queue Backlog]      |
| [Graph: Activity Failures]   | [Graph: Worker CPU/Memory]       |
+------------------------------------------------------------------+
```

---

## 5. Scaling for Billions of Transactions

### 5.1 Horizontal Scaling Strategy

| Component | Scaling Factor | Bottleneck | Solution |
|-----------|---------------|------------|----------|
| Frontend | gRPC connections | CPU | HPA on CPU, add pods |
| History | Workflow state | Memory + Shards | Increase `numHistoryShards` |
| Matching | Task dispatch | CPU | HPA, partition task queues |
| Workers | Activity execution | CPU/Memory | Scale independently per queue |
| Cassandra | Persistence | Disk I/O, nodes | Add nodes, tune compaction |
| Elasticsearch | Visibility queries | Memory | Add data nodes |

### 5.2 Performance Tuning

```go
// Worker tuning for high throughput
w := worker.New(client, "high-throughput-queue", worker.Options{
    // Concurrency
    MaxConcurrentActivityExecutionSize:     500,
    MaxConcurrentWorkflowTaskExecutionSize: 200,
    MaxConcurrentLocalActivityExecutionSize: 100,
    
    // Pollers (increase for high-load queues)
    MaxConcurrentActivityTaskPollers:   20,
    MaxConcurrentWorkflowTaskPollers:   10,
    
    // Sticky execution (cache workflows in memory)
    StickyScheduleToStartTimeout: 5 * time.Second,
    
    // Rate limiting (prevent overwhelming downstream)
    WorkerActivitiesPerSecond:    1000,
    TaskQueueActivitiesPerSecond: 5000,
})
```

### 5.3 Capacity Planning

```text
Calculation for 1 Billion transactions/month:

Transactions/sec = 1,000,000,000 / (30 * 24 * 3600) ≈ 385 TPS
Peak (10x) = 3,850 TPS

Per workflow: ~5 activities avg, ~20 history events
Total events/sec = 385 * 20 = 7,700 events/sec
Peak events/sec = 38,500

Storage (Cassandra):
- Event size: ~1KB avg
- Monthly: 1B * 20 events * 1KB = 20TB
- With RF=3: 60TB
- Retention 90 days: 180TB total

History Shards: 16,384 (maximum)
- Each shard handles ~2.35 workflows/sec at peak

Workers needed (at 200 concurrent activities each):
- 3,850 TPS * 5 activities / 200 = ~96 worker pods
- With headroom (2x): 192 worker pods

Cassandra nodes:
- 180TB / 2TB per node = 90 nodes (with 2TB SSDs)
- Or 9-12 nodes with 16TB NVMe (recommended)
```

### 5.4 History Shards

```text
History Shard Architecture:

WorkflowID → Hash → Shard Assignment → History Node

  Workflow-A ──hash──> Shard 0001 ──> History Pod 1
  Workflow-B ──hash──> Shard 8192 ──> History Pod 5
  Workflow-C ──hash──> Shard 0001 ──> History Pod 1 (same shard)
  Workflow-D ──hash──> Shard 16384 -> History Pod 10

Key insight: numHistoryShards is IMMUTABLE after cluster creation.
Set it high (8192-16384) from day one.
Each shard is owned by exactly one History pod at any time.
More shards = better distribution = higher throughput ceiling.
```

---

## 6. Production Best Practices

### 6.1 Determinism Rules

```go
// WRONG - Non-deterministic
func BadWorkflow(ctx workflow.Context) error {
    time.Now()           // BAD: use workflow.Now(ctx)
    rand.Int()           // BAD: use workflow.SideEffect
    uuid.New()           // BAD: use workflow.SideEffect
    os.Getenv("KEY")     // BAD: pass as workflow input
    go func() {}()       // BAD: use workflow.Go
    http.Get("...")      // BAD: must be in an Activity
}

// CORRECT - Deterministic
func GoodWorkflow(ctx workflow.Context) error {
    now := workflow.Now(ctx)
    
    var randomVal int
    workflow.SideEffect(ctx, func(ctx workflow.Context) interface{} {
        return rand.Intn(100)
    }).Get(&randomVal)
    
    var id string
    workflow.SideEffect(ctx, func(ctx workflow.Context) interface{} {
        return uuid.New().String()
    }).Get(&id)
}
```

### 6.2 Versioning for Safe Deployments

```go
func MyWorkflow(ctx workflow.Context) error {
    v := workflow.GetVersion(ctx, "change-id-1", workflow.DefaultVersion, 1)
    
    if v == workflow.DefaultVersion {
        // Old logic (for in-flight workflows)
        workflow.ExecuteActivity(ctx, OldActivity)
    } else {
        // New logic (v1)
        workflow.ExecuteActivity(ctx, NewActivity)
    }
    return nil
}
```

### 6.3 Error Handling Strategy

```go
// Custom error types for different handling
var (
    ErrRetryable    = temporal.NewApplicationError("retryable", "RETRYABLE")
    ErrNonRetryable = temporal.NewNonRetryableApplicationError("fatal", "FATAL", nil)
    ErrBusinessRule = temporal.NewApplicationError("business", "BUSINESS_RULE")
)

// Activity with proper error handling
func ChargePaymentActivity(ctx context.Context, payment Payment) error {
    result, err := gateway.Charge(payment)
    if err != nil {
        if isNetworkError(err) {
            return ErrRetryable // Will be retried per policy
        }
        if isInsufficientFunds(err) {
            return ErrNonRetryable // Won't be retried
        }
        return err // Default: retryable
    }
    
    // Heartbeat for long activities
    activity.RecordHeartbeat(ctx, result.Progress)
    return nil
}
```

### 6.4 Testing

```go
func TestPaymentWorkflow(t *testing.T) {
    testSuite := &testsuite.WorkflowTestSuite{}
    env := testSuite.NewTestWorkflowEnvironment()

    // Mock activities
    env.OnActivity(ValidatePayment, mock.Anything, mock.Anything).Return(ValidationResult{Valid: true}, nil)
    env.OnActivity(ChargeGateway, mock.Anything, mock.Anything).Return(GatewayResult{TxnID: "txn-123"}, nil)
    env.OnActivity(UpdateLedger, mock.Anything, mock.Anything).Return(nil)

    // Execute workflow
    env.ExecuteWorkflow(PaymentWorkflow, PaymentRequest{Amount: 1000})

    require.True(t, env.IsWorkflowCompleted())
    require.NoError(t, env.GetWorkflowError())

    var result PaymentResult
    require.NoError(t, env.GetWorkflowResult(&result))
    assert.Equal(t, "txn-123", result.TransactionID)
}
```

---

## 7. Temporal vs Alternatives Comparison

| Feature | Temporal | Cadence | Step Functions | Airflow |
|---------|----------|---------|----------------|---------|
| Durability | Event-sourced | Event-sourced | State machine | None (retry only) |
| Language Support | Go, Java, TS, Python, .NET | Go, Java | JSON/YAML | Python |
| Latency | <100ms | <100ms | 200-500ms | Minutes |
| Scale | Billions/month | Billions/month | Millions/month | Thousands/day |
| Long-running | Years | Years | 1 year max | Not designed for |
| Self-hosted | Yes | Yes | No (AWS only) | Yes |
| Human-in-loop | Native (Signals) | Native | Callback tokens | External |
| Cost at scale | Infrastructure | Infrastructure | Per transition ($$$) | Infrastructure |
| Visibility | Advanced queries | Basic | CloudWatch | Web UI |

---

## 8. Common Production Issues & Solutions

| Issue | Cause | Solution |
|-------|-------|----------|
| Workflow history too large | Long-running loop | Use Continue-As-New after N events |
| Non-determinism error | Code change broke replay | Use Versioning API |
| Activity timeout | Downstream service slow | Tune timeouts, add heartbeat |
| Task queue backlog | Workers can't keep up | Scale workers, optimize activities |
| Persistence latency spike | Cassandra compaction | Schedule compaction off-peak, tune GC |
| Sticky cache miss | Worker restarts | Increase cache TTL, stable deployments |
| Signal lost | Sent before workflow registers handler | Buffer signals at workflow start |
| Child workflow orphaned | Parent terminated | Set ParentClosePolicy correctly |
| Duplicate workflow execution | Missing idempotency key | Use deterministic WorkflowID |
| Memory pressure on history | Large payloads in events | Use external blob storage for payloads |
