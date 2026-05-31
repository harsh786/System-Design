# Problem 61: Streaming Deduplication with Bloom Filters

### Problem 61: Streaming Deduplication with Bloom Filters
```
CHALLENGE: Deduplicate 1 billion events/day (remembering all IDs = expensive)
BLOOM FILTER: Probabilistic. "Definitely not seen" or "probably seen"
FALSE POSITIVE RATE: 0.1% (1 in 1000 duplicates pass through)
MEMORY: 1 billion items at 0.1% FPR = ~1.2 GB (vs 30GB+ for hash set)
ROTATION: Time-windowed bloom filters (1 per hour, discard after 24h)
```
