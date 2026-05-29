# Metrics Monitoring System (like Datadog)

## 1. Requirements

### Functional Requirements
- Agent-based metric collection from hosts, containers, and cloud services
- Custom metrics API for application-level instrumentation
- Infrastructure metrics: CPU, memory, disk, network, container stats
- Metric visualization: time-series graphs, heatmaps, top lists, distributions
- Alerting: threshold-based, anomaly detection, forecast-based
- Dashboard builder with drag-and-drop widgets
- Service map auto-discovery from network flows
- Correlation across metrics, logs, and traces
- Tagging system for multi-dimensional querying
- Role-based access control for dashboards and alerts

### Non-Functional Requirements
- Ingest 10M+ metrics/second across all tenants
- Query latency < 500ms for 95th percentile dashboard loads
- Alert evaluation within 30 seconds of data arrival
- 99.99% availability for alerting pipeline
- 15-month retention with automatic downsampling
- Horizontal scalability for ingestion and query

## 2. Core Entities

```
Metric: metric_id, name, type (gauge/counter/rate/histogram), tags[], unit
MetricPoint: metric_id, timestamp, value, tags[]
Host: host_id, hostname, os, cloud_provider, region, tags[]
Container: container_id, host_id, image, name, labels[]
Dashboard: dashboard_id, owner_id, title, widgets[], layout, shared_with[]
Widget: widget_id, type, query, visualization_config, thresholds[]
Alert: alert_id, name, query, conditions[], notification_targets[], severity
AlertEvent: event_id, alert_id, status, timestamp, value, tags[]
Monitor: monitor_id, name, type (metric/anomaly/forecast/composite), query, thresholds
ServiceMap: service_id, dependencies[], metrics_summary
Tag: key, value (indexed for fast lookups)
```

## 3. API Design

### Metric Submission API
```
POST /api/v2/series
Authorization: Bearer <API_KEY>
Content-Type: application/json
Content-Encoding: gzip

Request:
{
  "series": [
    {
      "metric": "system.cpu.user",
      "type": "gauge",
      "points": [
        { "timestamp": 1700000000, "value": 72.5 }
      ],
      "tags": ["host:web-01", "env:production", "service:api"],
      "unit": "percent",
      "interval": 15
    },
    {
      "metric": "app.request.count",
      "type": "count",
      "points": [
        { "timestamp": 1700000000, "value": 1523 }
      ],
      "tags": ["endpoint:/api/users", "method:GET", "status:200"]
    }
  ]
}

Response (202 Accepted):
{
  "status": "ok",
  "errors": []
}
```

### Metric Query API
```
POST /api/v2/query
Authorization: Bearer <API_KEY>

Request:
{
  "query": "avg:system.cpu.user{env:production,service:api} by {host}",
  "from": 1700000000,
  "to": 1700003600,
  "interval": 60
}

Response:
{
  "series": [
    {
      "metric": "system.cpu.user",
      "tag_set": ["host:web-01"],
      "points": [
        [1700000000, 72.5],
        [1700000060, 68.3],
        [1700000120, 75.1]
      ],
      "aggregator": "avg",
      "unit": { "name": "percent", "scale_factor": 1 }
    }
  ],
  "query": "avg:system.cpu.user{env:production,service:api} by {host}",
  "from": 1700000000,
  "to": 1700003600
}
```

### Dashboard API
```
POST /api/v2/dashboards
Authorization: Bearer <API_KEY>

Request:
{
  "title": "Production Overview",
  "layout_type": "ordered",
  "widgets": [
    {
      "definition": {
        "type": "timeseries",
        "requests": [
          {
            "query": "avg:system.cpu.user{env:production} by {host}",
            "display_type": "line",
            "style": { "palette": "warm" }
          }
        ],
        "title": "CPU Usage by Host",
        "markers": [
          { "value": "y = 80", "display_type": "error dashed" }
        ]
      },
      "layout": { "x": 0, "y": 0, "width": 6, "height": 3 }
    }
  ],
  "tags": ["team:platform"]
}

Response (201):
{
  "id": "dash-abc123",
  "title": "Production Overview",
  "url": "/dashboards/dash-abc123",
  "created_at": "2024-01-15T10:00:00Z"
}
```

