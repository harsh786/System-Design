# Multi-Source Data Aggregation with Schema Evolution

## The Production Problem

A large enterprise (financial services, healthcare, or e-commerce conglomerate) ingests data from **200+ heterogeneous sources** into a unified lakehouse:

- 80+ internal microservices (each deploying independently, changing schemas weekly)
- 40+ third-party APIs (vendors change payloads without notice)
- 30+ legacy systems from 5 acquired companies (different naming conventions, types)
- 20+ SaaS platforms (Salesforce, HubSpot, Stripe — each with their own schema versioning)
- 15+ IoT device fleets (firmware updates change telemetry schemas)
- Government/regulatory feeds with mandated format changes

**The pain**: On average, **12-15 schema changes happen daily** across these sources. With traditional Hive/Parquet pipelines, each change requires:
1. Pipeline stop
2. Manual schema investigation
3. DDL change + backfill
4. Pipeline restart + validation

This means **constant breakage, 3-4 hours MTTR per incident, and 40+ hours/week of engineering toil**.

---

## Why Iceberg Solves This (vs Hive/Parquet)

### The Hive/Parquet Problem

```
┌─────────────────────────────────────────────────────────────────┐
│  HIVE/PARQUET: Schema = File Structure                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Parquet files store schema BY POSITION:                        │
│    Column 0 → "user_id" (INT)                                  │
│    Column 1 → "name" (STRING)                                  │
│    Column 2 → "email" (STRING)                                 │
│                                                                 │
│  If source ADDS a column between name and email:                │
│    Column 0 → "user_id" (INT)                                  │
│    Column 1 → "name" (STRING)                                  │
│    Column 2 → "phone" (STRING)  ← NEW                          │
│    Column 3 → "email" (STRING)                                  │
│                                                                 │
│  Old files: position 2 = email                                  │
│  New files: position 2 = phone                                  │
│  RESULT: CORRUPT DATA, SILENT ERRORS                            │
│                                                                 │
│  Renaming a column? → All consumers break                       │
│  Widening INT → LONG? → Type mismatch exceptions                │
│  Dropping a column? → Position shift corrupts everything         │
└─────────────────────────────────────────────────────────────────┘
```

### The Iceberg Solution

```
┌─────────────────────────────────────────────────────────────────┐
│  ICEBERG: Schema = Column IDs (Internal Mapping)                │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Every column gets a UNIQUE, IMMUTABLE integer ID:              │
│    ID 1 → "user_id" (INT)                                      │
│    ID 2 → "name" (STRING)                                      │
│    ID 3 → "email" (STRING)                                     │
│                                                                 │
│  ADD column "phone":                                            │
│    ID 1 → "user_id" (INT)                                      │
│    ID 2 → "name" (STRING)                                      │
│    ID 3 → "email" (STRING)                                     │
│    ID 4 → "phone" (STRING)  ← New ID, no position conflict     │
│                                                                 │
│  RENAME "name" → "full_name":                                   │
│    ID 2 still maps to same physical data                        │
│    Old files still readable via ID 2                            │
│                                                                 │
│  WIDEN INT → LONG:                                              │
│    ID 1 → "user_id" (LONG) — safe promotion, old data reads    │
│                                                                 │
│  DROP "email":                                                  │
│    ID 3 marked as deleted, never reused                         │
│    Old files: ID 3 data simply ignored on read                  │
│                                                                 │
│  RESULT: Zero breakage. Full backward/forward compatibility.    │
└─────────────────────────────────────────────────────────────────┘
```

### Key Differentiators

| Operation | Hive/Parquet | Iceberg |
|-----------|-------------|---------|
| Add column | Must be at END only | Anywhere, assigned new ID |
| Drop column | Breaks positional reads | ID retired, data ignored |
| Rename column | All consumers break | ID unchanged, name updated |
| Reorder columns | Impossible without rewrite | Metadata-only operation |
| Widen type (int→long) | Full table rewrite | Metadata update, read-time promotion |
| Nested field evolution | Not supported | Full struct/map/list evolution |
| Schema across partitions | Must match exactly | Each partition can differ |
| Time-travel with old schema | Impossible | Read old data with any schema version |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    MULTI-SOURCE SCHEMA EVOLUTION PLATFORM                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐        │
│  │Microsvcs │ │3rd Party │ │ Legacy   │ │  SaaS    │ │   IoT    │        │
│  │  (80+)   │ │APIs (40+)│ │Sys (30+) │ │Plat(20+) │ │Fleet(15+)│        │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘        │
│       │             │             │             │             │              │
│       ▼             ▼             ▼             ▼             ▼              │
│  ┌─────────────────────────────────────────────────────────────────┐       │
│  │              KAFKA + SCHEMA REGISTRY (Confluent)                 │       │
│  │  - Avro/Protobuf schemas with compatibility modes               │       │
│  │  - Schema ID embedded in message headers                        │       │
│  │  - BACKWARD/FORWARD/FULL compatibility enforcement              │       │
│  └───────────────────────────────┬─────────────────────────────────┘       │
│                                  │                                          │
│                                  ▼                                          │
│  ┌─────────────────────────────────────────────────────────────────┐       │
│  │              SCHEMA EVOLUTION ENGINE (Spark)                      │       │
│  │                                                                   │       │
│  │  ┌─────────────┐  ┌──────────────┐  ┌────────────────────┐      │       │
│  │  │Schema Drift │  │ Type Safety  │  │ Union-by-Name      │      │       │
│  │  │ Detector    │  │ Promoter     │  │ Merger             │      │       │
│  │  └─────────────┘  └──────────────┘  └────────────────────┘      │       │
│  │                                                                   │       │
│  │  ┌─────────────┐  ┌──────────────┐  ┌────────────────────┐      │       │
│  │  │Breaking     │  │ Nested Type  │  │ Partition          │      │       │
│  │  │Change Guard │  │ Evolver      │  │ Evolver            │      │       │
│  │  └─────────────┘  └──────────────┘  └────────────────────┘      │       │
│  └───────────────────────────────┬─────────────────────────────────┘       │
│                                  │                                          │
│                                  ▼                                          │
│  ┌─────────────────────────────────────────────────────────────────┐       │
│  │              ICEBERG LAKEHOUSE (S3 + AWS Glue Catalog)           │       │
│  │                                                                   │       │
│  │  ┌───────────────────────────────────────────────────────┐       │       │
│  │  │  Schema Metadata (per table):                          │       │       │
│  │  │    - Current schema (latest version)                   │       │       │
│  │  │    - All historical schemas (time-travel)              │       │       │
│  │  │    - Column ID → name mapping                          │       │       │
│  │  │    - Type promotion history                            │       │       │
│  │  └───────────────────────────────────────────────────────┘       │       │
│  └───────────────────────────────┬─────────────────────────────────┘       │
│                                  │                                          │
│                                  ▼                                          │
│  ┌─────────────────────────────────────────────────────────────────┐       │
│  │              MONITORING & GOVERNANCE                              │       │
│  │  - Schema drift alerts (PagerDuty)                               │       │
│  │  - Column lineage tracking                                       │       │
│  │  - Type conflict detection                                       │       │
│  │  - Breaking change approval workflow                             │       │
│  └─────────────────────────────────────────────────────────────────┘       │
│                                                                             │
│  ORCHESTRATION: Airflow DAGs (per-source + aggregation + validation)        │
│  TRANSFORMS: dbt models (union logic, deduplication, SCD)                   │
│  VALIDATION: Great Expectations (schema + data quality checks)              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Iceberg Schema Evolution Deep Dive

