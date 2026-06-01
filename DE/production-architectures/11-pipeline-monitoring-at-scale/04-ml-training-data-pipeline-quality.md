# ML Training Data Pipeline Quality Monitoring

## Problem Statement

Bad training data produces bad models which produce bad business decisions. At scale—training on 100TB+ datasets daily—silent data corruption can degrade model performance without any obvious error. Unlike application bugs that crash loudly, data quality issues are insidious: a subtle shift in feature distributions, a labeling inconsistency, or a join that introduces future information can silently destroy model accuracy over weeks.

The consequences are severe:
- A recommendation model trained on corrupted click data loses $2M/day in revenue
- A fraud model with label drift misses 15% more fraudulent transactions
- A credit scoring model with feature leakage passes regulatory audit but fails in production

Training data pipelines involve complex ETL spanning dozens of systems, and each transformation is an opportunity for subtle bugs that only manifest as gradual model degradation.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    ML TRAINING DATA PIPELINE WITH MONITORING                      │
└─────────────────────────────────────────────────────────────────────────────────┘

 ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐
 │ Clickstr.│   │  Logs    │   │ 3rd Party│   │ Labeled  │   │ Feature  │
 │  Events  │   │  (S3)    │   │   APIs   │   │  Data    │   │  Store   │
 └────┬─────┘   └────┬─────┘   └────┬─────┘   └────┬─────┘   └────┬─────┘
      │               │               │               │               │
      ▼               ▼               ▼               ▼               ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         INGESTION LAYER (Spark/Airflow)                       │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  MONITOR: Schema validation, row counts, freshness, null rates      │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    CLEANING & TRANSFORMATION (Spark/dbt)                      │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  MONITOR: Dedup rates, outlier removal %, transformation invertibility│   │
│  └─────────────────────────────────────────────────────────────────────┘    │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    FEATURE ENGINEERING (Spark/Feast)                           │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  MONITOR: Feature distributions, correlation changes, leakage tests  │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    TRAIN/TEST SPLIT + VALIDATION                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  MONITOR: Split ratio stability, class balance, temporal correctness  │   │
│  └─────────────────────────────────────────────────────────────────────┘    │
└──────────────────────────┬────────────────────────┬─────────────────────────┘
                           │                        │
                           ▼                        ▼
                   ┌──────────────┐         ┌──────────────┐
                   │   Training   │         │  Validation  │
                   │    (GPU)     │         │   Dataset    │
                   └──────┬───────┘         └──────────────┘
                          │
                          ▼
                   ┌──────────────┐
                   │    Model     │
                   │   Registry   │◄──── Data quality metadata attached
                   │  (MLflow)    │
                   └──────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                     MONITORING & OBSERVABILITY LAYER                          │
│                                                                              │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────────────┐   │
│  │   Great    │  │  Evidently │  │   MLflow   │  │  Custom Drift      │   │
│  │Expectations│  │     AI     │  │  Tracking  │  │  Detectors         │   │
│  └────────────┘  └────────────┘  └────────────┘  └────────────────────┘   │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────┐     │
│  │  Alerting: PagerDuty / Slack / Training Job Blocking               │     │
│  └────────────────────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Top Monitoring Challenges

### 1. Data Drift Detection

Training data distribution diverges from production serving data over time. A model trained on summer data performs poorly in winter because user behavior shifts.

```
Training Distribution          Production Distribution (3 months later)

    ▓▓▓▓                              ▓▓
    ▓▓▓▓▓▓                          ▓▓▓▓▓▓▓▓
    ▓▓▓▓▓▓▓▓                      ▓▓▓▓▓▓▓▓▓▓▓▓
  ▓▓▓▓▓▓▓▓▓▓▓▓                  ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
──────────────────────        ──────────────────────
   Feature X                       Feature X
   mean=5.2, std=1.1              mean=7.8, std=2.3
                                   ⚠️ PSI = 0.35 (HIGH DRIFT)
```

### 2. Label Quality Degradation

