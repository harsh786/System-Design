# Problem 5: E-Commerce Inventory Sync (Amazon-Scale)

## The Problem

You run an e-commerce platform with **350M+ products** across 20+ warehouses selling on 50+ marketplace channels (Amazon, Shopify, eBay, Walmart, etc.). Inventory must be synced every 15 minutes to prevent overselling — if a customer buys the last unit on Shopify but eBay still shows it in stock, you get cancelled orders, refunds, and seller reputation damage.

Each sync cycle involves:
1. Query warehouse databases for current stock levels
2. Calculate available inventory (physical stock - reserved - in-transit)
3. Push updated quantities to each marketplace channel's API

Constraints:
- **API rate limits vary wildly**: Shopify (40 req/s), eBay (5000 calls/day), Amazon SP-API (burst of 20 then 10/s)
- **Internal database is shared** with order processing — cannot saturate connection pool
- **Failure on one channel cannot block others** — eBay being down shouldn't delay Shopify sync
- **Must complete within 15 minutes** or the next cycle starts before the current one finishes

## Scale Numbers

| Resource | Limit |
|----------|-------|
| Products | 350M |
| Warehouses | 20+ |
| Marketplace channels | 50+ |
| Sync frequency | Every 15 min |
| API rate limits | 5–5000 req/s depending on channel |
| Database max connections | 100 concurrent (shared with OLTP) |
| Allocated DB connections for sync | 10 max |
| Network bandwidth to APIs | 500 Mbps |

## Architecture Diagram (ASCII)

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Airflow Scheduler                             │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │  inventory_sync_dag (every 15 min)                            │  │
│  │  ├── detect_changed_products (query CDC/changelog)            │  │
│  │  ├── partition_by_channel (fan-out to 50+ channels)           │  │
│  │  │   ├── sync_shopify [pool: shopify_api, slots: 3]          │  │
│  │  │   ├── sync_ebay [pool: ebay_api, slots: 1]                │  │
│  │  │   ├── sync_amazon [pool: amazon_api, slots: 2]            │  │
│  │  │   └── ... (50 channels, each with own pool)               │  │
│  │  └── reconciliation_report                                    │  │
│  └───────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
         │                    │                      │
         ▼                    ▼                      ▼
┌─────────────────┐  ┌──────────────┐      ┌──────────────────┐
│ Warehouse DB    │  │ Redis Cache  │      │ Marketplace APIs │
│ [pool: wh_db]  │  │ (stock cache)│      │ (rate-limited)   │
│ max 10 conn    │  │              │      │                  │
└─────────────────┘  └──────────────┘      └──────────────────┘

Pool Configuration:
┌────────────────────────────────────────┐
│ warehouse_db_pool:    10 slots         │
│ shopify_api_pool:     3 slots          │
│ ebay_api_pool:        1 slot           │
│ amazon_api_pool:      2 slots          │
│ walmart_api_pool:     5 slots          │
│ default_pool:         128 slots        │
└────────────────────────────────────────┘
```

## Airflow Concepts Taught

### 1. Pools (Resource Management)

Pools are Airflow's mechanism for **limiting parallelism to protect shared resources**. Without pools, if you launch 50 channel-sync tasks that each need 3 DB connections, you'd attempt 150 connections on a database that only allows 100.

**How pools work:**
- A pool has a name and a fixed number of **slots**
- Each task occupies one or more slots while running
- If no slots are available, the task waits in a queue (state: `queued` but not `running`)
- Tasks are dequeued by `priority_weight` (higher = runs first)

**Creating pools:**

```bash
# CLI
airflow pools set warehouse_db_pool 10 "Limits concurrent warehouse DB queries"
airflow pools set shopify_api_pool 3 "Shopify: max 40 req/s, 3 concurrent tasks is safe"
airflow pools set ebay_api_pool 1 "eBay: 5000 calls/day, serialize access"
airflow pools set amazon_api_pool 2 "Amazon SP-API burst handling"
```

```python
# Programmatic (in DAG or migration script)
from airflow.models import Pool
from airflow.utils.session import create_session

