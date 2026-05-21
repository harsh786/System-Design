# Deployment Strategies Deep Dive

This file is a dedicated deployment strategy roadmap. It complements Kubernetes and cloud-native topics by focusing on release safety, rollout mechanics, compatibility, observability, and rollback.

## Architect-Level Outcome

You should be able to choose a deployment strategy based on risk, compatibility, user impact, state migration, operational maturity, and rollback requirements.

## Deployment Strategy Selection Matrix

| Strategy | Best For | Strength | Risk |
| --- | --- | --- | --- |
| Rolling deployment | Stateless services with backward-compatible changes. | Simple and common. | Mixed versions during rollout. |
| Blue-green | Fast rollback and full-environment validation. | Quick traffic switch. | Double capacity cost and data migration risk. |
| Canary | Risky changes with measurable user impact. | Small blast radius. | Needs strong metrics and traffic control. |
| Progressive delivery | Controlled rollout by percentage, cohort, region, or tenant. | Fine-grained safety. | Tooling and discipline required. |
| Shadow deployment | Validate behavior without affecting users. | Safe correctness comparison. | Cannot test side effects directly. |
| Dark launch | Deploy hidden feature before enabling. | Separates deploy from release. | Dead code path until flag enabled. |
| Feature flags | Runtime control of behavior. | Fast disable without redeploy. | Flag debt and complex state. |
| A/B test | Product experiment. | Measures business impact. | Not a safety strategy by itself. |
| Ring deployment | Roll out by environment/user cohort. | Good for enterprise and internal users. | Requires cohort routing. |
| Big-bang | Simple low-risk systems. | Operationally easy. | High blast radius. |

## Rolling Deployment

Flow:

```text
old pods serving -> create new pods -> readiness passes -> shift traffic -> terminate old pods
```

Use when:

- Change is backward compatible.
- Service is stateless or state is externalized.
- Mixed versions can run safely.
- Database schema supports old and new code.

Checklist:

- Readiness probe validates real dependencies.
- Graceful shutdown drains in-flight requests.
- PreStop hook and termination grace period are configured.
- Connection draining is enabled at load balancer.
- Error rate, latency, and saturation are watched.
- Rollback is tested.

Failure modes:

- New pods pass shallow readiness but fail real traffic.
- Old and new versions disagree on schema or event format.
- Long-lived connections keep sending traffic to terminating pods.
- Rollback fails because DB migration was not backward compatible.

## Blue-Green Deployment

Flow:

```text
Blue live -> deploy Green -> validate Green -> switch traffic -> keep Blue for rollback
```

Use when:

- You need fast rollback.
- Environment-level validation matters.
- Traffic switch can be controlled at load balancer/DNS/gateway.
- Capacity cost is acceptable.

Hard part:

- Databases and state are not blue-green by default.
- Schema migrations must be expand-contract.
- Background workers must not double-process jobs.
- External callbacks/webhooks must route correctly.

## Canary Deployment

Flow:

```text
1% traffic -> observe -> 5% -> observe -> 25% -> observe -> 50% -> 100%
```

Use when:

- Risk is measurable.
- You have strong dashboards and alerts.
- You can route traffic by percentage, tenant, region, or cohort.
- You can roll back quickly.

Canary metrics:

- Request success rate.
- p95/p99 latency.
- Error budget burn.
- Business conversion or task success.
- Dependency error rate.
- CPU/memory/GC.
- Logs with new error signatures.
- Queue lag.

Automated rollback triggers:

- Error rate above threshold.
- p99 latency above threshold.
- SLO burn rate spike.
- CrashLoopBackOff or restart spike.
- Business KPI drop.
- DLQ spike.

## Progressive Delivery

Progressive delivery combines canary, feature flags, metrics, and policy.

Rollout dimensions:

- Percentage.
- Region.
- Tenant.
- Internal users.
- App version.
- Device type.
- Customer tier.
- Risk tier.

Required controls:

- Metric gates.
- Pause/resume.
- Automated rollback.
- Manual approval for sensitive stages.
- Audit trail.
- Owner and escalation.

## Shadow Deployment

Shadow traffic sends a copy of production requests to a new version without returning its response to users.

Use when:

- You want correctness comparison.
- You need production-like traffic shape.
- Side effects can be disabled or sandboxed.

Risks:

- Duplicate writes if side effects are not blocked.
- Extra load on dependencies.
- PII and compliance concerns.
- Comparing nondeterministic outputs can be hard.

## Dark Launch

Deploy code disabled behind a flag.

Use when:

- You want deploy and release to be separate.
- You need warmup or precomputation.
- You want internal-only validation first.

Risks:

- Flag never removed.
- Hidden code path lacks real exercise.
- Multiple flags interact unexpectedly.

## Feature Flag Strategy

Flag types:

- Release flags.
- Experiment flags.
- Ops kill switches.
- Permission/entitlement flags.
- Migration flags.

Flag rules:

- Every flag has owner and expiry.
- Kill switches are tested.
- Defaults are safe.
- Flags are observable.
- Sensitive flags require audit.
- Remove release flags after rollout.

## Database Deployment Strategy

Use expand-contract:

1. Expand: add new nullable columns/tables/indexes.
2. Deploy app that writes old and new shape if needed.
3. Backfill data idempotently.
4. Switch reads to new shape.
5. Stop old writes.
6. Contract: remove old columns only after safe window.

Rules:

- Avoid destructive schema changes in the same deploy as code.
- Make migrations resumable.
- Test rollback with both old and new code.
- Monitor replication lag and lock time.
- Use online schema migration for large tables.

## Event and API Deployment Compatibility

API:

- Add optional fields before requiring them.
- Do not remove fields without deprecation.
- Version breaking changes.
- Preserve error semantics.

Events:

- Add fields with defaults.
- Never reuse field names for different meaning.
- Maintain schema compatibility.
- Test consumers before producer change.
- Keep replay compatibility.

## Deployment Runbook Template

```markdown
# Deployment Runbook

## Change
...

## Risk
...

## Strategy
Rolling / canary / blue-green / shadow / progressive

## Prechecks
...

## Rollout Steps
...

## Metrics
...

## Rollback Criteria
...

## Rollback Steps
...

## Owner
...
```

## Interview Questions

1. When do you choose canary over blue-green?
2. How do you deploy a breaking database schema change safely?
3. How do you roll back a deployment that already changed data?
4. How do feature flags fail in production?
5. How do you deploy event schema changes safely?
6. What metrics should gate progressive delivery?
7. How do you shadow test a payment service safely?
8. How do you handle deployment for long-running WebSocket connections?

