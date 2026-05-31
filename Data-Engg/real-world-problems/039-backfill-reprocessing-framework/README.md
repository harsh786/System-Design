# Problem 39: Backfill & Reprocessing Framework

### Problem 39: Backfill & Reprocessing Framework
```
ARCH: Idempotent jobs + partition-level reprocessing + validation
PATTERN: Write to staging → validate → atomic swap to production
WHY IDEMPOTENT: Reprocessing same data must give same result
SCALE: Backfill 1 year of data = replay 365 daily partitions
```
