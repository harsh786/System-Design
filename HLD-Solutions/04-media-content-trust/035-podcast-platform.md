# Podcast Platform - System Design

## 1. Problem Statement

Design a podcast platform supporting RSS feed ingestion at scale, audio streaming, dynamic ad insertion, transcription, and creator analytics for 100M+ listeners and 5M+ shows.

---

## 2. Functional Requirements

| # | Requirement | Description |
|---|-------------|-------------|
| FR1 | RSS Feed Ingestion | Crawl and ingest millions of podcast RSS feeds with change detection |
| FR2 | Audio Upload/Hosting | Creators upload episodes directly; platform hosts and delivers audio |
| FR3 | Episode Streaming | Adaptive bitrate audio streaming with resume position |
| FR4 | Subscriptions | Subscribe to shows, auto-download new episodes |
| FR5 | Search & Discovery | Full-text search across shows, episodes, transcripts |
| FR6 | Creator Analytics | Downloads, listener demographics, retention curves, episode performance |
| FR7 | Dynamic Ad Insertion | Server-side ad stitching with targeting and frequency capping |
| FR8 | Transcription | Auto-transcribe episodes for search and accessibility |
| FR9 | Chapters | Support podcast chapters (timestamps + titles + images) |
| FR10 | Recommendations | Personalized show and episode suggestions |

---

## 3. Non-Functional Requirements

| Requirement | Target |
|-------------|--------|
| Availability | 99.95% |
| Audio start latency | < 500ms |
| RSS crawl freshness | New episodes detected within 15 minutes |
| Transcription latency | < 30 minutes after episode publish |
| Ad insertion latency | < 50ms additional latency per ad |
| Concurrent listeners | 10M+ |
| Catalog size | 5M+ shows, 200M+ episodes |
| Search latency | < 150ms p95 |
| Analytics freshness | < 1 hour for basic metrics, < 24h for demographics |
| DAI accuracy | Correct targeting >95%, zero audible glitches |

---

## 4. Capacity Estimation

### Traffic Estimates

```
Monthly active listeners:       100M
Daily active listeners:         30M
Concurrent streams (peak):     10M
Avg session duration:           45 minutes
Episodes played/user/day:       2.5
Total plays/day:                75M
Avg episode duration:           40 minutes
Avg bitrate:                    128 kbps (stereo) / 64 kbps (mono speech)

Streaming bandwidth:
  10M concurrent × 96 kbps (weighted avg) = 960 Gbps peak

RSS feeds to crawl:
  5M shows × check every 30 min = 167K feeds/minute = 2,800 feeds/sec

Search queries:
  30M DAU × 3 searches/day = 90M/day ≈ 1K QPS avg, 5K QPS peak

Ad insertion requests:
  75M plays/day × 4 ad slots avg = 300M ad decisions/day ≈ 3,500 QPS
```

### Storage Estimates

```
Audio storage:
  200M episodes × 40 min × 96 kbps = ~115 PB
  New episodes/day: 100K × 40 min × 96 kbps = 58 TB/day

Transcripts:
  200M episodes × 40 min × 150 words/min × 6 bytes/word = 7.2 TB
  New/day: 100K × 40 min × 150 × 6 = 3.6 GB/day

Metadata:
  5M shows × 10 KB = 50 GB
  200M episodes × 5 KB = 1 TB

Analytics events:
  75M plays × 60 position reports/play × 200 bytes = 900 TB/year
```

---

## 5. Data Modeling

### 5.1 Shows Table (PostgreSQL)

```sql
CREATE TABLE shows (
    show_id         BIGINT PRIMARY KEY,
    title           VARCHAR(500) NOT NULL,
    description     TEXT,
    author          VARCHAR(300),
    owner_email     VARCHAR(255),
    owner_user_id   BIGINT REFERENCES users(user_id),  -- NULL for RSS-only
    language        VARCHAR(10) DEFAULT 'en',
    categories      TEXT[] NOT NULL,
    cover_art_url   VARCHAR(512),
    website_url     VARCHAR(512),
    rss_feed_url    VARCHAR(1024) UNIQUE,
    is_hosted       BOOLEAN DEFAULT FALSE,   -- Hosted on platform vs RSS import
    is_explicit     BOOLEAN DEFAULT FALSE,
    episode_count   INT DEFAULT 0,
    subscriber_count BIGINT DEFAULT 0,
    total_plays     BIGINT DEFAULT 0,
    avg_episode_length_sec INT,
    publish_frequency VARCHAR(20),           -- 'daily', 'weekly', 'biweekly'
    last_episode_at TIMESTAMPTZ,
    last_crawled_at TIMESTAMPTZ,
    crawl_etag      VARCHAR(255),            -- HTTP ETag for change detection
    crawl_last_modified VARCHAR(255),        -- Last-Modified header
    feed_hash       VARCHAR(64),             -- SHA-256 of feed content
    status          VARCHAR(20) DEFAULT 'active', -- 'active','paused','dead'
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_shows_rss ON shows(rss_feed_url);
CREATE INDEX idx_shows_categories ON shows USING GIN(categories);
CREATE INDEX idx_shows_owner ON shows(owner_user_id) WHERE owner_user_id IS NOT NULL;
CREATE INDEX idx_shows_last_crawled ON shows(last_crawled_at ASC) WHERE status = 'active';
CREATE INDEX idx_shows_subscribers ON shows(subscriber_count DESC);
CREATE INDEX idx_shows_last_episode ON shows(last_episode_at DESC);
CREATE INDEX idx_shows_status ON shows(status);
```

### 5.2 Episodes Table (PostgreSQL - Partitioned by publish_date)

```sql
CREATE TABLE episodes (
    episode_id      BIGINT PRIMARY KEY,
    show_id         BIGINT NOT NULL REFERENCES shows(show_id),
    guid            VARCHAR(512) NOT NULL,    -- RSS GUID for deduplication
    title           VARCHAR(500) NOT NULL,
    description     TEXT,
    summary         TEXT,
    audio_url       VARCHAR(1024) NOT NULL,   -- Original source URL or hosted URL
    hosted_audio_url VARCHAR(1024),           -- Platform-hosted copy
    duration_sec    INT,
    file_size_bytes BIGINT,
    mime_type       VARCHAR(50) DEFAULT 'audio/mpeg',
    season          SMALLINT,
    episode_number  SMALLINT,
    episode_type    VARCHAR(20) DEFAULT 'full', -- 'full', 'trailer', 'bonus'
    is_explicit     BOOLEAN DEFAULT FALSE,
    cover_art_url   VARCHAR(512),
    transcript_status VARCHAR(20) DEFAULT 'pending', -- 'pending','processing','ready','failed'
    transcript_url  VARCHAR(512),
    chapters        JSONB,                    -- [{start_ms, title, url, image_url}]
    publish_date    TIMESTAMPTZ NOT NULL,
    play_count      BIGINT DEFAULT 0,
    unique_listeners BIGINT DEFAULT 0,
    avg_completion   DECIMAL(4,3) DEFAULT 0,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(show_id, guid)
) PARTITION BY RANGE (publish_date);

-- Create monthly partitions
CREATE TABLE episodes_2024_01 PARTITION OF episodes
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');

CREATE INDEX idx_episodes_show_date ON episodes(show_id, publish_date DESC);
CREATE INDEX idx_episodes_guid ON episodes(show_id, guid);
CREATE INDEX idx_episodes_transcript ON episodes(transcript_status) WHERE transcript_status = 'pending';
CREATE INDEX idx_episodes_publish ON episodes(publish_date DESC);
CREATE INDEX idx_episodes_plays ON episodes(play_count DESC);
```

