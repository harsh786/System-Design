# System Design: YouTube

## 1. Functional Requirements

1. **Video Upload & Processing**: Users upload videos in various formats; system transcodes to multiple resolutions/codecs
2. **Video Streaming**: Adaptive bitrate streaming (HLS/DASH) to any device
3. **Search & Discovery**: Full-text search, trending, category browsing
4. **Recommendation Engine**: Personalized feed based on watch history, subscriptions, interests
5. **Subscriptions & Notifications**: Subscribe to channels, get notified of new uploads
6. **Comments & Interactions**: Like/dislike, comment threads, community posts
7. **Live Streaming**: Real-time broadcast with chat
8. **Monetization/Ads**: Pre-roll, mid-roll, post-roll ads; creator revenue sharing
9. **Content ID**: Automated copyright detection and enforcement
10. **Playlists**: Create, share, collaborative playlists

## 2. Non-Functional Requirements

| Requirement | Target |
|-------------|--------|
| Availability | 99.99% (52 min downtime/year) |
| Video Upload Latency | Processing complete <30 min for 1080p, <2 hours for 4K |
| Streaming Latency | First frame <2s, rebuffer ratio <0.5% |
| Live Stream Latency | <5s glass-to-glass (standard), <1s (ultra-low) |
| Search Latency | p99 <200ms |
| Recommendation Latency | p99 <100ms |
| Durability | 99.999999999% (11 nines) for uploaded content |
| Scalability | Support 2B+ MAU, 500hr video uploaded/minute |
| Consistency | Eventual consistency for views/likes; strong for uploads |

## 3. Capacity Estimation

### Traffic
- **DAU**: 800M users
- **Video views/day**: 5B (avg 6.25 views/user/day)
- **Video uploads/day**: 720,000 (500 hours/min × 60 min/hr × 24 hr)
- **View QPS**: 5B / 86400 ≈ 58,000 QPS (peak: ~150K QPS)
- **Upload QPS**: 720K / 86400 ≈ 8.3 QPS (peak: ~25 QPS)
- **Comment writes/day**: 500M → ~5,800 QPS
- **Search QPS**: 3B/day → ~35,000 QPS

### Storage
- **Raw video/day**: 720K videos × avg 500MB = 360TB/day raw
- **After transcoding** (multiple resolutions): 360TB × 5 resolutions × 0.7 compression = 1.26PB/day
- **Metadata**: 720K × 5KB = 3.6GB/day
- **Comments**: 500M × 200B = 100GB/day
- **Total storage growth**: ~1.3PB/day → ~475PB/year

### Bandwidth
- **Egress (streaming)**: 5B views × avg 50MB per view = 250PB/day → ~23Tbps avg
- **Ingress (uploads)**: 360TB/day → ~33Gbps avg
- **CDN cache hit ratio**: >95% (reduces origin bandwidth significantly)

### Memory
- **Hot metadata cache**: Top 100M videos × 2KB = 200GB Redis cluster
- **Recommendation cache**: 800M users × 1KB = 800GB
- **Session cache**: 50M concurrent × 500B = 25GB

## 4. Data Modeling

