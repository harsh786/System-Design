# Uber/Lyft Ride-Sharing Platform - System Design

## 1. Functional Requirements

### Core Features
- **Ride Request**: Rider enters pickup/dropoff, sees fare estimate, requests ride
- **Driver Matching**: Match nearest/optimal available driver to rider request
- **Real-Time GPS Tracking**: Track driver location during ride (rider + driver see map)
- **ETA Calculation**: Estimated time of arrival for pickup and dropoff
- **Fare Estimation & Calculation**: Pre-ride estimate, post-ride actual (distance + time)
- **Surge Pricing**: Dynamic pricing based on supply-demand in area
- **Ride Types**: Pool, UberX, Comfort, Premium, XL
- **Driver Onboarding**: Registration, background check, vehicle verification
- **Trip History**: Past rides for riders and drivers
- **Ratings**: Bidirectional ratings (rider ↔ driver)
- **Payments**: Automated fare charging, driver payouts, tips

### User Flows
1. **Rider**: Open app → Enter destination → See fare/ETA → Request → Match → Track → Arrive → Rate → Pay
2. **Driver**: Go online → Receive request → Accept/Decline → Navigate to pickup → Start trip → Navigate to dropoff → Complete → Rate

## 2. Non-Functional Requirements

| Requirement | Target |
|---|---|
| Match Latency (P99) | < 5s |
| Location Update Frequency | Every 4 seconds |
| Location Pipeline Latency | < 2s end-to-end |
| ETA Accuracy | ± 2 minutes for trips < 30 min |
| Surge Price Update Frequency | Every 30 seconds |
| Availability | 99.99% |
| Active Drivers Tracked | 5M concurrent |
| Active Rides | 1M concurrent |
| Location Updates QPS | 1.25M (5M drivers / 4 sec) |
| Ride Requests per Second | 10K peak |

## 3. Capacity Estimation

### Storage
- **Driver Locations (Hot)**: 5M drivers × 200B = 1 GB (all in-memory)
- **Trip Data**: 20M trips/day × 5KB = 100 GB/day = 36 TB/year
- **Location History**: 5M drivers × 21,600 pings/day × 50B = 5.4 TB/day (retained 30 days)
- **User Profiles**: 100M riders + 5M drivers × 2KB = 210 GB
- **Payment Records**: 20M/day × 1KB = 20 GB/day

### Compute
- **Location Ingestion**: 1.25M updates/sec / 50K per instance = 25 instances
- **Matching Service**: 10K requests/sec, each scanning ~100 candidates = 20 instances
- **ETA Service**: 10K rides × 2 ETAs each = 20K QPS / 5K per instance = 4 instances
- **Geo-Index**: 5M drivers, spatial queries = 10 nodes (Redis/custom)

### Bandwidth
- **Location Inbound**: 1.25M × 200B = 250 MB/s
- **Map Tiles**: 10M users × 5KB/tile × 0.1 tiles/sec = 5 GB/s (CDN-served)
- **WebSocket Connections**: 6M concurrent (riders tracking + drivers)

## 4. Data Modeling

### Driver Location (Redis Geo + In-Memory)
```
# Redis Geo Set - indexed by H3 resolution 7 cell
Key: drivers:online:{city_id}
Type: GEO SET
Members: driver_id with lat/lng

# Driver details hash
Key: driver:{driver_id}
Type: Hash
Fields:
  lat → "37.7749"
  lng → "-122.4194"
  heading → "270"
  speed_mph → "25"
  status → "AVAILABLE"  # AVAILABLE, EN_ROUTE_PICKUP, ON_TRIP, OFFLINE
  ride_type_eligible → "UBERX,COMFORT,XL"
  vehicle_type → "SUV"
  current_ride_id → ""
  last_update → "1705300800"
  h3_cell → "872830828ffffff"
  rating → "4.92"
  acceptance_rate → "0.89"
```

