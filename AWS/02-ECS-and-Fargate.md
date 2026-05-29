# Amazon ECS & AWS Fargate - Complete Guide

## 1. ECS Architecture Overview

### What is ECS (Elastic Container Service)

Amazon ECS is a fully managed container orchestration service that allows you to run, stop, and manage Docker containers on a cluster. It eliminates the need to install, operate, and scale your own cluster management infrastructure.

ECS is deeply integrated with the AWS ecosystem — IAM, VPC, CloudWatch, ALB, Secrets Manager, and more — making it the natural choice for teams already invested in AWS.

### ECS vs Docker Swarm vs Kubernetes

| Aspect | ECS | Docker Swarm | Kubernetes (EKS) |
|--------|-----|--------------|-------------------|
| Managed by | AWS (fully managed control plane) | Self-managed | AWS manages control plane (EKS) |
| Complexity | Low | Low | High |
| Ecosystem | AWS-native integrations | Docker ecosystem | Largest open-source ecosystem |
| Portability | AWS-locked | Docker-native | Multi-cloud, on-prem |
| Scaling | Built-in auto scaling | Manual/scripted | HPA, VPA, Cluster Autoscaler |
| Networking | awsvpc, bridge, host | Overlay network | CNI plugins (VPC CNI on EKS) |
| Service Mesh | Service Connect | None built-in | Istio, Linkerd, App Mesh |
| Learning Curve | Low | Low | Steep |
| Cost | No control plane fee | Free | $0.10/hr per cluster ($73/mo) |

### Key Components

```
┌─────────────────────────────────────────────────────────┐
│                      ECS CLUSTER                         │
│                                                         │
│  ┌─────────────────────┐   ┌─────────────────────────┐ │
│  │   ECS SERVICE A     │   │    ECS SERVICE B        │ │
│  │                     │   │                         │ │
│  │  ┌──────┐ ┌──────┐ │   │  ┌──────┐ ┌──────┐    │ │
│  │  │Task 1│ │Task 2│ │   │  │Task 1│ │Task 2│    │ │
│  │  └──────┘ └──────┘ │   │  └──────┘ └──────┘    │ │
│  └─────────────────────┘   └─────────────────────────┘ │
│                                                         │
│  Container Instances (EC2) OR Fargate                   │
└─────────────────────────────────────────────────────────┘
```

- **Cluster**: Logical grouping of tasks and services. Can span multiple AZs. A cluster can mix EC2 and Fargate launch types.
- **Task Definition**: Blueprint (like a Dockerfile on steroids). Describes one or more containers — images, CPU, memory, ports, volumes, IAM roles, logging.
- **Task**: A running instantiation of a task definition. One task can run 1-10 containers (sidecars pattern).
- **Service**: Maintains desired count of tasks, handles rolling deploys, integrates with load balancers, and manages auto scaling.
- **Container Instance**: An EC2 instance running the ECS agent, registered to a cluster (EC2 launch type only).

### ECS Control Plane and Data Plane

**Control Plane** (fully managed by AWS):
- Scheduling decisions (where to place tasks)
- Service orchestration (maintaining desired count)
- API endpoint for all ECS operations
- Stores cluster state and task definitions

**Data Plane** (where containers actually run):
- **EC2 Launch Type**: Your EC2 instances running the ECS Container Agent
- **Fargate Launch Type**: AWS-managed infrastructure (Firecracker microVMs)
- **ECS Anywhere**: On-premises servers registered as external instances

### Container Agent on EC2 Instances

The ECS Container Agent is an open-source Go application that runs on each EC2 container instance:

- Communicates with ECS control plane via HTTPS
- Starts/stops containers as directed by the scheduler
- Reports task status and resource utilization
- Manages container lifecycle and health checks
- Handles image pulls from ECR or Docker Hub
- Runs as a Docker container itself (`amazon/amazon-ecs-agent`)

Configuration via `/etc/ecs/ecs.config`:
```bash
ECS_CLUSTER=my-cluster
ECS_ENABLE_TASK_IAM_ROLE=true
ECS_ENABLE_CONTAINER_METADATA=true
ECS_AVAILABLE_LOGGING_DRIVERS=["json-file","awslogs","fluentd"]
ECS_ENABLE_SPOT_INSTANCE_DRAINING=true
```

---

## 2. Task Definitions (Detailed)

### JSON Structure

```json
{
  "family": "my-web-app",
  "taskRoleArn": "arn:aws:iam::123456789:role/ecsTaskRole",
  "executionRoleArn": "arn:aws:iam::123456789:role/ecsTaskExecutionRole",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "512",
  "memory": "1024",
  "runtimePlatform": {
    "cpuArchitecture": "X86_64",
    "operatingSystemFamily": "LINUX"
  },
  "containerDefinitions": [...],
  "volumes": [...],
  "placementConstraints": [...],
  "ephemeralStorage": {
    "sizeInGiB": 30
  }
}
```

### Container Definitions (All Fields)