### Videos Table (PostgreSQL / Vitess sharded by video_id)
```sql
CREATE TABLE videos (
    video_id        BIGINT PRIMARY KEY,  -- Snowflake ID
    channel_id      BIGINT NOT NULL,
    title           VARCHAR(500) NOT NULL,
    description     TEXT,
    upload_status   ENUM('processing', 'ready', 'failed', 'blocked') DEFAULT 'processing',
    visibility      ENUM('public', 'unlisted', 'private') DEFAULT 'public',
    duration_ms     INT,
    category_id     SMALLINT,
    language        VARCHAR(10),
    upload_time     TIMESTAMP NOT NULL DEFAULT NOW(),
    publish_time    TIMESTAMP,
    thumbnail_url   VARCHAR(500),
    view_count      BIGINT DEFAULT 0,
    like_count      INT DEFAULT 0,
    dislike_count   INT DEFAULT 0,
    comment_count   INT DEFAULT 0,
    is_live         BOOLEAN DEFAULT FALSE,
    is_age_restricted BOOLEAN DEFAULT FALSE,
    content_id_status ENUM('clear', 'claimed', 'blocked') DEFAULT 'clear',
    monetization    ENUM('on', 'limited', 'off') DEFAULT 'off',
    created_at      TIMESTAMP DEFAULT NOW(),
    updated_at      TIMESTAMP DEFAULT NOW(),
    
    INDEX idx_channel_publish (channel_id, publish_time DESC),
    INDEX idx_category_views (category_id, view_count DESC),
    INDEX idx_upload_status (upload_status, upload_time),
    INDEX idx_trending (publish_time DESC, view_count DESC)
);

CREATE TABLE video_encodings (
    encoding_id     BIGINT PRIMARY KEY,
    video_id        BIGINT NOT NULL,
    resolution      ENUM('144p', '240p', '360p', '480p', '720p', '1080p', '1440p', '2160p'),
    codec           ENUM('h264', 'h265', 'vp9', 'av1'),
    bitrate_kbps    INT,
    file_size_bytes BIGINT,
    storage_path    VARCHAR(500),
    cdn_url_prefix  VARCHAR(300),
    segment_duration_ms INT DEFAULT 4000,
    status          ENUM('pending', 'encoding', 'complete', 'failed'),
    created_at      TIMESTAMP DEFAULT NOW(),
    
    INDEX idx_video_resolution (video_id, resolution, codec),
    UNIQUE INDEX idx_video_encoding (video_id, resolution, codec)
);

CREATE TABLE channels (
    channel_id      BIGINT PRIMARY KEY,
    user_id         BIGINT NOT NULL,
    channel_name    VARCHAR(200) NOT NULL,
    handle          VARCHAR(100) UNIQUE,
    description     TEXT,
    subscriber_count BIGINT DEFAULT 0,
    video_count     INT DEFAULT 0,
    total_views     BIGINT DEFAULT 0,
    country         VARCHAR(5),
    created_at      TIMESTAMP DEFAULT NOW(),
    verified        BOOLEAN DEFAULT FALSE,
    
    INDEX idx_user (user_id),
    INDEX idx_handle (handle),
    INDEX idx_subscribers (subscriber_count DESC)
);

CREATE TABLE subscriptions (
    user_id         BIGINT,
    channel_id      BIGINT,
    notification    ENUM('all', 'personalized', 'none') DEFAULT 'personalized',
    subscribed_at   TIMESTAMP DEFAULT NOW(),
    
    PRIMARY KEY (user_id, channel_id),
    INDEX idx_channel_subs (channel_id, subscribed_at DESC)
);

CREATE TABLE comments (
    comment_id      BIGINT PRIMARY KEY,
    video_id        BIGINT NOT NULL,
    user_id         BIGINT NOT NULL,
    parent_id       BIGINT DEFAULT NULL,  -- NULL for top-level
    content         TEXT NOT NULL,
    like_count      INT DEFAULT 0,
    reply_count     INT DEFAULT 0,
    is_pinned       BOOLEAN DEFAULT FALSE,
    is_hearted      BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMP DEFAULT NOW(),
    updated_at      TIMESTAMP DEFAULT NOW(),
    
    INDEX idx_video_top (video_id, is_pinned DESC, like_count DESC),
    INDEX idx_video_recent (video_id, created_at DESC),
    INDEX idx_parent_replies (parent_id, created_at ASC),
    INDEX idx_user_comments (user_id, created_at DESC)
);

CREATE TABLE watch_history (
    user_id         BIGINT,
    video_id        BIGINT,
    watch_time_ms   INT,
    percentage      FLOAT,
    watched_at      TIMESTAMP DEFAULT NOW(),
    
    PRIMARY KEY (user_id, video_id, watched_at),
    INDEX idx_user_recent (user_id, watched_at DESC)
) PARTITION BY RANGE (watched_at);  -- Monthly partitions

CREATE TABLE playlists (
    playlist_id     BIGINT PRIMARY KEY,
    user_id         BIGINT NOT NULL,
    title           VARCHAR(200),
    visibility      ENUM('public', 'unlisted', 'private') DEFAULT 'public',
    video_count     INT DEFAULT 0,
    created_at      TIMESTAMP DEFAULT NOW(),
    updated_at      TIMESTAMP DEFAULT NOW(),
    
    INDEX idx_user_playlists (user_id, updated_at DESC)
);

CREATE TABLE playlist_items (
    playlist_id     BIGINT,
    position        INT,
    video_id        BIGINT NOT NULL,
    added_at        TIMESTAMP DEFAULT NOW(),
    
    PRIMARY KEY (playlist_id, position),
    INDEX idx_video_in_playlists (video_id)
);
```

### View Counts (Redis + Kafka → Cassandra for persistence)
```sql
-- Cassandra schema for view analytics
CREATE TABLE video_views_by_time (
    video_id    BIGINT,
    time_bucket TEXT,  -- '2024-01-15_14' (hourly bucket)
    view_count  COUNTER,
    PRIMARY KEY (video_id, time_bucket)
) WITH CLUSTERING ORDER BY (time_bucket DESC);

CREATE TABLE video_views_by_geo (
    video_id    BIGINT,
    country     TEXT,
    date        DATE,
    view_count  COUNTER,
    PRIMARY KEY ((video_id, date), country)
);
```

### Search Index (Elasticsearch)
```json
{
  "mappings": {
    "properties": {
      "video_id": { "type": "long" },
      "title": { "type": "text", "analyzer": "standard", "fields": { "keyword": { "type": "keyword" } } },
      "description": { "type": "text", "analyzer": "standard" },
      "tags": { "type": "keyword" },
      "channel_name": { "type": "text", "fields": { "keyword": { "type": "keyword" } } },
      "category": { "type": "keyword" },
      "language": { "type": "keyword" },
      "duration_ms": { "type": "integer" },
      "view_count": { "type": "long" },
      "publish_time": { "type": "date" },
      "captions": { "type": "text", "analyzer": "standard" }
    }
  }
}
```

