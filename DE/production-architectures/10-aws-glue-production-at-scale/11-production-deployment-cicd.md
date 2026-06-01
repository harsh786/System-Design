# Production Deployment, CI/CD & Infrastructure-as-Code for AWS Glue at Enterprise Scale

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 1. The Problem: 500+ Glue Jobs Across 3 Environments with Zero-Downtime Deployments

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

### Business Context

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     ENTERPRISE GLUE PLATFORM AT SCALE                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Scale Metrics:                                                             │
│  ─────────────                                                              │
│  • 500+ Glue jobs across fraud, recommendations, reporting, ML pipelines   │
│  • 50+ data engineers and analysts contributing code                        │
│  • 3 environments: dev → staging → production                              │
│  • 20+ deployments per day across all teams                                │
│  • 99.9% SLA on critical data pipelines                                    │
│  • $200K+/month Glue compute spend requiring optimization                  │
│                                                                             │
│  Requirements:                                                              │
│  ─────────────                                                              │
│  • Automated testing at every stage (unit, integration, E2E)               │
│  • Zero-downtime deployments (no missed schedule windows)                  │
│  • Rollback within 5 minutes of failure detection                          │
│  • Full audit trail (who deployed what, when, with what approval)          │
│  • Cross-account isolation (dev/staging/prod in separate AWS accounts)     │
│  • Self-service deployment for teams with guardrails                       │
│                                                                             │
│  Pain Points Without CI/CD:                                                 │
│  ──────────────────────────                                                 │
│  • Manual Console deployments → human error, no audit trail                │
│  • "It works on my machine" → environment drift                            │
│  • Failed prod deploys during business hours → revenue impact              │
│  • No rollback capability → hours of downtime                              │
│  • Configuration drift between environments                                │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Repository Structure

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

### Monorepo Layout (Recommended for Shared Libraries)

```
glue-etl-platform/
├── jobs/
│   ├── fraud-detection/
│   │   ├── src/
│   │   │   ├── __init__.py
│   │   │   ├── main.py                 # Glue job entry point
│   │   │   ├── transformations.py      # Business logic (testable)
│   │   │   └── validators.py           # Data quality checks
│   │   ├── tests/
│   │   │   ├── test_transformations.py
│   │   │   └── test_validators.py
│   │   ├── configs/
│   │   │   ├── dev.json
│   │   │   ├── staging.json
│   │   │   └── prod.json
│   │   └── README.md
│   ├── recommendation-engine/
│   │   ├── src/
│   │   ├── tests/
│   │   └── configs/
│   ├── daily-aggregation/
│   │   ├── src/
│   │   ├── tests/
│   │   └── configs/
│   └── data-quality-checks/
│       ├── src/
│       ├── tests/
│       └── configs/
├── libs/
│   ├── glue_commons/
│   │   ├── __init__.py
│   │   ├── spark_utils.py              # Shared Spark utilities
│   │   ├── logging_config.py           # Structured logging
│   │   ├── metrics.py                  # CloudWatch metrics helper
│   │   ├── data_quality.py             # DQ framework
│   │   └── catalog_utils.py            # Glue Catalog helpers
│   └── setup.py
├── tests/
│   ├── integration/
│   │   ├── conftest.py
│   │   ├── test_fraud_pipeline_e2e.py
│   │   └── test_recommendation_e2e.py
│   └── performance/
│       └── test_dpu_benchmarks.py
├── infra/
│   ├── cdk/
│   │   ├── app.py
│   │   ├── stacks/
│   │   │   ├── glue_jobs_stack.py
│   │   │   ├── iam_stack.py
│   │   │   ├── networking_stack.py
│   │   │   └── monitoring_stack.py
│   │   └── constructs/
│   │       ├── glue_job_construct.py
│   │       └── glue_workflow_construct.py
│   ├── terraform/                      # Alternative IaC
│   │   ├── modules/
│   │   ├── environments/
│   │   └── main.tf
│   └── cloudformation/                 # Legacy support
│       └── glue-stack.yaml
├── configs/
│   ├── environments/
│   │   ├── dev.yaml
│   │   ├── staging.yaml
│   │   └── prod.yaml
│   └── job-defaults.yaml
├── scripts/
│   ├── deploy.sh
│   ├── rollback.sh
│   ├── run_integration_tests.sh
│   └── package_jobs.sh
├── .github/
│   └── workflows/
│       ├── ci.yml
│       ├── deploy-dev.yml
│       ├── deploy-staging.yml
│       ├── deploy-prod.yml
│       └── rollback.yml
├── Makefile
├── pyproject.toml
├── requirements.txt
└── README.md
```

---

## 3. Infrastructure as Code

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

### AWS CDK (Python) - Complete Stack