### Trip Schema (PostgreSQL)
```sql
CREATE TABLE trips (
    trip_id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Participants
    rider_id            UUID NOT NULL,
    driver_id           UUID,  -- NULL until matched
    vehicle_id          UUID,
    
    -- Ride type
    ride_type           VARCHAR(20) NOT NULL, -- POOL, UBERX, COMFORT, PREMIUM, XL
    
    -- Status
    status              VARCHAR(20) NOT NULL DEFAULT 'REQUESTED',
    -- REQUESTED, MATCHING, DRIVER_ASSIGNED, EN_ROUTE_PICKUP, 
    -- ARRIVED_PICKUP, IN_PROGRESS, COMPLETED, CANCELLED
    
    -- Locations
    pickup_location     GEOGRAPHY(POINT, 4326) NOT NULL,
    pickup_address      TEXT,
    dropoff_location    GEOGRAPHY(POINT, 4326) NOT NULL,
    dropoff_address     TEXT,
    actual_pickup_location  GEOGRAPHY(POINT, 4326),
    actual_dropoff_location GEOGRAPHY(POINT, 4326),
    
    -- Route
    estimated_route     JSONB,  -- Polyline
    actual_route        JSONB,
    estimated_distance_m INTEGER,
    actual_distance_m   INTEGER,
    estimated_duration_s INTEGER,
    actual_duration_s   INTEGER,
    
    -- Pricing
    estimated_fare      DECIMAL(10,2),
    actual_fare         DECIMAL(10,2),
    surge_multiplier    DECIMAL(4,2) DEFAULT 1.00,
    base_fare           DECIMAL(10,2),
    distance_fare       DECIMAL(10,2),
    time_fare           DECIMAL(10,2),
    surge_amount        DECIMAL(10,2) DEFAULT 0,
    toll_amount         DECIMAL(10,2) DEFAULT 0,
    tip_amount          DECIMAL(10,2) DEFAULT 0,
    promo_discount      DECIMAL(10,2) DEFAULT 0,
    currency            VARCHAR(3) DEFAULT 'USD',
    
    -- Payment
    payment_method_id   UUID,
    payment_status      VARCHAR(20) DEFAULT 'PENDING',
    payment_reference   VARCHAR(100),
    
    -- Ratings
    rider_rating        SMALLINT CHECK(rider_rating BETWEEN 1 AND 5),
    driver_rating       SMALLINT CHECK(driver_rating BETWEEN 1 AND 5),
    
    -- Pool specific
    pool_id             UUID,  -- Groups pooled rides
    pool_position       INTEGER, -- Pickup order in pool
    
    -- Timestamps
    requested_at        TIMESTAMP NOT NULL DEFAULT NOW(),
    matched_at          TIMESTAMP,
    driver_arrived_at   TIMESTAMP,
    trip_started_at     TIMESTAMP,
    trip_completed_at   TIMESTAMP,
    cancelled_at        TIMESTAMP,
    
    -- Cancellation
    cancelled_by        VARCHAR(10), -- RIDER, DRIVER, SYSTEM
    cancellation_reason VARCHAR(50),
    cancellation_fee    DECIMAL(10,2) DEFAULT 0,
    
    created_at          TIMESTAMP DEFAULT NOW(),
    updated_at          TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_trips_rider ON trips(rider_id, created_at DESC);
CREATE INDEX idx_trips_driver ON trips(driver_id, created_at DESC);
CREATE INDEX idx_trips_status ON trips(status, created_at) WHERE status NOT IN ('COMPLETED', 'CANCELLED');
CREATE INDEX idx_trips_pickup_geo ON trips USING GIST(pickup_location);
CREATE INDEX idx_trips_pool ON trips(pool_id) WHERE pool_id IS NOT NULL;
```

### Driver Schema
```sql
CREATE TABLE drivers (
    driver_id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL UNIQUE,
    
    -- Personal
    first_name          VARCHAR(100) NOT NULL,
    last_name           VARCHAR(100) NOT NULL,
    phone               VARCHAR(20) NOT NULL,
    email               VARCHAR(255),
    profile_photo_url   TEXT,
    
    -- Vehicle
    vehicle_id          UUID REFERENCES vehicles(vehicle_id),
    
    -- Status
    status              VARCHAR(20) DEFAULT 'PENDING', -- PENDING, ACTIVE, SUSPENDED, DEACTIVATED
    online_status       VARCHAR(20) DEFAULT 'OFFLINE', -- ONLINE, OFFLINE
    
    -- Qualifications
    license_number      VARCHAR(50),
    license_expiry      DATE,
    background_check_status VARCHAR(20),
    eligible_ride_types VARCHAR(100)[], -- {'UBERX', 'COMFORT', 'XL'}
    
    -- Performance
    rating              DECIMAL(3,2) DEFAULT 5.00,
    total_trips         INTEGER DEFAULT 0,
    acceptance_rate     DECIMAL(4,3) DEFAULT 1.000,
    cancellation_rate   DECIMAL(4,3) DEFAULT 0.000,
    total_online_hours  DECIMAL(10,1) DEFAULT 0,
    
    -- Financial
    bank_account_id     VARCHAR(100),
    earnings_balance    DECIMAL(12,2) DEFAULT 0,
    
    -- Market
    city_id             UUID NOT NULL,
    
    created_at          TIMESTAMP DEFAULT NOW(),
    updated_at          TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_drivers_status ON drivers(status, city_id);
CREATE INDEX idx_drivers_user ON drivers(user_id);
CREATE INDEX idx_drivers_rating ON drivers(rating DESC, total_trips DESC);
```

