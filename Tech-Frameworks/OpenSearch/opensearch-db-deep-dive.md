# OpenSearch Deep Dive - Architecture, Querying, Aggregations, Hotspots, CAP, and Production Playbook

**Purpose:** A practical learning note for understanding OpenSearch from system-design, database, search, analytics, and production operations perspectives.

**Primary focus:** what OpenSearch is, how it stores and searches documents, how indexing/querying/aggregations work, how shards and replicas behave, how CAP tradeoffs apply, how to solve hotspot problems, what Bloom filters mean in OpenSearch, how to use it as a document store or key-value lookup store, and what to check before running it in production.

**Docs checked:** Context7 was used for current OpenSearch documentation. Official OpenSearch and Lucene references are listed at the end.

**Date:** 2026-05-27

## 1. Mental Model

OpenSearch is a distributed search and analytics engine built on Apache Lucene.

The most useful mental model:

```text
Application
  |
OpenSearch REST API / client
  |
Cluster coordinator node
  |
Index
  |
Primary shard + replica shards
  |
Lucene segments
  |
Inverted index + doc values + stored _source
```

OpenSearch is often called a "database", but it is not the same kind of database as PostgreSQL, MySQL, ScyllaDB, Cassandra, MongoDB, or Redis.

OpenSearch is optimized for:

- Full-text search.
- Filtering.
- Faceted search.
- Log and event search.
- Near real-time analytics.
- Time-series observability data.
- Security/event investigation.
- Product/catalog search.
- Aggregations over indexed fields.
- Document retrieval by ID.
- Vector search and hybrid search when configured.

OpenSearch is not optimized for:

- Multi-row ACID transactions.
- Joins like a relational database.
- Strict serializable consistency.
- High-rate counter updates on the same document.
- OLTP source-of-truth workloads.
- Queue semantics.
- Arbitrary unbounded scans.
- Large analytical joins over historical data.

The core design question is:

> Can I model the data so searches, filters, and aggregations can be answered from indexed fields without heavy per-document computation?

If yes, OpenSearch can be very powerful. If no, use a primary database, data warehouse, OLAP engine, or stream processor alongside it.

## 2. What OpenSearch Is

OpenSearch is an open-source search, analytics, and observability suite. The storage/search engine is OpenSearch, and the UI/visualization layer is OpenSearch Dashboards.

It provides:

- REST APIs for indexing, searching, updating, deleting, and managing documents.
- Distributed indexing and searching across shards.
- Full-text search using analyzers and inverted indexes.
- Exact filtering using keyword, numeric, date, IP, boolean, and geo fields.
- Aggregations for dashboards and analytics.
- Index templates, aliases, data streams, and index state management.
- Security features such as TLS, authentication, authorization, and audit logging.
- Snapshot and restore for backup and migration.
- Plugins for SQL, PPL, alerting, anomaly detection, k-NN/vector search, observability, and more.

## 3. When To Use OpenSearch

Use OpenSearch when the workload needs:

- Search box behavior: relevance ranking, stemming, tokenization, typo tolerance, synonyms, autocomplete.
- Faceted filtering: category, brand, price, rating, availability, location.
- Fast filtering over semi-structured documents.
- Real-time dashboards over logs, metrics, traces, clicks, orders, or audit events.
- Investigation workflows: "find all events matching this condition in the last 24 hours".
- Multi-field ranking: text score plus business signals.
- Aggregation and drill-down on recent data.
- Geospatial search.
- Vector similarity search, usually combined with metadata filters.
- A search/read model derived from a primary transactional system.

Common real-world examples:

- E-commerce product search.
- Restaurant/search marketplace discovery.
- Log analytics platform.
- Security event investigation.
- Application observability.
- Customer support search.
- Document/content search.
- Search across messages, tickets, emails, or knowledge base articles.
- Fraud investigation search.
- Recommendation candidate retrieval.
- URL shortener analytics search over redirect events.

Avoid OpenSearch as the main system of record when the workload requires:

- Strong multi-record transactions.
- Ledger-grade correctness.
- Foreign-key constraints.
- Heavy relational joins.
- Frequent updates to the same few rows/documents.
- Strict read-after-write search visibility for every request.
- Very cheap cold historical analytics over petabytes.
- Large group-by analytics across long historical periods.

For those cases, use OpenSearch as a derived search index fed from PostgreSQL, MySQL, DynamoDB, Kafka, S3/lakehouse, ClickHouse, Pinot, Druid, or another primary system.

## 4. Core Concepts

| Concept | Meaning |
|---|---|
| Cluster | Group of OpenSearch nodes working together. |
| Node | One OpenSearch server process. |
| Cluster manager node | Node role responsible for cluster state, index metadata, shard allocation, and cluster coordination. Previously called master node in older Elasticsearch/OpenSearch terminology. |
| Data node | Node that holds shards and executes indexing/search work. |
| Coordinating node | Node that receives client requests, fans out to shards, merges responses, and returns the result. Every node can coordinate, but dedicated coordinating nodes are common at scale. |
| Ingest node | Node that runs ingest pipelines before documents are indexed. |
| Search node | Specialized role used with remote-store and segment-replication setups to isolate search workloads. |
| Index | Logical collection of documents, similar to a table from an application perspective. |
| Document | JSON object stored in an index. |
| Field | Named value inside a document. |
| Mapping | Schema-like definition describing field types and indexing behavior. |
| Shard | A Lucene index that holds part of an OpenSearch index. |
| Primary shard | Original writable shard copy. |
| Replica shard | Copy of a primary shard for high availability and search capacity. |
| Segment | Immutable Lucene sub-index created during refresh/flush and merged over time. |
| Translog | Transaction log used for durability and recovery of recent operations. |
| Refresh | Makes newly indexed documents visible to search by opening new searcher/segments. |
| Flush | Performs a Lucene commit and starts a new translog generation. |
| Merge | Background process that combines smaller Lucene segments into larger ones. |
| Analyzer | Text processing pipeline: character filters, tokenizer, token filters. |
| Inverted index | Maps terms to documents. This is the core structure for search. |
| Doc values | Columnar on-disk field representation used for sorting, aggregations, and scripting. |
| `_source` | Original JSON document stored for retrieval and reindexing. |
| `_id` | Document identifier. Used for direct GET/update/delete and default routing. |
| `_routing` | Value used to choose the target shard. Defaults to `_id` unless custom routing is supplied. |

## 5. How OpenSearch Stores Data

OpenSearch stores JSON documents, but internally it is not just a JSON file store.

When you index a document:

1. OpenSearch receives the JSON.
2. It checks the target index and mapping.
3. It analyzes text fields into tokens.
4. It writes terms into Lucene inverted indexes.
5. It stores doc values for fields used in aggregations, sorting, and scripts.
6. It stores `_source` unless disabled.
7. It appends operation data to the translog.
8. It later refreshes, flushes, and merges Lucene segments.

### 5.1 Inverted Index

For a text field like:

```json
{
  "title": "OpenSearch distributed search engine"
}
```

An analyzer may produce tokens:

```text
opensearch
distributed
search
engine
```

The inverted index maps:

```text
opensearch  -> doc 1, doc 9, doc 40
distributed -> doc 1, doc 12
search      -> doc 1, doc 2, doc 3
engine      -> doc 1, doc 8
```

This is why OpenSearch is fast at search. It does not scan every document for a word. It jumps from search terms to matching document IDs.

### 5.2 Doc Values

Doc values are column-oriented structures used for:

- Sorting.
- Aggregations.
- Scripting.
- Some filtering and field retrieval patterns.

For example, `price`, `brand.keyword`, `created_at`, and `status` should generally have doc values enabled if you sort or aggregate on them.

A common mistake is aggregating on a `text` field. Use a `keyword` subfield instead:

```json
{
  "mappings": {
    "properties": {
      "product_name": {
        "type": "text",
        "fields": {
          "keyword": {
            "type": "keyword"
          }
        }
      }
    }
  }
}
```

Use:

```text
product_name.keyword
```

for exact matches, sorting, and aggregations.

Use:

```text
product_name
```

for full-text search.

### 5.3 Segments

Lucene stores data in immutable segments.

High-level lifecycle:

```text
Index documents
  -> buffered in memory and translog
  -> refresh creates searchable segment/searcher
  -> flush commits durable segment state
  -> merge combines small segments
```

Segments are immutable. Updates are internally implemented as:

```text
delete old document version + add new document version
```

This is why OpenSearch can handle large append-heavy workloads well, but update-heavy workloads on the same documents can create segment churn and merge pressure.

### 5.4 Refresh

OpenSearch is near real time.

Indexing a document does not always mean it is immediately visible to search. A refresh makes recent changes searchable.

Important distinction:

- Direct document GET by ID can be real-time.
- Search is near real-time and depends on refresh behavior.

For user-facing write-then-search flows, use one of these approaches:

- Return the written object directly from the primary database.
- Use `refresh=wait_for` for selected writes where the user must immediately search the new document.
- Lower `refresh_interval` only if the workload can afford the extra cost.
- Keep default or longer refresh intervals for heavy ingestion.

Do not set `refresh=true` on every write in a high-throughput system. It can destroy indexing throughput.

### 5.5 Flush

Flush performs a Lucene commit and starts a new translog generation.

The translog protects recent writes that have not yet been committed to Lucene. On crash recovery, OpenSearch can replay operations from the translog.

### 5.6 Merge

OpenSearch/Lucene continuously merges small segments into larger segments.

Merges improve search efficiency by reducing the number of segments, but they consume:

- Disk I/O.
- CPU.
- Temporary disk space.
- Background thread capacity.

Heavy updates, deletes, very small refresh intervals, and aggressive indexing can create merge pressure.

## 6. Indexes, Shards, and Routing

An OpenSearch index is split into primary shards. Each primary shard can have zero or more replicas.

Example:

```json
PUT products-v1
{
  "settings": {
    "number_of_shards": 6,
    "number_of_replicas": 1
  }
}
```

This creates:

```text
6 primary shards
6 replica shards
12 total shard copies
```

### 6.1 What A Shard Really Is

A shard is a Lucene index.

If an OpenSearch index has 6 primary shards, that logical index is physically 6 independent Lucene indexes. A search across the OpenSearch index fans out to the relevant shards, each shard searches locally, and the coordinator merges the results.

### 6.2 Default Routing

By default, OpenSearch routes a document using `_id`:

```text
shard_num = hash(_routing) % number_of_primary_shards
```

When no custom routing is supplied:

```text
_routing = _id
```

If `_id` values are high-cardinality and evenly distributed, default routing usually distributes documents well.

### 6.3 Custom Routing

Custom routing sends related documents to the same shard or subset of shards.

Example:

```http
PUT orders/_doc/order_1001?routing=tenant_42
{
  "tenant_id": "tenant_42",
  "order_id": "order_1001",
  "amount": 120.50
}
```

Benefits:

- Querying by routing can reduce fan-out.
- Tenant-specific queries can hit fewer shards.
- Parent/child or co-located access patterns can work better.

Risk:

- If one routing key is very hot, one shard becomes very hot.

Custom routing is one of the most common causes of hotspot problems.

### 6.4 Partitioned Routing

OpenSearch supports routing a custom routing value to a subset of shards rather than exactly one shard by using `index.routing_partition_size` at index creation time.

Conceptually:

```text
tenant_42 -> shard 2, shard 5, shard 7, shard 9
```

instead of:

```text
tenant_42 -> shard 2 only
```

This helps when:

- Tenant-locality is useful.
- A large tenant is too hot for one shard.
- You can tolerate querying a small shard subset for that tenant.

