# Problem 24: Slowly Changing Dimensions (SCD Type 2)

### Problem 24: Slowly Changing Dimensions (SCD Type 2)
```
SCALE: 100M customer records, 500K updates/day
ARCH: CDC → Flink → Iceberg (with versioned rows)
WHY SCD2: Full history (customer address changed → keep both)
IMPLEMENTATION: Surrogate keys, effective_from/to dates
```
