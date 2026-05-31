# Generic Data Engineering Framework for Multiple Sources and Sinks

## Overview
A flexible, plugin-based framework for building data engineering jobs that can work with various sources (databases, message queues, files) and sinks (databases, data warehouses, object storage) with built-in support for transformations, CDC, and job orchestration.

---

## Architecture

### High-Level Design
```
┌─────────────────────────────────────────────────────────────────┐
│                     Job Orchestrator Layer                       │
│  (Scheduling, Monitoring, State Management, Error Handling)      │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Job Configuration Layer                      │
│        (YAML/JSON Config, Job Metadata, Pipeline Definition)     │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Core Framework Layer                        │
│                                                                  │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐       │
│  │   Source     │──▶│ Transform    │──▶│    Sink      │       │
│  │   Connector  │   │   Pipeline   │   │  Connector   │       │
│  └──────────────┘   └──────────────┘   └──────────────┘       │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Plugin Layer                                 │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Sources: PostgreSQL, MySQL, Kafka, S3, MongoDB, etc.     │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Transforms: CDC, Lookup, Filter, Aggregate, Enrich       │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Sinks: PostgreSQL, Redshift, S3, Kafka, Pinot, etc.      │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Core Components

### 1. **Job Configuration Schema**

```yaml
job:
  name: "cdc_transaction_pipeline"
  type: "stream"  # batch, stream, hybrid
  version: "1.0"
  schedule: "*/10 * * * *"  # Cron expression for batch jobs
  
  metadata:
    owner: "data-engineering-team"
    tags: ["AML", "UAT", "CDC"]
    description: "Process CDC events from transaction table"
    
  source:
    type: "postgresql"
    connection:
      serverName: "trm_server_db_pg"
      database: "trm_server_db"
      table: "dbo.trm_pine_pg_transaction_data"
      host: "192.168.100.203"
      port: 51593
      user: "${SVC_ACC_DMR}"
      password: "${B8E628FA-CDD3-442E-A18E-53E2E7956AEC}"
    
    mode: "cdc"  # full, incremental, cdc
    cdc_config:
      type: "debezium"
      capture_mode: "change_stream"
      start_position: "latest"
      
    extraction:
      batch_size: 1000
      parallel_tasks: 1
      watermark_column: "updated_at"
      
  transformations:
    - name: "lookup_issuer"
      type: "lookup"
      config:
        lookup_source:
          type: "postgresql"
          connection:
            serverName: "trm_server_db_pg"
            database: "trm_server_db"
            host: "192.168.100.203"
            port: 51593
          table: "trm_pine_pg_addon_issuer_id_master_tbl"
        lookup_key: "issuer_id"
        join_type: "left"  # left, inner, right
        cache_enabled: true
        cache_ttl: 3600
        sql: |
          SELECT issuer_name 
          FROM trm_pine_pg_addon_issuer_id_master_tbl (nolock) 
          WHERE issuer_id = ?
          
    - name: "lookup_acquirer"
      type: "lookup"
      config:
        lookup_source:
          type: "postgresql"
          connection:
            serverName: "trm_server_db_pg"
            database: "trm_server_db"
          table: "pine_pg_acquirer_master_tbl"
        lookup_key: "acquirer_id"
        sql: |
          SELECT acquirer_name, acquirer_code 
          FROM pine_pg_acquirer_master_tbl (nolock) 
          WHERE acquirer_id = ?
          
    - name: "enrich_transaction"
      type: "custom"
      class: "com.pinelabs.dmr.transformations.TransactionEnrichment"
      config:
        lookup_transform_value: true
        
    - name: "filter_invalid"
      type: "filter"
      config:
        condition: "status IS NOT NULL AND amount > 0"
        
  sink:
    type: "kafka"
    connection:
      bootstrap_servers: "kafka-broker:9092"
      topic: "transaction_events"
    
    format: "json"  # json, avro, parquet, csv
    mode: "append"  # append, overwrite, upsert
    
    error_handling:
      strategy: "retry"  # retry, skip, dlq
      max_retries: 3
      retry_backoff: "exponential"
      dlq_topic: "transaction_events_dlq"
      
    delivery_guarantee: "at_least_once"  # at_least_once, exactly_once
    
  monitoring:
    metrics:
      - "records_processed"
      - "processing_latency"
      - "error_rate"
    alerts:
      - condition: "error_rate > 5%"
        channel: "slack"
        recipients: ["#data-eng-alerts"]
        
  checkpointing:
    enabled: true
    storage: "s3"
    location: "s3://job-checkpoints/cdc_transaction_pipeline/"
    interval: "60s"