```python
# infra/cdk/stacks/glue_jobs_stack.py

from aws_cdk import (
    Stack, Duration, RemovalPolicy, Tags,
    aws_glue as glue,
    aws_iam as iam,
    aws_s3 as s3,
    aws_s3_deployment as s3deploy,
    aws_logs as logs,
    aws_events as events,
    aws_events_targets as targets,
    aws_ssm as ssm,
)
from constructs import Construct
from typing import Dict, Any
import json


class GlueJobsStack(Stack):
    """Production Glue jobs stack with full lifecycle management."""

    def __init__(self, scope: Construct, id: str, env_name: str,
                 config: Dict[str, Any], **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        self.env_name = env_name
        self.config = config

        # ─── S3 Buckets ───────────────────────────────────────────────
        self.scripts_bucket = s3.Bucket(
            self, "ScriptsBucket",
            bucket_name=f"glue-scripts-{env_name}-{self.account}",
            versioned=True,
            encryption=s3.BucketEncryption.S3_MANAGED,
            removal_policy=RemovalPolicy.RETAIN,
            lifecycle_rules=[
                s3.LifecycleRule(
                    noncurrent_version_expiration=Duration.days(90)
                )
            ],
        )

        self.data_bucket = s3.Bucket(
            self, "DataBucket",
            bucket_name=f"glue-data-{env_name}-{self.account}",
            versioned=True,
            encryption=s3.BucketEncryption.KMS,
            removal_policy=RemovalPolicy.RETAIN,
        )

        self.temp_bucket = s3.Bucket(
            self, "TempBucket",
            bucket_name=f"glue-temp-{env_name}-{self.account}",
            lifecycle_rules=[
                s3.LifecycleRule(expiration=Duration.days(7))
            ],
        )

        # ─── IAM Role ─────────────────────────────────────────────────
        self.glue_role = iam.Role(
            self, "GlueJobRole",
            role_name=f"glue-job-role-{env_name}",
            assumed_by=iam.ServicePrincipal("glue.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSGlueServiceRole"
                ),
            ],
        )

        # Least-privilege S3 access
        self.scripts_bucket.grant_read(self.glue_role)
        self.data_bucket.grant_read_write(self.glue_role)
        self.temp_bucket.grant_read_write(self.glue_role)

        # CloudWatch Logs
        self.glue_role.add_to_policy(iam.PolicyStatement(
            actions=[
                "logs:CreateLogGroup",
                "logs:CreateLogStream",
                "logs:PutLogEvents",
            ],
            resources=["arn:aws:logs:*:*:/aws-glue/*"],
        ))

        # ─── Deploy Scripts to S3 ────────────────────────────────────
        s3deploy.BucketDeployment(
            self, "DeployScripts",
            sources=[s3deploy.Source.asset("../../jobs")],
            destination_bucket=self.scripts_bucket,
            destination_key_prefix="scripts/",
        )

        # ─── Glue Database ────────────────────────────────────────────
        self.database = glue.CfnDatabase(
            self, "GlueDatabase",
            catalog_id=self.account,
            database_input=glue.CfnDatabase.DatabaseInputProperty(
                name=f"analytics_{env_name}",
                description=f"Analytics database for {env_name}",
            ),
        )

        # ─── Create Jobs from Config ─────────────────────────────────
        for job_name, job_config in config.get("jobs", {}).items():
            self._create_glue_job(job_name, job_config)

    def _create_glue_job(self, job_name: str, job_config: Dict[str, Any]):
        """Create a Glue job with production settings."""

        full_name = f"{job_name}-{self.env_name}"

        # Determine worker type from config
        worker_type = job_config.get("worker_type", "G.1X")
        num_workers = job_config.get("num_workers", {}).get(self.env_name, 2)
        timeout_minutes = job_config.get("timeout_minutes", 120)

        job = glue.CfnJob(
            self, f"Job-{job_name}",
            name=full_name,
            role=self.glue_role.role_arn,
            command=glue.CfnJob.JobCommandProperty(
                name="glueetl",
                python_version="3",
                script_location=(
                    f"s3://{self.scripts_bucket.bucket_name}"
                    f"/scripts/{job_config['script_path']}"
                ),
            ),
            glue_version="4.0",
            worker_type=worker_type,
            number_of_workers=num_workers,
            timeout=timeout_minutes,
            max_retries=job_config.get("max_retries", 1),
            execution_property=glue.CfnJob.ExecutionPropertyProperty(
                max_concurrent_runs=job_config.get("max_concurrent", 1),
            ),
            default_arguments={
                "--enable-metrics": "true",
                "--enable-observability-metrics": "true",
                "--enable-continuous-cloudwatch-log": "true",
                "--enable-spark-ui": "true",
                "--spark-event-logs-path": (
                    f"s3://{self.temp_bucket.bucket_name}/spark-logs/"
                ),
                "--TempDir": (
                    f"s3://{self.temp_bucket.bucket_name}/temp/"
                ),
                "--extra-py-files": (
                    f"s3://{self.scripts_bucket.bucket_name}"
                    f"/scripts/libs/glue_commons-latest.zip"
                ),
                "--env": self.env_name,
                "--job-bookmark-option": "job-bookmark-enable",
                **job_config.get("extra_args", {}),
            },
            tags={"Environment": self.env_name, "Team": job_config.get("team", "platform")},
        )

        # ─── Schedule Trigger ─────────────────────────────────────────
        if schedule := job_config.get("schedule", {}).get(self.env_name):
            glue.CfnTrigger(
                self, f"Trigger-{job_name}",
                name=f"trigger-{full_name}",
                type="SCHEDULED",
                schedule=schedule,
                start_on_creation=True,
                actions=[
                    glue.CfnTrigger.ActionProperty(
                        job_name=full_name,
                        arguments=job_config.get("trigger_args", {}),
                    )
                ],
            )

        # ─── Store Job Version in SSM ─────────────────────────────────
        ssm.StringParameter(
            self, f"SSM-{job_name}-version",
            parameter_name=f"/glue/{self.env_name}/{job_name}/version",
            string_value=job_config.get("version", "1.0.0"),
        )


# ─── CDK App Entry Point ──────────────────────────────────────────────────────
# infra/cdk/app.py

import aws_cdk as cdk
import yaml
import os

app = cdk.App()
env_name = app.node.try_get_context("env") or "dev"

# Load environment config
with open(f"../../configs/environments/{env_name}.yaml") as f:
    config = yaml.safe_load(f)

# Account mapping
accounts = {
    "dev":     cdk.Environment(account="111111111111", region="us-east-1"),
    "staging": cdk.Environment(account="222222222222", region="us-east-1"),
    "prod":    cdk.Environment(account="333333333333", region="us-east-1"),
}

GlueJobsStack(
    app, f"GlueJobs-{env_name}",
    env_name=env_name,
    config=config,
    env=accounts[env_name],
)

app.synth()
```

### Terraform Alternative

