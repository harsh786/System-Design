# Problem 55: Change Data Capture for Microservices

### Problem 55: Change Data Capture for Microservices
```
PATTERN: Outbox Pattern + Debezium
Each service writes events to outbox table → CDC captures → Kafka distributes
WHY: Ensures DB write + event publish are atomic (same transaction)
SCALE: 500 microservices, each publishing domain events
```
