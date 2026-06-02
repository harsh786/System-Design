# SageMaker Training and Endpoints

## SageMaker Training

### Training Job Anatomy

Every SageMaker training job has five components:

```
┌─────────────────────────────────────────────────────┐
│                 TRAINING JOB                         │
├─────────────────────────────────────────────────────┤
│                                                     │
│  1. ROLE (IAM)                                      │
│     └─ Permissions to access S3, ECR, CloudWatch    │
│                                                     │
│  2. INPUT (Data Channels)                           │
│     └─ s3://bucket/train/, s3://bucket/val/         │
│     └─ Mode: File (download) or Pipe (streaming)   │
│                                                     │
│  3. OUTPUT                                          │
│     └─ s3://bucket/output/ (model.tar.gz)           │
│     └─ s3://bucket/checkpoints/ (for spot)          │
│                                                     │
│  4. INSTANCE                                        │
│     └─ Type: ml.p3.2xlarge (1 V100 GPU)            │
│     └─ Count: 1 (or N for distributed)             │
│     └─ Volume: 50GB EBS                            │
│                                                     │
│  5. ALGORITHM                                       │
│     └─ Built-in (XGBoost, Linear Learner, etc.)    │
│     └─ OR Custom container (your Docker image)      │
│     └─ OR Framework (PyTorch, TF, HuggingFace)     │
│                                                     │
└─────────────────────────────────────────────────────┘
```

### Built-in Algorithms vs Custom Containers

| Approach | When to Use | Examples |
|----------|-------------|---------|
| Built-in algorithms | Standard ML tasks, fastest setup | XGBoost, Linear Learner, Image Classification |
| Framework estimators | Custom model, familiar framework | PyTorch, TensorFlow, HuggingFace |
| Custom container | Full control, non-standard deps | Custom CUDA kernels, proprietary libs |
| Bring Your Own Script | Most common — script + framework | `train.py` with PyTorch estimator |

### Spot Training (70% Cost Savings)

Managed Spot Training uses unused EC2 capacity:

```python
estimator = PyTorch(
    entry_point='train.py',
    role=role,
    instance_type='ml.p3.2xlarge',
    # Spot configuration
    use_spot_instances=True,
    max_wait=7200,       # Max time to wait for spot + training
    max_run=3600,        # Max training time
    checkpoint_s3_uri='s3://bucket/checkpoints/',  # CRITICAL: save progress
)
```

**Key rules for spot training:**
- Always set `checkpoint_s3_uri` — your training will resume from checkpoint on interruption
- `max_wait` >= `max_run` — account for possible interruptions
- Save checkpoints every N steps in your training script
- Spot savings: typically 60-70% off on-demand

```python
# In your train.py — checkpoint logic
import os

CHECKPOINT_DIR = '/opt/ml/checkpoints'

def save_checkpoint(model, optimizer, epoch, step):
    path = os.path.join(CHECKPOINT_DIR, f'checkpoint-{epoch}-{step}.pt')
    torch.save({
        'epoch': epoch,
        'step': step,
        'model_state_dict': model.state_dict(),
        'optimizer_state_dict': optimizer.state_dict(),
    }, path)

def load_latest_checkpoint(model, optimizer):
    checkpoints = sorted(os.listdir(CHECKPOINT_DIR))
    if not checkpoints:
        return 0, 0
    latest = torch.load(os.path.join(CHECKPOINT_DIR, checkpoints[-1]))
    model.load_state_dict(latest['model_state_dict'])
    optimizer.load_state_dict(latest['optimizer_state_dict'])
    return latest['epoch'], latest['step']
```

### Distributed Training on SageMaker

**Multi-GPU (single node):**
```python
# Use ml.p3.8xlarge (4 V100s) or ml.p3.16xlarge (8 V100s)
estimator = PyTorch(
    entry_point='train.py',
    instance_type='ml.p3.8xlarge',
    instance_count=1,
    # PyTorch DDP handles multi-GPU automatically
    distribution={'pytorchddp': {'enabled': True}},
)
```

**Multi-node:**
```python
estimator = PyTorch(
    entry_point='train.py',
    instance_type='ml.p3.16xlarge',
    instance_count=4,  # 4 nodes × 8 GPUs = 32 GPUs
    distribution={
        'pytorchddp': {
            'enabled': True,
            'custom_mpi_options': '-verbose --NCCL_DEBUG=VERSION'
        }
    },
)
```

