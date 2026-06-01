# Financial Audit Trail & Compliance Monitoring

## Problem Statement

Financial institutions must maintain complete, immutable audit trails for every transaction transformation. Regulatory frameworks—SOX, GDPR, PCI-DSS, MiFID II, Basel III—require proving data lineage, transformation correctness, and retention policy adherence at any point in time. A single missed audit record can result in $10M+ fines, criminal liability for executives, and loss of banking licenses.

The challenge is not just storing audit data—it's proving completeness. You must demonstrate that:
- Every source record has a verifiable transformation path to every downstream output
- No historical data has been modified after the fact
- All access is logged and attributable to a specific person/system
- Data retention meets minimum AND maximum requirements (keep ≥7 years, delete after right-to-be-forgotten requests)

At scale—processing 500M+ transactions/day across 50+ systems—maintaining this audit trail without impacting pipeline performance requires careful architecture.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│              FINANCIAL AUDIT TRAIL ARCHITECTURE                                   │
└─────────────────────────────────────────────────────────────────────────────────┘

 ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐
 │  Core    │  │  Payment │  │  Trading │  │  Lending │
 │ Banking  │  │ Gateway  │  │  System  │  │  System  │
 │  (OLTP)  │  │  (OLTP)  │  │  (OLTP)  │  │  (OLTP)  │
 └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘
      │              │              │              │
      ▼              ▼              ▼              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    CDC LAYER (Debezium + Kafka Connect)                       │
│                                                                              │
│  • Captures every INSERT/UPDATE/DELETE with before/after images              │
│  • Assigns monotonic LSN (Log Sequence Number) per source                   │
│  • Emits OpenLineage events for each captured change                        │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────┐       │
│  │  MONITOR: CDC lag, missing LSNs, schema change detection         │       │
│  └──────────────────────────────────────────────────────────────────┘       │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    KAFKA (Immutable Event Log)                                │
│                                                                              │
│  • Retention: infinite (compacted topics for latest state)                   │
│  • Partitioned by entity_id for ordering guarantees                         │
│  • Each message includes: source_system, timestamp, operation, LSN          │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────┐       │
│  │  MONITOR: Consumer lag, partition skew, message ordering          │       │
│  └──────────────────────────────────────────────────────────────────┘       │
└─────────────────────────┬───────────────────────┬───────────────────────────┘
                          │                       │
                          ▼                       ▼
┌────────────────────────────────────┐  ┌────────────────────────────────────┐
│  TRANSFORMATION (Spark Structured  │  │   RAW ARCHIVE (S3/ADLS)            │
│  Streaming + dbt)                  │  │                                    │
│                                    │  │  • Immutable raw event storage     │
│  • Business logic application      │  │  • Content-addressable (SHA-256)  │
│  • Reconciliation counts emitted   │  │  • Write-once, read-many          │
│  • OpenLineage events per job      │  │                                    │
│                                    │  │  Retention: 10 years minimum       │
│  ┌──────────────────────────────┐  │  └────────────────────────────────────┘
│  │ MONITOR: Input/output counts,│  │
│  │ transformation correctness   │  │
│  └──────────────────────────────┘  │
└─────────────────┬──────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│              APACHE ICEBERG TABLES (Lakehouse)                                │
│                                                                              │
│  • Time-travel: query any historical state                                   │
│  • Snapshot isolation: concurrent reads/writes                               │
│  • Row-level deletes for GDPR (without rewriting history)                   │
│  • Audit columns: _ingested_at, _source_system, _batch_id, _lineage_id     │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────┐       │
│  │  MONITOR: Snapshot count, table size, partition metrics           │       │
│  └──────────────────────────────────────────────────────────────────┘       │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│              LINEAGE & AUDIT LAYER                                            │
│                                                                              │
│  ┌────────────────┐  ┌────────────────┐  ┌─────────────────────────┐       │
│  │  OpenLineage   │  │    Marquez     │  │  Access Audit Log       │       │
│  │  (Events)      │──►│  (Lineage DB) │  │  (AWS CloudTrail /      │       │
│  └────────────────┘  └────────────────┘  │   Lake Formation)       │       │
│                                           └─────────────────────────┘       │
│  ┌──────────────────────────────────────────────────────────────────┐       │
│  │  MONITOR: Lineage completeness, access anomalies, retention age  │       │
│  └──────────────────────────────────────────────────────────────────┘       │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│              COMPLIANCE REPORTING                                             │
│                                                                              │
│  • SOX: Quarterly control attestation reports                                │
│  • GDPR: Data subject access requests (DSAR) fulfilled via time-travel      │
│  • PCI-DSS: Cardholder data flow documentation                              │
│  • MiFID II: Transaction reporting within T+1                                │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## What Must Be Monitored for Compliance