```json
{
  "name": "web-app",
  "image": "123456789.dkr.ecr.us-east-1.amazonaws.com/my-app:v1.2.3",
  "cpu": 256,
  "memory": 512,
  "memoryReservation": 256,
  "portMappings": [
    {
      "containerPort": 8080,
      "hostPort": 8080,
      "protocol": "tcp",
      "appProtocol": "http",
      "name": "web-app-8080"
    }
  ],
  "essential": true,
  "entryPoint": ["/bin/sh", "-c"],
  "command": ["node", "server.js"],
  "environment": [
    {"name": "NODE_ENV", "value": "production"},
    {"name": "PORT", "value": "8080"}
  ],
  "secrets": [
    {
      "name": "DB_PASSWORD",
      "valueFrom": "arn:aws:secretsmanager:us-east-1:123456789:secret:db-pass"
    },
    {
      "name": "API_KEY",
      "valueFrom": "arn:aws:ssm:us-east-1:123456789:parameter/api-key"
    }
  ],
  "logConfiguration": {
    "logDriver": "awslogs",
    "options": {
      "awslogs-group": "/ecs/my-web-app",
      "awslogs-region": "us-east-1",
      "awslogs-stream-prefix": "ecs"
    }
  },
  "healthCheck": {
    "command": ["CMD-SHELL", "curl -f http://localhost:8080/health || exit 1"],
    "interval": 30,
    "timeout": 5,
    "retries": 3,
    "startPeriod": 60
  },
  "dependsOn": [
    {
      "containerName": "init-container",
      "condition": "SUCCESS"
    },
    {
      "containerName": "datadog-agent",
      "condition": "HEALTHY"
    }
  ],
  "mountPoints": [
    {
      "sourceVolume": "efs-data",
      "containerPath": "/data",
      "readOnly": false
    }
  ],
  "ulimits": [
    {"name": "nofile", "softLimit": 65536, "hardLimit": 65536}
  ],
  "linuxParameters": {
    "initProcessEnabled": true
  },
  "dockerLabels": {
    "com.datadoghq.ad.instances": "[{\"host\":\"%%host%%\",\"port\":8080}]"
  },
  "stopTimeout": 30
}
```

### Task-Level vs Container-Level CPU/Memory

| Aspect | Task-Level | Container-Level |
|--------|-----------|-----------------|
| Required for | Fargate (mandatory) | EC2 (optional but recommended) |
| Purpose | Total resources for all containers in the task | Per-container limits/reservations |
| `cpu` | Hard limit for task | Relative weight (EC2) or hard limit |
| `memory` | Hard limit for task | Hard limit per container |
| `memoryReservation` | N/A | Soft limit (container can burst above) |

**Key Rule**: Sum of container-level CPU/memory cannot exceed task-level values.

### Network Modes

| Mode | Description | Use Case |
|------|-------------|----------|
| **awsvpc** | Each task gets its own ENI with private IP | Fargate (required), recommended for EC2 |
| **bridge** | Docker's default bridge network | Legacy, dynamic port mapping |
| **host** | Container uses host's network namespace | Maximum network performance |
| **none** | No external connectivity | Batch processing with no network needs |

**awsvpc** advantages:
- Security groups per task (not per instance)
- Full VPC features (flow logs, routing, NACLs)
- Simplified service discovery
- Required for Fargate

### Task Role vs Execution Role

```
┌─────────────────────────────────────────────────────┐
│                                                     │
│  EXECUTION ROLE                 TASK ROLE           │
│  (What ECS agent can do)        (What app can do)  │
│                                                     │
│  • Pull images from ECR         • Access DynamoDB   │
│  • Write to CloudWatch Logs     • Read from S3      │
│  • Fetch secrets from SM/SSM    • Publish to SNS    │
│  • Get auth tokens              • Call other APIs   │
│                                                     │
└─────────────────────────────────────────────────────┘
```

**Execution Role** (`executionRoleArn`):
- Used by the ECS agent (not the container itself)
- Needed to pull images from ECR
- Needed to send logs to CloudWatch
- Needed to retrieve secrets at container startup
- AWS managed policy: `AmazonECSTaskExecutionRolePolicy`

**Task Role** (`taskRoleArn`):
- Assumed by the application code inside the container
- Credentials available via container credential provider (169.254.170.2)
- Follows least privilege — each service gets only the permissions it needs

### Volumes

**EFS (Elastic File System)**:
```json
"volumes": [
  {
    "name": "efs-data",
    "efsVolumeConfiguration": {
      "fileSystemId": "fs-12345678",
      "rootDirectory": "/app-data",
      "transitEncryption": "ENABLED",
      "authorizationConfig": {
        "accessPointId": "fsap-12345678",
        "iam": "ENABLED"
      }
    }
  }
]
```

**Bind Mounts** (share between containers in same task):
```json
"volumes": [{"name": "shared-tmp"}]
// Container A: mountPoints: [{"sourceVolume": "shared-tmp", "containerPath": "/output"}]
// Container B: mountPoints: [{"sourceVolume": "shared-tmp", "containerPath": "/input"}]
```

### Logging Drivers

