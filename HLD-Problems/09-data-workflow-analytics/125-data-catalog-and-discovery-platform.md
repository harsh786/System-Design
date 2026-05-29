# Problem 125: Design Data Catalog & Discovery Platform

## Problem Statement

Design a Data Catalog and Discovery Platform similar to Amundsen, DataHub, or Atlan. The platform should help data teams find, understand, and trust data assets across the organization, providing a unified metadata layer over diverse data infrastructure.

## Key Challenges

### 1. Metadata Ingestion
- Auto-discovery from databases, data warehouses, data lakes
- Schema extraction and change detection
- Connector framework for diverse sources (Snowflake, BigQuery, Kafka, S3)
- Incremental vs full-sync ingestion strategies

### 2. Data Lineage
- Column-level lineage tracking
- Lineage extraction from SQL queries, ETL jobs, dbt models
- Impact analysis (what breaks if I change this column?)
- Visual lineage exploration

### 3. Data Quality & Trust
- Automated data profiling (null rates, distributions, cardinality)
- Freshness monitoring and SLO tracking
- Quality score computation
- Custom data quality assertions

### 4. Search & Discovery
- Full-text search across all metadata
- Faceted search (by owner, domain, quality, freshness)
- Relevance ranking (popularity, freshness, quality)
- Natural language queries

### 5. Governance & Compliance
- PII detection and classification (ML-based)
- Data ownership and stewardship assignment
- Access policy integration
- Retention and deletion tracking

### 6. Usage Analytics
- Query log analysis (who queries what, how often)
- Popular datasets and trending data assets
- Unused/stale dataset identification
- Cost attribution per dataset

## Scale Requirements
- Millions of datasets/tables/columns cataloged
- Petabytes of metadata indexed
- Sub-second search response
- Near real-time metadata freshness
- Support for 10K+ data users

## Expected Design Areas
- Metadata graph model
- Ingestion framework
- Search and ranking engine
- Lineage computation engine
- Quality monitoring system
- Access control and PII detection
