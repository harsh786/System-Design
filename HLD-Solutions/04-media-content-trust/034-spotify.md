# Spotify - System Design

## 1. Problem Statement

Design a music and podcast streaming platform serving 500M+ users with sub-200ms audio start, gapless playback, personalized recommendations, and offline support.

---

## 2. Functional Requirements

| # | Requirement | Description |
|---|-------------|-------------|
| FR1 | Audio Streaming | Stream Ogg Vorbis (free) / AAC (premium) at multiple quality levels |
| FR2 | Playlist Management | Create, edit, collaborate on playlists; auto-generated playlists |
| FR3 | Discover Weekly | Personalized weekly playlist of 30 songs using ML recommendations |
| FR4 | Search | Full-text search across tracks, artists, albums, playlists, podcasts |
| FR5 | Offline Downloads | Download tracks/playlists for offline playback (DRM-protected) |
| FR6 | Social Features | Follow friends, see activity, collaborative playlists, share |
| FR7 | Podcasts | RSS ingestion, streaming, episode tracking, show subscriptions |
| FR8 | Lyrics | Time-synced lyrics display during playback |
| FR9 | Queue & Crossfade | User queue management, crossfade between tracks, gapless playback |
| FR10 | Artist Analytics | Play counts, listener demographics, playlist adds |

---

## 3. Non-Functional Requirements

| Requirement | Target |
|-------------|--------|
| Availability | 99.99% |
| Audio start latency | < 200ms (cached), < 500ms (cold) |
| Gapless playback | Zero audible gap between consecutive tracks |
| Monthly active users | 500M+ |
| Concurrent streams | 50M+ |
| Catalog size | 100M+ tracks, 5M+ podcasts |
| Search latency | < 100ms p95 |
| Recommendation freshness | Discover Weekly updated every Monday 00:00 local |
| Offline sync | < 5 minutes for 100 tracks |
| Global availability | < 50ms to nearest edge |

---

## 4. Capacity Estimation

### Traffic Estimates

```
DAU:                        200M
Concurrent listeners:       50M (peak)
Avg session duration:       30 minutes
Tracks played/user/day:     ~25
Total plays/day:            5B
Average track duration:     3.5 minutes
Avg bitrate (weighted):     160 kbps (mix of free/premium qualities)

Streaming bandwidth:
  50M concurrent × 160 kbps = 8 Tbps peak egress

Search queries:
  200M DAU × 5 searches/day = 1B queries/day ≈ 12K QPS avg, 50K QPS peak

Playlist operations:
  200M × 2 ops/day = 400M ops/day ≈ 5K QPS
```

### Storage Estimates

```
Audio catalog:
  100M tracks × 5 quality levels × 3.5 min × 160 kbps avg = ~420 PB
  (With dedup across qualities sharing same master): ~200 PB

Metadata:
  100M tracks × 5 KB avg = 500 GB
  500M users × 2 KB = 1 TB
  10B playlist entries × 50 bytes = 500 GB

Listening history:
  5B plays/day × 100 bytes × 365 days = 180 TB/year

Podcast episodes:
  5M shows × 200 episodes × 45 min × 64 kbps = ~27 PB
```

### Compute Estimates

```
Audio serving:
  8 Tbps / 40 Gbps per CDN node = 200 CDN nodes minimum
  
Recommendation engine:
  Weekly batch: 500M users × 200 candidate tracks = 100B score computations
  ~5000 GPU hours per weekly run (matrix factorization + neural ranking)

Search:
  50K QPS peak / 5K QPS per Elasticsearch node = 10 search nodes (+ replicas)
```

---

## 5. Data Modeling

### 5.1 Tracks Table (PostgreSQL - Partitioned)

```sql
CREATE TABLE tracks (
    track_id        BIGINT PRIMARY KEY,          -- Spotify URI hash
    title           VARCHAR(300) NOT NULL,
    artist_ids      BIGINT[] NOT NULL,
    album_id        BIGINT NOT NULL,
    duration_ms     INT NOT NULL,
    explicit        BOOLEAN DEFAULT FALSE,
    disc_number     SMALLINT DEFAULT 1,
    track_number    SMALLINT NOT NULL,
    isrc            VARCHAR(12) UNIQUE,          -- International Standard Recording Code
    release_date    DATE,
    popularity      SMALLINT DEFAULT 0,          -- 0-100 score
    preview_url     VARCHAR(512),
    audio_features  JSONB,                       -- danceability, energy, tempo, etc.
    available_markets CHAR(2)[],
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_tracks_album ON tracks(album_id, disc_number, track_number);
CREATE INDEX idx_tracks_artist ON tracks USING GIN(artist_ids);
CREATE INDEX idx_tracks_isrc ON tracks(isrc) WHERE isrc IS NOT NULL;
CREATE INDEX idx_tracks_popularity ON tracks(popularity DESC);
CREATE INDEX idx_tracks_release ON tracks(release_date DESC);
CREATE INDEX idx_tracks_features ON tracks USING GIN(audio_features jsonb_path_ops);
```

### 5.2 Albums Table

```sql
CREATE TABLE albums (
    album_id        BIGINT PRIMARY KEY,
    title           VARCHAR(300) NOT NULL,
    artist_ids      BIGINT[] NOT NULL,
    album_type      VARCHAR(20) NOT NULL,        -- 'album', 'single', 'compilation'
    release_date    DATE NOT NULL,
    total_tracks    SMALLINT NOT NULL,
    label           VARCHAR(200),
    cover_art_urls  JSONB,                       -- {small, medium, large}
    copyrights      JSONB,
    genres          TEXT[],
    popularity      SMALLINT DEFAULT 0,
    available_markets CHAR(2)[],
    upc             VARCHAR(14),
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_albums_artist ON albums USING GIN(artist_ids);
CREATE INDEX idx_albums_release ON albums(release_date DESC);
CREATE INDEX idx_albums_genre ON albums USING GIN(genres);
CREATE INDEX idx_albums_label ON albums(label);
```

### 5.3 Artists Table

