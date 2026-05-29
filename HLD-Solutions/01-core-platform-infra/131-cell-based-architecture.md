# Cell-Based Architecture Design

## 1. Functional Requirements

### Core Features
- **Cell Provisioning**: Automated creation of self-contained deployment units with all services
- **Partition-Based Routing**: Map users/tenants to cells using partition keys
- **Shuffle Sharding**: Assign customers to random cell subsets for blast-radius isolation
- **Cell-by-Cell Deployment**: Progressive rollout across cells with automated rollback
- **Cell Migration**: Move users between cells with zero downtime
- **Health-Based Routing**: Detect unhealthy cells and reroute traffic automatically
- **Cross-Cell Communication**: Minimal, well-defined pathways for cross-cell operations

### User Stories
1. Service team deploys new version → rolls to 1 cell → monitors → continues or rolls back
2. Customer assigned to Cell-A → Cell-A fails → only that customer partition affected
3. New enterprise tenant onboarded → dedicated cell provisioned automatically
4. Cell reaches 80% capacity → users rebalanced to new cell transparently
5. Noisy neighbor detected → isolated to separate cell via shuffle shard boundaries

---

## 2. Non-Functional Requirements

| Metric | Target |
|--------|--------|
| Availability | 99.999% per cell, 99.9999% aggregate |
| Routing Latency | <1ms added per request |
| Cell Count | 1,000+ cells |
| Blast Radius | <0.1% of users affected per cell failure |
| Cell Provisioning | <15 minutes for new cell |
| Migration | Zero dropped requests during user migration |
| Deployment | Cell-by-cell canary with auto-rollback |
| Cross-Cell Traffic | <1% of total request volume |

---

## 3. Capacity Estimation

### Cell Sizing Model
```
Total Users: 1 billion
Cells: 1,000
Users per cell: 1M (average)
RPS per cell: 10,000 (average), 50,000 (peak)
Total RPS: 10M average, 50M peak

Cell composition (per cell):
- Compute: 200 pods across 20 services
- Database: 1 primary + 2 replicas (PostgreSQL)
- Cache: 3-node Redis cluster
- Queue: Dedicated Kafka partition set
- Storage: 5TB data per cell
```

### Routing Layer
```
Routing table size: 1B user → cell mappings
Compressed routing table: ~10GB (user_id → cell_id, 10 bytes/entry)
Routing lookup: O(1) hash map or bloom filter + fallback
Router instances: 50 (stateless, in-memory routing table)
Routing table refresh: Every 30 seconds via pub/sub
```

### Shuffle Sharding Math
```
Cells: 1,000
Shards per customer: 5 (each customer touches 5 cells)
Probability two customers share exact same 5 cells:
  P = C(1000,5)^-1 = 1 / 8.25 × 10^12 ≈ negligible

Probability two customers share ANY cell:
  P = 1 - (995/1000)^5 ≈ 0.025 (2.5%)
  
Blast radius of 1 cell failure: affects 1/1000 = 0.1% of users
With shuffle sharding: each customer's traffic spread across 5 cells
  → single cell failure only affects 20% of one customer's capacity
```

---

## 4. Data Modeling

