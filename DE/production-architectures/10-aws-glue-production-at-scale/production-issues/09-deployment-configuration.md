# Deployment & Configuration Issues (#91-100)

> Deployment issues are **self-inflicted wounds** — they happen when the gap between
> development and production isn't properly managed. These issues account for 25% of
> production incidents and are 100% preventable with proper CI/CD.

---

## Issue #91: Terraform/CDK State Drift After Manual Console Changes

### Severity: P2 | Frequency: Monthly

### Symptoms
```
# Terraform plan shows: 15 resources to DESTROY (unexpected!)
# Someone manually changed Glue job in Console during incident
# Terraform state doesn't know about manual change
# Next terraform apply: REVERTS the manual fix → breaks production again

# OR: CDK deploy fails: "Resource already exists" 
# (someone created it manually)
```

### Fix
```python
# Fix 1: Import manually-created resources into state
# terraform import aws_glue_job.fraud_detection fraud-detection-job
# Now Terraform manages the resource

# Fix 2: Detect drift proactively
# Run terraform plan daily as CI check:
# terraform plan -detailed-exitcode
# Exit code 2 = drift detected → alert + create ticket

# Fix 3: Prevent manual changes via SCP
{
    "Version": "2012-10-17",
    "Statement": [{
        "Effect": "Deny",
        "Action": [
            "glue:UpdateJob",
            "glue:DeleteJob",
            "glue:CreateJob"
        ],
        "Resource": "*",
        "Condition": {
            "StringNotLike": {
                "aws:PrincipalArn": [
                    "arn:aws:iam::*:role/CI-CD-Deploy-Role",
                    "arn:aws:iam::*:role/Emergency-Break-Glass-Role"
                ]
            }
        }
    }]
}
# Only CI/CD and emergency role can modify Glue jobs
# Console access: read-only

# Fix 4: Reconciliation script (runs daily)
import boto3
import json

def detect_state_drift():
    """Compare actual Glue jobs with IaC definitions."""
    glue = boto3.client('glue')
    actual_jobs = {j['Name']: j for j in glue.get_jobs()['Jobs']}
    
    defined_jobs = load_terraform_state()  # Parse .tfstate
    
    drift = {
        'in_aws_not_in_iac': set(actual_jobs.keys()) - set(defined_jobs.keys()),
        'in_iac_not_in_aws': set(defined_jobs.keys()) - set(actual_jobs.keys()),
        'modified': []  # Compare configs
    }
    
    for name in actual_jobs.keys() & defined_jobs.keys():
        if actual_jobs[name]['Command'] != defined_jobs[name]['command']:
            drift['modified'].append(name)
    
    if any(drift.values()):
        alert(f"Infrastructure drift detected: {json.dumps(drift)}")
```

---

## Issue #92: Job Parameters Not Propagating to Workers

### Severity: P2 | Frequency: Common after configuration changes

### Symptoms
```
# Updated job parameter: --output_path = "s3://new-bucket/"
# Job still writes to old bucket
# Reason: parameter read in wrong lifecycle phase, or cached from previous run

# OR: Spark conf set via --conf not taking effect
# Reason: Conf set AFTER SparkContext initialization (too late!)
```

