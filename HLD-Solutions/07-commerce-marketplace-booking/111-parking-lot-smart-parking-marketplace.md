# Design Smart Parking Marketplace

## 1. Functional Requirements

### Core Features
- **Real-Time Availability**: Live parking spot status via IoT sensors/cameras
- **Search & Discovery**: Find nearby parking by location, time, vehicle type
- **Reservation**: Book specific spot with time slot (advance or on-demand)
- **Dynamic Pricing**: Demand-based pricing with time-of-day, event, weather factors
- **Navigation**: In-app guidance to reserved spot (floor/zone/number)
- **Payment**: Hourly/daily/monthly passes, auto-charge on exit
- **Multi-Storey Floor Maps**: Interactive maps showing availability per floor
- **EV Charging**: Filter for EV spots, monitor charging status
- **Valet Service**: Request valet with real-time car status

### User Types
1. **Driver**: Searches, reserves, parks, pays
2. **Lot Operator**: Manages facility, sets pricing, monitors occupancy
3. **Enterprise**: Manages allocated parking for employees
4. **Valet Attendant**: Receives requests, manages car queue

## 2. Non-Functional Requirements

| Requirement | Target |
|---|---|
| Availability Display | Real-time (< 5s from sensor to app) |
| Search Latency | P99 < 300ms |
| Sensor Event Processing | < 2s end-to-end |
| Reservation Confirmation | < 1s |
| Payment Processing | < 3s |
| System Availability | 99.9% |
| Scale | 50K+ parking facilities, 5M+ spots |
| Concurrent Users | 500K during peak (morning/evening commute) |
| Sensor Data Ingestion | 1M+ events/min |
| Location Accuracy | Navigate to exact spot |

## 3. Capacity Estimation

### Storage
```
Parking facilities: 50K × 5KB = 250MB
Parking spots: 5M × 500B = 2.5GB
Floor maps: 50K facilities × 5 floors × 500KB = 125GB
Reservations: 20M/month × 1KB = 20GB/month
Sensor events: 5M spots × 24h × 2/h avg = 240M events/day × 200B = 48GB/day
Payment records: 20M/month × 500B = 10GB/month
User profiles: 10M × 1KB = 10GB
Historical occupancy: 50K × 365 × 24 × 200B = 87GB/year
```

### Throughput
```
Sensor events: 1M/min (16K/s)
Search queries: 10K/s peak
Availability checks: 20K/s
Reservation creates: 1K/s
Payment transactions: 500/s
WebSocket connections (floor maps): 100K concurrent
```

## 4. Data Modeling

### Full Database Schemas

