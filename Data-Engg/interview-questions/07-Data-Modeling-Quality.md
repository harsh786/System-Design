# Interview Questions Set 7: Data Modeling, Quality & Governance (Q181-210)

---

## Q181: Design a dimensional model for a subscription SaaS business. What facts and dimensions would you create?

**Answer:**

```
FACT TABLES:
┌────────────────────────────────────────────────────────────────┐
│ fct_subscription_events (Transaction Grain)                     │
│ - event_id, subscription_id, customer_id, plan_id, date_key    │
│ - event_type (CREATED, UPGRADED, DOWNGRADED, CANCELLED, RENEWED)│
│ - mrr_change (monthly recurring revenue impact)                 │
│ - arr_change                                                    │
│                                                                  │
│ fct_subscription_daily (Periodic Snapshot)                       │
│ - subscription_id, date_key, plan_id, status                    │
│ - mrr (current MRR for this subscription on this day)           │
│ - days_since_start, days_until_renewal                          │
│                                                                  │
│ fct_usage_daily (Periodic Snapshot)                              │
│ - customer_id, date_key, feature_id                             │
│ - api_calls, storage_bytes, compute_minutes                     │
│                                                                  │
│ fct_invoice (Transaction Grain)                                  │
│ - invoice_id, customer_id, date_key                             │
│ - amount, tax, discount, total_paid                             │
│ - payment_status (PAID, OVERDUE, FAILED)                        │
└────────────────────────────────────────────────────────────────┘

DIMENSION TABLES:
┌────────────────────┐ ┌──────────────────┐ ┌──────────────────┐
│ dim_customer (SCD2)│ │ dim_plan         │ │ dim_date         │
│ customer_id        │ │ plan_id          │ │ date_key         │
│ company_name       │ │ plan_name        │ │ full_date        │
│ industry           │ │ tier (Free/Pro/  │ │ fiscal_quarter   │
│ segment (SMB/ENT)  │ │   Enterprise)    │ │ is_month_end     │
│ region             │ │ monthly_price    │ │ is_quarter_end   │
│ acquisition_channel│ │ annual_price     │ │                  │
│ valid_from/to      │ │ features_included│ │                  │
│ is_current         │ │ max_seats        │ │                  │
└────────────────────┘ └──────────────────┘ └──────────────────┘

KEY METRICS DERIVABLE:
- MRR/ARR by segment, region, plan
- Net Revenue Retention (NRR) = (Beginning MRR + Expansion - Contraction - Churn) / Beginning MRR
- Churn rate (by cohort, segment)
- LTV/CAC ratio
- Usage-to-billing correlation
```

---

## Q182: Explain the difference between additive, semi-additive, and non-additive measures.

**Answer:**

```
ADDITIVE: Can be summed across ALL dimensions
  Examples: revenue, quantity, cost, discount
  SUM(revenue) across time: ✓ (total for year = sum of months)
  SUM(revenue) across products: ✓ (total = sum across products)
  SUM(revenue) across customers: ✓

SEMI-ADDITIVE: Can be summed across SOME dimensions but not time
  Examples: balance, inventory count, headcount
  SUM(balance) across customers: ✓ (total balance = sum of all accounts)
  SUM(balance) across time: ✗ (Jan balance + Feb balance ≠ anything meaningful)
  Correct for time: Use snapshot (end-of-period) or AVERAGE

NON-ADDITIVE: Cannot be summed across ANY dimension
  Examples: ratio, percentage, unit price, temperature, distinct count
  SUM(profit_margin%) across products: ✗ (must recalculate from underlying)
  SUM(distinct_users) across days: ✗ (users overlap between days)
  Correct: Store underlying components, calculate ratio at query time

  -- Anti-pattern: Storing percentages in fact table
  -- Correct: Store numerator and denominator separately
  -- BAD: conversion_rate = 5.2%
  -- GOOD: conversions = 52, visitors = 1000
  --        conversion_rate = SUM(conversions) / SUM(visitors) → correct rollup
```

---

## Q183: How do you design a data model for a multi-currency financial system?