```

---

## Framework Components

### 2. **Source Connector Interface**

```python
from abc import ABC, abstractmethod
from typing import Iterator, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum

class SourceMode(Enum):
    FULL = "full"
    INCREMENTAL = "incremental"
    CDC = "cdc"
    STREAMING = "streaming"

@dataclass
class SourceConfig:
    connection: Dict[str, Any]
    mode: SourceMode
    batch_size: int = 1000
    parallel_tasks: int = 1
    watermark_column: Optional[str] = None
    checkpoint_location: Optional[str] = None

@dataclass
class DataRecord:
    data: Dict[str, Any]
    metadata: Dict[str, Any]
    timestamp: int
    operation: str  # INSERT, UPDATE, DELETE for CDC
    partition_key: Optional[str] = None

class SourceConnector(ABC):
    """Base class for all source connectors"""
    
    def __init__(self, config: SourceConfig):
        self.config = config
        self.checkpoint = None
        
    @abstractmethod
    def connect(self) -> None:
        """Establish connection to the source"""
        pass
    
    @abstractmethod
    def read(self) -> Iterator[DataRecord]:
        """Read data from source"""
        pass
    
    @abstractmethod
    def get_schema(self) -> Dict[str, Any]:
        """Get schema information"""
        pass
    
    @abstractmethod
    def close(self) -> None:
        """Close connection"""
        pass
    
    def save_checkpoint(self, checkpoint: Dict[str, Any]) -> None:
        """Save checkpoint for incremental processing"""
        self.checkpoint = checkpoint
        
    def load_checkpoint(self) -> Optional[Dict[str, Any]]:
        """Load last checkpoint"""
        return self.checkpoint
```

### 3. **Sink Connector Interface**

```python
from abc import ABC, abstractmethod
from typing import List, Dict, Any
from enum import Enum

class WriteMode(Enum):
    APPEND = "append"
    OVERWRITE = "overwrite"
    UPSERT = "upsert"

class DeliveryGuarantee(Enum):
    AT_MOST_ONCE = "at_most_once"
    AT_LEAST_ONCE = "at_least_once"
    EXACTLY_ONCE = "exactly_once"

@dataclass
class SinkConfig:
    connection: Dict[str, Any]
    format: str = "json"
    mode: WriteMode = WriteMode.APPEND
    batch_size: int = 1000
    delivery_guarantee: DeliveryGuarantee = DeliveryGuarantee.AT_LEAST_ONCE
    error_handling: Dict[str, Any] = None

class SinkConnector(ABC):
    """Base class for all sink connectors"""
    
    def __init__(self, config: SinkConfig):
        self.config = config
        
    @abstractmethod
    def connect(self) -> None:
        """Establish connection to the sink"""
        pass
    
    @abstractmethod
    def write(self, records: List[DataRecord]) -> None:
        """Write data to sink"""
        pass
    
    @abstractmethod
    def flush(self) -> None:
        """Flush pending writes"""
        pass
    
    @abstractmethod
    def close(self) -> None:
        """Close connection"""
        pass
    
    def handle_error(self, record: DataRecord, error: Exception) -> None:
        """Handle write errors based on configuration"""
        strategy = self.config.error_handling.get("strategy", "retry")
        if strategy == "dlq":
            self._write_to_dlq(record, error)
        elif strategy == "skip":
            self._log_error(record, error)
        elif strategy == "retry":
            self._retry_write(record)
