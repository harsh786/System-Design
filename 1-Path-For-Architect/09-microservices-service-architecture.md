# Microservices and Service Architecture

_Split from `../world_class_pro_architect_master_roadmap.md`. The original source file is intentionally untouched._

---

# 10. Microservices Design and Patterns Roadmap

## 10.1 Service Boundaries

Design services around business capabilities and bounded contexts, not around technical layers.

### Good Boundaries

- Clear ownership.
- Independent deployability.
- Private data ownership.
- Stable APIs/events.
- Minimal synchronous dependencies.
- Separate scalability and reliability needs.

### Bad Boundaries

- Service per table.
- Service per CRUD screen.
- Shared database across services.
- Chatty synchronous calls.
- Distributed monolith.
- No clear team ownership.

## 10.2 Core Microservice Patterns

### API Gateway

- Authentication.
- Routing.
- Rate limiting.
- Request/response transformation.
- TLS termination.
- Observability.

### Backend for Frontend

- UI-specific API aggregation.
- Reduces client complexity.
- Avoids one generic API serving every consumer poorly.

### Database Per Service

- Each service owns its data.
- Other services access through APIs or events.
- Enables autonomy but creates consistency challenges.

### Saga

- Coordinates long-running business transactions.
- Uses local transactions and compensation.
- Can be orchestrated or choreographed.

### CQRS

- Separate write model from read model.
- Useful when reads and writes have different scale/model needs.

### Event Sourcing

- Store state changes as events.
- Rebuild state through replay.
- Powerful but operationally complex.

### Transactional Outbox

- Save business state and event in same local transaction.
- Separate relay publishes event.
- Prevents DB commit success but event publish failure.

### Inbox Pattern

- Store processed message IDs.
- Enables idempotent consumers.

### CDC

- Capture database changes and publish events.
- Useful for integration and migration.

## 10.3 Resilience Patterns

- Timeout.
- Retry with exponential backoff and jitter.
- Circuit breaker.
- Bulkhead.
- Rate limiter.
- Fallback.
- Load shedding.
- Backpressure.
- Dead-letter queue.
- Poison message quarantine.

## 10.4 Microservice Deployment Patterns

- Rolling deployment.
- Blue-green deployment.
- Canary deployment.
- Shadow traffic.
- Feature flags.
- Progressive delivery.
- Expand-contract database migration.
- Backward-compatible event/API evolution.

## 10.5 Microservice Testing

- Unit tests.
- Integration tests.
- Contract tests.
- Consumer-driven contract tests.
- End-to-end smoke tests.
- Chaos tests.
- Load tests.
- Replay tests.

## 10.6 Microservice Capstone Requirements

Build:

- API gateway.
- User service.
- Catalog service.
- Cart service.
- Order service.
- Inventory service.
- Payment service.
- Notification service.
- Search service.
- Analytics service.

Implement:

- Database per service.
- Outbox.
- Saga.
- Kafka events.
- Redis caching.
- OpenTelemetry tracing.
- Kubernetes deployment.
- GitOps.
- Canary release.

---


