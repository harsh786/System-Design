# 06 - Live Cricket Scaling (IPL Use Case)

## 1. The IPL Challenge - Scale Context

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    THE IPL SCALING CHALLENGE                                       │
│                                                                                   │
│  Why IPL is the hardest streaming problem in the world:                           │
│                                                                                   │
│  ┌────────────────────────────────────────────────────────────────────────┐      │
│  │  1. SINGLE CONTENT, ALL VIEWERS                                         │      │
│  │     Unlike Netflix where load is distributed across 15K titles,          │      │
│  │     ALL 25M viewers want the SAME live feed simultaneously.              │      │
│  │                                                                          │      │
│  │  2. PREDICTABLE BUT EXTREME SPIKES                                       │      │
│  │     0 → 25M viewers in 10 minutes. No time to auto-scale.               │      │
│  │     Must be pre-provisioned.                                             │      │
│  │                                                                          │      │
│  │  3. REAL-TIME (NO BUFFERING AHEAD)                                       │      │
│  │     Can't buffer 30 minutes ahead like Netflix. Content doesn't          │      │
│  │     exist until the moment it happens.                                    │      │
│  │                                                                          │      │
│  │  4. EMOTIONAL CRITICALITY                                                │      │
│  │     A wicket or six happening means: "Show it NOW or users rage-quit."    │      │
│  │     Any buffering during key moments = massive churn.                     │      │
│  │                                                                          │      │
│  │  5. INDIA'S NETWORK HETEROGENEITY                                        │      │
│  │     Users on 2G EDGE to 5G. Feature phones to 4K TVs.                    │      │
│  │     Must work for all. Can't exclude anyone.                              │      │
│  │                                                                          │      │
│  │  6. SIMULTANEOUS FUNCTIONALITY                                           │      │
│  │     Live video + live score + emoji reactions + polls + ads               │      │
│  │     ALL must work under 25M concurrent load.                              │      │
│  └────────────────────────────────────────────────────────────────────────┘      │
│                                                                                   │
│  World Records Set:                                                               │
│  - 2023 IPL Final (CSK vs GT): 25.3M concurrent viewers                          │
│  - 2023 Cricket World Cup Final: 59M concurrent (includes TV + OTT)               │
│  - Most emoji sent in 1 second: 5M+ (during a Dhoni six)                          │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Pre-Scale Architecture (The Key to Zero-Lag)

### 2.1 Scaling Timeline

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                 IPL MATCH DAY - SCALING TIMELINE                                   │
│                                                                                   │
│  ┌────────────────────────────────────────────────────────────────────────────┐  │
│  │ T-7 days: CAPACITY PLANNING                                                 │  │
│  │ ─────────────────────────────                                               │  │
│  │ - Predict expected viewers (ML model based on teams, day, time, rivalry)    │  │
│  │ - Reserve CDN burst capacity from all providers                              │  │
│  │ - Pre-book cloud instances (Reserved/On-Demand mix)                          │  │
│  │ - Alert on-call SRE team, assign dedicated war room                          │  │
│  │ - Predict: "CSK vs MI on Sunday evening = 22M+ viewers"                      │  │
│  └────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                   │
│  ┌────────────────────────────────────────────────────────────────────────────┐  │
│  │ T-24 hours: INFRASTRUCTURE PREP                                             │  │
│  │ ──────────────────────────────────                                          │  │
│  │ - Scale Kubernetes: 500 → 3000 pods for API services                         │  │
│  │ - Scale Redis: add read replicas (20 → 60 nodes)                             │  │
│  │ - Scale Kafka: increase partitions for event topics                           │  │
│  │ - Pre-warm DB connection pools                                               │  │
│  │ - Verify backup transcoder pipeline                                           │  │
│  │ - Run chaos engineering tests (kill random components)                        │  │
│  └────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                   │
│  ┌────────────────────────────────────────────────────────────────────────────┐  │
│  │ T-4 hours: FULL PRE-SCALE                                                   │  │
│  │ ────────────────────────────                                                │  │
│  │ - ALL services scaled to predicted peak (not 50%, not 80% - FULL 100%)      │  │
│  │ - CDN pre-warming begins (synthetic traffic)                                 │  │
│  │ - Feature flags set: disable non-essential features if needed                 │  │
│  │ - Database read replicas fully caught up                                      │  │
│  │ - Circuit breakers configured and tested                                      │  │
│  │ - War room assembled: SRE + Engineering + Product                            │  │
│  └────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                   │
│  ┌────────────────────────────────────────────────────────────────────────────┐  │
│  │ T-1 hour: VALIDATION                                                        │  │
│  │ ────────────────────                                                        │  │
│  │ - Load test with synthetic 5M viewers                                        │  │
│  │ - Verify every component responds within SLO                                  │  │
│  │ - Test failover scenarios (kill primary transcoder)                            │  │
│  │ - Verify CDN routing rules                                                    │  │
│  │ - Check DRM key server capacity                                               │  │
│  │ - Final go/no-go checklist (50-item runbook)                                  │  │
│  └────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                   │
│  ┌────────────────────────────────────────────────────────────────────────────┐  │
│  │ T-0: MATCH START - THUNDERING HERD ARRIVES                                  │  │
│  │ ─────────────────────────────────────────────                               │  │
│  │ - 500K stream starts/second                                                  │  │
│  │ - All pre-scaled capacity absorbs load instantly                              │  │
│  │ - No auto-scaling needed (too slow, already at peak)                          │  │
│  │ - Monitor dashboards: viewer count, rebuffer rate, latency                    │  │
│  │ - CDN orchestrator balances across providers in real-time                     │  │
│  └────────────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Why "Auto-Scale" Doesn't Work Here

