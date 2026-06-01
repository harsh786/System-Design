# Problem 3: Real-Time Fraud Batch Aggregation (Banking-Scale)

## The Problem

A major bank processes **10B+ transaction events per day** across cards, wire transfers, ATMs, and online banking. Their real-time fraud detection system (Flink + Kafka) catches obvious fraud — stolen cards used in a different country, transactions exceeding limits.

But **sophisticated fraud requires batch aggregation**:
- "Did this card have 50 small charges across 10 countries in 24 hours?"
- "Is this merchant seeing a spike in chargebacks from cards issued in the same ZIP?"
- "Did 200 cards all hit the same ATM network within 6 hours with identical withdrawal patterns?"

These patterns are invisible in real-time stream processing because they require:
- **Cross-entity joins** (card ↔ merchant ↔ geo)
- **Window aggregations** over millions of entities
- **Historical baselines** for anomaly scoring

The bank has **500+ fraud rule aggregations** that must run every hour. Results feed back into the real-time Flink system as enrichment features — enabling real-time decisions based on batch-computed intelligence.

## Scale Numbers

| Metric | Value |
|--------|-------|
| Events per day | 10 Billion |
| Aggregation rules | 500+ |
| Batch frequency | Hourly micro-batch |
| Unique cards | 200 Million |
| Unique merchants | 15 Million |
| SLA | Complete within 45 minutes of hour boundary |
| Output features | ~2,000 enrichment signals |
| Data retention | 90-day sliding window |

## Architecture Diagram

```
                         REAL-TIME PATH
    ┌──────────┐    ┌──────────────┐    ┌──────────────┐
    │ Card/ATM │───▶│    Kafka     │───▶│    Flink     │──▶ Block/Allow
    │  Events  │    │  (raw txns)  │    │ (streaming)  │
    └──────────┘    └──────┬───────┘    └──────▲───────┘
                           │                    │
                           │ Mirror             │ Enrichment
                           ▼                    │ Features
                    ┌──────────────┐    ┌──────┴───────┐
                    │  S3 / HDFS   │    │ Feature Store │
                    │ (hourly land)│    │  (Redis/DDB)  │
                    └──────┬───────┘    └──────▲───────┘
                           │                    │
                    ───────┼── BATCH PATH ──────┼────────
                           │                    │
                    ┌──────▼───────┐    ┌──────┴───────┐
                    │   Airflow    │───▶│    Spark     │
                    │  (orchestr.) │    │ (500+ rules) │
                    └──────────────┘    └──────────────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
        ┌──────────┐ ┌──────────┐ ┌──────────┐
        │Card Rules│ │Geo Rules │ │Merchant  │
        │(150 aggs)│ │(120 aggs)│ │Rules(230)│
        └──────────┘ └──────────┘ └──────────┘
```

## Airflow Concepts Taught

---

### 1. Dynamic DAGs (CRITICAL for 500+ Rules)

With 500+ fraud rules, you cannot write 500 static task definitions. You need **dynamic generation**.

#### Factory Pattern for DAG Generation

```python
# dags/fraud_rule_factory.py
"""
Factory pattern: Generate DAGs from a rule configuration registry.
Each rule category gets its own DAG to isolate failures.
"""
import yaml
from pathlib import Path
from airflow import DAG
from airflow.decorators import task
from datetime import datetime, timedelta

RULES_CONFIG = Path("/opt/airflow/config/fraud_rules.yaml")

def load_rules():
    with open(RULES_CONFIG) as f:
        return yaml.safe_load(f)

def create_fraud_dag(category: str, rules: list[dict]) -> DAG:
    """Factory: creates one DAG per fraud rule category."""
    dag_id = f"fraud_agg_{category}"

    default_args = {
        "owner": "fraud-platform",
        "retries": 2,
        "retry_delay": timedelta(minutes=3),
        "execution_timeout": timedelta(minutes=40),
        "sla": timedelta(minutes=45),
    }

    dag = DAG(
        dag_id=dag_id,
        default_args=default_args,
        schedule_interval="@hourly",
        start_date=datetime(2024, 1, 1),
        catchup=False,
        max_active_runs=1,
        tags=["fraud", category, "hourly"],
    )

    return dag

# Generate DAGs dynamically
config = load_rules()
for category, rules in config["categories"].items():
    dag = create_fraud_dag(category, rules)
    globals()[dag.dag_id] = dag  # Register in Airflow's namespace
```