### Monitor/Alert API
```
POST /api/v2/monitors
Authorization: Bearer <API_KEY>

Request:
{
  "name": "High CPU on Production Hosts",
  "type": "metric alert",
  "query": "avg(last_5m):avg:system.cpu.user{env:production} by {host} > 90",
  "message": "CPU usage is {{value}} on {{host.name}}. @slack-ops @pagerduty-infra",
  "options": {
    "thresholds": {
      "critical": 90,
      "warning": 80,
      "critical_recovery": 70,
      "warning_recovery": 60
    },
    "notify_no_data": true,
    "no_data_timeframe": 10,
    "evaluation_delay": 60,
    "new_group_delay": 300,
    "renotify_interval": 300
  },
  "tags": ["team:platform", "env:production"],
  "priority": 2
}

Response (201):
{
  "id": "mon-789xyz",
  "name": "High CPU on Production Hosts",
  "status": "OK",
  "created_at": "2024-01-15T10:00:00Z"
}
```

## 4. High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           METRICS MONITORING SYSTEM                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌───────────┐                  │
│  │  Host    │  │Container │  │  Cloud   │  │Application│                  │
│  │  Agent   │  │  Agent   │  │Integration│ │   SDK     │                  │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └─────┬─────┘                  │
│       │              │              │              │                         │
│       └──────────────┴──────┬───────┴──────────────┘                        │
│                             │                                               │
│                    ┌────────▼────────┐                                      │
│                    │  Intake Gateway │  (Load Balancer + Auth)               │
│                    │  (API Gateway)  │                                      │
│                    └────────┬────────┘                                      │
│                             │                                               │
│                    ┌────────▼────────┐                                      │
│                    │   Kafka Cluster │  (Partitioned by metric+tags hash)   │
│                    │  metrics-raw    │                                      │
│                    └───┬────────┬────┘                                      │
│                        │        │                                           │
│           ┌────────────▼──┐  ┌──▼───────────────┐                          │
│           │  Aggregation  │  │  Alert Evaluation │                          │
│           │   Workers     │  │     Engine        │                          │
│           └───────┬───────┘  └────────┬──────────┘                          │
│                   │                   │                                      │
│           ┌───────▼───────┐  ┌────────▼──────────┐                          │
│           │  Time-Series  │  │  Alert State DB   │                          │
│           │   Database    │  │  (Redis Cluster)  │                          │
│           │  (Custom TSDB)│  └────────┬──────────┘                          │
│           └───────┬───────┘           │                                      │
│                   │          ┌────────▼──────────┐                          │
│           ┌───────▼───────┐  │  Notification     │                          │
│           │  Query Engine │  │     Service       │                          │
│           │  (Distributed)│  └───────────────────┘                          │
│           └───────┬───────┘                                                 │
│                   │                                                          │
│           ┌───────▼───────┐                                                 │
│           │  Dashboard    │                                                 │
│           │   Service     │                                                 │
│           └───────────────┘                                                 │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 5. Deep Dive: Time-Series Database Engine

### Gorilla Compression (Facebook's Algorithm)

```python
class GorillaCompressor:
    """
    Delta-of-delta for timestamps, XOR for values.
    Achieves 12x compression on real-world metric data.
    """
    
    def __init__(self):
        self.prev_timestamp = 0
        self.prev_delta = 0
        self.prev_value_bits = 0
        self.prev_leading_zeros = float('inf')
        self.prev_trailing_zeros = 0
        self.bit_buffer = BitBuffer()
    
    def compress_timestamp(self, timestamp):
        if self.prev_timestamp == 0:
            # First timestamp: store full 64-bit value
            self.bit_buffer.write_bits(timestamp, 64)
            self.prev_timestamp = timestamp
            return
        
        delta = timestamp - self.prev_timestamp
        delta_of_delta = delta - self.prev_delta
        
        if delta_of_delta == 0:
            # Same interval - write single 0 bit
            self.bit_buffer.write_bit(0)
        elif -63 <= delta_of_delta <= 64:
            # Fits in 7 bits
            self.bit_buffer.write_bits(0b10, 2)
            self.bit_buffer.write_bits(delta_of_delta + 63, 7)  # bias encoding
        elif -255 <= delta_of_delta <= 256:
            # Fits in 9 bits
            self.bit_buffer.write_bits(0b110, 3)
            self.bit_buffer.write_bits(delta_of_delta + 255, 9)
        elif -2047 <= delta_of_delta <= 2048:
            # Fits in 12 bits
            self.bit_buffer.write_bits(0b1110, 4)
            self.bit_buffer.write_bits(delta_of_delta + 2047, 12)
        else:
            # Full 64-bit delta
            self.bit_buffer.write_bits(0b1111, 4)
            self.bit_buffer.write_bits(delta, 64)
        
        self.prev_delta = delta
        self.prev_timestamp = timestamp
    
    def compress_value(self, value):
        """XOR-based double compression for float64 values."""
        value_bits = float_to_bits(value)
        
        if self.prev_value_bits == 0 and value_bits == 0:
            self.bit_buffer.write_bit(0)
            return
        
        xor = value_bits ^ self.prev_value_bits
        
        if xor == 0:
            # Same value - write single 0 bit
            self.bit_buffer.write_bit(0)
        else:
            self.bit_buffer.write_bit(1)
            leading_zeros = count_leading_zeros(xor)
            trailing_zeros = count_trailing_zeros(xor)
            
            if (leading_zeros >= self.prev_leading_zeros and 
                trailing_zeros >= self.prev_trailing_zeros):
                # Reuse previous block size - write 0 + meaningful bits
                self.bit_buffer.write_bit(0)
                meaningful_bits = 64 - self.prev_leading_zeros - self.prev_trailing_zeros
                self.bit_buffer.write_bits(
                    xor >> self.prev_trailing_zeros, meaningful_bits
                )
            else:
                # New block size
                self.bit_buffer.write_bit(1)
                self.bit_buffer.write_bits(leading_zeros, 6)
                meaningful_bits = 64 - leading_zeros - trailing_zeros
                self.bit_buffer.write_bits(meaningful_bits, 6)
                self.bit_buffer.write_bits(xor >> trailing_zeros, meaningful_bits)
                
                self.prev_leading_zeros = leading_zeros
                self.prev_trailing_zeros = trailing_zeros
        
        self.prev_value_bits = value_bits
```