```hcl
# infra/terraform/modules/glue_job/main.tf

variable "job_name"      { type = string }
variable "environment"   { type = string }
variable "script_path"   { type = string }
variable "worker_type"   { type = string; default = "G.1X" }
variable "num_workers"   { type = number; default = 2 }
variable "timeout"       { type = number; default = 120 }
variable "schedule"      { type = string; default = "" }
variable "extra_args"    { type = map(string); default = {} }
variable "tags"          { type = map(string); default = {} }

locals {
  full_name = "${var.job_name}-${var.environment}"
}

resource "aws_glue_job" "this" {
  name         = local.full_name
  role_arn     = var.role_arn
  glue_version = "4.0"
  worker_type  = var.worker_type
  number_of_workers = var.num_workers
  timeout      = var.timeout
  max_retries  = 1

  command {
    name            = "glueetl"
    python_version  = "3"
    script_location = "s3://${var.scripts_bucket}/${var.script_path}"
  }

  execution_property {
    max_concurrent_runs = 1
  }

  default_arguments = merge({
    "--enable-metrics"                       = "true"
    "--enable-observability-metrics"         = "true"
    "--enable-continuous-cloudwatch-log"     = "true"
    "--enable-spark-ui"                      = "true"
    "--spark-event-logs-path"               = "s3://${var.temp_bucket}/spark-logs/"
    "--TempDir"                             = "s3://${var.temp_bucket}/temp/"
    "--env"                                 = var.environment
    "--job-bookmark-option"                 = "job-bookmark-enable"
  }, var.extra_args)

  tags = merge(var.tags, {
    Environment = var.environment
    ManagedBy   = "terraform"
  })
}

resource "aws_glue_trigger" "schedule" {
  count    = var.schedule != "" ? 1 : 0
  name     = "trigger-${local.full_name}"
  type     = "SCHEDULED"
  schedule = var.schedule
  enabled  = true

  actions {
    job_name = aws_glue_job.this.name
  }
}

output "job_name" { value = aws_glue_job.this.name }
output "job_arn"  { value = aws_glue_job.this.arn }
```

---

## 4. CI/CD Pipeline Architecture

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                          CI/CD PIPELINE FOR GLUE JOBS                                │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                     │
│  ┌──────────┐    ┌──────────┐    ┌───────────────┐    ┌───────────────────────┐   │
│  │Developer │───▶│  PR +    │───▶│  Merge to     │───▶│  CI: Build & Test     │   │
│  │  Push    │    │  Review  │    │  main branch  │    │  (lint, unit, package)│   │
│  └──────────┘    └──────────┘    └───────────────┘    └───────────┬───────────┘   │
│                                                                    │               │
│                                                                    ▼               │
│  ┌───────────────────────────────────────────────────────────────────────────┐    │
│  │                         DEV ENVIRONMENT (Auto)                             │    │
│  │  ┌─────────────┐    ┌──────────────────┐    ┌──────────────────────┐     │    │
│  │  │ Deploy CDK  │───▶│ Run Integration  │───▶│ Data Quality Gates   │     │    │
│  │  │ to dev acct │    │ Tests (LocalStack)│    │ (sample data check)  │     │    │
│  │  └─────────────┘    └──────────────────┘    └──────────┬───────────┘     │    │
│  └────────────────────────────────────────────────────────│──────────────────┘    │
│                                                            │ ✓ Pass               │
│                                                            ▼                       │
│  ┌───────────────────────────────────────────────────────────────────────────┐    │
│  │                       STAGING ENVIRONMENT (Auto)                            │    │
│  │  ┌─────────────┐    ┌──────────────────┐    ┌──────────────────────┐     │    │
│  │  │ Deploy CDK  │───▶│ E2E Tests (real  │───▶│ Performance Gate     │     │    │
│  │  │ to stg acct │    │ Glue execution)  │    │ (DPU < threshold)    │     │    │
│  │  └─────────────┘    └──────────────────┘    └──────────┬───────────┘     │    │
│  └────────────────────────────────────────────────────────│──────────────────┘    │
│                                                            │ ✓ Pass               │
│                                                            ▼                       │
│  ┌───────────────────────────────────────────────────────────────────────────┐    │
│  │                       PRODUCTION (Manual Approval)                          │    │
│  │  ┌──────────┐  ┌─────────────┐  ┌────────────┐  ┌──────────────────┐    │    │
│  │  │ Approval │─▶│ Blue-Green  │─▶│ Smoke Test │─▶│ Switch Traffic   │    │    │
│  │  │ Gate     │  │ Deploy      │  │ (validate) │  │ (activate new)   │    │    │
│  │  └──────────┘  └─────────────┘  └────────────┘  └──────────────────┘    │    │
│  │                                                                            │    │
│  │  On Failure: ┌────────────┐    ┌────────────────────────┐                 │    │
│  │              │ Auto       │───▶│ Rollback to previous   │                 │    │
│  │              │ Detect     │    │ version (< 5 min)      │                 │    │
│  │              └────────────┘    └────────────────────────┘                 │    │
│  └───────────────────────────────────────────────────────────────────────────┘    │
│                                                                                     │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 5. Testing Strategy

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

```
┌─────────────────────────────────────────────────────────────────┐
│                      TESTING PYRAMID                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│                        /\                                       │
│                       /  \        E2E Tests                     │
│                      / 5% \       (real Glue runs, staging)     │
│                     /──────\                                    │
│                    /        \     Integration Tests             │
│                   /   15%    \    (LocalStack / Glue Docker)    │
│                  /────────────\                                 │
│                 /              \   Data Quality Tests           │
│                /     20%       \  (Great Expectations, DQDL)   │
│               /────────────────\                               │
│              /                  \  Unit Tests                   │
│             /       60%          \ (pytest + moto, fast)       │
│            /──────────────────────\                            │
│                                                                 │
│  Execution Time:                                               │
│  • Unit:        < 30 seconds                                   │
│  • DQ:          < 2 minutes                                    │
│  • Integration: < 10 minutes                                   │
│  • E2E:         < 30 minutes                                   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Unit Tests (pytest + moto)

```python
# jobs/fraud-detection/tests/test_transformations.py

import pytest
from pyspark.sql import SparkSession
from pyspark.sql.types import StructType, StructField, StringType, DoubleType, TimestampType
from datetime import datetime

from jobs.fraud_detection.src.transformations import (
    flag_suspicious_transactions,
    calculate_velocity_features,
    apply_fraud_rules,
)


@pytest.fixture(scope="session")
def spark():
    """Create a local Spark session for testing."""
    return (
        SparkSession.builder
        .master("local[2]")
        .appName("fraud-detection-tests")
        .config("spark.sql.shuffle.partitions", "2")
        .config("spark.default.parallelism", "2")
        .getOrCreate()
    )


