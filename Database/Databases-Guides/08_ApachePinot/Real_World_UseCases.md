# Apache Pinot - Real World Use Cases & Production Guide

## Table of Contents
- [Use Case 1: LinkedIn Feed Analytics](#use-case-1-linkedin-feed-analytics)
- [Use Case 2: Uber Real-time Marketplace](#use-case-2-ubers-real-time-marketplace)
- [Use Case 3: Stripe Dashboard Analytics](#use-case-3-stripe-dashboard-analytics)
- [Use Case 4: Walmart Search Analytics](#use-case-4-walmart-search-analytics)
- [Use Case 5: Instacart Ad Performance](#use-case-5-instacart-ad-performance)
- [Replication](#replication)
- [Scalability](#scalability)
- [Production Setup](#production-setup)
- [Core Concepts](#core-concepts)

---

## Use Case 1: LinkedIn Feed Analytics

### Problem Statement
LinkedIn's "Who Viewed Your Profile" and content analytics process **billions of events per day** across 900M+ members. Requirements: sub-second query latency on fresh data (seconds-old), high write throughput, and interactive slice-and-dice analytics.

### Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        LinkedIn Feed Analytics                           │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────┐    ┌──────────────┐    ┌────────────────────────────┐    │
│  │ Tracking │───>│    Kafka     │───>│     Apache Pinot Cluster    │    │
│  │  Events  │    │  (Profile    │    │                            │    │
│  │(Billions)│    │   Views,     │    │  ┌──────────────────────┐  │    │
│  └──────────┘    │   Likes,     │    │  │    Controller (x3)   │  │    │
│                  │   Shares)    │    │  │  - Helix management  │  │    │
│  ┌──────────┐    └──────┬───────┘    │  │  - Segment assign    │  │    │
│  │  Hadoop  │           │            │  └──────────────────────┘  │    │
│  │  (Daily  │───────────┼──────┐     │                            │    │
│  │  Batch)  │           │      │     │  ┌──────────────────────┐  │    │
│  └──────────┘           │      │     │  │    Broker (x20)      │  │    │
│                         │      │     │  │  - Query routing     │  │    │
│                         ▼      ▼     │  │  - Scatter-gather    │  │    │
│                    ┌─────────────┐    │  └──────────┬───────────┘  │    │
│                    │  Real-time  │    │             │              │    │
│                    │  + Offline  │    │  ┌──────────▼───────────┐  │    │
│                    │   Tables    │    │  │    Server (x200+)    │  │    │
│                    └─────────────┘    │  │  - Segment storage   │  │    │
│                                      │  │  - Query execution   │  │    │
│  ┌──────────┐                        │  └──────────────────────┘  │    │
│  │  Member  │<── Query ──────────────│                            │    │
│  │Dashboard │   (< 100ms P99)        │  ┌──────────────────────┐  │    │
│  └──────────┘                        │  │    Minion (x10)      │  │    │
│                                      │  │  - Segment merge     │  │    │
│                                      │  │  - Purge tasks       │  │    │
│                                      │  └──────────────────────┘  │    │
│                                      └────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────┘
```

### Table Schema

```json
{
  "tableName": "profileViews",
  "tableType": "REALTIME",
  "segmentsConfig": {
    "replication": "3",
    "retentionTimeUnit": "DAYS",
    "retentionTimeValue": "90",
    "segmentPushType": "APPEND"
  },
  "tableIndexConfig": {
    "sortedColumn": ["viewerMemberId"],
    "invertedIndexColumns": ["viewedMemberId", "viewerIndustry", "viewerCountry"],
    "starTreeIndexConfigs": [{
      "dimensionsSplitOrder": ["viewedMemberId", "viewerCountry", "viewerIndustry"],
      "functionColumnPairs": ["COUNT__*", "SUM__viewDurationMs"],
      "maxLeafRecords": 10000
    }]
  },
  "schema": {
    "schemaName": "profileViews",
    "dimensionFieldSpecs": [
      {"name": "viewerMemberId", "dataType": "LONG"},
      {"name": "viewedMemberId", "dataType": "LONG"},
      {"name": "viewerCompany", "dataType": "STRING"},
      {"name": "viewerTitle", "dataType": "STRING"},
      {"name": "viewerIndustry", "dataType": "STRING"},
      {"name": "viewerCountry", "dataType": "STRING"},
      {"name": "viewSource", "dataType": "STRING"},
      {"name": "deviceType", "dataType": "STRING"}
    ],
    "metricFieldSpecs": [
      {"name": "viewDurationMs", "dataType": "LONG"},
      {"name": "viewCount", "dataType": "INT"}
    ],
    "dateTimeFieldSpecs": [{
      "name": "eventTimestamp",
      "dataType": "LONG",
      "format": "1:MILLISECONDS:EPOCH",
      "granularity": "1:MILLISECONDS"
    }]
  }
}
```

### Ingestion Config

**Real-time (Kafka):**
```json
{
  "streamConfigs": {
    "streamType": "kafka",
    "stream.kafka.topic.name": "tracking.profile-views",
    "stream.kafka.broker.list": "kafka-broker01:9092,kafka-broker02:9092",
    "stream.kafka.consumer.type": "lowlevel",
    "stream.kafka.consumer.prop.auto.offset.reset": "smallest",
    "stream.kafka.decoder.class.name": "org.apache.pinot.plugin.stream.kafka.KafkaAvroMessageDecoder",
    "realtime.segment.flush.threshold.rows": "500000",
    "realtime.segment.flush.threshold.time": "6h",
    "stream.kafka.consumer.prop.group.id": "pinot-profile-views"
  }
}
```

**Offline (Batch from Hadoop):**
```json
{
  "jobType": "SegmentCreationAndTarPush",
  "inputDirURI": "hdfs://namenode/data/profile_views/daily/",
  "outputDirURI": "hdfs://namenode/pinot_segments/profile_views/",
  "pinotClusterSpecs": [{
    "controllerURI": "http://pinot-controller:9000"
  }],
  "pushJobSpec": {
    "pushAttempts": 3,
    "pushParallelism": 5
  },
  "segmentNameGeneratorSpec": {
    "type": "normalizedDate",
    "configs": {
      "segment.name.prefix": "profileViews_OFFLINE"
    }
  }
}
```

### Query Patterns

```sql
-- Who viewed my profile (last 7 days, grouped by industry)
SELECT viewerIndustry, COUNT(*) as viewCount, 
       SUM(viewDurationMs) as totalDuration
FROM profileViews
WHERE viewedMemberId = 12345678
  AND eventTimestamp > ago('P7D')
GROUP BY viewerIndustry
ORDER BY viewCount DESC
LIMIT 10

-- Profile view trends (hits star-tree index)
SELECT DATETIMECONVERT(eventTimestamp, '1:MILLISECONDS:EPOCH', 
       '1:HOURS:EPOCH', '1:HOURS') as hourBucket,
       COUNT(*) as views
FROM profileViews
WHERE viewedMemberId = 12345678
  AND eventTimestamp > ago('P30D')
GROUP BY hourBucket
ORDER BY hourBucket

-- Content engagement analytics
SELECT viewSource, deviceType, 
       AVG(viewDurationMs) as avgDuration,
       COUNT(*) as totalViews
FROM profileViews
WHERE viewedMemberId = 12345678
GROUP BY viewSource, deviceType
```

### Scale Numbers

| Metric | Value |
|--------|-------|
| Events/day | 200B+ |
| Queries/second | 200K+ |
| P50 latency | 5ms |
| P99 latency | 50ms |
| Total data | 100TB+ |
| Servers | 1000+ |
| Tables | 50+ |
| Fresh data availability | < 3 seconds |

---

## Use Case 2: Uber's Real-time Marketplace

### Problem Statement
Uber needs real-time visibility into marketplace health: driver supply, rider demand, surge pricing, ETA accuracy, and trip metrics. Engineers and city ops teams query dashboards with **sub-second latency** across millions of concurrent trips.

### Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    Uber Marketplace Analytics                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌───────────┐   ┌───────────┐   ┌───────────┐                        │
│  │  Driver   │   │   Rider   │   │   Trip    │                        │
│  │  Events   │   │  Events   │   │  Events   │                        │
│  └─────┬─────┘   └─────┬─────┘   └─────┬─────┘                        │
│        │               │               │                               │
│        ▼               ▼               ▼                               │
│  ┌─────────────────────────────────────────────┐                       │
│  │            Apache Kafka                      │                       │
│  │  (marketplace-supply, marketplace-demand,    │                       │
│  │   trip-events, surge-events)                 │                       │
│  └────────────────────┬────────────────────────┘                       │
│                       │                                                 │
│                       ▼                                                 │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                   Apache Pinot Cluster                           │   │
│  │                                                                  │   │
│  │  ┌─────────────┐  ┌──────────────┐  ┌────────────────────────┐ │   │
│  │  │ Controller  │  │   Broker     │  │      Server            │ │   │
│  │  │   (x3 HA)  │  │   (x15)     │  │      (x150)           │ │   │
│  │  │             │  │             │  │                        │ │   │
│  │  │ -Ideal state│  │ -Routing    │  │ -Real-time tables:    │ │   │
│  │  │ -Rebalance │  │  table      │  │  trip_events_RT       │ │   │
│  │  │ -Schema mgmt│  │ -Reduce    │  │  supply_metrics_RT    │ │   │
│  │  │             │  │  scatter   │  │  demand_metrics_RT    │ │   │
│  │  └─────────────┘  └──────────────┘  │                        │ │   │
│  │                                      │ -Offline tables:      │ │   │
│  │  ┌─────────────┐                    │  trip_events_OFFLINE   │ │   │
│  │  │   Minion    │                    │  surge_history_OFFLINE │ │   │
│  │  │   (x5)     │                    └────────────────────────┘ │   │
│  │  │ -Merge RT  │                                               │   │
│  │  │  segments  │         ┌──────────────────────┐              │   │
│  │  │ -Compact   │         │    Deep Store (S3)    │              │   │
│  │  └─────────────┘         │  - Segment backup    │              │   │
│  │                          │  - Offline segments  │              │   │
│  └──────────────────────────└──────────────────────┘──────────────┘   │
│                                                                         │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐             │
│  │  Ops Portal  │    │  Eng Dash    │    │  ML Feature  │             │
│  │  (City Ops)  │    │  (Grafana)   │    │   Store      │             │
│  └──────────────┘    └──────────────┘    └──────────────┘             │
└─────────────────────────────────────────────────────────────────────────┘
```

### Table Schema

```json
{
  "schemaName": "tripEvents",
  "dimensionFieldSpecs": [
    {"name": "tripId", "dataType": "STRING"},
    {"name": "driverId", "dataType": "LONG"},
    {"name": "riderId", "dataType": "LONG"},
    {"name": "cityId", "dataType": "INT"},
    {"name": "vehicleType", "dataType": "STRING"},
    {"name": "tripStatus", "dataType": "STRING"},
    {"name": "geoHash", "dataType": "STRING"},
    {"name": "surgeMultiplier", "dataType": "FLOAT"}
  ],
  "metricFieldSpecs": [
    {"name": "fareAmount", "dataType": "DOUBLE"},
    {"name": "tripDistanceKm", "dataType": "DOUBLE"},
    {"name": "tripDurationSec", "dataType": "INT"},
    {"name": "waitTimeSec", "dataType": "INT"},
    {"name": "etaAccuracySec", "dataType": "INT"},
    {"name": "driverEarnings", "dataType": "DOUBLE"}
  ],
  "dateTimeFieldSpecs": [{
    "name": "tripTimestamp",
    "dataType": "LONG",
    "format": "1:MILLISECONDS:EPOCH",
    "granularity": "1:MILLISECONDS"
  }]
}
```

### Ingestion Config

```json
{
  "streamConfigs": {
    "streamType": "kafka",
    "stream.kafka.topic.name": "marketplace.trip-events",
    "stream.kafka.broker.list": "kafka01:9092,kafka02:9092,kafka03:9092",
    "stream.kafka.consumer.type": "lowlevel",
    "stream.kafka.consumer.prop.auto.offset.reset": "largest",
    "stream.kafka.decoder.class.name": "org.apache.pinot.plugin.stream.kafka.KafkaJSONMessageDecoder",
    "realtime.segment.flush.threshold.rows": "1000000",
    "realtime.segment.flush.threshold.time": "4h",
    "realtime.segment.flush.threshold.segment.size": "200M"
  }
}
```

### Query Patterns

```sql
-- Real-time supply/demand by geo
SELECT geoHash, 
       COUNTIF(tripStatus = 'AVAILABLE') as availableDrivers,
       COUNTIF(tripStatus = 'REQUESTED') as pendingRequests,
       AVG(waitTimeSec) as avgWaitTime
FROM tripEvents
WHERE cityId = 42
  AND tripTimestamp > ago('PT5M')
GROUP BY geoHash

-- Surge analysis
SELECT DATETIMECONVERT(tripTimestamp, '1:MILLISECONDS:EPOCH',
       '1:MINUTES:EPOCH', '5:MINUTES') as timeBucket,
       AVG(surgeMultiplier) as avgSurge,
       COUNT(*) as tripCount
FROM tripEvents
WHERE cityId = 42 AND tripTimestamp > ago('PT1H')
GROUP BY timeBucket
ORDER BY timeBucket

-- ETA accuracy monitoring
SELECT vehicleType,
       PERCENTILEEST(etaAccuracySec, 50) as p50_eta_error,
       PERCENTILEEST(etaAccuracySec, 99) as p99_eta_error,
       COUNT(*) as trips
FROM tripEvents
WHERE tripTimestamp > ago('PT1H')
GROUP BY vehicleType
```

### Scale Numbers

| Metric | Value |
|--------|-------|
| Events/second | 2M+ |
| Queries/second | 100K+ |
| P50 latency | 10ms |
| P99 latency | 80ms |
| Active tables | 30+ |
| Data freshness | < 1 second |
| Peak concurrent trips | 5M+ |

---

## Use Case 3: Stripe Dashboard Analytics

### Problem Statement
Stripe provides merchants with real-time analytics on payments, refunds, disputes, and revenue. Merchants expect instant dashboards showing current business metrics with ability to filter by product, currency, card type, and time range.

### Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    Stripe Payment Analytics                              │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌────────────────────────────────────────────┐                        │
│  │          Payment Processing Pipeline        │                        │
│  │                                            │                        │
│  │  Charge ──> Success/Fail ──> Settlement    │                        │
│  │  Refund ──> Dispute ──> Payout             │                        │
│  └──────────────────┬─────────────────────────┘                        │
│                     │                                                   │
│                     ▼                                                   │
│  ┌──────────────────────────────────────────────┐                      │
│  │  Kafka Topics                                 │                      │
│  │  - payments.charges     (50K events/sec)     │                      │
│  │  - payments.refunds     (5K events/sec)      │                      │
│  │  - payments.disputes    (1K events/sec)      │                      │
│  │  - payments.payouts     (10K events/sec)     │                      │
│  └──────────────────┬───────────────────────────┘                      │
│                     │                                                   │
│    ┌────────────────┼────────────────────────────────┐                 │
│    │                ▼      Pinot Cluster              │                 │
│    │  ┌───────────────────────────────────────────┐  │                 │
│    │  │ Controller (x3) │ Broker (x10) │ ZK (x3) │  │                 │
│    │  └───────────────────────────────────────────┘  │                 │
│    │                                                  │                 │
│    │  ┌────────────────────────────────────────────┐ │                 │
│    │  │        Servers (x80)                       │ │                 │
│    │  │                                            │ │                 │
│    │  │  Tenant: merchant_analytics                │ │                 │
│    │  │  ┌──────────────────────────────────────┐  │ │                 │
│    │  │  │ charges_REALTIME (consuming segments)│  │ │                 │
│    │  │  │ charges_OFFLINE  (completed segments)│  │ │                 │
│    │  │  │ refunds_REALTIME                     │  │ │                 │
│    │  │  │ disputes_REALTIME                    │  │ │                 │
│    │  │  │ payouts_REALTIME                     │  │ │                 │
│    │  │  └──────────────────────────────────────┘  │ │                 │
│    │  │                                            │ │                 │
│    │  │  Indexes: sorted(merchantId),              │ │                 │
│    │  │           inverted(currency, cardBrand),    │ │                 │
│    │  │           range(amount),                    │ │                 │
│    │  │           starTree(merchantId+currency)     │ │                 │
│    │  └────────────────────────────────────────────┘ │                 │
│    │                                                  │                 │
│    │  ┌────────────────────┐                         │                 │
│    │  │ Minion (x3)        │                         │                 │
│    │  │ - RealtimeToOffline│                         │                 │
│    │  │ - Segment purge    │                         │                 │
│    │  └────────────────────┘                         │                 │
│    └─────────────────────────────────────────────────┘                 │
│                     │                                                   │
│                     ▼                                                   │
│    ┌────────────────────────────────────┐                              │
│    │    Stripe Merchant Dashboard        │                              │
│    │    - Revenue charts                 │                              │
│    │    - Success rates                  │                              │
│    │    - Dispute tracking               │                              │
│    └────────────────────────────────────┘                              │
└─────────────────────────────────────────────────────────────────────────┘
```

### Table Schema

```json
{
  "schemaName": "charges",
  "dimensionFieldSpecs": [
    {"name": "chargeId", "dataType": "STRING"},
    {"name": "merchantId", "dataType": "STRING"},
    {"name": "customerId", "dataType": "STRING"},
    {"name": "currency", "dataType": "STRING"},
    {"name": "cardBrand", "dataType": "STRING"},
    {"name": "cardCountry", "dataType": "STRING"},
    {"name": "paymentMethod", "dataType": "STRING"},
    {"name": "status", "dataType": "STRING"},
    {"name": "productId", "dataType": "STRING"},
    {"name": "declineReason", "dataType": "STRING"},
    {"name": "riskScore", "dataType": "STRING"}
  ],
  "metricFieldSpecs": [
    {"name": "amount", "dataType": "LONG"},
    {"name": "fee", "dataType": "LONG"},
    {"name": "netAmount", "dataType": "LONG"},
    {"name": "refundedAmount", "dataType": "LONG"}
  ],
  "dateTimeFieldSpecs": [{
    "name": "chargeTimestamp",
    "dataType": "LONG",
    "format": "1:MILLISECONDS:EPOCH",
    "granularity": "1:MILLISECONDS"
  }]
}
```

### Ingestion Config

```json
{
  "streamConfigs": {
    "streamType": "kafka",
    "stream.kafka.topic.name": "payments.charges",
    "stream.kafka.broker.list": "kafka-payments-01:9092,kafka-payments-02:9092",
    "stream.kafka.consumer.type": "lowlevel",
    "stream.kafka.decoder.class.name": "org.apache.pinot.plugin.stream.kafka.KafkaProtobufMessageDecoder",
    "stream.kafka.decoder.prop.descriptorFile": "charges.desc",
    "realtime.segment.flush.threshold.rows": "250000",
    "realtime.segment.flush.threshold.time": "2h"
  },
  "tierConfigs": [{
    "name": "coldTier",
    "segmentSelectorType": "time",
    "segmentAge": "7d",
    "storageType": "pinot_server",
    "serverTag": "cold_OFFLINE"
  }]
}
```

### Query Patterns

```sql
-- Merchant revenue dashboard
SELECT DATETIMECONVERT(chargeTimestamp, '1:MILLISECONDS:EPOCH',
       '1:DAYS:EPOCH', '1:DAYS') as day,
       currency,
       SUM(amount) as grossVolume,
       SUM(fee) as totalFees,
       SUM(netAmount) as netRevenue,
       COUNT(*) as transactionCount,
       COUNTIF(status = 'succeeded') * 100.0 / COUNT(*) as successRate
FROM charges
WHERE merchantId = 'acct_1234'
  AND chargeTimestamp > ago('P30D')
GROUP BY day, currency
ORDER BY day DESC

-- Real-time decline analysis
SELECT declineReason, cardBrand,
       COUNT(*) as declineCount,
       AVG(amount) as avgDeclinedAmount
FROM charges
WHERE merchantId = 'acct_1234'
  AND status = 'failed'
  AND chargeTimestamp > ago('PT1H')
GROUP BY declineReason, cardBrand
ORDER BY declineCount DESC

-- Fraud risk monitoring
SELECT riskScore, COUNT(*) as cnt,
       SUM(amount) as totalAmount
FROM charges
WHERE chargeTimestamp > ago('PT15M')
  AND status = 'succeeded'
GROUP BY riskScore
```

### Scale Numbers

| Metric | Value |
|--------|-------|
| Payments/second | 50K+ |
| Merchants querying | Millions |
| P50 latency | 15ms |
| P99 latency | 100ms |
| Data retention | 2 years |
| Total data | 50TB+ |
| Freshness | < 2 seconds |

---

## Use Case 4: Walmart Search Analytics

### Problem Statement
Walmart's e-commerce search handles billions of queries, needing real-time analytics on search relevance, click-through rates, null result rates, and conversion funnels to continuously improve search quality.

### Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    Walmart Search Analytics                              │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐         │
│  │  Search  │    │  Click   │    │  Add to  │    │ Purchase │         │
│  │  Query   │    │  Event   │    │   Cart   │    │  Event   │         │
│  └────┬─────┘    └────┬─────┘    └────┬─────┘    └────┬─────┘         │
│       │               │               │               │                │
│       ▼               ▼               ▼               ▼                │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                   Kafka (Confluent)                              │   │
│  │  search-queries │ search-clicks │ cart-events │ purchase-events │   │
│  └────────────────────────────────┬────────────────────────────────┘   │
│                                   │                                     │
│  ┌────────────────────────────────▼────────────────────────────────┐   │
│  │                    Pinot Cluster                                  │   │
│  │                                                                  │   │
│  │  ┌────────────┐   ┌─────────────┐   ┌───────────────────────┐  │   │
│  │  │Controller  │   │  Broker     │   │    Server (x120)      │  │   │
│  │  │  (x3)     │   │  (x12)     │   │                       │  │   │
│  │  │           │   │            │   │  Tenant: search_team  │  │   │
│  │  │           │   │  Routing:  │   │                       │  │   │
│  │  │           │   │  balanced  │   │  search_queries_RT    │  │   │
│  │  │           │   │            │   │  search_clicks_RT     │  │   │
│  │  └────────────┘   └─────────────┘   │  search_funnels_RT   │  │   │
│  │                                      │                       │  │   │
│  │                                      │  Indexes:             │  │   │
│  │  ┌────────────┐                     │  - text(queryText)    │  │   │
│  │  │  Minion    │                     │  - inverted(category) │  │   │
│  │  │  (x4)     │                     │  - sorted(timestamp)  │  │   │
│  │  │           │                     │  - json(attributes)   │  │   │
│  │  │ Segment   │                     └───────────────────────┘  │   │
│  │  │ merge +   │                                                 │   │
│  │  │ rollup    │         Deep Store: HDFS                        │   │
│  │  └────────────┘                                                │   │
│  └────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐             │
│  │ Search Eng   │    │  A/B Test    │    │  ML Model    │             │
│  │  Dashboard   │    │  Analytics   │    │  Feedback    │             │
│  └──────────────┘    └──────────────┘    └──────────────┘             │
└─────────────────────────────────────────────────────────────────────────┘
```

### Table Schema

```json
{
  "schemaName": "searchQueries",
  "dimensionFieldSpecs": [
    {"name": "queryId", "dataType": "STRING"},
    {"name": "sessionId", "dataType": "STRING"},
    {"name": "userId", "dataType": "LONG"},
    {"name": "queryText", "dataType": "STRING"},
    {"name": "normalizedQuery", "dataType": "STRING"},
    {"name": "category", "dataType": "STRING"},
    {"name": "department", "dataType": "STRING"},
    {"name": "platform", "dataType": "STRING"},
    {"name": "abTestGroup", "dataType": "STRING"},
    {"name": "searchAlgorithm", "dataType": "STRING"},
    {"name": "storeId", "dataType": "STRING"},
    {"name": "resultItemIds", "dataType": "STRING", "singleValueField": false}
  ],
  "metricFieldSpecs": [
    {"name": "resultCount", "dataType": "INT"},
    {"name": "responseTimeMs", "dataType": "INT"},
    {"name": "clickPosition", "dataType": "INT"},
    {"name": "clickCount", "dataType": "INT"},
    {"name": "addToCartCount", "dataType": "INT"},
    {"name": "purchaseCount", "dataType": "INT"},
    {"name": "revenue", "dataType": "DOUBLE"}
  ],
  "dateTimeFieldSpecs": [{
    "name": "searchTimestamp",
    "dataType": "LONG",
    "format": "1:MILLISECONDS:EPOCH",
    "granularity": "1:MILLISECONDS"
  }]
}
```

### Ingestion Config

```json
{
  "streamConfigs": {
    "streamType": "kafka",
    "stream.kafka.topic.name": "search.query-events",
    "stream.kafka.broker.list": "kafka-search-01:9092,kafka-search-02:9092",
    "stream.kafka.consumer.type": "lowlevel",
    "stream.kafka.decoder.class.name": "org.apache.pinot.plugin.stream.kafka.KafkaAvroMessageDecoder",
    "stream.kafka.decoder.prop.schema.registry.rest.url": "http://schema-registry:8081",
    "realtime.segment.flush.threshold.rows": "750000",
    "realtime.segment.flush.threshold.time": "3h"
  },
  "indexingConfig": {
    "textIndexColumns": ["queryText"],
    "jsonIndexColumns": ["attributes"]
  }
}
```

### Query Patterns

```sql
-- Null result rate monitoring
SELECT DATETIMECONVERT(searchTimestamp, '1:MILLISECONDS:EPOCH',
       '1:MINUTES:EPOCH', '5:MINUTES') as timeBucket,
       platform,
       COUNTIF(resultCount = 0) as nullResults,
       COUNT(*) as totalSearches,
       COUNTIF(resultCount = 0) * 100.0 / COUNT(*) as nullRate
FROM searchQueries
WHERE searchTimestamp > ago('PT1H')
GROUP BY timeBucket, platform
ORDER BY timeBucket DESC

-- Search-to-purchase funnel by A/B group
SELECT abTestGroup, searchAlgorithm,
       COUNT(*) as searches,
       SUM(clickCount) as clicks,
       SUM(addToCartCount) as carts,
       SUM(purchaseCount) as purchases,
       SUM(revenue) as totalRevenue,
       SUM(clickCount) * 100.0 / COUNT(*) as ctr
FROM searchQueries
WHERE searchTimestamp > ago('P1D')
  AND abTestGroup IN ('control', 'variant_semantic_v2')
GROUP BY abTestGroup, searchAlgorithm

-- Slow queries detection
SELECT queryText, searchAlgorithm,
       PERCENTILEEST(responseTimeMs, 99) as p99_latency,
       COUNT(*) as frequency
FROM searchQueries
WHERE searchTimestamp > ago('PT1H')
  AND responseTimeMs > 500
GROUP BY queryText, searchAlgorithm
ORDER BY frequency DESC
LIMIT 50

-- Full-text search on queries
SELECT queryText, COUNT(*) as cnt
FROM searchQueries
WHERE TEXT_MATCH(queryText, '"wireless headphones" OR "bluetooth earbuds"')
  AND searchTimestamp > ago('P7D')
GROUP BY queryText
ORDER BY cnt DESC
LIMIT 20
```

### Scale Numbers

| Metric | Value |
|--------|-------|
| Search queries/day | 1B+ |
| Events ingested/sec | 30K+ |
| P50 latency | 8ms |
| P99 latency | 60ms |
| Pinot servers | 120 |
| Data retention | 90 days |
| Star-tree enabled | Yes (category rollup) |

---

## Use Case 5: Instacart Ad Performance

### Problem Statement
Instacart's advertising platform needs real-time measurement of ad impressions, clicks, and attributed conversions. Advertisers (CPG brands) need sub-second dashboards showing campaign ROI, bid optimization signals, and budget pacing.

### Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    Instacart Ad Performance                              │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌───────────┐   ┌───────────┐   ┌───────────┐   ┌───────────┐       │
│  │Impression │   │   Click   │   │   Cart    │   │  Order    │       │
│  │  Event    │   │   Event   │   │   Add     │   │ Complete  │       │
│  └─────┬─────┘   └─────┬─────┘   └─────┬─────┘   └─────┬─────┘       │
│        │               │               │               │               │
│        ▼               ▼               ▼               ▼               │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                        Kafka                                     │   │
│  │  ad-impressions (100K/s) │ ad-clicks │ conversions │ orders     │   │
│  └────────────────────────────────────┬────────────────────────────┘   │
│                                       │                                 │
│  ┌────────────────────────────────────▼────────────────────────────┐   │
│  │                     Pinot Cluster                                │   │
│  │                                                                  │   │
│  │  ┌──────────────────────────────────────────────────────────┐   │   │
│  │  │              Controller (x3, active-passive)              │   │   │
│  │  │  - Table/schema management                               │   │   │
│  │  │  - Segment assignment via Helix                          │   │   │
│  │  │  - Rebalance orchestration                               │   │   │
│  │  └──────────────────────────────────────────────────────────┘   │   │
│  │                                                                  │   │
│  │  ┌──────────────────────────────────────────────────────────┐   │   │
│  │  │                  Broker (x8)                              │   │   │
│  │  │  - Query planning + fan-out                              │   │   │
│  │  │  - Result merge + aggregation                            │   │   │
│  │  │  - Adaptive server selection                             │   │   │
│  │  └──────────────────────────────────────────────────────────┘   │   │
│  │                                                                  │   │
│  │  ┌──────────────────────────────────────────────────────────┐   │   │
│  │  │              Server (x60)                                 │   │   │
│  │  │                                                          │   │   │
│  │  │  ad_impressions_REALTIME  │  ad_clicks_REALTIME          │   │   │
│  │  │  conversions_REALTIME     │  campaign_budget_REALTIME     │   │   │
│  │  │                                                          │   │   │
│  │  │  Upsert enabled on: campaign_budget (dedup by campaignId)│   │   │
│  │  │                                                          │   │   │
│  │  │  Star-tree: advertiserId + campaignId + adGroupId        │   │   │
│  │  └──────────────────────────────────────────────────────────┘   │   │
│  │                                                                  │   │
│  │  ┌──────────┐              ┌──────────────────┐                 │   │
│  │  │Minion(x3)│              │  Deep Store (S3)  │                 │   │
│  │  │-Purge old│              │  segment backups  │                 │   │
│  │  │-Rollup   │              └──────────────────┘                 │   │
│  │  └──────────┘                                                   │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐             │
│  │  Advertiser  │    │  Bid Engine  │    │ Budget Pacer │             │
│  │  Dashboard   │    │  (real-time  │    │ (spend rate  │             │
│  │              │    │   signals)   │    │  control)    │             │
│  └──────────────┘    └──────────────┘    └──────────────┘             │
└─────────────────────────────────────────────────────────────────────────┘
```

### Table Schema

```json
{
  "schemaName": "adImpressions",
  "dimensionFieldSpecs": [
    {"name": "impressionId", "dataType": "STRING"},
    {"name": "advertiserId", "dataType": "STRING"},
    {"name": "campaignId", "dataType": "STRING"},
    {"name": "adGroupId", "dataType": "STRING"},
    {"name": "creativeId", "dataType": "STRING"},
    {"name": "productId", "dataType": "STRING"},
    {"name": "placementType", "dataType": "STRING"},
    {"name": "searchQuery", "dataType": "STRING"},
    {"name": "categoryId", "dataType": "STRING"},
    {"name": "storeId", "dataType": "STRING"},
    {"name": "platform", "dataType": "STRING"},
    {"name": "userId", "dataType": "LONG"},
    {"name": "auctionType", "dataType": "STRING"}
  ],
  "metricFieldSpecs": [
    {"name": "bidAmount", "dataType": "DOUBLE"},
    {"name": "winPrice", "dataType": "DOUBLE"},
    {"name": "isClick", "dataType": "INT"},
    {"name": "isConversion", "dataType": "INT"},
    {"name": "conversionRevenue", "dataType": "DOUBLE"},
    {"name": "impressionCount", "dataType": "INT"}
  ],
  "dateTimeFieldSpecs": [{
    "name": "eventTimestamp",
    "dataType": "LONG",
    "format": "1:MILLISECONDS:EPOCH",
    "granularity": "1:MILLISECONDS"
  }]
}
```

### Ingestion Config

```json
{
  "streamConfigs": {
    "streamType": "kafka",
    "stream.kafka.topic.name": "ads.impressions",
    "stream.kafka.broker.list": "kafka-ads-01:9092,kafka-ads-02:9092",
    "stream.kafka.consumer.type": "lowlevel",
    "stream.kafka.decoder.class.name": "org.apache.pinot.plugin.stream.kafka.KafkaAvroMessageDecoder",
    "realtime.segment.flush.threshold.rows": "500000",
    "realtime.segment.flush.threshold.time": "1h"
  },
  "upsertConfig": {
    "mode": "PARTIAL",
    "partialUpsertStrategies": {
      "isClick": "INCREMENT",
      "isConversion": "INCREMENT",
      "conversionRevenue": "INCREMENT"
    },
    "comparisonColumn": "eventTimestamp"
  }
}
```

### Query Patterns

```sql
-- Campaign performance dashboard (hits star-tree)
SELECT campaignId, adGroupId,
       SUM(impressionCount) as impressions,
       SUM(isClick) as clicks,
       SUM(isConversion) as conversions,
       SUM(winPrice) as spend,
       SUM(conversionRevenue) as revenue,
       SUM(conversionRevenue) / NULLIF(SUM(winPrice), 0) as roas,
       SUM(isClick) * 100.0 / NULLIF(SUM(impressionCount), 0) as ctr
FROM adImpressions
WHERE advertiserId = 'adv_coca_cola'
  AND eventTimestamp > ago('P1D')
GROUP BY campaignId, adGroupId
ORDER BY spend DESC

-- Budget pacing (real-time spend tracking)
SELECT campaignId,
       SUM(winPrice) as currentSpend,
       COUNT(*) as impressionsServed
FROM adImpressions
WHERE advertiserId = 'adv_coca_cola'
  AND eventTimestamp > todayStartUTC()
GROUP BY campaignId

-- Placement performance
SELECT placementType, categoryId,
       AVG(winPrice) as avgCPM,
       SUM(isClick) * 1000.0 / NULLIF(SUM(impressionCount), 0) as ctrPer1000,
       SUM(conversionRevenue) / NULLIF(SUM(isClick), 0) as revenuePerClick
FROM adImpressions
WHERE eventTimestamp > ago('PT6H')
GROUP BY placementType, categoryId
ORDER BY revenuePerClick DESC
LIMIT 50
```

### Scale Numbers

| Metric | Value |
|--------|-------|
| Impressions/day | 2B+ |
| Peak events/sec | 100K+ |
| P50 latency | 12ms |
| P99 latency | 75ms |
| Advertisers | 5000+ |
| Upsert table size | 500M rows |
| Budget queries/sec | 10K |
| Data freshness | < 2 seconds |

---

## Replication

### Segment Replication Across Servers

```
┌─────────────────────────────────────────────────────────────────┐
│                    Segment Replication Model                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Table: orders_REALTIME (replication=3)                          │
│                                                                  │
│  Kafka Partition 0        Kafka Partition 1                      │
│       │                        │                                 │
│       ▼                        ▼                                 │
│  ┌─────────────┐         ┌─────────────┐                       │
│  │  Server 1   │         │  Server 2   │                       │
│  │  Segment_0  │         │  Segment_1  │                       │
│  │  (PRIMARY)  │         │  (PRIMARY)  │                       │
│  └─────────────┘         └─────────────┘                       │
│                                                                  │
│  ┌─────────────┐         ┌─────────────┐                       │
│  │  Server 3   │         │  Server 4   │                       │
│  │  Segment_0  │         │  Segment_1  │                       │
│  │  (REPLICA)  │         │  (REPLICA)  │                       │
│  └─────────────┘         └─────────────┘                       │
│                                                                  │
│  ┌─────────────┐         ┌─────────────┐                       │
│  │  Server 5   │         │  Server 6   │                       │
│  │  Segment_0  │         │  Segment_1  │                       │
│  │  (REPLICA)  │         │  (REPLICA)  │                       │
│  └─────────────┘         └─────────────┘                       │
│                                                                  │
│  Key: LOW-LEVEL consumers - each replica independently          │
│       consumes from Kafka partition                              │
└─────────────────────────────────────────────────────────────────┘
```

### Helix-Based Cluster Management

Apache Helix manages the distributed state machine for Pinot:

```
┌────────────────────────────────────────────────────────────────┐
│                    Helix State Machine                           │
├────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ZooKeeper (source of truth)                                    │
│       │                                                         │
│       ├── /IDEALSTATES/                                         │
│       │    └── orders_REALTIME                                  │
│       │         Segment_0: {Server1:ONLINE, Server3:ONLINE}     │
│       │         Segment_1: {Server2:ONLINE, Server4:ONLINE}     │
│       │                                                         │
│       ├── /EXTERNALVIEW/                                        │
│       │    └── orders_REALTIME                                  │
│       │         Segment_0: {Server1:ONLINE, Server3:ONLINE}     │
│       │         Segment_1: {Server2:ONLINE, Server4:OFFLINE}    │
│       │                                                         │
│       └── /LIVEINSTANCES/                                       │
│            Server1, Server2, Server3, Server4                   │
│                                                                 │
│  State Transitions:                                             │
│    OFFLINE -> CONSUMING -> ONLINE -> DROPPED                    │
│                                                                 │
│  Real-time segment lifecycle:                                   │
│    CONSUMING (actively ingesting from Kafka)                    │
│        │                                                        │
│        ▼ (flush threshold reached)                              │
│    ONLINE (segment sealed, immutable)                           │
│        │                                                        │
│        ▼ (retention expired)                                    │
│    DROPPED (removed from server)                                │
│                                                                 │
└────────────────────────────────────────────────────────────────┘
```

### Ideal State vs External View

| Concept | Description |
|---------|-------------|
| **Ideal State** | Desired assignment of segments to servers (set by controller) |
| **External View** | Actual current state (reflects reality: server may be bootstrapping) |
| **Broker Routing** | Uses External View to route queries only to ONLINE replicas |
| **Rebalance** | Controller updates Ideal State; Helix drives convergence |

### Controller Failover

```
Controller Leader Election (via ZooKeeper):

  Controller-1 (LEADER)  ──dies──>  Controller-2 (STANDBY -> LEADER)
       │                                    │
       │ Owns:                              │ Takes over:
       │ - Segment assignment               │ - All leader duties
       │ - Rebalance triggers               │ - In-progress rebalances
       │ - Retention enforcement            │ - Retention enforcement
       │ - Minion task scheduling           │ - Minion tasks

  Recovery time: 10-30 seconds (ZK session timeout)
  Impact: No query impact (brokers/servers independent)
           Only management operations paused briefly
```

---

## Scalability

### Segment-Based Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                   Pinot Segment Architecture                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Table: events (HYBRID = REALTIME + OFFLINE)                         │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                    REALTIME Table                             │    │
│  │                                                              │    │
│  │  Kafka Partition 0    Kafka Partition 1    Kafka Partition 2  │    │
│  │       │                    │                    │             │    │
│  │       ▼                    ▼                    ▼             │    │
│  │  ┌──────────┐        ┌──────────┐        ┌──────────┐       │    │
│  │  │CONSUMING │        │CONSUMING │        │CONSUMING │       │    │
│  │  │ seg_0_12 │        │ seg_1_8  │        │ seg_2_10 │       │    │
│  │  │(mutable) │        │(mutable) │        │(mutable) │       │    │
│  │  └──────────┘        └──────────┘        └──────────┘       │    │
│  │  ┌──────────┐        ┌──────────┐        ┌──────────┐       │    │
│  │  │COMPLETED │        │COMPLETED │        │COMPLETED │       │    │
│  │  │ seg_0_11 │        │ seg_1_7  │        │ seg_2_9  │       │    │
│  │  │(immutable│        │(immutable│        │(immutable│       │    │
│  │  └──────────┘        └──────────┘        └──────────┘       │    │
│  │       ...                 ...                 ...             │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                    OFFLINE Table                              │    │
│  │                                                              │    │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │    │
│  │  │2024-01-01│  │2024-01-02│  │2024-01-03│  │2024-01-04│   │    │
│  │  │ segment  │  │ segment  │  │ segment  │  │ segment  │   │    │
│  │  │(optimized│  │(optimized│  │(optimized│  │(optimized│   │    │
│  │  │ sorted,  │  │ sorted,  │  │ sorted,  │  │ sorted,  │   │    │
│  │  │ indexed) │  │ indexed) │  │ indexed) │  │ indexed) │   │    │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  Query spans BOTH tables seamlessly (broker merges results)          │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### Lambda Architecture (Real-time + Offline)

```
                    ┌─────────────────────┐
                    │    Data Source       │
                    └──────────┬──────────┘
                               │
                 ┌─────────────┼─────────────┐
                 │                           │
                 ▼                           ▼
     ┌───────────────────┐      ┌───────────────────┐
     │   Speed Layer      │      │   Batch Layer      │
     │   (Kafka -> RT)    │      │   (Hadoop/Spark)   │
     │                   │      │                    │
     │   Freshness: <3s  │      │   Freshness: hours │
     │   Optimized: no   │      │   Optimized: yes   │
     │   Sorted: no      │      │   Sorted: yes      │
     │   StarTree: no    │      │   StarTree: yes    │
     └─────────┬─────────┘      └─────────┬──────────┘
               │                           │
               ▼                           ▼
     ┌───────────────────┐      ┌───────────────────┐
     │ events_REALTIME    │      │ events_OFFLINE     │
     │ (last few hours)   │      │ (historical, days) │
     └─────────┬─────────┘      └─────────┬──────────┘
               │                           │
               └───────────┬───────────────┘
                           │
                           ▼
               ┌───────────────────┐
               │   Broker merges   │
               │   results from    │
               │   both tables     │
               │   (time-based     │
               │    boundary)      │
               └───────────────────┘
```

### Upsert Capabilities

```
Upsert Mode: FULL or PARTIAL

Use case: Mutable entities (order status, campaign budgets)

┌────────────────────────────────────────────────────────────┐
│  Primary Key: orderId                                       │
│  Comparison Column: updatedAt                               │
│                                                             │
│  Event 1: {orderId: "A1", status: "placed", amount: 50}    │
│  Event 2: {orderId: "A1", status: "shipped", amount: 50}   │
│  Event 3: {orderId: "A1", status: "delivered", amount: 50} │
│                                                             │
│  Query Result: Only latest record per primary key           │
│  {orderId: "A1", status: "delivered", amount: 50}           │
│                                                             │
│  Implementation:                                            │
│  - Hash map: primaryKey -> (segmentName, docId)             │
│  - Stored on server heap (memory cost!)                     │
│  - Segments must be on same server (partition-level)        │
│                                                             │
│  Partial Upsert Strategies:                                 │
│  - OVERWRITE: replace field with latest                     │
│  - INCREMENT: add to existing value                         │
│  - APPEND: append to multi-value field                      │
│  - UNION: union of multi-value field                        │
│  - IGNORE: keep original value                             │
└────────────────────────────────────────────────────────────┘
```

### Star-Tree Index for Pre-Aggregation

```
┌────────────────────────────────────────────────────────────────┐
│              Star-Tree Index Structure                           │
├────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Dimensions: [country, browser, os]                             │
│  Metrics: [SUM(impressions), COUNT(*)]                          │
│                                                                 │
│                        (*, *, *)                                 │
│                     /      |      \                              │
│                   /        |        \                            │
│           (US,*,*)    (UK,*,*)    (IN,*,*)                      │
│           /    \       /    \       /    \                       │
│    (US,Chrome,*) (US,FF,*)  ...                                 │
│       /    \                                                    │
│ (US,Chrome,Win) (US,Chrome,Mac)                                 │
│                                                                 │
│  Query: SELECT SUM(impressions) WHERE country='US'              │
│  Without star-tree: scan all docs where country='US'            │
│  With star-tree: single lookup at node (US,*,*)                 │
│                                                                 │
│  Performance impact:                                            │
│  - Pre-aggregated queries: 10-100x faster                       │
│  - Storage overhead: 2-5x segment size                          │
│  - Build time: adds to segment creation                         │
│                                                                 │
│  Config:                                                        │
│  "starTreeIndexConfigs": [{                                     │
│    "dimensionsSplitOrder": ["country","browser","os"],           │
│    "skipStarNodeCreationForDimensions": [],                      │
│    "functionColumnPairs": [                                      │
│      "SUM__impressions",                                        │
│      "COUNT__*"                                                  │
│    ],                                                           │
│    "maxLeafRecords": 10000                                      │
│  }]                                                             │
│                                                                 │
└────────────────────────────────────────────────────────────────┘
```

### Tenant Isolation

```
┌─────────────────────────────────────────────────────────────────┐
│                    Multi-Tenant Cluster                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Brokers:                                                        │
│  ┌────────────────────┐  ┌────────────────────┐                 │
│  │ Broker Tenant:     │  │ Broker Tenant:     │                 │
│  │ "analytics_team"   │  │ "ml_team"          │                 │
│  │ (Broker 1-5)       │  │ (Broker 6-10)      │                 │
│  └────────────────────┘  └────────────────────┘                 │
│                                                                  │
│  Servers:                                                        │
│  ┌────────────────────┐  ┌────────────────────┐                 │
│  │ Server Tenant:     │  │ Server Tenant:     │                 │
│  │ "analytics_team"   │  │ "ml_team"          │                 │
│  │ (Server 1-50)      │  │ (Server 51-80)     │                 │
│  │                    │  │                    │                 │
│  │ Tables:            │  │ Tables:            │                 │
│  │ - user_events      │  │ - feature_store    │                 │
│  │ - page_views       │  │ - model_metrics    │                 │
│  │ - conversions      │  │ - training_data    │                 │
│  └────────────────────┘  └────────────────────┘                 │
│                                                                  │
│  Benefits:                                                       │
│  - Resource isolation (no noisy neighbor)                        │
│  - Independent scaling per tenant                                │
│  - Different SLAs per team                                       │
│  - Separate maintenance windows                                  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Multi-Stage Query Engine

```
Traditional (single-stage):     Multi-stage (v2):
  Broker                          Broker
    │                               │
    ├── Server1 (local agg)         ├── Stage 1: Server scan + filter
    ├── Server2 (local agg)         ├── Stage 2: Shuffle by key
    └── Server3 (local agg)         ├── Stage 3: Aggregate
    │                               └── Stage 4: Sort + limit
    ▼
  Broker (final merge)            Enables:
                                  - JOIN between tables
  Limitations:                    - Sub-queries
  - No JOINs                     - Window functions
  - No sub-queries               - Complex aggregations
  - Limited GROUP BY cardinality
```

---

## Production Setup

### Cluster Components Sizing

| Component | Small (< 10K QPS) | Medium (10-100K QPS) | Large (100K+ QPS) |
|-----------|-------------------|---------------------|-------------------|
| **Controller** | 3 nodes, 4 CPU, 8GB | 3 nodes, 8 CPU, 16GB | 3 nodes, 16 CPU, 32GB |
| **Broker** | 3 nodes, 8 CPU, 16GB | 10 nodes, 16 CPU, 32GB | 20+ nodes, 32 CPU, 64GB |
| **Server** | 5 nodes, 16 CPU, 64GB, SSD | 50 nodes, 32 CPU, 128GB, NVMe | 200+ nodes, 64 CPU, 256GB, NVMe |
| **Minion** | 2 nodes, 8 CPU, 32GB | 5 nodes, 16 CPU, 64GB | 10 nodes, 32 CPU, 128GB |
| **ZooKeeper** | 3 nodes, 4 CPU, 8GB | 3 nodes, 8 CPU, 16GB | 5 nodes, 8 CPU, 16GB |

**Key sizing principles:**
- Servers: Memory = (active_segment_size * replication) + 30% headroom
- Brokers: CPU-bound (query parsing, merging); scale with QPS
- Disk: NVMe SSDs for servers; 3-5x raw data for indexes

### Kafka Ingestion Tuning

```yaml
# Critical stream configs
realtime.segment.flush.threshold.rows: 500000     # Rows per segment
realtime.segment.flush.threshold.time: "6h"       # Max time before flush
realtime.segment.flush.threshold.segment.size: "200M"  # Size-based flush

# Consumer configs
stream.kafka.consumer.prop.max.poll.records: 10000
stream.kafka.consumer.prop.fetch.max.bytes: 52428800  # 50MB
stream.kafka.consumer.prop.max.partition.fetch.bytes: 10485760  # 10MB

# Partition parallelism
# Each Kafka partition = 1 consuming segment on Pinot
# Rule: Kafka partitions >= Pinot server count for even distribution
# Typical: 3x Pinot servers for partition count

# Backfill / catch-up
stream.kafka.consumer.prop.auto.offset.reset: "smallest"  # Start from beginning
# For large backlogs, temporarily increase flush threshold to avoid tiny segments
```

### Segment Management and Retention

```yaml
# Retention config
segmentsConfig:
  retentionTimeUnit: "DAYS"
  retentionTimeValue: "90"            # Keep 90 days
  deletedSegmentsRetentionPeriod: "7d" # Grace period before physical delete

# RealtimeToOffline job (Minion task)
task.RealtimeToOfflineSegmentsTask:
  bucketTimePeriod: "1d"              # Merge RT segments into daily offline
  bufferTimePeriod: "2d"              # Wait 2 days before merging (late data)
  roundBucketTimePeriod: "true"
  mergeType: "rollup"                 # Aggregate during merge
  
# Segment compaction
task.MergeRollupTask:
  mergeLevel_1:
    bucketTimePeriod: "1d"
    bufferTimePeriod: "3d"
    maxNumRecordsPerSegment: "5000000"
  mergeLevel_2:
    bucketTimePeriod: "30d"
    bufferTimePeriod: "35d"
    maxNumRecordsPerSegment: "20000000"
```

### Monitoring and Alerting

```
Key Metrics to Monitor:

┌──────────────────────────────────────────────────────────────┐
│  Controller Health                                            │
│  - pinot.controller.idealstateResourceCount                  │
│  - pinot.controller.segmentCount                             │
│  - pinot.controller.offlineSegmentCount                      │
│  - pinot.controller.realtimeSegmentCount                     │
│  - pinot.controller.errorCount                               │
├──────────────────────────────────────────────────────────────┤
│  Broker Metrics                                              │
│  - pinot.broker.queryExecution.P99 (alert > 500ms)           │
│  - pinot.broker.queries.totalCount                           │
│  - pinot.broker.queryExecution.exceptions                    │
│  - pinot.broker.routingTable.unavailableCount (alert > 0)    │
├──────────────────────────────────────────────────────────────┤
│  Server Metrics                                              │
│  - pinot.server.realtimeConsumptionRate                     │
│  - pinot.server.segmentCount                                │
│  - pinot.server.queryExecution.P99                          │
│  - pinot.server.totalDocs                                   │
│  - JVM heap usage (alert > 80%)                             │
│  - Disk usage (alert > 75%)                                 │
├──────────────────────────────────────────────────────────────┤
│  Ingestion Lag                                               │
│  - kafka.consumer.lag (alert > 100K)                         │
│  - pinot.server.consumingSegmentAge (alert > threshold)      │
│  - pinot.server.lastConsumedOffset vs kafka high watermark   │
├──────────────────────────────────────────────────────────────┤
│  Critical Alerts                                             │
│  - Segments in ERROR state                                   │
│  - Consuming segment not progressing (>5 min)                │
│  - Query latency P99 > SLA threshold                         │
│  - Replication factor violated (under-replicated segments)   │
│  - Deep store upload failures                                │
└──────────────────────────────────────────────────────────────┘
```

### Deep Store Configuration

```json
{
  "pinotFSConfigs": {
    "s3": {
      "class": "org.apache.pinot.plugin.filesystem.S3PinotFS",
      "region": "us-east-1",
      "accessKey": "${AWS_ACCESS_KEY}",
      "secretKey": "${AWS_SECRET_KEY}"
    }
  },
  "controller.data.dir": "s3://pinot-deep-store/controller",
  "controller.local.temp.dir": "/tmp/pinot-controller",
  "pinot.server.instance.segment.store.uri": "s3://pinot-deep-store/segments"
}
```

**Deep store purposes:**
- Segment backup (disaster recovery)
- Server bootstrap (new server downloads segments from deep store)
- Offline segment staging (batch job pushes here first)
- Cross-datacenter replication (replicate deep store -> replicate cluster)

---

## Core Concepts

### Segment Architecture (Columnar Within Segment)

```
┌──────────────────────────────────────────────────────────────────┐
│                    Pinot Segment Structure                         │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│  Segment file (immutable, memory-mapped):                         │
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  Metadata                                                   │  │
│  │  - segment.name, table.name                                 │  │
│  │  - segment.total.docs: 500000                               │  │
│  │  - segment.start.time / segment.end.time                    │  │
│  │  - segment.creation.time                                    │  │
│  │  - column metadata (cardinality, min/max, data type)        │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  Forward Index (columnar storage)                           │  │
│  │                                                             │  │
│  │  Column: userId     [1001, 1002, 1003, 1001, 1004, ...]    │  │
│  │  Column: country    [dict_id: 0, 2, 1, 0, 3, ...]          │  │
│  │  Column: amount     [50.0, 120.5, 30.0, 75.0, ...]         │  │
│  │  Column: timestamp  [1704067200, 1704067201, ...]           │  │
│  │                                                             │  │
│  │  Encoding: dictionary (low cardinality)                     │  │
│  │            raw (high cardinality / sorted)                  │  │
│  │            bit-compressed (fixed-width)                      │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  Dictionary                                                 │  │
│  │  Column: country -> {0:"US", 1:"UK", 2:"IN", 3:"DE"}       │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  Inverted Index (optional, per column)                      │  │
│  │  country="US" -> bitmap [1,0,0,1,0,1,0,0,1,...]            │  │
│  │  country="UK" -> bitmap [0,0,1,0,0,0,1,0,0,...]            │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  Star-Tree Index (optional)                                 │  │
│  │  Pre-aggregated tree structure for fast GROUP BY            │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
```

### Indexing Types

| Index Type | Use Case | How It Works |
|-----------|----------|--------------|
| **Sorted** | Primary filter column (e.g., timestamp) | Binary search O(log n); only 1 sorted column per segment |
| **Inverted** | Low-to-medium cardinality filters (country, status) | Bitmap per value; O(1) lookup for equality |
| **Range** | Numeric range filters (amount > 100) | Tree-based; efficient for BETWEEN queries |
| **Text** | Full-text search (product descriptions) | Lucene-based; supports MATCH, PHRASE |
| **JSON** | Nested/dynamic fields | JSON path extraction + indexing |
| **Vector** | Similarity search (embeddings) | HNSW-based approximate nearest neighbor |
| **Bloom Filter** | High cardinality NOT-IN checks | Probabilistic; skip segments without matching values |
| **Star-Tree** | Pre-aggregation for GROUP BY | Tree of pre-computed aggregates; 10-100x speedup |

### Real-time Ingestion Lifecycle

```
┌─────────────────────────────────────────────────────────────────┐
│              Real-time Segment Lifecycle                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. CONSUMING State                                              │
│     ┌──────────────────────────┐                                │
│     │  In-memory buffer        │ <── Kafka records              │
│     │  (mutable, append-only)  │                                │
│     │  No indexes built yet    │                                │
│     │  Queryable immediately   │                                │
│     └──────────────────────────┘                                │
│              │                                                    │
│              │ Trigger: rows > 500K OR time > 6h OR size > 200M  │
│              ▼                                                    │
│  2. Seal + Build                                                 │
│     ┌──────────────────────────┐                                │
│     │  Build columnar format   │                                │
│     │  Build all indexes       │                                │
│     │  Write to local disk     │                                │
│     │  Upload to deep store    │                                │
│     └──────────────────────────┘                                │
│              │                                                    │
│              ▼                                                    │
│  3. COMPLETED/ONLINE State                                       │
│     ┌──────────────────────────┐                                │
│     │  Immutable segment       │                                │
│     │  Memory-mapped from disk │                                │
│     │  Fully indexed           │                                │
│     │  Backed up in deep store │                                │
│     └──────────────────────────┘                                │
│              │                                                    │
│              │ Simultaneously, new CONSUMING segment starts       │
│              ▼                                                    │
│  4. New CONSUMING segment created for same partition             │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Query Routing

```
┌─────────────────────────────────────────────────────────────────┐
│                    Query Execution Flow                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Client                                                          │
│    │                                                             │
│    │ SQL Query                                                   │
│    ▼                                                             │
│  Load Balancer (round-robin across brokers)                      │
│    │                                                             │
│    ▼                                                             │
│  Broker                                                          │
│    │                                                             │
│    ├─ 1. Parse SQL                                               │
│    ├─ 2. Look up routing table (segment -> server mapping)       │
│    ├─ 3. Prune segments (time filter -> skip old segments)       │
│    ├─ 4. Select server replica (round-robin / adaptive)          │
│    ├─ 5. Fan-out query to selected servers                       │
│    │                                                             │
│    │     ┌──────────┐  ┌──────────┐  ┌──────────┐              │
│    ├────>│ Server 1 │  │ Server 2 │  │ Server 3 │              │
│    │     │ Seg A,D  │  │ Seg B,E  │  │ Seg C,F  │              │
│    │     └────┬─────┘  └────┬─────┘  └────┬─────┘              │
│    │          │              │              │                     │
│    │          │  partial     │  partial     │  partial            │
│    │          │  results     │  results     │  results            │
│    │          ▼              ▼              ▼                     │
│    ├─ 6. Merge partial results (reduce phase)                    │
│    ├─ 7. Apply LIMIT, final ORDER BY                             │
│    │                                                             │
│    ▼                                                             │
│  Response to client                                              │
│                                                                  │
│  Routing strategies:                                             │
│  - BalancedNumSegments: spread by segment count                  │
│  - ReplicaGroup: co-locate segments for reduced fan-out          │
│  - PartitionAware: route to server with matching partition       │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Upsert and Partial Upsert

```
┌─────────────────────────────────────────────────────────────────┐
│                    Upsert Implementation                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Requirements:                                                   │
│  - Table must use LOW-LEVEL Kafka consumer                       │
│  - Primary key column(s) required                                │
│  - Partition-level routing (same key -> same server)             │
│  - Comparison column for ordering (e.g., updatedAt)              │
│                                                                  │
│  In-Memory Structure (per partition, per server):                 │
│                                                                  │
│  HashMap<PrimaryKey, RecordLocation>                             │
│    "order_123" -> {segment: "seg_5", docId: 42891}              │
│    "order_456" -> {segment: "seg_7", docId: 1023}               │
│    "order_789" -> {segment: "seg_7", docId: 5501}               │
│                                                                  │
│  On new record arrival:                                          │
│    1. Extract primary key                                        │
│    2. Check if key exists in map                                 │
│    3. If exists: compare timestamps                              │
│       - If new > old: update map, mark old doc as invalid        │
│       - If new < old: mark new doc as invalid (late arrival)     │
│    4. If not exists: insert into map                             │
│                                                                  │
│  Query time:                                                     │
│    - Validity bitmap filters out invalidated docs                │
│    - Only latest version per key returned                        │
│                                                                  │
│  Memory cost: ~100 bytes per unique key                          │
│  10M unique keys ≈ 1GB heap per partition                        │
│                                                                  │
│  Partial Upsert Example:                                         │
│                                                                  │
│  Record 1: {id: "A", clicks: 5, impressions: 100, revenue: null}│
│  Record 2: {id: "A", clicks: null, impressions: null, revenue: 25}│
│                                                                  │
│  Strategies: {clicks: OVERWRITE, impressions: IGNORE,            │
│               revenue: OVERWRITE}                                 │
│                                                                  │
│  Result:   {id: "A", clicks: 5, impressions: 100, revenue: 25}  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Tenant Isolation (Detailed)

```
Table config with tenant:

{
  "tenants": {
    "broker": "analytics_team",
    "server": "analytics_team",
    "tagOverrideConfig": {
      "realtimeConsuming": "analytics_team_REALTIME",
      "realtimeCompleted": "analytics_team_OFFLINE"
    }
  }
}

Server tags:
  Server 1:  analytics_team_REALTIME, analytics_team_OFFLINE
  Server 2:  analytics_team_REALTIME, analytics_team_OFFLINE
  Server 3:  ml_team_REALTIME, ml_team_OFFLINE

This ensures:
  - analytics_team tables never land on ml_team servers
  - Resource contention is eliminated
  - Teams can scale independently
```

---

## Summary: When to Use Apache Pinot

| Criteria | Pinot is Great | Pinot is NOT Ideal |
|----------|---------------|-------------------|
| Query pattern | Aggregations, GROUP BY, filters | Point lookups by primary key |
| Data freshness | Sub-second to seconds | Not needed (batch is fine) |
| Query latency | Sub-second (P99 < 100ms) | Minutes acceptable |
| Data volume | TB to PB scale | < 1GB (overkill) |
| Concurrency | 100K+ QPS | < 100 QPS (simpler tools work) |
| Schema | Known upfront, append-mostly | Highly dynamic / schema-on-read |
| Mutations | Limited (upsert for specific cases) | Heavy random updates/deletes |
| JOINs | Limited (multi-stage engine) | Complex multi-table JOINs |

**Latency Benchmarks (production observed):**

| Query Type | P50 | P99 |
|-----------|-----|-----|
| Simple filter + count | 3ms | 15ms |
| GROUP BY (low cardinality) | 5ms | 30ms |
| GROUP BY (high cardinality, 100K groups) | 20ms | 100ms |
| Star-tree aggregation | 1ms | 5ms |
| Text search | 15ms | 80ms |
| Time-series (30 day range) | 10ms | 50ms |
| Upsert table query | 8ms | 40ms |
