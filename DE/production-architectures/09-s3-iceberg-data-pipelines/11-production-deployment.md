# Production Deployment: S3 + Iceberg Data Pipelines

## Table of Contents

1. [Infrastructure as Code (Terraform)](#infrastructure-as-code)
2. [Kubernetes Deployments](#kubernetes-deployments)
3. [CI/CD Pipeline](#cicd-pipeline)
4. [Catalog Setup](#catalog-setup)
5. [IAM & Security Model](#iam--security-model)
6. [Environment Management](#environment-management)
7. [Blue-Green Deployment](#blue-green-deployment)
8. [GitOps with ArgoCD](#gitops-with-argocd)
9. [Secrets Management](#secrets-management)
10. [Cost Optimization](#cost-optimization)
11. [Helm Charts](#helm-charts)

---

## Infrastructure as Code

### Project Structure

```
terraform/
├── modules/
│   ├── s3-lakehouse/
│   ├── glue-catalog/
│   ├── iam-roles/
│   ├── emr-cluster/
│   ├── eks-platform/
│   └── networking/
├── environments/
│   ├── dev/
│   ├── staging/
│   └── prod/
├── main.tf
├── variables.tf
└── backend.tf
```

### S3 Buckets Module

```hcl
# modules/s3-lakehouse/main.tf

variable "environment" {
  type = string
}

variable "project_name" {
  type    = string
  default = "iceberg-lakehouse"
}

variable "enable_versioning" {
  type    = bool
  default = true
}

variable "noncurrent_expiration_days" {
  type    = number
  default = 30
}

locals {
  bucket_prefix = "${var.project_name}-${var.environment}"
}

# Raw data landing zone
resource "aws_s3_bucket" "raw" {
  bucket = "${local.bucket_prefix}-raw"

  tags = {
    Environment = var.environment
    Layer       = "raw"
    ManagedBy   = "terraform"
  }
}

resource "aws_s3_bucket_versioning" "raw" {
  bucket = aws_s3_bucket.raw.id
  versioning_configuration {
    status = var.enable_versioning ? "Enabled" : "Disabled"
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "raw" {
  bucket = aws_s3_bucket.raw.id

  rule {
    id     = "transition-to-ia"
    status = "Enabled"

    transition {
      days          = 30
      storage_class = "STANDARD_IA"
    }

    transition {
      days          = 90
      storage_class = "GLACIER"
    }

    expiration {
      days = 365
    }

    noncurrent_version_expiration {
      noncurrent_days = var.noncurrent_expiration_days
    }
  }

  rule {
    id     = "abort-incomplete-multipart"
    status = "Enabled"

    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }
}

# Curated Iceberg tables layer
resource "aws_s3_bucket" "curated" {
  bucket = "${local.bucket_prefix}-curated"

  tags = {
    Environment = var.environment
    Layer       = "curated"
    ManagedBy   = "terraform"
  }
}

resource "aws_s3_bucket_versioning" "curated" {
  bucket = aws_s3_bucket.curated.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "curated" {
  bucket = aws_s3_bucket.curated.id

  rule {
    id     = "iceberg-metadata-management"
    status = "Enabled"

    filter {
      prefix = "metadata/"
    }

    noncurrent_version_expiration {
      noncurrent_days = 7
    }
  }

  rule {
    id     = "transition-old-data-files"
    status = "Enabled"

    filter {
      prefix = "data/"
    }

    transition {
      days          = 90
      storage_class = "STANDARD_IA"
    }

    transition {
      days          = 180
      storage_class = "GLACIER_IR"
    }
  }

  rule {
    id     = "cleanup-orphan-files"
    status = "Enabled"

    filter {
      prefix = "data/"
    }

    expiration {
      expired_object_delete_marker = true
    }

    noncurrent_version_expiration {
      noncurrent_days = 3
    }
  }
}

resource "aws_s3_bucket_intelligent_tiering_configuration" "curated" {
  bucket = aws_s3_bucket.curated.id
  name   = "iceberg-tiering"

  tiering {
    access_tier = "ARCHIVE_ACCESS"
    days        = 180
  }

  tiering {
    access_tier = "DEEP_ARCHIVE_ACCESS"
    days        = 365
  }
}

# Server-side encryption
resource "aws_s3_bucket_server_side_encryption_configuration" "curated" {
  bucket = aws_s3_bucket.curated.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.lakehouse.arn
    }
    bucket_key_enabled = true
  }
}

resource "aws_kms_key" "lakehouse" {
  description             = "KMS key for ${local.bucket_prefix} lakehouse encryption"
  deletion_window_in_days = 30
  enable_key_rotation     = true

  policy = data.aws_iam_policy_document.kms_policy.json
}

data "aws_iam_policy_document" "kms_policy" {
  statement {
    sid    = "EnableRootAccountAccess"
    effect = "Allow"
    principals {
      type        = "AWS"
      identifiers = ["arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"]
    }
    actions   = ["kms:*"]
    resources = ["*"]
  }
}

data "aws_caller_identity" "current" {}

# Bucket policy enforcing TLS
resource "aws_s3_bucket_policy" "curated" {
  bucket = aws_s3_bucket.curated.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "EnforceTLS"
        Effect    = "Deny"
        Principal = "*"
        Action    = "s3:*"
        Resource = [
          aws_s3_bucket.curated.arn,
          "${aws_s3_bucket.curated.arn}/*"
        ]
        Condition = {
          Bool = { "aws:SecureTransport" = "false" }
        }
      }
    ]
  })
}

output "raw_bucket_arn" {
  value = aws_s3_bucket.raw.arn
}

output "curated_bucket_arn" {
  value = aws_s3_bucket.curated.arn
}

output "curated_bucket_name" {
  value = aws_s3_bucket.curated.id
}

output "kms_key_arn" {
  value = aws_kms_key.lakehouse.arn
}
```

### AWS Glue Catalog Module

```hcl
# modules/glue-catalog/main.tf

variable "environment" {
  type = string
}

variable "curated_bucket_name" {
  type = string
}

variable "databases" {
  type = map(object({
    description = string
    tables      = list(string)
  }))
  default = {
    bronze = {
      description = "Raw ingested data in Iceberg format"
      tables      = []
    }
    silver = {
      description = "Cleaned and validated data"
      tables      = []
    }
    gold = {
      description = "Business-level aggregations"
      tables      = []
    }
  }
}

resource "aws_glue_catalog_database" "databases" {
  for_each = var.databases

  name        = "${var.environment}_${each.key}"
  description = each.value.description

  location_uri = "s3://${var.curated_bucket_name}/${each.key}/"

  create_table_default_permission {
    permissions = ["ALL"]
    principal {
      data_lake_principal_identifier = "IAM_ALLOWED_PRINCIPALS"
    }
  }
}

# Glue Catalog settings for Iceberg
resource "aws_glue_catalog_table" "iceberg_example" {
  database_name = aws_glue_catalog_database.databases["silver"].name
  name          = "events"

  table_type = "EXTERNAL_TABLE"

  parameters = {
    "table_type"                        = "ICEBERG"
    "metadata_location"                 = "s3://${var.curated_bucket_name}/silver/events/metadata/00000-metadata.json"
    "format-version"                    = "2"
    "write.parquet.compression-codec"   = "zstd"
    "write.metadata.delete-after-commit.enabled" = "true"
    "write.metadata.previous-versions-max"       = "10"
  }

  open_table_format_input {
    iceberg_input {
      metadata_operation = "CREATE"
      version            = "2"
    }
  }
}

# Lake Formation registration
resource "aws_lakeformation_resource" "curated" {
  arn      = "arn:aws:s3:::${var.curated_bucket_name}"
  role_arn = var.lakeformation_role_arn
}

variable "lakeformation_role_arn" {
  type = string
}

output "database_names" {
  value = { for k, v in aws_glue_catalog_database.databases : k => v.name }
}
```

### IAM Roles Module

```hcl
# modules/iam-roles/main.tf

variable "environment" {
  type = string
}

variable "curated_bucket_arn" {
  type = string
}

variable "raw_bucket_arn" {
  type = string
}

variable "kms_key_arn" {
  type = string
}

variable "eks_oidc_provider_arn" {
  type = string
}

variable "eks_oidc_provider_url" {
  type = string
}

# Spark job execution role
resource "aws_iam_role" "spark_executor" {
  name = "iceberg-spark-executor-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Federated = var.eks_oidc_provider_arn
        }
        Action = "sts:AssumeRoleWithWebIdentity"
        Condition = {
          StringEquals = {
            "${var.eks_oidc_provider_url}:sub" = "system:serviceaccount:spark:spark-executor"
          }
        }
      }
    ]
  })
}

resource "aws_iam_role_policy" "spark_s3_access" {
  name = "spark-s3-access"
  role = aws_iam_role.spark_executor.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "ReadRawBucket"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:ListBucket",
          "s3:GetBucketLocation"
        ]
        Resource = [
          var.raw_bucket_arn,
          "${var.raw_bucket_arn}/*"
        ]
      },
      {
        Sid    = "ReadWriteCuratedBucket"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket",
          "s3:GetBucketLocation",
          "s3:AbortMultipartUpload",
          "s3:ListMultipartUploadParts"
        ]
        Resource = [
          var.curated_bucket_arn,
          "${var.curated_bucket_arn}/*"
        ]
      },
      {
        Sid    = "GlueCatalogAccess"
        Effect = "Allow"
        Action = [
          "glue:GetDatabase",
          "glue:GetDatabases",
          "glue:GetTable",
          "glue:GetTables",
          "glue:CreateTable",
          "glue:UpdateTable",
          "glue:DeleteTable",
          "glue:GetPartitions",
          "glue:BatchCreatePartition"
        ]
        Resource = ["*"]
      },
      {
        Sid    = "KMSDecryptEncrypt"
        Effect = "Allow"
        Action = [
          "kms:Decrypt",
          "kms:Encrypt",
          "kms:GenerateDataKey",
          "kms:DescribeKey"
        ]
        Resource = [var.kms_key_arn]
      }
    ]
  })
}

# Flink streaming role (more restricted)
resource "aws_iam_role" "flink_executor" {
  name = "iceberg-flink-executor-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Federated = var.eks_oidc_provider_arn
        }
        Action = "sts:AssumeRoleWithWebIdentity"
        Condition = {
          StringEquals = {
            "${var.eks_oidc_provider_url}:sub" = "system:serviceaccount:flink:flink-executor"
          }
        }
      }
    ]
  })
}

# Compaction service role (needs delete permissions)
resource "aws_iam_role" "compaction_service" {
  name = "iceberg-compaction-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Federated = var.eks_oidc_provider_arn
        }
        Action = "sts:AssumeRoleWithWebIdentity"
        Condition = {
          StringEquals = {
            "${var.eks_oidc_provider_url}:sub" = "system:serviceaccount:iceberg-maintenance:compaction-sa"
          }
        }
      }
    ]
  })
}

resource "aws_iam_role_policy" "compaction_s3" {
  name = "compaction-s3-access"
  role = aws_iam_role.compaction_service.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket",
          "s3:GetBucketLocation"
        ]
        Resource = [
          var.curated_bucket_arn,
          "${var.curated_bucket_arn}/*"
        ]
      }
    ]
  })
}

output "spark_executor_role_arn" {
  value = aws_iam_role.spark_executor.arn
}

output "flink_executor_role_arn" {
  value = aws_iam_role.flink_executor.arn
}

output "compaction_role_arn" {
  value = aws_iam_role.compaction_service.arn
}
```

### Networking Module (VPC Endpoints)

```hcl
# modules/networking/main.tf

variable "vpc_id" {
  type = string
}

variable "private_subnet_ids" {
  type = list(string)
}

variable "private_route_table_ids" {
  type = list(string)
}

variable "environment" {
  type = string
}

data "aws_region" "current" {}

# S3 Gateway Endpoint (free, no data transfer charges)
resource "aws_vpc_endpoint" "s3" {
  vpc_id       = var.vpc_id
  service_name = "com.amazonaws.${data.aws_region.current.name}.s3"
  vpc_endpoint_type = "Gateway"

  route_table_ids = var.private_route_table_ids

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "AllowLakehouseBuckets"
        Effect    = "Allow"
        Principal = "*"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket",
          "s3:GetBucketLocation",
          "s3:AbortMultipartUpload"
        ]
        Resource = ["*"]
      }
    ]
  })

  tags = {
    Name        = "s3-endpoint-${var.environment}"
    Environment = var.environment
  }
}

# Glue Interface Endpoint
resource "aws_vpc_endpoint" "glue" {
  vpc_id              = var.vpc_id
  service_name        = "com.amazonaws.${data.aws_region.current.name}.glue"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = var.private_subnet_ids
  security_group_ids  = [aws_security_group.vpc_endpoints.id]
  private_dns_enabled = true

  tags = {
    Name        = "glue-endpoint-${var.environment}"
    Environment = var.environment
  }
}

# KMS Interface Endpoint
resource "aws_vpc_endpoint" "kms" {
  vpc_id              = var.vpc_id
  service_name        = "com.amazonaws.${data.aws_region.current.name}.kms"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = var.private_subnet_ids
  security_group_ids  = [aws_security_group.vpc_endpoints.id]
  private_dns_enabled = true

  tags = {
    Name        = "kms-endpoint-${var.environment}"
    Environment = var.environment
  }
}

resource "aws_security_group" "vpc_endpoints" {
  name_prefix = "vpc-endpoints-${var.environment}-"
  vpc_id      = var.vpc_id

  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["10.0.0.0/8"]
  }

  tags = {
    Name        = "vpc-endpoints-sg-${var.environment}"
    Environment = var.environment
  }
}
```

### EKS Platform Module

```hcl
# modules/eks-platform/main.tf

variable "environment" {
  type = string
}

variable "cluster_name" {
  type = string
}

variable "vpc_id" {
  type = string
}

variable "private_subnet_ids" {
  type = list(string)
}

module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 19.0"

  cluster_name    = var.cluster_name
  cluster_version = "1.29"

  vpc_id     = var.vpc_id
  subnet_ids = var.private_subnet_ids

  cluster_endpoint_private_access = true
  cluster_endpoint_public_access  = false

  eks_managed_node_groups = {
    # System workloads (operators, controllers)
    system = {
      instance_types = ["m6i.large"]
      min_size       = 2
      max_size       = 4
      desired_size   = 2

      labels = {
        workload-type = "system"
      }
    }

    # Spark drivers
    spark_drivers = {
      instance_types = ["m6i.xlarge"]
      min_size       = 1
      max_size       = 10
      desired_size   = 2

      labels = {
        workload-type = "spark-driver"
      }

      taints = [{
        key    = "spark-role"
        value  = "driver"
        effect = "NO_SCHEDULE"
      }]
    }

    # Spark executors (spot instances for cost savings)
    spark_executors = {
      instance_types = ["r6i.2xlarge", "r6i.4xlarge", "r5.2xlarge", "r5.4xlarge"]
      capacity_type  = "SPOT"
      min_size       = 0
      max_size       = 100
      desired_size   = 0

      labels = {
        workload-type = "spark-executor"
      }

      taints = [{
        key    = "spark-role"
        value  = "executor"
        effect = "NO_SCHEDULE"
      }]
    }

    # Flink (on-demand for stability)
    flink = {
      instance_types = ["m6i.2xlarge"]
      min_size       = 2
      max_size       = 20
      desired_size   = 4

      labels = {
        workload-type = "flink"
      }

      taints = [{
        key    = "flink-role"
        value  = "taskmanager"
        effect = "NO_SCHEDULE"
      }]
    }
  }

  manage_aws_auth_configmap = true

  tags = {
    Environment = var.environment
    Platform    = "iceberg-lakehouse"
  }
}

output "cluster_endpoint" {
  value = module.eks.cluster_endpoint
}

output "cluster_name" {
  value = module.eks.cluster_name
}

output "oidc_provider_arn" {
  value = module.eks.oidc_provider_arn
}

output "oidc_provider_url" {
  value = module.eks.cluster_oidc_issuer_url
}
```

### Environment Composition

```hcl
# environments/prod/main.tf

terraform {
  backend "s3" {
    bucket         = "iceberg-platform-tfstate"
    key            = "prod/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "terraform-locks"
    encrypt        = true
  }
}

provider "aws" {
  region = "us-east-1"

  default_tags {
    tags = {
      Environment = "prod"
      Project     = "iceberg-lakehouse"
      ManagedBy   = "terraform"
    }
  }
}

module "networking" {
  source              = "../../modules/networking"
  environment         = "prod"
  vpc_id              = var.vpc_id
  private_subnet_ids  = var.private_subnet_ids
  private_route_table_ids = var.private_route_table_ids
}

module "s3_lakehouse" {
  source      = "../../modules/s3-lakehouse"
  environment = "prod"
}

module "eks_platform" {
  source             = "../../modules/eks-platform"
  environment        = "prod"
  cluster_name       = "iceberg-prod"
  vpc_id             = var.vpc_id
  private_subnet_ids = var.private_subnet_ids
}

module "iam_roles" {
  source                = "../../modules/iam-roles"
  environment           = "prod"
  curated_bucket_arn    = module.s3_lakehouse.curated_bucket_arn
  raw_bucket_arn        = module.s3_lakehouse.raw_bucket_arn
  kms_key_arn           = module.s3_lakehouse.kms_key_arn
  eks_oidc_provider_arn = module.eks_platform.oidc_provider_arn
  eks_oidc_provider_url = module.eks_platform.oidc_provider_url
}

module "glue_catalog" {
  source               = "../../modules/glue-catalog"
  environment          = "prod"
  curated_bucket_name  = module.s3_lakehouse.curated_bucket_name
  lakeformation_role_arn = module.iam_roles.compaction_role_arn
}
```

---

## Kubernetes Deployments

### Spark Operator

```yaml
# k8s/spark-operator/namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: spark
  labels:
    app.kubernetes.io/managed-by: argocd
---
# k8s/spark-operator/service-account.yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: spark-executor
  namespace: spark
  annotations:
    eks.amazonaws.com/role-arn: arn:aws:iam::ACCOUNT_ID:role/iceberg-spark-executor-prod
---
# k8s/spark-operator/spark-application.yaml
apiVersion: sparkoperator.k8s.io/v1beta2
kind: ScheduledSparkApplication
metadata:
  name: iceberg-compaction-daily
  namespace: spark
spec:
  schedule: "0 2 * * *"
  concurrencyPolicy: Forbid
  template:
    type: Scala
    mode: cluster
    image: "company-registry.io/spark-iceberg:3.5.1-1.4.0"
    imagePullPolicy: Always
    mainClass: com.company.iceberg.CompactionJob
    mainApplicationFile: "local:///opt/spark/jars/iceberg-jobs.jar"
    sparkVersion: "3.5.1"
    restartPolicy:
      type: OnFailure
      onFailureRetries: 3
      onFailureRetryInterval: 60
      onSubmissionFailureRetries: 3
    sparkConf:
      "spark.sql.catalog.glue_catalog": "org.apache.iceberg.spark.SparkCatalog"
      "spark.sql.catalog.glue_catalog.catalog-impl": "org.apache.iceberg.aws.glue.GlueCatalog"
      "spark.sql.catalog.glue_catalog.warehouse": "s3://iceberg-lakehouse-prod-curated/"
      "spark.sql.catalog.glue_catalog.io-impl": "org.apache.iceberg.aws.s3.S3FileIO"
      "spark.hadoop.fs.s3a.endpoint": "s3.us-east-1.amazonaws.com"
      "spark.kubernetes.allocation.batch.size": "10"
      "spark.sql.shuffle.partitions": "200"
      "spark.sql.iceberg.handle-timestamp-without-timezone": "true"
    driver:
      cores: 2
      memory: "4g"
      serviceAccount: spark-executor
      labels:
        workload-type: spark-driver
      tolerations:
        - key: spark-role
          value: driver
          effect: NoSchedule
      nodeSelector:
        workload-type: spark-driver
    executor:
      cores: 4
      instances: 10
      memory: "8g"
      serviceAccount: spark-executor
      labels:
        workload-type: spark-executor
      tolerations:
        - key: spark-role
          value: executor
          effect: NoSchedule
      nodeSelector:
        workload-type: spark-executor
---
# Ad-hoc Spark application for ETL
apiVersion: sparkoperator.k8s.io/v1beta2
kind: SparkApplication
metadata:
  name: iceberg-etl-bronze-to-silver
  namespace: spark
spec:
  type: Python
  mode: cluster
  image: "company-registry.io/spark-iceberg:3.5.1-1.4.0"
  mainApplicationFile: "s3a://iceberg-lakehouse-prod-raw/jobs/bronze_to_silver.py"
  sparkVersion: "3.5.1"
  sparkConf:
    "spark.sql.catalog.glue_catalog": "org.apache.iceberg.spark.SparkCatalog"
    "spark.sql.catalog.glue_catalog.catalog-impl": "org.apache.iceberg.aws.glue.GlueCatalog"
    "spark.sql.catalog.glue_catalog.warehouse": "s3://iceberg-lakehouse-prod-curated/"
    "spark.sql.extensions": "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions"
  driver:
    cores: 2
    memory: "4g"
    serviceAccount: spark-executor
  executor:
    cores: 4
    instances: 20
    memory: "16g"
    serviceAccount: spark-executor
```

### Flink Operator

```yaml
# k8s/flink-operator/namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: flink
  labels:
    app.kubernetes.io/managed-by: argocd
---
# k8s/flink-operator/service-account.yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: flink-executor
  namespace: flink
  annotations:
    eks.amazonaws.com/role-arn: arn:aws:iam::ACCOUNT_ID:role/iceberg-flink-executor-prod
---
# k8s/flink-operator/flink-deployment.yaml
apiVersion: flink.apache.org/v1beta1
kind: FlinkDeployment
metadata:
  name: iceberg-streaming-ingestion
  namespace: flink
spec:
  image: company-registry.io/flink-iceberg:1.18-1.4.0
  flinkVersion: v1_18
  flinkConfiguration:
    taskmanager.numberOfTaskSlots: "4"
    state.backend: rocksdb
    state.checkpoints.dir: s3://iceberg-lakehouse-prod-curated/flink-checkpoints/
    state.savepoints.dir: s3://iceberg-lakehouse-prod-curated/flink-savepoints/
    execution.checkpointing.interval: "60000"
    execution.checkpointing.min-pause: "30000"
    restart-strategy: exponential-delay
    restart-strategy.exponential-delay.initial-backoff: "1s"
    restart-strategy.exponential-delay.max-backoff: "60s"
    # Iceberg-specific
    table.exec.iceberg.infer-source-parallelism: "true"
    # S3 settings
    s3.endpoint: s3.us-east-1.amazonaws.com
    s3.path-style-access: "false"
  serviceAccount: flink-executor
  jobManager:
    resource:
      memory: "2048m"
      cpu: 1
    replicas: 1
  taskManager:
    resource:
      memory: "8192m"
      cpu: 4
    replicas: 4
    podTemplate:
      spec:
        tolerations:
          - key: flink-role
            value: taskmanager
            effect: NoSchedule
        nodeSelector:
          workload-type: flink
  job:
    jarURI: local:///opt/flink/usrlib/iceberg-streaming.jar
    entryClass: com.company.flink.IcebergStreamingJob
    args:
      - "--kafka.bootstrap.servers"
      - "kafka-prod.internal:9092"
      - "--iceberg.warehouse"
      - "s3://iceberg-lakehouse-prod-curated/"
      - "--iceberg.catalog"
      - "glue_catalog"
    parallelism: 16
    upgradeMode: savepoint
    state: running
    savepointTriggerNonce: 0
---
# Flink Session Cluster for SQL workloads
apiVersion: flink.apache.org/v1beta1
kind: FlinkDeployment
metadata:
  name: flink-sql-session
  namespace: flink
spec:
  image: company-registry.io/flink-iceberg:1.18-1.4.0
  flinkVersion: v1_18
  flinkConfiguration:
    taskmanager.numberOfTaskSlots: "2"
    state.backend: rocksdb
    state.checkpoints.dir: s3://iceberg-lakehouse-prod-curated/flink-sql-checkpoints/
  serviceAccount: flink-executor
  jobManager:
    resource:
      memory: "4096m"
      cpu: 2
  taskManager:
    resource:
      memory: "8192m"
      cpu: 4
    replicas: 8
  mode: native
```

### Compaction & Maintenance Service

```yaml
# k8s/maintenance/compaction-cronjob.yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: iceberg-compaction
  namespace: iceberg-maintenance
spec:
  schedule: "0 */4 * * *"
  concurrencyPolicy: Forbid
  successfulJobsHistoryLimit: 5
  failedJobsHistoryLimit: 3
  jobTemplate:
    spec:
      backoffLimit: 2
      activeDeadlineSeconds: 7200
      template:
        metadata:
          labels:
            app: iceberg-compaction
        spec:
          serviceAccountName: compaction-sa
          restartPolicy: Never
          containers:
            - name: compaction
              image: company-registry.io/iceberg-maintenance:1.4.0
              command: ["python", "/app/compaction.py"]
              args:
                - "--catalog=glue_catalog"
                - "--warehouse=s3://iceberg-lakehouse-prod-curated/"
                - "--target-file-size-mb=256"
                - "--min-input-files=5"
                - "--tables=prod_silver.events,prod_silver.users,prod_gold.daily_metrics"
              env:
                - name: AWS_REGION
                  value: "us-east-1"
                - name: SPARK_CONF_DIR
                  value: "/opt/spark/conf"
              resources:
                requests:
                  memory: "4Gi"
                  cpu: "2"
                limits:
                  memory: "8Gi"
                  cpu: "4"
              volumeMounts:
                - name: spark-conf
                  mountPath: /opt/spark/conf
          volumes:
            - name: spark-conf
              configMap:
                name: spark-defaults
---
# Snapshot expiration job
apiVersion: batch/v1
kind: CronJob
metadata:
  name: iceberg-expire-snapshots
  namespace: iceberg-maintenance
spec:
  schedule: "0 6 * * *"
  concurrencyPolicy: Forbid
  jobTemplate:
    spec:
      template:
        spec:
          serviceAccountName: compaction-sa
          restartPolicy: Never
          containers:
            - name: expire-snapshots
              image: company-registry.io/iceberg-maintenance:1.4.0
              command: ["python", "/app/expire_snapshots.py"]
              args:
                - "--catalog=glue_catalog"
                - "--warehouse=s3://iceberg-lakehouse-prod-curated/"
                - "--older-than-days=7"
                - "--retain-last=5"
              resources:
                requests:
                  memory: "2Gi"
                  cpu: "1"
                limits:
                  memory: "4Gi"
                  cpu: "2"
---
# Orphan file cleanup
apiVersion: batch/v1
kind: CronJob
metadata:
  name: iceberg-orphan-cleanup
  namespace: iceberg-maintenance
spec:
  schedule: "0 8 * * 0"
  concurrencyPolicy: Forbid
  jobTemplate:
    spec:
      template:
        spec:
          serviceAccountName: compaction-sa
          restartPolicy: Never
          containers:
            - name: orphan-cleanup
              image: company-registry.io/iceberg-maintenance:1.4.0
              command: ["python", "/app/remove_orphans.py"]
              args:
                - "--catalog=glue_catalog"
                - "--warehouse=s3://iceberg-lakehouse-prod-curated/"
                - "--older-than-days=3"
                - "--dry-run=false"
              resources:
                requests:
                  memory: "2Gi"
                  cpu: "1"
---
# ConfigMap for Spark defaults
apiVersion: v1
kind: ConfigMap
metadata:
  name: spark-defaults
  namespace: iceberg-maintenance
data:
  spark-defaults.conf: |
    spark.sql.catalog.glue_catalog=org.apache.iceberg.spark.SparkCatalog
    spark.sql.catalog.glue_catalog.catalog-impl=org.apache.iceberg.aws.glue.GlueCatalog
    spark.sql.catalog.glue_catalog.warehouse=s3://iceberg-lakehouse-prod-curated/
    spark.sql.catalog.glue_catalog.io-impl=org.apache.iceberg.aws.s3.S3FileIO
    spark.sql.extensions=org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions
    spark.hadoop.fs.s3a.aws.credentials.provider=com.amazonaws.auth.WebIdentityTokenCredentialsProvider
```

---

## CI/CD Pipeline

### GitHub Actions - Schema Changes

```yaml
# .github/workflows/schema-migration.yml
name: Iceberg Schema Migration

on:
  pull_request:
    paths:
      - 'schemas/**'
  push:
    branches: [main]
    paths:
      - 'schemas/**'

env:
  AWS_REGION: us-east-1

jobs:
  validate-schema:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install pyiceberg[glue,s3] pydantic jsonschema

      - name: Validate schema definitions
        run: |
          python scripts/validate_schemas.py schemas/

      - name: Check backward compatibility
        run: |
          python scripts/check_schema_compatibility.py \
            --base-ref ${{ github.event.pull_request.base.sha }} \
            --head-ref ${{ github.sha }}

  apply-schema-dev:
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'
    needs: validate-schema
    runs-on: ubuntu-latest
    environment: dev
    permissions:
      id-token: write
      contents: read
    steps:
      - uses: actions/checkout@v4

      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::DEV_ACCOUNT:role/github-actions-iceberg
          aws-region: ${{ env.AWS_REGION }}

      - name: Apply schema changes to dev
        run: |
          python scripts/apply_schema_migration.py \
            --environment dev \
            --catalog glue \
            --warehouse s3://iceberg-lakehouse-dev-curated/

  apply-schema-prod:
    needs: apply-schema-dev
    runs-on: ubuntu-latest
    environment: prod
    permissions:
      id-token: write
      contents: read
    steps:
      - uses: actions/checkout@v4

      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::PROD_ACCOUNT:role/github-actions-iceberg
          aws-region: ${{ env.AWS_REGION }}

      - name: Apply schema changes to prod
        run: |
          python scripts/apply_schema_migration.py \
            --environment prod \
            --catalog glue \
            --warehouse s3://iceberg-lakehouse-prod-curated/
```

### GitHub Actions - Pipeline Deployment

```yaml
# .github/workflows/deploy-pipelines.yml
name: Deploy Data Pipelines

on:
  push:
    branches: [main]
    paths:
      - 'pipelines/**'
      - 'docker/**'

jobs:
  build-images:
    runs-on: ubuntu-latest
    permissions:
      id-token: write
      contents: read
    outputs:
      spark_image: ${{ steps.build.outputs.spark_tag }}
      flink_image: ${{ steps.build.outputs.flink_tag }}
    steps:
      - uses: actions/checkout@v4

      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::SHARED_ACCOUNT:role/github-actions-ecr
          aws-region: us-east-1

      - uses: aws-actions/amazon-ecr-login@v2
        id: ecr-login

      - name: Build and push images
        id: build
        run: |
          TAG="${{ github.sha }}"
          
          docker build -t ${{ steps.ecr-login.outputs.registry }}/spark-iceberg:${TAG} \
            -f docker/Dockerfile.spark .
          docker push ${{ steps.ecr-login.outputs.registry }}/spark-iceberg:${TAG}
          
          docker build -t ${{ steps.ecr-login.outputs.registry }}/flink-iceberg:${TAG} \
            -f docker/Dockerfile.flink .
          docker push ${{ steps.ecr-login.outputs.registry }}/flink-iceberg:${TAG}
          
          echo "spark_tag=${TAG}" >> $GITHUB_OUTPUT
          echo "flink_tag=${TAG}" >> $GITHUB_OUTPUT

  deploy-dev:
    needs: build-images
    runs-on: ubuntu-latest
    environment: dev
    steps:
      - uses: actions/checkout@v4

      - name: Update image tags in manifests
        run: |
          cd k8s/overlays/dev
          kustomize edit set image \
            spark-iceberg=ACCOUNT.dkr.ecr.us-east-1.amazonaws.com/spark-iceberg:${{ needs.build-images.outputs.spark_image }} \
            flink-iceberg=ACCOUNT.dkr.ecr.us-east-1.amazonaws.com/flink-iceberg:${{ needs.build-images.outputs.flink_image }}

      - name: Commit and push to GitOps repo
        run: |
          git config user.name "github-actions"
          git config user.email "actions@github.com"
          git add .
          git commit -m "Deploy pipelines: ${{ github.sha }}"
          git push

  deploy-prod:
    needs: [build-images, deploy-dev]
    runs-on: ubuntu-latest
    environment: prod
    steps:
      - uses: actions/checkout@v4

      - name: Update prod manifests
        run: |
          cd k8s/overlays/prod
          kustomize edit set image \
            spark-iceberg=ACCOUNT.dkr.ecr.us-east-1.amazonaws.com/spark-iceberg:${{ needs.build-images.outputs.spark_image }} \
            flink-iceberg=ACCOUNT.dkr.ecr.us-east-1.amazonaws.com/flink-iceberg:${{ needs.build-images.outputs.flink_image }}

      - name: Commit and push
        run: |
          git config user.name "github-actions"
          git config user.email "actions@github.com"
          git add .
          git commit -m "Prod deploy: ${{ github.sha }}"
          git push
```

### Schema Migration Script

```python
# scripts/apply_schema_migration.py
"""Apply Iceberg schema migrations using PyIceberg."""

import argparse
import yaml
from pathlib import Path
from pyiceberg.catalog import load_catalog
from pyiceberg.schema import Schema
from pyiceberg.types import (
    NestedField, StringType, LongType, TimestampType,
    DoubleType, BooleanType, MapType, ListType
)

TYPE_MAP = {
    "string": StringType(),
    "long": LongType(),
    "timestamp": TimestampType(),
    "double": DoubleType(),
    "boolean": BooleanType(),
}

def load_schema_definition(path: Path) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)

def apply_migration(catalog, table_id: str, schema_def: dict):
    table = catalog.load_table(table_id)
    
    with table.update_schema() as update:
        for col in schema_def.get("add_columns", []):
            update.add_column(
                path=col["name"],
                field_type=TYPE_MAP[col["type"]],
                doc=col.get("doc", ""),
                required=col.get("required", False),
            )
        
        for col in schema_def.get("drop_columns", []):
            update.delete_column(col)
        
        for rename in schema_def.get("rename_columns", []):
            update.rename_column(rename["from"], rename["to"])

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--environment", required=True)
    parser.add_argument("--catalog", default="glue")
    parser.add_argument("--warehouse", required=True)
    args = parser.parse_args()

    catalog = load_catalog(
        "glue_catalog",
        **{
            "type": "glue",
            "warehouse": args.warehouse,
            "region_name": "us-east-1",
        }
    )

    schemas_dir = Path("schemas") / args.environment
    for schema_file in schemas_dir.glob("*.yml"):
        schema_def = load_schema_definition(schema_file)
        table_id = f"{schema_def['database']}.{schema_def['table']}"
        print(f"Applying migration to {table_id}")
        apply_migration(catalog, table_id, schema_def)
        print(f"  Done.")

if __name__ == "__main__":
    main()
```

---

## Catalog Setup

### AWS Glue Configuration

```hcl
# Glue catalog Spark configuration (spark-defaults.conf)
spark.sql.catalog.glue_catalog=org.apache.iceberg.spark.SparkCatalog
spark.sql.catalog.glue_catalog.catalog-impl=org.apache.iceberg.aws.glue.GlueCatalog
spark.sql.catalog.glue_catalog.warehouse=s3://iceberg-lakehouse-prod-curated/
spark.sql.catalog.glue_catalog.io-impl=org.apache.iceberg.aws.s3.S3FileIO
spark.sql.catalog.glue_catalog.lock-impl=org.apache.iceberg.aws.glue.DynamoLockManager
spark.sql.catalog.glue_catalog.lock.table=iceberg-lock-table
```

### Nessie Catalog Deployment

```yaml
# k8s/nessie/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: nessie
  namespace: iceberg-catalog
spec:
  replicas: 3
  selector:
    matchLabels:
      app: nessie
  template:
    metadata:
      labels:
        app: nessie
    spec:
      containers:
        - name: nessie
          image: ghcr.io/projectnessie/nessie:0.76.0
          ports:
            - containerPort: 19120
          env:
            - name: NESSIE_VERSION_STORE_TYPE
              value: "DYNAMODB"
            - name: QUARKUS_DYNAMODB_AWS_REGION
              value: "us-east-1"
            - name: NESSIE_VERSION_STORE_DYNAMODB_TABLE_PREFIX
              value: "nessie-prod-"
          resources:
            requests:
              memory: "1Gi"
              cpu: "500m"
            limits:
              memory: "2Gi"
              cpu: "1"
          livenessProbe:
            httpGet:
              path: /api/v2/config
              port: 19120
            initialDelaySeconds: 30
          readinessProbe:
            httpGet:
              path: /api/v2/config
              port: 19120
---
apiVersion: v1
kind: Service
metadata:
  name: nessie
  namespace: iceberg-catalog
spec:
  selector:
    app: nessie
  ports:
    - port: 19120
      targetPort: 19120
  type: ClusterIP
```

### REST Catalog (Tabular/Polaris-style)

```yaml
# k8s/rest-catalog/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: iceberg-rest-catalog
  namespace: iceberg-catalog
spec:
  replicas: 3
  selector:
    matchLabels:
      app: iceberg-rest-catalog
  template:
    metadata:
      labels:
        app: iceberg-rest-catalog
    spec:
      containers:
        - name: catalog
          image: tabulario/iceberg-rest:0.10.0
          ports:
            - containerPort: 8181
          env:
            - name: CATALOG_WAREHOUSE
              value: "s3://iceberg-lakehouse-prod-curated/"
            - name: CATALOG_IO__IMPL
              value: "org.apache.iceberg.aws.s3.S3FileIO"
            - name: CATALOG_S3_ENDPOINT
              value: "https://s3.us-east-1.amazonaws.com"
            - name: AWS_REGION
              value: "us-east-1"
            - name: CATALOG_JDBC_URI
              valueFrom:
                secretKeyRef:
                  name: catalog-db-credentials
                  key: jdbc-url
          resources:
            requests:
              memory: "1Gi"
              cpu: "500m"
---
apiVersion: v1
kind: Service
metadata:
  name: iceberg-rest-catalog
  namespace: iceberg-catalog
spec:
  selector:
    app: iceberg-rest-catalog
  ports:
    - port: 8181
      targetPort: 8181
```

---

## IAM & Security Model

### Lake Formation Fine-Grained Access

```hcl
# Lake Formation permissions - table-level
resource "aws_lakeformation_permissions" "data_engineers_silver" {
  principal   = aws_iam_role.data_engineers.arn
  permissions = ["SELECT", "INSERT", "DELETE", "DESCRIBE", "ALTER"]

  table {
    database_name = "prod_silver"
    wildcard      = true
  }
}

# Column-level access for analysts (mask PII)
resource "aws_lakeformation_permissions" "analysts_events" {
  principal   = aws_iam_role.data_analysts.arn
  permissions = ["SELECT"]

  table_with_columns {
    database_name = "prod_silver"
    name          = "events"
    column_names  = ["event_id", "event_type", "timestamp", "category"]
    # Excludes: user_email, ip_address, device_id
  }
}

# Data science team - full read on gold
resource "aws_lakeformation_permissions" "data_science_gold" {
  principal   = aws_iam_role.data_science.arn
  permissions = ["SELECT", "DESCRIBE"]

  table {
    database_name = "prod_gold"
    wildcard      = true
  }
}

# Tag-based access control
resource "aws_lakeformation_resource_lf_tags" "pii_tag" {
  table {
    database_name = "prod_silver"
    name          = "users"
  }

  lf_tag {
    key   = "sensitivity"
    value = "pii"
  }
}

resource "aws_lakeformation_permissions" "pii_access" {
  principal   = aws_iam_role.pii_authorized.arn
  permissions = ["SELECT"]

  lf_tag_policy {
    resource_type = "TABLE"
    expression {
      key    = "sensitivity"
      values = ["pii"]
    }
  }
}
```

---

## Environment Management

### Kustomize Overlays

```yaml
# k8s/base/kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - spark-operator/
  - flink-operator/
  - maintenance/
  - nessie/

---
# k8s/overlays/dev/kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - ../../base
namePrefix: dev-
patches:
  - target:
      kind: FlinkDeployment
      name: iceberg-streaming-ingestion
    patch: |
      - op: replace
        path: /spec/taskManager/replicas
        value: 2
      - op: replace
        path: /spec/job/parallelism
        value: 4
  - target:
      kind: ScheduledSparkApplication
      name: iceberg-compaction-daily
    patch: |
      - op: replace
        path: /spec/template/executor/instances
        value: 3
configMapGenerator:
  - name: environment-config
    literals:
      - ENVIRONMENT=dev
      - WAREHOUSE=s3://iceberg-lakehouse-dev-curated/
      - CATALOG_DB_PREFIX=dev_

---
# k8s/overlays/prod/kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - ../../base
namePrefix: prod-
patches:
  - target:
      kind: FlinkDeployment
      name: iceberg-streaming-ingestion
    patch: |
      - op: replace
        path: /spec/taskManager/replicas
        value: 8
      - op: replace
        path: /spec/job/parallelism
        value: 32
configMapGenerator:
  - name: environment-config
    literals:
      - ENVIRONMENT=prod
      - WAREHOUSE=s3://iceberg-lakehouse-prod-curated/
      - CATALOG_DB_PREFIX=prod_
```

---

## Blue-Green Deployment

### Strategy for Flink Streaming Pipelines

```yaml
# k8s/blue-green/flink-blue-green.yaml
#
# Blue-green for Flink: deploy new version reading from same Kafka topics
# with a different consumer group, validate output, then switch.

# Green (new version)
apiVersion: flink.apache.org/v1beta1
kind: FlinkDeployment
metadata:
  name: iceberg-streaming-green
  namespace: flink
  labels:
    deployment-slot: green
    pipeline: streaming-ingestion
spec:
  image: company-registry.io/flink-iceberg:NEW_VERSION
  flinkVersion: v1_18
  flinkConfiguration:
    taskmanager.numberOfTaskSlots: "4"
    state.backend: rocksdb
    state.checkpoints.dir: s3://iceberg-lakehouse-prod-curated/flink-checkpoints-green/
  serviceAccount: flink-executor
  jobManager:
    resource:
      memory: "2048m"
      cpu: 1
  taskManager:
    resource:
      memory: "8192m"
      cpu: 4
    replicas: 4
  job:
    jarURI: local:///opt/flink/usrlib/iceberg-streaming.jar
    entryClass: com.company.flink.IcebergStreamingJob
    args:
      - "--kafka.bootstrap.servers"
      - "kafka-prod.internal:9092"
      - "--kafka.consumer.group"
      - "iceberg-ingestion-green"  # Different consumer group
      - "--iceberg.warehouse"
      - "s3://iceberg-lakehouse-prod-curated/"
      - "--iceberg.database"
      - "prod_silver_green"  # Write to staging tables
    parallelism: 16
    upgradeMode: savepoint
    state: running
---
# Validation job that compares blue vs green output
apiVersion: batch/v1
kind: Job
metadata:
  name: blue-green-validation
  namespace: flink
spec:
  template:
    spec:
      containers:
        - name: validator
          image: company-registry.io/iceberg-maintenance:1.4.0
          command: ["python", "/app/validate_blue_green.py"]
          args:
            - "--blue-table=prod_silver.events"
            - "--green-table=prod_silver_green.events"
            - "--sample-size=10000"
            - "--tolerance=0.01"
      restartPolicy: Never
```

### Blue-Green Cutover Script

```bash
#!/bin/bash
# scripts/blue-green-cutover.sh
set -euo pipefail

NAMESPACE="flink"
BLUE_DEPLOYMENT="iceberg-streaming-blue"
GREEN_DEPLOYMENT="iceberg-streaming-green"

echo "=== Blue-Green Cutover ==="

# 1. Take savepoint of blue
echo "Taking savepoint of blue deployment..."
kubectl patch flinkdeployment ${BLUE_DEPLOYMENT} -n ${NAMESPACE} \
  --type=merge -p '{"spec":{"job":{"savepointTriggerNonce": '$(date +%s)'}}}' 

# Wait for savepoint
sleep 30

# 2. Stop blue
echo "Stopping blue deployment..."
kubectl patch flinkdeployment ${BLUE_DEPLOYMENT} -n ${NAMESPACE} \
  --type=merge -p '{"spec":{"job":{"state":"suspended"}}}'

# 3. Update green to use production consumer group and tables
kubectl patch flinkdeployment ${GREEN_DEPLOYMENT} -n ${NAMESPACE} \
  --type=json -p='[
    {"op":"replace","path":"/spec/job/args/3","value":"iceberg-ingestion-prod"},
    {"op":"replace","path":"/spec/job/args/7","value":"prod_silver"}
  ]'

# 4. Rename deployments
kubectl label flinkdeployment ${BLUE_DEPLOYMENT} -n ${NAMESPACE} deployment-slot=retired
kubectl label flinkdeployment ${GREEN_DEPLOYMENT} -n ${NAMESPACE} deployment-slot=blue

echo "Cutover complete. Green is now the active (blue) deployment."
```

---

## GitOps with ArgoCD

### ArgoCD Application Definitions

```yaml
# argocd/applications/iceberg-platform.yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: iceberg-platform-prod
  namespace: argocd
  finalizers:
    - resources-finalizer.argocd.argoproj.io
spec:
  project: data-platform
  source:
    repoURL: https://github.com/company/iceberg-platform.git
    targetRevision: main
    path: k8s/overlays/prod
  destination:
    server: https://kubernetes.default.svc
    namespace: ""  # Uses namespaces defined in manifests
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
      allowEmpty: false
    syncOptions:
      - CreateNamespace=true
      - PrunePropagationPolicy=foreground
      - PruneLast=true
    retry:
      limit: 5
      backoff:
        duration: 5s
        factor: 2
        maxDuration: 3m
  ignoreDifferences:
    - group: flink.apache.org
      kind: FlinkDeployment
      jsonPointers:
        - /spec/job/savepointTriggerNonce
---
# ArgoCD Project with RBAC
apiVersion: argoproj.io/v1alpha1
kind: AppProject
metadata:
  name: data-platform
  namespace: argocd
spec:
  description: Iceberg data platform
  sourceRepos:
    - https://github.com/company/iceberg-platform.git
  destinations:
    - namespace: spark
      server: https://kubernetes.default.svc
    - namespace: flink
      server: https://kubernetes.default.svc
    - namespace: iceberg-maintenance
      server: https://kubernetes.default.svc
    - namespace: iceberg-catalog
      server: https://kubernetes.default.svc
  clusterResourceWhitelist:
    - group: ''
      kind: Namespace
  namespaceResourceWhitelist:
    - group: '*'
      kind: '*'
  roles:
    - name: data-engineer
      policies:
        - p, proj:data-platform:data-engineer, applications, get, data-platform/*, allow
        - p, proj:data-platform:data-engineer, applications, sync, data-platform/*, allow
      groups:
        - data-engineering-team
```

### Flux Configuration (Alternative)

```yaml
# flux/clusters/prod/iceberg-platform.yaml
apiVersion: source.toolkit.fluxcd.io/v1
kind: GitRepository
metadata:
  name: iceberg-platform
  namespace: flux-system
spec:
  interval: 1m
  url: https://github.com/company/iceberg-platform.git
  ref:
    branch: main
  secretRef:
    name: github-credentials
---
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: iceberg-platform-prod
  namespace: flux-system
spec:
  interval: 5m
  sourceRef:
    kind: GitRepository
    name: iceberg-platform
  path: ./k8s/overlays/prod
  prune: true
  healthChecks:
    - apiVersion: apps/v1
      kind: Deployment
      name: nessie
      namespace: iceberg-catalog
    - apiVersion: flink.apache.org/v1beta1
      kind: FlinkDeployment
      name: iceberg-streaming-ingestion
      namespace: flink
  timeout: 10m
```

---

## Secrets Management

### AWS Secrets Manager Integration

```yaml
# k8s/secrets/external-secrets.yaml
apiVersion: external-secrets.io/v1beta1
kind: SecretStore
metadata:
  name: aws-secrets-manager
  namespace: iceberg-catalog
spec:
  provider:
    aws:
      service: SecretsManager
      region: us-east-1
      auth:
        jwt:
          serviceAccountRef:
            name: external-secrets-sa
---
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: catalog-db-credentials
  namespace: iceberg-catalog
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: aws-secrets-manager
    kind: SecretStore
  target:
    name: catalog-db-credentials
    creationPolicy: Owner
  data:
    - secretKey: jdbc-url
      remoteRef:
        key: prod/iceberg/catalog-db
        property: jdbc_url
    - secretKey: username
      remoteRef:
        key: prod/iceberg/catalog-db
        property: username
    - secretKey: password
      remoteRef:
        key: prod/iceberg/catalog-db
        property: password
---
# Kafka credentials
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: kafka-credentials
  namespace: flink
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: aws-secrets-manager
    kind: SecretStore
  target:
    name: kafka-credentials
  data:
    - secretKey: sasl-username
      remoteRef:
        key: prod/iceberg/kafka
        property: sasl_username
    - secretKey: sasl-password
      remoteRef:
        key: prod/iceberg/kafka
        property: sasl_password
```

### HashiCorp Vault Integration

```yaml
# k8s/secrets/vault-injector.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: iceberg-rest-catalog
  namespace: iceberg-catalog
spec:
  template:
    metadata:
      annotations:
        vault.hashicorp.com/agent-inject: "true"
        vault.hashicorp.com/role: "iceberg-catalog"
        vault.hashicorp.com/agent-inject-secret-db: "secret/data/iceberg/catalog-db"
        vault.hashicorp.com/agent-inject-template-db: |
          {{- with secret "secret/data/iceberg/catalog-db" -}}
          export CATALOG_JDBC_URI="{{ .Data.data.jdbc_url }}"
          export CATALOG_JDBC_USER="{{ .Data.data.username }}"
          export CATALOG_JDBC_PASS="{{ .Data.data.password }}"
          {{- end }}
    spec:
      serviceAccountName: iceberg-catalog-sa
      containers:
        - name: catalog
          command: ["/bin/sh", "-c"]
          args: ["source /vault/secrets/db && exec java -jar /app/catalog.jar"]
```

---

## Cost Optimization

### Spot Instance Configuration

```hcl
# Spot instance handling for Spark executors
resource "aws_eks_node_group" "spark_executors_spot" {
  cluster_name    = module.eks.cluster_name
  node_group_name = "spark-executors-spot"
  node_role_arn   = aws_iam_role.eks_node.arn
  subnet_ids      = var.private_subnet_ids

  capacity_type = "SPOT"

  instance_types = [
    "r6i.2xlarge",   # Primary
    "r6i.4xlarge",
    "r5.2xlarge",    # Fallback
    "r5.4xlarge",
    "r5a.2xlarge",   # AMD fallback
    "r5a.4xlarge",
  ]

  scaling_config {
    desired_size = 0
    max_size     = 200
    min_size     = 0
  }

  labels = {
    "workload-type" = "spark-executor"
    "capacity-type" = "spot"
  }

  taint {
    key    = "spark-role"
    value  = "executor"
    effect = "NO_SCHEDULE"
  }
}
```

### S3 Storage Class Automation

```python
# scripts/optimize_storage_classes.py
"""Automatically transition cold Iceberg data to cheaper storage."""

from pyiceberg.catalog import load_catalog
from datetime import datetime, timedelta
import boto3

s3 = boto3.client('s3')

def get_cold_data_files(table, days_threshold=90):
    """Find data files not accessed in N days via snapshots."""
    current_snapshot = table.current_snapshot()
    cutoff = datetime.now() - timedelta(days=days_threshold)
    
    cold_files = []
    for manifest in current_snapshot.manifests(table.io):
        for entry in manifest.fetch(table.io):
            # Check file creation time from metadata
            if entry.data_file.file_size_in_bytes > 0:
                # Approximate age from snapshot timestamps
                cold_files.append(entry.data_file.file_path)
    
    return cold_files

def transition_to_ia(bucket, keys):
    """Transition objects to Intelligent-Tiering."""
    for key in keys:
        s3.copy_object(
            Bucket=bucket,
            Key=key,
            CopySource={'Bucket': bucket, 'Key': key},
            StorageClass='INTELLIGENT_TIERING',
            MetadataDirective='COPY'
        )

if __name__ == "__main__":
    catalog = load_catalog("glue_catalog", type="glue", warehouse="s3://iceberg-lakehouse-prod-curated/")
    
    tables = ["prod_silver.events", "prod_silver.transactions"]
    for table_id in tables:
        table = catalog.load_table(table_id)
        cold_files = get_cold_data_files(table, days_threshold=90)
        print(f"{table_id}: {len(cold_files)} cold files to transition")
```

### Cost Monitoring Dashboard Config

```yaml
# k8s/monitoring/cost-alerts.yaml
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: iceberg-cost-alerts
  namespace: monitoring
spec:
  groups:
    - name: iceberg-costs
      rules:
        - alert: SparkExecutorOverProvisioned
          expr: |
            avg_over_time(spark_executor_cpu_utilization[1h]) < 0.3
            and spark_executor_count > 5
          for: 30m
          labels:
            severity: warning
          annotations:
            summary: "Spark executors under-utilized, consider reducing count"

        - alert: S3RequestCostSpike
          expr: |
            rate(aws_s3_requests_total{bucket=~"iceberg-lakehouse.*"}[1h]) > 10000
          for: 15m
          labels:
            severity: warning
          annotations:
            summary: "High S3 request rate - check for metadata thrashing"
```

---

## Helm Charts

### Iceberg Maintenance Helm Chart

```yaml
# charts/iceberg-maintenance/Chart.yaml
apiVersion: v2
name: iceberg-maintenance
description: Iceberg table maintenance jobs (compaction, expiration, orphan cleanup)
version: 1.0.0
appVersion: "1.4.0"

---
# charts/iceberg-maintenance/values.yaml
image:
  repository: company-registry.io/iceberg-maintenance
  tag: "1.4.0"
  pullPolicy: IfNotPresent

serviceAccount:
  create: true
  name: compaction-sa
  annotations:
    eks.amazonaws.com/role-arn: ""

catalog:
  type: glue
  warehouse: "s3://iceberg-lakehouse-prod-curated/"
  region: us-east-1

compaction:
  enabled: true
  schedule: "0 */4 * * *"
  targetFileSizeMb: 256
  minInputFiles: 5
  tables: []
  resources:
    requests:
      memory: "4Gi"
      cpu: "2"
    limits:
      memory: "8Gi"
      cpu: "4"

expireSnapshots:
  enabled: true
  schedule: "0 6 * * *"
  olderThanDays: 7
  retainLast: 5

orphanCleanup:
  enabled: true
  schedule: "0 8 * * 0"
  olderThanDays: 3
  dryRun: false

---
# charts/iceberg-maintenance/templates/compaction-cronjob.yaml
{{- if .Values.compaction.enabled }}
apiVersion: batch/v1
kind: CronJob
metadata:
  name: {{ include "iceberg-maintenance.fullname" . }}-compaction
spec:
  schedule: {{ .Values.compaction.schedule | quote }}
  concurrencyPolicy: Forbid
  jobTemplate:
    spec:
      backoffLimit: 2
      activeDeadlineSeconds: 7200
      template:
        spec:
          serviceAccountName: {{ .Values.serviceAccount.name }}
          restartPolicy: Never
          containers:
            - name: compaction
              image: "{{ .Values.image.repository }}:{{ .Values.image.tag }}"
              command: ["python", "/app/compaction.py"]
              args:
                - "--catalog={{ .Values.catalog.type }}"
                - "--warehouse={{ .Values.catalog.warehouse }}"
                - "--target-file-size-mb={{ .Values.compaction.targetFileSizeMb }}"
                - "--min-input-files={{ .Values.compaction.minInputFiles }}"
                - "--tables={{ join "," .Values.compaction.tables }}"
              env:
                - name: AWS_REGION
                  value: {{ .Values.catalog.region | quote }}
              resources:
                {{- toYaml .Values.compaction.resources | nindent 16 }}
{{- end }}

---
# charts/iceberg-maintenance/templates/serviceaccount.yaml
{{- if .Values.serviceAccount.create }}
apiVersion: v1
kind: ServiceAccount
metadata:
  name: {{ .Values.serviceAccount.name }}
  annotations:
    {{- toYaml .Values.serviceAccount.annotations | nindent 4 }}
{{- end }}
```

### Spark Operator Helm Values

```yaml
# helm-values/spark-operator-prod.yaml
sparkOperator:
  replicaCount: 2
  image:
    repository: ghcr.io/kubeflow/spark-operator
    tag: v2.0.0

  webhook:
    enable: true

  resources:
    requests:
      memory: "512Mi"
      cpu: "250m"
    limits:
      memory: "1Gi"
      cpu: "500m"

  nodeSelector:
    workload-type: system

  serviceAccounts:
    spark:
      create: true
      name: spark-executor
      annotations:
        eks.amazonaws.com/role-arn: arn:aws:iam::ACCOUNT_ID:role/iceberg-spark-executor-prod

  # Watch specific namespaces
  sparkJobNamespace: spark
```

### Flink Operator Helm Values

```yaml
# helm-values/flink-operator-prod.yaml
flink-kubernetes-operator:
  image:
    repository: apache/flink-kubernetes-operator
    tag: "1.8.0"

  replicas: 2

  operatorConfiguration:
    flink.kubernetes.operator.reconcile.interval: "30s"
    flink.kubernetes.operator.observer.progress-check.interval: "10s"
    flink.kubernetes.operator.savepoint.trigger.grace-period: "60s"

  watchNamespaces:
    - flink

  resources:
    requests:
      memory: "512Mi"
      cpu: "250m"
    limits:
      memory: "1Gi"
      cpu: "500m"

  nodeSelector:
    workload-type: system
```

---

## Deployment Checklist

### Pre-Production Validation

```bash
#!/bin/bash
# scripts/pre-deploy-checks.sh
set -euo pipefail

echo "=== Pre-deployment Validation ==="

# 1. Terraform plan
echo "[1/6] Running Terraform plan..."
cd terraform/environments/prod
terraform plan -detailed-exitcode -out=tfplan
if [ $? -eq 2 ]; then
  echo "  Infrastructure changes detected. Review plan."
fi

# 2. Kustomize build validation
echo "[2/6] Validating Kubernetes manifests..."
kustomize build k8s/overlays/prod | kubeval --strict

# 3. Helm template validation
echo "[3/6] Validating Helm charts..."
helm template iceberg-maintenance charts/iceberg-maintenance \
  -f helm-values/maintenance-prod.yaml | kubeval --strict

# 4. Schema compatibility check
echo "[4/6] Checking schema compatibility..."
python scripts/check_schema_compatibility.py --environment prod

# 5. S3 bucket accessibility
echo "[5/6] Verifying S3 access..."
aws s3 ls s3://iceberg-lakehouse-prod-curated/ > /dev/null 2>&1
echo "  S3 access verified."

# 6. Catalog connectivity
echo "[6/6] Verifying catalog connectivity..."
python -c "
from pyiceberg.catalog import load_catalog
cat = load_catalog('glue', type='glue', warehouse='s3://iceberg-lakehouse-prod-curated/')
print(f'  Connected. Databases: {cat.list_namespaces()}')
"

echo "=== All checks passed ==="
```

---

## Summary

| Component | Tool | Configuration |
|-----------|------|---------------|
| Infrastructure | Terraform | Modular, per-environment |
| Container Orchestration | EKS | Spot for executors, on-demand for drivers |
| Spark | Spark Operator | ScheduledSparkApplication CRDs |
| Flink | Flink Operator | FlinkDeployment with savepoint upgrades |
| Catalog | AWS Glue / Nessie | DynamoDB backend for Nessie |
| GitOps | ArgoCD | Auto-sync with pruning |
| Secrets | External Secrets Operator | AWS Secrets Manager backend |
| CI/CD | GitHub Actions | Schema validation + image builds |
| Access Control | Lake Formation | Column-level, tag-based |
| Cost | Spot + S3 Tiering | Intelligent-Tiering + lifecycle rules |