### Column ID System

```sql
-- Iceberg assigns internal IDs to every column. These NEVER change.
-- View the internal schema with IDs:

-- Initial table creation
CREATE TABLE lakehouse.unified.customers (
    customer_id     BIGINT,        -- Assigned ID: 1
    name            STRING,        -- Assigned ID: 2
    email           STRING,        -- Assigned ID: 3
    created_at      TIMESTAMP      -- Assigned ID: 4
) USING iceberg;

-- After ADD COLUMN:
ALTER TABLE lakehouse.unified.customers ADD COLUMN phone STRING;
-- phone gets ID: 5

-- After RENAME:
ALTER TABLE lakehouse.unified.customers RENAME COLUMN name TO full_name;
-- full_name still has ID: 2 — old Parquet files with "name" still readable

-- After DROP + RE-ADD with same name:
ALTER TABLE lakehouse.unified.customers DROP COLUMN email;
-- ID 3 is RETIRED (never reused)

ALTER TABLE lakehouse.unified.customers ADD COLUMN email STRING;
-- email gets NEW ID: 6 — completely independent from old "email"
```

### Safe Type Promotions

Iceberg allows these promotions without rewriting data:

```
int       → long
float     → double
decimal   → decimal (wider precision/scale)
date      → timestamp (with time = 00:00:00)
```

```sql
-- Example: source starts sending larger IDs
ALTER TABLE lakehouse.unified.orders
    ALTER COLUMN order_id TYPE BIGINT;  -- was INT, promoted to LONG

-- Old parquet files with INT values are read and promoted at read-time
-- No data rewrite needed. Zero downtime.

-- Decimal widening:
ALTER TABLE lakehouse.unified.transactions
    ALTER COLUMN amount TYPE DECIMAL(18, 4);  -- was DECIMAL(10, 2)
```

### Nested Type Evolution

```sql
-- Structs: add/drop/rename fields inside structs
ALTER TABLE lakehouse.unified.events
    ADD COLUMN payload.new_field STRING;

ALTER TABLE lakehouse.unified.events
    RENAME COLUMN payload.old_name TO payload.new_name;

-- Maps: evolve value types
-- map<string, int> → map<string, long> (value type promotion)
ALTER TABLE lakehouse.unified.metrics
    ALTER COLUMN tags TYPE MAP<STRING, LONG>;

-- Lists: evolve element types
-- list<int> → list<long>
ALTER TABLE lakehouse.unified.scores
    ALTER COLUMN values TYPE LIST<LONG>;
```

### Partition Evolution

```sql
-- Start with daily partitions
CREATE TABLE lakehouse.unified.events (
    event_id    BIGINT,
    event_time  TIMESTAMP,
    source      STRING,
    payload     STRING
) USING iceberg
PARTITIONED BY (days(event_time));

-- Traffic grows — switch to hourly partitions (NO REWRITE)
ALTER TABLE lakehouse.unified.events
    ADD PARTITION FIELD hours(event_time);

-- Old data stays in daily partitions
-- New data writes to hourly partitions
-- Queries spanning both work transparently via metadata
```

---

## Production Code: Schema Evolution Engine

### Core Schema Drift Detector

```python
"""
schema_evolution_engine.py

Production schema drift detection and automatic evolution for 200+ sources.
Handles: new columns, type changes, renames, drops, nested evolution.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import logging
import json

from pyspark.sql import SparkSession, DataFrame
from pyspark.sql.types import (
    StructType, StructField, StringType, IntegerType,
    LongType, DoubleType, FloatType, DecimalType,
    TimestampType, DateType, BooleanType, ArrayType, MapType
)

logger = logging.getLogger(__name__)


class ChangeType(Enum):
    ADD_COLUMN = "add_column"
    DROP_COLUMN = "drop_column"
    RENAME_COLUMN = "rename_column"
    WIDEN_TYPE = "widen_type"
    NARROW_TYPE = "narrow_type"          # BREAKING
    INCOMPATIBLE_TYPE = "incompatible_type"  # BREAKING
    ADD_NESTED_FIELD = "add_nested_field"
    NULLABILITY_CHANGE = "nullability_change"


class Severity(Enum):
    SAFE = "safe"           # Auto-apply
    WARNING = "warning"     # Apply with alert
    BREAKING = "breaking"   # Requires approval


# Safe type promotion paths (Iceberg-compatible)
SAFE_PROMOTIONS = {
    IntegerType: {LongType, FloatType, DoubleType, DecimalType},
    LongType: {FloatType, DoubleType, DecimalType},
    FloatType: {DoubleType},
    DateType: {TimestampType},
}


@dataclass
class SchemaChange:
    change_type: ChangeType
    severity: Severity
    column_path: str
    old_type: Optional[str] = None
    new_type: Optional[str] = None
    source: str = ""
    details: str = ""


@dataclass
class SchemaEvolutionResult:
    source_name: str
    table_name: str
    changes: list = field(default_factory=list)
    applied: list = field(default_factory=list)
    blocked: list = field(default_factory=list)
    requires_approval: list = field(default_factory=list)


class SchemaEvolutionEngine:
    """
    Detects schema drift between incoming data and existing Iceberg tables.
    Automatically applies safe changes; blocks breaking changes.
    """

    def __init__(self, spark: SparkSession, catalog: str = "glue_catalog"):
        self.spark = spark
        self.catalog = catalog
        self.change_log = []

    def detect_drift(
        self, incoming_schema: StructType, table_name: str, source: str
    ) -> SchemaEvolutionResult:
        """
        Compare incoming data schema against current Iceberg table schema.
        Returns categorized list of changes.
        """
        result = SchemaEvolutionResult(source_name=source, table_name=table_name)

        try:
            current_schema = self.spark.table(
                f"{self.catalog}.{table_name}"
            ).schema
        except Exception:
            # Table doesn't exist — first load, no drift
            logger.info(f"Table {table_name} does not exist. Will create.")
            return result

        current_fields = {f.name: f for f in current_schema.fields}
        incoming_fields = {f.name: f for f in incoming_schema.fields}

        # Detect NEW columns (in incoming but not in current)
        for name, field in incoming_fields.items():
            if name not in current_fields:
                change = SchemaChange(
                    change_type=ChangeType.ADD_COLUMN,
                    severity=Severity.SAFE,
                    column_path=name,
                    new_type=str(field.dataType),
                    source=source,
                    details=f"New column '{name}' ({field.dataType}) from source '{source}'"
                )
                result.changes.append(change)

        # Detect DROPPED columns (in current but not in incoming)
        for name, field in current_fields.items():
            if name not in incoming_fields:
                change = SchemaChange(
                    change_type=ChangeType.DROP_COLUMN,
                    severity=Severity.WARNING,
                    column_path=name,
                    old_type=str(field.dataType),
                    source=source,
                    details=(
                        f"Column '{name}' missing from source '{source}'. "
                        f"May be intentional drop or source-specific absence."
                    )
                )
                result.changes.append(change)

        # Detect TYPE CHANGES
        for name in set(current_fields) & set(incoming_fields):
            current_type = current_fields[name].dataType
            incoming_type = incoming_fields[name].dataType

            if current_type != incoming_type:
                severity = self._classify_type_change(current_type, incoming_type)
                change = SchemaChange(
                    change_type=(
                        ChangeType.WIDEN_TYPE if severity == Severity.SAFE
                        else ChangeType.INCOMPATIBLE_TYPE
                    ),
                    severity=severity,
                    column_path=name,
                    old_type=str(current_type),
                    new_type=str(incoming_type),
                    source=source,
                    details=(
                        f"Type change on '{name}': "
                        f"{current_type} → {incoming_type}"
                    )
                )
                result.changes.append(change)

        # Categorize
        for change in result.changes:
            if change.severity == Severity.SAFE:
                result.applied.append(change)
            elif change.severity == Severity.BREAKING:
                result.blocked.append(change)
            else:
                result.requires_approval.append(change)

        return result

    def _classify_type_change(self, current, incoming) -> Severity:
        """Classify whether a type change is safe, warning, or breaking."""
        current_class = type(current)
        incoming_class = type(incoming)

        # Check safe promotions
        if current_class in SAFE_PROMOTIONS:
            if incoming_class in SAFE_PROMOTIONS[current_class]:
                return Severity.SAFE

        # Decimal widening (precision/scale increase)
        if isinstance(current, DecimalType) and isinstance(incoming, DecimalType):
            if (incoming.precision >= current.precision and
                    incoming.scale >= current.scale):
                return Severity.SAFE

        # String can absorb anything (common in multi-source scenarios)
        if isinstance(incoming, StringType):
            return Severity.WARNING  # Safe but may indicate upstream issue

        # Everything else is breaking
        return Severity.BREAKING

    def apply_safe_changes(self, result: SchemaEvolutionResult) -> list:
        """
        Apply all SAFE schema changes to the Iceberg table via ALTER TABLE.
        Returns list of applied DDL statements.
        """
        applied_ddl = []
        table = f"{self.catalog}.{result.table_name}"

        for change in result.applied:
            ddl = None

            if change.change_type == ChangeType.ADD_COLUMN:
                ddl = (
                    f"ALTER TABLE {table} "
                    f"ADD COLUMN {change.column_path} {change.new_type}"
                )

            elif change.change_type == ChangeType.WIDEN_TYPE:
                ddl = (
                    f"ALTER TABLE {table} "
                    f"ALTER COLUMN {change.column_path} TYPE {change.new_type}"
                )

            if ddl:
                try:
                    self.spark.sql(ddl)
                    applied_ddl.append(ddl)
                    logger.info(f"Applied: {ddl}")
                    self._log_change(result.source_name, result.table_name, change)
                except Exception as e:
                    logger.error(f"Failed to apply {ddl}: {e}")
                    change.severity = Severity.BREAKING
                    result.blocked.append(change)
                    result.applied.remove(change)

        return applied_ddl

    def _log_change(self, source: str, table: str, change: SchemaChange):
        """Log schema change to audit table for tracking."""
        self.spark.sql(f"""
            INSERT INTO {self.catalog}.schema_audit.change_log
            VALUES (
                current_timestamp(),
                '{source}',
                '{table}',
                '{change.change_type.value}',
                '{change.column_path}',
                '{change.old_type or ""}',
                '{change.new_type or ""}',
                '{change.severity.value}',
                '{change.details}'
            )
        """)
```

