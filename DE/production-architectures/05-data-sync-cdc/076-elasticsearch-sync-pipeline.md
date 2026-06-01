# Database to Elasticsearch Sync (E-commerce/Search)

## Problem Statement

E-commerce platforms store product data across multiple normalized tables (products, inventory, pricing, reviews, seller info). Search requires denormalized documents combining all these sources into a single Elasticsearch document. At scale with 100M+ products, 10K+ price changes/minute, and real-time inventory updates, maintaining search index freshness while handling schema evolution and zero-downtime reindexing is critical for revenue—stale search results directly impact conversion rates.

## Architecture Diagram

```mermaid
graph TB
    subgraph "Source Databases"
        PG_PROD[(PostgreSQL<br/>Products + Categories)]
        PG_INV[(PostgreSQL<br/>Inventory)]
        MY_PRICE[(MySQL<br/>Pricing Engine)]
        MONGO_REV[(MongoDB<br/>Reviews)]
        REDIS_POP[Redis<br/>Popularity Scores]
    end

    subgraph "CDC Layer"
        CDC1[Debezium PG<br/>Products]
        CDC2[Debezium PG<br/>Inventory]
        CDC3[Debezium MySQL<br/>Pricing]
        CDC4[MongoDB<br/>Change Streams]
    end

    subgraph "Kafka"
        T_PROD[cdc.products]
        T_INV[cdc.inventory]
        T_PRICE[cdc.pricing]
        T_REV[cdc.reviews]
        T_ENRICH[enriched.products]
    end

    subgraph "Stream Processing (Flink)"
        JOIN[Multi-stream Join<br/>+ Denormalization]
        PARTIAL[Partial Update<br/>Builder]
        BUFFER[Rate Limiter<br/>+ Dedup Buffer]
    end

    subgraph "Elasticsearch"
        ES1[ES Cluster<br/>products-v2 (active)]
        ES2[ES Cluster<br/>products-v3 (reindex)]
        ALIAS[Index Alias<br/>products-read]
    end

    subgraph "Orchestration"
        REINDEX[Reindex<br/>Coordinator]
        HEALTH[Health Checker]
        SWITCH[Alias Switcher]
    end

    PG_PROD --> CDC1
    PG_INV --> CDC2
    MY_PRICE --> CDC3
    MONGO_REV --> CDC4

    CDC1 --> T_PROD
    CDC2 --> T_INV
    CDC3 --> T_PRICE
    CDC4 --> T_REV

    T_PROD --> JOIN
    T_INV --> PARTIAL
    T_PRICE --> PARTIAL
    T_REV --> JOIN

    JOIN --> T_ENRICH
    T_ENRICH --> BUFFER
    PARTIAL --> BUFFER

    BUFFER --> ES1
    REINDEX --> ES2
    ES1 --> ALIAS
    ES2 --> ALIAS
    HEALTH --> SWITCH
    SWITCH --> ALIAS
```

## Component Breakdown

### Denormalized Document Model

```json
{
  "product_id": "P-12345678",
  "title": "Wireless Noise Canceling Headphones",
  "description": "Premium over-ear headphones with 30hr battery...",
  "brand": "AudioTech",
  "category": {
    "id": "cat-electronics-audio",
    "name": "Headphones",
    "path": ["Electronics", "Audio", "Headphones"],
    "level": 3
  },
  "seller": {
    "id": "seller-789",
    "name": "AudioTech Official Store",
    "rating": 4.8,
    "verified": true
  },
  "pricing": {
    "current_price": 299.99,
    "original_price": 399.99,
    "currency": "USD",
    "discount_percent": 25,
    "price_updated_at": "2024-01-15T10:30:00Z"
  },
  "inventory": {
    "in_stock": true,
    "quantity": 1523,
    "warehouse_availability": ["us-east", "us-west", "eu-central"],
    "low_stock": false,
    "updated_at": "2024-01-15T10:31:00Z"
  },
  "reviews": {
    "average_rating": 4.6,
    "total_count": 2847,
    "rating_distribution": {"5": 1800, "4": 700, "3": 200, "2": 100, "1": 47}
  },
  "attributes": {
    "color": ["Black", "Silver", "Blue"],
    "connectivity": "Bluetooth 5.3",
    "battery_life_hours": 30,
    "noise_canceling": true,
    "weight_grams": 250
  },
  "search_keywords": ["wireless headphones", "noise canceling", "bluetooth headphones"],
  "popularity_score": 0.89,
  "created_at": "2023-06-15T00:00:00Z",
  "updated_at": "2024-01-15T10:31:00Z",
  "_sync_metadata": {
    "last_full_sync": "2024-01-15T00:00:00Z",
    "last_partial_update": "2024-01-15T10:31:00Z",
    "version": 42
  }
}
```