```sql
CREATE TABLE artists (
    artist_id       BIGINT PRIMARY KEY,
    name            VARCHAR(300) NOT NULL,
    genres          TEXT[],
    popularity      SMALLINT DEFAULT 0,
    follower_count  BIGINT DEFAULT 0,
    image_urls      JSONB,
    external_urls   JSONB,
    bio             TEXT,
    verified        BOOLEAN DEFAULT FALSE,
    monthly_listeners BIGINT DEFAULT 0,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_artists_name ON artists(name);
CREATE INDEX idx_artists_genre ON artists USING GIN(genres);
CREATE INDEX idx_artists_popularity ON artists(popularity DESC);
CREATE INDEX idx_artists_monthly ON artists(monthly_listeners DESC);
```

### 5.4 Playlists Table (PostgreSQL + ScyllaDB for entries)

```sql
-- Playlist metadata (PostgreSQL)
CREATE TABLE playlists (
    playlist_id     BIGINT PRIMARY KEY,
    owner_id        BIGINT NOT NULL REFERENCES users(user_id),
    name            VARCHAR(200) NOT NULL,
    description     TEXT,
    is_public       BOOLEAN DEFAULT TRUE,
    is_collaborative BOOLEAN DEFAULT FALSE,
    cover_image_url VARCHAR(512),
    follower_count  BIGINT DEFAULT 0,
    total_tracks    INT DEFAULT 0,
    total_duration_ms BIGINT DEFAULT 0,
    snapshot_id     VARCHAR(64) NOT NULL,        -- Version for conflict resolution
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_playlists_owner ON playlists(owner_id, updated_at DESC);
CREATE INDEX idx_playlists_public_followers ON playlists(follower_count DESC) WHERE is_public = TRUE;
CREATE INDEX idx_playlists_snapshot ON playlists(playlist_id, snapshot_id);

-- Playlist entries (ScyllaDB for ordered, high-throughput access)
CREATE TABLE playlist_entries (
    playlist_id     BIGINT,
    position        INT,
    track_id        BIGINT,
    added_by        BIGINT,
    added_at        TIMESTAMP,
    PRIMARY KEY (playlist_id, position)
) WITH CLUSTERING ORDER BY (position ASC)
  AND compaction = {'class': 'LeveledCompactionStrategy'};
```

### 5.5 Listening History (ScyllaDB - Time-series)

```sql
CREATE TABLE listening_history (
    user_id         BIGINT,
    date_bucket     TEXT,            -- '2024-01-15' (daily partition)
    played_at       TIMESTAMP,
    track_id        BIGINT,
    context_type    TEXT,            -- 'playlist', 'album', 'artist', 'search'
    context_id      BIGINT,
    duration_played_ms INT,
    skipped         BOOLEAN,
    shuffle         BOOLEAN,
    offline         BOOLEAN,
    platform        TEXT,            -- 'ios', 'android', 'web', 'desktop'
    PRIMARY KEY ((user_id, date_bucket), played_at)
) WITH CLUSTERING ORDER BY (played_at DESC)
  AND default_time_to_live = 31536000  -- 1 year retention
  AND compaction = {'class': 'TimeWindowCompactionStrategy',
                    'compaction_window_unit': 'DAYS',
                    'compaction_window_size': 7};
```

### 5.6 User Library (PostgreSQL)

```sql
CREATE TABLE user_saved_tracks (
    user_id         BIGINT NOT NULL,
    track_id        BIGINT NOT NULL,
    saved_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, track_id)
);

CREATE INDEX idx_saved_tracks_user_time ON user_saved_tracks(user_id, saved_at DESC);

CREATE TABLE user_followed_artists (
    user_id         BIGINT NOT NULL,
    artist_id       BIGINT NOT NULL,
    followed_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, artist_id)
);

CREATE TABLE user_followed_playlists (
    user_id         BIGINT NOT NULL,
    playlist_id     BIGINT NOT NULL,
    followed_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, playlist_id)
);
```

### 5.7 Audio Files Metadata

```sql
CREATE TABLE audio_files (
    track_id        BIGINT NOT NULL,
    quality         VARCHAR(20) NOT NULL,        -- 'low_24', 'normal_96', 'high_160', 'very_high_320', 'lossless'
    codec           VARCHAR(10) NOT NULL,        -- 'ogg_vorbis', 'aac', 'flac'
    file_id         VARCHAR(64) NOT NULL,        -- Content-addressed hash
    file_size_bytes BIGINT NOT NULL,
    sample_rate     INT NOT NULL,                -- 44100, 48000
    channels        SMALLINT DEFAULT 2,
    loudness_db     DECIMAL(5,2),               -- ReplayGain normalization
    cdn_urls        TEXT[],                      -- Pre-computed CDN paths
    encryption_key_id VARCHAR(64),              -- DRM key reference
    segment_map     JSONB,                       -- Byte offsets for seeking
    PRIMARY KEY (track_id, quality)
);

CREATE INDEX idx_audio_files_file_id ON audio_files(file_id);
```

### 5.8 Recommendation Models

```sql
-- User taste profile (updated daily by batch pipeline)
CREATE TABLE user_taste_profiles (
    user_id         BIGINT PRIMARY KEY,
    genre_affinity  JSONB,           -- {"pop": 0.8, "rock": 0.6, "jazz": 0.2}
    audio_features_avg JSONB,        -- {danceability: 0.7, energy: 0.65, ...}
    artist_vectors  FLOAT4[128],     -- Embedding from collaborative filtering
    track_vectors   FLOAT4[128],     -- User embedding in track space
    top_genres      TEXT[5],
    diversity_score DECIMAL(3,2),    -- How diverse is listening (0-1)
    freshness_pref  DECIMAL(3,2),    -- Preference for new releases (0-1)
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Item embeddings (tracks, artists)
CREATE TABLE item_embeddings (
    item_id         BIGINT NOT NULL,
    item_type       VARCHAR(10) NOT NULL,  -- 'track', 'artist', 'album'
    embedding       FLOAT4[128],
    cluster_id      INT,
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (item_id, item_type)
);

CREATE INDEX idx_embeddings_cluster ON item_embeddings(item_type, cluster_id);
```