### Surge Pricing Schema
```sql
CREATE TABLE surge_zones (
    zone_id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    city_id             UUID NOT NULL,
    h3_index            VARCHAR(20) NOT NULL, -- H3 hex cell identifier (resolution 7)
    
    -- Current surge state
    surge_multiplier    DECIMAL(4,2) DEFAULT 1.00,
    demand_count        INTEGER DEFAULT 0,  -- Ride requests in last 5 min
    supply_count        INTEGER DEFAULT 0,  -- Available drivers in zone
    
    -- Bounds
    min_multiplier      DECIMAL(4,2) DEFAULT 1.00,
    max_multiplier      DECIMAL(4,2) DEFAULT 5.00,
    
    updated_at          TIMESTAMP DEFAULT NOW(),
    
    UNIQUE(city_id, h3_index)
);

CREATE INDEX idx_surge_city ON surge_zones(city_id, surge_multiplier DESC);
CREATE INDEX idx_surge_h3 ON surge_zones(h3_index);
```

## 5. High-Level Design (HLD)

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                              CLIENT LAYER                                                │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────┐                                │
│  │  Rider App   │  │  Driver App  │  │  Admin Portal │                                │
│  │  (iOS/And)   │  │  (iOS/And)   │  │               │                                │
│  └──────┬───────┘  └──────┬───────┘  └───────┬───────┘                                │
│         │  WebSocket       │  WebSocket        │  REST                                  │
└─────────┼──────────────────┼──────────────────┼────────────────────────────────────────┘
          │                  │                  │
┌─────────▼──────────────────▼──────────────────▼────────────────────────────────────────┐
│                    API Gateway + WebSocket Gateway                                       │
│  ┌─────────────────────┐  ┌─────────────────────────────────────────────┐              │
│  │  REST API Gateway   │  │  WebSocket Gateway (Location + Tracking)    │              │
│  │  (Auth + Rate Limit)│  │  6M concurrent connections                  │              │
│  └──────────┬──────────┘  └──────────────────┬──────────────────────────┘              │
└─────────────┼────────────────────────────────┼─────────────────────────────────────────┘
              │                                │
┌─────────────▼────────────────────────────────▼─────────────────────────────────────────┐
│                              SERVICE LAYER                                               │
│                                                                                          │
│  ┌────────────────────┐  ┌────────────────────┐  ┌──────────────────────────────────┐  │
│  │  Ride Request Svc  │  │  Matching Service  │  │  Location Service               │  │
│  │                    │  │                    │  │                                  │  │
│  │  - Validate req    │  │  - Geo query nearby│  │  - Ingest driver pings          │  │
│  │  - Fare estimate   │  │  - Rank candidates │  │  - Update geo-index             │  │
│  │  - Create trip     │  │  - Dispatch to drv │  │  - Publish to riders            │  │
│  └────────┬───────────┘  └────────┬───────────┘  └──────────────┬───────────────────┘  │
│           │                       │                              │                       │
│  ┌────────▼───────────┐  ┌───────▼────────────┐  ┌─────────────▼────────────────────┐  │
│  │  Pricing / Surge   │  │  ETA Service       │  │  Trip Management Service        │  │
│  │  Service           │  │                    │  │                                  │  │
│  │  - Fare calc       │  │  - Route calc      │  │  - State machine                │  │
│  │  - Surge compute   │  │  - Traffic-aware   │  │  - Status updates               │  │
│  │  - Dynamic pricing │  │  - ML predictions  │  │  - Completion + settlement      │  │
│  └────────────────────┘  └────────────────────┘  └──────────────────────────────────┘  │
│                                                                                          │
│  ┌────────────────────┐  ┌────────────────────┐  ┌──────────────────────────────────┐  │
│  │  Payment Service   │  │  Rating Service    │  │  Notification Service           │  │
│  └────────────────────┘  └────────────────────┘  └──────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────────────────────┘
              │                                │
┌─────────────▼────────────────────────────────▼─────────────────────────────────────────┐
│                              DATA LAYER                                                  │
│                                                                                          │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐  ┌─────────────────────────┐  │
│  │ Redis Cluster │  │  PostgreSQL   │  │  Apache Kafka │  │  Apache Flink           │  │
│  │               │  │               │  │               │  │                         │  │
│  │ - Geo index   │  │ - Trips       │  │ - Location    │  │ - Surge computation     │  │
│  │ - Driver state│  │ - Users       │  │   stream      │  │ - Location aggregation  │  │
│  │ - Surge cache │  │ - Payments    │  │ - Trip events │  │ - ETA model features    │  │
│  │ - ETA cache   │  │ - History     │  │ - Surge input │  │                         │  │
│  └───────────────┘  └───────────────┘  └───────────────┘  └─────────────────────────┘  │
│                                                                                          │
│  ┌───────────────┐  ┌───────────────┐                                                   │
│  │  OSRM / Valhalla  │  S3 (Location  │                                                │
│  │  (Routing Engine)  │   History)     │                                                │
│  └───────────────┘  └───────────────┘                                                   │
└──────────────────────────────────────────────────────────────────────────────────────────┘
```

## 6. Low-Level Design (LLD) - APIs

### Request Ride
```
POST /api/v1/rides/request
Request:
{
    "rider_id": "usr_rider_001",
    "pickup": {
        "lat": 37.7749,
        "lng": -122.4194,
        "address": "123 Market St, San Francisco"
    },
    "dropoff": {
        "lat": 37.7849,
        "lng": -122.4094,
        "address": "456 Mission St, San Francisco"
    },
    "ride_type": "UBERX",
    "payment_method_id": "pm_card_001",
    "pool_preferences": null
}

