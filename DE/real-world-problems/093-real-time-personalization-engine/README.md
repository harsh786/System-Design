# Problem 93: Real-Time Personalization Engine

### Problem 93: Real-Time Personalization Engine
```
ARCH: User actions → Kafka → Flink (user profile update) → Redis → API
FEATURES: Last 10 viewed items, category affinity, time-of-day patterns
SERVING: <10ms lookup of user context for personalization
SCALE: 100M users, 50K requests/sec for personalization decisions
```
