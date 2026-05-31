# CDN Security

## CDN as First Line of Defense

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    Defense-in-Depth with CDN                              │
│                                                                         │
│  Internet Traffic (legitimate + malicious)                               │
│         │                                                               │
│         ▼                                                               │
│  ┌─────────────────────────────────────────┐                           │
│  │  Layer 1: CDN Edge (DDoS Absorption)    │  ← Absorbs volumetric    │
│  │  • Anycast distributes across PoPs      │     attacks across        │
│  │  • Rate limiting                         │     300+ PoPs            │
│  │  • IP reputation filtering              │                           │
│  └────────────────────┬────────────────────┘                           │
│                       ▼                                                 │
│  ┌─────────────────────────────────────────┐                           │
│  │  Layer 2: WAF (Application Firewall)    │  ← Blocks L7 attacks     │
│  │  • OWASP Top 10 rules                   │     (SQLi, XSS, etc.)   │
│  │  • Custom rules                         │                           │
│  │  • Bot detection                        │                           │
│  └────────────────────┬────────────────────┘                           │
│                       ▼                                                 │
│  ┌─────────────────────────────────────────┐                           │
│  │  Layer 3: Origin Protection             │  ← Only clean traffic    │
│  │  • Origin cloaking (hidden IP)          │     reaches origin       │
│  │  • Authenticated origin pulls           │                           │
│  │  • IP allowlisting                      │                           │
│  └────────────────────┬────────────────────┘                           │
│                       ▼                                                 │
│  ┌─────────────────────────────────────────┐                           │
│  │  Origin Server                          │  ← Sees only clean,      │
│  │  • Application firewall                 │     validated requests    │
│  │  • Input validation                     │                           │
│  └─────────────────────────────────────────┘                           │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## DDoS Protection at CDN Layer

### Attack Layers

| Layer | Attack Type | Example | CDN Mitigation |
|-------|-------------|---------|----------------|
| L3 | Volumetric | UDP flood, ICMP flood | Anycast absorption, blackholing |
| L4 | Protocol | SYN flood, ACK flood | SYN cookies, connection limits |
| L7 | Application | HTTP flood, slowloris | Rate limiting, challenge pages |

### How CDN Absorbs DDoS

```
Attack: 500 Gbps UDP Flood targeting 1.2.3.4

Without CDN:                        With CDN (Anycast):
                                    
500 Gbps ──▶ Single Server         500 Gbps distributed across 300 PoPs
             💀 (overwhelmed)       
                                    PoP 1: 1.6 Gbps (easily handled)
                                    PoP 2: 1.6 Gbps (easily handled)
                                    PoP 3: 1.6 Gbps (easily handled)
                                    ...
                                    PoP 300: 1.6 Gbps (easily handled)
                                    
                                    Each PoP has 100+ Gbps capacity
                                    Total CDN capacity: 100+ Tbps
```

### L7 DDoS Mitigation

```
┌─────────────────────────────────────────────────────────────┐
│  L7 DDoS Detection & Mitigation                             │
│                                                             │
│  1. Traffic Analysis:                                        │
│     • Request rate per IP                                   │
│     • Request patterns (same URL, sequential)               │
│     • Header anomalies (missing Accept, bad User-Agent)     │
│     • Geographic anomaly (sudden spike from one country)    │
│                                                             │
│  2. Mitigation Actions:                                     │
│     • JavaScript challenge (proves browser execution)       │
│     • CAPTCHA challenge                                     │
│     • Rate limiting (429)                                   │
│     • Block IP/ASN/Country                                  │
│     • Managed challenge (Cloudflare Turnstile)             │
│     • Under-attack mode (challenge all visitors)           │
│                                                             │
│  3. Adaptive Response:                                      │
│     • Normal: pass through                                  │
│     • Elevated: JS challenge for suspicious                 │
│     • Attack: challenge all + aggressive rate limiting     │
└─────────────────────────────────────────────────────────────┘
```

