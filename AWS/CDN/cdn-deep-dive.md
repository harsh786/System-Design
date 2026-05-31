# CDN Deep Dive: Content Delivery Networks and AWS CloudFront

This note explains what a CDN is, how it differs from WAFs and load balancers, and the main CDN and CDN-adjacent options in AWS.

The core idea:

```text
User
  -> nearest CDN edge location
      -> serve cached content if available
      -> otherwise fetch from origin
  -> origin: S3 / ALB / EC2 / API Gateway / custom server / media origin
```

A CDN mainly answers:

```text
Can this content be served from an edge location close to the user,
instead of making every request travel to the origin?
```

---

## 1. What Is a CDN?

CDN means **Content Delivery Network**. It is a globally distributed network of edge locations that caches and delivers content closer to users.

Without a CDN:

```text
User in India
  -> origin server in us-east-1
  -> long network path
  -> higher latency
  -> origin handles every request
```

With a CDN:

```text
User in India
  -> nearby CDN edge
      -> cache hit: response served immediately
      -> cache miss: edge fetches from origin and stores response
```

The CDN improves:

- Latency.
- Throughput.
- Availability.
- Origin offload.
- Global scalability.
- DDoS absorption at the edge.
- TLS termination near users.
- Static and dynamic content delivery.

---

## 2. What a CDN Can Cache

Common cacheable content:

- Images.
- CSS.
- JavaScript.
- Fonts.
- Videos.
- Static HTML.
- Downloadable files.
- Public API responses.
- Product catalog responses.
- Search suggestions with short TTL.
- GraphQL or REST responses when cache keys are designed carefully.

Usually not cached by default:

- Login responses.
- Payment mutations.
- Personalized dashboards.
- User-specific private data.
- POST/PUT/PATCH/DELETE responses.
- Highly sensitive data.

Important point:

```text
CDN caching is safe only when the cache key fully separates users, tenants,
languages, devices, authorization scopes, and other dimensions that change
the response.
```

---

## 3. CDN Core Components

### 3.1 Edge Location

An edge location is a CDN point of presence close to users.

It handles:

- TLS connection from viewer.
- Cache lookup.
- Serving cached content.
- Forwarding misses to origin.
- Running lightweight edge logic.
- Applying security controls such as WAF when integrated.

### 3.2 Origin

The origin is the source of truth for content.

Common origins:

- S3 bucket.
- Application Load Balancer.
- EC2 instance.
- ECS or EKS service behind ALB.
- API Gateway.
- Media origin.
- On-premises server.
- Any custom HTTP server.

### 3.3 Distribution

A distribution is the CDN configuration.

It defines:

- Domain names.
- Origins.
- Cache behaviors.
- TLS certificates.
- Allowed HTTP methods.
- Cache policies.
- Origin request policies.
- Response headers policies.
- Logging.
- WAF association.
- Edge functions.

### 3.4 Cache Behavior

A cache behavior tells the CDN how to handle a subset of requests.

Example:

```text
/static/*
  origin: S3
  cache TTL: 30 days
  allow methods: GET, HEAD

/api/*
  origin: ALB
  cache TTL: 0 or short TTL
  forward Authorization header

/images/*
  origin: image service
  cache TTL: 7 days
  include width and format query params in cache key
```

### 3.5 Cache Key

The cache key determines whether two requests are considered the same cached object.

Possible cache key inputs:

- Host.
- Path.
- Query parameters.
- Headers.
- Cookies.
- HTTP method.
- Accept-Encoding.

Example:

```text
Cache key:
  host + path + query(width,format) + accept-encoding
```

Bad cache key:

```text
path only
```

If the response differs by user, language, device, or authorization scope, those dimensions must be included or the response must not be cached.

---

## 4. Cache Hit and Cache Miss

### 4.1 Cache Hit

The CDN already has a fresh copy.

```text
User -> CDN edge -> response from edge
```

Benefits:

- Low latency.
- No origin load.
- Better global performance.

### 4.2 Cache Miss

The CDN does not have the object or the object is stale.

```text
User -> CDN edge -> origin -> CDN edge -> user
```

The CDN may store the response for future requests depending on cache headers and policies.

### 4.3 Cache Revalidation

When cached content becomes stale, the CDN can revalidate with the origin.

Common HTTP headers:

```http
If-None-Match: "etag-value"
If-Modified-Since: Wed, 01 Jan 2025 00:00:00 GMT
```

Origin can respond:

```http
304 Not Modified
```