### Routing Table Schema
```sql
CREATE TABLE cell_assignments (
    partition_key VARCHAR(64) PRIMARY KEY,  -- user_id or tenant_id
    cell_id VARCHAR(32) NOT NULL,
    shard_set INT[] NOT NULL,              -- shuffle shard cell set
    assigned_at TIMESTAMP NOT NULL,
    version BIGINT NOT NULL,
    CONSTRAINT fk_cell FOREIGN KEY (cell_id) REFERENCES cells(cell_id)
);
CREATE INDEX idx_cell_assignments_cell ON cell_assignments(cell_id);

CREATE TABLE cells (
    cell_id VARCHAR(32) PRIMARY KEY,
    region VARCHAR(16) NOT NULL,
    status VARCHAR(16) NOT NULL DEFAULT 'active',  -- active, draining, provisioning, decommissioned
    capacity_limit INT NOT NULL,
    current_load INT NOT NULL DEFAULT 0,
    created_at TIMESTAMP NOT NULL,
    last_deploy_version VARCHAR(64),
    health_score FLOAT DEFAULT 1.0
);
CREATE INDEX idx_cells_region_status ON cells(region, status);

CREATE TABLE cell_health (
    cell_id VARCHAR(32) NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    error_rate FLOAT NOT NULL,
    p99_latency_ms FLOAT NOT NULL,
    cpu_utilization FLOAT NOT NULL,
    memory_utilization FLOAT NOT NULL,
    active_connections INT NOT NULL,
    PRIMARY KEY (cell_id, timestamp)
);

CREATE TABLE deployments (
    deployment_id UUID PRIMARY KEY,
    version VARCHAR(64) NOT NULL,
    status VARCHAR(16) NOT NULL,  -- rolling, paused, completed, rolled_back
    started_at TIMESTAMP NOT NULL,
    cells_completed INT DEFAULT 0,
    cells_total INT NOT NULL,
    rollback_trigger VARCHAR(256)
);

CREATE TABLE deployment_cell_status (
    deployment_id UUID NOT NULL,
    cell_id VARCHAR(32) NOT NULL,
    status VARCHAR(16) NOT NULL,  -- pending, deploying, baking, completed, failed
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    PRIMARY KEY (deployment_id, cell_id)
);

CREATE TABLE migrations (
    migration_id UUID PRIMARY KEY,
    partition_key VARCHAR(64) NOT NULL,
    source_cell VARCHAR(32) NOT NULL,
    target_cell VARCHAR(32) NOT NULL,
    status VARCHAR(16) NOT NULL,  -- preparing, dual_write, draining, completed
    started_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP
);
```

### Cell Configuration Document (stored in each cell)
```json
{
  "cell_id": "cell-us-east-042",
  "region": "us-east-1",
  "partition_range": {"start": "0x00000000", "end": "0x003FFFFF"},
  "services": {
    "user-service": {"replicas": 10, "version": "v2.3.1"},
    "order-service": {"replicas": 8, "version": "v1.9.0"},
    "payment-service": {"replicas": 5, "version": "v3.1.2"}
  },
  "database": {
    "primary": "cell-042-db-primary.internal",
    "replicas": ["cell-042-db-r1.internal", "cell-042-db-r2.internal"]
  },
  "capacity": {"max_users": 1200000, "max_rps": 60000}
}
```

---

## 5. High-Level Design (HLD)

### ASCII Architecture Diagram
```
                    ┌─────────────────────────────────────────┐
                    │           Global Load Balancer            │
                    │         (Anycast / CloudFront)            │
                    └─────────────────┬───────────────────────┘
                                      │
                    ┌─────────────────▼───────────────────────┐
                    │          Cell Router (Stateless)          │
                    │  ┌─────────────────────────────────┐     │
                    │  │ Routing Table (in-memory hash)   │     │
                    │  │ user_id → cell_id lookup         │     │
                    │  └─────────────────────────────────┘     │
                    └───┬──────────┬──────────┬───────────────┘
                        │          │          │
            ┌───────────▼──┐  ┌───▼────────┐ │  ┌─────────────┐
            │   Cell A     │  │   Cell B   │ │  │   Cell N    │
            │ ┌──────────┐ │  │            │ │  │             │
            │ │ Services  │ │  │  Services  │ │  │  Services   │
            │ ├──────────┤ │  │            │ │  │             │
            │ │ Database  │ │  │  Database  │ │  │  Database   │
            │ ├──────────┤ │  │            │ │  │             │
            │ │ Cache     │ │  │  Cache     │ │  │  Cache      │
            │ ├──────────┤ │  │            │ │  │             │
            │ │ Queue     │ │  │  Queue     │ │  │  Queue      │
            │ └──────────┘ │  │            │ │  │             │
            └──────────────┘  └────────────┘ │  └─────────────┘
                                             │
                    ┌────────────────────────▼─────────────────┐
                    │         Control Plane (Global)            │
                    │  - Cell Registry                          │
                    │  - Deployment Orchestrator                │
                    │  - Health Aggregator                      │
                    │  - Migration Controller                   │
                    │  - Routing Table Publisher                 │
                    └──────────────────────────────────────────┘
```

