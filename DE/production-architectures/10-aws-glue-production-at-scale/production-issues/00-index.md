# Top 100 AWS Glue Production Issues at Scale

## Master Index

> Real production issues encountered at companies processing **billions of records daily** with AWS Glue.
> Each issue includes: root cause, symptoms, debugging steps, fix, and prevention strategy.

---

## Issue Categories

| File | Category | Issues | Severity Range |
|------|----------|--------|----------------|
| [01-memory-resource-issues.md](01-memory-resource-issues.md) | Memory & Resource Exhaustion | #1-15 | P1-P2 (Critical) |
| [02-job-bookmark-issues.md](02-job-bookmark-issues.md) | Job Bookmark Failures | #16-25 | P1-P3 |
| [03-data-skew-performance.md](03-data-skew-performance.md) | Data Skew & Performance | #26-40 | P2-P3 |
| [04-connectivity-network-issues.md](04-connectivity-network-issues.md) | Connectivity & Network | #41-50 | P1-P2 |
| [05-schema-data-type-issues.md](05-schema-data-type-issues.md) | Schema & Data Type | #51-60 | P2-P3 |
| [06-concurrency-throttling.md](06-concurrency-throttling.md) | Concurrency & Throttling | #61-70 | P1-P2 |
| [07-cost-scaling-issues.md](07-cost-scaling-issues.md) | Cost & Scaling | #71-80 | P2-P3 |
| [08-data-quality-corruption.md](08-data-quality-corruption.md) | Data Quality & Corruption | #81-90 | P1-P2 |
| [09-deployment-configuration.md](09-deployment-configuration.md) | Deployment & Configuration | #91-100 | P2-P3 |

---

## Quick Reference: Top 10 Most Critical Issues

| # | Issue | Category | Frequency | Impact |
|---|-------|----------|-----------|--------|
| 1 | Driver OOM on large shuffles | Memory | Daily at >10TB | Job failure, SLA breach |
| 5 | Executor OOM on skewed partitions | Memory | Weekly | Cascade failures |
| 16 | Job bookmark corruption after failure | Bookmarks | Monthly | Data duplication/loss |
| 26 | Single-key data skew (hot partition) | Performance | Daily | 10x slowdown |
| 41 | JDBC connection pool exhaustion | Network | Weekly | Pipeline stall |
| 61 | Glue API throttling (concurrent jobs) | Throttling | Daily at scale | Orchestration failure |
| 63 | S3 throttling (503 SlowDown) | Throttling | Weekly at PB scale | I/O timeout |
| 71 | Auto-scaling cold start delay | Scaling | Every run | Wasted DPU-hours |
| 81 | Silent data corruption (type coercion) | Quality | Ongoing | Bad analytics |
| 91 | Terraform state drift after manual changes | Deploy | Monthly | Infra inconsistency |

---

## Severity Definitions

```
┌─────────────────────────────────────────────────────────────────────────┐
│  SEVERITY LEVELS                                                         │
├──────────┬──────────────────────────────────────────────────────────────┤
│  P1      │  Data loss, pipeline completely down, SLA breach imminent    │
│          │  Response: Immediate (< 15 min), All-hands                   │
├──────────┼──────────────────────────────────────────────────────────────┤
│  P2      │  Degraded performance, partial failure, workaround exists    │
│          │  Response: Within 1 hour, On-call engineer                   │
├──────────┼──────────────────────────────────────────────────────────────┤
│  P3      │  Non-critical, cosmetic, optimization opportunity            │
│          │  Response: Next business day, Backlog                         │
├──────────┼──────────────────────────────────────────────────────────────┤
│  P4      │  Enhancement, future-proofing, tech debt                     │
│          │  Response: Sprint planning                                    │
└──────────┴──────────────────────────────────────────────────────────────┘
```

---

## How to Use This Guide

1. **Incident Response**: Search by symptom → find issue → apply fix
2. **Prevention**: Read through categories relevant to your pipeline
3. **Architecture Review**: Use as checklist before production launch
4. **Interview Prep**: Each issue demonstrates deep production expertise
5. **Post-mortem Template**: Each issue follows RCA (Root Cause Analysis) format

---

## Common Debugging Workflow

```
┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│  1. DETECT       │────▶│  2. TRIAGE       │────▶│  3. DIAGNOSE     │
│                  │     │                  │     │                  │
│  CloudWatch Alarm│     │  Check severity  │     │  Spark UI        │
│  Job failure     │     │  Check SLA impact│     │  CloudWatch Logs │
│  Data freshness  │     │  Check blast     │     │  Driver logs     │
│  alert           │     │  radius          │     │  Executor logs   │
└──────────────────┘     └──────────────────┘     └────────┬─────────┘
                                                           │
┌──────────────────┐     ┌──────────────────┐             │
│  5. PREVENT      │◀────│  4. FIX          │◀────────────┘
│                  │     │                  │
│  Add monitoring  │     │  Apply fix       │
│  Add guard rails │     │  Verify fix      │
│  Update runbook  │     │  Deploy to prod  │
│  Write post-     │     │  Confirm SLA     │
│  mortem          │     │  met             │
└──────────────────┘     └──────────────────┘
```
