# Problem 9: Event-Driven Order Processing with Real-Time Updates

## The Problem

Modern e-commerce order processing requires:

- Process order lifecycle events from Kafka/EventBridge (millions of events/day)
- Maintain running order state across 50+ event types
- Support real-time queries on order state (customer support tools)
- Handle out-of-order events (network delays, multiple producers)
- Correlate events across multiple streams (payment, inventory, shipping)
- Push real-time updates to customers (WebSocket/push notifications)
- SLA monitoring: alert if order is stuck (no progress in X time)
- Handle duplicate events (at-least-once delivery from Kafka)

## Why Temporal for Event Processing?

Traditional event processing (Kafka Streams, Flink) handles stateless transformations well, but complex order orchestration needs:

| Requirement | Kafka Streams | Flink | Temporal |
|-------------|---------------|-------|----------|
| Long-running state (days) | RocksDB (fragile) | Checkpoints | Durable by design |
| Human intervention | Not possible | Not possible | Signals + queries |
| Timer-based SLA | Windowing hacks | Processing time windows | Native timers |
| Ad-hoc queries on state | Custom stores | Custom | Query handlers |
| Retry with backoff | Application code | Application code | Built-in retry policies |
| State recovery after crash | Reprocess topic | From checkpoint | Automatic replay |

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                  Event-Driven Order Processing Architecture                   │
└─────────────────────────────────────────────────────────────────────────────┘

                    Event Sources
┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│   Payment    │ │  Inventory   │ │   Shipping   │ │   Returns    │
│   Service    │ │   Service    │ │   Service    │ │   Service    │
└──────┬───────┘ └──────┬───────┘ └──────┬───────┘ └──────┬───────┘
       │                │                │                │
       ▼                ▼                ▼                ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Apache Kafka                                          │
│                                                                               │
│  ┌────────────┐  ┌─────────────┐  ┌─────────────┐  ┌────────────┐          │
│  │  payments  │  │  inventory  │  │  shipments  │  │  returns   │          │
│  │   topic    │  │    topic    │  │    topic    │  │   topic    │          │
│  └────────────┘  └─────────────┘  └─────────────┘  └────────────┘          │
└─────────────────────────────────────────────────────────────────────────────┘
       │                │                │                │
       └────────────────┴────────────────┴────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                     Event Router (Kafka Consumer Group)                       │
│                                                                               │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  1. Consume event from Kafka                                         │    │
│  │  2. Extract order_id from event                                      │    │
│  │  3. Signal workflow: client.SignalWorkflow(order_id, event)          │    │
│  │  4. If workflow doesn't exist: StartWorkflow + Signal (signal-with-  │    │
│  │     start)                                                           │    │
│  │  5. Commit Kafka offset after signal confirmed                       │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
                                │
                                ▼ (Signal per event)
┌─────────────────────────────────────────────────────────────────────────────┐
│                     Temporal Cluster                                          │
│                                                                               │
│  ┌───────────────────────────────────────────────────────────────────┐      │
│  │         OrderEventProcessorWorkflow (one per order)                │      │
│  │                                                                     │      │
│  │  State:                                                             │      │
│  │    - Current status (placed, paid, picking, shipped, delivered)    │      │
│  │    - Payment info (amount, method, status)                         │      │
│  │    - Inventory reservations                                         │      │
│  │    - Shipment tracking                                              │      │
│  │    - Event history (all events received)                           │      │
│  │    - Timers (SLA deadlines)                                         │      │
│  │                                                                     │      │
│  │  Signals: OrderEvent (any event type)                              │      │
│  │  Queries: GetState, GetHistory, GetETA                             │      │
│  │  Updates: CancelOrder, ModifyOrder (with validation)               │      │
│  └───────────────────────────────────────────────────────────────────┘      │
│                                                                               │
│  Millions of concurrent workflow executions (one per active order)           │
└─────────────────────────────────────────────────────────────────────────────┘
                                │
                                │ (On state change)
                                ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                     Notification Fan-out                                      │
│                                                                               │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐           │
│  │ WebSocket  │  │   Push     │  │   Email    │  │   SMS      │           │
│  │ (Real-time)│  │ (Mobile)   │  │            │  │            │           │
│  └────────────┘  └────────────┘  └────────────┘  └────────────┘           │
└─────────────────────────────────────────────────────────────────────────────┘


