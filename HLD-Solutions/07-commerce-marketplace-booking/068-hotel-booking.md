# Design Hotel Booking System (Booking.com)

## 1. Functional Requirements

### Core Features
- **Hotel/Room Inventory**: Hotels with multiple room types, photos, descriptions, star ratings
- **Search**: Date range + location + room type + guests with instant results
- **Rate Plans**: Flexible/non-refundable/advance purchase rates per room type
- **Allotment Management**: Room inventory allocation, stop-sell, overbooking strategy
- **Booking Modifications/Cancellations**: Date changes, room upgrades, penalty calculation
- **Loyalty Programs**: Points earning/redemption, tier benefits, member-only rates
- **Last-Minute Deals**: Flash sales, secret deals, mobile-only pricing

### User Flows
1. Guest searches → views hotel → selects room + rate → books → pays → stays → reviews
2. Hotel manager updates inventory → sets rates → manages allotments → processes bookings
3. System detects low occupancy → triggers dynamic pricing → generates deal

## 2. Non-Functional Requirements

| Requirement | Target |
|---|---|
| Search Latency | P99 < 800ms (complex multi-hotel) |
| Booking Consistency | Strong (no overselling beyond threshold) |
| Availability | 99.99% for booking engine |
| Rate Updates | Propagation < 5s globally |
| Scale | 28M+ reported listings, 1.5M room-nights/day |
| Concurrency | 100K+ concurrent searches |
| Data Freshness | Inventory accurate within 30s |
| Internationalization | 40+ languages, 70+ currencies |
| Partner API | <200ms response for availability queries |

## 3. Capacity Estimation

### Storage
```
Hotels: 2M × 10KB = 20GB
Room Types: 2M hotels × 5 types × 2KB = 20GB
Rate Plans: 10M room-types × 4 plans × 365 days × 100B = 1.5TB
Bookings: 500M/year × 1.5KB = 750GB
Reviews: 200M × 500B = 100GB
Photos: 2M hotels × 50 photos × 3MB = 300TB
Availability: 10M rooms × 365 days × 50B = 183GB
```

### Throughput
```
Search requests: 100K/s peak
Availability checks: 500K/s (including API partners)
Booking writes: 20K/min
Rate updates: 50K/min from channel managers
Review submissions: 5K/min
```

## 4. Data Modeling

### Full Database Schemas

