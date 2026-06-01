# ML Model Training Data Versioning & Management at Scale

## The Production Problem

An AI company operates at the following scale:

- **4 PB** of training data across vision, NLP, and tabular domains
- **1,200+ experiments/day** across 80 ML engineers
- **350 production models** serving real-time predictions
- **15M new labeled samples/week** from annotation pipelines
- **Critical requirement**: Any model in production must be reproducible — exact same data, exact same result

### What Goes Wrong Without Proper Versioning

```
Timeline of an incident:

Day 1: Model v2.3 trained on dataset "customer_features_v7", deployed to production
Day 5: Data team fixes 50K mislabeled rows in the same table
Day 8: Model v2.3 performance degrades — nobody knows why
Day 12: Team tries to retrain v2.3 — gets different results (data changed underneath)
Day 15: Rollback attempted — but which exact data was v2.3 trained on?
Day 18: $2.1M revenue impact traced to silent data corruption
```

This is the **"data versioning gap"** — models are versioned (MLflow), code is versioned (Git), but **data is mutable and unversioned**.

---

## Why Iceberg + Nessie (and Not Alternatives)

### Comparison Matrix

| Requirement | Raw S3 Snapshots | DVC | Data Warehouse | Iceberg + Nessie |
|---|---|---|---|---|
| PB-scale versioning | Copy = $$$$ | Pointer-based (fragile) | Expensive storage | Zero-copy branching |
| Branching/isolation | Manual folders | Git-like but file-level | Not supported | Native Git semantics |
| Time travel | Manual | Via Git history | 90-day limit (BQ) | Unlimited snapshots |
| Schema evolution | Break consumers | Not aware | ALTER TABLE | Native, backward-compatible |
| Concurrent writes | Conflicts | Lock files | Supported | MVCC with conflict resolution |
| Query from ML frameworks | Custom readers | Custom | SQL only | Spark/PyIceberg/Trino |
| Atomic mutations | No | Commit-level | Transaction | Snapshot-level ACID |
| Cost at 4 PB | 4 PB × N copies | Metadata only | $$$$$ | Metadata branching, shared data |

### Why Not DVC?

DVC versions **files** — it tracks pointers to S3 objects. But ML training data is rarely a static file:

1. Labels get corrected continuously
2. New features are appended (schema evolution)
3. Rows are filtered/sampled differently per experiment
4. Data quality fixes must propagate selectively

Iceberg versions **table state** — schema, partitioning, and the exact set of data files. Nessie adds Git-like branching on top, enabling isolated experimentation without copying data.

### Why Not Warehouse (Snowflake/BigQuery)?