### 5.3 User Subscriptions (PostgreSQL)

```sql
CREATE TABLE user_subscriptions (
    user_id         BIGINT NOT NULL,
    show_id         BIGINT NOT NULL,
    subscribed_at   TIMESTAMPTZ DEFAULT NOW(),
    auto_download   BOOLEAN DEFAULT FALSE,
    notifications   BOOLEAN DEFAULT TRUE,
    playback_speed  DECIMAL(2,1) DEFAULT 1.0,
    trim_silence    BOOLEAN DEFAULT FALSE,
    PRIMARY KEY (user_id, show_id)
);

CREATE INDEX idx_subs_user ON user_subscriptions(user_id, subscribed_at DESC);
CREATE INDEX idx_subs_show ON user_subscriptions(show_id);
```

### 5.4 Playback Progress (ScyllaDB)

```sql
CREATE TABLE playback_progress (
    user_id         BIGINT,
    episode_id      BIGINT,
    position_ms     INT,
    duration_ms     INT,
    completed       BOOLEAN,
    speed           DECIMAL,
    updated_at      TIMESTAMP,
    PRIMARY KEY (user_id, episode_id)
) WITH compaction = {'class': 'LeveledCompactionStrategy'}
  AND gc_grace_seconds = 604800;

-- For "Up Next" queue
CREATE TABLE user_queue (
    user_id         BIGINT,
    position        INT,
    episode_id      BIGINT,
    added_at        TIMESTAMP,
    source          TEXT,           -- 'auto', 'manual', 'subscription'
    PRIMARY KEY (user_id, position)
) WITH CLUSTERING ORDER BY (position ASC);
```

### 5.5 Ad Campaigns & Inventory (PostgreSQL)

```sql
CREATE TABLE ad_campaigns (
    campaign_id     BIGINT PRIMARY KEY,
    advertiser_id   BIGINT NOT NULL,
    name            VARCHAR(200) NOT NULL,
    audio_url       VARCHAR(1024) NOT NULL,
    duration_ms     INT NOT NULL,
    click_url       VARCHAR(1024),
    budget_cents    BIGINT NOT NULL,
    spent_cents     BIGINT DEFAULT 0,
    cpm_cents       INT NOT NULL,              -- Cost per mille (1000 impressions)
    start_date      DATE NOT NULL,
    end_date        DATE NOT NULL,
    status          VARCHAR(20) DEFAULT 'active',
    targeting       JSONB NOT NULL,            -- See targeting schema below
    frequency_cap   JSONB,                     -- {per_user_per_day: 3, per_user_total: 10}
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

/*
targeting JSONB schema:
{
    "geo": ["US", "CA", "GB"],
    "age_range": [25, 54],
    "gender": ["M", "F"],
    "interests": ["technology", "business"],
    "show_categories": ["Technology", "Business"],
    "show_ids": [123, 456],           -- Direct show targeting
    "exclude_show_ids": [789],
    "device": ["ios", "android"],
    "time_of_day": [6, 22],           -- 6am to 10pm
    "language": ["en"]
}
*/

CREATE INDEX idx_campaigns_active ON ad_campaigns(status, start_date, end_date)
    WHERE status = 'active';
CREATE INDEX idx_campaigns_targeting ON ad_campaigns USING GIN(targeting jsonb_path_ops);
CREATE INDEX idx_campaigns_budget ON ad_campaigns(spent_cents, budget_cents)
    WHERE status = 'active';

CREATE TABLE ad_slots (
    slot_id         BIGINT PRIMARY KEY,
    episode_id      BIGINT NOT NULL REFERENCES episodes(episode_id),
    slot_type       VARCHAR(20) NOT NULL,      -- 'pre_roll', 'mid_roll', 'post_roll'
    offset_ms       INT NOT NULL,              -- Position in episode
    max_duration_ms INT DEFAULT 60000,
    min_duration_ms INT DEFAULT 15000,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_slots_episode ON ad_slots(episode_id, offset_ms);

CREATE TABLE ad_impressions (
    impression_id   BIGINT PRIMARY KEY,
    campaign_id     BIGINT NOT NULL,
    episode_id      BIGINT NOT NULL,
    user_id         BIGINT,
    slot_type       VARCHAR(20),
    listened_ms     INT,
    completed       BOOLEAN,
    skipped         BOOLEAN DEFAULT FALSE,
    geo_country     CHAR(2),
    device_type     VARCHAR(20),
    timestamp       TIMESTAMPTZ NOT NULL DEFAULT NOW()
) PARTITION BY RANGE (timestamp);

CREATE INDEX idx_impressions_campaign ON ad_impressions(campaign_id, timestamp DESC);
CREATE INDEX idx_impressions_user ON ad_impressions(user_id, campaign_id, timestamp DESC);
```

### 5.6 Transcripts (PostgreSQL + Elasticsearch)

```sql
CREATE TABLE transcripts (
    episode_id      BIGINT PRIMARY KEY REFERENCES episodes(episode_id),
    language        VARCHAR(10) DEFAULT 'en',
    model_version   VARCHAR(50),
    word_count      INT,
    confidence_avg  DECIMAL(4,3),
    segments        JSONB,                    -- [{start_ms, end_ms, text, speaker, confidence}]
    full_text       TEXT,                     -- Plain text for full-text search
    srt_url         VARCHAR(512),             -- SRT subtitle file
    vtt_url         VARCHAR(512),             -- WebVTT file
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    processing_time_sec INT
);

CREATE INDEX idx_transcripts_fulltext ON transcripts USING GIN(to_tsvector('english', full_text));
```

### 5.7 Analytics Events (ClickHouse)

```sql
CREATE TABLE episode_analytics (
    event_date      Date,
    event_time      DateTime64(3),
    episode_id      UInt64,
    show_id         UInt64,
    user_id         UInt64,
    event_type      LowCardinality(String),  -- 'play_start', 'position', 'complete', 'skip'
    position_ms     UInt32,
    duration_ms     UInt32,
    speed           Float32,
    geo_country     LowCardinality(String),
    geo_region      String,
    device_type     LowCardinality(String),
    app_version     String,
    referrer        LowCardinality(String),  -- 'search', 'subscription', 'recommendation'
    session_id      String
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(event_date)
ORDER BY (show_id, episode_id, event_date, user_id)
TTL event_date + INTERVAL 2 YEAR;

-- Materialized view for real-time episode play counts
CREATE MATERIALIZED VIEW episode_play_counts_mv
ENGINE = SummingMergeTree()
PARTITION BY toYYYYMM(event_date)
ORDER BY (episode_id, event_date)
AS SELECT
    episode_id,
    event_date,
    countIf(event_type = 'play_start') AS play_starts,
    uniqIf(user_id, event_type = 'play_start') AS unique_listeners,
    countIf(event_type = 'complete') AS completions
FROM episode_analytics
GROUP BY episode_id, event_date;
```

### 5.8 RSS Crawl State (ScyllaDB)

```sql
CREATE TABLE crawl_state (
    feed_url        TEXT PRIMARY KEY,
    show_id         BIGINT,
    last_crawled    TIMESTAMP,
    next_crawl      TIMESTAMP,
    etag            TEXT,
    last_modified   TEXT,
    content_hash    TEXT,
    http_status     INT,
    consecutive_failures INT,
    crawl_interval_sec INT,          -- Adaptive: 900 to 86400
    priority        INT,             -- 1=high (popular), 5=low
    last_new_episode TIMESTAMP,
    assigned_crawler TEXT,            -- Crawler node currently responsible
) WITH compaction = {'class': 'LeveledCompactionStrategy'};

CREATE INDEX idx_crawl_next ON crawl_state(next_crawl);
```

