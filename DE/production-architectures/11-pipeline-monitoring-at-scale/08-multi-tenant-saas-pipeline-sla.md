# Multi-Tenant SaaS Pipeline SLA Monitoring

## Problem Statement

Multi-tenant data platforms (Snowflake, Databricks, Segment, Fivetran) must guarantee per-tenant SLAs while sharing infrastructure. The challenges:

- **1000s of tenants** with different SLA tiers (free, pro, enterprise)
- **Noisy neighbor problem**: One tenant's burst workload degrades others
- **Resource fairness**: Ensuring equitable CPU, memory, I/O distribution
- **Per-tenant observability**: Monitoring must scale with tenant count without metric explosion
- **SLA compliance tracking**: Proving you meet contractual obligations
- **Tenant isolation**: Failures in one tenant's pipeline shouldn't cascade

Real-world scale: A platform ingesting 500K events/sec across 5000 tenants, each expecting freshness guarantees ranging from 5 minutes (enterprise) to 1 hour (free tier).

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                   MULTI-TENANT PIPELINE ARCHITECTURE                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  INGESTION LAYER                                                            │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐        │
│  │Tenant A │  │Tenant B │  │Tenant C │  │Tenant D │  │  ...    │        │
│  │(Enterprise)│(Pro)    │  │(Free)   │  │(Enterprise)│ (5000)  │        │
│  └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘        │
│       │             │            │             │            │              │
│       ▼             ▼            ▼             ▼            ▼              │
│  ┌──────────────────────────────────────────────────────────────────┐      │
│  │              PRIORITY QUEUE / ROUTING LAYER                       │      │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │      │
│  │  │  P0 Queue    │  │  P1 Queue    │  │  P2 Queue    │          │      │
│  │  │ (Enterprise) │  │  (Pro)       │  │  (Free)      │          │      │
│  │  │  Weight: 60% │  │  Weight: 30% │  │  Weight: 10% │          │      │
│  │  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘          │      │
│  └─────────┼─────────────────┼─────────────────┼──────────────────┘      │
│            │                  │                  │                         │
│            ▼                  ▼                  ▼                         │
│  ┌──────────────────────────────────────────────────────────────────┐      │
│  │              SHARED PROCESSING CLUSTER                            │      │
│  │  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐       │      │
│  │  │Worker 1│ │Worker 2│ │Worker 3│ │Worker 4│ │Worker N│       │      │
│  │  │(T:A,D) │ │(T:B,E) │ │(T:C,F) │ │(T:G,H) │ │(T:...)│       │      │
│  │  └────────┘ └────────┘ └────────┘ └────────┘ └────────┘       │      │
│  │  Kubernetes cluster with resource quotas per namespace           │      │
│  └──────────────────────────────────────────────────────────────────┘      │
│            │                  │                  │                         │
│            ▼                  ▼                  ▼                         │
│  ┌──────────────────────────────────────────────────────────────────┐      │
│  │              TENANT-ISOLATED STORAGE                              │      │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐       │      │
│  │  │ s3://    │  │ s3://    │  │ s3://    │  │ s3://    │       │      │
│  │  │ tenant-a/│  │ tenant-b/│  │ tenant-c/│  │ tenant-d/│       │      │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘       │      │
│  └──────────────────────────────────────────────────────────────────┘      │
│                                                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                    SLA MONITORING LAYER                                      │
│  ┌──────────────────────────────────────────────────────────────────┐      │
│  │  ┌───────────┐  ┌──────────────┐  ┌────────────┐  ┌─────────┐  │      │
│  │  │ Freshness │  │ Noisy        │  │ Resource   │  │  SLA    │  │      │
│  │  │ Tracker   │  │ Neighbor     │  │ Quota      │  │ Report  │  │      │
│  │  │           │  │ Detector     │  │ Enforcer   │  │ Engine  │  │      │
│  │  └───────────┘  └──────────────┘  └────────────┘  └─────────┘  │      │
│  └──────────────────────────────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## SLA Tier Definitions

```
┌────────────────────────────────────────────────────────────────────┐
│                    SLA TIER MATRIX                                   │
├──────────┬──────────────┬─────────────┬───────────┬───────────────┤
│  Tier    │  Freshness   │  Throughput │  Support  │  Price/month  │
├──────────┼──────────────┼─────────────┼───────────┼───────────────┤
│Enterprise│  < 5 min     │  Unlimited  │  24/7     │  $50,000+     │
│  Pro     │  < 15 min    │  10M ev/day │  Business │  $5,000       │
│  Free    │  < 60 min    │  1M ev/day  │  None     │  $0           │
├──────────┼──────────────┼─────────────┼───────────┼───────────────┤
│  SLA %   │  99.9%       │  99.5%      │  N/A      │               │
│  Penalty │  10% credit  │  5% credit  │  N/A      │               │
└──────────┴──────────────┴─────────────┴───────────┴───────────────┘
```

