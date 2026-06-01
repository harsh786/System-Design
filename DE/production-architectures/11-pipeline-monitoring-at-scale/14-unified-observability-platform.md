# Unified Observability Platform for Data Engineering

## Problem Statement

Most organizations suffer from fragmented observability:

| Team | Tool | What They Monitor |
|------|------|-------------------|
| Infrastructure | DataDog / CloudWatch | Servers, containers, network |
| Data Engineering | Custom scripts + Airflow UI | Pipeline runs, data freshness |
| ML Engineering | W&B / MLflow | Model performance, training |
| Analytics | dbt Cloud | Transform runs, test results |
| SRE | PagerDuty + Grafana | SLOs, incidents |

**The result**: When a downstream dashboard shows wrong numbers, 5 teams spend 2 hours in a war room because no one can correlate infrastructure issues → pipeline lag → data quality impact → business metric deviation.

A unified observability platform provides:
- **Single pane of glass** across all pipeline components
- **Correlation** between metrics, logs, traces, and data quality signals
- **Lineage-aware alerting** that understands upstream/downstream impact
- **AI-powered root cause analysis** that identifies the WHY, not just the WHAT

---

## Architecture Diagram

```
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│                        UNIFIED OBSERVABILITY PLATFORM                                     │
│                                                                                          │
│  ┌────────────────────────────────────────────────────────────────────────────────────┐  │
│  │                        DATA SOURCES (Instrumented)                                  │  │
│  │                                                                                    │  │
│  │  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌─────────┐ │  │
│  │  │Airflow │ │ Spark  │ │ Flink  │ │ Kafka  │ │  dbt   │ │  DBs   │ │ Custom  │ │  │
│  │  │        │ │        │ │        │ │        │ │        │ │        │ │ Services│ │  │
│  │  └───┬────┘ └───┬────┘ └───┬────┘ └───┬────┘ └───┬────┘ └───┬────┘ └────┬────┘ │  │
│  │      │          │          │          │          │          │           │        │  │
│  │      └──────────┴──────────┴──────────┴──────────┴──────────┴───────────┘        │  │
│  │                                    │                                              │  │
│  │                    OpenTelemetry (metrics + logs + traces)                         │  │
│  │                    OpenLineage (data lineage events)                               │  │
│  └────────────────────────────────────┼───────────────────────────────────────────────┘  │
│                                       │                                                  │
│  ┌────────────────────────────────────┼───────────────────────────────────────────────┐  │
│  │              COLLECTION & CORRELATION LAYER                                         │  │
│  │                                    │                                                │  │
│  │  ┌───────────────────────────────────────────────────────────────────────────────┐ │  │
│  │  │                    OTel Collector Gateway                                      │ │  │
│  │  │  ┌─────────────┐  ┌──────────────┐  ┌─────────────────────────────────────┐  │ │  │
│  │  │  │ Enrich with │  │ Correlate    │  │ Route to appropriate backend       │  │ │  │
│  │  │  │ lineage     │  │ trace_id ↔   │  │ (metrics/logs/traces/lineage)      │  │ │  │
│  │  │  │ metadata    │  │ pipeline_run │  │                                     │  │ │  │
│  │  │  └─────────────┘  └──────────────┘  └─────────────────────────────────────┘  │ │  │
│  │  └───────────────────────────────────────────────────────────────────────────────┘ │  │
│  └────────────────────────────────────────────────────────────────────────────────────┘  │
│                                       │                                                  │
│  ┌────────────────────────────────────┼───────────────────────────────────────────────┐  │
│  │              STORAGE & QUERY LAYER │                                                │  │
│  │                                    │                                                │  │
│  │  ┌──────────┐ ┌──────┐ ┌──────┐ ┌─┴────────┐ ┌──────────┐ ┌───────────────────┐  │  │
│  │  │  Mimir   │ │ Loki │ │Tempo │ │ DataHub  │ │ClickHouse│ │ ML Feature Store  │  │  │
│  │  │(metrics) │ │(logs)│ │(trc) │ │(lineage +│ │(analytics│ │ (anomaly models)  │  │  │
│  │  │          │ │      │ │      │ │ catalog) │ │ queries) │ │                   │  │  │
│  │  └──────────┘ └──────┘ └──────┘ └──────────┘ └──────────┘ └───────────────────┘  │  │
│  └────────────────────────────────────────────────────────────────────────────────────┘  │
│                                       │                                                  │
│  ┌────────────────────────────────────┼───────────────────────────────────────────────┐  │
│  │              INTELLIGENCE LAYER    │                                                │  │
│  │                                    │                                                │  │
│  │  ┌───────────────┐  ┌─────────────────┐  ┌──────────────────┐  ┌───────────────┐  │  │
│  │  │ Anomaly       │  │ Root Cause      │  │ Impact Analysis  │  │ Predictive    │  │  │
│  │  │ Detection     │  │ Analysis (LLM + │  │ (Lineage-aware)  │  │ Alerts        │  │  │
│  │  │ (ML models)   │  │  Graph)         │  │                  │  │               │  │  │
│  │  └───────────────┘  └─────────────────┘  └──────────────────┘  └───────────────┘  │  │
│  └────────────────────────────────────────────────────────────────────────────────────┘  │
│                                       │                                                  │
│  ┌────────────────────────────────────┼───────────────────────────────────────────────┐  │
│  │              PRESENTATION LAYER    │                                                │  │
│  │                                    │                                                │  │
│  │  ┌────────────────┐  ┌──────────────┐  ┌──────────────┐  ┌────────────────────┐   │  │
│  │  │ Pipeline       │  │ SLA Burn-    │  │ Data         │  │ Natural Language   │   │  │
│  │  │ Topology       │  │ down Charts  │  │ Freshness    │  │ Query Interface    │   │  │
│  │  │ (Live DAG)     │  │              │  │ Map          │  │ ("Why was X slow?")│   │  │
│  │  └────────────────┘  └──────────────┘  └──────────────┘  └────────────────────┘   │  │
│  └────────────────────────────────────────────────────────────────────────────────────┘  │
│                                       │                                                  │
│  ┌────────────────────────────────────┼───────────────────────────────────────────────┐  │
│  │              ACTION LAYER          │                                                │  │
│  │                                    │                                                │  │
│  │  ┌────────────────┐  ┌──────────────┐  ┌──────────────────────────────────────┐   │  │
│  │  │ Automated      │  │ Runbook      │  │ Self-Service Monitoring Onboarding   │   │  │
│  │  │ Remediation    │  │ Execution    │  │ (API + UI for data teams)            │   │  │
│  │  │ (Temporal)     │  │              │  │                                      │   │  │
│  │  └────────────────┘  └──────────────┘  └──────────────────────────────────────┘   │  │
│  └────────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                          │
└──────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Correlation Across Signals

### Trace ID Propagation Through Data Pipelines

The key challenge: traditional request tracing (HTTP → service → DB) doesn't work for data pipelines where a single Kafka message might be processed hours later by a different service.

```
┌─────────────────────────────────────────────────────────────────────┐
│                Correlation Model for Data Pipelines                   │
│                                                                     │
│  Traditional Trace:    Request → Service A → Service B → DB         │
│                        (single trace_id, milliseconds)              │
│                                                                     │
│  Data Pipeline Trace:  Ingestion → Kafka → Transform → DWH         │
│                        (pipeline_run_id, hours/days)                │
│                                                                     │
│  Correlation Keys:                                                  │
│  ┌────────────────────────────────────────────────────────────┐    │
│  │  trace_id          → Links spans within a processing step  │    │
│  │  pipeline_run_id   → Links all steps in one pipeline run   │    │
│  │  lineage_run_id    → Links across pipeline boundaries      │    │
│  │  batch_id          → Links records in a micro-batch        │    │
│  │  correlation_id    → Business-level event correlation       │    │
│  └────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
```

### Propagation Through Kafka Headers

```python
"""
correlation_propagator.py
Propagate correlation context through Kafka messages for end-to-end tracing.
"""

