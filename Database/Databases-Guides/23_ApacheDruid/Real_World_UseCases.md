# Apache Druid - Real World Use Cases & Production Guide

## Core Concepts

### Segment Architecture
```
Segment (Columnar Storage Unit)
┌─────────────────────────────────────────────────┐
│  Segment: wikipedia_2024-01-01T00:00:00.000Z    │
├─────────────────────────────────────────────────┤
│  __time column     [compressed timestamps]       │
│  dimension cols    [dictionary + bitmap index]   │
│  metric cols       [LZ4 compressed numerics]     │
├─────────────────────────────────────────────────┤
│  Metadata: interval, version, shard spec         │
│  Size: 300MB-700MB optimal                       │
└─────────────────────────────────────────────────┘
```

### Bitmap Indexes
```
Dimension "country" (dictionary-encoded):
  0 = "US"
  1 = "UK"  
  2 = "IN"

Bitmap Index:
  "US" → 1001010110...  (bit per row)
  "UK" → 0100100001...
  "IN" → 0010001000...

Filter: country = "US" AND city = "NYC"
  → BITWISE AND of two bitmaps → O(n/64) operations
```

### Rollup at Ingestion
```
Raw Events (1B rows/day):
  2024-01-01T10:05:23 | page=Main | country=US | views=1 | bytes=5000
  2024-01-01T10:05:45 | page=Main | country=US | views=1 | bytes=3000
  2024-01-01T10:06:12 | page=Main | country=US | views=1 | bytes=7000

After Rollup (HOUR granularity):
  2024-01-01T10:00:00 | page=Main | country=US | views=3 | bytes=15000

Rollup ratio: 10:1 to 1000:1 depending on cardinality
```

### Segment Structure
```
┌──────────────────────────────────────┐
│           SEGMENT FILE               │
├──────────────────────────────────────┤
│  version.bin         (segment ver)   │
│  meta.smoosh         (metadata)      │
│  00000.smoosh        (columns)       │
│    ├── __time        (long[])        │
│    ├── dim_country   (dict+bitmap)   │
│    ├── dim_page      (dict+bitmap)   │
│    ├── met_count     (long[])        │
│    └── met_sum_bytes (double[])      │
│  index.drd           (dimensions)    │
│  factory.json        (segment type)  │
└──────────────────────────────────────┘
```

### Real-time vs Batch Ingestion
```
Real-time (Kafka Indexing):
  Kafka → MiddleManager → In-memory segment → Handoff → Historical
  Latency: sub-second to seconds
  Trade-off: smaller initial segments, needs compaction

Batch (Hadoop/Native):
  HDFS/S3 → Overlord → Task → Optimized segments → Historical
  Latency: minutes to hours
  Trade-off: perfect rollup, optimal segments
```

### Theta Sketches (Approximate Count-Distinct)
```json
{
  "queryType": "groupBy",
  "aggregations": [
    {
      "type": "thetaSketch",
      "name": "unique_users",
      "fieldName": "user_id_sketch",
      "size": 16384
    }
  ],
  "postAggregations": [
    {
      "type": "thetaSketchEstimate",
      "name": "unique_count",
      "field": { "type": "fieldAccess", "fieldName": "unique_users" }
    }
  ]
}
```
- Error bound: ~2% with size=16384
- Supports set operations (union, intersection, difference)
- Mergeable across segments and time

### Lookups (Dimension Enrichment)
```json
{
  "type": "cachedNamespace",
  "extractionNamespace": {
    "type": "jdbc",
    "connectorConfig": {
      "connectURI": "jdbc:mysql://lookup-db:3306/lookups",
      "user": "druid",
      "password": "secret"
    },
    "table": "country_lookup",
    "keyColumn": "country_code",
    "valueColumn": "country_name",
    "pollPeriod": "PT5M"
  }
}
```
Query-time enrichment without denormalization at ingest.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        MASTER TIER                                   │
│  ┌─────────────────┐    ┌─────────────────┐    ┌────────────────┐  │
│  │   Coordinator   │    │    Overlord     │    │   ZooKeeper    │  │
│  │ (segment mgmt)  │    │ (task mgmt)     │    │  (discovery)   │  │
│  └────────┬────────┘    └────────┬────────┘    └────────────────┘  │
│           │                      │                                   │
│  ┌────────┴──────────────────────┴────────┐                         │
│  │         Metadata Store (MySQL/PG)       │                         │
│  └─────────────────────────────────────────┘                         │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                        QUERY TIER                                    │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐           │
│  │ Broker 1 │  │ Broker 2 │  │ Broker 3 │  │ Router   │           │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘           │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                        DATA TIER                                     │
│  ┌───────────────────────────────┐  ┌────────────────────────────┐  │
│  │      Historical Nodes         │  │    MiddleManager Nodes     │  │
│  │  ┌─────┐ ┌─────┐ ┌─────┐    │  │  ┌──────┐ ┌──────┐        │  │
│  │  │Hot-1│ │Hot-2│ │Cold-1│    │  │  │ MM-1 │ │ MM-2 │        │  │
│  │  │64GB │ │64GB │ │32GB  │    │  │  │Peons │ │Peons │        │  │
│  │  └─────┘ └─────┘ └─────┘    │  │  └──────┘ └──────┘        │  │
│  └───────────────────────────────┘  └────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                    DEEP STORAGE (S3/HDFS)                            │
│  [All segments persisted as source of truth]                         │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Use Case 1: Netflix A/B Testing - Real-Time Experiment Analysis

### Architecture
```
┌──────────────┐     ┌──────────────┐     ┌──────────────────────────┐
│  Netflix App │────▶│    Kafka     │────▶│     Apache Druid         │
│  (events)    │     │  (ab_events) │     │                          │
└──────────────┘     └──────────────┘     │  ┌────────────────────┐  │
                                           │  │   Coordinator      │  │
┌──────────────┐                           │  │   - segment rules  │  │
│  Experiment  │                           │  │   - replication=2  │  │
│  Dashboard   │◀────────────────────────▶│  └────────────────────┘  │
│  (Analysts)  │     Queries               │  ┌────────────────────┐  │
└──────────────┘                           │  │   Overlord         │  │
                                           │  │   - Kafka tasks    │  │
                                           │  └────────────────────┘  │
                                           │  ┌────────────────────┐  │
                                           │  │   Broker x3        │  │
                                           │  │   - query routing  │  │
                                           │  └────────────────────┘  │
                                           │  ┌────────────────────┐  │
                                           │  │   Historical x12   │  │
                                           │  │   - hot tier: 7d   │  │
                                           │  │   - cold tier: 90d │  │
                                           │  └────────────────────┘  │
                                           │  ┌────────────────────┐  │
                                           │  │  MiddleManager x6  │  │
                                           │  │  - Kafka indexing  │  │
                                           │  └────────────────────┘  │
                                           └──────────────────────────┘
```