---

## WAF (Web Application Firewall) at Edge

### OWASP Top 10 Protection

```yaml
# Cloudflare WAF Managed Rules
waf_rules:
  owasp:
    - sql_injection:        BLOCK    # ' OR 1=1 --
    - xss:                  BLOCK    # <script>alert()</script>
    - path_traversal:       BLOCK    # ../../etc/passwd
    - command_injection:    BLOCK    # ; rm -rf /
    - file_inclusion:       BLOCK    # include=http://evil.com
    - xxe:                  BLOCK    # <!ENTITY xxe SYSTEM>
    - ssrf:                 LOG      # requests to internal IPs
    - broken_auth:          CHALLENGE
    
  custom_rules:
    - name: "Block known scanners"
      expression: |
        http.user_agent contains "sqlmap" or
        http.user_agent contains "nikto" or
        http.user_agent contains "nmap"
      action: BLOCK
      
    - name: "API rate limit"
      expression: |
        http.request.uri.path matches "^/api/" and
        rate_limit(key=ip, threshold=100, period=60)
      action: CHALLENGE
```

### WAF vs Traditional Firewall

| Feature | Network Firewall | CDN WAF |
|---------|-----------------|---------|
| Layer | L3/L4 | L7 (HTTP) |
| Inspects | IP/Port | Full HTTP request body |
| Location | Data center perimeter | Edge (300+ locations) |
| Latency impact | Minimal | 1-5ms per request |
| Can block | IPs, ports | URLs, headers, body patterns |
| Encrypted traffic | ❌ (unless TLS terminated) | ✅ (terminates TLS) |

---

## Bot Management and Detection

### Bot Classification

```
┌─────────────────────────────────────────────────────────────┐
│                    Bot Traffic Categories                     │
├───────────────┬──────────────────────────────────────────────┤
│ Good Bots     │ Googlebot, Bingbot, monitoring tools        │
│ Bad Bots      │ Scrapers, credential stuffers, DDoS bots   │
│ Gray Bots     │ SEO tools, price comparison, archivers     │
└───────────────┴──────────────────────────────────────────────┘
```

### Detection Techniques

| Technique | How It Works | Catches |
|-----------|-------------|---------|
| IP reputation | Known bad IP databases | Botnets, proxies |
| JS challenge | Execute JavaScript | Headless browsers |
| Fingerprinting | TLS/HTTP fingerprint (JA3/JA4) | Impersonation bots |
| Behavioral | Mouse movement, timing, patterns | Sophisticated bots |
| CAPTCHA | Human verification | Automated tools |
| Rate analysis | Request patterns | Brute force, scraping |
| Header analysis | Missing/invalid headers | Simple bots |

### Cloudflare Bot Management Example

```javascript
// Edge Worker: Custom bot detection logic
export default {
  async fetch(request, env) {
    const botScore = request.cf?.botManagement?.score || 0;
    // Score: 1 = definitely bot, 99 = definitely human
    
    if (botScore < 30) {
      // Likely bot - serve challenge or block
      return new Response('Blocked', { status: 403 });
    }
    
    if (botScore < 50) {
      // Suspicious - add challenge header
      const response = await fetch(request);
      const newResp = new Response(response.body, response);
      newResp.headers.set('X-Bot-Challenge', 'true');
      return newResp;
    }
    
    // Likely human - pass through
    return fetch(request);
  }
};
```

---

## Rate Limiting at Edge

### Configuration Strategies

```
┌─────────────────────────────────────────────────────────────────┐
│                    Rate Limiting Strategies                       │
├────────────────────┬────────────────────────────────────────────┤
│ Key                │ Examples                                    │
├────────────────────┼────────────────────────────────────────────┤
│ IP address         │ 100 req/min per IP                        │
│ IP + Path          │ 10 req/min per IP to /api/login           │
│ API key            │ 1000 req/min per key                      │
│ User ID (cookie)   │ 50 req/min per user                      │
│ Country            │ 500 req/min from high-risk countries      │
│ ASN                │ Rate limit entire ISP if abusive          │
└────────────────────┴────────────────────────────────────────────┘
```

