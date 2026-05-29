# Incident Management / On-Call Platform (like PagerDuty)

## 1. Requirements

### Functional Requirements
- Alert ingestion from multiple sources (monitoring, APM, logs, custom webhooks)
- Alert deduplication and correlation (group related alerts)
- Severity classification (P1-P5) with auto-detection
- On-call schedule management (rotations, overrides, escalations)
- Notification delivery (multi-channel: push, SMS, phone call, email, Slack)
- Acknowledgment tracking with timeout-based escalation
- Incident lifecycle management (triggered → acknowledged → resolved)
- Postmortem/retrospective creation and tracking
- Runbook automation (triggered actions on alert)
- Service catalog with ownership mapping
- SLA tracking and reporting

### Non-Functional Requirements
- Alert-to-notification latency < 30 seconds for P1 incidents
- 99.999% availability for notification delivery path
- Support 100K+ active on-call users
- Handle 1M+ alerts/day across all tenants
- Phone call delivery within 60 seconds
- Zero missed pages for P1 incidents
- Multi-region active-active deployment

## 2. Core Entities

```
Alert: alert_id, source, severity, title, description, tags[], dedup_key, status, 
       service_id, created_at, resolved_at
Incident: incident_id, alert_ids[], severity, status, title, assigned_to, 
          acknowledged_at, resolved_at, timeline[]
Service: service_id, name, team_id, escalation_policy_id, tags[]
EscalationPolicy: policy_id, name, rules[] (level, targets[], timeout_minutes)
Schedule: schedule_id, name, timezone, layers[], overrides[]
ScheduleLayer: rotation_type, users[], handoff_time, rotation_interval
Override: user_id, start_time, end_time, replaced_user_id
User: user_id, name, contact_methods[], notification_rules[]
ContactMethod: type (phone/sms/email/push/slack), address, verified, priority
NotificationRule: severity_filter, delay_minutes, contact_method_id, repeat_interval
Postmortem: postmortem_id, incident_id, timeline, root_cause, action_items[], severity
Runbook: runbook_id, trigger_conditions, actions[], service_id
```

## 3. API Design

### Alert Ingestion API
```
POST /api/v2/alerts
Authorization: Bearer <INTEGRATION_KEY>
Content-Type: application/json

Request:
{
  "routing_key": "svc-payment-prod",
  "event_action": "trigger",
  "dedup_key": "cpu-high-web01-prod",
  "payload": {
    "summary": "CPU usage exceeded 95% on web-01.prod",
    "severity": "critical",
    "source": "datadog-monitor-12345",
    "component": "web-01",
    "group": "production-web-tier",
    "class": "cpu",
    "timestamp": "2024-01-15T10:00:00.000Z",
    "custom_details": {
      "current_value": 97.2,
      "threshold": 95,
      "duration_minutes": 5,
      "affected_services": ["payment-api", "checkout"]
    }
  },
  "links": [
    { "href": "https://monitoring.internal/dashboard/cpu", "text": "CPU Dashboard" }
  ],
  "images": [
    { "src": "https://monitoring.internal/graph/cpu-web01.png", "alt": "CPU Graph" }
  ]
}

Response (202 Accepted):
{
  "status": "success",
  "message": "Alert created",
  "dedup_key": "cpu-high-web01-prod",
  "alert_id": "alert-abc123"
}
```

### Alert Acknowledge/Resolve
```
PUT /api/v2/alerts/alert-abc123/acknowledge
Authorization: Bearer <USER_TOKEN>

Request:
{
  "acknowledged_by": "user-xyz",
  "message": "Investigating - scaling up instances"
}

Response (200):
{
  "alert_id": "alert-abc123",
  "status": "acknowledged",
  "acknowledged_by": "user-xyz",
  "acknowledged_at": "2024-01-15T10:02:30.000Z"
}
```