```sql
-- Parking facilities
CREATE TABLE parking_facilities (
    facility_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(300) NOT NULL,
    operator_id UUID NOT NULL REFERENCES operators(operator_id),
    facility_type VARCHAR(30) NOT NULL, -- multi_storey, open_lot, underground, street
    latitude DECIMAL(10, 7) NOT NULL,
    longitude DECIMAL(10, 7) NOT NULL,
    address TEXT NOT NULL,
    city VARCHAR(100) NOT NULL,
    postal_code VARCHAR(10),
    total_spots INT NOT NULL,
    total_floors INT DEFAULT 1,
    has_ev_charging BOOLEAN DEFAULT FALSE,
    has_valet BOOLEAN DEFAULT FALSE,
    has_disabled_spots BOOLEAN DEFAULT TRUE,
    height_limit_cm INT, -- vehicle height restriction
    operating_hours JSONB, -- {"mon": {"open": "06:00", "close": "23:00"}, ...}
    is_24_hours BOOLEAN DEFAULT FALSE,
    base_rate_cents_per_hour INT NOT NULL,
    max_daily_rate_cents INT,
    monthly_pass_cents INT,
    ev_charging_rate_cents_per_kwh INT,
    accepted_vehicles VARCHAR(20)[], -- car, suv, motorcycle, truck
    amenities VARCHAR(50)[], -- covered, cctv, security, restroom, elevator
    avg_rating DECIMAL(3,2),
    review_count INT DEFAULT 0,
    status VARCHAR(20) DEFAULT 'active',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_facilities_location ON parking_facilities USING GIST(
    ST_MakePoint(longitude, latitude)::geography
);
CREATE INDEX idx_facilities_city ON parking_facilities(city, status) WHERE status = 'active';

-- Floors/Zones within a facility
CREATE TABLE facility_floors (
    floor_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    facility_id UUID NOT NULL REFERENCES parking_facilities(facility_id),
    floor_number INT NOT NULL, -- -2, -1, 0 (ground), 1, 2...
    floor_name VARCHAR(50), -- "Level B2", "Rooftop"
    total_spots INT NOT NULL,
    available_spots INT NOT NULL,
    has_ev_charging BOOLEAN DEFAULT FALSE,
    has_disabled BOOLEAN DEFAULT FALSE,
    height_limit_cm INT,
    floor_map_url TEXT, -- SVG/image of floor layout
    zones JSONB, -- [{"zone": "A", "spots": 50}, {"zone": "B", "spots": 60}]
    status VARCHAR(20) DEFAULT 'active',
    UNIQUE(facility_id, floor_number)
);
CREATE INDEX idx_floors_facility ON facility_floors(facility_id);

-- Individual parking spots
CREATE TABLE parking_spots (
    spot_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    facility_id UUID NOT NULL REFERENCES parking_facilities(facility_id),
    floor_id UUID NOT NULL REFERENCES facility_floors(floor_id),
    spot_number VARCHAR(10) NOT NULL, -- "A-042", "B2-15"
    zone VARCHAR(10),
    spot_type VARCHAR(30) NOT NULL, -- regular, compact, suv, disabled, ev_charging, motorcycle, valet
    vehicle_types VARCHAR(20)[], -- compatible vehicle types
    has_ev_charger BOOLEAN DEFAULT FALSE,
    ev_charger_type VARCHAR(20), -- level2, dc_fast, tesla
    ev_charger_kw INT,
    is_covered BOOLEAN DEFAULT TRUE,
    x_position DECIMAL(6,2), -- position on floor map (normalized 0-100)
    y_position DECIMAL(6,2),
    sensor_id VARCHAR(50), -- IoT sensor identifier
    camera_id VARCHAR(50), -- camera-based detection
    current_status VARCHAR(20) DEFAULT 'available',
    -- available, occupied, reserved, maintenance, out_of_service
    occupied_since TIMESTAMP,
    reserved_by UUID, -- reservation_id
    last_sensor_update TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_spots_facility_status ON parking_spots(facility_id, current_status);
CREATE INDEX idx_spots_floor ON parking_spots(floor_id, current_status);
CREATE INDEX idx_spots_sensor ON parking_spots(sensor_id);
CREATE UNIQUE INDEX idx_spots_number ON parking_spots(facility_id, spot_number);

-- Sensor events (high-volume time-series)
CREATE TABLE sensor_events (
    event_id BIGSERIAL,
    sensor_id VARCHAR(50) NOT NULL,
    spot_id UUID NOT NULL,
    facility_id UUID NOT NULL,
    event_type VARCHAR(20) NOT NULL, -- occupied, vacated, heartbeat, error
    confidence DECIMAL(3,2), -- 0.0 to 1.0 (for camera-based detection)
    vehicle_plate VARCHAR(20), -- license plate if detected
    vehicle_type VARCHAR(20),
    raw_data JSONB, -- raw sensor payload
    recorded_at TIMESTAMP NOT NULL DEFAULT NOW()
) PARTITION BY RANGE (recorded_at);
-- Daily partitions (high volume)
CREATE TABLE sensor_events_2024_07_15 PARTITION OF sensor_events
    FOR VALUES FROM ('2024-07-15') TO ('2024-07-16');

-- Reservations
CREATE TABLE reservations (
    reservation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(user_id),
    facility_id UUID NOT NULL REFERENCES parking_facilities(facility_id),
    spot_id UUID REFERENCES parking_spots(spot_id), -- NULL if any-spot reservation
    floor_id UUID REFERENCES facility_floors(floor_id),
    vehicle_id UUID REFERENCES user_vehicles(vehicle_id),
    reservation_type VARCHAR(20) NOT NULL, -- on_demand, advance, monthly
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP NOT NULL,
    actual_entry_time TIMESTAMP,
    actual_exit_time TIMESTAMP,
    status VARCHAR(20) NOT NULL DEFAULT 'confirmed',
    -- confirmed, active (parked), completed, cancelled, no_show, expired
    estimated_cost_cents INT,
    actual_cost_cents INT,
    payment_method VARCHAR(30),
    payment_status VARCHAR(20) DEFAULT 'pending',
    promo_code VARCHAR(30),
    discount_cents INT DEFAULT 0,
    ev_charging_requested BOOLEAN DEFAULT FALSE,
    valet_requested BOOLEAN DEFAULT FALSE,
    qr_code_data TEXT, -- for entry/exit gate scanning
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_reservations_user ON reservations(user_id, created_at DESC);
CREATE INDEX idx_reservations_facility_time ON reservations(facility_id, start_time, end_time) 
    WHERE status IN ('confirmed', 'active');
CREATE INDEX idx_reservations_spot ON reservations(spot_id, start_time, end_time) 
    WHERE status IN ('confirmed', 'active');

-- Pricing rules
CREATE TABLE pricing_rules (
    rule_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    facility_id UUID NOT NULL REFERENCES parking_facilities(facility_id),
    name VARCHAR(100),
    priority INT DEFAULT 0, -- higher priority overrides lower
    rule_type VARCHAR(30), -- base, peak, event, weather, surge
    conditions JSONB NOT NULL,
    -- {"day_of_week": [1,2,3,4,5], "hour_range": [8,18], "occupancy_above": 0.8}
    rate_cents_per_hour INT,
    rate_multiplier DECIMAL(3,2), -- e.g., 1.5 for 50% surge
    max_daily_cap_cents INT,
    valid_from TIMESTAMP,
    valid_to TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_pricing_facility ON pricing_rules(facility_id, is_active) WHERE is_active = TRUE;

-- User vehicles
CREATE TABLE user_vehicles (
    vehicle_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(user_id),
    license_plate VARCHAR(20) NOT NULL,
    vehicle_type VARCHAR(20) NOT NULL, -- car, suv, motorcycle, truck
    make VARCHAR(50),
    model VARCHAR(50),
    color VARCHAR(30),
    is_ev BOOLEAN DEFAULT FALSE,
    is_default BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Users
CREATE TABLE users (
    user_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    phone VARCHAR(15) UNIQUE NOT NULL,
    email VARCHAR(255),
    name VARCHAR(200),
    wallet_balance_cents INT DEFAULT 0,
    monthly_pass_facility_id UUID,
    monthly_pass_expiry DATE,
    preferred_facility_ids UUID[],
    created_at TIMESTAMP DEFAULT NOW()
);

-- Occupancy history (aggregated for analytics/forecasting)
CREATE TABLE occupancy_history (
    facility_id UUID NOT NULL,
    recorded_at TIMESTAMP NOT NULL,
    total_spots INT NOT NULL,
    occupied_spots INT NOT NULL,
    reserved_spots INT NOT NULL,
    occupancy_rate DECIMAL(4,3), -- 0.000 to 1.000
    avg_duration_minutes INT,
    PRIMARY KEY (facility_id, recorded_at)
);

-- EV charging sessions
CREATE TABLE ev_charging_sessions (
    session_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    reservation_id UUID REFERENCES reservations(reservation_id),
    spot_id UUID NOT NULL REFERENCES parking_spots(spot_id),
    user_id UUID NOT NULL REFERENCES users(user_id),
    charger_type VARCHAR(20),
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP,
    energy_delivered_kwh DECIMAL(6,2),
    cost_cents INT,
    status VARCHAR(20) DEFAULT 'charging', -- charging, complete, interrupted
    created_at TIMESTAMP DEFAULT NOW()
);

-- Valet requests
CREATE TABLE valet_requests (
    request_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    reservation_id UUID REFERENCES reservations(reservation_id),
    user_id UUID NOT NULL,
    facility_id UUID NOT NULL,
    attendant_id UUID,
    request_type VARCHAR(20), -- park, retrieve
    vehicle_id UUID REFERENCES user_vehicles(vehicle_id),
    spot_assigned UUID REFERENCES parking_spots(spot_id),
    status VARCHAR(20) DEFAULT 'pending', -- pending, assigned, in_progress, completed
    requested_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP,
    tip_cents INT DEFAULT 0
);
```

