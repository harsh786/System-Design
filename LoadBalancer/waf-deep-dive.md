# WAF Deep Dive: Web Application Firewall and AWS WAF

This note explains what a Web Application Firewall is, how it differs from load balancers and API gateways, and the main AWS WAF options and integrations.

The core idea:

```text
Client
  -> WAF
      -> inspect HTTP request
      -> allow, block, count, CAPTCHA, or challenge
  -> CloudFront / ALB / API Gateway / AppSync / application
```

A WAF mainly answers:

```text
Does this web request look malicious, abusive, malformed, or against policy?
```

It is not mainly a routing component. It is a security control for HTTP and HTTPS traffic.

---

## 1. What Is a WAF?

WAF means **Web Application Firewall**. It protects web applications and APIs by inspecting Layer 7 HTTP traffic.

It can inspect:

- Source IP address.
- HTTP method.
- Host.
- URI path.
- Query parameters.
- Headers.
- Cookies.
- Request body.
- JSON body fields in supported configurations.
- Form fields.
- Request size.
- Rate of requests.
- Known malicious signatures.
- Bot signals.
- IP reputation lists.

It can take actions such as:

- **Allow**: let the request continue.
- **Block**: reject the request.
- **Count**: observe matches without blocking.
- **CAPTCHA**: require human verification.
- **Challenge**: use a silent or interactive browser challenge.
- **Custom response**: return a configured error body or status code.

---

## 2. Why WAF Exists

Traditional firewalls operate mostly at network layers:

```text
Allow source IP 10.0.0.0/8 to destination port 443.
Block source IP 203.0.113.10.
```

But many attacks happen inside valid HTTPS requests:

```http
GET /search?q=' OR 1=1--
Host: api.example.com
```

From a network firewall perspective, this may look like valid HTTPS traffic to port 443. A WAF looks deeper at HTTP semantics and attack patterns.

Common threats WAF helps with:

- SQL injection.
- Cross-site scripting.
- Command injection.
- Local file inclusion.
- Remote file inclusion.
- Path traversal.
- Bad bots.
- Credential stuffing.
- Account takeover attempts.
- Account creation fraud.
- HTTP floods.
- Known malicious IPs.
- Oversized or malformed requests.
- Suspicious headers.
- Scanner traffic.

---

## 3. WAF vs Other Components

| Component | Main Job | Layer | Example Decision |
|-----------|----------|-------|------------------|
| Security Group | Instance or ENI firewall | L3/L4 | Allow TCP 443 from internet |
| NACL | Subnet-level stateless firewall | L3/L4 | Deny IP range at subnet |
| L4 Load Balancer | Distribute TCP/UDP connections | L4 | Send TCP connection to target A |
| L7 Load Balancer | Route HTTP requests | L7 | `/orders` goes to order service |
| API Gateway | Govern API access and lifecycle | L7 | Validate JWT, quota, route version |
| WAF | Detect and stop malicious web requests | L7 | Block SQL injection payload |
| AWS Shield | DDoS protection | L3/L4/L7 | Absorb volumetric attack |
| AWS Network Firewall | VPC network traffic inspection | L3-L7 | Control egress to domains/IPs |

Simple distinction:

```text
Load balancer:
  Where should this traffic go?

API Gateway:
  Is this API caller authenticated, authorized, valid, and within quota?

WAF:
  Does this HTTP request look malicious, abusive, or unsafe?
```

---

## 4. WAF vs L4 Load Balancer

| Aspect | L4 Load Balancer | WAF |
|--------|------------------|-----|
| Layer | Transport | Application |
| Protocol | TCP, UDP, TLS | HTTP/HTTPS |
| Main purpose | Connection distribution | Web request protection |
| Routing basis | IP, port, protocol, flow | Headers, path, query, body, rules |
| SQL injection detection | No | Yes |
| XSS detection | No | Yes |
| Bot detection | No | Yes, depending on rules |
| Rate limiting | Limited or none | Yes, application-aware |
| Best for | Databases, MQTT, Kafka, TCP apps | Websites, APIs, GraphQL, login pages |

