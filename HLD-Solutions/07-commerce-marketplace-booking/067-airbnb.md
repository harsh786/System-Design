# Design Airbnb - Vacation Rental Marketplace

## 1. Functional Requirements

### Core Features
- **Listing Management**: Hosts create/edit properties with photos, amenities, house rules, pricing
- **Search & Discovery**: Location-based search with date availability, filters (price, type, amenities)
- **Booking Flow**: Request-to-book or instant book with calendar management
- **Pricing Engine**: Host-set base price + dynamic pricing (smart pricing)
- **Reviews**: Two-way review system (guest reviews host, host reviews guest)
- **Messaging**: Real-time messaging between host and guest (pre/post booking)
- **Superhost Program**: Gamified host quality tier system
- **Experiences**: Bookable activities/tours hosted by locals

### User Flows
1. Guest searches → filters → views listing → checks availability → books → pays → stays → reviews
2. Host creates listing → sets availability → receives booking → hosts → reviews guest
3. Host enables smart pricing → system adjusts nightly rates automatically

## 2. Non-Functional Requirements

| Requirement | Target |
|---|---|
| Search Latency | P99 < 500ms |
| Booking Consistency | Strong consistency (no double-booking) |
| Availability | 99.99% for booking flow |
| Photo Serving | P95 < 200ms (CDN) |
| Calendar Updates | Real-time propagation < 2s |
| Scale | 7M+ active listings, 150M+ users |
| Throughput | 50K searches/sec peak, 5K bookings/min |
| Data Durability | Zero booking data loss |
| Geo Distribution | Multi-region (NA, EU, APAC) |
| Message Delivery | At-least-once, ordered per conversation |

## 3. Capacity Estimation

### Storage
```
Listings: 7M × 5KB metadata = 35GB
Photos: 7M listings × 20 photos × 2MB = 280TB
User Profiles: 150M × 2KB = 300GB
Bookings: 500M historical × 1KB = 500GB
Reviews: 300M × 500B = 150GB
Messages: 2B messages × 200B = 400GB
Calendar data: 7M listings × 365 days × 50B = 128GB
```

### Bandwidth
```
Search queries: 50K/s × 10KB response = 500MB/s
Photo serving: 200K/s × 500KB (compressed) = 100GB/s (CDN-served)
Booking writes: 5K/min × 2KB = 170KB/s
Message throughput: 10K messages/s × 200B = 2MB/s
```

### Compute
```
Search cluster: 200 nodes (Elasticsearch)
Application servers: 500 instances (auto-scaled)
Cache cluster: 50 Redis nodes (500GB total)
DB cluster: 20 PostgreSQL nodes (sharded)
ML inference: 50 GPU instances for pricing/ranking
```

## 4. Data Modeling

### Full Database Schemas