Response (202 Accepted):
{
    "trip_id": "trip_uuid_001",
    "status": "MATCHING",
    "fare_estimate": {
        "min": 12.50,
        "max": 16.00,
        "currency": "USD",
        "surge_multiplier": 1.2,
        "breakdown": {
            "base": 2.50,
            "distance": 6.40,
            "time": 3.20,
            "surge": 2.42,
            "booking_fee": 1.75
        }
    },
    "eta": {
        "pickup_seconds": 180,
        "dropoff_seconds": 720,
        "pickup_display": "3 min",
        "dropoff_display": "12 min"
    },
    "tracking_channel": "ws://tracking.uber.com/trip/trip_uuid_001"
}
```

### Driver Location Update (WebSocket)
```
// Driver sends every 4 seconds via WebSocket
{
    "type": "LOCATION_UPDATE",
    "driver_id": "drv_001",
    "payload": {
        "lat": 37.77492,
        "lng": -122.41938,
        "heading": 270,
        "speed_mph": 22,
        "accuracy_m": 5,
        "timestamp": 1705300804,
        "battery_pct": 67
    }
}

// Server acknowledges
{
    "type": "LOCATION_ACK",
    "server_timestamp": 1705300804500
}
```

### Rider Tracking Update (WebSocket push to rider)
```
// Server pushes to rider during active trip
{
    "type": "DRIVER_LOCATION",
    "trip_id": "trip_uuid_001",
    "driver": {
        "lat": 37.77502,
        "lng": -122.41945,
        "heading": 270,
        "eta_seconds": 120,
        "distance_m": 800
    },
    "updated_at": 1705300808
}
```

### Fare Calculation
```
GET /api/v1/rides/estimate?pickup_lat=37.7749&pickup_lng=-122.4194&dropoff_lat=37.7849&dropoff_lng=-122.4094&ride_type=UBERX

Response:
{
    "estimates": [
        {
            "ride_type": "UBERX",
            "fare_range": {"min": 12.50, "max": 16.00},
            "surge": 1.2,
            "eta_minutes": 3,
            "capacity": 4
        },
        {
            "ride_type": "COMFORT",
            "fare_range": {"min": 18.00, "max": 23.00},
            "surge": 1.0,
            "eta_minutes": 5,
            "capacity": 4
        },
        {
            "ride_type": "XL",
            "fare_range": {"min": 22.00, "max": 28.00},
            "surge": 1.0,
            "eta_minutes": 7,
            "capacity": 6
        }
    ]
}
```

## 7. Deep Dives

### Deep Dive 1: Supply-Demand Matching (Geospatial Index + Dispatch Algorithm)

**Geospatial Indexing with S2/H3**:
```python
import h3
import redis
from typing import List, Tuple
from dataclasses import dataclass

@dataclass
class DriverCandidate:
    driver_id: str
    lat: float
    lng: float
    distance_m: float
    eta_seconds: int
    rating: float
    acceptance_rate: float
    eligible_types: List[str]
    current_status: str