This tells the CDN to reuse the cached object without downloading the body again.

---

## 5. CDN vs WAF vs Load Balancer

| Component | Main Job | Layer | Example Decision |
|-----------|----------|-------|------------------|
| CDN | Cache and deliver content near users | L7/edge | Serve `/app.js` from Mumbai edge |
| WAF | Block malicious web requests | L7 security | Block SQL injection payload |
| L4 Load Balancer | Distribute TCP/UDP connections | L4 | Send TCP connection to target A |
| L7 Load Balancer | Route HTTP requests to services | L7 | `/orders` goes to order service |
| API Gateway | Govern API calls | L7 API control | Validate JWT and enforce quota |

Simple distinction:

```text
CDN:
  Make content faster and reduce origin load.

WAF:
  Stop malicious or abusive HTTP requests.

Load Balancer:
  Distribute traffic across healthy backends.

API Gateway:
  Authenticate, authorize, validate, meter, and route API calls.
```

---

## 6. CDN vs WAF

| Aspect | CDN | WAF |
|--------|-----|-----|
| Main purpose | Performance and origin offload | Security filtering |
| Primary action | Cache, deliver, accelerate | Allow, block, count, CAPTCHA, challenge |
| Inspects request? | Yes, for routing/cache key | Yes, for threat detection |
| Caches responses | Yes | No |
| Blocks SQLi/XSS | Only if WAF integrated | Yes |
| Protects against bots | Only with security features | Yes, with bot rules |
| Typical AWS service | CloudFront | AWS WAF |

They are often used together:

```text
User
  -> CloudFront CDN
      -> AWS WAF attached to CloudFront
      -> cache hit or origin request
  -> origin
```

At CloudFront, WAF can block bad traffic before it reaches your region or origin.

---

## 7. CDN vs Load Balancer

| Aspect | CDN | Load Balancer |
|--------|-----|---------------|
| Main purpose | Serve content from edge cache | Distribute traffic to backend targets |
| Geography | Global edge network | Usually regional, sometimes global |
| Caching | Core capability | Not usually |
| Origin offload | High for cacheable content | No cache offload by default |
| Routing | Cache behavior and origin selection | Target group or backend selection |
| Good for | Static assets, video, global apps, cacheable APIs | Web services, APIs, TCP/UDP services |
| AWS example | CloudFront | ALB, NLB, GWLB |

Typical architecture:

```text
User
  -> CloudFront
  -> ALB
  -> ECS/EKS/EC2 application
```

CloudFront handles global edge acceleration and caching.
ALB handles regional application routing to healthy targets.

---

## 8. CDN vs API Gateway

| Aspect | CDN | API Gateway |
|--------|-----|-------------|
| Main purpose | Speed, caching, edge delivery | API management and governance |
| Auth | Limited or edge logic | Core capability |
| Quotas/API keys | No, not primary | Core capability |
| Request validation | Limited | Common |
| Caching | Core capability | Optional API cache in some gateways |
| Developer portal | No | Often yes |
| Best for | Global content and cacheable responses | Public/private API control |

They can be combined:

```text
Client
  -> CloudFront
  -> API Gateway
  -> Lambda / services
```

Use this when:

- Users are global.
- You want custom domain, TLS, WAF, and caching at the edge.
- API Gateway handles API-level policies behind CloudFront.

---

## 9. AWS CDN Landscape

In AWS, the primary CDN service is:

```text
Amazon CloudFront
```

AWS does not have many separate CDN products in the same way it has multiple load balancer types. Instead, it has **CloudFront** plus several CDN-related or edge-acceleration services.

| AWS Service | Is It a CDN? | Role |
|-------------|--------------|------|
| Amazon CloudFront | Yes | Main AWS CDN for static, dynamic, API, and video delivery |
| CloudFront Functions | CDN edge compute | Lightweight JavaScript at viewer edge |
| Lambda@Edge | CDN edge compute | Heavier request/response logic at CloudFront edge |
| AWS WAF with CloudFront | CDN security integration | Web attack and bot filtering at edge |
| AWS Shield | DDoS protection | DDoS protection for edge and AWS resources |
| AWS Global Accelerator | Not a CDN | Anycast network acceleration for TCP/UDP without caching |
| S3 Transfer Acceleration | Not a CDN | Speeds uploads/downloads to S3 using edge network |
| AWS Elemental MediaPackage | Media origin, not CDN | Prepares video streams that CloudFront can deliver |
| AWS Elemental MediaStore | Media origin, not CDN | Low-latency media storage origin for CloudFront |
| AWS Amplify Hosting | Uses CDN | Managed frontend hosting backed by CloudFront |