Human labelers become inconsistent over time due to fatigue, guideline ambiguity, or team rotation. Inter-annotator agreement drops from 95% to 72% over 6 months.

### 3. Feature Leakage Detection

Information from the future leaks into training features. Example: using `account_status=closed` to predict `will_churn`—the status was set *after* the churn event.

### 4. Dataset Versioning and Reproducibility

Without strict versioning, you cannot reproduce a model from 3 months ago. DVC + content-addressable storage ensures byte-for-byte reproducibility.

### 5. Training/Serving Skew

Features computed differently in batch training vs real-time serving. Example: training uses 30-day rolling average computed in Spark; serving uses an approximation from Redis.

### 6. Class Imbalance Drift

Fraud rate drops from 1.2% to 0.4% due to seasonal patterns, making the model overfit to the majority class without rebalancing.

### 7. Pipeline Reproducibility

Non-deterministic operations (random shuffles, floating-point ordering) mean the same input produces different output, making debugging impossible.

---

## Data Quality Gates

Automated checks that BLOCK training if quality thresholds are not met:

```
┌─────────────────────────────────────────────────────────────┐
│                    QUALITY GATE WORKFLOW                      │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Dataset Ready ──► Schema Check ──► Stats Check ──►         │
│                         │                │                   │
│                    FAIL │           FAIL │                   │
│                         ▼                ▼                   │
│                   Block + Alert    Block + Alert             │
│                                                              │
│  ──► Null Check ──► Dedup Check ──► Drift Check ──►         │
│           │               │               │                  │
│      FAIL │          FAIL │          FAIL │                  │
│           ▼               ▼               ▼                  │
│     Block + Alert   Block + Alert   Block + Alert            │
│                                                              │
│  ──► Correlation Check ──► PASS ──► Training Begins         │
│           │                                                  │
│      FAIL │                                                  │
│           ▼                                                  │
│     Block + Alert                                            │
└─────────────────────────────────────────────────────────────┘
```

### Gate Thresholds

| Gate | Metric | Block Threshold | Warn Threshold |
|------|--------|----------------|----------------|
| Schema | Missing columns | Any | - |
| Schema | Type mismatch | Any | - |
| Stats | Mean deviation from baseline | > 3 std | > 2 std |
| Nulls | Null rate per column | > 5% (critical cols) | > 1% |
| Duplicates | Exact duplicate rows | > 0.1% | > 0.01% |
| Drift | PSI score | > 0.25 | > 0.1 |
| Correlation | Feature-target correlation change | > 0.3 | > 0.15 |
| Size | Row count vs expected | ±30% | ±15% |

---

## Production Code Examples

### Great Expectations Suite for Training Data

