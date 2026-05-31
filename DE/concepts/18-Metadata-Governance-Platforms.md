# Metadata and Governance Platforms

## 1. Metadata Fundamentals

### What is Metadata?

Metadata is "data about data" — the contextual information that makes raw data discoverable,
understandable, trustworthy, and governable. In modern data platforms, metadata is the connective
tissue between producers, consumers, and stewards.

### Categories of Metadata

#### Technical Metadata
- Schema definitions (column names, types, constraints)
- Table/file locations, partitioning schemes
- Storage format (Parquet, ORC, Avro, Delta)
- Database connection strings, catalog references
- Indexes, primary/foreign keys, sort orders
- Serialization/deserialization properties

#### Business Metadata
- Human-readable descriptions and documentation
- Business glossary terms and definitions
- Data ownership and stewardship assignments
- Classification labels (PII, PHI, financial)
- Data quality SLAs and expectations
- Business domain mappings

#### Operational Metadata
- Pipeline execution history (start, end, status, duration)
- Row counts, byte sizes per run
- Data freshness timestamps (last updated)
- Error logs and failure reasons
- Resource consumption (CPU, memory, I/O)
- Cost attribution per dataset/pipeline

### Active vs Passive Metadata

```
┌─────────────────────────────────────────────────────────┐
│                    ACTIVE METADATA                        │
│                                                          │
│  Metadata that DRIVES automation and decisions:          │
│  - Auto-classify PII → trigger masking                  │
│  - Freshness SLA breach → alert on-call                 │
│  - Schema change detected → notify downstream           │
│  - Lineage shows impact → block breaking change         │
│  - Quality score drops → quarantine dataset             │
│                                                          │
├─────────────────────────────────────────────────────────┤
│                   PASSIVE METADATA                        │
│                                                          │
│  Metadata for human consumption (catalog/search):        │
│  - Descriptions, tags, glossary terms                    │
│  - Ownership information                                 │
│  - Documentation links                                   │
│  - Usage statistics (who queried what)                   │
│  - Data previews and samples                             │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

### Metadata Graph Model

Modern metadata platforms model metadata as a **property graph**:

```
┌──────────┐     produces      ┌──────────┐     consumed_by    ┌──────────┐
│  Pipeline │─────────────────▶│  Dataset  │◀──────────────────│  Dashboard│
│  (Job)   │                   │  (Table)  │                   │  (Chart) │
└──────────┘                   └──────────┘                    └──────────┘
      │                              │                               │
      │ owned_by                     │ has_schema                    │ owned_by
      ▼                              ▼                               ▼
┌──────────┐                   ┌──────────┐                    ┌──────────┐
│   Team   │                   │  Schema  │                    │   Team   │
│  (Group) │                   │ (Fields) │                    │  (Group) │
└──────────┘                   └──────────┘                    └──────────┘
                                     │
                                     │ classified_as
                                     ▼
                               ┌──────────┐
                               │   Tag    │
                               │  (PII)   │
                               └──────────┘
```

Key relationships in the graph:
- **Lineage edges**: upstream → downstream data flow
- **Ownership edges**: dataset → team/person
- **Schema edges**: dataset → columns → types
- **Classification edges**: column → tag/glossary term
- **Dependency edges**: pipeline → input datasets

### The Metadata Platform Landscape

```
┌────────────────────────────────────────────────────────────────┐
│                     METADATA PLATFORMS                           │
├────────────────┬───────────────┬───────────────┬───────────────┤
│    DataHub     │ OpenMetadata  │  Apache Atlas │   Amundsen    │
│  (LinkedIn)   │  (Collate)    │   (Hortonworks)│  (Lyft)      │
├────────────────┼───────────────┼───────────────┼───────────────┤
│  Full-featured │  All-in-one   │  Hadoop-era   │  Search-first │
│  Extensible    │  Built-in     │  Type system  │  Simple       │
│  Stream-first  │  profiling    │  HBase/Solr   │  Neo4j+ES    │
│  GraphQL API   │  Airflow      │  Ranger integ │  Flask app   │
└────────────────┴───────────────┴───────────────┴───────────────┤
│                                                                 │
│                     LINEAGE SYSTEMS                              │
├────────────────┬───────────────┬───────────────────────────────┤
│    Marquez     │  OpenLineage  │  Egeria (ODPi)                │
│  (WeWork/LF)  │  (Standard)   │  (ING/IBM)                    │
├────────────────┼───────────────┼───────────────────────────────┤
│  Lineage store │  Spec/SDK     │  Enterprise governance        │
│  HTTP API      │  Event format │  Distributed catalogs         │
│  Airflow integ │  Multi-vendor │  Type system                  │
└────────────────┴───────────────┴───────────────────────────────┘
│                                                                 │
│                     CATALOG / VERSIONING                         │
├────────────────┬───────────────┬───────────────────────────────┤
│ Project Nessie │  AWS Glue     │  Hive Metastore               │
│  (Git for data)│  Catalog      │  (Legacy)                     │
└────────────────┴───────────────┴───────────────────────────────┘
```

---

## 2. DataHub (LinkedIn) Deep Dive

### Overview

DataHub is an extensible, stream-first metadata platform originally built at LinkedIn.
It's designed for real-time metadata ingestion, rich search, and programmatic governance.

### Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          DataHub Architecture                             │
│                                                                          │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────────────┐  │
│  │   DataHub    │    │   DataHub    │    │      Ingestion           │  │
│  │   Frontend   │    │   Actions    │    │      Framework           │  │
│  │   (React)    │    │  (Python)    │    │    (Python/Java)         │  │
│  └──────┬───────┘    └──────┬───────┘    └──────────┬───────────────┘  │
│         │                   │                        │                   │
│         │ GraphQL           │ Events                 │ MCE/MCP           │
│         ▼                   ▼                        ▼                   │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                    DataHub GMS (Backend)                          │   │
│  │              (Generalized Metadata Service)                       │   │
│  │                                                                   │   │
│  │  ┌─────────┐  ┌──────────┐  ┌───────────┐  ┌───────────────┐  │   │
│  │  │ GraphQL │  │  Rest.li │  │  Auth/ACL  │  │  Search Index │  │   │
│  │  │  API    │  │   API    │  │  Engine    │  │   Builder     │  │   │
│  │  └─────────┘  └──────────┘  └───────────┘  └───────────────┘  │   │
│  │                                                                   │   │
│  └──────────────────────────┬────────────────────────────────────────┘   │
│                             │                                            │
│         ┌───────────────────┼───────────────────┐                       │
│         ▼                   ▼                   ▼                        │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐               │
│  │    MySQL /   │   │ Elasticsearch│   │   Neo4j /    │               │
│  │  PostgreSQL  │   │   (Search)   │   │  Graph DB    │               │
│  │  (Primary)   │   │              │   │  (Lineage)   │               │
│  └──────────────┘   └──────────────┘   └──────────────┘               │
│         ▲                   ▲                   ▲                        │
│         │                   │                   │                        │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │                    Apache Kafka                                    │  │
│  │           (MetadataChangeEvent / MetadataAuditEvent)              │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### Key Components

#### GMS (Generalized Metadata Service)
- Java Spring Boot application
- Serves GraphQL and Rest.li APIs
- Handles authentication, authorization, search indexing
- Processes metadata change proposals (MCPs)
- Emits metadata change logs (MCLs) to Kafka

#### Kafka Topics
- **MetadataChangeProposal (MCP)**: Inbound metadata changes (proposed)
- **MetadataChangeLog (MCL)**: Committed metadata changes (versioned + timeseries)
- **MetadataAuditEvent (MAE)**: Legacy event format (deprecated)
- **Platform Events**: System events for Actions framework

#### Storage Layer
- **MySQL/PostgreSQL**: Primary store for entity aspects (source of truth)
- **Elasticsearch**: Full-text search, faceted filtering, ranking
- **Neo4j** (optional): Graph queries for lineage traversal (can use ES graph instead)

### Data Model

#### Entities
Top-level objects in the metadata graph:

```
Dataset          → Tables, views, streams, files
DataJob          → ETL jobs, Airflow tasks
DataFlow         → Pipelines, Airflow DAGs
Dashboard        → BI dashboards
Chart            → Individual visualizations
Container        → Databases, schemas, folders
Domain           → Business domains
GlossaryTerm    → Business vocabulary
Tag              → Free-form labels
DataProduct      → Logical data products
MLModel          → Machine learning models
MLFeatureTable   → Feature store tables
```

#### Aspects
Metadata attached to entities (like facets):

```python
# Example: Dataset entity with multiple aspects
{
  "urn": "urn:li:dataset:(urn:li:dataPlatform:snowflake,my_db.my_schema.users,PROD)",
  "aspects": {
    "schemaMetadata": {
      "fields": [
        {"fieldPath": "user_id", "type": "NUMBER", "nativeType": "INT64"},
        {"fieldPath": "email", "type": "STRING", "nativeType": "VARCHAR"}
      ]
    },
    "ownership": {
      "owners": [{"owner": "urn:li:corpUser:jdoe", "type": "DATAOWNER"}]
    },
    "globalTags": {
      "tags": [{"tag": "urn:li:tag:PII"}]
    },
    "datasetProperties": {
      "description": "Core user profiles table",
      "customProperties": {"team": "identity", "sla": "hourly"}
    },
    "status": {"removed": false},
    "upstreamLineage": {
      "upstreams": [
        {"dataset": "urn:li:dataset:(urn:li:dataPlatform:kafka,user-events,PROD)"}
      ]
    }
  }
}
```

#### URN (Uniform Resource Name)
DataHub's universal identifier format:

```
urn:li:dataset:(urn:li:dataPlatform:{platform},{name},{env})
urn:li:dataJob:(urn:li:dataFlow:({orchestrator},{flow_id},{env}),{job_id})
urn:li:dashboard:(urn:li:dataPlatform:{platform},{dashboard_id})
urn:li:corpUser:{username}
urn:li:corpGroup:{group_name}
urn:li:domain:{domain_id}
urn:li:glossaryTerm:{term_id}
```

### Ingestion Framework

#### Pull-based Ingestion (Recipes)

```yaml
# datahub-ingestion-recipe.yaml
source:
  type: snowflake
  config:
    account_id: "myorg-account"
    username: "${SNOWFLAKE_USER}"
    password: "${SNOWFLAKE_PASSWORD}"
    warehouse: "COMPUTE_WH"
    role: "DATAHUB_ROLE"
    database_pattern:
      allow:
        - "ANALYTICS_DB"
        - "RAW_DB"
      deny:
        - ".*_SCRATCH"
    schema_pattern:
      allow:
        - ".*"
    include_tables: true
    include_views: true
    include_table_lineage: true
    include_column_lineage: true
    include_usage_stats: true
    profiling:
      enabled: true
      profile_table_level_only: false
      max_workers: 10
      profile_table_row_limit: 5000000