class GeoMatchingService:
    """
    Uses H3 hexagonal grid (resolution 7, ~5km² cells) for spatial indexing.
    Drivers are indexed by their current H3 cell.
    For matching: search current cell + k-ring neighbors.
    """
    
    H3_RESOLUTION = 7  # ~5.16 km² per cell
    MAX_SEARCH_RINGS = 3  # Search up to 3 rings out (~15km radius)
    MAX_CANDIDATES = 20
    
    def __init__(self):
        self.redis = redis.RedisCluster(...)
        self.eta_service = ETAService()
    
    def find_nearby_drivers(self, lat: float, lng: float, 
                           ride_type: str, city_id: str) -> List[DriverCandidate]:
        """Find available drivers near pickup point using H3 spatial index."""
        
        pickup_h3 = h3.latlng_to_cell(lat, lng, self.H3_RESOLUTION)
        candidates = []
        
        # Expand search rings until we have enough candidates
        for ring in range(self.MAX_SEARCH_RINGS + 1):
            if ring == 0:
                cells = [pickup_h3]
            else:
                cells = h3.grid_ring(pickup_h3, ring)
            
            for cell in cells:
                # Get drivers in this H3 cell
                driver_ids = self.redis.smembers(f"geo:cell:{city_id}:{cell}")
                
                for driver_id in driver_ids:
                    driver_data = self.redis.hgetall(f"driver:{driver_id}")
                    
                    if not driver_data:
                        continue
                    if driver_data.get('status') != 'AVAILABLE':
                        continue
                    if ride_type not in driver_data.get('ride_type_eligible', '').split(','):
                        continue
                    
                    d_lat = float(driver_data['lat'])
                    d_lng = float(driver_data['lng'])
                    distance = self._haversine(lat, lng, d_lat, d_lng)
                    
                    candidates.append(DriverCandidate(
                        driver_id=driver_id,
                        lat=d_lat,
                        lng=d_lng,
                        distance_m=distance,
                        eta_seconds=0,  # Calculated later
                        rating=float(driver_data.get('rating', 4.5)),
                        acceptance_rate=float(driver_data.get('acceptance_rate', 0.8)),
                        eligible_types=driver_data.get('ride_type_eligible', '').split(','),
                        current_status=driver_data['status']
                    ))
            
            if len(candidates) >= self.MAX_CANDIDATES:
                break
        
        # Sort by distance, take top candidates
        candidates.sort(key=lambda c: c.distance_m)
        return candidates[:self.MAX_CANDIDATES]
    
    def update_driver_location(self, driver_id: str, lat: float, lng: float, 
                               city_id: str, metadata: dict):
        """Update driver's position in geo-index. Called every 4 seconds."""
        new_cell = h3.latlng_to_cell(lat, lng, self.H3_RESOLUTION)
        
        # Get previous cell
        old_cell = self.redis.hget(f"driver:{driver_id}", 'h3_cell')
        
        pipe = self.redis.pipeline()
        
        # Remove from old cell, add to new cell (if changed)
        if old_cell and old_cell != new_cell:
            pipe.srem(f"geo:cell:{city_id}:{old_cell}", driver_id)
        pipe.sadd(f"geo:cell:{city_id}:{new_cell}", driver_id)
        
        # Update driver hash
        pipe.hset(f"driver:{driver_id}", mapping={
            'lat': str(lat),
            'lng': str(lng),
            'h3_cell': new_cell,
            'heading': str(metadata.get('heading', 0)),
            'speed_mph': str(metadata.get('speed_mph', 0)),
            'last_update': str(int(time.time()))
        })
        
        pipe.execute()


class DispatchAlgorithm:
    """
    Batch matching: Instead of greedily assigning each request to nearest driver,
    batch requests over a short window (2s) and solve assignment optimally.
    
    Objective: Minimize total pickup time across all matches while considering:
    - Driver distance/ETA to pickup
    - Driver rating and acceptance rate
    - Ride type eligibility
    - Fairness (don't starve drivers at edges)
    """
    
    BATCH_WINDOW_MS = 2000  # Collect requests for 2 seconds
    
    def batch_match(self, requests: List[dict], 
                    candidates_per_request: dict) -> dict:
        """
        Solve the assignment problem using Hungarian algorithm variant.
        Returns: {trip_id: driver_id}
        """
        from scipy.optimize import linear_sum_assignment
        import numpy as np
        
        if len(requests) == 1:
            # Single request: use scoring-based approach
            return self._single_match(requests[0], candidates_per_request[requests[0]['trip_id']])
        
        # Build cost matrix
        all_drivers = set()
        for candidates in candidates_per_request.values():
            for c in candidates:
                all_drivers.add(c.driver_id)
        
        driver_list = list(all_drivers)
        n_requests = len(requests)
        n_drivers = len(driver_list)
        
        # Cost matrix: rows = requests, cols = drivers
        # High cost = bad match, infinity = impossible
        INF = 1e9
        cost_matrix = np.full((n_requests, n_drivers), INF)
        
        for i, req in enumerate(requests):
            candidates = candidates_per_request[req['trip_id']]
            candidate_map = {c.driver_id: c for c in candidates}
            
            for j, driver_id in enumerate(driver_list):
                if driver_id in candidate_map:
                    c = candidate_map[driver_id]
                    cost_matrix[i][j] = self._compute_match_cost(req, c)
        
        # Solve assignment
        row_ind, col_ind = linear_sum_assignment(cost_matrix)
        
        assignments = {}
        for i, j in zip(row_ind, col_ind):
            if cost_matrix[i][j] < INF:
                assignments[requests[i]['trip_id']] = driver_list[j]
        
        return assignments
    
    def _compute_match_cost(self, request: dict, candidate: DriverCandidate) -> float:
        """Compute cost of assigning this driver to this request."""
        # ETA weight (primary factor)
        eta_cost = candidate.eta_seconds / 60.0  # Normalize to minutes
        
        # Rating penalty (prefer higher-rated drivers)
        rating_penalty = (5.0 - candidate.rating) * 0.5
        
        # Acceptance rate (don't send to drivers who'll likely decline)
        decline_risk = (1.0 - candidate.acceptance_rate) * 3.0
        
        # Fairness: slight bonus for drivers who've been waiting longer
        # (implemented via driver.idle_time in production)
        
        return eta_cost + rating_penalty + decline_risk
    
    def _single_match(self, request: dict, candidates: List[DriverCandidate]) -> dict:
        """Score-based matching for single request (no batching needed)."""
        if not candidates:
            return {}
        
        scored = []
        for c in candidates:
            score = self._compute_match_cost(request, c)
            scored.append((score, c))
        
        scored.sort(key=lambda x: x[0])
        best = scored[0][1]
        
        return {request['trip_id']: best.driver_id}