```sql
-- Users table
CREATE TABLE users (
    user_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    phone VARCHAR(20),
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    profile_photo_url TEXT,
    bio TEXT,
    identity_verified BOOLEAN DEFAULT FALSE,
    verification_level VARCHAR(20) DEFAULT 'none', -- none, basic, enhanced
    superhost BOOLEAN DEFAULT FALSE,
    superhost_since TIMESTAMP,
    response_rate DECIMAL(5,2),
    response_time_hours INT,
    languages VARCHAR(200)[],
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    last_active TIMESTAMP,
    account_status VARCHAR(20) DEFAULT 'active' -- active, suspended, deactivated
);
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_superhost ON users(superhost) WHERE superhost = TRUE;

-- Listings table
CREATE TABLE listings (
    listing_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    host_id UUID NOT NULL REFERENCES users(user_id),
    title VARCHAR(200) NOT NULL,
    description TEXT,
    property_type VARCHAR(50) NOT NULL, -- apartment, house, villa, treehouse, etc.
    room_type VARCHAR(30) NOT NULL, -- entire_place, private_room, shared_room
    latitude DECIMAL(10, 7) NOT NULL,
    longitude DECIMAL(10, 7) NOT NULL,
    address_line1 VARCHAR(255),
    address_line2 VARCHAR(255),
    city VARCHAR(100) NOT NULL,
    state VARCHAR(100),
    country VARCHAR(100) NOT NULL,
    postal_code VARCHAR(20),
    max_guests INT NOT NULL,
    bedrooms INT NOT NULL,
    beds INT NOT NULL,
    bathrooms DECIMAL(3,1) NOT NULL,
    base_price_cents INT NOT NULL,
    currency VARCHAR(3) DEFAULT 'USD',
    cleaning_fee_cents INT DEFAULT 0,
    service_fee_percent DECIMAL(4,2) DEFAULT 14.0,
    weekly_discount_percent DECIMAL(4,2) DEFAULT 0,
    monthly_discount_percent DECIMAL(4,2) DEFAULT 0,
    min_nights INT DEFAULT 1,
    max_nights INT DEFAULT 365,
    check_in_time TIME DEFAULT '15:00',
    check_out_time TIME DEFAULT '11:00',
    instant_book BOOLEAN DEFAULT FALSE,
    smart_pricing_enabled BOOLEAN DEFAULT FALSE,
    status VARCHAR(20) DEFAULT 'draft', -- draft, active, paused, delisted
    avg_rating DECIMAL(3,2),
    review_count INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_listings_host ON listings(host_id);
CREATE INDEX idx_listings_location ON listings USING GIST(
    ST_MakePoint(longitude, latitude)::geography
);
CREATE INDEX idx_listings_city_status ON listings(city, status) WHERE status = 'active';
CREATE INDEX idx_listings_price ON listings(base_price_cents) WHERE status = 'active';

-- Listing amenities
CREATE TABLE listing_amenities (
    listing_id UUID REFERENCES listings(listing_id),
    amenity_id INT REFERENCES amenities(amenity_id),
    PRIMARY KEY (listing_id, amenity_id)
);

CREATE TABLE amenities (
    amenity_id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    category VARCHAR(50), -- essentials, features, safety, location
    icon_url TEXT
);

-- Listing photos
CREATE TABLE listing_photos (
    photo_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    listing_id UUID NOT NULL REFERENCES listings(listing_id),
    url TEXT NOT NULL,
    caption VARCHAR(200),
    sort_order INT NOT NULL,
    width INT,
    height INT,
    is_cover BOOLEAN DEFAULT FALSE,
    uploaded_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_photos_listing ON listing_photos(listing_id, sort_order);

-- House rules
CREATE TABLE listing_rules (
    rule_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    listing_id UUID NOT NULL REFERENCES listings(listing_id),
    rule_type VARCHAR(50), -- no_smoking, no_pets, no_parties, quiet_hours
    description TEXT,
    is_custom BOOLEAN DEFAULT FALSE
);

-- Calendar / Availability
CREATE TABLE listing_calendar (
    listing_id UUID NOT NULL REFERENCES listings(listing_id),
    date DATE NOT NULL,
    available BOOLEAN DEFAULT TRUE,
    price_cents INT, -- override price for this date (NULL = use base)
    min_nights INT, -- override min nights
    note VARCHAR(200),
    PRIMARY KEY (listing_id, date)
);
CREATE INDEX idx_calendar_avail ON listing_calendar(listing_id, date, available);

-- Blocked dates (more efficient for long blocks)
CREATE TABLE listing_blocked_dates (
    block_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    listing_id UUID NOT NULL REFERENCES listings(listing_id),
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    reason VARCHAR(50), -- host_blocked, booking, maintenance
    booking_id UUID REFERENCES bookings(booking_id),
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_blocked_listing_dates ON listing_blocked_dates(listing_id, start_date, end_date);

-- Bookings
CREATE TABLE bookings (
    booking_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    listing_id UUID NOT NULL REFERENCES listings(listing_id),
    guest_id UUID NOT NULL REFERENCES users(user_id),
    host_id UUID NOT NULL REFERENCES users(user_id),
    check_in DATE NOT NULL,
    check_out DATE NOT NULL,
    num_guests INT NOT NULL,
    num_nights INT GENERATED ALWAYS AS (check_out - check_in) STORED,
    nightly_rate_cents INT NOT NULL,
    cleaning_fee_cents INT NOT NULL,
    service_fee_cents INT NOT NULL,
    taxes_cents INT NOT NULL,
    total_cents INT NOT NULL,
    currency VARCHAR(3) DEFAULT 'USD',
    status VARCHAR(30) NOT NULL DEFAULT 'pending',
    -- pending, confirmed, active, completed, cancelled_by_guest, cancelled_by_host, declined
    payment_intent_id VARCHAR(255),
    payout_id VARCHAR(255),
    special_requests TEXT,
    cancellation_policy VARCHAR(30), -- flexible, moderate, strict
    cancelled_at TIMESTAMP,
    cancellation_reason TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_bookings_listing_dates ON bookings(listing_id, check_in, check_out) WHERE status IN ('confirmed', 'active');
CREATE INDEX idx_bookings_guest ON bookings(guest_id, created_at DESC);
CREATE INDEX idx_bookings_host ON bookings(host_id, created_at DESC);
CREATE INDEX idx_bookings_status ON bookings(status, check_in);

-- Reviews
CREATE TABLE reviews (
    review_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    booking_id UUID NOT NULL REFERENCES bookings(booking_id),
    reviewer_id UUID NOT NULL REFERENCES users(user_id),
    reviewee_id UUID NOT NULL REFERENCES users(user_id),
    listing_id UUID NOT NULL REFERENCES listings(listing_id),
    review_type VARCHAR(20) NOT NULL, -- guest_to_host, host_to_guest
    overall_rating INT NOT NULL CHECK (overall_rating BETWEEN 1 AND 5),
    cleanliness_rating INT CHECK (cleanliness_rating BETWEEN 1 AND 5),
    accuracy_rating INT CHECK (accuracy_rating BETWEEN 1 AND 5),
    communication_rating INT CHECK (communication_rating BETWEEN 1 AND 5),
    location_rating INT CHECK (location_rating BETWEEN 1 AND 5),
    checkin_rating INT CHECK (checkin_rating BETWEEN 1 AND 5),
    value_rating INT CHECK (value_rating BETWEEN 1 AND 5),
    comment TEXT,
    private_feedback TEXT, -- only visible to host
    host_response TEXT,
    is_published BOOLEAN DEFAULT FALSE, -- published after both submit or 14 days
    created_at TIMESTAMP DEFAULT NOW(),
    published_at TIMESTAMP
);
CREATE INDEX idx_reviews_listing ON reviews(listing_id, created_at DESC) WHERE is_published = TRUE;
CREATE INDEX idx_reviews_booking ON reviews(booking_id);

-- Messages
CREATE TABLE conversations (
    conversation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    booking_id UUID REFERENCES bookings(booking_id),
    listing_id UUID NOT NULL REFERENCES listings(listing_id),
    guest_id UUID NOT NULL REFERENCES users(user_id),
    host_id UUID NOT NULL REFERENCES users(user_id),
    last_message_at TIMESTAMP,
    guest_unread_count INT DEFAULT 0,
    host_unread_count INT DEFAULT 0,
    status VARCHAR(20) DEFAULT 'active', -- active, archived
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_conversations_guest ON conversations(guest_id, last_message_at DESC);
CREATE INDEX idx_conversations_host ON conversations(host_id, last_message_at DESC);

CREATE TABLE messages (
    message_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES conversations(conversation_id),
    sender_id UUID NOT NULL REFERENCES users(user_id),
    content TEXT NOT NULL,
    message_type VARCHAR(20) DEFAULT 'text', -- text, image, booking_request, system
    read_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_messages_conversation ON messages(conversation_id, created_at);

-- Pricing history (for smart pricing)
CREATE TABLE pricing_history (
    listing_id UUID NOT NULL,
    date DATE NOT NULL,
    suggested_price_cents INT,
    actual_price_cents INT,
    demand_score DECIMAL(3,2),
    occupancy_rate DECIMAL(3,2),
    comparable_avg_price INT,
    PRIMARY KEY (listing_id, date)
);

-- Superhost tracking
CREATE TABLE superhost_assessments (
    assessment_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    host_id UUID NOT NULL REFERENCES users(user_id),
    assessment_quarter VARCHAR(7), -- 2024-Q1
    overall_rating DECIMAL(3,2),
    response_rate DECIMAL(5,2),
    cancellation_rate DECIMAL(5,2),
    trips_hosted INT,
    qualifies BOOLEAN,
    created_at TIMESTAMP DEFAULT NOW()
);
```