Tradeoff:

- Reads for that routing value may fan out to multiple shards.
- It must be designed before index creation.

### 6.5 Shard Count Selection

Shard count affects:

- Write parallelism.
- Search fan-out.
- Recovery time.
- Heap and file descriptor overhead.
- Rebalancing speed.
- Operational complexity.

Too few shards:

- One shard can become too large.
- Write parallelism is limited.
- Hot shard risk increases.
- Recovery can be slow.

Too many shards:

- Cluster state grows.
- Heap overhead grows.
- Search fan-out grows.
- Merges and file handles increase.
- Small shards waste resources.

Practical rule:

- Start from data volume, expected growth, retention, and query rate.
- Prefer time-based indexes/data streams for logs/events.
- Keep shard sizes in a manageable range, often tens of GB rather than hundreds of GB.
- Test with production-like queries and ingestion.
- Use rollover policies instead of fixed calendar boundaries when volume varies.

## 7. Write Path

For normal document replication, the write path is:

```text
Client
  -> coordinating node
  -> route by _id/_routing
  -> primary shard
  -> index into Lucene memory structures
  -> append translog
  -> forward operation to replica shards
  -> replicas index and append translog
  -> ack when required shard copies respond
```

Important settings/concepts:

- `number_of_replicas`: number of replica copies.
- `wait_for_active_shards`: how many active shard copies must be available before indexing proceeds.
- `refresh`: whether to wait for or force refresh.
- `index.translog.durability`: request-level durability behavior.
- `_seq_no` and `_primary_term`: used for optimistic concurrency control.

### 7.1 Bulk Writes

Use the Bulk API for ingestion.

Example:

```http
POST _bulk
{ "index": { "_index": "events-000001", "_id": "evt_1" } }
{ "event_type": "login", "user_id": "u1", "ts": "2026-05-27T10:00:00Z" }
{ "index": { "_index": "events-000001", "_id": "evt_2" } }
{ "event_type": "logout", "user_id": "u1", "ts": "2026-05-27T10:10:00Z" }
```

Bulk tuning:

- Use multiple concurrent bulk workers.
- Keep bulk payloads moderate; do not send enormous payloads.
- Watch rejected writes and thread pools.
- Increase `refresh_interval` during heavy backfills.
- Temporarily reduce replicas for one-time backfills only if recovery risk is acceptable.
- Use ingest queues or Kafka to absorb bursts.
- Make writes idempotent when replaying from a stream.

### 7.2 Updates Are Rewrites

OpenSearch update:

```http
POST products/_update/p1
{
  "doc": {
    "price": 199
  }
}
```

Internally, OpenSearch retrieves the current document, applies the partial update, and writes a new version. Lucene marks the old version deleted and adds the new version.

Implications:

- Frequent updates to the same document are expensive.
- Counter workloads can create conflicts and segment churn.
- High update rates may need a different system such as Redis, ScyllaDB, DynamoDB, Cassandra, Aerospike, or a relational database, with periodic indexing into OpenSearch.

## 8. Read Path

OpenSearch has two major read paths:

1. Direct document lookup by ID.
2. Search query over one or more indexes/shards.

### 8.1 GET By ID

Example:

```http
GET products/_doc/p1
```

This is the closest OpenSearch gets to key-value access.

Strengths:

- Simple.
- Fast when `_id` and routing are known.
- Can retrieve exact document.
- Works well for read models and metadata lookup.

Limitations:

- It is not a Redis replacement.
- It is not a transactional KV database.
- Writes and updates are heavier than in purpose-built KV stores.
- Large `_source` documents can be expensive to retrieve.
- Hot keys can overload one shard.

### 8.2 Search Query

Search path:

```text
Client
  -> coordinating node
  -> target indexes/shards
  -> each shard executes query locally
  -> each shard returns top results / aggregation partials
  -> coordinator merges, sorts, reduces
  -> response returned
```

Search can be expensive because it fans out. A query across 100 shards is not equivalent to one local index lookup.

Reduce fan-out with:

- Narrow index patterns.
- Time filters.
- Routing.
- Aliases.
- Data streams and rollover.
- Tenant-specific indexes for large tenants.
- Search replicas for search-heavy workloads.

## 9. Querying

OpenSearch supports Query DSL, SQL, and PPL. Query DSL is the most precise and production-friendly for application services.

### 9.1 Query Context vs Filter Context

Query context answers:

```text
How well does this document match?
```

Filter context answers:

```text
Does this document match yes/no?
```

Use query context for relevance:

- `match`
- `multi_match`
- `query_string`
- `knn`/vector scoring

Use filter context for structured constraints:

- `term`
- `terms`
- `range`
- `exists`
- `ids`
- `geo_bounding_box`
- `bool.filter`

Filters are generally more cache-friendly and avoid scoring work.

### 9.2 Match Query

Use `match` for analyzed full-text fields.

```http
GET products/_search
{
  "query": {
    "match": {
      "description": "wireless noise cancelling headphones"
    }
  }
}
```

Best for:

- Search boxes.
- Descriptions.
- Titles.
- Natural-language fields.

### 9.3 Term Query

Use `term` for exact values, usually `keyword`, numeric, boolean, or ID-like fields.

```http
GET products/_search
{
  "query": {
    "term": {
      "brand.keyword": "Sony"
    }
  }
}
```

Do not use `term` against analyzed `text` fields unless you know exactly how they are tokenized.

### 9.4 Bool Query

Most production queries use `bool`.

```http
GET products/_search
{
  "query": {
    "bool": {
      "must": [
        {
          "match": {
            "title": "running shoes"
          }
        }
      ],
      "filter": [
        {
          "term": {
            "brand.keyword": "Nike"
          }
        },
        {
          "range": {
            "price": {
              "gte": 50,
              "lte": 200
            }
          }
        },
        {
          "term": {
            "in_stock": true
          }
        }
      ],
      "must_not": [
        {
          "term": {
            "status.keyword": "discontinued"
          }
        }
      ]
    }
  }
}
```

Use:

- `must` for required scoring clauses.
- `filter` for required non-scoring clauses.
- `should` for optional scoring boosts.
- `must_not` for exclusions.

### 9.5 Range Query

```http
GET orders/_search
{
  "query": {
    "range": {
      "created_at": {
        "gte": "now-7d",
        "lt": "now"
      }
    }
  }
}
```

Common for:

- Time filters.
- Prices.
- Latency ranges.
- Numeric thresholds.

### 9.6 Exists Query

```http
GET users/_search
{
  "query": {
    "exists": {
      "field": "email"
    }
  }
}
```

### 9.7 Nested Query

Use `nested` when arrays of objects must preserve object boundaries.

Example document:

```json
{
  "product_id": "p1",
  "offers": [
    { "seller": "s1", "price": 100 },
    { "seller": "s2", "price": 200 }
  ]
}
```

If `offers` is mapped as a normal object array, OpenSearch can flatten values and accidentally match `seller=s1` with `price=200`.

Use `nested` mapping when you need object-level correctness:

```json
{
  "mappings": {
    "properties": {
      "offers": {
        "type": "nested",
        "properties": {
          "seller": { "type": "keyword" },
          "price": { "type": "double" }
        }
      }
    }
  }
}
```

Nested query:

```http
GET products/_search
{
  "query": {
    "nested": {
      "path": "offers",
      "query": {
        "bool": {
          "filter": [
            { "term": { "offers.seller": "s1" } },
            { "range": { "offers.price": { "lte": 150 } } }
          ]
        }
      }
    }
  }
}
```

Nested fields are powerful but expensive. Avoid deeply nested or huge nested arrays.

### 9.8 Pagination

Small pagination:

```http
GET products/_search
{
  "from": 0,
  "size": 20,
  "query": {
    "match": {
      "title": "laptop"
    }
  }
}
```

Deep pagination with `from` and `size` is expensive because each shard may need to collect and sort many skipped results.

For deep user pagination:

- Use `search_after`.
- Use a stable sort.
- Use Point in Time (PIT) for consistent pagination.

Example:

```http
GET products/_search
{
  "size": 20,
  "sort": [
    { "created_at": "desc" },
    { "_id": "asc" }
  ],
  "search_after": ["2026-05-27T10:00:00Z", "p100"]
}
```

For batch export or reindex-style scanning:

- Use scroll for controlled backend jobs.
- Avoid scroll for user-facing pagination.

## 10. Filtering

Filtering is one of OpenSearch's strongest capabilities when fields are mapped correctly.

### 10.1 Query-Level Filtering

Use `bool.filter` when filters should affect both hits and aggregations:

```http
GET products/_search
{
  "query": {
    "bool": {
      "must": [
        { "match": { "title": "phone" } }
      ],
      "filter": [
        { "term": { "brand.keyword": "Apple" } },
        { "range": { "price": { "lte": 1000 } } }
      ]
    }
  }
}
```

### 10.2 Post Filter

Use `post_filter` when aggregations should be calculated before a selected UI filter is applied to hits.

Common faceted-search behavior:

- User searches "phone".
- Aggregations show all available brands.
- User selects one brand.
- Results filter to that brand.
- Brand facet still shows broader options.

```http
GET products/_search
{
  "query": {
    "match": {
      "title": "phone"
    }
  },
  "aggs": {
    "brands": {
      "terms": {
        "field": "brand.keyword"
      }
    }
  },
  "post_filter": {
    "term": {
      "brand.keyword": "Apple"
    }
  }
}
```

### 10.3 Aggregation-Level Filtering

Use filter aggregations when each aggregation needs different filter logic.

```http
GET orders/_search
{
  "size": 0,
  "aggs": {
    "paid_orders": {
      "filter": {
        "term": {
          "status.keyword": "paid"
        }
      },
      "aggs": {
        "revenue": {
          "sum": {
            "field": "amount"
          }
        }
      }
    }
  }
}
```

## 11. Aggregations

Aggregations are OpenSearch's analytics engine.

They answer questions like:

- Count products by brand.
- Average latency by service.
- Error count per minute.
- Top users by event count.
- Revenue per day.
- Percentile response time.
- Unique users in the last hour.

Aggregation categories:

| Type | Purpose | Examples |
|---|---|---|
| Metric | Compute numbers | `avg`, `sum`, `min`, `max`, `stats`, `percentiles`, `cardinality` |
| Bucket | Group documents | `terms`, `range`, `date_histogram`, `histogram`, `filters`, `geo_grid` |
| Pipeline | Compute over aggregation output | moving average, derivative, bucket script |
| Nested | Aggregate nested documents | `nested`, `reverse_nested` |

### 11.1 Basic Terms Aggregation

```http
GET products/_search
{
  "size": 0,
  "aggs": {
    "by_brand": {
      "terms": {
        "field": "brand.keyword",
        "size": 10
      }
    }
  }
}
```

Use `size: 0` when you only need aggregation results.

### 11.2 Date Histogram

```http
GET logs-*/_search
{
  "size": 0,
  "query": {
    "range": {
      "@timestamp": {
        "gte": "now-1h"
      }
    }
  },
  "aggs": {
    "errors_over_time": {
      "date_histogram": {
        "field": "@timestamp",
        "fixed_interval": "1m"
      },
      "aggs": {
        "error_count": {
          "filter": {
            "range": {
              "status_code": {
                "gte": 500
              }
            }
          }
        }
      }
    }
  }
}
```

### 11.3 Faceted Search Example