### Multi-Stream Join (Flink)

```sql
-- Flink SQL: Join product changes with latest inventory and pricing

-- Product CDC stream
CREATE TABLE cdc_products (
    product_id STRING,
    title STRING,
    description STRING,
    brand STRING,
    category_id STRING,
    seller_id STRING,
    attributes MAP<STRING, STRING>,
    updated_at TIMESTAMP(3),
    proc_time AS PROCTIME()
) WITH (
    'connector' = 'kafka',
    'topic' = 'cdc.products',
    'format' = 'debezium-json'
);

-- Inventory as a continuously updated table (latest per product)
CREATE TABLE inventory_latest (
    product_id STRING,
    quantity INT,
    warehouses ARRAY<STRING>,
    updated_at TIMESTAMP(3),
    PRIMARY KEY (product_id) NOT ENFORCED
) WITH (
    'connector' = 'upsert-kafka',
    'topic' = 'cdc.inventory.compacted',
    'key.format' = 'json',
    'value.format' = 'json'
);

-- Pricing as temporal table
CREATE TABLE pricing_latest (
    product_id STRING,
    current_price DECIMAL(10, 2),
    original_price DECIMAL(10, 2),
    currency STRING,
    updated_at TIMESTAMP(3),
    PRIMARY KEY (product_id) NOT ENFORCED
) WITH (
    'connector' = 'upsert-kafka',
    'topic' = 'cdc.pricing.compacted',
    'key.format' = 'json',
    'value.format' = 'json'
);

-- Enriched product document
INSERT INTO enriched_products
SELECT
    p.product_id,
    p.title,
    p.description,
    p.brand,
    p.category_id,
    p.seller_id,
    p.attributes,
    i.quantity,
    i.warehouses,
    pr.current_price,
    pr.original_price,
    pr.currency,
    CURRENT_TIMESTAMP as enriched_at
FROM cdc_products p
LEFT JOIN inventory_latest FOR SYSTEM_TIME AS OF p.proc_time AS i
    ON p.product_id = i.product_id
LEFT JOIN pricing_latest FOR SYSTEM_TIME AS OF p.proc_time AS pr
    ON p.product_id = pr.product_id;
```

### Partial Update Strategy

