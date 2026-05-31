# Problem 18: Real-Time Pricing Engine

### Problem 18: Real-Time Pricing Engine
```
SCALE: 50K price updates/sec (stock market data)
ARCH: Exchange Feed → UDP multicast → FPGA parsing → Kafka → Flink → Redis
WHY FPGA: <10 microsecond parsing (software too slow)
WHY UDP: Lower latency than TCP for market data
```