┌─────────────────────────────────────────────────────────────────────────────┐
│                     Order State Machine                                       │
│                                                                               │
│  ┌────────┐    PaymentReceived    ┌──────┐   InventoryReserved   ┌───────┐ │
│  │ PLACED │──────────────────────▶│ PAID │─────────────────────▶│PICKING│ │
│  └────────┘                       └──────┘                       └───────┘ │
│       │                                │                             │      │
│       │ PaymentFailed                  │ RefundInitiated             │      │
│       ▼                                ▼                             ▼      │
│  ┌────────┐                       ┌────────┐                   ┌────────┐  │
│  │CANCELLED│                      │REFUNDING│                   │ PACKED │  │
│  └────────┘                       └────────┘                   └────────┘  │
│                                                                      │      │
│                                                    ShipmentCreated   │      │
│                                                                      ▼      │
│                                                                 ┌────────┐  │
│       DeliveryAttempted(failed)         DeliveryConfirmed       │SHIPPED │  │
│       ┌─────────────────────────────────────────────────────────┤        │  │
│       │                                        │                └────────┘  │
│       ▼                                        ▼                            │
│  ┌──────────┐                            ┌───────────┐                      │
│  │DELIVERY  │                            │ DELIVERED │                      │
│  │ FAILED   │                            └───────────┘                      │
│  └──────────┘                                  │                            │
│                                                │ ReturnInitiated            │
│                                                ▼                            │
│                                          ┌──────────┐                       │
│                                          │ RETURNED │                       │
│                                          └──────────┘                       │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Complete Go Implementation

