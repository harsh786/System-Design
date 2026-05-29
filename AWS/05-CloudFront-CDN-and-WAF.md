# CloudFront (CDN) & WAF - Complete Guide

## 1. CDN Fundamentals

### What is a CDN?

A Content Delivery Network (CDN) is a geographically distributed network of servers that caches and delivers content from the nearest location to the end user, reducing latency and improving performance.

### How a CDN Works

```
User Request → DNS Resolution → Nearest Edge Location → Cache Hit? 
                                                          ├── Yes → Return cached content (fast)
                                                          └── No  → Fetch from origin → Cache → Return
```

### Edge Locations Concept

- **Edge Location**: Server in a data center close to users, caches content
- **Origin Server**: The authoritative source of truth (S3, EC2, ALB, etc.)
- **PoP (Point of Presence)**: Physical data center housing edge servers

### Push vs Pull CDN

| Aspect | Push CDN | Pull CDN |
|--------|----------|----------|
| How content arrives | You upload/push content to CDN | CDN fetches from origin on first request |
| Control | Full control over what's cached | Automatic based on requests |
| Best for | Large, rarely changing files | Dynamic sites with many assets |
| Storage cost | Higher (pre-loaded) | Lower (on-demand) |
| Example | S3 + CloudFront with pre-warming | CloudFront with ALB origin |

**CloudFront is a Pull CDN** - it fetches content from origin on cache miss.

### Benefits of CDN

1. **Latency Reduction**: Content served from nearest edge (ms vs hundreds of ms)
2. **Origin Offload**: 80-99% of requests served from cache, origin handles only misses
3. **DDoS Protection**: Distributed architecture absorbs volumetric attacks
4. **Global Reach**: Serve users worldwide without deploying infrastructure everywhere
5. **Cost Savings**: Reduced origin bandwidth, AWS data transfer pricing
6. **Reliability**: If one edge fails, traffic routes to next nearest

---

## 2. CloudFront Architecture

### Edge Locations & Regional Edge Caches

```
┌─────────────────────────────────────────────────────────────────┐
│                    CloudFront Architecture                        │
│                                                                   │
│  User → Edge Location (400+) → Regional Edge Cache (13) → Origin │
│         (city-level)            (continent-level)                  │
│                                                                   │
│  Cache Hierarchy:                                                 │
│  L1: Edge Location (smallest cache, closest to user)             │
│  L2: Regional Edge Cache (larger cache, fewer locations)          │
│  L3: Origin (source of truth)                                    │
└─────────────────────────────────────────────────────────────────┘
```

- **Edge Locations**: 400+ globally, in major cities worldwide
- **Regional Edge Caches**: 13 locations (larger caches, between edge and origin)
  - Content evicted from edge may still be in regional edge cache
  - Reduces origin fetches significantly

### Request Flow

```
1. User makes request → DNS resolves to nearest edge location
2. Edge Location checks local cache
   ├── Cache HIT → Return immediately (fastest)
   └── Cache MISS → Check Regional Edge Cache
                    ├── Cache HIT → Return to edge, cache locally
                    └── Cache MISS → Fetch from Origin
                                     → Cache at Regional Edge
                                     → Cache at Edge Location
                                     → Return to user
```

### Distributions

A CloudFront **Distribution** is the configuration entity:
- **Domain name**: d1234abcdef.cloudfront.net (auto-assigned)
- **Alternate domain names (CNAMEs)**: cdn.example.com
- **Origins**: Where content comes from
- **Cache Behaviors**: How different URL paths are handled
- **Error Pages**: Custom error responses
- **Restrictions**: Geo-restrictions
- **SSL Certificate**: For HTTPS

### Origins

| Origin Type | Use Case | Configuration |
|-------------|----------|---------------|
| **S3 Bucket** | Static assets, websites | OAC for private access |
| **ALB** | Dynamic web apps | Custom origin, HTTP/HTTPS |
| **EC2** | Direct server access | Public IP required, custom origin |
| **API Gateway** | REST/HTTP APIs | Regional or edge-optimized |
| **Custom HTTP** | Any HTTP server | On-prem, other clouds |
| **MediaStore** | Live video streaming | Container-based origin |
| **MediaPackage** | Video on demand | Packaging origin |
| **S3 Static Website** | Static hosting | HTTP only origin |

### S3 Origin with OAC (Origin Access Control)

```
CloudFront Distribution
    │
    ├── OAC (Origin Access Control)
    │     └── Signs requests to S3 with SigV4
    │
    └── S3 Bucket
          └── Bucket Policy: Allow only CloudFront service principal
              with condition on distribution ID
```

S3 Bucket Policy:
```json
{
  "Statement": [{
    "Effect": "Allow",
    "Principal": {"Service": "cloudfront.amazonaws.com"},
    "Action": "s3:GetObject",
    "Resource": "arn:aws:s3:::my-bucket/*",
    "Condition": {
      "StringEquals": {
        "AWS:SourceArn": "arn:aws:cloudfront::111122223333:distribution/EDFDVBD6EXAMPLE"
      }
    }
  }]
}
```

### Origin Groups (Failover)

```
Origin Group
├── Primary Origin: us-east-1 ALB
└── Secondary Origin: eu-west-1 ALB
    
Failover triggers on: 500, 502, 503, 504, 404, 403 (configurable)
```

- Automatic failover when primary returns configured error codes
- Use for high availability across regions
- Both origins must serve same content structure

---

## 3. Cache Behaviors

### Structure

```
Distribution
├── Default Cache Behavior (*)        ← catches all unmatched paths
├── Cache Behavior: /api/*            ← forward all, no caching
├── Cache Behavior: /images/*         ← aggressive caching
├── Cache Behavior: /static/*.css     ← long TTL, compressed
└── Cache Behavior: /video/*          ← streaming optimized
```

Behaviors are evaluated in order (priority); first path pattern match wins.

### Cache Policy

Defines **what's included in the cache key** (determines cache uniqueness):

```
Cache Key = URL path + selected:
  ├── Headers (e.g., Accept-Language, Authorization)
  ├── Cookies (e.g., session_id, preferences)
  └── Query Strings (e.g., ?size=large&color=red)
```

