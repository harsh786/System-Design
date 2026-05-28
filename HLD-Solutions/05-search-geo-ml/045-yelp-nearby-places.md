# Yelp / Nearby Places System Design

## 1. Problem Statement

Design a location-based service like Yelp that enables users to discover nearby businesses (restaurants, shops, services), view reviews and ratings, filter by attributes (cuisine, price, hours), see results on a map, and check in. The system must support geospatial queries with sub-200ms latency across 200M+ business listings.

---

## 2. Functional Requirements

| ID | Requirement | Description |
|----|-------------|-------------|
| FR1 | Nearby Search | Find businesses within radius of user's location |
| FR2 | Text + Geo Search | Combine text query ("sushi") with location proximity |
| FR3 | Filters | Filter by cuisine, price range ($ - $$$$), open now, rating |
| FR4 | Reviews & Ratings | Display reviews, photos, aggregate ratings |
| FR5 | Map View | Show results on interactive map with clustering |
| FR6 | Business Details | Hours, menu, phone, website, photos, Q&A |
| FR7 | Check-ins | Users check in at businesses |
| FR8 | Recommendations | Personalized "you might like" suggestions |
| FR9 | Sort Options | Sort by distance, rating, most reviewed, best match |
| FR10 | Business Registration | Business owners claim/manage listings |

## 3. Non-Functional Requirements

| ID | Requirement | Target |
|----|-------------|--------|
| NFR1 | Latency | p50 < 100ms, p99 < 300ms for nearby search |
| NFR2 | Availability | 99.99% uptime |
| NFR3 | Throughput | 20K QPS for search, 5K QPS for reviews |
| NFR4 | Scale | 200M+ businesses globally |
| NFR5 | Accuracy | Geospatial precision within 10 meters |
| NFR6 | Freshness | Business hours/status updates within minutes |
| NFR7 | Global | Support all countries with local business data |

---

## 4. Capacity Estimation

### Traffic
```
Daily active users:        50 million
Searches per user/day:     5
Total searches/day:        250 million
Search QPS:                250M / 86400 ≈ 2,900 QPS
Peak (3x):                 ~9,000 QPS
Review reads/day:          500 million (multiple per search)
Review read QPS:           ~5,800 QPS
Check-ins/day:             10 million
New reviews/day:           2 million
```

### Storage
```
Businesses:                200 million
Business document size:    2KB (metadata, hours, attributes)
Business store:            200M × 2KB = 400 GB
Reviews:                   5 billion total
Review size:               500 bytes average
Review store:              5B × 500 bytes = 2.5 TB
Photos:                    2 billion (stored in object storage)
Photo metadata:            2B × 200 bytes = 400 GB
Geospatial index:          200M × 50 bytes = 10 GB (coordinates + geohash)
User profiles:             200M users × 1KB = 200 GB
Check-in history:          10B check-ins × 50 bytes = 500 GB
```

### Bandwidth
```
Inbound (searches):        9K × 200 bytes = 1.8 MB/s
Outbound (results):        9K × 20 results × 500 bytes = 90 MB/s
Photo serving:             CDN (separate infrastructure)
```

### Infrastructure
```
Search cluster:            30 nodes (Elasticsearch/PostGIS)
Database:                  PostgreSQL with PostGIS (sharded)
Cache (Redis):             20 nodes, 500 GB total
CDN:                       Global edge network for photos/static
Object storage (S3):       Photos, ~500 TB total
```

---

## 5. Data Modeling

### Business Listing
```sql
CREATE TABLE businesses (
    business_id      UUID PRIMARY KEY,
    name             VARCHAR(200) NOT NULL,
    slug             VARCHAR(200) UNIQUE,
    category_ids     INTEGER[] NOT NULL,        -- [restaurants, japanese, sushi]
    location         GEOGRAPHY(POINT, 4326) NOT NULL,  -- PostGIS point
    latitude         DECIMAL(10, 7) NOT NULL,
    longitude        DECIMAL(10, 7) NOT NULL,
    geohash          VARCHAR(12) NOT NULL,      -- Precomputed geohash
    h3_index         BIGINT NOT NULL,           -- H3 cell at resolution 9
    address          JSONB NOT NULL,            -- {street, city, state, zip, country}
    phone            VARCHAR(20),
    website          VARCHAR(500),
    price_level      SMALLINT CHECK (price_level BETWEEN 1 AND 4),  -- $ to $$$$
    
    -- Aggregate ratings
    rating_avg       DECIMAL(2,1) DEFAULT 0.0,
    rating_count     INTEGER DEFAULT 0,
    
    -- Hours
    hours            JSONB,                    -- {"mon": {"open": "09:00", "close": "22:00"}, ...}
    is_open_now      BOOLEAN,                  -- Precomputed, updated every minute
    
    -- Attributes
    attributes       JSONB,                    -- {wifi: true, parking: "street", delivery: true}
    
    -- Status
    is_claimed       BOOLEAN DEFAULT FALSE,
    is_active        BOOLEAN DEFAULT TRUE,
    
    created_at       TIMESTAMP DEFAULT NOW(),
    updated_at       TIMESTAMP DEFAULT NOW()
);

-- Geospatial index
CREATE INDEX idx_businesses_geo ON businesses USING GIST(location);
-- Geohash index for range queries
CREATE INDEX idx_businesses_geohash ON businesses(geohash text_pattern_ops);
-- H3 index
CREATE INDEX idx_businesses_h3 ON businesses(h3_index);
-- Category + location compound
CREATE INDEX idx_businesses_category_geo ON businesses USING GIST(location) WHERE is_active = TRUE;
```

