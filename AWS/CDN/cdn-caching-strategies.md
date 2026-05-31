# CDN Caching Strategies - Complete Guide

## Cache-Control Header Complete Guide

### Header Syntax

```
Cache-Control: directive1, directive2, ...
```

### All Directives Explained

```
┌────────────────────────────────────────────────────────────────────────┐
│                    Cache-Control Directives                              │
├─────────────────────────┬──────────────────────────────────────────────┤
│ Directive               │ Meaning                                       │
├─────────────────────────┼──────────────────────────────────────────────┤
│ public                  │ Any cache (CDN, proxy) can store             │
│ private                 │ Only browser cache, NOT CDN/proxy            │
│ no-store                │ Don't cache at all, anywhere                 │
│ no-cache                │ Cache but revalidate every time              │
│ max-age=N              │ Fresh for N seconds (browser + CDN)          │
│ s-maxage=N             │ Fresh for N seconds (CDN/proxy ONLY)         │
│ stale-while-revalidate │ Serve stale while fetching fresh in bg       │
│ stale-if-error         │ Serve stale if origin returns error          │
│ immutable              │ Never revalidate (content will never change) │
│ must-revalidate        │ Don't serve stale, must check origin         │
│ proxy-revalidate       │ Same as must-revalidate but for CDN only     │
│ no-transform           │ Don't modify content (no compression change) │
└─────────────────────────┴──────────────────────────────────────────────┘
```

### Real-World Examples by Content Type

```http
# Static assets with content hash (e.g., app.a1b2c3.js)
Cache-Control: public, max-age=31536000, immutable

# HTML pages (cache at CDN, short TTL)
Cache-Control: public, s-maxage=3600, max-age=0, stale-while-revalidate=86400

# API responses (personalized)
Cache-Control: private, max-age=60, stale-while-revalidate=300

# User-specific data (never cache at CDN)
Cache-Control: private, no-store

# Images without hash (moderate TTL)
Cache-Control: public, max-age=86400, stale-while-revalidate=604800

# Error pages
Cache-Control: public, max-age=300, stale-if-error=86400

# Real-time data (stock prices)
Cache-Control: no-cache, no-store, must-revalidate
```

### s-maxage vs max-age

```
Cache-Control: public, max-age=60, s-maxage=3600

Browser:  caches for 60 seconds
CDN:      caches for 3600 seconds (1 hour)

Use case: CDN serves stale to many users while browser
          checks for fresh content more often.
```

### stale-while-revalidate in Action

```
Cache-Control: public, max-age=3600, stale-while-revalidate=86400

Timeline:
0s      → Cached (fresh)
3600s   → max-age expired, but stale-while-revalidate active
          CDN serves STALE response immediately (fast!)
          CDN fetches fresh copy in background
3601s   → Next request gets fresh copy
90000s  → stale-while-revalidate expired, must wait for origin
```

---

## Vary Header and Content Negotiation

### How Vary Works

The `Vary` header tells CDN which request headers create different cache variants.

```http
# Response from origin:
Vary: Accept-Encoding, Accept-Language

# CDN creates separate cache entries for:
# GET /page + Accept-Encoding: gzip     → Cache entry 1
# GET /page + Accept-Encoding: br       → Cache entry 2
# GET /page + Accept-Language: en       → Cache entry 3
# GET /page + Accept-Language: fr       → Cache entry 4
```

### Common Vary Configurations

```http
# Compression variants
Vary: Accept-Encoding

# Image format negotiation
Vary: Accept
# Allows: image/webp vs image/jpeg vs image/avif

# Mobile vs Desktop (DANGEROUS - high cardinality)
Vary: User-Agent  # ❌ BAD: thousands of unique User-Agents

# Better approach for device detection:
Vary: X-Device-Type  # ✅ Edge normalizes to: mobile/tablet/desktop
```

### Vary Pitfalls

| Problem | Solution |
|---------|----------|
| `Vary: *` | Disables caching entirely |
| `Vary: User-Agent` | Infinite variants, 0% hit rate |
| `Vary: Cookie` | Every user gets unique cache entry |
| Too many Vary headers | Combinatorial explosion of entries |

---

## Conditional Requests (ETag / Last-Modified)

### ETag Flow

```
First Request:
Client ──GET /api/data──▶ CDN/Origin
Client ◀── 200 OK ────── CDN/Origin
           ETag: "abc123"
           Cache-Control: no-cache

Subsequent Request (revalidation):
Client ──GET /api/data──────────────▶ CDN/Origin
         If-None-Match: "abc123"
         
Case A: Content unchanged
Client ◀── 304 Not Modified ─────── CDN/Origin
           (no body, saves bandwidth)

Case B: Content changed
Client ◀── 200 OK ──────────────── CDN/Origin
           ETag: "def456"
           (full body)
```