## 5. High-Level Design (HLD)

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                              IoT / SENSOR LAYER                                   │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐  ┌─────────────┐  │
│  │Ultrasonic│  │  Camera  │  │Magnetic  │  │  Gate/Barrier│  │ EV Charger  │  │
│  │ Sensors  │  │  (ANPR)  │  │ Sensors  │  │  Controllers │  │ Controllers │  │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └──────┬───────┘  └──────┬──────┘  │
│       │              │              │               │                 │          │
│       └──────────────┴──────────────┴───────┬───────┴─────────────────┘          │
│                                             │                                    │
│                                    ┌────────▼────────┐                           │
│                                    │  IoT Gateway    │                           │
│                                    │  (Edge Compute) │                           │
│                                    └────────┬────────┘                           │
└─────────────────────────────────────────────┼────────────────────────────────────┘
                                              │ MQTT/HTTPS
                                              ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│                         INGESTION & PROCESSING                                    │
│  ┌────────────────┐  ┌─────────────────┐  ┌──────────────────┐                 │
│  │  Kafka Topics  │  │  Apache Flink   │  │  Redis (State)   │                 │
│  │                │  │                 │  │                  │                 │
│  │- sensor.events │  │- Event dedup    │  │- Spot status     │                 │
│  │- availability  │  │- Occupancy calc │  │- Floor counters  │                 │
│  │- pricing.calc  │  │- Anomaly detect │  │- Facility avail  │                 │
│  │- entry.exit    │  │- Heartbeat mon  │  │- Pricing cache   │                 │
│  └────────────────┘  └─────────────────┘  └──────────────────┘                 │
└──────────────────────────────────────┬───────────────────────────────────────────┘
                                       │