transformers:
  - type: "simple_add_dataset_domain"
    config:
      semantics: OVERWRITE
      domain_urn: "urn:li:domain:analytics"

sink:
  type: datahub-rest
  config:
    server: "http://datahub-gms:8080"
    token: "${DATAHUB_TOKEN}"
```

#### Push-based Ingestion (Python SDK)

```python
"""DataHub Python SDK - Emitting metadata programmatically."""
import datahub.emitter.mce_builder as builder
from datahub.emitter.rest_emitter import DatahubRestEmitter
from datahub.metadata.schema_classes import (
    DatasetPropertiesClass,
    SchemaMetadataClass,
    SchemaFieldClass,
    StringTypeClass,
    NumberTypeClass,
    OwnershipClass,
    OwnerClass,
    OwnershipTypeClass,
    UpstreamLineageClass,
    UpstreamClass,
    DatasetLineageTypeClass,
    ChangeTypeClass,
)
from datahub.emitter.mcp import MetadataChangeProposalWrapper

# Initialize emitter
emitter = DatahubRestEmitter(
    gms_server="http://datahub-gms:8080",
    token="your-api-token"
)

# Define dataset URN
dataset_urn = builder.make_dataset_urn(
    platform="snowflake",
    name="analytics_db.public.user_metrics",
    env="PROD"
)

# Emit dataset properties
properties_event = MetadataChangeProposalWrapper(
    entityUrn=dataset_urn,
    aspect=DatasetPropertiesClass(
        description="Aggregated user engagement metrics, refreshed hourly",
        customProperties={
            "team": "growth-analytics",
            "refresh_frequency": "hourly",
            "cost_center": "CC-1234",
            "data_classification": "internal"
        },
        externalUrl="https://snowflake.myorg.com/analytics_db/public/user_metrics"
    ),
)
emitter.emit(properties_event)

# Emit schema
schema_event = MetadataChangeProposalWrapper(
    entityUrn=dataset_urn,
    aspect=SchemaMetadataClass(
        schemaName="user_metrics",
        platform=builder.make_data_platform_urn("snowflake"),
        version=0,
        hash="",
        platformSchema=builder.make_schema_field_urn("snowflake", "user_metrics"),
        fields=[
            SchemaFieldClass(
                fieldPath="user_id",
                type=builder.make_schema_field_type(NumberTypeClass()),
                nativeDataType="INT64",
                description="Unique user identifier",
                nullable=False,
            ),
            SchemaFieldClass(
                fieldPath="daily_active_minutes",
                type=builder.make_schema_field_type(NumberTypeClass()),
                nativeDataType="FLOAT64",
                description="Minutes active per day",
            ),
            SchemaFieldClass(
                fieldPath="last_login",
                type=builder.make_schema_field_type(StringTypeClass()),
                nativeDataType="TIMESTAMP_NTZ",
                description="Last login timestamp (UTC)",
            ),
        ],
    ),
)
emitter.emit(schema_event)

# Emit lineage
upstream_urn = builder.make_dataset_urn("kafka", "user-activity-events", "PROD")
lineage_event = MetadataChangeProposalWrapper(
    entityUrn=dataset_urn,
    aspect=UpstreamLineageClass(
        upstreams=[
            UpstreamClass(
                dataset=upstream_urn,
                type=DatasetLineageTypeClass.TRANSFORMED,
            )
        ]
    ),
)
emitter.emit(lineage_event)

# Emit ownership
ownership_event = MetadataChangeProposalWrapper(
    entityUrn=dataset_urn,
    aspect=OwnershipClass(
        owners=[
            OwnerClass(
                owner=builder.make_user_urn("alice"),
                type=OwnershipTypeClass.DATAOWNER,
            ),
            OwnerClass(
                owner=builder.make_group_urn("growth-team"),
                type=OwnershipTypeClass.DEVELOPER,
            ),
        ]
    ),
)
emitter.emit(ownership_event)

print(f"Successfully emitted metadata for {dataset_urn}")
```

### GraphQL API

```graphql
# Query dataset with lineage
query {
  dataset(urn: "urn:li:dataset:(urn:li:dataPlatform:snowflake,analytics_db.public.user_metrics,PROD)") {
    name
    description
    platform {
      name
    }
    ownership {
      owners {
        owner {
          ... on CorpUser {
            username
            info {
              fullName
              email
            }
          }
        }
        type
      }
    }
    schemaMetadata {
      fields {
        fieldPath
        type
        nativeDataType
        description
        globalTags {
          tags {
            tag {
              name
            }
          }
        }
      }
    }
    lineage(input: { direction: UPSTREAM, count: 10 }) {
      relationships {
        entity {
          urn
          ... on Dataset {
            name
            platform {
              name
            }
          }
        }
      }
    }
  }
}

# Search across all entities
query {
  searchAcrossEntities(
    input: {
      types: [DATASET]
      query: "user_metrics"
      filters: [
        { field: "platform", values: ["snowflake"] }
        { field: "tags", values: ["urn:li:tag:PII"] }
      ]
      count: 20
    }
  ) {
    total
    searchResults {
      entity {
        urn
        ... on Dataset {
          name
          description
        }
      }
      matchedFields {
        name
        value
      }
    }
  }
}
```

### Actions Framework

```python
"""DataHub Actions - React to metadata events in real-time."""
from datahub_actions.action.action import Action
from datahub_actions.event.event_envelope import EventEnvelope
from datahub_actions.pipeline.pipeline_context import PipelineContext

