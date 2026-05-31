# Pattern 08: Slowly Changing Dimensions (SCD)

## The Problem

```
SCENARIO:
═════════
Customer "John Smith" moves from NYC to LA on March 15.
You have orders:
  - Order A (Jan 10): shipped to NYC
  - Order B (Apr 20): shipped to LA

QUESTION: When you query "revenue by city", which city gets credit for Order A?
ANSWER DEPENDS ON SCD TYPE:

  Type 1 (Overwrite):  LA gets ALL revenue (history lost)
  Type 2 (History):    NYC gets Jan order, LA gets Apr order (correct!)
  Type 3 (Previous):   Current=LA, Previous=NYC (limited history)
  Type 4 (Mini-dim):   Fast-changing attributes in separate table
  Type 6 (Hybrid):     Current + historical in same row (Type 1+2+3)

WRONG ANSWER = WRONG BUSINESS DECISIONS
  If Type 1: "LA is our top market!" (wrong — NYC was bigger historically)
  If Type 2: "NYC had $X in Q1, LA had $Y in Q2" (correct, auditable)
```

## SCD Types Explained

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  SCD TYPE COMPARISON                                                         │
├─────────┬────────────────────┬──────────────────────┬───────────────────────┤
│ TYPE    │ STRATEGY           │ USE WHEN             │ TRADE-OFF             │
├─────────┼────────────────────┼──────────────────────┼───────────────────────┤
│ Type 0  │ Retain Original    │ Birth date, SSN      │ Never changes         │
│         │ (never update)     │ Initial values only  │ (fixed attributes)    │
├─────────┼────────────────────┼──────────────────────┼───────────────────────┤
│ Type 1  │ Overwrite          │ Corrections (typos)  │ No history            │
│         │ UPDATE SET ...     │ Non-historical attrs │ Simple, fast          │
│         │                    │ "I don't care about  │ Can't audit           │
│         │                    │  previous value"     │                       │
├─────────┼────────────────────┼──────────────────────┼───────────────────────┤
│ Type 2  │ Add New Row        │ Audit trail needed   │ Table grows           │
│         │ (versioned history)│ Historical reporting │ Complex joins         │
│         │ + effective dates  │ Regulatory (GDPR)    │ (need date filter)    │
│         │ + is_current flag  │ "What was true then?"│ Standard approach     │
├─────────┼────────────────────┼──────────────────────┼───────────────────────┤
│ Type 3  │ Add Column         │ Only need previous   │ Limited history       │
│         │ (previous_value)   │ "Before/After" only  │ (only 1 previous)    │
│         │                    │ Simple comparison    │ Schema change needed  │
├─────────┼────────────────────┼──────────────────────┼───────────────────────┤
│ Type 4  │ Mini-Dimension     │ Fast-changing attrs  │ Extra join            │
│         │ (separate table)   │ (age band, income    │ Smaller dim table     │
│         │                    │  bracket, score)     │ Fewer Type 2 rows     │
├─────────┼────────────────────┼──────────────────────┼───────────────────────┤
│ Type 6  │ Hybrid (1+2+3)    │ Need both current    │ Most complex          │
│         │ Current + history  │ and historical view  │ Redundant storage     │
│         │ in same table      │ without complex join │ Best of all worlds    │
└─────────┴────────────────────┴──────────────────────┴───────────────────────┘
```

## Type 2 Deep Dive (Most Common in Production)

```
TABLE: dim_customer (SCD Type 2)
═════════════════════════════════

┌──────────┬───────────┬─────────┬──────────────┬──────────────┬────────────┐
│ sk       │ cust_bk   │ city    │ effective_dt │ expiry_dt    │ is_current │
├──────────┼───────────┼─────────┼──────────────┼──────────────┼────────────┤
│ 1001     │ C-001     │ NYC     │ 2023-01-01   │ 2024-03-14   │ false      │
│ 1002     │ C-001     │ LA      │ 2024-03-15   │ 9999-12-31   │ true       │
│ 1003     │ C-002     │ Chicago │ 2023-06-15   │ 9999-12-31   │ true       │
└──────────┴───────────┴─────────┴──────────────┴──────────────┴────────────┘

  sk = surrogate key (auto-increment)
  cust_bk = business key (natural key from source)
  effective_dt = when this version became active
  expiry_dt = when this version was superseded (9999-12-31 = current)
  is_current = convenience flag (redundant with expiry_dt but fast)