**AWS Managed Cache Policies:**
- `CachingOptimized`: Minimal key, maximum caching (recommended for static)
- `CachingOptimizedForUncompressedObjects`: No Accept-Encoding normalization
- `CachingDisabled`: No caching (pass-through)
- `Amplify`: For AWS Amplify apps

### Origin Request Policy

Defines **what's forwarded to the origin** (independent of cache key):

- Forward headers origin needs (e.g., `Host`, `X-Forwarded-For`)
- Forward cookies for session management
- Forward query strings for server-side logic
- **Key insight**: You can forward values to origin WITHOUT including them in cache key

**AWS Managed Origin Request Policies:**
- `AllViewer`: Forward all viewer headers
- `AllViewerExceptHostHeader`: Forward all except Host
- `CORS-S3Origin`: Forward CORS headers
- `UserAgentRefererHeaders`: Forward User-Agent and Referer

### Response Headers Policy

Controls headers sent back to viewers:

- **CORS headers**: Access-Control-Allow-Origin, Methods, Headers
- **Security headers**: Strict-Transport-Security, X-Content-Type-Options, X-Frame-Options, Content-Security-Policy
- **Custom headers**: Add/remove/override any response header
- **Server-Timing**: Enable for performance metrics

### TTL (Time to Live)

| Setting | Value | Meaning |
|---------|-------|---------|
| Minimum TTL | 0 seconds | Floor for cache duration |
| Maximum TTL | 31,536,000 seconds (1 year) | Ceiling for cache duration |
| Default TTL | 86,400 seconds (24 hours) | Used when origin doesn't set Cache-Control |

**TTL Resolution Logic:**
```
If origin sends Cache-Control: max-age=X
  → Use X, clamped between Minimum and Maximum TTL

If origin sends Expires header (no Cache-Control)
  → Use calculated TTL from Expires

If origin sends neither
  → Use Default TTL
```

### Viewer Protocol Policy

| Option | Behavior |
|--------|----------|
| HTTP and HTTPS | Accept both protocols |
| **Redirect HTTP to HTTPS** | 301 redirect (recommended) |
| HTTPS Only | Reject HTTP with 403 |

### Allowed HTTP Methods

| Option | Methods | Use Case |
|--------|---------|----------|
| GET, HEAD | Read-only | Static content |
| GET, HEAD, OPTIONS | + CORS preflight | APIs with CORS |
| All Methods | + POST, PUT, PATCH, DELETE | Full API proxy |

### Compression

- **Automatic compression**: Enable gzip and Brotli
- Compresses objects 1,000-10,000,000 bytes
- Client must send `Accept-Encoding: gzip` or `Accept-Encoding: br`
- Reduces bandwidth 60-80% for text-based content
- Cache stores both compressed and uncompressed versions

---

## 4. Caching Deep Dive

### Cache Key Composition

```
Cache Key (determines uniqueness):
┌──────────────────────────────────────────────┐
│ Distribution domain                           │
│ + URL path: /images/photo.jpg                │
│ + Specified headers: Accept-Language: en     │
│ + Specified cookies: currency=USD            │
│ + Specified query strings: ?width=800        │
│ = Unique cache entry                         │
└──────────────────────────────────────────────┘
```

**More items in cache key = more unique entries = lower hit ratio**

### Cache-Control from Origin

```
# Cache for 1 hour, allow CDN to serve stale while revalidating
Cache-Control: public, max-age=3600, stale-while-revalidate=60

# Cache for 1 year (immutable content with versioned URLs)
Cache-Control: public, max-age=31536000, immutable

# Don't cache (dynamic content)
Cache-Control: no-cache, no-store, must-revalidate

# Private (user-specific, CDN should not cache)
Cache-Control: private, max-age=300
```

### Cache Invalidation

```bash
# Invalidate specific file
aws cloudfront create-invalidation \
  --distribution-id E1234567890 \
  --paths "/index.html"

# Invalidate with wildcard
aws cloudfront create-invalidation \
  --distribution-id E1234567890 \
  --paths "/images/*"

# Invalidate everything
aws cloudfront create-invalidation \
  --distribution-id E1234567890 \
  --paths "/*"
```

- First 1,000 invalidation paths/month: free
- Additional: $0.005 per path
- Wildcard (`/*`) counts as 1 path
- Propagation: typically 60-300 seconds globally

### Cache Hit Ratio Optimization

**Strategy 1: Minimize Cache Key**
```
BAD:  Cache key includes all headers, all cookies, all query strings
      → Almost every request is unique → ~0% hit ratio

GOOD: Cache key includes only what truly varies the content
      → Many requests share same cache entry → 90%+ hit ratio
```

**Strategy 2: Use Origin Shield**
```
Without Origin Shield:
Edge1 (miss) → Origin
Edge2 (miss) → Origin    ← 3 origin fetches for same content
Edge3 (miss) → Origin

With Origin Shield (single regional cache point):
Edge1 (miss) → Origin Shield (miss) → Origin   ← 1 origin fetch
Edge2 (miss) → Origin Shield (hit) → Return
Edge3 (miss) → Origin Shield (hit) → Return
```

**Strategy 3: Normalize Accept-Encoding**
- CloudFront normalizes to: `gzip`, `br`, or remove
- Prevents cache fragmentation from varied client headers

**Strategy 4: Versioned URLs**
```
# Instead of invalidating /style.css
/static/style.v2.css       ← New version, new cache entry
/static/style.abc123.css   ← Content hash in filename

Benefits:
- No invalidation cost or delay
- Old and new versions coexist during deployment
- Instant rollback by pointing to old version
```

**Strategy 5: Query String Ordering**
- CloudFront doesn't normalize query string order by default
- `?a=1&b=2` and `?b=2&a=1` are different cache keys
- Normalize at application level or with CloudFront Functions

### Origin Shield

```
User → Edge Location → Regional Edge Cache → Origin Shield → Origin
                                                    │
                                              Single point of
                                              entry to origin
```

- Additional caching layer before origin
- Choose Origin Shield region closest to your origin
- Reduces origin load for globally distributed viewers
- Improves cache hit ratio (one shared cache for all edges)
- Additional cost: per 10,000 requests ($0.0090-$0.012)

