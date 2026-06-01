# 07 - API Design

## 1. API Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                    HOTSTAR API ARCHITECTURE                            │
│                                                                       │
│  External APIs (Client-facing):     Protocol: HTTPS + HTTP/2          │
│  Internal APIs (Service-to-Service): Protocol: gRPC (Protobuf)        │
│  Real-time APIs (Interactive):      Protocol: WebSocket + SSE          │
│  Video Delivery:                    Protocol: HLS/DASH over HTTPS      │
│                                                                       │
│  Authentication: JWT (RS256) with short-lived access tokens (15 min)  │
│  Rate Limiting: Token bucket (per user + per device + per IP)         │
│  Versioning: URL path (/v1/, /v2/) with sunset headers                │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 2. Playback APIs (Critical Path)

### 2.1 Initialize Playback Session

```
POST /api/v1/playback/init
Authorization: Bearer <access_token>
X-Device-ID: device_abc123
X-App-Version: 12.5.3
X-Platform: android

Request Body:
{
    "content_type": "live",                    // "live" | "vod"
    "event_id": 98765432,                      // For live events
    "content_id": null,                        // For VOD
    "preferred_language": "hi",                // Commentary language
    "preferred_quality": "auto",               // "auto" | "240p" | ... | "4k"
    "device_info": {
        "type": "mobile",
        "os": "android",
        "os_version": "14",
        "model": "Samsung Galaxy S23",
        "screen_width": 1080,
        "screen_height": 2340,
        "hdr_capable": true,
        "widevine_level": "L1",
        "connection_type": "4g",
        "isp": "jio",
        "city": "Mumbai",
        "state": "MH"
    },
    "data_saver": false,
    "low_latency_mode": true
}

Response (200 OK):
{
    "session_id": "sess_7f3a2b1c-4d5e-6f7a-8b9c-0d1e2f3a4b5c",
    "playback_url": "https://edge-mum-jio.hotstar.com/live/98765432/hi/master.m3u8",
    "token": "eyJhbGciOiJSUzI1NiJ9...",       // Playback token (5 min expiry)
    "token_refresh_url": "/api/v1/playback/token/refresh",
    "token_expires_in": 300,
    "drm": {
        "type": "widevine",
        "license_url": "https://drm.hotstar.com/license/widevine",
        "certificate_url": "https://drm.hotstar.com/cert/widevine"
    },
    "cdn_config": {
        "primary": "https://edge-mum-jio.hotstar.com",
        "fallback": [
            "https://edge-mum-akamai.hotstar.com",
            "https://edge-mum-cf.hotstar.com"
        ],
        "failover_threshold_ms": 1500
    },
    "abr_config": {
        "max_quality": "1080p",                 // Based on device + subscription
        "start_quality": "480p",                // Progressive start
        "min_buffer_sec": 4,
        "max_buffer_sec": 10,
        "bandwidth_estimation_window": 3
    },
    "features": {
        "dvr_enabled": true,
        "dvr_window_sec": 14400,
        "low_latency_enabled": true,
        "ads_enabled": false,                   // Premium subscriber
        "interactive_enabled": true,
        "scoreboard_enabled": true
    },
    "concurrent_streams": {
        "current": 1,
        "max_allowed": 2
    }
}
```

### 2.2 Refresh Playback Token

```
POST /api/v1/playback/token/refresh
Authorization: Bearer <access_token>

Request Body:
{
    "session_id": "sess_7f3a2b1c-4d5e-6f7a-8b9c-0d1e2f3a4b5c",
    "current_token": "eyJhbGciOiJSUzI1NiJ9..."
}

Response (200 OK):
{
    "token": "eyJhbGciOiJSUzI1NiJ9...(new_token)",
    "expires_in": 300
}

// Called every 4.5 minutes (before 5-min expiry)
// If this fails → player retries 3× then re-inits session
// Token is validated at CDN edge (JWT signature check, no origin call)
```

### 2.3 Report Playback Heartbeat (QoE Metrics)

```
POST /api/v1/playback/heartbeat
Authorization: Bearer <access_token>

Request Body:
{
    "session_id": "sess_7f3a2b1c-4d5e-6f7a-8b9c-0d1e2f3a4b5c",
    "timestamp": "2024-05-15T19:45:32.123Z",
    "metrics": {
        "current_bitrate_kbps": 4200,
        "current_quality": "720p",
        "buffer_length_sec": 6.2,
        "dropped_frames": 0,
        "latency_from_live_sec": 8.5,
        "bandwidth_estimated_kbps": 12000,
        "rebuffer_events_since_last": 0,
        "rebuffer_duration_ms_since_last": 0,
        "bitrate_switches_since_last": 1,
        "cdn_used": "jio_cdn",
        "edge_pop": "mum-jio-03",
        "connection_type": "4g",
        "signal_strength_dbm": -75
    }
}

Response (200 OK):
{
    "ack": true,
    "server_time": "2024-05-15T19:45:32.456Z",
    "commands": []          // Can push commands: "switch_cdn", "reduce_quality", etc.
}

// Sent every 10 seconds during playback
// Batched and async (non-blocking for video playback)
// If network poor, batches accumulate and send when possible
```

