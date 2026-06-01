# Multi-database Synchronization (Polyglot Persistence)

## Problem Statement

Modern applications use multiple databases optimized for different access patterns: PostgreSQL for transactions, MongoDB for flexible documents, Elasticsearch for search, Redis for caching, Neo4j for graph queries. The challenge: when a product is updated in the source of truth (PostgreSQL), that change must propagate to all derived stores consistently, in order, handling partial failures where some stores update but others don't, without losing data or creating permanent divergence across 5+ database technologies.

## Architecture Diagram

```mermaid
graph TB
    subgraph "Source of Truth"
        PG[(PostgreSQL<br/>Primary Store)]
        APP[Application<br/>Service]
    end

    subgraph "CDC Layer"
        DBZ[Debezium<br/>PostgreSQL Connector]
    end

    subgraph "Kafka"
        T_CDC[cdc.products]
        T_CDC2[cdc.orders]
        T_FANOUT[fanout.products.enriched]
    end

    subgraph "Fan-out Service"
        ROUTER[Event Router<br/>+ Transformer]
        
        subgraph "Sink Connectors"
            S_MONGO[MongoDB Sink]
            S_ES[Elasticsearch Sink]
            S_REDIS[Redis Sink]
            S_NEO4J[Neo4j Sink]
            S_DYNAMO[DynamoDB Sink]
        end
    end

    subgraph "Derived Stores"
        MONGO[(MongoDB<br/>Product Catalog<br/>Flexible queries)]
        ES[(Elasticsearch<br/>Full-text search)]
        REDIS[Redis<br/>Cache + Sessions]
        NEO4J[(Neo4j<br/>Recommendations)]
        DYNAMO[(DynamoDB<br/>High-throughput reads)]
    end

    subgraph "Reconciliation"
        RECON[Reconciliation<br/>Job (hourly)]
        REPAIR[Auto-repair<br/>Service]
        DASH[Sync Health<br/>Dashboard]
    end

    APP --> PG
    PG --> DBZ
    DBZ --> T_CDC

    T_CDC --> ROUTER
    ROUTER --> T_FANOUT

    T_FANOUT --> S_MONGO --> MONGO
    T_FANOUT --> S_ES --> ES
    T_FANOUT --> S_REDIS --> REDIS
    T_FANOUT --> S_NEO4J --> NEO4J
    T_FANOUT --> S_DYNAMO --> DYNAMO

    RECON --> PG
    RECON --> MONGO
    RECON --> ES
    RECON --> REDIS
    RECON --> DASH
    REPAIR --> MONGO
    REPAIR --> ES
```

## Component Breakdown

### Fan-out Router and Transformer

```python
class FanoutRouter:
    """
    Routes CDC events to multiple sink connectors.
    Each sink may need different transformation.
    """
    
    def __init__(self):
        self.sinks = {
            'mongodb': MongoDBTransformer(),
            'elasticsearch': ElasticsearchTransformer(),
            'redis': RedisTransformer(),
            'neo4j': Neo4jTransformer(),
            'dynamodb': DynamoDBTransformer(),
        }
    
    def route(self, cdc_event: dict):
        table = cdc_event['source']['table']
        op = cdc_event['op']  # c=create, u=update, d=delete
        
        # Determine which sinks need this event
        routing = ROUTING_CONFIG[table]
        
        for sink_name in routing['sinks']:
            transformer = self.sinks[sink_name]
            try:
                transformed = transformer.transform(cdc_event)
                self.publish_to_sink(sink_name, transformed)
            except TransformError as e:
                self.send_to_dlq(sink_name, cdc_event, str(e))


class ElasticsearchTransformer:
    """Transform relational row to ES document"""
    
    def transform(self, event: dict) -> dict:
        if event['op'] == 'd':
            return {'_op': 'delete', '_id': event['before']['id']}
        
        row = event['after']
        return {
            '_op': 'index',
            '_id': row['id'],
            '_index': 'products',
            'doc': {
                'product_id': row['id'],
                'title': row['title'],
                'description': row['description'],
                'price': float(row['price']),
                'category': row['category_name'],
                'brand': row['brand'],
                'in_stock': row['stock_quantity'] > 0,
                'search_keywords': self._extract_keywords(row),
                'updated_at': event['source']['ts_ms']
            }
        }


class Neo4jTransformer:
    """Transform to graph operations"""
    
    def transform(self, event: dict) -> dict:
        row = event['after'] or event['before']
        table = event['source']['table']
        
        if table == 'products':
            return {
                '_op': 'merge_node',
                'label': 'Product',
                'key': {'product_id': row['id']},
                'properties': {
                    'title': row['title'],
                    'price': float(row['price']),
                    'category_id': row['category_id']
                }
            }
        elif table == 'order_items':
            return {
                '_op': 'merge_relationship',
                'type': 'PURCHASED',
                'start': {'label': 'Customer', 'key': {'customer_id': row['customer_id']}},
                'end': {'label': 'Product', 'key': {'product_id': row['product_id']}},
                'properties': {'quantity': row['quantity'], 'order_date': row['created_at']}
            }


class RedisTransformer:
    """Transform to Redis commands"""
    
    def transform(self, event: dict) -> dict:
        row = event['after'] or event['before']
        table = event['source']['table']
        
        if event['op'] == 'd':
            return {'_op': 'DEL', 'key': f"product:{row['id']}"}
        
        return {
            '_op': 'HSET',
            'key': f"product:{row['id']}",
            'fields': {
                'title': row['title'],
                'price': str(row['price']),
                'stock': str(row['stock_quantity']),
                'category': row['category_name'],
            },
            'ttl': 3600  # 1 hour TTL
        }
```

