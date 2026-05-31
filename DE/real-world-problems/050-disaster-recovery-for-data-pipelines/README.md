# Problem 50: Disaster Recovery for Data Pipelines

### Problem 50: Disaster Recovery for Data Pipelines
```
ARCH: Multi-AZ primary + cross-region standby + S3 cross-region replication
RPO: <1 hour (data loss tolerance)
RTO: <4 hours (recovery time)
STRATEGY: Active-passive with automated failover
TESTING: Monthly DR drills (actually fail over and back)
```
