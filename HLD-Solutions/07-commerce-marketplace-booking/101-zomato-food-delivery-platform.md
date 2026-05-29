# Design Zomato Food Delivery Platform

## 1. Functional Requirements

### Core Features
- **Restaurant Discovery**: Search by location, cuisine, rating, cost, dietary preference
- **Menu Browsing**: Full menu with photos, prices, customizations, dietary tags
- **Cart & Order Placement**: Multi-item cart, promo codes, special instructions
- **Delivery Partner Assignment**: Optimal rider matching based on distance, load, ETA
- **Live Order Tracking**: Real-time GPS tracking of delivery partner
- **Ratings & Reviews**: Restaurant rating, food photos, delivery rating
- **Table Booking**: Dine-in reservation for partner restaurants
- **Zomato Pro/Gold**: Subscription with discounts, priority delivery, exclusive deals

### User Types
1. **Customer**: Browses, orders, tracks, reviews
2. **Restaurant Partner**: Manages menu, accepts/rejects orders, manages prep time
3. **Delivery Partner**: Accepts deliveries, navigates, completes drops
4. **Admin**: Monitors operations, handles escalations, manages promotions

## 2. Non-Functional Requirements

| Requirement | Target |
|---|---|
| Search Latency | P99 < 400ms |
| Order Placement | < 2s end-to-end |
| Tracking Update | Every 3-5 seconds |
| Assignment Latency | < 30s from order confirmation |
| Availability | 99.95% (critical during meal peaks) |
| Scale | 500K+ restaurants, 50M+ orders/month |
| Concurrent Users | 2M+ during peak (lunch/dinner) |
| Location Accuracy | < 10m for delivery tracking |
| Notification Delivery | < 5s for order status changes |

## 3. Capacity Estimation

### Storage
```
Restaurants: 500K × 10KB = 5GB
Menu items: 500K × 50 items × 1KB = 25GB
Orders: 50M/month × 2KB = 100GB/month
Order items: 50M × 3 items × 200B = 30GB/month
Reviews: 20M/month × 500B = 10GB/month
Photos: 10M food photos × 2MB = 20TB
User profiles: 100M × 2KB = 200GB
Delivery partner locations: 500K partners × 24h × 1/5s × 100B = 864GB/day (time-series)
```

### Throughput (Peak Dinner 7-9 PM)
```
Active orders: 500K simultaneous
Orders per second: 3000
Location updates: 500K partners × 0.2/s = 100K updates/s
Search queries: 50K/s
Menu fetches: 30K/s
Push notifications: 20K/s
Restaurant confirmations: 3000/s
```

## 4. Data Modeling

### Full Database Schemas

