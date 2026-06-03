# OpenSearch/Elasticsearch - Real World Use Cases & Production Guide

## Table of Contents
1. [Core Concepts](#core-concepts)
2. [Real-World Use Cases](#real-world-use-cases)
3. [Replication](#replication)
4. [Scalability](#scalability)
5. [Production Setup](#production-setup)
6. [Performance Benchmarks](#performance-benchmarks)

---

## Core Concepts

### Inverted Index

The fundamental data structure powering full-text search:

```
Document Ingestion:
                                                    
  Doc 1: "quick brown fox"        INVERTED INDEX
  Doc 2: "quick red car"     ┌─────────────────────────┐
  Doc 3: "brown fox jumps"   │  Term     │ Postings    │
                              ├───────────┼─────────────┤
         │                    │ brown     │ [1, 3]      │
         ▼                    │ car       │ [2]         │
  ┌──────────────┐           │ fox       │ [1, 3]      │
  │  Analyzer    │           │ jumps     │ [3]         │
  │  Pipeline    │           │ quick     │ [1, 2]      │
  └──────────────┘           │ red       │ [2]         │
         │                    └───────────┴─────────────┘
         ▼                    
  Tokens stored in                Posting List Entry:
  Lucene segments                 [docID, freq, position, offset]
```

**Posting List Details:**
- Document ID (which doc contains term)
- Term Frequency (how often in doc)
- Position (where in doc - for phrase queries)
- Offsets (character positions - for highlighting)

### Analyzers Pipeline

```
Input Text: "The Quick-Brown FOX's"
                │
                ▼
┌───────────────────────────────────┐
│  CHARACTER FILTERS                │
│  html_strip, pattern_replace     │
│  "The Quick-Brown FOX's"         │
└───────────────┬───────────────────┘
                │
                ▼
┌───────────────────────────────────┐
│  TOKENIZER                        │
│  standard, whitespace, keyword    │
│  ["The", "Quick", "Brown",       │
│   "FOX's"]                        │
└───────────────┬───────────────────┘
                │
                ▼
┌───────────────────────────────────┐
│  TOKEN FILTERS                    │
│  lowercase, stemmer, stop,        │
│  synonym, edge_ngram              │
│  ["quick", "brown", "fox"]        │
└───────────────────────────────────┘
```

**Built-in Analyzers:**
| Analyzer | Tokenizer | Filters | Use Case |
|----------|-----------|---------|----------|
| standard | standard | lowercase, stop | General text |
| simple | letter | lowercase | Simple splitting |
| whitespace | whitespace | none | Structured codes |
| keyword | keyword (no-op) | none | Exact match |
| custom | configurable | configurable | Domain-specific |

### BKD Trees (Block KD Trees)

Used for numeric, date, and geo_point fields:

```
                    ┌─────────────┐
                    │ Root: x < 5 │
                    └──────┬──────┘
                     ┌─────┴─────┐
                     ▼           ▼
              ┌──────────┐ ┌──────────┐
              │ y < 3    │ │ y < 7    │
              └────┬─────┘ └────┬─────┘
               ┌───┴───┐    ┌───┴───┐
               ▼       ▼    ▼       ▼
            [leaf]  [leaf] [leaf]  [leaf]
            
  - O(log n) range queries
  - Efficient for: range, geo_bounding_box, geo_distance
  - Points stored in leaves (block size ~512-1024)
  - Dimensional split alternates axes
```

### Lucene Segments & Near-Real-Time Search

```
Write Path:
                                              
  Index Request ──► In-Memory Buffer ──► Segment (searchable)
                         │                    │
                         ▼                    ▼
                    Translog              Commit Point
                    (WAL on disk)        (fsync'd segment)

Timeline:
  t=0     Document indexed → in buffer + translog
  t=1s    refresh_interval → new segment created (NRT)
  t=30m   flush → segment fsync'd, translog cleared

Segment Lifecycle:
  ┌──────┐  ┌──────┐  ┌──────┐     ┌───────────────┐
  │ Seg1 │  │ Seg2 │  │ Seg3 │ ──► │ Merged Segment│
  │ 10MB │  │ 15MB │  │ 8MB  │     │    33MB       │
  └──────┘  └──────┘  └──────┘     └───────────────┘
  
  Segments are IMMUTABLE:
  - Deletes = bitmask (.del file)
  - Updates = delete old + index new
  - Merge = combine + purge deletes
```

### Doc Values vs Fielddata

```
                    COLUMNAR STORAGE
                    
  Doc Values (on disk, default for non-text):
  ┌─────────┬────────────────────────┐
  │ Doc ID  │ Field Value            │
  ├─────────┼────────────────────────┤
  │ 0       │ 42                     │
  │ 1       │ 17                     │
  │ 2       │ 99                     │
  └─────────┴────────────────────────┘
  Used for: sorting, aggregations, scripting
  Built at index time, memory-mapped

  Fielddata (in-heap, for text fields):
  ┌─────────┬────────────────────────┐
  │ Term    │ Doc IDs                │
  ├─────────┼────────────────────────┤
  │ quick   │ [0, 1, 5]             │
  │ brown   │ [0, 3]                │
  └─────────┴────────────────────────┘
  AVOID: unbounded heap usage
  Use keyword sub-field instead
```

### BM25 Scoring

```
score(q, d) = Σ IDF(t) * (tf(t,d) * (k1 + 1)) / (tf(t,d) + k1 * (1 - b + b * |d|/avgdl))

Where:
  tf(t,d)  = term frequency in document
  IDF(t)   = log(1 + (N - df + 0.5) / (df + 0.5))
  |d|      = document length
  avgdl    = average document length
  k1       = 1.2 (term frequency saturation)
  b        = 0.75 (length normalization)

Key Properties:
  - Term frequency saturates (unlike TF-IDF)
  - Short documents get slight boost
  - Rare terms score higher (IDF)
```

### Aggregations Framework

```
Aggregation Types:
                    
┌─────────────────────────────────────────────────┐
│ BUCKET (grouping)     │ METRIC (calculations)   │
├───────────────────────┼─────────────────────────┤
│ terms                 │ avg, sum, min, max      │
│ date_histogram        │ cardinality (HLL)       │
│ range                 │ percentiles (t-digest)  │
│ filters               │ stats, extended_stats   │
│ geohash_grid          │ top_hits                │
│ composite             │ scripted_metric         │
└───────────────────────┴─────────────────────────┘

│ PIPELINE (agg on aggs)                          │
├─────────────────────────────────────────────────┤
│ moving_avg, derivative, cumulative_sum          │
│ bucket_selector, bucket_sort                    │
└─────────────────────────────────────────────────┘

Execution: collect docs → build buckets → compute metrics
           (scatter to shards → gather at coordinator)
```

---

## Real-World Use Cases

### 1. Wikipedia Full-Text Search

**Scale:** 60M+ articles, 300+ languages, ~20B tokens indexed, 50K+ queries/sec

```
Architecture:
                                                    
  ┌─────────────┐     ┌────────────────────────────────────────────┐
  │  MediaWiki  │     │          Elasticsearch Cluster              │
  │  PHP App    │     │                                            │
  │             │     │  ┌──────────┐  ┌──────────┐  ┌──────────┐ │
  │  Cirrus-    │────►│  │  Coord   │  │  Coord   │  │  Coord   │ │
  │  Search     │     │  │  Node    │  │  Node    │  │  Node    │ │
  │  Plugin     │     │  └────┬─────┘  └────┬─────┘  └────┬─────┘ │
  └─────────────┘     │       │             │             │        │
                      │  ┌────▼─────────────▼─────────────▼────┐   │
        ┌─────────┐   │  │         Data Nodes (per language)   │   │
        │ Kafka   │──►│  │                                     │   │
        │ Change  │   │  │  [en_wiki: 7 shards, 1 replica]    │   │
        │ Stream  │   │  │  [de_wiki: 3 shards, 1 replica]    │   │
        └─────────┘   │  │  [fr_wiki: 3 shards, 1 replica]    │   │
                      │  │  [ja_wiki: 2 shards, 1 replica]    │   │
                      │  │  ... (300+ language indices)        │   │
                      │  └─────────────────────────────────────┘   │
                      │                                            │
                      │  Master Nodes: 3 (dedicated)               │
                      │  Data Nodes: ~100                          │
                      │  Coordinating: ~20                         │
                      └────────────────────────────────────────────┘
```

**Index Mapping:**
```json
{
  "mappings": {
    "properties": {
      "title": {
        "type": "text",
        "analyzer": "custom_wiki",
        "fields": {
          "plain": { "type": "text", "analyzer": "plain" },
          "prefix": { "type": "text", "analyzer": "prefix_analyzer" },
          "near_match": { "type": "text", "analyzer": "near_match" }
        }
      },
      "text": {
        "type": "text",
        "analyzer": "custom_wiki",
        "index_options": "offsets",
        "fields": {
          "plain": { "type": "text", "analyzer": "plain" }
        }
      },
      "category": { "type": "keyword" },
      "redirect": {
        "properties": {
          "title": { "type": "text", "analyzer": "near_match" }
        }
      },
      "heading": { "type": "text", "analyzer": "plain" },
      "opening_text": { "type": "text", "analyzer": "custom_wiki" },
      "auxiliary_text": { "type": "text", "analyzer": "plain" },
      "incoming_links": { "type": "integer" },
      "popularity_score": { "type": "float" },
      "timestamp": { "type": "date" },
      "namespace": { "type": "integer" },
      "language": { "type": "keyword" }
    }
  }
}
```

**Query DSL (Title Prefix + Full-Text):**
```json
{
  "query": {
    "bool": {
      "should": [
        {
          "multi_match": {
            "query": "quantum mechanics",
            "fields": ["title^3", "title.plain^2", "heading^1.5"],
            "type": "most_fields"
          }
        },
        {
          "match_phrase_prefix": {
            "title.prefix": {
              "query": "quantum mech",
              "boost": 10
            }
          }
        },
        {
          "match": {
            "text": {
              "query": "quantum mechanics",
              "minimum_should_match": "2<75%"
            }
          }
        }
      ],
      "filter": [
        { "term": { "namespace": 0 } }
      ]
    }
  },
  "rescore": {
    "window_size": 50,
    "query": {
      "rescore_query": {
        "function_score": {
          "functions": [
            {
              "field_value_factor": {
                "field": "incoming_links",
                "modifier": "log2p",
                "missing": 0
              }
            },
            {
              "field_value_factor": {
                "field": "popularity_score",
                "modifier": "sqrt"
              }
            }
          ],
          "score_mode": "multiply"
        }
      },
      "query_weight": 0.7,
      "rescore_query_weight": 1.2
    }
  },
  "highlight": {
    "fields": {
      "text": { "fragment_size": 150, "number_of_fragments": 3 }
    },
    "type": "fvh"
  },
  "suggest": {
    "did_you_mean": {
      "text": "quantm mechancs",
      "phrase": {
        "field": "title.trigram",
        "size": 1,
        "gram_size": 3,
        "direct_generator": [{
          "field": "title.trigram",
          "suggest_mode": "always"
        }]
      }
    }
  }
}
```

**Ingestion Pipeline (CirrusSearch):**
```json
{
  "description": "Wikipedia article processing",
  "processors": [
    {
      "script": {
        "source": "ctx.word_count = ctx.text.split(' ').length"
      }
    },
    {
      "remove": {
        "field": ["_raw_wikitext"],
        "ignore_missing": true
      }
    },
    {
      "set": {
        "field": "indexed_at",
        "value": "{{_ingest.timestamp}}"
      }
    }
  ]
}
```

---

### 2. Netflix Content Discovery

**Scale:** 230M+ subscribers, 15K+ titles, 30+ languages, real-time personalization

```
Architecture:

  ┌────────────┐   ┌────────────┐   ┌────────────────────────────────┐
  │  Netflix   │   │  Studio    │   │       Elasticsearch Cluster     │
  │  UI/Apps   │   │  Tools     │   │                                │
  └─────┬──────┘   └─────┬──────┘   │  ┌─────────────────────────┐  │
        │                 │          │  │  content_catalog         │  │
        ▼                 ▼          │  │  5 shards, 2 replicas   │  │
  ┌───────────────────────────┐     │  ├─────────────────────────┤  │
  │    API Gateway (Zuul)     │     │  │  user_profiles           │  │
  └─────────────┬─────────────┘     │  │  20 shards, 1 replica   │  │
                │                    │  ├─────────────────────────┤  │
                ▼                    │  │  studio_assets           │  │
  ┌───────────────────────────┐     │  │  10 shards, 1 replica   │  │
  │  Search Service (Java)    │────►│  ├─────────────────────────┤  │
  │  - Query planning         │     │  │  subtitles_index         │  │
  │  - A/B test routing       │     │  │  3 shards, 2 replicas   │  │
  │  - Personalization layer  │     │  └─────────────────────────┘  │
  └───────────────────────────┘     │                                │
                │                    │  50 data nodes (i3.4xlarge)    │
                ▼                    │  5 master nodes                │
  ┌───────────────────────────┐     │  10 coordinating nodes         │
  │  Kafka (content updates)  │────►│                                │
  └───────────────────────────┘     └────────────────────────────────┘
```

**Index Mapping:**
```json
{
  "mappings": {
    "properties": {
      "title": {
        "type": "text",
        "analyzer": "netflix_custom",
        "fields": {
          "keyword": { "type": "keyword" },
          "autocomplete": {
            "type": "text",
            "analyzer": "edge_ngram_analyzer",
            "search_analyzer": "standard"
          }
        }
      },
      "title_localized": {
        "type": "object",
        "properties": {
          "en": { "type": "text", "analyzer": "english" },
          "es": { "type": "text", "analyzer": "spanish" },
          "ja": { "type": "text", "analyzer": "kuromoji" },
          "ko": { "type": "text", "analyzer": "nori" }
        }
      },
      "genres": { "type": "keyword" },
      "micro_genres": { "type": "keyword" },
      "cast": {
        "type": "text",
        "fields": { "keyword": { "type": "keyword" } }
      },
      "director": { "type": "keyword" },
      "release_year": { "type": "integer" },
      "maturity_rating": { "type": "keyword" },
      "content_type": { "type": "keyword" },
      "popularity_by_region": {
        "type": "rank_features"
      },
      "embedding_vector": {
        "type": "dense_vector",
        "dims": 256,
        "index": true,
        "similarity": "cosine"
      },
      "availability": {
        "type": "nested",
        "properties": {
          "country": { "type": "keyword" },
          "start_date": { "type": "date" },
          "end_date": { "type": "date" }
        }
      }
    }
  }
}
```

**Query DSL (Personalized Search):**
```json
{
  "query": {
    "bool": {
      "must": [
        {
          "multi_match": {
            "query": "stranger things",
            "fields": [
              "title^5",
              "title.autocomplete^2",
              "title_localized.en^3",
              "cast^2",
              "director"
            ],
            "type": "best_fields",
            "fuzziness": "AUTO"
          }
        }
      ],
      "filter": [
        {
          "nested": {
            "path": "availability",
            "query": {
              "bool": {
                "must": [
                  { "term": { "availability.country": "US" } },
                  { "range": { "availability.start_date": { "lte": "now" } } },
                  { "range": { "availability.end_date": { "gte": "now" } } }
                ]
              }
            }
          }
        },
        {
          "terms": { "maturity_rating": ["TV-14", "TV-MA", "R"] }
        }
      ],
      "should": [
        {
          "rank_feature": {
            "field": "popularity_by_region.US",
            "boost": 2
          }
        },
        {
          "terms": {
            "micro_genres": ["sci-fi-thriller", "supernatural"],
            "boost": 1.5
          }
        },
        {
          "script_score": {
            "query": { "match_all": {} },
            "script": {
              "source": "cosineSimilarity(params.user_vector, 'embedding_vector') + 1.0",
              "params": {
                "user_vector": [0.12, -0.34, 0.56]
              }
            }
          }
        }
      ]
    }
  },
  "size": 20
}
```

---

### 3. Uber Logging Platform (ELK at Scale)

**Scale:** 100+ PB stored, 50+ TB/day ingestion, 100K+ queries/day, 3000+ microservices

```
Architecture:

  ┌──────────────────────────────────────────────────────────┐
  │  3000+ Microservices                                      │
  │  ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐              │
  │  │Svc A│ │Svc B│ │Svc C│ │Svc D│ │Svc E│ ...          │
  │  └──┬──┘ └──┬──┘ └──┬──┘ └──┬──┘ └──┬──┘              │
  └─────┼────────┼───────┼───────┼───────┼─────────────────┘
        │        │       │       │       │
        ▼        ▼       ▼       ▼       ▼
  ┌─────────────────────────────────────────────┐
  │          Kafka Clusters (Multi-DC)           │
  │  logs-raw: 500 partitions, RF=3             │
  │  Throughput: 50TB/day, 5M events/sec        │
  └──────────────────────┬──────────────────────┘
                         │
            ┌────────────┼────────────┐
            ▼            ▼            ▼
  ┌───────────────┐ ┌──────────┐ ┌───────────────┐
  │  Logstash /   │ │  Flink   │ │  Custom       │
  │  Vector       │ │  Stream  │ │  Indexer      │
  │  (parsing)    │ │  (enrich)│ │  (bulk API)   │
  │  200 nodes    │ │          │ │               │
  └───────┬───────┘ └────┬─────┘ └───────┬───────┘
          │               │               │
          ▼               ▼               ▼
  ┌──────────────────────────────────────────────────────────┐
  │              OpenSearch / Elasticsearch Cluster            │
  │                                                          │
  │  HOT TIER (NVMe SSD, 500 nodes)                         │
  │  ┌─────────────────────────────────────────┐            │
  │  │  logs-2024.01.15: 50 shards             │ ◄─ today  │
  │  │  logs-2024.01.14: 50 shards             │ ◄─ -1d    │
  │  └─────────────────────────────────────────┘            │
  │                                                          │
  │  WARM TIER (HDD, 300 nodes)                             │
  │  ┌─────────────────────────────────────────┐            │
  │  │  logs-2024.01.08 to logs-2024.01.13     │ ◄─ 2-7d   │
  │  │  force-merged, read-only                 │            │
  │  └─────────────────────────────────────────┘            │
  │                                                          │
  │  COLD TIER (S3 + searchable snapshots)                  │
  │  ┌─────────────────────────────────────────┐            │
  │  │  logs-2023.12.* (30-90d)                │            │
  │  └─────────────────────────────────────────┘            │
  │                                                          │
  │  FROZEN TIER (S3 only, on-demand)                       │
  │  ┌─────────────────────────────────────────┐            │
  │  │  logs-2023.* (90d+)                     │            │
  │  └─────────────────────────────────────────┘            │
  └──────────────────────────────────────────────────────────┘
```

**Index Template:**
```json
{
  "index_patterns": ["logs-*"],
  "template": {
    "settings": {
      "number_of_shards": 50,
      "number_of_replicas": 1,
      "refresh_interval": "30s",
      "translog.durability": "async",
      "translog.sync_interval": "30s",
      "codec": "best_compression",
      "routing.allocation.require.tier": "hot",
      "merge.scheduler.max_thread_count": 1
    },
    "mappings": {
      "dynamic": "false",
      "properties": {
        "@timestamp": { "type": "date" },
        "level": { "type": "keyword" },
        "service": { "type": "keyword" },
        "host": { "type": "keyword" },
        "datacenter": { "type": "keyword" },
        "trace_id": { "type": "keyword" },
        "span_id": { "type": "keyword" },
        "message": {
          "type": "text",
          "analyzer": "standard",
          "norms": false
        },
        "structured": {
          "type": "flattened"
        },
        "response_time_ms": { "type": "integer" },
        "status_code": { "type": "short" },
        "user_id": { "type": "keyword" },
        "endpoint": { "type": "keyword" }
      }
    }
  },
  "composed_of": ["logs-settings", "logs-mappings"],
  "priority": 200
}
```

**Query DSL (Trace Correlation):**
```json
{
  "query": {
    "bool": {
      "must": [
        { "term": { "trace_id": "abc123def456" } }
      ],
      "filter": [
        {
          "range": {
            "@timestamp": {
              "gte": "now-1h",
              "lte": "now"
            }
          }
        }
      ]
    }
  },
  "sort": [{ "@timestamp": "asc" }],
  "size": 1000,
  "aggs": {
    "by_service": {
      "terms": { "field": "service", "size": 50 },
      "aggs": {
        "error_rate": {
          "avg": {
            "script": "doc['level'].value == 'ERROR' ? 1 : 0"
          }
        },
        "p99_latency": {
          "percentiles": {
            "field": "response_time_ms",
            "percents": [50, 95, 99]
          }
        }
      }
    }
  }
}
```

**ILM Policy:**
```json
{
  "policy": {
    "phases": {
      "hot": {
        "min_age": "0ms",
        "actions": {
          "rollover": {
            "max_age": "1d",
            "max_primary_shard_size": "50gb"
          },
          "set_priority": { "priority": 100 }
        }
      },
      "warm": {
        "min_age": "2d",
        "actions": {
          "shrink": { "number_of_shards": 10 },
          "forcemerge": { "max_num_segments": 1 },
          "allocate": {
            "require": { "tier": "warm" }
          },
          "set_priority": { "priority": 50 }
        }
      },
      "cold": {
        "min_age": "30d",
        "actions": {
          "searchable_snapshot": {
            "snapshot_repository": "s3_repo"
          },
          "allocate": {
            "require": { "tier": "cold" }
          }
        }
      },
      "frozen": {
        "min_age": "90d",
        "actions": {
          "searchable_snapshot": {
            "snapshot_repository": "s3_repo",
            "force_merge_index": true
          }
        }
      },
      "delete": {
        "min_age": "365d",
        "actions": { "delete": {} }
      }
    }
  }
}
```

---

### 4. GitHub Code Search

**Scale:** 200M+ repositories, 15B+ files, 45M+ searches/day, sub-200ms P95

```
Architecture:

  ┌─────────────────┐
  │  GitHub.com     │
  │  Search Bar     │
  └────────┬────────┘
           │
           ▼
  ┌─────────────────────────────────────────────────────────────┐
  │  Search Gateway (routing, rate limiting, auth)               │
  └────────────────────────────┬────────────────────────────────┘
                               │
              ┌────────────────┼────────────────┐
              ▼                ▼                ▼
  ┌───────────────┐  ┌───────────────┐  ┌───────────────────┐
  │  Code Search  │  │  Repo Search  │  │  Issues/PR Search │
  │  Cluster      │  │  Cluster      │  │  Cluster          │
  └───────┬───────┘  └───────────────┘  └───────────────────┘
          │
          ▼
  ┌──────────────────────────────────────────────────────────┐
  │            Code Search Cluster (custom engine)            │
  │                                                          │
  │  Shard Strategy: by repository (consistent hashing)      │
  │                                                          │
  │  ┌────────┐ ┌────────┐ ┌────────┐     ┌────────┐      │
  │  │Shard 0 │ │Shard 1 │ │Shard 2 │ ... │Shard N │      │
  │  │repos   │ │repos   │ │repos   │     │repos   │      │
  │  │0-10K   │ │10K-20K │ │20K-30K │     │        │      │
  │  └────────┘ └────────┘ └────────┘     └────────┘      │
  │                                                          │
  │  Index Structure (per shard):                           │
  │  - Trigram index (for regex: "abc" → ngram lookup)      │
  │  - Symbol index (functions, classes, variables)         │
  │  - Path index (file paths)                              │
  │  - Language classifier output                           │
  │                                                          │
  │  ~640 nodes, 64TB RAM total, NVMe storage              │
  └──────────────────────────────────────────────────────────┘
          ▲
          │
  ┌───────┴───────────────────────────────────────────┐
  │  Indexing Pipeline                                 │
  │  Git push events → Kafka → Delta Indexer          │
  │  Full re-index: ~36 hours (background)            │
  │  Delta index: seconds (per push)                  │
  └───────────────────────────────────────────────────┘
```

**Index Mapping (Elasticsearch-equivalent representation):**
```json
{
  "mappings": {
    "properties": {
      "repo_id": { "type": "long" },
      "repo_name": {
        "type": "text",
        "fields": {
          "keyword": { "type": "keyword" },
          "path_hierarchy": {
            "type": "text",
            "analyzer": "path_analyzer"
          }
        }
      },
      "file_path": {
        "type": "text",
        "analyzer": "path_analyzer",
        "fields": {
          "keyword": { "type": "keyword" },
          "extension": { "type": "keyword" }
        }
      },
      "content": {
        "type": "text",
        "analyzer": "code_analyzer",
        "index_options": "offsets"
      },
      "symbols": {
        "type": "nested",
        "properties": {
          "name": { "type": "text", "analyzer": "camelcase_analyzer" },
          "kind": { "type": "keyword" },
          "line": { "type": "integer" }
        }
      },
      "language": { "type": "keyword" },
      "stars": { "type": "integer" },
      "last_indexed": { "type": "date" },
      "size_bytes": { "type": "integer" }
    }
  },
  "settings": {
    "analysis": {
      "analyzer": {
        "code_analyzer": {
          "tokenizer": "code_tokenizer",
          "filter": ["lowercase", "camelcase_split", "code_stop"]
        },
        "camelcase_analyzer": {
          "tokenizer": "standard",
          "filter": ["camelcase_split", "lowercase"]
        },
        "path_analyzer": {
          "tokenizer": "path_hierarchy"
        }
      },
      "tokenizer": {
        "code_tokenizer": {
          "type": "pattern",
          "pattern": "[^a-zA-Z0-9_]+"
        }
      },
      "filter": {
        "camelcase_split": {
          "type": "word_delimiter_graph",
          "split_on_case_change": true,
          "preserve_original": true
        }
      }
    }
  }
}
```

**Query DSL (Code Search with Regex):**
```json
{
  "query": {
    "bool": {
      "must": [
        {
          "bool": {
            "should": [
              {
                "match_phrase": {
                  "content": "func.*Handler"
                }
              },
              {
                "regexp": {
                  "content": "func [A-Z][a-zA-Z]*Handler"
                }
              }
            ]
          }
        }
      ],
      "filter": [
        { "term": { "language": "go" } },
        { "term": { "file_path.extension": "go" } },
        { "range": { "stars": { "gte": 100 } } }
      ]
    }
  },
  "sort": [
    { "_score": "desc" },
    { "stars": "desc" }
  ],
  "highlight": {
    "fields": {
      "content": {
        "fragment_size": 200,
        "number_of_fragments": 5,
        "pre_tags": ["<mark>"],
        "post_tags": ["</mark>"]
      }
    }
  },
  "size": 30
}
```

---

### 5. Booking.com Hotel Search

**Scale:** 28M+ listings, 1.5M+ searches/min peak, 200+ countries, real-time availability

```
Architecture:

  ┌────────────┐  ┌────────────┐  ┌────────────┐
  │  Web App   │  │  Mobile    │  │  Partner   │
  │            │  │  Apps      │  │  API       │
  └─────┬──────┘  └─────┬──────┘  └─────┬──────┘
        │                │               │
        ▼                ▼               ▼
  ┌──────────────────────────────────────────────┐
  │         Search Orchestration Layer            │
  │  (query understanding, geo-resolution,       │
  │   availability pre-filter, ranking)          │
  └──────────────────────┬───────────────────────┘
                         │
         ┌───────────────┼───────────────┐
         ▼               ▼               ▼
  ┌─────────────┐ ┌─────────────┐ ┌──────────────┐
  │ Geo Cluster │ │ Text Cluster│ │ Availability │
  │ (geo_point, │ │ (names,     │ │ Cache        │
  │  geo_shape) │ │  amenities) │ │ (Redis)      │
  └──────┬──────┘ └──────┬──────┘ └──────┬───────┘
         │               │               │
         ▼               ▼               ▼
  ┌──────────────────────────────────────────────────────┐
  │           Elasticsearch Cluster                       │
  │                                                      │
  │  ┌────────────────────────────────────────────────┐  │
  │  │  hotels_global: 28M docs                       │  │
  │  │  30 primary shards (region-aware routing)      │  │
  │  │  2 replicas (cross-zone)                       │  │
  │  ├────────────────────────────────────────────────┤  │
  │  │  reviews_index: 250M docs                      │  │
  │  │  50 primary shards, 1 replica                  │  │
  │  ├────────────────────────────────────────────────┤  │
  │  │  availability_index: real-time (5s refresh)    │  │
  │  │  20 primary shards, 1 replica                  │  │
  │  └────────────────────────────────────────────────┘  │
  │                                                      │
  │  80 data nodes (r5.4xlarge)                         │
  │  Routing: _routing = region_id                      │
  └──────────────────────────────────────────────────────┘
```

**Index Mapping:**
```json
{
  "mappings": {
    "_routing": { "required": true },
    "properties": {
      "hotel_id": { "type": "long" },
      "name": {
        "type": "text",
        "analyzer": "multilingual",
        "fields": {
          "keyword": { "type": "keyword" },
          "autocomplete": {
            "type": "search_as_you_type"
          }
        }
      },
      "location": { "type": "geo_point" },
      "geo_shape": { "type": "geo_shape" },
      "city": { "type": "keyword" },
      "country": { "type": "keyword" },
      "region_id": { "type": "keyword" },
      "star_rating": { "type": "byte" },
      "guest_rating": { "type": "scaled_float", "scaling_factor": 10 },
      "review_count": { "type": "integer" },
      "price_range": {
        "type": "integer_range"
      },
      "amenities": { "type": "keyword" },
      "property_type": { "type": "keyword" },
      "room_types": {
        "type": "nested",
        "properties": {
          "type": { "type": "keyword" },
          "capacity": { "type": "byte" },
          "price_per_night": { "type": "scaled_float", "scaling_factor": 100 },
          "available": { "type": "boolean" }
        }
      },
      "photos_count": { "type": "short" },
      "last_booked": { "type": "date" },
      "booking_popularity": { "type": "rank_feature" },
      "description": {
        "type": "text",
        "analyzer": "standard",
        "index_options": "freqs"
      }
    }
  },
  "settings": {
    "number_of_shards": 30,
    "number_of_replicas": 2,
    "routing.allocation.awareness.attributes": "zone",
    "index.search.idle.after": "30s"
  }
}
```

**Query DSL (Geo + Filters + Scoring):**
```json
{
  "query": {
    "bool": {
      "must": [
        {
          "multi_match": {
            "query": "hotel with pool near beach",
            "fields": ["name^3", "description", "amenities^2"],
            "type": "cross_fields"
          }
        }
      ],
      "filter": [
        {
          "geo_distance": {
            "distance": "5km",
            "location": { "lat": 41.38, "lon": 2.17 }
          }
        },
        {
          "range": { "star_rating": { "gte": 4 } }
        },
        {
          "terms": { "amenities": ["pool", "wifi", "parking"] }
        },
        {
          "nested": {
            "path": "room_types",
            "query": {
              "bool": {
                "must": [
                  { "term": { "room_types.available": true } },
                  { "range": { "room_types.capacity": { "gte": 2 } } },
                  { "range": { "room_types.price_per_night": { "lte": 200 } } }
                ]
              }
            }
          }
        }
      ],
      "should": [
        { "rank_feature": { "field": "booking_popularity", "boost": 2 } },
        {
          "range": {
            "guest_rating": { "gte": 8.5, "boost": 1.5 }
          }
        },
        {
          "distance_feature": {
            "field": "location",
            "pivot": "2km",
            "origin": { "lat": 41.38, "lon": 2.17 }
          }
        }
      ]
    }
  },
  "sort": [
    { "_score": "desc" },
    {
      "_geo_distance": {
        "location": { "lat": 41.38, "lon": 2.17 },
        "order": "asc",
        "unit": "km"
      }
    }
  ],
  "aggs": {
    "price_ranges": {
      "range": {
        "field": "room_types.price_per_night",
        "ranges": [
          { "to": 50 }, { "from": 50, "to": 100 },
          { "from": 100, "to": 200 }, { "from": 200 }
        ]
      }
    },
    "star_ratings": {
      "terms": { "field": "star_rating" }
    },
    "amenities_filter": {
      "terms": { "field": "amenities", "size": 20 }
    },
    "avg_price_by_area": {
      "geohash_grid": { "field": "location", "precision": 5 },
      "aggs": {
        "avg_price": { "avg": { "field": "room_types.price_per_night" } }
      }
    }
  },
  "size": 25
}
```

---

## Replication

### Primary and Replica Shards

```
Index: "products" (3 primary, 1 replica)

  Node 1                Node 2                Node 3
  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
  │  P0          │     │  P1          │     │  P2          │
  │  (primary)   │     │  (primary)   │     │  (primary)   │
  │              │     │              │     │              │
  │  R2          │     │  R0          │     │  R1          │
  │  (replica)   │     │  (replica)   │     │  (replica)   │
  └──────────────┘     └──────────────┘     └──────────────┘

Write Flow:
  Client ──► Coordinating Node ──► Primary Shard (P0)
                                        │
                                        ├──► Replica (R0 on Node 2)
                                        │         │
                                        │         ▼ ACK
                                        ▼
                                   ACK to client
                                   (wait_for_active_shards)

Read Flow:
  Client ──► Coordinating Node ──► ANY copy (P0 or R0)
             (round-robin / adaptive replica selection)
```

### Cross-Cluster Replication (CCR)

```
  Leader Cluster (US-East)          Follower Cluster (EU-West)
  ┌──────────────────────┐         ┌──────────────────────┐
  │  products (leader)   │ ──────► │  products (follower) │
  │  - writes accepted   │  async  │  - read-only         │
  │  - 5 shards          │  replay │  - 5 shards          │
  └──────────────────────┘         └──────────────────────┘

  Mechanism:
  1. Follower polls leader's shard changes (translog)
  2. Changes replayed in order (seq_no based)
  3. Configurable: poll_interval, max_read_request_size
  
  Use Cases:
  - Geo-proximity reads (reduce latency)
  - Disaster recovery (RPO near zero)
  - Centralized reporting (fan-in from multiple clusters)
```

### Shard Allocation Awareness

```yaml
# elasticsearch.yml
cluster.routing.allocation.awareness.attributes: zone
node.attr.zone: us-east-1a  # set per node

# Forced awareness (prevents all replicas in one zone)
cluster.routing.allocation.awareness.force.zone.values: us-east-1a,us-east-1b,us-east-1c
```

```
  Zone A              Zone B              Zone C
  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐
  │ Node 1      │   │ Node 3      │   │ Node 5      │
  │  P0, P2     │   │  R0, P1     │   │  R2, R1     │
  │ Node 2      │   │ Node 4      │   │ Node 6      │
  │  P3, R4     │   │  R3, P4     │   │  P5, R5     │
  └─────────────┘   └─────────────┘   └─────────────┘
  
  Rule: Primary and its replica NEVER in the same zone
```

### Index Lifecycle Management (ILM)

```
Timeline:
  ───────────────────────────────────────────────────────────────►
  
  │◄── HOT ──►│◄──── WARM ────►│◄──── COLD ────►│◄─ FROZEN ─►│ DELETE
  │   0-2d    │    2d-30d      │   30d-90d      │  90d-365d  │  365d+
  │           │                │                │            │
  │ NVMe SSD  │ HDD            │ Searchable     │ S3 only    │
  │ 50 shards │ shrink→10      │ snapshot       │ on-demand  │
  │ refresh 1s│ force-merge    │ partial cache  │ mount      │
  │ replicas:1│ read-only      │                │            │
  
  Storage Cost Reduction:
  HOT:    $$$$$  (fast SSD, full replicas)
  WARM:   $$$    (HDD, merged, fewer shards)
  COLD:   $$     (S3 + local cache)
  FROZEN: $      (S3 only, no local storage)
```

### Snapshots

```json
// Register repository
PUT _snapshot/s3_backup
{
  "type": "s3",
  "settings": {
    "bucket": "es-snapshots-prod",
    "region": "us-east-1",
    "base_path": "cluster-prod",
    "compress": true,
    "server_side_encryption": true,
    "max_snapshot_bytes_per_sec": "500mb",
    "max_restore_bytes_per_sec": "500mb"
  }
}

// SLM Policy (daily snapshots, retain 30)
PUT _slm/policy/daily-snap
{
  "schedule": "0 0 1 * * ?",
  "name": "<daily-snap-{now/d}>",
  "repository": "s3_backup",
  "config": {
    "indices": ["*"],
    "ignore_unavailable": true,
    "include_global_state": false
  },
  "retention": {
    "expire_after": "30d",
    "min_count": 5,
    "max_count": 30
  }
}
```

---

## Scalability

### Cluster Topology

```
Production Cluster Layout:

  ┌─────────────────────────────────────────────────────────────────┐
  │                        CLUSTER                                   │
  │                                                                 │
  │  MASTER-ELIGIBLE (3 nodes, dedicated, small instances)          │
  │  ┌────────┐  ┌────────┐  ┌────────┐                           │
  │  │Master 1│  │Master 2│  │Master 3│  - Cluster state mgmt     │
  │  │(active)│  │(standby)│ │(standby)│  - Shard allocation       │
  │  └────────┘  └────────┘  └────────┘  - Index creation          │
  │                                        - c5.2xlarge             │
  │  COORDINATING (10 nodes, no data)                               │
  │  ┌──────┐┌──────┐┌──────┐...          - Query routing          │
  │  │Coord1││Coord2││Coord3│             - Scatter/gather         │
  │  └──────┘└──────┘└──────┘             - Aggregation reduce     │
  │                                        - c5.4xlarge             │
  │  INGEST (5 nodes)                                               │
  │  ┌──────┐┌──────┐┌──────┐...          - Pipeline processing    │
  │  │Ingest││Ingest││Ingest│             - Enrichment             │
  │  └──────┘└──────┘└──────┘             - c5.4xlarge             │
  │                                                                 │
  │  DATA - HOT (50 nodes)                                          │
  │  ┌──────┐┌──────┐┌──────┐...          - NVMe SSD               │
  │  │ Hot  ││ Hot  ││ Hot  │             - i3.4xlarge             │
  │  └──────┘└──────┘└──────┘             - Active indexing         │
  │                                                                 │
  │  DATA - WARM (30 nodes)                                         │
  │  ┌──────┐┌──────┐┌──────┐...          - HDD (d2.4xlarge)       │
  │  │ Warm ││ Warm ││ Warm │             - Read-heavy             │
  │  └──────┘└──────┘└──────┘             - Older data             │
  │                                                                 │
  │  DATA - COLD/FROZEN (S3-backed)                                 │
  │  ┌──────┐┌──────┐                     - Minimal local disk     │
  │  │ Cold ││Frozen│                     - Searchable snapshots   │
  │  └──────┘└──────┘                                              │
  └─────────────────────────────────────────────────────────────────┘
```

### Shard Sizing Guidelines

```
Rule of Thumb:
  - Target: 10-50 GB per shard
  - Max docs per shard: ~2 billion (Lucene limit)
  - Max shards per node: ~1000 (practical: 20-25 per GB heap)
  - Shards per index = ceil(expected_size / 30GB)

Example Calculations:
  ┌──────────────────────────────────────────────────────┐
  │ Data Volume  │ Shard Size │ Shards │ Nodes Needed    │
  ├──────────────┼────────────┼────────┼─────────────────┤
  │ 100 GB       │ 25 GB      │ 4+1r=8 │ 3 data nodes   │
  │ 1 TB         │ 30 GB      │ 33+33r │ 10 data nodes  │
  │ 10 TB        │ 40 GB      │ 250+250│ 50 data nodes  │
  │ 100 TB       │ 50 GB      │ 2K+2K  │ 200 data nodes │
  └──────────────┴────────────┴────────┴─────────────────┘

Over-sharding Problems:
  - Each shard = 1 Lucene index = file handles, memory, threads
  - Cluster state bloat (all shards tracked by master)
  - Search latency: scatter to N shards → fan-out overhead
```

### Index Templates & Data Streams

```json
// Component template for shared settings
PUT _component_template/logs-settings
{
  "template": {
    "settings": {
      "number_of_shards": 5,
      "number_of_replicas": 1,
      "refresh_interval": "10s",
      "index.lifecycle.name": "logs-policy",
      "index.lifecycle.rollover_alias": "logs"
    }
  }
}

// Data stream (time-series, append-only)
PUT _index_template/logs-ds
{
  "index_patterns": ["logs-*"],
  "data_stream": {},
  "composed_of": ["logs-settings", "logs-mappings"],
  "priority": 500
}

// Usage
POST logs-nginx/_doc
{
  "@timestamp": "2024-01-15T10:30:00Z",
  "message": "GET /api/health 200"
}
```

### Rollover Strategy

```json
// Time + size based rollover
PUT _ilm/policy/rollover-policy
{
  "policy": {
    "phases": {
      "hot": {
        "actions": {
          "rollover": {
            "max_age": "1d",
            "max_primary_shard_size": "50gb",
            "max_docs": 500000000
          }
        }
      }
    }
  }
}

// Result: logs-000001, logs-000002, logs-000003...
// Alias "logs" always points to latest write index
```

### Searchable Snapshots

```
Tiers and Storage:

  Fully Mounted (Cold):
  ┌─────────────────────────────────────┐
  │ S3 Snapshot ──► Local Cache (full)  │
  │ First search: restore from S3       │
  │ Subsequent: local cache hit         │
  │ Latency: ~2-10x hot tier           │
  └─────────────────────────────────────┘

  Partially Mounted (Frozen):
  ┌─────────────────────────────────────┐
  │ S3 Snapshot ──► Sparse local cache  │
  │ Each search: fetch needed blocks    │
  │ Minimal disk (cache only)           │
  │ Latency: ~10-100x hot tier         │
  └─────────────────────────────────────┘
```

### Segment Merging

```
Before Merge:
  Seg0 (5MB) + Seg1 (8MB) + Seg2 (3MB) + Seg3 (12MB)
  = 4 segments, scattered reads, deleted docs waste space

Merge Policy (tiered):
  ┌────────────────────────────────────────────┐
  │ max_merge_at_once: 10                      │
  │ max_merged_segment: 5gb                    │
  │ segments_per_tier: 10                      │
  │ floor_segment: 2mb                         │
  └────────────────────────────────────────────┘

After Merge:
  MergedSeg (28MB) - one segment, deleted docs purged

Force Merge (for read-only indices):
  POST /warm-index/_forcemerge?max_num_segments=1
  - Eliminates all deleted docs
  - Single segment = fastest reads
  - NEVER on actively-written indices
```

---

## Production Setup

### JVM Heap Configuration

```bash
# /etc/elasticsearch/jvm.options

# Rule: Set to EXACTLY half of available RAM, max 32GB
# Why 32GB max? JVM compressed ordinary object pointers (oops)
# Above 32GB: pointers expand from 4 bytes to 8 bytes = LESS effective heap

-Xms30g          # 30GB (leaves 34GB for OS page cache on 64GB node)
-Xmx30g          # Must equal Xms (avoid resize pauses)

# GC: Use G1GC for heaps > 6GB (default in ES 7+)
-XX:+UseG1GC
-XX:G1HeapRegionSize=16m
-XX:InitiatingHeapOccupancyPercent=40
-XX:MaxGCPauseMillis=200

# Memory breakdown on 64GB node:
# ┌──────────────────────────────────────────┐
# │  JVM Heap: 30GB                          │
# │  ├── Indexing buffers: ~10%              │
# │  ├── Field data cache: bounded           │
# │  ├── Query cache: 10% of heap           │
# │  ├── Request cache: 1% of heap          │
# │  └── Overhead (GC, objects): ~20%        │
# │                                          │
# │  OS Page Cache: 34GB                     │
# │  ├── Lucene segment files (mmap)        │
# │  ├── Doc values                          │
# │  └── Stored fields                      │
# └──────────────────────────────────────────┘
```

### Thread Pools & Circuit Breakers

```json
// Thread Pools
PUT _cluster/settings
{
  "persistent": {
    "thread_pool.write.queue_size": 1000,
    "thread_pool.search.queue_size": 1000
  }
}

// Thread pool sizing (auto by default):
// search:  ((# of CPUs * 3) / 2) + 1, queue: 1000
// write:   # of CPUs, queue: 10000
// get:     # of CPUs, queue: 1000

// Circuit Breakers (prevent OOM)
PUT _cluster/settings
{
  "persistent": {
    "indices.breaker.total.limit": "70%",
    "indices.breaker.fielddata.limit": "40%",
    "indices.breaker.request.limit": "60%",
    "network.breaker.inflight_requests.limit": "100%"
  }
}

// When tripped: returns 429 (TOO_MANY_REQUESTS)
// Client should: back off and retry
```

### Refresh Interval & Translog

```json
// Index settings for write-heavy workloads
PUT /logs-*/_settings
{
  "index": {
    "refresh_interval": "30s",
    "translog": {
      "durability": "async",
      "sync_interval": "30s",
      "flush_threshold_size": "1gb"
    },
    "number_of_replicas": 0,
    "merge.scheduler.max_thread_count": 1
  }
}

// Performance tradeoffs:
// ┌────────────────────────────────────────────────────────┐
// │ Setting              │ Faster Write │ Faster Search    │
// ├──────────────────────┼──────────────┼──────────────────┤
// │ refresh_interval: -1 │ ✓✓✓          │ ✗ (not visible) │
// │ refresh_interval: 30s│ ✓✓           │ ✓ (30s delay)   │
// │ refresh_interval: 1s │ ✓            │ ✓✓✓             │
// ├──────────────────────┼──────────────┼──────────────────┤
// │ translog: async      │ ✓✓✓          │ (data loss risk) │
// │ translog: request    │ ✓            │ (durable)        │
// ├──────────────────────┼──────────────┼──────────────────┤
// │ replicas: 0 (bulk)   │ ✓✓✓          │ (no HA)         │
// │ replicas: 1          │ ✓            │ ✓✓ (redundancy) │
// └──────────────────────┴──────────────┴──────────────────┘
```

### Bulk Optimization

```json
// Optimal bulk request
POST _bulk
{"index":{"_index":"logs","_id":"1"}}
{"@timestamp":"2024-01-15T10:00:00Z","message":"log1"}
{"index":{"_index":"logs","_id":"2"}}
{"@timestamp":"2024-01-15T10:00:01Z","message":"log2"}
... (1000-5000 docs per batch)

// Bulk sizing guidelines:
// ┌────────────────────────────────────┐
// │ Target: 5-15 MB per bulk request   │
// │ Docs per batch: 1000-5000          │
// │ Concurrent bulk threads: 2-4       │
// │                                    │
// │ Measure: start at 1000 docs,       │
// │ increase until throughput plateaus  │
// │ or latency exceeds threshold       │
// └────────────────────────────────────┘
```

**Pre-indexing optimization checklist:**
```json
// Before bulk load
PUT /my-index/_settings
{
  "number_of_replicas": 0,
  "refresh_interval": "-1"
}

// ... bulk index millions of docs ...

// After bulk load
PUT /my-index/_settings
{
  "number_of_replicas": 1,
  "refresh_interval": "1s"
}

POST /my-index/_forcemerge?max_num_segments=5
POST /my-index/_refresh
```

---

## Performance Benchmarks

### Search Latency at Different Scales

```
┌─────────────────────────────────────────────────────────────────────────┐
│ Benchmark: Simple term query (keyword field)                            │
├──────────────┬──────────┬──────────┬──────────┬────────────────────────┤
│ Index Size   │ P50      │ P95      │ P99      │ Throughput (QPS)       │
├──────────────┼──────────┼──────────┼──────────┼────────────────────────┤
│ 1M docs      │ 2ms      │ 5ms      │ 10ms     │ 10,000                │
│ 10M docs     │ 3ms      │ 8ms      │ 15ms     │ 8,000                 │
│ 100M docs    │ 5ms      │ 15ms     │ 30ms     │ 5,000                 │
│ 1B docs      │ 10ms     │ 30ms     │ 60ms     │ 2,000                 │
│ 10B docs     │ 20ms     │ 80ms     │ 150ms    │ 500                   │
└──────────────┴──────────┴──────────┴──────────┴────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│ Benchmark: Full-text match query (analyzed text field)                   │
├──────────────┬──────────┬──────────┬──────────┬────────────────────────┤
│ Index Size   │ P50      │ P95      │ P99      │ Throughput (QPS)       │
├──────────────┼──────────┼──────────┼──────────┼────────────────────────┤
│ 1M docs      │ 5ms      │ 15ms    │ 25ms     │ 5,000                 │
│ 10M docs     │ 8ms      │ 25ms    │ 45ms     │ 3,000                 │
│ 100M docs    │ 15ms     │ 50ms    │ 100ms    │ 1,500                 │
│ 1B docs      │ 30ms     │ 100ms   │ 200ms    │ 800                   │
│ 10B docs     │ 80ms     │ 250ms   │ 500ms    │ 200                   │
└──────────────┴──────────┴──────────┴──────────┴────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│ Benchmark: Aggregation (terms + date_histogram + nested)                │
├──────────────┬──────────┬──────────┬──────────┬────────────────────────┤
│ Index Size   │ P50      │ P95      │ P99      │ Throughput (QPS)       │
├──────────────┼──────────┼──────────┼──────────┼────────────────────────┤
│ 1M docs      │ 10ms     │ 30ms    │ 50ms     │ 3,000                 │
│ 10M docs     │ 25ms     │ 80ms    │ 150ms    │ 1,000                 │
│ 100M docs    │ 80ms     │ 250ms   │ 500ms    │ 300                   │
│ 1B docs      │ 200ms    │ 800ms   │ 1500ms   │ 80                    │
│ 10B docs     │ 500ms    │ 2000ms  │ 5000ms   │ 20                    │
└──────────────┴──────────┴──────────┴──────────┴────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│ Benchmark: Geo-distance query + sort                                    │
├──────────────┬──────────┬──────────┬──────────┬────────────────────────┤
│ Index Size   │ P50      │ P95      │ P99      │ Throughput (QPS)       │
├──────────────┼──────────┼──────────┼──────────┼────────────────────────┤
│ 1M docs      │ 5ms      │ 12ms    │ 20ms     │ 6,000                 │
│ 10M docs     │ 8ms      │ 20ms    │ 40ms     │ 3,500                 │
│ 100M docs    │ 15ms     │ 45ms    │ 90ms     │ 1,500                 │
│ 1B docs      │ 40ms     │ 120ms   │ 250ms    │ 500                   │
└──────────────┴──────────┴──────────┴──────────┴────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│ Benchmark: Indexing throughput (bulk API)                                │
├──────────────┬─────────────────┬──────────────────────────────────────-─┤
│ Doc Size     │ Single Node     │ 10-Node Cluster                        │
├──────────────┼─────────────────┼────────────────────────────────────────┤
│ 1 KB         │ 30K docs/sec    │ 250K docs/sec                         │
│ 5 KB         │ 15K docs/sec    │ 120K docs/sec                         │
│ 10 KB        │ 8K docs/sec     │ 70K docs/sec                          │
│ 50 KB        │ 2K docs/sec     │ 15K docs/sec                          │
└──────────────┴─────────────────┴────────────────────────────────────────┘

Notes:
- Benchmarks on r5.4xlarge (16 vCPU, 128GB RAM, NVMe SSD)
- 30GB JVM heap, default settings unless noted
- QPS measured with single client, multiply ~3-5x with parallel clients
- Actual numbers vary with: mapping complexity, analyzer chain,
  query complexity, hardware, concurrent load
- Use Rally (esrally) for your own benchmarks
```

### Key Performance Tuning Levers

```
┌──────────────────────────────────────────────────────────────┐
│ Lever                    │ Impact │ Tradeoff                  │
├──────────────────────────┼────────┼───────────────────────────┤
│ More replicas            │ +read  │ More disk, slower writes  │
│ Fewer shards             │ +both  │ Less parallelism          │
│ refresh_interval: 30s    │ +write │ Stale search (30s)        │
│ doc_values: false        │ +write │ No sort/agg on field      │
│ norms: false             │ +write │ No scoring for field      │
│ index_options: freqs     │ +write │ No position queries       │
│ Routing                  │ +read  │ Uneven shard sizes        │
│ Forcemerge               │ +read  │ Expensive, one-time       │
│ Query cache (filter)     │ +read  │ Memory usage              │
│ Request cache (agg)      │ +read  │ Stale until refresh       │
└──────────────────────────┴────────┴───────────────────────────┘
```

---

## Quick Reference Commands

```bash
# Cluster health
GET _cluster/health

# Shard allocation
GET _cat/shards?v&s=store:desc

# Hot threads (debugging slow queries)
GET _nodes/hot_threads

# Pending tasks
GET _cluster/pending_tasks

# Index stats
GET /my-index/_stats

# Segment info
GET /my-index/_segments

# Node stats
GET _nodes/stats/jvm,os,process

# Slow log
PUT /my-index/_settings
{
  "index.search.slowlog.threshold.query.warn": "10s",
  "index.search.slowlog.threshold.query.info": "5s",
  "index.search.slowlog.threshold.fetch.warn": "1s"
}

# Profile query (explain execution)
GET /my-index/_search
{
  "profile": true,
  "query": { "match": { "title": "test" } }
}
```
