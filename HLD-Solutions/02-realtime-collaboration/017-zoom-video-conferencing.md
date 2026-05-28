# Design Zoom Video Conferencing - World-Class System Design

## 1. Functional Requirements

| # | Requirement | Description |
|---|---|---|
| FR1 | Video/audio calls | 1:1 and group video/audio calls with up to 1000 participants |
| FR2 | Screen sharing | Share screen, application window, or whiteboard |
| FR3 | Meeting scheduling | Schedule meetings with calendar integration, recurring meetings |
| FR4 | Meeting rooms | Persistent rooms with unique URLs, waiting rooms |
| FR5 | Recording | Cloud recording with automatic transcription |
| FR6 | Chat in meeting | Text chat, file sharing, reactions within meetings |
| FR7 | Breakout rooms | Split participants into smaller groups mid-meeting |
| FR8 | Virtual backgrounds | Real-time background replacement using ML |
| FR9 | Noise cancellation | AI-powered noise suppression |
| FR10 | End-to-end encryption | Optional E2EE for sensitive meetings |
| FR11 | Adaptive bitrate | Adjust video quality based on network conditions |
| FR12 | Webinar mode | Large-scale events with panelists and attendees (up to 50K) |

## 2. Non-Functional Requirements

| # | NFR | Target |
|---|---|---|
| NFR1 | Availability | 99.99% (52 min downtime/year) |
| NFR2 | Latency - audio | < 150ms one-way (mouth-to-ear) |
| NFR3 | Latency - video | < 200ms one-way |
| NFR4 | Latency - screen share | < 300ms |
| NFR5 | Jitter | < 30ms |
| NFR6 | Packet loss tolerance | Audio: < 5%, Video: < 2% graceful degradation |
| NFR7 | Concurrent meetings | 10M simultaneous meetings |
| NFR8 | Concurrent participants | 300M concurrent users |
| NFR9 | Video quality | Up to 1080p (4K for premium), adaptive 360p-1080p |
| NFR10 | Scale | 500M registered users, 100M DAU |
| NFR11 | Recording storage | Petabytes of recorded content |
| NFR12 | Global reach | < 50ms to nearest media server from any major city |

## 3. Capacity Estimation

### 3.1 Traffic Metrics

| Metric | Value |
|---|---|
| DAU | 100M |
| Concurrent meetings (peak) | 10M |
| Concurrent participants (peak) | 300M |
| Average meeting duration | 40 minutes |
| Average participants per meeting | 8 |
| Meetings per day | 500M |
| Recordings per day | 50M (10% of meetings) |

### 3.2 Bandwidth Estimation

| Stream Type | Bitrate | Per User | Total (300M users) |
|---|---|---|---|
| Video (720p) | 1.5 Mbps send + 1.5 Mbps recv | 3 Mbps | 900 Pbps theoretical |
| Video (actual with SFU) | 1.5 Mbps send + 4.5 Mbps recv (3 streams) | 6 Mbps | 1.8 Pbps |
| Audio | 64 Kbps send + 64 Kbps recv | 128 Kbps | 38.4 Pbps |
| Screen share | 2 Mbps (when active, ~20% of time) | 400 Kbps avg | 120 Pbps |

**Note**: Real-world estimation uses SFU architecture where each user sends 1 stream but receives N-1 streams (or subset with simulcast).

### 3.3 Storage Estimation

| Data | Calculation | Storage |
|---|---|---|
| Recordings/day | 50M meetings × 40 min × 2 Mbps = 50M × 600 MB | 30 PB/day |
| Recording retention (90 days) | 30 PB × 90 | 2.7 EB |
| Meeting metadata | 500M × 2 KB/day | 1 TB/day |
| Chat messages | 500M meetings × 20 msgs × 500 bytes | 5 TB/day |
| Transcriptions | 50M × 40 min × 1 KB/min | 2 TB/day |

### 3.4 Server Capacity

| Component | Calculation | Servers Needed |
|---|---|---|
| Media servers (SFU) | 300M users / 500 users per server | 600K servers |
| Signaling servers | 10M meetings / 10K conns per server | 1K servers |
| TURN servers | 15% of users need relay (45M) / 2K per server | 22.5K servers |
| Recording servers | 5M concurrent recordings / 50 per server | 100K servers |

## 4. Data Modeling

### 4.1 Database Selection

| Workload | Database | Justification |
|---|---|---|
| User accounts & profiles | PostgreSQL (sharded) | Relational, ACID, complex queries |
| Meeting metadata | PostgreSQL + Redis cache | Transactional, read-heavy |
| Meeting state (live) | Redis Cluster | In-memory, sub-ms latency for real-time state |
| Chat messages | Cassandra | High write throughput, time-series |
| Recordings metadata | PostgreSQL | Relational queries, access control |
| Recording files | S3 / Object Storage | Massive scale, lifecycle management |
| Signaling state | Redis | Ephemeral, connection mapping |
| Analytics | ClickHouse | Time-series analytics, OLAP |
| Search (recordings) | Elasticsearch | Full-text search on transcriptions |
| Calendar/scheduling | PostgreSQL | Complex recurring event logic |

### 4.2 Schema Design