### Fix
```python
# Fix 1: Read parameters at the RIGHT time
import sys
from awsglue.utils import getResolvedOptions

# Glue parameters are passed via sys.argv
# MUST resolve before using:
args = getResolvedOptions(sys.argv, [
    'JOB_NAME',
    'output_path',
    'input_database',
    'processing_date'
])

# Use args dict (not hardcoded values):
output_path = args['output_path']  # Correctly resolved from job parameters

# Fix 2: Spark conf must be set BEFORE SparkContext creation
# In Glue, use --conf in job parameters:
# --conf spark.sql.shuffle.partitions=2000
# This is set before Spark starts

# If setting programmatically, do it before any DataFrame operations:
from pyspark import SparkConf
conf = SparkConf()
conf.set("spark.sql.shuffle.partitions", "2000")
# Then create context with this conf

# Fix 3: Validate parameters at job start
def validate_args(args, required_params):
    """Fail fast if required parameters missing."""
    for param in required_params:
        if param not in args or not args[param]:
            raise ValueError(f"Missing required parameter: --{param}")
        logger.info(f"Parameter {param} = {args[param]}")

validate_args(args, ['output_path', 'input_database', 'processing_date'])

# Fix 4: Environment-specific parameter resolution
# Use SSM Parameter Store for environment-specific values:
import boto3

def resolve_config(env):
    """Load environment-specific configuration."""
    ssm = boto3.client('ssm')
    config = {}
    
    params = ssm.get_parameters_by_path(
        Path=f'/glue/{env}/',
        Recursive=True,
        WithDecryption=True
    )
    
    for param in params['Parameters']:
        key = param['Name'].split('/')[-1]
        config[key] = param['Value']
    
    return config
# /glue/production/output_bucket → "prod-data-lake"
# /glue/staging/output_bucket → "staging-data-lake"
```

---

## Issue #93: Library Version Conflicts (Dependency Hell)

### Severity: P2 | Frequency: On every dependency update

### Symptoms
```
# Error: ModuleNotFoundError: No module named 'pandas'
# OR: ImportError: cannot import name 'X' from 'package' (wrong version)
# OR: Job works locally but fails in Glue (different Python/Spark version)

# Glue 4.0: Python 3.10, Spark 3.3.0
# Developer's laptop: Python 3.11, Spark 3.5.0
# Library X requires: numpy >= 1.24 (Glue has numpy 1.22)
```

### Fix
```python
# Fix 1: Pin ALL dependency versions in requirements.txt
# requirements.txt:
# pandas==2.0.3
# numpy==1.24.3
# scikit-learn==1.3.0
# boto3==1.28.0  (match Glue's version!)

# Upload to S3 and reference in job:
# --additional-python-modules s3://artifacts/libs/requirements.txt

# Fix 2: Use wheel files for complex dependencies
# Build wheel locally matching Glue's Python version:
# pip wheel --python-version 3.10 --platform manylinux2014_x86_64 -w wheels/ .
# Upload wheels to S3:
# --extra-py-files s3://artifacts/wheels/mylib-1.0-py3-none-any.whl

# Fix 3: Use Glue's built-in libraries (avoid conflicts)
# Glue 4.0 includes: boto3, pandas, numpy, pyarrow, etc.
# Check available versions:
import pkg_resources
for pkg in pkg_resources.working_set:
    print(f"{pkg.key}=={pkg.version}")

# Fix 4: Docker-based local testing (match Glue environment exactly)
# docker pull amazon/aws-glue-libs:glue_libs_4.0.0_image_01
# Test in container BEFORE deploying to Glue

# Fix 5: Lock file in CI/CD
# Generate lock file:
# pip-compile --python-version 3.10 requirements.in > requirements.txt
# Commit lock file → reproducible builds
```

---

## Issue #94: Secret/Credential Exposure in Job Parameters

### Severity: P1 | Frequency: Audit finding (always exists until caught)

### Symptoms
```
# Database password visible in:
# - Glue Console → Job Parameters → --db_password = "P@ssw0rd123"
# - CloudTrail logs (StartJobRun API call includes all arguments)
# - Spark UI → Environment tab (shows all spark.conf values)
# - CloudWatch Logs (if code prints args)

# Compliance audit: FAILED (PCI-DSS, SOC2 violation)
```

