"""
LLMOps: Dataset Versioning System
===================================
Production-grade dataset versioning with schema management, quality gates,
lineage tracking, production feedback pipelines, and automated refresh.
"""

import hashlib
import json
import uuid
import statistics
from datetime import datetime, timezone
from typing import Any, Optional, Generator
from dataclasses import dataclass, field, asdict
from enum import Enum
from abc import ABC, abstractmethod
from collections import Counter, defaultdict
import copy


# =============================================================================
# Core Data Models
# =============================================================================

class FieldType(str, Enum):
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    LIST = "list"
    OBJECT = "object"
    TEXT = "text"  # Long text (prompts, responses)
    LABEL = "label"  # Categorical label
    SCORE = "score"  # Numeric score (e.g., 0-5)


class SplitType(str, Enum):
    TRAIN = "train"
    VALIDATION = "validation"
    TEST = "test"
    GOLDEN = "golden"  # Curated high-quality examples
    ADVERSARIAL = "adversarial"
    PRODUCTION = "production"  # Mined from production


class DatasetStatus(str, Enum):
    DRAFT = "draft"
    VALIDATING = "validating"
    VALID = "valid"
    INVALID = "invalid"
    ACTIVE = "active"
    DEPRECATED = "deprecated"


@dataclass
class FieldSchema:
    """Schema definition for a single field."""
    name: str
    field_type: FieldType
    description: str
    required: bool = True
    nullable: bool = False
    enum_values: list[str] = field(default_factory=list)
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    pattern: Optional[str] = None  # Regex pattern for validation


@dataclass
class DatasetSchema:
    """Schema for a dataset, defining expected fields and their types."""
    id: str
    name: str
    version: int
    fields: list[FieldSchema]
    description: str
    metadata_fields: list[FieldSchema] = field(default_factory=list)
    created_at: str = ""
    created_by: str = ""

    def validate_example(self, example: dict) -> list[str]:
        """Validate an example against this schema. Returns list of errors."""
        errors = []
        for field_def in self.fields:
            if field_def.name not in example:
                if field_def.required:
                    errors.append(f"Missing required field: {field_def.name}")
                continue

            value = example[field_def.name]
            if value is None:
                if not field_def.nullable:
                    errors.append(f"Field '{field_def.name}' cannot be null")
                continue

            # Type validation
            type_valid = self._validate_type(value, field_def)
            if not type_valid:
                errors.append(f"Field '{field_def.name}': expected {field_def.field_type.value}, got {type(value).__name__}")
                continue

            # Range validation
            if field_def.min_value is not None and isinstance(value, (int, float)):
                if value < field_def.min_value:
                    errors.append(f"Field '{field_def.name}': value {value} below minimum {field_def.min_value}")
            if field_def.max_value is not None and isinstance(value, (int, float)):
                if value > field_def.max_value:
                    errors.append(f"Field '{field_def.name}': value {value} above maximum {field_def.max_value}")

            # Length validation for strings
            if isinstance(value, str):
                if field_def.min_length and len(value) < field_def.min_length:
                    errors.append(f"Field '{field_def.name}': length {len(value)} below minimum {field_def.min_length}")
                if field_def.max_length and len(value) > field_def.max_length:
                    errors.append(f"Field '{field_def.name}': length {len(value)} above maximum {field_def.max_length}")

            # Enum validation
            if field_def.enum_values and value not in field_def.enum_values:
                errors.append(f"Field '{field_def.name}': value '{value}' not in allowed values {field_def.enum_values}")

        return errors

    def _validate_type(self, value: Any, field_def: FieldSchema) -> bool:
        type_map = {
            FieldType.STRING: str, FieldType.TEXT: str, FieldType.LABEL: str,
            FieldType.INTEGER: int, FieldType.FLOAT: (int, float),
            FieldType.BOOLEAN: bool, FieldType.LIST: list, FieldType.OBJECT: dict,
            FieldType.SCORE: (int, float),
        }
        expected = type_map.get(field_def.field_type)
        return isinstance(value, expected) if expected else True


@dataclass
class DatasetExample:
    """A single example in a dataset."""
    id: str
    data: dict[str, Any]
    metadata: dict[str, Any] = field(default_factory=dict)
    split: SplitType = SplitType.TEST
    source: str = "manual"  # manual, production, synthetic, augmented
    created_at: str = ""
    lineage: dict[str, Any] = field(default_factory=dict)  # Where this example came from