```

### 4. **Transformation Pipeline Interface**

```python
from abc import ABC, abstractmethod
from typing import List, Optional

class Transformation(ABC):
    """Base class for all transformations"""
    
    def __init__(self, name: str, config: Dict[str, Any]):
        self.name = name
        self.config = config
        
    @abstractmethod
    def transform(self, record: DataRecord) -> Optional[DataRecord]:
        """Transform a single record. Return None to filter out"""
        pass
    
    def setup(self) -> None:
        """Setup resources (e.g., lookup cache)"""
        pass
    
    def cleanup(self) -> None:
        """Cleanup resources"""
        pass

class LookupTransformation(Transformation):
    """Enrichment via lookup in another data source"""
    
    def __init__(self, name: str, config: Dict[str, Any]):
        super().__init__(name, config)
        self.cache = {}
        self.lookup_source = None
        
    def setup(self) -> None:
        # Initialize lookup source connection
        source_config = self.config.get("lookup_source")
        self.lookup_source = create_source_connector(source_config)
        
        # Pre-load cache if enabled
        if self.config.get("cache_enabled", False):
            self._preload_cache()
    
    def transform(self, record: DataRecord) -> Optional[DataRecord]:
        lookup_key = self.config["lookup_key"]
        key_value = record.data.get(lookup_key)
        
        if key_value and key_value in self.cache:
            lookup_data = self.cache[key_value]
            record.data.update(lookup_data)
        elif key_value:
            # Fetch from source
            lookup_data = self._fetch_lookup(key_value)
            if lookup_data:
                record.data.update(lookup_data)
                if self.config.get("cache_enabled"):
                    self.cache[key_value] = lookup_data
        
        return record
    
    def _preload_cache(self) -> None:
        """Preload lookup cache"""
        for record in self.lookup_source.read():
            key = record.data[self.config["lookup_key"]]
            self.cache[key] = record.data

class FilterTransformation(Transformation):
    """Filter records based on condition"""
    
    def transform(self, record: DataRecord) -> Optional[DataRecord]:
        condition = self.config["condition"]
        if self._evaluate_condition(record.data, condition):
            return record
        return None
    
    def _evaluate_condition(self, data: Dict[str, Any], condition: str) -> bool:
        """Evaluate filter condition"""
        # Simple implementation - can be enhanced with expression parser
        try:
            return eval(condition, {"__builtins__": {}}, data)
        except Exception:
            return False

class TransformationPipeline:
    """Pipeline to execute multiple transformations"""
    
    def __init__(self, transformations: List[Transformation]):
        self.transformations = transformations
        
    def setup(self) -> None:
        for transform in self.transformations:
            transform.setup()
    
    def process(self, record: DataRecord) -> Optional[DataRecord]:
        """Process record through all transformations"""
        current_record = record
        
        for transform in self.transformations:
            if current_record is None:
                break
            current_record = transform.transform(current_record)
            
        return current_record
    
    def cleanup(self) -> None:
        for transform in self.transformations:
            transform.cleanup()
```

### 5. **Job Executor**

```python
import logging
from typing import Dict, Any
from dataclasses import dataclass
import time

@dataclass
class JobMetrics:
    records_read: int = 0
    records_written: int = 0
    records_filtered: int = 0
    errors: int = 0
    start_time: float = 0
    end_time: float = 0
    
    @property
    def duration(self) -> float:
        return self.end_time - self.start_time
    
    @property
    def throughput(self) -> float:
        if self.duration > 0:
            return self.records_written / self.duration
        return 0

