# Problem 2: E-Commerce Order Fulfillment Pipeline

## The Problem

Design a production order fulfillment system handling:
- **2M+ orders/day** (peaks at 50K/minute during flash sales)
- **8+ microservices** coordinated per order (inventory, payment, shipping, notification, fraud, tax, warehouse, returns)
- **Orders in-flight for days/weeks** (international shipping tracking)
- **Partial fulfillment** (split shipments from multiple warehouses)
- **Order modifications while in-flight** (cancel items, change address, add items)
- **Flash sale resilience** (10x traffic spikes in seconds)

## Architecture

```
┌────────────────────────────────────────────────────────────────────────────────────┐
│                     ORDER FULFILLMENT ARCHITECTURE                                   │
├────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│  ┌──────────┐     ┌────────────────────────────────────────────────────────────┐   │
│  │ Order API │────►│                   TEMPORAL CLUSTER                          │   │
│  │ Gateway   │     │   Namespace: orders-prod                                   │   │
│  └──────────┘     │                                                             │   │
│                    │   Task Queues:                                              │   │
│  ┌──────────┐     │   ├── order-orchestration-tq  (main workflow)              │   │
│  │ Storefront│────►│   ├── payment-tq             (payment child workflows)    │   │
│  │ Events   │     │   ├── inventory-tq            (reservation/allocation)     │   │
│  └──────────┘     │   ├── shipping-tq             (label gen, tracking)        │   │
│                    │   ├── warehouse-tq            (pick/pack/ship)             │   │
│  ┌──────────┐     │   ├── fraud-tq                (fraud scoring)              │   │
│  │ Webhook  │────►│   ├── notification-tq         (email/sms/push)             │   │
│  │ Receiver │     │   └── returns-tq              (return processing)          │   │
│  └──────────┘     └────────────────────────────────────────────────────────────┘   │
│                                          │                                          │
│    ┌─────────────────────────────────────┼───────────────────────────────────┐     │
│    │                                     │                                    │     │
│    ▼                                     ▼                                    ▼     │
│ ┌────────────────┐  ┌─────────────────────────────┐  ┌─────────────────────────┐  │
│ │ Order Workers  │  │    Domain Workers             │  │   Integration Workers   │  │
│ │ (15 pods)      │  │                               │  │                         │  │
│ │                │  │  Payment (10 pods)            │  │  Shipping APIs (8 pods) │  │
│ │ Orchestration  │  │  Inventory (8 pods)           │  │  Warehouse WMS (5 pods) │  │
│ │ workflows      │  │  Fraud (5 pods)               │  │  Notification (10 pods) │  │
│ └────────────────┘  └─────────────────────────────┘  └─────────────────────────┘  │
│                                                                                      │
│ ┌──────────────────────────────────────────────────────────────────────────────┐    │
│ │                          MICROSERVICES                                        │    │
│ │                                                                               │    │
│ │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐          │    │
│ │  │Inventory │ │ Payment  │ │ Shipping │ │Warehouse │ │  Fraud   │          │    │
│ │  │ Service  │ │ Service  │ │ Service  │ │  WMS     │ │ Service  │          │    │
│ │  │(gRPC)    │ │(gRPC)    │ │(REST)    │ │(gRPC)    │ │(gRPC)    │          │    │
│ │  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘          │    │
│ └──────────────────────────────────────────────────────────────────────────────┘    │
└────────────────────────────────────────────────────────────────────────────────────┘
```

## Order State Machine

```
                    ┌──────────────────────────────────────────────┐
                    │              ORDER STATES                     │
                    └──────────────────────────────────────────────┘

    ┌─────────┐     ┌───────────┐     ┌────────────┐     ┌───────────┐
    │ CREATED │────►│ FRAUD     │────►│ PAYMENT    │────►│ INVENTORY │
    │         │     │ CHECK     │     │ PROCESSING │     │ RESERVED  │
    └─────────┘     └─────┬─────┘     └─────┬──────┘     └─────┬─────┘
                          │                  │                   │
                          │ rejected         │ declined          │ out of stock
                          ▼                  ▼                   ▼
                    ┌───────────┐     ┌───────────┐      ┌───────────┐
                    │ REJECTED  │     │ PAYMENT   │      │ BACKORDERED│
                    │           │     │ FAILED    │      │           │
                    └───────────┘     └───────────┘      └───────────┘

    ┌───────────┐     ┌───────────┐     ┌───────────┐     ┌───────────┐
    │ WAREHOUSE │────►│ PICKING   │────►│ PACKED    │────►│ SHIPPED   │
    │ ASSIGNED  │     │           │     │           │     │           │
    └───────────┘     └───────────┘     └───────────┘     └─────┬─────┘
                                                                  │
                                                                  ▼
                                                          ┌───────────┐
    ┌───────────┐     ┌───────────┐                      │ DELIVERED │
    │ RETURN    │◄────│ RETURN    │◄─────────────────────│           │
    │ COMPLETED │     │ INITIATED │                      └───────────┘
    └───────────┘     └───────────┘

    At ANY state:
    ──────────────
    Signal: CancelOrder      → CANCELLED (with compensations)
    Signal: ModifyOrder      → Apply modification if state allows
    Signal: AddressChange    → Update shipping if not yet shipped
```

## Complete Go Implementation

### Domain Types

```go
package orders

import "time"

type Order struct {
	ID              string          `json:"id"`
	CustomerID      string          `json:"customer_id"`
	Items           []OrderItem     `json:"items"`
	ShippingAddress Address         `json:"shipping_address"`
	BillingAddress  Address         `json:"billing_address"`
	PaymentMethod   PaymentMethod   `json:"payment_method"`
	TotalAmount     Money           `json:"total_amount"`
	TaxAmount       Money           `json:"tax_amount"`
	ShippingCost    Money           `json:"shipping_cost"`
	DiscountCodes   []string        `json:"discount_codes"`
	IsVIP           bool            `json:"is_vip"`
	Priority        int             `json:"priority"`
	CreatedAt       time.Time       `json:"created_at"`
	Metadata        map[string]string `json:"metadata"`
}

type OrderItem struct {
	ItemID       string `json:"item_id"`
	SKU          string `json:"sku"`
	Name         string `json:"name"`
	Quantity     int    `json:"quantity"`
	UnitPrice    Money  `json:"unit_price"`
	WarehouseID  string `json:"warehouse_id,omitempty"` // Assigned during fulfillment
	Weight       int    `json:"weight_grams"`
}

type Address struct {
	Line1      string `json:"line1"`
	Line2      string `json:"line2"`
	City       string `json:"city"`
	State      string `json:"state"`
	PostalCode string `json:"postal_code"`
	Country    string `json:"country"`
}

type PaymentMethod struct {
	Type       string `json:"type"` // card, paypal, bank_transfer
	TokenID    string `json:"token_id"`
	Last4      string `json:"last4"`
}

type Money struct {
	AmountCents int64  `json:"amount_cents"`
	Currency    string `json:"currency"`
}

// OrderState is the workflow's internal state (queryable)
type OrderState struct {
	OrderID          string                 `json:"order_id"`
	Status           OrderStatus            `json:"status"`
	Items            []OrderItem            `json:"items"`
	Shipments        map[string]*Shipment   `json:"shipments"`
	PaymentRef       string                 `json:"payment_ref"`
	FraudScore       float64                `json:"fraud_score"`
	ReservationRefs  map[string]string      `json:"reservation_refs"` // itemID -> reservationRef
	WarehouseAssignments map[string]string  `json:"warehouse_assignments"` // itemID -> warehouseID
	TrackingNumbers  map[string]string      `json:"tracking_numbers"` // shipmentID -> tracking
	ModificationLog  []Modification         `json:"modification_log"`
	Timeline         []TimelineEvent        `json:"timeline"`
	Error            string                 `json:"error,omitempty"`
	CreatedAt        time.Time              `json:"created_at"`
	UpdatedAt        time.Time              `json:"updated_at"`
}

type OrderStatus string
const (
	StatusCreated           OrderStatus = "CREATED"
	StatusFraudCheck        OrderStatus = "FRAUD_CHECK"
	StatusPaymentProcessing OrderStatus = "PAYMENT_PROCESSING"
	StatusInventoryReserved OrderStatus = "INVENTORY_RESERVED"
	StatusWarehouseAssigned OrderStatus = "WAREHOUSE_ASSIGNED"
	StatusPicking           OrderStatus = "PICKING"
	StatusPacked            OrderStatus = "PACKED"
	StatusShipped           OrderStatus = "SHIPPED"
	StatusDelivered         OrderStatus = "DELIVERED"
	StatusCancelled         OrderStatus = "CANCELLED"
	StatusPaymentFailed     OrderStatus = "PAYMENT_FAILED"
	StatusBackordered       OrderStatus = "BACKORDERED"
	StatusReturnInitiated   OrderStatus = "RETURN_INITIATED"
	StatusReturnCompleted   OrderStatus = "RETURN_COMPLETED"
	StatusPartiallyShipped  OrderStatus = "PARTIALLY_SHIPPED"
)

type Shipment struct {
	ShipmentID      string      `json:"shipment_id"`
	Items           []string    `json:"item_ids"`
	WarehouseID     string      `json:"warehouse_id"`
	TrackingNumber  string      `json:"tracking_number"`
	Carrier         string      `json:"carrier"`
	Status          string      `json:"status"`
	ShippedAt       time.Time   `json:"shipped_at,omitempty"`
	DeliveredAt     time.Time   `json:"delivered_at,omitempty"`
	EstDeliveryDate time.Time   `json:"est_delivery_date,omitempty"`
}

type Modification struct {
	Type       string    `json:"type"`
	Details    string    `json:"details"`
	RequestedAt time.Time `json:"requested_at"`
	Applied    bool      `json:"applied"`
	Reason     string    `json:"reason,omitempty"`
}

type TimelineEvent struct {
	Event     string    `json:"event"`
	Timestamp time.Time `json:"timestamp"`
	Details   string    `json:"details,omitempty"`
}

// Signals
type CancelOrderSignal struct {
	Reason     string `json:"reason"`
	RequestedBy string `json:"requested_by"`
}

type ModifyOrderSignal struct {
	Type    string      `json:"type"` // remove_item, change_quantity, add_item
	ItemID  string      `json:"item_id"`
	NewQty  int         `json:"new_qty,omitempty"`
	NewItem *OrderItem  `json:"new_item,omitempty"`
}

type AddressChangeSignal struct {
	NewAddress Address `json:"new_address"`
}

type ShipmentUpdateSignal struct {
	ShipmentID string `json:"shipment_id"`
	Status     string `json:"status"`
	Timestamp  time.Time `json:"timestamp"`
	Details    string `json:"details"`
}
```