```go
package orders

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"sort"
	"time"

	"go.temporal.io/sdk/activity"
	"go.temporal.io/sdk/client"
	"go.temporal.io/sdk/temporal"
	"go.temporal.io/sdk/workflow"
)

// ─────────────────────────────────────────────────────────────────────────────
// Domain Types
// ─────────────────────────────────────────────────────────────────────────────

type OrderStatus string

const (
	StatusPlaced         OrderStatus = "placed"
	StatusPaid           OrderStatus = "paid"
	StatusPicking        OrderStatus = "picking"
	StatusPacked         OrderStatus = "packed"
	StatusShipped        OrderStatus = "shipped"
	StatusDelivered      OrderStatus = "delivered"
	StatusCancelled      OrderStatus = "cancelled"
	StatusRefunding      OrderStatus = "refunding"
	StatusDeliveryFailed OrderStatus = "delivery_failed"
	StatusReturned       OrderStatus = "returned"
)

type EventType string

const (
	EventOrderPlaced        EventType = "order.placed"
	EventPaymentReceived    EventType = "payment.received"
	EventPaymentFailed      EventType = "payment.failed"
	EventInventoryReserved  EventType = "inventory.reserved"
	EventInventoryFailed    EventType = "inventory.failed"
	EventShipmentCreated    EventType = "shipment.created"
	EventShipmentPickedUp   EventType = "shipment.picked_up"
	EventDeliveryAttempted  EventType = "delivery.attempted"
	EventDeliveryConfirmed  EventType = "delivery.confirmed"
	EventDeliveryFailed     EventType = "delivery.failed"
	EventReturnInitiated    EventType = "return.initiated"
	EventReturnReceived     EventType = "return.received"
	EventRefundInitiated    EventType = "refund.initiated"
	EventRefundCompleted    EventType = "refund.completed"
	EventCancelRequested    EventType = "cancel.requested"
)

type OrderEvent struct {
	EventID     string         `json:"event_id"`
	EventType   EventType      `json:"event_type"`
	OrderID     string         `json:"order_id"`
	Timestamp   time.Time      `json:"timestamp"`
	Data        map[string]any `json:"data"`
	Source      string         `json:"source"`
	Version     int            `json:"version"` // For schema evolution
}

type OrderState struct {
	OrderID         string            `json:"order_id"`
	CustomerID      string            `json:"customer_id"`
	Status          OrderStatus       `json:"status"`
	Items           []OrderItem       `json:"items"`
	TotalAmount     float64           `json:"total_amount"`
	Currency        string            `json:"currency"`
	PaymentInfo     *PaymentInfo      `json:"payment_info"`
	ShipmentInfo    *ShipmentInfo     `json:"shipment_info"`
	DeliveryInfo    *DeliveryInfo     `json:"delivery_info"`
	EventHistory    []OrderEvent      `json:"event_history"`
	ProcessedEvents map[string]bool   `json:"processed_events"` // Deduplication
	CreatedAt       time.Time         `json:"created_at"`
	UpdatedAt       time.Time         `json:"updated_at"`
	SLADeadlines    map[string]time.Time `json:"sla_deadlines"`
	Metadata        map[string]string `json:"metadata"`

	// Buffered out-of-order events
	BufferedEvents  []OrderEvent `json:"buffered_events"`
}

type OrderItem struct {
	SKU      string  `json:"sku"`
	Name     string  `json:"name"`
	Quantity int     `json:"quantity"`
	Price    float64 `json:"price"`
}

type PaymentInfo struct {
	TransactionID string    `json:"transaction_id"`
	Method        string    `json:"method"`
	Amount        float64   `json:"amount"`
	Status        string    `json:"status"`
	PaidAt        time.Time `json:"paid_at"`
}

type ShipmentInfo struct {
	TrackingNumber string    `json:"tracking_number"`
	Carrier        string    `json:"carrier"`
	ShippedAt      time.Time `json:"shipped_at"`
	EstimatedDelivery time.Time `json:"estimated_delivery"`
}

type DeliveryInfo struct {
	DeliveredAt     time.Time `json:"delivered_at"`
	ReceivedBy      string    `json:"received_by"`
	Attempts        int       `json:"attempts"`
	LastAttemptAt   time.Time `json:"last_attempt_at"`
}

type NotificationRequest struct {
	OrderID    string      `json:"order_id"`
	CustomerID string      `json:"customer_id"`
	Type       string      `json:"type"` // "status_update", "delivery_eta", "delay_alert"
	Channel    string      `json:"channel"` // "push", "email", "sms", "websocket"
	Payload    map[string]any `json:"payload"`
}

// ─────────────────────────────────────────────────────────────────────────────
// Main Order Workflow
// ─────────────────────────────────────────────────────────────────────────────

func OrderEventProcessorWorkflow(ctx workflow.Context, initialEvent OrderEvent) error {
	logger := workflow.GetLogger(ctx)

	// Initialize order state
	state := &OrderState{
		OrderID:         initialEvent.OrderID,
		Status:          StatusPlaced,
		ProcessedEvents: make(map[string]bool),
		SLADeadlines:    make(map[string]time.Time),
		Metadata:        make(map[string]string),
		CreatedAt:       workflow.Now(ctx),
		UpdatedAt:       workflow.Now(ctx),
	}

	// Extract customer ID from initial event
	if cid, ok := initialEvent.Data["customer_id"].(string); ok {
		state.CustomerID = cid
	}

	// Process the initial event
	processEvent(state, initialEvent, workflow.Now(ctx))

	// Register query handlers
	registerQueryHandlers(ctx, state)

	// Register update handlers (Temporal Updates for validated mutations)
	registerUpdateHandlers(ctx, state)

	// Set search attributes for visibility
	_ = workflow.UpsertSearchAttributes(ctx, map[string]interface{}{
		"OrderID":    state.OrderID,
		"CustomerID": state.CustomerID,
		"Status":     string(state.Status),
	})

	// Set initial SLA timers
	// - Payment must be received within 30 minutes
	// - Shipment must be created within 48 hours of payment
	state.SLADeadlines["payment"] = workflow.Now(ctx).Add(30 * time.Minute)
	state.SLADeadlines["shipment"] = workflow.Now(ctx).Add(48 * time.Hour)

	// Activity options for notifications
	notifyCtx := workflow.WithActivityOptions(ctx, workflow.ActivityOptions{
		StartToCloseTimeout: 10 * time.Second,
		RetryPolicy: &temporal.RetryPolicy{
			MaximumAttempts: 3,
		},
	})

	// Event processing loop
	eventCh := workflow.GetSignalChannel(ctx, "order_event")
	eventsProcessed := 0
	const maxEventsBeforeContinueAsNew = 500

	for {
		// Create SLA timer for next deadline
		nextDeadline, nextSLAType := getNextSLADeadline(state)
		var slaTimer workflow.Future
		if !nextDeadline.IsZero() {
			duration := nextDeadline.Sub(workflow.Now(ctx))
			if duration > 0 {
				slaTimerCtx, _ := workflow.WithCancel(ctx)
				slaTimer = workflow.NewTimer(slaTimerCtx, duration)
			}
		}

		// Wait for event or SLA timeout
		selector := workflow.NewSelector(ctx)

		// Handle incoming events
		selector.AddReceive(eventCh, func(ch workflow.ReceiveChannel, more bool) {
			var event OrderEvent
			ch.Receive(ctx, &event)

			// Deduplication
			if state.ProcessedEvents[event.EventID] {
				logger.Info("Duplicate event ignored", "event_id", event.EventID)
				return
			}

			// Check if event is out of order
			if isOutOfOrder(state, event) {
				logger.Info("Buffering out-of-order event",
					"event_type", event.EventType,
					"current_status", state.Status,
				)
				state.BufferedEvents = append(state.BufferedEvents, event)
				return
			}

			// Process the event
			oldStatus := state.Status
			processEvent(state, event, workflow.Now(ctx))
			eventsProcessed++

			// If status changed, notify customer and process buffered events
			if state.Status != oldStatus {
				_ = workflow.UpsertSearchAttributes(ctx, map[string]interface{}{
					"Status": string(state.Status),
				})

				// Fan-out notifications
				_ = workflow.ExecuteActivity(notifyCtx, SendOrderNotification, NotificationRequest{
					OrderID:    state.OrderID,
					CustomerID: state.CustomerID,
					Type:       "status_update",
					Channel:    "all",
					Payload: map[string]any{
						"old_status": string(oldStatus),
						"new_status": string(state.Status),
					},
				}).Get(ctx, nil)

				// Try to process buffered events
				processBufferedEvents(state, workflow.Now(ctx))
			}
		})

		// Handle SLA timeout
		if slaTimer != nil {
			selector.AddFuture(slaTimer, func(f workflow.Future) {
				if err := f.Get(ctx, nil); err != nil {
					return // Timer was cancelled
				}
				logger.Warn("SLA breach detected",
					"order_id", state.OrderID,
					"sla_type", nextSLAType,
					"status", state.Status,
				)

				// Escalation notification
				_ = workflow.ExecuteActivity(notifyCtx, SendSLABreachAlert, state.OrderID, nextSLAType, state.Status).Get(ctx, nil)
			})
		}

		selector.Select(ctx)

		// Check if order is in terminal state
		if isTerminalState(state.Status) {
			logger.Info("Order reached terminal state",
				"order_id", state.OrderID,
				"status", state.Status,
				"events_processed", eventsProcessed,
			)
			// Keep workflow alive for a grace period (for late events)
			_ = workflow.Sleep(ctx, 24*time.Hour)
			return nil
		}

		// Continue-as-new to bound history
		if eventsProcessed >= maxEventsBeforeContinueAsNew {
			logger.Info("Continue-as-new for history management",
				"events_processed", eventsProcessed,
			)
			return workflow.NewContinueAsNewError(ctx, OrderEventProcessorResumed, state)
		}
	}
}

// OrderEventProcessorResumed continues processing after continue-as-new
func OrderEventProcessorResumed(ctx workflow.Context, state *OrderState) error {
	logger := workflow.GetLogger(ctx)
	logger.Info("Resumed order workflow", "order_id", state.OrderID, "status", state.Status)

	// Re-register handlers
	registerQueryHandlers(ctx, state)
	registerUpdateHandlers(ctx, state)

	// Continue the same event loop (extract to shared function in production)
	notifyCtx := workflow.WithActivityOptions(ctx, workflow.ActivityOptions{
		StartToCloseTimeout: 10 * time.Second,
		RetryPolicy:         &temporal.RetryPolicy{MaximumAttempts: 3},
	})

	eventCh := workflow.GetSignalChannel(ctx, "order_event")
	eventsProcessed := 0

	for {
		selector := workflow.NewSelector(ctx)
		selector.AddReceive(eventCh, func(ch workflow.ReceiveChannel, more bool) {
			var event OrderEvent
			ch.Receive(ctx, &event)

			if state.ProcessedEvents[event.EventID] {
				return
			}

			oldStatus := state.Status
			processEvent(state, event, workflow.Now(ctx))
			eventsProcessed++

			if state.Status != oldStatus {
				_ = workflow.UpsertSearchAttributes(ctx, map[string]interface{}{
					"Status": string(state.Status),
				})
				_ = workflow.ExecuteActivity(notifyCtx, SendOrderNotification, NotificationRequest{
					OrderID:    state.OrderID,
					CustomerID: state.CustomerID,
					Type:       "status_update",
					Channel:    "all",
					Payload: map[string]any{
						"new_status": string(state.Status),
					},
				}).Get(ctx, nil)

				processBufferedEvents(state, workflow.Now(ctx))
			}
		})

		selector.Select(ctx)

		if isTerminalState(state.Status) {
			_ = workflow.Sleep(ctx, 24*time.Hour)
			return nil
		}

		if eventsProcessed >= 500 {
			return workflow.NewContinueAsNewError(ctx, OrderEventProcessorResumed, state)
		}
	}
}

// ─────────────────────────────────────────────────────────────────────────────
// Query Handlers
// ─────────────────────────────────────────────────────────────────────────────

func registerQueryHandlers(ctx workflow.Context, state *OrderState) {
	// Full state query (for customer support)
	_ = workflow.SetQueryHandler(ctx, "get_state", func() (*OrderState, error) {
		return state, nil
	})

	// Lightweight status query
	_ = workflow.SetQueryHandler(ctx, "get_status", func() (OrderStatus, error) {
		return state.Status, nil
	})

	// Event history query
	_ = workflow.SetQueryHandler(ctx, "get_event_history", func() ([]OrderEvent, error) {
		return state.EventHistory, nil
	})

	// Estimated delivery query
	_ = workflow.SetQueryHandler(ctx, "get_estimated_delivery", func() (*time.Time, error) {
		if state.ShipmentInfo != nil && !state.ShipmentInfo.EstimatedDelivery.IsZero() {
			return &state.ShipmentInfo.EstimatedDelivery, nil
		}
		return nil, nil
	})

	// SLA status query
	_ = workflow.SetQueryHandler(ctx, "get_sla_status", func() (map[string]time.Time, error) {
		return state.SLADeadlines, nil
	})
}

// ─────────────────────────────────────────────────────────────────────────────
// Update Handlers (validated mutations)
// ─────────────────────────────────────────────────────────────────────────────

type CancelOrderRequest struct {
	Reason    string `json:"reason"`
	RequestedBy string `json:"requested_by"`
}

type ModifyOrderRequest struct {
	AddItems    []OrderItem `json:"add_items"`
	RemoveItems []string    `json:"remove_items"` // SKUs to remove
}

func registerUpdateHandlers(ctx workflow.Context, state *OrderState) {
	// Cancel order (with validation)
	_ = workflow.SetUpdateHandlerWithOptions(ctx, "cancel_order",
		func(ctx workflow.Context, req CancelOrderRequest) (string, error) {
			// Validation: can only cancel if not yet shipped
			if state.Status == StatusShipped || state.Status == StatusDelivered {
				return "", fmt.Errorf("cannot cancel order in status: %s", state.Status)
			}

			state.Status = StatusCancelled
			state.UpdatedAt = workflow.Now(ctx)
			state.Metadata["cancel_reason"] = req.Reason
			state.Metadata["cancelled_by"] = req.RequestedBy

			return "order_cancelled", nil
		},
		workflow.UpdateHandlerOptions{
			Validator: func(ctx workflow.Context, req CancelOrderRequest) error {
				if req.Reason == "" {
					return fmt.Errorf("cancellation reason is required")
				}
				if state.Status == StatusShipped || state.Status == StatusDelivered {
					return fmt.Errorf("cannot cancel: order already %s", state.Status)
				}
				return nil
			},
		},
	)

	// Modify order (with validation)
	_ = workflow.SetUpdateHandlerWithOptions(ctx, "modify_order",
		func(ctx workflow.Context, req ModifyOrderRequest) (string, error) {
			if state.Status != StatusPlaced && state.Status != StatusPaid {
				return "", fmt.Errorf("cannot modify order in status: %s", state.Status)
			}

			// Apply modifications
			for _, item := range req.AddItems {
				state.Items = append(state.Items, item)
				state.TotalAmount += item.Price * float64(item.Quantity)
			}

			state.UpdatedAt = workflow.Now(ctx)
			return "order_modified", nil
		},
		workflow.UpdateHandlerOptions{
			Validator: func(ctx workflow.Context, req ModifyOrderRequest) error {
				if state.Status != StatusPlaced && state.Status != StatusPaid {
					return fmt.Errorf("cannot modify: order in status %s", state.Status)
				}
				return nil
			},
		},
	)
}

// ─────────────────────────────────────────────────────────────────────────────
// Event Processing Logic
// ─────────────────────────────────────────────────────────────────────────────

func processEvent(state *OrderState, event OrderEvent, now time.Time) {
	// Mark as processed (deduplication)
	state.ProcessedEvents[event.EventID] = true
	state.EventHistory = append(state.EventHistory, event)
	state.UpdatedAt = now

	switch event.EventType {
	case EventPaymentReceived:
		state.Status = StatusPaid
		state.PaymentInfo = &PaymentInfo{
			TransactionID: getStr(event.Data, "transaction_id"),
			Method:        getStr(event.Data, "method"),
			Amount:        getFloat(event.Data, "amount"),
			Status:        "completed",
			PaidAt:        event.Timestamp,
		}
		// Update SLA: shipment must happen within 48h of payment
		state.SLADeadlines["shipment"] = now.Add(48 * time.Hour)
		delete(state.SLADeadlines, "payment") // Payment SLA met

	case EventPaymentFailed:
		state.Status = StatusCancelled
		state.Metadata["cancel_reason"] = "payment_failed"

	case EventInventoryReserved:
		if state.Status == StatusPaid {
			state.Status = StatusPicking
		}

	case EventInventoryFailed:
		// Inventory not available - need to cancel or backorder
		state.Metadata["inventory_issue"] = getStr(event.Data, "reason")

	case EventShipmentCreated:
		state.Status = StatusShipped
		state.ShipmentInfo = &ShipmentInfo{
			TrackingNumber:    getStr(event.Data, "tracking_number"),
			Carrier:           getStr(event.Data, "carrier"),
			ShippedAt:         event.Timestamp,
			EstimatedDelivery: parseTime(getStr(event.Data, "estimated_delivery")),
		}
		delete(state.SLADeadlines, "shipment") // Shipment SLA met
		state.SLADeadlines["delivery"] = state.ShipmentInfo.EstimatedDelivery.Add(24 * time.Hour) // 1 day buffer

	case EventDeliveryConfirmed:
		state.Status = StatusDelivered
		state.DeliveryInfo = &DeliveryInfo{
			DeliveredAt: event.Timestamp,
			ReceivedBy:  getStr(event.Data, "received_by"),
		}
		delete(state.SLADeadlines, "delivery")

	case EventDeliveryFailed:
		state.Status = StatusDeliveryFailed
		if state.DeliveryInfo == nil {
			state.DeliveryInfo = &DeliveryInfo{}
		}
		state.DeliveryInfo.Attempts++
		state.DeliveryInfo.LastAttemptAt = event.Timestamp

	case EventReturnInitiated:
		state.Status = StatusReturned
		state.Metadata["return_reason"] = getStr(event.Data, "reason")

	case EventRefundInitiated:
		state.Status = StatusRefunding
	}
}

func isOutOfOrder(state *OrderState, event OrderEvent) bool {
	// Define valid transitions
	validPreconditions := map[EventType][]OrderStatus{
		EventPaymentReceived:   {StatusPlaced},
		EventInventoryReserved: {StatusPaid},
		EventShipmentCreated:   {StatusPicking, StatusPacked, StatusPaid},
		EventDeliveryConfirmed: {StatusShipped},
		EventDeliveryFailed:    {StatusShipped},
		EventReturnInitiated:   {StatusDelivered},
	}

	validStatuses, exists := validPreconditions[event.EventType]
	if !exists {
		return false // Unknown event types are always processed
	}

	for _, s := range validStatuses {
		if state.Status == s {
			return false
		}
	}

	return true
}

func processBufferedEvents(state *OrderState, now time.Time) {
	// Sort buffered events by timestamp
	sort.Slice(state.BufferedEvents, func(i, j int) bool {
		return state.BufferedEvents[i].Timestamp.Before(state.BufferedEvents[j].Timestamp)
	})

	// Try to process each buffered event
	remaining := make([]OrderEvent, 0)
	for _, event := range state.BufferedEvents {
		if !isOutOfOrder(state, event) {
			processEvent(state, event, now)
		} else {
			remaining = append(remaining, event)
		}
	}
	state.BufferedEvents = remaining
}

func isTerminalState(status OrderStatus) bool {
	switch status {
	case StatusDelivered, StatusCancelled, StatusReturned:
		return true
	}
	return false
}

func getNextSLADeadline(state *OrderState) (time.Time, string) {
	var earliest time.Time
	var slaType string
	for t, deadline := range state.SLADeadlines {
		if earliest.IsZero() || deadline.Before(earliest) {
			earliest = deadline
			slaType = t
		}
	}
	return earliest, slaType
}

// ─────────────────────────────────────────────────────────────────────────────
// Kafka Consumer → Temporal Signal Router
// ─────────────────────────────────────────────────────────────────────────────

type EventRouter struct {
	temporalClient client.Client
	namespace      string
	taskQueue      string
}

func NewEventRouter(c client.Client) *EventRouter {
	return &EventRouter{
		temporalClient: c,
		namespace:      "orders",
		taskQueue:      "order-processing-tq",
	}
}

// RouteEvent routes a Kafka event to the appropriate Temporal workflow
func (r *EventRouter) RouteEvent(ctx context.Context, event OrderEvent) error {
	workflowID := fmt.Sprintf("order-%s", event.OrderID)

	// Use SignalWithStartWorkflow: if workflow exists, signal it.
	// If it doesn't exist, start it and deliver the signal.
	_, err := r.temporalClient.SignalWithStartWorkflow(
		ctx,
		workflowID,
		"order_event", // signal name
		event,         // signal payload
		client.StartWorkflowOptions{
			ID:        workflowID,
			TaskQueue: r.taskQueue,
			SearchAttributes: map[string]interface{}{
				"OrderID":    event.OrderID,
				"CustomerID": getStr(event.Data, "customer_id"),
				"Status":     "placed",
			},
			// Idempotent: if workflow already running, just signal
			WorkflowIDReusePolicy: temporal.WorkflowIDReusePolicyAllowDuplicate,
		},
		OrderEventProcessorWorkflow,
		event, // workflow input (initial event)
	)

	return err
}

// BatchRouteEvents processes a batch of Kafka messages efficiently
func (r *EventRouter) BatchRouteEvents(ctx context.Context, events []OrderEvent) error {
	// Group events by order ID for batch signaling
	byOrder := make(map[string][]OrderEvent)
	for _, e := range events {
		byOrder[e.OrderID] = append(byOrder[e.OrderID], e)
	}

	for orderID, orderEvents := range byOrder {
		for _, event := range orderEvents {
			if err := r.RouteEvent(ctx, event); err != nil {
				return fmt.Errorf("failed to route event for order %s: %w", orderID, err)
			}
		}
	}

	return nil
}

// ─────────────────────────────────────────────────────────────────────────────
// Activities
// ─────────────────────────────────────────────────────────────────────────────

type OrderActivities struct {
	NotificationService NotificationService
	AnalyticsService    AnalyticsService
}

type NotificationService interface {
	SendPush(ctx context.Context, customerID string, message map[string]any) error
	SendEmail(ctx context.Context, customerID string, template string, data map[string]any) error
	SendSMS(ctx context.Context, customerID string, message string) error
	PublishWebSocket(ctx context.Context, customerID string, event map[string]any) error
}

type AnalyticsService interface {
	TrackEvent(ctx context.Context, event string, properties map[string]any) error
}

func (a *OrderActivities) SendOrderNotification(ctx context.Context, req NotificationRequest) error {
	activity.RecordHeartbeat(ctx, fmt.Sprintf("notifying %s", req.CustomerID))

	// Fan out to all channels
	if req.Channel == "all" || req.Channel == "websocket" {
		_ = a.NotificationService.PublishWebSocket(ctx, req.CustomerID, req.Payload)
	}
	if req.Channel == "all" || req.Channel == "push" {
		_ = a.NotificationService.SendPush(ctx, req.CustomerID, req.Payload)
	}
	if req.Channel == "all" || req.Channel == "email" {
		_ = a.NotificationService.SendEmail(ctx, req.CustomerID, "order_update", req.Payload)
	}

	return nil
}

func (a *OrderActivities) SendSLABreachAlert(ctx context.Context, orderID, slaType string, status OrderStatus) error {
	activity.GetLogger(ctx).Warn("SLA breach",
		"order_id", orderID,
		"sla_type", slaType,
		"current_status", status,
	)
	// Page on-call, create incident ticket, etc.
	return nil
}

// ─────────────────────────────────────────────────────────────────────────────
// High-Throughput Signal Batching Pattern
// ─────────────────────────────────────────────────────────────────────────────

// For very high event rates (>10K events/second per order), batch signals
// to reduce workflow task frequency.

type BatchedSignalRouter struct {
	temporalClient client.Client
	buffer         map[string][]OrderEvent // orderID -> buffered events
	flushInterval  time.Duration
	maxBatchSize   int
}

func (r *BatchedSignalRouter) Start(ctx context.Context) {
	ticker := time.NewTicker(r.flushInterval)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			r.flush(ctx) // Flush remaining
			return
		case <-ticker.C:
			r.flush(ctx)
		}
	}
}

func (r *BatchedSignalRouter) flush(ctx context.Context) {
	for orderID, events := range r.buffer {
		if len(events) == 0 {
			continue
		}

		workflowID := fmt.Sprintf("order-%s", orderID)
		// Send all events as a single batch signal
		_ = r.temporalClient.SignalWorkflow(ctx, workflowID, "", "order_event_batch", events)
		delete(r.buffer, orderID)
	}
}

// ─────────────────────────────────────────────────────────────────────────────
// Customer Support Query API
// ─────────────────────────────────────────────────────────────────────────────

type OrderQueryService struct {
	temporalClient client.Client
}

func (s *OrderQueryService) GetOrderState(ctx context.Context, orderID string) (*OrderState, error) {
	workflowID := fmt.Sprintf("order-%s", orderID)

	resp, err := s.temporalClient.QueryWorkflow(ctx, workflowID, "", "get_state")
	if err != nil {
		return nil, fmt.Errorf("failed to query order %s: %w", orderID, err)
	}

	var state OrderState
	if err := resp.Get(&state); err != nil {
		return nil, fmt.Errorf("failed to decode order state: %w", err)
	}

	return &state, nil
}

func (s *OrderQueryService) GetEstimatedDelivery(ctx context.Context, orderID string) (*time.Time, error) {
	workflowID := fmt.Sprintf("order-%s", orderID)

	resp, err := s.temporalClient.QueryWorkflow(ctx, workflowID, "", "get_estimated_delivery")
	if err != nil {
		return nil, err
	}

	var eta *time.Time
	if err := resp.Get(&eta); err != nil {
		return nil, err
	}

	return eta, nil
}

func (s *OrderQueryService) CancelOrder(ctx context.Context, orderID string, reason, requestedBy string) error {
	workflowID := fmt.Sprintf("order-%s", orderID)

	handle, err := s.temporalClient.UpdateWorkflow(ctx, client.UpdateWorkflowOptions{
		WorkflowID: workflowID,
		UpdateName: "cancel_order",
		Args:       []interface{}{CancelOrderRequest{Reason: reason, RequestedBy: requestedBy}},
	})
	if err != nil {
		return err
	}

	var result string
	return handle.Get(ctx, &result)
}

// ─────────────────────────────────────────────────────────────────────────────
// Helper Functions
// ─────────────────────────────────────────────────────────────────────────────

func getStr(data map[string]any, key string) string {
	if v, ok := data[key].(string); ok {
		return v
	}
	return ""
}

func getFloat(data map[string]any, key string) float64 {
	if v, ok := data[key].(float64); ok {
		return v
	}
	return 0
}

func parseTime(s string) time.Time {
	t, _ := time.Parse(time.RFC3339, s)
	return t
}

func eventFingerprint(event OrderEvent) string {
	hash := sha256.Sum256([]byte(fmt.Sprintf("%s:%s:%s", event.OrderID, event.EventType, event.Timestamp)))
	return hex.EncodeToString(hash[:8])
}
```