Short answer:

```text
The AWS CDN is Amazon CloudFront.
Other AWS services either integrate with CloudFront, secure it, compute at its
edge, or accelerate traffic without being full CDNs.
```

---

## 10. Amazon CloudFront

Amazon CloudFront is AWS's CDN. It securely delivers data, video, applications, and APIs globally with low latency and high transfer speeds.

CloudFront can deliver:

- Static websites.
- Single-page applications.
- Images and assets.
- Video streaming.
- File downloads.
- APIs.
- Dynamic web applications.
- Software updates.

CloudFront can use these as origins:

- Amazon S3.
- Application Load Balancer.
- EC2.
- API Gateway.
- AWS Elemental MediaPackage.
- AWS Elemental MediaStore.
- Custom HTTP origin.

Basic flow:

```text
Viewer
  -> CloudFront edge
      -> cache hit: serve response
      -> cache miss: fetch from origin
  -> origin
```

---

## 11. CloudFront Key Capabilities

### 11.1 Global Edge Delivery

CloudFront serves requests from edge locations close to users.

Benefits:

- Lower round-trip latency.
- Faster TLS negotiation.
- Reduced origin load.
- Better global user experience.

### 11.2 Static Content Caching

Best use case:

```text
/static/app.v123.js
/images/logo.png
/fonts/inter.woff2
```

Recommended strategy:

- Use versioned file names.
- Cache for long TTL.
- Avoid frequent invalidations.

Example:

```http
Cache-Control: public, max-age=31536000, immutable
```

### 11.3 Dynamic Content Acceleration

CloudFront can also help dynamic requests by:

- Terminating TLS near the user.
- Reusing optimized connections to origins.
- Using AWS backbone network.
- Applying compression.
- Running edge logic.

Even when TTL is zero, CloudFront may still improve network path performance.

### 11.4 Cache Behaviors

Cache behaviors route different path patterns to different origins and policies.

Example:

```text
/static/* -> S3 origin, long cache
/api/*    -> ALB origin, no cache or short cache
/video/*  -> media origin, optimized streaming
```

### 11.5 Origin Access Control

Origin Access Control, or OAC, secures S3 origins so users cannot bypass CloudFront and directly access the S3 bucket.

```text
User
  -> CloudFront
  -> S3 bucket private to CloudFront
```

The AWS docs show OAC being created with SigV4 signing for S3 origins.

Use OAC instead of making the bucket public.

### 11.6 Origin Groups and Failover

CloudFront can use origin failover patterns.

Example:

```text
Primary origin: ALB in us-east-1
Secondary origin: ALB in us-west-2

If primary returns configured failure status:
  retry secondary origin
```

This improves availability for origin failures.

### 11.7 Origin Shield

Origin Shield adds an extra centralized caching layer between edge locations and the origin.

```text
Viewer edge
  -> regional edge cache
  -> Origin Shield
  -> origin
```

Best for:

- High origin cost.
- Many global cache misses for same object.
- Reducing duplicate origin fetches.
- Improving cache hit ratio.

### 11.8 Invalidation

Invalidation removes cached objects before TTL expiry.

Example:

```text
Invalidate /index.html
Invalidate /assets/*
```

Best practice:

- Use invalidation for HTML or emergency purges.
- Use versioned asset names for JS, CSS, images, and files.

Better:

```text
/app.v1.js -> /app.v2.js
```

Instead of:

```text
Overwrite /app.js and invalidate constantly
```

### 11.9 Signed URLs and Signed Cookies

CloudFront can restrict access to private content.

Use signed URLs for:

- One file.
- Temporary download link.
- Private video link.

Use signed cookies for:

- Access to many files.
- Private course content.
- Subscription media library.

Example:

```text
User authenticates in app
  -> app generates signed CloudFront URL
  -> user downloads private file through CloudFront
```

### 11.10 Field-Level Encryption

Field-level encryption protects sensitive fields before they reach origin applications.

Use case:

- Encrypt payment-related or sensitive form fields at the edge.
- Only authorized backend components can decrypt.

This is specialized and not needed for most basic CDN setups.

### 11.11 Compression

CloudFront can compress supported objects.

Benefits:

- Lower bandwidth.
- Faster page load.
- Better mobile performance.

Common encodings:

- gzip.
- brotli, depending on configuration and viewer support.

### 11.12 HTTP/2 and HTTP/3