---

## 6. High-Level Design (HLD)

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              CLIENT APPLICATIONS                                     │
│  ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐  ┌────────────┐                   │
│  │  iOS   │  │Android │  │Desktop │  │  Web   │  │Smart Spkrs │                   │
│  │  App   │  │  App   │  │  App   │  │Player  │  │ Car, TV    │                   │
│  └───┬────┘  └───┬────┘  └───┬────┘  └───┬────┘  └─────┬──────┘                   │
│      │           │           │           │              │                           │
│      └───────────┴───────────┴───────────┴──────────────┘                           │
│                              │                                                       │
└──────────────────────────────┼───────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              API GATEWAY & EDGE                                       │
│                                                                                       │
│  ┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐               │
│  │   API Gateway    │    │   Rate Limiter   │    │   Auth Service   │               │
│  │   (Envoy/NGINX)  │    │   (Token bucket) │    │   (OAuth2/JWT)   │               │
│  └────────┬─────────┘    └──────────────────┘    └──────────────────┘               │
│           │                                                                          │
└───────────┼──────────────────────────────────────────────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              CORE SERVICES                                            │
│                                                                                       │
│  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────────┐         │
│  │  Playback │ │  Catalog  │ │  Playlist │ │  Search   │ │ Social/Feed   │         │
│  │  Service  │ │  Service  │ │  Service  │ │  Service  │ │ Service       │         │
│  └─────┬─────┘ └───────────┘ └───────────┘ └─────┬─────┘ └───────────────┘         │
│        │                                          │                                  │
│  ┌─────┴─────┐ ┌───────────┐ ┌───────────┐ ┌────┴──────┐ ┌───────────────┐         │
│  │  Audio    │ │  User     │ │  Podcast  │ │  Recommend│ │ Payment/Sub   │         │
│  │  Delivery │ │  Service  │ │  Service  │ │  Service  │ │ Service       │         │
│  └───────────┘ └───────────┘ └───────────┘ └───────────┘ └───────────────┘         │
└─────────────────────────────────────────────────────────────────────────────────────┘
            │                                          │
            ▼                                          ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              AUDIO CDN & DELIVERY                                     │
│                                                                                       │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                           │
│  │   Origin     │    │   Regional   │    │   Edge PoPs  │                           │
│  │   Storage    │───►│   Cache      │───►│   (600+)     │──► Clients               │
│  │   (GCS/S3)  │    │   (50 DCs)   │    │              │                           │
│  └──────────────┘    └──────────────┘    └──────────────┘                           │
│                                                                                       │
│  Strategy: Content-addressed storage, popular tracks pre-warmed at edge             │
└─────────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              RECOMMENDATION & ML PLATFORM                             │
│                                                                                       │
│  ┌──────────────────────────────────────────────────────────────────────────┐       │
│  │                    Batch Pipeline (Weekly)                                 │       │
│  │  ┌──────────┐   ┌──────────────┐   ┌───────────┐   ┌──────────────┐     │       │
│  │  │Listening │──►│Collaborative │──►│  Neural   │──►│Discover Wkly │     │       │
│  │  │ History  │   │ Filtering    │   │  Ranker   │   │  Generation  │     │       │
│  │  └──────────┘   │(ALS/MatFact) │   │ (2-tower) │   └──────────────┘     │       │
│  │                  └──────────────┘   └───────────┘                         │       │
│  └──────────────────────────────────────────────────────────────────────────┘       │
│                                                                                       │
│  ┌──────────────────────────────────────────────────────────────────────────┐       │
│  │                    Real-time Pipeline                                      │       │
│  │  ┌──────────┐   ┌──────────────┐   ┌───────────┐   ┌──────────────┐     │       │
│  │  │Play Event│──►│  Feature     │──►│  Online   │──►│  Home Page   │     │       │
│  │  │ Stream   │   │  Store       │   │  Ranker   │   │  Recs        │     │       │
│  │  └──────────┘   │  (Redis)     │   │           │   └──────────────┘     │       │
│  │                  └──────────────┘   └───────────┘                         │       │
│  └──────────────────────────────────────────────────────────────────────────┘       │
└─────────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              DATA INFRASTRUCTURE                                     │
│                                                                                       │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────┐  ┌──────────────────┐          │
│  │ PostgreSQL   │  │ ScyllaDB     │  │ Redis      │  │ Elasticsearch    │          │
│  │ (Catalog,    │  │ (History,    │  │ (Sessions, │  │ (Search: tracks, │          │
│  │  Users,      │  │  Playlists,  │  │  Features, │  │  artists, albums,│          │
│  │  Playlists)  │  │  Counters)   │  │  Cache)    │  │  playlists)      │          │
│  └──────────────┘  └──────────────┘  └────────────┘  └──────────────────┘          │
│                                                                                       │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────┐  ┌──────────────────┐          │
│  │ Kafka        │  │ GCS/S3       │  │ BigQuery/  │  │ Feature Store    │          │
│  │ (Events,     │  │ (Audio files,│  │ Spark      │  │ (ML features,    │          │
│  │  Play logs)  │  │  Podcasts)   │  │ (Batch ML) │  │  embeddings)     │          │
│  └──────────────┘  └──────────────┘  └────────────┘  └──────────────────┘          │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 7. Low-Level Design (LLD) - APIs

### 7.1 Play Track

