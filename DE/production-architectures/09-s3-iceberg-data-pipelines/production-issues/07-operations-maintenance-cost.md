# Operations, Maintenance & Cost Issues (#87-100)

Issues related to day-to-day operations, maintenance scheduling, cost governance,
table lifecycle management, and organizational challenges at scale.

---

## Issue #87: Maintenance Jobs Competing with Production Workloads

**Severity:** P1 - High
**Frequency:** Daily during maintenance windows
**Affected Components:** Production query latency, SLA breaches
**First seen at:** Shared compute environments

### Symptoms
```
- Dashboard queries slow every day at 2 AM (maintenance time)
- Compaction + production ETL fight for same cluster resources
- YARN/K8s pod evictions during compaction (memory pressure)
- Production SLA breached because maintenance consumed resources
- "Do we skip compaction or accept slow queries?" dilemma daily
```

### Root Cause
```
Maintenance operations are RESOURCE INTENSIVE:
  - Compaction: reads + writes entire file set (CPU + I/O + memory)
  - expire_snapshots: lists all files, computes references (memory)
  - remove_orphan_files: LIST entire S3 prefix (slow, I/O heavy)
  - rewrite_manifests: reads all manifests (I/O + CPU)
  
When sharing cluster with production:
  - Compaction grabs 50% of executors → production gets 50%
  - S3 request budget shared → compaction reads throttle query reads
  - Memory pressure → GC pauses affect all workloads
  - Network bandwidth saturated → everything slower
```

### Permanent Fix
```yaml
# Strategy 1: Isolated maintenance compute (dedicated resources)
# Kubernetes namespace with resource quotas
apiVersion: v1
kind: Namespace
metadata:
  name: iceberg-maintenance
---
apiVersion: v1
kind: ResourceQuota
metadata:
  name: maintenance-quota
  namespace: iceberg-maintenance
spec:
  hard:
    requests.cpu: "32"       # Limited CPU
    requests.memory: "128Gi" # Limited memory
    limits.cpu: "64"
    limits.memory: "256Gi"
---
# Production namespace has separate quota (unaffected)
apiVersion: v1
kind: ResourceQuota
metadata:
  name: production-quota
  namespace: iceberg-production
spec:
  hard:
    requests.cpu: "200"
    requests.memory: "800Gi"
```

```python
# Strategy 2: Time-based scheduling (maintenance during off-peak)
MAINTENANCE_SCHEDULE = {
    'compaction': {
        'streaming_tables': {'interval': '30m', 'window': '24/7'},  # Always needed
        'batch_tables': {'interval': '6h', 'window': '00:00-06:00'},
    },
    'expire_snapshots': {
        'all_tables': {'interval': '6h', 'window': '02:00-04:00'},
    },
    'orphan_cleanup': {
        'all_tables': {'interval': '7d', 'window': 'Sunday 03:00-05:00'},
    },
    'manifest_rewrite': {
        'all_tables': {'interval': '7d', 'window': 'Saturday 03:00-05:00'},
    }
}
```

### Prevention
```
1. Dedicated maintenance cluster (spot instances, cost-effective)
2. Resource isolation (K8s namespaces, YARN queues)
3. Schedule heavy maintenance during absolute off-peak
4. Priority: production queries > maintenance (preemption)
5. Monitor resource contention metrics
```

---

## Issue #88: Table Lifecycle Management (Thousands of Abandoned Tables)

**Severity:** P2 - Medium
**Frequency:** Ongoing (grows without governance)
**Affected Components:** Storage costs, catalog clutter, confusion
**First seen at:** Organizations with >1000 Iceberg tables

### Symptoms
```
- 5000 tables in catalog, 2000 never queried in 6 months
- Storage: $200K/month for tables nobody uses
- Data engineers afraid to delete anything ("might be needed")
- Naming chaos: test_final_v2_backup, prod_temp_20230115
- No owner for 40% of tables (original creator left)
```

### Root Cause
```
No table lifecycle governance:
  - Easy to create tables (1 SQL statement)
  - Hard to determine if table is still needed
  - No ownership tracking
  - No automatic expiry for temp/test tables
  - No cost attribution (nobody feels the pain)
  - Fear of deleting something important
```