class JobExecutor:
    """Main job executor that orchestrates source, transforms, and sink"""
    
    def __init__(self, job_config: Dict[str, Any]):
        self.config = job_config
        self.logger = logging.getLogger(f"job.{job_config['job']['name']}")
        self.metrics = JobMetrics()
        
        # Initialize components
        self.source = self._create_source()
        self.sink = self._create_sink()
        self.pipeline = self._create_pipeline()
        
    def _create_source(self) -> SourceConnector:
        """Create source connector from config"""
        source_config = self.config["job"]["source"]
        connector_type = source_config["type"]
        return SourceConnectorFactory.create(connector_type, source_config)
    
    def _create_sink(self) -> SinkConnector:
        """Create sink connector from config"""
        sink_config = self.config["job"]["sink"]
        connector_type = sink_config["type"]
        return SinkConnectorFactory.create(connector_type, sink_config)
    
    def _create_pipeline(self) -> TransformationPipeline:
        """Create transformation pipeline from config"""
        transform_configs = self.config["job"].get("transformations", [])
        transformations = []
        
        for t_config in transform_configs:
            transform = TransformationFactory.create(
                t_config["type"],
                t_config["name"],
                t_config.get("config", {})
            )
            transformations.append(transform)
        
        return TransformationPipeline(transformations)
    
    def execute(self) -> JobMetrics:
        """Execute the job"""
        self.logger.info(f"Starting job: {self.config['job']['name']}")
        self.metrics.start_time = time.time()
        
        try:
            # Setup
            self.source.connect()
            self.sink.connect()
            self.pipeline.setup()
            
            # Process data
            batch = []
            batch_size = self.source.config.batch_size
            
            for record in self.source.read():
                self.metrics.records_read += 1
                
                # Apply transformations
                transformed_record = self.pipeline.process(record)
                
                if transformed_record is None:
                    self.metrics.records_filtered += 1
                    continue
                
                batch.append(transformed_record)
                
                # Write batch
                if len(batch) >= batch_size:
                    self._write_batch(batch)
                    batch = []
            
            # Write remaining records
            if batch:
                self._write_batch(batch)
            
            # Flush
            self.sink.flush()
            
        except Exception as e:
            self.logger.error(f"Job failed: {str(e)}", exc_info=True)
            self.metrics.errors += 1
            raise
        
        finally:
            # Cleanup
            self.pipeline.cleanup()
            self.source.close()
            self.sink.close()
            
            self.metrics.end_time = time.time()
            self._log_metrics()
        
        return self.metrics
    
    def _write_batch(self, batch: List[DataRecord]) -> None:
        """Write a batch of records"""
        try:
            self.sink.write(batch)
            self.metrics.records_written += len(batch)
        except Exception as e:
            self.logger.error(f"Failed to write batch: {str(e)}")
            self.metrics.errors += len(batch)
            
            # Handle errors based on configuration
            for record in batch:
                self.sink.handle_error(record, e)
    
    def _log_metrics(self) -> None:
        """Log job metrics"""
        self.logger.info(f"""
Job Metrics:
  Records Read: {self.metrics.records_read}
  Records Written: {self.metrics.records_written}
  Records Filtered: {self.metrics.records_filtered}
  Errors: {self.metrics.errors}
  Duration: {self.metrics.duration:.2f}s
  Throughput: {self.metrics.throughput:.2f} records/sec
        """)
```

---

## Concrete Implementations

### 6. **PostgreSQL Source Connector**

```python
import psycopg2
from psycopg2.extras import RealDictCursor
from typing import Iterator