```python
class ElasticsearchPartialUpdater:
    """
    For high-frequency changes (inventory, pricing), use partial updates
    instead of full document reindex to reduce ES load.
    """
    
    def __init__(self, es_client, buffer_config):
        self.es = es_client
        self.buffer = UpdateBuffer(
            max_size=1000,
            max_wait_ms=500,
            dedup_key='product_id'
        )
    
    async def handle_inventory_change(self, event: dict):
        product_id = event['product_id']
        
        partial_doc = {
            'inventory': {
                'in_stock': event['quantity'] > 0,
                'quantity': event['quantity'],
                'low_stock': event['quantity'] < 10,
                'updated_at': event['updated_at']
            },
            'updated_at': event['updated_at']
        }
        
        await self.buffer.add(product_id, partial_doc)
    
    async def handle_price_change(self, event: dict):
        product_id = event['product_id']
        discount = round((1 - event['current_price'] / event['original_price']) * 100)
        
        partial_doc = {
            'pricing': {
                'current_price': event['current_price'],
                'original_price': event['original_price'],
                'discount_percent': max(0, discount),
                'price_updated_at': event['updated_at']
            },
            'updated_at': event['updated_at']
        }
        
        await self.buffer.add(product_id, partial_doc)
    
    async def flush_buffer(self, updates: dict):
        """Bulk partial update to ES"""
        body = []
        for product_id, partial_doc in updates.items():
            body.append({'update': {'_index': 'products-v2', '_id': product_id}})
            body.append({
                'doc': partial_doc,
                'doc_as_upsert': False,  # Don't create if missing
                'retry_on_conflict': 3
            })
        
        response = await self.es.bulk(body=body, refresh='false')
        
        # Handle failures
        if response['errors']:
            for item in response['items']:
                if 'error' in item.get('update', {}):
                    error = item['update']['error']
                    if error['type'] == 'document_missing_exception':
                        # Trigger full document rebuild
                        await self.trigger_full_reindex(item['update']['_id'])
                    else:
                        await self.send_to_dlq(item)
```

### Zero-Downtime Reindexing

```python
class ZeroDowntimeReindexer:
    """
    Reindex entire index without search downtime.
    Uses alias switching pattern.
    """
    
    def __init__(self, es_client, kafka_consumer):
        self.es = es_client
        self.read_alias = 'products-read'
        self.write_alias = 'products-write'
    
    async def reindex(self, new_mapping: dict):
        current_index = await self._get_index_behind_alias(self.read_alias)
        new_version = self._next_version(current_index)
        new_index = f"products-{new_version}"
        
        # Step 1: Create new index with new mapping
        await self.es.indices.create(index=new_index, body={
            'settings': self._get_settings(),
            'mappings': new_mapping
        })
        
        # Step 2: Start CDC consumer writing to BOTH indices
        await self._add_alias(new_index, self.write_alias)
        # Now writes go to both old and new index
        
        # Step 3: Bulk reindex from source (not from old ES index)
        await self._bulk_reindex_from_source(new_index)
        
        # Step 4: Wait for new index to catch up with CDC stream
        await self._wait_for_convergence(new_index, current_index)
        
        # Step 5: Atomic alias switch
        await self.es.indices.update_aliases(body={
            'actions': [
                {'remove': {'index': current_index, 'alias': self.read_alias}},
                {'add': {'index': new_index, 'alias': self.read_alias}},
                {'remove': {'index': current_index, 'alias': self.write_alias}}
            ]
        })
        
        # Step 6: Verify new index serving correctly
        await self._verify_search_quality(new_index)
        
        # Step 7: Delete old index (after grace period)
        await asyncio.sleep(3600)  # 1 hour grace period
        await self.es.indices.delete(index=current_index)
    
    def _get_settings(self):
        return {
            'number_of_shards': 12,
            'number_of_replicas': 1,
            'refresh_interval': '1s',
            'translog.durability': 'async',
            'translog.sync_interval': '5s',
            'merge.scheduler.max_thread_count': 4,
            'codec': 'best_compression'
        }
```

## Data Flow

```
Full Document Update (product metadata change):
1. Product table updated in PostgreSQL
2. Debezium captures change → cdc.products topic
3. Flink joins with latest inventory + pricing (temporal join)
4. Full enriched document built
5. Buffered (dedup within 500ms window)
6. Bulk indexed to Elasticsearch

Partial Update (inventory/price change):
1. Inventory/price updated in source DB
2. CDC captures → cdc.inventory / cdc.pricing
3. Partial update builder creates minimal doc
4. Buffered and deduped (latest wins per product_id)
5. Bulk _update API to Elasticsearch
6. Only changed fields updated (no full reindex)

Latency targets:
- Price change → search reflects: < 3 seconds
- Inventory change → stock status: < 2 seconds  
- New product → searchable: < 10 seconds
```

