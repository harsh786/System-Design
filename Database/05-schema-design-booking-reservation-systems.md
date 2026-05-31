# Schema Design - Booking & Reservation Systems (Problems 91-110)

## Staff Architect Level - Including Double Booking Prevention

---

## Problem 91: Prevent Double Booking (The Classic Interview Problem)

**Difficulty:** Hard | **Frequency:** EXTREMELY HIGH (Asked at Google, Airbnb, Uber, Booking.com)

**Problem:** Design a system where users can book time slots (meeting rooms, doctor appointments, hotel rooms) and the system MUST prevent overlapping bookings.

**The Core Challenge:** Two users simultaneously trying to book the same overlapping slot. This is fundamentally a concurrency problem.

### Schema:

```sql
CREATE TABLE resources (
    resource_id UUID PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    type VARCHAR(50) NOT NULL,  -- 'meeting_room', 'doctor', 'hotel_room'
    capacity INT DEFAULT 1,
    timezone VARCHAR(50) DEFAULT 'UTC',
    is_active BOOLEAN DEFAULT TRUE
);

CREATE TABLE bookings (
    booking_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    resource_id UUID NOT NULL REFERENCES resources(resource_id),
    user_id UUID NOT NULL,
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP NOT NULL,
    status ENUM('confirmed', 'cancelled', 'completed', 'no_show') DEFAULT 'confirmed',
    title VARCHAR(255),
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    
    -- CRITICAL: Prevent invalid ranges
    CHECK (end_time > start_time),
    
    -- Index for overlap detection
    INDEX idx_resource_time (resource_id, start_time, end_time),
    
    -- PostgreSQL: Use exclusion constraint (BEST approach)
    -- EXCLUDE USING gist (resource_id WITH =, tstzrange(start_time, end_time) WITH &&)
);
```

### Solution 1: PostgreSQL Exclusion Constraint (BEST - Database-Level Guarantee)

```sql
-- Requires btree_gist extension
CREATE EXTENSION IF NOT EXISTS btree_gist;

CREATE TABLE bookings (
    booking_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    resource_id UUID NOT NULL,
    user_id UUID NOT NULL,
    time_range TSTZRANGE NOT NULL,
    status VARCHAR(20) DEFAULT 'confirmed',
    
    -- THIS IS THE MAGIC: Database enforces no overlaps
    CONSTRAINT no_double_booking 
        EXCLUDE USING gist (
            resource_id WITH =, 
            time_range WITH &&
        ) WHERE (status = 'confirmed')
);

-- Insert (will fail if overlapping)
INSERT INTO bookings (resource_id, user_id, time_range)
VALUES (@resource_id, @user_id, tstzrange('2024-03-15 10:00', '2024-03-15 11:00'));
-- If overlap exists → ERROR: conflicting key value violates exclusion constraint
```

**Why this is the BEST approach:**
- Database guarantees correctness regardless of application bugs
- Works under any concurrency level
- No race conditions possible
- Uses GiST index for efficient overlap checking

### Solution 2: SELECT FOR UPDATE (Pessimistic Locking)

```sql
BEGIN TRANSACTION;

-- Lock the resource for the time range
SELECT booking_id FROM bookings
WHERE resource_id = @resource_id
  AND status = 'confirmed'
  AND start_time < @end_time
  AND end_time > @start_time
FOR UPDATE;

-- If no rows returned, slot is free → insert
INSERT INTO bookings (resource_id, user_id, start_time, end_time, status)
VALUES (@resource_id, @user_id, @start_time, @end_time, 'confirmed');

COMMIT;
-- If rows were returned → slot is taken, ROLLBACK
```

**The Overlap Condition Explained:**
```
Two intervals [A_start, A_end) and [B_start, B_end) overlap when:
    A_start < B_end AND A_end > B_start

Visualized:
    Existing: |----A----|
    New:           |----B----|
    Overlap:       |---| (A_start < B_end AND A_end > B_start)
    
    No overlap: |----A----|        |----B----|
    (A_end <= B_start)
```

### Solution 3: Slot-Based Approach (Time Grid)

```sql
-- Pre-generate available time slots
CREATE TABLE time_slots (
    slot_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    resource_id UUID NOT NULL,
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP NOT NULL,
    is_available BOOLEAN DEFAULT TRUE,
    booking_id UUID REFERENCES bookings(booking_id),
    UNIQUE KEY uk_resource_start (resource_id, start_time)
);

-- Book a slot (atomic update)
UPDATE time_slots
SET is_available = FALSE, booking_id = @booking_id
WHERE resource_id = @resource_id
  AND start_time >= @start_time
  AND end_time <= @end_time
  AND is_available = TRUE;

-- Check affected_rows = expected_slot_count
-- If less → some slots were taken → ROLLBACK
```

### Solution 4: Optimistic Locking with Version

