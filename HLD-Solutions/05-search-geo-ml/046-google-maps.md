# Design Google Maps / Navigation System

## 1. Requirements

### 1.1 Functional Requirements
- **Map rendering**: Vector/raster tile serving at multiple zoom levels
- **Route planning**: Multi-modal (driving, walking, cycling, transit)
- **Turn-by-turn navigation**: Real-time guidance with rerouting
- **Traffic estimation**: Live and predictive traffic conditions
- **ETA calculation**: Accurate arrival time with traffic
- **POI search**: Points of interest search with autocomplete
- **Offline maps**: Download regions for offline use
- **Street view**: 360° imagery browsing

### 1.2 Non-Functional Requirements
- **Availability**: 99.99% uptime
- **Route calculation**: < 500ms for regional, < 2s for cross-country
- **Map tile load**: < 100ms from CDN (p95)
- **Scale**: 1B+ monthly active users
- **Freshness**: Traffic data updated every 30 seconds
- **Storage**: Petabytes of map/imagery data

## 2. Capacity Estimation

### 2.1 Traffic
- 1B MAU, 200M DAU, avg 5 map loads/day = 1B tile requests/day
- Route requests: 100M/day → ~1200/sec avg, ~5000/sec peak
- Navigation sessions: 50M/day active
- Traffic probe data: 200M devices reporting → 5M updates/sec

### 2.2 Storage
- Global road graph: ~500M road segments, ~200M intersections → 50 GB compressed
- Map tiles (all zoom levels): ~100 TB (vector), ~1 PB (raster)
- Traffic segment data: 500M segments × 100 bytes = 50 GB (real-time state)
- Historical traffic: 500M segments × 365 days × 288 intervals × 4 bytes = 200 TB
- Street view imagery: ~200 PB globally
- POI database: 200M POIs × 2KB = 400 GB

### 2.3 Bandwidth
- Tile serving: 1B requests/day × 50KB avg = 50 PB/day from CDN
- Route responses: 100M/day × 10KB = 1 TB/day
- Traffic overlay tiles: 200M/day × 20KB = 4 TB/day

## 3. Data Modeling

### 3.1 Road Graph (Custom Binary Format + PostgreSQL/PostGIS)

```sql
-- Road segments (edges in the graph)
CREATE TABLE road_segments (
    segment_id BIGINT PRIMARY KEY,
    osm_way_id BIGINT,
    start_node_id BIGINT REFERENCES road_nodes(node_id),
    end_node_id BIGINT REFERENCES road_nodes(node_id),
    road_class VARCHAR(20) NOT NULL, -- motorway, trunk, primary, secondary, residential
    road_name VARCHAR(200),
    length_meters INT NOT NULL,
    speed_limit_kmh SMALLINT,
    is_oneway BOOLEAN DEFAULT FALSE,
    is_toll BOOLEAN DEFAULT FALSE,
    lane_count SMALLINT DEFAULT 2,
    surface_type VARCHAR(20),
    geometry GEOMETRY(LINESTRING, 4326),
    country_code CHAR(2),
    region_code VARCHAR(10),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_segments_start_node ON road_segments(start_node_id);
CREATE INDEX idx_segments_end_node ON road_segments(end_node_id);
CREATE INDEX idx_segments_geometry ON road_segments USING GIST(geometry);
CREATE INDEX idx_segments_road_class ON road_segments(road_class);
CREATE INDEX idx_segments_region ON road_segments(country_code, region_code);

-- Road nodes (vertices in the graph)
CREATE TABLE road_nodes (
    node_id BIGINT PRIMARY KEY,
    lat DECIMAL(10,7) NOT NULL,
    lng DECIMAL(10,7) NOT NULL,
    is_intersection BOOLEAN DEFAULT FALSE,
    traffic_signal BOOLEAN DEFAULT FALSE,
    elevation_meters SMALLINT,
    partition_id INT -- For graph partitioning
);

CREATE INDEX idx_nodes_location ON road_nodes USING GIST(
    ST_SetSRID(ST_MakePoint(lng, lat), 4326)
);
CREATE INDEX idx_nodes_partition ON road_nodes(partition_id);

-- Turn restrictions
CREATE TABLE turn_restrictions (
    restriction_id BIGINT PRIMARY KEY,
    from_segment_id BIGINT REFERENCES road_segments(segment_id),
    via_node_id BIGINT REFERENCES road_nodes(node_id),
    to_segment_id BIGINT REFERENCES road_segments(segment_id),
    restriction_type VARCHAR(20), -- no_left_turn, no_u_turn, only_straight
    time_restriction JSONB -- NULL = always, or {days, hours}
);

CREATE INDEX idx_restrictions_via ON turn_restrictions(via_node_id);

-- POI (Points of Interest)
CREATE TABLE pois (
    poi_id BIGINT PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    category VARCHAR(50) NOT NULL, -- restaurant, gas_station, hotel, etc.
    subcategory VARCHAR(50),
    lat DECIMAL(10,7) NOT NULL,
    lng DECIMAL(10,7) NOT NULL,
    address TEXT,
    phone VARCHAR(30),
    website VARCHAR(500),
    rating DECIMAL(2,1),
    review_count INT DEFAULT 0,
    price_level SMALLINT, -- 1-4
    opening_hours JSONB,
    photos JSONB, -- array of photo URLs
    geometry GEOMETRY(POINT, 4326),
    search_vector TSVECTOR,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_pois_geometry ON pois USING GIST(geometry);
CREATE INDEX idx_pois_category ON pois(category, subcategory);
CREATE INDEX idx_pois_search ON pois USING GIN(search_vector);
CREATE INDEX idx_pois_name_trgm ON pois USING GIN(name gin_trgm_ops);

-- Traffic segments (real-time)
CREATE TABLE traffic_segments (
    segment_id BIGINT PRIMARY KEY REFERENCES road_segments(segment_id),
    current_speed_kmh SMALLINT,
    free_flow_speed_kmh SMALLINT,
    congestion_level VARCHAR(10), -- free, light, moderate, heavy, blocked
    travel_time_seconds INT,
    confidence DECIMAL(3,2),
    incident_id BIGINT,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

### 3.2 Map Tile Storage (S3 + CDN)

```
S3 Bucket Structure:
tiles/
  vector/
    {z}/{x}/{y}.mvt          # Mapbox Vector Tiles (protobuf)
  raster/
    {z}/{x}/{y}.png          # Pre-rendered raster tiles
  traffic/
    {z}/{x}/{y}/{timestamp}.mvt  # Traffic overlay tiles
  terrain/
    {z}/{x}/{y}.terrain      # Elevation data
  satellite/
    {z}/{x}/{y}.jpg          # Satellite imagery

