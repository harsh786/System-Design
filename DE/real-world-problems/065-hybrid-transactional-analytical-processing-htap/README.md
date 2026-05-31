# Problem 65: Hybrid Transactional/Analytical Processing (HTAP)

### Problem 65: Hybrid Transactional/Analytical Processing (HTAP)
```
ARCH: TiDB / CockroachDB / AlloyDB (single system, both OLTP + OLAP)
WHY: No ETL delay between operational and analytical
HOW: Row store (OLTP) + Column store (OLAP) with real-time replication
TRADE-OFF: Jack of all trades; dedicated systems still win for extreme scale
USE CASE: SMB/mid-market where operational simplicity > absolute performance
```