### Ordering Guarantees

```python
class OrderingGuaranteeManager:
    """
    Ensures events for the same entity are processed in order
    across all sink connectors.
    
    Strategy: Partition by entity ID in Kafka, 
    each sink processes partitions sequentially.
    """
    
    # Kafka topic configuration
    TOPIC_CONFIG = {
        'fanout.products.enriched': {
            'partitions': 24,
            'partition_key': 'product_id',  # Same product always same partition
            'replication_factor': 3,
        }
    }
    
    # Per-sink consumer configuration
    SINK_CONFIGS = {
        'elasticsearch': {
            'consumer_group': 'sink-elasticsearch',
            'concurrency': 24,  # 1 thread per partition = ordered
            'batch_size': 500,
            'linger_ms': 100,
        },
        'mongodb': {
            'consumer_group': 'sink-mongodb',
            'concurrency': 24,
            'batch_size': 1000,
            'linger_ms': 200,
        },
        'redis': {
            'consumer_group': 'sink-redis',
            'concurrency': 24,
            'batch_size': 2000,
            'linger_ms': 50,
        }
    }
```

### Partial Failure Handling

```python
class PartialFailureHandler:
    """
    When one sink fails but others succeed, we need to:
    1. Not block other sinks
    2. Retry the failed sink
    3. Track which sinks are behind
    4. Eventually repair divergence
    """
    
    def __init__(self):
        self.sink_status = {}  # Track per-sink health
    
    async def process_event(self, event: dict, sinks: list):
        results = {}
        
        for sink in sinks:
            try:
                if self.sink_status.get(sink, {}).get('circuit_open'):
                    # Circuit breaker open - skip, will be repaired later
                    results[sink] = 'skipped'
                    continue
                
                await self.write_to_sink(sink, event)
                results[sink] = 'success'
                self._record_success(sink)
                
            except Exception as e:
                results[sink] = f'failed: {e}'
                self._record_failure(sink, event, e)
                
                # Don't block other sinks
                # Failed event goes to per-sink retry queue
                await self.retry_queue.put(sink, event)
        
        return results
    
    def _record_failure(self, sink: str, event: dict, error: Exception):
        status = self.sink_status.setdefault(sink, {'failures': 0, 'last_failure': None})
        status['failures'] += 1
        status['last_failure'] = datetime.utcnow()
        
        # Open circuit breaker after 10 consecutive failures
        if status['failures'] >= 10:
            status['circuit_open'] = True
            status['circuit_open_until'] = datetime.utcnow() + timedelta(seconds=30)
            self.alert(f"Circuit breaker opened for sink: {sink}")
    
    def _record_success(self, sink: str):
        if sink in self.sink_status:
            self.sink_status[sink]['failures'] = 0
            self.sink_status[sink]['circuit_open'] = False
```

### Reconciliation Engine

```python
class ReconciliationEngine:
    """
    Periodically verifies all derived stores match source of truth.
    Repairs detected drift automatically.
    """
    
    def __init__(self, source_db, sinks: dict):
        self.source = source_db
        self.sinks = sinks
    
    async def run_reconciliation(self, table: str, batch_size: int = 10000):
        """Full reconciliation - runs hourly for critical tables"""
        
        total_checked = 0
        total_drift = 0
        
        # Stream through source in batches
        async for batch in self.source.stream_table(table, batch_size):
            for sink_name, sink in self.sinks.items():
                drift = await self._check_batch(sink_name, sink, table, batch)
                total_drift += len(drift)
                
                if drift:
                    await self._repair_drift(sink_name, sink, drift)
            
            total_checked += len(batch)
        
        self.metrics.gauge(f'reconciliation.{table}.checked', total_checked)
        self.metrics.gauge(f'reconciliation.{table}.drift', total_drift)
        
        # Check for orphans in derived stores (deleted from source)
        await self._check_orphans(table)
    
    async def _check_batch(self, sink_name: str, sink, table: str, source_batch: list):
        """Compare source batch against sink"""
        ids = [row['id'] for row in source_batch]
        sink_records = await sink.get_batch(table, ids)
        
        drift = []
        for source_row in source_batch:
            sink_row = sink_records.get(source_row['id'])
            
            if sink_row is None:
                drift.append({'type': 'missing', 'id': source_row['id'], 'source': source_row})
            elif not self._records_match(source_row, sink_row, sink_name):
                drift.append({'type': 'mismatch', 'id': source_row['id'], 
                            'source': source_row, 'sink': sink_row})
        
        return drift
    
    async def _repair_drift(self, sink_name: str, sink, drift: list):
        """Automatically repair detected drift"""
        for item in drift:
            if item['type'] == 'missing':
                await sink.upsert(item['source'])
                self.metrics.increment(f'reconciliation.repair.{sink_name}.missing')
            elif item['type'] == 'mismatch':
                await sink.upsert(item['source'])
                self.metrics.increment(f'reconciliation.repair.{sink_name}.mismatch')
```