```

### Deep Dive 2: Real-Time Location Pipeline

```
Driver App → WebSocket GW → Kafka (locations) → Flink (process) → 
    ├── Redis Geo Index (for matching)
    ├── Kafka (rider-tracking) → WebSocket GW → Rider App
    ├── S3 (location history, batch)
    └── Surge Engine Input
```

```python
class LocationIngestionPipeline:
    """
    Handles 1.25M location updates per second.
    Pipeline: WebSocket → Kafka → Flink → Multiple sinks
    """
    
    def __init__(self):
        self.kafka_producer = KafkaProducer({
            'bootstrap.servers': 'kafka:9092',
            'acks': '1',  # Don't need all replicas for location (acceptable loss)
            'linger.ms': 10,
            'batch.size': 131072,
            'compression.type': 'snappy',
            'buffer.memory': 268435456,  # 256MB
            'max.in.flight.requests.per.connection': 10
        })
    
    def on_location_received(self, driver_id: str, location: dict):
        """Process incoming location from WebSocket."""
        
        # Validate and enrich
        enriched = {
            'driver_id': driver_id,
            'lat': location['lat'],
            'lng': location['lng'],
            'heading': location.get('heading', 0),
            'speed_mph': location.get('speed_mph', 0),
            'timestamp': location['timestamp'],
            'h3_cell': h3.latlng_to_cell(location['lat'], location['lng'], 7),
            'server_received_at': int(time.time() * 1000)
        }
        
        # Publish to Kafka (partitioned by driver_id for ordering)
        self.kafka_producer.produce(
            topic='driver.locations',
            key=driver_id.encode(),
            value=json.dumps(enriched).encode()
        )
    
    def on_active_trip_location(self, driver_id: str, trip_id: str, location: dict):
        """For drivers on active trips, also publish to rider tracking channel."""
        # This goes to a separate topic consumed by the tracking service
        self.kafka_producer.produce(
            topic='trip.tracking',
            key=trip_id.encode(),
            value=json.dumps({
                'trip_id': trip_id,
                'driver_id': driver_id,
                **location,
                'timestamp': int(time.time() * 1000)
            }).encode()
        )


class FlinkLocationProcessor:
    """Flink job that processes driver locations and updates geo-index."""
    
    def build_pipeline(self, env):
        locations = env.from_source(
            KafkaSource.builder()
            .set_topics("driver.locations")
            .set_group_id("location-processor")
            .build()
        )
        
        # 1. Update geo-index in Redis
        locations.add_sink(RedisGeoSink())
        
        # 2. Compute speed/direction anomalies (fraud detection)
        locations.key_by(lambda l: l['driver_id']) \
            .process(AnomalyDetector()) \
            .filter(lambda a: a['is_anomaly']) \
            .add_sink(KafkaSink("driver.anomalies"))
        
        # 3. Aggregate for surge (count drivers per H3 cell per 30s window)
        locations.key_by(lambda l: l['h3_cell']) \
            .window(TumblingProcessingTimeWindows.of(Time.seconds(30))) \
            .process(SupplyCounter()) \
            .add_sink(KafkaSink("surge.supply"))
        
        # 4. Batch to S3 for historical analysis (5-min micro-batches)
        locations.window_all(TumblingProcessingTimeWindows.of(Time.minutes(5))) \
            .process(S3BatchWriter())
```

### Deep Dive 3: Surge Pricing Engine

```python
import h3
import numpy as np
from collections import defaultdict