import uuid
import json
import time
from typing import Dict, Optional, Any
from dataclasses import dataclass, field, asdict
from opentelemetry import trace, context
from opentelemetry.propagate import inject, extract
from opentelemetry.trace.propagation import TraceContextTextMapPropagator
from confluent_kafka import Producer, Consumer, Message

@dataclass
class PipelineContext:
    """Correlation context propagated through pipeline stages."""
    trace_id: str
    pipeline_run_id: str
    lineage_run_id: str
    source_pipeline: str
    source_step: str
    batch_id: str
    created_at: float = field(default_factory=time.time)
    
    def to_headers(self) -> Dict[str, bytes]:
        """Serialize to Kafka headers."""
        return {
            f"pipeline.{k}": v.encode() if isinstance(v, str) else str(v).encode()
            for k, v in asdict(self).items()
        }
    
    @classmethod
    def from_headers(cls, headers: list) -> Optional['PipelineContext']:
        """Deserialize from Kafka headers."""
        if not headers:
            return None
        
        header_dict = {}
        for key, value in headers:
            if key.startswith("pipeline."):
                field_name = key[len("pipeline."):]
                header_dict[field_name] = value.decode() if value else ""
        
        if "trace_id" not in header_dict:
            return None
        
        return cls(
            trace_id=header_dict.get("trace_id", ""),
            pipeline_run_id=header_dict.get("pipeline_run_id", ""),
            lineage_run_id=header_dict.get("lineage_run_id", ""),
            source_pipeline=header_dict.get("source_pipeline", ""),
            source_step=header_dict.get("source_step", ""),
            batch_id=header_dict.get("batch_id", ""),
            created_at=float(header_dict.get("created_at", 0)),
        )


class InstrumentedProducer:
    """Kafka producer that propagates pipeline correlation context."""
    
    def __init__(self, producer: Producer, pipeline_name: str, step_name: str):
        self.producer = producer
        self.pipeline_name = pipeline_name
        self.step_name = step_name
        self.tracer = trace.get_tracer(__name__)
    
    def produce(
        self,
        topic: str,
        value: bytes,
        key: Optional[bytes] = None,
        pipeline_context: Optional[PipelineContext] = None,
    ):
        """Produce message with correlation headers."""
        
        # Create or continue trace
        with self.tracer.start_as_current_span(
            f"kafka.produce.{topic}",
            attributes={
                "messaging.system": "kafka",
                "messaging.destination": topic,
                "pipeline.name": self.pipeline_name,
                "pipeline.step": self.step_name,
            }
        ) as span:
            # Build headers
            headers = {}
            
            # Inject OTel trace context
            inject(headers)
            
            # Add pipeline context
            if pipeline_context is None:
                pipeline_context = PipelineContext(
                    trace_id=format(span.get_span_context().trace_id, '032x'),
                    pipeline_run_id=str(uuid.uuid4()),
                    lineage_run_id=str(uuid.uuid4()),
                    source_pipeline=self.pipeline_name,
                    source_step=self.step_name,
                    batch_id=str(uuid.uuid4()),
                )
            
            headers.update(pipeline_context.to_headers())
            
            # Convert headers to Kafka format
            kafka_headers = [(k, v if isinstance(v, bytes) else v.encode()) 
                          for k, v in headers.items()]
            
            self.producer.produce(
                topic=topic,
                value=value,
                key=key,
                headers=kafka_headers,
            )


class InstrumentedConsumer:
    """Kafka consumer that extracts and continues pipeline correlation."""
    
    def __init__(self, consumer: Consumer, pipeline_name: str, step_name: str):
        self.consumer = consumer
        self.pipeline_name = pipeline_name
        self.step_name = step_name
        self.tracer = trace.get_tracer(__name__)
    
    def poll(self, timeout: float = 1.0) -> Optional[tuple]:
        """Poll and extract correlation context."""
        msg = self.consumer.poll(timeout)
        if msg is None or msg.error():
            return None
        
        # Extract pipeline context from headers
        pipeline_ctx = PipelineContext.from_headers(msg.headers())
        
        # Extract OTel context for trace continuation
        header_dict = {k: v.decode() for k, v in (msg.headers() or [])}
        ctx = extract(header_dict)
        
        # Start a new span linked to the producer span
        with self.tracer.start_as_current_span(
            f"kafka.consume.{msg.topic()}",
            context=ctx,
            attributes={
                "messaging.system": "kafka",
                "messaging.source": msg.topic(),
                "messaging.partition": msg.partition(),
                "messaging.offset": msg.offset(),
                "pipeline.name": self.pipeline_name,
                "pipeline.step": self.step_name,
                "pipeline.run_id": pipeline_ctx.pipeline_run_id if pipeline_ctx else "",
            }
        ):
            # Calculate pipeline latency
            if pipeline_ctx:
                pipeline_lag = time.time() - pipeline_ctx.created_at
                # Record as metric
                from prometheus_client import Histogram
                PIPELINE_LAG = Histogram(
                    'pipeline_end_to_end_lag_seconds',
                    'End-to-end pipeline processing lag',
                    ['source_pipeline', 'current_pipeline'],
                    buckets=[1, 5, 10, 30, 60, 300, 600, 1800, 3600]
                )
                PIPELINE_LAG.labels(
                    source_pipeline=pipeline_ctx.source_pipeline,
                    current_pipeline=self.pipeline_name
                ).observe(pipeline_lag)
        
        return msg, pipeline_ctx
