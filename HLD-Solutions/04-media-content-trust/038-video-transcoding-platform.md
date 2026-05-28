# Video Transcoding Platform - System Design

## 1. Requirements

### 1.1 Functional Requirements
- Accept 100+ input formats (H.264, H.265, VP9, AV1, ProRes, DNxHD, MPEG-2, etc.)
- Multiple output profiles: resolutions (4K/1080p/720p/480p/360p), codecs (H.264/H.265/VP9/AV1), containers (MP4/HLS/DASH/WebM)
- Parallel chunk-based processing with GOP-aligned splitting
- Quality metrics: VMAF, SSIM, PSNR per output
- DRM packaging: Widevine, FairPlay, PlayReady (CENC/CBCS)
- Priority queues (premium/standard/bulk)
- Webhook callbacks on job state transitions
- Per-title encoding optimization with ABR ladder generation
- Job cancellation and retry with idempotency

### 1.2 Non-Functional Requirements
- 99.9% job completion rate (jobs that enter must finish or fail definitively)
- Transcode speed ≥ 2x realtime for H.264 1080p baseline
- Support 100K concurrent jobs across all priority tiers
- Cost optimization via spot/preemptible instances
- Horizontal scalability with no single point of failure
- Exactly-once processing semantics for billing accuracy

---

## 2. Capacity Estimation

### 2.1 Traffic
- 100K concurrent jobs, average job duration = 10 minutes
- Peak submission rate: 100K / 10 min = 10K jobs/min = ~167 jobs/sec
- Average input file: 2GB (1080p, 60 min content)
- Average outputs per job: 6 renditions × 1.5GB avg = 9GB output per job

### 2.2 Storage
- Daily input: 167 jobs/sec × 86400 × 2GB = ~28 PB/day (input is transient, deleted after 24h)
- Daily output: ~28 PB × 4.5 ratio = ~126 PB/day stored long-term
- Hot storage (7 days): ~900 PB → tiered to cold after 30 days

### 2.3 Compute
- 1 hour of 1080p H.264 at 2x realtime = 30 min on 1 GPU
- With chunk-based parallelism (10 chunks): 3 min wall-clock per rendition
- 100K concurrent × 6 renditions = 600K rendition tasks
- GPU fleet: ~60K GPUs at peak (with spot instances, 3:1 spot-to-ondemand ratio)

### 2.4 Network
- Ingress: 167 jobs/sec × 2GB = 334 GB/sec peak ingress
- Egress to S3: 167 × 9GB = 1.5 TB/sec inter-AZ traffic
- Worker ↔ S3 bandwidth: each worker needs ~500 Mbps sustained

---

## 3. Data Modeling

### 3.1 PostgreSQL - Job Metadata

```sql
-- Jobs table: source of truth for job lifecycle
CREATE TABLE transcode_jobs (
    job_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL,
    priority        SMALLINT NOT NULL DEFAULT 2, -- 1=premium, 2=standard, 3=bulk
    status          VARCHAR(20) NOT NULL DEFAULT 'pending',
    -- pending, splitting, transcoding, merging, packaging, complete, failed, cancelled
    input_uri       TEXT NOT NULL,
    input_format    VARCHAR(50),
    input_duration_ms BIGINT,
    input_resolution VARCHAR(20),
    input_codec     VARCHAR(50),
    output_profiles JSONB NOT NULL, -- array of desired output specs
    webhook_url     TEXT,
    webhook_secret  VARCHAR(256),
    drm_config      JSONB, -- {widevine: bool, fairplay: bool, playready: bool, key_id: ...}
    metadata        JSONB DEFAULT '{}',
    retry_count     SMALLINT DEFAULT 0,
    max_retries     SMALLINT DEFAULT 3,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    error_message   TEXT,
    idempotency_key VARCHAR(256) UNIQUE,
    CONSTRAINT valid_status CHECK (status IN ('pending','splitting','transcoding','merging','packaging','complete','failed','cancelled'))
);

CREATE INDEX idx_jobs_tenant_status ON transcode_jobs(tenant_id, status);
CREATE INDEX idx_jobs_priority_created ON transcode_jobs(priority, created_at) WHERE status = 'pending';
CREATE INDEX idx_jobs_status ON transcode_jobs(status) WHERE status NOT IN ('complete','failed','cancelled');

-- Output renditions
CREATE TABLE job_renditions (
    rendition_id    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id          UUID NOT NULL REFERENCES transcode_jobs(job_id),
    profile_name    VARCHAR(100) NOT NULL,
    codec           VARCHAR(20) NOT NULL,
    container       VARCHAR(20) NOT NULL,
    resolution      VARCHAR(20) NOT NULL,
    bitrate_kbps    INTEGER,
    framerate       DECIMAL(5,2),
    status          VARCHAR(20) NOT NULL DEFAULT 'pending',
    output_uri      TEXT,
    output_size_bytes BIGINT,
    vmaf_score      DECIMAL(5,2),
    ssim_score      DECIMAL(7,5),
    psnr_score      DECIMAL(6,2),
    duration_ms     BIGINT,
    processing_time_ms BIGINT,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    completed_at    TIMESTAMPTZ
);

CREATE INDEX idx_renditions_job ON job_renditions(job_id);
CREATE INDEX idx_renditions_status ON job_renditions(status) WHERE status != 'complete';

-- Chunks for parallel processing
CREATE TABLE job_chunks (
    chunk_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id          UUID NOT NULL REFERENCES transcode_jobs(job_id),
    rendition_id    UUID NOT NULL REFERENCES job_renditions(rendition_id),
    chunk_index     INTEGER NOT NULL,
    total_chunks    INTEGER NOT NULL,
    start_time_ms   BIGINT NOT NULL,
    end_time_ms     BIGINT NOT NULL,
    status          VARCHAR(20) NOT NULL DEFAULT 'pending',
    worker_id       VARCHAR(100),
    input_chunk_uri TEXT,
    output_chunk_uri TEXT,
    assigned_at     TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    UNIQUE(rendition_id, chunk_index)
);

CREATE INDEX idx_chunks_rendition_status ON job_chunks(rendition_id, status);
CREATE INDEX idx_chunks_worker ON job_chunks(worker_id) WHERE status = 'processing';

-- Per-title encoding analysis results
CREATE TABLE encoding_analysis (
    analysis_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id          UUID NOT NULL REFERENCES transcode_jobs(job_id),
    content_complexity DECIMAL(5,2), -- spatial + temporal complexity score
    optimal_ladder  JSONB NOT NULL, -- [{resolution, bitrate, vmaf_target}, ...]
    convex_hull     JSONB, -- bitrate-quality points
    analysis_time_ms BIGINT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
```