```sql
-- Add version column
ALTER TABLE bookings ADD COLUMN version INT DEFAULT 0;

-- Application-level check + retry loop:
-- 1. Read current bookings for the resource
-- 2. Check for overlap in application code
-- 3. Insert with a unique constraint on (resource_id, time_range) 
-- 4. If constraint violation → retry
```

### Comparison of Approaches:

| Approach | Consistency | Performance | Complexity | Best For |
|----------|-------------|-------------|------------|----------|
| Exclusion Constraint | Perfect | High | Low | PostgreSQL systems |
| SELECT FOR UPDATE | Perfect | Medium (lock contention) | Medium | Any RDBMS |
| Slot-based | Perfect | High (pre-computed) | Medium | Fixed-interval bookings |
| Optimistic Lock | Good (with retry) | Highest (no locks) | High | Low-contention scenarios |

---

## Problem 92: Design a Hotel Reservation System (Booking.com)

**Difficulty:** Expert | **Frequency:** Very High

```sql
CREATE TABLE hotels (
    hotel_id UUID PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    address TEXT,
    city VARCHAR(100),
    country CHAR(2),
    star_rating DECIMAL(2,1),
    latitude DECIMAL(10,8),
    longitude DECIMAL(11,8),
    timezone VARCHAR(50),
    check_in_time TIME DEFAULT '15:00',
    check_out_time TIME DEFAULT '11:00'
);

CREATE TABLE room_types (
    room_type_id UUID PRIMARY KEY,
    hotel_id UUID NOT NULL REFERENCES hotels(hotel_id),
    name VARCHAR(100) NOT NULL,  -- "Deluxe King", "Standard Twin"
    description TEXT,
    max_occupancy INT NOT NULL,
    bed_configuration VARCHAR(100),  -- "1 King" or "2 Twin"
    total_rooms INT NOT NULL,  -- Number of physical rooms of this type
    base_price DECIMAL(10,2) NOT NULL,
    amenities JSONB,
    images JSONB
);

-- Daily inventory and pricing (flexible rates per day)
CREATE TABLE room_availability (
    room_type_id UUID NOT NULL REFERENCES room_types(room_type_id),
    date DATE NOT NULL,
    total_inventory INT NOT NULL,
    booked_count INT NOT NULL DEFAULT 0,
    available_count INT GENERATED ALWAYS AS (total_inventory - booked_count) STORED,
    price DECIMAL(10,2) NOT NULL,  -- Dynamic pricing per day
    min_stay_nights INT DEFAULT 1,
    is_closed BOOLEAN DEFAULT FALSE,  -- Stop sell
    PRIMARY KEY (room_type_id, date),
    CHECK (booked_count <= total_inventory)
);

CREATE TABLE reservations (
    reservation_id UUID PRIMARY KEY,
    hotel_id UUID NOT NULL,
    room_type_id UUID NOT NULL,
    guest_id UUID NOT NULL,
    confirmation_number VARCHAR(20) UNIQUE NOT NULL,
    check_in_date DATE NOT NULL,
    check_out_date DATE NOT NULL,
    nights INT GENERATED ALWAYS AS (check_out_date - check_in_date) STORED,
    room_count INT NOT NULL DEFAULT 1,  -- Can book multiple rooms
    total_price DECIMAL(12,2) NOT NULL,
    status ENUM('pending', 'confirmed', 'checked_in', 'checked_out', 'cancelled', 'no_show') DEFAULT 'pending',
    guest_name VARCHAR(255) NOT NULL,
    guest_email VARCHAR(255),
    special_requests TEXT,
    cancellation_policy VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW(),
    cancelled_at TIMESTAMP,
    INDEX idx_hotel_dates (hotel_id, check_in_date, check_out_date),
    INDEX idx_guest (guest_id),
    CHECK (check_out_date > check_in_date)
);
```

**Book a Room (Atomic Availability Decrement):**
```sql
BEGIN TRANSACTION;

-- Decrement availability for ALL nights of the stay
UPDATE room_availability
SET booked_count = booked_count + @room_count
WHERE room_type_id = @room_type_id
  AND date >= @check_in_date
  AND date < @check_out_date
  AND is_closed = FALSE
  AND (total_inventory - booked_count) >= @room_count;

-- Verify ALL dates were updated
-- Expected: check_out_date - check_in_date rows affected
IF @@ROW_COUNT != DATEDIFF(@check_out_date, @check_in_date) THEN
    ROLLBACK;
    -- Some dates don't have availability
ELSE
    -- Insert reservation
    INSERT INTO reservations (...) VALUES (...);
    COMMIT;
END IF;
```