@dataclass
class DatasetVersion:
    """An immutable version of a dataset."""
    id: str
    dataset_id: str
    version: int
    schema_version: int
    examples: list[DatasetExample]
    metadata: dict[str, Any]
    content_hash: str
    created_at: str
    created_by: str
    message: str
    parent_version: Optional[int] = None
    status: DatasetStatus = DatasetStatus.DRAFT
    quality_metrics: dict[str, Any] = field(default_factory=dict)
    split_counts: dict[str, int] = field(default_factory=dict)

    @staticmethod
    def compute_hash(examples: list[DatasetExample]) -> str:
        data = json.dumps([e.data for e in examples], sort_keys=True)
        return hashlib.sha256(data.encode()).hexdigest()[:16]


@dataclass
class QualityGateResult:
    """Result of running quality gates on a dataset version."""
    passed: bool
    checks: list[dict[str, Any]]
    overall_score: float
    blocking_failures: list[str]
    warnings: list[str]
    timestamp: str


@dataclass
class LineageRecord:
    """Tracks the origin and transformations of data."""
    example_id: str
    source_type: str  # production_trace, human_annotation, synthetic, augmentation
    source_id: Optional[str] = None  # trace_id, annotation_id, etc.
    transformations: list[dict] = field(default_factory=list)
    created_at: str = ""
    annotations: dict[str, Any] = field(default_factory=dict)


# =============================================================================
# Quality Gates
# =============================================================================

class QualityGate(ABC):
    """Abstract quality gate that validates dataset quality."""
    @abstractmethod
    def check(self, version: DatasetVersion, schema: DatasetSchema) -> dict: ...


class SchemaComplianceGate(QualityGate):
    """Ensures all examples comply with the schema."""
    def check(self, version: DatasetVersion, schema: DatasetSchema) -> dict:
        violations = []
        for example in version.examples:
            errors = schema.validate_example(example.data)
            if errors:
                violations.append({"example_id": example.id, "errors": errors})

        compliance_rate = 1.0 - (len(violations) / max(len(version.examples), 1))
        return {
            "gate": "schema_compliance",
            "passed": compliance_rate >= 0.99,
            "compliance_rate": compliance_rate,
            "violation_count": len(violations),
            "violations_sample": violations[:10],
            "blocking": True
        }


class DiversityGate(QualityGate):
    """Ensures dataset has sufficient diversity across categories."""
    def __init__(self, category_field: str, min_categories: int = 5, max_imbalance_ratio: float = 10.0):
        self.category_field = category_field
        self.min_categories = min_categories
        self.max_imbalance_ratio = max_imbalance_ratio

    def check(self, version: DatasetVersion, schema: DatasetSchema) -> dict:
        categories = Counter()
        for example in version.examples:
            cat = example.data.get(self.category_field) or example.metadata.get(self.category_field, "unknown")
            categories[cat] += 1

        num_categories = len(categories)
        if not categories:
            return {"gate": "diversity", "passed": False, "reason": "No categories found", "blocking": False}

        most_common = categories.most_common(1)[0][1]
        least_common = categories.most_common()[-1][1]
        imbalance_ratio = most_common / max(least_common, 1)

        passed = num_categories >= self.min_categories and imbalance_ratio <= self.max_imbalance_ratio
        return {
            "gate": "diversity",
            "passed": passed,
            "num_categories": num_categories,
            "imbalance_ratio": imbalance_ratio,
            "category_distribution": dict(categories.most_common(20)),
            "blocking": False
        }


class SizeGate(QualityGate):
    """Ensures dataset meets minimum size requirements."""
    def __init__(self, min_total: int = 100, min_per_split: dict = None):
        self.min_total = min_total
        self.min_per_split = min_per_split or {"test": 50, "golden": 20}

    def check(self, version: DatasetVersion, schema: DatasetSchema) -> dict:
        total = len(version.examples)
        split_counts = Counter(e.split.value for e in version.examples)

        issues = []
        if total < self.min_total:
            issues.append(f"Total examples ({total}) below minimum ({self.min_total})")

        for split, min_count in self.min_per_split.items():
            actual = split_counts.get(split, 0)
            if actual < min_count:
                issues.append(f"Split '{split}' has {actual} examples, needs {min_count}")

        return {
            "gate": "size",
            "passed": len(issues) == 0,
            "total_examples": total,
            "split_counts": dict(split_counts),
            "issues": issues,
            "blocking": True
        }


