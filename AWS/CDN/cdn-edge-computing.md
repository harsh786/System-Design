# CDN Edge Computing & Serverless at Edge

## What is Edge Computing?

Running compute (code) at CDN PoP locations, physically close to users instead of in a centralized data center.

```
Traditional:                          Edge Computing:

User (Mumbai) ──────────────────▶    User (Mumbai) ──▶ Edge (Mumbai PoP)
              500ms to US-East                         5ms to local PoP
              Origin processes                         Code runs HERE
              500ms back                               5ms back
              = 1000ms+                                = 10ms
```

### Edge Compute Platforms Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    Edge Compute Landscape                                 │
├────────────────────┬──────────────┬───────────┬─────────────────────────┤
│ Platform           │ Runtime      │ Cold Start│ Locations               │
├────────────────────┼──────────────┼───────────┼─────────────────────────┤
│ Cloudflare Workers │ V8 Isolates  │ 0ms       │ 300+ PoPs              │
│ Lambda@Edge        │ Node/Python  │ 5-50ms    │ 200+ CloudFront PoPs   │
│ CloudFront Func    │ JS (limited) │ 0ms       │ 200+ PoPs             │
│ Fastly Compute     │ WebAssembly  │ 0ms       │ 90+ PoPs              │
│ Vercel Edge Func   │ V8 Isolates  │ 0ms       │ Cloudflare network     │
│ Deno Deploy        │ V8 Isolates  │ 0ms       │ 35+ regions            │
│ Netlify Edge Func  │ Deno runtime │ 0ms       │ Deno network           │
└────────────────────┴──────────────┴───────────┴─────────────────────────┘
```

---

## Cloudflare Workers

### Architecture: V8 Isolates

```
┌────────────────────────────────────────────────────────────┐
│  Traditional (Lambda):         Cloudflare Workers:          │
│                                                            │
│  ┌──── VM ────┐               ┌──── V8 Engine ────────┐  │
│  │ ┌── OS ──┐ │               │                       │  │
│  │ │Runtime │ │               │  ┌Isolate┐ ┌Isolate┐ │  │
│  │ │  Code  │ │               │  │ Code  │ │ Code  │ │  │
│  │ └────────┘ │               │  └───────┘ └───────┘ │  │
│  └────────────┘               │  ┌Isolate┐ ┌Isolate┐ │  │
│  Cold start: 100ms+           │  │ Code  │ │ Code  │ │  │
│                               │  └───────┘ └───────┘ │  │
│                               └────────────────────────┘  │
│                               Cold start: 0ms             │
│                               Isolation: V8 sandboxing    │
└────────────────────────────────────────────────────────────┘
```

### Workers Example: A/B Testing at Edge

```javascript
export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    
    // Get or assign variant
    let variant = getCookie(request, 'ab_variant');
    if (!variant) {
      variant = Math.random() < 0.5 ? 'A' : 'B';
    }
    
    // Route to different origins based on variant
    const origin = variant === 'A' 
      ? 'https://origin-a.example.com' 
      : 'https://origin-b.example.com';
    
    const response = await fetch(origin + url.pathname, request);
    const newResponse = new Response(response.body, response);
    
    // Set variant cookie
    newResponse.headers.set('Set-Cookie', 
      `ab_variant=${variant}; Path=/; Max-Age=86400`);
    
    return newResponse;
  }
};
```

### Cloudflare Workers Ecosystem

| Service | Purpose | Use Case |
|---------|---------|----------|
| Workers KV | Key-value store (eventually consistent) | Config, feature flags, redirects |
| Durable Objects | Strongly consistent, single-instance | Counters, rate limiting, WebSocket |
| R2 | S3-compatible object storage (no egress fees) | Static assets, backups, logs |
| D1 | SQLite at edge | User data, session storage |
| Queues | Message queue | Async processing |
| Workers AI | ML inference at edge | Content moderation, embeddings |

### Workers KV Example

```javascript
export default {
  async fetch(request, env) {
    // Feature flag check at edge (0ms cold start)
    const featureEnabled = await env.FLAGS_KV.get('new-checkout');
    
    if (featureEnabled === 'true') {
      return fetch('https://origin.example.com/new-checkout', request);
    }
    return fetch('https://origin.example.com/checkout', request);
  }
};
```

### Durable Objects (Strongly Consistent)

```javascript
// Rate limiter using Durable Objects
export class RateLimiter {
  constructor(state, env) {
    this.state = state;
    this.requests = [];
  }

