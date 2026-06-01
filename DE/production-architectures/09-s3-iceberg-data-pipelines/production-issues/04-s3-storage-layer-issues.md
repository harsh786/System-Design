# S3 Storage Layer Issues (#46-58)

Issues specific to S3 as the storage backend for Iceberg tables, including throttling,
consistency, cost, and operational challenges.

---

## Issue #46: S3 503 SlowDown Throttling

**Severity:** P0 - Critical
**Frequency:** Weekly on high-throughput tables
**Affected Components:** All reads/writes to affected prefix
**First seen at:** Any deployment with >3500 PUT/s or >5500 GET/s per prefix

### Symptoms
```
- AmazonS3Exception: 503 Slow Down
- Intermittent S3 failures during peak writes
- Query timeouts (S3 reads failing with retries)
- Compaction jobs fail at 70% completion
- Flink checkpoint failures (S3 write throttled)
```

### Root Cause
```
S3 rate limits per PREFIX (first 6 characters after bucket):

  PUT/COPY/POST/DELETE: 3,500 requests/second/prefix
  GET/HEAD: 5,500 requests/second/prefix

  Iceberg default layout:
    s3://bucket/database/table/data/00001.parquet
    s3://bucket/database/table/data/00002.parquet
    
  ALL files share prefix: "databa" (first 6 chars of "database/...")
  
  With compaction reading 1000 files + writing 50 files:
    Reads: 1000 GET in 10 seconds = 100/s (fine)
    During peak: 100 concurrent queries × 50 files each = 5000 GET/s → THROTTLED
    
  With streaming: 100 Flink tasks × 60 commits/hour × 1 PUT each:
    = 6000 PUT/hour = ~2 PUT/s (fine individually)
    But bulk operations (compaction, backfill): 1000 PUTs in 5 seconds → THROTTLED
```

### Immediate Fix
```python
# Enable S3 request retries with backoff
spark.conf.set("spark.hadoop.fs.s3a.retry.limit", "20")
spark.conf.set("spark.hadoop.fs.s3a.retry.interval", "500ms")
spark.conf.set("spark.hadoop.fs.s3a.attempts.maximum", "20")

# Reduce parallelism during throttling
spark.conf.set("spark.sql.shuffle.partitions", "50")  # Fewer concurrent S3 ops
```

### Permanent Fix
```
1. Randomize S3 key prefixes (spread across partitions):
   Instead of: s3://bucket/db/table/data/00001.parquet
   Use:        s3://bucket/db/table/data/a3f2/00001.parquet (hash prefix)
   
   Iceberg table property:
   'write.object-storage.enabled' = 'true'  -- Randomizes prefixes automatically
   
2. Use S3 Express One Zone (10x higher request rates):
   - 100,000 requests/second (not 3,500)
   - Single AZ (trade durability for performance)
   - Good for hot tables, keep cold data on standard S3
   
3. Spread tables across multiple buckets:
   - Hot streaming tables: dedicated bucket
   - Cold analytical tables: shared bucket
   
4. Use S3 Access Points to distribute load
```

```properties
# Enable object storage mode (randomized prefixes)
write.object-storage.enabled = true
write.object-storage.path = s3://bucket/warehouse
write.data.path = s3://bucket/warehouse/data  # Separate from metadata path
```

### Prevention
```
- Enable write.object-storage.enabled=true for all new tables
- Monitor S3 request rates with CloudWatch (503 error metric)
- Alert at 70% of rate limit (warn before throttle)
- Separate hot tables into dedicated buckets
- Use exponential backoff in all S3 clients
```

---

## Issue #47: S3 Eventual Consistency Causing Stale Reads (Pre-2020 Issue, Still Relevant)

**Severity:** P1 - High
**Frequency:** Rare (S3 is strongly consistent since Dec 2020)
**Affected Components:** Read correctness in edge cases
**First seen at:** During S3 regional failovers and with CDN caching