### Fix
```python
# Fix 1: NEVER pass secrets as job parameters. Use Secrets Manager:
import boto3
import json

def get_secret(secret_name):
    """Retrieve secret from AWS Secrets Manager."""
    client = boto3.client('secretsmanager')
    response = client.get_secret_value(SecretId=secret_name)
    return json.loads(response['SecretString'])

# Usage:
creds = get_secret(f"glue/{args['environment']}/database-credentials")
jdbc_url = f"jdbc:mysql://{creds['host']}:{creds['port']}/{creds['database']}"

df = spark.read.format("jdbc").options(
    url=jdbc_url,
    user=creds['username'],
    password=creds['password']  # Retrieved at runtime, not in parameters
).load()

# Fix 2: Use Glue Connection (credentials stored securely)
# Create Glue Connection with JDBC credentials
# Job references connection by NAME only (no credentials in code)
dyf = glueContext.create_dynamic_frame.from_catalog(
    database="db",
    table_name="jdbc_table",
    additional_options={"useConnectionProperties": "true"}
)

# Fix 3: Use IAM authentication (no password at all!)
# For Aurora: IAM database authentication
# For Redshift: IAM-based temporary credentials
# For S3: IAM role (already used by Glue)

# Fix 4: Scan for secrets in code (CI/CD gate)
# Use git-secrets, trufflehog, or detect-secrets in pre-commit hooks
# Block any commit containing patterns: password=, secret=, key=
```

---

## Issue #95: Job Fails After Glue Version Upgrade (3.0 → 4.0)

### Severity: P2 | Frequency: On every Glue version upgrade

### Symptoms
```
# Upgraded job from Glue 3.0 to Glue 4.0
# Previously working job now fails:
# - "UnsupportedOperationException" (API removed in Spark 3.3)
# - Different default behavior (shuffle partitions, AQE settings)
# - Python 3.7 → 3.10 breaking changes
# - Library incompatibilities (newer numpy/pandas)
```

### Fix
```python
# Fix 1: Test in lower environment first (ALWAYS)
# Deploy Glue 4.0 version to dev → run full regression → promote to staging → prod
# NEVER upgrade Glue version directly in production

# Fix 2: Known breaking changes Glue 3.0 → 4.0:
"""
┌────────────────────────────────────────────────────────────────────┐
│  GLUE 3.0 → 4.0 BREAKING CHANGES                                   │
├────────────────────────────────────────────────────────────────────┤
│  Spark: 3.1 → 3.3                                                  │
│  Python: 3.7 → 3.10                                                │
│  - f-strings with = (3.8+): now supported                          │
│  - collections.abc import required (not from collections)          │
│  - Type hints syntax changes                                        │
│                                                                     │
│  Spark SQL behavior changes:                                        │
│  - ANSI mode default changes                                        │
│  - Timestamp parsing stricter                                       │
│  - CSV/JSON parsing behavior changes                                │
│  - groupBy().agg() null handling different                          │
│                                                                     │
│  Default settings changed:                                          │
│  - spark.sql.adaptive.enabled = true (was false in 3.0)            │
│  - spark.sql.ansi.enabled behavior                                  │
│  - spark.sql.legacy.timeParserPolicy = EXCEPTION (was LEGACY)      │
└────────────────────────────────────────────────────────────────────┘
"""

# Fix 3: Version compatibility layer
import sys
GLUE_VERSION = args.get('glue_version', '4.0')

if GLUE_VERSION == '4.0':
    # Spark 3.3 settings
    spark.conf.set("spark.sql.legacy.timeParserPolicy", "LEGACY")  # Keep old behavior
    spark.conf.set("spark.sql.ansi.enabled", "false")  # Disable strict ANSI
else:
    # Spark 3.1 settings (Glue 3.0)
    pass  # Defaults are fine

# Fix 4: Run both versions in parallel during migration
# Job v3: Glue 3.0 (production, writing to current output)
# Job v4: Glue 4.0 (shadow, writing to validation output)
# Compare outputs → if identical → promote v4, retire v3
```

---

## Issue #96: Hot-Deploy Breaks Running Job (Script Updated Mid-Execution)

### Severity: P1 | Frequency: Rare but catastrophic

### Symptoms
```
# CI/CD deploys new version to s3://scripts/etl_job.py
# Currently running job references same S3 path
# Spark re-reads script for task retries → gets NEW version mid-execution
# Job behaves unpredictably (old logic for some tasks, new for others)
```