class PostgreSQLSourceConnector(SourceConnector):
    """PostgreSQL source connector with CDC support"""
    
    def __init__(self, config: SourceConfig):
        super().__init__(config)
        self.connection = None
        self.cursor = None
        
    def connect(self) -> None:
        conn_config = self.config.connection
        self.connection = psycopg2.connect(
            host=conn_config["host"],
            port=conn_config["port"],
            database=conn_config["database"],
            user=conn_config["user"],
            password=conn_config["password"]
        )
        self.cursor = self.connection.cursor(cursor_factory=RealDictCursor)
    
    def read(self) -> Iterator[DataRecord]:
        if self.config.mode == SourceMode.FULL:
            yield from self._read_full()
        elif self.config.mode == SourceMode.INCREMENTAL:
            yield from self._read_incremental()
        elif self.config.mode == SourceMode.CDC:
            yield from self._read_cdc()
    
    def _read_full(self) -> Iterator[DataRecord]:
        """Read full table"""
        table = self.config.connection["table"]
        query = f"SELECT * FROM {table}"
        
        self.cursor.execute(query)
        
        while True:
            rows = self.cursor.fetchmany(self.config.batch_size)
            if not rows:
                break
            
            for row in rows:
                yield DataRecord(
                    data=dict(row),
                    metadata={"source": "postgresql", "table": table},
                    timestamp=int(time.time() * 1000),
                    operation="INSERT"
                )
    
    def _read_incremental(self) -> Iterator[DataRecord]:
        """Read incremental data based on watermark"""
        table = self.config.connection["table"]
        watermark_col = self.config.watermark_column
        
        # Load last checkpoint
        checkpoint = self.load_checkpoint()
        last_value = checkpoint.get("last_watermark") if checkpoint else None
        
        if last_value:
            query = f"SELECT * FROM {table} WHERE {watermark_col} > %s ORDER BY {watermark_col}"
            self.cursor.execute(query, (last_value,))
        else:
            query = f"SELECT * FROM {table} ORDER BY {watermark_col}"
            self.cursor.execute(query)
        
        max_watermark = last_value
        
        while True:
            rows = self.cursor.fetchmany(self.config.batch_size)
            if not rows:
                break
            
            for row in rows:
                row_dict = dict(row)
                max_watermark = max(max_watermark or row_dict[watermark_col], 
                                   row_dict[watermark_col])
                
                yield DataRecord(
                    data=row_dict,
                    metadata={"source": "postgresql", "table": table},
                    timestamp=int(time.time() * 1000),
                    operation="INSERT"
                )
        
        # Save checkpoint
        if max_watermark:
            self.save_checkpoint({"last_watermark": max_watermark})
    
    def _read_cdc(self) -> Iterator[DataRecord]:
        """Read CDC changes using logical replication"""
        # This would use PostgreSQL logical replication or tools like Debezium
        # Simplified example
        raise NotImplementedError("CDC mode requires Debezium or similar CDC tool")
    
    def get_schema(self) -> Dict[str, Any]:
        table = self.config.connection["table"]
        query = f"""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = %s
        """
        self.cursor.execute(query, (table.split('.')[-1],))
        columns = self.cursor.fetchall()
        
        return {row["column_name"]: row["data_type"] for row in columns}
    
    def close(self) -> None:
        if self.cursor:
            self.cursor.close()
        if self.connection:
            self.connection.close()
```

### 7. **Kafka Sink Connector**

```python
from kafka import KafkaProducer
import json