### 1. Data Completeness

Every source record must have a corresponding record in the target system. Zero tolerance for silent data loss.

```
Source System                    Target System
┌──────────────────┐            ┌──────────────────┐
│ Transactions: N  │───────────►│ Transactions: N  │
│                  │    Must     │                  │
│ Batch ID: B001   │    Equal    │ Batch ID: B001   │
└──────────────────┘            └──────────────────┘
         │                               │
         ▼                               ▼
    Count = 1,234,567              Count = 1,234,567 ✓
    Sum(amount) = $45.2M           Sum(amount) = $45.2M ✓
    Checksum = 0xABCD              Checksum = 0xABCD ✓
```

### 2. Transformation Correctness

Input/output reconciliation must balance for every batch. Business rules must produce verifiable results.

### 3. Retention Policy Compliance

| Regulation | Minimum Retention | Maximum Retention | Data Type |
|-----------|------------------|------------------|-----------|
| SOX | 7 years | - | Financial records |
| GDPR | - | Purpose limitation | Personal data |
| PCI-DSS | 1 year | Minimize | Cardholder data |
| MiFID II | 5 years | 7 years | Trading records |
| Basel III | 5 years | - | Risk data |

### 4. Access Audit

Every query against sensitive data must be logged with: who, what, when, why (business justification), and from where (IP/service).

### 5. Schema Evolution Tracking

All schema changes must be:
- Documented with change ticket reference
- Backward-compatible or explicitly versioned
- Auditable (who approved, when applied)

### 6. Data Lineage Completeness

No gaps allowed in the transformation chain. Every output field must trace back to source fields through documented transformations.

### 7. Immutability Verification

Historical data must remain unchanged. Any modification to closed periods must be detected and alerted immediately.

---

## Iceberg + Delta Lake for Audit

### Time-Travel Queries

```sql
-- Query the state of accounts table as it existed on a specific date
-- Critical for regulatory point-in-time reporting
SELECT *
FROM financial.accounts
FOR SYSTEM_TIME AS OF TIMESTAMP '2024-03-31 23:59:59'
WHERE account_type = 'SAVINGS';

-- Compare current state with historical state to detect unauthorized changes
SELECT 
    current.account_id,
    current.balance AS current_balance,
    historical.balance AS historical_balance,
    current.balance - historical.balance AS unexplained_change
FROM financial.accounts AS current
FULL OUTER JOIN financial.accounts 
    FOR SYSTEM_TIME AS OF TIMESTAMP '2024-03-31 23:59:59' AS historical
    ON current.account_id = historical.account_id
WHERE current.balance != historical.balance
  AND current.account_id NOT IN (
    -- Exclude accounts with legitimate transactions in the period
    SELECT DISTINCT account_id 
    FROM financial.transactions 
    WHERE txn_date > '2024-03-31'
  );
```

### Snapshot Metadata as Audit Trail

```sql
-- List all snapshots (each represents a committed state)
SELECT 
    snapshot_id,
    committed_at,
    operation,
    summary['added-records'] AS records_added,
    summary['deleted-records'] AS records_deleted,
    summary['changed-partition-count'] AS partitions_changed
FROM financial.accounts.snapshots
ORDER BY committed_at DESC;

-- Identify who made changes (correlate with pipeline metadata)
SELECT 
    s.snapshot_id,
    s.committed_at,
    s.operation,
    m.pipeline_run_id,
    m.triggered_by,
    m.approval_ticket
FROM financial.accounts.snapshots s
JOIN audit.pipeline_metadata m 
    ON s.snapshot_id = m.iceberg_snapshot_id
WHERE s.committed_at > current_timestamp - INTERVAL '24' HOUR;
```

### Row-Level Change Tracking

```sql
-- Iceberg changelog: see exactly what changed between two snapshots
SELECT *
FROM financial.accounts
CHANGES BETWEEN 
    SNAPSHOT '3789372893' AND SNAPSHOT '3789372894';

-- Detailed change tracking with before/after values
-- Using Iceberg's row-level deletes + inserts pattern
SELECT
    _change_type,  -- 'INSERT', 'DELETE', 'UPDATE_BEFORE', 'UPDATE_AFTER'
    account_id,
    balance,
    last_modified,
    _commit_snapshot_id
FROM financial.accounts.changes
WHERE _commit_snapshot_id > 3789372893
ORDER BY account_id, _change_ordinal;
```

---

## OpenLineage Integration

### Architecture