---

## Per-Tenant Monitoring Requirements

### 1. Data Freshness Per Tenant

```python
# Freshness = NOW() - MAX(event_timestamp) for each tenant's latest batch
freshness_query = """
SELECT
    tenant_id,
    DATEDIFF('second', MAX(event_timestamp), CURRENT_TIMESTAMP()) AS freshness_seconds,
    COUNT(*) AS records_in_last_batch
FROM raw_events
WHERE _ingested_at > DATEADD('hour', -2, CURRENT_TIMESTAMP())
GROUP BY tenant_id
"""
```

### 2. Per-Tenant Resource Consumption

Track CPU, memory, I/O per tenant workload to detect imbalances:

| Metric | Dimension | Alert Threshold |
|--------|-----------|----------------|
| CPU seconds | Per tenant per hour | > 3x fair share |
| Memory peak | Per tenant job | > namespace quota |
| I/O bytes | Per tenant per hour | > 2x average |
| Storage growth | Per tenant per day | > quota warning (80%) |
| Event throughput | Per tenant per minute | > tier limit |

### 3. Noisy Neighbor Detection

A noisy neighbor is a tenant consuming disproportionate shared resources:

```
Noise Score = (tenant_resource_usage / fair_share) - 1.0

fair_share = total_cluster_resource / num_active_tenants (weighted by tier)

If Noise Score > 2.0 → Throttle tenant
If Noise Score > 5.0 → Isolate tenant to dedicated resources
```

### 4. Per-Tenant Error Rates

```
Error Rate = failed_events / total_events (per tenant, per 5min window)

Healthy: < 0.1%
Warning: 0.1% - 1%
Critical: > 1%
```

---

## Fair Scheduling and Resource Management

### Weighted Fair Queue Architecture

```
┌──────────────────────────────────────────────────────────┐
│             WEIGHTED FAIR SCHEDULER                        │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  Enterprise (Weight: 6)  ████████████████████████        │
│  Pro        (Weight: 3)  ████████████                    │
│  Free       (Weight: 1)  ████                            │
│                                                          │
│  Scheduling Algorithm: Deficit Weighted Round Robin       │
│                                                          │
│  When burst capacity available:                          │
│    Enterprise: Can burst to 100% of cluster              │
│    Pro:        Can burst to 50% of cluster               │
│    Free:       Cannot burst beyond allocation            │
│                                                          │
├──────────────────────────────────────────────────────────┤
│  MONITORING METRICS:                                     │
│                                                          │
│  • queue_depth{tier="enterprise"} — should always be 0  │
│  • queue_wait_time{tier="pro"} — should be < 30s        │
│  • throttle_count{tier="free"} — expected, track trend  │
│  • scheduler_fairness_index — Jain's fairness (0-1)     │
└──────────────────────────────────────────────────────────┘
```

### Resource Quota Monitoring

```yaml
# Kubernetes ResourceQuota per tenant namespace
apiVersion: v1
kind: ResourceQuota
metadata:
  name: tenant-abc-quota
  namespace: tenant-abc
spec:
  hard:
    requests.cpu: "8"
    requests.memory: "32Gi"
    limits.cpu: "16"
    limits.memory: "64Gi"
    persistentvolumeclaims: "10"
    pods: "50"
```

---

## Multi-Tenant Metric Cardinality Challenge

### The Label Explosion Problem

```
Naive approach:
  metric{tenant_id="t1", table="orders", region="us-east"} 
  
  5000 tenants × 50 metrics × 10 tables × 3 regions = 7.5M time series
  
  At 15s scrape interval = 30B samples/day = UNSUSTAINABLE
```

### Solutions for High Cardinality

```
┌────────────────────────────────────────────────────────────────┐
│           CARDINALITY MANAGEMENT STRATEGIES                      │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  1. HIERARCHICAL AGGREGATION                                   │
│     ┌─────────────┐                                            │
│     │  Raw (15s)  │ ──▶ Keep for 2 hours (hot tenants only)  │
│     └──────┬──────┘                                            │
│            ▼                                                   │
│     ┌─────────────┐                                            │
│     │ 1min rollup │ ──▶ Keep for 24 hours (all tenants)      │
│     └──────┬──────┘                                            │
│            ▼                                                   │
│     ┌─────────────┐                                            │
│     │ 5min rollup │ ──▶ Keep for 30 days                     │
│     └──────┬──────┘                                            │
│            ▼                                                   │
│     ┌─────────────┐                                            │
│     │  1hr rollup │ ──▶ Keep for 1 year                      │
│     └─────────────┘                                            │
│                                                                │
│  2. TENANT SAMPLING                                            │
│     • Enterprise: 100% of metrics at full resolution          │
│     • Pro: 100% of metrics at 1min resolution                 │
│     • Free: Sampled 10% + aggregated only                     │
│                                                                │
│  3. METRIC NAMESPACING                                         │
│     • Separate Prometheus instances per tier                   │
│     • Thanos for global query across all                      │
│     • Recording rules for cross-tenant aggregations           │
│                                                                │
│  4. ADAPTIVE COLLECTION                                        │
│     • Increase resolution when SLA at risk                    │
│     • Decrease resolution for healthy tenants                 │
└────────────────────────────────────────────────────────────────┘
```