### 2.4 End Playback Session

```
POST /api/v1/playback/end
Authorization: Bearer <access_token>

Request Body:
{
    "session_id": "sess_7f3a2b1c-4d5e-6f7a-8b9c-0d1e2f3a4b5c",
    "reason": "user_exit",          // "user_exit" | "error" | "content_ended" | "device_limit"
    "final_metrics": {
        "total_watch_duration_sec": 3847,
        "total_rebuffer_count": 2,
        "total_rebuffer_duration_ms": 1200,
        "avg_bitrate_kbps": 3800,
        "peak_bitrate_kbps": 8000,
        "quality_distribution": {
            "1080p": 0.35,
            "720p": 0.55,
            "480p": 0.10
        },
        "startup_time_ms": 1650
    }
}

Response (200 OK):
{
    "ack": true,
    "watch_progress_saved": true
}
```

---

## 3. Content & Discovery APIs

### 3.1 Get Live Events

```
GET /api/v1/events/live?sport=cricket&page=1&limit=10
Authorization: Bearer <access_token>

Response (200 OK):
{
    "events": [
        {
            "event_id": 98765432,
            "title": "CSK vs MI - IPL 2024 Match 35",
            "title_localized": {
                "hi": "CSK बनाम MI - IPL 2024 मैच 35",
                "ta": "CSK vs MI - IPL 2024 போட்டி 35"
            },
            "sport": "cricket",
            "tournament": "IPL 2024",
            "teams": {
                "home": {"name": "Chennai Super Kings", "short": "CSK", "logo_url": "..."},
                "away": {"name": "Mumbai Indians", "short": "MI", "logo_url": "..."}
            },
            "status": "live",
            "started_at": "2024-05-15T19:30:00+05:30",
            "current_viewers": 22453000,
            "commentary_languages": ["hi", "en", "ta", "te", "kn", "bn", "ml", "mr"],
            "is_premium": true,
            "thumbnail_url": "https://img.hotstar.com/events/98765432/live_thumb.jpg",
            "match_info": {
                "innings": 2,
                "score": "CSK: 185/4 (18.2 ov) | MI: 120/3 (14 ov)",
                "status_text": "MI need 66 runs from 36 balls"
            }
        }
    ],
    "pagination": {
        "page": 1,
        "limit": 10,
        "total": 3,
        "has_next": false
    }
}
```

### 3.2 Search Content

```
GET /api/v1/search?q=dhoni&type=all&lang=hi,en&page=1&limit=20
Authorization: Bearer <access_token>

Response (200 OK):
{
    "results": {
        "live_events": [
            {
                "event_id": 98765432,
                "title": "CSK vs MI (Dhoni batting)",
                "match_type": "live",
                "relevance_score": 0.98
            }
        ],
        "vod_content": [
            {
                "content_id": "uuid-xyz",
                "title": "Dhoni: The Untold Story",
                "type": "movie",
                "year": 2016,
                "rating": "UA",
                "thumbnail_url": "..."
            }
        ],
        "highlights": [
            {
                "content_id": "uuid-abc",
                "title": "Dhoni's 5 Best IPL Sixes",
                "duration_sec": 180,
                "thumbnail_url": "..."
            }
        ]
    },
    "query_time_ms": 45,
    "total_results": 127
}
```

---

## 4. Interactive/Real-Time APIs

### 4.1 WebSocket Connection (Emoji/Polls/Score)