**Answer:**

```sql
-- Fact table with dual currency amounts
CREATE TABLE fct_transactions (
    transaction_id      BIGINT PRIMARY KEY,
    account_id          BIGINT,
    date_key            INT,
    transaction_type    VARCHAR(20),
    
    -- Original currency
    local_amount        DECIMAL(18,4),
    local_currency_code CHAR(3),
    
    -- Converted to reporting currency (USD)
    reporting_amount    DECIMAL(18,4),    -- Converted at transaction time
    exchange_rate_used  DECIMAL(12,8),    -- Rate at transaction time
    
    -- For balance sheet (period-end rate)
    period_end_amount   DECIMAL(18,4)     -- Re-translated at period end
);

-- Exchange rate dimension (Type 2: historical rates)
CREATE TABLE dim_exchange_rate (
    rate_id             BIGINT PRIMARY KEY,
    from_currency       CHAR(3),
    to_currency         CHAR(3),
    rate_date           DATE,
    spot_rate           DECIMAL(12,8),
    avg_rate            DECIMAL(12,8),    -- Monthly average
    closing_rate        DECIMAL(12,8),    -- End of day
    rate_source         VARCHAR(50)       -- Bloomberg, ECB, etc.
);

-- Design principles:
-- 1. ALWAYS store original local amount (source of truth)
-- 2. Store converted amount at transaction time (for P&L reporting)
-- 3. Keep exchange rate used (audit trail)
-- 4. Re-translate balance sheet items at period-end rates
-- 5. Separate rate table allows re-calculation if rates are corrected

-- Query: Revenue by region in USD
SELECT 
    d.region,
    SUM(f.reporting_amount) as revenue_usd,      -- P&L: historical rates
    SUM(f.local_amount) as revenue_local         -- Original amounts
FROM fct_transactions f
JOIN dim_customer d ON f.customer_id = d.customer_id
WHERE f.date_key BETWEEN 20240101 AND 20240131
GROUP BY d.region;
```

---

## Q184: How do you implement a metrics layer / semantic layer? Compare approaches.

**Answer:**

```yaml
# dbt Semantic Layer (MetricFlow):
semantic_models:
  - name: orders
    defaults:
      agg_time_dimension: order_date
    entities:
      - name: order_id
        type: primary
      - name: customer_id
        type: foreign
    dimensions:
      - name: order_date
        type: time
      - name: status
        type: categorical
    measures:
      - name: order_total
        agg: sum
        expr: amount
      - name: order_count
        agg: count
        expr: order_id

metrics:
  - name: revenue
    type: simple
    type_params:
      measure: order_total
    filter: |
      {{ Dimension('status') }} = 'COMPLETED'
      
  - name: average_order_value
    type: derived
    type_params:
      expr: revenue / order_count
      metrics:
        - name: revenue
        - name: order_count

  - name: revenue_growth_mom
    type: derived
    type_params:
      expr: (current_revenue - prior_revenue) / prior_revenue
      metrics:
        - name: current_revenue
          offset_window: 0
          filter: ...
        - name: prior_revenue
          offset_window: 1 month
```

**Comparison of approaches:**
| Tool | Approach | Strengths |
|------|----------|-----------|
| dbt Semantic Layer | YAML metric definitions | Integrated with dbt, version-controlled |
| Cube.js | Data model + REST/GraphQL API | Pre-aggregation, API-first |
| Looker LookML | Modeling language | Full BI platform, explores |
| Headless BI (GoodData, AtScale) | Virtual layer | Multi-tool serving |

---

## Q185: Explain activity schema vs entity-centric schema. When would you use each?

**Answer:**

