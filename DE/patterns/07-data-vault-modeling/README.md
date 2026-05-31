# Pattern 07: Data Vault Modeling

## Why Data Vault? The Problem with Star Schema

```
STAR SCHEMA PROBLEM:
════════════════════
Star schema is great for querying, terrible for LOADING.

Scenario: Marketing adds a new customer attribute "loyalty_tier"
  Star Schema:  ALTER TABLE dim_customer ADD loyalty_tier VARCHAR(20);
                → Rebuild entire dimension table (millions of rows)
                → All ETL jobs touching dim_customer must be updated
                → Downstream reports may break

Scenario: Two source systems disagree on customer address
  Star Schema:  Which one wins? You must pick one.
                → Business context lost. Audit impossible.

Scenario: New source system comes online (acquisition)
  Star Schema:  Redesign fact/dim relationships
                → 6-month project to integrate

DATA VAULT SOLVES:
══════════════════
✓ Additive (never destructive) - new sources plug in without redesign
✓ Full audit trail - every version of every record from every source
✓ Parallel loading - no dependencies between source loads
✓ Source-system agnostic - business keys unify across systems
✓ Handles schema changes gracefully - just add new satellites
```

## Core Concepts

```
DATA VAULT HAS 3 ENTITY TYPES:
═══════════════════════════════

┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                              │
│  ┌─────────────┐         ┌─────────────┐         ┌─────────────┐          │
│  │    HUB      │         │    LINK      │         │  SATELLITE  │          │
│  │             │         │              │         │             │          │
│  │ Business Key│◀────────│ FK to Hub A  │         │ FK to Hub   │          │
│  │ Hash Key    │         │ FK to Hub B  │────────▶│ or Link     │          │
│  │ Load Date   │         │ Hash Key     │         │ Descriptive │          │
│  │ Record Src  │         │ Load Date    │         │  Attributes │          │
│  │             │         │ Record Src   │         │ Load Date   │          │
│  └─────────────┘         └──────────────┘         │ End Date    │          │
│                                                    │ Record Src  │          │
│  WHAT:                   WHAT:                     └─────────────┘          │
│  Core business entities  Relationships between     WHAT:                    │
│  (Customer, Order,       entities (Customer        Context/attributes       │
│   Product, Account)       placed Order,            that CHANGE over time    │
│                           Order contains Product)  (customer address,       │
│  GRAIN:                                             order status)           │
│  One row per unique      GRAIN:                                             │
│  business key            One row per unique        GRAIN:                    │
│  (deduplicated across    relationship              One row per change        │
│   ALL source systems)    combination               (full history kept)       │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘

KEY INSIGHT:
  Hub = "What exists" (immutable once created)
  Link = "How things relate" (immutable once created)
  Satellite = "What we know about it" (changes over time, versioned)
```

## Detailed Architecture

```
EXAMPLE: E-COMMERCE DATA VAULT
═══════════════════════════════

SOURCE SYSTEMS:
  • ERP (SAP) - orders, products
  • CRM (Salesforce) - customers, interactions
  • Website - clickstream, cart events

                    ┌─────────────────────────────────┐
                    │        HUB_CUSTOMER              │
                    │  ─────────────────────           │
                    │  hub_customer_hk (MD5 hash)      │
                    │  customer_bk (business key)      │  ← "email" or "customer_id"
                    │  load_date                       │
                    │  record_source                   │
                    └─────────────┬───────────────────┘
                                  │
              ┌───────────────────┼───────────────────────┐
              │                   │                        │
              ▼                   ▼                        ▼
┌─────────────────────┐ ┌─────────────────────┐ ┌─────────────────────┐
│ SAT_CUSTOMER_CRM    │ │ SAT_CUSTOMER_ERP    │ │ SAT_CUSTOMER_WEB    │
│ ───────────────     │ │ ───────────────     │ │ ───────────────     │
│ hub_customer_hk(FK) │ │ hub_customer_hk(FK) │ │ hub_customer_hk(FK) │
│ load_date (PK)      │ │ load_date (PK)      │ │ load_date (PK)      │
│ name                │ │ name                │ │ display_name        │
│ email               │ │ account_number      │ │ last_login          │
│ phone               │ │ credit_limit        │ │ preferred_language  │
│ address             │ │ payment_terms       │ │ browser_fingerprint │
│ loyalty_tier        │ │ shipping_address    │ │ session_count       │
│ hashdiff            │ │ hashdiff            │ │ hashdiff            │
│ record_source       │ │ record_source       │ │ record_source       │
└─────────────────────┘ └─────────────────────┘ └─────────────────────┘

  ▲ Each source has its OWN satellite
  ▲ No conflict resolution needed at load time
  ▲ Business rules applied later (in Business Vault or Gold layer)


LINK EXAMPLE:
┌─────────────────────┐      ┌─────────────────────────┐      ┌──────────────┐
│    HUB_CUSTOMER     │      │    LINK_ORDER            │      │  HUB_ORDER   │
│    (customer_bk)    │◀─────│    ─────────────         │─────▶│  (order_bk)  │
└─────────────────────┘      │    link_order_hk         │      └──────────────┘
                              │    hub_customer_hk (FK)  │
                              │    hub_order_hk (FK)     │
                              │    load_date             │
                              │    record_source         │
                              └─────────────────────────┘
                                          │
                                          ▼
                              ┌─────────────────────────┐
                              │  SAT_ORDER_DETAILS       │
                              │  ──────────────────      │
                              │  link_order_hk (FK)      │
                              │  load_date (PK)          │
                              │  order_status            │
                              │  total_amount            │
                              │  payment_method          │
                              │  shipping_method         │
                              │  hashdiff                │
                              └─────────────────────────┘
```

