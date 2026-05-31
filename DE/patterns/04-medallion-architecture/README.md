# Pattern 04: Medallion Architecture (Bronze / Silver / Gold)

## Why Medallion? The Core Insight

```
THE PROBLEM:
═══════════
Raw data is messy, incomplete, and schema-unstable.
Business users need clean, reliable, performant data.
You can't serve both needs with one table.

THE SOLUTION:
═════════════
Layer data progressively, from raw → clean → business-ready.
Each layer serves a different audience and SLA.

Bronze: "Never lose raw data" (engineers)
Silver: "Clean, validated, deduplicated" (analysts, ML)
Gold:   "Business metrics, pre-aggregated" (executives, dashboards)

KEY INSIGHT:
You can always REBUILD downstream from upstream.
Gold is wrong? Rebuild from Silver.
Silver corrupted? Rebuild from Bronze.
Bronze is your SINGLE SOURCE OF TRUTH.
```

## Architecture Deep Dive

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  MEDALLION ARCHITECTURE                                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  SOURCES                 BRONZE              SILVER              GOLD        │
│  ───────                 ──────              ──────              ────        │
│                                                                              │
│  ┌──────────┐    ┌────────────────┐   ┌────────────────┐   ┌───────────┐  │
│  │ Kafka    │───▶│ Raw events     │──▶│ Deduplicated   │──▶│ Revenue   │  │
│  │ Topics   │    │ Append-only    │   │ Schema-valid   │   │ per day   │  │
│  └──────────┘    │ No transforms  │   │ Typed columns  │   │           │  │
│                  │ Original schema│   │ Business keys  │   │ Customer  │  │
│  ┌──────────┐   │ + metadata:    │   │ Null handling  │   │ LTV       │  │
│  │ APIs     │──▶│   _ingested_at │   │ Referential    │   │           │  │
│  │ (REST)   │   │   _source_file │   │  integrity     │   │ Funnel    │  │
│  └──────────┘   │   _batch_id    │   │ SCD handling   │   │ metrics   │  │
│                  │                │   │ Conforming     │   │           │  │
│  ┌──────────┐   │ FORMAT:        │   │                │   │ FORMAT:   │  │
│  │ Database │──▶│ Parquet/Delta  │   │ FORMAT:        │   │ Delta/    │  │
│  │ CDC      │   │ Partitioned by │   │ Delta Lake     │   │ Iceberg   │  │
│  └──────────┘   │ ingestion_date │   │ Partitioned by │   │ Optimized │  │
│                  │                │   │ business key   │   │ for query │  │
│  ┌──────────┐   │ RETENTION:     │   │                │   │ patterns  │  │
│  │ Files    │──▶│ Forever        │   │ RETENTION:     │   │           │  │
│  │ (S3/GCS) │   │ (cheapest tier)│   │ 2-5 years      │   │ RETENTION:│  │
│  └──────────┘   │                │   │ (standard tier)│   │ 1-2 years │  │
│                  └────────────────┘   └────────────────┘   └───────────┘  │
│                                                                              │
│  WHO READS:       Data Engineers       Analysts, ML         Executives,     │
│                   (debugging)          (exploration)        Dashboards      │
│                                                                              │
│  QUERY LATENCY:   Seconds-minutes      Sub-second-seconds  Milliseconds    │
│                   (raw scan)           (indexed)            (pre-computed)  │
│                                                                              │
│  DATA QUALITY:    None guaranteed       Schema + null +     Business rules  │
│                                         dedup + freshness   + reconciled    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Layer-by-Layer Design

### Bronze Layer: Raw Ingestion

```
DESIGN PRINCIPLES:
══════════════════
1. APPEND-ONLY: Never update or delete raw data
2. SCHEMA-ON-READ: Store as-is, don't enforce schema at write time
3. METADATA ENRICHMENT: Add ingestion metadata (timestamp, source, batch_id)
4. IDEMPOTENT WRITES: Re-running ingestion doesn't create duplicates
5. PARTITION BY TIME: Always partition by ingestion date (not business date)

WHY PARTITION BY INGESTION DATE (not event date)?
  - You don't know if event_date is correct in raw data
  - Ingestion date is the one thing YOU control
  - Makes it easy to "replay last 3 days of ingestion" if pipeline breaks
  - Late-arriving data still lands in correct ingestion partition

ANTI-PATTERN: Transforming in Bronze
  DON'T: Parse JSON, cast types, filter nulls in Bronze
  WHY: If your parsing logic has a bug, you lose the original data
  DO: Keep original payload + add metadata columns
```