### Datasource Schema
```
Datasource: netflix_ab_events
Granularity: MINUTE (query), HOUR (segment)

Dimensions:
  - experiment_id    (STRING, cardinality ~10K)
  - variant          (STRING, "control"|"treatment_a"|"treatment_b")
  - user_segment     (STRING, "new"|"returning"|"premium")
  - device_type      (STRING, ~20 values)
  - country          (STRING, ~190 values)
  - content_id       (STRING, cardinality ~50K)
  - event_type       (STRING, "play"|"pause"|"complete"|"abandon")

Metrics:
  - count            (longSum)
  - watch_time_ms    (longSum)
  - engagement_score (doubleSum)
  - unique_users     (thetaSketch, size=16384)
  - revenue_cents    (longSum)

Rollup: enabled (ratio ~50:1)
Retention: 90 days hot, 1 year cold
```

### Ingestion Spec
```json
{
  "type": "kafka",
  "spec": {
    "ioConfig": {
      "type": "kafka",
      "consumerProperties": {
        "bootstrap.servers": "kafka-broker-1:9092,kafka-broker-2:9092",
        "group.id": "druid-ab-events"
      },
      "topic": "netflix.ab.events",
      "inputFormat": { "type": "json" },
      "useEarliestOffset": true,
      "taskCount": 6,
      "replicas": 2,
      "taskDuration": "PT1H"
    },
    "tuningConfig": {
      "type": "kafka",
      "maxRowsPerSegment": 5000000,
      "maxRowsInMemory": 500000,
      "intermediatePersistPeriod": "PT10M"
    },
    "dataSchema": {
      "dataSource": "netflix_ab_events",
      "timestampSpec": { "column": "timestamp", "format": "iso" },
      "dimensionsSpec": {
        "dimensions": [
          "experiment_id", "variant", "user_segment",
          "device_type", "country", "content_id", "event_type"
        ]
      },
      "metricsSpec": [
        { "type": "count", "name": "event_count" },
        { "type": "longSum", "name": "watch_time_ms", "fieldName": "watch_time_ms" },
        { "type": "doubleSum", "name": "engagement_score", "fieldName": "engagement_score" },
        { "type": "thetaSketch", "name": "unique_users", "fieldName": "user_id", "size": 16384 },
        { "type": "longSum", "name": "revenue_cents", "fieldName": "revenue_cents" }
      ],
      "granularitySpec": {
        "segmentGranularity": "HOUR",
        "queryGranularity": "MINUTE",
        "rollup": true
      }
    }
  }
}
```

### Queries
```json
// Statistical significance check for experiment
{
  "queryType": "groupBy",
  "dataSource": "netflix_ab_events",
  "intervals": ["2024-01-01/2024-01-08"],
  "granularity": "DAY",
  "dimensions": ["variant"],
  "filter": { "type": "selector", "dimension": "experiment_id", "value": "exp_ui_redesign_v2" },
  "aggregations": [
    { "type": "longSum", "name": "total_watch_time", "fieldName": "watch_time_ms" },
    { "type": "thetaSketch", "name": "unique_users", "fieldName": "unique_users", "size": 16384 },
    { "type": "count", "name": "events" }
  ],
  "postAggregations": [
    {
      "type": "arithmetic", "name": "avg_watch_time_per_user",
      "fn": "/",
      "fields": [
        { "type": "fieldAccess", "fieldName": "total_watch_time" },
        { "type": "thetaSketchEstimate", "field": { "type": "fieldAccess", "fieldName": "unique_users" } }
      ]
    }
  ]
}
```

### Scale Numbers
| Metric | Value |
|--------|-------|
| Events/sec | 2M+ |
| Active experiments | 10,000+ |
| Raw events/day | 150B+ |
| After rollup/day | 3B rows |
| Query latency (p50) | 120ms |
| Query latency (p99) | 800ms |
| Historicals | 12 nodes (64GB RAM each) |
| MiddleManagers | 6 nodes |
| Deep storage | S3 (~50TB compressed) |

---

## Use Case 2: Airbnb Search Analytics - Marketplace Insights

### Architecture
```
┌───────────────┐    ┌──────────────┐    ┌──────────────────────────┐
│ Airbnb Search │───▶│    Kafka     │───▶│      Apache Druid        │
│  Service      │    │(search_logs) │    │                          │
└───────────────┘    └──────────────┘    │  ┌────────────────────┐  │
                                          │  │  Coordinator       │  │
┌───────────────┐    ┌──────────────┐    │  │  - load balancing  │  │
│ Booking       │───▶│    Kafka     │───▶│  └────────────────────┘  │
│ Service       │    │(bookings)    │    │  ┌────────────────────┐  │
└───────────────┘    └──────────────┘    │  │  Overlord          │  │
                                          │  │  - 2 supervisors   │  │
┌───────────────┐                         │  └────────────────────┘  │
│ Superset      │◀───────────────────────▶│  ┌────────────────────┐  │
│ Dashboards    │   Native queries        │  │  Broker x4         │  │
└───────────────┘                         │  │  - result cache    │  │
                                          │  └────────────────────┘  │
                                          │  ┌────────────────────┐  │
                                          │  │  Historical x16    │  │
                                          │  │  - SSD hot tier    │  │
                                          │  └────────────────────┘  │
                                          │  ┌────────────────────┐  │
                                          │  │  MiddleManager x8  │  │
                                          │  └────────────────────┘  │
                                          └──────────────────────────┘
```

### Datasource Schema
```
Datasource: airbnb_search_events
Granularity: MINUTE (query), HOUR (segment)

Dimensions:
  - search_id         (STRING)
  - market            (STRING, ~700 markets)
  - listing_type      (STRING, "entire"|"private"|"shared")
  - guests            (LONG)
  - checkin_dow       (STRING, day of week)
  - price_bucket      (STRING, "$0-50"|"$50-100"|...)
  - amenity_filter    (ARRAY<STRING>)
  - sort_order        (STRING)
  - platform          (STRING, "ios"|"android"|"web")
  - is_instant_book   (STRING, "true"|"false")

Metrics:
  - search_count          (count)
  - results_shown         (longSum)
  - clicks                (longSum)
  - bookings              (longSum)
  - revenue_usd           (doubleSum)
  - unique_searchers      (thetaSketch)
  - avg_price_shown       (doubleMean)
  - position_clicked_sum  (longSum)

Rollup: enabled (ratio ~30:1)
```

