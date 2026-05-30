# =============================================================================
# Terraform Infrastructure for AI Platform
# Production-grade infrastructure on AWS
# =============================================================================

terraform {
  required_version = ">= 1.6.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.30"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.24"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.12"
    }
  }

  backend "s3" {
    bucket         = "ai-platform-terraform-state"
    key            = "prod/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "terraform-locks"
  }
}

provider "aws" {
  region = var.aws_region
  default_tags {
    tags = {
      Project     = "ai-platform"
      Environment = var.environment
      ManagedBy   = "terraform"
      Team        = "ai-engineering"
    }
  }
}

# =============================================================================
# VARIABLES
# =============================================================================

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "prod"
}

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "cluster_name" {
  description = "EKS cluster name"
  type        = string
  default     = "ai-platform-prod"
}

variable "vpc_cidr" {
  description = "VPC CIDR block"
  type        = string
  default     = "10.0.0.0/16"
}

variable "availability_zones" {
  description = "Availability zones"
  type        = list(string)
  default     = ["us-east-1a", "us-east-1b", "us-east-1c"]
}

# =============================================================================
# VPC AND NETWORKING
# =============================================================================

module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.4"

  name = "${var.cluster_name}-vpc"
  cidr = var.vpc_cidr

  azs             = var.availability_zones
  private_subnets = ["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24"]
  public_subnets  = ["10.0.101.0/24", "10.0.102.0/24", "10.0.103.0/24"]

  enable_nat_gateway   = true
  single_nat_gateway   = false
  enable_dns_hostnames = true
  enable_dns_support   = true

  # Tags required for EKS
  public_subnet_tags = {
    "kubernetes.io/role/elb"                    = 1
    "kubernetes.io/cluster/${var.cluster_name}" = "shared"
  }
  private_subnet_tags = {
    "kubernetes.io/role/internal-elb"           = 1
    "kubernetes.io/cluster/${var.cluster_name}" = "shared"
  }
}

# VPC Endpoints for private access to AWS services
resource "aws_vpc_endpoint" "s3" {
  vpc_id       = module.vpc.vpc_id
  service_name = "com.amazonaws.${var.aws_region}.s3"
  route_table_ids = module.vpc.private_route_table_ids
}

resource "aws_vpc_endpoint" "ecr_api" {
  vpc_id              = module.vpc.vpc_id
  service_name        = "com.amazonaws.${var.aws_region}.ecr.api"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = module.vpc.private_subnets
  security_group_ids  = [aws_security_group.vpc_endpoints.id]
  private_dns_enabled = true
}

resource "aws_security_group" "vpc_endpoints" {
  name_prefix = "vpc-endpoints-"
  vpc_id      = module.vpc.vpc_id

  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr]
  }
}

# =============================================================================
# EKS CLUSTER
# =============================================================================

module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 19.21"

  cluster_name    = var.cluster_name
  cluster_version = "1.28"

  vpc_id     = module.vpc.vpc_id
  subnet_ids = module.vpc.private_subnets

  cluster_endpoint_public_access  = true
  cluster_endpoint_private_access = true

  # Cluster addons
  cluster_addons = {
    coredns = {
      most_recent = true
    }
    kube-proxy = {
      most_recent = true
    }
    vpc-cni = {
      most_recent = true
    }
    aws-ebs-csi-driver = {
      most_recent              = true
      service_account_role_arn = module.ebs_csi_irsa.iam_role_arn
    }
  }

  # Node groups
  eks_managed_node_groups = {
    # General purpose nodes for API services
    general = {
      name           = "general"
      instance_types = ["m6i.xlarge"]
      min_size       = 3
      max_size       = 20
      desired_size   = 5

      labels = {
        node-type = "general"
      }
    }

    # High-memory nodes for vector DB
    high_memory = {
      name           = "high-memory"
      instance_types = ["r6i.2xlarge"]
      min_size       = 3
      max_size       = 6
      desired_size   = 3

      labels = {
        node-type = "high-memory"
      }

      taints = {
        dedicated = {
          key    = "workload-type"
          value  = "vector-db"
          effect = "NO_SCHEDULE"
        }
      }
    }

    # GPU nodes for inference (optional, for self-hosted models)
    gpu_inference = {
      name           = "gpu-inference"
      instance_types = ["g5.2xlarge"]
      min_size       = 0
      max_size       = 4
      desired_size   = 0

      ami_type = "AL2_x86_64_GPU"

      labels = {
        node-type = "gpu-inference"
        gpu-type  = "a10g"
      }

      taints = {
        gpu = {
          key    = "nvidia.com/gpu"
          value  = "true"
          effect = "NO_SCHEDULE"
        }
      }
    }
  }

  # IRSA for service accounts
  enable_irsa = true
}