### Permanent Fix
```python
# Table governance system
class TableLifecycleManager:
    """Automated table lifecycle management."""
    
    POLICIES = {
        'temp': {'max_age_days': 7, 'auto_delete': True},
        'dev': {'max_age_days': 30, 'auto_delete': True},
        'staging': {'max_age_days': 90, 'auto_delete': False, 'notify_owner': True},
        'production': {'max_age_days': None, 'review_interval_days': 180},
    }
    
    def audit_tables(self):
        """Weekly audit: find unused, ownerless, or policy-violating tables."""
        all_tables = self.catalog.list_tables()
        
        for table in all_tables:
            last_read = self.get_last_read_time(table)  # From query logs
            last_write = self.get_last_write_time(table)  # From snapshots
            owner = self.get_owner(table)
            tier = self.get_tier(table)
            
            policy = self.POLICIES[tier]
            days_inactive = (now() - max(last_read, last_write)).days
            
            if policy.get('auto_delete') and days_inactive > policy['max_age_days']:
                self.delete_table(table, reason="exceeded_max_age")
            elif days_inactive > 180 and tier == 'production':
                self.notify_owner(owner, table, "Table unused for 180 days - review needed")
            elif owner is None:
                self.escalate("Ownerless table", table)
    
    def enforce_naming(self, table_name):
        """Enforce naming convention at creation time."""
        pattern = r'^(prod|staging|dev)\.[a-z_]+\.[a-z_]+$'
        if not re.match(pattern, table_name):
            raise ValueError(f"Table name must match pattern: {pattern}")
```

```sql
-- Required table properties at creation (enforced by policy)
CREATE TABLE prod.team.table (...)
TBLPROPERTIES (
    'owner' = 'data-engineering-team',
    'owner.email' = 'de@company.com',
    'created.by' = 'john.doe',
    'tier' = 'production',
    'retention.data.days' = '365',
    'retention.snapshots.days' = '7',
    'sla.freshness.minutes' = '60',
    'cost-center' = 'CC-12345'
);
```

---

## Issue #89: Cost Attribution - Nobody Knows What Costs What

**Severity:** P2 - Medium
**Frequency:** Every month at budget review
**Affected Components:** Budget, team accountability
**First seen at:** AWS bill reaches $500K+/month with no breakdown

### Symptoms
```
- Total S3 bill: $500K/month. Per-table breakdown: unknown
- "Who owns the table that's costing $50K/month?" → nobody knows
- Cannot charge back costs to teams
- No incentive to optimize (everyone shares one bill)
- Finance asks "what are we paying for?" → no answer
```

### Root Cause
```
S3 billing is per-bucket, not per-prefix or per-table:
  - All tables in same bucket → single line item
  - Cannot distinguish: storage vs requests vs transfer per table
  - Compute costs (Spark/Flink) not linked to tables
  - Query costs (Athena) aggregated, not per-table

Missing:
  - Per-table storage cost
  - Per-table request cost (reads + writes)
  - Per-table compute cost (processing time)
  - Per-team aggregated cost
```

### Permanent Fix
```python
# Cost attribution system
class IcebergCostTracker:
    """Track and attribute costs per Iceberg table."""
    
    def calculate_storage_cost_per_table(self):
        """Calculate S3 storage cost per table."""
        tables = self.catalog.list_all_tables()
        
        for table in tables:
            # Total data size from metadata (no S3 LIST needed!)
            stats = spark.sql(f"""
                SELECT 
                    SUM(file_size_in_bytes) as total_bytes,
                    COUNT(*) as file_count
                FROM prod.{table}.files
            """).first()
            
            # S3 Standard: $0.023/GB/month
            storage_cost = (stats.total_bytes / 1024**3) * 0.023
            
            # Request cost estimation:
            # Writes: count commits/day × files/commit × $0.005/1000 PUTs
            # Reads: query_count × avg_files_scanned × $0.0004/1000 GETs
            
            self.record_cost(table, 'storage', storage_cost)
    
    def generate_team_report(self, team):
        """Monthly cost report per team."""
        team_tables = self.get_team_tables(team)
        return {
            'total_storage_cost': sum(t.storage_cost for t in team_tables),
            'total_compute_cost': sum(t.compute_cost for t in team_tables),
            'total_query_cost': sum(t.query_cost for t in team_tables),
            'top_5_expensive_tables': sorted(team_tables, key=lambda t: t.total_cost)[:5],
            'optimization_opportunities': self.find_optimizations(team_tables),
        }
```

```
Tools:
1. S3 Storage Lens: per-prefix cost analysis
2. AWS Cost Explorer tags: tag buckets/resources by team
3. Athena query logs: per-table bytes scanned → cost
4. CloudWatch: per-table S3 request metrics
5. Custom dashboard: real-time per-table cost tracking
```

---

## Issue #90: Data Quality Regression Undetected for Days

**Severity:** P0 - Critical
**Frequency:** After pipeline changes, source system changes
**Affected Components:** All downstream consumers, reports, ML models
**First seen at:** After source system upgrade breaks data format

### Symptoms
```
- Finance reports wrong numbers for 3 days before anyone notices
- ML model accuracy drops (bad training data for a week)
- Null columns that should never be null (source changed format)
- Row count dropped 80% silently (filter condition changed)
- Data type changed upstream → all values parse as NULL
```