**In your training script:**
```python
import torch.distributed as dist

def train():
    dist.init_process_group(backend='nccl')
    local_rank = int(os.environ['LOCAL_RANK'])
    device = torch.device(f'cuda:{local_rank}')
    
    model = MyModel().to(device)
    model = torch.nn.parallel.DistributedDataParallel(model, device_ids=[local_rank])
    
    # SageMaker sets all environment variables for distributed training
    # SM_NUM_GPUS, SM_NUM_HOSTS, SM_CURRENT_HOST, etc.
```

### Hyperparameter Tuning Jobs

```python
from sagemaker.tuner import HyperparameterTuner, ContinuousParameter, IntegerParameter

tuner = HyperparameterTuner(
    estimator=estimator,
    objective_metric_name='val_accuracy',
    objective_type='Maximize',
    hyperparameter_ranges={
        'lr': ContinuousParameter(1e-5, 1e-2, scaling_type='Logarithmic'),
        'batch_size': IntegerParameter(16, 128),
        'hidden_dim': IntegerParameter(64, 512),
        'dropout': ContinuousParameter(0.1, 0.5),
    },
    max_jobs=50,
    max_parallel_jobs=5,
    strategy='Bayesian',  # Bayesian, Random, Hyperband, Grid
    early_stopping_type='Auto',  # Stop bad trials early
)

tuner.fit({'train': s3_train, 'val': s3_val})

# Get best training job
best_job = tuner.best_training_job()
```

**Emit metrics from your script for tuning:**
```python
# SageMaker parses stdout for metric definitions
print(f'val_accuracy={accuracy:.4f};')  # Must match metric_definitions regex
```

### SageMaker Experiments (Tracking)

```python
from sagemaker.experiments import Run

with Run(experiment_name='text-classifier', run_name='run-001') as run:
    run.log_parameter('lr', 0.001)
    run.log_parameter('epochs', 10)
    
    for epoch in range(10):
        # ... training ...
        run.log_metric('train_loss', loss, step=epoch)
        run.log_metric('val_accuracy', acc, step=epoch)
    
    run.log_artifact('model', 's3://bucket/model.tar.gz')
```

### Complete Training Job Example

```python
import sagemaker
from sagemaker.pytorch import PyTorch
from sagemaker.session import Session

session = sagemaker.Session()
role = sagemaker.get_execution_role()
bucket = session.default_bucket()

# Upload data
s3_train = session.upload_data('data/train', bucket=bucket, key_prefix='text-clf/train')
s3_val = session.upload_data('data/val', bucket=bucket, key_prefix='text-clf/val')

# Define estimator
estimator = PyTorch(
    entry_point='train.py',
    source_dir='src/',              # Directory with train.py + requirements.txt
    role=role,
    instance_count=1,
    instance_type='ml.p3.2xlarge',
    framework_version='2.0',
    py_version='py310',
    hyperparameters={
        'epochs': 10,
        'lr': 0.001,
        'batch_size': 32,
        'model_name': 'distilbert-base-uncased',
    },
    use_spot_instances=True,
    max_wait=7200,
    max_run=3600,
    checkpoint_s3_uri=f's3://{bucket}/text-clf/checkpoints/',
    output_path=f's3://{bucket}/text-clf/output/',
    metric_definitions=[
        {'Name': 'val_accuracy', 'Regex': 'val_accuracy=([0-9\\.]+)'},
        {'Name': 'train_loss', 'Regex': 'train_loss=([0-9\\.]+)'},
    ],
    tags=[
        {'Key': 'project', 'Value': 'text-classifier'},
        {'Key': 'team', 'Value': 'ml-platform'},
    ],
)

# Launch training
estimator.fit(
    inputs={'train': s3_train, 'val': s3_val},
    job_name='text-clf-2024-01-15',
    wait=True,
    logs='All',
)
```

---

## SageMaker Endpoints

### Real-time Endpoints (Single Model)

```python
from sagemaker.pytorch import PyTorchModel

model = PyTorchModel(
    model_data=estimator.model_data,  # s3://bucket/.../model.tar.gz
    role=role,
    framework_version='2.0',
    py_version='py310',
    entry_point='inference.py',       # Must define model_fn, input_fn, predict_fn, output_fn
)

predictor = model.deploy(
    initial_instance_count=2,
    instance_type='ml.g4dn.xlarge',
    endpoint_name='text-clf-prod',
)

# Invoke
result = predictor.predict({'text': 'This product is amazing!'})
```

