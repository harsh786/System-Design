# Cost Optimization for ML on AWS

## ML Costs Breakdown

```
Typical ML project cost distribution:
├── Training (10-20%)        — Bursts of expensive GPU compute
├── Inference (50-70%)       — 24/7 endpoint running
├── Storage (5-10%)          — S3 model artifacts, datasets, logs
├── Data Transfer (5-15%)    — Often overlooked!
└── Experimentation (5-10%)  — Notebooks, failed experiments
```

### Instance Type Comparison

| Instance | GPU | VRAM | $/hr (on-demand) | $/hr (spot) | Best For |
|----------|-----|------|-------------------|-------------|----------|
| ml.m5.xlarge | None | — | $0.23 | $0.07 | sklearn, XGBoost |
| ml.g4dn.xlarge | T4 | 16GB | $0.74 | $0.22 | Small models inference |
| ml.g4dn.2xlarge | T4 | 16GB | $1.12 | $0.34 | Medium inference |
| ml.g5.xlarge | A10G | 24GB | $1.41 | $0.42 | Transformers inference |
| ml.g5.2xlarge | A10G | 24GB | $1.52 | $0.46 | Large transformers |
| ml.p3.2xlarge | V100 | 16GB | $3.83 | $1.15 | Training |
| ml.p3.8xlarge | 4×V100 | 64GB | $14.69 | $4.41 | Distributed training |
| ml.p4d.24xlarge | 8×A100 | 320GB | $32.77 | $9.83 | Large model training |

---

## Cost Optimization Strategies

### 1. Spot Instances for Training (70% savings)

```python
estimator = PyTorch(
    instance_type='ml.p3.2xlarge',
    use_spot_instances=True,
    max_wait=7200,
    max_run=3600,
    checkpoint_s3_uri='s3://bucket/checkpoints/',
)
# Cost: $1.15/hr instead of $3.83/hr = 70% savings
```

**Rules:**
- Always checkpoint every N steps
- Set `max_wait` = 2× `max_run` (handles interruption + restart)
- Not suitable for: time-critical training, jobs < 10 minutes (overhead not worth it)

### 2. Savings Plans for Inference (up to 72% savings)

If you run endpoints 24/7, commit to 1-year or 3-year Savings Plan:

| Commitment | Savings vs On-Demand |
|------------|---------------------|
| No commitment (on-demand) | 0% |
| 1-year, no upfront | ~30% |
| 1-year, partial upfront | ~40% |
| 1-year, all upfront | ~45% |
| 3-year, all upfront | ~72% |

```
ml.g4dn.xlarge:
- On-demand: $0.736/hr × 730 hrs = $537/month
- 1yr Savings Plan (no upfront): ~$376/month
- 3yr Savings Plan (all upfront): ~$150/month
```

### 3. Right-Sizing

Benchmark your model on different instance types:

```python
import time
import boto3

def benchmark_instance(model_package_arn, instance_type, test_data, n_requests=100):
    """Deploy temporarily and measure latency + throughput."""
    sm = boto3.client('sagemaker-runtime')
    
    # Deploy (code omitted for brevity)
    endpoint_name = f'benchmark-{instance_type.replace(".", "-")}'
    
    latencies = []
    for _ in range(n_requests):
        start = time.time()
        sm.invoke_endpoint(
            EndpointName=endpoint_name,
            Body=test_data,
            ContentType='application/json',
        )
        latencies.append((time.time() - start) * 1000)
    
    return {
        'instance_type': instance_type,
        'p50_ms': sorted(latencies)[n_requests // 2],
        'p95_ms': sorted(latencies)[int(n_requests * 0.95)],
        'cost_per_hour': get_instance_price(instance_type),
        'cost_per_1M_requests': calculate_cost_per_million(latencies, instance_type),
    }

# Compare results:
# ml.g4dn.xlarge:  p50=45ms, p95=62ms,  $0.74/hr, $0.92/1M requests
# ml.g5.xlarge:    p50=28ms, p95=35ms,  $1.41/hr, $1.10/1M requests  
# ml.m5.2xlarge:   p50=120ms, p95=180ms, $0.46/hr, $1.53/1M requests (CPU only)
# Winner for this model: g4dn.xlarge (best cost/request ratio)
```