### Silver Layer: Conformed & Validated

```
DESIGN PRINCIPLES:
══════════════════
1. SCHEMA ENFORCEMENT: Strict types, not-null constraints
2. DEDUPLICATION: Business-key based (not row-based)
3. CONFORMING: Standardize field names, units, timezones
4. SLOWLY CHANGING DIMENSIONS: Track history of entity changes
5. REFERENTIAL INTEGRITY: Foreign keys resolve (orders.customer_id → customers.id)
6. PARTITION BY BUSINESS KEY: date, region, customer segment

DEDUPLICATION STRATEGY:
  -- Bronze may have duplicates (at-least-once delivery)
  -- Silver deduplicates using:
  
  SELECT *,
    ROW_NUMBER() OVER (
      PARTITION BY event_id          -- business key
      ORDER BY _ingested_at DESC     -- latest wins
    ) as rn
  FROM bronze.events
  WHERE rn = 1;

MERGE PATTERN (Delta Lake):
  MERGE INTO silver.customers AS target
  USING (
    SELECT * FROM bronze.customers_cdc
    WHERE _ingested_at > last_processed_timestamp()
  ) AS source
  ON target.customer_id = source.customer_id
  WHEN MATCHED AND source.op = 'UPDATE' THEN
    UPDATE SET *
  WHEN MATCHED AND source.op = 'DELETE' THEN
    DELETE
  WHEN NOT MATCHED AND source.op IN ('INSERT', 'READ') THEN
    INSERT *;
```

### Gold Layer: Business-Ready Aggregates

```
DESIGN PRINCIPLES:
══════════════════
1. BUSINESS DEFINITIONS: "Revenue" means exactly one thing here
2. PRE-AGGREGATED: Don't make dashboards compute on the fly
3. DENORMALIZED: Star schema or wide tables for fast queries
4. SLA-BOUND: Gold must refresh within X minutes of Silver
5. VERSIONED: Track when definitions change (audit trail)

EXAMPLES:
  gold.daily_revenue:        SUM(order_amount) GROUP BY date, region
  gold.customer_ltv:         Lifetime value per customer (rolling calc)
  gold.product_funnel:       View → Cart → Purchase conversion rates
  gold.churn_predictions:    ML model output joined with customer data

WHO BUILDS GOLD?
  - Data team builds the metrics layer
  - Business defines the LOGIC ("revenue = gross - refunds - tax")
  - Data team implements it as a certified dataset
  - Self-serve: Analysts can create "platinum" views on top of gold

SERVING PATTERN:
  Gold → Materialized View in Postgres/Redshift → Dashboard
  Gold → Cube (Apache Pinot / ClickHouse) → Real-time dashboard
  Gold → Feature Store → ML models
```

## When Each Layer Fails

```
┌──────────────┬─────────────────────────────────┬───────────────────────────┐
│ FAILURE      │ IMPACT                           │ RECOVERY                   │
├──────────────┼─────────────────────────────────┼───────────────────────────┤
│ Bronze       │ Data loss (can't rebuild)        │ Re-ingest from source      │
│ ingestion    │ Downstream stale                 │ (if source retains data)   │
│ fails        │                                  │ Kafka: replay from offset  │
├──────────────┼─────────────────────────────────┼───────────────────────────┤
│ Silver       │ Gold is stale                    │ Re-process from Bronze     │
│ transform    │ Analysts see old data            │ (Bronze is immutable)      │
│ fails        │ ML models use stale features     │ Fix bug, backfill          │
├──────────────┼─────────────────────────────────┼───────────────────────────┤
│ Gold         │ Dashboards stale                 │ Re-aggregate from Silver   │
│ aggregation  │ Execs see old numbers            │ (Silver is source of       │
│ fails        │                                  │ truth for Gold)            │
├──────────────┼─────────────────────────────────┼───────────────────────────┤
│ Schema       │ Bronze writes fail OR            │ Schema evolution:          │
│ change in    │ Silver transform fails           │ Bronze: accept new schema  │
│ source       │                                  │ Silver: add migration job  │
├──────────────┼─────────────────────────────────┼───────────────────────────┤
│ Late data    │ Silver/Gold numbers change       │ Watermark strategy:        │
│ arrives      │ retroactively                    │ Allow T+2 day corrections  │
│              │                                  │ in Silver, propagate Gold  │
├──────────────┼─────────────────────────────────┼───────────────────────────┤
│ Duplicate    │ Inflated metrics in Gold         │ Dedup in Bronze→Silver    │
│ events       │                                  │ transition (idempotent)    │
└──────────────┴─────────────────────────────────┴───────────────────────────┘
```

