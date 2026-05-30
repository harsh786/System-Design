"""
Cell-Based Architecture for AI Systems.

Implements cell definition, tenant routing, isolation, cross-cell communication,
scaling, hot tenant detection, health monitoring, and failover.
"""

from __future__ import annotations

import hashlib
import random
import time
import threading
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable


# ---------------------------------------------------------------------------
# Cell Definition
# ---------------------------------------------------------------------------

class CellStatus(Enum):
    ACTIVE = "active"
    DRAINING = "draining"     # No new tenants, finishing existing
    MAINTENANCE = "maintenance"
    FAILED = "failed"


@dataclass
class CellCapacity:
    max_tenants: int = 10_000
    max_rps: float = 50.0
    max_concurrent_requests: int = 500
    max_storage_gb: float = 100.0


@dataclass
class CellMetrics:
    tenant_count: int = 0
    current_rps: float = 0.0
    concurrent_requests: int = 0
    storage_used_gb: float = 0.0
    cpu_utilization: float = 0.0
    memory_utilization: float = 0.0
    error_rate: float = 0.0
    p99_latency_ms: float = 0.0
    last_health_check: float = field(default_factory=time.time)


@dataclass
class Cell:
    """A single isolated cell containing a subset of tenants."""

    cell_id: str
    region: str
    capacity: CellCapacity = field(default_factory=CellCapacity)
    metrics: CellMetrics = field(default_factory=CellMetrics)
    status: CellStatus = CellStatus.ACTIVE

    # Components within the cell
    gateway_endpoint: str = ""
    worker_pool_id: str = ""
    vector_db_shard: str = ""
    cache_cluster: str = ""
    queue_partition: str = ""

    # Failover
    backup_cell_id: str = ""

    @property
    def utilization(self) -> float:
        """Overall utilization score (0.0 to 1.0)."""
        scores = [
            self.metrics.tenant_count / max(self.capacity.max_tenants, 1),
            self.metrics.current_rps / max(self.capacity.max_rps, 1),
            self.metrics.concurrent_requests / max(self.capacity.max_concurrent_requests, 1),
            self.metrics.storage_used_gb / max(self.capacity.max_storage_gb, 1),
        ]
        return max(scores)

    @property
    def is_healthy(self) -> bool:
        return (
            self.status == CellStatus.ACTIVE
            and self.metrics.error_rate < 0.10
            and self.metrics.p99_latency_ms < 5000
            and time.time() - self.metrics.last_health_check < 30
        )

    @property
    def can_accept_tenants(self) -> bool:
        return (
            self.status == CellStatus.ACTIVE
            and self.metrics.tenant_count < self.capacity.max_tenants * 0.9
            and self.utilization < 0.8
        )


# ---------------------------------------------------------------------------
# Tenant-to-Cell Routing
# ---------------------------------------------------------------------------

@dataclass
class TenantAssignment:
    tenant_id: str
    cell_id: str
    assigned_at: float = field(default_factory=time.time)
    is_hot: bool = False
    request_count_last_hour: int = 0


class CellRouter:
    """Routes tenants to cells and manages assignments."""

    def __init__(self):
        self._cells: dict[str, Cell] = {}
        self._assignments: dict[str, TenantAssignment] = {}
        self._hot_tenant_threshold_rps: float = 5.0
        self._lock = threading.Lock()

    # --- Cell Management ---

    def add_cell(self, cell: Cell) -> None:
        self._cells[cell.cell_id] = cell

    def remove_cell(self, cell_id: str) -> list[str]:
        """Remove cell, return list of tenants that need reassignment."""
        cell = self._cells.get(cell_id)
        if not cell:
            return []
        cell.status = CellStatus.DRAINING
        displaced = [
            t.tenant_id for t in self._assignments.values() if t.cell_id == cell_id
        ]
        return displaced

    def get_cell(self, cell_id: str) -> Cell | None:
        return self._cells.get(cell_id)

    # --- Routing ---

    def route_tenant(self, tenant_id: str) -> Cell | None:
        """Get the cell for a tenant, assigning if needed."""
        with self._lock:
            assignment = self._assignments.get(tenant_id)
            if assignment:
                cell = self._cells.get(assignment.cell_id)
                if cell and cell.is_healthy:
                    return cell
                # Cell unhealthy — failover
                return self._failover_tenant(tenant_id, assignment)

            # New tenant — assign to best cell
            return self._assign_tenant(tenant_id)

    def _assign_tenant(self, tenant_id: str) -> Cell | None:
        """Assign a new tenant to the least-loaded cell."""
        # Consistent hashing as primary, load-based as tiebreaker
        candidates = [c for c in self._cells.values() if c.can_accept_tenants]
        if not candidates:
            return None

        # Use consistent hash to get preferred cell
        hash_val = int(hashlib.md5(tenant_id.encode()).hexdigest(), 16)
        candidates.sort(key=lambda c: c.cell_id)
        preferred_idx = hash_val % len(candidates)
        cell = candidates[preferred_idx]

        # If preferred is too loaded, pick least loaded
        if cell.utilization > 0.7:
            cell = min(candidates, key=lambda c: c.utilization)

        self._assignments[tenant_id] = TenantAssignment(
            tenant_id=tenant_id, cell_id=cell.cell_id
        )
        cell.metrics.tenant_count += 1
        return cell

    def _failover_tenant(self, tenant_id: str, assignment: TenantAssignment) -> Cell | None:
        """Failover tenant to backup cell or find new one."""
        current_cell = self._cells.get(assignment.cell_id)

        # Try backup cell
        if current_cell and current_cell.backup_cell_id:
            backup = self._cells.get(current_cell.backup_cell_id)
            if backup and backup.is_healthy and backup.can_accept_tenants:
                assignment.cell_id = backup.cell_id
                backup.metrics.tenant_count += 1
                return backup

        # Find any available cell
        del self._assignments[tenant_id]
        return self._assign_tenant(tenant_id)

    # --- Hot Tenant Detection ---

    def detect_hot_tenants(self) -> list[TenantAssignment]:
        """Identify tenants exceeding normal usage thresholds."""
        hot = []
        for assignment in self._assignments.values():
            # In production, this would check actual RPS from metrics
            if assignment.request_count_last_hour > self._hot_tenant_threshold_rps * 3600:
                assignment.is_hot = True
                hot.append(assignment)
        return hot

    def isolate_hot_tenant(self, tenant_id: str) -> Cell | None:
        """Move a hot tenant to a dedicated cell."""
        assignment = self._assignments.get(tenant_id)
        if not assignment:
            return None

        # Find a cell with low utilization or create dedicated
        # In production: provision a new cell for this tenant
        candidates = [
            c for c in self._cells.values()
            if c.can_accept_tenants and c.utilization < 0.3
        ]
        if not candidates:
            return None

        new_cell = candidates[0]
        old_cell = self._cells.get(assignment.cell_id)
        if old_cell:
            old_cell.metrics.tenant_count -= 1

        assignment.cell_id = new_cell.cell_id
        new_cell.metrics.tenant_count += 1
        return new_cell