---

## 5. Security Features

### HTTPS Configuration

**Viewer Protocol (Client ↔ Edge):**
- TLS 1.0-1.3 supported
- Recommend enforcing TLS 1.2+
- Use security policy TLSv1.2_2021 or later

**Origin Protocol (Edge ↔ Origin):**
- Match Viewer: use same protocol as client
- HTTPS Only: always HTTPS to origin
- HTTP Only: always HTTP to origin (e.g., S3 website endpoint)

### SSL/TLS Certificates

| Option | Cost | IP | Use Case |
|--------|------|-----|----------|
| Default CloudFront cert | Free | Shared | *.cloudfront.net domain |
| ACM Certificate | Free | SNI | Custom domain (recommended) |
| Custom Certificate (SNI) | Free | Shared IP | Custom domain, modern clients |
| Custom Certificate (Dedicated IP) | $600/month | Dedicated | Legacy clients without SNI |

**ACM Certificate requirements:**
- Must be in **us-east-1** region (for CloudFront)
- Supports wildcard: *.example.com
- Auto-renewal (DNS or email validation)

### Signed URLs

```
Purpose: Restrict access to individual files with time-limited URLs

Signed URL components:
- Base URL: https://d1234.cloudfront.net/premium/video.mp4
- Policy: expiration time, optional IP restriction, optional start time
- Signature: RSA-SHA1 signed with CloudFront key pair
- Key-Pair-Id: Identifies which key was used

Example use case: Paid video download link valid for 1 hour

Canned Policy (simpler):
https://d1234.cloudfront.net/video.mp4?Expires=1680000000&Signature=ABC...&Key-Pair-Id=KXYZ

Custom Policy (more control):
https://d1234.cloudfront.net/video.mp4?Policy=BASE64...&Signature=ABC...&Key-Pair-Id=KXYZ
- Supports date ranges
- Supports IP restrictions
- Supports wildcard paths
```

### Signed Cookies

```
Purpose: Restrict access to multiple files without changing URLs

Set-Cookie: CloudFront-Policy=BASE64_POLICY
Set-Cookie: CloudFront-Signature=SIGNATURE
Set-Cookie: CloudFront-Key-Pair-Id=KEY_PAIR_ID

Use case: Premium streaming - user logs in, gets cookies, 
          all /premium/* content accessible without URL changes
```

**Signed URLs vs Signed Cookies:**
| Aspect | Signed URLs | Signed Cookies |
|--------|------------|----------------|
| Scope | Single file | Multiple files (path pattern) |
| URL change | Yes (adds parameters) | No (normal URLs) |
| Best for | Individual downloads | Streaming, member areas |
| RTMP | Required (cookies not supported) | Not supported |

### Origin Access Control (OAC)

Replaces the older Origin Access Identity (OAI):
- Supports all S3 features (SSE-KMS, S3 Object Lambda)
- Supports all HTTP methods (OAI was GET only)
- Uses IAM service principal
- Regional scope (better for multi-region)

### Geo-Restriction

```
Whitelist: Only allow access from specified countries
Blacklist: Block access from specified countries

Based on: GeoIP database (country-level, not region/city)
Response when blocked: 403 Forbidden

Use cases:
- Content licensing (movies available only in certain countries)
- Compliance (data sovereignty)
- Sanctions compliance
```

### Field-Level Encryption

```
Client → Edge (encrypt specific fields) → Origin (encrypted fields)
                                               │
                                          Only authorized 
                                          microservice can decrypt
                                          with private key

Example: Credit card number encrypted at edge
- Application servers see encrypted blob
- Only payment service has private key to decrypt
```

- Encrypt up to 10 fields per request
- Uses RSA encryption with public key at edge
- Adds another layer beyond HTTPS
- Protects against compromised application servers

---

## 6. CloudFront Functions vs Lambda@Edge

### Comparison Table

| Feature | CloudFront Functions | Lambda@Edge |
|---------|---------------------|-------------|
| **Event Types** | Viewer Request, Viewer Response | Viewer Request/Response, Origin Request/Response |
| **Runtime** | JavaScript (ECMAScript 5.1) | Node.js, Python |
| **Execution Time** | < 1 ms | 5s (viewer), 30s (origin) |
| **Memory** | 2 MB | 128 - 10,240 MB |
| **Package Size** | 10 KB | 1 MB (viewer), 50 MB (origin) |
| **Network Access** | No | Yes |
| **File System** | No | Yes (/tmp, 512 MB) |
| **Request Body** | No | Yes (origin events) |
| **Geo Headers** | Yes | Yes |
| **Scale** | Millions of requests/sec | Thousands of requests/sec |
| **Price** | $0.10 per million invocations | $0.60 per million + $0.00000625125/ms |
| **Deploy Location** | All edge locations | Regional edge caches |
| **Build/Test** | CloudFront console | Lambda console (us-east-1) |

### Event Flow

```
Viewer Request → [CloudFront Function / Lambda@Edge]
    │
    ├── Cache Hit → Viewer Response → [CloudFront Function / Lambda@Edge]
    │
    └── Cache Miss → Origin Request → [Lambda@Edge only]
                         │
                     Origin Server
                         │
                     Origin Response → [Lambda@Edge only]
                         │
                     Viewer Response → [CloudFront Function / Lambda@Edge]
```

### CloudFront Functions Use Cases

```javascript
// URL Rewrite: Add index.html for directory paths
function handler(event) {
  var request = event.request;
  var uri = request.uri;
  if (uri.endsWith('/')) {
    request.uri += 'index.html';
  } else if (!uri.includes('.')) {
    request.uri += '/index.html';
  }
  return request;
}

// Header Manipulation: Add security headers
function handler(event) {
  var response = event.response;
  var headers = response.headers;
  headers['strict-transport-security'] = { value: 'max-age=63072000' };
  headers['x-content-type-options'] = { value: 'nosniff' };
  headers['x-frame-options'] = { value: 'DENY' };
  return response;
}

// Cache Key Normalization: Normalize query strings
function handler(event) {
  var request = event.request;
  var params = request.querystring;
  // Remove marketing parameters from cache key
  delete params.utm_source;
  delete params.utm_medium;
  delete params.utm_campaign;
  return request;
}

// Simple JWT Validation
function handler(event) {
  var request = event.request;
  var token = request.headers.authorization;
  if (!token || !isValidToken(token.value)) {
    return { statusCode: 401, body: 'Unauthorized' };
  }
  return request;
}
```