**Search Available Hotels:**
```sql
WITH date_range AS (
    SELECT generate_series(@check_in::date, @check_out::date - 1, '1 day')::date AS night
),
available_rooms AS (
    SELECT ra.room_type_id, rt.hotel_id, rt.name AS room_name,
           MIN(ra.available_count) AS min_available,  -- Bottleneck night
           SUM(ra.price) AS total_price,
           AVG(ra.price) AS avg_nightly_price
    FROM room_availability ra
    JOIN room_types rt ON ra.room_type_id = rt.room_type_id
    JOIN date_range dr ON ra.date = dr.night
    WHERE ra.is_closed = FALSE
      AND ra.available_count >= @rooms_needed
    GROUP BY ra.room_type_id, rt.hotel_id, rt.name
    HAVING COUNT(*) = (SELECT COUNT(*) FROM date_range)  -- Available ALL nights
)
SELECT h.name AS hotel, ar.room_name, ar.min_available, ar.total_price
FROM available_rooms ar
JOIN hotels h ON ar.hotel_id = h.hotel_id
WHERE h.city = @city
ORDER BY ar.total_price;
```

---

## Problem 93: Design a Restaurant Table Reservation System (OpenTable)

**Difficulty:** Hard | **Frequency:** High

```sql
CREATE TABLE restaurants (
    restaurant_id UUID PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    cuisine_type VARCHAR(100),
    max_party_size INT DEFAULT 20,
    reservation_duration_minutes INT DEFAULT 90,  -- Default time per reservation
    advance_booking_days INT DEFAULT 30,
    timezone VARCHAR(50) NOT NULL
);

CREATE TABLE restaurant_tables (
    table_id UUID PRIMARY KEY,
    restaurant_id UUID NOT NULL REFERENCES restaurants(restaurant_id),
    table_number VARCHAR(10) NOT NULL,
    min_capacity INT NOT NULL DEFAULT 1,
    max_capacity INT NOT NULL,
    section VARCHAR(50),  -- "patio", "main", "bar", "private"
    is_combinable BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    UNIQUE KEY uk_restaurant_table (restaurant_id, table_number)
);

-- Operating hours with special schedules
CREATE TABLE restaurant_hours (
    restaurant_id UUID NOT NULL,
    day_of_week INT NOT NULL,  -- 0=Sunday, 6=Saturday
    open_time TIME NOT NULL,
    close_time TIME NOT NULL,
    last_seating TIME NOT NULL,  -- Last reservation start time
    is_closed BOOLEAN DEFAULT FALSE,
    PRIMARY KEY (restaurant_id, day_of_week)
);

CREATE TABLE table_reservations (
    reservation_id UUID PRIMARY KEY,
    restaurant_id UUID NOT NULL,
    table_id UUID,  -- Can be NULL until table assigned
    guest_id UUID,
    guest_name VARCHAR(255) NOT NULL,
    guest_phone VARCHAR(20),
    guest_email VARCHAR(255),
    party_size INT NOT NULL,
    reservation_date DATE NOT NULL,
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,
    status ENUM('confirmed', 'seated', 'completed', 'cancelled', 'no_show') DEFAULT 'confirmed',
    source ENUM('website', 'app', 'phone', 'walkin') DEFAULT 'website',
    special_requests TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    INDEX idx_restaurant_date (restaurant_id, reservation_date, start_time),
    INDEX idx_table_date (table_id, reservation_date),
    
    -- Prevent double-booking of tables (PostgreSQL)
    -- EXCLUDE USING gist (table_id WITH =, tstzrange(start_time, end_time) WITH &&)
    --   WHERE (status IN ('confirmed', 'seated'))
);
```

**Find Available Time Slots:**
```sql
-- Get all 30-minute slots for a given date and party size
WITH RECURSIVE time_slots AS (
    SELECT rh.open_time AS slot_start,
           rh.open_time + INTERVAL '30 minutes' AS slot_end
    FROM restaurant_hours rh
    WHERE rh.restaurant_id = @restaurant_id
      AND rh.day_of_week = EXTRACT(DOW FROM @date::date)
      AND rh.is_closed = FALSE
    
    UNION ALL
    
    SELECT slot_start + INTERVAL '30 minutes',
           slot_end + INTERVAL '30 minutes'
    FROM time_slots
    WHERE slot_end <= (SELECT last_seating FROM restaurant_hours 
                       WHERE restaurant_id = @restaurant_id 
                       AND day_of_week = EXTRACT(DOW FROM @date::date))
),
available_tables AS (
    SELECT t.table_id, t.max_capacity, ts.slot_start
    FROM restaurant_tables t
    CROSS JOIN time_slots ts
    WHERE t.restaurant_id = @restaurant_id
      AND t.max_capacity >= @party_size
      AND t.min_capacity <= @party_size
      AND t.is_active = TRUE
      AND NOT EXISTS (
          SELECT 1 FROM table_reservations tr
          WHERE tr.table_id = t.table_id
            AND tr.reservation_date = @date
            AND tr.status IN ('confirmed', 'seated')
            AND tr.start_time < ts.slot_start + INTERVAL '90 minutes'
            AND tr.end_time > ts.slot_start
      )
)
SELECT slot_start, COUNT(DISTINCT table_id) AS available_tables
FROM available_tables
GROUP BY slot_start
HAVING COUNT(DISTINCT table_id) > 0
ORDER BY slot_start;
```

