# DoorDash Food Delivery Platform - System Design

## 1. Functional Requirements

### Core Features
- **Restaurant Catalog/Menus**: Browse restaurants, view menus, item customization
- **Order Placement**: Add items to cart, checkout with delivery address
- **Real-Time Delivery Tracking**: Live map showing Dasher position
- **Dasher (Driver) Assignment**: Match orders to optimal delivery drivers
- **Delivery Time Estimation**: Predict total time (prep + pickup + transit)
- **Batched Orders**: Assign multiple orders to one Dasher on same route
- **Restaurant Prep Time Learning**: ML-based prep time that improves per restaurant
- **Multi-Order (DashPass)**: Subscription for free delivery, priority matching
- **Tipping**: Pre-tip at order, post-delivery tip adjustment

### Order Lifecycle
```
Order Placed → Restaurant Confirms → Preparing → Ready for Pickup → 
Dasher Assigned → Dasher En Route to Restaurant → Dasher Arrived → 
Picked Up → Dasher En Route to Customer → Delivered
```

## 2. Non-Functional Requirements

| Requirement | Target |
|---|---|
| Order Placement Latency (P99) | < 1s |
| Delivery Time Estimate Accuracy | ± 5 minutes |
| Dasher Assignment Latency | < 30s |
| Location Update Frequency | Every 5 seconds |
| Concurrent Active Orders | 500K |
| Active Dashers | 1M |
| Restaurant Count | 500K |
| Order QPS (Peak, meal times) | 5K |
| Availability | 99.99% |
| Tracking Update Latency | < 3s |

## 3. Capacity Estimation

### Storage
- **Restaurants + Menus**: 500K restaurants × 200KB (menu + photos) = 100 GB
- **Orders**: 10M orders/day × 3KB = 30 GB/day = 11 TB/year
- **Dasher Locations**: 1M dashers × 17,280 pings/day × 50B = 864 GB/day (30-day retention)
- **User Profiles**: 50M users × 2KB = 100 GB
- **Dasher Profiles**: 2M dashers × 5KB = 10 GB

### Compute
- **Order Service**: 5K orders/sec / 2K per instance = 3 instances (with headroom: 10)
- **Tracking Service**: 200K updates/sec (1M dashers / 5s) → 10 instances
- **Assignment Service**: 5K assignments/sec → 5 instances (CPU-intensive matching)
- **Delivery Time ML**: 5K predictions/sec → 3 instances (GPU-backed)

### Bandwidth
- **Location Inbound**: 200K × 200B = 40 MB/s
- **Menu/Images**: Mostly CDN, origin: 1 GB/s
- **WebSocket (tracking)**: 500K active connections × 200B × 0.2/sec = 20 MB/s

## 4. Data Modeling

### Restaurant Schema
```sql
CREATE TABLE restaurants (
    restaurant_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Basic info
    name                VARCHAR(200) NOT NULL,
    description         TEXT,
    cuisine_types       VARCHAR(50)[] NOT NULL,
    
    -- Location
    address             JSONB NOT NULL,
    location            GEOGRAPHY(POINT, 4326) NOT NULL,
    delivery_radius_km  DECIMAL(5,2) DEFAULT 8.0,
    
    -- Operations
    status              VARCHAR(20) DEFAULT 'ACTIVE', -- ACTIVE, PAUSED, CLOSED, ONBOARDING
    is_open             BOOLEAN DEFAULT FALSE,
    operating_hours     JSONB NOT NULL, -- {"monday": {"open": "09:00", "close": "22:00"}, ...}
    
    -- Performance metrics
    avg_prep_time_min   DECIMAL(5,1) DEFAULT 20.0,
    avg_rating          DECIMAL(3,2) DEFAULT 0,
    total_ratings       INTEGER DEFAULT 0,
    order_accuracy_rate DECIMAL(4,3) DEFAULT 1.0,
    
    -- Prep time model
    prep_time_model_version VARCHAR(20),
    prep_time_features  JSONB, -- {"base_time": 15, "per_item_time": 3, "rush_multiplier": 1.5}
    
    -- Business
    commission_rate     DECIMAL(4,3) DEFAULT 0.20,
    dashpass_partner    BOOLEAN DEFAULT FALSE,
    
    -- Media
    logo_url            TEXT,
    header_image_url    TEXT,
    
    created_at          TIMESTAMP DEFAULT NOW(),
    updated_at          TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_restaurants_location ON restaurants USING GIST(location);
CREATE INDEX idx_restaurants_cuisine ON restaurants USING GIN(cuisine_types);
CREATE INDEX idx_restaurants_status ON restaurants(status, is_open);
CREATE INDEX idx_restaurants_rating ON restaurants(avg_rating DESC) WHERE status = 'ACTIVE';
```

