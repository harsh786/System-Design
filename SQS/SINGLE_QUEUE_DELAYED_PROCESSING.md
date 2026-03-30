# Delayed Record Processing with a Single SQS Queue

## Overview
This document explains how to implement delayed record processing using only a single AWS SQS queue. The solution leverages per-message delay and visibility timeout to achieve progressive retry intervals (15, 30, 45, 60 minutes) without the need for multiple queues.

---

## Key SQS Features Used

- **Per-Message Delay**: Each message can be sent with a delay of up to 15 minutes before it becomes visible in the queue.
- **Visibility Timeout**: After a message is received, it becomes invisible for a specified period (up to 12 hours). If not deleted, it reappears for reprocessing.

---

## Architecture

### Flow Diagram
```
┌──────────────┐
│   Producer   │
└──────┬───────┘
       │
       ▼
┌─────────────────────┐
│   SQS Queue         │
└──────┬──────────────┘
       │
       ▼
┌─────────────────────┐
│ Lambda/Worker       │
│ Processor           │
└──────┬──────────────┘
       │
       ▼
┌─────────────────────┐
│ DynamoDB (State)    │
└─────────────────────┘
```

---

## Processing Logic

1. **Initial Attempt**: Message is processed immediately.
2. **On Failure**: The processor increases the retry count and re-sends the message to the same queue with a per-message delay (up to 15 minutes).
3. **For Delays > 15 Minutes**: Use visibility timeout to hide the message for the required delay period.
4. **State Tracking**: Use DynamoDB to track retry count and next attempt time for each message.
5. **Max Retries**: After the final attempt (e.g., 5th), move the message to a Dead Letter Queue (DLQ).

---

## Example Implementation (Python/Pseudocode)

```python
import boto3
import json
from datetime import datetime, timedelta

sqs = boto3.client('sqs')
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('MessageProcessingState')

QUEUE_URL = 'https://sqs.us-east-1.amazonaws.com/123456789012/my-queue'
DLQ_URL = 'https://sqs.us-east-1.amazonaws.com/123456789012/my-dlq'

RETRY_DELAYS = [0, 15, 30, 45, 60]  # in minutes
MAX_RETRIES = 5


def lambda_handler(event, context):
    for record in event['Records']:
        message_body = json.loads(record['body'])
        receipt_handle = record['receiptHandle']
        message_id = message_body['messageId']

        # Get retry state
        state = table.get_item(Key={'messageId': message_id}).get('Item', {})
        retry_count = state.get('retryCount', 0)

        try:
            success = process_message(message_body)
            if success:
                sqs.delete_message(QueueUrl=QUEUE_URL, ReceiptHandle=receipt_handle)
                table.update_item(
                    Key={'messageId': message_id},
                    UpdateExpression='SET #status = :s',
                    ExpressionAttributeNames={'#status': 'status'},
                    ExpressionAttributeValues={':s': 'SUCCESS'}
                )
            else:
                handle_retry(message_body, receipt_handle, retry_count)
        except Exception as e:
            handle_retry(message_body, receipt_handle, retry_count)


def process_message(message_body):
    # ...business logic...
    return False  # Simulate failure for demonstration


def handle_retry(message_body, receipt_handle, retry_count):
    """
    Handle retry logic with safety mechanisms for re-queue failures.
    Key principle: Never delete the message until re-queue operation succeeds.
    """
    retry_count += 1
    message_id = message_body['messageId']
    
    if retry_count >= MAX_RETRIES:
        # Move to DLQ with error handling
        try:
            sqs.send_message(QueueUrl=DLQ_URL, MessageBody=json.dumps(message_body))
            # Only delete after successful DLQ insertion
            sqs.delete_message(QueueUrl=QUEUE_URL, ReceiptHandle=receipt_handle)
            table.update_item(
                Key={'messageId': message_id},
                UpdateExpression='SET #status = :s, retryCount = :c',
                ExpressionAttributeNames={'#status': 'status'},
                ExpressionAttributeValues={':s': 'FAILED', ':c': retry_count}
            )
        except Exception as e:
            print(f"Failed to move to DLQ: {e}. Message will reappear.")
            # Don't delete - message will automatically reappear after visibility timeout
            log_requeue_failure(message_id, retry_count, str(e))
    else:
        delay = RETRY_DELAYS[retry_count]
        
        try:
            if delay <= 15:
                # Use per-message delay - send new message with delay
                sqs.send_message(
                    QueueUrl=QUEUE_URL,
                    MessageBody=json.dumps(message_body),
                    DelaySeconds=delay * 60,
                    MessageAttributes={
                        'RetryCount': {'StringValue': str(retry_count), 'DataType': 'Number'}
                    }
                )
                # Only delete original message after successful re-queue
                sqs.delete_message(QueueUrl=QUEUE_URL, ReceiptHandle=receipt_handle)
            else:
                # Use visibility timeout for >15 min - no need to delete
                sqs.change_message_visibility(
                    QueueUrl=QUEUE_URL,
                    ReceiptHandle=receipt_handle,
                    VisibilityTimeout=delay * 60
                )
            
            # Update state only after successful queue operation
            table.update_item(
                Key={'messageId': message_id},
                UpdateExpression='SET retryCount = :c, #status = :s, lastAttempt = :t',
                ExpressionAttributeNames={'#status': 'status'},
                ExpressionAttributeValues={
                    ':c': retry_count, 
                    ':s': 'PENDING_RETRY',
                    ':t': int(datetime.now().timestamp())
                }
            )
        except Exception as e:
            print(f"Re-queue failed: {e}. Message will reappear after visibility timeout.")
            # Critical: Don't delete the message
            # It will automatically reappear after the current visibility timeout expires
            log_requeue_failure(message_id, retry_count, str(e))


def log_requeue_failure(message_id, retry_count, error):
    """Log re-queue failures for monitoring and recovery"""
    try:
        table.update_item(
            Key={'messageId': message_id},
            UpdateExpression='SET requeueFailures = if_not_exists(requeueFailures, :zero) + :one, lastError = :err, lastErrorTime = :t',
            ExpressionAttributeValues={
                ':zero': 0,
                ':one': 1,
                ':err': error,
                ':t': int(datetime.now().timestamp())
            }
        )
        # Publish CloudWatch metric
        cloudwatch = boto3.client('cloudwatch')
        cloudwatch.put_metric_data(
            Namespace='CustomMetrics/SQS',
            MetricData=[{'MetricName': 'RequeueFailures', 'Value': 1, 'Unit': 'Count'}]
        )
    except:
        pass  # Best effort logging
```

