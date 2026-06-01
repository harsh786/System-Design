# Problem 9: Data Quality Validation Pipeline (Enterprise-Scale)

## The Problem

A data platform ingests from 200+ sources into a central data lake and warehouse. Bad data propagates silently—causing incorrect ML model predictions, wrong financial reports, broken executive dashboards, and compliance violations discovered weeks later.

**Requirements:**
- Validate data at EVERY stage: ingestion, transformation, serving
- Quality dimensions: completeness, freshness, uniqueness, referential integrity, schema conformance
- 10,000+ validation rules across all datasets
- Critical rules BLOCK the pipeline; warning rules ALERT only
- Custom operators encapsulate company-specific validation logic
- Rules evolve weekly as sources and schemas change
- Full test coverage of DAGs and custom operators

## Scale Numbers

| Metric | Target |
|--------|--------|
| Data sources | 200+ |
| Validation rules | 10,000+ |
| Daily ingestion | 50 TB |
| Quality score target | 99.5% |
| Validation overhead | < 10% of pipeline runtime |
| Rule change frequency | Weekly |
| Alert latency | < 2 minutes after detection |

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                    DATA QUALITY VALIDATION PIPELINE                   │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  ┌──────────┐    ┌──────────────┐    ┌──────────────┐               │
│  │  Source   │───▶│  Ingestion   │───▶│  Quality     │               │
│  │  200+     │    │  Layer       │    │  Gate #1     │               │
│  └──────────┘    └──────────────┘    └──────┬───────┘               │
│                                              │                        │
│                                    ┌─────────┴─────────┐             │
│                                    ▼                   ▼              │
│                              ┌──────────┐       ┌──────────┐         │
│                              │  BLOCK   │       │  ALERT   │         │
│                              │  (fail)  │       │  (warn)  │         │
│                              └──────────┘       └────┬─────┘         │
│                                                      ▼              │
│                                              ┌──────────────┐        │
│                                              │ Transform    │        │
│                                              │ Layer        │        │
│                                              └──────┬───────┘        │
│                                                     ▼               │
│                                              ┌──────────────┐        │
│                                              │ Quality      │        │
│                                              │ Gate #2      │        │
│                                              └──────┬───────┘        │
│                                                     ▼               │
│                                              ┌──────────────┐        │
│                                              │ Serving      │        │
│                                              │ Layer        │        │
│                                              └──────────────┘        │
│                                                                       │
│  ┌────────────────────────────────────────────────────────────┐      │
│  │  QUALITY DASHBOARD: scores, trends, rule pass/fail rates   │      │
│  └────────────────────────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────────────────────┘
```

## Airflow Concepts Taught

### 1. Custom Operators

**Why custom operators?** When validation logic is reused across 200+ sources with the same interface but different parameters, a custom operator encapsulates the pattern.

**Key concepts:**
- Inherit from `BaseOperator`
- Implement `execute(self, context)` — the only required method
- Declare `template_fields` for Jinja-rendered parameters
- Use `template_fields_renderers` for UI display formatting
- Package as a plugin or installable Python package

```python
"""
custom_operators/data_quality.py
Production DataQualityOperator - validates datasets against configurable rules.
"""
from airflow.models import BaseOperator
from airflow.utils.decorators import apply_defaults
from airflow.exceptions import AirflowFailException, AirflowSkipException
from typing import Any, Dict, List, Optional
import json
import time