┌──────────────────────────────────────▼───────────────────────────────────────────┐
│                         APPLICATION SERVICES                                      │
│                                                                                   │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌──────────────┐ │
│  │  Search   │  │Reservation│  │  Pricing  │  │Navigation │  │  Payment     │ │
│  │  Service  │  │  Service  │  │  Engine   │  │  Service  │  │  Service     │ │
│  │           │  │           │  │           │  │           │  │              │ │
│  │- Geo srch │  │- Reserve  │  │- Dynamic  │  │- Route to │  │- Charge      │ │
│  │- Filter   │  │- Extend   │  │- Forecast │  │  spot     │  │- Wallet      │ │
│  │- ETA      │  │- Cancel   │  │- Surge    │  │- Floor map│  │- Monthly     │ │
│  │- Suggest  │  │- Validate │  │- Promo    │  │- AR guide │  │- Receipt     │ │
│  └───────────┘  └───────────┘  └───────────┘  └───────────┘  └──────────────┘ │
│                                                                                   │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐                                   │
│  │  Valet    │  │    EV     │  │ Analytics │                                   │
│  │  Service  │  │  Charging │  │ & Forecast│                                   │
│  └───────────┘  └───────────┘  └───────────┘                                   │
└──────────────────────────────────────────────────────────────────────────────────┘
         │               │                │
         ▼               ▼                ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│                          DATA STORES                                               │
│ ┌────────────┐ ┌────────────┐ ┌──────────────┐ ┌──────────────┐                │
│ │ PostgreSQL │ │ TimescaleDB│ │    Redis     │ │    S3        │                │
│ │            │ │            │ │              │ │              │                │
│ │- Facilities│ │- Sensor    │ │- Real-time   │ │- Floor maps  │                │
│ │- Spots     │ │  events    │ │  availability│ │- Reports     │                │
│ │- Reserves  │ │- Occupancy │ │- Pricing     │ │- ML models   │                │
│ │- Users     │ │  history   │ │- Sessions    │ │              │                │
│ └────────────┘ └────────────┘ └──────────────┘ └──────────────┘                │
└──────────────────────────────────────────────────────────────────────────────────┘
```

## 6. Low-Level Design (LLD) - APIs

### Search Parking API
```
POST /api/v1/parking/search
Request:
{
    "latitude": 40.7580,
    "longitude": -73.9855,
    "radius_km": 2,
    "arrival_time": "2024-07-15T09:00:00-04:00",
    "duration_hours": 4,
    "vehicle_type": "car",
    "filters": {
        "covered": true,
        "ev_charging": false,
        "max_price_per_hour": 25,
        "min_rating": 4.0,
        "valet_available": false,
        "height_min_cm": 180
    },
    "sort": "price"
}

Response:
{
    "results": [
        {
            "facility_id": "fac_001",
            "name": "Times Square Parking Garage",
            "type": "multi_storey",
            "distance_km": 0.3,
            "walking_time_min": 4,
            "total_spots": 800,
            "available_spots": 123,
            "occupancy_percent": 84,
            "pricing": {
                "rate_per_hour_cents": 1800,
                "estimated_total_cents": 7200,
                "surge_active": true,
                "surge_multiplier": 1.5,
                "max_daily_cents": 5500
            },
            "features": ["covered", "cctv", "elevator", "24_hours"],
            "ev_spots_available": 5,
            "rating": 4.2,
            "floors_available": [
                {"floor": 2, "available": 45},
                {"floor": 3, "available": 38},
                {"floor": 4, "available": 40}
            ],
            "entry_point": {"lat": 40.7582, "lng": -73.9857},
            "thumbnail": "https://cdn.smartpark.com/..."
        }
    ],
    "total_results": 18,
    "search_id": "srch_abc"
}
```

### Reserve Spot API
```
POST /api/v1/reservations
Request:
{
    "facility_id": "fac_001",
    "spot_type": "regular",  // or specific spot_id
    "floor_preference": 2,
    "vehicle_id": "veh_123",
    "start_time": "2024-07-15T09:00:00-04:00",
    "end_time": "2024-07-15T13:00:00-04:00",
    "ev_charging": false,
    "payment_method": "wallet"
}

Response:
{
    "reservation_id": "res_789",
    "status": "confirmed",
    "spot": {
        "spot_id": "spot_456",
        "spot_number": "2-A042",
        "floor": 2,
        "zone": "A",
        "type": "regular"
    },
    "timing": {
        "start": "2024-07-15T09:00:00-04:00",
        "end": "2024-07-15T13:00:00-04:00",
        "grace_period_minutes": 15
    },
    "pricing": {
        "rate_per_hour": 18.00,
        "estimated_total": 72.00,
        "currency": "USD"
    },
    "access": {
        "qr_code_url": "https://cdn.smartpark.com/qr/res_789.png",
        "entry_code": "7891",
        "entry_point": {"lat": 40.7582, "lng": -73.9857}
    },
    "navigation": {
        "directions": "Enter from 45th St, take ramp to Floor 2, Zone A. Your spot is A-042 on the left.",
        "floor_map_url": "https://cdn.smartpark.com/maps/fac_001/floor_2.svg"
    }
}
```

### Real-Time Floor Map API (WebSocket)
```
// Connect: wss://ws.smartpark.com/facilities/{facility_id}/floors/{floor_number}

