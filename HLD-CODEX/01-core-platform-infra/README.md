# Core Platform And Infrastructure

Back to [HLD Problem Bank](../README.md).

Foundational distributed systems: URL shorteners, ID generation, caches, queues, logs, rate limiting, API gateway, DNS, and notification systems.

## Problems

- [001. TinyURL / Bitly URL shortener](001-tinyurl-bitly-url-shortener.md) - key generation, redirects, TTL, abuse prevention, analytics
- [002. Pastebin / GitHub Gist](002-pastebin-github-gist.md) - paste storage, expiration, privacy, syntax rendering, spam control
- [003. A rate limiter for APIs](003-rate-limiter-for-apis.md) - token bucket, sliding window, distributed counters, fairness
- [004. An API gateway](004-api-gateway.md) - routing, auth, quotas, throttling, canary, observability
- [005. A load balancer](005-load-balancer.md) - L4/L7 routing, health checks, consistent hashing, draining
- [006. A CDN and static asset platform](006-cdn-and-static-asset-platform.md) - edge cache, origin shield, invalidation, signed URLs, geo routing
- [007. A distributed cache like Redis/Memcached](007-distributed-cache-like-redis-memcached.md) - sharding, replication, eviction, hot keys, cache stampede
- [008. A distributed queue](008-distributed-queue.md) - visibility timeout, retries, DLQ, priority, ordering
- [009. A Kafka-like event log](009-kafka-like-event-log.md) - partitions, replication, offsets, retention, consumer groups
- [010. A unique ID generator like Snowflake](010-unique-id-generator-like-snowflake.md) - clock drift, sequence, region/worker IDs, monotonicity