### Last-Modified Flow

```http
# Response:
Last-Modified: Wed, 21 Oct 2024 07:28:00 GMT

# Revalidation request:
If-Modified-Since: Wed, 21 Oct 2024 07:28:00 GMT

# Response if unchanged:
304 Not Modified
```

### ETag Types

| Type | Format | Use Case |
|------|--------|----------|
| Strong | `"abc123"` | Byte-for-byte identical |
| Weak | `W/"abc123"` | Semantically equivalent |

---

## Cache Key Design

### What Makes a Unique Cache Entry?

```
Default cache key = Scheme + Host + Path + Query String

Example:
https://cdn.example.com/images/hero.jpg?v=2&size=large

Cache key: https|cdn.example.com|/images/hero.jpg|v=2&size=large
```

### Cache Key Customization

```
┌──────────────────────────────────────────────────────────────┐
│                    Cache Key Components                        │
├──────────────────┬───────────────────────────────────────────┤
│ Component        │ Include in key?                            │
├──────────────────┼───────────────────────────────────────────┤
│ Host             │ Always                                    │
│ Path             │ Always                                    │
│ Query string     │ Configurable (all, some, none)           │
│ Headers (Vary)   │ Accept-Encoding, custom headers          │
│ Cookies          │ Specific cookies only                     │
│ Device type      │ Normalized (mobile/desktop)              │
│ Country/Geo      │ If geo-personalized content              │
│ Protocol         │ Usually no (http ≈ https)                │
└──────────────────┴───────────────────────────────────────────┘
```

### CloudFront Cache Key Policy Example

```json
{
  "CachePolicyConfig": {
    "Name": "OptimizedCaching",
    "MinTTL": 1,
    "MaxTTL": 86400,
    "DefaultTTL": 3600,
    "ParametersInCacheKeyAndForwardedToOrigin": {
      "EnableAcceptEncodingGzip": true,
      "EnableAcceptEncodingBrotli": true,
      "HeadersConfig": {
        "HeaderBehavior": "whitelist",
        "Headers": ["X-Device-Type", "CloudFront-Viewer-Country"]
      },
      "CookiesConfig": {
        "CookieBehavior": "whitelist",
        "Cookies": ["session_variant"]
      },
      "QueryStringsConfig": {
        "QueryStringBehavior": "whitelist",
        "QueryStrings": ["v", "size", "format"]
      }
    }
  }
}
```

### Query String Ordering

```
# These should be the SAME cache entry:
/api?color=red&size=large
/api?size=large&color=red

# Solution: CDN normalizes query string order
# CloudFront: automatic
# Cloudflare: Sort Query String setting
# Fastly: custom VCL
```

---

## Cache Invalidation Patterns

### 1. Purge (Hard Invalidation)

```
┌─────────────────────────────────────────────────────┐
│  Purge: Immediately remove from all edge caches     │
│                                                     │
│  POST /purge                                        │
│  { "url": "https://cdn.example.com/image.jpg" }    │
│                                                     │
│  Propagation time:                                  │
│  • Fastly: < 150ms (instant purge)                 │
│  • Cloudflare: < 30 seconds                        │
│  • CloudFront: 5-15 minutes                        │
│  • Akamai: 5-7 seconds (Fast Purge)               │
└─────────────────────────────────────────────────────┘
```

### 2. Soft Purge (Stale + Revalidate)

```
# Marks content as stale rather than deleting it
# Next request triggers revalidation, but stale is served immediately

Fastly Soft Purge:
  POST /purge/url
  Fastly-Soft-Purge: 1

Result: Content marked stale → serves stale-while-revalidate → fetches fresh
```

### 3. Surrogate Keys / Tags

```http
# Origin response:
Surrogate-Key: product-123 category-electronics homepage

# Purge all content tagged with "product-123":
POST /purge
Surrogate-Key: product-123

# This purges ALL URLs tagged with that key:
#   /products/123
#   /products/123/reviews
#   /category/electronics (has product-123 listed)
#   /homepage (shows product-123 in featured)
```

### 4. Wildcard/Prefix Purge

```bash
# CloudFront: Invalidation with wildcard
aws cloudfront create-invalidation \
  --distribution-id E1234 \
  --paths "/images/*" "/api/products/*"

# Cloudflare: Purge by prefix
curl -X POST "https://api.cloudflare.com/client/v4/zones/{zone}/purge_cache" \
  -d '{"prefixes": ["cdn.example.com/images/"]}'
```