```python
"""
training_data_quality_suite.py
Comprehensive validation suite for ML training datasets.
"""
import great_expectations as gx
from great_expectations.core import ExpectationSuite
from great_expectations.checkpoint import Checkpoint


def build_training_data_suite(context: gx.DataContext) -> ExpectationSuite:
    """Build a quality suite for the training dataset."""
    
    suite = context.add_expectation_suite("ml_training_quality_v2")
    
    # Schema expectations
    suite.add_expectation(
        gx.expectations.ExpectTableColumnsToMatchSet(
            column_set=[
                "user_id", "timestamp", "feature_1", "feature_2",
                "feature_3", "feature_4", "label", "split"
            ],
            exact_match=True
        )
    )
    
    # Type expectations
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToBeOfType(
            column="timestamp", type_="TIMESTAMP"
        )
    )
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToBeOfType(
            column="label", type_="INTEGER"
        )
    )
    
    # Null rate expectations (critical columns must have <1% nulls)
    for col in ["user_id", "timestamp", "label"]:
        suite.add_expectation(
            gx.expectations.ExpectColumnValuesToNotBeNull(
                column=col, mostly=0.99
            )
        )
    
    # Feature columns allow up to 5% nulls
    for col in ["feature_1", "feature_2", "feature_3", "feature_4"]:
        suite.add_expectation(
            gx.expectations.ExpectColumnValuesToNotBeNull(
                column=col, mostly=0.95
            )
        )
    
    # Range expectations
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToBeBetween(
            column="feature_1", min_value=-10.0, max_value=10.0, mostly=0.99
        )
    )
    
    # Label distribution (binary classification)
    suite.add_expectation(
        gx.expectations.ExpectColumnDistinctValuesToBeInSet(
            column="label", value_set=[0, 1]
        )
    )
    
    # Class balance check (positive rate between 0.5% and 5%)
    suite.add_expectation(
        gx.expectations.ExpectColumnProportionOfUniqueValuesToBeBetween(
            column="label", min_value=0.005, max_value=0.05
        )
    )
    
    # Duplicate detection
    suite.add_expectation(
        gx.expectations.ExpectCompoundColumnsToBeUnique(
            column_list=["user_id", "timestamp"]
        )
    )
    
    # Statistical profile checks
    suite.add_expectation(
        gx.expectations.ExpectColumnMeanToBeBetween(
            column="feature_1", min_value=4.0, max_value=6.5
        )
    )
    suite.add_expectation(
        gx.expectations.ExpectColumnStdevToBeBetween(
            column="feature_1", min_value=0.5, max_value=2.5
        )
    )
    
    # Row count expectation
    suite.add_expectation(
        gx.expectations.ExpectTableRowCountToBeBetween(
            min_value=50_000_000, max_value=200_000_000
        )
    )
    
    return suite


def run_quality_gate(context: gx.DataContext, dataset_path: str) -> bool:
    """Run quality gate and return pass/fail."""
    
    checkpoint = Checkpoint(
        name="training_quality_gate",
        data_context=context,
        validations=[
            {
                "batch_request": {
                    "datasource_name": "training_data",
                    "data_asset_name": "daily_training_set",
                    "options": {"path": dataset_path}
                },
                "expectation_suite_name": "ml_training_quality_v2",
            }
        ],
        action_list=[
            {"name": "store_result", "action": {"class_name": "StoreValidationResultAction"}},
            {"name": "slack_alert", "action": {
                "class_name": "SlackNotificationAction",
                "slack_webhook": "${SLACK_WEBHOOK}",
                "notify_on": "failure"
            }},
        ]
    )
    
    result = checkpoint.run()
    return result.success
```

### Custom Data Drift Detector (PSI + KL-Divergence)