QUERY: "Revenue by city for January 2024"

  SELECT d.city, SUM(f.amount)
  FROM fact_orders f
  JOIN dim_customer d ON f.customer_sk = d.sk
  WHERE f.order_date BETWEEN '2024-01-01' AND '2024-01-31'
  GROUP BY d.city;

  → NYC gets credit (because fact_orders.customer_sk = 1001 for Jan orders)
  → The SK in the fact table FREEZES the dimension state at time of transaction

QUERY: "Current view of all customers"

  SELECT * FROM dim_customer WHERE is_current = true;

QUERY: "What city was customer C-001 in on Feb 15, 2024?"

  SELECT city FROM dim_customer
  WHERE cust_bk = 'C-001'
    AND effective_dt <= '2024-02-15'
    AND expiry_dt > '2024-02-15';
  → NYC
```

## SCD Type 2 Loading Strategy

```
MERGE PATTERN (Delta Lake / Iceberg):
═════════════════════════════════════

-- Step 1: Identify changes
WITH changes AS (
  SELECT 
    src.customer_bk,
    src.city,
    src.name,
    src.phone,
    MD5(CONCAT(src.city, '|', src.name, '|', src.phone)) as src_hash
  FROM staging.customers src
),
current_dim AS (
  SELECT 
    sk,
    cust_bk,
    city,
    name,
    phone,
    MD5(CONCAT(city, '|', name, '|', phone)) as dim_hash
  FROM dim_customer
  WHERE is_current = true
)

-- Step 2: Close expired records
UPDATE dim_customer
SET expiry_dt = CURRENT_DATE - INTERVAL '1 day',
    is_current = false
WHERE sk IN (
  SELECT d.sk 
  FROM current_dim d
  JOIN changes c ON d.cust_bk = c.customer_bk
  WHERE d.dim_hash != c.src_hash  -- Attribute changed
);

-- Step 3: Insert new versions
INSERT INTO dim_customer (cust_bk, city, name, phone, effective_dt, expiry_dt, is_current)
SELECT 
  c.customer_bk, c.city, c.name, c.phone,
  CURRENT_DATE,      -- effective today
  '9999-12-31',      -- no expiry
  true               -- current version
FROM changes c
JOIN current_dim d ON d.cust_bk = c.customer_bk
WHERE d.dim_hash != c.src_hash  -- Only changed records

UNION ALL

-- Step 4: Insert brand new customers
SELECT
  c.customer_bk, c.city, c.name, c.phone,
  CURRENT_DATE, '9999-12-31', true
FROM changes c
LEFT JOIN current_dim d ON d.cust_bk = c.customer_bk
WHERE d.cust_bk IS NULL;  -- New customer, not in dim yet


DELTA LAKE NATIVE MERGE:
═══════════════════════

MERGE INTO dim_customer AS target
USING (
  SELECT *, MD5(CONCAT(city,'|',name,'|',phone)) as hash FROM staging.customers
) AS source
ON target.cust_bk = source.customer_bk AND target.is_current = true

-- Close old version when attributes change
WHEN MATCHED AND target.hash != source.hash THEN
  UPDATE SET target.expiry_dt = CURRENT_DATE, target.is_current = false

-- Insert new version (handled separately after the MERGE)
;

-- Then insert new versions
INSERT INTO dim_customer
SELECT customer_bk, city, name, phone, CURRENT_DATE, '9999-12-31', true, hash
FROM staging.customers s
WHERE EXISTS (
  SELECT 1 FROM dim_customer d 
  WHERE d.cust_bk = s.customer_bk 
  AND d.is_current = false 
  AND d.expiry_dt = CURRENT_DATE
);
```

## Type 6 (Hybrid) - Best of All Worlds

```
TABLE: dim_customer_type6
═════════════════════════