### 3.2 Redis - Job State & Coordination

```redis
# Job state machine (fast reads for status polling)
HSET job:{job_id} status "transcoding" progress 45 chunks_done 5 chunks_total 10

# Priority queues (sorted sets by timestamp for FIFO within priority)
ZADD queue:priority:1 {timestamp} {job_id}  # premium
ZADD queue:priority:2 {timestamp} {job_id}  # standard
ZADD queue:priority:3 {timestamp} {job_id}  # bulk

# Worker heartbeats
HSET worker:{worker_id} last_heartbeat {ts} current_job {job_id} gpu_util 85

# Rate limiting per tenant
INCR ratelimit:{tenant_id}:{window}
EXPIRE ratelimit:{tenant_id}:{window} 60

# Distributed locks for chunk merge coordination
SET lock:merge:{rendition_id} {worker_id} NX EX 300
```

### 3.3 S3 - Storage Layout

```
s3://transcoding-input/{tenant_id}/{job_id}/source.{ext}
s3://transcoding-chunks/{job_id}/{rendition_id}/chunk_{index:04d}.{ext}
s3://transcoding-output/{tenant_id}/{job_id}/{profile_name}/
    manifest.mpd          # DASH manifest
    master.m3u8           # HLS master playlist
    segment_000001.m4s    # media segments
    init.mp4              # initialization segment
s3://transcoding-metrics/{job_id}/{rendition_id}/vmaf_per_frame.json
```

---

## 4. High-Level Design

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          CLIENT / CONTENT PROVIDER                           │
└─────────────────┬───────────────────────────────────────┬───────────────────┘
                  │ Submit Job                             │ Poll Status
                  ▼                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           API GATEWAY (Kong/Envoy)                           │
│                    Rate Limiting │ Auth │ Request Routing                    │
└─────────────────┬───────────────────────────────────────┬───────────────────┘
                  │                                       │
                  ▼                                       ▼
┌──────────────────────────┐              ┌──────────────────────────────────┐
│     JOB SUBMISSION SVC   │              │        STATUS SERVICE            │
│  - Validate input        │              │  - Read from Redis (hot)         │
│  - Store in PostgreSQL   │              │  - Fallback to PostgreSQL        │
│  - Enqueue to Kafka      │              │  - WebSocket for live updates    │
│  - Return job_id         │              └──────────────────────────────────┘
└──────────┬───────────────┘
           │
           ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                         KAFKA CLUSTER (Job Events)                            │
│  Topics: job.submitted, job.split, chunk.ready, chunk.done,                  │
│          rendition.merge, job.complete, job.failed, webhook.send              │
│  Partitions: 256 per topic, keyed by job_id                                  │
└──────┬─────────────┬──────────────┬─────────────────┬────────────────────────┘
       │             │              │                 │
       ▼             ▼              ▼                 ▼
┌────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────────────┐
│  SPLITTER  │ │   WORKER     │ │   MERGER     │ │  DRM PACKAGER        │
│  SERVICE   │ │   FLEET      │ │   SERVICE    │ │  - Shaka Packager    │
│            │ │              │ │              │ │  - Widevine/FairPlay  │
│ - Probe    │ │ - GPU nodes  │ │ - Concat     │ │  - PlayReady         │
│ - GOP align│ │ - FFmpeg     │ │ - Validate   │ │  - CENC/CBCS         │
│ - Split    │ │ - x264/x265  │ │ - Quality    │ └──────────┬───────────┘
│ - Fan-out  │ │ - SVT-AV1   │ │   metrics    │            │
└────────────┘ │ - libvpx    │ └──────────────┘            ▼
               │ - NVENC     │              ┌──────────────────────────────┐
               └──────────────┘              │     WEBHOOK NOTIFIER         │
                                            │  - Exponential backoff retry  │
       ┌────────────────────────────────────│  - Dead letter queue          │
       │          S3 STORAGE                └──────────────────────────────┘
       │  ┌───────────┬───────────┐
       │  │  Input    │  Output   │
       │  │  Bucket   │  Bucket   │
       │  └───────────┴───────────┘
       │
       ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                      AUTOSCALER (Custom Controller)                           │
