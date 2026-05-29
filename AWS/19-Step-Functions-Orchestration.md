# AWS Step Functions & Workflow Orchestration - Complete Guide

---

## 1. Step Functions Overview
- **What:** Serverless orchestration service. Coordinate multiple AWS services into workflows
- **Model:** State machine defined in Amazon States Language (ASL) - JSON
- **Visual workflow:** Console shows execution path, input/output per state, errors
- **Pricing:** Standard: $0.025 per 1,000 state transitions. Express: $1 per 1M requests + duration
- **Integration:** 220+ AWS services (native SDK integrations, no Lambda glue code needed)

---

## 2. Workflow Types

| Feature | Standard | Express |
|---------|----------|---------|
| Duration | Up to 1 year | Up to 5 minutes |
| Execution model | Exactly-once | At-least-once (async) or At-most-once (sync) |
| Pricing | Per state transition ($0.025/1K) | Per request + duration |
| Execution history | Full (in console, 90 days) | CloudWatch Logs |
| Throughput | 2,000/sec start | 100,000/sec start |
| **Use case** | Long-running, exactly-once needed | High-volume, short, idempotent |

### Express Workflow Modes
- **Asynchronous:** Fire and forget. Result in CloudWatch Logs
- **Synchronous:** Caller waits for result (up to 5 min). For API Gateway integration

---

## 3. State Types

### Task State
- Performs work (invoke Lambda, call AWS API, activity worker)
```json
{
  "Type": "Task",
  "Resource": "arn:aws:lambda:us-east-1:123:function:ProcessOrder",
  "Parameters": {
    "orderId.$": "$.orderId",
    "amount.$": "$.amount"
  },
  "ResultPath": "$.processResult",
  "Retry": [
    {
      "ErrorEquals": ["ServiceException"],
      "IntervalSeconds": 2,
      "MaxAttempts": 3,
      "BackoffRate": 2.0
    }
  ],
  "Catch": [
    {
      "ErrorEquals": ["States.ALL"],
      "Next": "HandleError",
      "ResultPath": "$.error"
    }
  ],
  "TimeoutSeconds": 300,
  "Next": "NextState"
}
```

### SDK Integrations (200+ services, no Lambda needed)
```json
{
  "Type": "Task",
  "Resource": "arn:aws:states:::dynamodb:putItem",
  "Parameters": {
    "TableName": "Orders",
    "Item": {
      "orderId": {"S.$": "$.orderId"},
      "status": {"S": "PROCESSING"}
    }
  }
}
```
Common integrations: DynamoDB, SQS, SNS, ECS RunTask, Glue, EMR, SageMaker, CodeBuild, API Gateway

### Integration Patterns
| Pattern | Suffix | Behavior |
|---------|--------|----------|
| Request Response | (none) | Call API, get response, move on |
| Run a Job (.sync) | .sync | Start job, WAIT for completion, then move on |
| Wait for Callback | .waitForTaskToken | Pause, pass token, resume when external system calls back |

### Choice State (branching)
```json
{
  "Type": "Choice",
  "Choices": [
    {
      "Variable": "$.amount",
      "NumericGreaterThan": 1000,
      "Next": "HighValueOrder"
    },
    {
      "Variable": "$.status",
      "StringEquals": "PREMIUM",
      "Next": "PremiumProcessing"
    }
  ],
  "Default": "StandardProcessing"
}
```
- Comparison operators: StringEquals, NumericGreaterThan, BooleanEquals, TimestampLessThan, IsPresent, IsString, etc.
- Combine with And, Or, Not

### Parallel State (concurrent branches)
```json
{
  "Type": "Parallel",
  "Branches": [
    {
      "StartAt": "CheckInventory",
      "States": { "CheckInventory": { "Type": "Task", ... } }
    },
    {
      "StartAt": "ValidatePayment",
      "States": { "ValidatePayment": { "Type": "Task", ... } }
    },
    {
      "StartAt": "CalculateShipping",
      "States": { "CalculateShipping": { "Type": "Task", ... } }
    }
  ],
  "Next": "ProcessResults"
}
```
- All branches execute concurrently
- Output: Array of branch results (in order)
- If ANY branch fails → entire Parallel fails (unless caught)