```
ENTITY-CENTRIC (Traditional dimensional model):
  One table per entity type, one row per entity
  dim_customer: 1 row per customer (current state)
  fct_orders: 1 row per order event
  
  Pros: Simple queries, clear grain, standard BI tool support
  Cons: Denormalization complexity, SCD management

ACTIVITY SCHEMA (Event-centric):
  Single wide table with ALL activities for an entity
  
  activity_stream:
  ┌─────────────┬──────────┬──────────┬─────────────────────────┐
  │ entity_id   │ activity │ ts       │ attributes (JSON/MAP)   │
  ├─────────────┼──────────┼──────────┼─────────────────────────┤
  │ user_123    │ signup   │ Jan 1    │ {plan: "free"}          │
  │ user_123    │ login    │ Jan 2    │ {device: "mobile"}      │
  │ user_123    │ purchase │ Jan 3    │ {amount: 99, item: "X"} │
  │ user_123    │ upgrade  │ Jan 15   │ {plan: "pro"}           │
  │ user_456    │ signup   │ Jan 5    │ {plan: "pro"}           │
  └─────────────┴──────────┴──────────┴─────────────────────────┘
  
  Pros: 
  - All user behavior in one scan (great for ML features)
  - Flexible schema (attributes as JSON)
  - Easy to add new activity types
  - Natural for event sourcing
  
  Cons:
  - Complex queries for traditional BI (need PIVOT/LATERAL)
  - Schema-on-read (less strict)
  - Hard to enforce data quality on attributes

USE ACTIVITY SCHEMA WHEN:
  - Building ML feature stores
  - User journey analysis
  - Event-driven architecture
  - Rapid schema evolution needed
  
USE ENTITY-CENTRIC WHEN:
  - Traditional BI/reporting
  - Well-defined metrics and KPIs
  - Regulatory reporting (strict schema)
  - Team familiar with dimensional modeling
```

---

## Q186: How do you implement data contracts between teams?

**Answer:**

```
IMPLEMENTATION APPROACH:

1. CONTRACT DEFINITION (Producer-side):
```
```yaml
# contracts/orders-events.yaml
apiVersion: v2
kind: DataContract
metadata:
  name: orders.events.v2
  owner: orders-team@company.com
  domain: commerce
  
schema:
  type: protobuf
  file: protos/orders/v2/order_event.proto
  compatibility: BACKWARD

quality:
  - metric: completeness
    column: order_id
    threshold: 1.0  # 100% non-null
  - metric: freshness
    max_delay_minutes: 15
  - metric: volume
    min_daily: 10000
    max_daily: 5000000

sla:
  availability: 99.9%
  support_hours: "09:00-18:00 PST"
  notification_channel: "#orders-data-alerts"

consumers:
  - team: analytics
    use_case: "Daily revenue reporting"
    contact: analytics-team@company.com
  - team: ml-platform
    use_case: "Recommendation model training"
    contact: ml-team@company.com
```

```
2. ENFORCEMENT IN CI/CD:
   - PR modifies schema → CI validates compatibility against contract
   - Breaking change detected → CI blocks merge
   - Requires consumer acknowledgment for breaking changes

3. RUNTIME ENFORCEMENT:
   - Quality checks run on every data delivery
   - SLA monitoring (freshness, completeness) 
   - Automatic alerts on violation
   - Dashboard showing contract compliance scores

4. TOOLING:
   - Soda: soda-cl for contract checks
   - Schema Registry: Schema compatibility enforcement
   - DataHub: Contract metadata + lineage
   - Custom: dbt tests aligned with contract rules
```

---

## Q187: How do you detect and handle data quality anomalies automatically?

**Answer:**