### Main Order Fulfillment Workflow

```go
package workflows

import (
	"fmt"
	"sort"
	"time"

	"go.temporal.io/sdk/temporal"
	"go.temporal.io/sdk/workflow"

	"github.com/company/orders/activities"
	"github.com/company/orders/domain"
)

const (
	SignalCancelOrder    = "cancel-order"
	SignalModifyOrder    = "modify-order"
	SignalAddressChange  = "address-change"
	SignalShipmentUpdate = "shipment-update"
	QueryGetOrderState  = "get-order-state"
	QueryGetShipment    = "get-shipment"
)

// OrderFulfillmentWorkflow is the main orchestrator for order processing.
// It coordinates multiple child workflows, handles signals for modifications,
// and tracks the order through its complete lifecycle.
func OrderFulfillmentWorkflow(ctx workflow.Context, order domain.Order) (*domain.OrderState, error) {
	logger := workflow.GetLogger(ctx)
	logger.Info("Starting order fulfillment", "orderID", order.ID, "items", len(order.Items))

	// Initialize state
	state := &domain.OrderState{
		OrderID:              order.ID,
		Status:               domain.StatusCreated,
		Items:                order.Items,
		Shipments:            make(map[string]*domain.Shipment),
		ReservationRefs:      make(map[string]string),
		WarehouseAssignments: make(map[string]string),
		TrackingNumbers:      make(map[string]string),
		CreatedAt:            workflow.Now(ctx),
		UpdatedAt:            workflow.Now(ctx),
	}

	// Track compensations
	var compensations []compensation

	// Set search attributes
	_ = workflow.UpsertSearchAttributes(ctx, map[string]interface{}{
		"OrderID":     order.ID,
		"CustomerID":  order.CustomerID,
		"Status":      string(state.Status),
		"TotalAmount": order.TotalAmount.AmountCents,
		"IsVIP":       order.IsVIP,
		"ItemCount":   len(order.Items),
	})

	// Register query handlers
	_ = workflow.SetQueryHandler(ctx, QueryGetOrderState, func() (*domain.OrderState, error) {
		return state, nil
	})
	_ = workflow.SetQueryHandler(ctx, QueryGetShipment, func(shipmentID string) (*domain.Shipment, error) {
		s, ok := state.Shipments[shipmentID]
		if !ok {
			return nil, fmt.Errorf("shipment %s not found", shipmentID)
		}
		return s, nil
	})

	// Signal channels
	cancelCh := workflow.GetSignalChannel(ctx, SignalCancelOrder)
	modifyCh := workflow.GetSignalChannel(ctx, SignalModifyOrder)
	addressCh := workflow.GetSignalChannel(ctx, SignalAddressChange)
	shipmentCh := workflow.GetSignalChannel(ctx, SignalShipmentUpdate)

	// Cancellation flag
	cancelled := false

	// Helper: drain and process pending signals
	drainSignals := func() {
		for {
			var signal domain.CancelOrderSignal
			ok := cancelCh.ReceiveAsync(&signal)
			if !ok {
				break
			}
			cancelled = true
			state.addTimeline("CANCEL_REQUESTED", signal.Reason)
		}
		for {
			var mod domain.ModifyOrderSignal
			ok := modifyCh.ReceiveAsync(&mod)
			if !ok {
				break
			}
			applyModification(state, mod)
		}
		for {
			var addr domain.AddressChangeSignal
			ok := addressCh.ReceiveAsync(&addr)
			if !ok {
				break
			}
			if state.Status < domain.StatusShipped {
				order.ShippingAddress = addr.NewAddress
				state.addTimeline("ADDRESS_CHANGED", addr.NewAddress.City)
			}
		}
	}

	// Helper: update status
	updateStatus := func(status domain.OrderStatus) {
		state.Status = status
		state.UpdatedAt = workflow.Now(ctx)
		state.addTimeline(string(status), "")
		_ = workflow.UpsertSearchAttributes(ctx, map[string]interface{}{
			"Status": string(status),
		})
	}

	// ═══════════════════════════════════════════════════════════════════════
	// STEP 1: FRAUD CHECK
	// ═══════════════════════════════════════════════════════════════════════
	updateStatus(domain.StatusFraudCheck)
	drainSignals()
	if cancelled {
		updateStatus(domain.StatusCancelled)
		return state, nil
	}

	fraudCtx := workflow.WithActivityOptions(ctx, workflow.ActivityOptions{
		TaskQueue:           "fraud-tq",
		StartToCloseTimeout: 10 * time.Second,
		RetryPolicy: &temporal.RetryPolicy{
			MaximumAttempts: 3,
		},
	})

	var fraudResult domain.FraudCheckResult
	err := workflow.ExecuteActivity(fraudCtx, activities.CheckFraud, domain.FraudCheckInput{
		Order:      order,
		CustomerID: order.CustomerID,
		IPAddress:  order.Metadata["ip_address"],
	}).Get(ctx, &fraudResult)
	if err != nil {
		state.Error = fmt.Sprintf("fraud check failed: %v", err)
		updateStatus(domain.StatusCancelled)
		return state, nil
	}

	state.FraudScore = fraudResult.Score

	if fraudResult.Score > 0.8 {
		// High fraud score - requires human review
		logger.Warn("High fraud score, awaiting review", "score", fraudResult.Score)
		state.addTimeline("FRAUD_REVIEW_REQUIRED", fmt.Sprintf("score=%.2f", fraudResult.Score))

		// Wait for approval signal with 4-hour timeout
		approvalCh := workflow.GetSignalChannel(ctx, "fraud-approval")
		timerCtx, cancelTimer := workflow.WithCancel(ctx)
		timer := workflow.NewTimer(timerCtx, 4*time.Hour)

		selector := workflow.NewSelector(ctx)
		approved := false

		selector.AddReceive(approvalCh, func(ch workflow.ReceiveChannel, more bool) {
			var decision struct{ Approved bool }
			ch.Receive(ctx, &decision)
			approved = decision.Approved
			cancelTimer()
		})
		selector.AddFuture(timer, func(f workflow.Future) {
			// Timeout - auto-reject
		})
		// Also check for cancellation during wait
		selector.AddReceive(cancelCh, func(ch workflow.ReceiveChannel, more bool) {
			var signal domain.CancelOrderSignal
			ch.Receive(ctx, &signal)
			cancelled = true
			cancelTimer()
		})
		selector.Select(ctx)

		if cancelled || !approved {
			updateStatus(domain.StatusCancelled)
			state.addTimeline("FRAUD_REJECTED", "")
			return state, nil
		}
	}

	// ═══════════════════════════════════════════════════════════════════════
	// STEP 2: PAYMENT PROCESSING (Child Workflow)
	// ═══════════════════════════════════════════════════════════════════════
	updateStatus(domain.StatusPaymentProcessing)
	drainSignals()
	if cancelled {
		updateStatus(domain.StatusCancelled)
		return state, nil
	}

	paymentChildOpts := workflow.ChildWorkflowOptions{
		WorkflowID:         fmt.Sprintf("payment-%s", order.ID),
		TaskQueue:          "payment-tq",
		WorkflowRunTimeout: 5 * time.Minute,
		RetryPolicy: &temporal.RetryPolicy{
			MaximumAttempts: 3,
		},
	}
	paymentChildCtx := workflow.WithChildOptions(ctx, paymentChildOpts)

	var paymentResult domain.PaymentResult
	err = workflow.ExecuteChildWorkflow(paymentChildCtx, PaymentProcessingWorkflow, domain.PaymentInput{
		OrderID:       order.ID,
		CustomerID:    order.CustomerID,
		Amount:        order.TotalAmount,
		Tax:           order.TaxAmount,
		PaymentMethod: order.PaymentMethod,
		IdempotencyKey: fmt.Sprintf("order-%s-payment", order.ID),
	}).Get(ctx, &paymentResult)
	if err != nil {
		state.Error = fmt.Sprintf("payment failed: %v", err)
		updateStatus(domain.StatusPaymentFailed)
		// Notify customer
		_ = workflow.ExecuteActivity(
			workflow.WithActivityOptions(ctx, workflow.ActivityOptions{
				TaskQueue: "notification-tq", StartToCloseTimeout: 10 * time.Second,
			}),
			activities.SendNotification, domain.Notification{
				CustomerID: order.CustomerID,
				Type:       "PAYMENT_FAILED",
				OrderID:    order.ID,
			},
		).Get(ctx, nil)
		return state, nil
	}

	state.PaymentRef = paymentResult.Reference
	state.addTimeline("PAYMENT_CAPTURED", paymentResult.Reference)

	// Add payment compensation
	compensations = append(compensations, compensation{
		name: "refund_payment",
		fn: func(compCtx workflow.Context) error {
			return workflow.ExecuteActivity(compCtx, activities.RefundPayment, domain.RefundRequest{
				PaymentRef:     paymentResult.Reference,
				Amount:         order.TotalAmount,
				Reason:         "order_cancelled",
				IdempotencyKey: fmt.Sprintf("order-%s-refund", order.ID),
			}).Get(compCtx, nil)
		},
	})

	// ═══════════════════════════════════════════════════════════════════════
	// STEP 3: INVENTORY RESERVATION (Fan-out to warehouses)
	// ═══════════════════════════════════════════════════════════════════════
	updateStatus(domain.StatusInventoryReserved)
	drainSignals()
	if cancelled {
		runCompensations(ctx, compensations, logger)
		updateStatus(domain.StatusCancelled)
		return state, nil
	}

	inventoryCtx := workflow.WithActivityOptions(ctx, workflow.ActivityOptions{
		TaskQueue:           "inventory-tq",
		StartToCloseTimeout: 15 * time.Second,
		RetryPolicy: &temporal.RetryPolicy{
			MaximumAttempts: 5,
			InitialInterval: 500 * time.Millisecond,
		},
	})

	// Reserve inventory for each item (can fan out)
	type reserveResult struct {
		ItemID         string
		ReservationRef string
		WarehouseID    string
		Err            error
	}

	resultCh := workflow.NewChannel(ctx)
	for _, item := range state.Items {
		itemCopy := item // capture
		workflow.Go(ctx, func(gCtx workflow.Context) {
			var res domain.InventoryReservation
			err := workflow.ExecuteActivity(inventoryCtx, activities.ReserveInventory, domain.ReserveRequest{
				ItemID:     itemCopy.ItemID,
				SKU:        itemCopy.SKU,
				Quantity:   itemCopy.Quantity,
				OrderID:    order.ID,
				CustomerID: order.CustomerID,
				ShipTo:     order.ShippingAddress,
			}).Get(gCtx, &res)
			resultCh.Send(gCtx, reserveResult{
				ItemID:         itemCopy.ItemID,
				ReservationRef: res.ReservationRef,
				WarehouseID:    res.WarehouseID,
				Err:            err,
			})
		})
	}

	// Collect results
	allReserved := true
	for i := 0; i < len(state.Items); i++ {
		var res reserveResult
		resultCh.Receive(ctx, &res)
		if res.Err != nil {
			logger.Error("Inventory reservation failed", "item", res.ItemID, "error", res.Err)
			allReserved = false
		} else {
			state.ReservationRefs[res.ItemID] = res.ReservationRef
			state.WarehouseAssignments[res.ItemID] = res.WarehouseID
		}
	}

	if !allReserved {
		// Handle backorder or partial availability
		logger.Warn("Not all items could be reserved")
		updateStatus(domain.StatusBackordered)

		// Wait for restock signal or timeout
		restockCh := workflow.GetSignalChannel(ctx, "inventory-restocked")
		selector := workflow.NewSelector(ctx)
		restocked := false

		selector.AddReceive(restockCh, func(ch workflow.ReceiveChannel, more bool) {
			ch.Receive(ctx, nil)
			restocked = true
		})
		selector.AddReceive(cancelCh, func(ch workflow.ReceiveChannel, more bool) {
			var signal domain.CancelOrderSignal
			ch.Receive(ctx, &signal)
			cancelled = true
		})
		selector.AddFuture(workflow.NewTimer(ctx, 72*time.Hour), func(f workflow.Future) {
			// Auto-cancel after 3 days of backorder
		})
		selector.Select(ctx)

		if cancelled || !restocked {
			// Release any reservations we did get
			for itemID, ref := range state.ReservationRefs {
				_ = workflow.ExecuteActivity(inventoryCtx, activities.ReleaseReservation, ref).Get(ctx, nil)
				delete(state.ReservationRefs, itemID)
			}
			runCompensations(ctx, compensations, logger)
			updateStatus(domain.StatusCancelled)
			return state, nil
		}
	}

	// Add inventory compensation
	compensations = append(compensations, compensation{
		name: "release_inventory",
		fn: func(compCtx workflow.Context) error {
			for _, ref := range state.ReservationRefs {
				_ = workflow.ExecuteActivity(compCtx, activities.ReleaseReservation, ref).Get(compCtx, nil)
			}
			return nil
		},
	})

	// ═══════════════════════════════════════════════════════════════════════
	// STEP 4: WAREHOUSE ASSIGNMENT & SHIPMENT PLANNING
	// ═══════════════════════════════════════════════════════════════════════
	updateStatus(domain.StatusWarehouseAssigned)

	// Group items by warehouse for split shipments
	warehouseGroups := groupItemsByWarehouse(state.Items, state.WarehouseAssignments)

	// Create shipments
	for warehouseID, items := range warehouseGroups {
		shipmentID := fmt.Sprintf("shp-%s-%s", order.ID, warehouseID)
		itemIDs := make([]string, len(items))
		for i, item := range items {
			itemIDs[i] = item.ItemID
		}
		state.Shipments[shipmentID] = &domain.Shipment{
			ShipmentID:  shipmentID,
			Items:       itemIDs,
			WarehouseID: warehouseID,
			Status:      "PENDING",
		}
	}

	if len(state.Shipments) > 1 {
		state.addTimeline("SPLIT_SHIPMENT", fmt.Sprintf("%d shipments", len(state.Shipments)))
	}

	// ═══════════════════════════════════════════════════════════════════════
	// STEP 5: FULFILLMENT - Child workflows per shipment
	// ═══════════════════════════════════════════════════════════════════════
	// Launch child workflow for each shipment
	shipmentFutures := make(map[string]workflow.ChildWorkflowFuture)
	for shipmentID, shipment := range state.Shipments {
		childOpts := workflow.ChildWorkflowOptions{
			WorkflowID:         fmt.Sprintf("shipment-%s", shipmentID),
			TaskQueue:          "warehouse-tq",
			WorkflowRunTimeout: 7 * 24 * time.Hour, // Up to 7 days for fulfillment
		}
		childCtx := workflow.WithChildOptions(ctx, childOpts)

		future := workflow.ExecuteChildWorkflow(childCtx, ShipmentFulfillmentWorkflow, domain.ShipmentInput{
			ShipmentID:      shipmentID,
			OrderID:         order.ID,
			WarehouseID:     shipment.WarehouseID,
			Items:           getItemsByIDs(state.Items, shipment.Items),
			ShippingAddress: order.ShippingAddress,
			Priority:        order.Priority,
			IsVIP:           order.IsVIP,
		})
		shipmentFutures[shipmentID] = future
	}

	// ═══════════════════════════════════════════════════════════════════════
	// STEP 6: WAIT FOR ALL SHIPMENTS (with signal handling)
	// ═══════════════════════════════════════════════════════════════════════
	completedShipments := 0
	totalShipments := len(shipmentFutures)

	for completedShipments < totalShipments && !cancelled {
		selector := workflow.NewSelector(ctx)

		// Wait for shipment completions
		for shipmentID, future := range shipmentFutures {
			sid := shipmentID
			f := future
			selector.AddChildWorkflowFuture(f, func(f workflow.ChildWorkflowFuture) {
				var result domain.ShipmentResult
				err := f.Get(ctx, &result)
				if err != nil {
					logger.Error("Shipment failed", "shipmentID", sid, "error", err)
					state.Shipments[sid].Status = "FAILED"
				} else {
					state.Shipments[sid].Status = "DELIVERED"
					state.Shipments[sid].TrackingNumber = result.TrackingNumber
					state.Shipments[sid].Carrier = result.Carrier
					state.Shipments[sid].ShippedAt = result.ShippedAt
					state.Shipments[sid].DeliveredAt = result.DeliveredAt
					state.TrackingNumbers[sid] = result.TrackingNumber
				}
				completedShipments++
				delete(shipmentFutures, sid)
			})
		}

		// Handle signals during fulfillment
		selector.AddReceive(cancelCh, func(ch workflow.ReceiveChannel, more bool) {
			var signal domain.CancelOrderSignal
			ch.Receive(ctx, &signal)
			logger.Info("Cancel requested during fulfillment", "reason", signal.Reason)
			cancelled = true
		})

		selector.AddReceive(modifyCh, func(ch workflow.ReceiveChannel, more bool) {
			var mod domain.ModifyOrderSignal
			ch.Receive(ctx, &mod)
			applyModification(state, mod)
		})

		selector.AddReceive(addressCh, func(ch workflow.ReceiveChannel, more bool) {
			var addr domain.AddressChangeSignal
			ch.Receive(ctx, &addr)
			// Can only change if shipments haven't shipped yet
			canChange := true
			for _, s := range state.Shipments {
				if s.Status == "SHIPPED" || s.Status == "DELIVERED" {
					canChange = false
					break
				}
			}
			if canChange {
				order.ShippingAddress = addr.NewAddress
				state.addTimeline("ADDRESS_CHANGED", addr.NewAddress.City)
				// Signal child workflows about address change
				for sid := range shipmentFutures {
					_ = workflow.SignalChildWorkflow(ctx, fmt.Sprintf("shipment-%s", sid), "", "address-change", addr.NewAddress)
				}
			}
		})

		selector.AddReceive(shipmentCh, func(ch workflow.ReceiveChannel, more bool) {
			var update domain.ShipmentUpdateSignal
			ch.Receive(ctx, &update)
			if s, ok := state.Shipments[update.ShipmentID]; ok {
				s.Status = update.Status
				state.addTimeline(fmt.Sprintf("SHIPMENT_%s", update.Status), update.ShipmentID)
			}
		})

		selector.Select(ctx)

		// Update overall status
		shipped := 0
		for _, s := range state.Shipments {
			if s.Status == "SHIPPED" || s.Status == "DELIVERED" {
				shipped++
			}
		}
		if shipped > 0 && shipped < totalShipments {
			updateStatus(domain.StatusPartiallyShipped)
		} else if shipped == totalShipments {
			updateStatus(domain.StatusShipped)
		}
	}

	if cancelled {
		// Cancel remaining shipments
		for sid := range shipmentFutures {
			_ = workflow.SignalChildWorkflow(ctx, fmt.Sprintf("shipment-%s", sid), "", "cancel", nil)
		}
		runCompensations(ctx, compensations, logger)
		updateStatus(domain.StatusCancelled)
		return state, nil
	}

	// ═══════════════════════════════════════════════════════════════════════
	// STEP 7: COMPLETION & NOTIFICATIONS
	// ═══════════════════════════════════════════════════════════════════════
	updateStatus(domain.StatusDelivered)

	// Send delivery confirmation
	notifyCtx := workflow.WithActivityOptions(ctx, workflow.ActivityOptions{
		TaskQueue:           "notification-tq",
		StartToCloseTimeout: 10 * time.Second,
		RetryPolicy:         &temporal.RetryPolicy{MaximumAttempts: 3},
	})
	_ = workflow.ExecuteActivity(notifyCtx, activities.SendNotification, domain.Notification{
		CustomerID: order.CustomerID,
		Type:       "ORDER_DELIVERED",
		OrderID:    order.ID,
		Data:       map[string]interface{}{"tracking": state.TrackingNumbers},
	}).Get(ctx, nil)

	// ═══════════════════════════════════════════════════════════════════════
	// STEP 8: POST-DELIVERY (wait for return window, handle returns)
	// ═══════════════════════════════════════════════════════════════════════
	// Keep workflow alive for return window (30 days)
	returnWindowTimer := workflow.NewTimer(ctx, 30*24*time.Hour)
	returnCh := workflow.GetSignalChannel(ctx, "return-requested")

	returnWindowOpen := true
	for returnWindowOpen {
		selector := workflow.NewSelector(ctx)

		selector.AddFuture(returnWindowTimer, func(f workflow.Future) {
			returnWindowOpen = false
		})

		selector.AddReceive(returnCh, func(ch workflow.ReceiveChannel, more bool) {
			var returnReq domain.ReturnRequest
			ch.Receive(ctx, &returnReq)
			// Launch return child workflow
			returnChildCtx := workflow.WithChildOptions(ctx, workflow.ChildWorkflowOptions{
				WorkflowID: fmt.Sprintf("return-%s-%s", order.ID, returnReq.ItemID),
				TaskQueue:  "returns-tq",
			})
			workflow.ExecuteChildWorkflow(returnChildCtx, ReturnProcessingWorkflow, returnReq)
			updateStatus(domain.StatusReturnInitiated)
		})

		selector.Select(ctx)
	}

	// Check history size - continue-as-new if needed for very long orders
	info := workflow.GetInfo(ctx)
	if info.GetCurrentHistoryLength() > 5000 {
		return state, workflow.NewContinueAsNewError(ctx, OrderFulfillmentPostDelivery, state)
	}

	state.addTimeline("WORKFLOW_COMPLETED", "return window closed")
	return state, nil
}

// ═══════════════════════════════════════════════════════════════════════════════
// CHILD WORKFLOW: Payment Processing
// ═══════════════════════════════════════════════════════════════════════════════

func PaymentProcessingWorkflow(ctx workflow.Context, input domain.PaymentInput) (*domain.PaymentResult, error) {
	logger := workflow.GetLogger(ctx)

	actOpts := workflow.ActivityOptions{
		StartToCloseTimeout: 30 * time.Second,
		HeartbeatTimeout:    10 * time.Second,
		RetryPolicy: &temporal.RetryPolicy{
			MaximumAttempts:    5,
			InitialInterval:    time.Second,
			BackoffCoefficient: 2.0,
			NonRetryableErrorTypes: []string{
				"CardDeclinedError",
				"InsufficientFundsError",
				"InvalidPaymentMethodError",
			},
		},
	}
	ctx = workflow.WithActivityOptions(ctx, actOpts)

	// Step 1: Authorize payment
	var authResult domain.PaymentAuthResult
	err := workflow.ExecuteActivity(ctx, activities.AuthorizePayment, input).Get(ctx, &authResult)
	if err != nil {
		return nil, fmt.Errorf("authorization failed: %w", err)
	}
	logger.Info("Payment authorized", "authRef", authResult.AuthorizationRef)

	// Step 2: Capture payment
	var captureResult domain.PaymentCaptureResult
	err = workflow.ExecuteActivity(ctx, activities.CapturePayment, domain.CaptureInput{
		AuthorizationRef: authResult.AuthorizationRef,
		Amount:           input.Amount,
		IdempotencyKey:   input.IdempotencyKey + "-capture",
	}).Get(ctx, &captureResult)
	if err != nil {
		// Void the authorization
		logger.Error("Capture failed, voiding authorization", "error", err)
		_ = workflow.ExecuteActivity(ctx, activities.VoidAuthorization, authResult.AuthorizationRef).Get(ctx, nil)
		return nil, fmt.Errorf("capture failed: %w", err)
	}

	return &domain.PaymentResult{
		Reference:   captureResult.Reference,
		Amount:      input.Amount,
		CapturedAt:  workflow.Now(ctx),
	}, nil
}

// ═══════════════════════════════════════════════════════════════════════════════
// CHILD WORKFLOW: Shipment Fulfillment
// ═══════════════════════════════════════════════════════════════════════════════

func ShipmentFulfillmentWorkflow(ctx workflow.Context, input domain.ShipmentInput) (*domain.ShipmentResult, error) {
	logger := workflow.GetLogger(ctx)
	logger.Info("Starting shipment fulfillment",
		"shipmentID", input.ShipmentID,
		"warehouse", input.WarehouseID,
		"items", len(input.Items),
	)

	warehouseOpts := workflow.ActivityOptions{
		StartToCloseTimeout: 5 * time.Minute,
		HeartbeatTimeout:    30 * time.Second,
		RetryPolicy: &temporal.RetryPolicy{
			MaximumAttempts: 5,
			InitialInterval: 2 * time.Second,
		},
	}
	ctx = workflow.WithActivityOptions(ctx, warehouseOpts)

	// Handle cancel/address change signals
	cancelCh := workflow.GetSignalChannel(ctx, "cancel")
	addressCh := workflow.GetSignalChannel(ctx, "address-change")
	address := input.ShippingAddress
	cancelled := false

	// Check for cancellation between steps
	checkCancel := func() bool {
		var signal interface{}
		if cancelCh.ReceiveAsync(&signal) {
			cancelled = true
			return true
		}
		// Check address changes
		var newAddr domain.Address
		for addressCh.ReceiveAsync(&newAddr) {
			address = newAddr
		}
		return false
	}

	// Step 1: Create pick list
	if checkCancel() {
		return nil, fmt.Errorf("cancelled before picking")
	}

	var pickResult domain.PickResult
	err := workflow.ExecuteActivity(ctx, activities.CreatePickList, domain.PickRequest{
		ShipmentID:  input.ShipmentID,
		WarehouseID: input.WarehouseID,
		Items:       input.Items,
		Priority:    input.Priority,
	}).Get(ctx, &pickResult)
	if err != nil {
		return nil, fmt.Errorf("pick list creation failed: %w", err)
	}

	// Step 2: Wait for picking completion (warehouse signals when done)
	pickingDoneCh := workflow.GetSignalChannel(ctx, "picking-done")
	pickingTimer := workflow.NewTimer(ctx, 4*time.Hour) // SLA: pick within 4 hours

	selector := workflow.NewSelector(ctx)
	pickingDone := false
	selector.AddReceive(pickingDoneCh, func(ch workflow.ReceiveChannel, more bool) {
		ch.Receive(ctx, nil)
		pickingDone = true
	})
	selector.AddReceive(cancelCh, func(ch workflow.ReceiveChannel, more bool) {
		ch.Receive(ctx, nil)
		cancelled = true
	})
	selector.AddFuture(pickingTimer, func(f workflow.Future) {
		logger.Warn("Picking SLA breached", "shipmentID", input.ShipmentID)
	})
	selector.Select(ctx)

	if cancelled {
		_ = workflow.ExecuteActivity(ctx, activities.CancelPick, pickResult.PickListID).Get(ctx, nil)
		return nil, fmt.Errorf("cancelled during picking")
	}
	if !pickingDone {
		// SLA breached but not cancelled - escalate and continue waiting
		_ = workflow.ExecuteActivity(ctx, activities.EscalatePickDelay, input.ShipmentID).Get(ctx, nil)
		pickingDoneCh.Receive(ctx, nil) // Block until actually done
	}

	// Step 3: Pack
	var packResult domain.PackResult
	err = workflow.ExecuteActivity(ctx, activities.PackShipment, domain.PackRequest{
		ShipmentID:  input.ShipmentID,
		PickListID:  pickResult.PickListID,
		Items:       input.Items,
	}).Get(ctx, &packResult)
	if err != nil {
		return nil, fmt.Errorf("packing failed: %w", err)
	}

	// Step 4: Generate shipping label
	if checkCancel() {
		return nil, fmt.Errorf("cancelled before shipping")
	}

	shippingOpts := workflow.ActivityOptions{
		TaskQueue:           "shipping-tq",
		StartToCloseTimeout: 30 * time.Second,
		RetryPolicy: &temporal.RetryPolicy{
			MaximumAttempts: 5,
			InitialInterval: time.Second,
		},
	}
	shippingCtx := workflow.WithActivityOptions(ctx, shippingOpts)

	var labelResult domain.ShippingLabelResult
	err = workflow.ExecuteActivity(shippingCtx, activities.GenerateShippingLabel, domain.LabelRequest{
		ShipmentID:  input.ShipmentID,
		OrderID:     input.OrderID,
		Address:     address,
		Weight:      packResult.TotalWeight,
		Dimensions:  packResult.Dimensions,
		IsVIP:       input.IsVIP,
	}).Get(ctx, &labelResult)
	if err != nil {
		return nil, fmt.Errorf("label generation failed: %w", err)
	}

	// Step 5: Hand off to carrier and track
	var handoffResult domain.CarrierHandoffResult
	err = workflow.ExecuteActivity(shippingCtx, activities.HandoffToCarrier, domain.HandoffRequest{
		ShipmentID:     input.ShipmentID,
		TrackingNumber: labelResult.TrackingNumber,
		Carrier:        labelResult.Carrier,
		WarehouseID:    input.WarehouseID,
	}).Get(ctx, &handoffResult)
	if err != nil {
		return nil, fmt.Errorf("carrier handoff failed: %w", err)
	}

	// Step 6: Track delivery (poll or receive webhooks via signal)
	trackingCh := workflow.GetSignalChannel(ctx, "tracking-update")
	delivered := false
	var deliveredAt time.Time

	for !delivered {
		selector := workflow.NewSelector(ctx)

		// Webhook-driven tracking updates
		selector.AddReceive(trackingCh, func(ch workflow.ReceiveChannel, more bool) {
			var update domain.TrackingUpdate
			ch.Receive(ctx, &update)
			if update.Status == "DELIVERED" {
				delivered = true
				deliveredAt = update.Timestamp
			}
		})

		// Fallback: poll carrier API every 6 hours
		selector.AddFuture(workflow.NewTimer(ctx, 6*time.Hour), func(f workflow.Future) {
			var status domain.TrackingStatus
			err := workflow.ExecuteActivity(shippingCtx, activities.PollTrackingStatus, labelResult.TrackingNumber).Get(ctx, &status)
			if err == nil && status.Status == "DELIVERED" {
				delivered = true
				deliveredAt = status.Timestamp
			}
		})

		selector.Select(ctx)
	}

	return &domain.ShipmentResult{
		ShipmentID:     input.ShipmentID,
		TrackingNumber: labelResult.TrackingNumber,
		Carrier:        labelResult.Carrier,
		ShippedAt:      handoffResult.ShippedAt,
		DeliveredAt:    deliveredAt,
	}, nil
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
	"go.temporal.io/sdk/temporal"
)

type OrderActivities struct {
	inventorySvc    InventoryServiceClient
	paymentSvc      PaymentServiceClient
	shippingSvc     ShippingServiceClient
	warehouseSvc    WarehouseServiceClient
	fraudSvc        FraudServiceClient
	notificationSvc NotificationServiceClient
}

// CheckFraud calls the fraud detection service
func (a *OrderActivities) CheckFraud(ctx context.Context, input domain.FraudCheckInput) (*domain.FraudCheckResult, error) {
	logger := activity.GetLogger(ctx)

	score, flags, err := a.fraudSvc.EvaluateOrder(ctx, FraudRequest{
		OrderID:     input.Order.ID,
		CustomerID:  input.CustomerID,
		Amount:      input.Order.TotalAmount.AmountCents,
		Currency:    input.Order.TotalAmount.Currency,
		IPAddress:   input.IPAddress,
		ItemCount:   len(input.Order.Items),
		ShipCountry: input.Order.ShippingAddress.Country,
		IsNewCustomer: input.Order.Metadata["is_new_customer"] == "true",
	})
	if err != nil {
		return nil, fmt.Errorf("fraud service error: %w", err)
	}

	logger.Info("Fraud check completed", "score", score, "flags", flags)
	return &domain.FraudCheckResult{
		Score:    score,
		Flags:    flags,
		Approved: score < 0.8,
	}, nil
}

// ReserveInventory reserves items from the nearest warehouse
func (a *OrderActivities) ReserveInventory(ctx context.Context, req domain.ReserveRequest) (*domain.InventoryReservation, error) {
	logger := activity.GetLogger(ctx)
	info := activity.GetInfo(ctx)

	logger.Info("Reserving inventory",
		"sku", req.SKU,
		"quantity", req.Quantity,
		"attempt", info.Attempt,
	)

	activity.RecordHeartbeat(ctx, fmt.Sprintf("reserving %s qty=%d", req.SKU, req.Quantity))

	// Find nearest warehouse with stock
	warehouse, err := a.inventorySvc.FindNearestAvailable(ctx, req.SKU, req.Quantity, req.ShipTo)
	if err != nil {
		if isOutOfStock(err) {
			return nil, temporal.NewNonRetryableApplicationError(
				fmt.Sprintf("out of stock: %s", req.SKU),
				"OutOfStockError",
				err,
			)
		}
		return nil, fmt.Errorf("inventory lookup failed: %w", err)
	}

	// Reserve
	reservation, err := a.inventorySvc.Reserve(ctx, ReservationRequest{
		SKU:         req.SKU,
		Quantity:    req.Quantity,
		WarehouseID: warehouse.ID,
		OrderID:     req.OrderID,
		TTL:         30 * time.Minute, // Auto-release if not fulfilled within 30 min
	})
	if err != nil {
		return nil, fmt.Errorf("reservation failed: %w", err)
	}

	return &domain.InventoryReservation{
		ReservationRef: reservation.Ref,
		WarehouseID:    warehouse.ID,
		ExpiresAt:      reservation.ExpiresAt,
	}, nil
}

// ReleaseReservation releases a previously held inventory reservation
func (a *OrderActivities) ReleaseReservation(ctx context.Context, reservationRef string) error {
	return a.inventorySvc.ReleaseReservation(ctx, reservationRef)
}

// AuthorizePayment places a hold on the payment method
func (a *OrderActivities) AuthorizePayment(ctx context.Context, input domain.PaymentInput) (*domain.PaymentAuthResult, error) {
	activity.RecordHeartbeat(ctx, "authorizing")

	result, err := a.paymentSvc.Authorize(ctx, PaymentAuthRequest{
		CustomerID:     input.CustomerID,
		PaymentMethod:  input.PaymentMethod.TokenID,
		AmountCents:    input.Amount.AmountCents,
		Currency:       input.Amount.Currency,
		OrderID:        input.OrderID,
		IdempotencyKey: input.IdempotencyKey + "-auth",
	})
	if err != nil {
		if isCardDeclined(err) {
			return nil, temporal.NewNonRetryableApplicationError(
				"card declined", "CardDeclinedError", err,
			)
		}
		return nil, fmt.Errorf("payment authorization error: %w", err)
	}

	return &domain.PaymentAuthResult{
		AuthorizationRef: result.AuthRef,
		ExpiresAt:        result.ExpiresAt,
	}, nil
}

// CapturePayment captures a previously authorized payment
func (a *OrderActivities) CapturePayment(ctx context.Context, input domain.CaptureInput) (*domain.PaymentCaptureResult, error) {
	result, err := a.paymentSvc.Capture(ctx, PaymentCaptureRequest{
		AuthorizationRef: input.AuthorizationRef,
		AmountCents:      input.Amount.AmountCents,
		IdempotencyKey:   input.IdempotencyKey,
	})
	if err != nil {
		return nil, fmt.Errorf("capture failed: %w", err)
	}

	return &domain.PaymentCaptureResult{
		Reference:  result.CaptureRef,
		CapturedAt: time.Now(),
	}, nil
}

// GenerateShippingLabel creates a shipping label via carrier API
func (a *OrderActivities) GenerateShippingLabel(ctx context.Context, req domain.LabelRequest) (*domain.ShippingLabelResult, error) {
	activity.RecordHeartbeat(ctx, "generating_label")

	// Select carrier based on destination, weight, VIP status
	carrier := a.shippingSvc.SelectCarrier(ctx, CarrierSelectionInput{
		Destination: req.Address,
		Weight:      req.Weight,
		Dimensions:  req.Dimensions,
		IsVIP:       req.IsVIP,
	})

	label, err := a.shippingSvc.GenerateLabel(ctx, LabelGenRequest{
		Carrier:    carrier,
		FromAddr:   getWarehouseAddress(req.ShipmentID),
		ToAddr:     req.Address,
		Weight:     req.Weight,
		Dimensions: req.Dimensions,
		ServiceLevel: selectServiceLevel(req.IsVIP),
	})
	if err != nil {
		return nil, fmt.Errorf("label generation failed: %w", err)
	}

	return &domain.ShippingLabelResult{
		TrackingNumber: label.TrackingNumber,
		Carrier:        carrier,
		LabelURL:       label.LabelPDFURL,
		EstDelivery:    label.EstimatedDelivery,
	}, nil
}

// SendNotification sends customer notifications via appropriate channel
func (a *OrderActivities) SendNotification(ctx context.Context, notif domain.Notification) error {
	return a.notificationSvc.Send(ctx, notif)
}

// RefundPayment issues a refund for a captured payment
func (a *OrderActivities) RefundPayment(ctx context.Context, req domain.RefundRequest) error {
	_, err := a.paymentSvc.Refund(ctx, RefundRequest{
		PaymentRef:     req.PaymentRef,
		AmountCents:    req.Amount.AmountCents,
		Reason:         req.Reason,
		IdempotencyKey: req.IdempotencyKey,
	})
	return err
}
```