### Menu Schema
```sql
CREATE TABLE menu_categories (
    category_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    restaurant_id       UUID NOT NULL REFERENCES restaurants(restaurant_id),
    name                VARCHAR(100) NOT NULL,
    description         TEXT,
    sort_order          INTEGER DEFAULT 0,
    available_hours     JSONB, -- null = always available
    status              VARCHAR(20) DEFAULT 'ACTIVE'
);

CREATE INDEX idx_menu_cat_restaurant ON menu_categories(restaurant_id, sort_order);

CREATE TABLE menu_items (
    item_id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    restaurant_id       UUID NOT NULL REFERENCES restaurants(restaurant_id),
    category_id         UUID NOT NULL REFERENCES menu_categories(category_id),
    
    name                VARCHAR(200) NOT NULL,
    description         TEXT,
    image_url           TEXT,
    
    -- Pricing
    base_price          DECIMAL(8,2) NOT NULL,
    currency            VARCHAR(3) DEFAULT 'USD',
    
    -- Customization options
    customization_groups JSONB,
    -- [{"name": "Size", "required": true, "max_select": 1, 
    --   "options": [{"name": "Small", "price_delta": -2}, {"name": "Large", "price_delta": 3}]},
    --  {"name": "Toppings", "required": false, "max_select": 5, 
    --   "options": [{"name": "Extra Cheese", "price_delta": 1.5}]}]
    
    -- Availability
    is_available        BOOLEAN DEFAULT TRUE,
    available_hours     JSONB,
    max_daily_quantity  INTEGER, -- NULL = unlimited
    sold_today          INTEGER DEFAULT 0,
    
    -- Metadata
    calories            INTEGER,
    allergens           VARCHAR(50)[],
    dietary_tags        VARCHAR(50)[], -- VEGETARIAN, VEGAN, GLUTEN_FREE
    is_popular          BOOLEAN DEFAULT FALSE,
    
    -- Prep time impact
    prep_time_addition_min DECIMAL(4,1) DEFAULT 0, -- Extra prep for complex items
    
    sort_order          INTEGER DEFAULT 0,
    status              VARCHAR(20) DEFAULT 'ACTIVE',
    created_at          TIMESTAMP DEFAULT NOW(),
    updated_at          TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_menu_items_restaurant ON menu_items(restaurant_id, status);
CREATE INDEX idx_menu_items_category ON menu_items(category_id, sort_order);
CREATE INDEX idx_menu_items_popular ON menu_items(restaurant_id, is_popular) WHERE is_popular = TRUE;
```

### Order Schema
```sql
CREATE TABLE orders (
    order_id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_number        VARCHAR(20) UNIQUE NOT NULL,
    
    -- Participants
    customer_id         UUID NOT NULL,
    restaurant_id       UUID NOT NULL,
    dasher_id           UUID, -- NULL until assigned
    
    -- Status
    status              VARCHAR(30) NOT NULL DEFAULT 'PLACED',
    -- PLACED, RESTAURANT_CONFIRMED, PREPARING, READY_FOR_PICKUP,
    -- DASHER_ASSIGNED, DASHER_EN_ROUTE_PICKUP, DASHER_ARRIVED_RESTAURANT,
    -- PICKED_UP, DASHER_EN_ROUTE_DELIVERY, DELIVERED, CANCELLED
    
    -- Locations
    delivery_address    JSONB NOT NULL,
    delivery_location   GEOGRAPHY(POINT, 4326) NOT NULL,
    restaurant_location GEOGRAPHY(POINT, 4326) NOT NULL,
    
    -- Timing
    estimated_prep_time_min     DECIMAL(5,1),
    actual_prep_time_min        DECIMAL(5,1),
    estimated_delivery_time_min DECIMAL(5,1),
    actual_delivery_time_min    DECIMAL(5,1),
    estimated_delivery_at       TIMESTAMP,
    
    -- Pricing
    subtotal            DECIMAL(10,2) NOT NULL,
    delivery_fee        DECIMAL(8,2) DEFAULT 0,
    service_fee         DECIMAL(8,2) DEFAULT 0,
    tax                 DECIMAL(8,2) DEFAULT 0,
    tip_amount          DECIMAL(8,2) DEFAULT 0,
    promo_discount      DECIMAL(8,2) DEFAULT 0,
    total               DECIMAL(10,2) NOT NULL,
    currency            VARCHAR(3) DEFAULT 'USD',
    
    -- DashPass
    dashpass_applied    BOOLEAN DEFAULT FALSE,
    dashpass_savings    DECIMAL(8,2) DEFAULT 0,
    
    -- Payment
    payment_method_id   UUID NOT NULL,
    payment_status      VARCHAR(20) DEFAULT 'PENDING',
    
    -- Assignment
    assignment_batch_id UUID, -- If part of batched delivery
    batch_position      INTEGER, -- Order in batch (1 = picked up first)
    
    -- Special instructions
    delivery_instructions TEXT,
    contactless_delivery BOOLEAN DEFAULT TRUE,
    
    -- Timestamps
    placed_at           TIMESTAMP DEFAULT NOW(),
    confirmed_at        TIMESTAMP,
    ready_at            TIMESTAMP,
    picked_up_at        TIMESTAMP,
    delivered_at        TIMESTAMP,
    cancelled_at        TIMESTAMP,
    
    -- Ratings
    customer_rating     SMALLINT,
    customer_review     TEXT,
    dasher_rating_of_restaurant SMALLINT,
    
    created_at          TIMESTAMP DEFAULT NOW(),
    updated_at          TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_orders_customer ON orders(customer_id, created_at DESC);
CREATE INDEX idx_orders_restaurant ON orders(restaurant_id, status, created_at DESC);
CREATE INDEX idx_orders_dasher ON orders(dasher_id, status) WHERE dasher_id IS NOT NULL;
CREATE INDEX idx_orders_status ON orders(status, placed_at) WHERE status NOT IN ('DELIVERED', 'CANCELLED');
CREATE INDEX idx_orders_delivery_location ON orders USING GIST(delivery_location) WHERE status IN ('DASHER_ASSIGNED', 'DASHER_EN_ROUTE_PICKUP');
```

### Order Items Schema
```sql
CREATE TABLE order_items (
    order_item_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id            UUID NOT NULL REFERENCES orders(order_id),
    menu_item_id        UUID NOT NULL,
    
    -- Snapshot at order time
    item_name           VARCHAR(200) NOT NULL,
    quantity            INTEGER NOT NULL CHECK(quantity > 0),
    unit_price          DECIMAL(8,2) NOT NULL,
    
    -- Customizations selected
    customizations      JSONB,
    -- [{"group": "Size", "selected": "Large", "price_delta": 3.00},
    --  {"group": "Toppings", "selected": ["Extra Cheese", "Bacon"], "price_delta": 3.50}]
    
    special_instructions TEXT,
    line_total          DECIMAL(8,2) NOT NULL,
    
    created_at          TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_order_items_order ON order_items(order_id);
```