### Ingestion Spec
```json
{
  "type": "kafka",
  "spec": {
    "ioConfig": {
      "type": "kafka",
      "consumerProperties": {
        "bootstrap.servers": "kafka-1:9092,kafka-2:9092,kafka-3:9092"
      },
      "topic": "airbnb.search.events",
      "taskCount": 8,
      "replicas": 2,
      "taskDuration": "PT30M"
    },
    "dataSchema": {
      "dataSource": "airbnb_search_events",
      "timestampSpec": { "column": "event_time", "format": "millis" },
      "dimensionsSpec": {
        "dimensions": [
          "search_id", "market", "listing_type",
          { "type": "long", "name": "guests" },
          "checkin_dow", "price_bucket",
          { "type": "json", "name": "amenity_filter" },
          "sort_order", "platform", "is_instant_book"
        ]
      },
      "metricsSpec": [
        { "type": "count", "name": "search_count" },
        { "type": "longSum", "name": "results_shown", "fieldName": "num_results" },
        { "type": "longSum", "name": "clicks", "fieldName": "click_count" },
        { "type": "longSum", "name": "bookings", "fieldName": "booking_flag" },
        { "type": "doubleSum", "name": "revenue_usd", "fieldName": "booking_revenue" },
        { "type": "thetaSketch", "name": "unique_searchers", "fieldName": "user_id" }
      ],
      "granularitySpec": {
        "segmentGranularity": "HOUR",
        "queryGranularity": "MINUTE",
        "rollup": true
      }
    }
  }
}
```

### Queries
```json
// Conversion funnel by market
{
  "queryType": "groupBy",
  "dataSource": "airbnb_search_events",
  "intervals": ["2024-01-01/2024-01-02"],
  "granularity": "HOUR",
  "dimensions": ["market", "platform"],
  "aggregations": [
    { "type": "longSum", "name": "searches", "fieldName": "search_count" },
    { "type": "longSum", "name": "clicks", "fieldName": "clicks" },
    { "type": "longSum", "name": "bookings", "fieldName": "bookings" },
    { "type": "doubleSum", "name": "revenue", "fieldName": "revenue_usd" }
  ],
  "postAggregations": [
    {
      "type": "arithmetic", "name": "ctr", "fn": "/",
      "fields": [
        { "type": "fieldAccess", "fieldName": "clicks" },
        { "type": "fieldAccess", "fieldName": "searches" }
      ]
    },
    {
      "type": "arithmetic", "name": "conversion_rate", "fn": "/",
      "fields": [
        { "type": "fieldAccess", "fieldName": "bookings" },
        { "type": "fieldAccess", "fieldName": "searches" }
      ]
    }
  ],
  "having": { "type": "greaterThan", "aggregation": "searches", "value": 1000 },
  "limitSpec": { "type": "default", "limit": 50, "columns": [{"dimension": "revenue", "direction": "descending"}] }
}
```

### Scale Numbers
| Metric | Value |
|--------|-------|
| Searches/sec | 500K+ |
| Events/day | 40B |
| After rollup | 1.5B rows/day |
| Markets tracked | 700+ |
| Query latency (p50) | 90ms |
| Query latency (p99) | 600ms |
| Historicals | 16 nodes (128GB RAM, NVMe) |
| Retention | 30 days hot, 1 year cold |

---

## Use Case 3: Twitter Ad Analytics - Real-Time Ad Performance

### Architecture
```
┌───────────────┐    ┌──────────────┐    ┌──────────────────────────┐
│  Ad Serving   │───▶│    Kafka     │───▶│      Apache Druid        │
│  (impressions)│    │ (ad_events)  │    │                          │
└───────────────┘    └──────────────┘    │  ┌────────────────────┐  │
                                          │  │  Coordinator x2    │  │
┌───────────────┐    ┌──────────────┐    │  │  (HA pair)         │  │
│  Click/Conv   │───▶│    Kafka     │───▶│  └────────────────────┘  │
│  Tracker      │    │ (conversions)│    │  ┌────────────────────┐  │
└───────────────┘    └──────────────┘    │  │  Overlord x2       │  │
                                          │  │  (HA pair)         │  │
┌───────────────┐                         │  └────────────────────┘  │
│  Advertiser   │◀───────────────────────▶│  ┌────────────────────┐  │
│  Dashboard    │   Sub-second queries    │  │  Broker x6         │  │
└───────────────┘                         │  │  (query cache 4GB) │  │
                                          │  └────────────────────┘  │
                                          │  ┌────────────────────┐  │
                                          │  │  Historical x24    │  │
                                          │  │  Hot: 12 (256GB)   │  │
                                          │  │  Cold: 12 (64GB)   │  │
                                          │  └────────────────────┘  │
                                          │  ┌────────────────────┐  │
                                          │  │  MiddleManager x12 │  │
                                          │  └────────────────────┘  │
                                          └──────────────────────────┘
```

### Datasource Schema
```
Datasource: twitter_ad_impressions
Granularity: SECOND (query), 15MIN (segment)

Dimensions:
  - campaign_id       (STRING, ~5M)
  - ad_group_id       (STRING, ~20M)
  - creative_id       (STRING, ~50M)
  - advertiser_id     (STRING, ~500K)
  - placement         (STRING, "timeline"|"search"|"profile")
  - device_os         (STRING)
  - country           (STRING)
  - targeting_type    (STRING)
  - bid_type          (STRING, "cpm"|"cpc"|"cpv")
  - event_type        (STRING, "impression"|"click"|"conversion"|"video_view")

Metrics:
  - impressions       (count)
  - clicks            (longSum)
  - conversions       (longSum)
  - spend_micros      (longSum)  -- in microdollars
  - revenue_micros    (longSum)
  - video_views_25    (longSum)
  - video_views_50    (longSum)
  - video_views_100   (longSum)
  - unique_reach      (HLLSketch)
  - engagements       (longSum)

Rollup: enabled (ratio ~100:1)
```