```sql
-- Hotels
CREATE TABLE hotels (
    hotel_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(300) NOT NULL,
    chain_id UUID REFERENCES hotel_chains(chain_id),
    star_rating DECIMAL(2,1) CHECK (star_rating BETWEEN 1 AND 5),
    property_type VARCHAR(50), -- hotel, resort, hostel, apartment, b&b
    description TEXT,
    latitude DECIMAL(10, 7) NOT NULL,
    longitude DECIMAL(10, 7) NOT NULL,
    address_line1 VARCHAR(255),
    city VARCHAR(100) NOT NULL,
    country_code CHAR(2) NOT NULL,
    postal_code VARCHAR(20),
    timezone VARCHAR(50) NOT NULL,
    check_in_time TIME DEFAULT '15:00',
    check_out_time TIME DEFAULT '11:00',
    total_rooms INT NOT NULL,
    year_built INT,
    last_renovated INT,
    commission_percent DECIMAL(4,2) DEFAULT 15.0,
    avg_review_score DECIMAL(3,1),
    review_count INT DEFAULT 0,
    status VARCHAR(20) DEFAULT 'active',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_hotels_location ON hotels USING GIST(ST_MakePoint(longitude, latitude)::geography);
CREATE INDEX idx_hotels_city ON hotels(city, status) WHERE status = 'active';
CREATE INDEX idx_hotels_chain ON hotels(chain_id);

-- Hotel amenities
CREATE TABLE hotel_amenities (
    hotel_id UUID REFERENCES hotels(hotel_id),
    amenity_code VARCHAR(50),
    PRIMARY KEY (hotel_id, amenity_code)
);

-- Room types
CREATE TABLE room_types (
    room_type_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    hotel_id UUID NOT NULL REFERENCES hotels(hotel_id),
    name VARCHAR(200) NOT NULL,
    description TEXT,
    max_occupancy INT NOT NULL,
    max_adults INT NOT NULL,
    max_children INT DEFAULT 0,
    bed_configuration JSONB, -- [{"type": "king", "count": 1}]
    room_size_sqm DECIMAL(6,1),
    floor_level VARCHAR(20),
    view_type VARCHAR(50),
    amenities VARCHAR(50)[],
    photo_urls TEXT[],
    total_inventory INT NOT NULL, -- physical rooms of this type
    sort_order INT DEFAULT 0,
    status VARCHAR(20) DEFAULT 'active',
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_room_types_hotel ON room_types(hotel_id) WHERE status = 'active';

-- Rate plans
CREATE TABLE rate_plans (
    rate_plan_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    room_type_id UUID NOT NULL REFERENCES room_types(room_type_id),
    hotel_id UUID NOT NULL REFERENCES hotels(hotel_id),
    name VARCHAR(200) NOT NULL,
    rate_type VARCHAR(30) NOT NULL, -- standard, non_refundable, advance_purchase, member_only
    cancellation_policy_id UUID REFERENCES cancellation_policies(policy_id),
    meal_plan VARCHAR(30) DEFAULT 'room_only', -- room_only, breakfast, half_board, full_board
    is_derived BOOLEAN DEFAULT FALSE,
    parent_rate_plan_id UUID REFERENCES rate_plans(rate_plan_id),
    derivation_rule JSONB, -- {"type": "percentage", "value": -10}
    min_stay_nights INT DEFAULT 1,
    max_stay_nights INT DEFAULT 30,
    min_advance_days INT DEFAULT 0, -- book at least X days in advance
    max_advance_days INT DEFAULT 365,
    valid_days_of_week INT DEFAULT 127, -- bitmask Mon-Sun
    member_only BOOLEAN DEFAULT FALSE,
    mobile_only BOOLEAN DEFAULT FALSE,
    commission_override DECIMAL(4,2),
    status VARCHAR(20) DEFAULT 'active',
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_rate_plans_room ON rate_plans(room_type_id, status);

-- Cancellation policies
CREATE TABLE cancellation_policies (
    policy_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100),
    policy_type VARCHAR(30), -- free, moderate, strict, non_refundable
    free_cancellation_hours INT, -- hours before check-in
    penalty_first_night BOOLEAN DEFAULT FALSE,
    penalty_percent DECIMAL(5,2), -- % of total
    no_show_penalty_percent DECIMAL(5,2) DEFAULT 100
);

-- Daily rates (the core pricing table)
CREATE TABLE daily_rates (
    room_type_id UUID NOT NULL,
    rate_plan_id UUID NOT NULL,
    date DATE NOT NULL,
    rate_cents INT NOT NULL,
    currency CHAR(3) DEFAULT 'EUR',
    single_supplement_cents INT DEFAULT 0,
    extra_adult_cents INT DEFAULT 0,
    extra_child_cents INT DEFAULT 0,
    closed BOOLEAN DEFAULT FALSE, -- stop sell for this rate
    min_stay_override INT,
    updated_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (room_type_id, rate_plan_id, date)
);
CREATE INDEX idx_daily_rates_date_range ON daily_rates(room_type_id, rate_plan_id, date) 
    WHERE closed = FALSE;

-- Room inventory / allotment
CREATE TABLE room_inventory (
    room_type_id UUID NOT NULL,
    date DATE NOT NULL,
    total_rooms INT NOT NULL,
    sold_rooms INT DEFAULT 0,
    blocked_rooms INT DEFAULT 0,
    overbooking_allowance INT DEFAULT 0, -- extra rooms allowed beyond physical
    stop_sell BOOLEAN DEFAULT FALSE,
    min_availability_alert INT DEFAULT 2,
    updated_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (room_type_id, date)
);
CREATE INDEX idx_inventory_available ON room_inventory(room_type_id, date) 
    WHERE stop_sell = FALSE;

-- Bookings
CREATE TABLE bookings (
    booking_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    confirmation_number VARCHAR(20) UNIQUE NOT NULL,
    hotel_id UUID NOT NULL REFERENCES hotels(hotel_id),
    room_type_id UUID NOT NULL REFERENCES room_types(room_type_id),
    rate_plan_id UUID NOT NULL REFERENCES rate_plans(rate_plan_id),
    guest_id UUID NOT NULL REFERENCES guests(guest_id),
    check_in DATE NOT NULL,
    check_out DATE NOT NULL,
    num_nights INT GENERATED ALWAYS AS (check_out - check_in) STORED,
    num_rooms INT DEFAULT 1,
    num_adults INT NOT NULL,
    num_children INT DEFAULT 0,
    guest_name VARCHAR(200) NOT NULL,
    guest_email VARCHAR(255),
    guest_phone VARCHAR(30),
    special_requests TEXT,
    total_rate_cents INT NOT NULL,
    taxes_cents INT NOT NULL,
    fees_cents INT DEFAULT 0,
    total_cents INT NOT NULL,
    currency CHAR(3) DEFAULT 'EUR',
    payment_status VARCHAR(30) DEFAULT 'pending',
    payment_method VARCHAR(30),
    payment_card_last4 VARCHAR(4),
    status VARCHAR(30) NOT NULL DEFAULT 'confirmed',
    -- confirmed, modified, cancelled, no_show, completed, disputed
    cancellation_deadline TIMESTAMP,
    cancelled_at TIMESTAMP,
    cancellation_penalty_cents INT,
    loyalty_points_earned INT DEFAULT 0,
    loyalty_points_redeemed INT DEFAULT 0,
    source VARCHAR(30) DEFAULT 'direct', -- direct, partner_api, mobile, call_center
    affiliate_id VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_bookings_hotel_dates ON bookings(hotel_id, check_in, check_out) WHERE status = 'confirmed';
CREATE INDEX idx_bookings_guest ON bookings(guest_id, created_at DESC);
CREATE INDEX idx_bookings_confirmation ON bookings(confirmation_number);

-- Booking modifications log
CREATE TABLE booking_modifications (
    modification_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    booking_id UUID NOT NULL REFERENCES bookings(booking_id),
    modification_type VARCHAR(30), -- date_change, room_upgrade, add_guest, cancel
    old_values JSONB,
    new_values JSONB,
    price_difference_cents INT DEFAULT 0,
    modified_by VARCHAR(30), -- guest, hotel, system
    reason TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Loyalty program
CREATE TABLE loyalty_members (
    member_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    guest_id UUID NOT NULL REFERENCES guests(guest_id),
    program_id UUID NOT NULL,
    tier VARCHAR(30) DEFAULT 'bronze', -- bronze, silver, gold, platinum, diamond
    points_balance INT DEFAULT 0,
    lifetime_points INT DEFAULT 0,
    nights_this_year INT DEFAULT 0,
    tier_expiry_date DATE,
    enrolled_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE loyalty_transactions (
    transaction_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    member_id UUID NOT NULL REFERENCES loyalty_members(member_id),
    booking_id UUID REFERENCES bookings(booking_id),
    type VARCHAR(20), -- earn, redeem, bonus, expire, adjust
    points INT NOT NULL,
    description VARCHAR(200),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Reviews
CREATE TABLE hotel_reviews (
    review_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    booking_id UUID NOT NULL REFERENCES bookings(booking_id),
    hotel_id UUID NOT NULL REFERENCES hotels(hotel_id),
    guest_id UUID NOT NULL REFERENCES guests(guest_id),
    overall_score DECIMAL(2,1) CHECK (overall_score BETWEEN 1 AND 10),
    staff_score DECIMAL(2,1),
    facilities_score DECIMAL(2,1),
    cleanliness_score DECIMAL(2,1),
    comfort_score DECIMAL(2,1),
    value_score DECIMAL(2,1),
    location_score DECIMAL(2,1),
    wifi_score DECIMAL(2,1),
    title VARCHAR(200),
    positive_comment TEXT,
    negative_comment TEXT,
    travel_type VARCHAR(30), -- solo, couple, family, business, group
    room_type_stayed VARCHAR(100),
    hotel_response TEXT,
    is_verified BOOLEAN DEFAULT TRUE,
    language VARCHAR(5) DEFAULT 'en',
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_reviews_hotel ON hotel_reviews(hotel_id, created_at DESC);
```