### CloudFront + WAF Rate Limiting

```json
{
  "Name": "APIRateLimit",
  "Priority": 1,
  "Action": { "Block": {} },
  "Statement": {
    "RateBasedStatement": {
      "Limit": 2000,
      "AggregateKeyType": "IP",
      "ScopeDownStatement": {
        "ByteMatchStatement": {
          "SearchString": "/api/",
          "FieldToMatch": { "UriPath": {} },
          "PositionalConstraint": "STARTS_WITH",
          "TextTransformations": [{ "Priority": 0, "Type": "NONE" }]
        }
      }
    }
  },
  "VisibilityConfig": {
    "SampledRequestsEnabled": true,
    "CloudWatchMetricsEnabled": true,
    "MetricName": "APIRateLimit"
  }
}
```

### Sliding Window vs Fixed Window

```
Fixed Window:                        Sliding Window:
┌──────┬──────┐                     ┌──────────────┐
│ Min 1│ Min 2│                     │   Rolling    │
│100req│100req│                     │   window     │
└──────┴──────┘                     └──────────────┘

Problem: 100 at :59 + 100 at :01    No spike: always max 100 in ANY
= 200 in 2 seconds!                  60-second window

CDN Implementation:
• Cloudflare: Sliding window (accurate)
• AWS WAF: Fixed window (5-min buckets)
• Fastly: Sliding window via VCL
```

---

## TLS/SSL at Edge

### Certificate Management

```
┌─────────────────────────────────────────────────────────────┐
│  TLS at CDN Edge                                             │
│                                                             │
│  User ──TLS 1.3──▶ CDN Edge (terminates TLS here)          │
│                         │                                    │
│                         │──TLS 1.2/1.3──▶ Origin            │
│                         │  (re-encrypted)                    │
│                                                             │
│  Certificate Types:                                         │
│  • CDN-managed (free): Let's Encrypt / CDN CA              │
│  • Custom certificate: Upload your own                     │
│  • Dedicated IP cert: For legacy SNI-less clients          │
│                                                             │
│  Best Practices:                                            │
│  • TLS 1.3 minimum (disable 1.0/1.1)                      │
│  • HSTS header (Strict-Transport-Security)                 │
│  • OCSP stapling (faster handshake)                        │
│  • Certificate Transparency monitoring                     │
│  • Automatic renewal                                        │
└─────────────────────────────────────────────────────────────┘
```

### HSTS Configuration

```http
# Strict Transport Security
Strict-Transport-Security: max-age=31536000; includeSubDomains; preload

# Tells browsers:
# 1. Always use HTTPS for this domain (1 year)
# 2. Include all subdomains
# 3. Eligible for browser HSTS preload list
```

---

## Origin Protection

### Origin Cloaking

```
┌─────────────────────────────────────────────────────────────┐
│  Origin Cloaking: Hide origin IP from attackers              │
│                                                             │
│  ❌ Without cloaking:                                       │
│  attacker → finds origin IP → attacks directly              │
│                                                             │
│  ✅ With cloaking:                                          │
│  • DNS only shows CDN IPs (CNAME to CDN)                   │
│  • Origin IP never in public DNS                           │
│  • Origin firewall: only allow CDN IP ranges               │
│  • No direct IP access (return 403)                        │
│  • Separate origin hostname (not in public DNS)            │
│                                                             │
│  CloudFront origin IP ranges:                              │
│  aws ip-ranges.json → filter CLOUDFRONT service            │
│                                                             │
│  Cloudflare IP ranges:                                     │
│  https://cloudflare.com/ips/                               │
└─────────────────────────────────────────────────────────────┘
```

### Authenticated Origin Pulls

