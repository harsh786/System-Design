# Problem 132: Design Data Privacy / GDPR Compliance Engine

## Problem Statement

Design a centralized data privacy and GDPR compliance engine that enables an organization
to manage user consent, discover and classify personal data across all systems, fulfill
data subject access requests (DSARs), enforce retention policies, and maintain audit trails
for regulatory compliance. The platform must support GDPR, CCPA, HIPAA, and other privacy
regulations simultaneously across a global user base.

## Key Challenges

1. **Data Subject Access Requests (DSAR)**: Orchestrate the fulfillment of right-to-access
   and right-to-be-forgotten requests across hundreds of heterogeneous data stores within
   the legally mandated 30-day SLA.
2. **Consent Management**: Store and propagate granular, purpose-based consent (marketing,
   analytics, personalization) with real-time enforcement across all downstream systems.
3. **Data Classification and Inventory**: Automatically discover and classify PII, PHI,
   and PCI data across databases, data lakes, caches, logs, and backups using ML and
   pattern matching.
4. **Data Retention Enforcement**: Apply per-category retention policies with automated
   purging, respecting legal holds and cross-references between data stores.
5. **Cross-Border Data Transfer Compliance**: Enforce data residency rules, track data
   flows across regions, and ensure appropriate safeguards (SCCs, BCRs) are in place.
6. **Privacy Impact Assessments**: Automate DPIA workflows for new data processing
   activities, integrating with CI/CD to catch privacy issues before deployment.
7. **Breach Notification Workflow**: Detect potential breaches, assess impact scope,
   and orchestrate 72-hour notification to authorities and affected users.
8. **Anonymization and Pseudonymization**: Provide tooling for k-anonymity, differential
   privacy, and tokenization that preserves data utility while protecting privacy.

## Scale Requirements

- 500M+ user profiles with consent records
- 1,000+ data stores to scan and classify
- DSAR fulfillment within 30 days (target: <7 days)
- Consent decisions enforced within <5 seconds of change
- 10,000+ data retention policies active simultaneously
- Continuous PII scanning of petabytes of data
- Audit trail immutable and queryable for 7+ years

## Expected Discussion Areas

- Cryptographic erasure vs hard deletion
- Consent propagation with eventual consistency
- PII detection accuracy (precision vs recall trade-offs)
- Legal hold conflict resolution with retention policies
- Handling PII in backups and append-only logs
- Differential privacy for analytics on sensitive data
