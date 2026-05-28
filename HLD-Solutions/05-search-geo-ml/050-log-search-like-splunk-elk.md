# Log Search Platform Design (Splunk / ELK Stack)

## 1. Requirements

### 1.1 Functional Requirements
| ID | Requirement | Description |
|----|-------------|-------------|
| FR1 | Log Ingestion at Scale | Accept logs from thousands of sources |
| FR2 | Full-Text Search | Search across all log fields with free text |
| FR3 | Structured Query Language | SPL/KQL-like query language with pipes |
| FR4 | Real-Time Tail | Live stream of logs matching a filter |
| FR5 | Dashboards | Visual panels with charts, tables, alerts |
| FR6 | Alerting | Trigger notifications on pattern matches |
| FR7 | Retention Policies | Configurable per-index retention |
| FR8 | Multi-Tenant Isolation | Logical and physical data separation |
| FR9 | Field Extraction | Auto-extract and index structured fields |

### 1.2 Non-Functional Requirements
| Requirement | Target |
|-------------|--------|
| Availability | 99.99% for search, 99.999% for ingestion |
| Search Latency | < 5s for 30-day window queries |
| Ingestion Rate | 1 PB/day aggregate, 100K events/sec per tenant |
| Query Throughput | 10K concurrent searches |
| Data Retention | Hot: 7 days, Warm: 30 days, Cold: 1 year, Frozen: 7 years |
| Durability | Zero data loss (at-least-once delivery) |

---

## 2. Capacity Estimation

### 2.1 Storage
```
Daily ingestion: 1 PB raw
Average event size: 500 bytes
Events per day: 1 PB / 500 B = 2 trillion events/day
Events per second: ~23 million EPS (aggregate)

Storage with compression (10:1 ratio for logs):
- Raw: 1 PB/day
- Compressed hot: 100 TB/day
- Hot tier (7 days): 700 TB SSD
- Warm tier (30 days): 3 PB HDD with compressed index
- Cold tier (1 year): 36.5 PB object storage (S3)
- Frozen (7 years): 255 PB archive (S3 Glacier)

Index overhead: ~15% of compressed data
- Hot index: 105 TB
- Warm index: 450 TB (sparse)
```

### 2.2 Compute
```
Indexer fleet:
- Throughput per indexer: 50 GB/hour = ~14 MB/s
- Indexers needed for 1 PB/day: 1 PB / (50 GB × 24h) = ~833 indexers
- With headroom (2x): 1700 indexer nodes

Search heads:
- 10K concurrent searches
- Each search uses 2 vCPUs for 5s avg
- vCPUs needed: 10K × 2 / (avg_concurrent_factor=3) = ~7000 vCPUs
- Search head nodes (32 vCPU each): ~220 nodes

Kafka brokers:
- 1 PB/day ÷ 86400 = 11.5 GB/s sustained write
- With replication (3x): 34.5 GB/s
- Brokers (1 GB/s each): 35+ brokers
```

### 2.3 Network
```
Ingestion bandwidth: 11.5 GB/s inbound
Internal replication: 34.5 GB/s (Kafka)
Indexer to storage: 11.5 GB/s
Search scatter-gather: highly variable, up to 50 GB/s burst reads
```

---

## 3. Data Modeling

### 3.1 Event Schema (Internal Representation)
```sql
-- Logical event structure (stored in columnar segments)
CREATE TABLE events (
    event_id        BIGINT,              -- monotonic per-shard ID
    timestamp       TIMESTAMPTZ NOT NULL, -- event time (primary sort key)
    ingest_time     TIMESTAMPTZ NOT NULL, -- when we received it
    tenant_id       INT NOT NULL,
    index_name      VARCHAR(128),         -- logical index (e.g., "web_access")
    source          VARCHAR(512),         -- originating host/app
    sourcetype      VARCHAR(128),         -- log format (apache, json, syslog)
    raw_event       TEXT,                 -- original log line
    -- Extracted fields stored as columnar attributes
    fields          JSONB                 -- {"status": 200, "method": "GET", ...}
);

-- Partitioned by: tenant_id → index_name → time_bucket (1-hour segments)
```

### 3.2 Index Metadata (PostgreSQL - Control Plane)
```sql
CREATE TABLE tenants (
    tenant_id       SERIAL PRIMARY KEY,
    name            VARCHAR(255) NOT NULL,
    tier            VARCHAR(20) DEFAULT 'standard', -- standard, premium, enterprise
    daily_quota_gb  BIGINT DEFAULT 100,
    retention_days  INT DEFAULT 30,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE indexes (
    index_id        SERIAL PRIMARY KEY,
    tenant_id       INT REFERENCES tenants(tenant_id),
    index_name      VARCHAR(128) NOT NULL,
    sourcetype      VARCHAR(128),
    retention_days  INT,              -- override tenant default
    hot_days        INT DEFAULT 7,
    warm_days       INT DEFAULT 30,
    frozen_days     INT DEFAULT 365,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, index_name)
);

CREATE TABLE segments (
    segment_id      BIGINT PRIMARY KEY,
    index_id        INT REFERENCES indexes(index_id),
    tenant_id       INT NOT NULL,
    time_start      TIMESTAMPTZ NOT NULL,
    time_end        TIMESTAMPTZ NOT NULL,
    event_count     BIGINT,
    raw_size_bytes  BIGINT,
    compressed_size BIGINT,
    tier            VARCHAR(10),       -- hot, warm, cold, frozen
    storage_path    TEXT,              -- s3://bucket/path or local path
    bloom_filter    BYTEA,            -- serialized bloom filter for field values
    min_max_fields  JSONB,            -- {"status": [200, 504], "latency": [1, 9999]}
    status          VARCHAR(20) DEFAULT 'active',
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_segments_tenant_time ON segments(tenant_id, time_start, time_end);
CREATE INDEX idx_segments_tier ON segments(tier);

CREATE TABLE saved_searches (
    search_id       SERIAL PRIMARY KEY,
    tenant_id       INT REFERENCES tenants(tenant_id),
    name            VARCHAR(255),
    query           TEXT NOT NULL,
    schedule_cron   VARCHAR(50),       -- for scheduled searches / alerts
    alert_condition TEXT,              -- "count > 100"
    alert_action    JSONB,            -- {"type": "webhook", "url": "..."}
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE dashboards (
    dashboard_id    SERIAL PRIMARY KEY,
    tenant_id       INT REFERENCES tenants(tenant_id),
    name            VARCHAR(255),
    panels          JSONB,            -- array of panel configs
    refresh_interval INT DEFAULT 60,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
```