### Review
```sql
CREATE TABLE reviews (
    review_id        UUID PRIMARY KEY,
    business_id      UUID NOT NULL REFERENCES businesses(business_id),
    user_id          UUID NOT NULL REFERENCES users(user_id),
    rating           SMALLINT NOT NULL CHECK (rating BETWEEN 1 AND 5),
    text             TEXT,
    photos           UUID[],                   -- References to photo objects
    useful_count     INTEGER DEFAULT 0,
    funny_count      INTEGER DEFAULT 0,
    cool_count       INTEGER DEFAULT 0,
    response_text    TEXT,                     -- Business owner response
    response_at      TIMESTAMP,
    created_at       TIMESTAMP DEFAULT NOW(),
    updated_at       TIMESTAMP
);

CREATE INDEX idx_reviews_business ON reviews(business_id, created_at DESC);
CREATE INDEX idx_reviews_user ON reviews(user_id, created_at DESC);
CREATE INDEX idx_reviews_rating ON reviews(business_id, rating);
```

### Category Hierarchy
```sql
CREATE TABLE categories (
    category_id      INTEGER PRIMARY KEY,
    name             VARCHAR(100) NOT NULL,
    slug             VARCHAR(100) UNIQUE,
    parent_id        INTEGER REFERENCES categories(category_id),
    level            SMALLINT,                 -- 0=root, 1=mid, 2=leaf
    search_aliases   TEXT[]                    -- Alternative names for search
);

-- Example hierarchy:
-- Restaurants (level 0)
--   ├── Japanese (level 1)
--   │   ├── Sushi (level 2)
--   │   ├── Ramen (level 2)
--   ├── Italian (level 1)
--   │   ├── Pizza (level 2)
```

### Elasticsearch Business Document
```json
{
    "business_id": "abc-123",
    "name": "Sushi Nakazawa",
    "name_autocomplete": "Sushi Nakazawa",
    "categories": ["restaurants", "japanese", "sushi"],
    "location": {"lat": 40.7328, "lon": -74.0059},
    "geohash": "dr5ru7",
    "h3_index": 617700169958293503,
    "price_level": 4,
    "rating_avg": 4.8,
    "rating_count": 2456,
    "is_open_now": true,
    "hours": {...},
    "attributes": {
        "reservations": true,
        "delivery": false,
        "outdoor_seating": false,
        "wifi": true
    },
    "city": "New York",
    "state": "NY",
    "country": "US",
    "popularity_score": 0.92
}
```

---

## 6. High-Level Design (HLD)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    YELP / NEARBY PLACES ARCHITECTURE                          │
└─────────────────────────────────────────────────────────────────────────────┘

                         ┌──────────────┐
                         │  Mobile App  │
                         │  / Web       │
                         └──────┬───────┘
                                │
                         ┌──────▼───────┐
                         │  CDN + LB    │── Photos, static assets
                         │  (CloudFront)│
                         └──────┬───────┘
                                │
                    ┌───────────▼───────────┐
                    │   API Gateway          │
                    │  (Auth, Rate Limit)    │
                    └───────────┬───────────┘
                                │
         ┌──────────────────────┼──────────────────────┐
         │                      │                      │
  ┌──────▼──────┐      ┌───────▼───────┐     ┌───────▼───────┐
  │   Search    │      │   Business    │     │   Review      │
  │   Service   │      │   Service     │     │   Service     │
  └──────┬──────┘      └───────┬───────┘     └───────┬───────┘
         │                      │                      │
         │              ┌───────▼───────┐              │
         │              │   User        │              │
         │              │   Service     │              │
         │              └───────────────┘              │
         │                                             │
  ┌──────▼──────┐                             ┌───────▼───────┐
  │Elasticsearch│                             │  PostgreSQL   │
  │(Geo Index + │                             │  (Reviews +   │
  │ Text Search)│                             │   Users)      │
  └─────────────┘                             └───────────────┘
         │
  ┌──────▼──────┐      ┌───────────────┐     ┌───────────────┐
  │  Redis      │      │  PostgreSQL   │     │   S3          │
  │  (Cache +   │      │  + PostGIS    │     │  (Photos)     │
  │  Geo)       │      │  (Businesses) │     └───────────────┘
  └─────────────┘      └───────────────┘

═══════════════════ SUPPORTING SERVICES ════════════════════════

  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐   ┌──────────────┐
  │ Notification│   │Recommendation│   │  Check-in   │   │  Map Tile    │
  │ Service     │   │  Engine      │   │  Service    │   │  Service     │
  └─────────────┘   └─────────────┘   └─────────────┘   └──────────────┘

═══════════════════ DATA PIPELINE ══════════════════════════════

  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐
  │  Kafka      │──▶│  Spark/     │──▶│  Analytics  │
  │  (Events)   │   │  Flink      │   │  (Metrics)  │
  └─────────────┘   └─────────────┘   └─────────────┘
```

### Component Responsibilities

| Component | Role |
|-----------|------|
| Search Service | Geospatial + text search, filter, rank results |
| Business Service | CRUD for business listings, hours, attributes |
| Review Service | Submit/read reviews, ratings aggregation |
| User Service | Authentication, profiles, preferences |
| Elasticsearch | Geospatial index + full-text search |
| Redis | Cache popular queries, geospatial commands (GEOSEARCH) |
| PostgreSQL + PostGIS | Source of truth for business/review data |
| Recommendation Engine | Personalized suggestions based on history |
| Check-in Service | Record/display user check-ins |

---

## 7. Low-Level Design (LLD) - APIs

### Nearby Search API
```
GET /v1/search?q={query}&lat={latitude}&lng={longitude}&radius={meters}
    &category={cat}&price={1,2,3,4}&rating={min}&open_now={true}
    &sort={distance|rating|best_match|review_count}
    &page={page}&limit={limit}