```http
GET products/_search
{
  "size": 20,
  "query": {
    "bool": {
      "must": [
        { "match": { "title": "running shoes" } }
      ],
      "filter": [
        { "range": { "price": { "lte": 200 } } }
      ]
    }
  },
  "aggs": {
    "brands": {
      "terms": {
        "field": "brand.keyword",
        "size": 20
      }
    },
    "price_ranges": {
      "range": {
        "field": "price",
        "ranges": [
          { "to": 50 },
          { "from": 50, "to": 100 },
          { "from": 100, "to": 200 },
          { "from": 200 }
        ]
      }
    }
  }
}
```

### 11.4 Aggregation Performance Rules

Use these rules in production:

- Aggregate on `keyword`, numeric, date, boolean, IP, and geo fields.
- Avoid aggregating on raw `text` fields.
- Avoid enabling `fielddata` on high-cardinality `text` fields unless you fully understand the memory cost.
- Use time filters before aggregating logs/events.
- Limit `terms.size`.
- Use composite aggregations for paginating large bucket sets.
- Beware of high-cardinality fields such as `user_id`, `trace_id`, `session_id`, and `request_id`.
- For dashboards, pre-aggregate when queries are too expensive.
- Use rollups/transforms/materialized summaries for heavy repeated analytics.
- Watch circuit breakers and heap usage.

## 12. Mapping and Schema Design

Mappings are one of the most important production decisions in OpenSearch.

Bad mappings cause:

- Wrong search behavior.
- Slow queries.
- Failed aggregations.
- Mapping explosion.
- High heap usage.
- Expensive reindexing.

### 12.1 Text vs Keyword

Use `text` for full-text search:

```json
"description": {
  "type": "text"
}
```

Use `keyword` for exact match, aggregations, sorting, IDs, tags, status, enum-like values:

```json
"status": {
  "type": "keyword"
}
```

Use multi-fields when you need both:

```json
"title": {
  "type": "text",
  "fields": {
    "keyword": {
      "type": "keyword",
      "ignore_above": 256
    }
  }
}
```

### 12.2 Explicit Mapping

Prefer explicit mappings for production indexes.

```http
PUT products-v1
{
  "settings": {
    "number_of_shards": 6,
    "number_of_replicas": 1
  },
  "mappings": {
    "dynamic": "strict",
    "properties": {
      "product_id": { "type": "keyword" },
      "title": {
        "type": "text",
        "fields": {
          "keyword": { "type": "keyword", "ignore_above": 256 }
        }
      },
      "brand": { "type": "keyword" },
      "category": { "type": "keyword" },
      "price": { "type": "double" },
      "rating": { "type": "float" },
      "in_stock": { "type": "boolean" },
      "created_at": { "type": "date" }
    }
  }
}
```

`dynamic: strict` fails writes that contain unknown fields. This is useful when schema correctness matters.

### 12.3 Mapping Explosion

Mapping explosion happens when too many fields are created in an index.

Common causes:

- Dynamic mapping on unpredictable JSON.
- User-defined custom attributes as real fields.
- Logs with arbitrary keys.
- Deeply nested objects.
- Dynamic field names such as `metric_2026_05_27_10_01`.

Symptoms:

- High heap usage.
- Slow cluster state updates.
- Slow searches.
- Indexing failures.
- Unstable cluster manager nodes.

Prevention:

- Use explicit mappings.
- Use `dynamic: strict` or `dynamic: false`.
- Use dynamic templates carefully.
- Use `flat_object` for arbitrary key-value attributes.
- Limit total fields.
- Normalize dynamic field names into key/value pairs.

Bad:

```json
{
  "metrics": {
    "cpu_host_123_2026_05_27_10_00": 80,
    "cpu_host_456_2026_05_27_10_00": 75
  }
}
```

Better:

```json
{
  "metric_name": "cpu",
  "host_id": "host_123",
  "ts": "2026-05-27T10:00:00Z",
  "value": 80
}
```

## 13. Bloom Filters In OpenSearch

Bloom filters are probabilistic membership structures.

They answer:

```text
Is this key definitely absent, or maybe present?
```

They can return:

- Definitely no.
- Maybe yes.

They do not return:

- Definitely yes.

False positives are possible. False negatives are not expected.

### 13.1 How This Relates To OpenSearch

OpenSearch is built on Lucene. Lucene has low-level structures that accelerate term lookups, postings lookups, doc values, points, and segment-level reads.

In current OpenSearch index settings, there is also an explicit document ID lookup optimization using a `fuzzy_set`, which is a Bloom filter-style data structure:

```json
{
  "index.optimize_doc_id_lookup.fuzzy_set.enabled": true,
  "index.optimize_doc_id_lookup.fuzzy_set.false_positive_probability": 0.20
}
```

Purpose:

- Optimize document ID lookups.
- Help negative ID lookups return faster.
- Improve workloads with many upserts or GET/index calls where many IDs may not exist.

Tradeoff:

- Lower false-positive probability can improve negative lookup throughput.
- Lower false-positive probability uses more storage/memory.
- Creating the structure has indexing-time overhead.

### 13.2 What Bloom Filters Do Not Do

Bloom filters do not magically speed up every OpenSearch query.

They are not the main mechanism for:

- Full-text relevance search.
- Aggregations.
- Range queries.
- Sorting.
- Vector search.
- Geo search.

For those, the primary structures are:

- Inverted indexes.
- Doc values.
- BKD/point trees for numeric/date/geo-style fields.
- Vector indexes for k-NN.
- Query caches and request caches in some cases.

### 13.3 Interview Answer

If asked "Does OpenSearch use Bloom filters?", answer carefully:

> OpenSearch is a Lucene-based search engine. Its main search structures are inverted indexes, segments, doc values, and point/vector structures. Bloom-filter-style fuzzy sets can be used for optimizing document ID lookups, especially negative lookups, but Bloom filters are not the general query execution engine the way they are often discussed in LSM databases like Cassandra or ScyllaDB.

## 14. Replication

OpenSearch replication exists for:

- High availability.
- Search throughput.
- Fault recovery.
- Zone/rack resilience.

### 14.1 Primary and Replica Shards

Each primary shard can have replicas.

Example:

```json
{
  "number_of_shards": 3,
  "number_of_replicas": 2
}
```

This gives:

```text
3 primary shards
6 replica shards
9 total shard copies
```

Rules:

- A replica shard is not allocated on the same node as its primary.
- If a primary fails, a replica can be promoted.
- Replicas can serve search requests.
- More replicas can increase search capacity but also increase indexing cost.

### 14.2 Document Replication

In classic document replication:

```text
write -> primary shard
primary indexes operation
primary writes translog
primary forwards operation to replicas
replicas index operation
replicas write translog
ack returns based on required active shards
```

Pros:

- Replicas are independently indexed and ready for search.
- Straightforward primary-replica model.

Cons:

- Every replica repeats indexing work.
- Higher CPU cost during write-heavy workloads.

### 14.3 Segment Replication

Segment replication copies Lucene segment files rather than re-indexing every document independently on each replica.

Concept:

```text
primary indexes documents
primary creates segments
replicas copy segments
```

Benefits:

- Can improve indexing throughput.
- Reduces duplicate indexing CPU on replicas.
- Useful for some heavy ingest workloads.

Tradeoffs:

- More network movement of segment files.
- Different read-after-write behavior.
- Operational constraints around version and index setup.
- Existing indexes may need reindexing to use it.

### 14.4 Remote-Backed Storage

Remote-backed storage stores transaction logs and segment data in remote object storage.

Concept:

```text
primary shard writes data
translog uploaded to remote store
segments uploaded to remote segment store
replicas recover/fetch from remote store
```

Benefits:

- Better data-loss protection in some architectures.
- Faster recovery patterns.
- Enables separation of indexing and search workloads.

Tradeoffs:

- More architectural complexity.
- Remote storage latency and throughput matter.
- Requires careful testing and operational discipline.

### 14.5 Search Replicas

In remote-store and segment-replication-enabled setups, OpenSearch can separate search and indexing workloads.

Replica types:

- Write replicas: can be promoted to primary and support write availability.
- Search replicas: serve search only and cannot be promoted to primary.

Use search replicas when:

- Search workload is heavy.
- Indexing workload is heavy.
- You want separate scaling for search and indexing capacity.

Do not treat search replicas as write-failover copies.

### 14.6 Cross-Cluster Replication

Cross-cluster replication replicates indexes from one cluster to another.

Common uses:

- Disaster recovery.
- Read-only regional copies.
- Migration.
- Search in a secondary region.

Important:

- CCR is not the same as synchronous multi-region transactions.
- It introduces replication lag.
- It needs monitoring for follower health and lag.

## 15. CAP Theorem and Consistency

CAP theorem says that during a network partition, a distributed system must choose between:

- Consistency: all clients see a single correct value/order.
- Availability: every request receives a non-error response.

OpenSearch does not fit cleanly into a one-word CP/AP label for every operation. Its behavior depends on which part of the system you are discussing.

### 15.1 Cluster Coordination

OpenSearch uses quorum-based cluster-manager election and cluster-state publication.

This prevents split-brain:

```text
Only a majority side can elect/update cluster state.
Minority side cannot safely make conflicting cluster-wide decisions.
```

Tradeoff:

- Better consistency of cluster metadata and shard ownership.
- Lower availability for the minority side during a partition.

### 15.2 Writes

Writes go to the primary shard for the target routing key.

Important consistency mechanisms:

- Primary term identifies the current primary generation.
- Sequence numbers order operations.
- Replicas apply operations from the primary.
- Stale primaries should be fenced off when cluster state changes.
- `wait_for_active_shards` can require more active copies before accepting writes.

Tradeoff:

- OpenSearch favors avoiding conflicting primaries over accepting writes everywhere.
- If the primary or cluster-manager majority is unavailable, writes can fail.

### 15.3 Reads and Search

Direct GET by ID can be more up-to-date than search.

Search is near real-time:

```text
write acknowledged
  does not always mean
immediately visible to search
```

Search visibility depends on:

- Refresh interval.
- Replica state.
- Segment replication lag.
- Query target shards.
- Whether `refresh=wait_for` or `refresh=true` was used.

### 15.4 Practical CAP Answer

For interviews and system design:

> OpenSearch uses quorum-based cluster coordination to prevent split-brain, so under partitions it may sacrifice availability on the minority side for cluster-state consistency. Writes are primary-shard based and replicated to replicas. Search is near real-time rather than strictly linearizable. OpenSearch is excellent as a search/read model, but it should not be used as the sole strongly consistent transactional database for money movement, inventory correctness, or ledger workflows.

## 16. Hotspot Problems

A hotspot happens when one shard, node, tenant, field, or query pattern receives disproportionate load.

Symptoms:

- One data node has much higher CPU.
- One shard has much higher indexing/search load.
- High p99 latency.
- Search or write thread pool rejections.
- Merge backlog.
- Disk I/O saturation.
- Uneven shard sizes.
- Circuit breaker trips.
- Long garbage collection pauses.
- Slow logs show repeated expensive queries.

### 16.1 Common Hotspot Causes

#### Cause 1: Bad Custom Routing

Example:

```text
routing = tenant_id
```

If tenant `tenant_big` sends 40 percent of traffic, one shard may receive 40 percent of write/read load.

#### Cause 2: Low Shard Count

If an index has one primary shard, all writes go to one primary shard.

This can be fine for small indexes, but not for high ingestion or large search workloads.

#### Cause 3: Time-Series Write Concentration

For logs/events, most writes go to the current write index.

If the current index has too few primary shards, the current write workload can overload a small number of shards.

#### Cause 4: Hot Terms and Expensive Aggregations

