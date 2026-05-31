# Iceberg as Long-Term Source of Truth

## Why Iceberg for Historical Data

Traditional data lakes suffer from the "data swamp" problem — files accumulate without structure, schema drifts silently, and reconstructing a historical view becomes impossible. Iceberg solves this by treating **metadata as a first-class citizen**.

```
┌─────────────────────────────────────────────────────────────┐
│              TRADITIONAL DATA LAKE (Hive)                     │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  /data/events/year=2023/month=01/                           │
│    → Schema changed? Nobody knows.                          │
│    → Files deleted? No record.                              │
│    → What existed on Jan 15? Can't tell.                    │
│    → Who wrote what? No audit trail.                        │
│                                                              │
│  Result: "Data Swamp" — unreliable for historical queries    │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│              ICEBERG TABLE FORMAT                             │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Snapshot 1 (Jan 1) → Complete state captured               │
│  Snapshot 2 (Jan 2) → Schema evolved, tracked by column ID  │
│  Snapshot 3 (Jan 3) → Rows deleted, delete files recorded   │
│  ...                                                         │
│  Snapshot 900 (Mar 10) → Full lineage preserved             │
│                                                              │
│  Query ANY point in time: SELECT * FROM t FOR SYSTEM_TIME    │
│  AS OF TIMESTAMP '2023-01-15 00:00:00'                      │
│                                                              │
│  Result: Reliable, auditable, time-traversable archive       │
└─────────────────────────────────────────────────────────────┘
```

---

## The Three Pillars of Source-of-Truth

### Pillar 1: Immutable Snapshot History

Every write creates a new snapshot. Snapshots are **never modified** — only new ones are appended. This gives you a complete timeline of your data.

```
Snapshot Chain (immutable append-only):

  snap-001 ──→ snap-002 ──→ snap-003 ──→ snap-004 ──→ snap-005
  (initial)    (insert)     (update)     (delete)     (schema
                                                       change)

Each snapshot records:
  ┌──────────────────────────────────────┐
  │ snapshot-id: 3847293847293           │
  │ timestamp:   2024-01-15T10:30:00Z    │
  │ operation:   append / overwrite /    │
  │              delete / replace        │
  │ summary:                             │
  │   added-files: 12                    │
  │   deleted-files: 3                   │
  │   added-rows: 1,450,000             │
  │   deleted-rows: 200                  │
  │ parent-snapshot-id: 3847293847292    │
  │ manifest-list: s3://...manifest-list │
  └──────────────────────────────────────┘
```

**Real-World Example — Financial Audit at a Bank:**

```sql
-- What was the account balance on Dec 31 for year-end reporting?
SELECT account_id, balance, currency
FROM accounts.balances
FOR SYSTEM_TIME AS OF TIMESTAMP '2024-12-31 23:59:59'
WHERE account_type = 'savings';

-- Compare balances between two dates to detect anomalies
SELECT 
  current.account_id,
  historical.balance AS balance_dec_31,
  current.balance AS balance_today,
  current.balance - historical.balance AS change
FROM accounts.balances AS current
JOIN accounts.balances 
  FOR SYSTEM_TIME AS OF TIMESTAMP '2024-12-31 23:59:59' AS historical
  ON current.account_id = historical.account_id
WHERE ABS(current.balance - historical.balance) > 1000000;
```

### Pillar 2: Schema Evolution with Full Backward Compatibility

Iceberg tracks schema by **column IDs**, not names or positions. This means:
- Columns can be renamed without breaking historical queries
- Columns can be reordered without data rewriting
- New columns return `NULL` for old data
- Dropped columns remain readable in historical snapshots

```
Schema History (tracked in metadata):

  Schema v0 (2023-01):
    ├── id: 1        (int)
    ├── name: 2      (string)
    └── amount: 3    (decimal)

  Schema v1 (2023-06): Added column
    ├── id: 1        (int)
    ├── name: 2      (string)
    ├── amount: 3    (decimal)
    └── currency: 4  (string, default='USD')  ← NEW

  Schema v2 (2024-01): Renamed + type promoted
    ├── id: 1           (int)
    ├── full_name: 2    (string)         ← RENAMED from 'name'
    ├── amount: 3       (decimal(18,4))  ← WIDENED from decimal
    └── currency: 4     (string)

  Historical query on schema v0 data with v2 schema:
    → Column 2 returned as "full_name" (correct via ID mapping)
    → Column 4 returned as NULL (didn't exist in v0)
    → Column 3 returned as decimal(18,4) (safe promotion)
```

**Real-World Example — Healthcare System (HIPAA Compliance):**