Headers:
  Authorization: Bearer <token>
  X-Device-Location: lat,lng (real-time location)

Response 200:
{
    "query": "sushi",
    "location": {"lat": 40.7328, "lng": -74.0059},
    "radius_meters": 5000,
    "total_results": 47,
    "results": [
        {
            "business_id": "abc-123",
            "name": "Sushi Nakazawa",
            "categories": ["Sushi", "Japanese"],
            "distance_meters": 350,
            "rating": 4.8,
            "review_count": 2456,
            "price_level": 4,
            "is_open": true,
            "closes_at": "23:00",
            "image_url": "https://cdn.yelp.com/...",
            "location": {"lat": 40.7335, "lng": -74.0048},
            "snippet": "Amazing omakase experience. The fish is incredibly fresh...",
            "delivery": false,
            "reservation_url": "https://..."
        }
    ],
    "map_bounds": {
        "ne": {"lat": 40.76, "lng": -73.97},
        "sw": {"lat": 40.70, "lng": -74.04}
    },
    "filters_applied": {
        "category": "sushi",
        "open_now": true
    },
    "facets": {
        "categories": [
            {"name": "Sushi", "count": 23},
            {"name": "Japanese", "count": 35},
            {"name": "Ramen", "count": 12}
        ],
        "price_level": [
            {"level": 1, "count": 5},
            {"level": 2, "count": 18},
            {"level": 3, "count": 15},
            {"level": 4, "count": 9}
        ],
        "features": [
            {"name": "Delivery", "count": 28},
            {"name": "Outdoor Seating", "count": 19}
        ]
    }
}
```

### Business Details API
```
GET /v1/businesses/{business_id}

Response 200:
{
    "business_id": "abc-123",
    "name": "Sushi Nakazawa",
    "categories": ["Sushi", "Japanese"],
    "location": {
        "address": "23 Commerce St",
        "city": "New York",
        "state": "NY",
        "zip": "10014",
        "coordinates": {"lat": 40.7335, "lng": -74.0048}
    },
    "rating": 4.8,
    "review_count": 2456,
    "price_level": 4,
    "phone": "+1-212-924-2212",
    "website": "https://sushinakazawa.com",
    "hours": {
        "monday": {"open": "17:00", "close": "22:00"},
        "tuesday": {"open": "17:00", "close": "22:00"}
    },
    "is_open_now": true,
    "attributes": {
        "reservations": true,
        "wifi": "free",
        "parking": "street",
        "ambience": "upscale",
        "noise_level": "quiet"
    },
    "photos": [
        {"url": "https://...", "caption": "Omakase platter", "user_id": "..."}
    ],
    "recent_reviews": [...],
    "rating_distribution": [1890, 342, 112, 67, 45],
    "popular_times": {"friday": [0,0,0,...,5,8,10,10,9,7,3,0]}
}
```

### Submit Review API
```
POST /v1/businesses/{business_id}/reviews
{
    "rating": 5,
    "text": "Best sushi in NYC. The omakase is worth every penny...",
    "photos": ["photo_upload_id_1", "photo_upload_id_2"]
}