class SlackNotificationAction(Action):
    """Notify Slack when PII tag is added to a dataset."""

    @classmethod
    def create(cls, config: dict, ctx: PipelineContext) -> "Action":
        return cls(config, ctx)

    def __init__(self, config: dict, ctx: PipelineContext):
        self.webhook_url = config.get("webhook_url")

    def act(self, event: EventEnvelope) -> None:
        metadata = event.event
        if self._is_pii_tag_addition(metadata):
            dataset_name = metadata.get("entityUrn", "unknown")
            self._send_slack_message(
                f"⚠️ PII tag added to dataset: {dataset_name}\n"
                f"Please verify data classification and access controls."
            )

    def _is_pii_tag_addition(self, metadata: dict) -> bool:
        aspect_name = metadata.get("aspectName")
        if aspect_name == "globalTags":
            tags = metadata.get("aspect", {}).get("tags", [])
            return any("PII" in t.get("tag", "") for t in tags)
        return False

    def _send_slack_message(self, message: str):
        import requests
        requests.post(self.webhook_url, json={"text": message})

    def close(self) -> None:
        pass
```

Actions pipeline config:

```yaml
# actions.yaml
name: "pii_notification_pipeline"
source:
  type: "kafka"
  config:
    connection:
      bootstrap: "localhost:9092"
      schema_registry_url: "http://localhost:8081"
    topic: "MetadataChangeLog_Versioned_v1"

filter:
  event_type: "MetadataChangeLogEvent_v1"
  event:
    aspectName: "globalTags"

action:
  type: "slack_notification"
  config:
    webhook_url: "${SLACK_WEBHOOK_URL}"

options:
  retry_count: 3
  failure_mode: "CONTINUE"
```

### Domains and Data Products

```python
"""Setting up domains and data products in DataHub."""
from datahub.emitter.rest_emitter import DatahubRestEmitter
from datahub.emitter.mcp import MetadataChangeProposalWrapper
from datahub.metadata.schema_classes import (
    DomainPropertiesClass,
    DomainsClass,
    DataProductPropertiesClass,
)

emitter = DatahubRestEmitter("http://datahub-gms:8080")

# Create a domain
domain_urn = "urn:li:domain:customer-360"
domain_event = MetadataChangeProposalWrapper(
    entityUrn=domain_urn,
    aspect=DomainPropertiesClass(
        name="Customer 360",
        description="All customer-related data assets including profiles, interactions, and segments"
    ),
)
emitter.emit(domain_event)

# Assign dataset to domain
dataset_urn = "urn:li:dataset:(urn:li:dataPlatform:snowflake,analytics.public.customers,PROD)"
assign_domain = MetadataChangeProposalWrapper(
    entityUrn=dataset_urn,
    aspect=DomainsClass(domains=[domain_urn]),
)
emitter.emit(assign_domain)

# Create a data product
data_product_urn = "urn:li:dataProduct:customer-engagement-metrics"
dp_event = MetadataChangeProposalWrapper(
    entityUrn=data_product_urn,
    aspect=DataProductPropertiesClass(
        name="Customer Engagement Metrics",
        description="Curated engagement metrics for the customer domain",
        assets=[
            dataset_urn,
            "urn:li:dataset:(urn:li:dataPlatform:snowflake,analytics.public.customer_events,PROD)",
        ],
    ),
)
emitter.emit(dp_event)
```

### Deployment

#### Docker Compose (Development)

```yaml
# docker-compose.yml (simplified)
version: "3.8"
services:
  datahub-gms:
    image: linkedin/datahub-gms:latest
    environment:
      EBEAN_DATASOURCE_URL: "jdbc:mysql://mysql:3306/datahub?verifyServerCertificate=false&useSSL=true"
      EBEAN_DATASOURCE_USERNAME: datahub
      EBEAN_DATASOURCE_PASSWORD: datahub
      KAFKA_BOOTSTRAP_SERVER: broker:29092
      ELASTICSEARCH_HOST: elasticsearch
      ELASTICSEARCH_PORT: "9200"
      NEO4J_HOST: "bolt://neo4j:7687"
      DATAHUB_ANALYTICS_ENABLED: "true"
    ports:
      - "8080:8080"
    depends_on:
      - mysql
      - elasticsearch
      - broker
      - neo4j

  datahub-frontend:
    image: linkedin/datahub-frontend-react:latest
    environment:
      DATAHUB_GMS_HOST: datahub-gms
      DATAHUB_GMS_PORT: "8080"
      AUTH_OIDC_ENABLED: "true"
      AUTH_OIDC_CLIENT_ID: "${OIDC_CLIENT_ID}"
      AUTH_OIDC_CLIENT_SECRET: "${OIDC_CLIENT_SECRET}"
      AUTH_OIDC_DISCOVERY_URI: "https://login.microsoftonline.com/{tenant}/v2.0/.well-known/openid-configuration"
    ports:
      - "9002:9002"

  mysql:
    image: mysql:8.0
    environment:
      MYSQL_DATABASE: datahub
      MYSQL_USER: datahub
      MYSQL_PASSWORD: datahub
      MYSQL_ROOT_PASSWORD: datahub
    volumes:
      - mysql-data:/var/lib/mysql

  elasticsearch:
    image: elasticsearch:7.17.9
    environment:
      discovery.type: single-node
      ES_JAVA_OPTS: "-Xms512m -Xmx512m"
    volumes:
      - es-data:/usr/share/elasticsearch/data

  neo4j:
    image: neo4j:4.4
    environment:
      NEO4J_AUTH: neo4j/datahub
    volumes:
      - neo4j-data:/data

  broker:
    image: confluentinc/cp-kafka:7.4.0
    environment:
      KAFKA_BROKER_ID: 1
      KAFKA_ZOOKEEPER_CONNECT: zookeeper:2181
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://broker:29092
    depends_on:
      - zookeeper

  zookeeper:
    image: confluentinc/cp-zookeeper:7.4.0
    environment:
      ZOOKEEPER_CLIENT_PORT: 2181

volumes:
  mysql-data:
  es-data:
  neo4j-data:
```

#### Kubernetes Helm (Production)

```yaml
# values-production.yaml for DataHub Helm chart
datahub-gms:
  replicaCount: 3
  resources:
    requests:
      cpu: "2"
      memory: "4Gi"
    limits:
      cpu: "4"
      memory: "8Gi"
  livenessProbe:
    initialDelaySeconds: 60
  readinessProbe:
    initialDelaySeconds: 45

datahub-frontend:
  replicaCount: 2
  resources:
    requests:
      cpu: "1"
      memory: "2Gi"
  ingress:
    enabled: true
    className: nginx
    hosts:
      - host: datahub.internal.myorg.com
        paths:
          - path: /
    tls:
      - secretName: datahub-tls
        hosts:
          - datahub.internal.myorg.com

global:
  elasticsearch:
    host: "elasticsearch-master"
    port: "9200"
    indexPrefix: "datahub"
  kafka:
    bootstrap:
      server: "kafka-headless:9092"
    schemaregistry:
      url: "http://schema-registry:8081"
  sql:
    datasource:
      host: "mysql-primary:3306"
      url: "jdbc:mysql://mysql-primary:3306/datahub"
      driver: "com.mysql.cj.jdbc.Driver"
      username: "datahub"
      password:
        secretRef: datahub-mysql-secret
        secretKey: mysql-password
  neo4j:
    host: "bolt://neo4j:7687"
    username: "neo4j"
    password:
      secretRef: datahub-neo4j-secret
      secretKey: neo4j-password

# Elasticsearch managed externally (AWS OpenSearch or self-managed)
elasticsearch:
  enabled: false

# Kafka managed externally (MSK or Confluent)
kafka:
  enabled: false