## Worker Setup

```go
package main

import (
	"log"
	"time"

	"go.temporal.io/sdk/client"
	"go.temporal.io/sdk/worker"

	orders "mycompany/order-processing"
)

func main() {
	c, err := client.Dial(client.Options{
		HostPort:  "temporal.internal:7233",
		Namespace: "orders",
	})
	if err != nil {
		log.Fatalf("Unable to create client: %v", err)
	}
	defer c.Close()

	w := worker.New(c, "order-processing-tq", worker.Options{
		// High workflow concurrency (signal-driven, lightweight)
		MaxConcurrentWorkflowTaskExecutionSize: 1000,
		// Low activity concurrency (notifications are I/O bound)
		MaxConcurrentActivityExecutionSize: 50,
		// Sticky cache for millions of workflows
		StickyScheduleToStartTimeout: 5 * time.Second,
	})

	w.RegisterWorkflow(orders.OrderEventProcessorWorkflow)
	w.RegisterWorkflow(orders.OrderEventProcessorResumed)

	activities := &orders.OrderActivities{
		// Initialize notification and analytics services
	}
	w.RegisterActivity(activities)

	if err := w.Run(worker.InterruptCh()); err != nil {
		log.Fatalf("Worker failed: %v", err)
	}
}
```

## Failure Scenarios & Handling

