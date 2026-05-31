# CDN Video & Media Delivery

## Video Streaming Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    Video Delivery Pipeline                                │
│                                                                         │
│  Source ──▶ Transcode ──▶ Package ──▶ CDN ──▶ Player                   │
│                                                                         │
│  ┌──────┐   ┌──────────┐   ┌─────────┐   ┌────┐   ┌──────┐          │
│  │Camera│──▶│Transcoder│──▶│Packager  │──▶│CDN │──▶│Player│          │
│  │/File │   │(H.264,   │   │(HLS/DASH│   │Edge│   │(ABR) │          │
│  └──────┘   │ H.265,   │   │manifest)│   └────┘   └──────┘          │
│             │ VP9, AV1)│   └─────────┘                                │
│             └──────────┘                                               │
│                                                                         │
│  Bitrate ladder (example):                                              │
│  • 1080p @ 5 Mbps (H.264)                                             │
│  • 720p  @ 2.5 Mbps                                                   │
│  • 480p  @ 1 Mbps                                                     │
│  • 360p  @ 500 Kbps                                                   │
│  • 240p  @ 200 Kbps (mobile/slow)                                     │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## HLS (HTTP Live Streaming)

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  HLS Structure                                               │
│                                                             │
│  Master Playlist (master.m3u8)                              │
│  ├── Variant 1080p (playlist_1080.m3u8)                    │
│  │   ├── segment_001.ts (6 seconds)                        │
│  │   ├── segment_002.ts (6 seconds)                        │
│  │   └── segment_003.ts (6 seconds)                        │
│  ├── Variant 720p (playlist_720.m3u8)                      │
│  │   ├── segment_001.ts                                    │
│  │   ├── segment_002.ts                                    │
│  │   └── segment_003.ts                                    │
│  └── Variant 360p (playlist_360.m3u8)                      │
│      ├── segment_001.ts                                    │
│      ├── segment_002.ts                                    │
│      └── segment_003.ts                                    │
└─────────────────────────────────────────────────────────────┘
```

### Master Playlist Example

```m3u8
#EXTM3U
#EXT-X-VERSION:4

#EXT-X-STREAM-INF:BANDWIDTH=5000000,RESOLUTION=1920x1080,CODECS="avc1.640028,mp4a.40.2"
1080p/playlist.m3u8

#EXT-X-STREAM-INF:BANDWIDTH=2500000,RESOLUTION=1280x720,CODECS="avc1.64001f,mp4a.40.2"
720p/playlist.m3u8

#EXT-X-STREAM-INF:BANDWIDTH=1000000,RESOLUTION=854x480,CODECS="avc1.4d401e,mp4a.40.2"
480p/playlist.m3u8

#EXT-X-STREAM-INF:BANDWIDTH=500000,RESOLUTION=640x360,CODECS="avc1.42c01e,mp4a.40.2"
360p/playlist.m3u8
```

### Media Playlist (per variant)

```m3u8
#EXTM3U
#EXT-X-VERSION:4
#EXT-X-TARGETDURATION:6
#EXT-X-MEDIA-SEQUENCE:0