### Helper Functions

```go
package workflows

import (
	"go.temporal.io/sdk/workflow"
)

type compensation struct {
	name string
	fn   func(workflow.Context) error
}

func runCompensations(ctx workflow.Context, comps []compensation, logger workflow.Logger) {
	compCtx, _ := workflow.NewDisconnectedContext(ctx)
	compCtx = workflow.WithActivityOptions(compCtx, workflow.ActivityOptions{
		StartToCloseTimeout:    60 * time.Second,
		ScheduleToCloseTimeout: 5 * time.Minute,
		RetryPolicy: &temporal.RetryPolicy{
			MaximumAttempts:    10,
			InitialInterval:    time.Second,
			BackoffCoefficient: 2.0,
		},
	})

	for i := len(comps) - 1; i >= 0; i-- {
		logger.Info("Running compensation", "name", comps[i].name, "index", i)
		if err := comps[i].fn(compCtx); err != nil {
			logger.Error("Compensation failed", "name", comps[i].name, "error", err)
		}
	}
}

func groupItemsByWarehouse(items []domain.OrderItem, assignments map[string]string) map[string][]domain.OrderItem {
	groups := make(map[string][]domain.OrderItem)
	for _, item := range items {
		wh := assignments[item.ItemID]
		groups[wh] = append(groups[wh], item)
	}
	return groups
}

func getItemsByIDs(allItems []domain.OrderItem, ids []string) []domain.OrderItem {
	idSet := make(map[string]bool)
	for _, id := range ids {
		idSet[id] = true
	}
	var result []domain.OrderItem
	for _, item := range allItems {
		if idSet[item.ItemID] {
			result = append(result, item)
		}
	}
	return result
}

func applyModification(state *domain.OrderState, mod domain.ModifyOrderSignal) {
	modification := domain.Modification{
		Type:        mod.Type,
		RequestedAt: time.Now(),
	}

	switch mod.Type {
	case "remove_item":
		if state.Status <= domain.StatusInventoryReserved {
			// Can still remove items
			for i, item := range state.Items {
				if item.ItemID == mod.ItemID {
					state.Items = append(state.Items[:i], state.Items[i+1:]...)
					modification.Applied = true
					modification.Details = fmt.Sprintf("removed item %s", mod.ItemID)
					break
				}
			}
		} else {
			modification.Applied = false
			modification.Reason = "order already in fulfillment"
		}
	case "change_quantity":
		if state.Status <= domain.StatusInventoryReserved {
			for i, item := range state.Items {
				if item.ItemID == mod.ItemID {
					state.Items[i].Quantity = mod.NewQty
					modification.Applied = true
					modification.Details = fmt.Sprintf("changed qty to %d", mod.NewQty)
					break
				}
			}
		}
	}

	state.ModificationLog = append(state.ModificationLog, modification)
}

func (s *OrderState) addTimeline(event, details string) {
	s.Timeline = append(s.Timeline, domain.TimelineEvent{
		Event:     event,
		Timestamp: time.Now(), // Note: in real code, use workflow.Now(ctx)
		Details:   details,
	})
}
```

