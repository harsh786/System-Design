# CDN Master Index - Complete Guide

## Learning Path for CDN Mastery

```
Level 1: Fundamentals          Level 2: Advanced           Level 3: Expert
┌─────────────────────┐       ┌─────────────────────┐    ┌─────────────────────┐
│ cdn-deep-dive.md    │──────▶│ cdn-architecture.md │───▶│ cdn-edge-computing  │
│ (What/Why/Basics)   │       │ (How it works)      │    │ (Compute at edge)   │
└─────────────────────┘       ├─────────────────────┤    ├─────────────────────┤
                              │ cdn-caching-         │    │ cdn-video-streaming │
                              │ strategies.md       │    │ (Media delivery)    │
                              ├─────────────────────┤    ├─────────────────────┤
                              │ cdn-security.md     │    │ cdn-providers-      │
                              │ (Protection)        │    │ comparison.md       │
                              └─────────────────────┘    └─────────────────────┘
```

## File Index

| # | File | Topic | Level |
|---|------|-------|-------|
| 1 | [cdn-deep-dive.md](./cdn-deep-dive.md) | CDN fundamentals, basics, overview | Beginner |
| 2 | [cdn-architecture.md](./cdn-architecture.md) | Internal architecture, routing, request lifecycle | Intermediate |
| 3 | [cdn-caching-strategies.md](./cdn-caching-strategies.md) | Complete caching guide, headers, invalidation | Intermediate |
| 4 | [cdn-security.md](./cdn-security.md) | DDoS, WAF, TLS, origin protection | Intermediate |
| 5 | [cdn-edge-computing.md](./cdn-edge-computing.md) | Edge compute, serverless at edge, Workers | Advanced |
| 6 | [cdn-video-streaming.md](./cdn-video-streaming.md) | HLS, DASH, live streaming, VOD | Advanced |
| 7 | [cdn-providers-comparison.md](./cdn-providers-comparison.md) | CloudFront, Cloudflare, Akamai, Fastly comparison | Advanced |

## Quick Reference: When to Use What

| Scenario | Read This |
|----------|-----------|
| "What is a CDN?" | cdn-deep-dive.md |
| "How does a CDN route requests?" | cdn-architecture.md |
| "What Cache-Control headers should I set?" | cdn-caching-strategies.md |
| "How to invalidate/purge cache?" | cdn-caching-strategies.md |
| "How to protect origin from DDoS?" | cdn-security.md |
| "How to run code at the edge?" | cdn-edge-computing.md |
| "How to do A/B testing at CDN?" | cdn-edge-computing.md |
| "How to stream video via CDN?" | cdn-video-streaming.md |
| "Which CDN provider should I pick?" | cdn-providers-comparison.md |
| "How to set up multi-CDN?" | cdn-providers-comparison.md |
| "How to optimize CDN costs?" | cdn-providers-comparison.md |

## System Design Interview Quick Hits

- **Static content delivery** → cdn-deep-dive.md + cdn-caching-strategies.md
- **Video streaming platform** → cdn-video-streaming.md + cdn-architecture.md
- **Global low-latency API** → cdn-edge-computing.md + cdn-architecture.md
- **DDoS-resilient architecture** → cdn-security.md + cdn-architecture.md
- **E-commerce at scale** → cdn-caching-strategies.md + cdn-edge-computing.md