### 1. Kafka Consumer Lag (10K Events Behind)

```
Scenario: Consumer falls behind due to slow signal delivery or Temporal congestion
Detection: Consumer group lag metric > threshold
Handling:
  1. Batch signal optimization: group events by order, send batch signals
  2. Scale consumer instances (more partitions = more parallelism)
  3. Use SignalWithStart to avoid "workflow not found" errors
  4. Temporal can handle burst of signals (they queue on workflow task queue)
  5. Monitor: temporal_workflow_task_schedule_to_start_latency

Prevention:
  - Size Kafka partitions = order ID hash distribution
  - Consumer auto-scaling based on lag metric
  - Separate consumer groups for different event priorities
```

### 2. Duplicate Events from At-Least-Once Delivery

```
Scenario: Kafka rebalance causes messages to be redelivered
Detection: event.EventID already in state.ProcessedEvents
Handling:
  1. Every event has a unique EventID (set by producer)
  2. Workflow maintains ProcessedEvents map
  3. Duplicate events are silently dropped (idempotent)
  4. Map is preserved across continue-as-new
  5. After terminal state + grace period, old event IDs are irrelevant

Note: The ProcessedEvents map can grow large for long-lived orders.
Mitigation: Only keep last 1000 event IDs + prune on continue-as-new.
```