Zoom levels: 0-22
Level 0: 1 tile (whole world)
Level 14: ~268M tiles (street level)
Level 22: ~17.6 trillion tiles (building level, on-demand)
```

### 3.3 Redis - Real-time Traffic State

```redis
# Traffic speed per segment (rolling average)
HSET traffic:speed segment_123456 45
HSET traffic:speed segment_123457 12

# Traffic incidents
HSET incident:98765 type accident lat 40.7484 lng -73.9857 severity major lanes_blocked 2 estimated_clear 1700003600

# ETA cache (route hash → ETA)
SET eta:cache:{route_hash} "{eta_seconds: 1200, computed_at: 1700000000}" EX 60

# Popular routes cache
SET route:cache:{origin_dest_hash} "{polyline, distance, duration}" EX 300
```

## 4. High-Level Design

### 4.1 Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                                CLIENTS                                           │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                      │
│  │  Mobile App  │    │   Web App    │    │ 3rd Party API│                      │
│  └──────┬───────┘    └──────┬───────┘    └──────┬───────┘                      │
└─────────┼───────────────────┼───────────────────┼───────────────────────────────┘
          │                   │                   │
          ▼                   ▼                   ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                            CDN (CloudFront/Akamai)                               │
│  ┌───────────────────────────────────────────────────────────────────┐          │
│  │  Map Tiles (vector/raster) │ Traffic Tiles │ Static Assets        │          │
│  └───────────────────────────────────────────────────────────────────┘          │
└─────────────────────────────────────────┬───────────────────────────────────────┘
                                          │ (cache miss)
                                          ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                          API GATEWAY (Regional)                                   │
│  ┌─────────────┐  ┌────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │   Auth      │  │ Rate Limit │  │  Geo-Routing │  │  Compression │          │
│  └─────────────┘  └────────────┘  └──────────────┘  └──────────────┘          │
└────────┬─────────────────┬──────────────────┬───────────────────┬───────────────┘
         │                 │                  │                   │
         ▼                 ▼                  ▼                   ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│   Routing    │  │    Tile      │  │   Traffic    │  │     POI      │
│   Service    │  │   Service    │  │   Service    │  │   Service    │
│              │  │              │  │              │  │              │
│ -Route calc  │  │ -Vector gen  │  │ -Real-time   │  │ -Search      │
│ -Navigation  │  │ -Raster gen  │  │ -Prediction  │  │ -Autocomplete│
│ -ETA         │  │ -Caching     │  │ -Incidents   │  │ -Details     │
└──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘
       │                 │                  │                   │
       ▼                 ▼                  ▼                   ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│                              DATA LAYER                                            │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌──────────┐  │
│  │ Road Graph │  │    S3      │  │   Redis    │  │ Elasticsearch│ │PostgreSQL│  │
│  │ (in-memory)│  │ (tiles)    │  │ (traffic)  │  │  (POI/search)│ │(metadata)│  │
│  └────────────┘  └────────────┘  └────────────┘  └────────────┘  └──────────┘  │
└──────────────────────────────────────────────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│                        DATA PIPELINE (Kafka + Flink)                               │
│  ┌──────────────┐  ┌───────────────┐  ┌──────────────────┐                      │
│  │Traffic Probes│  │ Map Updates   │  │ ML Traffic Model │                      │
│  │(from devices)│  │ (OSM imports) │  │ (prediction)     │                      │
│  └──────────────┘  └───────────────┘  └──────────────────┘                      │
└──────────────────────────────────────────────────────────────────────────────────┘
```

### 4.2 Navigation Session Flow

