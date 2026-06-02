# ML Testing: Complete Strategy with Runnable Pytest Code

## 1. Why ML Testing is Different

| Traditional Software | ML Systems |
|---------------------|------------|
| Deterministic output | Probabilistic output |
| Test exact values | Test properties/distributions |
| Bug = wrong logic | Bug = bad data, drift, bias |
| Deploy once, done | Models degrade over time |

**What to test in ML:**
- **Data quality** — schema, ranges, freshness, balance
- **Feature engineering** — determinism, shapes, no leakage
- **Model quality** — accuracy, fairness, latency, robustness
- **Infrastructure** — serving, versioning, rollback
- **Production** — drift, staleness, prediction distribution

---

## 2. Test Pyramid for ML

```
            /\           E2E Tests (full pipeline, slow, few)
           /  \
          /----\         Model Quality Tests (accuracy, fairness, latency)
         /------\
        /--------\       Feature Tests (deterministic, no nulls, shapes)
       /----------\
      /------------\     Data Quality Tests (schema, ranges, freshness)
     /--------------\
    /________________\   Unit Tests (utility functions, transformations)
```

**Run frequency:**
- Unit + Data: every commit
- Feature + Model Quality: every PR
- E2E + Drift: nightly / pre-deploy

---

## 3. Project Structure

```
ml-project/
├── data/
│   └── train.csv
├── models/
│   ├── production_model.joblib
│   └── preprocessing_pipeline.joblib
├── src/
│   ├── features.py
│   ├── train.py
│   └── serve.py
├── tests/
│   ├── conftest.py
│   ├── test_data_quality.py
│   ├── test_features.py
│   ├── test_model_quality.py
│   ├── test_integration.py
│   └── test_drift.py
├── pytest.ini
└── requirements-test.txt
```

---

## 4. pytest.ini

```ini
[pytest]
testpaths = tests
markers =
    slow: marks tests as slow (deselect with '-m "not slow"')
    gpu: requires GPU
    data: data quality tests
    model: model quality tests
    integration: integration tests
    drift: drift detection tests
addopts = -v --tb=short
filterwarnings =
    ignore::DeprecationWarning
```

---

## 5. conftest.py — Shared Fixtures

```python
# tests/conftest.py
import pytest
import pandas as pd
import numpy as np
import joblib
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent


@pytest.fixture(scope="session")
def model():
    """Load the production model once for all tests."""
    model_path = PROJECT_ROOT / "models" / "production_model.joblib"
    return joblib.load(model_path)


@pytest.fixture(scope="session")
def pipeline():
    """Load preprocessing pipeline once for all tests."""
    pipe_path = PROJECT_ROOT / "models" / "preprocessing_pipeline.joblib"
    return joblib.load(pipe_path)


@pytest.fixture(scope="session")
def raw_data():
    """Load training data once for all tests."""
    return pd.read_csv(PROJECT_ROOT / "data" / "train.csv")


@pytest.fixture
def sample_data():
    """Small representative sample for fast tests."""
    np.random.seed(42)
    n = 100
    return pd.DataFrame({
        "id": range(n),
        "age": np.random.randint(18, 80, n),
        "income": np.random.lognormal(10, 1, n),
        "price": np.random.uniform(10, 1000, n),
        "category": np.random.choice(["A", "B", "C", "D"], n),
        "timestamp": pd.date_range("2024-01-01", periods=n, freq="h"),
        "target": np.random.choice([0, 1], n, p=[0.7, 0.3]),
    })


@pytest.fixture
def sample_features():
    """Pre-processed feature matrix for model tests."""
    np.random.seed(42)
    return np.random.randn(50, 10)


@pytest.fixture
def sample_input():
    """Single input for latency tests."""
    return np.random.randn(1, 10)


@pytest.fixture
def test_client():
    """Flask/FastAPI test client."""
    from src.serve import create_app
    app = create_app(testing=True)
    with app.test_client() as client:
        yield client
```

---

## 6. Data Quality Tests