class KafkaSinkConnector(SinkConnector):
    """Kafka sink connector"""
    
    def __init__(self, config: SinkConfig):
        super().__init__(config)
        self.producer = None
        self.dlq_producer = None
        
    def connect(self) -> None:
        conn_config = self.config.connection
        
        self.producer = KafkaProducer(
            bootstrap_servers=conn_config["bootstrap_servers"],
            value_serializer=lambda v: json.dumps(v).encode('utf-8'),
            acks='all' if self.config.delivery_guarantee == DeliveryGuarantee.EXACTLY_ONCE else 1,
            retries=3
        )
        
        # Setup DLQ if configured
        if self.config.error_handling and self.config.error_handling.get("dlq_topic"):
            self.dlq_producer = KafkaProducer(
                bootstrap_servers=conn_config["bootstrap_servers"],
                value_serializer=lambda v: json.dumps(v).encode('utf-8')
            )
    
    def write(self, records: List[DataRecord]) -> None:
        topic = self.config.connection["topic"]
        
        for record in records:
            try:
                self.producer.send(
                    topic,
                    value=record.data,
                    key=record.partition_key.encode('utf-8') if record.partition_key else None
                )
            except Exception as e:
                self.handle_error(record, e)
    
    def flush(self) -> None:
        if self.producer:
            self.producer.flush()
    
    def close(self) -> None:
        if self.producer:
            self.producer.close()
        if self.dlq_producer:
            self.dlq_producer.close()
    
    def _write_to_dlq(self, record: DataRecord, error: Exception) -> None:
        if self.dlq_producer:
            dlq_topic = self.config.error_handling["dlq_topic"]
            dlq_record = {
                "original_data": record.data,
                "error": str(error),
                "timestamp": time.time()
            }
            self.dlq_producer.send(dlq_topic, value=dlq_record)
```

---

## Factory Pattern for Connectors

### 8. **Connector Factories**

```python
class SourceConnectorFactory:
    """Factory for creating source connectors"""
    
    _connectors = {
        "postgresql": PostgreSQLSourceConnector,
        "mysql": MySQLSourceConnector,
        "kafka": KafkaSourceConnector,
        "s3": S3SourceConnector,
        "mongodb": MongoDBSourceConnector,
    }
    
    @classmethod
    def create(cls, connector_type: str, config: Dict[str, Any]) -> SourceConnector:
        connector_class = cls._connectors.get(connector_type)
        if not connector_class:
            raise ValueError(f"Unknown source connector type: {connector_type}")
        
        source_config = SourceConfig(
            connection=config["connection"],
            mode=SourceMode(config.get("mode", "full")),
            batch_size=config.get("extraction", {}).get("batch_size", 1000),
            parallel_tasks=config.get("extraction", {}).get("parallel_tasks", 1),
            watermark_column=config.get("extraction", {}).get("watermark_column")
        )
        
        return connector_class(source_config)
    
    @classmethod
    def register(cls, connector_type: str, connector_class: type) -> None:
        """Register a new connector type"""
        cls._connectors[connector_type] = connector_class

class SinkConnectorFactory:
    """Factory for creating sink connectors"""
    
    _connectors = {
        "postgresql": PostgreSQLSinkConnector,
        "kafka": KafkaSinkConnector,
        "s3": S3SinkConnector,
        "redshift": RedshiftSinkConnector,
        "pinot": PinotSinkConnector,
    }
    
    @classmethod
    def create(cls, connector_type: str, config: Dict[str, Any]) -> SinkConnector:
        connector_class = cls._connectors.get(connector_type)
        if not connector_class:
            raise ValueError(f"Unknown sink connector type: {connector_type}")
        
        sink_config = SinkConfig(
            connection=config["connection"],
            format=config.get("format", "json"),
            mode=WriteMode(config.get("mode", "append")),
            batch_size=config.get("batch_size", 1000),
            delivery_guarantee=DeliveryGuarantee(config.get("delivery_guarantee", "at_least_once")),
            error_handling=config.get("error_handling")
        )
        
        return connector_class(sink_config)

class TransformationFactory:
    """Factory for creating transformations"""
    
    _transformations = {
        "lookup": LookupTransformation,
        "filter": FilterTransformation,
        "custom": CustomTransformation,
    }
    
    @classmethod
    def create(cls, transform_type: str, name: str, config: Dict[str, Any]) -> Transformation:
        transform_class = cls._transformations.get(transform_type)
        if not transform_class:
            raise ValueError(f"Unknown transformation type: {transform_type}")
        
        return transform_class(name, config)
```

---

## Usage Examples

### 9. **Example 1: CDC Job from PostgreSQL to Kafka**

```python
# Load job configuration
with open("cdc_transaction_pipeline.yaml", "r") as f:
    job_config = yaml.safe_load(f)