```python
"""
drift_detector.py
Detects distribution shift between training baseline and current data.
Uses Population Stability Index (PSI) and KL-Divergence.
"""
import numpy as np
from scipy.stats import entropy
from dataclasses import dataclass
from typing import Dict, List, Tuple
import logging

logger = logging.getLogger(__name__)


@dataclass
class DriftResult:
    feature: str
    psi_score: float
    kl_divergence: float
    drift_detected: bool
    severity: str  # "none", "warning", "critical"
    baseline_stats: Dict
    current_stats: Dict


class DataDriftDetector:
    """
    Monitors feature distribution drift using PSI and KL-divergence.
    
    PSI Interpretation:
      < 0.1  : No significant shift
      0.1-0.2: Moderate shift (warning)
      > 0.2  : Significant shift (critical, block training)
    """
    
    PSI_WARN_THRESHOLD = 0.1
    PSI_CRITICAL_THRESHOLD = 0.2
    N_BINS = 20
    EPSILON = 1e-6  # Avoid log(0)
    
    def __init__(self, baseline_profiles: Dict[str, np.ndarray]):
        """
        Args:
            baseline_profiles: Dict mapping feature name to baseline values array
        """
        self.baseline_histograms = {}
        self.baseline_stats = {}
        
        for feature, values in baseline_profiles.items():
            hist, bin_edges = np.histogram(values, bins=self.N_BINS, density=True)
            hist = hist + self.EPSILON  # Smooth
            hist = hist / hist.sum()   # Normalize
            self.baseline_histograms[feature] = (hist, bin_edges)
            self.baseline_stats[feature] = {
                "mean": float(np.mean(values)),
                "std": float(np.std(values)),
                "p5": float(np.percentile(values, 5)),
                "p50": float(np.percentile(values, 50)),
                "p95": float(np.percentile(values, 95)),
            }
    
    def calculate_psi(
        self, baseline_hist: np.ndarray, current_hist: np.ndarray
    ) -> float:
        """Calculate Population Stability Index."""
        psi = np.sum(
            (current_hist - baseline_hist) * np.log(current_hist / baseline_hist)
        )
        return float(psi)
    
    def calculate_kl_divergence(
        self, baseline_hist: np.ndarray, current_hist: np.ndarray
    ) -> float:
        """Calculate KL-Divergence (baseline || current)."""
        return float(entropy(baseline_hist, current_hist))
    
    def detect_drift(
        self, current_data: Dict[str, np.ndarray]
    ) -> List[DriftResult]:
        """
        Detect drift across all monitored features.
        
        Args:
            current_data: Dict mapping feature name to current values array
            
        Returns:
            List of DriftResult for each feature
        """
        results = []
        
        for feature, values in current_data.items():
            if feature not in self.baseline_histograms:
                logger.warning(f"Feature '{feature}' not in baseline, skipping")
                continue
            
            baseline_hist, bin_edges = self.baseline_histograms[feature]
            
            # Compute histogram for current data using same bin edges
            current_hist, _ = np.histogram(values, bins=bin_edges, density=True)
            current_hist = current_hist + self.EPSILON
            current_hist = current_hist / current_hist.sum()
            
            psi = self.calculate_psi(baseline_hist, current_hist)
            kl_div = self.calculate_kl_divergence(baseline_hist, current_hist)
            
            # Determine severity
            if psi > self.PSI_CRITICAL_THRESHOLD:
                severity = "critical"
                drift_detected = True
            elif psi > self.PSI_WARN_THRESHOLD:
                severity = "warning"
                drift_detected = True
            else:
                severity = "none"
                drift_detected = False
            
            current_stats = {
                "mean": float(np.mean(values)),
                "std": float(np.std(values)),
                "p5": float(np.percentile(values, 5)),
                "p50": float(np.percentile(values, 50)),
                "p95": float(np.percentile(values, 95)),
            }
            
            results.append(DriftResult(
                feature=feature,
                psi_score=psi,
                kl_divergence=kl_div,
                drift_detected=drift_detected,
                severity=severity,
                baseline_stats=self.baseline_stats[feature],
                current_stats=current_stats,
            ))
            
            if drift_detected:
                logger.warning(
                    f"Drift detected in '{feature}': PSI={psi:.4f} "
                    f"({severity}), KL={kl_div:.4f}"
                )
        
        return results
    
    def should_block_training(self, results: List[DriftResult]) -> Tuple[bool, str]:
        """Determine if training should be blocked based on drift results."""
        critical_features = [r for r in results if r.severity == "critical"]
        warning_features = [r for r in results if r.severity == "warning"]
        
        if critical_features:
            features_str = ", ".join(r.feature for r in critical_features)
            return True, f"Critical drift in: {features_str}"
        
        if len(warning_features) > len(results) * 0.3:
            return True, f"Warning drift in >30% of features ({len(warning_features)}/{len(results)})"
        
        return False, "All checks passed"
```

### MLflow Integration for Data Quality Tracking