#### PostgreSQL: Meetings
```sql
CREATE TABLE meetings (
    meeting_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    host_user_id      UUID NOT NULL REFERENCES users(user_id),
    title             VARCHAR(255),
    meeting_type      VARCHAR(20) NOT NULL, -- instant, scheduled, recurring, webinar
    status            VARCHAR(20) DEFAULT 'scheduled', -- scheduled, live, ended, cancelled
    password_hash     VARCHAR(128),
    waiting_room      BOOLEAN DEFAULT FALSE,
    e2ee_enabled      BOOLEAN DEFAULT FALSE,
    max_participants  INT DEFAULT 100,
    scheduled_start   TIMESTAMP WITH TIME ZONE,
    scheduled_end     TIMESTAMP WITH TIME ZONE,
    actual_start      TIMESTAMP WITH TIME ZONE,
    actual_end        TIMESTAMP WITH TIME ZONE,
    timezone          VARCHAR(50),
    recurrence_rule   JSONB,              -- RRULE for recurring meetings
    settings          JSONB,              -- mute on entry, video off, etc.
    created_at        TIMESTAMP DEFAULT NOW(),
    updated_at        TIMESTAMP DEFAULT NOW(),
    version           INT DEFAULT 1
);

CREATE INDEX idx_meetings_host ON meetings(host_user_id, scheduled_start DESC);
CREATE INDEX idx_meetings_status ON meetings(status) WHERE status = 'live';
CREATE INDEX idx_meetings_schedule ON meetings(scheduled_start) WHERE status = 'scheduled';

CREATE TABLE meeting_participants (
    meeting_id        UUID REFERENCES meetings(meeting_id),
    user_id           UUID REFERENCES users(user_id),
    role              VARCHAR(20) DEFAULT 'participant', -- host, co-host, panelist, participant, attendee
    join_time         TIMESTAMP WITH TIME ZONE,
    leave_time        TIMESTAMP WITH TIME ZONE,
    duration_seconds  INT,
    device_type       VARCHAR(20),
    connection_quality VARCHAR(10), -- good, fair, poor
    PRIMARY KEY (meeting_id, user_id, join_time)
);

CREATE INDEX idx_participants_user ON meeting_participants(user_id, join_time DESC);

CREATE TABLE recordings (
    recording_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    meeting_id        UUID REFERENCES meetings(meeting_id),
    recording_type    VARCHAR(20), -- video, audio, transcript, chat
    status            VARCHAR(20) DEFAULT 'processing', -- processing, ready, failed, deleted
    storage_path      TEXT,         -- S3 path
    file_size_bytes   BIGINT,
    duration_seconds  INT,
    resolution        VARCHAR(10),  -- 720p, 1080p
    transcript_path   TEXT,
    created_at        TIMESTAMP DEFAULT NOW(),
    expires_at        TIMESTAMP WITH TIME ZONE,
    access_level      VARCHAR(20) DEFAULT 'host_only'
);

CREATE INDEX idx_recordings_meeting ON recordings(meeting_id);
CREATE INDEX idx_recordings_expiry ON recordings(expires_at) WHERE status = 'ready';
```

#### Redis: Live Meeting State
```
# Meeting state (lives only during active meeting)
Key: meeting:live:{meeting_id}
Type: HASH
Fields:
  status: "active"
  host_user_id: "u_123"
  participant_count: "8"
  start_time: "1716003600"
  media_server_id: "ms_us_east_01"
  recording_active: "true"
  screen_share_user: "u_456"
  breakout_active: "false"
TTL: None (deleted when meeting ends)

# Participant connection mapping
Key: meeting:participants:{meeting_id}
Type: HASH
Fields:
  u_123: "ms_us_east_01:conn_abc"   # user → media_server:connection
  u_456: "ms_us_east_01:conn_def"
  u_789: "ms_eu_west_01:conn_ghi"   # different region participant

# Signaling channel
Key: signal:{user_id}:{meeting_id}
Type: LIST (for SDP offers/answers, ICE candidates)
TTL: 300s
```

#### Cassandra: Chat Messages
```sql
CREATE TABLE meeting_chat (
    meeting_id    UUID,
    message_id    TIMEUUID,
    sender_id     UUID,
    message_type  TEXT,      -- text, file, reaction, system
    content       TEXT,
    file_url      TEXT,
    recipient     TEXT,      -- 'all', user_id for DM, breakout_room_id
    created_at    TIMESTAMP,
    PRIMARY KEY ((meeting_id), message_id)
) WITH CLUSTERING ORDER BY (message_id ASC)
  AND default_time_to_live = 2592000; -- 30 days
```

## 5. High-Level Design (HLD)

### 5.1 Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              CLIENT LAYER                                     │
│  [Desktop App] [Mobile App] [Web Browser] [Room Systems] [Phone Dial-in]    │
│                                                                               │
│  Client Components:                                                           │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐               │
│  │ WebRTC     │ │ Codec      │ │ Noise      │ │ Virtual BG │               │
│  │ Stack      │ │ Engine     │ │ Canceller  │ │ ML Model   │               │
│  │ (ICE/DTLS/ │ │ (H.264/   │ │ (RNNoise/  │ │            │               │
│  │  SRTP)     │ │  VP8/VP9/  │ │  Krisp)    │ │            │               │
│  │            │ │  AV1)      │ │            │ │            │               │
│  └────────────┘ └────────────┘ └────────────┘ └────────────┘               │
└───────────────────────────────────┬─────────────────────────────────────────┘
                                    │ UDP/TCP (SRTP/DTLS)
                                    │ WSS (Signaling)
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         EDGE / NETWORK LAYER                                  │
│                                                                               │
│  ┌──────────┐  ┌──────────────┐  ┌────────────┐  ┌────────────────────┐   │
│  │ Route 53 │  │ Global       │  │ TURN/STUN  │  │ DDoS Protection    │   │
│  │ (DNS +   │  │ Anycast      │  │ Servers    │  │ (AWS Shield)       │   │
│  │  Latency │  │ Network      │  │ (Relay for │  │                    │   │
│  │  Routing)│  │              │  │  NAT trvsl)│  │                    │   │
│  └──────────┘  └──────────────┘  └────────────┘  └────────────────────┘   │
│                                                                               │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │              Points of Presence (PoPs) - 200+ locations               │   │
│  │  Each PoP: TURN servers + Edge media processors + Signaling relay    │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                               │
└───────────────────────────────────┬─────────────────────────────────────────┘
                                    │
