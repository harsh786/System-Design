# Data Platform Infrastructure - Deep Dive

## Table of Contents
1. [IaC for Data Platforms](#1-iac-for-data-platforms)
2. [Terraform for AWS Data Infrastructure](#2-terraform-for-aws-data-infrastructure)
3. [GitOps for Data Platforms](#3-gitops-for-data-platforms)
4. [Kubernetes Operators for Data](#4-kubernetes-operators-for-data)
5. [Helm Charts for Data Stack](#5-helm-charts-for-data-stack)
6. [Access Control & Security](#6-access-control--security)
7. [Secrets Management](#7-secrets-management)
8. [Networking for Data Platforms](#8-networking-for-data-platforms)
9. [Platform Engineering Principles](#9-platform-engineering-principles)
10. [Production Checklist](#10-production-checklist)

---

## 1. IaC for Data Platforms

### Why IaC is Non-Negotiable

```
Without IaC:                          With IaC:
─────────────                         ─────────
• "Who created this EMR?"             • Full audit trail in git
• "What config is prod?"              • Exact reproducibility
• "Can we recreate this?"             • Disaster recovery in minutes
• "Is staging same as prod?"          • Environment parity guaranteed
• Snowflake configs (manual drift)    • Drift detection automated
• 3 weeks to provision new env        • New environment in 30 minutes
```

### Terraform vs Pulumi vs CDK

| Dimension | Terraform | Pulumi | AWS CDK |
|-----------|-----------|--------|---------|
| Language | HCL (declarative) | Python/Go/TS/C# | TypeScript/Python/Java |
| State | Remote (S3 + DynamoDB) | Pulumi Cloud / self-managed | CloudFormation |
| AWS coverage | Excellent (community + official) | Good | Native (best for AWS) |
| Multi-cloud | Yes | Yes | AWS only |
| Learning curve | Low-medium | Low (if you know the language) | Medium |
| Ecosystem | Massive (modules, providers) | Growing | Growing |
| Drift detection | `terraform plan` | `pulumi preview` | CloudFormation drift |
| Best for | Multi-cloud, platform teams | Dev teams who prefer real code | Pure AWS shops |

---

## 2. Terraform for AWS Data Infrastructure

### Module Design Pattern

```
terraform/
├── modules/                    # Reusable modules
│   ├── msk-cluster/
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   ├── outputs.tf
│   │   └── versions.tf
│   ├── glue-job/
│   ├── emr-cluster/
│   ├── kinesis-stream/
│   ├── redshift-serverless/
│   └── data-lake-bucket/
├── environments/              # Environment-specific
│   ├── dev/
│   │   ├── main.tf
│   │   ├── terraform.tfvars
│   │   └── backend.tf
│   ├── staging/
│   └── prod/
├── terragrunt.hcl            # DRY configuration
└── .github/
    └── workflows/
        └── terraform.yml      # CI/CD
```

### MSK Cluster Module

```hcl
# modules/msk-cluster/main.tf
resource "aws_msk_cluster" "this" {
  cluster_name           = var.cluster_name
  kafka_version          = var.kafka_version
  number_of_broker_nodes = var.broker_count

  broker_node_group_info {
    instance_type   = var.instance_type
    client_subnets  = var.subnet_ids
    security_groups = [aws_security_group.msk.id]

    storage_info {
      ebs_storage_info {
        volume_size = var.ebs_volume_size
        provisioned_throughput {
          enabled           = var.ebs_volume_size >= 500
          volume_throughput = var.ebs_throughput
        }
      }
    }

    connectivity_info {
      public_access {
        type = "DISABLED"
      }
    }
  }

  encryption_info {
    encryption_in_transit {
      client_broker = "TLS"
      in_cluster    = true
    }
    encryption_at_rest_kms_key_arn = var.kms_key_arn
  }

  configuration_info {
    arn      = aws_msk_configuration.this.arn
    revision = aws_msk_configuration.this.latest_revision
  }

  open_monitoring {
    prometheus {
      jmx_exporter {
        enabled_in_broker = true
      }
      node_exporter {
        enabled_in_broker = true
      }
    }
  }

  logging_info {
    broker_logs {
      cloudwatch_logs {
        enabled   = true
        log_group = aws_cloudwatch_log_group.msk.name
      }
      s3 {
        enabled = true
        bucket  = var.logs_bucket
        prefix  = "msk/${var.cluster_name}"
      }
    }
  }

  tags = var.tags
}

resource "aws_msk_configuration" "this" {
  kafka_versions = [var.kafka_version]
  name           = "${var.cluster_name}-config"

  server_properties = <<PROPERTIES
auto.create.topics.enable=false
default.replication.factor=3
min.insync.replicas=2
num.partitions=6
log.retention.hours=${var.retention_hours}
log.retention.bytes=${var.retention_bytes}
unclean.leader.election.enable=false
message.max.bytes=10485760
replica.fetch.max.bytes=10485760
log.segment.bytes=1073741824
log.cleanup.policy=delete
compression.type=producer
PROPERTIES
}

# MSK Serverless (alternative)
resource "aws_msk_serverless_cluster" "serverless" {
  count        = var.serverless ? 1 : 0
  cluster_name = "${var.cluster_name}-serverless"

  vpc_config {
    subnet_ids         = var.subnet_ids
    security_group_ids = [aws_security_group.msk.id]
  }

  client_authentication {
    sasl {
      iam {
        enabled = true
      }
    }
  }
}

# Security Group
resource "aws_security_group" "msk" {
  name_prefix = "${var.cluster_name}-msk-"
  vpc_id      = var.vpc_id

  ingress {
    from_port       = 9092
    to_port         = 9098
    protocol        = "tcp"
    security_groups = var.client_security_group_ids
    description     = "Kafka broker ports"
  }

  ingress {
    from_port       = 2181
    to_port         = 2181
    protocol        = "tcp"
    security_groups = var.client_security_group_ids
    description     = "ZooKeeper (if applicable)"
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = var.tags
}
```

### Glue Job Module

```hcl
# modules/glue-job/main.tf
resource "aws_glue_job" "this" {
  name              = var.job_name
  role_arn          = aws_iam_role.glue.arn
  glue_version      = "4.0"
  worker_type       = var.worker_type  # G.1X, G.2X, G.4X, G.8X, Z.2X
  number_of_workers = var.num_workers
  timeout           = var.timeout_minutes
  max_retries       = var.max_retries

  command {
    script_location = "s3://${var.scripts_bucket}/glue-jobs/${var.job_name}/${var.script_name}"
    python_version  = "3"
  }

  default_arguments = merge({
    "--job-language"                     = "python"
    "--job-bookmark-option"             = var.enable_bookmarks ? "job-bookmark-enable" : "job-bookmark-disable"
    "--enable-metrics"                  = "true"
    "--enable-continuous-cloudwatch-log" = "true"
    "--enable-spark-ui"                 = "true"
    "--spark-event-logs-path"           = "s3://${var.logs_bucket}/spark-ui/${var.job_name}/"
    "--enable-auto-scaling"             = var.enable_auto_scaling ? "true" : "false"
    "--TempDir"                         = "s3://${var.scripts_bucket}/glue-temp/${var.job_name}/"
    "--extra-py-files"                  = join(",", var.extra_py_files)
    "--additional-python-modules"       = join(",", var.additional_python_modules)
    "--datalake-formats"                = "iceberg"
    "--conf"                            = "spark.sql.extensions=org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions"
  }, var.custom_arguments)

  execution_property {
    max_concurrent_runs = var.max_concurrent_runs
  }

  dynamic "notification_property" {
    for_each = var.notify_delay_after_minutes != null ? [1] : []
    content {
      notify_delay_after = var.notify_delay_after_minutes
    }
  }

  tags = var.tags
}

# Glue Trigger (scheduled)
resource "aws_glue_trigger" "schedule" {
  count    = var.schedule_expression != null ? 1 : 0
  name     = "${var.job_name}-schedule"
  type     = "SCHEDULED"
  schedule = var.schedule_expression  # "cron(0 8 * * ? *)"

  actions {
    job_name = aws_glue_job.this.name
    arguments = var.trigger_arguments
  }

  tags = var.tags
}

# IAM Role
resource "aws_iam_role" "glue" {
  name = "${var.job_name}-glue-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = { Service = "glue.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "glue_service" {
  role       = aws_iam_role.glue.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSGlueServiceRole"
}

resource "aws_iam_role_policy" "s3_access" {
  name = "${var.job_name}-s3-access"
  role = aws_iam_role.glue.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject", "s3:ListBucket"]
        Resource = concat(
          [for bucket in var.s3_buckets : "arn:aws:s3:::${bucket}"],
          [for bucket in var.s3_buckets : "arn:aws:s3:::${bucket}/*"]
        )
      }
    ]
  })
}
```

### Terragrunt for Multi-Environment

```hcl
# terragrunt.hcl (root)
remote_state {
  backend = "s3"
  generate = {
    path      = "backend.tf"
    if_exists = "overwrite_terragrunt"
  }
  config = {
    bucket         = "mycompany-terraform-state"
    key            = "${path_relative_to_include()}/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "terraform-locks"
  }
}

generate "provider" {
  path      = "provider.tf"
  if_exists = "overwrite_terragrunt"
  contents  = <<EOF
provider "aws" {
  region = "${local.aws_region}"
  default_tags {
    tags = {
      Environment = "${local.environment}"
      ManagedBy   = "terraform"
      Team        = "data-platform"
    }
  }
}
EOF
}

# environments/prod/msk/terragrunt.hcl
terraform {
  source = "../../../modules/msk-cluster"
}

include "root" {
  path = find_in_parent_folders()
}

inputs = {
  cluster_name     = "prod-data-platform"
  kafka_version    = "3.5.1"
  broker_count     = 6
  instance_type    = "kafka.m5.2xlarge"
  ebs_volume_size  = 1000
  retention_hours  = 168
  subnet_ids       = dependency.vpc.outputs.private_subnet_ids
}

dependency "vpc" {
  config_path = "../vpc"
}
```

### CI/CD for Terraform

```yaml
# .github/workflows/terraform.yml
name: Terraform Data Platform
on:
  pull_request:
    paths: ['terraform/**']
  push:
    branches: [main]
    paths: ['terraform/**']

jobs:
  plan:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        environment: [dev, staging, prod]
    steps:
      - uses: actions/checkout@v4
      - uses: hashicorp/setup-terraform@v3
      
      - name: Terraform Init
        run: terraform init
        working-directory: terraform/environments/${{ matrix.environment }}
      
      - name: Terraform Plan
        run: terraform plan -out=tfplan -no-color
        working-directory: terraform/environments/${{ matrix.environment }}
      
      - name: Infracost
        uses: infracost/actions/setup@v2
      - run: infracost breakdown --path terraform/environments/${{ matrix.environment }}

  apply:
    if: github.ref == 'refs/heads/main' && github.event_name == 'push'
    needs: plan
    environment: ${{ matrix.environment }}  # Requires approval for prod
    runs-on: ubuntu-latest
    strategy:
      max-parallel: 1
      matrix:
        environment: [dev, staging, prod]
    steps:
      - uses: actions/checkout@v4
      - uses: hashicorp/setup-terraform@v3
      - run: terraform init && terraform apply -auto-approve
        working-directory: terraform/environments/${{ matrix.environment }}
```

---

## 3. GitOps for Data Platforms

### ArgoCD Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                      ArgoCD Server                                 │
│                                                                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐   │
│  │  API Server  │  │  Repo Server │  │  Application          │   │
│  │  (UI + CLI)  │  │  (Git clone) │  │  Controller           │   │
│  │              │  │              │  │  (reconciliation loop)│   │
│  └──────────────┘  └──────────────┘  └──────────────────────┘   │
└──────────────────────────────────────────────────────────────────┘
         │                                        │
         │                                        │ Compare desired
         │                                        │ vs actual state
         ▼                                        ▼
┌──────────────┐                        ┌──────────────────────┐
│   Git Repo    │                        │   Kubernetes Cluster  │
│  (desired     │                        │   (actual state)      │
│   state)      │                        │                        │
└──────────────┘                        └──────────────────────┘
```

### App-of-Apps Pattern for Data Platform

```yaml
# argocd/apps/data-platform.yaml (parent app)
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: data-platform
  namespace: argocd
spec:
  project: data-platform
  source:
    repoURL: https://github.com/company/data-platform-gitops
    targetRevision: main
    path: argocd/apps
  destination:
    server: https://kubernetes.default.svc
    namespace: argocd
  syncPolicy:
    automated:
      prune: true
      selfHeal: true

---
# argocd/apps/kafka.yaml (child app)
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: kafka-cluster
  namespace: argocd
spec:
  project: data-platform
  source:
    repoURL: https://github.com/company/data-platform-gitops
    targetRevision: main
    path: kubernetes/kafka
    helm:
      valueFiles:
        - values-prod.yaml
  destination:
    server: https://kubernetes.default.svc
    namespace: kafka
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - CreateNamespace=true

---
# argocd/apps/flink-jobs.yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: flink-jobs
  namespace: argocd
spec:
  project: data-platform
  source:
    repoURL: https://github.com/company/data-platform-gitops
    path: kubernetes/flink-jobs
  destination:
    server: https://kubernetes.default.svc
    namespace: flink
  syncPolicy:
    automated:
      selfHeal: true
    syncOptions:
      - RespectIgnoreDifferences=true
```

---

## 4. Kubernetes Operators for Data

### Strimzi (Kafka on K8s)

```yaml
# Kafka cluster with Strimzi
apiVersion: kafka.strimzi.io/v1beta2
kind: Kafka
metadata:
  name: production-cluster
  namespace: kafka
spec:
  kafka:
    version: 3.6.0
    replicas: 6
    
    listeners:
      - name: internal
        port: 9092
        type: internal
        tls: true
        authentication:
          type: scram-sha-512
      - name: external
        port: 9094
        type: loadbalancer
        tls: true
        authentication:
          type: scram-sha-512
    
    config:
      offsets.topic.replication.factor: 3
      transaction.state.log.replication.factor: 3
      transaction.state.log.min.isr: 2
      default.replication.factor: 3
      min.insync.replicas: 2
      num.partitions: 12
      log.retention.hours: 168
      log.segment.bytes: 1073741824
      auto.create.topics.enable: false
      
    storage:
      type: jbod
      volumes:
        - id: 0
          type: persistent-claim
          size: 1Ti
          class: gp3
          deleteClaim: false
        - id: 1
          type: persistent-claim
          size: 1Ti
          class: gp3
          deleteClaim: false
    
    rack:
      topologyKey: topology.kubernetes.io/zone
    
    resources:
      requests:
        memory: 8Gi
        cpu: "4"
      limits:
        memory: 12Gi
        cpu: "6"
    
    jvmOptions:
      -Xms: 4096m
      -Xmx: 4096m
    
    metricsConfig:
      type: jmxPrometheusExporter
      valueFrom:
        configMapKeyRef:
          name: kafka-metrics-config
          key: kafka-metrics-config.yml
    
    template:
      pod:
        affinity:
          podAntiAffinity:
            requiredDuringSchedulingIgnoredDuringExecution:
              - labelSelector:
                  matchExpressions:
                    - key: strimzi.io/name
                      operator: In
                      values: [production-cluster-kafka]
                topologyKey: kubernetes.io/hostname

  # Cruise Control for auto-rebalancing
  cruiseControl:
    config:
      goals: >
        com.linkedin.kafka.cruisecontrol.analyzer.goals.RackAwareGoal,
        com.linkedin.kafka.cruisecontrol.analyzer.goals.ReplicaCapacityGoal,
        com.linkedin.kafka.cruisecontrol.analyzer.goals.DiskCapacityGoal,
        com.linkedin.kafka.cruisecontrol.analyzer.goals.NetworkInboundCapacityGoal,
        com.linkedin.kafka.cruisecontrol.analyzer.goals.NetworkOutboundCapacityGoal,
        com.linkedin.kafka.cruisecontrol.analyzer.goals.CpuCapacityGoal
    resources:
      requests:
        memory: 2Gi
        cpu: "1"
    metricsConfig:
      type: jmxPrometheusExporter

  zookeeper:
    replicas: 3
    storage:
      type: persistent-claim
      size: 100Gi
      class: gp3
    resources:
      requests:
        memory: 2Gi
        cpu: "1"

  entityOperator:
    topicOperator:
      resources:
        requests:
          memory: 512Mi
    userOperator:
      resources:
        requests:
          memory: 512Mi

---
# KafkaTopic CRD
apiVersion: kafka.strimzi.io/v1beta2
kind: KafkaTopic
metadata:
  name: orders-cdc
  labels:
    strimzi.io/cluster: production-cluster
spec:
  partitions: 24
  replicas: 3
  config:
    retention.ms: "604800000"    # 7 days
    cleanup.policy: "compact,delete"
    min.insync.replicas: "2"
    compression.type: "zstd"
    segment.bytes: "1073741824"

---
# KafkaUser with ACLs
apiVersion: kafka.strimzi.io/v1beta2
kind: KafkaUser
metadata:
  name: orders-service
  labels:
    strimzi.io/cluster: production-cluster
spec:
  authentication:
    type: scram-sha-512
  authorization:
    type: simple
    acls:
      - resource:
          type: topic
          name: orders-
          patternType: prefix
        operations: [Read, Write, Describe]
      - resource:
          type: group
          name: orders-consumer-
          patternType: prefix
        operations: [Read]
```

### Flink Kubernetes Operator

```yaml
# FlinkDeployment - Application mode
apiVersion: flink.apache.org/v1beta1
kind: FlinkDeployment
metadata:
  name: cdc-pipeline
  namespace: flink
spec:
  image: company/flink-cdc:1.18-latest
  flinkVersion: v1_18
  flinkConfiguration:
    taskmanager.numberOfTaskSlots: "4"
    state.backend: rocksdb
    state.checkpoints.dir: s3://flink-checkpoints/cdc-pipeline/
    state.savepoints.dir: s3://flink-savepoints/cdc-pipeline/
    execution.checkpointing.interval: "60000"
    execution.checkpointing.min-pause: "30000"
    execution.checkpointing.mode: EXACTLY_ONCE
    state.backend.rocksdb.memory.managed: "true"
    state.backend.rocksdb.memory.fixed-per-slot: "256mb"
    restart-strategy: fixed-delay
    restart-strategy.fixed-delay.attempts: "10"
    restart-strategy.fixed-delay.delay: "30s"
    kubernetes.operator.savepoint.trigger.grace-period: "60s"
    
  serviceAccount: flink-sa
  
  jobManager:
    resource:
      memory: "2048m"
      cpu: 1
    replicas: 1
  
  taskManager:
    resource:
      memory: "4096m"
      cpu: 2
    replicas: 4
  
  job:
    jarURI: local:///opt/flink/usrlib/cdc-pipeline.jar
    entryClass: com.company.CDCPipeline
    parallelism: 8
    upgradeMode: savepoint    # savepoint on upgrade (vs stateless, last-state)
    state: running
    savepointTriggerNonce: 0  # Increment to trigger manual savepoint
    
  podTemplate:
    spec:
      containers:
        - name: flink-main-container
          env:
            - name: AWS_REGION
              value: us-east-1
          volumeMounts:
            - name: flink-config
              mountPath: /opt/flink/conf
      serviceAccountName: flink-sa
      nodeSelector:
        node-type: compute-optimized

---
# Flink autoscaler config
apiVersion: flink.apache.org/v1beta1
kind: FlinkDeployment
metadata:
  name: autoscaled-job
spec:
  flinkConfiguration:
    kubernetes.operator.job.autoscaler.enabled: "true"
    kubernetes.operator.job.autoscaler.stabilization.interval: "5m"
    kubernetes.operator.job.autoscaler.metrics.window: "10m"
    kubernetes.operator.job.autoscaler.target.utilization: "0.7"
    kubernetes.operator.job.autoscaler.scale-down.max-factor: "0.5"
    kubernetes.operator.job.autoscaler.scale-up.max-factor: "2.0"
```

### Spark on K8s Operator

```yaml
apiVersion: sparkoperator.k8s.io/v1beta2
kind: SparkApplication
metadata:
  name: daily-etl
  namespace: spark
spec:
  type: Python
  pythonVersion: "3"
  mode: cluster
  image: company/spark:3.5-latest
  imagePullPolicy: Always
  mainApplicationFile: s3://spark-jobs/daily-etl/main.py
  arguments:
    - "--date=2024-01-15"
    - "--env=production"
  
  sparkVersion: "3.5.0"
  restartPolicy:
    type: OnFailure
    onFailureRetries: 3
    onFailureRetryInterval: 60
  
  sparkConf:
    spark.sql.extensions: "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions"
    spark.sql.catalog.iceberg: "org.apache.iceberg.spark.SparkCatalog"
    spark.sql.catalog.iceberg.warehouse: "s3://data-lake/iceberg/"
    spark.sql.adaptive.enabled: "true"
    spark.sql.adaptive.coalescePartitions.enabled: "true"
    spark.serializer: "org.apache.spark.serializer.KryoSerializer"
    spark.hadoop.fs.s3a.aws.credentials.provider: "com.amazonaws.auth.WebIdentityTokenCredentialsProvider"
  
  driver:
    cores: 2
    memory: "4g"
    serviceAccount: spark-sa
    labels:
      app: daily-etl
      role: driver
  
  executor:
    cores: 4
    instances: 10
    memory: "8g"
    labels:
      app: daily-etl
      role: executor
  
  dynamicAllocation:
    enabled: true
    initialExecutors: 5
    minExecutors: 2
    maxExecutors: 20
  
  # Volcano scheduler for fair scheduling
  batchScheduler: volcano
  batchSchedulerOptions:
    queue: data-platform
    priorityClassName: high-priority
```

---

## 5. Helm Charts for Data Stack

### Helmfile for Managing Multiple Releases

```yaml
# helmfile.yaml
repositories:
  - name: strimzi
    url: https://strimzi.io/charts/
  - name: flink-operator
    url: https://downloads.apache.org/flink/flink-kubernetes-operator-1.7.0/
  - name: apache-airflow
    url: https://airflow.apache.org
  - name: prometheus-community
    url: https://prometheus-community.github.io/helm-charts
  - name: grafana
    url: https://grafana.github.io/helm-charts

environments:
  dev:
    values:
      - environments/dev/values.yaml
  staging:
    values:
      - environments/staging/values.yaml
  production:
    values:
      - environments/production/values.yaml

releases:
  - name: strimzi-operator
    namespace: kafka
    chart: strimzi/strimzi-kafka-operator
    version: 0.38.0
    values:
      - charts/strimzi/values.yaml
      - charts/strimzi/values-{{ .Environment.Name }}.yaml

  - name: flink-operator
    namespace: flink
    chart: flink-operator/flink-kubernetes-operator
    version: 1.7.0
    values:
      - charts/flink-operator/values.yaml

  - name: airflow
    namespace: airflow
    chart: apache-airflow/airflow
    version: 1.11.0
    values:
      - charts/airflow/values.yaml
      - charts/airflow/values-{{ .Environment.Name }}.yaml

  - name: monitoring
    namespace: monitoring
    chart: prometheus-community/kube-prometheus-stack
    version: 55.0.0
    values:
      - charts/monitoring/values.yaml
```

---

## 6. Access Control & Security

### Apache Ranger

```
┌──────────────────────────────────────────────────────────────┐
│                    Apache Ranger Architecture                   │
│                                                                │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐   │
│  │ Ranger Admin │    │  UserSync    │    │   TagSync    │   │
│  │  (Policy DB) │    │ (LDAP/AD →   │    │ (Atlas tags →│   │
│  │              │    │  Ranger)     │    │  policies)   │   │
│  └──────┬───────┘    └──────────────┘    └──────────────┘   │
│         │                                                      │
│         │ Policy download (periodic pull)                     │
│         ▼                                                      │
│  ┌────────────────────────────────────────────────────────┐  │
│  │              Ranger Plugins (embedded in services)       │  │
│  │                                                          │  │
│  │  ┌─────┐  ┌──────┐  ┌─────┐  ┌──────┐  ┌──────────┐ │  │
│  │  │Hive │  │Spark │  │Kafka│  │HBase │  │  HDFS/S3 │ │  │
│  │  └─────┘  └──────┘  └─────┘  └──────┘  └──────────┘ │  │
│  └────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

### AWS Lake Formation

```hcl
# Terraform: Lake Formation permissions
resource "aws_lakeformation_permissions" "analyst_access" {
  principal   = "arn:aws:iam::123456789:role/data-analyst"

  permissions = ["SELECT"]

  table_with_columns {
    database_name = "silver"
    name          = "orders"
    column_names  = ["order_id", "amount", "status", "order_date"]
    # Excluded: customer_pii, email, phone (PII columns)
  }
}

# LF-Tags for attribute-based access control
resource "aws_lakeformation_lf_tag" "data_classification" {
  key    = "classification"
  values = ["public", "internal", "confidential", "restricted"]
}

resource "aws_lakeformation_lf_tag" "domain" {
  key    = "domain"
  values = ["orders", "payments", "customers", "analytics"]
}

# Tag-based grant (all tables tagged "public" accessible to analysts)
resource "aws_lakeformation_permissions" "tag_based_access" {
  principal   = "arn:aws:iam::123456789:role/data-analyst"
  permissions = ["SELECT", "DESCRIBE"]

  lf_tag_policy {
    resource_type = "TABLE"
    expression {
      key    = "classification"
      values = ["public", "internal"]
    }
  }
}

# Row-level security via data filters
resource "aws_lakeformation_data_cells_filter" "region_filter" {
  table_data {
    database_name = "silver"
    table_name    = "orders"
    name          = "us-only-filter"
    
    column_names = ["order_id", "amount", "status", "region"]
    
    row_filter {
      filter_expression = "region = 'US'"
    }
  }
}
```

### OPA (Open Policy Agent)

```rego
# policy/data_access.rego
package data.access

# Default deny
default allow = false

# Allow if user has appropriate role for the classification
allow {
    input.action == "SELECT"
    role := user_roles[input.user]
    permitted_classifications[role][_] == input.resource.classification
}

# Role definitions
user_roles := {
    "analyst@company.com": "analyst",
    "engineer@company.com": "engineer",
    "admin@company.com": "admin"
}

# Classification access by role
permitted_classifications := {
    "analyst": ["public", "internal"],
    "engineer": ["public", "internal", "confidential"],
    "admin": ["public", "internal", "confidential", "restricted"]
}

# Column-level PII masking
mask_columns[col] {
    input.resource.columns[_] == col
    pii_columns[_] == col
    not input.user_has_pii_access
}

pii_columns := ["email", "phone", "ssn", "credit_card"]

# Time-based access (business hours only for some data)
allow {
    input.resource.classification == "restricted"
    is_business_hours
}

is_business_hours {
    now := time.now_ns()
    hour := time.clock(now)[0]
    hour >= 9
    hour < 18
}
```

---

## 7. Secrets Management

```hcl
# Terraform: AWS Secrets Manager for pipeline credentials
resource "aws_secretsmanager_secret" "db_credentials" {
  name = "data-platform/prod/mysql-source"
  
  tags = {
    Environment = "production"
    Service     = "data-pipeline"
  }
}

resource "aws_secretsmanager_secret_version" "db_credentials" {
  secret_id = aws_secretsmanager_secret.db_credentials.id
  secret_string = jsonencode({
    username = "pipeline_user"
    password = var.mysql_password  # From CI/CD secret
    host     = "mysql-primary.prod.internal"
    port     = 3306
    database = "orders"
  })
}

# Automatic rotation (every 30 days)
resource "aws_secretsmanager_secret_rotation" "db_credentials" {
  secret_id           = aws_secretsmanager_secret.db_credentials.id
  rotation_lambda_arn = aws_lambda_function.rotate_secret.arn
  
  rotation_rules {
    automatically_after_days = 30
  }
}
```

```python
# Airflow: Reading secrets from AWS Secrets Manager
# In airflow.cfg or env var:
# AIRFLOW__SECRETS__BACKEND=airflow.providers.amazon.aws.secrets.secrets_manager.SecretsManagerBackend
# AIRFLOW__SECRETS__BACKEND_KWARGS={"connections_prefix": "airflow/connections", "variables_prefix": "airflow/variables"}

# Flink: Reading secrets via K8s secrets mounted as env vars
# In FlinkDeployment spec:
#   env:
#     - name: DB_PASSWORD
#       valueFrom:
#         secretKeyRef:
#           name: mysql-credentials
#           key: password
```

---

## 8. Networking for Data Platforms

### VPC Design

```
┌────────────────────────────────────────────────────────────────────┐
│                    Data Platform VPC (10.0.0.0/16)                   │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ Public Subnets (10.0.0.0/20, 10.0.16.0/20, 10.0.32.0/20) │   │
│  │   • NAT Gateways (one per AZ)                               │   │
│  │   • ALB for Airflow/Grafana UI                              │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ Private Subnets (10.0.48.0/20, 10.0.64.0/20, 10.0.80.0/20)│   │
│  │   • MSK brokers                                              │   │
│  │   • EMR clusters                                             │   │
│  │   • Flink TaskManagers                                       │   │
│  │   • EKS worker nodes                                        │   │
│  │   • RDS/Aurora                                               │   │
│  │   • Redshift                                                 │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ VPC Endpoints (no internet for AWS service access)           │   │
│  │   • S3 (Gateway)                                             │   │
│  │   • Glue, KMS, STS, CloudWatch, Kinesis (Interface)         │   │
│  │   • Secrets Manager, DynamoDB (Interface)                    │   │
│  └─────────────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────────────┘
```

---

## 9. Platform Engineering Principles

### Internal Developer Platform for Data

```
┌────────────────────────────────────────────────────────────────┐
│                Self-Serve Data Platform                          │
│                                                                  │
│  Developer Interface:                                           │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  • CLI: `dctl create pipeline --type=cdc --source=mysql`  │  │
│  │  • Portal: Web UI for pipeline creation                   │  │
│  │  • Templates: Golden paths for common patterns            │  │
│  │  • Catalog: Discover available datasets                   │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
│  Platform Capabilities:                                         │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  • Provisioning: Terraform modules (pre-approved)         │  │
│  │  • Deployment: ArgoCD (GitOps)                            │  │
│  │  • Observability: Pre-configured dashboards               │  │
│  │  • Security: Lake Formation + Ranger (policy-as-code)     │  │
│  │  • Quality: Soda/GE pre-integrated                        │  │
│  │  • Cost: Per-team budgets and alerts                      │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
│  Team Topology:                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐    │
│  │ Platform Team│  │ Enabling Team│  │ Stream-Aligned    │    │
│  │ (infra,      │  │ (best        │  │ Teams (domain     │    │
│  │  tooling,    │  │  practices,  │  │  pipelines, data  │    │
│  │  standards)  │  │  training)   │  │  products)        │    │
│  └──────────────┘  └──────────────┘  └──────────────────┘    │
└────────────────────────────────────────────────────────────────┘
```

---

## 10. Production Checklist

### Infrastructure
- [ ] All resources defined in Terraform (no manual resources)
- [ ] Remote state with locking (S3 + DynamoDB)
- [ ] CI/CD pipeline with plan → review → apply
- [ ] Drift detection scheduled (weekly `terraform plan`)
- [ ] Resource tagging strategy enforced (cost allocation, ownership)
- [ ] Infracost integrated for cost visibility

### GitOps
- [ ] ArgoCD deployed with HA (3+ replicas)
- [ ] App-of-apps pattern for platform components
- [ ] Sync policies configured (auto-sync for non-prod, manual for prod)
- [ ] RBAC configured (team-scoped access)
- [ ] Notifications (Slack/Teams on sync failures)

### Kubernetes
- [ ] Operators installed and versioned (Strimzi, Flink, Spark)
- [ ] Resource quotas per namespace
- [ ] Pod disruption budgets for stateful services
- [ ] Node affinity/anti-affinity for HA
- [ ] Persistent volume backup strategy
- [ ] Monitoring: operator metrics exposed to Prometheus

### Security
- [ ] Lake Formation or Ranger configured
- [ ] Column-level access for PII
- [ ] Secrets in AWS Secrets Manager (not in code/config)
- [ ] Secret rotation automated
- [ ] IAM roles follow least privilege
- [ ] VPC endpoints for all AWS services (no internet path)
- [ ] Security groups minimal (port + source-specific)
- [ ] Encryption at-rest and in-transit everywhere

### Networking
- [ ] VPC with multi-AZ subnets
- [ ] NAT Gateway per AZ (HA)
- [ ] VPC endpoints for S3, Glue, KMS, STS, CloudWatch
- [ ] Security groups audited quarterly
- [ ] Cross-account access via PrivateLink (not VPC peering for large scale)
