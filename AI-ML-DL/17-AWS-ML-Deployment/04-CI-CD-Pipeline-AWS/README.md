# CI/CD Pipeline for ML on AWS

## CI/CD Architecture

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│  GitHub  │───▶│  Build & │───▶│  Train   │───▶│ Evaluate │───▶│  Deploy  │
│  Push    │    │  Test    │    │  Model   │    │  Model   │    │  Canary  │
└──────────┘    └──────────┘    └──────────┘    └──────────┘    └──────────┘
                                                      │                │
                                                      ▼                ▼
                                                ┌──────────┐    ┌──────────┐
                                                │  Reject  │    │ Monitor  │
                                                │  + Alert │    │ → Full   │
                                                └──────────┘    └──────────┘
```

### When to Retrain

| Trigger | Method | Example |
|---------|--------|---------|
| Scheduled | EventBridge cron | Weekly retraining on new data |
| Data drift | Model Monitor alarm | Feature distribution shifted |
| Performance drop | CloudWatch alarm | Accuracy below threshold |
| New data volume | S3 event + Lambda | 10K new labeled samples arrived |
| Manual | Git tag / button | Data scientist triggers |

---

## GitHub Actions Workflow (Complete)

```yaml
# .github/workflows/ml-pipeline.yml
name: ML Pipeline

on:
  pull_request:
    branches: [main]
    paths: ['src/**', 'training/**', 'tests/**']
  push:
    branches: [main]
  release:
    types: [published]

env:
  AWS_REGION: us-east-1
  ECR_REPO: 123456.dkr.ecr.us-east-1.amazonaws.com/text-classifier
  SAGEMAKER_ROLE: arn:aws:iam::123456:role/SageMakerExecutionRole

permissions:
  id-token: write
  contents: read

