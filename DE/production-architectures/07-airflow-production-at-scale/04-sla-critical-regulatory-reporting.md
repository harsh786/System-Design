# Problem 4: SLA-Critical Regulatory Reporting (Finance-Scale)

## The Problem

A major bank must submit daily regulatory reports to the Federal Reserve and ECB by strict deadlines. The consequences of failure are not "the dashboard is stale" — they are seven-figure fines and potential regulatory action.

- **SOX compliance**: every data transformation must have an immutable audit trail
- **Basel III**: risk calculations must use T-1 (previous business day) end-of-day positions exactly
- **Missing deadline = $1M+ fine per occurrence** — some reports carry $5M penalties
- **Multiple reports with different deadlines** throughout the day (7:00 AM, 9:00 AM, 2:00 PM)
- **Complete lineage and reproducibility**: regulators can ask "show me exactly how you computed this number" years later

This is the environment where Airflow's SLA, callback, priority, and timeout features stop being "nice to have" and become the difference between a normal day and a crisis.

---

## Scale Numbers

| Metric | Value |
|--------|-------|
| Regulatory reports with hard deadlines | 15 |
| Fine per missed deadline | $1M - $5M |
| Position records processed | 100M+ |
| Source systems feeding the pipeline | 50+ |
| Processing window | 2:00 AM - 7:00 AM (5 hours) |
| Tolerance for delay | Zero |
| Audit retention period | 7 years |
| Concurrent report pipelines | 8-12 |

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        REGULATORY REPORTING PIPELINE                      │
│                                                                          │
│  02:00 AM                                                   07:00 AM     │
│  ┌──────┐    ┌──────────┐    ┌────────────┐    ┌────────┐  ┌────────┐  │
│  │Source│───▶│Validation│───▶│Risk Calcs  │───▶│Report  │─▶│Submit  │  │
│  │Ingest│    │& Recon   │    │(Basel III) │    │Generate│  │to Fed  │  │
│  └──────┘    └──────────┘    └────────────┘    └────────┘  └────────┘  │
│     │             │                │                │           │        │
│     ▼             ▼                ▼                ▼           ▼        │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │              IMMUTABLE AUDIT LOG (SOX Compliance)                  │   │
│  │  Every transformation, row count, checksum, timestamp logged      │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                                                          │
│  ┌─────────────────────── MONITORING LAYER ──────────────────────────┐  │
│  │                                                                    │  │
│  │  SLA Monitor ──▶ 80% time warning ──▶ PagerDuty ──▶ War Room     │  │
│  │                                                                    │  │
│  │  [02:00]─────[03:30]──────[05:00]──────[06:00]──────[07:00]      │  │
│  │  Start    Checkpoint1   Checkpoint2   WARNING      DEADLINE       │  │
│  │                                        ▲                          │  │
│  │                                        │                          │  │
│  │                              Auto-escalation                      │  │
│  │                              if behind schedule                   │  │
│  └────────────────────────────────────────────────────────────────────┘  │
│                                                                          │
│  ┌──────────── QUEUE ARCHITECTURE ────────────────┐                     │
│  │  critical_queue ──▶ Dedicated 16-core workers  │                     │
│  │  standard_queue ──▶ Shared pool workers        │                     │
│  │  validation_queue ─▶ Memory-optimized workers  │                     │
│  └────────────────────────────────────────────────┘                     │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Airflow Concepts Taught

### 1. SLA Monitoring

The `sla` parameter defines the **maximum expected duration** from the DAG's `execution_date` (logical date) — not from when the task starts. This is a critical distinction.

```python
from datetime import timedelta

task = PythonOperator(
    task_id='generate_capital_report',
    python_callable=generate_report,
    # SLA = max time from execution_date start to task completion
    sla=timedelta(hours=4, minutes=30),  # Must finish by 4.5h after scheduled start
)
```

**SLA vs execution_timeout — they are different:**

| Feature | `sla` | `execution_timeout` |
|---------|--------|---------------------|
| What it measures | Time from execution_date to task completion | Time for a single task attempt |
| What happens on breach | Callback fires, logged in `sla_miss` table | Task is **killed** with `AirflowTaskTimeout` |
| Kills the task? | **No** — it's informational | **Yes** |
| Use case | Alerting, compliance tracking | Preventing runaway tasks |

**SLA miss callback:**

