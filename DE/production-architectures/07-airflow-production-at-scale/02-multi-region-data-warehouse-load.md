# Problem 2: Multi-Region Data Warehouse Load (Uber-Scale)

## The Problem

Uber operates in 70+ countries. Each country/region runs its own ETL pipelines producing
trip data, earnings, safety metrics, and marketplace signals. All of this must consolidate
into a single global data warehouse for cross-region analytics, executive dashboards, and
ML feature stores.

The dependency chain:

```
Regional ETLs (70+) → Global Aggregation → Analytics-Ready Tables → Dashboard Refresh
```

Challenges:
- **Inter-DAG dependencies**: 200+ DAGs that depend on each other across 5-6 levels
- **All-or-nothing convergence**: Global aggregation cannot start until ALL upstream regions complete
- **Clock skew**: Regions operate in different timezones with different SLAs
- **Partial failure**: One slow region blocks the entire pipeline
- **Circular debugging**: When something fails at level 5, tracing back through 200 DAGs is hell

## Scale Numbers

| Metric | Value |
|--------|-------|
| Data warehouse size | 500TB+ |
| Interdependent DAGs | 200+ |
| Regional data sources | 70+ |
| Task instances/day | 50,000+ |
| Dependency depth | 5-6 levels |
| Max acceptable latency | 4 hours from regional close to dashboard |
| Concurrent running DAGs | ~80 at peak |

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         REGIONAL ETL LAYER                               │
│                                                                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐       ┌──────────┐          │
│  │ US-East  │  │ EU-West  │  │ APAC-SGP │  ...  │ LATAM-BR │          │
│  │ ETL DAG  │  │ ETL DAG  │  │ ETL DAG  │       │ ETL DAG  │          │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘       └────┬─────┘          │
│       │              │              │                   │                │
│       ▼              ▼              ▼                   ▼                │
│  [Dataset:      [Dataset:      [Dataset:          [Dataset:             │
│   us_east_      eu_west_       apac_sgp_          latam_br_             │
│   trips]        trips]         trips]              trips]               │
└───────┼──────────────┼──────────────┼───────────────────┼───────────────┘
        │              │              │                   │
        ▼              ▼              ▼                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    GLOBAL AGGREGATION LAYER                               │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────┐        │
│  │  global_trip_aggregation DAG                                 │        │
│  │  (triggered when ALL regional datasets updated)              │        │
│  │                                                              │        │
│  │  [merge_regions] → [compute_global_metrics] → [write_warehouse]│     │
│  └──────────────────────────────────┬──────────────────────────┘        │
│                                     │                                    │
│                                     ▼                                    │
│                              [Dataset: global_trips]                     │
└─────────────────────────────────────┼────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                     ANALYTICS & DASHBOARD LAYER                           │
│                                                                          │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐            │
│  │ Executive KPIs │  │ ML Feature     │  │ Regional       │            │
│  │ DAG            │  │ Store DAG      │  │ Comparison DAG │            │
│  └────────────────┘  └────────────────┘  └────────────────┘            │
└─────────────────────────────────────────────────────────────────────────┘
```

## Airflow Concepts Taught

### 1. Cross-DAG Dependencies

Three approaches exist, each with distinct trade-offs:

#### ExternalTaskSensor

Polls the state of a task in another DAG. The original cross-DAG mechanism.

```python
from airflow.sensors.external_task import ExternalTaskSensor
from datetime import timedelta

wait_for_us_east = ExternalTaskSensor(
    task_id="wait_for_us_east_etl",
    external_dag_id="us_east_regional_etl",
    external_task_id="final_validation",
    # Critical: match execution dates across DAGs with different schedules
    execution_delta=timedelta(hours=0),
    # NEVER use 'poke' in production at scale - holds a worker slot
    mode="reschedule",
    timeout=7200,  # 2 hours
    poke_interval=300,  # check every 5 min
    exponential_backoff=True,
)
```

#### TriggerDagRunOperator

Actively triggers a downstream DAG instead of passively waiting.

```python
from airflow.operators.trigger_dagrun import TriggerDagRunOperator