jobs:
  # ─── PR: Lint + Test ───────────────────────────
  lint-and-test:
    runs-on: ubuntu-latest
    if: github.event_name == 'pull_request'
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.10'
      - run: pip install -r requirements-dev.txt
      - run: ruff check src/ training/
      - run: pytest tests/ -v --cov=src --cov-report=xml
      - run: |
          # Test inference script locally
          python -c "
          from src.inference import model_fn, input_fn, predict_fn, output_fn
          import json
          model = model_fn('tests/fixtures/model/')
          inp = input_fn(json.dumps({'text': 'test'}), 'application/json')
          pred = predict_fn(inp, model)
          out = output_fn(pred, 'application/json')
          assert 'prediction' in json.loads(out[0])
          "

  # ─── Main: Build Container ────────────────────
  build-container:
    runs-on: ubuntu-latest
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'
    outputs:
      image_uri: ${{ steps.build.outputs.image_uri }}
    steps:
      - uses: actions/checkout@v4
      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::123456:role/GitHubActionsRole
          aws-region: ${{ env.AWS_REGION }}
      - uses: aws-actions/amazon-ecr-login@v2
      - id: build
        run: |
          IMAGE_TAG="${{ github.sha }}"
          IMAGE_URI="${ECR_REPO}:${IMAGE_TAG}"
          docker build -t $IMAGE_URI .
          docker push $IMAGE_URI
          echo "image_uri=$IMAGE_URI" >> $GITHUB_OUTPUT

  # ─── Main: Train Model ────────────────────────
  train:
    runs-on: ubuntu-latest
    needs: build-container
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'
    outputs:
      model_artifact: ${{ steps.train.outputs.model_artifact }}
    steps:
      - uses: actions/checkout@v4
      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::123456:role/GitHubActionsRole
          aws-region: ${{ env.AWS_REGION }}
      - uses: actions/setup-python@v5
        with:
          python-version: '3.10'
      - run: pip install sagemaker boto3
      - id: train
        run: |
          python scripts/launch_training.py \
            --image-uri ${{ needs.build-container.outputs.image_uri }} \
            --role ${{ env.SAGEMAKER_ROLE }} \
            --instance-type ml.p3.2xlarge \
            --use-spot \
            --output-path s3://ml-artifacts/models/${{ github.sha }}/
          
          # Script outputs model artifact path
          echo "model_artifact=$(cat /tmp/model_artifact_path.txt)" >> $GITHUB_OUTPUT

  # ─── Main: Evaluate ───────────────────────────
  evaluate:
    runs-on: ubuntu-latest
    needs: train
    outputs:
      passed: ${{ steps.eval.outputs.passed }}
      accuracy: ${{ steps.eval.outputs.accuracy }}
    steps:
      - uses: actions/checkout@v4
      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::123456:role/GitHubActionsRole
          aws-region: ${{ env.AWS_REGION }}
      - uses: actions/setup-python@v5
        with:
          python-version: '3.10'
      - run: pip install sagemaker boto3
      - id: eval
        run: |
          python scripts/evaluate_model.py \
            --model-artifact ${{ needs.train.outputs.model_artifact }} \
            --test-data s3://ml-data/test/ \
            --threshold 0.85
          
          # Script writes evaluation results
          ACCURACY=$(cat /tmp/eval_accuracy.txt)
          PASSED=$(cat /tmp/eval_passed.txt)
          echo "accuracy=$ACCURACY" >> $GITHUB_OUTPUT
          echo "passed=$PASSED" >> $GITHUB_OUTPUT

  # ─── Main: Register + Deploy Canary ───────────
  deploy-canary:
    runs-on: ubuntu-latest
    needs: [train, evaluate]
    if: needs.evaluate.outputs.passed == 'true'
    steps:
      - uses: actions/checkout@v4
      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::123456:role/GitHubActionsRole
          aws-region: ${{ env.AWS_REGION }}
      - run: pip install sagemaker boto3
      - run: |
          python scripts/deploy_canary.py \
            --model-artifact ${{ needs.train.outputs.model_artifact }} \
            --endpoint-name text-clf-prod \
            --canary-weight 10 \
            --instance-type ml.g4dn.xlarge

  # ─── Alert on failure ─────────────────────────
  alert-failure:
    runs-on: ubuntu-latest
    needs: evaluate
    if: needs.evaluate.outputs.passed == 'false'
    steps:
      - run: |
          echo "Model evaluation failed. Accuracy: ${{ needs.evaluate.outputs.accuracy }}"
          # Send to Slack/PagerDuty
          curl -X POST ${{ secrets.SLACK_WEBHOOK }} \
            -H 'Content-Type: application/json' \
            -d '{"text":"ML Pipeline: Model failed evaluation. Accuracy: ${{ needs.evaluate.outputs.accuracy }}"}'

  # ─── Release: Full Deploy ─────────────────────
  deploy-full:
    runs-on: ubuntu-latest
    if: github.event_name == 'release'
    steps:
      - uses: actions/checkout@v4
      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::123456:role/GitHubActionsRole
          aws-region: ${{ env.AWS_REGION }}
      - run: pip install sagemaker boto3
      - run: |
          python scripts/deploy_full.py \
            --endpoint-name text-clf-prod \
            --model-package-group text-classifier \
            --approval-status Approved
```

### Rollback Script

```python
# scripts/rollback.py
import boto3
import sys

def rollback(endpoint_name):
    sm = boto3.client('sagemaker')
    
    # Get current endpoint config
    endpoint = sm.describe_endpoint(EndpointName=endpoint_name)
    current_config = endpoint['EndpointConfigName']
    
    # List previous configs (sorted by creation time)
    configs = sm.list_endpoint_configs(
        NameContains=endpoint_name,
        SortBy='CreationTime',
        SortOrder='Descending',
    )['EndpointConfigs']
    
    # Find the previous one
    previous_config = None
    for config in configs:
        if config['EndpointConfigName'] != current_config:
            previous_config = config['EndpointConfigName']
            break
    
    if not previous_config:
        print("No previous config found for rollback!")
        sys.exit(1)
    
    print(f"Rolling back: {current_config} → {previous_config}")
    sm.update_endpoint(
        EndpointName=endpoint_name,
        EndpointConfigName=previous_config,
    )
    print("Rollback initiated. Monitoring...")

