# Observability and CloudWatch for ML

## ML Observability Stack

```
What to monitor:
├── Infrastructure metrics (CPU, GPU, memory, disk)
├── Application metrics (latency p50/p95/p99, throughput, errors)
├── Model metrics (prediction distribution, confidence, drift)
├── Data metrics (input features distribution, missing rates)
└── Business metrics (conversion, revenue, engagement)
```

**The key insight:** Infrastructure can be healthy while the model is silently degrading. You MUST monitor at all five layers.

---

## CloudWatch for ML

### Custom Metrics (boto3)

```python
import boto3
import time
from datetime import datetime

cloudwatch = boto3.client('cloudwatch')

def emit_prediction_metrics(prediction, confidence, latency_ms, model_version):
    """Emit after every prediction."""
    cloudwatch.put_metric_data(
        Namespace='ML/TextClassifier',
        MetricData=[
            {
                'MetricName': 'PredictionConfidence',
                'Value': confidence,
                'Unit': 'None',
                'Dimensions': [
                    {'Name': 'ModelVersion', 'Value': model_version},
                    {'Name': 'Endpoint', 'Value': 'text-clf-prod'},
                ],
            },
            {
                'MetricName': 'PredictionLatency',
                'Value': latency_ms,
                'Unit': 'Milliseconds',
                'Dimensions': [
                    {'Name': 'ModelVersion', 'Value': model_version},
                ],
            },
            {
                'MetricName': 'PredictionClass',
                'Value': float(prediction),
                'Unit': 'None',
                'Dimensions': [
                    {'Name': 'ModelVersion', 'Value': model_version},
                ],
            },
        ],
    )

def emit_drift_score(drift_score, feature_name):
    """Emit from drift detection Lambda (runs hourly)."""
    cloudwatch.put_metric_data(
        Namespace='ML/TextClassifier',
        MetricData=[
            {
                'MetricName': 'DriftScore',
                'Value': drift_score,
                'Unit': 'None',
                'Dimensions': [
                    {'Name': 'Feature', 'Value': feature_name},
                ],
            },
        ],
    )
```

### Alarms

```python
def create_ml_alarms(endpoint_name, sns_topic_arn):
    cloudwatch = boto3.client('cloudwatch')
    
    # Alarm 1: High latency
    cloudwatch.put_metric_alarm(
        AlarmName=f'{endpoint_name}-high-latency',
        MetricName='ModelLatency',
        Namespace='AWS/SageMaker',
        Statistic='p95',  # Use extended statistic for percentiles
        Period=300,
        EvaluationPeriods=3,
        Threshold=500000,  # 500ms in microseconds
        ComparisonOperator='GreaterThanThreshold',
        Dimensions=[
            {'Name': 'EndpointName', 'Value': endpoint_name},
            {'Name': 'VariantName', 'Value': 'AllTraffic'},
        ],
        AlarmActions=[sns_topic_arn],
        AlarmDescription='P95 latency > 500ms for 15 minutes',
    )
    
    # Alarm 2: Error rate
    cloudwatch.put_metric_alarm(
        AlarmName=f'{endpoint_name}-high-errors',
        MetricName='Invocation5XXErrors',
        Namespace='AWS/SageMaker',
        Statistic='Sum',
        Period=300,
        EvaluationPeriods=2,
        Threshold=10,
        ComparisonOperator='GreaterThanThreshold',
        Dimensions=[
            {'Name': 'EndpointName', 'Value': endpoint_name},
            {'Name': 'VariantName', 'Value': 'AllTraffic'},
        ],
        AlarmActions=[sns_topic_arn],
        TreatMissingData='notBreaching',
    )
    
    # Alarm 3: Low confidence (model uncertainty)
    cloudwatch.put_metric_alarm(
        AlarmName=f'{endpoint_name}-low-confidence',
        MetricName='PredictionConfidence',
        Namespace='ML/TextClassifier',
        Statistic='Average',
        Period=3600,  # 1 hour
        EvaluationPeriods=3,
        Threshold=0.7,
        ComparisonOperator='LessThanThreshold',
        Dimensions=[
            {'Name': 'Endpoint', 'Value': endpoint_name},
        ],
        AlarmActions=[sns_topic_arn],
        AlarmDescription='Average confidence < 0.7 for 3 hours — possible drift',
    )
    
    # Alarm 4: Drift detected
    cloudwatch.put_metric_alarm(
        AlarmName=f'{endpoint_name}-drift-detected',
        MetricName='DriftScore',
        Namespace='ML/TextClassifier',
        Statistic='Maximum',
        Period=3600,
        EvaluationPeriods=1,
        Threshold=0.3,  # KL-divergence threshold
        ComparisonOperator='GreaterThanThreshold',
        AlarmActions=[sns_topic_arn],
        AlarmDescription='Data drift detected — trigger retraining review',
    )
    
    # Composite Alarm: Multiple signals = critical
    cloudwatch.put_composite_alarm(
        AlarmName=f'{endpoint_name}-critical',
        AlarmRule=f'ALARM("{endpoint_name}-high-latency") AND ALARM("{endpoint_name}-high-errors")',
        AlarmActions=[sns_topic_arn],
        AlarmDescription='Both latency AND errors are high — likely model/infra failure',
    )
```