### Root Cause
```
No automated data quality validation between commits:
  - Pipeline writes data without checking correctness
  - No row count assertions
  - No NULL rate monitoring
  - No schema drift detection
  - No statistical anomaly detection
  - No freshness alerts
  
  Typical timeline:
  Day 0: Source change breaks data format
  Day 0-3: Pipeline runs "successfully" (no errors, just wrong data)
  Day 3: Business user notices dashboard looks wrong
  Day 3-5: Investigation to find root cause
  Day 5: Fix deployed
  Day 5-7: Backfill/repair of corrupt data
  → 7 days of impact for issue that should be caught in minutes
```

### Permanent Fix
```python
# Data quality framework for Iceberg tables
class IcebergDataQuality:
    """Validate data quality on every commit."""
    
    def validate_after_write(self, table_name, snapshot_id):
        """Run validation suite after each commit."""
        
        checks = [
            self.check_row_count(table_name, snapshot_id),
            self.check_null_rates(table_name, snapshot_id),
            self.check_value_ranges(table_name, snapshot_id),
            self.check_uniqueness(table_name, snapshot_id),
            self.check_freshness(table_name, snapshot_id),
            self.check_schema_drift(table_name, snapshot_id),
        ]
        
        failures = [c for c in checks if not c.passed]
        
        if failures:
            severity = max(f.severity for f in failures)
            if severity == 'critical':
                # ROLLBACK: revert to previous snapshot
                self.rollback(table_name, snapshot_id - 1)
                self.alert_critical(table_name, failures)
            elif severity == 'warning':
                self.alert_warning(table_name, failures)
    
    def check_row_count(self, table_name, snapshot_id):
        """Verify row count within expected bounds."""
        current = self.get_row_count(table_name, snapshot_id)
        previous = self.get_row_count(table_name, snapshot_id - 1)
        
        change_pct = abs(current - previous) / max(previous, 1) * 100
        
        # Alert if >50% change (likely a problem)
        if change_pct > 50:
            return CheckResult(passed=False, severity='critical',
                message=f"Row count changed {change_pct:.1f}% ({previous} → {current})")
        return CheckResult(passed=True)
    
    def check_null_rates(self, table_name, snapshot_id):
        """Monitor NULL rates for critical columns."""
        critical_columns = self.get_critical_columns(table_name)
        
        for col in critical_columns:
            null_rate = spark.sql(f"""
                SELECT COUNT(*) FILTER (WHERE {col} IS NULL) * 100.0 / COUNT(*)
                FROM prod.{table_name}
                WHERE _snapshot_id = {snapshot_id}
            """).first()[0]
            
            if null_rate > col.max_null_pct:
                return CheckResult(passed=False, severity='critical',
                    message=f"Column {col.name}: NULL rate {null_rate}% (max: {col.max_null_pct}%)")
        
        return CheckResult(passed=True)
```

---

## Issue #91: Iceberg Library Version Mismatch Across Team

**Severity:** P1 - High
**Frequency:** In organizations with multiple teams/services
**Affected Components:** Cross-team data sharing, table compatibility
**First seen at:** When team A upgrades Iceberg but team B doesn't

### Symptoms
```
- Team A writes table → Team B can't read it
- Error: "Unsupported feature: format version 2"
- Different behaviors: Team A sees row-level deletes, Team B doesn't
- Spark 3.3 vs Spark 3.5 have different Iceberg behavior
- "Works on my machine" across different team environments
```

### Permanent Fix
```
1. Organization-wide Iceberg BOM (Bill of Materials):
   - Single version pinned for entire org
   - Quarterly coordinated upgrades
   - Compatibility testing before upgrade
   
2. Central platform team owns Iceberg version:
   - Publishes "approved versions" quarterly
   - All teams must use approved version within 30 days
   - CI/CD validates library version
   
3. Compatibility matrix maintained:
```

```markdown
| Iceberg Version | Spark | Flink | Trino | Athena | Format |
|----------------|-------|-------|-------|--------|--------|
| 1.4.x          | 3.3-3.5 | 1.16-1.18 | 435+ | v3 | v1, v2 |
| 1.5.x          | 3.4-3.5 | 1.17-1.19 | 440+ | v3 | v1, v2 |
| 1.6.x          | 3.5   | 1.18-1.20 | 445+ | v3 | v1, v2 |
```

---

## Issue #92: Runaway Spark Job Consuming Entire Cluster

**Severity:** P0 - Critical
**Frequency:** When compaction or backfill runs without resource limits
**Affected Components:** All workloads on shared cluster
**First seen at:** Automated compaction without guardrails

### Symptoms
```
- Compaction job acquires all 500 executors (cluster starved)
- Other jobs queued for 2 hours (no resources available)
- YARN queue backed up: 200 pending applications
- Cluster appears "full" but only one job running
- Auto-scaling kicks in but takes 10 minutes (too slow)
```