---

## Problem 94: Design a Flight Booking System

**Difficulty:** Expert | **Frequency:** High

```sql
CREATE TABLE flights (
    flight_id UUID PRIMARY KEY,
    flight_number VARCHAR(10) NOT NULL,  -- "AA1234"
    airline_code CHAR(2) NOT NULL,
    departure_airport CHAR(3) NOT NULL,  -- IATA: "JFK"
    arrival_airport CHAR(3) NOT NULL,
    departure_time TIMESTAMP NOT NULL,
    arrival_time TIMESTAMP NOT NULL,
    aircraft_type VARCHAR(50),
    status ENUM('scheduled', 'boarding', 'departed', 'arrived', 'cancelled', 'delayed') DEFAULT 'scheduled',
    INDEX idx_route_date (departure_airport, arrival_airport, departure_time)
);

CREATE TABLE seat_classes (
    flight_id UUID NOT NULL REFERENCES flights(flight_id),
    class ENUM('economy', 'premium_economy', 'business', 'first') NOT NULL,
    total_seats INT NOT NULL,
    available_seats INT NOT NULL,
    base_price DECIMAL(10,2) NOT NULL,
    PRIMARY KEY (flight_id, class),
    CHECK (available_seats >= 0 AND available_seats <= total_seats)
);

CREATE TABLE flight_bookings (
    booking_id UUID PRIMARY KEY,
    pnr VARCHAR(6) UNIQUE NOT NULL,  -- Passenger Name Record
    user_id UUID NOT NULL,
    status ENUM('pending', 'confirmed', 'ticketed', 'cancelled', 'refunded') DEFAULT 'pending',
    total_price DECIMAL(12,2) NOT NULL,
    currency CHAR(3) DEFAULT 'USD',
    booking_source VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE booking_segments (
    segment_id UUID PRIMARY KEY,
    booking_id UUID NOT NULL REFERENCES flight_bookings(booking_id),
    flight_id UUID NOT NULL REFERENCES flights(flight_id),
    class ENUM('economy', 'premium_economy', 'business', 'first') NOT NULL,
    segment_order INT NOT NULL,  -- For multi-leg itineraries
    INDEX idx_booking (booking_id),
    INDEX idx_flight (flight_id)
);

CREATE TABLE passengers (
    passenger_id UUID PRIMARY KEY,
    booking_id UUID NOT NULL REFERENCES flight_bookings(booking_id),
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    date_of_birth DATE,
    passport_number VARCHAR(50),
    nationality CHAR(2),
    seat_number VARCHAR(5),  -- "12A"
    meal_preference VARCHAR(50),
    special_assistance JSONB
);
```

**Seat Inventory Management (with overbooking):**
```sql
-- Airlines overbook by ~5-15%
CREATE TABLE seat_inventory (
    flight_id UUID NOT NULL,
    class VARCHAR(20) NOT NULL,
    physical_seats INT NOT NULL,
    overbooking_factor DECIMAL(3,2) DEFAULT 1.05,  -- 5% overbook
    bookable_seats INT GENERATED ALWAYS AS (FLOOR(physical_seats * overbooking_factor)) STORED,
    confirmed_bookings INT NOT NULL DEFAULT 0,
    available INT GENERATED ALWAYS AS (FLOOR(physical_seats * overbooking_factor) - confirmed_bookings) STORED,
    PRIMARY KEY (flight_id, class)
);
```

---

## Problem 95: Design a Movie Theater Seat Booking System

**Difficulty:** Hard | **Frequency:** Very High

**Key Challenge:** Users select specific seats; must prevent same seat being sold twice.