### Anomaly Detection

```python
# Use CloudWatch anomaly detection for metrics with no clear threshold
cloudwatch.put_anomaly_detector(
    Namespace='ML/TextClassifier',
    MetricName='PredictionClass',
    Stat='Average',
    Dimensions=[
        {'Name': 'ModelVersion', 'Value': 'v2'},
    ],
)

# Alarm on anomaly
cloudwatch.put_metric_alarm(
    AlarmName='prediction-distribution-anomaly',
    MetricName='PredictionClass',
    Namespace='ML/TextClassifier',
    Statistic='Average',
    Period=3600,
    EvaluationPeriods=2,
    ThresholdMetricId='ad1',
    ComparisonOperator='LessThanLowerOrGreaterThanUpperThreshold',
    Metrics=[
        {
            'Id': 'm1',
            'MetricStat': {
                'Metric': {
                    'Namespace': 'ML/TextClassifier',
                    'MetricName': 'PredictionClass',
                    'Dimensions': [{'Name': 'ModelVersion', 'Value': 'v2'}],
                },
                'Period': 3600,
                'Stat': 'Average',
            },
        },
        {
            'Id': 'ad1',
            'Expression': 'ANOMALY_DETECTION_BAND(m1, 2)',  # 2 standard deviations
        },
    ],
)
```

---

## SageMaker Model Monitor

### Data Quality Monitoring

```python
from sagemaker.model_monitor import DefaultModelMonitor
from sagemaker.model_monitor.dataset_format import DatasetFormat

# Step 1: Create baseline from training data
monitor = DefaultModelMonitor(
    role=role,
    instance_count=1,
    instance_type='ml.m5.xlarge',
    volume_size_in_gb=20,
    max_runtime_in_seconds=3600,
)

monitor.suggest_baseline(
    baseline_dataset='s3://bucket/baseline-data/train.csv',
    dataset_format=DatasetFormat.csv(header=True),
    output_s3_uri='s3://bucket/monitoring/baseline/',
    wait=True,
)

# Step 2: Create monitoring schedule
from sagemaker.model_monitor import CronExpressionGenerator

monitor.create_monitoring_schedule(
    monitor_schedule_name='text-clf-data-quality',
    endpoint_input=endpoint_name,
    output_s3_uri='s3://bucket/monitoring/reports/',
    statistics=monitor.baseline_statistics(),
    constraints=monitor.suggested_constraints(),
    schedule_cron_expression=CronExpressionGenerator.hourly(),
)
```

### Model Quality Monitoring (Accuracy Over Time)

```python
from sagemaker.model_monitor import ModelQualityMonitor

model_monitor = ModelQualityMonitor(
    role=role,
    instance_count=1,
    instance_type='ml.m5.xlarge',
)

# Baseline: expected performance
model_monitor.suggest_baseline(
    baseline_dataset='s3://bucket/baseline-data/predictions-with-labels.csv',
    dataset_format=DatasetFormat.csv(header=True),
    output_s3_uri='s3://bucket/monitoring/model-quality-baseline/',
    problem_type='BinaryClassification',
    inference_attribute='prediction',
    ground_truth_attribute='label',
    probability_attribute='probability',
)

# Schedule: compare against baseline
model_monitor.create_monitoring_schedule(
    monitor_schedule_name='text-clf-model-quality',
    endpoint_input=endpoint_name,
    output_s3_uri='s3://bucket/monitoring/model-quality-reports/',
    problem_type='BinaryClassification',
    ground_truth_input='s3://bucket/ground-truth/',  # Delayed ground truth
    schedule_cron_expression=CronExpressionGenerator.daily(),
)
```

### Bias Monitoring

```python
from sagemaker.clarify import BiasConfig, ModelConfig, ModelPredictedLabelConfig

bias_config = BiasConfig(
    label_values_or_threshold=[1],
    facet_name='gender',
    facet_values_or_threshold=[0],  # Monitor bias against group 0
)

model_monitor.create_monitoring_schedule(
    monitor_schedule_name='text-clf-bias',
    endpoint_input=endpoint_name,
    output_s3_uri='s3://bucket/monitoring/bias-reports/',
    schedule_cron_expression=CronExpressionGenerator.daily(),
    bias_config=bias_config,
)
```