### Map State (iterate over collection)
```json
{
  "Type": "Map",
  "ItemsPath": "$.orders",
  "MaxConcurrency": 10,
  "ItemProcessor": {
    "ProcessorConfig": {
      "Mode": "DISTRIBUTED"
    },
    "StartAt": "ProcessOrder",
    "States": {
      "ProcessOrder": { "Type": "Task", ... }
    }
  },
  "Next": "Done"
}
```
- **Inline Mode:** Up to 40 concurrent iterations (per execution)
- **Distributed Mode:** Up to 10,000 concurrent iterations! (separate child executions)
  - Can process millions of items (S3 inventory, large CSV files)
  - Each child: own execution, own timeout, own history

### Wait State
```json
{ "Type": "Wait", "Seconds": 60, "Next": "CheckStatus" }
{ "Type": "Wait", "Timestamp": "2024-03-01T00:00:00Z", "Next": "Execute" }
{ "Type": "Wait", "SecondsPath": "$.waitTime", "Next": "Continue" }
```

### Other States
- **Pass:** Pass input to output (add/transform data, no-op)
- **Succeed:** Terminal success state
- **Fail:** Terminal failure state (with Error and Cause)

---

## 4. Error Handling

### Built-in Error Codes
| Error | When |
|-------|------|
| States.ALL | Catches everything |
| States.Timeout | Task exceeded TimeoutSeconds |
| States.TaskFailed | Task returned error |
| States.Permissions | Insufficient IAM permissions |
| States.ResultPathMatchFailure | ResultPath can't apply to input |
| States.ParameterPathFailure | Path in Parameters doesn't exist |
| States.HeartbeatTimeout | Heartbeat not received in time |

### Retry
```json
"Retry": [
  {
    "ErrorEquals": ["TransientError"],
    "IntervalSeconds": 1,
    "MaxAttempts": 5,
    "BackoffRate": 2.0,
    "MaxDelaySeconds": 60
  },
  {
    "ErrorEquals": ["States.ALL"],
    "MaxAttempts": 2
  }
]
```
- Evaluated in order (first match wins)
- BackoffRate: Multiplier for each retry (2.0 = 1s, 2s, 4s, 8s, 16s)
- MaxDelaySeconds: Cap the backoff interval

### Catch
```json
"Catch": [
  {
    "ErrorEquals": ["PaymentDeclined"],
    "Next": "HandleDeclinedPayment",
    "ResultPath": "$.error"
  },
  {
    "ErrorEquals": ["States.ALL"],
    "Next": "GeneralErrorHandler"
  }
]
```

---

## 5. Input/Output Processing

### Data Flow
```
State Input → InputPath (select portion) → Parameters (construct) 
  → Task Execution → Result → ResultSelector (reshape) 
    → ResultPath (where to place in original input) → OutputPath (select portion) → State Output
```

### Key Concepts
| Filter | Purpose | Example |
|--------|---------|---------|
| InputPath | Select which part of input to use | "$.order" (only order object) |
| Parameters | Construct task input | Map fields, add static values |
| ResultSelector | Reshape task output | Select specific fields from result |
| ResultPath | Where to put result in input | "$.taskResult" (merge with input) |
| OutputPath | Select what to pass to next state | "$.taskResult" (only result, discard rest) |

### Intrinsic Functions
```json
{
  "Parameters": {
    "id.$": "States.UUID()",
    "timestamp.$": "States.Format('{}T{}', $.date, $.time)",
    "hash.$": "States.Hash($.data, 'SHA-256')",
    "array.$": "States.Array($.item1, $.item2)",
    "json.$": "States.StringToJson($.jsonString)",
    "partition.$": "States.ArrayPartition($.items, 10)"
  }
}
```

---

## 6. Step Functions Patterns

### Saga Pattern (Compensation)
```json
{
  "Comment": "Order Saga with compensation",
  "StartAt": "ReserveInventory",
  "States": {
    "ReserveInventory": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:...:ReserveInventory",
      "Catch": [{ "ErrorEquals": ["States.ALL"], "Next": "Fail" }],
      "Next": "ProcessPayment"
    },
    "ProcessPayment": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:...:ProcessPayment",
      "Catch": [{ "ErrorEquals": ["States.ALL"], "Next": "ReleaseInventory" }],
      "Next": "ShipOrder"
    },
    "ShipOrder": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:...:ShipOrder",
      "Catch": [{ "ErrorEquals": ["States.ALL"], "Next": "RefundPayment" }],
      "Next": "Success"
    },
    "RefundPayment": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:...:RefundPayment",
      "Next": "ReleaseInventory"
    },
    "ReleaseInventory": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:...:ReleaseInventory",
      "Next": "Fail"
    },
    "Success": { "Type": "Succeed" },
    "Fail": { "Type": "Fail", "Error": "SagaFailed" }
  }
}
```

