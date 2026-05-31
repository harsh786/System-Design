# Problem 8: Social Media Feed Generation

### Problem 8: Social Media Feed Generation
```
SCALE: 500M users, 10K new posts/sec
ARCH: Fan-out on write (Kafka) + Fan-out on read (hybrid)
WHY HYBRID: Celebrities fan-out on read (too many followers), others on write
STORAGE: Redis (feed cache) + Cassandra (persistent timeline)
```