```python
def sla_miss_callback(dag, task_list, blocking_task_list, slas, blocking_tis):
    """
    Called when ANY task in the DAG misses its SLA.
    
    Args:
        dag: The DAG object
        task_list: Tasks that missed SLA
        blocking_task_list: Tasks blocking the SLA-missed tasks
        slas: List of SlaMiss objects
        blocking_tis: TaskInstances of blocking tasks
    """
    missed_tasks = [str(t) for t in task_list]
    blocking = [str(t) for t in blocking_task_list]
    
    alert_payload = {
        "severity": "P1",
        "dag_id": dag.dag_id,
        "missed_tasks": missed_tasks,
        "blocking_tasks": blocking,
        "timestamp": datetime.utcnow().isoformat(),
    }
    
    # Immediate PagerDuty escalation for regulatory SLA
    pagerduty_trigger_incident(alert_payload)
    
    # Audit log for compliance
    write_audit_event("SLA_BREACH", alert_payload)
```

**How SLA tracking works internally:**
1. The scheduler checks `sla_miss` conditions after each task completion
2. SLA is measured from `execution_date + sla_timedelta`
3. Misses are stored in the `sla_miss` table in the metadata DB
4. The `sla_miss_callback` is called on the **DAG level**, not per-task

---

### 2. Callbacks (Full Lifecycle)

Airflow provides callbacks at every stage of task and DAG execution:

```python
from airflow.models import TaskInstance, DagRun

# ─── CALLBACK FUNCTIONS ───────────────────────────────────────────

def on_success(context: dict):
    """Fires after task succeeds."""
    ti: TaskInstance = context['ti']
    write_audit_log(
        event="TASK_SUCCESS",
        task_id=ti.task_id,
        dag_id=ti.dag_id,
        execution_date=context['execution_date'],
        duration=ti.duration,
    )

def on_failure(context: dict):
    """Fires after task fails (all retries exhausted)."""
    ti: TaskInstance = context['ti']
    exception = context.get('exception')
    
    # Determine severity based on task criticality
    severity = "P1" if ti.task_id in CRITICAL_TASKS else "P2"
    
    send_pagerduty_alert(
        severity=severity,
        summary=f"[REGULATORY] {ti.task_id} FAILED in {ti.dag_id}",
        details={
            "exception": str(exception),
            "log_url": ti.log_url,
            "try_number": ti.try_number,
        }
    )

def on_retry(context: dict):
    """Fires before each retry attempt."""
    ti: TaskInstance = context['ti']
    attempt = ti.try_number
    max_retries = ti.max_tries
    
    # If this is the last retry, pre-alert the on-call
    if attempt >= max_retries - 1:
        send_slack_alert(
            channel="#regulatory-ops",
            text=f":warning: {ti.task_id} on FINAL retry ({attempt}/{max_retries}). "
                 f"Failure will trigger P1 escalation.",
        )

def on_execute(context: dict):
    """Fires when task begins execution (before the callable runs)."""
    ti: TaskInstance = context['ti']
    write_audit_log(
        event="TASK_START",
        task_id=ti.task_id,
        start_time=datetime.utcnow().isoformat(),
        worker=ti.hostname,
    )

# ─── APPLYING CALLBACKS ───────────────────────────────────────────

# Task-level callbacks
task = PythonOperator(
    task_id='calculate_risk_weights',
    python_callable=calculate_risk_weights,
    on_success_callback=on_success,
    on_failure_callback=on_failure,
    on_retry_callback=on_retry,
    on_execute_callback=on_execute,
)

# DAG-level callbacks (apply to ALL tasks as defaults)
dag = DAG(
    'regulatory_reporting',
    default_args={
        'on_success_callback': on_success,
        'on_failure_callback': on_failure,
        'on_retry_callback': on_retry,
    },
    sla_miss_callback=sla_miss_callback,  # DAG-level only
)
```

**DAG-level vs task-level:** Task-level callbacks override DAG-level defaults. Use DAG-level for audit logging (you want it everywhere) and task-level for specific escalation behavior.

---

### 3. Priority & Queues

When you have 15 regulatory reports competing for workers, **priority_weight** determines who runs first:

```python
# Higher number = higher priority (runs first when resources are constrained)

submit_to_fed = PythonOperator(
    task_id='submit_to_federal_reserve',
    python_callable=submit_report,
    priority_weight=100,  # Highest priority — this is the final submission
    queue='critical_queue',  # Route to dedicated workers
)

risk_calculation = PythonOperator(
    task_id='risk_weight_calculation',
    python_callable=calculate_rwa,
    priority_weight=80,
    queue='critical_queue',
)

data_validation = PythonOperator(
    task_id='validate_positions',
    python_callable=validate,
    priority_weight=50,
    queue='validation_queue',
)
```