```
PUT /api/v1/me/player/play
Authorization: Bearer <access_token>
X-Device-Id: device_abc123

Request:
{
    "context_uri": "spotify:playlist:37i9dQZF1DXcBWIGoYBM5M",
    "offset": {"position": 5},
    "position_ms": 0
}

Response (204 No Content)

-- Internally triggers:
GET /api/v1/audio/resolve?track_id=7ouMYWpwJ422jRcDASZB7P&quality=very_high_320

Internal Response:
{
    "file_id": "a3f2b8c9d4e5f6a7b8c9d0e1f2a3b4c5",
    "cdn_url": "https://audio-edge-us-west.spotify.com/audio/a3f2b8c9d4e5f6a7b8c9d0e1f2a3b4c5",
    "fallback_urls": [
        "https://audio-edge-us-east.spotify.com/audio/a3f2b8c9d4e5f6a7b8c9d0e1f2a3b4c5"
    ],
    "codec": "ogg_vorbis",
    "bitrate_kbps": 320,
    "file_size_bytes": 8432100,
    "encryption": {
        "key_id": "key_xyz789",
        "algorithm": "AES-128-CTR"
    },
    "loudness_normalization_db": -2.5,
    "segment_map": {
        "header_bytes": [0, 4096],
        "seek_table": [[0, 4096], [30000, 512000], [60000, 1024000]]
    },
    "expires_at": "2024-01-15T15:30:00Z"
}
```

### 7.2 Get Recommendations (Discover Weekly)

```
GET /api/v1/me/discover-weekly
Authorization: Bearer <access_token>

Response (200 OK):
{
    "playlist_id": "37i9dQZF1E38BFDI",
    "name": "Discover Weekly",
    "description": "Your weekly mixtape of fresh music. Enjoy new discoveries and deep cuts.",
    "generated_at": "2024-01-15T00:00:00Z",
    "tracks": [
        {
            "track_id": "4iV5W9uYEdYUVa79Axb7Rh",
            "title": "Blinding Lights",
            "artists": [{"id": "1Xyo4u8uXC1ZmMpatF05PJ", "name": "The Weeknd"}],
            "album": {"id": "4yP0hdKOZPNshxUOjY0cZj", "name": "After Hours"},
            "duration_ms": 200040,
            "recommendation_reason": "Because you listened to Daft Punk",
            "score": 0.92
        }
    ],
    "total_tracks": 30
}
```

### 7.3 Search

```
GET /api/v1/search?q=blinding%20lights&type=track,artist&limit=10&market=US
Authorization: Bearer <access_token>

Response (200 OK):
{
    "tracks": {
        "items": [
            {
                "track_id": "0VjIjW4GlUZAMYd2vXMi3b",
                "title": "Blinding Lights",
                "artists": [{"id": "1Xyo4u8uXC1ZmMpatF05PJ", "name": "The Weeknd"}],
                "album": {"id": "4yP0hdKOZPNshxUOjY0cZj", "name": "After Hours"},
                "duration_ms": 200040,
                "popularity": 95,
                "explicit": false,
                "preview_url": "https://p.scdn.co/mp3-preview/abc123"
            }
        ],
        "total": 156
    },
    "artists": {
        "items": [
            {
                "artist_id": "1Xyo4u8uXC1ZmMpatF05PJ",
                "name": "The Weeknd",
                "genres": ["canadian pop", "pop"],
                "popularity": 97,
                "followers": 85000000,
                "images": [{"url": "https://i.scdn.co/image/abc", "width": 640}]
            }
        ],
        "total": 3
    }
}
```

### 7.4 Create/Update Playlist

```
POST /api/v1/playlists
Authorization: Bearer <access_token>

Request:
{
    "name": "Road Trip Vibes",
    "description": "Perfect songs for a long drive",
    "public": true,
    "collaborative": false
}

Response (201 Created):
{
    "playlist_id": "5LiKDArtXYm48Q0iJBRmT3",
    "name": "Road Trip Vibes",
    "owner": {"id": "user123", "display_name": "Harsh"},
    "snapshot_id": "MSw0OGU3NjM2Yzg2NjgxMTQ",
    "tracks": {"total": 0},
    "href": "https://api.spotify.com/v1/playlists/5LiKDArtXYm48Q0iJBRmT3"
}

--- Add tracks:
POST /api/v1/playlists/5LiKDArtXYm48Q0iJBRmT3/tracks

Request:
{
    "uris": [
        "spotify:track:0VjIjW4GlUZAMYd2vXMi3b",
        "spotify:track:7qiZfU4dY1lWllzX7mPBI3"
    ],
    "position": 0
}

Response (201 Created):
{
    "snapshot_id": "MSw0OGU3NjM2Yzg2NjgxMTQ1"
}
```

### 7.5 Record Play Event

```
POST /api/v1/me/player/play-event (Internal)

Request:
{
    "track_id": "0VjIjW4GlUZAMYd2vXMi3b",
    "context_uri": "spotify:playlist:37i9dQZF1DXcBWIGoYBM5M",
    "position_ms": 0,
    "duration_played_ms": 185000,
    "completed": true,
    "skipped": false,
    "shuffle": true,
    "repeat_mode": "off",
    "platform": "ios",
    "device_id": "device_abc123",
    "timestamp": "2024-01-15T14:30:00Z",
    "offline": false
}

Response (202 Accepted)
```

---

## 8. Deep Dive: Recommendation Engine

### 8.1 Architecture Overview