### Thanos/Mimir Architecture for Multi-Tenant

```
┌────────────────────────────────────────────────────────────┐
│                                                            │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐      │
│  │ Prometheus  │  │ Prometheus  │  │ Prometheus  │      │
│  │ (Tier 0)   │  │ (Tier 1)   │  │ (Tier 2)   │      │
│  │ Enterprise  │  │ Pro tenants │  │ Free tenants│      │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘      │
│         │                 │                 │             │
│         ▼                 ▼                 ▼             │
│  ┌──────────────────────────────────────────────────┐    │
│  │           Thanos Querier (Global View)            │    │
│  │   Provides unified query across all tenants       │    │
│  └──────────────────────────────────────────────────┘    │
│         │                                                │
│         ▼                                                │
│  ┌──────────────────────────────────────────────────┐    │
│  │           Thanos Store (Object Storage)           │    │
│  │   Long-term retention with compaction             │    │
│  └──────────────────────────────────────────────────┘    │
└────────────────────────────────────────────────────────────┘
```

---

## Production Code Examples

### 1. Per-Tenant SLA Checker (Airflow Sensor)

```python
"""
Airflow sensor that checks data freshness SLA per tenant.
Blocks downstream DAGs until SLA is met or breached.
"""

from airflow.sensors.base import BaseSensorOperator
from airflow.utils.decorators import apply_defaults
from datetime import datetime, timedelta
from typing import Dict, List
import snowflake.connector
import json


class TenantFreshnessSensor(BaseSensorOperator):
    """Monitors data freshness for all tenants, alerts on SLA breach."""

    SLA_THRESHOLDS = {
        'enterprise': timedelta(minutes=5),
        'pro': timedelta(minutes=15),
        'free': timedelta(hours=1),
    }

    @apply_defaults
    def __init__(self, snowflake_conn_id: str, **kwargs):
        super().__init__(**kwargs)
        self.snowflake_conn_id = snowflake_conn_id

    def poke(self, context) -> bool:
        """Check freshness for all tenants."""
        conn = self._get_snowflake_connection()
        cur = conn.cursor()

        cur.execute("""
            SELECT
                t.tenant_id,
                t.tier,
                DATEDIFF('second', MAX(e.event_timestamp), CURRENT_TIMESTAMP()) AS stale_seconds,
                COUNT(*) AS recent_events
            FROM tenant_registry t
            LEFT JOIN raw_events e
                ON t.tenant_id = e.tenant_id
                AND e._ingested_at > DATEADD('hour', -2, CURRENT_TIMESTAMP())
            WHERE t.status = 'active'
            GROUP BY t.tenant_id, t.tier
        """)

        breaches = []
        for row in cur.fetchall():
            tenant_id, tier, stale_seconds, event_count = row
            threshold = self.SLA_THRESHOLDS.get(tier, timedelta(hours=1))

            if stale_seconds and stale_seconds > threshold.total_seconds():
                breaches.append({
                    'tenant_id': tenant_id,
                    'tier': tier,
                    'stale_seconds': stale_seconds,
                    'threshold_seconds': threshold.total_seconds(),
                    'breach_factor': stale_seconds / threshold.total_seconds()
                })

        if breaches:
            self._handle_breaches(breaches, context)
            # Sort by severity (enterprise first, highest breach factor)
            breaches.sort(key=lambda x: (-{'enterprise': 3, 'pro': 2, 'free': 1}[x['tier']],
                                          -x['breach_factor']))
            self.log.error(f"SLA breaches: {len(breaches)} tenants")
            for b in breaches[:10]:
                self.log.error(
                    f"  {b['tenant_id']} ({b['tier']}): "
                    f"{b['stale_seconds']}s stale (threshold: {b['threshold_seconds']}s)"
                )

        cur.close()
        conn.close()

        # Sensor succeeds if no enterprise breaches
        enterprise_breaches = [b for b in breaches if b['tier'] == 'enterprise']
        return len(enterprise_breaches) == 0

    def _handle_breaches(self, breaches: List[Dict], context):
        """Route alerts based on tier severity."""
        from airflow.providers.slack.hooks.slack import SlackHook

        enterprise_breaches = [b for b in breaches if b['tier'] == 'enterprise']
        if enterprise_breaches:
            # Page on-call for enterprise SLA breach
            self._page_oncall(enterprise_breaches)

        # Log all breaches to SLA tracking table
        self._record_breaches(breaches)

    def _page_oncall(self, breaches):
        """Send PagerDuty alert for enterprise SLA breach."""
        import requests
        requests.post("https://events.pagerduty.com/v2/enqueue", json={
            "routing_key": "YOUR_PD_KEY",
            "event_action": "trigger",
            "payload": {
                "summary": f"Enterprise SLA breach: {len(breaches)} tenants",
                "severity": "critical",
                "source": "tenant-sla-monitor",
                "custom_details": {"breaches": breaches[:5]}
            }
        })

    def _record_breaches(self, breaches):
        """Write breach records for SLA reporting."""
        pass  # Insert into sla_breach_log table

    def _get_snowflake_connection(self):
        from airflow.hooks.base import BaseHook
        conn = BaseHook.get_connection(self.snowflake_conn_id)
        return snowflake.connector.connect(
            account=conn.extra_dejson['account'],
            user=conn.login,
            password=conn.password,
            warehouse=conn.extra_dejson.get('warehouse', 'MONITORING_WH'),
            database=conn.schema
        )
```