## Scalability Sizing

```
COST MODEL (AWS, 1 TB/day ingestion):
═════════════════════════════════════

Bronze (S3 Standard-IA):
  Storage: 1 TB/day × 365 days × $0.0125/GB = $4,562/year
  Writes: 1 TB/day ÷ 128 MB per file = 8,000 PUTs/day × $0.005/1000 = $14.60/year
  Total Bronze: ~$4,600/year

Silver (S3 Standard):
  Storage: 0.7 TB/day × 90 days × $0.023/GB = $1,449/year  
  (30% compression from dedup + filtering)
  Compute (Spark): 10 × r5.2xlarge × 4 hr/day × $0.504/hr = $7,358/year
  Total Silver: ~$8,800/year

Gold (S3 + Redshift):
  Storage: 0.1 TB/day × 30 days × $0.023/GB = $69/year
  Compute (Redshift): 2 × ra3.xlplus reserved = $4,234/year
  Total Gold: ~$4,300/year

TOTAL: ~$17,700/year for 1 TB/day pipeline
  (Compare: Snowflake equivalent ≈ $30,000-50,000/year)

SCALING TO 10 TB/day:
  Bronze: Linear (storage cost)
  Silver: Sub-linear (larger Spark cluster, but better parallelism)
  Gold: Constant (aggregates don't grow with raw volume)
  Estimated: ~$120,000/year
```

## Runnable Implementation