  async fetch(request) {
    const now = Date.now();
    // Remove requests older than 1 minute
    this.requests = this.requests.filter(t => now - t < 60000);
    
    if (this.requests.length >= 100) {
      return new Response('Rate limited', { status: 429 });
    }
    
    this.requests.push(now);
    await this.state.storage.put('requests', this.requests);
    return new Response('OK');
  }
}
```

---

## AWS Lambda@Edge vs CloudFront Functions

### Comparison

```
┌─────────────────────────────────────────────────────────────────────────┐
│              Lambda@Edge vs CloudFront Functions                          │
├──────────────────────┬──────────────────────┬────────────────────────────┤
│                      │ CloudFront Functions  │ Lambda@Edge                │
├──────────────────────┼──────────────────────┼────────────────────────────┤
│ Runtime              │ JavaScript (ES 5.1)  │ Node.js, Python            │
│ Execution location   │ 200+ edge locations  │ 13 regional edge caches    │
│ Max execution time   │ 1ms                  │ 5s (viewer) / 30s (origin) │
│ Max memory           │ 2 MB                 │ 128-3008 MB                │
│ Max package size     │ 10 KB                │ 50 MB                      │
│ Network access       │ ❌ No                │ ✅ Yes                     │
│ File system          │ ❌ No                │ ✅ /tmp (512 MB)           │
│ Pricing             │ $0.10/million         │ $0.60/million + duration   │
│ Triggers            │ Viewer req/res only   │ All 4 event types          │
│ Cold start          │ None                  │ 5-50ms                     │
│ Use case            │ Simple transforms     │ Complex logic, API calls   │
└──────────────────────┴──────────────────────┴────────────────────────────┘
```

### Event Types (CloudFront)

```
                  CloudFront Functions          Lambda@Edge
                        │                          │
User ──▶ Viewer Request ──▶ Cache Check ──▶ Origin Request ──▶ Origin
User ◀── Viewer Response ◀── Cache ◀────── Origin Response ◀── Origin
                        │                          │
            (lightweight,                  (full compute,
             no network)                    network access)
```

### CloudFront Function Example: URL Rewrite

```javascript
function handler(event) {
  var request = event.request;
  var uri = request.uri;
  
  // Add index.html to directory requests
  if (uri.endsWith('/')) {
    request.uri += 'index.html';
  } 
  // Add .html extension if no extension
  else if (!uri.includes('.')) {
    request.uri += '/index.html';
  }
  
  return request;
}
```

### Lambda@Edge Example: Authentication

```javascript
exports.handler = async (event) => {
  const request = event.Records[0].cf.request;
  const headers = request.headers;
  
  const token = headers.authorization?.[0]?.value?.replace('Bearer ', '');
  
  if (!token) {
    return {
      status: '401',
      statusDescription: 'Unauthorized',
      body: JSON.stringify({ error: 'Missing token' }),
    };
  }
  
  try {
    // Validate JWT (can make network calls)
    const decoded = await verifyJWT(token);
    
    // Add user info as headers for origin
    request.headers['x-user-id'] = [{ value: decoded.sub }];
    request.headers['x-user-role'] = [{ value: decoded.role }];
    
    return request;
  } catch (err) {
    return { status: '403', statusDescription: 'Forbidden' };
  }
};
```

---

## Fastly Compute@Edge (WebAssembly)

### Architecture

```
┌──────────────────────────────────────────────────────────┐
│  Fastly Compute@Edge                                      │
│                                                          │
│  Source Code (Rust/Go/JS) → Compile → WebAssembly (.wasm)│
│                                                          │
│  Advantages of Wasm:                                     │
│  • Near-native performance                               │
│  • Language agnostic (Rust, Go, JS, etc.)               │
│  • Strong sandboxing                                     │
│  • 0ms cold start (pre-compiled)                        │
│  • No garbage collection pauses                          │
└──────────────────────────────────────────────────────────┘
```

### Example (Rust)

```rust
use fastly::{Request, Response, Error};