### 2. Noisy Neighbor Detector

```python
#!/usr/bin/env python3
"""
Noisy Neighbor Detector - Identifies tenants consuming disproportionate
shared resources and triggers throttling or isolation.
"""

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from prometheus_client import start_http_server, Gauge, Counter
import requests


NOISE_SCORE = Gauge(
    'tenant_noise_score',
    'Noisy neighbor score (0=fair, >2=noisy)',
    ['tenant_id', 'tier', 'resource']
)

THROTTLE_EVENTS = Counter(
    'tenant_throttle_total',
    'Number of times tenant was throttled',
    ['tenant_id', 'tier', 'reason']
)

ISOLATION_EVENTS = Counter(
    'tenant_isolation_total',
    'Number of times tenant was isolated to dedicated resources',
    ['tenant_id', 'tier']
)


@dataclass
class TenantResourceUsage:
    tenant_id: str
    tier: str
    cpu_seconds: float = 0
    memory_gb_seconds: float = 0
    io_bytes: int = 0
    event_count: int = 0
    active_jobs: int = 0


@dataclass
class ResourceBudget:
    """Per-tier resource budget (fair share)."""
    cpu_seconds_per_hour: float
    memory_gb_peak: float
    io_bytes_per_hour: int
    events_per_hour: int


TIER_BUDGETS = {
    'enterprise': ResourceBudget(
        cpu_seconds_per_hour=3600,  # 1 full core-hour
        memory_gb_peak=32,
        io_bytes_per_hour=100 * 1024**3,  # 100GB
        events_per_hour=50_000_000
    ),
    'pro': ResourceBudget(
        cpu_seconds_per_hour=900,
        memory_gb_peak=8,
        io_bytes_per_hour=25 * 1024**3,
        events_per_hour=10_000_000
    ),
    'free': ResourceBudget(
        cpu_seconds_per_hour=120,
        memory_gb_peak=2,
        io_bytes_per_hour=5 * 1024**3,
        events_per_hour=500_000
    ),
}


class NoisyNeighborDetector:
    """Detects and mitigates noisy neighbor tenants."""

    THROTTLE_THRESHOLD = 2.0   # Noise score above which we throttle
    ISOLATION_THRESHOLD = 5.0  # Noise score above which we isolate

    def __init__(self, prometheus_url: str, k8s_api_url: str):
        self.prometheus_url = prometheus_url
        self.k8s_api_url = k8s_api_url
        self.tenant_history: Dict[str, List[float]] = {}  # rolling noise scores

    def get_tenant_resource_usage(self, window_minutes: int = 15) -> List[TenantResourceUsage]:
        """Query Prometheus for per-tenant resource usage."""
        usages = []

        # CPU usage per tenant
        cpu_query = f'sum(rate(container_cpu_usage_seconds_total{{namespace=~"tenant-.*"}}[{window_minutes}m])) by (namespace)'
        cpu_results = self._query_prometheus(cpu_query)

        # Memory per tenant
        mem_query = f'max(container_memory_working_set_bytes{{namespace=~"tenant-.*"}}) by (namespace)'
        mem_results = self._query_prometheus(mem_query)

        # Build usage map
        usage_map: Dict[str, TenantResourceUsage] = {}
        for result in cpu_results:
            namespace = result['metric']['namespace']
            tenant_id = namespace.replace('tenant-', '')
            usage_map[tenant_id] = TenantResourceUsage(
                tenant_id=tenant_id,
                tier=self._get_tenant_tier(tenant_id),
                cpu_seconds=float(result['value'][1]) * window_minutes * 60
            )

        for result in mem_results:
            namespace = result['metric']['namespace']
            tenant_id = namespace.replace('tenant-', '')
            if tenant_id in usage_map:
                usage_map[tenant_id].memory_gb_seconds = float(result['value'][1]) / (1024**3)

        return list(usage_map.values())

    def calculate_noise_scores(self, usages: List[TenantResourceUsage]) -> Dict[str, float]:
        """Calculate noise score for each tenant."""
        scores = {}

        for usage in usages:
            budget = TIER_BUDGETS.get(usage.tier, TIER_BUDGETS['free'])

            # Calculate per-resource noise scores
            cpu_score = (usage.cpu_seconds / (budget.cpu_seconds_per_hour / 4)) - 1  # 15min window
            mem_score = (usage.memory_gb_seconds / budget.memory_gb_peak) - 1

            # Overall noise score = max of individual scores
            noise_score = max(cpu_score, mem_score, 0)
            scores[usage.tenant_id] = noise_score

            # Export metric
            NOISE_SCORE.labels(
                tenant_id=usage.tenant_id,
                tier=usage.tier,
                resource='overall'
            ).set(noise_score)

            # Track history for trending
            if usage.tenant_id not in self.tenant_history:
                self.tenant_history[usage.tenant_id] = []
            self.tenant_history[usage.tenant_id].append(noise_score)
            # Keep last 24 data points (6 hours at 15min intervals)
            self.tenant_history[usage.tenant_id] = self.tenant_history[usage.tenant_id][-24:]

        return scores

    def enforce_limits(self, scores: Dict[str, float], usages: List[TenantResourceUsage]):
        """Throttle or isolate noisy tenants."""
        usage_map = {u.tenant_id: u for u in usages}

        for tenant_id, score in scores.items():
            usage = usage_map.get(tenant_id)
            if not usage:
                continue

            if score >= self.ISOLATION_THRESHOLD:
                # Persistent high noise — isolate to dedicated node pool
                self._isolate_tenant(tenant_id, usage.tier)
                ISOLATION_EVENTS.labels(
                    tenant_id=tenant_id, tier=usage.tier
                ).inc()

            elif score >= self.THROTTLE_THRESHOLD:
                # Moderate noise — apply rate limiting
                self._throttle_tenant(tenant_id, usage.tier)
                THROTTLE_EVENTS.labels(
                    tenant_id=tenant_id, tier=usage.tier, reason='noise_score'
                ).inc()

    def _throttle_tenant(self, tenant_id: str, tier: str):
        """Apply rate limiting to a tenant's workloads."""
        print(f"THROTTLE: tenant={tenant_id} tier={tier}")
        # In production: Update rate limiter, reduce Kubernetes resource limits,
        # or pause lower-priority jobs for this tenant
        # Example: Patch the tenant's ResourceQuota to reduce limits
        pass

    def _isolate_tenant(self, tenant_id: str, tier: str):
        """Move tenant to dedicated node pool."""
        print(f"ISOLATE: tenant={tenant_id} tier={tier}")
        # In production: Add node affinity to move pods to dedicated nodes,
        # or scale up a dedicated node group for this tenant
        pass

    def _get_tenant_tier(self, tenant_id: str) -> str:
        """Look up tenant tier from registry."""
        # In production: query tenant registry DB or cache
        return 'pro'  # default

    def _query_prometheus(self, query: str) -> list:
        """Execute PromQL query."""
        resp = requests.get(f"{self.prometheus_url}/api/v1/query", params={'query': query})
        return resp.json().get('data', {}).get('result', [])

    def run(self):
        """Main monitoring loop."""
        start_http_server(9092)
        print("Noisy neighbor detector started on :9092")

        while True:
            try:
                usages = self.get_tenant_resource_usage()
                scores = self.calculate_noise_scores(usages)
                self.enforce_limits(scores, usages)

                # Log top noisy tenants
                top_noisy = sorted(scores.items(), key=lambda x: -x[1])[:5]
                for tenant_id, score in top_noisy:
                    if score > 1.0:
                        print(f"  Noisy: {tenant_id} score={score:.2f}")

            except Exception as e:
                print(f"Error in detection cycle: {e}")

            time.sleep(60)  # Check every minute


if __name__ == "__main__":
    detector = NoisyNeighborDetector(
        prometheus_url="http://thanos-querier:9090",
        k8s_api_url="https://kubernetes.default.svc"
    )
    detector.run()
```