```python
"""
mlflow_quality_tracker.py
Logs data quality metrics alongside model training metrics in MLflow.
"""
import mlflow
from typing import Dict, List
from drift_detector import DriftResult


class MLflowQualityTracker:
    """Track data quality metrics per training run in MLflow."""
    
    def __init__(self, experiment_name: str):
        mlflow.set_experiment(experiment_name)
    
    def log_quality_metrics(
        self,
        run_id: str,
        drift_results: List[DriftResult],
        dataset_stats: Dict,
        validation_result: Dict,
    ):
        """Log comprehensive data quality metrics to an MLflow run."""
        
        with mlflow.start_run(run_id=run_id):
            # Dataset-level metrics
            mlflow.log_metrics({
                "data/row_count": dataset_stats["row_count"],
                "data/null_rate_overall": dataset_stats["null_rate"],
                "data/duplicate_rate": dataset_stats["duplicate_rate"],
                "data/positive_class_rate": dataset_stats["positive_rate"],
            })
            
            # Per-feature drift metrics
            for result in drift_results:
                prefix = f"drift/{result.feature}"
                mlflow.log_metrics({
                    f"{prefix}/psi": result.psi_score,
                    f"{prefix}/kl_divergence": result.kl_divergence,
                    f"{prefix}/mean_shift": abs(
                        result.current_stats["mean"] - result.baseline_stats["mean"]
                    ),
                })
            
            # Aggregate drift metrics
            psi_scores = [r.psi_score for r in drift_results]
            mlflow.log_metrics({
                "drift/max_psi": max(psi_scores),
                "drift/mean_psi": sum(psi_scores) / len(psi_scores),
                "drift/features_drifted": sum(1 for r in drift_results if r.drift_detected),
            })
            
            # Validation results
            mlflow.log_metrics({
                "validation/expectations_passed": validation_result["passed"],
                "validation/expectations_failed": validation_result["failed"],
                "validation/success_rate": validation_result["success_rate"],
            })
            
            # Tag the run with quality status
            max_psi = max(psi_scores)
            if max_psi > 0.2:
                mlflow.set_tag("data_quality", "critical_drift")
            elif max_psi > 0.1:
                mlflow.set_tag("data_quality", "moderate_drift")
            else:
                mlflow.set_tag("data_quality", "healthy")
            
            # Log dataset version
            mlflow.log_param("dataset_version", dataset_stats["version"])
            mlflow.log_param("dataset_path", dataset_stats["path"])
```

### Airflow DAG with Quality Gates