- **Cost**: 4 PB in Snowflake at $23/TB/month = $92K/month just for storage
- **Lock-in**: Training pipelines need Spark/Ray, not SQL-only access
- **Branching**: No native branch/merge semantics for datasets
- **Open format**: Iceberg files are open Parquet — any engine reads them

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        ML Training Data Platform                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────────────┐   │
│  │  Annotation  │     │  Feature     │     │  External Data       │   │
│  │  Pipeline    │     │  Engineering │     │  Ingestion           │   │
│  │  (Label Box) │     │  (dbt/Spark) │     │  (Airbyte/Kafka)     │   │
│  └──────┬───────┘     └──────┬───────┘     └──────────┬───────────┘   │
│         │                    │                         │               │
│         ▼                    ▼                         ▼               │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                    Apache Airflow (Orchestration)                │   │
│  │         DAGs: ingest → validate → transform → register          │   │
│  └─────────────────────────────┬───────────────────────────────────┘   │
│                                │                                       │
│                                ▼                                       │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                     Nessie Catalog                               │   │
│  │  ┌─────────┐  ┌──────────────┐  ┌────────────────────────┐     │   │
│  │  │  main   │  │ experiment/  │  │  release/model-v2.3    │     │   │
│  │  │ branch  │  │ user-alice   │  │  (tagged, immutable)   │     │   │
│  │  └────┬────┘  └──────┬───────┘  └────────────────────────┘     │   │
│  │       │               │                                         │   │
│  │       ▼               ▼                                         │   │
│  │  ┌─────────────────────────────────────────────────────────┐    │   │
│  │  │              Iceberg Table Metadata                       │    │   │
│  │  │   (snapshots, schema, partition specs, sort orders)      │    │   │
│  │  └─────────────────────────┬───────────────────────────────┘    │   │
│  └────────────────────────────┼────────────────────────────────────┘   │
│                               │                                        │
│                               ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                      Amazon S3 (Data Lake)                      │   │
│  │                                                                 │   │
│  │   s3://ml-data/training/features/*.parquet                      │   │
│  │   s3://ml-data/training/labels/*.parquet                        │   │
│  │   s3://ml-data/training/embeddings/*.parquet                    │   │
│  │                         (4 PB)                                  │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                        │
│  ┌───────────────────────┐  ┌───────────────────────────────────────┐  │
│  │   MLflow / SageMaker  │  │   Training Cluster (Spark/Ray/GPU)    │  │
│  │   Experiment Tracker  │  │   Reads from tagged snapshot          │  │
│  │   Links: run → tag    │  │   via PyIceberg / Spark               │  │
│  └───────────────────────┘  └───────────────────────────────────────┘  │
│                                                                        │
└────────────────────────────────────────────────────────────────────────┘
```

---

## Table DDL

### Training Data Table

```sql
CREATE TABLE nessie.ml.training_data (
    sample_id           STRING      NOT NULL,
    source_dataset      STRING      NOT NULL,
    ingestion_timestamp TIMESTAMP   NOT NULL,
    split               STRING,          -- train/val/test
    content_hash        STRING      NOT NULL,  -- SHA-256 of raw content
    raw_data            BINARY,
    metadata            MAP<STRING, STRING>
)
USING iceberg
PARTITIONED BY (source_dataset, days(ingestion_timestamp))
TBLPROPERTIES (
    'write.metadata.delete-after-commit.enabled' = 'false',
    'write.metadata.previous-versions-max'       = '1000',
    'history.expire.max-snapshot-age-ms'         = '31536000000',  -- 1 year
    'write.parquet.row-group-size-bytes'         = '134217728',
    'write.target-file-size-bytes'               = '536870912'
);
```

### Labels Table

```sql
CREATE TABLE nessie.ml.labels (
    sample_id           STRING      NOT NULL,
    label_type          STRING      NOT NULL,  -- classification, bbox, segmentation
    label_value         STRING      NOT NULL,
    confidence          DOUBLE,
    annotator_id        STRING,
    annotation_timestamp TIMESTAMP  NOT NULL,
    review_status       STRING      DEFAULT 'pending',  -- pending/approved/rejected
    label_version       INT         NOT NULL DEFAULT 1
)
USING iceberg
PARTITIONED BY (label_type, months(annotation_timestamp))
TBLPROPERTIES (
    'format-version'                             = '2',
    'write.delete.mode'                          = 'merge-on-read',
    'write.update.mode'                          = 'merge-on-read',
    'history.expire.max-snapshot-age-ms'         = '63072000000'  -- 2 years
);
```

### Features Table

```sql
CREATE TABLE nessie.ml.features (
    sample_id           STRING      NOT NULL,
    feature_set_name    STRING      NOT NULL,
    feature_version     INT         NOT NULL,
    computed_at         TIMESTAMP   NOT NULL,
    -- Typed feature columns (schema evolves over time)
    numeric_features    MAP<STRING, DOUBLE>,
    categorical_features MAP<STRING, STRING>,
    embedding_vector    ARRAY<FLOAT>,
    feature_hash        STRING      NOT NULL   -- deterministic hash of inputs
)
USING iceberg
PARTITIONED BY (feature_set_name, feature_version)
TBLPROPERTIES (
    'format-version'    = '2',
    'write.target-file-size-bytes' = '268435456'
);
```

### Dataset Registry

```sql
CREATE TABLE nessie.ml.dataset_registry (
    dataset_id          STRING      NOT NULL,
    dataset_name        STRING      NOT NULL,
    created_at          TIMESTAMP   NOT NULL,
    created_by          STRING      NOT NULL,
    nessie_branch       STRING      NOT NULL,
    nessie_commit_hash  STRING      NOT NULL,
    iceberg_snapshot_id LONG        NOT NULL,
    tables_included     ARRAY<STRING>  NOT NULL,
    row_counts          MAP<STRING, LONG>,
    schema_fingerprint  STRING      NOT NULL,
    quality_score       DOUBLE,
    status              STRING      DEFAULT 'active',  -- active/deprecated/poisoned
    description         STRING,
    tags                MAP<STRING, STRING>
)
USING iceberg
PARTITIONED BY (bucket(16, dataset_id));
```

---

## Nessie Workflow: Branch → Experiment → Merge

### Core Concept

Nessie provides **Git semantics for data catalogs**. Each branch points to a different version of the catalog — different table snapshots, schemas, and even different tables entirely. Branches are metadata-only (zero data copy).

### Creating Experiment Branches

```python
from pynessie import NessieClient

nessie = NessieClient(
    endpoint="http://nessie.internal:19120/api/v2",
    auth_token=os.environ["NESSIE_TOKEN"]
)

# Create experiment branch from main
main_ref = nessie.get_reference("main")
nessie.create_reference(
    reference_name="experiment/alice-new-features-v3",
    reference_type="BRANCH",
    source_reference=main_ref
)
print(f"Branch created at commit: {main_ref.hash}")
```

### Tagging a Release (Immutable Dataset Pin)

```python
# Tag the current main as a release — immutable forever
main_ref = nessie.get_reference("main")
nessie.create_reference(
    reference_name="release/training-data-2024-q4",
    reference_type="TAG",
    source_reference=main_ref
)

# This tag can NEVER be moved — guarantees reproducibility
# Any model trained on this tag will always see identical data
```

### Merging Experiment Back to Main

```python
# After validation passes, merge experiment branch
experiment_ref = nessie.get_reference("experiment/alice-new-features-v3")

