# Design Airline Reservation System

## 1. Functional Requirements

### Core Features
- **Flight Search**: One-way, round-trip, multi-city with connections and flexible dates
- **Fare Classes**: Economy/Business/First with sub-buckets (Y, B, M, H, Q, K...)
- **PNR Management**: Passenger Name Record creation, modification, cancellation
- **Seat Selection**: Aircraft seat map with paid/free seat selection
- **Check-in**: Online check-in 24-48h before departure
- **Boarding Pass**: Digital/print boarding pass with barcode
- **Frequent Flyer**: Miles earning/redemption, tier status, upgrades
- **Codeshare/Alliance**: Flights operated by partner airlines, shared inventory

### User Flows
1. Search flights → Select itinerary → Enter passenger details → Select fare → Pay → Get PNR
2. Manage booking → Add ancillaries (bags, meals, seats) → Check-in → Get boarding pass
3. Redeem miles → Search award flights → Book with miles + taxes

## 2. Non-Functional Requirements

| Requirement | Target |
|---|---|
| Search Latency | P99 < 3s (complex multi-leg) |
| Booking Consistency | Strong (no overselling beyond limits) |
| Availability | 99.99% for booking engine |
| PNR Access | < 500ms globally |
| Search Throughput | 20K searches/sec |
| Concurrent Bookings | 5K/sec during sales |
| Data Retention | PNR: 5 years, Financial: 7 years |
| GDS Integration | < 2s response to GDS queries |
| Regulatory | IATA standards (NDC, ONE Order) |

## 3. Capacity Estimation

### Storage
```
Flights: 200K flights/day × 365 × 500B = 36.5GB/year
Flight schedules: 500K routes × 2KB = 1GB
Fare rules: 10M fare basis codes × 5KB = 50GB
PNRs: 500M/year × 3KB = 1.5TB/year
Booking segments: 1B/year × 500B = 500GB/year
Passenger data: 800M passengers/year × 1KB = 800GB/year
Seat maps: 5K aircraft × 300 seats × 200B = 300MB
Inventory: 200K flights × 26 fare buckets × 50B = 260MB/day
```

### Throughput
```
Flight searches: 20K/s peak (holiday seasons)
Fare quotes: 50K/s (including meta-search engines)
PNR creates: 5K/s peak
Check-ins: 2K/s (24h before peak departure wave)
Seat map requests: 10K/s
Inventory updates: 100K/min (real-time yield management)
```

## 4. Data Modeling

### Full Database Schemas