with create_session() as session:
    pools = [
        Pool(pool="warehouse_db_pool", slots=10, description="Warehouse DB connections"),
        Pool(pool="shopify_api_pool", slots=3, description="Shopify API concurrency"),
        Pool(pool="ebay_api_pool", slots=1, description="eBay API - serialize"),
    ]
    for pool in pools:
        existing = session.query(Pool).filter(Pool.pool == pool.pool).first()
        if not existing:
            session.add(pool)
```

**Using pools in tasks:**

```python
sync_to_shopify = PythonOperator(
    task_id="sync_shopify_batch_1",
    python_callable=sync_inventory,
    pool="shopify_api_pool",       # Which pool to draw from
    pool_slots=1,                   # How many slots this task consumes
    priority_weight=10,             # Higher priority = gets slot first
)
```

**Multiple pools per task** — a task can only belong to one pool. If you need to limit both DB and API access, the pattern is to split into two tasks (read DB → push API) each with their own pool.

### 2. Connections & Hooks

**Connection model** — every external system Airflow talks to is represented as a Connection:

```
conn_id:    "warehouse_db_us_east"
conn_type:  "postgres"
host:       "warehouse-replica.internal.com"
schema:     "inventory"
login:      "airflow_readonly"
password:   "***"
port:       5432
extra:      {"sslmode": "require", "connect_timeout": 10}
```

**Secrets Backend** — in production, never store credentials in Airflow's metadata DB:

```python
# airflow.cfg or env variable
[secrets]
backend = airflow.providers.amazon.aws.secrets.secrets_manager.SecretsManagerBackend
backend_kwargs = {"connections_prefix": "airflow/connections", "sep": "/"}
```

This means `conn_id="warehouse_db_us_east"` resolves to AWS Secrets Manager key `airflow/connections/warehouse_db_us_east` containing:

```json
{
  "conn_type": "postgres",
  "host": "warehouse-replica.internal.com",
  "schema": "inventory",
  "login": "airflow_readonly",
  "password": "actual-secret-here",
  "port": 5432,
  "extra": "{\"sslmode\": \"require\"}"
}
```

### 3. Hooks Deep Dive

Hooks are the **reusable connection wrappers** that handle opening, using, and closing connections. They are the building blocks that Operators use internally.

**Built-in hooks:**

```python
from airflow.providers.postgres.hooks.postgres import PostgresHook

hook = PostgresHook(postgres_conn_id="warehouse_db_us_east")
records = hook.get_records("SELECT sku, qty FROM stock WHERE updated_at > %s", [last_sync])
```

**Custom hook for marketplace APIs with rate limiting:**

```python
from airflow.hooks.base import BaseHook
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type
import time
import threading


