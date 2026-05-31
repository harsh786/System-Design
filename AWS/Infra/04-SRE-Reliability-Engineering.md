# SRE & Reliability Engineering - Staff/Architect Level

> Site Reliability Engineering concepts, SLOs, chaos engineering, incident management.
> Critical for Staff+ roles where reliability ownership is expected.

---

## 1. SRE Fundamentals

### What is SRE?
- **Google's definition:** "SRE is what happens when you ask a software engineer to design an operations function"
- **Core principle:** Apply software engineering to operations problems
- **Key practices:** SLOs, error budgets, toil reduction, automation, blameless postmortems

### SLIs, SLOs, SLAs

| Concept | Definition | Example |
|---------|-----------|---------|
| **SLI** (Service Level Indicator) | Metric that measures service quality | Request latency p99, error rate, throughput |
| **SLO** (Service Level Objective) | Target value for an SLI | 99.9% of requests < 200ms, error rate < 0.1% |
| **SLA** (Service Level Agreement) | Contract with consequences if SLO breached | 99.95% uptime or customer gets service credits |

### Choosing Good SLIs
- **Availability SLI:** Successful requests / total requests (exclude health checks, include all user-facing)
- **Latency SLI:** Proportion of requests faster than threshold (not average! Use percentiles)
- **Correctness SLI:** Correct responses / total responses
- **Freshness SLI:** Proportion of data fresher than threshold (for async systems)
- **Coverage SLI:** Proportion of valid data processed / total valid data received (for pipelines)

### Setting SLOs (Staff-level decisions)
- **100% is wrong:** Nothing is 100% reliable. Even 99.99% allows 52 min downtime/year
- **User expectations:** What do users actually notice? Start with user journey, not infrastructure
- **Cost curve:** Each 9 costs 10x more. 99.9% → 99.99% might require multi-region ($$$)

| Availability | Downtime/year | Downtime/month | Architecture Required |
|-------------|---------------|----------------|----------------------|
| 99% | 3.65 days | 7.3 hours | Single region, basic HA |
| 99.9% | 8.76 hours | 43 minutes | Multi-AZ, auto-scaling, health checks |
| 99.95% | 4.38 hours | 22 minutes | Multi-AZ, automated failover, redundancy |
| 99.99% | 52.6 minutes | 4.3 minutes | Multi-region, active-active, zero-downtime deploys |
| 99.999% | 5.26 minutes | 26 seconds | Multi-region active-active, automated everything |

---

## 2. Error Budgets

### Concept
- **Error budget = 1 - SLO**
- Example: SLO = 99.9% → Error budget = 0.1% = 43.2 minutes/month of allowed failure
- **Purpose:** Balances reliability investment vs feature velocity

### Error Budget Policy
```
Budget remaining > 50%:
  → Ship features freely, take risks, experiment
  
Budget remaining 20-50%:
  → Slow down, more testing, careful deployments
  
Budget remaining < 20%:
  → Feature freeze. Focus on reliability improvements only
  
Budget exhausted (0%):
  → Complete freeze. All engineering on reliability
  → Freeze remains until budget regenerates OR reliability fix deployed
```

### Error Budget Burn Rate Alerting
- **Problem:** Alert when SLO is in danger, not after it's breached
- **Burn rate:** How fast you're consuming your error budget
  - 1x burn rate: consuming budget at sustainable pace (will exhaust at end of window)
  - 14.4x burn rate: consuming 14.4x faster → will breach SLO in 5% of window (36 min of 30-day window)
- **Multi-window alerting:**
  - Page (urgent): 14.4x burn rate over 1 hour + 6x over 3 days
  - Ticket (non-urgent): 3x burn rate over 1 day + 1x over 3 days
- **Why this works:** Fewer false alerts than threshold-based (adapts to actual error budget)

---

## 3. Chaos Engineering

### Principles
1. **Define steady state:** What does "normal" look like? (throughput, latency, error rate)
2. **Hypothesize:** "If X fails, system should degrade gracefully"
3. **Introduce failure:** Smallest blast radius first, in production
4. **Observe:** Did system maintain steady state?
5. **Learn:** Fix weaknesses discovered

### AWS Fault Injection Simulator (FIS)
- **Actions available:**
  - EC2: Stop/terminate instances, stress CPU/memory/IO
  - ECS: Stop tasks, drain container instances
  - EKS: Terminate pods, node failures
  - RDS: Failover, reboot
  - Network: Inject latency, packet loss, blackhole traffic
  - AZ: Power interruption simulation