```
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│  Client  │     │ Routing  │     │ Traffic  │     │   Nav    │
│   App    │     │ Service  │     │ Service  │     │ Service  │
└────┬─────┘     └────┬─────┘     └────┬─────┘     └────┬─────┘
     │ Route Request   │               │               │
     │────────────────►│               │               │
     │                 │ Get Traffic   │               │
     │                 │──────────────►│               │
     │                 │◄──────────────│               │
     │                 │ Calculate     │               │
     │  Route + ETA   │               │               │
     │◄────────────────│               │               │
     │                 │               │               │
     │ Start Navigation│               │               │
     │─────────────────────────────────────────────────►│
     │                 │               │               │
     │◄═══════════════ Location Updates (every 1s) ════►│
     │                 │               │               │
     │                 │     Traffic Change             │
     │                 │◄──────────────│               │
     │  Reroute        │               │               │
     │◄────────────────│               │               │
```

## 5. Low-Level Design - APIs

### 5.1 Route Planning API

```
POST /api/v1/directions
Authorization: Bearer {token}

Request:
{
  "origin": {"lat": 40.7484, "lng": -73.9857},
  "destination": {"lat": 40.7580, "lng": -73.9855},
  "waypoints": [
    {"lat": 40.7527, "lng": -73.9772}
  ],
  "mode": "driving",  // driving, walking, cycling, transit
  "alternatives": true,
  "departure_time": "2024-01-15T08:00:00Z",
  "avoid": ["tolls", "ferries"],
  "units": "metric"
}

Response 200:
{
  "routes": [
    {
      "route_id": "route_abc123",
      "summary": "via FDR Drive",
      "distance_meters": 4200,
      "duration_seconds": 720,
      "duration_in_traffic_seconds": 960,
      "polyline": "encoded_polyline_string...",
      "bounds": {"ne": {"lat": 40.76, "lng": -73.97}, "sw": {"lat": 40.74, "lng": -73.99}},
      "legs": [
        {
          "distance_meters": 2100,
          "duration_seconds": 360,
          "start_address": "350 5th Ave",
          "end_address": "Waypoint 1",
          "steps": [
            {
              "instruction": "Head north on 5th Ave",
              "distance_meters": 400,
              "duration_seconds": 60,
              "maneuver": "straight",
              "polyline": "encoded...",
              "start_location": {"lat": 40.7484, "lng": -73.9857},
              "end_location": {"lat": 40.7520, "lng": -73.9857}
            },
            {
              "instruction": "Turn right onto E 42nd St",
              "distance_meters": 300,
              "duration_seconds": 45,
              "maneuver": "turn-right",
              "polyline": "encoded..."
            }
          ]
        }
      ],
      "traffic_conditions": "moderate",
      "toll_cost_cents": 0
    }
  ],
  "geocoded_waypoints": [
    {"status": "OK", "place_id": "place_123"}
  ]
}
```

### 5.2 Map Tile API

```
GET /api/v1/tiles/vector/{z}/{x}/{y}.mvt
GET /api/v1/tiles/raster/{z}/{x}/{y}.png?style=default&retina=true
GET /api/v1/tiles/traffic/{z}/{x}/{y}.mvt

Response Headers:
  Content-Type: application/x-protobuf (vector) / image/png (raster)
  Cache-Control: public, max-age=86400 (base tiles) / max-age=30 (traffic)
  ETag: "tile_hash_abc123"
  Content-Encoding: gzip
```

### 5.3 Traffic API

```
GET /api/v1/traffic?bounds=40.70,-74.02,40.80,-73.93&zoom=14

Response 200:
{
  "segments": [
    {
      "segment_id": 123456,
      "polyline": "encoded...",
      "speed_kmh": 25,
      "free_flow_kmh": 55,
      "congestion": "heavy",  // free, light, moderate, heavy, blocked
      "travel_time_seconds": 120,
      "incidents": []
    }
  ],
  "incidents": [
    {
      "id": "inc_789",
      "type": "accident",
      "location": {"lat": 40.7484, "lng": -73.9857},
      "severity": "major",
      "description": "Multi-vehicle accident, 2 lanes blocked",
      "estimated_clear_time": "2024-01-15T09:30:00Z"
    }
  ],
  "updated_at": "2024-01-15T08:15:30Z"
}
```

### 5.4 POI Search API

```
GET /api/v1/places/search?q=coffee+shop&lat=40.7484&lng=-73.9857&radius=1000&limit=20

Response 200:
{
  "results": [
    {
      "place_id": "place_456",
      "name": "Blue Bottle Coffee",
      "category": "cafe",
      "location": {"lat": 40.7490, "lng": -73.9850},
      "distance_meters": 85,
      "rating": 4.5,
      "review_count": 234,
      "price_level": 3,
      "is_open": true,
      "opening_hours": {"today": "7:00 AM - 7:00 PM"},
      "address": "450 W 15th St, New York, NY",
      "photos": ["https://cdn.maps.example.com/photos/abc.jpg"]
    }
  ],
  "next_page_token": "token_xyz"
}
```

## 6. Deep Dive: Road Graph and Routing Algorithms

### 6.1 Graph Representation

