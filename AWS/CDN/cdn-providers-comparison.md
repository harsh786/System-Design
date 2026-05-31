# CDN Providers Deep Comparison

## AWS CloudFront

### Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│  CloudFront Architecture                                                 │
│                                                                         │
│  Distribution (config unit)                                             │
│  ├── Behaviors (path-based routing rules)                              │
│  │   ├── /api/* → API Gateway origin (TTL: 0, forward all headers)    │
│  │   ├── /static/* → S3 origin (TTL: 1yr, immutable)                  │
│  │   └── /* → ALB origin (TTL: 60s, cache by cookie)                  │
│  ├── Origins                                                           │
│  │   ├── S3 Bucket (OAC - Origin Access Control)                      │
│  │   ├── ALB/EC2 (custom origin, HTTPS)                               │
│  │   ├── API Gateway                                                    │
│  │   └── MediaPackage (video)                                          │
│  ├── Cache Policies (what's in cache key)                              │
│  ├── Origin Request Policies (what to forward)                         │
│  └── Response Headers Policies (add security headers)                  │
│                                                                         │
│  Edge Locations: 400+ PoPs in 90+ cities                               │
│  Regional Edge Caches: 13 locations                                    │
└─────────────────────────────────────────────────────────────────────────┘
```

### OAI vs OAC (Origin Access)

| Feature | OAI (Legacy) | OAC (Recommended) |
|---------|-------------|-------------------|
| S3 SSE-KMS | ❌ | ✅ |
| S3 in any region | ❌ | ✅ |
| POST/PUT to S3 | ❌ | ✅ |
| SigV4 signing | ❌ | ✅ |

### CloudFront + Lambda@Edge Example

```yaml
# CDK / CloudFormation pattern
Distribution:
  DefaultCacheBehavior:
    ViewerProtocolPolicy: redirect-to-https
    CachePolicyId: "658327ea-..."  # CachingOptimized
    OriginRequestPolicyId: "88a5ef..."
    LambdaFunctionAssociations:
      - EventType: viewer-request
        FunctionARN: !Ref AuthFunction
      - EventType: origin-response
        FunctionARN: !Ref AddHeadersFunction
  Origins:
    - DomainName: !GetAtt Bucket.DomainName
      S3OriginConfig:
        OriginAccessIdentity: ""
      OriginAccessControlId: !Ref OAC
```

### CloudFront Pricing (2024)

| Region | First 10 TB | Next 40 TB | Next 100 TB |
|--------|-------------|------------|-------------|
| US/Europe | $0.085/GB | $0.080/GB | $0.060/GB |
| Asia Pacific | $0.120/GB | $0.100/GB | $0.080/GB |
| India | $0.109/GB | $0.085/GB | $0.070/GB |
| Functions | $0.10/million | - | - |
| Lambda@Edge | $0.60/million + $0.00000625/128MB-s | - | - |
| Invalidations | First 1000 free, then $0.005 each | - | - |

---

## Cloudflare

### Architecture & Offerings

```
┌─────────────────────────────────────────────────────────────────────────┐
│  Cloudflare Stack                                                        │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  CDN / Caching (every request passes through)                    │   │
│  ├─────────────────────────────────────────────────────────────────┤   │
│  │  Workers (V8 isolates on every request if configured)           │   │
│  ├─────────────────────────────────────────────────────────────────┤   │
│  │  Security: DDoS + WAF + Bot Management                         │   │
│  ├─────────────────────────────────────────────────────────────────┤   │
│  │  Performance: Argo Smart Routing + Tiered Caching              │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  Key Products:                                                          │
│  • Workers: Serverless at edge (V8 isolates, 0ms cold start)          │
│  • Pages: Full-stack deployment (like Vercel/Netlify)                  │
│  • R2: S3-compatible storage (ZERO egress fees)                        │
│  • D1: SQLite at edge                                                  │
│  • KV: Key-value store (eventually consistent)                         │
│  • Durable Objects: Strongly consistent coordination                   │
│  • Queues: Message queue                                               │
│  • Stream: Video delivery                                              │
│  • Images: Optimization & transformation                               │
│  • Argo: Smart routing (reduces latency 30%)                          │
│                                                                         │
│  Network: 300+ PoPs, 200+ Tbps capacity                               │
└─────────────────────────────────────────────────────────────────────────┘
```

### Cloudflare Pricing

| Plan | Price | Key Features |
|------|-------|-------------|
| Free | $0 | Basic CDN, DDoS, shared SSL, 100K Workers/day |
| Pro | $20/mo | WAF managed rules, image optimization, mobile optimization |
| Business | $200/mo | Custom WAF rules, 100% SLA, dynamic redirects |
| Enterprise | Custom | Dedicated support, Argo, advanced DDoS, Bot Management |

### Argo Smart Routing

```
Without Argo:                        With Argo:
                                     
User → Internet (public BGP) → Origin    User → Cloudflare backbone → Origin
       (congested, unpredictable)                (optimized, private)
       
Latency improvement: ~30% average
How: Cloudflare measures real-time latency between all PoPs
     Routes traffic through fastest private backbone path
     
Cost: +$0.10/GB on top of plan
```

---

## Akamai

### Enterprise Features

```
┌─────────────────────────────────────────────────────────────────┐
│  Akamai Product Suite                                            │
│                                                                  │
│  Content Delivery:                                               │
│  • Ion: Web performance (SPA/SSR optimization)                  │
│  • DSA (Dynamic Site Accelerator): Dynamic content              │
│  • Download Delivery: Large file downloads                      │
│  • Media Delivery: Video streaming                              │
│  • NetStorage: Distributed origin storage                       │
│                                                                  │
│  Security:                                                       │
│  • Kona Site Defender: WAF + DDoS                              │
│  • Bot Manager: Advanced bot detection                          │
│  • Prolexic: L3/L4 DDoS (dedicated scrubbing)                 │
│  • Enterprise Application Access: Zero Trust                    │
│                                                                  │
│  Edge Compute:                                                   │
│  • EdgeWorkers: JavaScript at edge                             │
│  • EdgeKV: Key-value at edge                                   │
│                                                                  │
│  Network: 4,100+ PoPs, 365+ Tbps capacity                     │
│  (Largest CDN by PoP count)                                    │
└─────────────────────────────────────────────────────────────────┘
```

### Akamai: When to Choose

- Enterprise with complex requirements
- Need deepest global penetration (China, Africa, Middle East)
- Heavy video/media workloads
- Existing Akamai contracts (hard to leave)
- Need dedicated DDoS scrubbing (Prolexic)
- Regulatory compliance requiring specific data handling

---

## Fastly

### Key Differentiators

```
┌─────────────────────────────────────────────────────────────────┐
│  Fastly Strengths                                                │
│                                                                  │
│  1. Instant Purge: < 150ms global purge propagation            │
│     (vs CloudFront 5-15 min, Cloudflare 30s)                   │
│                                                                  │
│  2. VCL (Varnish Configuration Language):                       │
│     Fine-grained cache control logic                            │
│     if (req.url ~ "^/api/") { set beresp.ttl = 1s; }          │
│                                                                  │
│  3. Compute@Edge: WebAssembly runtime                          │
│     Rust, Go, JavaScript → compiled to Wasm                    │
│     Near-native performance                                     │
│                                                                  │
│  4. Image Optimizer: Real-time image transformation            │
│     Resize, crop, format conversion at edge                    │
│                                                                  │
│  5. Real-time logging: Stream logs to your analytics           │
│     Sub-second log delivery                                     │
│                                                                  │
│  Network: 90+ PoPs (fewer but larger/faster)                   │
│  Architecture: Varnish-based (memory-first caching)            │
└─────────────────────────────────────────────────────────────────┘
```

### Fastly VCL Example

```vcl
sub vcl_recv {
  # Normalize Accept-Encoding
  if (req.http.Accept-Encoding) {
    if (req.http.Accept-Encoding ~ "br") {
      set req.http.Accept-Encoding = "br";
    } elsif (req.http.Accept-Encoding ~ "gzip") {
      set req.http.Accept-Encoding = "gzip";
    } else {
      unset req.http.Accept-Encoding;
    }
  }
  
  # Strip tracking query params from cache key
  set req.url = querystring.regfilter(req.url, "^(utm_|fbclid|gclid)");
}

sub vcl_fetch {
  # Surrogate key for tag-based purging
  if (beresp.http.Surrogate-Key) {
    set beresp.http.Surrogate-Key = beresp.http.Surrogate-Key;
  }
  
  # Stale-while-revalidate
  if (beresp.status == 200) {
    set beresp.stale_while_revalidate = 86400s;
    set beresp.stale_if_error = 86400s;
  }
}
```

---

## Azure CDN / Front Door

```
┌─────────────────────────────────────────────────────────────────┐
│  Azure Front Door (combines CDN + Load Balancer + WAF)          │
│                                                                  │
│  Features:                                                       │
│  • Global load balancing (L7)                                   │
│  • CDN caching                                                   │
│  • WAF (Azure WAF)                                              │
│  • SSL offload                                                   │
│  • URL-based routing                                             │
│  • Session affinity                                              │
│  • Health probes                                                 │
│  • Private Link to origins                                       │
│                                                                  │
│  Tiers:                                                         │
│  • Standard: Basic CDN + routing                                │
│  • Premium: WAF + Bot protection + Private Link                 │
│                                                                  │
│  Best for: Azure-native apps, .NET workloads,                  │
│            multi-region Azure deployments                        │
└─────────────────────────────────────────────────────────────────┘
```

---

## Google Cloud CDN

```
Key features:
• Integrated with Cloud Load Balancing
• Anycast IP (single IP globally)
• Cache modes: CACHE_ALL, USE_ORIGIN_HEADERS, FORCE_CACHE_ALL
• Signed URLs/Cookies
• Cloud Armor (WAF/DDoS)
• Media CDN (specialized for video)

Best for: GCP-native apps, YouTube-scale video (Media CDN)
Limitation: Fewer PoPs than Cloudflare/Akamai, less edge compute
```

---

## Budget Options

| Provider | Starting Price | Best For |
|----------|---------------|----------|
| BunnyCDN | $0.01/GB | Budget static sites, images |
| KeyCDN | $0.04/GB | Pay-as-you-go, no minimum |
| StackPath | $0.04/GB | Small-medium sites |
| Cloudflare (free) | $0/mo | Personal sites, basic protection |

---

## Full Comparison Matrix

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         CDN Provider Comparison Matrix                            │
├──────────────┬───────────┬───────────┬──────────┬─────────┬────────┬────────────┤
│              │CloudFront │Cloudflare │ Akamai   │ Fastly  │Az.FD   │Google CDN  │
├──────────────┼───────────┼───────────┼──────────┼─────────┼────────┼────────────┤
│ PoPs         │ 400+      │ 300+      │ 4100+    │ 90+     │ 150+   │ 150+       │
│ Capacity     │ 100+ Tbps │ 200+ Tbps │ 365 Tbps │ 65 Tbps │ ?      │ ?          │
│ Free tier    │ 1TB/mo    │ Unlimited │ ❌       │ ❌      │ ❌     │ ❌         │
│ Edge compute │ ✅        │ ✅ (best) │ ✅       │ ✅      │ ❌     │ ❌         │
│ Purge speed  │ 5-15 min  │ < 30s     │ 5-7s     │ <150ms  │ ~10min │ ~1min      │
│ WebSocket    │ ✅        │ ✅        │ ✅       │ ✅      │ ✅     │ ❌         │
│ HTTP/3       │ ✅        │ ✅        │ ✅       │ ✅      │ ✅     │ ✅         │
│ DDoS         │ Shield    │ Included  │ Prolexic │ Included│ Armor  │ Cloud Armor│
│ WAF          │ AWS WAF   │ Included  │ Kona     │ Sig.Sci │ Az WAF │ Cloud Armor│
│ Bot Mgmt     │ Bot Ctrl  │ Add-on    │ Bot Mgr  │ Sig.Sci │ ❌     │ reCAPTCHA  │
│ Image Opt    │ Lambda    │ ✅ Polish │ IM       │ ✅ IO   │ ❌     │ ❌         │
│ Video        │ MediaSvcs │ Stream    │ Media    │ ✅      │ ❌     │ Media CDN  │
│ Object Store │ S3        │ R2        │ NetStor  │ ❌      │ Blob   │ GCS        │
│ Pricing      │ Per-GB    │ Flat+ovg  │ Contract │ Per-GB  │ Per-GB │ Per-GB     │
│ Min commit   │ None      │ None      │ Yes      │ None    │ None   │ None       │
└──────────────┴───────────┴───────────┴──────────┴─────────┴────────┴────────────┘
```

---

## When to Choose Which Provider

```
┌─────────────────────────────────────────────────────────────────────┐
│  Decision Matrix                                                     │
├─────────────────────────────────────────┬───────────────────────────┤
│ Scenario                                │ Best Choice               │
├─────────────────────────────────────────┼───────────────────────────┤
│ AWS-native app, S3 origins              │ CloudFront                │
│ Free tier, good-enough for most         │ Cloudflare                │
│ Edge compute focus (Workers/KV/D1)      │ Cloudflare                │
│ Enterprise, maximum global reach        │ Akamai                    │
│ Instant purge critical (e-commerce)     │ Fastly                    │
│ Video/streaming at scale                │ Akamai / Fastly           │
│ Wasm at edge (Rust/Go)                  │ Fastly Compute@Edge       │
│ Azure-native app                        │ Azure Front Door          │
│ GCP-native app                          │ Google Cloud CDN          │
│ Budget, simple static sites             │ BunnyCDN / Cloudflare Free│
│ DDoS protection (primary concern)       │ Cloudflare / Akamai       │
│ Zero egress cost storage                │ Cloudflare R2             │
│ Next.js/Vercel deployment               │ Vercel (uses Cloudflare)  │
│ Full-stack edge platform                │ Cloudflare                │
└─────────────────────────────────────────┴───────────────────────────┘
```

---

## Multi-CDN Strategy

### DNS-Based Multi-CDN

```
Route 53 / NS1 / Cloudflare DNS
         │
         ├── Weighted routing:
         │   60% → CloudFront (cdn-cf.example.com)
         │   40% → Fastly (cdn-fastly.example.com)
         │
         ├── Failover routing:
         │   Primary: CloudFront
         │   Secondary: Cloudflare (health check fails → switch)
         │
         └── Latency-based:
             US users → CloudFront (better US peering)
             EU users → Cloudflare (more EU PoPs)
```

### RUM-Based Multi-CDN

```javascript
// Client-side CDN selection based on real performance
const CDN_HOSTS = [
  'cdn1.example.com', // CloudFront
  'cdn2.example.com', // Cloudflare
  'cdn3.example.com', // Fastly
];

async function selectFastestCDN() {
  const results = await Promise.allSettled(
    CDN_HOSTS.map(async (host) => {
      const start = performance.now();
      await fetch(`https://${host}/probe.gif`, { mode: 'no-cors' });
      return { host, latency: performance.now() - start };
    })
  );
  
  const successful = results
    .filter(r => r.status === 'fulfilled')
    .map(r => r.value)
    .sort((a, b) => a.latency - b.latency);
  
  return successful[0]?.host || CDN_HOSTS[0];
}
```

---

## Cost Optimization Tips

### CloudFront

```
1. Use Origin Shield (reduces origin fetches, improves hit ratio)
2. Enable compression (Brotli/gzip) - smaller = cheaper
3. Use CloudFront Functions ($0.10/M) instead of Lambda@Edge ($0.60/M)
4. Use Cache Policies (avoid forwarding unnecessary headers)
5. Reserved Pricing (1yr commit = 20-40% savings)
6. Use S3 as origin (no data transfer between S3 and CF in same region)
7. Security Savings Bundle (Shield Advanced + CloudFront + WAF discount)
```

### Cloudflare

```
1. Free plan handles most small-medium sites
2. Use R2 instead of S3 (zero egress = massive savings at scale)
3. Cache Everything page rule (cache HTML too)
4. Workers Free: 100K requests/day (enough for many use cases)
5. Argo Smart Routing: 30% latency improvement for $0.10/GB
6. Use Cloudflare Pages (free for most projects)
```

### General Cost Tips

```
┌─────────────────────────────────────────────────────────────────┐
│  Universal CDN Cost Optimization                                 │
│                                                                  │
│  1. Maximize cache hit ratio (fewer origin fetches = cheaper)   │
│  2. Compress everything (smaller responses = less bandwidth)    │
│  3. Use appropriate image formats (WebP/AVIF = 50%+ smaller)   │
│  4. Set long TTLs with versioned URLs                           │
│  5. Remove unnecessary query params from cache key              │
│  6. Use Vary header wisely (fewer variants = better hits)       │
│  7. Enable request collapsing / origin shield                   │
│  8. Monitor top URLs by bandwidth (optimize the expensive ones) │
│  9. Consider committed use discounts (1yr/3yr)                  │
│ 10. Evaluate multi-CDN: route cheap traffic to cheapest CDN    │
└─────────────────────────────────────────────────────────────────┘
```

### Cost Example: 100 TB/month delivery

| Provider | Estimated Cost | Notes |
|----------|---------------|-------|
| CloudFront | ~$8,500 | Standard pricing |
| CloudFront (committed) | ~$5,500 | 1-year commitment |
| Cloudflare Pro | ~$20/mo + Argo | Unmetered bandwidth |
| Cloudflare Enterprise | ~$5,000+ | Negotiated |
| Akamai | ~$4,000-15,000 | Contract dependent |
| Fastly | ~$7,500 | $0.08/GB average |
| BunnyCDN | ~$1,000 | $0.01/GB |
| Google Cloud CDN | ~$8,000 | $0.08/GB |

> Note: Cloudflare's flat-rate model makes it extremely cost-effective at scale. BunnyCDN is the budget king but with fewer features. CloudFront wins for AWS-integrated workloads.
