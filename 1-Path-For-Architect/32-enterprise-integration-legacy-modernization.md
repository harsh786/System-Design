# Enterprise Integration and Legacy Modernization

Many architect roles involve systems that already exist: monoliths, ERPs, CRMs, mainframes, batch jobs, file drops, and manual processes. This track covers how to modernize without breaking the business.

## Architect-Level Outcome

You should be able to integrate and modernize legacy systems with low risk, clear ownership, measurable progress, and rollback paths.

## Integration Styles

| Style | Use When | Risk |
| --- | --- | --- |
| Point-to-point API | Simple integration with clear ownership. | Spaghetti dependencies over time. |
| API facade | Legacy must be hidden behind stable contract. | Facade can become overloaded. |
| Batch file exchange | Partner or legacy supports only files. | Delay, reconciliation, schema drift. |
| CDC | Need near-real-time sync from legacy DB. | Schema changes, ordering, replay. |
| Event-driven integration | Multiple consumers need state changes. | Event contract governance required. |
| ESB/iPaaS | Enterprise integration standard or many SaaS connectors. | Central bottleneck, vendor lock-in. |
| Strangler fig | Incremental replacement of monolith. | Routing and data consistency complexity. |

## Legacy Modernization Formula

```text
Map current state -> Identify business-critical flows -> Add observability -> Wrap with facade -> Extract capability -> Migrate data -> Run in parallel -> Cut over -> Retire old path
```

## Current-State Discovery

Find:

- Business capabilities supported.
- Upstream and downstream dependencies.
- Data ownership and source of truth.
- Batch jobs and schedules.
- Hidden manual processes.
- Peak traffic and seasonal events.
- Operational runbooks.
- Known incidents.
- Compliance constraints.
- Team ownership and knowledge gaps.

## Strangler Pattern

```text
Client -> Routing Layer -> New Service for migrated capability
                     -> Legacy System for remaining capability
```

Steps:

1. Put a routing layer in front of the legacy system.
2. Identify one bounded capability.
3. Build new service behind stable contract.
4. Sync required data.
5. Shadow or parallel-run new behavior.
6. Move small traffic slice.
7. Monitor correctness and latency.
8. Increase traffic.
9. Retire legacy code path.

## Anti-Corruption Layer

Use when legacy data models or APIs do not match the domain model.

Responsibilities:

- Translate legacy models to domain models.
- Hide legacy errors and quirks.
- Normalize IDs and statuses.
- Add retries and timeouts.
- Preserve auditability.
- Prevent legacy concepts from leaking into new services.

## Data Migration Patterns

| Pattern | Use When |
| --- | --- |
| Big-bang migration | Small, low-risk, easily reversible system. |
| Backfill plus CDC | Large dataset with live writes. |
| Dual-write with reconciliation | Temporary bridge between old and new. |
| Event replay | Events are complete and reliable source. |
| Parallel run | Need correctness comparison before cutover. |

Migration checklist:

- Source-to-target mapping.
- Data quality checks.
- Idempotent backfill.
- Checkpointing and resume.
- Reconciliation reports.
- Cutover criteria.
- Rollback plan.
- Audit trail.

## Enterprise System Integration

### ERP/CRM/SaaS

Examples: SAP, Salesforce, Workday, ServiceNow.

Design points:

- Rate limits.
- Bulk APIs.
- Webhook reliability.
- Object model mapping.
- Tenant and environment separation.
- Sandbox testing.
- API version changes.
- Data ownership and reconciliation.

### Mainframe

Design points:

- Batch windows.
- File formats.
- Transaction boundaries.
- Limited direct query access.
- High correctness requirements.
- Change approval processes.
- API facade or event extraction.

### File-Based Integration

Design points:

- Naming convention.
- Schema version.
- Encryption.
- Checksums.
- Delivery acknowledgment.
- Duplicate detection.
- Partial file handling.
- Reprocessing and quarantine.

## Modernization Risk Register

| Risk | Mitigation |
| --- | --- |
| Unknown dependency | Traffic analysis, logs, stakeholder interviews. |
| Data mismatch | Reconciliation reports and domain review. |
| Cutover failure | Canary, rollback, parallel run. |
| Legacy team bottleneck | Knowledge transfer and documentation. |
| Scope explosion | Capability-by-capability roadmap. |
| Integration latency | Async flow, caching, local read models. |

## Interview Questions

1. How would you migrate a monolithic order system to services?
2. How do you integrate with SAP/Salesforce safely?
3. When is CDC better than dual writes?
4. How do you design an anti-corruption layer?
5. How do you modernize a file-based nightly batch process?
6. How do you prove migration correctness?
7. How do you decide what to extract first from a monolith?