module "ebs_csi_irsa" {
  source  = "terraform-aws-modules/iam/aws//modules/iam-role-for-service-accounts-eks"
  version = "~> 5.30"

  role_name             = "${var.cluster_name}-ebs-csi"
  attach_ebs_csi_policy = true

  oidc_providers = {
    main = {
      provider_arn               = module.eks.oidc_provider_arn
      namespace_service_accounts = ["kube-system:ebs-csi-controller-sa"]
    }
  }
}

# =============================================================================
# REDIS (ElastiCache)
# =============================================================================

resource "aws_elasticache_subnet_group" "redis" {
  name       = "${var.cluster_name}-redis"
  subnet_ids = module.vpc.private_subnets
}

resource "aws_security_group" "redis" {
  name_prefix = "redis-"
  vpc_id      = module.vpc.vpc_id

  ingress {
    from_port       = 6379
    to_port         = 6379
    protocol        = "tcp"
    security_groups = [module.eks.node_security_group_id]
  }
}

resource "aws_elasticache_replication_group" "redis" {
  replication_group_id = "${var.cluster_name}-redis"
  description          = "Redis for AI platform caching"

  node_type            = "cache.r6g.large"
  num_cache_clusters   = 3
  port                 = 6379
  parameter_group_name = "default.redis7"

  subnet_group_name  = aws_elasticache_subnet_group.redis.name
  security_group_ids = [aws_security_group.redis.id]

  at_rest_encryption_enabled = true
  transit_encryption_enabled = true
  auth_token                 = random_password.redis_password.result

  automatic_failover_enabled = true
  multi_az_enabled           = true

  snapshot_retention_limit = 7
  snapshot_window          = "03:00-05:00"
  maintenance_window       = "sun:05:00-sun:07:00"
}

resource "random_password" "redis_password" {
  length  = 32
  special = false
}

# =============================================================================
# S3 - Document Storage
# =============================================================================

resource "aws_s3_bucket" "documents" {
  bucket = "${var.cluster_name}-documents-${var.environment}"
}