**weight_rule determines how priority propagates:**

| Rule | Behavior |
|------|----------|
| `downstream` (default) | Task priority = own weight + sum of all downstream weights |
| `upstream` | Task priority = own weight + sum of all upstream weights |
| `absolute` | Task priority = exactly its own weight, no propagation |

```python
# With downstream rule, early tasks inherit the urgency of what depends on them
dag = DAG(
    'fed_capital_report',
    default_args={'weight_rule': 'downstream'},
)
# Now the first task (data ingest) gets priority = its weight + all downstream weights
# This ensures the critical path gets resources first
```

**Queue-based worker specialization:**

```ini
# Worker 1-4: celery config (or kubernetes executor pod template)
# Dedicated to regulatory workloads
[celery]
worker_queues = critical_queue

# Worker 5-10: shared pool
[celery]  
worker_queues = standard_queue,validation_queue
```

---

### 4. Timeout Management

```python
from datetime import timedelta

task = PythonOperator(
    task_id='generate_lcr_report',
    python_callable=generate_lcr,
    
    # Task is KILLED if a single attempt exceeds this
    execution_timeout=timedelta(minutes=45),
    
    # SLA breach notification (does NOT kill the task)
    sla=timedelta(hours=3),
)

dag = DAG(
    'liquidity_coverage_ratio',
    
    # Entire DAG run is marked failed if it exceeds this
    dagrun_timeout=timedelta(hours=4, minutes=45),
    
    schedule_interval='0 2 * * *',  # 2 AM daily
)
```

**Sensor timeout — a common trap:**

```python
wait_for_positions = ExternalTaskSensor(
    task_id='wait_for_eod_positions',
    external_dag_id='position_close',
    external_task_id='final_snapshot',
    
    timeout=3600,          # Total time to wait (seconds) before FAILING
    poke_interval=60,      # Check every 60 seconds
    mode='reschedule',     # Release worker slot between pokes (critical for pools!)
    
    # Soft fail = mark as skipped instead of failed (use for optional dependencies)
    soft_fail=False,       # For regulatory: NEVER soft_fail, we need hard failure
)
```

**Graceful timeout handling with cleanup:**

```python
def generate_report_with_cleanup(**context):
    temp_files = []
    try:
        temp_files = prepare_temp_data()
        result = compute_report(temp_files)
        return result
    except AirflowTaskTimeout:
        # Cleanup before dying — don't leave partial state
        cleanup_temp_files(temp_files)
        write_audit_log("TASK_TIMEOUT", context['ti'].task_id)
        raise  # Re-raise so Airflow marks it failed

task = PythonOperator(
    task_id='generate_report',
    python_callable=generate_report_with_cleanup,
    execution_timeout=timedelta(minutes=30),
    on_failure_callback=on_failure,  # This fires AFTER timeout kills the task
)
```

---

### 5. on_failure_callback & Alerting

Building a production escalation chain:

```python
import time
from enum import Enum

class Severity(Enum):
    P1_REGULATORY = "P1"  # Regulatory deadline at risk
    P2_CRITICAL = "P2"    # Critical but has buffer
    P3_WARNING = "P3"     # Needs attention, not urgent

def build_failure_callback(severity: Severity, report_name: str):
    """Factory that creates context-aware failure callbacks."""
    
    def callback(context: dict):
        ti = context['ti']
        exception = context.get('exception')
        dag_run = context['dag_run']
        
        elapsed = (datetime.utcnow() - dag_run.start_date).total_seconds() / 3600
        deadline_hours = 5.0  # 7 AM - 2 AM = 5 hours
        time_remaining = deadline_hours - elapsed
        
        alert_context = {
            "report": report_name,
            "task": ti.task_id,
            "error": str(exception)[:500],
            "attempt": ti.try_number,
            "time_remaining_hours": round(time_remaining, 2),
            "log_url": ti.log_url,
            "severity": severity.value,
        }
        
        # 1. Always: immutable audit log
        write_compliance_audit(alert_context)
        
        # 2. Always: Slack notification
        send_slack_alert(
            channel="#regulatory-ops",
            blocks=format_rich_slack_blocks(alert_context),
        )
        
        # 3. P1/P2: PagerDuty
        if severity in (Severity.P1_REGULATORY, Severity.P2_CRITICAL):
            pagerduty_trigger(alert_context)
        
        # 4. P1 with <1h remaining: activate war room
        if severity == Severity.P1_REGULATORY and time_remaining < 1.0:
            activate_war_room(alert_context)
            notify_regulatory_liaison(alert_context)
    
    return callback
```