┌──────┬─────────┬──────────────┬─────────────────┬──────────────┬────────┐
│ sk   │ cust_bk │ current_city │ historical_city │ effective_dt │ is_cur │
├──────┼─────────┼──────────────┼─────────────────┼──────────────┼────────┤
│ 1001 │ C-001   │ LA           │ NYC             │ 2023-01-01   │ false  │
│ 1002 │ C-001   │ LA           │ LA              │ 2024-03-15   │ true   │
└──────┴─────────┴──────────────┴─────────────────┴──────────────┴────────┘

  current_city: Always shows TODAY's value (Type 1 - overwritten on all rows)
  historical_city: Shows what was true at that row's time (Type 2 - versioned)

USE CASE:
  "Show me revenue by CURRENT city": JOIN on sk, GROUP BY current_city
  "Show me revenue by HISTORICAL city": JOIN on sk, GROUP BY historical_city
  Both work without complex date filtering!

TRADE-OFF:
  When John moves, you must UPDATE current_city on ALL historical rows.
  For 10M customers with avg 5 versions each = 50M rows to update.
  Fine for daily batch. Not suitable for real-time.
```

## Runnable Implementation

```python
"""
Slowly Changing Dimensions - All Types with Comparison
======================================================
Demonstrates:
- SCD Type 1 (Overwrite)
- SCD Type 2 (Add Row with effective dates)
- SCD Type 3 (Previous value column)
- SCD Type 6 (Hybrid)
- How each type answers the same business question differently
"""

from datetime import date, timedelta
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from collections import defaultdict
import json


# ============================================================================
# SCD TYPE 1: OVERWRITE
# ============================================================================

class SCDType1:
    """Simple overwrite - no history preserved."""
    
    def __init__(self):
        self.dimension: Dict[str, Dict] = {}  # business_key → attributes
    
    def load(self, business_key: str, attributes: Dict):
        """Always overwrite. Previous values lost forever."""
        self.dimension[business_key] = attributes.copy()
    
    def get(self, business_key: str) -> Optional[Dict]:
        return self.dimension.get(business_key)
    
    def query_revenue_by_city(self, facts: List[Dict]) -> Dict[str, float]:
        """All revenue attributed to CURRENT city."""
        result = defaultdict(float)
        for fact in facts:
            customer = self.dimension.get(fact["customer_bk"])
            if customer:
                result[customer["city"]] += fact["amount"]
        return dict(result)


# ============================================================================
# SCD TYPE 2: VERSIONED HISTORY
# ============================================================================

@dataclass
class DimRecord:
    surrogate_key: int
    business_key: str
    attributes: Dict
    effective_date: date
    expiry_date: date
    is_current: bool


class SCDType2:
    """Full history with effective dates."""
    
    def __init__(self):
        self.dimension: List[DimRecord] = []
        self.sk_counter = 1000
        # Fact table stores surrogate key (frozen at transaction time)
        self.fact_sk_map: Dict[str, int] = {}  # fact_id → dimension SK
    
    def _next_sk(self) -> int:
        self.sk_counter += 1
        return self.sk_counter
    
    def load(self, business_key: str, attributes: Dict, effective_date: date):
        """Insert new version if changed, close old version."""
        # Find current version
        current = None
        for record in self.dimension:
            if record.business_key == business_key and record.is_current:
                current = record
                break
        
        if current is None:
            # Brand new entity
            sk = self._next_sk()
            self.dimension.append(DimRecord(
                surrogate_key=sk,
                business_key=business_key,
                attributes=attributes.copy(),
                effective_date=effective_date,
                expiry_date=date(9999, 12, 31),
                is_current=True
            ))
        else:
            # Check if attributes changed
            if current.attributes != attributes:
                # Close old version
                current.expiry_date = effective_date - timedelta(days=1)
                current.is_current = False
                # Insert new version
                sk = self._next_sk()
                self.dimension.append(DimRecord(
                    surrogate_key=sk,
                    business_key=business_key,
                    attributes=attributes.copy(),
                    effective_date=effective_date,
                    expiry_date=date(9999, 12, 31),
                    is_current=True
                ))
    
    def get_current(self, business_key: str) -> Optional[Dict]:
        """Get current version."""
        for record in self.dimension:
            if record.business_key == business_key and record.is_current:
                return record.attributes
        return None
    
    def get_at_date(self, business_key: str, as_of: date) -> Optional[Dict]:
        """Point-in-time lookup."""
        for record in self.dimension:
            if (record.business_key == business_key and
                record.effective_date <= as_of <= record.expiry_date):
                return record.attributes
        return None
    
    def get_sk_at_date(self, business_key: str, as_of: date) -> Optional[int]:
        """Get surrogate key valid at a specific date."""
        for record in self.dimension:
            if (record.business_key == business_key and
                record.effective_date <= as_of <= record.expiry_date):
                return record.surrogate_key
        return None
    
    def get_history(self, business_key: str) -> List[Dict]:
        """Get all versions."""
        return [
            {
                "sk": r.surrogate_key,
                "effective": str(r.effective_date),
                "expiry": str(r.expiry_date),
                "is_current": r.is_current,
                **r.attributes
            }
            for r in self.dimension
            if r.business_key == business_key
        ]
    
    def query_revenue_by_city(self, facts: List[Dict]) -> Dict[str, float]:
        """Revenue attributed to city AS IT WAS at time of order."""
        result = defaultdict(float)
        for fact in facts:
            # Look up dimension state at ORDER DATE
            attrs = self.get_at_date(fact["customer_bk"], fact["order_date"])
            if attrs:
                result[attrs["city"]] += fact["amount"]
        return dict(result)


