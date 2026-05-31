# Problem 79: Real-Time Supply Chain Optimization

### Problem 79: Real-Time Supply Chain Optimization
```
ARCH: IoT sensors + ERP CDC → Kafka → Flink (demand forecasting) → Optimizer
SCALE: 1M SKUs, 10K warehouses, 5-minute reoptimization cycle
WHY REAL-TIME: Stock-outs cost millions/day; faster response = less waste
ML: Demand forecasting (Prophet), route optimization (OR-Tools)
```