#### Rule Configuration (YAML-Driven)

```yaml
# config/fraud_rules.yaml
categories:
  card_velocity:
    priority: critical
    timeout_minutes: 30
    rules:
      - id: card_multi_country_24h
        sql_template: card_velocity_by_geo.sql
        params:
          window_hours: 24
          threshold: 5
          entity: card_id
      - id: card_rapid_small_charges
        sql_template: card_velocity_amount.sql
        params:
          window_hours: 6
          max_amount: 50
          min_count: 20
          entity: card_id

  geo_anomaly:
    priority: high
    timeout_minutes: 25
    rules:
      - id: impossible_travel
        sql_template: geo_impossible_travel.sql
        params:
          max_speed_kmh: 900
          window_hours: 12
      - id: geo_cluster_new_cards
        sql_template: geo_cluster_detection.sql
        params:
          cluster_radius_km: 5
          min_cards: 10
          window_hours: 6

  merchant_risk:
    priority: high
    timeout_minutes: 35
    rules:
      - id: merchant_chargeback_spike
        sql_template: merchant_chargeback_rate.sql
        params:
          baseline_days: 30
          spike_factor: 3.0
      - id: merchant_card_testing
        sql_template: merchant_small_auth_pattern.sql
        params:
          auth_amount_max: 1.00
          min_auths: 50
          window_hours: 2
```

#### Performance Implications of Dynamic DAGs

```python
# WRONG: Loading external service in DAG parsing (blocks scheduler)
# rules = fetch_from_database()  # DO NOT DO THIS

# RIGHT: Load from local file, cached
# The scheduler parses ALL DAG files every 30s by default.
# Dynamic DAGs must parse FAST (< 2 seconds).

# Tuning for 500+ rules:
# airflow.cfg
# [scheduler]
# min_file_process_interval = 60   # Don't reparse too often
# dag_dir_list_interval = 120      # Scan for new files less often
# parsing_processes = 4            # Parallel DAG parsing
```

---

### 2. TaskFlow API (Modern Pythonic Airflow)

The TaskFlow API (Airflow 2.0+) replaces verbose operator instantiation with Python decorators.