---

## Logging Strategy

### What to Log from Every Prediction

```python
import json
import logging
import uuid
import time

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def predict_with_logging(input_data, model, model_version):
    request_id = str(uuid.uuid4())
    start = time.time()
    
    # Run prediction
    prediction = model.predict(input_data)
    latency_ms = (time.time() - start) * 1000
    
    # Structured log entry
    log_entry = {
        'event': 'prediction',
        'request_id': request_id,
        'timestamp': time.time(),
        'model_version': model_version,
        'input_hash': hash(str(input_data)) % (10**8),  # Privacy: hash, don't log raw
        'input_length': len(str(input_data)),
        'prediction': int(prediction['label']),
        'confidence': float(prediction['confidence']),
        'latency_ms': round(latency_ms, 2),
        'features': {  # Log feature stats, not raw values
            'text_length': len(input_data.get('text', '')),
            'has_special_chars': bool(input_data.get('text', '').strip()),
        },
    }
    
    logger.info(json.dumps(log_entry))
    return prediction
```

### CloudWatch Logs Insights Queries

```sql
-- Average latency by model version (last 24h)
fields @timestamp, latency_ms, model_version
| filter event = 'prediction'
| stats avg(latency_ms) as avg_latency, 
        pct(latency_ms, 95) as p95_latency,
        count(*) as requests
  by model_version
| sort avg_latency desc

-- Confidence distribution (detect drift)
fields @timestamp, confidence
| filter event = 'prediction'
| stats avg(confidence) as avg_conf,
        min(confidence) as min_conf,
        count(*) as total
  by bin(1h)

-- Error patterns
fields @timestamp, @message
| filter @message like /ERROR/
| stats count(*) as error_count by bin(5m)
| sort @timestamp desc

-- Slow predictions (> 1 second)
fields @timestamp, latency_ms, model_version, input_length
| filter event = 'prediction' and latency_ms > 1000
| sort latency_ms desc
| limit 50
```

---

## Alerting & Incident Response

### Alert Hierarchy

| Priority | Condition | Response Time | Action |
|----------|-----------|---------------|--------|
| **P1** | Endpoint down, 100% errors | 5 min | Auto-rollback + page on-call |
| **P2** | Latency > 2x normal, error rate > 5% | 30 min | Investigate, manual rollback if needed |
| **P3** | Drift detected, confidence dropping | 4 hours | Review, schedule retraining |
| **P4** | Cost anomaly, slow degradation | Next business day | Optimize, plan changes |

### Auto-Remediation Lambda

```python
# lambda: auto-rollback on P1 alarm
import boto3

def lambda_handler(event, context):
    sm = boto3.client('sagemaker')
    endpoint_name = event['detail']['configuration']['metrics'][0]['dimensions']['EndpointName']
    
    # Get list of endpoint configs (sorted by time)
    configs = sm.list_endpoint_configs(
        NameContains=endpoint_name.replace('-prod', ''),
        SortBy='CreationTime',
        SortOrder='Descending',
    )['EndpointConfigs']
    
    # Current config
    current = sm.describe_endpoint(EndpointName=endpoint_name)['EndpointConfigName']
    
    # Find previous (rollback target)
    previous = next((c['EndpointConfigName'] for c in configs 
                     if c['EndpointConfigName'] != current), None)
    
    if previous:
        sm.update_endpoint(
            EndpointName=endpoint_name,
            EndpointConfigName=previous,
        )
        
        # Notify
        sns = boto3.client('sns')
        sns.publish(
            TopicArn='arn:aws:sns:us-east-1:123456:ml-alerts',
            Subject=f'AUTO-ROLLBACK: {endpoint_name}',
            Message=f'Rolled back from {current} to {previous}. Investigate immediately.',
        )
        
        return {'action': 'rolled_back', 'from': current, 'to': previous}
    
    return {'action': 'no_rollback_target', 'error': 'No previous config found'}
```

### Post-Mortem Template for ML Incidents

```markdown
## ML Incident Post-Mortem

**Date:** YYYY-MM-DD
**Duration:** X hours
**Severity:** P1/P2/P3
**Model/Endpoint:** text-clf-prod v3

### Summary
One sentence describing what happened and impact.

### Timeline
- HH:MM — Alarm triggered (what metric, what threshold)
- HH:MM — On-call acknowledged
- HH:MM — Root cause identified
- HH:MM — Mitigation applied (rollback/fix)
- HH:MM — Confirmed resolved

### Root Cause
What actually caused the issue? (data drift, bad deployment, infra, etc.)

### Impact
- X% of predictions affected
- Y minutes of degraded service
- Z users impacted
- Business impact: $$ lost revenue / wrong predictions served

### What Went Well
- Alarm fired within N minutes
- Auto-rollback worked / didn't work

### What Went Wrong
- Detection was too slow because...
- Rollback failed because...

### Action Items
| Item | Owner | Due Date |
|------|-------|----------|
| Add alarm for X | @engineer | YYYY-MM-DD |
| Improve monitoring for Y | @team | YYYY-MM-DD |
| Add integration test for Z | @engineer | YYYY-MM-DD |
```