```
CDN ──────────────────▶ Origin
     mTLS (mutual TLS)
     
CDN presents client certificate to origin.
Origin verifies: "Is this really from my CDN?"

# Nginx origin configuration:
server {
    listen 443 ssl;
    
    ssl_client_certificate /etc/nginx/certs/cloudflare-ca.pem;
    ssl_verify_client on;
    
    # Only requests with valid CDN client cert are accepted
    # Direct requests → 403
}
```

### Origin Protection Checklist

```
□ DNS: CNAME to CDN (never expose origin A record)
□ Firewall: Allow only CDN IP ranges
□ mTLS: Authenticated origin pulls
□ Header validation: Check X-CDN-Secret header
□ Rate limiting at origin (defense in depth)
□ No origin IP in email headers, error pages, etc.
□ Separate domain for origin (not guessable)
□ Block direct IP access on origin
```

---

## Geo-Blocking and Geo-Restrictions

### CloudFront Geo-Restriction

```json
{
  "GeoRestriction": {
    "RestrictionType": "whitelist",
    "Quantity": 3,
    "Items": ["US", "CA", "GB"]
  }
}
```

### Cloudflare Firewall Rules

```
# Block specific countries
(ip.geoip.country in {"CN" "RU" "KP"}) → Block

# Allow specific countries to API
(http.request.uri.path matches "^/api" and 
 not ip.geoip.country in {"US" "CA" "GB" "DE"}) → Block

# Challenge (not block) suspicious regions
(ip.geoip.country in {"NG" "VN"} and 
 http.request.uri.path contains "/checkout") → Challenge
```

---

## Hot-Linking Protection

### Signed URLs

```python
# AWS CloudFront Signed URL
import boto3
from botocore.signers import CloudFrontSigner
from datetime import datetime, timedelta
import rsa

def generate_signed_url(url, key_pair_id, private_key_path, expiry_hours=24):
    expire_date = datetime.utcnow() + timedelta(hours=expiry_hours)
    
    with open(private_key_path, 'rb') as f:
        private_key = rsa.PrivateKey.load_pkcs1(f.read())
    
    def rsa_signer(message):
        return rsa.sign(message, private_key, 'SHA-1')
    
    signer = CloudFrontSigner(key_pair_id, rsa_signer)
    signed_url = signer.generate_presigned_url(
        url, date_less_than=expire_date
    )
    return signed_url

# Usage:
url = generate_signed_url(
    'https://cdn.example.com/premium/video.mp4',
    'K1234567890',
    '/path/to/private_key.pem'
)
# Result: https://cdn.example.com/premium/video.mp4?Expires=...&Signature=...&Key-Pair-Id=...
```

### Signed Cookies (Access to Multiple Files)

```python
# CloudFront Signed Cookies - grant access to path pattern
def generate_signed_cookies(resource_pattern, key_pair_id, private_key):
    policy = {
        "Statement": [{
            "Resource": resource_pattern,  # e.g., "https://cdn.example.com/premium/*"
            "Condition": {
                "DateLessThan": {"AWS:EpochTime": int(expire_time.timestamp())}
            }
        }]
    }
    
    # Returns 3 cookies:
    # CloudFront-Policy
    # CloudFront-Signature  
    # CloudFront-Key-Pair-Id
```

### Token Authentication (Simpler)

```nginx
# Origin validates token at edge (Cloudflare Worker)
# Token = HMAC(path + expiry, secret)

# Generate token:
# token = HMAC-SHA256("/video/123.mp4" + "1700000000", secret_key)
# URL: /video/123.mp4?token=abc123&expires=1700000000
```

---

## AWS Shield Standard vs Advanced

| Feature | Shield Standard | Shield Advanced |
|---------|----------------|-----------------|
| Price | Free (included) | $3,000/month + data |
| L3/L4 DDoS | ✅ Automatic | ✅ Enhanced |
| L7 DDoS | ❌ | ✅ (with WAF) |
| DDoS Response Team | ❌ | ✅ 24/7 DRT |
| Cost protection | ❌ | ✅ (DDoS cost refund) |
| Attack visibility | Basic | Real-time metrics |
| SLA | None | 99.99% |
| Health checks | ❌ | ✅ Route 53 integrated |