### Lambda@Edge Use Cases

```python
# A/B Testing (Origin Request)
def lambda_handler(event, context):
    request = event['Records'][0]['cf']['request']
    headers = request['headers']
    
    # Check experiment cookie
    if 'cookie' in headers:
        for cookie in headers['cookie']:
            if 'experiment=B' in cookie['value']:
                request['origin']['custom']['domainName'] = 'experiment-b.example.com'
                return request
    
    # Default: experiment A
    return request

# Dynamic Origin Selection
def lambda_handler(event, context):
    request = event['Records'][0]['cf']['request']
    country = headers.get('cloudfront-viewer-country', [{'value': 'US'}])[0]['value']
    
    if country in ['DE', 'FR', 'IT']:
        request['origin']['custom']['domainName'] = 'eu-origin.example.com'
    elif country in ['JP', 'KR', 'AU']:
        request['origin']['custom']['domainName'] = 'apac-origin.example.com'
    
    return request

# Image Resizing (Origin Response)
def lambda_handler(event, context):
    response = event['Records'][0]['cf']['response']
    request = event['Records'][0]['cf']['request']
    
    if response['status'] == '200':
        # Resize image based on query string
        width = request['querystring'].get('w', '800')
        # Process image...
    
    return response
```

---

## 7. Advanced CloudFront

### Real-Time Logs

```
CloudFront → Kinesis Data Streams → Lambda/Firehose → S3/Elasticsearch

Fields available:
- Timestamp, edge location, response status
- Bytes sent, time to first byte
- Cache hit/miss, SSL protocol
- Client IP, User-Agent, Referer
- Request ID (for debugging)

Sampling rate: 1-100% (control cost)
Latency: seconds (near real-time)
```

### Standard Logs (Access Logs)

```
CloudFront → S3 Bucket (log files)

- Delivered every few minutes (not real-time)
- Tab-separated format
- Includes all request details
- Free (pay only for S3 storage)
- Use Athena for analysis
```

### Custom Error Pages

```
Origin returns 404 → CloudFront serves /errors/404.html (from S3)
Origin returns 500 → CloudFront serves /errors/500.html

Configuration:
- Error Code: 403, 404, 500, 502, 503, 504
- Response Page Path: /custom-error.html
- Response Code: Override (e.g., 404 → 200 for SPA)
- Error Caching TTL: How long to cache error (default 5 min)

SPA Use Case:
- All 403/404 → serve /index.html with 200 status
- Let client-side router handle paths
```

### Continuous Deployment

```
Production Distribution (90% traffic)
          │
Staging Distribution (10% traffic)
          │
    ┌─────┴─────┐
    │ Same domain│
    │ Traffic    │
    │ splitting  │
    └───────────┘

- Test changes with real traffic before full deployment
- Canary deployment: gradually shift traffic
- Rollback: instantly shift 100% back to production
- Session stickiness: same user always hits same distribution
```

### Price Classes

| Price Class | Regions Included | Cost |
|-------------|-----------------|------|
| All | All edge locations globally | Highest (best performance) |
| 200 | Excludes South America, Australia | Medium |
| 100 | US, Canada, Europe only | Lowest cost |

### HTTP/2 and HTTP/3

- **HTTP/2**: Enabled by default, multiplexing, header compression, server push
- **HTTP/3**: QUIC protocol, opt-in, UDP-based, faster connection setup
  - Better performance on lossy networks (mobile)
  - 0-RTT connection resumption

### WebSocket Support

- Persistent connections through CloudFront
- `Allowed Methods` must include all methods
- TTL should be set appropriately
- No caching for WebSocket traffic
- Use for real-time applications (chat, gaming, live updates)

### Origin Failover with Origin Groups

```yaml
Origin Group:
  Primary: ALB in us-east-1
  Failover: ALB in eu-west-1
  Failover criteria:
    - 500 Internal Server Error
    - 502 Bad Gateway
    - 503 Service Unavailable
    - 504 Gateway Timeout

Flow:
1. Request → Primary origin
2. Primary returns 503
3. CloudFront automatically retries with failover origin
4. Failover returns 200 → serve to user
```

### Streaming

- **RTMP**: Deprecated (September 2020)
- **HLS (HTTP Live Streaming)**: Segment-based, widely supported
- **DASH**: Similar to HLS, open standard
- Serve via S3 or MediaStore/MediaPackage as origin
- Use `Cache-Control` headers appropriate for segments vs manifests

---

## 8. AWS WAF (Web Application Firewall)

### Architecture

```
┌─────────────────────────────────────────────────┐
│                   Web ACL                         │
│                                                   │
│  ┌─────────────────────────────────────────────┐ │
│  │ Rule Group 1 (AWS Managed: Core Rule Set)   │ │
│  │  ├── Rule: SQLi Detection          [Block]  │ │
│  │  ├── Rule: XSS Detection           [Block]  │ │
│  │  └── Rule: Path Traversal          [Block]  │ │
│  └─────────────────────────────────────────────┘ │
│                                                   │
│  ┌─────────────────────────────────────────────┐ │
│  │ Rule Group 2 (Custom)                        │ │
│  │  ├── Rule: Rate Limit 2000/5min    [Block]  │ │
│  │  ├── Rule: Geo Block (sanctioned)  [Block]  │ │
│  │  └── Rule: Allow trusted IPs       [Allow]  │ │
│  └─────────────────────────────────────────────┘ │
│                                                   │
│  Default Action: Allow                            │
└─────────────────────────────────────────────────┘
         │
    Attached to: CloudFront, ALB, API Gateway, AppSync, Cognito
```

### Where WAF Attaches

| Resource | Scope | Notes |
|----------|-------|-------|
| CloudFront | Global | Web ACL must be in us-east-1 |
| ALB | Regional | Same region as ALB |
| API Gateway (REST) | Regional | Stage-level |
| AppSync | Regional | GraphQL API |
| Cognito User Pool | Regional | Hosted UI |
| App Runner | Regional | Service-level |
| Verified Access | Regional | Instance-level |