---

## Dashboards

### Complete CloudWatch Dashboard JSON

```json
{
  "widgets": [
    {
      "type": "text",
      "x": 0, "y": 0, "width": 24, "height": 1,
      "properties": {
        "markdown": "# ML Model Health Dashboard — text-clf-prod"
      }
    },
    {
      "type": "metric",
      "x": 0, "y": 1, "width": 8, "height": 6,
      "properties": {
        "title": "Invocations per Minute",
        "metrics": [
          ["AWS/SageMaker", "Invocations", "EndpointName", "text-clf-prod", "VariantName", "AllTraffic", {"stat": "Sum", "period": 60}]
        ],
        "view": "timeSeries",
        "region": "us-east-1"
      }
    },
    {
      "type": "metric",
      "x": 8, "y": 1, "width": 8, "height": 6,
      "properties": {
        "title": "Latency (p50, p95, p99)",
        "metrics": [
          ["AWS/SageMaker", "ModelLatency", "EndpointName", "text-clf-prod", "VariantName", "AllTraffic", {"stat": "p50", "period": 60, "label": "p50"}],
          ["...", {"stat": "p95", "period": 60, "label": "p95"}],
          ["...", {"stat": "p99", "period": 60, "label": "p99"}]
        ],
        "view": "timeSeries",
        "yAxis": {"left": {"label": "Microseconds"}}
      }
    },
    {
      "type": "metric",
      "x": 16, "y": 1, "width": 8, "height": 6,
      "properties": {
        "title": "Error Rate",
        "metrics": [
          [{"expression": "errors/invocations*100", "label": "Error %", "id": "e1"}],
          ["AWS/SageMaker", "Invocation5XXErrors", "EndpointName", "text-clf-prod", "VariantName", "AllTraffic", {"stat": "Sum", "period": 300, "id": "errors", "visible": false}],
          ["AWS/SageMaker", "Invocations", "EndpointName", "text-clf-prod", "VariantName", "AllTraffic", {"stat": "Sum", "period": 300, "id": "invocations", "visible": false}]
        ],
        "view": "timeSeries"
      }
    },
    {
      "type": "metric",
      "x": 0, "y": 7, "width": 8, "height": 6,
      "properties": {
        "title": "Prediction Confidence (avg)",
        "metrics": [
          ["ML/TextClassifier", "PredictionConfidence", "Endpoint", "text-clf-prod", {"stat": "Average", "period": 300}]
        ],
        "view": "timeSeries",
        "annotations": {
          "horizontal": [{"value": 0.7, "label": "Drift threshold", "color": "#ff0000"}]
        }
      }
    },
    {
      "type": "metric",
      "x": 8, "y": 7, "width": 8, "height": 6,
      "properties": {
        "title": "Drift Score",
        "metrics": [
          ["ML/TextClassifier", "DriftScore", "Feature", "text_length", {"stat": "Maximum", "period": 3600}],
          ["ML/TextClassifier", "DriftScore", "Feature", "vocabulary", {"stat": "Maximum", "period": 3600}]
        ],
        "view": "timeSeries",
        "annotations": {
          "horizontal": [{"value": 0.3, "label": "Alert threshold", "color": "#ff0000"}]
        }
      }
    },
    {
      "type": "metric",
      "x": 16, "y": 7, "width": 8, "height": 6,
      "properties": {
        "title": "Instance Count & CPU",
        "metrics": [
          ["AWS/SageMaker", "CPUUtilization", "EndpointName", "text-clf-prod", "VariantName", "AllTraffic", {"stat": "Average", "period": 60}],
          ["/aws/sagemaker/Endpoints", "MemoryUtilization", "EndpointName", "text-clf-prod", "VariantName", "AllTraffic", {"stat": "Average", "period": 60}]
        ],
        "view": "timeSeries"
      }
    }
  ]
}
```

### Three Dashboard Views

**1. Operational (SRE):** Latency, error rate, CPU/GPU/memory, instance count, auto-scaling events
**2. Model Health (ML Team):** Confidence distribution, drift scores, prediction class balance, feature distributions
**3. Business Impact (Leadership):** Predictions served, accuracy (when ground truth available), revenue impact, cost per prediction