### Symptoms
```
- Newly written file returns 404 for brief period
- S3 LIST doesn't show recently created file
- Query reads stale version of metadata file
- Cross-region replication lag causes inconsistency
- CloudFront/CDN caching returns old S3 objects
```

### Root Cause
```
S3 has been strongly consistent since Dec 2020. However:

1. S3 Cross-Region Replication (CRR) is EVENTUALLY consistent:
   - Write to us-east-1 → read from eu-west-1 may be stale (lag: seconds to minutes)
   
2. CDN/Proxy caching:
   - CloudFront caches S3 objects (TTL-based)
   - VPC endpoints may cache DNS/routing

3. S3 Transfer Acceleration edge cases:
   - Route through CloudFront → potential caching

4. During S3 infrastructure events:
   - Regional failover can briefly show stale data
   - Extremely rare but has happened
```

### Permanent Fix
```
1. For multi-region: route all metadata reads to primary region
2. Disable CDN for Iceberg metadata paths
3. Use S3 versioning + version ID for reads (not just key)
4. For CRR: read-after-write only from primary region
5. Don't use S3 Transfer Acceleration for Iceberg metadata
```

---

## Issue #48: S3 DELETE Rate Limiting During Orphan Cleanup

**Severity:** P2 - Medium
**Frequency:** During large orphan cleanup operations
**Affected Components:** Cleanup job duration, S3 costs
**First seen at:** Tables with millions of orphan files

### Symptoms
```
- remove_orphan_files takes 12+ hours (expected: 1 hour)
- S3 delete throttling: 503 errors during cleanup
- Cleanup job OOM (listing millions of files)
- Progress: deleted 10K files/hour (have 5M to delete)
- Blocking other operations due to S3 rate limit consumption
```

### Root Cause
```
Orphan cleanup requires:
  1. LIST all files in data/ directory (can be millions)
  2. Collect all referenced files from current metadata
  3. Compute difference (orphan = exists on S3 but not in metadata)
  4. DELETE each orphan file individually
  
  For a table with 5M orphan files:
    LIST: 5000 LIST requests (1000 objects per request) = $0.025
    Memory: 5M file paths in memory = ~500MB
    DELETE: 5M delete requests at 3500/s/prefix = 24 minutes minimum
    But with rate limiting and retries: 2-12 hours
    
  S3 batch delete: max 1000 objects per request
    5M / 1000 = 5000 batch delete requests
    Still limited by 3500 requests/s/prefix
```

### Permanent Fix
```python
# Use S3 batch delete with parallelism across prefixes
import boto3
from concurrent.futures import ThreadPoolExecutor

def fast_orphan_delete(bucket, orphan_keys, max_workers=20):
    """Delete orphan files using batch operations across threads."""
    s3 = boto3.client('s3')
    
    # Group by prefix for parallel deletion
    prefix_groups = {}
    for key in orphan_keys:
        prefix = key[:6]  # First 6 chars (S3 partition key)
        prefix_groups.setdefault(prefix, []).append(key)
    
    def delete_batch(keys):
        # S3 allows 1000 deletes per request
        for i in range(0, len(keys), 1000):
            batch = keys[i:i+1000]
            s3.delete_objects(
                Bucket=bucket,
                Delete={'Objects': [{'Key': k} for k in batch]}
            )
    
    # Parallel deletion across different prefixes
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        executor.map(delete_batch, prefix_groups.values())
```

```
Additional strategies:
1. Use S3 Lifecycle rules for files older than N days in specific prefixes
2. Run cleanup during off-peak hours (less S3 competition)
3. Chunk cleanup: delete 100K per run, not 5M at once
4. Use write.object-storage.enabled (spreads across prefixes, avoids single-prefix limit)
```

---

## Issue #49: S3 Storage Costs Exploding (10x Expected)

**Severity:** P2 - Medium
**Frequency:** Ongoing (grows without monitoring)
**Affected Components:** AWS bill, budget overruns
**First seen at:** After 6 months of operations without cost governance

### Symptoms
```
- S3 bill: $500K/month (expected: $50K)
- Storage growing faster than data growth (duplicates from compaction)
- Metadata storage significant (10-20% of total)
- Previous versions of files not being cleaned up
- Multipart upload fragments accumulating
```

