# Modern Orchestration - Deep Dive

## Table of Contents
1. [Orchestration Evolution](#1-orchestration-evolution)
2. [Dagster Deep Dive](#2-dagster-deep-dive)
3. [Temporal Deep Dive](#3-temporal-deep-dive)
4. [AWS Step Functions Deep Dive](#4-aws-step-functions-deep-dive)
5. [Prefect Deep Dive](#5-prefect-deep-dive)
6. [Amazon MWAA](#6-amazon-mwaa)
7. [Orchestration Patterns at Scale](#7-orchestration-patterns-at-scale)
8. [Decision Framework](#8-decision-framework)
9. [Production Checklist](#9-production-checklist)

---

## 1. Orchestration Evolution

```
Timeline:
  cron (1970s) → Luigi (2012) → Airflow (2014) → Dagster/Prefect/Temporal (2019+)

Paradigm Shifts:
┌──────────────┬──────────────────┬───────────────────┬──────────────────┐
│   Cron       │   DAG-Based      │   Asset-Based     │  Workflow-Based  │
│              │  (Airflow)       │  (Dagster)        │  (Temporal)      │
├──────────────┼──────────────────┼───────────────────┼──────────────────┤
│ Schedule     │ "Run this task   │ "Keep this asset  │ "Execute this    │
│ scripts      │  after that task"│  up to date"      │  business logic  │
│              │                  │                   │  reliably"       │
├──────────────┼──────────────────┼───────────────────┼──────────────────┤
│ No deps      │ Task deps (DAG)  │ Data deps (assets)│ Code-level deps  │
│ No retry     │ Task-level retry │ Partition backfill│ Activity retry   │
│ No vis.      │ Execution-centric│ Data-centric      │ Durable execution│
└──────────────┴──────────────────┴───────────────────┴──────────────────┘
```

### Push vs Pull Execution

| Model | How It Works | Examples |
|-------|-------------|----------|
| **Push** (scheduler-driven) | Central scheduler triggers tasks on schedule | Airflow, Dagster schedules |
| **Pull** (event-driven) | Workers pull tasks from queue when ready | Temporal, Prefect agents |
| **Hybrid** | Schedule + sensor/trigger combination | Dagster sensors, Airflow sensors |

---

## 2. Dagster Deep Dive

### Core Concepts

```
┌────────────────────────────────────────────────────────────────┐
│                    Dagster Concepts Hierarchy                    │
│                                                                  │
│  Definitions (code location)                                    │
│  ├── Assets (primary abstraction)                               │
│  │   ├── Source Assets (external, not materialized by Dagster) │
│  │   ├── Software-Defined Assets (materialized by Dagster)     │
│  │   └── Asset dependencies (upstream/downstream)              │
│  ├── Resources (external services: DB connections, APIs)       │
│  ├── IO Managers (how assets are stored/loaded)                │
│  ├── Sensors (event-driven triggers)                           │
│  ├── Schedules (time-driven triggers)                          │
│  └── Jobs (executable graph of ops - legacy pattern)           │
│      ├── Ops (compute unit)                                    │
│      └── Graphs (composition of ops)                           │
└────────────────────────────────────────────────────────────────┘
```

### Software-Defined Assets (The Paradigm Shift)

```python
import dagster as dg
from dagster import asset, AssetExecutionContext, MaterializeResult, MetadataValue
from dagster_aws.s3 import S3Resource
import pandas as pd

# Source asset (external - not managed by Dagster)
source_orders = dg.SourceAsset(key="raw_orders_table", description="MySQL orders table")

# Bronze layer: raw ingestion
@asset(
    deps=[source_orders],
    group_name="bronze",
    kinds={"s3", "parquet"},
    description="Raw orders extracted from MySQL to S3",
    metadata={"owner": "data-eng", "sla_minutes": 15},
    retry_policy=dg.RetryPolicy(max_retries=3, delay=30),
    freshness_policy=dg.FreshnessPolicy(maximum_lag_minutes=30),
)
def bronze_orders(context: AssetExecutionContext, s3: S3Resource) -> MaterializeResult:
    """Extract orders from MySQL, write as Parquet to S3."""
    df = extract_from_mysql("SELECT * FROM orders WHERE updated_at > :last_run")
    
    path = f"s3://data-lake/bronze/orders/dt={context.partition_key}/data.parquet"
    df.to_parquet(path)
    
    return MaterializeResult(
        metadata={
            "row_count": MetadataValue.int(len(df)),
            "path": MetadataValue.path(path),
            "schema": MetadataValue.table_schema(
                dg.TableSchema(columns=[
                    dg.TableColumn("order_id", "int"),
                    dg.TableColumn("amount", "decimal"),
                    dg.TableColumn("status", "string"),
                ])
            ),
        }
    )

# Silver layer: cleaned and validated
@asset(
    deps=[bronze_orders],
    group_name="silver",
    kinds={"iceberg"},
    description="Cleaned orders with data quality checks",
    auto_materialize_policy=dg.AutoMaterializePolicy.eager(),
)
def silver_orders(context: AssetExecutionContext) -> MaterializeResult:
    """Clean, deduplicate, and validate orders."""
    df = read_parquet(f"s3://data-lake/bronze/orders/dt={context.partition_key}/")
    
    # Data quality
    df = df.dropDuplicates(["order_id"])
    df = df.filter(df.amount > 0)
    df = df.filter(df.status.isin(["pending", "shipped", "delivered", "cancelled"]))
    
    # Write to Iceberg
    df.writeTo("catalog.silver.orders").overwritePartitions()
    
    return MaterializeResult(
        metadata={"row_count": MetadataValue.int(df.count())}
    )

# Gold layer: business aggregations
@asset(
    deps=[silver_orders],
    group_name="gold",
    kinds={"iceberg"},
    description="Daily revenue metrics by customer segment",
)
def gold_daily_revenue(context: AssetExecutionContext) -> MaterializeResult:
    """Aggregate daily revenue by customer segment."""
    df = spark.sql("""
        SELECT 
            date_trunc('day', order_date) as dt,
            customer_segment,
            COUNT(*) as order_count,
            SUM(amount) as total_revenue,
            AVG(amount) as avg_order_value
        FROM catalog.silver.orders
        WHERE dt = '{partition}'
        GROUP BY 1, 2
    """.format(partition=context.partition_key))
    
    df.writeTo("catalog.gold.daily_revenue").overwritePartitions()
    return MaterializeResult(metadata={"row_count": MetadataValue.int(df.count())})
```

### Partitions and Backfills

```python
from dagster import DailyPartitionsDefinition, WeeklyPartitionsDefinition

# Daily partitions
daily_partitions = DailyPartitionsDefinition(start_date="2024-01-01")

@asset(partitions_def=daily_partitions)
def partitioned_orders(context: AssetExecutionContext):
    partition_date = context.partition_key  # "2024-01-15"
    df = extract_orders_for_date(partition_date)
    write_to_lake(df, partition_date)

# Multi-dimensional partitions
from dagster import MultiPartitionsDefinition, StaticPartitionsDefinition

multi_partitions = MultiPartitionsDefinition({
    "date": DailyPartitionsDefinition(start_date="2024-01-01"),
    "region": StaticPartitionsDefinition(["us-east", "us-west", "eu-west"]),
})

@asset(partitions_def=multi_partitions)
def regional_orders(context: AssetExecutionContext):
    keys = context.partition_key.keys_by_dimension
    date = keys["date"]
    region = keys["region"]
    # Process for specific date + region combination
```

### IO Managers

```python
from dagster import IOManager, io_manager, InputContext, OutputContext
import pyarrow.parquet as pq
import s3fs

class S3ParquetIOManager(IOManager):
    def __init__(self, bucket: str, prefix: str):
        self.bucket = bucket
        self.prefix = prefix
        self.fs = s3fs.S3FileSystem()
    
    def _get_path(self, context) -> str:
        asset_key = "/".join(context.asset_key.path)
        if context.has_partition_key:
            return f"s3://{self.bucket}/{self.prefix}/{asset_key}/partition={context.partition_key}/data.parquet"
        return f"s3://{self.bucket}/{self.prefix}/{asset_key}/data.parquet"
    
    def handle_output(self, context: OutputContext, obj: pd.DataFrame):
        path = self._get_path(context)
        obj.to_parquet(path, filesystem=self.fs)
        context.add_output_metadata({"path": path, "rows": len(obj)})
    
    def load_input(self, context: InputContext) -> pd.DataFrame:
        path = self._get_path(context)
        return pd.read_parquet(path, filesystem=self.fs)

@io_manager(config_schema={"bucket": str, "prefix": str})
def s3_parquet_io_manager(context):
    return S3ParquetIOManager(
        bucket=context.resource_config["bucket"],
        prefix=context.resource_config["prefix"],
    )
```

### Dagster + dbt Integration

```python
from dagster_dbt import DbtCliResource, dbt_assets, DagsterDbtTranslator
from pathlib import Path

dbt_project_dir = Path(__file__).parent / "dbt_project"
dbt_resource = DbtCliResource(project_dir=str(dbt_project_dir))

class CustomDbtTranslator(DagsterDbtTranslator):
    def get_group_name(self, dbt_resource_props):
        return dbt_resource_props.get("fqn", ["default"])[1]  # Use dbt folder as group

@dbt_assets(
    manifest=dbt_project_dir / "target" / "manifest.json",
    dagster_dbt_translator=CustomDbtTranslator(),
)
def my_dbt_assets(context: AssetExecutionContext, dbt: DbtCliResource):
    yield from dbt.cli(["build"], context=context).stream()
```

### Dagster Deployment on K8s

```yaml
# values.yaml for dagster-helm
dagsterWebserver:
  replicaCount: 2
  resources:
    requests:
      cpu: "500m"
      memory: "1Gi"

dagsterDaemon:
  resources:
    requests:
      cpu: "500m"
      memory: "512Mi"

runLauncher:
  type: K8sRunLauncher
  config:
    k8sRunLauncher:
      envConfigMaps:
        - name: dagster-env
      jobNamespace: dagster-runs
      loadInclusterConfig: true

dagster-user-deployments:
  enabled: true
  deployments:
    - name: data-pipelines
      image:
        repository: "123456789.dkr.ecr.us-east-1.amazonaws.com/dagster-pipelines"
        tag: "latest"
      dagsterApiGrpcArgs:
        - "--module-name"
        - "data_pipelines.definitions"
      resources:
        requests:
          cpu: "250m"
          memory: "512Mi"

postgresql:
  enabled: true
  postgresqlPassword: "${DAGSTER_PG_PASSWORD}"
```

### Dagster vs Airflow

| Dimension | Dagster | Airflow |
|-----------|---------|---------|
| Core abstraction | Assets (data-centric) | Tasks (execution-centric) |
| Scheduling | Per-asset freshness policies | Per-DAG schedules |
| Testing | First-class (unit test assets, mock resources) | Difficult (need running instance) |
| Type safety | Python type system, resources are typed | XComs are untyped |
| Backfills | Asset partition backfill (first-class) | Manual `airflow backfill` (brittle) |
| Dev experience | Local development server, fast iteration | Need full env or docker compose |
| Partitioning | Multi-dimensional, declarative | Manual (template macros) |
| Lineage | Automatic from asset dependencies | Manual (dataset feature, newer) |
| Maturity | Growing (2019+) | Very mature (2014+), huge community |
| Migration | Can wrap Airflow DAGs | - |

---

## 3. Temporal Deep Dive

### Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                     Temporal Cluster                               │
│                                                                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐   │
│  │   Frontend   │  │   History    │  │      Matching         │   │
│  │   Service    │  │   Service    │  │      Service          │   │
│  │              │  │              │  │                        │   │
│  │ • gRPC API  │  │ • Workflow   │  │ • Task Queue routing  │   │
│  │ • Rate limit│  │   state mgmt │  │ • Worker dispatching  │   │
│  │ • Auth      │  │ • Timer mgmt│  │ • Load balancing      │   │
│  │ • Routing   │  │ • Event hist │  │                        │   │
│  └──────────────┘  └──────────────┘  └──────────────────────┘   │
│                                                                    │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │                   Persistence Layer                        │    │
│  │  • Cassandra / PostgreSQL / MySQL (workflow state)        │    │
│  │  • Elasticsearch (visibility / search)                    │    │
│  └──────────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────────┘
                              │
                              │ gRPC (poll for tasks)
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│                       Worker Process                               │
│  ┌──────────────────┐  ┌────────────────────────────────────┐   │
│  │ Workflow Worker   │  │         Activity Worker             │   │
│  │                   │  │                                      │   │
│  │ • Deterministic  │  │ • Side effects (DB, API, file I/O) │   │
│  │ • Event sourced  │  │ • Retryable independently           │   │
│  │ • Replay-safe    │  │ • Timeout-able                      │   │
│  └──────────────────┘  └────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────┘
```

### Core Concepts with Data Pipeline Example

```python
from temporalio import workflow, activity
from temporalio.client import Client
from temporalio.worker import Worker
from datetime import timedelta
from dataclasses import dataclass

# Activities: side-effect-ful operations (retryable independently)
@dataclass
class PipelineConfig:
    source_table: str
    target_path: str
    partition_date: str
    quality_threshold: float = 0.95

@activity.defn
async def extract_data(config: PipelineConfig) -> dict:
    """Extract from source database."""
    df = spark.read.jdbc(url, config.source_table, 
                         predicates=[f"dt = '{config.partition_date}'"])
    path = f"s3://staging/{config.source_table}/{config.partition_date}/"
    df.write.parquet(path)
    return {"path": path, "row_count": df.count()}

@activity.defn
async def validate_data(extract_result: dict, config: PipelineConfig) -> dict:
    """Run data quality checks."""
    df = spark.read.parquet(extract_result["path"])
    
    checks = {
        "null_rate": df.filter(df.id.isNull()).count() / df.count(),
        "duplicate_rate": 1 - df.dropDuplicates(["id"]).count() / df.count(),
        "row_count": df.count(),
    }
    
    quality_score = 1.0 - checks["null_rate"] - checks["duplicate_rate"]
    checks["quality_score"] = quality_score
    checks["passed"] = quality_score >= config.quality_threshold
    
    return checks

@activity.defn
async def load_to_iceberg(extract_result: dict, config: PipelineConfig) -> dict:
    """Load validated data to Iceberg table."""
    df = spark.read.parquet(extract_result["path"])
    df.writeTo(f"catalog.silver.{config.source_table}").overwritePartitions()
    return {"status": "success", "rows_loaded": df.count()}

@activity.defn
async def send_alert(message: str, severity: str) -> None:
    """Send alert to PagerDuty/Slack."""
    # ... alerting logic

# Workflow: deterministic orchestration logic
@workflow.defn
class DataPipelineWorkflow:
    @workflow.run
    async def run(self, config: PipelineConfig) -> dict:
        # Step 1: Extract with retry
        extract_result = await workflow.execute_activity(
            extract_data,
            config,
            start_to_close_timeout=timedelta(minutes=30),
            retry_policy=RetryPolicy(
                initial_interval=timedelta(seconds=10),
                maximum_interval=timedelta(minutes=5),
                maximum_attempts=3,
                non_retryable_error_types=["ValueError"],
            ),
        )
        
        # Step 2: Validate
        validation = await workflow.execute_activity(
            validate_data,
            args=[extract_result, config],
            start_to_close_timeout=timedelta(minutes=10),
        )
        
        # Step 3: Gate on quality
        if not validation["passed"]:
            await workflow.execute_activity(
                send_alert,
                args=[f"Quality check failed: {validation}", "warning"],
                start_to_close_timeout=timedelta(seconds=30),
            )
            # Wait for human approval (signal)
            approved = await workflow.wait_condition(
                lambda: self._approved, timeout=timedelta(hours=4)
            )
            if not approved:
                raise ApplicationError("Quality gate rejected - timed out")
        
        # Step 4: Load
        load_result = await workflow.execute_activity(
            load_to_iceberg,
            args=[extract_result, config],
            start_to_close_timeout=timedelta(minutes=30),
            heartbeat_timeout=timedelta(minutes=5),
        )
        
        return {"extract": extract_result, "validation": validation, "load": load_result}
    
    _approved: bool = False
    
    @workflow.signal
    async def approve(self):
        """Human approval signal."""
        self._approved = True
    
    @workflow.query
    def get_status(self) -> str:
        """Query current pipeline status."""
        return self._status

# Saga Pattern (compensating transactions)
@workflow.defn
class OrderSagaWorkflow:
    @workflow.run
    async def run(self, order):
        compensations = []
        try:
            # Step 1
            reservation = await workflow.execute_activity(reserve_inventory, order)
            compensations.append(("release_inventory", reservation))
            
            # Step 2
            payment = await workflow.execute_activity(charge_payment, order)
            compensations.append(("refund_payment", payment))
            
            # Step 3
            await workflow.execute_activity(confirm_order, order)
            
        except Exception as e:
            # Compensate in reverse order
            for comp_activity, comp_data in reversed(compensations):
                await workflow.execute_activity(comp_activity, comp_data)
            raise
```

### Temporal vs Airflow vs Step Functions

| Dimension | Temporal | Airflow | Step Functions |
|-----------|----------|---------|----------------|
| Model | Code-first workflows | DAG definition | JSON/YAML state machine |
| Duration | Minutes to years | Minutes to hours | 1 year max (Standard) |
| Granularity | Any code can be a workflow | Task (operator) | State (Lambda, service call) |
| Human-in-loop | Signals + queries (first-class) | Manual trigger | Callback pattern |
| Testing | Unit test like regular code | Difficult | Local testing with SAM |
| Versioning | Worker-level versioning | DAG versioning | Alias-based |
| Cost | Self-hosted (infra) | Self-hosted (infra) | Per-state-transition |
| Best for | Complex business workflows, sagas, long-running | Data pipeline scheduling | Event-driven AWS orchestration |

---

## 4. AWS Step Functions Deep Dive

### Architecture

```
┌────────────────────────────────────────────────────────────────┐
│                    AWS Step Functions                            │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              State Machine (ASL Definition)                │  │
│  │                                                            │  │
│  │  Start → Extract → Validate → Choice ──┬── Load           │  │
│  │                                         │                  │  │
│  │                                    (quality_ok?)           │  │
│  │                                         │                  │  │
│  │                                    No ──┴── Alert → Fail  │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
│  Execution Types:                                               │
│  ┌───────────────────┐  ┌────────────────────────────────┐    │
│  │    Standard        │  │          Express                │    │
│  │ • 1 year duration │  │ • 5 min duration               │    │
│  │ • Exactly-once    │  │ • At-least-once                │    │
│  │ • $0.025/1K trans │  │ • $1/1M requests + duration    │    │
│  │ • Audit history   │  │ • No execution history         │    │
│  └───────────────────┘  └────────────────────────────────┘    │
└────────────────────────────────────────────────────────────────┘
```

### Distributed Map (Batch Processing)

```json
{
  "Comment": "Process 100K+ files with Distributed Map",
  "StartAt": "ProcessFiles",
  "States": {
    "ProcessFiles": {
      "Type": "Map",
      "ItemProcessor": {
        "ProcessorConfig": {
          "Mode": "DISTRIBUTED",
          "ExecutionType": "STANDARD"
        },
        "StartAt": "ProcessSingleFile",
        "States": {
          "ProcessSingleFile": {
            "Type": "Task",
            "Resource": "arn:aws:lambda:us-east-1:123456789:function:process-file",
            "End": true
          }
        }
      },
      "ItemReader": {
        "Resource": "arn:aws:states:::s3:listObjectsV2",
        "Parameters": {
          "Bucket": "data-lake-raw",
          "Prefix": "incoming/2024-01-15/"
        }
      },
      "MaxConcurrency": 1000,
      "ToleratedFailurePercentage": 5,
      "ResultWriter": {
        "Resource": "arn:aws:states:::s3:putObject",
        "Parameters": {
          "Bucket": "data-lake-results",
          "Prefix": "processing-results/2024-01-15/"
        }
      },
      "End": true
    }
  }
}
```

### Complete Data Pipeline Orchestration

```json
{
  "Comment": "Data Pipeline: Extract (DMS) → Quality (Glue) → Transform (Glue) → Load (Athena)",
  "StartAt": "StartDMSTask",
  "States": {
    "StartDMSTask": {
      "Type": "Task",
      "Resource": "arn:aws:states:::aws-sdk:databasemigration:startReplicationTask",
      "Parameters": {
        "ReplicationTaskArn": "arn:aws:dms:us-east-1:123:task:ABC123",
        "StartReplicationTaskType": "reload-target"
      },
      "Next": "WaitForDMS",
      "Retry": [
        {
          "ErrorEquals": ["States.TaskFailed"],
          "IntervalSeconds": 60,
          "MaxAttempts": 3,
          "BackoffRate": 2.0
        }
      ]
    },
    "WaitForDMS": {
      "Type": "Wait",
      "Seconds": 300,
      "Next": "CheckDMSStatus"
    },
    "CheckDMSStatus": {
      "Type": "Task",
      "Resource": "arn:aws:states:::aws-sdk:databasemigration:describeReplicationTasks",
      "Parameters": {
        "Filters": [{"Name": "replication-task-arn", "Values.$": "$.ReplicationTaskArn"}]
      },
      "Next": "IsDMSComplete"
    },
    "IsDMSComplete": {
      "Type": "Choice",
      "Choices": [
        {
          "Variable": "$.ReplicationTasks[0].Status",
          "StringEquals": "stopped",
          "Next": "RunDataQuality"
        }
      ],
      "Default": "WaitForDMS"
    },
    "RunDataQuality": {
      "Type": "Task",
      "Resource": "arn:aws:states:::glue:startJobRun.sync",
      "Parameters": {
        "JobName": "data-quality-check",
        "Arguments": {
          "--source_path": "s3://data-lake/raw/orders/",
          "--quality_threshold": "0.95"
        }
      },
      "Next": "QualityGate",
      "Catch": [
        {
          "ErrorEquals": ["States.TaskFailed"],
          "Next": "AlertDataQualityFailed"
        }
      ]
    },
    "QualityGate": {
      "Type": "Choice",
      "Choices": [
        {
          "Variable": "$.JobRunState",
          "StringEquals": "SUCCEEDED",
          "Next": "RunTransformation"
        }
      ],
      "Default": "AlertDataQualityFailed"
    },
    "RunTransformation": {
      "Type": "Parallel",
      "Branches": [
        {
          "StartAt": "TransformOrders",
          "States": {
            "TransformOrders": {
              "Type": "Task",
              "Resource": "arn:aws:states:::glue:startJobRun.sync",
              "Parameters": {
                "JobName": "transform-orders",
                "Arguments": {"--partition_date.$": "$.partition_date"}
              },
              "End": true
            }
          }
        },
        {
          "StartAt": "TransformCustomers",
          "States": {
            "TransformCustomers": {
              "Type": "Task",
              "Resource": "arn:aws:states:::glue:startJobRun.sync",
              "Parameters": {"JobName": "transform-customers"},
              "End": true
            }
          }
        }
      ],
      "Next": "RunAthenaAggregation"
    },
    "RunAthenaAggregation": {
      "Type": "Task",
      "Resource": "arn:aws:states:::athena:startQueryExecution.sync",
      "Parameters": {
        "QueryString": "INSERT INTO gold.daily_revenue SELECT date_trunc('day', order_date), SUM(amount) FROM silver.orders GROUP BY 1",
        "WorkGroup": "data-pipeline",
        "ResultConfiguration": {
          "OutputLocation": "s3://athena-results/pipeline/"
        }
      },
      "Next": "PipelineSuccess"
    },
    "AlertDataQualityFailed": {
      "Type": "Task",
      "Resource": "arn:aws:states:::sns:publish",
      "Parameters": {
        "TopicArn": "arn:aws:sns:us-east-1:123:data-alerts",
        "Message": "Data quality check failed for pipeline run"
      },
      "Next": "PipelineFailed"
    },
    "PipelineSuccess": {"Type": "Succeed"},
    "PipelineFailed": {"Type": "Fail", "Error": "QualityCheckFailed"}
  }
}
```

### Step Functions Limitations

| Limitation | Impact | Workaround |
|-----------|--------|------------|
| Payload 256KB max | Can't pass large data between states | Use S3 for data, pass S3 URIs |
| 25K history events | Long-running workflows hit limit | Use nested (child) executions |
| Standard: 1 year max | Not for indefinite processes | Use Express + re-trigger pattern |
| Express: 5 min max | Not for long-running tasks | Use Standard or callback |
| No loops (native) | Complex iteration | Map state or recursive execution |
| Cold start | Lambda cold starts add latency | Provisioned concurrency |

---

## 5. Prefect Deep Dive

### Architecture (Prefect 2.x/3.x)

```
┌────────────────────────────────────────────────────────────────┐
│                    Prefect Architecture                          │
│                                                                  │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐   │
│  │ Prefect      │     │  Work Pools  │     │   Workers     │   │
│  │ Server/Cloud │────▶│              │────▶│              │   │
│  │              │     │ • Process    │     │ • Poll for   │   │
│  │ • API       │     │ • K8s        │     │   flow runs  │   │
│  │ • UI        │     │ • Docker     │     │ • Execute    │   │
│  │ • Scheduler │     │ • ECS        │     │   locally    │   │
│  └──────────────┘     └──────────────┘     └──────────────┘   │
└────────────────────────────────────────────────────────────────┘
```

### Core Concepts

```python
from prefect import flow, task
from prefect.tasks import task_input_hash
from datetime import timedelta

@task(
    retries=3,
    retry_delay_seconds=60,
    cache_key_fn=task_input_hash,
    cache_expiration=timedelta(hours=1),
    log_prints=True,
)
def extract_data(source: str, date: str) -> pd.DataFrame:
    """Extract with automatic retry and caching."""
    print(f"Extracting from {source} for {date}")
    return pd.read_sql(f"SELECT * FROM {source} WHERE dt = '{date}'", conn)

@task(retries=2)
def validate(df: pd.DataFrame) -> bool:
    assert len(df) > 0, "Empty dataframe"
    assert df.duplicated().sum() == 0, "Duplicates found"
    return True

@task
def load(df: pd.DataFrame, target: str):
    df.to_parquet(f"s3://lake/{target}/")

@flow(name="daily-etl", log_prints=True)
def daily_pipeline(date: str, sources: list[str]):
    """Dynamic flow - no pre-defined DAG required."""
    for source in sources:  # Dynamic iteration (impossible in Airflow DAGs)
        df = extract_data(source, date)
        if validate(df):
            load(df, source)
        else:
            print(f"Skipping {source} - validation failed")

# Run
daily_pipeline(date="2024-01-15", sources=["orders", "customers", "products"])
```

### Prefect vs Airflow Key Differences

| Aspect | Prefect | Airflow |
|--------|---------|---------|
| DAG definition | Not required (dynamic at runtime) | Required (static, pre-parsed) |
| Parameters | Native Python function args | Params dict, templates |
| Dynamic tasks | Native (loops, conditionals) | Dynamic task mapping (2.3+) |
| Local execution | `python my_flow.py` (instant) | Need scheduler + webserver |
| Deployment | Deploy independently per flow | DAG folder (coupled) |

---

## 6. Amazon MWAA

### Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    Amazon MWAA                                 │
│                                                                │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │  Customer VPC                                            │ │
│  │  ┌──────────┐  ┌──────────┐  ┌────────────────────┐   │ │
│  │  │Scheduler │  │ Workers  │  │  Web Server         │   │ │
│  │  │(Fargate) │  │(Fargate) │  │  (Fargate)          │   │ │
│  │  │          │  │2-25 auto │  │  Public or Private  │   │ │
│  │  └──────────┘  └──────────┘  └────────────────────┘   │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                                │
│  ┌───────────────┐  ┌────────────────┐  ┌───────────────┐   │
│  │ Aurora (meta) │  │ S3 (DAGs,      │  │ CloudWatch    │   │
│  │ Managed       │  │  plugins, reqs)│  │ (logs)        │   │
│  └───────────────┘  └────────────────┘  └───────────────┘   │
└──────────────────────────────────────────────────────────────┘
```

### MWAA Sizing and Limitations

| Environment Class | Scheduler | Workers | Max DAGs | Cost/hour |
|-------------------|-----------|---------|----------|-----------|
| mw1.small | 2 vCPU, 2GB | 1-10 | ~50 | ~$0.49 |
| mw1.medium | 2 vCPU, 4GB | 1-20 | ~250 | ~$0.97 |
| mw1.large | 4 vCPU, 8GB | 1-25 | ~1000 | ~$1.94 |

**Key Limitations:**
- Worker startup: 3-5 minutes (cold start)
- DAG parsing: all DAGs parsed every 30s (performance impact with many DAGs)
- Plugins: must be zipped and uploaded to S3
- Python packages: requirements.txt (some packages incompatible with Fargate)
- No SSH to workers (debugging harder)
- VPC required (networking complexity)

### MWAA vs Self-Managed Airflow on EKS

| Dimension | MWAA | Airflow on EKS |
|-----------|------|----------------|
| Ops overhead | Low (managed) | High (K8s expertise needed) |
| Scaling | Auto 2-25 workers (slow) | KubernetesExecutor (fast pod creation) |
| Cost | Premium (~2-3x) | Lower at scale (spot instances) |
| Customization | Limited (package constraints) | Full control |
| Networking | VPC required, complex | Standard K8s networking |
| Debugging | CloudWatch only | kubectl exec, full access |
| Best for | Small-medium teams, <250 DAGs | Large teams, heavy workloads, customization |

---

## 7. Orchestration Patterns at Scale

### Event-Driven Orchestration

```python
# Dagster sensor: trigger on S3 file arrival
from dagster import sensor, RunRequest, SensorEvaluationContext
import boto3

@sensor(job=process_new_files_job, minimum_interval_seconds=30)
def s3_file_sensor(context: SensorEvaluationContext):
    s3 = boto3.client('s3')
    
    # Get cursor (last processed file)
    last_key = context.cursor or ""
    
    response = s3.list_objects_v2(
        Bucket='data-lake-incoming',
        Prefix='orders/',
        StartAfter=last_key
    )
    
    new_files = response.get('Contents', [])
    if not new_files:
        return
    
    for file in new_files:
        yield RunRequest(
            run_key=file['Key'],
            run_config={"ops": {"process": {"config": {"file_path": file['Key']}}}}
        )
    
    context.update_cursor(new_files[-1]['Key'])
```

### Multi-Team Orchestration Pattern

```
┌─────────────────────────────────────────────────────────┐
│              Platform Team (Shared Infrastructure)        │
│  ┌────────────────────────────────────────────────────┐ │
│  │  Shared Resources: Connections, IO Managers, Alerts │ │
│  └────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
        │                    │                    │
        ▼                    ▼                    ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│  Team A      │  │  Team B      │  │  Team C      │
│  (Orders)    │  │  (Payments)  │  │  (Analytics) │
│              │  │              │  │              │
│  Own assets  │  │  Own assets  │  │  Own assets  │
│  Own schedules│  │  Own schedules│  │  Own schedules│
│  Own alerts  │  │  Own alerts  │  │  Own alerts  │
└──────────────┘  └──────────────┘  └──────────────┘

Cross-team dependencies via:
  • Asset sensors (Team C depends on Team A's gold assets)
  • Shared external assets (SourceAssets)
  • Contract: asset metadata (SLA, schema, owner)
```

### Backfill Strategies

```python
# Dagster: partition-aware backfill
@asset(
    partitions_def=DailyPartitionsDefinition(start_date="2024-01-01"),
    backfill_policy=dg.BackfillPolicy.single_run(),  # All partitions in one run
    # vs BackfillPolicy.multi_run(max_partitions_per_run=7)  # Weekly batches
)
def orders_daily(context):
    # Dagster handles partition selection
    partition_date = context.partition_key
    ...

# Airflow backfill (manual, brittle)
# airflow dags backfill -s 2024-01-01 -e 2024-01-31 my_dag
# Problems: creates N DagRuns, can overwhelm scheduler, no progress tracking
```

---

## 8. Decision Framework

### Comparison Matrix

| Dimension | Airflow | Dagster | Temporal | Step Functions | Prefect |
|-----------|---------|---------|----------|----------------|---------|
| **Paradigm** | DAG/tasks | Assets | Workflows | State machine | Flows/tasks |
| **Complexity** | Medium | Medium | High | Low-Medium | Low |
| **Learning curve** | Medium | Medium | High | Low | Low |
| **Testing** | Hard | Easy | Easy | Medium | Easy |
| **Scalability** | Good (K8sExec) | Good (K8s) | Excellent | Excellent | Good |
| **Long-running** | Poor | Poor | Excellent | Good (Standard) | Poor |
| **Dynamic pipelines** | Limited | Good | Native | Map state | Native |
| **Cloud-native (AWS)** | MWAA | Dagster+ | Self-host | Native | Prefect Cloud |
| **Community** | Massive | Growing | Growing | AWS-only | Growing |
| **Cost (managed)** | MWAA: $$$  | Dagster+: $$ | Self-host | Per-transition | Cloud: $$ |
| **Best for** | Mature data teams | Modern data teams | Complex workflows | AWS-native, serverless | Small-medium teams |

### Decision Tree

```
What's your primary use case?

├── Scheduled data pipelines (ETL/ELT)
│   ├── Existing Airflow? Large team? → Stay with Airflow (MWAA or EKS)
│   ├── New project? Data-centric thinking? → Dagster
│   └── Simple pipelines? Dynamic? → Prefect
│
├── Complex business workflows (sagas, human-in-loop, long-running)
│   └── Temporal
│
├── Event-driven, serverless AWS
│   └── Step Functions
│
├── Hybrid (data + business logic)
│   └── Dagster (data) + Temporal (business workflows)
│
└── Cost-sensitive, AWS-heavy, minimal ops
    └── Step Functions + EventBridge
```

---

## 9. Production Checklist

### Dagster
- [ ] K8s deployment with separate user code deployments
- [ ] PostgreSQL for run storage (not SQLite)
- [ ] S3 IO Manager for asset persistence
- [ ] Asset freshness policies configured
- [ ] Sensors for external data arrival
- [ ] Resource configuration per environment (dev/staging/prod)
- [ ] Alerting on asset materialization failures
- [ ] Partition backfill tested
- [ ] dbt integration tested with manifest refresh
- [ ] Dagster daemon running (schedules, sensors, auto-materialize)

### Temporal
- [ ] Cluster sized (Cassandra/PostgreSQL, history shards)
- [ ] Worker fleet auto-scaled
- [ ] Workflow versioning strategy defined
- [ ] Activity retry policies tuned
- [ ] Heartbeat timeouts for long activities
- [ ] Dead letter queue for failed workflows
- [ ] Search attributes for visibility queries
- [ ] Archival configured (completed workflow cleanup)
- [ ] mTLS between workers and cluster
- [ ] Load test: max concurrent workflows

### Step Functions
- [ ] Standard vs Express chosen per workflow
- [ ] Error handling (Retry + Catch) on all Task states
- [ ] Payload size verified (< 256KB between states)
- [ ] Distributed Map for batch (max concurrency set)
- [ ] CloudWatch alarms: ExecutionsFailed, ExecutionsTimedOut
- [ ] X-Ray tracing enabled
- [ ] IAM execution role least-privilege
- [ ] EventBridge rule for scheduled triggers
- [ ] Cost estimated (state transitions × executions/day)
- [ ] Integration tested with Glue/Athena/Lambda timeouts

### MWAA
- [ ] VPC with private subnets and NAT gateway
- [ ] Environment class sized for DAG count
- [ ] Requirements.txt tested (constraint conflicts)
- [ ] Plugins packaged and versioned
- [ ] DAG parsing performance optimized (reduce import time)
- [ ] CloudWatch log groups monitored
- [ ] Startup script configured
- [ ] DAG serialization enabled (reduce DB load)
- [ ] Connection secrets in Secrets Manager (not Airflow UI)
- [ ] Worker auto-scaling tested under load