│  - Monitor Kafka consumer lag per priority                                   │
│  - Scale GPU fleet: spot instances first, on-demand fallback                 │
│  - Scale splitter/merger based on queue depth                                │
│  - Predictive scaling based on historical submission patterns                │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 5. Low-Level Design - APIs

### 5.1 Submit Transcoding Job

```
POST /v1/jobs
Authorization: Bearer {token}
Idempotency-Key: {uuid}
Content-Type: application/json

{
  "input": {
    "uri": "s3://customer-bucket/video.mov",
    "credentials": {"role_arn": "arn:aws:iam::123:role/transcoding-access"}
  },
  "profiles": [
    {
      "name": "h264_1080p",
      "codec": "h264",
      "resolution": "1920x1080",
      "bitrate_kbps": 5000,
      "container": "mp4",
      "framerate": 30
    },
    {
      "name": "h265_4k",
      "codec": "h265",
      "resolution": "3840x2160",
      "bitrate_kbps": 15000,
      "container": "fmp4",
      "framerate": 60
    },
    {
      "name": "adaptive_hls",
      "codec": "h264",
      "container": "hls",
      "adaptive": true,
      "per_title_optimization": true
    }
  ],
  "drm": {
    "widevine": true,
    "fairplay": true,
    "playready": false,
    "key_server_url": "https://keys.example.com/v1/keys"
  },
  "priority": 1,
  "webhook": {
    "url": "https://customer.com/webhooks/transcode",
    "secret": "whsec_...",
    "events": ["job.started", "job.progress", "job.complete", "job.failed"]
  },
  "metadata": {"content_id": "movie-123", "title": "Example Movie"}
}

Response 202:
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "estimated_completion": "2024-01-15T10:30:00Z",
  "links": {
    "self": "/v1/jobs/550e8400-e29b-41d4-a716-446655440000",
    "cancel": "/v1/jobs/550e8400-e29b-41d4-a716-446655440000/cancel"
  }
}
```

### 5.2 Get Job Status

```
GET /v1/jobs/{job_id}
Authorization: Bearer {token}

Response 200:
{
  "job_id": "550e8400-...",
  "status": "transcoding",
  "progress": {
    "overall_percent": 65,
    "renditions": [
      {"name": "h264_1080p", "status": "complete", "progress": 100},
      {"name": "h265_4k", "status": "transcoding", "progress": 45},
      {"name": "adaptive_hls", "status": "transcoding", "progress": 50}
    ]
  },
  "quality_metrics": {
    "h264_1080p": {"vmaf": 93.2, "ssim": 0.9812, "psnr": 42.1}
  },
  "timing": {
    "submitted_at": "2024-01-15T10:00:00Z",
    "started_at": "2024-01-15T10:00:05Z",
    "estimated_completion": "2024-01-15T10:08:00Z"
  }
}
```

### 5.3 Cancel Job

```
POST /v1/jobs/{job_id}/cancel
Authorization: Bearer {token}

Response 200:
{
  "job_id": "550e8400-...",
  "status": "cancelled",
  "chunks_cancelled": 15,
  "chunks_already_complete": 5
}
```

### 5.4 List Job Outputs

```
GET /v1/jobs/{job_id}/outputs
Authorization: Bearer {token}

Response 200:
{
  "outputs": [
    {
      "profile": "h264_1080p",
      "uri": "s3://output/tenant/job/h264_1080p/output.mp4",
      "size_bytes": 1073741824,
      "duration_ms": 3600000,
      "quality": {"vmaf": 93.2, "ssim": 0.9812, "psnr": 42.1},
      "signed_url": "https://cdn.example.com/...",
      "signed_url_expires": "2024-01-15T11:00:00Z"
    }
  ]
}
```

---

## 6. Deep Dive: Chunk-Based Parallel Transcoding

### 6.1 GOP-Aligned Splitting Algorithm

