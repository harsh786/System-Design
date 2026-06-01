# Monitoring & Alerting Guide — Temporal at Scale

## Table of Contents
1. [Metrics Architecture](#metrics-architecture)
2. [Temporal Server Metrics](#temporal-server-metrics)
3. [SDK/Worker Metrics](#sdkworker-metrics)
4. [Grafana Dashboards](#grafana-dashboards)
5. [Alerting Strategy](#alerting-strategy)
6. [Operational Runbooks](#operational-runbooks)
7. [Distributed Tracing](#distributed-tracing)
8. [Log Management](#log-management)

---

## Metrics Architecture

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                          Observability Architecture                            │
│                                                                                │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐           │
│  │ Temporal Server  │    │  Worker Pods    │    │ Business Apps   │           │
│  │ (Frontend,       │    │ (Go workers)    │    │ (API servers)   │           │
│  │  History,        │    │                 │    │                 │           │
│  │  Matching)       │    │ /metrics :9090  │    │ /metrics :9090  │           │
│  │ /metrics :9090   │    └────────┬────────┘    └────────┬────────┘           │
│  └────────┬─────────┘             │                      │                    │
│           │                       │                      │                    │
│  ┌────────┴───────────────────────┴──────────────────────┴────────┐          │
│  │                     Prometheus (Federation)                      │          │
│  │  - scrape_interval: 15s                                         │          │
│  │  - retention: 30d (local), Thanos for long-term                 │          │
│  └────────┬──────────────────────────────┬─────────────────────────┘          │
│           │                              │                                    │
│  ┌────────┴─────────┐          ┌────────┴────────────┐                       │
│  │    Grafana        │          │   Alertmanager       │                       │
│  │  - Dashboards     │          │  - PagerDuty (P1)    │                       │
│  │  - Explore        │          │  - Slack (P2/P3)     │                       │
│  │  - Annotations    │          │  - Email (P3)        │                       │
│  └───────────────────┘          └─────────────────────┘                       │
│                                                                                │
│  ┌────────────────────────────────────────────────────────────────┐           │
│  │                    OpenTelemetry Collector                       │           │
│  │  - Receives traces from workers (OTLP gRPC :4317)              │           │
│  │  - Exports to Jaeger/Tempo                                      │           │
│  │  - Tail sampling (1% normal, 100% errors)                       │           │
│  └────────────────────────────────────────────────────────────────┘           │
│                                                                                │
│  ┌────────────────────────────────────────────────────────────────┐           │
│  │                    Loki / Elasticsearch                          │           │
│  │  - Worker structured logs (JSON)                                │           │
│  │  - Correlation: workflow_id, run_id, activity_id                │           │
│  │  - Retention: 30d hot, 90d warm, 1y cold                       │           │
│  └────────────────────────────────────────────────────────────────┘           │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## Temporal Server Metrics

### Critical Metrics Reference

| Metric | Type | What It Tells You | Alert Threshold |
|--------|------|-------------------|-----------------|
| `schedule_to_start_latency` | Histogram | Workers can't keep up | p99 > 10s |
| `persistence_latency` | Histogram | Database health | p99 > 500ms |
| `service_requests` | Counter | Throughput | Sudden drop > 50% |
| `service_errors` | Counter | Error rate | > 1% of requests |
| `history_size` | Histogram | Workflow bloat | > 10MB |
| `workflow_endtoend_latency` | Histogram | User-facing latency | Depends on SLO |
| `tasks_added_rate` vs `tasks_dispatched_rate` | Counter | Queue backlog | Added >> Dispatched |

### Prometheus Scrape Configuration

```yaml
# prometheus.yaml - Scrape config for Temporal
scrape_configs:
  # Temporal Server components
  - job_name: 'temporal-server'
    kubernetes_sd_configs:
      - role: pod
        namespaces:
          names: ['temporal']
    relabel_configs:
      - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_scrape]
        action: keep
        regex: true
      - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_port]
        action: replace
        target_label: __address__
        regex: (.+)
        replacement: ${1}:${2}
      - source_labels: [__meta_kubernetes_pod_label_app_kubernetes_io_component]
        target_label: component
      - source_labels: [__meta_kubernetes_pod_name]
        target_label: pod
    metric_relabel_configs:
      # Drop high-cardinality metrics we don't need
      - source_labels: [__name__]
        regex: 'go_.*'
        action: drop

  # Temporal Workers
  - job_name: 'temporal-workers'
    kubernetes_sd_configs:
      - role: pod
        namespaces:
          names: ['temporal-workers']
    relabel_configs:
      - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_scrape]
        action: keep
        regex: true
      - source_labels: [__meta_kubernetes_pod_label_task_queue]
        target_label: task_queue
      - source_labels: [__meta_kubernetes_pod_label_version]
        target_label: worker_version
```

### PromQL Alert Rules (Complete)

```yaml
# temporal-alerts.yaml - PrometheusRule resource
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: temporal-alerts
  namespace: observability
  labels:
    release: prometheus
spec:
  groups:
    # ═══════════════════════════════════════════════════
    # P1 ALERTS - Page immediately (PagerDuty)
    # ═══════════════════════════════════════════════════
    - name: temporal.p1.critical
      rules:
        # Workers overwhelmed - tasks waiting too long to be picked up
        - alert: TemporalHighScheduleToStartLatency
          expr: |
            histogram_quantile(0.99,
              sum(rate(temporal_workflow_task_schedule_to_start_latency_bucket{
                namespace!="internal"
              }[5m])) by (le, namespace, task_queue)
            ) > 30
          for: 5m
          labels:
            severity: critical
            team: platform
            page: "true"
          annotations:
            summary: "Workflow tasks waiting >30s to start ({{ $labels.namespace }}/{{ $labels.task_queue }})"
            description: |
              p99 schedule-to-start latency is {{ $value | humanizeDuration }}.
              This means workers cannot keep up with incoming tasks.
              Likely causes: insufficient workers, worker crashes, or stuck tasks.
            runbook_url: "https://runbooks.company.com/temporal/high-schedule-to-start"
            dashboard_url: "https://grafana.company.com/d/temporal-workers"

        # Activity workers overwhelmed
        - alert: TemporalHighActivityScheduleToStartLatency
          expr: |
            histogram_quantile(0.99,
              sum(rate(temporal_activity_schedule_to_start_latency_bucket{
                namespace!="internal"
              }[5m])) by (le, namespace, task_queue)
            ) > 60
          for: 5m
          labels:
            severity: critical
            team: platform
            page: "true"
          annotations:
            summary: "Activities waiting >60s to start ({{ $labels.namespace }}/{{ $labels.task_queue }})"
            runbook_url: "https://runbooks.company.com/temporal/high-activity-latency"

        # Database is unhealthy
        - alert: TemporalPersistenceLatencyCritical
          expr: |
            histogram_quantile(0.99,
              sum(rate(temporal_persistence_latency_bucket[5m])) by (le, operation, service_name)
            ) > 2
          for: 3m
          labels:
            severity: critical
            team: platform
            page: "true"
          annotations:
            summary: "Database latency critical: {{ $labels.operation }} p99 > 2s on {{ $labels.service_name }}"
            description: |
              Persistence operation {{ $labels.operation }} has p99 latency of {{ $value }}s.
              This will cause cascading failures across all workflows.
            runbook_url: "https://runbooks.company.com/temporal/persistence-latency"

        # Complete worker fleet down
        - alert: TemporalNoWorkersAvailable
          expr: |
            sum by (namespace, task_queue) (
              temporal_worker_task_slots_available
            ) == 0
            and
            sum by (namespace, task_queue) (
              rate(temporal_matching_tasks_added_total[5m])
            ) > 0
          for: 2m
          labels:
            severity: critical
            team: platform
            page: "true"
          annotations:
            summary: "No workers available for {{ $labels.namespace }}/{{ $labels.task_queue }} but tasks are queuing"

        # Temporal Frontend unreachable
        - alert: TemporalFrontendDown
          expr: |
            up{job="temporal-server", component="frontend"} == 0
          for: 1m
          labels:
            severity: critical
            page: "true"
          annotations:
            summary: "Temporal Frontend pod {{ $labels.pod }} is down"

        # History service shard loss
        - alert: TemporalHistoryShardsMissing
          expr: |
            sum(temporal_history_shard_controller_count{type="acquired"}) 
            < 
            sum(temporal_history_shard_controller_count{type="total"}) * 0.95
          for: 5m
          labels:
            severity: critical
            page: "true"
          annotations:
            summary: "More than 5% of history shards are unassigned"

    # ═══════════════════════════════════════════════════
    # P2 ALERTS - Alert within 15 minutes (Slack)
    # ═══════════════════════════════════════════════════
    - name: temporal.p2.warning
      rules:
        # Elevated workflow failure rate
        - alert: TemporalWorkflowFailureRateHigh
          expr: |
            (
              sum(rate(temporal_workflow_failed_total[15m])) by (namespace, workflow_type)
              /
              sum(rate(temporal_workflow_completed_total[15m])) by (namespace, workflow_type)
            ) > 0.05
          for: 10m
          labels:
            severity: warning
            team: platform
          annotations:
            summary: "Workflow failure rate >5% for {{ $labels.workflow_type }} in {{ $labels.namespace }}"
            description: "Current failure rate: {{ $value | humanizePercentage }}"

        # History size approaching limit
        - alert: TemporalHistorySizeWarning
          expr: |
            histogram_quantile(0.99,
              sum(rate(temporal_history_size_bucket[1h])) by (le, namespace)
            ) > 10485760
          for: 30m
          labels:
            severity: warning
          annotations:
            summary: "Workflow histories exceeding 10MB (p99) in {{ $labels.namespace }}"
            description: "Large histories cause memory pressure and slow replays. Use ContinueAsNew."

        # Persistence latency elevated (not critical yet)
        - alert: TemporalPersistenceLatencyElevated
          expr: |
            histogram_quantile(0.99,
              sum(rate(temporal_persistence_latency_bucket[5m])) by (le, operation)
            ) > 0.5
          for: 10m
          labels:
            severity: warning
          annotations:
            summary: "Persistence p99 latency elevated: {{ $labels.operation }} at {{ $value }}s"

        # Rate limiting triggered
        - alert: TemporalNamespaceRateLimited
          expr: |
            sum(rate(temporal_service_errors_total{error_type="resource_exhausted"}[5m])) by (namespace) > 1
          for: 5m
          labels:
            severity: warning
          annotations:
            summary: "Namespace {{ $labels.namespace }} is being rate limited"

        # Task queue backlog growing
        - alert: TemporalTaskQueueBacklogGrowing
          expr: |
            (
              sum(rate(temporal_matching_tasks_added_total[5m])) by (task_queue, namespace)
              -
              sum(rate(temporal_matching_tasks_dispatched_total[5m])) by (task_queue, namespace)
            ) > 100
          for: 10m
          labels:
            severity: warning
          annotations:
            summary: "Task queue backlog growing: {{ $labels.task_queue }} ({{ $value }} tasks/sec net increase)"

        # Worker error rate elevated
        - alert: TemporalActivityFailureRateHigh
          expr: |
            (
              sum(rate(temporal_activity_execution_failed_total[10m])) by (namespace, activity_type)
              /
              sum(rate(temporal_activity_execution_total[10m])) by (namespace, activity_type)
            ) > 0.1
          for: 10m
          labels:
            severity: warning
          annotations:
            summary: "Activity {{ $labels.activity_type }} failure rate >10%"

    # ═══════════════════════════════════════════════════
    # P3 ALERTS - Next business day (Email/Slack)
    # ═══════════════════════════════════════════════════
    - name: temporal.p3.info
      rules:
        # Worker inefficiency (too many pollers, not enough work)
        - alert: TemporalWorkerOverProvisioned
          expr: |
            (
              sum(temporal_worker_task_slots_available) by (task_queue, namespace)
              /
              sum(temporal_worker_task_slots_available + temporal_worker_task_slots_used) by (task_queue, namespace)
            ) > 0.9
          for: 1h
          labels:
            severity: info
          annotations:
            summary: "Workers for {{ $labels.task_queue }} are >90% idle - consider scaling down"

        # Elasticsearch disk usage
        - alert: TemporalESStorageHigh
          expr: |
            elasticsearch_filesystem_data_used_percent{cluster="temporal-es"} > 75
          for: 1h
          labels:
            severity: info
          annotations:
            summary: "Temporal ES cluster storage >75% - review ILM policies"

        # Long-running workflows
        - alert: TemporalLongRunningWorkflows
          expr: |
            sum(temporal_workflow_running{execution_duration_bucket="+Inf"}) by (namespace, workflow_type)
            -
            sum(temporal_workflow_running{execution_duration_bucket="86400"}) by (namespace, workflow_type)
            > 100
          for: 6h
          labels:
            severity: info
          annotations:
            summary: ">100 workflows running for more than 24h in {{ $labels.namespace }}"
```

### Alertmanager Configuration

```yaml
# alertmanager.yaml
global:
  resolve_timeout: 5m
  pagerduty_url: 'https://events.pagerduty.com/v2/enqueue'
  slack_api_url_file: /etc/alertmanager/secrets/slack-webhook-url

route:
  receiver: 'default-slack'
  group_by: ['alertname', 'namespace', 'task_queue']
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 4h
  routes:
    - receiver: 'pagerduty-critical'
      match:
        severity: critical
        page: "true"
      group_wait: 10s
      repeat_interval: 30m
    
    - receiver: 'slack-warning'
      match:
        severity: warning
      group_wait: 1m
      repeat_interval: 2h
    
    - receiver: 'email-info'
      match:
        severity: info
      group_wait: 10m
      repeat_interval: 24h

receivers:
  - name: 'pagerduty-critical'
    pagerduty_configs:
      - service_key_file: /etc/alertmanager/secrets/pagerduty-service-key
        severity: critical
        description: '{{ .CommonAnnotations.summary }}'
        details:
          firing: '{{ template "pagerduty.default.description" . }}'
          runbook: '{{ .CommonAnnotations.runbook_url }}'
          dashboard: '{{ .CommonAnnotations.dashboard_url }}'

  - name: 'slack-warning'
    slack_configs:
      - channel: '#temporal-alerts'
        title: '{{ .CommonAnnotations.summary }}'
        text: |
          *Alert:* {{ .CommonLabels.alertname }}
          *Namespace:* {{ .CommonLabels.namespace }}
          *Description:* {{ .CommonAnnotations.description }}
          *Runbook:* {{ .CommonAnnotations.runbook_url }}
        actions:
          - type: button
            text: 'Runbook'
            url: '{{ .CommonAnnotations.runbook_url }}'
          - type: button
            text: 'Dashboard'
            url: '{{ .CommonAnnotations.dashboard_url }}'

  - name: 'email-info'
    email_configs:
      - to: 'platform-team@company.com'
        send_resolved: true

  - name: 'default-slack'
    slack_configs:
      - channel: '#temporal-alerts'
```

---

## SDK/Worker Metrics

### Go Worker Metrics Implementation

```go
// metrics.go - Custom metrics for Temporal workers
package metrics

import (
	"context"
	"time"

	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promauto"
	"go.temporal.io/sdk/activity"
)

var (
	// Business metrics
	PaymentsProcessed = promauto.NewCounterVec(prometheus.CounterOpts{
		Namespace: "business",
		Subsystem: "payments",
		Name:      "processed_total",
		Help:      "Total number of payments processed",
	}, []string{"status", "payment_method", "currency"})

	PaymentAmount = promauto.NewHistogramVec(prometheus.HistogramOpts{
		Namespace: "business",
		Subsystem: "payments",
		Name:      "amount_dollars",
		Help:      "Payment amounts in dollars",
		Buckets:   []float64{1, 10, 50, 100, 500, 1000, 5000, 10000, 50000},
	}, []string{"payment_method", "currency"})

	OrdersFulfilled = promauto.NewCounterVec(prometheus.CounterOpts{
		Namespace: "business",
		Subsystem: "orders",
		Name:      "fulfilled_total",
		Help:      "Total orders fulfilled",
	}, []string{"warehouse", "shipping_method"})

	OrderFulfillmentDuration = promauto.NewHistogramVec(prometheus.HistogramOpts{
		Namespace: "business",
		Subsystem: "orders",
		Name:      "fulfillment_duration_seconds",
		Help:      "Time from order placement to fulfillment",
		Buckets:   prometheus.ExponentialBuckets(60, 2, 15), // 1min to ~22 days
	}, []string{"order_type"})

	// Activity-level metrics
	ActivityExternalCallDuration = promauto.NewHistogramVec(prometheus.HistogramOpts{
		Namespace: "temporal",
		Subsystem: "activity",
		Name:      "external_call_duration_seconds",
		Help:      "Duration of external service calls from activities",
		Buckets:   prometheus.DefBuckets,
	}, []string{"service", "operation", "status"})

	ActivityRetries = promauto.NewCounterVec(prometheus.CounterOpts{
		Namespace: "temporal",
		Subsystem: "activity",
		Name:      "retries_total",
		Help:      "Number of activity retries (application-level)",
	}, []string{"activity_type", "reason"})

	// Workflow-level metrics (tracked via search attributes + queries)
	WorkflowStageTransitions = promauto.NewCounterVec(prometheus.CounterOpts{
		Namespace: "temporal",
		Subsystem: "workflow",
		Name:      "stage_transitions_total",
		Help:      "Workflow stage transitions",
	}, []string{"workflow_type", "from_stage", "to_stage"})
)

// TrackExternalCall measures duration of external service calls
func TrackExternalCall(ctx context.Context, service, operation string, fn func() error) error {
	start := time.Now()
	err := fn()
	duration := time.Since(start).Seconds()

	status := "success"
	if err != nil {
		status = "error"
	}

	ActivityExternalCallDuration.WithLabelValues(service, operation, status).Observe(duration)

	// Also heartbeat to Temporal if this is a long call
	if duration > 5 {
		activity.RecordHeartbeat(ctx, map[string]interface{}{
			"service":   service,
			"operation": operation,
			"duration":  duration,
		})
	}

	return err
}

// EmitPaymentMetrics records payment processing metrics
func EmitPaymentMetrics(status, method, currency string, amount float64) {
	PaymentsProcessed.WithLabelValues(status, method, currency).Inc()
	if status == "success" {
		PaymentAmount.WithLabelValues(method, currency).Observe(amount)
	}
}
```

### Custom MetricsHandler with Namespace/TaskQueue Labels

```go
// metrics_handler.go - Enhanced metrics handler for multi-tenant tracking
package metrics

import (
	"strings"
	"time"

	"github.com/prometheus/client_golang/prometheus"
	"go.temporal.io/sdk/client"
)

type PrometheusMetricsHandler struct {
	namespace string
	taskQueue string
	registry  *prometheus.Registry
	counters  map[string]*prometheus.CounterVec
	gauges    map[string]*prometheus.GaugeVec
	timers    map[string]*prometheus.HistogramVec
}

func NewPrometheusMetricsHandler(namespace, taskQueue string, registry *prometheus.Registry) client.MetricsHandler {
	return &PrometheusMetricsHandler{
		namespace: namespace,
		taskQueue: taskQueue,
		registry:  registry,
		counters:  make(map[string]*prometheus.CounterVec),
		gauges:    make(map[string]*prometheus.GaugeVec),
		timers:    make(map[string]*prometheus.HistogramVec),
	}
}

func (h *PrometheusMetricsHandler) WithTags(tags map[string]string) client.MetricsHandler {
	// Clone with additional tags
	newHandler := &PrometheusMetricsHandler{
		namespace: h.namespace,
		taskQueue: h.taskQueue,
		registry:  h.registry,
		counters:  h.counters,
		gauges:    h.gauges,
		timers:    h.timers,
	}
	return newHandler
}

func (h *PrometheusMetricsHandler) Counter(name string) client.MetricsCounter {
	sanitized := sanitizeMetricName(name)
	counter, ok := h.counters[sanitized]
	if !ok {
		counter = prometheus.NewCounterVec(prometheus.CounterOpts{
			Namespace: "temporal_sdk",
			Name:      sanitized,
		}, []string{"namespace", "task_queue"})
		h.registry.MustRegister(counter)
		h.counters[sanitized] = counter
	}
	return &prometheusCounter{counter: counter.WithLabelValues(h.namespace, h.taskQueue)}
}

func (h *PrometheusMetricsHandler) Gauge(name string) client.MetricsGauge {
	sanitized := sanitizeMetricName(name)
	gauge, ok := h.gauges[sanitized]
	if !ok {
		gauge = prometheus.NewGaugeVec(prometheus.GaugeOpts{
			Namespace: "temporal_sdk",
			Name:      sanitized,
		}, []string{"namespace", "task_queue"})
		h.registry.MustRegister(gauge)
		h.gauges[sanitized] = gauge
	}
	return &prometheusGauge{gauge: gauge.WithLabelValues(h.namespace, h.taskQueue)}
}

func (h *PrometheusMetricsHandler) Timer(name string) client.MetricsTimer {
	sanitized := sanitizeMetricName(name)
	timer, ok := h.timers[sanitized]
	if !ok {
		timer = prometheus.NewHistogramVec(prometheus.HistogramOpts{
			Namespace: "temporal_sdk",
			Name:      sanitized,
			Buckets:   prometheus.ExponentialBuckets(0.001, 2, 20), // 1ms to ~17 min
		}, []string{"namespace", "task_queue"})
		h.registry.MustRegister(timer)
		h.timers[sanitized] = timer
	}
	return &prometheusTimer{observer: timer.WithLabelValues(h.namespace, h.taskQueue)}
}

type prometheusCounter struct{ counter prometheus.Counter }
func (c *prometheusCounter) Inc(v int64) { c.counter.Add(float64(v)) }

type prometheusGauge struct{ gauge prometheus.Gauge }
func (g *prometheusGauge) Update(v float64) { g.gauge.Set(v) }

type prometheusTimer struct{ observer prometheus.Observer }
func (t *prometheusTimer) Record(d time.Duration) { t.observer.Observe(d.Seconds()) }

func sanitizeMetricName(name string) string {
	return strings.ReplaceAll(strings.ReplaceAll(name, ".", "_"), "-", "_")
}
```

---

## Grafana Dashboards

### Dashboard 1: Cluster Health

```json
{
  "dashboard": {
    "title": "Temporal - Cluster Health",
    "uid": "temporal-cluster-health",
    "tags": ["temporal", "infrastructure"],
    "timezone": "browser",
    "refresh": "30s",
    "panels": [
      {
        "title": "Frontend Request Rate",
        "type": "timeseries",
        "gridPos": { "h": 8, "w": 12, "x": 0, "y": 0 },
        "targets": [
          {
            "expr": "sum(rate(temporal_service_requests_total[5m])) by (operation)",
            "legendFormat": "{{ operation }}"
          }
        ]
      },
      {
        "title": "Frontend Error Rate",
        "type": "timeseries",
        "gridPos": { "h": 8, "w": 12, "x": 12, "y": 0 },
        "targets": [
          {
            "expr": "sum(rate(temporal_service_errors_total[5m])) by (operation, error_type) / sum(rate(temporal_service_requests_total[5m])) by (operation) * 100",
            "legendFormat": "{{ operation }} - {{ error_type }}"
          }
        ],
        "fieldConfig": {
          "defaults": {
            "unit": "percent",
            "thresholds": {
              "steps": [
                { "color": "green", "value": 0 },
                { "color": "yellow", "value": 1 },
                { "color": "red", "value": 5 }
              ]
            }
          }
        }
      },
      {
        "title": "Persistence Latency (p99)",
        "type": "timeseries",
        "gridPos": { "h": 8, "w": 12, "x": 0, "y": 8 },
        "targets": [
          {
            "expr": "histogram_quantile(0.99, sum(rate(temporal_persistence_latency_bucket[5m])) by (le, operation))",
            "legendFormat": "{{ operation }}"
          }
        ],
        "fieldConfig": {
          "defaults": { "unit": "s" }
        }
      },
      {
        "title": "History Shards Status",
        "type": "stat",
        "gridPos": { "h": 4, "w": 6, "x": 12, "y": 8 },
        "targets": [
          {
            "expr": "sum(temporal_history_shard_controller_count{type=\"acquired\"})",
            "legendFormat": "Acquired"
          },
          {
            "expr": "sum(temporal_history_shard_controller_count{type=\"total\"})",
            "legendFormat": "Total"
          }
        ]
      },
      {
        "title": "Active Workflows",
        "type": "stat",
        "gridPos": { "h": 4, "w": 6, "x": 18, "y": 8 },
        "targets": [
          {
            "expr": "sum(temporal_workflow_active_count) by (namespace)",
            "legendFormat": "{{ namespace }}"
          }
        ]
      },
      {
        "title": "Schedule-to-Start Latency (p99)",
        "type": "timeseries",
        "gridPos": { "h": 8, "w": 24, "x": 0, "y": 16 },
        "targets": [
          {
            "expr": "histogram_quantile(0.99, sum(rate(temporal_workflow_task_schedule_to_start_latency_bucket[5m])) by (le, task_queue))",
            "legendFormat": "WF Task - {{ task_queue }}"
          },
          {
            "expr": "histogram_quantile(0.99, sum(rate(temporal_activity_schedule_to_start_latency_bucket[5m])) by (le, task_queue))",
            "legendFormat": "Activity - {{ task_queue }}"
          }
        ],
        "fieldConfig": {
          "defaults": {
            "unit": "s",
            "thresholds": {
              "steps": [
                { "color": "green", "value": 0 },
                { "color": "yellow", "value": 5 },
                { "color": "red", "value": 30 }
              ]
            }
          }
        }
      }
    ]
  }
}
```

### Dashboard 2: Workflow Performance

```json
{
  "dashboard": {
    "title": "Temporal - Workflow Performance",
    "uid": "temporal-workflow-perf",
    "panels": [
      {
        "title": "Workflow Starts Rate",
        "type": "timeseries",
        "gridPos": { "h": 8, "w": 12, "x": 0, "y": 0 },
        "targets": [
          {
            "expr": "sum(rate(temporal_workflow_started_total[5m])) by (workflow_type)",
            "legendFormat": "{{ workflow_type }}"
          }
        ]
      },
      {
        "title": "Workflow Completion Rate",
        "type": "timeseries",
        "gridPos": { "h": 8, "w": 12, "x": 12, "y": 0 },
        "targets": [
          {
            "expr": "sum(rate(temporal_workflow_completed_total[5m])) by (workflow_type)",
            "legendFormat": "completed - {{ workflow_type }}"
          },
          {
            "expr": "sum(rate(temporal_workflow_failed_total[5m])) by (workflow_type)",
            "legendFormat": "failed - {{ workflow_type }}"
          },
          {
            "expr": "sum(rate(temporal_workflow_timed_out_total[5m])) by (workflow_type)",
            "legendFormat": "timed_out - {{ workflow_type }}"
          }
        ]
      },
      {
        "title": "End-to-End Workflow Latency (p50, p95, p99)",
        "type": "timeseries",
        "gridPos": { "h": 8, "w": 24, "x": 0, "y": 8 },
        "targets": [
          {
            "expr": "histogram_quantile(0.50, sum(rate(temporal_workflow_endtoend_latency_bucket[5m])) by (le, workflow_type))",
            "legendFormat": "p50 - {{ workflow_type }}"
          },
          {
            "expr": "histogram_quantile(0.95, sum(rate(temporal_workflow_endtoend_latency_bucket[5m])) by (le, workflow_type))",
            "legendFormat": "p95 - {{ workflow_type }}"
          },
          {
            "expr": "histogram_quantile(0.99, sum(rate(temporal_workflow_endtoend_latency_bucket[5m])) by (le, workflow_type))",
            "legendFormat": "p99 - {{ workflow_type }}"
          }
        ]
      },
      {
        "title": "History Size Distribution",
        "type": "heatmap",
        "gridPos": { "h": 8, "w": 12, "x": 0, "y": 16 },
        "targets": [
          {
            "expr": "sum(rate(temporal_history_size_bucket[5m])) by (le)",
            "legendFormat": "{{ le }}",
            "format": "heatmap"
          }
        ]
      },
      {
        "title": "Workflow Task Execution Latency",
        "type": "timeseries",
        "gridPos": { "h": 8, "w": 12, "x": 12, "y": 16 },
        "targets": [
          {
            "expr": "histogram_quantile(0.99, sum(rate(temporal_workflow_task_execution_latency_bucket[5m])) by (le, workflow_type))",
            "legendFormat": "p99 - {{ workflow_type }}"
          }
        ],
        "fieldConfig": {
          "defaults": { "unit": "s" }
        }
      }
    ]
  }
}
```

### Dashboard 3: Worker Fleet Health

```json
{
  "dashboard": {
    "title": "Temporal - Worker Fleet",
    "uid": "temporal-worker-fleet",
    "panels": [
      {
        "title": "Worker Task Slots (Available vs Used)",
        "type": "timeseries",
        "gridPos": { "h": 8, "w": 12, "x": 0, "y": 0 },
        "targets": [
          {
            "expr": "sum(temporal_worker_task_slots_available) by (task_queue, worker_type)",
            "legendFormat": "available - {{ task_queue }} ({{ worker_type }})"
          },
          {
            "expr": "sum(temporal_worker_task_slots_used) by (task_queue, worker_type)",
            "legendFormat": "used - {{ task_queue }} ({{ worker_type }})"
          }
        ]
      },
      {
        "title": "Worker Utilization %",
        "type": "gauge",
        "gridPos": { "h": 8, "w": 12, "x": 12, "y": 0 },
        "targets": [
          {
            "expr": "sum(temporal_worker_task_slots_used) by (task_queue) / (sum(temporal_worker_task_slots_available) by (task_queue) + sum(temporal_worker_task_slots_used) by (task_queue)) * 100",
            "legendFormat": "{{ task_queue }}"
          }
        ],
        "fieldConfig": {
          "defaults": {
            "unit": "percent",
            "min": 0,
            "max": 100,
            "thresholds": {
              "steps": [
                { "color": "green", "value": 0 },
                { "color": "yellow", "value": 70 },
                { "color": "red", "value": 90 }
              ]
            }
          }
        }
      },
      {
        "title": "Activity Execution Duration",
        "type": "timeseries",
        "gridPos": { "h": 8, "w": 12, "x": 0, "y": 8 },
        "targets": [
          {
            "expr": "histogram_quantile(0.99, sum(rate(temporal_activity_execution_latency_bucket[5m])) by (le, activity_type))",
            "legendFormat": "p99 - {{ activity_type }}"
          }
        ]
      },
      {
        "title": "Worker Pod CPU/Memory",
        "type": "timeseries",
        "gridPos": { "h": 8, "w": 12, "x": 12, "y": 8 },
        "targets": [
          {
            "expr": "sum(rate(container_cpu_usage_seconds_total{namespace=\"temporal-workers\"}[5m])) by (pod)",
            "legendFormat": "CPU - {{ pod }}"
          }
        ]
      },
      {
        "title": "Worker Pods (Desired vs Ready)",
        "type": "timeseries",
        "gridPos": { "h": 8, "w": 24, "x": 0, "y": 16 },
        "targets": [
          {
            "expr": "kube_deployment_spec_replicas{namespace=\"temporal-workers\"}",
            "legendFormat": "desired - {{ deployment }}"
          },
          {
            "expr": "kube_deployment_status_replicas_ready{namespace=\"temporal-workers\"}",
            "legendFormat": "ready - {{ deployment }}"
          }
        ]
      }
    ]
  }
}
```

### Dashboard 4: Business Metrics

```json
{
  "dashboard": {
    "title": "Temporal - Business KPIs",
    "uid": "temporal-business",
    "panels": [
      {
        "title": "Payments Processed / min",
        "type": "stat",
        "targets": [{ "expr": "sum(rate(business_payments_processed_total{status=\"success\"}[5m])) * 60" }]
      },
      {
        "title": "Payment Success Rate",
        "type": "gauge",
        "targets": [{
          "expr": "sum(rate(business_payments_processed_total{status=\"success\"}[1h])) / sum(rate(business_payments_processed_total[1h])) * 100"
        }]
      },
      {
        "title": "Orders Fulfilled / hour",
        "type": "stat",
        "targets": [{ "expr": "sum(rate(business_orders_fulfilled_total[5m])) * 3600" }]
      },
      {
        "title": "Order Fulfillment Duration (p95)",
        "type": "timeseries",
        "targets": [{
          "expr": "histogram_quantile(0.95, sum(rate(business_orders_fulfillment_duration_seconds_bucket[30m])) by (le, order_type))",
          "legendFormat": "{{ order_type }}"
        }]
      }
    ]
  }
}
```

---

## Operational Runbooks

### Runbook 1: High Schedule-to-Start Latency

```
═══════════════════════════════════════════════════════════════════
RUNBOOK: High Schedule-to-Start Latency
Alert:   TemporalHighScheduleToStartLatency
Impact:  Workflows are delayed; SLA breach risk
═══════════════════════════════════════════════════════════════════

SEVERITY: P1 if > 30s, P2 if > 10s

SYMPTOMS:
- Alert: schedule-to-start p99 exceeds threshold
- Users report slow workflow execution
- Task queue backlog growing

DIAGNOSIS STEPS:

1. Identify affected task queue(s):
   $ kubectl exec -it temporal-admin-tools -- tctl taskqueue describe \
     --task-queue <queue-name> --task-queue-type workflow

   Look at: pollerCount, backlogCountHint

2. Check worker fleet health:
   $ kubectl get pods -n temporal-workers -l task-queue=<queue-name>
   $ kubectl top pods -n temporal-workers -l task-queue=<queue-name>

   Look for: CrashLoopBackOff, OOMKilled, Pending pods

3. Check if HPA is at max:
   $ kubectl get hpa -n temporal-workers

4. Check worker logs for errors:
   $ kubectl logs -n temporal-workers -l task-queue=<queue-name> --tail=100 | grep -i error

5. Check Temporal server matching service:
   $ kubectl logs -n temporal -l app.kubernetes.io/component=matching --tail=50

RESOLUTION:

A) Workers crashed/OOM:
   - Fix the root cause (memory leak, large payload)
   - Short-term: increase memory limits, restart pods
   $ kubectl rollout restart deployment/temporal-worker-<queue> -n temporal-workers

B) Insufficient workers (HPA at max):
   - Increase HPA maxReplicas
   $ kubectl patch hpa temporal-worker-<queue>-hpa -n temporal-workers \
     --type merge -p '{"spec":{"maxReplicas": 100}}'
   - Add more nodes to cluster if needed

C) Worker code bug (all activities failing fast, re-queuing):
   - Check activity error rate in Grafana
   - If 100% failure: roll back worker deployment
   $ kubectl rollout undo deployment/temporal-worker-<queue> -n temporal-workers

D) Matching service issue:
   - Check matching service CPU/memory
   - Increase task queue partitions in dynamic config
   - Restart matching pods if needed

VERIFICATION:
- schedule-to-start latency returning to normal (< 1s p99)
- Task queue backlog clearing
- Workflow completions resuming normal rate

POST-INCIDENT:
- Document root cause
- Add capacity buffer (20% above peak)
- Review HPA scaling parameters
═══════════════════════════════════════════════════════════════════
```

### Runbook 2: Database Performance Degradation

```
═══════════════════════════════════════════════════════════════════
RUNBOOK: Database Performance Degradation
Alert:   TemporalPersistenceLatencyCritical
Impact:  All workflows affected; complete cluster degradation
═══════════════════════════════════════════════════════════════════

SEVERITY: P1

SYMPTOMS:
- Persistence latency p99 > 2s
- All workflow operations slow
- Possible timeouts in history service logs

DIAGNOSIS STEPS:

1. Identify which persistence operation is slow:
   Query: histogram_quantile(0.99, sum(rate(temporal_persistence_latency_bucket[5m])) by (le, operation))
   
   Common operations: CreateWorkflowExecution, UpdateWorkflowExecution,
   GetWorkflowExecution, AppendHistoryNodes

2. FOR CASSANDRA:
   a) Check cluster status:
      $ nodetool status
      $ nodetool tpstats  # Thread pool stats
      $ nodetool compactionstats
   
   b) Check for hot partitions:
      $ nodetool tablehistograms temporal.executions
   
   c) Check disk I/O:
      $ iostat -x 1 5
   
   d) Check GC pressure:
      Look at GC logs, check heap usage
   
   e) Check compaction backlog:
      $ nodetool compactionstats
      If pending compactions > 100: compaction is behind

3. FOR POSTGRESQL:
   a) Check active connections:
      SELECT count(*), state FROM pg_stat_activity GROUP BY state;
   
   b) Check for lock contention:
      SELECT * FROM pg_stat_activity WHERE wait_event_type = 'Lock';
   
   c) Check table bloat (vacuum needed?):
      SELECT relname, n_dead_tup, n_live_tup, 
             n_dead_tup::float/GREATEST(n_live_tup,1) as dead_ratio
      FROM pg_stat_user_tables 
      ORDER BY n_dead_tup DESC LIMIT 10;
   
   d) Check slow queries:
      SELECT query, calls, mean_exec_time, total_exec_time
      FROM pg_stat_statements ORDER BY mean_exec_time DESC LIMIT 10;
   
   e) Check replication lag:
      SELECT client_addr, sent_lsn - replay_lsn as lag
      FROM pg_stat_replication;

RESOLUTION:

A) Cassandra compaction backlog:
   - Increase compaction throughput:
     $ nodetool setcompactionthroughput 256
   - Consider temporarily adding nodes

B) Cassandra node down:
   - Check if node rejoining (nodetool status shows UJ/UL)
   - If permanently down: replace node
   - Temporal should handle this with LOCAL_QUORUM

C) PostgreSQL vacuum behind:
   - Run manual vacuum:
     VACUUM (VERBOSE, ANALYZE) executions;
     VACUUM (VERBOSE, ANALYZE) history_node;
   - Increase autovacuum aggressiveness

D) PostgreSQL connection exhaustion:
   - Check PgBouncer stats
   - Increase pool size or max connections
   - Kill idle connections:
     SELECT pg_terminate_backend(pid) FROM pg_stat_activity 
     WHERE state = 'idle' AND query_start < now() - interval '10 minutes';

E) Disk I/O saturated:
   - Verify SSD/NVMe performance
   - Check for noisy neighbors (shared storage)
   - Scale up instance type

VERIFICATION:
- Persistence latency p99 < 200ms
- No error logs from history service
- Workflow starts/completions at normal rate

POST-INCIDENT:
- Review capacity planning
- Add disk I/O monitoring
- Consider database scaling (add nodes/replicas)
═══════════════════════════════════════════════════════════════════
```

### Runbook 3: Workflow Stuck in Running State

```
═══════════════════════════════════════════════════════════════════
RUNBOOK: Workflow Stuck in Running State
Alert:   Manual investigation (or TemporalLongRunningWorkflows)
Impact:  Individual workflows not progressing
═══════════════════════════════════════════════════════════════════

SEVERITY: P2-P3 (depends on business impact)

DIAGNOSIS STEPS:

1. Get workflow status:
   $ tctl workflow describe --workflow-id <wf-id> --namespace production

2. Get pending activities:
   $ tctl workflow describe --workflow-id <wf-id> | jq '.pendingActivities'
   
   Look for:
   - state: SCHEDULED (no worker picked it up)
   - state: STARTED (activity running but not completing)
   - lastFailure (activity keeps failing)
   - attempt number (high = retrying repeatedly)

3. Check workflow history for last event:
   $ tctl workflow show --workflow-id <wf-id> --output_filename /tmp/history.json
   $ cat /tmp/history.json | jq '.events[-5:]'

4. Check if workflow task is stuck:
   Look for WorkflowTaskScheduled without WorkflowTaskCompleted following it.
   This means a worker picked up the task but never responded.

RESOLUTION:

A) Activity stuck in SCHEDULED (no worker):
   - Verify workers are running for that task queue
   - Check if activity is on a different task queue than workers
   $ tctl taskqueue describe --task-queue <queue> --task-queue-type activity

B) Activity retrying forever:
   - Check the failure message in pendingActivities
   - Fix downstream service
   - Or cancel the workflow if unrecoverable:
   $ tctl workflow cancel --workflow-id <wf-id> --namespace production

C) Workflow task stuck (non-determinism suspected):
   - Check worker logs for "non-determinism" errors
   - The workflow code was changed in an incompatible way
   - Deploy fix with versioning, then reset:
   $ tctl workflow reset --workflow-id <wf-id> --reason "non-determinism fix" \
     --reset-type LastWorkflowTask --namespace production

D) Workflow waiting for signal that will never come:
   - Send the signal manually:
   $ tctl workflow signal --workflow-id <wf-id> --name <signal-name> \
     --input '{"approved": true}' --namespace production
   - Or terminate if the signal source is permanently gone:
   $ tctl workflow terminate --workflow-id <wf-id> --reason "signal source unavailable"

E) Timer-based (workflow legitimately waiting):
   - Check if there's a timer event in history
   - Verify the expected fire time
   - No action needed if timer hasn't fired yet

VERIFICATION:
- Workflow progressing (new events in history)
- Or workflow completed/terminated
═══════════════════════════════════════════════════════════════════
```

### Runbook 4: Worker OOM/Crash Loop

```
═══════════════════════════════════════════════════════════════════
RUNBOOK: Worker OOM / CrashLoopBackOff
Alert:   Pod restart alerts or TemporalNoWorkersAvailable
Impact:  Task queue has no workers; workflows delayed
═══════════════════════════════════════════════════════════════════

DIAGNOSIS:

1. Check pod status and events:
   $ kubectl describe pod <pod-name> -n temporal-workers
   Look for: OOMKilled, Error, reason for restart

2. Check previous container logs:
   $ kubectl logs <pod-name> -n temporal-workers --previous

3. Check memory usage pattern:
   Query: container_memory_working_set_bytes{pod=~"temporal-worker.*"}

4. Common OOM causes:
   - Large workflow histories loaded during replay
   - Large payloads in activities
   - Memory leak in activity code (unclosed connections)
   - Too many concurrent activities for the memory limit

RESOLUTION:

A) Large history replay:
   - Reduce MaxConcurrentWorkflowTaskExecutionSize (e.g., from 200 to 50)
   - Identify workflows with large histories:
     Query: temporal_history_size > 10MB
   - Fix: implement ContinueAsNew in those workflows
   
B) Memory leak in activity:
   - Profile: add pprof endpoint, capture heap profile
   - Common: unclosed HTTP clients, database connections, file handles
   - Short-term: increase memory limit, decrease concurrency
   $ kubectl patch deployment temporal-worker-<queue> -n temporal-workers \
     --type json -p '[{"op":"replace","path":"/spec/template/spec/containers/0/resources/limits/memory","value":"16Gi"}]'

C) Too many concurrent activities:
   - Reduce MAX_CONCURRENT_ACTIVITIES env var
   - Or increase memory limit proportionally

D) Crash (not OOM):
   - Check logs for panic stack trace
   - Fix the bug, deploy new version
   - If blocking: roll back to previous version
   $ kubectl rollout undo deployment/temporal-worker-<queue> -n temporal-workers

VERIFICATION:
- Pods stable (no restarts in 10 min)
- schedule-to-start latency normalizing
- Memory usage below 80% of limit
═══════════════════════════════════════════════════════════════════
```

### Runbook 5: Namespace Rate Limited

```
═══════════════════════════════════════════════════════════════════
RUNBOOK: Namespace Rate Limited
Alert:   TemporalNamespaceRateLimited
Impact:  Some requests failing with RESOURCE_EXHAUSTED
═══════════════════════════════════════════════════════════════════

DIAGNOSIS:

1. Check which namespace is rate limited:
   Query: sum(rate(temporal_service_errors_total{error_type="resource_exhausted"}[5m])) by (namespace, operation)

2. Check current traffic vs limits:
   Query: sum(rate(temporal_service_requests_total[5m])) by (namespace)
   Compare with: frontend.namespaceRPS in dynamic config

3. Determine if traffic spike is legitimate or a bug:
   - Check if a batch job started
   - Check if retry storms are occurring (exponential backoff missing)
   - Check if a single workflow type is dominating

RESOLUTION:

A) Legitimate traffic increase:
   - Increase namespace RPS limit in dynamic config:
   Edit dynamic-config.yaml:
     frontend.namespaceRPS:
       - value: 2400  # Increase from current
         constraints:
           namespace: "production"
   
   The config is hot-reloaded, no restart needed.

B) Retry storm (bug):
   - Identify the offending workflow/activity type
   - Fix missing backoff in client code
   - Temporarily rate-limit at the worker level:
     Set WorkerActivitiesPerSecond or TaskQueueActivitiesPerSecond

C) Runaway workflow starting too many child workflows:
   - Find the parent workflow:
     $ tctl workflow list --query "WorkflowType='BatchParent' AND ExecutionStatus='Running'"
   - Terminate if needed
   - Fix the code to throttle child workflow creation

VERIFICATION:
- resource_exhausted errors drop to 0
- Legitimate traffic flowing without errors
- RPS within limits
═══════════════════════════════════════════════════════════════════
```

---

## Distributed Tracing

### OpenTelemetry Integration

```go
// tracing.go - OpenTelemetry interceptor for Temporal
package tracing

import (
	"context"

	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/codes"
	"go.opentelemetry.io/otel/propagation"
	"go.opentelemetry.io/otel/trace"
	"go.temporal.io/sdk/interceptor"
	"go.temporal.io/sdk/workflow"
)

// TracingInterceptor propagates traces across workflow -> activity -> downstream
type TracingInterceptor struct {
	interceptor.WorkerInterceptorBase
	tracer     trace.Tracer
	propagator propagation.TextMapPropagator
}

func NewTracingInterceptor() *TracingInterceptor {
	return &TracingInterceptor{
		tracer:     otel.Tracer("temporal-worker"),
		propagator: otel.GetTextMapPropagator(),
	}
}

func (t *TracingInterceptor) InterceptActivity(
	ctx context.Context,
	next interceptor.ActivityInboundInterceptor,
) interceptor.ActivityInboundInterceptor {
	return &tracingActivityInterceptor{
		ActivityInboundInterceptorBase: interceptor.ActivityInboundInterceptorBase{Next: next},
		tracer:                         t.tracer,
	}
}

type tracingActivityInterceptor struct {
	interceptor.ActivityInboundInterceptorBase
	tracer trace.Tracer
}

func (t *tracingActivityInterceptor) ExecuteActivity(
	ctx context.Context,
	in *interceptor.ExecuteActivityInput,
) (interface{}, error) {
	info := workflow.GetActivityInfo(ctx)

	ctx, span := t.tracer.Start(ctx, "temporal.activity."+info.ActivityType.Name,
		trace.WithAttributes(
			attribute.String("temporal.workflow.id", info.WorkflowExecution.ID),
			attribute.String("temporal.workflow.run_id", info.WorkflowExecution.RunID),
			attribute.String("temporal.activity.type", info.ActivityType.Name),
			attribute.String("temporal.activity.id", info.ActivityID),
			attribute.String("temporal.task_queue", info.TaskQueue),
			attribute.Int("temporal.activity.attempt", int(info.Attempt)),
			attribute.String("temporal.namespace", info.WorkflowNamespace),
		),
	)
	defer span.End()

	result, err := t.Next.ExecuteActivity(ctx, in)
	if err != nil {
		span.RecordError(err)
		span.SetStatus(codes.Error, err.Error())
	}
	return result, err
}
```

### OpenTelemetry Collector Configuration

```yaml
# otel-collector-config.yaml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317
      http:
        endpoint: 0.0.0.0:4318

processors:
  batch:
    timeout: 5s
    send_batch_size: 512

  # Tail-based sampling: keep all errors, sample 1% of success
  tail_sampling:
    decision_wait: 10s
    num_traces: 100000
    policies:
      - name: errors-policy
        type: status_code
        status_code:
          status_codes: [ERROR]
      - name: slow-traces
        type: latency
        latency:
          threshold_ms: 5000
      - name: probabilistic-sampling
        type: probabilistic
        probabilistic:
          sampling_percentage: 1

  attributes:
    actions:
      - key: environment
        value: production
        action: upsert

exporters:
  otlp/jaeger:
    endpoint: jaeger-collector.observability.svc.cluster.local:4317
    tls:
      insecure: true

  prometheus:
    endpoint: 0.0.0.0:8889
    namespace: otel

service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [batch, tail_sampling, attributes]
      exporters: [otlp/jaeger]
    metrics:
      receivers: [otlp]
      processors: [batch]
      exporters: [prometheus]
```

---

## Log Management

### Structured Logging Standard

```go
// logging.go - Structured logging adapter for Temporal SDK
package logging

import (
	"log/slog"

	tlog "go.temporal.io/sdk/log"
)

// TemporalSlogAdapter adapts slog to Temporal's logger interface
type TemporalSlogAdapter struct {
	logger *slog.Logger
}

func NewTemporalSlogAdapter(logger *slog.Logger) *TemporalSlogAdapter {
	return &TemporalSlogAdapter{logger: logger}
}

func (l *TemporalSlogAdapter) Debug(msg string, keyvals ...interface{}) {
	l.logger.Debug(msg, keyvals...)
}

func (l *TemporalSlogAdapter) Info(msg string, keyvals ...interface{}) {
	l.logger.Info(msg, keyvals...)
}

func (l *TemporalSlogAdapter) Warn(msg string, keyvals ...interface{}) {
	l.logger.Warn(msg, keyvals...)
}

func (l *TemporalSlogAdapter) Error(msg string, keyvals ...interface{}) {
	l.logger.Error(msg, keyvals...)
}

// Ensure interface compliance
var _ tlog.Logger = (*TemporalSlogAdapter)(nil)
```

### Log Levels and What to Log

```
┌────────┬──────────────────────────────────────────────────────────────┐
│ Level  │ What to Log                                                  │
├────────┼──────────────────────────────────────────────────────────────┤
│ ERROR  │ Activity failures (after all retries exhausted)              │
│        │ Unrecoverable errors (data corruption, config errors)        │
│        │ External service errors (after circuit breaker opens)        │
│        │ Non-determinism detection                                    │
├────────┼──────────────────────────────────────────────────────────────┤
│ WARN   │ Activity retries (individual retry attempts)                 │
│        │ Approaching limits (history size > 80% threshold)            │
│        │ Degraded performance (slow responses from dependencies)      │
│        │ Circuit breaker state changes                                │
├────────┼──────────────────────────────────────────────────────────────┤
│ INFO   │ Workflow started/completed                                   │
│        │ Significant state transitions                                │
│        │ Business events (payment processed, order shipped)           │
│        │ Worker startup/shutdown                                      │
│        │ Configuration loaded                                         │
├────────┼──────────────────────────────────────────────────────────────┤
│ DEBUG  │ Activity start/complete (individual)                         │
│        │ Signal received                                              │
│        │ Timer fired                                                  │
│        │ Detailed request/response (NEVER log sensitive data)         │
└────────┴──────────────────────────────────────────────────────────────┘
```

### Loki LogQL Queries for Common Investigations

```logql
# Find all logs for a specific workflow execution
{namespace="temporal-workers"} |= "workflow_id" | json | workflow_id="order-12345"

# Find all errors in the last hour
{namespace="temporal-workers"} | json | level="ERROR" 

# Find non-determinism errors
{namespace="temporal-workers"} |= "non-determinism" | json

# Activity failures by type
sum by (activity_type) (
  count_over_time({namespace="temporal-workers"} | json | level="ERROR" | activity_type != "" [1h])
)

# Correlate across workflow execution
{namespace="temporal-workers"} | json | run_id="abc-123-def-456"
```

---

## Summary: Monitoring Maturity Model

| Level | Capabilities | Timeframe |
|-------|-------------|-----------|
| L1 - Basic | Prometheus scraping, basic alerts (up/down), default Grafana dashboards | Week 1 |
| L2 - Operational | Custom alerts (schedule-to-start, persistence), runbooks, structured logging | Week 2-3 |
| L3 - Advanced | Custom business metrics, distributed tracing, log correlation, HPA on custom metrics | Month 1-2 |
| L4 - Proactive | Anomaly detection, capacity forecasting, chaos engineering integration, SLO tracking | Month 3+ |

Target L3 for production readiness. L4 for billion-scale operations.