if __name__ == '__main__':
    rollback(sys.argv[1])
```

---

## Infrastructure as Code (CDK)

### Complete CDK: SageMaker Endpoint + Autoscaling + Alarms

```python
# cdk/ml_stack.py
from aws_cdk import (
    Stack, Duration, RemovalPolicy, CfnOutput,
    aws_sagemaker as sagemaker,
    aws_applicationautoscaling as autoscaling,
    aws_cloudwatch as cloudwatch,
    aws_cloudwatch_actions as cw_actions,
    aws_sns as sns,
    aws_iam as iam,
)
from constructs import Construct

class MLInferenceStack(Stack):
    def __init__(self, scope: Construct, id: str, **kwargs):
        super().__init__(scope, id, **kwargs)
        
        # Parameters
        model_data_url = "s3://ml-artifacts/models/latest/model.tar.gz"
        instance_type = "ml.g4dn.xlarge"
        endpoint_name = "text-clf-prod"
        
        # IAM Role
        role = iam.Role(self, "SageMakerRole",
            assumed_by=iam.ServicePrincipal("sagemaker.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonSageMakerFullAccess"),
            ],
        )
        
        # Model
        model = sagemaker.CfnModel(self, "Model",
            execution_role_arn=role.role_arn,
            primary_container={
                "image": "123456.dkr.ecr.us-east-1.amazonaws.com/text-classifier:latest",
                "modelDataUrl": model_data_url,
            },
            model_name=f"{endpoint_name}-model",
        )
        
        # Endpoint Config
        endpoint_config = sagemaker.CfnEndpointConfig(self, "EndpointConfig",
            endpoint_config_name=f"{endpoint_name}-config",
            production_variants=[{
                "variantName": "AllTraffic",
                "modelName": model.model_name,
                "instanceType": instance_type,
                "initialInstanceCount": 2,
                "initialVariantWeight": 1.0,
            }],
        )
        endpoint_config.add_dependency(model)
        
        # Endpoint
        endpoint = sagemaker.CfnEndpoint(self, "Endpoint",
            endpoint_name=endpoint_name,
            endpoint_config_name=endpoint_config.endpoint_config_name,
        )
        endpoint.add_dependency(endpoint_config)
        
        # Autoscaling
        target = autoscaling.ScalableTarget(self, "ScalableTarget",
            service_namespace=autoscaling.ServiceNamespace.SAGEMAKER,
            resource_id=f"endpoint/{endpoint_name}/variant/AllTraffic",
            scalable_dimension="sagemaker:variant:DesiredInstanceCount",
            min_capacity=2,
            max_capacity=10,
        )
        
        target.scale_to_track_metric("InvocationTracking",
            target_value=750,
            predefined_metric=autoscaling.PredefinedMetric.SAGEMAKER_VARIANT_INVOCATIONS_PER_INSTANCE,
            scale_in_cooldown=Duration.seconds(300),
            scale_out_cooldown=Duration.seconds(60),
        )
        
        # SNS Topic for alerts
        alert_topic = sns.Topic(self, "MLAlerts", topic_name="ml-alerts")
        
        # Alarms
        cloudwatch.Alarm(self, "HighLatency",
            metric=cloudwatch.Metric(
                namespace="AWS/SageMaker",
                metric_name="ModelLatency",
                dimensions_map={"EndpointName": endpoint_name, "VariantName": "AllTraffic"},
                statistic="p95",
                period=Duration.minutes(5),
            ),
            threshold=500000,  # 500ms in microseconds
            evaluation_periods=3,
            alarm_description="P95 latency > 500ms for 15 minutes",
        ).add_alarm_action(cw_actions.SnsAction(alert_topic))
        
        cloudwatch.Alarm(self, "HighErrorRate",
            metric=cloudwatch.MathExpression(
                expression="errors / invocations * 100",
                using_metrics={
                    "errors": cloudwatch.Metric(
                        namespace="AWS/SageMaker",
                        metric_name="Invocation5XXErrors",
                        dimensions_map={"EndpointName": endpoint_name, "VariantName": "AllTraffic"},
                        statistic="Sum",
                        period=Duration.minutes(5),
                    ),
                    "invocations": cloudwatch.Metric(
                        namespace="AWS/SageMaker",
                        metric_name="Invocations",
                        dimensions_map={"EndpointName": endpoint_name, "VariantName": "AllTraffic"},
                        statistic="Sum",
                        period=Duration.minutes(5),
                    ),
                },
            ),
            threshold=5,  # 5% error rate
            evaluation_periods=2,
            alarm_description="Error rate > 5% for 10 minutes",
        ).add_alarm_action(cw_actions.SnsAction(alert_topic))
        
        cloudwatch.Alarm(self, "LowInvocations",
            metric=cloudwatch.Metric(
                namespace="AWS/SageMaker",
                metric_name="Invocations",
                dimensions_map={"EndpointName": endpoint_name, "VariantName": "AllTraffic"},
                statistic="Sum",
                period=Duration.minutes(15),
            ),
            threshold=1,
            evaluation_periods=2,
            comparison_operator=cloudwatch.ComparisonOperator.LESS_THAN_THRESHOLD,
            alarm_description="No invocations for 30 minutes — possible routing issue",
        ).add_alarm_action(cw_actions.SnsAction(alert_topic))
        
        CfnOutput(self, "EndpointNameOutput", value=endpoint_name)
