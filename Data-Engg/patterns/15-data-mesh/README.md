# Pattern 15: Data Mesh

## Core Principles

```
Data Mesh is an ORGANIZATIONAL pattern (not just technology).
It decentralizes data ownership to domain teams.

FOUR PRINCIPLES:
═══════════════

1. DOMAIN OWNERSHIP
   • Each business domain owns its data end-to-end
   • Orders team owns order data (pipeline, quality, serving)
   • No central "data team" bottleneck
   • Domain experts write the transformations (they know the data best)

2. DATA AS A PRODUCT
   • Treat data like a product with users (other teams)
   • SLAs: freshness, quality, availability
   • Documentation: schema, semantics, usage examples
   • Discoverability: registered in catalog, searchable

3. SELF-SERVE DATA PLATFORM
   • Platform team provides infrastructure as a service
   • Domain teams deploy pipelines without platform tickets
   • Templates: "Deploy a new data product in 30 minutes"
   • Abstractions: Don't need to know K8s to deploy Flink job

4. FEDERATED COMPUTATIONAL GOVERNANCE
   • Global standards (interoperability, security, compliance)
   • Local execution (each domain implements its way)
   • Automated policy enforcement (not manual review)
   • Example: "All PII fields must be tagged" → enforced by platform
```

## Architecture

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                        DATA MESH ARCHITECTURE                                      │
├──────────────────────────────────────────────────────────────────────────────────┤
│                                                                                   │
│  DOMAIN DATA PRODUCTS                                                             │
│  ═════════════════════                                                            │
│                                                                                   │
│  ┌─────────────────────────┐  ┌─────────────────────────┐                       │
│  │  ORDERS DOMAIN           │  │  CUSTOMERS DOMAIN        │                       │
│  │                          │  │                          │                        │
│  │  Owner: Orders Team      │  │  Owner: Customer Team    │                       │
│  │  Data Products:          │  │  Data Products:          │                       │
│  │  • orders_placed         │  │  • customer_profiles     │                       │
│  │  • orders_fulfilled      │  │  • customer_segments     │                       │
│  │  • order_metrics_daily   │  │  • customer_ltv          │                       │
│  │                          │  │                          │                        │
│  │  SLA: 99.9%, <5min fresh │  │  SLA: 99.5%, <1hr fresh │                       │
│  │  Format: Iceberg (SQL)   │  │  Format: Iceberg (SQL)   │                       │
│  │  Access: API + SQL       │  │  Access: SQL + API       │                       │
│  └─────────────────────────┘  └─────────────────────────┘                       │
│                                                                                   │
│  ┌─────────────────────────┐  ┌─────────────────────────┐                       │
│  │  PAYMENTS DOMAIN         │  │  MARKETING DOMAIN        │                       │
│  │                          │  │                          │                        │
│  │  Owner: Payments Team    │  │  Owner: Marketing Team   │                       │
│  │  Data Products:          │  │  Data Products:          │                       │
│  │  • payment_transactions  │  │  • campaign_performance  │                       │
│  │  • payment_failures      │  │  • attribution_events    │                       │
│  │  • revenue_by_method     │  │  • funnel_metrics        │                       │
│  └─────────────────────────┘  └─────────────────────────┘                       │
│                                                                                   │
│  SELF-SERVE PLATFORM                                                              │
│  ═══════════════════                                                              │
│  ┌────────────────────────────────────────────────────────────────────────────┐  │
│  │                                                                             │  │
│  │  INFRASTRUCTURE PLANE (managed by platform team):                           │  │
│  │  ├── Compute: Kubernetes clusters (Spark, Flink, dbt)                       │  │
│  │  ├── Storage: S3 + Iceberg (shared object store)                            │  │
│  │  ├── Streaming: Kafka clusters (shared event bus)                           │  │
│  │  ├── Catalog: DataHub (discovery, lineage, governance)                      │  │
│  │  ├── Quality: Great Expectations (automated checks)                         │  │
│  │  └── Security: SSO, RBAC, encryption, audit logging                         │  │
│  │                                                                             │  │
│  │  DEVELOPER EXPERIENCE:                                                      │  │
│  │  ├── Templates: "Create data product" → scaffolds pipeline + tests          │  │
│  │  ├── CI/CD: Push to git → auto-deploy pipeline                              │  │
│  │  ├── Monitoring: Built-in dashboards for every data product                 │  │
│  │  └── Documentation: Auto-generated from schema + annotations                │  │
│  │                                                                             │  │
│  └────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                   │
│  FEDERATED GOVERNANCE                                                             │
│  ════════════════════                                                             │
│  ┌────────────────────────────────────────────────────────────────────────────┐  │
│  │  Global Policies (enforced by platform, defined by governance council):     │  │
│  │  • All PII must be tagged and access-controlled                             │  │
│  │  • All data products must have schema + documentation                       │  │
│  │  • All data products must pass quality gates before publishing               │  │
│  │  • Naming conventions: {domain}_{entity}_{aggregation_level}                 │  │
│  │  • Retention: Defined per classification (PII: 3yr, logs: 90d)              │  │
│  │  • Interop: All products queryable via standard SQL                          │  │
│  └────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                   │
└──────────────────────────────────────────────────────────────────────────────────┘
```

## When Data Mesh Works (and When It Doesn't)

```
WORKS WELL:
  • Large organizations (100+ engineers touching data)
  • Multiple distinct domains (orders, payments, users, products)
  • Distributed teams (domain teams in different offices/time zones)
  • Existing data team is a bottleneck (6-month backlog)
  • Need data freshness AND domain expertise in transforms

DOESN'T WORK:
  • Small companies (< 50 engineers) → overhead too high
  • Single product → not enough domains to distribute
  • Teams lack data engineering skills → need central support
  • No platform investment → chaos without self-serve
  • Premature adoption → over-engineering simple problems

TYPICAL JOURNEY:
  Stage 1: Central data team (5-10 people, all pipelines)
  Stage 2: Embedded engineers (in each domain, reporting to data team)
  Stage 3: Data mesh (domain teams own data, platform team enables)
  
  Transition from 1→3 typically takes 2-3 years.
```