### 3.3 Segment File Format (Columnar + Inverted Index)
```
Segment file layout (inspired by Lucene):
┌─────────────────────────────────────┐
│         Segment Header              │
│  - magic bytes, version             │
│  - event_count, time_range          │
│  - field_schema                     │
├─────────────────────────────────────┤
│       Column Store (per field)      │
│  - timestamp column (delta + VByte) │
│  - source column (dictionary enc)   │
│  - status column (RLE + bitpack)    │
│  - raw_event column (LZ4 blocks)   │
├─────────────────────────────────────┤
│       Inverted Index                │
│  - term dictionary (FST)           │
│  - posting lists (roaring bitmaps) │
│  - position index (for phrases)    │
├─────────────────────────────────────┤
│       Bloom Filters                 │
│  - per-field bloom (token presence)│
├─────────────────────────────────────┤
│       Min/Max Index                 │
│  - per-column min/max values       │
│  - used for segment pruning        │
├─────────────────────────────────────┤
│       Footer + Checksums            │
└─────────────────────────────────────┘

Segment size target: 500 MB - 1 GB compressed
Time span: 1 hour of data per segment
```

---

## 4. High-Level Design

### 4.1 Architecture Diagram
```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            DATA SOURCES                                       │
│  [App Servers] [Containers] [Cloud Services] [Network Devices] [Databases]  │
│       │             │             │                │              │          │
│       ▼             ▼             ▼                ▼              ▼          │
│  ┌──────────────────────────────────────────────────────────────────┐       │
│  │                    COLLECTION AGENTS                               │       │
│  │  [Filebeat] [Fluentd] [OpenTelemetry] [Syslog] [HTTP API]       │       │
│  │  - Tail log files    - Parse formats   - Buffer locally          │       │
│  │  - Add metadata      - Compress        - Retry on failure        │       │
│  └──────────────────────────────────┬───────────────────────────────┘       │
└─────────────────────────────────────┼───────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         INGESTION LAYER                                       │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────┐       │
│  │                      KAFKA CLUSTER                                │       │
│  │  Topics: logs.raw.{tenant_id} (partitioned by source)            │       │
│  │  - 35+ brokers, RF=3                                             │       │
│  │  - 11.5 GB/s sustained write                                     │       │
│  │  - 7 day retention (replay buffer)                                │       │
│  └──────────────────────────────────┬───────────────────────────────┘       │
│                                     │                                        │
│         ┌───────────────────────────┼───────────────────────┐               │
│         ▼                           ▼                       ▼               │
│  ┌─────────────┐          ┌─────────────────┐      ┌──────────────┐        │
│  │  FLINK      │          │  INDEXER FLEET   │      │  ALERT       │        │
│  │  (Real-time)│          │  (1700 nodes)    │      │  ENGINE      │        │
│  │             │          │                  │      │  (Flink)     │        │
│  │  - Live tail│          │  - Parse events  │      │              │        │
│  │  - RT alerts│          │  - Extract fields│      │  - Pattern   │        │
│  │  - Streaming│          │  - Tokenize      │      │    matching  │        │
│  │    aggreg.  │          │  - Build index   │      │  - Threshold │        │
│  └─────────────┘          │  - Write segments│      │  - Anomaly   │        │
│                           └────────┬─────────┘      └──────────────┘        │
└────────────────────────────────────┼────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          STORAGE TIERS                                        │
│                                                                              │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐  ┌────────────┐  │
│  │   HOT TIER    │  │   WARM TIER   │  │   COLD TIER   │  │  FROZEN    │  │
│  │   (NVMe SSD)  │  │   (HDD)       │  │   (S3)        │  │  (Glacier) │  │
│  │               │  │               │  │               │  │            │  │
│  │  - 7 days     │  │  - 30 days    │  │  - 1 year     │  │  - 7 years │  │
│  │  - Full index │  │  - Compressed │  │  - Sparse idx │  │  - Archive │  │
│  │  - 700 TB     │  │    index      │  │  - On-demand  │  │  - Restore │  │
│  │  - <1s search │  │  - 3 PB       │  │    rehydrate  │  │    in hours│  │
│  │               │  │  - <5s search │  │  - 36.5 PB    │  │  - 255 PB  │  │
│  └───────────────┘  └───────────────┘  └───────────────┘  └────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          QUERY LAYER                                          │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────┐       │
│  │                   SEARCH HEAD CLUSTER                              │       │
│  │  (220 nodes, coordinating distributed queries)                    │       │
│  │                                                                   │       │
│  │  ┌─────────────┐  ┌──────────────┐  ┌─────────────────────┐     │       │
│  │  │ Query Parser │  │ Query Planner│  │ Result Aggregator   │     │       │
│  │  │ (SPL/KQL)   │  │ (Optimizer)  │  │ (Streaming merge)   │     │       │
│  │  └─────────────┘  └──────────────┘  └─────────────────────┘     │       │
│  └──────────────────────────────────────────────────────────────────┘       │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────┐       │
│  │                      UI / API LAYER                                │       │
│  │  [Search UI]  [Dashboard Engine]  [REST API]  [WebSocket (tail)] │       │
│  └──────────────────────────────────────────────────────────────────┘       │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 5. Low-Level Design - APIs

### 5.1 Log Ingestion API
```
POST /v1/ingest/{index_name}
Headers:
  Authorization: Bearer <token>
  X-Tenant-ID: tenant_123
  Content-Type: application/x-ndjson
  Content-Encoding: gzip