### Union-by-Name Multi-Source Merger

```python
"""
union_by_name_merger.py

Merges DataFrames from 200+ sources with different schemas into unified tables.
Uses Spark's union-by-name with Iceberg's schema evolution for seamless merging.
"""

from pyspark.sql import SparkSession, DataFrame
from pyspark.sql.functions import lit, col, current_timestamp, input_file_name
from pyspark.sql.types import StructType, StructField, StringType, NullType
from typing import List, Dict, Tuple
import logging

logger = logging.getLogger(__name__)


class MultiSourceMerger:
    """
    Merges DataFrames from heterogeneous sources using union-by-name strategy.
    Missing columns become NULL. Type conflicts resolved via widening.
    """

    def __init__(self, spark: SparkSession, evolution_engine):
        self.spark = spark
        self.engine = evolution_engine

    def merge_sources(
        self,
        source_frames: Dict[str, DataFrame],
        target_table: str,
        add_metadata: bool = True
    ) -> DataFrame:
        """
        Merge multiple source DataFrames into a single unified DataFrame.

        Strategy:
        1. Compute superset schema (all columns from all sources)
        2. Add missing columns as NULL to each source
        3. Align types via safe promotion
        4. Union by name
        5. Detect and apply schema evolution to target table
        """
        if not source_frames:
            raise ValueError("No source frames to merge")

        # Step 1: Compute superset schema
        superset = self._compute_superset_schema(source_frames)
        logger.info(
            f"Superset schema has {len(superset.fields)} columns "
            f"from {len(source_frames)} sources"
        )

        # Step 2+3: Align each source to superset
        aligned_frames = []
        for source_name, df in source_frames.items():
            aligned = self._align_to_superset(df, superset, source_name)
            if add_metadata:
                aligned = (
                    aligned
                    .withColumn("_source_system", lit(source_name))
                    .withColumn("_ingested_at", current_timestamp())
                    .withColumn("_schema_version",
                                lit(self._schema_hash(df.schema)))
                )
            aligned_frames.append(aligned)

        # Step 4: Union by name
        result = aligned_frames[0]
        for frame in aligned_frames[1:]:
            result = result.unionByName(frame, allowMissingColumns=True)

        # Step 5: Evolve target table schema
        evolution_result = self.engine.detect_drift(
            result.schema, target_table, source="multi_source_merge"
        )
        if evolution_result.applied:
            self.engine.apply_safe_changes(evolution_result)
            logger.info(
                f"Applied {len(evolution_result.applied)} schema changes "
                f"to {target_table}"
            )
        if evolution_result.blocked:
            logger.error(
                f"BLOCKED {len(evolution_result.blocked)} breaking changes "
                f"for {target_table}: {evolution_result.blocked}"
            )

        return result

    def _compute_superset_schema(
        self, frames: Dict[str, DataFrame]
    ) -> StructType:
        """Build union of all schemas, resolving type conflicts via widening."""
        all_fields: Dict[str, StructField] = {}

        for source_name, df in frames.items():
            for field in df.schema.fields:
                if field.name not in all_fields:
                    all_fields[field.name] = field
                else:
                    # Resolve type conflict — pick wider type
                    existing = all_fields[field.name]
                    wider = self._wider_type(existing, field)
                    all_fields[field.name] = wider

        return StructType(list(all_fields.values()))

    def _align_to_superset(
        self, df: DataFrame, superset: StructType, source: str
    ) -> DataFrame:
        """Add missing columns as NULL, cast mismatched types."""
        current_cols = {f.name: f for f in df.schema.fields}

        for field in superset.fields:
            if field.name not in current_cols:
                # Add missing column as NULL with correct type
                df = df.withColumn(field.name, lit(None).cast(field.dataType))
            elif current_cols[field.name].dataType != field.dataType:
                # Cast to wider type
                df = df.withColumn(field.name, col(field.name).cast(field.dataType))

        return df

    def _wider_type(self, a: StructField, b: StructField) -> StructField:
        """Return the wider of two types. Falls back to STRING."""
        from pyspark.sql.types import (
            IntegerType, LongType, FloatType, DoubleType, StringType
        )
        type_order = [IntegerType, LongType, FloatType, DoubleType, StringType]

        a_idx = next(
            (i for i, t in enumerate(type_order) if isinstance(a.dataType, t)),
            len(type_order)
        )
        b_idx = next(
            (i for i, t in enumerate(type_order) if isinstance(b.dataType, t)),
            len(type_order)
        )

        wider_idx = max(a_idx, b_idx)
        if wider_idx >= len(type_order):
            # Fallback: stringify
            return StructField(a.name, StringType(), nullable=True)

        return StructField(
            a.name, type_order[wider_idx](), nullable=a.nullable or b.nullable
        )

    def _schema_hash(self, schema: StructType) -> str:
        """Deterministic hash of schema for version tracking."""
        import hashlib
        schema_json = schema.json()
        return hashlib.md5(schema_json.encode()).hexdigest()[:12]
```