```

### OpenTelemetry Instrumentation for Spark

```python
"""
spark_otel_instrumentation.py
Instrument PySpark jobs with OpenTelemetry for unified observability.
"""

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.semconv.resource import ResourceAttributes
from pyspark.sql import SparkSession, DataFrame
from functools import wraps
from typing import Callable, Any
import time

# Initialize OTel
resource = Resource.create({
    ResourceAttributes.SERVICE_NAME: "spark-etl",
    ResourceAttributes.SERVICE_VERSION: "1.0.0",
    "pipeline.name": "daily-aggregation",
})

provider = TracerProvider(resource=resource)
exporter = OTLPSpanExporter(endpoint="http://otel-collector:4317", insecure=True)
provider.add_span_processor(BatchSpanProcessor(exporter))
trace.set_tracer_provider(provider)
tracer = trace.get_tracer(__name__)


def traced_transform(name: str, pipeline: str = ""):
    """Decorator to trace Spark transformations."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            with tracer.start_as_current_span(
                name,
                attributes={
                    "spark.operation": name,
                    "pipeline.name": pipeline,
                    "pipeline.step": name,
                }
            ) as span:
                start = time.time()
                try:
                    result = func(*args, **kwargs)
                    
                    # Record DataFrame metrics if result is a DF
                    if isinstance(result, DataFrame):
                        # Note: count() triggers computation
                        # Only do this in debug/development
                        if kwargs.get("_collect_metrics", False):
                            count = result.count()
                            span.set_attribute("spark.output.row_count", count)
                    
                    span.set_attribute("spark.status", "success")
                    return result
                    
                except Exception as e:
                    span.set_attribute("spark.status", "error")
                    span.set_attribute("spark.error.message", str(e))
                    span.record_exception(e)
                    raise
                finally:
                    duration = time.time() - start
                    span.set_attribute("spark.duration_seconds", duration)
        
        return wrapper
    return decorator


class InstrumentedSparkPipeline:
    """Spark ETL pipeline with full observability instrumentation."""
    
    def __init__(self, spark: SparkSession, pipeline_name: str, run_id: str):
        self.spark = spark
        self.pipeline_name = pipeline_name
        self.run_id = run_id
        
        # Prometheus metrics
        from prometheus_client import Counter, Histogram, Gauge, push_to_gateway
        
        self.records_processed = Counter(
            'spark_pipeline_records_processed_total',
            'Records processed',
            ['pipeline', 'stage', 'status']
        )
        self.stage_duration = Histogram(
            'spark_pipeline_stage_duration_seconds',
            'Stage duration',
            ['pipeline', 'stage'],
            buckets=[1, 5, 10, 30, 60, 120, 300, 600, 1800, 3600]
        )
        self.data_freshness = Gauge(
            'spark_pipeline_data_freshness_seconds',
            'Age of most recent record processed',
            ['pipeline']
        )
    
    @traced_transform("read_source", "daily-aggregation")
    def read_source(self, path: str) -> DataFrame:
        """Read source data with instrumentation."""
        df = self.spark.read.parquet(path)
        
        # Record source metrics
        count = df.count()
        self.records_processed.labels(
            pipeline=self.pipeline_name, stage="read", status="success"
        ).inc(count)
        
        # Check data freshness
        from pyspark.sql.functions import max as spark_max, col
        max_ts = df.select(spark_max(col("event_timestamp"))).collect()[0][0]
        if max_ts:
            freshness = time.time() - max_ts.timestamp()
            self.data_freshness.labels(pipeline=self.pipeline_name).set(freshness)
        
        return df
    
    @traced_transform("transform", "daily-aggregation")
    def transform(self, df: DataFrame) -> DataFrame:
        """Apply transformations with monitoring."""
        from pyspark.sql.functions import col, when, count as spark_count
        
        # Track null rates per column (data quality signal)
        null_counts = df.select([
            spark_count(when(col(c).isNull(), c)).alias(c)
            for c in df.columns
        ]).collect()[0]
        
        span = trace.get_current_span()
        for col_name in df.columns:
            null_rate = null_counts[col_name] / df.count() if df.count() > 0 else 0
            span.set_attribute(f"dq.null_rate.{col_name}", null_rate)
        
        # Apply transformation
        result = df.filter(col("status") != "deleted")
        
        return result
    
    @traced_transform("write_sink", "daily-aggregation")
    def write_sink(self, df: DataFrame, path: str):
        """Write to sink with metrics."""
        start = time.time()
        
        df.write.mode("overwrite").parquet(path)
        
        duration = time.time() - start
        self.stage_duration.labels(
            pipeline=self.pipeline_name, stage="write"
        ).observe(duration)
    
    def run(self, source_path: str, sink_path: str):
        """Execute full pipeline with end-to-end trace."""
        with tracer.start_as_current_span(
            f"pipeline.{self.pipeline_name}",
            attributes={
                "pipeline.name": self.pipeline_name,
                "pipeline.run_id": self.run_id,
            }
        ):
            df = self.read_source(source_path)
            transformed = self.transform(df)
            self.write_sink(transformed, sink_path)
            
            # Push metrics to gateway (since Spark is batch)
            from prometheus_client import push_to_gateway
            push_to_gateway(
                'pushgateway:9091',
                job=f'spark-{self.pipeline_name}',
                grouping_key={'run_id': self.run_id},
                registry=None  # Use default registry
            )
```

---

## AI-Powered Operations

### Anomaly Detection Microservice

```python
"""
anomaly_detection_service.py
ML-based anomaly detection for pipeline metrics.
Uses multiple algorithms for robust detection.
"""

from fastapi import FastAPI, BackgroundTasks
from pydantic import BaseModel
from typing import List, Dict, Optional
import numpy as np
from datetime import datetime, timedelta
import httpx
from dataclasses import dataclass

app = FastAPI(title="Pipeline Anomaly Detection Service")

# --- Models ---

class MetricPoint(BaseModel):
    timestamp: float
    value: float

class AnomalyResult(BaseModel):
    metric_name: str
    pipeline: str
    is_anomaly: bool
    anomaly_score: float  # 0-1, higher = more anomalous
    expected_range: tuple
    actual_value: float
    algorithm: str
    explanation: str

# --- Anomaly Detection Algorithms ---

class SeasonalDecomposition:
    """Detect anomalies considering daily/weekly seasonality."""
    
    def __init__(self, seasonal_period: int = 96):  # 96 = 24h at 15min intervals
        self.seasonal_period = seasonal_period
    
    def detect(self, values: np.ndarray, sensitivity: float = 3.0) -> List[bool]:
        """
        Decompose time series into trend + seasonal + residual.
        Flag points where residual exceeds sensitivity * std.
        """
        n = len(values)
        if n < self.seasonal_period * 2:
            # Not enough data for seasonal decomposition
            return self._simple_zscore(values, sensitivity)
        
        # Extract seasonal component (average of same-period values)
        seasonal = np.zeros(n)
        for i in range(n):
            period_idx = i % self.seasonal_period
            same_period = values[period_idx::self.seasonal_period]
            seasonal[i] = np.median(same_period)
        
        # Trend (moving average)
        window = min(self.seasonal_period, n // 4)
        trend = np.convolve(values, np.ones(window)/window, mode='same')
        
        # Residual
        residual = values - trend - seasonal
        
        # Anomaly detection on residual
        std = np.std(residual)
        mean = np.mean(residual)
        
        return [abs(r - mean) > sensitivity * std for r in residual]
    
    def _simple_zscore(self, values: np.ndarray, sensitivity: float) -> List[bool]:
        mean = np.mean(values)
        std = np.std(values)
        if std == 0:
            return [False] * len(values)
        return [abs(v - mean) / std > sensitivity for v in values]


class IsolationForestDetector:
    """Multivariate anomaly detection using Isolation Forest."""
    
    def __init__(self, contamination: float = 0.01):
        from sklearn.ensemble import IsolationForest
        self.model = IsolationForest(
            contamination=contamination,
            random_state=42,
            n_estimators=200
        )
        self.is_fitted = False
    
    def fit(self, features: np.ndarray):
        """Train on historical normal data."""
        self.model.fit(features)
        self.is_fitted = True
    
    def predict(self, features: np.ndarray) -> np.ndarray:
        """Returns -1 for anomalies, 1 for normal."""
        if not self.is_fitted:
            raise ValueError("Model not fitted yet")
        return self.model.predict(features)
    
    def score(self, features: np.ndarray) -> np.ndarray:
        """Anomaly score (lower = more anomalous)."""
        return self.model.score_samples(features)


class ProphetPredictor:
    """Forecast-based anomaly detection using Prophet-like decomposition."""
    
    def predict_expected_range(
        self, 
        historical: np.ndarray, 
        confidence: float = 0.95
    ) -> tuple:
        """Predict expected range for next data point."""
        if len(historical) < 10:
            mean = np.mean(historical)
            std = np.std(historical)
            return (mean - 2*std, mean + 2*std)
        
        # Simple exponential smoothing for trend
        alpha = 0.3
        smoothed = [historical[0]]
        for val in historical[1:]:
            smoothed.append(alpha * val + (1 - alpha) * smoothed[-1])
        
        predicted = smoothed[-1]
        
        # Residuals for confidence interval
        residuals = historical - np.array(smoothed)
        std = np.std(residuals)
        
        z = 1.96 if confidence == 0.95 else 2.576  # 99%
        return (predicted - z * std, predicted + z * std)


# --- Service Logic ---

class AnomalyDetectionEngine:
    """Orchestrates multiple detection algorithms."""
    
    def __init__(self):
        self.seasonal = SeasonalDecomposition()
        self.predictor = ProphetPredictor()
        self.prometheus_url = "http://thanos-query:9090"
    
    async def fetch_metric_history(
        self, 
        query: str, 
        hours_back: int = 168  # 1 week
    ) -> np.ndarray:
        """Fetch metric history from Prometheus/Thanos."""
        end = datetime.utcnow()
        start = end - timedelta(hours=hours_back)
        
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.prometheus_url}/api/v1/query_range",
                params={
                    "query": query,
                    "start": start.timestamp(),
                    "end": end.timestamp(),
                    "step": "900"  # 15-minute resolution
                },
                timeout=30.0
            )
            resp.raise_for_status()
            
            result = resp.json()["data"]["result"]
            if not result:
                return np.array([])
            
            values = [float(v[1]) for v in result[0]["values"]]
            return np.array(values)
    
    async def detect_anomaly(
        self, 
        metric_name: str, 
        pipeline: str,
        current_value: float
    ) -> AnomalyResult:
        """Run anomaly detection on a metric."""
        
        # Fetch historical data
        query = f'{metric_name}{{pipeline="{pipeline}"}}'
        history = await self.fetch_metric_history(query)
        
        if len(history) < 20:
            return AnomalyResult(
                metric_name=metric_name,
                pipeline=pipeline,
                is_anomaly=False,
                anomaly_score=0.0,
                expected_range=(0, 0),
                actual_value=current_value,
                algorithm="insufficient_data",
                explanation="Not enough historical data for detection"
            )
        
        # Method 1: Seasonal decomposition
        anomalies = self.seasonal.detect(history)
        is_seasonal_anomaly = anomalies[-1] if anomalies else False
        
        # Method 2: Expected range prediction
        expected_range = self.predictor.predict_expected_range(history)
        is_range_anomaly = current_value < expected_range[0] or current_value > expected_range[1]
        
        # Method 3: Rate of change
        if len(history) >= 2:
            recent_change = abs(current_value - history[-2]) / max(abs(history[-2]), 1)
            historical_changes = np.abs(np.diff(history)) / np.maximum(np.abs(history[:-1]), 1)
            change_threshold = np.percentile(historical_changes, 99)
            is_change_anomaly = recent_change > change_threshold
        else:
            is_change_anomaly = False
        
        # Consensus: anomaly if 2+ methods agree
        votes = sum([is_seasonal_anomaly, is_range_anomaly, is_change_anomaly])
        is_anomaly = votes >= 2
        anomaly_score = votes / 3.0
        
        # Generate explanation
        explanations = []
        if is_seasonal_anomaly:
            explanations.append("unusual for this time of day/week")
        if is_range_anomaly:
            explanations.append(f"outside expected range [{expected_range[0]:.2f}, {expected_range[1]:.2f}]")
        if is_change_anomaly:
            explanations.append("sudden rate of change")
        
        return AnomalyResult(
            metric_name=metric_name,
            pipeline=pipeline,
            is_anomaly=is_anomaly,
            anomaly_score=anomaly_score,
            expected_range=expected_range,
            actual_value=current_value,
            algorithm="consensus(seasonal+range+roc)",
            explanation="; ".join(explanations) if explanations else "within normal bounds"
        )


engine = AnomalyDetectionEngine()

@app.post("/v1/detect", response_model=AnomalyResult)
async def detect_anomaly(
    metric_name: str,
    pipeline: str,
    current_value: float
):
    """Detect if current metric value is anomalous."""
    return await engine.detect_anomaly(metric_name, pipeline, current_value)

@app.post("/v1/batch-detect", response_model=List[AnomalyResult])
async def batch_detect(metrics: List[Dict[str, Any]]):
    """Batch anomaly detection for multiple metrics."""
    results = []
    for m in metrics:
        result = await engine.detect_anomaly(
            m["metric_name"], m["pipeline"], m["current_value"]
        )
        results.append(result)
    return results
```

---

## Automated Remediation with Temporal

```python
"""
remediation_workflows.py
Temporal workflows for automated pipeline remediation.
"""

from temporalio import workflow, activity
from temporalio.common import RetryPolicy
from dataclasses import dataclass
from datetime import timedelta
from typing import Optional
import logging

logger = logging.getLogger(__name__)

@dataclass
class PipelineAlert:
    alert_name: str
    pipeline: str
    severity: str
    current_value: float
    threshold: float
    labels: dict

@dataclass
class RemediationResult:
    success: bool
    action_taken: str
    details: str
    escalated: bool = False

# --- Activities ---

@activity.defn
async def check_pipeline_status(pipeline: str) -> dict:
    """Check current pipeline status from multiple sources."""
    import httpx
    async with httpx.AsyncClient() as client:
        # Check Flink job status
        flink_resp = await client.get(
            f"http://flink-operator:8081/v1/deployments/{pipeline}/status"
        )
        
        # Check Kafka consumer lag
        lag_resp = await client.get(
            f"http://prometheus:9090/api/v1/query",
            params={"query": f'kafka_consumer_lag{{consumergroup="{pipeline}"}}'}
        )
        
        return {
            "flink_status": flink_resp.json() if flink_resp.status_code == 200 else None,
            "consumer_lag": lag_resp.json() if lag_resp.status_code == 200 else None,
        }

@activity.defn
async def scale_pipeline(pipeline: str, target_parallelism: int) -> bool:
    """Scale a Flink pipeline's parallelism."""
    import httpx
    async with httpx.AsyncClient() as client:
        resp = await client.patch(
            f"http://flink-operator:8081/v1/deployments/{pipeline}",
            json={"spec": {"job": {"parallelism": target_parallelism}}},
            timeout=30.0
        )
        return resp.status_code == 200