### Invalidation Strategy Comparison

| Strategy | Speed | Granularity | Cost |
|----------|-------|-------------|------|
| URL purge | Fast | Single URL | Low per URL |
| Wildcard purge | Medium | Path prefix | Medium |
| Surrogate key purge | Fast | Logical group | Low |
| Purge all | Instant | Everything | High (cache cold) |
| TTL-based expiry | Slow (wait) | All matching | Free |
| Versioned URLs | Instant | Per asset | Free |

### Best Practice: Versioned URLs

```html
<!-- Instead of purging, use content-addressable URLs -->
<link rel="stylesheet" href="/css/app.a1b2c3d4.css">
<script src="/js/bundle.e5f6g7h8.js"></script>
<img src="/img/hero-v3.webp">

<!-- Cache forever, new version = new URL = instant update -->
Cache-Control: public, max-age=31536000, immutable
```

---

## Cache Warming Strategies

### What is Cache Warming?

Pre-populate CDN cache before users hit it (avoid cold cache after deploy/purge).

```
┌─────────────────────────────────────────────────────────────┐
│                    Cache Warming Approaches                    │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. Crawler-based: Bot requests all URLs from all PoPs     │
│  2. Preload header: Origin tells CDN to prefetch           │
│  3. Origin push: Push content to CDN proactively           │
│  4. Synthetic traffic: Route test traffic through CDN      │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Implementation Example

```python
import requests
from concurrent.futures import ThreadPoolExecutor

# Warm cache by requesting from multiple PoP locations
URLS_TO_WARM = [
    "https://cdn.example.com/",
    "https://cdn.example.com/products",
    "https://cdn.example.com/api/catalog",
]

# Request from different regions (via DNS or headers)
REGIONS = ["us-east", "eu-west", "ap-south"]

def warm_url(url, region):
    headers = {"X-Warm-Region": region}
    resp = requests.get(url, headers=headers)
    print(f"[{region}] {url}: {resp.status_code} ({resp.headers.get('X-Cache')})")

with ThreadPoolExecutor(max_workers=20) as executor:
    for url in URLS_TO_WARM:
        for region in REGIONS:
            executor.submit(warm_url, url, region)
```

---

## Cache Stampede / Thundering Herd Prevention

### The Problem

```
Cache expires → 1000 concurrent users all get MISS → 1000 requests hit origin

Timeline:
T=0:     Cache entry expires
T=0.001: Request 1 → MISS → fetch from origin
T=0.002: Request 2 → MISS → fetch from origin
T=0.003: Request 3 → MISS → fetch from origin
...
T=0.100: Request 1000 → MISS → fetch from origin
Origin: 💀 (overwhelmed)
```

### Solutions

```
┌────────────────────────────────────────────────────────────────────┐
│ Solution 1: Request Collapsing (Coalescing)                         │
│                                                                     │
│ T=0.001: Request 1 → MISS → fetch from origin                     │
│ T=0.002: Request 2 → MISS → WAIT (collapse behind request 1)      │
│ T=0.003: Request 3 → MISS → WAIT (collapse behind request 1)      │
│ T=0.200: Origin responds → serve to ALL 1000 waiters              │
│                                                                     │
│ Origin sees: 1 request (not 1000)                                  │
├────────────────────────────────────────────────────────────────────┤
│ Solution 2: Stale-While-Revalidate                                 │
│                                                                     │
│ T=0.001: Request 1 → STALE (serve immediately) + async refresh    │
│ T=0.002: Request 2 → STALE (serve immediately)                    │
│ T=0.200: Background refresh completes → cache updated              │
│                                                                     │
│ Users see: instant response (stale but fast)                       │
├────────────────────────────────────────────────────────────────────┤
│ Solution 3: Lock / Mutex                                           │
│                                                                     │
│ First request acquires lock → fetches from origin                  │
│ Other requests wait or get stale                                   │
│ Lock released → all get fresh content                              │
├────────────────────────────────────────────────────────────────────┤
│ Solution 4: Probabilistic Early Expiration                         │
│                                                                     │
│ TTL remaining: 100s                                                │
│ Each request has probability of triggering refresh:                │
│   P(refresh) = 1 - e^(-β * (now - (expiry - TTL)))               │
│ Result: one lucky request refreshes before actual expiry           │
└────────────────────────────────────────────────────────────────────┘
```

### CDN Provider Support

| Provider | Request Collapsing | Stale-While-Revalidate |
|----------|-------------------|----------------------|
| Cloudflare | ✅ (default) | ✅ |
| CloudFront | ✅ (origin shield) | ✅ |
| Fastly | ✅ (request collapsing) | ✅ |
| Akamai | ✅ (tiered distribution) | ✅ |

---

## Negative Caching

### Caching Error Responses

```http
# Cache 404s to prevent origin hammering
# (e.g., crawler hitting non-existent URLs)