### Kafka + Schema Registry Integration

```python
"""
kafka_schema_ingestion.py

Consumes from Kafka with Schema Registry, detecting schema changes
at ingestion time and routing to evolution engine.
"""

from confluent_kafka import DeserializingConsumer
from confluent_kafka.schema_registry import SchemaRegistryClient
from confluent_kafka.schema_registry.avro import AvroDeserializer
from pyspark.sql import SparkSession
from pyspark.sql.avro.functions import from_avro
from pyspark.sql.functions import col, expr
import logging

logger = logging.getLogger(__name__)


class SchemaAwareKafkaIngestion:
    """
    Reads from Kafka topics with embedded schema IDs.
    Detects when schema version changes and triggers evolution.
    """

    def __init__(self, spark: SparkSession, schema_registry_url: str):
        self.spark = spark
        self.sr_client = SchemaRegistryClient({"url": schema_registry_url})
        self._schema_cache: dict = {}  # subject → latest version seen

    def create_streaming_reader(
        self, topics: list, kafka_brokers: str
    ) -> "DataFrame":
        """
        Create Spark Structured Streaming reader from Kafka.
        Handles schema evolution via Schema Registry integration.
        """
        return (
            self.spark.readStream
            .format("kafka")
            .option("kafka.bootstrap.servers", kafka_brokers)
            .option("subscribe", ",".join(topics))
            .option("startingOffsets", "latest")
            .option("maxOffsetsPerTrigger", 100000)
            # Key configs for schema evolution:
            .option("failOnDataLoss", "false")  # Handle topic compaction
            .load()
        )

    def deserialize_with_evolution(
        self, raw_df, topic: str, target_table: str
    ):
        """
        Deserialize Avro messages using Schema Registry.
        Detects schema version bumps and triggers table evolution.
        """
        # Get latest schema from registry
        subject = f"{topic}-value"
        latest_schema = self.sr_client.get_latest_version(subject)
        schema_str = latest_schema.schema.schema_str

        # Check if schema version has changed since last seen
        cached_version = self._schema_cache.get(subject)
        if cached_version and cached_version != latest_schema.version:
            logger.warning(
                f"Schema version change detected for {subject}: "
                f"v{cached_version} → v{latest_schema.version}"
            )
            self._handle_schema_version_change(
                subject, cached_version, latest_schema.version, target_table
            )

        self._schema_cache[subject] = latest_schema.version

        # Deserialize with current schema
        deserialized = raw_df.select(
            from_avro(col("value"), schema_str).alias("data")
        ).select("data.*")

        return deserialized

    def _handle_schema_version_change(
        self, subject: str, old_version: int, new_version: int, table: str
    ):
        """
        When Schema Registry reports a new version, compare schemas
        and trigger Iceberg table evolution.
        """
        old_schema = self.sr_client.get_version(subject, old_version)
        new_schema = self.sr_client.get_version(subject, new_version)

        # Log the change
        logger.info(
            f"Schema evolution for {subject}: "
            f"v{old_version} → v{new_version}\n"
            f"Compatibility: {self.sr_client.get_compatibility(subject)}"
        )

        # The actual Iceberg evolution happens in the merge step
        # when detect_drift compares incoming DataFrame schema vs table schema


def build_spark_session_with_iceberg() -> SparkSession:
    """Configure Spark with Iceberg + AWS Glue + Schema Registry."""
    return (
        SparkSession.builder
        .appName("MultiSourceSchemaEvolution")
        .config("spark.sql.catalog.glue_catalog", "org.apache.iceberg.spark.SparkCatalog")
        .config("spark.sql.catalog.glue_catalog.catalog-impl",
                "org.apache.iceberg.aws.glue.GlueCatalog")
        .config("spark.sql.catalog.glue_catalog.warehouse",
                "s3://data-lakehouse-prod/warehouse/")
        .config("spark.sql.catalog.glue_catalog.io-impl",
                "org.apache.iceberg.aws.s3.S3FileIO")
        # Schema evolution configs
        .config("spark.sql.iceberg.handle-timestamp-without-timezone", "true")
        .config("spark.sql.sources.partitionOverwriteMode", "dynamic")
        # Merge-on-read for faster evolution
        .config("spark.sql.catalog.glue_catalog.write.merge-mode", "merge-on-read")
        .getOrCreate()
    )
```

### Automatic Schema Evolution Write Path

```python
"""
evolution_writer.py

Writes DataFrames to Iceberg tables with automatic schema evolution.
Handles merge-on-read, schema merging, and safe writes.
"""

from pyspark.sql import SparkSession, DataFrame
from pyspark.sql.functions import col, current_timestamp, lit
import logging

logger = logging.getLogger(__name__)


class EvolutionAwareWriter:
    """
    Writes to Iceberg with schema evolution enabled.
    Supports: append, overwrite, merge (upsert).
    """

    def __init__(self, spark: SparkSession, catalog: str = "glue_catalog"):
        self.spark = spark
        self.catalog = catalog

    def write_with_evolution(
        self,
        df: DataFrame,
        table: str,
        mode: str = "append",
        merge_key: list = None,
        partition_by: list = None
    ):
        """
        Write DataFrame to Iceberg table with automatic schema evolution.

        Key Iceberg properties used:
        - mergeSchema: automatically add new columns
        - unionByName: match columns by name, not position
        """
        full_table = f"{self.catalog}.{table}"

        if mode == "merge" and merge_key:
            self._merge_with_evolution(df, full_table, merge_key)
        else:
            self._append_with_evolution(df, full_table, partition_by)

    def _append_with_evolution(
        self, df: DataFrame, table: str, partition_by: list = None
    ):
        """Append with automatic schema merge."""
        writer = (
            df.writeTo(table)
            .option("merge-schema", "true")  # KEY: auto-evolve schema
            .option("check-nullability", "false")  # Allow new nullable cols
        )

        if partition_by:
            # Iceberg handles partition evolution transparently
            writer = writer.partitionedBy(*partition_by)

        try:
            writer.append()
            logger.info(f"Appended {df.count()} rows to {table} with schema merge")
        except Exception as e:
            if "cannot be cast to" in str(e) or "type mismatch" in str(e):
                logger.error(
                    f"Type mismatch writing to {table}. "
                    f"Attempting type promotion..."
                )
                self._handle_type_mismatch(df, table)
            else:
                raise

    def _merge_with_evolution(
        self, df: DataFrame, table: str, merge_key: list
    ):
        """
        MERGE INTO with schema evolution — new columns from source
        are automatically added to target.
        """
        # Register source as temp view
        df.createOrReplaceTempView("_merge_source")

        merge_condition = " AND ".join(
            [f"target.{k} = source.{k}" for k in merge_key]
        )

        # Build update set (all non-key columns)
        non_key_cols = [c for c in df.columns if c not in merge_key]
        update_set = ", ".join([f"target.{c} = source.{c}" for c in non_key_cols])
        insert_cols = ", ".join(df.columns)
        insert_vals = ", ".join([f"source.{c}" for c in df.columns])

        merge_sql = f"""
            MERGE INTO {table} AS target
            USING _merge_source AS source
            ON {merge_condition}
            WHEN MATCHED THEN UPDATE SET {update_set}
            WHEN NOT MATCHED THEN INSERT ({insert_cols}) VALUES ({insert_vals})
        """

        self.spark.sql(merge_sql)
        logger.info(f"Merged into {table} with key {merge_key}")

    def _handle_type_mismatch(self, df: DataFrame, table: str):
        """
        When a type mismatch occurs, attempt safe promotion on the table
        then retry the write.
        """
        table_schema = self.spark.table(table).schema
        df_schema = df.schema

        for df_field in df_schema.fields:
            table_field = next(
                (f for f in table_schema.fields if f.name == df_field.name),
                None
            )
            if table_field and table_field.dataType != df_field.dataType:
                # Attempt ALTER TABLE type promotion
                alter_sql = (
                    f"ALTER TABLE {table} "
                    f"ALTER COLUMN {df_field.name} TYPE {df_field.dataType.simpleString()}"
                )
                try:
                    self.spark.sql(alter_sql)
                    logger.info(f"Promoted type: {alter_sql}")
                except Exception as e:
                    logger.error(f"Cannot promote type for {df_field.name}: {e}")
                    raise

        # Retry write after promotion
        df.writeTo(table).option("merge-schema", "true").append()
```