Examples:

- Aggregating by `user_id` with millions of unique values.
- Large `terms` aggregations on high-cardinality fields.
- Querying broad time ranges without filters.
- Leading wildcard queries.
- Heavy scripts on many documents.
- Runtime fields in repeated dashboards.

#### Cause 5: Large Documents or Nested Explosions

Huge documents and nested arrays can create:

- More indexing work.
- More stored field retrieval cost.
- More Lucene documents internally.
- Higher heap pressure.

#### Cause 6: Update Storms

Repeated updates to the same document or small key range can overload one shard and create version conflicts.

### 16.2 How To Detect Hotspots

Useful APIs:

```http
GET _cat/shards?v&s=store:desc
GET _cat/allocation?v
GET _cat/thread_pool/search,write?v
GET _nodes/hot_threads
GET _nodes/stats
GET _cluster/health
GET _cluster/pending_tasks
GET _cluster/allocation/explain
```

Check:

- Which shard is slow or overloaded?
- Is traffic skewed by tenant/routing key?
- Are shard sizes uneven?
- Are write/search queues rejecting requests?
- Is the disk near watermarks?
- Are merges falling behind?
- Is refresh too frequent?
- Are queries scanning too much data?
- Is a dashboard running expensive aggregations every few seconds?

Enable slow logs for index/search diagnosis:

```http
PUT products-v1/_settings
{
  "index.search.slowlog.threshold.query.warn": "2s",
  "index.search.slowlog.threshold.fetch.warn": "1s",
  "index.indexing.slowlog.threshold.index.warn": "1s"
}
```

### 16.3 Hotspot Solution Playbook

#### Solution 1: Prefer Default Routing When Possible

If you do not need tenant-local routing, let OpenSearch route by `_id`.

Use high-cardinality, evenly distributed IDs:

```text
good: uuid, ulid with enough randomness, hash-based ID
bad: tenant_42_sequence_1 if all writes for tenant_42 are routed together
```

#### Solution 2: Salt the Routing Key

If one tenant is too hot, route across buckets:

```text
routing = tenant_id + ":" + bucket
bucket = hash(document_id) % 16
```

Example:

```text
tenant_big:0
tenant_big:1
...
tenant_big:15
```

Writes distribute across 16 routing buckets.

Read tradeoff:

- To query all tenant data, fan out to 16 buckets.
- To query one known document, compute the same bucket.

This is a common real-world fix for hot tenants.

#### Solution 3: Use Partitioned Routing

If you want custom routing but one routing key is too hot, create the index with `index.routing_partition_size`.

This spreads one routing value across a subset of primary shards.

Use when:

- Tenant queries should still avoid full-cluster fan-out.
- Large tenants need more than one shard.

#### Solution 4: Isolate Whale Tenants

For multi-tenant SaaS:

```text
small tenants -> shared index
large tenants -> dedicated index or dedicated cluster
```

Benefits:

- Prevents one tenant from affecting everyone.
- Allows tenant-specific shard count, replicas, refresh, and retention.
- Easier billing and capacity planning.

#### Solution 5: Use Data Streams and Rollover

For logs/events:

- Use data streams.
- Use index templates.
- Rollover by size, age, and document count.
- Keep shard sizes controlled.
- Delete or move old indexes by lifecycle policy.

Example lifecycle:

```text
hot index: current writes and searches
warm index: less frequent searches
cold index: rare searches
deleted: retention expired
```

#### Solution 6: Increase Primary Shards Carefully

More primary shards can increase write parallelism, but too many shards create overhead.

If an existing index is under-sharded:

- Split the index if the setup allows it.
- Reindex into a new index with more primary shards.
- Use aliases to switch traffic.

#### Solution 7: Reduce Expensive Query Work

For search hotspots:

- Add time filters.
- Avoid leading wildcard queries.
- Avoid unbounded `terms` aggregations.
- Use `keyword` fields for filters/aggregations.
- Use `search_after` + PIT for deep pagination.
- Precompute dashboard summaries.
- Cache application-level common results when acceptable.
- Use request cache for repeated aggregation queries where applicable.

#### Solution 8: Tune Ingest

For write hotspots:

- Use Bulk API.
- Increase `refresh_interval` for heavy ingestion.
- Use ingest pipelines carefully.
- Move CPU-heavy parsing outside OpenSearch when needed.
- Use Kafka or another queue to smooth bursts.
- Make producers respect backpressure and retries.
- Watch write rejections.

#### Solution 9: Scale the Right Role

Scale based on the bottleneck:

| Bottleneck | Add/change |
|---|---|
| Search CPU | More data/search replicas, search nodes, coordinating nodes, query optimization |
| Indexing CPU | More primary shards/data nodes, bulk tuning, segment replication, ingest offload |
| Disk I/O | Faster disks, fewer merges, less update churn, better shard sizing |
| Heap | Reduce field count, reduce shard count, reduce aggregation cardinality |
| Cluster state | Fewer indexes/shards/fields, stronger cluster-manager nodes |
| Ingest pipeline CPU | Dedicated ingest nodes or external processing |

## 17. Real-World Problem Solving

### 17.1 Problem: E-Commerce Product Search

Requirements:

- Search by title and description.
- Filter by category, brand, price, rating, availability.
- Sort by relevance, price, rating, newest.
- Show facets.
- Update product inventory and price.

Recommended architecture:

```text
Product service database: source of truth
  -> change data capture / events
  -> indexing service
  -> OpenSearch product index
  -> search API
```

Mapping:

```http
PUT products-v1
{
  "settings": {
    "number_of_shards": 6,
    "number_of_replicas": 1
  },
  "mappings": {
    "dynamic": "strict",
    "properties": {
      "product_id": { "type": "keyword" },
      "title": {
        "type": "text",
        "fields": {
          "keyword": { "type": "keyword", "ignore_above": 256 }
        }
      },
      "description": { "type": "text" },
      "brand": { "type": "keyword" },
      "category": { "type": "keyword" },
      "price": { "type": "double" },
      "rating": { "type": "float" },
      "in_stock": { "type": "boolean" },
      "updated_at": { "type": "date" }
    }
  }
}
```

Query:

```http
GET products-v1/_search
{
  "size": 20,
  "query": {
    "bool": {
      "must": [
        {
          "multi_match": {
            "query": "wireless headphones",
            "fields": ["title^3", "description"]
          }
        }
      ],
      "filter": [
        { "term": { "in_stock": true } },
        { "range": { "price": { "gte": 50, "lte": 300 } } }
      ]
    }
  },
  "aggs": {
    "brands": {
      "terms": { "field": "brand", "size": 20 }
    },
    "categories": {
      "terms": { "field": "category", "size": 20 }
    }
  }
}
```

Production decisions:

- Product DB remains source of truth.
- Search index is rebuildable.
- Use aliases: `products_current -> products-v1`.
- Reindex to `products-v2` when mappings change.
- Update inventory carefully; high-frequency inventory may stay in primary DB/cache and be joined in application if update rate is too high.

### 17.2 Problem: Log Analytics Platform

Requirements:

- Ingest logs from thousands of services.
- Search by service, level, trace ID, request ID.
- Aggregate error counts per minute.
- Retain hot logs for 14 days and cold logs for 90 days.

Architecture:

```text
Apps
  -> log agent
  -> Kafka / buffer
  -> ingest workers
  -> OpenSearch data stream
  -> dashboards and alerting
```

Index strategy:

- Use data streams.
- Rollover by size and age.
- Use index templates.
- Keep mappings controlled.
- Avoid dynamic field explosion.
- Store arbitrary log metadata in `flat_object` when needed.

Query:

```http
GET logs-app-*/_search
{
  "size": 100,
  "query": {
    "bool": {
      "filter": [
        { "term": { "service.keyword": "checkout" } },
        { "range": { "@timestamp": { "gte": "now-15m" } } },
        { "range": { "status_code": { "gte": 500 } } }
      ]
    }
  },
  "sort": [
    { "@timestamp": "desc" }
  ]
}
```

Aggregation:

```http
GET logs-app-*/_search
{
  "size": 0,
  "query": {
    "bool": {
      "filter": [
        { "term": { "service.keyword": "checkout" } },
        { "range": { "@timestamp": { "gte": "now-1h" } } }
      ]
    }
  },
  "aggs": {
    "errors_per_minute": {
      "date_histogram": {
        "field": "@timestamp",
        "fixed_interval": "1m"
      },
      "aggs": {
        "errors": {
          "filter": {
            "range": {
              "status_code": {
                "gte": 500
              }
            }
          }
        }
      }
    }
  }
}
```

Hotspot risk:

- One service produces most logs.
- One current write index has too few shards.
- Dashboard queries last 7 days every 5 seconds.
- Dynamic labels create mapping explosion.

Fix:

- Isolate high-volume services.
- Rollover by size.
- Pre-aggregate metrics outside OpenSearch.
- Use strict mappings and `flat_object`.
- Add throttling and backpressure.

### 17.3 Problem: Multi-Tenant SaaS Search Hotspot

Scenario:

```text
1000 tenants share one index.
Custom routing = tenant_id.
Tenant A becomes huge.
Tenant A overloads one shard.
```

Symptoms:

- One shard has high CPU and queueing.
- Queries for other tenants slow down.
- `_cat/shards` shows uneven docs/store/load.

Fix options:

1. Short term:
   - Add read replicas if search-heavy.
   - Reduce heavy tenant dashboard frequency.
   - Cache common tenant queries.
   - Move expensive aggregations to async jobs.

2. Medium term:
   - Reindex with salted routing.
   - Use `tenant_id:bucket` routing.
   - Query all buckets for tenant-level queries.

3. Long term:
   - Put large tenants in dedicated indexes.
   - Keep small tenants in shared indexes.
   - Use index aliases to hide routing/index choices from application code.

### 17.4 Problem: URL Shortener Search and Analytics

OpenSearch should not be the primary redirect lookup path.

Use:

```text
short_code -> destination_url
```

in a low-latency KV database such as Redis, DynamoDB, ScyllaDB, Cassandra, Aerospike, or a relational DB with cache.

Use OpenSearch for:

- Searching links by owner, title, tags, campaign.
- Analytics event search.
- Aggregations by country/device/referrer.
- Debugging abuse/spam.

Architecture:

```text
Redirect path:
client -> edge/cache/KV -> redirect

Analytics path:
redirect event -> Kafka -> OpenSearch -> dashboards/search
```

This keeps the critical redirect path fast and uses OpenSearch for what it does best.

## 18. Using OpenSearch As A Key-Value Store

You can use OpenSearch as a key-value lookup store using `_id`.

Example:

```http
PUT user_profiles/_doc/u123
{
  "user_id": "u123",
  "name": "Asha",
  "plan": "premium",
  "city": "Bengaluru"
}
```

Read:

```http
GET user_profiles/_doc/u123
```

Multi-get:

```http
GET user_profiles/_mget
{
  "ids": ["u123", "u456", "u789"]
}
```

Use this pattern when:

- The document is also searched.
- The data is a read model.
- The system can tolerate OpenSearch operational semantics.
- Occasional near-real-time search delay is acceptable.
- The data can be rebuilt from another source.

Avoid this pattern when:

- You need ultra-low-latency hot-key access.
- You need high write/update rates on the same keys.
- You need strong transactions.
- You need strict source-of-truth semantics.
- You only need simple key-value lookup and no search.

Better alternatives for pure KV:

- Redis for cache/session.
- DynamoDB/Aerospike/ScyllaDB/Cassandra for high-scale KV.
- PostgreSQL/MySQL for transactional entity storage.