| Driver | Destination | Use Case |
|--------|------------|----------|
| `awslogs` | CloudWatch Logs | Default, simplest |
| `fluentd` | Fluentd endpoint | Custom routing |
| `splunk` | Splunk HEC | Enterprise Splunk |
| `awsfirelens` | Fluent Bit/Fluentd sidecar | Advanced routing, transformation |

**FireLens Example** (route to multiple destinations):
```json
{
  "name": "log-router",
  "image": "amazon/aws-for-fluent-bit:latest",
  "essential": true,
  "firelensConfiguration": {
    "type": "fluentbit",
    "options": {
      "config-file-type": "file",
      "config-file-value": "/fluent-bit/configs/custom.conf"
    }
  }
}
```

### Placement Constraints (EC2 only)

```json
"placementConstraints": [
  {
    "type": "memberOf",
    "expression": "attribute:ecs.instance-type =~ t3.*"
  },
  {
    "type": "distinctInstance"
  }
]
```

- `memberOf`: Cluster query language expression
- `distinctInstance`: Each task on a different instance (HA)

---

## 3. ECS Services

### Service Types

| Type | Behavior | Use Case |
|------|----------|----------|
| **REPLICA** | Maintains N copies across cluster | Web apps, APIs |
| **DAEMON** | Exactly one task per container instance | Log agents, monitoring |

### Deployment Controllers

**1. ECS (Rolling Update)** — Default:
```json
"deploymentConfiguration": {
  "minimumHealthyPercent": 100,
  "maximumPercent": 200,
  "deploymentCircuitBreaker": {
    "enable": true,
    "rollback": true
  }
}
```

- `minimumHealthyPercent: 100` + `maximumPercent: 200` → Zero downtime (spins up new before draining old)
- `minimumHealthyPercent: 50` + `maximumPercent: 100` → In-place (replace half at a time, saves resources)

**2. CODE_DEPLOY (Blue/Green)**:
- Uses AWS CodeDeploy
- Creates new task set (green), shifts traffic via ALB target groups
- Supports canary (10% → 100%), linear (10% every 5 min), all-at-once
- Automatic rollback on alarms

**3. EXTERNAL**:
- Third-party deployment controller
- ECS does not manage deployments

### Load Balancing

**ALB (Application Load Balancer)**:
- Path-based routing: `/api/*` → service A, `/web/*` → service B
- Host-based routing: `api.example.com` → service A
- Dynamic port mapping: ALB discovers container ports automatically (bridge mode)
- Health checks at target group level
- Supports gRPC, WebSockets, HTTP/2

**NLB (Network Load Balancer)**:
- TCP/UDP/TLS traffic
- Ultra-low latency, millions of requests/sec
- Static IP / Elastic IP support
- Required for non-HTTP services (databases, custom protocols)

### Service Discovery (AWS Cloud Map)

```
ECS Service → Cloud Map Service → Route 53 Private Hosted Zone
                                   → A records (awsvpc tasks)
                                   → SRV records (bridge mode)
```

Configuration:
```json
"serviceRegistries": [
  {
    "registryArn": "arn:aws:servicediscovery:us-east-1:123456789:service/srv-xxx",
    "containerName": "web",
    "containerPort": 8080
  }
]
```

Services discover each other via DNS: `http://payment-service.production.local:8080`

### Service Connect

Service Connect is ECS's built-in service mesh (powered by Envoy proxy):

- Automatic sidecar proxy injection
- Client-side load balancing
- Automatic retries and circuit breaking
- Per-service traffic metrics in CloudWatch
- No need to manage Cloud Map namespaces manually

```json
"serviceConnectConfiguration": {
  "enabled": true,
  "namespace": "production",
  "services": [
    {
      "portName": "web-app-8080",
      "clientAliases": [{"port": 8080, "dnsName": "web-app"}]
    }
  ]
}
```

### Auto Scaling

**Target Tracking** (recommended):
```json
{
  "targetValue": 75.0,
  "predefinedMetricSpecification": {
    "predefinedMetricType": "ECSServiceAverageCPUUtilization"
  },
  "scaleInCooldown": 300,
  "scaleOutCooldown": 60
}
```

Predefined metrics:
- `ECSServiceAverageCPUUtilization`
- `ECSServiceAverageMemoryUtilization`
- `ALBRequestCountPerTarget`

**Step Scaling**: Custom CloudWatch alarms with different scaling amounts at different thresholds.

**Scheduled Scaling**: Scale based on predictable traffic patterns (e.g., scale up at 8 AM, down at 10 PM).

### Circuit Breaker

Detects deployment failures and automatically rolls back:

```json
"deploymentCircuitBreaker": {
  "enable": true,
  "rollback": true
}
```

Logic: If tasks repeatedly fail to reach RUNNING state or fail health checks, ECS stops the deployment and rolls back to the last stable version.

### Capacity Providers

Map services to infrastructure strategies:

```json
"capacityProviderStrategy": [
  {"capacityProvider": "FARGATE", "weight": 1, "base": 2},
  {"capacityProvider": "FARGATE_SPOT", "weight": 3}
]
```

- `base`: Minimum tasks on this provider (guaranteed)
- `weight`: Ratio of remaining tasks