CloudFront supports modern HTTP protocols for viewer connections.

Benefits:

- Multiplexing.
- Better connection efficiency.
- Lower latency.
- Improved performance on lossy networks with HTTP/3 over QUIC.

### 11.13 Logs and Metrics

CloudFront observability:

- Standard logs.
- Real-time logs.
- CloudWatch metrics.
- Cache hit ratio.
- Origin latency.
- Error rate.
- Bytes downloaded/uploaded.
- Top paths.
- Viewer locations.
- TLS errors.

---

## 12. CloudFront Functions

CloudFront Functions run lightweight JavaScript at the edge.

Best for:

- Header manipulation.
- URL rewrites.
- Redirects.
- Simple authentication checks.
- A/B routing by cookie.
- Normalizing cache keys.

Characteristics:

- Very low latency.
- High scale.
- Runs at viewer request or viewer response events.
- Lightweight runtime.

Example uses:

```text
/old-path -> /new-path
Add security headers
Redirect HTTP-style hostnames
Normalize trailing slashes
Route by country header
```

Use CloudFront Functions when logic is small and latency-sensitive.

---

## 13. Lambda@Edge

Lambda@Edge runs Lambda functions in response to CloudFront events.

Best for:

- More complex logic than CloudFront Functions.
- Origin request manipulation.
- Origin response manipulation.
- Dynamic origin selection.
- Advanced A/B testing.
- Authentication flows.
- Custom response generation.

CloudFront event points:

- Viewer request.
- Viewer response.
- Origin request.
- Origin response.

Tradeoff:

- More powerful than CloudFront Functions.
- Higher latency and operational complexity.
- Separate pricing.

Rule of thumb:

```text
Use CloudFront Functions for simple viewer-side transformations.
Use Lambda@Edge for heavier logic or origin-facing events.
```

---

## 14. AWS WAF with CloudFront

AWS WAF can be attached to CloudFront distributions.

```text
User
  -> CloudFront + AWS WAF
      -> block bad requests
      -> serve cache hit or fetch origin
  -> origin
```

Benefits:

- Blocks malicious traffic at the edge.
- Reduces origin attack load.
- Applies managed WAF rules globally.
- Works well with bot control and rate-based rules.

Use for:

- SQL injection protection.
- XSS protection.
- Bad bot filtering.
- IP reputation blocking.
- Login/signup abuse reduction.
- HTTP flood mitigation as part of a broader DDoS strategy.

---

## 15. AWS Shield with CloudFront

AWS Shield provides DDoS protection.

CloudFront benefits from AWS edge DDoS protections. Shield Standard is automatically included for AWS services such as CloudFront. Shield Advanced adds stronger protection, cost protections, and response support for high-risk workloads.

Difference:

```text
CloudFront:
  CDN and edge delivery.

AWS WAF:
  Web request filtering.

AWS Shield:
  DDoS protection.
```

---

## 16. AWS Global Accelerator vs CloudFront

Global Accelerator is often confused with CDN.

| Aspect | CloudFront | Global Accelerator |
|--------|------------|--------------------|
| Is CDN? | Yes | No |
| Caches content | Yes | No |
| Protocols | HTTP/HTTPS and content delivery focus | TCP/UDP acceleration |
| Entry | Edge locations | Anycast static IPs |
| Best for | Websites, APIs, video, static assets | Gaming, VoIP, TCP/UDP apps, regional failover |
| Origin | HTTP origins and AWS origins | ALB, NLB, EC2, Elastic IP endpoints |

Use CloudFront when:

- You need caching.
- You serve HTTP content.
- You want CDN behavior.

Use Global Accelerator when:

- You need static anycast IPs.
- You need TCP/UDP acceleration.
- You need fast regional failover without HTTP caching.

---

## 17. S3 Transfer Acceleration vs CloudFront

S3 Transfer Acceleration speeds transfers into and out of S3 using AWS edge locations.

| Aspect | CloudFront | S3 Transfer Acceleration |
|--------|------------|--------------------------|
| Main job | CDN caching and delivery | Faster S3 uploads/downloads |
| Caching | Yes | No, not as CDN cache |
| Best for | Serving content to many users | Users uploading large files to S3 |
| Access pattern | Many reads, cacheable | Direct S3 object transfer |

Use CloudFront for content distribution.
Use S3 Transfer Acceleration for speeding S3 transfers, especially uploads from distant clients.

---

## 18. AWS Media Services and CloudFront

For video workloads, CloudFront is the CDN, while media services prepare or store media.

