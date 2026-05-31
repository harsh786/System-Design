# Problem 99: Unified Batch + Stream Processing (Apache Beam)

### Problem 99: Unified Batch + Stream Processing (Apache Beam)
```
CONCEPT: Write once, run anywhere (batch OR stream, same code)
ARCH: Beam Pipeline → Runner (Flink for stream, Spark for batch)
WHY BEAM: Same business logic for both backfill (batch) and real-time (stream)
TRADE-OFF: Abstraction layer = less control over optimization
BEST FOR: Teams that need both modes and want single codebase
```