An L4 load balancer does not understand HTTP payloads, so it cannot block most application-layer attacks.

---

## 5. WAF vs L7 Load Balancer

| Aspect | L7 Load Balancer | WAF |
|--------|------------------|-----|
| Main purpose | HTTP routing and traffic distribution | HTTP security inspection |
| Routing | Host, path, header, cookie | Usually not primary purpose |
| Security rules | Basic or integrated | Core capability |
| SQLi/XSS protection | Usually via WAF integration | Core use case |
| Bot controls | Usually via WAF/security add-on | Common capability |
| Rate-based blocking | Sometimes | Common capability |
| Request transformation | Common | Limited/security-focused |

They are often used together:

```text
Client
  -> WAF
  -> L7 Load Balancer
  -> Application
```

In AWS, WAF can be directly associated with an ALB, so the separation is logical even if the deployment is integrated.

---

## 6. WAF vs API Gateway

| Aspect | API Gateway | WAF |
|--------|-------------|-----|
| Main purpose | API management and governance | Application-layer attack protection |
| AuthN/AuthZ | Core capability | Limited; can inspect tokens but not full business auth |
| API keys | Core capability | Not primary |
| Quotas and plans | Core capability | Not primary |
| Schema validation | Common | Some request inspection, but security-focused |
| SQLi/XSS blocking | Not primary | Core capability |
| Bot control | Limited or add-on | Common with managed rules |
| Developer portal | Common in API platforms | No |
| API lifecycle | Versioning, publishing, plans | No |

Use both for public APIs:

```text
Client
  -> WAF
      -> block attacks and abusive patterns
  -> API Gateway
      -> authenticate, authorize, rate limit, validate API contract
  -> Backend services
```

The WAF should not replace API authorization. The backend and API Gateway still need proper auth checks.

---

## 7. WAF vs AWS Shield

| Aspect | AWS WAF | AWS Shield |
|--------|---------|------------|
| Main focus | Web request filtering | DDoS protection |
| Layer | Mostly L7 | L3, L4, and L7 |
| Example attack | SQL injection, bad bot, HTTP flood | Volumetric flood, SYN flood, request flood |
| Custom rules | Yes | No, not in the same way |
| Managed DDoS response | No | Shield Advanced provides extra DDoS support |

Typical pairing:

```text
AWS Shield:
  absorbs and mitigates DDoS attacks.

AWS WAF:
  filters application-layer malicious requests.
```

For CloudFront and Route 53, AWS Shield Standard is automatically included. Shield Advanced is used for higher-risk workloads that need stronger DDoS protection, cost protection, and response support.

---

## 8. AWS WAF Core Concepts

### 8.1 Web ACL

A **Web ACL** is the main AWS WAF policy object.

It contains:

- Name and description.
- Scope: `CLOUDFRONT` or `REGIONAL`.
- Default action: allow or block.
- Ordered rules.
- Visibility configuration.
- Optional custom response bodies.

Mental model:

```text
Web ACL
  default action: allow

  rule priority 1:
    block IPs from deny list

  rule priority 2:
    block SQL injection

  rule priority 3:
    challenge suspicious bot traffic

  rule priority 4:
    rate limit /login
```

### 8.2 Rules

A rule defines what to inspect and what action to take.

Rule examples:

- Match source IP in an IP set.
- Match URI path `/admin`.
- Match header `User-Agent`.
- Match query parameter.
- Match request body.
- Detect SQL injection.
- Detect cross-site scripting.
- Rate-limit by IP.
- Use a managed rule group.

### 8.3 Rule Priority

Rules are evaluated in priority order.

Example:

```text
Priority 0: Allow trusted monitoring IPs
Priority 1: Block known bad IPs
Priority 2: Block SQL injection
Priority 3: Rate-limit login path
Default: Allow
```

Priority matters. A broad allow rule before a block rule can accidentally bypass protection.

### 8.4 Rule Actions

Common actions:

- `ALLOW`
- `BLOCK`
- `COUNT`
- `CAPTCHA`
- `CHALLENGE`

`COUNT` is useful when testing a new rule:

```text
Deploy new rule in COUNT mode.
Observe matches and false positives.
Switch to BLOCK after confidence increases.
```

### 8.5 Rule Groups

A rule group is a reusable collection of rules.

Types:

- Custom rule groups created by your team.
- AWS Managed Rules.
- AWS Marketplace managed rule groups.

Rule groups help standardize protection across many applications.

### 8.6 Web ACL Capacity Units

AWS WAF uses capacity units to represent rule complexity. More complex matching consumes more capacity.

Examples of higher-cost logic:

- Body inspection.
- Regex matching.
- Managed rule groups.
- Bot control rules.

Capacity matters because each Web ACL has limits.

---

## 9. AWS WAF Scopes

AWS WAF has two main scopes.

| Scope | Used For | Notes |
|-------|----------|-------|
| `CLOUDFRONT` | CloudFront distributions | Global edge protection; configure through `us-east-1` APIs |
| `REGIONAL` | Regional services | ALB, API Gateway REST API, AppSync, Cognito, App Runner, Amplify, Verified Access |

Use `CLOUDFRONT` when traffic enters through CloudFront.
Use `REGIONAL` when protecting a regional AWS resource directly.

---

## 10. AWS Resources That Can Use AWS WAF

AWS WAFv2 Web ACLs can be associated with:

| AWS Resource | Scope | Common Use |
|--------------|-------|------------|
| CloudFront distribution | `CLOUDFRONT` | Global websites, APIs, edge protection |
| Application Load Balancer | `REGIONAL` | Web apps and microservices behind ALB |
| API Gateway REST API | `REGIONAL` | Public REST APIs |
| AppSync GraphQL API | `REGIONAL` | GraphQL APIs |
| Amazon Cognito user pool | `REGIONAL` | Hosted UI and auth endpoints |
| App Runner service | `REGIONAL` | Managed container web apps |
| Amplify application | `REGIONAL` | Frontend web applications |
| Verified Access instance | `REGIONAL` | Zero-trust application access |

AWS WAF does not attach directly to Network Load Balancer because NLB is Layer 4 and WAF requires HTTP-level visibility.

---

## 11. Different WAF Options in AWS

### 11.1 AWS WAFv2

AWS WAFv2 is the current AWS WAF version and should be used for new workloads.

It provides:

- Web ACLs.
- Custom rules.
- Managed rule groups.
- IP sets.
- Regex pattern sets.
- Rate-based rules.
- CAPTCHA and Challenge actions.
- Logging and metrics.
- Association with CloudFront and regional resources.

Use this by default.

### 11.2 AWS WAF for CloudFront

This protects traffic at AWS edge locations.

```text
Client
  -> CloudFront + AWS WAF
  -> Origin: ALB / S3 / API Gateway / custom origin
```

Best for:

- Public websites.
- Global APIs.
- Static and dynamic web applications.
- Blocking bad traffic before it reaches a region.
- Combining WAF with CDN caching and DDoS edge absorption.

Advantages:

- Edge filtering.
- Lower origin load.
- Good place for global IP reputation and bot controls.
- Works well with Shield and CDN protections.

### 11.3 AWS WAF Regional

This protects regional AWS resources directly.

```text
Client
  -> ALB + AWS WAF Regional
  -> ECS / EKS / EC2 service
```

Common regional integrations:

- ALB.
- API Gateway REST API.
- AppSync.
- Cognito user pools.
- App Runner.
- Amplify.
- Verified Access.

Best for:

- Apps not using CloudFront.
- Internal or regional public apps.
- API Gateway protection.
- ALB-hosted web applications.

### 11.4 AWS Managed Rules for AWS WAF

AWS Managed Rules are prebuilt rule groups maintained by AWS.

Common categories:

- Common web exploit protection.
- Known bad inputs.
- SQL database attacks.
- Linux-specific attacks.
- Unix-specific attacks.
- Windows-specific attacks.
- PHP-specific attacks.
- WordPress-specific attacks.
- IP reputation lists.
- Anonymous IP lists.
- Admin protection.

Benefits:

- Faster setup.
- AWS-maintained updates.
- Good baseline protection.
- Less need to write every signature yourself.