For EC2: Capacity providers manage Auto Scaling Groups with managed scaling and managed termination protection.

---

## 4. Fargate (Serverless Containers)

### How Fargate Works

1. You submit a task definition (image, CPU, memory, networking)
2. AWS provisions a Firecracker microVM in their fleet
3. Your container runs in an isolated kernel (not shared with other customers)
4. ENI attached to your VPC — full networking capabilities
5. When task stops, the microVM is destroyed (no data persistence)

**Firecracker**: Open-source VMM (Virtual Machine Monitor) created by AWS. Same technology powers Lambda. Boots in <125ms, minimal memory overhead.

### Fargate vs EC2 Launch Type Decision Matrix

| Factor | Choose Fargate | Choose EC2 |
|--------|---------------|------------|
| Ops overhead | Want zero infrastructure management | Willing to manage instances |
| Cost (steady) | Higher per-unit cost | Lower with Reserved Instances |
| Cost (variable) | Better for spiky/unpredictable loads | Better for steady baseline |
| GPU | Not supported | Required for ML/AI workloads |
| Privileged mode | Not supported | Need Docker-in-Docker |
| Custom AMI | Not applicable | Need custom kernel modules |
| Spot savings | Up to 70% with Fargate Spot | Up to 90% with EC2 Spot |
| Startup time | ~30-60s cold start | Instant (on running instances) |
| Storage | Up to 200 GiB ephemeral | Instance store (TB+) |
| Windows | Supported (not on Spot) | Full support |
| Compliance | Isolated microVM per task | Dedicated hosts/instances available |

### Valid CPU/Memory Combinations

| CPU (vCPU) | Memory Range | Increments |
|------------|--------------|------------|
| 0.25 | 0.5, 1, 2 GB | Fixed values |
| 0.5 | 1, 2, 3, 4 GB | 1 GB |
| 1 | 2, 3, 4, 5, 6, 7, 8 GB | 1 GB |
| 2 | 4–16 GB | 1 GB |
| 4 | 8–30 GB | 1 GB |
| 8 | 16–60 GB | 4 GB |
| 16 | 32–120 GB | 8 GB |

**Important**: These are the ONLY valid combinations. You cannot set arbitrary values.

### Fargate Spot

- Up to 70% discount compared to On-Demand Fargate
- AWS can reclaim capacity with a **2-minute warning** (SIGTERM sent)
- Warning delivered via task metadata endpoint and EventBridge
- Not suitable for: stateful workloads, real-time critical services
- Ideal for: batch processing, dev/test, fault-tolerant workers, CI/CD jobs
- Not available for Windows containers or ARM tasks (as of now)

Handle graceful shutdown:
```python
import signal
import sys

def handler(signum, frame):
    # Save state, drain connections, cleanup
    print("Received SIGTERM, shutting down gracefully...")
    sys.exit(0)

signal.signal(signal.SIGTERM, handler)
```

### Platform Versions

| Version | Key Features |
|---------|-------------|
| 1.4.0 (LATEST) | EFS support, ephemeral storage up to 200 GiB, container dependencies, SYS_PTRACE cap, larger task sizes |
| 1.3.0 | Task recycling, Secrets Manager, awslogs improvements |
| 1.2.0 | Container health checks, secrets |
| 1.1.0 | Task metadata endpoint, service discovery |
| 1.0.0 | Initial release |

Always use `LATEST` or explicitly `1.4.0` for new workloads.

### Fargate Ephemeral Storage

- Default: 20 GiB (free, included in price)
- Configurable: 21–200 GiB (additional charges per GB-hour)
- Shared among all containers in the task
- Encrypted at rest
- Destroyed when task stops

```json
"ephemeralStorage": {
  "sizeInGiB": 100
}
```

### Fargate Limitations

- No GPU support (use EC2 with GPU instances like P3/G4)
- No privileged containers (no Docker-in-Docker)
- No custom kernel modules
- No Windows containers on Spot
- Maximum 200 GiB ephemeral storage
- ENI limit can cause placement failures in small subnets
- Cold start latency (~30-60s for image pull + container start)
- No daemon tasks (DAEMON service type is EC2-only)
- Cannot mount instance store volumes

---

## 5. ECS Networking

### awsvpc Mode Deep Dive

Each task gets its own Elastic Network Interface (ENI):

```
┌──────────────────────────────┐
│         VPC Subnet           │
│                              │
│  Task A ─── ENI (10.0.1.5)  │   ← Own security group
│  Task B ─── ENI (10.0.1.6)  │   ← Own security group
│  Task C ─── ENI (10.0.1.7)  │   ← Own security group
│                              │
└──────────────────────────────┘
```

Benefits:
- Fine-grained network access control per task
- VPC Flow Logs per task
- Each task is addressable by IP
- Compatible with all VPC features

Limitation (EC2 only): ENI density per instance. Solution: Enable `awsvpcTrunking` for higher ENI limits.

### VPC Endpoints for ECR

Required for Fargate tasks in private subnets:

| Endpoint | Type | Purpose |
|----------|------|---------|
| `com.amazonaws.region.ecr.api` | Interface | ECR API calls |
| `com.amazonaws.region.ecr.dkr` | Interface | Docker image layer pulls |
| `com.amazonaws.region.s3` | Gateway | Image layers stored in S3 |
| `com.amazonaws.region.logs` | Interface | CloudWatch Logs |
| `com.amazonaws.region.secretsmanager` | Interface | Secrets retrieval |

Without these endpoints, tasks in private subnets need a NAT Gateway ($32+/month + data charges).

### Inter-Service Communication Patterns

1. **ALB-based**: Services register with ALB, communicate via ALB DNS
2. **Service Discovery (Cloud Map)**: Direct task-to-task via DNS (lower latency, no LB cost)
3. **Service Connect**: Envoy sidecar mesh, best of both worlds
4. **App Mesh**: Full-featured service mesh with traffic policies (being superseded by Service Connect)

---

## 6. ECR (Elastic Container Registry)

### Private Repositories

- Each AWS account gets one registry per region
- Registry: `<account_id>.dkr.ecr.<region>.amazonaws.com`
- Repository: Holds images for one application (e.g., `my-app`)
- Images tagged with versions: `my-app:v1.2.3`, `my-app:latest`

### Lifecycle Policies

Automatically clean up old images:

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
      "description": "Expire untagged images after 7 days",
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

### Image Scanning

- **Basic Scanning**: CVE scanning using Clair (free, on-push or manual)
- **Enhanced Scanning**: Uses Amazon Inspector, continuous scanning, OS + programming language packages, richer findings

### Cross-Region & Cross-Account

- **Replication**: Automatic push replication to other regions/accounts
- **Cross-account**: Resource-based policies on repositories

```json
{
  "replicationConfiguration": {
    "rules": [
      {
        "destinations": [
          {"region": "eu-west-1", "registryId": "123456789012"}
        ]
      }
    ]
  }
}
```

### Pull-Through Cache

Cache upstream registries in your ECR:
- Docker Hub: `docker.io`
- GitHub Container Registry: `ghcr.io`
- Quay: `quay.io`
- ECR Public: `public.ecr.aws`

Reduces external dependencies and speeds up pulls.

### Image Tag Immutability

When enabled, prevents overwriting existing tags. Forces teams to use unique tags (e.g., git SHA), preventing "latest" drift issues.

---

## 7. Monitoring & Observability

### CloudWatch Container Insights

Automatically collects:
- CPU/Memory utilization (per task, service, cluster)
- Network I/O (bytes in/out)
- Storage read/write
- Task count (running, pending, desired)
- Container instance metrics (EC2)

Enable at cluster level:
```bash
aws ecs update-cluster-settings --cluster my-cluster \
  --settings name=containerInsights,value=enabled
```

### Custom Metrics with Sidecar

Run CloudWatch agent or StatsD sidecar alongside your application container:

```json
{
  "name": "cloudwatch-agent",
  "image": "amazon/cloudwatch-agent:latest",
  "essential": false,
  "secrets": [
    {
      "name": "CW_CONFIG_CONTENT",
      "valueFrom": "arn:aws:ssm:us-east-1:123456789:parameter/cw-agent-config"
    }
  ]
}
```

### FireLens Log Routing

Route logs to multiple destinations simultaneously:
- CloudWatch Logs (operational)
- S3 (archival)
- Elasticsearch/OpenSearch (search)
- Datadog/Splunk (third-party)

### X-Ray Integration

Add X-Ray daemon as sidecar:
```json
{
  "name": "xray-daemon",
  "image": "amazon/aws-xray-daemon",
  "cpu": 32,
  "memoryReservation": 256,
  "portMappings": [{"containerPort": 2000, "protocol": "udp"}],
  "essential": false
}
```

Application sends traces to `localhost:2000/udp`.

### ECS Exec (Interactive Debugging)

SSM-based exec into running containers (like `kubectl exec`):

```bash
aws ecs execute-command --cluster my-cluster \
  --task arn:aws:ecs:us-east-1:123456789:task/my-cluster/abc123 \
  --container web-app \
  --command "/bin/sh" \
  --interactive
```

Requirements:
- SSM agent in container (automatically added for Fargate 1.4.0+)
- Task role needs SSM permissions
- `enableExecuteCommand: true` on service/task

---

## 8. Security

### Task IAM Roles

Each service/task gets its own IAM role — principle of least privilege:

```
Payment Service Task Role:
  → DynamoDB: Read/Write to payments table
  → SQS: Send to notifications queue
  → KMS: Decrypt payment data

User Service Task Role:
  → DynamoDB: Read/Write to users table
  → S3: Read/Write to profile-pictures bucket
  → Cognito: Admin operations
```

Credentials delivered via task metadata endpoint (169.254.170.2), automatically rotated.

### Secrets Management

**In Task Definition:**
```json
"secrets": [
  {
    "name": "DATABASE_URL",
    "valueFrom": "arn:aws:secretsmanager:us-east-1:123:secret:prod/db-url"
  },
  {
    "name": "FEATURE_FLAGS",
    "valueFrom": "arn:aws:ssm:us-east-1:123:parameter/prod/feature-flags"
  }
]
```

