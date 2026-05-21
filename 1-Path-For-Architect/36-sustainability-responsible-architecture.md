# Sustainability and Responsible Architecture

Sustainability is increasingly part of cloud architecture, cost optimization, compliance, and executive review. It is not usually the main interview topic, but it can distinguish principal-level architecture judgment.

## Architect-Level Outcome

You should be able to reduce waste in compute, storage, network, and data processing while preserving reliability and business outcomes.

## Sustainability Levers

| Area | Levers |
| --- | --- |
| Compute | right sizing, autoscaling, efficient runtimes, batch scheduling, serverless where appropriate |
| Storage | retention limits, compression, tiering, lifecycle policies, deduplication |
| Network | CDN, regional locality, payload reduction, avoiding unnecessary cross-region transfer |
| Data | partition pruning, query optimization, compaction, avoiding duplicate pipelines |
| AI | model right sizing, caching, batching, token reduction, evaluation before using larger models |
| Operations | shutting idle environments, scheduled scaling, cost and carbon dashboards |

## Responsible Architecture Principles

- Do not collect data without a purpose.
- Do not retain data longer than necessary.
- Match reliability targets to business need.
- Use smaller models and systems when they satisfy requirements.
- Prefer efficient algorithms and data structures.
- Make cost and resource usage visible to teams.
- Reduce duplicate platforms and pipelines.

## Trade-Offs

| Decision | Sustainability Benefit | Risk |
| --- | --- | --- |
| Lower retention | less storage and cost | compliance or analytics loss |
| Smaller model | lower inference cost | lower answer quality |
| Regional locality | lower network transfer | less global resilience |
| Aggressive autoscaling | less idle compute | cold start or latency risk |
| Batch instead of real-time | less compute pressure | less freshness |

## Sustainability Metrics

- CPU utilization.
- Idle resource percentage.
- Storage growth by class.
- Data retained past policy.
- Cross-region egress.
- Cost per request/user/event.
- Model tokens per successful task.
- Cache hit ratio.
- Query bytes scanned.
- Unused environments and resources.

## Interview Questions

1. How do you reduce cloud waste without reducing reliability?
2. How do you design data retention for cost, privacy, and sustainability?
3. How do you make AI inference more efficient?
4. When is real-time processing not justified?
5. How do you include sustainability in architecture reviews?
6. How do you balance active-active reliability with cost and resource usage?