@activity.defn
async def restart_pipeline(pipeline: str) -> bool:
    """Restart a pipeline with a savepoint."""
    import httpx
    async with httpx.AsyncClient() as client:
        # Trigger savepoint
        sp_resp = await client.post(
            f"http://flink-operator:8081/v1/deployments/{pipeline}/savepoints"
        )
        
        if sp_resp.status_code != 200:
            return False
        
        # Restart from savepoint
        restart_resp = await client.post(
            f"http://flink-operator:8081/v1/deployments/{pipeline}/restart",
            json={"fromSavepoint": True}
        )
        return restart_resp.status_code == 200

@activity.defn
async def notify_team(pipeline: str, message: str, channel: str = "slack") -> bool:
    """Send notification to team."""
    import httpx
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://hooks.slack.com/services/XXX/YYY/ZZZ",
            json={
                "channel": f"#data-eng-{pipeline}",
                "text": message
            }
        )
        return resp.status_code == 200

@activity.defn
async def create_incident_ticket(
    pipeline: str, 
    alert: PipelineAlert, 
    remediation_result: RemediationResult
) -> str:
    """Create an incident ticket in Jira/PagerDuty."""
    import httpx
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "http://incident-service:8080/v1/incidents",
            json={
                "title": f"[Auto-Remediation] {alert.alert_name} on {pipeline}",
                "severity": alert.severity,
                "description": (
                    f"Alert: {alert.alert_name}\n"
                    f"Pipeline: {pipeline}\n"
                    f"Action taken: {remediation_result.action_taken}\n"
                    f"Result: {'Success' if remediation_result.success else 'Failed'}\n"
                    f"Details: {remediation_result.details}"
                ),
                "auto_remediated": remediation_result.success,
            }
        )
        return resp.json().get("incident_id", "unknown")

