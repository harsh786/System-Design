# End-to-End Streaming Platform Architecture

## Complete Production Architecture for 1M+ events/sec

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                    PRODUCTION STREAMING PLATFORM                                    │
│                    (Handles 1M+ events/second)                                     │
├──────────────────────────────────────────────────────────────────────────────────┤
│                                                                                   │
│  ┌─────────────────────────────────────────────────────────────────────────────┐ │
│  │ SOURCES (Producers)                                                          │ │
│  │                                                                              │ │
│  │ [Mobile Apps] [Web SDKs] [IoT Devices] [Microservices] [Partner APIs]        │ │
│  │      ↓              ↓           ↓              ↓              ↓              │ │
│  │ [SDK Client]  [JS Tracker] [MQTT Bridge] [gRPC Client] [REST API]           │ │
│  │                                                                              │ │
│  │ Combined: 1M events/sec, avg 1KB each = 1 GB/s                               │ │
│  └──────────────────────────────────┬──────────────────────────────────────────┘ │
│                                      │                                            │
│  ┌───────────────────────────────────▼──────────────────────────────────────────┐│
│  │ INGESTION GATEWAY                                                             ││
│  │                                                                               ││
│  │ Load Balancer (AWS ALB/NLB)                                                   ││
│  │    ↓                                                                          ││
│  │ API Gateway Fleet (100 pods, auto-scaled)                                     ││
│  │    • Authentication (API key / JWT)                                           ││
│  │    • Rate limiting (per-client token bucket)                                  ││
│  │    • Schema validation (lightweight, reject malformed)                        ││
│  │    • Batching (collect 100 events, single Kafka produce)                      ││
│  │    • Circuit breaker (if Kafka unavailable → buffer to disk)                  ││
│  │                                                                               ││
│  │ WHY API GATEWAY (not direct Kafka produce):                                   ││
│  │    • Clients don't need Kafka client libraries                                ││
│  │    • Protocol translation (HTTP/gRPC → Kafka)                                 ││
│  │    • Central auth/rate limiting                                                ││
│  │    • Schema validation before Kafka (save storage)                            ││
│  └───────────────────────────────────┬──────────────────────────────────────────┘│
│                                       │                                           │
│  ┌────────────────────────────────────▼─────────────────────────────────────────┐│
│  │ KAFKA CLUSTER (Event Bus)                                                     ││
│  │                                                                               ││
│  │ Cluster: 30 brokers, 3 AZs (10 per AZ)                                       ││
│  │ Hardware: m5.4xlarge (16 vCPU, 64GB RAM, 2x1TB NVMe SSD)                     ││
│  │                                                                               ││
│  │ Topics:                                                                       ││
│  │ ┌─────────────────────────────────────────────────────────────────┐          ││
│  │ │ events.raw        : 200 partitions, RF=3, retention=7d          │          ││
│  │ │ events.enriched   : 200 partitions, RF=3, retention=3d          │          ││
│  │ │ events.dead-letter: 10 partitions, RF=3, retention=30d          │          ││
│  │ │ events.alerts     : 20 partitions, RF=3, retention=7d           │          ││
│  │ └─────────────────────────────────────────────────────────────────┘          ││
│  │                                                                               ││
│  │ Performance:                                                                  ││
│  │ • Write: 1 GB/s sustained (30 brokers × 100MB/s each, 30% utilization)       ││
│  │ • Read: 3 GB/s (multiple consumer groups)                                     ││
│  │ • Latency: <5ms produce ack (acks=all, 3 replicas)                           ││
│  │                                                                               ││
│  │ Tiered Storage:                                                               ││
│  │ • Hot (SSD): Last 24 hours (high-throughput reads)                            ││
│  │ • Warm (S3): 1-7 days (for consumer catchup/replay)                          ││
│  │ • Archive (S3 IA): 7-30 days (for investigation/compliance)                  ││
│  └───────────────┬──────────────────────────────────────┬───────────────────────┘│
│                   │                                      │                        │
│  ┌────────────────▼─────────────────┐  ┌────────────────▼──────────────────────┐│
│  │ STREAM PROCESSING (Flink)        │  │ STREAM PROCESSING (Flink)             ││
│  │ Job: Event Enrichment            │  │ Job: Real-Time Analytics              ││
│  │                                   │  │                                       ││
│  │ Cluster: 50 TaskManagers          │  │ Cluster: 30 TaskManagers              ││
│  │ Parallelism: 200                  │  │ Parallelism: 120                      ││
│  │ State: 500GB (RocksDB)           │  │ State: 200GB (RocksDB)                ││
│  │ Checkpoints: 60s, incremental    │  │ Checkpoints: 60s                      ││
│  │                                   │  │                                       ││
│  │ Operations:                       │  │ Operations:                           ││
│  │ • User profile lookup (Redis)    │  │ • Tumbling windows (1min, 5min, 1hr)  ││
│  │ • Geo-IP enrichment              │  │ • Session windows (30min gap)         ││
│  │ • Device fingerprinting          │  │ • Sliding windows (rate calculation)  ││
│  │ • Event deduplication            │  │ • TopN computation                    ││
│  │ • Schema normalization           │  │ • Anomaly detection                   ││
│  │                                   │  │                                       ││
│  │ Output: events.enriched topic    │  │ Output: Pinot + Redis + Alerts        ││
│  └───────────────────────────────────┘  └──────────────────────────────────────┘│
│                                                                                   │
│  ┌─────────────────────────────────────────────────────────────────────────────┐ │
│  │ SERVING LAYER                                                                │ │
│  │                                                                              │ │
│  │ ┌───────────────┐  ┌───────────────┐  ┌───────────────┐  ┌──────────────┐  │ │
│  │ │ Apache Pinot  │  │ Redis Cluster │  │ Delta Lake    │  │ Elasticsearch│  │ │
│  │ │               │  │               │  │               │  │              │  │ │
│  │ │ Real-time     │  │ Feature Store │  │ Historical    │  │ Full-text    │  │ │
│  │ │ OLAP queries  │  │ + Current     │  │ analytics     │  │ search       │  │ │
│  │ │               │  │   state cache │  │               │  │              │  │ │
│  │ │ 50K queries/s │  │ 500K ops/s    │  │ PB-scale      │  │ 10K search/s │  │ │
│  │ │ <100ms P99    │  │ <1ms P99      │  │ minutes fresh │  │ <200ms P99   │  │ │
│  │ └───────────────┘  └───────────────┘  └───────────────┘  └──────────────┘  │ │
│  └─────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                   │
│  ┌─────────────────────────────────────────────────────────────────────────────┐ │
│  │ OBSERVABILITY                                                                │ │
│  │                                                                              │ │
│  │ Metrics: Prometheus → Grafana (Kafka lag, Flink backpressure, throughput)    │ │
│  │ Tracing: OpenTelemetry → Jaeger (end-to-end event tracing)                  │ │
│  │ Logging: Structured JSON → Elasticsearch (error investigation)               │ │
│  │ Alerting: Grafana Alerts → PagerDuty (P1: lag > 5min, P2: error > 1%)      │ │
│  └─────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                   │
│  INFRASTRUCTURE:                                                                  │
│  • Kubernetes (EKS): 100+ nodes, auto-scaling                                    │
│  • Terraform: All infra as code                                                   │
│  • ArgoCD: GitOps deployment                                                      │
│  • Cost: ~$150K/month at this scale                                               │
│                                                                                   │
└──────────────────────────────────────────────────────────────────────────────────┘
```

## Failure Modes & Recovery

| Failure | Detection | Recovery | Impact |
|---------|-----------|----------|--------|
| Kafka broker death | ISR count drops | Auto-rebalance partitions | <30s, no data loss |
| Flink TaskManager crash | Heartbeat timeout | Restore from checkpoint | <3 min, exactly-once |
| Full AZ outage | Health checks | Other 2 AZs handle load | <1 min, 50% extra load |
| Schema poison pill | Deserialization error | DLQ + alert | Single event, no pipeline impact |
| Consumer lag explosion | Lag metric alert | Auto-scale consumers | 2-5 min to recover |
| Disk full (Kafka) | Disk usage alert | Tiered storage spillover | No data loss |

## Capacity Planning Formula

```
KAFKA SIZING:
  Brokers = (write_throughput × replication_factor) / (per_broker_throughput × target_utilization)
  = (1 GB/s × 3) / (200 MB/s × 0.6) = 25 brokers (round to 30 for headroom)

FLINK SIZING:
  TaskManagers = total_parallelism / slots_per_tm
  Total parallelism = Kafka partitions (for 1:1 mapping)
  = 200 / 4 slots = 50 TaskManagers

STORAGE (30-day retention):
  Daily data = 1 GB/s × 86400 = 86 TB/day
  30-day hot = 86 TB × 7 days = 600 TB (Kafka SSD)
  30-day warm = 86 TB × 23 days = 2 PB (S3)
  Monthly storage cost = 600TB × $0.10/GB + 2PB × $0.023/GB = $60K + $46K = $106K
```