---

## Advanced Patterns

### Pattern 1: Fan-Out to Multiple Warehouses

```go
// When an order has items across multiple warehouses, we create
// parallel shipment workflows - each warehouse independently picks,
// packs, and ships their portion.

func FanOutFulfillment(ctx workflow.Context, order domain.Order, warehouseGroups map[string][]domain.OrderItem) error {
	// Launch all shipments in parallel
	futures := make(map[string]workflow.ChildWorkflowFuture)
	for warehouseID, items := range warehouseGroups {
		childOpts := workflow.ChildWorkflowOptions{
			WorkflowID:            fmt.Sprintf("ship-%s-%s", order.ID, warehouseID),
			TaskQueue:             "warehouse-tq",
			ParentClosePolicy:     enums.PARENT_CLOSE_POLICY_REQUEST_CANCEL,
			WorkflowRunTimeout:    7 * 24 * time.Hour,
		}
		childCtx := workflow.WithChildOptions(ctx, childOpts)
		futures[warehouseID] = workflow.ExecuteChildWorkflow(childCtx, ShipmentFulfillmentWorkflow, domain.ShipmentInput{
			WarehouseID: warehouseID,
			Items:       items,
			OrderID:     order.ID,
		})
	}

	// Wait for all, track partial completions
	results := make(map[string]*domain.ShipmentResult)
	errors := make(map[string]error)

	for warehouseID, future := range futures {
		var result domain.ShipmentResult
		err := future.Get(ctx, &result)
		if err != nil {
			errors[warehouseID] = err
		} else {
			results[warehouseID] = &result
		}
	}

	// Handle partial failures
	if len(errors) > 0 && len(results) > 0 {
		// Some shipped, some failed - partial fulfillment
		// Notify customer about partial shipment
	}

	return nil
}
```