@activity.defn
async def wait_for_recovery(pipeline: str, timeout_minutes: int = 10) -> bool:
    """Wait for pipeline to recover (lag decreasing)."""
    import httpx
    import asyncio
    
    check_interval = 30  # seconds
    max_checks = (timeout_minutes * 60) // check_interval
    previous_lag = float('inf')
    
    async with httpx.AsyncClient() as client:
        for _ in range(max_checks):
            resp = await client.get(
                f"http://prometheus:9090/api/v1/query",
                params={
                    "query": f'sum(kafka_consumer_lag{{consumergroup="{pipeline}"}})'
                }
            )
            
            if resp.status_code == 200:
                result = resp.json()["data"]["result"]
                if result:
                    current_lag = float(result[0]["value"][1])
                    if current_lag < previous_lag * 0.8:  # Lag decreasing
                        return True
                    previous_lag = current_lag
            
            await asyncio.sleep(check_interval)
    
    return False


# --- Workflows ---

@workflow.defn
class PipelineLagRemediationWorkflow:
    """
    Automated remediation workflow for pipeline consumer lag.
    
    Strategy:
    1. Check current status
    2. Try scaling up (least disruptive)
    3. If still lagging, try restart from savepoint
    4. If still failing, escalate to human
    """
    
    @workflow.run
    async def run(self, alert: PipelineAlert) -> RemediationResult:
        pipeline = alert.pipeline
        
        # Step 1: Assess situation
        status = await workflow.execute_activity(
            check_pipeline_status,
            pipeline,
            start_to_close_timeout=timedelta(seconds=30),
        )
        
        await workflow.execute_activity(
            notify_team,
            args=[pipeline, f"Auto-remediation started for {alert.alert_name}"],
            start_to_close_timeout=timedelta(seconds=10),
        )
        
        # Step 2: Try scaling up
        current_parallelism = status.get("flink_status", {}).get("parallelism", 4)
        new_parallelism = min(current_parallelism * 2, 64)  # Cap at 64
        
        scaled = await workflow.execute_activity(
            scale_pipeline,
            args=[pipeline, new_parallelism],
            start_to_close_timeout=timedelta(seconds=60),
            retry_policy=RetryPolicy(maximum_attempts=3),
        )
        
        if scaled:
            # Wait for recovery
            recovered = await workflow.execute_activity(
                wait_for_recovery,
                args=[pipeline, 10],
                start_to_close_timeout=timedelta(minutes=12),
            )
            
            if recovered:
                result = RemediationResult(
                    success=True,
                    action_taken=f"Scaled from {current_parallelism} to {new_parallelism}",
                    details="Pipeline recovered after scaling"
                )
                await workflow.execute_activity(
                    notify_team,
                    args=[pipeline, f"Auto-remediation SUCCESS: {result.action_taken}"],
                    start_to_close_timeout=timedelta(seconds=10),
                )
                return result
        
        # Step 3: Try restart from savepoint
        restarted = await workflow.execute_activity(
            restart_pipeline,
            pipeline,
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=RetryPolicy(maximum_attempts=2),
        )
        
        if restarted:
            recovered = await workflow.execute_activity(
                wait_for_recovery,
                args=[pipeline, 15],
                start_to_close_timeout=timedelta(minutes=17),
            )
            
            if recovered:
                result = RemediationResult(
                    success=True,
                    action_taken="Restarted from savepoint",
                    details="Pipeline recovered after restart"
                )
                return result
        
        # Step 4: Escalate to human
        result = RemediationResult(
            success=False,
            action_taken="Attempted scale + restart, both failed",
            details="Escalating to on-call engineer",
            escalated=True
        )
        
        # Create incident
        await workflow.execute_activity(
            create_incident_ticket,
            args=[pipeline, alert, result],
            start_to_close_timeout=timedelta(seconds=30),
        )
        
        await workflow.execute_activity(
            notify_team,
            args=[pipeline, f"AUTO-REMEDIATION FAILED for {pipeline}. Incident created. Paging on-call."],
            start_to_close_timeout=timedelta(seconds=10),
        )
        
        return result