## 19. Using OpenSearch As A Document Database

OpenSearch stores JSON documents and can behave like a document database for search-oriented read models.

Good document-style use cases:

- Product documents.
- User profile search documents.
- Content/documents.
- Tickets/issues.
- Knowledge base articles.
- Event documents.
- Audit records.

But it differs from MongoDB/Couchbase/DynamoDB:

- Updates are heavier.
- No multi-document ACID transactions.
- No rich transactional constraints.
- Query behavior depends heavily on mapping.
- Search index size is larger due to inverted index and doc values.
- Mappings are harder to change in place.

Best practice:

```text
Primary DB owns truth.
OpenSearch stores denormalized search document.
Application writes primary DB.
CDC/event pipeline updates OpenSearch.
OpenSearch can be rebuilt.
```

## 20. Optimistic Concurrency Control

Use `_seq_no` and `_primary_term` to prevent lost updates.

Get document:

```http
GET products/_doc/p1
```

Response includes:

```json
{
  "_seq_no": 10,
  "_primary_term": 3
}
```

Conditional update:

```http
PUT products/_doc/p1?if_seq_no=10&if_primary_term=3
{
  "product_id": "p1",
  "price": 199
}
```

If another update happened first, OpenSearch rejects the write with a version conflict.

Use this for:

- Preventing lost updates.
- Idempotent indexing.
- CDC pipelines that need ordering checks.

Do not use this as a replacement for relational transactions across multiple entities.

## 21. Pros and Cons

### 21.1 Pros

- Excellent full-text search.
- Strong filtering and faceted navigation.
- Powerful near-real-time aggregations.
- Distributed horizontal scaling.
- JSON document model.
- Rich ecosystem and APIs.
- Good for logs, observability, and security analytics.
- Supports analyzers, synonyms, ranking, highlighting, geo, vector search.
- Index aliases make zero-downtime reindexing practical.
- Replicas improve search throughput and availability.
- Snapshots support backup and migration.

### 21.2 Cons

- Operationally complex at scale.
- Shard planning matters.
- Mapping mistakes are expensive to fix.
- High-cardinality aggregations can be costly.
- Dynamic mapping can cause mapping explosion.
- Updates are internally delete-plus-add.
- Search is near-real-time, not instantly visible by default.
- Not a transactional source-of-truth database.
- Heap, disk, merge, and cluster-state pressure need active monitoring.
- Expensive if used for long-retention cold analytics.
- Cross-cluster and remote-store setups require careful operations.
- Query DSL can become complex.

## 22. Production Readiness Checklist

### 22.1 Data Modeling

- Define access patterns before creating mappings.
- Use explicit mappings for production.
- Use `text` for search and `keyword` for exact filters/aggregations.
- Use `dynamic: strict` or controlled dynamic templates.
- Avoid mapping explosion.
- Avoid huge nested arrays.
- Avoid storing frequently changing counters in OpenSearch.
- Keep documents reasonably sized.
- Decide whether `_source` should be stored, filtered, or compressed.

### 22.2 Index and Shard Strategy

- Choose primary shard count based on volume, growth, and throughput.
- Use replicas for HA and search capacity.
- Use data streams for time-series data.
- Use rollover by size/age/docs.
- Keep shard sizes manageable.
- Avoid too many tiny shards.
- Use aliases for versioned indexes.
- Plan reindexing strategy before mapping changes.

### 22.3 Cluster Topology

- Use dedicated cluster-manager nodes in production.
- Use data nodes sized for storage and query/index load.
- Use ingest nodes if pipelines are heavy.
- Use coordinating nodes for high client fan-out workloads.
- Use zone/rack awareness.
- Keep replicas across failure domains.
- Avoid running all roles on all nodes at large scale unless intentionally simple.

### 22.4 Capacity Planning

Estimate:

- Raw data per day.
- Index expansion factor.
- Retention period.
- Replica factor.
- Query rate.
- Ingestion rate.
- Peak burst rate.
- Dashboard frequency.
- Aggregation cardinality.
- Recovery time objective.

Rough storage formula:

```text
required_storage =
  raw_data_per_day
  * index_expansion_factor
  * retention_days
  * (1 + number_of_replicas)
  * safety_margin
```

Index expansion varies heavily by mapping, analyzers, doc values, and stored fields. Measure with real samples.

### 22.5 Hardware

OpenSearch usually benefits from:

- Fast SSD/NVMe.
- Enough RAM for heap and OS page cache.
- Strong CPU for indexing/search/aggregations.
- High network bandwidth for replication and recovery.
- Separate disks or isolation where needed.

JVM heap guidance:

- Do not give all RAM to heap.
- Leave memory for OS page cache.
- Keep heap below compressed ordinary object pointer limits when applicable.
- Monitor GC, heap pressure, and circuit breakers.

### 22.6 Ingestion

- Use Bulk API.
- Use retry with exponential backoff.
- Respect 429/rejections.
- Make ingestion idempotent.
- Avoid per-document refresh.
- Use queues for burst absorption.
- Validate mapping before writing production data.
- Separate parsing/enrichment from OpenSearch when pipelines become CPU-heavy.

### 22.7 Search and Aggregation Safety

- Add time filters to log/event queries.
- Limit page sizes.
- Avoid deep `from`/`size`.
- Use `search_after` and PIT for deep pagination.
- Avoid leading wildcard queries.
- Avoid expensive scripts on broad result sets.
- Use `keyword` fields for aggregations.
- Watch high-cardinality aggregations.
- Use slow logs.
- Add request timeouts.
- Protect public search endpoints with validation and rate limits.

### 22.8 Security

- Enable TLS.
- Use authentication and role-based access control.
- Restrict admin APIs.
- Use least-privilege roles for applications.
- Protect snapshot repositories.
- Avoid exposing OpenSearch directly to the public internet.
- Enable audit logging where required.
- Rotate credentials.
- Separate tenant data with index permissions or application-level controls.

### 22.9 Backup and Disaster Recovery

- Configure snapshot repositories.
- Take automated snapshots.
- Test restore regularly.
- Document restore runbooks.
- Use cross-cluster replication only when its lag and consistency model fit the requirement.
- Keep index templates and cluster settings under version control.
- Do not treat replicas as backups. Replicas protect availability, not accidental deletes or corruption.

### 22.10 Monitoring

Monitor:

- Cluster health: green/yellow/red.
- Node CPU.
- JVM heap and GC.
- Disk usage and watermarks.
- Indexing rate and latency.
- Search rate and latency.
- Thread pool queues/rejections.
- Segment count.
- Merge time and backlog.
- Refresh time.
- Query cache/request cache.
- Circuit breaker trips.
- Shard sizes and allocation.
- Cluster pending tasks.
- Snapshot success/failure.
- Replication lag for cross-cluster setups.

Useful commands:

```http
GET _cluster/health
GET _cat/nodes?v
GET _cat/indices?v&s=store.size:desc
GET _cat/shards?v
GET _cat/allocation?v
GET _nodes/stats
GET _nodes/hot_threads
GET _cluster/pending_tasks
```

### 22.11 Upgrade and Migration

- Read version-specific breaking changes.
- Test plugins.
- Snapshot before upgrade.
- Use rolling upgrades only when supported.
- Reindex when mapping or version compatibility requires it.
- Use aliases for blue/green index migrations.
- Validate dashboards, alerts, and clients after upgrade.

## 23. Common Design Patterns

### 23.1 Search Index As Read Model

```text
Primary DB -> CDC/events -> indexing service -> OpenSearch
```

Use when:

- Primary DB handles transactions.
- OpenSearch handles search and analytics.
- Index can be rebuilt.

### 23.2 Alias-Based Reindex

```text
products_current -> products-v1

Create products-v2
Reindex products-v1 -> products-v2
Validate
Switch alias products_current -> products-v2
Delete old index later
```

Benefits:

- Zero or low downtime.
- Safe schema evolution.
- Rollback path if old index is kept.

### 23.3 Time-Series Data Stream

```text
logs-app
  -> backing index logs-app-000001
  -> backing index logs-app-000002
  -> rollover
  -> retention/delete
```

Use for:

- Logs.
- Metrics.
- Traces.
- Clickstream.
- Audit events.

### 23.4 Tenant Isolation

Options:

| Model | Use when |
|---|---|
| Shared index | Many small tenants, low traffic, simple operations |
| Shared index with routing | Tenant queries dominate and tenants are similar size |
| Shared index with salted routing | Some tenants are larger but still share infrastructure |
| Index per large tenant | Large tenants need isolation |
| Cluster per very large tenant | Compliance, noisy-neighbor, or dedicated SLA requirements |

## 24. Operational Failure Modes

### 24.1 Cluster Yellow

Meaning:

- Primary shards are assigned.
- Some replicas are not assigned.

Impact:

- Data is searchable.
- HA is reduced.
- Another node failure may cause data unavailability.

Fix:

- Check allocation explain.
- Check disk watermarks.
- Check replica count vs node count.
- Check shard allocation awareness.

### 24.2 Cluster Red

Meaning:

- One or more primary shards are unassigned.

Impact:

- Some data is unavailable.
- Writes/searches to affected shards fail.

Fix:

- Stop writes if needed.
- Check allocation explain.
- Restore from snapshot if data is lost.
- Recover failed nodes if possible.
- Avoid unsafe allocation unless you understand data-loss implications.

### 24.3 Disk Watermark Reached

OpenSearch protects itself when disk usage is high.

Symptoms:

- Shards stop allocating.
- Index may become read-only.
- Writes fail.

Fix:

- Add disk capacity.
- Delete expired indexes.
- Move shards.
- Increase nodes.
- Fix retention/rollover.
- Never run production clusters near full disk.

### 24.4 Circuit Breakers

Circuit breakers prevent memory exhaustion.

Common causes:

- High-cardinality aggregations.
- Huge result windows.
- Scripts over broad matches.
- Fielddata on text fields.
- Too many concurrent dashboards.

Fix:

- Optimize queries.
- Reduce aggregation size/cardinality.
- Add filters.
- Use keyword/doc values.
- Pre-aggregate.
- Add capacity only after query shape is sane.

## 25. OpenSearch vs Other Databases

| System | Best At | OpenSearch Comparison |
|---|---|---|
| PostgreSQL/MySQL | Transactions, joins, constraints | Use as source of truth; OpenSearch as search index |
| MongoDB | Document database with primary data semantics | OpenSearch has stronger search/aggregation, weaker transactional document DB semantics |
| Redis | Ultra-fast cache/KV | OpenSearch is slower/heavier but searchable |
| ScyllaDB/Cassandra | Massive predictable key/range access | OpenSearch is better for ad hoc search/filter/aggregations |
| Aerospike | Low-latency KV/document access | OpenSearch is better for text search and facets |
| ClickHouse/Pinot/Druid | OLAP analytics | OpenSearch is better for search and recent event investigation; OLAP engines are better for large analytical scans |
| Kafka | Durable event log | OpenSearch is a query/index target, not a queue |
| S3/Lakehouse | Cheap long-term storage | OpenSearch is expensive for cold long-retention raw data |

## 26. What Operations OpenSearch Solves

OpenSearch solves:

- Full-text search.
- Exact filtering.
- Faceted navigation.
- Time-series log search.
- Near real-time dashboards.
- Security event investigation.
- Alerting over indexed data.
- Document retrieval.
- Autocomplete and suggestions.
- Geospatial search.
- Vector and hybrid search.
- Approximate analytics over recent indexed data.