### Fix
```python
# Fix 1: Versioned script paths (CRITICAL)
# Don't deploy to: s3://scripts/etl_job.py (mutable!)
# Deploy to: s3://scripts/etl_job_v2.3.1_abc123.py (immutable!)
# Update Glue job to reference new path only AFTER current run completes

# In CDK:
import hashlib

script_hash = hashlib.md5(open('etl_job.py','rb').read()).hexdigest()[:8]
script_key = f"scripts/etl_job_{script_hash}.py"

glue.CfnJob(self, "Job",
    command={"scriptLocation": f"s3://artifacts/{script_key}"}
)

# Fix 2: Wait for running jobs before deploy
import boto3

def safe_deploy(job_name, new_script_path):
    """Deploy only when no runs are active."""
    glue = boto3.client('glue')
    
    # Check for running executions
    runs = glue.get_job_runs(JobName=job_name, MaxResults=5)
    active_runs = [r for r in runs['JobRuns'] if r['JobRunState'] in ['RUNNING', 'STARTING']]
    
    if active_runs:
        logger.warning(f"Job {job_name} has {len(active_runs)} active runs. Waiting...")
        # Wait for completion OR proceed with warning
        wait_for_completion(job_name, active_runs)
    
    # Now safe to update
    glue.update_job(
        JobName=job_name,
        JobUpdate={'Command': {'ScriptLocation': new_script_path}}
    )

# Fix 3: Blue-green job deployment
# Deploy as NEW job: fraud-detection-v2
# Run v2 in shadow mode (verify output matches v1)
# Once validated: update triggers/workflows to use v2
# Keep v1 for rollback (disable, don't delete)
```

---

## Issue #97: Missing Job Dependencies (Extra JARs/Python Packages)

### Severity: P2 | Frequency: On first deploy to new environment

### Symptoms
```
# Job works in dev: ✓
# Job fails in prod: ModuleNotFoundError: No module named 'great_expectations'
# OR: ClassNotFoundException: org.apache.iceberg.spark.SparkCatalog

# Root cause: dev has manually-installed packages that prod doesn't
```

### Fix
```python
# Fix 1: Declare ALL dependencies in job configuration (IaC)
# CDK example:
glue.CfnJob(self, "FraudJob",
    command={
        "name": "glueetl",
        "scriptLocation": f"s3://scripts/{script_key}",
        "pythonVersion": "3"
    },
    default_arguments={
        "--additional-python-modules": "great_expectations==0.17.0,pandera==0.16.0",
        "--extra-jars": "s3://jars/iceberg-spark-runtime-3.3_2.12-1.3.0.jar",
        "--extra-py-files": "s3://libs/custom_transforms.zip",
        "--extra-files": "s3://config/lookup_table.csv"
    }
)

# Fix 2: Package custom code as wheel/egg
# Build: python setup.py bdist_wheel
# Upload: aws s3 cp dist/mylib-1.0.whl s3://artifacts/libs/
# Reference: --extra-py-files s3://artifacts/libs/mylib-1.0.whl

# Fix 3: Fat JAR for Java dependencies (uber jar)
# mvn package -Pshade → single JAR with all dependencies
# Upload: aws s3 cp target/uber-jar.jar s3://artifacts/jars/
# Reference: --extra-jars s3://artifacts/jars/uber-jar.jar

# Fix 4: Pre-deploy validation script
def validate_dependencies(job_name):
    """Verify all referenced artifacts exist in S3."""
    glue = boto3.client('glue')
    s3 = boto3.client('s3')
    
    job = glue.get_job(JobName=job_name)
    args = job['Job']['DefaultArguments']
    
    paths_to_check = []
    if '--extra-jars' in args:
        paths_to_check.extend(args['--extra-jars'].split(','))
    if '--extra-py-files' in args:
        paths_to_check.extend(args['--extra-py-files'].split(','))
    
    for path in paths_to_check:
        bucket, key = parse_s3_path(path)
        try:
            s3.head_object(Bucket=bucket, Key=key)
        except:
            raise Exception(f"MISSING DEPENDENCY: {path} does not exist!")
```