```sql
-- Restaurants
CREATE TABLE restaurants (
    restaurant_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(300) NOT NULL,
    slug VARCHAR(300) UNIQUE,
    description TEXT,
    cuisine_types VARCHAR(50)[] NOT NULL,
    cost_for_two_cents INT, -- average cost for 2 people
    latitude DECIMAL(10, 7) NOT NULL,
    longitude DECIMAL(10, 7) NOT NULL,
    address TEXT NOT NULL,
    city VARCHAR(100) NOT NULL,
    locality VARCHAR(100) NOT NULL,
    pincode VARCHAR(10),
    phone VARCHAR(20),
    opening_time TIME,
    closing_time TIME,
    is_open BOOLEAN DEFAULT TRUE,
    delivery_available BOOLEAN DEFAULT TRUE,
    dine_in_available BOOLEAN DEFAULT TRUE,
    avg_delivery_time_min INT, -- estimated from historical data
    avg_rating DECIMAL(3,2),
    total_ratings INT DEFAULT 0,
    total_orders INT DEFAULT 0,
    is_promoted BOOLEAN DEFAULT FALSE,
    zomato_gold_partner BOOLEAN DEFAULT FALSE,
    fssai_license VARCHAR(20),
    commission_percent DECIMAL(4,2) DEFAULT 25.0,
    preparation_time_min INT DEFAULT 20,
    min_order_cents INT DEFAULT 10000, -- minimum order value
    delivery_radius_km DECIMAL(4,1) DEFAULT 7.0,
    status VARCHAR(20) DEFAULT 'active', -- active, paused, closed, suspended
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_restaurants_location ON restaurants USING GIST(
    ST_MakePoint(longitude, latitude)::geography
);
CREATE INDEX idx_restaurants_city_locality ON restaurants(city, locality) WHERE status = 'active';
CREATE INDEX idx_restaurants_cuisine ON restaurants USING GIN(cuisine_types);
CREATE INDEX idx_restaurants_rating ON restaurants(avg_rating DESC) WHERE status = 'active';

-- Menu categories
CREATE TABLE menu_categories (
    category_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    restaurant_id UUID NOT NULL REFERENCES restaurants(restaurant_id),
    name VARCHAR(100) NOT NULL,
    description TEXT,
    sort_order INT DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE
);

-- Menu items
CREATE TABLE menu_items (
    item_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    restaurant_id UUID NOT NULL REFERENCES restaurants(restaurant_id),
    category_id UUID REFERENCES menu_categories(category_id),
    name VARCHAR(200) NOT NULL,
    description TEXT,
    price_cents INT NOT NULL,
    discounted_price_cents INT,
    photo_url TEXT,
    is_veg BOOLEAN NOT NULL,
    is_bestseller BOOLEAN DEFAULT FALSE,
    spice_level INT, -- 1-5
    serves INT DEFAULT 1,
    preparation_time_min INT,
    calories INT,
    allergens VARCHAR(50)[],
    is_available BOOLEAN DEFAULT TRUE,
    sort_order INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_menu_items_restaurant ON menu_items(restaurant_id, is_available) WHERE is_available = TRUE;

-- Menu item customizations
CREATE TABLE item_customizations (
    customization_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    item_id UUID NOT NULL REFERENCES menu_items(item_id),
    group_name VARCHAR(100) NOT NULL, -- "Size", "Add-ons", "Spice Level"
    is_required BOOLEAN DEFAULT FALSE,
    min_selections INT DEFAULT 0,
    max_selections INT DEFAULT 1,
    options JSONB NOT NULL
    -- [{"name": "Regular", "price_cents": 0}, {"name": "Large", "price_cents": 5000}]
);

-- Orders
CREATE TABLE orders (
    order_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_number VARCHAR(20) UNIQUE NOT NULL, -- ZMT-XXXXXXXX
    customer_id UUID NOT NULL REFERENCES users(user_id),
    restaurant_id UUID NOT NULL REFERENCES restaurants(restaurant_id),
    delivery_partner_id UUID REFERENCES delivery_partners(partner_id),
    delivery_address_id UUID REFERENCES user_addresses(address_id),
    delivery_latitude DECIMAL(10, 7),
    delivery_longitude DECIMAL(10, 7),
    delivery_address_text TEXT,
    order_type VARCHAR(20) DEFAULT 'delivery', -- delivery, pickup, dine_in
    status VARCHAR(30) NOT NULL DEFAULT 'placed',
    -- placed, confirmed, preparing, ready_for_pickup, out_for_delivery, delivered, cancelled
    subtotal_cents INT NOT NULL,
    delivery_fee_cents INT DEFAULT 0,
    packaging_charge_cents INT DEFAULT 0,
    discount_cents INT DEFAULT 0,
    promo_code VARCHAR(30),
    taxes_cents INT NOT NULL,
    total_cents INT NOT NULL,
    payment_method VARCHAR(30), -- upi, card, wallet, cod
    payment_status VARCHAR(20) DEFAULT 'pending',
    special_instructions TEXT,
    estimated_delivery_time TIMESTAMP,
    actual_delivery_time TIMESTAMP,
    restaurant_confirmed_at TIMESTAMP,
    prepared_at TIMESTAMP,
    picked_up_at TIMESTAMP,
    delivered_at TIMESTAMP,
    cancelled_at TIMESTAMP,
    cancellation_reason TEXT,
    cancelled_by VARCHAR(20), -- customer, restaurant, system
    is_pro_order BOOLEAN DEFAULT FALSE,
    rating_restaurant INT,
    rating_delivery INT,
    rating_food INT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_orders_customer ON orders(customer_id, created_at DESC);
CREATE INDEX idx_orders_restaurant ON orders(restaurant_id, created_at DESC);
CREATE INDEX idx_orders_partner ON orders(delivery_partner_id, created_at DESC);
CREATE INDEX idx_orders_status ON orders(status) WHERE status NOT IN ('delivered', 'cancelled');
CREATE INDEX idx_orders_active ON orders(restaurant_id, status) WHERE status IN ('placed', 'confirmed', 'preparing');

-- Order items
CREATE TABLE order_items (
    order_item_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id UUID NOT NULL REFERENCES orders(order_id),
    item_id UUID NOT NULL REFERENCES menu_items(item_id),
    item_name VARCHAR(200) NOT NULL, -- denormalized for history
    quantity INT NOT NULL,
    unit_price_cents INT NOT NULL,
    total_price_cents INT NOT NULL,
    customizations JSONB, -- selected customizations
    special_instructions TEXT
);
CREATE INDEX idx_order_items_order ON order_items(order_id);

-- Delivery partners
CREATE TABLE delivery_partners (
    partner_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(200) NOT NULL,
    phone VARCHAR(15) UNIQUE NOT NULL,
    email VARCHAR(255),
    vehicle_type VARCHAR(20), -- bicycle, scooter, motorcycle, car
    vehicle_number VARCHAR(20),
    license_number VARCHAR(30),
    city VARCHAR(100) NOT NULL,
    current_latitude DECIMAL(10, 7),
    current_longitude DECIMAL(10, 7),
    is_online BOOLEAN DEFAULT FALSE,
    is_available BOOLEAN DEFAULT TRUE, -- not on a delivery
    current_order_id UUID,
    avg_rating DECIMAL(3,2) DEFAULT 5.0,
    total_deliveries INT DEFAULT 0,
    acceptance_rate DECIMAL(5,2) DEFAULT 100,
    earnings_today_cents INT DEFAULT 0,
    status VARCHAR(20) DEFAULT 'active', -- active, suspended, inactive
    last_location_update TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_partners_location ON delivery_partners USING GIST(
    ST_MakePoint(current_longitude, current_latitude)::geography
) WHERE is_online = TRUE AND is_available = TRUE;
CREATE INDEX idx_partners_city_available ON delivery_partners(city, is_available) 
    WHERE is_online = TRUE AND status = 'active';

-- Delivery tracking (time-series)
CREATE TABLE delivery_tracking (
    tracking_id BIGSERIAL PRIMARY KEY,
    order_id UUID NOT NULL,
    partner_id UUID NOT NULL,
    latitude DECIMAL(10, 7) NOT NULL,
    longitude DECIMAL(10, 7) NOT NULL,
    speed_kmh DECIMAL(5,1),
    bearing DECIMAL(5,1),
    accuracy_meters DECIMAL(5,1),
    recorded_at TIMESTAMP NOT NULL DEFAULT NOW()
) PARTITION BY RANGE (recorded_at);
-- Monthly partitions
CREATE TABLE delivery_tracking_2024_07 PARTITION OF delivery_tracking 
    FOR VALUES FROM ('2024-07-01') TO ('2024-08-01');

-- User addresses
CREATE TABLE user_addresses (
    address_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(user_id),
    label VARCHAR(30), -- home, work, other
    address_line1 VARCHAR(255) NOT NULL,
    address_line2 VARCHAR(255),
    landmark TEXT,
    latitude DECIMAL(10, 7) NOT NULL,
    longitude DECIMAL(10, 7) NOT NULL,
    city VARCHAR(100),
    pincode VARCHAR(10),
    is_default BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Reviews
CREATE TABLE restaurant_reviews (
    review_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id UUID REFERENCES orders(order_id),
    restaurant_id UUID NOT NULL REFERENCES restaurants(restaurant_id),
    user_id UUID NOT NULL REFERENCES users(user_id),
    rating INT NOT NULL CHECK (rating BETWEEN 1 AND 5),
    review_text TEXT,
    photos TEXT[], -- photo URLs
    food_items_reviewed UUID[], -- specific items
    is_delivery_review BOOLEAN DEFAULT TRUE,
    helpful_count INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_reviews_restaurant ON restaurant_reviews(restaurant_id, created_at DESC);

-- Promotions
CREATE TABLE promotions (
    promo_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code VARCHAR(30) UNIQUE NOT NULL,
    description TEXT,
    discount_type VARCHAR(20), -- percentage, flat, free_delivery
    discount_value INT, -- percentage (20) or flat amount in cents (5000)
    max_discount_cents INT,
    min_order_cents INT,
    valid_from TIMESTAMP NOT NULL,
    valid_to TIMESTAMP NOT NULL,
    max_uses INT,
    max_uses_per_user INT DEFAULT 1,
    applicable_restaurants UUID[], -- NULL = all
    applicable_cuisines VARCHAR(50)[],
    is_pro_only BOOLEAN DEFAULT FALSE,
    current_uses INT DEFAULT 0,
    status VARCHAR(20) DEFAULT 'active'
);
```