### 3. Tenant Health Score Calculator

```python
#!/usr/bin/env python3
"""
Tenant Health Score - Composite metric combining freshness,
error rate, throughput, and resource usage into a single score.
"""

from dataclasses import dataclass
from typing import Dict, Optional
from enum import Enum


class HealthStatus(Enum):
    HEALTHY = "healthy"       # Score >= 0.8
    DEGRADED = "degraded"     # Score 0.5 - 0.8
    UNHEALTHY = "unhealthy"   # Score < 0.5
    CRITICAL = "critical"     # Score < 0.2


@dataclass
class TenantHealthInputs:
    tenant_id: str
    tier: str
    freshness_seconds: float        # Current data staleness
    error_rate: float               # Error rate (0-1)
    throughput_ratio: float         # Actual/expected throughput (0-1+)
    resource_usage_ratio: float     # Actual/quota resource usage (0-1+)
    queue_depth: int                # Pending events in queue
    last_successful_run_age: float  # Seconds since last success


class TenantHealthCalculator:
    """
    Calculates a composite health score (0-1) for each tenant.
    
    Score formula:
      health = w1*freshness_score + w2*error_score + w3*throughput_score + w4*resource_score
    
    Weights vary by tier (enterprise cares more about freshness).
    """

    TIER_WEIGHTS = {
        'enterprise': {'freshness': 0.4, 'errors': 0.3, 'throughput': 0.2, 'resource': 0.1},
        'pro':        {'freshness': 0.3, 'errors': 0.3, 'throughput': 0.2, 'resource': 0.2},
        'free':       {'freshness': 0.2, 'errors': 0.3, 'throughput': 0.2, 'resource': 0.3},
    }

    FRESHNESS_THRESHOLDS = {
        'enterprise': 300,    # 5 min
        'pro': 900,           # 15 min
        'free': 3600,         # 1 hour
    }

    def calculate_health(self, inputs: TenantHealthInputs) -> float:
        """Calculate composite health score (0-1)."""
        weights = self.TIER_WEIGHTS.get(inputs.tier, self.TIER_WEIGHTS['free'])
        threshold = self.FRESHNESS_THRESHOLDS.get(inputs.tier, 3600)

        # Freshness score: 1.0 if within SLA, degrades linearly
        freshness_score = max(0, 1.0 - (inputs.freshness_seconds / (threshold * 2)))

        # Error score: 1.0 if no errors, 0.0 if > 5% error rate
        error_score = max(0, 1.0 - (inputs.error_rate / 0.05))

        # Throughput score: 1.0 if at expected level, drops if below
        throughput_score = min(1.0, inputs.throughput_ratio)

        # Resource score: 1.0 if under quota, degrades if over
        resource_score = max(0, 1.0 - max(0, inputs.resource_usage_ratio - 0.8) / 0.4)

        # Weighted composite
        health = (
            weights['freshness'] * freshness_score +
            weights['errors'] * error_score +
            weights['throughput'] * throughput_score +
            weights['resource'] * resource_score
        )

        return round(max(0, min(1, health)), 3)

    def get_status(self, score: float) -> HealthStatus:
        """Map score to health status."""
        if score >= 0.8:
            return HealthStatus.HEALTHY
        elif score >= 0.5:
            return HealthStatus.DEGRADED
        elif score >= 0.2:
            return HealthStatus.UNHEALTHY
        return HealthStatus.CRITICAL

    def calculate_fleet_health(self, all_inputs: list) -> Dict:
        """Calculate fleet-wide health summary."""
        scores = {}
        status_counts = {s: 0 for s in HealthStatus}

        for inputs in all_inputs:
            score = self.calculate_health(inputs)
            status = self.get_status(score)
            scores[inputs.tenant_id] = {'score': score, 'status': status}
            status_counts[status] += 1

        total = len(all_inputs)
        return {
            'total_tenants': total,
            'healthy_pct': status_counts[HealthStatus.HEALTHY] / max(total, 1) * 100,
            'degraded_pct': status_counts[HealthStatus.DEGRADED] / max(total, 1) * 100,
            'unhealthy_pct': status_counts[HealthStatus.UNHEALTHY] / max(total, 1) * 100,
            'critical_pct': status_counts[HealthStatus.CRITICAL] / max(total, 1) * 100,
            'scores': scores
        }
```