┌───────────────────────────────────┼─────────────────────────────────────────┐
│                      SIGNALING LAYER                │                         │
│                                                      ▼                        │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                   Signaling Service (WebSocket)                       │    │
│  │  • SDP Offer/Answer exchange (WebRTC negotiation)                   │    │
│  │  • ICE candidate relay                                               │    │
│  │  • Meeting room management (join/leave/mute/kick)                   │    │
│  │  • Real-time state sync (who's talking, screen sharing, etc.)       │    │
│  │  Tech: Go + WebSocket | Stateless | 10K connections/server          │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                               │
└───────────────────────────────────┬─────────────────────────────────────────┘
                                    │
┌───────────────────────────────────┼─────────────────────────────────────────┐
│                      MEDIA LAYER (Core)             │                         │
│                                                      ▼                        │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │           Selective Forwarding Unit (SFU) Cluster                     │    │
│  │                                                                       │    │
│  │  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐       │    │
│  │  │  SFU-1    │  │  SFU-2    │  │  SFU-3    │  │  SFU-N    │       │    │
│  │  │ (500 usr) │  │ (500 usr) │  │ (500 usr) │  │ (500 usr) │       │    │
│  │  │           │  │           │  │           │  │           │       │    │
│  │  │ Simulcast │  │ Simulcast │  │ Simulcast │  │ Simulcast │       │    │
│  │  │ SVC Layer │  │ SVC Layer │  │ SVC Layer │  │ SVC Layer │       │    │
│  │  │ Selection │  │ Selection │  │ Selection │  │ Selection │       │    │
│  │  └───────────┘  └───────────┘  └───────────┘  └───────────┘       │    │
│  │                                                                       │    │
│  │  Cross-SFU Cascading (for meetings spanning multiple SFUs):          │    │
│  │  SFU-1 ←──UDP/TCP──→ SFU-2 ←──UDP/TCP──→ SFU-3                    │    │
│  │                                                                       │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                               │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │           Media Processing Services                                   │    │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐                │    │
│  │  │ Transcoding  │ │ Recording    │ │ Composition  │                │    │
│  │  │ Service      │ │ Service      │ │ Service      │                │    │
│  │  │ (H264→VP8)   │ │ (media→S3)   │ │ (Grid/Speaker│                │    │
│  │  │              │ │              │ │  view render) │                │    │
│  │  └──────────────┘ └──────────────┘ └──────────────┘                │    │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐                │    │
│  │  │ Speech-to-   │ │ Live         │ │ AI Noise     │                │    │
│  │  │ Text (STT)   │ │ Captioning   │ │ Suppression  │                │    │
│  │  │              │ │              │ │ (server-side)│                │    │
│  │  └──────────────┘ └──────────────┘ └──────────────┘                │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                               │
└───────────────────────────────────┬─────────────────────────────────────────┘
                                    │
┌───────────────────────────────────┼─────────────────────────────────────────┐
│                   APPLICATION LAYER                  │                         │
│                                                      ▼                        │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐          │
│  │ Meeting Service  │  │ User Service     │  │ Auth Service     │          │
│  │ (CRUD, schedule) │  │ (profiles, plan) │  │ (OAuth, JWT,SSO) │          │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘          │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐          │
│  │ Recording Service│  │ Notification Svc │  │ Calendar Service │          │
│  │ (manage, share)  │  │ (email, push)    │  │ (Google, O365)   │          │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘          │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐          │
│  │ Chat Service     │  │ Billing Service  │  │ Analytics Service│          │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘          │
│                                                                               │
└───────────────────────────────────┬─────────────────────────────────────────┘
                                    │
┌───────────────────────────────────┼─────────────────────────────────────────┐
│                      DATA LAYER                     │                         │
│                                                      ▼                        │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐      │
│  │ PostgreSQL   │ │ Redis Cluster│ │ Cassandra    │ │ S3           │      │
│  │ (Meetings,   │ │ (Live state, │ │ (Chat, CDR) │ │ (Recordings, │      │
│  │  Users,      │ │  Signaling,  │ │              │ │  Transcripts)│      │
│  │  Billing)    │ │  Routing)    │ │              │ │              │      │
│  └──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘      │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐                       │
│  │ ClickHouse   │ │ Elasticsearch│ │ Kafka        │                       │
│  │ (Analytics)  │ │ (Search)     │ │ (Events)     │                       │
│  └──────────────┘ └──────────────┘ └──────────────┘                       │
│                                                                               │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 5.2 Media Architecture: SFU vs MCU

```
┌─────────────────────────────────────────────────────────────────┐
│  SELECTIVE FORWARDING UNIT (SFU) - Chosen Architecture          │
│                                                                   │
│  Why SFU over MCU:                                               │
│  • Lower latency (no transcoding delay)                          │
│  • Better scaling (linear vs exponential compute)                │
│  • Simulcast support (multiple quality layers)                   │
│  • Lower server cost (forwarding vs encoding)                    │
│                                                                   │
│  How Simulcast Works:                                            │
│                                                                   │
│  Sender encodes 3 layers simultaneously:                         │
│  ┌─────────┐                                                     │
│  │ Client  │──→ High (720p, 1.5 Mbps)  ──→ SFU ──→ Good conn  │
│  │ Camera  │──→ Medium (360p, 500 Kbps) ──→ SFU ──→ Fair conn  │
│  │         │──→ Low (180p, 150 Kbps)    ──→ SFU ──→ Poor conn  │
│  └─────────┘                                                     │
│                                                                   │
│  SFU selects which layer to forward based on:                    │
│  • Receiver's available bandwidth (REMB/TWCC feedback)           │
│  • Whether video is in "active speaker" vs "thumbnail"           │
│  • Explicit quality preference from receiver                     │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

### 5.3 Meeting Topology for Large Meetings

```
Small meeting (≤ 20 participants): Single SFU
┌─────┐     ┌─────────┐     ┌─────┐
│User1│◄───►│  SFU-1  │◄───►│User2│
│User3│◄───►│ (single)│◄───►│User4│
└─────┘     └─────────┘     └─────┘

Medium meeting (20-300 participants): Cascaded SFUs
┌─────┐     ┌─────────┐           ┌─────────┐     ┌─────┐
│User1│◄───►│  SFU-1  │◄─cascade─►│  SFU-2  │◄───►│User5│
│User2│◄───►│ Region1 │           │ Region2 │◄───►│User6│
└─────┘     └─────────┘           └─────────┘     └─────┘

Large meeting/Webinar (300-50K): Hierarchical tree
                    ┌──────────┐
                    │ Origin   │ (Host/Panelists)
                    │ SFU      │
                    └────┬─────┘
              ┌──────────┼──────────┐
              ▼          ▼          ▼
        ┌──────────┐ ┌──────────┐ ┌──────────┐
        │ Edge     │ │ Edge     │ │ Edge     │  (Regional)
        │ SFU-1   │ │ SFU-2   │ │ SFU-3   │
        └────┬─────┘ └────┬─────┘ └────┬─────┘
             │             │             │
        ┌────┴────┐   ┌────┴────┐   ┌────┴────┐
        │ 1000    │   │ 1000    │   │ 1000    │  (Attendees)
        │ viewers │   │ viewers │   │ viewers │
        └─────────┘   └─────────┘   └─────────┘
```

## 6. Low-Level Design (LLD)

### 6.1 Signaling Protocol (WebSocket)

```json
// Client → Server: Join Meeting
{
  "type": "join",
  "meeting_id": "meet_abc123",
  "auth_token": "jwt_...",
  "device_info": {
    "type": "desktop",
    "os": "macOS",
    "browser": "Chrome 125",
    "audio_codecs": ["opus"],
    "video_codecs": ["H264", "VP9", "AV1"],
    "simulcast": true,
    "max_resolution": "1080p"
  }
}

// Server → Client: Join Accepted + Room State
{
  "type": "join_accepted",
  "participant_id": "part_xyz",
  "media_server": {
    "url": "wss://sfu-us-east-01.zoom.example.com",
    "ice_servers": [
      {"urls": "stun:stun.zoom.example.com:3478"},
      {"urls": "turn:turn.zoom.example.com:443", "credential": "temp_cred_..."}
    ]
  },
  "room_state": {
    "participants": [
      {"user_id": "u_1", "name": "Alice", "audio": true, "video": true, "role": "host"},
      {"user_id": "u_2", "name": "Bob", "audio": true, "video": false, "role": "participant"}
    ],
    "screen_share": null,
    "recording": false
  }
}

// SDP Offer/Answer Exchange
{
  "type": "sdp_offer",
  "sdp": "v=0\r\no=- 12345 2 IN IP4 127.0.0.1\r\n...",
  "tracks": [
    {"id": "audio_0", "kind": "audio", "codec": "opus/48000/2"},
    {"id": "video_0", "kind": "video", "codec": "H264", "simulcast": ["h", "m", "l"]}
  ]
}

// ICE Candidate
{
  "type": "ice_candidate",
  "candidate": "candidate:1 1 UDP 2130706431 192.168.1.1 54321 typ host",
  "sdpMid": "0",
  "sdpMLineIndex": 0
}

// Media Control
{
  "type": "media_control",
  "action": "mute_audio"  // mute_audio, unmute_audio, stop_video, start_video
}

// Active Speaker Notification
{
  "type": "active_speaker",
  "user_id": "u_1",
  "audio_level": 0.85,
  "timestamp": 1716003600000
}

// Quality Adaptation
{
  "type": "quality_update",
  "user_id": "u_2",
  "layer": "medium",       // high, medium, low
  "reason": "bandwidth"    // bandwidth, cpu, manual
}
```

### 6.2 REST APIs

```http
POST /api/v1/meetings
Authorization: Bearer <token>
Content-Type: application/json

Request:
{
  "title": "Team Standup",
  "type": "scheduled",
  "scheduled_start": "2025-05-20T09:00:00Z",
  "duration_minutes": 30,
  "timezone": "America/New_York",
  "settings": {
    "waiting_room": true,
    "mute_on_entry": true,
    "video_off_on_entry": false,
    "allow_recording": true,
    "e2ee": false,
    "max_participants": 50,
    "breakout_rooms_enabled": true
  },
  "recurrence": {
    "type": "weekly",
    "days": ["MON", "WED", "FRI"],
    "end_date": "2025-12-31"
  }
}

Response (201 Created):
{
  "meeting_id": "meet_abc123",
  "join_url": "https://zoom.example.com/j/meet_abc123",
  "host_url": "https://zoom.example.com/j/meet_abc123?host_key=hk_xyz",
  "password": "123456",
  "dial_in_numbers": [
    {"country": "US", "number": "+1-555-0100", "pin": "12345#"}
  ],
  "settings": {...},
  "created_at": "2025-05-18T10:00:00Z"
}
```

```http
POST /api/v1/meetings/{meeting_id}/join
Authorization: Bearer <token>

Request:
{
  "display_name": "John Doe",
  "password": "123456",
  "device_type": "desktop"
}

Response (200 OK):
{
  "participant_id": "part_xyz",
  "signaling_url": "wss://signal-us-east.zoom.example.com/ws",
  "signaling_token": "sig_token_...",
  "media_region": "us-east-1",
  "ice_servers": [...],
  "meeting_info": {
    "title": "Team Standup",
    "host": "Alice",
    "participant_count": 5,
    "recording_active": false,
    "waiting_room_active": true
  }
}
```

### 6.3 Internal gRPC APIs

```protobuf
syntax = "proto3";
package media.v1;

service MediaRoutingService {
  rpc AllocateMediaServer(AllocateRequest) returns (AllocateResponse);
  rpc CascadeSFUs(CascadeRequest) returns (CascadeResponse);
  rpc MigrateParticipant(MigrateRequest) returns (MigrateResponse);
  rpc GetServerLoad(LoadRequest) returns (LoadResponse);
}

service RecordingService {
  rpc StartRecording(StartRecordingRequest) returns (StartRecordingResponse);
  rpc StopRecording(StopRecordingRequest) returns (StopRecordingResponse);
  rpc GetRecordingStatus(StatusRequest) returns (StatusResponse);
  rpc ProcessRecording(ProcessRequest) returns (ProcessResponse);  // transcode + upload
}

service TranscriptionService {
  rpc StartLiveTranscription(stream AudioFrame) returns (stream TranscriptSegment);
  rpc TranscribeRecording(TranscribeRequest) returns (TranscribeResponse);
  rpc GetTranscript(GetTranscriptRequest) returns (TranscriptResponse);
}
```

## 7. Architecture Components Deep Dive

### 7.1 WebRTC Media Pipeline

```
┌─────────────────────────────────────────────────────────────────┐
│                  MEDIA PIPELINE (Per Participant)                 │
│                                                                   │
│  SEND PATH:                                                      │
│  Microphone → Noise Cancel → Opus Encode → SRTP → Network      │
│  Camera → Background → H264 Encode (3 layers) → SRTP → Network │
│                                                                   │
│  RECEIVE PATH:                                                   │
│  Network → SRTP Decrypt → Jitter Buffer → Decoder → Render     │
│                                                                   │
│  SFU FORWARDING (No transcoding!):                               │
│  Recv SRTP from sender → Select layer → Forward SRTP to recv   │
│                                                                   │
│  Bandwidth Estimation:                                           │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ TWCC (Transport-Wide Congestion Control):                │    │
│  │ • Receiver sends feedback every 100ms                    │    │
│  │ • Reports packet arrival times                            │    │
│  │ • Sender estimates available bandwidth                    │    │
│  │ • Adjusts encoding bitrate + simulcast layer selection   │    │
│  │                                                           │    │
│  │ GCC (Google Congestion Control):                          │    │
│  │ • Delay-based + loss-based estimation                    │    │
│  │ • Ramp-up slowly, back-off quickly                       │    │
│  │ • Target: fill available bandwidth without causing loss  │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

### 7.2 SFU Server Design

```
┌─────────────────────────────────────────────────────────────────┐
│                    SFU SERVER INTERNALS                           │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Transport Layer                                          │    │
│  │  • ICE/DTLS/SRTP stack per participant                   │    │
│  │  • UDP sockets (primary) + TCP fallback                  │    │
│  │  • TURN relay integration                                │    │
│  └────────────────────────────────┬────────────────────────┘    │
│                                    │                              │
│  ┌─────────────────────────────────▼──────────────────────────┐ │
│  │  Router Layer                                                │ │
│  │  • Per-meeting "Room" object                                 │ │
│  │  • Track subscription management                             │ │
│  │  • Simulcast layer selection per subscriber                  │ │
│  │  • Active speaker detection (audio level + VAD)              │ │
│  │  • Bandwidth allocation across tracks                        │ │
│  └────────────────────────────────┬────────────────────────────┘ │
│                                    │                              │
│  ┌─────────────────────────────────▼──────────────────────────┐ │
│  │  Quality Layer                                               │ │
│  │  • Per-receiver bandwidth estimation                         │ │
│  │  • Temporal/Spatial layer switching (VP9 SVC)               │ │
│  │  • Keyframe requests (PLI/FIR)                              │ │
│  │  • Packet loss concealment                                   │ │
│  │  • FEC (Forward Error Correction) for lossy links           │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                   │
│  Capacity: 500 participants per SFU server                       │
│  Hardware: 32 cores, 64GB RAM, 25 Gbps NIC                     │
│  OS: Linux with tuned UDP buffer sizes                           │
│  Language: C++ or Rust for performance                           │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

### 7.3 Recording Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                  RECORDING PIPELINE                               │
│                                                                   │
│  1. CAPTURE (on SFU):                                           │
│     SFU forks media streams to Recording Agent                   │
│     Recording Agent receives raw RTP/SRTP packets                │
│                                                                   │
│  2. MUX (Recording Service):                                    │
│     ┌────────────────────────────────────────┐                  │
│     │ Individual Track Recording:             │                  │
│     │ • Each participant → separate file      │                  │
│     │ • Audio: Opus → PCM → WAV segment      │                  │
│     │ • Video: H264 → MP4 segment            │                  │
│     │ • Segments: 30-second chunks to S3      │                  │
│     └────────────────────────────────────────┘                  │
│                                                                   │
│  3. POST-PROCESS (Async - after meeting ends):                  │
│     ┌────────────────────────────────────────┐                  │
│     │ Composition Service:                    │                  │
│     │ • Merge all tracks into single file     │                  │
│     │ • Active speaker view / Gallery view    │                  │
│     │ • Add chapter markers (speaker changes) │                  │
│     │ • Transcode to multiple qualities       │                  │
│     │   (1080p, 720p, 480p, audio-only)      │                  │
│     │ • Generate thumbnail                    │                  │
│     │ • Run STT for transcript               │                  │
│     │ • Upload final to S3                    │                  │
│     │                                         │                  │
│     │ Processing time: ~0.5x real-time        │                  │
│     │ (40 min meeting → 20 min processing)    │                  │
│     └────────────────────────────────────────┘                  │
│                                                                   │
│  4. STORAGE:                                                     │
│     S3 path: s3://recordings/{org_id}/{meeting_id}/              │
│       ├── raw/                                                    │
│       │   ├── audio_user1.opus                                   │
│       │   ├── video_user1.h264                                   │
│       │   └── ...                                                 │
│       ├── processed/                                              │
│       │   ├── meeting_1080p.mp4                                  │
│       │   ├── meeting_720p.mp4                                   │
│       │   ├── meeting_audio.m4a                                  │
│       │   └── thumbnail.jpg                                       │
│       ├── transcript/                                             │
│       │   ├── transcript.json (timestamped)                      │
│       │   ├── transcript.vtt (subtitles)                         │
│       │   └── chapters.json                                       │
│       └── metadata.json                                           │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

### 7.4 TURN/STUN Infrastructure

- **STUN**: Lightweight, helps client discover its public IP/port. Stateless.
- **TURN**: Heavy relay, used when direct P2P/SFU connection fails (symmetric NAT, corporate firewalls)
- **Deployment**: TURN on TCP 443 (looks like HTTPS to firewalls)
- **Capacity**: Each TURN server relays ~2000 streams
- **Selection**: Client tries direct → STUN → TURN (ICE negotiation)
- **Authentication**: Short-lived credentials generated per session (HMAC-based)

## 8. Deep Dive Components

### 8.1 Adaptive Bitrate & Congestion Control (Deep Dive)

```
┌─────────────────────────────────────────────────────────────────┐
│           ADAPTIVE BITRATE CONTROL LOOP                          │
│                                                                   │
│  Input signals:                                                  │
│  • TWCC feedback (packet delay gradient)                         │
│  • RTCP Receiver Reports (packet loss %)                        │
│  • PLI/FIR requests (keyframe requests = quality issue)         │
│  • CPU usage on sender                                           │
│                                                                   │
│  Algorithm (Sender-side GCC):                                    │
│  ┌─────────────────────────────────────────────────────┐        │
│  │                                                       │        │
│  │  estimated_bw = delay_based_estimate()               │        │
│  │  if (packet_loss > 10%):                             │        │
│  │      target_bw = estimated_bw * 0.7                  │        │
│  │  elif (packet_loss > 2%):                            │        │
│  │      target_bw = estimated_bw * 0.9                  │        │
│  │  else:                                               │        │
│  │      target_bw = estimated_bw * 1.05  // probe up   │        │
│  │                                                       │        │
│  │  target_bw = clamp(target_bw, MIN_BW, MAX_BW)       │        │
│  │  encoder.setBitrate(target_bw)                        │        │
│  │                                                       │        │
│  │  // Simulcast layer selection on SFU side:            │        │
│  │  if (receiver_bw > 1.5 Mbps): forward HIGH layer     │        │
│  │  elif (receiver_bw > 500 Kbps): forward MEDIUM       │        │
│  │  else: forward LOW layer                              │        │
│  │                                                       │        │
│  └─────────────────────────────────────────────────────┘        │
│                                                                   │
│  Adaptation Timeline Example:                                    │
│  t=0s:   Good network → 720p high quality                       │
│  t=5s:   Congestion detected → switch to 360p medium            │
│  t=10s:  Severe loss → switch to 180p low + audio priority      │
│  t=15s:  Recovery → probe up to 360p                             │
│  t=20s:  Stable → back to 720p                                   │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

### 8.2 Active Speaker Detection (Deep Dive)

```
Algorithm: Server-side Voice Activity Detection (VAD)

Input: Audio levels from all participants (extracted from RTP header extensions)

Processing (every 100ms):
1. Calculate audio energy per participant (dBFS)
2. Apply voice activity detection threshold (-40 dBFS)
3. Smooth with exponential moving average (α = 0.7)
4. Rank participants by smoothed audio level
5. Apply hysteresis: speaker must be active for 300ms before switching
6. Maximum switch rate: once per 2 seconds (prevents rapid flipping)

Output:
- Active speaker ID → clients reorder video layout
- Top-3 speakers → SFU forwards their HIGH simulcast layer
- Non-speakers → SFU forwards LOW layer (saves bandwidth)

Code:
```python
class ActiveSpeakerDetector:
    def __init__(self):
        self.levels = {}           # user_id → smoothed level
        self.active_since = {}     # user_id → timestamp
        self.current_speaker = None
        self.last_switch = 0
        self.ALPHA = 0.7
        self.THRESHOLD_DB = -40
        self.SWITCH_DELAY_MS = 300
        self.MIN_SWITCH_INTERVAL_MS = 2000
    
    def update(self, user_id, audio_level_db, timestamp):
        # Exponential smoothing
        prev = self.levels.get(user_id, -100)
        self.levels[user_id] = self.ALPHA * audio_level_db + (1 - self.ALPHA) * prev
        
        # Voice activity check
        if self.levels[user_id] > self.THRESHOLD_DB:
            if user_id not in self.active_since:
                self.active_since[user_id] = timestamp
        else:
            self.active_since.pop(user_id, None)
        
        # Speaker switch logic
        if (timestamp - self.last_switch) < self.MIN_SWITCH_INTERVAL_MS:
            return self.current_speaker
        
        # Find loudest active speaker
        candidates = [
            (uid, self.levels[uid]) for uid, start in self.active_since.items()
            if (timestamp - start) >= self.SWITCH_DELAY_MS
        ]
        
        if candidates:
            new_speaker = max(candidates, key=lambda x: x[1])[0]
            if new_speaker != self.current_speaker:
                self.current_speaker = new_speaker
                self.last_switch = timestamp
        
        return self.current_speaker
```

### 8.3 End-to-End Encryption (Deep Dive)

```
┌─────────────────────────────────────────────────────────────────┐
│                 E2EE Architecture (Insertable Streams)            │
│                                                                   │
│  Problem: SFU needs to forward encrypted media but shouldn't    │
│           be able to decrypt content                              │
│                                                                   │
│  Solution: Double encryption                                     │
│  Layer 1: SRTP (transport encryption, SFU can decrypt)          │
│  Layer 2: E2EE frame encryption (only participants can decrypt) │
│                                                                   │
│  Flow:                                                           │
│  Sender:                                                         │
│    Raw frame → E2EE encrypt (inner) → SRTP encrypt (outer) → SFU│
│                                                                   │
│  SFU:                                                            │
│    SRTP decrypt (outer) → [E2EE encrypted blob] → SRTP encrypt → Recv│
│    SFU can route but CANNOT read the actual media content        │
│                                                                   │
│  Receiver:                                                       │
│    SRTP decrypt (outer) → E2EE decrypt (inner) → Raw frame      │
│                                                                   │
│  Key Exchange:                                                   │
│  • Each participant generates ephemeral keys per meeting         │
│  • Key distribution via MLS (Messaging Layer Security) protocol  │
│  • Ratcheting: keys rotate periodically for forward secrecy      │
│  • When participant joins/leaves: key rotation triggered          │
│                                                                   │
│  Trade-offs with E2EE:                                           │
│  ✗ No server-side recording                                      │
│  ✗ No live transcription                                         │
│  ✗ No server-side noise cancellation                             │
│  ✗ No SFU-based simulcast layer switching (workaround: SVC)     │
│  ✓ Maximum privacy                                               │
│  ✓ Compliance with strict security requirements                  │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

## 9. Component Optimization

### 9.1 Kafka (Event Processing)

```yaml
# Meeting events topic
meeting-events:
  partitions: 32
  replication.factor: 3
  retention.ms: 604800000     # 7 days
  compression.type: lz4
  # Partition by meeting_id for ordering within a meeting

# Recording events
recording-events:
  partitions: 16
  replication.factor: 3
  retention.ms: 2592000000    # 30 days

# Analytics events (high volume)
media-quality-events:
  partitions: 64
  replication.factor: 2
  retention.ms: 86400000      # 1 day
  compression.type: zstd
  # High volume: quality metrics every 5 seconds per participant
```

### 9.2 Caching Strategy

```
Layer 1: Client-side cache
  - Meeting metadata (title, settings) - cached until meeting starts
  - User profiles (name, avatar) - cached 1 hour
  - ICE server credentials - cached per session

Layer 2: Edge cache (CDN)
  - Static assets (JS/CSS/images)
  - Recording playback (HLS segments)
  - Avatar images, meeting backgrounds

Layer 3: Redis (application cache)
  - Live meeting state: TTL = meeting duration
  - User session tokens: TTL = 24 hours
  - Media server load: TTL = 10 seconds
  - TURN credentials: TTL = session duration
  - Meeting participant list: TTL = meeting duration

Layer 4: Local in-process cache (per SFU)
  - Participant track subscriptions
  - Active speaker state
  - Bandwidth estimates per connection
```

### 9.3 WebSocket Optimization

```
Signaling WebSocket:
- Use binary protocol (Protobuf over WS) for signaling messages
- Heartbeat: 15 second ping/pong
- Compression: permessage-deflate for text messages
- Connection pooling: reuse WS for multiple meeting signals
- Graceful migration: during SFU failover, signal new SFU via WS

Media Transport (UDP):
- SO_REUSEPORT for multi-core UDP socket distribution
- GRO (Generic Receive Offload) for batch packet processing
- XDP (eXpress Data Path) for kernel-bypass packet forwarding
- DSCP marking for QoS prioritization in enterprise networks
- ECN (Explicit Congestion Notification) for early congestion detection
```

### 9.4 Database Optimization

```sql
-- PostgreSQL: Partition meetings by month for performance
CREATE TABLE meetings (
    meeting_id UUID,
    created_at TIMESTAMP DEFAULT NOW(),
    ...
) PARTITION BY RANGE (created_at);

CREATE TABLE meetings_2025_05 PARTITION OF meetings
    FOR VALUES FROM ('2025-05-01') TO ('2025-06-01');

-- Index for finding live meetings quickly
CREATE INDEX CONCURRENTLY idx_live_meetings 
    ON meetings(status, media_server_region) 
    WHERE status = 'live';

-- ClickHouse: Meeting quality analytics
CREATE TABLE meeting_quality_metrics (
    meeting_id       UUID,
    participant_id   UUID,
    timestamp        DateTime64(3),
    audio_bitrate    UInt32,
    video_bitrate    UInt32,
    packet_loss_pct  Float32,
    jitter_ms        Float32,
    rtt_ms           UInt32,
    resolution       LowCardinality(String),
    fps              UInt8,
    cpu_usage_pct    UInt8
) ENGINE = MergeTree()
PARTITION BY toYYYYMMDD(timestamp)
ORDER BY (meeting_id, participant_id, timestamp)
TTL timestamp + INTERVAL 30 DAY;
```

### 9.5 S3 / Storage Optimization

```
Recording Storage Strategy:
1. Hot tier (S3 Standard): First 7 days - frequent playback
2. Warm tier (S3 IA): 7-90 days - occasional access
3. Cold tier (S3 Glacier): >90 days - archival/compliance

Lifecycle Policy:
{
  "Rules": [
    {"Transition": [
      {"Days": 7, "StorageClass": "STANDARD_IA"},
      {"Days": 90, "StorageClass": "GLACIER_INSTANT"},
      {"Days": 365, "StorageClass": "GLACIER_DEEP_ARCHIVE"}
    ]},
    {"Expiration": {"Days": 730}}  // Auto-delete after 2 years
  ]
}

Playback Optimization:
- Store recordings in HLS format (chunked .ts segments + .m3u8 manifest)
- CDN caches popular recordings at edge
- Byte-range requests for seeking without downloading full file
- Adaptive bitrate playlist (multiple quality variants)
```

### 9.6 Flink (Real-time Quality Analytics)

```java
// Real-time meeting quality monitoring
StreamExecutionEnvironment env = StreamExecutionEnvironment.getExecutionEnvironment();

DataStream<QualityMetric> metrics = env
    .addSource(new FlinkKafkaConsumer<>("media-quality-events", schema, props));

// Detect degraded meetings in real-time
metrics
    .keyBy(QualityMetric::getMeetingId)
    .window(SlidingEventTimeWindows.of(Time.seconds(30), Time.seconds(5)))
    .aggregate(new MeetingQualityAggregator())
    .filter(agg -> agg.getAvgPacketLoss() > 5.0 || agg.getAvgJitter() > 50)
    .addSink(new QualityAlertSink());  // Trigger SFU migration or TURN fallback

// Real-time concurrent meeting count per region
metrics
    .map(m -> new RegionMeeting(m.getRegion(), m.getMeetingId()))
    .keyBy(RegionMeeting::getRegion)
    .window(TumblingEventTimeWindows.of(Time.minutes(1)))
    .aggregate(new UniqueCountAggregator())
    .addSink(new CapacityDashboardSink());
```

## 10. Observability

### 10.1 Key Metrics

```yaml
# Meeting Metrics
zoom_meetings_active{region, plan_type}                    # Gauge
zoom_meetings_started_total{region}                        # Counter
zoom_meeting_duration_seconds                              # Histogram
zoom_participants_active{region}                           # Gauge
zoom_participants_joined_total{region, device_type}        # Counter

# Media Quality Metrics (per participant, sampled)
zoom_media_packet_loss_pct{direction, media_type}          # Histogram
zoom_media_jitter_ms{direction, media_type}                # Histogram
zoom_media_rtt_ms{region_pair}                             # Histogram
zoom_media_bitrate_bps{direction, media_type, quality}     # Gauge
zoom_media_fps{quality}                                     # Histogram
zoom_media_resolution{quality}                              # Gauge

# SFU Metrics
zoom_sfu_connections_active{server_id}                      # Gauge
zoom_sfu_cpu_usage{server_id}                               # Gauge
zoom_sfu_bandwidth_bps{server_id, direction}                # Gauge
zoom_sfu_rooms_active{server_id}                            # Gauge
zoom_sfu_cascade_latency_ms{src_region, dst_region}         # Histogram

# Signaling Metrics
zoom_signaling_connections{server_id}                       # Gauge
zoom_signaling_latency_ms{message_type}                    # Histogram
zoom_ice_negotiation_duration_ms                            # Histogram
zoom_ice_candidate_type_selected{type}                      # Counter (host/srflx/relay)

# Recording Metrics
zoom_recording_active{region}                               # Gauge
zoom_recording_processing_duration_ratio                    # Histogram (processing_time/meeting_duration)
zoom_recording_storage_bytes{tier}                          # Gauge

# Infrastructure
zoom_turn_relay_active{server_id}                           # Gauge
zoom_turn_bandwidth_bps{server_id}                          # Gauge
zoom_cdn_cache_hit_ratio{region}                            # Gauge
```

### 10.2 Alerting

| Alert | Condition | Severity | Action |
|---|---|---|---|
| Meeting join failure rate | >2% failures in 5 min | P1 | Check signaling/SFU allocation |
| Media quality degraded (region) | >10% participants with >5% loss | P1 | Check network, scale TURN |
| SFU capacity critical | >85% CPU on >50% of fleet | P1 | Scale SFU fleet, redirect traffic |
| Recording pipeline backlog | >10K unprocessed recordings | P2 | Scale recording workers |
| TURN relay saturation | >80% bandwidth on TURN fleet | P2 | Scale TURN, check network paths |
| ICE negotiation slow | p99 > 10 seconds | P2 | Check STUN/TURN availability |
| Cross-region cascade latency | >100ms between SFUs | P3 | Check inter-region network |

## 11. Considerations and Assumptions

### 11.1 Key Assumptions

| # | Assumption | Impact |
|---|---|---|
| 1 | Average meeting has 8 participants | SFU capacity planning |
| 2 | 85% of connections succeed P2P/SFU-direct, 15% need TURN | TURN fleet sizing |
| 3 | 70% of participants use video, 95% use audio | Bandwidth planning |
| 4 | Peak hours: 9-11 AM and 2-4 PM per timezone | Capacity staggered globally |
| 5 | Enterprise users need higher quality than free tier | Resource allocation per plan |
| 6 | 10% of meetings are recorded | Recording infrastructure sizing |
| 7 | Average network: 10 Mbps down, 5 Mbps up | Simulcast layer selection |
| 8 | Mobile data: 5 Mbps down, 2 Mbps up | Lower default quality for mobile |

### 11.2 Trade-offs

| Decision | Choice | Trade-off |
|---|---|---|
| SFU vs MCU | SFU | Lower latency but more client bandwidth needed |
| Simulcast vs SVC | Simulcast (H264) + SVC (VP9) | Wider codec support vs better adaptation |
| Recording: real-time vs post | Post-processing composition | Higher quality output but delayed availability |
| E2EE | Optional per-meeting | Maximum privacy sacrifices server-side features |
| Global vs regional | Regional SFU + cross-region cascade | Lower intra-region latency, some cross-region lag |
| UDP vs TCP for media | UDP primary, TCP 443 fallback | Better media quality but may be blocked by firewalls |

### 11.3 Security

| Concern | Implementation |
|---|---|
| Authentication | OAuth 2.0 + JWT for API, short-lived tokens for media sessions |
| Transport security | DTLS 1.2 for media (mandatory in WebRTC), TLS 1.3 for signaling |
| Media encryption | SRTP with AES-128-CM (standard), optional E2EE layer |
| Meeting security | Passwords, waiting rooms, host approval, meeting locks |
| Abuse prevention | Rate limiting, meeting bomb detection, automatic mute/remove |
| Data sovereignty | Regional media processing, no data leaving region |
| Compliance | SOC 2, HIPAA (healthcare), FedRAMP (government) |