```
┌───────────────┐     ┌───────────────┐     ┌───────────────┐
│   Airflow     │     │    Spark      │     │     dbt       │
│  (Scheduler)  │     │   (Jobs)      │     │   (Models)    │
└───────┬───────┘     └───────┬───────┘     └───────┬───────┘
        │                     │                     │
        │  OpenLineage        │  OpenLineage        │  OpenLineage
        │  Events             │  Events             │  Events
        │                     │                     │
        ▼                     ▼                     ▼
┌─────────────────────────────────────────────────────────────┐
│                    MARQUEZ (Lineage Server)                   │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  Lineage Graph:                                      │    │
│  │                                                      │    │
│  │  source.transactions ──► staging.txn_cleaned         │    │
│  │       │                       │                      │    │
│  │       │                       ▼                      │    │
│  │       │               mart.daily_balances            │    │
│  │       │                       │                      │    │
│  │       ▼                       ▼                      │    │
│  │  staging.txn_raw ──► mart.customer_360               │    │
│  │                                                      │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
│  Column-level lineage: mart.daily_balances.total_amount     │
│    ← staging.txn_cleaned.amount (SUM aggregation)           │
│    ← source.transactions.txn_amount (renamed)               │
└─────────────────────────────────────────────────────────────┘
```

### Custom OpenLineage Event Emission from Spark

```python
"""
openlineage_spark_audit.py
Emit OpenLineage events from custom Spark jobs for financial audit trail.
"""
from openlineage.client import OpenLineageClient
from openlineage.client.run import (
    RunEvent, RunState, Run, Job, Dataset,
    InputDataset, OutputDataset
)
from openlineage.client.facet import (
    SchemaDatasetFacet, SchemaField,
    DataQualityMetricsInputDatasetFacet,
    ColumnLineageDatasetFacet, ColumnLineageDatasetFacetFieldsAdditional,
    InputField, SqlJobFacet
)
from datetime import datetime
import uuid


class FinancialPipelineLineageEmitter:
    """Emits OpenLineage events for financial data pipeline runs."""
    
    def __init__(self, marquez_url: str, namespace: str = "financial_pipelines"):
        self.client = OpenLineageClient(url=marquez_url)
        self.namespace = namespace
    
    def emit_job_start(
        self,
        job_name: str,
        run_id: str,
        input_datasets: list,
        output_datasets: list,
        sql: str = None,
    ):
        """Emit a START event when a transformation job begins."""
        
        inputs = []
        for ds in input_datasets:
            inputs.append(InputDataset(
                namespace=self.namespace,
                name=ds["name"],
                facets={
                    "schema": SchemaDatasetFacet(
                        fields=[
                            SchemaField(name=f["name"], type=f["type"])
                            for f in ds.get("schema", [])
                        ]
                    )
                }
            ))
        
        outputs = []
        for ds in output_datasets:
            output_facets = {
                "schema": SchemaDatasetFacet(
                    fields=[
                        SchemaField(name=f["name"], type=f["type"])
                        for f in ds.get("schema", [])
                    ]
                )
            }
            
            # Add column-level lineage if available
            if "column_lineage" in ds:
                output_facets["columnLineage"] = ColumnLineageDatasetFacet(
                    fields={
                        col: ColumnLineageDatasetFacetFieldsAdditional(
                            inputFields=[
                                InputField(
                                    namespace=self.namespace,
                                    name=inp["dataset"],
                                    field=inp["field"]
                                )
                                for inp in sources
                            ],
                            transformationType="SQL",
                            transformationDescription=ds["column_lineage"][col].get("description", "")
                        )
                        for col, sources in ds["column_lineage"].items()
                    }
                )
            
            outputs.append(OutputDataset(
                namespace=self.namespace,
                name=ds["name"],
                facets=output_facets
            ))
        
        job_facets = {}
        if sql:
            job_facets["sql"] = SqlJobFacet(query=sql)
        
        event = RunEvent(
            eventType=RunState.START,
            eventTime=datetime.utcnow().isoformat() + "Z",
            run=Run(runId=run_id),
            job=Job(namespace=self.namespace, name=job_name, facets=job_facets),
            inputs=inputs,
            outputs=outputs,
        )
        
        self.client.emit(event)
    
    def emit_job_complete(
        self,
        job_name: str,
        run_id: str,
        input_count: int,
        output_count: int,
        quality_metrics: dict,
    ):
        """Emit a COMPLETE event with reconciliation data."""
        
        event = RunEvent(
            eventType=RunState.COMPLETE,
            eventTime=datetime.utcnow().isoformat() + "Z",
            run=Run(
                runId=run_id,
                facets={
                    "dataQuality": {
                        "inputRecordCount": input_count,
                        "outputRecordCount": output_count,
                        "reconciliation": {
                            "inputSum": quality_metrics.get("input_sum"),
                            "outputSum": quality_metrics.get("output_sum"),
                            "balanced": quality_metrics.get("balanced", False),
                        }
                    }
                }
            ),
            job=Job(namespace=self.namespace, name=job_name),
            inputs=[],
            outputs=[],
        )
        
        self.client.emit(event)
    
    def emit_job_fail(self, job_name: str, run_id: str, error_message: str):
        """Emit a FAIL event when a job fails."""
        
        event = RunEvent(
            eventType=RunState.FAIL,
            eventTime=datetime.utcnow().isoformat() + "Z",
            run=Run(
                runId=run_id,
                facets={"errorMessage": {"message": error_message}}
            ),
            job=Job(namespace=self.namespace, name=job_name),
            inputs=[],
            outputs=[],
        )
        
        self.client.emit(event)
```