---

## Real-World Scenarios

### Scenario 1: New Source Onboarding (Acquisition)

```sql
-- Company acquires "FastPay" — their customer table has different column names
-- FastPay schema:
--   fp_customer_id (INT), full_name (VARCHAR), mail (VARCHAR), 
--   signup_date (DATE), loyalty_tier (VARCHAR)

-- Our existing unified table:
--   customer_id (BIGINT), name (STRING), email (STRING), 
--   created_at (TIMESTAMP)

-- Step 1: Map FastPay columns to our schema (dbt model)
-- Step 2: Add new columns that don't exist in our table

ALTER TABLE glue_catalog.unified.customers ADD COLUMN loyalty_tier STRING;
-- Iceberg assigns new column ID (e.g., ID 7)
-- Old data has NULL for loyalty_tier — perfectly fine

-- Step 3: Type promotion for customer_id (INT → BIGINT already in place)
-- No action needed — our table already uses BIGINT

-- Step 4: Write FastPay data with schema merge
-- All old data retains its structure. New FastPay records have loyalty_tier filled.
```

### Scenario 2: Source Renames Column After API Update

```sql
-- Stripe API v2023-11 renames "charge_amount" to "payment_amount"
-- Old data in table uses column ID 5 named "charge_amount"

-- Rename in Iceberg (metadata-only, instant):
ALTER TABLE glue_catalog.unified.payments 
    RENAME COLUMN charge_amount TO payment_amount;

-- Column ID 5 still points to same physical data in all Parquet files
-- Old files written with "charge_amount" header → read via ID 5 → returned as "payment_amount"
-- Downstream consumers immediately see "payment_amount" with zero data movement
```

### Scenario 3: Handling NULL Safety Across Sources

```python
# Some sources send customer_id as required, others as optional.
# Iceberg handles this gracefully:

# Source A: customer_id is NOT NULL (always present)
# Source B: customer_id is nullable (sometimes missing for anonymous events)

# When merging:
# - Iceberg column becomes nullable (wider compatibility)
# - Validation layer flags unexpected NULLs from Source A (data quality issue)
# - No schema change needed — nullable is the safe default

# In practice, the Great Expectations check catches this:
expectation_suite = {
    "expectations": [
        {
            "expectation_type": "expect_column_values_to_not_be_null",
            "kwargs": {
                "column": "customer_id",
                "mostly": 0.999  # Allow 0.1% nulls (anonymous events)
            }
        }
    ]
}
```

---

## Table DDL: Evolution Over Time

```sql
-- ═══════════════════════════════════════════════════════════════════
-- TABLE EVOLUTION HISTORY: unified.customers
-- Shows how the table evolved over 18 months with 200+ sources
-- ═══════════════════════════════════════════════════════════════════

-- V1 (2024-01-15): Initial creation from core platform
CREATE TABLE glue_catalog.unified.customers (
    customer_id     BIGINT       COMMENT 'Unique customer identifier',  -- ID: 1
    name            STRING       COMMENT 'Customer display name',       -- ID: 2
    email           STRING       COMMENT 'Primary email',               -- ID: 3
    created_at      TIMESTAMP    COMMENT 'Account creation time'        -- ID: 4
) USING iceberg
PARTITIONED BY (days(created_at))
TBLPROPERTIES (
    'write.format.default' = 'parquet',
    'write.parquet.compression-codec' = 'zstd'
);

-- V2 (2024-02-03): Mobile app starts sending phone numbers
ALTER TABLE glue_catalog.unified.customers ADD COLUMN phone STRING;  -- ID: 5

-- V3 (2024-03-20): Acquired company "FastPay" has loyalty data
ALTER TABLE glue_catalog.unified.customers ADD COLUMNS (
    loyalty_tier    STRING,      -- ID: 6
    loyalty_points  INT          -- ID: 7
);

-- V4 (2024-04-10): GDPR requirement — track consent
ALTER TABLE glue_catalog.unified.customers ADD COLUMNS (
    consent_marketing   BOOLEAN,     -- ID: 8
    consent_analytics   BOOLEAN,     -- ID: 9
    consent_updated_at  TIMESTAMP    -- ID: 10
);

-- V5 (2024-05-22): Rename for clarity after naming standards review
ALTER TABLE glue_catalog.unified.customers RENAME COLUMN name TO display_name;
-- ID 2 unchanged, just name mapping updated

-- V6 (2024-07-15): Points system scales beyond INT range
ALTER TABLE glue_catalog.unified.customers ALTER COLUMN loyalty_points TYPE BIGINT;
-- ID 7 keeps its data, old INT values read as BIGINT at read-time

-- V7 (2024-08-30): Add structured address (nested type)
ALTER TABLE glue_catalog.unified.customers ADD COLUMN address STRUCT<
    street: STRING,
    city: STRING,
    state: STRING,
    zip: STRING,
    country: STRING
>;  -- ID: 11 (struct), IDs 12-16 (nested fields)

-- V8 (2024-10-05): IoT team adds device metadata
ALTER TABLE glue_catalog.unified.customers ADD COLUMN
    devices MAP<STRING, STRUCT<device_type: STRING, last_seen: TIMESTAMP>>;
-- ID: 17 (map), IDs 18-19 (key/value struct fields)

-- V9 (2024-11-20): Partition evolution — traffic grew 10x
ALTER TABLE glue_catalog.unified.customers ADD PARTITION FIELD bucket(16, customer_id);
-- New data uses bucket partitioning; old daily partitions still valid

-- V10 (2025-01-10): Drop deprecated column (consent moved to separate table)
ALTER TABLE glue_catalog.unified.customers DROP COLUMN consent_updated_at;
-- ID 10 retired. Never reused. Old files with this column → ignored on read.

-- Current schema has gone through 10 evolution steps
-- Zero data rewrites. Zero downtime. All historical data still accessible.
```

---

## Airflow Orchestration