```sql
-- Airlines
CREATE TABLE airlines (
    airline_code CHAR(2) PRIMARY KEY, -- IATA code: AA, UA, LH
    icao_code CHAR(3),
    name VARCHAR(200) NOT NULL,
    alliance VARCHAR(30), -- star_alliance, oneworld, skyteam
    country_code CHAR(2),
    hub_airports CHAR(3)[],
    is_active BOOLEAN DEFAULT TRUE
);

-- Airports
CREATE TABLE airports (
    airport_code CHAR(3) PRIMARY KEY, -- IATA: JFK, LAX, LHR
    icao_code CHAR(4),
    name VARCHAR(200) NOT NULL,
    city VARCHAR(100) NOT NULL,
    country_code CHAR(2) NOT NULL,
    timezone VARCHAR(50) NOT NULL,
    latitude DECIMAL(10, 7),
    longitude DECIMAL(10, 7),
    terminal_count INT,
    is_hub BOOLEAN DEFAULT FALSE
);

-- Aircraft types
CREATE TABLE aircraft_types (
    aircraft_code VARCHAR(10) PRIMARY KEY, -- 73H, 789, 388
    name VARCHAR(100), -- Boeing 737-800, B787-9
    manufacturer VARCHAR(50),
    seat_capacity_economy INT,
    seat_capacity_business INT,
    seat_capacity_first INT,
    range_km INT,
    is_widebody BOOLEAN
);

-- Flight schedules (template, not specific dates)
CREATE TABLE flight_schedules (
    schedule_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    airline_code CHAR(2) NOT NULL REFERENCES airlines(airline_code),
    flight_number VARCHAR(6) NOT NULL, -- AA1234
    departure_airport CHAR(3) NOT NULL REFERENCES airports(airport_code),
    arrival_airport CHAR(3) NOT NULL REFERENCES airports(airport_code),
    departure_time TIME NOT NULL,
    arrival_time TIME NOT NULL,
    duration_minutes INT NOT NULL,
    days_of_week INT NOT NULL, -- bitmask: Mon=1, Tue=2, ...
    aircraft_code VARCHAR(10) REFERENCES aircraft_types(aircraft_code),
    effective_from DATE NOT NULL,
    effective_to DATE NOT NULL,
    is_codeshare BOOLEAN DEFAULT FALSE,
    operating_carrier CHAR(2), -- if codeshare, who operates
    operating_flight_number VARCHAR(6),
    UNIQUE(airline_code, flight_number, effective_from)
);
CREATE INDEX idx_schedule_route ON flight_schedules(departure_airport, arrival_airport, days_of_week);

-- Flight instances (specific date)
CREATE TABLE flights (
    flight_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    schedule_id UUID REFERENCES flight_schedules(schedule_id),
    airline_code CHAR(2) NOT NULL,
    flight_number VARCHAR(6) NOT NULL,
    departure_airport CHAR(3) NOT NULL,
    arrival_airport CHAR(3) NOT NULL,
    departure_datetime TIMESTAMP WITH TIME ZONE NOT NULL,
    arrival_datetime TIMESTAMP WITH TIME ZONE NOT NULL,
    flight_date DATE NOT NULL,
    aircraft_code VARCHAR(10),
    aircraft_registration VARCHAR(10),
    status VARCHAR(20) DEFAULT 'scheduled',
    -- scheduled, boarding, departed, in_air, landed, arrived, cancelled, diverted
    gate_departure VARCHAR(10),
    gate_arrival VARCHAR(10),
    terminal_departure VARCHAR(5),
    terminal_arrival VARCHAR(5),
    actual_departure TIMESTAMP WITH TIME ZONE,
    actual_arrival TIMESTAMP WITH TIME ZONE,
    delay_minutes INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_flights_route_date ON flights(departure_airport, arrival_airport, flight_date);
CREATE INDEX idx_flights_number_date ON flights(airline_code, flight_number, flight_date);

-- Fare classes / booking classes (RBD - Reservation Booking Designator)
CREATE TABLE fare_classes (
    class_code CHAR(1) PRIMARY KEY, -- Y, J, F, B, M, H, Q, K, L, etc.
    cabin VARCHAR(20) NOT NULL, -- first, business, premium_economy, economy
    name VARCHAR(50),
    priority INT, -- higher = more expensive/flexible
    upgradeable BOOLEAN DEFAULT TRUE,
    mileage_earn_percent INT DEFAULT 100,
    change_fee_usd INT DEFAULT 0,
    cancel_fee_usd INT DEFAULT 0,
    refundable BOOLEAN DEFAULT TRUE,
    advance_seat_selection BOOLEAN DEFAULT TRUE,
    lounge_access BOOLEAN DEFAULT FALSE,
    priority_boarding BOOLEAN DEFAULT FALSE,
    checked_bags_included INT DEFAULT 0
);

-- Fare rules (complex rule engine)
CREATE TABLE fare_rules (
    fare_basis_code VARCHAR(15) PRIMARY KEY, -- YOW, BXRNUS, MHXAP14
    fare_class CHAR(1) NOT NULL REFERENCES fare_classes(class_code),
    origin_area VARCHAR(10), -- geographic zone
    destination_area VARCHAR(10),
    one_way_round_trip CHAR(1), -- O, R
    advance_purchase_days INT, -- min days before departure
    min_stay_days INT,
    max_stay_days INT,
    saturday_night_required BOOLEAN DEFAULT FALSE,
    blackout_dates DATE[],
    seasonality VARCHAR(10), -- H (high), L (low), S (shoulder)
    combinability_rule VARCHAR(30), -- can combine with other fares?
    valid_carrier CHAR(2)[],
    routing_restrictions TEXT, -- allowed routing
    penalties JSONB, -- change/cancel penalties
    created_at TIMESTAMP DEFAULT NOW()
);

-- Inventory (available seats per fare class per flight)
CREATE TABLE flight_inventory (
    flight_id UUID NOT NULL REFERENCES flights(flight_id),
    class_code CHAR(1) NOT NULL REFERENCES fare_classes(class_code),
    authorized INT NOT NULL, -- total seats allocated to this class
    sold INT DEFAULT 0,
    available INT GENERATED ALWAYS AS (authorized - sold) STORED,
    waitlisted INT DEFAULT 0,
    revenue_value DECIMAL(10,2), -- bid price for revenue management
    status VARCHAR(10) DEFAULT 'open', -- open, closed, waitlist
    updated_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (flight_id, class_code)
);
CREATE INDEX idx_inventory_available ON flight_inventory(flight_id, class_code) WHERE status = 'open';

-- PNR (Passenger Name Record)
CREATE TABLE pnrs (
    pnr_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    record_locator CHAR(6) UNIQUE NOT NULL, -- ABCDEF
    creating_airline CHAR(2) NOT NULL,
    agency_id VARCHAR(20),
    contact_email VARCHAR(255),
    contact_phone VARCHAR(30),
    num_passengers INT NOT NULL,
    status VARCHAR(20) DEFAULT 'confirmed',
    -- confirmed, ticketed, cancelled, flown, archived
    total_fare_cents INT,
    currency CHAR(3) DEFAULT 'USD',
    payment_method VARCHAR(30),
    ticketing_deadline TIMESTAMP, -- must ticket by this time
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    version INT DEFAULT 1 -- optimistic locking
);
CREATE INDEX idx_pnr_locator ON pnrs(record_locator);
CREATE INDEX idx_pnr_status ON pnrs(status) WHERE status IN ('confirmed', 'ticketed');

-- PNR passengers
CREATE TABLE pnr_passengers (
    passenger_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pnr_id UUID NOT NULL REFERENCES pnrs(pnr_id),
    title VARCHAR(10), -- MR, MRS, MS, DR
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    date_of_birth DATE,
    gender CHAR(1),
    passport_number VARCHAR(20),
    passport_expiry DATE,
    passport_country CHAR(2),
    frequent_flyer_number VARCHAR(20),
    frequent_flyer_airline CHAR(2),
    passenger_type CHAR(3) DEFAULT 'ADT', -- ADT, CHD, INF
    meal_preference VARCHAR(10), -- VGML, AVML, KSML
    special_assistance VARCHAR(20)[], -- WCHR, BLND, DEAF
    ticket_number VARCHAR(15), -- 13-digit ticket number
    e_ticket_issued BOOLEAN DEFAULT FALSE
);
CREATE INDEX idx_passengers_pnr ON pnr_passengers(pnr_id);
CREATE INDEX idx_passengers_name ON pnr_passengers(last_name, first_name);

-- PNR segments (flight legs)
CREATE TABLE pnr_segments (
    segment_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pnr_id UUID NOT NULL REFERENCES pnrs(pnr_id),
    segment_number INT NOT NULL,
    flight_id UUID NOT NULL REFERENCES flights(flight_id),
    airline_code CHAR(2) NOT NULL,
    flight_number VARCHAR(6) NOT NULL,
    departure_airport CHAR(3) NOT NULL,
    arrival_airport CHAR(3) NOT NULL,
    departure_datetime TIMESTAMP WITH TIME ZONE NOT NULL,
    arrival_datetime TIMESTAMP WITH TIME ZONE NOT NULL,
    booking_class CHAR(1) NOT NULL,
    cabin VARCHAR(20),
    fare_basis VARCHAR(15),
    status CHAR(2) DEFAULT 'HK', -- HK=confirmed, UC=unconfirmed, XX=cancelled
    seat_number VARCHAR(4),
    checked_in BOOLEAN DEFAULT FALSE,
    boarding_pass_issued BOOLEAN DEFAULT FALSE,
    UNIQUE(pnr_id, segment_number)
);
CREATE INDEX idx_segments_pnr ON pnr_segments(pnr_id, segment_number);
CREATE INDEX idx_segments_flight ON pnr_segments(flight_id) WHERE status = 'HK';

-- SSR (Special Service Requests)
CREATE TABLE pnr_ssr (
    ssr_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pnr_id UUID NOT NULL REFERENCES pnrs(pnr_id),
    passenger_id UUID REFERENCES pnr_passengers(passenger_id),
    segment_id UUID REFERENCES pnr_segments(segment_id),
    ssr_code VARCHAR(4) NOT NULL, -- WCHR, MEAL, SEAT, OTHS
    text TEXT,
    status VARCHAR(10) DEFAULT 'HK',
    created_at TIMESTAMP DEFAULT NOW()
);

-- Frequent flyer accounts
CREATE TABLE frequent_flyer (
    ff_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    member_number VARCHAR(20) UNIQUE NOT NULL,
    airline_code CHAR(2) NOT NULL,
    passenger_name VARCHAR(200) NOT NULL,
    email VARCHAR(255),
    tier VARCHAR(20) DEFAULT 'basic', -- basic, silver, gold, platinum
    miles_balance INT DEFAULT 0,
    lifetime_miles INT DEFAULT 0,
    qualifying_miles_ytd INT DEFAULT 0,
    qualifying_segments_ytd INT DEFAULT 0,
    tier_expiry_date DATE,
    enrolled_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_ff_member ON frequent_flyer(member_number);

-- Seat maps (per aircraft configuration)
CREATE TABLE seat_maps (
    aircraft_code VARCHAR(10) NOT NULL,
    configuration_id VARCHAR(20) NOT NULL, -- same aircraft, different configs
    seat_number VARCHAR(4) NOT NULL, -- 1A, 12F, 45K
    cabin VARCHAR(20) NOT NULL,
    row_number INT NOT NULL,
    column_letter CHAR(1) NOT NULL,
    seat_type VARCHAR(20), -- window, middle, aisle
    seat_class VARCHAR(20), -- standard, extra_legroom, bulkhead, exit_row
    is_wing BOOLEAN DEFAULT FALSE,
    is_exit_row BOOLEAN DEFAULT FALSE,
    has_power BOOLEAN DEFAULT FALSE,
    recline_limited BOOLEAN DEFAULT FALSE,
    price_tier VARCHAR(20), -- free, preferred, extra_legroom (for pricing)
    PRIMARY KEY (aircraft_code, configuration_id, seat_number)
);

-- Flight seat assignments
CREATE TABLE flight_seat_assignments (
    flight_id UUID NOT NULL REFERENCES flights(flight_id),
    seat_number VARCHAR(4) NOT NULL,
    pnr_id UUID REFERENCES pnrs(pnr_id),
    passenger_id UUID REFERENCES pnr_passengers(passenger_id),
    assignment_type VARCHAR(20), -- selected, assigned, upgraded
    assigned_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (flight_id, seat_number)
);
CREATE INDEX idx_seat_assignments_pnr ON flight_seat_assignments(pnr_id);
```