```
Discover Weekly Pipeline:
━━━━━━━━━━━━━━━━━━━━━━━━

Phase 1: Data Collection (Continuous)
┌────────────┐     ┌─────────┐     ┌────────────────┐
│ Play Events│────►│  Kafka  │────►│  Data Lake     │
│ (5B/day)   │     │         │     │  (Parquet on   │
│            │     │         │     │   GCS/S3)      │
└────────────┘     └─────────┘     └────────────────┘

Phase 2: Feature Engineering (Daily)
┌────────────────┐     ┌──────────────────────────────┐
│  Raw Plays     │────►│  Spark Pipeline               │
│  + Skips       │     │  - User-item interaction mat  │
│  + Saves       │     │  - Audio feature aggregation  │
│  + Playlist    │     │  - Session context features   │
│    additions   │     │  - Social graph features      │
└────────────────┘     └──────────────┬───────────────┘
                                      │
Phase 3: Model Training (Weekly)      ▼
┌────────────────────────────────────────────────────────┐
│                                                         │
│  ┌─────────────────┐    ┌──────────────────────────┐  │
│  │ Collaborative   │    │ Content-Based            │  │
│  │ Filtering       │    │                          │  │
│  │                 │    │ Audio CNN features       │  │
│  │ ALS Matrix      │    │ NLP on playlist names    │  │
│  │ Factorization   │    │ Artist2Vec embeddings    │  │
│  │ 128-dim vectors │    │ Genre graph embeddings   │  │
│  └────────┬────────┘    └────────────┬─────────────┘  │
│           │                          │                 │
│           └────────────┬─────────────┘                 │
│                        ▼                               │
│           ┌──────────────────────┐                     │
│           │  Two-Tower Neural    │                     │
│           │  Ranker              │                     │
│           │                      │                     │
│           │  User tower: 128-dim │                     │
│           │  Item tower: 128-dim │                     │
│           │  Cross features      │                     │
│           │  Output: relevance   │                     │
│           └──────────┬───────────┘                     │
│                      │                                 │
└──────────────────────┼─────────────────────────────────┘
                       ▼
Phase 4: Playlist Generation (Sunday night)
┌─────────────────────────────────────────────────────────┐
│  For each user (500M):                                   │
│  1. Retrieve user embedding (128-dim)                    │
│  2. ANN search: find 1000 candidate tracks               │
│  3. Filter: already heard, explicit pref, market avail   │
│  4. Neural rank: score all candidates                     │
│  5. Diversity: MMR to ensure genre/artist spread         │
│  6. Select top 30 tracks                                  │
│  7. Write to playlist store                               │
└─────────────────────────────────────────────────────────┘
```

### 8.2 Collaborative Filtering Implementation

```python
import numpy as np
from implicit.als import AlternatingLeastSquares
from scipy.sparse import csr_matrix

class CollaborativeFilteringModel:
    """
    Alternating Least Squares (ALS) for implicit feedback.
    
    Key insight: We use implicit signals (play count, duration, saves)
    rather than explicit ratings. A play is weighted by engagement:
    - Full listen = weight 1.0
    - Skipped (< 30s) = weight -0.3
    - Saved to library = weight 2.0
    - Added to playlist = weight 1.5
    - Repeated play = weight * log(play_count + 1)
    """
    
    def __init__(self, factors=128, regularization=0.01, iterations=15):
        self.model = AlternatingLeastSquares(
            factors=factors,
            regularization=regularization,
            iterations=iterations,
            use_gpu=True,  # CUDA acceleration
            num_threads=0,  # Use all cores
        )
        self.user_factors = None  # (num_users, 128)
        self.item_factors = None  # (num_items, 128)
    
    def build_interaction_matrix(self, play_events: list) -> csr_matrix:
        """
        Build user-item confidence matrix.
        c_ui = 1 + alpha * f(plays, duration, saves)
        """
        rows, cols, data = [], [], []
        
        for event in play_events:
            user_idx = self.user_map[event['user_id']]
            item_idx = self.item_map[event['track_id']]
            
            # Compute engagement weight
            weight = self._compute_weight(event)
            
            rows.append(user_idx)
            cols.append(item_idx)
            data.append(weight)
        
        matrix = csr_matrix(
            (data, (rows, cols)),
            shape=(self.num_users, self.num_items)
        )
        return matrix
    
    def _compute_weight(self, event: dict) -> float:
        """Compute engagement weight for a play event."""
        base_weight = 0.0
        
        # Duration-based weight
        completion_ratio = event['duration_played_ms'] / event['track_duration_ms']
        if completion_ratio > 0.8:
            base_weight = 1.0
        elif completion_ratio > 0.5:
            base_weight = 0.5
        elif completion_ratio < 0.1:  # Skip
            base_weight = -0.3
        else:
            base_weight = completion_ratio * 0.5
        
        # Boost for explicit positive signals
        if event.get('saved_to_library'):
            base_weight += 2.0
        if event.get('added_to_playlist'):
            base_weight += 1.5
        
        # Repeat listen bonus (logarithmic)
        play_count = event.get('play_count', 1)
        repeat_bonus = np.log1p(play_count) * 0.3
        
        return max(0, base_weight + repeat_bonus)
    
    def train(self, interaction_matrix: csr_matrix):
        """Train ALS model on interaction matrix."""
        self.model.fit(interaction_matrix)
        self.user_factors = self.model.user_factors
        self.item_factors = self.model.item_factors
    
    def get_user_recommendations(self, user_id: str, n: int = 1000,
                                  filter_already_heard: bool = True) -> list:
        """Get top-N candidate tracks for a user."""
        user_idx = self.user_map[user_id]
        
        # Compute scores: dot product of user and all item vectors
        scores = self.user_factors[user_idx] @ self.item_factors.T
        
        if filter_already_heard:
            heard_indices = self.get_user_history_indices(user_id)
            scores[heard_indices] = -np.inf
        
        # Get top N indices
        top_indices = np.argpartition(scores, -n)[-n:]
        top_indices = top_indices[np.argsort(scores[top_indices])[::-1]]
        
        return [(self.item_map_reverse[idx], scores[idx]) for idx in top_indices]


class AudioFeatureCNN:
    """
    Extract audio features using a CNN trained on mel spectrograms.
    Used for content-based similarity (cold-start problem).
    """
    
    def __init__(self):
        self.model = self._build_model()
    
    def _build_model(self):
        """VGG-like architecture for audio feature extraction."""
        import torch.nn as nn
        
        return nn.Sequential(
            # Input: mel spectrogram (1, 128, 1024) - ~23 sec of audio
            nn.Conv2d(1, 64, 3, padding=1), nn.ReLU(), nn.BatchNorm2d(64),
            nn.Conv2d(64, 64, 3, padding=1), nn.ReLU(), nn.BatchNorm2d(64),
            nn.MaxPool2d(2, 2),
            
            nn.Conv2d(64, 128, 3, padding=1), nn.ReLU(), nn.BatchNorm2d(128),
            nn.Conv2d(128, 128, 3, padding=1), nn.ReLU(), nn.BatchNorm2d(128),
            nn.MaxPool2d(2, 2),
            
            nn.Conv2d(128, 256, 3, padding=1), nn.ReLU(), nn.BatchNorm2d(256),
            nn.Conv2d(256, 256, 3, padding=1), nn.ReLU(), nn.BatchNorm2d(256),
            nn.MaxPool2d(2, 2),
            
            nn.AdaptiveAvgPool2d((1, 1)),
            nn.Flatten(),
            nn.Linear(256, 128),  # 128-dim embedding
        )
    
    def extract_features(self, audio_path: str) -> np.ndarray:
        """Extract 128-dim embedding from audio file."""
        mel_spec = self._compute_mel_spectrogram(audio_path)
        with torch.no_grad():
            embedding = self.model(mel_spec.unsqueeze(0).unsqueeze(0))
        return embedding.numpy().flatten()


class PlaylistNLPFeatures:
    """
    Extract features from playlist names/descriptions.
    Intuition: Playlist names encode user intent (e.g., "chill vibes", "workout beast")
    """
    
    def __init__(self):
        from sentence_transformers import SentenceTransformer
        self.encoder = SentenceTransformer('all-MiniLM-L6-v2')
    
    def encode_playlist_context(self, playlists: list) -> np.ndarray:
        """
        For each track, aggregate embeddings of playlists it appears in.
        Tracks in playlists named "sad songs" get a "sadness" signal.
        """
        track_playlist_embeddings = {}
        
        for playlist in playlists:
            name_embedding = self.encoder.encode(playlist['name'])
            for track_id in playlist['track_ids']:
                if track_id not in track_playlist_embeddings:
                    track_playlist_embeddings[track_id] = []
                track_playlist_embeddings[track_id].append(name_embedding)
        
        # Average embeddings for each track
        result = {}
        for track_id, embeddings in track_playlist_embeddings.items():
            result[track_id] = np.mean(embeddings, axis=0)
        
        return result


class DiscoverWeeklyGenerator:
    """Orchestrates the full Discover Weekly generation pipeline."""
    
    def __init__(self, cf_model, audio_model, nlp_model, neural_ranker):
        self.cf_model = cf_model
        self.audio_model = audio_model
        self.nlp_model = nlp_model
        self.neural_ranker = neural_ranker
    
    def generate_for_user(self, user_id: str) -> list:
        """Generate 30-track Discover Weekly playlist for a user."""
        
        # Step 1: Get candidates from collaborative filtering
        cf_candidates = self.cf_model.get_user_recommendations(user_id, n=500)
        
        # Step 2: Get candidates from content similarity
        user_profile = self.get_user_audio_profile(user_id)
        content_candidates = self.audio_model.find_similar(user_profile, n=500)
        
        # Step 3: Merge and deduplicate candidates
        all_candidates = self._merge_candidates(cf_candidates, content_candidates)
        
        # Step 4: Filter (market availability, explicit content pref, recency)
        filtered = self._apply_filters(user_id, all_candidates)
        
        # Step 5: Neural ranking
        user_features = self._get_user_features(user_id)
        scored = []
        for track_id, base_score in filtered:
            track_features = self._get_track_features(track_id)
            neural_score = self.neural_ranker.predict(user_features, track_features)
            final_score = 0.6 * neural_score + 0.3 * base_score + 0.1 * self._freshness_bonus(track_id)
            scored.append((track_id, final_score))
        
        scored.sort(key=lambda x: x[1], reverse=True)
        
        # Step 6: Apply diversity via Maximal Marginal Relevance (MMR)
        diversified = self._mmr_diversify(scored[:200], n=30, lambda_param=0.7)
        
        return diversified
    
    def _mmr_diversify(self, candidates: list, n: int, lambda_param: float) -> list:
        """
        Maximal Marginal Relevance: balance relevance with diversity.
        Ensures we don't recommend 30 songs from same artist/genre.
        """
        selected = []
        remaining = list(candidates)
        
        while len(selected) < n and remaining:
            best_score = -np.inf
            best_idx = 0
            
            for i, (track_id, relevance) in enumerate(remaining):
                # Max similarity to already selected items
                if selected:
                    max_sim = max(
                        self._track_similarity(track_id, sel_id)
                        for sel_id, _ in selected
                    )
                else:
                    max_sim = 0
                
                # MMR score: balance relevance and novelty
                mmr_score = lambda_param * relevance - (1 - lambda_param) * max_sim
                
                if mmr_score > best_score:
                    best_score = mmr_score
                    best_idx = i
            
            selected.append(remaining.pop(best_idx))
        
        return selected
```