### Schedule Management
```
POST /api/v2/schedules
Authorization: Bearer <API_TOKEN>

Request:
{
  "name": "Platform Team Primary On-Call",
  "timezone": "America/New_York",
  "layers": [
    {
      "name": "Primary",
      "rotation_type": "weekly",
      "handoff_time": "09:00",
      "handoff_day": "monday",
      "users": [
        { "user_id": "user-001", "name": "Alice" },
        { "user_id": "user-002", "name": "Bob" },
        { "user_id": "user-003", "name": "Carol" },
        { "user_id": "user-004", "name": "Dave" }
      ],
      "restrictions": [
        {
          "type": "daily",
          "start_time": "09:00",
          "end_time": "17:00",
          "start_day": "monday",
          "end_day": "friday"
        }
      ]
    },
    {
      "name": "After-Hours",
      "rotation_type": "daily",
      "handoff_time": "17:00",
      "users": [
        { "user_id": "user-001" },
        { "user_id": "user-002" }
      ]
    }
  ],
  "overrides": []
}

Response (201):
{
  "id": "sched-abc123",
  "name": "Platform Team Primary On-Call",
  "current_on_call": {
    "user_id": "user-001",
    "name": "Alice",
    "start": "2024-01-15T09:00:00-05:00",
    "end": "2024-01-22T09:00:00-05:00"
  }
}
```

### Escalation Policy
```
POST /api/v2/escalation-policies
Authorization: Bearer <API_TOKEN>

Request:
{
  "name": "Payment Service Escalation",
  "repeat_enabled": true,
  "num_loops": 3,
  "rules": [
    {
      "escalation_delay_in_minutes": 5,
      "targets": [
        { "type": "schedule", "id": "sched-primary" }
      ]
    },
    {
      "escalation_delay_in_minutes": 10,
      "targets": [
        { "type": "schedule", "id": "sched-secondary" },
        { "type": "user", "id": "user-team-lead" }
      ]
    },
    {
      "escalation_delay_in_minutes": 15,
      "targets": [
        { "type": "user", "id": "user-engineering-manager" },
        { "type": "user", "id": "user-vp-engineering" }
      ]
    }
  ]
}

Response (201):
{
  "id": "ep-payment-001",
  "name": "Payment Service Escalation",
  "rules_count": 3,
  "services": ["payment-api", "payment-processor"]
}
```

### Incident Timeline
```
GET /api/v2/incidents/inc-12345/timeline
Authorization: Bearer <USER_TOKEN>

Response:
{
  "incident_id": "inc-12345",
  "timeline": [
    {
      "timestamp": "2024-01-15T10:00:00Z",
      "type": "triggered",
      "detail": "Alert triggered: CPU > 95% on web-01"
    },
    {
      "timestamp": "2024-01-15T10:00:15Z",
      "type": "notification_sent",
      "detail": "Push notification sent to Alice (on-call primary)"
    },
    {
      "timestamp": "2024-01-15T10:02:30Z",
      "type": "acknowledged",
      "detail": "Acknowledged by Alice",
      "user": "user-001"
    },
    {
      "timestamp": "2024-01-15T10:15:00Z",
      "type": "status_update",
      "detail": "Scaling up web tier from 5 to 10 instances",
      "user": "user-001"
    },
    {
      "timestamp": "2024-01-15T10:25:00Z",
      "type": "resolved",
      "detail": "CPU normalized after scaling. Resolved.",
      "user": "user-001"
    }
  ],
  "duration_minutes": 25,
  "time_to_ack_seconds": 150,
  "time_to_resolve_minutes": 25
}
```