trigger_global = TriggerDagRunOperator(
    task_id="trigger_global_aggregation",
    trigger_dag_id="global_trip_aggregation",
    conf={"triggered_by": "us_east", "execution_date": "{{ ds }}"},
    wait_for_completion=True,  # block until downstream finishes
    poke_interval=60,
    allowed_states=["success"],
    failed_states=["failed"],
)
```

#### Datasets (Airflow 2.4+) - The Modern Approach

Declarative, event-driven. No polling. No worker slots wasted.

```python
from airflow.datasets import Dataset

# Define datasets as URIs
us_east_trips = Dataset("s3://uber-warehouse/us-east/trips/{{ ds }}")
eu_west_trips = Dataset("s3://uber-warehouse/eu-west/trips/{{ ds }}")
```

#### When to Use Which

| Method | Use When | Avoid When |
|--------|----------|------------|
| ExternalTaskSensor | Legacy DAGs you can't modify | High-scale (wastes slots) |
| TriggerDagRunOperator | You need to pass config, fan-out | Simple data dependencies |
| Datasets | New DAGs, data-driven triggers | Need task-level granularity |

---

### 2. Datasets (Data-Aware Scheduling)

Datasets decouple producers from consumers. A consumer DAG runs only when its
input datasets have ALL been updated.

#### Dataset URI Conventions

```python
from airflow.datasets import Dataset

# Convention: protocol://system/domain/entity/partition
us_east_trips = Dataset("s3://uber-warehouse/us-east/trips/daily")
eu_west_trips = Dataset("s3://uber-warehouse/eu-west/trips/daily")
apac_sgp_trips = Dataset("s3://uber-warehouse/apac-sgp/trips/daily")
latam_br_trips = Dataset("s3://uber-warehouse/latam-br/trips/daily")
global_trips = Dataset("s3://uber-warehouse/global/trips/daily")
```

#### Producer DAG

```python
from airflow import DAG
from airflow.datasets import Dataset
from airflow.providers.amazon.aws.operators.emr import EmrServerlessStartJobOperator
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta

us_east_trips = Dataset("s3://uber-warehouse/us-east/trips/daily")

default_args = {
    "owner": "data-platform",
    "retries": 3,
    "retry_delay": timedelta(minutes=10),
    "retry_exponential_backoff": True,
    "max_retry_delay": timedelta(minutes=60),
    "execution_timeout": timedelta(hours=2),
}

with DAG(
    dag_id="us_east_regional_etl",
    schedule="0 6 * * *",  # 6 AM UTC daily
    start_date=datetime(2024, 1, 1),
    catchup=False,
    default_args=default_args,
    tags=["regional", "us-east", "producer"],
) as dag:

    extract = EmrServerlessStartJobOperator(
        task_id="extract_trip_events",
        application_id="{{ var.value.emr_app_id_us_east }}",
        execution_role_arn="{{ var.value.emr_role_arn }}",
        job_driver={
            "sparkSubmit": {
                "entryPoint": "s3://uber-etl/jars/trip-extract.jar",
                "sparkSubmitParameters": "--conf spark.executor.instances=200",
            }
        },
    )

    transform = EmrServerlessStartJobOperator(
        task_id="transform_and_validate",
        application_id="{{ var.value.emr_app_id_us_east }}",
        execution_role_arn="{{ var.value.emr_role_arn }}",
        job_driver={
            "sparkSubmit": {
                "entryPoint": "s3://uber-etl/jars/trip-transform.jar",
            }
        },
    )

    # This task produces the dataset - signals downstream consumers
    publish = PythonOperator(
        task_id="publish_to_warehouse",
        python_callable=lambda: print("Region data landed in warehouse"),
        outlets=[us_east_trips],  # <-- THIS triggers consumers
    )

    extract >> transform >> publish
```

#### Consumer DAG (Multi-Dataset Trigger)

```python
from airflow import DAG
from airflow.datasets import Dataset
from airflow.operators.python import PythonOperator
from airflow.providers.amazon.aws.operators.emr import EmrServerlessStartJobOperator
from datetime import datetime, timedelta