## 5. High-Level Design (HLD)

```
┌──────────────────────────────────────────────────────────────────────────────────────┐
│                              CLIENT APPLICATIONS                                      │
│  ┌───────────┐  ┌───────────┐  ┌──────────────┐  ┌─────────────────┐              │
│  │ Customer  │  │ Restaurant│  │  Delivery    │  │   Admin         │              │
│  │  App      │  │  Partner  │  │  Partner App │  │   Dashboard     │              │
│  │ (iOS/And) │  │  App/Web  │  │  (iOS/And)   │  │                 │              │
│  └─────┬─────┘  └─────┬─────┘  └──────┬───────┘  └───────┬─────────┘              │
│        │    GPS+WS     │               │ GPS               │                        │
└────────┼───────────────┼───────────────┼───────────────────┼────────────────────────┘
         │               │               │                   │
         ▼               ▼               ▼                   ▼
┌──────────────────────────────────────────────────────────────────────────────────────┐
│                          GATEWAY LAYER                                                 │
│  ┌──────────┐  ┌────────────┐  ┌──────────────┐  ┌────────────────┐                │
│  │  API GW  │  │  WebSocket │  │  Rate Limiter│  │  Geo-Router    │                │
│  │  (Kong)  │  │  Gateway   │  │              │  │  (city-based)  │                │
│  └──────────┘  └────────────┘  └──────────────┘  └────────────────┘                │
└───────────────────────────────────────┬──────────────────────────────────────────────┘
                                        │
    ┌────────────┬──────────────┬───────┼───────┬──────────────┬──────────────┐
    ▼            ▼              ▼       ▼       ▼              ▼              ▼
┌────────┐ ┌─────────┐ ┌───────────┐ ┌─────────┐ ┌──────────┐ ┌────────────────┐
│Search &│ │  Order  │ │ Delivery  │ │ Tracking│ │ Payment  │ │  Notification  │
│Catalog │ │ Service │ │Assignment │ │ Service │ │ Service  │ │   Service      │
│Service │ │         │ │  Service  │ │         │ │          │ │                │
│        │ │         │ │           │ │         │ │          │ │                │
│-Disc.  │ │-Cart    │ │-Matching  │ │-GPS ingest│-Process │ │ - Push         │
│-Menu   │ │-Place   │ │-Route opt │ │-ETA calc│ │-Refund  │ │ - SMS          │
│-Rank   │ │-Status  │ │-Cluster   │ │-Broadcast│-Wallet  │ │ - In-app       │
│-Review │ │-History │ │-Reassign  │ │-History │ │-Promo   │ │                │
└───┬────┘ └───┬─────┘ └─────┬─────┘ └────┬────┘ └─────┬────┘ └────────────────┘
    │          │              │            │            │
    ▼          ▼              ▼            ▼            ▼
┌──────────────────────────────────────────────────────────────────────────────────────┐
│                           DATA & STREAMING LAYER                                      │
│                                                                                       │
│ ┌────────────┐ ┌────────────┐ ┌─────────────┐ ┌──────────────┐ ┌───────────────┐  │
│ │Elasticsearch│ │ PostgreSQL │ │    Redis    │ │    Kafka     │ │ Apache Flink  │  │
│ │            │ │  (Sharded) │ │   Cluster   │ │              │ │               │  │
│ │- Restaurant│ │            │ │             │ │              │ │- ETA compute  │  │
│ │  search    │ │- Orders    │ │- Partner    │ │- order.events│ │- Demand pred  │  │
│ │- Menu srch │ │- Menus     │ │  locations  │ │- tracking    │ │- Fraud detect │  │
│ │- Geo index │ │- Users     │ │- Order state│ │- assignment  │ │- Surge calc   │  │
│ │            │ │- Partners  │ │- Restaurant │ │- notification│ │               │  │
│ └────────────┘ └────────────┘ │  status     │ └──────────────┘ └───────────────┘  │
│                               │- Cart cache │                                       │
│ ┌────────────┐ ┌────────────┐ │- Geofence   │ ┌──────────────┐                    │
│ │  TimescaleDB│ │    S3      │ └─────────────┘ │   ML Models  │                    │
│ │ (Tracking  │ │  (Photos)  │                  │ - ETA pred   │                    │
│ │  time-srs) │ │            │                  │ - Ranking    │                    │
│ └────────────┘ └────────────┘                  │ - Fraud      │                    │
│                                                 └──────────────┘                    │
└──────────────────────────────────────────────────────────────────────────────────────┘
```

