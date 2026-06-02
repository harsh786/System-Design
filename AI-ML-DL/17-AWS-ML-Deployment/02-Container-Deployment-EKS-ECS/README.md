# Container Deployment: EKS and ECS

## When to Use Containers vs SageMaker

```
Decision Tree:
│
├─ Do you need managed ML-specific features (Model Monitor, A/B testing, Registry)?
│  └─ YES → SageMaker Endpoints
│
├─ Do you need custom serving logic, multi-framework ensemble, or sidecar containers?
│  └─ YES → EKS (Kubernetes)
│
├─ Do you have < 10 models with simple HTTP serving?
│  └─ YES → ECS (simpler than EKS)
│
├─ Do you already have a Kubernetes team/cluster?
│  └─ YES → EKS
│
└─ Default → Start with SageMaker, migrate to EKS when you outgrow it
```

| Factor | SageMaker | EKS | ECS |
|--------|-----------|-----|-----|
| Setup time | Hours | Days-Weeks | Hours-Days |
| GPU scheduling | Managed | nvidia-device-plugin | EC2 launch type only |
| Custom preprocessing | Limited | Full control | Full control |
| Multi-model serving | Built-in (MMS) | Triton/KServe | Manual |
| Cost overhead | ~20-30% premium | Cluster ($73/mo) + nodes | No cluster fee |
| Team needed | ML engineer | ML + Platform engineer | ML + DevOps |

---

## Docker for ML

### Multi-Stage Dockerfile for ML Serving

```dockerfile
# Stage 1: Build dependencies
FROM python:3.10-slim as builder

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --target=/app/deps -r requirements.txt

# Stage 2: Runtime
FROM nvidia/cuda:12.1.0-runtime-ubuntu22.04 as runtime

# Install Python (minimal)
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.10 python3.10-distutils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy dependencies from builder
COPY --from=builder /app/deps /usr/local/lib/python3.10/site-packages/

# Copy application code
COPY src/ ./src/
COPY models/ ./models/

# Health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Non-root user
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8080

# Graceful shutdown handling
STOPSIGNAL SIGTERM

CMD ["python3.10", "-m", "uvicorn", "src.server:app", "--host", "0.0.0.0", "--port", "8080"]
```

### Model Baking vs Model Loading

| Pattern | Model Baking | Model Loading |
|---------|-------------|---------------|
| Where is model? | Inside Docker image | S3/EFS, loaded at startup |
| Image size | Large (2-10GB) | Small (500MB) |
| Deploy speed | Slow (pull large image) | Fast (small image) + load time |
| Model update | Rebuild + redeploy | Update S3 path, restart |
| Best for | Stable models, CI/CD | Frequent model updates |

**Model loading pattern:**
```python
# src/server.py
import os
import boto3
import torch
from fastapi import FastAPI
from contextlib import asynccontextmanager

model = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global model
    # Load model from S3 at startup
    s3 = boto3.client('s3')
    s3.download_file(
        os.environ['MODEL_BUCKET'],
        os.environ['MODEL_KEY'],
        '/tmp/model.pt'
    )
    model = torch.jit.load('/tmp/model.pt', map_location='cuda:0')
    model.eval()
    yield
    # Cleanup on shutdown
    del model
    torch.cuda.empty_cache()

app = FastAPI(lifespan=lifespan)

@app.get('/health')
def health():
    return {'status': 'healthy', 'model_loaded': model is not None}

@app.post('/predict')
async def predict(request: dict):
    # inference logic
    with torch.no_grad():
        result = model(preprocess(request['input']))
    return {'prediction': result.tolist()}
```

---

## EKS Deployment

### GPU Node Group Setup

```yaml
# eks-gpu-nodegroup.yaml
apiVersion: eksctl.io/v1alpha5
kind: ClusterConfig

metadata:
  name: ml-cluster
  region: us-east-1

managedNodeGroups:
  - name: gpu-workers
    instanceType: g4dn.xlarge
    minSize: 0
    maxSize: 10
    desiredCapacity: 2
    labels:
      node-type: gpu
      nvidia.com/gpu: "true"
    taints:
      - key: nvidia.com/gpu
        value: "true"
        effect: NoSchedule
    volumeSize: 100
    ami: auto
    ssh:
      allow: false

  - name: cpu-workers
    instanceType: m5.2xlarge
    minSize: 2
    maxSize: 20
    desiredCapacity: 3
    labels:
      node-type: cpu
```