# ALL of these must update before this DAG runs (AND logic)
us_east_trips = Dataset("s3://uber-warehouse/us-east/trips/daily")
eu_west_trips = Dataset("s3://uber-warehouse/eu-west/trips/daily")
apac_sgp_trips = Dataset("s3://uber-warehouse/apac-sgp/trips/daily")
latam_br_trips = Dataset("s3://uber-warehouse/latam-br/trips/daily")

global_trips = Dataset("s3://uber-warehouse/global/trips/daily")

with DAG(
    dag_id="global_trip_aggregation",
    # Triggered by datasets, not cron
    schedule=[us_east_trips, eu_west_trips, apac_sgp_trips, latam_br_trips],
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["global", "aggregation", "consumer"],
) as dag:

    merge = EmrServerlessStartJobOperator(
        task_id="merge_all_regions",
        application_id="{{ var.value.emr_app_id_global }}",
        execution_role_arn="{{ var.value.emr_role_arn }}",
        job_driver={
            "sparkSubmit": {
                "entryPoint": "s3://uber-etl/jars/global-merge.jar",
                "sparkSubmitParameters": "--conf spark.executor.instances=500",
            }
        },
    )

    compute_metrics = EmrServerlessStartJobOperator(
        task_id="compute_global_metrics",
        application_id="{{ var.value.emr_app_id_global }}",
        execution_role_arn="{{ var.value.emr_role_arn }}",
        job_driver={
            "sparkSubmit": {
                "entryPoint": "s3://uber-etl/jars/global-metrics.jar",
            }
        },
    )

    publish_global = PythonOperator(
        task_id="publish_global_dataset",
        python_callable=lambda: print("Global aggregation complete"),
        outlets=[global_trips],
    )

    merge >> compute_metrics >> publish_global
```

#### Dataset Limitations

1. **AND-only logic** - all listed datasets must update (no OR triggers)
2. **No partition awareness** - URI is static, cannot template `{{ ds }}`
3. **No cross-Airflow-instance support** - single cluster only
4. **No conditional datasets** - cannot say "trigger if 60/70 regions complete"

Workaround for partial completion (60 of 70 regions):

```python
# Use a "gate" DAG on a schedule that checks completion percentage
from airflow.operators.python import BranchPythonOperator

def check_region_completion(**context):
    from airflow.models import DagRun
    session = context["session"]
    today = context["ds"]

    completed = session.query(DagRun).filter(
        DagRun.dag_id.like("%_regional_etl"),
        DagRun.execution_date == today,
        DagRun.state == "success",
    ).count()

    total_regions = 70
    if completed / total_regions >= 0.85:  # 85% threshold
        return "trigger_global_aggregation"
    else:
        return "wait_more"
```

---

### 3. Sensors Deep Dive

Sensors are operators that wait for a condition. At Uber-scale, sensor misconfiguration
is the #1 cause of worker pool exhaustion.

#### mode='poke' vs mode='reschedule'

```
POKE MODE (DANGEROUS AT SCALE):
┌─────────────────────────────────────────────────────┐
│ Worker Slot                                          │
│ ████████░░░░████████░░░░████████░░░░████████ SUCCESS│
│ ^check   ^sleep  ^check  ^sleep  ^check             │
│                                                      │
│ HOLDS THE SLOT FOR ENTIRE DURATION (could be hours) │
└─────────────────────────────────────────────────────┘

RESCHEDULE MODE (PRODUCTION-SAFE):
┌──────┐     ┌──────┐     ┌──────┐     ┌──────┐
│ Slot │     │ Slot │     │ Slot │     │ Slot │
│██████│     │██████│     │██████│     │██████│ SUCCESS
└──────┘     └──────┘     └──────┘     └──────┘
 ^check       ^check       ^check       ^check
 (release)    (release)    (release)

 SLOT IS FREE BETWEEN CHECKS