```python
"""
training_pipeline_dag.py
Airflow DAG that enforces quality gates before model training.
"""
from airflow import DAG
from airflow.operators.python import PythonOperator, BranchPythonOperator
from airflow.operators.dummy import DummyOperator
from airflow.utils.dates import days_ago
from datetime import timedelta


default_args = {
    "owner": "ml-platform",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
    "execution_timeout": timedelta(hours=4),
}


def run_ingestion(**context):
    """Ingest raw data from sources into staging."""
    from ingestion import ingest_training_data
    
    ds = context["ds"]
    stats = ingest_training_data(date=ds)
    context["ti"].xcom_push(key="ingestion_stats", value=stats)
    return stats


def run_quality_gate(**context):
    """Run quality checks and decide whether to proceed."""
    from quality_gate import QualityGate
    
    ds = context["ds"]
    gate = QualityGate(date=ds)
    result = gate.run_all_checks()
    
    context["ti"].xcom_push(key="quality_result", value=result)
    
    if result["passed"]:
        return "proceed_to_feature_engineering"
    else:
        return "block_training_and_alert"


def run_feature_engineering(**context):
    """Compute features from cleaned data."""
    from features import compute_features
    
    ds = context["ds"]
    compute_features(date=ds)


def run_drift_detection(**context):
    """Check for distribution drift against baseline."""
    from drift_detector import DataDriftDetector
    import numpy as np
    
    ds = context["ds"]
    # Load baseline and current profiles
    detector = DataDriftDetector.from_baseline(date=ds)
    results = detector.detect_drift_from_date(date=ds)
    
    block, reason = detector.should_block_training(results)
    context["ti"].xcom_push(key="drift_results", value={
        "block": block,
        "reason": reason,
        "features_drifted": sum(1 for r in results if r.drift_detected),
    })
    
    if block:
        return "block_training_and_alert"
    return "proceed_to_training"


def run_training(**context):
    """Execute model training."""
    from training import train_model
    
    ds = context["ds"]
    quality_result = context["ti"].xcom_pull(key="quality_result")
    drift_results = context["ti"].xcom_pull(key="drift_results")
    
    train_model(
        date=ds,
        quality_metadata=quality_result,
        drift_metadata=drift_results,
    )


def alert_and_block(**context):
    """Send alerts when quality gate fails."""
    from alerting import send_pagerduty_alert, send_slack_notification
    
    quality_result = context["ti"].xcom_pull(key="quality_result")
    drift_results = context["ti"].xcom_pull(key="drift_results")
    
    send_slack_notification(
        channel="#ml-data-quality",
        message=f"Training blocked for {context['ds']}: "
                f"Quality={quality_result}, Drift={drift_results}"
    )
    send_pagerduty_alert(
        severity="warning",
        summary=f"ML training quality gate failed for {context['ds']}"
    )
    raise Exception("Training blocked by quality gate")


with DAG(
    dag_id="ml_training_pipeline_with_quality_gates",
    default_args=default_args,
    schedule_interval="@daily",
    start_date=days_ago(1),
    catchup=False,
    tags=["ml", "training", "quality"],
) as dag:
    
    ingest = PythonOperator(
        task_id="ingest_raw_data",
        python_callable=run_ingestion,
    )
    
    quality_gate = BranchPythonOperator(
        task_id="quality_gate_check",
        python_callable=run_quality_gate,
    )
    
    feature_eng = PythonOperator(
        task_id="proceed_to_feature_engineering",
        python_callable=run_feature_engineering,
    )
    
    drift_check = BranchPythonOperator(
        task_id="drift_detection",
        python_callable=run_drift_detection,
    )
    
    training = PythonOperator(
        task_id="proceed_to_training",
        python_callable=run_training,
    )
    
    block_alert = PythonOperator(
        task_id="block_training_and_alert",
        python_callable=alert_and_block,
        trigger_rule="none_failed_min_one_success",
    )
    
    # DAG structure
    ingest >> quality_gate
    quality_gate >> [feature_eng, block_alert]
    feature_eng >> drift_check
    drift_check >> [training, block_alert]
```

### Training/Serving Skew Detector

```python
"""
serving_skew_detector.py
Compares feature values between batch training and real-time serving
to detect training/serving skew.
"""
import numpy as np
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


@dataclass
class SkewResult:
    feature: str
    training_mean: float
    serving_mean: float
    absolute_diff: float
    relative_diff: float
    skew_detected: bool
    sample_size_training: int
    sample_size_serving: int


class TrainingServingSkewDetector:
    """
    Detects discrepancies between feature values used in batch training
    vs those computed in real-time serving.
    
    Common causes of skew:
    - Different computation logic (Spark vs Redis/Python)
    - Different data freshness (batch=T-1, serving=realtime)
    - Missing values handled differently
    - Timezone inconsistencies
    """
    
    RELATIVE_THRESHOLD = 0.05  # 5% relative difference
    ABSOLUTE_THRESHOLD = 0.5   # absolute difference
    
    def __init__(self, feature_store_client, serving_log_client):
        self.feature_store = feature_store_client
        self.serving_logs = serving_log_client
    
    def compare_features(
        self,
        entity_ids: List[str],
        features: List[str],
        training_date: str,
    ) -> List[SkewResult]:
        """
        For a sample of entities, compare training-time feature values
        with serving-time feature values.
        """
        results = []
        
        for feature in features:
            # Get batch-computed values from feature store
            training_values = self.feature_store.get_historical_features(
                entity_ids=entity_ids,
                feature_name=feature,
                timestamp=training_date,
            )
            
            # Get serving-time computed values from prediction logs
            serving_values = self.serving_logs.get_feature_values(
                entity_ids=entity_ids,
                feature_name=feature,
                date_range=(training_date, training_date),
            )
            
            # Match on entity_id and compare
            matched_training = []
            matched_serving = []
            
            for eid in entity_ids:
                t_val = training_values.get(eid)
                s_val = serving_values.get(eid)
                if t_val is not None and s_val is not None:
                    matched_training.append(t_val)
                    matched_serving.append(s_val)
            
            if not matched_training:
                logger.warning(f"No matched values for feature '{feature}'")
                continue
            
            t_mean = np.mean(matched_training)
            s_mean = np.mean(matched_serving)
            abs_diff = abs(t_mean - s_mean)
            rel_diff = abs_diff / (abs(t_mean) + 1e-8)
            
            skew_detected = (
                rel_diff > self.RELATIVE_THRESHOLD or
                abs_diff > self.ABSOLUTE_THRESHOLD
            )
            
            results.append(SkewResult(
                feature=feature,
                training_mean=t_mean,
                serving_mean=s_mean,
                absolute_diff=abs_diff,
                relative_diff=rel_diff,
                skew_detected=skew_detected,
                sample_size_training=len(matched_training),
                sample_size_serving=len(matched_serving),
            ))
            
            if skew_detected:
                logger.error(
                    f"Training/serving skew in '{feature}': "
                    f"training_mean={t_mean:.4f}, serving_mean={s_mean:.4f}, "
                    f"relative_diff={rel_diff:.4f}"
                )
        
        return results
```