### Pattern 2: Human-in-the-Loop for Fraud Review

```go
// Fraud review uses signal + timer pattern for human decision with timeout
func WaitForFraudReview(ctx workflow.Context, orderID string, score float64) (bool, error) {
	logger := workflow.GetLogger(ctx)

	// Notify fraud team
	_ = workflow.ExecuteActivity(ctx, NotifyFraudTeam, FraudAlert{
		OrderID:   orderID,
		Score:     score,
		Dashboard: fmt.Sprintf("https://fraud.internal/review/%s", orderID),
	}).Get(ctx, nil)

	// Wait for decision
	approvalCh := workflow.GetSignalChannel(ctx, "fraud-decision")

	// Escalation timers
	escalation1 := workflow.NewTimer(ctx, 30*time.Minute)   // Escalate after 30 min
	escalation2 := workflow.NewTimer(ctx, 2*time.Hour)      // Auto-reject after 2 hours

	for {
		selector := workflow.NewSelector(ctx)

		selector.AddReceive(approvalCh, func(ch workflow.ReceiveChannel, more bool) {
			var decision FraudDecision
			ch.Receive(ctx, &decision)
			logger.Info("Fraud decision received", "approved", decision.Approved, "reviewer", decision.ReviewerID)
		})

		selector.AddFuture(escalation1, func(f workflow.Future) {
			_ = workflow.ExecuteActivity(ctx, EscalateFraudReview, orderID).Get(ctx, nil)
		})

		selector.AddFuture(escalation2, func(f workflow.Future) {
			logger.Warn("Fraud review timed out, auto-rejecting")
		})

		selector.Select(ctx)
		// Process result...
		break
	}

	return false, nil
}
```

