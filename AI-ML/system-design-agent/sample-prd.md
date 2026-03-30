# PRD: Real-Time Order Tracking System

## Overview
Build a real-time order tracking system that allows customers to track their food delivery orders from placement to delivery. The system should provide live location updates of delivery partners and estimated time of arrival (ETA).

## Background
Currently, customers have no visibility into their order status after placement. This leads to high support call volumes and poor customer satisfaction. We need a system that provides real-time tracking with sub-second location updates.

## Goals
1. Provide real-time order status tracking for customers
2. Show live delivery partner location on a map
3. Calculate and display dynamic ETA based on real-time traffic
4. Send push notifications at key order milestones
5. Reduce support calls related to "Where is my order?" by 60%

## Non-Goals
- Route optimization for delivery partners (handled by existing routing service)
- Payment processing
- Order placement flow

## Functional Requirements

### FR-1: Order Status Tracking (P0)
- Customers can view current order status: PLACED → CONFIRMED → PREPARING → PICKED_UP → IN_TRANSIT → DELIVERED
- Status transitions are triggered by delivery partner app and restaurant POS
- Each status change is timestamped and stored

### FR-2: Live Location Tracking (P0)
- Delivery partner's location is captured every 3 seconds via mobile app
- Customer sees delivery partner location on an embedded map
- Location updates are pushed to customer app in real-time via WebSocket

### FR-3: Dynamic ETA Calculation (P1)
- ETA is recalculated every 30 seconds based on current location and traffic
- ETA considers: distance, current speed, traffic conditions, restaurant prep time
- ETA accuracy target: within 3 minutes of actual delivery 80% of the time

### FR-4: Push Notifications (P1)
- Send push notification on each status change
- Send notification when ETA changes by more than 5 minutes
- Send notification when delivery partner is 2 minutes away
- Users can configure notification preferences

### FR-5: Order History (P2)
- Customers can view past 90 days of order tracking history
- Each historical order shows: timeline of status changes, delivery route taken

## Non-Functional Requirements

### Scale
- **Active orders at peak**: 500,000 concurrent orders
- **Location updates**: 170,000 updates/second (500K orders × 1 update/3 sec)
- **Customer app polling**: Handled via WebSocket (no polling)
- **Read QPS**: 50,000 (order status checks)
- **Write QPS**: 170,000 (location updates) + 5,000 (status changes)

### Latency
- Location update ingestion: < 100ms (p99)
- Location push to customer: < 500ms end-to-end (p95)
- ETA calculation: < 200ms (p95)
- Order status query: < 50ms (p95)

### Availability
- **Target**: 99.95% uptime
- Location tracking is critical — must gracefully degrade (show last known location)
- Order status must be eventually consistent within 2 seconds

### Data
- Location data retention: 7 days (hot), 90 days (warm/archive)
- Order status data retention: 2 years
- Estimated storage: ~500GB/day for location data

## Data Entities

### Order
- order_id (UUID)
- customer_id (UUID)
- restaurant_id (UUID)
- delivery_partner_id (UUID, nullable)
- status (enum)
- placed_at (timestamp)
- estimated_delivery_at (timestamp)
- actual_delivered_at (timestamp, nullable)
- delivery_address (JSON)

### OrderStatusEvent
- event_id (UUID)
- order_id (UUID)
- status (enum)
- timestamp (timestamp)
- actor (delivery_partner | restaurant | system)
- metadata (JSON)

### DeliveryLocation
- order_id (UUID)
- delivery_partner_id (UUID)
- latitude (decimal)
- longitude (decimal)
- speed_kmh (float)
- heading (float)
- accuracy_meters (float)
- captured_at (timestamp)

### NotificationPreference
- customer_id (UUID)
- notification_type (enum)
- channel (push | sms | email)
- enabled (boolean)

## Integrations
- **Delivery Partner App**: Sends location updates via gRPC
- **Restaurant POS**: Sends order status via REST webhook
- **Google Maps API**: For ETA calculation and map rendering
- **Firebase Cloud Messaging**: For push notifications
- **Existing Order Service**: REST API to get order details
- **Kafka**: For async event streaming between services

## Success Metrics
- Reduce "Where is my order?" support calls by 60%
- Location update delivery latency p95 < 500ms
- ETA accuracy within 3 minutes for 80% of deliveries
- Customer satisfaction score improvement by 15%

## Constraints
- Must use existing Kubernetes infrastructure
- Must integrate with existing authentication service (OAuth 2.0)
- Budget: $15,000/month for infrastructure
- Timeline: MVP in 8 weeks
