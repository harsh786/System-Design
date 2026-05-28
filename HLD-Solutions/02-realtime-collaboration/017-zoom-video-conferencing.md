# Design Zoom - Video Conferencing Platform

## 1. Functional Requirements

- **Video/Audio Meetings**: 1:1 and group video calls (up to 1000 participants)
- **Screen Sharing**: Share screen, application window, or browser tab
- **Chat**: In-meeting text chat with file sharing
- **Recording**: Cloud and local recording with transcription
- **Scheduling**: Calendar integration, recurring meetings, waiting rooms
- **Breakout Rooms**: Split participants into sub-groups
- **Virtual Background**: AI-powered background replacement/blur
- **Reactions/Polls**: Emoji reactions, polls, Q&A
- **Webinar Mode**: Panelists + large audience (up to 50K attendees)
- **Whiteboard**: Collaborative drawing during meetings
- **Live Transcription/Captions**: Real-time speech-to-text
- **Meeting Security**: Passwords, waiting rooms, lock meeting, remove participants
- **Phone Dial-in**: PSTN bridge for audio-only participants
- **End-to-End Encryption**: Optional E2E for sensitive meetings

## 2. Non-Functional Requirements

| Requirement | Target |
|---|---|
| Availability | 99.99% for meeting service |
| Audio latency | < 150ms one-way (same region) |
| Video latency | < 200ms one-way |
| Video quality | 720p default, 1080p+ for pro |
| Join time | < 3s from click to connected |
| Concurrent meetings | 10M+ simultaneous |
| Concurrent participants (total) | 300M+ |
| Scalability | Support 300M DAU |
| Packet loss tolerance | Acceptable quality up to 10% loss |
| Bandwidth adaptation | 100kbps - 4Mbps adaptive |

## 3. Capacity Estimation

| Metric | Value |
|---|---|
| DAU | 300M |
| Concurrent meetings | 10M |
| Avg participants/meeting | 8 |
| Concurrent video streams | 80M |
| Meetings/day | 100M |
| Avg meeting duration | 40 minutes |
| Recordings/day | 10M (10% of meetings) |
| Recording storage/day | 10M × 40min × 50MB/hr = 333 TB/day |

### Bandwidth
| Traffic | Calculation | Value |
|---|---|---|
| Video ingress | 80M × 1.5 Mbps avg | 120 Tbps |
| Video egress | 80M × 3 Mbps (recv multiple) | 240 Tbps |
| Audio (backup) | 80M × 64 kbps | 5.12 Tbps |
| Screen share | 5M × 2 Mbps | 10 Tbps |
| Signaling | 100K joins/sec × 5KB | 500 MB/s |

## 4. Data Modeling

### Database Selection

| Store | Technology | Purpose |
|---|---|---|
| User/Account data | PostgreSQL (sharded) | Relational, ACID |
| Meeting metadata | PostgreSQL | Scheduling, settings |
| Meeting state (live) | Redis Cluster | Real-time, ephemeral |
| Chat messages | Cassandra | High write, per-meeting |
| Recordings | S3/GCS | Large blob storage |
| Recording metadata | PostgreSQL | Search, access control |
| Analytics | ClickHouse | Usage metrics, reporting |
| Signaling | Redis Pub/Sub | Low-latency coordination |
| Calendar events | PostgreSQL | Scheduling integration |

### Schema

```sql
-- Users
CREATE TABLE users (
    id UUID PRIMARY KEY,
    email VARCHAR(255) UNIQUE,
    name VARCHAR(100),
    plan_type VARCHAR(20), -- basic, pro, business, enterprise
    personal_meeting_id VARCHAR(11) UNIQUE, -- 10-digit PMI
    settings JSONB,
    created_at TIMESTAMPTZ
);

-- Meetings (scheduled)
CREATE TABLE meetings (
    id BIGINT PRIMARY KEY, -- 9-11 digit meeting ID
    host_id UUID REFERENCES users(id),
    topic VARCHAR(200),
    type SMALLINT, -- instant, scheduled, recurring, webinar
    start_time TIMESTAMPTZ,
    duration_minutes INT,
    timezone VARCHAR(50),
    password VARCHAR(10),
    waiting_room_enabled BOOLEAN DEFAULT TRUE,
    recording_type VARCHAR(20), -- none, local, cloud, auto
    max_participants INT DEFAULT 100,
    e2e_encrypted BOOLEAN DEFAULT FALSE,
    recurrence JSONB, -- for recurring meetings
    settings JSONB, -- all meeting settings
    status VARCHAR(20) DEFAULT 'scheduled', -- scheduled, started, ended
    created_at TIMESTAMPTZ
);
CREATE INDEX idx_meetings_host ON meetings(host_id, start_time);
CREATE INDEX idx_meetings_time ON meetings(start_time) WHERE status = 'scheduled';

-- Meeting Participants (live state - Redis, historical - PostgreSQL)
CREATE TABLE meeting_participants (
    meeting_id BIGINT,
    user_id UUID,
    join_time TIMESTAMPTZ,
    leave_time TIMESTAMPTZ,
    role VARCHAR(20), -- host, co-host, participant, attendee
    audio_status VARCHAR(10), -- muted, unmuted
    video_status VARCHAR(10), -- on, off
    duration_seconds INT,
    PRIMARY KEY (meeting_id, user_id, join_time)
);

-- Recordings
CREATE TABLE recordings (
    id UUID PRIMARY KEY,
    meeting_id BIGINT,
    type VARCHAR(20), -- video, audio, transcript, chat
    status VARCHAR(20), -- processing, ready, expired, deleted
    file_url TEXT,
    file_size_bytes BIGINT,
    duration_seconds INT,
    resolution VARCHAR(10),
    transcript_url TEXT,
    password VARCHAR(20),
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ
);
CREATE INDEX idx_recordings_meeting ON recordings(meeting_id);
```