### Pattern 3: Continue-As-New for Long Orders

```go
// International orders can be in-flight for months.
// Use continue-as-new to prevent history from growing too large.

func OrderFulfillmentPostDelivery(ctx workflow.Context, state *domain.OrderState) (*domain.OrderState, error) {
	// This workflow handles the post-delivery phase (returns, reviews)
	// It was continued-as-new from the main workflow

	info := workflow.GetInfo(ctx)
	logger := workflow.GetLogger(ctx)

	// Register same query handlers
	_ = workflow.SetQueryHandler(ctx, QueryGetOrderState, func() (*domain.OrderState, error) {
		return state, nil
	})

	returnCh := workflow.GetSignalChannel(ctx, "return-requested")
	reviewCh := workflow.GetSignalChannel(ctx, "review-submitted")

	// Return window: 30 days from delivery
	returnDeadline := workflow.NewTimer(ctx, 30*24*time.Hour)

	for {
		selector := workflow.NewSelector(ctx)

		selector.AddReceive(returnCh, func(ch workflow.ReceiveChannel, more bool) {
			var req domain.ReturnRequest
			ch.Receive(ctx, &req)
			// Process return...
		})

		selector.AddReceive(reviewCh, func(ch workflow.ReceiveChannel, more bool) {
			var review domain.ReviewSubmission
			ch.Receive(ctx, &review)
			// Record review...
		})

		selector.AddFuture(returnDeadline, func(f workflow.Future) {
			logger.Info("Return window closed")
		})

		selector.Select(ctx)

		// Check if we should continue-as-new again
		if info.GetCurrentHistoryLength() > 2000 {
			return state, workflow.NewContinueAsNewError(ctx, OrderFulfillmentPostDelivery, state)
		}

		break // Window closed
	}

	return state, nil
}
```