merge_result = nessie.merge(
    from_ref="experiment/alice-new-features-v3",
    from_hash=experiment_ref.hash,
    to_ref="main",
    # Conflict resolution
    default_merge_behavior="NORMAL",
    merge_key_behavior={
        "ml.features": "NORMAL",  # merge normally
        "ml.labels": "DROP"       # discard label changes (needs separate review)
    }
)

if merge_result.was_successful:
    print(f"Merged to main at {merge_result.target_hash}")
    # Clean up experiment branch
    nessie.delete_reference("experiment/alice-new-features-v3")
else:
    print(f"Conflicts: {merge_result.details}")
```

### Cherry-Pick Specific Changes

```python
# Cherry-pick a single commit (e.g., a critical label fix) to a release branch
nessie.transplant(
    from_ref="main",
    hashes_to_transplant=["abc123def456"],  # specific commit hash
    to_ref="hotfix/model-v2.3-label-fix"
)
```

---

## PyIceberg: Programmatic Table Management

### Loading Tables from Specific Branches

```python
from pyiceberg.catalog.nessie import NessieCatalog

catalog = NessieCatalog(
    name="ml_catalog",
    **{
        "uri": "http://nessie.internal:19120/api/v2",
        "ref": "main",  # default branch
        "s3.endpoint": "https://s3.us-east-1.amazonaws.com",
        "s3.region": "us-east-1",
    }
)

# Load table from a specific branch
catalog.properties["ref"] = "experiment/alice-new-features-v3"
features_table = catalog.load_table("ml.features")

# Load table from a tag (reproducibility)
catalog.properties["ref"] = "release/training-data-2024-q4"
training_table = catalog.load_table("ml.training_data")
```

### Reading Data for Training

```python
import pyarrow as pa
from pyiceberg.expressions import EqualTo, GreaterThanOrEqual

# Read specific snapshot (pinned for reproducibility)
table = catalog.load_table("ml.training_data")

# Option 1: Read from tag (recommended for training)
scan = table.scan(
    row_filter=EqualTo("split", "train"),
    selected_fields=("sample_id", "content_hash", "raw_data", "metadata")
)
df = scan.to_pandas()

# Option 2: Read from specific snapshot ID (ultimate reproducibility)
snapshot_id = 7458923014726382190  # logged in MLflow
scan = table.scan(snapshot_id=snapshot_id)
arrow_table = scan.to_arrow()

# Option 3: Time travel to specific timestamp
from datetime import datetime
scan = table.scan(
    timestamp_ms=int(datetime(2024, 10, 15, 0, 0, 0).timestamp() * 1000)
)
```

### Schema Evolution for New Features

```python
from pyiceberg.schema import Schema
from pyiceberg.types import NestedField, StringType, DoubleType, ListType, FloatType

table = catalog.load_table("ml.features")

# Add new feature column without breaking existing consumers
with table.update_schema() as update:
    update.add_column(
        path="text_embedding_v2",
        field_type=ListType(element_id=101, element_type=FloatType(), element_required=False),
        doc="768-dim text embedding from model v2"
    )
    update.add_column(
        path="quality_score",
        field_type=DoubleType(),
        doc="Automated quality score [0,1]"
    )

# Old consumers still work — they just don't see new columns
# New experiments on this branch see the evolved schema
```

### Snapshot Management

```python
# List all snapshots (audit trail)
table = catalog.load_table("ml.training_data")
for snapshot in table.metadata.snapshots:
    print(f"  ID: {snapshot.snapshot_id}")
    print(f"  Timestamp: {snapshot.timestamp_ms}")
    print(f"  Operation: {snapshot.operation}")
    print(f"  Summary: {snapshot.summary}")
    print()

# Get current snapshot for MLflow logging
current_snapshot = table.current_snapshot()
print(f"Pin this in MLflow: snapshot_id={current_snapshot.snapshot_id}")
```

---

## Training from a Specific Dataset Version

### Complete Training Script with Reproducibility

```python
"""
train_model.py — Reproducible training with Iceberg dataset pinning.
"""
import os
import hashlib
import mlflow
from pyiceberg.catalog.nessie import NessieCatalog
from datetime import datetime

class ReproducibleDataLoader:
    """Loads training data from a pinned Iceberg snapshot with full lineage."""

    def __init__(self, nessie_ref: str, snapshot_id: int = None):
        self.catalog = NessieCatalog(
            name="ml_catalog",
            **{
                "uri": os.environ["NESSIE_URI"],
                "ref": nessie_ref,
                "s3.region": "us-east-1",
            }
        )
        self.nessie_ref = nessie_ref
        self.snapshot_id = snapshot_id
        self._lineage = {}

    def load_training_set(self, table_name: str, filters=None, columns=None):
        """Load data and record full lineage for reproducibility."""
        table = self.catalog.load_table(table_name)

        scan_kwargs = {}
        if self.snapshot_id:
            scan_kwargs["snapshot_id"] = self.snapshot_id
        if filters:
            scan_kwargs["row_filter"] = filters
        if columns:
            scan_kwargs["selected_fields"] = tuple(columns)

        scan = table.scan(**scan_kwargs)
        arrow_table = scan.to_arrow()

        # Record lineage
        actual_snapshot = (
            self.snapshot_id or table.current_snapshot().snapshot_id
        )
        self._lineage[table_name] = {
            "nessie_ref": self.nessie_ref,
            "snapshot_id": actual_snapshot,
            "schema_id": table.metadata.current_schema_id,
            "row_count": len(arrow_table),
            "data_hash": hashlib.sha256(
                arrow_table.to_pandas().to_json().encode()
            ).hexdigest()[:16],
            "loaded_at": datetime.utcnow().isoformat(),
        }

        return arrow_table.to_pandas()

    def log_lineage_to_mlflow(self):
        """Log complete data lineage to MLflow experiment."""
        for table_name, info in self._lineage.items():
            for key, value in info.items():
                mlflow.log_param(f"data.{table_name}.{key}", value)