## 5. High-Level Design (HLD)

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                            CLIENT CHANNELS                                        │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌───────────────┐        │
│  │ Website  │ │  Mobile  │ │  GDS     │ │  Meta-   │ │   Travel      │        │
│  │  (B2C)   │ │   App    │ │(Amadeus/ │ │  Search  │ │   Agent       │        │
│  │          │ │          │ │Sabre/TF) │ │(Kayak/GF)│ │   Portal      │        │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘ └──────┬────────┘        │
└───────┼────────────┼────────────┼────────────┼───────────────┼──────────────────┘
        │            │            │            │               │
        ▼            ▼            ▼            ▼               ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│                        API GATEWAY & NDC LAYER                                    │
│  ┌───────────┐  ┌───────────┐  ┌───────────────┐  ┌──────────────────┐        │
│  │   Kong    │  │   Auth    │  │  NDC/EDIFACT  │  │   Rate Limiter   │        │
│  │  Gateway  │  │  (OAuth2) │  │   Translator  │  │   (per channel)  │        │
│  └───────────┘  └───────────┘  └───────────────┘  └──────────────────┘        │
└───────────────────────────────────────┬──────────────────────────────────────────┘
                                        │
      ┌──────────────┬──────────────────┼──────────────────┬──────────────┐
      ▼              ▼                  ▼                  ▼              ▼