### Root Cause
```
Multiple factors compound:

1. Orphan files (never cleaned): +30-50% storage
2. Historical snapshots (all data versions retained): +100-200%
3. Compaction doubles storage temporarily: +100% peak
4. Aborted multipart uploads: +5-10%
5. Metadata files (not expired): +5-20%
6. Delete files (MoR) accumulating: +10-30%
7. Wrong storage class (all data in STANDARD, even cold): +200% vs lifecycle

Combined: 50TB actual data → 200TB S3 storage → $4600/month vs $1150/month
```

### Permanent Fix
```json
// S3 Lifecycle Policy (apply to all Iceberg buckets)
{
  "Rules": [
    {
      "ID": "abort-multipart-uploads",
      "Filter": {},
      "Status": "Enabled",
      "AbortIncompleteMultipartUpload": {"DaysAfterInitiation": 1}
    },
    {
      "ID": "transition-old-data-to-ia",
      "Filter": {"Prefix": "warehouse/"},
      "Status": "Enabled",
      "Transitions": [
        {"Days": 90, "StorageClass": "STANDARD_IA"},
        {"Days": 365, "StorageClass": "GLACIER_IR"}
      ]
    },
    {
      "ID": "delete-old-metadata",
      "Filter": {"Prefix": "warehouse/", "Tags": [{"Key": "iceberg-type", "Value": "metadata"}]},
      "Status": "Enabled",
      "Expiration": {"Days": 30}
    }
  ]
}
```

```python
# Cost dashboard: track storage per table
def calculate_table_costs(table_name):
    files = spark.sql(f"SELECT * FROM prod.{table_name}.files")
    total_bytes = files.agg({"file_size_in_bytes": "sum"}).first()[0]
    
    # S3 Standard: $0.023/GB/month
    monthly_cost = (total_bytes / 1024**3) * 0.023
    return monthly_cost
```

---

## Issue #50: S3 Access Denied After IAM Policy Change

**Severity:** P0 - Critical
**Frequency:** During infrastructure changes
**Affected Components:** All table operations immediately
**First seen at:** After IAM role rotation, policy update, or account migration

### Symptoms
```
- AccessDeniedException: Access Denied for all Iceberg operations
- Queries fail: "Unable to read file s3://bucket/..."
- Writes fail: "Unable to write to s3://bucket/..."
- Compaction, maintenance, queries ALL fail simultaneously
- Error appears suddenly (was working minutes ago)
```

### Root Cause
```
Iceberg needs MULTIPLE S3 permissions:

  Read operations: s3:GetObject, s3:ListBucket
  Write operations: s3:PutObject, s3:DeleteObject
  Metadata operations: s3:GetObject, s3:PutObject on metadata/
  Compaction: s3:GetObject (read) + s3:PutObject (write) + s3:DeleteObject (cleanup)
  
  Common causes:
  1. IAM role rotation: new role doesn't have Iceberg-specific permissions
  2. Bucket policy change: removed cross-account access
  3. Lake Formation permissions: table-level permission revoked
  4. VPC endpoint policy: restricts S3 access
  5. SCP (Service Control Policy): org-level restriction
  6. S3 Object Ownership change: ACLs disabled, breaks cross-account
  
  Minimum IAM for Iceberg:
  s3:GetObject, s3:PutObject, s3:DeleteObject, s3:ListBucket,
  s3:GetBucketLocation, s3:AbortMultipartUpload, s3:ListMultipartUploadParts
```

### Immediate Fix
```json
// Emergency IAM policy (full Iceberg access)
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject",
        "s3:ListBucket",
        "s3:GetBucketLocation",
        "s3:AbortMultipartUpload",
        "s3:ListMultipartUploadParts"
      ],
      "Resource": [
        "arn:aws:s3:::iceberg-bucket",
        "arn:aws:s3:::iceberg-bucket/*"
      ]
    }
  ]
}
```