### Component Descriptions

1. **Global Load Balancer**: Anycast entry point, terminates TLS, forwards to nearest router
2. **Cell Router**: Stateless layer that looks up partition key → cell mapping, routes request
3. **Cell (Self-Contained Unit)**: Contains all services, databases, caches needed to serve its user partition independently
4. **Control Plane**: Global singleton managing cell lifecycle, deployments, health, and routing table updates

### Request Flow
```
1. Client → Global LB (anycast, nearest PoP)
2. LB → Cell Router (extracts partition key from request: user_id header, JWT, or URL)
3. Router → lookup routing table → find cell_id
4. Router → forward request to Cell ingress
5. Cell processes request entirely locally (DB, cache, queue all cell-local)
6. Response returns via same path
```

---

## 6. Low-Level Design (LLD) - APIs

### Cell Router API (Internal)
```
POST /route
Headers: X-Partition-Key: {user_id}
→ Proxied to: https://cell-{id}.internal/{original_path}

GET /admin/routing-table/stats
Response:
{
  "total_entries": 1000000000,
  "cells_active": 987,
  "cells_draining": 3,
  "last_refresh": "2024-01-15T10:30:00Z",
  "table_version": 458923
}
```

### Cell Management API
```
POST /cells
Request:
{
  "region": "us-east-1",
  "capacity_limit": 1000000,
  "template": "standard-cell-v3"
}
Response: 201
{
  "cell_id": "cell-us-east-043",
  "status": "provisioning",
  "estimated_ready": "2024-01-15T10:45:00Z"
}

POST /cells/{cell_id}/drain
Request: { "target_cell": "cell-us-east-044", "rate_limit_per_sec": 1000 }
Response: 202 { "migration_id": "mig-uuid-123" }

GET /cells/{cell_id}/health
Response:
{
  "cell_id": "cell-us-east-042",
  "health_score": 0.95,
  "metrics": {
    "error_rate": 0.002,
    "p99_latency_ms": 45,
    "cpu_pct": 62,
    "memory_pct": 71,
    "rps": 12400
  }
}
```

### Deployment API
```
POST /deployments
Request:
{
  "version": "v2.4.0",
  "strategy": "canary",
  "canary_cells": 3,
  "bake_time_minutes": 30,
  "rollback_threshold": { "error_rate": 0.01, "latency_p99_ms": 200 }
}
Response: 202
{
  "deployment_id": "dep-uuid-456",
  "status": "rolling",
  "cells_completed": 0,
  "cells_total": 1000
}

POST /deployments/{id}/pause
POST /deployments/{id}/resume
POST /deployments/{id}/rollback
```

### Migration API
```
POST /migrations
Request:
{
  "partition_keys": ["user-123", "user-456"],
  "source_cell": "cell-us-east-042",
  "target_cell": "cell-us-east-043",
  "strategy": "dual-write-then-switch"
}
Response: 202
{
  "migration_id": "mig-uuid-789",
  "status": "preparing",
  "estimated_duration_sec": 300
}
```

---

## 7. Deep Dives

### Deep Dive 1: Cell Sizing Strategy

**Problem**: How large should each cell be? Smaller cells reduce blast radius but increase operational overhead.

**Analysis - Thin Cells vs Fat Cells**:
```
Thin Cell (1K users):
  + Blast radius: 0.0001% per cell failure
  + Fast provisioning, easy to reason about
  - 1M cells needed → massive operational overhead
  - Resource underutilization (each cell needs min baseline)
  - Control plane managing 1M cells is complex

Fat Cell (10M users):
  + Only 100 cells → simple operations
  + High resource utilization
  - Blast radius: 1% per failure (10M users affected)
  - Long deployment cycles (fewer canary data points)
  - Harder to migrate users out

Sweet Spot (1M users, 1000 cells):
  + Blast radius: 0.1% per failure
  + Manageable operational overhead
  + Good deployment velocity (meaningful canary per cell)
  + Reasonable control plane load
```