### Chunk-Based Storage with Rollups

```python
class TimeSeriesChunk:
    """
    2-hour chunks of compressed time-series data.
    Immutable once sealed (append-only during active window).
    """
    
    CHUNK_DURATION = 7200  # 2 hours in seconds
    
    def __init__(self, metric_id, start_time, tags_hash):
        self.metric_id = metric_id
        self.start_time = start_time
        self.end_time = start_time + self.CHUNK_DURATION
        self.tags_hash = tags_hash
        self.compressor = GorillaCompressor()
        self.min_value = float('inf')
        self.max_value = float('-inf')
        self.sum_value = 0.0
        self.count = 0
        self.sealed = False
    
    def append(self, timestamp, value):
        if self.sealed:
            raise ChunkSealedError()
        if timestamp < self.start_time or timestamp >= self.end_time:
            raise OutOfRangeError()
        
        self.compressor.compress_timestamp(timestamp)
        self.compressor.compress_value(value)
        
        # Maintain aggregates for rollup
        self.min_value = min(self.min_value, value)
        self.max_value = max(self.max_value, value)
        self.sum_value += value
        self.count += 1
    
    def seal(self):
        """Seal chunk and flush to persistent storage."""
        self.sealed = True
        return ChunkMetadata(
            metric_id=self.metric_id,
            start_time=self.start_time,
            end_time=self.end_time,
            tags_hash=self.tags_hash,
            min_value=self.min_value,
            max_value=self.max_value,
            avg_value=self.sum_value / self.count if self.count > 0 else 0,
            count=self.count,
            size_bytes=self.compressor.bit_buffer.size()
        )


class RollupEngine:
    """
    Downsample high-resolution data into lower resolution for long-term storage.
    Retention policy:
      - Raw (15s intervals): 15 days
      - 1-minute rollups: 63 days
      - 5-minute rollups: 15 months
      - 1-hour rollups: indefinite
    """
    
    ROLLUP_CONFIGS = [
        RollupConfig(source_resolution=15, target_resolution=60, retention_days=63),
        RollupConfig(source_resolution=60, target_resolution=300, retention_days=450),
        RollupConfig(source_resolution=300, target_resolution=3600, retention_days=None),
    ]
    
    def rollup_chunk(self, chunk, target_resolution):
        """Aggregate chunk data into lower resolution buckets."""
        points = chunk.decompress_all()
        buckets = defaultdict(list)
        
        for timestamp, value in points:
            bucket_key = (timestamp // target_resolution) * target_resolution
            buckets[bucket_key].append(value)
        
        rolled_up = []
        for bucket_ts, values in sorted(buckets.items()):
            rolled_up.append(RollupPoint(
                timestamp=bucket_ts,
                min=min(values),
                max=max(values),
                sum=sum(values),
                count=len(values),
                avg=sum(values) / len(values),
                p50=percentile(values, 50),
                p95=percentile(values, 95),
                p99=percentile(values, 99)
            ))
        
        return rolled_up
```

### Tag-Based Indexing with Inverted Index