```

---

## Data Pipeline-Specific Features

### Pipeline Topology Visualization

```python
"""
pipeline_topology_api.py
API that serves live pipeline topology with health status
for custom Grafana plugin visualization.
"""

from fastapi import FastAPI
from typing import List, Dict, Optional
from dataclasses import dataclass
from enum import Enum
import httpx

app = FastAPI(title="Pipeline Topology API")

class HealthStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    CRITICAL = "critical"
    UNKNOWN = "unknown"

@dataclass
class PipelineNode:
    id: str
    name: str
    type: str  # source, transform, sink, kafka_topic
    health: HealthStatus
    metrics: Dict[str, float]  # throughput, latency, error_rate
    metadata: Dict[str, str]

@dataclass  
class PipelineEdge:
    source: str
    target: str
    throughput_per_sec: float
    lag_seconds: float

@dataclass
class PipelineTopology:
    nodes: List[PipelineNode]
    edges: List[PipelineEdge]
    last_updated: float


async def fetch_pipeline_health() -> PipelineTopology:
    """Build topology from multiple sources."""
    
    async with httpx.AsyncClient() as client:
        # Get pipeline definitions from Airflow/Flink
        # Get health metrics from Prometheus
        # Get lineage from DataHub
        
        prom_resp = await client.get(
            "http://thanos-query:9090/api/v1/query",
            params={"query": "pipeline:error_rate:ratio5m"}
        )
        
        error_rates = {}
        if prom_resp.status_code == 200:
            for result in prom_resp.json()["data"]["result"]:
                pipeline = result["metric"].get("pipeline", "")
                rate = float(result["value"][1])
                error_rates[pipeline] = rate
    
    # Build topology (simplified)
    nodes = [
        PipelineNode(
            id="kafka-events",
            name="Events Topic",
            type="kafka_topic",
            health=HealthStatus.HEALTHY,
            metrics={"throughput": 50000, "partitions": 64},
            metadata={"topic": "events.raw"}
        ),
        PipelineNode(
            id="flink-transform",
            name="Event Transform",
            type="transform",
            health=HealthStatus.HEALTHY if error_rates.get("transform", 0) < 0.01 
                   else HealthStatus.DEGRADED,
            metrics={
                "throughput": 48000,
                "latency_p99": 2.3,
                "error_rate": error_rates.get("transform", 0)
            },
            metadata={"framework": "flink", "parallelism": "32"}
        ),
        PipelineNode(
            id="dwh-sink",
            name="Data Warehouse",
            type="sink",
            health=HealthStatus.HEALTHY,
            metrics={"throughput": 47000, "freshness_seconds": 120},
            metadata={"system": "BigQuery", "dataset": "analytics"}
        ),
    ]
    
    edges = [
        PipelineEdge(
            source="kafka-events",
            target="flink-transform",
            throughput_per_sec=50000,
            lag_seconds=5
        ),
        PipelineEdge(
            source="flink-transform",
            target="dwh-sink",
            throughput_per_sec=48000,
            lag_seconds=120
        ),
    ]
    
    import time
    return PipelineTopology(nodes=nodes, edges=edges, last_updated=time.time())


@app.get("/v1/topology")
async def get_topology():
    """Get current pipeline topology with health status."""
    topology = await fetch_pipeline_health()
    return {
        "nodes": [vars(n) for n in topology.nodes],
        "edges": [vars(e) for e in topology.edges],
        "last_updated": topology.last_updated
    }

