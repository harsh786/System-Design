# Business Continuity, Disaster Recovery, and Crisis Management

Reliability is not complete until you can recover from major failures. This track covers RTO/RPO, backup integrity, regional failover, cyber recovery, crisis communication, and executive-level incident handling.

## Architect-Level Outcome

You should be able to design recovery strategies by business criticality, prove them through drills, and communicate clearly during crisis.

## Core Terms

| Term | Meaning |
| --- | --- |
| RTO | Recovery Time Objective: how quickly the service must recover. |
| RPO | Recovery Point Objective: how much data loss is acceptable. |
| MTD | Maximum Tolerable Downtime. |
| DR | Disaster recovery. |
| BCP | Business continuity planning. |
| Backup integrity | Proof that backups can actually restore. |
| Cyber recovery | Recovery after ransomware, destructive attack, or credential compromise. |

## Criticality Tiers

| Tier | Example | RTO | RPO | Strategy |
| --- | --- | --- | --- | --- |
| Tier 0 | identity, payments, core ordering | minutes | seconds/minutes | active-active or hot standby |
| Tier 1 | customer APIs, inventory | < 1 hour | minutes | warm standby or active-passive |
| Tier 2 | admin tools, reporting | hours | hours | pilot light or restore from backup |
| Tier 3 | internal analytics | days | day | backup restore |

## DR Strategies

| Strategy | Description | Pros | Cons |
| --- | --- | --- | --- |
| Backup and restore | Restore infrastructure and data after failure. | cheapest | slowest |
| Pilot light | Minimal core infra always running. | lower cost than warm standby | scaling during recovery |
| Warm standby | Scaled-down full environment. | faster recovery | ongoing cost |
| Hot standby | Fully running passive region. | fast failover | high cost |
| Active-active | Multiple regions serve traffic. | lowest RTO | complexity and consistency risk |

## RTO/RPO Design Process

```text
Business impact -> Criticality tier -> RTO/RPO -> Data replication -> Failover architecture -> Runbook -> Drill -> Evidence
```

Do not assign active-active to every system. Match recovery strategy to business impact.

## Backup Strategy

Checklist:

- Full, incremental, and point-in-time recovery where needed.
- Encryption of backups.
- Separate access controls.
- Immutable or locked backups for cyber recovery.
- Cross-region or offsite storage.
- Restore tests.
- Backup monitoring.
- Retention policy.
- Documented owner.

## Regional Failover

Design points:

- DNS or global traffic manager.
- Health checks.
- Data replication.
- Read-only degraded mode if writes are unsafe.
- Dependency availability in failover region.
- Secrets and certificates in failover region.
- Capacity headroom.
- Runbook with decision authority.
- Failback plan.

## Cyber Recovery

Cyber recovery differs from normal DR because the latest backup may be compromised.

Design controls:

- Immutable backups.
- Separate admin credentials.
- Break-glass access.
- Malware scanning before restore.
- Known-good restore points.
- Audit log preservation.
- Secret rotation after recovery.
- Isolation environment for investigation.

## Crisis Management

Incident roles:

- Incident commander.
- Technical lead.
- Communications lead.
- Operations lead.
- Scribe.
- Executive liaison.

Communication principles:

- State impact, not speculation.
- Give next update time.
- Separate internal technical details from customer-facing updates.
- Track decisions and timestamps.
- Communicate mitigation before root cause if impact is ongoing.
- Follow with postmortem and action items.

## DR Drill Plan

For each critical service:

1. Define failure scenario.
2. Define success criteria.
3. Notify participants.
4. Execute runbook.
5. Measure RTO/RPO.
6. Validate data correctness.
7. Validate customer-facing behavior.
8. Record gaps.
9. Assign action items.
10. Repeat until target is met.

## Interview Questions

1. How do you choose active-active vs warm standby?
2. How do you prove backups are usable?
3. What is the difference between failover and failback?
4. How do you recover after ransomware?
5. How do you define RTO/RPO for a payment system?
6. How do you communicate during a major outage?
7. How do you handle data divergence after regional failover?