### Dasher Schema
```sql
CREATE TABLE dashers (
    dasher_id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL UNIQUE,
    
    -- Personal
    first_name          VARCHAR(100) NOT NULL,
    last_name           VARCHAR(100) NOT NULL,
    phone               VARCHAR(20) NOT NULL,
    profile_photo_url   TEXT,
    
    -- Vehicle
    vehicle_type        VARCHAR(20), -- CAR, BIKE, SCOOTER, WALK
    
    -- Status
    status              VARCHAR(20) DEFAULT 'ACTIVE', -- ACTIVE, SUSPENDED, DEACTIVATED
    online_status       VARCHAR(20) DEFAULT 'OFFLINE', -- ONLINE, OFFLINE
    current_orders      INTEGER DEFAULT 0, -- How many active orders
    max_concurrent      INTEGER DEFAULT 2, -- Max batched orders
    
    -- Performance
    rating              DECIMAL(3,2) DEFAULT 5.00,
    total_deliveries    INTEGER DEFAULT 0,
    acceptance_rate     DECIMAL(4,3) DEFAULT 1.000,
    completion_rate     DECIMAL(4,3) DEFAULT 1.000,
    on_time_rate        DECIMAL(4,3) DEFAULT 1.000,
    
    -- Metrics for assignment optimization
    avg_speed_mph       DECIMAL(5,1) DEFAULT 20.0,
    avg_pickup_time_sec INTEGER DEFAULT 120, -- Time spent at restaurant
    
    -- Location
    last_known_lat      DECIMAL(10,7),
    last_known_lng      DECIMAL(10,7),
    last_location_at    TIMESTAMP,
    current_h3_cell     VARCHAR(20),
    
    -- Market
    city_id             UUID NOT NULL,
    preferred_zones     UUID[],
    
    -- Schedule
    scheduled_shifts    JSONB,
    
    created_at          TIMESTAMP DEFAULT NOW(),
    updated_at          TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_dashers_location ON dashers(current_h3_cell, online_status) WHERE online_status = 'ONLINE';
CREATE INDEX idx_dashers_city ON dashers(city_id, online_status, rating DESC);
CREATE INDEX idx_dashers_available ON dashers(city_id, current_orders, max_concurrent) 
    WHERE online_status = 'ONLINE' AND status = 'ACTIVE';
```

## 5. High-Level Design (HLD)

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                              CLIENT LAYER                                                │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────┐  ┌──────────────────────┐    │
│  │ Customer App │  │  Dasher App  │  │ Restaurant App │  │  Merchant Portal     │    │
│  │ (iOS/And)    │  │  (iOS/And)   │  │  (Tablet)      │  │  (Web)               │    │
│  └──────┬───────┘  └──────┬───────┘  └───────┬────────┘  └──────────┬───────────┘    │
│         │  REST+WS        │  REST+WS          │  REST+WS             │  REST          │
└─────────┼──────────────────┼──────────────────┼──────────────────────┼────────────────┘
          │                  │                  │                      │
┌─────────▼──────────────────▼──────────────────▼──────────────────────▼────────────────┐
│                 API Gateway (Auth, Rate Limit, Routing)                                 │
│                 + WebSocket Gateway (Tracking Connections)                              │
└─────────────────────────────────┬─────────────────────────────────────────────────────┘
                                  │
┌─────────────────────────────────┼─────────────────────────────────────────────────────┐
│                                 ▼             SERVICE LAYER                             │
│                                                                                        │
│  ┌─────────────────────┐  ┌──────────────────────┐  ┌─────────────────────────────┐  │
│  │ Restaurant/Menu Svc │  │  Order Service       │  │  Delivery Time Prediction   │  │
│  │                     │  │                      │  │  (ML Service)               │  │
│  │ - Catalog CRUD      │  │  - Order lifecycle   │  │                             │  │
│  │ - Menu management   │  │  - Status machine    │  │  - Prep time model          │  │
│  │ - Availability      │  │  - Payment flow      │  │  - Transit time model       │  │
│  │ - Geofence search   │  │  - Cancellations     │  │  - Dynamic updates          │  │
│  └─────────────────────┘  └──────────┬───────────┘  └──────────────┬──────────────┘  │
│                                      │                              │                  │
│  ┌─────────────────────┐  ┌─────────▼────────────┐  ┌─────────────▼──────────────┐  │
│  │ Dasher Location Svc │  │  Assignment Service  │  │  Tracking Service          │  │
│  │                     │  │  (Dispatch Engine)   │  │                            │  │
│  │ - Ingest pings      │  │                      │  │  - Real-time position      │  │
│  │ - Geo-index         │  │  - Bipartite match   │  │  - ETA updates to customer │  │
│  │ - Supply tracking   │  │  - Batch optimization│  │  - Route tracking          │  │
│  └─────────────────────┘  │  - Acceptance flow   │  └────────────────────────────┘  │
│                            └──────────────────────┘                                    │
│                                                                                        │
│  ┌─────────────────────┐  ┌──────────────────────┐  ┌────────────────────────────┐  │
│  │ Payment Service     │  │  Notification Svc    │  │  Geofence Service          │  │
│  │ - Charge customer   │  │  - Push/SMS          │  │  - Delivery zone mgmt      │  │
│  │ - Pay dasher        │  │  - Order updates     │  │  - Restaurant availability │  │
│  │ - Tips              │  │  - Promo alerts      │  │  - Zone-based pricing      │  │
│  └─────────────────────┘  └──────────────────────┘  └────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────────────────────────┘
                                  │
┌─────────────────────────────────┼─────────────────────────────────────────────────────┐
│                                 ▼             DATA LAYER                                │
│                                                                                        │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐  ┌───────────────────────┐  │
│  │ PostgreSQL    │  │ Redis Cluster │  │ Apache Kafka  │  │ Apache Flink          │  │
│  │               │  │               │  │               │  │                       │  │
│  │ - Orders      │  │ - Dasher locs │  │ - Order events│  │ - Delivery time model │  │
│  │ - Restaurants │  │ - Geo index   │  │ - Location    │  │ - Prep time learning  │  │
│  │ - Menus       │  │ - Session     │  │   stream      │  │ - Supply/demand agg   │  │
│  │ - Dashers     │  │ - ETA cache   │  │ - Assignment  │  │                       │  │
│  └───────────────┘  └───────────────┘  └───────────────┘  └───────────────────────┘  │
│                                                                                        │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐                              │
│  │ Elasticsearch │  │ S3            │  │ ML Model Store│                              │
│  │ (Restaurant   │  │ (Images,      │  │ (SageMaker)   │                              │
│  │  search)      │  │  Locations)   │  │               │                              │
│  └───────────────┘  └───────────────┘  └───────────────┘                              │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

