# Problem 3: IoT Sensor Data Pipeline (Manufacturing)

## Problem 3: IoT Sensor Data Pipeline (Manufacturing)

### Business Context
Smart factory with 100,000 sensors reporting every second. Need real-time anomaly 
detection + historical analysis for predictive maintenance.

### Architecture
```
┌─────────────────────────────────────────────────────────────────────────────┐
│              IoT SENSOR DATA PIPELINE ARCHITECTURE                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  EDGE LAYER                                                                  │
│  ┌────────────────────────────────────────────────────────────────┐         │
│  │  100,000 Sensors → Edge Gateways (100 units)                    │         │
│  │                                                                 │         │
│  │  WHY EDGE PROCESSING:                                           │         │
│  │  • 100K sensors × 1 msg/sec × 500 bytes = 50 MB/s raw          │         │
│  │  • Can't send ALL data to cloud (bandwidth + cost)              │         │
│  │  • Edge does: filtering, aggregation, compression               │         │
│  │  • Sends: 5 MB/s to cloud (10x reduction)                      │         │
│  │  • Local alerting: <10ms for critical thresholds                │         │
│  │                                                                 │         │
│  │  Each gateway: Raspberry Pi 4 / Jetson Nano                     │         │
│  │  Protocol: MQTT (lightweight, pub/sub, QoS levels)              │         │
│  └────────────────────────────────┬───────────────────────────────┘         │
│                                    │ 5 MB/s aggregated                       │
│  ┌─────────────────────────────────▼──────────────────────────────┐         │
│  │  INGESTION: AWS IoT Core / Kafka                                │         │
│  │                                                                 │         │
│  │  IoT Core → Kafka (bridge)                                      │         │
│  │  Topics:                                                        │         │
│  │  • sensors.temperature (partitioned by factory_zone)            │         │
│  │  • sensors.vibration                                            │         │
│  │  • sensors.pressure                                             │         │
│  │  • sensors.alerts (high priority, separate topic)               │         │
│  └──────────────────┬──────────────────────────────┬──────────────┘         │
│                      │                              │                         │
│  ┌───────────────────▼───────────┐  ┌──────────────▼──────────────┐         │
│  │  REAL-TIME: Flink             │  │  BATCH: Spark                │         │
│  │                               │  │                              │         │
│  │  • Anomaly detection          │  │  • Daily aggregations        │         │
│  │    (sliding window stats)     │  │  • ML model training         │         │
│  │  • Pattern matching           │  │  • Predictive maintenance    │         │
│  │    (CEP - Complex Event)      │  │  • Capacity planning         │         │
│  │  • Real-time dashboards       │  │  • Historical reports        │         │
│  │                               │  │                              │         │
│  │  Alert → PagerDuty/OpsGenie  │  │  Store → S3/Delta Lake       │          │
│  └───────────────────────────────┘  └─────────────────────────────┘         │
│                                                                              │
│  STORAGE STRATEGY (Time-Series Optimized):                                   │
│  ┌────────────────────────────────────────────────────────────────┐         │
│  │  Hot (0-24h): TimescaleDB / InfluxDB   → Fast dashboards       │         │
│  │  Warm (1-90d): Apache Druid            → Interactive analytics  │         │
│  │  Cold (90d+): S3 + Delta Lake          → ML training, audits   │         │
│  │                                                                 │         │
│  │  WHY TimescaleDB for hot:                                       │         │
│  │  • 100K inserts/sec                                             │         │
│  │  • Time-range queries optimized                                 │         │
│  │  • Continuous aggregation (auto-rollup)                         │         │
│  │  • PostgreSQL compatible (familiar SQL)                         │         │
│  │                                                                 │         │
│  │  WHY Delta Lake for cold:                                       │         │
│  │  • Cheap (S3 pricing: $0.023/GB)                                │         │
│  │  • Spark-native (ML training directly)                          │         │
│  │  • ACID (reliable historical data)                              │         │
│  │  • Time-travel (reproduce past analyses)                        │         │
│  └────────────────────────────────────────────────────────────────┘         │
│                                                                              │
│  DATA VOLUME CALCULATION:                                                    │
│  • Raw: 100K × 1/sec × 500B = 50 MB/s = 4.3 TB/day                         │
│  • After edge reduction: 500 GB/day                                          │
│  • After aggregation (1-min): 50 GB/day                                     │
│  • Hot storage: 50 GB × 1 day = 50 GB (fits in RAM)                         │
│  • Warm: 50 GB × 90 days = 4.5 TB (Druid cluster)                           │
│  • Cold: Infinite (S3 lifecycle to Glacier after 1 year)                     │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