### 3. Event Schema Evolution (v1 vs v2 Events)

```
Scenario: Payment service deploys new event schema (adds field, removes field)
Detection: Version field in OrderEvent
Handling:
  1. Event router normalizes events before signaling workflow
  2. processEvent handles multiple versions:
     - v1: payment.received has "amount" as int (cents)
     - v2: payment.received has "amount" as float (dollars)
  3. Default values for missing fields
  4. Strict mode: reject events with unknown required fields
  5. Schema registry (Confluent) validates at Kafka level

Code:
  switch event.Version {
  case 1:
      amount = float64(getInt(event.Data, "amount")) / 100.0
  case 2:
      amount = getFloat(event.Data, "amount")
  }
```

### 4. Workflow History Growing Too Large

```
Scenario: Order with 1000+ events approaches 50K event limit
Detection: eventsProcessed counter in workflow
Handling:
  1. Continue-as-new after 500 events
  2. Full state serialized and passed to new execution
  3. ProcessedEvents map pruned to last 200 entries
  4. EventHistory trimmed (keep last 100 events in memory)
  5. Full history available via Temporal visibility API

Sizing:
  - Average order: 10-20 events (no continue-as-new needed)
  - Complex order with issues: 50-100 events (rare continue-as-new)
  - Threshold of 500 provides large safety margin
```