## 6. Low-Level Design (LLD) - APIs

### Place Order
```
POST /api/v1/orders
Request:
{
    "customer_id": "usr_001",
    "restaurant_id": "rest_001",
    "items": [
        {
            "menu_item_id": "item_001",
            "quantity": 2,
            "customizations": [
                {"group": "Size", "selected": ["Large"], "price_delta": 3.00},
                {"group": "Extras", "selected": ["Extra Sauce"], "price_delta": 0.50}
            ],
            "special_instructions": "No onions"
        },
        {
            "menu_item_id": "item_005",
            "quantity": 1,
            "customizations": [],
            "special_instructions": null
        }
    ],
    "delivery_address": {
        "lat": 37.7749,
        "lng": -122.4194,
        "formatted": "123 Main St, Apt 4B, San Francisco, CA 94102",
        "instructions": "Gate code: 1234. Leave at door."
    },
    "payment_method_id": "pm_001",
    "tip_amount": 5.00,
    "promo_code": "SAVE5",
    "contactless_delivery": true,
    "dashpass_applied": true
}

Response (201 Created):
{
    "order_id": "ord_uuid_001",
    "order_number": "DD-7F3A9B",
    "status": "PLACED",
    "estimated_delivery": {
        "time_min": 35,
        "time_max": 45,
        "estimated_at": "2024-01-14T17:45:00Z",
        "breakdown": {
            "prep_time_min": 18,
            "pickup_time_min": 5,
            "transit_time_min": 12
        }
    },
    "pricing": {
        "subtotal": 32.50,
        "delivery_fee": 0.00,  // DashPass
        "service_fee": 4.88,
        "tax": 2.93,
        "tip": 5.00,
        "promo_discount": -5.00,
        "total": 40.31,
        "dashpass_savings": 5.99
    },
    "restaurant": {
        "name": "Tony's Pizza",
        "address": "789 Broadway, SF"
    },
    "tracking_url": "https://doordash.com/track/DD-7F3A9B"
}
```

### Get Order Status (Real-time via WebSocket)
```
// WebSocket connection
ws://tracking.doordash.com/orders/ord_uuid_001

// Server pushes status updates:
{
    "type": "ORDER_STATUS_UPDATE",
    "order_id": "ord_uuid_001",
    "status": "DASHER_EN_ROUTE_PICKUP",
    "dasher": {
        "name": "Mike S.",
        "photo_url": "https://...",
        "vehicle": "Silver Toyota Camry",
        "rating": 4.95
    },
    "dasher_location": {
        "lat": 37.7755,
        "lng": -122.4180,
        "heading": 180
    },
    "eta": {
        "pickup_eta_min": 3,
        "delivery_eta_min": 18,
        "updated_at": "2024-01-14T17:20:00Z"
    },
    "timeline": [
        {"event": "Order placed", "time": "5:00 PM", "completed": true},
        {"event": "Restaurant confirmed", "time": "5:01 PM", "completed": true},
        {"event": "Being prepared", "time": "5:02 PM", "completed": true},
        {"event": "Dasher picking up", "time": "5:18 PM", "completed": false, "current": true},
        {"event": "On the way", "time": null, "completed": false},
        {"event": "Delivered", "time": null, "completed": false}
    ]
}
```

### Search Restaurants
```
GET /api/v1/restaurants/search?lat=37.7749&lng=-122.4194&cuisine=italian&sort=rating&dashpass_only=true

Response:
{
    "restaurants": [
        {
            "restaurant_id": "rest_001",
            "name": "Tony's Pizza",
            "cuisine_types": ["Italian", "Pizza"],
            "rating": 4.8,
            "total_ratings": 2340,
            "delivery_time_estimate": {"min": 25, "max": 35},
            "delivery_fee": 3.99,
            "dashpass_free_delivery": true,
            "distance_km": 1.2,
            "price_range": "$$",
            "image_url": "https://cdn.doordash.com/...",
            "is_open": true,
            "popular_items": ["Margherita Pizza", "Garlic Knots"],
            "promo": {"text": "20% off $25+", "code": "TONY20"}
        }
    ],
    "total_results": 45,
    "filters_applied": {"cuisine": "italian", "dashpass": true}
}
```

## 7. Deep Dives

### Deep Dive 1: Delivery Time Prediction (ML Model)

**Model Architecture**:
```
Input Features → Feature Engineering → Gradient Boosted Trees → Time Prediction
                                                                  ├── Prep Time (restaurant)
                                                                  ├── Pickup Time (dasher wait)
                                                                  └── Transit Time (drive)
```

