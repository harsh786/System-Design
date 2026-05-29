# Infrastructure as Code (IaC) - Terraform, CloudFormation & CDK

## 1. IaC Fundamentals

### What is Infrastructure as Code?

Infrastructure as Code (IaC) is the practice of managing and provisioning computing infrastructure through machine-readable configuration files rather than manual processes or interactive configuration tools.

**Declarative vs Imperative:**

| Approach | Description | Tools |
|----------|-------------|-------|
| Declarative | Define WHAT the desired end state should be | Terraform, CloudFormation, CDK |
| Imperative | Define HOW to achieve the desired state (step-by-step) | Ansible playbooks, shell scripts |

```
# Declarative (Terraform) - "I want 3 instances"
resource "aws_instance" "web" {
  count         = 3
  ami           = "ami-0c55b159cbfafe1f0"
  instance_type = "t3.micro"
}

# Imperative (pseudo-code) - "Create instances one by one"
for i in 1 2 3; do
  aws ec2 run-instances --image-id ami-0c55b159cbfafe1f0 --instance-type t3.micro
done
```

**Idempotency:** Applying the same configuration multiple times produces the same result. If 3 instances exist and you apply the config again, no changes occur.

### Benefits of IaC

1. **Version Control** - Track changes via Git, audit history, rollback capability
2. **Reproducibility** - Spin up identical environments (dev/staging/prod)
3. **Consistency** - Eliminate snowflake servers and configuration drift
4. **Automation** - CI/CD pipelines for infrastructure changes
5. **Documentation** - Code IS the documentation of your infrastructure
6. **Speed** - Provision infrastructure in minutes, not days
7. **Cost** - Destroy non-production environments when not needed

### IaC Tools Comparison

| Tool | Language | Cloud | State | Approach |
|------|----------|-------|-------|----------|
| Terraform | HCL | Multi-cloud | External state file | Declarative |
| CloudFormation | YAML/JSON | AWS only | Managed by AWS | Declarative |
| CDK | TS/Python/Java/Go | AWS (primarily) | CloudFormation | Declarative (imperative syntax) |
| Pulumi | TS/Python/Go/C# | Multi-cloud | Pulumi Service/self-hosted | Declarative (imperative syntax) |
| Ansible | YAML | Multi-cloud | Stateless | Imperative/Declarative hybrid |
| Chef | Ruby DSL | Multi-cloud | Chef Server | Imperative |
| Puppet | Puppet DSL | Multi-cloud | PuppetDB | Declarative |

### Mutable vs Immutable Infrastructure

**Mutable:** Update existing servers in-place (SSH in, apt upgrade, config changes).
- Risk: Configuration drift, snowflake servers, "works on my machine"

**Immutable:** Never modify running infrastructure. Replace with new instances from fresh images.
- Pattern: Build new AMI → Deploy new instances → Destroy old instances
- Tools: Packer (build images) + Terraform (deploy infrastructure)

### Configuration Drift

Drift occurs when actual infrastructure state differs from the declared state.

**Causes:**
- Manual changes via console/CLI
- Auto-scaling events
- External tools modifying resources
- Failed partial applies

**Detection:**
- `terraform plan` (shows drift)
- `aws cloudformation detect-stack-drift`
- AWS Config rules
- Regular plan runs in CI

**Prevention:**
- Restrict console/CLI access (IAM policies)
- All changes through IaC pipeline only
- Automated drift detection with alerts
- Nightly `terraform plan` runs

---

## 2. Terraform Fundamentals

### What is Terraform?

Terraform is an open-source IaC tool by HashiCorp that enables you to define and provision infrastructure across multiple cloud providers using a declarative configuration language (HCL - HashiCorp Configuration Language).

**Key characteristics:**
- Multi-cloud: AWS, Azure, GCP, Kubernetes, Datadog, PagerDuty, etc.
- Provider ecosystem: 3000+ providers in the Terraform Registry
- Plan before apply: Preview changes before executing
- State-based: Tracks real-world resources via state file
- Open-source core with commercial offering (Terraform Cloud/Enterprise)

### Architecture

```
┌─────────────────────────────────────────────────┐
│                 Terraform CLI                     │
├─────────────────────────────────────────────────┤
│                                                   │
│  ┌──────────┐  ┌──────────┐  ┌──────────────┐  │
│  │ Providers│  │   State  │  │   Backend    │  │
│  │(AWS,GCP) │  │(.tfstate)│  │(S3,TF Cloud) │  │
│  └──────────┘  └──────────┘  └──────────────┘  │
│                                                   │
├─────────────────────────────────────────────────┤
│              Cloud Provider APIs                  │
└─────────────────────────────────────────────────┘
```

### Core Workflow

```
Write (.tf files) → terraform init → terraform plan → terraform apply
                                                            ↓
                                                    Infrastructure Created
                                                            ↓
                                              terraform destroy (cleanup)
```

### Essential Commands

```bash
# Initialize working directory, download providers
terraform init

# Preview changes without applying
terraform plan

# Apply changes (create/modify/destroy resources)
terraform apply

# Destroy all managed infrastructure
terraform destroy

# Validate configuration syntax
terraform validate

# Format code to canonical style
terraform fmt -recursive

# Import existing resource into state
terraform import aws_instance.web i-1234567890abcdef0

# Mark resource for recreation on next apply
terraform taint aws_instance.web

# Remove taint mark
terraform untaint aws_instance.web

# Show current state or plan
terraform show

# Generate dependency graph (DOT format)
terraform graph | dot -Tpng > graph.png

# Output values
terraform output
terraform output -json
```

### HCL Syntax Basics

```hcl
# Block types
terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

# Provider configuration
provider "aws" {
  region = "us-east-1"
}

# Variables
variable "instance_type" {
  type        = string
  default     = "t3.micro"
  description = "EC2 instance type"
}

# Locals (computed values)
locals {
  common_tags = {
    Environment = var.environment
    ManagedBy   = "terraform"
    Project     = var.project_name
  }
}

# Resource
resource "aws_instance" "web" {
  ami           = data.aws_ami.ubuntu.id
  instance_type = var.instance_type
  tags          = local.common_tags
}

# Data source (read existing resources)
data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"]

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]
  }
}

# Output
output "instance_ip" {
  value       = aws_instance.web.public_ip
  description = "Public IP of the web instance"
}
```

---

## 3. Terraform Configuration Deep Dive

### Providers

```hcl
# Multiple provider configurations
provider "aws" {
  region = "us-east-1"
  alias  = "east"
}

provider "aws" {
  region = "eu-west-1"
  alias  = "europe"
}

# Use specific provider
resource "aws_instance" "eu_web" {
  provider      = aws.europe
  ami           = "ami-0abc123"
  instance_type = "t3.micro"
}

# Kubernetes provider
provider "kubernetes" {
  host                   = data.aws_eks_cluster.cluster.endpoint
  cluster_ca_certificate = base64decode(data.aws_eks_cluster.cluster.certificate_authority[0].data)
  token                  = data.aws_eks_cluster_auth.cluster.token
}
```

### Resources and Meta-Arguments