```python
"""
Medallion Architecture - Complete Pipeline Simulation
=====================================================
Demonstrates Bronze → Silver → Gold with:
- Schema enforcement at Silver
- Deduplication
- Late data handling
- Aggregation to Gold
- Data quality checks at each layer
"""

import json
import hashlib
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from collections import defaultdict
import random


# ============================================================================
# BRONZE LAYER: Raw Ingestion (append-only, no transforms)
# ============================================================================

class BronzeLayer:
    """
    Simulates landing zone for raw data.
    Rules:
      - Never transform data
      - Always append (never update/delete)
      - Add ingestion metadata
      - Partition by ingestion date
    """
    
    def __init__(self):
        self.partitions: Dict[str, List[Dict]] = defaultdict(list)  # date → records
        self.total_records = 0
        self.total_bytes = 0
    
    def ingest(self, raw_records: List[Dict], source: str, batch_id: str) -> int:
        """Ingest raw records with metadata enrichment."""
        ingestion_time = datetime.utcnow()
        partition_key = ingestion_time.strftime("%Y-%m-%d")
        
        count = 0
        for record in raw_records:
            # Add metadata (the ONLY transformation in Bronze)
            enriched = {
                "_raw_payload": json.dumps(record),  # Preserve original
                "_ingested_at": ingestion_time.isoformat(),
                "_source": source,
                "_batch_id": batch_id,
                "_partition": partition_key,
            }
            self.partitions[partition_key].append(enriched)
            count += 1
            self.total_bytes += len(json.dumps(enriched))
        
        self.total_records += count
        print(f"  [BRONZE] Ingested {count} records into partition={partition_key} "
              f"from source={source}")
        return count
    
    def get_records_since(self, since_date: str) -> List[Dict]:
        """Read records from Bronze for Silver processing."""
        results = []
        for partition_date, records in sorted(self.partitions.items()):
            if partition_date >= since_date:
                results.extend(records)
        return results


# ============================================================================
# SILVER LAYER: Cleaned, Validated, Deduplicated
# ============================================================================

@dataclass
class SilverRecord:
    """Strongly typed record after validation."""
    order_id: str
    customer_id: str
    product_id: str
    amount: float
    currency: str
    order_date: str  # ISO format
    status: str
    _processed_at: str = ""
    _source_batch: str = ""
    _version: int = 1


class SilverLayer:
    """
    Simulates conformed/validated layer.
    Rules:
      - Enforce schema (reject invalid records)
      - Deduplicate by business key
      - Standardize formats (dates, currencies, etc.)
      - Track data quality metrics
    """
    
    VALID_STATUSES = {"pending", "confirmed", "shipped", "delivered", "cancelled"}
    VALID_CURRENCIES = {"USD", "EUR", "GBP", "JPY", "INR"}
    
    def __init__(self):
        self.records: Dict[str, SilverRecord] = {}  # order_id → record
        self.rejected: List[Dict] = []  # DLQ for failed validation
        self.quality_metrics = {
            "total_processed": 0,
            "accepted": 0,
            "rejected_schema": 0,
            "rejected_business_rule": 0,
            "deduplicated": 0,
            "late_arrivals": 0,
        }
    
    def process_from_bronze(self, bronze_records: List[Dict]) -> Dict[str, int]:
        """Transform Bronze → Silver with validation and dedup."""
        stats = {"accepted": 0, "rejected": 0, "deduplicated": 0, "updated": 0}
        
        for bronze_record in bronze_records:
            self.quality_metrics["total_processed"] += 1
            
            # Step 1: Parse raw payload
            try:
                raw = json.loads(bronze_record["_raw_payload"])
            except (json.JSONDecodeError, KeyError):
                self._reject(bronze_record, "PARSE_ERROR", "Cannot parse raw payload")
                stats["rejected"] += 1
                continue
            
            # Step 2: Schema validation
            validation_error = self._validate_schema(raw)
            if validation_error:
                self._reject(bronze_record, "SCHEMA_ERROR", validation_error)
                stats["rejected"] += 1
                continue
            
            # Step 3: Business rule validation
            biz_error = self._validate_business_rules(raw)
            if biz_error:
                self._reject(bronze_record, "BUSINESS_RULE_ERROR", biz_error)
                stats["rejected"] += 1
                continue
            
            # Step 4: Conform/Standardize
            conformed = self._conform(raw, bronze_record)
            
            # Step 5: Deduplication (latest version wins)
            if conformed.order_id in self.records:
                existing = self.records[conformed.order_id]
                if conformed._version > existing._version:
                    self.records[conformed.order_id] = conformed
                    stats["updated"] += 1
                else:
                    stats["deduplicated"] += 1
                    self.quality_metrics["deduplicated"] += 1
            else:
                self.records[conformed.order_id] = conformed
                stats["accepted"] += 1
                self.quality_metrics["accepted"] += 1
        
        print(f"  [SILVER] Processed {len(bronze_records)} records: "
              f"accepted={stats['accepted']}, updated={stats['updated']}, "
              f"rejected={stats['rejected']}, deduped={stats['deduplicated']}")
        return stats
    
    def _validate_schema(self, raw: Dict) -> Optional[str]:
        """Check required fields and types."""
        required = ["order_id", "customer_id", "product_id", "amount", "order_date", "status"]
        for field_name in required:
            if field_name not in raw:
                return f"Missing required field: {field_name}"
        
        # Type checks
        try:
            float(raw["amount"])
        except (ValueError, TypeError):
            return f"Invalid amount: {raw.get('amount')}"
        
        if raw.get("status", "").lower() not in self.VALID_STATUSES:
            return f"Invalid status: {raw.get('status')}"
        
        return None
    
    def _validate_business_rules(self, raw: Dict) -> Optional[str]:
        """Domain-specific validation."""
        amount = float(raw["amount"])
        if amount < 0:
            return f"Negative order amount: {amount}"
        if amount > 1_000_000:
            return f"Suspiciously large order: {amount}"
        return None
    
    def _conform(self, raw: Dict, bronze_record: Dict) -> SilverRecord:
        """Standardize formats."""
        return SilverRecord(
            order_id=str(raw["order_id"]).strip(),
            customer_id=str(raw["customer_id"]).strip(),
            product_id=str(raw["product_id"]).strip(),
            amount=round(float(raw["amount"]), 2),
            currency=raw.get("currency", "USD").upper(),
            order_date=raw["order_date"],  # Would normalize timezone here
            status=raw["status"].lower(),
            _processed_at=datetime.utcnow().isoformat(),
            _source_batch=bronze_record.get("_batch_id", "unknown"),
            _version=int(raw.get("_version", 1)),
        )
    
    def _reject(self, record: Dict, error_type: str, message: str):
        """Send to Dead Letter Queue."""
        self.rejected.append({
            "record": record,
            "error_type": error_type,
            "error_message": message,
            "rejected_at": datetime.utcnow().isoformat(),
        })
        if "SCHEMA" in error_type:
            self.quality_metrics["rejected_schema"] += 1
        else:
            self.quality_metrics["rejected_business_rule"] += 1


# ============================================================================
# GOLD LAYER: Business Aggregates
# ============================================================================

class GoldLayer:
    """
    Simulates business-ready aggregation layer.
    Rules:
      - Pre-compute metrics (don't let dashboards do GROUP BY)
      - Use business definitions (revenue = confirmed orders only)
      - Denormalize for query speed
      - Track metric lineage (which Silver tables feed this)
    """
    
    def __init__(self):
        self.daily_revenue: Dict[str, Dict] = {}  # date → {revenue, orders, avg}
        self.customer_metrics: Dict[str, Dict] = {}  # customer_id → {ltv, orders, ...}
        self.product_metrics: Dict[str, Dict] = {}  # product_id → {revenue, volume}
        self.last_refresh: Optional[str] = None
    
    def refresh_from_silver(self, silver: SilverLayer):
        """Rebuild Gold aggregates from Silver."""
        # Reset
        daily = defaultdict(lambda: {"revenue": 0.0, "order_count": 0, "amounts": []})
        customers = defaultdict(lambda: {"ltv": 0.0, "order_count": 0, "first_order": None, "last_order": None})
        products = defaultdict(lambda: {"revenue": 0.0, "units_sold": 0})
        
        for record in silver.records.values():
            # Business rule: Only CONFIRMED+ orders count as revenue
            if record.status in ("confirmed", "shipped", "delivered"):
                date_key = record.order_date[:10]  # YYYY-MM-DD
                
                # Daily revenue
                daily[date_key]["revenue"] += record.amount
                daily[date_key]["order_count"] += 1
                daily[date_key]["amounts"].append(record.amount)
                
                # Customer LTV
                customers[record.customer_id]["ltv"] += record.amount
                customers[record.customer_id]["order_count"] += 1
                if (customers[record.customer_id]["first_order"] is None or 
                    record.order_date < customers[record.customer_id]["first_order"]):
                    customers[record.customer_id]["first_order"] = record.order_date
                customers[record.customer_id]["last_order"] = record.order_date
                
                # Product metrics
                products[record.product_id]["revenue"] += record.amount
                products[record.product_id]["units_sold"] += 1
        
        # Finalize daily metrics
        for date_key, metrics in daily.items():
            metrics["avg_order_value"] = (
                metrics["revenue"] / metrics["order_count"] if metrics["order_count"] > 0 else 0
            )
            del metrics["amounts"]  # Don't store raw list in gold
            self.daily_revenue[date_key] = dict(metrics)
        
        self.customer_metrics = dict(customers)
        self.product_metrics = dict(products)
        self.last_refresh = datetime.utcnow().isoformat()
        
        print(f"  [GOLD] Refreshed: {len(self.daily_revenue)} days, "
              f"{len(self.customer_metrics)} customers, "
              f"{len(self.product_metrics)} products")


# ============================================================================
# PIPELINE ORCHESTRATION
# ============================================================================

def generate_sample_orders(count: int, include_bad_data: bool = True) -> List[Dict]:
    """Generate realistic order data with some quality issues."""
    orders = []
    products = [f"PROD-{i:03d}" for i in range(1, 20)]
    statuses = ["pending", "confirmed", "shipped", "delivered", "cancelled"]
    
    for i in range(count):
        order_date = datetime(2024, 1, 1) + timedelta(days=random.randint(0, 30))
        
        order = {
            "order_id": f"ORD-{i:06d}",
            "customer_id": f"CUST-{random.randint(1, 100):04d}",
            "product_id": random.choice(products),
            "amount": round(random.uniform(10, 500), 2),
            "currency": random.choice(["USD", "EUR", "GBP"]),
            "order_date": order_date.strftime("%Y-%m-%dT%H:%M:%S"),
            "status": random.choice(statuses),
            "_version": 1,
        }
        orders.append(order)
    
    if include_bad_data:
        # Add some intentionally bad records
        orders.append({"order_id": "BAD-001", "amount": "not_a_number"})  # Schema error
        orders.append({  # Business rule violation
            "order_id": "BAD-002", "customer_id": "C1", "product_id": "P1",
            "amount": -50, "order_date": "2024-01-15", "status": "confirmed"
        })
        orders.append({  # Missing fields
            "order_id": "BAD-003"
        })
        # Duplicate (same order_id, different version)
        orders.append({
            "order_id": "ORD-000001", "customer_id": "CUST-0001",
            "product_id": "PROD-001", "amount": 999.99, "currency": "USD",
            "order_date": "2024-01-20T10:00:00", "status": "delivered",
            "_version": 2,  # Newer version
        })
    
    return orders


def run_medallion_pipeline():
    """Execute full Bronze → Silver → Gold pipeline."""
    print("=" * 70)
    print("MEDALLION ARCHITECTURE - FULL PIPELINE DEMO")
    print("=" * 70)
    
    # Initialize layers
    bronze = BronzeLayer()
    silver = SilverLayer()
    gold = GoldLayer()
    
    # ─── PHASE 1: Ingest to Bronze ───
    print("\n╔══ PHASE 1: BRONZE INGESTION ══╗")
    
    # Batch 1: API source
    batch1_orders = generate_sample_orders(50, include_bad_data=True)
    bronze.ingest(batch1_orders, source="orders-api", batch_id="batch-001")
    
    # Batch 2: CDC source (simulating database replication)
    batch2_orders = generate_sample_orders(30, include_bad_data=False)
    bronze.ingest(batch2_orders, source="orders-cdc", batch_id="batch-002")
    
    # Batch 3: Late-arriving data (older events arriving now)
    batch3_orders = generate_sample_orders(20, include_bad_data=False)
    bronze.ingest(batch3_orders, source="orders-api", batch_id="batch-003-late")
    
    print(f"\n  Bronze Stats: {bronze.total_records} total records, "
          f"{bronze.total_bytes / 1024:.1f} KB")
    
    # ─── PHASE 2: Bronze → Silver ───
    print("\n╔══ PHASE 2: SILVER TRANSFORMATION ══╗")
    
    all_bronze = bronze.get_records_since("2024-01-01")
    stats = silver.process_from_bronze(all_bronze)
    
    print(f"\n  Silver Stats:")
    print(f"    Valid records: {len(silver.records)}")
    print(f"    Rejected (DLQ): {len(silver.rejected)}")
    print(f"    Quality metrics: {json.dumps(silver.quality_metrics, indent=6)}")
    
    # ─── PHASE 3: Silver → Gold ───
    print("\n╔══ PHASE 3: GOLD AGGREGATION ══╗")
    
    gold.refresh_from_silver(silver)
    
    print(f"\n  Gold - Daily Revenue (sample):")
    for date_key in sorted(list(gold.daily_revenue.keys())[:5]):
        metrics = gold.daily_revenue[date_key]
        print(f"    {date_key}: ${metrics['revenue']:,.2f} "
              f"({metrics['order_count']} orders, "
              f"avg ${metrics['avg_order_value']:,.2f})")
    
    print(f"\n  Gold - Top 5 Customers by LTV:")
    top_customers = sorted(
        gold.customer_metrics.items(),
        key=lambda x: x[1]["ltv"],
        reverse=True
    )[:5]
    for cust_id, metrics in top_customers:
        print(f"    {cust_id}: LTV=${metrics['ltv']:,.2f} "
              f"({metrics['order_count']} orders)")
    
    # ─── PHASE 4: Data Quality Report ───
    print("\n╔══ PHASE 4: DATA QUALITY REPORT ══╗")
    total = silver.quality_metrics["total_processed"]
    accepted = silver.quality_metrics["accepted"]
    print(f"  Acceptance rate: {accepted/total*100:.1f}%")
    print(f"  Schema errors: {silver.quality_metrics['rejected_schema']}")
    print(f"  Business rule errors: {silver.quality_metrics['rejected_business_rule']}")
    print(f"  Duplicates removed: {silver.quality_metrics['deduplicated']}")
    
    # Show rejected records (DLQ)
    if silver.rejected:
        print(f"\n  Dead Letter Queue ({len(silver.rejected)} records):")
        for rej in silver.rejected[:3]:
            print(f"    [{rej['error_type']}] {rej['error_message']}")
    
    print("\n" + "=" * 70)
    print("PIPELINE COMPLETE")
    print("=" * 70)
    print(f"""
ARCHITECTURE SUMMARY:
  Bronze: {bronze.total_records} raw records (immutable, append-only)
  Silver: {len(silver.records)} validated records (deduplicated, typed)
  Gold:   {len(gold.daily_revenue)} daily aggregates, {len(gold.customer_metrics)} customer metrics
  
  Data Loss: 0 records (bad data in DLQ, not lost)
  Rebuild Capability: Gold can be rebuilt from Silver in seconds
                      Silver can be rebuilt from Bronze in minutes
""")


if __name__ == "__main__":
    random.seed(42)
    run_medallion_pipeline()
```

