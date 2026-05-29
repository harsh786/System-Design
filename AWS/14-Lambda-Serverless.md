# AWS Lambda & Serverless - Complete Guide

---

## 1. Lambda Overview
- **What:** Run code without provisioning servers. Pay per invocation + duration
- **Runtime:** Node.js, Python, Java, Go, .NET, Ruby, custom (via containers or layers)
- **Trigger → Execute → Scale automatically → Pay only for what you use**
- **Max execution time:** 15 minutes
- **Memory:** 128 MB to 10,240 MB (CPU scales proportionally)
- **Pricing:** $0.20 per 1M requests + $0.0000166667 per GB-second

---

## 2. Lambda Execution Model

### Cold Start vs Warm Start
- **Cold start:** New execution environment created (download code, init runtime, run init code). Takes 100ms-10s
- **Warm start:** Reuse existing environment (skip init). Takes < 10ms
- **Factors affecting cold start:** Runtime (Java > Node.js), package size, VPC (adds ENI creation), memory allocation
- **Mitigation:** Provisioned Concurrency (pre-warmed), keep functions warm (scheduled ping), smaller packages

### Execution Environment Lifecycle
```
INIT phase (cold start only):
  Extension init → Runtime init → Function init (your global scope code)
INVOKE phase (every invocation):
  Your handler function executes
SHUTDOWN phase (idle timeout):
  Runtime shutdown → Extension shutdown → Environment destroyed
```

### Concurrency
- **Default:** 1000 concurrent executions per region (soft limit, can increase)
- **Reserved concurrency:** Guarantee capacity for critical functions (also throttles to this limit)
- **Provisioned concurrency:** Pre-initialized environments (eliminate cold starts). Costs: always-on
- **Burst:** Initial burst of 500-3000 (varies by region), then +500/minute
- **Throttling:** When at concurrency limit → 429 TooManyRequestsException

---

## 3. Lambda Event Sources

### Synchronous Invocations (caller waits for response)
| Source | Notes |
|--------|-------|
| API Gateway | REST/HTTP API → Lambda |
| ALB | Target type: Lambda |
| CloudFront (Lambda@Edge) | Edge processing |
| Cognito | Lambda triggers |
| Step Functions | Orchestration |
| SDK/CLI | Direct invoke |

### Asynchronous Invocations (fire and forget)
| Source | Notes |
|--------|-------|
| S3 Events | Object created/deleted |
| SNS | Topic notification |
| CloudWatch Events/EventBridge | Scheduled, rule-based |
| CodeCommit | Repository events |
| SES | Email receiving |
| CloudFormation | Custom resources |

- **Async behavior:** Lambda retries 2x (total 3 attempts). On final failure → DLQ (SQS/SNS) or Destinations
- **Destinations:** On success/failure → route to SQS, SNS, Lambda, EventBridge

### Stream-based (polling)
| Source | Notes |
|--------|-------|
| Kinesis Data Streams | Batch processing, per-shard |
| DynamoDB Streams | CDC events |
| SQS | Queue polling (batch 1-10000) |
| MSK / Self-managed Kafka | Event streaming |

- **Event Source Mapping:** Lambda service polls the stream/queue and invokes function with batch
- **SQS:** Batch size 1-10000, batch window 0-300s. Failed messages → retry or DLQ
- **Kinesis/DynamoDB:** Batch size 1-10000, per-shard parallelization, bisect batch on error

---

## 4. Lambda Configuration

### Environment Variables
- Key-value pairs available in function code
- Can encrypt with KMS (encrypted at rest automatically, optionally encrypt in transit)
- Max 4 KB total

### Lambda Layers
- Shared code/libraries across functions (up to 5 layers per function)
- **Use case:** Common dependencies (AWS SDK, numpy), shared business logic, custom runtimes
- Layers versioned independently. Total unzipped size: 250 MB (with layers)

### VPC Configuration
- Lambda in VPC: Access private resources (RDS, ElastiCache, internal services)
- **ENI:** Lambda creates Hyperplane ENI in each subnet/security group combination
- **Cold start impact:** Minimal since Hyperplane (used to be 10s+ with classic ENIs)
- **Internet access from VPC Lambda:** Needs NAT Gateway in public subnet
- **Best practice:** Only put Lambda in VPC if it needs private resource access

### Lambda Container Images
- Package function as Docker image (up to 10 GB)
- Use AWS base images or custom (must implement Lambda Runtime API)
- Stored in ECR. Pulled and cached by Lambda service
- **Use case:** Large dependencies, existing container workflows, custom runtimes