Request (NDJSON - newline-delimited JSON):
{"timestamp": "2024-01-15T10:30:00Z", "source": "web-server-01", "event": "GET /api/users 200 45ms"}
{"timestamp": "2024-01-15T10:30:01Z", "source": "web-server-01", "event": "POST /api/orders 500 2340ms"}
{"timestamp": "2024-01-15T10:30:01Z", "source": "web-server-02", "event": "GET /health 200 2ms"}

Response (200 OK):
{
  "acknowledged": true,
  "events_accepted": 3,
  "events_rejected": 0,
  "ingest_id": "batch_abc123"
}

Response (429 Too Many Requests):
{
  "error": "rate_limit_exceeded",
  "tenant_id": "tenant_123",
  "current_rate_eps": 120000,
  "limit_eps": 100000,
  "retry_after_ms": 5000
}
```

### 5.2 Search API
```
POST /v1/search
Headers:
  Authorization: Bearer <token>
  X-Tenant-ID: tenant_123

Request:
{
  "query": "index=web_access status>=500 | stats count by source | sort -count | head 10",
  "time_range": {
    "earliest": "2024-01-01T00:00:00Z",
    "latest": "2024-01-15T23:59:59Z"
  },
  "max_results": 10000,
  "timeout_seconds": 30,
  "search_mode": "smart"   // "fast" (sampled), "smart" (adaptive), "verbose" (all)
}

Response (200 OK - streaming NDJSON):
{"type": "metadata", "search_id": "srch_xyz", "scanned_events": 0, "status": "running"}
{"type": "progress", "scanned_events": 50000000, "segments_searched": 120, "elapsed_ms": 1200}
{"type": "result", "data": {"source": "web-server-03", "count": 4521}}
{"type": "result", "data": {"source": "web-server-01", "count": 3892}}
{"type": "result", "data": {"source": "api-gateway-02", "count": 2104}}
...
{"type": "complete", "scanned_events": 892341567, "matched_events": 45023, "elapsed_ms": 3400}
```

### 5.3 Real-Time Tail API (WebSocket)
```
WS /v1/tail
Message (subscribe):
{
  "action": "subscribe",
  "filter": {
    "index": "web_access",
    "query": "status=500 AND source=api-*"
  },
  "fields": ["timestamp", "source", "raw_event"]
}

Message (event stream):
{
  "type": "event",
  "timestamp": "2024-01-15T10:30:45.123Z",
  "source": "api-gateway-01",
  "raw_event": "POST /api/payments 500 Internal Server Error 12453ms",
  "fields": {"method": "POST", "path": "/api/payments", "status": 500, "latency_ms": 12453}
}
```

### 5.4 Alert Configuration API
```
POST /v1/alerts
Request:
{
  "name": "High Error Rate",
  "query": "index=web_access status>=500 | stats count as errors | where errors > 100",
  "schedule": "*/5 * * * *",
  "window": "5m",
  "severity": "critical",
  "actions": [
    {"type": "webhook", "url": "https://pagerduty.com/webhook/xxx"},
    {"type": "email", "to": ["oncall@company.com"]},
    {"type": "slack", "channel": "#alerts-prod"}
  ],
  "throttle_minutes": 15
}