## 5. High-Level Design (HLD)

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              CLIENT LAYER                                        │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐                       │
│  │  Web App │  │iOS/Android│  │ Host App │  │ Admin    │                       │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘                       │
└───────┼──────────────┼──────────────┼──────────────┼────────────────────────────┘
        │              │              │              │
        ▼              ▼              ▼              ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           API GATEWAY / CDN                                      │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────┐  ┌─────────────┐         │
│  │ CloudFront  │  │ Rate Limiter │  │   Auth/JWT   │  │  API Router │         │
│  │   (CDN)     │  │  (Token Bkt) │  │  Validation  │  │             │         │
│  └─────────────┘  └──────────────┘  └──────────────┘  └──────┬──────┘         │
└───────────────────────────────────────────────────────────────┼─────────────────┘
                                                                │
        ┌────────────────────┬──────────────────┬───────────────┼────────────┐
        ▼                    ▼                  ▼               ▼            ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌────────────┐  ┌─────────┐
│   Search     │  │   Listing    │  │   Booking    │  │  Pricing   │  │ Message │
│   Service    │  │   Service    │  │   Service    │  │  Service   │  │ Service │
│              │  │              │  │              │  │            │  │         │
│ - Geo search │  │ - CRUD       │  │ - Reserve    │  │ - Dynamic  │  │ - Chat  │
│ - Filters   │  │ - Photos     │  │ - Confirm    │  │ - Calendar │  │ - Notif │
│ - Ranking   │  │ - Calendar   │  │ - Cancel     │  │ - ML model │  │ - WS    │
│ - Suggest   │  │ - Rules      │  │ - Payout     │  │            │  │         │
└──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └─────┬──────┘  └────┬────┘
       │                  │                  │                │              │
       ▼                  ▼                  ▼                ▼              ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│                           DATA & EVENT LAYER                                     │
│                                                                                  │
│  ┌─────────────┐  ┌─────────────┐  ┌──────────────┐  ┌──────────────────┐     │
│  │Elasticsearch│  │ PostgreSQL  │  │    Redis     │  │     Kafka        │     │
│  │  (Search)   │  │  (Primary)  │  │   (Cache +   │  │  (Events Bus)    │     │
│  │             │  │  Sharded by │  │   Sessions)  │  │                  │     │
│  │ - Listings  │  │  listing_id │  │              │  │ - booking.events │     │
│  │ - Geo index │  │  user_id    │  │ - Calendar   │  │ - calendar.sync  │     │
│  │ - Autocmpl  │  │             │  │ - Listings   │  │ - pricing.update │     │
│  └─────────────┘  └─────────────┘  │ - Sessions   │  │ - review.events  │     │
│                                     └──────────────┘  └──────────────────┘     │
│  ┌─────────────┐  ┌─────────────┐  ┌──────────────┐                           │
│  │     S3      │  │  DynamoDB   │  │ Apache Flink │                           │
│  │  (Photos)   │  │ (Messages)  │  │ (Stream Proc)│                           │
│  └─────────────┘  └─────────────┘  └──────────────┘                           │
└──────────────────────────────────────────────────────────────────────────────────┘
        │                                                        │
        ▼                                                        ▼
