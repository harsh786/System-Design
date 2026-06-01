# Top 100 Production Issues in S3 + Iceberg at Large Scale

## Overview

These are real production issues encountered at companies running Iceberg at scale
(Netflix, Apple, LinkedIn, Uber, Stripe, Airbnb, and large banks/fintechs).

Each issue includes: root cause, symptoms, impact, fix, and prevention.

---

## Issue Categories

| File | Category | Issues | Severity |
|------|----------|--------|----------|
| `01-metadata-catalog-issues.md` | Metadata & Catalog Failures | #1-15 | Critical/High |
| `02-small-files-compaction-issues.md` | Small Files & Compaction | #16-30 | High |
| `03-concurrency-write-conflicts.md` | Concurrency & Write Conflicts | #31-45 | Critical |
| `04-s3-storage-layer-issues.md` | S3 Storage Layer Problems | #46-58 | High/Critical |
| `05-query-performance-issues.md` | Query Performance & Planning | #59-72 | High |
| `06-streaming-cdc-realtime-issues.md` | Streaming, CDC & Real-Time | #73-86 | Critical |
| `07-operations-maintenance-cost.md` | Operations, Maintenance & Cost | #87-100 | Medium/High |

---

## Severity Definitions

| Level | Impact | Response Time |
|-------|--------|---------------|
| **P0 - Critical** | Data loss, pipeline down, serving impacted | < 15 min |
| **P1 - High** | Performance degradation, SLA breach risk | < 1 hour |
| **P2 - Medium** | Increased cost, manual intervention needed | < 4 hours |
| **P3 - Low** | Suboptimal, tech debt accumulation | Next sprint |

---

## Top 10 Most Common (Quick Reference)

| # | Issue | Category | Frequency |
|---|-------|----------|-----------|
| 1 | Small files explosion from streaming | Compaction | Daily |
| 2 | S3 throttling (503 SlowDown) | S3 | Weekly |
| 3 | Metadata file explosion (too many snapshots) | Metadata | Weekly |
| 4 | Commit conflicts on hot tables | Concurrency | Daily |
| 5 | Query planning timeout (too many manifests) | Performance | Daily |
| 6 | Orphan files consuming storage | Operations | Ongoing |
| 7 | Partition explosion (too many partitions) | Metadata | Monthly |
| 8 | Delete file accumulation (MoR read amplification) | Compaction | Daily |
| 9 | OOM during compaction of large partitions | Operations | Weekly |
| 10 | Schema evolution breaking downstream consumers | Catalog | Monthly |

---

## Reading Guide

Each issue follows this structure:

```
## Issue #N: [Title]

**Severity:** P0/P1/P2/P3
**Frequency:** How often this occurs at scale
**Affected Components:** What breaks
**First seen at:** Company/scale where this typically appears

### Symptoms
- What you observe (logs, metrics, user reports)

### Root Cause
- Why this happens (technical deep-dive)

### Impact
- Business/technical consequences

### Immediate Fix (Stop the bleeding)
- What to do RIGHT NOW

### Permanent Fix (Prevent recurrence)
- Long-term solution with code/config

### Prevention
- How to never see this again

### Monitoring
- Alerts to catch this early
```