Response:
{
  "alert_id": "alert_001",
  "status": "active",
  "next_run": "2024-01-15T10:35:00Z"
}
```

---

## 6. Deep Dive: Indexing Pipeline

### 6.1 Pipeline Stages
```
┌─────────┐    ┌─────────┐    ┌──────────┐    ┌──────────┐    ┌─────────┐
│  Parse  │───▶│ Extract │───▶│ Tokenize │───▶│  Build   │───▶│  Write  │
│  Event  │    │ Fields  │    │  Text    │    │  Index   │    │ Segment │
└─────────┘    └─────────┘    └──────────┘    └──────────┘    └─────────┘
```

### 6.2 Field Extraction Engine
```python
class FieldExtractor:
    """
    Automatically extracts structured fields from raw log events.
    Supports: JSON, key=value, CSV, regex patterns, grok.
    """

    def __init__(self):
        self.extractors = {
            'json': self._extract_json,
            'kv': self._extract_key_value,
            'apache': self._extract_apache_combined,
            'syslog': self._extract_syslog,
        }
        # Learned patterns from user feedback
        self.custom_patterns = {}

    def extract(self, raw_event: str, sourcetype: str) -> dict:
        """Extract structured fields from raw event."""
        # Try sourcetype-specific extractor first
        if sourcetype in self.extractors:
            return self.extractors[sourcetype](raw_event)

        # Auto-detect format
        if raw_event.strip().startswith('{'):
            return self._extract_json(raw_event)

        # Try key=value pattern
        kv_fields = self._extract_key_value(raw_event)
        if len(kv_fields) > 2:
            return kv_fields

        # Fall back to regex-based extraction
        return self._extract_regex_patterns(raw_event)

    def _extract_json(self, event: str) -> dict:
        """Flatten nested JSON into dot-notation fields."""
        try:
            parsed = json.loads(event)
            return self._flatten_dict(parsed)
        except json.JSONDecodeError:
            return {}

    def _flatten_dict(self, d: dict, prefix='') -> dict:
        fields = {}
        for key, value in d.items():
            full_key = f"{prefix}.{key}" if prefix else key
            if isinstance(value, dict):
                fields.update(self._flatten_dict(value, full_key))
            elif isinstance(value, list):
                fields[full_key] = json.dumps(value)
            else:
                fields[full_key] = value
        return fields

    def _extract_key_value(self, event: str) -> dict:
        """Extract key=value pairs, handling quotes."""
        pattern = r'(\w+)=(?:"([^"]*)"|([\S]+))'
        matches = re.findall(pattern, event)
        return {k: v1 or v2 for k, v1, v2 in matches}

    def _extract_apache_combined(self, event: str) -> dict:
        """Parse Apache Combined Log Format."""
        pattern = (
            r'(?P<client_ip>[\d.]+) - (?P<user>\S+) '
            r'\[(?P<timestamp>[^\]]+)\] '
            r'"(?P<method>\w+) (?P<path>\S+) (?P<protocol>\S+)" '
            r'(?P<status>\d+) (?P<bytes>\d+) '
            r'"(?P<referrer>[^"]*)" "(?P<user_agent>[^"]*)"'
        )
        match = re.match(pattern, event)
        if match:
            fields = match.groupdict()
            fields['status'] = int(fields['status'])
            fields['bytes'] = int(fields['bytes'])
            return fields
        return {}
```

### 6.3 Inverted Index Builder
```python
class InvertedIndexBuilder:
    """
    Builds segment-level inverted index (Lucene-inspired).
    Components: term dictionary (FST), posting lists, positions.
    """

    def __init__(self, segment_id: str):
        self.segment_id = segment_id
        self.term_dict = {}        # term -> (doc_count, posting_list_offset)
        self.posting_lists = {}    # term -> RoaringBitmap of doc_ids
        self.positions = {}        # term -> {doc_id: [positions]}
        self.doc_count = 0
        self.field_stats = defaultdict(lambda: {'count': 0, 'min': None, 'max': None})

    def add_document(self, doc_id: int, fields: dict):
        """Index all fields of a document."""
        self.doc_count += 1

        for field_name, value in fields.items():
            # Update field statistics
            self._update_field_stats(field_name, value)

            # Tokenize text fields
            if isinstance(value, str):
                tokens = self.tokenize(value)
                for position, token in enumerate(tokens):
                    term_key = f"{field_name}:{token}"
                    if term_key not in self.posting_lists:
                        self.posting_lists[term_key] = RoaringBitmap()
                        self.positions[term_key] = {}
                    self.posting_lists[term_key].add(doc_id)
                    self.positions[term_key].setdefault(doc_id, []).append(position)

            # Numeric fields: store for range queries
            elif isinstance(value, (int, float)):
                self._add_numeric_field(field_name, doc_id, value)

    def tokenize(self, text: str) -> List[str]:
        """Tokenize text for indexing."""
        # Lowercase
        text = text.lower()
        # Split on non-alphanumeric (preserving IPs, paths, etc.)
        tokens = re.findall(r'[a-z0-9_.:/\-]+', text)
        # Also index n-grams for partial matching
        return tokens

    def build_segment(self) -> bytes:
        """Serialize index into segment file format."""
        segment_data = io.BytesIO()

        # 1. Write header
        header = SegmentHeader(
            version=2,
            doc_count=self.doc_count,
            term_count=len(self.posting_lists),
            field_count=len(self.field_stats)
        )
        segment_data.write(header.serialize())

        # 2. Build FST (Finite State Transducer) for term dictionary
        fst_data = self._build_fst()
        segment_data.write(fst_data)

        # 3. Write posting lists (Roaring Bitmap serialized)
        postings_offset = segment_data.tell()
        for term, bitmap in sorted(self.posting_lists.items()):
            compressed = bitmap.serialize()
            segment_data.write(compressed)

        # 4. Write bloom filters per field
        bloom_data = self._build_bloom_filters()
        segment_data.write(bloom_data)

        # 5. Write min/max index
        segment_data.write(json.dumps(self.field_stats).encode())

        return segment_data.getvalue()

    def _build_bloom_filters(self) -> bytes:
        """Build bloom filter for quick segment-level field value existence check."""
        blooms = {}
        for term_key in self.posting_lists:
            field, token = term_key.split(':', 1)
            if field not in blooms:
                blooms[field] = BloomFilter(
                    capacity=100000,
                    error_rate=0.01
                )
            blooms[field].add(token)
        return pickle.dumps(blooms)

    def _update_field_stats(self, field_name: str, value):
        """Track min/max for segment pruning."""
        stats = self.field_stats[field_name]
        stats['count'] += 1
        if isinstance(value, (int, float)):
            if stats['min'] is None or value < stats['min']:
                stats['min'] = value
            if stats['max'] is None or value > stats['max']:
                stats['max'] = value