```hcl
# depends_on - explicit dependency
resource "aws_instance" "web" {
  ami           = "ami-0c55b159cbfafe1f0"
  instance_type = "t3.micro"
  depends_on    = [aws_iam_role_policy.s3_access]
}

# count - create multiple identical resources
resource "aws_instance" "web" {
  count         = 3
  ami           = "ami-0c55b159cbfafe1f0"
  instance_type = "t3.micro"
  tags = {
    Name = "web-${count.index}"
  }
}

# for_each - create resources from map/set
resource "aws_instance" "web" {
  for_each      = toset(["app1", "app2", "app3"])
  ami           = "ami-0c55b159cbfafe1f0"
  instance_type = "t3.micro"
  tags = {
    Name = each.value
  }
}

# for_each with map
variable "instances" {
  default = {
    web  = { type = "t3.micro", az = "us-east-1a" }
    api  = { type = "t3.small", az = "us-east-1b" }
    db   = { type = "t3.medium", az = "us-east-1c" }
  }
}

resource "aws_instance" "servers" {
  for_each          = var.instances
  ami               = "ami-0c55b159cbfafe1f0"
  instance_type     = each.value.type
  availability_zone = each.value.az
  tags = {
    Name = each.key
  }
}

# lifecycle - control resource behavior
resource "aws_instance" "web" {
  ami           = "ami-0c55b159cbfafe1f0"
  instance_type = "t3.micro"

  lifecycle {
    create_before_destroy = true   # Create replacement before destroying
    prevent_destroy       = true   # Prevent accidental deletion
    ignore_changes        = [tags] # Don't update if tags change externally
    replace_triggered_by  = [null_resource.trigger.id]
  }
}
```

### Variables - Types and Validation

```hcl
# String
variable "environment" {
  type    = string
  default = "dev"

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be dev, staging, or prod."
  }
}

# Number
variable "instance_count" {
  type    = number
  default = 2
}

# Boolean
variable "enable_monitoring" {
  type    = bool
  default = true
}

# List
variable "availability_zones" {
  type    = list(string)
  default = ["us-east-1a", "us-east-1b", "us-east-1c"]
}

# Map
variable "instance_types" {
  type = map(string)
  default = {
    dev     = "t3.micro"
    staging = "t3.small"
    prod    = "t3.large"
  }
}

# Object (structured type)
variable "vpc_config" {
  type = object({
    cidr_block       = string
    enable_dns       = bool
    public_subnets   = list(string)
    private_subnets  = list(string)
  })

  default = {
    cidr_block     = "10.0.0.0/16"
    enable_dns     = true
    public_subnets = ["10.0.1.0/24", "10.0.2.0/24"]
    private_subnets = ["10.0.10.0/24", "10.0.11.0/24"]
  }
}

# Sensitive variable (hidden from output)
variable "db_password" {
  type      = string
  sensitive = true
}

# Nullable
variable "override_ami" {
  type    = string
  default = null
}
```

### Dynamic Blocks

```hcl
variable "ingress_rules" {
  default = [
    { port = 80, cidr = "0.0.0.0/0", description = "HTTP" },
    { port = 443, cidr = "0.0.0.0/0", description = "HTTPS" },
    { port = 22, cidr = "10.0.0.0/8", description = "SSH internal" },
  ]
}

resource "aws_security_group" "web" {
  name   = "web-sg"
  vpc_id = aws_vpc.main.id

  dynamic "ingress" {
    for_each = var.ingress_rules
    content {
      from_port   = ingress.value.port
      to_port     = ingress.value.port
      protocol    = "tcp"
      cidr_blocks = [ingress.value.cidr]
      description = ingress.value.description
    }
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}
```

### Provisioners (Last Resort)

```hcl
resource "aws_instance" "web" {
  ami           = "ami-0c55b159cbfafe1f0"
  instance_type = "t3.micro"

  # Remote execution
  provisioner "remote-exec" {
    inline = [
      "sudo apt-get update",
      "sudo apt-get install -y nginx",
    ]

    connection {
      type        = "ssh"
      user        = "ubuntu"
      private_key = file("~/.ssh/id_rsa")
      host        = self.public_ip
    }
  }

  # Local execution
  provisioner "local-exec" {
    command = "echo ${self.public_ip} >> inventory.txt"
  }

  # File copy
  provisioner "file" {
    source      = "conf/app.conf"
    destination = "/etc/app.conf"
  }
}
```

> **Note:** Prefer user_data, configuration management tools (Ansible), or pre-baked AMIs over provisioners.

---

## 4. Terraform State

### What is State?

State is Terraform's mapping between your configuration and the real-world resources. It tracks resource IDs, attributes, dependencies, and metadata.

```json
// terraform.tfstate (simplified)
{
  "version": 4,
  "terraform_version": "1.5.0",
  "resources": [
    {
      "mode": "managed",
      "type": "aws_instance",
      "name": "web",
      "instances": [
        {
          "attributes": {
            "id": "i-0abc123def456",
            "ami": "ami-0c55b159cbfafe1f0",
            "instance_type": "t3.micro",
            "public_ip": "54.123.45.67"
          }
        }
      ]
    }
  ]
}
```

### Remote Backends

```hcl
# S3 Backend with DynamoDB locking (recommended for AWS)
terraform {
  backend "s3" {
    bucket         = "my-terraform-state-bucket"
    key            = "prod/vpc/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "terraform-locks"
    kms_key_id     = "alias/terraform-state"
  }
}

# Create the backend resources (bootstrap)
resource "aws_s3_bucket" "terraform_state" {
  bucket = "my-terraform-state-bucket"

  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_s3_bucket_versioning" "terraform_state" {
  bucket = aws_s3_bucket.terraform_state.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "terraform_state" {
  bucket = aws_s3_bucket.terraform_state.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.terraform.id
    }
  }
}

resource "aws_dynamodb_table" "terraform_locks" {
  name         = "terraform-locks"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "LockID"

  attribute {
    name = "LockID"
    type = "S"
  }
}
```

### State Commands

```bash
# List all resources in state
terraform state list

# Show details of a specific resource
terraform state show aws_instance.web

# Move/rename a resource in state (no infrastructure change)
terraform state mv aws_instance.web aws_instance.app

# Remove a resource from state (doesn't destroy the resource)
terraform state rm aws_instance.web

# Pull remote state to local
terraform state pull > state_backup.json

# Push local state to remote (DANGEROUS)
terraform state push state_backup.json

# Replace provider in state
terraform state replace-provider hashicorp/aws registry.terraform.io/hashicorp/aws
```

### Workspaces

```bash
# List workspaces
terraform workspace list

# Create new workspace
terraform workspace new staging

# Switch workspace
terraform workspace select prod

# Show current workspace
terraform workspace show

# Delete workspace
terraform workspace delete staging
```

```hcl
# Use workspace name in configuration
resource "aws_instance" "web" {
  instance_type = terraform.workspace == "prod" ? "t3.large" : "t3.micro"
  tags = {
    Environment = terraform.workspace
  }
}
```

### State Security Best Practices

1. **Never commit state to Git** - add to `.gitignore`
2. **Enable encryption** at rest (S3 SSE, KMS)
3. **Enable versioning** on state bucket for recovery
4. **Restrict access** via IAM policies
5. **Enable locking** to prevent concurrent modifications
6. **Use sensitive marking** on outputs containing secrets
7. **Audit state access** via CloudTrail/access logs