OpenSearch partially solves:

- Document database workloads.
- Key-value lookup by ID.
- Real-time analytics.
- Multi-tenant search.

OpenSearch does not solve well:

- OLTP transactions.
- Relational joins.
- Strongly consistent counters.
- Message queues.
- Ledger systems.
- Cheap cold-storage analytics.
- Arbitrary data lake exploration.

## 27. Decision Framework

Ask these questions before choosing OpenSearch:

1. Do users need search relevance, filtering, facets, or investigation?
2. Can data be denormalized into search documents?
3. Is another system the source of truth?
4. Can the index be rebuilt?
5. Are mappings known and controlled?
6. Is near-real-time search acceptable?
7. What is the retention period?
8. What are the top queries and aggregations?
9. What fields have high cardinality?
10. What is the write/update ratio?
11. What is the expected shard size?
12. How will backups and restores be tested?
13. How will hotspots be detected and isolated?
14. What is the disaster recovery plan?

If the answer to "Can the index be rebuilt?" is no, be very careful. OpenSearch can be durable, but it is usually best treated as a rebuildable search/read model rather than the only source of truth.

## 28. Discussion Session Notes

This section captures the discussion topics from the request in Q&A form.

### 28.1 Explain OpenSearch DB In All Aspects

OpenSearch is a distributed Lucene-based search and analytics engine. It stores JSON documents in indexes, splits indexes into shards, replicates shards for availability and search capacity, and uses inverted indexes/doc values/segments to make search and aggregations fast. It should usually be used as a search/read model fed from a primary source-of-truth database.

### 28.2 How To Solve Hotspot Problem

First identify whether the hotspot is caused by routing, shard count, tenant skew, query shape, aggregation cardinality, updates, or hardware.

Then apply the matching fix:

- Bad routing: remove custom routing, salt routing, or use partitioned routing.
- Hot tenant: isolate into dedicated index/cluster.
- Current write index overloaded: increase primary shards carefully and use rollover.
- Search-heavy: add replicas/search nodes and optimize queries.
- Aggregation-heavy: reduce cardinality, add filters, pre-aggregate.
- Update-heavy: move counters/state to a better primary database and index periodically.

### 28.3 Bloom Filter

Bloom filters answer "definitely absent or maybe present." In OpenSearch, Bloom-filter-style fuzzy sets can optimize document ID lookups, especially negative lookups. They are not the main data structure for full-text search or aggregations. The main search structure is Lucene's inverted index.

### 28.4 Replication

OpenSearch uses primary and replica shards. Writes go to the primary shard and are replicated. Replica shards improve availability and search capacity. OpenSearch also supports segment replication and remote-backed storage in newer architectures, plus search replicas for separating search from indexing workloads.

### 28.5 CAP Theorem

OpenSearch uses quorum-based cluster coordination to prevent split-brain. During network partitions, the majority side can continue cluster-state decisions, while the minority side may lose availability for writes or metadata changes. Search is near real-time, not strictly linearizable. Use OpenSearch for search/read models, not as the only strongly consistent transactional store.

### 28.6 Different Operations It Solves

OpenSearch solves search, filtering, faceting, log/event investigation, dashboards, aggregations, autocomplete, geospatial search, vector search, and document retrieval. It is not the best system for transactions, queues, relational joins, or high-frequency hot-key updates.

### 28.7 Pros and Cons

Pros:

- Fast full-text search.
- Powerful filters and aggregations.
- Distributed and horizontally scalable.
- Good ecosystem.
- Great for observability/search.

Cons:

- Operationally complex.
- Mapping and shard mistakes are costly.
- Not a transactional database.
- Expensive for high-cardinality aggregations and cold data.
- Updates are heavier than in KV/document databases.

### 28.8 Aggregation, Filtering, Query

Use:

- `match` and `multi_match` for full-text search.
- `term`, `terms`, `range`, `exists` in filter context for exact filtering.
- `terms`, `date_histogram`, `range`, `avg`, `sum`, `percentiles`, and pipeline aggregations for analytics.
- `keyword` fields for aggregations and sorting.
- `search_after` + PIT for deep pagination.

### 28.9 Use As Key-Value Store

Use `_id` and GET/MGET for key-value style reads. This is acceptable when the document is also searched and the index is a read model. Do not use OpenSearch as a pure high-frequency KV store when Redis, DynamoDB, Aerospike, ScyllaDB, Cassandra, or PostgreSQL would fit better.

### 28.10 Use As Document DB

OpenSearch stores JSON and can serve document-style reads, but it lacks strong multi-document transactions and update efficiency compared with purpose-built document databases. Best practice is to denormalize data into search documents and rebuild the index from a primary source.

### 28.11 Production Aspects To Cover

Production OpenSearch requires:

- Explicit mappings.
- Shard and replica planning.
- Data streams/rollover/retention.
- Backpressure-aware ingestion.
- Security and TLS.
- Snapshots and restore testing.
- Slow logs and monitoring.
- Cluster-manager quorum.
- Zone-aware shard allocation.
- Capacity planning.
- Upgrade strategy.
- Hotspot isolation.
- Disaster recovery.

## 29. Quick Commands Cheat Sheet

Create index:

```http
PUT my-index
{
  "settings": {
    "number_of_shards": 3,
    "number_of_replicas": 1
  },
  "mappings": {
    "properties": {
      "id": { "type": "keyword" },
      "title": {
        "type": "text",
        "fields": {
          "keyword": { "type": "keyword" }
        }
      },
      "created_at": { "type": "date" }
    }
  }
}
```

Index document:

```http
PUT my-index/_doc/1
{
  "id": "1",
  "title": "OpenSearch deep dive",
  "created_at": "2026-05-27T10:00:00Z"
}
```

Get document:

```http
GET my-index/_doc/1
```

Search:

```http
GET my-index/_search
{
  "query": {
    "match": {
      "title": "deep dive"
    }
  }
}
```

Filter:

```http
GET my-index/_search
{
  "query": {
    "bool": {
      "filter": [
        {
          "range": {
            "created_at": {
              "gte": "now-7d"
            }
          }
        }
      ]
    }
  }
}
```

Aggregation:

```http
GET my-index/_search
{
  "size": 0,
  "aggs": {
    "docs_per_day": {
      "date_histogram": {
        "field": "created_at",
        "calendar_interval": "day"
      }
    }
  }
}
```

Cluster health:

```http
GET _cluster/health
```

Shard view:

```http
GET _cat/shards?v
```

Hot threads:

```http
GET _nodes/hot_threads
```

Allocation explain:

```http
GET _cluster/allocation/explain
```

## 30. References

- OpenSearch documentation, concepts and cluster architecture: https://docs.opensearch.org/latest/getting-started/concepts/
- OpenSearch documentation, indexing data and shard/replica settings: https://docs.opensearch.org/latest/opensearch/index-data/
- OpenSearch documentation, Query DSL: https://docs.opensearch.org/latest/query-dsl/
- OpenSearch documentation, term vs full-text queries: https://docs.opensearch.org/latest/query-dsl/term-vs-full-text/
- OpenSearch documentation, filter search results: https://docs.opensearch.org/latest/search-plugins/filter-search/
- OpenSearch documentation, aggregations: https://docs.opensearch.org/latest/aggregations/
- OpenSearch documentation, routing: https://docs.opensearch.org/latest/field-types/metadata-fields/routing/
- OpenSearch documentation, index settings and document ID lookup fuzzy set/Bloom filter settings: https://docs.opensearch.org/latest/install-and-configure/configuring-opensearch/index-settings/
- OpenSearch documentation, mapping explosion: https://docs.opensearch.org/latest/mappings/mapping-explosion/
- OpenSearch documentation, point in time and pagination: https://docs.opensearch.org/latest/search-plugins/searching-data/point-in-time/
- OpenSearch documentation, segment replication: https://docs.opensearch.org/latest/tuning-your-cluster/availability-and-recovery/segment-replication/
- OpenSearch documentation, remote-backed storage: https://docs.opensearch.org/latest/tuning-your-cluster/availability-and-recovery/remote-store/
- OpenSearch documentation, search replicas and separating index/search workloads: https://docs.opensearch.org/latest/tuning-your-cluster/separate-index-and-search-workloads/
- OpenSearch documentation, voting and quorum: https://docs.opensearch.org/latest/tuning-your-cluster/discovery-cluster-formation/voting-quorums/
- OpenSearch documentation, snapshots: https://docs.opensearch.org/latest/tuning-your-cluster/availability-and-recovery/snapshots/
- Apache Lucene Bloom codec package: https://lucene.apache.org/core/9_11_1/codecs/org/apache/lucene/codecs/bloom/package-summary.html

---

## 31. When to Use Which Query Keyword — Decision Guide

### 31.1 Field Types: `text` vs `keyword`

Before choosing a query type, understand how OpenSearch stores your data:

| Aspect | `text` field | `keyword` field |
|--------|-------------|-----------------|
| Storage | Analyzed → broken into tokens via analyzer | Stored as-is, exact single token |
| Example | `"Quick Brown Fox"` → `["quick", "brown", "fox"]` | `"Quick Brown Fox"` → `["Quick Brown Fox"]` |
| Use case | Full-text search, natural language | Exact match, filtering, sorting, aggregations |
| Queried with | `match`, `match_phrase`, `multi_match` | `term`, `terms`, `wildcard`, `prefix` |
| Sorting | Cannot sort directly (use `.keyword` sub-field) | Sortable |
| Aggregation | Not ideal (tokenized buckets) | Ideal for buckets |

**Mapping example with both:**
```json
{
  "properties": {
    "product_name": {
      "type": "text",
      "fields": {
        "keyword": { "type": "keyword", "ignore_above": 256 }
      }
    },
    "status": { "type": "keyword" },
    "description": { "type": "text", "analyzer": "english" }
  }
}
```

### 31.2 Query Types — When to Use Each

#### `term` — Exact Value Match (No Analysis)

**When to use:**
- Filtering by status, ID, enum values, exact codes
- Querying `keyword` fields or numeric/date/boolean fields
- You need exact match, no fuzziness or tokenization