### 4. SLA Breach Notification System

```python
#!/usr/bin/env python3
"""
SLA Breach Notification - Routes alerts based on tier, breach duration,
and escalation policy. Tracks SLA compliance for reporting.
"""

import time
from datetime import datetime, timedelta
from typing import Dict, List
from dataclasses import dataclass
import requests
import json


@dataclass
class SLABreach:
    tenant_id: str
    tier: str
    metric: str  # freshness, error_rate, throughput
    current_value: float
    threshold: float
    breach_start: datetime
    breach_duration_minutes: float = 0
    acknowledged: bool = False
    resolved: bool = False


class SLABreachNotifier:
    """Manages SLA breach lifecycle: detection → notification → escalation → resolution."""

    ESCALATION_POLICY = {
        'enterprise': [
            (0, 'slack', '#data-platform-alerts'),
            (5, 'pagerduty', 'data-oncall'),
            (15, 'pagerduty', 'engineering-manager'),
            (30, 'pagerduty', 'vp-engineering'),
        ],
        'pro': [
            (0, 'slack', '#data-platform-alerts'),
            (30, 'pagerduty', 'data-oncall'),
            (60, 'email', 'data-team@company.com'),
        ],
        'free': [
            (0, 'slack', '#data-platform-low-priority'),
            (120, 'email', 'data-team@company.com'),
        ],
    }

    def __init__(self):
        self.active_breaches: Dict[str, SLABreach] = {}
        self.breach_history: List[SLABreach] = []
        self.last_escalation: Dict[str, int] = {}  # breach_key -> escalation_level

    def report_breach(self, breach: SLABreach):
        """Report a new or ongoing SLA breach."""
        key = f"{breach.tenant_id}:{breach.metric}"

        if key in self.active_breaches:
            # Update existing breach
            existing = self.active_breaches[key]
            existing.current_value = breach.current_value
            existing.breach_duration_minutes = (
                datetime.utcnow() - existing.breach_start
            ).total_seconds() / 60
            self._check_escalation(existing)
        else:
            # New breach
            breach.breach_start = datetime.utcnow()
            self.active_breaches[key] = breach
            self.last_escalation[key] = -1
            self._notify(breach, level=0)

    def resolve_breach(self, tenant_id: str, metric: str):
        """Mark a breach as resolved."""
        key = f"{tenant_id}:{metric}"
        if key in self.active_breaches:
            breach = self.active_breaches.pop(key)
            breach.resolved = True
            breach.breach_duration_minutes = (
                datetime.utcnow() - breach.breach_start
            ).total_seconds() / 60
            self.breach_history.append(breach)
            self._notify_resolution(breach)
            del self.last_escalation[key]

    def _check_escalation(self, breach: SLABreach):
        """Check if we need to escalate."""
        key = f"{breach.tenant_id}:{breach.metric}"
        policy = self.ESCALATION_POLICY.get(breach.tier, self.ESCALATION_POLICY['free'])
        current_level = self.last_escalation.get(key, -1)

        for level, (minutes_threshold, channel, target) in enumerate(policy):
            if level > current_level and breach.breach_duration_minutes >= minutes_threshold:
                self._notify(breach, level=level)
                self.last_escalation[key] = level

    def _notify(self, breach: SLABreach, level: int):
        """Send notification via appropriate channel."""
        policy = self.ESCALATION_POLICY.get(breach.tier, self.ESCALATION_POLICY['free'])
        if level >= len(policy):
            return

        _, channel, target = policy[level]
        message = (
            f"SLA BREACH [{breach.tier.upper()}] Tenant: {breach.tenant_id}\n"
            f"Metric: {breach.metric} = {breach.current_value:.2f} "
            f"(threshold: {breach.threshold:.2f})\n"
            f"Duration: {breach.breach_duration_minutes:.0f} min\n"
            f"Escalation level: {level}"
        )

        if channel == 'slack':
            self._send_slack(target, message)
        elif channel == 'pagerduty':
            self._send_pagerduty(target, breach)
        elif channel == 'email':
            self._send_email(target, message)

    def _notify_resolution(self, breach: SLABreach):
        """Notify that a breach has been resolved."""
        message = (
            f"RESOLVED: SLA breach for tenant {breach.tenant_id}\n"
            f"Metric: {breach.metric}\n"
            f"Total breach duration: {breach.breach_duration_minutes:.0f} min"
        )
        self._send_slack('#data-platform-alerts', message)

    def get_sla_compliance_report(self, period_days: int = 30) -> Dict:
        """Generate SLA compliance report for billing/reporting."""
        cutoff = datetime.utcnow() - timedelta(days=period_days)
        recent = [b for b in self.breach_history if b.breach_start > cutoff]

        by_tenant = {}
        for breach in recent:
            if breach.tenant_id not in by_tenant:
                by_tenant[breach.tenant_id] = {
                    'tier': breach.tier,
                    'total_breach_minutes': 0,
                    'breach_count': 0
                }
            by_tenant[breach.tenant_id]['total_breach_minutes'] += breach.breach_duration_minutes
            by_tenant[breach.tenant_id]['breach_count'] += 1

        # Calculate SLA compliance percentage
        total_minutes = period_days * 24 * 60
        for tenant_id, data in by_tenant.items():
            data['compliance_pct'] = (
                (total_minutes - data['total_breach_minutes']) / total_minutes * 100
            )
            data['sla_met'] = data['compliance_pct'] >= 99.9 if data['tier'] == 'enterprise' else True

        return by_tenant

    def _send_slack(self, channel: str, message: str):
        print(f"[Slack → {channel}] {message}")

    def _send_pagerduty(self, service: str, breach: SLABreach):
        print(f"[PagerDuty → {service}] {breach.tenant_id}: {breach.metric}")

    def _send_email(self, to: str, message: str):
        print(f"[Email → {to}] {message[:100]}...")
```