class MarketplaceHook(BaseHook):
    """Base hook for marketplace APIs with built-in rate limiting."""

    conn_name_attr = "marketplace_conn_id"
    default_conn_name = "marketplace_default"
    conn_type = "http"
    hook_name = "Marketplace"

    def __init__(self, marketplace_conn_id: str, rate_limit_rps: float, **kwargs):
        super().__init__()
        self.marketplace_conn_id = marketplace_conn_id
        self.rate_limit_rps = rate_limit_rps
        self._min_interval = 1.0 / rate_limit_rps
        self._last_request_time = 0.0
        self._lock = threading.Lock()
        self._session = None

    def get_conn(self):
        """Get connection details and create HTTP session."""
        if self._session is None:
            import requests
            conn = self.get_connection(self.marketplace_conn_id)
            self._session = requests.Session()
            self._session.headers.update({
                "Authorization": f"Bearer {conn.password}",
                "Content-Type": "application/json",
            })
            self._base_url = f"https://{conn.host}"
        return self._session

    def _throttle(self):
        """Enforce rate limit using token bucket."""
        with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_request_time
            if elapsed < self._min_interval:
                time.sleep(self._min_interval - elapsed)
            self._last_request_time = time.monotonic()

    @retry(
        retry=retry_if_exception_type((ConnectionError, TimeoutError)),
        wait=wait_exponential(multiplier=1, min=2, max=60),
        stop=stop_after_attempt(5),
    )
    def _request(self, method: str, endpoint: str, **kwargs):
        """Make a rate-limited request with retry logic."""
        self._throttle()
        session = self.get_conn()
        response = session.request(method, f"{self._base_url}{endpoint}", timeout=30, **kwargs)

        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", 60))
            self.log.warning(f"Rate limited. Sleeping {retry_after}s")
            time.sleep(retry_after)
            raise ConnectionError("Rate limited — will retry")

        if response.status_code >= 500:
            raise ConnectionError(f"Server error: {response.status_code}")

        response.raise_for_status()
        return response.json()

    def update_inventory(self, sku: str, quantity: int, warehouse_id: str):
        """Update inventory for a single SKU."""
        return self._request("PUT", f"/inventory/{sku}", json={
            "quantity": quantity,
            "warehouse_id": warehouse_id,
            "updated_at": time.time(),
        })

    def bulk_update_inventory(self, updates: list[dict], batch_size: int = 100):
        """Update inventory in batches respecting rate limits."""
        results = {"success": 0, "failed": 0, "errors": []}
        for i in range(0, len(updates), batch_size):
            batch = updates[i:i + batch_size]
            try:
                self._request("POST", "/inventory/bulk", json={"items": batch})
                results["success"] += len(batch)
            except Exception as e:
                results["failed"] += len(batch)
                results["errors"].append({"batch_start": i, "error": str(e)})
                self.log.error(f"Batch {i} failed: {e}")
        return results


class ShopifyHook(MarketplaceHook):
    """Shopify-specific hook: 40 req/s limit, uses GraphQL bulk operations."""

    def __init__(self, conn_id: str = "shopify_default"):
        super().__init__(marketplace_conn_id=conn_id, rate_limit_rps=35)  # 35 to leave headroom

    def bulk_update_inventory(self, updates: list[dict], **kwargs):
        """Shopify supports bulk mutations via GraphQL."""
        mutation = """
        mutation inventorySetQuantities($input: InventorySetQuantitiesInput!) {
            inventorySetQuantities(input: $input) {
                inventoryAdjustmentGroup { reason }
                userErrors { field message }
            }
        }
        """
        # Shopify allows 100 items per bulk mutation
        for i in range(0, len(updates), 100):
            batch = updates[i:i + 100]
            variables = {
                "input": {
                    "name": "available",
                    "reason": "correction",
                    "quantities": [
                        {"inventoryItemId": u["sku"], "locationId": u["location"], "quantity": u["qty"]}
                        for u in batch
                    ]
                }
            }
            self._request("POST", "/admin/api/2024-01/graphql.json", json={
                "query": mutation, "variables": variables
            })


class EbayHook(MarketplaceHook):
    """eBay-specific hook: 5000 calls/day = ~3.5/min average."""

    def __init__(self, conn_id: str = "ebay_default"):
        # Very conservative: 5000/day means ~0.058 req/s sustained
        super().__init__(marketplace_conn_id=conn_id, rate_limit_rps=0.05)
```

**Hook vs Operator — when to use which:**
- Use a **Hook** when you need fine-grained control, reuse across operators, or custom retry logic
- Use an **Operator** when the action maps cleanly to a single task (transfer, run query, trigger)
- In this system, hooks are preferred because rate limiting logic is shared across many tasks

### 4. Rate Limiting Patterns

**Pattern 1: Pool-based rate limiting**

The simplest approach — pool slots cap how many tasks hit an API simultaneously:

```python
# If each task makes ~10 req/s and Shopify allows 40 req/s:
# 3 pool slots × 10 req/s = 30 req/s (safe under 40 limit)
Pool(pool="shopify_api_pool", slots=3)
```

**Pattern 2: In-task token bucket (shown in MarketplaceHook above)**

For fine-grained control within a single task making many sequential calls.

**Pattern 3: Circuit breaker pattern**

```python
import time
from dataclasses import dataclass, field
from airflow.models import Variable


