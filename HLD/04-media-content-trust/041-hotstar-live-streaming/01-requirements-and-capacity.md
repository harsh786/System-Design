# 01 - Requirements and Capacity Estimation

## 1. Problem Statement

Design a streaming platform capable of serving **25M+ concurrent live viewers** for premium sports content (cricket) while simultaneously serving VOD content to millions, with sub-2-second stream start time, near-zero rebuffering, and graceful handling of traffic spikes that go from 0 to 25M users in under 10 minutes.

---

## 2. Functional Requirements

| # | Requirement | Description |
|---|-------------|-------------|
| FR1 | Live Video Streaming | Broadcast live sports/events to 25M+ concurrent viewers with ABR |
| FR2 | Video-on-Demand (VOD) | Stream movies, series, originals with multi-language audio |
| FR3 | Multi-Language Commentary | 8+ simultaneous audio tracks for live sports (Hindi, English, Tamil, Telugu, etc.) |
| FR4 | Adaptive Bitrate (ABR) | Seamless quality switching from 240p to 4K based on network |
| FR5 | Multi-Device Playback | Support 500+ device types (smart TVs, mobile, web, Fire Stick, Chromecast) |
| FR6 | Live Scoreboard/Overlay | Real-time score updates, ball-by-ball commentary overlay |
| FR7 | Watch Party | Synchronized viewing with friends |
| FR8 | Interactive Features | Polls, predictions, emojis during live events |
| FR9 | DVR/Catch-up | Rewind live stream, watch highlights, catch-up from beginning |
| FR10 | Subscription Management | Free tier (with ads), VIP (sports), Premium (Disney+ content) |
| FR11 | Offline Downloads | Download VOD content with DRM for offline viewing |
| FR12 | Content Recommendations | ML-based personalized content discovery |
| FR13 | Ad Insertion (SSAI) | Server-side ad insertion for free-tier users during live events |
| FR14 | Concurrent Stream Limits | Enforce device limits per subscription (2-4 simultaneous) |
| FR15 | Regional Content | Geo-restricted content + regional language support |

---

## 3. Non-Functional Requirements

| Requirement | Target | Justification |
|-------------|--------|---------------|
| Availability | 99.99% (streaming), 99.95% (control plane) | Any downtime during IPL = millions in lost revenue |
| Stream Start Time | < 2 seconds (p95) | Users abandon after 3s wait |
| Rebuffer Ratio | < 0.1% of play time | Key QoE metric |
| Glass-to-Glass Latency | < 10 seconds (live sports) | Must be close to TV broadcast |
| Traffic Spike Handling | 0 → 25M in 10 minutes | Match start creates thundering herd |
| API Latency | < 50ms p99 (hot path) | Manifest requests, token validation |
| Scalability | 25M+ concurrent, 500M+ registered users | India's scale |
| CDN Egress | 100+ Tbps peak | Each viewer at 3-5 Mbps average |
| Fault Tolerance | Zero single points of failure | Multi-CDN, multi-region, multi-cloud |
| Device Coverage | 500+ device types | Feature phones to 4K smart TVs |
| Network Resilience | Work on 2G/3G/4G/5G/WiFi | India's heterogeneous network landscape |
| Cold Start (app open → play) | < 5 seconds | Including app init + first frame |

---

## 4. Capacity Estimation

### 4.1 Traffic Profile

```
┌─────────────────────────────────────────────────────────────┐
│              HOTSTAR TRAFFIC PATTERN (IPL Day)                │
│                                                               │
│  Concurrent    ▲                                              │
│  Users (M)     │                     ╭──────╮                 │
│                │                    ╱        ╲  Match 2       │
│  25M ─────────│───────────────────╱──────────╲──────         │
│                │       ╭────╮    ╱              ╲             │
│  15M ─────────│──────╱──────╲──╱────────────────╲───         │
│                │    ╱        ╲╱                    ╲          │
│  10M ─────────│──╱───────────────────────────────── ╲──      │
│                │╱                                      ╲      │
│  5M  ─────────│────────────────────────────────────────╲─    │
│                │─── VOD baseline ───────────────────────────   │
│  2M  ─────────│──────────────────────────────────────────    │
│                └────┬────┬────┬────┬────┬────┬────┬────►     │
│                   10AM  2PM  4PM  6PM  8PM  10PM 12AM        │
│                          Match 1      Match 2                 │
└─────────────────────────────────────────────────────────────┘
```

### 4.2 Peak Traffic Numbers (IPL Final)

```
Registered Users:                    500,000,000
DAU (normal day):                    50,000,000
DAU (IPL match day):                 150,000,000
Peak Concurrent Viewers:             25,300,000
Peak Concurrent (VOD + Live):        30,000,000

Stream Starts/second (match start):  500,000
Manifest Requests/second:            25M × 1 req/2sec = 12,500,000
Token Validation/second:             500,000 (new sessions)
API Requests/second (total):         10,000,000+
WebSocket Connections (interactivity): 20,000,000
```

### 4.3 Bandwidth Estimation