### Ingestion Spec
```json
{
  "type": "kafka",
  "spec": {
    "ioConfig": {
      "type": "kafka",
      "consumerProperties": {
        "bootstrap.servers": "kafka-ads-1:9092,kafka-ads-2:9092,kafka-ads-3:9092",
        "max.poll.records": "5000"
      },
      "topic": "twitter.ads.events",
      "taskCount": 12,
      "replicas": 2,
      "taskDuration": "PT15M"
    },
    "tuningConfig": {
      "type": "kafka",
      "maxRowsPerSegment": 5000000,
      "maxRowsInMemory": 1000000,
      "maxBytesInMemory": 536870912,
      "intermediatePersistPeriod": "PT5M",
      "handoffConditionTimeout": 900000
    },
    "dataSchema": {
      "dataSource": "twitter_ad_impressions",
      "timestampSpec": { "column": "event_ts", "format": "millis" },
      "dimensionsSpec": {
        "dimensions": [
          "campaign_id", "ad_group_id", "creative_id",
          "advertiser_id", "placement", "device_os",
          "country", "targeting_type", "bid_type", "event_type"
        ]
      },
      "metricsSpec": [
        { "type": "count", "name": "impressions" },
        { "type": "longSum", "name": "clicks", "fieldName": "is_click" },
        { "type": "longSum", "name": "conversions", "fieldName": "is_conversion" },
        { "type": "longSum", "name": "spend_micros", "fieldName": "spend_micros" },
        { "type": "longSum", "name": "revenue_micros", "fieldName": "revenue_micros" },
        { "type": "HLLSketchBuild", "name": "unique_reach", "fieldName": "user_id", "lgK": 12 }
      ],
      "granularitySpec": {
        "segmentGranularity": "FIFTEEN_MINUTE",
        "queryGranularity": "SECOND",
        "rollup": true
      }
    }
  }
}
```

### Queries
```json
// Real-time campaign performance for advertiser dashboard
{
  "queryType": "groupBy",
  "dataSource": "twitter_ad_impressions",
  "intervals": ["2024-01-15T00:00:00/2024-01-15T23:59:59"],
  "granularity": "FIFTEEN_MINUTE",
  "dimensions": ["campaign_id", "placement"],
  "filter": {
    "type": "and",
    "fields": [
      { "type": "selector", "dimension": "advertiser_id", "value": "adv_12345" },
      { "type": "selector", "dimension": "event_type", "value": "impression" }
    ]
  },
  "aggregations": [
    { "type": "count", "name": "impressions" },
    { "type": "longSum", "name": "clicks", "fieldName": "clicks" },
    { "type": "longSum", "name": "spend", "fieldName": "spend_micros" },
    { "type": "HLLSketchMerge", "name": "reach", "fieldName": "unique_reach", "lgK": 12 }
  ],
  "postAggregations": [
    {
      "type": "arithmetic", "name": "ctr", "fn": "/",
      "fields": [
        { "type": "fieldAccess", "fieldName": "clicks" },
        { "type": "fieldAccess", "fieldName": "impressions" }
      ]
    },
    {
      "type": "arithmetic", "name": "cpm_micros", "fn": "*",
      "fields": [
        {
          "type": "arithmetic", "fn": "/",
          "fields": [
            { "type": "fieldAccess", "fieldName": "spend" },
            { "type": "fieldAccess", "fieldName": "impressions" }
          ]
        },
        { "type": "constant", "value": 1000 }
      ]
    }
  ]
}
```

### Scale Numbers
| Metric | Value |
|--------|-------|
| Ad events/sec | 5M+ |
| Events/day | 400B+ |
| After rollup | 8B rows/day |
| Advertisers | 500K+ |
| Query latency (p50) | 50ms |
| Query latency (p99) | 400ms |
| Cluster nodes | 50+ total |
| Data retained | 2 years |
| Deep storage | S3 (~200TB) |

---

## Use Case 4: Confluent Kafka Monitoring - Cluster Metrics

### Architecture
```
┌───────────────┐    ┌──────────────┐    ┌──────────────────────────┐
│ Kafka Brokers │───▶│  Metrics     │───▶│      Apache Druid        │
│ (JMX metrics) │    │  Kafka Topic │    │                          │
└───────────────┘    └──────────────┘    │  ┌────────────────────┐  │
                                          │  │  Coordinator       │  │
┌───────────────┐    ┌──────────────┐    │  └────────────────────┘  │
│ Connect/SR/   │───▶│  Metrics     │───▶│  ┌────────────────────┐  │
│ ksqlDB        │    │  Kafka Topic │    │  │  Overlord          │  │
└───────────────┘    └──────────────┘    │  └────────────────────┘  │
                                          │  ┌────────────────────┐  │
┌───────────────┐                         │  │  Broker x2         │  │
│ Confluent     │◀───────────────────────▶│  └────────────────────┘  │
│ Control Center│   <100ms queries        │  ┌────────────────────┐  │
└───────────────┘                         │  │  Historical x6     │  │
                                          │  │  (64GB RAM each)   │  │
┌───────────────┐                         │  └────────────────────┘  │
│ Alert Manager │◀─── threshold queries ──│  ┌────────────────────┐  │
└───────────────┘                         │  │  MiddleManager x4  │  │
                                          │  └────────────────────┘  │
                                          └──────────────────────────┘
```

### Datasource Schema
```
Datasource: confluent_kafka_metrics
Granularity: SECOND (query), MINUTE (segment)

Dimensions:
  - cluster_id        (STRING)
  - broker_id         (STRING)
  - topic             (STRING, cardinality ~100K)
  - partition          (STRING)
  - consumer_group    (STRING, ~50K)
  - metric_name       (STRING)
  - environment       (STRING, "prod"|"staging"|"dev")
  - region            (STRING)

Metrics:
  - bytes_in_per_sec        (doubleSum)
  - bytes_out_per_sec       (doubleSum)
  - messages_in_per_sec     (doubleSum)
  - request_latency_ms      (doubleSum)
  - request_count           (longSum)
  - consumer_lag            (longMax)
  - under_replicated        (longMax)
  - isr_shrinks             (longSum)
  - partition_count         (longLast)
  - disk_usage_bytes        (longLast)

Rollup: enabled (ratio ~20:1)
```

### Ingestion Spec
```json
{
  "type": "kafka",
  "spec": {
    "ioConfig": {
      "type": "kafka",
      "consumerProperties": {
        "bootstrap.servers": "monitoring-kafka:9092"
      },
      "topic": "_confluent-metrics",
      "taskCount": 4,
      "replicas": 2,
      "taskDuration": "PT10M"
    },
    "dataSchema": {
      "dataSource": "confluent_kafka_metrics",
      "timestampSpec": { "column": "timestamp", "format": "millis" },
      "dimensionsSpec": {
        "dimensions": [
          "cluster_id", "broker_id", "topic", "partition",
          "consumer_group", "metric_name", "environment", "region"
        ]
      },
      "metricsSpec": [
        { "type": "doubleSum", "name": "bytes_in", "fieldName": "bytes_in_per_sec" },
        { "type": "doubleSum", "name": "bytes_out", "fieldName": "bytes_out_per_sec" },
        { "type": "doubleSum", "name": "messages_in", "fieldName": "messages_in_per_sec" },
        { "type": "longSum", "name": "request_count", "fieldName": "request_count" },
        { "type": "longMax", "name": "consumer_lag", "fieldName": "consumer_lag" },
        { "type": "longMax", "name": "under_replicated", "fieldName": "under_replicated_partitions" }
      ],
      "granularitySpec": {
        "segmentGranularity": "MINUTE",
        "queryGranularity": "SECOND",
        "rollup": true
      }
    }
  }
}
```

