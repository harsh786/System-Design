# Problem 66: Streaming Aggregation with Retraction

### Problem 66: Streaming Aggregation with Retraction
```
PROBLEM: User updates profile → aggregation count changes
APPROACH: Retraction stream (emit -1 for old value, +1 for new value)
EXAMPLE: User moves from "NY" to "CA"
  → Emit: (NY, -1), (CA, +1) → count_by_state stays correct
IMPLEMENTATION: Flink handles retractions natively in SQL mode
```