---

## Dashboard Design

### Per-Tenant View

```
┌─────────────────────────────────────────────────────────────────┐
│  TENANT DASHBOARD: acme-corp (Enterprise)          Health: 0.92 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Freshness: 2m 30s ████████████████████░░░  SLA: 5m    ✓      │
│  Error Rate: 0.02% ████████████████████████  SLA: <1%   ✓      │
│  Throughput: 98%   ████████████████████░░░░  Expected   ✓      │
│  Storage:   45GB   ████████████░░░░░░░░░░░  Quota:100GB ✓      │
│                                                                 │
│  ┌───────── Event Volume (last 24h) ─────────┐                 │
│  │    ▄▄                                      │                 │
│  │   ████▄       ▄▄▄                         │                 │
│  │  ██████▄    ▄█████▄      ▄                │                 │
│  │ ████████████████████████████▄              │                 │
│  │ ██████████████████████████████             │                 │
│  └────────────────────────────────────────────┘                 │
│  Recent Alerts: None                                            │
│  Last Breach: 12 days ago (duration: 3 min)                    │
└─────────────────────────────────────────────────────────────────┘
```

### Fleet-Wide SLA Heatmap

```
┌──────────────────────────────────────────────────────────────────┐
│  FLEET SLA COMPLIANCE HEATMAP                                     │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Enterprise (52 tenants):                                        │
│  ■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■□□□         │
│  (96% meeting SLA)                          ■=OK □=Breach        │
│                                                                  │
│  Pro (480 tenants):                                              │
│  ■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■□          │
│  (98% meeting SLA)                                               │
│                                                                  │
│  Free (4500 tenants):                                            │
│  ■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■□□□□□□           │
│  (89% meeting SLA — expected for free tier)                      │
│                                                                  │
│  TOP OFFENDERS:                                                  │
│  1. tenant-xyz (enterprise) — 12min stale [INVESTIGATING]       │
│  2. tenant-abc (pro) — high error rate 2.3% [KNOWN ISSUE]      │
│  3. tenant-def (pro) — queue backed up [AUTO-SCALING]           │
└──────────────────────────────────────────────────────────────────┘
```