```python
class MetricIndex:
    """
    Inverted index for fast tag-based metric lookups.
    Maps tag key:value → set of series IDs.
    """
    
    def __init__(self):
        # tag_value -> sorted list of series_ids (posting list)
        self.postings = {}  # "env:production" -> [sid1, sid2, sid3, ...]
        # series_id -> full tag set
        self.series_tags = {}
        # metric_name -> sorted list of series_ids
        self.metric_index = {}
    
    def index_series(self, series_id, metric_name, tags):
        """Add or update a series in the index."""
        self.series_tags[series_id] = tags
        
        # Index by metric name
        if metric_name not in self.metric_index:
            self.metric_index[metric_name] = SortedList()
        self.metric_index[metric_name].add(series_id)
        
        # Index each tag
        for tag in tags:
            if tag not in self.postings:
                self.postings[tag] = RoaringBitmap()
            self.postings[tag].add(series_id)
    
    def query(self, metric_name, tag_filters, group_by=None):
        """
        Resolve query: avg:system.cpu{env:production,service:api} by {host}
        Uses intersection of posting lists for AND semantics.
        """
        # Start with all series for this metric
        if metric_name not in self.metric_index:
            return []
        
        result_set = RoaringBitmap(self.metric_index[metric_name])
        
        # Intersect with each tag filter
        for tag_filter in tag_filters:
            if tag_filter.is_wildcard():
                # env:* → union all posting lists with prefix "env:"
                matching = RoaringBitmap()
                for key, posting in self.postings.items():
                    if key.startswith(tag_filter.key + ":"):
                        matching |= posting
                result_set &= matching
            elif tag_filter.is_negation():
                # !env:staging → subtract from result
                if tag_filter.value in self.postings:
                    result_set -= self.postings[tag_filter.value]
            else:
                # Exact match
                tag_key = f"{tag_filter.key}:{tag_filter.value}"
                if tag_key in self.postings:
                    result_set &= self.postings[tag_key]
                else:
                    return []  # No matches
        
        # Group by specified tag
        if group_by:
            groups = defaultdict(list)
            for series_id in result_set:
                tags = self.series_tags[series_id]
                group_value = next(
                    (t.split(":", 1)[1] for t in tags if t.startswith(group_by + ":")),
                    "__none__"
                )
                groups[group_value].append(series_id)
            return groups
        
        return list(result_set)
```

## 6. Deep Dive: Alert Evaluation Engine