## 5. High-Level Design

```
┌────────────────────────────────────────────────────────────────────────────────┐
│                              CLIENTS                                             │
│  Desktop App │ Mobile App │ Web (WebRTC) │ Phone (PSTN) │ Room System (H.323)  │
└──────────────────────────────────┬─────────────────────────────────────────────┘
                                   │
┌──────────────────────────────────▼─────────────────────────────────────────────┐
│                           EDGE LAYER                                             │
│ ┌────────┐ ┌─────────────┐ ┌──────────┐ ┌───────────────────────────────────┐ │
│ │  DNS   │ │   Anycast   │ │   WAF    │ │  TURN/STUN Servers (global edge) │ │
│ │(Geo LB)│ │ Load Balance│ │          │ │  - NAT traversal                 │ │
│ └────────┘ └─────────────┘ └──────────┘ │  - Relay for restricted networks │ │
│                                           └───────────────────────────────────┘ │
└──────────────────────────────────┬─────────────────────────────────────────────┘
                                   │
         ┌─────────────────────────┼──────────────────────────────┐
         ▼                         ▼                              ▼
┌──────────────────┐    ┌──────────────────────┐    ┌──────────────────────────┐
│ SIGNALING SERVER │    │   MEDIA SERVER       │    │    WEB API SERVER        │
│ (WebSocket)      │    │   (SFU Cluster)      │    │                          │
│ - Join/leave     │    │                      │    │  - REST APIs             │
│ - Offer/Answer   │    │  ┌────────────────┐  │    │  - Scheduling            │
│ - ICE candidates │    │  │ Audio Router   │  │    │  - User management       │
│ - Room control   │    │  │ (Opus codec)   │  │    │  - Recording management  │
│ - Chat relay     │    │  ├────────────────┤  │    │  - Billing               │
│                  │    │  │ Video Router   │  │    │  - Admin/Compliance       │
│                  │    │  │ (VP8/H.264/AV1)│  │    │                          │
│                  │    │  ├────────────────┤  │    └──────────────────────────┘
│                  │    │  │ Screen Share   │  │
│                  │    │  │ Router         │  │    ┌──────────────────────────┐
│                  │    │  ├────────────────┤  │    │   RECORDING SERVICE      │
│                  │    │  │ Recording      │  │    │   - Capture streams      │
│                  │    │  │ Tap            │  │    │   - Transcode            │
│                  │    │  └────────────────┘  │    │   - Store to S3          │
│                  │    │                      │    │   - Generate transcript   │
└──────────────────┘    └──────────────────────┘    └──────────────────────────┘
                                   │
┌──────────────────────────────────▼─────────────────────────────────────────────┐
│                              DATA LAYER                                          │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌─────────┐ ┌────────┐  │
│  │PostgreSQL│ │  Redis   │ │ Cassandra│ │   S3     │ │ClickHse │ │ Kafka  │  │
│  │(Metadata)│ │(LiveState│ │  (Chat)  │ │(Record.) │ │(Analytcs)│ │(Events)│  │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └─────────┘ └────────┘  │
└────────────────────────────────────────────────────────────────────────────────┘
```

### Media Architecture - SFU (Selective Forwarding Unit)