```python
import subprocess
import json
from dataclasses import dataclass
from typing import List

@dataclass
class Chunk:
    index: int
    start_time_ms: int
    end_time_ms: int
    start_byte: int  # for byte-range extraction
    end_byte: int
    keyframe_pts: int

def probe_keyframes(input_uri: str) -> List[int]:
    """Extract all keyframe positions using ffprobe."""
    cmd = [
        'ffprobe', '-v', 'quiet',
        '-select_streams', 'v:0',
        '-show_entries', 'packet=pts_time,flags',
        '-of', 'json',
        input_uri
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    packets = json.loads(result.stdout)['packets']
    
    keyframes = []
    for pkt in packets:
        if 'K' in pkt.get('flags', ''):
            keyframes.append(int(float(pkt['pts_time']) * 1000))
    return keyframes

def compute_gop_aligned_chunks(
    keyframes: List[int],
    duration_ms: int,
    target_chunk_duration_ms: int = 30000,  # 30 seconds default
    min_chunk_duration_ms: int = 10000,
    max_chunk_duration_ms: int = 60000
) -> List[Chunk]:
    """
    Split video into chunks aligned to GOP boundaries.
    
    Strategy:
    1. Target N chunks where each is ~target_chunk_duration
    2. Snap chunk boundaries to nearest keyframe
    3. Ensure no chunk is too small (merge with neighbor) or too large (split at next keyframe)
    """
    if not keyframes:
        # Fallback: single chunk for keyframe-less content
        return [Chunk(index=0, start_time_ms=0, end_time_ms=duration_ms,
                      start_byte=0, end_byte=-1, keyframe_pts=0)]
    
    num_chunks = max(1, duration_ms // target_chunk_duration_ms)
    ideal_chunk_size = duration_ms / num_chunks
    
    chunks = []
    chunk_start = 0
    chunk_index = 0
    
    for i in range(1, num_chunks):
        ideal_boundary = int(i * ideal_chunk_size)
        
        # Find nearest keyframe to ideal boundary
        nearest_kf = min(keyframes, key=lambda kf: abs(kf - ideal_boundary))
        
        # Validate chunk size constraints
        chunk_duration = nearest_kf - chunk_start
        if chunk_duration < min_chunk_duration_ms:
            continue  # Skip this boundary, merge with next chunk
        if chunk_duration > max_chunk_duration_ms:
            # Find intermediate keyframe
            candidates = [kf for kf in keyframes 
                         if chunk_start < kf < nearest_kf]
            if candidates:
                nearest_kf = candidates[len(candidates) // 2]
        
        chunks.append(Chunk(
            index=chunk_index,
            start_time_ms=chunk_start,
            end_time_ms=nearest_kf,
            start_byte=0, end_byte=0,  # Computed separately
            keyframe_pts=nearest_kf
        ))
        chunk_start = nearest_kf
        chunk_index += 1
    
    # Final chunk
    chunks.append(Chunk(
        index=chunk_index,
        start_time_ms=chunk_start,
        end_time_ms=duration_ms,
        start_byte=0, end_byte=0,
        keyframe_pts=chunk_start
    ))
    
    return chunks

def extract_chunk(input_uri: str, chunk: Chunk, output_uri: str) -> str:
    """Extract a chunk using stream copy (fast, no re-encode)."""
    cmd = [
        'ffmpeg', '-y',
        '-ss', str(chunk.start_time_ms / 1000.0),
        '-to', str(chunk.end_time_ms / 1000.0),
        '-i', input_uri,
        '-c', 'copy',
        '-avoid_negative_ts', 'make_zero',
        '-movflags', '+faststart',
        output_uri
    ]
    subprocess.run(cmd, check=True)
    return output_uri
```

### 6.2 Fan-Out Worker Processing