---

## 5. Terraform Modules

### Module Structure

```
modules/
└── vpc/
    ├── main.tf          # Resources
    ├── variables.tf     # Input variables
    ├── outputs.tf       # Output values
    ├── versions.tf      # Required providers
    ├── locals.tf        # Local values
    └── README.md        # Documentation
```

### Creating a Module

```hcl
# modules/vpc/variables.tf
variable "vpc_cidr" {
  type        = string
  description = "CIDR block for the VPC"
}

variable "environment" {
  type        = string
  description = "Environment name"
}

variable "public_subnet_cidrs" {
  type        = list(string)
  description = "CIDR blocks for public subnets"
}

variable "private_subnet_cidrs" {
  type        = list(string)
  description = "CIDR blocks for private subnets"
}

variable "availability_zones" {
  type        = list(string)
  description = "Availability zones"
}
```

```hcl
# modules/vpc/main.tf
resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name        = "${var.environment}-vpc"
    Environment = var.environment
  }
}

resource "aws_subnet" "public" {
  count                   = length(var.public_subnet_cidrs)
  vpc_id                  = aws_vpc.main.id
  cidr_block              = var.public_subnet_cidrs[count.index]
  availability_zone       = var.availability_zones[count.index]
  map_public_ip_on_launch = true

  tags = {
    Name = "${var.environment}-public-${count.index + 1}"
  }
}

resource "aws_subnet" "private" {
  count             = length(var.private_subnet_cidrs)
  vpc_id            = aws_vpc.main.id
  cidr_block        = var.private_subnet_cidrs[count.index]
  availability_zone = var.availability_zones[count.index]

  tags = {
    Name = "${var.environment}-private-${count.index + 1}"
  }
}

resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id
  tags   = { Name = "${var.environment}-igw" }
}

resource "aws_nat_gateway" "main" {
  count         = length(var.public_subnet_cidrs)
  allocation_id = aws_eip.nat[count.index].id
  subnet_id     = aws_subnet.public[count.index].id
  tags          = { Name = "${var.environment}-nat-${count.index + 1}" }
}

resource "aws_eip" "nat" {
  count  = length(var.public_subnet_cidrs)
  domain = "vpc"
}
```

```hcl
# modules/vpc/outputs.tf
output "vpc_id" {
  value       = aws_vpc.main.id
  description = "VPC ID"
}

output "public_subnet_ids" {
  value       = aws_subnet.public[*].id
  description = "List of public subnet IDs"
}

output "private_subnet_ids" {
  value       = aws_subnet.private[*].id
  description = "List of private subnet IDs"
}
```

### Using a Module

```hcl
# Root module - main.tf
module "vpc" {
  source = "./modules/vpc"

  vpc_cidr             = "10.0.0.0/16"
  environment          = "prod"
  public_subnet_cidrs  = ["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24"]
  private_subnet_cidrs = ["10.0.10.0/24", "10.0.11.0/24", "10.0.12.0/24"]
  availability_zones   = ["us-east-1a", "us-east-1b", "us-east-1c"]
}

# Reference module outputs
resource "aws_instance" "web" {
  subnet_id = module.vpc.public_subnet_ids[0]
  # ...
}
```

### Module Sources

```hcl
# Local path
module "vpc" {
  source = "./modules/vpc"
}

# Terraform Registry
module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.0"
}

# GitHub
module "vpc" {
  source = "github.com/myorg/terraform-modules//vpc?ref=v1.2.0"
}

# S3
module "vpc" {
  source = "s3::https://my-bucket.s3.amazonaws.com/modules/vpc.zip"
}
```

### Module Testing

```hcl
# tests/vpc_test.tftest.hcl (Terraform built-in testing)
run "create_vpc" {
  command = plan

  variables {
    vpc_cidr             = "10.0.0.0/16"
    environment          = "test"
    public_subnet_cidrs  = ["10.0.1.0/24"]
    private_subnet_cidrs = ["10.0.10.0/24"]
    availability_zones   = ["us-east-1a"]
  }

  assert {
    condition     = aws_vpc.main.cidr_block == "10.0.0.0/16"
    error_message = "VPC CIDR mismatch"
  }

  assert {
    condition     = aws_vpc.main.enable_dns_hostnames == true
    error_message = "DNS hostnames should be enabled"
  }
}
```

---

## 6. Terraform Advanced

### Terragrunt

Terragrunt is a thin wrapper around Terraform that provides tools for keeping configurations DRY, managing remote state, and working with multiple modules.

```
# Directory structure with Terragrunt
live/
├── terragrunt.hcl              # Root config (backend, provider)
├── prod/
│   ├── terragrunt.hcl          # Environment config
│   ├── vpc/
│   │   └── terragrunt.hcl
│   ├── ecs/
│   │   └── terragrunt.hcl
│   └── rds/
│       └── terragrunt.hcl
└── dev/
    ├── terragrunt.hcl
    ├── vpc/
    │   └── terragrunt.hcl
    └── ecs/
        └── terragrunt.hcl
```

```hcl
# live/terragrunt.hcl (root)
remote_state {
  backend = "s3"
  generate = {
    path      = "backend.tf"
    if_exists = "overwrite_terragrunt"
  }
  config = {
    bucket         = "my-terraform-state"
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
  region = "us-east-1"
}
EOF
}
```

```hcl
# live/prod/vpc/terragrunt.hcl
include "root" {
  path = find_in_parent_folders()
}

terraform {
  source = "../../../modules//vpc"
}

inputs = {
  vpc_cidr    = "10.0.0.0/16"
  environment = "prod"
}

# Dependency
dependency "networking" {
  config_path = "../networking"
}
```

### Terraform Import and Moved Blocks

```hcl
# Import block (Terraform 1.5+)
import {
  to = aws_instance.web
  id = "i-0abc123def456"
}

# Moved block (refactoring without destroy/recreate)
moved {
  from = aws_instance.web
  to   = module.compute.aws_instance.web
}

moved {
  from = aws_instance.app
  to   = aws_instance.application
}
```

### terraform_remote_state

```hcl
# Read state from another Terraform project
data "terraform_remote_state" "vpc" {
  backend = "s3"
  config = {
    bucket = "my-terraform-state"
    key    = "prod/vpc/terraform.tfstate"
    region = "us-east-1"
  }
}

# Use outputs from remote state
resource "aws_instance" "web" {
  subnet_id = data.terraform_remote_state.vpc.outputs.public_subnet_ids[0]
}
```

### Null Resource and Triggers

```hcl
resource "null_resource" "deploy" {
  triggers = {
    build_hash = filemd5("${path.module}/app.zip")
  }

  provisioner "local-exec" {
    command = "aws s3 cp app.zip s3://deploy-bucket/"
  }

  depends_on = [aws_s3_bucket.deploy]
}
```

---

## 7. Terraform Best Practices

### Directory Structure for Large Projects

```
terraform/
├── modules/                    # Reusable modules
│   ├── vpc/
│   ├── ecs-cluster/
│   ├── rds/
│   └── monitoring/
├── environments/               # Environment-specific configs
│   ├── dev/
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   ├── terraform.tfvars
│   │   └── backend.tf
│   ├── staging/
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   ├── terraform.tfvars
│   │   └── backend.tf
│   └── prod/
│       ├── main.tf
│       ├── variables.tf
│       ├── terraform.tfvars
│       └── backend.tf
└── global/                     # Shared resources (IAM, DNS)
    ├── iam/
    └── route53/
```