### 4. Multi-Model Endpoints (10-100x cost reduction)

Instead of N endpoints for N models:

```
Traditional: 100 models × 1 endpoint each × $537/month = $53,700/month
Multi-model: 100 models × 1 shared endpoint (2 instances) = $1,074/month
Savings: 98%
```

Trade-off: Cold loading when model isn't cached (~1-5s first request).

### 5. Serverless Inference (Pay Per Use)

```
Comparison for low-traffic model (1000 requests/day, 200ms avg):

Always-on endpoint (ml.g4dn.xlarge):
  $0.736/hr × 24hr × 30 days = $530/month

Serverless (3GB memory, 200ms):
  1000 × 30 = 30,000 requests/month
  Compute: 30,000 × 0.2s × 3GB × $0.0000167/GB-s = $0.30/month
  Request: 30,000 × $0.0000002 = $0.006/month
  Total: ~$1/month (with provisioned concurrency: ~$50/month)

Savings: 99% (without provisioned) or 90% (with provisioned)
```

### 6. Model Optimization = Smaller Instance

| Optimization | Size Reduction | Latency Impact | Quality Impact |
|-------------|----------------|----------------|----------------|
| FP16 quantization | 50% | 20-40% faster | < 0.5% accuracy drop |
| INT8 quantization | 75% | 30-50% faster | 1-2% accuracy drop |
| Distillation | 60-90% | 50-80% faster | 1-5% accuracy drop |
| Pruning | 50-90% | 30-70% faster | 1-3% accuracy drop |
| ONNX conversion | 0% | 20-50% faster | 0% |

```python
# Example: Convert PyTorch model to ONNX for faster inference
import torch
import onnx

model.eval()
dummy_input = torch.randn(1, 512)  # Match your input shape
torch.onnx.export(model, dummy_input, 'model.onnx', opset_version=14)

# Now serve with ONNX Runtime instead of PyTorch
# Often allows stepping down from g4dn.xlarge to m5.xlarge
```

### 7. Scheduled Scaling

```python
# Scale down at night (if traffic drops)
autoscaling = boto3.client('application-autoscaling')

# Scale to 1 instance at 10 PM
autoscaling.put_scheduled_action(
    ServiceNamespace='sagemaker',
    ResourceId=f'endpoint/{endpoint_name}/variant/AllTraffic',
    ScalableDimension='sagemaker:variant:DesiredInstanceCount',
    ScheduledActionName='scale-down-night',
    Schedule='cron(0 22 * * ? *)',  # 10 PM UTC
    ScalableTargetAction={'MinCapacity': 1, 'MaxCapacity': 3},
)

# Scale up at 6 AM
autoscaling.put_scheduled_action(
    ServiceNamespace='sagemaker',
    ResourceId=f'endpoint/{endpoint_name}/variant/AllTraffic',
    ScalableDimension='sagemaker:variant:DesiredInstanceCount',
    ScheduledActionName='scale-up-morning',
    Schedule='cron(0 6 * * ? *)',  # 6 AM UTC
    ScalableTargetAction={'MinCapacity': 2, 'MaxCapacity': 10},
)
```

### 8. Inference Caching

For repeated/similar predictions (e.g., product recommendations):

```python
import hashlib
import json
import redis

cache = redis.Redis(host='elasticache-endpoint', port=6379)
CACHE_TTL = 3600  # 1 hour

def predict_with_cache(input_data, model):
    # Create cache key from input
    cache_key = f"pred:{hashlib.md5(json.dumps(input_data, sort_keys=True).encode()).hexdigest()}"
    
    # Check cache
    cached = cache.get(cache_key)
    if cached:
        return json.loads(cached)  # Cache hit — free!
    
    # Cache miss — run model
    prediction = model.predict(input_data)
    cache.setex(cache_key, CACHE_TTL, json.dumps(prediction))
    return prediction

# If 40% of requests are cache hits, you save 40% on compute
```