def train():
    # Pin to a specific release tag
    DATASET_REF = "release/training-data-2024-q4"

    loader = ReproducibleDataLoader(nessie_ref=DATASET_REF)

    with mlflow.start_run():
        # Load data from pinned version
        features = loader.load_training_set(
            "ml.features",
            filters=EqualTo("feature_set_name", "customer_v3"),
            columns=["sample_id", "numeric_features", "embedding_vector"]
        )
        labels = loader.load_training_set(
            "ml.labels",
            filters=And(
                EqualTo("label_type", "classification"),
                EqualTo("review_status", "approved")
            ),
            columns=["sample_id", "label_value"]
        )

        # Merge features + labels
        training_df = features.merge(labels, on="sample_id", how="inner")

        # Log lineage BEFORE training
        loader.log_lineage_to_mlflow()
        mlflow.log_param("dataset_ref", DATASET_REF)
        mlflow.log_param("training_rows", len(training_df))

        # ... actual model training ...
        model = train_model(training_df)

        mlflow.sklearn.log_model(model, "model")


if __name__ == "__main__":
    train()
```

---

## A/B Dataset Comparison

### Comparing Two Dataset Versions

```python
"""
Compare two branches/tags to understand what changed in training data.
Used before merging experiment branches or debugging model regressions.
"""
from pyiceberg.catalog.nessie import NessieCatalog
import pandas as pd

def compare_dataset_versions(
    table_name: str,
    ref_a: str,    # e.g., "release/training-data-2024-q3"
    ref_b: str,    # e.g., "release/training-data-2024-q4"
) -> dict:
    """Compare two dataset versions for drift analysis."""

    results = {}

    for ref_name, ref in [("A", ref_a), ("B", ref_b)]:
        catalog = NessieCatalog(
            name="ml_catalog",
            **{"uri": os.environ["NESSIE_URI"], "ref": ref, "s3.region": "us-east-1"}
        )
        table = catalog.load_table(table_name)
        snapshot = table.current_snapshot()

        results[ref_name] = {
            "ref": ref,
            "snapshot_id": snapshot.snapshot_id,
            "schema": str(table.schema()),
            "row_count": int(snapshot.summary.get("total-records", 0)),
            "file_count": int(snapshot.summary.get("total-data-files", 0)),
            "total_size_bytes": int(snapshot.summary.get("total-files-size", 0)),
        }

    # Compute diff summary
    diff = {
        "row_count_delta": results["B"]["row_count"] - results["A"]["row_count"],
        "size_delta_gb": (
            results["B"]["total_size_bytes"] - results["A"]["total_size_bytes"]
        ) / (1024**3),
        "schema_changed": results["A"]["schema"] != results["B"]["schema"],
    }

    return {"version_a": results["A"], "version_b": results["B"], "diff": diff}


def compute_feature_drift(table_name: str, ref_a: str, ref_b: str, feature_col: str):
    """Statistical drift detection between two dataset versions."""
    from scipy import stats

    catalog_a = NessieCatalog(name="a", **{"uri": os.environ["NESSIE_URI"], "ref": ref_a, "s3.region": "us-east-1"})
    catalog_b = NessieCatalog(name="b", **{"uri": os.environ["NESSIE_URI"], "ref": ref_b, "s3.region": "us-east-1"})

    df_a = catalog_a.load_table(table_name).scan(selected_fields=(feature_col,)).to_pandas()
    df_b = catalog_b.load_table(table_name).scan(selected_fields=(feature_col,)).to_pandas()

    # KS test for distribution drift
    ks_stat, p_value = stats.ks_2samp(df_a[feature_col], df_b[feature_col])

    return {
        "feature": feature_col,
        "ks_statistic": ks_stat,
        "p_value": p_value,
        "drift_detected": p_value < 0.01,
        "mean_shift": df_b[feature_col].mean() - df_a[feature_col].mean(),
        "std_shift": df_b[feature_col].std() - df_a[feature_col].std(),
    }
```

---

## Spark Processing Pipeline

### Feature Engineering on a Branch

```python
from pyspark.sql import SparkSession