---

## Production Implementation

```python
"""
regulatory_reporting_dag.py

Production DAG for Federal Reserve daily capital adequacy reports.
Demonstrates: SLAs, callbacks, priorities, timeouts, audit trail.
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.sensors.external_task import ExternalTaskSensor
from airflow.models import Variable
from airflow.exceptions import AirflowTaskTimeout

# ─── CONFIGURATION ────────────────────────────────────────────────

REPORT_DEADLINE = "07:00"  # Must submit by 7 AM ET
PROCESSING_START = "02:00"
TOTAL_WINDOW_HOURS = 5.0
WARNING_THRESHOLD = 0.80  # Alert at 80% of window consumed

CRITICAL_TASKS = [
    'submit_to_federal_reserve',
    'generate_capital_report',
    'calculate_risk_weighted_assets',
]

# ─── AUDIT TRAIL (SOX Compliance) ─────────────────────────────────

class ComplianceAuditLogger:
    """Immutable audit logger for SOX/regulatory compliance."""
    
    def __init__(self, report_id: str):
        self.report_id = report_id
        self.session_id = f"{report_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
    
    def log_event(self, event_type: str, details: dict):
        """Write immutable audit event to append-only store."""
        record = {
            "session_id": self.session_id,
            "report_id": self.report_id,
            "event_type": event_type,
            "timestamp": datetime.utcnow().isoformat(),
            "details": details,
            "checksum": self._compute_checksum(details),
        }
        # Write to immutable store (e.g., AWS QLDB, append-only Postgres, blockchain)
        write_to_immutable_ledger(record)
        return record
    
    def _compute_checksum(self, data: dict) -> str:
        import hashlib, json
        return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()


audit = ComplianceAuditLogger(report_id="FED_FR_Y14Q")

# ─── CALLBACKS ─────────────────────────────────────────────────────

def regulatory_sla_miss_callback(dag, task_list, blocking_task_list, slas, blocking_tis):
    """DAG-level SLA miss — immediate P1 escalation."""
    missed = [str(t) for t in task_list]
    
    audit.log_event("SLA_BREACH", {
        "missed_tasks": missed,
        "blocking_tasks": [str(t) for t in blocking_task_list],
    })
    
    pagerduty_trigger_incident(
        severity="critical",
        summary=f"REGULATORY SLA BREACH: {dag.dag_id} — tasks {missed}",
        component="regulatory-reporting",
        group="federal-reserve",
    )
    
    send_slack_alert(
        channel="#regulatory-escalation",
        text=f":rotating_light: *SLA BREACH* on `{dag.dag_id}`\n"
             f"Missed tasks: {missed}\n"
             f"Blocking: {[str(t) for t in blocking_task_list]}\n"
             f"*Immediate action required.*",
    )


def task_success_audit(context):
    """Every successful task gets logged for SOX."""
    ti = context['ti']
    audit.log_event("TASK_COMPLETE", {
        "task_id": ti.task_id,
        "duration_seconds": ti.duration,
        "try_number": ti.try_number,
        "worker": ti.hostname,
        "xcom_result_hash": _hash_xcom(ti),
    })


def task_failure_escalation(context):
    """Failure callback with time-aware escalation."""
    ti = context['ti']
    dag_run = context['dag_run']
    
    elapsed_hours = (datetime.utcnow() - dag_run.start_date).total_seconds() / 3600
    remaining = TOTAL_WINDOW_HOURS - elapsed_hours
    
    audit.log_event("TASK_FAILURE", {
        "task_id": ti.task_id,
        "exception": str(context.get('exception', ''))[:1000],
        "try_number": ti.try_number,
        "time_remaining_hours": round(remaining, 2),
    })
    
    if remaining < 1.0:
        # Less than 1 hour: war room mode
        activate_war_room(ti.dag_id, ti.task_id, remaining)
    elif remaining < 2.0:
        # Less than 2 hours: P1 page
        pagerduty_trigger_incident(severity="critical", summary=f"{ti.task_id} failed, {remaining:.1f}h remaining")
    else:
        # Buffer exists: P2 alert
        send_slack_alert(channel="#regulatory-ops", text=f"{ti.task_id} failed, retrying. {remaining:.1f}h buffer.")


def pre_sla_warning_check(**context):
    """Checkpoint task: warn if we're consuming too much of the window."""
    dag_run = context['dag_run']
    elapsed = (datetime.utcnow() - dag_run.start_date).total_seconds() / 3600
    fraction_used = elapsed / TOTAL_WINDOW_HOURS
    
    if fraction_used >= WARNING_THRESHOLD:
        send_slack_alert(
            channel="#regulatory-ops",
            text=f":warning: *PRE-SLA WARNING*: {fraction_used*100:.0f}% of processing window consumed. "
                 f"Only {TOTAL_WINDOW_HOURS - elapsed:.1f}h remaining.",
        )
        audit.log_event("PRE_SLA_WARNING", {"fraction_used": fraction_used})
    
    return {"fraction_used": fraction_used, "on_track": fraction_used < WARNING_THRESHOLD}


# ─── DAG DEFINITION ───────────────────────────────────────────────

default_args = {
    'owner': 'regulatory-team',
    'retries': 3,
    'retry_delay': timedelta(minutes=2),
    'retry_exponential_backoff': True,
    'max_retry_delay': timedelta(minutes=10),
    'on_success_callback': task_success_audit,
    'on_failure_callback': task_failure_escalation,
    'execution_timeout': timedelta(minutes=60),  # Default per-task timeout
}

with DAG(
    dag_id='fed_capital_adequacy_daily',
    default_args=default_args,
    schedule_interval='0 2 * * 1-5',  # 2 AM weekdays
    start_date=datetime(2024, 1, 1),
    catchup=False,
    dagrun_timeout=timedelta(hours=4, minutes=45),  # Hard DAG timeout
    sla_miss_callback=regulatory_sla_miss_callback,
    tags=['regulatory', 'federal-reserve', 'sox', 'p1'],
    max_active_runs=1,  # Never overlap regulatory runs
) as dag:

    # ─── STAGE 1: Wait for upstream data ──────────────────────────

    wait_for_positions = ExternalTaskSensor(
        task_id='wait_for_eod_positions',
        external_dag_id='trading_eod_close',
        external_task_id='position_snapshot_complete',
        timeout=3600,
        poke_interval=60,
        mode='reschedule',
        sla=timedelta(hours=1),  # Positions must be ready within 1h of start
        priority_weight=90,
        queue='critical_queue',
    )

    wait_for_market_data = ExternalTaskSensor(
        task_id='wait_for_market_data',
        external_dag_id='market_data_eod',
        external_task_id='rates_curves_complete',
        timeout=3600,
        poke_interval=60,
        mode='reschedule',
        sla=timedelta(hours=1),
        priority_weight=90,
        queue='critical_queue',
    )

    # ─── STAGE 2: Validate & Reconcile ────────────────────────────

    validate_positions = PythonOperator(
        task_id='validate_position_data',
        python_callable=validate_position_completeness,
        sla=timedelta(hours=1, minutes=30),
        execution_timeout=timedelta(minutes=30),
        priority_weight=80,
        queue='validation_queue',
    )

    reconcile_with_source = PythonOperator(
        task_id='reconcile_with_source_systems',
        python_callable=run_reconciliation,
        sla=timedelta(hours=2),
        execution_timeout=timedelta(minutes=45),
        priority_weight=75,
        queue='validation_queue',
    )

    # ─── STAGE 3: Risk Calculations (Basel III) ───────────────────

    calculate_rwa = PythonOperator(
        task_id='calculate_risk_weighted_assets',
        python_callable=compute_rwa_basel3,
        sla=timedelta(hours=3),
        execution_timeout=timedelta(minutes=90),
        priority_weight=95,
        queue='critical_queue',
        pool='risk_calculation_pool',  # Limit concurrency of heavy calcs
    )

    calculate_capital_ratios = PythonOperator(
        task_id='calculate_capital_ratios',
        python_callable=compute_capital_ratios,
        sla=timedelta(hours=3, minutes=30),
        execution_timeout=timedelta(minutes=30),
        priority_weight=95,
        queue='critical_queue',
    )

    # ─── CHECKPOINT: Pre-SLA Warning ──────────────────────────────

    sla_checkpoint = PythonOperator(
        task_id='pre_sla_warning_check',
        python_callable=pre_sla_warning_check,
        priority_weight=100,
        queue='critical_queue',
    )

    # ─── STAGE 4: Report Generation ──────────────────────────────

    generate_report = PythonOperator(
        task_id='generate_capital_report',
        python_callable=generate_fed_report_xml,
        sla=timedelta(hours=4),
        execution_timeout=timedelta(minutes=30),
        priority_weight=95,
        queue='critical_queue',
    )

    validate_report_schema = PythonOperator(
        task_id='validate_report_schema',
        python_callable=validate_against_fed_xsd,
        sla=timedelta(hours=4, minutes=15),
        execution_timeout=timedelta(minutes=10),
        priority_weight=100,
        queue='critical_queue',
    )

    # ─── STAGE 5: Submission ──────────────────────────────────────

    submit_to_fed = PythonOperator(
        task_id='submit_to_federal_reserve',
        python_callable=submit_via_fedline,
        sla=timedelta(hours=4, minutes=45),
        execution_timeout=timedelta(minutes=15),
        priority_weight=100,
        queue='critical_queue',
        retries=5,  # More retries for submission (network issues)
        retry_delay=timedelta(minutes=1),
        on_success_callback=submission_success_notify,  # Override: notify leadership
    )

    # ─── DEPENDENCIES ─────────────────────────────────────────────

    [wait_for_positions, wait_for_market_data] >> validate_positions
    validate_positions >> reconcile_with_source
    reconcile_with_source >> calculate_rwa >> calculate_capital_ratios
    calculate_capital_ratios >> sla_checkpoint >> generate_report
    generate_report >> validate_report_schema >> submit_to_fed
```