## Hash Key Strategy

```
WHY HASH KEYS?
══════════════
Problem: Business keys vary across systems
  CRM: customer_id = "SF-001234"
  ERP: customer_id = "SAP-C-001234"
  Web: customer_id = "email:john@example.com"

Solution: Hash the BUSINESS KEY to create a surrogate
  hub_customer_hk = MD5("john@example.com")  -- use canonical business key
  
Advantages:
  • Deterministic (same input → same hash, no sequence needed)
  • Parallel loadable (no sequence generator bottleneck)
  • Distributed (no central lookup required)
  • Performant joins (fixed-width, indexable)

HASHDIFF (Satellite change detection):
  hashdiff = MD5(CONCAT(name, '|', email, '|', phone, '|', address))
  
  If hashdiff changes → insert new satellite row (attribute changed)
  If hashdiff same → skip (no change, don't store duplicate)

PRODUCTION CHOICE:
  MD5: Fast, sufficient for data vault (not security)
  SHA-256: If compliance requires stronger hashing
  WARNING: Don't use MD5 for PII! Use SHA-256 or better.
```

## Loading Patterns

```
PARALLEL LOAD (Key Advantage of Data Vault):
════════════════════════════════════════════

Traditional Star Schema ETL:
  [Extract CRM] → [Transform] → [Load dim_customer] → [Load fact_order]
                                        ↑ SEQUENTIAL (can't parallelize)

Data Vault ETL:
  [Extract CRM] ──→ [Load HUB_CUSTOMER]  ──→ [Load SAT_CUSTOMER_CRM]
  [Extract ERP] ──→ [Load HUB_CUSTOMER]  ──→ [Load SAT_CUSTOMER_ERP]   PARALLEL!
  [Extract Web] ──→ [Load HUB_CUSTOMER]  ──→ [Load SAT_CUSTOMER_WEB]
  [Extract ERP] ──→ [Load HUB_ORDER]     ──→ [Load SAT_ORDER_DETAILS]
  [After hubs]  ──→ [Load LINK_ORDER]    

  Hub loads: INSERT WHERE NOT EXISTS (idempotent, parallel-safe)
  Sat loads: INSERT WHERE hashdiff changed (only store changes)
  Link loads: INSERT WHERE NOT EXISTS (after hubs loaded)

SQL PATTERN (Hub Load):
  INSERT INTO hub_customer (hub_customer_hk, customer_bk, load_date, record_source)
  SELECT 
    MD5(customer_email) as hub_customer_hk,
    customer_email as customer_bk,
    CURRENT_TIMESTAMP as load_date,
    'CRM' as record_source
  FROM staging.crm_customers
  WHERE MD5(customer_email) NOT IN (SELECT hub_customer_hk FROM hub_customer);

SQL PATTERN (Satellite Load):
  INSERT INTO sat_customer_crm
  SELECT 
    MD5(s.customer_email) as hub_customer_hk,
    CURRENT_TIMESTAMP as load_date,
    s.name, s.phone, s.address, s.loyalty_tier,
    MD5(CONCAT(s.name,'|',s.phone,'|',s.address,'|',s.loyalty_tier)) as hashdiff,
    'CRM' as record_source
  FROM staging.crm_customers s
  LEFT JOIN (
    SELECT hub_customer_hk, hashdiff
    FROM sat_customer_crm
    WHERE load_date = (SELECT MAX(load_date) FROM sat_customer_crm sc2
                       WHERE sc2.hub_customer_hk = sat_customer_crm.hub_customer_hk)
  ) current_sat ON current_sat.hub_customer_hk = MD5(s.customer_email)
  WHERE current_sat.hub_customer_hk IS NULL  -- New record
     OR current_sat.hashdiff != MD5(CONCAT(s.name,'|',s.phone,'|',s.address,'|',s.loyalty_tier));
```