# ============================================================================
# SCD TYPE 3: PREVIOUS VALUE COLUMN
# ============================================================================

class SCDType3:
    """Keeps current + previous value only."""
    
    def __init__(self):
        self.dimension: Dict[str, Dict] = {}  # bk → {current_X, previous_X}
    
    def load(self, business_key: str, attributes: Dict):
        """Update with previous value tracking."""
        existing = self.dimension.get(business_key)
        
        if existing is None:
            # New record
            record = {}
            for key, value in attributes.items():
                record[f"current_{key}"] = value
                record[f"previous_{key}"] = None
            self.dimension[business_key] = record
        else:
            # Update: shift current to previous
            for key, value in attributes.items():
                if existing.get(f"current_{key}") != value:
                    existing[f"previous_{key}"] = existing.get(f"current_{key}")
                    existing[f"current_{key}"] = value
    
    def get(self, business_key: str) -> Optional[Dict]:
        return self.dimension.get(business_key)


# ============================================================================
# DEMONSTRATION
# ============================================================================

def run_scd_comparison():
    """Compare how different SCD types handle the same scenario."""
    print("=" * 70)
    print("SLOWLY CHANGING DIMENSIONS - TYPE COMPARISON")
    print("=" * 70)
    
    # Initialize all types
    type1 = SCDType1()
    type2 = SCDType2()
    type3 = SCDType3()
    
    # ─── TIMELINE OF EVENTS ───
    print("\n╔══ TIMELINE ══╗")
    print("""
  2024-01-01: John (C-001) lives in NYC, works at Acme Corp
  2024-01-15: John places Order A ($500) - shipped to NYC
  2024-02-01: John places Order B ($300) - shipped to NYC
  2024-03-15: John MOVES to LA, switches to Beta Inc
  2024-04-01: John places Order C ($700) - shipped to LA
  2024-05-01: John places Order D ($200) - shipped to LA
    """)
    
    # ─── LOAD INITIAL STATE ───
    initial = {"city": "NYC", "company": "Acme Corp", "name": "John Smith"}
    updated = {"city": "LA", "company": "Beta Inc", "name": "John Smith"}
    
    # Type 1: Load initial, then overwrite
    type1.load("C-001", initial)
    type1.load("C-001", updated)  # Overwrites!
    
    # Type 2: Load with dates
    type2.load("C-001", initial, date(2024, 1, 1))
    type2.load("C-001", updated, date(2024, 3, 15))
    
    # Type 3: Load with previous tracking
    type3.load("C-001", initial)
    type3.load("C-001", updated)
    
    # ─── FACT TABLE ───
    facts = [
        {"id": "OA", "customer_bk": "C-001", "order_date": date(2024, 1, 15), "amount": 500},
        {"id": "OB", "customer_bk": "C-001", "order_date": date(2024, 2, 1), "amount": 300},
        {"id": "OC", "customer_bk": "C-001", "order_date": date(2024, 4, 1), "amount": 700},
        {"id": "OD", "customer_bk": "C-001", "order_date": date(2024, 5, 1), "amount": 200},
    ]
    
    # ─── COMPARE RESULTS ───
    print("╔══ QUERY: 'Revenue by City' ══╗")
    print()
    
    # Type 1 result
    rev_type1 = type1.query_revenue_by_city(facts)
    print(f"  TYPE 1 (Overwrite): {rev_type1}")
    print(f"    → LA gets ALL $1,700 (NYC history LOST)")
    print(f"    → WRONG for historical reporting")
    
    # Type 2 result
    rev_type2 = type2.query_revenue_by_city(facts)
    print(f"\n  TYPE 2 (Versioned): {rev_type2}")
    print(f"    → NYC gets $800 (Jan+Feb orders), LA gets $900 (Apr+May orders)")
    print(f"    → CORRECT historical attribution")
    
    # ─── TYPE 2 POINT-IN-TIME ───
    print("\n╔══ TYPE 2: POINT-IN-TIME QUERIES ══╗")
    
    feb_state = type2.get_at_date("C-001", date(2024, 2, 15))
    apr_state = type2.get_at_date("C-001", date(2024, 4, 15))
    print(f"  John on Feb 15: {feb_state}")
    print(f"  John on Apr 15: {apr_state}")
    
    print(f"\n  Full history:")
    for version in type2.get_history("C-001"):
        print(f"    SK={version['sk']} [{version['effective']} → {version['expiry']}] "
              f"city={version['city']}, company={version['company']} "
              f"{'← CURRENT' if version['is_current'] else ''}")
    
    # ─── TYPE 3 VIEW ───
    print("\n╔══ TYPE 3: PREVIOUS VALUE ══╗")
    t3_record = type3.get("C-001")
    print(f"  Record: {json.dumps(t3_record, indent=4, default=str)}")
    print(f"  → Can answer: 'Where did John move FROM?' (NYC)")
    print(f"  → CANNOT answer: 'When did he move?' (no dates)")
    print(f"  → CANNOT track: more than 1 previous value")
    
    # ─── DECISION MATRIX ───
    print("\n╔══ DECISION MATRIX ══╗")
    print("""
  ┌────────────────────────────────────┬────────┬────────┬────────┐
  │ REQUIREMENT                         │ Type 1 │ Type 2 │ Type 3 │
  ├────────────────────────────────────┼────────┼────────┼────────┤
  │ "What is current state?"            │   ✓    │   ✓    │   ✓    │
  │ "What was state on date X?"         │   ✗    │   ✓    │   ✗    │
  │ "What was previous value?"          │   ✗    │   ✓    │   ✓    │
  │ "Full change history?"              │   ✗    │   ✓    │   ✗    │
  │ Simple to implement?                │   ✓    │   ✗    │   ✓    │
  │ Storage efficient?                  │   ✓    │   ✗    │   ✓    │
  │ Query performance (current)?        │   ✓    │   ✓*   │   ✓    │
  │ Query performance (historical)?     │  N/A   │   ✓    │  N/A   │
  │ Regulatory compliance?              │   ✗    │   ✓    │   ✗    │
  └────────────────────────────────────┴────────┴────────┴────────┘
  * Type 2 current queries need WHERE is_current=true filter
    """)
    
    # ─── PRODUCTION RECOMMENDATION ───
    print("╔══ PRODUCTION RECOMMENDATION ══╗")
    print("""
  DEFAULT CHOICE: Type 2 (versioned history)
    WHY: Most flexibility, regulatory compliance, correct reporting
    COST: 3-5x more rows per dimension (manageable with partitioning)
    
  USE Type 1 FOR: Error corrections, non-historical attributes
    EXAMPLE: Fix typo in customer name → Type 1 (not a real change)
    EXAMPLE: Customer phone number → Type 1 (nobody reports by phone)
    
  USE Type 2 FOR: Business-critical attributes that affect reporting
    EXAMPLE: Customer city, segment, tier → Type 2
    EXAMPLE: Product category, price → Type 2
    EXAMPLE: Employee department, title → Type 2
    
  HYBRID (most common in practice):
    Same dimension table has BOTH Type 1 and Type 2 columns:
    - name (Type 1): corrections only, no history needed
    - city (Type 2): affects reporting, need history
    - email (Type 1): not a reporting dimension
    - segment (Type 2): critical for all business analysis
    """)
    
    print("\n" + "=" * 70)


if __name__ == "__main__":
    run_scd_comparison()
```