---

## Issue #98: CloudWatch Logs Not Appearing (Silent Job Execution)

### Severity: P2 | Frequency: Common with new jobs/VPC

### Symptoms
```
# Job runs (shows RUNNING in console)
# CloudWatch Logs: empty (no log group, or log group exists but empty)
# Can't debug because there are no logs to read!
# Job fails with generic error, no details available
```

### Fix
```python
# Fix 1: Enable continuous logging (not enabled by default!)
# Job parameter: --enable-continuous-cloudwatch-log true
# Also: --continuous-log-logGroup /aws-glue/jobs/output

# In CDK:
default_arguments={
    "--enable-continuous-cloudwatch-log": "true",
    "--enable-metrics": "true",
    "--continuous-log-logGroup": "/aws-glue/jobs/output",
    "--continuous-log-logStreamPrefix": "fraud-detection",
    "--continuous-log-conversionPattern": "%d{yyyy-MM-dd HH:mm:ss} %p %c: %m%n"
}

# Fix 2: Verify IAM permissions for CloudWatch
# Glue role needs:
{
    "Effect": "Allow",
    "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents",
        "logs:AssociateKmsKey"
    ],
    "Resource": "arn:aws:logs:*:*:log-group:/aws-glue/*"
}

# Fix 3: VPC endpoint for CloudWatch Logs
# If Glue job is in VPC without internet: needs VPC endpoint
# com.amazonaws.region.logs (Interface endpoint)
# Without it: log writes silently fail (no network path)

# Fix 4: Add explicit logging in job code
import logging
logger = logging.getLogger('glue_job')
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
logger.addHandler(handler)

logger.info("Job started successfully")
logger.info(f"Processing {record_count} records")
logger.error(f"Error processing batch: {error}")
# These appear in CloudWatch when continuous logging is enabled
```

---

## Issue #99: Glue Studio Visual Job Generates Inefficient Code

### Severity: P3 | Frequency: Common with visual ETL

### Symptoms
```
# Glue Studio generates code that:
# - Reads entire table then filters (no pushdown)
# - Creates unnecessary DynamicFrame ↔ DataFrame conversions
# - Uses resolveChoice on every column (slow for wide tables)
# - Doesn't use optimal join strategies
# - No repartition before write (small files)
# Result: 10x slower than hand-written equivalent
```

### Fix
```python
# Fix 1: Export Glue Studio code and optimize manually
# Use Glue Studio to generate initial code (fast prototyping)
# Then: Download generated script → optimize → use as custom script

# Common optimizations on Glue Studio generated code:

# Generated (inefficient):
dyf = glueContext.create_dynamic_frame.from_catalog(
    database="db", table_name="huge_table"
)
df = dyf.toDF()
df = df.filter(df["date"] >= "2024-01-01")  # Filter AFTER full read!

# Optimized (pushdown):
dyf = glueContext.create_dynamic_frame.from_catalog(
    database="db", table_name="huge_table",
    push_down_predicate="date >= '2024-01-01'"  # Filter at source!
)

# Generated (unnecessary conversion):
dyf1 = glueContext.create_dynamic_frame.from_catalog(...)
df1 = dyf1.toDF()  # DynamicFrame → DataFrame
# ... transform ...
dyf2 = DynamicFrame.fromDF(df1, glueContext)  # DataFrame → DynamicFrame
# ... transform ...
df2 = dyf2.toDF()  # DynamicFrame → DataFrame AGAIN!

# Optimized (single conversion):
dyf = glueContext.create_dynamic_frame.from_catalog(...)
df = dyf.toDF()
# All transformations in DataFrame API
# Convert back to DynamicFrame only at final write if needed

# Fix 2: Use Glue Studio only for simple ETL
# Complex pipelines: write code manually (better performance, testable)
# Simple mappings/filters: Glue Studio is fine (productivity gain > performance loss)
```

---

## Issue #100: No Rollback Strategy (Can't Undo Bad Deploy)