**Implementation**:
```python
import numpy as np
from dataclasses import dataclass
from typing import Optional

@dataclass
class DeliveryTimeFeatures:
    # Restaurant features
    restaurant_id: str
    historical_avg_prep_min: float
    current_order_queue: int  # Orders being prepared right now
    time_of_day_bucket: int   # 0-23
    day_of_week: int
    is_peak_hour: bool
    restaurant_rating: float
    
    # Order features
    item_count: int
    total_item_complexity: float  # Sum of per-item prep_time_addition
    has_custom_items: bool
    order_subtotal: float
    
    # Route features
    restaurant_to_customer_distance_m: float
    restaurant_to_customer_route_time_s: int  # From routing engine
    current_traffic_multiplier: float  # 1.0 = normal, 2.0 = heavy traffic
    
    # Dasher features (if already assigned)
    dasher_to_restaurant_distance_m: Optional[float]
    dasher_current_speed_mph: Optional[float]
    dasher_has_other_orders: bool
    dasher_avg_pickup_time_sec: Optional[int]
    
    # External features
    weather_condition: str  # CLEAR, RAIN, SNOW
    weather_severity: float  # 0-1

class DeliveryTimePredictionService:
    """
    Predicts total delivery time from order placement to door.
    
    Model trained on millions of historical deliveries.
    Features updated in real-time by Flink pipelines.
    """
    
    def __init__(self):
        self.prep_model = self._load_model('prep_time_v3')
        self.transit_model = self._load_model('transit_time_v2')
        self.pickup_model = self._load_model('pickup_time_v1')
    
    def predict_delivery_time(self, features: DeliveryTimeFeatures) -> dict:
        """Predict total delivery time with breakdown."""
        
        # 1. Predict restaurant prep time
        prep_features = self._extract_prep_features(features)
        prep_time_min = self.prep_model.predict(prep_features)
        
        # Apply queue adjustment (each order in queue adds time)
        queue_adjustment = features.current_order_queue * 2.5  # ~2.5 min per queued order
        adjusted_prep = prep_time_min + queue_adjustment
        
        # 2. Predict pickup time (dasher wait at restaurant)
        if features.dasher_to_restaurant_distance_m:
            dasher_travel = features.dasher_to_restaurant_distance_m / (
                features.dasher_current_speed_mph * 26.82  # mph to m/min
            )
        else:
            dasher_travel = 5.0  # Assume 5 min if not yet assigned
        
        # Dasher arrives before food ready? Wait at restaurant
        pickup_buffer = max(0, adjusted_prep - dasher_travel) + 2  # +2 min for handoff
        
        # 3. Predict transit time
        base_transit = features.restaurant_to_customer_route_time_s / 60.0
        traffic_adjusted = base_transit * features.current_traffic_multiplier
        
        # Weather adjustment
        weather_factor = {'CLEAR': 1.0, 'RAIN': 1.2, 'SNOW': 1.5}
        weather_adjusted = traffic_adjusted * weather_factor.get(features.weather_condition, 1.0)
        
        # Batch order adjustment
        if features.dasher_has_other_orders:
            weather_adjusted += 8  # Extra time for multi-drop
        
        # Total
        total_time_min = adjusted_prep + pickup_buffer + weather_adjusted
        
        # Confidence interval
        confidence = self._compute_confidence(features)
        margin = total_time_min * (1 - confidence) * 0.5
        
        return {
            'total_min': round(total_time_min),
            'range_min': round(total_time_min - margin),
            'range_max': round(total_time_min + margin),
            'breakdown': {
                'prep_time_min': round(adjusted_prep),
                'pickup_time_min': round(pickup_buffer),
                'transit_time_min': round(weather_adjusted)
            },
            'confidence': confidence,
            'model_version': 'v3.2.1'
        }
    
    def update_prediction_in_flight(self, order_id: str, 
                                     current_state: str,
                                     dasher_location: dict) -> dict:
        """
        Dynamically update delivery time as we learn more.
        Called whenever state changes or dasher location updates.
        """
        order = self.order_service.get_order(order_id)
        
        if current_state == 'PREPARING':
            # Update based on actual time spent so far
            time_in_prep = (now() - order['confirmed_at']).total_seconds() / 60
            remaining_prep = max(0, order['estimated_prep_time_min'] - time_in_prep)
            
            # If taking longer than estimate, update
            if time_in_prep > order['estimated_prep_time_min'] * 0.8:
                # Likely going to be late, add buffer
                remaining_prep += 3
            
            return self._recalculate_from_prep(order, remaining_prep, dasher_location)
        
        elif current_state == 'PICKED_UP':
            # Only transit remains - use real-time routing
            eta = self.routing_service.get_eta(
                from_lat=dasher_location['lat'],
                from_lng=dasher_location['lng'],
                to_lat=order['delivery_location']['lat'],
                to_lng=order['delivery_location']['lng'],
                traffic='live'
            )
            return {
                'total_min': round(eta['duration_min']),
                'range_min': round(eta['duration_min'] - 2),
                'range_max': round(eta['duration_min'] + 3)
            }
    
    def _compute_confidence(self, features: DeliveryTimeFeatures) -> float:
        """Higher confidence when we have more data about this restaurant."""
        base_confidence = 0.7
        
        # More historical data = higher confidence
        if features.historical_avg_prep_min > 0:
            base_confidence += 0.1
        
        # Peak hours are less predictable
        if features.is_peak_hour:
            base_confidence -= 0.1
        
        # Bad weather reduces confidence
        if features.weather_condition != 'CLEAR':
            base_confidence -= 0.05
        
        return min(0.95, max(0.5, base_confidence))


class PrepTimeLearningService:
    """
    Continuously learns restaurant prep times from actual data.
    Updates model features for each restaurant as deliveries complete.
    """
    
    def on_order_picked_up(self, order_id: str, restaurant_id: str,
                           confirmed_at: datetime, picked_up_at: datetime,
                           item_count: int, order_complexity: float):
        """Learn from actual prep time when Dasher picks up."""
        actual_prep_min = (picked_up_at - confirmed_at).total_seconds() / 60
        
        # Update running average with exponential decay
        current_features = self.redis.hgetall(f"rest:prep:{restaurant_id}")
        
        alpha = 0.1  # Learning rate
        current_avg = float(current_features.get('avg_prep', '20'))
        new_avg = (1 - alpha) * current_avg + alpha * actual_prep_min
        
        # Update per-item time
        current_per_item = float(current_features.get('per_item_time', '3'))
        actual_per_item = actual_prep_min / max(item_count, 1)
        new_per_item = (1 - alpha) * current_per_item + alpha * actual_per_item
        
        # Time-of-day adjustment
        hour = confirmed_at.hour
        time_bucket = f"hour_{hour}"
        current_hour_factor = float(current_features.get(time_bucket, '1.0'))
        actual_hour_factor = actual_prep_min / new_avg
        new_hour_factor = (1 - alpha) * current_hour_factor + alpha * actual_hour_factor
        
        self.redis.hset(f"rest:prep:{restaurant_id}", mapping={
            'avg_prep': str(round(new_avg, 1)),
            'per_item_time': str(round(new_per_item, 1)),
            time_bucket: str(round(new_hour_factor, 2)),
            'sample_count': str(int(current_features.get('sample_count', '0')) + 1),
            'last_updated': str(int(time.time()))
        })
```