### Queries
```json
// Consumer lag alert query
{
  "queryType": "topN",
  "dataSource": "confluent_kafka_metrics",
  "intervals": ["2024-01-15T10:00:00/2024-01-15T10:05:00"],
  "granularity": "MINUTE",
  "dimension": "consumer_group",
  "filter": {
    "type": "and",
    "fields": [
      { "type": "selector", "dimension": "cluster_id", "value": "prod-cluster-1" },
      { "type": "bound", "dimension": "consumer_lag", "lower": "10000", "ordering": "numeric" }
    ]
  },
  "aggregations": [
    { "type": "longMax", "name": "max_lag", "fieldName": "consumer_lag" }
  ],
  "metric": "max_lag",
  "threshold": 20
}
```

### Scale Numbers
| Metric | Value |
|--------|-------|
| Metrics/sec | 500K |
| Kafka clusters monitored | 200+ |
| Topics tracked | 100K+ |
| Consumer groups | 50K+ |
| Query latency (p50) | 30ms |
| Query latency (p99) | 200ms |
| Retention | 7 days (1-sec), 90 days (1-min rollup) |
| Cluster size | 12 nodes total |

---

## Use Case 5: Target Retail - Real-Time Inventory & Sales Analytics

### Architecture
```
┌───────────────┐    ┌──────────────┐    ┌──────────────────────────┐
│  POS Systems  │───▶│    Kafka     │───▶│      Apache Druid        │
│  (1900 stores)│    │(transactions)│    │                          │
└───────────────┘    └──────────────┘    │  ┌────────────────────┐  │
                                          │  │  Coordinator       │  │
┌───────────────┐    ┌──────────────┐    │  │  - load rules      │  │
│  Inventory    │───▶│    Kafka     │───▶│  └────────────────────┘  │
│  Systems      │    │ (inventory)  │    │  ┌────────────────────┐  │
└───────────────┘    └──────────────┘    │  │  Overlord          │  │
                                          │  └────────────────────┘  │
┌───────────────┐    ┌──────────────┐    │  ┌────────────────────┐  │
│  E-commerce   │───▶│    Kafka     │───▶│  │  Broker x4         │  │
│  Platform     │    │(online_sales)│    │  └────────────────────┘  │
└───────────────┘    └──────────────┘    │  ┌────────────────────┐  │
                                          │  │  Historical x20    │  │
┌───────────────┐                         │  │  Hot: 10 (256GB)   │  │
│ Merch/Supply  │◀───────────────────────▶│  │  Cold: 10 (64GB)   │  │
│ Chain Dashbd  │                         │  └────────────────────┘  │
└───────────────┘                         │  ┌────────────────────┐  │
                                          │  │  MiddleManager x8  │  │
                                          │  └────────────────────┘  │
                                          └──────────────────────────┘
```

### Datasource Schema
```
Datasource: target_sales_inventory
Granularity: MINUTE (query), HOUR (segment)

Dimensions:
  - store_id          (STRING, ~1900)
  - department        (STRING, ~50)
  - category          (STRING, ~500)
  - subcategory       (STRING, ~5000)
  - sku               (STRING, ~500K)
  - brand             (STRING, ~10K)
  - channel           (STRING, "store"|"online"|"pickup")
  - region            (STRING, ~10)
  - district          (STRING, ~300)
  - promo_flag        (STRING, "true"|"false")
  - payment_method    (STRING)

Metrics:
  - units_sold        (longSum)
  - revenue_cents     (longSum)
  - discount_cents    (longSum)
  - transactions      (count)
  - inventory_on_hand (longLast)
  - unique_customers  (HLLSketch)
  - basket_items_sum  (longSum)

Rollup: enabled (ratio ~15:1)
```

### Ingestion Spec
```json
{
  "type": "kafka",
  "spec": {
    "ioConfig": {
      "type": "kafka",
      "consumerProperties": {
        "bootstrap.servers": "kafka-retail-1:9092,kafka-retail-2:9092"
      },
      "topic": "target.pos.transactions",
      "taskCount": 8,
      "replicas": 2,
      "taskDuration": "PT30M"
    },
    "dataSchema": {
      "dataSource": "target_sales_inventory",
      "timestampSpec": { "column": "txn_timestamp", "format": "iso" },
      "dimensionsSpec": {
        "dimensions": [
          "store_id", "department", "category", "subcategory",
          "sku", "brand", "channel", "region", "district",
          "promo_flag", "payment_method"
        ]
      },
      "metricsSpec": [
        { "type": "longSum", "name": "units_sold", "fieldName": "quantity" },
        { "type": "longSum", "name": "revenue_cents", "fieldName": "total_cents" },
        { "type": "longSum", "name": "discount_cents", "fieldName": "discount_cents" },
        { "type": "count", "name": "transactions" },
        { "type": "longLast", "name": "inventory_on_hand", "fieldName": "current_inventory" },
        { "type": "HLLSketchBuild", "name": "unique_customers", "fieldName": "loyalty_id", "lgK": 14 }
      ],
      "granularitySpec": {
        "segmentGranularity": "HOUR",
        "queryGranularity": "MINUTE",
        "rollup": true
      }
    }
  }
}
```