#[fastly::main]
fn main(req: Request) -> Result<Response, Error> {
    // Geo-based routing
    let country = req.get_client_ip_addr()
        .and_then(|ip| fastly::geo::geo_lookup(ip))
        .map(|geo| geo.country_code())
        .unwrap_or("US");
    
    let backend = match country {
        "IN" | "SG" | "JP" => "backend-apac",
        "DE" | "FR" | "GB" => "backend-eu",
        _ => "backend-us",
    };
    
    Ok(req.send(backend)?)
}
```

---

## Vercel Edge Functions / Edge Middleware

### Edge Middleware

```typescript
// middleware.ts (runs on every request at edge)
import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

export function middleware(request: NextRequest) {
  // Geo-based redirect
  const country = request.geo?.country || 'US';
  
  if (country === 'DE' && !request.nextUrl.pathname.startsWith('/de')) {
    return NextResponse.redirect(new URL('/de' + request.nextUrl.pathname, request.url));
  }
  
  // A/B test
  const bucket = request.cookies.get('bucket')?.value || 
    (Math.random() < 0.5 ? 'a' : 'b');
  
  const response = NextResponse.rewrite(
    new URL(`/${bucket}${request.nextUrl.pathname}`, request.url)
  );
  
  response.cookies.set('bucket', bucket);
  return response;
}

export const config = {
  matcher: ['/((?!api|_next/static|favicon.ico).*)'],
};
```

---

## Deno Deploy

```typescript
// Ultra-low latency edge server
Deno.serve(async (req: Request) => {
  const url = new URL(req.url);
  
  // Edge-side API aggregation
  if (url.pathname === '/api/dashboard') {
    const [user, stats, notifications] = await Promise.all([
      fetch('https://api.example.com/user'),
      fetch('https://api.example.com/stats'),
      fetch('https://api.example.com/notifications'),
    ]);
    
    return Response.json({
      user: await user.json(),
      stats: await stats.json(),
      notifications: await notifications.json(),
    });
  }
  
  return new Response('Not found', { status: 404 });
});
```

---

## Edge-Side Use Cases

### 1. JWT Validation at Edge

```javascript
// Validate JWT without hitting origin
import { jwtVerify } from 'jose';

const PUBLIC_KEY = await importKey(env.JWT_PUBLIC_KEY);

export default {
  async fetch(request, env) {
    const auth = request.headers.get('Authorization');
    if (!auth?.startsWith('Bearer ')) {
      return new Response('Unauthorized', { status: 401 });
    }
    
    try {
      const { payload } = await jwtVerify(auth.slice(7), PUBLIC_KEY);
      
      // Forward validated claims to origin
      const newHeaders = new Headers(request.headers);
      newHeaders.set('X-User-ID', payload.sub);
      newHeaders.set('X-User-Roles', payload.roles.join(','));
      
      return fetch(request.url, { headers: newHeaders });
    } catch {
      return new Response('Invalid token', { status: 403 });
    }
  }
};
```

### 2. Image Optimization at Edge

```javascript
// Cloudflare Worker: On-the-fly image transformation
export default {
  async fetch(request) {
    const url = new URL(request.url);
    
    // Parse transform parameters
    const width = url.searchParams.get('w') || 'auto';
    const quality = url.searchParams.get('q') || '80';
    const format = request.headers.get('Accept')?.includes('webp') ? 'webp' : 'jpeg';
    
    // Use Cloudflare Image Resizing
    return fetch(url.origin + url.pathname, {
      cf: {
        image: {
          width: parseInt(width),
          quality: parseInt(quality),
          format: format,
          fit: 'cover',
        }
      }
    });
  }
};
```

### 3. Edge-Side API Aggregation

```javascript
// Reduce multiple API calls to one edge call
export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    
    if (url.pathname === '/api/page-data') {
      // Parallel fetch from multiple microservices
      const [products, reviews, recommendations] = await Promise.all([
        fetch(`${env.PRODUCTS_API}/featured`),
        fetch(`${env.REVIEWS_API}/recent`),
        fetch(`${env.RECO_API}/popular`),
      ]);
      
      return Response.json({
        products: await products.json(),
        reviews: await reviews.json(),
        recommendations: await recommendations.json(),
        // Served from edge - user gets single fast response
        // instead of 3 round trips from browser
      }, {
        headers: { 'Cache-Control': 'public, s-maxage=60' }
      });
    }
  }
};
```

### 4. Feature Flags at Edge

```javascript
export default {
  async fetch(request, env) {
    // Read flags from KV (cached at edge, ~1ms read)
    const flags = JSON.parse(await env.FLAGS.get('feature-flags') || '{}');
    const userId = getCookie(request, 'user_id');
    
    // Evaluate flags
    const userFlags = evaluateFlags(flags, {
      userId,
      country: request.headers.get('CF-IPCountry'),
      percentage: hashToPercentage(userId),
    });
    
    // Pass flags to origin or modify response
    const response = await fetch(request);
    const html = await response.text();
    
    return new Response(
      html.replace('__FLAGS__', JSON.stringify(userFlags)),
      response
    );
  }
};
```

---

## Edge Databases

| Database | Type | Consistency | Latency | Use Case |
|----------|------|-------------|---------|----------|
| Cloudflare D1 | SQLite (replicated) | Read replicas | <5ms reads | User data, sessions |
| Workers KV | Key-Value | Eventually consistent | <10ms | Config, flags, cache |
| Durable Objects | Key-Value | Strong (single instance) | <50ms | Counters, coordination |
| Turso (libSQL) | SQLite (distributed) | Tunable | <10ms | App data |
| PlanetScale | MySQL (Vitess) | Strong | <50ms | Transactional data |
| Neon | Postgres (serverless) | Strong | Variable | Complex queries |
| Upstash Redis | Redis | Eventually consistent | <5ms | Rate limiting, sessions |

---

## Edge-Side Rendering

### SSR at Edge vs Origin

```
Traditional SSR:                    Edge SSR:

User (Mumbai) ──▶ Origin (US)     User (Mumbai) ──▶ Edge (Mumbai)
                  React render                       React render
                  200ms render                       200ms render
                  + 500ms network                    + 5ms network
                  = 700ms TTFB                       = 205ms TTFB
```

### ISR (Incremental Static Regeneration) at Edge

```
┌─────────────────────────────────────────────────────────────┐
│  ISR Flow:                                                   │
│                                                             │
│  1. First request → Generate static HTML → Cache at edge    │
│  2. Subsequent requests → Serve from edge cache (instant)   │
│  3. After revalidation period:                              │
│     → Serve stale (fast)                                    │
│     → Regenerate in background                              │
│     → Update edge cache                                     │
│  4. Next request → Gets fresh version                       │
│                                                             │
│  = Static-site speed + dynamic freshness                    │
└─────────────────────────────────────────────────────────────┘
```

---

## Cold Start Comparison

```
┌─────────────────────────────────────────────────────────────────┐
│  Cold Start Benchmarks (P50)                                     │
│                                                                  │
│  Cloudflare Workers  │ ████ 0ms (isolates pre-warmed)           │
│  CloudFront Func     │ ████ 0ms (lightweight JS)                │
│  Fastly Compute      │ ████ 0ms (pre-compiled Wasm)             │
│  Vercel Edge         │ ████ 0ms (V8 isolates)                   │
│  Deno Deploy         │ ████ 0ms (V8 isolates)                   │
│  Lambda@Edge         │ ████████████████ 40-200ms (container)    │
│  Lambda (regular)    │ ██████████████████████ 100-500ms         │
│                                                                  │
│  Note: Lambda@Edge cold starts are worse than regular Lambda    │
│  because deployment is at edge (less warm capacity per region)  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Performance Comparison & Benchmarks

| Platform | P50 Latency | P99 Latency | Max Duration | Max Memory | Price (per M) |
|----------|-------------|-------------|--------------|------------|---------------|
| CF Workers | 1-3ms | 10ms | 30s (paid) | 128 MB | $0.50 |
| CF Functions | <1ms | 2ms | 1ms | 2 MB | $0.10 |
| Lambda@Edge | 5-50ms | 200ms | 5-30s | 3 GB | $0.60 + compute |
| Fastly Compute | 1-5ms | 15ms | 60s | 128 MB | $0.50 |
| Vercel Edge | 1-3ms | 10ms | 25s | 128 MB | Included in plan |
| Deno Deploy | 1-5ms | 20ms | 50s | 512 MB | $2.00 |

### When to Use Which

```
Simple header/URL manipulation  → CloudFront Functions (cheapest, fastest)
A/B testing, geo-routing        → Cloudflare Workers (0ms cold start, KV)
Auth, API calls needed          → Lambda@Edge (network access, more time)
Performance-critical compute    → Fastly Compute@Edge (Wasm, predictable)
Next.js middleware              → Vercel Edge Functions (native integration)
Full SSR at edge                → Cloudflare Workers + D1 or Deno Deploy
```