```

### Production Scaling Considerations

| Component | Scaling Strategy | Key Metrics |
|-----------|-----------------|-------------|
| GMS | Horizontal (3-5 replicas) | API latency p99, request rate |
| Elasticsearch | 3+ nodes, dedicated masters | Search latency, indexing lag |
| Kafka | Partition by entity type | Consumer lag on MCL topics |
| MySQL | Primary-replica, connection pooling | Query latency, connection count |
| Neo4j | Read replicas for lineage queries | Traversal time, memory usage |
| Frontend | 2+ replicas behind LB | Response time, concurrent users |

---

## 3. OpenMetadata Deep Dive

### Overview

OpenMetadata is an all-in-one metadata platform with built-in data profiling,
lineage, quality tests, and a focus on simplicity. Backed by Collate (commercial).

### Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                     OpenMetadata Architecture                         │
│                                                                      │
│  ┌───────────────────┐         ┌───────────────────────────────┐   │
│  │    OpenMetadata    │         │    Ingestion Framework        │   │
│  │    UI (React)      │         │    (Python + Airflow)         │   │
│  └────────┬──────────┘         └──────────────┬────────────────┘   │
│           │                                    │                     │
│           │ REST API                           │ REST API            │
│           ▼                                    ▼                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │              OpenMetadata Server                              │   │
│  │          (Dropwizard / Java Application)                     │   │
│  │                                                               │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────────┐ │   │
│  │  │  REST    │  │  JSON    │  │  Auth    │  │  Event      │ │   │
│  │  │  APIs    │  │  Schema  │  │  (OIDC)  │  │  Handlers   │ │   │
│  │  └──────────┘  └──────────┘  └──────────┘  └────────────┘ │   │
│  └───────────────────────┬─────────────────────────────────────┘   │
│                          │                                          │
│          ┌───────────────┼───────────────┐                         │
│          ▼                               ▼                          │
│  ┌──────────────────┐           ┌──────────────────┐              │
│  │   MySQL / PG     │           │  Elasticsearch   │              │
│  │  (Primary Store) │           │    (Search)      │              │
│  └──────────────────┘           └──────────────────┘              │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │          Airflow (Ingestion Orchestration)                    │  │
│  │    - Metadata ingestion DAGs                                  │  │
│  │    - Data profiler DAGs                                       │  │
│  │    - Data quality test DAGs                                   │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

### Key Differentiators from DataHub

| Feature | OpenMetadata | DataHub |
|---------|-------------|---------|
| Data Profiling | Built-in (column stats, distributions) | Via Great Expectations integration |
| Data Quality | Native test framework | External (GE, dbt tests) |
| Lineage | Visual editor + automated | Automated + manual via API |
| Streaming arch | No (pull-based) | Yes (Kafka backbone) |
| API style | REST (OpenAPI) | GraphQL + Rest.li |
| Ingestion orchestrator | Airflow (built-in) | Standalone recipes |
| Extensibility | JSON Schema entities | PDL models + aspects |
| Governance | Roles/policies/teams | Policies + domains |

### Built-in Data Profiler

```yaml
# OpenMetadata profiler configuration
source:
  type: snowflake
  serviceName: snowflake_prod
  sourceConfig:
    config:
      type: Profiler
      generateSampleData: true
      profileSample: 10  # percentage
      profileSampleType: PERCENTAGE
      threadCount: 5
      timeoutSeconds: 300
      databaseFilterPattern:
        includes:
          - "ANALYTICS_DB"
      schemaFilterPattern:
        includes:
          - "PUBLIC"
      tableFilterPattern:
        includes:
          - ".*"
processor:
  type: orm-profiler
  config:
    tableConfig:
      - fullyQualifiedName: "snowflake_prod.ANALYTICS_DB.PUBLIC.users"
        profileSample: 50
        columnConfig:
          excludeColumns:
            - "password_hash"
          includeColumns:
            - columnName: "email"
              metrics:
                - uniqueCount
                - nullCount
                - distinctCount
```

### Roles and Policies

```json
{
  "name": "DataStewardPolicy",
  "description": "Allow data stewards to manage metadata for their domain",
  "rules": [
    {
      "name": "EditDescriptions",
      "resources": ["All"],
      "operations": ["EditDescription", "EditTags", "EditGlossaryTerms"],
      "effect": "allow",
      "condition": "matchAnyOwner()"
    },
    {
      "name": "ViewAll",
      "resources": ["All"],
      "operations": ["ViewAll"],
      "effect": "allow"
    },
    {
      "name": "DenyDeleteProd",
      "resources": ["table"],
      "operations": ["Delete"],
      "effect": "deny",
      "condition": "matchAnyTag('Production')"
    }
  ]
}
```

### OpenMetadata vs DataHub Decision Matrix

Choose **OpenMetadata** when:
- You want an all-in-one solution (profiling + quality + catalog)
- Your team prefers simpler REST APIs over GraphQL
- You already use Airflow for orchestration
- You have <500 data assets to start

Choose **DataHub** when:
- You need real-time metadata streaming (event-driven)
- You have a large-scale platform (10K+ datasets)
- You need deep extensibility (custom entities/aspects)
- You want a mature GraphQL API for integrations
- You need fine-grained programmatic governance (Actions)

---

## 4. Project Nessie

### Overview

Project Nessie provides **Git-like semantics for data lakes**. It enables branching,
tagging, and committing for Apache Iceberg tables — enabling multi-table transactions,
CI/CD for data, and safe experimentation.

### Core Concepts

```
┌─────────────────────────────────────────────────────────────────┐
│                    Project Nessie                                 │
│                                                                  │
│   main ─────●─────●─────●─────●─────●─────●──── (production)   │
│                    │                 ▲                            │
│                    │    merge        │                            │
│                    ▼                 │                            │
│   feature/        ●─────●─────●─────●  (experiment branch)      │
│   new-model                                                      │
│                                                                  │
│   Each ● = commit (atomic snapshot of ALL tables)                │
│   Tags = named immutable references (like releases)              │
│   Branches = mutable references (like git branches)              │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Key Features

1. **Branches**: Isolated workspaces for experimentation
2. **Tags**: Immutable snapshots for reproducibility
3. **Commits**: Atomic multi-table transactions
4. **Merge**: Conflict detection and resolution
5. **History**: Full audit trail of all changes

### Iceberg Integration

```python
"""Using Nessie with Apache Iceberg via PySpark."""
from pyspark.sql import SparkSession

spark = SparkSession.builder \
    .appName("NessieIcebergExample") \
    .config("spark.jars.packages",
            "org.apache.iceberg:iceberg-spark-runtime-3.4_2.12:1.4.0,"
            "org.projectnessie.nessie-integrations:nessie-spark-extensions-3.4_2.12:0.74.0") \
    .config("spark.sql.extensions",
            "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions,"
            "org.projectnessie.spark.extensions.NessieSparkSessionExtensions") \
    .config("spark.sql.catalog.nessie", "org.apache.iceberg.spark.SparkCatalog") \
    .config("spark.sql.catalog.nessie.catalog-impl",
            "org.apache.iceberg.nessie.NessieCatalog") \
    .config("spark.sql.catalog.nessie.uri", "http://nessie-server:19120/api/v2") \
    .config("spark.sql.catalog.nessie.ref", "main") \
    .config("spark.sql.catalog.nessie.warehouse", "s3://my-bucket/warehouse") \
    .getOrCreate()

# Work on main branch
spark.sql("USE nessie")
spark.sql("CREATE TABLE IF NOT EXISTS users (id INT, name STRING, email STRING)")
spark.sql("INSERT INTO users VALUES (1, 'Alice', 'alice@example.com')")

# Create a branch for experimentation
spark.sql("CREATE BRANCH IF NOT EXISTS `experiment/new-schema` IN nessie FROM main")

# Switch to the branch
spark.sql("USE REFERENCE `experiment/new-schema` IN nessie")

# Make changes on the branch (doesn't affect main)
spark.sql("ALTER TABLE users ADD COLUMN phone STRING")
spark.sql("INSERT INTO users VALUES (2, 'Bob', 'bob@example.com', '+1-555-0123')")

# Verify main is unchanged
spark.sql("USE REFERENCE main IN nessie")
result = spark.sql("DESCRIBE TABLE users").collect()
# phone column NOT present on main

# Merge when ready
spark.sql("MERGE BRANCH `experiment/new-schema` INTO main IN nessie")
```

### Nessie REST API

```bash
# List branches
curl http://nessie:19120/api/v2/trees

# Create branch
curl -X POST http://nessie:19120/api/v2/trees \
  -H "Content-Type: application/json" \
  -d '{
    "type": "BRANCH",
    "name": "feature/add-metrics",
    "hash": "main"
  }'

# Get commit log
curl "http://nessie:19120/api/v2/trees/main/log?maxRecords=10"

# Create tag (immutable snapshot)
curl -X POST http://nessie:19120/api/v2/trees \
  -H "Content-Type: application/json" \
  -d '{
    "type": "TAG",
    "name": "release-2024-01-15",
    "hash": "main"
  }'
```