---

## Handling Re-Queue Failures

### Problem
What happens if the message fails to be inserted back into the queue during a retry attempt? This could occur due to:
- Network issues
- SQS service unavailability
- Throttling limits
- Permission errors

### Solution Strategies

#### 1. **Visibility Timeout Extension (Recommended)**
Don't delete the message immediately. Instead, extend its visibility timeout. If re-queuing fails, the message will automatically reappear in the queue.

```python
def handle_retry_with_safety(message_body, receipt_handle, retry_count):
    retry_count += 1
    message_id = message_body['messageId']
    
    if retry_count >= MAX_RETRIES:
        # Move to DLQ with retry logic
        try:
            sqs.send_message(QueueUrl=DLQ_URL, MessageBody=json.dumps(message_body))
            sqs.delete_message(QueueUrl=QUEUE_URL, ReceiptHandle=receipt_handle)
        except Exception as e:
            print(f"Failed to move to DLQ: {e}")
            # Don't delete - message will reappear and retry again
            update_state_with_error(message_id, retry_count, str(e))
    else:
        delay = RETRY_DELAYS[retry_count]
        
        try:
            if delay <= 15:
                # Per-message delay approach
                sqs.send_message(
                    QueueUrl=QUEUE_URL,
                    MessageBody=json.dumps(message_body),
                    DelaySeconds=delay * 60,
                    MessageAttributes={
                        'RetryCount': {
                            'StringValue': str(retry_count),
                            'DataType': 'Number'
                        }
                    }
                )
                # Only delete after successful re-queue
                sqs.delete_message(QueueUrl=QUEUE_URL, ReceiptHandle=receipt_handle)
            else:
                # Visibility timeout approach
                sqs.change_message_visibility(
                    QueueUrl=QUEUE_URL,
                    ReceiptHandle=receipt_handle,
                    VisibilityTimeout=delay * 60
                )
            
            # Update state only after successful queue operation
            table.update_item(
                Key={'messageId': message_id},
                UpdateExpression='SET retryCount = :c, #status = :s, lastAttempt = :t',
                ExpressionAttributeNames={'#status': 'status'},
                ExpressionAttributeValues={
                    ':c': retry_count, 
                    ':s': 'PENDING_RETRY',
                    ':t': int(datetime.now().timestamp())
                }
            )
            
        except Exception as e:
            print(f"Failed to re-queue message: {e}")
            # DON'T delete the message - let it reappear
            # Log the error in DynamoDB for monitoring
            try:
                table.update_item(
                    Key={'messageId': message_id},
                    UpdateExpression='SET requeueFailures = if_not_exists(requeueFailures, :zero) + :one, lastError = :err',
                    ExpressionAttributeValues={
                        ':zero': 0,
                        ':one': 1,
                        ':err': str(e)
                    }
                )
            except:
                pass  # Best effort logging
            
            # Message will reappear after current visibility timeout expires
```

#### 2. **Transactional State Management**
Use DynamoDB as the source of truth. If re-queuing fails, the state remains unchanged, and a separate recovery process can handle it.