```python
class RoadGraph:
    """
    In-memory road graph optimized for routing.
    Uses adjacency array representation for cache-friendly traversal.
    
    Memory layout:
    - nodes[]: array of (lat, lng, first_edge_idx)
    - edges[]: array of (target_node, weight, road_class, flags)
    - Sorted by source node for locality
    """
    
    def __init__(self):
        self.nodes = []       # Compact node array
        self.edges = []       # Compact edge array  
        self.node_index = {}  # node_id → array index
        self.shortcuts = []   # Contraction Hierarchy shortcuts
        self.ch_levels = []   # CH node ordering
    
    def load_from_binary(self, filepath: str):
        """Load pre-processed graph from binary file (fast mmap load)."""
        # Memory-mapped for fast startup
        import mmap
        with open(filepath, 'rb') as f:
            mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
            header = struct.unpack('III', mm[:12])  # num_nodes, num_edges, num_shortcuts
            # ... deserialize arrays
    
    def get_neighbors(self, node_idx: int) -> list:
        """Get all outgoing edges from a node."""
        first_edge = self.nodes[node_idx].first_edge
        next_first = self.nodes[node_idx + 1].first_edge if node_idx + 1 < len(self.nodes) else len(self.edges)
        return self.edges[first_edge:next_first]
```

### 6.2 Contraction Hierarchies (Primary Algorithm)

```python
import heapq

class ContractionHierarchies:
    """
    Pre-processed graph enabling bidirectional Dijkstra with shortcuts.
    Preprocessing: O(n log n) time, query: O(n^0.5) typical case.
    
    Key idea: Contract nodes in order of importance.
    When contracting node v, add shortcuts between neighbors
    if the shortest path goes through v.
    """
    
    def __init__(self, graph: RoadGraph):
        self.graph = graph
        self.forward_graph = {}  # Upward edges (to higher-importance nodes)
        self.backward_graph = {} # Downward edges
        self.node_order = []     # Contraction order (importance ranking)
    
    def preprocess(self):
        """
        Preprocess graph by contracting nodes in order of importance.
        Importance = edge_difference + contracted_neighbors + level
        
        This takes hours but produces a graph where queries are ~1000x faster.
        """
        importance_queue = []  # min-heap of (importance, node_id)
        contracted = set()
        
        # Initialize importance for all nodes
        for node_id in range(len(self.graph.nodes)):
            imp = self.calculate_importance(node_id, contracted)
            heapq.heappush(importance_queue, (imp, node_id))
        
        order = 0
        while importance_queue:
            _, node_id = heapq.heappop(importance_queue)
            
            # Lazy update: recalculate importance (may have changed)
            current_imp = self.calculate_importance(node_id, contracted)
            if importance_queue and current_imp > importance_queue[0][0]:
                heapq.heappush(importance_queue, (current_imp, node_id))
                continue
            
            # Contract this node
            shortcuts = self.contract_node(node_id, contracted)
            contracted.add(node_id)
            self.node_order.append(node_id)
            self.graph.ch_levels[node_id] = order
            order += 1
            
            # Add shortcuts to graph
            for shortcut in shortcuts:
                self.graph.shortcuts.append(shortcut)
    
    def contract_node(self, node_id: int, contracted: set) -> list:
        """
        Contract node v: for each pair (u,w) of non-contracted neighbors,
        if shortest u→w path goes through v, add shortcut u→w.
        """
        shortcuts = []
        in_edges = self.get_incoming(node_id, contracted)
        out_edges = self.get_outgoing(node_id, contracted)
        
        for u, weight_uv in in_edges:
            for w, weight_vw in out_edges:
                if u == w:
                    continue
                shortcut_weight = weight_uv + weight_vw
                
                # Check if there's a witness path u→w not through v
                witness = self.find_witness(u, w, node_id, shortcut_weight, contracted)
                
                if not witness:
                    shortcuts.append({
                        "from": u, "to": w,
                        "weight": shortcut_weight,
                        "via": node_id
                    })
        
        return shortcuts
    
    def query(self, source: int, target: int) -> dict:
        """
        Bidirectional Dijkstra on CH graph.
        Forward search goes upward, backward search goes upward from target.
        Meet in the middle at highest-importance node on shortest path.
        """
        INF = float('inf')
        
        # Forward distances (from source, going up)
        dist_f = {source: 0}
        pq_f = [(0, source)]
        
        # Backward distances (from target, going up)
        dist_b = {target: 0}
        pq_b = [(0, target)]
        
        best_distance = INF
        meeting_node = -1
        
        visited_f = set()
        visited_b = set()
        
        while pq_f or pq_b:
            # Forward step
            if pq_f:
                d, u = heapq.heappop(pq_f)
                if d > best_distance:
                    pq_f = []
                else:
                    visited_f.add(u)
                    # Check if backward search reached this node
                    if u in dist_b:
                        total = d + dist_b[u]
                        if total < best_distance:
                            best_distance = total
                            meeting_node = u
                    
                    # Only explore upward edges
                    for v, weight in self.get_upward_edges(u):
                        new_dist = d + weight
                        if new_dist < dist_f.get(v, INF):
                            dist_f[v] = new_dist
                            heapq.heappush(pq_f, (new_dist, v))
            
            # Backward step (symmetric)
            if pq_b:
                d, u = heapq.heappop(pq_b)
                if d > best_distance:
                    pq_b = []
                else:
                    visited_b.add(u)
                    if u in dist_f:
                        total = d + dist_f[u]
                        if total < best_distance:
                            best_distance = total
                            meeting_node = u
                    
                    for v, weight in self.get_upward_edges_reverse(u):
                        new_dist = d + weight
                        if new_dist < dist_b.get(v, INF):
                            dist_b[v] = new_dist
                            heapq.heappush(pq_b, (new_dist, v))
        
        # Reconstruct path by unpacking shortcuts
        path = self.unpack_path(source, meeting_node, target, dist_f, dist_b)
        
        return {
            "distance": best_distance,
            "path": path,
            "nodes_explored": len(visited_f) + len(visited_b)
        }
    
    def calculate_importance(self, node_id: int, contracted: set) -> int:
        """
        Importance heuristic for node ordering.
        Lower importance = contract first.
        """
        in_edges = self.get_incoming(node_id, contracted)
        out_edges = self.get_outgoing(node_id, contracted)
        
        # Edge difference: shortcuts_added - edges_removed
        shortcuts_needed = self.count_shortcuts_needed(node_id, contracted)
        edges_removed = len(in_edges) + len(out_edges)
        edge_diff = shortcuts_needed - edges_removed
        
        # Contracted neighbors (avoid creating long shortcut chains)
        contracted_neighbors = sum(1 for u, _ in in_edges + out_edges if u in contracted)
        
        return edge_diff * 10 + contracted_neighbors * 5
```