class DataQualityOperator(BaseOperator):
    """
    Validates a dataset against a set of quality rules.
    
    Supports: completeness, freshness, uniqueness, schema, custom SQL checks.
    Behavior on failure controlled by `blocking` parameter.
    """

    template_fields = ("table", "partition_key", "rules_config", "ds")
    template_fields_renderers = {"rules_config": "json"}
    ui_color = "#4dc9f6"
    ui_fgcolor = "#000000"

    def __init__(
        self,
        table: str,
        rules_config: str,  # JSON string or path, templated
        conn_id: str = "warehouse_default",
        blocking: bool = True,
        quality_threshold: float = 0.95,
        partition_key: str = "{{ ds }}",
        ds: str = "{{ ds }}",
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.table = table
        self.rules_config = rules_config
        self.conn_id = conn_id
        self.blocking = blocking
        self.quality_threshold = quality_threshold
        self.partition_key = partition_key
        self.ds = ds

    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Run all validation rules and compute quality score."""
        rules = json.loads(self.rules_config)
        results = []
        start_time = time.time()

        for rule in rules:
            result = self._execute_rule(rule)
            results.append(result)
            self.log.info(
                f"Rule '{rule['name']}': {'PASS' if result['passed'] else 'FAIL'} "
                f"(value={result['actual_value']})"
            )

        # Compute quality score
        passed = sum(1 for r in results if r["passed"])
        quality_score = passed / len(results) if results else 1.0
        elapsed = time.time() - start_time

        summary = {
            "table": self.table,
            "partition": self.partition_key,
            "quality_score": quality_score,
            "rules_total": len(results),
            "rules_passed": passed,
            "rules_failed": len(results) - passed,
            "elapsed_seconds": elapsed,
            "results": results,
        }

        # Push to XCom for downstream decisions
        context["ti"].xcom_push(key="quality_summary", value=summary)

        # Decide: block or alert
        if quality_score < self.quality_threshold and self.blocking:
            failed_rules = [r for r in results if not r["passed"]]
            raise AirflowFailException(
                f"Quality score {quality_score:.3f} below threshold "
                f"{self.quality_threshold}. Failed rules: "
                f"{[r['rule_name'] for r in failed_rules]}"
            )

        return summary

    def _execute_rule(self, rule: Dict) -> Dict:
        """Execute a single validation rule."""
        rule_type = rule["type"]
        checker = getattr(self, f"_check_{rule_type}", None)
        if not checker:
            raise ValueError(f"Unknown rule type: {rule_type}")
        return checker(rule)

    def _check_completeness(self, rule: Dict) -> Dict:
        """Check null ratio for a column."""
        from airflow.providers.common.sql.hooks.sql import DbApiHook
        hook = DbApiHook.get_hook(self.conn_id)
        column = rule["column"]
        threshold = rule.get("threshold", 0.99)

        query = f"""
            SELECT 
                COUNT(*) as total,
                COUNT({column}) as non_null
            FROM {self.table}
            WHERE partition_date = '{self.partition_key}'
        """
        result = hook.get_first(query)
        ratio = result[1] / result[0] if result[0] > 0 else 0

        return {
            "rule_name": rule["name"],
            "rule_type": "completeness",
            "passed": ratio >= threshold,
            "actual_value": ratio,
            "threshold": threshold,
        }

    def _check_freshness(self, rule: Dict) -> Dict:
        """Check data is not stale."""
        from airflow.providers.common.sql.hooks.sql import DbApiHook
        hook = DbApiHook.get_hook(self.conn_id)
        timestamp_col = rule["timestamp_column"]
        max_delay_hours = rule.get("max_delay_hours", 24)

        query = f"""
            SELECT MAX({timestamp_col}) FROM {self.table}
            WHERE partition_date = '{self.partition_key}'
        """
        result = hook.get_first(query)
        from datetime import datetime, timezone, timedelta
        if result[0] is None:
            return {"rule_name": rule["name"], "rule_type": "freshness",
                    "passed": False, "actual_value": "NO DATA", "threshold": max_delay_hours}

        delay_hours = (datetime.now(timezone.utc) - result[0]).total_seconds() / 3600
        return {
            "rule_name": rule["name"],
            "rule_type": "freshness",
            "passed": delay_hours <= max_delay_hours,
            "actual_value": delay_hours,
            "threshold": max_delay_hours,
        }

    def _check_uniqueness(self, rule: Dict) -> Dict:
        """Check for duplicate values."""
        from airflow.providers.common.sql.hooks.sql import DbApiHook
        hook = DbApiHook.get_hook(self.conn_id)
        columns = rule["columns"]
        col_list = ", ".join(columns)

        query = f"""
            SELECT COUNT(*) - COUNT(DISTINCT {col_list})
            FROM {self.table}
            WHERE partition_date = '{self.partition_key}'
        """
        duplicates = hook.get_first(query)[0]
        return {
            "rule_name": rule["name"],
            "rule_type": "uniqueness",
            "passed": duplicates == 0,
            "actual_value": duplicates,
            "threshold": 0,
        }

    def _check_schema(self, rule: Dict) -> Dict:
        """Validate expected columns and types exist."""
        from airflow.providers.common.sql.hooks.sql import DbApiHook
        hook = DbApiHook.get_hook(self.conn_id)
        expected_columns = rule["expected_columns"]  # {"col": "type", ...}

        query = f"""
            SELECT column_name, data_type 
            FROM information_schema.columns
            WHERE table_name = '{self.table.split('.')[-1]}'
        """
        rows = hook.get_records(query)
        actual = {row[0]: row[1] for row in rows}
        missing = [c for c in expected_columns if c not in actual]

        return {
            "rule_name": rule["name"],
            "rule_type": "schema",
            "passed": len(missing) == 0,
            "actual_value": missing if missing else "all columns present",
            "threshold": "no missing columns",
        }
```

---

### 2. BranchPythonOperator & Branching

Branching lets the DAG choose different execution paths at runtime. The branch function returns the `task_id` (or list of task_ids) to follow; all other downstream paths are **skipped**.

```python
from airflow.decorators import dag, task
from airflow.operators.empty import EmptyOperator
from airflow.utils.trigger_rule import TriggerRule
from datetime import datetime


@dag(schedule="@daily", start_date=datetime(2024, 1, 1), catchup=False)
def quality_gate_dag():
    
    validate = DataQualityOperator(
        task_id="validate_orders",
        table="warehouse.orders",
        rules_config='{{ var.json.orders_quality_rules }}',
        blocking=False,  # Don't block here; let branch decide
        quality_threshold=0.95,
    )

    @task.branch
    def decide_quality_action(**context):
        """Branch based on quality score from validation."""
        ti = context["ti"]
        summary = ti.xcom_pull(task_ids="validate_orders", key="quality_summary")
        score = summary["quality_score"]
        
        if score >= 0.99:
            return "continue_pipeline"
        elif score >= 0.95:
            return ["continue_pipeline", "send_warning"]
        else:
            return "block_pipeline"

    continue_pipeline = EmptyOperator(task_id="continue_pipeline")
    send_warning = EmptyOperator(task_id="send_warning")
    block_pipeline = EmptyOperator(task_id="block_pipeline")

    # Join node after branch — uses trigger_rule to handle skipped upstreams
    join = EmptyOperator(
        task_id="join_after_branch",
        trigger_rule=TriggerRule.NONE_FAILED_MIN_ONE_SUCCESS,
    )

    validate >> decide_quality_action() >> [continue_pipeline, send_warning, block_pipeline]
    [continue_pipeline, send_warning] >> join


quality_gate_dag()
```

**Critical detail:** Tasks downstream of non-selected branches get state `skipped`. Use `trigger_rule=TriggerRule.NONE_FAILED_MIN_ONE_SUCCESS` on join nodes to proceed even when some upstreams are skipped.

---

### 3. ShortCircuitOperator

Unlike branching (which selects a path), ShortCircuitOperator skips ALL downstream tasks if its callable returns `False`.

```python
from airflow.decorators import task


@task.short_circuit
def check_data_exists(table: str, ds: str, **context):
    """Skip entire validation if partition has no data."""
    from airflow.providers.common.sql.hooks.sql import DbApiHook
    hook = DbApiHook.get_hook("warehouse_default")
    count = hook.get_first(
        f"SELECT COUNT(*) FROM {table} WHERE partition_date = '{ds}'"
    )[0]
    return count > 0  # False = short-circuit (skip all downstream)


# Usage in DAG:
# check_data_exists(table="warehouse.orders", ds="{{ ds }}") >> validate >> transform
```

**When to use ShortCircuit vs Branch:**
- ShortCircuit: "If condition is false, skip everything downstream"
- Branch: "Go down path A or path B based on condition"

---

### 4. Testing Airflow DAGs

#### DAG Validation Tests (run in CI)

```python
"""tests/test_dag_integrity.py"""
import pytest
from airflow.models import DagBag


@pytest.fixture(scope="session")
def dagbag():
    return DagBag(dag_folder="dags/", include_examples=False)


def test_no_import_errors(dagbag):
    """All DAGs must import without errors."""
    assert dagbag.import_errors == {}, f"Import errors: {dagbag.import_errors}"


def test_dag_ids_are_unique(dagbag):
    """No duplicate DAG IDs."""
    dag_ids = [dag.dag_id for dag in dagbag.dags.values()]
    assert len(dag_ids) == len(set(dag_ids))


def test_quality_dag_has_expected_tasks(dagbag):
    """Quality gate DAG has required task structure."""
    dag = dagbag.get_dag("quality_gate_dag")
    assert dag is not None
    task_ids = [t.task_id for t in dag.tasks]
    assert "validate_orders" in task_ids
    assert "decide_quality_action" in task_ids


def test_no_cycles(dagbag):
    """All DAGs are acyclic."""
    for dag_id, dag in dagbag.dags.items():
        # topological_sort raises if cycle exists
        assert dag.topological_sort()
```

#### Unit Testing Custom Operators

```python
"""tests/test_data_quality_operator.py"""
import pytest
import json
from unittest.mock import patch, MagicMock
from airflow.models import TaskInstance, DagRun
from airflow.utils.state import State
from airflow.exceptions import AirflowFailException
from custom_operators.data_quality import DataQualityOperator
from datetime import datetime


@pytest.fixture
def mock_context():
    """Create a mock Airflow task context."""
    ti = MagicMock(spec=TaskInstance)
    ti.xcom_push = MagicMock()
    return {
        "ti": ti,
        "ds": "2024-01-15",
        "execution_date": datetime(2024, 1, 15),
    }


@pytest.fixture
def completeness_rules():
    return json.dumps([
        {
            "name": "orders_amount_not_null",
            "type": "completeness",
            "column": "amount",
            "threshold": 0.99,
        }
    ])


class TestDataQualityOperator:

    @patch("custom_operators.data_quality.DbApiHook")
    def test_passes_when_quality_above_threshold(
        self, mock_hook_class, mock_context, completeness_rules
    ):
        """Operator succeeds when quality score meets threshold."""
        mock_hook = MagicMock()
        mock_hook.get_first.return_value = (1000, 998)  # 99.8% complete
        mock_hook_class.get_hook.return_value = mock_hook

        operator = DataQualityOperator(
            task_id="test_quality",
            table="warehouse.orders",
            rules_config=completeness_rules,
            quality_threshold=0.95,
            blocking=True,
        )

        result = operator.execute(mock_context)
        assert result["quality_score"] == 1.0
        assert result["rules_passed"] == 1

    @patch("custom_operators.data_quality.DbApiHook")
    def test_blocks_when_critical_rule_fails(
        self, mock_hook_class, mock_context, completeness_rules
    ):
        """Operator raises AirflowFailException when blocking and below threshold."""
        mock_hook = MagicMock()
        mock_hook.get_first.return_value = (1000, 500)  # 50% complete - bad
        mock_hook_class.get_hook.return_value = mock_hook

        operator = DataQualityOperator(
            task_id="test_quality",
            table="warehouse.orders",
            rules_config=completeness_rules,
            quality_threshold=0.95,
            blocking=True,
        )

        with pytest.raises(AirflowFailException, match="Quality score"):
            operator.execute(mock_context)

    @patch("custom_operators.data_quality.DbApiHook")
    def test_alerts_only_when_non_blocking(
        self, mock_hook_class, mock_context, completeness_rules
    ):
        """Non-blocking operator returns result even when below threshold."""
        mock_hook = MagicMock()
        mock_hook.get_first.return_value = (1000, 500)
        mock_hook_class.get_hook.return_value = mock_hook

        operator = DataQualityOperator(
            task_id="test_quality",
            table="warehouse.orders",
            rules_config=completeness_rules,
            quality_threshold=0.95,
            blocking=False,  # Alert only
        )

        result = operator.execute(mock_context)
        assert result["quality_score"] == 0.0  # Failed but didn't raise
        assert result["rules_failed"] == 1

    def test_template_fields_are_rendered(self):
        """Verify template_fields includes all templated params."""
        assert "table" in DataQualityOperator.template_fields
        assert "rules_config" in DataQualityOperator.template_fields
        assert "ds" in DataQualityOperator.template_fields
```

---

### 5. Custom Callbacks & Notifications

```python
"""callbacks/quality_callbacks.py"""
from airflow.models import TaskInstance
from typing import Dict, Any


def quality_failure_callback(context: Dict[str, Any]):
    """
    Called when a quality validation task fails.
    Routes notifications based on severity and publishes to quality dashboard.
    """
    ti: TaskInstance = context["ti"]
    dag_id = context["dag"].dag_id
    task_id = ti.task_id
    exception = context.get("exception")
    
    # Pull quality summary from XCom (if available before failure)
    summary = ti.xcom_pull(key="quality_summary") or {}
    
    # Determine severity
    score = summary.get("quality_score", 0)
    if score < 0.8:
        severity = "critical"
    elif score < 0.95:
        severity = "warning"
    else:
        severity = "info"

    # Publish to quality dashboard (e.g., via HTTP hook)
    _publish_to_dashboard(dag_id, task_id, summary, severity)
    
    # Route notification by severity
    if severity == "critical":
        _send_pagerduty(dag_id, task_id, summary)
        _send_slack(channel="#data-quality-critical", dag_id=dag_id, summary=summary)
    elif severity == "warning":
        _send_slack(channel="#data-quality-warnings", dag_id=dag_id, summary=summary)


def quality_sla_miss_callback(dag, task_list, blocking_task_list, slas, blocking_tis):
    """Called when quality validation exceeds its SLA (adds too much latency)."""
    _send_slack(
        channel="#data-platform-ops",
        dag_id=dag.dag_id,
        summary={"message": f"Quality validation SLA missed. Tasks: {task_list}"},
    )


def _publish_to_dashboard(dag_id, task_id, summary, severity):
    from airflow.providers.http.hooks.http import HttpHook
    hook = HttpHook(method="POST", http_conn_id="quality_dashboard")
    hook.run(
        endpoint="/api/v1/quality-events",
        json={
            "dag_id": dag_id,
            "task_id": task_id,
            "summary": summary,
            "severity": severity,
        },
    )


def _send_pagerduty(dag_id, task_id, summary):
    from airflow.providers.pagerduty.hooks.pagerduty import PagerdutyHook
    hook = PagerdutyHook(pagerduty_conn_id="pagerduty_default")
    hook.create_event(
        summary=f"Data quality CRITICAL: {dag_id}/{task_id} score={summary.get('quality_score', 'N/A')}",
        severity="critical",
        source="airflow-quality-pipeline",
    )


def _send_slack(channel, dag_id, summary):
    from airflow.providers.slack.hooks.slack_webhook import SlackWebhookHook
    hook = SlackWebhookHook(slack_webhook_conn_id="slack_quality")
    hook.send(text=f"[{dag_id}] Quality: {summary}")
```

---

## Production Implementation: Full DAG

```python
"""dags/data_quality_validation.py"""
from airflow.decorators import dag, task
from airflow.operators.empty import EmptyOperator
from airflow.utils.trigger_rule import TriggerRule
from custom_operators.data_quality import DataQualityOperator
from callbacks.quality_callbacks import quality_failure_callback
from datetime import datetime, timedelta
import json


# Configuration-driven: rules loaded from Variable or config file
SOURCES_CONFIG = {
    "orders": {
        "table": "warehouse.orders",
        "blocking": True,
        "threshold": 0.99,
        "rules": [
            {"name": "order_id_unique", "type": "uniqueness", "columns": ["order_id"]},
            {"name": "amount_not_null", "type": "completeness", "column": "amount", "threshold": 0.99},
            {"name": "data_fresh", "type": "freshness", "timestamp_column": "created_at", "max_delay_hours": 6},
        ],
    },
    "payments": {
        "table": "warehouse.payments",
        "blocking": True,
        "threshold": 0.995,
        "rules": [
            {"name": "payment_id_unique", "type": "uniqueness", "columns": ["payment_id"]},
            {"name": "amount_complete", "type": "completeness", "column": "amount", "threshold": 0.999},
            {"name": "status_complete", "type": "completeness", "column": "status", "threshold": 1.0},
        ],
    },
    "user_events": {
        "table": "lake.user_events",
        "blocking": False,  # Warning only — high volume, some loss acceptable
        "threshold": 0.95,
        "rules": [
            {"name": "event_id_unique", "type": "uniqueness", "columns": ["event_id"]},
            {"name": "user_id_complete", "type": "completeness", "column": "user_id", "threshold": 0.98},
        ],
    },
}


def create_validation_tasks(source_name: str, config: dict, dag_instance):
    """Factory: generates validation + branching tasks for one source."""
    
    validate = DataQualityOperator(
        task_id=f"validate_{source_name}",
        table=config["table"],
        rules_config=json.dumps(config["rules"]),
        blocking=False,  # Let branch handle blocking logic
        quality_threshold=config["threshold"],
        on_failure_callback=quality_failure_callback,
        execution_timeout=timedelta(minutes=15),
        dag=dag_instance,
    )

    @task.branch(task_id=f"branch_{source_name}")
    def branch_on_quality(source=source_name, **context):
        ti = context["ti"]
        summary = ti.xcom_pull(task_ids=f"validate_{source}", key="quality_summary")
        if summary is None:
            return f"block_{source}"
        
        score = summary["quality_score"]
        threshold = config["threshold"]
        
        if score >= threshold:
            return f"pass_{source}"
        elif config["blocking"]:
            return f"block_{source}"
        else:
            return f"warn_{source}"

    pass_task = EmptyOperator(task_id=f"pass_{source_name}", dag=dag_instance)
    warn_task = EmptyOperator(task_id=f"warn_{source_name}", dag=dag_instance)
    block_task = EmptyOperator(task_id=f"block_{source_name}", dag=dag_instance)

    join_task = EmptyOperator(
        task_id=f"join_{source_name}",
        trigger_rule=TriggerRule.NONE_FAILED_MIN_ONE_SUCCESS,
        dag=dag_instance,
    )

    branch = branch_on_quality()
    validate >> branch >> [pass_task, warn_task, block_task]
    [pass_task, warn_task] >> join_task

    return validate, join_task, block_task


@dag(
    dag_id="data_quality_validation",
    schedule="0 */2 * * *",  # Every 2 hours
    start_date=datetime(2024, 1, 1),
    catchup=False,
    default_args={
        "owner": "data-platform",
        "retries": 1,
        "retry_delay": timedelta(minutes=2),
    },
    tags=["data-quality", "platform"],
    max_active_runs=1,
)
def data_quality_validation():
    start = EmptyOperator(task_id="start")
    
    @task
    def compute_overall_score(**context):
        """Aggregate quality scores across all sources."""
        ti = context["ti"]
        scores = []
        for source_name in SOURCES_CONFIG:
            summary = ti.xcom_pull(
                task_ids=f"validate_{source_name}", key="quality_summary"
            )
            if summary:
                scores.append(summary["quality_score"])
        
        overall = sum(scores) / len(scores) if scores else 0
        context["ti"].xcom_push(key="overall_quality_score", value=overall)
        return {"overall_score": overall, "source_count": len(scores)}

    join_all = EmptyOperator(
        task_id="join_all",
        trigger_rule=TriggerRule.NONE_FAILED_MIN_ONE_SUCCESS,
    )

    score_task = compute_overall_score()
    end = EmptyOperator(task_id="end")

    # Wire up all sources
    join_tasks = []
    for source_name, config in SOURCES_CONFIG.items():
        validate, join_task, _ = create_validation_tasks(
            source_name, config, None  # dag auto-assigned via decorator
        )
        start >> validate
        join_tasks.append(join_task)

    join_tasks >> join_all >> score_task >> end


data_quality_validation()
```

---

## Production Handling

### Critical Rule Failure

When a blocking rule fails:
1. `AirflowFailException` raised → task marked `failed`
2. `on_failure_callback` fires → PagerDuty alert + Slack notification
3. Branch routes to `block_<source>` → downstream transforms skipped
4. On-call engineer investigates via quality dashboard
5. After fix: clear failed task, let it re-run (or trigger manually)

### Configuration-Driven Rule Evolution

Rules live in Airflow Variables or an external config store (S3/GCS JSON files). Adding a new rule requires zero DAG code changes:

```python
# Update via CLI or API — no deploy needed
airflow variables set orders_quality_rules '[{"name": "new_rule", "type": "completeness", ...}]'
```

### False Positive Management

```python
# Suppression config: temporarily mute known false positives
SUPPRESSED_RULES = {
    "user_events.event_id_unique": {
        "reason": "Known duplicate issue during migration, JIRA-1234",
        "expires": "2024-02-01",
    }
}
```

### Quality Score Trending

The `compute_overall_score` task pushes metrics that feed a time-series dashboard. Degradation below 99.5% over a 24-hour window triggers a separate alerting DAG.

---

## Key Takeaways

| Concept | When to Use |
|---------|-------------|
| Custom Operators | Reusable logic across many DAGs/tasks with same interface |
| `@task.branch` | Choose execution path at runtime based on data |
| `@task.short_circuit` | Skip all downstream if precondition fails |
| `trigger_rule=NONE_FAILED_MIN_ONE_SUCCESS` | Join node after branches (handles skipped states) |
| `AirflowFailException` | Intentional failure (won't retry) |
| `on_failure_callback` | React to failures with custom notification logic |
| `template_fields` | Make operator params Jinja-renderable |
| DagBag tests | CI validation of DAG structure and imports |
| Factory functions | Generate repetitive task patterns from config |
| Config-driven rules | Evolve validation without code deploys |