### Human Approval Workflow
```
Start → Submit Request → Wait for Approval (callback token)
  → [Human reviews in web app]
  → Human calls SendTaskSuccess/SendTaskFailure with token
  → Approved? → Choice → Yes → Execute Change
                        → No → Notify Requestor (rejected)
  → Timeout (48 hours) → Auto-reject
```

### Polling Pattern (wait for async job)
```
Start Job → Wait 30s → Check Status → Choice:
  COMPLETED → Process Result
  FAILED → Handle Error  
  RUNNING → Wait 30s (loop back)
```

### Fan-Out / Fan-In
```
Get Items → Map (Distributed, 10K concurrency):
  Per item: Validate → Transform → Load
→ Collect Results → Generate Report
```

### Circuit Breaker
```
Check Circuit State (DynamoDB):
  OPEN → Return cached/fallback response
  CLOSED → Call Downstream Service:
    Success → Reset failure count → Return
    Failure → Increment failure count:
      > threshold → Set state OPEN, set TTL → Return fallback
  HALF-OPEN → Try single request:
    Success → Set CLOSED
    Failure → Set OPEN
```

---

## 7. Step Functions + EventBridge / API Gateway

### API Gateway Integration
```
REST API → POST /orders → Step Functions StartExecution
  - Synchronous: API Gateway waits for workflow result (Express)
  - Asynchronous: Return executionArn immediately (Standard)
  
HTTP API → Step Functions integration (direct, no Lambda proxy)
```

### EventBridge Trigger
```
EventBridge Rule → Target: Step Functions (start execution)
  Input: Event detail becomes execution input
  
Use case: S3 upload event → Start file processing workflow
         Scheduled event → Start daily ETL pipeline
```

### Nested Workflows
```
Parent Workflow:
  → Start Child Workflow A (.sync - wait for completion)
  → Start Child Workflow B (.sync)
  → Aggregate results
  
Benefits:
  - Modularity (reuse child workflows)
  - Separate execution histories
  - Different teams own different workflows
```

---

## 8. Best Practices

