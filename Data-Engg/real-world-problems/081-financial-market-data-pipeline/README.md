# Problem 81: Financial Market Data Pipeline

### Problem 81: Financial Market Data Pipeline
```
ARCH: Exchange feed → FPGA parser → Kernel bypass → In-memory grid → Analytics
LATENCY: <10 microseconds (tick-to-trade)
WHY NOT KAFKA: Too slow for HFT (adds 1-5ms); use shared memory / LMAX Disruptor
ANALYTICS: End-of-day batch for risk calculations (Spark)
```