## 5. High-Level Design (ASCII Architecture)

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                                    CLIENTS                                                │
│  [Web App]  [Mobile iOS/Android]  [Smart TV]  [Gaming Console]  [Embedded Player]       │
└──────────────────────────────────────┬──────────────────────────────────────────────────┘
                                       │
                              ┌────────▼────────┐
                              │   Global DNS    │
                              │  (GeoDNS/Anycast)│
                              └────────┬────────┘
                                       │
                    ┌──────────────────┬┴──────────────────┐
                    │                  │                    │
           ┌────────▼──────┐  ┌───────▼───────┐  ┌───────▼───────┐
           │  CDN Edge     │  │  API Gateway  │  │  Upload       │
           │  (Streaming)  │  │  (Rate Limit, │  │  Service      │
           │  Akamai/Own   │  │   Auth, Route)│  │  (Resumable)  │
           └───────┬───────┘  └───────┬───────┘  └───────┬───────┘
                   │                  │                    │
                   │         ┌────────┴────────────────────┤
                   │         │                             │
    ┌──────────────┤    ┌────▼─────┐  ┌─────────┐   ┌────▼──────────┐
    │              │    │  Video   │  │ Search  │   │  Video         │
    │   Origin     │    │  Service │  │ Service │   │  Processing    │
    │   Storage    │    │          │  │ (ES)    │   │  Pipeline      │
    │   (S3/GCS)  │    └────┬─────┘  └────┬────┘   │               │
    │              │         │              │        │ ┌───────────┐ │
    └──────────────┘         │              │        │ │ Transcode │ │
                             │              │        │ │ (FFmpeg)  │ │
                    ┌────────┴───┐          │        │ └─────┬─────┘ │
                    │            │          │        │ ┌─────▼─────┐ │
              ┌─────▼────┐ ┌────▼─────┐    │        │ │ Thumbnail │ │
              │Recommend │ │  User    │    │        │ │ Generator │ │
              │ Service  │ │ Service  │    │        │ └─────┬─────┘ │
              │(ML/DNN)  │ │          │    │        │ ┌─────▼─────┐ │
              └─────┬────┘ └────┬─────┘    │        │ │ Content   │ │
                    │           │           │        │ │ ID/Safety │ │
                    │           │           │        │ └───────────┘ │
                    │           │           │        └───────────────┘
                    │           │           │
         ┌──────────┴───────────┴───────────┴──────────────────┐
         │                    DATA LAYER                         │
         │                                                      │
         │  ┌──────────┐  ┌──────────┐  ┌───────────────────┐ │
         │  │ Vitess   │  │  Redis   │  │    Cassandra      │ │
         │  │ (MySQL   │  │  Cluster │  │  (View counts,    │ │
         │  │  Sharded)│  │  (Cache) │  │   Watch history)  │ │
         │  └──────────┘  └──────────┘  └───────────────────┘ │
         │                                                      │
         │  ┌──────────┐  ┌──────────┐  ┌───────────────────┐ │
         │  │  Kafka   │  │  HDFS/   │  │  Elasticsearch    │ │
         │  │ (Events) │  │  BigQuery│  │  (Search index)   │ │
         │  └──────────┘  └──────────┘  └───────────────────┘ │
         └──────────────────────────────────────────────────────┘
```

## 6. Low-Level Design: API Contracts

### Video Upload API
```
POST /api/v1/videos/upload/init
Authorization: Bearer <token>
Content-Type: application/json

Request:
{
  "title": "My Video",
  "description": "Description here",
  "category_id": 22,
  "tags": ["tech", "tutorial"],
  "visibility": "public",
  "file_size_bytes": 1073741824,
  "file_name": "video.mp4",
  "content_type": "video/mp4"
}

Response (201):
{
  "video_id": "dQw4w9WgXcQ",
  "upload_url": "https://upload.youtube-internal.com/resumable/v1/abc123",
  "upload_token": "eyJhbGciOi...",
  "chunk_size": 8388608,
  "expires_at": "2024-01-15T15:00:00Z"
}
```

### Video Upload (Resumable - tus protocol)
```
PUT /upload/resumable/v1/{upload_token}
Content-Range: bytes 0-8388607/1073741824
Content-Type: application/octet-stream

[binary chunk data]

Response (308 - Resume Incomplete):
{ "offset": 8388608 }

Response (200 - Complete):
{
  "video_id": "dQw4w9WgXcQ",
  "status": "processing",
  "estimated_processing_time_seconds": 1200
}
```

### Get Video / Stream
```
GET /api/v1/videos/{video_id}

Response (200):
{
  "video_id": "dQw4w9WgXcQ",
  "title": "My Video",
  "channel": {
    "channel_id": "UC123",
    "name": "TechChannel",
    "subscriber_count": 1500000,
    "avatar_url": "https://cdn.yt/avatars/UC123.jpg"
  },
  "duration_ms": 612000,
  "view_count": 12500000,
  "like_count": 450000,
  "publish_time": "2024-01-10T08:00:00Z",
  "streaming": {
    "dash_manifest": "https://cdn.yt/dash/dQw4w9WgXcQ/manifest.mpd",
    "hls_manifest": "https://cdn.yt/hls/dQw4w9WgXcQ/master.m3u8",
    "available_qualities": ["2160p", "1440p", "1080p", "720p", "480p", "360p", "144p"]
  },
  "thumbnails": {
    "default": "https://cdn.yt/thumbs/dQw4w9WgXcQ/default.jpg",
    "high": "https://cdn.yt/thumbs/dQw4w9WgXcQ/hq.jpg"
  }
}
```

### Recommendation Feed
```
GET /api/v1/feed/recommended?page_token={token}&limit=20

Response (200):
{
  "videos": [
    {
      "video_id": "abc123",
      "title": "...",
      "channel": { "name": "...", "avatar_url": "..." },
      "thumbnail_url": "...",
      "duration_ms": 300000,
      "view_count": 5000000,
      "publish_time": "2024-01-14T...",
      "reason": "Based on your watch history"
    }
  ],
  "next_page_token": "eyJ..."
}
```

### Comments API
```
GET /api/v1/videos/{video_id}/comments?sort=top&page_token={token}&limit=20

POST /api/v1/videos/{video_id}/comments
Request:
{ "content": "Great video!", "parent_id": null }

