# Production Issues #46-60: Alerting & On-Call Issues

## Context
At scale: 10K+ alert rules, 500+ on-call engineers, 100+ alerts firing per day.
Companies: Google (SRE book), Netflix, Stripe, Meta managing alert fatigue at scale.

---

## Issue #46: Alert Storm During Cascading Failure (1000 Alerts in 5 Minutes)

```
┌─────────────────────────────────────────────────────────────────────────┐
│  PROBLEM: One Root Cause → 1000 Alerts → Paralysis                      │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Severity: P0 (Critical)                                               │
│  Frequency: Every major incident (monthly)                             │
│                                                                         │
│  SCENARIO:                                                              │
│  Database primary fails over (1 root cause)                            │
│  → Connection pool errors on 50 services (50 alerts)                  │
│  → Each service's error rate spikes (50 alerts)                       │
│  → Downstream services timeout (100 alerts)                            │
│  → SLA breach alerts (20 alerts)                                      │
│  → Customer impact alerts (10 alerts)                                  │
│  → Auto-scaling triggers (30 alerts)                                   │
│  → Disk space alerts (log volume spike) (20 alerts)                   │
│                                                                         │
│  TOTAL: 280 alerts in 3 minutes                                        │
│  On-call: phone vibrating non-stop, can't focus                       │
│  → Opens PagerDuty: 280 incidents, can't find root cause              │
│  → MTTR increased from 5 min to 30 min due to noise                  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Resolution**:
```yaml
# 1. AlertManager grouping
route:
  group_by: ['cluster', 'namespace', 'alertname']
  group_wait: 30s       # Wait for related alerts
  group_interval: 5m    # How often to send grouped notification
  repeat_interval: 4h
  
  routes:
    # Infrastructure alerts grouped together
    - match_re:
        alertname: '(NodeDown|PodCrash|DiskFull|NetworkPartition)'
      group_by: ['cluster']
      receiver: infra-team
      
    # Service alerts grouped by service
    - match_re:
        alertname: '(HighLatency|HighErrorRate|SLOBreach)'
      group_by: ['service']
      receiver: service-team

# 2. Alert inhibition (suppress symptoms when cause is alerting)
inhibit_rules:
  - source_match:
      alertname: 'DatabaseDown'
    target_match_re:
      alertname: '(HighErrorRate|HighLatency|ConnectionPoolExhausted)'
    equal: ['cluster']
    # If DB is down, suppress all dependent service alerts

  - source_match:
      alertname: 'NodeDown'
    target_match_re:
      alertname: '.+'
    equal: ['node']
    # If node is down, suppress all pod alerts on that node

# 3. PagerDuty intelligent grouping
# Configure alert grouping window: 5 minutes
# ML-based: group alerts that historically fire together
```

---

## Issue #47: Alert Fatigue - 90% of Alerts Are Noise

```
┌─────────────────────────────────────────────────────────────────────────┐
│  PROBLEM: On-Call Ignoring Alerts Because 90% Are False Positive        │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Severity: P1 (High)                                                   │
│  Frequency: Continuous (organizational problem)                        │
│                                                                         │
│  SYMPTOMS:                                                              │
│  - 100 alerts/day, only 10 require action                             │
│  - On-call acknowledges without investigating (muscle memory)         │
│  - Real incident mixed with noise → missed for 30 minutes            │
│  - New on-call overwhelmed, experienced on-call desensitized         │
│                                                                         │
│  CAUSES:                                                                │
│  - Thresholds too tight (alert on normal variance)                    │
│  - No for: duration (alerts on transient spikes)                     │
│  - Alerting on symptoms not causes                                     │
│  - Copy-pasted alerts from tutorials without tuning                   │
│  - Alerts created during incidents never cleaned up                   │
│  - No ownership → nobody deletes stale alerts                        │
│                                                                         │
│  SIGNAL-TO-NOISE DEATH SPIRAL:                                         │
│  Noise → ignored → real alert missed → longer incident               │
│  → someone adds MORE alerts → even more noise                         │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Resolution**:
```yaml
# 1. Alert hygiene process (monthly review)
# For each alert that fired, categorize:
# - Actionable (required human intervention) → KEEP
# - Informational (auto-resolved, no action) → DOWNGRADE to notification
# - False positive (incorrect threshold) → FIX or DELETE
# Target: >80% of pages should be actionable

# 2. Use 'for' duration appropriately
# BAD: Alert on any momentary spike
- alert: HighCPU
  expr: cpu_usage > 0.9
  # Fires on 1-second spikes during GC

# GOOD: Alert on sustained issue
- alert: HighCPU
  expr: cpu_usage > 0.9
  for: 10m  # Must be sustained for 10 minutes

# 3. Multi-signal alerts (reduce false positives)
# BAD: Alert on one signal
- alert: ServiceDegraded
  expr: error_rate > 0.01

# GOOD: Alert on correlated signals
- alert: ServiceDegraded
  expr: |
    (error_rate > 0.01)
    AND (latency_p99 > 2)
    AND (traffic_rate > 100)  # Only when there's actual traffic

# 4. Actionability requirement
# Every alert MUST have:
# - runbook_url in annotations
# - Clear action the on-call should take
# - Expected resolution time
# If you can't fill these → it's not an alert, it's a dashboard
annotations:
  runbook_url: https://wiki.company.com/runbooks/high-error-rate
  action: "Check recent deployments, consider rollback"
  expected_resolution: "5-15 minutes"
```

