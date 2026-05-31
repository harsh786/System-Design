# Problem 4: E-Commerce Search & Analytics (Amazon Scale)

## Problem 4: E-Commerce Search & Analytics (Amazon Scale)

### Business Context
E-commerce platform with 500M products, 50M daily active users, needing:
- Product search (<200ms)
- Real-time analytics (what's trending now)
- Personalized ranking

### Architecture
```
┌─────────────────────────────────────────────────────────────────────────────┐
│              E-COMMERCE DATA PLATFORM ARCHITECTURE                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────┐         │
│  │  USER ACTIONS                                                   │         │
│  │  [Search] [Click] [Add to Cart] [Purchase] [Review] [Browse]    │         │
│  │  50M DAU × 20 actions/session = 1 billion events/day            │         │
│  └──────────────────────────────┬─────────────────────────────────┘         │
│                                  │                                           │
│  ┌───────────────────────────────▼──────────────────────────────────┐       │
│  │  EVENT BUS (Kafka)                                                │       │
│  │  • user-actions: 200 partitions (12K events/sec)                  │       │
│  │  • product-updates: 50 partitions (from catalog service)          │       │
│  │  • search-queries: 100 partitions (for query analytics)           │       │
│  └───────┬──────────────────┬────────────────────────┬──────────────┘       │
│          │                  │                        │                        │
│  ┌───────▼──────┐  ┌───────▼──────────┐  ┌─────────▼────────────┐          │
│  │  SEARCH      │  │  ANALYTICS       │  │  PERSONALIZATION      │          │
│  │  PIPELINE    │  │  PIPELINE        │  │  PIPELINE             │          │
│  │              │  │                   │  │                       │           │
│  │  Elasticsearch│ │  Flink → Druid   │  │  Flink → Redis        │          │
│  │  500M docs    │ │  Real-time OLAP  │  │  User profiles        │          │
│  │  50 nodes     │ │  trending, CTR   │  │  Recent interactions  │          │
│  │              │  │                   │  │                       │           │
│  │  WHY ES:     │  │  WHY Druid:      │  │  WHY Redis:           │          │
│  │  • Full-text │  │  • Sub-second    │  │  • <1ms lookup        │          │
│  │  • Facets    │  │    aggregation   │  │  • Session state      │          │
│  │  • Geo-search│  │  • Real-time     │  │  • A/B bucketing      │          │
│  │  • Fuzzy     │  │    ingestion     │  │  • Feature store      │          │
│  │  • 200ms SLA │  │  • Slice & dice  │  │                       │           │
│  └──────────────┘  └──────────────────┘  └───────────────────────┘          │
│                                                                              │
│  SEARCH RANKING (L1 → L2 → L3):                                             │
│  ┌────────────────────────────────────────────────────────────────┐         │
│  │  L1: Candidate Retrieval (ES, 10K candidates, <50ms)            │         │
│  │      → BM25 + semantic search (vector)                          │         │
│  │                                                                 │         │
│  │  L2: Feature Scoring (lightweight model, 1K → 200, <30ms)      │         │
│  │      → GBDT on: CTR, conversion, relevance, freshness          │         │
│  │                                                                 │         │
│  │  L3: Personalized Re-ranking (deep model, 200 → 50, <50ms)     │         │
│  │      → User history + item features + context                   │         │
│  │                                                                 │         │
│  │  Total: <200ms for personalized search results                  │         │
│  └────────────────────────────────────────────────────────────────┘         │
│                                                                              │
│  BATCH (Daily):                                                              │
│  ┌────────────────────────────────────────────────────────────────┐         │
│  │  • Product catalog enrichment (descriptions, categories)        │         │
│  │  • Popularity scoring (sales rank, trending)                    │         │
│  │  • Review aggregation (sentiment, rating)                       │         │
│  │  • Search relevance model retraining                            │         │
│  │  • A/B test analysis                                            │         │
│  │                                                                 │         │
│  │  Tool: Spark + dbt + Airflow                                    │         │
│  │  Storage: Delta Lake (10 PB catalog + events)                   │         │
│  └────────────────────────────────────────────────────────────────┘         │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

