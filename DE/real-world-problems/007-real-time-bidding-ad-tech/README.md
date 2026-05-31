# Problem 7: Real-Time Bidding (Ad Tech)

### Problem 7: Real-Time Bidding (Ad Tech)
```
SCALE: 1M bid requests/sec, 50ms response budget
ARCH: Bid Request → Feature Lookup (Aerospike <1ms) → ML Score → Respond
WHY AEROSPIKE: Sub-ms reads at scale, SSD-optimized
SCALABILITY: 3000 bid servers, geo-distributed
```