# Create and execute job
executor = JobExecutor(job_config)
metrics = executor.execute()

print(f"Job completed. Processed {metrics.records_written} records in {metrics.duration}s")
```

### 10. **Example 2: Batch ETL from S3 to Redshift**

```yaml
job:
  name: "s3_to_redshift_etl"
  type: "batch"
  schedule: "0 2 * * *"  # Daily at 2 AM
  
  source:
    type: "s3"
    connection:
      bucket: "raw-data-bucket"
      prefix: "transactions/2024/"
      format: "parquet"
    mode: "full"
    
  transformations:
    - name: "deduplicate"
      type: "custom"
      class: "DeduplicateTransformation"
      config:
        key_columns: ["transaction_id"]
        
    - name: "validate_schema"
      type: "custom"
      class: "SchemaValidation"
      
  sink:
    type: "redshift"
    connection:
      host: "redshift-cluster.amazonaws.com"
      database: "analytics"
      table: "transactions"
      user: "${REDSHIFT_USER}"
      password: "${REDSHIFT_PASSWORD}"
    mode: "overwrite"
```

### 11. **Example 3: Real-time Streaming from Kafka to Pinot**

```yaml
job:
  name: "kafka_to_pinot_streaming"
  type: "stream"
  
  source:
    type: "kafka"
    connection:
      bootstrap_servers: "kafka:9092"
      topic: "click_events"
      group_id: "pinot_consumer"
    mode: "streaming"
    
  transformations:
    - name: "enrich_user_data"
      type: "lookup"
      config:
        lookup_source:
          type: "redis"
          connection:
            host: "redis-cache"
            port: 6379
        lookup_key: "user_id"
        cache_enabled: true
        
    - name: "aggregate_metrics"
      type: "aggregate"
      config:
        window: "60s"
        group_by: ["user_id", "event_type"]
        aggregations:
          - column: "value"
            function: "sum"
            
  sink:
    type: "pinot"
    connection:
      controller: "pinot-controller:9000"
      table: "click_events_realtime"
    mode: "append"
    delivery_guarantee: "at_least_once"
```

---

## Advanced Features

### 12. **Job Orchestration & Monitoring**

```python
class JobOrchestrator:
    """Orchestrator for managing multiple jobs"""
    
    def __init__(self):
        self.scheduler = BackgroundScheduler()
        self.jobs = {}
        
    def register_job(self, job_config: Dict[str, Any]) -> None:
        """Register a job with scheduler"""
        job_name = job_config["job"]["name"]
        schedule = job_config["job"].get("schedule")
        
        if schedule:
            # Batch job with schedule
            self.scheduler.add_job(
                func=self._execute_job,
                trigger=CronTrigger.from_crontab(schedule),
                args=[job_config],
                id=job_name
            )
        else:
            # Streaming job - start immediately
            self._execute_job(job_config)
        
        self.jobs[job_name] = job_config
    
    def _execute_job(self, job_config: Dict[str, Any]) -> None:
        """Execute a job"""
        job_name = job_config["job"]["name"]
        logger.info(f"Executing job: {job_name}")
        
        try:
            executor = JobExecutor(job_config)
            metrics = executor.execute()
            
            # Send metrics to monitoring system
            self._publish_metrics(job_name, metrics)
            
            # Check alerts
            self._check_alerts(job_config, metrics)
            
        except Exception as e:
            logger.error(f"Job {job_name} failed: {str(e)}")
            self._send_alert(job_name, str(e))
    
    def start(self) -> None:
        """Start the orchestrator"""
        self.scheduler.start()
    
    def stop(self) -> None:
        """Stop the orchestrator"""
        self.scheduler.shutdown()