---

## Alert Patterns

### Prometheus Alert Rules

```yaml
# ml_training_data_alerts.yml
groups:
  - name: ml_training_data_quality
    rules:
      # Dataset size anomaly
      - alert: TrainingDatasetSizeAnomaly
        expr: |
          abs(ml_training_dataset_row_count - ml_training_dataset_row_count_expected)
          / ml_training_dataset_row_count_expected > 0.2
        for: 5m
        labels:
          severity: warning
          team: ml-platform
        annotations:
          summary: "Training dataset size deviates >20% from expected"
          description: |
            Dataset: {{ $labels.dataset }}
            Actual rows: {{ $value }}
            Expected: {{ $labels.expected_rows }}
          runbook_url: "https://wiki.internal/runbooks/ml-data-size-anomaly"

      # Feature drift
      - alert: FeatureDistributionDrift
        expr: ml_feature_psi_score > 0.2
        for: 0m
        labels:
          severity: critical
          team: ml-platform
        annotations:
          summary: "Critical feature drift detected (PSI > 0.2)"
          description: |
            Feature: {{ $labels.feature_name }}
            PSI Score: {{ $value }}
            Action: Training will be automatically blocked

      # Label distribution shift
      - alert: LabelDistributionShift
        expr: |
          abs(ml_positive_class_rate - ml_positive_class_rate_baseline)
          / ml_positive_class_rate_baseline > 0.3
        for: 0m
        labels:
          severity: warning
          team: ml-platform
        annotations:
          summary: "Label distribution shifted >30% from baseline"

      # Pipeline completion time
      - alert: TrainingPipelineSlowdown
        expr: |
          ml_training_pipeline_duration_seconds
          > ml_training_pipeline_duration_p95_seconds * 1.5
        for: 10m
        labels:
          severity: warning
          team: ml-platform
        annotations:
          summary: "Training pipeline taking 50% longer than P95"

      # High null rate
      - alert: FeatureHighNullRate
        expr: ml_feature_null_rate > 0.01
        for: 0m
        labels:
          severity: warning
          team: ml-platform
        annotations:
          summary: "Feature {{ $labels.feature }} has >1% null rate"

      # Training/serving skew
      - alert: TrainingServingSkew
        expr: ml_serving_skew_relative_diff > 0.05
        for: 5m
        labels:
          severity: critical
          team: ml-platform
        annotations:
          summary: "Training/serving skew detected in {{ $labels.feature }}"
```

---

## Technologies