## 6. Low-Level Design (LLD) - APIs

### Restaurant Search API
```
POST /api/v1/search/restaurants
Request:
{
    "latitude": 19.0760,
    "longitude": 72.8777,
    "radius_km": 5,
    "query": "biryani",
    "filters": {
        "cuisines": ["biryani", "north_indian"],
        "veg_only": false,
        "rating_min": 4.0,
        "cost_for_two_max": 800,
        "delivery_time_max": 40,
        "offers_available": true,
        "zomato_pro": true
    },
    "sort": "relevance",
    "page": 1,
    "page_size": 20
}

Response:
{
    "restaurants": [
        {
            "restaurant_id": "rest_abc",
            "name": "Paradise Biryani",
            "cuisines": ["Biryani", "North Indian", "Mughlai"],
            "rating": 4.5,
            "total_ratings": 12500,
            "cost_for_two": 600,
            "delivery_time_min": 25,
            "delivery_fee": 30,
            "distance_km": 2.3,
            "thumbnail": "https://cdn.zomato.com/...",
            "is_open": true,
            "offers": ["60% off up to ₹120", "Free delivery"],
            "is_promoted": true,
            "promoted_position": 1,
            "pro_discount": 15,
            "tags": ["bestseller", "newly_opened"],
            "food_photos_count": 234
        }
    ],
    "total_results": 156,
    "applied_filters": {...},
    "promoted_count": 3
}
```