### Queries
```json
// Real-time sales by store during Black Friday
{
  "queryType": "groupBy",
  "dataSource": "target_sales_inventory",
  "intervals": ["2024-11-29T00:00:00/2024-11-29T23:59:59"],
  "granularity": "FIFTEEN_MINUTE",
  "dimensions": ["store_id", "department"],
  "aggregations": [
    { "type": "longSum", "name": "units", "fieldName": "units_sold" },
    { "type": "longSum", "name": "revenue", "fieldName": "revenue_cents" },
    { "type": "count", "name": "txn_count" },
    { "type": "HLLSketchMerge", "name": "customers", "fieldName": "unique_customers" }
  ],
  "postAggregations": [
    {
      "type": "arithmetic", "name": "avg_basket_value", "fn": "/",
      "fields": [
        { "type": "fieldAccess", "fieldName": "revenue" },
        { "type": "fieldAccess", "fieldName": "txn_count" }
      ]
    }
  ],
  "limitSpec": {
    "type": "default", "limit": 100,
    "columns": [{ "dimension": "revenue", "direction": "descending" }]
  }
}

// Inventory stockout alert
{
  "queryType": "scan",
  "dataSource": "target_sales_inventory",
  "intervals": ["2024-01-15T09:00:00/2024-01-15T10:00:00"],
  "filter": {
    "type": "and",
    "fields": [
      { "type": "bound", "dimension": "inventory_on_hand", "upper": "5", "ordering": "numeric" },
      { "type": "bound", "dimension": "units_sold", "lower": "50", "ordering": "numeric" }
    ]
  },
  "columns": ["store_id", "sku", "inventory_on_hand", "units_sold"],
  "limit": 500
}
```

### Scale Numbers
| Metric | Value |
|--------|-------|
| Transactions/sec | 100K+ (peak Black Friday: 500K) |
| Stores | 1,900+ |
| SKUs | 500K+ |
| Events/day | 8B |
| After rollup | 500M rows/day |
| Query latency (p50) | 80ms |
| Query latency (p99) | 500ms |
| Historical nodes | 20 (mix hot/cold) |
| Deep storage | S3 (~80TB) |
| Retention | 14 days hot, 2 years cold |

---

## Replication

### Segment Replication Across Historicals
```
Coordinator Replication Logic:
┌────────────────────────────────────────────────────────┐
│                  Coordinator                            │
│                                                        │
│  Load Rules:                                           │
│  ┌──────────────────────────────────────────────────┐  │
│  │ Rule 1: Load Forever, Tier=_default, Replicas=2  │  │
│  │ Rule 2: Period P7D, Tier=hot, Replicas=3         │  │
│  │ Rule 3: Period P90D, Tier=cold, Replicas=1       │  │
│  │ Rule 4: Drop Forever                             │  │
│  └──────────────────────────────────────────────────┘  │
│                                                        │
│  Segment Placement:                                    │
│  segment_2024-01-15_hour_01                            │
│    → Historical-Hot-1 (replica 1)                      │
│    → Historical-Hot-2 (replica 2)                      │
│    → Historical-Hot-3 (replica 3)                      │
│                                                        │
│  segment_2023-11-01_hour_01                            │
│    → Historical-Cold-1 (replica 1)                     │
└────────────────────────────────────────────────────────┘
```

### Deep Storage as Source of Truth
```
┌─────────────────────────────────────────────┐
│              Deep Storage (S3)               │
│                                             │
│  s3://druid-deep-storage/                   │
│    datasource/                              │
│      2024-01-15T00:00:00.000Z_             │
│        2024-01-15T01:00:00.000Z/           │
│          0/                                 │
│            index.zip (segment file)         │
│            descriptor.json                  │
│                                             │
│  Properties:                                │
│  - 11 nines durability (S3)                 │
│  - All segments persisted before visible    │
│  - Historical can re-download if lost       │
│  - Coordinator knows all segments via       │
│    metadata store                           │
└─────────────────────────────────────────────┘

Recovery Flow:
  Historical crashes → restarts → checks local cache
    → missing segments downloaded from S3
    → Coordinator reassigns segments to other nodes meanwhile
```

### Historical Tiered Storage (Hot/Cold)
```
Configuration (runtime.properties):

# Hot tier historicals
druid.server.tier=hot
druid.server.priority=10
druid.segmentCache.locations=[{"path":"/mnt/nvme/druid","maxSize":"500G"}]
druid.server.maxSize=500000000000

# Cold tier historicals  
druid.server.tier=cold
druid.server.priority=5
druid.segmentCache.locations=[{"path":"/mnt/hdd/druid","maxSize":"2T"}]
druid.server.maxSize=2000000000000

Load Rules (via Coordinator API):
[
  {
    "type": "loadByPeriod",
    "period": "P7D",
    "tieredReplicants": { "hot": 2 },
    "useDefaultTierForNull": false
  },
  {
    "type": "loadByPeriod", 
    "period": "P90D",
    "tieredReplicants": { "cold": 1 },
    "useDefaultTierForNull": false
  },
  { "type": "dropForever" }
]
```

### Ingestion HA
```
Kafka Indexing Service HA:
┌─────────────────────────────────────────────┐
│  Supervisor Config:                          │
│    replicas: 2                               │
│    taskCount: 6                              │
│                                              │
│  Result: 12 tasks total                      │
│    - 6 primary tasks (one per Kafka partition)│
│    - 6 replica tasks (redundant)             │
│                                              │
│  Failure handling:                           │
│    - Task fails → Overlord restarts          │
│    - MiddleManager fails → tasks reassigned  │
│    - Kafka offsets committed only after      │
│      segment published to deep storage       │
│    - Exactly-once via Kafka transaction IDs  │
└─────────────────────────────────────────────┘

Overlord HA:
  - Multiple Overlords with ZK leader election
  - Standby takes over in <30s
  - Task state in metadata store (MySQL/PG)
```

---

## Scalability

### Architecture Tiers Diagram
```
                    ┌─────────────────────┐
                    │    Load Balancer     │
                    └──────────┬──────────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                │
    ┌─────────▼──────┐  ┌─────▼──────┐  ┌─────▼──────┐
    │   Router Node  │  │Router Node │  │Router Node │
    │  (optional)    │  │            │  │            │
    └─────────┬──────┘  └─────┬──────┘  └─────┬──────┘
              │                │                │
    ┌─────────▼────────────────▼────────────────▼─────────┐
    │                    QUERY TIER                         │
    │  ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐    │
    │  │Broker 1│  │Broker 2│  │Broker 3│  │Broker 4│    │
    │  │ 32GB   │  │ 32GB   │  │ 32GB   │  │ 32GB   │    │
    │  └────┬───┘  └────┬───┘  └────┬───┘  └────┬───┘    │
    └───────┼────────────┼────────────┼────────────┼───────┘
            │            │            │            │
    ┌───────▼────────────▼────────────▼────────────▼───────┐
    │                    DATA TIER                          │
    │                                                      │
    │  Historical (Hot):     Historical (Cold):            │
    │  ┌──────┐ ┌──────┐    ┌──────┐ ┌──────┐            │
    │  │256GB │ │256GB │    │ 64GB │ │ 64GB │            │
    │  │NVMe  │ │NVMe  │    │ HDD  │ │ HDD  │            │
    │  └──────┘ └──────┘    └──────┘ └──────┘            │
    │                                                      │
    │  MiddleManagers:                                     │
    │  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐              │
    │  │ MM-1 │ │ MM-2 │ │ MM-3 │ │ MM-4 │              │
    │  │128GB │ │128GB │ │128GB │ │128GB │              │
    │  └──────┘ └──────┘ └──────┘ └──────┘              │
    └──────────────────────────────────────────────────────┘
            │
    ┌───────▼──────────────────────────────────────────────┐
    │                   MASTER TIER                         │
    │  ┌─────────────┐  ┌──────────┐  ┌────────────────┐  │
    │  │Coordinator  │  │ Overlord │  │ ZooKeeper x3   │  │
    │  │(HA pair)    │  │(HA pair) │  │                │  │
    │  └─────────────┘  └──────────┘  └────────────────┘  │
    │  ┌──────────────────────────────┐                    │
    │  │  Metadata Store (MySQL RDS)  │                    │
    │  └──────────────────────────────┘                    │
    └──────────────────────────────────────────────────────┘
```