## 5. High-Level Design (HLD)

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                           CLIENT APPLICATIONS                                     │
│  ┌────────┐  ┌────────┐  ┌────────────┐  ┌──────────────┐  ┌──────────┐       │
│  │Web App │  │Mobile  │  │Partner API │  │Channel Mgr   │  │Extranet  │       │
│  │(Guest) │  │  Apps  │  │(Affiliates)│  │(Hotel Rates) │  │(Hotelier)│       │
│  └───┬────┘  └───┬────┘  └─────┬──────┘  └──────┬───────┘  └────┬─────┘       │
└──────┼───────────┼──────────────┼────────────────┼────────────────┼─────────────┘
       │           │              │                │                │
       ▼           ▼              ▼                ▼                ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│                       API GATEWAY LAYER                                            │
│  ┌──────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌──────────────┐  │
│  │  Kong /  │  │   Auth    │  │Rate Limit │  │  Geo-     │  │  Request     │  │
│  │  Envoy   │  │  Service  │  │ (per-key) │  │  Routing  │  │  Validator   │  │
│  └──────────┘  └───────────┘  └───────────┘  └───────────┘  └──────────────┘  │
└───────────────────────────────────────┬──────────────────────────────────────────┘
                                        │
         ┌──────────────┬───────────────┼───────────────┬──────────────┐
         ▼              ▼               ▼               ▼              ▼
┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌───────────┐ ┌───────────┐
│   Search    │ │  Inventory  │ │   Booking   │ │   Rate    │ │  Review   │
│   Service   │ │   Service   │ │   Service   │ │  Service  │ │  Service  │
│             │ │             │ │             │ │           │ │           │
│- Hotel srch │ │- Allotment  │ │- Reserve    │ │- Rate mgmt│ │- Submit   │
│- Avail chk  │ │- Stop-sell  │ │- Confirm    │ │- Derived  │ │- Moderate │
│- Geo filter │ │- Overbook   │ │- Modify     │ │- Promo    │ │- Aggregate│
│- Ranking    │ │- Reconcile  │ │- Cancel     │ │- Parity   │ │           │
└──────┬──────┘ └──────┬──────┘ └──────┬──────┘ └─────┬─────┘ └───────────┘
       │               │               │               │
       ▼               ▼               ▼               ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│                          DATA LAYER                                                │