### Nessie vs Hive Metastore vs AWS Glue Catalog

| Feature | Nessie | Hive Metastore | AWS Glue Catalog |
|---------|--------|----------------|------------------|
| Branching | Yes (core feature) | No | No |
| Multi-table txn | Yes (atomic commits) | No | No |
| Time travel | Via branches/tags | No (Iceberg does it) | No (Iceberg does it) |
| Table format | Iceberg, Delta | Hive, Iceberg | Hive, Iceberg, Delta |
| CI/CD for data | Native | Manual | Manual |
| Cloud-native | Yes (K8s) | Hadoop-era | AWS-managed |
| Query engines | Spark, Flink, Trino, Dremio | Spark, Hive, Presto | Athena, Spark, Redshift |
| Conflict detection | Yes (merge conflicts) | No | No |
| Scale | 10M+ objects | Proven at scale | Managed (limits apply) |

### CI/CD for Data with Nessie

```yaml
# .github/workflows/data-ci.yml
name: Data Pipeline CI
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  data-validation:
    runs-on: ubuntu-latest
    steps:
      - name: Create Nessie branch
        run: |
          BRANCH="ci/${GITHUB_SHA:0:8}"
          curl -X POST $NESSIE_URI/api/v2/trees \
            -d "{\"type\":\"BRANCH\",\"name\":\"$BRANCH\",\"hash\":\"main\"}"

      - name: Run pipeline on branch
        run: |
          spark-submit --conf spark.sql.catalog.nessie.ref=$BRANCH \
            my_pipeline.py

      - name: Run data quality checks
        run: |
          python run_quality_checks.py --nessie-branch=$BRANCH

      - name: Merge to main (if checks pass)
        if: github.event_name == 'push'
        run: |
          curl -X POST "$NESSIE_URI/api/v2/trees/main/merge" \
            -d "{\"fromRefName\":\"$BRANCH\"}"

      - name: Cleanup branch
        if: always()
        run: |
          curl -X DELETE "$NESSIE_URI/api/v2/trees/$BRANCH"
```

---

## 5. Marquez + OpenLineage

### OpenLineage Overview

OpenLineage is an **open standard** for lineage event collection. It defines a JSON
event format that any system can emit, creating a vendor-neutral lineage graph.

### Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                   OpenLineage Ecosystem                               │
│                                                                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐          │
│  │  Spark   │  │ Airflow  │  │   dbt    │  │  Flink   │          │
│  │  (OL     │  │  (OL     │  │  (OL     │  │  (OL     │          │
│  │  listener)│  │  listener)│  │  adapter)│  │  listener)│          │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘          │
│       │              │              │              │                  │
│       │  RunEvent    │  RunEvent    │  RunEvent    │  RunEvent       │
│       ▼              ▼              ▼              ▼                  │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │              OpenLineage HTTP Transport                        │   │
│  └──────────────────────────────┬───────────────────────────────┘   │
│                                 │                                     │
│                                 ▼                                     │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                     Marquez                                    │   │
│  │              (Lineage Store + API)                             │   │
│  │                                                                │   │
│  │  ┌─────────┐  ┌─────────────┐  ┌──────────────────────────┐ │   │
│  │  │  REST   │  │  PostgreSQL │  │  Lineage Graph Engine    │ │   │
│  │  │  API    │  │  (Storage)  │  │  (Jobs → Datasets → Runs)│ │   │
│  │  └─────────┘  └─────────────┘  └──────────────────────────┘ │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  Alternative backends: DataHub, OpenMetadata, Atlan, custom          │
└─────────────────────────────────────────────────────────────────────┘
```

### OpenLineage Event Format

```json
{
  "eventType": "COMPLETE",
  "eventTime": "2024-01-15T10:30:00.000Z",
  "run": {
    "runId": "d46e465b-d358-4d32-83d4-df660ff614dd",
    "facets": {
      "nominalTime": {
        "nominalStartTime": "2024-01-15T10:00:00.000Z",
        "nominalEndTime": "2024-01-15T10:30:00.000Z"
      },
      "processing_engine": {
        "version": "3.4.1",
        "name": "spark"
      }
    }
  },
  "job": {
    "namespace": "analytics-team",
    "name": "etl.transform_user_metrics",
    "facets": {
      "jobType": {
        "processingType": "BATCH",
        "integration": "SPARK",
        "jobType": "TASK"
      },
      "sql": {
        "query": "SELECT user_id, COUNT(*) as event_count FROM events GROUP BY user_id"
      },
      "sourceCodeLocation": {
        "type": "git",
        "url": "https://github.com/myorg/pipelines",
        "repoUrl": "https://github.com/myorg/pipelines",
        "path": "jobs/transform_user_metrics.py",
        "version": "abc123"
      }
    }
  },
  "inputs": [
    {
      "namespace": "snowflake://myorg.snowflakecomputing.com",
      "name": "RAW_DB.PUBLIC.events",
      "facets": {
        "schema": {
          "fields": [
            {"name": "user_id", "type": "INT64"},
            {"name": "event_type", "type": "STRING"},
            {"name": "timestamp", "type": "TIMESTAMP"}
          ]
        },
        "dataSource": {
          "name": "snowflake_prod",
          "uri": "snowflake://myorg.snowflakecomputing.com/RAW_DB/PUBLIC"
        },
        "columnLineage": {
          "fields": {
            "user_id": {
              "inputFields": [
                {"namespace": "snowflake://myorg", "name": "RAW_DB.PUBLIC.events", "field": "user_id"}
              ],
              "transformationDescription": "passthrough",
              "transformationType": "IDENTITY"
            }
          }
        }
      },
      "inputFacets": {
        "dataQualityMetrics": {
          "rowCount": 1500000,
          "bytes": 524288000,
          "columnMetrics": {
            "user_id": {"nullCount": 0, "distinctCount": 250000}
          }
        }
      }
    }
  ],
  "outputs": [
    {
      "namespace": "snowflake://myorg.snowflakecomputing.com",
      "name": "ANALYTICS_DB.PUBLIC.user_metrics",
      "facets": {
        "schema": {
          "fields": [
            {"name": "user_id", "type": "INT64"},
            {"name": "event_count", "type": "INT64"}
          ]
        },
        "outputStatistics": {
          "rowCount": 250000,
          "bytes": 10485760
        }
      }
    }
  ],
  "producer": "https://github.com/OpenLineage/OpenLineage/tree/0.29.0/integration/spark"
}
```

### Spark Integration

```python
"""Spark with OpenLineage listener for automatic lineage capture."""
from pyspark.sql import SparkSession

spark = SparkSession.builder \
    .appName("UserMetricsETL") \
    .config("spark.extraListeners", "io.openlineage.spark.agent.OpenLineageSparkListener") \
    .config("spark.openlineage.transport.type", "http") \
    .config("spark.openlineage.transport.url", "http://marquez:5000") \
    .config("spark.openlineage.namespace", "analytics-team") \
    .config("spark.openlineage.parentJobNamespace", "analytics-team") \
    .config("spark.openlineage.parentJobName", "daily-pipeline") \
    .config("spark.openlineage.parentRunId", "abc-123-def") \
    .getOrCreate()

# All Spark operations automatically emit lineage events
events_df = spark.read.table("raw_db.events")
user_metrics = events_df.groupBy("user_id").count()
user_metrics.write.mode("overwrite").saveAsTable("analytics_db.user_metrics")
# ^ OpenLineage captures: input(raw_db.events) → job → output(analytics_db.user_metrics)
```

### Airflow Integration

```python
"""Airflow DAG with OpenLineage integration."""
from airflow import DAG
from airflow.providers.openlineage.plugins.listener import OpenLineageListener
from airflow.providers.snowflake.operators.snowflake import SnowflakeOperator
from datetime import datetime

# OpenLineage is auto-enabled via airflow.cfg:
# [openlineage]
# transport = {"type": "http", "url": "http://marquez:5000", "endpoint": "api/v1/lineage"}
# namespace = "airflow-prod"