### .gitignore

```gitignore
# Terraform
.terraform/
*.tfstate
*.tfstate.backup
*.tfstate.*.backup
crash.log
crash.*.log
*.tfvars
!example.tfvars
override.tf
override.tf.json
*_override.tf
*_override.tf.json
.terraformrc
terraform.rc
.terraform.lock.hcl
```

### Naming Conventions

```hcl
# Resources: <provider>_<resource_type>.<descriptive_name>
resource "aws_instance" "web_server" {}
resource "aws_security_group" "web_allow_http" {}
resource "aws_iam_role" "ecs_task_execution" {}

# Variables: snake_case, descriptive
variable "vpc_cidr_block" {}
variable "enable_nat_gateway" {}
variable "database_instance_class" {}

# Outputs: <resource>_<attribute>
output "vpc_id" {}
output "alb_dns_name" {}
output "rds_endpoint" {}
```

### Tagging Strategy

```hcl
locals {
  common_tags = {
    Environment = var.environment
    Project     = var.project_name
    Team        = var.team
    ManagedBy   = "terraform"
    CostCenter  = var.cost_center
    Repository  = "github.com/myorg/infra"
  }
}

# Apply to all resources
resource "aws_instance" "web" {
  # ...
  tags = merge(local.common_tags, {
    Name = "${var.environment}-web-server"
    Role = "web"
  })
}
```

### Pre-commit Hooks

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/antonbabenko/pre-commit-terraform
    rev: v1.83.5
    hooks:
      - id: terraform_fmt
      - id: terraform_validate
      - id: terraform_tflint
      - id: terraform_tfsec
      - id: terraform_checkov
      - id: terraform_docs
```

### CI/CD Pipeline (GitHub Actions)

```yaml
# .github/workflows/terraform.yml
name: Terraform
on:
  pull_request:
    paths: ['terraform/**']
  push:
    branches: [main]
    paths: ['terraform/**']

jobs:
  plan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: hashicorp/setup-terraform@v3
        with:
          terraform_version: 1.5.0

      - name: Terraform Init
        run: terraform init
        working-directory: terraform/environments/prod

      - name: Terraform Format Check
        run: terraform fmt -check -recursive

      - name: Terraform Validate
        run: terraform validate

      - name: Terraform Plan
        run: terraform plan -out=tfplan
        working-directory: terraform/environments/prod

      - name: Post Plan to PR
        if: github.event_name == 'pull_request'
        uses: actions/github-script@v7
        with:
          script: |
            // Post plan output as PR comment

  apply:
    needs: plan
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    environment: production
    steps:
      - name: Terraform Apply
        run: terraform apply -auto-approve tfplan
```

---

## 8. Terraform with AWS (Examples)

### ECS Cluster with Fargate

```hcl
resource "aws_ecs_cluster" "main" {
  name = "${var.environment}-cluster"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }

  configuration {
    execute_command_configuration {
      logging = "OVERRIDE"
      log_configuration {
        cloud_watch_log_group_name = aws_cloudwatch_log_group.ecs.name
      }
    }
  }
}

resource "aws_ecs_task_definition" "app" {
  family                   = "${var.environment}-app"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = 256
  memory                   = 512
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([
    {
      name      = "app"
      image     = "${aws_ecr_repository.app.repository_url}:latest"
      essential = true
      portMappings = [
        {
          containerPort = 8080
          protocol      = "tcp"
        }
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.app.name
          "awslogs-region"        = var.region
          "awslogs-stream-prefix" = "app"
        }
      }
      environment = [
        { name = "ENV", value = var.environment }
      ]
      secrets = [
        { name = "DB_PASSWORD", valueFrom = aws_ssm_parameter.db_password.arn }
      ]
    }
  ])
}

resource "aws_ecs_service" "app" {
  name            = "${var.environment}-app"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.app.arn
  desired_count   = var.app_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = module.vpc.private_subnet_ids
    security_groups  = [aws_security_group.ecs_tasks.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.app.arn
    container_name   = "app"
    container_port   = 8080
  }

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }
}
```

### RDS with Secrets Manager

```hcl
resource "random_password" "db" {
  length  = 32
  special = false
}

resource "aws_secretsmanager_secret" "db" {
  name                    = "${var.environment}/rds/credentials"
  recovery_window_in_days = 7
}

resource "aws_secretsmanager_secret_version" "db" {
  secret_id = aws_secretsmanager_secret.db.id
  secret_string = jsonencode({
    username = "admin"
    password = random_password.db.result
    host     = aws_db_instance.main.endpoint
    port     = 5432
    dbname   = "appdb"
  })
}

resource "aws_db_instance" "main" {
  identifier     = "${var.environment}-postgres"
  engine         = "postgres"
  engine_version = "15.4"
  instance_class = var.db_instance_class

  allocated_storage     = 20
  max_allocated_storage = 100
  storage_encrypted     = true
  kms_key_id            = aws_kms_key.rds.arn

  db_name  = "appdb"
  username = "admin"
  password = random_password.db.result

  multi_az               = var.environment == "prod"
  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.rds.id]

  backup_retention_period = 7
  skip_final_snapshot     = var.environment != "prod"
  deletion_protection     = var.environment == "prod"

  performance_insights_enabled = true
}
```

### S3 + CloudFront

```hcl
resource "aws_s3_bucket" "website" {
  bucket = "${var.domain_name}-website"
}

resource "aws_s3_bucket_policy" "website" {
  bucket = aws_s3_bucket.website.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "CloudFrontAccess"
      Effect    = "Allow"
      Principal = { Service = "cloudfront.amazonaws.com" }
      Action    = "s3:GetObject"
      Resource  = "${aws_s3_bucket.website.arn}/*"
      Condition = {
        StringEquals = {
          "AWS:SourceArn" = aws_cloudfront_distribution.website.arn
        }
      }
    }]
  })
}

resource "aws_cloudfront_distribution" "website" {
  enabled             = true
  default_root_object = "index.html"
  aliases             = [var.domain_name]

  origin {
    domain_name              = aws_s3_bucket.website.bucket_regional_domain_name
    origin_id                = "S3Origin"
    origin_access_control_id = aws_cloudfront_origin_access_control.website.id
  }

  default_cache_behavior {
    allowed_methods        = ["GET", "HEAD"]
    cached_methods         = ["GET", "HEAD"]
    target_origin_id       = "S3Origin"
    viewer_protocol_policy = "redirect-to-https"
    compress               = true

    forwarded_values {
      query_string = false
      cookies { forward = "none" }
    }
  }

  viewer_certificate {
    acm_certificate_arn      = aws_acm_certificate.website.arn
    ssl_support_method       = "sni-only"
    minimum_protocol_version = "TLSv1.2_2021"
  }

  restrictions {
    geo_restriction { restriction_type = "none" }
  }
}
```

### Common Pattern: for_each over Maps

```hcl
variable "services" {
  default = {
    api = {
      port     = 8080
      cpu      = 512
      memory   = 1024
      replicas = 3
      health   = "/health"
    }
    worker = {
      port     = 9090
      cpu      = 256
      memory   = 512
      replicas = 2
      health   = "/ready"
    }
    gateway = {
      port     = 443
      cpu      = 1024
      memory   = 2048
      replicas = 2
      health   = "/status"
    }
  }
}

