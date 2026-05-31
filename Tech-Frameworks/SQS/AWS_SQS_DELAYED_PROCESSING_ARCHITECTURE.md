# AWS SQS - Delayed Record Processing Architecture

## Table of Contents
1. [AWS SQS Overview](#aws-sqs-overview)
2. [Key SQS Concepts](#key-sqs-concepts)
3. [Delayed Processing Use Case](#delayed-processing-use-case)
4. [Architecture Design](#architecture-design)
5. [Implementation Details](#implementation-details)
6. [Scaling Considerations](#scaling-considerations)
7. [Best Practices](#best-practices)

---

## AWS SQS Overview

**Amazon Simple Queue Service (SQS)** is a fully managed message queuing service that enables you to decouple and scale microservices, distributed systems, and serverless applications.

### Types of SQS Queues

1. **Standard Queue**
   - Unlimited throughput
   - At-least-once delivery
   - Best-effort ordering
   - Use case: High throughput scenarios where occasional duplicates are acceptable

2. **FIFO Queue**
   - Up to 3,000 messages per second (with batching: 30,000 msg/s)
   - Exactly-once processing
   - Strict ordering (First-In-First-Out)
   - Use case: When message order and deduplication are critical

---

## Key SQS Concepts

### 1. **Delay Queues**
- **Purpose**: Postpone delivery of new messages to consumers
- **Delay Period**: 0 to 15 minutes (900 seconds)
- **Configuration**: Set at queue level or per-message level
- **Use Case**: Implement a waiting period before messages become available

```
Message Sent → Delay Period → Message Available for Processing
```

### 2. **Visibility Timeout**
- **Purpose**: Prevents other consumers from processing a message that's already being processed
- **Duration**: 0 seconds to 12 hours (default: 30 seconds)
- **Mechanism**: When a consumer retrieves a message, it becomes invisible to other consumers
- **Behavior**: 
  - If processed successfully → Delete message
  - If not processed within timeout → Message becomes visible again

```
Consumer Receives Msg → Visibility Timeout Starts → Process → Delete Msg
                                ↓
                    (Timeout expires) → Msg visible again
```

### 3. **Message Retention**
- Messages can be retained in queue for 1 minute to 14 days
- Default: 4 days
- After retention period, messages are automatically deleted

### 4. **Dead Letter Queue (DLQ)**
- Receives messages that can't be processed successfully
- Helps isolate problematic messages for debugging
- **maxReceiveCount**: Number of times a message can be received before moving to DLQ

### 5. **Long Polling**
- Reduces empty responses and false empty responses
- Wait time: 1 to 20 seconds
- More cost-effective than short polling

---

## Delayed Processing Use Case

### Business Requirement
Process records with progressive retry delays:
- **1st Attempt**: Immediate (0 min)
- **2nd Attempt**: After 15 minutes
- **3rd Attempt**: After 30 minutes
- **4th Attempt**: After 45 minutes
- **5th Attempt**: After 60 minutes

### Challenges
1. SQS delay queue maximum: 15 minutes
2. Need to handle delays beyond 15 minutes (30, 45, 60 min)
3. Maintain processing state and retry count
4. Handle failures and dead letters

---

## Architecture Design

### Solution: Multi-Queue Architecture with DynamoDB State Management

```
┌─────────────────────────────────────────────────────────────────────┐
│                         DELAYED PROCESSING SYSTEM                    │
└─────────────────────────────────────────────────────────────────────┘

┌──────────────┐
│   Producer   │
│  Application │
└──────┬───────┘
       │
       ├── Send Initial Message
       │
       ▼
┌─────────────────────┐
│   Primary Queue     │◄─────────────────┐
│  (Standard SQS)     │                  │
│  - No Delay         │                  │
└──────┬──────────────┘                  │
       │                                 │
       │ Receive Message                 │
       ▼                                 │
┌─────────────────────┐                  │
│  Lambda/Worker      │                  │
│   Processor         │                  │
│                     │                  │
│  1. Process Record  │                  │
│  2. Check Status    │                  │
│  3. Update State    │                  │
└──────┬──────────────┘                  │
       │                                 │
       ├─── Success ───► Delete Message  │
       │                                 │
       ├─── Retry Logic                  │
       │                                 │
       ▼                                 │
┌─────────────────────────────────────────┴─────────────┐
│              RETRY QUEUE ARCHITECTURE                  │
│                                                        │
│  ┌──────────────────┐    ┌──────────────────┐        │
│  │  15-Min Queue    │    │  30-Min Queue    │        │
│  │  Delay: 15 min   │    │  Delay: 15 min   │        │
│  │  (Retry #2)      │    │  (Retry #3)      │        │
│  └────────┬─────────┘    └────────┬─────────┘        │
│           │                       │                   │
│           └───────────┬───────────┘                   │
│                       │                               │
│  ┌──────────────────┐ │ ┌──────────────────┐         │
│  │  45-Min Queue    │ │ │  60-Min Queue    │         │
│  │  Delay: 15 min   │ │ │  Delay: 15 min   │         │
│  │  (Retry #4)      │ │ │  (Retry #5)      │         │
│  └────────┬─────────┘ │ └────────┬─────────┘         │
│           │           │          │                    │
│           └───────────┴──────────┘                    │
│                       │                               │
│                       │ All route back to Primary     │
│                       └───────────────────────────────┘
│                                                        │
└────────────────────────────────────────────────────────┘
       │
       │ Max Retries Exceeded
       ▼
┌──────────────────────┐
│   Dead Letter Queue  │
│   (Final Failures)   │
└──────────────────────┘

┌─────────────────────────────────────────────────────────┐
│              STATE MANAGEMENT (DynamoDB)                 │
├──────────────┬──────────────┬───────────┬──────────────┤
│  MessageID   │  RetryCount  │  NextTime │  Metadata    │
├──────────────┼──────────────┼───────────┼──────────────┤
│  msg-12345   │      2       │  15:30:00 │  {...}       │
│  msg-67890   │      4       │  16:45:00 │  {...}       │
└──────────────┴──────────────┴───────────┴──────────────┘
```

---

## Implementation Details

### Architecture Components

#### 1. **Queue Setup**

```yaml
Queues:
  Primary_Queue:
    Type: Standard
    DelaySeconds: 0
    VisibilityTimeout: 300  # 5 minutes
    MessageRetentionPeriod: 1209600  # 14 days
    ReceiveMessageWaitTimeSeconds: 20  # Long polling
    
  Retry_15Min_Queue:
    Type: Standard
    DelaySeconds: 900  # 15 minutes
    VisibilityTimeout: 300
    
  Retry_30Min_Queue:
    Type: Standard
    DelaySeconds: 900  # 15 minutes (cumulative: 15+15=30)
    VisibilityTimeout: 300
    
  Retry_45Min_Queue:
    Type: Standard
    DelaySeconds: 900  # 15 minutes (cumulative: 30+15=45)
    VisibilityTimeout: 300
    
  Retry_60Min_Queue:
    Type: Standard
    DelaySeconds: 900  # 15 minutes (cumulative: 45+15=60)
    VisibilityTimeout: 300
    
  Dead_Letter_Queue:
    Type: Standard
    MessageRetentionPeriod: 1209600  # 14 days for debugging
```

#### 2. **DynamoDB State Table**

```json
{
  "TableName": "MessageProcessingState",
  "KeySchema": [
    {
      "AttributeName": "messageId",
      "KeyType": "HASH"
    }
  ],
  "Attributes": {
    "messageId": "String",
    "retryCount": "Number",
    "lastAttemptTimestamp": "Number",
    "nextAttemptTimestamp": "Number",
    "status": "String",  // PENDING, PROCESSING, SUCCESS, FAILED
    "originalPayload": "Map",
    "errorHistory": "List",
    "createdAt": "Number",
    "ttl": "Number"  // Auto-cleanup after 30 days
  }
}
```

#### 3. **Processing Logic**

```python
import boto3
import json
from datetime import datetime, timedelta

sqs = boto3.client('sqs')
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('MessageProcessingState')

# Queue URLs
QUEUES = {
    'primary': 'https://sqs.us-east-1.amazonaws.com/123456/primary-queue',
    'retry_15': 'https://sqs.us-east-1.amazonaws.com/123456/retry-15min-queue',
    'retry_30': 'https://sqs.us-east-1.amazonaws.com/123456/retry-30min-queue',
    'retry_45': 'https://sqs.us-east-1.amazonaws.com/123456/retry-45min-queue',
    'retry_60': 'https://sqs.us-east-1.amazonaws.com/123456/retry-60min-queue',
    'dlq': 'https://sqs.us-east-1.amazonaws.com/123456/dead-letter-queue'
}

RETRY_DELAYS = {
    0: 0,      # Immediate
    1: 15,     # 15 minutes
    2: 30,     # 30 minutes
    3: 45,     # 45 minutes
    4: 60      # 60 minutes
}

MAX_RETRIES = 5

def lambda_handler(event, context):
    """
    Main processor function - handles messages from all queues
    """
    for record in event['Records']:
        message_body = json.loads(record['body'])
        receipt_handle = record['receiptHandle']
        queue_url = extract_queue_url(record)
        
        try:
            # Process the message
            success = process_message(message_body)
            
            if success:
                # Delete from current queue
                delete_message(queue_url, receipt_handle)
                update_state(message_body['messageId'], 'SUCCESS')
            else:
                # Handle retry logic
                handle_retry(message_body, queue_url, receipt_handle)
                
        except Exception as e:
            print(f"Error processing message: {e}")
            handle_retry(message_body, queue_url, receipt_handle)


def process_message(message_body):
    """
    Your business logic here
    Returns: True if successful, False if needs retry
    """
    try:
        # Simulate processing
        message_id = message_body['messageId']
        data = message_body['data']
        
        # Your actual processing logic
        result = perform_business_logic(data)
        
        return result
    except Exception as e:
        print(f"Processing error: {e}")
        return False


def handle_retry(message_body, current_queue_url, receipt_handle):
    """
    Determines retry logic based on retry count
    """
    message_id = message_body['messageId']
    
    # Get current state from DynamoDB
    response = table.get_item(Key={'messageId': message_id})
    
    if 'Item' in response:
        retry_count = response['Item']['retryCount']
    else:
        retry_count = 0
        # Create initial state
        create_initial_state(message_body)
    
    retry_count += 1
    
    if retry_count >= MAX_RETRIES:
        # Move to Dead Letter Queue
        send_to_dlq(message_body, retry_count)
        delete_message(current_queue_url, receipt_handle)
        update_state(message_id, 'FAILED', retry_count)
    else:
        # Route to appropriate retry queue
        next_queue = determine_next_queue(retry_count)
        send_to_retry_queue(message_body, next_queue, retry_count)
        delete_message(current_queue_url, receipt_handle)
        update_retry_state(message_id, retry_count)


def determine_next_queue(retry_count):
    """
    Routes message to appropriate delay queue
    
    Retry 1: 15-min queue (processes after 15 min total)
    Retry 2: 30-min queue (processes after 30 min total)
    Retry 3: 45-min queue (processes after 45 min total)
    Retry 4: 60-min queue (processes after 60 min total)
    """
    queue_mapping = {
        1: 'retry_15',
        2: 'retry_30',
        3: 'retry_45',
        4: 'retry_60'
    }
    return QUEUES[queue_mapping.get(retry_count, 'dlq')]


def send_to_retry_queue(message_body, queue_url, retry_count):
    """
    Sends message to retry queue with updated metadata
    """
    message_body['retryCount'] = retry_count
    message_body['retryTimestamp'] = datetime.now().isoformat()
    
    sqs.send_message(
        QueueUrl=queue_url,
        MessageBody=json.dumps(message_body),
        MessageAttributes={
            'RetryCount': {
                'StringValue': str(retry_count),
                'DataType': 'Number'
            },
            'OriginalTimestamp': {
                'StringValue': message_body.get('originalTimestamp', ''),
                'DataType': 'String'
            }
        }
    )


def send_to_dlq(message_body, retry_count):
    """
    Sends message to Dead Letter Queue after max retries
    """
    dlq_message = {
        'originalMessage': message_body,
        'finalRetryCount': retry_count,
        'failureTimestamp': datetime.now().isoformat(),
        'reason': 'MAX_RETRIES_EXCEEDED'
    }
    
    sqs.send_message(
        QueueUrl=QUEUES['dlq'],
        MessageBody=json.dumps(dlq_message)
    )


def update_state(message_id, status, retry_count=0):
    """
    Updates processing state in DynamoDB
    """
    table.update_item(
        Key={'messageId': message_id},
        UpdateExpression='SET #status = :status, retryCount = :count, lastAttemptTimestamp = :timestamp',
        ExpressionAttributeNames={'#status': 'status'},
        ExpressionAttributeValues={
            ':status': status,
            ':count': retry_count,
            ':timestamp': int(datetime.now().timestamp())
        }
    )


def update_retry_state(message_id, retry_count):
    """
    Updates state for retry attempts
    """
    next_delay = RETRY_DELAYS.get(retry_count, 0)
    next_attempt = datetime.now() + timedelta(minutes=next_delay)
    
    table.update_item(
        Key={'messageId': message_id},
        UpdateExpression='SET retryCount = :count, nextAttemptTimestamp = :next, #status = :status',
        ExpressionAttributeNames={'#status': 'status'},
        ExpressionAttributeValues={
            ':count': retry_count,
            ':next': int(next_attempt.timestamp()),
            ':status': 'PENDING_RETRY'
        }
    )


def delete_message(queue_url, receipt_handle):
    """
    Deletes message from queue after processing
    """
    sqs.delete_message(
        QueueUrl=queue_url,
        ReceiptHandle=receipt_handle
    )


def create_initial_state(message_body):
    """
    Creates initial state record in DynamoDB
    """
    message_id = message_body['messageId']
    current_time = int(datetime.now().timestamp())
    
    table.put_item(
        Item={
            'messageId': message_id,
            'retryCount': 0,
            'status': 'PROCESSING',
            'originalPayload': message_body,
            'createdAt': current_time,
            'lastAttemptTimestamp': current_time,
            'ttl': current_time + (30 * 24 * 60 * 60)  # 30 days TTL
        }
    )
```

---

## Workflow Execution Timeline

### Example: Message Processing Flow

```
Time: 00:00 - Message arrives in Primary Queue
             └─► Processor attempts #1 → FAILS
                 └─► Send to 15-Min Retry Queue (delay: 15 min)

Time: 00:15 - Message becomes visible in 15-Min Queue
             └─► Processor attempts #2 → FAILS
                 └─► Send to 30-Min Queue (delay: 15 min)

Time: 00:30 - Message becomes visible in 30-Min Queue
             └─► Processor attempts #3 → FAILS
                 └─► Send to 45-Min Queue (delay: 15 min)

Time: 00:45 - Message becomes visible in 45-Min Queue
             └─► Processor attempts #4 → FAILS
                 └─► Send to 60-Min Queue (delay: 15 min)

Time: 01:00 - Message becomes visible in 60-Min Queue
             └─► Processor attempts #5 → FAILS
                 └─► Move to Dead Letter Queue
                     └─► Alert/Manual Investigation
```

---

## Alternative Approach: EventBridge + Step Functions

### For More Complex Delay Requirements

```
┌──────────────┐
│   Producer   │
└──────┬───────┘
       │
       ▼
┌─────────────────────┐
│  EventBridge Rule   │
│  (Initial Trigger)  │
└──────┬──────────────┘
       │
       ▼
┌─────────────────────────────────────────┐
│         Step Functions State Machine     │
│                                          │
│  ┌────────────────────────────────────┐ │
│  │  1. Process Record                 │ │
│  └────────┬───────────────────────────┘ │
│           │                              │
│  ┌────────▼────────────┐                │
│  │  Success?           │                │
│  └────┬─────────┬──────┘                │
│       │         │                        │
│      Yes        No                       │
│       │         │                        │
│       │    ┌────▼──────────────┐        │
│       │    │  Wait 15 Minutes  │        │
│       │    └────┬──────────────┘        │
│       │         │                        │
│       │    ┌────▼──────────────┐        │
│       │    │  Retry Attempt    │        │
│       │    └────┬──────────────┘        │
│       │         │                        │
│       │    (Repeat with 30, 45, 60 min) │
│       │         │                        │
│       │    ┌────▼──────────────┐        │
│       │    │  Max Retries?     │        │
│       │    └────┬─────────┬────┘        │
│       │         │         │             │
│       │        Yes       No             │
│       │         │         └─► DLQ       │
│       │         │                        │
│  ┌────▼─────────▼────┐                  │
│  │     Complete      │                  │
│  └───────────────────┘                  │
└─────────────────────────────────────────┘
```

#### Step Functions Definition (Simplified)

```json
{
  "Comment": "Delayed Retry Processing",
  "StartAt": "ProcessRecord",
  "States": {
    "ProcessRecord": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:us-east-1:123456:function:ProcessRecord",
      "Catch": [{
        "ErrorEquals": ["States.ALL"],
        "Next": "CheckRetryCount"
      }],
      "Next": "Success"
    },
    "CheckRetryCount": {
      "Type": "Choice",
      "Choices": [
        {
          "Variable": "$.retryCount",
          "NumericEquals": 0,
          "Next": "Wait15Minutes"
        },
        {
          "Variable": "$.retryCount",
          "NumericEquals": 1,
          "Next": "Wait30Minutes"
        },
        {
          "Variable": "$.retryCount",
          "NumericEquals": 2,
          "Next": "Wait45Minutes"
        },
        {
          "Variable": "$.retryCount",
          "NumericEquals": 3,
          "Next": "Wait60Minutes"
        }
      ],
      "Default": "MoveToDLQ"
    },
    "Wait15Minutes": {
      "Type": "Wait",
      "Seconds": 900,
      "Next": "IncrementRetry"
    },
    "Wait30Minutes": {
      "Type": "Wait",
      "Seconds": 1800,
      "Next": "IncrementRetry"
    },
    "Wait45Minutes": {
      "Type": "Wait",
      "Seconds": 2700,
      "Next": "IncrementRetry"
    },
    "Wait60Minutes": {
      "Type": "Wait",
      "Seconds": 3600,
      "Next": "IncrementRetry"
    },
    "IncrementRetry": {
      "Type": "Pass",
      "Parameters": {
        "retryCount.$": "States.MathAdd($.retryCount, 1)",
        "data.$": "$.data"
      },
      "Next": "ProcessRecord"
    },
    "MoveToDLQ": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:us-east-1:123456:function:MoveToDLQ",
      "Next": "Failed"
    },
    "Success": {
      "Type": "Succeed"
    },
    "Failed": {
      "Type": "Fail"
    }
  }
}
```

---

## Scaling Considerations

### 1. **Throughput Scaling**

```
Component          | Scaling Strategy
-------------------|--------------------------------------------------
SQS Queues         | Unlimited throughput (Standard Queue)
                   | Auto-scales with load
-------------------|--------------------------------------------------
Lambda Workers     | Concurrent executions: 1000 (default)
                   | Reserved concurrency per function
                   | Batch size: 1-10 messages
-------------------|--------------------------------------------------
DynamoDB           | On-demand capacity mode (auto-scaling)
                   | Or Provisioned: Set RCU/WCU with auto-scaling
-------------------|--------------------------------------------------
EventBridge        | Soft limit: 10,000 invocations/second/region
```

### 2. **Cost Optimization**

```
Strategy                          | Savings
----------------------------------|----------------------------------------
Use Long Polling (20s)            | Reduce empty receives by 90%
Batch Operations                  | Process 10 messages at once
DynamoDB On-Demand                | Pay only for actual usage
Lambda Reserved Concurrency       | Predictable costs for steady workload
Standard Queue vs FIFO            | Standard is cheaper if order not needed
Message Batching                  | Up to 10 messages per API call
```

### 3. **Monitoring Metrics**

```yaml
CloudWatch Metrics:
  SQS:
    - ApproximateNumberOfMessagesVisible
    - ApproximateNumberOfMessagesDelayed
    - ApproximateAgeOfOldestMessage
    - NumberOfMessagesSent
    - NumberOfMessagesReceived
    - NumberOfMessagesDeleted
    
  Lambda:
    - Invocations
    - Errors
    - Duration
    - ConcurrentExecutions
    - Throttles
    
  DynamoDB:
    - ConsumedReadCapacityUnits
    - ConsumedWriteCapacityUnits
    - UserErrors
    - SystemErrors
    
  Custom:
    - RetryCount per message
    - Success rate per retry stage
    - End-to-end processing time
    - DLQ message count
```

---

## Best Practices

### 1. **Idempotency**
```python
def process_message_idempotent(message_id, data):
    """
    Ensure processing is idempotent
    Check if already processed before executing
    """
    # Check DynamoDB for existing result
    response = table.get_item(Key={'messageId': message_id})
    
    if 'Item' in response and response['Item']['status'] == 'SUCCESS':
        # Already processed, skip
        return True
    
    # Process and store result atomically
    result = perform_operation(data)
    
    # Use conditional write to prevent race conditions
    table.put_item(
        Item={
            'messageId': message_id,
            'status': 'SUCCESS',
            'result': result
        },
        ConditionExpression='attribute_not_exists(messageId) OR #status <> :success',
        ExpressionAttributeNames={'#status': 'status'},
        ExpressionAttributeValues={':success': 'SUCCESS'}
    )
    
    return True
```

### 2. **Visibility Timeout Management**
```python
def extend_visibility_timeout(queue_url, receipt_handle, additional_seconds):
    """
    Extend visibility timeout for long-running tasks
    """
    sqs.change_message_visibility(
        QueueUrl=queue_url,
        ReceiptHandle=receipt_handle,
        VisibilityTimeout=additional_seconds
    )
```

### 3. **Batch Processing**
```python
def batch_receive_messages(queue_url, max_messages=10):
    """
    Receive multiple messages in one API call
    """
    response = sqs.receive_message(
        QueueUrl=queue_url,
        MaxNumberOfMessages=max_messages,  # 1-10
        WaitTimeSeconds=20,  # Long polling
        MessageAttributeNames=['All']
    )
    
    return response.get('Messages', [])
```

### 4. **Error Handling**
```python
def process_with_error_tracking(message_body):
    """
    Track error details for debugging
    """
    try:
        result = process_message(message_body)
        return result
    except Exception as e:
        # Log error details
        error_info = {
            'error_type': type(e).__name__,
            'error_message': str(e),
            'timestamp': datetime.now().isoformat(),
            'stack_trace': traceback.format_exc()
        }
        
        # Store in DynamoDB for analysis
        table.update_item(
            Key={'messageId': message_body['messageId']},
            UpdateExpression='SET errorHistory = list_append(if_not_exists(errorHistory, :empty), :error)',
            ExpressionAttributeValues={
                ':error': [error_info],
                ':empty': []
            }
        )
        
        raise
```

### 5. **Dead Letter Queue Monitoring**
```python
def monitor_dlq():
    """
    Set up CloudWatch alarm for DLQ messages
    """
    cloudwatch = boto3.client('cloudwatch')
    
    cloudwatch.put_metric_alarm(
        AlarmName='SQS-DLQ-Messages-Alert',
        ComparisonOperator='GreaterThanThreshold',
        EvaluationPeriods=1,
        MetricName='ApproximateNumberOfMessagesVisible',
        Namespace='AWS/SQS',
        Period=300,
        Statistic='Average',
        Threshold=10,
        ActionsEnabled=True,
        AlarmActions=['arn:aws:sns:us-east-1:123456:AlertTopic'],
        Dimensions=[
            {
                'Name': 'QueueName',
                'Value': 'dead-letter-queue'
            }
        ]
    )
```

### 6. **Message Deduplication**
```python
def send_message_with_deduplication(queue_url, message_body):
    """
    Use content-based deduplication for FIFO queues
    """
    import hashlib
    
    # Generate deduplication ID from content
    content_hash = hashlib.sha256(
        json.dumps(message_body, sort_keys=True).encode()
    ).hexdigest()
    
    sqs.send_message(
        QueueUrl=queue_url,
        MessageBody=json.dumps(message_body),
        MessageDeduplicationId=content_hash[:128],  # Max 128 chars
        MessageGroupId='default-group'  # Required for FIFO
    )
```

---

## Infrastructure as Code (Terraform)

```hcl
# Primary Queue
resource "aws_sqs_queue" "primary_queue" {
  name                       = "primary-processing-queue"
  delay_seconds              = 0
  max_message_size           = 262144  # 256 KB
  message_retention_seconds  = 1209600  # 14 days
  receive_wait_time_seconds  = 20  # Long polling
  visibility_timeout_seconds = 300  # 5 minutes

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.dlq.arn
    maxReceiveCount     = 5
  })

  tags = {
    Environment = "production"
    Purpose     = "delayed-processing"
  }
}

# 15-Minute Retry Queue
resource "aws_sqs_queue" "retry_15min_queue" {
  name                       = "retry-15min-queue"
  delay_seconds              = 900  # 15 minutes
  visibility_timeout_seconds = 300
  message_retention_seconds  = 1209600

  tags = {
    RetryStage = "15min"
  }
}

# 30-Minute Retry Queue
resource "aws_sqs_queue" "retry_30min_queue" {
  name                       = "retry-30min-queue"
  delay_seconds              = 900  # 15 minutes (cumulative delay)
  visibility_timeout_seconds = 300
  message_retention_seconds  = 1209600

  tags = {
    RetryStage = "30min"
  }
}

# 45-Minute Retry Queue
resource "aws_sqs_queue" "retry_45min_queue" {
  name                       = "retry-45min-queue"
  delay_seconds              = 900
  visibility_timeout_seconds = 300
  message_retention_seconds  = 1209600

  tags = {
    RetryStage = "45min"
  }
}

# 60-Minute Retry Queue
resource "aws_sqs_queue" "retry_60min_queue" {
  name                       = "retry-60min-queue"
  delay_seconds              = 900
  visibility_timeout_seconds = 300
  message_retention_seconds  = 1209600

  tags = {
    RetryStage = "60min"
  }
}

# Dead Letter Queue
resource "aws_sqs_queue" "dlq" {
  name                      = "processing-dead-letter-queue"
  message_retention_seconds = 1209600  # 14 days

  tags = {
    Purpose = "dead-letter-queue"
  }
}

# DynamoDB State Table
resource "aws_dynamodb_table" "processing_state" {
  name           = "MessageProcessingState"
  billing_mode   = "PAY_PER_REQUEST"
  hash_key       = "messageId"

  attribute {
    name = "messageId"
    type = "S"
  }

  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  tags = {
    Purpose = "processing-state-management"
  }
}

# Lambda Function
resource "aws_lambda_function" "processor" {
  filename      = "processor.zip"
  function_name = "message-processor"
  role          = aws_iam_role.lambda_role.arn
  handler       = "index.lambda_handler"
  runtime       = "python3.11"
  timeout       = 300
  memory_size   = 512

  environment {
    variables = {
      PRIMARY_QUEUE_URL    = aws_sqs_queue.primary_queue.url
      RETRY_15MIN_QUEUE    = aws_sqs_queue.retry_15min_queue.url
      RETRY_30MIN_QUEUE    = aws_sqs_queue.retry_30min_queue.url
      RETRY_45MIN_QUEUE    = aws_sqs_queue.retry_45min_queue.url
      RETRY_60MIN_QUEUE    = aws_sqs_queue.retry_60min_queue.url
      DLQ_URL              = aws_sqs_queue.dlq.url
      STATE_TABLE_NAME     = aws_dynamodb_table.processing_state.name
    }
  }
}

# Lambda Event Source Mappings
resource "aws_lambda_event_source_mapping" "primary_queue_trigger" {
  event_source_arn = aws_sqs_queue.primary_queue.arn
  function_name    = aws_lambda_function.processor.arn
  batch_size       = 10
  enabled          = true
}

resource "aws_lambda_event_source_mapping" "retry_15min_trigger" {
  event_source_arn = aws_sqs_queue.retry_15min_queue.arn
  function_name    = aws_lambda_function.processor.arn
  batch_size       = 10
}

resource "aws_lambda_event_source_mapping" "retry_30min_trigger" {
  event_source_arn = aws_sqs_queue.retry_30min_queue.arn
  function_name    = aws_lambda_function.processor.arn
  batch_size       = 10
}

resource "aws_lambda_event_source_mapping" "retry_45min_trigger" {
  event_source_arn = aws_sqs_queue.retry_45min_queue.arn
  function_name    = aws_lambda_function.processor.arn
  batch_size       = 10
}

resource "aws_lambda_event_source_mapping" "retry_60min_trigger" {
  event_source_arn = aws_sqs_queue.retry_60min_queue.arn
  function_name    = aws_lambda_function.processor.arn
  batch_size       = 10
}
```

---

## Comparison: SQS Multi-Queue vs Step Functions

| Aspect | Multi-Queue Approach | Step Functions Approach |
|--------|---------------------|------------------------|
| **Cost** | Lower (SQS + Lambda) | Higher (Step Functions execution cost) |
| **Complexity** | Medium (queue management) | Low (visual workflow) |
| **Delay Precision** | 15-min granularity | Exact delays possible |
| **Max Delay** | Unlimited (chain queues) | 1 year per wait state |
| **State Management** | Manual (DynamoDB) | Built-in state management |
| **Monitoring** | CloudWatch metrics | Built-in execution history |
| **Scalability** | Very High | High (4000 exec/s per account) |
| **Best For** | High-throughput, cost-sensitive | Complex workflows, audit trails |

---

## Conclusion

The **Multi-Queue SQS Architecture** provides a scalable, cost-effective solution for delayed record processing with progressive retry intervals:

✅ **Leverages SQS Features**: Delay queues, visibility timeout, DLQs  
✅ **Handles Long Delays**: Chains 15-minute delays for 30, 45, 60-minute delays  
✅ **Maintains State**: DynamoDB tracks retry counts and processing status  
✅ **Highly Scalable**: Auto-scales with message volume  
✅ **Cost-Effective**: Pay only for messages processed  
✅ **Fault-Tolerant**: DLQ captures failed messages for investigation  

This architecture ensures reliable message processing with automatic retries at specified intervals, making it ideal for scenarios like payment retries, notification systems, and distributed task processing.