@pytest.fixture
def sample_transactions(spark):
    """Sample transaction data for testing."""
    schema = StructType([
        StructField("transaction_id", StringType(), False),
        StructField("user_id", StringType(), False),
        StructField("amount", DoubleType(), False),
        StructField("merchant", StringType(), True),
        StructField("timestamp", TimestampType(), False),
        StructField("country", StringType(), True),
    ])
    data = [
        ("txn001", "user1", 50.00, "amazon", datetime(2024, 1, 1, 10, 0), "US"),
        ("txn002", "user1", 9999.99, "unknown_shop", datetime(2024, 1, 1, 10, 5), "NG"),
        ("txn003", "user2", 25.00, "starbucks", datetime(2024, 1, 1, 11, 0), "US"),
        ("txn004", "user1", 8500.00, "wire_transfer", datetime(2024, 1, 1, 10, 2), "RU"),
    ]
    return spark.createDataFrame(data, schema)


class TestFlagSuspiciousTransactions:
    def test_flags_high_amount(self, spark, sample_transactions):
        result = flag_suspicious_transactions(sample_transactions, threshold=5000.0)
        flagged = result.filter(result.is_suspicious == True)
        assert flagged.count() == 2

    def test_no_false_positives_below_threshold(self, spark, sample_transactions):
        result = flag_suspicious_transactions(sample_transactions, threshold=5000.0)
        safe = result.filter(
            (result.is_suspicious == False) & (result.amount < 5000)
        )
        assert safe.count() == 2

    def test_handles_empty_dataframe(self, spark):
        schema = StructType([
            StructField("transaction_id", StringType(), False),
            StructField("amount", DoubleType(), False),
        ])
        empty_df = spark.createDataFrame([], schema)
        result = flag_suspicious_transactions(empty_df, threshold=5000.0)
        assert result.count() == 0


class TestVelocityFeatures:
    def test_calculates_transaction_count_per_window(self, spark, sample_transactions):
        result = calculate_velocity_features(
            sample_transactions,
            window_minutes=10,
        )
        # user1 has 3 transactions within 10 minutes
        user1_velocity = result.filter(result.user_id == "user1").first()
        assert user1_velocity.txn_count_window == 3

    def test_velocity_flag_triggers_above_threshold(self, spark, sample_transactions):
        result = calculate_velocity_features(
            sample_transactions,
            window_minutes=10,
            velocity_threshold=2,
        )
        user1 = result.filter(result.user_id == "user1").first()
        assert user1.high_velocity_flag == True
```

### Integration Tests (Glue Docker Container)

```python
# tests/integration/test_fraud_pipeline_e2e.py

import pytest
import boto3
import time
import json
from moto import mock_s3, mock_glue


@pytest.fixture
def aws_credentials():
    """Mock AWS credentials for LocalStack."""
    import os
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
    os.environ["AWS_ENDPOINT_URL"] = "http://localhost:4566"


@pytest.fixture
def s3_client(aws_credentials):
    return boto3.client("s3", endpoint_url="http://localhost:4566")


@pytest.fixture
def setup_test_data(s3_client):
    """Upload test data to LocalStack S3."""
    s3_client.create_bucket(Bucket="test-data-bucket")
    test_records = [
        {"transaction_id": "t1", "user_id": "u1", "amount": 100.0},
        {"transaction_id": "t2", "user_id": "u1", "amount": 15000.0},
    ]
    s3_client.put_object(
        Bucket="test-data-bucket",
        Key="input/transactions/dt=2024-01-01/data.json",
        Body="\n".join(json.dumps(r) for r in test_records),
    )
    return "s3://test-data-bucket/input/transactions/"


class TestFraudPipelineIntegration:
    """Integration tests running against LocalStack / Glue Docker."""

    def test_full_pipeline_produces_output(self, s3_client, setup_test_data):
        """Run the full fraud detection pipeline and validate output."""
        from jobs.fraud_detection.src.main import run_pipeline

        run_pipeline(
            input_path=setup_test_data,
            output_path="s3://test-data-bucket/output/fraud-flags/",
            env="test",
        )

        # Verify output was written
        response = s3_client.list_objects_v2(
            Bucket="test-data-bucket",
            Prefix="output/fraud-flags/",
        )
        assert response["KeyCount"] > 0

    def test_pipeline_handles_malformed_records(self, s3_client):
        """Pipeline should quarantine bad records, not fail."""
        s3_client.put_object(
            Bucket="test-data-bucket",
            Key="input/bad/data.json",
            Body="not valid json\n{broken",
        )
        from jobs.fraud_detection.src.main import run_pipeline

        # Should not raise
        result = run_pipeline(
            input_path="s3://test-data-bucket/input/bad/",
            output_path="s3://test-data-bucket/output/bad-test/",
            env="test",
        )
        assert result.quarantined_count >= 2
```

---

## 6. Deployment Patterns

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

### Blue-Green Deployment for Glue Jobs

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    BLUE-GREEN DEPLOYMENT PATTERN                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Current State (Blue = Active):                                         │
│  ┌─────────────────────┐     ┌──────────────────────────────────┐     │
│  │ fraud-detection-blue │◀────│ Trigger: cron(0 */2 * * ? *)    │     │
│  │ (v2.3.1 - ACTIVE)   │     │ Points to BLUE                   │     │
│  └─────────────────────┘     └──────────────────────────────────┘     │
│  ┌─────────────────────┐                                               │
│  │ fraud-detection-green│     (idle, previous version v2.3.0)          │
│  │ (v2.3.0 - STANDBY)  │                                               │
│  └─────────────────────┘                                               │
│                                                                         │
│  Deployment (promoting Green to v2.4.0):                               │
│  1. Deploy new code to GREEN job                                        │
│  2. Run smoke test on GREEN (manual trigger, sample data)              │
│  3. Switch trigger to point to GREEN                                    │
│  4. Monitor first scheduled run                                         │
│  5. If success: GREEN is now active, BLUE is standby                   │
│  6. If failure: revert trigger to BLUE (< 1 min rollback)             │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Canary Deployment

```python
# scripts/canary_deploy.py
"""
Canary deployment: run both old and new versions on same input,
compare outputs for consistency before switching.
"""

import boto3
import time
from deepdiff import DeepDiff

glue = boto3.client("glue")
s3 = boto3.client("s3")