// Initial state (on connect):
{
    "type": "floor_state",
    "floor": 2,
    "total_spots": 150,
    "available": 45,
    "spots": [
        {"spot_id": "spot_001", "number": "2-A001", "x": 10.5, "y": 5.2, "status": "available", "type": "regular"},
        {"spot_id": "spot_002", "number": "2-A002", "x": 12.0, "y": 5.2, "status": "occupied", "type": "regular"},
        {"spot_id": "spot_003", "number": "2-A003", "x": 13.5, "y": 5.2, "status": "reserved", "type": "ev_charging"}
    ]
}

// Live updates:
{
    "type": "spot_update",
    "spot_id": "spot_045",
    "number": "2-A045",
    "old_status": "occupied",
    "new_status": "available",
    "timestamp": "2024-07-15T09:15:32Z"
}
```

### Sensor Event Ingestion API (IoT Gateway)
```
POST /api/v1/sensors/events (batch)
Request:
{
    "gateway_id": "gw_001",
    "events": [
        {
            "sensor_id": "sns_A042",
            "event_type": "occupied",
            "confidence": 0.97,
            "vehicle_detected": true,
            "plate_number": "ABC1234",
            "timestamp": "2024-07-15T09:02:15.456Z"
        },
        {
            "sensor_id": "sns_A043",
            "event_type": "vacated",
            "confidence": 0.99,
            "timestamp": "2024-07-15T09:02:16.123Z"
        },
        {
            "sensor_id": "sns_A044",
            "event_type": "heartbeat",
            "battery_level": 0.85,
            "timestamp": "2024-07-15T09:02:16.500Z"
        }
    ]
}
```

## 7. Deep Dives

### Deep Dive 1: Real-Time Availability Aggregation (IoT → User)

```python
class SensorEventProcessor:
    """
    Flink streaming job processing sensor events.
    Pipeline: IoT Sensor → MQTT → Kafka → Flink → Redis → WebSocket → User App
    
    Challenges:
    - Sensor failures (false positives/negatives)
    - Network latency causing out-of-order events
    - 16K events/second throughput
    - Sub-5-second end-to-end latency
    """
    
    def __init__(self, redis, kafka, ws_broadcaster):
        self.redis = redis
        self.kafka = kafka
        self.ws = ws_broadcaster
        self.spot_states = {}  # In-memory state per spot
    
    async def process_event(self, event: SensorEvent):
        spot_id = event.spot_id
        
        # Step 1: Deduplication (idempotency key)
        dedup_key = f"dedup:{event.sensor_id}:{event.timestamp}"
        if await self.redis.exists(dedup_key):
            return  # Already processed
        await self.redis.setex(dedup_key, 60, "1")  # 60s dedup window
        
        # Step 2: Confidence filtering (reject low-confidence events)
        if event.event_type != 'heartbeat' and event.confidence < 0.80:
            # Low confidence - wait for confirmation
            await self._queue_for_confirmation(event)
            return
        
        # Step 3: State transition validation
        current_state = await self._get_current_state(spot_id)
        new_state = self._determine_state(event, current_state)
        
        if new_state == current_state.status:
            return  # No actual change
        
        # Step 4: Update spot state
        await self._update_spot_state(spot_id, new_state, event)
        
        # Step 5: Update facility/floor counters
        await self._update_counters(event.facility_id, event.floor_id, current_state.status, new_state)
        
        # Step 6: Broadcast to WebSocket clients
        await self._broadcast_update(event.facility_id, event.floor_id, spot_id, new_state)
    
    def _determine_state(self, event: SensorEvent, current: SpotState) -> str:
        """Determine actual state considering sensor reliability"""
        if event.event_type == 'occupied':
            if current.status == 'reserved':
                # Reserved spot now occupied - reservation activated
                return 'occupied'
            return 'occupied'
        elif event.event_type == 'vacated':
            return 'available'
        return current.status
    
    async def _update_counters(self, facility_id, floor_id, old_status, new_status):
        """Atomic counter updates in Redis"""
        pipe = self.redis.pipeline()
        
        if old_status == 'available' and new_status == 'occupied':
            pipe.hincrby(f"facility:{facility_id}", "available", -1)
            pipe.hincrby(f"facility:{facility_id}", "occupied", 1)
            pipe.hincrby(f"floor:{floor_id}", "available", -1)
            pipe.hincrby(f"floor:{floor_id}", "occupied", 1)
        elif old_status == 'occupied' and new_status == 'available':
            pipe.hincrby(f"facility:{facility_id}", "available", 1)
            pipe.hincrby(f"facility:{facility_id}", "occupied", -1)
            pipe.hincrby(f"floor:{floor_id}", "available", 1)
            pipe.hincrby(f"floor:{floor_id}", "occupied", -1)
        
        await pipe.execute()