spark = SparkSession.builder \
    .appName("FeatureEngineering") \
    .config("spark.sql.catalog.nessie", "org.apache.iceberg.spark.SparkCatalog") \
    .config("spark.sql.catalog.nessie.catalog-impl", "org.apache.iceberg.nessie.NessieCatalog") \
    .config("spark.sql.catalog.nessie.uri", "http://nessie.internal:19120/api/v2") \
    .config("spark.sql.catalog.nessie.ref", "experiment/alice-new-features-v3") \
    .config("spark.sql.catalog.nessie.warehouse", "s3://ml-data/warehouse") \
    .config("spark.sql.catalog.nessie.io-impl", "org.apache.iceberg.aws.s3.S3FileIO") \
    .getOrCreate()

# Write to experiment branch (isolated from main)
spark.sql("""
    INSERT INTO nessie.ml.features
    SELECT
        t.sample_id,
        'customer_v4' AS feature_set_name,
        4 AS feature_version,
        current_timestamp() AS computed_at,
        map(
            'age_normalized', (t.age - 30.0) / 15.0,
            'income_log', ln(t.income + 1),
            'tenure_months', cast(datediff(current_date(), t.signup_date) / 30 as double)
        ) AS numeric_features,
        map(
            'segment', t.segment,
            'region', t.region
        ) AS categorical_features,
        t.embedding AS embedding_vector,
        sha2(concat_ws('|', t.sample_id, 'customer_v4', '4'), 256) AS feature_hash
    FROM nessie.ml.training_data t
    WHERE t.source_dataset = 'customers'
""")

# Validate before merge
validation_df = spark.sql("""
    SELECT
        COUNT(*) as total_rows,
        COUNT(DISTINCT sample_id) as unique_samples,
        SUM(CASE WHEN numeric_features IS NULL THEN 1 ELSE 0 END) as null_features,
        SUM(CASE WHEN feature_hash IS NULL THEN 1 ELSE 0 END) as null_hashes
    FROM nessie.ml.features
    WHERE feature_set_name = 'customer_v4'
""")
validation_df.show()
```

---

## Airflow Orchestration

### Dataset Release DAG

```python
"""
airflow/dags/dataset_release.py
Orchestrates: validate → tag → register → notify
"""
from airflow import DAG
from airflow.operators.python import PythonOperator, BranchPythonOperator
from airflow.utils.dates import days_ago
from datetime import timedelta

default_args = {
    "owner": "ml-platform",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}

dag = DAG(
    "dataset_release_pipeline",
    default_args=default_args,
    schedule_interval="@weekly",
    start_date=days_ago(1),
    catchup=False,
    tags=["ml", "data-versioning"],
)


def run_quality_gates(**context):
    """Execute all quality checks before releasing a dataset."""
    from pyiceberg.catalog.nessie import NessieCatalog
    from pynessie import NessieClient

    catalog = NessieCatalog(
        name="ml", **{"uri": NESSIE_URI, "ref": "main", "s3.region": "us-east-1"}
    )

    checks = {}

    # Check 1: Row count regression
    table = catalog.load_table("ml.training_data")
    current_count = int(table.current_snapshot().summary["total-records"])
    previous_count = int(table.metadata.snapshots[-2].summary["total-records"])
    checks["row_count_regression"] = current_count >= previous_count * 0.95

    # Check 2: Schema compatibility
    checks["schema_valid"] = table.metadata.current_schema_id >= 0

    # Check 3: No NULL primary keys
    scan = table.scan(row_filter=IsNull("sample_id"))
    null_count = len(scan.to_arrow())
    checks["no_null_keys"] = null_count == 0

    # Check 4: Label distribution stability
    labels_table = catalog.load_table("ml.labels")
    # ... statistical tests ...
    checks["label_distribution_stable"] = True  # simplified

    all_passed = all(checks.values())
    context["ti"].xcom_push(key="quality_checks", value=checks)
    context["ti"].xcom_push(key="all_passed", value=all_passed)

    return "create_release_tag" if all_passed else "notify_failure"


def create_release_tag(**context):
    """Create immutable tag for the release."""
    from pynessie import NessieClient
    from datetime import datetime

    nessie = NessieClient(endpoint=NESSIE_URI)
    tag_name = f"release/training-data-{datetime.now().strftime('%Y-%m-%d')}"

    main_ref = nessie.get_reference("main")
    nessie.create_reference(
        reference_name=tag_name,
        reference_type="TAG",
        source_reference=main_ref
    )

    context["ti"].xcom_push(key="release_tag", value=tag_name)
    context["ti"].xcom_push(key="commit_hash", value=main_ref.hash)


def register_dataset(**context):
    """Register the release in the dataset registry."""
    from pyiceberg.catalog.nessie import NessieCatalog
    import uuid

    tag_name = context["ti"].xcom_pull(key="release_tag")
    commit_hash = context["ti"].xcom_pull(key="commit_hash")

    catalog = NessieCatalog(
        name="ml", **{"uri": NESSIE_URI, "ref": "main", "s3.region": "us-east-1"}
    )
    registry = catalog.load_table("ml.dataset_registry")

    # ... append row to registry ...


quality_gate = BranchPythonOperator(
    task_id="quality_gates",
    python_callable=run_quality_gates,
    dag=dag,
)

tag_task = PythonOperator(
    task_id="create_release_tag",
    python_callable=create_release_tag,
    dag=dag,
)