with DAG(
    dag_id="user_metrics_pipeline",
    start_date=datetime(2024, 1, 1),
    schedule_interval="@hourly",
    catchup=False,
) as dag:

    extract = SnowflakeOperator(
        task_id="extract_events",
        sql="""
            CREATE OR REPLACE TABLE staging.hourly_events AS
            SELECT * FROM raw.events
            WHERE timestamp >= '{{ data_interval_start }}'
              AND timestamp < '{{ data_interval_end }}'
        """,
        snowflake_conn_id="snowflake_prod",
    )

    transform = SnowflakeOperator(
        task_id="transform_metrics",
        sql="""
            MERGE INTO analytics.user_metrics t
            USING (
                SELECT user_id, COUNT(*) as event_count
                FROM staging.hourly_events
                GROUP BY user_id
            ) s
            ON t.user_id = s.user_id
            WHEN MATCHED THEN UPDATE SET event_count = t.event_count + s.event_count
            WHEN NOT MATCHED THEN INSERT (user_id, event_count) VALUES (s.user_id, s.event_count)
        """,
        snowflake_conn_id="snowflake_prod",
    )

    extract >> transform
    # OpenLineage automatically captures lineage for each task
```

### Marquez API

```bash
# Get lineage for a job
curl "http://marquez:5000/api/v1/lineage?nodeId=job:analytics-team:etl.transform_user_metrics"

# List datasets in a namespace
curl "http://marquez:5000/api/v1/namespaces/analytics-team/datasets"

# Get dataset details with column lineage
curl "http://marquez:5000/api/v1/namespaces/analytics-team/datasets/user_metrics"

# Get job runs
curl "http://marquez:5000/api/v1/namespaces/analytics-team/jobs/etl.transform_user_metrics/runs"

# Search
curl "http://marquez:5000/api/v1/search?q=user_metrics&filter=dataset"
```

### Custom Facets

```python
"""Emitting custom OpenLineage facets."""
from openlineage.client import OpenLineageClient
from openlineage.client.run import (
    RunEvent, RunState, Run, Job, Dataset,
    InputDataset, OutputDataset
)
from openlineage.client.facet import (
    BaseFacet, SchemaDatasetFacet, SchemaField,
    DataQualityMetricsInputDatasetFacet,
    ColumnMetric
)
from openlineage.client.transport.http import HttpConfig, HttpTransport
import uuid
from datetime import datetime

# Custom facet for cost tracking
class CostFacet(BaseFacet):
    def __init__(self, compute_cost_usd: float, storage_cost_usd: float, credits_used: float):
        super().__init__()
        self.compute_cost_usd = compute_cost_usd
        self.storage_cost_usd = storage_cost_usd
        self.credits_used = credits_used

# Initialize client
config = HttpConfig(url="http://marquez:5000", endpoint="api/v1/lineage")
transport = HttpTransport(config)
client = OpenLineageClient(transport=transport)

# Emit event with custom facet
run_id = str(uuid.uuid4())
event = RunEvent(
    eventType=RunState.COMPLETE,
    eventTime=datetime.utcnow().isoformat() + "Z",
    run=Run(runId=run_id),
    job=Job(namespace="analytics-team", name="expensive_aggregation"),
    inputs=[
        InputDataset(
            namespace="snowflake://myorg",
            name="RAW_DB.events",
            facets={
                "schema": SchemaDatasetFacet(
                    fields=[
                        SchemaField(name="user_id", type="INT64"),
                        SchemaField(name="event_type", type="STRING"),
                    ]
                ),
                "dataQualityMetrics": DataQualityMetricsInputDatasetFacet(
                    rowCount=10_000_000,
                    bytes=5_000_000_000,
                ),
            },
        )
    ],
    outputs=[
        OutputDataset(
            namespace="snowflake://myorg",
            name="ANALYTICS_DB.aggregated_events",
            facets={
                "cost": CostFacet(
                    compute_cost_usd=12.50,
                    storage_cost_usd=0.23,
                    credits_used=5.0,
                ),
            },
        )
    ],
    producer="my-pipeline/v1.0",
)
client.emit(event)
```

---

## 6. Data Catalog Patterns

### Federated Catalog Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Federated Catalog Architecture                     │
│                                                                      │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐               │
│  │  Domain A   │  │  Domain B   │  │  Domain C   │               │
│  │  (Finance)  │  │  (Marketing)│  │  (Product)  │               │
│  │             │  │             │  │             │               │
│  │  Local      │  │  Local      │  │  Local      │               │
│  │  Catalog    │  │  Catalog    │  │  Catalog    │               │
│  │  Owner      │  │  Owner      │  │  Owner      │               │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘               │
│         │                 │                 │                        │
│         │  publish        │  publish        │  publish              │
│         ▼                 ▼                 ▼                        │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │              Central Metadata Platform (DataHub)               │  │
│  │                                                                │  │
│  │  - Aggregates metadata from all domains                       │  │
│  │  - Provides unified search and discovery                      │  │
│  │  - Enforces cross-domain governance policies                  │  │
│  │  - Maintains global lineage graph                             │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                      │
│  Key Principles:                                                     │
│  1. Domain teams OWN their metadata (descriptions, quality)         │
│  2. Central platform AGGREGATES for discovery                       │
│  3. Automated ingestion reduces manual burden                       │
│  4. Governance policies applied centrally, enforced locally         │
└─────────────────────────────────────────────────────────────────────┘
```

### Automated PII Detection

```python
"""Automated PII detection using column names and sampling."""
import re
from typing import List, Dict, Tuple
from datahub.emitter.rest_emitter import DatahubRestEmitter
from datahub.emitter.mcp import MetadataChangeProposalWrapper
from datahub.metadata.schema_classes import GlobalTagsClass, TagAssociationClass

PII_PATTERNS = {
    "email": [r".*email.*", r".*e_mail.*"],
    "phone": [r".*phone.*", r".*mobile.*", r".*tel.*"],
    "ssn": [r".*ssn.*", r".*social_sec.*", r".*national_id.*"],
    "name": [r".*first_name.*", r".*last_name.*", r".*full_name.*"],
    "address": [r".*address.*", r".*street.*", r".*zip.*", r".*postal.*"],
    "ip_address": [r".*ip_addr.*", r".*ip_address.*", r".*client_ip.*"],
    "credit_card": [r".*card_num.*", r".*cc_num.*", r".*credit_card.*"],
    "dob": [r".*date_of_birth.*", r".*dob.*", r".*birth_date.*"],
}

DATA_PATTERNS = {
    "email": r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$",
    "phone": r"^\+?[\d\s\-\(\)]{7,15}$",
    "ssn": r"^\d{3}-?\d{2}-?\d{4}$",
    "ip_address": r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$",
    "credit_card": r"^\d{4}[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{4}$",
}


def detect_pii_columns(
    column_names: List[str],
    sample_data: Dict[str, List[str]] = None,
) -> Dict[str, str]:
    """Detect PII columns by name patterns and optional data sampling."""
    pii_columns = {}

    for col in column_names:
        col_lower = col.lower()
        for pii_type, patterns in PII_PATTERNS.items():
            if any(re.match(p, col_lower) for p in patterns):
                pii_columns[col] = pii_type
                break

    # Enhanced detection via data sampling
    if sample_data:
        for col, values in sample_data.items():
            if col in pii_columns:
                continue
            for pii_type, pattern in DATA_PATTERNS.items():
                match_count = sum(1 for v in values if v and re.match(pattern, str(v)))
                if match_count / max(len(values), 1) > 0.7:
                    pii_columns[col] = pii_type
                    break

    return pii_columns


def tag_pii_in_datahub(
    emitter: DatahubRestEmitter,
    dataset_urn: str,
    pii_columns: Dict[str, str],
):
    """Apply PII tags to columns in DataHub."""
    for column, pii_type in pii_columns.items():
        tag_urn = f"urn:li:tag:PII_{pii_type.upper()}"
        # Use editableSchemaMetadata to tag at field level
        event = MetadataChangeProposalWrapper(
            entityUrn=dataset_urn,
            aspect=GlobalTagsClass(
                tags=[TagAssociationClass(tag=tag_urn)]
            ),
        )
        emitter.emit(event)
```

### Freshness Tracking and Alerting