| Category | Tool | Purpose |
|----------|------|---------|
| Data Validation | Great Expectations | Schema, stats, custom expectations |
| Drift Detection | Evidently AI | Automated drift reports and monitoring |
| Experiment Tracking | MLflow | Metrics, params, artifacts per run |
| Pipeline Orchestration | Airflow / Kubeflow | DAG execution with quality gates |
| Dataset Versioning | DVC | Git-like versioning for large datasets |
| Feature Store | Feast | Consistent features across train/serve |
| Experiment Tracking | Weights & Biases | Visualization, comparison, collaboration |
| Compute | Spark | Distributed data processing |
| Transformation | dbt | SQL-based transformation with tests |

---

## Runbook: Data Quality Gate Failure

### Symptoms
- Airflow DAG `ml_training_pipeline_with_quality_gates` shows `block_training_and_alert` task executed
- Slack alert in `#ml-data-quality`
- No new model registered in MLflow for today

### Diagnosis Steps

```
Step 1: Identify which gate failed
─────────────────────────────────
  → Check Airflow task logs for quality_gate_check
  → Look for specific failed expectations in Great Expectations report
  → URL: https://ge-reports.internal/training_quality/latest

Step 2: Classify the failure
────────────────────────────
  A) Schema failure → upstream source changed schema
  B) Stats failure → distribution shift in source data
  C) Null spike → upstream ETL bug or source outage
  D) Drift failure → genuine concept drift vs data bug

Step 3: For Schema failures
───────────────────────────
  → Check upstream team's changelog for schema modifications
  → If intentional: update expectation suite + retrigger
  → If unintentional: escalate to source team

Step 4: For Drift failures
──────────────────────────
  → Compare current vs baseline distributions visually
  → Check if drift is in ALL features (suggests source issue)
     or specific features (suggests genuine drift)
  → If source issue: fix source, backfill, retrigger
  → If genuine drift: update baseline, document decision,
     consider retraining strategy change

Step 5: Recovery
────────────────
  → Fix root cause
  → Re-run ingestion if needed: 
    `airflow dags trigger ml_training_pipeline_with_quality_gates --conf '{"rerun": true}'`
  → Verify quality gate passes
  → Confirm model training completes successfully
  → Check model metrics against previous version

Step 6: Post-incident
─────────────────────
  → Update quality thresholds if too sensitive/lenient
  → Add new expectations for the failure mode
  → Document in incident log
```

### Escalation Path

| Time Since Failure | Action |
|-------------------|--------|
| 0-30 min | On-call ML engineer investigates |
| 30 min - 2 hr | Escalate to data platform team if source issue |
| 2-4 hr | Notify ML model owners of delayed training |
| 4+ hr | Executive notification if revenue-impacting model |

---

## Key Metrics Dashboard

```
┌─────────────────────────────────────────────────────────────────┐
│            ML TRAINING DATA QUALITY DASHBOARD                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Quality Gate Pass Rate (7d)     Dataset Size Trend              │
│  ┌──────────────────────┐       ┌──────────────────────┐       │
│  │ ████████████░░ 85%   │       │      ___/\___        │       │
│  │ Today: PASSED ✓      │       │  ___/        \__     │       │
│  └──────────────────────┘       │ /               \    │       │
│                                  └──────────────────────┘       │
│  Max PSI Score (today)           Null Rate Trend                 │
│  ┌──────────────────────┐       ┌──────────────────────┐       │
│  │ feature_3: 0.08      │       │ ─────────── 0.2%     │       │
│  │ feature_1: 0.05      │       │             stable   │       │
│  │ [ALL BELOW 0.1] ✓    │       └──────────────────────┘       │
│  └──────────────────────┘                                       │
│                                                                  │
│  Training/Serving Skew           Label Distribution              │
│  ┌──────────────────────┐       ┌──────────────────────┐       │
│  │ Max relative diff:   │       │ Positive rate: 1.2%  │       │
│  │ 0.02 (healthy)       │       │ Baseline:      1.1%  │       │
│  └──────────────────────┘       │ [WITHIN BOUNDS] ✓    │       │
│                                  └──────────────────────┘       │
└─────────────────────────────────────────────────────────────────┘
```