Response (201):
{
  "comment_id": "Ugx123",
  "content": "Great video!",
  "author": { "user_id": "...", "name": "...", "avatar": "..." },
  "created_at": "2024-01-15T12:00:00Z",
  "like_count": 0
}
```

## 7. Deep Dive: Video Transcoding Pipeline

### Architecture
```
┌──────────┐    ┌─────────┐    ┌──────────────────────────────────────┐
│  Upload  │───▶│  Kafka  │───▶│       Transcoding Orchestrator       │
│  Service │    │ (topic: │    │                                      │
└──────────┘    │ upload- │    │  ┌────────────────────────────────┐  │
                │ complete)│    │  │  Split into GOP-aligned chunks │  │
                └─────────┘    │  └────────────────┬───────────────┘  │
                               │                   │                   │
                               │  ┌────────────────▼───────────────┐  │
                               │  │  Parallel Encode (K8s Jobs)    │  │
                               │  │                                │  │
                               │  │  ┌─────┐ ┌─────┐ ┌─────┐     │  │
                               │  │  │chunk│ │chunk│ │chunk│ ... │  │
                               │  │  │ 1   │ │ 2   │ │ 3   │     │  │
                               │  │  └──┬──┘ └──┬──┘ └──┬──┘     │  │
                               │  │     │       │       │         │  │
                               │  │  For each chunk, encode to:   │  │
                               │  │  - H.264: 360p,480p,720p,1080p│  │
                               │  │  - VP9: 720p,1080p,1440p,4K   │  │
                               │  │  - AV1: 720p,1080p,1440p,4K   │  │
                               │  └────────────────┬───────────────┘  │
                               │                   │                   │
                               │  ┌────────────────▼───────────────┐  │
                               │  │     Concatenate + Package      │  │
                               │  │  - Generate HLS segments (.ts) │  │
                               │  │  - Generate DASH segments(.m4s)│  │
                               │  │  - Create manifests            │  │
                               │  └────────────────┬───────────────┘  │
                               │                   │                   │
                               └───────────────────┼───────────────────┘
                                                   │
                               ┌───────────────────▼───────────────────┐
                               │  Post-Processing Pipeline              │
                               │  1. Thumbnail extraction (I-frames)   │
                               │  2. Audio extraction (separate tracks)│
                               │  3. Caption generation (Whisper ASR)  │
                               │  4. Content ID fingerprinting         │
                               │  5. Safety/moderation ML scan         │
                               │  6. Upload to object storage + CDN   │
                               └───────────────────────────────────────┘
```

### FFmpeg Transcoding Configuration
```python
# transcoding_profiles.py
ENCODING_LADDER = {
    "h264": [
        {"resolution": "3840x2160", "bitrate": "15000k", "profile": "high", "level": "5.1",
         "preset": "slow", "crf": 18, "maxrate": "20000k", "bufsize": "30000k"},
        {"resolution": "2560x1440", "bitrate": "8000k", "profile": "high", "level": "5.0",
         "preset": "slow", "crf": 20, "maxrate": "12000k", "bufsize": "16000k"},
        {"resolution": "1920x1080", "bitrate": "4500k", "profile": "high", "level": "4.1",
         "preset": "medium", "crf": 22, "maxrate": "6000k", "bufsize": "9000k"},
        {"resolution": "1280x720", "bitrate": "2500k", "profile": "high", "level": "3.1",
         "preset": "medium", "crf": 23, "maxrate": "3500k", "bufsize": "5000k"},
        {"resolution": "854x480", "bitrate": "1000k", "profile": "main", "level": "3.1",
         "preset": "fast", "crf": 25, "maxrate": "1500k", "bufsize": "2000k"},
        {"resolution": "640x360", "bitrate": "600k", "profile": "main", "level": "3.0",
         "preset": "fast", "crf": 27, "maxrate": "900k", "bufsize": "1200k"},
        {"resolution": "256x144", "bitrate": "200k", "profile": "baseline", "level": "1.3",
         "preset": "fast", "crf": 30, "maxrate": "300k", "bufsize": "400k"},
    ],
    "vp9": [
        {"resolution": "3840x2160", "bitrate": "12000k", "crf": 24, "speed": 1,
         "tile_columns": 4, "threads": 16, "row_mt": 1},
        {"resolution": "1920x1080", "bitrate": "3000k", "crf": 28, "speed": 2,
         "tile_columns": 2, "threads": 8, "row_mt": 1},
        {"resolution": "1280x720", "bitrate": "1800k", "crf": 30, "speed": 2,
         "tile_columns": 2, "threads": 4, "row_mt": 1},
    ],
    "av1": [
        {"resolution": "3840x2160", "bitrate": "8000k", "crf": 25, "cpu_used": 4,
         "tile_columns": 4, "tile_rows": 2, "threads": 16},
        {"resolution": "1920x1080", "bitrate": "2500k", "crf": 28, "cpu_used": 5,
         "tile_columns": 2, "tile_rows": 1, "threads": 8},
    ]
}

def generate_ffmpeg_command(input_path: str, profile: dict, codec: str, segment_duration: int = 4) -> str:
    """Generate FFmpeg command for a single encoding profile."""
    if codec == "h264":
        return (
            f"ffmpeg -i {input_path} "
            f"-c:v libx264 -preset {profile['preset']} -crf {profile['crf']} "
            f"-profile:v {profile['profile']} -level {profile['level']} "
            f"-maxrate {profile['maxrate']} -bufsize {profile['bufsize']} "
            f"-vf scale={profile['resolution']} "
            f"-c:a aac -b:a 128k -ac 2 "
            f"-f hls -hls_time {segment_duration} -hls_list_size 0 "
            f"-hls_segment_filename 'segment_%04d.ts' "
            f"output.m3u8"
        )
    elif codec == "vp9":
        return (
            f"ffmpeg -i {input_path} "
            f"-c:v libvpx-vp9 -b:v {profile['bitrate']} -crf {profile['crf']} "
            f"-speed {profile['speed']} -tile-columns {profile['tile_columns']} "
            f"-threads {profile['threads']} -row-mt {profile['row_mt']} "
            f"-vf scale={profile['resolution']} "
            f"-c:a libopus -b:a 128k "
            f"-f dash -seg_duration {segment_duration} "
            f"output.mpd"
        )
    elif codec == "av1":
        return (
            f"ffmpeg -i {input_path} "
            f"-c:v libaom-av1 -b:v {profile['bitrate']} -crf {profile['crf']} "
            f"-cpu-used {profile['cpu_used']} "
            f"-tile-columns {profile['tile_columns']} -tile-rows {profile['tile_rows']} "
            f"-threads {profile['threads']} "
            f"-vf scale={profile['resolution']} "
            f"-c:a libopus -b:a 128k "
            f"-f dash -seg_duration {segment_duration} "
            f"output.mpd"
        )