```python
class AlertEvaluationEngine:
    """
    Periodic evaluation of monitor queries against metric data.
    Supports threshold, anomaly, forecast, and composite monitors.
    """
    
    def __init__(self, tsdb, state_store, notification_service):
        self.tsdb = tsdb
        self.state_store = state_store  # Redis cluster
        self.notification_service = notification_service
        self.evaluators = {
            'metric': ThresholdEvaluator(),
            'anomaly': AnomalyEvaluator(),
            'forecast': ForecastEvaluator(),
            'composite': CompositeEvaluator(),
        }
    
    async def evaluate_monitor(self, monitor):
        """Evaluate a single monitor against current data."""
        evaluator = self.evaluators[monitor.type]
        
        # Fetch data for evaluation window
        query_result = await self.tsdb.query(
            metric=monitor.parsed_query.metric,
            tags=monitor.parsed_query.tags,
            aggregation=monitor.parsed_query.aggregation,
            window=monitor.parsed_query.window,
            group_by=monitor.parsed_query.group_by
        )
        
        # Evaluate each group independently
        results = {}
        for group_key, series in query_result.groups.items():
            status = evaluator.evaluate(series, monitor.thresholds)
            results[group_key] = status
        
        # Update state and trigger notifications
        await self._process_results(monitor, results)
    
    async def _process_results(self, monitor, results):
        """Process evaluation results, handle state transitions."""
        for group_key, new_status in results.items():
            state_key = f"monitor:{monitor.id}:group:{group_key}"
            prev_state = await self.state_store.get_state(state_key)
            
            if self._is_state_transition(prev_state, new_status):
                # Deduplicate: check if we already alerted in this window
                dedup_key = f"dedup:{monitor.id}:{group_key}:{new_status.level}"
                if await self.state_store.set_nx(dedup_key, ttl=monitor.renotify_interval):
                    await self._trigger_alert(monitor, group_key, prev_state, new_status)
            
            await self.state_store.set_state(state_key, new_status)


class AnomalyEvaluator:
    """
    Anomaly detection using seasonal decomposition + DBSCAN.
    Learns normal patterns and alerts on deviations.
    """
    
    def evaluate(self, series, thresholds):
        # Seasonal decomposition (STL - Seasonal-Trend Loess)
        seasonal, trend, residual = self.stl_decompose(
            series.values,
            period=self._detect_seasonality(series)
        )
        
        # DBSCAN on residuals to find anomalous points
        residual_points = np.array(residual).reshape(-1, 1)
        clustering = DBSCAN(
            eps=thresholds.anomaly_sensitivity * np.std(residual),
            min_samples=3
        ).fit(residual_points)
        
        # Points labeled -1 are anomalies
        anomaly_indices = np.where(clustering.labels_ == -1)[0]
        
        # Check if recent points are anomalous
        recent_window = len(series.values) - thresholds.evaluation_points
        recent_anomalies = [i for i in anomaly_indices if i >= recent_window]
        
        if len(recent_anomalies) >= thresholds.min_anomaly_points:
            deviation = self._calculate_deviation(series, seasonal, trend)
            return AlertStatus(
                level='critical' if deviation > thresholds.critical_deviations else 'warning',
                value=deviation,
                message=f"Anomaly detected: {deviation:.1f} standard deviations from expected"
            )
        
        return AlertStatus(level='ok')
    
    def stl_decompose(self, values, period):
        """Seasonal-Trend decomposition using LOESS."""
        n = len(values)
        # Initial trend estimate using moving average
        trend = self._moving_average(values, period)
        
        for iteration in range(6):  # Iterative refinement
            # Detrend
            detrended = [values[i] - trend[i] for i in range(n)]
            
            # Extract seasonal component
            seasonal = self._extract_seasonal(detrended, period)
            
            # Deseasoned
            deseasoned = [values[i] - seasonal[i % period] for i in range(n)]
            
            # Re-estimate trend with LOESS on deseasoned
            trend = self._loess_smooth(deseasoned, bandwidth=1.5 * period)
        
        residual = [values[i] - trend[i] - seasonal[i % period] for i in range(n)]
        return seasonal, trend, residual


class CompositeMonitor:
    """
    Multi-condition alerts that combine multiple monitors.
    Example: Alert only if BOTH high CPU AND high memory.
    """
    
    def __init__(self, monitor_ids, operator, trigger_window):
        self.monitor_ids = monitor_ids
        self.operator = operator  # AND, OR, NOT
        self.trigger_window = trigger_window
    
    def evaluate(self, monitor_states):
        statuses = [monitor_states.get(mid, 'ok') for mid in self.monitor_ids]
        
        if self.operator == 'AND':
            return all(s in ('warning', 'critical') for s in statuses)
        elif self.operator == 'OR':
            return any(s in ('warning', 'critical') for s in statuses)
        elif self.operator == 'NOT':
            return statuses[0] not in ('warning', 'critical')
```

## 7. Deep Dive: Agent Architecture