### Place Order API
```
POST /api/v1/orders
Request:
{
    "restaurant_id": "rest_abc",
    "items": [
        {
            "item_id": "item_001",
            "quantity": 2,
            "customizations": [
                {"group": "Size", "selected": "Full"},
                {"group": "Add-ons", "selected": ["Raita", "Extra Gravy"]}
            ],
            "special_instructions": "Less spicy"
        },
        {"item_id": "item_002", "quantity": 1, "customizations": []}
    ],
    "delivery_address_id": "addr_xyz",
    "payment_method": "upi",
    "promo_code": "ZOMATO60",
    "special_instructions": "Ring the bell",
    "tip_cents": 5000
}

Response:
{
    "order_id": "ord_789",
    "order_number": "ZMT-12345678",
    "status": "placed",
    "restaurant": {"name": "Paradise Biryani", "phone": "..."},
    "items": [...],
    "pricing": {
        "subtotal": 750,
        "delivery_fee": 30,
        "packaging": 20,
        "discount": -120,
        "taxes": 47,
        "tip": 50,
        "total": 777
    },
    "estimated_delivery": "2024-07-15T20:05:00+05:30",
    "estimated_time_minutes": 35,
    "tracking_url": "https://zomato.com/track/ord_789"
}
```

### Live Tracking API
```
// WebSocket: wss://tracking.zomato.com/orders/{order_id}

// Server pushes:
{
    "type": "location_update",
    "partner": {
        "name": "Rahul",
        "phone": "+91...",
        "photo": "...",
        "vehicle": "Scooter"
    },
    "location": {
        "latitude": 19.0765,
        "longitude": 72.8781,
        "bearing": 135,
        "speed_kmh": 22
    },
    "eta_minutes": 8,
    "distance_remaining_km": 1.2,
    "route_polyline": "encoded_polyline...",
    "timestamp": "2024-07-15T19:57:00Z"
}

// Status updates:
{
    "type": "status_update",
    "status": "out_for_delivery",
    "message": "Your order has been picked up!",
    "timestamp": "2024-07-15T19:50:00Z"
}
```

### Delivery Partner Assignment API (Internal)
```
POST /api/internal/v1/assignments/find
Request:
{
    "order_id": "ord_789",
    "restaurant_location": {"lat": 19.0740, "lng": 72.8760},
    "delivery_location": {"lat": 19.0810, "lng": 72.8830},
    "priority": "normal",  // or "pro_priority"
    "search_radius_km": 3
}

Response:
{
    "assigned_partner": {
        "partner_id": "dp_456",
        "name": "Rahul",
        "distance_to_restaurant_km": 0.8,
        "eta_to_restaurant_min": 5,
        "current_load": 0,  // other active orders
        "rating": 4.8
    },
    "assignment_attempts": 1,
    "total_candidates_evaluated": 12
}
```

## 7. Deep Dives

### Deep Dive 1: Restaurant Ranking (Personalized Search)

```python
class RestaurantRankingEngine:
    """
    Multi-factor ranking that considers:
    1. Relevance to query
    2. User personalization
    3. Distance & delivery time
    4. Quality (rating + review count)
    5. Business factors (promotion, commission)
    6. Real-time signals (currently busy, accepting orders)
    """
    
    def rank(self, restaurants: List[Restaurant], query: SearchQuery, user: User) -> List[Restaurant]:
        scored = []
        for rest in restaurants:
            score = self._compute_score(rest, query, user)
            scored.append((rest, score))
        
        # Inject promoted restaurants at designated positions
        scored.sort(key=lambda x: x[1], reverse=True)
        result = self._inject_promotions(scored, query)
        return result
    
    def _compute_score(self, rest: Restaurant, query: SearchQuery, user: User) -> float:
        score = 0.0
        
        # Relevance to query (25%)
        if query.text:
            text_score = self._text_relevance(rest, query.text)
            score += 0.25 * text_score
        else:
            score += 0.25 * 0.5  # neutral for browse
        
        # Distance & delivery time (25%)
        distance_score = 1.0 - min(rest.distance_km / query.radius_km, 1.0)
        delivery_time_score = 1.0 - min(rest.delivery_time_min / 60, 1.0)
        score += 0.15 * distance_score + 0.10 * delivery_time_score
        
        # Quality (20%)
        # Bayesian average to handle low review counts
        C = 3.8  # platform mean
        m = 30   # prior weight
        bayesian_rating = (rest.total_ratings * rest.avg_rating + m * C) / (rest.total_ratings + m)
        score += 0.15 * (bayesian_rating / 5.0)
        score += 0.05 * min(math.log1p(rest.total_ratings) / 10, 1.0)
        
        # Personalization (15%)
        user_pref_score = self._personalization_score(rest, user)
        score += 0.15 * user_pref_score
        
        # Business factors (10%)
        commission_boost = rest.commission_percent / 30.0  # normalize
        score += 0.05 * commission_boost
        score += 0.05 * (1.0 if rest.is_promoted else 0.0)
        
        # Real-time signals (5%)
        if rest.is_busy:
            score -= 0.03  # penalize busy restaurants (longer prep)
        if rest.is_new:
            score += 0.02  # boost new restaurants for discovery
        
        return score
    
    def _personalization_score(self, rest: Restaurant, user: User) -> float:
        """Score based on user's ordering history and preferences"""
        signals = 0.0
        
        # Cuisine preference (from order history)
        cuisine_match = len(set(rest.cuisines) & set(user.preferred_cuisines)) / max(len(rest.cuisines), 1)
        signals += 0.4 * cuisine_match
        
        # Price sensitivity
        price_match = 1.0 - abs(rest.cost_for_two - user.avg_order_value) / user.avg_order_value
        signals += 0.2 * max(0, price_match)
        
        # Previously ordered from this restaurant
        if rest.restaurant_id in user.order_history_restaurants:
            signals += 0.3
        
        # Collaborative filtering (users like you also ordered from...)
        cf_score = self.collaborative_filter.predict(user.user_id, rest.restaurant_id)
        signals += 0.1 * cf_score
        
        return min(1.0, signals)

    def _text_relevance(self, rest: Restaurant, query_text: str) -> float:
        """Elasticsearch BM25-based text relevance"""
        # Matches against: restaurant name, cuisine, menu item names, locality
        # Boosted: exact name match > cuisine match > item match
        pass  # Computed via ES query score
```

