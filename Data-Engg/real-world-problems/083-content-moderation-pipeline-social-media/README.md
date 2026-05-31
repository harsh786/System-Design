# Problem 83: Content Moderation Pipeline (Social Media)

### Problem 83: Content Moderation Pipeline (Social Media)
```
ARCH: Upload → Kafka → ML models (image/text/video) → Decision → Store
MODELS: NSFW detection, hate speech NLP, deepfake detection
LATENCY: <30 seconds (content shouldn't be visible until moderated)
SCALE: 500M posts/day, 99.9% automated, 0.1% human review queue
```