```
┌─────────────────────────────────────────────────────────────────┐
│                    SFU ARCHITECTURE                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  Why SFU over MCU:                                               │
│  - MCU: server decodes + re-encodes all streams (CPU expensive)  │
│  - SFU: server just forwards packets (10x less CPU)              │
│  - SFU: better quality (no re-encoding loss)                     │
│  - SFU: lower latency (no processing delay)                     │
│  - Trade-off: client receives N streams, more client bandwidth   │
│                                                                   │
│  Simulcast (send multiple qualities):                            │
│  - Each sender publishes 3 layers:                               │
│    · High: 720p @ 30fps @ 1.5 Mbps                              │
│    · Medium: 360p @ 30fps @ 500 Kbps                             │
│    · Low: 180p @ 15fps @ 150 Kbps                                │
│  - SFU selects which layer to forward to each receiver           │
│  - Active speaker gets High, thumbnails get Low                  │
│                                                                   │
│  SVC (Scalable Video Coding) alternative:                        │
│  - Single bitstream with embedded layers                         │
│  - SFU can drop enhancement layers for constrained receivers     │
│  - Used in newer implementations (AV1/SVC)                       │
│                                                                   │
│  Audio Handling:                                                  │
│  - Opus codec: 6-128 kbps, excellent quality                    │
│  - Server-side mixing: forward top 3 active speakers only       │
│  - Reduces bandwidth from N×N to N×3                             │
│  - Voice Activity Detection (VAD) for speaker selection          │
│                                                                   │
│  Large Meetings (>50 participants):                              │
│  - Cascaded SFU: multiple SFU nodes cooperate                   │
│  - Participants grouped by region                                │
│  - SFU nodes exchange only active speaker streams                │
│  - Reduces inter-DC bandwidth dramatically                       │
└─────────────────────────────────────────────────────────────────┘
```

## 6. Low-Level Design - APIs

### Meeting Management APIs

```
POST /api/v2/meetings
Request: {
  "topic": "Weekly Standup",
  "type": 2, // scheduled
  "start_time": "2024-05-28T09:00:00Z",
  "duration": 30,
  "timezone": "America/New_York",
  "password": "abc123",
  "settings": {
    "waiting_room": true,
    "mute_upon_entry": true,
    "auto_recording": "cloud",
    "breakout_rooms": true
  }
}
Response: {
  "id": 98765432109,
  "host_id": "user_123",
  "topic": "Weekly Standup",
  "join_url": "https://zoom.us/j/98765432109?pwd=encoded_pwd",
  "password": "abc123",
  "start_url": "https://zoom.us/s/98765432109?zak=host_token"
}

GET /api/v2/meetings/{meeting_id}
Response: { full meeting details + participant count if live }

DELETE /api/v2/meetings/{meeting_id}
Response: 204 No Content
```

### Real-time Signaling (WebSocket)

```json
// Client → Server: Join meeting
{"action": "join", "meeting_id": 98765432109, "token": "jwt...", "media_caps": {"audio": true, "video": true, "simulcast": true}}

// Server → Client: Room state
{"event": "room_state", "participants": [...], "settings": {...}, "media_server": "sfu-us-west-1.zoom.us"}

// Client → Server: Publish stream
{"action": "publish", "kind": "video", "sdp": "v=0\r\n...", "simulcast_layers": ["high", "medium", "low"]}

// Server → Client: Stream available
{"event": "stream_available", "participant_id": "p_456", "kind": "video", "track_id": "t_789"}

// Client → Server: Subscribe to stream
{"action": "subscribe", "track_id": "t_789", "preferred_quality": "high"}

// Server → Client: SDP answer
{"event": "sdp_answer", "sdp": "v=0\r\n..."}

// Server → Client: Active speaker changed
{"event": "active_speaker", "participant_id": "p_456", "audio_level": 0.8}

// Client → Server: Mute/unmute
{"action": "mute", "kind": "audio", "muted": true}

// Host → Server: Mute all
{"action": "mute_all", "allow_unmute": true}
```

## 7. Architecture Deep Dive

### 7.1 Meeting Join Flow

```
1. User clicks join link → DNS resolves to nearest edge
2. Client connects WebSocket to signaling server
3. Signaling authenticates token, checks meeting exists/started
4. Signaling assigns media server (nearest SFU with capacity)
5. Client establishes WebRTC connection to SFU:
   a. STUN: discover public IP
   b. ICE: find best connectivity path
   c. DTLS: secure the connection
   d. SRTP: begin encrypted media flow
6. Client publishes audio/video tracks to SFU
7. SFU notifies other participants of new stream
8. Other participants subscribe to new stream
9. Total time: < 3 seconds
```

### 7.2 Bandwidth Adaptation (Congestion Control)

```
Algorithm: Google Congestion Control (GCC) / Transport-CC

Sender Side:
1. Start at 1 Mbps, probe for available bandwidth
2. Increase gradually (additive increase)
3. On packet loss or delay spike: reduce immediately (multiplicative decrease)
4. Select simulcast layer based on estimated bandwidth:
   - > 1.5 Mbps: send High + Medium + Low
   - 500K - 1.5M: send Medium + Low
   - < 500K: send Low only

Receiver Side (SFU):
1. Monitor each receiver's available bandwidth
2. Switch forwarded layer based on receiver bandwidth:
   - Receiver has 2 Mbps: forward High for speaker, Medium for others
   - Receiver has 500 Kbps: forward Low for all, Medium for speaker
3. Temporal scalability: drop frames to reduce bitrate without resolution change

Network Quality Indicators:
- RTT measurement (RTCP sender/receiver reports)
- Packet loss percentage
- Jitter (variation in packet arrival time)
- Available bandwidth estimation
```

