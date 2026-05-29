# CloudWatch & AWS Monitoring - Complete Guide

---

## 1. CloudWatch Overview
- **What:** Monitoring and observability service for AWS resources and applications
- **Pillars:** Metrics, Logs, Alarms, Dashboards, Events, Insights, Traces (X-Ray)
- **Scope:** Per-region (but can create cross-region dashboards)
- **Pricing:** Pay per metric, alarm, log ingested, dashboard, API call

---

## 2. CloudWatch Metrics

### Built-in Metrics (free tier)
- **EC2:** CPUUtilization, NetworkIn/Out, DiskReadOps, StatusCheckFailed (5-min interval)
- **EBS:** VolumeReadOps, VolumeWriteBytes, VolumeQueueLength
- **RDS:** CPUUtilization, DatabaseConnections, FreeableMemory, ReadIOPS, ReplicaLag
- **Lambda:** Invocations, Errors, Duration, Throttles, ConcurrentExecutions
- **ALB:** RequestCount, TargetResponseTime, HTTPCode_Target_5XX, HealthyHostCount
- **SQS:** ApproximateNumberOfMessagesVisible, ApproximateAgeOfOldestMessage
- **DynamoDB:** ConsumedReadCapacityUnits, ThrottledRequests, SuccessfulRequestLatency

### Detailed Monitoring (paid)
- EC2: 1-minute intervals (vs default 5-min). Enable per instance ($2.10/month/instance)
- Enhanced Monitoring: OS-level metrics (memory, disk, swap, processes). Via CloudWatch Agent

### Custom Metrics
- Publish your own metrics via `PutMetricData` API
- **Resolution:** Standard (1 minute) or High Resolution (1 second)
- **Dimensions:** Up to 30 per metric (filter/group by instance, service, etc.)
- **Use cases:** Business metrics (orders/minute), application metrics (cache hit rate), queue depth
```python
import boto3
cloudwatch = boto3.client('cloudwatch')
cloudwatch.put_metric_data(
    Namespace='MyApp',
    MetricData=[{
        'MetricName': 'OrdersProcessed',
        'Dimensions': [{'Name': 'Environment', 'Value': 'Production'}],
        'Value': 42,
        'Unit': 'Count',
        'Timestamp': datetime.utcnow()
    }]
)
```

### Metric Math
- Combine metrics with expressions: `METRICS("m1") / METRICS("m2") * 100`
- Functions: SUM, AVG, MIN, MAX, STDDEV, PERCENTILE, FILL, IF, RATE, PERIOD, ANOMALY_DETECTION_BAND
- **Use case:** Error rate = Errors / Invocations × 100, Latency P99, Cost per request

### CloudWatch Embedded Metric Format (EMF)
- Publish custom metrics from Lambda/containers without PutMetricData API calls
- Write structured JSON to stdout → CloudWatch extracts metrics automatically
- **Benefits:** No API overhead, lower cost, metrics + logs in one write
```json
{
  "_aws": {
    "Timestamp": 1234567890,
    "CloudWatchMetrics": [{
      "Namespace": "MyApp",
      "Dimensions": [["Service", "Environment"]],
      "Metrics": [{"Name": "ProcessingTime", "Unit": "Milliseconds"}]
    }]
  },
  "Service": "OrderService",
  "Environment": "Production",
  "ProcessingTime": 125
}
```

---

## 3. CloudWatch Logs

### Architecture
```
Log Group: /aws/lambda/my-function (retention, encryption, subscription)
  └── Log Stream: 2024/01/15/[$LATEST]abc123 (one per instance/container)
       └── Log Events: timestamp + message (individual lines)
```

### Log Sources
| Source | Log Group Pattern | Setup |
|--------|------------------|-------|
| Lambda | /aws/lambda/{function-name} | Automatic (execution role needs permissions) |
| ECS/Fargate | /ecs/{task-def} | awslogs log driver in task def |
| EC2 | Custom | CloudWatch Agent installed |
| API Gateway | /aws/apigateway/{api-id} | Enable access logging |
| VPC Flow Logs | /aws/vpc/flowlogs | Enable on VPC/subnet/ENI |
| RDS | /aws/rds/instance/{id}/{log-type} | Enable in parameter group |
| EKS | /aws/eks/{cluster}/cluster | Enable control plane logging |
| CloudTrail | Custom | Create trail → CloudWatch Logs |
| Route 53 | /aws/route53/{hosted-zone-id} | Enable query logging |