---

## Cloudflare DDoS Mitigation Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│  Cloudflare DDoS Architecture                                        │
│                                                                     │
│  Global Network: 300+ cities, 200+ Tbps capacity                   │
│                                                                     │
│  Every server runs:                                                 │
│  ┌────────────────────────────────────────────────────────┐        │
│  │  1. gatebot (global threat detection)                  │        │
│  │     - Analyzes traffic patterns globally               │        │
│  │     - Pushes mitigation rules to all edges             │        │
│  │                                                        │        │
│  │  2. dosd (per-server detection)                        │        │
│  │     - Local traffic analysis                           │        │
│  │     - Instant mitigation (no central dependency)       │        │
│  │                                                        │        │
│  │  3. flowtrackd (TCP state tracking)                    │        │
│  │     - SYN flood protection                             │        │
│  │     - Connection tracking without full state           │        │
│  │                                                        │        │
│  │  4. Magic Transit (L3 protection)                      │        │
│  │     - BGP anycast for network-layer defense            │        │
│  │     - Customer IP ranges announced from CF network     │        │
│  └────────────────────────────────────────────────────────┘        │
│                                                                     │
│  Key: Every server is a DDoS scrubber                              │
│  No traffic trombone to centralized scrubbing center               │
└─────────────────────────────────────────────────────────────────────┘
```

---

## IP Reputation and Threat Intelligence at Edge

### Threat Intelligence Sources

```
┌─────────────────────────────────────────────────────────────┐
│  Edge Threat Intelligence                                    │
│                                                             │
│  Real-time signals:                                         │
│  • IP reputation score (0-100)                              │
│  • ASN reputation (hosting providers, bulletproof hosts)    │
│  • JA3/JA4 TLS fingerprint (known malware signatures)      │
│  • HTTP fingerprint (header order, values)                  │
│  • Behavioral signals (request patterns)                    │
│  • Threat feeds (STIX/TAXII, abuse databases)              │
│                                                             │
│  Decision at edge (< 1ms):                                  │
│  Score > 80  → Pass                                         │
│  Score 50-80 → Challenge (JS/CAPTCHA)                       │
│  Score < 50  → Block or Tarpit                              │
│                                                             │
│  Cloudflare advantage: sees 20%+ of internet traffic       │
│  → massive threat intelligence from aggregate data          │
└─────────────────────────────────────────────────────────────┘
```

### Security Headers Best Practice

```http
# Set at CDN edge for all responses:
Strict-Transport-Security: max-age=31536000; includeSubDomains; preload
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-XSS-Protection: 0
Referrer-Policy: strict-origin-when-cross-origin
Permissions-Policy: camera=(), microphone=(), geolocation=()
Content-Security-Policy: default-src 'self'; script-src 'self' cdn.example.com;
```

---

## Security Configuration Comparison

| Feature | CloudFront + WAF | Cloudflare Pro | Akamai | Fastly |
|---------|-----------------|----------------|--------|--------|
| DDoS L3/L4 | Shield Standard | Included | Prolexic | Included |
| DDoS L7 | WAF rules | Included | Kona | Signal Sciences |
| WAF | AWS WAF ($5/rule) | Included | Kona WAF | Next-Gen WAF |
| Bot Management | Bot Control ($10/M) | $$ add-on | Bot Manager | Signal Sciences |
| Rate Limiting | WAF rate rules | Included (basic) | Rate Control | VCL/Compute |
| Geo-blocking | ✅ | ✅ | ✅ | ✅ |
| Signed URLs | ✅ | ✅ (Workers) | ✅ | ✅ (VCL) |
| mTLS Origin | ❌ (use header) | ✅ | ✅ | ✅ |
| Zero Trust | ❌ | Cloudflare Access | EAA | ❌ |