```

### 6.4 Segment Compaction
```python
class SegmentCompactor:
    """
    Merge small segments into larger ones (like Lucene merge policy).
    Reduces segment count for faster queries.
    """

    def __init__(self, max_segment_size_gb=1, merge_factor=10):
        self.max_segment_size = max_segment_size_gb * 1024**3
        self.merge_factor = merge_factor  # merge when N segments at same level

    def find_merge_candidates(self, segments: List[Segment]) -> List[List[Segment]]:
        """Tiered merge policy: group segments by size tier."""
        tiers = defaultdict(list)
        for seg in segments:
            tier = int(math.log2(max(seg.size_bytes, 1)))
            tiers[tier].append(seg)

        merge_groups = []
        for tier, tier_segments in tiers.items():
            if len(tier_segments) >= self.merge_factor:
                # Take merge_factor segments from this tier
                merge_groups.append(tier_segments[:self.merge_factor])

        return merge_groups

    def merge_segments(self, segments: List[Segment]) -> Segment:
        """Merge multiple segments into one, rebuilding index."""
        builder = InvertedIndexBuilder(segment_id=generate_segment_id())

        doc_id_offset = 0
        for segment in segments:
            reader = SegmentReader(segment)
            for doc in reader.iterate_docs():
                builder.add_document(doc_id_offset, doc.fields)
                doc_id_offset += 1

        new_segment_data = builder.build_segment()
        return self._write_segment(new_segment_data)
```

---

## 7. Deep Dive: Storage Tiering

### 7.1 Tier Lifecycle
```
┌──────────────────────────────────────────────────────────────┐
│                    SEGMENT LIFECYCLE                           │
│                                                               │
│   Ingest → HOT (NVMe SSD)                                   │
│            │  Full inverted index + column store              │
│            │  All fields indexed                              │
│            │  Fastest search: <1s                             │
│            │                                                  │
│            │ (after 7 days)                                   │
│            ▼                                                  │
│           WARM (HDD / EBS)                                   │
│            │  Compressed inverted index                       │
│            │  Column store with heavier compression           │
│            │  Search: 1-5s                                    │
│            │                                                  │
│            │ (after 30 days)                                  │
│            ▼                                                  │
│           COLD (S3 Standard)                                 │
│            │  Sparse index (bloom + min/max only)            │
│            │  Raw data LZ4-compressed in Parquet              │
│            │  Search: 10-60s (on-demand segment load)        │
│            │                                                  │
│            │ (after 1 year)                                   │
│            ▼                                                  │
│           FROZEN (S3 Glacier)                                │
│              No index, archive only                           │
│              Restore: 1-12 hours                             │
│              Used for compliance/legal hold                   │
└──────────────────────────────────────────────────────────────┘
```

### 7.2 Tier Migration Engine
```python
class TierMigrationEngine:
    """
    Manages segment movement across storage tiers based on age policies.
    Runs as background daemon on every indexer node.
    """

    def __init__(self, storage_backends: dict):
        self.hot_store = storage_backends['hot']      # Local NVMe
        self.warm_store = storage_backends['warm']    # Network HDD
        self.cold_store = storage_backends['cold']    # S3
        self.frozen_store = storage_backends['frozen'] # Glacier

    async def run_migration_cycle(self):
        """Check all segments and migrate as needed."""
        segments = await self.get_all_segments()

        for segment in segments:
            target_tier = self._determine_tier(segment)
            if target_tier != segment.current_tier:
                await self._migrate_segment(segment, target_tier)

    def _determine_tier(self, segment: Segment) -> str:
        """Determine correct tier based on age and retention policy."""
        age_days = (datetime.now() - segment.time_end).days
        policy = self._get_retention_policy(segment.tenant_id, segment.index_id)

        if age_days <= policy.hot_days:
            return 'hot'
        elif age_days <= policy.warm_days:
            return 'warm'
        elif age_days <= policy.cold_days:
            return 'cold'
        elif age_days <= policy.frozen_days:
            return 'frozen'
        else:
            return 'delete'

    async def _migrate_segment(self, segment: Segment, target_tier: str):
        """Migrate segment to target tier with appropriate transformation."""
        if target_tier == 'warm':
            # Compress index, remove position data
            transformed = self._compress_for_warm(segment)
            await self.warm_store.write(transformed)

        elif target_tier == 'cold':
            # Convert to Parquet + sparse index (bloom + min/max)
            parquet_data = self._convert_to_parquet(segment)
            sparse_index = self._build_sparse_index(segment)
            await self.cold_store.write(parquet_data)
            await self.cold_store.write_index(sparse_index)

        elif target_tier == 'frozen':
            # Just archive raw compressed data
            await self.frozen_store.archive(segment.storage_path)

        elif target_tier == 'delete':
            await self._delete_segment(segment)

        # Update metadata
        await self._update_segment_metadata(segment.segment_id, target_tier)

    def _compress_for_warm(self, segment: Segment) -> bytes:
        """Rewrite segment with heavier compression for warm tier."""
        reader = SegmentReader(segment)

        # Remove position index (no phrase search on warm)
        # Apply ZSTD compression (better ratio than LZ4)
        # Keep inverted index but with smaller posting lists (top-freq terms only)
        return rewrite_segment(
            reader,
            compression='zstd',
            keep_positions=False,
            term_frequency_cutoff=3  # Only index terms appearing 3+ times
        )

    def _build_sparse_index(self, segment: Segment) -> dict:
        """Build minimal index for cold tier: bloom filters + min/max."""
        reader = SegmentReader(segment)
        sparse = {
            'time_range': (segment.time_start, segment.time_end),
            'event_count': segment.event_count,
            'bloom_filters': {},
            'min_max': {}
        }

        for field_name in reader.get_fields():
            values = reader.get_field_values(field_name)
            # Bloom filter for existence queries
            bloom = BloomFilter(capacity=len(values), error_rate=0.01)
            for v in values:
                bloom.add(str(v))
            sparse['bloom_filters'][field_name] = bloom.serialize()

            # Min/max for range pruning
            if reader.is_numeric_field(field_name):
                sparse['min_max'][field_name] = (min(values), max(values))

        return sparse