```python
# Statistical anomaly detection for data quality

import numpy as np
from scipy import stats

class DataQualityAnomalyDetector:
    def __init__(self, lookback_days=30, sensitivity=3.0):
        self.lookback = lookback_days
        self.sensitivity = sensitivity  # Z-score threshold
    
    def detect_volume_anomaly(self, current_count, historical_counts):
        """Detect if today's row count is anomalous."""
        mean = np.mean(historical_counts)
        std = np.std(historical_counts)
        
        if std == 0:
            return False, 0
        
        z_score = (current_count - mean) / std
        is_anomaly = abs(z_score) > self.sensitivity
        
        return is_anomaly, z_score
    
    def detect_null_rate_anomaly(self, current_rate, historical_rates):
        """Detect spike in null rate for a column."""
        # Use IQR method (robust to outliers)
        q1 = np.percentile(historical_rates, 25)
        q3 = np.percentile(historical_rates, 75)
        iqr = q3 - q1
        upper_bound = q3 + 1.5 * iqr
        
        is_anomaly = current_rate > upper_bound
        return is_anomaly, current_rate, upper_bound
    
    def detect_distribution_shift(self, current_dist, reference_dist):
        """Detect distribution change using KL divergence / PSI."""
        # Population Stability Index (PSI)
        psi = 0
        for i in range(len(current_dist)):
            if current_dist[i] == 0:
                current_dist[i] = 0.001
            if reference_dist[i] == 0:
                reference_dist[i] = 0.001
            psi += (current_dist[i] - reference_dist[i]) * \
                   np.log(current_dist[i] / reference_dist[i])
        
        # PSI interpretation:
        # < 0.1: No significant change
        # 0.1 - 0.25: Moderate change (investigate)
        # > 0.25: Significant change (alert!)
        severity = "OK" if psi < 0.1 else "WARN" if psi < 0.25 else "CRITICAL"
        return psi, severity

# Integration with pipeline:
def quality_gate(table_name, df, spark):
    detector = DataQualityAnomalyDetector()
    
    # Get historical metrics
    history = spark.sql(f"""
        SELECT date, row_count, null_rate_customer_id 
        FROM data_quality_metrics 
        WHERE table_name = '{table_name}' 
        AND date > current_date - 30
    """).toPandas()
    
    # Check volume
    current_count = df.count()
    is_anomaly, z_score = detector.detect_volume_anomaly(
        current_count, history["row_count"].values)
    
    if is_anomaly:
        alert(f"Volume anomaly in {table_name}: count={current_count}, z={z_score:.2f}")
        if abs(z_score) > 5:  # Extreme anomaly → block
            raise DataQualityException(f"Extreme volume anomaly: z={z_score}")
```

---

## Q188: How do you implement column-level lineage tracking?

**Answer:**

```
COLUMN-LEVEL LINEAGE:
Shows which source columns feed into which target columns

Example:
  Source: raw.orders (order_id, user_id, amount, tax, created_at)
  Transform: SELECT order_id, user_id, amount + tax AS total, DATE(created_at) AS order_date
  Target: analytics.fct_orders (order_id, user_id, total, order_date)

  Column lineage:
  raw.orders.order_id ──────────────────▶ analytics.fct_orders.order_id
  raw.orders.user_id ───────────────────▶ analytics.fct_orders.user_id
  raw.orders.amount ──┐
                      ├── (+ expression) ▶ analytics.fct_orders.total
  raw.orders.tax ─────┘
  raw.orders.created_at ── (DATE()) ────▶ analytics.fct_orders.order_date

IMPLEMENTATION APPROACHES:

1. SQL PARSING (dbt + OpenLineage):
   - Parse SQL AST to extract column dependencies
   - dbt models → SQL → parsed → lineage graph
   - Tools: sqllineage, sqlglot, OpenLineage

2. RUNTIME TRACKING (Spark / Flink):
   - Intercept query plans (Spark LogicalPlan)
   - Extract column relationships from plan nodes
   - OpenLineage Spark integration (automatic)

3. METADATA PLATFORM (DataHub / OpenMetadata):
   - Ingest lineage from multiple sources
   - Store in graph database
   - API for querying upstream/downstream dependencies
   - UI for visual exploration

USE CASES:
  - Impact analysis: "If I change column X, what breaks?"
  - Root cause: "This metric is wrong. Which upstream source caused it?"
  - Compliance: "Where does PII flow? Who has access?"
  - Documentation: Auto-generated data documentation
```

---

## Q189: Design a data quality framework for a 500-table data warehouse.

**Answer:**

