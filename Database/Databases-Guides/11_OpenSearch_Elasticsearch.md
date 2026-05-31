# OpenSearch / Elasticsearch - Staff Architect Complete Guide

## Table of Contents
1. [Architecture Overview](#architecture-overview)
2. [Inverted Index & Lucene](#inverted-index--lucene)
3. [Indexing & Mapping](#indexing--mapping)
4. [Search & Query DSL](#search--query-dsl)
5. [Cluster Architecture](#cluster-architecture)
6. [Sharding & Replication](#sharding--replication)
7. [Aggregations & Analytics](#aggregations--analytics)
8. [Performance Optimization](#performance-optimization)
9. [Staff Architect Interview Questions](#staff-architect-interview-questions)
10. [Scenario-Based Questions](#scenario-based-questions)

---

## Architecture Overview

### Cluster Architecture
```
┌─────────────────────────────────────────────────────────────┐
│                 OpenSearch/Elasticsearch Cluster              │
│                                                               │
│  Master-Eligible Nodes (3+):                                 │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐                     │
│  │Master   │  │Master   │  │Master   │  Cluster state mgmt  │
│  │Eligible │  │Eligible │  │Eligible │  Index metadata      │
│  │(Active) │  │(Standby)│  │(Standby)│  Shard allocation    │
│  └─────────┘  └─────────┘  └─────────┘                     │
│                                                               │
│  Data Nodes:                                                  │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐       │
│  │  Data   │  │  Data   │  │  Data   │  │  Data   │       │
│  │ Node 1  │  │ Node 2  │  │ Node 3  │  │ Node 4  │       │
│  │         │  │         │  │         │  │         │       │
│  │ Shards: │  │ Shards: │  │ Shards: │  │ Shards: │       │
│  │ [P0][R1]│  │ [P1][R0]│  │ [P2][R3]│  │ [P3][R2]│       │
│  └─────────┘  └─────────┘  └─────────┘  └─────────┘       │
│                                                               │
│  Coordinating Nodes (optional):                              │
│  ┌─────────┐  ┌─────────┐                                   │
│  │  Coord  │  │  Coord  │  Query routing, result merging    │
│  └─────────┘  └─────────┘                                   │
│                                                               │
│  Ingest Nodes:                                               │
│  ┌─────────┐  Document transformation pipelines             │
│  │ Ingest  │                                                 │
│  └─────────┘                                                 │
└─────────────────────────────────────────────────────────────┘
```

### Core Concepts
```
Index: Collection of documents with similar characteristics (like a database table)
Shard: Horizontal partition of an index (is a Lucene index)
Replica: Copy of a primary shard (HA + read throughput)
Document: JSON object stored in an index
Mapping: Schema definition (field types, analyzers)
Segment: Immutable Lucene file within a shard (LSM-like)
```

---

## Inverted Index & Lucene

### Inverted Index Structure
```
Documents:
Doc 1: "The quick brown fox"
Doc 2: "The quick blue car"
Doc 3: "A brown dog"

After analysis (tokenization + lowercasing):

Term Dictionary → Posting Lists:
┌──────────┬───────────────────────────────────┐
│ Term     │ Posting List (DocID, Position...)  │
├──────────┼───────────────────────────────────┤
│ "a"      │ [3:0]                             │
│ "blue"   │ [2:2]                             │
│ "brown"  │ [1:2, 3:1]                        │
│ "car"    │ [2:3]                             │
│ "dog"    │ [3:2]                             │
│ "fox"    │ [1:3]                             │
│ "quick"  │ [1:1, 2:1]                        │
│ "the"    │ [1:0, 2:0]                        │
└──────────┴───────────────────────────────────┘

Additional structures per field:
- Doc values: Column-oriented store for sorting/aggregations
- Norms: Field length normalization (relevance scoring)
- Stored fields: Original JSON document
- Term vectors: Per-document term information (optional)
```

### Lucene Segment Internals
```
Lucene Segment (immutable):
├── .si    - Segment info (metadata)
├── .fnm   - Field names and types
├── .fdx   - Stored fields index
├── .fdt   - Stored fields data
├── .tim   - Term dictionary
├── .tip   - Term index (prefix tree for fast lookup)
├── .doc   - Frequencies and positions (posting lists)
├── .pos   - Position data
├── .pay   - Payloads and offsets
├── .dvd   - Doc values data
├── .dvm   - Doc values metadata
├── .nvd   - Norms data
├── .nvm   - Norms metadata
├── .liv   - Live documents (deleted docs bitmask)
└── .kdd/.kdm - Point values (BKD tree for numerics/geo)

Segment lifecycle:
1. Documents buffered in memory (translog for durability)
2. Refresh (default: 1s): Flush to new Lucene segment → searchable
3. Segments accumulate
4. Merge: Combine small segments into larger ones
   - Reclaims deleted documents
   - Reduces segment count (fewer file handles, faster search)
```

### BKD Tree (Numeric/Geo Indexing)
```
For numeric, date, and geo_point fields:
- Multi-dimensional balanced KD-tree
- O(log N) for range queries
- Block-based for I/O efficiency
- Much faster than inverted index for range queries

Example: Find documents where price BETWEEN 100 AND 500
- BKD tree splits space recursively
- Each leaf block contains sorted values
- Range query touches minimal blocks
```

---

## Indexing & Mapping

### Mapping Types
```json
PUT /products
{
  "mappings": {
    "properties": {
      "name": {
        "type": "text",
        "analyzer": "english",
        "fields": {
          "keyword": { "type": "keyword" },
          "autocomplete": {
            "type": "text",
            "analyzer": "autocomplete_analyzer"
          }
        }
      },
      "price": { "type": "float" },
      "category": { "type": "keyword" },
      "tags": { "type": "keyword" },
      "description": { "type": "text", "analyzer": "english" },
      "created_at": { "type": "date" },
      "location": { "type": "geo_point" },
      "attributes": { "type": "flattened" },
      "reviews": {
        "type": "nested",
        "properties": {
          "author": { "type": "keyword" },
          "rating": { "type": "integer" },
          "text": { "type": "text" }
        }
      }
    }
  }
}
```

### Field Types
```
Text types:
- text: Full-text search (analyzed, tokenized)
- keyword: Exact match, sorting, aggregations (not analyzed)
- completion: Autocomplete suggestions (FST-based)

Numeric types:
- long, integer, short, byte, double, float, half_float, scaled_float

Date: date, date_nanos

Boolean: boolean

Binary: binary (base64 encoded)

Range: integer_range, float_range, date_range, ip_range

Complex:
- object: Inner JSON object (flattened internally)
- nested: Independent inner documents (for arrays of objects)
- flattened: Entire object as single field (low overhead)
- join: Parent-child relationships

Specialized:
- geo_point: Latitude/longitude
- geo_shape: Polygons, circles, etc.
- ip: IPv4/IPv6 addresses
- dense_vector: ML embeddings (kNN search)
- rank_feature: Boost scoring features
```

### Analyzers
```json
PUT /my_index
{
  "settings": {
    "analysis": {
      "analyzer": {
        "autocomplete_analyzer": {
          "type": "custom",
          "tokenizer": "standard",
          "filter": ["lowercase", "autocomplete_filter"]
        }
      },
      "filter": {
        "autocomplete_filter": {
          "type": "edge_ngram",
          "min_gram": 2,
          "max_gram": 20
        }
      }
    }
  }
}

Analysis pipeline:
Input: "The Quick Brown Fox's"
    │
    ▼ Character Filter (html_strip, mapping, pattern_replace)
"The Quick Brown Fox's"
    │
    ▼ Tokenizer (standard, whitespace, ngram, keyword, pattern)
["The", "Quick", "Brown", "Fox's"]
    │
    ▼ Token Filters (lowercase, stemmer, stop, synonym, ngram)
["the", "quick", "brown", "fox"]
    │
    ▼ Indexed terms
```

---

## Search & Query DSL

### Query Types
```json
// Full-text queries
{ "match": { "title": "brown fox" } }
{ "match_phrase": { "title": "brown fox" } }
{ "multi_match": { "query": "brown fox", "fields": ["title^2", "body"] } }

// Term-level queries (exact match, not analyzed)
{ "term": { "status": "published" } }
{ "terms": { "tag": ["search", "elasticsearch"] } }
{ "range": { "price": { "gte": 10, "lte": 100 } } }
{ "exists": { "field": "email" } }
{ "prefix": { "name.keyword": "Joh" } }
{ "wildcard": { "name.keyword": "Jo*n" } }
{ "regexp": { "name.keyword": "joh?n(athan)?" } }
{ "fuzzy": { "name": { "value": "jonh", "fuzziness": "AUTO" } } }

// Compound queries
{
  "bool": {
    "must": [{ "match": { "title": "search" } }],
    "must_not": [{ "term": { "status": "draft" } }],
    "should": [{ "match": { "title": "elasticsearch" } }],
    "filter": [
      { "range": { "date": { "gte": "2024-01-01" } } },
      { "term": { "category": "tech" } }
    ],
    "minimum_should_match": 1
  }
}

// Scoring notes:
// must: Contributes to score
// filter: No scoring (cached, faster)
// should: Optional boost
// must_not: Excludes (no scoring)
```

### Relevance Scoring (BM25)
```
BM25 formula (default since ES 5.0):
score(q,d) = Σ IDF(qi) × (f(qi,d) × (k1+1)) / (f(qi,d) + k1 × (1 - b + b × |d|/avgdl))

Where:
- f(qi,d): Term frequency of qi in document d
- |d|: Document length
- avgdl: Average document length
- k1: Term frequency saturation (default: 1.2)
- b: Length normalization (default: 0.75)
- IDF: Inverse document frequency (rarer terms score higher)

Tuning relevance:
- function_score: Custom scoring functions
- field boosting: "title^3" (title matches worth 3x)
- decay functions: Score by distance (geo, date, numeric)
- script_score: Custom scoring via Painless scripts
```

### Vector Search (kNN)
```json
// Dense vector field
PUT /products
{
  "mappings": {
    "properties": {
      "title_vector": {
        "type": "dense_vector",
        "dims": 768,
        "index": true,
        "similarity": "cosine"
      }
    }
  }
}

// kNN search
POST /products/_search
{
  "knn": {
    "field": "title_vector",
    "query_vector": [0.1, 0.2, ...],
    "k": 10,
    "num_candidates": 100
  }
}

// Hybrid: kNN + keyword filtering
POST /products/_search
{
  "query": { "bool": { "filter": { "term": { "category": "electronics" } } } },
  "knn": {
    "field": "title_vector",
    "query_vector": [0.1, 0.2, ...],
    "k": 10,
    "num_candidates": 100,
    "filter": { "term": { "in_stock": true } }
  }
}
```

---

## Sharding & Replication

### Shard Sizing Guidelines
```
Recommendations:
- Shard size: 10-50GB (optimal for most workloads)
- Max shard size: 65GB (hard limit recommendation)
- Shards per GB heap: 20 shards per GB of heap memory
- Node capacity: Typically 20-40 shards per node

Time-series pattern (ILM - Index Lifecycle Management):
logs-2024.01.15 (1 day = 1 index, 5 primary shards)
logs-2024.01.16
logs-2024.01.17
...

ILM phases:
- Hot: Active writes, fast SSD, more replicas
- Warm: Read-only, can shrink/force-merge, cheaper storage
- Cold: Infrequent access, searchable snapshots
- Frozen: Rarely accessed, mounted from snapshot
- Delete: Remove after retention period

Data streams (preferred for time-series):
POST _data_stream/logs
- Auto-managed backing indices
- Automatic rollover (by size, age, or doc count)
```

### Routing
```json
// Custom routing: Control which shard a document goes to
PUT /orders/_doc/123?routing=customer_456
{ "customer_id": "customer_456", "amount": 99.99 }

// Ensures all documents for a customer on same shard
// Enables efficient customer-scoped queries (single shard)

// Query with routing (targeted to single shard):
GET /orders/_search?routing=customer_456
{ "query": { "term": { "customer_id": "customer_456" } } }

// Without routing: Query hits ALL shards (scatter-gather)
// With routing: Query hits SINGLE shard (much faster)
```

---

## Aggregations & Analytics

### Aggregation Types
```json
POST /orders/_search
{
  "size": 0,
  "aggs": {
    // Bucket aggregation (grouping)
    "by_status": {
      "terms": { "field": "status", "size": 10 },
      "aggs": {
        // Metric aggregation (stats per bucket)
        "total_amount": { "sum": { "field": "amount" } },
        "avg_amount": { "avg": { "field": "amount" } },
        
        // Sub-aggregation (histogram within each status)
        "monthly": {
          "date_histogram": {
            "field": "created_at",
            "calendar_interval": "month"
          },
          "aggs": {
            "revenue": { "sum": { "field": "amount" } }
          }
        }
      }
    },
    
    // Pipeline aggregation (aggregation of aggregation)
    "max_monthly_revenue": {
      "max_bucket": { "buckets_path": "by_status>monthly>revenue" }
    },
    
    // Cardinality (approximate distinct count, HLL)
    "unique_customers": {
      "cardinality": { "field": "customer_id", "precision_threshold": 40000 }
    },
    
    // Percentiles
    "latency_percentiles": {
      "percentiles": { "field": "response_time", "percents": [50, 90, 95, 99] }
    }
  }
}
```

---

## Performance Optimization

### Indexing Performance
```
1. Bulk API (always batch):
   POST /_bulk
   {"index":{"_index":"logs"}}
   {"message":"log1","@timestamp":"2024-01-15T10:00:00"}
   {"index":{"_index":"logs"}}
   {"message":"log2","@timestamp":"2024-01-15T10:00:01"}
   
   Batch size: 5-15MB per request

2. Refresh interval:
   PUT /logs/_settings
   { "index": { "refresh_interval": "30s" } }
   // Default 1s → Increase for write-heavy (less overhead)
   // Set -1 during bulk load (disable refresh)

3. Replica count during bulk load:
   PUT /logs/_settings
   { "index": { "number_of_replicas": 0 } }
   // Restore after load completes

4. Translog settings:
   "index.translog.durability": "async"
   "index.translog.sync_interval": "5s"
   // Trades durability for write speed
```

### Search Performance
```
1. Filter vs Query:
   - Use "filter" context for exact matches (cached, no scoring)
   - Use "query" context only when relevance scoring needed

2. Routing: Route queries to single shard when possible

3. Index sorting (at index creation):
   "sort": { "field": ["timestamp"], "order": ["desc"] }
   // Enables early termination for sorted queries

4. Force merge (for read-only indices):
   POST /logs-2024.01/_forcemerge?max_num_segments=1
   // Single segment per shard = fastest searches

5. Doc values: Disable for fields not used in aggregations/sorting:
   "myfield": { "type": "text", "doc_values": false }

6. Source filtering: Only return needed fields:
   { "_source": ["title", "date"], "query": { ... } }
```

---

## Staff Architect Interview Questions

**Q1: When would you use OpenSearch vs a relational database for search?**
**A:** OpenSearch/ES when: Full-text search (relevance ranking), log analytics, unstructured/semi-structured data, aggregations on high-cardinality fields, fuzzy matching, autocomplete, vector search. Relational DB when: ACID transactions, complex JOINs, exact queries on structured data, frequent updates to same records, strong consistency requirements.

**Q2: Explain the trade-off between more shards and fewer larger shards.**
**A:**
- More shards: Better parallelism per query, easier rebalancing. But: Higher overhead (memory per shard ~40MB), more network connections, slower aggregations (more scatter-gather)
- Fewer shards: Less overhead, better for small indices. But: Single shard limits node-level parallelism, harder to rebalance, can become too large
- Sweet spot: 10-50GB per shard, total shards < 20 × heap_GB per node

**Q3: How do you handle schema evolution in Elasticsearch?**
**A:**
- Fields cannot be deleted from mappings (ever)
- Field type cannot be changed after creation
- Solutions: Reindex to new index with updated mapping, use aliases for zero-downtime cutover, use runtime fields for temporary/calculated fields without reindexing
- Data streams + ILM handle time-series schema evolution (new backing index gets new mapping)

**Q4: Explain how Elasticsearch handles near real-time search.**
**A:** 
Writes go to: Translog (fsync for durability) + In-memory buffer.
Every `refresh_interval` (1s default): Buffer flushed to new Lucene segment → searchable.
Documents are NOT immediately searchable after write (NRT = ~1s delay).
For immediate visibility: `POST /index/_refresh` or `?refresh=wait_for` on write.
Trade-off: More frequent refresh = more segments = slower search until merge.

---

## Scenario-Based Questions

### Scenario 1: Designing a Log Analytics Platform

**Requirements:** 500GB/day logs, 30-day retention, real-time search, dashboards.

```
Index strategy:
- Data stream: "logs" with daily backing indices
- ILM policy:
  Hot (0-2 days): 3 primary, 1 replica, fast SSD
  Warm (2-7 days): Shrink to 1 primary, force-merge, cheaper SSD
  Cold (7-30 days): Searchable snapshot (S3)
  Delete: After 30 days

Cluster sizing:
- 500GB/day × 1.1 (overhead) × 2 (hot replicas) = 1.1TB/day hot writes
- Hot tier: 3 data nodes (i3.4xlarge: 3.8TB NVMe each)
- Warm tier: 3 data nodes (d2.xlarge: larger, slower disks)
- Cold tier: Searchable snapshots on S3
- Master: 3 dedicated m5.large nodes
- Coordinating: 2 nodes for Kibana/query routing

Mapping optimization:
- Disable _source on non-debug indices (50% storage savings)
- Use keyword only for fields not needing full-text
- Enable best_compression for warm/cold indices
- Disable doc_values for fields not aggregated

Ingest pipeline:
Filebeat → Kafka → Logstash/Vector → OpenSearch
- Kafka buffers during peak/outages
- Logstash enriches (geoip, user-agent parsing)
- Bulk indexing with 10MB batch size
```

### Scenario 2: E-Commerce Product Search

**Requirements:** 10M products, autocomplete, faceted search, relevance tuning.

```json
// Index design with multi-field mapping
PUT /products
{
  "settings": {
    "number_of_shards": 5,
    "number_of_replicas": 2,
    "analysis": {
      "analyzer": {
        "autocomplete": {
          "tokenizer": "standard",
          "filter": ["lowercase", "edge_ngram_filter"]
        }
      },
      "filter": {
        "edge_ngram_filter": {
          "type": "edge_ngram",
          "min_gram": 2,
          "max_gram": 15
        }
      }
    }
  },
  "mappings": {
    "properties": {
      "name": {
        "type": "text",
        "analyzer": "english",
        "fields": {
          "keyword": { "type": "keyword" },
          "autocomplete": { "type": "text", "analyzer": "autocomplete" }
        }
      },
      "category": { "type": "keyword" },
      "brand": { "type": "keyword" },
      "price": { "type": "scaled_float", "scaling_factor": 100 },
      "rating": { "type": "half_float" },
      "in_stock": { "type": "boolean" },
      "popularity_score": { "type": "rank_feature" }
    }
  }
}

// Search with facets, boosting, and autocomplete
POST /products/_search
{
  "query": {
    "function_score": {
      "query": {
        "bool": {
          "must": { "multi_match": { "query": "wireless headphones", "fields": ["name^3", "description"] } },
          "filter": [
            { "term": { "in_stock": true } },
            { "range": { "price": { "lte": 200 } } }
          ]
        }
      },
      "functions": [
        { "rank_feature": { "field": "popularity_score", "boost": 2 } },
        { "field_value_factor": { "field": "rating", "modifier": "log1p" } }
      ]
    }
  },
  "aggs": {
    "categories": { "terms": { "field": "category", "size": 20 } },
    "brands": { "terms": { "field": "brand", "size": 20 } },
    "price_ranges": {
      "range": { "field": "price", "ranges": [
        { "to": 50 }, { "from": 50, "to": 100 }, { "from": 100, "to": 200 }, { "from": 200 }
      ]}
    }
  }
}
```