```
Average bitrate per viewer:          4 Mbps (mix of mobile + TV)
Peak concurrent:                     25,000,000

Peak CDN Egress = 25M × 4 Mbps = 100 Tbps

Breakdown by quality:
  - 4K (2%):     500K × 15 Mbps  = 7.5 Tbps
  - 1080p (15%): 3.75M × 8 Mbps  = 30 Tbps
  - 720p (35%):  8.75M × 4 Mbps  = 35 Tbps
  - 480p (30%):  7.5M × 2 Mbps   = 15 Tbps
  - 360p (13%):  3.25M × 1 Mbps  = 3.25 Tbps
  - 240p (5%):   1.25M × 0.5 Mbps = 0.625 Tbps
                                    ─────────
  Total:                            ~91.4 Tbps (matches estimate)

Multi-language audio (separate tracks):
  25M × 128 Kbps = 3.2 Tbps additional

Total with audio: ~95-105 Tbps peak
```

### 4.4 Storage Estimation

```
Live Stream Storage (rolling buffer):
  - 1 live feed × 8 quality levels × 8 languages = 64 variants
  - Each at avg 4 Mbps × 4 hours match = 7.2 GB per variant
  - 64 variants × 7.2 GB = 460 GB per match
  - With DVR buffer (full match): ~500 GB per match

VOD Library:
  - 100,000 titles (movies + episodes)
  - Average 8 quality levels × 3 audio tracks = 24 variants per title
  - Average 4 GB per variant = 96 GB per title
  - Total: 100K × 96 GB = 9.6 PB
  - With replication (3 regions): 28.8 PB

Metadata + User Data:
  - User profiles: 500M × 5KB = 2.5 TB
  - Watch history: 500M × 500 entries × 200B = 50 TB
  - Content metadata: 100K × 100KB = 10 GB
  - Recommendations cache: 500M × 1KB = 500 GB
```

### 4.5 Compute Estimation

```
Live Transcoding:
  - 1 source feed × 8 quality levels = 8 parallel transcodes
  - With 8 languages: 8 × 8 = 64 transcodes (audio muxed)
  - Actually: 8 video transcodes + 8 audio pass-throughs
  - GPU requirement: 8 × NVIDIA T4 (1 per quality level)
  - Redundancy (3x): 24 GPUs for live transcoding

Manifest Generation:
  - 12.5M requests/sec ÷ 50K req/sec per node = 250 nodes
  - With 3x headroom: 750 manifest server nodes

API Gateway:
  - 10M RPS ÷ 100K RPS per node = 100 nodes
  - With 2x headroom: 200 API gateway nodes

WebSocket Servers (Interactivity):
  - 20M connections ÷ 500K connections per node = 40 nodes
  - With failover: 80 WebSocket nodes

Token/Auth Service:
  - 500K validations/sec ÷ 50K per node = 10 nodes
  - With headroom: 30 auth nodes

CDN Edge Nodes:
  - 100 Tbps ÷ 40 Gbps per edge node = 2,500 edge nodes minimum
  - Distributed across 200+ PoPs in India
```

### 4.6 Memory/Cache Estimation

```
Session State Cache (Redis):
  - 30M concurrent sessions × 2KB = 60 GB
  - Distributed across 20 Redis cluster nodes

Content Metadata Cache:
  - 100K titles × 100KB = 10 GB (fits single node, replicated)

Manifest Cache (edge):
  - 8 quality × 8 language × 2-sec segments = 128 segments live
  - 128 × 2MB avg = 256 MB per edge (trivial)

User Auth Token Cache:
  - 30M active tokens × 500B = 15 GB

CDN Hot Content Cache (per edge):
  - Last 30 seconds of live = 30 × 64 variants × 2MB = 3.84 GB
  - Top 100 VOD titles: 100 × 24 variants × first 5 min = 72 GB
  - Total per edge node: ~80 GB (fits in RAM)
```

---

## 5. Traffic Spike Characteristics (The Thundering Herd Problem)

### 5.1 IPL Match Start Pattern

```
T-30 min:    2M users (pre-show, warming up)
T-10 min:    5M users (toss, team announcement)
T-5 min:     8M users (national anthem, players walking in)
T-0 (first ball): 15M users (massive spike)
T+5 min:     20M users (word-of-mouth, notifications)
T+15 min:    25M users (peak, everyone settled)

Ramp Rate: 13M new users in 5 minutes = 43,000 new stream starts/second
```

### 5.2 Wicket/Six Moment Pattern

```
When a wicket falls or six is hit:
- Social media explodes
- Users who paused resume playback
- New users rush in
- Spike of 2-5M additional viewers in 60 seconds
- Manifest request spike: 2-5M instant requests
- DVR rewind requests spike: 5M "show me that again"

This creates a SECONDARY thundering herd on top of steady state.
```

### 5.3 Key Insight: Why This is Harder Than Netflix

| Dimension | Netflix | Hotstar (Live) |
|-----------|---------|----------------|
| Traffic pattern | Smooth, predictable | Extreme spikes (100x in minutes) |
| Content popularity | Long tail distribution | Single stream gets ALL traffic |
| Cacheability | Highly cacheable (same content) | 2-second segments expire immediately |
| Failure impact | One user affected | 25M users simultaneously affected |
| Latency tolerance | 5-10 seconds buffering OK | Must be near real-time (< 10s) |
| Scaling time | Hours to scale | Must handle spike in seconds |
| CDN warming | Content pre-pushed | Real-time origin fetches |