┌───────────┐ ┌───────────┐ ┌──────────────┐ ┌────────────┐ ┌───────────────┐
│  Search   │ │ Inventory │ │   Booking    │ │  Revenue   │ │   Check-in    │
│  (Fare    │ │  Control  │ │  (PNR Mgmt)  │ │ Management │ │  & Boarding   │
│   Shop)   │ │           │ │              │ │            │ │               │
│           │ │- Bucket   │ │- Create PNR  │ │- Bid price │ │- Check-in     │
│- Route    │ │  mgmt     │ │- Modify      │ │- Forecast  │ │- Seat assign  │
│  graph    │ │- Sell/cnl │ │- Cancel      │ │- Overbook  │ │- Boarding pass│
│- Pricing  │ │- Waitlist │ │- Split/merge │ │- Optimizer │ │- Gate mgmt    │
│- Avail    │ │- Codeshare│ │- Ticket      │ │            │ │               │
└─────┬─────┘ └─────┬─────┘ └──────┬───────┘ └─────┬──────┘ └───────┬───────┘
      │              │              │               │                │
      ▼              ▼              ▼               ▼                ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│                          DATA LAYER                                                │
│                                                                                    │
│ ┌──────────────┐ ┌──────────────┐ ┌────────────┐ ┌──────────────────┐           │
│ │  PostgreSQL  │ │    Redis     │ │   Kafka    │ │  Elasticsearch   │           │
│ │  (Sharded)   │ │   Cluster    │ │            │ │                  │           │
│ │              │ │              │ │            │ │- Flight search   │           │
│ │- PNRs       │ │- Inventory   │ │- pnr.evts  │ │- Schedule search │           │
│ │- Passengers │ │  counters    │ │- inv.upd   │ │- Fare search     │           │
│ │- Tickets    │ │- Seat locks  │ │- checkin   │ │                  │           │
│ │- Fare rules │ │- Session     │ │- revenue   │ └──────────────────┘           │
│ └──────────────┘ │- Fare cache │ │- notif     │                                │
│                  └──────────────┘ └────────────┘                                │
│ ┌──────────────┐ ┌──────────────┐ ┌────────────┐                               │
│ │   Graph DB   │ │   ClickHouse │ │   S3       │                               │
│ │  (Route net) │ │ (Analytics)  │ │  (Tickets) │                               │
│ └──────────────┘ └──────────────┘ └────────────┘                               │
└──────────────────────────────────────────────────────────────────────────────────┘
```

## 6. Low-Level Design (LLD) - APIs

### Flight Search API
```
POST /api/v1/flights/search
Request:
{
    "trip_type": "round_trip",  // one_way, round_trip, multi_city
    "segments": [
        {
            "origin": "JFK",
            "destination": "LHR",
            "date": "2024-08-15",
            "flexible_dates": true  // ±3 days
        },
        {
            "origin": "LHR",
            "destination": "JFK",
            "date": "2024-08-22"
        }
    ],
    "passengers": {"adults": 2, "children": 1, "infants": 0},
    "cabin": "economy",  // economy, premium_economy, business, first
    "max_stops": 1,
    "preferred_airlines": ["AA", "BA"],
    "max_price": 2000,
    "currency": "USD",
    "include_nearby_airports": true
}

Response:
{
    "search_id": "srch_xyz789",
    "outbound": [
        {
            "offer_id": "off_001",
            "itinerary": [
                {
                    "flight": "AA100",
                    "airline": "American Airlines",
                    "aircraft": "Boeing 777-300ER",
                    "departure": {"airport": "JFK", "terminal": "8", "time": "2024-08-15T19:00:00-04:00"},
                    "arrival": {"airport": "LHR", "terminal": "5", "time": "2024-08-16T07:00:00+01:00"},
                    "duration_minutes": 420,
                    "cabin": "economy",
                    "booking_class": "M",
                    "fare_basis": "MHXAP14",
                    "seats_remaining": 4
                }
            ],
            "total_duration_minutes": 420,
            "stops": 0,
            "pricing": {
                "per_adult": {"base": 450, "taxes": 112, "total": 562},
                "per_child": {"base": 340, "taxes": 112, "total": 452},
                "grand_total": 1576,
                "currency": "USD"
            },
            "fare_rules_summary": {
                "refundable": false,
                "changeable": true,
                "change_fee": 200,
                "advance_purchase": "14 days",
                "baggage": {"carry_on": "1 × 7kg", "checked": "1 × 23kg"}
            },
            "fare_brand": "Main Cabin"
        }
    ],
    "flexible_dates_grid": {
        "2024-08-13": 523,
        "2024-08-14": 498,
        "2024-08-15": 562,
        "2024-08-16": 587,
        "2024-08-17": 612
    }
}
```

### Create Booking (PNR) API
```
POST /api/v1/bookings
Request:
{
    "offer_ids": ["off_001", "off_002"],  // outbound + return
    "passengers": [
        {
            "type": "ADT",
            "title": "MR",
            "first_name": "JOHN",
            "last_name": "SMITH",
            "date_of_birth": "1985-03-15",
            "passport": {"number": "AB1234567", "expiry": "2028-05-20", "country": "US"},
            "frequent_flyer": {"airline": "AA", "number": "1234567890"},
            "meal": "VGML",
            "contact": {"email": "john@example.com", "phone": "+12125551234"}
        }
    ],
    "payment": {
        "method": "card",
        "card_token": "tok_stripe_abc"
    },
    "ancillaries": {
        "seats": [{"segment": 0, "passenger": 0, "seat": "14A"}],
        "bags": [{"segment": 0, "passenger": 0, "type": "extra_checked", "weight": "23kg"}]
    }
}