### Rule Types

**Regular Rules:**
- Match conditions → action
- Inspect request components (URI, headers, body, query, etc.)

**Rate-Based Rules:**
- Count requests per 5-minute window
- Trigger action when threshold exceeded
- Automatically unblock when rate drops
- Minimum threshold: 100 requests per 5 minutes
- Aggregation: IP, forwarded IP, custom keys

### Actions

| Action | Effect | Use Case |
|--------|--------|----------|
| **Allow** | Pass request through | Trusted IPs, known good |
| **Block** | Return 403 | Attacks, restricted access |
| **Count** | Log only, don't block | Testing rules before enforcing |
| **CAPTCHA** | Challenge with CAPTCHA | Suspected bots |
| **Challenge** | Silent JS challenge | Bot detection without UX impact |

---

## 9. WAF Rules Deep Dive

### AWS Managed Rule Groups

**Core Rule Set (CRS)**
- General web application protection
- OWASP Top 10 coverage
- SQL injection, XSS, file inclusion, etc.
- WCU: 700

**Known Bad Inputs**
- Request patterns known to be malicious
- Log4j/Log4Shell, Spring Shell
- WCU: 200

**SQL Database**
- SQL injection patterns specific to SQL databases
- WCU: 200

**Linux/POSIX OS**
- LFI, command injection targeting Linux
- WCU: 200

**Windows OS**
- PowerShell commands, Windows-specific attacks
- WCU: 200

**PHP Application**
- PHP-specific exploits and injections
- WCU: 100

**Bot Control**
```
Common Bot Control:
- Categorizes bots (verified, unverified)
- Allows search engines (Google, Bing)
- Blocks scrapers, crawlers
- WCU: 50
- Cost: $10/month + $1/million requests

Targeted Bot Control:
- Advanced (credential stuffing, account takeover)
- ML-based behavioral detection
- Browser fingerprinting
- Cost: $10/month + $10/million requests
```

**Account Takeover Prevention (ATP)**
```
- Monitors login page for credential stuffing
- Checks credentials against stolen credential databases
- Rate limits failed login attempts
- Requires login endpoint configuration
- Cost: $10/month + $1/million login attempts inspected
```

**Account Creation Fraud Prevention (ACFP)**
```
- Monitors registration page
- Detects fake account creation
- Phone/email validation signals
- Cost: $10/month + $1/million requests
```

### Custom Rules

**IP Set Rule:**
```json
{
  "Name": "BlockBadIPs",
  "Statement": {
    "IPSetReferenceStatement": {
      "ARN": "arn:aws:wafv2:...:ipset/bad-ips/..."
    }
  },
  "Action": {"Block": {}},
  "Priority": 1
}
```
- Supports IPv4 and IPv6 CIDR
- Up to 10,000 IP addresses per IP set

**Rate-Based Rule:**
```json
{
  "Name": "RateLimit",
  "Statement": {
    "RateBasedStatement": {
      "Limit": 2000,
      "AggregateKeyType": "IP",
      "ScopeDownStatement": {
        "ByteMatchStatement": {
          "SearchString": "/api/",
          "FieldToMatch": {"UriPath": {}},
          "PositionalConstraint": "STARTS_WITH"
        }
      }
    }
  },
  "Action": {"Block": {}}
}
```

**Geo Match:**
```json
{
  "Statement": {
    "GeoMatchStatement": {
      "CountryCodes": ["RU", "CN", "KP"]
    }
  },
  "Action": {"Block": {}}
}
```

**String Match:**
```json
{
  "Statement": {
    "ByteMatchStatement": {
      "SearchString": "admin",
      "FieldToMatch": {"UriPath": {}},
      "TextTransformations": [{"Priority": 0, "Type": "LOWERCASE"}],
      "PositionalConstraint": "CONTAINS"
    }
  }
}
```

**Size Constraint:**
```json
{
  "Statement": {
    "SizeConstraintStatement": {
      "FieldToMatch": {"Body": {}},
      "ComparisonOperator": "GT",
      "Size": 10000
    }
  },
  "Action": {"Block": {}}
}
```

### Rule Priority & Evaluation

```
Rules evaluated in numeric priority order (lowest number = first)

Priority 0: Allow trusted IPs          → Match? → Allow (stop)
Priority 1: Block bad IPs              → Match? → Block (stop)
Priority 2: Rate limit                  → Match? → Block (stop)
Priority 3: AWS Managed CRS            → Match? → Block (stop)
Priority 4: Bot Control                 → Match? → Block (stop)
...
Default Action: Allow                   → No rules matched → Allow
```

**First match wins** - once a rule matches, evaluation stops.

### Labels

```
Rule 1: If request from /api/* → Add label "api-request"
Rule 2: If has label "api-request" AND rate > 1000 → Block

Use cases:
- Different rate limits for different paths
- Tag requests for downstream rules
- Complex conditional logic across rule groups
```

### Scope-Down Statements

Narrow when a rate-based rule applies:
```
Rate-based rule: 500 requests/5min
Scope-down: Only requests to /login endpoint
Result: Rate limit login attempts separately from normal traffic
```

---

## 10. WAF + Shield + Firewall Manager

### AWS Shield Standard

- **Free** - automatically enabled on all AWS accounts
- Protection against L3/L4 DDoS attacks:
  - SYN floods
  - UDP reflection attacks
  - DNS amplification
- Applied to CloudFront, Route 53, Global Accelerator, ELB, EC2

### AWS Shield Advanced

| Feature | Details |
|---------|---------|
| **Cost** | $3,000/month + data transfer |
| **Protection** | L3, L4, and L7 DDoS |
| **DRT** | 24/7 DDoS Response Team access |
| **Cost Protection** | Refund for scaling during attack |
| **WAF Included** | WAF fees waived for associated resources |
| **Health Checks** | Route 53 health-based detection |
| **Visibility** | Near real-time attack metrics |
| **Automatic mitigation** | L7 rules created automatically |
| **Resources** | CloudFront, ALB, NLB, EIP, Global Accelerator |

### AWS Firewall Manager