┌──────────────────────────┐                    ┌──────────────────────────┐
│    ML / Analytics        │                    │   External Services      │
│  ┌─────────┐ ┌────────┐ │                    │  ┌────────┐ ┌─────────┐ │
│  │ Pricing │ │Ranking │ │                    │  │Stripe  │ │ Twilio  │ │
│  │  Model  │ │ Model  │ │                    │  │Payment │ │  SMS    │ │
│  └─────────┘ └────────┘ │                    │  └────────┘ └─────────┘ │
│  ┌─────────┐ ┌────────┐ │                    │  ┌────────┐ ┌─────────┐ │
│  │ Fraud   │ │Recomm. │ │                    │  │SendGrid│ │ Google  │ │
│  │Detector │ │ Engine │ │                    │  │ Email  │ │  Maps   │ │
│  └─────────┘ └────────┘ │                    │  └────────┘ └─────────┘ │
└──────────────────────────┘                    └──────────────────────────┘
```

## 6. Low-Level Design (LLD) - APIs

### Search API
```
POST /api/v1/search/listings
Request:
{
    "location": {
        "latitude": 37.7749,
        "longitude": -122.4194,
        "radius_km": 15
    },
    "check_in": "2024-06-15",
    "check_out": "2024-06-20",
    "guests": 4,
    "filters": {
        "price_min": 100,
        "price_max": 500,
        "property_type": ["apartment", "house"],
        "room_type": "entire_place",
        "amenities": ["wifi", "pool", "kitchen"],
        "instant_book": true,
        "superhost": true
    },
    "sort": "relevance",
    "page": 1,
    "page_size": 20
}

Response:
{
    "results": [
        {
            "listing_id": "abc123",
            "title": "Stunning Marina View Apartment",
            "property_type": "apartment",
            "room_type": "entire_place",
            "latitude": 37.8035,
            "longitude": -122.4382,
            "photos": [{"url": "https://cdn.airbnb.com/...", "width": 720}],
            "price": {"nightly": 250, "total": 1450, "currency": "USD"},
            "rating": 4.92,
            "review_count": 187,
            "host": {"name": "Sarah", "superhost": true, "photo": "..."},
            "amenities_preview": ["Wifi", "Pool", "Kitchen", "Parking"],
            "instant_book": true
        }
    ],
    "total_results": 342,
    "page": 1,
    "search_id": "srch_abc123",
    "map_bounds": {"ne": {"lat": 37.85, "lng": -122.35}, "sw": {"lat": 37.70, "lng": -122.52}}
}
```

### Booking API
```
POST /api/v1/bookings
Request:
{
    "listing_id": "abc123",
    "check_in": "2024-06-15",
    "check_out": "2024-06-20",
    "guests": {"adults": 2, "children": 1, "infants": 0},
    "special_requests": "Late check-in around 10pm",
    "payment_method_id": "pm_stripe_xyz"
}

Response:
{
    "booking_id": "bk_789xyz",
    "status": "confirmed",  // or "pending" for request-to-book
    "listing": {"title": "Stunning Marina View", "host": "Sarah"},
    "dates": {"check_in": "2024-06-15", "check_out": "2024-06-20"},
    "pricing": {
        "nightly_rate": 250,
        "nights": 5,
        "subtotal": 1250,
        "cleaning_fee": 100,
        "service_fee": 189,
        "taxes": 153,
        "total": 1692
    },
    "cancellation_policy": "moderate",
    "confirmation_code": "HMRK7YXQ"
}
```

### Calendar Management API
```
PUT /api/v1/listings/{listing_id}/calendar
Request:
{
    "dates": [
        {"date": "2024-06-15", "available": false, "price_cents": null},
        {"date": "2024-06-16", "available": true, "price_cents": 28000},
        {"date": "2024-06-17", "available": true, "price_cents": 32000}
    ]
}

GET /api/v1/listings/{listing_id}/calendar?start=2024-06-01&end=2024-06-30
Response:
{
    "listing_id": "abc123",
    "calendar": [
        {"date": "2024-06-01", "available": true, "price": 250, "min_nights": 2},
        {"date": "2024-06-02", "available": true, "price": 250, "min_nights": 2},
        {"date": "2024-06-03", "available": false, "reason": "booked"}
    ]
}
```

### Review API
```
POST /api/v1/reviews
Request:
{
    "booking_id": "bk_789xyz",
    "overall_rating": 5,
    "cleanliness_rating": 5,
    "accuracy_rating": 4,
    "communication_rating": 5,
    "location_rating": 5,
    "checkin_rating": 5,
    "value_rating": 4,
    "comment": "Amazing stay! Sarah was incredibly welcoming...",
    "private_feedback": "The bathroom could use a new shower curtain"
}
```

### Smart Pricing API
```
POST /api/v1/pricing/suggest
Request:
{
    "listing_id": "abc123",
    "date_range": {"start": "2024-06-01", "end": "2024-08-31"}
}