```sql
CREATE TABLE theaters (
    theater_id UUID PRIMARY KEY,
    name VARCHAR(255),
    address TEXT
);

CREATE TABLE screens (
    screen_id UUID PRIMARY KEY,
    theater_id UUID NOT NULL REFERENCES theaters(theater_id),
    name VARCHAR(50),  -- "Screen 1", "IMAX"
    total_seats INT NOT NULL
);

CREATE TABLE seats (
    seat_id UUID PRIMARY KEY,
    screen_id UUID NOT NULL REFERENCES screens(screen_id),
    row_label CHAR(2) NOT NULL,  -- "A", "B", "AA"
    seat_number INT NOT NULL,
    seat_type ENUM('standard', 'premium', 'vip', 'wheelchair', 'companion') DEFAULT 'standard',
    UNIQUE KEY uk_screen_seat (screen_id, row_label, seat_number)
);

CREATE TABLE showings (
    showing_id UUID PRIMARY KEY,
    screen_id UUID NOT NULL REFERENCES screens(screen_id),
    movie_id UUID NOT NULL,
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP NOT NULL,
    price_standard DECIMAL(8,2) NOT NULL,
    price_premium DECIMAL(8,2),
    price_vip DECIMAL(8,2),
    status ENUM('scheduled', 'selling', 'sold_out', 'cancelled') DEFAULT 'scheduled',
    UNIQUE KEY uk_screen_time (screen_id, start_time)
);

-- Seat status per showing
CREATE TABLE showing_seats (
    showing_id UUID NOT NULL REFERENCES showings(showing_id),
    seat_id UUID NOT NULL REFERENCES seats(seat_id),
    status ENUM('available', 'held', 'booked', 'blocked') DEFAULT 'available',
    held_by UUID,  -- User who is holding (temporary)
    held_until TIMESTAMP,  -- Hold expiration
    booking_id UUID,
    PRIMARY KEY (showing_id, seat_id),
    INDEX idx_status (showing_id, status)
);
```

**Two-Phase Booking (Hold → Confirm):**
```sql
-- Phase 1: Hold seats (5-minute hold during checkout)
UPDATE showing_seats
SET status = 'held', held_by = @user_id, held_until = NOW() + INTERVAL '5 minutes'
WHERE showing_id = @showing_id
  AND seat_id IN (@seat1, @seat2, @seat3)
  AND status = 'available';
  
-- Verify ALL seats were held
-- If affected_rows != number_of_seats → some were taken → ROLLBACK

-- Phase 2: Confirm after payment
UPDATE showing_seats
SET status = 'booked', booking_id = @booking_id
WHERE showing_id = @showing_id
  AND seat_id IN (@seat1, @seat2, @seat3)
  AND held_by = @user_id
  AND status = 'held';

-- Background job: Release expired holds
UPDATE showing_seats
SET status = 'available', held_by = NULL, held_until = NULL
WHERE status = 'held' AND held_until < NOW();
```

---

## Problem 96: Design a Doctor Appointment Booking System

**Difficulty:** Hard | **Frequency:** Very High

```sql
CREATE TABLE doctors (
    doctor_id UUID PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    specialization VARCHAR(100) NOT NULL,
    consultation_duration_minutes INT DEFAULT 30,
    max_daily_appointments INT DEFAULT 20
);

-- Weekly recurring schedule
CREATE TABLE doctor_schedules (
    schedule_id UUID PRIMARY KEY,
    doctor_id UUID NOT NULL REFERENCES doctors(doctor_id),
    day_of_week INT NOT NULL,  -- 0-6
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,
    slot_duration_minutes INT NOT NULL DEFAULT 30,
    location_id UUID,
    is_active BOOLEAN DEFAULT TRUE,
    PRIMARY KEY (doctor_id, day_of_week, start_time)
);

-- Exceptions to regular schedule (holidays, leave, special hours)
CREATE TABLE schedule_overrides (
    override_id UUID PRIMARY KEY,
    doctor_id UUID NOT NULL,
    override_date DATE NOT NULL,
    override_type ENUM('unavailable', 'modified_hours') NOT NULL,
    start_time TIME,  -- For modified hours
    end_time TIME,
    reason VARCHAR(255),
    UNIQUE KEY uk_doctor_date (doctor_id, override_date)
);

CREATE TABLE appointments (
    appointment_id UUID PRIMARY KEY,
    doctor_id UUID NOT NULL REFERENCES doctors(doctor_id),
    patient_id UUID NOT NULL,
    appointment_date DATE NOT NULL,
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,
    appointment_type ENUM('new_patient', 'follow_up', 'urgent', 'telehealth') DEFAULT 'follow_up',
    status ENUM('scheduled', 'confirmed', 'in_progress', 'completed', 'cancelled', 'no_show') DEFAULT 'scheduled',
    cancellation_reason TEXT,
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    
    INDEX idx_doctor_date (doctor_id, appointment_date, start_time),
    INDEX idx_patient (patient_id),
    
    -- PostgreSQL exclusion constraint
    EXCLUDE USING gist (
        doctor_id WITH =,
        tstzrange(
            (appointment_date || ' ' || start_time)::timestamptz,
            (appointment_date || ' ' || end_time)::timestamptz
        ) WITH &&
    ) WHERE (status NOT IN ('cancelled'))
);
```

---

## Problem 97: Design an Event Ticketing System (Ticketmaster)

**Difficulty:** Expert | **Frequency:** High

**Key Challenge:** Extreme burst traffic (Taylor Swift tickets scenario — millions of concurrent users)