- Secrets Manager: For credentials that rotate (DB passwords, API keys) — $0.40/secret/month
- SSM Parameter Store: For configuration that changes less often — free (standard) or $0.05/advanced

Secrets are injected as environment variables at container start. Execution role needs permission to read them.

### VPC Security Groups Per Task (awsvpc)

```
Web Task SG:       Inbound 443 from ALB SG
API Task SG:       Inbound 8080 from Web Task SG
DB Task SG:        Inbound 5432 from API Task SG only
```

This microsegmentation is only possible with awsvpc network mode.

### Interface VPC Endpoints

Keep all traffic private (no internet transit):
- ECR endpoints (image pulls)
- CloudWatch Logs endpoint (logging)
- Secrets Manager endpoint (secrets)
- S3 gateway endpoint (image layers)
- STS endpoint (IAM role assumption)

---

## 9. ECS vs EKS vs Lambda Comparison

| Feature | ECS | EKS | Lambda |
|---------|-----|-----|--------|
| **Orchestration** | AWS-native | Kubernetes | Event-driven |
| **Control Plane Cost** | Free | $73/month/cluster | Free |
| **Operational Overhead** | Low | High | Minimal |
| **Scaling Speed** | ~30-60s (Fargate) | ~30-60s (Fargate), minutes (nodes) | Milliseconds (warm), seconds (cold) |
| **Max Runtime** | Unlimited | Unlimited | 15 minutes |
| **Portability** | AWS only | Multi-cloud | AWS only |
| **Container Image** | Required | Required | Optional (supported) |
| **Networking** | VPC-native | VPC CNI | VPC (optional) |
| **GPU Support** | Yes (EC2) | Yes | No |
| **Service Mesh** | Service Connect | Istio/Linkerd/App Mesh | N/A |
| **CI/CD** | CodePipeline, any | ArgoCD, Flux, any | SAM, any |
| **IAM Granularity** | Per task | Per pod (IRSA) | Per function |
| **Spot/Savings** | Fargate Spot, EC2 Spot | EC2 Spot, Fargate Spot | N/A |
| **Learning Curve** | Low-Medium | High | Low |
| **Best For** | AWS-native container workloads | Multi-cloud, K8s ecosystem | Event-driven, short tasks |
| **Ecosystem** | AWS integrations | Massive K8s ecosystem | Serverless framework |
| **State** | Stateful possible (EFS) | Stateful (EBS CSI, EFS) | Stateless |
| **Windows** | Supported | Supported | Not supported |

---

## 10. Scenario-Based Interview Questions

### Q1: Deploy microservices with zero-downtime on ECS

**Answer:**

1. **Task Definition**: Use `awsvpc` network mode, define health check with appropriate `startPeriod` to allow warm-up
2. **Service Configuration**:
   - `minimumHealthyPercent: 100` — never kill old tasks before new ones are healthy
   - `maximumPercent: 200` — allow double capacity during deploy
   - Circuit breaker enabled with rollback
3. **ALB Integration**:
   - Register new tasks with target group
   - Health check grace period: Give new tasks time to warm up before ALB checks
   - Deregistration delay: 30-60s to drain existing connections
4. **Deployment**:
   - New task definition revision deployed
   - ECS starts new tasks → waits for health check → registers with ALB → drains old tasks → stops old tasks
5. **Signals**: Use `stopTimeout` (30s) to allow graceful shutdown (drain connections, complete in-flight requests)

### Q2: Fargate tasks OOM - Troubleshooting

**Answer:**

1. **Identify the issue**: Check stopped task reason — `OutOfMemoryError` in CloudWatch, `exitCode: 137` (SIGKILL from OOM killer)
2. **Analyze memory usage**: Container Insights → task memory utilization over time
3. **Root causes**:
   - Container `memory` hard limit too low
   - Memory leak in application
   - JVM: Heap not bounded (`-Xmx` not set, defaults to 25% of container memory)
   - Multiple containers in task competing for task-level memory
4. **Solutions**:
   - Increase task-level memory to next valid combination
   - Set `memoryReservation` (soft limit) lower than `memory` (hard limit) for burstable workloads
   - Fix application memory leak
   - JVM: Set `-Xmx` to ~75% of container memory limit
   - Monitor with CloudWatch alarm on `MemoryUtilization > 80%`

### Q3: Design cost-effective container strategy for variable traffic

**Answer:**

```
Capacity Provider Strategy:
┌─────────────────────────────────────────────┐
│  Base: 2 tasks on FARGATE (always available)│
│  Variable: 3:1 ratio FARGATE_SPOT:FARGATE   │
└─────────────────────────────────────────────┘
```

1. **Baseline (predictable)**: Fargate On-Demand with Compute Savings Plans (up to 50% discount)
2. **Burst capacity**: Fargate Spot (70% discount) for non-critical overflow
3. **Auto Scaling**: Target tracking on CPU (70%) with ALBRequestCountPerTarget as secondary
4. **Scheduled Scaling**: Scale down at night/weekends if traffic is predictable
5. **Right-sizing**: Start with smallest CPU/memory that works, monitor and adjust
6. **Multi-AZ**: Spread across AZs for both availability and Spot capacity diversity