@dataclass
class CircuitBreaker:
    """Circuit breaker for marketplace APIs stored in Airflow Variables."""
    channel: str
    failure_threshold: int = 5
    recovery_timeout: int = 300  # 5 minutes

    @property
    def _var_key(self):
        return f"circuit_breaker_{self.channel}"

    def _get_state(self) -> dict:
        import json
        raw = Variable.get(self._var_key, default_var='{"state":"closed","failures":0,"last_failure":0}')
        return json.loads(raw)

    def _set_state(self, state: dict):
        import json
        Variable.set(self._var_key, json.dumps(state))

    def is_open(self) -> bool:
        state = self._get_state()
        if state["state"] == "open":
            if time.time() - state["last_failure"] > self.recovery_timeout:
                # Transition to half-open: allow one request through
                state["state"] = "half-open"
                self._set_state(state)
                return False
            return True
        return False

    def record_success(self):
        self._set_state({"state": "closed", "failures": 0, "last_failure": 0})

    def record_failure(self):
        state = self._get_state()
        state["failures"] += 1
        state["last_failure"] = time.time()
        if state["failures"] >= self.failure_threshold:
            state["state"] = "open"
        self._set_state(state)
```

**Pattern 4: Backpressure via pool resizing**

```python
def check_api_health_and_resize_pool(**context):
    """Dynamically resize pool based on API health."""
    from airflow.models import Pool
    from airflow.utils.session import create_session

    response_times = context["ti"].xcom_pull(task_ids="measure_api_latency")
    avg_latency = sum(response_times) / len(response_times)

    with create_session() as session:
        pool = session.query(Pool).filter(Pool.pool == "shopify_api_pool").first()
        if avg_latency > 2.0:  # API is stressed
            pool.slots = max(1, pool.slots - 1)
        elif avg_latency < 0.5:  # API is healthy
            pool.slots = min(5, pool.slots + 1)
        session.commit()
```

### 5. Resource-Aware Scheduling

Combining pools, priority weights, and queues for intelligent scheduling:

```python
# High-priority products (low stock, high velocity) sync first
sync_critical_skus = PythonOperator(
    task_id="sync_critical_skus",
    pool="shopify_api_pool",
    priority_weight=100,          # Runs before low-priority tasks
    queue="high_memory_workers",  # Route to beefy workers
    weight_rule="absolute",       # Don't inherit from downstream
)

# Bulk catalog sync is low priority
sync_long_tail = PythonOperator(
    task_id="sync_long_tail_products",
    pool="shopify_api_pool",
    priority_weight=1,            # Runs only when critical is done
    queue="default",
)
```

## Production Implementation

```python
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.models import Variable
from airflow.utils.task_group import TaskGroup
import json


CHANNELS = ["shopify", "ebay", "amazon", "walmart", "etsy"]
BATCH_SIZE = 10000
PRIORITY_MAP = {"shopify": 50, "amazon": 40, "walmart": 30, "ebay": 20, "etsy": 10}


default_args = {
    "owner": "inventory-team",
    "retries": 2,
    "retry_delay": timedelta(minutes=1),
    "retry_exponential_backoff": True,
    "execution_timeout": timedelta(minutes=12),  # Must finish before next 15-min cycle
    "on_failure_callback": alert_on_failure,
}


