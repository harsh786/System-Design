# Top 100 Production Issues in Temporal at Large Scale

## Overview

These are real production issues encountered when running Temporal at scale (billions of transactions,
millions of concurrent workflows, thousands of workers). Each issue includes:
- **Symptoms** - How you detect the problem
- **Root Cause** - What's actually happening
- **Impact** - Business/system impact
- **Detection** - Metrics/alerts that catch it
- **Resolution** - Step-by-step fix
- **Prevention** - How to avoid it permanently
- **Go Code** - Production fixes where applicable

---

## Issue Categories

| File | Category | Issues | Severity Distribution |
|------|----------|--------|----------------------|
| [01-worker-task-queue-issues.md](./01-worker-task-queue-issues.md) | Worker & Task Queue | #1-#15 | 5 Critical, 6 High, 4 Medium |
| [02-history-state-issues.md](./02-history-state-issues.md) | History & State Management | #16-#30 | 4 Critical, 7 High, 4 Medium |
| [03-database-persistence-issues.md](./03-database-persistence-issues.md) | Database & Persistence | #31-#45 | 6 Critical, 5 High, 4 Medium |
| [04-network-connectivity-issues.md](./04-network-connectivity-issues.md) | Network & Connectivity | #46-#55 | 3 Critical, 5 High, 2 Medium |
| [05-scaling-performance-issues.md](./05-scaling-performance-issues.md) | Scaling & Performance | #56-#70 | 4 Critical, 7 High, 4 Medium |
| [06-workflow-determinism-issues.md](./06-workflow-determinism-issues.md) | Workflow Design & Determinism | #71-#85 | 5 Critical, 6 High, 4 Medium |
| [07-operational-deployment-issues.md](./07-operational-deployment-issues.md) | Operational & Deployment | #86-#100 | 3 Critical, 7 High, 5 Medium |

---

## Quick Reference: Top 10 Most Critical Issues

| # | Issue | Category | Blast Radius |
|---|-------|----------|--------------|
| 1 | Schedule-to-Start Latency Explosion | Worker | All workflows on queue |
| 16 | Workflow History Size Exceeds 50K Events | History | Individual workflow dies |
| 31 | Cassandra Partition Hotspot | Database | Entire cluster degraded |
| 36 | Database Connection Pool Exhaustion | Database | All workflow processing stops |
| 46 | gRPC Deadline Exceeded Cascade | Network | Service-wide outage |
| 56 | Thundering Herd on Worker Restart | Scaling | Spike-induced failures |
| 71 | Non-Determinism Error in Production | Determinism | Workflow permanently stuck |
| 76 | Workflow Versioning Conflict | Determinism | New deployments break old flows |
| 86 | Namespace Rate Limit Exhaustion | Operational | Entire namespace blocked |
| 91 | Temporal Server OOM During Shard Movement | Operational | Cluster instability |

---

## Severity Definitions

| Level | Definition | Response Time |
|-------|-----------|---------------|
| **Critical** | Complete workflow processing halted, data loss risk | < 5 minutes |
| **High** | Significant degradation, SLA at risk | < 15 minutes |
| **Medium** | Partial impact, workaround available | < 1 hour |
| **Low** | Minor inconvenience, no business impact | Next business day |

---

## How to Use This Guide

1. **During Incident**: Search by symptom in the relevant category file
2. **Prevention**: Review all Critical/High issues for your scale tier
3. **Architecture Review**: Use as checklist before going to production
4. **Capacity Planning**: Issues #56-#70 contain scaling thresholds
5. **Code Review**: Issues #71-#85 are workflow design anti-patterns

---

## Scale Tiers Referenced

| Tier | Workflows/Day | Concurrent | Workers | DB Size |
|------|--------------|------------|---------|---------|
| Small | < 100K | < 10K | < 50 | < 100GB |
| Medium | 100K - 10M | 10K - 500K | 50-500 | 100GB-1TB |
| Large | 10M - 100M | 500K - 5M | 500-5000 | 1TB-10TB |
| Massive | 100M - 1B+ | 5M - 50M+ | 5000+ | 10TB+ |

Most issues in this guide manifest at **Large** and **Massive** tiers.