class SurgePricingEngine:
    """
    Computes surge multiplier per H3 cell based on supply/demand ratio.
    
    Key principles:
    1. Demand = ride requests per cell per time window
    2. Supply = available drivers per cell per time window
    3. Surge = f(demand/supply) with smoothing and caps
    4. Price elasticity: Higher surge → fewer requests (negative feedback)
    """
    
    # Surge parameters
    SURGE_WINDOW_SEC = 300  # 5-minute rolling window
    UPDATE_INTERVAL_SEC = 30
    MIN_DEMAND_FOR_SURGE = 3  # Don't surge for < 3 requests
    SMOOTHING_FACTOR = 0.7  # Exponential smoothing (0 = instant, 1 = never change)
    
    # Surge curve: maps demand/supply ratio to multiplier
    SURGE_CURVE = [
        (0.0, 1.0),   # ratio 0-0.5: no surge
        (0.5, 1.0),
        (1.0, 1.0),   # ratio 1.0: balanced, no surge
        (1.5, 1.2),   # 50% more demand than supply
        (2.0, 1.5),
        (3.0, 2.0),
        (4.0, 2.5),
        (5.0, 3.0),
        (8.0, 4.0),
        (10.0, 5.0),  # 10x demand → 5x price (capped)
    ]
    
    def __init__(self):
        self.redis = redis.RedisCluster(...)
        self.current_surge = {}  # h3_cell → current multiplier
    
    def compute_surge(self, city_id: str) -> dict:
        """Compute surge for all cells in a city. Called every 30 seconds."""
        
        # Get all demand counts (from Flink aggregation)
        demand_by_cell = self._get_demand_counts(city_id)
        
        # Get all supply counts (from Flink aggregation)
        supply_by_cell = self._get_supply_counts(city_id)
        
        all_cells = set(demand_by_cell.keys()) | set(supply_by_cell.keys())
        updated_surge = {}
        
        for cell in all_cells:
            demand = demand_by_cell.get(cell, 0)
            supply = supply_by_cell.get(cell, 0)
            
            # Calculate raw surge
            if supply == 0:
                if demand >= self.MIN_DEMAND_FOR_SURGE:
                    raw_multiplier = 5.0  # Max surge when no supply
                else:
                    raw_multiplier = 1.0
            elif demand < self.MIN_DEMAND_FOR_SURGE:
                raw_multiplier = 1.0
            else:
                ratio = demand / supply
                raw_multiplier = self._interpolate_surge(ratio)
            
            # Apply exponential smoothing
            prev_multiplier = self.current_surge.get(cell, 1.0)
            smoothed = (self.SMOOTHING_FACTOR * prev_multiplier + 
                       (1 - self.SMOOTHING_FACTOR) * raw_multiplier)
            
            # Round to nearest 0.1
            final_multiplier = round(max(1.0, min(5.0, smoothed)), 1)
            
            updated_surge[cell] = final_multiplier
            
            # Persist to Redis
            self.redis.hset(f"surge:{city_id}", cell, str(final_multiplier))
        
        self.current_surge = updated_surge
        return updated_surge
    
    def _interpolate_surge(self, ratio: float) -> float:
        """Interpolate surge multiplier from curve."""
        for i in range(len(self.SURGE_CURVE) - 1):
            r1, m1 = self.SURGE_CURVE[i]
            r2, m2 = self.SURGE_CURVE[i + 1]
            if r1 <= ratio <= r2:
                t = (ratio - r1) / (r2 - r1)
                return m1 + t * (m2 - m1)
        return self.SURGE_CURVE[-1][1]  # Max
    
    def get_surge_for_location(self, lat: float, lng: float, 
                                city_id: str) -> float:
        """Get current surge multiplier for a location."""
        cell = h3.latlng_to_cell(lat, lng, 7)
        surge = self.redis.hget(f"surge:{city_id}", cell)
        return float(surge) if surge else 1.0
    
    def _get_demand_counts(self, city_id: str) -> dict:
        """Get ride request counts per H3 cell from Flink output."""
        return {k.decode(): int(v) for k, v in 
                self.redis.hgetall(f"demand:{city_id}").items()}
    
    def _get_supply_counts(self, city_id: str) -> dict:
        """Get available driver counts per H3 cell from Flink output."""
        return {k.decode(): int(v) for k, v in 
                self.redis.hgetall(f"supply:{city_id}").items()}
```

**Kafka Configuration for Location Pipeline**:
```yaml
topics:
  driver.locations:
    partitions: 256        # High parallelism for 1.25M msg/sec
    replication_factor: 2  # 2 is enough for location (ephemeral)
    retention_ms: 3600000  # 1 hour only
    compression_type: snappy
    max_message_bytes: 1024
    min_insync_replicas: 1
    
  trip.tracking:
    partitions: 64
    replication_factor: 2
    retention_ms: 3600000
    
  surge.supply:
    partitions: 32
    replication_factor: 3
    retention_ms: 86400000
    
  surge.demand:
    partitions: 32
    replication_factor: 3
    retention_ms: 86400000