def detect_changed_products(**context):
    """Query CDC changelog for products changed since last sync."""
    from airflow.providers.postgres.hooks.postgres import PostgresHook

    hook = PostgresHook(postgres_conn_id="warehouse_db_replica")
    last_sync = Variable.get("last_inventory_sync_ts", default_var="1970-01-01T00:00:00")

    # Query uses CDC (Change Data Capture) table — not scanning 350M rows
    changed = hook.get_records("""
        SELECT sku, warehouse_id, quantity_available, quantity_reserved
        FROM inventory_changelog
        WHERE changed_at > %s
        ORDER BY priority_score DESC
        LIMIT 500000
    """, [last_sync])

    # Partition into batches and push to XCom (or S3 for large sets)
    batches = [changed[i:i+BATCH_SIZE] for i in range(0, len(changed), BATCH_SIZE)]

    # For 350M products, don't use XCom — write to S3
    import boto3
    s3 = boto3.client("s3")
    batch_keys = []
    for idx, batch in enumerate(batches):
        key = f"inventory-sync/{context['ds']}/{context['run_id']}/batch_{idx}.json"
        s3.put_object(
            Bucket="inventory-sync-staging",
            Key=key,
            Body=json.dumps(batch),
        )
        batch_keys.append(key)

    Variable.set("last_inventory_sync_ts", datetime.utcnow().isoformat())
    return batch_keys


def sync_channel(channel: str, **context):
    """Sync inventory to a specific marketplace channel."""
    import boto3

    # Circuit breaker check
    cb = CircuitBreaker(channel=channel)
    if cb.is_open():
        context["ti"].log.warning(f"Circuit breaker OPEN for {channel}. Skipping.")
        return {"status": "skipped", "reason": "circuit_breaker_open"}

    # Get the appropriate hook
    hook_map = {
        "shopify": ShopifyHook,
        "ebay": EbayHook,
        "amazon": lambda: MarketplaceHook("amazon_sp_api", rate_limit_rps=10),
        "walmart": lambda: MarketplaceHook("walmart_api", rate_limit_rps=20),
        "etsy": lambda: MarketplaceHook("etsy_api", rate_limit_rps=5),
    }
    hook = hook_map[channel]() if callable(hook_map[channel]) else hook_map[channel]

    # Load batches from S3
    batch_keys = context["ti"].xcom_pull(task_ids="detect_changed_products")
    s3 = boto3.client("s3")

    total_results = {"success": 0, "failed": 0, "errors": []}

    for key in batch_keys:
        obj = s3.get_object(Bucket="inventory-sync-staging", Key=key)
        updates = json.loads(obj["Body"].read())

        # Filter to products listed on this channel
        channel_updates = [u for u in updates if channel in u.get("channels", [])]
        if not channel_updates:
            continue

        try:
            result = hook.bulk_update_inventory(channel_updates)
            total_results["success"] += result["success"]
            total_results["failed"] += result["failed"]
            total_results["errors"].extend(result.get("errors", []))
            cb.record_success()
        except Exception as e:
            cb.record_failure()
            total_results["failed"] += len(channel_updates)
            total_results["errors"].append(str(e))
            if cb.is_open():
                context["ti"].log.error(f"Circuit breaker tripped for {channel}")
                break

    # Push metrics
    from airflow.providers.amazon.aws.hooks.cloudwatch import CloudwatchHook
    cw = CloudwatchHook()
    cw.conn.put_metric_data(
        Namespace="InventorySync",
        MetricData=[
            {"MetricName": "SyncSuccess", "Value": total_results["success"],
             "Dimensions": [{"Name": "Channel", "Value": channel}]},
            {"MetricName": "SyncFailed", "Value": total_results["failed"],
             "Dimensions": [{"Name": "Channel", "Value": channel}]},
        ]
    )
    return total_results