```python
"""Monitor dataset freshness and alert on SLA breaches."""
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Optional
import requests


@dataclass
class FreshnessSLA:
    dataset_urn: str
    max_staleness: timedelta
    owner_email: str
    severity: str = "high"


FRESHNESS_SLAS = [
    FreshnessSLA(
        dataset_urn="urn:li:dataset:(urn:li:dataPlatform:snowflake,analytics.user_metrics,PROD)",
        max_staleness=timedelta(hours=2),
        owner_email="data-team@myorg.com",
        severity="critical",
    ),
    FreshnessSLA(
        dataset_urn="urn:li:dataset:(urn:li:dataPlatform:snowflake,analytics.daily_report,PROD)",
        max_staleness=timedelta(hours=25),
        owner_email="analytics@myorg.com",
        severity="high",
    ),
]


def check_freshness(datahub_url: str, sla: FreshnessSLA) -> Optional[str]:
    """Check if dataset meets freshness SLA via DataHub API."""
    query = """
    query {
      dataset(urn: "%s") {
        lastIngested
        datasetProfiles(limit: 1) {
          timestampMillis
          rowCount
        }
      }
    }
    """ % sla.dataset_urn

    response = requests.post(
        f"{datahub_url}/api/graphql",
        json={"query": query},
        headers={"Authorization": "Bearer <token>"},
    )
    data = response.json()["data"]["dataset"]

    profiles = data.get("datasetProfiles", [])
    if not profiles:
        return f"No profile data for {sla.dataset_urn}"

    last_profile_ms = profiles[0]["timestampMillis"]
    last_profile_time = datetime.fromtimestamp(last_profile_ms / 1000)
    staleness = datetime.utcnow() - last_profile_time

    if staleness > sla.max_staleness:
        return (
            f"FRESHNESS SLA BREACH: {sla.dataset_urn}\n"
            f"  Expected: updated within {sla.max_staleness}\n"
            f"  Actual: last update {staleness} ago\n"
            f"  Severity: {sla.severity}"
        )
    return None
```

### Schema Change Notification

```python
"""Detect and notify on schema changes using DataHub Actions."""

# actions-schema-change.yaml
ACTION_CONFIG = """
name: "schema_change_detector"
source:
  type: "kafka"
  config:
    connection:
      bootstrap: "kafka:9092"
    topic: "MetadataChangeLog_Versioned_v1"

filter:
  event_type: "MetadataChangeLogEvent_v1"
  event:
    aspectName: "schemaMetadata"

action:
  type: "schema_change_notifier"
  config:
    slack_webhook: "${SLACK_WEBHOOK}"
    email_recipients:
      - "data-platform@myorg.com"
"""
```

---

## 7. AWS Glue Catalog as Governance

### Cross-Account Sharing with Lake Formation

```
┌─────────────────────────────────────────────────────────────────────┐
│                Cross-Account Glue Catalog Sharing                     │
│                                                                      │
│  Account A (Producer)              Account B (Consumer)              │
│  ┌────────────────────┐           ┌────────────────────┐           │
│  │  Glue Catalog      │           │  Glue Catalog      │           │
│  │  ┌──────────────┐  │   share   │  ┌──────────────┐  │           │
│  │  │ Database:    │  │──────────▶│  │ Resource     │  │           │
│  │  │ analytics    │  │           │  │ Link:        │  │           │
│  │  │              │  │           │  │ shared_      │  │           │
│  │  │ Tables:      │  │           │  │ analytics    │  │           │
│  │  │ - users      │  │           │  └──────────────┘  │           │
│  │  │ - orders     │  │           │                    │           │
│  │  └──────────────┘  │           │  Query via:        │           │
│  │                    │           │  - Athena           │           │
│  │  Lake Formation    │           │  - Redshift Spectrum│           │
│  │  - LF-Tags        │           │  - EMR Spark        │           │
│  │  - Permissions     │           │                    │           │
│  └────────────────────┘           └────────────────────┘           │
└─────────────────────────────────────────────────────────────────────┘
```

### LF-Tags for Column-Level Access Control

```python
"""AWS Lake Formation LF-Tags for governance."""
import boto3

lf_client = boto3.client("lakeformation")
glue_client = boto3.client("glue")

# Create LF-Tags
lf_client.create_lf_tag(
    TagKey="classification",
    TagValues=["public", "internal", "confidential", "restricted"]
)

lf_client.create_lf_tag(
    TagKey="pii_type",
    TagValues=["none", "email", "phone", "ssn", "name", "address"]
)

# Assign LF-Tags to columns
lf_client.add_lf_tags_to_resource(
    Resource={
        "TableWithColumns": {
            "DatabaseName": "analytics",
            "Name": "users",
            "ColumnNames": ["email", "phone_number"]
        }
    },
    LFTags=[
        {"TagKey": "classification", "TagValues": ["restricted"]},
        {"TagKey": "pii_type", "TagValues": ["email", "phone"]},
    ]
)

# Grant access based on LF-Tags (tag-based access control)
lf_client.grant_permissions(
    Principal={"DataLakePrincipalIdentifier": "arn:aws:iam::123456789:role/AnalystRole"},
    Resource={
        "LFTagPolicy": {
            "ResourceType": "TABLE",
            "Expression": [
                {"TagKey": "classification", "TagValues": ["public", "internal"]}
            ]
        }
    },
    Permissions=["SELECT"],
)

# Deny access to restricted columns for non-privileged roles
lf_client.grant_permissions(
    Principal={"DataLakePrincipalIdentifier": "arn:aws:iam::123456789:role/AnalystRole"},
    Resource={
        "LFTagPolicy": {
            "ResourceType": "COLUMN",
            "Expression": [
                {"TagKey": "classification", "TagValues": ["restricted"]}
            ]
        }
    },
    Permissions=[],  # No permissions = denied
    PermissionsWithGrantOption=[],
)
```

### Hybrid: Glue Catalog + DataHub

```yaml
# DataHub ingestion from Glue Catalog
source:
  type: glue
  config:
    aws_region: us-east-1
    aws_role: "arn:aws:iam::123456789:role/DataHubGlueReader"
    extract_transforms: true
    extract_owners_from_tags: true
    catalog_id: "123456789012"
    database_pattern:
      allow:
        - "analytics.*"
        - "raw.*"

sink:
  type: datahub-rest
  config:
    server: "http://datahub-gms:8080"
```

---

## 8. Governance Automation

### GDPR/CCPA Compliance Pipeline

```python
"""Automated GDPR Right to Erasure (Right to be Forgotten) pipeline."""
from dataclasses import dataclass
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)


@dataclass
class ErasureRequest:
    request_id: str
    subject_id: str  # user_id or email
    subject_type: str  # "user_id", "email", "phone"
    requested_at: str
    deadline: str  # GDPR: 30 days


@dataclass
class DataLocation:
    platform: str
    database: str
    table: str
    column: str
    erasure_method: str  # "delete", "anonymize", "nullify"


def get_pii_locations_from_lineage(
    datahub_url: str, subject_type: str
) -> List[DataLocation]:
    """Query DataHub to find all locations of a PII type."""
    # Use DataHub search to find all columns tagged with the PII type
    query = """
    query {
      searchAcrossEntities(
        input: {
          types: [DATASET]
          query: "*"
          filters: [
            { field: "fieldGlossaryTerms", values: ["urn:li:glossaryTerm:%s"] }
          ]
          count: 1000
        }
      ) {
        searchResults {
          entity {
            urn
            ... on Dataset {
              name
              platform { name }
              schemaMetadata {
                fields {
                  fieldPath
                  glossaryTerms { terms { term { name } } }
                }
              }
            }
          }
        }
      }
    }
    """ % subject_type
    # Parse results into DataLocation objects
    # ...
    return []


def execute_erasure(request: ErasureRequest, locations: List[DataLocation]):
    """Execute data erasure across all identified locations."""
    results = []
    for loc in locations:
        try:
            if loc.erasure_method == "delete":
                # Execute DELETE WHERE subject_column = subject_id
                pass
            elif loc.erasure_method == "anonymize":
                # Execute UPDATE SET column = hash(column) WHERE ...
                pass
            elif loc.erasure_method == "nullify":
                # Execute UPDATE SET column = NULL WHERE ...
                pass
            results.append({"location": loc, "status": "success"})
        except Exception as e:
            results.append({"location": loc, "status": "failed", "error": str(e)})
            logger.error(f"Erasure failed for {loc}: {e}")

    # Log audit trail
    log_erasure_audit(request, results)
    return results


def log_erasure_audit(request: ErasureRequest, results: List[Dict]):
    """Maintain immutable audit log for compliance."""
    audit_record = {
        "request_id": request.request_id,
        "subject_id": "REDACTED",  # Don't store subject ID in audit
        "requested_at": request.requested_at,
        "completed_at": "2024-01-15T12:00:00Z",
        "locations_processed": len(results),
        "locations_succeeded": sum(1 for r in results if r["status"] == "success"),
        "locations_failed": sum(1 for r in results if r["status"] == "failed"),
    }
    # Write to immutable audit store (e.g., S3 with Object Lock)
    logger.info(f"Erasure audit: {audit_record}")
```