### Deep Dive 2: Dasher Assignment (Bipartite Matching)

```python
from typing import List, Dict, Tuple
from scipy.optimize import linear_sum_assignment
import numpy as np

@dataclass
class OrderForAssignment:
    order_id: str
    restaurant_id: str
    restaurant_lat: float
    restaurant_lng: float
    customer_lat: float
    customer_lng: float
    placed_at: float  # Unix timestamp
    priority: float  # Higher = assign sooner (DashPass, waiting long)
    estimated_prep_remaining_min: float

@dataclass  
class DasherForAssignment:
    dasher_id: str
    lat: float
    lng: float
    current_orders: int
    max_concurrent: int
    rating: float
    acceptance_rate: float
    avg_speed_mph: float
    vehicle_type: str
    heading: float  # Current direction of travel

class DasherAssignmentEngine:
    """
    Bipartite matching: Assign available dashers to pending orders.
    
    Run every 5 seconds (batch window) to optimize across multiple orders.
    Considers:
    1. Dasher proximity to restaurant
    2. Current order load (can they batch?)
    3. Acceptance likelihood
    4. Customer wait time (don't let orders wait too long)
    5. Batching opportunity (two orders from same restaurant or same route)
    """
    
    BATCH_INTERVAL_SEC = 5
    MAX_ASSIGNMENT_DISTANCE_KM = 10
    
    def assign(self, pending_orders: List[OrderForAssignment],
               available_dashers: List[DasherForAssignment]) -> Dict[str, str]:
        """
        Returns: {order_id: dasher_id}
        Uses Hungarian algorithm for optimal assignment.
        """
        if not pending_orders or not available_dashers:
            return {}
        
        n_orders = len(pending_orders)
        n_dashers = len(available_dashers)
        
        # Build cost matrix
        cost_matrix = np.full((n_orders, n_dashers), 1e6)  # Infeasible default
        
        for i, order in enumerate(pending_orders):
            for j, dasher in enumerate(available_dashers):
                # Skip if dasher at capacity
                if dasher.current_orders >= dasher.max_concurrent:
                    continue
                
                cost = self._compute_assignment_cost(order, dasher)
                
                # Check if within max distance
                distance_km = self._haversine_km(
                    dasher.lat, dasher.lng,
                    order.restaurant_lat, order.restaurant_lng
                )
                if distance_km <= self.MAX_ASSIGNMENT_DISTANCE_KM:
                    cost_matrix[i][j] = cost
        
        # Solve assignment problem
        row_indices, col_indices = linear_sum_assignment(cost_matrix)
        
        assignments = {}
        for i, j in zip(row_indices, col_indices):
            if cost_matrix[i][j] < 1e5:  # Valid assignment
                assignments[pending_orders[i].order_id] = available_dashers[j].dasher_id
        
        return assignments
    
    def _compute_assignment_cost(self, order: OrderForAssignment, 
                                  dasher: DasherForAssignment) -> float:
        """
        Lower cost = better match. Components:
        """
        # 1. Travel time to restaurant (most important)
        distance_km = self._haversine_km(
            dasher.lat, dasher.lng,
            order.restaurant_lat, order.restaurant_lng
        )
        travel_time_min = (distance_km / dasher.avg_speed_mph) * 60 / 1.609
        
        # 2. Wait time penalty (orders waiting longer get priority)
        wait_time_sec = time.time() - order.placed_at
        wait_penalty = -min(wait_time_sec / 60, 10) * 2  # Negative = good (reduces cost)
        
        # 3. Acceptance probability
        decline_risk = (1.0 - dasher.acceptance_rate) * 15  # Big penalty for low acceptance
        
        # 4. Batching bonus (if dasher already has order from same restaurant or nearby)
        batch_bonus = 0
        if dasher.current_orders > 0:
            # Check if dasher's current order is on the same route
            batch_bonus = self._compute_batch_bonus(order, dasher)
        
        # 5. Direction bonus (is dasher heading toward restaurant?)
        direction_bonus = self._direction_alignment(
            dasher.lat, dasher.lng, dasher.heading,
            order.restaurant_lat, order.restaurant_lng
        )
        
        # 6. Priority adjustment (DashPass orders, high-value)
        priority_adjustment = -order.priority * 3
        
        # 7. Prep time alignment (arrive when food is ready)
        # Ideal: dasher arrives just as food is ready
        prep_remaining = order.estimated_prep_remaining_min
        arrival_gap = abs(travel_time_min - prep_remaining)
        timing_penalty = arrival_gap * 0.5
        
        total_cost = (
            travel_time_min * 3.0 +      # Weight: 3x
            wait_penalty +                 # Negative (bonus)
            decline_risk +
            batch_bonus +                  # Negative if good batch
            direction_bonus +              # Negative if aligned
            priority_adjustment +          # Negative for priority
            timing_penalty
        )
        
        return total_cost
    
    def _compute_batch_bonus(self, order: OrderForAssignment, 
                              dasher: DasherForAssignment) -> float:
        """Bonus for batching: same restaurant or delivery on same route."""
        # Get dasher's current orders
        current_orders = self.order_service.get_dasher_active_orders(dasher.dasher_id)
        
        for existing_order in current_orders:
            # Same restaurant? Big bonus!
            if existing_order['restaurant_id'] == order.restaurant_id:
                return -10.0  # Strong incentive to batch
            
            # Delivery address near this order's delivery?
            delivery_distance = self._haversine_km(
                existing_order['customer_lat'], existing_order['customer_lng'],
                order.customer_lat, order.customer_lng
            )
            if delivery_distance < 1.0:  # Within 1km
                return -5.0  # Good batch opportunity
        
        return 0
    
    def _direction_alignment(self, d_lat, d_lng, heading, 
                              r_lat, r_lng) -> float:
        """Bonus if dasher is already heading toward restaurant."""
        import math
        bearing_to_restaurant = self._bearing(d_lat, d_lng, r_lat, r_lng)
        angle_diff = abs(bearing_to_restaurant - heading)
        if angle_diff > 180:
            angle_diff = 360 - angle_diff
        
        # 0° diff = perfect alignment, 180° = opposite direction
        if angle_diff < 45:
            return -3.0  # Strong bonus
        elif angle_diff < 90:
            return -1.0
        return 0
```