---

## Cost Estimation Formulas

```
TRAINING:
  cost = instance_price/hr × hours × (1 - spot_discount) × (1 + data_transfer_overhead)
  
  Examples:
  - Quick experiment: $3.83 × 1hr × 0.3 (spot) = $1.15
  - Full training: $3.83 × 8hr × 0.3 (spot) = $9.20
  - Distributed (4 nodes): $14.69 × 4 × 4hr × 0.3 = $70.50
  - Hyperparameter tuning (50 jobs): $3.83 × 50 × 1hr × 0.3 = $57.45

INFERENCE (always-on):
  monthly_cost = instance_price/hr × 730 hrs × instance_count
  
  Examples:
  - ml.g4dn.xlarge × 2 instances: $0.74 × 730 × 2 = $1,080/month
  - With savings plan (40% off): $648/month
  - With night scaling (12hr at 1 instance): ~$810/month

INFERENCE (serverless):
  monthly_cost = requests × avg_duration_sec × memory_gb × $0.0000167 + requests × $0.0000002
  
  Examples:
  - 100K/day: 3M/month × 0.2s × 3GB × $0.0000167 = $30/month
  - 1M/day: 30M/month × 0.2s × 3GB × $0.0000167 = $300/month

STORAGE:
  S3: $0.023/GB/month (standard), $0.0125/GB/month (IA)
  - 100 model versions × 2GB each = 200GB = $4.60/month
  - Training data: 500GB = $11.50/month
```

---

## Cost Monitoring

### Tagging Strategy

```python
# Always tag ML resources
tags = [
    {'Key': 'project', 'Value': 'text-classifier'},
    {'Key': 'team', 'Value': 'ml-platform'},
    {'Key': 'environment', 'Value': 'production'},
    {'Key': 'model-version', 'Value': 'v2.1'},
    {'Key': 'cost-center', 'Value': 'ml-inference'},
]
```

### Budget Alert

```python
budgets = boto3.client('budgets')

budgets.create_budget(
    AccountId='123456789012',
    Budget={
        'BudgetName': 'ML-Monthly-Budget',
        'BudgetLimit': {'Amount': '2000', 'Unit': 'USD'},
        'TimeUnit': 'MONTHLY',
        'BudgetType': 'COST',
        'CostFilters': {
            'TagKeyValue': ['user:project$text-classifier'],
        },
    },
    NotificationsWithSubscribers=[
        {
            'Notification': {
                'NotificationType': 'ACTUAL',
                'ComparisonOperator': 'GREATER_THAN',
                'Threshold': 80.0,  # Alert at 80% of budget
                'ThresholdType': 'PERCENTAGE',
            },
            'Subscribers': [
                {'SubscriptionType': 'EMAIL', 'Address': 'ml-team@company.com'},
            ],
        },
        {
            'Notification': {
                'NotificationType': 'FORECASTED',
                'ComparisonOperator': 'GREATER_THAN',
                'Threshold': 100.0,  # Alert if forecast exceeds budget
                'ThresholdType': 'PERCENTAGE',
            },
            'Subscribers': [
                {'SubscriptionType': 'SNS', 'Address': 'arn:aws:sns:us-east-1:123456:ml-cost-alerts'},
            ],
        },
    ],
)
```

### Monthly Cost Review Checklist

```
□ Are there idle endpoints? (check invocation count = 0)
□ Are training jobs using spot instances?
□ Are there undeleted experiments/trial components?
□ Is S3 lifecycle moving old artifacts to IA/Glacier?
□ Are instance types right-sized? (check GPU utilization < 30% = oversized)
□ Can any always-on endpoints move to serverless?
□ Are there orphaned EBS volumes or ENIs?
□ Data transfer: are endpoints in same region as callers?
```