Risk:

- False positives are possible.
- Always test in `COUNT` mode for sensitive applications.

### 11.5 AWS WAF Bot Control

Bot Control is an AWS Managed Rules option for identifying and controlling bot traffic.

It can help with:

- Scrapers.
- Credential stuffing automation.
- Inventory hoarding.
- Fake account creation.
- Automated scanning.
- Non-browser clients pretending to be browsers.

Inspection levels:

- **Common**: broad bot detection.
- **Targeted**: more advanced detection, including machine-learning-based signals when enabled.

Use for:

- Login pages.
- Signup pages.
- Search endpoints.
- Product pages.
- Checkout and inventory-sensitive flows.

### 11.6 AWS WAF Fraud Control

AWS WAF Fraud Control provides specialized managed rule groups.

Common examples:

- Account takeover prevention.
- Account creation fraud prevention.

Useful for:

- Login protection.
- Signup protection.
- Credential stuffing mitigation.
- Fake account creation prevention.

These rule groups may require configuration such as:

- Login path.
- Registration path.
- Username field.
- Password field.
- Payload type: JSON or form-encoded.

### 11.7 AWS Marketplace Managed Rule Groups

Third-party vendors publish managed rule groups through AWS Marketplace.

Use when:

- You want a vendor-specific threat intelligence feed.
- You need compliance-oriented protection.
- You already use a security vendor's WAF rules.
- You need coverage beyond AWS-managed rules.

Tradeoff:

- Additional cost.
- Vendor dependency.
- Still requires false-positive testing.

### 11.8 Custom AWS WAF Rules

Custom rules are written for your application-specific needs.

Examples:

```text
Block all requests to /admin unless source IP is office VPN.
Rate-limit POST /login by source IP.
Block requests missing required header.
Block suspicious User-Agent values.
Challenge traffic from risky countries.
Block oversized JSON bodies.
```

Custom rules are essential because managed rules do not know every application-specific policy.

### 11.9 AWS Firewall Manager for WAF

AWS Firewall Manager is not a separate WAF engine. It centrally manages WAF policies across AWS accounts and resources.

Use it when:

- You have many AWS accounts.
- You use AWS Organizations.
- You want central security team governance.
- You need consistent WAF policies on many ALBs, CloudFront distributions, or API Gateways.

Example:

```text
Security account
  -> Firewall Manager policy
  -> apply baseline AWS WAF Web ACL to all production ALBs
  -> enforce managed rule groups
  -> report non-compliant resources
```

### 11.10 AWS WAF Classic

AWS WAF Classic is the older version of AWS WAF.

For new workloads:

```text
Use AWS WAFv2.
Avoid WAF Classic unless maintaining an existing legacy setup.
```

---

## 12. Common AWS WAF Architectures

### 12.1 Website Behind CloudFront

```text
Browser
  -> Route 53
  -> CloudFront + AWS WAF
  -> ALB / S3 / custom origin
```

Best for:

- Public websites.
- Global users.
- Static and dynamic content.
- Edge caching.
- Early attack filtering.

### 12.2 API Behind API Gateway

```text
Client
  -> API Gateway REST API + AWS WAF
  -> Lambda / ECS / internal services
```

Best for:

- Public REST APIs.
- API auth and throttling.
- WAF protection on API endpoints.

Note:

AWS WAF protects API Gateway REST APIs. For other API Gateway types, check current AWS service support before designing around WAF attachment.

### 12.3 Application Behind ALB

```text
Client
  -> ALB + AWS WAF
  -> Target group
  -> ECS / EKS / EC2 app
```

Best for:

- Web apps.
- Microservices exposed through ALB.
- Regional traffic entry.

### 12.4 GraphQL with AppSync

```text
Client
  -> AppSync GraphQL API + AWS WAF
  -> Data sources
      -> Lambda
      -> DynamoDB
      -> OpenSearch
```

Best for:

- GraphQL APIs.
- Protecting expensive query endpoints.
- Rate limiting abusive clients.

### 12.5 Cognito Hosted UI Protection