### 6.3 A* with ALT (A* Landmarks Triangle inequality)

```python
class ALTRouter:
    """
    A* search with landmark-based heuristic for cases where CH isn't available
    (e.g., dynamic edge weights, temporary road closures).
    
    Landmarks are strategically chosen nodes with precomputed distances to all nodes.
    Triangle inequality provides tight lower bounds for A* heuristic.
    """
    
    def __init__(self, graph: RoadGraph, num_landmarks: int = 16):
        self.graph = graph
        self.landmarks = []
        self.dist_to_landmark = {}    # node → distances to all landmarks
        self.dist_from_landmark = {}  # node → distances from all landmarks
    
    def select_landmarks(self, num_landmarks: int):
        """Select landmarks using farthest-first traversal."""
        # Start with a random node
        first = random.randint(0, len(self.graph.nodes) - 1)
        self.landmarks = [first]
        
        for _ in range(num_landmarks - 1):
            # Find node farthest from all current landmarks
            max_min_dist = 0
            farthest_node = -1
            
            for node_id in range(len(self.graph.nodes)):
                min_dist = min(
                    self.get_dist(node_id, lm) for lm in self.landmarks
                )
                if min_dist > max_min_dist:
                    max_min_dist = min_dist
                    farthest_node = node_id
            
            self.landmarks.append(farthest_node)
    
    def heuristic(self, node: int, target: int) -> float:
        """
        Lower bound on distance using triangle inequality:
        d(u, t) >= |d(u, L) - d(t, L)| for any landmark L
        d(u, t) >= |d(L, t) - d(L, u)| for any landmark L
        
        Take max over all landmarks for tightest bound.
        """
        max_bound = 0
        for lm_idx, landmark in enumerate(self.landmarks):
            # Forward: d(node, landmark) - d(target, landmark)
            bound1 = abs(
                self.dist_to_landmark[node][lm_idx] - 
                self.dist_to_landmark[target][lm_idx]
            )
            # Backward: d(landmark, target) - d(landmark, node)
            bound2 = abs(
                self.dist_from_landmark[target][lm_idx] - 
                self.dist_from_landmark[node][lm_idx]
            )
            max_bound = max(max_bound, bound1, bound2)
        
        return max_bound
    
    def search(self, source: int, target: int, traffic_weights: dict = None) -> dict:
        """A* search using ALT heuristic. Supports dynamic edge weights."""
        dist = {source: 0}
        pq = [(self.heuristic(source, target), 0, source)]  # (f, g, node)
        parent = {source: None}
        explored = 0
        
        while pq:
            f, g, u = heapq.heappop(pq)
            
            if u == target:
                path = self.reconstruct_path(parent, target)
                return {"distance": g, "path": path, "explored": explored}
            
            if g > dist.get(u, float('inf')):
                continue
            
            explored += 1
            
            for v, base_weight in self.graph.get_neighbors(u):
                # Apply dynamic traffic weight if available
                weight = traffic_weights.get((u, v), base_weight) if traffic_weights else base_weight
                
                new_dist = g + weight
                if new_dist < dist.get(v, float('inf')):
                    dist[v] = new_dist
                    f_score = new_dist + self.heuristic(v, target)
                    heapq.heappush(pq, (f_score, new_dist, v))
                    parent[v] = u
        
        return {"distance": float('inf'), "path": [], "explored": explored}
```

### 6.4 Multi-Modal Transit Routing