```

**Rule**: Always use `mode='reschedule'` unless poke_interval < 30 seconds.

#### Deferrable Sensors (Airflow 2.4+)

Even better than reschedule - uses the triggerer process instead of a worker:

```python
from airflow.providers.amazon.aws.sensors.s3 import S3KeySensor

wait_for_data = S3KeySensor(
    task_id="wait_for_regional_data",
    bucket_name="uber-warehouse",
    bucket_key="us-east/trips/{{ ds }}/_SUCCESS",
    aws_conn_id="aws_default",
    # Deferrable - uses triggerer, zero worker slots consumed
    deferrable=True,
    timeout=14400,  # 4 hours
    poke_interval=120,
)
```

#### ExternalTaskSensor Production Configuration

```python
from airflow.sensors.external_task import ExternalTaskSensor
from airflow.utils.state import DagRunState

wait_for_upstream = ExternalTaskSensor(
    task_id="wait_for_eu_west",
    external_dag_id="eu_west_regional_etl",
    external_task_id="publish_to_warehouse",
    allowed_states=[DagRunState.SUCCESS],
    failed_states=[DagRunState.FAILED],
    mode="reschedule",
    timeout=7200,
    poke_interval=300,
    exponential_backoff=True,
    # Soft fail: mark as skipped instead of failed
    # Useful when one region being slow shouldn't fail the whole pipeline
    soft_fail=False,
)
```

#### Soft Fail vs Hard Fail

| Setting | Behavior | Use Case |
|---------|----------|----------|
| `soft_fail=False` | Task fails → DAG fails | Critical dependencies |
| `soft_fail=True` | Task skipped → downstream can use trigger_rule | Optional dependencies |

---

### 4. TriggerDagRunOperator

For active orchestration patterns where a coordinator DAG controls execution flow.

#### Fan-Out Pattern

```python
from airflow import DAG
from airflow.operators.trigger_dagrun import TriggerDagRunOperator
from airflow.operators.python import PythonOperator
from datetime import datetime

with DAG(
    dag_id="global_aggregation_complete_fanout",
    schedule=None,  # triggered by upstream
    start_date=datetime(2024, 1, 1),
    tags=["orchestrator", "fan-out"],
) as dag:

    # Fan-out: trigger multiple downstream consumers
    trigger_executive_kpis = TriggerDagRunOperator(
        task_id="trigger_executive_kpis",
        trigger_dag_id="executive_kpi_dashboard",
        conf={
            "source": "global_aggregation",
            "execution_date": "{{ ds }}",
            "priority": "P0",
        },
        wait_for_completion=False,  # fire-and-forget
        reset_dag_run=True,  # clear if already exists
    )

    trigger_ml_features = TriggerDagRunOperator(
        task_id="trigger_ml_features",
        trigger_dag_id="ml_feature_store_refresh",
        conf={"execution_date": "{{ ds }}"},
        wait_for_completion=False,
    )

    trigger_regional_comparison = TriggerDagRunOperator(
        task_id="trigger_regional_comparison",
        trigger_dag_id="regional_comparison_report",
        conf={"execution_date": "{{ ds }}"},
        wait_for_completion=True,  # block - needed for SLA
        poke_interval=120,
        allowed_states=["success"],
        failed_states=["failed"],
    )

    # All fire in parallel (no dependencies between them)
    [trigger_executive_kpis, trigger_ml_features, trigger_regional_comparison]
```

#### Passing Configuration

```python
# In the triggered DAG, access conf:
def process_with_conf(**context):
    conf = context["dag_run"].conf
    source = conf.get("source", "unknown")
    priority = conf.get("priority", "P2")
    execution_date = conf.get("execution_date")

    if priority == "P0":
        # Allocate more resources
        spark_config = {"spark.executor.instances": "500"}
    else:
        spark_config = {"spark.executor.instances": "100"}

    return spark_config
```

---

### 5. Trigger Rules

Trigger rules control when a task runs based on upstream task states. Critical for
multi-region convergence where not all paths may succeed.

```python
from airflow.utils.trigger_rule import TriggerRule

# In multi-region scenarios:

# Default: ALL upstream tasks must succeed
task_all_success = PythonOperator(
    task_id="requires_all_regions",
    trigger_rule=TriggerRule.ALL_SUCCESS,  # default
    python_callable=strict_aggregation,
)

# Run if no upstream FAILED (skipped is OK)
task_none_failed = PythonOperator(
    task_id="tolerant_aggregation",
    trigger_rule=TriggerRule.NONE_FAILED,
    python_callable=partial_aggregation,
)

# Run regardless of upstream state (cleanup tasks)
task_all_done = PythonOperator(
    task_id="send_completion_report",
    trigger_rule=TriggerRule.ALL_DONE,
    python_callable=send_report,
)

# Run as soon as ONE upstream succeeds (fast-path)
task_one_success = PythonOperator(
    task_id="early_partial_metrics",
    trigger_rule=TriggerRule.ONE_SUCCESS,
    python_callable=compute_partial,
)
```

#### Multi-Region Convergence Pattern

```python
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.sensors.external_task import ExternalTaskSensor
from airflow.utils.trigger_rule import TriggerRule
from datetime import datetime, timedelta

with DAG(
    dag_id="global_convergence",
    schedule="0 12 * * *",
    start_date=datetime(2024, 1, 1),
) as dag:

    # Wait for each region (soft_fail=True means skipped if timeout)
    region_sensors = []
    regions = ["us_east", "us_west", "eu_west", "eu_east", "apac_sgp",
               "apac_tokyo", "latam_br", "latam_mx", "africa_ng", "mena_ae"]

    for region in regions:
        sensor = ExternalTaskSensor(
            task_id=f"wait_{region}",
            external_dag_id=f"{region}_regional_etl",
            external_task_id="publish_to_warehouse",
            mode="reschedule",
            timeout=5400,  # 90 min
            poke_interval=300,
            soft_fail=True,  # Skip if region times out
        )
        region_sensors.append(sensor)

    # Runs if NO region sensor FAILED (skipped is acceptable)
    aggregate = PythonOperator(
        task_id="aggregate_available_regions",
        trigger_rule=TriggerRule.NONE_FAILED,
        python_callable=aggregate_regions,
    )

    # Always runs - reports which regions made it
    report = PythonOperator(
        task_id="completion_report",
        trigger_rule=TriggerRule.ALL_DONE,
        python_callable=report_completion,
    )

    region_sensors >> aggregate >> report
```

---

## Production Implementation: Complete Working Example

```python
"""
Complete production setup for multi-region data warehouse load.
File: dags/multi_region_warehouse.py
"""
from __future__ import annotations

from airflow import DAG
from airflow.datasets import Dataset
from airflow.operators.python import PythonOperator, BranchPythonOperator
from airflow.operators.trigger_dagrun import TriggerDagRunOperator
from airflow.operators.empty import EmptyOperator
from airflow.sensors.external_task import ExternalTaskSensor
from airflow.utils.trigger_rule import TriggerRule
from airflow.models import Variable
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

# ============================================================
# DATASET DEFINITIONS
# ============================================================
REGIONS = [
    "us_east", "us_west", "eu_west", "eu_central",
    "apac_singapore", "apac_tokyo", "apac_sydney",
    "latam_brazil", "latam_mexico", "mena_uae",
]

REGIONAL_DATASETS = {
    region: Dataset(f"s3://uber-warehouse/{region}/trips/daily")
    for region in REGIONS
}

GLOBAL_DATASET = Dataset("s3://uber-warehouse/global/trips/daily")