**Cell-Per-Tenant for Enterprise**:
```
Large enterprise customers (>100K users) get dedicated cells:
- Complete isolation (noisy neighbor elimination)
- Custom SLAs and deployment schedules
- Dedicated resources, no contention
- Premium pricing tier

Small/medium customers share cells:
- Bin-packing: fill cells to 80% capacity target
- Shuffle sharding across shared cells
- Cost-efficient, good enough isolation
```

**Capacity Planning Per Cell**:
```python
class CellCapacityPlanner:
    def compute_cell_limits(self, cell_type: str) -> dict:
        if cell_type == "standard":
            return {
                "max_users": 1_000_000,
                "max_rps": 50_000,
                "max_storage_gb": 5_000,
                "max_connections": 100_000,
                "scale_trigger_pct": 80,  # trigger rebalance at 80%
                "hard_limit_pct": 95       # reject new assignments at 95%
            }
        elif cell_type == "enterprise":
            return {
                "max_users": 500_000,  # single tenant, lower density
                "max_rps": 100_000,    # higher per-user RPS allowance
                "max_storage_gb": 20_000,
                "dedicated": True
            }
    
    def should_split_cell(self, cell_metrics: dict) -> bool:
        return (
            cell_metrics["user_count"] > cell_metrics["max_users"] * 0.9 or
            cell_metrics["rps"] > cell_metrics["max_rps"] * 0.85 or
            cell_metrics["storage_gb"] > cell_metrics["max_storage_gb"] * 0.8
        )
```

### Deep Dive 2: Shuffle Sharding Implementation

**Problem**: How to assign customers to cell subsets such that failures are maximally isolated?

**Probability Model**:
```
Given:
  N = number of cells (1000)
  k = cells per customer's shard set (5)

For two customers to share ALL cells (complete overlap):
  P(exact overlap) = 1 / C(N, k) = 1 / C(1000, 5) ≈ 1.2 × 10^-13

For two customers to share at least 1 cell:
  P(≥1 overlap) = 1 - C(N-k, k) / C(N, k)
               = 1 - C(995, 5) / C(1000, 5)
               ≈ 0.0249 (2.49%)

Expected blast radius when 1 cell fails:
  - Without shuffle sharding: 100% of cell's users lose service
  - With shuffle sharding (k=5): Each affected user still has 4/5 = 80% capacity
    Users experience degradation, not outage
```

**Implementation**:
```python
import hashlib
import struct

class ShuffleShardAssigner:
    def __init__(self, cells: list, shard_size: int = 5):
        self.cells = sorted(cells)  # deterministic ordering
        self.shard_size = shard_size
    
    def get_shard_set(self, customer_id: str) -> list:
        """Deterministically assign customer to k cells using stable hashing."""
        selected = []
        attempt = 0
        while len(selected) < self.shard_size:
            seed = f"{customer_id}:{attempt}"
            h = hashlib.sha256(seed.encode()).digest()
            index = struct.unpack(">I", h[:4])[0] % len(self.cells)
            cell = self.cells[index]
            if cell not in selected:
                selected.append(cell)
            attempt += 1
        return selected
    
    def route_request(self, customer_id: str, request_id: str) -> str:
        """Route individual request to one cell from the shard set."""
        shard_set = self.get_shard_set(customer_id)
        # Consistent selection within shard set for session affinity
        h = hashlib.sha256(f"{customer_id}:{request_id}".encode()).digest()
        index = struct.unpack(">I", h[:4])[0] % len(shard_set)
        return shard_set[index]
    
    def handle_cell_failure(self, customer_id: str, failed_cell: str) -> str:
        """Reroute away from failed cell to another in shard set."""
        shard_set = self.get_shard_set(customer_id)
        healthy = [c for c in shard_set if c != failed_cell]
        if not healthy:
            raise Exception("All cells in shard set failed - escalate!")
        # Hash to pick from remaining healthy cells
        h = hashlib.sha256(f"{customer_id}:failover".encode()).digest()
        return healthy[struct.unpack(">I", h[:4])[0] % len(healthy)]
```