│                                                                                    │
│ ┌────────────┐  ┌────────────┐  ┌─────────────┐  ┌──────────────┐              │
│ │Elasticsearch│  │ PostgreSQL │  │   Redis     │  │    Kafka     │              │
│ │            │  │  (Sharded) │  │  Cluster    │  │              │              │
│ │- Hotels    │  │            │  │             │  │- inventory   │              │
│ │- GeoIndex  │  │- Bookings  │  │- Inventory  │  │  .updates    │              │
│ │- Facets    │  │- Rates     │  │  counters   │  │- rate.changes│              │
│ │            │  │- Inventory │  │- Rate cache │  │- booking.evts│              │
│ │            │  │- Reviews   │  │- Sessions   │  │- search.logs │              │
│ └────────────┘  └────────────┘  │- Search cache│  └──────────────┘              │
│                                  └─────────────┘                                  │
│ ┌────────────┐  ┌────────────┐  ┌─────────────┐                                 │
│ │    S3      │  │  ClickHouse│  │ Apache Flink│                                 │
│ │  (Photos)  │  │ (Analytics)│  │ (Stream)    │                                 │
│ └────────────┘  └────────────┘  └─────────────┘                                 │
└──────────────────────────────────────────────────────────────────────────────────┘
```

## 6. Low-Level Design (LLD) - APIs

### Search API
```
POST /api/v2/hotels/search
Request:
{
    "destination": {"city": "Paris", "country": "FR"},
    "check_in": "2024-07-10",
    "check_out": "2024-07-14",
    "rooms": [
        {"adults": 2, "children": [8, 12]},
        {"adults": 2, "children": []}
    ],
    "filters": {
        "star_rating": [4, 5],
        "price_max_per_night": 300,
        "amenities": ["pool", "spa", "parking"],
        "property_type": ["hotel", "resort"],
        "review_score_min": 8.0,
        "free_cancellation": true
    },
    "sort": "price_and_availability",
    "currency": "USD",
    "language": "en",
    "page": 1,
    "page_size": 25
}

Response:
{
    "hotels": [
        {
            "hotel_id": "htl_abc123",
            "name": "Grand Hotel Paris Opera",
            "star_rating": 4.5,
            "review_score": 8.7,
            "review_count": 2341,
            "location": {"lat": 48.8698, "lng": 2.3322, "district": "9th Arr."},
            "distance_to_center_km": 1.2,
            "photos": [{"url": "...", "caption": "Lobby"}],
            "cheapest_room": {
                "room_type": "Superior Double",
                "rate_plan": "Non-refundable",
                "nightly_rate": 189,
                "total_for_stay": 756,
                "currency": "USD",
                "meal_plan": "breakfast",
                "availability": "last_3_rooms"
            },
            "all_rates_from": 189,
            "badges": ["genius_discount", "free_cancellation_available"],
            "sustainability_level": 2
        }
    ],
    "total_results": 847,
    "filters_available": {
        "star_rating": {"3": 245, "4": 412, "5": 190},
        "amenities": {"pool": 156, "spa": 89, "parking": 320}
    }
}
```

### Availability & Pricing API (Partner)
```
GET /api/v2/hotels/{hotel_id}/availability
    ?check_in=2024-07-10
    &check_out=2024-07-14
    &adults=2&children=1&child_ages=8

Response:
{
    "hotel_id": "htl_abc123",
    "rooms": [
        {
            "room_type_id": "rt_001",
            "name": "Superior Double",
            "max_occupancy": 3,
            "available_rooms": 5,
            "rates": [
                {
                    "rate_plan_id": "rp_standard",
                    "name": "Flexible Rate",
                    "rate_type": "standard",
                    "meal_plan": "breakfast",
                    "cancellation": {
                        "free_until": "2024-07-08T23:59:00+02:00",
                        "penalty_after": "first_night"
                    },
                    "nightly_rates": [
                        {"date": "2024-07-10", "rate": 220, "currency": "EUR"},
                        {"date": "2024-07-11", "rate": 220, "currency": "EUR"},
                        {"date": "2024-07-12", "rate": 250, "currency": "EUR"},
                        {"date": "2024-07-13", "rate": 250, "currency": "EUR"}
                    ],
                    "total": 940,
                    "taxes": 94,
                    "grand_total": 1034
                },
                {
                    "rate_plan_id": "rp_nonref",
                    "name": "Non-Refundable",
                    "rate_type": "non_refundable",
                    "meal_plan": "room_only",
                    "discount_percent": 15,
                    "total": 799,
                    "taxes": 80,
                    "grand_total": 879
                }
            ]
        }
    ]
}
```

### Booking API
```
POST /api/v2/bookings
Request:
{
    "hotel_id": "htl_abc123",
    "room_type_id": "rt_001",
    "rate_plan_id": "rp_standard",
    "check_in": "2024-07-10",
    "check_out": "2024-07-14",
    "num_rooms": 1,
    "guests": [
        {"first_name": "John", "last_name": "Smith", "email": "john@example.com"}
    ],
    "special_requests": "High floor preferred, extra pillows",
    "payment": {
        "method": "card",
        "card_token": "tok_stripe_xyz"
    },
    "loyalty_member_id": "LM_123456"
}