**When NOT to use:**
- On `text` fields (the stored tokens won't match your input because analyzer already split them)

```json
// Find all orders with status exactly "SHIPPED"
{ "query": { "term": { "status": "SHIPPED" } } }

// WRONG: searching text field with term — will likely return 0 results
// because "Quick Brown Fox" was tokenized to ["quick","brown","fox"]
{ "query": { "term": { "description": "Quick Brown Fox" } } }
```

#### `terms` — Match Any of Multiple Exact Values

**When to use:**
- IN-clause equivalent: match any value from a list
- Filtering by multiple statuses, IDs, categories

```json
// Orders that are either SHIPPED or DELIVERED
{ "query": { "terms": { "status": ["SHIPPED", "DELIVERED"] } } }
```

#### `match` — Full-Text Search (Analyzed)

**When to use:**
- Searching natural language text
- User-facing search boxes
- You want tokenization, stemming, and relevance scoring
- Searching `text` fields

**How it works:** Your query string is analyzed with the same analyzer as the field, then matched against stored tokens.

```json
// Searches for documents containing "quick" OR "brown" (default OR operator)
{ "query": { "match": { "description": "quick brown" } } }

// Searches for documents containing "quick" AND "brown"
{ "query": { "match": { "description": { "query": "quick brown", "operator": "and" } } } }
```

#### `match_phrase` — Exact Phrase in Order

**When to use:**
- Searching for words that must appear together in sequence
- Finding exact phrases within text content

```json
// Documents containing "brown fox" as a contiguous phrase
{ "query": { "match_phrase": { "description": "brown fox" } } }
```

#### `multi_match` — Search Across Multiple Fields

**When to use:**
- Search bar querying title + description + tags simultaneously
- You want relevance across multiple fields with different boosts

**Types:**
| Type | Behavior |
|------|----------|
| `best_fields` (default) | Score from best matching field |
| `most_fields` | Sum of scores from all matching fields |
| `cross_fields` | Treats all fields as one big field |
| `phrase` | Runs `match_phrase` on each field |

```json
{
  "query": {
    "multi_match": {
      "query": "opensearch cluster",
      "fields": ["title^3", "description", "tags^2"],
      "type": "best_fields"
    }
  }
}
```

#### `range` — Numeric/Date Range Filtering

**When to use:**
- Date ranges (last 7 days, between dates)
- Price ranges, age ranges, any numeric bounds
- Timestamp-based queries

```json
// Orders from the last 30 days with amount > 100
{
  "query": {
    "bool": {
      "filter": [
        { "range": { "created_at": { "gte": "now-30d/d", "lte": "now/d" } } },
        { "range": { "amount": { "gt": 100 } } }
      ]
    }
  }
}
```

**Operators:** `gt` (>), `gte` (>=), `lt` (<), `lte` (<=)

#### `exists` — Field Has a Value

**When to use:**
- Finding documents where a field is present (not null/missing)
- Filtering out incomplete records

```json
// Documents that have a "phone_number" field
{ "query": { "exists": { "field": "phone_number" } } }

// Documents WITHOUT phone_number (negate with must_not)
{ "query": { "bool": { "must_not": { "exists": { "field": "phone_number" } } } } }
```

#### `wildcard` / `prefix` — Pattern Matching on Keywords

**When to use:**
- Autocomplete on keyword fields
- Pattern matching (use sparingly — expensive)

```json
{ "query": { "prefix": { "product_code": "SKU-" } } }
{ "query": { "wildcard": { "email.keyword": "*@gmail.com" } } }
```

⚠️ **Warning:** Leading wildcards (`*something`) scan ALL terms in the index — very expensive.

### 31.3 Bool Query Compound Clauses

The `bool` query combines multiple conditions. Each clause type has different behavior:

| Clause | Scoring? | Required? | Cached? | Use for |
|--------|----------|-----------|---------|---------|
| `must` | Yes (adds to score) | Yes (must match) | No | Conditions that affect relevance ranking |
| `filter` | No (0 score) | Yes (must match) | Yes ✓ | Exact filters where ranking doesn't matter |
| `should` | Yes (boosts score) | No (optional*) | No | Nice-to-have matches that boost ranking |
| `must_not` | No (excludes) | Yes (must NOT match) | Yes ✓ | Exclusion conditions |

*`should` becomes required if there's no `must` or `filter` clause (at least one `should` must match).

**Critical decision: `must` vs `filter`**

```json
// BAD: Using must for a status filter — wastes CPU calculating relevance score for exact match
{
  "query": {
    "bool": {
      "must": [
        { "match": { "description": "opensearch tutorial" } },
        { "term": { "status": "published" } }  // ← This doesn't need scoring!
      ]
    }
  }
}

// GOOD: filter for exact conditions, must only for relevance-based matching
{
  "query": {
    "bool": {
      "must": [
        { "match": { "description": "opensearch tutorial" } }
      ],
      "filter": [
        { "term": { "status": "published" } },
        { "range": { "created_at": { "gte": "2026-01-01" } } }
      ]
    }
  }
}
```

**`should` for boosting:**
```json
{
  "query": {
    "bool": {
      "must": [
        { "match": { "title": "database" } }
      ],
      "should": [
        { "term": { "is_featured": true } },   // Featured articles rank higher
        { "term": { "category": "tutorial" } }  // Tutorials rank higher
      ],
      "filter": [
        { "term": { "status": "published" } }
      ]
    }
  }
}
```

### 31.4 Decision Matrix — Quick Reference

| I want to... | Use this | On this field type |
|--------------|----------|-------------------|
| Search natural text with relevance | `match` | `text` |
| Find exact phrase in text | `match_phrase` | `text` |
| Search across multiple text fields | `multi_match` | `text` |
| Filter by exact status/ID/enum | `term` in `filter` | `keyword` |
| Filter by multiple values (IN clause) | `terms` in `filter` | `keyword` |
| Filter by date range | `range` in `filter` | `date` |
| Filter by numeric range | `range` in `filter` | `integer`/`float` |
| Check if field exists | `exists` | any |
| Exclude documents | `must_not` | any |
| Boost results meeting soft criteria | `should` | any |
| Combine multiple conditions | `bool` query | mixed |
| Sort by a string field | Sort on `.keyword` sub-field | `keyword` |
| Aggregate (group by) | Aggregation on `keyword` field | `keyword` |
| Autocomplete/prefix search | `prefix` or `match_bool_prefix` | `keyword` / `search_as_you_type` |

### 31.5 Common Mistakes

| Mistake | Why it fails | Fix |
|---------|-------------|-----|
| `term` on a `text` field | Text is analyzed/lowercased; "iPhone" stored as "iphone" | Use `match` or query the `.keyword` sub-field |
| `match` on a `keyword` field | Works but doesn't leverage analysis; might miss matches | Use `term` for keyword fields |
| All conditions in `must` | Calculates relevance scores unnecessarily for exact filters | Move exact filters to `filter` clause |
| `should` expecting it to be required | `should` is optional when `must`/`filter` exist | Use `minimum_should_match: 1` if at least one should match |
| Wildcard with leading `*` | Scans entire term dictionary — extremely slow | Restructure data or use n-gram tokenizer |

---

## 32. Time-Based Partitioning and Cross-Partition Queries

### 32.1 Why Time-Based Indexes?

OpenSearch does NOT have native table-level partitioning like PostgreSQL. Instead, it achieves partitioning by using **multiple indexes with time-based naming conventions**.

**Benefits:**
- **Efficient deletion:** Drop an entire old index instead of deleting documents one-by-one
- **Hot/warm/cold tiering:** Move older indexes to cheaper storage
- **Performance:** Queries targeting recent data only search relevant indexes
- **Independent scaling:** Recent indexes get more replicas/shards; old ones get fewer
- **Mapping evolution:** New indexes can have updated mappings without reindexing old data

### 32.2 Index Naming Conventions

```
Pattern: {index-prefix}-{time-period}

Examples:
  logs-2026-01          (monthly)
  logs-2026-01-15       (daily)
  orders-2026-q1        (quarterly)
  metrics-2026-w03      (weekly)
```

**Monthly partitioning is the most common** for business data — good balance between too many indexes (daily) and too-large indexes (yearly).

### 32.3 How to Create Time-Based Indexes

#### Option A: Index Templates + Application Logic

**Step 1: Create an index template**
```json
PUT _index_template/orders-template
{
  "index_patterns": ["orders-*"],
  "template": {
    "settings": {
      "number_of_shards": 3,
      "number_of_replicas": 1
    },
    "mappings": {
      "properties": {
        "order_id": { "type": "keyword" },
        "customer_id": { "type": "keyword" },
        "amount": { "type": "float" },
        "status": { "type": "keyword" },
        "created_at": { "type": "date" },
        "description": { "type": "text" }
      }
    }
  }
}
```

**Step 2: Application writes to the correct index based on timestamp**
```python
from datetime import datetime

def get_index_name(timestamp: datetime) -> str:
    return f"orders-{timestamp.strftime('%Y-%m')}"

# Indexing a document
doc = {"order_id": "ORD-123", "amount": 99.99, "created_at": "2026-05-15T10:30:00Z"}
index_name = get_index_name(datetime(2026, 5, 15))  # → "orders-2026-05"
opensearch_client.index(index=index_name, body=doc)
```

#### Option B: Data Streams (Append-Only, Recommended for Logs/Events)

```json
PUT _index_template/logs-stream-template
{
  "index_patterns": ["logs-stream*"],
  "data_stream": {},
  "template": {
    "settings": { "number_of_shards": 2 },
    "mappings": {
      "properties": {
        "@timestamp": { "type": "date" },
        "message": { "type": "text" },
        "level": { "type": "keyword" }
      }
    }
  }
}

// Create the data stream
PUT _data_stream/logs-stream

// Indexing — OpenSearch automatically routes to the current backing index
POST logs-stream/_doc
{ "@timestamp": "2026-05-15T10:30:00Z", "message": "Request received", "level": "INFO" }
```

Data streams automatically create new backing indexes based on rollover conditions.

#### Option C: Rollover with ILM (Index Lifecycle Management)

```json
// Define a lifecycle policy
PUT _plugins/_ism/policies/orders-lifecycle
{
  "policy": {
    "description": "Monthly rollover with hot-warm-cold",
    "default_state": "hot",
    "states": [
      {
        "name": "hot",
        "actions": [
          { "rollover": { "min_index_age": "30d", "min_size": "50gb" } }
        ],
        "transitions": [
          { "state_name": "warm", "conditions": { "min_index_age": "30d" } }
        ]
      },
      {
        "name": "warm",
        "actions": [
          { "replica_count": { "number_of_replicas": 1 } },
          { "force_merge": { "max_num_segments": 1 } }
        ],
        "transitions": [
          { "state_name": "cold", "conditions": { "min_index_age": "90d" } }
        ]
      },
      {
        "name": "cold",
        "actions": [
          { "read_only": {} }
        ],
        "transitions": [
          { "state_name": "delete", "conditions": { "min_index_age": "365d" } }
        ]
      },
      {
        "name": "delete",
        "actions": [{ "delete": {} }]
      }
    ]
  }
}
```

### 32.4 Querying Across Multiple Partitions

This is the key question: **how to fetch data from multiple monthly indexes?**

#### Method 1: Wildcard Index Pattern (Most Common)

```json
// Search across ALL order indexes
GET orders-*/_search
{ "query": { "match": { "status": "SHIPPED" } } }

// Search only 2026 indexes
GET orders-2026-*/_search
{ "query": { "range": { "amount": { "gte": 100 } } } }

// Search specific months (Q1 2026)
GET orders-2026-01,orders-2026-02,orders-2026-03/_search
{ "query": { "term": { "customer_id": "CUST-456" } } }
```

#### Method 2: Index Aliases (Recommended for Production)

```json
// Create aliases that group indexes logically
POST _aliases
{
  "actions": [
    { "add": { "index": "orders-2026-01", "alias": "orders-current-quarter" } },
    { "add": { "index": "orders-2026-02", "alias": "orders-current-quarter" } },
    { "add": { "index": "orders-2026-03", "alias": "orders-current-quarter" } },
    { "add": { "index": "orders-*", "alias": "orders-all" } }
  ]
}

// Query the alias — searches all underlying indexes
GET orders-current-quarter/_search
{ "query": { "term": { "status": "PENDING" } } }

// Alias with built-in filter (filtered alias)
POST _aliases
{
  "actions": [
    {
      "add": {
        "index": "orders-*",
        "alias": "orders-high-value",
        "filter": { "range": { "amount": { "gte": 1000 } } }
      }
    }
  ]
}
```

#### Method 3: Date Math in Index Names

```json
// Query last 3 months dynamically (no hardcoding month names)
GET /<orders-{now/M}>/_search           // Current month
GET /<orders-{now/M-1M}>/_search        // Last month
GET /<orders-{now/M-1M}>,<orders-{now/M}>/_search  // Last 2 months

// Date math syntax: <index-{date-math-expression}>
// Must URL-encode: < → %3C, > → %3E, / → %2F
// Actual request:
GET /%3Corders-%7Bnow%2FM%7D%3E,%3Corders-%7Bnow%2FM-1M%7D%3E/_search
```

### 32.5 Performance Considerations for Cross-Partition Queries

| Strategy | Performance | When to Use |
|----------|-------------|-------------|
| Wildcard `orders-*` | Searches ALL indexes (fan-out to all shards) | When you truly need data from all time |
| Specific indexes `orders-2026-01,orders-2026-02` | Only searches named indexes | When you know the time range |
| Filtered alias | Searches subset with pre-applied filter | When you repeatedly query the same subset |
| Date math | Dynamic, always current | For rolling windows (last N months) |

**Tips:**
- Always combine cross-index queries with a `range` filter on the timestamp field — even if the index name limits the time range, the filter helps OpenSearch skip irrelevant shards within the index.
- Use `preference=_local` to prefer local shard copies.
- Set `allow_partial_search_results: false` if you need guaranteed complete results.

### 32.6 Maintaining Time-Based Partitions

```
Monthly Maintenance Workflow:
┌─────────────────────────────────────────────┐
│ Start of Month                               │
│ 1. New index auto-created by template        │
│ 2. Update write alias to point to new index  │
│ 3. Old index becomes read-only               │
├─────────────────────────────────────────────┤
│ End of Retention Period                       │
│ 4. Move old indexes to warm/cold tier         │
│ 5. Reduce replicas on old indexes             │
│ 6. Force merge old indexes (1 segment)        │
│ 7. Delete indexes beyond retention policy     │
└─────────────────────────────────────────────┘
```

**Write alias pattern:**
```json
// Write alias always points to current month's index
POST _aliases
{
  "actions": [
    { "remove": { "index": "orders-2026-04", "alias": "orders-write" } },
    { "add": { "index": "orders-2026-05", "alias": "orders-write", "is_write_index": true } }
  ]
}

// Application always writes to the alias
POST orders-write/_doc
{ "order_id": "ORD-789", "created_at": "2026-05-28T14:00:00Z" }
```

---

## 33. OpenSearch vs Redis — Deep Comparison and Decision Guide

### 33.1 Fundamental Architecture Differences

| Aspect | OpenSearch | Redis |
|--------|-----------|-------|
| **Core purpose** | Full-text search and analytics engine | In-memory data structure store / cache |
| **Data model** | Documents (JSON) with rich mappings | Key-value with typed data structures |
| **Storage** | Disk-based with OS page cache (Lucene segments) | Primarily in-memory (RAM) |
| **Indexing** | Inverted index (every field value → document IDs) | Hash tables, skip lists, radix trees |
| **Query language** | Query DSL (JSON), SQL plugin | Commands (GET, SET, HGET, ZADD...) |
| **Write path** | Index → refresh (1s) → searchable (near-real-time) | Write → immediately available |
| **Latency** | 5-50ms typical search | 0.1-1ms typical read |
| **Throughput** | 1K-50K queries/sec per node | 100K-1M ops/sec per node |
| **Consistency** | Eventually consistent (tunable) | Strong within single node, eventual in cluster |
| **Scaling** | Horizontal (shards across nodes) | Horizontal (hash slots in cluster mode) |
| **Data size** | TB-scale on disk | Limited by RAM (typically GB-scale) |

### 33.2 What Each Does Best

#### OpenSearch Excels At:

1. **Full-text search** — "Find all products matching 'wireless noise-cancelling headphones'"
2. **Fuzzy/typo-tolerant search** — "Find 'iphone' even if user typed 'iphon'"
3. **Relevance ranking** — Return results sorted by how well they match
4. **Complex analytics** — Aggregations, histograms, term frequency, nested groupings
5. **Log analytics** — Searching through terabytes of log data with time filters
6. **Geospatial queries** — "Find restaurants within 5km"
7. **Schema-flexible documents** — Rich nested objects, arrays, multi-field mappings
8. **Cross-field search** — Search across title + description + tags simultaneously

#### Redis Excels At:

1. **Caching** — Store computed results for instant retrieval
2. **Session storage** — User sessions with TTL-based expiry
3. **Rate limiting** — Sliding window counters per user/IP
4. **Real-time leaderboards** — Sorted sets for rankings
5. **Pub/sub messaging** — Real-time event broadcasting
6. **Distributed locks** — Mutex across services (Redlock)
7. **Queues** — Job queues with BRPOP/BLPOP
8. **Counters/inventory** — Atomic increment/decrement (views, stock)
9. **Exact key lookup** — O(1) retrieval by known key

### 33.3 Query Capability Comparison

| Query Type | OpenSearch | Redis |
|-----------|-----------|-------|
| Get by exact ID | ✅ `GET index/_doc/id` | ✅ `GET key` (faster) |
| Get by exact field value | ✅ `term` query | ✅ If you model key as `field:value` |
| Full-text search | ✅ Native (inverted index) | ❌ Not designed for this (RedisSearch module adds limited support) |
| Fuzzy/typo matching | ✅ Native | ❌ |
| Range queries | ✅ Native | ⚠️ Sorted sets only (ZRANGEBYSCORE) |
| Aggregations (GROUP BY) | ✅ Native (terms, histogram, date_histogram) | ❌ Must compute in application |
| Sorting by relevance | ✅ Native (TF-IDF / BM25) | ❌ |
| Geospatial | ✅ Native | ✅ GEO commands |
| Joins/relations | ⚠️ Limited (nested, parent-child) | ❌ |
| Transactions | ❌ | ✅ MULTI/EXEC |
| TTL/expiry | ⚠️ Per index (ILM) | ✅ Per key (native) |
| Pub/Sub | ❌ | ✅ Native |
| Atomic counters | ❌ | ✅ INCR/DECR |

### 33.4 Data Freshness and Consistency

| Aspect | OpenSearch | Redis |
|--------|-----------|-------|
| Write-to-read delay | ~1 second (refresh interval) | Instant (0ms) |
| Can force immediate read? | Yes (`?refresh=true`) but expensive | Not needed — always immediate |
| Consistency model | Eventually consistent | Strong on single node, eventual in cluster |
| Suitable for counters? | No (risk of lost updates) | Yes (INCR is atomic) |
| Suitable for inventory? | No (stale reads) | Yes (with WATCH/MULTI) |
| Suitable for search? | Yes (designed for it) | No (not designed for it) |

### 33.5 Cost and Resource Comparison

| Factor | OpenSearch | Redis |
|--------|-----------|-------|
| Memory cost | Uses disk + OS cache (cheaper per TB) | Everything in RAM (expensive per GB) |
| Storage cost | 1TB feasible on standard SSDs | 1TB = 1TB of RAM (~$10K+/month in cloud) |
| Node count for 1TB data | 3-5 nodes (standard instances) | 50+ nodes (memory-optimized) |
| CPU usage | High during indexing and complex queries | Low (simple data structure operations) |
| Typical cloud cost | $500-2000/month for moderate workload | $100-500/month for caching workload |
| Data durability | Durable (segments on disk + replicas) | Optional (RDB/AOF), risk of data loss |

### 33.6 Decision Matrix — When to Use Which

| Scenario | Use OpenSearch | Use Redis | Use Both |
|----------|:---:|:---:|:---:|
| E-commerce product search | ✅ | | |
| Shopping cart storage | | ✅ | |
| Product catalog with search + caching | | | ✅ |
| Log aggregation and analysis | ✅ | | |
| User session storage | | ✅ | |
| Real-time analytics dashboard | ✅ (aggregations) | | |
| Rate limiting | | ✅ | |
| Autocomplete/typeahead | ✅ | ⚠️ (sorted sets work for simple cases) | |
| Leaderboard | | ✅ | |
| Full-text search on user content | ✅ | | |
| Caching expensive API responses | | ✅ | |
| Distributed locking | | ✅ | |
| Monitoring metrics (time-series) | ✅ | | |
| Job queue | | ✅ (or dedicated queue) | |
| Search with cached results | | | ✅ |
| Geolocation queries | ✅ | ✅ (simpler geo) | |
| Event sourcing / audit log | ✅ | | |
| Counting page views (real-time) | | ✅ | |
| Finding similar documents | ✅ | | |
| Feature flags | | ✅ | |

### 33.7 Common Pattern: Using Both Together

```
┌──────────────────────────────────────────────────────────────┐
│                      Application Layer                         │
├──────────────────────────────────────────────────────────────┤
│                                                                │
│  Search Request Flow:                                          │
│  ┌─────────┐     ┌─────────┐     ┌─────────────────┐         │
│  │ Client  │────→│  Redis  │────→│   OpenSearch     │         │
│  │ Request │     │ (Cache) │     │ (Search Engine)  │         │
│  └─────────┘     └─────────┘     └─────────────────┘         │
│                                                                │
│  1. Check Redis for cached search results                      │
│  2. Cache miss → Query OpenSearch                              │
│  3. Store results in Redis with TTL (e.g., 60s)               │
│  4. Return results to client                                   │
│                                                                │
│  Write Flow:                                                   │
│  ┌─────────┐     ┌─────────────────┐     ┌─────────┐         │
│  │ Client  │────→│   OpenSearch     │────→│  Redis  │         │
│  │ Write   │     │ (Index Doc)      │     │ (Bust)  │         │
│  └─────────┘     └─────────────────┘     └─────────┘         │
│                                                                │
│  1. Index document into OpenSearch                             │
│  2. Invalidate related Redis cache keys                        │
│  3. Next search will fetch fresh results from OpenSearch       │
└──────────────────────────────────────────────────────────────┘
```

### 33.8 Anti-Patterns

| Anti-Pattern | Problem | Correct Approach |
|-------------|---------|-----------------|
| Using Redis for full-text search | No inverted index, no relevance scoring, no analyzers | Use OpenSearch for search |
| Using OpenSearch as a cache | 1s refresh delay, heavier per-query cost | Use Redis for caching |
| Using OpenSearch for counters | Not atomic, stale reads possible | Use Redis INCR |
| Using Redis to store TBs of data | RAM cost is prohibitive | Use OpenSearch (disk-based) |
| Using OpenSearch for session storage | Overkill, unnecessary indexing overhead | Use Redis with TTL |
| Using Redis for complex aggregations | Must compute in application code | Use OpenSearch aggregations |
| Using OpenSearch for pub/sub | Not designed for it | Use Redis Pub/Sub or Kafka |
| Using Redis for audit logs | Data loss risk, no search capability | Use OpenSearch with ILM |

### 33.9 Summary Decision Flowchart

```
START: What do you need?
│
├─── "I need to SEARCH text" ──────────────→ OpenSearch
│
├─── "I need FAST key-value lookup" ────────→ Redis
│
├─── "I need to AGGREGATE/ANALYZE data" ───→ OpenSearch
│
├─── "I need a CACHE layer" ────────────────→ Redis
│
├─── "I need REAL-TIME counters" ───────────→ Redis
│
├─── "I need to RANK by relevance" ─────────→ OpenSearch
│
├─── "I need TTL-based expiry" ─────────────→ Redis
│
├─── "I need to store LARGE datasets" ──────→ OpenSearch (disk-based)
│
├─── "I need IMMEDIATE consistency" ─────────→ Redis
│
├─── "I need search + speed" ───────────────→ Both (OpenSearch + Redis cache)
│
└─── "I need a MESSAGE QUEUE" ──────────────→ Neither (use Kafka/SQS/RabbitMQ)
```