```bash
# Install NVIDIA device plugin (required for GPU scheduling)
kubectl apply -f https://raw.githubusercontent.com/NVIDIA/k8s-device-plugin/v0.14.0/nvidia-device-plugin.yml
```

### Model Serving Deployment

```yaml
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: text-classifier
  labels:
    app: text-classifier
    version: v2
spec:
  replicas: 3
  selector:
    matchLabels:
      app: text-classifier
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0  # Zero-downtime
  template:
    metadata:
      labels:
        app: text-classifier
        version: v2
      annotations:
        prometheus.io/scrape: "true"
        prometheus.io/port: "8080"
    spec:
      tolerations:
        - key: nvidia.com/gpu
          operator: Exists
          effect: NoSchedule
      containers:
        - name: model-server
          image: 123456.dkr.ecr.us-east-1.amazonaws.com/text-classifier:v2
          ports:
            - containerPort: 8080
          resources:
            requests:
              memory: "4Gi"
              cpu: "2"
              nvidia.com/gpu: "1"
            limits:
              memory: "8Gi"
              cpu: "4"
              nvidia.com/gpu: "1"
          env:
            - name: MODEL_BUCKET
              value: "ml-models-prod"
            - name: MODEL_KEY
              value: "text-classifier/v2/model.pt"
            - name: BATCH_SIZE
              value: "32"
          readinessProbe:
            httpGet:
              path: /health
              port: 8080
            initialDelaySeconds: 60  # Model loading time
            periodSeconds: 10
          livenessProbe:
            httpGet:
              path: /health
              port: 8080
            initialDelaySeconds: 120
            periodSeconds: 30
          lifecycle:
            preStop:
              exec:
                command: ["/bin/sh", "-c", "sleep 15"]  # Graceful drain
---
apiVersion: v1
kind: Service
metadata:
  name: text-classifier
spec:
  selector:
    app: text-classifier
  ports:
    - port: 80
      targetPort: 8080
  type: ClusterIP
---
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: text-classifier
  annotations:
    kubernetes.io/ingress.class: alb
    alb.ingress.kubernetes.io/scheme: internet-facing
    alb.ingress.kubernetes.io/target-type: ip
    alb.ingress.kubernetes.io/healthcheck-path: /health
spec:
  rules:
    - http:
        paths:
          - path: /predict
            pathType: Prefix
            backend:
              service:
                name: text-classifier
                port:
                  number: 80
```

### HPA on Custom Metrics

```yaml
# hpa.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: text-classifier-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: text-classifier
  minReplicas: 2
  maxReplicas: 20
  metrics:
    # Scale on GPU utilization
    - type: Pods
      pods:
        metric:
          name: gpu_utilization
        target:
          type: AverageValue
          averageValue: "70"
    # Scale on request latency
    - type: Pods
      pods:
        metric:
          name: http_request_duration_seconds_p95
        target:
          type: AverageValue
          averageValue: "200m"  # 200ms
    # Scale on queue depth
    - type: External
      external:
        metric:
          name: sqs_queue_depth
          selector:
            matchLabels:
              queue: inference-requests
        target:
          type: AverageValue
          averageValue: "10"
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 60
      policies:
        - type: Pods
          value: 4
          periodSeconds: 60
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
        - type: Pods
          value: 1
          periodSeconds: 120
```

### Canary Deployment with Istio

```yaml
# canary.yaml
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: text-classifier
spec:
  hosts:
    - text-classifier
  http:
    - route:
        - destination:
            host: text-classifier
            subset: stable
          weight: 90
        - destination:
            host: text-classifier
            subset: canary
          weight: 10
---
apiVersion: networking.istio.io/v1beta1
kind: DestinationRule
metadata:
  name: text-classifier
spec:
  host: text-classifier
  subsets:
    - name: stable
      labels:
        version: v1
    - name: canary
      labels:
        version: v2
```

### NVIDIA Triton on EKS

```yaml
# triton-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: triton-inference
spec:
  replicas: 2
  selector:
    matchLabels:
      app: triton
  template:
    metadata:
      labels:
        app: triton
    spec:
      containers:
        - name: triton
          image: nvcr.io/nvidia/tritonserver:23.10-py3
          args:
            - tritonserver
            - --model-repository=s3://ml-models/triton-repo/
            - --model-control-mode=poll
            - --repository-poll-secs=60
          ports:
            - containerPort: 8000  # HTTP
            - containerPort: 8001  # gRPC
            - containerPort: 8002  # Metrics
          resources:
            limits:
              nvidia.com/gpu: "1"
          readinessProbe:
            httpGet:
              path: /v2/health/ready
              port: 8000
            initialDelaySeconds: 30
```