```python
class TransitRouter:
    """
    Multi-modal routing combining walking + public transit.
    Uses RAPTOR algorithm (Round-Based Public Transit Routing).
    """
    
    def route(self, origin, destination, departure_time) -> list:
        """
        RAPTOR: Find Pareto-optimal journeys (minimize transfers AND arrival time).
        Each round finds journeys with one more transfer.
        """
        # Find walkable transit stops from origin/destination
        origin_stops = self.find_nearby_stops(origin, max_walk_km=0.8)
        dest_stops = self.find_nearby_stops(destination, max_walk_km=0.8)
        
        MAX_TRANSFERS = 3
        INF = float('inf')
        
        # earliest_arrival[k][stop] = earliest arrival at stop with k transfers
        earliest = [[INF] * self.num_stops for _ in range(MAX_TRANSFERS + 1)]
        
        # Initialize: walk to initial stops
        marked_stops = set()
        for stop_id, walk_time in origin_stops:
            earliest[0][stop_id] = departure_time + walk_time
            marked_stops.add(stop_id)
        
        # RAPTOR rounds
        for k in range(1, MAX_TRANSFERS + 1):
            # Copy previous round's results
            for s in range(self.num_stops):
                earliest[k][s] = earliest[k-1][s]
            
            new_marked = set()
            
            # For each marked stop, scan routes through it
            for stop_id in marked_stops:
                for route in self.get_routes_through_stop(stop_id):
                    # Board this route at stop_id
                    board_time = earliest[k-1][stop_id]
                    trip = self.get_earliest_trip(route, stop_id, board_time)
                    
                    if trip is None:
                        continue
                    
                    # Traverse route forward, updating arrival times
                    for next_stop, arrival_time in self.traverse_trip(trip, stop_id):
                        if arrival_time < earliest[k][next_stop]:
                            earliest[k][next_stop] = arrival_time
                            new_marked.add(next_stop)
            
            # Transfers: walking between nearby stops
            for stop_id in new_marked:
                for transfer_stop, walk_time in self.get_transfers(stop_id):
                    arr = earliest[k][stop_id] + walk_time
                    if arr < earliest[k][transfer_stop]:
                        earliest[k][transfer_stop] = arr
                        new_marked.add(transfer_stop)
            
            marked_stops = new_marked
            if not marked_stops:
                break
        
        # Extract Pareto-optimal journeys to destination
        journeys = []
        for stop_id, walk_time in dest_stops:
            for k in range(MAX_TRANSFERS + 1):
                arrival = earliest[k][stop_id] + walk_time
                journeys.append({
                    "arrival_time": arrival,
                    "transfers": k,
                    "final_walk": walk_time
                })
        
        return self.pareto_filter(journeys)
```

## 7. Deep Dive: Traffic Prediction

### 7.1 Real-Time Traffic Processing

```python
class TrafficProcessor:
    """
    Processes probe data from millions of devices to estimate
    per-segment traffic conditions in real-time.
    """
    
    def __init__(self):
        self.segment_buffer = {}  # segment_id → list of speed samples
        self.FLUSH_INTERVAL_SEC = 30
        self.MIN_SAMPLES = 3  # Minimum probes to update a segment
    
    def process_probe(self, probe: dict):
        """
        Probe data: {device_id, lat, lng, speed, heading, timestamp}
        1. Map-match probe to road segment
        2. Buffer speed observation
        3. Periodically aggregate and publish
        """
        # Map matching: snap GPS point to nearest road segment
        segment = self.map_match(probe["lat"], probe["lng"], probe["heading"])
        
        if segment is None:
            return
        
        # Buffer the speed observation
        if segment.id not in self.segment_buffer:
            self.segment_buffer[segment.id] = []
        
        self.segment_buffer[segment.id].append({
            "speed": probe["speed"],
            "timestamp": probe["timestamp"],
            "confidence": self.estimate_confidence(probe)
        })
    
    def flush_aggregates(self):
        """Aggregate buffered probes and update traffic state."""
        updates = {}
        
        for segment_id, samples in self.segment_buffer.items():
            if len(samples) < self.MIN_SAMPLES:
                continue
            
            # Weighted median (more recent = higher weight)
            speeds = sorted(samples, key=lambda s: s["speed"])
            weights = [s["confidence"] for s in speeds]
            
            median_speed = self.weighted_median(
                [s["speed"] for s in speeds], weights
            )
            
            # Determine congestion level
            free_flow = self.get_free_flow_speed(segment_id)
            ratio = median_speed / free_flow if free_flow > 0 else 1.0
            
            congestion = self.ratio_to_congestion(ratio)
            
            updates[segment_id] = {
                "speed_kmh": int(median_speed),
                "congestion": congestion,
                "confidence": min(1.0, len(samples) / 10),
                "sample_count": len(samples)
            }
        
        # Publish updates
        self.publish_traffic_updates(updates)
        self.segment_buffer.clear()
    
    def ratio_to_congestion(self, ratio: float) -> str:
        if ratio >= 0.85:
            return "free"
        elif ratio >= 0.65:
            return "light"
        elif ratio >= 0.40:
            return "moderate"
        elif ratio >= 0.20:
            return "heavy"
        else:
            return "blocked"
```

### 7.2 Traffic Prediction ML Model