- **Guardrails:** Stop conditions (if error rate > 10%, abort experiment)
- **Example experiment:**
  ```json
  {
    "action": "aws:ec2:terminate-instances",
    "targets": { "instances": "tag:environment=production AND tag:service=user-api" },
    "percentage": 30,
    "stopConditions": [
      { "source": "cloudwatch", "value": "arn:aws:cloudwatch:alarm:HighErrorRate" }
    ]
  }
  ```

### Chaos Engineering Maturity
| Level | Description | Examples |
|-------|-------------|---------|
| 1 | Manual testing in dev | Kill a pod manually, observe |
| 2 | Automated in staging | FIS experiments on schedule in staging |
| 3 | Automated in production (limited) | Single instance termination in prod with guardrails |
| 4 | Continuous in production | Regular automated experiments, team comfortable |
| 5 | Chaos as culture | Every team runs experiments, part of CI/CD, game days |

### Game Day Template
```
Pre-game:
  - Notify stakeholders (not engineers being tested)
  - Verify monitoring/alerting working
  - Confirm rollback capability
  - Document hypothesis

Game:
  - Start recording (screen share for learning)
  - Inject failure
  - Observe (DO NOT intervene unless safety threshold hit)
  - Time: detection, escalation, mitigation, recovery

Post-game:
  - Timeline of events
  - What went well?
  - What surprised us?
  - Action items (sorted by priority)
  - Schedule follow-up for action items
```

---

## 4. Incident Management

### Incident Severity Levels
| Severity | Definition | Response Time | Example |
|----------|-----------|---------------|---------|
| SEV1 | Complete outage, all users affected | 5 minutes | Production down, data loss |
| SEV2 | Major degradation, many users affected | 15 minutes | Critical feature broken, >5% errors |
| SEV3 | Minor degradation, some users affected | 1 hour | Non-critical feature broken, <5% errors |
| SEV4 | Minimal impact, workaround exists | 4 hours | Cosmetic issue, minor bug |

### Incident Response Process
```
Detection (automated alert or user report)
  ↓
Triage (5 min): Severity classification, assign incident commander
  ↓
Communication: Status page, Slack channel, stakeholder notification
  ↓
Investigation: Dashboard review, logs, recent changes
  ↓
Mitigation: Immediate fix (rollback, scale up, failover, block traffic)
  ↓
Resolution: Root fix (may come later as follow-up)
  ↓
Post-mortem: Blameless review within 48 hours
  ↓
Action items: Track to completion, improve systems
```