```text
User
  -> Cognito hosted UI + AWS WAF
  -> authentication flow
```

Best for:

- Login abuse reduction.
- Bot control.
- Account takeover protection.

---

## 13. WAF Rule Examples

### 13.1 Block Known Bad IPs

```text
If source IP in bad_ip_set:
  BLOCK
```

Use for:

- Known attackers.
- Threat intelligence feeds.
- Temporary incident response blocks.

### 13.2 Allow Trusted Internal IPs

```text
If source IP in corporate_vpn_ip_set:
  ALLOW
```

Use carefully. Broad allow rules can bypass later security rules.

### 13.3 Protect Admin Paths

```text
If URI starts with /admin
AND source IP not in office_vpn_ip_set:
  BLOCK
```

Good for:

- Admin consoles.
- Internal dashboards accidentally exposed through public entry.

### 13.4 Rate-Limit Login

```text
If path == /login
AND source IP exceeds threshold:
  BLOCK or CAPTCHA
```

Good for:

- Credential stuffing reduction.
- Brute-force login control.

### 13.5 Count Before Blocking

```text
If request matches new managed rule:
  COUNT
```

After observation:

```text
If false positives are low:
  switch to BLOCK
```

---

## 14. Rate-Based Rules

Rate-based rules block or count clients that exceed a request threshold.

Examples:

```text
Block IPs making more than 2,000 requests in 5 minutes.
Challenge clients making too many requests to /login.
Block clients scraping /products too aggressively.
```

Possible aggregation keys depend on configuration and service capabilities, but common designs include:

- Source IP.
- Forwarded IP.
- IP plus path.
- IP plus header.
- Tenant or API key when available through custom keys.

Rate limits are useful, but they are not a complete DDoS strategy. Use Shield, CloudFront, scalable origins, and application-level backpressure too.

---

## 15. CAPTCHA and Challenge

### CAPTCHA

CAPTCHA asks the user to prove they are human.

Best for:

- Suspicious login attempts.
- Signup abuse.
- Scraping prevention.

Tradeoff:

- Adds user friction.
- Can hurt accessibility and conversion.

### Challenge

Challenge can validate browser-like behavior with less visible friction.

Best for:

- Suspicious automated traffic.
- Bot filtering before CAPTCHA.
- Reducing false positives.

---

## 16. Logging and Monitoring

AWS WAF observability should include:

- Allowed request count.
- Blocked request count.
- Counted request count.
- CAPTCHA and Challenge outcomes.
- Top matched rules.
- Top source IPs.
- Top countries.
- Top paths.
- False positives.
- Rate-based rule triggers.
- Bot control matches.

Useful destinations and integrations:

- CloudWatch metrics.
- AWS WAF sampled requests.
- AWS WAF logs.
- Amazon S3.
- CloudWatch Logs.
- Kinesis Data Firehose.
- SIEM tooling.

Log carefully:

- Do not expose tokens.
- Do not log passwords.
- Redact sensitive headers and fields where needed.
- Protect WAF logs because they can contain request details.

---

## 17. False Positives

A false positive happens when WAF blocks a legitimate request.

Common causes:

- Search queries that look like SQL.
- Developer tools sending unusual headers.
- Large JSON bodies.
- API clients with non-browser user agents.
- GraphQL queries that look suspicious.
- Encoded payloads.
- File uploads.
- Rich text input containing HTML or scripts.

Safe rollout pattern:

```text
1. Add managed rule group in COUNT mode.
2. Monitor matches.
3. Identify legitimate traffic that matches rules.
4. Add exclusions or overrides.
5. Enable BLOCK for high-confidence rules.
6. Keep monitoring after deployment.
```

---

## 18. Best Practices

- Put WAF as close to the edge as possible for internet-facing applications.
- Use CloudFront plus WAF for public global apps when possible.
- Start with AWS Managed Rules as a baseline.
- Add custom rules for application-specific behavior.
- Use `COUNT` mode before blocking with new rules.
- Add rate-based rules for login, signup, search, and expensive endpoints.
- Use Bot Control for bot-sensitive flows.
- Use Fraud Control for login and account creation abuse.
- Keep API Gateway and backend authorization even when WAF is present.
- Sanitize and validate input in the application too.
- Monitor false positives continuously.
- Use Firewall Manager for multi-account governance.
- Combine WAF with Shield for DDoS resilience.