```python
# tests/test_data_quality.py
import pytest
import pandas as pd
import numpy as np


@pytest.mark.data
class TestDataSchema:
    """Verify data conforms to expected schema."""

    def test_required_columns_exist(self, raw_data):
        required = ["id", "age", "income", "price", "category", "target"]
        missing = set(required) - set(raw_data.columns)
        assert not missing, f"Missing columns: {missing}"

    def test_column_types(self, raw_data):
        assert pd.api.types.is_numeric_dtype(raw_data["age"])
        assert pd.api.types.is_numeric_dtype(raw_data["income"])
        assert pd.api.types.is_numeric_dtype(raw_data["price"])
        assert pd.api.types.is_object_dtype(raw_data["category"])

    def test_no_duplicate_ids(self, raw_data):
        assert raw_data["id"].nunique() == len(raw_data), "Duplicate IDs found"

    def test_row_count_reasonable(self, raw_data):
        assert len(raw_data) >= 1000, "Too few rows — possible data loss"
        assert len(raw_data) <= 10_000_000, "Unexpectedly large dataset"


@pytest.mark.data
class TestDataValues:
    """Verify values are within expected ranges."""

    def test_target_not_null(self, raw_data):
        null_count = raw_data["target"].isnull().sum()
        assert null_count == 0, f"{null_count} null targets"

    def test_age_in_range(self, raw_data):
        assert raw_data["age"].between(0, 150).all(), (
            f"Ages out of range: {raw_data['age'].describe()}"
        )

    def test_price_non_negative(self, raw_data):
        assert raw_data["price"].ge(0).all(), "Negative prices found"

    def test_income_positive(self, raw_data):
        assert raw_data["income"].gt(0).all(), "Non-positive incomes"

    def test_categorical_values_valid(self, raw_data):
        valid_categories = {"A", "B", "C", "D"}
        actual = set(raw_data["category"].unique())
        invalid = actual - valid_categories
        assert not invalid, f"Invalid categories: {invalid}"

    def test_no_future_timestamps(self, raw_data):
        timestamps = pd.to_datetime(raw_data["timestamp"])
        assert (timestamps <= pd.Timestamp.now()).all()


@pytest.mark.data
class TestDataDistribution:
    """Verify data distributions are healthy."""

    def test_class_balance(self, raw_data):
        ratios = raw_data["target"].value_counts(normalize=True)
        assert ratios.min() >= 0.05, (
            f"Severe class imbalance: {ratios.to_dict()}"
        )

    def test_no_single_value_columns(self, raw_data):
        for col in raw_data.select_dtypes(include=[np.number]).columns:
            nunique = raw_data[col].nunique()
            assert nunique > 1, f"Column {col} has only one value"

    def test_null_rate_below_threshold(self, raw_data):
        null_rates = raw_data.isnull().mean()
        high_null = null_rates[null_rates > 0.5]
        assert high_null.empty, f"High null columns: {high_null.to_dict()}"

    def test_data_freshness(self, raw_data):
        latest = pd.to_datetime(raw_data["timestamp"]).max()
        staleness_days = (pd.Timestamp.now() - latest).days
        assert staleness_days <= 30, f"Data is {staleness_days} days old"
```

---

## 7. Feature Engineering Tests