---

## 9. Deep Dive: Audio Delivery

### 9.1 Pre-buffering & Gapless Playback

```python
class AudioDeliveryClient:
    """
    Client-side audio delivery logic for seamless playback.
    
    Key techniques:
    1. Pre-buffering: Start fetching next track before current ends
    2. Gapless: Use codec delay compensation + crossfade
    3. Quality adaptation: Switch bitrate based on network conditions
    """
    
    PREFETCH_THRESHOLD_MS = 15000  # Start fetching next track 15s before end
    MIN_BUFFER_MS = 5000           # Minimum buffer before starting playback
    TARGET_BUFFER_MS = 30000       # Target buffer size
    
    def __init__(self, cdn_resolver, drm_client):
        self.cdn_resolver = cdn_resolver
        self.drm = drm_client
        self.buffer = AudioBuffer()
        self.prefetch_queue = []
        self.current_quality = 'high_160'
        self.network_monitor = NetworkMonitor()
    
    async def start_playback(self, track_id: str, position_ms: int = 0):
        """Start playing a track with minimal latency."""
        
        # Step 1: Resolve CDN URL (cached locally)
        audio_meta = await self.cdn_resolver.resolve(track_id, self.current_quality)
        
        # Step 2: Request initial bytes (header + seek to position)
        seek_offset = self._calculate_seek_offset(audio_meta['segment_map'], position_ms)
        
        # Step 3: Fetch header + first chunk in parallel
        header_data, first_chunk = await asyncio.gather(
            self._fetch_range(audio_meta['cdn_url'], 0, audio_meta['segment_map']['header_bytes'][1]),
            self._fetch_range(audio_meta['cdn_url'], seek_offset, seek_offset + 65536)
        )
        
        # Step 4: Decrypt + decode
        decrypted = self.drm.decrypt(header_data + first_chunk, audio_meta['encryption'])
        
        # Step 5: Feed to decoder, start playback when buffer > MIN_BUFFER_MS
        self.buffer.feed(decrypted)
        if self.buffer.duration_ms >= self.MIN_BUFFER_MS:
            self._start_audio_output()
        
        # Step 6: Continue fetching remaining data in background
        asyncio.create_task(self._stream_remaining(audio_meta, seek_offset + 65536))
    
    async def _handle_gapless_transition(self, current_track: dict, next_track: dict):
        """
        Gapless playback between tracks.
        
        Ogg Vorbis has encoder delay (priming samples) that must be trimmed.
        We overlap-add the last samples of current track with first samples of next.
        """
        # Get encoder delay info from metadata
        current_end_padding = current_track.get('end_padding_samples', 0)
        next_start_padding = next_track.get('start_padding_samples', 0)
        
        # Trim padding from both tracks
        current_trimmed = self.buffer.trim_end(current_end_padding)
        next_trimmed = self.prefetch_buffer.trim_start(next_start_padding)
        
        # Seamless concatenation (no crossfade for gapless albums)
        if self._is_same_album(current_track, next_track):
            # Direct concatenation - artist intended no gap
            self.buffer.append(next_trimmed)
        else:
            # Apply short crossfade (12ms) to avoid click
            crossfade_samples = int(0.012 * 44100)  # 12ms at 44.1kHz
            self.buffer.crossfade_append(next_trimmed, crossfade_samples)
    
    def _adapt_quality(self, bandwidth_kbps: float):
        """Adaptive bitrate selection based on network conditions."""
        quality_ladder = [
            ('very_high_320', 320),
            ('high_160', 160),
            ('normal_96', 96),
            ('low_24', 24),
        ]
        
        # Select highest quality that fits in 80% of available bandwidth
        # (leaving 20% headroom for network variance)
        available = bandwidth_kbps * 0.8
        
        for quality, bitrate in quality_ladder:
            if bitrate <= available:
                if quality != self.current_quality:
                    self.current_quality = quality
                    # Quality switch happens at next track (not mid-track)
                    self._schedule_quality_switch(quality)
                return
        
        # Fallback to lowest
        self.current_quality = 'low_24'


class CDNAudioResolver:
    """
    Resolves track IDs to CDN URLs with intelligent routing.
    
    Strategy:
    - Popular tracks (top 1%): Pre-warmed at all edge PoPs
    - Recent tracks (last 30 days): Available at regional caches
    - Long-tail: Fetched from origin on demand, cached on access
    """
    
    POPULAR_THRESHOLD = 10000  # plays/day to be considered "popular"
    
    async def resolve(self, track_id: str, quality: str) -> dict:
        """Get best CDN URL for track."""
        
        # Check local URL cache (TTL: 1 hour)
        cached = self.url_cache.get(f"{track_id}:{quality}")
        if cached and not cached.expired:
            return cached
        
        # Fetch from audio metadata service
        meta = await self.metadata_service.get_audio_file(track_id, quality)
        
        # Select nearest CDN edge with content
        edge_url = await self._select_edge(meta['file_id'], meta['popularity'])
        
        result = {
            'cdn_url': edge_url,
            'file_id': meta['file_id'],
            'file_size_bytes': meta['file_size_bytes'],
            'encryption': meta['encryption'],
            'segment_map': meta['segment_map'],
            'loudness_normalization_db': meta['loudness_db'],
            'start_padding_samples': meta.get('start_padding_samples', 0),
            'end_padding_samples': meta.get('end_padding_samples', 0),
        }
        
        self.url_cache.set(f"{track_id}:{quality}", result, ttl=3600)
        return result
```