```python
"""
dags/multi_source_schema_evolution_dag.py

Airflow DAG that orchestrates schema-evolving ingestion for 200+ sources.
Runs every 15 minutes. Handles drift detection, evolution, and alerts.
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.trigger_dagrun import TriggerDagRunOperator
from airflow.providers.amazon.aws.sensors.s3 import S3KeySensor
from airflow.utils.task_group import TaskGroup

default_args = {
    "owner": "data-platform",
    "depends_on_past": False,
    "email_on_failure": True,
    "email": ["data-platform-oncall@company.com"],
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}

# Source registry — in production this comes from a config service
SOURCE_GROUPS = {
    "microservices": {
        "topics": [f"svc-{i}-events" for i in range(80)],
        "compatibility": "BACKWARD",
        "auto_evolve": True,
    },
    "third_party": {
        "topics": ["stripe-events", "salesforce-cdc", "hubspot-webhooks"],
        "compatibility": "FORWARD",
        "auto_evolve": True,
    },
    "legacy_systems": {
        "topics": ["legacy-oracle-cdc", "legacy-db2-cdc", "fastpay-sync"],
        "compatibility": "FULL",
        "auto_evolve": False,  # Requires manual approval
    },
}


with DAG(
    dag_id="multi_source_schema_evolution",
    default_args=default_args,
    description="Ingest 200+ sources with automatic schema evolution",
    schedule_interval="*/15 * * * *",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    max_active_runs=1,
    tags=["schema-evolution", "lakehouse", "iceberg"],
) as dag:

    def detect_schema_drift(**context):
        """Check all sources for schema changes since last run."""
        from schema_evolution_engine import SchemaEvolutionEngine
        from kafka_schema_ingestion import build_spark_session_with_iceberg

        spark = build_spark_session_with_iceberg()
        engine = SchemaEvolutionEngine(spark)

        drift_report = {}
        for group, config in SOURCE_GROUPS.items():
            for topic in config["topics"]:
                # Compare Schema Registry version vs last processed
                result = engine.detect_drift_for_topic(topic)
                if result.changes:
                    drift_report[topic] = result

        context["ti"].xcom_push(key="drift_report", value=drift_report)
        return drift_report

    def apply_safe_evolutions(**context):
        """Apply all non-breaking schema changes automatically."""
        drift_report = context["ti"].xcom_pull(
            task_ids="detect_drift", key="drift_report"
        )
        if not drift_report:
            return "No schema changes detected"

        from schema_evolution_engine import SchemaEvolutionEngine
        from kafka_schema_ingestion import build_spark_session_with_iceberg

        spark = build_spark_session_with_iceberg()
        engine = SchemaEvolutionEngine(spark)

        applied = []
        blocked = []
        for topic, result in drift_report.items():
            if result.applied:
                ddl_list = engine.apply_safe_changes(result)
                applied.extend(ddl_list)
            if result.blocked:
                blocked.extend(result.blocked)

        if blocked:
            # Push to approval workflow
            context["ti"].xcom_push(key="blocked_changes", value=blocked)

        return f"Applied {len(applied)} changes, blocked {len(blocked)}"

    def ingest_with_merged_schema(**context):
        """Run the actual data ingestion with evolved schemas."""
        from kafka_schema_ingestion import (
            SchemaAwareKafkaIngestion, build_spark_session_with_iceberg
        )
        from union_by_name_merger import MultiSourceMerger
        from evolution_writer import EvolutionAwareWriter
        from schema_evolution_engine import SchemaEvolutionEngine

        spark = build_spark_session_with_iceberg()
        engine = SchemaEvolutionEngine(spark)
        merger = MultiSourceMerger(spark, engine)
        writer = EvolutionAwareWriter(spark)

        # Read from all sources, merge, write
        source_frames = {}
        for group, config in SOURCE_GROUPS.items():
            for topic in config["topics"]:
                df = spark.read.format("kafka").option(
                    "kafka.bootstrap.servers", "kafka-prod:9092"
                ).option("subscribe", topic).load()
                source_frames[topic] = df

        # Merge all sources
        unified = merger.merge_sources(source_frames, "unified.events")

        # Write with evolution
        writer.write_with_evolution(
            unified, "unified.events", mode="append"
        )

    def alert_on_breaking_changes(**context):
        """Send alerts for blocked breaking changes requiring approval."""
        blocked = context["ti"].xcom_pull(
            task_ids="apply_evolutions", key="blocked_changes"
        )
        if blocked:
            # Integration with PagerDuty/Slack
            from alerting import send_schema_alert
            send_schema_alert(
                channel="#data-platform-alerts",
                changes=blocked,
                severity="high"
            )

    # Task definitions
    detect_drift = PythonOperator(
        task_id="detect_drift",
        python_callable=detect_schema_drift,
    )

    apply_evolutions = PythonOperator(
        task_id="apply_evolutions",
        python_callable=apply_safe_evolutions,
    )

    ingest_data = PythonOperator(
        task_id="ingest_data",
        python_callable=ingest_with_merged_schema,
    )

    alert_breaking = PythonOperator(
        task_id="alert_breaking_changes",
        python_callable=alert_on_breaking_changes,
        trigger_rule="all_done",
    )

    # DAG flow
    detect_drift >> apply_evolutions >> ingest_data >> alert_breaking
```

---

## dbt Models for Schema-Evolved Tables

```sql
-- models/staging/stg_unified_customers.sql
-- dbt model that handles schema evolution gracefully

{{ config(
    materialized='incremental',
    unique_key='customer_id',
    incremental_strategy='merge',
    file_format='iceberg',
    on_schema_change='append_new_columns'  -- KEY: auto-handle new columns
) }}

WITH source AS (
    SELECT * FROM {{ source('lakehouse', 'raw_customers') }}
    {% if is_incremental() %}
    WHERE _ingested_at > (SELECT MAX(_ingested_at) FROM {{ this }})
    {% endif %}
),

-- Handle column renames from different sources
normalized AS (
    SELECT
        customer_id,
        -- Coalesce across naming variants from different sources
        COALESCE(display_name, full_name, name) AS customer_name,
        COALESCE(email, mail, email_address) AS email,
        COALESCE(phone, phone_number, mobile) AS phone,
        -- New columns appear as NULL until source starts sending
        loyalty_tier,
        loyalty_points,
        -- Nested struct access (safe with Iceberg evolution)
        address.street AS address_street,
        address.city AS address_city,
        address.country AS address_country,
        -- Metadata
        _source_system,
        _ingested_at,
        created_at
    FROM source
),

-- Deduplicate across sources (same customer from multiple systems)
deduplicated AS (
    SELECT *,
        ROW_NUMBER() OVER (
            PARTITION BY customer_id
            ORDER BY _ingested_at DESC
        ) AS _row_num
    FROM normalized
)

SELECT * EXCEPT(_row_num)
FROM deduplicated
WHERE _row_num = 1
```

```yaml
# models/staging/stg_unified_customers.yml
version: 2

models:
  - name: stg_unified_customers
    description: "Unified customer table with schema evolution from 200+ sources"
    config:
      on_schema_change: append_new_columns
    columns:
      - name: customer_id
        tests:
          - not_null
          - unique
      - name: customer_name
        tests:
          - not_null:
              config:
                severity: warn  # Some sources may not have name initially
      - name: email
        tests:
          - not_null:
              where: "_source_system NOT IN ('iot-fleet', 'anonymous-events')"
```

---

## Monitoring & Alerting

### Schema Drift Dashboard Metrics