## When to Use Data Vault vs Alternatives

```
┌──────────────────┬──────────────────┬──────────────────┬──────────────────┐
│                  │ DATA VAULT       │ STAR SCHEMA      │ ONE BIG TABLE    │
├──────────────────┼──────────────────┼──────────────────┼──────────────────┤
│ Best for         │ Enterprise DWH   │ Reporting/BI     │ Ad-hoc analytics │
│                  │ Many sources     │ Simple queries   │ Data science     │
│                  │ Regulatory/audit │ Known patterns   │ Small scale      │
├──────────────────┼──────────────────┼──────────────────┼──────────────────┤
│ Schema changes   │ Easy (add sat)   │ Hard (alter dim) │ Trivial (add col)│
├──────────────────┼──────────────────┼──────────────────┼──────────────────┤
│ Query complexity │ High (many joins)│ Low (star joins) │ None (one scan)  │
├──────────────────┼──────────────────┼──────────────────┼──────────────────┤
│ Load speed       │ Fast (parallel)  │ Slow (sequential)│ Fast (append)    │
├──────────────────┼──────────────────┼──────────────────┼──────────────────┤
│ Audit trail      │ Complete         │ Limited (SCD2)   │ None             │
├──────────────────┼──────────────────┼──────────────────┼──────────────────┤
│ # of sources     │ Many (10+)       │ Few (1-3)        │ One              │
├──────────────────┼──────────────────┼──────────────────┼──────────────────┤
│ Team size needed │ Large (5+)       │ Medium (2-4)     │ Small (1-2)      │
├──────────────────┼──────────────────┼──────────────────┼──────────────────┤
│ Typical org      │ Enterprise       │ Mid-size         │ Startup          │
│                  │ (bank, telco)    │ (e-commerce)     │ (early stage)    │
└──────────────────┴──────────────────┴──────────────────┴──────────────────┘

USE DATA VAULT WHEN:
  ✓ 10+ source systems feeding the warehouse
  ✓ Regulatory requirements (banking, healthcare, insurance)
  ✓ Sources change schemas frequently
  ✓ Need to track who said what and when (audit)
  ✓ Large team that can parallelize development

DON'T USE DATA VAULT WHEN:
  ✗ Single source system (overkill)
  ✗ Startup with 2 data engineers (too complex)
  ✗ Only need simple reporting (star schema is simpler)
  ✗ Real-time requirements (Data Vault is batch-oriented)
```

## Runnable Implementation

