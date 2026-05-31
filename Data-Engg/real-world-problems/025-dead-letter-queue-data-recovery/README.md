# Problem 25: Dead Letter Queue & Data Recovery

### Problem 25: Dead Letter Queue & Data Recovery
```
SCALE: 1% error rate on 1M events/day = 10K failures to handle
ARCH: Main pipeline → DLQ (separate topic) → Retry logic → Alert
RETRY STRATEGY: Exponential backoff, max 3 retries, then manual queue
ROOT CAUSE: Schema errors (40%), downstream timeout (30%), data quality (30%)
```