### Prevention
```
- Terraform-managed IAM (all changes via PR review)
- Separate IAM roles for: readers, writers, maintenance (blast radius)
- Test IAM changes in staging before production
- Monitor S3 403 errors in CloudTrail (alert on first occurrence)
- IAM policy CI/CD: validate Iceberg permissions before deploy
```

---

## Issue #51: S3 Multipart Upload Fragments (Ghost Storage)

**Severity:** P3 - Low (but expensive over time)
**Frequency:** Ongoing (accumulates silently)
**Affected Components:** Storage costs only
**First seen at:** After months of operation with job failures

### Symptoms
```
- S3 storage reported higher than sum of all visible objects
- S3 billing shows "incomplete multipart uploads" line item
- aws s3api list-multipart-uploads returns thousands of entries
- Storage cost higher than expected based on file sizes
- Each failed Spark/Flink write leaves fragments
```

### Root Cause
```
S3 multipart upload for files > 5MB:
  1. Initiate multipart upload (creates upload ID)
  2. Upload parts (5MB-5GB each)
  3. Complete multipart upload (assembles parts into object)
  
  If step 3 never happens (job crash, OOM, timeout):
    → Parts remain on S3 FOREVER (billed as storage)
    → Not visible in normal LIST operations
    → Only visible via list-multipart-uploads API
    
  At scale with daily job failures:
    100 failed jobs/day × 10 files each × 128MB = 128GB/day of fragments
    Over 1 year: 46TB of invisible storage waste!
```

### Fix
```json
// S3 Lifecycle rule (MANDATORY for all Iceberg buckets)
{
  "Rules": [{
    "ID": "abort-incomplete-multipart",
    "Filter": {},
    "Status": "Enabled",
    "AbortIncompleteMultipartUpload": {
      "DaysAfterInitiation": 1
    }
  }]
}
```

---

## Issue #52: S3 Cross-Region Replication Lag Breaking DR Reads

**Severity:** P1 - High
**Frequency:** During failover or when reading from replica region
**Affected Components:** DR queries, read replicas
**First seen at:** Multi-region deployments using CRR for DR

### Symptoms
```
- Queries in DR region fail: "File not found" for recently written files
- Metadata file points to data files that haven't replicated yet
- Replication lag: 15 minutes during normal operation, 2+ hours during peak
- DR region shows table state from 30 minutes ago
- Failover to DR results in data loss (un-replicated commits)
```

### Root Cause
```
S3 CRR replication order is NOT guaranteed:

  Primary region writes:
    T0: data-file-001.parquet (written to S3)
    T1: manifest-001.avro (references data-file-001)
    T2: metadata.json (references manifest-001)
    T3: Catalog updated (points to metadata.json)
    
  CRR replicates in ARBITRARY order:
    T0+5s: metadata.json arrives in DR region
    T0+10s: manifest-001.avro arrives
    T0+30s: data-file-001.parquet arrives
    
  Between T0+5s and T0+30s:
    DR region has metadata → manifest → but data file MISSING
    Query in DR: "FileNotFoundException: data-file-001.parquet"
    
  Metadata arrives before data it references = broken reads
```

### Permanent Fix
```
1. Reverse-order verification:
   - Don't update DR catalog until ALL data files are replicated
   - Use S3 event notifications to track replication completion
   
2. Stale catalog in DR:
   - DR catalog points to metadata from 1 hour ago (guaranteed replicated)
   - Accept 1-hour RPO for DR reads
   
3. DR-specific maintenance:
   - Run verification job in DR: check all referenced files exist
   - Only advance DR catalog pointer after verification passes
   
4. Use S3 Replication Time Control (S3 RTC):
   - 99.99% of objects replicated within 15 minutes
   - SLA-backed replication timing
   - Costs more but provides guarantees
```

---

## Issue #53: S3 Prefix Hotspotting (All Files Under Same Prefix)

**Severity:** P1 - High
**Frequency:** On tables without object-storage-mode
**Affected Components:** Read/write throughput
**First seen at:** Tables with millions of files in flat directory structure