class SensorHealthMonitor:
    """Monitors sensor heartbeats and handles failures"""
    
    HEARTBEAT_INTERVAL_SECONDS = 300  # Expected heartbeat every 5 min
    FAILURE_THRESHOLD = 3  # 3 missed heartbeats = sensor down
    
    async def check_sensor_health(self):
        """Periodic job (every minute) checking sensor health"""
        sensors = await self.get_all_active_sensors()
        now = datetime.utcnow()
        
        for sensor in sensors:
            last_heartbeat = await self.redis.hget(f"sensor:{sensor.sensor_id}", "last_heartbeat")
            
            if last_heartbeat:
                elapsed = (now - datetime.fromisoformat(last_heartbeat)).total_seconds()
                missed = int(elapsed / self.HEARTBEAT_INTERVAL_SECONDS)
                
                if missed >= self.FAILURE_THRESHOLD:
                    await self._handle_sensor_failure(sensor)
    
    async def _handle_sensor_failure(self, sensor):
        """When sensor fails, mark spot as 'unknown' and alert operator"""
        await self.redis.hset(f"spot:{sensor.spot_id}", "status", "unknown")
        await self.redis.hset(f"spot:{sensor.spot_id}", "sensor_healthy", "false")
        
        # Alert facility operator
        await self.notification_service.alert_operator(
            sensor.facility_id,
            f"Sensor {sensor.sensor_id} at spot {sensor.spot_number} is unresponsive"
        )
        
        # Fall back to camera-based detection if available
        if sensor.backup_camera_id:
            await self._activate_camera_fallback(sensor)
```

### Deep Dive 2: Demand Forecasting for Dynamic Pricing

```python
class DemandForecastingEngine:
    """
    Time-series prediction for parking demand.
    Uses: Historical patterns + Events + Weather + Day-of-week + Holidays
    
    Model: Prophet/LSTM hybrid for each facility
    Granularity: Hourly predictions, 7 days ahead
    """
    
    def __init__(self, model_store, feature_store, event_api, weather_api):
        self.models = model_store
        self.features = feature_store
        self.events = event_api
        self.weather = weather_api
    
    async def forecast(self, facility_id: str, hours_ahead: int = 168) -> List[HourlyForecast]:
        """Predict occupancy for next 7 days (168 hours)"""
        
        # Load facility-specific model
        model = await self.models.load(f"demand_model_{facility_id}")
        
        # Extract features
        features = await self._extract_features(facility_id, hours_ahead)
        
        # Generate predictions
        predictions = model.predict(features)
        
        return [
            HourlyForecast(
                timestamp=features[i]['timestamp'],
                predicted_occupancy=predictions[i],
                confidence_interval=(predictions[i] * 0.9, min(1.0, predictions[i] * 1.1))
            )
            for i in range(hours_ahead)
        ]
    
    async def _extract_features(self, facility_id: str, hours: int) -> List[dict]:
        """Feature engineering for demand prediction"""
        features = []
        now = datetime.utcnow()
        
        # Historical patterns (same hour, same day-of-week, last 4 weeks)
        historical = await self._get_historical_patterns(facility_id)
        
        # Upcoming events within 2km
        nearby_events = await self.events.get_nearby(facility_id, days_ahead=7)
        
        # Weather forecast
        weather = await self.weather.forecast(facility_id, days_ahead=7)
        
        for hour_offset in range(hours):
            target_time = now + timedelta(hours=hour_offset)
            
            features.append({
                'timestamp': target_time,
                'hour_of_day': target_time.hour,
                'day_of_week': target_time.weekday(),
                'is_weekend': target_time.weekday() >= 5,
                'is_holiday': self._is_holiday(target_time),
                'month': target_time.month,
                
                # Historical same-period occupancy
                'hist_avg_occupancy_same_hour': historical.get_avg(target_time.hour, target_time.weekday()),
                'hist_std_occupancy': historical.get_std(target_time.hour, target_time.weekday()),
                'trend_7d': historical.get_trend_7d(target_time),
                
                # Events
                'event_within_500m': self._check_event(nearby_events, target_time, 500),
                'event_within_1km': self._check_event(nearby_events, target_time, 1000),
                'event_capacity': self._event_capacity(nearby_events, target_time),
                
                # Weather
                'temperature': weather.get_temp(target_time),
                'precipitation_prob': weather.get_rain_prob(target_time),
                'is_severe_weather': weather.is_severe(target_time),
            })
        
        return features