## Data Flow

```
Write Path (Single Source of Truth):
1. Application writes ONLY to PostgreSQL
2. Debezium captures WAL change
3. Published to Kafka CDC topic
4. Fan-out router transforms per sink
5. Each sink connector writes independently
6. Consumer offsets committed per sink

Read Path (Polyglot reads):
- Transactional queries → PostgreSQL
- Full-text search → Elasticsearch
- Product catalog browse → MongoDB
- Recommendations → Neo4j
- Cache/fast lookups → Redis/DynamoDB

Reconciliation (Hourly):
1. Stream source of truth in batches
2. Compare against each derived store
3. Auto-repair detected drift
4. Report metrics to dashboard
```

## Scaling Strategies

| Sink | Throughput | Batch Strategy |
|------|-----------|----------------|
| PostgreSQL (source) | N/A (origin) | N/A |
| MongoDB | 50K writes/sec | Bulk upsert, batch 1000 |
| Elasticsearch | 30K docs/sec | Bulk API, batch 500 |
| Redis | 200K ops/sec | Pipeline, batch 2000 |
| Neo4j | 10K writes/sec | Batch Cypher, batch 500 |
| DynamoDB | 40K WCU | BatchWriteItem, batch 25 |

### Consumer Group Isolation
```
Each sink has its own Kafka consumer group:
- sink-mongodb (24 consumers)
- sink-elasticsearch (24 consumers)
- sink-redis (12 consumers)
- sink-neo4j (6 consumers)
- sink-dynamodb (12 consumers)

Benefits:
- Independent scaling
- One slow sink doesn't block others
- Independent retry/failure handling
- Per-sink lag monitoring
```

## Failure Handling

| Failure | Impact | Resolution |
|---------|--------|------------|
| Single sink down | One derived store stale | Circuit breaker, retry queue, catch up when restored |
| Source DB down | No new changes | All sinks pause, resume on recovery |
| Kafka down | All sinks stall | Resume from last committed offset |
| Sink schema mismatch | Write rejections | DLQ + alert, fix transformer |
| Data corruption in sink | Incorrect query results | Reconciliation detects + repairs |
| Network partition | Subset of sinks affected | Independent per-sink handling |

### Sink Health Dashboard Metrics
```yaml
per_sink_metrics:
  - consumer_lag_events: "How far behind source"
  - write_latency_p99_ms: "Sink write performance"
  - error_rate_percent: "Failed writes / total"
  - circuit_breaker_status: "open/closed"
  - last_successful_write: "Timestamp"
  - reconciliation_drift_count: "Records out of sync"
```

## Cost Optimization

| Component | Monthly Cost | Notes |
|-----------|-------------|-------|
| PostgreSQL (source) | ~$2,000 | Already exists |
| Kafka + CDC | ~$3,000 | Shared infrastructure |
| MongoDB (derived) | ~$2,000 | Atlas M30 |
| Elasticsearch | ~$4,000 | 6 data nodes |
| Redis | ~$1,200 | ElastiCache |
| Neo4j | ~$1,500 | Aura Professional |
| DynamoDB | ~$800 | On-demand |
| Fan-out workers | ~$1,000 | 4x m5.large |
| Reconciliation | ~$200 | Spot, hourly |
| **Total** | **~$15,700/month** | Full polyglot stack |

### When NOT to Use Polyglot
```
Avoid if:
- Single database can serve all query patterns adequately
- Team doesn't have expertise in multiple databases
- Data volume < 10M records (PostgreSQL can handle it all)
- Eventual consistency is unacceptable for ALL read patterns
- Operational overhead of 5+ databases exceeds benefit
```

## Real-World Companies

| Company | Polyglot Stack | Pattern |
|---------|---------------|---------|
| **Uber** | MySQL + Cassandra + ES + Redis | CDC-based sync |
| **Netflix** | Cassandra + ES + EVCache + S3 | Change events |
| **LinkedIn** | Espresso + Voldemort + ES | Brooklin CDC |
| **Airbnb** | MySQL + ES + Redis + HBase | Event-driven sync |
| **Shopify** | MySQL + ES + Redis + Memcached | CDC pipeline |
| **Pinterest** | MySQL + HBase + ES + Redis | Multi-store sync |
| **Twitter** | Manhattan + ES + Redis + HDFS | Fan-out on write |