```python
class MetricAgent:
    """
    Lightweight agent deployed on every host/node.
    Plugin-based collection with local aggregation.
    """
    
    def __init__(self, config):
        self.config = config
        self.collectors = self._load_collectors()
        self.aggregator = LocalAggregator(flush_interval=15)
        self.forwarder = BatchForwarder(
            endpoint=config.intake_url,
            api_key=config.api_key,
            batch_size=1000,
            compression='zstd'
        )
        self.auto_discovery = AutoDiscovery(config)
    
    def _load_collectors(self):
        """Load plugin-based collectors based on config and auto-discovery."""
        collectors = [
            SystemCollector(),  # CPU, memory, disk, network
            ProcessCollector(),  # Per-process metrics
        ]
        
        # Auto-discover services
        if self.config.container_runtime:
            collectors.append(ContainerCollector(self.config.container_runtime))
        
        # Load integration plugins
        for integration in self.config.integrations:
            collector_class = COLLECTOR_REGISTRY.get(integration.name)
            if collector_class:
                collectors.append(collector_class(integration.config))
        
        return collectors
    
    async def run(self):
        """Main agent loop."""
        # Start auto-discovery in background
        asyncio.create_task(self.auto_discovery.watch())
        
        while True:
            collection_start = time.time()
            
            # Collect from all plugins in parallel
            tasks = [c.collect() for c in self.collectors]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for result in results:
                if isinstance(result, Exception):
                    log.error(f"Collection error: {result}")
                    continue
                for metric_point in result:
                    # Add host-level tags
                    metric_point.tags.extend(self.config.host_tags)
                    self.aggregator.submit(metric_point)
            
            # Flush aggregated metrics
            batch = self.aggregator.flush()
            if batch:
                await self.forwarder.send(batch)
            
            # Sleep until next collection interval
            elapsed = time.time() - collection_start
            await asyncio.sleep(max(0, self.config.collection_interval - elapsed))


class LocalAggregator:
    """
    Aggregate metrics locally before sending to reduce network traffic.
    Counters: sum over flush interval
    Gauges: keep last value (+ min/max/avg)
    Histograms: compute percentiles locally
    """
    
    def __init__(self, flush_interval=15):
        self.flush_interval = flush_interval
        self.metrics = defaultdict(lambda: defaultdict(list))
        self.counters = defaultdict(float)
    
    def submit(self, point):
        key = (point.metric, tuple(sorted(point.tags)))
        
        if point.type == 'counter':
            self.counters[key] += point.value
        elif point.type == 'gauge':
            self.metrics[key]['values'].append(point.value)
        elif point.type == 'histogram':
            self.metrics[key]['values'].append(point.value)
    
    def flush(self):
        """Flush aggregated metrics and reset."""
        batch = []
        timestamp = int(time.time())
        
        # Flush counters as rates
        for key, value in self.counters.items():
            metric, tags = key
            batch.append(MetricPoint(
                metric=metric,
                type='rate',
                value=value / self.flush_interval,
                timestamp=timestamp,
                tags=list(tags)
            ))
        
        # Flush gauges
        for key, data in self.metrics.items():
            metric, tags = key
            values = data['values']
            if values:
                batch.append(MetricPoint(
                    metric=metric,
                    type='gauge',
                    value=values[-1],  # Last value
                    timestamp=timestamp,
                    tags=list(tags)
                ))
        
        self.counters.clear()
        self.metrics.clear()
        return batch


class AutoDiscovery:
    """
    Auto-discover services running on the host via container labels/annotations.
    Watches Docker/Kubernetes for new containers and configures collectors.
    """
    
    ANNOTATION_PREFIX = "monitoring.io/"
    
    async def watch(self):
        """Watch for container events and configure collectors."""
        if self.config.container_runtime == 'docker':
            async for event in self.docker_client.events(filters={'type': 'container'}):
                await self._handle_container_event(event)
        elif self.config.container_runtime == 'containerd':
            async for event in self.cri_client.watch_pods():
                await self._handle_pod_event(event)
    
    async def _handle_container_event(self, event):
        if event['Action'] == 'start':
            container = await self.docker_client.inspect(event['id'])
            labels = container['Config']['Labels']
            
            # Check for monitoring annotations
            check_name = labels.get(f'{self.ANNOTATION_PREFIX}check')
            if check_name:
                config = {
                    'host': container['NetworkSettings']['IPAddress'],
                    'port': labels.get(f'{self.ANNOTATION_PREFIX}port'),
                    'tags': self._extract_tags(labels),
                }
                collector = COLLECTOR_REGISTRY[check_name](config)
                self.agent.add_collector(collector)
```

## 8. Database Schema

### Time-Series Storage (Custom Engine)

```sql
-- Metric metadata
CREATE TABLE metric_metadata (
    metric_id       BIGINT PRIMARY KEY AUTO_INCREMENT,
    metric_name     VARCHAR(512) NOT NULL,
    metric_type     ENUM('gauge', 'counter', 'rate', 'histogram') NOT NULL,
    unit            VARCHAR(64),
    description     TEXT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_seen_at    TIMESTAMP,
    tenant_id       BIGINT NOT NULL,
    UNIQUE INDEX idx_metric_tenant (tenant_id, metric_name)
);

-- Series (unique combination of metric + tags)
CREATE TABLE series (
    series_id       BIGINT PRIMARY KEY AUTO_INCREMENT,
    metric_id       BIGINT NOT NULL,
    tags_hash       BIGINT NOT NULL,  -- FNV hash of sorted tags
    tags_json       JSON NOT NULL,
    tenant_id       BIGINT NOT NULL,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_active_at  TIMESTAMP,
    UNIQUE INDEX idx_metric_tags (metric_id, tags_hash),
    INDEX idx_tenant (tenant_id),
    INDEX idx_last_active (last_active_at)
);

-- Tag inverted index (for fast label queries)
CREATE TABLE tag_postings (
    tag_key         VARCHAR(256) NOT NULL,
    tag_value       VARCHAR(1024) NOT NULL,
    series_id       BIGINT NOT NULL,
    tenant_id       BIGINT NOT NULL,
    PRIMARY KEY (tenant_id, tag_key, tag_value, series_id),
    INDEX idx_key_only (tenant_id, tag_key)
);

-- Chunk metadata (actual data in object storage / local SSDs)
CREATE TABLE chunks (
    chunk_id        BIGINT PRIMARY KEY AUTO_INCREMENT,
    series_id       BIGINT NOT NULL,
    start_time      BIGINT NOT NULL,  -- Unix epoch seconds
    end_time        BIGINT NOT NULL,
    point_count     INT NOT NULL,
    min_value       DOUBLE,
    max_value       DOUBLE,
    sum_value       DOUBLE,
    size_bytes      INT NOT NULL,
    storage_path    VARCHAR(512) NOT NULL,
    resolution      INT NOT NULL DEFAULT 15,  -- seconds between points
    INDEX idx_series_time (series_id, start_time, end_time),
    INDEX idx_resolution (resolution, start_time)
);

-- Rollup data (pre-aggregated)
CREATE TABLE rollups (
    series_id       BIGINT NOT NULL,
    timestamp       BIGINT NOT NULL,
    resolution      INT NOT NULL,  -- 60, 300, 3600
    min_value       DOUBLE,
    max_value       DOUBLE,
    avg_value       DOUBLE,
    sum_value       DOUBLE,
    count           INT,
    p50             DOUBLE,
    p95             DOUBLE,
    p99             DOUBLE,
    PRIMARY KEY (series_id, resolution, timestamp)
) PARTITION BY RANGE (timestamp);
```