```python
# dags/fraud_agg_card_velocity.py
from airflow.decorators import dag, task, task_group
from airflow.models.param import Param
from datetime import datetime, timedelta
from typing import Any

@dag(
    schedule="@hourly",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    default_args={"retries": 2, "retry_delay": timedelta(minutes=2)},
    params={"force_full_refresh": Param(False, type="boolean")},
    tags=["fraud", "card_velocity"],
)
def fraud_agg_card_velocity():

    @task
    def determine_time_window(**context) -> dict:
        """Calculate the processing window for this run."""
        execution_date = context["data_interval_end"]
        return {
            "window_start": (execution_date - timedelta(hours=1)).isoformat(),
            "window_end": execution_date.isoformat(),
            "partition": execution_date.strftime("year=%Y/month=%m/day=%d/hour=%H"),
        }

    @task
    def count_source_events(window: dict) -> dict:
        """Validate source data landed before processing."""
        from utils.s3_client import count_objects
        count = count_objects(
            bucket="fraud-events-landing",
            prefix=f"raw/transactions/{window['partition']}/"
        )
        if count == 0:
            raise ValueError(f"No events found for {window['partition']}")
        return {"event_count": count, **window}

    @task.branch
    def check_data_quality(metadata: dict) -> str:
        """Branch based on data volume sanity check."""
        expected_min = 300_000_000  # 300M events/hour minimum
        if metadata["event_count"] < expected_min:
            return "alert_low_volume"
        return "run_aggregations"

    @task
    def alert_low_volume(metadata: dict):
        """Send PagerDuty alert for abnormally low data volume."""
        from utils.alerting import page
        page(
            severity="warning",
            message=f"Low event volume: {metadata['event_count']} (expected 300M+)",
        )

    @task(multiple_outputs=True)
    def run_aggregations(metadata: dict) -> dict:
        """Execute Spark aggregation job and return results metadata."""
        from utils.spark_submit import submit_job
        result = submit_job(
            job_name="card_velocity_aggregation",
            params={
                "window_start": metadata["window_start"],
                "window_end": metadata["window_end"],
                "rules_config": "s3://fraud-config/card_velocity_rules.yaml",
            }
        )
        return {
            "output_path": result["output_path"],
            "records_processed": result["records_processed"],
            "rules_computed": result["rules_computed"],
            "duration_seconds": result["duration_seconds"],
        }

    @task.short_circuit
    def validate_output(output_path: str, records_processed: int) -> bool:
        """Short-circuit if aggregation produced no results."""
        return records_processed > 0

    @task
    def publish_to_feature_store(output_path: str, rules_computed: int):
        """Push aggregation results to Redis feature store for real-time lookup."""
        from utils.feature_store import bulk_load
        bulk_load(
            source_path=output_path,
            store="redis-fraud-features",
            ttl_hours=2,
            key_prefix="card_velocity",
        )

    # Wire the DAG
    window = determine_time_window()
    metadata = count_source_events(window)
    branch = check_data_quality(metadata)
    alert_low_volume(metadata)
    agg_result = run_aggregations(metadata)
    valid = validate_output(agg_result["output_path"], agg_result["records_processed"])
    publish_to_feature_store(agg_result["output_path"], agg_result["rules_computed"])

fraud_agg_card_velocity()
```

---

### 3. XCom (Cross-Communication)

XCom passes metadata between tasks. At this scale, knowing what to pass is critical.

#### What to Put in XCom

```python
# GOOD: Small metadata, paths, counts
@task
def compute_aggregation() -> dict:
    return {
        "output_path": "s3://fraud-results/card_velocity/2024/01/15/13/",
        "record_count": 45_000_000,
        "rules_computed": 150,
        "max_score": 0.97,
        "duration_sec": 842,
    }
```

#### What NOT to Put in XCom

```python
# BAD: Never pass actual data through XCom
@task
def bad_example():
    import pandas as pd
    df = pd.read_parquet("s3://...")  # 45M rows
    return df.to_dict()  # THIS WILL KILL YOUR METADATA DB

# BAD: Large lists
@task
def also_bad():
    return list(range(10_000_000))  # Serialized to metadata DB = disaster
```

#### Custom XCom Backend (S3)

```python
# For results that are too large for the metadata DB but need task-to-task passing:
# airflow.cfg:
# [core]
# xcom_backend = utils.s3_xcom_backend.S3XComBackend

# utils/s3_xcom_backend.py
from airflow.models.xcom import BaseXCom
import json, boto3

class S3XComBackend(BaseXCom):
    """Store XCom values > 48KB in S3, keep reference in metadata DB."""

    PREFIX = "s3://airflow-xcom-store/"
    THRESHOLD = 48_000  # bytes

    @staticmethod
    def serialize_value(value, key=None, task_id=None, dag_id=None, run_id=None, **kwargs):
        serialized = json.dumps(value).encode()
        if len(serialized) > S3XComBackend.THRESHOLD:
            s3_key = f"{dag_id}/{run_id}/{task_id}/{key}.json"
            boto3.client("s3").put_object(
                Bucket="airflow-xcom-store", Key=s3_key, Body=serialized
            )
            return BaseXCom.serialize_value({"__s3_ref": s3_key})
        return BaseXCom.serialize_value(value)

    @staticmethod
    def deserialize_value(result):
        val = BaseXCom.deserialize_value(result)
        if isinstance(val, dict) and "__s3_ref" in val:
            obj = boto3.client("s3").get_object(
                Bucket="airflow-xcom-store", Key=val["__s3_ref"]
            )
            return json.loads(obj["Body"].read())
        return val
```

#### XCom in Templates