### Compliance Reporting from Lineage

```python
"""
compliance_reporter.py
Generates compliance reports from OpenLineage data stored in Marquez.
"""
import requests
from datetime import datetime, timedelta
from typing import Dict, List


class ComplianceReporter:
    """Generate regulatory compliance reports from lineage metadata."""
    
    def __init__(self, marquez_url: str):
        self.marquez_url = marquez_url
    
    def generate_sox_report(self, quarter_end: str) -> Dict:
        """
        SOX Section 404: Internal Controls over Financial Reporting
        Proves that all financial transformations have complete audit trail.
        """
        report = {
            "report_type": "SOX_404_DATA_CONTROLS",
            "quarter_end": quarter_end,
            "generated_at": datetime.utcnow().isoformat(),
            "controls": []
        }
        
        # Control 1: All pipelines have lineage
        jobs = self._get_all_jobs(namespace="financial_pipelines")
        jobs_with_lineage = [j for j in jobs if j.get("latestRun")]
        
        report["controls"].append({
            "control_id": "SOX-DC-001",
            "description": "All financial data pipelines emit lineage events",
            "total_pipelines": len(jobs),
            "pipelines_with_lineage": len(jobs_with_lineage),
            "compliance_rate": len(jobs_with_lineage) / max(len(jobs), 1),
            "status": "PASS" if len(jobs_with_lineage) == len(jobs) else "FAIL",
        })
        
        # Control 2: Reconciliation passes for all runs
        failed_reconciliations = self._get_failed_reconciliations(quarter_end)
        
        report["controls"].append({
            "control_id": "SOX-DC-002",
            "description": "Source-target reconciliation passes for all batches",
            "total_runs": self._get_total_runs(quarter_end),
            "failed_reconciliations": len(failed_reconciliations),
            "status": "PASS" if len(failed_reconciliations) == 0 else "FAIL",
            "exceptions": failed_reconciliations[:10],  # First 10 for review
        })
        
        # Control 3: No unauthorized schema changes
        schema_changes = self._get_schema_changes(quarter_end)
        unauthorized = [s for s in schema_changes if not s.get("approval_ticket")]
        
        report["controls"].append({
            "control_id": "SOX-DC-003",
            "description": "All schema changes have approval tickets",
            "total_changes": len(schema_changes),
            "unauthorized_changes": len(unauthorized),
            "status": "PASS" if len(unauthorized) == 0 else "FAIL",
        })
        
        return report
    
    def generate_gdpr_dsar_report(self, data_subject_id: str) -> Dict:
        """
        GDPR Data Subject Access Request: trace all data related to a person.
        Uses lineage to find all downstream datasets containing their data.
        """
        # Find all datasets containing this subject's data
        source_datasets = self._find_datasets_with_subject(data_subject_id)
        
        # Trace lineage downstream
        all_datasets = set()
        for ds in source_datasets:
            downstream = self._get_downstream_datasets(ds)
            all_datasets.update(downstream)
        
        return {
            "report_type": "GDPR_DSAR",
            "data_subject_id": data_subject_id,
            "generated_at": datetime.utcnow().isoformat(),
            "datasets_containing_data": list(all_datasets),
            "total_datasets": len(all_datasets),
            "lineage_complete": True,
        }
    
    def _get_all_jobs(self, namespace: str) -> List[Dict]:
        resp = requests.get(f"{self.marquez_url}/api/v1/namespaces/{namespace}/jobs")
        return resp.json().get("jobs", [])
    
    def _get_downstream_datasets(self, dataset_name: str) -> List[str]:
        resp = requests.get(
            f"{self.marquez_url}/api/v1/lineage",
            params={"nodeId": f"dataset:{dataset_name}", "depth": 10}
        )
        graph = resp.json().get("graph", [])
        return [node["id"] for node in graph if node["type"] == "DATASET"]
    
    def _get_failed_reconciliations(self, quarter_end: str) -> List[Dict]:
        # Query Marquez for runs where reconciliation.balanced = False
        # Implementation depends on how facets are stored/queried
        pass
    
    def _get_total_runs(self, quarter_end: str) -> int:
        pass
    
    def _get_schema_changes(self, quarter_end: str) -> List[Dict]:
        pass
    
    def _find_datasets_with_subject(self, subject_id: str) -> List[str]:
        pass
```