### Dashboard and Monitor Storage (PostgreSQL)

```sql
CREATE TABLE dashboards (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       BIGINT NOT NULL,
    title           VARCHAR(256) NOT NULL,
    description     TEXT,
    layout_type     VARCHAR(32) DEFAULT 'ordered',
    widgets         JSONB NOT NULL DEFAULT '[]',
    tags            TEXT[] DEFAULT '{}',
    is_public       BOOLEAN DEFAULT FALSE,
    created_by      BIGINT NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    INDEX idx_tenant_dashboards (tenant_id),
    INDEX idx_tags (tags) USING GIN
);

CREATE TABLE monitors (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       BIGINT NOT NULL,
    name            VARCHAR(256) NOT NULL,
    type            VARCHAR(32) NOT NULL,  -- metric, anomaly, forecast, composite
    query           TEXT NOT NULL,
    message         TEXT,
    thresholds      JSONB NOT NULL,
    options         JSONB DEFAULT '{}',
    notification_targets JSONB DEFAULT '[]',
    tags            TEXT[] DEFAULT '{}',
    priority        SMALLINT DEFAULT 3,
    status          VARCHAR(32) DEFAULT 'OK',
    last_evaluated  TIMESTAMPTZ,
    created_by      BIGINT NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    INDEX idx_tenant_monitors (tenant_id),
    INDEX idx_status (status),
    INDEX idx_type (type)
);

CREATE TABLE monitor_state (
    monitor_id      UUID NOT NULL REFERENCES monitors(id),
    group_key       VARCHAR(512) NOT NULL,
    status          VARCHAR(32) NOT NULL,
    value           DOUBLE PRECISION,
    triggered_at    TIMESTAMPTZ,
    resolved_at     TIMESTAMPTZ,
    last_notified   TIMESTAMPTZ,
    PRIMARY KEY (monitor_id, group_key)
);

CREATE TABLE alert_events (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    monitor_id      UUID NOT NULL REFERENCES monitors(id),
    tenant_id       BIGINT NOT NULL,
    group_key       VARCHAR(512),
    status          VARCHAR(32) NOT NULL,
    value           DOUBLE PRECISION,
    message         TEXT,
    tags            JSONB,
    triggered_at    TIMESTAMPTZ NOT NULL,
    resolved_at     TIMESTAMPTZ,
    acknowledged_by BIGINT,
    acknowledged_at TIMESTAMPTZ,
    INDEX idx_monitor_events (monitor_id, triggered_at DESC),
    INDEX idx_tenant_events (tenant_id, triggered_at DESC)
);
```

## 9. Kafka & Redis Configuration

### Kafka Configuration

