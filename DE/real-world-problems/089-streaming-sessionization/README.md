# Problem 89: Streaming Sessionization

### Problem 89: Streaming Sessionization
```
CHALLENGE: Group click events into sessions without fixed end time
SESSION GAP: 30 minutes of inactivity = new session
ARCH: Click stream → Kafka → Flink (session window with gap) → Sessions table
METRICS: Session duration, pages/session, conversion rate, bounce rate
REAL-TIME: "Active sessions now" counter for live dashboard
```