```
// WebSocket connection for real-time features
WS wss://rt.hotstar.com/v1/events/98765432/interactive
Headers:
  Authorization: Bearer <access_token>
  X-Session-ID: sess_7f3a2b1c...

// --- Client → Server Messages ---

// Send Emoji Reaction
{
    "type": "emoji",
    "payload": {
        "emoji_id": "six_fire",
        "timestamp": "2024-05-15T19:45:32.123Z"
    }
}

// Submit Poll Answer
{
    "type": "poll_response",
    "payload": {
        "poll_id": "poll_12345",
        "option_id": 2
    }
}

// --- Server → Client Messages ---

// Emoji Burst (aggregated, sent every 500ms)
{
    "type": "emoji_burst",
    "payload": {
        "emojis": [
            {"emoji_id": "six_fire", "count": 234000},
            {"emoji_id": "wicket_shocked", "count": 89000},
            {"emoji_id": "clap", "count": 156000}
        ],
        "total_participants": 18000000,
        "window_ms": 500
    }
}

// Live Score Update (pushed on every ball)
{
    "type": "score_update",
    "payload": {
        "innings": 2,
        "batting_team": "MI",
        "score": "121/3",
        "overs": "14.1",
        "current_batsman": "Rohit Sharma",
        "batsman_score": "45 (32)",
        "bowler": "Jadeja",
        "bowler_figures": "2/28 (3.1)",
        "last_ball": "4 (cover drive)",
        "run_rate": 8.53,
        "required_rate": 11.14
    }
}

// Poll Published
{
    "type": "poll",
    "payload": {
        "poll_id": "poll_12345",
        "question": "Who will win?",
        "options": [
            {"id": 1, "text": "CSK", "votes_pct": 62},
            {"id": 2, "text": "MI", "votes_pct": 38}
        ],
        "total_votes": 8500000,
        "expires_in_sec": 30
    }
}
```

### 4.2 Real-Time Score API (SSE for lightweight clients)

```
GET /api/v1/events/98765432/score/stream
Accept: text/event-stream
Authorization: Bearer <access_token>

// Server-Sent Events Response:
event: ball
data: {"over":"14.2","runs":1,"batsman":"Rohit","bowler":"Jadeja","score":"122/3"}

event: ball
data: {"over":"14.3","runs":6,"batsman":"Rohit","bowler":"Jadeja","score":"128/3","highlight":true}

event: ball  
data: {"over":"14.4","runs":0,"batsman":"Rohit","bowler":"Jadeja","score":"128/3","wicket":false}

event: wicket
data: {"over":"14.5","batsman":"Rohit","bowler":"Jadeja","score":"128/4","dismissal":"caught","how":"c Dhoni b Jadeja","highlight":true}

event: timeout
data: {"type":"strategic","duration_sec":150,"ad_break":true}
```

---

## 5. Authentication & Subscription APIs

### 5.1 Login (Phone OTP - India primary)

```
// Step 1: Request OTP
POST /api/v1/auth/otp/send
{
    "phone": "+919876543210",
    "purpose": "login"
}

Response (200 OK):
{
    "request_id": "otp_req_abc123",
    "expires_in_sec": 300,
    "retry_after_sec": 30
}

// Step 2: Verify OTP
POST /api/v1/auth/otp/verify
{
    "request_id": "otp_req_abc123",
    "phone": "+919876543210",
    "otp": "784523"
}

Response (200 OK):
{
    "access_token": "eyJhbGciOiJSUzI1NiJ9...",
    "refresh_token": "rt_xyz789...",
    "access_token_expires_in": 900,          // 15 minutes
    "refresh_token_expires_in": 2592000,     // 30 days
    "user": {
        "user_id": 123456789,
        "display_name": "Harsh",
        "subscription": {
            "plan": "premium",
            "expires_at": "2024-12-31T23:59:59Z",
            "max_streams": 2
        }
    }
}
```

### 5.2 Check Entitlement

```
GET /api/v1/entitlement/check?content_type=live&event_id=98765432
Authorization: Bearer <access_token>

Response (200 OK):
{
    "entitled": true,
    "reason": "active_premium_subscription",
    "features": {
        "max_quality": "4k",
        "ads_free": true,
        "dvr": true,
        "downloads": true,
        "concurrent_streams": 2
    }
}

// Response if not entitled (402):
{
    "entitled": false,
    "reason": "subscription_required",
    "required_plan": "premium",
    "upgrade_url": "https://www.hotstar.com/subscribe",
    "plans": [
        {"plan": "mobile", "price": "₹149/month", "features": ["mobile_only", "480p"]},
        {"plan": "super", "price": "₹299/month", "features": ["all_devices", "1080p"]},
        {"plan": "premium", "price": "₹499/month", "features": ["all_devices", "4k", "disney+"]}
    ]
}
```

---

## 6. Internal APIs (gRPC)

### 6.1 CDN Routing Service

```protobuf
syntax = "proto3";

service CDNRoutingService {
    // Get optimal CDN endpoint for a user
    rpc GetOptimalCDN(CDNRequest) returns (CDNResponse);
    
    // Report CDN health metrics
    rpc ReportCDNHealth(CDNHealthReport) returns (Ack);
    
    // Trigger traffic shift between CDNs
    rpc ShiftTraffic(TrafficShiftRequest) returns (TrafficShiftResponse);
}

message CDNRequest {
    string user_ip = 1;
    string isp = 2;
    string state = 3;
    string city = 4;
    string device_type = 5;
    int64 event_id = 6;
    string quality_requested = 7;
}

message CDNResponse {
    string primary_endpoint = 1;
    repeated string fallback_endpoints = 2;
    string pop_id = 3;
    string cdn_provider = 4;
    int32 expected_latency_ms = 5;
    map<string, string> headers = 6;     // Custom headers for CDN
}

message CDNHealthReport {
    string cdn_provider = 1;
    string pop_id = 2;
    double load_percentage = 3;
    double error_rate = 4;
    int32 p50_latency_ms = 5;
    int32 p99_latency_ms = 6;
    int64 active_connections = 7;
    double bandwidth_utilized_gbps = 8;
}
```