Response:
{
    "booking_id": "bk_xyz789",
    "confirmation_number": "BKG-7891234",
    "status": "confirmed",
    "hotel": {"name": "Grand Hotel Paris Opera", "address": "..."},
    "room": "Superior Double",
    "dates": {"check_in": "2024-07-10", "check_out": "2024-07-14", "nights": 4},
    "pricing": {
        "room_total": 940,
        "taxes": 94,
        "grand_total": 1034,
        "currency": "EUR"
    },
    "cancellation": {
        "free_until": "2024-07-08T23:59:00+02:00",
        "policy": "Free cancellation until July 8. After that, first night charged."
    },
    "loyalty_points_earned": 2068,
    "check_in_instructions": "Check-in from 15:00. Present ID at reception."
}
```

### Rate Update API (Hotel Extranet)
```
PUT /api/v2/extranet/rates/bulk
Request:
{
    "hotel_id": "htl_abc123",
    "updates": [
        {
            "room_type_id": "rt_001",
            "rate_plan_id": "rp_standard",
            "dates": {"from": "2024-07-01", "to": "2024-07-31"},
            "rate_cents": 22000,
            "currency": "EUR",
            "closed": false,
            "min_stay": 2
        },
        {
            "room_type_id": "rt_001",
            "rate_plan_id": "rp_standard",
            "dates": {"from": "2024-07-12", "to": "2024-07-14"},
            "rate_cents": 25000,
            "currency": "EUR",
            "closed": false,
            "min_stay": 1
        }
    ]
}
```

## 7. Deep Dives

### Deep Dive 1: Rate Management (Multiple Rate Plans + Derived Rates)

**Problem**: A single room type can have 5-10 rate plans, some derived from a master rate. When the master rate changes, all derived rates must update atomically and propagate to search results within 5 seconds.

```python
class RateManagementEngine:
    """
    Handles complex rate hierarchies:
    - Master Rate (set by hotel)
      ├── Non-Refundable (-15%)
      ├── Advance Purchase (-10%, min 14 days ahead)
      ├── Member Rate (-5%)
      ├── Mobile Rate (-8%)
      └── Package Rate (breakfast included, +20 EUR)
    """
    
    def __init__(self, db, redis, kafka):
        self.db = db
        self.redis = redis
        self.kafka = kafka
    
    async def update_master_rate(self, room_type_id: str, rate_plan_id: str, 
                                  dates: DateRange, new_rate_cents: int):
        """Update master rate and cascade to all derived rates"""
        
        # Get all derived rate plans
        derived_plans = await self.db.fetch("""
            SELECT rate_plan_id, derivation_rule 
            FROM rate_plans 
            WHERE parent_rate_plan_id = $1 AND status = 'active'
        """, rate_plan_id)
        
        async with self.db.transaction() as tx:
            # Update master rate
            await self._upsert_daily_rates(tx, room_type_id, rate_plan_id, dates, new_rate_cents)
            
            # Cascade to derived rates
            for derived in derived_plans:
                derived_rate = self._apply_derivation(new_rate_cents, derived['derivation_rule'])
                await self._upsert_daily_rates(
                    tx, room_type_id, derived['rate_plan_id'], dates, derived_rate
                )
        
        # Invalidate cache and emit event
        await self._invalidate_and_notify(room_type_id, dates)
    
    def _apply_derivation(self, base_rate_cents: int, rule: dict) -> int:
        """Apply derivation rule to calculate derived rate"""
        if rule['type'] == 'percentage':
            return int(base_rate_cents * (1 + rule['value'] / 100))
        elif rule['type'] == 'fixed_offset':
            return base_rate_cents + rule['value']
        elif rule['type'] == 'fixed_amount':
            return rule['value']
        raise ValueError(f"Unknown derivation type: {rule['type']}")
    
    async def _invalidate_and_notify(self, room_type_id: str, dates: DateRange):
        """Invalidate Redis cache and emit Kafka event for search index update"""
        # Invalidate rate cache
        pipe = self.redis.pipeline()
        current = dates.start
        while current <= dates.end:
            pipe.delete(f"rate:{room_type_id}:{current.isoformat()}")
            current += timedelta(days=1)
        await pipe.execute()
        
        # Emit event for search service to re-index
        await self.kafka.produce('rate.changes', {
            'room_type_id': room_type_id,
            'hotel_id': await self._get_hotel_id(room_type_id),
            'date_from': dates.start.isoformat(),
            'date_to': dates.end.isoformat(),
            'timestamp': datetime.utcnow().isoformat()
        })

class RateParityChecker:
    """Ensures rate parity across distribution channels"""
    
    async def check_parity(self, hotel_id: str, date: date) -> List[ParityViolation]:
        # Fetch rates from all channels
        our_rates = await self._get_our_rates(hotel_id, date)
        
        # Compare with OTA rates (scraped/API)
        violations = []
        for channel in ['expedia', 'hotels_com', 'direct_website']:
            channel_rates = await self._get_channel_rates(hotel_id, date, channel)
            for room_type, our_rate in our_rates.items():
                channel_rate = channel_rates.get(room_type)
                if channel_rate and channel_rate < our_rate * 0.98:  # 2% tolerance
                    violations.append(ParityViolation(
                        hotel_id=hotel_id, room_type=room_type,
                        our_rate=our_rate, channel_rate=channel_rate,
                        channel=channel, date=date
                    ))
        return violations
