# System Design: Disney+ Hotstar - Live Streaming at Scale

## Overview

Disney+ Hotstar is India's largest streaming platform that handles **25M+ concurrent viewers** during live cricket events (IPL), making it one of the most demanding real-time streaming systems globally. Unlike Netflix (pure VOD) or Twitch (user-generated live), Hotstar uniquely combines:

- **Live Sports Streaming** at unprecedented scale (IPL, Cricket World Cup)
- **VOD Content** (Movies, Series, Disney+ catalog)
- **Massive traffic spikes** (0 to 25M concurrent in minutes when a match starts)
- **India-specific challenges** (heterogeneous networks, low-end devices, regional languages)

## Document Structure

| # | File | Description |
|---|------|-------------|
| 1 | [01-requirements-and-capacity.md](./01-requirements-and-capacity.md) | Functional/Non-functional requirements + capacity estimation |
| 2 | [02-data-modeling.md](./02-data-modeling.md) | ER diagrams, database schemas, storage choices |
| 3 | [03-high-level-architecture.md](./03-high-level-architecture.md) | Full system architecture diagram + component breakdown |
| 4 | [04-streaming-pipeline.md](./04-streaming-pipeline.md) | Ingest, transcoding, packaging, ABR delivery pipeline |
| 5 | [05-cdn-and-edge-delivery.md](./05-cdn-and-edge-delivery.md) | Multi-CDN strategy, edge caching, P2P augmentation |
| 6 | [06-live-cricket-scaling.md](./06-live-cricket-scaling.md) | IPL-specific scaling: thundering herd, pre-warming, graceful degradation |
| 7 | [07-api-design.md](./07-api-design.md) | REST/gRPC APIs for streaming, playback, interactions |
| 8 | [08-deep-dives.md](./08-deep-dives.md) | ABR algorithms, fault tolerance, zero-lag strategies, observability |

## Key Numbers (IPL Final Scale)

```
Concurrent Viewers:          25,300,000 (world record, 2023 IPL)
Peak Bandwidth:              100+ Tbps egress
Stream Start Time:           < 2 seconds
Rebuffer Rate:               < 0.5% (target < 0.1%)
Glass-to-Glass Latency:      8-15 seconds (broadcast to viewer)
API Requests/sec (peak):     10M+ RPS
Traffic Ramp Rate:           0 → 15M concurrent in 10 minutes
Devices Supported:           500+ device types
Languages:                   8 commentary tracks simultaneously
```