```

### Transcoding Orchestrator (Kubernetes Job)
```python
# transcoding_orchestrator.py
import asyncio
from dataclasses import dataclass
from enum import Enum
from typing import List
import kubernetes_asyncio as k8s

class TranscodeStatus(Enum):
    PENDING = "pending"
    SPLITTING = "splitting"
    ENCODING = "encoding"
    CONCATENATING = "concatenating"
    PACKAGING = "packaging"
    COMPLETE = "complete"
    FAILED = "failed"

@dataclass
class TranscodeJob:
    video_id: str
    input_path: str
    output_prefix: str
    profiles: List[dict]
    priority: int  # 0=highest (premium creators), 5=lowest
    
class TranscodingOrchestrator:
    def __init__(self, k8s_client, kafka_producer, redis_client):
        self.k8s = k8s_client
        self.kafka = kafka_producer
        self.redis = redis_client
        
    async def process_video(self, job: TranscodeJob):
        """Main orchestration: split → parallel encode → concatenate → package."""
        try:
            # 1. Probe input to determine GOP structure
            probe = await self._probe_video(job.input_path)
            gop_size = probe['gop_size']
            duration = probe['duration']
            
            # 2. Split into GOP-aligned chunks (each ~10s)
            chunk_duration = max(gop_size * 4, 10)  # At least 4 GOPs per chunk
            num_chunks = int(duration / chunk_duration) + 1
            chunks = await self._split_video(job.input_path, chunk_duration, num_chunks)
            
            # 3. For each profile, submit parallel K8s jobs for all chunks
            encoding_tasks = []
            for profile in job.profiles:
                for chunk_idx, chunk_path in enumerate(chunks):
                    task = self._submit_encode_job(
                        video_id=job.video_id,
                        chunk_path=chunk_path,
                        chunk_idx=chunk_idx,
                        profile=profile,
                        priority=job.priority
                    )
                    encoding_tasks.append(task)
            
            # 4. Wait for all encoding jobs (with timeout)
            results = await asyncio.gather(*encoding_tasks, return_exceptions=True)
            failed = [r for r in results if isinstance(r, Exception)]
            if failed:
                raise TranscodeError(f"{len(failed)} chunks failed: {failed[0]}")
            
            # 5. Concatenate chunks per profile
            for profile in job.profiles:
                await self._concatenate_chunks(job.video_id, profile)
            
            # 6. Package into HLS/DASH with manifests
            manifest_urls = await self._package_streaming(job.video_id, job.profiles)
            
            # 7. Publish completion event
            await self.kafka.send('video-ready', {
                'video_id': job.video_id,
                'manifests': manifest_urls,
                'profiles': [p['resolution'] for p in job.profiles]
            })
            
        except Exception as e:
            await self._handle_failure(job, e)
    
    async def _submit_encode_job(self, video_id, chunk_path, chunk_idx, profile, priority):
        """Submit a Kubernetes Job for encoding one chunk at one quality level."""
        job_manifest = {
            "apiVersion": "batch/v1",
            "kind": "Job",
            "metadata": {
                "name": f"encode-{video_id}-{profile['resolution']}-{chunk_idx}",
                "labels": {"app": "transcoder", "video": video_id}
            },
            "spec": {
                "backoffLimit": 2,
                "activeDeadlineSeconds": 3600,
                "template": {
                    "spec": {
                        "priorityClassName": f"transcode-priority-{priority}",
                        "containers": [{
                            "name": "ffmpeg",
                            "image": "youtube/transcoder:latest",
                            "command": ["python", "encode_chunk.py"],
                            "env": [
                                {"name": "INPUT_PATH", "value": chunk_path},
                                {"name": "PROFILE", "value": str(profile)},
                                {"name": "OUTPUT_PATH", "value": f"s3://encoded/{video_id}/"},
                            ],
                            "resources": {
                                "requests": {"cpu": "4", "memory": "8Gi", "nvidia.com/gpu": "1"},
                                "limits": {"cpu": "8", "memory": "16Gi", "nvidia.com/gpu": "1"}
                            }
                        }],
                        "restartPolicy": "OnFailure",
                        "nodeSelector": {"workload": "transcode"}
                    }
                }
            }
        }
        await self.k8s.create_namespaced_job("transcoding", job_manifest)
```

## 8. Deep Dive: Recommendation System

### Architecture
```
┌────────────────────────────────────────────────────────────────────────┐
│                     RECOMMENDATION PIPELINE                             │
│                                                                        │
│  ┌─────────────┐    ┌──────────────┐    ┌────────────────────────┐   │
│  │  Candidate  │───▶│   Ranking    │───▶│  Re-ranking / Policy   │   │
│  │  Generation │    │   Model      │    │  (Diversity, Freshness)│   │
│  │  (~1000)    │    │  (~100)      │    │  (~20 final)           │   │
│  └─────────────┘    └──────────────┘    └────────────────────────┘   │
│        │                   │                       │                   │
│   Sources:            Deep Neural          Business Rules:             │
│   - Collaborative     Network with:       - No duplicate channels    │
│     filtering         - Watch time pred    - Mix content types        │
│   - Content-based     - Click pred         - Cap controversial        │
│   - Trending          - Engagement pred    - Boost subscriptions      │
│   - Subscriptions     - Satisfaction       - Freshness decay          │
│   - Search history                                                    │
└────────────────────────────────────────────────────────────────────────┘
```

### Candidate Generation (Two-Tower Model)
```python
# recommendation/candidate_generation.py
import tensorflow as tf