## Anti-Patterns

```
❌ ANTI-PATTERN 1: "Everything in Gold"
  Skipping Silver, going Bronze → Gold directly.
  Problem: No intermediate layer to debug.
  When Gold is wrong, you can't tell if it's the transform or the data.

❌ ANTI-PATTERN 2: "Silver is just Bronze with types"
  Not deduplicating, not validating business rules.
  Problem: Gold metrics are inflated by duplicates.

❌ ANTI-PATTERN 3: "Gold as a data lake"
  Storing raw granular data in Gold.
  Problem: Dashboards scan millions of rows → slow.
  Gold should be PRE-AGGREGATED for its consumers.

❌ ANTI-PATTERN 4: "Mutable Bronze"
  Updating/deleting raw data.
  Problem: Lost ability to rebuild downstream layers.
  Exception: GDPR deletion (but use soft-delete + crypto-shredding).

❌ ANTI-PATTERN 5: "One giant Silver table"
  All entities in one table.
  Problem: Schema changes affect everything, no isolation.
  DO: One Silver table per entity (orders, customers, products).

✅ CORRECT PATTERN: "Thin Bronze, Rich Silver, Focused Gold"
  Bronze: Raw + metadata only
  Silver: Full business logic (dedup, conform, validate, SCD)
  Gold: Only what consumers actually need (aggregates, features)
```