Response:
{
    "pnr_id": "pnr_abc123",
    "record_locator": "XKWM7F",
    "status": "confirmed",
    "passengers": [
        {"name": "SMITH/JOHN MR", "ticket_number": "0011234567890", "seat": "14A"}
    ],
    "segments": [
        {
            "flight": "AA100",
            "date": "2024-08-15",
            "route": "JFK → LHR",
            "departure": "19:00",
            "arrival": "07:00+1",
            "class": "M",
            "status": "HK" // confirmed
        }
    ],
    "pricing": {
        "total": 1576,
        "currency": "USD",
        "breakdown": {
            "base_fare": 1240,
            "taxes_fees": 336,
            "ancillaries": 0
        }
    },
    "ticketing_deadline": "2024-08-01T23:59:00Z",
    "frequent_flyer_miles": 6920
}
```

### Check-in API
```
POST /api/v1/checkin
Request:
{
    "record_locator": "XKWM7F",
    "last_name": "SMITH",
    "segment_number": 0,
    "passengers": [
        {
            "passenger_id": "pax_001",
            "travel_document": {"type": "passport", "number": "AB1234567"},
            "seat_preference": "window"
        }
    ]
}

Response:
{
    "status": "checked_in",
    "boarding_pass": {
        "passenger": "SMITH/JOHN MR",
        "flight": "AA100",
        "date": "15AUG",
        "route": "JFK → LHR",
        "gate": "B47",
        "boarding_time": "18:15",
        "seat": "14A",
        "class": "M",
        "group": "4",
        "sequence": "0087",
        "barcode_data": "M1SMITH/JOHN MR   EABCDEF JFKLHRAA 0100 227M014A0087 ...",
        "barcode_url": "https://cdn.airline.com/bp/XKWM7F_0.pkpass"
    }
}
```

## 7. Deep Dives

### Deep Dive 1: Fare Search Optimization (ITA-Style Graph Search)

**Problem**: Finding the cheapest itinerary across thousands of possible routes and millions of fare combinations. JFK→Tokyo might have 50+ routing options with different fare rules.

```python
class FareSearchEngine:
    """
    ITA Matrix-style fare search using graph-based approach.
    
    Key insight: Separate routing from pricing.
    1. Find valid routings (graph traversal)
    2. For each routing, find applicable fares
    3. Apply combinability rules
    4. Return cheapest valid combinations
    """
    
    def __init__(self, route_graph, fare_index, inventory_service):
        self.route_graph = route_graph  # Neo4j or in-memory graph
        self.fare_index = fare_index    # Pre-indexed fare rules
        self.inventory = inventory_service
    
    async def search(self, origin: str, destination: str, date: date,
                     passengers: PassengerCount, cabin: str, max_stops: int) -> List[Offer]:
        
        # Phase 1: Find valid routings (Dijkstra/BFS on route graph)
        routings = await self._find_routings(origin, destination, date, max_stops)
        # Returns: [["JFK-LHR"], ["JFK-BOS-LHR"], ["JFK-ORD-LHR"], ...]
        
        # Phase 2: For each routing, find available flights
        flight_options = await self._find_flights_for_routings(routings, date)
        
        # Phase 3: Check inventory availability per fare class
        priced_options = await self._price_options(flight_options, passengers, cabin)
        
        # Phase 4: Apply fare rules and combinability
        valid_offers = self._apply_fare_rules(priced_options, date)
        
        # Phase 5: Sort and return top N
        valid_offers.sort(key=lambda o: o.total_price)
        return valid_offers[:50]
    
    async def _find_routings(self, origin, destination, date, max_stops):
        """
        Graph traversal to find valid routings.
        Constraints: max connections, min connection time, max total time
        """
        routings = []
        
        # BFS with pruning
        queue = deque([(origin, [origin], 0)])  # (current, path, stops)
        
        while queue:
            current, path, stops = queue.popleft()
            
            if current == destination:
                routings.append(path)
                continue
            
            if stops >= max_stops + 1:
                continue
            
            # Get connecting airports
            neighbors = self.route_graph.get_connections(current, date)
            for next_airport in neighbors:
                if next_airport not in path:  # no circles
                    # Check minimum connection time
                    if self._valid_connection(current, next_airport, path):
                        queue.append((next_airport, path + [next_airport], stops + 1))
        
        return routings
    
    async def _price_options(self, flight_options, passengers, cabin):
        """
        For each flight combination, find cheapest available fare class.
        Uses fare basis code lookup + availability check.
        """
        priced = []
        
        for option in flight_options:
            best_fare = None
            
            # Get applicable fare basis codes for this route
            fares = self.fare_index.get_fares(
                origin=option.origin,
                destination=option.destination,
                cabin=cabin,
                travel_date=option.date
            )
            
            # Sort by price (cheapest first)
            fares.sort(key=lambda f: f.amount)
            
            for fare in fares:
                # Check availability in fare's booking class
                avail = await self.inventory.check_availability(
                    option.flight_id, fare.booking_class
                )
                if avail >= passengers.total:
                    # Check fare rule validity
                    if self._fare_rules_satisfied(fare, option):
                        best_fare = fare
                        break
            
            if best_fare:
                priced.append(PricedOption(option=option, fare=best_fare))
        
        return priced
    
    def _fare_rules_satisfied(self, fare, option) -> bool:
        """Check advance purchase, min/max stay, blackouts, etc."""
        today = date.today()
        travel_date = option.date
        
        # Advance purchase
        if fare.advance_purchase_days:
            if (travel_date - today).days < fare.advance_purchase_days:
                return False
        
        # Blackout dates
        if travel_date in fare.blackout_dates:
            return False
        
        # Day of week restriction
        if fare.valid_days and travel_date.weekday() not in fare.valid_days:
            return False
        
        return True

