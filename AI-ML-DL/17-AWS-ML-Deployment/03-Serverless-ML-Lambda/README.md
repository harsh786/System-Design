# Serverless ML with Lambda

## When Lambda Works for ML

| Criteria | Requirement |
|----------|-------------|
| Model size | < 250MB (deployment package) or use EFS for larger |
| Inference time | < 15 minutes (Lambda max timeout) |
| Memory | < 10GB |
| Traffic pattern | Bursty, infrequent, unpredictable |
| Latency tolerance | Cold starts: 1-10s acceptable |
| GPU needed | No (Lambda has no GPU) |

**Good fits:** sklearn models, small NLP (TF-IDF + LR), feature engineering, lightweight image processing, embeddings lookup.

**Bad fits:** Large transformers, diffusion models, real-time low-latency, GPU-required inference.

---

## Lambda Deployment Patterns

### Pattern 1: Model in Deployment Package (< 50MB)

```python
# lambda_function.py
import json
import pickle
import numpy as np

# Model loaded at cold start (stays warm between invocations)
with open('model.pkl', 'rb') as f:
    model = pickle.load(f)

def lambda_handler(event, context):
    body = json.loads(event['body'])
    features = np.array(body['features']).reshape(1, -1)
    
    prediction = model.predict(features)
    probability = model.predict_proba(features).max()
    
    return {
        'statusCode': 200,
        'body': json.dumps({
            'prediction': int(prediction[0]),
            'confidence': float(probability),
            'model_version': 'v2.1',
        }),
        'headers': {'Content-Type': 'application/json'}
    }
```

**Deploy:**
```bash
# Package with dependencies
pip install -t package/ scikit-learn numpy
cp lambda_function.py model.pkl package/
cd package && zip -r ../deployment.zip . && cd ..
aws lambda update-function-code --function-name ml-predict --zip-file fileb://deployment.zip
```

### Pattern 2: Model in Lambda Layer (< 250MB)

```bash
# Create layer with model + dependencies
mkdir -p layer/python
pip install -t layer/python/ scikit-learn numpy
cp model.pkl layer/python/
cd layer && zip -r ../model-layer.zip . && cd ..

aws lambda publish-layer-version \
    --layer-name sklearn-model \
    --zip-file fileb://model-layer.zip \
    --compatible-runtimes python3.10
```

### Pattern 3: Model on EFS (Unlimited Size)

For models > 250MB (e.g., sentence transformers, small LLMs):

```python
import json
import torch
from transformers import AutoTokenizer, AutoModel

# EFS mounted at /mnt/models
MODEL_PATH = '/mnt/models/sentence-transformer'

# Load once at cold start
tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH)
model = AutoModel.from_pretrained(MODEL_PATH)
model.eval()

def lambda_handler(event, context):
    body = json.loads(event['body'])
    text = body['text']
    
    inputs = tokenizer(text, return_tensors='pt', truncation=True, max_length=512)
    with torch.no_grad():
        outputs = model(**inputs)
    
    embedding = outputs.last_hidden_state[:, 0, :].squeeze().tolist()
    
    return {
        'statusCode': 200,
        'body': json.dumps({'embedding': embedding}),
    }
```

**Lambda configuration for EFS:**
```python
# CDK
from aws_cdk import aws_lambda as lambda_, aws_efs as efs, aws_ec2 as ec2

fn = lambda_.Function(self, 'MLFunction',
    runtime=lambda_.Runtime.PYTHON_3_10,
    handler='lambda_function.lambda_handler',
    code=lambda_.Code.from_asset('lambda/'),
    memory_size=3072,
    timeout=Duration.seconds(60),
    vpc=vpc,
    filesystem=lambda_.FileSystem.from_efs_access_point(
        access_point, '/mnt/models'
    ),
)
```

### Pattern 4: Model on S3 + /tmp Caching

```python
import json
import os
import boto3
import pickle

s3 = boto3.client('s3')
MODEL_BUCKET = os.environ['MODEL_BUCKET']
MODEL_KEY = os.environ['MODEL_KEY']
LOCAL_PATH = '/tmp/model.pkl'

# Cache: only download if not in /tmp (persists between warm invocations)
model = None

def load_model():
    global model
    if model is not None:
        return model
    if not os.path.exists(LOCAL_PATH):
        s3.download_file(MODEL_BUCKET, MODEL_KEY, LOCAL_PATH)
    with open(LOCAL_PATH, 'rb') as f:
        model = pickle.load(f)
    return model

def lambda_handler(event, context):
    m = load_model()
    body = json.loads(event['body'])
    prediction = m.predict([body['features']])
    return {
        'statusCode': 200,
        'body': json.dumps({'prediction': prediction.tolist()}),
    }
```

---

## Lambda + API Gateway

### SAM Template (Complete)

```yaml
# template.yaml
AWSTemplateFormatVersion: '2010-09-09'
Transform: AWS::Serverless-2016-10-31
Description: ML Inference API

Globals:
  Function:
    Timeout: 30
    MemorySize: 3072
    Runtime: python3.10
    Environment:
      Variables:
        MODEL_BUCKET: !Ref ModelBucket
        MODEL_KEY: models/classifier/v2/model.pkl

Resources:
  MLFunction:
    Type: AWS::Serverless::Function
    Properties:
      CodeUri: src/
      Handler: lambda_function.lambda_handler
      Architectures: [x86_64]
      Events:
        Predict:
          Type: Api
          Properties:
            Path: /predict
            Method: post
            RestApiId: !Ref MLApi
      Policies:
        - S3ReadPolicy:
            BucketName: !Ref ModelBucket

  MLApi:
    Type: AWS::Serverless::Api
    Properties:
      StageName: prod
      Cors:
        AllowOrigin: "'*'"
        AllowMethods: "'POST,OPTIONS'"
      MethodSettings:
        - ResourcePath: /predict
          HttpMethod: POST
          ThrottlingRateLimit: 1000
          ThrottlingBurstLimit: 500

  ModelBucket:
    Type: AWS::S3::Bucket
    Properties:
      BucketName: !Sub ${AWS::StackName}-models

Outputs:
  ApiEndpoint:
    Value: !Sub "https://${MLApi}.execute-api.${AWS::Region}.amazonaws.com/prod/predict"
```