class TwoTowerModel(tf.keras.Model):
    """
    User tower encodes user features → user embedding
    Video tower encodes video features → video embedding
    Score = dot product of embeddings
    """
    def __init__(self, embedding_dim=256):
        super().__init__()
        self.embedding_dim = embedding_dim
        
        # User tower
        self.user_watch_embedding = tf.keras.layers.Embedding(50_000_000, 64)  # video history
        self.user_search_embedding = tf.keras.layers.Embedding(1_000_000, 32)  # search terms
        self.user_dense = tf.keras.Sequential([
            tf.keras.layers.Dense(512, activation='relu'),
            tf.keras.layers.BatchNormalization(),
            tf.keras.layers.Dense(256, activation='relu'),
            tf.keras.layers.Dense(embedding_dim, activation=None),
            tf.keras.layers.Lambda(lambda x: tf.nn.l2_normalize(x, axis=1))
        ])
        
        # Video tower
        self.video_id_embedding = tf.keras.layers.Embedding(500_000_000, 64)
        self.channel_embedding = tf.keras.layers.Embedding(50_000_000, 32)
        self.category_embedding = tf.keras.layers.Embedding(100, 16)
        self.video_dense = tf.keras.Sequential([
            tf.keras.layers.Dense(512, activation='relu'),
            tf.keras.layers.BatchNormalization(),
            tf.keras.layers.Dense(256, activation='relu'),
            tf.keras.layers.Dense(embedding_dim, activation=None),
            tf.keras.layers.Lambda(lambda x: tf.nn.l2_normalize(x, axis=1))
        ])
    
    def call(self, inputs):
        user_features, video_features = inputs
        user_emb = self.user_tower(user_features)
        video_emb = self.video_tower(video_features)
        return tf.reduce_sum(user_emb * video_emb, axis=1)
    
    def user_tower(self, features):
        watch_hist = tf.reduce_mean(self.user_watch_embedding(features['watch_history']), axis=1)
        search_hist = tf.reduce_mean(self.user_search_embedding(features['search_history']), axis=1)
        demographics = features['demographics']  # age_bucket, gender, country
        combined = tf.concat([watch_hist, search_hist, demographics], axis=1)
        return self.user_dense(combined)
    
    def video_tower(self, features):
        vid_emb = self.video_id_embedding(features['video_id'])
        chan_emb = self.channel_embedding(features['channel_id'])
        cat_emb = self.category_embedding(features['category_id'])
        video_stats = features['stats']  # views, likes, freshness, duration
        combined = tf.concat([vid_emb, chan_emb, cat_emb, video_stats], axis=1)
        return self.video_dense(combined)


class CandidateRetrieval:
    """ANN-based retrieval using pre-computed video embeddings."""
    
    def __init__(self, model: TwoTowerModel, ann_index):
        self.model = model
        self.ann_index = ann_index  # ScaNN / FAISS index with 500M video embeddings
    
    def get_candidates(self, user_features: dict, num_candidates: int = 1000) -> list:
        user_embedding = self.model.user_tower(user_features)
        # ANN search: retrieve top-K nearest video embeddings
        video_ids, scores = self.ann_index.search(user_embedding.numpy(), k=num_candidates)
        return list(zip(video_ids, scores))
```

### Ranking Model (Deep Neural Network)
```python
# recommendation/ranking_model.py
class RankingModel(tf.keras.Model):
    """
    Multi-task model predicting:
    1. P(click) - will user click the thumbnail
    2. E(watch_time) - expected watch time
    3. P(like) - will user like
    4. P(share) - will user share
    5. Satisfaction score (composite)
    """
    def __init__(self):
        super().__init__()
        self.shared_layers = tf.keras.Sequential([
            tf.keras.layers.Dense(1024, activation='relu'),
            tf.keras.layers.Dropout(0.2),
            tf.keras.layers.Dense(512, activation='relu'),
            tf.keras.layers.Dropout(0.1),
            tf.keras.layers.Dense(256, activation='relu'),
        ])
        
        self.click_head = tf.keras.layers.Dense(1, activation='sigmoid', name='click')
        self.watch_time_head = tf.keras.layers.Dense(1, activation='relu', name='watch_time')
        self.like_head = tf.keras.layers.Dense(1, activation='sigmoid', name='like')
        self.share_head = tf.keras.layers.Dense(1, activation='sigmoid', name='share')
    
    def call(self, features):
        # Features: user embedding, video embedding, cross features, context
        x = self.shared_layers(features)
        return {
            'click': self.click_head(x),
            'watch_time': self.watch_time_head(x),
            'like': self.like_head(x),
            'share': self.share_head(x),
        }
    
    def compute_final_score(self, predictions: dict) -> float:
        """Weighted combination of predictions → final ranking score."""
        return (
            0.1 * predictions['click'] +
            0.5 * tf.math.log1p(predictions['watch_time']) +  # Emphasize watch time
            0.2 * predictions['like'] +
            0.2 * predictions['share']
        )
```

## 9. Deep Dive: CDN & Adaptive Bitrate Streaming

### CDN Architecture
```
┌─────────────────────────────────────────────────────────────────────┐
│  USER REQUEST: GET /video/abc123/segment_0042.ts                    │
└──────────────────────────────────┬──────────────────────────────────┘
                                   │
                    ┌──────────────▼──────────────┐
                    │     Edge PoP (City-level)    │   Cache Hit → Serve
                    │     SSD: 50TB, RAM: 512GB   │   immediately
                    │     Hit ratio: ~70%         │
                    └──────────────┬──────────────┘
                                   │ Cache Miss
                    ┌──────────────▼──────────────┐
                    │   Regional PoP (Country)     │   Cache Hit → Serve
                    │   SSD: 500TB                │   + fill edge
                    │   Hit ratio: ~90%           │
                    └──────────────┬──────────────┘
                                   │ Cache Miss
                    ┌──────────────▼──────────────┐
                    │   Origin Shield (Region)     │   Protect origin from
                    │   Cache: 5PB                │   thundering herd
                    └──────────────┬──────────────┘
                                   │ Cache Miss
                    ┌──────────────▼──────────────┐
                    │   Origin (GCS/S3)            │   Source of truth
                    │   Multi-region replicated   │
                    └─────────────────────────────┘