```python
# tests/test_features.py
import pytest
import pandas as pd
import numpy as np


@pytest.mark.parametrize("seed", [42, 123, 456])
def test_pipeline_deterministic(sample_data, pipeline, seed):
    """Same input always produces same output."""
    r1 = pipeline.transform(sample_data.copy())
    r2 = pipeline.transform(sample_data.copy())
    pd.testing.assert_frame_equal(r1, r2)


def test_pipeline_preserves_row_count(sample_data, pipeline):
    """Transformation should not add or drop rows."""
    result = pipeline.transform(sample_data)
    assert len(result) == len(sample_data)


def test_pipeline_no_nulls_in_output(sample_data, pipeline):
    """All nulls should be handled by the pipeline."""
    result = pipeline.transform(sample_data)
    null_count = result.isnull().sum().sum()
    assert null_count == 0, f"Pipeline output has {null_count} nulls"


def test_pipeline_no_infinities(sample_data, pipeline):
    """No infinite values in output."""
    result = pipeline.transform(sample_data)
    numeric = result.select_dtypes(include=[np.number])
    inf_count = np.isinf(numeric.values).sum()
    assert inf_count == 0, f"Pipeline output has {inf_count} infinities"


def test_scaled_features_bounded(sample_data, pipeline):
    """Scaled features should be within reasonable range."""
    result = pipeline.transform(sample_data)
    numeric = result.select_dtypes(include=[np.number])
    assert (numeric.abs() < 100).all().all(), "Features exceed expected range"


def test_one_hot_encoding_complete(sample_data, pipeline):
    """All expected encoded columns exist."""
    result = pipeline.transform(sample_data)
    expected_cols = ["category_A", "category_B", "category_C", "category_D"]
    for col in expected_cols:
        assert col in result.columns, f"Missing encoded column: {col}"


def test_one_hot_mutually_exclusive(sample_data, pipeline):
    """Each row should have exactly one hot-encoded category active."""
    result = pipeline.transform(sample_data)
    cat_cols = [c for c in result.columns if c.startswith("category_")]
    row_sums = result[cat_cols].sum(axis=1)
    assert (row_sums == 1).all(), "One-hot encoding is not mutually exclusive"


def test_no_target_leakage(sample_data, pipeline):
    """Target column should never appear in features."""
    result = pipeline.transform(sample_data)
    assert "target" not in result.columns, "Target leakage detected!"


def test_feature_names_stable(sample_data, pipeline):
    """Feature names should not change between runs."""
    r1 = pipeline.transform(sample_data)
    r2 = pipeline.transform(sample_data)
    assert list(r1.columns) == list(r2.columns)


def test_handles_unseen_categories(pipeline):
    """Pipeline should handle categories not seen in training."""
    unseen = pd.DataFrame({
        "age": [25], "income": [50000], "price": [100],
        "category": ["Z"],  # unseen!
        "timestamp": [pd.Timestamp.now()],
    })
    result = pipeline.transform(unseen)
    assert not result.isnull().any().any()
```

---

## 8. Model Quality Tests