### Design
- **Single responsibility:** Each state does one thing
- **Idempotent tasks:** Design all tasks to handle re-execution safely
- **Timeouts:** Always set TimeoutSeconds (don't rely on defaults)
- **Error handling:** Catch at every task, have a global error handler
- **Small payloads:** State input/output max 256 KB. Use S3 for large data, pass references

### Performance
- **Express for high-volume:** If > 1000 executions/sec and < 5 min duration
- **Distributed Map:** For processing millions of items (not inline Map)
- **Minimize state transitions:** Each transition costs (Standard). Combine simple operations
- **Avoid Lambda for simple operations:** Use SDK integrations (DynamoDB, SQS, SNS directly)

### Cost Optimization
- **Express vs Standard:** Express is 10× cheaper for high-volume short workflows
- **Reduce transitions:** Fewer states = lower cost
- **SDK integrations:** Eliminate Lambda invocations (no Lambda cost + no transition to/from Lambda)
- **Batch processing:** Process items in batches in Map state (fewer total executions)

---

## 9. Scenario-Based Interview Questions

### Q1: Design an order fulfillment workflow for e-commerce
**Answer:**
```
Workflow: Standard (long-running, exactly-once, visible execution history)

States:
  1. ValidateOrder (Task: Lambda)
     - Check items exist, prices correct, address valid
     - Catch: ValidationError → NotifyCustomer("invalid order")
     
  2. ReserveInventory (Task: DynamoDB conditional update)
     - Atomic decrement stock. Catch: InsufficientStock → Waitlist
     
  3. ProcessPayment (Task: Lambda → Stripe API)
     - Retry: 3 attempts, backoff 2x (transient network errors)
     - Catch: PaymentDeclined → ReleaseInventory → NotifyCustomer
     
  4. Parallel:
     - Branch A: CreateShipment (Task: Lambda → shipping API)
     - Branch B: SendConfirmation (Task: SNS email)
     - Branch C: UpdateAnalytics (Task: Firehose putRecord)
     
  5. WaitForShipment (Callback: shipping webhook sends task token)
     - TimeoutSeconds: 604800 (7 days)
     
  6. MarkDelivered (Task: DynamoDB update)
  
  7. Success

Compensation (on any failure after payment):
  RefundPayment → ReleaseInventory → NotifyCustomer → Fail
```

### Q2: Process 10 million S3 objects using Step Functions
**Answer:**
```
Workflow: Standard (orchestrator) + Distributed Map

States:
  1. GetS3Inventory (Task: Lambda - list or use S3 Inventory manifest)
  
  2. Distributed Map:
     - ItemReader: S3 Inventory CSV manifest (or S3 ListObjects)
     - MaxConcurrency: 1000 (control parallel load)
     - BatchSize: 100 (each child processes 100 items)
     - Child Workflow: Express (short, cheap per execution)
       Per batch:
         - Download objects
         - Transform (resize, convert, classify)
         - Upload result to destination bucket
         - Record status in DynamoDB
     
  3. AggregateResults: Count successes/failures
  
  4. SendReport: SNS notification with summary

Cost estimate:
  - 10M objects / 100 batch = 100K child executions
  - Express: ~$0.10 for requests + duration
  - Parent: ~50 state transitions = $0.00125
  - Total Step Functions cost: < $5 for 10M objects
```

### Q3: Implement async API with Step Functions (long-running task)
**Answer:**
```
Client → API Gateway POST /process → Step Functions StartExecution
  Response: { "executionId": "abc-123", "statusUrl": "/process/abc-123" }

Step Functions Workflow:
  1. Store initial status in DynamoDB (PENDING)
  2. Long processing (may take minutes/hours)
  3. Update DynamoDB (COMPLETED + result)
  4. Notify via WebSocket / callback URL

Client polls: GET /process/abc-123 → Lambda → Read DynamoDB
  Returns: { "status": "PROCESSING" } or { "status": "COMPLETED", "result": {...} }

Better: WebSocket notification
  - Step Functions → SNS → Lambda → API Gateway WebSocket → Client
  - No polling needed, instant notification

Even better: Callback pattern
  - Client provides callback URL
  - Workflow completes → Lambda calls client's webhook
```

### Q4: Step Functions vs SQS + Lambda for workflow orchestration?
**Answer:**
| | Step Functions | SQS + Lambda Chain |
|--|---|---|
| Visibility | Full visual execution, state per step | Hard to trace (distributed logs) |
| Error handling | Built-in retry, catch, compensation | DIY in each Lambda (manual DLQ) |
| Branching | Choice state (declarative) | Code logic in Lambda |
| Parallel | Parallel/Map states | Fan-out via multiple queues |
| Long-running | Up to 1 year (callbacks) | Difficult (queue message retention 14 days) |
| Cost (low volume) | Higher (per transition) | Lower (per message) |
| Cost (high volume) | Express workflows competitive | May be cheaper |
| Complexity | Declarative, easy to modify | More code, harder to change |
| **Choose Step Functions** | Complex logic, visibility needed, long-running, saga | |
| **Choose SQS** | Simple fan-out, very high volume, decoupling only | |

### Q5: Design ML model training pipeline with Step Functions
**Answer:**
```
Trigger: S3 upload of new training data → EventBridge → Step Functions

Workflow:
  1. DataValidation (Lambda):
     - Schema validation, null checks, distribution analysis
     - Fail if data quality < threshold
     
  2. DataPreprocessing (Glue Job .sync):
     - Feature engineering, normalization, train/test split
     - Wait for completion (may take 30 min)
     
  3. ModelTraining (SageMaker CreateTrainingJob .sync):
     - Hyperparameters from SSM Parameter Store
     - Wait for completion (may take hours)
     - Retry on transient failures (spot interruption)
     
  4. ModelEvaluation (Lambda):
     - Compare new model metrics vs current production model
     - Choice: improvement > 2%?
       Yes → Continue to deployment
       No → Archive model → Notify team → End
       
  5. Human Approval (Callback):
     - SNS → Reviewer → Reviews metrics → Approves/Rejects
     - Timeout: 72 hours → Auto-reject
     
  6. DeployModel (SageMaker CreateEndpoint .sync):
     - Canary deployment: 10% traffic to new model
     - Wait 1 hour
     - CheckCanaryMetrics: Errors < threshold?
       Yes → Full deployment (100%)
       No → Rollback → Alert team
       
  7. Success: Update model registry, notify stakeholders
```