---

## 19. Common Mistakes

| Mistake | Why It Hurts | Better Approach |
|---------|--------------|-----------------|
| Treating WAF as complete security | WAF cannot fix broken auth or insecure code | Use WAF plus secure app design |
| Blocking managed rules immediately | Can cause false positives | Start in `COUNT` mode |
| No rate limits on login | Credential stuffing becomes easier | Add rate-based rules and fraud controls |
| WAF only on ALB while CloudFront is public | Attack traffic reaches regional edge first | Attach WAF at CloudFront if CloudFront is entry |
| Trusting headers from clients | Clients can spoof forwarded headers | Sanitize at trusted edge |
| No logs | Cannot investigate blocks or attacks | Enable metrics and WAF logs |
| Too many custom regex rules | Hard to maintain and can be costly | Prefer managed rules and simple custom rules |
| Using WAF instead of API auth | WAF does not understand business permissions | Keep API Gateway/service auth |

---

## 20. Decision Guide

| Requirement | Recommended AWS Option |
|-------------|------------------------|
| Protect global public website | CloudFront + AWS WAF |
| Protect ALB-hosted application | AWS WAF Regional on ALB |
| Protect REST API | AWS WAF on API Gateway REST API |
| Protect GraphQL API | AWS WAF on AppSync |
| Protect login/signup from bots | AWS WAF Bot Control and Fraud Control |
| Apply WAF across many accounts | AWS Firewall Manager |
| Need third-party rule intelligence | AWS Marketplace managed rule group |
| Need DDoS protection | AWS Shield plus WAF |
| Need VPC network egress firewall | AWS Network Firewall |
| Need TCP/UDP load balancing | NLB, not WAF |

---

## 21. Interview-Ready Explanation

Use this concise answer:

```text
A WAF, or Web Application Firewall, protects HTTP and HTTPS applications by
inspecting Layer 7 request data such as paths, headers, query strings, cookies,
and bodies. It blocks or challenges malicious requests like SQL injection, XSS,
bad bots, credential stuffing, suspicious IPs, and abusive request rates.

It is different from a load balancer because a load balancer mainly distributes
traffic to healthy backends. It is different from an API Gateway because an API
Gateway mainly handles API governance such as authentication, authorization,
quotas, API keys, validation, and versioning. WAF is security inspection;
API Gateway is API control; load balancer is traffic distribution.

In AWS, the current service is AWS WAFv2. It uses Web ACLs containing ordered
rules and can be associated with CloudFront, ALB, API Gateway REST API, AppSync,
Cognito user pools, App Runner, Amplify, and Verified Access. AWS also provides
managed rule groups, Bot Control, Fraud Control, Marketplace managed rules,
and Firewall Manager for central multi-account WAF governance.
```

---

## 22. Final Mental Model

```text
Security Group / NACL:
  Should this IP/port/protocol be allowed?

L4 Load Balancer:
  Which backend gets this TCP/UDP connection?

L7 Load Balancer:
  Which backend gets this HTTP request?

API Gateway:
  Is this API caller valid, authorized, within quota, and using the right contract?

WAF:
  Is this HTTP request malicious, abusive, automated, malformed, or suspicious?

Shield:
  Is this traffic part of a DDoS attack?

Firewall Manager:
  Are WAF policies consistently applied across accounts and resources?
```

If you remember one thing:

```text
WAF is not a replacement for secure application code, API authorization, or load
balancing. It is an application-layer security filter that reduces malicious and
abusive traffic before it reaches your application.
```

---

## 23. References

- AWS WAFv2 API Reference: `https://docs.aws.amazon.com/aws-sdk-php/v3/api/api-wafv2-2019-07-29.html`
- AWS CLI CloudFront and WAF examples: `https://docs.aws.amazon.com/cli/latest/userguide/bash_cloudfront_code_examples.html`