class DynamicPricingEngine:
    """Calculates real-time price based on demand forecast and current occupancy"""
    
    async def calculate_price(self, facility_id: str, spot_type: str, 
                              start_time: datetime, duration_hours: int) -> PriceResult:
        # Get base rate
        base_rate = await self._get_base_rate(facility_id, spot_type)
        
        # Get current occupancy
        current_occupancy = await self._get_occupancy(facility_id)
        
        # Get demand forecast
        forecast = await self.forecaster.forecast(facility_id, duration_hours)
        avg_predicted_occupancy = sum(f.predicted_occupancy for f in forecast) / len(forecast)
        
        # Calculate surge multiplier
        multiplier = self._calculate_multiplier(current_occupancy, avg_predicted_occupancy)
        
        # Check for event-based pricing
        event_multiplier = await self._check_event_pricing(facility_id, start_time)
        
        # Apply pricing rules (ordered by priority)
        rules = await self._get_active_rules(facility_id, start_time)
        final_multiplier = self._apply_rules(multiplier, event_multiplier, rules)
        
        # Calculate total
        hourly_rate = int(base_rate * final_multiplier)
        total = hourly_rate * duration_hours
        
        # Cap at max daily rate
        max_daily = await self._get_max_daily(facility_id)
        total = min(total, max_daily)
        
        return PriceResult(
            hourly_rate_cents=hourly_rate,
            total_cents=total,
            multiplier=final_multiplier,
            is_surge=final_multiplier > 1.0,
            breakdown={
                'base_rate': base_rate,
                'occupancy_surge': multiplier,
                'event_premium': event_multiplier,
                'duration_hours': duration_hours
            }
        )
    
    def _calculate_multiplier(self, current_occ: float, predicted_occ: float) -> float:
        """Pricing multiplier based on occupancy"""
        # Use max of current and predicted
        effective_occ = max(current_occ, predicted_occ)
        
        if effective_occ >= 0.95:
            return 2.5  # Near full - premium pricing
        elif effective_occ >= 0.85:
            return 1.8
        elif effective_occ >= 0.70:
            return 1.3
        elif effective_occ >= 0.50:
            return 1.0  # Base rate
        elif effective_occ >= 0.30:
            return 0.8  # Discount to attract
        else:
            return 0.6  # Deep discount
```

### Deep Dive 3: Spot Recommendation Algorithm

```python
class SpotRecommendationEngine:
    """
    Recommends optimal parking spot based on:
    1. Distance from destination (walking time after parking)
    2. Price (cheaper spots on higher floors)
    3. Availability probability (will the spot still be free when I arrive?)
    4. User preferences (covered, near elevator, near exit)
    5. Vehicle compatibility
    """
    
    async def recommend(self, user_id: str, params: SearchParams) -> List[SpotRecommendation]:
        # Get user preferences from history
        user_prefs = await self._get_user_preferences(user_id)
        
        # Find candidate facilities
        facilities = await self._search_facilities(params)
        
        recommendations = []
        for facility in facilities:
            score = self._score_facility(facility, params, user_prefs)
            
            # Find best spot within facility
            best_spot = await self._find_best_spot(facility, params, user_prefs)
            
            recommendations.append(SpotRecommendation(
                facility=facility,
                spot=best_spot,
                score=score,
                reasons=self._explain_recommendation(facility, best_spot, params)
            ))
        
        recommendations.sort(key=lambda r: r.score, reverse=True)
        return recommendations[:10]
    
    def _score_facility(self, facility, params, user_prefs) -> float:
        score = 0.0
        
        # Walking distance to destination (35%)
        walk_time = self._calculate_walk_time(facility.location, params.destination)
        walk_score = 1.0 - min(walk_time / 15, 1.0)  # 15 min walk = 0 score
        score += 0.35 * walk_score
        
        # Price (25%)
        estimated_cost = self._estimate_cost(facility, params.duration_hours)
        price_budget_ratio = estimated_cost / params.max_price if params.max_price else 0.5
        price_score = 1.0 - min(price_budget_ratio, 1.0)
        score += 0.25 * price_score
        
        # Availability probability (20%)
        # P(spot available when user arrives)
        eta_minutes = self._driving_eta(params.current_location, facility.location)
        avail_prob = self._predict_availability_at_arrival(facility, eta_minutes)
        score += 0.20 * avail_prob
        
        # Amenities match (10%)
        amenity_match = len(set(user_prefs.preferred_amenities) & set(facility.amenities))
        score += 0.10 * min(amenity_match / 3, 1.0)
        
        # Rating (10%)
        score += 0.10 * (facility.avg_rating / 5.0)
        
        return score
    
    def _predict_availability_at_arrival(self, facility, eta_minutes: int) -> float:
        """Predict if spots will still be available when user arrives"""
        current_available = facility.available_spots
        current_occupancy_rate = 1 - (current_available / facility.total_spots)
        
        # Historical fill rate at this time
        historical_fill_rate = self._get_fill_rate(facility.facility_id, eta_minutes)
        
        # Predicted spots that will be taken in eta_minutes
        predicted_taken = historical_fill_rate * eta_minutes
        predicted_available = max(0, current_available - predicted_taken)
        
        # Probability of at least 1 spot available
        if predicted_available > 5:
            return 0.99
        elif predicted_available > 2:
            return 0.90
        elif predicted_available > 0:
            return 0.70
        else:
            return 0.30
```

## 8. Component Optimization

### Kafka Configuration for IoT Events
```yaml
topics:
  sensor.events.raw:
    partitions: 128  # High parallelism for 16K events/s
    replication.factor: 2
    retention.ms: 86400000  # 1 day
    compression.type: snappy
    segment.ms: 3600000  # 1 hour segments
    # Partition by facility_id for locality
    
  availability.updates:
    partitions: 32
    replication.factor: 3
    retention.ms: 3600000  # 1 hour
    compression.type: lz4
    
  pricing.recalculations:
    partitions: 16
    replication.factor: 2
    retention.ms: 86400000