class DeduplicationGate(QualityGate):
    """Detects and reports duplicate examples."""
    def __init__(self, max_duplicate_rate: float = 0.05):
        self.max_duplicate_rate = max_duplicate_rate

    def check(self, version: DatasetVersion, schema: DatasetSchema) -> dict:
        seen_hashes = {}
        duplicates = []

        for example in version.examples:
            h = hashlib.md5(json.dumps(example.data, sort_keys=True).encode()).hexdigest()
            if h in seen_hashes:
                duplicates.append({"example_id": example.id, "duplicate_of": seen_hashes[h]})
            else:
                seen_hashes[h] = example.id

        duplicate_rate = len(duplicates) / max(len(version.examples), 1)
        return {
            "gate": "deduplication",
            "passed": duplicate_rate <= self.max_duplicate_rate,
            "duplicate_rate": duplicate_rate,
            "duplicate_count": len(duplicates),
            "duplicates_sample": duplicates[:10],
            "blocking": False
        }


# =============================================================================
# Dataset Diff Engine
# =============================================================================

class DatasetDiffEngine:
    """Computes diffs between dataset versions."""

    @staticmethod
    def diff(old_version: DatasetVersion, new_version: DatasetVersion) -> dict:
        """Compute a comprehensive diff between two dataset versions."""
        old_ids = {e.id: e for e in old_version.examples}
        new_ids = {e.id: e for e in new_version.examples}

        added = [e for eid, e in new_ids.items() if eid not in old_ids]
        removed = [e for eid, e in old_ids.items() if eid not in new_ids]
        
        modified = []
        for eid in set(old_ids.keys()) & set(new_ids.keys()):
            if old_ids[eid].data != new_ids[eid].data:
                modified.append({
                    "id": eid,
                    "old": old_ids[eid].data,
                    "new": new_ids[eid].data
                })

        # Split distribution changes
        old_splits = Counter(e.split.value for e in old_version.examples)
        new_splits = Counter(e.split.value for e in new_version.examples)

        return {
            "added_count": len(added),
            "removed_count": len(removed),
            "modified_count": len(modified),
            "unchanged_count": len(old_ids) - len(removed) - len(modified),
            "added_sample": [asdict(e) for e in added[:5]],
            "removed_sample": [asdict(e) for e in removed[:5]],
            "modified_sample": modified[:5],
            "old_split_distribution": dict(old_splits),
            "new_split_distribution": dict(new_splits),
            "schema_changed": old_version.schema_version != new_version.schema_version,
        }


# =============================================================================
# Production Feedback Pipeline
# =============================================================================

@dataclass
class ProductionFeedback:
    """Feedback from production that can become a dataset example."""
    id: str
    trace_id: str
    input_data: dict[str, Any]
    output_data: dict[str, Any]
    feedback_type: str  # thumbs_up, thumbs_down, correction, escalation
    feedback_value: Any  # The actual feedback (corrected output, rating, etc.)
    user_id: Optional[str] = None
    timestamp: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class FeedbackToDatasetPipeline:
    """Converts production feedback into dataset examples."""

    def __init__(self, schema: DatasetSchema):
        self.schema = schema
        self.pending_feedback: list[ProductionFeedback] = []
        self.processed_feedback: list[str] = []
        self.conversion_rules: list[callable] = []

    def add_feedback(self, feedback: ProductionFeedback):
        """Add production feedback to the pipeline."""
        self.pending_feedback.append(feedback)

    def add_conversion_rule(self, rule: callable):
        """Add a rule for converting feedback to examples."""
        self.conversion_rules.append(rule)

    def process(self, min_confidence: float = 0.8) -> list[DatasetExample]:
        """Process pending feedback into dataset examples."""
        new_examples = []

        for feedback in self.pending_feedback:
            example = self._convert_feedback(feedback)
            if example:
                # Validate against schema
                errors = self.schema.validate_example(example.data)
                if not errors:
                    new_examples.append(example)
                    self.processed_feedback.append(feedback.id)

        # Clear processed
        self.pending_feedback = [f for f in self.pending_feedback if f.id not in self.processed_feedback]
        return new_examples

    def _convert_feedback(self, feedback: ProductionFeedback) -> Optional[DatasetExample]:
        """Convert a single feedback item to a dataset example."""
        # Apply custom conversion rules first
        for rule in self.conversion_rules:
            result = rule(feedback)
            if result:
                return result

        # Default conversion based on feedback type
        if feedback.feedback_type == "correction":
            return DatasetExample(
                id=str(uuid.uuid4()),
                data={
                    "input": feedback.input_data,
                    "expected_output": feedback.feedback_value,
                    "original_output": feedback.output_data,
                },
                metadata={
                    "source_trace": feedback.trace_id,
                    "feedback_type": feedback.feedback_type,
                },
                split=SplitType.PRODUCTION,
                source="production_feedback",
                created_at=datetime.now(timezone.utc).isoformat(),
                lineage={
                    "source_type": "production_feedback",
                    "trace_id": feedback.trace_id,
                    "feedback_id": feedback.id,
                }
            )
        elif feedback.feedback_type == "thumbs_up":
            return DatasetExample(
                id=str(uuid.uuid4()),
                data={
                    "input": feedback.input_data,
                    "expected_output": feedback.output_data,
                },
                metadata={
                    "source_trace": feedback.trace_id,
                    "quality": "verified_good",
                },
                split=SplitType.PRODUCTION,
                source="production_positive",
                created_at=datetime.now(timezone.utc).isoformat(),
                lineage={
                    "source_type": "production_positive",
                    "trace_id": feedback.trace_id,
                }
            )
        return None