Response:
{
    "suggestions": [
        {
            "date": "2024-06-15",
            "suggested_price": 285,
            "base_price": 250,
            "factors": {
                "seasonality": +15,
                "demand": +20,
                "local_events": 0,
                "day_of_week": 0,
                "comparable_listings_avg": 280
            },
            "confidence": 0.87
        }
    ]
}
```

## 7. Deep Dives

### Deep Dive 1: Availability Search (Calendar Intersection)

**Problem**: Given a date range (check_in, check_out), find all listings that are fully available for ALL dates in the range within a geographic area.

**Strategy**: Geo-filter first (reduces candidate set dramatically), then date-filter.

```python
# Availability Search Algorithm
class AvailabilitySearchEngine:
    def __init__(self, es_client, redis_client, pg_pool):
        self.es = es_client
        self.redis = redis_client
        self.pg = pg_pool

    async def search(self, params: SearchParams) -> List[Listing]:
        # Phase 1: Geo + basic filter via Elasticsearch (fast, reduces to ~5K candidates)
        candidates = await self._geo_filter(params)
        
        # Phase 2: Availability check via Redis bitmap (sub-ms per listing)
        available_ids = await self._check_availability_batch(
            candidates, params.check_in, params.check_out
        )
        
        # Phase 3: Price calculation + ranking
        ranked = await self._rank_results(available_ids, params)
        return ranked[:params.page_size]

    async def _geo_filter(self, params):
        """Elasticsearch geo_distance query with filters"""
        query = {
            "bool": {
                "must": [
                    {"term": {"status": "active"}},
                    {"range": {"max_guests": {"gte": params.guests}}},
                ],
                "filter": [
                    {
                        "geo_distance": {
                            "distance": f"{params.radius_km}km",
                            "location": {
                                "lat": params.latitude,
                                "lon": params.longitude
                            }
                        }
                    }
                ]
            }
        }
        # Add optional filters
        if params.price_min:
            query["bool"]["must"].append(
                {"range": {"base_price_cents": {"gte": params.price_min * 100}}}
            )
        if params.amenities:
            query["bool"]["must"].append(
                {"terms": {"amenities": params.amenities}}
            )
        
        results = await self.es.search(index="listings", body={"query": query, "size": 5000})
        return [hit["_id"] for hit in results["hits"]["hits"]]

    async def _check_availability_batch(self, listing_ids, check_in, check_out):
        """
        Redis bitmap approach:
        Each listing has a bitmap for the year: key = `avail:{listing_id}:{year}`
        Bit position = day of year (0-365)
        Bit value: 1 = available, 0 = blocked
        
        Check: BITCOUNT on the date range should equal number of nights
        """
        pipe = self.redis.pipeline()
        num_nights = (check_out - check_in).days
        
        for listing_id in listing_ids:
            year = check_in.year
            start_bit = check_in.timetuple().tm_yday - 1
            end_bit = start_bit + num_nights - 1
            
            # BITCOUNT counts set bits in byte range (approximate, need GETBIT loop for exact)
            # Better approach: use BITFIELD to get range
            key = f"avail:{listing_id}:{year}"
            for day_offset in range(num_nights):
                pipe.getbit(key, start_bit + day_offset)
        
        results = await pipe.execute()
        
        available = []
        idx = 0
        for listing_id in listing_ids:
            bits = results[idx:idx + num_nights]
            if all(b == 1 for b in bits):
                available.append(listing_id)
            idx += num_nights
        
        return available
```

**Index Strategy for Calendar Queries**:
```sql
-- Approach 1: Check NO blocked dates exist in range (fast with B-tree)
-- Returns listings that ARE available
SELECT listing_id FROM listings l
WHERE l.status = 'active'
AND ST_DWithin(l.geog, ST_MakePoint(-122.4, 37.8)::geography, 15000)
AND NOT EXISTS (
    SELECT 1 FROM listing_blocked_dates bd
    WHERE bd.listing_id = l.listing_id
    AND bd.start_date < '2024-06-20'  -- check_out
    AND bd.end_date > '2024-06-15'    -- check_in
);

-- Covering index for the blocked dates check
CREATE INDEX idx_blocked_overlap ON listing_blocked_dates(listing_id, start_date, end_date);

-- Approach 2: Materialized availability windows (pre-computed)
CREATE MATERIALIZED VIEW listing_availability_windows AS
SELECT listing_id,
       available_from,
       available_to,
       min_nights
FROM (
    -- Compute contiguous available windows per listing
    -- Gap-and-island SQL problem
) computed_windows;

CREATE INDEX idx_avail_windows ON listing_availability_windows(listing_id, available_from, available_to);
```

**Redis Calendar Bitmap Sync (Kafka Consumer)**:
```python
# Flink job to maintain Redis availability bitmaps
class CalendarSyncProcessor:
    """
    Consumes calendar.update events from Kafka
    Updates Redis bitmaps in real-time
    """
    
    async def process_event(self, event):
        if event.type == 'booking_confirmed':
            await self._block_dates(event.listing_id, event.check_in, event.check_out)
        elif event.type == 'booking_cancelled':
            await self._unblock_dates(event.listing_id, event.check_in, event.check_out)
        elif event.type == 'host_blocked':
            await self._block_dates(event.listing_id, event.start_date, event.end_date)
    
    async def _block_dates(self, listing_id, start_date, end_date):
        pipe = self.redis.pipeline()
        current = start_date
        while current < end_date:
            year = current.year
            day_of_year = current.timetuple().tm_yday - 1
            pipe.setbit(f"avail:{listing_id}:{year}", day_of_year, 0)
            current += timedelta(days=1)
        await pipe.execute()
