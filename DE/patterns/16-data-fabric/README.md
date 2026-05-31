# Pattern 16: Data Fabric

## Data Fabric vs Data Mesh

```
THE CONFUSION:
══════════════
Both Data Fabric and Data Mesh solve the same problem: 
"How do I find, access, and trust data across a large organization?"

But they solve it VERY differently:

┌─────────────────────────────────┬──────────────────────────────────────────┐
│ DATA MESH                        │ DATA FABRIC                               │
├─────────────────────────────────┼──────────────────────────────────────────┤
│ Organizational principle         │ Technology architecture                    │
│ Decentralized ownership          │ Centralized intelligence layer             │
│ Each domain builds + owns data   │ AI/ML automates integration + governance  │
│ Federated governance             │ Unified metadata + knowledge graph         │
│ Self-serve infrastructure        │ Automated data discovery + access          │
│                                  │                                            │
│ PEOPLE solution:                 │ TECHNOLOGY solution:                       │
│ "Give domains ownership"         │ "Build smart connectors + metadata"       │
│                                  │                                            │
│ REQUIRES:                        │ REQUIRES:                                  │
│ Org change, domain teams,        │ Metadata platform, knowledge graph,       │
│ platform team, cultural shift    │ AI/ML for automation, connectors          │
│                                  │                                            │
│ FAILURE MODE:                    │ FAILURE MODE:                              │
│ Domains don't invest in data     │ Garbage in, garbage out (AI can't fix    │
│ quality → data products rot      │ fundamentally bad data)                   │
└─────────────────────────────────┴──────────────────────────────────────────┘

CAN YOU USE BOTH? YES.
  Data Mesh = organizational model (who owns what)
  Data Fabric = infrastructure layer (how to discover/access/govern)
  Best practice: Data Mesh teams build products ON a Data Fabric platform.
```