### 5. Signal Ordering Guarantees

```
Scenario: Two signals arrive at workflow in different order than produced
Reality: Temporal signals are ordered per-workflow (FIFO delivery)
BUT: Events from different Kafka topics may arrive in any order

Handling:
  1. isOutOfOrder() checks if current state can accept the event
  2. Out-of-order events are buffered in state.BufferedEvents
  3. After each state change, buffered events are re-evaluated
  4. Buffered events sorted by timestamp before processing
  5. Events that remain buffered for >1 hour trigger alert
```

## Production Configuration

```yaml
# Search attributes for customer support queries
search_attributes:
  OrderID: Keyword
  CustomerID: Keyword
  Status: Keyword
  CreatedAt: Datetime

# Workflow execution
workflow:
  execution_timeout: 720h  # 30 days max order lifecycle
  run_timeout: 720h
  task_timeout: 10s

# Visibility queries (customer support)
# Find all orders for a customer:
#   OrderID = "order-123" OR CustomerID = "cust-456"
# Find stuck orders:
#   Status = "shipped" AND CloseTime IS NULL AND StartTime < "2024-01-01"

# Worker scaling
worker:
  replicas: 20  # Handle millions of concurrent workflows
  workflow_cache_size: 10000  # Sticky cache
  max_concurrent_workflow_tasks: 1000
  max_concurrent_activities: 50
```

## Metrics & Observability

| Metric | Description | Alert |
|--------|-------------|-------|
| `orders_active_count` | Concurrent running workflows | > 5M |
| `orders_events_per_second` | Signal throughput | < 1000 |
| `orders_sla_breaches` | SLA violations | > 0 |
| `orders_duplicate_events` | Deduplicated events | > 10% of total |
| `orders_buffered_events` | Out-of-order events buffered | > 100 per order |
| `orders_continue_as_new` | History overflow events | Informational |
| `kafka_consumer_lag` | Messages behind | > 10000 |
| `temporal_signal_latency_p99` | Time from Kafka consume to workflow signal | > 1s |

## CQRS Pattern with Temporal

```
Commands (Mutations):
  - Signals: order_event (from Kafka)
  - Updates: cancel_order, modify_order (from API with validation)

Queries (Read-only):
  - get_state: Full order state for customer support
  - get_status: Lightweight status check
  - get_estimated_delivery: ETA for customer-facing UI
  - get_event_history: Audit trail

Projections:
  - Temporal workflow IS the projection (materializes state from events)
  - No separate read model needed for real-time queries
  - For analytics: events also flow to data warehouse (parallel consumer)
```