register_task = PythonOperator(
    task_id="register_dataset",
    python_callable=register_dataset,
    dag=dag,
)

notify_failure = PythonOperator(
    task_id="notify_failure",
    python_callable=lambda **ctx: send_alert(ctx),
    dag=dag,
)

quality_gate >> [tag_task, notify_failure]
tag_task >> register_task
```

---

## Production Safeguards

### Dataset Poisoning Prevention

```python
"""
Quality gates that run before ANY merge to main.
Prevents accidental or malicious data corruption.
"""

class DatasetPoisoningDetector:
    """Detects anomalous changes that could indicate data poisoning."""

    def __init__(self, catalog, baseline_ref: str, candidate_ref: str):
        self.catalog = catalog
        self.baseline_ref = baseline_ref
        self.candidate_ref = candidate_ref

    def check_label_flip_rate(self, table_name: str, max_flip_rate: float = 0.05):
        """
        Detect if too many labels changed between versions.
        A poisoning attack often flips labels to degrade model performance.
        """
        self.catalog.properties["ref"] = self.baseline_ref
        baseline = self.catalog.load_table(table_name).scan(
            selected_fields=("sample_id", "label_value")
        ).to_pandas()

        self.catalog.properties["ref"] = self.candidate_ref
        candidate = self.catalog.load_table(table_name).scan(
            selected_fields=("sample_id", "label_value")
        ).to_pandas()

        merged = baseline.merge(candidate, on="sample_id", suffixes=("_old", "_new"))
        flipped = merged[merged["label_value_old"] != merged["label_value_new"]]
        flip_rate = len(flipped) / len(merged)

        return {
            "passed": flip_rate <= max_flip_rate,
            "flip_rate": flip_rate,
            "flipped_count": len(flipped),
            "threshold": max_flip_rate,
        }

    def check_distribution_shift(self, table_name: str, feature_cols: list):
        """Detect sudden distribution shifts that indicate injected data."""
        from scipy.stats import ks_2samp

        results = []
        for col in feature_cols:
            self.catalog.properties["ref"] = self.baseline_ref
            baseline_vals = self.catalog.load_table(table_name).scan(
                selected_fields=(col,)
            ).to_pandas()[col]

            self.catalog.properties["ref"] = self.candidate_ref
            candidate_vals = self.catalog.load_table(table_name).scan(
                selected_fields=(col,)
            ).to_pandas()[col]

            stat, p_value = ks_2samp(baseline_vals.dropna(), candidate_vals.dropna())
            results.append({
                "feature": col,
                "ks_stat": stat,
                "p_value": p_value,
                "anomalous": p_value < 0.001,  # very strict threshold
            })

        anomalous_features = [r for r in results if r["anomalous"]]
        return {
            "passed": len(anomalous_features) == 0,
            "anomalous_features": anomalous_features,
        }

    def check_volume_anomaly(self, table_name: str, max_growth_rate: float = 0.3):
        """Detect abnormal data volume changes (injection or deletion)."""
        self.catalog.properties["ref"] = self.baseline_ref
        baseline_table = self.catalog.load_table(table_name)
        baseline_count = int(
            baseline_table.current_snapshot().summary["total-records"]
        )

        self.catalog.properties["ref"] = self.candidate_ref
        candidate_table = self.catalog.load_table(table_name)
        candidate_count = int(
            candidate_table.current_snapshot().summary["total-records"]
        )

        growth_rate = abs(candidate_count - baseline_count) / baseline_count

        return {
            "passed": growth_rate <= max_growth_rate,
            "baseline_count": baseline_count,
            "candidate_count": candidate_count,
            "growth_rate": growth_rate,
            "threshold": max_growth_rate,
        }


def pre_merge_validation(candidate_branch: str) -> bool:
    """
    Mandatory validation before any branch merges to main.
    Called by CI/CD or Airflow before nessie.merge().
    """
    catalog = NessieCatalog(name="ml", **{"uri": NESSIE_URI, "s3.region": "us-east-1"})
    detector = DatasetPoisoningDetector(catalog, "main", candidate_branch)

    checks = [
        detector.check_label_flip_rate("ml.labels"),
        detector.check_volume_anomaly("ml.training_data"),
        detector.check_distribution_shift("ml.features", ["income_log", "age_normalized"]),
    ]

    all_passed = all(c["passed"] for c in checks)

    if not all_passed:
        failed = [c for c in checks if not c["passed"]]
        raise DataPoisoningAlert(
            f"Pre-merge validation FAILED for {candidate_branch}: {failed}"
        )

    return True