```python
# Access XCom in templated fields (Jinja):
spark_submit = SparkSubmitOperator(
    task_id="run_spark",
    application_args=[
        "--input", "{{ ti.xcom_pull(task_ids='determine_window', key='return_value')['partition'] }}",
        "--rules", "{{ ti.xcom_pull(task_ids='load_rules', key='active_rule_ids') }}",
    ],
)
```

---

### 4. Dynamic Task Mapping (expand)

This is the killer feature for 500+ fraud rules. Instead of creating 500 static tasks, you **dynamically expand** at runtime.

```python
from airflow.decorators import dag, task, task_group
from datetime import datetime, timedelta

@dag(
    schedule="@hourly",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["fraud", "dynamic"],
)
def fraud_dynamic_rule_execution():

    @task
    def load_active_rules() -> list[dict]:
        """Load rule definitions from config store."""
        import yaml
        with open("/opt/airflow/config/fraud_rules.yaml") as f:
            config = yaml.safe_load(f)

        rules = []
        for category, cat_config in config["categories"].items():
            for rule in cat_config["rules"]:
                rules.append({
                    "rule_id": rule["id"],
                    "category": category,
                    "sql_template": rule["sql_template"],
                    "params": rule["params"],
                    "priority": cat_config["priority"],
                    "timeout": cat_config["timeout_minutes"],
                })
        return rules  # Returns list — Airflow maps over it

    @task
    def determine_window() -> dict:
        from pendulum import now
        end = now().start_of("hour")
        start = end.subtract(hours=1)
        return {"start": start.isoformat(), "end": end.isoformat()}

    @task(
        max_active_tis_per_dag=50,  # Limit concurrent Spark jobs
        execution_timeout=timedelta(minutes=40),
        retries=2,
    )
    def execute_rule(rule: dict, window: dict) -> dict:
        """Execute a single fraud aggregation rule via Spark."""
        from utils.spark_submit import submit_job

        result = submit_job(
            job_name=f"fraud_rule_{rule['rule_id']}",
            params={
                "sql_template": rule["sql_template"],
                "rule_params": rule["params"],
                "window_start": window["start"],
                "window_end": window["end"],
            },
            timeout_minutes=rule["timeout"],
        )
        return {
            "rule_id": rule["rule_id"],
            "category": rule["category"],
            "output_path": result["output_path"],
            "records": result["records_processed"],
            "duration_sec": result["duration_seconds"],
            "status": "success",
        }

    @task
    def publish_results(results: list[dict]):
        """Bulk-publish all rule results to feature store."""
        from utils.feature_store import bulk_load_multi

        successful = [r for r in results if r["status"] == "success"]
        failed = [r for r in results if r["status"] != "success"]

        if failed:
            from utils.alerting import page
            page(severity="high", message=f"{len(failed)} fraud rules failed: {[r['rule_id'] for r in failed]}")

        bulk_load_multi(
            results=successful,
            store="redis-fraud-features",
            ttl_hours=2,
        )
        return {"published": len(successful), "failed": len(failed)}

    @task
    def record_metrics(results: list[dict], publish_status: dict):
        """Push execution metrics to monitoring."""
        from utils.metrics import push_gauge
        push_gauge("fraud.rules.executed", len(results))
        push_gauge("fraud.rules.published", publish_status["published"])
        push_gauge("fraud.rules.failed", publish_status["failed"])

        # Track individual rule performance
        for r in results:
            push_gauge(
                f"fraud.rule.duration_sec",
                r["duration_sec"],
                tags={"rule_id": r["rule_id"], "category": r["category"]},
            )

    # === DAG Wiring with Dynamic Task Mapping ===
    rules = load_active_rules()
    window = determine_window()

    # THIS IS THE KEY: .expand() creates one task instance per rule
    # .partial() provides the shared window argument
    rule_results = execute_rule.partial(window=window).expand(rule=rules)

    # Reduce: collect all mapped results
    pub_status = publish_results(rule_results)
    record_metrics(rule_results, pub_status)

fraud_dynamic_rule_execution()
```

#### How expand() Works Under the Hood