### Deep Dive 3: Geofence-Based Order Availability

```python
import h3
from shapely.geometry import Point, Polygon

class GeofenceService:
    """
    Determines which restaurants are available to a customer based on:
    1. Restaurant's delivery radius
    2. DoorDash delivery zones (operational areas)
    3. Current driver supply in the area
    4. Dynamic zone adjustment based on conditions
    """
    
    def get_available_restaurants(self, customer_lat: float, customer_lng: float,
                                   filters: dict = None) -> List[dict]:
        """Find restaurants that can deliver to this location."""
        
        # 1. Check if customer is in a DoorDash service zone
        customer_point = Point(customer_lng, customer_lat)
        service_zone = self._get_service_zone(customer_point)
        
        if not service_zone:
            return []  # Not in delivery area
        
        # 2. Find restaurants within delivery distance
        # Use PostGIS spatial query
        restaurants = self.db.execute("""
            SELECT r.*, 
                ST_Distance(r.location::geography, 
                    ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography) / 1000 as distance_km
            FROM restaurants r
            WHERE r.status = 'ACTIVE' 
              AND r.is_open = TRUE
              AND ST_DWithin(
                  r.location::geography,
                  ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography,
                  r.delivery_radius_km * 1000  -- meters
              )
            ORDER BY distance_km
            LIMIT 100
        """, lat=customer_lat, lng=customer_lng)
        
        # 3. Filter by current Dasher supply
        customer_h3 = h3.latlng_to_cell(customer_lat, customer_lng, 7)
        nearby_dashers = self._count_available_dashers(customer_h3)
        
        # If very low supply, restrict to closer restaurants
        if nearby_dashers < 3:
            max_distance = 3.0  # km, reduced from normal
            restaurants = [r for r in restaurants if r['distance_km'] <= max_distance]
        
        # 4. Add delivery time estimates
        enriched = []
        for rest in restaurants:
            delivery_estimate = self.delivery_time_service.predict(
                restaurant_lat=rest['lat'],
                restaurant_lng=rest['lng'],
                customer_lat=customer_lat,
                customer_lng=customer_lng,
                restaurant_id=rest['restaurant_id']
            )
            enriched.append({
                **rest,
                'delivery_estimate': delivery_estimate,
                'delivery_fee': self._calculate_delivery_fee(
                    rest['distance_km'], service_zone, nearby_dashers
                )
            })
        
        return enriched
    
    def _calculate_delivery_fee(self, distance_km: float, 
                                 zone: dict, dasher_supply: int) -> float:
        """Dynamic delivery fee based on distance and supply."""
        base_fee = 2.99
        distance_fee = max(0, (distance_km - 2) * 0.50)  # $0.50 per km after 2km
        
        # Supply-based adjustment
        if dasher_supply < 5:
            supply_surcharge = 2.00  # Low supply premium
        elif dasher_supply < 10:
            supply_surcharge = 1.00
        else:
            supply_surcharge = 0
        
        return round(base_fee + distance_fee + supply_surcharge, 2)
    
    def on_dasher_location_update(self, dasher_id: str, lat: float, lng: float):
        """Update supply counts per H3 cell when dashers move."""
        new_cell = h3.latlng_to_cell(lat, lng, 7)
        old_cell = self.redis.hget(f"dasher:{dasher_id}", 'current_h3_cell')
        
        if old_cell != new_cell:
            pipe = self.redis.pipeline()
            if old_cell:
                pipe.hincrby("dasher_supply", old_cell, -1)
            pipe.hincrby("dasher_supply", new_cell, 1)
            pipe.hset(f"dasher:{dasher_id}", 'current_h3_cell', new_cell)
            pipe.execute()
```

## 8. Component Optimization

### Restaurant Menu Caching
```yaml
cache_strategy:
  # Menu data rarely changes - aggressive caching
  menu_cache:
    layer: Redis
    key: "menu:{restaurant_id}"
    ttl: 300  # 5 minutes
    invalidation: On menu update via Kafka event
    
  # Restaurant availability (changes frequently during day)
  availability_cache:
    layer: Redis
    key: "rest:avail:{restaurant_id}"
    ttl: 30  # 30 seconds
    
  # Delivery fee cache per zone
  delivery_fee_cache:
    layer: Redis
    key: "fee:{zone_id}:{distance_bucket}"
    ttl: 60  # Recalculated every minute
```

### Kafka Configuration
```yaml
topics:
  order.events:
    partitions: 64
    replication_factor: 3
    retention_ms: 604800000  # 7 days
    min_insync_replicas: 2
    compression_type: lz4
    
  dasher.locations:
    partitions: 128
    replication_factor: 2
    retention_ms: 3600000  # 1 hour
    compression_type: snappy
    
  assignment.events:
    partitions: 32
    replication_factor: 3
    retention_ms: 86400000
    
  restaurant.updates:
    partitions: 16
    replication_factor: 3
    cleanup_policy: compact
```