```

---

## 8. Deep Dive: Distributed Query Execution

### 8.1 Query Processing Pipeline
```
┌────────────┐    ┌────────────┐    ┌────────────┐    ┌────────────┐
│   Parse    │───▶│   Plan     │───▶│  Execute   │───▶│  Aggregate │
│   Query    │    │  (Optimize)│    │  (Scatter) │    │  (Gather)  │
└────────────┘    └────────────┘    └────────────┘    └────────────┘
```

### 8.2 Query Language Parser
```python
class QueryParser:
    """
    Parse SPL-like query language into execution plan.
    Syntax: <search_terms> | <command> <args> | <command> <args> ...

    Examples:
    - index=web status>=500 "timeout error"
    - index=web | stats count by status | sort -count
    - index=app error | rex "user=(?P<user>\w+)" | top user
    """

    def parse(self, query_string: str) -> QueryPlan:
        """Parse query string into logical execution plan."""
        # Split on pipe operator (respecting quotes)
        stages = self._split_pipes(query_string)

        # First stage is always a search/filter
        search_stage = self._parse_search(stages[0])

        # Subsequent stages are transforming commands
        transform_stages = []
        for stage in stages[1:]:
            cmd = self._parse_command(stage)
            transform_stages.append(cmd)

        return QueryPlan(
            search=search_stage,
            transforms=transform_stages
        )

    def _parse_search(self, search_str: str) -> SearchStage:
        """Parse search terms into filter predicates."""
        predicates = []

        # Parse field=value conditions
        for match in re.finditer(r'(\w+)\s*(>=|<=|!=|=|>|<)\s*("[^"]*"|[\S]+)', search_str):
            field, op, value = match.groups()
            value = value.strip('"')
            predicates.append(FieldPredicate(field, op, value))

        # Parse free text terms
        text_terms = re.sub(r'\w+\s*[><=!]+\s*"?[^"\s]+"?', '', search_str).strip()
        if text_terms:
            predicates.append(TextPredicate(text_terms))

        return SearchStage(predicates=predicates)

    def _parse_command(self, cmd_str: str) -> TransformStage:
        """Parse transform command (stats, sort, head, rex, etc.)."""
        parts = cmd_str.strip().split(None, 1)
        command = parts[0]
        args = parts[1] if len(parts) > 1 else ''

        handlers = {
            'stats': self._parse_stats,
            'sort': self._parse_sort,
            'head': self._parse_head,
            'tail': self._parse_tail,
            'where': self._parse_where,
            'rex': self._parse_rex,
            'eval': self._parse_eval,
            'dedup': self._parse_dedup,
            'top': self._parse_top,
            'timechart': self._parse_timechart,
        }

        if command in handlers:
            return handlers[command](args)
        raise QuerySyntaxError(f"Unknown command: {command}")
```

### 8.3 Distributed Query Executor
```python
class DistributedQueryExecutor:
    """
    Scatter-gather query execution across time-partitioned shards.
    Optimizations: segment pruning, parallel scan, early termination.
    """

    def __init__(self, search_head_cluster, segment_catalog):
        self.cluster = search_head_cluster
        self.catalog = segment_catalog

    async def execute(self, query_plan: QueryPlan, tenant_id: int,
                      time_range: TimeRange, timeout_s: float = 30) -> AsyncIterator:
        """Execute distributed query with streaming results."""

        # 1. Identify relevant segments (prune by time + bloom + min/max)
        candidate_segments = await self._prune_segments(
            tenant_id, query_plan.search, time_range
        )

        # 2. Group segments by storage tier for different execution strategies
        hot_segments = [s for s in candidate_segments if s.tier == 'hot']
        warm_segments = [s for s in candidate_segments if s.tier == 'warm']
        cold_segments = [s for s in candidate_segments if s.tier == 'cold']

        # 3. Scatter search to indexer peers
        search_tasks = []

        # Hot: scatter to nodes holding segments in memory/SSD
        for batch in chunk(hot_segments, 10):
            node = self._get_segment_owner(batch[0])
            task = asyncio.create_task(
                node.search_segments(batch, query_plan.search, timeout_s)
            )
            search_tasks.append(task)

        # Warm: scatter to nodes with HDD access
        for batch in chunk(warm_segments, 5):
            node = self._get_segment_owner(batch[0])
            task = asyncio.create_task(
                node.search_segments(batch, query_plan.search, timeout_s)
            )
            search_tasks.append(task)

        # Cold: on-demand fetch from S3 (slower)
        if cold_segments:
            task = asyncio.create_task(
                self._search_cold_tier(cold_segments, query_plan.search, timeout_s)
            )
            search_tasks.append(task)

        # 4. Stream partial results as they arrive
        result_stream = MergeSortStream(key=lambda e: e.timestamp, reverse=True)

        for completed in asyncio.as_completed(search_tasks):
            try:
                partial_results = await asyncio.wait_for(completed, timeout=timeout_s)
                result_stream.add_batch(partial_results)

                # Apply transforms incrementally where possible
                if query_plan.is_streaming_compatible():
                    yield self._apply_streaming_transforms(
                        result_stream, query_plan.transforms
                    )
            except asyncio.TimeoutError:
                # Return partial results
                break

        # 5. Final aggregation
        yield self._finalize_transforms(result_stream, query_plan.transforms)

    async def _prune_segments(self, tenant_id: int, search: SearchStage,
                              time_range: TimeRange) -> List[Segment]:
        """
        Aggressively prune segments before searching.
        Typically eliminates 90%+ of segments.
        """
        # Time-based pruning (most effective)
        segments = await self.catalog.get_segments_in_range(
            tenant_id, time_range.start, time_range.end
        )

        pruned = []
        for segment in segments:
            # Check bloom filter for field value existence
            if not self._bloom_check(segment, search.predicates):
                continue  # Skip segment - value definitely not present

            # Check min/max for numeric range predicates
            if not self._minmax_check(segment, search.predicates):
                continue  # Skip segment - range doesn't overlap

            pruned.append(segment)

        return pruned

    def _bloom_check(self, segment: Segment, predicates: List) -> bool:
        """Check bloom filter - false means definitely not in segment."""
        for pred in predicates:
            if isinstance(pred, FieldPredicate) and pred.op == '=':
                bloom = segment.bloom_filters.get(pred.field)
                if bloom and not bloom.might_contain(pred.value):
                    return False
        return True

    def _minmax_check(self, segment: Segment, predicates: List) -> bool:
        """Check min/max index for range predicates."""
        for pred in predicates:
            if isinstance(pred, FieldPredicate) and pred.op in ('>', '>=', '<', '<='):
                minmax = segment.min_max_fields.get(pred.field)
                if minmax:
                    seg_min, seg_max = minmax
                    if pred.op in ('>', '>=') and float(pred.value) > seg_max:
                        return False
                    if pred.op in ('<', '<=') and float(pred.value) < seg_min:
                        return False
        return True