### Reconciliation Job

```python
"""
reconciliation_job.py
Compares source counts vs target counts for every batch.
Any mismatch > 0 triggers an immediate alert.
"""
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from dataclasses import dataclass
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class ReconciliationResult:
    batch_id: str
    source_system: str
    target_table: str
    source_count: int
    target_count: int
    source_sum: Optional[float]
    target_sum: Optional[float]
    count_matched: bool
    sum_matched: bool
    timestamp: str


class BatchReconciliation:
    """
    Reconciles source system record counts and amounts against
    target lakehouse tables for every batch.
    
    Zero tolerance: any mismatch triggers P1 alert.
    """
    
    def __init__(self, spark: SparkSession):
        self.spark = spark
    
    def reconcile_batch(
        self,
        batch_id: str,
        source_system: str,
        source_query: str,
        target_table: str,
        amount_column: Optional[str] = None,
    ) -> ReconciliationResult:
        """
        Compare source and target for a specific batch.
        
        Args:
            batch_id: Unique identifier for this batch
            source_system: Name of source (e.g., 'core_banking')
            source_query: SQL to get source counts/sums
            target_table: Iceberg table to validate against
            amount_column: Column to sum for amount reconciliation
        """
        
        # Get source metrics
        source_df = self.spark.sql(source_query)
        source_metrics = source_df.first()
        source_count = source_metrics["record_count"]
        source_sum = source_metrics.get("total_amount") if amount_column else None
        
        # Get target metrics
        target_df = self.spark.sql(f"""
            SELECT 
                COUNT(*) as record_count
                {f', SUM({amount_column}) as total_amount' if amount_column else ''}
            FROM {target_table}
            WHERE _batch_id = '{batch_id}'
        """)
        target_metrics = target_df.first()
        target_count = target_metrics["record_count"]
        target_sum = target_metrics.get("total_amount") if amount_column else None
        
        # Compare
        count_matched = source_count == target_count
        sum_matched = True
        if source_sum is not None and target_sum is not None:
            # Allow 0.01 cent tolerance for floating point
            sum_matched = abs(source_sum - target_sum) < 0.01
        
        result = ReconciliationResult(
            batch_id=batch_id,
            source_system=source_system,
            target_table=target_table,
            source_count=source_count,
            target_count=target_count,
            source_sum=source_sum,
            target_sum=target_sum,
            count_matched=count_matched,
            sum_matched=sum_matched,
            timestamp=datetime.utcnow().isoformat(),
        )
        
        # Log result
        if not count_matched or not sum_matched:
            logger.critical(
                f"RECONCILIATION FAILURE | batch={batch_id} | "
                f"source={source_system} | target={target_table} | "
                f"count: {source_count} vs {target_count} | "
                f"sum: {source_sum} vs {target_sum}"
            )
            self._emit_alert(result)
        else:
            logger.info(
                f"Reconciliation PASS | batch={batch_id} | "
                f"records={source_count} | sum={source_sum}"
            )
        
        # Persist result for audit
        self._persist_result(result)
        
        return result
    
    def _emit_alert(self, result: ReconciliationResult):
        """Emit P1 alert for reconciliation failure."""
        from alerting import send_pagerduty_alert
        
        send_pagerduty_alert(
            severity="critical",
            summary=f"Reconciliation failure: {result.source_system} → {result.target_table}",
            details={
                "batch_id": result.batch_id,
                "source_count": result.source_count,
                "target_count": result.target_count,
                "count_diff": result.source_count - result.target_count,
                "source_sum": result.source_sum,
                "target_sum": result.target_sum,
            }
        )
    
    def _persist_result(self, result: ReconciliationResult):
        """Write reconciliation result to audit table."""
        from pyspark.sql import Row
        
        row = Row(**result.__dict__)
        df = self.spark.createDataFrame([row])
        df.writeTo("audit.reconciliation_results").append()
```

### dbt Audit Helper Macros