```python
def handle_retry_transactional(message_body, receipt_handle, retry_count):
    retry_count += 1
    message_id = message_body['messageId']
    delay = RETRY_DELAYS[retry_count] if retry_count < MAX_RETRIES else None
    
    # Step 1: Update state FIRST (source of truth)
    try:
        table.update_item(
            Key={'messageId': message_id},
            UpdateExpression='SET retryCount = :c, #status = :s, nextRetryTime = :nrt, receiptHandle = :rh',
            ExpressionAttributeNames={'#status': 'status'},
            ExpressionAttributeValues={
                ':c': retry_count,
                ':s': 'PENDING_RETRY' if retry_count < MAX_RETRIES else 'FAILED',
                ':nrt': int((datetime.now() + timedelta(minutes=delay or 0)).timestamp()),
                ':rh': receipt_handle
            }
        )
    except Exception as e:
        print(f"Failed to update state: {e}")
        # Don't delete message - will retry entire flow
        return
    
    # Step 2: Try to re-queue
    try:
        if retry_count >= MAX_RETRIES:
            sqs.send_message(QueueUrl=DLQ_URL, MessageBody=json.dumps(message_body))
            sqs.delete_message(QueueUrl=QUEUE_URL, ReceiptHandle=receipt_handle)
        elif delay <= 15:
            sqs.send_message(
                QueueUrl=QUEUE_URL,
                MessageBody=json.dumps(message_body),
                DelaySeconds=delay * 60
            )
            sqs.delete_message(QueueUrl=QUEUE_URL, ReceiptHandle=receipt_handle)
        else:
            sqs.change_message_visibility(
                QueueUrl=QUEUE_URL,
                ReceiptHandle=receipt_handle,
                VisibilityTimeout=delay * 60
            )
    except Exception as e:
        print(f"Re-queue failed: {e}")
        # State is already updated in DynamoDB
        # Recovery process will handle orphaned messages
        table.update_item(
            Key={'messageId': message_id},
            UpdateExpression='SET requeueFailed = :true, lastError = :err',
            ExpressionAttributeValues={
                ':true': True,
                ':err': str(e)
            }
        )
```

#### 3. **Recovery Process for Orphaned Messages**
Run a periodic Lambda that checks DynamoDB for messages that failed to re-queue.

```python
def recovery_process(event, context):
    """
    Periodic Lambda (e.g., every 5 minutes) to recover orphaned messages
    """
    # Scan for messages that failed to re-queue
    response = table.scan(
        FilterExpression='requeueFailed = :true AND #status = :status',
        ExpressionAttributeNames={'#status': 'status'},
        ExpressionAttributeValues={
            ':true': True,
            ':status': 'PENDING_RETRY'
        }
    )
    
    for item in response.get('Items', []):
        message_id = item['messageId']
        retry_count = item['retryCount']
        next_retry_time = item.get('nextRetryTime', 0)
        
        # Check if it's time to retry
        if datetime.now().timestamp() >= next_retry_time:
            try:
                # Reconstruct message and re-queue
                message_body = item['originalPayload']
                delay = max(0, RETRY_DELAYS[retry_count] - 
                           int((datetime.now().timestamp() - next_retry_time) / 60))
                
                if delay <= 15:
                    sqs.send_message(
                        QueueUrl=QUEUE_URL,
                        MessageBody=json.dumps(message_body),
                        DelaySeconds=delay * 60
                    )
                else:
                    # Send immediately with adjusted visibility
                    sqs.send_message(
                        QueueUrl=QUEUE_URL,
                        MessageBody=json.dumps(message_body),
                        DelaySeconds=0
                    )
                
                # Clear the failed flag
                table.update_item(
                    Key={'messageId': message_id},
                    UpdateExpression='REMOVE requeueFailed, lastError',
                )
                
                print(f"Recovered message: {message_id}")
                
            except Exception as e:
                print(f"Recovery failed for {message_id}: {e}")
                # Will retry on next run
```

#### 4. **Exponential Backoff for Re-Queue Attempts**
If re-queuing fails, implement exponential backoff before the message reappears.