### Symptoms
```
- S3 LIST takes 30+ seconds (millions of objects in one prefix)
- Random S3 500 errors during peak operations
- Performance varies wildly (S3 internal rebalancing)
- New table performs well, degrades over months
- Some queries fast, others slow (depends on S3 partition assignment)
```

### Root Cause
```
Default Iceberg layout puts all data files under:
  s3://bucket/db/table/data/

S3 internally partitions by key prefix.
If millions of files share the same prefix → single S3 partition → hot spot.

S3 automatically repartitions (splits) but:
  - Detection takes time (hours/days of sustained high load)
  - During split: performance degraded
  - Split is based on request pattern, not file count
  
With default layout and 10M files:
  All under "db/table/data/" → single prefix partition
  Any burst exceeding 5500 GET/s → throttled
```

### Permanent Fix
```sql
-- Enable object storage layout (randomized prefixes)
ALTER TABLE db.table SET TBLPROPERTIES (
  'write.object-storage.enabled' = 'true'
);

-- Result: files distributed across many prefixes
-- Before: s3://bucket/db/table/data/00001.parquet
-- After:  s3://bucket/db/table/data/a3f2/b891/00001.parquet
--         s3://bucket/db/table/data/7c4e/d123/00002.parquet
```

---

## Issue #54: S3 Versioning Conflicts with Iceberg Snapshot Expiry

**Severity:** P2 - Medium
**Frequency:** When S3 versioning is enabled on Iceberg buckets
**Affected Components:** Storage costs, confusion
**First seen at:** Regulated environments requiring S3 versioning

### Symptoms
```
- After expire_snapshots + remove_orphan_files: storage doesn't decrease
- S3 shows "delete markers" instead of actual deletions
- Storage continues growing despite cleanup operations
- aws s3api list-object-versions shows all "deleted" files still present
- Compliance team mandated S3 versioning but it conflicts with Iceberg
```

### Root Cause
```
S3 versioning + Iceberg is fundamentally conflicting:

  Iceberg cleanup: DeleteObject on orphan file
  With S3 versioning: Delete creates "delete marker" (file still exists as version!)
  
  Result: Files are NEVER actually deleted
  → Storage grows indefinitely regardless of Iceberg maintenance
  → Both Iceberg AND S3 retain all versions (redundant)
  
  Storage math:
    Table: 100TB active data
    Iceberg retains 7 days of snapshots: ~100TB (some overlap)
    S3 versioning retains ALL versions: 500TB+ (every file ever written)
    Total: 500TB instead of 100TB = 5x cost
```

### Fix
```
1. Use Iceberg time travel INSTEAD of S3 versioning:
   - Iceberg already provides point-in-time recovery
   - S3 versioning is redundant and expensive
   - Disable versioning on Iceberg data buckets
   
2. If versioning required (compliance):
   - Add S3 Lifecycle rule to expire old versions:
     NoncurrentVersionExpiration: {NoncurrentDays: 7}
   - Set to match Iceberg snapshot retention
   
3. Separate buckets:
   - Non-versioned bucket for Iceberg data (Iceberg handles versioning)
   - Versioned bucket for other compliance data
```

---

## Issue #55: S3 Select/Glacier Retrieval Failures for Archived Data

**Severity:** P2 - Medium
**Frequency:** When querying data transitioned to Glacier/Deep Archive
**Affected Components:** Queries on historical data
**First seen at:** After S3 lifecycle transitions Iceberg files to Glacier

### Symptoms
```
- Query fails: "InvalidObjectState: Object is in GLACIER storage class"
- Historical queries (>90 days) suddenly fail
- Iceberg doesn't know about S3 storage classes
- Restore requests required before query (12-48 hour delay)
- S3 lifecycle transitioned files without Iceberg knowledge
```