```sql
-- macros/audit_helpers.sql

-- Macro: Record count reconciliation between source and target
{% macro reconcile_counts(source_relation, target_relation, batch_column, batch_value) %}

WITH source_count AS (
    SELECT COUNT(*) as cnt
    FROM {{ source_relation }}
    WHERE {{ batch_column }} = '{{ batch_value }}'
),
target_count AS (
    SELECT COUNT(*) as cnt
    FROM {{ target_relation }}
    WHERE {{ batch_column }} = '{{ batch_value }}'
)
SELECT
    '{{ source_relation }}' as source_table,
    '{{ target_relation }}' as target_table,
    '{{ batch_value }}' as batch_id,
    s.cnt as source_count,
    t.cnt as target_count,
    s.cnt - t.cnt as difference,
    CASE WHEN s.cnt = t.cnt THEN 'PASS' ELSE 'FAIL' END as status,
    CURRENT_TIMESTAMP as checked_at
FROM source_count s
CROSS JOIN target_count t

{% endmacro %}


-- Macro: Amount reconciliation with tolerance
{% macro reconcile_amounts(source_relation, target_relation, amount_column, batch_column, batch_value, tolerance=0.01) %}

WITH source_sum AS (
    SELECT COALESCE(SUM({{ amount_column }}), 0) as total
    FROM {{ source_relation }}
    WHERE {{ batch_column }} = '{{ batch_value }}'
),
target_sum AS (
    SELECT COALESCE(SUM({{ amount_column }}), 0) as total
    FROM {{ target_relation }}
    WHERE {{ batch_column }} = '{{ batch_value }}'
)
SELECT
    '{{ source_relation }}' as source_table,
    '{{ target_relation }}' as target_table,
    '{{ batch_value }}' as batch_id,
    s.total as source_amount,
    t.total as target_amount,
    ABS(s.total - t.total) as difference,
    CASE 
        WHEN ABS(s.total - t.total) <= {{ tolerance }} THEN 'PASS' 
        ELSE 'FAIL' 
    END as status,
    CURRENT_TIMESTAMP as checked_at
FROM source_sum s
CROSS JOIN target_sum t

{% endmacro %}


-- Macro: Detect records in source missing from target
{% macro find_missing_records(source_relation, target_relation, join_keys, batch_column, batch_value) %}

SELECT 
    s.*,
    'MISSING_IN_TARGET' as audit_status
FROM {{ source_relation }} s
LEFT JOIN {{ target_relation }} t
    ON {% for key in join_keys %}
        s.{{ key }} = t.{{ key }}
        {% if not loop.last %} AND {% endif %}
    {% endfor %}
WHERE s.{{ batch_column }} = '{{ batch_value }}'
  AND t.{{ join_keys[0] }} IS NULL

{% endmacro %}


-- Macro: Schema change detection
{% macro detect_schema_changes(relation, expected_columns) %}

{% set actual_columns = adapter.get_columns_in_relation(relation) %}

{% set added = [] %}
{% set removed = [] %}

{% for col in actual_columns %}
    {% if col.name not in expected_columns %}
        {% do added.append(col.name) %}
    {% endif %}
{% endfor %}

{% for col_name in expected_columns %}
    {% set found = actual_columns | selectattr("name", "equalto", col_name) | list %}
    {% if found | length == 0 %}
        {% do removed.append(col_name) %}
    {% endif %}
{% endfor %}

{% if added | length > 0 or removed | length > 0 %}
    {{ log("SCHEMA CHANGE DETECTED in " ~ relation, info=True) }}
    {{ log("  Added columns: " ~ added | join(", "), info=True) }}
    {{ log("  Removed columns: " ~ removed | join(", "), info=True) }}
{% endif %}

{% endmacro %}
```

### Retention Policy Enforcement Monitor