### Permanent Fix
```python
# Always set resource limits for maintenance jobs
compaction_spark = SparkSession.builder \
    .config("spark.dynamicAllocation.maxExecutors", "20") \
    .config("spark.dynamicAllocation.minExecutors", "2") \
    .config("spark.executor.memory", "8g") \
    .config("spark.executor.cores", "2") \
    .config("spark.yarn.queue", "maintenance") \
    .config("spark.scheduler.mode", "FAIR") \
    .getOrCreate()
```

```yaml
# YARN queue configuration (capacity scheduler)
queues:
  production:
    capacity: 60%
    maximum-capacity: 80%
    priority: 100
  maintenance:
    capacity: 20%
    maximum-capacity: 30%
    priority: 10
  adhoc:
    capacity: 20%
    maximum-capacity: 40%
    priority: 50
```

---

## Issue #93: Table Migration from Hive/Delta to Iceberg Fails at Scale

**Severity:** P1 - High
**Frequency:** During migration projects (one-time but critical)
**Affected Components:** Migration timeline, project delivery
**First seen at:** Every large-scale migration project

### Symptoms
```
- Migration of 100TB table: OOM after 12 hours
- Migrate procedure fails: "Too many files to process"
- Migrated table has wrong partition spec
- Performance regression after migration (missing statistics)
- 50,000 tables to migrate, each taking 1 hour = 6 years(!)
```

### Root Cause
```
Migration challenges at scale:

1. In-place migration (snapshot existing files):
   - Must read ALL file metadata (millions of files)
   - Generate Iceberg manifests for existing Parquet files
   - Single-threaded metadata processing → hours for large tables
   
2. Full-copy migration:
   - Read all data → write as Iceberg → verify
   - For 100TB: 100TB read + 100TB write + verification
   - 12+ hours for single table, × 50,000 tables = impossible
   
3. Partition mapping:
   - Hive partitions (explicit directory structure) → Iceberg hidden partitions
   - Partition names may not map cleanly
   - Mixed partition formats (string dates vs timestamps)
```

### Permanent Fix
```python
# Scalable migration framework
class IcebergMigrationManager:
    """Manage migration of thousands of tables to Iceberg."""
    
    def migrate_in_place(self, hive_table, iceberg_table):
        """Snapshot migration (fast, no data copy)."""
        spark.sql(f"""
            CALL prod.system.snapshot(
                source_table => '{hive_table}',
                table => '{iceberg_table}',
                properties => map(
                    'format-version', '2'
                )
            )
        """)
        
        # Post-migration: collect statistics (missing from Hive files)
        spark.sql(f"""
            CALL prod.system.rewrite_data_files(
                table => '{iceberg_table}',
                strategy => 'binpack'
            )
        """)
    
    def parallel_migration(self, table_list, max_concurrent=10):
        """Migrate many tables in parallel."""
        from concurrent.futures import ThreadPoolExecutor
        
        # Sort by size: small tables first (quick wins)
        sorted_tables = sorted(table_list, key=lambda t: t.size_bytes)
        
        with ThreadPoolExecutor(max_workers=max_concurrent) as executor:
            futures = {
                executor.submit(self.migrate_in_place, t.hive_name, t.iceberg_name): t
                for t in sorted_tables
            }
            for future in as_completed(futures):
                table = futures[future]
                try:
                    future.result()
                    self.mark_migrated(table)
                except Exception as e:
                    self.mark_failed(table, str(e))
```

---

## Issue #94: Accidental Table DROP in Production

**Severity:** P0 - Critical
**Frequency:** Rare but catastrophic (1-2x per year)
**Affected Components:** Complete data loss for dropped table
**First seen at:** Human error (wrong environment, wrong table)

### Symptoms
```
- Table gone from catalog (immediate impact on all consumers)
- Data files may still exist on S3 (catalog pointer lost)
- All downstream pipelines fail
- No built-in "undo" for DROP TABLE
- Panic in the team
```

### Root Cause
```
Common causes:
  - Developer ran DROP TABLE in wrong environment (prod vs dev)
  - Script variable error: DROP TABLE ${TABLE} (wrong variable value)
  - Automation bug: cleanup script too aggressive
  - Terraform destroy on wrong resource
  - Manual cleanup of "unused" table that was actually needed
```