```python
def handle_retry_with_backoff(message_body, receipt_handle, retry_count):
    retry_count += 1
    message_id = message_body['messageId']
    
    # Track re-queue failures
    state = table.get_item(Key={'messageId': message_id}).get('Item', {})
    requeue_failures = state.get('requeueFailures', 0)
    
    # Calculate backoff: 30s, 60s, 120s, 240s, etc.
    backoff_seconds = min(30 * (2 ** requeue_failures), 900)  # Max 15 minutes
    
    try:
        delay = RETRY_DELAYS[retry_count] if retry_count < MAX_RETRIES else 0
        
        if retry_count >= MAX_RETRIES:
            sqs.send_message(QueueUrl=DLQ_URL, MessageBody=json.dumps(message_body))
            sqs.delete_message(QueueUrl=QUEUE_URL, ReceiptHandle=receipt_handle)
        elif delay <= 15:
            sqs.send_message(
                QueueUrl=QUEUE_URL,
                MessageBody=json.dumps(message_body),
                DelaySeconds=delay * 60
            )
            sqs.delete_message(QueueUrl=QUEUE_URL, ReceiptHandle=receipt_handle)
        else:
            sqs.change_message_visibility(
                QueueUrl=QUEUE_URL,
                ReceiptHandle=receipt_handle,
                VisibilityTimeout=delay * 60
            )
        
        # Reset requeue failure counter on success
        table.update_item(
            Key={'messageId': message_id},
            UpdateExpression='SET retryCount = :c, requeueFailures = :zero',
            ExpressionAttributeValues={':c': retry_count, ':zero': 0}
        )
        
    except Exception as e:
        print(f"Re-queue attempt failed (attempt #{requeue_failures + 1}): {e}")
        
        # Don't delete message - extend visibility with backoff
        try:
            sqs.change_message_visibility(
                QueueUrl=QUEUE_URL,
                ReceiptHandle=receipt_handle,
                VisibilityTimeout=backoff_seconds
            )
            
            # Increment requeue failure counter
            table.update_item(
                Key={'messageId': message_id},
                UpdateExpression='SET requeueFailures = if_not_exists(requeueFailures, :zero) + :one',
                ExpressionAttributeValues={':zero': 0, ':one': 1}
            )
        except:
            # If even visibility timeout extension fails, message will reappear
            # after default visibility timeout
            pass
```

#### 5. **CloudWatch Alarms for Monitoring**
Set up alarms to detect re-queue failures:

```python
def setup_requeue_failure_alarm():
    cloudwatch = boto3.client('cloudwatch')
    
    # Create custom metric for re-queue failures
    cloudwatch.put_metric_alarm(
        AlarmName='SQS-Requeue-Failures',
        ComparisonOperator='GreaterThanThreshold',
        EvaluationPeriods=1,
        MetricName='RequeueFailures',
        Namespace='CustomMetrics/SQS',
        Period=300,
        Statistic='Sum',
        Threshold=10,
        ActionsEnabled=True,
        AlarmActions=['arn:aws:sns:us-east-1:123456:AlertTopic'],
        AlarmDescription='Alert when message re-queue operations fail'
    )

def publish_requeue_failure_metric():
    """Call this when re-queue fails"""
    cloudwatch = boto3.client('cloudwatch')
    cloudwatch.put_metric_data(
        Namespace='CustomMetrics/SQS',
        MetricData=[
            {
                'MetricName': 'RequeueFailures',
                'Value': 1,
                'Unit': 'Count',
                'Timestamp': datetime.now()
            }
        ]
    )
```

### Best Practices for Re-Queue Safety

1. **Never delete before confirming re-queue success** - Always attempt the queue operation first
2. **Use visibility timeout as safety net** - If re-queue fails, message reappears automatically
3. **Implement idempotency** - Messages may be processed multiple times
4. **Log all failures** - Track re-queue failures in DynamoDB or CloudWatch
5. **Set up recovery process** - Periodic Lambda to handle orphaned messages
6. **Monitor metrics** - Alert on unusual re-queue failure rates
7. **Use exponential backoff** - Prevent overwhelming the system during outages
8. **Test failure scenarios** - Simulate SQS unavailability in testing

---

## Key Points
- **Single Queue**: All retries and delays are managed in one queue.
- **Per-Message Delay**: Used for up to 15 minutes.
- **Visibility Timeout**: Used for longer delays (30, 45, 60 minutes).
- **State Table**: DynamoDB tracks retry attempts and status.
- **DLQ**: Messages exceeding max retries are moved to a Dead Letter Queue.
- **Re-Queue Safety**: Never delete messages before confirming successful re-queue operations.

---

## Pros & Cons

| Pros                                   | Cons                                  |
|----------------------------------------|---------------------------------------|
| Simple queue management                | Visibility timeout can be tricky      |
| Lower operational overhead             | Potential for duplicate processing    |
| Cost-effective for moderate workloads  | Less granular control over delays     |
| Easy to monitor                        | All logic in processor code           |

---

## Best Practices
- Ensure message processing is idempotent.
- Monitor queue metrics and DLQ.
- Use CloudWatch alarms for failed messages.
- Tune visibility timeout based on processing time and delay requirements.

---

## Conclusion
This approach allows you to implement progressive delayed processing using a single SQS queue, leveraging per-message delay and visibility timeout. It is suitable for moderate workloads and simplifies queue management, but requires careful handling of visibility timeouts and state tracking.