```python
class TrafficPredictor:
    """
    Predicts traffic conditions for future time windows.
    Combines historical patterns with real-time observations.
    
    Model: Temporal Graph Convolutional Network
    Input: historical speeds + current speeds + features (time, day, weather, events)
    Output: predicted speeds for next 15/30/60 minutes per segment
    """
    
    def predict_segment_speed(self, segment_id: int, target_time: int) -> float:
        """
        Ensemble prediction combining:
        1. Historical average for this time/day
        2. Recent trend (last 30 min trajectory)
        3. ML model prediction
        """
        # Historical baseline
        day_of_week = self.get_day_of_week(target_time)
        time_bucket = self.get_15min_bucket(target_time)  # 0-95
        historical_speed = self.get_historical_speed(segment_id, day_of_week, time_bucket)
        
        # Recent trend
        recent_speeds = self.get_recent_speeds(segment_id, window_min=30)
        trend = self.calculate_trend(recent_speeds)
        trend_predicted = recent_speeds[-1] + trend * (target_time - time.time()) / 60
        
        # ML model (pre-computed for common horizons)
        ml_prediction = self.ml_model.predict(
            segment_id=segment_id,
            features={
                "current_speed": recent_speeds[-1] if recent_speeds else historical_speed,
                "historical_speed": historical_speed,
                "day_of_week": day_of_week,
                "time_of_day": time_bucket,
                "is_holiday": self.is_holiday(target_time),
                "weather": self.get_weather_condition(),
                "neighbor_speeds": self.get_neighbor_speeds(segment_id)
            }
        )
        
        # Ensemble (weighted by confidence)
        weights = [0.2, 0.3, 0.5]  # historical, trend, ML
        predicted = (
            weights[0] * historical_speed +
            weights[1] * max(0, trend_predicted) +
            weights[2] * ml_prediction
        )
        
        return max(5, predicted)  # Minimum 5 km/h (not zero)
    
    def compute_eta(self, route_segments: list, departure_time: int) -> int:
        """
        Compute ETA by summing predicted travel times along route.
        Accounts for time progression (later segments use later predictions).
        """
        total_seconds = 0
        current_time = departure_time
        
        for segment in route_segments:
            predicted_speed = self.predict_segment_speed(segment.id, current_time)
            # Convert speed to travel time for this segment
            segment_time = (segment.length_meters / 1000) / (predicted_speed / 3600)
            total_seconds += segment_time
            current_time += segment_time
        
        return int(total_seconds)
```

## 8. Deep Dive: Map Tile Rendering

### 8.1 Vector Tile Generation Pipeline

```python
class VectorTileGenerator:
    """
    Generates Mapbox Vector Tiles (MVT) from geographic data.
    Tiles contain geometry + attributes, rendered client-side.
    
    Advantages over raster:
    - 10x smaller file size
    - Client-side styling (dark mode, custom themes)
    - Smooth rotation/tilt
    - Resolution independent
    """
    
    TILE_SIZE = 4096  # Internal coordinate space
    
    def generate_tile(self, z: int, x: int, y: int) -> bytes:
        """Generate a single vector tile at the specified coordinates."""
        
        # Calculate tile bounds in geographic coordinates
        bounds = self.tile_to_bounds(z, x, y)
        
        # Buffer for including features slightly outside tile (prevents edge artifacts)
        buffer_deg = self.get_buffer(z)
        buffered_bounds = self.expand_bounds(bounds, buffer_deg)
        
        layers = []
        
        # Layer 1: Roads (different detail levels per zoom)
        roads = self.query_roads(buffered_bounds, z)
        road_layer = self.build_layer("roads", roads, z)
        layers.append(road_layer)
        
        # Layer 2: Buildings (only at zoom >= 15)
        if z >= 15:
            buildings = self.query_buildings(buffered_bounds)
            layers.append(self.build_layer("buildings", buildings, z))
        
        # Layer 3: Water bodies
        water = self.query_water(buffered_bounds, z)
        layers.append(self.build_layer("water", water, z))
        
        # Layer 4: Land use (parks, residential, commercial)
        landuse = self.query_landuse(buffered_bounds, z)
        layers.append(self.build_layer("landuse", landuse, z))
        
        # Layer 5: Labels
        if z >= 10:
            labels = self.query_labels(buffered_bounds, z)
            layers.append(self.build_layer("labels", labels, z))
        
        # Layer 6: POIs (zoom >= 14)
        if z >= 14:
            pois = self.query_pois(buffered_bounds, z)
            layers.append(self.build_layer("pois", pois, z))
        
        # Encode to MVT protobuf format
        tile_data = self.encode_mvt(layers)
        
        # Compress with gzip
        return gzip.compress(tile_data)
    
    def simplify_geometry(self, geometry, z: int):
        """
        Douglas-Peucker simplification based on zoom level.
        Lower zoom = more aggressive simplification.
        """
        tolerance = self.get_simplification_tolerance(z)
        # At zoom 0: tolerance ~1000m (only major features)
        # At zoom 14: tolerance ~1m (street-level detail)
        # At zoom 20: tolerance ~0.01m (building outlines)
        return geometry.simplify(tolerance, preserve_topology=True)
    
    def get_road_filter(self, z: int) -> list:
        """Which road classes to include at each zoom level."""
        filters = {
            0: ["motorway"],
            4: ["motorway", "trunk"],
            7: ["motorway", "trunk", "primary"],
            10: ["motorway", "trunk", "primary", "secondary"],
            12: ["motorway", "trunk", "primary", "secondary", "tertiary"],
            14: ["motorway", "trunk", "primary", "secondary", "tertiary", "residential"],
            16: ["motorway", "trunk", "primary", "secondary", "tertiary", "residential", "service"]
        }
        for min_zoom in sorted(filters.keys(), reverse=True):
            if z >= min_zoom:
                return filters[min_zoom]
        return filters[0]
```

### 8.2 Progressive Tile Loading