### Permanent Fix
```python
# Prevention layers:

# Layer 1: Soft delete (rename, don't drop)
def safe_drop_table(table_name, confirm=False):
    """Soft-delete: rename with expiry date instead of dropping."""
    if not confirm:
        raise ValueError("Must explicitly confirm drop")
    
    expiry = (datetime.now() + timedelta(days=30)).strftime('%Y%m%d')
    tombstone_name = f"_tombstone_{table_name}_{expiry}"
    
    spark.sql(f"ALTER TABLE {table_name} RENAME TO {tombstone_name}")
    spark.sql(f"""ALTER TABLE {tombstone_name} SET TBLPROPERTIES (
        'drop.requested.by' = '{current_user()}',
        'drop.requested.at' = '{datetime.now().isoformat()}',
        'drop.permanent.after' = '{expiry}'
    )""")
    
    logger.critical(f"TABLE {table_name} SOFT-DELETED. Recoverable until {expiry}")

# Layer 2: IAM prevention (no DROP in production)
# Only automation role can drop. Humans cannot.

# Layer 3: Catalog backup (hourly export of all table pointers)
def backup_catalog():
    """Hourly backup of all metadata locations."""
    tables = glue.get_tables(DatabaseName='production')
    backup = {t['Name']: t['Parameters'].get('metadata_location') for t in tables}
    s3.put_object(
        Bucket='catalog-backups',
        Key=f'backup/{datetime.now().isoformat()}.json',
        Body=json.dumps(backup)
    )
```

```
Recovery if DROP already happened:
1. Data files likely still on S3 (DROP removes catalog pointer, not data)
2. Find last metadata.json file in S3:
   aws s3 ls s3://bucket/db/table/metadata/ --recursive | sort | tail -5
3. Register table with found metadata:
   CALL prod.system.register_table(
     table => 'db.table',
     metadata_file => 's3://bucket/db/table/metadata/v-last.metadata.json'
   )
```

---

## Issue #95: Inadequate Capacity Planning (Storage Growth Surprise)

**Severity:** P2 - Medium
**Frequency:** Quarterly (budget review shock)
**Affected Components:** Budget, infrastructure scaling
**First seen at:** 6 months into Iceberg deployment

### Symptoms
```
- Storage growing 3x faster than data growth (unexplained)
- Projected cost: $1M/year. Actual: $3M/year after 6 months.
- S3 bill doubling every quarter
- No visibility into growth drivers (which tables? why?)
- Emergency budget requests to finance
```

### Root Cause
```
Hidden storage multipliers:

  Raw data ingestion: 10TB/month
  Expected storage: 10TB/month × 12 = 120TB/year

  Actual storage:
    Raw data: 120TB
    + Snapshots (7 days × 10TB): +70TB
    + Compaction doubles: +120TB (temporary but overlapping)
    + Delete files: +12TB
    + Orphan files (not cleaned): +36TB
    + Metadata: +6TB
    + Multipart fragments: +3TB
    = 367TB actual (3x expected!)
    
  Additional multipliers:
    - Tables with long snapshot retention (audit): 10x raw
    - MoR tables with slow compaction: 2x raw
    - Cross-region replication: 2x everything
```

### Permanent Fix
```python
# Capacity planning calculator
class IcebergCapacityPlanner:
    def project_storage(self, table_config):
        raw_growth_per_month = table_config.raw_ingest_tb_per_month
        
        # Compute multipliers
        snapshot_multiplier = min(table_config.snapshot_retention_days / 30, 3)
        compaction_multiplier = 1.3  # 30% overhead during compaction
        orphan_multiplier = 1.1 if table_config.has_cleanup else 1.5
        mor_multiplier = 1.2 if table_config.is_mor else 1.0
        replication_multiplier = table_config.num_regions
        
        total_multiplier = (
            1  # Raw data
            + snapshot_multiplier
            + compaction_multiplier - 1
            + orphan_multiplier - 1
            + mor_multiplier - 1
        ) * replication_multiplier
        
        return raw_growth_per_month * total_multiplier
    
    # For 10TB/month ingestion:
    # Conservative estimate: 10TB × 3.5 = 35TB/month actual storage cost
```

---

## Issue #96: No Rollback Strategy for Bad Data Writes

**Severity:** P1 - High
**Frequency:** After pipeline bugs write incorrect data
**Affected Components:** Data correctness recovery
**First seen at:** Every production data pipeline eventually

### Symptoms
```
- Pipeline bug wrote 1 billion incorrect rows
- Downstream reports used wrong data for 4 hours
- Need to "undo" the bad write but table has subsequent good writes
- Simple rollback would lose GOOD data written after the bad write
- Manual repair taking days
```