#EXTINF:6.006,
segment_000.ts
#EXTINF:6.006,
segment_001.ts
#EXTINF:6.006,
segment_002.ts
#EXT-X-ENDLIST
```

### HLS Caching Strategy

| File Type | Cache-Control | Rationale |
|-----------|--------------|-----------|
| Master playlist | `max-age=3600` (VOD) / `max-age=1` (live) | Rarely changes for VOD |
| Media playlist | `max-age=segment_duration/2` (live) | Must refresh to see new segments |
| Segments (.ts/.m4s) | `max-age=31536000, immutable` | Never change once created |
| Encryption keys | `max-age=3600` | Rotate periodically |

---

## DASH (Dynamic Adaptive Streaming over HTTP)

### DASH vs HLS

| Feature | HLS | DASH |
|---------|-----|------|
| Creator | Apple | MPEG consortium (open standard) |
| Container | .ts (MPEG-TS) or .m4s (fMP4) | .m4s (fMP4) |
| Manifest | .m3u8 (playlist) | .mpd (XML) |
| Codec support | H.264, H.265, AV1 | Any codec |
| DRM | FairPlay (Apple) | Widevine, PlayReady |
| Browser support | Safari native, others via JS | All via JS (MSE) |
| Industry use | Apple ecosystem, most OTT | YouTube, Netflix |
| Live latency | 20-30s (standard), 2s (LL-HLS) | 20-30s, 2-3s (LL-DASH) |

### DASH MPD Structure

```xml
<?xml version="1.0" encoding="UTF-8"?>
<MPD xmlns="urn:mpeg:dash:schema:mpd:2011" 
     type="static" 
     mediaPresentationDuration="PT1H30M">
  <Period>
    <AdaptationSet mimeType="video/mp4" codecs="avc1.640028">
      <Representation id="1080p" bandwidth="5000000" width="1920" height="1080">
        <SegmentTemplate media="1080p/seg_$Number$.m4s" 
                        initialization="1080p/init.mp4"
                        duration="6000" timescale="1000"/>
      </Representation>
      <Representation id="720p" bandwidth="2500000" width="1280" height="720">
        <SegmentTemplate media="720p/seg_$Number$.m4s"
                        initialization="720p/init.mp4"
                        duration="6000" timescale="1000"/>
      </Representation>
    </AdaptationSet>
    <AdaptationSet mimeType="audio/mp4" codecs="mp4a.40.2">
      <Representation id="audio" bandwidth="128000">
        <SegmentTemplate media="audio/seg_$Number$.m4s"
                        initialization="audio/init.mp4"
                        duration="6000" timescale="1000"/>
      </Representation>
    </AdaptationSet>
  </Period>
</MPD>
```

---

## Adaptive Bitrate Streaming (ABR)

### How ABR Works

```
┌──────────────────────────────────────────────────────────────────┐
│  ABR Algorithm at Player                                          │
│                                                                  │
│  Inputs:                                                         │
│  • Available bandwidth (measured from segment downloads)         │
│  • Buffer level (seconds of video buffered)                     │
│  • Segment download time                                        │
│  • Display resolution                                            │
│                                                                  │
│  Decision:                                                       │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Bandwidth: 8 Mbps | Buffer: 15s | Display: 1080p      │    │
│  │  → Select: 1080p @ 5 Mbps (headroom for fluctuation)   │    │
│  │                                                         │    │
│  │  Bandwidth drops to 2 Mbps | Buffer: 4s                │    │
│  │  → Switch down: 480p @ 1 Mbps (protect buffer)        │    │
│  │                                                         │    │
│  │  Bandwidth recovers to 6 Mbps | Buffer: 20s            │    │
│  │  → Switch up gradually: 720p → 1080p                   │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  Popular algorithms: BBA (Buffer-Based), MPC, BOLA, Pensieve    │
└──────────────────────────────────────────────────────────────────┘
```

---

## Video Transcoding Pipeline

### Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    Video Processing Pipeline                              │
│                                                                         │
│  Upload ──▶ Ingest ──▶ Transcode ──▶ Package ──▶ Store ──▶ CDN        │
│                                                                         │
│  ┌─────────┐                                                           │
│  │ Upload  │  S3 / GCS / R2                                            │
│  │ (source)│                                                           │
│  └────┬────┘                                                           │
│       ▼                                                                 │
│  ┌─────────┐                                                           │
│  │ Ingest  │  Validate, extract metadata                               │
│  │ Queue   │  (codec, resolution, duration, audio tracks)              │
│  └────┬────┘                                                           │
│       ▼                                                                 │
│  ┌──────────────┐                                                      │
│  │ Transcode    │  Parallel encoding of bitrate ladder                 │
│  │ (distributed)│  • FFmpeg / MediaConvert / Mux                       │
│  │              │  • GPU-accelerated (NVENC)                           │
│  │              │  • Per-title encoding (Netflix approach)             │
│  └────┬─────────┘                                                      │
│       ▼                                                                 │
│  ┌─────────┐                                                           │
│  │ Package │  Create HLS/DASH manifests + segments                     │
│  │         │  Apply DRM encryption                                     │
│  └────┬────┘                                                           │
│       ▼                                                                 │
│  ┌─────────┐                                                           │
│  │ Storage │  S3 origin with CDN in front                              │
│  └────┬────┘                                                           │
│       ▼                                                                 │
│  ┌─────────┐                                                           │
│  │  CDN    │  Cache segments globally                                  │
│  └─────────┘                                                           │
└─────────────────────────────────────────────────────────────────────────┘
```