consumer_config:
  sensor_processor:
    group.id: sensor-event-processor
    max.poll.records: 1000
    fetch.min.bytes: 10000
    auto.offset.reset: latest
```

### Redis Data Structures
```python
# Facility availability (Hash)
# Key: "facility:{facility_id}"
# Fields: total, available, occupied, reserved, unknown
# Updated atomically on every sensor event

# Floor availability (Hash)  
# Key: "floor:{floor_id}"
# Fields: total, available, occupied

# Spot status (Hash)
# Key: "spot:{spot_id}"
# Fields: status, occupied_since, reserved_by, sensor_healthy, last_update

# Geospatial index for search
# Key: "parking_locations"
# GEOADD parking_locations lng lat facility_id

# Pricing cache
# Key: "price:{facility_id}:{hour}"
# Value: current_rate_cents
# TTL: 300 (recalculated every 5 min)

REDIS_CONFIG = {
    "cluster_nodes": 12,
    "memory_per_node_gb": 16,
    "persistence": "rdb_hourly",  # Periodic RDB for recovery
    "maxmemory_policy": "volatile-lfu",
}
```

### Flink Job Configuration
```yaml
flink_job:
  name: sensor-event-processor
  parallelism: 32
  checkpoint_interval_ms: 10000
  state_backend: rocksdb
  watermark_strategy: bounded_out_of_order(5_seconds)
  
  sources:
    - kafka_topic: sensor.events.raw
      deserializer: json
      
  sinks:
    - redis: spot_status_updates
    - kafka: availability.updates
    - timescaledb: sensor_events_archive
```

## 9. Observability

### Key Metrics
```yaml
metrics:
  - name: sensor_event_processing_latency_ms
    type: histogram
    labels: [facility_id, event_type]
    buckets: [10, 50, 100, 500, 1000, 2000, 5000]
    
  - name: availability_propagation_delay_ms
    type: histogram
    description: "Time from sensor event to user app display"
    
  - name: sensor_health_rate
    type: gauge
    labels: [facility_id]
    description: "% of sensors sending heartbeats on time"
    
  - name: occupancy_rate
    type: gauge
    labels: [facility_id, floor]
    
  - name: reservation_conversion_rate
    type: gauge
    labels: [source]
    
  - name: pricing_recalculation_frequency
    type: counter
    labels: [facility_id, trigger]
    
  - name: forecast_accuracy_mae
    type: gauge
    labels: [facility_id]
    description: "Mean absolute error of demand forecast"
```

### Alerts
```yaml
alerts:
  - name: SensorHealthDegraded
    condition: sensor_health_rate < 0.9
    for: 5m
    severity: warning
    
  - name: AvailabilityPropagationSlow
    condition: availability_propagation_delay_ms_p95 > 5000
    severity: critical
    
  - name: FacilityDataStale
    condition: time_since_last_sensor_event > 600  # 10 min
    severity: critical
    action: "Mark facility availability as 'unknown', notify operator"
    
  - name: OverbookingDetected
    condition: confirmed_reservations > available_spots * 1.1
    severity: critical
```

## 10. Considerations

### IoT Sensor Reliability
- **Ultrasonic**: 95% accuracy, affected by temperature extremes
- **Magnetic**: 98% accuracy, requires in-ground installation
- **Camera (ANPR)**: 99% accuracy in good lighting, expensive
- **Strategy**: Multi-sensor fusion where possible, confidence-weighted decisions

### Handling Sensor Failures Gracefully
```python
# When sensor is down, use:
# 1. Entry/exit gate counters (facility-level count, not spot-level)
# 2. Camera fallback (if available)
# 3. Last known state with "staleness" indicator
# 4. User-reported status ("I'm leaving spot A-042")
```

### Multi-Facility Search Optimization
- Pre-compute availability aggregates per geo-grid (H3 hexagons)
- Update aggregates on availability change events
- Search first checks geo-grid aggregate, then queries specific facilities
- Reduces DB load by 80% for broad area searches

### Payment & Auto-Charging
- On entry: Pre-authorize estimated amount
- On exit: Charge actual duration, release pre-auth excess
- Monthly pass: Validate via license plate at gate (no action needed)
- Overstay: Auto-extend reservation, charge at current rate

### Offline Handling
- If network fails at facility: Gate opens (revenue loss < customer frustration)
- Buffer sensor events locally at IoT gateway, batch-send when reconnected
- App shows cached last-known availability with "data may be stale" warning

## 11. Scale Considerations

```
Sensor event processing: 16K events/s
- 128 Kafka partitions, 32 Flink workers
- Process 500 events/s per worker
- Sub-second processing latency

Search at peak (morning commute):
- 10K searches/s
- Redis geo-queries: <5ms per query
- Elasticsearch fallback for complex filters: <50ms

WebSocket connections (floor maps):
- 100K concurrent connections
- 50 WebSocket servers (2000 connections each)
- Redis Pub/Sub for cross-server broadcast
```