```

### Deep Dive 2: Allotment & Overbooking Strategy

**Problem**: Hotels want to maximize revenue. Statistical overbooking based on historical cancellation rates can increase revenue by 5-15%, but walking a guest is extremely costly.

```python
class AllotmentManager:
    """
    Manages room inventory with intelligent overbooking.
    
    Physical rooms: 100 Superior Doubles
    Sellable inventory = Physical + Overbooking Allowance
    Overbooking % depends on: cancellation probability, no-show rate, walk cost
    """
    
    def __init__(self, db, redis, ml_model):
        self.db = db
        self.redis = redis
        self.ml_model = ml_model
    
    async def check_availability(self, room_type_id: str, date: date) -> AvailabilityResult:
        """Check if rooms are available (including overbooking buffer)"""
        
        # Fast path: Redis counter
        cache_key = f"inv:{room_type_id}:{date.isoformat()}"
        cached = await self.redis.hgetall(cache_key)
        
        if cached:
            total = int(cached['total'])
            sold = int(cached['sold'])
            overbooking = int(cached['overbooking'])
            stop_sell = cached.get('stop_sell') == '1'
            
            if stop_sell:
                return AvailabilityResult(available=False, reason='stop_sell')
            
            available = (total + overbooking) - sold
            return AvailabilityResult(
                available=available > 0,
                rooms_left=available,
                urgency='last_rooms' if available <= 3 else None
            )
        
        # Cache miss: load from DB
        return await self._load_and_cache(room_type_id, date)
    
    async def calculate_overbooking_allowance(self, room_type_id: str, date: date) -> int:
        """
        Calculate optimal overbooking level using expected cost model:
        
        E[cost of overbooking by X] = P(need to walk) × walk_cost
        E[revenue gain] = P(cancellation) × room_revenue
        
        Optimal X: marginal revenue gain = marginal walk cost
        """
        # Get historical data
        stats = await self._get_cancellation_stats(room_type_id, date)
        
        features = {
            'historical_cancel_rate': stats.cancel_rate,  # e.g., 0.15
            'historical_noshow_rate': stats.noshow_rate,  # e.g., 0.03
            'days_until_date': (date - date.today()).days,
            'day_of_week': date.weekday(),
            'is_event_period': await self._check_events(room_type_id, date),
            'current_booking_pace': stats.booking_pace,
            'refundable_booking_ratio': stats.refundable_ratio,
        }
        
        # ML model predicts actual cancellation probability
        predicted_cancel_prob = self.ml_model.predict_cancellation(features)
        
        # Calculate optimal overbooking
        total_rooms = await self._get_total_rooms(room_type_id)
        avg_room_revenue = await self._get_avg_revenue(room_type_id, date)
        walk_cost = avg_room_revenue * 3  # Walking cost ≈ 3x room revenue
        
        # Binary search for optimal overbooking level
        optimal = 0
        for x in range(1, int(total_rooms * 0.2)):  # Max 20% overbooking
            # P(walk needed | overbooked by x) using binomial distribution
            from scipy.stats import binom
            p_walk = 1 - binom.cdf(x - 1, total_rooms + x, 1 - predicted_cancel_prob)
            
            marginal_revenue = avg_room_revenue * predicted_cancel_prob
            marginal_cost = p_walk * walk_cost
            
            if marginal_revenue > marginal_cost:
                optimal = x
            else:
                break
        
        return optimal
    
    async def sell_room(self, room_type_id: str, date: date) -> bool:
        """Atomic room sale with Redis counter"""
        cache_key = f"inv:{room_type_id}:{date.isoformat()}"
        
        # Lua script for atomic check-and-decrement
        lua_script = """
        local total = tonumber(redis.call('HGET', KEYS[1], 'total'))
        local sold = tonumber(redis.call('HGET', KEYS[1], 'sold'))
        local overbooking = tonumber(redis.call('HGET', KEYS[1], 'overbooking'))
        local stop_sell = redis.call('HGET', KEYS[1], 'stop_sell')
        
        if stop_sell == '1' then return 0 end
        if sold >= (total + overbooking) then return 0 end
        
        redis.call('HINCRBY', KEYS[1], 'sold', 1)
        return 1
        """
        
        result = await self.redis.eval(lua_script, 1, cache_key)
        
        if result == 1:
            # Async: persist to DB
            await self.kafka.produce('inventory.updates', {
                'room_type_id': room_type_id,
                'date': date.isoformat(),
                'action': 'sold',
                'timestamp': datetime.utcnow().isoformat()
            })
            return True
        return False

class StopSellManager:
    """Automatically triggers stop-sell when thresholds are breached"""
    
    async def evaluate_stop_sell(self, room_type_id: str, date: date):
        inv = await self.get_inventory(room_type_id, date)
        
        available = inv.total + inv.overbooking - inv.sold
        
        # Stop sell conditions
        if available <= 0:
            await self._set_stop_sell(room_type_id, date, reason='sold_out')
        elif available <= inv.min_availability_alert:
            await self._emit_low_inventory_alert(room_type_id, date, available)