## Data Fabric Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  DATA FABRIC ARCHITECTURE                                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────┐       │
│  │  LAYER 1: UNIFIED METADATA & KNOWLEDGE GRAPH                      │       │
│  │  ─────────────────────────────────────────────                    │       │
│  │                                                                   │       │
│  │  Active Metadata:                                                 │       │
│  │  • Technical: schema, lineage, quality scores, freshness          │       │
│  │  • Business: definitions, owners, domains, certifications         │       │
│  │  • Operational: access patterns, query frequency, SLA compliance  │       │
│  │  • Social: ratings, annotations, who uses what                    │       │
│  │                                                                   │       │
│  │  Knowledge Graph:                                                 │       │
│  │  [Table A] ──feeds──▶ [Pipeline X] ──produces──▶ [Table B]       │       │
│  │  [Table B] ──consumed_by──▶ [Dashboard Y]                        │       │
│  │  [Column Z] ──contains──▶ [PII: email]                           │       │
│  │  [Table A] ──owned_by──▶ [Team: Payments]                        │       │
│  │                                                                   │       │
│  │  AI/ML Layer:                                                     │       │
│  │  • Auto-classify PII columns (NLP on column names + samples)      │       │
│  │  • Recommend datasets for a question ("who has churn data?")      │       │
│  │  • Detect anomalies in freshness/quality                          │       │
│  │  • Suggest joins between related tables                           │       │
│  └──────────────────────────────────────────────────────────────────┘       │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────┐       │
│  │  LAYER 2: INTELLIGENT DATA INTEGRATION                            │       │
│  │  ─────────────────────────────────────────                        │       │
│  │                                                                   │       │
│  │  Virtual Layer (Query Federation):                                │       │
│  │  • Trino/Presto: Query across Postgres, S3, Kafka without ETL     │       │
│  │  • Dremio: Reflections (auto-materialized views for performance) │       │
│  │  • Starburst: Cross-cloud query federation                        │       │
│  │                                                                   │       │
│  │  Physical Layer (ETL/ELT):                                        │       │
│  │  • When federation is too slow, materialize into lakehouse        │       │
│  │  • Auto-generated pipelines based on access patterns              │       │
│  │  • Self-healing: If source schema changes → auto-adapt mapping    │       │
│  │                                                                   │       │
│  │  Semantic Layer:                                                   │       │
│  │  • Business definitions as code ("revenue = orders.amount WHERE   │       │
│  │    status='completed' AND NOT is_test_order")                     │       │
│  │  • dbt metrics, Cube.dev, AtScale, LookML                        │       │
│  │  • One definition used everywhere (dashboard, API, ML)            │       │
│  └──────────────────────────────────────────────────────────────────┘       │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────┐       │
│  │  LAYER 3: AUTOMATED GOVERNANCE & ACCESS                           │       │
│  │  ─────────────────────────────────────────                        │       │
│  │                                                                   │       │
│  │  Policy Engine:                                                   │       │
│  │  • Row-level security (users see only their region's data)        │       │
│  │  • Column masking (PII columns hashed for non-privileged users)   │       │
│  │  • Dynamic: Policies adjust based on context (role + purpose)     │       │
│  │                                                                   │       │
│  │  Access Management:                                               │       │
│  │  • Self-serve catalog: Search, preview, request access            │       │
│  │  • Auto-approve if policy allows (no ticket, instant access)      │       │
│  │  • Audit trail: who accessed what, when, why                      │       │
│  │                                                                   │       │
│  │  Quality Automation:                                              │       │
│  │  • Auto-profiling: Stats computed on every new dataset            │       │
│  │  • Anomaly detection: Alert if distribution shifts                │       │
│  │  • Freshness SLA: Alert if data is stale                         │       │
│  │  • Auto-certification: Dataset gets "gold" badge when quality     │       │
│  │    thresholds met continuously for 30 days                        │       │
│  └──────────────────────────────────────────────────────────────────┘       │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────┐       │
│  │  LAYER 4: DATA SOURCES (Connected, not Copied)                    │       │
│  │  ─────────────────────────────────────────────                    │       │
│  │                                                                   │       │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐  │       │
│  │  │Postgres │ │ Kafka   │ │  S3     │ │Snowflake│ │ APIs    │  │       │
│  │  │(OLTP)   │ │(Stream) │ │(Lake)   │ │(DWH)    │ │(SaaS)   │  │       │
│  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘  │       │
│  │                                                                   │       │
│  │  Connectors: 200+ pre-built (Fivetran/Airbyte/custom)            │       │
│  │  CDC: Real-time change capture from all OLTP systems              │       │
│  │  Catalog: Every source auto-registered + profiled                 │       │
│  └──────────────────────────────────────────────────────────────────┘       │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## When Data Fabric Works / Doesn't

```
DATA FABRIC WORKS WHEN:
═══════════════════════
✓ Organization has 50+ data sources scattered across teams
✓ Data discovery is the #1 problem ("where is customer data?")
✓ Governance is critical (regulated industry: banking, healthcare)
✓ Data duplication is rampant (same data copied 10 places)
✓ Self-serve analytics is the goal (reduce ticket-based access)
✓ You have budget for metadata platforms ($200K-$500K/year tooling)

DATA FABRIC DOESN'T WORK WHEN:
═══════════════════════════════
✗ Data is fundamentally messy (no amount of metadata fixes bad sources)
✗ Small org (< 50 people) — overhead exceeds value
✗ No one curates metadata (knowledge graph rots without maintenance)
✗ Query federation performance is insufficient (need physical ETL anyway)
✗ Political issues (teams refuse to share data — need Data Mesh org change first)

TECHNOLOGY STACK:
════════════════
  Metadata Platform: DataHub, Atlan, Collibra, Alation
  Knowledge Graph: Neo4j, Apache Atlas, OpenMetadata
  Query Federation: Trino/Presto, Dremio, Starburst
  Semantic Layer: dbt metrics, Cube.dev, AtScale
  Governance: Apache Ranger, Privacera, Immuta
  Integration: Fivetran, Airbyte, Debezium
  AI/ML Layer: Custom models for classification, recommendation, anomaly detection
```

## Data Fabric vs Point Solutions

```
MATURITY PROGRESSION:
═════════════════════

Level 1: Point Solutions (most orgs today)
  • Each team has their own tools (team A uses Airflow, team B uses dbt)
  • No unified catalog ("where is the data?" → ask Slack)
  • Manual governance (spreadsheets tracking PII columns)
  
Level 2: Central Catalog (minimum viable Data Fabric)
  • One place to discover all data (DataHub/Atlan)
  • Lineage visible (who produces/consumes)
  • Basic governance (PII tags, access requests)
  
Level 3: Semantic Layer (intermediate)
  • Business definitions as code (dbt metrics)
  • One "revenue" definition used everywhere
  • Self-serve with guardrails
  
Level 4: Full Data Fabric (advanced)
  • AI-powered discovery and recommendations
  • Auto-classification of sensitive data
  • Query federation (access without ETL)
  • Policy-based auto-governance
  • Self-healing pipelines
  
RECOMMENDATION:
  Start at Level 2 (catalog + lineage). It delivers 80% of the value
  at 20% of the cost. Move to Level 3-4 only after Level 2 is mature.
```