```

### Deep Dive 2: Dynamic Pricing (Smart Pricing ML Model)

**Architecture**:
```
┌─────────────┐     ┌──────────────┐     ┌──────────────┐
│ Feature     │────▶│  ML Model    │────▶│  Price       │
│ Pipeline    │     │  (XGBoost +  │     │  Suggestion  │
│             │     │   Neural Net)│     │  Cache       │
└─────────────┘     └──────────────┘     └──────────────┘
      ▲                                        │
      │                                        ▼
┌─────────────┐                         ┌──────────────┐
│ Data Sources│                         │  Calendar    │
│ - Bookings  │                         │  Service     │
│ - Events    │                         │  (applies)   │
│ - Weather   │                         └──────────────┘
│ - Comps     │
└─────────────┘
```

**Feature Engineering**:
```python
class PricingFeatureExtractor:
    def extract_features(self, listing_id: str, target_date: date) -> dict:
        return {
            # Temporal features
            "day_of_week": target_date.weekday(),
            "month": target_date.month,
            "is_weekend": target_date.weekday() >= 5,
            "days_until": (target_date - date.today()).days,
            "is_holiday": self._check_holiday(target_date),
            
            # Demand signals
            "search_volume_7d": self._get_search_volume(listing_id, 7),
            "booking_rate_30d": self._get_booking_rate(listing_id, 30),
            "views_to_booking_ratio": self._get_conversion(listing_id),
            "area_occupancy_rate": self._get_area_occupancy(listing_id, target_date),
            
            # Listing attributes
            "base_price": self._get_base_price(listing_id),
            "avg_rating": self._get_rating(listing_id),
            "review_count": self._get_review_count(listing_id),
            "superhost": self._is_superhost(listing_id),
            "instant_book": self._is_instant_book(listing_id),
            
            # Comparable listings
            "comp_avg_price": self._get_comparable_avg(listing_id, target_date),
            "comp_availability_rate": self._get_comp_availability(listing_id, target_date),
            
            # Local events
            "event_score": self._get_event_impact(listing_id, target_date),
            "event_distance_km": self._get_nearest_event_distance(listing_id, target_date),
            
            # Seasonality
            "historical_occupancy_same_period": self._get_hist_occupancy(listing_id, target_date),
            "yoy_demand_change": self._get_yoy_change(listing_id, target_date),
        }

class DynamicPricingModel:
    def __init__(self):
        self.model = self._load_model()  # XGBoost ensemble
        self.bounds_model = self._load_bounds()  # Price bounds neural net
    
    def predict_optimal_price(self, listing_id: str, target_date: date) -> PriceSuggestion:
        features = self.feature_extractor.extract_features(listing_id, target_date)
        
        # Base prediction
        predicted_price = self.model.predict(features)
        
        # Apply bounds (host min/max, market reasonableness)
        bounds = self.bounds_model.get_bounds(listing_id)
        clamped_price = max(bounds.min_price, min(bounds.max_price, predicted_price))
        
        # Revenue optimization: price vs occupancy tradeoff
        # P(booking | price) curve
        booking_prob = self._estimate_booking_probability(listing_id, clamped_price, target_date)
        expected_revenue = clamped_price * booking_prob
        
        # Find price that maximizes expected revenue
        optimal = self._optimize_revenue(listing_id, target_date, bounds)
        
        return PriceSuggestion(
            suggested_price=optimal.price,
            confidence=optimal.confidence,
            expected_occupancy=optimal.booking_probability,
            factors=features
        )
```

**Kafka Configuration for Price Updates**:
```yaml
# Topic: pricing.suggestions
topic.pricing.suggestions:
  partitions: 32
  replication.factor: 3
  retention.ms: 604800000  # 7 days
  cleanup.policy: delete
  compression.type: lz4

# Consumer group config
consumer:
  group.id: pricing-suggestion-applier
  auto.offset.reset: latest
  max.poll.records: 500
  session.timeout.ms: 30000
```

### Deep Dive 3: Trust & Safety

**Identity Verification Pipeline**:
```python
class IdentityVerificationService:
    """Multi-step verification: ID document + selfie + liveness"""
    
    async def verify_identity(self, user_id: str, documents: VerificationDocs) -> VerificationResult:
        # Step 1: Document quality check
        doc_quality = await self.doc_processor.assess_quality(documents.id_photo)
        if doc_quality.score < 0.7:
            return VerificationResult(status='retry', reason='poor_image_quality')
        
        # Step 2: OCR + document authenticity
        doc_data = await self.ocr_service.extract(documents.id_photo)
        authenticity = await self.fraud_detector.check_document(documents.id_photo)
        
        # Step 3: Face match (ID photo vs selfie)
        face_match = await self.face_service.compare(
            documents.id_photo, documents.selfie_photo
        )
        
        # Step 4: Liveness detection
        liveness = await self.liveness_service.verify(documents.video_selfie)
        
        # Step 5: Watchlist / sanctions check
        watchlist_clear = await self.compliance.check_watchlist(doc_data.name, doc_data.dob)
        
        overall = self._compute_overall_score(doc_quality, authenticity, face_match, liveness)
        
        if overall.score >= 0.9 and watchlist_clear:
            await self._mark_verified(user_id, doc_data)
            return VerificationResult(status='verified')
        elif overall.score >= 0.6:
            return VerificationResult(status='manual_review')
        else:
            return VerificationResult(status='rejected', reason=overall.failure_reason)