```

### Deep Dive 3: Search Ranking Algorithm

```python
class HotelSearchRanker:
    """
    Multi-factor ranking combining:
    1. Price competitiveness
    2. Review quality
    3. Commission (business factor)
    4. Conversion probability (ML)
    5. Content quality
    """
    
    def rank_hotels(self, hotels: List[Hotel], query: SearchQuery, user: User) -> List[Hotel]:
        scored = []
        for hotel in hotels:
            score = self._compute_score(hotel, query, user)
            scored.append((hotel, score))
        
        scored.sort(key=lambda x: x[1], reverse=True)
        return [h for h, _ in scored]
    
    def _compute_score(self, hotel: Hotel, query: SearchQuery, user: User) -> float:
        score = 0.0
        
        # Price competitiveness (25%) - lower price relative to quality = better
        price_score = self._price_value_score(hotel, query)
        score += 0.25 * price_score
        
        # Review quality (25%)
        review_score = self._review_score(hotel)
        score += 0.25 * review_score
        
        # Conversion probability (20%) - ML predicted P(book | click)
        conversion_score = self._conversion_model.predict(hotel, query, user)
        score += 0.20 * conversion_score
        
        # Commission/revenue potential (15%)
        commission_score = hotel.commission_percent / 25.0  # normalize to 0-1
        score += 0.15 * commission_score
        
        # Content quality (10%) - photos, description completeness
        content_score = self._content_quality(hotel)
        score += 0.10 * content_score
        
        # Recency & freshness (5%)
        freshness_score = self._freshness_score(hotel)
        score += 0.05 * freshness_score
        
        # Boosts
        if hotel.is_preferred_partner:
            score *= 1.05
        if hotel.has_genius_deal and user.is_genius:
            score *= 1.08
        
        return score
    
    def _price_value_score(self, hotel: Hotel, query: SearchQuery) -> float:
        """Score based on price vs star rating vs location"""
        expected_price = self._get_market_average(hotel.city, hotel.star_rating, query.dates)
        actual_price = hotel.cheapest_rate
        
        # Cheaper than expected for its tier = better score
        ratio = expected_price / max(actual_price, 1)
        return min(1.0, ratio)
    
    def _review_score(self, hotel: Hotel) -> float:
        """Bayesian average review score"""
        C = 7.0  # prior mean (average platform score)
        m = 10   # prior weight (minimum reviews for confidence)
        
        bayesian = (hotel.review_count * hotel.avg_score + m * C) / (hotel.review_count + m)
        return bayesian / 10.0  # normalize to 0-1
    
    def _conversion_model_features(self, hotel, query, user):
        return {
            'price_relative': hotel.cheapest_rate / query.avg_market_price,
            'review_score': hotel.avg_score,
            'review_count_log': math.log1p(hotel.review_count),
            'star_rating': hotel.star_rating,
            'distance_to_center': hotel.distance_km,
            'photos_count': hotel.photo_count,
            'has_free_cancellation': hotel.has_free_cancel,
            'user_previous_stars': user.avg_booked_stars,
            'user_price_sensitivity': user.price_sensitivity_score,
            'device': query.device_type,
            'days_until_checkin': (query.check_in - date.today()).days,
        }
```

## 8. Component Optimization

### Redis Inventory Counter Design
```python
# Redis data structure for inventory
# Hash per room_type per date
# Key: inv:{room_type_id}:{YYYY-MM-DD}
# Fields: total, sold, blocked, overbooking, stop_sell

INVENTORY_CACHE_CONFIG = {
    "ttl_seconds": 86400,  # 24h, refreshed on update
    "lua_sell_script": "...",  # Atomic sell
    "lua_release_script": "...",  # Atomic release on cancel
    "warmup_days_ahead": 90,  # Pre-warm 90 days of inventory
}

# Periodic reconciliation job (every 5 min)
class InventoryReconciler:
    """Reconciles Redis counters with PostgreSQL truth"""
    async def reconcile(self):
        room_types = await self.db.fetch("SELECT room_type_id FROM room_types WHERE status='active'")
        for rt in room_types:
            for day_offset in range(90):
                d = date.today() + timedelta(days=day_offset)
                db_inv = await self._get_db_inventory(rt.room_type_id, d)
                redis_inv = await self._get_redis_inventory(rt.room_type_id, d)
                
                if db_inv.sold != redis_inv.sold:
                    # DB is source of truth
                    await self._fix_redis(rt.room_type_id, d, db_inv)
                    self.metrics.increment('inventory.reconciliation.fixes')
```

### Elasticsearch Hotel Index Optimization
```json
{
    "settings": {
        "number_of_shards": 20,
        "number_of_replicas": 2,
        "index.search.idle.after": "30s",
        "index.queries.cache.enabled": true
    },
    "mappings": {
        "properties": {
            "location": {"type": "geo_point"},
            "city": {"type": "keyword"},
            "country_code": {"type": "keyword"},
            "star_rating": {"type": "float"},
            "review_score": {"type": "float"},
            "review_count": {"type": "integer"},
            "min_price_eur": {"type": "integer"},
            "property_type": {"type": "keyword"},
            "amenities": {"type": "keyword"},
            "commission_percent": {"type": "float"},
            "name": {
                "type": "text",
                "fields": {"keyword": {"type": "keyword"}}
            }
        }
    }
}
```

### Kafka Topic Configuration
```yaml
topics:
  inventory.updates:
    partitions: 64
    replication.factor: 3
    retention.ms: 259200000  # 3 days
    partition.assignment.strategy: cooperative-sticky
    # Partition by room_type_id for ordering per room
    
  rate.changes:
    partitions: 32
    replication.factor: 3
    retention.ms: 604800000  # 7 days
    compression.type: snappy
    
  booking.events:
    partitions: 32
    replication.factor: 3
    retention.ms: 2592000000  # 30 days
    min.insync.replicas: 2
    # Exactly-once semantics for booking events
    
  search.impressions:
    partitions: 128
    replication.factor: 2
    retention.ms: 86400000  # 1 day
    compression.type: lz4
    # High volume, analytics only