class RoutingGraph:
    """Pre-built graph of all airline routes for fast traversal"""
    
    def __init__(self):
        # Adjacency list: airport -> [(airport, flight_info)]
        self.graph = defaultdict(list)
        self.min_connection_times = {}  # (airport, terminal_pair) -> minutes
    
    def build_from_schedules(self, schedules):
        """Build routing graph from flight schedules"""
        for schedule in schedules:
            self.graph[schedule.departure].append(RouteEdge(
                destination=schedule.arrival,
                airline=schedule.airline_code,
                departure_time=schedule.departure_time,
                arrival_time=schedule.arrival_time,
                days=schedule.days_of_week
            ))
    
    def get_connections(self, airport: str, date: date) -> List[str]:
        """Get all airports reachable from this airport on given date"""
        day_of_week = date.weekday()
        return [
            edge.destination 
            for edge in self.graph[airport] 
            if day_of_week in edge.days
        ]
```

### Deep Dive 2: Inventory Control (Revenue Management)

**Problem**: An aircraft has 180 economy seats but 26 fare classes (Y, B, M, H, Q, K, L...). How many seats to allocate to each class to maximize revenue?

```python
class RevenueManagementSystem:
    """
    EMSR-b (Expected Marginal Seat Revenue) algorithm for nested inventory control.
    
    Nesting: Higher fare classes can use lower class allocations.
    If Y (full fare) has auth=10, B has auth=20, then B class actually has 30 seats
    (10 Y-allocated that B can overflow into + 20 B-allocated).
    
    Bid price: Minimum fare acceptable to sell a seat = opportunity cost of that seat.
    """
    
    def __init__(self, demand_forecaster, optimizer):
        self.forecaster = demand_forecaster
        self.optimizer = optimizer
    
    async def optimize_flight(self, flight_id: str):
        """Re-optimize inventory allocations for a flight"""
        flight = await self.get_flight(flight_id)
        days_to_departure = (flight.departure_date - date.today()).days
        
        # Forecast demand per fare class
        demand_forecasts = await self.forecaster.forecast(flight_id, days_to_departure)
        # Returns: {class_code: (mean_demand, std_dev)}
        
        # Current bookings
        current_bookings = await self.get_current_bookings(flight_id)
        
        # Calculate optimal protection levels using EMSR-b
        protections = self._emsr_b(demand_forecasts, flight.capacity)
        
        # Convert to booking limits (authorized seats)
        await self._apply_protections(flight_id, protections)
    
    def _emsr_b(self, demand: Dict[str, Tuple[float, float]], capacity: int) -> Dict[str, int]:
        """
        EMSR-b algorithm:
        For each class j, protect seats from lower classes if:
        P(demand_j > protection_j) × fare_j > fare_{j+1}
        
        Where fare classes are ordered: Y > B > M > H > Q > K > L
        """
        classes = sorted(demand.keys(), key=lambda c: self.get_fare(c), reverse=True)
        protections = {}
        
        remaining_capacity = capacity
        
        for i, fare_class in enumerate(classes[:-1]):
            fare_i = self.get_fare(fare_class)
            fare_next = self.get_fare(classes[i + 1])
            
            mean_demand, std_demand = demand[fare_class]
            
            # Find protection level where:
            # P(demand > protection) = fare_next / fare_i
            critical_ratio = fare_next / fare_i
            
            # Using inverse normal distribution
            from scipy.stats import norm
            z = norm.ppf(1 - critical_ratio)
            protection = int(mean_demand + z * std_demand)
            protection = max(0, min(protection, remaining_capacity))
            
            protections[fare_class] = protection
            remaining_capacity -= protection
        
        # Lowest class gets remaining
        protections[classes[-1]] = remaining_capacity
        return protections
    
    async def get_bid_price(self, flight_id: str) -> float:
        """
        Bid price = minimum fare to accept a booking.
        If bid price is $300, don't sell any fare below $300.
        Used for real-time sell/no-sell decisions.
        """
        flight = await self.get_flight(flight_id)
        days_to_departure = (flight.departure_date - date.today()).days
        
        remaining_seats = flight.capacity - flight.sold
        
        # Bid price increases as:
        # - fewer seats remain
        # - closer to departure
        # - higher forecasted demand
        
        demand_forecast = await self.forecaster.forecast_total(flight_id, days_to_departure)
        
        # If expected remaining demand > remaining seats, bid price goes up
        demand_to_come = demand_forecast.mean - flight.sold
        load_factor_expected = (flight.sold + demand_to_come) / flight.capacity
        
        if load_factor_expected > 0.95:
            # Very high demand - only sell premium fares
            return self.get_fare('M')  # Set floor at M class
        elif load_factor_expected > 0.85:
            return self.get_fare('Q')
        else:
            return self.get_fare('L')  # Accept cheap fares
    
    async def should_sell(self, flight_id: str, fare_class: str, fare_amount: float) -> bool:
        """Real-time sell decision"""
        bid_price = await self.get_bid_price(flight_id)
        
        if fare_amount >= bid_price:
            # Check if class is open (has available seats in nested bucket)
            available = await self.inventory.check_availability(flight_id, fare_class)
            return available > 0
        
        return False