```
┌──────────────────────────────────────────────────────────────────┐
│          DATA QUALITY FRAMEWORK (500 TABLES)                      │
│                                                                    │
│  TIER 1: AUTOMATED (every table, every run)                       │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │ Applied via dbt generic tests + macros:                   │    │
│  │ - Primary key uniqueness + not_null                       │    │
│  │ - Foreign key referential integrity                       │    │
│  │ - Enum/accepted values for categorical columns            │    │
│  │ - Freshness (recency check)                               │    │
│  │ - Row count > 0 (table not empty)                         │    │
│  │                                                           │    │
│  │ Auto-generated from metadata:                             │    │
│  │   for each table in catalog:                              │    │
│  │     add unique test on PK                                 │    │
│  │     add not_null on required columns                      │    │
│  │     add freshness test (based on SLA)                     │    │
│  └──────────────────────────────────────────────────────────┘    │
│                                                                    │
│  TIER 2: STATISTICAL (critical tables, anomaly detection)        │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │ Applied to top 50 business-critical tables:               │    │
│  │ - Volume anomaly detection (Z-score, ±3σ)                 │    │
│  │ - Null rate monitoring (trend + threshold)                │    │
│  │ - Distribution stability (PSI for key columns)            │    │
│  │ - Cross-table reconciliation (source vs target counts)    │    │
│  │ - Value range monitoring (min/max drift)                  │    │
│  └──────────────────────────────────────────────────────────┘    │
│                                                                    │
│  TIER 3: BUSINESS RULES (domain-specific)                        │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │ Custom tests per domain:                                  │    │
│  │ - Revenue tables: Total > 0, matches billing system ±1%  │    │
│  │ - User tables: Active users < total users                 │    │
│  │ - Financial: Credits = Debits (balanced)                  │    │
│  │ - Inventory: Stock >= 0 (no negative inventory)           │    │
│  │ Written by domain data stewards                           │    │
│  └──────────────────────────────────────────────────────────┘    │
│                                                                    │
│  EXECUTION:                                                      │
│  - Tier 1: Run in dbt pipeline (fail on violation)               │
│  - Tier 2: Run post-pipeline (alert, don't block)               │
│  - Tier 3: Run daily (alert domain team)                         │
│                                                                    │
│  SCORING & REPORTING:                                            │
│  - Table-level quality score (weighted dimensions)               │
│  - Domain-level score (average of tables in domain)              │
│  - Trend dashboard (score over time, SLA compliance)             │
│  - Weekly report to data governance council                      │
└──────────────────────────────────────────────────────────────────┘
```

---

## Q190-210: [Data Modeling & Quality - Condensed]

**Q190:** How do you model many-to-many relationships in a star schema?
- Bridge table (factless fact): `bridge_customer_product(customer_id, product_id, weight_factor)`
- Weight factor for proportional allocation of measures

**Q191:** When would you denormalize vs normalize in a data warehouse?
- Denormalize (star schema): BI queries, read performance, simpler joins
- Normalize (3NF/Data Vault): ETL loading, auditability, flexibility
- Modern: Denormalize in Gold layer, normalize in Silver/staging

**Q192:** How do you handle NULL in dimensional models?
- Never allow NULL foreign keys in fact tables
- Use special dimension row: `customer_id = -1, name = 'Unknown'`
- Distinguishes between "Unknown" vs "Not Applicable"

**Q193:** How do you design a data model for event-driven microservices?
- Event store: All events (immutable, append-only)
- Materialized views: Current state derived from events
- Projections: Domain-specific read models (polyglot persistence)

**Q194:** What is a junk dimension? When do you use it?
- Combines low-cardinality flags/indicators into single dimension
- Instead of 5 boolean fact columns → 1 junk dimension key → 32 rows
- Reduces fact table width, improves query flexibility

**Q195:** How do you handle late-arriving dimensions?
- Record arrives before its dimension entry exists
- Solution: Inferred member (create placeholder dim row, update later)
- `dim_customer: {id: 999, name: "Inferred - Awaiting Data", is_inferred: true}`

**Q196:** Design a data model for a ride-sharing platform.
- fct_trips (trip_id, rider_id, driver_id, start_time, end_time, distance, fare, surge_multiplier)
- fct_driver_availability_snapshot (driver_id, timestamp, status, location_geohash)
- dim_rider, dim_driver, dim_location (geospatial hierarchy), dim_vehicle