```

### 8.4 Search Head Clustering
```python
class SearchHeadCluster:
    """
    Cluster of search heads for high availability and load balancing.
    - Captain election via Raft consensus
    - Job scheduling across members
    - Artifact replication for saved searches
    """

    def __init__(self, members: List[SearchHead]):
        self.members = members
        self.captain = None
        self.job_queue = PriorityQueue()

    def assign_search(self, search_job: SearchJob) -> SearchHead:
        """Assign search to least-loaded member."""
        # Consider: current load, memory usage, affinity to data
        loads = [(m, m.current_load()) for m in self.members if m.is_healthy()]
        loads.sort(key=lambda x: x[1])

        assigned = loads[0][0]
        assigned.accept_job(search_job)
        return assigned

    def handle_member_failure(self, failed_member: SearchHead):
        """Redistribute jobs from failed member."""
        orphaned_jobs = failed_member.get_running_jobs()
        for job in orphaned_jobs:
            if job.is_restartable():
                new_member = self.assign_search(job)
                new_member.restart_job(job, from_checkpoint=job.last_checkpoint)
```

---

## 9. Component Optimization

### 9.1 Kafka Configuration
```yaml
# Broker config for log ingestion
num.partitions: 128                    # per topic
default.replication.factor: 3
min.insync.replicas: 2
log.retention.hours: 168               # 7 days replay buffer
log.segment.bytes: 1073741824          # 1 GB segments
compression.type: lz4                  # best throughput
message.max.bytes: 10485760            # 10 MB max batch

# Producer config (agents)
batch.size: 1048576                    # 1 MB batches
linger.ms: 100                         # wait up to 100ms to fill batch
acks: 1                                # leader ack (balance durability/speed)
buffer.memory: 67108864                # 64 MB buffer

# Consumer config (indexers)
fetch.min.bytes: 1048576               # 1 MB minimum fetch
fetch.max.wait.ms: 500
max.poll.records: 10000
auto.offset.reset: earliest
```

### 9.2 Flink Real-Time Alerting
```python
class AlertStreamProcessor:
    """
    Flink job consuming from Kafka for real-time alerting.
    Evaluates alert conditions as sliding window aggregations.
    """

    def process(self, env: StreamExecutionEnvironment):
        # Source: Kafka topic
        source = KafkaSource.builder() \
            .set_topics("logs.raw.*") \
            .set_starting_offsets(OffsetsInitializer.latest()) \
            .build()

        stream = env.from_source(source, WatermarkStrategy.for_monotonous_timestamps())

        # Key by tenant + alert_id
        keyed_stream = stream \
            .filter(lambda e: self._has_matching_alerts(e)) \
            .key_by(lambda e: (e.tenant_id, e.matched_alert_id))

        # Sliding window aggregation (5-min window, 1-min slide)
        windowed = keyed_stream \
            .window(SlidingEventTimeWindows.of(Time.minutes(5), Time.minutes(1))) \
            .aggregate(AlertAggregator())

        # Evaluate alert conditions and emit notifications
        alerts = windowed.filter(lambda agg: agg.evaluate_condition())
        alerts.add_sink(AlertNotificationSink())