```
Organization Root Account
    │
    ├── Security Admin Account (Firewall Manager admin)
    │     └── Policies:
    │           ├── WAF Policy → Applied to all ALBs in all accounts
    │           ├── Shield Advanced → Enabled on all CloudFront distributions
    │           ├── Security Group → Audit/enforce SG rules
    │           └── Network Firewall → VPC-level filtering
    │
    ├── Account A (auto-compliant)
    ├── Account B (auto-compliant)
    └── Account C (auto-compliant)
```

**Prerequisites:**
- AWS Organizations with all features enabled
- Designate Firewall Manager admin account
- Enable AWS Config in all accounts/regions

### WAF Logging

| Destination | Latency | Cost | Use Case |
|-------------|---------|------|----------|
| S3 | Minutes | Cheapest | Archival, compliance |
| CloudWatch Logs | Seconds | Medium | Real-time dashboards |
| Kinesis Data Firehose | Seconds | Medium-High | Stream processing |

Log prefix requirement: `aws-waf-logs-*`

### WAF Metrics (CloudWatch)

- `AllowedRequests` - count per rule/WebACL
- `BlockedRequests` - count per rule/WebACL
- `CountedRequests` - count-action requests
- `PassedRequests` - passed rule group evaluation
- `CaptchaRequests` - CAPTCHA challenges issued
- `ChallengeRequests` - JS challenges issued

---

## 11. DDoS Protection Architecture

### Multi-Layer Defense

```
┌─────────────────────────────────────────────────────────┐
│ Layer 1: Edge (Global)                                   │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Route 53 → CloudFront → WAF + Shield Advanced       │ │
│ │ - Absorb volumetric attacks at edge                  │ │
│ │ - Rate limiting, geo-blocking, bot control           │ │
│ │ - Auto-scaling across 400+ edge locations            │ │
│ └─────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────┤
│ Layer 2: Network (VPC)                                   │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ - NACLs: Stateless rules, block known bad IPs       │ │
│ │ - Security Groups: Allow only expected traffic       │ │
│ │ - VPC Flow Logs: Detect anomalies                   │ │
│ │ - Network Firewall: Deep packet inspection          │ │
│ └─────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────┤
│ Layer 3: Application                                     │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ - ALB + WAF: Application-level filtering            │ │
│ │ - Auto Scaling: Handle legitimate surges            │ │
│ │ - API Gateway: Throttling (10,000 RPS default)      │ │
│ │ - Application rate limiting (per user/API key)      │ │
│ └─────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────┤
│ Layer 4: Monitoring & Response                           │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ - CloudWatch Alarms: Spike detection                │ │
│ │ - Shield Advanced: Attack notifications             │ │
│ │ - Lambda: Auto-update WAF IP blacklist              │ │
│ │ - DRT engagement for active attacks                 │ │
│ └─────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

### Best Practices

1. **Always use CloudFront** even for single-region apps (absorbs attacks at edge)
2. **Hide origin**: Never expose origin IP directly
3. **Scale ahead**: Use Shield Advanced health checks for faster detection
4. **Defense in depth**: Multiple layers, each reducing attack surface
5. **Test regularly**: Simulate attacks in non-production
6. **Runbooks**: Document response procedures for DDoS events
7. **Pre-position**: WAF rules ready to activate during attack

---

## 12. Scenario-Based Interview Questions

### Q1: "CloudFront cache hit ratio is 30% - how to improve?"

**Answer:**
```
Diagnosis steps:
1. Check cache key composition - too many headers/cookies/query strings?
2. Check TTLs - too short?
3. Check content characteristics - mostly unique dynamic content?

Solutions (priority order):
1. Reduce cache key:
   - Remove unnecessary headers (keep only Accept-Encoding, Accept-Language if needed)
   - Remove unnecessary cookies (forward only session cookies to origin, not to cache key)
   - Whitelist only required query strings

2. Enable Origin Shield:
   - Single additional cache layer
   - Dramatically reduces origin fetches

3. Increase TTLs:
   - Static assets: 1 year (use versioned URLs for updates)
   - Semi-dynamic: 5-15 minutes
   - Set appropriate Cache-Control headers from origin

4. Normalize query strings:
   - Use CloudFront Function to sort/remove unnecessary params
   - Remove tracking params (utm_*) from cache key

5. Use versioned URLs:
   - /static/app.v2.3.1.js instead of /static/app.js
   - Eliminates need for invalidation