---

## 6. High-Level Design (HLD)

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              CLIENT APPLICATIONS                                     │
│  ┌────────┐  ┌────────┐  ┌────────┐  ┌────────────┐  ┌──────────┐                 │
│  │  iOS   │  │Android │  │  Web   │  │Smart Spkrs │  │ Car/Auto │                 │
│  │  App   │  │  App   │  │Player  │  │            │  │          │                 │
│  └───┬────┘  └───┬────┘  └───┬────┘  └─────┬──────┘  └────┬─────┘                 │
│      └───────────┴───────────┴──────────────┴───────────────┘                       │
└──────────────────────────────────┬───────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              API GATEWAY & CDN                                        │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────────┐             │
│  │  API Gateway    │    │  Audio CDN      │    │  Ad Decision Engine │             │
│  │  (rate limit,   │    │  (with SSAI     │    │  (real-time         │             │
│  │   auth, route)  │    │   stitching)    │    │   ad selection)     │             │
│  └────────┬────────┘    └────────┬────────┘    └──────────┬──────────┘             │
└───────────┼──────────────────────┼────────────────────────┼─────────────────────────┘
            │                      │                        │
            ▼                      ▼                        ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              CORE SERVICES                                            │
│                                                                                       │
│  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌────────────────┐        │
│  │  Catalog  │ │  Playback │ │  Search   │ │  User     │ │ Subscription   │        │
│  │  Service  │ │  Service  │ │  Service  │ │  Service  │ │ Service        │        │
│  └───────────┘ └───────────┘ └───────────┘ └───────────┘ └────────────────┘        │
│                                                                                       │
│  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌────────────────┐        │
│  │  RSS      │ │  Ad       │ │Transcriptn│ │ Analytics │ │ Recommendation │        │
│  │  Crawler  │ │  Service  │ │  Service  │ │  Service  │ │ Service        │        │
│  └───────────┘ └───────────┘ └───────────┘ └───────────┘ └────────────────┘        │
└─────────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              RSS CRAWLING INFRASTRUCTURE                              │
│                                                                                       │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐       │
│  │  Scheduler   │    │  Crawler     │    │  Parser      │    │  Dedup       │       │
│  │  (Priority   │───►│  Pool        │───►│  Service     │───►│  Service     │       │
│  │   Queue)     │    │  (200 nodes) │    │  (RSS/Atom)  │    │  (GUID +    │       │
│  │              │    │              │    │              │    │   content)   │       │
│  │  Adaptive    │    │  Polite:     │    │  Extracts:   │    │              │       │
│  │  intervals   │    │  robots.txt  │    │  - Episodes  │    │  Outputs:    │       │
│  │  based on    │    │  rate limit  │    │  - Chapters  │    │  - New eps   │       │
│  │  frequency   │    │  per domain  │    │  - Metadata  │    │  - Updates   │       │
│  └──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘       │
└─────────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              DYNAMIC AD INSERTION (SSAI)                              │
│                                                                                       │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐       │
│  │  Ad Decision │    │  Ad Stitcher │    │  Frequency   │    │  Analytics   │       │
│  │  Service     │───►│  (Server-    │───►│  Cap Store   │───►│  Tracker     │       │
│  │              │    │   side)      │    │  (Redis)     │    │              │       │
│  │  Targeting:  │    │              │    │              │    │  Viewability │       │
│  │  - Profile   │    │  Zero-gap    │    │  Per-user    │    │  Completion  │       │
│  │  - Context   │    │  audio merge │    │  Per-campaign│    │  Attribution │       │
│  │  - Show cat  │    │  Loudness    │    │  Time-based  │    │              │       │
│  └──────────────┘    │  matching    │    └──────────────┘    └──────────────┘       │
│                      └──────────────┘                                                │
└─────────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              DATA STORES                                              │
│                                                                                       │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────┐  ┌──────────────────┐          │
│  │ PostgreSQL   │  │ ScyllaDB     │  │ Redis      │  │ Elasticsearch    │          │
│  │ (Shows, Eps, │  │ (Progress,   │  │ (Freq cap, │  │ (Full-text +     │          │
│  │  Ads, Users) │  │  Queue,      │  │  Sessions, │  │  transcript      │          │
│  │              │  │  Crawl state)│  │  Rate lim) │  │  search)         │          │
│  └──────────────┘  └──────────────┘  └────────────┘  └──────────────────┘          │
│                                                                                       │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────┐                                │
│  │ Kafka        │  │ S3/GCS       │  │ ClickHouse │                                │
│  │ (Events,     │  │ (Audio files,│  │ (Analytics,│                                │
│  │  Crawl tasks)│  │  Transcripts)│  │  Ad metrics│                                │
│  └──────────────┘  └──────────────┘  └────────────┘                                │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 7. Low-Level Design (LLD) - APIs

### 7.1 Get Episode Stream URL (with Ad Insertion)

```
GET /api/v1/episodes/EP123456/stream
Authorization: Bearer <user_token>
X-Device-Id: device_abc
X-Listener-Geo: US-CA

Response (200 OK):
{
    "episode_id": "EP123456",
    "stream_url": "https://audio-cdn.podcast.com/stream/EP123456?token=xyz&session=sess_abc",
    "format": "audio/mpeg",
    "bitrate_kbps": 128,
    "duration_ms": 2520000,
    "resume_position_ms": 845000,
    "chapters": [
        {"start_ms": 0, "title": "Intro", "image_url": null},
        {"start_ms": 60000, "title": "Topic 1: AI Agents", "image_url": "https://..."},
        {"start_ms": 1200000, "title": "Topic 2: Future of Work", "image_url": null},
        {"start_ms": 2400000, "title": "Outro", "image_url": null}
    ],
    "ad_markers": [
        {"offset_ms": 0, "type": "pre_roll", "duration_ms": 30000},
        {"offset_ms": 1200000, "type": "mid_roll", "duration_ms": 60000},
        {"offset_ms": 2520000, "type": "post_roll", "duration_ms": 15000}
    ],
    "transcript_available": true,
    "loudness_normalization_lufs": -16.0
}
```

### 7.2 Search Episodes

```
GET /api/v1/search?q=machine+learning+transformers&type=episode,show&limit=20
Authorization: Bearer <user_token>

Response (200 OK):
{
    "episodes": {
        "items": [
            {
                "episode_id": "EP789012",
                "show_id": "SH345678",
                "title": "Understanding Transformer Architecture",
                "show_title": "Machine Learning Street Talk",
                "description": "Deep dive into attention mechanisms...",
                "publish_date": "2024-01-10T08:00:00Z",
                "duration_sec": 3840,
                "transcript_snippet": "...the key innovation in transformers is the self-attention mechanism which allows...",
                "relevance_score": 0.95
            }
        ],
        "total": 1420
    },
    "shows": {
        "items": [
            {
                "show_id": "SH345678",
                "title": "Machine Learning Street Talk",
                "author": "Dr. Tim Scarfe",
                "subscriber_count": 250000,
                "episode_count": 180,
                "categories": ["Technology", "Science"]
            }
        ],
        "total": 45
    }
}
```

### 7.3 Creator Analytics

```
GET /api/v1/shows/SH345678/analytics?period=30d&metrics=plays,listeners,retention
Authorization: Bearer <creator_token>

Response (200 OK):
{
    "show_id": "SH345678",
    "period": {"start": "2023-12-16", "end": "2024-01-15"},
    "summary": {
        "total_plays": 485000,
        "unique_listeners": 125000,
        "avg_completion_rate": 0.72,
        "new_subscribers": 8500,
        "total_subscribers": 250000
    },
    "daily": [
        {"date": "2024-01-15", "plays": 18500, "unique_listeners": 12000}
    ],
    "demographics": {
        "geo": [{"country": "US", "pct": 0.45}, {"country": "GB", "pct": 0.12}],
        "device": [{"type": "ios", "pct": 0.55}, {"type": "android", "pct": 0.35}],
        "age_range": [{"range": "25-34", "pct": 0.38}, {"range": "35-44", "pct": 0.28}]
    },
    "top_episodes": [
        {
            "episode_id": "EP789012",
            "title": "Understanding Transformer Architecture",
            "plays": 45000,
            "avg_completion": 0.78,
            "retention_curve": [1.0, 0.95, 0.90, 0.85, 0.80, 0.75, 0.70, 0.65, 0.60]
        }
    ],
    "listening_methods": {
        "subscription_feed": 0.60,
        "search": 0.15,
        "recommendation": 0.20,
        "shared_link": 0.05
    }
}
```

### 7.4 Submit New Show (RSS)

```
POST /api/v1/shows/submit
Authorization: Bearer <creator_token>

Request:
{
    "rss_feed_url": "https://feeds.example.com/my-podcast/feed.xml",
    "claimed_ownership": true
}

Response (202 Accepted):
{
    "submission_id": "sub_abc123",
    "status": "validating",
    "estimated_processing_time_sec": 60,
    "validation_steps": [
        {"step": "fetch_feed", "status": "in_progress"},
        {"step": "parse_rss", "status": "pending"},
        {"step": "validate_audio", "status": "pending"},
        {"step": "ownership_verification", "status": "pending"}
    ]
}
```

### 7.5 Upload Episode (Hosted)

```
POST /api/v1/shows/SH345678/episodes/upload
Authorization: Bearer <creator_token>
Content-Type: multipart/form-data

Request (multipart):
  file: <audio_file.mp3>
  metadata: {
      "title": "Episode 50: The Future of Podcasting",
      "description": "In this milestone episode...",
      "season": 3,
      "episode_number": 50,
      "explicit": false,
      "publish_date": "2024-01-20T08:00:00Z",
      "chapters": [
          {"start_ms": 0, "title": "Intro"},
          {"start_ms": 120000, "title": "Main Topic"},
          {"start_ms": 2400000, "title": "Q&A"}
      ]
  }

Response (202 Accepted):
{
    "episode_id": "EP999001",
    "upload_status": "processing",
    "processing_steps": [
        {"step": "audio_validation", "status": "complete"},
        {"step": "loudness_normalization", "status": "in_progress"},
        {"step": "multi_bitrate_encode", "status": "pending"},
        {"step": "transcription", "status": "pending"},
        {"step": "cdn_distribution", "status": "pending"}
    ],
    "estimated_ready": "2024-01-15T15:05:00Z"
}
```

---

## 8. Deep Dive: Dynamic Ad Insertion (DAI)

### 8.1 Server-Side Ad Stitching Architecture

```
Ad-Inserted Audio Stream Flow:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Client Request → CDN Edge → Ad Decision → Audio Stitcher → Client

Detailed flow:
┌────────┐     ┌────────────┐     ┌──────────────────────────────────┐
│ Client │────►│ CDN Edge   │────►│ SSAI Origin (Ad Stitcher)        │
│        │     │ (cache     │     │                                  │
│        │     │  bypass for│     │ 1. Parse request context          │
│        │     │  ad-enabled│     │ 2. Query Ad Decision Engine       │
│        │     │  episodes) │     │ 3. Fetch episode audio segment    │
│        │     │            │     │ 4. Fetch ad creative audio        │
│        │◄────│◄───────────│◄────│ 5. Stitch: normalize loudness     │
│        │     │            │     │ 6. Encode + stream to client      │
└────────┘     └────────────┘     └──────────────────────────────────┘
                                          │
                                          ▼
                                  ┌──────────────────┐
                                  │ Ad Decision Svc  │
                                  │                  │
                                  │ Inputs:          │
                                  │  - User profile  │
                                  │  - Show category │
                                  │  - Geo/time      │
                                  │  - Freq caps     │
                                  │  - Budget avail  │
                                  │                  │
                                  │ Algorithm:       │
                                  │  Second-price    │
                                  │  auction with    │
                                  │  pacing          │
                                  └──────────────────┘
```

### 8.2 Ad Decision Engine Implementation

```python
class AdDecisionEngine:
    """
    Real-time ad selection with targeting, frequency capping, and budget pacing.
    Must respond in <10ms to keep total DAI latency under 50ms.
    """
    
    def __init__(self, campaign_store, frequency_store, budget_pacer):
        self.campaigns = campaign_store      # PostgreSQL (cached in memory)
        self.frequency = frequency_store      # Redis
        self.pacer = budget_pacer            # Budget pacing service
        self.campaign_index = None           # In-memory targeting index
    
    async def select_ad(self, request: AdRequest) -> AdDecision:
        """
        Select best ad for this impression opportunity.
        
        Args:
            request: Contains user_id, show_id, episode_id, slot_type,
                     geo, device, listener_profile, timestamp
        
        Returns:
            AdDecision with selected creative and metadata
        """
        # Step 1: Find eligible campaigns (targeting match)
        eligible = self._match_targeting(request)
        
        if not eligible:
            return AdDecision(ad=None, fill_type='house_ad')
        
        # Step 2: Apply frequency caps (Redis check)
        uncapped = await self._apply_frequency_caps(request.user_id, eligible)
        
        if not uncapped:
            return AdDecision(ad=None, fill_type='house_ad')
        
        # Step 3: Apply budget pacing (don't overspend early in flight)
        paced = await self._apply_pacing(uncapped)
        
        # Step 4: Run auction (second-price)
        winner = self._run_auction(paced, request)
        
        # Step 5: Record impression (async)
        asyncio.create_task(self._record_impression(winner, request))
        
        # Step 6: Increment frequency counters
        await self._increment_frequency(request.user_id, winner.campaign_id)
        
        return AdDecision(
            ad=winner,
            creative_url=winner.audio_url,
            duration_ms=winner.duration_ms,
            tracking_url=f"/api/v1/ads/track/{winner.impression_id}",
            fill_type='programmatic'
        )
    
    def _match_targeting(self, request: AdRequest) -> list:
        """
        In-memory targeting index for sub-millisecond matching.
        Index structure: inverted index by targeting dimension.
        """
        candidates = set(self.campaign_index['all_active'])
        
        # Geo targeting
        if request.geo_country:
            geo_campaigns = self.campaign_index['geo'].get(request.geo_country, set())
            geo_any = self.campaign_index['geo'].get('*', set())
            candidates &= (geo_campaigns | geo_any)
        
        # Category targeting
        show_categories = self._get_show_categories(request.show_id)
        cat_campaigns = set()
        for cat in show_categories:
            cat_campaigns |= self.campaign_index['category'].get(cat, set())
        cat_campaigns |= self.campaign_index['category'].get('*', set())
        candidates &= cat_campaigns
        
        # Device targeting
        device_campaigns = self.campaign_index['device'].get(request.device_type, set())
        device_any = self.campaign_index['device'].get('*', set())
        candidates &= (device_campaigns | device_any)
        
        # Slot type (pre/mid/post roll)
        slot_campaigns = self.campaign_index['slot_type'].get(request.slot_type, set())
        slot_any = self.campaign_index['slot_type'].get('*', set())
        candidates &= (slot_campaigns | slot_any)
        
        return [self.campaigns[cid] for cid in candidates]
    
    async def _apply_frequency_caps(self, user_id: str, campaigns: list) -> list:
        """Check Redis for frequency cap violations."""
        pipe = self.redis.pipeline()
        
        for campaign in campaigns:
            # Daily cap
            pipe.get(f"freq:daily:{user_id}:{campaign.campaign_id}")
            # Total cap
            pipe.get(f"freq:total:{user_id}:{campaign.campaign_id}")
        
        results = await pipe.execute()
        
        uncapped = []
        for i, campaign in enumerate(campaigns):
            daily_count = int(results[i*2] or 0)
            total_count = int(results[i*2+1] or 0)
            
            cap = campaign.frequency_cap
            if cap:
                if daily_count >= cap.get('per_user_per_day', float('inf')):
                    continue
                if total_count >= cap.get('per_user_total', float('inf')):
                    continue
            
            uncapped.append(campaign)
        
        return uncapped
    
    def _run_auction(self, campaigns: list, request: AdRequest) -> object:
        """Second-price auction with quality score."""
        if len(campaigns) == 1:
            return campaigns[0]
        
        scored = []
        for campaign in campaigns:
            # eCPM adjusted by predicted completion rate
            predicted_completion = self._predict_completion(campaign, request)
            effective_bid = campaign.cpm_cents * predicted_completion
            scored.append((effective_bid, campaign))
        
        scored.sort(key=lambda x: x[0], reverse=True)
        
        # Winner pays second price
        winner = scored[0][1]
        winner.clearing_price = scored[1][0] if len(scored) > 1 else scored[0][0] * 0.5
        
        return winner


class AudioStitcher:
    """
    Server-side audio stitching for seamless ad insertion.
    Handles loudness normalization and crossfading.
    """
    
    TARGET_LUFS = -16.0  # Podcast standard loudness
    CROSSFADE_MS = 50    # Short crossfade to avoid clicks
    
    async def stitch_stream(self, episode_id: str, ad_decisions: list, 
                            start_position_ms: int = 0) -> AsyncGenerator:
        """
        Generate stitched audio stream with ads inserted at marker positions.
        
        Yields audio chunks that seamlessly blend content and ads.
        """
        episode_audio = await self.audio_store.get_stream(episode_id)
        ad_markers = await self.get_ad_markers(episode_id)
        
        current_position = 0
        
        for marker in ad_markers:
            # Skip markers before resume position
            if marker.offset_ms + marker.duration_ms < start_position_ms:
                current_position = marker.offset_ms + marker.duration_ms
                continue
            
            # Yield episode content up to ad marker
            if current_position < marker.offset_ms:
                async for chunk in self._stream_segment(
                    episode_audio, current_position, marker.offset_ms
                ):
                    yield chunk
            
            # Get ad for this slot
            ad = self._get_ad_for_slot(ad_decisions, marker)
            if ad:
                # Normalize ad loudness to match episode
                episode_loudness = await self._measure_loudness(episode_id, marker.offset_ms)
                ad_audio = await self._normalize_ad(ad.creative_url, episode_loudness)
                
                # Crossfade into ad
                yield self._crossfade_transition(
                    episode_audio, marker.offset_ms, ad_audio, 0, self.CROSSFADE_MS
                )
                
                # Stream ad content
                async for chunk in self._stream_audio(ad_audio, self.CROSSFADE_MS, ad.duration_ms):
                    yield chunk
                
                # Crossfade back to content
                yield self._crossfade_transition(
                    ad_audio, ad.duration_ms - self.CROSSFADE_MS,
                    episode_audio, marker.offset_ms,
                    self.CROSSFADE_MS
                )
            
            current_position = marker.offset_ms
        
        # Yield remaining episode content
        async for chunk in self._stream_segment(episode_audio, current_position, None):
            yield chunk
    
    async def _normalize_ad(self, ad_url: str, target_lufs: float) -> bytes:
        """
        Normalize ad creative to target loudness level.
        Cached result (ad creatives don't change).
        """
        cache_key = f"normalized:{ad_url}:{target_lufs}"
        cached = await self.cache.get(cache_key)
        if cached:
            return cached
        
        raw_audio = await self.fetch_audio(ad_url)
        current_lufs = self._measure_integrated_loudness(raw_audio)
        
        gain_db = target_lufs - current_lufs
        normalized = self._apply_gain(raw_audio, gain_db)
        
        # Apply limiter to prevent clipping
        normalized = self._apply_true_peak_limiter(normalized, ceiling_dbtp=-1.0)
        
        await self.cache.set(cache_key, normalized, ttl=86400)
        return normalized
```

---

## 9. Deep Dive: RSS Crawling at Scale

### 9.1 Distributed Crawler Architecture

```
RSS Crawl Pipeline:
━━━━━━━━━━━━━━━━━━

┌────────────────┐     ┌────────────────┐     ┌────────────────┐
│   Scheduler    │────►│  Crawler Pool  │────►│  Parser Pool   │
│                │     │  (200 nodes)   │     │  (50 nodes)    │
│ Priority Queue │     │                │     │                │
│ (Redis Sorted  │     │ HTTP fetchers  │     │ RSS/Atom/JSON  │
│  Set by next   │     │ with:          │     │ feed parsing   │
│  crawl time)   │     │ - robots.txt   │     │                │
│                │     │ - politeness   │     │ Extract:       │
│ Adaptive       │     │ - retry logic  │     │ - New episodes │
│ scheduling:    │     │ - conditional  │     │ - Updated meta │
│ - Popular show │     │   GET (ETag/   │     │ - Chapters     │
│   → every 15m  │     │   If-Mod-Since)│     │ - Enclosures   │
│ - Active show  │     │ - timeout 30s  │     │                │
│   → every 1h   │     │ - max 5MB      │     └───────┬────────┘
│ - Inactive     │     │                │             │
│   → every 24h  │     └────────────────┘             │
│ - Dead (5 fail)│                                    ▼
│   → stop       │                          ┌────────────────┐
└────────────────┘                          │  Deduplicator  │
                                            │                │
                                            │ Check:         │
                                            │ - GUID match   │
                                            │ - Content hash │
                                            │ - URL match    │
                                            │ - Title+date   │
                                            │   similarity   │
                                            └───────┬────────┘
                                                    │
                                                    ▼
                                            ┌────────────────┐
                                            │  Ingestion     │
                                            │                │
                                            │ - Save episode │
                                            │ - Queue audio  │
                                            │   download     │
                                            │ - Queue        │
                                            │   transcription│
                                            │ - Notify subs  │
                                            │ - Index search │
                                            └────────────────┘
```

### 9.2 Crawler Implementation

```python
class DistributedRSSCrawler:
    """
    Distributed RSS crawler with adaptive scheduling, politeness,
    and intelligent change detection.
    """
    
    # Politeness settings
    MIN_CRAWL_DELAY_SEC = 1         # Minimum between requests to same domain
    MAX_CONCURRENT_PER_DOMAIN = 2    # Max parallel requests per domain
    REQUEST_TIMEOUT_SEC = 30
    MAX_FEED_SIZE_BYTES = 5_000_000  # 5MB max feed size
    
    # Adaptive scheduling
    INTERVAL_POPULAR = 900           # 15 min for shows with >10K subscribers
    INTERVAL_ACTIVE = 3600           # 1 hour for shows with weekly episodes
    INTERVAL_MODERATE = 14400        # 4 hours for biweekly shows
    INTERVAL_INACTIVE = 86400        # 24 hours for monthly or less
    MAX_CONSECUTIVE_FAILURES = 5     # Mark as dead after 5 failures
    
    def __init__(self, scheduler, http_client, parser, dedup_service):
        self.scheduler = scheduler
        self.http = http_client
        self.parser = parser
        self.dedup = dedup_service
        self.domain_semaphores = {}  # Per-domain concurrency control
    
    async def crawl_feed(self, feed_url: str, crawl_state: dict) -> CrawlResult:
        """Crawl a single RSS feed with conditional GET and change detection."""
        
        domain = urlparse(feed_url).netloc
        
        # Politeness: respect domain rate limits
        async with self._get_domain_semaphore(domain):
            await self._respect_crawl_delay(domain)
            
            # Conditional GET headers (avoid re-downloading unchanged feeds)
            headers = {}
            if crawl_state.get('etag'):
                headers['If-None-Match'] = crawl_state['etag']
            if crawl_state.get('last_modified'):
                headers['If-Modified-Since'] = crawl_state['last_modified']
            
            try:
                response = await self.http.get(
                    feed_url,
                    headers=headers,
                    timeout=self.REQUEST_TIMEOUT_SEC,
                    max_size=self.MAX_FEED_SIZE_BYTES
                )
                
                # 304 Not Modified - feed hasn't changed
                if response.status == 304:
                    return CrawlResult(
                        status='unchanged',
                        new_episodes=[],
                        next_crawl_interval=crawl_state.get('crawl_interval_sec', 3600)
                    )
                
                if response.status != 200:
                    return self._handle_error(response.status, crawl_state)
                
                # Content hash check (some servers don't support conditional GET)
                content_hash = hashlib.sha256(response.body).hexdigest()
                if content_hash == crawl_state.get('content_hash'):
                    return CrawlResult(status='unchanged', new_episodes=[])
                
                # Parse the feed
                parsed = await self.parser.parse(response.body, feed_url)
                
                # Deduplicate episodes
                new_episodes = await self.dedup.find_new_episodes(
                    parsed.episodes, crawl_state['show_id']
                )
                
                # Calculate next crawl interval based on publishing frequency
                next_interval = self._calculate_interval(parsed, new_episodes)
                
                return CrawlResult(
                    status='updated',
                    new_episodes=new_episodes,
                    show_metadata_updates=parsed.show_updates,
                    next_crawl_interval=next_interval,
                    etag=response.headers.get('ETag'),
                    last_modified=response.headers.get('Last-Modified'),
                    content_hash=content_hash
                )
            
            except asyncio.TimeoutError:
                return self._handle_timeout(crawl_state)
            except Exception as e:
                return self._handle_error_exception(e, crawl_state)
    
    def _calculate_interval(self, parsed_feed, new_episodes: list) -> int:
        """Adaptively set crawl interval based on publishing pattern."""
        
        if not parsed_feed.episodes:
            return self.INTERVAL_INACTIVE
        
        # Calculate average time between episodes
        pub_dates = sorted([ep.publish_date for ep in parsed_feed.episodes[-10:]])
        if len(pub_dates) >= 2:
            intervals = [(pub_dates[i+1] - pub_dates[i]).total_seconds() 
                        for i in range(len(pub_dates)-1)]
            avg_interval = sum(intervals) / len(intervals)
            
            # Crawl at 1/4 the publishing interval (catch new eps quickly)
            ideal_crawl = max(self.INTERVAL_POPULAR, avg_interval / 4)
            return min(int(ideal_crawl), self.INTERVAL_INACTIVE)
        
        # If we found new episodes this crawl, check more frequently
        if new_episodes:
            return self.INTERVAL_ACTIVE
        
        return self.INTERVAL_MODERATE
    
    def _handle_error(self, status: int, crawl_state: dict) -> CrawlResult:
        """Handle HTTP error responses with exponential backoff."""
        failures = crawl_state.get('consecutive_failures', 0) + 1
        
        if failures >= self.MAX_CONSECUTIVE_FAILURES:
            return CrawlResult(status='dead', mark_inactive=True)
        
        # Exponential backoff: 1h, 2h, 4h, 8h, 16h
        backoff_interval = min(3600 * (2 ** failures), 86400)
        
        if status == 410:  # Gone - feed permanently removed
            return CrawlResult(status='dead', mark_inactive=True)
        elif status == 429:  # Rate limited
            retry_after = int(crawl_state.get('retry_after', 3600))
            return CrawlResult(status='rate_limited', next_crawl_interval=retry_after)
        
        return CrawlResult(
            status='error',
            next_crawl_interval=backoff_interval,
            consecutive_failures=failures
        )


class EpisodeDeduplicator:
    """
    Deduplicate episodes across multiple signals to handle RSS feed quirks:
    - Same episode with different GUIDs (feed migration)
    - Same GUID with updated content (corrections)
    - Duplicate entries in feed
    """
    
    async def find_new_episodes(self, parsed_episodes: list, show_id: str) -> list:
        """Identify genuinely new episodes from a parsed feed."""
        
        existing_guids = await self.db.get_episode_guids(show_id)
        existing_urls = await self.db.get_episode_urls(show_id)
        
        new_episodes = []
        
        for episode in parsed_episodes:
            # Check 1: GUID match (most reliable)
            if episode.guid in existing_guids:
                # Check if content updated (title/url changed)
                await self._check_for_updates(episode, existing_guids[episode.guid])
                continue
            
            # Check 2: Audio URL match (feed might have changed GUIDs)
            if episode.audio_url in existing_urls:
                continue
            
            # Check 3: Fuzzy title + date match (handles minor title corrections)
            if await self._fuzzy_match_exists(episode, show_id):
                continue
            
            # Check 4: Audio content hash (same file, different URL)
            # Only for small files or when other checks are ambiguous
            if episode.file_size_bytes and episode.file_size_bytes < 1_000_000:
                if await self._content_hash_exists(episode.audio_url):
                    continue
            
            new_episodes.append(episode)
        
        return new_episodes
    
    async def _fuzzy_match_exists(self, episode, show_id: str) -> bool:
        """Check if a similar episode exists (handles title corrections)."""
        from difflib import SequenceMatcher
        
        # Get episodes published within ±2 days
        nearby_episodes = await self.db.get_episodes_near_date(
            show_id, episode.publish_date, window_days=2
        )
        
        for existing in nearby_episodes:
            similarity = SequenceMatcher(
                None, episode.title.lower(), existing.title.lower()
            ).ratio()
            
            if similarity > 0.85:  # 85% title similarity
                return True
        
        return False
```

### 9.3 Crawl Scheduler with Priority Queue

```python
class CrawlScheduler:
    """
    Redis-backed priority scheduler for RSS crawl tasks.
    Uses sorted set with next_crawl_time as score.
    """
    
    BATCH_SIZE = 100  # Fetch this many tasks at once
    
    def __init__(self, redis_client):
        self.redis = redis_client
        self.queue_key = "crawl:schedule"
        self.lock_prefix = "crawl:lock:"
    
    async def get_next_batch(self, crawler_id: str) -> list:
        """Get next batch of feeds due for crawling."""
        now = time.time()
        
        # Atomic: get feeds with next_crawl <= now, remove from queue
        pipe = self.redis.pipeline()
        pipe.zrangebyscore(self.queue_key, 0, now, start=0, num=self.BATCH_SIZE)
        results = await pipe.execute()
        
        tasks = []
        for feed_url in results[0]:
            # Try to acquire lock (prevent double-crawling)
            lock_key = f"{self.lock_prefix}{feed_url}"
            acquired = await self.redis.set(lock_key, crawler_id, nx=True, ex=300)
            
            if acquired:
                # Remove from schedule (will be re-added after crawl)
                await self.redis.zrem(self.queue_key, feed_url)
                tasks.append(feed_url)
        
        return tasks
    
    async def reschedule(self, feed_url: str, interval_sec: int):
        """Reschedule feed for next crawl."""
        next_crawl = time.time() + interval_sec
        
        # Add jitter (±10%) to prevent thundering herd
        jitter = interval_sec * 0.1 * (2 * random.random() - 1)
        next_crawl += jitter
        
        await self.redis.zadd(self.queue_key, {feed_url: next_crawl})
        
        # Release lock
        await self.redis.delete(f"{self.lock_prefix}{feed_url}")
    
    async def get_queue_stats(self) -> dict:
        """Get scheduler statistics for monitoring."""
        now = time.time()
        
        total = await self.redis.zcard(self.queue_key)
        overdue = await self.redis.zcount(self.queue_key, 0, now)
        next_hour = await self.redis.zcount(self.queue_key, now, now + 3600)
        
        return {
            'total_scheduled': total,
            'overdue': overdue,
            'next_hour': next_hour,
            'crawl_rate_per_min': self._get_recent_crawl_rate()
        }
```

---

## 10. Component Optimization

### 10.1 Kafka Configuration

```yaml
kafka:
  brokers: 24
  topics:
    crawl.tasks:
      partitions: 64
      replication_factor: 3
      retention_ms: 3600000        # 1 hour
      cleanup_policy: delete
      
    episode.new:
      partitions: 32
      replication_factor: 3
      retention_ms: 604800000      # 7 days
      
    playback.events:
      partitions: 128
      replication_factor: 3
      retention_ms: 2592000000     # 30 days
      compression_type: zstd
      
    ad.impressions:
      partitions: 64
      replication_factor: 3
      retention_ms: 7776000000     # 90 days
      min_insync_replicas: 2
      
    transcription.jobs:
      partitions: 32
      replication_factor: 2
      retention_ms: 86400000       # 1 day
  
  producer:
    acks: all
    linger_ms: 20
    batch_size: 65536
    compression_type: zstd
    
  consumer:
    fetch_min_bytes: 32768
    fetch_max_wait_ms: 50
    max_poll_records: 500
```

### 10.2 Redis Configuration

```yaml
redis:
  cluster:
    nodes: 18
    replicas_per_master: 2
    
  instances:
    crawl_scheduler:
      maxmemory: 16gb
      maxmemory_policy: noeviction
      # Sorted set: crawl:schedule → {feed_url: next_crawl_time}
      
    frequency_caps:
      maxmemory: 32gb
      maxmemory_policy: volatile-ttl
      # Keys: freq:daily:{user_id}:{campaign_id} → count (TTL: 24h)
      # Keys: freq:total:{user_id}:{campaign_id} → count (TTL: campaign duration)
      
    playback_state:
      maxmemory: 64gb
      maxmemory_policy: volatile-lru
      # Hash: progress:{user_id} → {episode_id: position_ms}
      
    session_cache:
      maxmemory: 16gb
      maxmemory_policy: volatile-lru
      
  data_structures:
    schedule: "ZADD crawl:schedule {next_crawl_timestamp} {feed_url}"
    freq_daily: "INCR freq:daily:{user_id}:{campaign_id}; EXPIRE ... 86400"
    freq_total: "INCR freq:total:{user_id}:{campaign_id}"
    progress: "HSET progress:{user_id} {episode_id} {position_ms}"
    domain_rate: "SET domain_last:{domain} {timestamp}; EXPIRE ... 60"
```

### 10.3 Flink Stream Processing

```java
public class PodcastAnalyticsPipeline {
    
    public static void main(String[] args) throws Exception {
        StreamExecutionEnvironment env = StreamExecutionEnvironment.getExecutionEnvironment();
        env.setParallelism(32);
        env.enableCheckpointing(60000);
        
        DataStream<PlaybackEvent> events = env
            .addSource(new FlinkKafkaConsumer<>("playback.events", schema, props));
        
        // Real-time play count aggregation
        DataStream<EpisodePlayCount> playCounts = events
            .filter(e -> e.getType().equals("play_start"))
            .keyBy(PlaybackEvent::getEpisodeId)
            .window(TumblingEventTimeWindows.of(Time.minutes(5)))
            .aggregate(new PlayCounter())
            .name("episode-play-counts");
        
        playCounts.addSink(new ClickHouseSink<>("episode_play_counts"));
        
        // Retention curve computation (what % of listeners reach each timestamp)
        DataStream<RetentionCurve> retention = events
            .filter(e -> e.getType().equals("position_report"))
            .keyBy(PlaybackEvent::getEpisodeId)
            .window(TumblingEventTimeWindows.of(Time.hours(1)))
            .process(new RetentionCurveCalculator())
            .name("retention-curves");
        
        retention.addSink(new PostgresSink<>("episode_retention"));
        
        // Ad completion tracking
        DataStream<AdCompletion> adMetrics = events
            .filter(e -> e.getType().equals("ad_event"))
            .keyBy(e -> e.getAdImpressionId())
            .window(SessionWindows.withGap(Time.minutes(5)))
            .process(new AdCompletionTracker())
            .name("ad-completion");
        
        adMetrics.addSink(new KafkaSink<>("ad.completions"));
        
        env.execute("Podcast Analytics Pipeline");
    }
}

class RetentionCurveCalculator extends ProcessWindowFunction<
        PlaybackEvent, RetentionCurve, String, TimeWindow> {
    
    @Override
    public void process(String episodeId, Context ctx,
                       Iterable<PlaybackEvent> events, Collector<RetentionCurve> out) {
        // Divide episode into 100 segments
        // Count unique listeners that reached each segment
        Map<Integer, Set<String>> segmentListeners = new HashMap<>();
        int totalListeners = 0;
        
        for (PlaybackEvent event : events) {
            int segment = (int)(event.getPositionMs() * 100.0 / event.getDurationMs());
            segment = Math.min(segment, 99);
            
            segmentListeners.computeIfAbsent(segment, k -> new HashSet<>())
                           .add(event.getUserId());
        }
        
        totalListeners = segmentListeners.getOrDefault(0, Collections.emptySet()).size();
        
        double[] curve = new double[100];
        for (int i = 0; i < 100; i++) {
            int listeners = segmentListeners.getOrDefault(i, Collections.emptySet()).size();
            curve[i] = totalListeners > 0 ? (double) listeners / totalListeners : 0;
        }
        
        out.collect(new RetentionCurve(episodeId, curve, ctx.window().getEnd()));
    }
}
```

### 10.4 Transcription Pipeline

```python
class TranscriptionPipeline:
    """
    Auto-transcription pipeline using Whisper large-v3.
    Processes ~100K episodes/day with GPU cluster.
    """
    
    def __init__(self, model_path: str, gpu_pool):
        self.model = WhisperModel(model_path, device="cuda", compute_type="float16")
        self.gpu_pool = gpu_pool
    
    async def transcribe_episode(self, episode_id: str, audio_url: str) -> dict:
        """
        Full transcription pipeline:
        1. Download audio
        2. Preprocess (normalize, mono)
        3. Run Whisper inference
        4. Post-process (punctuation, speaker diarization)
        5. Generate timestamps for search indexing
        """
        # Download and preprocess
        audio = await self.download_audio(audio_url)
        audio_mono = self.preprocess(audio, target_sr=16000, mono=True)
        
        # Run Whisper with word-level timestamps
        segments, info = self.model.transcribe(
            audio_mono,
            language=None,  # Auto-detect
            beam_size=5,
            word_timestamps=True,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 500}
        )
        
        # Format segments
        transcript_segments = []
        full_text_parts = []
        
        for segment in segments:
            transcript_segments.append({
                "start_ms": int(segment.start * 1000),
                "end_ms": int(segment.end * 1000),
                "text": segment.text.strip(),
                "confidence": segment.avg_logprob,
                "words": [
                    {"word": w.word, "start": int(w.start*1000), "end": int(w.end*1000)}
                    for w in (segment.words or [])
                ]
            })
            full_text_parts.append(segment.text.strip())
        
        full_text = " ".join(full_text_parts)
        
        # Store results
        await self.store_transcript(episode_id, {
            "segments": transcript_segments,
            "full_text": full_text,
            "language": info.language,
            "confidence_avg": info.language_probability,
            "word_count": len(full_text.split()),
        })
        
        # Index in Elasticsearch for search
        await self.index_for_search(episode_id, full_text, transcript_segments)
        
        return {"status": "complete", "word_count": len(full_text.split())}
```

---

## 11. Observability

```yaml
metrics:
  crawling:
    - name: feeds_crawled_total
      type: counter
      labels: [status, crawler_node]
    
    - name: crawl_latency_ms
      type: histogram
      buckets: [100, 500, 1000, 5000, 10000, 30000]
      labels: [status]
    
    - name: new_episodes_detected_total
      type: counter
      labels: [show_category]
    
    - name: crawl_queue_depth
      type: gauge
      description: "Number of overdue feeds in crawl queue"
    
    - name: feed_freshness_lag_sec
      type: histogram
      description: "Time between episode publish and detection"
      buckets: [60, 300, 900, 1800, 3600, 7200]
  
  ad_insertion:
    - name: ad_decision_latency_ms
      type: histogram
      buckets: [1, 5, 10, 25, 50, 100]
      labels: [decision_type]
    
    - name: ad_fill_rate
      type: gauge
      labels: [slot_type, geo]
    
    - name: ad_completion_rate
      type: gauge
      labels: [slot_type, campaign_id]
    
    - name: ad_stitch_latency_ms
      type: histogram
      buckets: [5, 10, 25, 50, 100, 200]
    
    - name: frequency_cap_rejections_total
      type: counter
      labels: [reason]
  
  playback:
    - name: audio_start_latency_ms
      type: histogram
      buckets: [100, 200, 500, 1000, 2000, 5000]
      labels: [platform, cache_hit]
    
    - name: rebuffer_events_total
      type: counter
      labels: [platform, network_type]
    
    - name: episodes_streamed_total
      type: counter
      labels: [source, platform]
  
  transcription:
    - name: transcription_queue_depth
      type: gauge
    
    - name: transcription_latency_min
      type: histogram
      buckets: [5, 10, 15, 30, 60, 120]
    
    - name: transcription_accuracy
      type: gauge
      labels: [language, model_version]

alerting:
  rules:
    - alert: CrawlQueueBacklog
      expr: crawl_queue_depth > 10000
      for: 5m
      severity: warning
      annotation: "RSS crawl falling behind schedule"
    
    - alert: AdDecisionSlow
      expr: histogram_quantile(0.99, ad_decision_latency_ms) > 50
      for: 2m
      severity: critical
    
    - alert: LowAdFillRate
      expr: ad_fill_rate < 0.7
      for: 15m
      severity: warning
    
    - alert: TranscriptionBacklog
      expr: transcription_queue_depth > 5000
      for: 10m
      severity: warning
    
    - alert: FeedFreshnessDegrade
      expr: histogram_quantile(0.95, feed_freshness_lag_sec) > 3600
      for: 15m
      severity: warning
      annotation: "New episodes taking >1 hour to detect"
```

---

## 12. Considerations & Trade-offs

### 12.1 RSS Crawling Trade-offs

| Decision | Trade-off |
|----------|-----------|
| Adaptive intervals | Complexity vs. infrastructure cost (fewer wasted requests) |
| Conditional GET | Requires server support (many podcast hosts don't support ETag) |
| Content hashing | Extra compute vs. detecting changes without server cooperation |
| WebSub/PubSubHubbub | Real-time notifications but <5% of feeds support it |
| Feed polling vs push | Polling is universal; push requires ecosystem adoption |

### 12.2 Ad Insertion Model

| Approach | Latency | Targeting | Measurability |
|----------|---------|-----------|---------------|
| Baked-in (host-read) | 0ms | None (same for all) | Low |
| Client-side (VAST) | +200ms | Full | Medium (client trust) |
| Server-side (SSAI) | +50ms | Full | High (server-verified) |

We chose SSAI because:
- No client modification needed (works with all podcast apps)
- Cannot be blocked by ad blockers
- Server-verified impression tracking
- Seamless audio experience (loudness-matched)

### 12.3 Consistency Model

- **Playback progress**: Last-write-wins with device priority (active device wins)
- **Subscriptions**: Strongly consistent (user action)
- **Play counts**: Eventually consistent (5-minute lag via Flink)
- **Ad frequency caps**: Strongly consistent within Redis cluster (over-delivery costs money)
- **RSS crawl state**: Eventually consistent (double-crawl is idempotent)
- **Transcripts**: Write-once, immutable after generation

### 12.4 Scaling Challenges

| Challenge | Solution |
|-----------|----------|
| 5M RSS feeds to crawl | Distributed scheduler, adaptive intervals, WebSub for supported feeds |
| 200M episodes searchable | Elasticsearch with transcript indexing, sharded by language |
| 300M ad decisions/day | In-memory campaign index, pre-computed targeting, Redis freq caps |
| 100K new episodes/day | Parallel transcription on GPU cluster, async processing |
| Audio hosting (115 PB) | Tiered storage (hot/warm/cold), CDN for popular, on-demand for long-tail |

### 12.5 Cost Estimation

```
Monthly infrastructure (estimated):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Audio CDN (960 Gbps peak):    $8M
Audio storage (115 PB):       $1.5M (cold storage + CDN hot layer)
Compute (services):           $3M
Transcription GPU cluster:    $500K (A100 GPUs, batch processing)
Databases + Kafka:            $1.5M
RSS Crawling (200 nodes):     $200K
Search (Elasticsearch):       $500K
ClickHouse (analytics):       $300K
Total:                        ~$15.5M/month

Revenue:
- Ad revenue: 75M plays/day × 4 ads × $25 CPM ÷ 1000 = $225K/day = $6.75M/month
- Premium subscriptions: break-even at 2M subs × $10/mo = $20M/month
- Creator hosting fees: variable
```

### 12.6 Future Considerations

1. **WebSub integration**: Real-time feed notifications for supporting hosts (eliminate polling for ~5% of feeds)
2. **AI-powered show notes**: Auto-generate summaries, key topics, guest bios from transcripts
3. **Live podcasting**: Real-time streaming with live chat (similar to Twitch for audio)
4. **Cross-episode search**: "Find all episodes where Elon Musk discusses Mars" across entire catalog
5. **Personalized ad timing**: ML model to insert mid-rolls at natural pause points (not arbitrary timestamps)
6. **Video podcasts**: Support video RSS feeds with adaptive streaming
7. **P2P distribution**: WebRTC-based peer-assisted delivery for popular episodes to reduce CDN costs

---
