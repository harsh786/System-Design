# Top 100 Apache Flink Production Issues at Scale

> Battle-tested solutions for the most common production issues encountered when running Flink at billion-scale. Each issue includes symptoms, root cause, diagnosis steps, fix, and prevention.

---

## Issue Categories

| File | Category | Issues | Severity Distribution |
|------|----------|--------|----------------------|
| [01-state-checkpointing-issues.md](01-state-checkpointing-issues.md) | State & Checkpointing | #1-14 | 🔴 9 Critical, 🟡 5 Warning |
| [02-memory-gc-resource-issues.md](02-memory-gc-resource-issues.md) | Memory, GC & Resources | #15-26 | 🔴 7 Critical, 🟡 5 Warning |
| [03-backpressure-performance-issues.md](03-backpressure-performance-issues.md) | Backpressure & Performance | #27-40 | 🔴 6 Critical, 🟡 8 Warning |
| [04-kafka-integration-issues.md](04-kafka-integration-issues.md) | Kafka Integration | #41-53 | 🔴 5 Critical, 🟡 8 Warning |
| [05-windowing-watermark-issues.md](05-windowing-watermark-issues.md) | Windowing & Watermarks | #54-65 | 🔴 4 Critical, 🟡 8 Warning |
| [06-deployment-kubernetes-issues.md](06-deployment-kubernetes-issues.md) | Deployment & Kubernetes | #66-76 | 🔴 5 Critical, 🟡 6 Warning |
| [07-networking-serialization-issues.md](07-networking-serialization-issues.md) | Networking & Serialization | #77-86 | 🔴 4 Critical, 🟡 6 Warning |
| [08-connector-sink-issues.md](08-connector-sink-issues.md) | Connectors & Sinks | #87-95 | 🔴 3 Critical, 🟡 6 Warning |
| [09-job-lifecycle-recovery-issues.md](09-job-lifecycle-recovery-issues.md) | Job Lifecycle & Recovery | #96-100 | 🔴 3 Critical, 🟡 2 Warning |

---

## Quick Reference: Top 10 Most Frequent Issues

| # | Issue | Frequency | Impact | Category |
|---|-------|-----------|--------|----------|
| 1 | Checkpoint timeout due to backpressure | Very High | Job restart | State |
| 15 | TaskManager OOM killed by Kubernetes | Very High | Job restart | Memory |
| 27 | Backpressure from slow sink | Very High | Latency spike | Performance |
| 41 | Kafka consumer lag growing unbounded | Very High | Data freshness | Kafka |
| 54 | Watermark not advancing (idle partitions) | High | Windows never fire | Windowing |
| 5 | State size growing unbounded (no TTL) | High | Checkpoint failure | State |
| 30 | Hot key causing single subtask overload | High | Uneven processing | Performance |
| 66 | Pod evicted due to resource limits | High | Job restart | K8s |
| 77 | Network buffer exhaustion | Medium-High | Backpressure | Network |
| 87 | Elasticsearch sink bulk failures | Medium-High | Data loss risk | Connectors |

---

## Issue Template Format

Each issue follows this structure:

```
## Issue #N: [Title]
**Severity**: 🔴 Critical / 🟡 Warning / 🟢 Info
**Frequency**: How often seen in production
**Impact**: What happens if unresolved

### Symptoms
- Observable indicators in logs/metrics/UI

### Root Cause
Technical explanation of why this happens

### Diagnosis
Step-by-step commands and queries to confirm

### Fix
Immediate resolution + code/config changes

### Prevention
How to avoid this in the future

### Production Config
Exact configuration values that prevent recurrence
```

---

## Monitoring Queries for Early Detection

```promql
# Top issues can be detected early with these Prometheus queries:

# Issue 1: Checkpoint taking too long
flink_jobmanager_job_lastCheckpointDuration > 300000

# Issue 15: Memory approaching limits
container_memory_working_set_bytes / container_spec_memory_limit_bytes > 0.85

# Issue 27: Backpressure detected
flink_taskmanager_job_task_backPressuredTimeMsPerSecond > 500

# Issue 41: Kafka lag growing
flink_taskmanager_job_task_operator_KafkaSourceReader_KafkaConsumer_records_lag_max > 100000

# Issue 54: Watermark stalled
time() - flink_taskmanager_job_task_operator_currentOutputWatermark/1000 > 300
```

---

## Environment Context

These issues are documented from production environments running:
- Flink 1.16 - 1.19
- Kubernetes 1.25 - 1.29
- Kafka 3.x - 3.7
- State sizes: 100GB - 5TB
- Throughput: 100K - 10M events/sec
- Cluster sizes: 50 - 500 TaskManagers