**inference.py:**
```python
import torch
import json
from transformers import AutoTokenizer, AutoModelForSequenceClassification

def model_fn(model_dir):
    """Load model from the model_dir (extracted model.tar.gz)"""
    model = AutoModelForSequenceClassification.from_pretrained(model_dir)
    tokenizer = AutoTokenizer.from_pretrained(model_dir)
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    model.to(device).eval()
    return {'model': model, 'tokenizer': tokenizer, 'device': device}

def input_fn(request_body, content_type):
    """Deserialize input"""
    if content_type == 'application/json':
        return json.loads(request_body)
    raise ValueError(f'Unsupported content type: {content_type}')

def predict_fn(input_data, model_dict):
    """Run inference"""
    model = model_dict['model']
    tokenizer = model_dict['tokenizer']
    device = model_dict['device']
    
    tokens = tokenizer(input_data['text'], return_tensors='pt', 
                       truncation=True, max_length=512).to(device)
    
    with torch.no_grad():
        outputs = model(**tokens)
        probs = torch.softmax(outputs.logits, dim=-1)
    
    return {'label': int(probs.argmax()), 'confidence': float(probs.max())}

def output_fn(prediction, accept):
    """Serialize output"""
    return json.dumps(prediction), 'application/json'
```

### Multi-Model Endpoints (MMS)

Serve 100s of models on a single endpoint — models load/unload dynamically:

```python
from sagemaker.multidatamodel import MultiDataModel

mme = MultiDataModel(
    name='multi-model-endpoint',
    model_data_prefix=f's3://{bucket}/models/',  # All model.tar.gz files here
    model=model,
    sagemaker_session=session,
)

predictor = mme.deploy(
    initial_instance_count=2,
    instance_type='ml.g4dn.xlarge',
)

# Add models dynamically
mme.add_model(model_data_source='s3://bucket/models/customer-A.tar.gz')
mme.add_model(model_data_source='s3://bucket/models/customer-B.tar.gz')

# Invoke specific model
predictor.predict(data={'text': 'hello'}, target_model='customer-A.tar.gz')
```

**Use cases:** Per-customer models, A/B testing many variants, region-specific models.

### Serverless Inference

```python
from sagemaker.serverless import ServerlessInferenceConfig

serverless_config = ServerlessInferenceConfig(
    memory_size_in_mb=3072,     # 1024, 2048, 3072, 4096, 5120, 6144
    max_concurrency=10,          # Max concurrent invocations
    provisioned_concurrency=2,   # Keep 2 warm (reduces cold starts)
)

predictor = model.deploy(
    serverless_inference_config=serverless_config,
    endpoint_name='text-clf-serverless',
)
```

**Trade-offs:**
- Pro: $0 when idle, auto-scales to 0
- Con: Cold start 1-30s (depends on model size), max 6GB memory

### Async Inference

For heavy models (LLMs, image generation) where response time > 60s:

```python
from sagemaker.async_inference import AsyncInferenceConfig

async_config = AsyncInferenceConfig(
    output_path=f's3://{bucket}/async-output/',
    failure_path=f's3://{bucket}/async-failures/',
    max_concurrent_invocations_per_instance=4,
    notification_config={
        'SuccessTopic': 'arn:aws:sns:us-east-1:123456:success',
        'ErrorTopic': 'arn:aws:sns:us-east-1:123456:error',
    }
)

predictor = model.deploy(
    initial_instance_count=1,
    instance_type='ml.g5.2xlarge',
    async_inference_config=async_config,
)

# Invoke — returns immediately with output location
response = predictor.predict_async(input_path='s3://bucket/input/request.json')
output_location = response.output_path  # Poll this for result
```

### Endpoint Autoscaling

```python
import boto3

client = boto3.client('application-autoscaling')

# Register scalable target
client.register_scalable_target(
    ServiceNamespace='sagemaker',
    ResourceId=f'endpoint/{endpoint_name}/variant/AllTraffic',
    ScalableDimension='sagemaker:variant:DesiredInstanceCount',
    MinCapacity=1,
    MaxCapacity=10,
)

# Target tracking policy (recommended)
client.put_scaling_policy(
    PolicyName='invocations-target-tracking',
    ServiceNamespace='sagemaker',
    ResourceId=f'endpoint/{endpoint_name}/variant/AllTraffic',
    ScalableDimension='sagemaker:variant:DesiredInstanceCount',
    PolicyType='TargetTrackingScaling',
    TargetTrackingScalingPolicyConfiguration={
        'TargetValue': 750.0,  # Target invocations per instance per minute
        'PredefinedMetricSpecification': {
            'PredefinedMetricType': 'SageMakerVariantInvocationsPerInstance'
        },
        'ScaleInCooldown': 300,
        'ScaleOutCooldown': 60,
    },
)

# Step scaling (for more control)
client.put_scaling_policy(
    PolicyName='latency-step-scaling',
    ServiceNamespace='sagemaker',
    ResourceId=f'endpoint/{endpoint_name}/variant/AllTraffic',
    ScalableDimension='sagemaker:variant:DesiredInstanceCount',
    PolicyType='StepScaling',
    StepScalingPolicyConfiguration={
        'AdjustmentType': 'ChangeInCapacity',
        'StepAdjustments': [
            {'MetricIntervalLowerBound': 0, 'MetricIntervalUpperBound': 50, 'ScalingAdjustment': 1},
            {'MetricIntervalLowerBound': 50, 'ScalingAdjustment': 3},
        ],
        'Cooldown': 60,
    },
)
```