## Technology Choices

```
┌─────────────────┬───────────────────────────────────────────────────────────┐
│ LAYER           │ RECOMMENDED STACK                                          │
├─────────────────┼───────────────────────────────────────────────────────────┤
│ Bronze Storage  │ Delta Lake on S3/ADLS (ACID, time travel, schema evolution)│
│                 │ OR Apache Iceberg (better for multi-engine)                 │
│                 │ Partition: ingestion_date                                   │
│                 │ Format: Parquet (columnar, compressed)                      │
├─────────────────┼───────────────────────────────────────────────────────────┤
│ Bronze → Silver │ Spark Structured Streaming (micro-batch, exactly-once)     │
│ Engine          │ OR dbt + Spark (SQL-first, testable)                        │
│                 │ OR Flink (if sub-second latency needed)                     │
├─────────────────┼───────────────────────────────────────────────────────────┤
│ Silver Storage  │ Delta Lake / Iceberg (MERGE support critical)              │
│                 │ Partition: business_date + region                           │
│                 │ Z-ORDER: customer_id, product_id                            │
├─────────────────┼───────────────────────────────────────────────────────────┤
│ Silver → Gold   │ dbt (SQL transforms, tested, documented)                   │
│ Engine          │ OR Spark (for complex aggregations)                         │
│                 │ Schedule: Airflow / Dagster                                 │
├─────────────────┼───────────────────────────────────────────────────────────┤
│ Gold Storage    │ Delta Lake / Iceberg (for data lake queries)                │
│                 │ + Materialized to: ClickHouse, Pinot, or Redshift          │
│                 │   (for dashboard serving)                                   │
├─────────────────┼───────────────────────────────────────────────────────────┤
│ Orchestration   │ Airflow (mature) or Dagster (modern, asset-based)          │
│                 │ DAG: Bronze → Silver → Gold (with quality gates)            │
├─────────────────┼───────────────────────────────────────────────────────────┤
│ Quality Gates   │ Great Expectations / Soda / dbt tests                      │
│                 │ Between each layer transition                               │
│                 │ Block promotion if quality fails                            │
└─────────────────┴───────────────────────────────────────────────────────────┘
```