```yaml
# Kafka Topics
topics:
  metrics-raw:
    partitions: 256
    replication_factor: 3
    retention_ms: 3600000  # 1 hour (processing buffer)
    cleanup_policy: delete
    compression_type: zstd
    max_message_bytes: 1048576
    segment_bytes: 536870912

  metrics-aggregated:
    partitions: 128
    replication_factor: 3
    retention_ms: 86400000  # 24 hours
    cleanup_policy: delete
    compression_type: lz4

  alert-evaluations:
    partitions: 64
    replication_factor: 3
    retention_ms: 86400000
    cleanup_policy: delete

  alert-notifications:
    partitions: 32
    replication_factor: 3
    retention_ms: 604800000  # 7 days

# Producer config (Intake Gateway)
producer:
  acks: 1  # Leader ack only for throughput
  batch_size: 65536
  linger_ms: 10
  compression_type: zstd
  buffer_memory: 268435456  # 256MB
  max_in_flight_requests: 5
  retries: 3

# Consumer config (Aggregation Workers)
consumer:
  group_id: metrics-aggregation-workers
  auto_offset_reset: latest
  max_poll_records: 10000
  fetch_max_bytes: 52428800  # 50MB
  session_timeout_ms: 30000
  max_poll_interval_ms: 300000
```

### Redis Configuration

```yaml
# Redis Cluster for Alert State
redis:
  cluster:
    nodes: 6  # 3 masters + 3 replicas
    node_memory: 32GB
    maxmemory_policy: volatile-lru
  
  # Alert state keys
  key_patterns:
    monitor_state: "monitor:{monitor_id}:group:{group_key}"
    dedup: "dedup:{monitor_id}:{group_key}:{level}"
    evaluation_lock: "eval_lock:{monitor_id}"
    rate_limit: "rate:{tenant_id}:notifications"
  
  # TTL policies
  ttl:
    monitor_state: null  # Never expires
    dedup: 300  # 5 minutes (renotify interval)
    evaluation_lock: 60  # 1 minute
    rate_limit: 3600  # 1 hour window

  # Lua scripts for atomic operations
  scripts:
    check_and_transition: |
      local current = redis.call('HGET', KEYS[1], 'status')
      local new_status = ARGV[1]
      local timestamp = ARGV[2]
      if current ~= new_status then
        redis.call('HSET', KEYS[1], 'status', new_status, 'transitioned_at', timestamp, 'prev_status', current)
        return {current, new_status, 1}  -- transition occurred
      end
      return {current, new_status, 0}  -- no transition
```

## 10. Scalability & Performance

### Write Path Optimization
- **Intake sharding**: Hash metrics by series ID to partition across Kafka
- **Batch compression**: Agent batches 1000 points with zstd before sending
- **WAL for durability**: Write-ahead log on TSDB nodes before memory buffer
- **Async indexing**: Index updates queued separately from data writes

### Query Path Optimization
- **Query fan-out**: Distribute query across TSDB nodes owning relevant series
- **Chunk skip index**: Min/max per chunk enables skipping irrelevant chunks
- **Query caching**: Cache recent dashboard queries in Redis (15s TTL)
- **Pre-aggregation**: Hot dashboards trigger pre-computation of results

### Alert Evaluation Scaling
- **Partitioned evaluation**: Monitors assigned to evaluator nodes via consistent hash
- **Staggered scheduling**: Spread evaluations across the minute to avoid thundering herd
- **Priority queues**: P1 monitors evaluated every 15s, P5 every 5 minutes

### Capacity Planning
```
10M metrics/sec ingestion:
- Kafka: 256 partitions × 40K msg/sec/partition = 10.2M msg/sec
- TSDB nodes: 50 nodes × 200K writes/sec = 10M writes/sec
- Storage: 10M series × 4 points/min × 16 bytes × (1 / 12 compression) = ~90 GB/day raw
- Alert evaluators: 100K monitors / 50 nodes = 2K monitors/node, ~30ms each = 60s cycle
```

## 11. Failure Handling & Reliability

### Agent Failure
- Local disk buffer: queue metrics during network outages (up to 4 hours)
- Automatic retry with exponential backoff
- Health endpoint for orchestrator monitoring

### TSDB Node Failure
- Replication factor 2: each series written to 2 nodes
- Automatic re-replication on node loss
- Query routes around failed nodes using replicas

### Alert Pipeline Reliability
- Kafka provides durability for alert evaluation queue
- Redis sentinel for alert state failover
- Dead letter queue for failed notifications
- Heartbeat monitors: alert if evaluator stops running

### Data Consistency
- Eventual consistency for metrics (acceptable for monitoring)
- Strong consistency for alert state (Redis cluster with WAIT)
- Idempotent metric writes (same timestamp + series = overwrite)

### Disaster Recovery
- Cross-region Kafka MirrorMaker for critical alert topics
- TSDB snapshots to object storage every 6 hours
- Alert configuration replicated to standby region
- RTO: 5 minutes for alerting, 30 minutes for full dashboard access