def canary_deploy(job_name: str, env: str, canary_input_path: str):
    """Run canary comparison between blue and green versions."""

    blue_job = f"{job_name}-blue"
    green_job = f"{job_name}-green"
    blue_output = f"s3://glue-data-{env}/canary/{job_name}/blue/"
    green_output = f"s3://glue-data-{env}/canary/{job_name}/green/"

    # Run both versions on same canary dataset
    blue_run = glue.start_job_run(
        JobName=blue_job,
        Arguments={"--input_path": canary_input_path, "--output_path": blue_output},
    )
    green_run = glue.start_job_run(
        JobName=green_job,
        Arguments={"--input_path": canary_input_path, "--output_path": green_output},
    )

    # Wait for both to complete
    _wait_for_completion(blue_job, blue_run["JobRunId"])
    _wait_for_completion(green_job, green_run["JobRunId"])

    # Compare outputs
    blue_data = _read_output(blue_output)
    green_data = _read_output(green_output)

    diff = DeepDiff(blue_data, green_data, ignore_order=True)

    if diff:
        print(f"CANARY FAILED - Outputs differ:\n{diff}")
        return False

    print("CANARY PASSED - Outputs match. Safe to promote green.")
    return True


def _wait_for_completion(job_name: str, run_id: str, timeout: int = 1800):
    start = time.time()
    while time.time() - start < timeout:
        status = glue.get_job_run(JobName=job_name, RunId=run_id)
        state = status["JobRun"]["JobRunState"]
        if state == "SUCCEEDED":
            return
        if state in ("FAILED", "TIMEOUT", "STOPPED"):
            raise RuntimeError(f"{job_name} run {run_id} ended with state: {state}")
        time.sleep(30)
    raise TimeoutError(f"{job_name} run {run_id} timed out after {timeout}s")
```

---

## 7. Implementation

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

### GitHub Actions - Full CI/CD Workflow

```yaml
# .github/workflows/ci.yml
name: Glue ETL CI/CD Pipeline

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

env:
  PYTHON_VERSION: "3.10"
  CDK_VERSION: "2.120.0"

jobs:
  # ═══════════════════════════════════════════════════════════════════
  # Stage 1: Build & Unit Tests
  # ═══════════════════════════════════════════════════════════════════
  build-and-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}
          cache: pip

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -e libs/glue_commons
          pip install pytest pytest-cov flake8 black mypy

      - name: Lint
        run: |
          black --check jobs/ libs/
          flake8 jobs/ libs/ --max-line-length 100
          mypy jobs/ libs/ --ignore-missing-imports

      - name: Unit Tests
        run: |
          pytest jobs/ libs/ \
            --cov=jobs --cov=libs \
            --cov-report=xml \
            --cov-fail-under=80 \
            -x -v

      - name: Upload coverage
        uses: actions/upload-artifact@v4
        with:
          name: coverage-report
          path: coverage.xml

  # ═══════════════════════════════════════════════════════════════════
  # Stage 2: Integration Tests (LocalStack)
  # ═══════════════════════════════════════════════════════════════════
  integration-tests:
    needs: build-and-test
    runs-on: ubuntu-latest
    services:
      localstack:
        image: localstack/localstack:latest
        ports:
          - 4566:4566
        env:
          SERVICES: s3,glue,iam,ssm
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}
          cache: pip

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -e libs/glue_commons
          pip install pytest boto3 localstack-client

      - name: Run Integration Tests
        env:
          AWS_ENDPOINT_URL: http://localhost:4566
          AWS_ACCESS_KEY_ID: test
          AWS_SECRET_ACCESS_KEY: test
          AWS_DEFAULT_REGION: us-east-1
        run: |
          pytest tests/integration/ -v --timeout=300

  # ═══════════════════════════════════════════════════════════════════
  # Stage 3: Deploy to Dev (auto on main merge)
  # ═══════════════════════════════════════════════════════════════════
  deploy-dev:
    needs: integration-tests
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    environment: dev
    permissions:
      id-token: write
      contents: read
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}

      - uses: actions/setup-node@v4
        with:
          node-version: "20"

      - name: Install CDK
        run: npm install -g aws-cdk@${{ env.CDK_VERSION }}

      - name: Configure AWS (Dev Account)
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::111111111111:role/github-deploy-role
          aws-region: us-east-1

      - name: CDK Deploy to Dev
        working-directory: infra/cdk
        run: |
          pip install -r requirements.txt
          cdk deploy --all --context env=dev --require-approval never

      - name: Post-Deploy Smoke Test
        run: |
          python scripts/smoke_test.py --env dev --jobs fraud-detection,daily-aggregation

  # ═══════════════════════════════════════════════════════════════════
  # Stage 4: Deploy to Staging
  # ═══════════════════════════════════════════════════════════════════
  deploy-staging:
    needs: deploy-dev
    runs-on: ubuntu-latest
    environment: staging
    permissions:
      id-token: write
      contents: read
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}

      - uses: actions/setup-node@v4
        with:
          node-version: "20"

      - name: Install CDK
        run: npm install -g aws-cdk@${{ env.CDK_VERSION }}

      - name: Configure AWS (Staging Account)
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::222222222222:role/github-deploy-role
          aws-region: us-east-1

      - name: CDK Deploy to Staging
        working-directory: infra/cdk
        run: |
          pip install -r requirements.txt
          cdk deploy --all --context env=staging --require-approval never

      - name: E2E Tests in Staging
        run: |
          python scripts/run_e2e_tests.py --env staging --timeout 1800

  # ═══════════════════════════════════════════════════════════════════
  # Stage 5: Deploy to Production (manual approval)
  # ═══════════════════════════════════════════════════════════════════
  deploy-prod:
    needs: deploy-staging
    runs-on: ubuntu-latest
    environment:
      name: production
      url: https://console.aws.amazon.com/glue
    permissions:
      id-token: write
      contents: read
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}

      - uses: actions/setup-node@v4
        with:
          node-version: "20"

      - name: Install CDK
        run: npm install -g aws-cdk@${{ env.CDK_VERSION }}

      - name: Configure AWS (Prod Account)
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::333333333333:role/github-deploy-role
          aws-region: us-east-1

      - name: Record Deployment Start
        run: |
          echo "DEPLOY_START=$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> $GITHUB_ENV
          echo "DEPLOY_SHA=${{ github.sha }}" >> $GITHUB_ENV

      - name: CDK Deploy to Production
        working-directory: infra/cdk
        run: |
          pip install -r requirements.txt
          cdk deploy --all --context env=prod --require-approval never

      - name: Production Smoke Tests
        id: smoke
        run: |
          python scripts/smoke_test.py --env prod --jobs fraud-detection,daily-aggregation

      - name: Auto-Rollback on Failure
        if: failure()
        run: |
          echo "::error::Smoke tests failed. Initiating rollback..."
          python scripts/rollback.py --env prod --to-version previous