```
load_active_rules() returns: [{rule_1}, {rule_2}, ..., {rule_500}]

Airflow creates at runtime:
  execute_rule[0] → processes rule_1
  execute_rule[1] → processes rule_2
  ...
  execute_rule[499] → processes rule_500

Each is an independent task instance with its own:
  - retry count
  - execution timeout
  - log file
  - state (success/failed/running)

publish_results() receives the LIST of all 500 return values.
```

#### Controlling Mapped Task Parallelism

```python
# Method 1: max_active_tis_per_dag on the task
@task(max_active_tis_per_dag=50)
def execute_rule(rule, window): ...

# Method 2: Pool (shared resource limiting)
@task(pool="spark_cluster", pool_slots=1)
def execute_rule(rule, window): ...

# In Airflow UI or CLI, create pool:
# airflow pools set spark_cluster 50 "Spark cluster capacity"
```

---

### 5. TaskGroups

With 500+ tasks, the Airflow UI becomes unusable without organization.

```python
from airflow.decorators import dag, task, task_group
from datetime import datetime

@dag(schedule="@hourly", start_date=datetime(2024, 1, 1), catchup=False)
def fraud_agg_organized():

    @task_group(group_id="card_fraud")
    def card_fraud_rules(rules: list[dict], window: dict):
        """All card-related fraud aggregations."""

        @task_group(group_id="velocity")
        def velocity_checks(rules, window):
            @task
            def run_velocity_rule(rule: dict, window: dict):
                ...
            return run_velocity_rule.partial(window=window).expand(rule=rules)

        @task_group(group_id="amount_patterns")
        def amount_checks(rules, window):
            @task
            def run_amount_rule(rule: dict, window: dict):
                ...
            return run_amount_rule.partial(window=window).expand(rule=rules)

        vel_rules = [r for r in rules if "velocity" in r["rule_id"]]
        amt_rules = [r for r in rules if "amount" in r["rule_id"]]

        velocity_checks(vel_rules, window)
        amount_checks(amt_rules, window)

    @task_group(group_id="geo_fraud")
    def geo_fraud_rules(rules: list[dict], window: dict):
        """Geographic anomaly detection rules."""
        @task
        def run_geo_rule(rule: dict, window: dict):
            ...
        return run_geo_rule.partial(window=window).expand(rule=rules)

    @task_group(group_id="merchant_fraud")
    def merchant_fraud_rules(rules: list[dict], window: dict):
        """Merchant-level fraud pattern detection."""
        @task
        def run_merchant_rule(rule: dict, window: dict):
            ...
        return run_merchant_rule.partial(window=window).expand(rule=rules)

    # Main flow
    @task
    def load_and_categorize_rules() -> dict:
        import yaml
        with open("/opt/airflow/config/fraud_rules.yaml") as f:
            config = yaml.safe_load(f)
        categorized = {}
        for category, cat_config in config["categories"].items():
            categorized[category] = cat_config["rules"]
        return categorized

    @task
    def get_window() -> dict:
        from pendulum import now
        end = now().start_of("hour")
        return {"start": end.subtract(hours=1).isoformat(), "end": end.isoformat()}

    rules = load_and_categorize_rules()
    window = get_window()

    # Each group runs independently in the UI — collapsible, navigable
    card_fraud_rules(rules["card_velocity"], window)
    geo_fraud_rules(rules["geo_anomaly"], window)
    merchant_fraud_rules(rules["merchant_risk"], window)

fraud_agg_organized()
```

**UI Behavior:**
```
fraud_agg_organized (DAG)
├── load_and_categorize_rules
├── get_window
├── card_fraud (TaskGroup - collapsible)
│   ├── velocity (TaskGroup)
│   │   ├── run_velocity_rule[0] ✓
│   │   ├── run_velocity_rule[1] ✓
│   │   └── run_velocity_rule[2] running...
│   └── amount_patterns (TaskGroup)
│       ├── run_amount_rule[0] ✓
│       └── run_amount_rule[1] queued
├── geo_fraud (TaskGroup - collapsible)
│   ├── run_geo_rule[0] ✓
│   └── run_geo_rule[1] ✓
└── merchant_fraud (TaskGroup - collapsible)
    ├── run_merchant_rule[0] running...
    └── run_merchant_rule[1] queued
```