```python
# tests/test_model_quality.py
import pytest
import numpy as np
import time
from sklearn.metrics import accuracy_score, f1_score, roc_auc_score


@pytest.mark.model
class TestModelAccuracy:
    """Verify model meets minimum quality bars."""

    def test_beats_majority_baseline(self, model, sample_features, sample_data):
        test_y = sample_data["target"].values[:len(sample_features)]
        preds = model.predict(sample_features)
        model_acc = accuracy_score(test_y, preds)
        baseline_acc = np.bincount(test_y).max() / len(test_y)
        assert model_acc > baseline_acc + 0.05, (
            f"Model ({model_acc:.3f}) barely beats baseline ({baseline_acc:.3f})"
        )

    def test_f1_above_threshold(self, model, sample_features, sample_data):
        test_y = sample_data["target"].values[:len(sample_features)]
        preds = model.predict(sample_features)
        f1 = f1_score(test_y, preds, average="weighted")
        assert f1 >= 0.70, f"F1 too low: {f1:.3f}"

    def test_not_overfitting(self, model, sample_features, sample_data):
        """Train-test gap should be small."""
        test_y = sample_data["target"].values[:len(sample_features)]
        # Simulate: in practice, compare train vs test scores
        test_score = model.score(sample_features, test_y)
        # If model has train_score_ attribute (some sklearn models)
        train_score = getattr(model, "train_score_", test_score + 0.05)
        if isinstance(train_score, np.ndarray):
            train_score = train_score[-1]
        gap = train_score - test_score
        assert gap < 0.15, f"Overfitting detected: gap={gap:.3f}"


@pytest.mark.model
class TestModelFairness:
    """Verify model performs equitably across groups."""

    def test_performance_across_age_groups(self, model, sample_data):
        features = sample_data[["age", "income", "price"]].values
        # Pad to match model input if needed
        features = np.pad(features, ((0, 0), (0, 7)), constant_values=0)
        targets = sample_data["target"].values

        young = sample_data["age"] < 30
        old = sample_data["age"] >= 50

        if young.sum() > 0 and old.sum() > 0:
            score_young = accuracy_score(targets[young], model.predict(features[young]))
            score_old = accuracy_score(targets[old], model.predict(features[old]))
            gap = abs(score_young - score_old)
            assert gap < 0.15, (
                f"Age bias: young={score_young:.3f}, old={score_old:.3f}"
            )

    def test_equal_false_positive_rates(self, model, sample_features, sample_data):
        """FPR should not vary wildly across groups."""
        test_y = sample_data["target"].values[:len(sample_features)]
        preds = model.predict(sample_features)
        # Group by median split of first feature as proxy
        median = np.median(sample_features[:, 0])
        group_a = sample_features[:, 0] < median
        group_b = ~group_a

        def fpr(mask):
            negatives = test_y[mask] == 0
            if negatives.sum() == 0:
                return 0
            return (preds[mask][negatives] == 1).mean()

        fpr_a, fpr_b = fpr(group_a), fpr(group_b)
        assert abs(fpr_a - fpr_b) < 0.10, (
            f"FPR disparity: {fpr_a:.3f} vs {fpr_b:.3f}"
        )


@pytest.mark.model
class TestModelRobustness:
    """Verify model handles edge cases gracefully."""

    def test_handles_zeros(self, model):
        zeros = np.zeros((1, 10))
        result = model.predict(zeros)
        assert result is not None
        assert not np.isnan(result[0])

    def test_handles_large_values(self, model):
        large = np.ones((1, 10)) * 1e6
        result = model.predict(large)
        assert result is not None
        assert not np.isnan(result[0])

    def test_handles_negative_values(self, model):
        negative = -np.ones((1, 10)) * 100
        result = model.predict(negative)
        assert result is not None

    def test_prediction_range_valid(self, model, sample_features):
        """Predictions should be within expected range."""
        preds = model.predict(sample_features)
        # For classification: labels should be valid
        valid_labels = {0, 1}
        assert set(preds).issubset(valid_labels), (
            f"Invalid predictions: {set(preds) - valid_labels}"
        )

    def test_predict_proba_sums_to_one(self, model, sample_features):
        """Probabilities should sum to 1."""
        if hasattr(model, "predict_proba"):
            probas = model.predict_proba(sample_features)
            sums = probas.sum(axis=1)
            np.testing.assert_allclose(sums, 1.0, atol=1e-5)


@pytest.mark.model
class TestModelLatency:
    """Verify model meets performance SLAs."""

    def test_single_prediction_latency(self, model, sample_input):
        """Single prediction should be fast."""
        times = []
        for _ in range(100):
            start = time.perf_counter()
            model.predict(sample_input)
            times.append(time.perf_counter() - start)
        p99 = sorted(times)[98]
        assert p99 < 0.100, f"p99 latency {p99*1000:.1f}ms exceeds 100ms SLA"

    def test_batch_prediction_latency(self, model, sample_features):
        """Batch prediction should scale reasonably."""
        start = time.perf_counter()
        model.predict(sample_features)
        elapsed = time.perf_counter() - start
        per_sample = elapsed / len(sample_features)
        assert per_sample < 0.010, f"Per-sample latency: {per_sample*1000:.1f}ms"

    def test_model_memory_footprint(self, model):
        """Model should not be unreasonably large."""
        import sys
        size_mb = sys.getsizeof(model) / 1e6
        # Note: this is approximate; use joblib file size for accuracy
        assert size_mb < 500, f"Model size {size_mb:.0f}MB exceeds limit"
```

---

## 9. Integration Tests