```sql
-- Schema evolved: 'patient_name' → 'patient_full_name'
-- Old queries still work via column ID mapping

-- Query data from 2 years ago (before schema change)
SELECT patient_full_name, diagnosis_code, treatment_date
FROM medical.patient_records
FOR SYSTEM_TIME AS OF TIMESTAMP '2022-06-15 00:00:00'
WHERE diagnosis_code LIKE 'C%';

-- The engine maps column ID 5 → "patient_full_name" even though
-- the file on disk has the header "patient_name"
```

### Pillar 3: Partition Evolution Without Rewriting History

Iceberg decouples **logical partitioning** from physical file layout. When you change partition strategy, old data stays where it is — the metadata layer handles the translation.

```
Partition Evolution Timeline:

  2023-01 to 2023-06: Partitioned by month(event_time)
    s3://bucket/data/event_time_month=2023-01/file1.parquet
    s3://bucket/data/event_time_month=2023-02/file2.parquet

  2023-07 onwards: Changed to day(event_time) for better pruning
    s3://bucket/data/event_time_day=2023-07-01/file3.parquet
    s3://bucket/data/event_time_day=2023-07-02/file4.parquet

  Query spanning both partition schemes:
  ┌─────────────────────────────────────────────────┐
  │ SELECT * FROM events                             │
  │ WHERE event_time BETWEEN '2023-05-01'           │
  │                    AND '2023-08-01'             │
  │                                                  │
  │ Iceberg transparently:                          │
  │  • Reads monthly partitions for May-June        │
  │  • Reads daily partitions for July              │
  │  • Merges results seamlessly                    │
  └─────────────────────────────────────────────────┘
```

---

## Data Retention Strategies

### Strategy 1: Tiered Retention with S3 Lifecycle

```
┌──────────────────────────────────────────────────────────────────┐
│                    TIERED RETENTION ARCHITECTURE                   │
├──────────────────────────────────────────────────────────────────┤
│                                                                    │
│  HOT TIER (0-90 days)          WARM TIER (91-365 days)           │
│  ┌────────────────────┐        ┌────────────────────┐            │
│  │ S3 Standard        │        │ S3 Standard-IA     │            │
│  │ Full snapshots     │  ───→  │ Weekly snapshots   │            │
│  │ All manifests      │        │ Compacted files    │            │
│  │ Fast query access  │        │ Reduced metadata   │            │
│  │ $0.023/GB/month    │        │ $0.0125/GB/month   │            │
│  └────────────────────┘        └────────────────────┘            │
│                                         │                         │
│                                         ▼                         │
│  COLD TIER (1-7 years)         ARCHIVE TIER (7+ years)           │
│  ┌────────────────────┐        ┌────────────────────┐            │
│  │ S3 Glacier IR      │        │ S3 Glacier Deep    │            │
│  │ Monthly snapshots  │  ───→  │ Annual snapshots   │            │
│  │ Heavily compacted  │        │ Regulatory holds   │            │
│  │ Minutes to access  │        │ 12hr restore time  │            │
│  │ $0.004/GB/month    │        │ $0.00099/GB/month  │            │
│  └────────────────────┘        └────────────────────┘            │
│                                                                    │
└──────────────────────────────────────────────────────────────────┘
```

**Implementation with Table Properties:**

```sql
-- Configure snapshot retention
ALTER TABLE events SET TBLPROPERTIES (
  'history.expire.max-snapshot-age-ms' = '7776000000',  -- 90 days
  'history.expire.min-snapshots-to-keep' = '10'
);

-- For long-term audit tables, keep much longer
ALTER TABLE financial_transactions SET TBLPROPERTIES (
  'history.expire.max-snapshot-age-ms' = '220752000000',  -- 7 years
  'history.expire.min-snapshots-to-keep' = '365'
);
```

### Strategy 2: Branch-Based Retention (Iceberg 1.2+)

Branches allow you to maintain separate retention policies for different use cases:

```
Main Branch (production):
  └── Expires snapshots after 7 days (fast, recent queries)

Audit Branch:
  └── Retains snapshots for 7 years (compliance)

Analytics Branch:
  └── Retains snapshots for 90 days (trend analysis)

┌─────────────────────────────────────────────────────────┐
│                                                          │
│  main ─────●────●────●────●────●────●── (latest)       │
│             \                                            │
│  audit ──────●────●────●────●────●────●── (7yr retain) │
│               \                                          │
│  analytics ────●────●────●── (90d retain)               │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

```sql
-- Create a long-lived audit branch
ALTER TABLE transactions 
CREATE BRANCH audit_2024
AS OF VERSION 847293847293
RETAIN 2555 DAYS;  -- 7 years