```

### 9.3 Bloom Filter Optimization
```python
class SegmentBloomFilter:
    """
    Per-segment bloom filter for fast segment pruning.
    Saves expensive I/O by eliminating segments that definitely
    don't contain searched terms.

    At 1% FPR with 100K terms per segment:
    - Size: ~120 KB per segment
    - Total for hot tier (700K segments): ~84 GB in memory
    - Segment elimination rate: typically 85-95%
    """

    def __init__(self, expected_items=100000, fp_rate=0.01):
        # Optimal size: -n*ln(p) / (ln(2))^2
        self.size = int(-expected_items * math.log(fp_rate) / (math.log(2)**2))
        self.num_hashes = int((self.size / expected_items) * math.log(2))
        self.bit_array = bitarray(self.size)
        self.bit_array.setall(0)

    def add(self, item: str):
        for i in range(self.num_hashes):
            idx = mmh3.hash(item, i) % self.size
            self.bit_array[idx] = 1

    def might_contain(self, item: str) -> bool:
        for i in range(self.num_hashes):
            idx = mmh3.hash(item, i) % self.size
            if not self.bit_array[idx]:
                return False  # Definitely not present
        return True  # Might be present (FPR ≤ 1%)
```

---

## 10. Observability

### 10.1 Platform Metrics
```yaml
# Ingestion Health
- ingest_events_per_second: by tenant, sourcetype
- ingest_lag_seconds: Kafka consumer lag
- ingest_drop_rate: events rejected (quota, parse error)
- indexer_queue_depth: per-node processing backlog

# Search Performance
- search_latency_p50: target < 1s
- search_latency_p99: target < 5s
- search_concurrency: active searches
- segments_scanned_per_search: avg, p99
- segment_prune_ratio: % eliminated by bloom/minmax

# Storage
- tier_usage_bytes: by tier, tenant
- tier_migration_rate: segments/hour moving between tiers
- compaction_rate: merges per hour
- storage_cost_per_gb: by tier

# Reliability
- data_loss_events: target = 0
- replication_lag: Kafka ISR status
- node_health: indexer/search head availability
```

### 10.2 SLI/SLO Definitions
```yaml
SLOs:
  ingestion_availability:
    definition: "% of time ingest endpoint returns 2xx"
    target: 99.999%
    window: 30 days

  search_latency:
    definition: "p99 search latency for hot tier queries"
    target: 5 seconds
    window: 30 days

  data_completeness:
    definition: "% of ingested events searchable within 60s"
    target: 99.9%

  query_availability:
    definition: "% of searches completing without error"
    target: 99.99%
```

---

## 11. Trade-off Analysis

| Decision | Option A | Option B | Choice | Rationale |
|----------|----------|----------|--------|-----------|
| Index format | Lucene (ES) | Custom segment format | Custom | Control over tiering, compression, pruning |
| Ingestion buffer | Kafka | Kinesis | Kafka | Higher throughput, replay, ecosystem |
| Hot storage | Local SSD | Distributed (Ceph) | Local SSD | Lowest latency, segment locality |
| Cold format | Raw compressed | Parquet columnar | Parquet | Columnar enables field-level reads |
| Query language | SQL | SPL-like pipes | SPL-like | Better for exploratory log analysis |
| Alerting | Poll-based | Stream-based (Flink) | Flink | Sub-second alert latency |
| Multi-tenancy | Shared index | Per-tenant index | Per-tenant | Isolation, independent retention |
| Compression | LZ4 (hot) / ZSTD (cold) | Single codec | Mixed | LZ4 speed for hot, ZSTD ratio for cold |

### Key Design Decisions

1. **Segment-based architecture**: Each segment is self-contained with its own index, enabling independent tiering, compaction, and deletion without rewriting other segments.

2. **Bloom filters for pruning**: At PB scale, reading every segment is impossible. Bloom filters eliminate 90%+ of irrelevant segments before any I/O.

3. **Streaming query results**: For multi-billion event searches, streaming partial results gives users immediate feedback rather than waiting for full completion.

4. **Separation of hot path (Flink) and batch path (Indexer)**: Real-time alerting needs sub-second latency which batch indexing can't provide.

---

## 12. Failure Modes & Mitigations

| Failure | Impact | Mitigation |
|---------|--------|------------|
| Kafka broker failure | Temporary ingest slowdown | RF=3, ISR failover, producer retries |
| Indexer node crash | Segment loss if uncommitted | WAL + Kafka replay from last committed offset |
| Search head OOM | Query fails | Memory limits per query, spill to disk |
| S3 outage | Cold tier unsearchable | Hot/warm still available, degrade gracefully |
| Noisy tenant | Other tenants impacted | Per-tenant rate limits, resource quotas, fair scheduling |
| Corrupt segment | Search errors | Checksum validation, rebuild from Kafka replay |
| Network partition | Split-brain indexing | Kafka consumer groups handle rebalancing |

---

## 13. Multi-Tenancy Architecture

```
┌─────────────────────────────────────────────────┐
│              TENANT ISOLATION                     │
│                                                  │
│  Ingestion:  Separate Kafka topics per tenant    │
│  Indexing:   Dedicated indexer pools (premium)   │
│  Storage:    Per-tenant segment namespacing      │
│  Search:     Query-level tenant_id enforcement   │
│  Quotas:     Ingest rate, storage, search conc.  │
│                                                  │
│  Isolation levels:                               │
│  - Standard: Logical isolation (shared infra)    │
│  - Premium:  Dedicated indexer pool              │
│  - Enterprise: Dedicated cluster (VPC)           │
└─────────────────────────────────────────────────┘
```

---

## 14. Evolution Path

```
Phase 1: Single-tenant, hot-only, basic search (100 TB)
Phase 2: Multi-tenant, hot+warm tiers, alerting (1 PB)
Phase 3: Cold tier (S3), distributed query, dashboards (10 PB)
Phase 4: ML-powered anomaly detection, frozen tier, compliance (100 PB+)
```