Expected result: 85-95%+ hit ratio for content-heavy sites
```

### Q2: "Design CDN for global e-commerce platform"

**Answer:**
```
Architecture:
┌──────────────────────────────────────────────────┐
│ CloudFront Distribution                           │
│                                                    │
│ Behaviors:                                         │
│ /static/*     → S3 (1yr TTL, versioned)           │
│ /images/*     → S3 (1yr TTL, Origin Shield)       │
│ /api/*        → ALB (0 TTL, all methods, CORS)    │
│ /product/*    → ALB (5min TTL, vary by cookie)    │
│ /*            → ALB (default, short TTL)          │
│                                                    │
│ Origins:                                           │
│ ├── S3 (static assets) + OAC                      │
│ ├── ALB us-east-1 (primary)                       │
│ └── ALB eu-west-1 (failover via Origin Group)     │
│                                                    │
│ Security:                                          │
│ ├── WAF: Rate limiting, SQL injection, XSS        │
│ ├── Shield Advanced                                │
│ ├── Geo-restriction: Block sanctioned countries   │
│ └── HTTPS everywhere (redirect HTTP)              │
│                                                    │
│ Edge Computing:                                    │
│ ├── CloudFront Function: URL rewrites, headers    │
│ └── Lambda@Edge: Personalization, A/B testing     │
└──────────────────────────────────────────────────┘
```

### Q3: "Protect against DDoS attacks - architecture"

**Answer:**
```
1. Edge Layer:
   - CloudFront in front of everything (absorbs L3/L4 at edge)
   - WAF with rate-based rules (2000 req/5min per IP)
   - Bot Control managed rule group
   - Shield Advanced for L7 protection + DRT access

2. Network Layer:
   - Keep origins private (no public IPs if possible)
   - NACLs blocking known bad CIDRs
   - Security Groups allowing only CloudFront IP ranges

3. Application Layer:
   - API Gateway with throttling
   - Auto Scaling to handle legitimate spikes
   - Application-level rate limiting per user/API key

4. Monitoring:
   - CloudWatch alarms on request spikes
   - Shield Advanced attack notifications → SNS → PagerDuty
   - Lambda auto-remediation (update WAF IP sets)

5. Response Plan:
   - Activate pre-built WAF rules
   - Engage Shield Advanced DRT
   - Scale origin infrastructure
   - Communicate with users
```

### Q4: "WAF blocking legitimate traffic - troubleshoot"

**Answer:**
```
1. Identify what's being blocked:
   - Enable WAF logging (CloudWatch Logs for real-time)
   - Check terminatingRuleId in logs
   - Look at blocked request details (URI, headers, body)

2. Common false positives:
   - Managed rules too aggressive (CRS blocking valid input)
   - Rate-based rules too low for legitimate traffic
   - Geo-blocking hitting VPN users

3. Remediation steps:
   a. Set problematic rule to Count mode (stop blocking, keep logging)
   b. Analyze Count logs to confirm false positive
   c. Options:
      - Add Allow rule (higher priority) for legitimate patterns
      - Use scope-down to exclude specific paths
      - Override specific rule in managed group to Count
      - Create label-based exception logic
   
4. Prevention:
   - Always deploy new rules in Count mode first
   - Use continuous deployment to test with real traffic
   - Set up alerts for sudden spike in blocked requests
```

### Q5: "Implement A/B testing at the edge"

**Answer:**
```
Lambda@Edge (Origin Request event):

1. Check for existing experiment cookie
2. If no cookie, assign user to variant (weighted random)
3. Route to appropriate origin/path
4. Set cookie in response for consistency

Implementation:
- Origin Request: Route based on cookie/random assignment
- Origin Response: Set experiment cookie for future requests

Benefits:
- No client-side flicker
- Server-side rendering matches variant
- Consistent experience (cookie stickiness)
- No origin code changes needed
- Can route to entirely different origins

Alternatively: CloudFront Continuous Deployment
- Native traffic splitting (10/90, 50/50, etc.)
- No code required
- Limited to two variants
```

### Q6: "Secure premium video content delivery"

**Answer:**
```
Architecture:
1. S3 bucket (private) → CloudFront with OAC
2. User authenticates → Application generates Signed Cookies
3. Signed cookies valid for session duration (e.g., 4 hours)
4. Cookie path: /premium/* (all premium content)
5. IP restriction optional (prevent cookie sharing)

Additional security:
- Token-based URL signing for downloads
- Watermarking via Lambda@Edge (inject user ID in video)
- Geo-restriction for licensing compliance
- DRM integration (Widevine/FairPlay via AWS Elemental)

Content protection:
- No direct S3 access (OAC enforced)
- Short-lived tokens (expire after viewing session)
- Referrer checking via CloudFront Function
- CORS restricted to your domain only
```

### Q7: "Reduce origin load by 90% with CloudFront"

**Answer:**
```
Strategy:
1. Aggressive cache policies:
   - Static assets: Cache-Control: max-age=31536000 (1 year)
   - Use content hashes in filenames for cache busting
   
2. Enable Origin Shield:
   - Single point of entry to origin
   - Collapses concurrent misses into single origin fetch

3. Minimize cache key:
   - Static: URL only (no headers, cookies, query strings)
   - Dynamic: Only vary on what truly changes response

4. Stale-while-revalidate:
   - Serve stale content while fetching fresh in background
   - User never waits for origin

5. Custom error caching:
   - Cache 404s for 5 minutes (prevents repeated lookups)
   - Cache 500s briefly (prevents thundering herd on failure)

6. CloudFront Functions:
   - Normalize requests to maximize cache sharing
   - Remove unnecessary query parameters
   - Standardize headers

Measurement:
- Monitor cache hit ratio in CloudWatch
- Track origin request count
- Target: <10% of requests reach origin
```

### Q8: "Multi-region failover with CloudFront"

**Answer:**
```
Origin Groups configuration:
Primary: ALB in us-east-1
Secondary: ALB in eu-west-1

Failover triggers: 500, 502, 503, 504

For more sophisticated routing:
- Lambda@Edge on Origin Request
- Check origin health (Route 53 health checks)
- Dynamic origin selection based on:
  - Health status
  - Viewer geography
  - Latency

Combined with:
- Route 53 health checks on origins
- Cross-region data replication (RDS, DynamoDB Global Tables)
- S3 Cross-Region Replication for static assets

RTO: Seconds (automatic CloudFront failover)
RPO: Depends on data replication strategy
```

### Q9: "How to serve dynamic content via CloudFront"

**Answer:**
```
Dynamic content through CloudFront benefits:
- Persistent connections to origin (connection reuse)
- TCP/TLS optimization (edge terminates, keeps warm connection to origin)
- HTTP/2 multiplexing
- Route optimization (AWS backbone network)
- Even with TTL=0, faster than direct to origin

Configuration:
- Cache Policy: CachingDisabled
- Origin Request Policy: AllViewer (forward everything)
- Allowed Methods: All
- TTL: 0 (always forward to origin)
- Compress objects: Yes (still compresses on the fly)

Semi-dynamic (personalized but cacheable):
- Vary by specific cookies (e.g., currency, language)
- Short TTL (5-60 seconds)
- Origin Shield to reduce origin hits during TTL window
```

### Q10: "Design rate limiting that allows legitimate bursts"

**Answer:**
```
Multi-tier rate limiting:

Tier 1: WAF rate-based (coarse)
- 10,000 requests/5min per IP (general)
- Scope-down: /api/* paths only
- Action: CAPTCHA (not immediate block)

Tier 2: WAF rate-based (sensitive endpoints)
- 100 requests/5min per IP for /login
- 50 requests/5min per IP for /register
- Action: Block

Tier 3: Application level (fine-grained)
- Token bucket algorithm per API key
- Allows bursts up to bucket size
- Sustained rate limited to refill rate
- 429 response with Retry-After header

Key design choices:
- WAF rate limit is per 5-min window (not sliding)
- Combine with CAPTCHA for suspected abuse (not immediate block)
- Whitelist known good IPs (monitoring, partners)
- Use custom keys (API key header) instead of just IP
  for better accuracy behind shared IPs
```

### Q11: "Block bad bots while allowing search engines"

**Answer:**
```
Solution: AWS WAF Bot Control

1. Enable Bot Control managed rule group:
   - Verified bots (Google, Bing): Allow
   - Unverified bots: Challenge or Block
   - Categories: scraper, crawler, monitoring, etc.

2. Custom rules on top:
   - Allow specific User-Agents you trust
   - Block known bad bot signatures
   - Rate limit unverified bot category

3. Signal-based detection:
   - Challenge action (silent JS check)
   - Legitimate browsers pass automatically
   - Headless browsers/scripts fail or require more compute

4. Behavioral signals (Targeted Bot Control):
   - Mouse movement patterns
   - Typing cadence
   - Navigation patterns
   - ML-based anomaly detection

5. robots.txt (complementary, not security):
   - Only respected by well-behaved bots
   - Not a security measure
```

### Q12: "CloudFront for Single Page Application (SPA)"

**Answer:**
```
Configuration:
1. Origin: S3 bucket with OAC
2. Default root object: index.html
3. Custom error response:
   - 403 → /index.html (200 status, TTL 0)
   - 404 → /index.html (200 status, TTL 0)
   (Client-side router handles all paths)

4. Cache behaviors:
   - /static/*: Long TTL (assets have content hash)
   - /*: Short TTL or no-cache for index.html

5. CloudFront Function (Viewer Request):
   - Rewrite paths without extension to /index.html
   - OR handle client-side routing without custom error pages

6. Security headers via Response Headers Policy:
   - CSP, HSTS, X-Frame-Options, X-Content-Type-Options
```

### Q13: "Migrate from custom CDN to CloudFront - strategy"

**Answer:**
```
1. Setup phase:
   - Create CloudFront distribution
   - Configure origins (same as current CDN)
   - Mirror cache behaviors and TTLs
   - SSL cert in ACM (us-east-1)

2. Testing phase:
   - Use distribution domain (d1234.cloudfront.net) for testing
   - Verify caching, headers, compression
   - Test all edge cases (error pages, redirects, CORS)

3. Migration phase:
   - DNS cutover: CNAME cdn.example.com → CloudFront
   - Low TTL DNS first (60s), then switch
   - Monitor hit ratios, error rates, latency

4. Optimization phase:
   - Tune cache policies based on real metrics
   - Enable Origin Shield
   - Add CloudFront Functions for header manipulation
   - Implement WAF rules

5. Rollback plan:
   - Keep old CDN active during transition
   - DNS rollback within seconds if issues
```

### Q14: "CloudFront + API Gateway vs ALB - when to use which?"

**Answer:**
```
CloudFront + API Gateway:
- Serverless APIs (Lambda backend)
- Need throttling, API keys, usage plans
- Request/response transformation
- Edge-optimized for global APIs
- WebSocket APIs
- Cost: Per-request pricing

CloudFront + ALB:
- Container/EC2 backends
- High throughput (no per-request API Gateway cost)
- Need sticky sessions, host-based routing
- Simpler setup for traditional web apps
- WebSocket support
- Cost: Hourly + LCU pricing (cheaper at high volume)

Both benefit from CloudFront:
- TLS termination at edge
- Caching (even short TTLs help)
- AWS backbone routing
- WAF + Shield protection
- Global edge network
```

### Q15: "Design content delivery for multi-tenant SaaS"

**Answer:**
```
Architecture:
- Single CloudFront distribution
- Wildcard cert: *.customers.saas.com
- Alternate CNAMEs: *.customers.saas.com

Routing (Lambda@Edge):
- Extract tenant from Host header
- Route to tenant-specific origin path/bucket
- Apply tenant-specific caching rules

Cache strategy:
- Cache key includes Host header (tenant isolation)
- Shared static assets: /shared/* (long TTL, cross-tenant)
- Tenant assets: /tenant/* (include Host in key)

Security:
- WAF: Rate limiting per tenant (custom header key)
- Signed URLs for private tenant content
- OAC for S3 origins

Multi-tenant isolation:
- Separate S3 prefixes per tenant
- Lambda@Edge validates tenant access
- No cross-tenant cache pollution (Host in cache key)
```

---

## Quick Reference: Key Numbers

| Metric | Value |
|--------|-------|
| Edge Locations | 400+ |
| Regional Edge Caches | 13 |
| Max file size (cache) | 30 GB |
| Max TTL | 31,536,000 seconds (1 year) |
| Default TTL | 86,400 seconds (24 hours) |
| Free invalidation paths/month | 1,000 |
| Invalidation propagation | 60-300 seconds |
| WAF Web ACLs per region | 100 |
| WAF rules per Web ACL | 1,500 WCU |
| WAF IP set max | 10,000 addresses |
| Rate-based rule minimum | 100 requests/5 min |
| Rate-based rule window | 5 minutes |
| Shield Advanced cost | $3,000/month |
| CloudFront Functions timeout | < 1 ms |
| Lambda@Edge timeout (viewer) | 5 seconds |
| Lambda@Edge timeout (origin) | 30 seconds |
| HTTP/3 | QUIC, opt-in |
| Origin Shield regions | 12 |

---

## Key Exam Tips

1. **OAC > OAI**: Always recommend OAC for S3 origins (newer, more features)
2. **CloudFront Functions vs Lambda@Edge**: Functions for simple, fast tasks; Lambda@Edge for complex logic
3. **Cache key = cache uniqueness**: More items in key = lower hit ratio
4. **Origin Shield**: Best answer for "reduce origin load" or "improve hit ratio"
5. **Signed URLs vs Cookies**: URLs for single files, Cookies for multiple files
6. **WAF Count mode**: Always test rules in Count before Block
7. **Shield Advanced**: Mention for any DDoS protection question ($3000/month)
8. **ACM certs for CloudFront**: Must be in us-east-1
9. **Price Class**: Tradeoff between cost and global coverage
10. **Versioned URLs**: Better than invalidation (instant, no cost, rollback-friendly)