### Deep Dive 2: Delivery Optimization

```python
class DeliveryAssignmentEngine:
    """
    Assigns optimal delivery partner considering:
    1. Distance to restaurant
    2. Partner's current load (batching)
    3. ETA optimization
    4. Fairness (distribute orders evenly)
    5. Partner preferences/zone
    """
    
    async def assign_order(self, order: Order) -> Optional[DeliveryPartner]:
        # Find candidate partners
        candidates = await self._find_candidates(order)
        
        if not candidates:
            # Expand radius, retry after delay
            return await self._retry_with_expanded_radius(order)
        
        # Score and rank candidates
        scored = [(p, self._score_partner(p, order)) for p in candidates]
        scored.sort(key=lambda x: x[1], reverse=True)
        
        # Try top candidates (broadcast or sequential)
        for partner, score in scored[:3]:
            accepted = await self._offer_to_partner(partner, order, timeout=30)
            if accepted:
                await self._confirm_assignment(order, partner)
                return partner
        
        # No one accepted - queue for retry
        await self._queue_for_reassignment(order)
        return None
    
    async def _find_candidates(self, order: Order) -> List[DeliveryPartner]:
        """Find available partners near restaurant using geospatial query"""
        # Redis geospatial index for real-time partner locations
        nearby = await self.redis.georadius(
            "partner_locations",
            order.restaurant_longitude,
            order.restaurant_latitude,
            3,  # 3 km radius
            unit='km',
            sort='ASC',
            count=20
        )
        
        partner_ids = [p.member for p in nearby]
        
        # Filter: online, available, not at capacity
        available = await self._filter_available(partner_ids)
        return available
    
    def _score_partner(self, partner: DeliveryPartner, order: Order) -> float:
        """Score a partner for this specific order"""
        score = 0.0
        
        # Distance to restaurant (40%) - closer is better
        dist = haversine(partner.lat, partner.lng, order.restaurant_lat, order.restaurant_lng)
        score += 0.40 * (1.0 - min(dist / 3.0, 1.0))
        
        # Current load (20%) - prefer idle partners
        load_score = 1.0 - (partner.current_orders / partner.max_capacity)
        score += 0.20 * load_score
        
        # Route efficiency for batching (20%)
        if partner.current_orders > 0:
            batch_score = self._batch_efficiency(partner, order)
            score += 0.20 * batch_score
        else:
            score += 0.20 * 0.5
        
        # Fairness (10%) - partners who haven't had orders recently get priority
        idle_minutes = (now() - partner.last_order_time).total_seconds() / 60
        fairness = min(idle_minutes / 30, 1.0)
        score += 0.10 * fairness
        
        # Rating & reliability (10%)
        score += 0.10 * (partner.avg_rating / 5.0)
        
        return score
    
    def _batch_efficiency(self, partner: DeliveryPartner, new_order: Order) -> float:
        """
        Calculate if this new order can be efficiently batched with partner's current deliveries.
        Good batch: restaurant is on the way, delivery location is nearby existing drop.
        """
        if not partner.current_route:
            return 0.5
        
        # Calculate detour needed to add this order
        original_route_time = partner.current_route.estimated_time
        new_route = self._calculate_route_with_addition(partner.current_route, new_order)
        detour_time = new_route.estimated_time - original_route_time
        
        # Good batch if detour < 10 min
        if detour_time < 10:
            return 1.0 - (detour_time / 10)
        return 0.0

class ETAPredictionModel:
    """ML model for estimated delivery time"""
    
    def predict_eta(self, order: Order, partner: DeliveryPartner) -> int:
        """Returns estimated minutes until delivery"""
        features = {
            'distance_partner_to_restaurant_km': self._distance(partner, order.restaurant),
            'distance_restaurant_to_customer_km': self._distance(order.restaurant, order.delivery),
            'restaurant_prep_time_min': order.restaurant.avg_prep_time,
            'current_hour': datetime.now().hour,
            'day_of_week': datetime.now().weekday(),
            'is_peak_hour': self._is_peak(),
            'weather_condition': self._get_weather(),
            'traffic_congestion_score': self._get_traffic(order.city),
            'partner_current_load': partner.current_orders,
            'restaurant_current_orders': self._restaurant_queue_length(order.restaurant_id),
            'historical_route_time': self._get_historical_route_time(
                order.restaurant.location, order.delivery_location
            ),
        }
        
        return self.model.predict(features)  # Returns minutes
```