### A/B Testing with Production Variants

```python
from sagemaker.model import Model

# Deploy two models with traffic split
endpoint_config = session.create_endpoint_config(
    name='ab-test-config',
    production_variants=[
        {
            'VariantName': 'ModelA',
            'ModelName': 'text-clf-v1',
            'InstanceType': 'ml.g4dn.xlarge',
            'InitialInstanceCount': 1,
            'InitialVariantWeight': 90,  # 90% traffic
        },
        {
            'VariantName': 'ModelB',
            'ModelName': 'text-clf-v2',
            'InstanceType': 'ml.g4dn.xlarge',
            'InitialInstanceCount': 1,
            'InitialVariantWeight': 10,  # 10% traffic (canary)
        },
    ],
)

# Update traffic split (shift more to winner)
sm_client = boto3.client('sagemaker')
sm_client.update_endpoint_weights_and_capacities(
    EndpointName='text-clf-prod',
    DesiredWeightsAndCapacities=[
        {'VariantName': 'ModelA', 'DesiredWeight': 50},
        {'VariantName': 'ModelB', 'DesiredWeight': 50},
    ],
)
```

### Blue/Green Deployment

```python
sm_client = boto3.client('sagemaker')

# Create new endpoint config (green)
sm_client.create_endpoint_config(
    EndpointConfigName='text-clf-green',
    ProductionVariants=[{
        'VariantName': 'AllTraffic',
        'ModelName': 'text-clf-v2',
        'InstanceType': 'ml.g4dn.xlarge',
        'InitialInstanceCount': 2,
    }],
)

# Update endpoint (blue → green, zero-downtime)
sm_client.update_endpoint(
    EndpointName='text-clf-prod',
    EndpointConfigName='text-clf-green',
    RetainDeploymentConfig=True,
    DeploymentConfig={
        'BlueGreenUpdatePolicy': {
            'TrafficRoutingConfiguration': {
                'Type': 'CANARY',
                'CanarySize': {'Type': 'INSTANCE_COUNT', 'Value': 1},
                'WaitIntervalInSeconds': 600,  # Wait 10 min before full shift
            },
            'TerminationWaitInSeconds': 300,
            'MaximumExecutionTimeoutInSeconds': 1800,
        },
        'AutoRollbackConfiguration': {
            'Alarms': [{'AlarmName': 'text-clf-high-error-rate'}],
        },
    },
)
```

---

## SageMaker Pipelines

### Complete Pipeline Example