# =============================================================================
# Main Dataset Versioning System
# =============================================================================

class DatasetVersioningSystem:
    """
    Complete dataset versioning system.
    
    Features:
    - Schema-driven validation
    - Immutable versions with content-addressable hashing
    - Quality gates (compliance, diversity, size, deduplication)
    - Production feedback pipeline
    - Diff and comparison
    - Split management
    - Lineage tracking
    - Automated refresh
    """

    def __init__(self):
        self.schemas: dict[str, DatasetSchema] = {}
        self.versions: dict[str, list[DatasetVersion]] = {}
        self.lineage: dict[str, LineageRecord] = {}
        self.quality_gates: list[QualityGate] = [
            SchemaComplianceGate(),
            DiversityGate(category_field="category"),
            SizeGate(min_total=10, min_per_split={"test": 5}),
            DeduplicationGate(),
        ]
        self.feedback_pipelines: dict[str, FeedbackToDatasetPipeline] = {}
        self._current_user = "system"

    def set_user(self, user: str):
        self._current_user = user

    # -------------------------------------------------------------------------
    # Schema Management
    # -------------------------------------------------------------------------

    def create_schema(self, dataset_id: str, name: str, fields: list[FieldSchema],
                      description: str = "") -> DatasetSchema:
        """Create or update the schema for a dataset."""
        existing = self.schemas.get(dataset_id)
        version = (existing.version + 1) if existing else 1

        schema = DatasetSchema(
            id=dataset_id,
            name=name,
            version=version,
            fields=fields,
            description=description,
            created_at=datetime.now(timezone.utc).isoformat(),
            created_by=self._current_user,
        )
        self.schemas[dataset_id] = schema
        return schema

    # -------------------------------------------------------------------------
    # Version Management
    # -------------------------------------------------------------------------

    def create_version(
        self,
        dataset_id: str,
        examples: list[DatasetExample],
        message: str = "",
        metadata: dict = None,
        run_quality_gates: bool = True
    ) -> DatasetVersion:
        """Create a new version of a dataset."""
        schema = self.schemas.get(dataset_id)
        if not schema:
            raise ValueError(f"No schema defined for dataset '{dataset_id}'")

        existing_versions = self.versions.get(dataset_id, [])
        version_num = len(existing_versions) + 1

        # Compute split counts
        split_counts = Counter(e.split.value for e in examples)

        version = DatasetVersion(
            id=str(uuid.uuid4()),
            dataset_id=dataset_id,
            version=version_num,
            schema_version=schema.version,
            examples=examples,
            metadata=metadata or {},
            content_hash=DatasetVersion.compute_hash(examples),
            created_at=datetime.now(timezone.utc).isoformat(),
            created_by=self._current_user,
            message=message,
            parent_version=version_num - 1 if version_num > 1 else None,
            split_counts=dict(split_counts),
        )

        # Run quality gates
        if run_quality_gates:
            gate_result = self.run_quality_gates(version)
            version.quality_metrics = {
                "overall_passed": gate_result.passed,
                "score": gate_result.overall_score,
                "checks": gate_result.checks,
            }
            version.status = DatasetStatus.VALID if gate_result.passed else DatasetStatus.INVALID

        if dataset_id not in self.versions:
            self.versions[dataset_id] = []
        self.versions[dataset_id].append(version)

        # Track lineage for new examples
        for example in examples:
            if example.lineage:
                self.lineage[example.id] = LineageRecord(
                    example_id=example.id,
                    source_type=example.lineage.get("source_type", "unknown"),
                    source_id=example.lineage.get("source_id"),
                    created_at=example.created_at,
                )

        return version

    def get_version(self, dataset_id: str, version: int) -> Optional[DatasetVersion]:
        versions = self.versions.get(dataset_id, [])
        for v in versions:
            if v.version == version:
                return v
        return None

    def get_latest_version(self, dataset_id: str) -> Optional[DatasetVersion]:
        versions = self.versions.get(dataset_id, [])
        return versions[-1] if versions else None

    def get_split(self, dataset_id: str, version: int, split: SplitType) -> list[DatasetExample]:
        """Get examples for a specific split."""
        v = self.get_version(dataset_id, version)
        if not v:
            return []
        return [e for e in v.examples if e.split == split]

    # -------------------------------------------------------------------------
    # Quality Gates
    # -------------------------------------------------------------------------

    def run_quality_gates(self, version: DatasetVersion) -> QualityGateResult:
        """Run all quality gates on a dataset version."""
        schema = self.schemas.get(version.dataset_id)
        checks = []
        blocking_failures = []
        warnings = []

        for gate in self.quality_gates:
            result = gate.check(version, schema)
            checks.append(result)
            if not result["passed"]:
                if result.get("blocking", False):
                    blocking_failures.append(result["gate"])
                else:
                    warnings.append(result["gate"])

        passed = len(blocking_failures) == 0
        score = sum(1 for c in checks if c["passed"]) / max(len(checks), 1)

        return QualityGateResult(
            passed=passed,
            checks=checks,
            overall_score=score,
            blocking_failures=blocking_failures,
            warnings=warnings,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    # -------------------------------------------------------------------------
    # Diff and Comparison
    # -------------------------------------------------------------------------

    def diff_versions(self, dataset_id: str, v1: int, v2: int) -> dict:
        """Compute diff between two versions."""
        version1 = self.get_version(dataset_id, v1)
        version2 = self.get_version(dataset_id, v2)
        if not version1 or not version2:
            raise ValueError("Version not found")
        return DatasetDiffEngine.diff(version1, version2)

    # -------------------------------------------------------------------------
    # Production Feedback Integration
    # -------------------------------------------------------------------------

    def setup_feedback_pipeline(self, dataset_id: str) -> FeedbackToDatasetPipeline:
        """Set up a feedback pipeline for a dataset."""
        schema = self.schemas.get(dataset_id)
        if not schema:
            raise ValueError(f"No schema for dataset '{dataset_id}'")
        pipeline = FeedbackToDatasetPipeline(schema)
        self.feedback_pipelines[dataset_id] = pipeline
        return pipeline

    def ingest_feedback(self, dataset_id: str, feedback: ProductionFeedback):
        """Ingest production feedback for a dataset."""
        pipeline = self.feedback_pipelines.get(dataset_id)
        if not pipeline:
            raise ValueError(f"No feedback pipeline for '{dataset_id}'")
        pipeline.add_feedback(feedback)

    def process_feedback(self, dataset_id: str) -> list[DatasetExample]:
        """Process pending feedback into new examples."""
        pipeline = self.feedback_pipelines.get(dataset_id)
        if not pipeline:
            return []
        return pipeline.process()

    def refresh_from_feedback(self, dataset_id: str, message: str = "Auto-refresh from feedback") -> Optional[DatasetVersion]:
        """Create a new version incorporating processed feedback."""
        new_examples = self.process_feedback(dataset_id)
        if not new_examples:
            return None

        latest = self.get_latest_version(dataset_id)
        if not latest:
            raise ValueError(f"No existing version for '{dataset_id}'")

        # Merge new examples with existing
        all_examples = list(latest.examples) + new_examples

        return self.create_version(
            dataset_id,
            all_examples,
            message=f"{message} (+{len(new_examples)} examples from feedback)",
            metadata={**latest.metadata, "refresh_source": "feedback", "new_examples": len(new_examples)}
        )

    # -------------------------------------------------------------------------
    # Lineage
    # -------------------------------------------------------------------------

    def get_lineage(self, example_id: str) -> Optional[LineageRecord]:
        return self.lineage.get(example_id)

    def get_lineage_summary(self, dataset_id: str, version: int) -> dict:
        """Get lineage summary for a dataset version."""
        v = self.get_version(dataset_id, version)
        if not v:
            return {}

        source_counts = Counter(e.source for e in v.examples)
        lineage_counts = Counter()
        for e in v.examples:
            record = self.lineage.get(e.id)
            if record:
                lineage_counts[record.source_type] += 1

        return {
            "total_examples": len(v.examples),
            "by_source": dict(source_counts),
            "by_lineage_type": dict(lineage_counts),
            "with_lineage": sum(1 for e in v.examples if e.id in self.lineage),
            "without_lineage": sum(1 for e in v.examples if e.id not in self.lineage),
        }


# =============================================================================
# Usage Example
# =============================================================================

def main():
    """Demonstrate the dataset versioning system."""
    system = DatasetVersioningSystem()
    system.set_user("data-engineer@company.com")

    # Define schema
    schema = system.create_schema(
        dataset_id="customer-support-eval",
        name="Customer Support Evaluation Dataset",
        fields=[
            FieldSchema(name="input", field_type=FieldType.TEXT, description="Customer query"),
            FieldSchema(name="expected_output", field_type=FieldType.TEXT, description="Expected response"),
            FieldSchema(name="category", field_type=FieldType.LABEL, description="Query category",
                       enum_values=["billing", "technical", "account", "general", "complaint"]),
            FieldSchema(name="difficulty", field_type=FieldType.LABEL, description="Difficulty level",
                       enum_values=["easy", "medium", "hard"]),
            FieldSchema(name="quality_score", field_type=FieldType.SCORE, description="Expected quality",
                       min_value=1, max_value=5, required=False, nullable=True),
        ],
        description="Evaluation dataset for customer support agent"
    )
    print(f"Created schema v{schema.version}: {schema.name}")

    # Create initial dataset
    examples = []
    categories = ["billing", "technical", "account", "general", "complaint"]
    difficulties = ["easy", "medium", "hard"]

    for i in range(50):
        examples.append(DatasetExample(
            id=str(uuid.uuid4()),
            data={
                "input": f"Sample customer query #{i} about {categories[i % 5]}",
                "expected_output": f"Expected helpful response for query #{i}",
                "category": categories[i % 5],
                "difficulty": difficulties[i % 3],
                "quality_score": 4 if i % 3 == 0 else None,
            },
            metadata={"annotator": f"annotator-{i % 3}"},
            split=SplitType.TEST if i < 30 else SplitType.GOLDEN,
            source="manual",
            created_at=datetime.now(timezone.utc).isoformat(),
        ))

    v1 = system.create_version(
        "customer-support-eval",
        examples,
        message="Initial dataset with 50 examples",
        metadata={"project": "support-agent-v2"}
    )
    print(f"\nCreated v{v1.version} (hash: {v1.content_hash})")
    print(f"  Status: {v1.status.value}")
    print(f"  Splits: {v1.split_counts}")
    print(f"  Quality: {v1.quality_metrics.get('overall_passed', 'N/A')}")

    # Set up feedback pipeline
    pipeline = system.setup_feedback_pipeline("customer-support-eval")
    print("\nFeedback pipeline configured")

    # Simulate production feedback
    for i in range(5):
        system.ingest_feedback("customer-support-eval", ProductionFeedback(
            id=str(uuid.uuid4()),
            trace_id=f"trace-{uuid.uuid4().hex[:8]}",
            input_data={"input": f"Real user query about billing issue #{i}", "category": "billing", "difficulty": "medium"},
            output_data={"output": f"Agent response #{i}"},
            feedback_type="correction" if i % 2 == 0 else "thumbs_up",
            feedback_value=f"Better response for query #{i}" if i % 2 == 0 else None,
            timestamp=datetime.now(timezone.utc).isoformat(),
        ))

    # Refresh dataset from feedback
    v2 = system.refresh_from_feedback("customer-support-eval")
    if v2:
        print(f"\nRefreshed to v{v2.version} (hash: {v2.content_hash})")
        print(f"  Total examples: {len(v2.examples)}")
        print(f"  Splits: {v2.split_counts}")

        # Diff versions
        diff = system.diff_versions("customer-support-eval", 1, 2)
        print(f"\nDiff v1 → v2:")
        print(f"  Added: {diff['added_count']}")
        print(f"  Removed: {diff['removed_count']}")
        print(f"  Modified: {diff['modified_count']}")

    # Lineage summary
    lineage = system.get_lineage_summary("customer-support-eval", v2.version if v2 else 1)
    print(f"\nLineage summary: {json.dumps(lineage, indent=2)}")


if __name__ == "__main__":
    main()