### Pattern 4: Versioning for Mid-Flight Updates

```go
// When you need to change workflow logic while orders are in-flight:
func OrderFulfillmentWorkflowVersioned(ctx workflow.Context, order domain.Order) (*domain.OrderState, error) {
	// Version 1 → 2: Added gift wrapping step
	v := workflow.GetVersion(ctx, "add-gift-wrapping", workflow.DefaultVersion, 2)

	// ... existing steps ...

	if v >= 1 {
		// v1+: Added tax calculation step
		err := workflow.ExecuteActivity(ctx, CalculateTax, order).Get(ctx, nil)
		if err != nil {
			return nil, err
		}
	}

	if v >= 2 {
		// v2+: Added gift wrapping
		if order.Metadata["gift_wrap"] == "true" {
			err := workflow.ExecuteActivity(ctx, ApplyGiftWrapping, order.ID).Get(ctx, nil)
			if err != nil {
				return nil, err
			}
		}
	}

	// ... continue with fulfillment ...
	return nil, nil
}
```

---

## Failure Scenarios

### Scenario 1: Inventory Service Down for 2 Hours

```
Timeline:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
t=0min   │ ReserveInventory activity starts
t=0.5s   │ Attempt 1: inventory service returns 503 → retry
t=1.5s   │ Attempt 2: inventory service returns 503 → retry
t=3.5s   │ Attempt 3: inventory service returns 503 → retry
t=7.5s   │ Attempt 4: timeout → retry
t=15.5s  │ Attempt 5: 503 → MaximumAttempts reached → activity FAILS
         │
         │ BUT: ScheduleToCloseTimeout is 30 minutes, RetryPolicy continues...
         │ Activity is re-scheduled after brief backoff
         │
t=16s    │ New activity task: attempts start over
t=16-32s │ 5 more attempts, all fail
...      │ This pattern continues...
         │
t=120min │ Inventory service comes back online
t=120min │ Next attempt succeeds! Reservation confirmed.
t=121min │ Workflow continues to shipping...
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

KEY: The workflow AUTOMATICALLY retries. No human intervention needed.
     Payment was already captured - it stays captured during the wait.
     The customer sees "Processing" status the whole time.
     If ScheduleToCloseTimeout (30min) is breached → workflow can decide
     to release payment hold and notify customer.
```