resource "aws_s3_bucket_versioning" "documents" {
  bucket = aws_s3_bucket.documents.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "documents" {
  bucket = aws_s3_bucket.documents.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.ai_platform.id
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "documents" {
  bucket = aws_s3_bucket.documents.id

  rule {
    id     = "archive-old-documents"
    status = "Enabled"

    transition {
      days          = 90
      storage_class = "INTELLIGENT_TIERING"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "documents" {
  bucket                  = aws_s3_bucket.documents.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# =============================================================================
# SECRETS MANAGEMENT (AWS Secrets Manager)
# =============================================================================

resource "aws_kms_key" "ai_platform" {
  description             = "KMS key for AI platform secrets"
  deletion_window_in_days = 30
  enable_key_rotation     = true
}

resource "aws_kms_alias" "ai_platform" {
  name          = "alias/ai-platform-${var.environment}"
  target_key_id = aws_kms_key.ai_platform.key_id
}

resource "aws_secretsmanager_secret" "openai_api_key" {
  name       = "/ai-platform/${var.environment}/openai-api-key"
  kms_key_id = aws_kms_key.ai_platform.id

  tags = {
    Component = "ai-gateway"
    Rotation  = "manual"
  }
}

resource "aws_secretsmanager_secret" "anthropic_api_key" {
  name       = "/ai-platform/${var.environment}/anthropic-api-key"
  kms_key_id = aws_kms_key.ai_platform.id

  tags = {
    Component = "ai-gateway"
    Rotation  = "manual"
  }
}

resource "aws_secretsmanager_secret" "redis_password" {
  name       = "/ai-platform/${var.environment}/redis-password"
  kms_key_id = aws_kms_key.ai_platform.id
}

resource "aws_secretsmanager_secret_version" "redis_password" {
  secret_id     = aws_secretsmanager_secret.redis_password.id
  secret_string = random_password.redis_password.result
}

resource "aws_secretsmanager_secret" "qdrant_api_key" {
  name       = "/ai-platform/${var.environment}/qdrant-api-key"
  kms_key_id = aws_kms_key.ai_platform.id
}

resource "aws_secretsmanager_secret" "postgres_url" {
  name       = "/ai-platform/${var.environment}/postgres-url"
  kms_key_id = aws_kms_key.ai_platform.id
}

# =============================================================================
# RDS PostgreSQL (Metadata DB)
# =============================================================================

resource "aws_db_subnet_group" "postgres" {
  name       = "${var.cluster_name}-postgres"
  subnet_ids = module.vpc.private_subnets
}

resource "aws_security_group" "postgres" {
  name_prefix = "postgres-"
  vpc_id      = module.vpc.vpc_id

  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [module.eks.node_security_group_id]
  }
}

resource "aws_rds_cluster" "postgres" {
  cluster_identifier = "${var.cluster_name}-metadata"
  engine             = "aurora-postgresql"
  engine_version     = "15.4"
  database_name      = "ai_platform"
  master_username    = "admin"
  master_password    = random_password.postgres_password.result

  db_subnet_group_name   = aws_db_subnet_group.postgres.name
  vpc_security_group_ids = [aws_security_group.postgres.id]

  storage_encrypted = true
  kms_key_id        = aws_kms_key.ai_platform.arn

  backup_retention_period = 14
  preferred_backup_window = "02:00-04:00"

  deletion_protection = true
  skip_final_snapshot = false
  final_snapshot_identifier = "${var.cluster_name}-metadata-final"
}

resource "aws_rds_cluster_instance" "postgres" {
  count              = 2
  identifier         = "${var.cluster_name}-metadata-${count.index}"
  cluster_identifier = aws_rds_cluster.postgres.id
  instance_class     = "db.r6g.large"
  engine             = aws_rds_cluster.postgres.engine
  engine_version     = aws_rds_cluster.postgres.engine_version
}

resource "random_password" "postgres_password" {
  length  = 32
  special = false
}

# =============================================================================
# API GATEWAY (AWS)
# =============================================================================

resource "aws_apigatewayv2_api" "ai_platform" {
  name          = "${var.cluster_name}-api"
  protocol_type = "HTTP"

  cors_configuration {
    allow_origins = ["https://app.company.com"]
    allow_methods = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    allow_headers = ["Authorization", "Content-Type", "X-Request-ID"]
    max_age       = 3600
  }
}

resource "aws_apigatewayv2_stage" "prod" {
  api_id      = aws_apigatewayv2_api.ai_platform.id
  name        = "$default"
  auto_deploy = true

  default_route_settings {
    throttling_burst_limit = 1000
    throttling_rate_limit  = 500
  }

  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.api_gateway.arn
    format = jsonencode({
      requestId      = "$context.requestId"
      ip             = "$context.identity.sourceIp"
      requestTime    = "$context.requestTime"
      httpMethod     = "$context.httpMethod"
      path           = "$context.path"
      status         = "$context.status"
      responseLength = "$context.responseLength"
      latency        = "$context.responseLatency"
    })
  }
}

resource "aws_cloudwatch_log_group" "api_gateway" {
  name              = "/aws/apigateway/${var.cluster_name}"
  retention_in_days = 30
}

# =============================================================================
# MONITORING STACK
# =============================================================================

resource "aws_cloudwatch_log_group" "ai_platform" {
  name              = "/ai-platform/${var.environment}"
  retention_in_days = 90
  kms_key_id        = aws_kms_key.ai_platform.arn
}

# CloudWatch Dashboard
resource "aws_cloudwatch_dashboard" "ai_platform" {
  dashboard_name = "ai-platform-${var.environment}"
  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "metric"
        x      = 0
        y      = 0
        width  = 12
        height = 6
        properties = {
          metrics = [
            ["AI-Platform", "RequestCount", "Environment", var.environment],
            ["AI-Platform", "ErrorCount", "Environment", var.environment],
          ]
          title  = "Request & Error Count"
          region = var.aws_region
          period = 60
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 0
        width  = 12
        height = 6
        properties = {
          metrics = [
            ["AI-Platform", "Latency", "Environment", var.environment, { stat = "p50" }],
            ["AI-Platform", "Latency", "Environment", var.environment, { stat = "p95" }],
            ["AI-Platform", "Latency", "Environment", var.environment, { stat = "p99" }],
          ]
          title  = "Latency Percentiles"
          region = var.aws_region
          period = 60
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 6
        width  = 12
        height = 6
        properties = {
          metrics = [
            ["AI-Platform", "TokensUsed", "Environment", var.environment],
            ["AI-Platform", "CostUSD", "Environment", var.environment],
          ]
          title  = "Token Usage & Cost"
          region = var.aws_region
          period = 300
        }
      }
    ]
  })
}

# Cost alerting
resource "aws_budgets_budget" "ai_platform" {
  name         = "ai-platform-${var.environment}-monthly"
  budget_type  = "COST"
  limit_amount = "10000"
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  notification {
    comparison_operator       = "GREATER_THAN"
    threshold                 = 80
    threshold_type            = "PERCENTAGE"
    notification_type         = "FORECASTED"
    subscriber_email_addresses = ["ai-team@company.com"]
  }

  notification {
    comparison_operator       = "GREATER_THAN"
    threshold                 = 100
    threshold_type            = "PERCENTAGE"
    notification_type         = "ACTUAL"
    subscriber_email_addresses = ["ai-team@company.com", "engineering-leads@company.com"]
  }
}

# =============================================================================
# IAM ROLES (IRSA for EKS pods)
# =============================================================================

module "agent_orchestrator_irsa" {
  source  = "terraform-aws-modules/iam/aws//modules/iam-role-for-service-accounts-eks"
  version = "~> 5.30"

  role_name = "${var.cluster_name}-agent-orchestrator"

  oidc_providers = {
    main = {
      provider_arn               = module.eks.oidc_provider_arn
      namespace_service_accounts = ["ai-production:agent-orchestrator-sa"]
    }
  }

  role_policy_arns = {
    secrets = aws_iam_policy.read_secrets.arn
    s3      = aws_iam_policy.s3_documents_read.arn
  }
}

resource "aws_iam_policy" "read_secrets" {
  name = "${var.cluster_name}-read-secrets"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret"
        ]
        Resource = "arn:aws:secretsmanager:${var.aws_region}:*:secret:/ai-platform/${var.environment}/*"
      },
      {
        Effect = "Allow"
        Action = [
          "kms:Decrypt"
        ]
        Resource = aws_kms_key.ai_platform.arn
      }
    ]
  })
}

resource "aws_iam_policy" "s3_documents_read" {
  name = "${var.cluster_name}-s3-documents-read"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.documents.arn,
          "${aws_s3_bucket.documents.arn}/*"
        ]
      }
    ]
  })
}

# =============================================================================
# OUTPUTS
# =============================================================================

output "cluster_endpoint" {
  description = "EKS cluster endpoint"
  value       = module.eks.cluster_endpoint
}

output "cluster_name" {
  description = "EKS cluster name"
  value       = module.eks.cluster_name
}

output "vpc_id" {
  description = "VPC ID"
  value       = module.vpc.vpc_id
}

output "redis_endpoint" {
  description = "Redis primary endpoint"
  value       = aws_elasticache_replication_group.redis.primary_endpoint_address
}

output "postgres_endpoint" {
  description = "Aurora PostgreSQL endpoint"
  value       = aws_rds_cluster.postgres.endpoint
}

output "s3_documents_bucket" {
  description = "S3 bucket for documents"
  value       = aws_s3_bucket.documents.id
}

output "api_gateway_url" {
  description = "API Gateway URL"
  value       = aws_apigatewayv2_stage.prod.invoke_url
}