```python
class TileLoadingStrategy:
    """
    Client-side tile loading with progressive enhancement.
    Load low-res tiles first, then upgrade to high-res.
    """
    
    def get_tiles_for_viewport(self, viewport, target_zoom: int) -> list:
        """
        Strategy:
        1. Show cached tiles immediately (any zoom level)
        2. Request parent tiles (z-2) for quick coverage
        3. Request target zoom tiles for detail
        4. Pre-fetch adjacent tiles for smooth panning
        """
        tiles_needed = []
        
        # Immediate: use any cached tile that covers viewport
        cached = self.get_cached_tiles(viewport)
        
        # Priority 1: Parent tiles for quick fill (if not cached at target zoom)
        parent_zoom = max(0, target_zoom - 2)
        parent_tiles = self.calculate_tile_coords(viewport, parent_zoom)
        for tile in parent_tiles:
            if not self.is_cached(tile):
                tiles_needed.append({"tile": tile, "priority": "high"})
        
        # Priority 2: Target zoom tiles
        target_tiles = self.calculate_tile_coords(viewport, target_zoom)
        for tile in target_tiles:
            if not self.is_cached(tile):
                tiles_needed.append({"tile": tile, "priority": "medium"})
        
        # Priority 3: Prefetch adjacent (for panning)
        adjacent = self.get_adjacent_tiles(target_tiles)
        for tile in adjacent:
            if not self.is_cached(tile):
                tiles_needed.append({"tile": tile, "priority": "low"})
        
        return tiles_needed
```

## 9. Component Configuration

### 9.1 Routing Service Deployment

```yaml
routing_service:
  instances: 50 per region
  memory: 128GB per instance  # In-memory road graph
  cpu: 32 cores
  graph_data:
    global_graph_size: 50GB compressed, 200GB in memory
    partition_strategy: geographic (continent → country → region)
    update_frequency: weekly (full), daily (traffic weights)
  
  ch_preprocessing:
    duration: ~4 hours for global graph
    triggered_by: weekly map update
    output: binary CH graph + shortcuts

  caching:
    route_cache: Redis, 5-minute TTL, LRU eviction
    popular_routes: pre-computed, top 100K O-D pairs per city
```

### 9.2 CDN Configuration for Tiles

```yaml
cdn_config:
  provider: CloudFront
  origins:
    - s3://map-tiles-{region} (primary)
    - tile-renderer-service (fallback, on-demand generation)
  
  cache_behaviors:
    base_tiles:
      path_pattern: "/tiles/vector/{z}/{x}/{y}.mvt"
      ttl: 86400  # 24 hours (base map changes weekly)
      compress: true
      
    traffic_tiles:
      path_pattern: "/tiles/traffic/*"
      ttl: 30  # 30 seconds (real-time data)
      compress: true
      
    satellite:
      path_pattern: "/tiles/satellite/*"
      ttl: 604800  # 7 days
      
  edge_locations: 400+ globally
  estimated_hit_rate: 95% for base tiles, 60% for traffic
```

### 9.3 Kafka Topics

```yaml
kafka_topics:
  traffic.probes:
    partitions: 512
    replication: 3
    retention: 1h
    compression: snappy
    throughput: 5M events/sec
    
  traffic.segments:
    partitions: 128
    replication: 3
    retention: 24h
    compaction: enabled (latest per segment)
    
  map.updates:
    partitions: 32
    replication: 3
    retention: 7d
```

## 10. Observability

### 10.1 Key Metrics

```yaml
routing_metrics:
  - route_calculation_latency_ms (p50, p95, p99 by mode)
  - route_cache_hit_rate
  - nodes_explored_per_query (efficiency indicator)
  - alternative_routes_generated
  
tile_metrics:
  - tile_request_rate (by zoom level)
  - cdn_cache_hit_rate
  - tile_generation_latency_ms
  - tile_size_bytes_avg
  
traffic_metrics:
  - probe_ingestion_rate
  - segment_coverage_percent (segments with fresh data)
  - eta_accuracy_percent (predicted vs actual)
  - traffic_update_latency_ms

alerts:
  - route_latency_p99 > 2s → page
  - cdn_hit_rate < 80% → warn
  - probe_lag > 60s → critical
  - eta_error > 30% → investigate
```

## 11. Trade-offs and Considerations

### 11.1 CH vs Dynamic Routing
- **CH**: 1000x faster queries but requires hours of preprocessing; can't handle real-time road closures
- **A*/ALT**: Slower but supports dynamic weights
- **Solution**: Use CH for 95% of queries, fall back to A* when road graph changes detected within 4-hour window

### 11.2 Vector vs Raster Tiles
- **Vector**: Smaller, client-styled, rotatable; requires powerful client GPU
- **Raster**: Pre-rendered, universally supported; large, fixed style
- **Solution**: Vector primary, raster fallback for low-end devices

### 11.3 Traffic Data Privacy
- Probe data from user devices raises privacy concerns
- Solution: Aggregate at segment level (no individual trajectories stored), differential privacy for low-traffic roads, k-anonymity (minimum 3 probes per segment)

### 11.4 Offline Maps
- Full detail offline: 2-5 GB per country
- Solution: Compact vector tiles + basic routing graph; no traffic, limited POI
- Progressive sync: WiFi-only download, delta updates

### 11.5 Global vs Regional Deployment
- Road graph too large for single server (200GB+ in memory)
- Solution: Geographic partitioning with border-node stitching for cross-region routes
- Challenge: Cross-continental routes require multi-hop coordination
