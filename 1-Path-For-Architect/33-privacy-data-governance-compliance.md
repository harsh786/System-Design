# Privacy, Data Governance, and Compliance

World-class architects understand that data design is not only storage and query performance. It also includes ownership, privacy, retention, deletion, consent, residency, auditability, and regulatory controls.

## Architect-Level Outcome

You should be able to design systems that protect sensitive data, prove compliance controls, and keep data usable through contracts, ownership, lineage, and quality.

## Data Governance Areas

| Area | Outcome |
| --- | --- |
| Classification | Know which data is public, internal, confidential, restricted, PII, PHI, PCI, or secrets. |
| Ownership | Every dataset has a business and technical owner. |
| Data contracts | Producers publish schema, freshness, quality, and compatibility guarantees. |
| Lineage | Consumers can trace data back to sources and transformations. |
| Quality | Freshness, completeness, validity, uniqueness, and reconciliation are measured. |
| Retention | Data is retained only as long as needed. |
| Deletion | User and tenant deletion can be executed and verified. |
| Residency | Data stays in approved regions. |
| Access control | Users and systems get least-privilege access. |

## Privacy-by-Design Checklist

- Minimize data collected.
- Define purpose for collection and use.
- Classify data at ingestion.
- Encrypt sensitive data in transit and at rest.
- Tokenize or mask sensitive fields where possible.
- Separate identifiers from behavioral data where possible.
- Enforce access by role, purpose, and tenant.
- Audit sensitive reads and exports.
- Define retention and deletion policy.
- Test deletion and restore behavior.
- Prevent sensitive data in logs, traces, prompts, and analytics.

## Data Classification Matrix

| Class | Examples | Controls |
| --- | --- | --- |
| Public | marketing pages, public docs | integrity and availability |
| Internal | internal runbooks, metrics | authenticated access |
| Confidential | contracts, financial reports | RBAC, audit, encryption |
| Restricted | PII, PHI, PCI, secrets | strict access, masking, DLP, audit |
| Regulated | healthcare, payment, residency-bound data | policy enforcement, retention, compliance evidence |

## Consent and Purpose Limitation

Design points:

- Store consent version and timestamp.
- Associate consent with purpose.
- Make downstream processing purpose-aware.
- Support consent withdrawal.
- Stop future processing after withdrawal.
- Evaluate whether historical data must be deleted or retained for legal basis.

## Data Deletion Architecture

```text
Deletion Request -> Identity Verification -> Deletion Orchestrator
                     -> Service Delete APIs
                     -> Data Lake Delete Jobs
                     -> Search/Cache Purge
                     -> Audit Evidence
```

Hard parts:

- Backups.
- Derived data.
- Event logs.
- Third-party processors.
- Search indexes.
- Caches.
- ML features and embeddings.
- Legal hold exceptions.

## Data Residency

Design points:

- Region-aware tenant placement.
- Regional encryption keys.
- Regional backups.
- Regional analytics.
- Cross-region support access controls.
- Avoid accidental replication through logs, traces, and data lakes.
- Route requests to correct region.

## Data Contracts

Each data product or event should define:

- Owner.
- Schema.
- Semantics.
- Compatibility policy.
- Freshness SLO.
- Quality checks.
- Retention.
- Classification.
- Allowed consumers.
- Deprecation policy.

## Compliance Evidence

Architects should know how controls are proven:

- Access review records.
- Audit logs.
- Change management records.
- Encryption configuration.
- Backup/restore test evidence.
- Incident response records.
- Vulnerability scan results.
- Vendor risk assessment.
- Data retention/deletion evidence.
- Policy-as-code results.

## Interview Questions

1. How do you implement right-to-delete in an event-driven system?
2. How do you prevent PII from leaking into logs and traces?
3. How do you design data residency for a global SaaS platform?
4. What is a data contract and why does it matter?
5. How do you handle consent withdrawal?
6. How do you govern data lake access?
7. How do you prove compliance controls to auditors?