# ---------------------------------------------------------------------------
# Cross-Cell Communication
# ---------------------------------------------------------------------------

class CrossCellBus:
    """Handles communication between cells (rare, for admin/global ops)."""

    def __init__(self):
        self._handlers: dict[str, list[Callable]] = defaultdict(list)

    def subscribe(self, event_type: str, handler: Callable) -> None:
        self._handlers[event_type].append(handler)

    def publish(self, event_type: str, source_cell: str, payload: dict[str, Any]) -> None:
        """Publish event to all subscribers (async in production)."""
        for handler in self._handlers.get(event_type, []):
            handler(source_cell, payload)

    # Standard cross-cell events
    def broadcast_config_update(self, source_cell: str, config: dict) -> None:
        self.publish("config_update", source_cell, config)

    def request_tenant_migration(self, source_cell: str, tenant_id: str, target_cell: str) -> None:
        self.publish("tenant_migration", source_cell, {
            "tenant_id": tenant_id,
            "target_cell": target_cell,
        })

    def report_cell_failure(self, cell_id: str, reason: str) -> None:
        self.publish("cell_failure", cell_id, {"reason": reason})


# ---------------------------------------------------------------------------
# Cell Health Monitor
# ---------------------------------------------------------------------------

class CellHealthMonitor:
    """Monitors cell health and triggers failover when needed."""

    def __init__(self, router: CellRouter, bus: CrossCellBus):
        self.router = router
        self.bus = bus
        self._check_interval_seconds = 10.0
        self._consecutive_failures: dict[str, int] = defaultdict(int)
        self._failover_threshold = 3

    def check_all_cells(self) -> dict[str, Any]:
        """Run health check on all cells. Returns status report."""
        report = {"healthy": [], "degraded": [], "failed": [], "actions_taken": []}

        for cell_id, cell in self.router._cells.items():
            if cell.status == CellStatus.MAINTENANCE:
                continue

            if cell.is_healthy:
                self._consecutive_failures[cell_id] = 0
                report["healthy"].append(cell_id)
            elif cell.metrics.error_rate > 0.5 or cell.metrics.p99_latency_ms > 10000:
                self._consecutive_failures[cell_id] += 1
                if self._consecutive_failures[cell_id] >= self._failover_threshold:
                    self._trigger_failover(cell, report)
                else:
                    report["degraded"].append(cell_id)
            else:
                report["degraded"].append(cell_id)

        return report

    def _trigger_failover(self, cell: Cell, report: dict) -> None:
        """Trigger failover for a failing cell."""
        cell.status = CellStatus.FAILED
        report["failed"].append(cell.cell_id)

        # Notify bus
        self.bus.report_cell_failure(cell.cell_id, "consecutive_health_check_failures")

        # Get displaced tenants
        displaced = self.router.remove_cell(cell.cell_id)
        report["actions_taken"].append({
            "action": "failover",
            "cell": cell.cell_id,
            "displaced_tenants": len(displaced),
        })

        # Reassign tenants
        for tenant_id in displaced:
            if tenant_id in self.router._assignments:
                del self.router._assignments[tenant_id]
            new_cell = self.router._assign_tenant(tenant_id)
            if new_cell:
                report["actions_taken"].append({
                    "action": "reassign",
                    "tenant": tenant_id,
                    "new_cell": new_cell.cell_id,
                })