---

## Issue #48: Alert on Stale Data Showing "All Clear" During Outage

```
┌─────────────────────────────────────────────────────────────────────────┐
│  PROBLEM: Monitoring Shows Green Because It's Not Getting Data          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Severity: P0 (Critical)                                               │
│  Frequency: During collection pipeline failures                        │
│                                                                         │
│  SCENARIO:                                                              │
│  Prometheus can't scrape targets (network partition)                   │
│  → No new data points → last known value still in memory              │
│  → rate() returns 0 (no change in counter)                            │
│  → Error rate alert: error_rate = 0 → "All Clear!"                   │
│  → Dashboard shows flat lines → team thinks everything fine           │
│  → Actually: COMPLETE OUTAGE, just can't see it                       │
│                                                                         │
│  THE MOST DANGEROUS FAILURE MODE:                                      │
│  Silent monitoring failure = no alerts = no incident declared          │
│  Customer reports come in 30+ minutes later                           │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Resolution**:
```yaml
# 1. "Dead Man's Switch" alert (watchdog)
# Alert that ALWAYS fires. If it stops → monitoring is broken.
- alert: Watchdog
  expr: vector(1)  # Always true
  labels:
    severity: none
  annotations:
    summary: "This alert always fires. Absence means monitoring is down."

# PagerDuty: Configure "no data" alert
# If Watchdog stops firing for 5 min → page immediately

# 2. Freshness alerts on every critical metric
- alert: MetricStale
  expr: time() - timestamp(up{job="payment-service"}) > 120
  for: 0m  # Immediately
  annotations:
    summary: "Haven't received metrics from payment-service in 2 minutes"

# 3. Absent() function for critical metrics
- alert: PaymentMetricsMissing
  expr: absent(payment_transactions_total)
  for: 2m
  labels:
    severity: critical