```

### Rollback Script

```python
# scripts/rollback.py
"""
Automated rollback for Glue job deployments.
Restores previous script versions from S3 versioning and reverts job definitions.
"""

import argparse
import boto3
import json
import sys
from datetime import datetime


def rollback(env: str, to_version: str = "previous"):
    """Rollback Glue jobs to a previous deployment."""

    glue = boto3.client("glue")
    s3 = boto3.client("s3")
    ssm = boto3.client("ssm")

    scripts_bucket = f"glue-scripts-{env}-{boto3.client('sts').get_caller_identity()['Account']}"

    # Get list of jobs managed by our pipeline
    paginator = glue.get_paginator("get_jobs")
    managed_jobs = []
    for page in paginator.paginate():
        for job in page["Jobs"]:
            if job.get("Tags", {}).get("Environment") == env:
                managed_jobs.append(job)

    print(f"Found {len(managed_jobs)} managed jobs in {env}")

    rollback_manifest = {
        "timestamp": datetime.utcnow().isoformat(),
        "env": env,
        "jobs_rolled_back": [],
    }

    for job in managed_jobs:
        job_name = job["Name"]
        script_location = job["Command"]["ScriptLocation"]

        # Get previous S3 version
        s3_key = script_location.replace(f"s3://{scripts_bucket}/", "")
        versions = s3.list_object_versions(
            Bucket=scripts_bucket, Prefix=s3_key, MaxKeys=2
        )

        if len(versions.get("Versions", [])) < 2:
            print(f"  SKIP {job_name}: no previous version available")
            continue

        previous_version_id = versions["Versions"][1]["VersionId"]

        # Copy previous version as current
        s3.copy_object(
            Bucket=scripts_bucket,
            Key=s3_key,
            CopySource={
                "Bucket": scripts_bucket,
                "Key": s3_key,
                "VersionId": previous_version_id,
            },
        )

        print(f"  ROLLED BACK {job_name}: restored S3 version {previous_version_id}")
        rollback_manifest["jobs_rolled_back"].append({
            "job_name": job_name,
            "restored_version_id": previous_version_id,
        })

    # Record rollback in SSM
    ssm.put_parameter(
        Name=f"/glue/{env}/last-rollback",
        Value=json.dumps(rollback_manifest),
        Type="String",
        Overwrite=True,
    )

    print(f"\nRollback complete. {len(rollback_manifest['jobs_rolled_back'])} jobs restored.")
    return rollback_manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", required=True, choices=["dev", "staging", "prod"])
    parser.add_argument("--to-version", default="previous")
    args = parser.parse_args()

    result = rollback(args.env, args.to_version)
    if not result["jobs_rolled_back"]:
        print("WARNING: No jobs were rolled back")
        sys.exit(1)
```

### Smoke Test Script

```python
# scripts/smoke_test.py
"""
Post-deployment smoke tests - validates Glue jobs are functional.
"""

import argparse
import boto3
import time
import sys


def smoke_test(env: str, jobs: list[str], timeout: int = 600):
    """Run quick validation of deployed jobs."""

    glue = boto3.client("glue")
    failures = []

    for job_name in jobs:
        full_name = f"{job_name}-{env}"
        print(f"Testing {full_name}...")

        try:
            # Verify job exists and is configured correctly
            job = glue.get_job(JobName=full_name)["Job"]
            assert job["GlueVersion"] == "4.0", "Wrong Glue version"
            assert job["Command"]["PythonVersion"] == "3", "Wrong Python version"

            # Run with --dry-run flag (job must support this)
            run = glue.start_job_run(
                JobName=full_name,
                Arguments={"--dry-run": "true", "--sample-size": "100"},
            )

            # Wait for completion
            run_id = run["JobRunId"]
            start = time.time()
            while time.time() - start < timeout:
                status = glue.get_job_run(JobName=full_name, RunId=run_id)
                state = status["JobRun"]["JobRunState"]
                if state == "SUCCEEDED":
                    duration = status["JobRun"]["ExecutionTime"]
                    print(f"  PASS ({duration}s)")
                    break
                if state in ("FAILED", "TIMEOUT", "STOPPED"):
                    error = status["JobRun"].get("ErrorMessage", "Unknown")
                    failures.append(f"{full_name}: {state} - {error}")
                    print(f"  FAIL: {error}")
                    break
                time.sleep(15)
            else:
                failures.append(f"{full_name}: Smoke test timed out ({timeout}s)")

        except Exception as e:
            failures.append(f"{full_name}: {str(e)}")
            print(f"  ERROR: {e}")

    if failures:
        print(f"\n{'='*60}")
        print(f"SMOKE TEST FAILED - {len(failures)} failures:")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)

    print(f"\nAll {len(jobs)} smoke tests passed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", required=True)
    parser.add_argument("--jobs", required=True, help="Comma-separated job names")
    parser.add_argument("--timeout", type=int, default=600)
    args = parser.parse_args()

    smoke_test(args.env, args.jobs.split(","), args.timeout)
```

---

## 8. Environment Management

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

### Cross-Account Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    CROSS-ACCOUNT DEPLOYMENT MODEL                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐        │
│  │   DEV ACCOUNT   │    │ STAGING ACCOUNT │    │  PROD ACCOUNT   │        │
│  │  111111111111   │    │  222222222222   │    │  333333333333   │        │
│  ├─────────────────┤    ├─────────────────┤    ├─────────────────┤        │
│  │ • 2 DPU/job     │    │ • 5 DPU/job     │    │ • 10-50 DPU/job │        │
│  │ • Sample data   │    │ • Full data copy│    │ • Live data      │        │
│  │ • Auto-deploy   │    │ • Auto-deploy   │    │ • Manual approve│        │
│  │ • VPC-A         │    │ • VPC-B         │    │ • VPC-C          │        │
│  │ • Relaxed IAM   │    │ • Moderate IAM  │    │ • Strict IAM     │        │
│  └─────────────────┘    └─────────────────┘    └─────────────────┘        │
│          ▲                       ▲                       ▲                  │
│          │                       │                       │                  │
│          └───────────────────────┼───────────────────────┘                  │
│                                  │                                          │
│                    ┌─────────────────────────┐                              │
│                    │   TOOLING ACCOUNT       │                              │
│                    │   (CI/CD, artifacts)    │                              │
│                    │   000000000000          │                              │
│                    │                         │                              │
│                    │   • GitHub OIDC Role    │                              │
│                    │   • Artifact S3 bucket  │                              │
│                    │   • Cross-account roles │                              │
│                    └─────────────────────────┘                              │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Environment Configuration

```yaml
# configs/environments/prod.yaml
environment: prod
account_id: "333333333333"
region: us-east-1