```python
# tests/test_integration.py
import pytest
import numpy as np
import json


@pytest.mark.integration
class TestEndToEnd:
    """Full pipeline integration tests."""

    def test_raw_to_prediction(self, sample_data, pipeline, model):
        """Complete flow: raw data → features → predictions."""
        features = pipeline.transform(sample_data)
        feature_matrix = features.select_dtypes(include=[np.number]).values
        # Ensure correct shape for model
        if feature_matrix.shape[1] != 10:
            feature_matrix = np.pad(
                feature_matrix,
                ((0, 0), (0, max(0, 10 - feature_matrix.shape[1]))),
            )[:, :10]
        predictions = model.predict(feature_matrix)
        assert len(predictions) == len(sample_data)
        assert all(isinstance(p, (int, float, np.integer, np.floating)) for p in predictions)

    def test_pipeline_model_shape_compatibility(self, sample_data, pipeline, model):
        """Pipeline output shape must match model input shape."""
        features = pipeline.transform(sample_data)
        numeric = features.select_dtypes(include=[np.number])
        # This should not raise
        try:
            model.predict(numeric.values[:1])
        except ValueError as e:
            pytest.fail(f"Shape mismatch: {e}")


@pytest.mark.integration
class TestAPIEndpoint:
    """Test the serving API."""

    def test_predict_endpoint_success(self, test_client):
        payload = {"features": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]}
        response = test_client.post(
            "/predict",
            data=json.dumps(payload),
            content_type="application/json",
        )
        assert response.status_code == 200
        body = response.get_json()
        assert "prediction" in body
        assert "confidence" in body
        assert 0 <= body["confidence"] <= 1

    def test_predict_endpoint_bad_input(self, test_client):
        response = test_client.post(
            "/predict",
            data=json.dumps({"features": "not_a_list"}),
            content_type="application/json",
        )
        assert response.status_code == 400

    def test_predict_endpoint_missing_fields(self, test_client):
        response = test_client.post(
            "/predict",
            data=json.dumps({}),
            content_type="application/json",
        )
        assert response.status_code == 400

    def test_health_endpoint(self, test_client):
        response = test_client.get("/health")
        assert response.status_code == 200
        assert response.get_json()["status"] == "healthy"


@pytest.mark.integration
class TestModelVersioning:
    """Verify model versioning works correctly."""

    def test_model_has_metadata(self, model):
        """Model should carry version metadata."""
        assert hasattr(model, "metadata_") or hasattr(model, "version_")

    def test_can_load_previous_version(self):
        """Previous model version should still be loadable."""
        import joblib
        from pathlib import Path
        models_dir = Path("models")
        versions = sorted(models_dir.glob("model_v*.joblib"))
        if len(versions) >= 2:
            old = joblib.load(versions[-2])
            assert old is not None
```

---

## 10. Drift Detection Tests

```python
# tests/test_drift.py
import pytest
import numpy as np
from scipy.stats import ks_2samp, chi2_contingency


@pytest.mark.drift
class TestFeatureDrift:
    """Detect distribution shifts between training and serving data."""

    @pytest.fixture
    def training_distribution(self):
        """Saved statistics from training data."""
        np.random.seed(42)
        return {
            "age": np.random.normal(40, 15, 10000),
            "income": np.random.lognormal(10, 1, 10000),
            "price": np.random.uniform(10, 1000, 10000),
        }

    @pytest.fixture
    def serving_data(self):
        """Recent serving/production data."""
        np.random.seed(99)
        return {
            "age": np.random.normal(42, 15, 500),  # slight shift
            "income": np.random.lognormal(10, 1, 500),
            "price": np.random.uniform(10, 1000, 500),
        }

    def test_no_numerical_drift(self, training_distribution, serving_data):
        """KS test for numerical feature drift."""
        for feature in ["age", "income", "price"]:
            stat, p_value = ks_2samp(
                training_distribution[feature],
                serving_data[feature],
            )
            assert p_value > 0.01, (
                f"Drift detected in '{feature}': KS={stat:.4f}, p={p_value:.4f}"
            )

    def test_no_categorical_drift(self):
        """Chi-squared test for categorical drift."""
        # Training distribution
        train_counts = np.array([400, 300, 200, 100])
        # Serving distribution
        serve_counts = np.array([38, 32, 18, 12])
        # Normalize to same total
        expected = train_counts / train_counts.sum() * serve_counts.sum()
        from scipy.stats import chisquare
        stat, p_value = chisquare(serve_counts, expected)
        assert p_value > 0.05, f"Categorical drift: chi2={stat:.2f}, p={p_value:.4f}"


@pytest.mark.drift
class TestPredictionDrift:
    """Monitor prediction distribution stability."""

    def test_prediction_distribution_stable(self):
        """Prediction scores should not shift dramatically."""
        np.random.seed(42)
        historical = np.random.beta(2, 5, 1000)  # historical predictions
        current = np.random.beta(2, 5, 200)       # current predictions
        stat, p_value = ks_2samp(historical, current)
        assert p_value > 0.05, (
            f"Prediction distribution shifted: KS={stat:.4f}, p={p_value:.4f}"
        )

    def test_positive_rate_stable(self):
        """Rate of positive predictions should be stable."""
        historical_rate = 0.30
        current_preds = np.random.choice([0, 1], 200, p=[0.68, 0.32])
        current_rate = current_preds.mean()
        assert abs(current_rate - historical_rate) < 0.10, (
            f"Positive rate shifted: {historical_rate:.2f} → {current_rate:.2f}"
        )

    def test_null_prediction_rate(self):
        """Should not produce null/error predictions."""
        predictions = np.random.choice([0, 1, None], 1000, p=[0.49, 0.50, 0.01])
        null_rate = sum(1 for p in predictions if p is None) / len(predictions)
        assert null_rate < 0.05, f"Null prediction rate: {null_rate:.2%}"
```

