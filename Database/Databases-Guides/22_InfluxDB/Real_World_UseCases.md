# InfluxDB - Real World Use Cases & Production Guide

## Table of Contents
1. [Use Case 1: Tesla Vehicle Telemetry](#use-case-1-tesla-vehicle-telemetry)
2. [Use Case 2: IBM Cloud Monitoring](#use-case-2-ibm-cloud-monitoring)
3. [Use Case 3: Hulu Video QoS](#use-case-3-hulu-video-qos)
4. [Use Case 4: Cisco ThousandEyes](#use-case-4-cisco-thousandeyes)
5. [Use Case 5: Honeywell Building Management](#use-case-5-honeywell-building-management)
6. [Replication Deep Dive](#replication-deep-dive)
7. [Scalability Patterns](#scalability-patterns)
8. [Production Setup](#production-setup)
9. [Core Concepts](#core-concepts)

---

## Use Case 1: Tesla Vehicle Telemetry

### Why InfluxDB?
- Purpose-built for time-series data (optimized write path)
- Handles millions of data points/second from connected vehicles
- Built-in downsampling and retention policies
- Tags for high-cardinality vehicle identification
- Flux for complex fleet-wide analytics

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│              Tesla Vehicle Telemetry Pipeline                        │
└─────────────────────────────────────────────────────────────────────┘

┌──────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  Tesla   │───▶│   MQTT/HTTP  │───▶│   Telegraf   │───▶│   InfluxDB   │
│ Vehicles │    │   Gateway    │    │   (agent)    │    │   Cluster    │
│ (millions)│   └──────────────┘    │   per region │    │              │
└──────────┘                        └──────────────┘    └──────────────┘
                                                              │
                                                              ▼
                                                       ┌──────────────┐
                                                       │   Grafana    │
                                                       │  Dashboards  │
                                                       └──────────────┘

Data Model:
┌─────────────────────────────────────────────────────────────────────┐
│  Measurement: vehicle_telemetry                                      │
│                                                                      │
│  Tags (indexed, for filtering/grouping):                            │
│    vehicle_id = "VIN_ABC123"                                        │
│    model = "Model_3"                                                │
│    firmware_version = "2024.8.1"                                    │
│    region = "us-west"                                               │
│                                                                      │
│  Fields (not indexed, actual values):                                │
│    battery_pct = 72.5                                               │
│    speed_mph = 65.2                                                 │
│    motor_temp_c = 45.3                                              │
│    range_miles = 210.5                                              │
│    charging_state = "not_charging"                                  │
│    latitude = 37.7749                                               │
│    longitude = -122.4194                                            │
│                                                                      │
│  Timestamp: 2024-03-01T14:30:00.000Z                               │
│                                                                      │
│  Line Protocol:                                                      │
│  vehicle_telemetry,vehicle_id=VIN_ABC123,model=Model_3              │
│    battery_pct=72.5,speed_mph=65.2,motor_temp_c=45.3 1709304600000 │
└─────────────────────────────────────────────────────────────────────┘

Retention & Downsampling:
┌────────────────────────────────────────────────────────────────┐
│  Raw data (1s intervals):     retained 7 days                   │
│  1-minute aggregates:         retained 30 days                  │
│  1-hour aggregates:           retained 1 year                   │
│  1-day aggregates:            retained forever                  │
│                                                                  │
│  Continuous Query (downsampling):                                │
│  CREATE CONTINUOUS QUERY "cq_1m" ON "tesla"                     │
│  BEGIN                                                           │
│    SELECT mean(battery_pct), max(speed_mph), mean(motor_temp_c) │
│    INTO "rp_30d"."vehicle_telemetry_1m"                         │
│    FROM "rp_7d"."vehicle_telemetry"                             │
│    GROUP BY time(1m), vehicle_id, model                         │
│  END                                                             │
└────────────────────────────────────────────────────────────────┘
```

### Scale Numbers
- **Millions of vehicles** reporting every 1-10 seconds
- **~10M+ data points/second** ingestion
- **50+ fields** per vehicle per sample
- **Series cardinality**: ~5M (vehicles * unique tag combinations)

---

## Use Case 2: IBM Cloud Monitoring

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│              IBM Cloud Infrastructure Monitoring                     │
└─────────────────────────────────────────────────────────────────────┘

┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐
│ Bare Metal│  │    VMs    │  │ Containers│  │  Network  │
│  Servers  │  │           │  │  (K8s)    │  │  Devices  │
└─────┬─────┘  └─────┬─────┘  └─────┬─────┘  └─────┬─────┘
      │              │              │              │
      └──────────────┴──────────────┴──────────────┘
                              │
                    ┌─────────▼──────────┐
                    │   Telegraf Agents   │
                    │   (per host/pod)    │
                    │                     │
                    │   Plugins:          │
                    │   - cpu, mem, disk  │
                    │   - net, docker     │
                    │   - kubernetes      │
                    │   - custom scripts  │
                    └─────────┬──────────┘
                              │
                    ┌─────────▼──────────┐
                    │  InfluxDB Cluster   │
                    │  (Enterprise)       │
                    │                     │
                    │  Meta Nodes: 3      │
                    │  Data Nodes: 6+     │
                    │                     │
                    │  Retention:         │
                    │  - hot:  7 days     │
                    │  - warm: 30 days    │
                    │  - cold: 1 year     │
                    └─────────┬──────────┘
                              │
              ┌───────────────┼───────────────┐
              │               │               │
              ▼               ▼               ▼
       ┌────────────┐  ┌────────────┐  ┌────────────┐
       │  Grafana   │  │ Kapacitor  │  │   API      │
       │ Dashboards │  │ (Alerting) │  │ (custom    │
       │            │  │            │  │  tools)    │
       └────────────┘  └────────────┘  └────────────┘
```

---

## Use Case 3: Hulu Video QoS

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│         Hulu - Video Quality of Service Monitoring                   │
└─────────────────────────────────────────────────────────────────────┘

┌──────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  Video   │───▶│  QoS Beacon  │───▶│  Kafka       │───▶│  InfluxDB    │
│  Player  │    │  (client-side)│   │  (buffer)    │    │              │
│ (SDK)    │    └──────────────┘    └──────────────┘    └──────────────┘
└──────────┘
                                                              │
Metrics collected per stream:                                 ▼
┌────────────────────────────────────────┐           ┌──────────────┐
│  - buffer_health_ms (rebuffering)      │           │  Real-time   │
│  - startup_time_ms                     │           │  Dashboard   │
│  - bitrate_kbps (current quality)      │           │  (Grafana)   │
│  - frame_drop_rate                     │           └──────────────┘
│  - error_rate                          │
│  - cdn_response_time_ms               │
│  - viewer_engagement_seconds          │
└────────────────────────────────────────┘

Flux Query (detect degradation):
┌────────────────────────────────────────────────────────────────────┐
│  from(bucket: "video_qos")                                          │
│    |> range(start: -5m)                                             │
│    |> filter(fn: (r) => r._measurement == "stream_quality")        │
│    |> filter(fn: (r) => r._field == "rebuffer_ratio")              │
│    |> aggregateWindow(every: 1m, fn: mean)                         │
│    |> filter(fn: (r) => r._value > 0.02)                          │
│    |> group(columns: ["cdn", "region"])                             │
│    // Alert if rebuffering > 2% in any region/CDN                  │
└────────────────────────────────────────────────────────────────────┘
```

---

## Use Case 4: Cisco ThousandEyes

### Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│         Cisco ThousandEyes - Network Performance Monitoring         │
└─────────────────────────────────────────────────────────────────────┘

Distributed Probes (worldwide):
┌──────┐  ┌──────┐  ┌──────┐  ┌──────┐  ┌──────┐
│Probe │  │Probe │  │Probe │  │Probe │  │Probe │
│US-E  │  │US-W  │  │EU    │  │APAC  │  │SA    │
└──┬───┘  └──┬───┘  └──┬───┘  └──┬───┘  └──┬───┘
   │         │         │         │         │
   └─────────┴─────────┴─────────┴─────────┘
                        │
              ┌─────────▼──────────┐
              │  Collection Tier   │
              │  (Telegraf + HTTP) │
              └─────────┬──────────┘
                        │
              ┌─────────▼──────────┐
              │  InfluxDB          │
              │                    │
              │  Measurements:     │
              │  - network_latency │
              │  - dns_resolution  │
              │  - http_response   │
              │  - path_trace      │
              │  - bgp_routing     │
              └────────────────────┘

Data Model:
  network_latency,
    probe=us-east-1,target=api.example.com,protocol=tcp,port=443
    rtt_ms=12.5,packet_loss_pct=0.0,jitter_ms=1.2
    1709304600000000000
```

---

## Use Case 5: Honeywell Building Management

### Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│         Honeywell - Smart Building IoT Sensors                      │
└─────────────────────────────────────────────────────────────────────┘

Building Sensors:
┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
│  HVAC    │ │ Lighting │ │  Power   │ │ Security │
│  Sensors │ │  Sensors │ │  Meters  │ │  Cameras │
└────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘
     │            │            │            │
     └────────────┴────────────┴────────────┘
                        │
              ┌─────────▼──────────┐
              │  BACnet/Modbus     │
              │  to MQTT Bridge    │
              └─────────┬──────────┘
                        │
              ┌─────────▼──────────┐
              │  Telegraf           │
              │  (MQTT consumer)   │
              └─────────┬──────────┘
                        │
              ┌─────────▼──────────┐
              │  InfluxDB           │
              │                    │
              │  Measurements:     │
              │  - hvac_temp       │
              │  - energy_usage    │
              │  - occupancy       │
              │  - air_quality     │
              └─────────┬──────────┘
                        │
              ┌─────────▼──────────┐
              │  Kapacitor         │
              │  (anomaly detect)  │
              │  + Grafana         │
              └────────────────────┘

Line Protocol Examples:
  hvac_temp,building=HQ,floor=3,zone=A temperature=72.1,humidity=45.2,setpoint=72.0 1709304600000
  energy_usage,building=HQ,floor=3,meter=main kw=125.5,kwh_today=1502.3 1709304600000
  air_quality,building=HQ,floor=3,zone=A co2_ppm=450,pm25=12.3,voc_ppb=150 1709304600000
```

---

## Replication Deep Dive

### InfluxDB Enterprise Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│              InfluxDB Enterprise Cluster                             │
└─────────────────────────────────────────────────────────────────────┘

              ┌─────────────────────────────────────┐
              │          Meta Nodes (3+)            │
              │                                     │
              │  - Raft consensus for metadata     │
              │  - Database/RP definitions          │
              │  - User/permission management      │
              │  - Shard group assignment           │
              │                                     │
              │  ┌────┐  ┌────┐  ┌────┐           │
              │  │Meta│  │Meta│  │Meta│           │
              │  │ 1  │  │ 2  │  │ 3  │           │
              │  └────┘  └────┘  └────┘           │
              └─────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              │               │               │
              ▼               ▼               ▼
       ┌────────────┐  ┌────────────┐  ┌────────────┐
       │ Data Node 1│  │ Data Node 2│  │ Data Node 3│
       │            │  │            │  │            │
       │ Shards:    │  │ Shards:    │  │ Shards:    │
       │ [1,2,3]    │  │ [1,4,5]    │  │ [2,3,5]    │
       │            │  │            │  │            │
       │ TSM Engine │  │ TSM Engine │  │ TSM Engine │
       └────────────┘  └────────────┘  └────────────┘

Replication Factor = 2:
  Each shard exists on 2 data nodes
  Writes go to all shard owners
  Reads can go to any shard owner

Hinted Handoff:
  If data node is temporarily down:
  - Other nodes buffer writes in hinted handoff queue
  - Replay when node returns
  - Configurable max age and size
```

### InfluxDB 3.0 / IOx Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│              InfluxDB 3.0 (IOx) - New Architecture                  │
└─────────────────────────────────────────────────────────────────────┘

                    ┌─────────────────────────────┐
                    │        Write Path           │
                    │                             │
                    │  ┌─────────────────────┐   │
                    │  │   Ingester Nodes    │   │
                    │  │   (WAL + in-memory) │   │
                    │  └──────────┬──────────┘   │
                    │             │ persist       │
                    │             ▼               │
                    │  ┌─────────────────────┐   │
                    │  │   Object Store      │   │  ← Parquet files
                    │  │   (S3/GCS/Azure)    │   │     on object storage
                    │  └─────────────────────┘   │
                    └─────────────────────────────┘

                    ┌─────────────────────────────┐
                    │        Query Path           │
                    │                             │
                    │  ┌─────────────────────┐   │
                    │  │   Querier Nodes     │   │
                    │  │   (DataFusion/Arrow)│   │
                    │  │                     │   │
                    │  │   Reads Parquet     │   │
                    │  │   from object store │   │
                    │  │   + in-memory data  │   │
                    │  └─────────────────────┘   │
                    └─────────────────────────────┘

Key Changes from TSM:
- Storage: Parquet files on object store (infinite retention, cheap)
- Query Engine: Apache DataFusion (Rust, columnar, vectorized)
- Wire Format: Apache Arrow (zero-copy, columnar in-memory)
- Catalog: PostgreSQL for metadata
- Separation of compute and storage (scale independently)
```

---

## Scalability Patterns

### TSM Storage Engine (InfluxDB 1.x/2.x)

```
┌─────────────────────────────────────────────────────────────────────┐
│              TSM (Time-Structured Merge Tree)                        │
└─────────────────────────────────────────────────────────────────────┘

Write Path:
┌────────┐    ┌────────────┐    ┌────────────┐    ┌──────────────┐
│ Write  │───▶│    WAL     │───▶│  In-Memory │───▶│  TSM File    │
│ (line  │    │ (append-   │    │   Cache    │    │  (immutable, │
│ proto) │    │  only log) │    │ (sorted)   │    │  compressed) │
└────────┘    └────────────┘    └────────────┘    └──────────────┘

TSM File Structure:
┌─────────────────────────────────────────────────────────────────┐
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Data Blocks (compressed time+value pairs)                │  │
│  │                                                          │  │
│  │  Block 1: timestamps[t1,t2,...] values[v1,v2,...]       │  │
│  │  Block 2: timestamps[...] values[...]                   │  │
│  │  ...                                                     │  │
│  └──────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Index (series key → block offset)                        │  │
│  └──────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Footer (index offset, metadata)                          │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘

Compaction:
  Level 1: Small files from cache flush (1-2MB)
  Level 2: Merged from Level 1 (10-100MB)
  Level 3: Merged from Level 2 (100MB-1GB)
  Level 4: Full compaction (optimize for reads)

Compression Algorithms:
- Timestamps: Delta-of-delta encoding (Gorilla paper)
  [1000, 1001, 1002, 1003] → [1000, 1, 0, 0] → very compact
- Float values: XOR encoding (Gorilla paper)
  Similar consecutive values → few bits each
- Integer values: Simple8B encoding
- String values: Snappy compression
- Boolean: Bit-packed

Typical compression: 2-10 bytes per data point (vs 16 bytes raw)
```

### Series Cardinality

```
┌─────────────────────────────────────────────────────────────────────┐
│              Cardinality Impact                                      │
└─────────────────────────────────────────────────────────────────────┘

Series = unique combination of measurement + tag set

Example:
  cpu,host=server1,cpu=cpu0         → 1 series
  cpu,host=server1,cpu=cpu1         → 1 series
  cpu,host=server2,cpu=cpu0         → 1 series
  
  1000 hosts * 16 CPUs = 16,000 series (manageable)
  
  BAD: cpu,host=server1,request_id=uuid-abc  → unbounded cardinality!
  Each unique request_id creates a new series permanently

Impact of High Cardinality:
┌────────────────────┬───────────────┬─────────────────────────────────┐
│ Series Count       │ RAM Required  │ Impact                          │
├────────────────────┼───────────────┼─────────────────────────────────┤
│ < 100K             │ < 1 GB        │ No issues                       │
│ 100K - 1M          │ 1-8 GB        │ Slight query slowdown           │
│ 1M - 10M           │ 8-64 GB       │ Need TSI index, careful design  │
│ > 10M              │ 64+ GB        │ Consider sharding or VictoriaM  │
└────────────────────┴───────────────┴─────────────────────────────────┘

TSI (Time Series Index):
- Disk-based index (vs in-memory)
- Allows higher cardinality without RAM pressure
- Uses memory-mapped files
- Enabled by default in InfluxDB 2.x
```

---

## Production Setup

### Hardware Sizing

```
┌─────────────────────────────────────────────────────────────────────┐
│              InfluxDB Hardware Recommendations                       │
└─────────────────────────────────────────────────────────────────────┘

Formula:
  RAM = (series_count * 2KB) + (active_queries * query_memory)
  Disk = (writes_per_sec * bytes_per_point * retention_seconds) / compression_ratio

Small (< 100K series, < 50K writes/sec):
├── CPU: 4 cores
├── RAM: 8-16 GB
├── Storage: 256 GB SSD
└── Network: 1 Gbps

Medium (100K-1M series, 50K-500K writes/sec):
├── CPU: 8-16 cores
├── RAM: 32-64 GB
├── Storage: 1-2 TB NVMe SSD
└── Network: 10 Gbps

Large (1M+ series, 500K+ writes/sec):
├── CPU: 32+ cores
├── RAM: 128+ GB
├── Storage: 4+ TB NVMe SSD
└── Network: 25 Gbps
└── Consider: InfluxDB Enterprise or VictoriaMetrics
```

### Telegraf Configuration

```toml
# telegraf.conf

[global_tags]
  environment = "production"
  region = "us-east-1"

[agent]
  interval = "10s"
  flush_interval = "10s"
  metric_batch_size = 5000
  metric_buffer_limit = 100000

[[outputs.influxdb_v2]]
  urls = ["http://influxdb:8086"]
  token = "${INFLUX_TOKEN}"
  organization = "myorg"
  bucket = "metrics"

[[inputs.cpu]]
  percpu = true
  totalcpu = true

[[inputs.mem]]

[[inputs.disk]]
  ignore_fs = ["tmpfs", "devtmpfs"]

[[inputs.kubernetes]]
  url = "https://kubernetes.default:443"

[[inputs.docker]]
  endpoint = "unix:///var/run/docker.sock"
```

### Retention Policy Design

```
┌─────────────────────────────────────────────────────────────────────┐
│              Multi-Tier Retention Strategy                           │
└─────────────────────────────────────────────────────────────────────┘

Tier 1 (Hot - Raw Data):
  Duration: 7 days
  Resolution: 10s
  Storage: NVMe SSD
  Use: Real-time troubleshooting

Tier 2 (Warm - 1-minute aggregates):
  Duration: 30 days
  Resolution: 1m
  Storage: SSD
  Use: Recent trend analysis

Tier 3 (Cold - 1-hour aggregates):
  Duration: 365 days
  Resolution: 1h
  Storage: HDD or object store
  Use: Capacity planning, reporting

Flux Task (downsampling):
  option task = {name: "downsample_1m", every: 1m}
  
  from(bucket: "raw")
    |> range(start: -task.every)
    |> aggregateWindow(every: 1m, fn: mean)
    |> to(bucket: "aggregated_1m")
```

---

## Core Concepts

### Data Model

```
┌─────────────────────────────────────────────────────────────────────┐
│              InfluxDB Data Model                                     │
└─────────────────────────────────────────────────────────────────────┘

Line Protocol:
  <measurement>,<tag_key>=<tag_value> <field_key>=<field_value> <timestamp>
  
  Example:
  weather,location=us-midwest,season=summer temperature=82.0,humidity=71.0 1465839830100400200

Concepts:
┌──────────────┬────────────────────────────────────────────────────────┐
│ Measurement  │ Logical container (like a table)                       │
│              │ Example: "cpu", "http_requests", "temperature"         │
├──────────────┼────────────────────────────────────────────────────────┤
│ Tags         │ Indexed metadata (for fast lookups + grouping)         │
│              │ Example: host=server1, region=us-east                  │
│              │ RULE: Use for metadata you filter/group by             │
│              │ WARNING: High cardinality tags kill performance         │
├──────────────┼────────────────────────────────────────────────────────┤
│ Fields       │ Actual data values (NOT indexed)                       │
│              │ Example: cpu_usage=72.5, free_mem=1024                 │
│              │ RULE: Use for values you aggregate (mean, max, etc.)  │
│              │ Can be float, int, string, boolean                     │
├──────────────┼────────────────────────────────────────────────────────┤
│ Timestamp    │ Nanosecond precision                                   │
│              │ Always stored, always indexed                          │
└──────────────┴────────────────────────────────────────────────────────┘

Tags vs Fields Decision:
┌────────────────────────────────────────────────────────────────┐
│  Question                           │  Use as  │              │
├─────────────────────────────────────┼──────────┤              │
│  Will you GROUP BY this value?      │  Tag     │              │
│  Will you filter WHERE x = y?       │  Tag     │              │
│  Is cardinality bounded (< 100K)?   │  Tag     │              │
│  Is it a numeric measurement?       │  Field   │              │
│  Is cardinality unbounded (UUIDs)?  │  Field   │  ← CRITICAL │
│  Will you do math on it?            │  Field   │              │
└─────────────────────────────────────┴──────────┘              │
└────────────────────────────────────────────────────────────────┘
```

### Flux Query Language

```
┌─────────────────────────────────────────────────────────────────────┐
│              Flux Query Examples                                     │
└─────────────────────────────────────────────────────────────────────┘

// Basic query: average CPU per host over last hour
from(bucket: "metrics")
  |> range(start: -1h)
  |> filter(fn: (r) => r._measurement == "cpu")
  |> filter(fn: (r) => r._field == "usage_percent")
  |> aggregateWindow(every: 5m, fn: mean)
  |> group(columns: ["host"])

// Alert: detect anomaly (value > 3 standard deviations)
from(bucket: "metrics")
  |> range(start: -1h)
  |> filter(fn: (r) => r._measurement == "response_time")
  |> aggregateWindow(every: 1m, fn: mean)
  |> derivative(unit: 1m)
  |> filter(fn: (r) => r._value > 100.0)

// Join: correlate two measurements
cpu = from(bucket: "metrics")
  |> range(start: -1h)
  |> filter(fn: (r) => r._measurement == "cpu")

mem = from(bucket: "metrics")
  |> range(start: -1h)
  |> filter(fn: (r) => r._measurement == "mem")

join(tables: {cpu: cpu, mem: mem}, on: ["_time", "host"])
  |> map(fn: (r) => ({r with ratio: r._value_cpu / r._value_mem}))

// Comparison with InfluxQL:
// InfluxQL: SELECT MEAN(usage) FROM cpu WHERE host='server1' GROUP BY time(5m)
// Flux:     from(bucket:"m") |> range(start:-1h) |> filter(fn:(r)=>r.host=="server1")
//           |> aggregateWindow(every:5m, fn:mean)
```

### Comparison with Other Time-Series Databases

```
┌──────────────────┬────────────────┬────────────────┬────────────────┬────────────────┐
│ Feature          │ InfluxDB       │ Prometheus     │ TimescaleDB    │VictoriaMetrics │
├──────────────────┼────────────────┼────────────────┼────────────────┼────────────────┤
│ Data Model       │ Tags + Fields  │ Labels only    │ SQL tables     │ Labels         │
│ Query Language   │ Flux/InfluxQL  │ PromQL         │ SQL            │ MetricsQL      │
│ Push/Pull        │ Push           │ Pull           │ Push (SQL)     │ Push           │
│ Clustering       │ Enterprise/$   │ No (Thanos)    │ Multi-node     │ Yes (free)     │
│ Cardinality      │ TSI needed     │ Limited        │ Good           │ Excellent      │
│ Compression      │ 2-10 bytes/pt  │ 1.5 bytes/pt   │ Varies         │ 0.4 bytes/pt   │
│ Long-term        │ Built-in       │ External       │ Built-in       │ Built-in       │
│ Write Speed      │ 500K+/sec      │ N/A (pull)     │ 500K+/sec      │ 1M+/sec        │
│ Best For         │ IoT, DevOps    │ K8s monitoring │ SQL users, IoT │ High scale     │
└──────────────────┴────────────────┴────────────────┴────────────────┴────────────────┘
```

### Write Performance Benchmarks

```
┌─────────────────────────────────────────────────────────────────────┐
│ InfluxDB 2.x Write Performance (single node, NVMe SSD)             │
├─────────────────────────────────────────────────────────────────────┤
│ Series Count  │ Write Rate      │ Disk Usage/day │ RAM Usage        │
├───────────────┼─────────────────┼────────────────┼──────────────────┤
│ 10K series    │ 500K pts/sec    │ 5 GB           │ 2 GB             │
│ 100K series   │ 300K pts/sec    │ 30 GB          │ 4 GB             │
│ 1M series     │ 150K pts/sec    │ 100 GB         │ 16 GB            │
│ 10M series    │ 50K pts/sec     │ 300 GB         │ 64 GB (TSI)      │
└───────────────┴─────────────────┴────────────────┴──────────────────┘

Key Performance Tips:
1. Batch writes (5000-10000 points per request)
2. Use line protocol (most efficient format)
3. Avoid high-cardinality tags (bounded metadata only)
4. Set appropriate shard duration (1 day for high write, 7 days for low)
5. Use SSD (NVMe preferred) for WAL and data
6. Pre-create databases/buckets before load
```