### AWS MediaConvert Example

```json
{
  "Role": "arn:aws:iam::123456:role/MediaConvert",
  "Settings": {
    "Inputs": [{
      "FileInput": "s3://source-bucket/raw/movie.mp4"
    }],
    "OutputGroups": [{
      "OutputGroupSettings": {
        "Type": "HLS_GROUP_SETTINGS",
        "HlsGroupSettings": {
          "Destination": "s3://output-bucket/hls/movie/",
          "SegmentLength": 6,
          "MinSegmentLength": 2
        }
      },
      "Outputs": [
        { "VideoDescription": { "Width": 1920, "Height": 1080 },
          "Preset": "System-Generic_Hd_Mp4_Avc_Aac_16x9_1920x1080p_24Hz_6Mbps" },
        { "VideoDescription": { "Width": 1280, "Height": 720 },
          "Preset": "System-Generic_Hd_Mp4_Avc_Aac_16x9_1280x720p_24Hz_3Mbps" },
        { "VideoDescription": { "Width": 640, "Height": 360 },
          "Preset": "System-Generic_Sd_Mp4_Avc_Aac_16x9_640x360p_24Hz_800Kbps" }
      ]
    }]
  }
}
```

---

## Live Streaming via CDN

### Live Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    Live Streaming Architecture                            │
│                                                                         │
│  Camera ──RTMP──▶ Ingest Server ──▶ Live Transcoder ──▶ Packager       │
│                   (Wowza/AWS)       (real-time)         (HLS/DASH)      │
│                                                             │            │
│                                                             ▼            │
│                                                        CDN Origin        │
│                                                             │            │
│                                                   ┌─────────┼────────┐  │
│                                                   ▼         ▼        ▼  │
│                                                PoP-1     PoP-2    PoP-3 │
│                                                   │         │        │  │
│                                                Viewers  Viewers  Viewers │
│                                                                         │
│  Latency (standard HLS): 20-30 seconds                                 │
│  Latency (LL-HLS):       2-5 seconds                                   │
│  Latency (WebRTC):       < 1 second                                    │
└─────────────────────────────────────────────────────────────────────────┘
```

### Live Manifest Caching

```
For live streaming:

Master playlist:     Cache: 1 hour (doesn't change during stream)
Media playlist:      Cache: segment_duration / 3  (e.g., 2s for 6s segments)
                     Must refresh to discover new segments!
Current segment:     Cache: forever (immutable once written)
Previous segments:   Cache: DVR window duration

Key challenge: Media playlist must have very short TTL
               but it's the most-requested file!

Solution: CDN origin shield + request collapsing
          Thousands of requests → 1 origin fetch every 2s
```

---

## Low-Latency Streaming

### LL-HLS (Low-Latency HLS)

```
Standard HLS:                      LL-HLS:
                                   
Segment: 6 seconds                 Partial segment: 200ms-1s
Wait for full segment              Stream parts as produced
Latency: 3× segment = 18s+        Latency: 2-5 seconds

Key features:
• Partial segments (EXT-X-PART)
• Playlist delta updates (reduce manifest size)
• Blocking playlist reload (server holds request)
• Preload hints (prefetch next part)
```

```m3u8
# LL-HLS Manifest
#EXTM3U
#EXT-X-SERVER-CONTROL:CAN-BLOCK-RELOAD=YES,PART-HOLD-BACK=1.0
#EXT-X-PART-INF:PART-TARGET=0.5

#EXTINF:4.0,
segment_100.m4s
#EXT-X-PART:DURATION=0.5,URI="segment_101_part0.m4s"
#EXT-X-PART:DURATION=0.5,URI="segment_101_part1.m4s"
#EXT-X-PART:DURATION=0.5,URI="segment_101_part2.m4s"
#EXT-X-PRELOAD-HINT:TYPE=PART,URI="segment_101_part3.m4s"
```

### Latency Comparison

```
┌────────────────────────────────────────────────────────────┐
│  Streaming Latency Spectrum                                 │
│                                                            │
│  WebRTC          │ ██ < 1s (real-time)                    │
│  LL-HLS/LL-DASH  │ ████████ 2-5s                          │
│  CMAF-CTE        │ ██████████ 3-8s                        │
│  Standard HLS    │ ████████████████████████ 15-30s        │
│  Standard DASH   │ ████████████████████████ 15-30s        │
│                                                            │
│  Trade-offs:                                               │
│  Lower latency = less buffer = more rebuffering risk      │
│  Lower latency = more manifest requests = more CDN cost   │
└────────────────────────────────────────────────────────────┘
```

---

## VOD (Video on Demand) Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  VOD Architecture (e.g., Netflix/YouTube pattern)                │
│                                                                  │
│  1. Upload: Creator uploads source file                         │
│  2. Process: Transcode to all quality levels                    │
│  3. Store: S3/GCS with HLS/DASH packaged                       │
│  4. Index: Metadata in database (title, duration, thumbnails)   │
│  5. Serve: CDN → Player                                         │
│                                                                  │
│  ┌─────────┐     ┌──────────┐     ┌──────┐     ┌──────┐      │
│  │  S3     │────▶│CloudFront│────▶│Player│     │ API  │      │
│  │ (origin)│     │  (CDN)   │     │      │◀───│Server│      │
│  └─────────┘     └──────────┘     └──────┘     └──────┘      │
│                                                                  │
│  Player flow:                                                   │
│  1. API call → get video metadata + signed manifest URL         │
│  2. Fetch master.m3u8 (via CDN, signed URL)                    │
│  3. Player selects variant based on bandwidth                   │
│  4. Fetch segments sequentially (CDN cache hit ~99%)           │
│                                                                  │
│  Cache hit ratio for popular VOD: 95-99%                       │
│  Long-tail content: 60-80% (use origin shield)                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## CDN for Video: Provider Comparison

| Feature | CloudFront + MediaConvert | Cloudflare Stream | Mux |
|---------|--------------------------|-------------------|-----|
| Transcoding | MediaConvert / Elemental | Built-in | Built-in |
| Delivery | CloudFront CDN | Cloudflare CDN | Multi-CDN |
| Player | Bring your own | Built-in embed | Mux Player |
| Analytics | CloudWatch | Dashboard | Mux Data |
| DRM | SpekeV2 integration | Token auth only | Widevine/FairPlay |
| Live | MediaLive + MediaPackage | Live (beta) | ✅ |
| Pricing | Per-minute + per-GB | Per-minute stored + viewed | Per-minute + per-GB |
| Best for | AWS-native, full control | Simple, good value | Analytics-first |

---

## Multi-CDN for Video Delivery

```
┌─────────────────────────────────────────────────────────────────────┐
│  Multi-CDN Video Strategy                                            │
│                                                                     │
│  Player (ABR + CDN selection):                                      │
│  ┌──────────────────────────────────────────────────────────┐      │
│  │ 1. Request manifest from primary CDN                      │      │
│  │ 2. Monitor segment download performance                   │      │
│  │ 3. If degradation detected:                               │      │
│  │    • Switch CDN for next segment request                  │      │
│  │    • No viewer impact (seamless switch)                   │      │
│  │ 4. Report quality metrics to analytics                    │      │
│  └──────────────────────────────────────────────────────────┘      │
│                                                                     │
│  CDN Switching Signals:                                             │
│  • Segment download time > threshold                                │
│  • HTTP error rates increasing                                      │
│  • TCP connection failures                                          │
│  • Regional CDN health checks failing                              │
│                                                                     │
│  Implementation:                                                    │
│  • Manifest contains CDN-agnostic segment paths                    │
│  • Player prepends CDN base URL dynamically                        │
│  • URL: {selected_cdn}/path/to/segment_001.ts                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## DRM (Digital Rights Management)

### DRM Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  DRM Flow                                                        │
│                                                                  │
│  1. Content encrypted during packaging (CENC - Common Enc)      │
│  2. Encrypted segments stored on CDN (safe even if leaked)      │
│  3. Player requests license to decrypt                          │
│                                                                  │
│  Player ──▶ CDN (encrypted segments)                            │
│  Player ──▶ License Server (get decryption key)                 │
│                                                                  │
│  ┌───────────────────────────────────────────────────────┐     │
│  │  Platform        │ DRM System   │ License Server      │     │
│  ├───────────────────┼──────────────┼─────────────────────┤     │
│  │  Chrome/Android   │ Widevine     │ Google              │     │
│  │  Safari/iOS       │ FairPlay     │ Apple               │     │
│  │  Edge/Xbox        │ PlayReady    │ Microsoft           │     │
│  └───────────────────┴──────────────┴─────────────────────┘     │
│                                                                  │
│  CENC allows single encryption, multiple DRM systems            │
│  Same encrypted file works with Widevine AND PlayReady          │
└─────────────────────────────────────────────────────────────────┘
```

### DRM + CDN Configuration

```
Encrypted content flow:
1. Packager encrypts with content key → segments (AES-128-CTR)
2. Content key encrypted with DRM-specific wrapping → stored in license server
3. CDN serves encrypted segments (no special handling needed)
4. Player requests license: POST /license (origin, not CDN)
5. License server validates entitlement → returns content key
6. Player decrypts and renders locally

CDN caching:
• Encrypted segments: cache normally (long TTL, immutable)
• License requests: DO NOT cache (per-user authorization)
• Manifests: cache normally
```

---

## Video Analytics at Edge

```javascript
// Cloudflare Worker: Video analytics collection
export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    
    // Track segment requests for analytics
    if (url.pathname.match(/segment_\d+\.(ts|m4s)$/)) {
      const analytics = {
        timestamp: Date.now(),
        viewer_country: request.headers.get('CF-IPCountry'),
        quality: url.pathname.includes('1080p') ? '1080p' : 
                 url.pathname.includes('720p') ? '720p' : 'other',
        cdn_pop: request.cf?.colo,
        cache_status: 'pending', // will be set after fetch
      };
      
      const response = await fetch(request);
      analytics.cache_status = response.headers.get('CF-Cache-Status');
      
      // Async write to analytics (don't block response)
      event.waitUntil(
        env.ANALYTICS_QUEUE.send(JSON.stringify(analytics))
      );
      
      return response;
    }
    
    return fetch(request);
  }
};
```

### Key Video Metrics

| Metric | Description | Target |
|--------|-------------|--------|
| TTFF (Time to First Frame) | Time from play click to first frame | < 2s |
| Rebuffer ratio | % time spent buffering | < 1% |
| Bitrate | Average quality delivered | Maximize |
| Startup failures | Play attempts that fail | < 0.5% |
| CDN hit ratio | Segments served from cache | > 95% |
| Join time | Time to start playback | < 3s |