### Deep Dive 3: Real-Time Order Tracking Pipeline

```python
class TrackingPipeline:
    """
    Pipeline: Partner GPS → Kafka → Flink Processing → Redis → WebSocket → Client
    
    Requirements:
    - 500K partners sending location every 5 seconds
    - 100K location events/second
    - Sub-second propagation to customer app
    - ETA recalculation on every update
    """
    
    # Kafka producer on delivery partner app
    async def send_location(self, partner_id: str, lat: float, lng: float, 
                           speed: float, bearing: float):
        await self.kafka.produce('tracking.locations', {
            'partner_id': partner_id,
            'latitude': lat,
            'longitude': lng,
            'speed_kmh': speed,
            'bearing': bearing,
            'timestamp': time.time()
        }, key=partner_id)  # Partition by partner_id for ordering

class TrackingFlinkJob:
    """Apache Flink stream processing for tracking events"""
    
    def process_location(self, event: LocationEvent):
        partner_id = event.partner_id
        
        # 1. Update partner's current location in Redis (geospatial)
        self.redis.geoadd("partner_locations", event.longitude, event.latitude, partner_id)
        self.redis.hset(f"partner:{partner_id}", mapping={
            'lat': event.latitude, 'lng': event.longitude,
            'speed': event.speed_kmh, 'bearing': event.bearing,
            'updated_at': event.timestamp
        })
        
        # 2. Check if partner has active order(s)
        active_orders = self.redis.smembers(f"partner_orders:{partner_id}")
        
        for order_id in active_orders:
            # 3. Recalculate ETA
            order_info = self.redis.hgetall(f"order:{order_id}")
            new_eta = self._recalculate_eta(event, order_info)
            
            # 4. Store updated tracking for WebSocket broadcast
            self.redis.publish(f"tracking:{order_id}", json.dumps({
                'type': 'location_update',
                'location': {'lat': event.latitude, 'lng': event.longitude},
                'speed_kmh': event.speed_kmh,
                'bearing': event.bearing,
                'eta_minutes': new_eta,
                'timestamp': event.timestamp
            }))
            
            # 5. Check geofence (near restaurant pickup / near customer)
            self._check_geofence(event, order_info)
    
    def _check_geofence(self, event, order_info):
        """Auto-detect when partner arrives at restaurant or customer"""
        rest_lat, rest_lng = float(order_info['rest_lat']), float(order_info['rest_lng'])
        cust_lat, cust_lng = float(order_info['cust_lat']), float(order_info['cust_lng'])
        
        dist_to_restaurant = haversine(event.latitude, event.longitude, rest_lat, rest_lng)
        dist_to_customer = haversine(event.latitude, event.longitude, cust_lat, cust_lng)
        
        if dist_to_restaurant < 0.05 and order_info['status'] == 'assigned':  # 50m
            self._trigger_event('partner_arrived_restaurant', order_info)
        elif dist_to_customer < 0.05 and order_info['status'] == 'out_for_delivery':
            self._trigger_event('partner_near_customer', order_info)
```

**Kafka Configuration**:
```yaml
topics:
  tracking.locations:
    partitions: 128  # High parallelism for 100K events/s
    replication.factor: 2  # Lower replication OK (ephemeral data)
    retention.ms: 3600000  # 1 hour only
    compression.type: snappy
    segment.bytes: 104857600  # 100MB segments
    
  order.events:
    partitions: 64
    replication.factor: 3
    retention.ms: 604800000  # 7 days
    min.insync.replicas: 2
    
  assignment.events:
    partitions: 32
    replication.factor: 3
    retention.ms: 86400000
```

## 8. Component Optimization