# 4. Synthetic monitoring (external perspective)
# External service hits health endpoint every 30 seconds
# If no response → alert (independent of internal monitoring)
```

---

## Issue #49: Flapping Alerts (Firing → Resolved → Firing Every 5 Minutes)

```
┌─────────────────────────────────────────────────────────────────────────┐
│  PROBLEM: Alert Oscillates, Pages On-Call Repeatedly                    │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Severity: P2 (Medium)                                                 │
│  Frequency: Common with threshold-based alerts on noisy metrics        │
│                                                                         │
│  SCENARIO:                                                              │
│  Threshold: CPU > 80%                                                  │
│  Actual CPU: oscillates between 78% and 82%                           │
│  → Alert fires at 82% → resolves at 78% → fires at 82%               │
│  → 10 pages in 1 hour for the same non-issue                          │
│  → On-call frustrated, silences alert, misses real spike later        │
│                                                                         │
│  PATTERN:                                                               │
│  Alert: ████░░░████░░░████░░░████░░░  (firing/resolved/firing)        │
│  Actual: ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~  (stable around threshold)      │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Resolution**:
```yaml
# 1. Hysteresis (different fire/resolve thresholds)
# Fire at 85%, resolve at 70% (15% gap)
- alert: HighCPU
  expr: |
    (cpu_usage > 0.85)
    OR
    (ALERTS{alertname="HighCPU"} == 1 AND cpu_usage > 0.70)
  # Fires at 85%, stays firing until below 70%

# 2. Longer 'for' duration with smoothed metric
- alert: HighCPU
  expr: avg_over_time(cpu_usage[10m]) > 0.80  # Smoothed over 10 min
  for: 5m  # Sustained for 5 more minutes
  # Total: Must be high for ~15 minutes before alert

# 3. AlertManager: wait before sending resolve
route:
  group_wait: 30s
  # Don't send "resolved" immediately
  # Wait in case it fires again within group_interval

# 4. Rate of change instead of threshold
- alert: CPUTrending
  expr: predict_linear(cpu_usage[30m], 3600) > 0.95
  # Alert: CPU will hit 95% within 1 hour at current rate
```

---

## Issue #50: Critical Alert Routed to Wrong Team (Routing Misconfiguration)

```
┌─────────────────────────────────────────────────────────────────────────┐
│  PROBLEM: Payment Failure Alert Goes to Platform Team, Not Payments     │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Severity: P1 (High)                                                   │
│  Frequency: After team reorganizations / service ownership changes     │
│                                                                         │
│  SCENARIO:                                                              │
│  Alert: PaymentProcessingFailed                                        │
│  Correct team: payments-oncall                                         │
│  Routed to: platform-oncall (wrong team)                              │
│                                                                         │
│  → Platform team: "Not our service, re-routing"  (10 min delay)       │
│  → Payments team finally gets paged (15 min total delay)              │
│  → MTTR extended by routing confusion                                  │
│                                                                         │
│  ROOT CAUSE:                                                            │
│  - Service ownership changed but alert routing wasn't updated         │
│  - New service deployed without configuring alert routing              │
│  - Namespace/label used for routing doesn't match service owner       │
│  - Catch-all route sends unmatched alerts to wrong default team       │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Resolution**:
```yaml
# 1. Service catalog as source of truth for routing
# Each service declares its on-call team in service metadata
apiVersion: backstage.io/v1alpha1
kind: Component
metadata:
  name: payment-service
  annotations:
    pagerduty.com/service-id: "PXXXXXX"
    opsgenie.com/team: "payments-team"
spec:
  owner: payments-team
  lifecycle: production

# 2. Automated routing from service catalog
# Generate AlertManager config from catalog
route:
  routes:
    # Auto-generated from service catalog
    - match:
        service: payment-service
      receiver: payments-team-pagerduty
    - match:
        service: auth-service
      receiver: identity-team-pagerduty

# 3. Alert routing tests in CI
# Test that every service has a route
# Test that no alert falls through to catch-all
def test_alert_routing():
    for service in get_all_services():
        route = find_matching_route(service)
        assert route != "catch-all", f"{service} has no explicit route"
        assert route.receiver in active_oncall_schedules()