resource "aws_ecs_service" "services" {
  for_each        = var.services
  name            = each.key
  cluster         = aws_ecs_cluster.main.id
  desired_count   = each.value.replicas
  task_definition = aws_ecs_task_definition.services[each.key].arn
  launch_type     = "FARGATE"

  network_configuration {
    subnets         = module.vpc.private_subnet_ids
    security_groups = [aws_security_group.services[each.key].id]
  }
}
```

---

## 9. AWS CloudFormation

### Template Anatomy

```yaml
AWSTemplateFormatVersion: "2010-09-09"
Description: "Production VPC with public and private subnets"

Metadata:
  AWS::CloudFormation::Interface:
    ParameterGroups:
      - Label: { default: "Network Configuration" }
        Parameters:
          - VpcCidr
          - Environment

Parameters:
  Environment:
    Type: String
    AllowedValues: [dev, staging, prod]
    Default: dev
  VpcCidr:
    Type: String
    Default: "10.0.0.0/16"
    AllowedPattern: '(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})/(\d{1,2})'

Mappings:
  RegionMap:
    us-east-1:
      AMI: ami-0c55b159cbfafe1f0
    eu-west-1:
      AMI: ami-0abc123def456789

Conditions:
  IsProd: !Equals [!Ref Environment, prod]
  CreateNATGateway: !Or
    - !Equals [!Ref Environment, prod]
    - !Equals [!Ref Environment, staging]

Resources:
  VPC:
    Type: AWS::EC2::VPC
    Properties:
      CidrBlock: !Ref VpcCidr
      EnableDnsHostnames: true
      EnableDnsSupport: true
      Tags:
        - Key: Name
          Value: !Sub "${Environment}-vpc"
        - Key: Environment
          Value: !Ref Environment

  PublicSubnet1:
    Type: AWS::EC2::Subnet
    Properties:
      VpcId: !Ref VPC
      CidrBlock: !Select [0, !Cidr [!Ref VpcCidr, 6, 8]]
      AvailabilityZone: !Select [0, !GetAZs ""]
      MapPublicIpOnLaunch: true
      Tags:
        - Key: Name
          Value: !Sub "${Environment}-public-1"

  NATGateway:
    Type: AWS::EC2::NatGateway
    Condition: CreateNATGateway
    Properties:
      AllocationId: !GetAtt NATGatewayEIP.AllocationId
      SubnetId: !Ref PublicSubnet1

  NATGatewayEIP:
    Type: AWS::EC2::EIP
    Condition: CreateNATGateway
    Properties:
      Domain: vpc

  WebServerSG:
    Type: AWS::EC2::SecurityGroup
    Properties:
      GroupDescription: "Allow HTTP/HTTPS"
      VpcId: !Ref VPC
      SecurityGroupIngress:
        - IpProtocol: tcp
          FromPort: 80
          ToPort: 80
          CidrIp: 0.0.0.0/0
        - IpProtocol: tcp
          FromPort: 443
          ToPort: 443
          CidrIp: 0.0.0.0/0

  WebServer:
    Type: AWS::EC2::Instance
    Properties:
      ImageId: !FindInMap [RegionMap, !Ref "AWS::Region", AMI]
      InstanceType: !If [IsProd, t3.large, t3.micro]
      SubnetId: !Ref PublicSubnet1
      SecurityGroupIds:
        - !Ref WebServerSG
      Tags:
        - Key: Name
          Value: !Sub "${Environment}-web"

Outputs:
  VpcId:
    Description: "VPC ID"
    Value: !Ref VPC
    Export:
      Name: !Sub "${Environment}-VpcId"

  PublicSubnet1Id:
    Value: !Ref PublicSubnet1
    Export:
      Name: !Sub "${Environment}-PublicSubnet1"

  WebServerIP:
    Value: !GetAtt WebServer.PublicIp
    Condition: IsProd
```

### Intrinsic Functions Reference

```yaml
# !Ref - reference parameter or resource
VpcId: !Ref VPC

# !GetAtt - get attribute of resource
Endpoint: !GetAtt MyRDS.Endpoint.Address

# !Sub - string substitution
Name: !Sub "${Environment}-${AWS::StackName}-instance"

# !Join - join strings
Value: !Join ["-", [!Ref Environment, "app", "server"]]

# !Select - select from list
AZ: !Select [0, !GetAZs ""]

# !Split - split string into list
Parts: !Split [",", "a,b,c"]

# !If - conditional value
Type: !If [IsProd, "t3.large", "t3.micro"]

# !FindInMap - lookup from mappings
AMI: !FindInMap [RegionMap, !Ref "AWS::Region", AMI]

# !Cidr - generate CIDR blocks
Subnets: !Cidr [!Ref VpcCidr, 6, 8]

# !GetAZs - get availability zones
AZs: !GetAZs ""

# !ImportValue - cross-stack reference
VpcId: !ImportValue prod-VpcId
```

### Nested Stacks

```yaml
# Parent stack
Resources:
  VPCStack:
    Type: AWS::CloudFormation::Stack
    Properties:
      TemplateURL: https://s3.amazonaws.com/mybucket/vpc.yaml
      Parameters:
        Environment: !Ref Environment
        VpcCidr: "10.0.0.0/16"

  ECSStack:
    Type: AWS::CloudFormation::Stack
    DependsOn: VPCStack
    Properties:
      TemplateURL: https://s3.amazonaws.com/mybucket/ecs.yaml
      Parameters:
        VpcId: !GetAtt VPCStack.Outputs.VpcId
        SubnetIds: !GetAtt VPCStack.Outputs.PrivateSubnetIds
```

### StackSets (Multi-Account/Region)

```yaml
# Deploy security baseline across all accounts
Resources:
  SecurityBaseline:
    Type: AWS::CloudFormation::StackSet
    Properties:
      StackSetName: security-baseline
      PermissionModel: SERVICE_MANAGED
      AutoDeployment:
        Enabled: true
        RetainStacksOnAccountRemoval: false
      StackInstancesGroup:
        - DeploymentTargets:
            OrganizationalUnitIds:
              - ou-abc123
          Regions:
            - us-east-1
            - eu-west-1