```

## 8. Component Optimization

### WebSocket Gateway Scaling
```yaml
# Each gateway node handles ~100K concurrent connections
gateway:
  instances: 60  # 6M connections / 100K per node
  memory_per_instance: 16GB
  protocol: WebSocket with binary framing (protobuf)
  heartbeat_interval: 30s
  connection_timeout: 120s
  
  # Connection routing: sticky sessions via consistent hashing on user_id
  load_balancer: 
    algorithm: consistent_hash
    key: user_id
```

### Matching Service Performance
```python
# Pre-filter drivers in Redis, compute scoring in service
# Target: < 100ms for full match cycle

class MatchingOptimizations:
    # 1. Pre-computed ETA matrix (updated every 30s by background job)
    # Instead of calling routing API for each candidate, use pre-computed grid
    
    def get_precomputed_eta(self, from_cell: str, to_cell: str) -> int:
        """~1ms lookup vs ~50ms routing API call."""
        return int(self.redis.hget(f"eta_matrix:{from_cell}", to_cell) or 300)
    
    # 2. Driver ranking cached per cell (refreshed every 5s)
    # Avoid re-scoring all drivers on every request
    
    # 3. Circuit breaker on routing API - fall back to haversine estimate
```

## 9. Observability

### Key Metrics
```yaml
metrics:
  - name: ride_request_to_match_seconds
    type: histogram
    buckets: [1, 2, 3, 5, 8, 10, 15, 30]
    labels: [city, ride_type]
  
  - name: driver_location_lag_ms
    type: histogram
    buckets: [100, 500, 1000, 2000, 5000]
  
  - name: active_drivers_gauge
    type: gauge
    labels: [city, status]
  
  - name: active_trips_gauge
    type: gauge
    labels: [city, ride_type, status]
  
  - name: surge_multiplier_gauge
    type: gauge
    labels: [city, h3_cell]
  
  - name: match_success_rate
    type: gauge
    labels: [city, ride_type]
  
  - name: driver_acceptance_rate
    type: gauge
    labels: [city]
  
  - name: eta_accuracy_error_seconds
    type: histogram
    labels: [city, ride_type]
    buckets: [30, 60, 120, 180, 300, 600]
  
  - name: websocket_connections_gauge
    type: gauge
    labels: [gateway_node, connection_type]
  
  - name: fare_calculation_total
    type: counter
    labels: [city, ride_type, surge_bucket]
```

### Alerting
```yaml
alerts:
  - name: MatchTimeHigh
    expr: histogram_quantile(0.99, ride_request_to_match_seconds) > 10
    for: 3m
    severity: critical
    
  - name: LocationPipelineLag
    expr: avg(driver_location_lag_ms) > 3000
    for: 2m
    severity: critical
    
  - name: LowDriverSupply
    expr: active_drivers_gauge{status="AVAILABLE"} / active_trips_gauge < 0.3
    for: 10m
    severity: warning
    
  - name: HighSurge
    expr: avg(surge_multiplier_gauge{city="SF"}) > 3.0
    for: 15m
    severity: info
```

## 10. Failure Scenarios & Considerations

### Location Service Failure
- **Impact**: Can't update driver positions, matching uses stale data
- **Mitigation**: Driver app caches last known position, matching falls back to last-known
- **Recovery**: On reconnection, driver sends full state sync

### Matching Service Partition
- **Impact**: Riders can't get matched in affected region
- **Mitigation**: Regional failover, match in nearest healthy region
- **User Impact**: Longer wait times, system shows "high demand" messaging

### Surge Calculation Stale
- **Impact**: Under-priced (lost revenue) or over-priced (lost riders)
- **Mitigation**: Fail to surge=1.0 if calculation is >2min stale
- **Bound**: Max surge capped at 5x regardless

### Payment Failure After Trip
- **Handling**: Trip still completes, charge retried 3x, then flagged
- **Driver Impact**: Driver always gets paid (Uber absorbs risk)

## 11. Technology Choices

| Component | Technology | Rationale |
|---|---|---|
| Geo Index | Redis + H3 | Sub-ms spatial queries at scale |
| Driver State | Redis Cluster | In-memory, real-time state |
| Trip Database | PostgreSQL + PostGIS | Spatial queries + ACID |
| Event Streaming | Apache Kafka | 1M+ msg/sec, durable |
| Stream Processing | Apache Flink | Stateful stream for surge/aggregation |
| Routing Engine | OSRM/Valhalla | Self-hosted for low-latency ETA |
| WebSocket | Custom Go service | 100K connections per node |
| ML Models | TensorFlow Serving | ETA prediction, demand forecasting |
| Monitoring | Prometheus + Grafana | Real-time operational metrics |
| Map Tiles | Mapbox/HERE | CDN-served vector tiles |
