# Domain-Specific Architecture Deep Dives

Architect interviews often use familiar domains to test whether you can apply fundamentals under real business constraints. This file gives domain playbooks.

## How to Use This File

For each domain, prepare:

- Functional requirements.
- Non-functional requirements.
- Data model.
- API and event contracts.
- Core invariants.
- Failure modes.
- Security/compliance concerns.
- Observability dashboard.
- Scaling bottlenecks.
- Trade-offs and migration path.

## Fintech and Payments

### Core Systems

- Payment gateway.
- Wallet.
- Ledger.
- Payouts.
- Fraud detection.
- Reconciliation.
- Disputes and chargebacks.
- Risk and compliance reporting.

### Must-Know Concepts

- Idempotency keys.
- Double-entry accounting.
- Immutable ledger entries.
- Authorization vs capture vs settlement.
- Webhook retries and dedupe.
- PCI DSS scope reduction.
- Tokenization.
- Reconciliation against processor/bank reports.
- Audit trails and non-repudiation.
- Limits, velocity checks, fraud rules.

### Core Invariants

- Money is never created or lost.
- Every balance change is explained by immutable ledger entries.
- External provider callbacks are idempotent.
- User-visible payment state can lag provider state but must converge.
- Refunds and chargebacks are separate financial events, not destructive updates.

### Architecture Sketch

```text
Client -> Payment API -> Idempotency Store -> Payment Orchestrator -> Provider Adapter
                         |                    |
                         -> Ledger Service    -> Webhook Processor -> Reconciliation
                         -> Risk Service      -> Audit Store
```

### Interview Traps

- Updating account balance directly without ledger entries.
- Treating provider webhook as trusted and ordered.
- Ignoring duplicate payment attempts.
- Ignoring reconciliation.
- Mixing transactional traffic with analytics traffic.

## Multi-Tenant SaaS

### Tenancy Models

| Model | Use When | Trade-off |
| --- | --- | --- |
| Shared DB, shared schema | Small tenants, low cost. | Strong app-level isolation required. |
| Shared DB, tenant column | Common SaaS model. | Risk of cross-tenant leaks. |
| Schema per tenant | Medium isolation. | Migration and operational complexity. |
| Database per tenant | Strong isolation. | Higher cost and fleet management. |
| Cell-based architecture | Large scale and blast-radius control. | Routing, operations, and capacity complexity. |

### Must-Know Concepts

- Tenant isolation.
- Tenant-aware auth and authorization.
- Quotas and rate limits.
- Entitlements and feature flags.
- Billing metering.
- Data residency.
- Tenant-level backup/restore.
- Noisy neighbor control.
- Tenant migration between cells.
- Admin impersonation audit.

### Core Invariants

- A request can access only one authorized tenant context unless explicitly cross-tenant admin.
- Tenant ID must be part of auth context, not just request input.
- Background jobs must preserve tenant context.
- Logs and analytics must not leak tenant data.

## Marketplace and Booking Systems

### Core Systems

- Catalog/listings.
- Availability.
- Pricing.
- Search and ranking.
- Reservation/hold.
- Payment.
- Fulfillment.
- Reviews.
- Trust and safety.

### Core Invariants

- Inventory cannot be oversold beyond defined business rules.
- Holds expire reliably.
- Payment confirmation and booking confirmation converge.
- Search index may be stale, but booking source of truth must be correct.

### Patterns

- Search index for discovery, transactional DB for reservation.
- Temporary holds with TTL.
- Optimistic concurrency for low contention.
- Pessimistic locks for scarce high-value inventory.
- Saga for booking-payment-confirmation.
- Outbox events for downstream fulfillment.

### Interview Questions

- Design movie ticket booking.
- Design hotel booking.
- Design airline reservation.
- Design ride-hailing matching.
- Design food delivery dispatch.

## AdTech and Real-Time Bidding

### Must-Know Concepts

- Bid request latency budgets, often tens of milliseconds.
- Real-time feature lookup.
- User/device identity.
- Budget pacing.
- Frequency capping.
- Auction mechanics.
- Fraud/bot detection.
- Attribution.
- Stream processing for impressions, clicks, conversions.

### Architecture Sketch

```text
Exchange -> Bidder Edge -> Feature Cache -> Model/Rules -> Bid Response
                       -> Budget Service
                       -> Event Stream -> Attribution/Reporting
```

### Hard Problems

- Low latency under high QPS.
- Global traffic routing.
- Hot advertisers/campaigns.
- Accurate budget spend with distributed bidders.
- Privacy and consent.
- Fraud and invalid traffic.

## Media Streaming

### Must-Know Concepts

- Upload pipeline.
- Transcoding ladder.
- Object storage.
- CDN.
- DRM.
- Playback manifests.
- Adaptive bitrate.
- Recommendation feeds.
- Watch history.
- Regional rights.

### Failure Modes

- Transcoding backlog.
- CDN cache miss storm.
- Hot viral content.
- Regional rights leakage.
- Playback startup latency.
- Inconsistent watch progress.

### Interview Questions

- Design YouTube.
- Design Netflix.
- Design live streaming.
- Design short video feed.
- Design video upload and processing.

## Healthcare and Regulated Data

### Must-Know Concepts

- PHI/PII classification.
- Consent and purpose limitation.
- Audit trails.
- Data retention.
- Data deletion.
- Encryption and key management.
- Break-glass access.
- Least privilege.
- Interoperability standards where relevant.
- High availability for critical workflows.

### Architecture Priorities

- Security and privacy first.
- Explicit data ownership.
- Strong auditability.
- Regional and regulatory constraints.
- Controlled data sharing.
- Disaster recovery and continuity plans.

## IoT and Device Platforms

### Must-Know Concepts

- Device identity and provisioning.
- MQTT.
- Certificate rotation.
- Telemetry ingestion.
- Command and control.
- Offline buffering.
- Time-series storage.
- Firmware updates.
- Digital twins.
- Fleet monitoring.

### Architecture Sketch

```text
Device -> MQTT Broker -> Ingestion Stream -> Rules Engine -> Time-Series Store
                           |                  -> Alerting
                           -> Device Registry -> Command Service
```

### Failure Modes

- Device reconnect storm.
- Clock skew.
- Duplicate telemetry.
- Offline devices replaying old data.
- Certificate expiry.
- Firmware rollout failure.

## Enterprise Internal Platforms

### Common Platforms

- Identity platform.
- API platform.
- Event platform.
- Developer platform.
- Observability platform.
- Data platform.
- ML/AI platform.
- Secrets and policy platform.

### Architect Focus

- Self-service workflows.
- Golden paths.
- Guardrails.
- Paved-road adoption.
- Backward compatibility.
- Multi-team ownership.
- Chargeback/showback.
- Documentation and support model.

## Domain Practice Matrix

| Domain | Primary Risk | Deep Dive |
| --- | --- | --- |
| Payments | Correctness and audit. | Ledger, idempotency, reconciliation. |
| SaaS | Tenant isolation. | Auth context, quotas, data partitioning. |
| Marketplace | Inventory correctness. | Holds, concurrency, search staleness. |
| AdTech | Ultra-low latency. | Feature cache, pacing, stream processing. |
| Media | CDN and processing scale. | Transcoding, ABR, cache strategy. |
| Healthcare | Privacy and compliance. | Consent, audit, encryption. |
| IoT | Fleet reliability. | Device identity, MQTT, time-series. |
| Internal platform | Adoption and operability. | Self-service, standards, ownership. |