```

## 9. Observability

### Key Metrics
```yaml
metrics:
  - name: hotel_search_latency_ms
    type: histogram
    labels: [region, sort_type, has_dates]
    
  - name: booking_conversion_rate
    type: gauge
    labels: [source, device, region]
    
  - name: inventory_accuracy_percent
    type: gauge
    labels: [region]
    description: "Redis vs DB inventory match rate"
    
  - name: rate_propagation_delay_ms
    type: histogram
    labels: [source_type]
    description: "Time from rate update to search index reflection"
    
  - name: overbooking_walk_events
    type: counter
    labels: [hotel_id, reason]
    
  - name: cancellation_rate
    type: gauge
    labels: [rate_type, days_before_checkin]
```

### Alerting
```yaml
alerts:
  - name: InventoryDesync
    condition: hotel_inventory_accuracy_percent < 99
    for: 5m
    severity: critical
    action: "Trigger emergency reconciliation"
    
  - name: BookingFailureSpike
    condition: rate(booking_failures_total[5m]) > 50
    severity: critical
    
  - name: RatePropagationSlow
    condition: histogram_quantile(0.95, rate_propagation_delay_ms) > 10000
    for: 3m
    severity: warning
    
  - name: WalkEventDetected
    condition: increase(overbooking_walk_events[1h]) > 0
    severity: critical
    action: "Notify hotel operations + reduce overbooking for property"
```

### Distributed Tracing Example
```
Search Request → [API Gateway: 3ms]
  → [Search Service: 650ms total]
    ├── [ES Hotel Query: 120ms] (geo + filters)
    ├── [Inventory Check: 200ms] (batch Redis for 50 hotels × 4 nights)
    ├── [Rate Calculation: 150ms] (derived rates, taxes, currency)
    ├── [Ranking Model: 100ms] (ML inference)
    └── [Response Assembly: 80ms] (photos, badges, urgency)
```

## 10. Considerations

### Rate Update Consistency
- Channel managers send rate updates via XML/JSON APIs
- Updates must be atomic per room_type × date_range
- Use optimistic locking (version column) on rate updates
- Conflict resolution: last-writer-wins with timestamp

### Multi-Currency Handling
```python
class CurrencyService:
    """Handles display currency conversion with daily rate caching"""
    
    def convert(self, amount_cents: int, from_currency: str, to_currency: str) -> int:
        rate = self.get_rate(from_currency, to_currency)
        converted = int(amount_cents * rate)
        # Round to nearest common denomination
        return self._round_to_display(converted, to_currency)
    
    def get_rate(self, from_c: str, to_c: str) -> float:
        # Redis cached, refreshed every 4 hours
        return self.redis.get(f"fx:{from_c}:{to_c}") or self._fetch_from_provider(from_c, to_c)
```

### Handling Peak Load (Flash Sales)
- Last-minute deals can cause 10x traffic spike
- Solution: Queue-based booking with virtual waiting room
- Pre-compute availability for deal listings
- Rate-limit per-user to prevent bot abuse

### Data Consistency Across Services
- Saga pattern for booking: Reserve Inventory → Process Payment → Confirm Booking
- Compensation: If payment fails → release inventory counter
- Dead letter queue for failed saga steps with manual intervention alerts

### Geographic Sharding Strategy
```
Region shards for PostgreSQL:
- EU shard: Hotels in Europe/Africa
- NA shard: Hotels in Americas
- APAC shard: Hotels in Asia-Pacific

Cross-region queries (user in EU searching APAC hotels):
- Route to APAC read replica in EU region
- Eventual consistency (~1s lag) acceptable for search
- Booking always routed to primary shard
```

## 11. Additional Diagrams

### Booking State Machine
```
┌──────────┐   payment    ┌───────────┐   check-in   ┌──────────┐
│  PENDING │────success──▶│ CONFIRMED │─────────────▶│  ACTIVE  │
└────┬─────┘              └─────┬─────┘              └────┬─────┘
     │                          │                         │
  payment                    modify                   check-out
   fail                        │                         │
     │                    ┌────┴─────┐              ┌────┴──────┐
     ▼                    │ MODIFIED │              │ COMPLETED │
┌──────────┐              └──────────┘              └───────────┘
│  FAILED  │                    │
└──────────┘              cancel│
                                ▼
                         ┌───────────┐
                         │ CANCELLED │
                         └───────────┘
```

### Rate Hierarchy
```
Master Rate (€220/night)
├── Non-Refundable: €220 × 0.85 = €187
├── Advance Purchase (14d+): €220 × 0.90 = €198
├── Genius Member: €220 × 0.95 = €209
├── Mobile-Only: €220 × 0.92 = €202
└── Breakfast Package: €220 + €20 = €240
```
