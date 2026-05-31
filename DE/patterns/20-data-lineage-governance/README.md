# Pattern 20: Data Lineage & Governance

## Why Lineage Matters

```
SCENARIO: CEO asks "why is revenue number different on dashboard vs report?"

WITHOUT LINEAGE:
  → Hunt through 500 pipelines to find where revenue is computed
  → Take 3 days to trace the discrepancy
  → Find: Two different definitions of "revenue" (with/without refunds)

WITH LINEAGE:
  → Click on dashboard metric → see lineage graph
  → See: Dashboard uses orders.amount, Report uses orders.net_amount
  → Root cause in 5 minutes
  → Fix: Standardize definition in gold layer

LINEAGE = Understanding how data flows from source to consumption.
```

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  DATA LINEAGE & GOVERNANCE PLATFORM                                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────┐         │
│  │  LINEAGE COLLECTION (OpenLineage Standard)                      │         │
│  │                                                                 │         │
│  │  Every pipeline emits lineage events:                           │         │
│  │  {                                                              │         │
│  │    "run": {"runId": "abc-123"},                                 │         │
│  │    "job": {"name": "etl_orders_daily", "namespace": "prod"},    │         │
│  │    "inputs": [                                                  │         │
│  │      {"name": "raw.orders", "namespace": "bronze"}              │         │
│  │    ],                                                           │         │
│  │    "outputs": [                                                 │         │
│  │      {"name": "clean.orders", "namespace": "silver"}            │         │
│  │    ],                                                           │         │
│  │    "eventType": "COMPLETE",                                     │         │
│  │    "eventTime": "2024-01-15T10:00:00Z"                         │         │
│  │  }                                                              │         │
│  │                                                                 │         │
│  │  Emitters:                                                      │         │
│  │  • Spark: OpenLineage Spark extension (automatic)               │         │
│  │  • Airflow: OpenLineage Airflow provider (automatic)            │         │
│  │  • Flink: Custom lineage reporter                               │         │
│  │  • dbt: Native lineage from model dependencies                  │         │
│  └──────────────────────────┬─────────────────────────────────────┘         │
│                              │                                               │
│  ┌───────────────────────────▼───────────────────────────────────────┐      │
│  │  LINEAGE STORE (Marquez / DataHub / Atlan)                         │      │
│  │                                                                    │      │
│  │  Storage: Graph Database (Neo4j / JanusGraph)                      │      │
│  │                                                                    │      │
│  │  Graph Structure:                                                  │      │
│  │  [Source Table] ──(read_by)──→ [Job] ──(writes_to)──→ [Output]    │      │
│  │                                                                    │      │
│  │  Capabilities:                                                     │      │
│  │  • Upstream lineage: "Where does this data come from?"             │      │
│  │  • Downstream lineage: "What will break if I change this table?"   │      │
│  │  • Column-level lineage: "Which source columns map to this one?"  │      │
│  │  • Run history: "When did this pipeline last succeed?"             │      │
│  │  • Impact analysis: "If source changes schema, who is affected?"  │      │
│  └────────────────────────────────────────────────────────────────────┘     │
│                                                                              │
│  USE CASES:                                                                  │
│  ┌────────────────────────────────────────────────────────────────┐         │
│  │  1. ROOT CAUSE ANALYSIS                                         │         │
│  │     Dashboard wrong → trace upstream → find broken pipeline     │         │
│  │                                                                 │         │
│  │  2. IMPACT ANALYSIS                                             │         │
│  │     Source table schema change → who downstream is affected?    │         │
│  │     Answer in seconds (not days of manual hunting)              │         │
│  │                                                                 │         │
│  │  3. COMPLIANCE (GDPR)                                           │         │
│  │     "Show me all tables that contain user email addresses"      │         │
│  │     → Column-level lineage shows PII propagation                │         │
│  │                                                                 │         │
│  │  4. DATA DISCOVERY                                              │         │
│  │     "I need customer purchase data" → Search catalog            │         │
│  │     → See: quality score, freshness, owner, documentation       │         │
│  │                                                                 │         │
│  │  5. DEPRECATION                                                 │         │
│  │     Want to drop old table? Check downstream lineage first.     │         │
│  │     If nothing reads it → safe to drop.                         │         │
│  │     If 5 dashboards read it → migrate consumers first.          │         │
│  └────────────────────────────────────────────────────────────────┘         │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