```

### Adaptive Bitrate Selection (Client-Side Algorithm)
```python
# player/abr_algorithm.py
class AdaptiveBitrateController:
    """
    Buffer-based ABR algorithm (similar to BBA from Netflix research).
    Selects quality based on buffer level and throughput estimation.
    """
    def __init__(self, available_bitrates: list):
        self.bitrates = sorted(available_bitrates)  # [200, 600, 1000, 2500, 4500, 8000, 15000]
        self.buffer_target = 30.0  # seconds
        self.buffer_min = 5.0
        self.throughput_history = []  # Last N segment download throughputs
        self.ewma_fast = 0  # Exponentially weighted moving average (fast)
        self.ewma_slow = 0  # EWMA (slow, more stable)
        
    def select_quality(self, buffer_level: float, last_throughput_kbps: float) -> int:
        """Select bitrate index based on buffer level and estimated throughput."""
        # Update throughput estimation (EWMA)
        alpha_fast, alpha_slow = 0.5, 0.1
        self.ewma_fast = alpha_fast * last_throughput_kbps + (1 - alpha_fast) * self.ewma_fast
        self.ewma_slow = alpha_slow * last_throughput_kbps + (1 - alpha_slow) * self.ewma_slow
        
        # Conservative throughput estimate (minimum of fast and slow EWMA)
        safe_throughput = min(self.ewma_fast, self.ewma_slow) * 0.85  # 15% safety margin
        
        # Buffer-based selection
        if buffer_level < self.buffer_min:
            # Emergency: pick lowest quality to refill buffer
            return 0
        elif buffer_level > self.buffer_target:
            # Comfortable: pick highest quality that fits throughput
            for i in range(len(self.bitrates) - 1, -1, -1):
                if self.bitrates[i] < safe_throughput:
                    return i
            return 0
        else:
            # Linear interpolation between min and max based on buffer level
            ratio = (buffer_level - self.buffer_min) / (self.buffer_target - self.buffer_min)
            max_allowed_idx = int(ratio * (len(self.bitrates) - 1))
            # Further constrain by throughput
            for i in range(max_allowed_idx, -1, -1):
                if self.bitrates[i] < safe_throughput:
                    return i
            return 0
```

## 10. Component Optimization

### Kafka Configuration (Event Streaming)
```yaml
# Video events topic (views, likes, comments)
video-events:
  partitions: 256
  replication_factor: 3
  retention_ms: 604800000  # 7 days
  segment_bytes: 1073741824  # 1GB
  compression_type: lz4
  min_insync_replicas: 2
  cleanup_policy: delete

# Upload completion events
upload-complete:
  partitions: 64
  replication_factor: 3
  retention_ms: 259200000  # 3 days
  max_message_bytes: 1048576

# Recommendation events (training data)
watch-events:
  partitions: 512
  replication_factor: 3
  retention_ms: 2592000000  # 30 days
  compression_type: zstd  # Better ratio for large volumes
```

### Redis Caching Strategy
```python
# Cache layers for video metadata
CACHE_CONFIG = {
    "video_metadata": {
        "prefix": "v:",
        "ttl": 3600,  # 1 hour
        "serialization": "msgpack",
        "strategy": "write-through",  # Update cache on writes
    },
    "view_counts": {
        "prefix": "vc:",
        "ttl": None,  # Persistent (counter)
        "strategy": "write-behind",  # Batch flush to Cassandra every 5s
        "batch_size": 1000,
    },
    "trending_videos": {
        "prefix": "trending:",
        "ttl": 300,  # 5 min refresh
        "data_structure": "sorted_set",  # ZREVRANGE for top-N
    },
    "user_subscriptions": {
        "prefix": "subs:",
        "ttl": 86400,
        "data_structure": "set",
    },
    "recommendation_cache": {
        "prefix": "rec:",
        "ttl": 900,  # 15 min (personalized, refresh frequently)
        "serialization": "protobuf",
    }
}
```

### Content ID System (Fingerprinting)
```python
# content_id/fingerprint.py
import numpy as np
from scipy.fft import fft