Cost optimization: Savings Plans > Fargate Spot > Right-sizing > Scheduled scaling

### Q4: Handle secrets in ECS task definitions

**Answer:**

**Never** put secrets in environment variables directly (visible in console, API, logs).

**Best Practice:**
1. Store in Secrets Manager (rotatable) or SSM Parameter Store (static config)
2. Reference via `secrets` block in container definition (injected at startup)
3. Execution role grants access only to specific secrets
4. Encrypt with customer-managed KMS key for audit trail

```json
"secrets": [
  {"name": "DB_PASS", "valueFrom": "arn:aws:secretsmanager:..."},
  {"name": "API_KEY", "valueFrom": "arn:aws:ssm:...:parameter/prod/api-key"}
]
```

**Advanced**: For secrets that change without redeployment, fetch from Secrets Manager SDK in application code (not via task def injection, which only reads at start).

### Q5: Service discovery between microservices

**Answer:**

Three approaches, in order of recommendation:

1. **Service Connect** (recommended for new workloads):
   - Zero-config Envoy sidecar
   - Use endpoint name directly: `http://payment-service:8080`
   - Built-in retries, circuit breaking, metrics
   - No Cloud Map management needed

2. **Cloud Map + Service Discovery**:
   - DNS-based: `payment.prod.local` → A record → task IP
   - Works across services without Service Connect
   - SRV records provide port information

3. **ALB-based**:
   - All traffic flows through ALB
   - Higher latency, additional cost
   - Useful when you need path-based routing between services

### Q6: Blue/Green deployment on ECS with CodeDeploy

**Answer:**

Architecture:
```
ALB → Listener (port 443) → Target Group Blue (active)
                           → Target Group Green (standby)
```

Setup:
1. Service uses `CODE_DEPLOY` deployment controller
2. Two target groups configured on ALB
3. CodeDeploy application + deployment group targeting the ECS service
4. AppSpec file defines traffic shifting:

```yaml
version: 0.0
Resources:
  - TargetService:
      Type: AWS::ECS::Service
      Properties:
        TaskDefinition: <new-task-def-arn>
        LoadBalancerInfo:
          ContainerName: "web"
          ContainerPort: 8080
```

Traffic shifting options:
- `Canary10Percent5Minutes`: 10% for 5 min, then 100%
- `Linear10PercentEvery1Minute`: Gradual shift
- `AllAtOnce`: Instant flip

Rollback: Triggered by CloudWatch alarms (error rate, latency) or manual.

### Q7: ECS capacity providers strategy for mixed On-Demand/Spot

**Answer:**

```json
"capacityProviderStrategy": [
  {
    "capacityProvider": "FARGATE",
    "base": 3,
    "weight": 1
  },
  {
    "capacityProvider": "FARGATE_SPOT",
    "base": 0,
    "weight": 3
  }
]
```

This means:
- First 3 tasks always run on On-Demand (reliable baseline)
- Additional tasks split 75% Spot / 25% On-Demand
- If desired count = 11: 3 base On-Demand + 2 On-Demand + 6 Spot

For EC2 capacity providers:
- Create ASG with mixed instances policy (multiple instance types for Spot diversity)
- Enable managed scaling (target capacity = 100%)
- Enable managed termination protection (ECS protects instances with running tasks)

### Q8: Container health checks failing - Debug process

**Answer:**

1. **Check health check definition**:
   - Is the command correct? Test locally: `docker exec <container> curl -f http://localhost:8080/health`
   - Is `startPeriod` long enough? (JVM apps need 60-120s)
   - Is `interval` reasonable? (not too aggressive)

2. **Check container logs**: `aws ecs describe-tasks` → look at `stoppedReason`, then CloudWatch Logs

3. **Check application startup**:
   - Is the app listening on the correct port?
   - Are dependencies available? (DB, cache, external services)
   - Did init containers complete successfully? (check `dependsOn`)

4. **Check networking**:
   - Security group allows health check traffic
   - Health check path returns 200 (not redirect)
   - Container port matches port mapping

5. **ECS Exec** to debug interactively:
   ```bash
   aws ecs execute-command --cluster x --task y --container z --interactive --command "/bin/sh"
   # Inside: curl localhost:8080/health
   ```

6. **Common fixes**:
   - Increase `startPeriod` for slow-starting apps
   - Fix health endpoint to not depend on external services
   - Ensure health check command binary exists in container image (`curl`, `wget`)

### Q9: Migration from Docker Compose to ECS

**Answer:**

Mapping:
| Docker Compose | ECS |
|---------------|-----|
| `services:` | Task Definition (multiple containers) or separate Services |
| `image:` | `containerDefinitions[].image` |
| `ports:` | `portMappings` |
| `environment:` | `environment` or `secrets` |
| `volumes:` | EFS volumes or bind mounts |
| `depends_on:` | `dependsOn` with conditions |
| `networks:` | `awsvpc` + security groups |
| `deploy.replicas:` | Service `desiredCount` |
| `healthcheck:` | `healthCheck` |