### Incident Commander Role
- **Coordinates** (doesn't necessarily debug)
- Delegates: Investigation lead, Communication lead
- Decides: Escalation, rollback, customer communication
- Documents: Timeline, decisions, actions
- Authority to: Page anyone, make rollback decisions, declare resolved

### Blameless Post-mortem Template
```markdown
## Incident: Payment Service Outage - 2024-01-15

### Summary
Payment processing was unavailable for 23 minutes (14:32-14:55 UTC)
affecting approximately 12,000 users and $450K in attempted transactions.

### Timeline
- 14:30 - Deploy v2.3.1 to production (normal CI/CD)
- 14:32 - Error rate spike detected by monitoring
- 14:34 - PagerDuty alert fires, on-call acknowledges
- 14:38 - Incident commander assigned, investigation begins
- 14:42 - Root cause identified (DB migration incompatible with rollback)
- 14:47 - Decision: forward-fix (rollback would lose data)
- 14:52 - Fix deployed (v2.3.2)
- 14:55 - Service recovered, error rate normal

### Root Cause
Database migration in v2.3.1 added NOT NULL column without default value.
During rolling deployment, old version instances couldn't write to modified table.

### Contributing Factors
- No database backward-compatibility check in CI/CD pipeline
- Rolling deployment meant old + new code running simultaneously
- Migration was not tested against old application version

### Action Items
| Action | Owner | Priority | Status |
|--------|-------|----------|--------|
| Add DB migration backward-compat check to CI | @team-platform | P1 | TODO |
| Implement expand/contract migration pattern | @team-payments | P1 | TODO |
| Add deployment canary that tests old+new code paths | @team-platform | P2 | TODO |
| Document migration best practices | @team-lead | P3 | TODO |

### Lessons Learned
- Database migrations are the #1 deployment risk
- Need automated check: "Can old version work with new schema?"
- Forward-fix was right call (rollback would have data loss)
```

---

## 5. Toil Reduction

### What is Toil?
- **Manual:** Human must perform the task
- **Repetitive:** Done over and over
- **Automatable:** Could be done by software
- **Tactical:** Interrupt-driven, not strategic
- **No enduring value:** Doesn't improve the system permanently
- **Scales linearly:** More users/services = more toil

### Toil Examples and Automation
| Toil | Automation |
|------|-----------|
| Manually scaling instances | Auto Scaling + predictive |
| SSL certificate renewal | cert-manager + Let's Encrypt |
| Access provisioning | Self-service IAM + approval workflow |
| Log investigation | Automated anomaly detection + correlation |
| Database backup verification | Automated restore testing (Lambda) |
| Security patch application | Systems Manager Patch Manager + maintenance windows |
| Capacity planning | Compute Optimizer + automated right-sizing |
| Incident alerting triage | ML-based alert correlation (reduced noise) |

### Toil Budget
- **Google's guideline:** SRE teams spend max 50% on toil, 50% on engineering
- **If toil > 50%:** Reduce services managed OR automate OR add headcount
- **Measure:** Track time spent on toil vs engineering weekly. Report to leadership
- **Architect role:** Design systems that generate less toil (self-healing, self-scaling, self-configuring)

---

## 6. On-Call Best Practices

### On-Call Design
- **Rotation:** 1-week rotation, 2+ people in rotation (reduce burden)
- **Response time:** SEV1 < 5 min, SEV2 < 15 min
- **Escalation:** Primary → Secondary → Manager (5 min each level)
- **Compensation:** Extra pay, comp time, no more than 25% pages off-hours
- **Handoff:** Written handoff document (open issues, ongoing investigations)

### Alert Design (Reduce Noise)
- **SLO-based:** Alert on error budget burn rate (not raw metric threshold)
- **Actionable:** Every alert must have a clear action. If not → delete or auto-resolve
- **Target:** < 2 pages per on-call shift (more = alert fatigue = missed real issues)
- **Route correctly:** Alert goes to team that can actually fix it
- **Deduplicate:** Group related alerts into single incident

### On-Call Metrics
| Metric | Target | Meaning |
|--------|--------|---------|
| Pages per week | < 2 | Low burden, each page is meaningful |
| Time to acknowledge | < 5 min | Team is responsive |
| MTTD (detect) | < 5 min | Monitoring catches issues quickly |
| MTTR (resolve) | < 30 min | Team can fix issues fast |
| False positive rate | < 5% | Alerts are real |
| Escalation rate | < 10% | Primary can handle most issues |

---

## 7. Reliability Testing

### Testing Pyramid for Reliability
```
                    /\
                   /  \  Chaos experiments (production)
                  /----\
                 / Load \  Load/stress testing (staging)
                /--------\
               / Integration\ Integration testing with failure injection
              /--------------\
             /  Unit tests    \  Unit tests with error cases
            /------------------\
```

### Disaster Recovery Testing
- **Tabletop exercise:** Walk through DR plan on whiteboard (monthly)
- **Component test:** Failover single component (database failover, AZ evacuation) (monthly)
- **Full DR test:** Activate DR plan completely (failover to DR region) (quarterly)
- **Document:** Actual RTO/RPO achieved vs target. Update runbooks with findings

### Production Readiness Review
```
Before any service goes to production:
□ SLOs defined and measured
□ Monitoring and alerting configured (SLO-based)
□ Runbooks documented (top 5 alert scenarios)
□ On-call rotation established
□ Load tested at 2x expected traffic
□ Failure modes identified and mitigated
□ Rollback mechanism tested
□ Dependencies documented with fallback behavior
□ Data backup and recovery tested
□ Security review completed
□ Capacity planning done for 6 months
□ Cost estimate approved
```

---

## 8. Observability Engineering (Advanced)

### Observability vs Monitoring
- **Monitoring:** Predefined questions ("Is CPU > 80%?") → predefined answers
- **Observability:** Explore unknown questions ("Why is this specific user getting errors?") → investigate
- **Staff insight:** You need BOTH. Monitoring for known failure modes. Observability for debugging novel issues

### High-Cardinality Observability
- **Problem:** With microservices, you need to query by: user_id, request_id, service, version, region, pod, endpoint, status_code... (millions of combinations)
- **Traditional monitoring (CloudWatch):** Low cardinality. Can't search by user_id across all services
- **Solution:** Distributed tracing + structured events
  - OpenTelemetry: Auto-instrument all services, propagate trace context
  - Each span carries all dimensions (user_id, endpoint, status, latency)
  - Query: "Show me all requests for user X that took > 500ms in the last hour"

### Observability Architecture at Scale
```
Application Layer:
  OpenTelemetry SDK (auto-instrumentation)
    ↓ exports traces, metrics, logs
Collection Layer:
  OpenTelemetry Collector (per-node DaemonSet)
    ↓ batch, filter, sample, enrich
Storage Layer:
  Traces → Jaeger/Tempo/X-Ray (sampled 10%, 100% errors)
  Metrics → Prometheus/Thanos (15s scrape, 2-year retention)
  Logs → Loki/OpenSearch (structured JSON, 30-day hot)
Visualization Layer:
  Grafana (unified dashboards, correlation, explore)
Alerting Layer:
  Alertmanager (SLO-based burn rate alerts)
```

### Cost-Effective Observability
| Signal | Optimization | Savings |
|--------|-------------|---------|
| Traces | Sample 10% normal, 100% errors | 90% storage |
| Metrics | 15s→60s for non-critical, drop unused labels | 70% storage |
| Logs | Structured → filter at collection, tier storage | 80% storage |
| Total | Use Grafana stack (open source) vs vendor | 60-80% vs Datadog/New Relic |

---

## 9. Release Engineering

### Deployment Strategies Comparison (Staff-level detail)
| Strategy | Risk | Rollback Speed | Complexity | Resource Cost |
|----------|------|---------------|------------|---------------|
| Rolling update | Medium | Minutes | Low | 1x + buffer |
| Blue/Green | Low | Instant | Medium | 2x during deploy |
| Canary | Very Low | Instant | High | 1x + canary |
| Feature flags | Lowest | Instant | Medium (code) | 1x |
| Shadow/Traffic mirror | None (read-only) | N/A | High | 2x (shadow env) |

### Progressive Delivery Framework
```
Deploy → Canary (1%) → Observe (5 min) → 
  Analysis pass? 
    → Expand (10%) → Observe (10 min) →
    Analysis pass?
      → Expand (50%) → Observe (15 min) → Full (100%)
    Analysis fail? → Rollback
  Analysis fail? → Rollback immediately

Analysis criteria:
  - Error rate < 0.5%
  - Latency p99 < 300ms
  - No increase in 5xx responses
  - Business metrics stable (conversion rate, revenue)
```

### Feature Flags Architecture
- **Use cases:** Progressive rollout, kill switch, A/B testing, trunk-based development
- **Implementation:**
  ```
  Flag types:
    - Release flag: canary new feature (temporary, remove after full rollout)
    - Ops flag: kill switch for degradation (permanent)
    - Experiment flag: A/B test (temporary, remove after decision)
    - Permission flag: premium feature (permanent)
  ```
- **Services:** LaunchDarkly, Split.io, AWS AppConfig (feature flags), custom (DynamoDB + cache)
- **Best practices:** Clean up flags after use, audit flag changes, default to safe state (off), cache flags locally (don't call remote on every request)
- **Operational flags every service should have:**
  - Circuit breaker per dependency (instant disable of failing integrations)
  - Read-only mode (disable writes during incidents)
  - Maintenance mode (show maintenance page)
  - Debug mode (increased logging for specific users)

---

## 10. Staff/Architect Reliability Scenarios

### Q1: Service SLO is 99.95% but actual is 99.7%. What's your approach?
**Answer:**
1. **Gap analysis:** 99.95% allows 22 min/month downtime. 99.7% = 2.2 hours/month. Gap = ~2 hours
2. **Error budget review:** Budget exhausted in first week of month → feature freeze per policy
3. **Incident analysis:** Categorize the 2 hours of downtime:
   - Deployment failures: 45 min → Implement canary + auto-rollback
   - Single-AZ failures: 30 min → Verify true Multi-AZ with health-check-based routing
   - Database failovers: 20 min → RDS Proxy (66% faster failover) + connection retry in app
   - DNS propagation: 15 min → Lower TTL + health check interval
   - Unknown/misc: 10 min → Better monitoring coverage
4. **Priority actions:** Canary deployments (biggest impact) → RDS Proxy → Multi-AZ validation
5. **Timeline:** 99.95% achievable within 1-2 sprints with canary + RDS Proxy + health checks
6. **Process fix:** Add deployment SLI (% deployments without errors) + automated rollback

### Q2: Design on-call system for 200-microservice platform with 10 teams
**Answer:**
- **Ownership model:** Each team on-call for their services (3-5 services per team)
- **Escalation path:** Service team → Platform team → Management
- **Shared responsibility:**
  - Platform team: Infrastructure (K8s cluster, networking, shared services)
  - Service teams: Application logic, service-specific issues
- **Routing:** PagerDuty with service → team mapping (auto-route based on alert source)
- **Cross-team issues:** If alert fires but service team can't identify cause → escalate to platform + dependent teams
- **Reducing burden:**
  - SLO-based alerts only (no noise)
  - Runbooks for every alert (80% of pages have documented fix)
  - Auto-remediation for known issues (Lambda triggered by alarm)
  - Max 2 pages/week target (more → escalate to leadership for investment)
- **Metrics dashboard:** Per-team: pages/week, MTTR, escalation rate, false positive rate

### Q3: CEO asks "Why can't we just deploy faster?" (currently bi-weekly releases)
**Answer:**
- **Diagnose WHY releases are bi-weekly:**
  - Manual testing required? → Automate test suite, add canary
  - Integration issues? → Decouple services, contract testing
  - Fear of breaking prod? → Feature flags, canary, auto-rollback
  - Change approval process? → Automated compliance gates (replace manual approvals)
  - Monolith? → Can't deploy pieces independently → microservices strategy
- **Propose path to daily deploys:**
  1. **Week 1-4:** Automated testing (unit + integration in CI). Kill manual testing gate
  2. **Week 4-8:** Feature flags for all new features. Deploy code without releasing features
  3. **Week 8-12:** Canary deployments with automated rollback (5 min to know if broken)
  4. **Week 12+:** Continuous deployment (merge to main = deploy to production in 15 min)
- **Business case:** DORA research shows elite performers deploy multiple times per day with LOWER failure rates (smaller changes = easier to debug)
- **Key insight:** Deploy frequency and stability are NOT trade-offs. They're positively correlated (deploy often → small changes → faster recovery → higher reliability)

### Q4: Design the SLO framework for a new organization
**Answer:**
```
Step 1: Identify critical user journeys
  - Login
  - Product search
  - Add to cart
  - Checkout/payment
  - Order tracking

Step 2: Define SLIs per journey (what to measure)
  - Availability: success_requests / total_requests
  - Latency: % requests < threshold
  - Correctness: correct_results / total_results

Step 3: Set initial SLOs (start conservative)
  Journey          | Availability | Latency (p99)
  Login            | 99.95%       | < 500ms
  Search           | 99.9%        | < 300ms
  Checkout         | 99.99%       | < 1000ms
  Order tracking   | 99.9%        | < 500ms

Step 4: Implement measurement
  - OpenTelemetry SDK → Prometheus metrics
  - Grafana SLO dashboards (budget remaining, burn rate)
  
Step 5: Error budget policies (per-journey)
  - Budget > 50%: ship features freely
  - Budget < 20%: reliability sprint
  - Budget exhausted: freeze + fix

Step 6: Review cadence
  - Weekly: SLO dashboard review in team standup
  - Monthly: SLO target review (too easy? too hard?)
  - Quarterly: Adjust SLOs based on business requirements + customer feedback
```

### Q5: Production database approaching 90% storage. What's your architectural response?
**Answer:**
- **Immediate (< 24 hours):**
  - Increase storage (auto-scaling enabled? increase max)
  - Identify largest tables → purge/archive candidates
  - Check for unexplained growth (application bug writing excessively?)
  
- **Short-term (1-2 weeks):**
  - Implement data lifecycle (DynamoDB TTL, or Lambda archiving old records to S3)
  - Add monitoring: storage growth rate alert at 70% and 80%
  - Capacity planning: at current growth rate, when do we hit 100%?
  
- **Medium-term (1-2 months):**
  - Table partitioning (time-based: orders_2024_01, orders_2024_02)
  - Archive strategy: hot data (RDS) → warm (S3 + Athena) → cold (S3 Glacier)
  - Consider read-heavy tables moving to DynamoDB or OpenSearch (reduce RDS load)
  
- **Architecture change (if fundamental issue):**
  - Event sourcing: only current state in hot DB, events in Kinesis → S3
  - CQRS: separate write (small, hot) from read (can be rebuilt from events)
  - Sharding: split database by tenant/entity if single DB is limit
  
- **Key metric:** GB growth per day → project exactly when you hit limits → prioritize accordingly

