# Problem 87: Multi-Model Data Store Pattern

### Problem 87: Multi-Model Data Store Pattern
```
ARCH: Single logical dataset stored in multiple physical systems:
  → PostgreSQL (transactional queries)
  → Elasticsearch (full-text search)
  → Redis (real-time cache)
  → S3+Iceberg (analytics)
SYNC: CDC from PostgreSQL feeds all other stores
CONSISTENCY: Eventually consistent (1-5 second lag acceptable)
```