---

## Production Implementation (Full)

```python
# dags/fraud_batch_aggregation_production.py
"""
Production fraud batch aggregation DAG.
Runs hourly, executes 500+ rules via dynamic task mapping,
publishes results to feature store for real-time enrichment.
"""
from airflow.decorators import dag, task, task_group
from airflow.models.param import Param
from airflow.exceptions import AirflowSkipException
from datetime import datetime, timedelta
from typing import Any

DEFAULT_ARGS = {
    "owner": "fraud-platform",
    "retries": 2,
    "retry_delay": timedelta(minutes=2),
    "execution_timeout": timedelta(minutes=40),
    "sla": timedelta(minutes=45),
    "on_failure_callback": "utils.callbacks.fraud_rule_failure_handler",
}

@dag(
    dag_id="fraud_batch_aggregation_v2",
    schedule="5 * * * *",  # 5 minutes past each hour
    start_date=datetime(2024, 1, 1),
    catchup=False,
    max_active_runs=1,
    default_args=DEFAULT_ARGS,
    params={
        "rule_filter": Param(None, type=["null", "string"], description="Run only rules matching this prefix"),
        "force_reprocess": Param(False, type="boolean"),
        "dry_run": Param(False, type="boolean"),
    },
    tags=["fraud", "production", "hourly", "critical"],
)
def fraud_batch_aggregation_v2():

    @task
    def compute_window(**context) -> dict:
        """Determine processing window aligned to hour boundary."""
        from pendulum import instance
        logical_date = instance(context["data_interval_end"])
        window_end = logical_date.start_of("hour")
        window_start = window_end.subtract(hours=1)
        return {
            "start": window_start.isoformat(),
            "end": window_end.isoformat(),
            "partition_path": window_end.format("YYYY/MM/DD/HH"),
            "run_id": context["run_id"],
        }

    @task
    def validate_source_data(window: dict) -> dict:
        """Ensure landing zone has data before proceeding."""
        from utils.s3_client import count_objects, get_total_size_gb

        path = f"raw/transactions/{window['partition_path']}/"
        file_count = count_objects("fraud-events-landing", path)
        size_gb = get_total_size_gb("fraud-events-landing", path)

        if file_count == 0:
            raise ValueError(f"No source data at {path}")

        return {
            **window,
            "source_files": file_count,
            "source_size_gb": size_gb,
        }

    @task
    def load_rules(**context) -> list[dict]:
        """Load active fraud rules, applying any filters from params."""
        import yaml
        rule_filter = context["params"].get("rule_filter")

        with open("/opt/airflow/config/fraud_rules.yaml") as f:
            config = yaml.safe_load(f)

        rules = []
        for category, cat_config in config["categories"].items():
            for rule in cat_config["rules"]:
                if rule.get("enabled", True):
                    rules.append({
                        "rule_id": rule["id"],
                        "category": category,
                        "priority": cat_config["priority"],
                        "sql_template": rule["sql_template"],
                        "params": rule["params"],
                        "timeout_minutes": cat_config["timeout_minutes"],
                        "version": rule.get("version", "1.0"),
                    })

        if rule_filter:
            rules = [r for r in rules if r["rule_id"].startswith(rule_filter)]

        return rules

    @task(
        pool="spark_fraud_pool",
        pool_slots=1,
        max_active_tis_per_dag=40,
        retries=3,
        retry_delay=timedelta(minutes=1),
    )
    def execute_single_rule(rule: dict, window_meta: dict, **context) -> dict:
        """Execute one fraud rule as a Spark job."""
        import time
        from utils.spark_submit import submit_job
        from utils.metrics import push_timer

        dry_run = context["params"].get("dry_run", False)
        if dry_run:
            return {"rule_id": rule["rule_id"], "status": "skipped_dry_run", "records": 0, "output_path": "", "duration_sec": 0}

        start = time.time()
        try:
            result = submit_job(
                job_name=f"fraud_{rule['rule_id']}_v{rule['version']}",
                main_class="com.bank.fraud.RuleAggregator",
                params={
                    "rule_id": rule["rule_id"],
                    "sql_template": f"s3://fraud-config/sql/{rule['sql_template']}",
                    "rule_params": rule["params"],
                    "window_start": window_meta["start"],
                    "window_end": window_meta["end"],
                    "output_base": f"s3://fraud-results/{rule['category']}/{rule['rule_id']}/{window_meta['partition_path']}/",
                },
                timeout_minutes=rule["timeout_minutes"],
                spark_conf={
                    "spark.sql.shuffle.partitions": "200",
                    "spark.executor.instances": "20",
                    "spark.executor.memory": "8g",
                },
            )
            duration = time.time() - start
            push_timer("fraud.rule.execution_time", duration, tags={"rule": rule["rule_id"]})

            return {
                "rule_id": rule["rule_id"],
                "category": rule["category"],
                "status": "success",
                "output_path": result["output_path"],
                "records": result["records_processed"],
                "duration_sec": int(duration),
                "version": rule["version"],
            }
        except Exception as e:
            duration = time.time() - start
            return {
                "rule_id": rule["rule_id"],
                "category": rule["category"],
                "status": "failed",
                "error": str(e)[:500],
                "output_path": "",
                "records": 0,
                "duration_sec": int(duration),
                "version": rule["version"],
            }

    @task
    def aggregate_results(results: list[dict]) -> dict:
        """Summarize execution across all rules."""
        successful = [r for r in results if r["status"] == "success"]
        failed = [r for r in results if r["status"] == "failed"]
        skipped = [r for r in results if r["status"] == "skipped_dry_run"]

        summary = {
            "total": len(results),
            "successful": len(successful),
            "failed": len(failed),
            "skipped": len(skipped),
            "total_records": sum(r["records"] for r in successful),
            "avg_duration_sec": sum(r["duration_sec"] for r in successful) / max(len(successful), 1),
            "failed_rules": [r["rule_id"] for r in failed],
            "successful_paths": [r["output_path"] for r in successful if r["output_path"]],
        }
        return summary

    @task
    def publish_to_feature_store(results: list[dict]):
        """Bulk-load successful rule outputs into Redis for real-time enrichment."""
        from utils.feature_store import bulk_load_multi

        successful = [r for r in results if r["status"] == "success"]
        if not successful:
            raise AirflowSkipException("No successful results to publish")

        bulk_load_multi(
            results=successful,
            store="redis-fraud-features",
            ttl_hours=2,
            batch_size=10_000,
        )

    @task
    def alert_on_failures(summary: dict, **context):
        """Alert if critical rules failed."""
        from utils.alerting import page, notify_slack

        if summary["failed"] > 0:
            notify_slack(
                channel="#fraud-platform-alerts",
                message=f"⚠️ {summary['failed']}/{summary['total']} fraud rules failed: {summary['failed_rules'][:10]}",
            )

        # Page if > 10% failure rate
        failure_rate = summary["failed"] / max(summary["total"], 1)
        if failure_rate > 0.10:
            page(
                severity="critical",
                message=f"Fraud aggregation {failure_rate:.0%} failure rate ({summary['failed']}/{summary['total']})",
                runbook="https://wiki.internal/fraud-agg-runbook",
            )

    @task
    def emit_completion_metrics(summary: dict):
        """Push final metrics for dashboarding."""
        from utils.metrics import push_gauge, push_event
        push_gauge("fraud.batch.rules_successful", summary["successful"])
        push_gauge("fraud.batch.rules_failed", summary["failed"])
        push_gauge("fraud.batch.total_records", summary["total_records"])
        push_gauge("fraud.batch.avg_rule_duration_sec", summary["avg_duration_sec"])
        push_event("fraud.batch.completed", tags={"status": "success" if summary["failed"] == 0 else "partial"})

    # === DAG Assembly ===
    window = compute_window()
    validated = validate_source_data(window)
    rules = load_rules()

    # Dynamic expansion: one task per rule
    rule_results = execute_single_rule.partial(window_meta=validated).expand(rule=rules)

    # Post-processing
    summary = aggregate_results(rule_results)
    publish_to_feature_store(rule_results)
    alert_on_failures(summary)
    emit_completion_metrics(summary)

fraud_batch_aggregation_v2()
```