class FraudDetectionEngine:
    """Real-time fraud scoring for bookings"""
    
    def score_booking(self, booking_request: BookingRequest) -> FraudScore:
        signals = {
            "new_account_days": self._account_age(booking_request.guest_id),
            "payment_risk": self._payment_risk_score(booking_request.payment_method),
            "velocity": self._booking_velocity(booking_request.guest_id),
            "geo_mismatch": self._check_geo_consistency(booking_request),
            "message_sentiment": self._analyze_messages(booking_request.conversation_id),
            "known_fraud_patterns": self._check_patterns(booking_request),
        }
        
        risk_score = self.fraud_model.predict(signals)
        
        if risk_score > 0.8:
            return FraudScore(action='block', score=risk_score)
        elif risk_score > 0.5:
            return FraudScore(action='additional_verification', score=risk_score)
        else:
            return FraudScore(action='allow', score=risk_score)
```

**Content Moderation Pipeline**:
```python
class ContentModerationPipeline:
    """Moderates listing photos, reviews, and messages"""
    
    async def moderate_photo(self, photo_url: str) -> ModerationResult:
        # Parallel checks
        results = await asyncio.gather(
            self.nsfw_detector.check(photo_url),
            self.quality_assessor.assess(photo_url),
            self.text_detector.extract_and_check(photo_url),  # personal info in photos
            self.authenticity_checker.check(photo_url),  # stock photos
        )
        
        nsfw, quality, text_issues, authenticity = results
        
        if nsfw.is_explicit:
            return ModerationResult(action='reject', reason='explicit_content')
        if not authenticity.is_original:
            return ModerationResult(action='flag', reason='possible_stock_photo')
        
        return ModerationResult(action='approve')
```

## 8. Component Optimization

### Search Performance
```python
# Elasticsearch index settings for optimal search
LISTING_INDEX_SETTINGS = {
    "settings": {
        "number_of_shards": 10,
        "number_of_replicas": 2,
        "refresh_interval": "5s",
        "analysis": {
            "analyzer": {
                "listing_analyzer": {
                    "type": "custom",
                    "tokenizer": "standard",
                    "filter": ["lowercase", "synonym", "stemmer"]
                }
            }
        }
    },
    "mappings": {
        "properties": {
            "location": {"type": "geo_point"},
            "title": {"type": "text", "analyzer": "listing_analyzer"},
            "base_price_cents": {"type": "integer"},
            "amenities": {"type": "keyword"},
            "status": {"type": "keyword"},
            "max_guests": {"type": "integer"},
            "avg_rating": {"type": "float"},
            "instant_book": {"type": "boolean"},
            "property_type": {"type": "keyword"},
            "room_type": {"type": "keyword"}
        }
    }
}
```

### Redis Caching Strategy
```python
# Cache hierarchy
CACHE_CONFIG = {
    "listing_detail": {"ttl": 300, "pattern": "listing:{id}"},
    "listing_calendar": {"ttl": 60, "pattern": "cal:{listing_id}:{month}"},
    "search_results": {"ttl": 30, "pattern": "search:{hash}"},
    "user_profile": {"ttl": 600, "pattern": "user:{id}"},
    "pricing_suggestion": {"ttl": 3600, "pattern": "price:{listing_id}:{date}"},
}

# Cache invalidation via Kafka events
class CacheInvalidator:
    async def handle_event(self, event):
        if event.type == 'listing_updated':
            await self.redis.delete(f"listing:{event.listing_id}")
            await self.invalidate_search_cache(event.listing_id)
        elif event.type == 'booking_confirmed':
            await self.redis.delete(f"cal:{event.listing_id}:*")
```

### Booking Service - Distributed Lock for Double-Booking Prevention
```python
class BookingService:
    async def create_booking(self, request: BookingRequest) -> Booking:
        lock_key = f"booking_lock:{request.listing_id}:{request.check_in}:{request.check_out}"
        
        # Acquire distributed lock (Redlock)
        lock = await self.redis.lock(lock_key, timeout=30)
        if not lock:
            raise ConflictError("Listing is being booked by another guest")
        
        try:
            # Double-check availability
            available = await self._check_availability(
                request.listing_id, request.check_in, request.check_out
            )
            if not available:
                raise UnavailableError("Dates no longer available")
            
            # Create booking in DB
            booking = await self._persist_booking(request)
            
            # Block dates
            await self._block_calendar_dates(request.listing_id, request.check_in, request.check_out, booking.id)
            
            # Process payment
            payment = await self.payment_service.charge(request.payment_method_id, booking.total_cents)
            
            # Emit event
            await self.kafka.produce('booking.events', BookingConfirmedEvent(booking))
            
            return booking
        except Exception as e:
            await self._rollback(booking)
            raise
        finally:
            await lock.release()
```

## 9. Observability

### Metrics (Prometheus)
```yaml
# Key metrics
airbnb_search_latency_seconds:
  type: histogram
  labels: [region, query_type]
  buckets: [0.05, 0.1, 0.25, 0.5, 1.0, 2.5]

airbnb_booking_total:
  type: counter
  labels: [status, listing_type, region]

airbnb_availability_cache_hit_ratio:
  type: gauge
  labels: [region]