defaults:
  glue_version: "4.0"
  worker_type: G.2X
  timeout_minutes: 180
  max_retries: 2
  bookmark_enabled: true

jobs:
  fraud-detection:
    script_path: fraud-detection/src/main.py
    worker_type: G.2X
    num_workers:
      dev: 2
      staging: 5
      prod: 20
    timeout_minutes: 60
    max_retries: 2
    max_concurrent: 1
    team: fraud-team
    version: "2.4.1"
    schedule:
      dev: "cron(0 */4 * * ? *)"
      staging: "cron(0 */2 * * ? *)"
      prod: "cron(0 * * * ? *)"
    extra_args:
      "--fraud-threshold": "0.85"
      "--model-version": "v3"
      "--output-path": "s3://glue-data-prod-333333333333/fraud-results/"

  daily-aggregation:
    script_path: daily-aggregation/src/main.py
    worker_type: G.4X
    num_workers:
      dev: 2
      staging: 10
      prod: 50
    timeout_minutes: 180
    max_retries: 1
    team: analytics-team
    version: "1.8.0"
    schedule:
      prod: "cron(0 2 * * ? *)"
    extra_args:
      "--partitions": "2000"
      "--output-format": "iceberg"

  recommendation-engine:
    script_path: recommendation-engine/src/main.py
    worker_type: G.2X
    num_workers:
      dev: 2
      staging: 5
      prod: 15
    timeout_minutes: 90
    team: ml-team
    version: "3.1.0"
    schedule:
      prod: "cron(0 6 * * ? *)"
```

### Parameter Store Pattern

```python
# libs/glue_commons/config_loader.py
"""
Load configuration from SSM Parameter Store / Secrets Manager.
Enables runtime config changes without redeployment.
"""

import boto3
import json
from functools import lru_cache


class ConfigLoader:
    def __init__(self, env: str, job_name: str):
        self.env = env
        self.job_name = job_name
        self.ssm = boto3.client("ssm")
        self.secrets = boto3.client("secretsmanager")

    @lru_cache(maxsize=64)
    def get_parameter(self, key: str) -> str:
        """Get a parameter from SSM Parameter Store."""
        param_path = f"/glue/{self.env}/{self.job_name}/{key}"
        response = self.ssm.get_parameter(Name=param_path, WithDecryption=True)
        return response["Parameter"]["Value"]

    def get_secret(self, secret_name: str) -> dict:
        """Get credentials from Secrets Manager."""
        response = self.secrets.get_secret_value(
            SecretId=f"glue/{self.env}/{secret_name}"
        )
        return json.loads(response["SecretString"])

    def get_connection_string(self, connection_name: str) -> str:
        """Get database connection string."""
        secret = self.get_secret(connection_name)
        return (
            f"jdbc:postgresql://{secret['host']}:{secret['port']}"
            f"/{secret['database']}?user={secret['username']}"
            f"&password={secret['password']}"
        )

    def get_feature_flags(self) -> dict:
        """Get feature flags for gradual rollouts."""
        try:
            flags = self.get_parameter("feature-flags")
            return json.loads(flags)
        except self.ssm.exceptions.ParameterNotFound:
            return {}
```

---

## 9. Monitoring Deployment Health

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

### Post-Deployment Validation

```python
# scripts/post_deploy_validation.py
"""
Automated post-deployment monitoring.
Watches first N runs after deployment for anomalies.
"""

import boto3
import time
from datetime import datetime, timedelta


class DeploymentHealthMonitor:
    def __init__(self, env: str, deploy_timestamp: datetime):
        self.env = env
        self.deploy_timestamp = deploy_timestamp
        self.glue = boto3.client("glue")
        self.cloudwatch = boto3.client("cloudwatch")

    def validate_deployment(self, job_names: list[str],
                            watch_duration_hours: int = 2) -> dict:
        """Monitor jobs for anomalies after deployment."""

        results = {"healthy": [], "degraded": [], "failed": []}
        end_time = self.deploy_timestamp + timedelta(hours=watch_duration_hours)

        while datetime.utcnow() < end_time:
            for job_name in job_names:
                full_name = f"{job_name}-{self.env}"
                health = self._check_job_health(full_name)

                if health["status"] == "FAILED":
                    results["failed"].append(full_name)
                    print(f"ALERT: {full_name} FAILED post-deploy. Triggering rollback.")
                    return results
                elif health["status"] == "DEGRADED":
                    results["degraded"].append(full_name)

            time.sleep(60)

        results["healthy"] = [j for j in job_names
                              if f"{j}-{self.env}" not in results["failed"]
                              and f"{j}-{self.env}" not in results["degraded"]]
        return results

    def _check_job_health(self, job_name: str) -> dict:
        """Check if a job is healthy based on recent runs."""
        runs = self.glue.get_job_runs(JobName=job_name, MaxResults=3)["JobRuns"]

        # Filter to runs after deployment
        post_deploy_runs = [
            r for r in runs
            if r["StartedOn"] > self.deploy_timestamp
        ]

        if not post_deploy_runs:
            return {"status": "PENDING", "message": "No runs since deploy"}

        latest = post_deploy_runs[0]
        if latest["JobRunState"] == "FAILED":
            return {"status": "FAILED", "message": latest.get("ErrorMessage")}

        # Check for performance degradation
        if latest["JobRunState"] == "SUCCEEDED":
            exec_time = latest["ExecutionTime"]
            baseline = self._get_baseline_duration(job_name)
            if exec_time > baseline * 2:
                return {
                    "status": "DEGRADED",
                    "message": f"Duration {exec_time}s vs baseline {baseline}s (2x slower)",
                }

        return {"status": "HEALTHY"}

    def _get_baseline_duration(self, job_name: str) -> int:
        """Get P90 duration from last 20 successful runs."""
        response = self.cloudwatch.get_metric_statistics(
            Namespace="Glue",
            MetricName="glue.driver.aggregate.elapsedTime",
            Dimensions=[{"Name": "JobName", "Value": job_name}],
            StartTime=datetime.utcnow() - timedelta(days=7),
            EndTime=self.deploy_timestamp,
            Period=86400,
            Statistics=["Average"],
        )
        if response["Datapoints"]:
            return int(max(dp["Average"] for dp in response["Datapoints"]) / 1000)
        return 3600  # Default 1hr baseline