---

## Production Handling

### What Happens When SLA Breach is Imminent

```
Timeline (5-hour window):
─────────────────────────────────────────────────────────────
02:00  02:30  03:00  03:30  04:00  04:30  05:00  05:30  06:00  06:30  07:00
  │      │      │      │      │      │      │      │      │      │      │
  ├──────────────────────────────┤                              DEADLINE
  │     Normal processing        │                                 │
  │                              ├──── 60% mark: status check      │
  │                              │                                  │
  │                              ├────── 80% mark: WARNING ─────── │
  │                              │       (04:00 = 80% of 5h)       │
  │                              │                                  │
  │                              │    ┌── 90%: P1 PAGE ────────── │
  │                              │    │   (04:30)                   │
  │                              │    │                             │
  │                              │    │  ┌── <1h: WAR ROOM ────── │
  │                              │    │  │  (06:00)                 │
  │                              │    │  │                          │
  │                              │    │  │  ┌── <30m: REG NOTIFY  │
```

### Escalation Chain

| Trigger | Action | Who |
|---------|--------|-----|
| Task fails, >2h buffer | Slack alert, auto-retry | On-call engineer |
| Task fails, 1-2h buffer | P1 PagerDuty | On-call + backup |
| 80% window consumed | Pre-SLA warning in Slack | Team lead notified |
| Task fails, <1h buffer | War room activated | VP Engineering, Compliance |
| SLA breach confirmed | Regulatory liaison notified | Chief Risk Officer |
| Submission missed | Board notification, fine assessment | C-suite |