airbnb_calendar_sync_lag_seconds:
  type: histogram
  labels: [source]

airbnb_pricing_model_inference_ms:
  type: histogram
  labels: [model_version]

airbnb_double_booking_attempts:
  type: counter
  labels: [region]
```

### Distributed Tracing
```
Search Request Trace:
API Gateway (2ms) → Search Service (450ms total)
  ├── ES Geo Query (80ms)
  ├── Redis Availability Check (120ms for 2000 listings)
  ├── Price Calculation (50ms)
  ├── Ranking Model (100ms)
  └── Response Assembly (10ms)
```

### Alerting Rules
```yaml
groups:
  - name: airbnb_critical
    rules:
      - alert: DoubleBookingDetected
        expr: rate(airbnb_double_booking_attempts[5m]) > 0
        severity: critical
        
      - alert: SearchLatencyHigh
        expr: histogram_quantile(0.99, airbnb_search_latency_seconds) > 2
        for: 5m
        severity: warning
        
      - alert: CalendarSyncLag
        expr: airbnb_calendar_sync_lag_seconds > 60
        for: 10m
        severity: critical
        
      - alert: BookingSuccessRateLow
        expr: rate(airbnb_booking_total{status="success"}[5m]) / rate(airbnb_booking_total[5m]) < 0.95
        severity: warning
```

### Logging Structure
```json
{
    "timestamp": "2024-06-15T10:30:00Z",
    "service": "booking-service",
    "trace_id": "abc123",
    "span_id": "def456",
    "level": "INFO",
    "event": "booking_created",
    "booking_id": "bk_789",
    "listing_id": "lst_456",
    "guest_id": "usr_123",
    "check_in": "2024-07-01",
    "check_out": "2024-07-05",
    "total_cents": 169200,
    "latency_ms": 340
}
```

## 10. Considerations

### Scaling Strategies
- **Search**: Shard Elasticsearch by geo-region; route queries to regional shards
- **Calendar**: Redis cluster with consistent hashing by listing_id
- **Bookings**: PostgreSQL sharded by listing_id (co-locate listing + bookings)
- **Photos**: S3 + CloudFront with regional edge caches
- **Messages**: DynamoDB with conversation_id partition key for infinite scale

### Consistency vs Availability Tradeoffs
- **Booking flow**: Strong consistency (CP) — cannot allow double-bookings
- **Search results**: Eventually consistent (AP) — slight staleness acceptable
- **Calendar display**: Eventually consistent with 2s propagation target
- **Reviews**: Eventually consistent with 14-day reveal window

### Failure Handling
- **Payment failure after booking**: Saga pattern with compensation (release dates)
- **Calendar sync failure**: Retry queue with exponential backoff + dead letter
- **Search degradation**: Fallback to cached results with staleness indicator

### Multi-Region Deployment
```
US-WEST (Primary for Americas)
EU-WEST (Primary for Europe/Africa)  
AP-SOUTHEAST (Primary for Asia-Pacific)

Cross-region replication:
- User data: Async replication (eventual consistency)
- Booking data: Sync replication to 2 regions (strong consistency)
- Search index: Independent per region (rebuilt from replicated DB)
```

### Cost Optimization
- Photo storage tiering: Hot (recent uploads) → Warm (>30 days) → Cold (unlisted)
- Search result caching: 30s TTL saves ~40% of ES queries
- Dynamic scaling: Scale down search cluster 50% during off-peak (2am-6am local)
- Spot instances for ML training; reserved for inference

## 11. Data Flow Diagrams

### Booking Flow State Machine
```
    ┌─────────┐    guest      ┌─────────┐   host     ┌───────────┐
    │  DRAFT  │───request────▶│ PENDING │──accept───▶│ CONFIRMED │
    └─────────┘               └────┬────┘            └─────┬─────┘
                                   │                       │
                              host │decline          check-in
                                   ▼                       ▼
                              ┌─────────┐           ┌──────────┐
                              │DECLINED │           │  ACTIVE  │
                              └─────────┘           └─────┬────┘
                                                          │
                                                    check-out
                                                          ▼
                              ┌───────────┐         ┌───────────┐
                              │ CANCELLED │◀────────│ COMPLETED │
                              └───────────┘  cancel └───────────┘
```

### Search Ranking Formula
```python
def compute_listing_score(listing, query, user):
    """Multi-factor ranking score"""
    score = 0.0
    
    # Quality signals (40%)
    score += 0.20 * normalize(listing.avg_rating, 3.0, 5.0)
    score += 0.10 * normalize(listing.review_count, 0, 200)
    score += 0.05 * (1.0 if listing.superhost else 0.0)
    score += 0.05 * listing.response_rate
    
    # Relevance signals (30%)
    score += 0.15 * geo_decay(listing.distance_km, query.radius_km)
    score += 0.10 * amenity_match_ratio(listing.amenities, query.amenities)
    score += 0.05 * price_fit_score(listing.price, query.price_range)
    
    # Conversion signals (20%)
    score += 0.10 * listing.click_through_rate
    score += 0.05 * listing.booking_conversion_rate
    score += 0.05 * listing.instant_book_boost
    
    # Personalization (10%)
    score += 0.05 * user_preference_match(listing, user.history)
    score += 0.05 * collaborative_filtering_score(listing, user)
    
    return score
```