### Permanent Fix
```python
# Strategy 1: Rollback to specific snapshot (loses subsequent writes)
def simple_rollback(table_name, good_snapshot_id):
    """Roll back to last known good state. LOSES subsequent writes."""
    spark.sql(f"""
        CALL prod.system.rollback_to_snapshot(
            table => '{table_name}',
            snapshot_id => {good_snapshot_id}
        )
    """)
    # WARNING: All commits after good_snapshot_id are lost!

# Strategy 2: Cherry-pick (undo specific bad snapshot, keep others)
def cherry_pick_revert(table_name, bad_snapshot_id):
    """Revert specific snapshot without losing subsequent changes."""
    
    # Get files added by the bad snapshot
    bad_files = spark.sql(f"""
        SELECT file_path FROM prod.{table_name}.all_data_files
        WHERE snapshot_id = {bad_snapshot_id}
        AND content = 0  -- DATA files (not delete files)
    """).collect()
    
    # Delete those specific files from current snapshot
    for file_batch in chunked(bad_files, 1000):
        paths = [f.file_path for f in file_batch]
        spark.sql(f"""
            DELETE FROM prod.{table_name}
            WHERE _file IN ({','.join(f"'{p}'" for p in paths)})
        """)

# Strategy 3: Overwrite partition (replace bad data with corrected)
def overwrite_with_correct(table_name, partition_filter, correct_df):
    """Replace bad partition data with corrected version."""
    correct_df.writeTo(f"prod.{table_name}") \
        .overwritePartitions()
```

---

## Issue #97: Testing Pipeline Changes Without Production Impact

**Severity:** P2 - Medium
**Frequency:** Every pipeline deployment
**Affected Components:** Development velocity, deployment confidence
**First seen at:** Teams without proper staging environment

### Symptoms
```
- "Let's test in prod" → data corruption
- No way to validate pipeline output before committing
- Staging environment has different data characteristics
- Schema changes deployed blind (hope for the best)
- Every deployment is a gamble
```

### Permanent Fix
```
1. Nessie branches for safe testing:
```

```python
# Test pipeline changes on branch (doesn't affect production)
def test_on_branch(pipeline_fn, table_name):
    """Run pipeline on isolated branch, validate, then merge."""
    
    branch_name = f"test-{pipeline_fn.__name__}-{uuid4().hex[:8]}"
    
    # Create branch from current main
    spark.sql(f"ALTER TABLE {table_name} CREATE BRANCH `{branch_name}`")
    
    try:
        # Run pipeline on branch
        spark.conf.set("spark.sql.catalog.prod.ref", branch_name)
        pipeline_fn(table_name)
        
        # Validate output
        assert_row_count_reasonable(table_name)
        assert_no_nulls_in_required_columns(table_name)
        assert_schema_compatible(table_name)
        
        # If valid: merge to main
        spark.conf.set("spark.sql.catalog.prod.ref", "main")
        # Manual merge approval required for production
        return {"status": "validated", "branch": branch_name}
        
    except Exception as e:
        # Drop branch (no production impact)
        spark.sql(f"ALTER TABLE {table_name} DROP BRANCH `{branch_name}`")
        raise
```

---

## Issue #98: Compliance Audit Fails (Cannot Prove Data Lineage)

**Severity:** P1 - High
**Frequency:** Annual audits, regulatory reviews
**Affected Components:** Regulatory compliance, audit certification
**First seen at:** SOX/GDPR/HIPAA audits

### Symptoms
```
- Auditor asks: "Show me what data looked like on March 15 at 2 PM"
- Cannot prove: who wrote what, when, and from which source
- No lineage: table → where did this data come from?
- Cannot demonstrate GDPR deletion was complete
- Audit finding: "insufficient data governance controls"
```

### Permanent Fix
```python
# Iceberg provides built-in audit capabilities:

# 1. Point-in-time query (prove table state at any time)
audit_query = f"""
    SELECT * FROM prod.{table_name}
    FOR SYSTEM_TIME AS OF TIMESTAMP '2024-03-15 14:00:00'
"""

# 2. Snapshot history (who committed, when)
history = spark.sql(f"""
    SELECT 
        snapshot_id,
        committed_at,
        operation,
        summary['added-records'] as added_rows,
        summary['deleted-records'] as deleted_rows,
        summary['spark.app.id'] as job_id
    FROM prod.{table_name}.snapshots
    ORDER BY committed_at
""")

# 3. Data lineage tracking (custom metadata in commits)
# Add lineage info to every commit:
spark.conf.set("spark.sql.iceberg.commit.metadata.source_system", "payment_gateway")
spark.conf.set("spark.sql.iceberg.commit.metadata.pipeline_id", "etl-payments-daily")
spark.conf.set("spark.sql.iceberg.commit.metadata.source_timestamp", "2024-03-15T14:00:00Z")

# 4. GDPR deletion proof
def prove_deletion(table_name, user_id, deletion_date):
    """Generate compliance proof of user data deletion."""
    
    # Show data existed before deletion
    before = spark.sql(f"""
        SELECT COUNT(*) FROM prod.{table_name}
        FOR SYSTEM_TIME AS OF TIMESTAMP '{deletion_date} 00:00:00'
        WHERE user_id = '{user_id}'
    """).first()[0]
    
    # Show data absent after deletion
    after = spark.sql(f"""
        SELECT COUNT(*) FROM prod.{table_name}
        WHERE user_id = '{user_id}'
    """).first()[0]
    
    return {
        'user_id': user_id,
        'records_before_deletion': before,
        'records_after_deletion': after,
        'deletion_confirmed': after == 0,
        'deletion_date': deletion_date,
        'proof_generated_at': datetime.now().isoformat()
    }
```