### 7.3 Recording Architecture

```
┌─────────────────────────────────────────────────────────┐
│              RECORDING PIPELINE                           │
├─────────────────────────────────────────────────────────┤
│                                                           │
│  1. Recording Tap (on SFU):                              │
│     - Capture all media streams as RTP packets           │
│     - Write raw streams to local SSD buffer              │
│     - Forward to recording processor                     │
│                                                           │
│  2. Recording Processor:                                 │
│     - Decode all video streams                           │
│     - Compose into gallery/speaker layout                │
│     - Encode as H.264 MP4 (720p/1080p)                  │
│     - Mix all audio into single track                    │
│     - Generate: full_video.mp4, audio_only.m4a,          │
│       speaker_view.mp4, gallery_view.mp4                 │
│                                                           │
│  3. Post-Processing:                                     │
│     - Upload to S3 (multi-part, parallel)                │
│     - Generate transcript (Whisper/DeepSpeech ASR)       │
│     - Generate chapters/highlights                       │
│     - Thumbnail generation at key moments                │
│     - Encrypt with meeting-specific key                  │
│                                                           │
│  4. Delivery:                                             │
│     - Notify host: "Recording ready"                     │
│     - Generate share link with access control            │
│     - Retention policy: auto-delete after 30/60/90 days  │
│     - Download or stream via CDN                         │
│                                                           │
│  Storage Tiers:                                           │
│  - Hot (7 days): S3 Standard                             │
│  - Warm (30 days): S3 IA                                │
│  - Cold (90+ days): S3 Glacier                           │
└─────────────────────────────────────────────────────────┘
```

## 8. Optimization

### 8.1 Media Server Optimization
- **SIMD (AVX2/NEON)**: Hardware-accelerated packet routing
- **Zero-copy networking**: sendfile/splice for media forwarding
- **DPDK or XDP**: Kernel bypass for ultra-low latency packet handling
- **Connection pooling**: Reuse DTLS sessions for same client
- **Memory pools**: Pre-allocated buffers for RTP packets (avoid GC)

### 8.2 Global Infrastructure
```
Media Server Regions: 20+ regions worldwide
  US: us-east-1, us-west-2, us-central
  EU: eu-west-1, eu-central-1, eu-north-1
  APAC: ap-southeast-1, ap-northeast-1, ap-south-1
  
Meeting Allocation:
  - Determine optimal region based on participant locations
  - If all in same city: use nearest region
  - If distributed: use central region or cascade across regions
  - Dynamic migration: if participants change, can relocate meeting
```

### 8.3 Caching & CDN
```
- Meeting metadata: Redis cache (TTL 5 min)
- User profiles/avatars: CDN with long TTL
- Virtual backgrounds: CDN edge cache
- Recordings: CloudFront with signed URLs
- Static assets: Aggressive caching (1 year, immutable)
```

## 9. Observability

```yaml
Key Metrics:
  zoom_meeting_join_latency_seconds{region, quantile}
  zoom_active_meetings_total{region}
  zoom_concurrent_participants{region}
  zoom_media_packet_loss_ratio{direction="send|recv", region}
  zoom_audio_mos_score{region}  # Mean Opinion Score (1-5)
  zoom_video_quality_score{resolution, region}
  zoom_sfu_cpu_utilization{node}
  zoom_sfu_bandwidth_usage_gbps{node, direction}
  zoom_recording_processing_time_seconds{quantile}
  zoom_signaling_latency_seconds{quantile}

Alerts:
  Critical: packet_loss > 5% in region, MOS < 3.0, join_latency > 10s
  Warning: CPU > 80% on SFU, recording queue > 1000, bandwidth > 80% capacity
```

## 10. Considerations

### Key Trade-offs
| Decision | Chosen | Trade-off |
|---|---|---|
| SFU over MCU | Lower server cost, better quality | More client bandwidth needed |
| Simulcast over SVC | Broader codec support | Less bandwidth efficient |
| Regional SFU | Low latency | Cascading complexity for global meetings |
| Cloud recording | No client resources used | Server storage/processing cost |
| WebRTC (web) | No plugin needed | Browser limitations for advanced features |

### Security
- SRTP encryption for all media (mandatory)
- DTLS key exchange for peer authentication
- Optional E2E encryption (host enables, server can't decrypt)
- Waiting room to prevent uninvited participants (Zoom-bombing)
- Meeting passwords, meeting lock, remove participants
- Watermarking for screenshots/recordings (enterprise)
- SOC2, HIPAA, FedRAMP compliance options