Steps:
1. Push images to ECR
2. Create task definitions (one per logical service, or group tightly-coupled containers)
3. Create ECS cluster
4. Create services with ALB integration
5. Set up service discovery for inter-service communication
6. Configure auto scaling
7. Set up CI/CD pipeline for automated deployments

**Tool**: `ecs-cli compose` can translate docker-compose.yml directly (deprecated but functional). Prefer Copilot CLI or CDK for new projects.

### Q10: Design multi-region ECS deployment

**Answer:**

```
                    Route 53 (latency-based routing)
                    ┌──────────┬──────────┐
                    ▼          ▼          ▼
              US-EAST-1   EU-WEST-1   AP-SOUTH-1
              ┌───────┐   ┌───────┐   ┌───────┐
              │  ALB  │   │  ALB  │   │  ALB  │
              │  ECS  │   │  ECS  │   │  ECS  │
              │ Cluster│   │Cluster│   │Cluster│
              └───────┘   └───────┘   └───────┘
                    │          │          │
              DynamoDB Global Tables (or Aurora Global)
```

Implementation:
1. **ECR**: Enable cross-region replication
2. **Infrastructure as Code**: Same CDK/Terraform per region, parameterized
3. **CI/CD**: Deploy to primary first, then secondary (with approval gates)
4. **Data**: DynamoDB Global Tables or Aurora Global Database for data replication
5. **DNS**: Route 53 latency-based routing with health checks for automatic failover
6. **Secrets**: Replicate secrets to each region
7. **Monitoring**: Centralized CloudWatch dashboard with cross-region metrics

### Q11: ECS task stuck in PENDING state

**Answer:**

Common causes:
1. **No capacity**: Cluster has no instances with enough CPU/memory → check capacity provider or add instances
2. **ENI limit** (awsvpc): Subnet ran out of IPs or instance hit ENI limit → use larger subnet or enable trunk ENI
3. **Image pull failure**: ECR permission issue or image doesn't exist → check execution role, verify image URI
4. **Port conflict** (host/bridge): Host port already in use → use dynamic port mapping
5. **Placement constraints**: No instance matches constraints → relax constraints or add matching instances
6. **Resource contention**: CPU/memory reserved by other tasks → right-size or add capacity

Debug: `aws ecs describe-tasks --tasks <arn>` → check `stoppedReason` and `stopCode`

### Q12: Implement canary deployment for ECS service

**Answer:**

**Option A: CodeDeploy Blue/Green with Canary:**
- `Canary10Percent5Minutes`: Routes 10% traffic to new version for 5 min
- CloudWatch alarms monitor error rate during canary window
- Auto-rollback if alarms trigger

**Option B: Weighted Target Groups (manual):**
- Two services behind same ALB with weighted target groups
- Gradually shift weight: 5% → 25% → 50% → 100%
- Monitor metrics between shifts

**Option C: Service Connect with traffic policies:**
- Route percentage of traffic to canary service
- Progressive rollout with automated checks

### Q13: Optimize Fargate startup time

**Answer:**

Fargate cold start breakdown:
- Image pull: 10-60s (largest contributor)
- Container start: 1-5s
- Application boot: Varies

Optimizations:
1. **Smaller images**: Use alpine/distroless base images (50MB vs 500MB+)
2. **Multi-stage builds**: Only ship runtime dependencies
3. **Seekable OCI (SOCI)**: Lazy-loading image layers — container starts before full image download
4. **ECR in same region**: Avoid cross-region pulls
5. **Reduce startup dependencies**: Async initialization, don't block on DB migrations
6. **Keep minimum tasks running**: `base` in capacity provider strategy prevents all-cold-start scenarios

### Q14: ECS task needs to access on-premises resources

**Answer:**

Options:
1. **VPN/Direct Connect**: Task in private subnet, route to on-prem via VPN/DX gateway
2. **PrivateLink**: If on-prem exposes NLB, use PrivateLink
3. **Transit Gateway**: Hub-and-spoke connectivity between VPCs and on-prem

Networking setup:
- Task in private subnet with route table entry pointing to VGW/TGW
- Security group allows outbound to on-prem CIDR
- On-prem firewall allows inbound from VPC CIDR
- DNS: Route 53 Resolver for hybrid DNS resolution

### Q15: Right-sizing ECS tasks

**Answer:**

Process:
1. Deploy with generous CPU/memory allocation
2. Enable Container Insights
3. Monitor for 1-2 weeks under production load
4. Analyze P95/P99 CPU and memory utilization
5. Set memory to ~120% of observed peak (buffer for spikes)
6. Set CPU based on P99 utilization (Fargate: you pay for allocated, not used)

Tools:
- CloudWatch Container Insights dashboards
- AWS Compute Optimizer (provides right-sizing recommendations for ECS on EC2)
- Custom CloudWatch metrics for application-level measurements

Rule of thumb: If average CPU utilization < 20%, you're over-provisioned. If memory utilization is consistently > 80%, you risk OOM.