```

### CloudFormation vs Terraform

| Feature | CloudFormation | Terraform |
|---------|---------------|-----------|
| Cloud support | AWS only | Multi-cloud |
| Language | YAML/JSON | HCL |
| State | Managed by AWS | Self-managed |
| Drift detection | Built-in | terraform plan |
| Rollback | Automatic on failure | Manual |
| Modularity | Nested stacks | Modules |
| Preview | Change Sets | terraform plan |
| Ecosystem | AWS-native integrations | 3000+ providers |
| Learning curve | Moderate | Moderate |
| Cost | Free | Free (OSS) / Paid (Cloud) |

---

## 10. AWS CDK (Cloud Development Kit)

### Overview

CDK lets you define cloud infrastructure using familiar programming languages. It synthesizes to CloudFormation templates.

```
App → Stack(s) → Construct(s) → CloudFormation Template
```

### Construct Levels

- **L1 (CfnXxx):** Direct CloudFormation resource mapping, no defaults
- **L2 (Curated):** Opinionated defaults, helper methods, best practices built-in
- **L3 (Patterns):** Multi-resource patterns (e.g., ApplicationLoadBalancedFargateService)

### CDK Example (TypeScript)

```typescript
import * as cdk from 'aws-cdk-lib';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as ecs from 'aws-cdk-lib/aws-ecs';
import * as ecs_patterns from 'aws-cdk-lib/aws-ecs-patterns';
import * as rds from 'aws-cdk-lib/aws-rds';
import { Construct } from 'constructs';

export class AppStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // VPC (L2 - sensible defaults: 2 AZs, public+private subnets, NAT)
    const vpc = new ec2.Vpc(this, 'AppVpc', {
      maxAzs: 3,
      natGateways: 1,
    });

    // ECS Cluster
    const cluster = new ecs.Cluster(this, 'Cluster', {
      vpc,
      containerInsights: true,
    });

    // Fargate Service with ALB (L3 pattern)
    const service = new ecs_patterns.ApplicationLoadBalancedFargateService(
      this, 'AppService', {
        cluster,
        cpu: 512,
        memoryLimitMiB: 1024,
        desiredCount: 3,
        taskImageOptions: {
          image: ecs.ContainerImage.fromAsset('./app'),
          containerPort: 8080,
          environment: {
            NODE_ENV: 'production',
          },
        },
        publicLoadBalancer: true,
      }
    );

    // Auto-scaling
    const scaling = service.service.autoScaleTaskCount({ maxCapacity: 10 });
    scaling.scaleOnCpuUtilization('CpuScaling', {
      targetUtilizationPercent: 70,
    });

    // RDS
    const database = new rds.DatabaseInstance(this, 'Database', {
      engine: rds.DatabaseInstanceEngine.postgres({
        version: rds.PostgresEngineVersion.VER_15_4,
      }),
      instanceType: ec2.InstanceType.of(ec2.InstanceClass.T3, ec2.InstanceSize.MEDIUM),
      vpc,
      vpcSubnets: { subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS },
      multiAz: true,
      allocatedStorage: 20,
      maxAllocatedStorage: 100,
      deletionProtection: true,
    });

    // Allow ECS to connect to RDS
    database.connections.allowDefaultPortFrom(service.service);

    // Outputs
    new cdk.CfnOutput(this, 'LoadBalancerDNS', {
      value: service.loadBalancer.loadBalancerDnsName,
    });
  }
}
```

### CDK CLI Commands

```bash
# Initialize new project
cdk init app --language typescript

# Synthesize CloudFormation template
cdk synth

# Show diff with deployed stack
cdk diff

# Deploy
cdk deploy

# Deploy all stacks
cdk deploy --all

# Destroy
cdk destroy

# List stacks
cdk ls

# Bootstrap (first-time setup per account/region)
cdk bootstrap aws://ACCOUNT-ID/REGION
```

### CDK Testing

```typescript
import { Template, Match } from 'aws-cdk-lib/assertions';
import * as cdk from 'aws-cdk-lib';
import { AppStack } from '../lib/app-stack';

describe('AppStack', () => {
  const app = new cdk.App();
  const stack = new AppStack(app, 'TestStack');
  const template = Template.fromStack(stack);

  test('Creates VPC with expected CIDR', () => {
    template.hasResourceProperties('AWS::EC2::VPC', {
      EnableDnsHostnames: true,
    });
  });

  test('Creates ECS cluster', () => {
    template.resourceCountIs('AWS::ECS::Cluster', 1);
  });

  test('RDS is multi-AZ', () => {
    template.hasResourceProperties('AWS::RDS::DBInstance', {
      MultiAZ: true,
      DeletionProtection: true,
    });
  });

  test('No public RDS', () => {
    template.hasResourceProperties('AWS::RDS::DBInstance', {
      PubliclyAccessible: Match.absent(),
    });
  });
});
```

### CDK vs Terraform vs CloudFormation Decision Matrix

| Criteria | CDK | Terraform | CloudFormation |
|----------|-----|-----------|----------------|
| Multi-cloud | No | Yes | No |
| Language | TS/Python/Java/Go | HCL | YAML/JSON |
| Abstraction level | High (L3 patterns) | Low-Medium | Low |
| Type safety | Yes | Limited | No |
| Testing | Native unit tests | Terratest | cfn-lint, TaskCat |
| State management | AWS-managed | Self-managed | AWS-managed |
| Learning curve | Low (if you know the language) | Medium | Medium-High |
| Best for | AWS-only, complex apps | Multi-cloud, platform teams | AWS-native, simple stacks |

---

## 11. Terraform Security

### tfsec

```bash
# Install
brew install tfsec

# Run scan
tfsec .
tfsec --format json --out results.json

# Example findings:
# - aws_s3_bucket missing encryption
# - aws_security_group with 0.0.0.0/0 ingress
# - aws_db_instance without storage encryption
```

### Checkov

```bash
# Install
pip install checkov

# Scan Terraform
checkov -d .
checkov -f main.tf

# Scan CloudFormation
checkov --framework cloudformation -d .

# Skip specific checks
checkov -d . --skip-check CKV_AWS_18,CKV_AWS_21

# Custom policies (Python)
# checkov/policies/custom_check.py
```

### Sentinel (Terraform Cloud/Enterprise)

```python
# Sentinel policy: Restrict instance types
import "tfplan/v2" as tfplan

allowed_types = ["t3.micro", "t3.small", "t3.medium"]

main = rule {
  all tfplan.resource_changes as _, rc {
    rc.type is "aws_instance" and
    rc.change.after.instance_type in allowed_types
  }
}
```

### OPA/Rego

```rego
# policy/terraform.rego
package terraform

deny[msg] {
  resource := input.resource_changes[_]
  resource.type == "aws_s3_bucket"
  not resource.change.after.server_side_encryption_configuration
  msg := sprintf("S3 bucket '%s' must have encryption enabled", [resource.name])
}

deny[msg] {
  resource := input.resource_changes[_]
  resource.type == "aws_security_group_rule"
  resource.change.after.cidr_blocks[_] == "0.0.0.0/0"
  resource.change.after.type == "ingress"
  msg := sprintf("Security group rule '%s' must not allow 0.0.0.0/0 ingress", [resource.name])
}
```

### Common Security Checks

```hcl
# GOOD: Encrypted S3 bucket
resource "aws_s3_bucket_server_side_encryption_configuration" "example" {
  bucket = aws_s3_bucket.example.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "aws:kms"
    }
  }
}