# Origin response for missing content:
HTTP/1.1 404 Not Found
Cache-Control: public, max-age=300

# CloudFront Error Caching:
# Custom Error Response:
#   Error Code: 404
#   Error Caching TTL: 300 seconds
#   Custom Error Page: /404.html
```

### What to Cache

| Status Code | Cache? | TTL | Reason |
|-------------|--------|-----|--------|
| 404 | ✅ | 5 min | Prevent origin hammering |
| 403 | ✅ | 1 min | Auth decisions are stable short-term |
| 500 | ⚠️ | 10 sec | Brief protection, but don't cache long |
| 502/503 | ❌ | 0 | Transient, origin might recover |
| 429 | ⚠️ | Per Retry-After | Rate limit response |

---

## Streaming / Chunked Caching

### Video Segment Caching

```
┌────────────────────────────────────────────────────────┐
│  HLS Video Caching Strategy                             │
│                                                        │
│  manifest.m3u8          → Cache: 2-6 seconds (live)   │
│                         → Cache: 1 hour (VOD)         │
│                                                        │
│  segment-001.ts (4s)   → Cache: 1 year (immutable)   │
│  segment-002.ts (4s)   → Cache: 1 year (immutable)   │
│  segment-003.ts (4s)   → Cache: 1 year (immutable)   │
│                                                        │
│  For live: manifest changes every segment duration    │
│  Segments once created never change → cache forever   │
└────────────────────────────────────────────────────────┘
```

### Range Request Caching

```http
# Large file downloads (e.g., 2GB software update)
# CDN caches full file, serves range requests from cache

GET /update.zip HTTP/1.1
Range: bytes=0-1048575

HTTP/1.1 206 Partial Content
Content-Range: bytes 0-1048575/2147483648
Content-Length: 1048576

# CDN behavior:
# 1. First range request → fetch full object (or range from origin)
# 2. Cache full object
# 3. Serve subsequent ranges from cache
```

---

## Dynamic Content Caching

### What Can Be Cached Dynamically?

```
┌─────────────────────────────────────────────────────────────┐
│           Dynamic Caching Decision Tree                       │
│                                                             │
│  Is response personalized per user?                         │
│    YES → Is personalization in a small part of page?        │
│           YES → Use ESI/Fragment caching                    │
│           NO  → Cache at browser only (private)            │
│    NO  → Does it change frequently?                         │
│           YES → Short TTL (1-60s) + stale-while-revalidate │
│           NO  → Long TTL (hours/days)                      │
└─────────────────────────────────────────────────────────────┘
```

### API Response Caching

```http
# GET /api/products?category=electronics
# Same response for all users → cache at CDN

Cache-Control: public, s-maxage=60, stale-while-revalidate=300
Surrogate-Key: products category-electronics

# GET /api/user/profile
# Different per user → don't cache at CDN

Cache-Control: private, max-age=60
```

### Personalization at Edge

```javascript
// Cloudflare Worker: Personalize at edge without busting cache
addEventListener('fetch', event => {
  event.respondWith(handleRequest(event.request));
});

async function handleRequest(request) {
  // Cache the base response (same for all)
  const cacheKey = new URL(request.url);
  cacheKey.searchParams.delete('user_id');
  
  let response = await caches.default.match(cacheKey);
  if (!response) {
    response = await fetch(cacheKey);
    // Cache the generic version
    response = new Response(response.body, response);
    response.headers.set('Cache-Control', 'public, s-maxage=3600');
    event.waitUntil(caches.default.put(cacheKey, response.clone()));
  }
  
  // Personalize at edge (from cookie/header)
  const country = request.headers.get('CF-IPCountry');
  let body = await response.text();
  body = body.replace('{{COUNTRY}}', country);
  
  return new Response(body, response);
}
```

---

## Fragment Caching (ESI - Edge Side Includes)

### How ESI Works

```html
<!-- Page template cached for 1 hour -->
<html>
<body>
  <header>
    <!-- User-specific nav, cached 5 min per user -->
    <esi:include src="/fragments/nav?user=123" />
  </header>
  
  <main>
    <!-- Product listing, cached 10 min for all -->
    <esi:include src="/fragments/products" />
  </main>
  
  <footer>
    <!-- Static footer, cached 1 day -->
    <esi:include src="/fragments/footer" />
  </footer>