### Redis Architecture for Location
```python
# Geospatial index for partner discovery
# Key: "partner_locations" (GEOADD)
# Enables: GEORADIUS queries for assignment

# Real-time order state (Hash)
# Key: "order:{order_id}"
# Fields: status, partner_id, rest_lat, rest_lng, cust_lat, cust_lng, eta

# Pub/Sub for WebSocket fan-out
# Channel: "tracking:{order_id}"
# Subscribers: WebSocket servers handling that customer's connection

# Partner availability bitmap
# Key: "partners_online:{city}"
# Type: SET of partner_ids

REDIS_CLUSTER_CONFIG = {
    "nodes": 30,
    "shards": 15,
    "memory_per_node_gb": 32,
    "total_memory_gb": 480,
    "eviction": "allkeys-lru",
    "persistence": "none",  # Pure cache + ephemeral state
}
```

### Search Optimization (Elasticsearch)
```json
{
    "settings": {
        "number_of_shards": 10,
        "number_of_replicas": 2,
        "analysis": {
            "analyzer": {
                "food_analyzer": {
                    "type": "custom",
                    "tokenizer": "standard",
                    "filter": ["lowercase", "food_synonyms", "stemmer"]
                }
            },
            "filter": {
                "food_synonyms": {
                    "type": "synonym",
                    "synonyms": [
                        "biryani,briyani,biriyani",
                        "pizza,pitza",
                        "naan,nan,naan bread"
                    ]
                }
            }
        }
    }
}
```

## 9. Observability

### Key Metrics
```yaml
metrics:
  - name: order_placement_latency_ms
    type: histogram
    labels: [city, payment_method]
    
  - name: delivery_assignment_time_seconds
    type: histogram
    labels: [city, priority]
    
  - name: eta_accuracy_error_minutes
    type: histogram
    labels: [city, time_of_day]
    description: "abs(actual_delivery_time - predicted_eta)"
    
  - name: partner_utilization_rate
    type: gauge
    labels: [city, vehicle_type]
    
  - name: restaurant_acceptance_rate
    type: gauge
    labels: [city]
    
  - name: tracking_propagation_delay_ms
    type: histogram
    description: "Time from GPS event to customer app display"
    
  - name: orders_per_second
    type: gauge
    labels: [city, status]
    
  - name: active_deliveries
    type: gauge
    labels: [city]
```

### Alerting
```yaml
alerts:
  - name: AssignmentFailureHigh
    condition: rate(assignment_failures[5m]) / rate(orders_placed[5m]) > 0.1
    severity: critical
    action: "Expand search radius, activate surge incentives"
    
  - name: ETAInaccurate
    condition: avg(eta_accuracy_error_minutes) > 15
    for: 10m
    severity: warning
    
  - name: TrackingLag
    condition: tracking_propagation_delay_ms_p95 > 5000
    severity: critical
    
  - name: PartnerSupplyLow
    condition: available_partners / active_orders < 0.5
    for: 5m
    severity: critical
    action: "Trigger surge pricing, send partner incentive notifications"
```

## 10. Considerations

### Surge Pricing / Dynamic Delivery Fee
```python
class SurgePricingEngine:
    def calculate_surge(self, city: str, locality: str) -> float:
        """Calculate surge multiplier based on demand/supply ratio"""
        demand = self.redis.get(f"demand:{city}:{locality}")  # orders/min
        supply = self.redis.get(f"supply:{city}:{locality}")  # available partners
        
        ratio = float(demand) / max(float(supply), 1)
        
        if ratio > 3.0:
            return 2.0  # 2x surge
        elif ratio > 2.0:
            return 1.5
        elif ratio > 1.5:
            return 1.2
        return 1.0
```

### Order Batching (Multiple Orders, One Partner)
- Partner picks up from 2 restaurants on same route → delivers both
- Reduces cost per delivery by 30-40%
- Constraint: max 15 min additional delay for first customer
- Algorithm: Check if new order's restaurant is within 1km detour of existing route

### Restaurant Busy Detection
- Track order acceptance time → if increasing, restaurant is backing up
- Auto-increase estimated prep time
- If rejection rate spikes → temporarily pause orders for that restaurant

### Failure Handling
- **Payment failure**: Hold order, retry 2x, then cancel with notification
- **Restaurant rejects**: Auto-assign to nearby alternative (if customer consents)
- **Partner unavailable mid-delivery**: Reassign to nearest available partner
- **Customer unreachable**: Partner waits 5 min → marks as delivered (photo proof)

### Data Retention
```
Active orders: Hot storage (Redis + PostgreSQL primary)
Completed orders (30 days): Warm storage (PostgreSQL)
Historical orders (30d+): Cold storage (S3 + Athena for analytics)
Tracking data: 7 days hot, then archived
Reviews: Permanent (PostgreSQL)
```

## 11. System Scale Numbers

```
Peak dinner (7-9 PM):
- Orders/sec: 3000
- Active deliveries: 500K
- Partner location updates: 100K/sec
- WebSocket connections: 1.5M
- Kafka throughput: 200K events/sec
- Redis ops: 2M/sec
- ES queries: 50K/sec
- DB writes: 10K/sec
```