```

### 13. **State Management & Checkpointing**

```python
class CheckpointManager:
    """Manage job state and checkpoints"""
    
    def __init__(self, storage_backend: str, location: str):
        self.storage = self._create_storage(storage_backend, location)
    
    def save_checkpoint(self, job_name: str, checkpoint: Dict[str, Any]) -> None:
        """Save checkpoint"""
        key = f"{job_name}/checkpoint.json"
        self.storage.write(key, json.dumps(checkpoint))
    
    def load_checkpoint(self, job_name: str) -> Optional[Dict[str, Any]]:
        """Load checkpoint"""
        key = f"{job_name}/checkpoint.json"
        data = self.storage.read(key)
        return json.loads(data) if data else None
    
    def _create_storage(self, backend: str, location: str):
        if backend == "s3":
            return S3Storage(location)
        elif backend == "local":
            return LocalStorage(location)
        else:
            raise ValueError(f"Unknown storage backend: {backend}")
```

---

## Best Practices

### 14. **Design Principles**

1. **Plugin Architecture**: Easy to add new sources, sinks, and transformations
2. **Configuration-Driven**: Define jobs via YAML/JSON without code changes
3. **Fault Tolerance**: Built-in retry mechanisms, checkpointing, and DLQ
4. **Scalability**: Support for parallel processing and partitioning
5. **Monitoring**: Comprehensive metrics and alerting
6. **Type Safety**: Use dataclasses and type hints
7. **Testability**: Mock-friendly interfaces for unit testing

### 15. **Performance Optimization**

- **Batch Processing**: Process records in batches to reduce overhead
- **Caching**: Cache lookup data to avoid repeated queries
- **Parallel Processing**: Use multiple workers for sources that support partitioning
- **Connection Pooling**: Reuse connections for better performance
- **Async I/O**: Use async operations for I/O-bound tasks

### 16. **Error Handling Strategy**

```python
class ErrorHandler:
    """Centralized error handling"""
    
    def __init__(self, config: Dict[str, Any]):
        self.strategy = config.get("strategy", "retry")
        self.max_retries = config.get("max_retries", 3)
        self.backoff = config.get("retry_backoff", "exponential")
        
    def handle(self, func, *args, **kwargs):
        """Execute function with error handling"""
        for attempt in range(self.max_retries):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if attempt == self.max_retries - 1:
                    if self.strategy == "dlq":
                        self._write_to_dlq(args, e)
                    raise
                
                # Calculate backoff
                wait_time = self._calculate_backoff(attempt)
                time.sleep(wait_time)
    
    def _calculate_backoff(self, attempt: int) -> float:
        if self.backoff == "exponential":
            return 2 ** attempt
        return 1.0
```

---

## Deployment

### 17. **Kubernetes Deployment**

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: data-pipeline-executor
spec:
  replicas: 3
  selector:
    matchLabels:
      app: data-pipeline
  template:
    metadata:
      labels:
        app: data-pipeline
    spec:
      containers:
      - name: pipeline
        image: data-pipeline:latest
        env:
        - name: CONFIG_PATH
          value: "/config/jobs"
        - name: CHECKPOINT_STORAGE
          value: "s3://pipeline-checkpoints/"
        volumeMounts:
        - name: job-configs
          mountPath: /config/jobs
      volumes:
      - name: job-configs
        configMap:
          name: pipeline-configs
```

---

## Conclusion

This generic framework provides:

✅ **Flexibility**: Support for multiple sources and sinks via plugins  
✅ **Extensibility**: Easy to add new connectors and transformations  
✅ **Reliability**: Built-in error handling, retries, and checkpointing  
✅ **Observability**: Comprehensive metrics and monitoring  
✅ **Scalability**: Support for batch and streaming workloads  
✅ **Maintainability**: Configuration-driven approach reduces code changes  

The framework can be extended with additional features like:
- Schema evolution and validation
- Data quality checks
- Advanced CDC support (Debezium integration)
- Multi-tenancy support
- Cost optimization and resource management