```python
"""
monitoring/schema_drift_monitor.py

Continuous monitoring for schema drift across 200+ sources.
Publishes metrics to CloudWatch/Datadog.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List
import boto3


@dataclass
class SchemaMetrics:
    total_sources: int
    total_tables: int
    schema_versions_total: int
    changes_last_24h: int
    breaking_changes_pending: int
    avg_columns_per_table: float
    max_schema_version: int
    sources_with_drift: int


class SchemaDriftMonitor:
    """Monitors schema evolution metrics across the lakehouse."""

    def __init__(self, spark, catalog: str = "glue_catalog"):
        self.spark = spark
        self.catalog = catalog
        self.cloudwatch = boto3.client("cloudwatch")

    def collect_metrics(self) -> SchemaMetrics:
        """Collect current schema evolution metrics."""
        # Query schema audit log
        changes_24h = self.spark.sql("""
            SELECT COUNT(*) as cnt
            FROM glue_catalog.schema_audit.change_log
            WHERE change_time > current_timestamp() - INTERVAL 24 HOURS
        """).collect()[0]["cnt"]

        breaking = self.spark.sql("""
            SELECT COUNT(*) as cnt
            FROM glue_catalog.schema_audit.change_log
            WHERE severity = 'breaking'
              AND status = 'pending_approval'
        """).collect()[0]["cnt"]

        # Get table-level stats from Iceberg metadata
        table_stats = self.spark.sql("""
            SELECT
                COUNT(DISTINCT table_name) as tables,
                SUM(schema_version) as total_versions,
                MAX(schema_version) as max_version,
                AVG(column_count) as avg_columns
            FROM glue_catalog.schema_audit.table_registry
        """).collect()[0]

        return SchemaMetrics(
            total_sources=200,
            total_tables=table_stats["tables"],
            schema_versions_total=table_stats["total_versions"],
            changes_last_24h=changes_24h,
            breaking_changes_pending=breaking,
            avg_columns_per_table=table_stats["avg_columns"],
            max_schema_version=table_stats["max_version"],
            sources_with_drift=self._count_drifted_sources(),
        )

    def publish_metrics(self, metrics: SchemaMetrics):
        """Push metrics to CloudWatch for dashboarding."""
        namespace = "DataLakehouse/SchemaEvolution"
        self.cloudwatch.put_metric_data(
            Namespace=namespace,
            MetricData=[
                {
                    "MetricName": "SchemaChangesLast24h",
                    "Value": metrics.changes_last_24h,
                    "Unit": "Count",
                },
                {
                    "MetricName": "BreakingChangesPending",
                    "Value": metrics.breaking_changes_pending,
                    "Unit": "Count",
                },
                {
                    "MetricName": "SourcesWithDrift",
                    "Value": metrics.sources_with_drift,
                    "Unit": "Count",
                },
                {
                    "MetricName": "TotalSchemaVersions",
                    "Value": metrics.schema_versions_total,
                    "Unit": "Count",
                },
            ],
        )

    def check_alerts(self, metrics: SchemaMetrics) -> List[str]:
        """Generate alerts based on thresholds."""
        alerts = []

        if metrics.breaking_changes_pending > 0:
            alerts.append(
                f"CRITICAL: {metrics.breaking_changes_pending} breaking schema "
                f"changes awaiting approval"
            )

        if metrics.changes_last_24h > 50:
            alerts.append(
                f"WARNING: Unusually high schema churn — "
                f"{metrics.changes_last_24h} changes in 24h (normal: 12-15)"
            )

        if metrics.sources_with_drift > 20:
            alerts.append(
                f"WARNING: {metrics.sources_with_drift} sources have "
                f"unapplied schema drift"
            )

        return alerts

    def _count_drifted_sources(self) -> int:
        """Count sources whose latest schema differs from table schema."""
        return self.spark.sql("""
            SELECT COUNT(DISTINCT source_name)
            FROM glue_catalog.schema_audit.drift_tracking
            WHERE drift_detected = true
              AND resolved = false
        """).collect()[0][0]
```

### Type Conflict Detection

```python
"""
monitoring/type_conflict_detector.py

Detects when multiple sources send conflicting types for the same logical column.
E.g., Source A sends customer_id as INT, Source B sends it as STRING.
"""


class TypeConflictDetector:
    """
    Scans incoming data across sources to find type disagreements.
    Reports conflicts before they cause pipeline failures.
    """

    def __init__(self, spark):
        self.spark = spark

    def detect_conflicts(self, source_schemas: Dict[str, "StructType"]) -> List[dict]:
        """
        Given schemas from all sources, find columns where types disagree.
        """
        # Build column → {source: type} mapping
        column_types: Dict[str, Dict[str, str]] = {}

        for source, schema in source_schemas.items():
            for field in schema.fields:
                if field.name not in column_types:
                    column_types[field.name] = {}
                column_types[field.name][source] = str(field.dataType)

        # Find disagreements
        conflicts = []
        for col_name, type_map in column_types.items():
            unique_types = set(type_map.values())
            if len(unique_types) > 1:
                conflicts.append({
                    "column": col_name,
                    "types_found": dict(type_map),
                    "unique_types": list(unique_types),
                    "resolution": self._suggest_resolution(unique_types),
                })

        return conflicts

    def _suggest_resolution(self, types: set) -> str:
        """Suggest how to resolve a type conflict."""
        type_strs = {t.lower() for t in types}

        # int + long → promote to long
        if type_strs <= {"integertype()", "longtype()"}:
            return "SAFE: Promote all to BIGINT"

        # float + double → promote to double
        if type_strs <= {"floattype()", "doubletype()"}:
            return "SAFE: Promote all to DOUBLE"

        # numeric + string → investigate (likely source bug)
        if "stringtype()" in type_strs:
            return "WARNING: String mixed with numeric — investigate source encoding"

        return "BREAKING: Manual resolution required"
```

---

## Production Handling: Breaking Changes

### Rollback Procedures

```python
"""
rollback/schema_rollback.py

Rollback schema changes using Iceberg's snapshot-based time travel.
"""


class SchemaRollback:
    """
    Roll back schema changes using Iceberg metadata.
    Does NOT roll back data — only schema definition.
    """

    def __init__(self, spark, catalog="glue_catalog"):
        self.spark = spark
        self.catalog = catalog

    def list_schema_history(self, table: str) -> list:
        """List all schema versions for a table."""
        return self.spark.sql(f"""
            SELECT 
                s.schema_id,
                s.timestamp,
                s.columns
            FROM {self.catalog}.{table}.schemas s
            ORDER BY s.schema_id DESC
        """).collect()

    def rollback_to_schema_version(self, table: str, schema_id: int):
        """
        Roll back table schema to a previous version.
        
        WARNING: This is a metadata-only operation. Data written with newer
        schema columns will still exist in files but won't be queryable
        (columns appear as NULL or are hidden).
        """
        # Iceberg doesn't natively support schema rollback,
        # so we reconstruct the old schema and apply reverse operations.
        full_table = f"{self.catalog}.{table}"

        current_schemas = self.list_schema_history(table)
        target_schema = next(
            s for s in current_schemas if s["schema_id"] == schema_id
        )

        # Apply reverse DDL operations
        # This is a controlled operation requiring approval
        self.spark.sql(f"""
            CALL {self.catalog}.system.rollback_to_snapshot(
                table => '{table}',
                snapshot_id => (
                    SELECT snapshot_id 
                    FROM {full_table}.snapshots 
                    WHERE schema_id = {schema_id}
                    ORDER BY committed_at DESC LIMIT 1
                )
            )
        """)

    def create_savepoint(self, table: str, label: str):
        """Tag current schema state for easy rollback reference."""
        full_table = f"{self.catalog}.{table}"
        self.spark.sql(f"""
            ALTER TABLE {full_table} 
            SET TBLPROPERTIES ('schema.savepoint.{label}' = 
                (SELECT current_schema_id FROM {full_table}.metadata))
        """)
```