---

## ECS Deployment

### Task Definition

```json
{
  "family": "text-classifier",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["EC2"],
  "cpu": "4096",
  "memory": "16384",
  "executionRoleArn": "arn:aws:iam::123456:role/ecsTaskExecutionRole",
  "taskRoleArn": "arn:aws:iam::123456:role/ecsTaskRole",
  "containerDefinitions": [
    {
      "name": "model-server",
      "image": "123456.dkr.ecr.us-east-1.amazonaws.com/text-classifier:v2",
      "portMappings": [
        {"containerPort": 8080, "protocol": "tcp"}
      ],
      "resourceRequirements": [
        {"type": "GPU", "value": "1"}
      ],
      "environment": [
        {"name": "MODEL_BUCKET", "value": "ml-models-prod"},
        {"name": "MODEL_KEY", "value": "text-classifier/v2/model.pt"}
      ],
      "healthCheck": {
        "command": ["CMD-SHELL", "curl -f http://localhost:8080/health || exit 1"],
        "interval": 30,
        "timeout": 10,
        "retries": 3,
        "startPeriod": 120
      },
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/text-classifier",
          "awslogs-region": "us-east-1",
          "awslogs-stream-prefix": "ecs"
        }
      }
    }
  ],
  "placementConstraints": [
    {"type": "memberOf", "expression": "attribute:ecs.instance-type =~ g4dn.*"}
  ]
}
```

### ECS Service with ALB

```json
{
  "serviceName": "text-classifier-service",
  "cluster": "ml-cluster",
  "taskDefinition": "text-classifier:5",
  "desiredCount": 2,
  "launchType": "EC2",
  "loadBalancers": [
    {
      "targetGroupArn": "arn:aws:elasticloadbalancing:us-east-1:123456:targetgroup/text-clf/abc123",
      "containerName": "model-server",
      "containerPort": 8080
    }
  ],
  "deploymentConfiguration": {
    "maximumPercent": 200,
    "minimumHealthyPercent": 100,
    "deploymentCircuitBreaker": {
      "enable": true,
      "rollback": true
    }
  },
  "serviceRegistries": [
    {"registryArn": "arn:aws:servicediscovery:us-east-1:123456:service/srv-abc123"}
  ]
}
```

### ECS Auto Scaling

```python
import boto3

autoscaling = boto3.client('application-autoscaling')

# Register target
autoscaling.register_scalable_target(
    ServiceNamespace='ecs',
    ResourceId='service/ml-cluster/text-classifier-service',
    ScalableDimension='ecs:service:DesiredCount',
    MinCapacity=2,
    MaxCapacity=10,
)

# Target tracking on CPU
autoscaling.put_scaling_policy(
    PolicyName='cpu-target-tracking',
    ServiceNamespace='ecs',
    ResourceId='service/ml-cluster/text-classifier-service',
    ScalableDimension='ecs:service:DesiredCount',
    PolicyType='TargetTrackingScaling',
    TargetTrackingScalingPolicyConfiguration={
        'TargetValue': 60.0,
        'PredefinedMetricSpecification': {
            'PredefinedMetricType': 'ECSServiceAverageCPUUtilization'
        },
        'ScaleInCooldown': 300,
        'ScaleOutCooldown': 60,
    },
)
```

---

## ECR (Container Registry)

### Push/Pull Workflow

```bash
# Authenticate
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin 123456.dkr.ecr.us-east-1.amazonaws.com

# Create repository
aws ecr create-repository --repository-name text-classifier --image-scanning-configuration scanOnPush=true

# Build, tag, push
docker build -t text-classifier:v2 .
docker tag text-classifier:v2 123456.dkr.ecr.us-east-1.amazonaws.com/text-classifier:v2
docker push 123456.dkr.ecr.us-east-1.amazonaws.com/text-classifier:v2
```

### Lifecycle Policy (Cleanup)

```json
{
  "rules": [
    {
      "rulePriority": 1,
      "description": "Keep last 10 tagged images",
      "selection": {
        "tagStatus": "tagged",
        "tagPrefixList": ["v"],
        "countType": "imageCountMoreThan",
        "countNumber": 10
      },
      "action": {"type": "expire"}
    },
    {
      "rulePriority": 2,
      "description": "Delete untagged images older than 7 days",
      "selection": {
        "tagStatus": "untagged",
        "countType": "sinceImagePushed",
        "countUnit": "days",
        "countNumber": 7
      },
      "action": {"type": "expire"}
    }
  ]
}
```