```python
"""
retention_monitor.py
Monitors and enforces data retention policies across the lakehouse.
"""
from datetime import datetime, timedelta
from typing import Dict, List
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class RetentionPolicy:
    table: str
    regulation: str
    min_retention_days: int
    max_retention_days: int  # 0 = no maximum
    pii_columns: List[str]


@dataclass
class RetentionStatus:
    table: str
    oldest_record_age_days: int
    policy: RetentionPolicy
    min_compliance: bool  # True if oldest record meets minimum retention
    max_compliance: bool  # True if no records exceed maximum retention
    action_required: str  # "none", "approaching_min_delete", "exceeds_max"


class RetentionPolicyMonitor:
    """
    Monitors data retention compliance across regulated tables.
    
    Checks:
    1. Data not deleted before minimum retention period
    2. Data deleted after maximum retention period (GDPR)
    3. Alerts when approaching retention deadlines
    """
    
    APPROACHING_THRESHOLD_DAYS = 30  # Alert 30 days before deadline
    
    def __init__(self, spark, policies: List[RetentionPolicy]):
        self.spark = spark
        self.policies = {p.table: p for p in policies}
    
    def check_all_policies(self) -> List[RetentionStatus]:
        """Check retention compliance for all monitored tables."""
        results = []
        
        for table, policy in self.policies.items():
            status = self._check_table_retention(table, policy)
            results.append(status)
            
            if not status.min_compliance or not status.max_compliance:
                logger.critical(
                    f"RETENTION VIOLATION | table={table} | "
                    f"regulation={policy.regulation} | "
                    f"action={status.action_required}"
                )
        
        return results
    
    def _check_table_retention(
        self, table: str, policy: RetentionPolicy
    ) -> RetentionStatus:
        """Check a single table against its retention policy."""
        
        # Get oldest and newest record ages
        age_df = self.spark.sql(f"""
            SELECT 
                DATEDIFF(CURRENT_DATE, MIN(_ingested_at)) as oldest_age_days,
                DATEDIFF(CURRENT_DATE, MAX(_ingested_at)) as newest_age_days,
                COUNT(*) as total_records
            FROM {table}
        """)
        
        row = age_df.first()
        oldest_age = row["oldest_age_days"]
        
        # Check minimum retention (data must NOT be deleted before this)
        min_compliance = oldest_age >= policy.min_retention_days
        
        # Check maximum retention (data MUST be deleted after this)
        max_compliance = True
        if policy.max_retention_days > 0:
            max_compliance = oldest_age <= policy.max_retention_days
        
        # Determine action
        action = "none"
        if not max_compliance:
            action = "exceeds_max_IMMEDIATE_DELETE_REQUIRED"
        elif not min_compliance:
            action = "below_min_INVESTIGATE_PREMATURE_DELETION"
        elif policy.max_retention_days > 0:
            days_until_max = policy.max_retention_days - oldest_age
            if days_until_max <= self.APPROACHING_THRESHOLD_DAYS:
                action = f"approaching_max_delete_in_{days_until_max}_days"
        
        return RetentionStatus(
            table=table,
            oldest_record_age_days=oldest_age,
            policy=policy,
            min_compliance=min_compliance,
            max_compliance=max_compliance,
            action_required=action,
        )
    
    def enforce_max_retention(self, table: str) -> int:
        """Delete records exceeding maximum retention (GDPR compliance)."""
        policy = self.policies[table]
        
        if policy.max_retention_days == 0:
            return 0
        
        cutoff_date = datetime.now() - timedelta(days=policy.max_retention_days)
        
        # Use Iceberg's row-level delete
        deleted = self.spark.sql(f"""
            DELETE FROM {table}
            WHERE _ingested_at < '{cutoff_date.strftime('%Y-%m-%d')}'
        """)
        
        count = deleted.first()["num_affected_rows"]
        
        logger.info(
            f"Retention enforcement: deleted {count} records from {table} "
            f"older than {policy.max_retention_days} days"
        )
        
        # Log the deletion for audit
        self.spark.sql(f"""
            INSERT INTO audit.retention_actions
            VALUES (
                '{table}', '{policy.regulation}', {count},
                '{cutoff_date.strftime('%Y-%m-%d')}', CURRENT_TIMESTAMP,
                'automated_retention_enforcement'
            )
        """)
        
        return count
```

---

## Alert Rules