# GOOD: Block public access
resource "aws_s3_bucket_public_access_block" "example" {
  bucket                  = aws_s3_bucket.example.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# GOOD: Restricted security group
resource "aws_security_group_rule" "ssh" {
  type              = "ingress"
  from_port         = 22
  to_port           = 22
  protocol          = "tcp"
  cidr_blocks       = ["10.0.0.0/8"]  # Not 0.0.0.0/0
  security_group_id = aws_security_group.example.id
}

# GOOD: Encrypted RDS
resource "aws_db_instance" "example" {
  storage_encrypted = true
  kms_key_id        = aws_kms_key.rds.arn
  # ...
}
```

---

## 12. Scenario-Based Interview Questions

### Q1: Terraform state is corrupted - recovery process

**Answer:**
1. **Don't panic.** Check if S3 versioning is enabled on state bucket.
2. Retrieve previous state version from S3 versioning.
3. If no versioning, check for local `.terraform.tfstate.backup`.
4. As last resort:
   - Create empty state: `terraform state pull > /dev/null`
   - Re-import all resources: `terraform import <resource> <id>`
   - Use `terraform plan` to verify alignment.
5. **Prevention:** Always enable versioning, use DynamoDB locking, backup state regularly.

---

### Q2: Two people apply at same time - what happens?

**Answer:**
- With **state locking** (DynamoDB): Second person gets "Error acquiring the state lock" and must wait.
- Without locking: Race condition. Both read same state, both try to modify. Results in corrupted state or duplicate resources.
- **Solution:** Always enable locking. Use `terraform force-unlock <LOCK_ID>` only if a lock is orphaned (crashed process).

---

### Q3: Design Terraform structure for 50 microservices

**Answer:**
```
infra/
├── modules/
│   ├── ecs-service/          # Generic service module
│   ├── rds/
│   └── networking/
├── platform/                  # Shared infrastructure
│   ├── vpc/
│   ├── ecs-cluster/
│   └── monitoring/
├── services/                  # Per-service configs
│   ├── service-a/
│   │   ├── main.tf           # Calls ecs-service module
│   │   └── terraform.tfvars
│   ├── service-b/
│   └── ...
└── terragrunt.hcl            # DRY configuration
```

Key principles:
- One state file per service (small blast radius)
- Shared module for common patterns
- Terragrunt for DRY backend/provider configs
- CI/CD only applies changed services (path-based triggers)

---

### Q4: Migrate CloudFormation to Terraform

**Approach:**
1. Document all CloudFormation resources and their IDs.
2. Write equivalent Terraform configurations.
3. Use `terraform import` to bring existing resources into Terraform state.
4. Run `terraform plan` - should show NO changes if import was correct.
5. Delete CloudFormation stack with `DeletionPolicy: Retain` on all resources.
6. Verify Terraform manages resources correctly.

Tools: `cf-to-tf` (community tool), `former2` (generates IaC from existing AWS resources).

---

### Q5: Terraform plan shows unexpected destroy - troubleshoot

**Steps:**
1. Check what resource is being destroyed and why.
2. Common causes:
   - Resource was renamed → Terraform sees delete old + create new. Fix: use `moved` block.
   - `count` or `for_each` key changed → resources re-indexed.
   - Provider or data source returned different value.
   - State file was manually edited.
3. Use `terraform plan -target=<resource>` to isolate.
4. Check `terraform state show <resource>` vs actual config.
5. If safe, use `terraform state mv` to fix addressing.

---

### Q6: How to handle secrets in Terraform

**Options (best to worst):**
1. **External secret manager** - Reference secrets from AWS Secrets Manager/SSM Parameter Store via data sources. Terraform never stores the secret.
2. **Sensitive variables** - Mark `sensitive = true`. Still in state file but hidden from output.
3. **SOPS/encrypted tfvars** - Encrypt variable files, decrypt in CI.
4. **Environment variables** - `TF_VAR_db_password` in CI secrets.
5. **Never:** Hardcoded in `.tf` files or committed `.tfvars`.

```hcl
# Best: Generate and store in Secrets Manager
resource "random_password" "db" {
  length  = 32
  special = false
}

resource "aws_secretsmanager_secret_version" "db" {
  secret_id     = aws_secretsmanager_secret.db.id
  secret_string = random_password.db.result
}

# Application reads from Secrets Manager at runtime
```

---

### Q7: Implement blue/green deployment with Terraform

```hcl
variable "active_color" {
  default = "blue"  # Toggle between "blue" and "green"
}

resource "aws_lb_listener_rule" "app" {
  listener_arn = aws_lb_listener.main.arn
  priority     = 100

  action {
    type             = "forward"
    target_group_arn = var.active_color == "blue" ? aws_lb_target_group.blue.arn : aws_lb_target_group.green.arn
  }

  condition {
    path_pattern { values = ["/*"] }
  }
}

resource "aws_ecs_service" "blue" {
  name            = "app-blue"
  desired_count   = var.active_color == "blue" ? 3 : 0
  task_definition = aws_ecs_task_definition.blue.arn
  # ...
}

resource "aws_ecs_service" "green" {
  name            = "app-green"
  desired_count   = var.active_color == "green" ? 3 : 0
  task_definition = aws_ecs_task_definition.green.arn
  # ...
}
```

Deployment: Change `active_color` variable, apply. Rollback: Change back.

---

### Q8: Terraform drift detected - resolution strategy

1. Run `terraform plan` to see the drift.
2. Determine cause: manual change? Auto-scaling? External tool?
3. Decision:
   - **Accept Terraform's state:** `terraform apply` to revert drift.
   - **Accept real-world state:** Update `.tf` code to match, then `terraform apply` (no-op).
   - **Ignore specific attributes:** Add to `lifecycle { ignore_changes = [...] }`.
4. Prevent recurrence: restrict console access, document exceptions.

---

### Q9: Design CI/CD pipeline for Terraform

```
PR Created → Format Check → Validate → Plan → Comment Plan on PR
                                                       ↓
PR Merged → Plan → Manual Approval → Apply → Notify Slack
```

Key requirements:
- Plan output posted as PR comment for review
- Apply only on merge to main
- Manual approval gate for production
- State locking prevents parallel applies
- Separate pipelines per environment
- Drift detection on schedule (nightly plan)

---

### Q10: How to test infrastructure code

| Level | Tool | Tests |
|-------|------|-------|
| Static | `terraform validate`, `tflint` | Syntax, best practices |
| Policy | `tfsec`, `checkov`, OPA | Security, compliance |
| Unit | `terraform test` (built-in) | Module logic, plan assertions |
| Integration | Terratest (Go) | Deploy real infra, validate, destroy |
| E2E | Custom scripts | Full stack deployment verification |

```go
// Terratest example
func TestVpcModule(t *testing.T) {
    terraformOptions := terraform.WithDefaultRetryableErrors(t, &terraform.Options{
        TerraformDir: "../modules/vpc",
        Vars: map[string]interface{}{
            "vpc_cidr":    "10.0.0.0/16",
            "environment": "test",
        },
    })
    defer terraform.Destroy(t, terraformOptions)
    terraform.InitAndApply(t, terraformOptions)

    vpcId := terraform.Output(t, terraformOptions, "vpc_id")
    assert.NotEmpty(t, vpcId)
}
```

---

### Q11: Zero-downtime infrastructure changes

Strategies:
1. **`create_before_destroy`** lifecycle for replacement resources.
2. **Blue/green** for full environment swaps.
3. **Rolling updates** via ECS/ASG deployment configurations.
4. **Database changes** - add columns (not remove), use migrations.
5. **DNS-based cutover** - low TTL, switch after validation.
6. **Feature flags** - decouple deployment from release.

---

### Q12: Multi-region deployment with Terraform

```hcl
# Use provider aliases
provider "aws" {
  alias  = "primary"
  region = "us-east-1"
}

provider "aws" {
  alias  = "secondary"
  region = "eu-west-1"
}

module "primary" {
  source    = "./modules/app"
  providers = { aws = aws.primary }
  # ...
}

module "secondary" {
  source    = "./modules/app"
  providers = { aws = aws.secondary }
  # ...
}

# Global resources (Route53, CloudFront) in one region
resource "aws_route53_record" "failover_primary" {
  provider = aws.primary
  name     = "app.example.com"
  type     = "A"
  set_identifier = "primary"
  failover_routing_policy { type = "PRIMARY" }
  alias {
    name    = module.primary.alb_dns_name
    zone_id = module.primary.alb_zone_id
    evaluate_target_health = true
  }
  zone_id = data.aws_route53_zone.main.zone_id
}
```

---

### Q13: Terraform vs CDK for a new project - decision

**Choose Terraform when:**
- Multi-cloud or plan to be
- Platform/infra team managing shared infrastructure
- Need mature ecosystem and community modules
- Team has mixed programming backgrounds
- Want explicit, reviewable infrastructure code

**Choose CDK when:**
- AWS-only shop
- Application developers owning their infra
- Complex logic needed (loops, conditionals, inheritance)
- Want type safety and IDE autocomplete
- Already deep in AWS ecosystem

---

### Q14: How to refactor Terraform without downtime

1. Use `moved` blocks to rename/relocate resources.
2. Use `terraform state mv` for state-only changes.
3. Never change `for_each` keys without migration plan.
4. Test in non-prod first.
5. Process:
   - Add `moved` block → `plan` shows move not destroy → `apply`
   - Remove old code + `moved` block in next commit

---

### Q15: Import 200 existing resources into Terraform

**Approach:**
1. Use **`former2`** or **`terraformer`** to auto-generate `.tf` files from existing AWS resources.
2. Review and clean up generated code.
3. Use **import blocks** (Terraform 1.5+) for declarative import:
```hcl
import {
  to = aws_instance.web
  id = "i-abc123"
}
```
4. Run `terraform plan` with `-generate-config-out=generated.tf` to auto-generate configs for imported resources.
5. Iterate: fix plan until it shows no changes.
6. Organize into modules.

---

### Q16: State locked and team member is unavailable

```bash
# Check who holds the lock
terraform plan  # Error shows lock ID and info

# If the lock is genuinely orphaned (crashed process)
terraform force-unlock LOCK-ID

# NEVER force-unlock if someone might be running apply
```

---

### Q17: Terraform Cloud vs self-managed

| Aspect | Terraform Cloud | Self-managed (S3+CI) |
|--------|----------------|---------------------|
| State | Managed, encrypted | S3+DynamoDB |
| Runs | Remote execution | CI/CD runner |
| Policy | Sentinel/OPA built-in | Manual integration |
| Cost | Per-user pricing | Infrastructure cost |
| VCS | Native integration | CI/CD config |
| Secrets | Built-in variable sets | CI secrets |
| Best for | Teams wanting managed solution | Teams with existing CI/CD |

---

### Q18: How to handle terraform apply failure mid-way

**What happens:** Terraform applies resources in dependency order. If resource #5 of 10 fails:
- Resources 1-4 are created and in state.
- Resource 5 may be partially created (check in console).
- Resources 6-10 are not attempted.

**Resolution:**
1. Fix the root cause (permission, quota, invalid config).
2. Run `terraform apply` again. Terraform resumes from the failed point.
3. If resource is in a bad state: `terraform taint <resource>` to force recreation.
4. If stuck: `terraform state rm <resource>` and re-import or let it recreate.

---

### Q19: Implement cost controls with Terraform

```hcl
# Use Infracost for cost estimation in CI
# infracost breakdown --path .

# Enforce budget with Sentinel
import "tfplan/v2" as tfplan
import "decimal"

monthly_budget = decimal.new(5000)

main = rule {
  decimal.new(tfplan.cost_estimate.monthly) <= monthly_budget
}
```

```yaml
# GitHub Action for cost estimation
- name: Infracost
  uses: infracost/actions/setup@v3
- run: infracost breakdown --path=. --format=json --out-file=/tmp/infracost.json
- run: infracost comment github --path=/tmp/infracost.json --github-token=${{ github.token }}
```

---

### Q20: Design module for reusable EKS cluster

Key considerations:
- Configurable node groups (instance types, scaling)
- IRSA (IAM Roles for Service Accounts) support
- Add-ons (CoreDNS, kube-proxy, VPC CNI, EBS CSI)
- Encryption (envelope encryption for secrets)
- Logging (control plane logs to CloudWatch)
- Network policy (Calico or VPC CNI policy)
- Private vs public endpoint access

```hcl
module "eks" {
  source = "./modules/eks"

  cluster_name    = "${var.environment}-eks"
  cluster_version = "1.28"
  vpc_id          = module.vpc.vpc_id
  subnet_ids      = module.vpc.private_subnet_ids

  node_groups = {
    general = {
      instance_types = ["t3.large"]
      min_size       = 2
      max_size       = 10
      desired_size   = 3
    }
    compute = {
      instance_types = ["c5.2xlarge"]
      min_size       = 0
      max_size       = 20
      desired_size   = 0
      taints = [{ key = "workload", value = "compute", effect = "NO_SCHEDULE" }]
    }
  }

  enable_cluster_encryption = true
  enable_irsa               = true
  cluster_addons = {
    coredns    = { most_recent = true }
    kube-proxy = { most_recent = true }
    vpc-cni    = { most_recent = true }
  }
}
```

---

## Quick Reference: Key Terraform Commands

| Command | Purpose |
|---------|---------|
| `terraform init` | Initialize, download providers |
| `terraform plan` | Preview changes |
| `terraform apply` | Execute changes |
| `terraform destroy` | Remove all resources |
| `terraform fmt` | Format code |
| `terraform validate` | Check syntax |
| `terraform import` | Import existing resource |
| `terraform state list` | List managed resources |
| `terraform state mv` | Rename in state |
| `terraform state rm` | Remove from state |
| `terraform output` | Show outputs |
| `terraform workspace` | Manage workspaces |
| `terraform force-unlock` | Release stuck lock |
| `terraform taint` | Mark for recreation |
| `terraform graph` | Dependency visualization |

---

## Key Takeaways for Interviews

1. **State is sacred** - Protect it, lock it, encrypt it, version it.
2. **Modules for reuse** - Small, focused, well-documented, versioned.
3. **Plan before apply** - Always review. Automate review in CI.
4. **Security by default** - tfsec/checkov in pipeline, Sentinel in Cloud.
5. **Blast radius** - Small state files, targeted applies, environment isolation.
6. **Secrets never in code** - External secret managers, sensitive variables.
7. **Immutable > Mutable** - Replace, don't patch.
8. **Test at every level** - Static → Unit → Integration → E2E.
9. **DRY with Terragrunt** - For large-scale multi-environment setups.
10. **Choose the right tool** - Terraform for multi-cloud, CDK for AWS-native app teams, CloudFormation for simple AWS stacks.