---

## Alert Rules

```yaml
groups:
  - name: tenant_sla
    rules:
      - alert: EnterpriseTenantSLABreach
        expr: |
          tenant_data_freshness_seconds{tier="enterprise"} > 300
        for: 2m
        labels:
          severity: critical
          tier: enterprise
        annotations:
          summary: "Enterprise tenant {{ $labels.tenant_id }} SLA breach"
          description: "Freshness: {{ $value }}s (SLA: 300s)"

      - alert: NoisyNeighborDetected
        expr: |
          tenant_noise_score > 3.0
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Noisy neighbor: {{ $labels.tenant_id }} (score: {{ $value }})"

      - alert: TenantQuotaExhausted
        expr: |
          tenant_resource_usage_ratio > 0.95
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Tenant {{ $labels.tenant_id }} at 95% quota"

      - alert: FleetHealthDegraded
        expr: |
          (count(tenant_health_score < 0.5) / count(tenant_health_score)) > 0.05
        for: 10m
        labels:
          severity: critical
        annotations:
          summary: "More than 5% of tenants unhealthy"
```

---

## Technologies Summary

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Compute isolation | Kubernetes namespaces | Per-tenant resource quotas |
| Scheduling | Airflow pools / Celery priorities | Fair workload distribution |
| Metrics | Prometheus + Thanos/Mimir | High-cardinality multi-tenant metrics |
| Dashboards | Grafana (template variables) | Per-tenant and fleet views |
| Queue management | Kafka (priority topics) | Tiered ingestion |
| SLA tracking | Custom (PostgreSQL) | Breach history and compliance |
| Alerting | PagerDuty + Slack | Tiered escalation |

---

## Key Takeaways

1. **Per-tenant SLA monitoring is non-negotiable** for paid multi-tenant platforms
2. **Noisy neighbor detection** prevents one tenant from degrading the entire fleet
3. **Metric cardinality** is the #1 challenge — solve it early with hierarchical aggregation
4. **Health scores** provide a single number for fleet-wide visibility
5. **Escalation policies must vary by tier** — enterprise gets paged, free gets batched
6. **SLA compliance reports** are required for enterprise contracts and billing credits