# ============================================================
# REGIONAL ETL DAG FACTORY
# ============================================================
def create_regional_etl_dag(region: str, schedule: str) -> DAG:
    """Factory function to create a regional ETL DAG."""

    dataset = REGIONAL_DATASETS[region]

    default_args = {
        "owner": "data-platform",
        "retries": 3,
        "retry_delay": timedelta(minutes=5),
        "retry_exponential_backoff": True,
        "max_retry_delay": timedelta(minutes=30),
        "execution_timeout": timedelta(hours=2),
        "sla": timedelta(hours=3),
    }

    dag = DAG(
        dag_id=f"{region}_regional_etl",
        schedule=schedule,
        start_date=datetime(2024, 1, 1),
        catchup=False,
        default_args=default_args,
        tags=["regional", region, "producer"],
        doc_md=f"Regional ETL for {region}. Produces: {dataset.uri}",
    )

    with dag:
        def extract_data(region, **context):
            ds = context["ds"]
            logger.info(f"Extracting {region} data for {ds}")
            # In reality: Spark job submission
            return f"s3://uber-raw/{region}/{ds}/"

        def transform_data(region, **context):
            logger.info(f"Transforming {region} data")
            # In reality: dbt run or Spark transformation

        def validate_data(region, **context):
            logger.info(f"Validating {region} data quality")
            # In reality: Great Expectations or custom checks
            row_count = 1_000_000  # simulated
            if row_count < 100_000:
                raise ValueError(f"{region} data too small: {row_count} rows")

        def publish_data(region, **context):
            logger.info(f"Publishing {region} to warehouse")
            # In reality: COPY INTO or Spark write to warehouse

        extract = PythonOperator(
            task_id="extract",
            python_callable=extract_data,
            op_kwargs={"region": region},
        )

        transform = PythonOperator(
            task_id="transform",
            python_callable=transform_data,
            op_kwargs={"region": region},
        )

        validate = PythonOperator(
            task_id="validate",
            python_callable=validate_data,
            op_kwargs={"region": region},
        )

        publish = PythonOperator(
            task_id="publish_to_warehouse",
            python_callable=publish_data,
            op_kwargs={"region": region},
            outlets=[dataset],  # Signal dataset update
        )

        extract >> transform >> validate >> publish

    return dag


# Create all regional DAGs
# Staggered schedules based on timezone
REGION_SCHEDULES = {
    "us_east": "0 6 * * *",
    "us_west": "0 8 * * *",
    "eu_west": "0 4 * * *",
    "eu_central": "0 4 * * *",
    "apac_singapore": "0 22 * * *",  # Previous day UTC
    "apac_tokyo": "0 21 * * *",
    "apac_sydney": "0 20 * * *",
    "latam_brazil": "0 7 * * *",
    "latam_mexico": "0 8 * * *",
    "mena_uae": "0 2 * * *",
}

for region in REGIONS:
    globals()[f"{region}_etl_dag"] = create_regional_etl_dag(
        region, REGION_SCHEDULES[region]
    )

# ============================================================
# GLOBAL AGGREGATION DAG (Dataset-Triggered)
# ============================================================
with DAG(
    dag_id="global_trip_aggregation",
    schedule=list(REGIONAL_DATASETS.values()),  # Wait for ALL regions
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["global", "aggregation", "consumer", "producer"],
    default_args={
        "owner": "data-platform",
        "retries": 2,
        "retry_delay": timedelta(minutes=15),
        "execution_timeout": timedelta(hours=3),
    },
) as global_agg_dag:

    def merge_regions(**context):
        triggering_events = context["triggering_dataset_events"]
        logger.info(f"Triggered by {len(triggering_events)} dataset events")
        # Spark: read all regional tables, union, deduplicate

    def compute_global_kpis(**context):
        # Compute cross-region metrics: global GMV, trip counts, etc.
        pass

    def write_to_warehouse(**context):
        # Write final aggregated tables
        pass

    merge = PythonOperator(task_id="merge_all_regions", python_callable=merge_regions)
    kpis = PythonOperator(task_id="compute_global_kpis", python_callable=compute_global_kpis)
    write = PythonOperator(
        task_id="write_to_warehouse",
        python_callable=write_to_warehouse,
        outlets=[GLOBAL_DATASET],
    )

    merge >> kpis >> write