---

## Production Handling

### What Happens When One Rule Takes Too Long

```python
# Each mapped task has independent execution_timeout.
# If rule X times out:
# 1. That specific mapped instance fails
# 2. It retries (retries=3)
# 3. Other rules continue unaffected
# 4. publish_to_feature_store still runs with partial results
# 5. alert_on_failures catches it

# For known slow rules, override timeout per-rule:
@task(execution_timeout=timedelta(minutes=40))
def execute_single_rule(rule: dict, window_meta: dict, **context):
    from airflow.exceptions import AirflowTaskTimeout
    # Dynamic timeout from rule config:
    import signal
    signal.alarm(rule["timeout_minutes"] * 60)
    ...
```

### Handling Rule Configuration Changes

```python
# Rules are loaded at RUNTIME (inside a task), not at parse time.
# This means:
# 1. Add new rule to YAML → next hourly run picks it up automatically
# 2. Disable a rule (enabled: false) → next run skips it
# 3. No DAG redeploy needed for rule changes

# For breaking changes, version the rules:
# rule_id: card_multi_country_24h
# version: "2.1"
# This flows through to Spark job selection and output paths
```

### A/B Testing New Fraud Rules

```python
@task
def load_rules(**context) -> list[dict]:
    """Support A/B testing via rule config."""
    rules = load_from_yaml()

    # A/B rules run in shadow mode — compute but don't publish
    for rule in rules:
        if rule.get("ab_test", False):
            rule["shadow_mode"] = True
    return rules

@task
def execute_single_rule(rule: dict, window_meta: dict, **context) -> dict:
    result = run_spark_job(rule, window_meta)
    result["shadow_mode"] = rule.get("shadow_mode", False)
    return result

@task
def publish_to_feature_store(results: list[dict]):
    # Only publish non-shadow results to production store
    production_results = [r for r in results if not r.get("shadow_mode")]
    shadow_results = [r for r in results if r.get("shadow_mode")]

    bulk_load(production_results, store="redis-fraud-features")
    # Shadow results go to analysis store for comparison
    bulk_load(shadow_results, store="s3-fraud-ab-analysis")
```