---

## Issue #99: Iceberg Table Becomes "Unmaintainable" (Too Large for Any Operation)

**Severity:** P0 - Critical
**Frequency:** Rare but terrifying (neglected tables)
**Affected Components:** All operations on the table
**First seen at:** Tables running for years without maintenance

### Symptoms
```
- expire_snapshots: OOM (500K snapshots to process)
- rewrite_data_files: timeout (10M files to compact)
- remove_orphan_files: runs for 48 hours, still not done
- Any DDL operation: hangs indefinitely
- Table effectively "frozen" - can't maintain, can't migrate
```

### Root Cause
```
Accumulated tech debt over years:
  - 500K snapshots (never expired)
  - 10M data files (never compacted)
  - 5M orphan files (never cleaned)
  - 100K manifests (never rewritten)
  - Metadata file: 2GB JSON (500K snapshot entries)
  
  Any maintenance operation must process this backlog:
    expire_snapshots: load 2GB metadata → parse 500K entries → OOM
    compact: plan 10M files → generate task set → OOM
    Even simple SELECT COUNT(*) → plan 10M files → timeout
```

### Permanent Fix
```python
# Progressive recovery for "unmaintainable" table
def recover_table(table_name):
    """Multi-stage recovery for severely neglected table."""
    
    # Stage 1: Increase resources dramatically
    spark = SparkSession.builder \
        .config("spark.driver.memory", "64g") \
        .config("spark.executor.memory", "32g") \
        .config("spark.dynamicAllocation.maxExecutors", "100") \
        .getOrCreate()
    
    # Stage 2: Expire snapshots in chunks (not all at once)
    for i in range(100):  # 100 rounds, each expiring oldest batch
        try:
            spark.sql(f"""
                CALL prod.system.expire_snapshots(
                    table => '{table_name}',
                    older_than => current_timestamp() - INTERVAL 1 DAY,
                    retain_last => 5,
                    max_concurrent_deletes => 10
                )
            """)
            break
        except Exception as e:
            if "OOM" in str(e):
                # Reduce scope: expire fewer at a time
                spark.sql(f"""
                    CALL prod.system.expire_snapshots(
                        table => '{table_name}',
                        older_than => current_timestamp() - INTERVAL 365 DAYS,
                        retain_last => 1000
                    )
                """)
    
    # Stage 3: Compact in small batches (partition by partition)
    partitions = spark.sql(f"SELECT DISTINCT partition FROM prod.{table_name}.files").collect()
    for partition in partitions:
        spark.sql(f"""
            CALL prod.system.rewrite_data_files(
                table => '{table_name}',
                where => "partition = '{partition.partition}'",
                strategy => 'binpack',
                options => map(
                    'partial-progress.enabled', 'true',
                    'partial-progress.max-commits', '5',
                    'max-file-group-size-bytes', '5368709120'
                )
            )
        """)
    
    # Stage 4: Rewrite manifests
    spark.sql(f"CALL prod.system.rewrite_manifests('{table_name}')")
    
    # Stage 5: Orphan cleanup (after all above settled)
    spark.sql(f"""
        CALL prod.system.remove_orphan_files(
            table => '{table_name}',
            older_than => current_timestamp() - INTERVAL 3 DAYS
        )
    """)
```

---

## Issue #100: Multi-Engine Inconsistency (Spark Writes, Trino Reads Different Data)

**Severity:** P1 - High
**Frequency:** In multi-engine environments
**Affected Components:** Data trust, cross-team confusion
**First seen at:** Organizations using Spark (write) + Trino (query)

### Symptoms
```
- Spark INSERT reports 1M rows committed
- Trino SELECT COUNT(*) returns 999,500 rows (500 "missing")
- Athena shows different result than Trino on same table
- Timestamp values differ between engines
- Decimal precision issues between engines
```

### Root Cause
```
Multi-engine inconsistencies:

1. Metadata caching: Trino cache TTL vs Spark live read
   → Trino reads stale snapshot (see Issue #8)
   
2. Timestamp handling:
   Spark: TIMESTAMP → microseconds (configurable)
   Trino: TIMESTAMP(6) → microseconds
   Athena v2: TIMESTAMP → milliseconds (!)
   → Same value, different interpretation (see Issue #12)
   
3. Decimal handling:
   Spark: DECIMAL(38,18) → BigDecimal
   Trino: DECIMAL(38,18) → fixed point
   Rounding differences in edge cases
   
4. NULL handling in aggregations:
   Spark: COUNT(*) counts NULLs
   Trino: COUNT(*) counts NULLs
   But: COUNT(column) differs on NULL semantics
   
5. Partition pruning differences:
   Same filter may prune differently across engines
   → Different engines read different file sets → different results (if bugs)
```