```

---

## GitOps for ML Models

### Promotion Workflow

```
dev (experiment) → staging (integration test) → prod (traffic)

Model Registry States:
- PendingManualApproval → Created, awaiting review
- Approved             → Passed evaluation, ready for deployment
- Rejected             → Failed evaluation or found issues
```

```python
# scripts/promote_model.py
import boto3

def promote_to_prod(model_package_group, version):
    sm = boto3.client('sagemaker')
    
    # Get model package ARN
    packages = sm.list_model_packages(
        ModelPackageGroupName=model_package_group,
        ModelPackageType='Versioned',
        SortBy='CreationTime',
        SortOrder='Descending',
    )
    
    target_package = packages['ModelPackageSummaryList'][version - 1]
    arn = target_package['ModelPackageArn']
    
    # Verify it's approved
    details = sm.describe_model_package(ModelPackageName=arn)
    if details['ModelApprovalStatus'] != 'Approved':
        raise ValueError(f"Model {arn} is not approved!")
    
    # Deploy to prod
    model_name = f"prod-{model_package_group}-v{version}"
    sm.create_model(
        ModelName=model_name,
        PrimaryContainer={
            'ModelPackageName': arn,
        },
        ExecutionRoleArn='arn:aws:iam::123456:role/SageMakerRole',
    )
    
    # Update endpoint
    config_name = f"prod-config-v{version}"
    sm.create_endpoint_config(
        EndpointConfigName=config_name,
        ProductionVariants=[{
            'VariantName': 'AllTraffic',
            'ModelName': model_name,
            'InstanceType': 'ml.g4dn.xlarge',
            'InitialInstanceCount': 2,
        }],
    )
    
    sm.update_endpoint(
        EndpointName=f"{model_package_group}-prod",
        EndpointConfigName=config_name,
    )
    
    print(f"Promoted {arn} to production")
```

### Audit Trail

Every model deployment is tracked via:
1. **Model Registry** — version, metrics, who approved
2. **CloudTrail** — API calls (CreateEndpoint, UpdateEndpoint)
3. **Git** — code version that produced the model (tag in model metadata)
4. **SageMaker Experiments** — hyperparameters, datasets used