### Segment Columnar Architecture
```
Query: SELECT SUM(revenue) WHERE country='US' AND date='2024-01-15'

Traditional Row Store:          Druid Columnar:
┌────┬─────┬───────┬─────┐    Only reads 2 columns:
│time│cntry│revenue│other│    ┌───────┐  ┌───────────┐
│ .. │ US  │  100  │ ... │    │country│  │  revenue  │
│ .. │ UK  │  200  │ ... │    │bitmap │  │  values   │
│ .. │ US  │  150  │ ... │    │index  │  │(compressed)│
│ .. │ IN  │   80  │ ... │    └───┬───┘  └─────┬─────┘
│... │ ... │  ...  │ ... │        │             │
└────┴─────┴───────┴─────┘        ▼             ▼
Reads ALL columns              "US" bitmap → filter → SUM
(100% I/O)                     (5% I/O, vectorized)
```

### Real-time Kafka Ingestion Scaling
```
Scaling Kafka Indexing:

Kafka Topic: 64 partitions
  │
  ▼
Supervisor Config:
  taskCount: 16        (each task handles 4 partitions)
  replicas: 2          (32 tasks total)
  taskDuration: PT1H   (handoff every hour)

Throughput per task: ~100K events/sec
Total throughput: 1.6M events/sec

Scale up:
  - Increase taskCount (up to = partition count)
  - Add MiddleManager nodes
  - Increase Kafka partitions + taskCount together
  
Backpressure:
  - Tasks buffer in memory (maxRowsInMemory)
  - Persist to disk periodically
  - If behind: increase tasks or reduce rollup complexity
```

### Pre-aggregation (Rollup)
```
Without Rollup:
  1B raw events/day → 1B rows in Druid → slow queries

With Rollup (queryGranularity=MINUTE):
  1B raw events → 50M rolled-up rows → fast queries

Perfect Rollup (batch reindexing):
  Native batch task re-ingests with optimal rollup
  50M rows → 10M rows (additional dedup)

Rollup Trade-offs:
  ┌──────────────────────────────────────────┐
  │  More rollup = less storage + faster     │
  │  Less rollup = more flexibility          │
  │                                          │
  │  Cannot: query individual raw events     │
  │  Cannot: add new dimensions post-ingest  │
  │  Can: approximate counts (sketches)      │
  └──────────────────────────────────────────┘
```

### Multi-tenancy
```
Strategy 1: Separate datasources per tenant
  - Full isolation
  - Independent retention/rollup
  - Higher overhead (more segments)

Strategy 2: Shared datasource with tenant_id dimension
  - Efficient storage (shared rollup)
  - Use query filters
  - Risk: noisy neighbor

Strategy 3: Tiered brokers with query priorities
  ┌─────────────────────────────────────────┐
  │  Broker Config (per-tenant):            │
  │                                         │
  │  "priority_tenant_A": {                 │
  │    "maxQueuedQueries": 100,             │
  │    "maxConcurrent": 20,                 │
  │    "timeout": "PT30S"                   │
  │  },                                     │
  │  "standard_tier": {                     │
  │    "maxQueuedQueries": 50,              │
  │    "maxConcurrent": 5,                  │
  │    "timeout": "PT60S"                   │
  │  }                                      │
  └─────────────────────────────────────────┘
```

### Compaction
```json
// Auto-compaction config
{
  "dataSource": "my_datasource",
  "taskPriority": 25,
  "inputSegmentSizeBytes": 419430400,
  "maxRowsPerSegment": 5000000,
  "skipOffsetFromLatest": "PT1H",
  "tuningConfig": {
    "type": "index_parallel",
    "maxNumConcurrentSubTasks": 4,
    "partitionsSpec": {
      "type": "hashed",
      "numShards": null,
      "targetRowsPerSegment": 5000000
    },
    "forceGuaranteedRollup": true
  },
  "granularitySpec": {
    "segmentGranularity": "DAY",
    "queryGranularity": "MINUTE"
  }
}
```

Benefits:
- Merges small real-time segments into optimal large segments
- Achieves perfect rollup (better compression)
- Reduces segment count (less coordinator overhead)
- Runs as background tasks during low-traffic periods

---

## Production Setup

### Node Sizing Recommendations

| Node Type | CPU | RAM | Storage | Count | Notes |
|-----------|-----|-----|---------|-------|-------|
| Broker | 16 cores | 32-64GB | 100GB SSD | 3-6 | Heap=12GB, direct=20GB+ |
| Historical (Hot) | 16 cores | 128-256GB | 1-2TB NVMe | 6-20 | Heap=12GB, direct=rest |
| Historical (Cold) | 8 cores | 32-64GB | 4-10TB HDD | 4-12 | Heap=8GB |
| MiddleManager | 16 cores | 128GB | 500GB SSD | 4-8 | Per-peon: heap=1GB |
| Coordinator | 8 cores | 16GB | 50GB | 2 (HA) | Heap=12GB |
| Overlord | 8 cores | 16GB | 50GB | 2 (HA) | Heap=12GB |
| Router | 4 cores | 8GB | 50GB | 2-3 | Heap=4GB |