# 4. Quarterly routing audit
# Send test alert to every route, verify correct person acknowledges
```

---

## Issue #51: Alert Rule Returns Empty Result (Silent Alert Failure)

```
┌─────────────────────────────────────────────────────────────────────────┐
│  PROBLEM: Alert Rule Silently Evaluating to Nothing                     │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Severity: P0 (Critical - You think you're protected but aren't)       │
│  Frequency: After metric renames, label changes, or relabeling        │
│                                                                         │
│  SCENARIO:                                                              │
│  Alert rule: rate(http_requests_errors_total{service="api"}[5m]) > 0.05│
│  Metric renamed to: http_request_errors_total (underscore change)     │
│  → PromQL query returns empty vector (no match)                        │
│  → No alert fires (empty != threshold breach)                          │
│  → Protection GONE, nobody knows                                       │
│                                                                         │
│  COMMON CAUSES:                                                         │
│  - Metric name typo in alert rule                                      │
│  - Label value changed (env="production" → env="prod")                │
│  - Metric dropped by relabeling rule (Issue #15)                      │
│  - Prometheus job renamed                                               │
│  - Service mesh changes label topology                                 │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Resolution**:
```yaml
# 1. Alert on absent alert evaluation
# For every critical alert, have a meta-alert
- alert: AlertRuleNotEvaluating
  expr: |
    absent(ALERTS{alertname="PaymentErrorRate"})
    AND absent(ALERTS{alertname="PaymentErrorRate", alertstate="resolved"})
  # If the alert rule isn't even evaluating (no pending/firing/resolved)

# 2. Unit test alert rules
# promtool test rules
rule_files:
  - alerts.yml
evaluation_interval: 1m
tests:
  - interval: 1m
    input_series:
      - series: 'http_request_errors_total{service="api"}'
        values: '0 0 0 100 200 300'  # Spike at minute 3
    alert_rule_test:
      - alertname: HighErrorRate
        eval_time: 5m
        exp_alerts:
          - exp_labels:
              service: api
              severity: critical

# 3. CI/CD validation
# Before deploying new relabel rules:
# - Evaluate all alert rules against current data
# - If any alert that was returning results now returns empty → BLOCK

# 4. Prometheus rule evaluation metrics
prometheus_rule_evaluation_failures_total > 0
prometheus_rule_group_last_evaluation_samples == 0  # Rule matched nothing
```

---

## Issue #52: Alertmanager Cluster Split-Brain (Duplicate Notifications)

```
┌─────────────────────────────────────────────────────────────────────────┐
│  PROBLEM: Same Alert Sent 3x (Once Per AM Instance)                     │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Severity: P2 (Medium)                                                 │
│  Frequency: During network partitions                                  │
│                                                                         │
│  SCENARIO:                                                              │
│  3 Alertmanager instances in HA cluster                                │
│  Network partition: AM-1 can't reach AM-2 and AM-3                    │
│  → Each partition thinks it's the leader                               │
│  → Alert received by all 3 → each sends notification                  │
│  → On-call gets 3 PagerDuty pages for same alert                     │
│  → During major incident: 3 × 280 alerts = 840 notifications         │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Resolution**:
```yaml
# 1. Alertmanager gossip protocol tuning
alertmanager:
  cluster:
    peer-timeout: 15s
    gossip-interval: 200ms
    push-pull-interval: 60s
    settle-timeout: 60s
    # Faster convergence after partition heals

# 2. PagerDuty deduplication key
# Use consistent dedup_key so PD only creates one incident
receivers:
  - name: pagerduty
    pagerduty_configs:
      - routing_key: <key>
        # Dedup key based on alert content, not AM instance
        description: '{{ .GroupLabels.alertname }} - {{ .GroupLabels.service }}'
        # PagerDuty deduplicates based on this key

# 3. Notification deduplication at receiver
# Slack: same channel + same thread key = updates existing message
# Email: same subject line = thread
# Custom webhook: idempotent based on alert fingerprint
```

---

## Issue #53: SLO Alert Burn Rate Miscalculation

```
┌─────────────────────────────────────────────────────────────────────────┐
│  PROBLEM: SLO Burn Rate Alert Fires Too Late or Too Early              │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Severity: P1 (High)                                                   │
│  Frequency: Common when implementing SLO-based alerting                │
│                                                                         │
│  SCENARIO A (Too Late):                                                 │
│  SLO: 99.9% availability (error budget: 43.2 min/month)               │
│  Alert: burn rate > 1 over 1 hour                                     │
│  Complete outage for 30 minutes → burn rate = 30/43.2 = 0.69          │
│  Alert threshold: 1.0 → DOESN'T FIRE during full outage              │
│  Error budget consumed: 69% → still no alert                          │
│                                                                         │
│  SCENARIO B (Too Early):                                                │
│  Alert: burn rate > 14.4 over 5 minutes                               │
│  Brief 2-minute spike: burn rate = 14.4 → fires                      │
│  Auto-resolves 3 minutes later → false positive                       │
│  → On-call fatigued by transient burn rate spikes                     │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Resolution**:
```yaml
# Google SRE multi-window, multi-burn-rate alerts
# Both a short AND long window must exceed threshold

# Fast burn: detect rapid consumption
- alert: SLOBurnRateFast
  expr: |
    (
      # 14.4x burn rate over 1 hour (2% budget in 1 hour)
      (1 - rate(http_requests_total{status=~"5.."}[1h]) 
       / rate(http_requests_total[1h])) < (1 - 14.4 * (1 - 0.999))
    )
    AND
    (
      # Confirmed by 5-minute window (not just a blip)
      (1 - rate(http_requests_total{status=~"5.."}[5m]) 
       / rate(http_requests_total[5m])) < (1 - 14.4 * (1 - 0.999))
    )
  for: 2m
  labels:
    severity: critical  # Page immediately

# Slow burn: detect gradual consumption
- alert: SLOBurnRateSlow
  expr: |
    (
      # 3x burn rate over 6 hours (18% budget in 6 hours)
      (1 - rate(http_requests_total{status=~"5.."}[6h]) 
       / rate(http_requests_total[6h])) < (1 - 3 * (1 - 0.999))
    )
    AND
    (
      # Confirmed by 30-minute window
      (1 - rate(http_requests_total{status=~"5.."}[30m]) 
       / rate(http_requests_total[30m])) < (1 - 3 * (1 - 0.999))
    )
  for: 15m
  labels:
    severity: warning  # Ticket, not page
```

---

## Issue #54: On-Call Overload (Single Engineer Gets ALL Alerts)

```
┌─────────────────────────────────────────────────────────────────────────┐
│  PROBLEM: Routing Sends All P1s to Same Person                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Severity: P1 (High - Human)                                           │
│  Frequency: Every on-call rotation                                     │
│                                                                         │
│  SCENARIO:                                                              │
│  Small team (5 engineers) owns 30 services                             │
│  → One on-call gets paged for ALL 30 services                         │
│  → Major incident: 50 alerts across 10 services simultaneously        │
│  → One person can't triage 50 alerts in parallel                      │
│  → Critical payment alert buried in noise                             │
│  → Burnout: engineer quits after 3 months of on-call                  │
│                                                                         │
│  BURNOUT MATH:                                                          │
│  100 alerts/week × 5 min per alert = 8.3 hours/week just on alerts    │
│  + 2 AM pages/week × 1 hour each = 10.3 hours/week of interrupt      │
│  → Effectively working 50+ hours while on-call                        │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Resolution**:
```yaml
# 1. Tiered on-call
# L1: Bot/automation handles known issues (auto-remediation)
# L2: Primary on-call (actionable alerts only)
# L3: Secondary on-call (escalation after 15 min)
# L4: Engineering manager (escalation after 30 min)

# 2. Auto-remediation for known issues
# Instead of paging human, run playbook automatically
- alert: DiskFull
  expr: disk_usage > 0.9
  labels:
    auto_remediate: "true"
    playbook: "disk-cleanup"
  # Automation: kubectl exec cleanup-job

# 3. Alert budget per on-call shift
# Target: < 2 pages per 8-hour shift
# If exceeded: escalate to secondary, review alert quality

# 4. Follow-the-sun rotation
# US shift: 9 AM - 5 PM PST → on-call during business hours
# India shift: 5 PM - 1 AM PST → handle overnight
# EU shift: 1 AM - 9 AM PST → early morning

# 5. Service criticality tiers
# Tier 1 (payment, auth): Page immediately
# Tier 2 (recommendations, analytics): Page during business hours only
# Tier 3 (internal tools): Create ticket, no page
```

---

## Issue #55: Alert Notification Channel Down (PagerDuty Outage)

```
┌─────────────────────────────────────────────────────────────────────────┐
│  PROBLEM: Alerting Tool Itself Has an Outage                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Severity: P0 (Critical)                                               │
│  Frequency: Annual (PagerDuty/OpsGenie outages do happen)              │
│                                                                         │
│  SCENARIO:                                                              │
│  PagerDuty has a service degradation                                   │
│  → Webhook deliveries delayed by 15+ minutes                          │
│  → On-call doesn't receive critical payment alert                     │
│  → 15 minutes of undetected payment failures                          │
│  → $500K revenue impact before detected via other means               │
│                                                                         │
│  IRONY:                                                                 │
│  Your monitoring works perfectly.                                       │
│  Your alerting tool is the single point of failure.                    │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Resolution**:
```yaml
# 1. Multi-channel redundancy
receivers:
  - name: critical-alerts
    pagerduty_configs:
      - routing_key: <primary>
    slack_configs:
      - channel: '#critical-alerts'
        send_resolved: true
    webhook_configs:
      - url: 'https://backup-alerting.internal/webhook'
    # If PagerDuty is down, Slack still delivers

# 2. Independent monitoring path
# Separate, simple monitoring that doesn't share infrastructure
# Uptime check: external service → synthetic probe → SMS gateway
# Doesn't use: Prometheus, AlertManager, PagerDuty
# Uses: simple curl + Twilio SMS

# 3. Heartbeat monitoring for the alerting system
# External service checks if alerts are being received
# "Dead man's switch" alert → if not received → SMS direct

# 4. Status page subscription
# Auto-subscribe to PagerDuty status page
# Trigger backup notification path if PD is degraded
```

---

## Issue #56: Alert Thresholds Not Adjusting to Growth

```
┌─────────────────────────────────────────────────────────────────────────┐
│  PROBLEM: Static Thresholds Become Wrong as System Grows                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Severity: P2 (Medium)                                                 │
│  Frequency: Quarterly (after growth spurts)                            │
│                                                                         │
│  SCENARIO:                                                              │
│  January: Traffic = 10K req/sec, alert: error_count > 100/min         │
│  June: Traffic = 50K req/sec (5x growth)                              │
│  Same error rate (0.1%) → error_count = 500/min (5x more errors)     │
│  → Alert fires constantly → team silences it                          │
│  → Actual error spike (1%) → 5000/min → silenced alert                │
│  → Real problem undetected                                            │
│                                                                         │
│  OR REVERSE:                                                            │
│  Alert: response_time > 200ms                                          │
│  After optimization: normal becomes 50ms                              │
│  → 100ms spike (2x) doesn't fire alert                               │
│  → Performance regression undetected                                   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Resolution**:
```yaml
# 1. Percentage-based alerts (scale-independent)
# BAD: error_count > 100
# GOOD: error_rate > 0.01 (1%)
- alert: HighErrorRate
  expr: |
    rate(http_errors_total[5m]) / rate(http_requests_total[5m]) > 0.01

# 2. Anomaly detection (learns normal)
# BAD: latency > 200ms (static)
# GOOD: latency > 2 * avg_over_time(latency[7d])
- alert: LatencyAnomaly
  expr: |
    http_request_duration_seconds:p99
    > 2 * avg_over_time(http_request_duration_seconds:p99[7d:1h])

# 3. SLO-based (tied to business requirement, not absolute values)
# "99.9% of requests under 500ms" doesn't change with growth

# 4. Automated threshold tuning
# Monthly job: analyze alert firing history
# If alert fires > 5x/week and always auto-resolves → widen threshold
# If alert never fires → verify it still works (might be stale)
```

---

## Issue #57: Runbook Outdated (Points to Deprecated Systems)

```
┌─────────────────────────────────────────────────────────────────────────┐
│  PROBLEM: Runbook Says "SSH to server X" - Server Doesn't Exist         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Severity: P2 (Medium, but P0 impact during incidents)                 │
│  Frequency: Every infrastructure migration                             │
│                                                                         │
│  SCENARIO:                                                              │
│  3 AM page: "Database replication lag critical"                        │
│  On-call opens runbook:                                                │
│  Step 1: "SSH to db-replica-01.prod.internal"                         │
│  → Host doesn't exist (migrated to RDS 6 months ago)                  │
│  Step 2: "Run /opt/scripts/fix-replication.sh"                         │
│  → Script doesn't exist                                               │
│  Step 3: "Escalate to DBA team"                                        │
│  → DBA team dissolved, responsibilities moved to platform             │
│                                                                         │
│  RESULT: 3 AM, zero useful documentation, cold debugging              │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Resolution**:
```yaml
# 1. Runbook testing in CI/CD
# Automated runbook validation:
# - All linked URLs return 200
# - All referenced hosts resolve
# - All referenced scripts exist
# - All referenced teams exist in org chart

# 2. Runbook freshness alerts
- alert: RunbookStale
  expr: |
    (time() - runbook_last_updated_timestamp) > 90 * 86400  # 90 days
  annotations:
    summary: "Runbook for {{ $labels.alertname }} not updated in 90 days"

# 3. Executable runbooks (Jupyter/automation)
# Instead of text instructions, provide executable steps
# "Click to restart service" → actually runs kubectl rollout restart
# Self-updating: if infra changes, automation updates

# 4. Runbook ownership = alert ownership
# When alert is created/modified, runbook must be updated in same PR
# CI check: alert_rules.yml change without runbook update → fail
```

---

## Issue #58: Alert During Planned Maintenance (False Emergency)

```
┌─────────────────────────────────────────────────────────────────────────┐
│  PROBLEM: Planned DB Migration Triggers Every Alert                     │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Severity: P2 (Medium)                                                 │
│  Frequency: Every maintenance window (weekly)                          │
│                                                                         │
│  SCENARIO:                                                              │
│  Maintenance window: Saturday 2 AM, database upgrade                   │
│  → Database connections dropped (expected)                             │
│  → 50 alerts fire across all dependent services                       │
│  → On-call paged (wasn't aware of maintenance)                        │
│  → 30 minutes of confusion: "Is this the maintenance or real issue?" │
│                                                                         │
│  WORSE:                                                                 │
│  Team silences ALL alerts during maintenance window                   │
│  → Actual unrelated issue occurs during maintenance                   │
│  → Issue not detected for hours (silenced)                            │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Resolution**:
```yaml
# 1. Maintenance window integration
# AlertManager silences with matchers (not blanket silence)
apiVersion: v1
kind: Silence
metadata:
  name: db-maintenance-2024-01-15
spec:
  matchers:
    - name: alertname
      value: "DatabaseConnectionErrors|HighLatency"
      isRegex: true
    - name: service  
      value: ".*"
      isRegex: true
    - name: dependency
      value: "primary-db"
  startsAt: "2024-01-15T02:00:00Z"
  endsAt: "2024-01-15T04:00:00Z"
  comment: "Planned DB migration JIRA-1234"

# 2. Only silence specific expected alerts
# Keep active: disk space, security, unrelated services
# Silence: connection errors, latency, availability for DB-dependent services

# 3. Maintenance announcement in alerting
# When maintenance starts: post in #incidents channel
# List affected services and expected behavior
# Auto-notify on-call: "Maintenance in progress, expect alerts from X"

# 4. Post-maintenance validation
# After maintenance window closes:
# Automatically verify all services recovered
# If not → escalate (maintenance went wrong)
```

---

## Issue #59: Alert Evaluation Latency (5-Minute Delay to Detection)

```
┌─────────────────────────────────────────────────────────────────────────┐
│  PROBLEM: Issue Starts → Alert Fires 5+ Minutes Later                   │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Severity: P1 (High)                                                   │
│  Frequency: Inherent to pull-based monitoring                          │
│                                                                         │
│  BREAKDOWN OF 5-MINUTE DELAY:                                          │
│  - Scrape interval: 30s (metric collected up to 30s late)             │
│  - rate() needs 2 data points: +30s (need 2 scrapes)                  │
│  - 'for' duration: 2m (must be sustained)                             │
│  - Alert evaluation interval: 30s                                      │
│  - AlertManager group_wait: 30s                                        │
│  - PagerDuty processing: 5s                                            │
│  TOTAL: 30 + 30 + 120 + 30 + 30 + 5 = 245 seconds (4 minutes!)      │
│                                                                         │
│  FOR PAYMENTS:                                                          │
│  4 minutes of undetected payment failures                              │
│  At 1000 payments/min = 4000 failed payments before alert             │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Resolution**:
```yaml
# 1. Reduce scrape interval for critical services
scrape_configs:
  - job_name: payment-service
    scrape_interval: 10s  # Instead of default 30s
    scrape_timeout: 5s

# 2. Reduce 'for' duration for critical alerts
- alert: PaymentProcessingFailed
  expr: rate(payment_failures_total[1m]) > 0
  for: 30s  # Only 30s instead of 2m for critical
  labels:
    severity: critical

# 3. Push-based alerting for ultra-critical
# Application pushes alert directly (bypasses scrape cycle)
# payment_failed → Kafka → Lambda → PagerDuty (< 10 seconds)

# 4. Reduce group_wait for critical
route:
  routes:
    - match:
        severity: critical
      group_wait: 10s       # Send immediately
      group_interval: 1m
      receiver: critical-pagerduty
```

---

## Issue #60: Alert Notification Lacks Context (Useless Page)

```
┌─────────────────────────────────────────────────────────────────────────┐
│  PROBLEM: Page Says "HighErrorRate" - Nothing Else Useful               │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Severity: P2 (Medium, but multiplied by every incident)               │
│  Frequency: Every alert (design problem)                               │
│                                                                         │
│  BAD PAGE (what on-call sees at 3 AM):                                  │
│  "FIRING: HighErrorRate                                                 │
│   Labels: service=api, severity=critical                               │
│   Value: 0.05"                                                          │
│                                                                         │
│  ENGINEER QUESTIONS:                                                    │
│  - What's the normal value? (Is 0.05 barely over threshold?)          │
│  - Which endpoints are affected?                                       │
│  - When did it start?                                                   │
│  - Was there a recent deployment?                                      │
│  - What's the customer impact?                                         │
│  - What should I do first?                                             │
│                                                                         │
│  → 10 minutes spent gathering context before starting fix              │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Resolution**:
```yaml
# Rich alert annotations with full context
- alert: HighErrorRate
  expr: rate(http_errors[5m]) / rate(http_requests[5m]) > 0.01
  for: 2m
  labels:
    severity: critical
    team: payments
  annotations:
    summary: |
      Error rate {{ $value | humanizePercentage }} for {{ $labels.service }}
      (threshold: 1%, normal: ~0.1%)
    
    impact: |
      Estimated {{ $value | multiply 60000 | humanize }} customers/min affected.
      Revenue impact: ~${{ $value | multiply 500 | humanize }}/min
    
    context: |
      - Dashboard: https://grafana.internal/d/abc123?service={{ $labels.service }}
      - Recent deploys: https://deploy.internal/{{ $labels.service }}/history
      - Logs: https://loki.internal/explore?query={service="{{ $labels.service }}"} |= "error"
      - Traces: https://tempo.internal/search?service={{ $labels.service }}&error=true
    
    runbook_url: https://wiki.internal/runbooks/high-error-rate
    
    first_steps: |
      1. Check if recent deployment (link above)
      2. If yes → rollback: `kubectl rollout undo deploy/{{ $labels.service }}`
      3. If no → check dependency health dashboard
      4. Escalate if not resolved in 10 minutes
```

---

## Summary: Alerting & On-Call Issues

| # | Issue | Severity | Human Impact |
|---|-------|----------|-------------|
| 46 | Alert storm cascading failure | P0 | Paralysis, can't find root cause |
| 47 | Alert fatigue 90% noise | P1 | Desensitization, burnout |
| 48 | Stale data showing "all clear" | P0 | Complete blindness during outage |
| 49 | Flapping alerts | P2 | Repeated pages for non-issue |
| 50 | Wrong team routed | P1 | 15+ min delay to right responder |
| 51 | Silent alert failure (no data) | P0 | False sense of safety |
| 52 | AlertManager split-brain | P2 | Duplicate notifications |
| 53 | SLO burn rate miscalculation | P1 | Late/early detection |
| 54 | On-call overload | P1 | Burnout, attrition |
| 55 | Notification channel down | P0 | No pages during outage |
| 56 | Static thresholds wrong at scale | P2 | Permanent noise or silence |
| 57 | Outdated runbooks | P2 | Useless during incident |
| 58 | Maintenance window alerts | P2 | False emergencies |
| 59 | 5-minute detection delay | P1 | Extended customer impact |
| 60 | Alerts lack context | P2 | Slow initial triage |