```python
from kafka import KafkaProducer, KafkaConsumer
import json

class ChunkDispatcher:
    """Dispatches chunks to workers via Kafka with priority-aware routing."""
    
    def __init__(self):
        self.producer = KafkaProducer(
            bootstrap_servers=['kafka-1:9092', 'kafka-2:9092', 'kafka-3:9092'],
            value_serializer=lambda v: json.dumps(v).encode(),
            key_serializer=lambda k: k.encode(),
            acks='all',
            retries=3,
            max_in_flight_requests_per_connection=1  # ordering guarantee
        )
    
    def dispatch_chunks(self, job_id: str, rendition_id: str, 
                       chunks: list, profile: dict, priority: int):
        """Fan-out chunks to Kafka topic partitioned by job_id."""
        topic = f'chunks.priority.{priority}'
        
        for chunk in chunks:
            message = {
                'job_id': job_id,
                'rendition_id': rendition_id,
                'chunk_index': chunk.index,
                'total_chunks': len(chunks),
                'input_chunk_uri': f's3://chunks/{job_id}/{rendition_id}/input_{chunk.index:04d}.mp4',
                'output_chunk_uri': f's3://chunks/{job_id}/{rendition_id}/output_{chunk.index:04d}.mp4',
                'profile': profile,
                'start_time_ms': chunk.start_time_ms,
                'end_time_ms': chunk.end_time_ms,
            }
            self.producer.send(
                topic=topic,
                key=job_id,  # All chunks of same job to same partition
                value=message
            )
        self.producer.flush()


class TranscodeWorker:
    """GPU/CPU worker that processes individual chunks."""
    
    def __init__(self, worker_id: str):
        self.worker_id = worker_id
        self.consumer = KafkaConsumer(
            'chunks.priority.1', 'chunks.priority.2', 'chunks.priority.3',
            group_id='transcode-workers',
            bootstrap_servers=['kafka-1:9092', 'kafka-2:9092', 'kafka-3:9092'],
            value_deserializer=lambda v: json.loads(v.decode()),
            max_poll_records=1,  # Process one chunk at a time
            session_timeout_ms=300000,  # 5 min timeout for long transcodes
        )
    
    def process_chunk(self, message: dict):
        """Transcode a single chunk according to profile."""
        profile = message['profile']
        
        # Build FFmpeg command based on profile
        cmd = self._build_ffmpeg_cmd(
            input_uri=message['input_chunk_uri'],
            output_uri=message['output_chunk_uri'],
            profile=profile
        )
        
        # Execute transcode
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise TranscodeError(result.stderr)
        
        # Compute quality metrics on output
        metrics = self._compute_quality_metrics(
            original=message['input_chunk_uri'],
            transcoded=message['output_chunk_uri']
        )
        
        return {
            'chunk_index': message['chunk_index'],
            'output_uri': message['output_chunk_uri'],
            'metrics': metrics
        }
    
    def _build_ffmpeg_cmd(self, input_uri: str, output_uri: str, profile: dict) -> list:
        cmd = ['ffmpeg', '-y', '-i', input_uri]
        
        codec = profile['codec']
        if codec == 'h264':
            cmd += ['-c:v', 'libx264', '-preset', 'medium',
                    '-b:v', f"{profile['bitrate_kbps']}k",
                    '-maxrate', f"{int(profile['bitrate_kbps'] * 1.5)}k",
                    '-bufsize', f"{profile['bitrate_kbps'] * 2}k"]
        elif codec == 'h265':
            cmd += ['-c:v', 'libx265', '-preset', 'medium',
                    '-b:v', f"{profile['bitrate_kbps']}k",
                    '-tag:v', 'hvc1']
        elif codec == 'av1':
            cmd += ['-c:v', 'libsvtav1', '-preset', '6',
                    '-b:v', f"{profile['bitrate_kbps']}k",
                    '-svtav1-params', 'tune=0']
        elif codec == 'vp9':
            cmd += ['-c:v', 'libvpx-vp9', '-b:v', f"{profile['bitrate_kbps']}k",
                    '-quality', 'good', '-speed', '2']
        
        # Resolution scaling
        if 'resolution' in profile:
            w, h = profile['resolution'].split('x')
            cmd += ['-vf', f'scale={w}:{h}:flags=lanczos']
        
        cmd += ['-c:a', 'aac', '-b:a', '128k', output_uri]
        return cmd
    
    def _compute_quality_metrics(self, original: str, transcoded: str) -> dict:
        """Compute VMAF/SSIM/PSNR using ffmpeg libvmaf filter."""
        cmd = [
            'ffmpeg', '-i', transcoded, '-i', original,
            '-lavfi', 'libvmaf=model=version=vmaf_v0.6.1:log_fmt=json:log_path=/tmp/vmaf.json:feature=name=psnr|name=float_ssim',
            '-f', 'null', '-'
        ]
        subprocess.run(cmd, check=True)
        
        with open('/tmp/vmaf.json') as f:
            vmaf_data = json.load(f)
        
        return {
            'vmaf': vmaf_data['pooled_metrics']['vmaf']['mean'],
            'psnr': vmaf_data['pooled_metrics']['psnr_y']['mean'],
            'ssim': vmaf_data['pooled_metrics']['float_ssim']['mean'],
        }
```

### 6.3 Ordered Merge with VBR Handling

```python
class ChunkMerger:
    """Merges transcoded chunks back into final output maintaining order."""
    
    def __init__(self, redis_client, s3_client):
        self.redis = redis_client
        self.s3 = s3_client
    
    def on_chunk_complete(self, job_id: str, rendition_id: str, 
                          chunk_index: int, total_chunks: int):
        """Called when a chunk finishes. Triggers merge when all chunks done."""
        # Atomic increment of completed chunk counter
        done = self.redis.hincrby(f'rendition:{rendition_id}', 'chunks_done', 1)
        
        if done == total_chunks:
            # Acquire merge lock (prevent duplicate merges)
            lock_acquired = self.redis.set(
                f'lock:merge:{rendition_id}', 'locked',
                nx=True, ex=600
            )
            if lock_acquired:
                self._execute_merge(job_id, rendition_id, total_chunks)
    
    def _execute_merge(self, job_id: str, rendition_id: str, total_chunks: int):
        """Concatenate chunks in order using FFmpeg concat demuxer."""
        # Generate concat file
        concat_list = ""
        for i in range(total_chunks):
            chunk_uri = f's3://chunks/{job_id}/{rendition_id}/output_{i:04d}.mp4'
            # Download to local or use s3 FUSE mount
            local_path = f'/tmp/merge/{rendition_id}/chunk_{i:04d}.mp4'
            self.s3.download_file(chunk_uri, local_path)
            concat_list += f"file '{local_path}'\n"
        
        concat_file = f'/tmp/merge/{rendition_id}/concat.txt'
        with open(concat_file, 'w') as f:
            f.write(concat_list)
        
        output_path = f'/tmp/merge/{rendition_id}/final.mp4'
        
        # Use concat demuxer for lossless merge
        cmd = [
            'ffmpeg', '-y',
            '-f', 'concat', '-safe', '0',
            '-i', concat_file,
            '-c', 'copy',  # No re-encode, just concatenate
            '-movflags', '+faststart',
            output_path
        ]
        subprocess.run(cmd, check=True)
        
        # Validate output duration matches expected
        self._validate_output(output_path, job_id, rendition_id)
        
        # Upload final output
        final_uri = f's3://output/{job_id}/{rendition_id}/output.mp4'
        self.s3.upload_file(output_path, final_uri)
        
        # Cleanup chunks
        self._cleanup_chunks(job_id, rendition_id, total_chunks)
    
    def _validate_output(self, path: str, job_id: str, rendition_id: str):
        """Validate merged output for continuity issues."""
        # Check for timestamp discontinuities
        cmd = ['ffprobe', '-v', 'error', '-show_entries', 
               'format=duration', '-of', 'json', path]
        result = subprocess.run(cmd, capture_output=True, text=True)
        actual_duration = float(json.loads(result.stdout)['format']['duration'])
        
        expected_duration = self.redis.hget(f'rendition:{rendition_id}', 'expected_duration')
        tolerance = 0.5  # 500ms tolerance
        
        if abs(actual_duration - float(expected_duration)) > tolerance:
            raise MergeValidationError(
                f"Duration mismatch: expected {expected_duration}s, got {actual_duration}s"
            )
```