---

## 11. CI/CD Integration

```yaml
# .github/workflows/ml-tests.yml
name: ML Tests

on:
  pull_request:
    paths: ["src/**", "tests/**", "data/**"]
  push:
    branches: [main]
  schedule:
    - cron: "0 6 * * *"  # nightly drift checks

jobs:
  fast-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install -r requirements-test.txt
      - run: pytest -m "data or not (model or integration or drift or slow)" --timeout=60

  model-quality:
    runs-on: ubuntu-latest
    if: github.event_name == 'push' || github.event.pull_request.merged
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install -r requirements-test.txt
      - run: pytest -m "model" --timeout=300

  drift-detection:
    runs-on: ubuntu-latest
    if: github.event_name == 'schedule'
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install -r requirements-test.txt
      - run: pytest -m "drift" --timeout=120
```

---

## 12. What NOT to Test

| Don't Test | Why | Test Instead |
|-----------|-----|--------------|
| Exact model outputs | Change with retraining | Properties, bounds, relative ordering |
| Specific weight values | Implementation detail | Model behavior |
| Training convergence time | Hardware-dependent | Final metric thresholds |
| Exact loss values | Stochastic | Loss is decreasing, below threshold |
| Random seed reproducibility across machines | Platform-dependent | Statistical properties hold |

---

## 13. Handling Flaky ML Tests

```python
# Use tolerances for statistical tests
def test_accuracy_with_tolerance(model, test_X, test_y):
    """Run multiple times, pass if majority succeed."""
    scores = []
    for seed in range(5):
        np.random.seed(seed)
        idx = np.random.choice(len(test_X), size=len(test_X), replace=True)
        score = model.score(test_X[idx], test_y[idx])
        scores.append(score)
    median_score = np.median(scores)
    assert median_score >= 0.75, f"Median accuracy: {median_score:.3f}"


# Use pytest-rerunfailures for inherently stochastic tests
# pytest.ini: addopts = --reruns 3 --reruns-delay 1
```

---

## 14. requirements-test.txt

```
pytest>=7.4
pytest-timeout>=2.2
pytest-rerunfailures>=12.0
pandas>=2.0
numpy>=1.24
scikit-learn>=1.3
scipy>=1.11
joblib>=1.3
```

---

## Key Takeaways

1. **Test properties, not values** — ML outputs change; behaviors shouldn't
2. **Layer your tests** — fast data tests catch 80% of issues cheaply
3. **Automate drift detection** — models rot silently in production
4. **Set clear SLAs** — latency, accuracy, fairness thresholds in code
5. **Test the pipeline, not just the model** — most bugs are in data/features