### CloudWatch Agent
- Install on EC2/on-prem servers for:
  - System metrics: Memory, disk, swap, netstat (not available by default)
  - Custom logs: Application log files → CloudWatch Logs
  - StatsD / collectd: Receive custom metrics from applications
- Configuration: JSON config file (wizard available)
- SSM Parameter Store: Store and distribute agent configs

### Log Insights (Query Language)
```
# Find 5XX errors in last hour
fields @timestamp, @message
| filter @message like /5\d{2}/
| sort @timestamp desc
| limit 20

# Top 10 most expensive Lambda invocations
fields @timestamp, @billedDuration, @memorySize
| stats max(@billedDuration) as maxDuration by bin(5m)
| sort maxDuration desc
| limit 10

# Error rate per service
fields @timestamp, @message
| filter @message like /ERROR/
| stats count() as errorCount by bin(1h)

# P50, P90, P99 latency
fields @timestamp, @duration
| stats pct(@duration, 50) as p50, pct(@duration, 90) as p90, pct(@duration, 99) as p99 by bin(5m)
```

### Subscription Filters
- Stream logs in real-time to:
  - Lambda (process/transform)
  - Kinesis Data Streams (real-time analytics)
  - Kinesis Data Firehose (archive to S3, Elasticsearch)
  - Another account's destination (cross-account log aggregation)
- **Pattern:** Filter which log events to stream (e.g., only ERROR lines)
- **Limit:** 2 subscription filters per log group