class AudioFingerprinter:
    """Chromaprint-like audio fingerprinting for Content ID."""
    
    def __init__(self, sample_rate=11025, frame_size=4096, overlap=2048):
        self.sample_rate = sample_rate
        self.frame_size = frame_size
        self.overlap = overlap
    
    def generate_fingerprint(self, audio_samples: np.ndarray) -> bytes:
        """Generate a compact fingerprint from audio samples."""
        # 1. Compute spectrogram
        hop = self.frame_size - self.overlap
        num_frames = (len(audio_samples) - self.frame_size) // hop
        
        fingerprint_bits = []
        for i in range(num_frames):
            frame = audio_samples[i * hop : i * hop + self.frame_size]
            # Apply Hanning window
            windowed = frame * np.hanning(self.frame_size)
            # FFT
            spectrum = np.abs(fft(windowed)[:self.frame_size // 2])
            
            # 2. Divide into frequency bands and compute energy
            bands = self._compute_band_energies(spectrum)
            
            # 3. Generate sub-fingerprint (32-bit hash per frame)
            bits = 0
            for j in range(len(bands) - 1):
                if bands[j] - bands[j+1] > 0:
                    bits |= (1 << j)
            fingerprint_bits.append(bits)
        
        return np.array(fingerprint_bits, dtype=np.uint32).tobytes()
    
    def _compute_band_energies(self, spectrum, num_bands=33):
        """Divide spectrum into logarithmically-spaced frequency bands."""
        band_edges = np.logspace(np.log10(300), np.log10(5000), num_bands + 1)
        freq_per_bin = self.sample_rate / self.frame_size
        energies = []
        for i in range(num_bands):
            low_bin = int(band_edges[i] / freq_per_bin)
            high_bin = int(band_edges[i+1] / freq_per_bin)
            energies.append(np.sum(spectrum[low_bin:high_bin] ** 2))
        return energies
    
    def match(self, query_fp: bytes, database_fps: dict, threshold=0.6) -> list:
        """Match query fingerprint against database using bit error rate."""
        query = np.frombuffer(query_fp, dtype=np.uint32)
        matches = []
        for video_id, db_fp in database_fps.items():
            db = np.frombuffer(db_fp, dtype=np.uint32)
            # Sliding window comparison
            best_score = 0
            for offset in range(0, len(db) - len(query), 10):
                segment = db[offset:offset + len(query)]
                # Hamming distance
                xor = np.bitwise_xor(query, segment)
                bit_errors = sum(bin(x).count('1') for x in xor)
                max_bits = len(query) * 32
                similarity = 1 - (bit_errors / max_bits)
                best_score = max(best_score, similarity)
            if best_score >= threshold:
                matches.append((video_id, best_score))
        return sorted(matches, key=lambda x: x[1], reverse=True)
```

## 11. Observability

### Key Metrics
```yaml
# Prometheus metrics
metrics:
  # Upload pipeline
  - video_upload_duration_seconds{resolution, codec}
  - video_transcode_duration_seconds{resolution, codec, priority}
  - video_transcode_queue_depth{priority}
  - video_processing_failures_total{stage, error_type}
  
  # Streaming
  - video_stream_requests_total{quality, device_type, region}
  - video_rebuffer_ratio{quality, cdn_pop}
  - video_startup_time_seconds{device_type, connection_type}
  - cdn_cache_hit_ratio{pop_level}  # edge, regional, origin
  - cdn_bandwidth_bytes_total{pop, direction}
  
  # Engagement
  - video_watch_time_seconds{category}
  - recommendation_ctr{position, source}
  - search_result_clicks{position}
  
  # Infrastructure
  - kafka_consumer_lag{topic, consumer_group}
  - redis_memory_usage_bytes{cluster}
  - db_query_duration_seconds{query_type, shard}

# Alerts
alerts:
  - name: HighRebufferRatio
    expr: video_rebuffer_ratio > 0.02
    for: 5m
    severity: critical
    
  - name: TranscodeQueueBacklog
    expr: video_transcode_queue_depth{priority="0"} > 100
    for: 10m
    severity: warning
    
  - name: CDNCacheHitDrop
    expr: cdn_cache_hit_ratio{pop_level="edge"} < 0.60
    for: 15m
    severity: warning
```

### Distributed Tracing
```
Upload Request Trace:
  [Client] ──upload──▶ [Upload Service] ──store──▶ [Object Storage]
                              │
                              ├──event──▶ [Kafka: upload-complete]
                              │                    │
                              │              [Transcoding Orchestrator]
                              │                    │
                              │              ┌─────┴─────┐
                              │         [Encode 1]  [Encode N]  (parallel)
                              │              └─────┬─────┘
                              │                    │
                              │              [Package HLS/DASH]
                              │                    │
                              │              [Content ID Scan]
                              │                    │
                              │              [Publish to CDN]
                              │                    │
                              └── webhook ──▶ [Notify Creator: "Video Live"]
```

## 12. Key Considerations & Trade-offs

| Decision | Choice | Trade-off |
|----------|--------|-----------|
| Storage for videos | Object storage (GCS/S3) | Cost-effective for large blobs; no random access |
| View count accuracy | Eventually consistent (Kafka → batch) | Real-time count ±5% acceptable for scale |
| Transcoding priority | Premium creators first | UX for small creators delayed; mitigate with queue SLAs |
| CDN strategy | Own PoPs + third-party (Akamai) | Capex for own; flexibility with hybrid |
| Recommendation freshness | 15-min cache + real-time signals | Slightly stale but orders of magnitude less compute |
| Comment storage | Sharded MySQL (Vitess) | Good for threaded reads; fan-out for moderation |
| Live streaming | Separate pipeline (lower latency path) | Duplication of some infra; justified by different SLAs |
| AV1 vs VP9 vs H.264 | Serve newest codec device supports | Encoding cost ↑ 10x for AV1; bandwidth savings 30-50% |
| Thumbnail generation | AI-selected best frames | Compute cost; significantly improves CTR |

### Sharding Strategy
- **Videos**: Hash on `video_id` (uniform distribution, no hotspots)
- **Comments**: Hash on `video_id` (co-locate comments with video for efficient reads)
- **Watch History**: Hash on `user_id` (user-centric queries)
- **Subscriptions**: Hash on `user_id` (fan-out on write for notifications)

### Failure Modes & Mitigations
1. **Transcoding failure**: Retry with exponential backoff; dead-letter queue after 3 attempts; alert on-call
2. **CDN origin overload**: Origin shield caching; request coalescing; circuit breaker
3. **Recommendation service down**: Fall back to trending/popular videos (pre-computed)
4. **Database shard failure**: Read replicas auto-promote; cross-region failover in <30s
5. **Kafka broker loss**: ISR ensures no data loss; consumers rebalance automatically