### Retention Enforcement

```python
"""Automated data retention enforcement."""
from datetime import datetime, timedelta
from typing import List
import boto3


RETENTION_POLICIES = {
    "raw_events": timedelta(days=90),
    "processed_analytics": timedelta(days=365),
    "audit_logs": timedelta(days=2555),  # 7 years
    "tmp_staging": timedelta(days=7),
    "pii_data": timedelta(days=365),  # With annual review
}


def enforce_retention_s3(bucket: str, prefix: str, max_age: timedelta):
    """Delete S3 objects older than retention policy."""
    s3 = boto3.client("s3")
    cutoff = datetime.utcnow() - max_age

    paginator = s3.get_paginator("list_objects_v2")
    objects_to_delete = []

    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            if obj["LastModified"].replace(tzinfo=None) < cutoff:
                objects_to_delete.append({"Key": obj["Key"]})

            if len(objects_to_delete) >= 1000:
                s3.delete_objects(
                    Bucket=bucket,
                    Delete={"Objects": objects_to_delete}
                )
                objects_to_delete = []

    if objects_to_delete:
        s3.delete_objects(
            Bucket=bucket,
            Delete={"Objects": objects_to_delete}
        )


def enforce_retention_snowflake(
    connection, database: str, schema: str, table: str,
    timestamp_column: str, max_age: timedelta
):
    """Delete rows older than retention policy in Snowflake."""
    cutoff_date = (datetime.utcnow() - max_age).strftime("%Y-%m-%d")
    query = f"""
        DELETE FROM {database}.{schema}.{table}
        WHERE {timestamp_column} < '{cutoff_date}'
    """
    cursor = connection.cursor()
    cursor.execute(query)
    deleted_rows = cursor.rowcount
    return deleted_rows
```

### Access Review Automation

```python
"""Periodic access review automation."""
from typing import List, Dict
from dataclasses import dataclass


@dataclass
class AccessGrant:
    principal: str  # user or role
    resource: str  # dataset URN
    permission: str  # SELECT, INSERT, etc.
    granted_at: str
    granted_by: str
    last_used: str  # From query logs


def generate_access_review(
    grants: List[AccessGrant],
    unused_threshold_days: int = 90,
) -> Dict[str, List[AccessGrant]]:
    """Generate access review report categorizing grants."""
    from datetime import datetime, timedelta

    cutoff = datetime.utcnow() - timedelta(days=unused_threshold_days)
    review = {
        "revoke_candidates": [],  # Unused for > threshold
        "review_needed": [],  # Active but broad permissions
        "compliant": [],  # Recently used, appropriate scope
    }

    for grant in grants:
        last_used_dt = datetime.fromisoformat(grant.last_used) if grant.last_used else None

        if not last_used_dt or last_used_dt < cutoff:
            review["revoke_candidates"].append(grant)
        elif grant.permission in ("ALL", "OWNERSHIP"):
            review["review_needed"].append(grant)
        else:
            review["compliant"].append(grant)

    return review
```

---

## 9. Decision Framework

### DataHub vs OpenMetadata vs Atlas vs Amundsen

| Criteria | DataHub | OpenMetadata | Apache Atlas | Amundsen |
|----------|---------|--------------|--------------|----------|
| **Maturity** | High (LinkedIn prod) | Medium (growing fast) | High (legacy) | Medium (maintenance) |
| **Architecture** | Stream-first (Kafka) | Pull-based (Airflow) | Kafka + HBase | Flask + Neo4j |
| **Scale** | 10K+ datasets proven | 1K-5K sweet spot | Large (Hadoop) | Medium |
| **Search** | Elasticsearch (excellent) | Elasticsearch (good) | Solr | Elasticsearch |
| **Lineage** | Excellent (column-level) | Good (visual) | Basic | Basic |
| **Extensibility** | Very high (aspects) | Medium (JSON schema) | High (type system) | Low |
| **API** | GraphQL + REST | REST (OpenAPI) | REST | REST |
| **Built-in profiling** | No (integrations) | Yes (native) | No | No |
| **Built-in quality** | No (integrations) | Yes (native) | No | No |
| **Community** | Large, active | Growing fast | Declining | Maintenance mode |
| **Commercial** | Acryl Data (managed) | Collate (managed) | Cloudera | None |
| **Best for** | Large orgs, platform teams | Mid-size, all-in-one | Hadoop shops | Simple discovery |

### Build vs Buy Decision

**Build (Open Source) when:**
- You have a platform team (3+ engineers) to maintain
- You need deep customization
- Multi-cloud or on-prem requirements
- Budget constraints but engineering capacity

**Buy (Managed/SaaS) when:**
- Time to value matters more than customization
- Team < 3 engineers for metadata platform
- You want built-in support and SLAs
- Compliance requires vendor accountability

**Commercial options:**
- Acryl Data (managed DataHub)
- Collate (managed OpenMetadata)
- Atlan (SaaS catalog)
- Alation (enterprise catalog)
- Select Star (automated lineage)

---

## 10. Production Checklist

### Deployment

- [ ] High availability: 3+ GMS replicas, ES cluster (3 nodes min)
- [ ] Kafka: 3+ brokers, replication factor 3, proper partitioning
- [ ] Database: Primary-replica setup, automated backups
- [ ] Secrets management: Vault/AWS Secrets Manager for credentials
- [ ] TLS everywhere (inter-service, client-facing)
- [ ] Network policies / security groups restricting access

### Ingestion

- [ ] All critical data sources connected (databases, warehouses, BI tools)
- [ ] Lineage extraction enabled (Spark, Airflow, dbt)
- [ ] Ingestion schedules configured (hourly for critical, daily for others)
- [ ] Push-based ingestion for real-time pipelines
- [ ] Profiling enabled for key datasets
- [ ] Ingestion monitoring and alerting

### Governance

- [ ] Domain model defined and datasets assigned
- [ ] Ownership assigned to all production datasets
- [ ] PII classification (automated + manual review)
- [ ] Access control policies configured
- [ ] Retention policies defined and automated
- [ ] GDPR/CCPA erasure workflow tested

### Operations

- [ ] Monitoring dashboards (ingestion lag, API latency, search quality)
- [ ] Alerting on freshness SLA breaches
- [ ] Schema change notifications to downstream owners
- [ ] Backup and disaster recovery tested
- [ ] Runbook for common operational issues
- [ ] Capacity planning for metadata growth

### Adoption

- [ ] Search relevance tuned (boost frequently accessed datasets)
- [ ] Business glossary populated with key terms
- [ ] User onboarding documentation
- [ ] Integration with IDE/notebook environments
- [ ] Slack/Teams bot for metadata queries
- [ ] Usage metrics tracked (MAU, searches, edits)

### Advanced

- [ ] Column-level lineage for critical pipelines
- [ ] Data contracts defined between producers and consumers
- [ ] Cost attribution per dataset/pipeline
- [ ] Impact analysis workflow before schema changes
- [ ] Automated data product quality scoring
- [ ] Integration with incident management (PagerDuty/OpsGenie)

---

## Summary

The modern metadata and governance stack has evolved from simple catalogs to
**active metadata platforms** that drive automation. Key architectural decisions:

1. **DataHub** for large-scale, event-driven, highly extensible metadata management
2. **OpenMetadata** for all-in-one simplicity with built-in profiling and quality
3. **Nessie** for Git-like data lake versioning and multi-table transactions
4. **OpenLineage + Marquez** for vendor-neutral lineage collection and visualization
5. **AWS Glue + Lake Formation** for AWS-native governance with LF-Tags
6. **Governance automation** closes the loop: detect → classify → enforce → audit

The most successful implementations treat metadata as a **product** — with dedicated
ownership, SLAs, and continuous improvement based on user adoption metrics.