### ZooKeeper & Metadata Configuration
```properties
# common/runtime.properties

# ZooKeeper
druid.zk.service.host=zk-1:2181,zk-2:2181,zk-3:2181
druid.zk.paths.base=/druid
druid.zk.service.sessionTimeoutMs=30000

# Metadata Store (MySQL RDS recommended for production)
druid.metadata.storage.type=mysql
druid.metadata.storage.connector.connectURI=jdbc:mysql://druid-metadata.cluster-xyz.us-east-1.rds.amazonaws.com:3306/druid
druid.metadata.storage.connector.user=druid
druid.metadata.storage.connector.password=${METADATA_PASSWORD}
druid.metadata.storage.connector.createTables=true

# Connection pool
druid.metadata.storage.connector.dbcp.maxTotal=20
druid.metadata.storage.connector.dbcp.maxIdle=5
```

### Deep Storage (S3) Configuration
```properties
# Deep Storage
druid.storage.type=s3
druid.storage.bucket=my-druid-deep-storage
druid.storage.baseKey=druid/segments
druid.s3.accessKey=${AWS_ACCESS_KEY}
druid.s3.secretKey=${AWS_SECRET_KEY}

# Or use IAM role (preferred):
druid.s3.sse.type=s3
druid.storage.archiveBucket=my-druid-archive

# Indexer logs
druid.indexer.logs.type=s3
druid.indexer.logs.s3Bucket=my-druid-deep-storage
druid.indexer.logs.s3Prefix=druid/indexing-logs
```

### Segment Granularity Guidelines
```
┌──────────────────────────────────────────────────────────┐
│  Data Volume/Day    │  Segment Granularity  │  Result    │
├─────────────────────┼───────────────────────┼────────────┤
│  < 100M rows        │  DAY                  │  ~1 seg    │
│  100M - 1B rows     │  HOUR                 │  ~24 segs  │
│  1B - 10B rows      │  HOUR + partitions    │  ~100 segs │
│  > 10B rows         │  15MIN + partitions   │  ~400 segs │
└──────────────────────────────────────────────────────────┘

Target: 300MB-700MB per segment (compressed)
Too small: coordinator overhead, excessive merging
Too large: slow queries, memory pressure on historicals
```

### Query Caching
```properties
# Broker cache (result-level)
druid.broker.cache.useCache=true
druid.broker.cache.populateCache=true
druid.broker.cache.type=caffeine
druid.broker.cache.sizeInBytes=2147483648  # 2GB
druid.broker.cache.expireAfter=3600000     # 1 hour

# Historical cache (segment-level)  
druid.historical.cache.useCache=true
druid.historical.cache.populateCache=true
druid.historical.cache.type=caffeine
druid.historical.cache.sizeInBytes=1073741824  # 1GB

# Cache effectiveness for time-series:
#   Immutable historical segments → high hit rate (80%+)
#   Real-time segments → not cached (always changing)
```

### Monitoring Setup
```yaml
# Druid emits metrics to various sinks
# runtime.properties:
druid.monitoring.monitors=["org.apache.druid.server.metrics.QueryCountStatsMonitor","org.apache.druid.server.metrics.ServiceStatusMonitor","org.apache.druid.java.util.metrics.JvmMonitor","org.apache.druid.java.util.metrics.JvmCpuMonitor","org.apache.druid.java.util.metrics.JvmThreadsMonitor"]
druid.emitter=composing
druid.emitter.composing.emitters=["logging","prometheus"]
druid.emitter.prometheus.port=9090
druid.emitter.prometheus.namespace=druid

# Key metrics to alert on:
# ┌──────────────────────────────────────────────────────┐
# │ Metric                        │ Alert Threshold      │
# ├───────────────────────────────┼──────────────────────┤
# │ query/time (p99)              │ > 5000ms             │
# │ query/failed/count            │ > 0                  │
# │ segment/unavailable/count     │ > 0                  │
# │ jvm/mem/used (% of max)       │ > 85%               │
# │ segment/underReplicated/count │ > 0                  │
# │ ingest/events/thrownAway      │ > 1000/min           │
# │ task/run/time                  │ > taskDuration * 2  │
# │ segment/size (avg)            │ > 700MB or < 100MB  │
# └───────────────────────────────┴──────────────────────┘
```

---

## Query Latency Benchmarks

### By Query Type (production clusters, 1B+ rows scanned)

| Query Type | p50 | p90 | p99 | Notes |
|-----------|-----|-----|-----|-------|
| Timeseries (1 metric, 1 day) | 15ms | 40ms | 100ms | Single segment scan |
| Timeseries (5 metrics, 7 days) | 50ms | 120ms | 300ms | Parallel segment scan |
| TopN (1000 values) | 30ms | 80ms | 200ms | Optimized single-dim |
| GroupBy (2 dims, low card) | 80ms | 200ms | 500ms | Merge on broker |
| GroupBy (3 dims, high card) | 200ms | 600ms | 2000ms | Memory-intensive |
| Scan (raw rows, 1000 limit) | 20ms | 50ms | 150ms | Direct segment read |
| Theta sketch intersect | 100ms | 250ms | 700ms | Sketch merge cost |
| SQL (simple WHERE) | 50ms | 120ms | 350ms | Native translation |
| SQL (JOIN with lookup) | 80ms | 200ms | 500ms | Lookup in-memory |

### By Data Scale

| Rows Scanned | Segments Hit | Avg Latency | Notes |
|-------------|-------------|-------------|-------|
| 1M | 1-2 | 10-20ms | Single historical |
| 100M | 10-20 | 50-100ms | Parallel across nodes |
| 1B | 50-100 | 100-300ms | Full cluster engaged |
| 10B | 200+ | 300-800ms | Needs good rollup |
| 100B | 1000+ | 1-5s | Consider pre-computation |

### Optimization Impact

| Optimization | Before | After | Improvement |
|-------------|--------|-------|-------------|
| Enable rollup (50:1) | 2000ms | 200ms | 10x |
| Add bitmap index filter | 500ms | 50ms | 10x |
| Result cache hit | 100ms | 5ms | 20x |
| Segment granularity tuning | 800ms | 200ms | 4x |
| Historical tier (SSD) | 300ms | 80ms | 3.7x |
| Broker-side merge optimization | 400ms | 150ms | 2.7x |
| Theta sketch vs exact distinct | 5000ms | 100ms | 50x |

---

## Summary: When to Use Apache Druid

**Ideal for:**
- Sub-second OLAP on event-level data
- Real-time streaming + historical batch in one system
- High-concurrency dashboards (1000s of users)
- Time-series with rich dimensions
- Approximate analytics (sketches) at massive scale

**Not ideal for:**
- Full-text search (use Elasticsearch)
- Point lookups by key (use Cassandra/DynamoDB)
- Transactions / ACID (use PostgreSQL)
- Ad-hoc complex JOINs (use Spark/Presto)
- Small data < 10M rows (overkill)