Response 201:
{
    "review_id": "rev-456",
    "created_at": "2024-01-15T18:30:00Z"
}
```

---

## 8. Deep Dive: Geospatial Indexing

### Geohash vs S2 vs H3

```python
class GeospatialIndexing:
    """
    Comparison of geospatial indexing approaches:
    
    1. Geohash: 
       - Divides Earth into grid of cells encoded as base-32 strings
       - Longer hash = smaller cell (precision)
       - Adjacent cells share prefix (mostly) - good for range queries
       - Problem: Edge cases at cell boundaries
       
    2. S2 Geometry (Google):
       - Maps sphere surface to cells on a Hilbert curve
       - Hierarchical: 30 levels (0 = entire face, 30 = ~1cm²)
       - No pole singularity, uniform cell sizes
       - Better coverage queries (covering a region with minimal cells)
    
    3. H3 (Uber):
       - Hexagonal hierarchical grid
       - Each hexagon has exactly 6 equidistant neighbors
       - Better for k-ring (nearby) operations
       - 16 resolutions (0 = ~4M km², 15 = ~0.9 m²)
    """
    
    # === GEOHASH IMPLEMENTATION ===
    
    BASE32 = '0123456789bcdefghjkmnpqrstuvwxyz'
    
    def encode_geohash(self, lat: float, lng: float, precision: int = 9) -> str:
        """
        Encode lat/lng to geohash string.
        
        Precision levels:
        - 4: ~39km × 20km (city-level)
        - 5: ~5km × 5km (neighborhood)
        - 6: ~1.2km × 600m (block level)
        - 7: ~150m × 150m (street level)
        - 8: ~38m × 19m (building level)
        - 9: ~5m × 5m (exact location)
        """
        lat_range = (-90.0, 90.0)
        lng_range = (-180.0, 180.0)
        
        geohash = []
        bits = 0
        bit_count = 0
        is_lng = True  # Alternate lng/lat bits
        
        while len(geohash) < precision:
            if is_lng:
                mid = (lng_range[0] + lng_range[1]) / 2
                if lng >= mid:
                    bits = (bits << 1) | 1
                    lng_range = (mid, lng_range[1])
                else:
                    bits = (bits << 1) | 0
                    lng_range = (lng_range[0], mid)
            else:
                mid = (lat_range[0] + lat_range[1]) / 2
                if lat >= mid:
                    bits = (bits << 1) | 1
                    lat_range = (mid, lat_range[1])
                else:
                    bits = (bits << 1) | 0
                    lat_range = (lat_range[0], mid)
            
            is_lng = not is_lng
            bit_count += 1
            
            if bit_count == 5:
                geohash.append(self.BASE32[bits])
                bits = 0
                bit_count = 0
        
        return ''.join(geohash)
    
    def get_neighbors(self, geohash: str) -> list[str]:
        """
        Get 8 neighboring geohash cells.
        Needed because a nearby point might be in an adjacent cell.
        """
        lat, lng = self.decode_geohash(geohash)
        precision = len(geohash)
        
        # Approximate cell dimensions at this precision
        lat_err = 90.0 / (2 ** (precision * 5 // 2))
        lng_err = 180.0 / (2 ** ((precision * 5 + 1) // 2))
        
        neighbors = []
        for dlat in [-lat_err * 2, 0, lat_err * 2]:
            for dlng in [-lng_err * 2, 0, lng_err * 2]:
                if dlat == 0 and dlng == 0:
                    continue
                neighbor = self.encode_geohash(lat + dlat, lng + dlng, precision)
                neighbors.append(neighbor)
        
        return neighbors
    
    def search_nearby_geohash(self, lat: float, lng: float, 
                             radius_meters: float, businesses_index: dict) -> list:
        """
        Geohash-based proximity search:
        1. Determine geohash precision that covers radius
        2. Get cell + neighboring cells
        3. Fetch all businesses in those cells
        4. Filter by exact distance
        5. Sort by distance
        """
        # Determine precision based on radius
        precision = self._radius_to_precision(radius_meters)
        
        # Get center cell and neighbors
        center_hash = self.encode_geohash(lat, lng, precision)
        search_cells = [center_hash] + self.get_neighbors(center_hash)
        
        # Fetch candidates from all cells
        candidates = []
        for cell in search_cells:
            if cell in businesses_index:
                candidates.extend(businesses_index[cell])
        
        # Filter by exact distance
        results = []
        for business in candidates:
            dist = self.haversine_distance(lat, lng, business.lat, business.lng)
            if dist <= radius_meters:
                results.append((business, dist))
        
        # Sort by distance
        results.sort(key=lambda x: x[1])
        return results
    
    def _radius_to_precision(self, radius_meters: float) -> int:
        """Map search radius to appropriate geohash precision"""
        if radius_meters > 40000:
            return 4
        elif radius_meters > 5000:
            return 5
        elif radius_meters > 1000:
            return 6
        elif radius_meters > 150:
            return 7
        else:
            return 8
    
    # === H3 IMPLEMENTATION ===
    
    def search_nearby_h3(self, lat: float, lng: float, 
                        radius_meters: float, h3_index: dict) -> list:
        """
        H3-based proximity search using k-ring.
        
        Advantages over geohash:
        - Hexagons have uniform neighbor distances
        - No edge effects (all neighbors equidistant from center)
        - k_ring(k) gives all cells within k hops
        """
        import h3
        
        # Determine H3 resolution based on radius
        resolution = self._radius_to_h3_resolution(radius_meters)
        
        # Get center cell
        center_cell = h3.latlng_to_cell(lat, lng, resolution)
        
        # Get k-ring (all cells within k hops)
        k = self._radius_to_k_ring(radius_meters, resolution)
        search_cells = h3.grid_disk(center_cell, k)
        
        # Fetch candidates
        candidates = []
        for cell in search_cells:
            if cell in h3_index:
                candidates.extend(h3_index[cell])
        
        # Filter by exact distance and sort
        results = []
        for business in candidates:
            dist = self.haversine_distance(lat, lng, business.lat, business.lng)
            if dist <= radius_meters:
                results.append((business, dist))
        
        results.sort(key=lambda x: x[1])
        return results
    
    def _radius_to_h3_resolution(self, radius_meters: float) -> int:
        """
        H3 resolutions and approximate edge lengths:
        Res 4: ~22km edge (city)
        Res 5: ~8km edge
        Res 6: ~3.2km edge
        Res 7: ~1.2km edge (neighborhood)
        Res 8: ~460m edge
        Res 9: ~174m edge (block)
        """
        if radius_meters > 20000:
            return 5
        elif radius_meters > 5000:
            return 6
        elif radius_meters > 2000:
            return 7
        elif radius_meters > 500:
            return 8
        else:
            return 9
    
    @staticmethod
    def haversine_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
        """
        Calculate distance between two points on Earth in meters.
        Uses Haversine formula (accurate for small distances).
        """
        import math
        R = 6371000  # Earth radius in meters
        
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lng2 - lng1)
        
        a = (math.sin(dphi / 2) ** 2 + 
             math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        
        return R * c


class QuadTree:
    """
    QuadTree for spatial indexing of businesses.
    
    Recursively subdivides 2D space into 4 quadrants.
    Good for non-uniform distributions (cities have more businesses than rural).
    
    Operations:
    - Insert: O(log n)
    - Range query: O(√n + k) where k = results
    - Nearest neighbor: O(log n)
    """
    
    MAX_POINTS_PER_NODE = 50  # Split when exceeded
    MAX_DEPTH = 20
    
    def __init__(self, bounds: tuple, depth: int = 0):
        """
        bounds: (min_lat, min_lng, max_lat, max_lng)
        """
        self.bounds = bounds
        self.depth = depth
        self.points = []       # [(lat, lng, business_id), ...]
        self.children = None   # [NW, NE, SW, SE] when split
        self.is_leaf = True
    
    def insert(self, lat: float, lng: float, business_id: str) -> bool:
        """Insert a business into the QuadTree"""
        if not self._contains(lat, lng):
            return False
        
        if self.is_leaf:
            self.points.append((lat, lng, business_id))
            
            # Split if over capacity
            if len(self.points) > self.MAX_POINTS_PER_NODE and self.depth < self.MAX_DEPTH:
                self._split()
            
            return True
        else:
            # Route to appropriate child
            for child in self.children:
                if child.insert(lat, lng, business_id):
                    return True
            return False
    
    def range_query(self, center_lat: float, center_lng: float, 
                   radius_meters: float) -> list:
        """
        Find all businesses within radius of center point.
        Prunes entire subtrees that don't intersect the search circle.
        """
        results = []
        self._range_search(center_lat, center_lng, radius_meters, results)
        return results
    
    def _range_search(self, lat: float, lng: float, radius: float, results: list):
        """Recursive range search with pruning"""
        # Check if this node's bounds intersect the search circle
        if not self._intersects_circle(lat, lng, radius):
            return  # Prune entire subtree
        
        if self.is_leaf:
            # Check each point
            for plat, plng, bid in self.points:
                dist = GeospatialIndexing.haversine_distance(lat, lng, plat, plng)
                if dist <= radius:
                    results.append((bid, dist, plat, plng))
        else:
            # Recurse into children
            for child in self.children:
                child._range_search(lat, lng, radius, results)
    
    def _split(self):
        """Split leaf node into 4 children"""
        min_lat, min_lng, max_lat, max_lng = self.bounds
        mid_lat = (min_lat + max_lat) / 2
        mid_lng = (min_lng + max_lng) / 2
        
        self.children = [
            QuadTree((mid_lat, min_lng, max_lat, mid_lng), self.depth + 1),  # NW
            QuadTree((mid_lat, mid_lng, max_lat, max_lng), self.depth + 1),  # NE
            QuadTree((min_lat, min_lng, mid_lat, mid_lng), self.depth + 1),  # SW
            QuadTree((min_lat, mid_lng, mid_lat, max_lng), self.depth + 1),  # SE
        ]
        
        # Redistribute points
        for lat, lng, bid in self.points:
            for child in self.children:
                if child.insert(lat, lng, bid):
                    break
        
        self.points = []
        self.is_leaf = False
    
    def _contains(self, lat: float, lng: float) -> bool:
        min_lat, min_lng, max_lat, max_lng = self.bounds
        return min_lat <= lat <= max_lat and min_lng <= lng <= max_lng
    
    def _intersects_circle(self, center_lat: float, center_lng: float, 
                          radius_meters: float) -> bool:
        """Check if bounding box intersects search circle (approximate)"""
        min_lat, min_lng, max_lat, max_lng = self.bounds
        
        # Find closest point on rectangle to circle center
        closest_lat = max(min_lat, min(center_lat, max_lat))
        closest_lng = max(min_lng, min(center_lng, max_lng))
        
        dist = GeospatialIndexing.haversine_distance(
            center_lat, center_lng, closest_lat, closest_lng
        )
        
        return dist <= radius_meters
```

---

## 9. Deep Dive: Location-Aware Ranking

```python
class LocationAwareRanker:
    """
    Rank nearby businesses by combining:
    1. Distance (closer = better, with decay)
    2. Rating (higher = better, weighted by count)
    3. Text relevance (if query provided)
    4. Popularity (check-ins, reviews, photos)
    5. Personalization (user preferences)
    6. Business quality signals (claimed, complete profile)
    """
    
    # Weight configuration (tuned via A/B testing)
    WEIGHTS = {
        'distance': 0.30,
        'rating': 0.25,
        'text_relevance': 0.20,
        'popularity': 0.15,
        'personalization': 0.05,
        'quality': 0.05,
    }
    
    def rank(self, businesses: list, user_location: tuple,
            query: str, user_profile: dict, sort_by: str = 'best_match') -> list:
        """
        Main ranking function.
        
        If sort_by is specified (not best_match), apply simple sort.
        Otherwise, use multi-signal scoring.
        """
        if sort_by == 'distance':
            return sorted(businesses, key=lambda b: b['distance_meters'])
        elif sort_by == 'rating':
            return sorted(businesses, key=lambda b: -b['rating_avg'])
        elif sort_by == 'review_count':
            return sorted(businesses, key=lambda b: -b['rating_count'])
        
        # Best match: multi-signal scoring
        scored = []
        for business in businesses:
            score = self._compute_score(business, user_location, query, user_profile)
            scored.append((business, score))
        
        scored.sort(key=lambda x: x[1], reverse=True)
        return [b for b, _ in scored]
    
    def _compute_score(self, business: dict, user_location: tuple,
                      query: str, user_profile: dict) -> float:
        """Compute composite relevance score"""
        
        distance_score = self._distance_score(business['distance_meters'])
        rating_score = self._rating_score(business['rating_avg'], business['rating_count'])
        text_score = self._text_relevance_score(business, query)
        popularity_score = self._popularity_score(business)
        personal_score = self._personalization_score(business, user_profile)
        quality_score = self._quality_score(business)
        
        # Weighted combination
        final = (
            self.WEIGHTS['distance'] * distance_score +
            self.WEIGHTS['rating'] * rating_score +
            self.WEIGHTS['text_relevance'] * text_score +
            self.WEIGHTS['popularity'] * popularity_score +
            self.WEIGHTS['personalization'] * personal_score +
            self.WEIGHTS['quality'] * quality_score
        )
        
        # Boost if currently open
        if business.get('is_open_now'):
            final *= 1.1
        
        return final
    
    def _distance_score(self, distance_meters: float) -> float:
        """
        Gaussian decay: score = exp(-distance² / (2 * σ²))
        
        σ determines how quickly score drops with distance:
        - σ = 1000m: score drops to 0.6 at 1km, 0.13 at 2km
        - σ = 2000m: score drops to 0.88 at 1km, 0.6 at 2km
        
        Users prefer closer places, but a great restaurant 2km away
        should still rank high.
        """
        import math
        sigma = 1500  # meters
        return math.exp(-(distance_meters ** 2) / (2 * sigma ** 2))
    
    def _rating_score(self, avg_rating: float, review_count: int) -> float:
        """
        Bayesian average to handle businesses with few reviews.
        
        score = (C * m + review_count * avg_rating) / (C + review_count)
        
        Where:
        - C = minimum reviews before rating is trusted (e.g., 10)
        - m = global mean rating (e.g., 3.7)
        
        This prevents a 5-star place with 1 review from outranking
        a 4.5-star place with 1000 reviews.
        """
        C = 10  # Confidence parameter
        m = 3.7  # Global mean
        
        bayesian_rating = (C * m + review_count * avg_rating) / (C + review_count)
        
        # Normalize to [0, 1]
        return (bayesian_rating - 1) / 4.0  # Map 1-5 to 0-1
    
    def _text_relevance_score(self, business: dict, query: str) -> float:
        """
        Text match scoring for query against business name, categories, attributes.
        Returns 0 if no query, or BM25-like score normalized to [0, 1].
        """
        if not query:
            return 0.5  # Neutral when no text query
        
        query_lower = query.lower()
        name_lower = business['name'].lower()
        categories = [c.lower() for c in business.get('categories', [])]
        
        score = 0.0
        
        # Exact name match: highest score
        if query_lower == name_lower:
            return 1.0
        
        # Name contains query
        if query_lower in name_lower:
            score = 0.8
        
        # Category match
        for cat in categories:
            if query_lower in cat or cat in query_lower:
                score = max(score, 0.7)
        
        # Partial token overlap
        query_tokens = set(query_lower.split())
        name_tokens = set(name_lower.split())
        overlap = query_tokens & name_tokens
        if overlap:
            score = max(score, 0.5 * len(overlap) / len(query_tokens))
        
        return score
    
    def _popularity_score(self, business: dict) -> float:
        """
        Combine multiple popularity signals:
        - Review count (log-scaled)
        - Check-in count (log-scaled)
        - Photo count
        - Recent activity (reviews in last 30 days)
        """
        import math
        
        review_signal = math.log1p(business.get('rating_count', 0)) / 10.0
        checkin_signal = math.log1p(business.get('checkin_count', 0)) / 8.0
        photo_signal = min(business.get('photo_count', 0) / 50.0, 1.0)
        recency_signal = min(business.get('reviews_last_30d', 0) / 20.0, 1.0)
        
        return min(
            0.4 * review_signal + 0.2 * checkin_signal + 
            0.2 * photo_signal + 0.2 * recency_signal,
            1.0
        )
    
    def _personalization_score(self, business: dict, user_profile: dict) -> float:
        """
        Score based on user's historical preferences.
        - Category affinity: user frequently searches/visits this category
        - Price match: business price level matches user's typical range
        - Previously visited: slight boost for repeat visits (familiarity)
        """
        if not user_profile:
            return 0.5
        
        score = 0.5  # Neutral baseline
        
        # Category affinity
        user_categories = user_profile.get('category_affinity', {})
        for cat in business.get('categories', []):
            if cat in user_categories:
                score += 0.2 * user_categories[cat]
        
        # Price match
        user_price_pref = user_profile.get('avg_price_level', 2)
        price_diff = abs(business.get('price_level', 2) - user_price_pref)
        score -= 0.1 * price_diff
        
        return max(min(score, 1.0), 0.0)
    
    def _quality_score(self, business: dict) -> float:
        """
        Business profile completeness and quality signals:
        - Is claimed by owner (verified)
        - Has hours listed
        - Has photos
        - Has complete attributes
        - Responds to reviews
        """
        score = 0.0
        
        if business.get('is_claimed'):
            score += 0.3
        if business.get('hours'):
            score += 0.2
        if business.get('photo_count', 0) > 5:
            score += 0.2
        if business.get('attributes'):
            score += 0.15
        if business.get('response_rate', 0) > 0.5:
            score += 0.15
        
        return score
```

---

## 10. Redis Geospatial Caching

```python
class GeoCache:
    """
    Redis-based geospatial caching layer.
    
    Uses Redis GEO commands (built on sorted sets with geohash scores):
    - GEOADD: Add business locations
    - GEOSEARCH: Find businesses within radius
    - GEODIST: Distance between two points
    
    Caching strategy:
    - Cache popular search regions (city centers, tourist areas)
    - Pre-compute "open now" status every minute
    - Cache query results by (geohash_prefix + query + filters)
    """
    
    def __init__(self, redis_client):
        self.redis = redis_client
        self.CACHE_TTL = 300  # 5 minutes for search results
        self.GEO_KEY = "businesses:geo"
    
    def populate_geo_index(self, businesses: list):
        """
        Load all business locations into Redis GEO structure.
        Memory: ~200M businesses × 50 bytes ≈ 10GB (fits in Redis cluster)
        """
        pipe = self.redis.pipeline()
        batch_size = 10000
        
        for i in range(0, len(businesses), batch_size):
            batch = businesses[i:i + batch_size]
            for b in batch:
                pipe.geoadd(
                    self.GEO_KEY,
                    (b['longitude'], b['latitude'], b['business_id'])
                )
            pipe.execute()
    
    def search_nearby(self, lat: float, lng: float, 
                     radius_km: float, count: int = 100) -> list:
        """
        Redis GEOSEARCH - O(N+log(N)) where N = elements in radius.
        Returns business_ids sorted by distance.
        """
        results = self.redis.geosearch(
            self.GEO_KEY,
            longitude=lng,
            latitude=lat,
            radius=radius_km,
            unit='km',
            count=count,
            sort='ASC',  # Nearest first
            withcoord=True,
            withdist=True
        )
        
        return [
            {
                'business_id': member,
                'distance_km': dist,
                'lat': coord[1],
                'lng': coord[0]
            }
            for member, dist, coord in results
        ]
    
    def cache_search_results(self, cache_key: str, results: list):
        """Cache search results for repeated queries in same area"""
        import json
        self.redis.setex(
            f"search:{cache_key}",
            self.CACHE_TTL,
            json.dumps(results)
        )
    
    def get_cached_results(self, lat: float, lng: float, 
                          query: str, filters: dict) -> list | None:
        """
        Check if we have cached results for this search.
        Cache key: geohash(lat,lng, precision=6) + query_hash + filter_hash
        
        Using geohash precision 6 (~1.2km cell) means users within 
        the same ~1km area get cache hits.
        """
        import hashlib, json
        
        geo = GeospatialIndexing()
        geohash = geo.encode_geohash(lat, lng, precision=6)
        
        filter_str = json.dumps(filters, sort_keys=True)
        cache_key = f"{geohash}:{query}:{hashlib.md5(filter_str.encode()).hexdigest()[:8]}"
        
        cached = self.redis.get(f"search:{cache_key}")
        if cached:
            return json.loads(cached)
        return None
    
    def update_open_status(self):
        """
        Cron job every minute: update is_open_now for all businesses.
        Uses Redis HSET for fast lookups during ranking.
        """
        import datetime
        now = datetime.datetime.now()
        current_day = now.strftime('%A').lower()
        current_time = now.strftime('%H:%M')
        
        # Batch update open status
        # In production: Kafka stream processes hour changes
        pipe = self.redis.pipeline()
        
        # For each business, check if current time is within hours
        for business_id, hours in self.get_all_business_hours():
            day_hours = hours.get(current_day)
            if day_hours:
                is_open = day_hours['open'] <= current_time <= day_hours['close']
            else:
                is_open = False
            
            pipe.hset(f"business:{business_id}", "is_open_now", int(is_open))
        
        pipe.execute()
```

---

## 11. Elasticsearch Geo Query Implementation

```python
class ElasticsearchGeoSearch:
    """
    Elasticsearch implementation for combined text + geo search.
    Uses geo_distance filter + text relevance scoring.
    """
    
    def search(self, query: str, lat: float, lng: float, 
              radius_km: float, filters: dict, sort: str,
              page: int = 1, size: int = 20) -> dict:
        """Build and execute Elasticsearch geo query"""
        
        es_query = {
            "bool": {
                "must": [],
                "filter": [
                    {
                        "geo_distance": {
                            "distance": f"{radius_km}km",
                            "location": {"lat": lat, "lon": lng}
                        }
                    },
                    {"term": {"is_active": True}}
                ]
            }
        }
        
        # Add text query if provided
        if query:
            es_query["bool"]["must"].append({
                "multi_match": {
                    "query": query,
                    "fields": ["name^3", "categories^2", "attributes.*"],
                    "type": "best_fields",
                    "fuzziness": "AUTO"
                }
            })
        
        # Add filters
        if 'price_level' in filters:
            es_query["bool"]["filter"].append(
                {"terms": {"price_level": filters['price_level']}}
            )
        if 'rating_min' in filters:
            es_query["bool"]["filter"].append(
                {"range": {"rating_avg": {"gte": filters['rating_min']}}}
            )
        if filters.get('open_now'):
            es_query["bool"]["filter"].append(
                {"term": {"is_open_now": True}}
            )
        if 'categories' in filters:
            es_query["bool"]["filter"].append(
                {"terms": {"categories": filters['categories']}}
            )
        
        # Build sort
        sort_clause = self._build_sort(sort, lat, lng)
        
        # Function score for best_match (combine text + distance + rating)
        if sort == 'best_match':
            full_query = {
                "function_score": {
                    "query": es_query,
                    "functions": [
                        {
                            "gauss": {
                                "location": {
                                    "origin": {"lat": lat, "lon": lng},
                                    "scale": "2km",
                                    "offset": "500m",
                                    "decay": 0.5
                                }
                            },
                            "weight": 3
                        },
                        {
                            "field_value_factor": {
                                "field": "rating_avg",
                                "modifier": "log1p",
                                "factor": 2
                            },
                            "weight": 2
                        },
                        {
                            "field_value_factor": {
                                "field": "rating_count",
                                "modifier": "log1p",
                                "factor": 0.5
                            },
                            "weight": 1
                        }
                    ],
                    "score_mode": "sum",
                    "boost_mode": "multiply"
                }
            }
        else:
            full_query = es_query
        
        # Execute
        body = {
            "query": full_query,
            "sort": sort_clause,
            "from": (page - 1) * size,
            "size": size,
            "aggs": self._build_facets(),
            "script_fields": {
                "distance": {
                    "script": {
                        "source": "doc['location'].arcDistance(params.lat, params.lon)",
                        "params": {"lat": lat, "lon": lng}
                    }
                }
            }
        }
        
        return self.es.search(index="businesses", body=body)
    
    def _build_facets(self) -> dict:
        """Build aggregations for faceted navigation"""
        return {
            "categories": {
                "terms": {"field": "categories", "size": 20}
            },
            "price_levels": {
                "terms": {"field": "price_level", "size": 4}
            },
            "features": {
                "nested": {"path": "attributes"},
                "aggs": {
                    "feature_names": {
                        "terms": {"field": "attributes.key", "size": 10}
                    }
                }
            },
            "rating_ranges": {
                "range": {
                    "field": "rating_avg",
                    "ranges": [
                        {"from": 4.5, "key": "4.5+"},
                        {"from": 4.0, "key": "4.0+"},
                        {"from": 3.5, "key": "3.5+"}
                    ]
                }
            }
        }
```

---

## 12. Observability

### Key Metrics
```yaml
search_quality:
  - click_through_rate: users clicking on a result (target > 60%)
  - zero_results_rate: searches with no results (target < 1%)
  - avg_position_clicked: position of first click (target < 5)
  - map_interaction_rate: users engaging with map
  - checkin_after_search: searches leading to check-in

performance:
  - search_latency_p50: target < 100ms
  - search_latency_p99: target < 300ms
  - geo_query_time: spatial index lookup time
  - facet_computation_time: aggregation time
  - photo_load_time: via CDN

infrastructure:
  - geo_index_size: PostGIS/ES spatial index memory
  - cache_hit_rate: Redis geo cache (target > 50%)
  - es_heap_usage: Elasticsearch JVM heap
  - shard_distribution: even query spread
  - indexing_rate: new/updated businesses per minute

business:
  - businesses_per_search: average results returned
  - claimed_business_rate: fraction of businesses claimed by owners
  - review_submission_rate: reviews per day
  - photo_upload_rate: new photos per day
```

### Alerting
```yaml
alerts:
  - name: search_latency_high
    condition: p99 > 500ms for 5 minutes
    severity: critical

  - name: geo_index_stale
    condition: businesses not updated in > 1 hour
    severity: warning

  - name: zero_results_spike
    condition: zero_results_rate > 5% for 10 minutes
    severity: high

  - name: open_status_stale
    condition: is_open_now not refreshed in > 5 minutes
    severity: warning
```

---

## 13. Considerations & Trade-offs

### Geohash vs H3 vs PostGIS
```
Trade-off: Simplicity vs precision vs features

Geohash:
+ Simple, string-based, works with any key-value store
+ Good for Redis GEOSEARCH and prefix-based range queries
- Edge effects at cell boundaries
- Rectangular cells (unequal area at different latitudes)

H3 (chosen for production):
+ Hexagonal (uniform neighbor distance)
+ Hierarchical (multi-resolution queries)
+ Better for k-nearest-neighbor queries
- Requires H3 library, not natively supported everywhere

PostGIS:
+ Most feature-rich (ST_DWithin, complex polygons)
+ Handles irregular boundaries (cities, neighborhoods)
- Higher latency than in-memory solutions
- Best for source of truth, not real-time serving

Decision: H3 for serving layer (Redis/memory), PostGIS for source of truth.
```

### Real-time "Open Now" vs Batch
```
Trade-off: Accurate open/closed status vs computation cost

Option A: Compute at query time
- Pro: Always accurate
- Con: ~5ms per business × 100 results = 500ms overhead

Option B: Precompute every minute (chosen)
- Pro: Zero query-time cost
- Con: Up to 1-minute stale (acceptable for hours)

Decision: Batch update is_open_now flag every minute.
Special handling for holidays/closures via event-driven updates.
```

### Distance Sorting vs Relevance
```
Trade-off: Purely closest vs best overall experience

A user searching "pizza" at 8pm:
- Closest might be a mediocre pizza place 200m away
- Best might be a 4.8-star place 1.5km away

Decision: Default to "best match" with Gaussian distance decay.
σ=1.5km means a 4.8-star place at 1.5km scores comparably
to a 3.5-star place at 200m.
Allow user to override with explicit "distance" sort.
```

### Cold Start for New Businesses
```
Challenge: New businesses have no reviews/ratings/check-ins.
Solutions:
- Initial visibility boost for first 30 days
- Show "New on Yelp" badge
- Prompt nearby users to review
- Use owner-provided data (photos, menu) to infer quality
- Display completeness as trust signal
```

---

## 14. Summary

| Dimension | Approach |
|-----------|----------|
| Geo Index | H3 hexagonal grid (serving) + PostGIS (source of truth) |
| Search | Elasticsearch geo_distance + text scoring + function_score |
| Ranking | Multi-signal: distance decay + Bayesian rating + popularity + personalization |
| Caching | Redis GEO commands + geohash-based result caching |
| Data Structure | QuadTree (in-memory) for fast range queries |
| Freshness | Open status: 1-min batch update; Business data: event-driven |
| Scale | 200M businesses, 9K QPS, Elasticsearch sharded + replicated |
| Precision | Haversine distance for final filtering, H3 k-ring for candidate generation |