```

### Schema Validation Gate

```python
def validate_schema_compatibility(branch: str, table_name: str):
    """
    Ensure schema changes on experiment branches are backward-compatible.
    Prevents breaking production model input pipelines.
    """
    catalog = NessieCatalog(name="ml", **{"uri": NESSIE_URI, "s3.region": "us-east-1"})

    catalog.properties["ref"] = "main"
    main_schema = catalog.load_table(table_name).schema()

    catalog.properties["ref"] = branch
    branch_schema = catalog.load_table(table_name).schema()

    # Check: no columns removed
    main_fields = {f.name for f in main_schema.fields}
    branch_fields = {f.name for f in branch_schema.fields}
    removed = main_fields - branch_fields
    if removed:
        raise SchemaBreakingChange(f"Columns removed: {removed}")

    # Check: no type changes on existing columns
    for field in main_schema.fields:
        branch_field = branch_schema.find_field(field.field_id)
        if branch_field and branch_field.field_type != field.field_type:
            raise SchemaBreakingChange(
                f"Type changed for {field.name}: {field.field_type} → {branch_field.field_type}"
            )

    # Additions are always safe
    added = branch_fields - main_fields
    if added:
        print(f"New columns (safe): {added}")

    return True
```

---

## Reproducibility Guarantees

### How to Pin Exact Dataset Version for Any Experiment

The system provides **three levels** of reproducibility:

```
Level 1 (Recommended): Nessie Tag
    - Create: release/dataset-2024-q4
    - Immutable: tag cannot be moved
    - Contains: exact catalog state (all table snapshots)
    - Usage: catalog.properties["ref"] = "release/dataset-2024-q4"

Level 2 (Maximum precision): Snapshot ID per table
    - Record: snapshot_id=7458923014726382190 for each table
    - Survives: even if tag is accidentally deleted
    - Usage: table.scan(snapshot_id=7458923014726382190)
    - Store in: MLflow params

Level 3 (Cryptographic): Data content hash
    - Compute: SHA-256 of sorted DataFrame bytes
    - Verifies: no bit-level corruption
    - Store in: MLflow params + dataset_registry
```

### MLflow Integration for Full Lineage

```python
def log_dataset_lineage(mlflow_run_id: str, tables: dict[str, int]):
    """
    Log complete dataset lineage to MLflow.
    tables: {"ml.training_data": snapshot_id, "ml.labels": snapshot_id, ...}
    """
    with mlflow.start_run(run_id=mlflow_run_id):
        mlflow.log_params({
            "data.nessie_ref": DATASET_REF,
            "data.nessie_commit": nessie.get_reference(DATASET_REF).hash,
            "data.pin_timestamp": datetime.utcnow().isoformat(),
        })
        for table_name, snap_id in tables.items():
            safe_name = table_name.replace(".", "_")
            mlflow.log_param(f"data.{safe_name}.snapshot_id", snap_id)

        # Tag the run with dataset version for search
        mlflow.set_tag("dataset_version", DATASET_REF)
```

### Reproducing Any Historical Experiment

```python
def reproduce_experiment(mlflow_run_id: str):
    """
    Given any MLflow run ID, reconstruct the exact training data.
    This is the key guarantee: any model can be reproduced.
    """
    run = mlflow.get_run(mlflow_run_id)
    params = run.data.params

    nessie_ref = params["data.nessie_ref"]
    snapshot_ids = {
        k.replace("data.", "").replace("_snapshot_id", "").replace("_", "."):
        int(v)
        for k, v in params.items()
        if k.endswith("_snapshot_id")
    }

    catalog = NessieCatalog(
        name="ml", **{"uri": NESSIE_URI, "ref": nessie_ref, "s3.region": "us-east-1"}
    )

    datasets = {}
    for table_name, snap_id in snapshot_ids.items():
        table = catalog.load_table(table_name)
        datasets[table_name] = table.scan(snapshot_id=snap_id).to_pandas()

    return datasets
```

---

## Scale Considerations

### Operating at PB Scale with 1000s of Experiments/Day

| Challenge | Solution |
|---|---|
| Metadata explosion (1000s branches) | Nessie GC: auto-delete merged branches after 7 days |
| Snapshot accumulation | Retain tagged snapshots forever; expire untagged after 30 days |
| S3 list operations at scale | Iceberg manifest files eliminate S3 LIST calls |
| Concurrent branch writes | Nessie MVCC — no lock contention between experiments |
| Large scans for training | Partition pruning + column projection via PyIceberg |
| Cross-region training | S3 replication + region-local Nessie read replicas |

### Snapshot Expiry Policy

```sql
-- Keep snapshots referenced by tags forever
-- Expire unreferenced snapshots after 30 days (saves metadata bloat)
-- Never expire snapshots in dataset_registry

ALTER TABLE nessie.ml.training_data SET TBLPROPERTIES (
    'history.expire.max-snapshot-age-ms' = '2592000000',   -- 30 days
    'history.expire.min-snapshots-to-keep' = '50'
);

-- CRITICAL: This does NOT delete data files still referenced by tags/branches
-- Iceberg only deletes orphaned data files during explicit orphan removal
```

### Nessie GC Configuration

```yaml
# nessie-gc.yaml — runs as periodic CronJob
nessie:
  gc:
    # Delete branches merged >7 days ago
    expired-branch-cleanup:
      enabled: true
      max-age-days: 7
      exclude-patterns:
        - "release/*"
        - "main"
        - "production/*"

    # Compact Nessie commit log
    commit-log-compaction:
      enabled: true
      # Keep full history for tags
      preserve-tagged-commits: true