```

### Automated Rollback Triggers (CloudWatch Alarm)

```python
# infra/cdk/constructs/deployment_alarm.py

from aws_cdk import (
    aws_cloudwatch as cw,
    aws_cloudwatch_actions as cw_actions,
    aws_sns as sns,
    aws_lambda as _lambda,
    Duration,
)
from constructs import Construct


class DeploymentRollbackAlarm(Construct):
    """Auto-rollback alarm: triggers Lambda to rollback on consecutive failures."""

    def __init__(self, scope: Construct, id: str, job_name: str, env: str):
        super().__init__(scope, id)

        # Alarm on 2 consecutive failures
        alarm = cw.Alarm(
            self, "FailureAlarm",
            metric=cw.Metric(
                namespace="Glue",
                metric_name="glue.driver.aggregate.numFailedTasks",
                dimensions_map={"JobName": f"{job_name}-{env}"},
                period=Duration.minutes(5),
                statistic="Sum",
            ),
            threshold=1,
            evaluation_periods=2,
            datapoints_to_alarm=2,
            alarm_description=f"Auto-rollback trigger for {job_name} in {env}",
        )

        # SNS topic for notifications
        topic = sns.Topic(self, "RollbackTopic",
                         topic_name=f"glue-rollback-{env}")

        alarm.add_alarm_action(cw_actions.SnsAction(topic))
```

---

## 10. Best Practices Checklist

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

```
┌─────────────────────────────────────────────────────────────────────────────┐
│              PRODUCTION DEPLOYMENT BEST PRACTICES (35 items)                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  REPOSITORY & CODE                                                          │
│  ─────────────────                                                          │
│  [ ] 1. Monorepo with shared libs; polyrepo only for isolated teams        │
│  [ ] 2. Separate business logic from Glue boilerplate (testable)           │
│  [ ] 3. Pin all dependency versions (requirements.txt + lock file)         │
│  [ ] 4. Pre-commit hooks: black, flake8, mypy, secrets scanner            │
│  [ ] 5. Branch protection: require PR review + CI pass                     │
│  [ ] 6. Conventional commits for automated changelogs                      │
│                                                                             │
│  TESTING                                                                    │
│  ───────                                                                    │
│  [ ] 7.  80%+ unit test coverage on transformation logic                   │
│  [ ] 8.  Moto/LocalStack for AWS service mocking                          │
│  [ ] 9.  Integration tests run against Glue Docker container               │
│  [ ] 10. Data quality tests (schema validation, null checks, ranges)       │
│  [ ] 11. Performance regression tests (DPU usage, duration baselines)      │
│  [ ] 12. E2E tests on staging with production-like data volumes            │
│  [ ] 13. Chaos tests: simulate S3 failures, network partitions             │
│                                                                             │
│  INFRASTRUCTURE                                                             │
│  ──────────────                                                             │
│  [ ] 14. ALL resources defined in IaC (CDK/Terraform) - zero Console edits│
│  [ ] 15. Cross-account isolation (dev/staging/prod separate accounts)      │
│  [ ] 16. Least-privilege IAM roles per job (not shared service role)       │
│  [ ] 17. S3 bucket versioning enabled for scripts (enables rollback)       │
│  [ ] 18. KMS encryption for data at rest                                   │
│  [ ] 19. VPC endpoints for S3/Glue (no public internet)                   │
│  [ ] 20. Resource tagging: team, environment, cost-center, version         │
│                                                                             │
│  CI/CD PIPELINE                                                             │
│  ──────────────                                                             │
│  [ ] 21. Automated deploy to dev on merge to main                          │
│  [ ] 22. Automated deploy to staging after dev tests pass                  │
│  [ ] 23. Manual approval gate for production                               │
│  [ ] 24. Deploy during low-traffic windows (avoid schedule conflicts)      │
│  [ ] 25. Blue-green pattern for zero-downtime                              │
│  [ ] 26. Canary validation for critical jobs                               │
│  [ ] 27. Automated rollback on smoke test failure (< 5 min)               │
│  [ ] 28. Deployment notifications (Slack, PagerDuty)                       │
│                                                                             │
│  CONFIGURATION                                                              │
│  ─────────────                                                              │
│  [ ] 29. Environment-specific configs in YAML (not hardcoded)              │
│  [ ] 30. Secrets in Secrets Manager (never in code or env vars)            │
│  [ ] 31. Feature flags for gradual rollouts                                │
│  [ ] 32. Runtime config via SSM Parameter Store (change without deploy)    │
│                                                                             │
│  MONITORING & OBSERVABILITY                                                 │
│  ──────────────────────────                                                 │
│  [ ] 33. Post-deploy health check for first N runs                         │
│  [ ] 34. Deployment metrics dashboard (success rate, duration, rollbacks)  │
│  [ ] 35. Audit trail: who deployed what, when, with what SHA               │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Summary

```
┌─────────────────────────────────────────────────────────────────────┐
│                    KEY TAKEAWAYS                                     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  1. IaC Everything: CDK/Terraform for reproducible deployments     │
│  2. Test Pyramid: 60% unit, 20% DQ, 15% integration, 5% E2E      │
│  3. Progressive Delivery: dev → staging → prod with gates          │
│  4. Blue-Green: zero-downtime with instant rollback                │
│  5. Cross-Account: hard isolation between environments             │
│  6. Automation: 20+ deploys/day safely with < 5 min rollback      │
│  7. Observability: know deployment health within minutes            │
│                                                                     │
│  Result: From "deploy and pray" to confident, automated,           │
│  auditable deployments at enterprise scale.                         │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```