```yaml
# financial_audit_alerts.yml
groups:
  - name: financial_compliance_critical
    rules:
      # Source-target mismatch (ZERO tolerance)
      - alert: ReconciliationFailure
        expr: audit_reconciliation_difference != 0
        for: 0m
        labels:
          severity: critical
          team: data-platform
          regulation: SOX
        annotations:
          summary: "RECONCILIATION FAILURE: {{ $labels.source }} → {{ $labels.target }}"
          description: |
            Batch: {{ $labels.batch_id }}
            Source count: {{ $labels.source_count }}
            Target count: {{ $labels.target_count }}
            Difference: {{ $value }}
            ACTION: Investigate immediately. Do NOT proceed with downstream processing.
          runbook_url: "https://wiki.internal/runbooks/reconciliation-failure"

      # Missing lineage event
      - alert: LineageEventMissing
        expr: |
          time() - audit_last_lineage_event_timestamp{namespace="financial_pipelines"}
          > 3600
        for: 5m
        labels:
          severity: critical
          team: data-platform
          regulation: SOX
        annotations:
          summary: "No lineage event for pipeline {{ $labels.job_name }} in >1 hour"
          description: |
            Pipeline runs without lineage tracking violate SOX controls.
            Last event: {{ $labels.last_event_time }}

      # Retention deadline approaching
      - alert: RetentionDeadlineApproaching
        expr: audit_retention_days_until_max < 30
        for: 0m
        labels:
          severity: warning
          team: data-platform
          regulation: GDPR
        annotations:
          summary: "Data in {{ $labels.table }} must be deleted within {{ $value }} days"

      # Retention violation (data exceeds max)
      - alert: RetentionViolation
        expr: audit_retention_days_until_max < 0
        for: 0m
        labels:
          severity: critical
          team: data-platform
          regulation: GDPR
        annotations:
          summary: "RETENTION VIOLATION: {{ $labels.table }} has data {{ $value }} days past maximum"
          description: "Immediate deletion required. GDPR fine risk."

      # Unauthorized data access
      - alert: UnauthorizedDataAccess
        expr: audit_access_unauthorized_attempts > 0
        for: 0m
        labels:
          severity: critical
          team: security
          regulation: PCI-DSS
        annotations:
          summary: "Unauthorized access attempt to {{ $labels.table }}"
          description: |
            User: {{ $labels.user }}
            Table: {{ $labels.table }}
            Time: {{ $labels.timestamp }}
            Source IP: {{ $labels.source_ip }}

      # Schema change without ticket
      - alert: UnauthorizedSchemaChange
        expr: audit_schema_changes_without_ticket > 0
        for: 0m
        labels:
          severity: critical
          team: data-platform
          regulation: SOX
        annotations:
          summary: "Schema change to {{ $labels.table }} without approval ticket"

      # CDC lag too high (transactions not captured)
      - alert: CDCLagCritical
        expr: debezium_cdc_lag_seconds > 300
        for: 2m
        labels:
          severity: critical
          team: data-platform
        annotations:
          summary: "CDC lag {{ $value }}s for {{ $labels.source_system }}"
          description: "Transactions may be missed. Financial records at risk of incompleteness."

      # Immutability violation (historical data modified)
      - alert: ImmutabilityViolation
        expr: audit_historical_data_modifications > 0
        for: 0m
        labels:
          severity: critical
          team: security
          regulation: SOX
        annotations:
          summary: "HISTORICAL DATA MODIFIED in {{ $labels.table }}"
          description: |
            Records in closed period were modified.
            Snapshot before: {{ $labels.snapshot_before }}
            Snapshot after: {{ $labels.snapshot_after }}
            Records affected: {{ $value }}
            THIS IS A POTENTIAL FRAUD INDICATOR.
```

---

## Technologies

| Category | Tool | Purpose |
|----------|------|---------|
| Table Format | Apache Iceberg | Time-travel, snapshots, row-level deletes |
| Table Format | Delta Lake | Alternative with similar audit capabilities |
| Lineage | OpenLineage | Standard lineage event format |
| Lineage Server | Marquez | Stores and queries lineage graph |
| CDC | Debezium | Captures every database change |
| Streaming | Kafka | Immutable event log backbone |
| Transformation | Spark | Distributed processing with lineage |
| Transformation | dbt | SQL transformations with built-in tests |
| Access Control | AWS Lake Formation | Column-level security + access logging |
| Catalog | DataHub | Metadata, governance, discovery |
| Orchestration | Airflow | Pipeline scheduling with audit metadata |

---

## Runbook: Reconciliation Failure

### Immediate Response (< 5 minutes)

```
1. HALT downstream processing
   → Pause all DAGs consuming the affected table
   → Command: airflow dags pause <downstream_dag_id>

2. Identify the scope
   → Which batch failed?
   → How many records are missing/extra?
   → Is it a count issue or an amount issue?

3. Check for known causes
   → CDC lag: check Debezium metrics
   → Kafka consumer lag: check consumer group offsets  
   → Spark job failure: check Spark UI for failed tasks
```

### Investigation (5-30 minutes)

```
4. Compare source snapshot with target
   → Use Iceberg time-travel to see target state before this batch
   → Query source system audit tables for the batch window

5. Check for duplicates in target
   SELECT _batch_id, primary_key, COUNT(*)
   FROM target_table
   WHERE _batch_id = 'FAILED_BATCH'
   GROUP BY _batch_id, primary_key
   HAVING COUNT(*) > 1;

6. Check for missing records
   → Use dbt macro: find_missing_records(source, target, keys, batch)
   → Identify pattern: random records missing vs contiguous range

7. Check Kafka for the batch
   → Verify all messages for the batch are present in topic
   → Check for consumer rebalance during processing
```

### Resolution

```
8. If records exist in Kafka but not in target:
   → Reprocess the batch from Kafka offset
   → Verify reconciliation passes after reprocessing

9. If records missing from Kafka (CDC issue):
   → Check Debezium connector status
   → Verify source WAL/binlog still contains the records
   → Perform manual extraction from source if needed

10. After resolution:
    → Verify reconciliation passes
    → Resume downstream DAGs
    → Document incident with root cause
    → Update monitoring if gap existed
```

### Escalation

| Time | Action |
|------|--------|
| 0-5 min | On-call data engineer |
| 5-30 min | Involve source system team if CDC issue |
| 30 min+ | Notify compliance officer |
| 2 hr+ | Regulatory disclosure assessment |
