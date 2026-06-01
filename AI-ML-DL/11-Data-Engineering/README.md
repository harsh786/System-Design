# Data Engineering for ML

## Why Data Engineering Matters

> "More data beats better algorithms, but better data beats more data." — Peter Norvig (paraphrased)

```
┌─────────────────────────────────────────────────────────┐
│                   THE DATA FLYWHEEL                       │
│                                                          │
│   Better Data ──→ Better Models ──→ Better Products     │
│       ↑                                    │            │
│       └────── More Users ←────────────────┘            │
│                                                          │
│   Companies that master this flywheel WIN.              │
└─────────────────────────────────────────────────────────┘
```

## The Reality of ML in Production

| Activity                  | % of Time |
|---------------------------|-----------|
| Data collection & cleaning | 40%       |
| Feature engineering        | 20%       |
| Model training & tuning    | 15%       |
| Infrastructure & deployment| 15%       |
| Monitoring & maintenance   | 10%       |

**80% of ML work is data work.**

## What Data Engineering Covers

```
┌──────────────────────────────────────────────────────────────┐
│                    DATA ENGINEERING STACK                      │
├──────────────────────────────────────────────────────────────┤
│  Sources        │ Ingestion      │ Storage        │ Serving  │
│  ─────────      │ ─────────      │ ─────────      │ ──────── │
│  APIs           │ Kafka          │ Data Lake      │ Feature  │
│  Databases      │ Airflow        │ Data Warehouse │ Store    │
│  Logs           │ Spark          │ Delta Lake     │ APIs     │
│  Events         │ Flink          │ Iceberg        │ Caches   │
│  Files          │ dbt            │ BigQuery       │ Models   │
└──────────────────────────────────────────────────────────────┘
```

## Learning Path

| # | Topic | Key Skills |
|---|-------|-----------|
| 01 | [SQL Mastery](./01-SQL-Mastery/) | Queries, window functions, optimization |
| 02 | [Apache Spark](./02-Apache-Spark/) | Distributed computing, PySpark |
| 03 | [ETL/ELT Pipelines](./03-ETL-ELT-Pipelines/) | Airflow, dbt, orchestration |
| 04 | [Data Modeling](./04-Data-Modeling/) | Star schema, feature stores |
| 05 | [Streaming Pipelines](./05-Streaming-Pipelines/) | Kafka, Flink, real-time ML |

## Data > Algorithms: Evidence

1. **Google's Unreasonable Effectiveness of Data (2009)** - Simple models + massive data beat complex models + small data
2. **GPT scaling laws** - Performance scales predictably with data quantity and quality
3. **Tesla's data engine** - More driving data → better autopilot → more users → more data
4. **Recommendation systems** - Netflix, Spotify win with data diversity, not model novelty

## Core Principles

1. **Data Quality > Data Quantity** - Garbage in, garbage out
2. **Reproducibility** - Every transformation must be traceable
3. **Idempotency** - Re-running pipelines produces same results
4. **Schema Evolution** - Data formats change; handle it gracefully
5. **Freshness vs Cost** - Real-time is expensive; batch when possible