### Root Cause
```
S3 Lifecycle rules are EXTERNAL to Iceberg:

  Lifecycle rule: Transition objects older than 90 days to GLACIER
  
  Iceberg metadata still references these files normally.
  When query needs the file:
    Iceberg: "Read s3://bucket/db/table/data/old-file.parquet"
    S3: "This object is in GLACIER, must restore first (12-48 hours)"
    Query: FAILS immediately
    
  Iceberg has no concept of S3 storage classes.
  It assumes all referenced files are instantly readable.
```

### Permanent Fix
```
1. Don't use Glacier on Iceberg data directories:
   - Use Iceberg's own archival patterns (separate tables for cold data)
   - Lifecycle rules only on KNOWN non-referenced data
   
2. Use S3 Intelligent-Tiering (NO retrieval cost/delay):
   - Automatically moves to cheaper tiers
   - Still instantly accessible
   - Best for Iceberg (no behavior change)
   
3. If must use Glacier: partition hot/cold data:
   - Hot table: recent data (no lifecycle)
   - Cold table: archived data (Glacier OK, queries pre-plan restores)
   
4. Archive pattern:
   - Move old partitions to separate "archive" Iceberg table
   - Apply Glacier only to archive table
   - Archive queries know to pre-restore
```

---

## Issue #56: S3 Request Costs Exceed Storage Costs

**Severity:** P2 - Medium
**Frequency:** On tables with millions of small files queried frequently
**Affected Components:** AWS bill structure
**First seen at:** Tables with many files + many queries + no compaction

### Symptoms
```
- S3 bill breakdown: Storage $10K, Requests $50K (requests 5x more!)
- Each Athena query costs $0.50+ in S3 requests alone
- LIST requests dominate cost (planning phase)
- Small files = more requests per byte of data read
- Moving to larger instances doesn't help (S3 cost is external)
```

### Root Cause
```
S3 request pricing:
  PUT/POST/COPY/DELETE: $5.00 per 1M requests
  GET/SELECT: $0.40 per 1M requests
  LIST: $5.00 per 1M requests
  
Table with 1M small files, queried 100 times/day:
  Planning (LIST manifests + GET manifests): 10K requests/query
  Execution (GET data files): 1M requests/query (1 per file!)
  
  Daily: 100 queries × 1.01M requests = 101M requests
  Monthly: 3B requests
  Cost: 3B GET × $0.40/1M = $1,200/month in REQUESTS ALONE
  
  Same table compacted to 10K files (128MB each):
  Daily: 100 queries × 10K requests = 1M requests  
  Monthly: 30M requests
  Cost: 30M GET × $0.40/1M = $12/month
  
  Compaction saves: $1,200 → $12 = 99% reduction in request costs
```

### Fix
```
1. COMPACT (most impactful): reduce file count by 100x
2. Use S3 Express One Zone for hot tables (different pricing)
3. Use manifest caching (fewer LIST/GET for metadata)
4. Use predicate pushdown (read fewer files per query)
5. Enable S3 request metrics to track per-table costs
6. Budget alert: S3 requests > $X/table/day
```

---

## Issue #57: VPC Endpoint Throttling for S3 Access

**Severity:** P1 - High
**Frequency:** In private VPC deployments without proper sizing
**Affected Components:** All S3 operations from VPC
**First seen at:** On-prem to AWS (VPN) or private subnet deployments

### Symptoms
```
- S3 operations slow from EMR/EKS (5x slower than expected)
- Timeouts connecting to S3 from private subnets
- Network bandwidth to S3 saturated
- Not S3 throttling (no 503), but network-level slowness
- Same queries fast from public subnet, slow from private
```

### Root Cause
```
S3 Gateway VPC Endpoint:
  - Free, routes traffic through VPC gateway
  - No bandwidth limit (uses S3 infrastructure directly)
  - BUT: requires specific route table configuration
  
S3 Interface VPC Endpoint (PrivateLink):
  - Costs per ENI per hour + per GB processed
  - BANDWIDTH LIMITED by ENI sizing
  - Default: 10 Gbps per ENI
  - Large clusters easily saturate this
  
Common issues:
  - Missing S3 gateway endpoint → traffic goes through NAT Gateway (expensive + limited)
  - NAT Gateway: 45 Gbps max, $0.045/GB processed
    Compaction reading 10TB: $450 in NAT Gateway data processing alone!
  - Interface endpoint: limited ENI bandwidth
```