### 6.2 Transcoder Control Service

```protobuf
syntax = "proto3";

service TranscoderService {
    // Start transcoding for a live event
    rpc StartTranscoding(TranscodeRequest) returns (TranscodeResponse);
    
    // Get transcoder health/status
    rpc GetStatus(StatusRequest) returns (TranscoderStatus);
    
    // Switch to backup feed
    rpc SwitchFeed(FeedSwitchRequest) returns (FeedSwitchResponse);
    
    // Update ABR ladder dynamically
    rpc UpdateABRLadder(ABRLadderUpdate) returns (Ack);
}

message TranscodeRequest {
    int64 event_id = 1;
    string source_url = 2;
    string backup_url = 3;
    string encoding_profile = 4;        // "cricket_hd", "cricket_4k"
    repeated string languages = 5;
    ABRLadder abr_ladder = 6;
    int32 segment_duration_ms = 7;
    bool low_latency = 8;
    string output_bucket = 9;
}

message ABRLadder {
    repeated QualityLevel levels = 1;
}

message QualityLevel {
    string label = 1;                    // "1080p_h264"
    int32 width = 2;
    int32 height = 3;
    int32 bitrate_kbps = 4;
    int32 fps = 5;
    string codec = 6;                    // "h264", "h265", "av1"
    string profile = 7;                  // "high", "main"
}
```

---

## 7. Rate Limiting Strategy

```
┌─────────────────────────────────────────────────────────────────────┐
│              RATE LIMITING CONFIGURATION                               │
│                                                                       │
│  API Endpoint              │ Limit (per user)  │ Burst │ Window       │
│  ─────────────────────────│───────────────────│───────│─────────     │
│  POST /playback/init      │ 10 req/min        │ 3     │ sliding      │
│  POST /playback/heartbeat │ 12 req/min        │ 2     │ sliding      │
│  GET /events/live         │ 30 req/min        │ 5     │ sliding      │
│  GET /search              │ 60 req/min        │ 10    │ sliding      │
│  POST /auth/otp/send      │ 3 req/hour        │ 1     │ fixed        │
│  WS /interactive          │ 30 msg/min        │ 5     │ sliding      │
│  POST /emoji              │ 10 req/min        │ 3     │ sliding      │
│                                                                       │
│  Global limits (per IP):                                              │
│  - 1000 req/min for all APIs combined                                 │
│  - 50 WebSocket connections per IP                                    │
│                                                                       │
│  During IPL Peak (relaxed limits):                                    │
│  - Heartbeat: 6 req/min (reduce frequency)                            │
│  - Interactive: 5 msg/min (throttle emoji spam)                        │
│  - Search: 10 req/min (discourage during peak)                         │
│                                                                       │
│  Implementation: Token bucket algorithm in Redis                       │
│  Key format: rate:{user_id}:{endpoint}:{window}                       │
│  Lua script for atomic check-and-decrement                            │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 8. Error Responses

```json
// 429 Too Many Requests
{
    "error": {
        "code": "RATE_LIMITED",
        "message": "Too many requests. Please retry after 30 seconds.",
        "retry_after_sec": 30
    }
}

// 403 Forbidden (geo-restriction)
{
    "error": {
        "code": "GEO_RESTRICTED",
        "message": "This content is not available in your region.",
        "user_country": "US",
        "allowed_countries": ["IN", "SG", "MY"]
    }
}

// 409 Conflict (concurrent stream limit)
{
    "error": {
        "code": "STREAM_LIMIT_EXCEEDED",
        "message": "Maximum 2 simultaneous streams allowed.",
        "active_sessions": [
            {"device": "Samsung Galaxy S23", "started_at": "2024-05-15T19:30:00Z"},
            {"device": "LG Smart TV", "started_at": "2024-05-15T19:35:00Z"}
        ],
        "action_required": "End one of the active sessions to start a new one."
    }
}

// 503 Service Unavailable (overload protection)
{
    "error": {
        "code": "SERVICE_OVERLOADED",
        "message": "High demand. Please retry shortly.",
        "retry_after_sec": 5,
        "queue_position": 45000           // Optional: show queue position
    }
}
```