Common services:

- AWS Elemental MediaPackage.
- AWS Elemental MediaStore.
- AWS Elemental MediaConvert.
- AWS Elemental MediaLive.

Example:

```text
Live stream
  -> MediaLive
  -> MediaPackage
  -> CloudFront
  -> viewers
```

CloudFront delivers the video segments globally.
Media services encode, package, or prepare the streams.

---

## 19. AWS Amplify Hosting and CloudFront

AWS Amplify Hosting provides managed frontend hosting and uses CloudFront under the hood for global delivery.

Use Amplify Hosting when:

- You want simple deployment for frontend apps.
- You use React, Next.js, Vue, Angular, or static sites.
- You want CI/CD, preview branches, custom domains, and CDN delivery managed together.

If you need lower-level CDN control, use CloudFront directly.

---

## 20. Common CDN Architecture Patterns

### 20.1 Static Website

```text
User
  -> CloudFront
  -> private S3 bucket with OAC
```

Use:

- Long TTL for versioned assets.
- Short TTL or invalidation for `index.html`.
- OAC to keep S3 private.
- Custom domain and TLS certificate.

### 20.2 Web App Behind ALB

```text
User
  -> CloudFront + AWS WAF
  -> ALB
  -> ECS/EKS/EC2 app
```

Use:

- Cache static paths.
- Forward dynamic paths to ALB.
- Apply WAF at CloudFront.
- Use ALB for regional load balancing.

### 20.3 API Acceleration

```text
Client
  -> CloudFront
  -> API Gateway or ALB
  -> service
```

Use:

- Short TTL for safe GET responses.
- No caching for mutations.
- Include correct auth/tenant dimensions in cache key if caching private API data.
- Use WAF for API attack protection.

### 20.4 Image Optimization

```text
User
  -> CloudFront
  -> image transformation service
  -> S3 original images
```

Cache key:

```text
path + width + height + format + quality
```

Use:

- Long TTL for generated variants.
- Query parameter allowlist.
- Origin Shield if many edges request the same generated image.

### 20.5 Video Streaming

```text
Viewer
  -> CloudFront
  -> MediaPackage / MediaStore / S3
```

Use:

- Segment caching.
- Signed URLs or signed cookies for paid content.
- Origin failover for high availability.

---

## 21. Cache-Control Strategy

### 21.1 Versioned Static Assets

Use long TTL:

```http
Cache-Control: public, max-age=31536000, immutable
```

File names should change when content changes:

```text
app.7f3a9c.js
styles.b18cd.css
```

### 21.2 HTML Entry Point

Use short TTL:

```http
Cache-Control: public, max-age=60
```

Or use invalidation after deployment:

```text
Invalidate /index.html
```

### 21.3 API Responses

Cache only safe responses:

```http
Cache-Control: public, max-age=30
```

For private responses:

```http
Cache-Control: private, no-store
```

or avoid CDN caching unless the cache key is correctly scoped.

---

## 22. Security Considerations

### 22.1 Protect the Origin

Bad design:

```text
User can access both:
  https://cdn.example.com/file.jpg
  https://s3.amazonaws.com/bucket/file.jpg
```

Better:

```text
User
  -> CloudFront
  -> private S3 origin with OAC
```

For custom origins:

- Restrict origin access to CloudFront where possible.
- Use secret headers carefully.
- Use security groups to allow CloudFront or ALB paths.
- Keep WAF at edge and origin where needed.

### 22.2 Avoid Caching Private Data Incorrectly

Dangerous:

```text
GET /profile
Authorization: Bearer userA

Cached only by path:
  /profile

UserB requests /profile and receives UserA response.
```

Fix:

- Do not cache private profile responses.
- Or include authorization/user/tenant dimensions in cache key if safe and supported.
- Prefer `Cache-Control: private, no-store` for sensitive data.

### 22.3 Signed URLs and Cookies

Use signed URLs/cookies when content should be served through CDN but only to authorized users.

Examples:

- Paid videos.
- Private documents.
- Temporary downloads.
- Course assets.

### 22.4 WAF at CDN Edge

Attach AWS WAF to CloudFront for:

- SQL injection protection.
- XSS protection.
- Bot filtering.
- Rate-based blocking.
- IP reputation filtering.
- Geo-based restrictions when appropriate.

---

## 23. Performance Considerations

Key metrics:

- Cache hit ratio.
- Origin latency.
- Edge latency.
- Total bytes served from edge.
- Origin request count.
- 4xx and 5xx errors.
- Time to first byte.
- Invalidation frequency.