### Scenario 2: Payment Declined After Inventory Reserved

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
t=0s   │ Inventory reserved for 3 items (reservationRefs stored in state)
t=1s   │ PaymentProcessingWorkflow (child) starts
t=2s   │ AuthorizePayment → "CardDeclinedError" (non-retryable)
t=2s   │ Child workflow returns error to parent
t=3s   │ Parent detects payment failure
t=3s   │ COMPENSATION: ReleaseReservation called for each item
t=3.5s │ All 3 reservations released
t=4s   │ Status updated to PAYMENT_FAILED
t=4s   │ Notification sent: "Payment failed, please update payment method"
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

RESULT: Inventory immediately available for other orders.
        No money charged. Clean state.
```

### Scenario 3: Customer Modifies Order During Payment Processing

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
t=0s   │ Order has 5 items, total $250
t=1s   │ Fraud check passes
t=2s   │ PaymentProcessingWorkflow (child) starts, authorizing $250
t=3s   │ Customer sends ModifyOrder signal: remove item worth $50
       │
       │ Signal is BUFFERED in the channel - workflow is busy with payment
       │
t=5s   │ Payment authorized for $250 (original amount)
t=5s   │ Payment captured for $250
t=6s   │ Parent receives child result
t=6s   │ Parent processes buffered signal: removes item from state
       │
       │ PROBLEM: We charged $250 but order is now $200
       │
       │ SOLUTION: After inventory reservation, detect discrepancy:
       │ if chargedAmount != currentOrderTotal:
       │   issue partial refund for difference ($50)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

DESIGN DECISION: This is why signals are drained between steps.
Alternative: Reject modifications during payment processing.
```

### Scenario 4: Flash Sale - 50K Orders/Minute

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Normal load:  1,400 orders/min → 15 order workers handle easily
Flash sale:   50,000 orders/min → need to scale

TEMPORAL HANDLES THIS:
1. Orders queue in task queue - never lost
2. schedule_to_start_latency increases (workers saturated)
3. HPA detects worker CPU > 70% → scales to 80 pods
4. New workers poll same task queue → immediate capacity
5. Backlog clears within minutes

PROTECTION LAYERS:
- Frontend rate limiting: 60K/min max per namespace
- Task queue partitioning: work spread across matching nodes
- Inventory semaphore: max 1000 concurrent reservation calls
- Payment rate limit: max 500 concurrent authorizations

SCALING TIMELINE:
t=0      │ Flash sale starts, 50K/min orders arrive
t=0-30s  │ Existing 15 workers at max capacity
t=30s    │ schedule_to_start_latency > 5s → alert fires
t=30s    │ K8s HPA scales order workers: 15 → 45 pods
t=90s    │ New pods ready, polling task queue
t=90-180s│ Backlog drains, latency normalizes
t=5min   │ All orders processing normally
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## Production Configuration

### Task Queue Strategy

```go
// Separate task queues per domain allows independent scaling
const (
	OrderOrchestrationTQ = "order-orchestration-tq"  // Main workflow logic
	PaymentTQ            = "payment-tq"              // Payment processing
	InventoryTQ          = "inventory-tq"            // Stock management
	ShippingTQ           = "shipping-tq"             // Label gen, tracking
	WarehouseTQ          = "warehouse-tq"            // WMS integration
	FraudTQ              = "fraud-tq"                // Fraud scoring
	NotificationTQ       = "notification-tq"         // Emails, SMS, push
	ReturnsTQ            = "returns-tq"              // Return processing
)

// Worker fleet configuration
var WorkerConfigs = map[string]worker.Options{
	OrderOrchestrationTQ: {
		MaxConcurrentWorkflowTaskExecutionSize: 500,
		MaxConcurrentActivityExecutionSize:     100,
		MaxConcurrentWorkflowTaskPollers:       8,
		MaxConcurrentActivityTaskPollers:       4,
	},
	PaymentTQ: {
		MaxConcurrentActivityExecutionSize: 200,
		MaxConcurrentActivityTaskPollers:   15,
	},
	InventoryTQ: {
		MaxConcurrentActivityExecutionSize: 300, // High throughput needed
		MaxConcurrentActivityTaskPollers:   20,
	},
	WarehouseTQ: {
		MaxConcurrentWorkflowTaskExecutionSize: 100,
		MaxConcurrentActivityExecutionSize:     50,
		MaxConcurrentWorkflowTaskPollers:       4,
	},
}
```

### Kubernetes HPA Configuration

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: order-workers-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: order-workers
  minReplicas: 10
  maxReplicas: 100
  metrics:
    - type: Pods
      pods:
        metric:
          name: temporal_worker_task_slots_available
        target:
          type: AverageValue
          averageValue: "50"  # Scale up when < 50 slots available
    - type: External
      external:
        metric:
          name: temporal_schedule_to_start_latency_p99
          selector:
            matchLabels:
              task_queue: order-orchestration-tq
        target:
          type: Value
          value: "2000"  # Scale up when p99 > 2s
```

### Timeout Hierarchy

```
OrderFulfillmentWorkflow: WorkflowRunTimeout = 90 days (international orders)
│
├── FraudCheck Activity: Start-to-Close = 10s, S2S = 5s
├── PaymentProcessing Child: WorkflowRunTimeout = 5 min
│   ├── Authorize Activity: S2C = 30s, Heartbeat = 10s
│   └── Capture Activity: S2C = 30s
├── ReserveInventory Activity: S2C = 15s, Schedule-to-Close = 30 min
├── ShipmentFulfillment Child: WorkflowRunTimeout = 7 days
│   ├── CreatePickList Activity: S2C = 5 min
│   ├── PackShipment Activity: S2C = 5 min
│   ├── GenerateLabel Activity: S2C = 30s
│   └── PollTracking Activity: S2C = 10s (runs every 6 hours)
└── Notification Activity: S2C = 10s
```