### Permanent Fix
```hcl
# Terraform: S3 Gateway Endpoint (free, unlimited bandwidth)
resource "aws_vpc_endpoint" "s3_gateway" {
  vpc_id       = aws_vpc.main.id
  service_name = "com.amazonaws.${var.region}.s3"
  vpc_endpoint_type = "Gateway"
  
  route_table_ids = [
    aws_route_table.private_a.id,
    aws_route_table.private_b.id,
    aws_route_table.private_c.id,
  ]
}

# IMPORTANT: Gateway endpoint for data path (free)
# Interface endpoint only if need DNS resolution from on-prem
```

---

## Issue #58: S3 Object Lock Preventing Iceberg File Operations

**Severity:** P0 - Critical
**Frequency:** After enabling S3 Object Lock for compliance
**Affected Components:** All write/delete operations
**First seen at:** Compliance-mandated immutable storage

### Symptoms
```
- Compaction fails: "Access Denied" when trying to delete old files
- expire_snapshots runs but orphan cleanup fails
- remove_orphan_files: "Object is locked and cannot be deleted"
- Storage grows without bound (can never delete anything)
- Table becomes un-maintainable over time
```

### Root Cause
```
S3 Object Lock (WORM compliance):
  GOVERNANCE mode: can override with special permission
  COMPLIANCE mode: NOBODY can delete (not even root) until retention expires
  
  With Iceberg maintenance:
    Compaction creates new files → tries to eventually delete old files
    Object Lock: "Cannot delete, retention not expired"
    → Old files accumulate forever
    → Storage grows linearly without any cleanup possible
    
  This is fundamentally incompatible with Iceberg's maintenance model.
```

### Permanent Fix
```
1. DON'T use Object Lock on Iceberg data buckets:
   - Iceberg's own snapshots provide audit trail
   - Time travel = immutable history without Object Lock
   
2. If compliance requires immutability:
   - Use GOVERNANCE mode (allows override with specific IAM permission)
   - Set short retention (7-30 days) matching Iceberg snapshot retention
   - Maintenance roles have s3:BypassGovernanceRetention permission
   
3. Hybrid approach:
   - Iceberg data bucket: NO Object Lock (Iceberg manages lifecycle)
   - Audit bucket: Object Lock (export audit snapshots here periodically)
   - Compliance met via audit exports, not data bucket locking

4. Use Iceberg snapshot retention as compliance mechanism:
   history.expire.min-snapshots-to-keep = 365
   → 365 snapshots = complete audit trail without Object Lock
```

---

## Summary: S3 Storage Layer Issues

| # | Issue | Severity | Key Fix |
|---|-------|----------|---------|
| 46 | S3 503 SlowDown throttling | P0 | object-storage.enabled + prefix distribution |
| 47 | Eventual consistency (CRR lag) | P1 | DR catalog lag + RTC |
| 48 | DELETE rate limiting during cleanup | P2 | Batch delete + lifecycle rules |
| 49 | Storage costs exploding | P2 | Lifecycle rules + aggressive cleanup |
| 50 | Access Denied after IAM change | P0 | Terraform IAM + monitoring 403s |
| 51 | Multipart upload fragments | P3 | AbortIncompleteMultipartUpload lifecycle |
| 52 | CRR lag breaking DR reads | P1 | Delayed catalog pointer + RTC |
| 53 | Prefix hotspotting | P1 | object-storage.enabled |
| 54 | S3 versioning conflicts | P2 | Disable versioning or set NoncurrentExpiry |
| 55 | Glacier retrieval failures | P2 | S3 Intelligent-Tiering |
| 56 | Request costs > storage costs | P2 | Compaction (reduce file count) |
| 57 | VPC endpoint throttling | P1 | S3 Gateway endpoint (not Interface) |
| 58 | Object Lock prevents maintenance | P0 | Don't lock Iceberg data buckets |