with DAG(
    dag_id="inventory_sync_all_channels",
    schedule_interval="*/15 * * * *",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    max_active_runs=1,              # Never overlap runs
    default_args=default_args,
    tags=["inventory", "critical"],
) as dag:

    detect_changes = PythonOperator(
        task_id="detect_changed_products",
        python_callable=detect_changed_products,
        pool="warehouse_db_pool",
        pool_slots=2,  # Uses 2 connections for parallel reads
        priority_weight=100,
    )

    with TaskGroup("channel_sync") as channel_sync_group:
        for channel in CHANNELS:
            PythonOperator(
                task_id=f"sync_{channel}",
                python_callable=sync_channel,
                op_kwargs={"channel": channel},
                pool=f"{channel}_api_pool",
                pool_slots=1,
                priority_weight=PRIORITY_MAP.get(channel, 10),
                # Each channel is independent — trigger_rule ensures isolation
                trigger_rule="all_done",
            )

    reconciliation = PythonOperator(
        task_id="reconciliation_report",
        python_callable=generate_reconciliation_report,
        trigger_rule="all_done",  # Run even if some channels failed
    )

    detect_changes >> channel_sync_group >> reconciliation
```

## Production Handling

### Marketplace API is down

```python
# The circuit breaker + trigger_rule="all_done" combination means:
# 1. First few failures increment the circuit breaker counter
# 2. After threshold, circuit opens → task returns "skipped" immediately
# 3. Other channels continue unaffected (trigger_rule="all_done" on group)
# 4. After recovery_timeout, circuit goes half-open → next run tries one request
# 5. If it succeeds, circuit closes and normal sync resumes
```

### Rate limit exceeded (HTTP 429)

The `MarketplaceHook._request` method handles this:
1. Reads `Retry-After` header
2. Sleeps for that duration
3. Retries via `tenacity` with exponential backoff
4. If retries exhausted, the task fails → Airflow retries the task (up to `retries=2`)
5. If all retries exhausted, circuit breaker increments

### Database connection exhaustion

```python
# Pool "warehouse_db_pool" has 10 slots. The database has 100 connections total,
# but order processing needs 80+. Our 10 slots guarantee we never exceed our budget.
#
# If connections are still exhausted (other services misbehaving):
# - PostgresHook has connect_timeout=10 in the connection's `extra`
# - Task fails → goes back to pool queue → retries after retry_delay
# - Alert fires so on-call can investigate the connection leak
```

### Partial sync recovery

```python
def sync_channel_with_checkpointing(channel: str, **context):
    """Resume from last checkpoint if previous run partially completed."""
    run_id = context["run_id"]
    checkpoint_key = f"sync_checkpoint_{channel}_{run_id}"

    # Check if we have a checkpoint from a previous attempt
    last_batch_idx = int(Variable.get(checkpoint_key, default_var="0"))

    batch_keys = context["ti"].xcom_pull(task_ids="detect_changed_products")

    for idx, key in enumerate(batch_keys[last_batch_idx:], start=last_batch_idx):
        # ... sync logic ...
        # Save checkpoint after each successful batch
        Variable.set(checkpoint_key, str(idx + 1))

    # Clean up checkpoint on full success
    Variable.delete(checkpoint_key)
```

## Key Takeaways

| Concept | What It Solves | Key Config |
|---------|---------------|------------|
| **Pools** | Prevents resource exhaustion (DB connections, API limits) | `pool=`, `pool_slots=`, `priority_weight=` |
| **Connections** | Centralized credential management with secrets backends | `conn_id`, Secrets Manager backend |
| **Custom Hooks** | Reusable API wrappers with rate limiting and retries | Extend `BaseHook`, implement `get_conn()` |
| **Circuit Breaker** | Fail fast when a downstream is unhealthy | Stored in Variables, checked before API calls |
| **trigger_rule="all_done"** | Failure isolation between parallel branches | Downstream runs regardless of upstream status |
| **max_active_runs=1** | Prevents sync overlap when cycles take > 15 min | DAG-level parameter |
| **Checkpointing** | Resume partial syncs without re-processing | Variable-based batch tracking |

**The mental model**: Pools are your resource budget enforcement. Hooks are your connection wrappers. Circuit breakers are your graceful degradation. Together they let you sync 350M products across 50 APIs without overwhelming anything or letting one failure cascade into a total outage.