```bash
sam build && sam deploy --guided
```

---

## Step Functions for ML Workflows

### Complete State Machine: Train → Evaluate → Deploy

```json
{
  "Comment": "ML Training Pipeline with conditional deployment",
  "StartAt": "TrainModel",
  "States": {
    "TrainModel": {
      "Type": "Task",
      "Resource": "arn:aws:states:::sagemaker:createTrainingJob.sync",
      "Parameters": {
        "TrainingJobName.$": "States.Format('train-{}', $$.Execution.Name)",
        "AlgorithmSpecification": {
          "TrainingImage": "123456.dkr.ecr.us-east-1.amazonaws.com/trainer:latest",
          "TrainingInputMode": "File"
        },
        "RoleArn": "arn:aws:iam::123456:role/SageMakerRole",
        "ResourceConfig": {
          "InstanceCount": 1,
          "InstanceType": "ml.p3.2xlarge",
          "VolumeSizeInGB": 50
        },
        "InputDataConfig": [
          {
            "ChannelName": "train",
            "DataSource": {
              "S3DataSource": {
                "S3Uri": "s3://bucket/train/",
                "S3DataType": "S3Prefix"
              }
            }
          }
        ],
        "OutputDataConfig": {
          "S3OutputPath": "s3://bucket/output/"
        },
        "StoppingCondition": {"MaxRuntimeInSeconds": 3600}
      },
      "Next": "EvaluateModel",
      "Catch": [
        {"ErrorEquals": ["States.ALL"], "Next": "NotifyFailure"}
      ]
    },
    "EvaluateModel": {
      "Type": "Task",
      "Resource": "arn:aws:states:::lambda:invoke",
      "Parameters": {
        "FunctionName": "evaluate-model",
        "Payload": {
          "model_artifact.$": "$.ModelArtifacts.S3ModelArtifacts"
        }
      },
      "ResultPath": "$.evaluation",
      "Next": "CheckMetrics"
    },
    "CheckMetrics": {
      "Type": "Choice",
      "Choices": [
        {
          "Variable": "$.evaluation.Payload.accuracy",
          "NumericGreaterThanEquals": 0.85,
          "Next": "HumanApproval"
        }
      ],
      "Default": "ModelBelowThreshold"
    },
    "HumanApproval": {
      "Type": "Task",
      "Resource": "arn:aws:states:::sns:publish.waitForTaskToken",
      "Parameters": {
        "TopicArn": "arn:aws:sns:us-east-1:123456:ml-approvals",
        "Message": {
          "taskToken.$": "$$.Task.Token",
          "accuracy.$": "$.evaluation.Payload.accuracy",
          "model.$": "$.ModelArtifacts.S3ModelArtifacts"
        }
      },
      "TimeoutSeconds": 86400,
      "Next": "DeployModel",
      "Catch": [
        {"ErrorEquals": ["States.Timeout"], "Next": "ApprovalTimeout"}
      ]
    },
    "DeployModel": {
      "Type": "Task",
      "Resource": "arn:aws:states:::sagemaker:createEndpoint",
      "Parameters": {
        "EndpointName": "text-clf-prod",
        "EndpointConfigName.$": "$.endpointConfig"
      },
      "Next": "NotifySuccess"
    },
    "NotifySuccess": {
      "Type": "Task",
      "Resource": "arn:aws:states:::sns:publish",
      "Parameters": {
        "TopicArn": "arn:aws:sns:us-east-1:123456:ml-notifications",
        "Message": "Model deployed successfully"
      },
      "End": true
    },
    "ModelBelowThreshold": {
      "Type": "Task",
      "Resource": "arn:aws:states:::sns:publish",
      "Parameters": {
        "TopicArn": "arn:aws:sns:us-east-1:123456:ml-notifications",
        "Message.$": "States.Format('Model accuracy {} below threshold 0.85', $.evaluation.Payload.accuracy)"
      },
      "End": true
    },
    "NotifyFailure": {
      "Type": "Task",
      "Resource": "arn:aws:states:::sns:publish",
      "Parameters": {
        "TopicArn": "arn:aws:sns:us-east-1:123456:ml-alerts",
        "Message": "Training job failed"
      },
      "End": true
    },
    "ApprovalTimeout": {
      "Type": "Pass",
      "Result": "Approval timed out after 24 hours",
      "End": true
    }
  }
}
```

### Key Step Functions Patterns for ML

```
Retry with backoff (for transient failures):
"Retry": [
  {
    "ErrorEquals": ["ThrottlingException", "ServiceUnavailable"],
    "IntervalSeconds": 30,
    "MaxAttempts": 3,
    "BackoffRate": 2.0
  }
]

Parallel evaluation (test on multiple datasets):
"ParallelEval": {
  "Type": "Parallel",
  "Branches": [
    {"StartAt": "EvalDatasetA", ...},
    {"StartAt": "EvalDatasetB", ...},
    {"StartAt": "EvalDatasetC", ...}
  ],
  "Next": "AggregateResults"
}
```