```

### Deep Dive 3: PNR State Management

```python
class PNRStateMachine:
    """
    PNR has complex state transitions with SSR/OSI messages.
    
    States: DRAFT → CONFIRMED → TICKETED → CHECKED_IN → FLOWN → ARCHIVED
                 ↓ (cancel)     ↓ (cancel)
              CANCELLED       REFUNDED
    
    Each state change triggers inventory updates, notifications, and partner sync.
    """
    
    VALID_TRANSITIONS = {
        'DRAFT': ['CONFIRMED', 'CANCELLED'],
        'CONFIRMED': ['TICKETED', 'CANCELLED', 'MODIFIED'],
        'TICKETED': ['CHECKED_IN', 'CANCELLED', 'REFUNDED', 'MODIFIED'],
        'MODIFIED': ['TICKETED', 'CANCELLED'],
        'CHECKED_IN': ['BOARDED', 'NO_SHOW'],
        'BOARDED': ['FLOWN'],
        'FLOWN': ['ARCHIVED'],
        'CANCELLED': ['ARCHIVED'],
        'REFUNDED': ['ARCHIVED'],
    }
    
    async def transition(self, pnr_id: str, new_status: str, actor: str, reason: str = None):
        """Atomic state transition with optimistic locking"""
        async with self.db.transaction() as tx:
            # Fetch with lock
            pnr = await tx.fetch_one(
                "SELECT * FROM pnrs WHERE pnr_id = $1 FOR UPDATE", pnr_id
            )
            
            # Validate transition
            if new_status not in self.VALID_TRANSITIONS.get(pnr.status, []):
                raise InvalidTransition(f"Cannot move from {pnr.status} to {new_status}")
            
            # Execute transition side-effects
            await self._execute_side_effects(tx, pnr, new_status, actor)
            
            # Update status
            await tx.execute(
                "UPDATE pnrs SET status = $1, version = version + 1, updated_at = NOW() WHERE pnr_id = $2 AND version = $3",
                new_status, pnr_id, pnr.version
            )
            
            # Emit event
            await self.kafka.produce('pnr.events', {
                'pnr_id': pnr_id,
                'record_locator': pnr.record_locator,
                'old_status': pnr.status,
                'new_status': new_status,
                'actor': actor,
                'reason': reason,
                'timestamp': datetime.utcnow().isoformat()
            })
    
    async def _execute_side_effects(self, tx, pnr, new_status, actor):
        """Side effects for each transition"""
        if new_status == 'CANCELLED':
            # Release inventory
            for segment in await self._get_segments(tx, pnr.pnr_id):
                await self.inventory.release(segment.flight_id, segment.booking_class, 1)
            # Calculate refund
            refund = await self._calculate_refund(pnr)
            if refund > 0:
                await self.payment_service.refund(pnr.payment_id, refund)
        
        elif new_status == 'TICKETED':
            # Issue e-tickets
            for passenger in await self._get_passengers(tx, pnr.pnr_id):
                ticket_number = await self._issue_ticket(passenger, pnr)
                await tx.execute(
                    "UPDATE pnr_passengers SET ticket_number = $1, e_ticket_issued = TRUE WHERE passenger_id = $2",
                    ticket_number, passenger.passenger_id
                )
        
        elif new_status == 'CHECKED_IN':
            # Assign seat if not already assigned
            # Generate boarding pass data
            pass

class PNRModificationService:
    """Handles complex PNR modifications (date changes, route changes, name corrections)"""
    
    async def change_dates(self, pnr_id: str, segment_idx: int, new_date: date):
        """Change flight date - involves re-pricing and inventory swap"""
        pnr = await self.get_pnr(pnr_id)
        old_segment = pnr.segments[segment_idx]
        
        # Find new flight on new date
        new_flight = await self.find_flight(
            old_segment.airline_code, old_segment.flight_number, new_date
        )
        if not new_flight:
            raise FlightNotFound(f"No flight on {new_date}")
        
        # Check availability on new flight
        avail = await self.inventory.check_availability(new_flight.flight_id, old_segment.booking_class)
        if avail < pnr.num_passengers:
            raise NoAvailability()
        
        # Calculate fare difference
        fare_diff = await self._calculate_fare_difference(pnr, old_segment, new_flight)
        change_fee = self._get_change_fee(old_segment.fare_basis)
        
        async with self.db.transaction() as tx:
            # Release old inventory
            await self.inventory.release(old_segment.flight_id, old_segment.booking_class, pnr.num_passengers)
            
            # Sell new inventory
            await self.inventory.sell(new_flight.flight_id, old_segment.booking_class, pnr.num_passengers)
            
            # Update segment
            await self._update_segment(tx, old_segment, new_flight)
            
            # Log modification
            await self._log_modification(tx, pnr_id, 'date_change', {
                'old_date': old_segment.departure_datetime.isoformat(),
                'new_date': new_flight.departure_datetime.isoformat(),
                'fare_difference': fare_diff,
                'change_fee': change_fee
            })
        
        # Collect additional payment if needed
        total_additional = fare_diff + change_fee
        if total_additional > 0:
            await self.payment_service.charge_additional(pnr.payment_id, total_additional)
        
        return ModificationResult(success=True, additional_charge=total_additional)