**Blast Radius Comparison**:
```
Scenario: Cell-042 has a bad deployment causing 100% failure

Without shuffle sharding:
  - 1M users in Cell-042 → 100% outage for those users
  - Blast radius: 0.1% of total user base, complete outage

With shuffle sharding (k=5):
  - Same 1M users assigned to Cell-042 as one of their 5 cells
  - Each user loses 1/5 = 20% of their capacity
  - Remaining 4 cells handle traffic (with load increase)
  - Blast radius: 0.1% of users experience 20% degradation (not outage)

With shuffle sharding + health-aware routing:
  - Router detects Cell-042 unhealthy
  - Automatically routes to other cells in each user's shard set
  - Users experience brief latency spike, then normal service
  - Effective blast radius: near zero (transient only)
```

### Deep Dive 3: Cell Lifecycle and Migration

**Cell Provisioning Automation**:
```python
class CellProvisioner:
    def provision_cell(self, region: str, template: str) -> Cell:
        """Provision a new cell end-to-end in <15 minutes."""
        cell_id = self.generate_cell_id(region)
        
        # Phase 1: Infrastructure (5 min)
        # - Terraform/CDK deploys: VPC, subnets, security groups
        # - Database cluster (restore from template snapshot)
        # - Redis cluster, Kafka partition set
        # - Kubernetes namespace with resource quotas
        
        # Phase 2: Services (5 min)
        # - Deploy all services at current production version
        # - Run health checks and readiness probes
        # - Warm caches with baseline data
        
        # Phase 3: Integration (3 min)
        # - Register in cell registry
        # - Add to monitoring/alerting
        # - Run integration test suite
        # - Mark cell as "ready" (not yet serving traffic)
        
        # Phase 4: Traffic (2 min)
        # - Assign partition range or specific users
        # - Update routing table
        # - Verify first requests succeed
        
        return Cell(cell_id=cell_id, status="active")
```

**User Migration (Zero-Downtime)**:
```
Migration Protocol (Dual-Write → Switch → Cleanup):

Phase 1 - Prepare (T+0):
  - Mark user as "migrating" in routing table
  - Source cell continues serving reads AND writes
  - Begin replicating user data to target cell

Phase 2 - Dual Write (T+1min):
  - Router sends writes to BOTH source and target cell
  - Reads still served from source cell
  - Target cell catches up on historical data

Phase 3 - Verify (T+5min):
  - Compare data checksums between source and target
  - Run consistency validation queries
  - If mismatch: extend dual-write, investigate

Phase 4 - Switch (T+6min):
  - Atomic routing table update: user → target cell
  - Reads now served from target cell
  - Writes go to target cell only
  - Source cell queues any in-flight writes for forwarding

Phase 5 - Cleanup (T+1hr):
  - Delete user data from source cell
  - Remove migration tracking record
  - Migration complete
```

**Cell Evacuation for Decommission**:
```python
class CellEvacuator:
    def evacuate_cell(self, cell_id: str, reason: str):
        """Gracefully move all users off a cell."""
        cell = self.get_cell(cell_id)
        users = self.get_users_in_cell(cell_id)
        
        # Find target cells with capacity
        targets = self.find_cells_with_capacity(
            region=cell.region,
            needed_capacity=len(users),
            exclude=[cell_id]
        )
        
        # Distribute users across targets (bin-packing)
        assignments = self.bin_pack_users(users, targets)
        
        # Migrate in batches (rate-limited)
        for batch in self.batch(assignments, size=1000):
            for user, target in batch:
                self.migrate_user(user, cell_id, target)
            self.wait_for_batch_completion(batch)
            self.verify_cell_load(targets)  # Don't overwhelm targets
        
        # Mark cell as decommissioned
        self.update_cell_status(cell_id, "decommissioned")
```

---

## 8. Component Optimization