```python
from sagemaker.workflow.pipeline import Pipeline
from sagemaker.workflow.steps import ProcessingStep, TrainingStep
from sagemaker.workflow.step_collections import RegisterModel
from sagemaker.workflow.conditions import ConditionGreaterThanOrEqualTo
from sagemaker.workflow.condition_step import ConditionStep
from sagemaker.workflow.parameters import ParameterString, ParameterFloat
from sagemaker.processing import ScriptProcessor
from sagemaker.workflow.properties import PropertyFile

# Pipeline parameters
model_approval = ParameterString(name='ModelApproval', default_value='PendingManualApproval')
accuracy_threshold = ParameterFloat(name='AccuracyThreshold', default_value=0.85)

# Step 1: Data Processing
processor = ScriptProcessor(
    image_uri='123456.dkr.ecr.us-east-1.amazonaws.com/preprocessing:latest',
    role=role,
    instance_count=1,
    instance_type='ml.m5.xlarge',
)

processing_step = ProcessingStep(
    name='PreprocessData',
    processor=processor,
    inputs=[ProcessingInput(source=f's3://{bucket}/raw-data/', destination='/opt/ml/processing/input')],
    outputs=[
        ProcessingOutput(output_name='train', source='/opt/ml/processing/output/train'),
        ProcessingOutput(output_name='val', source='/opt/ml/processing/output/val'),
    ],
    code='scripts/preprocess.py',
)

# Step 2: Training
training_step = TrainingStep(
    name='TrainModel',
    estimator=estimator,
    inputs={
        'train': TrainingInput(s3_data=processing_step.properties.ProcessingOutputConfig.Outputs['train'].S3Output.S3Uri),
        'val': TrainingInput(s3_data=processing_step.properties.ProcessingOutputConfig.Outputs['val'].S3Output.S3Uri),
    },
)

# Step 3: Evaluation
eval_processor = ScriptProcessor(
    image_uri='123456.dkr.ecr.us-east-1.amazonaws.com/evaluation:latest',
    role=role,
    instance_count=1,
    instance_type='ml.m5.xlarge',
)

evaluation_report = PropertyFile(name='EvalReport', output_name='evaluation', path='evaluation.json')

eval_step = ProcessingStep(
    name='EvaluateModel',
    processor=eval_processor,
    inputs=[
        ProcessingInput(source=training_step.properties.ModelArtifacts.S3ModelArtifacts, destination='/opt/ml/processing/model'),
        ProcessingInput(source=processing_step.properties.ProcessingOutputConfig.Outputs['val'].S3Output.S3Uri, destination='/opt/ml/processing/test'),
    ],
    outputs=[ProcessingOutput(output_name='evaluation', source='/opt/ml/processing/evaluation')],
    code='scripts/evaluate.py',
    property_files=[evaluation_report],
)

# Step 4: Conditional — only register if accuracy > threshold
condition = ConditionGreaterThanOrEqualTo(
    left=JsonGet(step_name='EvaluateModel', property_file=evaluation_report, json_path='metrics.accuracy'),
    right=accuracy_threshold,
)

# Step 5: Register Model
register_step = RegisterModel(
    name='RegisterModel',
    estimator=estimator,
    model_data=training_step.properties.ModelArtifacts.S3ModelArtifacts,
    content_types=['application/json'],
    response_types=['application/json'],
    inference_instances=['ml.g4dn.xlarge', 'ml.m5.large'],
    transform_instances=['ml.m5.xlarge'],
    model_package_group_name='text-classifier',
    approval_status=model_approval,
)

condition_step = ConditionStep(
    name='CheckAccuracy',
    conditions=[condition],
    if_steps=[register_step],
    else_steps=[],  # Do nothing if accuracy too low
)

# Assemble pipeline
pipeline = Pipeline(
    name='text-clf-pipeline',
    parameters=[model_approval, accuracy_threshold],
    steps=[processing_step, training_step, eval_step, condition_step],
)

pipeline.upsert(role_arn=role)
execution = pipeline.start()
```

---

## Model Registry

### Model Versioning and Approval

```python
sm_client = boto3.client('sagemaker')

# Create model package group
sm_client.create_model_package_group(
    ModelPackageGroupName='text-classifier',
    ModelPackageGroupDescription='Production text classification models',
)

# List versions
packages = sm_client.list_model_packages(
    ModelPackageGroupName='text-classifier',
    SortBy='CreationTime',
    SortOrder='Descending',
)

# Approve a model version (manual gate)
sm_client.update_model_package(
    ModelPackageArn='arn:aws:sagemaker:us-east-1:123456:model-package/text-classifier/3',
    ModelApprovalStatus='Approved',
    ApprovalDescription='Accuracy 0.92, passes all quality gates',
)

# Deploy approved model
from sagemaker.model import ModelPackage

model = ModelPackage(
    role=role,
    model_package_arn='arn:aws:sagemaker:us-east-1:123456:model-package/text-classifier/3',
)
predictor = model.deploy(instance_type='ml.g4dn.xlarge', initial_instance_count=1)
```

### Model Cards

```python
sm_client.create_model_card(
    ModelCardName='text-classifier-v3',
    Content=json.dumps({
        'model_overview': {
            'model_name': 'text-classifier-v3',
            'model_description': 'DistilBERT fine-tuned for product review sentiment',
            'model_creator': 'ML Platform Team',
            'problem_type': 'Binary Classification',
        },
        'intended_uses': {
            'purpose_of_model': 'Classify product reviews as positive/negative',
            'intended_users': ['Product team', 'Customer support'],
            'out_of_scope_uses': ['Not for hate speech detection'],
        },
        'training_details': {
            'training_observations': 'Trained on 100K labeled reviews',
            'objective_function': 'Cross-entropy loss',
        },
        'evaluation_details': [
            {'metric': 'Accuracy', 'value': '0.923'},
            {'metric': 'F1', 'value': '0.918'},
            {'metric': 'AUC-ROC', 'value': '0.961'},
        ],
    }),
    ModelCardStatus='Draft',
)
```