---

## 10. Component Optimization

### 10.1 Kafka Configuration

```yaml
kafka:
  brokers: 60
  topics:
    play.events:
      partitions: 256
      replication_factor: 3
      retention_ms: 604800000      # 7 days
      compression_type: zstd
      cleanup_policy: delete
      min_insync_replicas: 2
      
    user.actions:
      partitions: 128
      replication_factor: 3
      retention_ms: 2592000000     # 30 days
      cleanup_policy: compact,delete
      
    recommendation.updates:
      partitions: 64
      replication_factor: 2
      retention_ms: 86400000       # 1 day
      
    catalog.changes:
      partitions: 32
      replication_factor: 3
      retention_ms: -1             # Infinite (compacted)
      cleanup_policy: compact
      
  producer:
    acks: all                      # Durability for play events (revenue!)
    linger_ms: 50                  # Batch for throughput
    batch_size: 131072
    compression_type: zstd
    
  consumer:
    fetch_min_bytes: 65536
    fetch_max_wait_ms: 100
    max_poll_records: 5000
    auto_offset_reset: earliest
```

### 10.2 Redis Configuration

```yaml
redis:
  cluster:
    nodes: 40
    replicas_per_master: 2
    
  instances:
    session_playback:
      maxmemory: 128gb
      maxmemory_policy: volatile-lru
      # Current playback state per user
      # Key: session:{user_id} → {track_id, position_ms, device_id, quality}
      
    feature_store:
      maxmemory: 256gb
      maxmemory_policy: allkeys-lru
      # Real-time ML features for online ranking
      # Key: features:user:{user_id} → {recent_genres, session_length, ...}
      
    url_cache:
      maxmemory: 32gb
      maxmemory_policy: allkeys-lru
      # CDN URL resolution cache
      
    social_feed:
      maxmemory: 64gb
      maxmemory_policy: volatile-ttl
      # Friend activity feed (sorted sets by timestamp)
```

### 10.3 Elasticsearch Search Configuration