---

## 7. Deep Dive: Per-Title Encoding Optimization

### 7.1 Convex Hull Bitrate-Quality Analysis

```python
import numpy as np
from scipy.spatial import ConvexHull
from dataclasses import dataclass
from typing import List, Tuple

@dataclass
class EncodingPoint:
    resolution: str
    bitrate_kbps: int
    vmaf: float
    encode_time_s: float

@dataclass 
class ABRLadderRung:
    resolution: str
    bitrate_kbps: int
    target_vmaf: float
    codec: str

class PerTitleOptimizer:
    """
    Implements Netflix-style per-title encoding optimization.
    
    For each title, we:
    1. Encode short representative segments at multiple bitrate-resolution combos
    2. Measure VMAF for each point
    3. Compute convex hull of bitrate-vs-quality curve
    4. Select optimal ABR ladder from hull points
    """
    
    # Standard test matrix
    RESOLUTIONS = ['3840x2160', '1920x1080', '1280x720', '960x540', '640x360']
    BITRATES = [500, 1000, 1500, 2000, 3000, 4000, 6000, 8000, 12000, 16000, 20000]
    
    def __init__(self, sample_duration_s: int = 10, num_samples: int = 3):
        self.sample_duration_s = sample_duration_s
        self.num_samples = num_samples
    
    def analyze(self, input_uri: str) -> List[ABRLadderRung]:
        """Run full per-title analysis and return optimal ABR ladder."""
        # Step 1: Extract representative samples
        samples = self._extract_samples(input_uri)
        
        # Step 2: Encode all resolution×bitrate combinations
        encoding_points = []
        for resolution in self.RESOLUTIONS:
            for bitrate in self.BITRATES:
                # Skip impossible combinations (4K at 500kbps)
                if not self._is_valid_combo(resolution, bitrate):
                    continue
                
                avg_vmaf = self._encode_and_measure(samples, resolution, bitrate)
                encoding_points.append(EncodingPoint(
                    resolution=resolution,
                    bitrate_kbps=bitrate,
                    vmaf=avg_vmaf,
                    encode_time_s=0
                ))
        
        # Step 3: Compute convex hull
        hull_points = self._compute_convex_hull(encoding_points)
        
        # Step 4: Select ladder rungs from hull
        ladder = self._select_ladder(hull_points)
        
        return ladder
    
    def _compute_convex_hull(self, points: List[EncodingPoint]) -> List[EncodingPoint]:
        """
        Compute upper convex hull of bitrate-VMAF points.
        Points on the hull represent Pareto-optimal encoding settings.
        """
        if len(points) < 3:
            return points
        
        # Convert to numpy array [bitrate, vmaf]
        coords = np.array([[p.bitrate_kbps, p.vmaf] for p in points])
        
        # Compute convex hull
        hull = ConvexHull(coords)
        
        # Extract upper hull (we want max VMAF for given bitrate)
        hull_points = []
        for idx in hull.vertices:
            hull_points.append(points[idx])
        
        # Filter to only upper hull (increasing VMAF with increasing bitrate)
        hull_points.sort(key=lambda p: p.bitrate_kbps)
        upper_hull = [hull_points[0]]
        for p in hull_points[1:]:
            if p.vmaf >= upper_hull[-1].vmaf:
                upper_hull.append(p)
        
        return upper_hull
    
    def _select_ladder(self, hull_points: List[EncodingPoint],
                       min_vmaf_delta: float = 3.0,
                       max_rungs: int = 8) -> List[ABRLadderRung]:
        """
        Select ABR ladder rungs from convex hull points.
        
        Criteria:
        - Each rung should provide at least min_vmaf_delta improvement over previous
        - Maximum max_rungs total
        - Must include lowest and highest quality points
        """
        if not hull_points:
            return self._default_ladder()
        
        ladder = []
        last_vmaf = 0
        
        for point in hull_points:
            if point.vmaf - last_vmaf >= min_vmaf_delta or len(ladder) == 0:
                ladder.append(ABRLadderRung(
                    resolution=point.resolution,
                    bitrate_kbps=point.bitrate_kbps,
                    target_vmaf=point.vmaf,
                    codec='h264'
                ))
                last_vmaf = point.vmaf
            
            if len(ladder) >= max_rungs:
                break
        
        # Ensure we have the highest quality point
        best = max(hull_points, key=lambda p: p.vmaf)
        if ladder[-1].target_vmaf < best.vmaf - 1.0:
            ladder.append(ABRLadderRung(
                resolution=best.resolution,
                bitrate_kbps=best.bitrate_kbps,
                target_vmaf=best.vmaf,
                codec='h264'
            ))
        
        return ladder
    
    def _is_valid_combo(self, resolution: str, bitrate: int) -> bool:
        """Filter out nonsensical resolution-bitrate combinations."""
        w = int(resolution.split('x')[0])
        min_bitrate = {3840: 4000, 1920: 1500, 1280: 800, 960: 400, 640: 200}
        max_bitrate = {3840: 25000, 1920: 10000, 1280: 5000, 960: 3000, 640: 1500}
        return min_bitrate.get(w, 200) <= bitrate <= max_bitrate.get(w, 25000)
    
    def _default_ladder(self) -> List[ABRLadderRung]:
        """Fallback fixed ladder when analysis fails."""
        return [
            ABRLadderRung('640x360', 800, 70, 'h264'),
            ABRLadderRung('960x540', 1500, 80, 'h264'),
            ABRLadderRung('1280x720', 3000, 87, 'h264'),
            ABRLadderRung('1920x1080', 5000, 93, 'h264'),
            ABRLadderRung('3840x2160', 15000, 97, 'h264'),
        ]
```