### Log Retention & Cost
- **Retention:** Never expire (default), or 1 day to 10 years
- **Cost:** $0.50/GB ingested, $0.03/GB stored/month
- **Optimization:**
  - Set retention (don't keep forever)
  - Export to S3 for long-term (much cheaper storage)
  - Use log levels (don't log DEBUG in production)
  - Structured logging (easier to query, less noise)

---

## 4. CloudWatch Alarms

### Alarm States
- **OK:** Metric within threshold
- **ALARM:** Metric breached threshold
- **INSUFFICIENT_DATA:** Not enough data points to evaluate

### Alarm Types
| Type | Description |
|------|-------------|
| Metric Alarm | Based on single metric or math expression |
| Composite Alarm | Combines multiple alarms with AND/OR logic |
| Anomaly Detection | ML-based band, alarms when metric goes outside expected range |

### Configuration
```yaml
MetricName: CPUUtilization
Namespace: AWS/EC2
Statistic: Average
Period: 300 (5 minutes)
EvaluationPeriods: 3
DatapointsToAlarm: 2 (2 of 3 periods must breach)
Threshold: 80
ComparisonOperator: GreaterThanThreshold
TreatMissingData: missing | notBreaching | breaching | ignore
```

### Alarm Actions
| Target | Use Case |
|--------|----------|
| SNS Topic | Email/SMS/PagerDuty notification |
| Auto Scaling | Scale EC2/ECS |
| EC2 Actions | Stop, terminate, reboot, recover instance |
| Systems Manager | OpsItem, Incident Manager |
| Lambda (via SNS) | Custom remediation |

### Composite Alarms
```
ALARM if (High CPU AND High Memory AND High Disk)
  → Reduces alarm noise (only alert if multiple metrics indicate real problem)
  
ALARM if (Service A unhealthy OR Service B unhealthy)  
  → Alert if any critical dependency is down
```

### Anomaly Detection
- ML model learns metric patterns (hourly, daily, weekly seasonality)
- Creates expected band (upper/lower bounds)
- Alarm triggers when metric outside band
- **Use cases:** Request count drops unexpectedly, latency spike, unusual error count
- Training period: 2 weeks for good baseline

---

## 5. CloudWatch Dashboards
- **Custom dashboards:** Widgets (line, stacked area, number, gauge, text, log, alarm)
- **Automatic dashboards:** Pre-built per service (account-level overview)
- **Cross-account:** View metrics from multiple accounts in one dashboard
- **Cross-region:** Single dashboard combining metrics from different regions
- **Pricing:** $3/dashboard/month (first 3 free)
- **Sharing:** Share dashboard publicly (via Cognito) without AWS console access

### Dashboard Best Practices
```
Layout:
├── Row 1: Key Business Metrics (orders/sec, revenue, active users)
├── Row 2: Application Health (error rate, latency P50/P90/P99, throughput)
├── Row 3: Infrastructure (CPU, memory, disk, network)
├── Row 4: Dependencies (DB connections, cache hit rate, queue depth)
└── Row 5: Alarms Status (all alarms in one widget)
```

---

## 6. CloudWatch Container Insights

### ECS Container Insights
- Metrics: CPU/Memory utilization per cluster, service, task
- Network: Bytes in/out, packet drops
- Storage: EBS read/write per container
- **Setup:** Enable at cluster level (account setting for new clusters)

### EKS Container Insights
- Metrics: Pod, node, service, namespace level CPU/Memory/Network/Disk
- **Enhanced observability:** Accelerated compute metrics (GPU), Kubernetes control plane
- **Setup:** CloudWatch Agent (DaemonSet) or AWS Distro for OpenTelemetry (ADOT)
- **Container map:** Visual topology of pods, services, nodes

### Performance Logs
- Container Insights stores structured performance data as log events
- Query with Log Insights:
```
# Top 5 pods by CPU
stats avg(CpuUtilized) as avgCPU by PodName
| sort avgCPU desc
| limit 5

# OOMKilled containers
fields @timestamp, PodName, @message
| filter @message like /OOMKilled/
```

---

## 7. AWS X-Ray (Distributed Tracing)

### Overview
- **What:** Analyze and debug distributed applications (trace requests across services)
- **Trace:** End-to-end path of a request (Segments → Subsegments)
- **Service Map:** Visual representation of application architecture (discovered from traces)
- **Annotations:** Indexed key-value pairs (filterable)
- **Metadata:** Non-indexed data (for debugging, not searchable)

### Integration
| Service | How |
|---------|-----|
| Lambda | Enable "Active Tracing" (1 click) |
| API Gateway | Enable X-Ray tracing on stage |
| ECS/EKS | X-Ray daemon as sidecar container |
| EC2 | X-Ray daemon process |
| App code | X-Ray SDK (instrument HTTP calls, SQL, AWS SDK) |

### X-Ray Sampling Rules
- Default: 1 request/sec + 5% of additional requests
- Custom rules: Match by service, URL path, HTTP method
- **Reservoir:** Guaranteed traces per second
- **Rate:** Percentage of additional requests
- Reduce sampling for high-throughput services (cost/performance)

### X-Ray Insights
- Automated anomaly detection on traces
- Detect: Increased fault rate, latency changes, throttling
- Root cause analysis: Which service/node caused the issue

---

## 8. CloudWatch Synthetics (Canaries)

### What
- Automated scripts that run on schedule (monitors endpoints/APIs)
- Like a "synthetic user" continuously testing your application
- Written in Node.js or Python (Puppeteer/Selenium under the hood)

### Canary Types
| Blueprint | Use Case |
|-----------|----------|
| Heartbeat | Check URL returns 200 |
| API Canary | Test REST API (multi-step) |
| Broken Link Checker | Crawl page, find broken links |
| Visual Monitoring | Screenshot comparison (pixel diff) |
| GUI Workflow | Multi-step UI interactions |

### Features
- Schedule: Every 1 minute to once per hour
- Artifacts: Screenshots, HAR files, logs (stored in S3)
- Alarms: Integrate with CloudWatch Alarms on canary metrics
- VPC: Run inside VPC (test internal endpoints)
- **Use case:** SLA monitoring, deployment validation, third-party dependency health

---

## 9. CloudWatch Application Signals (APM)

### What (new - 2024)
- Application Performance Monitoring (APM) built into CloudWatch
- Auto-discovers services, endpoints, dependencies
- SLO management: Define SLIs/SLOs, track error budget
- Powered by OpenTelemetry (auto-instrumentation)

### Features
- **Service dashboard:** Latency, throughput, errors, dependencies per service
- **SLO:** Define targets (99.9% availability, P99 < 500ms), track burn rate
- **Dependency map:** Auto-discovered call graph
- **Correlated signals:** Metrics + Traces + Logs in one view

---

## 10. Monitoring Architecture Patterns

### Basic Monitoring Stack
```
CloudWatch Metrics → Alarms → SNS → PagerDuty/Slack
CloudWatch Logs → Subscription Filter → Lambda → Elasticsearch/OpenSearch
X-Ray → Service Map + Trace Analysis
Synthetics → Canaries → Alarm on failure
```

### Enterprise Observability
```
Applications (EMF/OTEL) → CloudWatch Metrics + Logs
  ├── Container Insights (EKS/ECS metrics)
  ├── Application Signals (APM, SLOs)
  ├── X-Ray (distributed traces)
  ├── Synthetics (external monitoring)
  └── Dashboards (cross-account, cross-region)

Alerting:
  CloudWatch Alarms → Composite Alarms → SNS
    → PagerDuty (P1/P2)
    → Slack (P3/P4)
    → Incident Manager (runbooks, escalation)

Long-term:
  Logs → Firehose → S3 (Glacier after 90 days)
  Metrics → Metric Streams → Firehose → S3/Datadog/Splunk
```

### Cross-Account Monitoring
- **CloudWatch cross-account observability:** Share metrics/logs/traces across accounts
- **Monitoring account:** Central account views all other accounts
- **Source accounts:** Share their data with monitoring account
- **Use case:** Platform team monitors all workload accounts

---

## 11. Key Metrics to Monitor (by service)

### EC2 / ECS / EKS
| Metric | Alert Threshold | Notes |
|--------|----------------|-------|
| CPU Utilization | > 80% sustained | Scale out trigger |
| Memory Utilization | > 85% | Need CloudWatch Agent |
| Disk Utilization | > 80% | Need CloudWatch Agent |
| StatusCheckFailed | > 0 | Instance health issue |
| NetworkIn/Out | Baseline + 2 stddev | Anomaly detection |

### Lambda
| Metric | Alert Threshold | Notes |
|--------|----------------|-------|
| Errors | > 1% of invocations | Error rate alarm |
| Duration | > 80% of timeout | Risk of timeout |
| Throttles | > 0 | Hitting concurrency limit |
| ConcurrentExecutions | > 80% of limit | Pre-scale or request increase |
| IteratorAge | > 60000 ms (streams) | Falling behind |

### RDS / Aurora
| Metric | Alert Threshold | Notes |
|--------|----------------|-------|
| CPUUtilization | > 80% | Scale up or read replicas |
| FreeableMemory | < 1 GB | Need larger instance |
| DatabaseConnections | > 80% of max | Connection leak or scale |
| ReadReplicaLag | > 30 seconds | Replication issue |
| FreeStorageSpace | < 20% | Scale storage |

### ALB
| Metric | Alert Threshold | Notes |
|--------|----------------|-------|
| TargetResponseTime | P99 > 2 seconds | Backend latency issue |
| HTTPCode_Target_5XX | > 1% | Backend errors |
| UnHealthyHostCount | > 0 | Target failing health checks |
| RejectedConnectionCount | > 0 | LB overloaded |
| ActiveConnectionCount | Baseline + anomaly | Traffic spike |

---

## 12. Scenario-Based Interview Questions

### Q1: Application latency increased 3× but CPU and memory are normal. How to diagnose?
**Answer:**
1. **X-Ray traces:** Look at trace waterfall. Which subsegment has increased latency?
   - Database queries? → Check RDS metrics (connections, IOPS, CPU)
   - External API? → Check that dependency's response time
   - Network? → VPC Flow Logs, check cross-AZ traffic
2. **CloudWatch Logs Insights:** Query for slow requests
   ```
   fields @timestamp, @duration | filter @duration > 3000 | stats count() by bin(5m)
   ```
3. **Check recent changes:** Deployment? Config change? (CloudTrail)
4. **Common causes:** DNS resolution issues, connection pool exhaustion, GC pauses, cold starts, downstream throttling

### Q2: Design monitoring for a multi-account, multi-region SaaS platform
**Answer:**
```
Architecture:
  Central Monitoring Account (us-east-1):
    - Cross-account observability enabled
    - Receives metrics/logs from all workload accounts
    - Centralized dashboards (per-tenant, per-service, overall)
    - Composite alarms (cross-account)
    
  Per-Workload Account:
    - Local alarms (fast response)
    - CloudWatch Agent on all instances
    - Container Insights for EKS
    - X-Ray tracing enabled
    - Logs with 30-day retention (export to S3 for long-term)
    
  Alerting Hierarchy:
    P1 (service down): Auto-remediation → then PagerDuty → Incident Manager
    P2 (degraded): PagerDuty → on-call
    P3 (warning): Slack channel → next business day
    P4 (info): Dashboard only, weekly review
    
  SLO Tracking:
    - Application Signals SLOs per tenant
    - Error budget dashboard (burn rate alerts)
    - Monthly SLA reports (automated via Lambda + QuickSight)
```

### Q3: CloudWatch costs are $15K/month. How to reduce?
**Answer:**
1. **Log reduction (usually 60-70% of cost):**
   - Reduce log verbosity (no DEBUG in prod)
   - Set retention policies (don't keep forever). 30 days active, export to S3
   - Remove redundant logging (VPC flow logs sampling, reduce API Gateway logging)
   - Use EMF instead of PutMetricData (fewer API calls)
2. **Metrics:**
   - Remove unused custom metrics
   - Use Standard resolution (1 min) instead of High Resolution (1 sec)
   - Reduce dimensions (each combination = separate metric)
3. **Alarms:**
   - Consolidate: Composite alarms instead of many individual
   - Remove stale alarms for decommissioned resources
4. **Dashboards:**
   - 3 free, $3/each after. Consolidate dashboards
5. **X-Ray:**
   - Reduce sampling rate (1% instead of 5% for high-traffic)
   - Selectively enable (not every service needs tracing)

### Q4: How to detect and alert on anomalies without knowing thresholds?
**Answer:**
- **CloudWatch Anomaly Detection:** ML model learns metric patterns
  - Handles: Daily patterns, weekly patterns, trends, seasonality
  - Creates upper/lower band. Alarm when metric outside band
  - Training: 2 weeks for good model. Exclude outlier periods
- **Configuration:**
  ```yaml
  MetricName: RequestCount
  AnomalyDetector:
    Band: 2 (standard deviations)
  Alarm:
    ComparisonOperator: LessThanLowerOrGreaterThanUpperThreshold
    ThresholdMetricId: ad1
  ```
- **Limitations:** Doesn't work well for metrics with no pattern, new services, highly variable metrics
- **Alternative:** Contributor Insights (top-N analysis), CloudWatch Logs anomaly detection

### Q5: Lambda function has intermittent 5XX errors. How to build observability?
**Answer:**
```
1. Structured logging (JSON):
   { "level": "ERROR", "requestId": "abc", "error": "timeout", "service": "payment-api" }

2. Custom metrics (EMF):
   { "_aws": {...}, "ErrorType": "timeout", "PaymentService": 1 }

3. X-Ray tracing:
   - Enable Active Tracing
   - Capture subsegments for each external call
   - Annotate: error_type, customer_id (searchable)

4. Alarms:
   - Error rate > 1% over 5 min → P2 alert
   - Throttles > 0 → Scale alert (increase reserved concurrency)
   - Duration P99 > 10s → Timeout risk alert

5. Dashboard:
   - Error count by error type (from custom metric)
   - Invocations vs Errors timeline
   - Duration P50/P90/P99
   - X-Ray service map showing failing downstream

6. Root cause analysis:
   - Log Insights: correlate errors with specific inputs/downstream calls
   - X-Ray: filter traces by fault=true, find common pattern
```