```yaml
elasticsearch:
  cluster:
    nodes: 24
    shards_per_index:
      tracks: 12
      artists: 6
      albums: 8
      playlists: 16
    replicas: 2
    
  index_settings:
    tracks:
      analysis:
        analyzer:
          track_analyzer:
            type: custom
            tokenizer: standard
            filter: [lowercase, asciifolding, track_synonym, edge_ngram_filter]
          
          phonetic_analyzer:
            type: custom
            tokenizer: standard
            filter: [lowercase, double_metaphone]
      
      mappings:
        properties:
          title:
            type: text
            analyzer: track_analyzer
            fields:
              exact: { type: keyword }
              phonetic: { type: text, analyzer: phonetic_analyzer }
          artist_name:
            type: text
            analyzer: track_analyzer
            fields:
              exact: { type: keyword }
          popularity:
            type: integer
          release_date:
            type: date
          available_markets:
            type: keyword
          genres:
            type: keyword
          audio_features:
            type: object
            properties:
              danceability: { type: float }
              energy: { type: float }
              tempo: { type: float }
```

### 10.4 Flink for Real-time Features

```java
public class RealTimeFeaturePipeline {
    
    public static void main(String[] args) throws Exception {
        StreamExecutionEnvironment env = StreamExecutionEnvironment.getExecutionEnvironment();
        env.setParallelism(32);
        env.enableCheckpointing(30000);
        
        DataStream<PlayEvent> plays = env
            .addSource(new FlinkKafkaConsumer<>("play.events", new PlayEventSchema(), props));
        
        // Compute session-level features in real-time
        DataStream<UserSessionFeatures> sessionFeatures = plays
            .keyBy(PlayEvent::getUserId)
            .window(SessionWindows.withGap(Time.minutes(30)))
            .process(new SessionFeatureExtractor())
            .name("session-features");
        
        // Update feature store (Redis) for real-time recommendations
        sessionFeatures.addSink(new RedisFeatureSink());
        
        // Compute trending tracks (sliding window)
        DataStream<TrendingTrack> trending = plays
            .keyBy(PlayEvent::getTrackId)
            .window(SlidingEventTimeWindows.of(Time.hours(1), Time.minutes(5)))
            .aggregate(new PlayCounter())
            .filter(c -> c.getCount() > 1000)
            .keyBy(c -> "global")
            .process(new TopNProcess(50))
            .name("trending-tracks");
        
        trending.addSink(new RedisTrendingSink());
        
        env.execute("Spotify Real-time Features");
    }
}
```

---

## 11. Observability

```yaml
metrics:
  playback:
    - name: audio_start_latency_ms
      type: histogram
      buckets: [50, 100, 200, 500, 1000, 2000, 5000]
      labels: [platform, quality, cache_hit]
    
    - name: rebuffer_events_total
      type: counter
      labels: [platform, quality, network_type]
    
    - name: gapless_success_ratio
      type: gauge
      labels: [codec, platform]
    
    - name: tracks_played_total
      type: counter
      labels: [tier, platform, context_type]
  
  recommendations:
    - name: discover_weekly_ctr
      type: gauge
      description: "Click-through rate on Discover Weekly tracks"
    
    - name: recommendation_latency_ms
      type: histogram
      labels: [model_version, endpoint]
    
    - name: skip_rate
      type: gauge
      labels: [source, position_in_playlist]
  
  search:
    - name: search_latency_ms
      type: histogram
      buckets: [10, 25, 50, 100, 200, 500]
      labels: [query_type, result_count]
    
    - name: zero_results_ratio
      type: gauge
      labels: [market, language]
  
  cdn:
    - name: cache_hit_ratio
      type: gauge
      labels: [tier, content_type]
    
    - name: bandwidth_gbps
      type: gauge
      labels: [region, pop_id]

alerting:
  rules:
    - alert: HighAudioStartLatency
      expr: histogram_quantile(0.95, audio_start_latency_ms) > 500
      for: 3m
      severity: critical
    
    - alert: HighSkipRate
      expr: skip_rate{source="discover_weekly"} > 0.6
      for: 1h
      severity: warning
      annotation: "Discover Weekly quality degraded"
    
    - alert: SearchDegraded
      expr: histogram_quantile(0.99, search_latency_ms) > 200
      for: 2m
      severity: critical
```

---

## 12. Considerations & Trade-offs

### 12.1 Audio Format Trade-offs

| Format | Quality @ Bitrate | License | Use Case |
|--------|------------------|---------|----------|
| Ogg Vorbis 96 | Good | Free | Free tier mobile |
| Ogg Vorbis 160 | Very good | Free | Free tier desktop |
| AAC 256 | Excellent | Licensed | Premium |
| FLAC | Lossless | Free | HiFi tier |

### 12.2 Consistency Model

- **Playback state**: Eventually consistent (last-write-wins across devices, 1s staleness)
- **Playlists**: Optimistic concurrency with snapshot_id versioning
- **Play counts**: Eventually consistent (batched increments, 5-minute lag)
- **Library (saved tracks)**: Strongly consistent per user (single-leader replication)
- **Recommendations**: Pre-computed weekly; stale by design (freshness not critical)

### 12.3 Offline Downloads Architecture

```
Download flow:
1. Client requests track list for offline sync
2. Server returns encrypted file URLs + DRM license (time-limited)
3. Client downloads in background (WiFi-preferred)
4. Files stored encrypted on device (Widevine L3 / FairPlay)
5. License renewal: every 30 days must connect to verify subscription active
6. Subscription lapsed → offline files become unplayable after grace period
```

### 12.4 Cold Start Problem

| Scenario | Solution |
|----------|----------|
| New user, no history | Onboarding genre/artist selection → content-based recs |
| New track, no plays | Audio features CNN + artist similarity + editorial boost |
| New artist | Genre graph embedding + similar artist suggestions |
| Market expansion | Transfer learning from similar markets |

### 12.5 Cost Estimation

```
Monthly infrastructure costs (estimated):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CDN bandwidth (8 Tbps peak):      $40M
Storage (200 PB audio):           $4M  (negotiated cold + hot tiers)
Compute (services + ML):          $12M
Databases (Postgres+Scylla+ES):   $5M
ML training (GPU cluster):        $3M
Kafka + streaming infra:          $2M
Total:                            ~$66M/month

Revenue:
- 220M premium × $10/mo:         $2.2B/month
- Ad-supported revenue:           $300M/month
Healthy unit economics.
```

---