---

## 8. Component Optimization

### 8.1 Kafka Configuration

```properties
# Broker configuration for high-throughput chunk processing
num.partitions=256
default.replication.factor=3
min.insync.replicas=2
log.retention.hours=24
log.segment.bytes=1073741824
message.max.bytes=10485760

# Consumer configuration for workers
max.poll.records=1
max.poll.interval.ms=600000
session.timeout.ms=300000
heartbeat.interval.ms=10000
fetch.min.bytes=1
fetch.max.wait.ms=100

# Producer configuration
acks=all
retries=5
retry.backoff.ms=1000
max.in.flight.requests.per.connection=1
compression.type=lz4
batch.size=65536
linger.ms=10
```

### 8.2 Spot Instance Strategy

```python
class AutoScaler:
    """Custom autoscaler for GPU worker fleet."""
    
    INSTANCE_POOLS = [
        {'type': 'g5.xlarge', 'gpus': 1, 'cost_per_hour': 1.006, 'spot_discount': 0.70},
        {'type': 'g5.2xlarge', 'gpus': 1, 'cost_per_hour': 1.212, 'spot_discount': 0.65},
        {'type': 'p3.2xlarge', 'gpus': 1, 'cost_per_hour': 3.06, 'spot_discount': 0.60},
    ]
    
    def compute_desired_capacity(self, metrics: dict) -> dict:
        """
        Compute desired fleet size based on queue depth and SLA.
        
        Strategy:
        - Premium queue: target <30s queue wait, use on-demand
        - Standard queue: target <5min queue wait, use 80% spot
        - Bulk queue: target <30min queue wait, use 95% spot
        """
        desired = {}
        
        for priority, config in [(1, {'max_wait_s': 30, 'spot_ratio': 0.2}),
                                  (2, {'max_wait_s': 300, 'spot_ratio': 0.8}),
                                  (3, {'max_wait_s': 1800, 'spot_ratio': 0.95})]:
            queue_depth = metrics[f'queue_depth_priority_{priority}']
            avg_process_time_s = metrics.get(f'avg_process_time_{priority}', 180)
            current_workers = metrics[f'workers_priority_{priority}']
            
            # Workers needed = queue_depth / (max_wait / avg_process_time)
            throughput_per_worker = config['max_wait_s'] / avg_process_time_s
            needed = max(1, int(queue_depth / max(1, throughput_per_worker)))
            
            # Apply dampening to avoid oscillation
            dampened = int(current_workers + (needed - current_workers) * 0.3)
            
            desired[priority] = {
                'total': dampened,
                'spot': int(dampened * config['spot_ratio']),
                'on_demand': dampened - int(dampened * config['spot_ratio'])
            }
        
        return desired
    
    def handle_spot_interruption(self, instance_id: str, worker_id: str):
        """Handle spot instance termination (2-min warning)."""
        # 1. Stop accepting new chunks
        # 2. Checkpoint current chunk progress
        # 3. Re-enqueue incomplete chunk
        # 4. Request replacement instance
        pass
```

### 8.3 S3 Multipart Upload Optimization