```sql
CREATE TABLE events (
    event_id UUID PRIMARY KEY,
    name VARCHAR(500) NOT NULL,
    venue_id UUID NOT NULL,
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP,
    on_sale_time TIMESTAMP NOT NULL,  -- When tickets go on sale
    status ENUM('upcoming', 'on_sale', 'sold_out', 'completed', 'cancelled') DEFAULT 'upcoming',
    max_tickets_per_user INT DEFAULT 4
);

CREATE TABLE ticket_tiers (
    tier_id UUID PRIMARY KEY,
    event_id UUID NOT NULL REFERENCES events(event_id),
    name VARCHAR(100) NOT NULL,  -- "General Admission", "VIP", "Floor"
    price DECIMAL(10,2) NOT NULL,
    total_quantity INT NOT NULL,
    available_quantity INT NOT NULL,
    sale_start TIMESTAMP,
    sale_end TIMESTAMP,
    INDEX idx_event (event_id)
);

-- Virtual waiting room queue
CREATE TABLE ticket_queue (
    queue_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    event_id UUID NOT NULL,
    user_id UUID NOT NULL,
    queue_position INT NOT NULL,
    joined_at TIMESTAMP DEFAULT NOW(),
    status ENUM('waiting', 'active', 'expired', 'completed') DEFAULT 'waiting',
    activated_at TIMESTAMP,  -- When given access to buy
    expires_at TIMESTAMP,
    UNIQUE KEY uk_event_user (event_id, user_id),
    INDEX idx_event_status (event_id, status, queue_position)
);

CREATE TABLE ticket_orders (
    order_id UUID PRIMARY KEY,
    event_id UUID NOT NULL,
    user_id UUID NOT NULL,
    tier_id UUID NOT NULL,
    quantity INT NOT NULL,
    unit_price DECIMAL(10,2) NOT NULL,
    total_price DECIMAL(10,2) NOT NULL,
    service_fee DECIMAL(10,2) NOT NULL,
    status ENUM('reserved', 'payment_pending', 'confirmed', 'cancelled', 'refunded') DEFAULT 'reserved',
    reserved_at TIMESTAMP DEFAULT NOW(),
    reservation_expires_at TIMESTAMP NOT NULL,  -- Must pay within X minutes
    confirmed_at TIMESTAMP,
    INDEX idx_event_user (event_id, user_id),
    INDEX idx_expires (status, reservation_expires_at)
);
```

**Architecture for Extreme Concurrency:**
```
1. CDN + Static queue page → Absorb traffic without hitting backend
2. Virtual Queue (Redis ZADD with random score for fairness)
3. Batch activation: Move N users from waiting → active every M seconds
4. Active users get time-limited token to access purchase flow
5. Inventory: Redis DECR for fast-path, SQL for source of truth
6. Payment timeout: 10 minutes to complete or release back to pool
```

---

## Problem 98: Design a Parking Lot System

**Difficulty:** Medium | **Frequency:** Very High (Classic OOP + DB design)

```sql
CREATE TABLE parking_lots (
    lot_id UUID PRIMARY KEY,
    name VARCHAR(255),
    address TEXT,
    total_spots INT NOT NULL,
    hourly_rate DECIMAL(6,2) NOT NULL,
    daily_max_rate DECIMAL(8,2)
);

CREATE TABLE parking_spots (
    spot_id UUID PRIMARY KEY,
    lot_id UUID NOT NULL REFERENCES parking_lots(lot_id),
    spot_number VARCHAR(10) NOT NULL,
    level INT NOT NULL DEFAULT 1,
    type ENUM('compact', 'regular', 'large', 'handicap', 'electric') NOT NULL,
    is_available BOOLEAN DEFAULT TRUE,
    UNIQUE KEY uk_lot_spot (lot_id, spot_number)
);

CREATE TABLE parking_sessions (
    session_id UUID PRIMARY KEY,
    lot_id UUID NOT NULL,
    spot_id UUID NOT NULL REFERENCES parking_spots(spot_id),
    vehicle_plate VARCHAR(20) NOT NULL,
    vehicle_type ENUM('motorcycle', 'compact', 'regular', 'large', 'truck') NOT NULL,
    entry_time TIMESTAMP NOT NULL DEFAULT NOW(),
    exit_time TIMESTAMP,
    duration_minutes INT GENERATED ALWAYS AS (
        EXTRACT(EPOCH FROM (COALESCE(exit_time, NOW()) - entry_time)) / 60
    ) STORED,
    amount_charged DECIMAL(8,2),
    payment_status ENUM('pending', 'paid', 'waived') DEFAULT 'pending',
    INDEX idx_spot (spot_id, exit_time),
    INDEX idx_plate (vehicle_plate)
);

-- Real-time availability
CREATE VIEW lot_availability AS
SELECT pl.lot_id, pl.name,
       ps.type AS spot_type,
       COUNT(*) AS total,
       SUM(CASE WHEN ps.is_available THEN 1 ELSE 0 END) AS available
FROM parking_lots pl
JOIN parking_spots ps ON pl.lot_id = ps.lot_id
GROUP BY pl.lot_id, pl.name, ps.type;
```

