# Problem 64: Real-Time ETL for Compliance (GDPR/CCPA)

### Problem 64: Real-Time ETL for Compliance (GDPR/CCPA)
```
REQUIREMENTS: Delete user data within 30 days of request
CHALLENGE: Data spread across 50+ tables, 3 storage systems
ARCH: Deletion request → Kafka → Flink (find all user data) → Execute deletes
PATTERN: Crypto-shredding (encrypt per-user key, delete key = data gone)
ADVANTAGE: Don't need to find every copy; just destroy the encryption key
```