### Post-Mortem Requirements (SOX)

Every SLA breach or near-miss requires:

1. **Root cause analysis** within 24 hours
2. **Immutable audit trail** review (who/what/when for every step)
3. **Remediation plan** filed with compliance within 48 hours
4. **Evidence preservation** — all logs, XCom values, configs frozen
5. **Regulatory notification** if deadline actually missed

---

## Key Takeaways

1. **SLA is informational, execution_timeout kills** — use both. SLA for alerting humans, timeout for preventing runaway tasks from consuming your window.

2. **Callbacks are your compliance layer** — `on_success_callback` on every task gives you the SOX audit trail for free. Don't rely on Airflow's metadata DB alone; write to an immutable ledger.

3. **Priority weight with downstream rule** ensures early tasks in a critical path get resources first. Without this, a low-priority DAG can starve your regulatory pipeline.

4. **Queue isolation is non-negotiable** — regulatory workloads must run on dedicated workers that cannot be starved by batch analytics or ad-hoc queries.

5. **Time-aware escalation** is more useful than static severity. A failure at 02:30 (4.5h buffer) is P3. The same failure at 06:30 (30min buffer) is "wake up the CRO."

6. **`dagrun_timeout` is your last line of defense** — if individual task timeouts and retries don't save you, the DAG-level timeout ensures you fail loudly rather than run past your submission window silently.

7. **`max_active_runs=1`** prevents overlapping regulatory runs. If yesterday's run is still going when today's starts, you have two problems instead of one.

8. **Checkpoint tasks** (like `pre_sla_warning_check`) are cheap insurance. A 2-second Python task that checks elapsed time and alerts can save you from a silent creep toward deadline.