### Breaking vs Non-Breaking Change Classification

```python
"""
Schema change classification matrix used by the evolution engine.
"""

CHANGE_CLASSIFICATION = {
    # ─── NON-BREAKING (auto-apply) ──────────────────────────────
    "add_optional_column": {
        "severity": "safe",
        "action": "auto_apply",
        "description": "Adding a new nullable column",
        "iceberg_op": "ALTER TABLE ADD COLUMN",
    },
    "widen_int_to_long": {
        "severity": "safe",
        "action": "auto_apply",
        "description": "Promote INT to BIGINT",
        "iceberg_op": "ALTER TABLE ALTER COLUMN TYPE",
    },
    "widen_float_to_double": {
        "severity": "safe",
        "action": "auto_apply",
        "description": "Promote FLOAT to DOUBLE",
        "iceberg_op": "ALTER TABLE ALTER COLUMN TYPE",
    },
    "widen_decimal_precision": {
        "severity": "safe",
        "action": "auto_apply",
        "description": "Increase DECIMAL precision/scale",
        "iceberg_op": "ALTER TABLE ALTER COLUMN TYPE",
    },
    "add_nested_field": {
        "severity": "safe",
        "action": "auto_apply",
        "description": "Add field to existing STRUCT",
        "iceberg_op": "ALTER TABLE ADD COLUMN parent.new_field",
    },
    "reorder_columns": {
        "severity": "safe",
        "action": "auto_apply",
        "description": "Change column order (metadata only)",
        "iceberg_op": "ALTER TABLE ALTER COLUMN AFTER/FIRST",
    },

    # ─── WARNING (apply with notification) ──────────────────────
    "rename_column": {
        "severity": "warning",
        "action": "apply_with_alert",
        "description": "Rename column (consumers may reference old name)",
        "iceberg_op": "ALTER TABLE RENAME COLUMN",
    },
    "drop_column_unused": {
        "severity": "warning",
        "action": "apply_with_alert",
        "description": "Drop column with zero downstream references",
        "iceberg_op": "ALTER TABLE DROP COLUMN",
    },
    "make_required_optional": {
        "severity": "warning",
        "action": "apply_with_alert",
        "description": "Change NOT NULL to nullable",
        "iceberg_op": "ALTER TABLE ALTER COLUMN DROP NOT NULL",
    },

    # ─── BREAKING (requires approval) ───────────────────────────
    "narrow_type": {
        "severity": "breaking",
        "action": "block_require_approval",
        "description": "Narrow type (LONG→INT) — data loss risk",
        "iceberg_op": "NOT SUPPORTED — requires table rewrite",
    },
    "incompatible_type_change": {
        "severity": "breaking",
        "action": "block_require_approval",
        "description": "Incompatible type (STRING→INT) — parse failures",
        "iceberg_op": "NOT SUPPORTED",
    },
    "drop_column_with_consumers": {
        "severity": "breaking",
        "action": "block_require_approval",
        "description": "Drop column referenced by downstream queries/dashboards",
        "iceberg_op": "ALTER TABLE DROP COLUMN (after consumer migration)",
    },
    "make_optional_required": {
        "severity": "breaking",
        "action": "block_require_approval",
        "description": "Add NOT NULL to existing nullable column",
        "iceberg_op": "Requires backfill + constraint",
    },
}
```

---

## Great Expectations Validation

```python
"""
validation/schema_quality_checks.py

Great Expectations suite that validates schema evolution didn't corrupt data.
Runs after every evolution + write cycle.
"""

import great_expectations as gx


def build_schema_evolution_suite(table_name: str, expected_columns: list):
    """
    Build validation suite that adapts to schema evolution.
    Key: validates KNOWN columns strictly, tolerates NEW columns.
    """
    context = gx.get_context()

    suite = context.add_expectation_suite(
        expectation_suite_name=f"{table_name}_post_evolution"
    )

    # Core columns must always exist
    for col in expected_columns:
        suite.add_expectation(
            gx.expectations.ExpectColumnToExist(column=col)
        )

    # No unexpected type changes on core columns
    type_expectations = {
        "customer_id": "LongType",
        "email": "StringType",
        "created_at": "TimestampType",
    }
    for col, expected_type in type_expectations.items():
        suite.add_expectation(
            gx.expectations.ExpectColumnValuesToBeOfType(
                column=col, type_=expected_type
            )
        )

    # Row count should not drop drastically after evolution
    suite.add_expectation(
        gx.expectations.ExpectTableRowCountToBeBetween(
            min_value=1000,  # Minimum expected rows
        )
    )

    # NULL rates should not spike after schema change
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToNotBeNull(
            column="customer_id", mostly=0.9999
        )
    )

    return suite
```

---

## Scale Considerations

### Performance at 200+ Sources, 1000+ Tables

| Dimension | Number | Strategy |
|-----------|--------|----------|
| Sources | 200+ | Parallel ingestion via Airflow task groups |
| Tables | 1,000+ | Namespace isolation, concurrent catalog ops |
| Schema versions (total) | 50,000+ | Iceberg metadata compaction (expire old snapshots) |
| Daily schema changes | 12-15 | Auto-apply safe, queue breaking |
| Columns per table (max) | 500+ | Column pruning, projection pushdown |
| Partitions per table | 100K+ | Partition spec evolution, manifest list pruning |

### Metadata Management at Scale

```sql
-- Expire old snapshots to keep metadata lean (run daily)
CALL glue_catalog.system.expire_snapshots(
    table => 'unified.events',
    older_than => TIMESTAMP '2024-01-01 00:00:00',
    retain_last => 100
);

-- Rewrite manifests to optimize metadata reads
CALL glue_catalog.system.rewrite_manifests(
    table => 'unified.events'
);

-- Remove orphan files from failed evolution attempts
CALL glue_catalog.system.remove_orphan_files(
    table => 'unified.events',
    older_than => TIMESTAMP '2024-06-01 00:00:00'
);
```

### Catalog Operations Concurrency

```python
# Iceberg uses optimistic concurrency for schema evolution.
# Multiple sources can evolve the same table simultaneously.
# Conflicts are resolved via retry:

from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=1, max=30),
    reraise=True
)
def safe_schema_evolution(spark, table, ddl):
    """
    Apply DDL with retry on CommitFailedException.
    Iceberg's optimistic locking means concurrent ALTER TABLEs
    may conflict — retry resolves this safely.
    """
    try:
        spark.sql(ddl)
    except Exception as e:
        if "CommitFailedException" in str(e):
            # Another process modified the table — retry with fresh metadata
            spark.sql(f"REFRESH TABLE {table}")
            raise  # tenacity will retry
        raise
```

---

## Summary

Iceberg's schema evolution transforms the problem of multi-source data aggregation from a **constant firefight** (40+ hours/week of schema-related toil) into a **self-healing system** that:

1. **Absorbs new columns** automatically via column ID assignment
2. **Handles type growth** via safe read-time promotion
3. **Survives renames** because internal IDs never change
4. **Evolves partitions** without rewriting historical data
5. **Tracks full history** — any schema version queryable via time-travel
6. **Blocks unsafe changes** with classification + approval workflows

The result: **zero-downtime schema evolution** across 200+ sources with 12-15 daily changes, reducing engineering toil from 40+ hours/week to <2 hours/week (reviewing breaking change approvals only).