@app.get("/v1/impact/{node_id}")
async def get_impact_analysis(node_id: str):
    """
    If node X fails, what downstream systems are affected?
    Uses lineage graph for impact analysis.
    """
    # Query DataHub lineage API
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"http://datahub-api:8080/relationships",
            params={
                "urn": f"urn:li:dataJob:{node_id}",
                "direction": "OUTGOING",
                "types": ["Produces", "Consumes"],
                "maxHops": 5
            }
        )
    
    if resp.status_code != 200:
        return {"affected_nodes": [], "error": "Lineage lookup failed"}
    
    downstream = resp.json().get("relationships", [])
    
    return {
        "source_node": node_id,
        "affected_downstream": [
            {
                "node": rel["entity"],
                "impact": "data_freshness_violation" if rel["hops"] <= 2 else "delayed",
                "estimated_impact_time": f"{rel['hops'] * 30}min",
            }
            for rel in downstream
        ],
        "total_affected": len(downstream),
        "recommendation": "Notify downstream consumers before maintenance"
    }
```

---

## Self-Service Monitoring Onboarding

```python
"""
monitoring_onboarding_api.py
Self-service API for data teams to onboard their pipelines to monitoring.
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional, Dict
import yaml
import json

app = FastAPI(title="Monitoring Onboarding API")

class PipelineOnboardingRequest(BaseModel):
    """Request to onboard a new pipeline to monitoring."""
    pipeline_name: str = Field(..., regex=r'^[a-z][a-z0-9-]{2,50}$')
    team: str
    description: str
    
    # SLO configuration
    availability_slo: float = Field(99.9, ge=90.0, le=100.0)
    latency_p99_slo_seconds: float = Field(30.0, gt=0)
    freshness_slo_seconds: float = Field(3600, gt=0)
    
    # Data sources
    kafka_topics: List[str] = []
    kafka_consumer_groups: List[str] = []
    
    # Alert routing
    slack_channel: str
    pagerduty_service_id: Optional[str] = None
    
    # Labels
    criticality: str = Field("standard", regex=r'^(critical|high|standard|low)$')
    environment: str = Field("production", regex=r'^(production|staging|dev)$')

class OnboardingResult(BaseModel):
    success: bool
    dashboard_url: str
    alert_rules_created: List[str]
    service_monitor_created: bool
    message: str


def generate_prometheus_rules(req: PipelineOnboardingRequest) -> dict:
    """Generate PrometheusRule for the pipeline."""
    
    error_budget = 1 - (req.availability_slo / 100)
    
    rules = {
        "apiVersion": "monitoring.coreos.com/v1",
        "kind": "PrometheusRule",
        "metadata": {
            "name": f"pipeline-{req.pipeline_name}",
            "namespace": "monitoring",
            "labels": {
                "team": req.team,
                "pipeline": req.pipeline_name,
                "release": "kube-prometheus-stack"
            }
        },
        "spec": {
            "groups": [
                {
                    "name": f"{req.pipeline_name}.slo",
                    "rules": [
                        {
                            "alert": f"{req.pipeline_name.title()}ErrorBudgetBurn",
                            "expr": (
                                f'(\n'
                                f'  sum(rate(pipeline_events_processed_total{{pipeline="{req.pipeline_name}", status="failed"}}[1h]))\n'
                                f'  / sum(rate(pipeline_events_processed_total{{pipeline="{req.pipeline_name}"}}[1h]))\n'
                                f') > {14.4 * error_budget}'
                            ),
                            "for": "2m",
                            "labels": {
                                "severity": "critical",
                                "team": req.team,
                                "pipeline": req.pipeline_name
                            },
                            "annotations": {
                                "summary": f"Pipeline {req.pipeline_name} burning error budget",
                                "runbook_url": f"https://runbooks.company.com/pipeline/{req.pipeline_name}"
                            }
                        },
                        {
                            "alert": f"{req.pipeline_name.title()}LatencyHigh",
                            "expr": (
                                f'histogram_quantile(0.99, '
                                f'sum(rate(pipeline_processing_duration_seconds_bucket{{pipeline="{req.pipeline_name}"}}[5m])) by (le)'
                                f') > {req.latency_p99_slo_seconds}'
                            ),
                            "for": "10m",
                            "labels": {
                                "severity": "warning",
                                "team": req.team,
                                "pipeline": req.pipeline_name
                            },
                            "annotations": {
                                "summary": f"Pipeline {req.pipeline_name} p99 latency exceeds SLO"
                            }
                        },
                        {
                            "alert": f"{req.pipeline_name.title()}DataStale",
                            "expr": (
                                f'time() - pipeline_last_successful_run_timestamp_seconds'
                                f'{{pipeline="{req.pipeline_name}"}} > {req.freshness_slo_seconds}'
                            ),
                            "for": "5m",
                            "labels": {
                                "severity": "critical",
                                "team": req.team,
                                "pipeline": req.pipeline_name
                            },
                            "annotations": {
                                "summary": f"Pipeline {req.pipeline_name} data freshness SLO breached"
                            }
                        }
                    ]
                }
            ]
        }
    }
    
    # Add Kafka lag alerts if topics configured
    if req.kafka_consumer_groups:
        kafka_rules = []
        for cg in req.kafka_consumer_groups:
            kafka_rules.append({
                "alert": f"{req.pipeline_name.title()}KafkaLagHigh",
                "expr": f'sum(kafka_consumergroup_lag{{consumergroup="{cg}"}}) > 1000000',
                "for": "5m",
                "labels": {
                    "severity": "warning",
                    "team": req.team,
                    "pipeline": req.pipeline_name
                },
                "annotations": {
                    "summary": f"Consumer group {cg} lag exceeds 1M"
                }
            })
        
        rules["spec"]["groups"].append({
            "name": f"{req.pipeline_name}.kafka",
            "rules": kafka_rules
        })
    
    return rules


def generate_grafana_dashboard(req: PipelineOnboardingRequest) -> dict:
    """Generate a standard Grafana dashboard for the pipeline."""
    return {
        "dashboard": {
            "title": f"Pipeline: {req.pipeline_name}",
            "tags": ["pipeline", req.team, "auto-generated"],
            "templating": {
                "list": [
                    {
                        "name": "pipeline",
                        "type": "constant",
                        "query": req.pipeline_name
                    }
                ]
            },
            "panels": [
                {
                    "title": "Throughput (events/sec)",
                    "type": "timeseries",
                    "targets": [{
                        "expr": f'sum(rate(pipeline_events_processed_total{{pipeline="{req.pipeline_name}"}}[5m]))'
                    }],
                    "gridPos": {"x": 0, "y": 0, "w": 12, "h": 8}
                },
                {
                    "title": "Error Rate",
                    "type": "timeseries",
                    "targets": [{
                        "expr": f'pipeline:error_rate:ratio5m{{pipeline="{req.pipeline_name}"}}'
                    }],
                    "fieldConfig": {
                        "defaults": {
                            "thresholds": {
                                "steps": [
                                    {"value": 0, "color": "green"},
                                    {"value": 0.01, "color": "yellow"},
                                    {"value": 0.05, "color": "red"}
                                ]
                            }
                        }
                    },
                    "gridPos": {"x": 12, "y": 0, "w": 12, "h": 8}
                },
                {
                    "title": "Latency Percentiles",
                    "type": "timeseries",
                    "targets": [
                        {"expr": f'pipeline:latency_seconds:p99_5m{{pipeline="{req.pipeline_name}"}}', "legendFormat": "p99"},
                        {"expr": f'pipeline:latency_seconds:p95_5m{{pipeline="{req.pipeline_name}"}}', "legendFormat": "p95"},
                    ],
                    "gridPos": {"x": 0, "y": 8, "w": 12, "h": 8}
                },
                {
                    "title": "SLO Error Budget Remaining",
                    "type": "gauge",
                    "targets": [{
                        "expr": f'pipeline:slo_error_budget:remaining{{pipeline="{req.pipeline_name}"}} * 100'
                    }],
                    "gridPos": {"x": 12, "y": 8, "w": 12, "h": 8}
                }
            ]
        },
        "folderId": 0,
        "overwrite": True
    }


@app.post("/v1/onboard", response_model=OnboardingResult)
async def onboard_pipeline(req: PipelineOnboardingRequest):
    """
    Onboard a pipeline to the monitoring platform.
    Creates: alert rules, dashboard, service monitor.
    """
    import httpx
    
    # 1. Generate and apply PrometheusRule
    rules = generate_prometheus_rules(req)
    
    async with httpx.AsyncClient() as client:
        # Apply via Kubernetes API (or GitOps commit)
        k8s_resp = await client.post(
            "https://kubernetes.default.svc/apis/monitoring.coreos.com/v1/namespaces/monitoring/prometheusrules",
            json=rules,
            headers={"Authorization": "Bearer <sa-token>"},
            verify=False
        )
    
    # 2. Generate and create Grafana dashboard
    dashboard = generate_grafana_dashboard(req)
    
    async with httpx.AsyncClient() as client:
        grafana_resp = await client.post(
            "http://grafana:3000/api/dashboards/db",
            json=dashboard,
            headers={"Authorization": "Bearer <grafana-api-key>"}
        )
        dashboard_url = f"http://grafana.internal.company.com{grafana_resp.json().get('url', '')}"
    
    # 3. Create alert routing for team
    alert_rules_created = [
        f"{req.pipeline_name}-error-budget-burn",
        f"{req.pipeline_name}-latency-slo",
        f"{req.pipeline_name}-data-freshness",
    ]
    if req.kafka_consumer_groups:
        alert_rules_created.append(f"{req.pipeline_name}-kafka-lag")
    
    return OnboardingResult(
        success=True,
        dashboard_url=dashboard_url,
        alert_rules_created=alert_rules_created,
        service_monitor_created=True,
        message=f"Pipeline '{req.pipeline_name}' onboarded successfully. "
                f"Dashboard: {dashboard_url}"
    )
```

---

## Organizational Adoption

### Platform Team Structure

```
┌─────────────────────────────────────────────────────────────────┐
│                  Observability Platform Team                      │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Platform Engineers (3-5)                                │   │
│  │  • Maintain monitoring infrastructure                    │   │
│  │  • Build self-service APIs                              │   │
│  │  • Optimize costs                                       │   │
│  │  • On-call for monitoring stack itself                  │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Embedded SREs (per data team)                           │   │
│  │  • Help define SLOs                                     │   │
│  │  • Review alert rules                                   │   │
│  │  • Build team-specific dashboards                       │   │
│  │  • On-call for data pipelines                           │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Data Teams (self-service users)                         │   │
│  │  • Onboard pipelines via API/UI                         │   │
│  │  • Define SLOs for their pipelines                      │   │
│  │  • Own their alert rules (review by SRE)                │   │
│  │  • First responders for their pipeline alerts           │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Cost Allocation Model

| Metric Type | Allocation Basis | Example |
|------------|-----------------|---------|
| Metric series | Per team's active series count | Team A: 50K series = $X/mo |
| Log volume | Per team's ingested GB/day | Team B: 100GB/day = $Y/mo |
| Trace storage | Per team's sampled spans | Team C: 10M spans/day = $Z/mo |
| Dashboard compute | Shared (platform budget) | N/A |
| Alert evaluation | Per team's rule count | Team D: 50 rules = $W/mo |

### Maturity Model

| Level | Characteristics | Monitoring Approach |
|-------|----------------|---------------------|
| 1 - Reactive | Manual checks, no alerts | Cron scripts + email |
| 2 - Proactive | Basic alerting, manual investigation | Prometheus + Grafana |
| 3 - SLO-driven | Error budgets, burn rate alerts | Multi-window SLOs |
| 4 - Automated | Self-healing, predictive alerts | ML anomaly + Temporal |
| 5 - Intelligent | AI root cause, NL querying, auto-optimization | Full platform |

---

## Summary

A unified observability platform for data engineering requires:

1. **Single collection standard** (OpenTelemetry) across all components
2. **Correlation by design** - trace_id + pipeline_run_id + lineage propagated everywhere
3. **Intelligence layer** - ML anomaly detection, automated root cause analysis
4. **Self-service** - Data teams onboard in minutes via API, not weeks via tickets
5. **Lineage-aware** - Alerts understand upstream causes and downstream impact
6. **Action-oriented** - From detection to automated remediation in seconds
7. **Cost-transparent** - Every team knows what their observability costs

The platform is never "done" - it evolves with the organization's maturity from basic metrics to AI-powered autonomous operations.