```python
"""
Data Vault 2.0 - Complete Loading Pipeline
==========================================
Demonstrates:
- Hub loading with business key deduplication
- Satellite loading with change detection (hashdiff)
- Link loading for relationships
- Multi-source integration (CRM + ERP disagree)
- Point-in-time query reconstruction
"""

import hashlib
import json
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from collections import defaultdict


def md5_hash(*args) -> str:
    """Generate MD5 hash from concatenated arguments."""
    concat = "|".join(str(a).strip().lower() for a in args)
    return hashlib.md5(concat.encode()).hexdigest()[:16]  # Truncated for readability


# ============================================================================
# DATA VAULT ENTITIES
# ============================================================================

@dataclass
class HubRecord:
    hash_key: str
    business_key: str
    load_date: str
    record_source: str


@dataclass
class SatelliteRecord:
    parent_hash_key: str  # FK to Hub or Link
    load_date: str
    end_date: Optional[str]  # None = current
    hashdiff: str
    attributes: Dict
    record_source: str


@dataclass 
class LinkRecord:
    hash_key: str
    hub_hash_keys: Dict[str, str]  # role_name → hub_hash_key
    load_date: str
    record_source: str


# ============================================================================
# DATA VAULT STORE
# ============================================================================

class DataVault:
    """In-memory Data Vault 2.0 implementation."""
    
    def __init__(self):
        # Hubs: hub_name → {hash_key → HubRecord}
        self.hubs: Dict[str, Dict[str, HubRecord]] = defaultdict(dict)
        # Satellites: sat_name → {parent_hk → [SatelliteRecord]} (ordered by load_date)
        self.satellites: Dict[str, Dict[str, List[SatelliteRecord]]] = defaultdict(lambda: defaultdict(list))
        # Links: link_name → {hash_key → LinkRecord}
        self.links: Dict[str, Dict[str, LinkRecord]] = defaultdict(dict)
        
        self.stats = {"hub_inserts": 0, "hub_skips": 0, 
                      "sat_inserts": 0, "sat_skips": 0,
                      "link_inserts": 0, "link_skips": 0}
    
    # ─── HUB LOADING ───
    def load_hub(self, hub_name: str, business_key: str, source: str, load_date: str) -> str:
        """Load a hub record. Returns hash_key. Idempotent."""
        hk = md5_hash(business_key)
        
        if hk not in self.hubs[hub_name]:
            self.hubs[hub_name][hk] = HubRecord(
                hash_key=hk,
                business_key=business_key,
                load_date=load_date,
                record_source=source
            )
            self.stats["hub_inserts"] += 1
        else:
            self.stats["hub_skips"] += 1
        
        return hk
    
    # ─── SATELLITE LOADING ───
    def load_satellite(self, sat_name: str, parent_hk: str, 
                       attributes: Dict, source: str, load_date: str) -> bool:
        """Load satellite record with change detection. Returns True if new version inserted."""
        hashdiff = md5_hash(*[str(v) for v in sorted(attributes.items())])
        
        existing = self.satellites[sat_name][parent_hk]
        
        # Check if current version has same hashdiff (no change)
        if existing:
            current = existing[-1]  # Latest
            if current.hashdiff == hashdiff:
                self.stats["sat_skips"] += 1
                return False
            # Close previous record
            current.end_date = load_date
        
        # Insert new version
        self.satellites[sat_name][parent_hk].append(SatelliteRecord(
            parent_hash_key=parent_hk,
            load_date=load_date,
            end_date=None,  # Current/active
            hashdiff=hashdiff,
            attributes=attributes.copy(),
            record_source=source
        ))
        self.stats["sat_inserts"] += 1
        return True
    
    # ─── LINK LOADING ───
    def load_link(self, link_name: str, hub_refs: Dict[str, str], 
                  source: str, load_date: str) -> str:
        """Load a link record. Returns hash_key. Idempotent."""
        # Link hash = hash of all hub hash keys combined
        hk = md5_hash(*[v for k, v in sorted(hub_refs.items())])
        
        if hk not in self.links[link_name]:
            self.links[link_name][hk] = LinkRecord(
                hash_key=hk,
                hub_hash_keys=hub_refs.copy(),
                load_date=load_date,
                record_source=source
            )
            self.stats["link_inserts"] += 1
        else:
            self.stats["link_skips"] += 1
        
        return hk
    
    # ─── POINT-IN-TIME QUERY ───
    def get_satellite_at(self, sat_name: str, parent_hk: str, 
                         as_of: str) -> Optional[Dict]:
        """Get satellite attributes as they were at a specific point in time."""
        records = self.satellites[sat_name].get(parent_hk, [])
        
        for record in records:
            if record.load_date <= as_of:
                if record.end_date is None or record.end_date > as_of:
                    return record.attributes
        return None
    
    def get_current_satellite(self, sat_name: str, parent_hk: str) -> Optional[Dict]:
        """Get current (latest) satellite attributes."""
        records = self.satellites[sat_name].get(parent_hk, [])
        if records:
            return records[-1].attributes
        return None
    
    def get_satellite_history(self, sat_name: str, parent_hk: str) -> List[Dict]:
        """Get full history of satellite changes."""
        records = self.satellites[sat_name].get(parent_hk, [])
        return [
            {
                "load_date": r.load_date,
                "end_date": r.end_date or "current",
                "source": r.record_source,
                **r.attributes
            }
            for r in records
        ]


# ============================================================================
# SIMULATION: Multi-Source Loading
# ============================================================================

def run_data_vault_demo():
    """Demonstrate Data Vault loading from multiple sources."""
    print("=" * 70)
    print("DATA VAULT 2.0 - MULTI-SOURCE LOADING DEMO")
    print("=" * 70)
    
    vault = DataVault()
    
    # ─── DAY 1: Initial Load from CRM ───
    print("\n╔══ DAY 1: CRM INITIAL LOAD ══╗")
    load_date_1 = "2024-01-01T00:00:00"
    
    crm_customers = [
        {"email": "john@example.com", "name": "John Smith", "phone": "555-0101", 
         "loyalty_tier": "Gold", "address": "123 Main St, NYC"},
        {"email": "jane@example.com", "name": "Jane Doe", "phone": "555-0102",
         "loyalty_tier": "Silver", "address": "456 Oak Ave, LA"},
        {"email": "bob@example.com", "name": "Bob Wilson", "phone": "555-0103",
         "loyalty_tier": "Bronze", "address": "789 Pine Rd, Chicago"},
    ]
    
    for cust in crm_customers:
        # Load Hub (business key = email)
        hk = vault.load_hub("hub_customer", cust["email"], "CRM", load_date_1)
        # Load Satellite (CRM-specific attributes)
        vault.load_satellite("sat_customer_crm", hk, {
            "name": cust["name"],
            "phone": cust["phone"],
            "loyalty_tier": cust["loyalty_tier"],
            "address": cust["address"],
        }, "CRM", load_date_1)
    
    print(f"  Loaded {len(crm_customers)} customers from CRM")
    
    # ─── DAY 1: Initial Load from ERP (same customers, different attributes) ───
    print("\n╔══ DAY 1: ERP INITIAL LOAD ══╗")
    
    erp_customers = [
        {"email": "john@example.com", "account_no": "ERP-001", "credit_limit": 10000,
         "payment_terms": "Net30", "shipping_address": "123 Main St, New York, NY 10001"},
        {"email": "jane@example.com", "account_no": "ERP-002", "credit_limit": 5000,
         "payment_terms": "Net15", "shipping_address": "456 Oak Ave, Los Angeles, CA 90001"},
    ]
    
    for cust in erp_customers:
        # Same Hub (same business key → same hash → no duplicate)
        hk = vault.load_hub("hub_customer", cust["email"], "ERP", load_date_1)
        # DIFFERENT Satellite (ERP context)
        vault.load_satellite("sat_customer_erp", hk, {
            "account_no": cust["account_no"],
            "credit_limit": cust["credit_limit"],
            "payment_terms": cust["payment_terms"],
            "shipping_address": cust["shipping_address"],
        }, "ERP", load_date_1)
    
    print(f"  Loaded {len(erp_customers)} customers from ERP (same hub, different satellite)")
    
    # ─── DAY 1: Load Orders (Links) ───
    print("\n╔══ DAY 1: ORDER LOAD (LINKS) ══╗")
    
    orders = [
        {"order_id": "ORD-001", "customer_email": "john@example.com", "amount": 150.00, "status": "confirmed"},
        {"order_id": "ORD-002", "customer_email": "john@example.com", "amount": 89.99, "status": "shipped"},
        {"order_id": "ORD-003", "customer_email": "jane@example.com", "amount": 250.00, "status": "pending"},
    ]
    
    for order in orders:
        # Load Order Hub
        order_hk = vault.load_hub("hub_order", order["order_id"], "ERP", load_date_1)
        # Load Customer Hub (already exists, will be skipped)
        cust_hk = vault.load_hub("hub_customer", order["customer_email"], "ERP", load_date_1)
        # Load Link (Customer → Order relationship)
        link_hk = vault.load_link("link_customer_order", {
            "customer": cust_hk,
            "order": order_hk,
        }, "ERP", load_date_1)
        # Load Order Satellite
        vault.load_satellite("sat_order_details", order_hk, {
            "amount": order["amount"],
            "status": order["status"],
        }, "ERP", load_date_1)
    
    print(f"  Loaded {len(orders)} orders with customer links")
    
    # ─── DAY 7: CRM UPDATE (John moved + got promoted) ───
    print("\n╔══ DAY 7: CRM UPDATE (CUSTOMER CHANGE) ══╗")
    load_date_7 = "2024-01-07T00:00:00"
    
    hk_john = vault.load_hub("hub_customer", "john@example.com", "CRM", load_date_7)
    changed = vault.load_satellite("sat_customer_crm", hk_john, {
        "name": "John Smith",
        "phone": "555-0101",
        "loyalty_tier": "Platinum",   # CHANGED: Gold → Platinum
        "address": "999 Park Ave, NYC",  # CHANGED: new address
    }, "CRM", load_date_7)
    
    print(f"  John's CRM satellite updated: {changed} (new version created)")
    
    # ─── DAY 14: Order status changed ───
    print("\n╔══ DAY 14: ORDER STATUS UPDATE ══╗")
    load_date_14 = "2024-01-14T00:00:00"
    
    order_hk = vault.load_hub("hub_order", "ORD-003", "ERP", load_date_14)
    vault.load_satellite("sat_order_details", order_hk, {
        "amount": 250.00,
        "status": "delivered",  # CHANGED: pending → delivered
    }, "ERP", load_date_14)
    
    print(f"  Order ORD-003 status updated to 'delivered'")
    
    # ─── QUERIES: Point-in-Time ───
    print("\n╔══ POINT-IN-TIME QUERIES ══╗")
    
    hk_john = md5_hash("john@example.com")
    
    # What was John's CRM data on Day 3?
    day3 = vault.get_satellite_at("sat_customer_crm", hk_john, "2024-01-03T00:00:00")
    print(f"\n  John's CRM data on Day 3:")
    print(f"    {json.dumps(day3, indent=6)}")
    
    # What is John's CRM data NOW?
    current = vault.get_current_satellite("sat_customer_crm", hk_john)
    print(f"\n  John's CRM data currently:")
    print(f"    {json.dumps(current, indent=6)}")
    
    # Full history of John's CRM satellite
    history = vault.get_satellite_history("sat_customer_crm", hk_john)
    print(f"\n  John's CRM history ({len(history)} versions):")
    for version in history:
        print(f"    [{version['load_date']} → {version['end_date']}] "
              f"tier={version['loyalty_tier']}, addr={version['address']}")
    
    # ─── MULTI-SOURCE VIEW (Business Vault) ───
    print("\n╔══ BUSINESS VAULT: UNIFIED CUSTOMER VIEW ══╗")
    print("  (Combining CRM + ERP satellites for John)")
    
    crm_view = vault.get_current_satellite("sat_customer_crm", hk_john)
    erp_view = vault.get_current_satellite("sat_customer_erp", hk_john)
    
    unified = {}
    if crm_view:
        unified.update(crm_view)
    if erp_view:
        unified.update(erp_view)
    # Business rule: CRM name wins over ERP name
    unified["_source_priority"] = "CRM for name/contact, ERP for financials"
    
    print(f"  Unified view: {json.dumps(unified, indent=4)}")
    
    # ─── STATS ───
    print("\n╔══ VAULT STATISTICS ══╗")
    print(f"  Hub inserts: {vault.stats['hub_inserts']} | skips: {vault.stats['hub_skips']}")
    print(f"  Satellite inserts: {vault.stats['sat_inserts']} | skips (no change): {vault.stats['sat_skips']}")
    print(f"  Link inserts: {vault.stats['link_inserts']} | skips: {vault.stats['link_skips']}")
    
    print(f"\n  Hubs:")
    for hub_name, records in vault.hubs.items():
        print(f"    {hub_name}: {len(records)} unique entities")
    
    print(f"\n  Satellites:")
    for sat_name, records in vault.satellites.items():
        total_versions = sum(len(v) for v in records.values())
        print(f"    {sat_name}: {len(records)} entities, {total_versions} total versions")
    
    print(f"\n  Links:")
    for link_name, records in vault.links.items():
        print(f"    {link_name}: {len(records)} relationships")
    
    print("\n" + "=" * 70)
    print("KEY TAKEAWAYS:")
    print("=" * 70)
    print("""
  1. Same customer loaded from CRM and ERP → ONE Hub record (deduplicated)
  2. Each source has its OWN satellite (no conflict resolution at load time)
  3. Changes create NEW satellite versions (full audit trail)
  4. Point-in-time queries work: "What did we know on Day X?"
  5. Links capture relationships without coupling Hub loads
  6. Parallel loading: CRM and ERP can load simultaneously
  7. Business rules applied AFTER loading (in Business Vault/Gold layer)
""")


if __name__ == "__main__":
    run_data_vault_demo()
```