# ---------------------------------------------------------------------------
# Cell Scaling Manager
# ---------------------------------------------------------------------------

class CellScaler:
    """Manages adding/removing cells based on load."""

    def __init__(self, router: CellRouter):
        self.router = router
        self._scale_up_threshold = 0.75  # avg utilization
        self._scale_down_threshold = 0.25
        self._min_cells = 3
        self._cell_counter = 0

    def evaluate_scaling(self) -> dict[str, Any]:
        """Check if cells need to be added or removed."""
        active_cells = [
            c for c in self.router._cells.values()
            if c.status == CellStatus.ACTIVE
        ]
        if not active_cells:
            return {"action": "scale_up", "reason": "no_active_cells"}

        avg_util = sum(c.utilization for c in active_cells) / len(active_cells)
        max_util = max(c.utilization for c in active_cells)

        if avg_util > self._scale_up_threshold or max_util > 0.9:
            return {
                "action": "scale_up",
                "reason": f"avg_util={avg_util:.2f}, max_util={max_util:.2f}",
                "current_cells": len(active_cells),
                "recommended_new_cells": max(1, int(len(active_cells) * 0.5)),
            }

        if avg_util < self._scale_down_threshold and len(active_cells) > self._min_cells:
            return {
                "action": "scale_down",
                "reason": f"avg_util={avg_util:.2f}",
                "current_cells": len(active_cells),
                "recommended_remove": max(1, int(len(active_cells) * 0.2)),
            }

        return {"action": "none", "avg_util": avg_util, "cells": len(active_cells)}

    def provision_cell(self, region: str) -> Cell:
        """Create and register a new cell."""
        self._cell_counter += 1
        cell_id = f"cell-{region}-{self._cell_counter:04d}"
        cell = Cell(
            cell_id=cell_id,
            region=region,
            gateway_endpoint=f"https://{cell_id}.internal:8443",
            worker_pool_id=f"workers-{cell_id}",
            vector_db_shard=f"vdb-shard-{cell_id}",
            cache_cluster=f"cache-{cell_id}",
            queue_partition=f"queue-{cell_id}",
        )
        self.router.add_cell(cell)
        return cell


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------

def main():
    router = CellRouter()
    bus = CrossCellBus()
    monitor = CellHealthMonitor(router, bus)
    scaler = CellScaler(router)

    print("=" * 60)
    print("CELL-BASED ARCHITECTURE DEMO")
    print("=" * 60)

    # Provision initial cells
    print("\n--- Provisioning cells ---")
    cells = []
    for i in range(5):
        cell = scaler.provision_cell("us-east-1")
        cells.append(cell)
        print(f"  Created: {cell.cell_id}")

    # Set up backup relationships
    for i in range(len(cells) - 1):
        cells[i].backup_cell_id = cells[i + 1].cell_id
    cells[-1].backup_cell_id = cells[0].cell_id

    # Route tenants
    print("\n--- Routing tenants ---")
    tenant_cells = {}
    for i in range(100):
        tenant_id = f"tenant-{i:04d}"
        cell = router.route_tenant(tenant_id)
        if cell:
            tenant_cells[tenant_id] = cell.cell_id

    # Show distribution
    distribution = defaultdict(int)
    for cell_id in tenant_cells.values():
        distribution[cell_id] += 1
    for cell_id, count in sorted(distribution.items()):
        print(f"  {cell_id}: {count} tenants")

    # Simulate hot tenant
    print("\n--- Hot tenant detection ---")
    assignment = router._assignments.get("tenant-0001")
    if assignment:
        assignment.request_count_last_hour = 50000  # Way above threshold
        hot = router.detect_hot_tenants()
        print(f"  Hot tenants detected: {len(hot)}")
        if hot:
            new_cell = router.isolate_hot_tenant(hot[0].tenant_id)
            if new_cell:
                print(f"  Isolated {hot[0].tenant_id} to {new_cell.cell_id}")

    # Simulate cell failure
    print("\n--- Cell failure simulation ---")
    failing_cell = cells[2]
    failing_cell.metrics.error_rate = 0.6
    failing_cell.metrics.p99_latency_ms = 15000
    failing_cell.metrics.last_health_check = time.time()

    for _ in range(3):  # 3 consecutive failures
        report = monitor.check_all_cells()

    print(f"  Healthy: {len(report['healthy'])}")
    print(f"  Degraded: {len(report['degraded'])}")
    print(f"  Failed: {len(report['failed'])}")
    for action in report["actions_taken"][:5]:
        print(f"  Action: {action}")

    # Scaling evaluation
    print("\n--- Scaling evaluation ---")
    scaling = scaler.evaluate_scaling()
    print(f"  Decision: {scaling['action']}")
    if "reason" in scaling:
        print(f"  Reason: {scaling['reason']}")


if __name__ == "__main__":
    main()