---

## Problem 99: Design a Ride-Hailing System (Uber/Lyft Database)

**Difficulty:** Expert | **Frequency:** Very High

```sql
CREATE TABLE drivers (
    driver_id UUID PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    phone VARCHAR(20) NOT NULL,
    vehicle_plate VARCHAR(20),
    vehicle_type ENUM('economy', 'comfort', 'premium', 'xl', 'pool') NOT NULL,
    status ENUM('offline', 'available', 'en_route', 'on_trip') DEFAULT 'offline',
    current_latitude DECIMAL(10,8),
    current_longitude DECIMAL(11,8),
    location_updated_at TIMESTAMP,
    rating DECIMAL(3,2) DEFAULT 5.00,
    total_trips INT DEFAULT 0
);

-- Geospatial index for finding nearby drivers
-- In production: Use Redis GeoSpatial or H3 hexagonal grid

CREATE TABLE ride_requests (
    ride_id UUID PRIMARY KEY,
    rider_id UUID NOT NULL,
    pickup_latitude DECIMAL(10,8) NOT NULL,
    pickup_longitude DECIMAL(11,8) NOT NULL,
    pickup_address VARCHAR(500),
    dropoff_latitude DECIMAL(10,8) NOT NULL,
    dropoff_longitude DECIMAL(11,8) NOT NULL,
    dropoff_address VARCHAR(500),
    ride_type ENUM('economy', 'comfort', 'premium', 'xl', 'pool') NOT NULL,
    status ENUM('requested', 'matching', 'driver_assigned', 'driver_arriving', 'in_progress', 'completed', 'cancelled') DEFAULT 'requested',
    driver_id UUID REFERENCES drivers(driver_id),
    
    -- Pricing
    estimated_price DECIMAL(10,2),
    actual_price DECIMAL(10,2),
    surge_multiplier DECIMAL(4,2) DEFAULT 1.00,
    distance_km DECIMAL(8,2),
    duration_minutes INT,
    
    -- Timestamps
    requested_at TIMESTAMP DEFAULT NOW(),
    accepted_at TIMESTAMP,
    pickup_at TIMESTAMP,
    dropoff_at TIMESTAMP,
    cancelled_at TIMESTAMP,
    
    INDEX idx_status (status, requested_at),
    INDEX idx_driver (driver_id, status),
    INDEX idx_rider (rider_id, requested_at DESC)
);

-- Surge pricing zones (H3 hexagons)
CREATE TABLE surge_zones (
    h3_index VARCHAR(15) NOT NULL,  -- H3 hexagonal index
    ride_type VARCHAR(20) NOT NULL,
    surge_multiplier DECIMAL(4,2) NOT NULL DEFAULT 1.00,
    demand_count INT NOT NULL DEFAULT 0,
    supply_count INT NOT NULL DEFAULT 0,
    computed_at TIMESTAMP NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    PRIMARY KEY (h3_index, ride_type)
);
```

---

## Problem 100: Design a Calendar/Scheduling System (Google Calendar)

**Difficulty:** Hard | **Frequency:** Very High

```sql
CREATE TABLE calendars (
    calendar_id UUID PRIMARY KEY,
    owner_id UUID NOT NULL,
    name VARCHAR(255) NOT NULL,
    color VARCHAR(7) DEFAULT '#4285F4',
    timezone VARCHAR(50) NOT NULL,
    is_primary BOOLEAN DEFAULT FALSE,
    visibility ENUM('public', 'private', 'free_busy_only') DEFAULT 'private'
);

CREATE TABLE calendar_events (
    event_id UUID PRIMARY KEY,
    calendar_id UUID NOT NULL REFERENCES calendars(calendar_id),
    title VARCHAR(500) NOT NULL,
    description TEXT,
    location VARCHAR(500),
    
    -- Time (support all-day events and timed events)
    is_all_day BOOLEAN DEFAULT FALSE,
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP NOT NULL,
    timezone VARCHAR(50),
    
    -- Recurrence (RFC 5545 RRULE)
    is_recurring BOOLEAN DEFAULT FALSE,
    recurrence_rule VARCHAR(500),  -- "FREQ=WEEKLY;BYDAY=MO,WE,FR;UNTIL=20241231"
    recurrence_id UUID,  -- Links exception to parent recurring event
    original_start_time TIMESTAMP,  -- Original occurrence this exception replaces
    
    -- Status
    status ENUM('confirmed', 'tentative', 'cancelled') DEFAULT 'confirmed',
    visibility ENUM('public', 'private', 'confidential') DEFAULT 'public',
    
    -- Reminders
    default_reminders JSONB,  -- [{"method": "popup", "minutes": 10}]
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    INDEX idx_calendar_time (calendar_id, start_time, end_time),
    INDEX idx_recurring (is_recurring, recurrence_id)
);

-- Event attendees
CREATE TABLE event_attendees (
    event_id UUID NOT NULL REFERENCES calendar_events(event_id),
    user_id UUID,
    email VARCHAR(255) NOT NULL,
    response_status ENUM('needs_action', 'accepted', 'declined', 'tentative') DEFAULT 'needs_action',
    role ENUM('organizer', 'required', 'optional') DEFAULT 'required',
    is_organizer BOOLEAN DEFAULT FALSE,
    responded_at TIMESTAMP,
    PRIMARY KEY (event_id, email)
);

-- Free/busy lookup for scheduling
CREATE TABLE free_busy_cache (
    user_id UUID NOT NULL,
    date DATE NOT NULL,
    busy_intervals JSONB NOT NULL,  -- [{"start": "09:00", "end": "10:00"}, ...]
    updated_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (user_id, date)
);
```