### Permanent Fix
```
1. Standardize configuration across all engines:
   - Same timestamp precision (microseconds, Iceberg v2)
   - Same timezone (UTC always)
   - Same decimal handling mode
   
2. Integration tests: write with A, read with B, verify equality
   
3. Cache alignment:
   - Same TTL across engines
   - Or: all engines read current snapshot (disable cache)
   
4. Golden dataset test:
   - Known dataset written once
   - ALL engines query same assertions
   - Automated regression test on every upgrade
```

```python
# Cross-engine validation test
def validate_cross_engine(table_name):
    """Verify all engines return same results."""
    
    spark_count = spark.sql(f"SELECT COUNT(*) FROM {table_name}").first()[0]
    trino_count = trino_query(f"SELECT COUNT(*) FROM {table_name}")
    athena_count = athena_query(f"SELECT COUNT(*) FROM {table_name}")
    
    assert spark_count == trino_count == athena_count, \
        f"Count mismatch: Spark={spark_count}, Trino={trino_count}, Athena={athena_count}"
    
    # Verify specific values
    spark_sum = spark.sql(f"SELECT SUM(amount) FROM {table_name}").first()[0]
    trino_sum = trino_query(f"SELECT SUM(amount) FROM {table_name}")
    
    assert abs(spark_sum - trino_sum) < 0.01, \
        f"Sum mismatch: Spark={spark_sum}, Trino={trino_sum}"
```

---

## Summary: Operations, Maintenance & Cost Issues

| # | Issue | Severity | Key Fix |
|---|-------|----------|---------|
| 87 | Maintenance competing with production | P1 | Isolated compute + scheduling |
| 88 | Thousands of abandoned tables | P2 | Lifecycle management + governance |
| 89 | No cost attribution | P2 | Per-table cost tracking + chargeback |
| 90 | Data quality undetected for days | P0 | Automated validation on every commit |
| 91 | Library version mismatch | P1 | Org-wide BOM + coordinated upgrades |
| 92 | Runaway job consuming cluster | P0 | Resource limits + queue isolation |
| 93 | Migration fails at scale | P1 | Parallel migration + in-place snapshot |
| 94 | Accidental DROP TABLE | P0 | Soft-delete + catalog backup + IAM |
| 95 | Storage growth surprise | P2 | Capacity planning with multipliers |
| 96 | No rollback for bad writes | P1 | Snapshot rollback + cherry-pick revert |
| 97 | Cannot test without production impact | P2 | Nessie branches for testing |
| 98 | Compliance audit fails | P1 | Iceberg time travel + lineage metadata |
| 99 | Table becomes unmaintainable | P0 | Progressive recovery + never skip maintenance |
| 100 | Multi-engine inconsistency | P1 | Standardized config + cross-engine tests |

---

## Final Summary: All 100 Issues by Category

| Category | Issues | P0 Count | P1 Count | P2 Count | P3 Count |
|----------|--------|----------|----------|----------|----------|
| Metadata & Catalog | #1-15 | 3 | 8 | 4 | 0 |
| Small Files & Compaction | #16-30 | 1 | 6 | 6 | 2 |
| Concurrency & Write Conflicts | #31-45 | 5 | 8 | 2 | 0 |
| S3 Storage Layer | #46-58 | 3 | 4 | 5 | 1 |
| Query Performance | #59-72 | 0 | 5 | 9 | 0 |
| Streaming & CDC | #73-86 | 2 | 11 | 1 | 0 |
| Operations & Cost | #87-100 | 4 | 5 | 5 | 0 |
| **TOTAL** | **100** | **18** | **47** | **32** | **3** |

### Key Takeaways

```
Top 5 Prevention Strategies (addresses 80% of issues):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. SCHEDULED MAINTENANCE (prevents #1,3,5,6,16,17,19,27,99)
   → Automate: expire_snapshots + compaction + orphan cleanup
   → Run on EVERY table, not just "when someone remembers"
   
2. SINGLE WRITER PER TABLE (prevents #31,32,34,36,40,41,45)
   → Design for partition-isolated or fan-in write patterns
   → Never have concurrent writers to same partition
   
3. RESOURCE ISOLATION (prevents #28,46,87,92)
   → Separate compute for maintenance vs production
   → S3 prefix distribution for hot tables
   
4. MONITORING + ALERTS (prevents #8,19,49,77,90,95)
   → Track: file count, snapshot count, freshness, costs
   → Alert BEFORE issues become critical (trending alerts)
   
5. GOVERNANCE (prevents #13,88,89,91,94,98)
   → Table ownership, naming conventions, lifecycle policies
   → IAM controls, catalog RBAC, deployment automation
```
