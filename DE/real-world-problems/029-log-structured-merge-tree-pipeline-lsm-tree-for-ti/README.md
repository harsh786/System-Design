# Problem 29: Log-Structured Merge Tree Pipeline (LSM-Tree for Time-Series)

## Problem 29: Log-Structured Merge Tree Pipeline (LSM-Tree for Time-Series)

### Why LSM-Tree for Data Engineering?
```
THE INSIGHT: Most data engineering workloads are WRITE-HEAVY

Traditional B-Tree:
  • Random writes (slow on SSD, terrible on HDD)
  • Each write = disk seek
  • Good for reads, bad for writes

LSM-Tree (used by: RocksDB, Cassandra, HBase, LevelDB):
  • Sequential writes (fast on any storage)
  • Buffer writes in memory → flush to disk as sorted runs
  • Background compaction merges runs
  • PERFECT for: time-series, event logs, CDC sinks

DATA ENGINEERING USE:
  • Flink state backend (RocksDB)
  • Kafka storage engine
  • Time-series databases (InfluxDB, TimescaleDB)
  • Data lake compaction strategies
```