## 4. High-Level Architecture

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                    INCIDENT MANAGEMENT PLATFORM                               │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐                    │
│  │ Datadog  │  │CloudWatch│  │  Custom  │  │  Slack   │                    │
│  │ Webhook  │  │  Events  │  │ Webhook  │  │  Bot     │                    │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘                    │
│       │              │              │              │                          │
│       └──────────────┴──────┬───────┴──────────────┘                         │
│                             │                                                │
│                    ┌────────▼────────┐                                       │
│                    │  Alert Intake   │  (Rate limiting, validation)           │
│                    │  Gateway        │                                       │
│                    └────────┬────────┘                                       │
│                             │                                                │
│                    ┌────────▼────────┐                                       │
│                    │  Dedup & Merge  │  (Correlation engine)                  │
│                    │  Engine         │                                       │
│                    └────────┬────────┘                                       │
│                             │                                                │
│                    ┌────────▼────────┐                                       │
│                    │   Kafka Cluster │                                       │
│                    │  alert-events   │                                       │
│                    └───┬────────┬────┘                                       │
│                        │        │                                            │
│           ┌────────────▼──┐  ┌──▼───────────────┐                           │
│           │  Incident     │  │  Escalation      │                           │
│           │  Manager      │  │  Engine          │                           │
│           └───────┬───────┘  └────────┬─────────┘                           │
│                   │                   │                                       │
│           ┌───────▼───────┐  ┌────────▼─────────┐                           │
│           │  Incident DB  │  │  Schedule        │                           │
│           │  (PostgreSQL) │  │  Resolver        │                           │
│           └───────────────┘  └────────┬─────────┘                           │
│                                       │                                      │
│                              ┌────────▼─────────┐                           │
│                              │  Notification    │                           │
│                              │  Dispatcher      │                           │
│                              └──┬───┬───┬───┬───┘                           │
│                                 │   │   │   │                               │
│                    ┌────────────┘   │   │   └────────────┐                  │
│                    │                │   │                 │                  │
│               ┌────▼───┐  ┌────────▼┐ ┌▼────────┐  ┌────▼────┐            │
│               │  Push  │  │  SMS   │ │ Phone  │  │  Email  │            │
│               │  (APNs/│  │(Twilio)│ │(Twilio)│  │(SendGrid│            │
│               │  FCM)  │  │        │ │        │  │         │            │
│               └────────┘  └────────┘ └────────┘  └─────────┘            │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

## 5. Deep Dive: Alert Correlation and Deduplication

```python
class AlertCorrelationEngine:
    """
    Groups related alerts to reduce noise and identify root causes.
    Uses time-window grouping, attribute similarity, and graph-based inference.
    """
    
    def __init__(self, config, state_store):
        self.config = config
        self.state_store = state_store  # Redis
        self.dedup_window = config.dedup_window_seconds  # 300s default
        self.similarity_threshold = config.similarity_threshold  # 0.7
    
    async def process_alert(self, alert):
        """Process incoming alert through dedup and correlation pipeline."""
        
        # Step 1: Exact deduplication by dedup_key
        existing = await self._find_by_dedup_key(alert)
        if existing:
            return await self._merge_into_existing(existing, alert)
        
        # Step 2: Time-window based grouping
        related_alerts = await self._find_time_correlated(alert)
        
        # Step 3: Similarity matching
        best_match = self._find_similar_alert(alert, related_alerts)
        if best_match and best_match.score > self.similarity_threshold:
            return await self._correlate(alert, best_match.alert)
        
        # Step 4: Service dependency correlation
        root_cause = await self._infer_root_cause(alert)
        if root_cause:
            return await self._attach_to_incident(alert, root_cause.incident_id)
        
        # No correlation found - create new incident
        return await self._create_new_incident(alert)
    
    async def _find_by_dedup_key(self, alert):
        """Exact match on dedup_key within time window."""
        key = f"dedup:{alert.tenant_id}:{alert.dedup_key}"
        existing_id = await self.state_store.get(key)
        if existing_id:
            return await self.state_store.get_alert(existing_id)
        return None
    
    async def _find_time_correlated(self, alert):
        """Find alerts within time window for same service/group."""
        window_start = alert.timestamp - self.dedup_window
        
        # Query recent alerts for same service or group
        candidates = await self.state_store.query_alerts(
            tenant_id=alert.tenant_id,
            service_id=alert.service_id,
            group=alert.group,
            since=window_start,
            status=['triggered', 'acknowledged']
        )
        return candidates
    
    def _find_similar_alert(self, alert, candidates):
        """Score similarity between alerts using multiple signals."""
        scores = []
        for candidate in candidates:
            score = self._calculate_similarity(alert, candidate)
            scores.append(SimilarityResult(alert=candidate, score=score))
        
        scores.sort(key=lambda x: x.score, reverse=True)
        return scores[0] if scores else None
    
    def _calculate_similarity(self, a, b):
        """Multi-factor similarity scoring."""
        score = 0.0
        
        # Same service: +0.3
        if a.service_id == b.service_id:
            score += 0.3
        
        # Same class/category: +0.2
        if a.alert_class == b.alert_class:
            score += 0.2
        
        # Tag overlap (Jaccard similarity): +0.2 * jaccard
        a_tags = set(a.tags)
        b_tags = set(b.tags)
        if a_tags or b_tags:
            jaccard = len(a_tags & b_tags) / len(a_tags | b_tags)
            score += 0.2 * jaccard
        
        # Title similarity (TF-IDF cosine): +0.15
        title_sim = self._text_similarity(a.title, b.title)
        score += 0.15 * title_sim
        
        # Temporal proximity (closer = higher): +0.15
        time_diff = abs(a.timestamp - b.timestamp)
        temporal_score = max(0, 1 - (time_diff / self.dedup_window))
        score += 0.15 * temporal_score
        
        return score
    
    async def _infer_root_cause(self, alert):
        """
        Use service dependency graph to infer root cause.
        If upstream service has active incident, this alert is likely a symptom.
        """
        # Get upstream dependencies for this service
        dependencies = await self.state_store.get_service_dependencies(alert.service_id)
        
        for dep in dependencies:
            # Check if upstream has active incident
            active_incident = await self.state_store.get_active_incident(dep.upstream_service_id)
            if active_incident:
                # Verify temporal correlation
                if active_incident.created_at <= alert.timestamp:
                    return RootCauseResult(
                        incident_id=active_incident.id,
                        confidence=0.85,
                        reason=f"Upstream service {dep.upstream_service_name} has active incident"
                    )
        
        return None


class IntelligentNoiseReduction:
    """
    ML-based noise reduction to suppress flapping and transient alerts.
    Uses historical patterns to determine if alert is actionable.
    """
    
    def __init__(self, model_path):
        self.model = self._load_model(model_path)
        self.flap_detector = FlapDetector(window=3600, threshold=5)
    
    def should_suppress(self, alert, history):
        """Determine if alert should be suppressed (noise)."""
        features = self._extract_features(alert, history)
        
        # Check flapping (>5 trigger/resolve cycles in 1 hour)
        if self.flap_detector.is_flapping(alert.dedup_key):
            return SuppressionDecision(
                suppress=True,
                reason="flapping",
                auto_resolve_after=300
            )
        
        # ML model prediction
        noise_probability = self.model.predict_proba(features)[0]
        if noise_probability > 0.85:
            return SuppressionDecision(
                suppress=True,
                reason="ml_noise_prediction",
                confidence=noise_probability
            )
        
        return SuppressionDecision(suppress=False)
    
    def _extract_features(self, alert, history):
        """Feature engineering for noise prediction."""
        return {
            'times_triggered_24h': history.trigger_count_24h,
            'avg_resolve_time_seconds': history.avg_resolve_time,
            'auto_resolve_rate': history.auto_resolve_count / max(history.total_count, 1),
            'ack_rate': history.ack_count / max(history.total_count, 1),
            'hour_of_day': alert.timestamp.hour,
            'day_of_week': alert.timestamp.weekday(),
            'severity_numeric': SEVERITY_MAP[alert.severity],
            'has_runbook': 1 if alert.runbook_url else 0,
        }
```

## 6. Deep Dive: On-Call Scheduling

```python
class OnCallScheduler:
    """
    Manages complex rotation schedules with multiple layers,
    restrictions, overrides, and fairness tracking.
    """
    
    def resolve_on_call(self, schedule, timestamp):
        """
        Determine who is on-call at a given timestamp.
        Process layers bottom-to-top (higher layers override lower).
        Then apply overrides on top.
        """
        resolved_user = None
        
        # Process layers (later layers override earlier)
        for layer in schedule.layers:
            user = self._resolve_layer(layer, timestamp)
            if user:
                resolved_user = user
        
        # Apply overrides (highest priority)
        override_user = self._check_overrides(schedule.overrides, timestamp)
        if override_user:
            resolved_user = override_user
        
        return resolved_user
    
    def _resolve_layer(self, layer, timestamp):
        """Resolve which user is on-call in a rotation layer."""
        # Check restrictions (e.g., business hours only)
        if not self._within_restrictions(layer.restrictions, timestamp):
            return None
        
        if layer.rotation_type == 'weekly':
            return self._resolve_weekly(layer, timestamp)
        elif layer.rotation_type == 'daily':
            return self._resolve_daily(layer, timestamp)
        elif layer.rotation_type == 'custom':
            return self._resolve_custom(layer, timestamp)
    
    def _resolve_weekly(self, layer, timestamp):
        """Weekly rotation algorithm."""
        # Calculate which rotation period we're in
        epoch = layer.start_time  # When rotation started
        handoff_weekday = layer.handoff_day  # 0=Monday
        handoff_hour = layer.handoff_time.hour
        
        # Find the most recent handoff time before timestamp
        dt = datetime.fromtimestamp(timestamp, tz=layer.timezone)
        
        # Days since last handoff day
        days_since_handoff = (dt.weekday() - handoff_weekday) % 7
        if days_since_handoff == 0 and dt.hour < handoff_hour:
            days_since_handoff = 7
        
        last_handoff = dt - timedelta(days=days_since_handoff)
        last_handoff = last_handoff.replace(hour=handoff_hour, minute=0, second=0)
        
        # Count weeks since rotation start
        weeks_elapsed = int((last_handoff - epoch).days / 7)
        user_index = weeks_elapsed % len(layer.users)
        
        return layer.users[user_index]
    
    def _resolve_daily(self, layer, timestamp):
        """Daily rotation algorithm."""
        dt = datetime.fromtimestamp(timestamp, tz=layer.timezone)
        epoch = layer.start_time
        handoff_hour = layer.handoff_time.hour
        
        # Adjust for handoff time
        if dt.hour < handoff_hour:
            dt -= timedelta(days=1)
        
        days_elapsed = (dt.date() - epoch.date()).days
        user_index = days_elapsed % len(layer.users)
        
        return layer.users[user_index]
    
    def _check_overrides(self, overrides, timestamp):
        """Check if any override is active at timestamp."""
        for override in overrides:
            if override.start_time <= timestamp <= override.end_time:
                return override.user
        return None


class EscalationEngine:
    """
    Manages escalation chains with timeout-based progression.
    Ensures someone always gets paged for critical incidents.
    """
    
    def __init__(self, scheduler, notification_service, state_store):
        self.scheduler = scheduler
        self.notifications = notification_service
        self.state_store = state_store
    
    async def start_escalation(self, incident):
        """Begin escalation chain for an incident."""
        policy = await self.state_store.get_escalation_policy(incident.escalation_policy_id)
        
        # Start at level 0
        await self._escalate_to_level(incident, policy, level=0, loop=0)
    
    async def _escalate_to_level(self, incident, policy, level, loop):
        """Notify targets at current escalation level."""
        if level >= len(policy.rules):
            if policy.repeat_enabled and loop < policy.num_loops:
                # Restart from level 0
                await self._escalate_to_level(incident, policy, level=0, loop=loop + 1)
            else:
                # Final escalation: notify admin/management
                await self._final_escalation(incident)
            return
        
        rule = policy.rules[level]
        
        # Resolve targets (schedules → users)
        users = await self._resolve_targets(rule.targets)
        
        # Send notifications to all targets at this level
        for user in users:
            await self.notifications.notify(
                user=user,
                incident=incident,
                escalation_level=level
            )
        
        # Schedule timeout for next level
        await self.state_store.schedule_escalation(
            incident_id=incident.id,
            next_level=level + 1,
            loop=loop,
            timeout_seconds=rule.escalation_delay_minutes * 60
        )
    
    async def handle_acknowledgment(self, incident_id, user_id):
        """Handle ack - cancel pending escalations."""
        await self.state_store.cancel_pending_escalations(incident_id)
        await self.state_store.update_incident_status(incident_id, 'acknowledged', user_id)
    
    async def check_escalation_timeout(self, incident_id):
        """Called by scheduler when escalation timeout fires."""
        incident = await self.state_store.get_incident(incident_id)
        
        if incident.status == 'triggered':  # Not yet acknowledged
            escalation_state = await self.state_store.get_escalation_state(incident_id)
            policy = await self.state_store.get_escalation_policy(incident.escalation_policy_id)
            await self._escalate_to_level(
                incident, policy,
                level=escalation_state.next_level,
                loop=escalation_state.loop
            )


class FairnessTracker:
    """Track on-call burden for fair distribution."""
    
    async def get_fairness_report(self, schedule_id, period_days=90):
        """Generate fairness metrics for a schedule."""
        users = await self._get_schedule_users(schedule_id)
        
        report = []
        for user in users:
            stats = await self._get_user_stats(user.id, period_days)
            report.append({
                'user': user.name,
                'total_on_call_hours': stats.total_hours,
                'weekend_hours': stats.weekend_hours,
                'holiday_hours': stats.holiday_hours,
                'incidents_handled': stats.incident_count,
                'avg_response_time_seconds': stats.avg_response_time,
                'sleep_interruptions': stats.night_pages,  # Pages between 22:00-07:00
                'burden_score': self._calculate_burden(stats)
            })
        
        return sorted(report, key=lambda x: x['burden_score'], reverse=True)
    
    def _calculate_burden(self, stats):
        """Weighted burden score (higher = more burdened)."""
        return (
            stats.total_hours * 1.0 +
            stats.weekend_hours * 1.5 +
            stats.holiday_hours * 2.0 +
            stats.night_pages * 3.0 +
            stats.incident_count * 0.5
        )
```

## 7. Deep Dive: Notification Delivery Guarantee

```python
class NotificationDispatcher:
    """
    Multi-channel notification delivery with guaranteed delivery.
    Priority escalation: Push → SMS → Phone Call.
    """
    
    CHANNEL_PRIORITY = ['push', 'sms', 'phone', 'email']
    
    async def notify(self, user, incident, escalation_level):
        """
        Deliver notification using user's preferences with fallback.
        Guarantees delivery by escalating channels on failure.
        """
        # Get user's notification rules for this severity
        rules = self._get_matching_rules(user, incident.severity)
        
        # Sort by priority and attempt delivery
        delivery_id = str(uuid.uuid4())
        
        for rule in sorted(rules, key=lambda r: r.delay_minutes):
            if rule.delay_minutes > 0:
                # Schedule delayed notification
                await self._schedule_delayed(delivery_id, user, incident, rule)
                continue
            
            # Immediate delivery
            success = await self._deliver_with_retry(
                delivery_id, user, incident, rule.contact_method
            )
            
            if success:
                await self._record_delivery(delivery_id, user, incident, rule.contact_method)
                return
        
        # All preferred methods failed - use fallback chain
        await self._fallback_delivery(delivery_id, user, incident)
    
    async def _deliver_with_retry(self, delivery_id, user, incident, contact_method, max_retries=3):
        """Attempt delivery with retries and exponential backoff."""
        for attempt in range(max_retries):
            try:
                if contact_method.type == 'push':
                    success = await self._send_push(user, incident, contact_method)
                elif contact_method.type == 'sms':
                    success = await self._send_sms(user, incident, contact_method)
                elif contact_method.type == 'phone':
                    success = await self._make_call(user, incident, contact_method)
                elif contact_method.type == 'email':
                    success = await self._send_email(user, incident, contact_method)
                
                if success:
                    return True
            except DeliveryException as e:
                wait = (2 ** attempt) + random.uniform(0, 1)
                await asyncio.sleep(wait)
        
        return False
    
    async def _make_call(self, user, incident, contact_method):
        """
        Make phone call via Twilio with TTS.
        Requires user to press a key to acknowledge.
        """
        call = await self.twilio_client.calls.create(
            to=contact_method.address,
            from_=self.config.caller_id,
            twiml=self._build_call_twiml(incident),
            status_callback=f"{self.config.base_url}/callbacks/call/{incident.id}",
            timeout=30
        )
        
        # Wait for answer/acknowledgment (max 60 seconds)
        ack_received = await self._wait_for_call_ack(call.sid, timeout=60)
        return ack_received
    
    def _build_call_twiml(self, incident):
        """Build TwiML for automated phone call."""
        return f"""
        <Response>
            <Say voice="alice">
                Alert: {incident.severity} severity incident.
                {incident.title}.
                Press 1 to acknowledge. Press 2 to escalate.
            </Say>
            <Gather numDigits="1" action="/callbacks/gather/{incident.id}" timeout="10">
                <Say>Press 1 to acknowledge or 2 to escalate.</Say>
            </Gather>
            <Say>No input received. This incident will be escalated.</Say>
        </Response>
        """
    
    async def _fallback_delivery(self, delivery_id, user, incident):
        """Last resort: try ALL channels in priority order."""
        for channel_type in self.CHANNEL_PRIORITY:
            contacts = [c for c in user.contact_methods if c.type == channel_type]
            for contact in contacts:
                success = await self._deliver_with_retry(
                    delivery_id, user, incident, contact, max_retries=2
                )
                if success:
                    return
        
        # Complete failure - log critical error and notify system admin
        await self._escalate_delivery_failure(user, incident)


class DoNotDisturbHandler:
    """
    Handle DND settings while ensuring critical alerts get through.
    """
    
    async def should_notify(self, user, incident):
        """Check if notification should be sent given DND settings."""
        dnd = await self._get_dnd_settings(user.id)
        
        if not dnd or not dnd.enabled:
            return True
        
        # P1/Critical always breaks through DND
        if incident.severity in ('P1', 'critical'):
            return True
        
        # Check if current time is within DND window
        now = datetime.now(tz=user.timezone)
        if dnd.start_time <= now.time() <= dnd.end_time:
            # Within DND - suppress unless override conditions met
            if dnd.allow_repeated and await self._is_repeated_page(user, incident):
                return True  # Multiple pages = probably important
            return False
        
        return True
```

## 8. Database Schema

```sql
-- Core tables
CREATE TABLE alerts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       BIGINT NOT NULL,
    dedup_key       VARCHAR(512) NOT NULL,
    source          VARCHAR(256) NOT NULL,
    severity        VARCHAR(16) NOT NULL,  -- critical, high, warning, low, info
    status          VARCHAR(32) NOT NULL DEFAULT 'triggered',
    title           VARCHAR(1024) NOT NULL,
    description     TEXT,
    service_id      UUID REFERENCES services(id),
    incident_id     UUID REFERENCES incidents(id),
    custom_details  JSONB,
    tags            TEXT[] DEFAULT '{}',
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    acknowledged_at TIMESTAMPTZ,
    resolved_at     TIMESTAMPTZ,
    resolved_by     VARCHAR(64),  -- user or auto
    INDEX idx_dedup (tenant_id, dedup_key, status),
    INDEX idx_service (tenant_id, service_id, created_at DESC),
    INDEX idx_status (tenant_id, status, severity, created_at DESC)
);

CREATE TABLE incidents (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       BIGINT NOT NULL,
    incident_number SERIAL,
    title           VARCHAR(1024) NOT NULL,
    severity        VARCHAR(16) NOT NULL,
    status          VARCHAR(32) NOT NULL DEFAULT 'triggered',
    assigned_to     UUID REFERENCES users(id),
    escalation_policy_id UUID REFERENCES escalation_policies(id),
    alert_count     INT DEFAULT 1,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    acknowledged_at TIMESTAMPTZ,
    acknowledged_by UUID REFERENCES users(id),
    resolved_at     TIMESTAMPTZ,
    resolved_by     UUID REFERENCES users(id),
    INDEX idx_tenant_status (tenant_id, status, created_at DESC),
    INDEX idx_assigned (assigned_to, status)
);

CREATE TABLE incident_timeline (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    incident_id     UUID NOT NULL REFERENCES incidents(id),
    event_type      VARCHAR(64) NOT NULL,
    detail          TEXT,
    user_id         UUID REFERENCES users(id),
    metadata        JSONB,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    INDEX idx_incident_timeline (incident_id, created_at)
);

CREATE TABLE schedules (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       BIGINT NOT NULL,
    name            VARCHAR(256) NOT NULL,
    timezone        VARCHAR(64) NOT NULL,
    layers          JSONB NOT NULL,
    overrides       JSONB DEFAULT '[]',
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    INDEX idx_tenant_schedules (tenant_id)
);

CREATE TABLE escalation_policies (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       BIGINT NOT NULL,
    name            VARCHAR(256) NOT NULL,
    repeat_enabled  BOOLEAN DEFAULT TRUE,
    num_loops       INT DEFAULT 3,
    rules           JSONB NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    INDEX idx_tenant_policies (tenant_id)
);

CREATE TABLE notification_log (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       BIGINT NOT NULL,
    incident_id     UUID NOT NULL,
    user_id         UUID NOT NULL,
    channel         VARCHAR(32) NOT NULL,
    status          VARCHAR(32) NOT NULL,  -- sent, delivered, failed, acknowledged
    sent_at         TIMESTAMPTZ DEFAULT NOW(),
    delivered_at    TIMESTAMPTZ,
    acknowledged_at TIMESTAMPTZ,
    error_message   TEXT,
    INDEX idx_incident_notifications (incident_id, sent_at),
    INDEX idx_user_notifications (user_id, sent_at DESC)
);

CREATE TABLE services (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       BIGINT NOT NULL,
    name            VARCHAR(256) NOT NULL,
    team_id         UUID,
    escalation_policy_id UUID REFERENCES escalation_policies(id),
    description     TEXT,
    tags            TEXT[] DEFAULT '{}',
    UNIQUE (tenant_id, name)
);

CREATE TABLE postmortems (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    incident_id     UUID NOT NULL REFERENCES incidents(id),
    tenant_id       BIGINT NOT NULL,
    title           VARCHAR(512),
    summary         TEXT,
    root_cause      TEXT,
    impact          TEXT,
    timeline_md     TEXT,
    action_items    JSONB DEFAULT '[]',
    status          VARCHAR(32) DEFAULT 'draft',
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    published_at    TIMESTAMPTZ
);
```

## 9. Kafka & Redis Configuration

### Kafka Configuration

```yaml
topics:
  alert-events:
    partitions: 64
    replication_factor: 3
    retention_ms: 604800000  # 7 days
    cleanup_policy: delete
    compression_type: lz4
    min_insync_replicas: 2  # Critical path - must not lose alerts
    
  escalation-timers:
    partitions: 32
    replication_factor: 3
    retention_ms: 86400000
    cleanup_policy: compact  # Keep latest state per key
    
  notification-commands:
    partitions: 32
    replication_factor: 3
    retention_ms: 86400000
    min_insync_replicas: 2

  notification-delivery-log:
    partitions: 16
    replication_factor: 3
    retention_ms: 2592000000  # 30 days

producer:
  acks: all  # Critical path - cannot lose alerts
  retries: 10
  retry_backoff_ms: 100
  enable_idempotence: true
  max_in_flight_requests: 1

consumer:
  group_id: incident-manager
  auto_offset_reset: earliest  # Don't miss alerts on restart
  enable_auto_commit: false  # Manual commit after processing
  max_poll_records: 100
  session_timeout_ms: 10000
```

### Redis Configuration

```yaml
redis:
  cluster:
    nodes: 6
    node_memory: 16GB
    maxmemory_policy: noeviction  # Never evict - alert state is critical
  
  key_patterns:
    # Alert deduplication
    dedup_key: "dedup:{tenant_id}:{dedup_key}"  # TTL: 24h
    
    # Active incidents per service
    active_incidents: "active:{tenant_id}:{service_id}"  # Set of incident IDs
    
    # Escalation timers (sorted set by fire time)
    escalation_queue: "escalation_queue"  # ZSET: score=fire_time, value=incident_id
    
    # On-call cache (invalidated on schedule change)
    oncall_cache: "oncall:{schedule_id}:{date}"  # TTL: 24h
    
    # Notification rate limiting
    notify_rate: "notify_rate:{user_id}:{channel}"  # Sliding window counter
    
    # Flap detection
    flap_history: "flap:{tenant_id}:{dedup_key}"  # List of trigger/resolve timestamps

  # Lua script for atomic escalation timer processing
  scripts:
    pop_due_escalations: |
      local now = tonumber(ARGV[1])
      local items = redis.call('ZRANGEBYSCORE', KEYS[1], '-inf', now, 'LIMIT', 0, 100)
      if #items > 0 then
        redis.call('ZREM', KEYS[1], unpack(items))
      end
      return items
```

## 10. Scalability & Performance

### Alert Ingestion
- **Rate limiting**: Per-integration rate limit (1000 alerts/min default)
- **Async processing**: Immediate 202 response, process via Kafka consumers
- **Dedup short-circuit**: Redis lookup before Kafka publish for exact dedup

### Notification Delivery
- **Multi-region**: Deploy notification workers in 3+ regions for phone/SMS reliability
- **Provider failover**: Twilio primary → Vonage secondary → AWS SNS tertiary
- **Parallel delivery**: Different channels for same user sent in parallel
- **Backpressure**: Queue depth monitoring with auto-scaling

### Schedule Resolution
- **Caching**: Pre-compute on-call for next 24h, cache in Redis
- **Invalidation**: Any schedule/override change invalidates cache
- **Timezone handling**: All schedule logic in UTC, display in user's timezone

### Capacity
```
1M alerts/day:
- Kafka: ~12 alerts/sec sustained, bursts to 1000/sec
- Alert processing: 5 consumers, each handles 200 alerts/sec
- Notifications: 100K notifications/day (many alerts are deduped)
- Phone calls: Peak 50 concurrent calls (Twilio capacity)
- Redis: 500K active dedup keys × 200 bytes = 100MB
```

## 11. Failure Handling & Reliability

### Zero Missed Pages (P1)
- Kafka with `acks=all` and `min.insync.replicas=2`
- Consumer commits offset only after notification confirmed sent
- Escalation timer backed by Redis persistence (AOF every second)
- Watchdog monitors: alert if escalation queue grows without processing

### Notification Provider Failures
- Circuit breaker per provider (open after 5 consecutive failures)
- Automatic failover to secondary provider
- SMS/Call delivery receipts tracked and retried on failure
- Dead letter queue for permanently failed deliveries

### Schedule Service Failures
- Cached on-call resolves served from Redis
- Fallback: escalation policy owner contacted directly
- Schedule service stateless - any instance can compute on-call

### Data Loss Prevention
- PostgreSQL streaming replication (sync mode for critical tables)
- Point-in-time recovery with WAL archival
- Cross-region async replication for DR

### Disaster Recovery
- Active-active in 2 regions (US-East, US-West)
- Alert ingestion: either region can accept
- Notifications: routed to region closest to user's phone carrier
- RTO < 30 seconds for P1 alert path
- RPO = 0 for alert events (sync Kafka replication)