### Routing Table Optimization
```
Challenge: 1B entries, <1ms lookup, refreshed every 30s

Approach 1 - Direct Hash Map (In-Memory):
  - 1B entries × 10 bytes (8-byte user_id + 2-byte cell_id) = 10GB
  - Too large for every router instance

Approach 2 - Range-Based Partitioning:
  - Hash user_id to 32-bit space
  - Divide into 1000 ranges, each mapped to a cell
  - Routing table: 1000 entries (range_start → cell_id)
  - O(log N) binary search = O(log 1000) ≈ 10 comparisons
  - Table size: ~16KB (trivially fits in L1 cache)
  
Approach 3 - Hybrid (Range + Overrides):
  - Default: range-based routing (16KB table)
  - Overrides: specific user → cell mappings for migrations/enterprise
  - Override table: 100K entries × 10 bytes = 1MB
  - Two-tier lookup: check override map first, fall back to range

Selected: Approach 3 (Hybrid)
  - 99.99% of lookups resolved by range table (L1 cache hit)
  - 0.01% enterprise/migrating users resolved by override map
  - Total memory: ~1.5MB per router instance
  - Refresh: range table rarely changes, overrides update via pub/sub
```

### Deployment Orchestration Optimization
```
Problem: Deploy to 1000 cells safely and quickly

Strategy - Exponential Rollout with Bake Times:
  Wave 1: 1 cell (canary), bake 30 min
  Wave 2: 5 cells, bake 15 min
  Wave 3: 50 cells, bake 10 min
  Wave 4: 200 cells, bake 5 min
  Wave 5: remaining 744 cells

  Total time: ~2 hours for full rollout
  Blast radius if bad deploy detected in Wave 1: 0.1% of users

Auto-Rollback Triggers:
  - Error rate > 2× baseline for cell
  - P99 latency > 3× baseline
  - Any cell health score < 0.7
  - Deployment circuit breaker: >2 cells fail in same wave → halt all
```

---

## 9. Observability

### Key Metrics (Per Cell)
```
Cell Health Score (composite):
  health = w1*(1-error_rate) + w2*(1-latency_norm) + w3*(1-saturation)
  where w1=0.4, w2=0.3, w3=0.3

Per-Cell Metrics:
  - cell_rps{cell_id, service}
  - cell_error_rate{cell_id, service, error_code}
  - cell_latency_p50/p99{cell_id, service}
  - cell_saturation{cell_id, resource=cpu|memory|disk|connections}
  - cell_user_count{cell_id}
  - cell_cross_cell_calls{source_cell, target_cell}

Router Metrics:
  - router_lookup_latency_us{method=range|override}
  - router_table_version
  - router_fallback_count (couldn't route, used fallback)

Deployment Metrics:
  - deployment_wave_duration_sec{deployment_id, wave}
  - deployment_rollback_count{reason}
  - deployment_bake_time_anomalies{cell_id}

Migration Metrics:
  - migration_duration_sec{strategy}
  - migration_data_divergence_count
  - migration_in_progress_count
```

### Alerting Rules
```yaml
alerts:
  - name: CellHealthDegraded
    condition: cell_health_score < 0.8 for 2m
    severity: warning
    action: notify on-call

  - name: CellHealthCritical
    condition: cell_health_score < 0.5 for 1m
    severity: critical
    action: auto-drain cell, page on-call

  - name: CrossCellTrafficSpike
    condition: cross_cell_call_rate > 5% of total for 5m
    severity: warning
    action: investigate data locality violation

  - name: DeploymentStalled
    condition: deployment_wave_duration > 2× expected
    severity: warning
    action: pause deployment, notify release engineer

  - name: RoutingTableStale
    condition: router_table_age > 120s
    severity: critical
    action: force refresh, fallback to previous table
```

### Distributed Tracing
```
Trace enrichment for cell-based architecture:
  - span.cell_id: which cell processed this request
  - span.routing_method: range | override | failover
  - span.cross_cell: true if request crossed cell boundary
  - span.migration_state: normal | dual_write | draining
```

---

## 10. Failure Scenarios & Mitigations