### Severity: P1 | Frequency: On every bad deployment (quarterly)

### Symptoms
```
# Deployed new version at 2:00 AM
# 2:15 AM: Alerts fire (output data quality degraded)
# 2:20 AM: "Quick, rollback!"
# 2:21 AM: "How do we rollback?" "I don't know."
# 2:30 AM: Manually edit code in console (introduces more bugs)
# 3:00 AM: Finally figure out how to revert → 1 hour of bad data in production
```

### Fix
```python
# STRATEGY 1: Script versioning (instant rollback)
# Every deploy creates new versioned script:
# s3://scripts/fraud-detection/v23_abc123.py (current)
# s3://scripts/fraud-detection/v22_def456.py (previous)
# s3://scripts/fraud-detection/v21_ghi789.py (2 versions ago)

# Rollback: update job to point to previous version
def rollback(job_name, versions_back=1):
    """Rollback Glue job to previous version."""
    glue = boto3.client('glue')
    ssm = boto3.client('ssm')
    
    # Get previous version path from parameter store
    previous = ssm.get_parameter(
        Name=f'/glue/versions/{job_name}/v-{versions_back}'
    )['Parameter']['Value']
    
    # Update job to use previous script
    glue.update_job(
        JobName=job_name,
        JobUpdate={
            'Command': {'ScriptLocation': previous}
        }
    )
    logger.info(f"Rolled back {job_name} to {previous}")

# STRATEGY 2: Blue-green jobs
# fraud-detection-blue (current production)
# fraud-detection-green (new version)
# Workflow triggers whichever is "active"
# Rollback: switch active pointer from green → blue (instant)

# STRATEGY 3: Feature flags in job code
import json

def get_feature_flags():
    ssm = boto3.client('ssm')
    flags = ssm.get_parameter(Name='/glue/feature-flags')
    return json.loads(flags['Parameter']['Value'])

flags = get_feature_flags()

if flags.get("use_new_aggregation_logic", False):
    result = new_aggregation(df)
else:
    result = old_aggregation(df)  # Rollback: set flag to false

# STRATEGY 4: Output versioning (rollback data, not code)
# Write to versioned output:
# s3://output/transactions/version=v23/date=2024-01-15/
# Dashboard view points to "latest good version"
# Rollback: update view to point to v22 (instant, no reprocessing)

# STRATEGY 5: Iceberg time travel (rollback table state)
spark.sql("""
    CALL system.rollback_to_snapshot('db.output_table', 1234567890)
""")
# Instantly reverts table to previous state (metadata-only operation)
# All data still exists, just pointing to old snapshot
```

---

## Deployment Best Practices Summary

```
┌─────────────────────────────────────────────────────────────────────┐
│  PRODUCTION DEPLOYMENT CHECKLIST                                     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Before Deploy:                                                      │
│  □ All tests passing (unit + integration + E2E)                     │
│  □ Code reviewed and approved                                       │
│  □ Dependencies explicitly declared and pinned                      │
│  □ No secrets in code or parameters                                 │
│  □ Rollback plan documented and tested                              │
│  □ No active runs of target job                                     │
│                                                                      │
│  During Deploy:                                                      │
│  □ Deploy to staging first, verify                                  │
│  □ Use versioned script paths (immutable)                           │
│  □ Update IaC state (no drift)                                      │
│  □ Enable continuous logging                                         │
│  □ Set appropriate timeout                                           │
│                                                                      │
│  After Deploy:                                                       │
│  □ Verify first production run succeeds                             │
│  □ Check output data quality                                         │
│  □ Verify metrics (duration, cost, record counts)                   │
│  □ Compare output with previous version                             │
│  □ Confirm CloudWatch logs flowing                                   │
│                                                                      │
│  On Failure:                                                         │
│  □ Execute rollback within 5 minutes                                │
│  □ Verify rollback succeeded                                         │
│  □ Reprocess affected time window if needed                         │
│  □ Write post-mortem                                                 │
│  □ Add regression test for the failure case                         │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```