</body>
</html>
```

```
┌──────────────────────────────────────────────────────────┐
│  ESI Processing at CDN Edge                               │
│                                                          │
│  1. CDN receives page with <esi:include> tags            │
│  2. For each fragment:                                    │
│     - Check cache for fragment URL                       │
│     - If HIT → inline cached fragment                   │
│     - If MISS → fetch fragment from origin              │
│  3. Assemble complete page                               │
│  4. Return assembled page to user                        │
│                                                          │
│  Cache independently:                                    │
│  /page (1hr) + /nav (5min) + /products (10min)          │
│                                                          │
│  Supported by: Akamai, Fastly (VCL), Varnish            │
│  NOT supported by: CloudFront, Cloudflare (use Workers) │
└──────────────────────────────────────────────────────────┘
```

---

## Cache Hierarchies

### L1 → L2 → L3 → Origin

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Cache Hierarchy                                    │
│                                                                     │
│  L1: Edge Cache (per PoP)                                          │
│  ├── Size: 1-10 TB per PoP                                         │
│  ├── Latency: < 5ms                                                │
│  ├── Hit ratio: 80-95% (popular content)                           │
│  └── TTL: respects Cache-Control                                    │
│                                                                     │
│  L2: Regional Cache (per region)                                    │
│  ├── Size: 50-500 TB                                                │
│  ├── Latency: 10-30ms                                              │
│  ├── Hit ratio: 95-99% (after L1 miss)                             │
│  └── Aggregates misses from many L1 PoPs                           │
│                                                                     │
│  L3: Origin Shield (1-3 globally)                                  │
│  ├── Size: 500 TB+                                                  │
│  ├── Latency: 30-100ms                                             │
│  ├── Hit ratio: 99%+ (only truly new content misses)               │
│  └── Request collapsing, single origin fetch                       │
│                                                                     │
│  Origin:                                                            │
│  └── Only sees 0.1-1% of total traffic                             │
└─────────────────────────────────────────────────────────────────────┘
```

### Inclusive vs Exclusive Caching

| Type | Behavior | Used By |
|------|----------|---------|
| Inclusive | All levels may hold same content | Most CDNs |
| Exclusive | Content exists at only one level | Some custom setups |
| Hierarchical | Fill from nearest parent that has it | Akamai, CloudFront |

---

## Complete Cache-Control Recipes

```http
# ────────────────────────────────────────────────
# STATIC ASSETS (JS, CSS with content hash)
# ────────────────────────────────────────────────
Cache-Control: public, max-age=31536000, immutable
# Cache for 1 year, never revalidate

# ────────────────────────────────────────────────
# HTML PAGES (server-rendered)
# ────────────────────────────────────────────────
Cache-Control: public, s-maxage=3600, max-age=0, stale-while-revalidate=86400, stale-if-error=86400
# CDN: 1hr fresh, serve stale up to 24hr while revalidating
# Browser: always revalidate (max-age=0)

# ────────────────────────────────────────────────
# API (public, non-personalized)
# ────────────────────────────────────────────────
Cache-Control: public, s-maxage=30, stale-while-revalidate=60
Surrogate-Key: api products
# CDN: 30s fresh, serve stale 60s while revalidating

# ────────────────────────────────────────────────
# API (personalized per user)
# ────────────────────────────────────────────────
Cache-Control: private, max-age=60, stale-while-revalidate=300
# Browser only, no CDN caching

# ────────────────────────────────────────────────
# IMAGES (no content hash)
# ────────────────────────────────────────────────
Cache-Control: public, max-age=86400, stale-while-revalidate=604800
# 1 day fresh, serve stale up to 7 days

# ────────────────────────────────────────────────
# FONTS
# ────────────────────────────────────────────────
Cache-Control: public, max-age=31536000, immutable
# Fonts rarely change, cache forever

# ────────────────────────────────────────────────
# VIDEO MANIFEST (live)
# ────────────────────────────────────────────────
Cache-Control: public, max-age=2, stale-while-revalidate=2
# Must be very fresh for live streaming

# ────────────────────────────────────────────────
# VIDEO SEGMENTS
# ────────────────────────────────────────────────
Cache-Control: public, max-age=31536000, immutable
# Segments are immutable once created

# ────────────────────────────────────────────────
# NEVER CACHE (sensitive data)
# ────────────────────────────────────────────────
Cache-Control: no-store, no-cache, must-revalidate, private
Pragma: no-cache
# Belt and suspenders
```