### Performance Monitoring Per Rule

```python
# Grafana dashboard query (PromQL):
# fraud_rule_duration_seconds{rule_id="card_multi_country_24h"} > 1800

# Airflow SLA miss callback:
def sla_miss_callback(dag, task_list, blocking_task_list, slas, blocking_tis):
    """Triggered when any task exceeds its SLA."""
    from utils.alerting import page
    for ti in blocking_tis:
        page(
            severity="high",
            message=f"SLA miss: {ti.task_id} in {dag.dag_id} (>{ti.task.sla})",
        )
```

---

## Key Takeaways

| Concept | When to Use | Banking Example |
|---------|-------------|-----------------|
| **Dynamic DAGs** | Rule count changes without deploys | 500 rules from YAML config |
| **TaskFlow API** | Clean Python-native DAG authoring | Type-safe XCom, readable flow |
| **XCom** | Pass metadata (not data) between tasks | Paths, counts, status |
| **Dynamic Task Mapping** | Runtime parallelism over variable-length inputs | `.expand(rule=rules)` |
| **TaskGroups** | Visual organization of large DAGs | card/geo/merchant grouping |

**Critical Production Patterns:**
1. **Never block the scheduler** — parse DAGs fast, load config in tasks
2. **Pool-limit Spark jobs** — 40 concurrent max prevents cluster overload
3. **Independent failure** — one rule failing cannot block others
4. **Shadow mode** — test new rules without affecting production scoring
5. **Metrics per rule** — detect degradation before SLA breach
6. **Hourly alignment** — `5 * * * *` gives landing zone 5 minutes to finalize