## Scaling Strategies

### Elasticsearch Cluster Sizing (100M products)
```yaml
cluster:
  data_nodes: 12
  instance_type: r6g.2xlarge  # 64GB RAM, 8 vCPU
  storage_per_node: 1TB gp3
  
  # Index configuration
  primary_shards: 12          # 1 per data node
  replica_shards: 1           # Total 24 shards
  avg_doc_size: 5KB
  total_index_size: ~500GB    # 100M × 5KB
  per_shard_size: ~42GB       # 500GB / 12 shards
  
  # Write throughput
  bulk_size: 1000 docs
  bulk_concurrent: 4 per node
  refresh_interval: 1s
  sustained_indexing: 50K docs/sec

  # Search performance
  query_latency_p50: 15ms
  query_latency_p99: 100ms
  search_concurrency: 500 queries/sec
```

### Write Optimization
```json
{
  "index.refresh_interval": "1s",
  "index.translog.durability": "async",
  "index.translog.sync_interval": "5s",
  "index.number_of_replicas": 0,
  "indices.memory.index_buffer_size": "20%"
}
```

## Failure Handling

| Failure | Detection | Recovery |
|---------|-----------|----------|
| ES node down | Cluster health yellow/red | Replicas serve reads, reassign shards |
| Bulk rejection | 429 responses | Exponential backoff, reduce batch size |
| Document conflict | Version conflict exception | Retry with latest version |
| CDC lag | Consumer lag metric | Scale workers, alert |
| Mapping explosion | Field limit exceeded | Strict mapping, reject unknown fields |
| Reindex failure | Progress stalls | Resume from checkpoint, not restart |

### Consistency Verification
```python
class SearchConsistencyChecker:
    """Periodic check that search reflects source of truth"""
    
    def run_hourly(self):
        # Sample 1000 random products
        sample_ids = self.db.execute(
            "SELECT id FROM products ORDER BY RANDOM() LIMIT 1000"
        )
        
        for product_id in sample_ids:
            db_record = self.db.get_product(product_id)
            es_record = self.es.get(index='products-read', id=product_id)
            
            # Check critical fields
            if db_record['price'] != es_record['pricing']['current_price']:
                self.metrics.increment('search_price_mismatch')
                self.trigger_reindex(product_id)
            
            if db_record['in_stock'] != es_record['inventory']['in_stock']:
                self.metrics.increment('search_stock_mismatch')
                self.trigger_reindex(product_id)
```

## Cost Optimization

| Component | Monthly Cost | Notes |
|-----------|-------------|-------|
| ES Cluster (12+12 nodes) | ~$12,000 | r6g.2xlarge + 1TB gp3 |
| Flink (enrichment) | ~$2,400 | 4x m5.xlarge |
| Kafka (CDC topics) | Shared | Part of CDC infra |
| Reindex compute | ~$500 | Spot, monthly |
| **Total** | **~$14,900/month** | 100M products, real-time sync |

### Optimization Tips
```
1. Partial updates for high-frequency changes (save 80% ES write load)
2. Source filtering: only store searchable fields in ES
3. Disable _source for large fields, use stored fields selectively
4. Use force_merge for read-only historical indices
5. ILM: hot-warm-cold for time-based product indices
6. Reduce replica count during bulk reindex, restore after
```

## Real-World Companies

| Company | Scale | Approach |
|---------|-------|----------|
| **Amazon** | Billions of products | Custom search infra + real-time sync |
| **eBay** | 1.5B+ listings | Kafka CDC → Elasticsearch |
| **Shopify** | 100M+ products | Debezium → Kafka → ES |
| **Zalando** | 50M+ articles | CDC-based search sync |
| **Walmart** | 200M+ items | Kafka Streams → ES |
| **Etsy** | 100M+ listings | Real-time search indexing |
| **Instacart** | Inventory-aware search | CDC → real-time stock in search |