```

## 8. Component Optimization

### Fare Cache Strategy
```python
# Fares are relatively static (change daily, not per-second)
# Cache strategy: Multi-layer
FARE_CACHE = {
    "L1_local": {"type": "in-memory", "ttl": 300, "size": "2GB per instance"},
    "L2_redis": {"type": "redis_cluster", "ttl": 3600, "size": "50GB"},
    "L3_db": {"type": "PostgreSQL", "source_of_truth": True}
}

# Inventory is dynamic (changes per booking)
INVENTORY_CACHE = {
    "redis": {
        "key": "inv:{flight_id}:{class_code}",
        "type": "integer_counter",
        "ttl": None,  # No TTL, invalidated on change
        "consistency": "read_after_write"  # Use Redis WAIT for critical reads
    }
}
```

### Search Performance Optimization
```python
# Pre-compute common routes (top 1000 O&D pairs)
class SearchPrecomputer:
    """Pre-compute search results for popular routes"""
    
    async def precompute_daily(self):
        popular_routes = await self.get_popular_routes(top_n=1000)
        
        for route in popular_routes:
            for days_ahead in range(1, 90):
                search_date = date.today() + timedelta(days=days_ahead)
                results = await self.search_engine.search(
                    route.origin, route.destination, search_date
                )
                # Cache results
                await self.redis.setex(
                    f"precomputed:{route.origin}:{route.destination}:{search_date}",
                    3600,  # 1 hour TTL
                    json.dumps(results)
                )
```

### Kafka Topics
```yaml
topics:
  pnr.events:
    partitions: 32
    replication.factor: 3
    retention.ms: 2592000000  # 30 days
    min.insync.replicas: 2
    
  inventory.updates:
    partitions: 64
    replication.factor: 3
    retention.ms: 86400000
    compression.type: lz4
    # Partition by flight_id for ordering
    
  revenue.optimization:
    partitions: 16
    replication.factor: 2
    retention.ms: 86400000
    
  checkin.events:
    partitions: 32
    replication.factor: 3
    retention.ms: 172800000  # 2 days
```

## 9. Observability

### Metrics
```yaml
metrics:
  - name: flight_search_latency_ms
    type: histogram
    labels: [trip_type, cabin, num_stops]
    buckets: [100, 250, 500, 1000, 2000, 3000, 5000]
    
  - name: inventory_sell_reject_rate
    type: gauge
    labels: [reason]  # no_availability, bid_price, closed
    
  - name: pnr_creation_rate
    type: counter
    labels: [channel, status]
    
  - name: revenue_per_asm  # Revenue per Available Seat Mile
    type: gauge
    labels: [route, cabin]
    
  - name: load_factor
    type: gauge
    labels: [flight_id, cabin]
    
  - name: overbooking_denied_boarding
    type: counter
    labels: [flight_id]
```

### Alerting
```yaml
alerts:
  - name: OversellBeyondLimit
    condition: flight_oversell_count > overbooking_limit
    severity: critical
    
  - name: InventoryDesync
    condition: abs(redis_inventory - db_inventory) > 2
    for: 5m
    severity: critical
    
  - name: GDSResponseSlow
    condition: gds_response_time_p95 > 3000
    severity: warning
    
  - name: RevenueOptimizationStale
    condition: time_since_last_optimization > 3600
    severity: warning
```

## 10. Considerations

### GDS Integration (Amadeus/Sabre/Travelport)
- NDC (New Distribution Capability) XML API for modern distribution
- EDIFACT legacy format for traditional GDS channels
- Maintain dual-format response capability
- GDS cut ~$4-12 per segment in fees → incentivize direct bookings

### Alliance & Codeshare
- Codeshare: Marketing carrier ≠ Operating carrier
- Inventory comes from operating carrier via AVS (Availability Status) messages
- Revenue sharing rules per codeshare agreement
- Interline ticketing: One ticket, multiple carriers

### Regulatory Compliance
- EU261: Compensation rules for delays/cancellations
- DOT (US): Fare advertising rules, refund policies
- PCI-DSS: Payment card data security
- GDPR: Passenger data privacy
- APIS: Advance Passenger Information to customs

### Overbooking Strategy
```python
# Airlines typically overbook 5-15% based on historical no-show rates
def calculate_overbooking(flight, historical_noshow_rate, denied_boarding_cost):
    capacity = flight.total_seats
    fare_avg = flight.avg_fare
    
    # Optimal overbooking: marginal revenue = marginal cost of denied boarding
    # Iterative approach
    for extra in range(1, int(capacity * 0.2)):
        p_denied = probability_denied_boarding(capacity, extra, historical_noshow_rate)
        marginal_revenue = fare_avg * historical_noshow_rate
        marginal_cost = p_denied * denied_boarding_cost
        
        if marginal_cost > marginal_revenue:
            return extra - 1
    return 0
```

## 11. Scaling & Multi-Region

### Global Distribution
```
Primary Regions:
- US-EAST: Americas operations hub
- EU-WEST: European operations hub  
- AP-SOUTH: Asia-Pacific hub

Data routing:
- PNR writes → primary region of departing airport
- PNR reads → any region (replicated)
- Inventory → primary per flight (strongly consistent)
- Search → regional (pre-computed, eventually consistent)
```

### Handling 50K Searches/Second
- Pre-computed search results for top 1000 O&D pairs
- Redis-cached fare lookups
- Elasticsearch for flexible date search and discovery
- Graph DB for routing computation (pre-warmed)
- CDN for static schedule data (changes once/season)