**Find Free Slots for Meeting (Availability Check):**
```sql
-- Find when ALL required attendees are free
WITH attendee_events AS (
    SELECT ea.email, ce.start_time, ce.end_time
    FROM event_attendees ea
    JOIN calendar_events ce ON ea.event_id = ce.event_id
    WHERE ea.email IN ('alice@co.com', 'bob@co.com', 'carol@co.com')
      AND ea.response_status != 'declined'
      AND ce.start_time::date = @target_date
      AND ce.status != 'cancelled'
),
busy_periods AS (
    SELECT start_time, end_time FROM attendee_events
)
-- Generate candidate slots and exclude busy ones
-- (In practice, done in application code with interval arithmetic)
SELECT slot_start, slot_end
FROM generate_series(
    @target_date + '09:00'::time,
    @target_date + '17:00'::time,
    '30 minutes'::interval
) AS slot_start
CROSS JOIN LATERAL (SELECT slot_start + @duration::interval AS slot_end) se
WHERE NOT EXISTS (
    SELECT 1 FROM busy_periods bp
    WHERE bp.start_time < se.slot_end AND bp.end_time > slot_start
);
```

---

## Problem 101-110: Additional Booking System Problems

### Problem 101: Design a Coworking Space Booking System
- Hot desk vs dedicated desk vs private office
- Hourly, daily, monthly billing
- Meeting room credits system

### Problem 102: Design a Sports Court Booking System
- Recurring weekly bookings
- Peak vs off-peak pricing
- Team/group bookings

### Problem 103: Design a Salon/Spa Appointment System
- Multiple services per appointment
- Staff skill matching
- Buffer time between appointments

### Problem 104: Design a Car Rental System
- Vehicle availability by location
- One-way rentals
- Insurance and extras

### Problem 105: Design a Shared Equipment Lending Library
- Return date tracking
- Waitlist when unavailable
- Damage deposits

### Problem 106: Design a Gym Class Booking System
- Limited capacity classes
- Waitlist with auto-enrollment
- Cancellation penalties

### Problem 107: Design a Conference Room System with Catering
- Room + equipment + catering booking
- Conflict detection across resources
- Recurring meetings

### Problem 108: Design a Vacation Rental System (Airbnb)
- Minimum/maximum stay rules
- Seasonal pricing
- Blocked dates by owner

### Problem 109: Design a Healthcare OR (Operating Room) Scheduling
- Priority-based scheduling
- Equipment and staff dependencies
- Emergency overrides

### Problem 110: Design a Multi-Resource Booking (Wedding Venue)
- Multiple resources per booking (venue + catering + music)
- Deposit and payment milestones
- Seasonal availability

---

## Key Patterns for Preventing Double Booking

| Technique | Database | Best For |
|-----------|----------|----------|
| Exclusion Constraint | PostgreSQL | Any time-range booking |
| SELECT FOR UPDATE | Any RDBMS | Medium concurrency |
| Atomic UPDATE with WHERE | Any RDBMS | Slot-based systems |
| Redis DECR + SQL confirm | Any | Extreme concurrency |
| Distributed Lock (Redis/Zookeeper) | Distributed | Multi-service coordination |
| Event Sourcing | Any | Audit-heavy requirements |
| Saga Pattern | Distributed | Multi-resource bookings |

## The Overlap Detection Formula

```
Two intervals [s1, e1) and [s2, e2) overlap if and only if:
    s1 < e2 AND s2 < e1

Equivalently, they DON'T overlap when:
    e1 <= s2 OR e2 <= s1
    (first ends before second starts, OR second ends before first starts)
```

This formula appears in EVERY booking system. Memorize it.
