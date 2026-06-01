# Top 100 Production Spark Issues at Scale

> Battle-tested solutions to the 100 most common production issues encountered when running Apache Spark at billion-record scale. Organized by category with root cause analysis, solutions, and decision trees.

---

## Quick Navigation

| File | Category | Issues | Most Critical |
|------|----------|--------|---------------|
| [01-memory-oom-issues.md](./01-memory-oom-issues.md) | Memory & OOM | #1-10 | Executor OOM, Driver OOM, GC Overhead |
| [02-shuffle-network-issues.md](./02-shuffle-network-issues.md) | Shuffle & Network | #11-20 | Fetch Failed, Data Skew, Network Saturation |
| [03-data-skew-partition-issues.md](./03-data-skew-partition-issues.md) | Data Skew & Partitions | #21-30 | Join Skew, Partition Pruning, Explosion |
| [04-streaming-issues.md](./04-streaming-issues.md) | Streaming | #31-40 | Lag, State Growth, Exactly-Once, Watermarks |
| [05-storage-io-issues.md](./05-storage-io-issues.md) | Storage & I/O | #41-50 | S3 Throttling, Small Files, Predicate Pushdown |
| [06-performance-query-optimization.md](./06-performance-query-optimization.md) | Performance & Query | #51-60 | Wrong Join, UDF Bottleneck, Codegen |
| [07-cluster-resource-management.md](./07-cluster-resource-management.md) | Cluster & Resources | #61-70 | Starvation, Spot Termination, Driver SPOF |
| [08-data-quality-correctness.md](./08-data-quality-correctness.md) | Data Quality | #71-80 | Silent Loss, Duplicates, Type Coercion |
| [09-deployment-operations.md](./09-deployment-operations.md) | Deployment & Ops | #81-90 | JAR Hell, Idempotency, Secret Exposure |
| [10-cost-scaling-issues.md](./10-cost-scaling-issues.md) | Cost & Scaling | #91-100 | Over-Provisioned, Spot Fallback, TCO |

---

## Top 10 Most Impactful Issues (Start Here)

| Rank | Issue | Why It Matters |
|------|-------|----------------|
| 1 | #13 - Shuffle Data Skew | Single skewed key makes 10-min job take 3 hours |
| 2 | #1 - Executor OOM During Shuffle | #1 cause of job failure at scale |
| 3 | #42 - Small Files Problem | 10-100x slower reads, cascading to all downstream |
| 4 | #31 - Streaming Falling Behind | Silent latency growth → eventual data loss |
| 5 | #17 - Partition Count Misconfiguration | Default 200 is wrong for 99% of production jobs |
| 6 | #54 - UDF Performance Bottleneck | 10-100x slower than built-in functions |
| 7 | #72 - Duplicate Records | Financial impact, trust erosion |
| 8 | #91 - Over-Provisioned Executors | 30-50% cost waste in most clusters |
| 9 | #25 - Partition Pruning Not Working | Reading 365x more data than needed |
| 10 | #34 - Exactly-Once Broken | Data correctness is non-negotiable |

---

## Issue Format

Each issue follows this structure:
- **Frequency**: How often this occurs in production
- **Severity**: Impact when it happens
- **Spark Component**: Which part of Spark is involved
- **Symptoms**: What you see (error messages, metrics, UI observations)
- **Root Cause**: Why it happens
- **Solution**: Code + configuration to fix it
- **Prevention Checklist**: How to prevent recurrence

---

## How to Use

1. **Incident response**: Search for your error message → find matching issue → apply solution
2. **Prevention**: Read all issues in your category → implement prevention checklists
3. **Interview prep**: Each issue is a real production scenario with deep technical answer
4. **Code review**: Check for anti-patterns listed in each issue
5. **Capacity planning**: Categories 7 and 10 cover resource and cost management

---

## Universal Quick Fixes (Apply to All Production Spark Jobs)

```python
# These 10 settings prevent 60% of production issues:
spark.conf.set("spark.sql.adaptive.enabled", "true")                    # Fixes: #13, #16, #17, #24
spark.conf.set("spark.sql.adaptive.skewJoin.enabled", "true")           # Fixes: #13, #21
spark.conf.set("spark.sql.adaptive.coalescePartitions.enabled", "true") # Fixes: #17, #24
spark.conf.set("spark.shuffle.service.enabled", "true")                 # Fixes: #11, #63, #99
spark.conf.set("spark.serializer", "org.apache.spark.serializer.KryoSerializer")  # Fixes: #60
spark.conf.set("spark.executor.memoryOverhead", "2g")                   # Fixes: #5, #8
spark.conf.set("spark.sql.files.maxPartitionBytes", "256MB")            # Fixes: #29, #42
spark.conf.set("spark.locality.wait", "0s")                             # Fixes: #30 (cloud only)
spark.conf.set("spark.dynamicAllocation.enabled", "true")               # Fixes: #91, #67
spark.conf.set("spark.sql.parquet.filterPushdown", "true")              # Fixes: #46
```