Improve cache hit ratio by:

- Using long TTL for versioned assets.
- Avoiding unnecessary headers in cache key.
- Avoiding all query parameters when only some matter.
- Normalizing URLs.
- Using Origin Shield for global workloads.
- Avoiding cookies in cache key unless required.

Bad cache behavior:

```text
Forward all headers, all cookies, all query strings.
```

This creates many cache variants and often destroys cache hit ratio.

---

## 24. Common Mistakes

| Mistake | Why It Hurts | Better Approach |
|---------|--------------|-----------------|
| Treating CDN as only static file hosting | Misses API and dynamic acceleration opportunities | Use behaviors by path |
| Forwarding all headers/cookies/query strings | Low cache hit ratio | Allowlist only required dimensions |
| Caching user-specific data by path only | Data leak risk | Do not cache or scope cache key correctly |
| Making S3 origin public | Users bypass CDN/security controls | Use OAC |
| Frequent invalidation of all assets | Cost and operational churn | Use versioned filenames |
| No WAF on public CDN | Attack traffic reaches origin | Attach AWS WAF to CloudFront |
| Using CDN when TCP/UDP acceleration is needed | CDN is HTTP/content-focused | Use Global Accelerator |
| Not monitoring origin errors | CDN can mask origin stress until cache misses rise | Track origin latency and 5xx |
| Huge TTL for HTML | Users get stale app shell | Short TTL or targeted invalidation |

---

## 25. Decision Guide

| Requirement | AWS Choice |
|-------------|------------|
| Global CDN for static assets | CloudFront |
| CDN in front of S3 static website | CloudFront + private S3 + OAC |
| CDN in front of ALB app | CloudFront + ALB |
| CDN with WAF protection | CloudFront + AWS WAF |
| Lightweight edge rewrite/redirect | CloudFront Functions |
| Complex edge request/origin logic | Lambda@Edge |
| Private paid downloads | CloudFront signed URLs/cookies |
| Video streaming delivery | CloudFront + MediaPackage/MediaStore/S3 |
| TCP/UDP global acceleration | Global Accelerator |
| Faster uploads to S3 | S3 Transfer Acceleration |
| Managed frontend hosting | Amplify Hosting |
| DDoS protection | Shield with CloudFront/WAF |

---

## 26. Interview-Ready Explanation

Use this concise answer:

```text
A CDN, or Content Delivery Network, is a globally distributed edge network that
caches and serves content close to users. It reduces latency, improves throughput,
offloads origin servers, and increases availability. A CDN is best for static
assets, media, downloads, and cacheable API or dynamic responses.

It differs from a WAF because WAF is a security filter that blocks malicious
HTTP traffic such as SQL injection, XSS, bad bots, and abusive request rates.
It differs from a load balancer because a load balancer distributes traffic
across healthy backend targets, while a CDN caches and accelerates content
globally. In many architectures they are combined: CloudFront CDN at the edge,
AWS WAF attached to CloudFront, and ALB behind it for regional load balancing.

In AWS, the primary CDN is Amazon CloudFront. CloudFront supports S3, ALB, EC2,
API Gateway, media services, and custom HTTP origins. AWS also has CDN-adjacent
services: CloudFront Functions and Lambda@Edge for edge compute, AWS WAF for edge
security, Shield for DDoS protection, Global Accelerator for non-caching TCP/UDP
acceleration, S3 Transfer Acceleration for S3 transfers, and Amplify Hosting for
managed frontend hosting backed by CloudFront.
```

---

## 27. Final Mental Model

```text
CDN:
  Cache and serve content near users.

WAF:
  Block malicious or abusive web requests.

Load Balancer:
  Distribute traffic across healthy backends.

API Gateway:
  Govern API access, auth, validation, quotas, and versions.

Global Accelerator:
  Accelerate TCP/UDP traffic with Anycast but no caching.

CloudFront Functions / Lambda@Edge:
  Run logic at the CDN edge.
```

If you remember one thing:

```text
CloudFront is AWS's primary CDN. It is about edge delivery and caching.
WAF is about request security. Load balancers are about backend distribution.
These components solve different problems and are commonly used together.
```

---

## 28. References

- Amazon CloudFront Developer Guide: `https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/`
- CloudFront Functions: `https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/cloudfront-functions.html`
- Lambda@Edge examples: `https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/lambda-examples.html`
- CloudFront Origin Access Control examples: `https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/get-started-cli-tutorial.html`