### Assignment Service Optimization
```python
class AssignmentBatcher:
    """
    Batch orders for 5 seconds before running assignment.
    During peak, might have 25 orders in a batch = much better optimization
    than assigning one at a time.
    """
    
    def __init__(self):
        self.batch_interval = 5  # seconds
        self.pending_orders = []
        self.assignment_engine = DasherAssignmentEngine()
    
    async def run(self):
        while True:
            await asyncio.sleep(self.batch_interval)
            
            if not self.pending_orders:
                continue
            
            # Snapshot and clear
            batch = self.pending_orders[:]
            self.pending_orders = []
            
            # Get available dashers for this batch's region
            regions = set(o.restaurant_h3 for o in batch)
            dashers = await self._get_available_dashers(regions)
            
            # Run optimization
            assignments = self.assignment_engine.assign(batch, dashers)
            
            # Dispatch assignments
            for order_id, dasher_id in assignments.items():
                await self._dispatch_to_dasher(order_id, dasher_id)
            
            # Unassigned orders stay for next batch (with increased priority)
            for order in batch:
                if order.order_id not in assignments:
                    order.priority += 1  # Increase priority for next round
                    self.pending_orders.append(order)
```

## 9. Observability

### Key Metrics
```yaml
metrics:
  # Delivery performance
  - name: delivery_time_total_minutes
    type: histogram
    labels: [city, restaurant_tier]
    buckets: [15, 20, 25, 30, 35, 40, 45, 60, 90]
  
  - name: delivery_time_prediction_error_minutes
    type: histogram
    labels: [model_version]
    buckets: [-10, -5, -3, -1, 0, 1, 3, 5, 10]
  
  - name: prep_time_actual_minutes
    type: histogram
    labels: [restaurant_id_bucket]
    buckets: [5, 10, 15, 20, 25, 30, 45, 60]
  
  # Assignment
  - name: assignment_latency_seconds
    type: histogram
    buckets: [5, 10, 15, 20, 30, 45, 60]
  
  - name: assignment_batch_size
    type: histogram
    buckets: [1, 2, 5, 10, 20, 50]
  
  - name: dasher_acceptance_total
    type: counter
    labels: [accepted, city]
  
  # Orders
  - name: orders_placed_total
    type: counter
    labels: [city, restaurant_cuisine, dashpass]
  
  - name: orders_cancelled_total
    type: counter
    labels: [cancelled_by, reason, stage]
  
  - name: order_value_dollars
    type: histogram
    labels: [city]
    buckets: [10, 15, 20, 30, 50, 75, 100, 200]
  
  # Supply/Demand
  - name: active_dashers_gauge
    type: gauge
    labels: [city, zone, status]
  
  - name: unassigned_orders_gauge
    type: gauge
    labels: [city, wait_time_bucket]
  
  # Customer satisfaction
  - name: customer_rating_distribution
    type: histogram
    labels: [city]
    buckets: [1, 2, 3, 4, 5]
  
  - name: dasher_rating_distribution
    type: histogram
    labels: [city]
    buckets: [1, 2, 3, 4, 5]
```

### Alerting
```yaml
alerts:
  - name: DeliveryTimeSLABreach
    expr: histogram_quantile(0.90, delivery_time_total_minutes) > 45
    for: 10m
    severity: warning
    
  - name: UnassignedOrdersHigh
    expr: unassigned_orders_gauge > 100
    for: 5m
    severity: critical
    annotation: "Orders waiting for Dasher assignment"
    
  - name: DasherSupplyLow
    expr: active_dashers_gauge{status="available"} / orders_placed_total[5m] < 0.5
    for: 10m
    severity: warning
    
  - name: HighCancellationRate
    expr: rate(orders_cancelled_total[1h]) / rate(orders_placed_total[1h]) > 0.1
    for: 30m
    severity: warning
    
  - name: PrepTimePredictionDrift
    expr: abs(avg(delivery_time_prediction_error_minutes)) > 5
    for: 20m
    severity: warning
    annotation: "ML model accuracy degrading - retrain needed"
```

## 10. Failure Scenarios & Considerations

### Dasher Goes Offline During Delivery
- **Detection**: No location updates for 60 seconds
- **Handling**: 
  1. Send push notification to Dasher
  2. After 3 min: reassign order to nearby Dasher
  3. Notify customer of delay
- **Prevention**: Low battery warning prompts, auto-assign backup Dasher for critical orders

### Restaurant Doesn't Confirm Order
- **Timeout**: 5 minutes to confirm
- **Handling**: Auto-cancel, full refund, notify customer with alternatives
- **Prevention**: Track confirmation rate, suspend repeatedly non-responsive restaurants

### Assignment Starvation (No Dashers Available)
- **Detection**: Order unassigned for > 5 minutes
- **Escalation**:
  1. Expand search radius
  2. Increase pay bonus for nearby Dashers
  3. If > 15 min: offer customer cancel with promo credit
- **Prevention**: Demand forecasting → proactive Dasher incentives

### Delivery Time Severely Underestimated
- **Detection**: Actual time > estimate + 15 min
- **Handling**: Proactive notification, offer credit, reduce delivery fee
- **Prevention**: Conservative estimates during high-uncertainty times, real-time adjustment

### Peak Hour Overload
- **Strategy**: 
  1. Dynamic delivery fees (reduces demand)
  2. Limit new orders per restaurant (prevents kitchen overload)
  3. Increase Dasher batch size
  4. Show "busy" status with longer delivery times

## 11. Technology Choices

| Component | Technology | Rationale |
|---|---|---|
| Order/Restaurant DB | PostgreSQL + PostGIS | Spatial queries, ACID |
| Dasher Location | Redis Cluster + H3 | Real-time geo-index |
| Event Bus | Apache Kafka | Order lifecycle events |
| Stream Processing | Apache Flink | Prep time learning, supply aggregation |
| Search | Elasticsearch | Restaurant search with geo + facets |
| ML Serving | TensorFlow Serving / SageMaker | Delivery time prediction |
| CDN | CloudFront | Menu images, static assets |
| WebSocket | Go service | Tracking connections |
| Assignment | Python + scipy | Optimization algorithms |
| Monitoring | Prometheus + Grafana | Operational metrics |
| Routing | OSRM | Self-hosted for low-latency ETAs |