```python
import boto3
from concurrent.futures import ThreadPoolExecutor
import math

class OptimizedS3Transfer:
    """Optimized S3 transfers for large video files."""
    
    def __init__(self):
        self.s3 = boto3.client('s3')
        self.PART_SIZE = 100 * 1024 * 1024  # 100MB parts
        self.MAX_CONCURRENCY = 20
    
    def upload_large_file(self, local_path: str, bucket: str, key: str):
        """Multipart upload with parallel part uploads."""
        file_size = os.path.getsize(local_path)
        num_parts = math.ceil(file_size / self.PART_SIZE)
        
        # Initiate multipart upload
        mpu = self.s3.create_multipart_upload(
            Bucket=bucket, Key=key,
            StorageClass='INTELLIGENT_TIERING',
            ServerSideEncryption='aws:kms'
        )
        upload_id = mpu['UploadId']
        
        parts = []
        with ThreadPoolExecutor(max_workers=self.MAX_CONCURRENCY) as executor:
            futures = []
            for part_num in range(1, num_parts + 1):
                offset = (part_num - 1) * self.PART_SIZE
                size = min(self.PART_SIZE, file_size - offset)
                futures.append(executor.submit(
                    self._upload_part, bucket, key, upload_id,
                    part_num, local_path, offset, size
                ))
            
            for future in futures:
                parts.append(future.result())
        
        # Complete multipart upload
        self.s3.complete_multipart_upload(
            Bucket=bucket, Key=key, UploadId=upload_id,
            MultipartUpload={'Parts': sorted(parts, key=lambda p: p['PartNumber'])}
        )
```

---

## 9. Observability

### 9.1 Key Metrics

```yaml
# Prometheus metrics
metrics:
  - name: transcode_jobs_submitted_total
    type: counter
    labels: [tenant_id, priority]
  
  - name: transcode_jobs_completed_total
    type: counter
    labels: [tenant_id, priority, status]  # status: complete/failed/cancelled
  
  - name: transcode_job_duration_seconds
    type: histogram
    labels: [priority, codec, resolution]
    buckets: [30, 60, 120, 300, 600, 1200, 3600]
  
  - name: transcode_queue_depth
    type: gauge
    labels: [priority]
  
  - name: transcode_worker_gpu_utilization
    type: gauge
    labels: [worker_id, instance_type]
  
  - name: transcode_quality_vmaf
    type: histogram
    labels: [codec, resolution]
    buckets: [60, 70, 75, 80, 85, 90, 93, 95, 97, 99]
  
  - name: transcode_speed_ratio
    type: histogram  # >1 means faster than realtime
    labels: [codec, resolution, instance_type]
    buckets: [0.5, 1, 2, 3, 5, 10, 20]
  
  - name: transcode_cost_per_minute
    type: gauge
    labels: [codec, resolution, instance_type]

# Alerts
alerts:
  - name: HighQueueDepth
    expr: transcode_queue_depth{priority="1"} > 100
    for: 5m
    severity: critical
  
  - name: LowCompletionRate
    expr: rate(transcode_jobs_completed_total{status="complete"}[1h]) / rate(transcode_jobs_submitted_total[1h]) < 0.99
    for: 15m
    severity: warning
  
  - name: SlowTranscoding
    expr: histogram_quantile(0.95, transcode_speed_ratio) < 1.0
    for: 10m
    severity: warning
```

### 9.2 Distributed Tracing

```
Trace: job-submission → split → chunk-dispatch → [parallel chunk transcodes] → merge → DRM-package → webhook
Spans tagged with: job_id, tenant_id, priority, codec, resolution, chunk_index
```

---

## 10. Considerations & Trade-offs

| Decision | Choice | Trade-off |
|----------|--------|-----------|
| Chunk granularity | 30s default | Smaller = more parallelism but higher merge overhead |
| Quality metric | VMAF primary | CPU-intensive to compute but most perceptually accurate |
| Job queue | Kafka over SQS | Higher throughput, ordering guarantees, but operational complexity |
| GPU vs CPU encoding | GPU for H.264/H.265, CPU for AV1 | GPU is faster but lower quality at same bitrate for AV1 |
| Spot instances | 80% spot for standard tier | 60-70% cost savings but requires interruption handling |
| Per-title optimization | Optional per job | 2-5 min analysis overhead but 20-40% bitrate savings |
| DRM packaging | Post-transcode | Simpler pipeline but adds latency vs inline packaging |
| Chunk storage | Ephemeral S3 with lifecycle | Cleaned after 24h; retry requires re-splitting |

### Failure Modes
- **Worker crash mid-chunk**: Heartbeat timeout → chunk re-enqueued → idempotent re-processing
- **S3 write failure**: Retry with exponential backoff; switch AZ if persistent
- **Spot interruption**: 2-min warning → checkpoint → re-enqueue remainder
- **Quality below threshold**: Auto-retry with higher bitrate or different encoder settings
- **Merge discontinuity**: Detected by duration validation → re-encode boundary chunks with overlap

### Cost Optimization Summary
- Spot instances: 60-70% compute savings
- S3 Intelligent Tiering: auto-tier cold outputs
- Per-title encoding: 20-40% CDN bandwidth savings
- Chunk-level deduplication: skip re-encoding unchanged segments for re-submits