**Q197:** How do you implement data contracts in dbt?
```yaml
models:
  - name: fct_orders
    config:
      contract:
        enforced: true  # dbt 1.5+ contract enforcement
    columns:
      - name: order_id
        data_type: bigint
        constraints:
          - type: not_null
          - type: primary_key
```

**Q198:** How do you handle data quality in streaming pipelines?
- In-stream validation (Flink): Filter invalid events to DLQ
- Schema validation at ingestion (Schema Registry)
- Post-landing quality checks (batch on micro-batches)
- Real-time quality metrics (null rates, volume per window)

**Q199:** Explain One Big Table (OBT) pattern. When is it appropriate?
- Single denormalized table with ALL dimensions inlined
- No joins at query time → fastest BI performance
- Use when: Simple analytics, small-medium data, BI-focused
- Avoid when: Data changes frequently, many dimensions, complex updates

**Q200:** How do you implement data mesh with existing data warehouse?
- Domain teams own their data products (dbt models per domain)
- Shared platform (Snowflake/BigQuery) with namespace isolation
- Data contracts between domains
- Self-serve infrastructure (templates, automated provisioning)
- Federated governance (global standards + domain autonomy)

**Q201-210: Additional quality & governance questions:**

**Q201:** How do you handle PII detection and classification at scale?
- Automated scanning: Column name patterns, regex on sample data
- ML-based: Train classifier on labeled PII/non-PII columns
- Tools: AWS Macie, Google DLP, Collibra, custom Spark UDFs

**Q202:** Design an access control model for a data platform.
- RBAC + ABAC hybrid: Roles for basic access, attributes for fine-grained
- Data domains own access policies
- Automated provisioning from identity provider (Okta → Data platform)

**Q203:** How do you implement data retention and right-to-delete (GDPR)?
- Tag PII columns in catalog
- Retention policies per dataset (auto-delete after N days)
- Right to delete: Locate all instances of user_id across systems → delete/anonymize
- Iceberg: DELETE WHERE user_id = X (across all partitions)

**Q204:** How do you validate data pipeline migrations?
- Shadow mode: Run old and new pipeline in parallel, compare outputs
- Reconciliation: Row counts, checksum, sample comparison
- A/B testing: Route % of traffic to new pipeline, validate

**Q205:** Explain data profiling. How do you automate it?
- Statistics per column: min, max, mean, null%, distinct%, top values, distribution
- Run on every new dataset load (Great Expectations profiler, dbt-profiler)
- Store results in metadata platform for trend analysis

**Q206:** How do you implement data versioning for ML reproducibility?
- DVC (Data Version Control): Git-like versioning for data files
- Delta Lake/Iceberg time travel: Reference specific snapshot for training
- Feature store versioning: Point-in-time correct feature retrieval

**Q207:** Design a data quality SLA framework.
- Define SLIs (Service Level Indicators): Freshness, completeness, accuracy
- Define SLOs (Objectives): 99.5% completeness, <30min freshness
- Define SLAs (Agreements): With consumers, penalties for breach
- Automated monitoring + alerting on SLO violations

**Q208:** How do you handle conflicting business definitions of the same metric?
- Semantic layer: ONE definition per metric, documented
- Governance council resolves conflicts
- Metric documentation: Formula, assumptions, caveats, owner
- dbt metrics layer as single source of truth

**Q209:** Explain data mesh vs data fabric. How do they differ?
- Data Mesh: Organizational (domain ownership, decentralized)
- Data Fabric: Technical (automated metadata, AI-driven integration)
- Mesh = people + process; Fabric = technology + automation
- Can complement each other (Fabric enables Mesh infrastructure)

**Q210:** How do you measure the ROI of data quality initiatives?
- Reduced time-to-insight (fewer "is this data correct?" questions)
- Reduced incidents (MTTR, incident frequency)
- Trust metrics (survey: "Do you trust the data?")
- Business impact: Decisions made faster, fewer reverted decisions
- Cost: Pipeline reruns avoided, support tickets reduced