```

---

## dbt Integration for Feature Transforms

### Feature Pipeline as dbt Models

```sql
-- models/features/customer_features_v4.sql
{{
    config(
        materialized='incremental',
        file_format='iceberg',
        catalog='nessie',
        schema='ml',
        incremental_strategy='merge',
        unique_key='sample_id',
        properties={
            'write.target-file-size-bytes': '268435456'
        }
    )
}}

WITH base AS (
    SELECT
        sample_id,
        raw_data,
        metadata
    FROM {{ source('ml', 'training_data') }}
    WHERE source_dataset = 'customers'
    {% if is_incremental() %}
        AND ingestion_timestamp > (SELECT MAX(computed_at) FROM {{ this }})
    {% endif %}
),

computed AS (
    SELECT
        sample_id,
        'customer_v4' AS feature_set_name,
        4 AS feature_version,
        CURRENT_TIMESTAMP() AS computed_at,
        MAP(
            'recency_days', DATEDIFF(CURRENT_DATE(), last_activity_date),
            'frequency', transaction_count,
            'monetary', total_spend
        ) AS numeric_features,
        MAP('segment', customer_segment) AS categorical_features,
        NULL AS embedding_vector,
        SHA2(CONCAT(sample_id, '|customer_v4|4'), 256) AS feature_hash
    FROM base
)

SELECT * FROM computed
```

---

## SageMaker Integration

### Training Job with Pinned Dataset

```python
import sagemaker
from sagemaker.estimator import Estimator

def launch_training_job(dataset_tag: str, experiment_name: str):
    """Launch SageMaker training job with pinned Iceberg dataset."""

    estimator = Estimator(
        image_uri="123456789.dkr.ecr.us-east-1.amazonaws.com/ml-training:latest",
        role="arn:aws:iam::123456789:role/SageMakerExecutionRole",
        instance_count=4,
        instance_type="ml.p4d.24xlarge",
        hyperparameters={
            "nessie_ref": dataset_tag,
            "nessie_uri": "http://nessie.internal:19120/api/v2",
            "table_name": "ml.features",
            "feature_set": "customer_v4",
            "epochs": 50,
            "batch_size": 2048,
        },
        environment={
            "NESSIE_TOKEN": "{{resolve:secretsmanager:nessie-token}}",
        },
        tags=[
            {"Key": "dataset_version", "Value": dataset_tag},
            {"Key": "experiment", "Value": experiment_name},
        ],
    )

    estimator.fit(wait=False)
    return estimator.latest_training_job.name
```

---

## Operational Runbooks

### Runbook: Fixing Bad Labels Without Breaking Production

```
Scenario: 50K labels discovered to be incorrect.
Constraint: 3 production models trained on these labels must NOT be affected.

Steps:
1. Identify affected production models and their dataset tags
   → Models use: release/training-data-2024-q3 (tag is IMMUTABLE — safe)

2. Create fix branch from main
   → nessie.create_reference("fix/label-correction-batch-42", from="main")

3. Apply corrections on the fix branch
   → UPDATE ml.labels SET label_value = ... WHERE sample_id IN (...)
   → Only visible on fix/label-correction-batch-42

4. Run poisoning detection against main
   → pre_merge_validation("fix/label-correction-batch-42")

5. Merge to main (production models unaffected — they read from tags)
   → nessie.merge("fix/label-correction-batch-42", to="main")

6. Create new release tag
   → nessie.create_reference("release/training-data-2024-q4", type=TAG, from=main)

7. Retrain models against new tag when ready
   → New models trained on release/training-data-2024-q4
   → Old models still reproducible from release/training-data-2024-q3
```

### Runbook: Debugging Model Regression

```
Scenario: Model v3.1 performing worse than v3.0 in production.

Steps:
1. Pull dataset versions from MLflow
   v3.0: release/training-data-2024-q3, snapshot_id=111
   v3.1: release/training-data-2024-q4, snapshot_id=222

2. Run A/B comparison
   → compare_dataset_versions("ml.features", ref_a, ref_b)
   → compute_feature_drift("ml.features", ref_a, ref_b, "income_log")

3. If data drift detected: root-cause which commits introduced the shift
   → nessie.get_commit_log("main", from=q3_hash, to=q4_hash)

4. If specific commit is problematic: revert or cherry-pick fix
   → nessie.transplant(fix_commit, to="hotfix/v3.1-data-fix")

5. Retrain from corrected data, validate, deploy
```

---

## Summary

| Capability | Implementation |
|---|---|
| Dataset versioning | Nessie tags (immutable) |
| Experiment isolation | Nessie branches (zero-copy) |
| Reproducibility | Snapshot ID + tag + content hash logged to MLflow |
| Safe mutation | Branch → validate → merge workflow |
| Poisoning prevention | Pre-merge quality gates (distribution, volume, flip rate) |
| Schema evolution | Iceberg native (additive changes only to main) |
| Scale (4 PB) | Partition pruning, manifest-based planning, no S3 LIST |
| 1000s experiments/day | MVCC branches, no lock contention |
| Feature drift detection | KS-test between tagged versions |
| Lineage | MLflow params → Nessie ref → Iceberg snapshot → S3 files |