# ============================================================
# ALTERNATIVE: ExternalTaskSensor Approach (Legacy)
# ============================================================
with DAG(
    dag_id="global_aggregation_sensor_based",
    schedule="0 12 * * *",  # Cron-based, not dataset-triggered
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["global", "legacy", "sensor-based"],
) as sensor_dag:

    sensors = []
    for region in REGIONS:
        sensor = ExternalTaskSensor(
            task_id=f"wait_{region}",
            external_dag_id=f"{region}_regional_etl",
            external_task_id="publish_to_warehouse",
            mode="reschedule",
            timeout=7200,
            poke_interval=300,
            exponential_backoff=True,
            soft_fail=True,  # Don't block on slow regions
        )
        sensors.append(sensor)

    check_completion = BranchPythonOperator(
        task_id="check_completion_threshold",
        trigger_rule=TriggerRule.ALL_DONE,
        python_callable=lambda **ctx: (
            "proceed_aggregation"
            if sum(1 for s in sensors if s.state == "success") >= 8
            else "alert_incomplete"
        ),
    )

    proceed = EmptyOperator(task_id="proceed_aggregation")
    alert = PythonOperator(
        task_id="alert_incomplete",
        python_callable=lambda: logger.warning("Less than 80% regions completed"),
    )

    aggregate = PythonOperator(
        task_id="run_aggregation",
        trigger_rule=TriggerRule.NONE_FAILED_MIN_ONE_SUCCESS,
        python_callable=lambda: logger.info("Running global aggregation"),
    )

    sensors >> check_completion >> [proceed, alert]
    proceed >> aggregate
```

---

## Production Handling

### What Happens When One Region Is Slow

```
Scenario: APAC-Tokyo ETL runs 3 hours late due to source system issues.

WITH DATASETS (AND logic):
  - Global aggregation simply doesn't trigger
  - All other regions sit idle waiting
  - SLA breach at hour 4

WITH SENSORS + soft_fail:
  - Tokyo sensor times out → marked SKIPPED
  - trigger_rule=NONE_FAILED allows aggregation to proceed
  - Tokyo data backfilled in next run

RECOMMENDED PATTERN:
  - Use datasets for critical-path regions (US, EU)
  - Use a timeout-based gate for non-critical regions
  - Implement "partial aggregation" that can incorporate late data
```

### Timeout Escalation Strategy

```python
# In Airflow variables or config:
TIMEOUT_CONFIG = {
    "tier_1_regions": {"timeout": 7200, "soft_fail": False},   # US, EU - must complete
    "tier_2_regions": {"timeout": 5400, "soft_fail": True},    # APAC - best effort
    "tier_3_regions": {"timeout": 3600, "soft_fail": True},    # Emerging - optional
}
```

### DAG Dependency Visualization

Use `airflow dags show` or the Airflow UI's "Dataset" tab to see:
- Which DAGs produce which datasets
- Which DAGs consume which datasets
- Current state of dataset events
- Historical trigger timeline

```bash
# CLI: show dependency graph
airflow dags show global_trip_aggregation --save dependency_graph.png

# API: get dataset events
curl -X GET "http://airflow:8080/api/v1/datasets/events" \
  -H "Authorization: Bearer $TOKEN"
```

---

## Key Takeaways

1. **Datasets > Sensors** for new pipelines. Zero worker slots consumed, declarative, visible in UI.

2. **Sensors must use `mode='reschedule'`** or `deferrable=True`. A single `mode='poke'` sensor waiting 2 hours blocks a worker slot for 2 hours. At 70 regions, that's 70 blocked slots.

3. **Use `soft_fail=True` + `TriggerRule.NONE_FAILED`** for graceful degradation. One slow region shouldn't block the entire warehouse.

4. **Tier your regions**. Not all regions are equal. US/EU are P0 (hard fail), emerging markets are P2 (soft fail).

5. **Dataset AND-logic limitation** is real. For partial-completion semantics, combine a scheduled gate DAG with dataset triggers.

6. **TriggerDagRunOperator for fan-out**, datasets for fan-in. The aggregation layer fans-in (waits for all), the distribution layer fans-out (triggers many).

7. **Cross-DAG debugging** requires consistent `execution_date` alignment. Use `execution_delta` carefully when DAGs have different schedules.

8. **At 50,000+ tasks/day**, every wasted worker slot costs real money. Deferrable operators and datasets are not optional - they're survival.