---

## 5. Lambda Advanced Features

### Lambda@Edge vs CloudFront Functions
| | Lambda@Edge | CloudFront Functions |
|--|---|---|
| Events | Viewer/Origin Request/Response | Viewer Request/Response only |
| Runtime | Node.js, Python | JavaScript |
| Duration | 5-30s | < 1ms |
| Memory | 128-10240 MB | 2 MB |
| Network | Yes | No |
| Body access | Yes (origin events) | No |
| Scale | Thousands RPS | Millions RPS |
| **Use** | Complex auth, origin selection, A/B testing | URL rewrite, header manipulation |

### Step Functions Integration
- **Standard workflow:** Invoke Lambda, wait for result, branch/retry/catch
- **Express workflow:** High-volume, short duration (up to 5 min)
- **Map state:** Fan-out parallel Lambda invocations (up to 10,000 concurrent)
- **Callback pattern:** Lambda returns task token → external system completes later

### Lambda Power Tuning
- Use AWS Lambda Power Tuning (Step Functions tool)
- Tests function at different memory sizes → shows cost vs speed trade-off
- Often: More memory = faster = CHEAPER (less duration × higher rate = similar cost but faster)

### Lambda SnapStart (Java)
- Snapshots initialized execution environment (after INIT phase)
- New invocations restore from snapshot instead of cold starting
- Reduces Java cold start from 5-10s to < 200ms
- Must handle: Unique values (don't cache random/time in init), network connections (re-establish)

---

## 6. Lambda Error Handling

### Retry Behavior
| Invocation Type | Retry | Error Handling |
|-----------------|-------|----------------|
| Synchronous | No (caller retries) | Return error to caller |
| Asynchronous | 2 retries (configurable) | DLQ or Destination on failure |
| Stream (Kinesis/DDB) | Until success or data expires | Bisect batch, max retry attempts, skip |
| SQS | Returns to queue, retry until visibility timeout | After maxReceiveCount → DLQ |

### Dead Letter Queues (DLQ)
- SQS queue or SNS topic for failed events
- **Async only:** Configure on Lambda function
- **SQS source:** Configure on SQS queue (redrive policy)
- **Best practice:** Always configure DLQ. Monitor DLQ depth with CloudWatch alarm

### Destinations
- Route function results (success/failure) to:
  - SQS, SNS, Lambda, EventBridge
- More flexible than DLQ (captures success too, includes full event + response/error)
- **Preferred over DLQ for new designs**

---

## 7. Lambda Security
- **Execution Role:** IAM role assumed by Lambda function (permissions to access AWS services)
- **Resource Policy:** Who can invoke the function (API Gateway, S3, other accounts)
- **VPC:** Isolate in private subnets, security group controls outbound traffic
- **Environment variable encryption:** KMS (encrypt helpers via console/SDK)
- **Code signing:** Ensure only trusted code deployed (AWS Signer)
- **Reserved concurrency:** Prevent one function from consuming all capacity (isolate)

---

## 8. Lambda Monitoring
- **CloudWatch Metrics:** Invocations, Errors, Duration, Throttles, ConcurrentExecutions, IteratorAge (streams)
- **CloudWatch Logs:** Every invocation logged (START, END, REPORT + your console.log/print)
- **X-Ray:** Distributed tracing (add `tracing: Active` in config)
- **CloudWatch Lambda Insights:** Enhanced monitoring (CPU, memory, network, cold starts)
- **Key alarm:** IteratorAge for stream sources (growing = falling behind = problem)

---

## 9. Lambda Patterns & Best Practices

### Architectural Patterns
- **API Backend:** API Gateway → Lambda → DynamoDB/RDS
- **Event Processing:** S3/SQS/Kinesis → Lambda → transform → store
- **Scheduled Tasks:** EventBridge (cron) → Lambda → cleanup/reporting
- **Stream Processing:** Kinesis/DDB Streams → Lambda → aggregate → write
- **Orchestration:** Step Functions → multiple Lambdas → saga pattern

### Best Practices
- **Keep functions small:** Single responsibility (one function = one job)
- **Minimize cold starts:** Small packages, avoid VPC unless needed, provisioned concurrency for critical
- **Reuse connections:** Initialize SDK clients OUTSIDE handler (reused across warm invocations)
- **Idempotent handlers:** Same event processed twice → same result (use DynamoDB conditional write / dedup)
- **Timeouts:** Set reasonable timeout (not 15 min default). Downstream timeouts shorter than function timeout
- **Environment variables:** Configuration (not code). Secrets via Secrets Manager / SSM
- **Power tuning:** Right-size memory for cost/performance balance

---

## 10. Serverless Ecosystem

### API Gateway + Lambda
- REST API: Full features, request/response transformation, caching
- HTTP API: Simpler, cheaper ($1/M vs $3.50/M), faster, JWT auth native
- Direct Lambda URL (Function URL): Simplest, no API Gateway needed, HTTPS endpoint directly on Lambda

### EventBridge
- Serverless event bus for event-driven architectures
- **Rules:** Route events based on pattern matching
- **Sources:** 90+ AWS services, SaaS (Zendesk, Shopify), custom apps
- **Targets:** Lambda, SQS, SNS, Step Functions, API Gateway, ECS tasks, and more
- **Features:** Archive events (replay), schema registry, pipes (source→enrichment→target)

### Step Functions
- **Orchestrate:** Multiple Lambda functions with branching, parallel, error handling
- **Standard:** Long-running (1 year), exactly-once, $0.025/1000 transitions
- **Express:** Short (5 min), at-least-once, high-volume, $0.001/1000 requests
- **Use cases:** Order processing, ETL pipelines, ML workflows, approval processes

---

## 11. Scenario-Based Interview Questions

### Q1: Lambda function connecting to RDS has connection timeout errors at scale
**Answer:**
- **Problem:** Each Lambda instance opens DB connection. 1000 concurrent Lambdas = 1000 connections (exceeds RDS max_connections ~600 for db.r5.large)
- **Solution 1: RDS Proxy** (recommended) - Pools connections. 1000 Lambda → 100 DB connections
- **Solution 2:** Reduce concurrency with reserved concurrency (cap at 100)
- **Solution 3:** DynamoDB instead of RDS (no connection limit)
- **Solution 4:** Connection reuse in Lambda (init outside handler, reuse across warm invocations)

### Q2: Lambda cold starts causing timeout for user-facing API
**Answer:**
- **Provisioned Concurrency:** Set to expected baseline traffic (eliminates cold starts, costs money)
- **Reduce function size:** Remove unused dependencies, use Lambda layers, tree-shake
- **Avoid VPC:** If function doesn't need private resources, remove VPC config
- **Runtime choice:** Node.js/Python cold starts ~200ms. Java ~5s. Use SnapStart for Java
- **Architecture:** For latency-critical: Consider Fargate/ECS instead (always warm)

### Q3: Design event-driven image processing pipeline
**Answer:**
```
User uploads image → S3 bucket (s3:ObjectCreated event)
  → EventBridge rule → Step Functions workflow:
    1. Lambda: Validate image (size, format, virus scan)
    2. Lambda: Generate thumbnail (256px)
    3. Lambda: Generate medium (1024px)
    4. Parallel: Lambda: Extract EXIF metadata
    5. Lambda: Store metadata in DynamoDB
    6. Lambda: Notify user (SNS → email/push)
    
Error handling: 
  - Any step fails → catch → DLQ → manual review
  - Retry 2x with exponential backoff per step
```

### Q4: Lambda function costs are $5000/month. Optimize?
**Answer:**
1. **Power tuning:** Find optimal memory (might be 512 MB instead of 1024 MB)
2. **Reduce invocations:** Batch processing (SQS batch size 10 instead of 1)
3. **Reduce duration:** Optimize code, reduce dependencies, cache repeated lookups
4. **Provisioned vs on-demand:** If steady traffic, provisioned can be cheaper (avoid burst pricing)
5. **Architecture change:** If always running 24/7 → consider Fargate (cheaper for constant load)
6. **Graviton (ARM):** 20% cheaper for same compute. Use arm64 architecture

### Q5: Design serverless real-time data processing at 100K events/second
**Answer:**
- **Ingestion:** Kinesis Data Streams (100 shards × 1000 records/sec = 100K/sec)
- **Processing:** Lambda with Kinesis trigger (parallelization factor 10 per shard = 1000 concurrent)
- **Enrichment:** DynamoDB lookups (DAX cache for hot keys)
- **Storage:** Kinesis Data Firehose → S3 (Parquet, partitioned by time)
- **Real-time analytics:** Lambda → DynamoDB (counters) → API for dashboard
- **Alternative:** Kinesis Data Analytics (Apache Flink) for complex aggregations (windowed, stateful)
- **Cost:** ~$3000-5000/month at this scale (Lambda + Kinesis + DynamoDB)