```
Traditional auto-scaling:
  Detect high load → Provision new instances → Register → Accept traffic
  Time: 3-5 minutes minimum

IPL reality:
  0 → 15M viewers in 5 minutes
  If you wait to detect load → you're already overwhelmed
  New instances take 2-3 min to provision
  Connection pools need warming
  Caches are cold
  
  By the time auto-scale kicks in, 5M users already had bad experience
  = Massive churn, social media backlash, front-page news

Hotstar's approach: PRE-SCALE EVERYTHING
  - Pay for 25M-viewer capacity even during pre-show (when only 2M are watching)
  - Cost of over-provisioning for 4 hours << cost of 5M users churning
  - "You can't auto-scale your way out of a thundering herd"
```

---

## 3. Graceful Degradation Strategy

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    GRACEFUL DEGRADATION LEVELS                                     │
│                                                                                   │
│  Level 0: NORMAL (all systems healthy)                                            │
│  ┌─────────────────────────────────────────────────────────────────────────┐     │
│  │  - Full functionality: video + interactive + recommendations + ads       │     │
│  │  - All quality levels available (240p - 4K)                              │     │
│  │  - Full DVR (rewind entire match)                                        │     │
│  │  - Real-time polls, emoji, predictions active                            │     │
│  │  - Personalized manifest per user                                        │     │
│  └─────────────────────────────────────────────────────────────────────────┘     │
│                                                                                   │
│  Level 1: ELEVATED LOAD (CDN > 70%, API > 60%)                                   │
│  ┌─────────────────────────────────────────────────────────────────────────┐     │
│  │  SHED:                                                                   │     │
│  │  - Disable recommendation engine (serve static "trending" list)          │     │
│  │  - Reduce analytics reporting frequency (every 30s → every 60s)          │     │
│  │  - Disable non-essential API calls (profile pics, achievements)          │     │
│  │  KEEP:                                                                   │     │
│  │  - Full video quality, all languages, DVR, core interaction              │     │
│  └─────────────────────────────────────────────────────────────────────────┘     │
│                                                                                   │
│  Level 2: HIGH LOAD (CDN > 85%, API > 80%)                                       │
│  ┌─────────────────────────────────────────────────────────────────────────┐     │
│  │  SHED:                                                                   │     │
│  │  - Cap video quality: mobile → 720p max, TV → 1080p max (disable 4K)    │     │
│  │  - Reduce emoji/interaction frequency (batch, don't real-time)           │     │
│  │  - Disable Watch Party feature                                           │     │
│  │  - DVR window reduced (last 30 min only, not full match)                 │     │
│  │  - Reduce manifest update frequency (every 4s instead of 2s)            │     │
│  │  KEEP:                                                                   │     │
│  │  - Live video streaming (core experience)                                │     │
│  │  - Live scoreboard overlay                                               │     │
│  │  - Core ad serving (revenue)                                             │     │
│  └─────────────────────────────────────────────────────────────────────────┘     │
│                                                                                   │
│  Level 3: CRITICAL (CDN > 95%, services degrading)                                │
│  ┌─────────────────────────────────────────────────────────────────────────┐     │
│  │  SHED:                                                                   │     │
│  │  - ALL interactive features OFF (polls, emoji, predictions)              │     │
│  │  - Ads disabled (protect core video delivery)                            │     │
│  │  - DVR disabled (only live edge)                                         │     │
│  │  - Reduce to 4 quality levels (240p, 480p, 720p, 1080p)                 │     │
│  │  - New user sessions throttled (queued, not rejected)                     │     │
│  │  - Score overlay served from static cache (not real-time)                │     │
│  │  KEEP:                                                                   │     │
│  │  - LIVE VIDEO STREAMING AT ALL COSTS                                     │     │
│  │  - This is the ONLY thing that matters                                   │     │
│  └─────────────────────────────────────────────────────────────────────────┘     │
│                                                                                   │
│  Level 4: EMERGENCY (partial system failure)                                      │
│  ┌─────────────────────────────────────────────────────────────────────────┐     │
│  │  - Audio-only option offered to overflow users                           │     │
│  │  - Static frame + audio for extremely degraded connections               │     │
│  │  - "Match is live" holding page for users who can't stream               │     │
│  │  - Redirect overflow to partner TV channels                              │     │
│  │  - This level should NEVER be reached with proper pre-scaling            │     │
│  └─────────────────────────────────────────────────────────────────────────┘     │
│                                                                                   │
│  Degradation triggers are AUTOMATIC (not human-dependent):                        │
│  - Prometheus alerts trigger PagerDuty                                            │
│  - Feature flag service auto-toggles based on metrics                             │
│  - CDN orchestrator auto-rebalances                                               │
│  - Human override available but not required for L0-L3                             │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Thundering Herd Solutions

### 4.1 At Match Start

```
┌─────────────────────────────────────────────────────────────────────┐
│           THUNDERING HERD: MATCH START (500K starts/sec)              │
│                                                                       │
│  Problem: 500K users simultaneously call:                             │
│  - POST /playback/init (session creation)                             │
│  - GET /manifest.m3u8 (first manifest)                                │
│  - GET /segment_0001.m4s (first video segment)                        │
│  - GET /drm/license (DRM key acquisition)                             │
│                                                                       │
│  Solutions Applied:                                                    │
│  ─────────────────                                                    │
│                                                                       │
│  1. STAGGERED START (Client-side jitter)                              │
│  ┌──────────────────────────────────────────────────────────┐        │
│  │  When user clicks "Watch Live":                           │        │
│  │  - Add random delay: 0-3000ms (spread over 3 seconds)    │        │
│  │  - Show "connecting..." animation during delay            │        │
│  │  - Turns 500K instant → 167K/sec over 3 seconds           │        │
│  │  - User perceives 0-3 second "normal" startup time         │        │
│  └──────────────────────────────────────────────────────────┘        │
│                                                                       │
│  2. MANIFEST CACHING (serve stale for first request)                  │
│  ┌──────────────────────────────────────────────────────────┐        │
│  │  First manifest request gets cached manifest (3-4 sec old) │        │
│  │  - User starts playing immediately from cached position    │        │
│  │  - Next manifest refresh (2s later) gets live edge         │        │
│  │  - User is 4 seconds behind live but streaming instantly   │        │
│  │  - Within 10 seconds, catches up to live edge              │        │
│  └──────────────────────────────────────────────────────────┘        │
│                                                                       │
│  3. SESSION POOLING (pre-created sessions)                            │
│  ┌──────────────────────────────────────────────────────────┐        │
│  │  Pre-create 500K session tokens during pre-show            │        │
│  │  - When user logs in for pre-show → session created early  │        │
│  │  - When match starts → session already exists              │        │
│  │  - No session-creation thundering herd                     │        │
│  └──────────────────────────────────────────────────────────┘        │
│                                                                       │
│  4. DRM KEY PRE-FETCH                                                 │
│  ┌──────────────────────────────────────────────────────────┐        │
│  │  During pre-show, client pre-fetches DRM license           │        │
│  │  - License valid for 4 hours (whole match)                 │        │
│  │  - No DRM server load at match start                       │        │
│  │  - Key rotation happens mid-stream (background refresh)    │        │
│  └──────────────────────────────────────────────────────────┘        │
│                                                                       │
│  5. REQUEST COALESCING (at every layer)                               │
│  ┌──────────────────────────────────────────────────────────┐        │
│  │  CDN edge: 50K requests for same segment → 1 origin fetch  │        │
│  │  API gateway: deduplicate identical requests within 100ms   │        │
│  │  Shield cache: 200 edge misses → 1 origin fetch            │        │
│  └──────────────────────────────────────────────────────────┘        │
└─────────────────────────────────────────────────────────────────────┘
```

### 4.2 At Key Moments (Wicket/Six)

```
┌─────────────────────────────────────────────────────────────────────┐
│        THUNDERING HERD: WICKET FALLS (millions DVR rewind)            │
│                                                                       │
│  What happens when Virat Kohli gets out:                              │
│                                                                       │
│  1. Social media explodes (5M tweets in 60 seconds)                   │
│  2. Users who paused → resume playback (+2M viewers)                  │
│  3. Users watching other content → switch to cricket (+1M)            │
│  4. MOST IMPORTANTLY: 10M users hit "rewind 10 seconds"              │
│                                                                       │
│  The DVR rewind thundering herd:                                      │
│  - 10M users request segments from 10-30 seconds ago                  │
│  - These segments are at the EDGE of cache TTL                        │
│  - If evicted: massive origin load                                    │
│                                                                       │
│  Solutions:                                                            │
│  ──────────                                                           │
│  1. EXTENDED SEGMENT TTL                                              │
│     - Live segments kept for 10 minutes (not just sliding window)     │
│     - DVR segments cached at shield for full match duration            │
│     - Cost: more edge storage. Benefit: zero origin hits for DVR      │
│                                                                       │
│  2. PREDICTIVE CACHING                                                │
│     - ML model watches ball-by-ball data feed                          │
│     - Detects "key moment" (wicket, six, close call)                  │
│     - Instantly pins those segments in cache (don't evict)            │
│     - Pre-fetches "replay" angles to edge                              │
│                                                                       │
│  3. DVR REQUEST SPREADING                                             │
│     - Client SDK adds 0-500ms jitter to rewind requests               │
│     - Prevents exact same millisecond stampede                         │
│                                                                       │
│  4. HIGHLIGHT CLIPS PRE-GENERATED                                     │
│     - Real-time clipping service creates 15-sec highlight clips       │
│     - Within 5 seconds of wicket: clip is on CDN                      │
│     - Users offered "watch highlight" instead of manual rewind         │
│     - Reduces DVR segment requests by 60%                              │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 5. Infrastructure Scaling Specifics

### 5.1 Kubernetes Scaling Strategy

```yaml
# HPA Configuration for Playback Service (event mode)
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: playback-service-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: playback-service
  minReplicas: 50          # Normal operation
  maxReplicas: 2000        # IPL peak
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 0   # Scale up IMMEDIATELY
      policies:
      - type: Percent
        value: 100                     # Double capacity per evaluation
        periodSeconds: 15
    scaleDown:
      stabilizationWindowSeconds: 3600  # Wait 1 hour before scaling down
      policies:
      - type: Percent
        value: 10                       # Scale down slowly (10% per period)
        periodSeconds: 300
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 50         # Scale at 50% (aggressive)
  - type: Pods
    pods:
      metric:
        name: http_requests_per_second
      target:
        type: AverageValue
        averageValue: 5000             # 5K RPS per pod target
```

```yaml
# Pre-scale CronJob (runs before every scheduled match)
apiVersion: batch/v1
kind: CronJob
metadata:
  name: ipl-prescale
spec:
  schedule: "0 14 * * *"    # 2 PM IST (4 hours before typical 7:30 PM match)
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: prescaler
            image: hotstar/prescaler:latest
            command:
            - /bin/sh
            - -c
            - |
              # Scale all critical services to predicted peak
              kubectl scale deployment playback-service --replicas=1500
              kubectl scale deployment manifest-server --replicas=800
              kubectl scale deployment auth-service --replicas=200
              kubectl scale deployment interaction-service --replicas=300
              kubectl scale deployment ad-service --replicas=400
              
              # Verify all pods are running and healthy
              kubectl wait --for=condition=ready pod -l app=playback-service --timeout=600s
              
              # Warm up: send synthetic traffic to fill caches and connection pools
              /bin/warmup --target-rps=100000 --duration=300s
```

### 5.2 Database Scaling for IPL

```
┌─────────────────────────────────────────────────────────────────────┐
│              DATABASE SCALING DURING IPL                               │
│                                                                       │
│  PostgreSQL (Citus - User/Subscription data):                         │
│  ─────────────────────────────────────────────                        │
│  Normal: 256 shards, 32 nodes, 128 read replicas                      │
│  IPL:    256 shards, 32 nodes, 512 read replicas (4× read capacity)   │
│  Why: Session validation hits read replicas heavily                     │
│                                                                       │
│  Redis Cluster (Session/Token/Viewer counts):                          │
│  ─────────────────────────────────────────────                        │
│  Normal: 20 master + 40 replica nodes (128 GB total)                  │
│  IPL:    60 master + 120 replica nodes (512 GB total, 3× capacity)    │
│  Why: 30M concurrent sessions × 2KB = 60 GB session state             │
│       + viewer counts + rate limiters + config cache                   │
│                                                                       │
│  ScyllaDB (Playback events):                                          │
│  ────────────────────────────                                         │
│  Normal: 20 nodes (handle 500K writes/sec)                            │
│  IPL:    50 nodes (handle 5M writes/sec)                              │
│  Why: 25M viewers × heartbeat every 10s = 2.5M writes/sec             │
│       + session start/stop + quality changes + errors                  │
│                                                                       │
│  Kafka (Event streaming):                                             │
│  ────────────────────────                                             │
│  Normal: 30 brokers, 100 partitions per topic                         │
│  IPL:    100 brokers, 500 partitions for hot topics                   │
│  Why: 10M+ events/sec during peak (QoE + interactions + analytics)    │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 6. Real-Time Monitoring During Live Event

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    WAR ROOM DASHBOARD (during IPL match)                           │
│                                                                                   │
│  ┌───────────────────────────────────────────────────────────────────────────┐   │
│  │  LIVE METRICS (refreshed every 1 second)                                   │   │
│  │                                                                             │   │
│  │  Concurrent Viewers:  24,832,451  ▲ (+125K/min)                            │   │
│  │  Stream Starts/sec:   12,450                                                │   │
│  │  Manifest Req/sec:    12,416,225                                            │   │
│  │  Segment Req/sec:     24,832,451                                            │   │
│  │                                                                             │   │
│  │  ─── QUALITY OF EXPERIENCE ───                                              │   │
│  │  Rebuffer Rate:       0.08%  ✅ (target: < 0.1%)                           │   │
│  │  Avg Startup Time:    1.8s   ✅ (target: < 2s)                             │   │
│  │  Avg Bitrate:         4.2 Mbps                                              │   │
│  │  Error Rate:          0.02%  ✅ (target: < 0.05%)                          │   │
│  │  Latency (live edge): 8.5s   ✅ (target: < 10s)                           │   │
│  │                                                                             │   │
│  │  ─── CDN HEALTH ───                                                         │   │
│  │  Akamai:     65% capacity  ✅  | Egress: 40 Tbps                           │   │
│  │  CloudFront: 72% capacity  ✅  | Egress: 28 Tbps                           │   │
│  │  Fastly:     58% capacity  ✅  | Egress: 18 Tbps                           │   │
│  │  Jio CDN:    81% capacity  ⚠️  | Egress: 12 Tbps                           │   │
│  │  Total Egress: 98 Tbps                                                      │   │
│  │                                                                             │   │
│  │  ─── INFRASTRUCTURE ───                                                     │   │
│  │  API Gateway:    52% CPU    ✅  (1200/2000 pods)                            │   │
│  │  Playback Svc:   61% CPU    ✅  (1500/2000 pods)                            │   │
│  │  Manifest Svc:   45% CPU    ✅  (750/1000 pods)                             │   │
│  │  Redis Cluster:  68% memory ✅  (380/512 GB)                                │   │
│  │  Kafka:          72% disk   ✅  (100 brokers)                               │   │
│  │  Transcoder:     40% GPU    ✅  (24 GPUs active)                            │   │
│  │                                                                             │   │
│  │  ─── ALERTS ───                                                             │   │
│  │  ⚠️  Jio CDN Mumbai PoP approaching 85% - overflow ready                   │   │
│  │  ℹ️  Match innings break in ~15 min - prepare for ad burst                  │   │
│  └───────────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 7. Match Events → System Impact Correlation

```
┌────────────────────────────────────────────────────────────────────────────────┐
│  Cricket Event     │ System Impact                    │ Automated Response      │
│  ─────────────────│──────────────────────────────────│───────────────────────  │
│  Toss             │ +2M viewers in 2 min              │ Monitor, no action      │
│  First Ball       │ +13M viewers in 5 min             │ All pre-scaled          │
│  Wicket           │ +2M viewers + 10M DVR rewinds     │ Pin segments in cache   │
│  Six (Dhoni/Kohli)│ +5M emoji/sec + 3M DVR rewinds   │ Throttle emoji service  │
│  Strategic Timeout│ -3M viewers (break)               │ Ad burst (SSAI active)  │
│  Innings Break    │ -5M viewers, +8M ad impressions   │ Scale down video, up ad │
│  Last Over        │ +5M new viewers (word of mouth)   │ Ensure headroom         │
│  Match Result     │ -10M in 5 min (mass exit)         │ Serve highlights        │
│  Super Over       │ +8M viewers (MAXIMUM PEAK)        │ All hands on deck       │
│  DRS Review       │ +15M DVR "show ball tracker"      │ Pin replay segments     │
│  Rain Delay       │ -8M viewers over 30 min           │ Gradual scale down      │
└────────────────────────────────────────────────────────────────────────────────┘
```

---

## 8. Cost of IPL Infrastructure

```
┌─────────────────────────────────────────────────────────────────────┐
│              IPL INFRASTRUCTURE COST ESTIMATE (2 months)               │
│                                                                       │
│  CDN Bandwidth:                                                       │
│  - 74 matches × avg 80 Tbps × 3.5 hours = ~100 PB egress            │
│  - Cost: $1.5M - $2M (negotiated rate at scale)                       │
│                                                                       │
│  Cloud Compute (AWS):                                                 │
│  - 3000+ pods × 2 months (over-provisioned)                          │
│  - GPU instances for transcoding (24/7 during season)                 │
│  - Cost: $800K - $1.2M                                               │
│                                                                       │
│  Database/Storage:                                                    │
│  - Expanded Redis, Scylla, Kafka clusters                            │
│  - S3 storage for segments + VOD                                      │
│  - Cost: $200K - $400K                                               │
│                                                                       │
│  Total IPL Infrastructure Spend: $3M - $5M for 2 months              │
│                                                                       │
│  Revenue Context:                                                     │
│  - IPL digital rights: ₹23,575 crore for 5 years (~$2.8B)            │
│  - Per season: ~$560M in rights costs                                 │
│  - Ad revenue during IPL: estimated $200-300M per season              │
│  - Subscription revenue boost: 15M+ new subscribers during IPL        │
│                                                                       │
│  Conclusion: $5M infra cost is < 1% of IPL revenue                    │
│  "You don't optimize for cost during IPL. You optimize for ZERO lag." │
└─────────────────────────────────────────────────────────────────────┘
```