-- Query the audit branch at any historical point
SELECT * FROM transactions VERSION AS OF 'audit_2024'
WHERE transaction_date = '2024-03-15';
```

### Strategy 3: Table Cloning for Regulatory Snapshots

```sql
-- Create a regulatory snapshot (zero-copy clone)
CREATE TABLE regulatory.eoy_2024_snapshot
CLONE financial.transactions
AS OF TIMESTAMP '2024-12-31 23:59:59';

-- This clone:
--   • Shares data files with the source (no duplication)
--   • Has independent metadata (can't be affected by source changes)
--   • Can be retained indefinitely regardless of source table policies
--   • Satisfies SOX, GDPR Article 17, HIPAA audit requirements
```

---

## Regulatory Compliance Patterns

### GDPR — Right to Erasure (Article 17)

The challenge: Iceberg is append-only, but GDPR requires the ability to delete personal data.

```
GDPR Deletion Architecture:

  ┌─────────────────────────────────────────────────────┐
  │                                                      │
  │  1. Deletion Request Received                       │
  │     └── Record in deletion_requests table           │
  │                                                      │
  │  2. Identify Affected Files                         │
  │     └── Query metadata for files containing PII     │
  │                                                      │
  │  3. Rewrite Files (excluding deleted user)          │
  │     └── New snapshot with rewritten data files      │
  │                                                      │
  │  4. Expire Old Snapshots                            │
  │     └── Remove snapshots containing the old data    │
  │                                                      │
  │  5. Orphan File Cleanup                             │
  │     └── Physically delete old data files from S3    │
  │                                                      │
  │  6. Verification                                     │
  │     └── Confirm user data absent in all snapshots   │
  │                                                      │
  └─────────────────────────────────────────────────────┘
```

```sql
-- Step 1: Delete the user's data
DELETE FROM user_events
WHERE user_id = 'user-to-forget-12345';

-- Step 2: Expire all snapshots that contained this user's data
CALL catalog.system.expire_snapshots(
  table => 'db.user_events',
  older_than => TIMESTAMP '2024-06-01 00:00:00',
  retain_last => 1  -- Keep only the post-deletion snapshot
);

-- Step 3: Remove orphaned files (physically delete from S3)
CALL catalog.system.remove_orphan_files(
  table => 'db.user_events',
  older_than => TIMESTAMP '2024-06-01 00:00:00'
);

-- Step 4: Verify deletion (should return 0 rows)
SELECT COUNT(*) FROM user_events
WHERE user_id = 'user-to-forget-12345';

-- Also verify across ALL retained snapshots
SELECT snapshot_id, COUNT(*) as user_rows
FROM user_events 
  FOR SYSTEM_TIME AS OF snapshot_id
WHERE user_id = 'user-to-forget-12345'
GROUP BY snapshot_id;
```

### SOX Compliance — Financial Record Immutability

```
SOX Requirement: Financial records must be immutable for 7 years.
Iceberg Solution: Branch-based retention + write-once policies.

  ┌───────────────────────────────────────────────────────┐
  │  TABLE: financial.general_ledger                       │
  │                                                        │
  │  Properties:                                           │
  │    write.wap.enabled = true (Write-Audit-Publish)     │
  │    history.expire.max-snapshot-age-ms = 7 years       │
  │    write.delete.mode = merge-on-read (preserve files) │
  │                                                        │
  │  Audit Branch: sox_fy2024                             │
  │    • Retains all snapshots for 7 years                │
  │    • Read-only after fiscal year close                │
  │    • Separate from production compaction              │
  │                                                        │
  │  S3 Configuration:                                     │
  │    • Object Lock: GOVERNANCE mode                     │
  │    • Retention: 7 years                               │
  │    • No lifecycle transitions until retention expires  │
  └───────────────────────────────────────────────────────┘
```

### HIPAA — Access Audit Trail

```sql
-- Iceberg metadata itself serves as an access log
-- Every query that reads data creates a scan plan through metadata

-- Who accessed patient records and when?
-- (Combine Iceberg metadata with query engine audit logs)

SELECT 
  query_id,
  user_name,
  query_text,
  tables_accessed,
  rows_returned,
  execution_time
FROM system.query_audit_log
WHERE tables_accessed LIKE '%patient_records%'
  AND execution_time > TIMESTAMP '2024-01-01'
ORDER BY execution_time DESC;

-- Iceberg snapshot metadata provides write audit
SELECT 
  snapshot_id,
  committed_at,
  operation,
  summary['added-records'] as records_added,
  summary['deleted-records'] as records_deleted
FROM prod.patient_records.snapshots
ORDER BY committed_at DESC;
```

---

## Building an Immutable Audit Trail

### Architecture: Event Sourcing with Iceberg

```
┌────────────────────────────────────────────────────────────────┐
│                  EVENT SOURCING ON ICEBERG                       │
├────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Source Systems          Iceberg Event Store                    │
│  ┌──────────┐           ┌───────────────────────────────────┐  │
│  │ App DB   │──CDC──┐   │ TABLE: events.raw_events          │  │
│  └──────────┘       │   │                                    │  │
│  ┌──────────┐       ├──▶│ event_id     UUID  (unique)        │  │
│  │ API Logs │──ETL──┤   │ event_type   STRING               │  │
│  └──────────┘       │   │ entity_id    STRING               │  │
│  ┌──────────┐       │   │ entity_type  STRING               │  │
│  │ IoT Msgs │──────-┘   │ payload      STRING (JSON)        │  │
│  └──────────┘           │ occurred_at  TIMESTAMP            │  │
│                          │ ingested_at  TIMESTAMP            │  │
│                          │ source       STRING               │  │
│                          │                                    │  │
│                          │ PARTITIONED BY days(occurred_at)   │  │
│                          └───────────────────────────────────┘  │
│                                      │                           │
│                                      ▼                           │
│                          ┌───────────────────────────────────┐  │
│                          │ TABLE: events.entity_snapshots     │  │
│                          │ (Materialized current state)       │  │
│                          │                                    │  │
│                          │ Built by replaying events          │  │
│                          │ Rebuildable from raw_events        │  │
│                          │ at ANY point in time               │  │
│                          └───────────────────────────────────┘  │
│                                                                  │
└────────────────────────────────────────────────────────────────┘
```

**Reconstructing Entity State at Any Point:**

```sql
-- Rebuild customer state as it existed on March 15, 2024
WITH ordered_events AS (
  SELECT 
    entity_id,
    event_type,
    payload,
    occurred_at,
    ROW_NUMBER() OVER (
      PARTITION BY entity_id 
      ORDER BY occurred_at DESC
    ) as rn
  FROM events.raw_events
  FOR SYSTEM_TIME AS OF TIMESTAMP '2024-03-15 23:59:59'
  WHERE entity_type = 'customer'
    AND entity_id = 'cust-789'
)
SELECT 
  entity_id,
  -- Replay events to reconstruct state
  LAST_VALUE(JSON_EXTRACT(payload, '$.name')) as name,
  LAST_VALUE(JSON_EXTRACT(payload, '$.email')) as email,
  LAST_VALUE(JSON_EXTRACT(payload, '$.plan')) as subscription_plan,
  MAX(occurred_at) as last_activity
FROM ordered_events
WHERE rn = 1
GROUP BY entity_id;
```

---

## Comparison: Iceberg vs. Traditional Archival Systems

| Aspect | Traditional Archive | Iceberg as Source of Truth |
|--------|-------------------|--------------------------|
| **Query Language** | Custom export tools, grep | Standard SQL |
| **Schema Changes** | Break historical access | Transparent via column IDs |
| **Point-in-Time** | Full database restore (hours) | Time-travel query (seconds) |
| **Storage Cost** | Full copies per snapshot | Shared data files, metadata-only snapshots |
| **Compliance Audit** | External audit logs | Built into metadata |
| **Data Correction** | Restore + replay | Single UPDATE + snapshot |
| **Cross-temporal Join** | Impossible without full restore | Native SQL JOIN across time |
| **Retention Granularity** | Per-backup (coarse) | Per-snapshot (fine-grained) |
| **Access Speed** | Hours (tape/glacier restore) | Seconds (metadata-driven pruning) |
| **Storage Overhead** | 10-50x (full copies) | 1.01-1.1x (metadata only) |

---

## Production Pattern: Slowly Changing Dimensions (SCD)

### SCD Type 2 with Iceberg (Track Full History)

```sql
-- Traditional SCD Type 2 requires maintaining valid_from/valid_to columns
-- Iceberg simplifies this dramatically with time travel

-- Instead of complex SCD logic, just do simple overwrites:
MERGE INTO dim.customers AS target
USING staging.customer_updates AS source
ON target.customer_id = source.customer_id
WHEN MATCHED THEN UPDATE SET *
WHEN NOT MATCHED THEN INSERT *;

-- To get the "SCD Type 2" view at any historical point:
SELECT * FROM dim.customers
FOR SYSTEM_TIME AS OF TIMESTAMP '2024-01-15 00:00:00'
WHERE customer_id = 'C-12345';

-- Compare how a customer record evolved:
SELECT 
  '2024-01-01' as snapshot_date, c.*
FROM dim.customers FOR SYSTEM_TIME AS OF TIMESTAMP '2024-01-01' c
WHERE c.customer_id = 'C-12345'
UNION ALL
SELECT 
  '2024-06-01' as snapshot_date, c.*
FROM dim.customers FOR SYSTEM_TIME AS OF TIMESTAMP '2024-06-01' c
WHERE c.customer_id = 'C-12345';
```

### SCD with Iceberg Tags (Named Snapshots)

```sql
-- Tag important business milestones
ALTER TABLE dim.customers 
CREATE TAG end_of_q1_2024 
AS OF VERSION 9283749283749;

ALTER TABLE dim.customers 
CREATE TAG end_of_q2_2024 
AS OF VERSION 9283749283912;

-- Query by business-meaningful name instead of timestamp
SELECT * FROM dim.customers VERSION AS OF 'end_of_q1_2024'
WHERE region = 'EMEA';

-- Perfect for:
--  • Fiscal year snapshots
--  • Pre/post migration comparisons
--  • Regulatory reporting dates
--  • Data quality validation checkpoints
```

---

## Cost Analysis: Iceberg as Archive vs. Traditional Backup

```
Scenario: 10TB dataset, 365 daily snapshots, 5% daily change rate

┌─────────────────────────────────────────────────────────────┐
│ TRADITIONAL BACKUP (Full daily copies)                       │
├─────────────────────────────────────────────────────────────┤
│ Storage: 10TB × 365 days = 3,650 TB                        │
│ Cost: 3,650 TB × $0.023/GB = $83,950/month                 │
│ Restore time: 2-4 hours per snapshot                        │
│ Query capability: None (must restore first)                  │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ ICEBERG (Snapshot-based, shared data files)                  │
├─────────────────────────────────────────────────────────────┤
│ Base data: 10 TB                                            │
│ Daily delta: 500 GB × 365 = 182.5 TB (new data files)      │
│ Metadata: ~50 GB (manifests, manifest lists)                │
│ Total: ~192.5 TB                                            │
│ Cost: 192.5 TB × $0.023/GB = $4,428/month                  │
│ Query time: Seconds (direct SQL, no restore needed)          │
│                                                              │
│ Savings: 95% storage reduction, instant query access         │
└─────────────────────────────────────────────────────────────┘
```

---

## Anti-Patterns to Avoid

### 1. Never Expiring Snapshots
```
Problem: Metadata grows unbounded, query planning slows to a crawl.
         Manifest list becomes enormous.

Solution: Define clear retention tiers:
  • Hot: Keep all snapshots (last 7 days)
  • Warm: Keep daily snapshots (8-90 days)
  • Cold: Keep weekly snapshots (91-365 days)
  • Archive: Keep monthly snapshots (1-7 years)
```

### 2. Using Time Travel Instead of Proper Backups
```
Problem: Snapshot expiration will eventually delete historical states.
         S3 bucket deletion destroys everything.

Solution: 
  • Use branches/tags for critical business milestones
  • Enable S3 Cross-Region Replication for disaster recovery
  • Create cloned tables for regulatory snapshots
  • S3 Object Lock for compliance-critical data
```

### 3. Not Planning for Schema Evolution
```
Problem: Dropping columns makes historical queries return incomplete data.
         Renaming without using ALTER TABLE breaks column ID tracking.

Solution:
  • Always use ALTER TABLE for schema changes (preserves column IDs)
  • Document schema evolution decisions in table properties
  • Test historical queries after schema changes
  • Never directly modify Parquet file schemas outside Iceberg
```

---

## Summary: Source of Truth Guarantees

| Guarantee | How Iceberg Delivers It |
|-----------|------------------------|
| **Completeness** | Every write recorded as snapshot; no silent mutations |
| **Consistency** | ACID transactions; snapshot isolation across readers |
| **Correctability** | UPDATE/DELETE create new snapshots; mistakes fixable without losing history |
| **Queryability** | Standard SQL with time travel; no restore/export needed |
| **Durability** | S3 11 nines durability; cross-region replication available |
| **Auditability** | Snapshot metadata tracks who/what/when for every change |
| **Evolvability** | Schema changes tracked by column ID; partition evolution without rewrite |
| **Compliance** | GDPR deletion possible; SOX retention via branches; HIPAA audit via metadata |
