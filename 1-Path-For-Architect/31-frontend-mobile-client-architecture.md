# Frontend, Mobile, and Client Architecture

Architect roles often own complete user journeys. Even backend-heavy architects should understand how client architecture affects latency, reliability, release safety, API design, and product quality.

## Architect-Level Outcome

You should be able to design end-to-end systems where web, mobile, edge, APIs, and backend services work together with strong performance, compatibility, security, and rollout control.

## Core Areas

| Area | Architect-Level Outcome |
| --- | --- |
| Web performance | Explain Core Web Vitals, caching, CDN, hydration, bundle size, and rendering trade-offs. |
| Mobile architecture | Design offline sync, version compatibility, push, local storage, and staged rollout. |
| API composition | Choose REST, GraphQL, BFF, gateway aggregation, and client-driven composition. |
| Release strategy | Use feature flags, phased rollout, app version gates, and backward-compatible APIs. |
| Accessibility and i18n | Design inclusive, global-ready product experiences. |
| Client observability | Track user journey performance, crashes, errors, and real-user metrics. |

## Client Architecture Patterns

### Backend for Frontend

```text
Web App -> Web BFF -> Core Services
Mobile App -> Mobile BFF -> Core Services
Partner API -> Partner Gateway -> Core Services
```

Use when different clients have different payload, auth, latency, or aggregation needs.

Benefits:

- Reduces client complexity.
- Avoids chatty client calls.
- Encapsulates client-specific composition.
- Lets mobile and web evolve independently.

Risks:

- Duplicated logic across BFFs.
- BFFs become mini-monoliths.
- Ownership confusion.

### GraphQL Gateway

Use when clients need flexible query composition across many backend domains.

Design points:

- Schema ownership by domain.
- Query complexity limits.
- Depth limits.
- Persisted queries for production clients.
- Resolver batching to avoid N+1 calls.
- Authorization at field and object level.
- Caching strategy for entity and query results.

### Edge Rendering and CDN

Use for:

- Public content.
- Low-latency global reads.
- SEO-sensitive pages.
- Personalization with careful cache keys.

Risks:

- Cache invalidation.
- User-specific data leakage.
- Complex debugging.
- Split logic across edge and origin.

## Web Performance Deep Dive

### Key Metrics

| Metric | Meaning |
| --- | --- |
| LCP | Largest content paint; main loading experience. |
| INP | Interaction responsiveness. |
| CLS | Visual layout stability. |
| TTFB | Server and network response time. |
| FCP | First content visible. |

### Optimization Levers

- CDN and edge caching.
- SSR, SSG, ISR, or client rendering based on content type.
- Code splitting.
- Image optimization.
- Font loading strategy.
- Critical CSS.
- Reducing JavaScript execution.
- API aggregation.
- HTTP caching headers.
- Prefetching and preloading.

## Mobile Architecture

### Offline Sync

```text
Local Store -> Sync Queue -> API -> Conflict Resolver -> Server Source of Truth
```

Design points:

- Local-first reads for critical UX.
- Operation log for offline writes.
- Idempotency keys.
- Conflict resolution strategy.
- Retry with backoff.
- Sync status visible to user when needed.
- Data encryption at rest.

### App Version Compatibility

Backend APIs must support old app versions because mobile upgrades are not immediate.

Rules:

- Never remove fields until app adoption reaches safe threshold.
- Add fields as optional first.
- Use version gates for breaking behavior.
- Support forced upgrade only for security or severe correctness risk.
- Track API usage by app version.

### Push Notifications

Design points:

- Device token lifecycle.
- User preferences.
- Quiet hours.
- Priority and collapse keys.
- Provider feedback handling.
- Delivery attempts and audit.
- Abuse and rate limits.

## Client Security

- OAuth 2.0 Authorization Code with PKCE for mobile and SPA.
- Secure token storage.
- Certificate pinning only with operational maturity.
- No secrets in client apps.
- API authorization must be server-side.
- Protect against XSS, CSRF, clickjacking, malicious deep links.
- Validate all client input server-side.

## Client Observability

Track:

- Real-user performance.
- JavaScript errors.
- Mobile crashes.
- API error rate by client version.
- Screen load time.
- Funnel drop-off.
- Offline sync failures.
- Push delivery/open rates.
- Feature flag exposure.

## Interview Questions

1. Design a mobile app that works offline and syncs later.
2. When do you choose BFF vs GraphQL vs direct service APIs?
3. How do you protect backend compatibility for old mobile app versions?
4. How do you improve p95 page load time globally?
5. How do you prevent CDN cache leakage of user data?
6. How do you roll out a risky mobile feature?
7. How do you observe client-side failures in production?