| Failure | Impact | Mitigation |
|---------|--------|------------|
| Single cell total failure | 0.1% users affected | Health detection → route to shard set alternatives (shuffle sharding) |
| Router crash | Routing unavailable | Stateless routers behind LB, N+2 redundancy, cached routing at client |
| Bad deployment in cell | Cell degradation | Auto-rollback on metric breach within bake time |
| Routing table corruption | Misrouted requests | Versioned table with checksum, rollback to last known good |
| Cell database failure | Cell data unavailable | Per-cell DB replicas with automated failover, cross-region standby |
| Control plane down | No new deployments/migrations | Cells continue operating independently, routing table cached |
| Noisy neighbor in shared cell | Cell performance degradation | Rate limiting per tenant, auto-migration of noisy tenant to dedicated cell |
| Cross-cell call storm | Cascading overload | Circuit breaker on cross-cell paths, bulkhead per calling cell |
| Cell capacity exceeded | Requests rejected | Auto-split: provision new cell + migrate subset of users |
| Network partition between router and cell | Cell unreachable | Retry to alternate cell in shard set, mark cell unhealthy |

### Cascading Failure Prevention
```
Key principle: Cells share NOTHING except the routing layer.

Isolation boundaries:
  - Separate database clusters per cell (no shared DB)
  - Separate Kafka clusters per cell (no shared queue)
  - Separate connection pools and thread pools
  - Independent deployment pipelines
  - Independent scaling decisions
  
The only shared components:
  - Global Load Balancer (anycast, extremely simple)
  - Cell Router (stateless, O(1) lookup, N+2 redundant)
  - Control Plane (not in request path, graceful degradation)
  
If ANY cell fails, other cells are completely unaffected because
they have zero runtime dependencies on the failed cell.
```

---

## 11. Considerations & Trade-offs

### Trade-offs

| Decision | Chosen | Alternative | Reasoning |
|----------|--------|-------------|-----------|
| Cell size | 1M users | 10K or 10M | Balance blast radius vs operational overhead |
| Routing approach | Range + overrides | Full hash map | Cache-friendly, tiny memory footprint |
| Data isolation | Separate DB per cell | Shared DB with schemas | True isolation, no cross-cell queries possible |
| Deployment | Exponential waves | All-at-once | Progressive risk reduction |
| Cross-cell | Minimize (<1%) | Allow freely | Cell independence is the core value proposition |
| Shuffle sharding k | 5 cells per customer | 2 or 10 | Good blast radius reduction without over-spreading |

### When NOT to Use Cell-Based Architecture
```
- Small scale (<100K users): Overhead not justified
- Highly interconnected data: Social graphs, collaborative editing
  (cross-cell traffic would dominate)
- Low blast-radius tolerance already met by AZ/region redundancy
- Teams too small to manage cell lifecycle automation
```

### Comparison with Alternatives
```
Cell-Based vs Multi-AZ:
  - AZs: infrastructure isolation (hardware, power, network)
  - Cells: application isolation (deployment, data, configuration)
  - Best practice: cells WITHIN AZs (orthogonal concerns)

Cell-Based vs Multi-Region:
  - Regions: geographic isolation, latency optimization
  - Cells: fine-grained blast radius within a region
  - Best practice: multiple cells per region

Cell-Based vs Microservices:
  - Microservices: functional decomposition
  - Cells: deployment/failure domain decomposition
  - Cells contain microservices (cell = complete copy of all services for a partition)
```

### Key Design Principles
```
1. Cell Independence: A cell must be able to operate with zero
   knowledge of other cells' existence or state.

2. Routing Simplicity: The router is the only shared component in
   the request path. Keep it stateless and trivially simple.

3. Blast Radius Math: Always quantify. P(user_affected) = 1/N_cells.
   With shuffle sharding: severity = 1/k of user's capacity.

4. Progressive Trust: New code earns trust cell-by-cell. Never deploy
   to all cells simultaneously.

5. Minimize Cross-Cell: Every cross-cell call is a failure domain
   coupling. Design data models to keep requests cell-local.
```
