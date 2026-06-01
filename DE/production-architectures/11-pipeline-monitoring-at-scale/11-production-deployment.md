# Production Deployment of Pipeline Monitoring Infrastructure

## Problem Statement

Monitoring infrastructure occupies a paradoxical position: it must be the most reliable system in your stack while simultaneously being complex distributed software itself. The "who monitors the monitor?" problem is real—if your monitoring goes down during an incident, you're flying blind.

Key challenges:
- **Reliable deployment**: Monitoring upgrades must not create gaps in observability
- **Version control**: Alert rules, dashboards, and configurations must be auditable
- **Data preservation**: Upgrades must not lose historical metrics, logs, or traces
- **Self-monitoring**: The monitoring stack must monitor itself with independent mechanisms
- **Multi-environment**: Dev/staging/prod monitoring with consistent configurations

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                          GitOps Deployment Flow                                  │
│                                                                                 │
│  ┌──────────┐    ┌──────────┐    ┌──────────────┐    ┌───────────────────────┐ │
│  │  GitHub   │───▶│  CI/CD   │───▶│   ArgoCD     │───▶│   Kubernetes Cluster  │ │
│  │  Repo     │    │ (Actions)│    │  (GitOps)    │    │                       │ │
│  └──────────┘    └──────────┘    └──────────────┘    └───────────────────────┘ │
│       │                                                        │                │
│       │  - Alert rules (.yaml)                                 │                │
│       │  - Dashboards (.jsonnet)                               ▼                │
│       │  - Helm values                          ┌──────────────────────────┐    │
│       │  - Terraform modules                    │   monitoring namespace   │    │
│       │                                         │                          │    │
│                                                 │  ┌────────┐ ┌────────┐  │    │
│                                                 │  │Prom-HA │ │Prom-HA │  │    │
│                                                 │  │Shard-0 │ │Shard-1 │  │    │
│                                                 │  └───┬────┘ └───┬────┘  │    │
│                                                 │      │          │       │    │
│                                                 │      ▼          ▼       │    │
│                                                 │  ┌──────────────────┐   │    │
│                                                 │  │  Thanos Query    │   │    │
│                                                 │  │  (Federation)    │   │    │
│                                                 │  └────────┬─────────┘   │    │
│                                                 │           │             │    │
│  ┌─────────────────────────────────────────────────────────────────────┐  │    │
│  │                    Storage Backends                                  │  │    │
│  │                                                                     │  │    │
│  │  ┌─────────────┐  ┌──────────────┐  ┌─────────────┐               │  │    │
│  │  │ S3 (Thanos  │  │ PostgreSQL   │  │ S3 (Loki    │               │  │    │
│  │  │  Metrics)   │  │ (Grafana DB) │  │  Chunks)    │               │  │    │
│  │  └─────────────┘  └──────────────┘  └─────────────┘               │  │    │
│  │                                                                     │  │    │
│  │  ┌─────────────┐  ┌──────────────┐                                │  │    │
│  │  │ S3 (Tempo   │  │ DynamoDB     │                                │  │    │
│  │  │  Traces)    │  │ (Loki Index) │                                │  │    │
│  │  └─────────────┘  └──────────────┘                                │  │    │
│  └─────────────────────────────────────────────────────────────────────┘  │    │
│                                                                           │    │
│  ┌────────────────────────────────────────────────────────────────────┐   │    │
│  │                    Visualization & Alerting                         │   │    │
│  │                                                                    │   │    │
│  │  ┌──────────┐  ┌──────────────┐  ┌──────────────┐                │   │    │
│  │  │Grafana   │  │AlertManager  │  │ PagerDuty /  │                │   │    │
│  │  │(HA x3)   │  │(Cluster x3) │  │ Slack / OG   │                │   │    │
│  │  └──────────┘  └──────────────┘  └──────────────┘                │   │    │
│  └────────────────────────────────────────────────────────────────────┘   │    │
│                                                                           │    │
└───────────────────────────────────────────────────────────────────────────────┘

                    ┌─────────────────────────────────┐
                    │   Independent Self-Monitoring    │
                    │                                 │
                    │  - Blackbox Exporter (external) │
                    │  - Synthetic checks (Pingdom)   │
                    │  - Dead man's switch (PagerDuty)│
                    └─────────────────────────────────┘
```

---

## Infrastructure as Code

### Terraform Module Structure

```
monitoring-terraform/
├── modules/
│   ├── prometheus/
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   ├── outputs.tf
│   │   └── versions.tf
│   ├── thanos/
│   │   ├── main.tf
│   │   ├── s3.tf
│   │   ├── iam.tf
│   │   └── variables.tf
│   ├── grafana/
│   │   ├── main.tf
│   │   ├── rds.tf
│   │   └── variables.tf
│   ├── loki/
│   │   ├── main.tf
│   │   ├── s3.tf
│   │   ├── dynamodb.tf
│   │   └── variables.tf
│   └── tempo/
│       ├── main.tf
│       ├── s3.tf
│       └── variables.tf
├── environments/
│   ├── dev/
│   │   ├── main.tf
│   │   └── terraform.tfvars
│   ├── staging/
│   │   ├── main.tf
│   │   └── terraform.tfvars
│   └── production/
│       ├── main.tf
│       └── terraform.tfvars
└── shared/
    ├── eks.tf
    ├── vpc.tf
    └── iam.tf
```

### Complete Terraform Module for Monitoring Stack

```hcl
# modules/monitoring-stack/main.tf

terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.12"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.25"
    }
  }
}

# --- S3 Buckets for Long-term Storage ---

resource "aws_s3_bucket" "thanos_metrics" {
  bucket = "${var.environment}-monitoring-thanos-metrics"

  tags = {
    Environment = var.environment
    Component   = "monitoring"
    ManagedBy   = "terraform"
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "thanos_lifecycle" {
  bucket = aws_s3_bucket.thanos_metrics.id

  rule {
    id     = "transition-to-ia"
    status = "Enabled"

    transition {
      days          = 30
      storage_class = "STANDARD_IA"
    }

    transition {
      days          = 90
      storage_class = "GLACIER"
    }

    expiration {
      days = var.metrics_retention_days
    }
  }
}

resource "aws_s3_bucket" "loki_chunks" {
  bucket = "${var.environment}-monitoring-loki-chunks"

  tags = {
    Environment = var.environment
    Component   = "monitoring"
  }
}

resource "aws_s3_bucket" "tempo_traces" {
  bucket = "${var.environment}-monitoring-tempo-traces"

  tags = {
    Environment = var.environment
    Component   = "monitoring"
  }
}

# --- IAM for Monitoring Components (IRSA) ---

module "thanos_irsa" {
  source = "terraform-aws-modules/iam/aws//modules/iam-role-for-service-accounts-eks"

  role_name = "${var.environment}-thanos-role"

  oidc_providers = {
    main = {
      provider_arn               = var.eks_oidc_provider_arn
      namespace_service_accounts = ["monitoring:thanos-store", "monitoring:thanos-compact"]
    }
  }
}

resource "aws_iam_role_policy" "thanos_s3" {
  name = "${var.environment}-thanos-s3-policy"
  role = module.thanos_irsa.iam_role_name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.thanos_metrics.arn,
          "${aws_s3_bucket.thanos_metrics.arn}/*"
        ]
      }
    ]
  })
}

# --- RDS for Grafana HA ---

resource "aws_db_instance" "grafana" {
  identifier = "${var.environment}-grafana-db"

  engine         = "postgres"
  engine_version = "15.4"
  instance_class = var.grafana_db_instance_class

  allocated_storage     = 50
  max_allocated_storage = 200
  storage_encrypted     = true

  db_name  = "grafana"
  username = "grafana_admin"
  password = var.grafana_db_password

  multi_az               = var.environment == "production" ? true : false
  backup_retention_period = 7
  skip_final_snapshot    = var.environment != "production"

  vpc_security_group_ids = [aws_security_group.grafana_db.id]
  db_subnet_group_name   = aws_db_subnet_group.monitoring.name

  tags = {
    Environment = var.environment
    Component   = "grafana"
  }
}

# --- DynamoDB for Loki Index ---

resource "aws_dynamodb_table" "loki_index" {
  name         = "${var.environment}-loki-index"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "h"
  range_key    = "r"

  attribute {
    name = "h"
    type = "S"
  }

  attribute {
    name = "r"
    type = "B"
  }

  point_in_time_recovery {
    enabled = true
  }

  tags = {
    Environment = var.environment
    Component   = "loki"
  }
}

# --- Kubernetes Namespace ---

resource "kubernetes_namespace" "monitoring" {
  metadata {
    name = "monitoring"

    labels = {
      "app.kubernetes.io/managed-by" = "terraform"
      "pod-security.kubernetes.io/enforce" = "privileged"
    }
  }
}

# --- Helm Release: kube-prometheus-stack ---

resource "helm_release" "kube_prometheus_stack" {
  name       = "kube-prometheus-stack"
  namespace  = kubernetes_namespace.monitoring.metadata[0].name
  repository = "https://prometheus-community.github.io/helm-charts"
  chart      = "kube-prometheus-stack"
  version    = "55.5.0"

  values = [
    templatefile("${path.module}/helm-values/kube-prometheus-stack.yaml", {
      environment          = var.environment
      thanos_bucket        = aws_s3_bucket.thanos_metrics.id
      thanos_role_arn      = module.thanos_irsa.iam_role_arn
      grafana_db_host      = aws_db_instance.grafana.endpoint
      grafana_db_password  = var.grafana_db_password
      alertmanager_replicas = var.environment == "production" ? 3 : 1
      prometheus_replicas   = var.environment == "production" ? 2 : 1
      retention_days       = var.prometheus_local_retention_days
    })
  ]

  timeout = 900

  depends_on = [
    kubernetes_namespace.monitoring,
    aws_db_instance.grafana,
  ]
}

# --- Helm Release: Loki ---

resource "helm_release" "loki" {
  name       = "loki"
  namespace  = kubernetes_namespace.monitoring.metadata[0].name
  repository = "https://grafana.github.io/helm-charts"
  chart      = "loki"
  version    = "5.41.0"

  values = [
    templatefile("${path.module}/helm-values/loki.yaml", {
      environment    = var.environment
      chunks_bucket  = aws_s3_bucket.loki_chunks.id
      dynamodb_table = aws_dynamodb_table.loki_index.name
      region         = var.aws_region
    })
  ]

  depends_on = [kubernetes_namespace.monitoring]
}

# --- Helm Release: Tempo ---

resource "helm_release" "tempo" {
  name       = "tempo"
  namespace  = kubernetes_namespace.monitoring.metadata[0].name
  repository = "https://grafana.github.io/helm-charts"
  chart      = "tempo-distributed"
  version    = "1.7.0"

  values = [
    templatefile("${path.module}/helm-values/tempo.yaml", {
      environment   = var.environment
      traces_bucket = aws_s3_bucket.tempo_traces.id
      region        = var.aws_region
    })
  ]

  depends_on = [kubernetes_namespace.monitoring]
}
```

### Variables

```hcl
# modules/monitoring-stack/variables.tf

variable "environment" {
  type        = string
  description = "Environment name (dev/staging/production)"
}

variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "eks_oidc_provider_arn" {
  type        = string
  description = "EKS OIDC provider ARN for IRSA"
}

variable "metrics_retention_days" {
  type    = number
  default = 365
}

variable "prometheus_local_retention_days" {
  type    = number
  default = 15
}

variable "grafana_db_instance_class" {
  type    = string
  default = "db.t3.medium"
}

variable "grafana_db_password" {
  type      = string
  sensitive = true
}
```

---

## Helm Values for kube-prometheus-stack

```yaml
# helm-values/kube-prometheus-stack.yaml

global:
  rbac:
    create: true

prometheus:
  prometheusSpec:
    replicas: ${prometheus_replicas}
    retention: ${retention_days}d
    retentionSize: "40GB"

    # Thanos sidecar for HA and long-term storage
    thanos:
      image: quay.io/thanos/thanos:v0.33.0
      objectStorageConfig:
        existingSecret:
          name: thanos-objstore-config
          key: objstore.yml

    # Resource limits
    resources:
      requests:
        cpu: "2"
        memory: "8Gi"
      limits:
        cpu: "4"
        memory: "16Gi"

    # Storage
    storageSpec:
      volumeClaimTemplate:
        spec:
          storageClassName: gp3
          accessModes: ["ReadWriteOnce"]
          resources:
            requests:
              storage: 100Gi

    # Pod anti-affinity for HA
    podAntiAffinity: "hard"

    # External labels for Thanos deduplication
    externalLabels:
      cluster: "${environment}"
      region: "us-east-1"

    # Rule selector - pick up all PrometheusRule CRDs
    ruleSelector: {}
    ruleNamespaceSelector: {}
    serviceMonitorSelector: {}
    serviceMonitorNamespaceSelector: {}

  # Service for Thanos sidecar
  thanosService:
    enabled: true
  thanosServiceMonitor:
    enabled: true

alertmanager:
  alertmanagerSpec:
    replicas: ${alertmanager_replicas}
    podAntiAffinity: "hard"

    storage:
      volumeClaimTemplate:
        spec:
          storageClassName: gp3
          accessModes: ["ReadWriteOnce"]
          resources:
            requests:
              storage: 10Gi

  config:
    global:
      resolve_timeout: 5m
      slack_api_url_file: /etc/alertmanager/secrets/slack-webhook-url

    route:
      group_by: ['namespace', 'alertname', 'severity']
      group_wait: 30s
      group_interval: 5m
      repeat_interval: 4h
      receiver: 'slack-default'
      routes:
        - match:
            severity: critical
          receiver: 'pagerduty-critical'
          repeat_interval: 1h
        - match:
            severity: warning
          receiver: 'slack-warnings'
          repeat_interval: 4h

    receivers:
      - name: 'slack-default'
        slack_configs:
          - channel: '#monitoring-alerts'
            send_resolved: true
      - name: 'pagerduty-critical'
        pagerduty_configs:
          - service_key_file: /etc/alertmanager/secrets/pagerduty-key
      - name: 'slack-warnings'
        slack_configs:
          - channel: '#monitoring-warnings'
            send_resolved: true

grafana:
  replicas: 3
  
  persistence:
    enabled: false  # Using external PostgreSQL

  database:
    type: postgres
    host: "${grafana_db_host}"
    name: grafana
    user: grafana_admin
    password: "${grafana_db_password}"
    ssl_mode: require

  # Dashboard provisioning
  dashboardProviders:
    dashboardproviders.yaml:
      apiVersion: 1
      providers:
        - name: 'default'
          orgId: 1
          folder: 'Pipeline Monitoring'
          type: file
          disableDeletion: true
          editable: false
          options:
            path: /var/lib/grafana/dashboards/default

  dashboardsConfigMaps:
    default: "grafana-dashboards"

  # Data source provisioning
  datasources:
    datasources.yaml:
      apiVersion: 1
      datasources:
        - name: Prometheus
          type: prometheus
          url: http://kube-prometheus-stack-prometheus:9090
          isDefault: true
        - name: Thanos
          type: prometheus
          url: http://thanos-query:9090
          jsonData:
            customQueryParameters: "dedup=true&partial_response=true"
        - name: Loki
          type: loki
          url: http://loki-gateway:80
        - name: Tempo
          type: tempo
          url: http://tempo-query-frontend:3100
          jsonData:
            tracesToLogs:
              datasourceUid: loki
              tags: ['job', 'namespace', 'pod']

  ingress:
    enabled: true
    ingressClassName: alb
    annotations:
      alb.ingress.kubernetes.io/scheme: internal
      alb.ingress.kubernetes.io/certificate-arn: "${grafana_cert_arn}"
    hosts:
      - grafana.internal.company.com
```

---

## Deployment Strategies

### Blue-Green Deployment for Grafana

```yaml
# grafana-blue-green.yaml
# Strategy: Deploy new Grafana version as "green", validate, switch traffic

apiVersion: argoproj.io/v1alpha1
kind: Rollout
metadata:
  name: grafana
  namespace: monitoring
spec:
  replicas: 3
  strategy:
    blueGreen:
      activeService: grafana-active
      previewService: grafana-preview
      autoPromotionEnabled: false
      prePromotionAnalysis:
        templates:
          - templateName: grafana-health-check
        args:
          - name: service-name
            value: grafana-preview
      scaleDownDelaySeconds: 300
  selector:
    matchLabels:
      app: grafana
  template:
    metadata:
      labels:
        app: grafana
    spec:
      containers:
        - name: grafana
          image: grafana/grafana:10.2.3
          ports:
            - containerPort: 3000
          readinessProbe:
            httpGet:
              path: /api/health
              port: 3000
            initialDelaySeconds: 10
            periodSeconds: 5
          livenessProbe:
            httpGet:
              path: /api/health
              port: 3000
            initialDelaySeconds: 30
            periodSeconds: 10
---
apiVersion: argoproj.io/v1alpha1
kind: AnalysisTemplate
metadata:
  name: grafana-health-check
  namespace: monitoring
spec:
  args:
    - name: service-name
  metrics:
    - name: grafana-api-health
      interval: 30s
      count: 5
      successCondition: result == "ok"
      provider:
        web:
          url: "http://{{args.service-name}}.monitoring.svc:3000/api/health"
          jsonPath: "{$.database}"
    - name: dashboard-load-test
      interval: 60s
      count: 3
      successCondition: result[0] < 2000
      provider:
        prometheus:
          address: http://prometheus:9090
          query: |
            histogram_quantile(0.95,
              rate(grafana_http_request_duration_seconds_bucket{
                service="{{args.service-name}}"
              }[5m])
            ) * 1000
```

### Canary Deployment for Alert Rules

```yaml
# alert-rule-canary.yaml
# Strategy: Deploy new alert rules to a subset first, validate no false positives

apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: pipeline-alerts-canary
  namespace: monitoring
  labels:
    release: kube-prometheus-stack
    alert-stage: canary  # Only evaluated by canary Prometheus
spec:
  groups:
    - name: pipeline.canary.rules
      rules:
        - alert: PipelineLatencyHighCanary
          expr: |
            histogram_quantile(0.99, 
              rate(pipeline_processing_duration_seconds_bucket[5m])
            ) > 30
          for: 10m
          labels:
            severity: warning
            stage: canary
          annotations:
            summary: "CANARY: Pipeline latency p99 > 30s"
            runbook_url: "https://runbooks.company.com/pipeline-latency"
```

### Zero-Downtime Storage Migration

```bash
#!/bin/bash
# migrate-thanos-storage.sh
# Migrate Thanos from one S3 bucket to another without data loss

set -euo pipefail

OLD_BUCKET="prod-monitoring-thanos-v1"
NEW_BUCKET="prod-monitoring-thanos-v2"
THANOS_NAMESPACE="monitoring"

echo "=== Phase 1: Sync existing data ==="
aws s3 sync "s3://${OLD_BUCKET}" "s3://${NEW_BUCKET}" \
  --source-region us-east-1 \
  --region us-east-1

echo "=== Phase 2: Update Thanos store to dual-read ==="
kubectl apply -f - <<EOF
apiVersion: v1
kind: Secret
metadata:
  name: thanos-objstore-config
  namespace: ${THANOS_NAMESPACE}
stringData:
  objstore.yml: |
    type: S3
    config:
      bucket: "${NEW_BUCKET}"
      endpoint: s3.us-east-1.amazonaws.com
      region: us-east-1
EOF

echo "=== Phase 3: Rolling restart of Thanos components ==="
kubectl rollout restart statefulset/thanos-store -n ${THANOS_NAMESPACE}
kubectl rollout status statefulset/thanos-store -n ${THANOS_NAMESPACE} --timeout=300s

kubectl rollout restart deployment/thanos-compact -n ${THANOS_NAMESPACE}
kubectl rollout status deployment/thanos-compact -n ${THANOS_NAMESPACE} --timeout=300s

echo "=== Phase 4: Update Prometheus sidecar config ==="
kubectl rollout restart statefulset/prometheus-kube-prometheus-stack -n ${THANOS_NAMESPACE}
kubectl rollout status statefulset/prometheus-kube-prometheus-stack -n ${THANOS_NAMESPACE} --timeout=600s

echo "=== Phase 5: Validate ==="
# Query Thanos to ensure data continuity
RESULT=$(curl -s "http://thanos-query:9090/api/v1/query?query=up" | jq '.status')
if [ "$RESULT" == '"success"' ]; then
  echo "Migration successful. Old bucket can be archived after retention period."
else
  echo "ERROR: Validation failed. Rolling back..."
  exit 1
fi
```

---

## GitOps for Monitoring

### ArgoCD Application Manifests

```yaml
# argocd/monitoring-app.yaml

apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: monitoring-stack
  namespace: argocd
  finalizers:
    - resources-finalizer.argocd.argoproj.io
spec:
  project: platform
  source:
    repoURL: https://github.com/company/monitoring-config.git
    targetRevision: main
    path: environments/production
    helm:
      valueFiles:
        - values.yaml
        - values-production.yaml
  destination:
    server: https://kubernetes.default.svc
    namespace: monitoring
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
      - ServerSideApply=true
    retry:
      limit: 5
      backoff:
        duration: 5s
        factor: 2
        maxDuration: 3m
  ignoreDifferences:
    - group: ""
      kind: Secret
      jsonPointers:
        - /data
---
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: alert-rules
  namespace: argocd
spec:
  project: platform
  source:
    repoURL: https://github.com/company/alert-rules.git
    targetRevision: main
    path: rules/production
    directory:
      recurse: true
  destination:
    server: https://kubernetes.default.svc
    namespace: monitoring
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
```

### Dashboard as Code (Grafonnet)

```jsonnet
// dashboards/pipeline-overview.jsonnet

local grafana = import 'grafonnet/grafana.libsonnet';
local dashboard = grafana.dashboard;
local row = grafana.row;
local prometheus = grafana.prometheus;
local graphPanel = grafana.graphPanel;
local statPanel = grafana.statPanel;
local template = grafana.template;

local datasource = 'Thanos';

dashboard.new(
  'Data Pipeline Overview',
  tags=['pipeline', 'data-engineering'],
  schemaVersion=30,
  refresh='30s',
  time_from='now-6h',
)
.addTemplate(
  template.datasource('datasource', 'prometheus', datasource)
)
.addTemplate(
  template.new(
    'pipeline',
    datasource,
    'label_values(pipeline_events_processed_total, pipeline)',
    refresh='time',
    multi=true,
    includeAll=true,
  )
)
.addRow(
  row.new(title='Pipeline Health')
  .addPanel(
    statPanel.new(
      'Events Processed (24h)',
      datasource=datasource,
    )
    .addTarget(
      prometheus.target(
        'sum(increase(pipeline_events_processed_total{pipeline=~"$pipeline"}[24h]))',
        legendFormat='Total Events',
      )
    )
    + { fieldConfig: { defaults: { unit: 'short', decimals: 0 } } },
    gridPos={ x: 0, y: 0, w: 6, h: 4 },
  )
  .addPanel(
    statPanel.new(
      'Pipeline Success Rate',
      datasource=datasource,
    )
    .addTarget(
      prometheus.target(
        |||
          sum(rate(pipeline_events_processed_total{pipeline=~"$pipeline", status="success"}[1h]))
          /
          sum(rate(pipeline_events_processed_total{pipeline=~"$pipeline"}[1h]))
          * 100
        |||,
        legendFormat='Success %',
      )
    )
    + { fieldConfig: { defaults: { unit: 'percent', thresholds: {
      steps: [
        { value: 0, color: 'red' },
        { value: 95, color: 'yellow' },
        { value: 99, color: 'green' },
      ]
    } } } },
    gridPos={ x: 6, y: 0, w: 6, h: 4 },
  )
  .addPanel(
    graphPanel.new(
      'Processing Latency (p50/p95/p99)',
      datasource=datasource,
      span=12,
    )
    .addTarget(
      prometheus.target(
        'histogram_quantile(0.50, sum(rate(pipeline_processing_duration_seconds_bucket{pipeline=~"$pipeline"}[5m])) by (le))',
        legendFormat='p50',
      )
    )
    .addTarget(
      prometheus.target(
        'histogram_quantile(0.95, sum(rate(pipeline_processing_duration_seconds_bucket{pipeline=~"$pipeline"}[5m])) by (le))',
        legendFormat='p95',
      )
    )
    .addTarget(
      prometheus.target(
        'histogram_quantile(0.99, sum(rate(pipeline_processing_duration_seconds_bucket{pipeline=~"$pipeline"}[5m])) by (le))',
        legendFormat='p99',
      )
    ),
    gridPos={ x: 0, y: 4, w: 24, h: 8 },
  )
)
```

### Alert Rule CI/CD Pipeline

```yaml
# .github/workflows/alert-rules-ci.yaml

name: Alert Rules CI/CD

on:
  pull_request:
    paths:
      - 'rules/**'
  push:
    branches: [main]
    paths:
      - 'rules/**'

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install promtool
        run: |
          PROM_VERSION="2.48.1"
          wget -q "https://github.com/prometheus/prometheus/releases/download/v${PROM_VERSION}/prometheus-${PROM_VERSION}.linux-amd64.tar.gz"
          tar xzf "prometheus-${PROM_VERSION}.linux-amd64.tar.gz"
          sudo mv "prometheus-${PROM_VERSION}.linux-amd64/promtool" /usr/local/bin/

      - name: Lint alert rules
        run: |
          find rules/ -name '*.yaml' -o -name '*.yml' | while read f; do
            echo "Validating: $f"
            promtool check rules "$f"
          done

      - name: Unit test alert rules
        run: |
          find tests/ -name '*_test.yaml' -o -name '*_test.yml' | while read f; do
            echo "Testing: $f"
            promtool test rules "$f"
          done

      - name: Check for high-cardinality queries
        run: |
          python3 scripts/check_cardinality.py rules/

  cost-estimate:
    runs-on: ubuntu-latest
    if: github.event_name == 'pull_request'
    steps:
      - uses: actions/checkout@v4

      - name: Estimate alert evaluation cost
        run: |
          python3 scripts/estimate_alert_cost.py \
            --rules-dir rules/ \
            --prometheus-url ${{ secrets.PROMETHEUS_URL }} \
            --output cost-report.md

      - name: Comment cost estimate on PR
        uses: actions/github-script@v7
        with:
          script: |
            const fs = require('fs');
            const report = fs.readFileSync('cost-report.md', 'utf8');
            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: report
            });

  deploy:
    needs: validate
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Trigger ArgoCD sync
        run: |
          argocd app sync alert-rules \
            --server ${{ secrets.ARGOCD_SERVER }} \
            --auth-token ${{ secrets.ARGOCD_TOKEN }}
```

### Alert Rule Unit Tests

```yaml
# tests/pipeline_alerts_test.yaml

rule_files:
  - ../rules/production/pipeline-alerts.yaml

evaluation_interval: 1m

tests:
  - interval: 1m
    input_series:
      - series: 'pipeline_events_processed_total{pipeline="ingestion", status="success"}'
        values: '100+100x60'  # 100 events/min for 60 minutes
      - series: 'pipeline_events_processed_total{pipeline="ingestion", status="failed"}'
        values: '0+0x50 0+10x10'  # 0 failures for 50min, then 10/min for 10min

    alert_rule_test:
      - eval_time: 55m
        alertname: PipelineHighErrorRate
        exp_alerts: []  # No alert yet

      - eval_time: 65m
        alertname: PipelineHighErrorRate
        exp_alerts:
          - exp_labels:
              severity: critical
              pipeline: ingestion
            exp_annotations:
              summary: "Pipeline ingestion error rate above 5%"

  - interval: 1m
    input_series:
      - series: 'pipeline_lag_seconds{pipeline="transform", partition="0"}'
        values: '10+10x30'  # Increasing lag

    alert_rule_test:
      - eval_time: 20m
        alertname: PipelineLagCritical
        exp_alerts:
          - exp_labels:
              severity: critical
              pipeline: transform
```

---

## High Availability Setup

### Prometheus HA with Thanos

```
┌─────────────────────────────────────────────────────────────┐
│                    Prometheus HA Architecture                │
│                                                             │
│  AZ-1                          AZ-2                         │
│  ┌────────────────────┐       ┌────────────────────┐       │
│  │ Prometheus-0       │       │ Prometheus-1       │       │
│  │ ┌────────────────┐ │       │ ┌────────────────┐ │       │
│  │ │  TSDB (15d)    │ │       │ │  TSDB (15d)    │ │       │
│  │ └────────────────┘ │       │ └────────────────┘ │       │
│  │ ┌────────────────┐ │       │ ┌────────────────┐ │       │
│  │ │ Thanos Sidecar │─┼───┐   │ │ Thanos Sidecar │─┼──┐   │
│  │ └────────────────┘ │   │   │ └────────────────┘ │  │   │
│  └────────────────────┘   │   └────────────────────┘  │   │
│                           │                            │   │
│                           ▼                            ▼   │
│                    ┌──────────────────────────────────┐    │
│                    │         S3 (Long-term)           │    │
│                    └──────────────┬───────────────────┘    │
│                                   │                        │
│  ┌────────────────┐    ┌─────────┴──────────┐            │
│  │ Thanos Compact │    │   Thanos Store      │            │
│  │ (Downsampling) │    │   (S3 Gateway)      │            │
│  └────────────────┘    └─────────┬──────────┘            │
│                                   │                        │
│                    ┌──────────────┴───────────────┐       │
│                    │      Thanos Query            │       │
│                    │  (Deduplication + Fan-out)   │       │
│                    └──────────────────────────────┘       │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Thanos Components Configuration

```yaml
# thanos-query.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: thanos-query
  namespace: monitoring
spec:
  replicas: 3
  selector:
    matchLabels:
      app: thanos-query
  template:
    metadata:
      labels:
        app: thanos-query
    spec:
      affinity:
        podAntiAffinity:
          requiredDuringSchedulingIgnoredDuringExecution:
            - labelSelector:
                matchLabels:
                  app: thanos-query
              topologyKey: topology.kubernetes.io/zone
      containers:
        - name: thanos-query
          image: quay.io/thanos/thanos:v0.33.0
          args:
            - query
            - --log.level=info
            - --query.replica-label=prometheus_replica
            - --query.auto-downsampling
            - --store=dnssrv+_grpc._tcp.thanos-store.monitoring.svc
            - --store=dnssrv+_grpc._tcp.prometheus-operated.monitoring.svc
          ports:
            - name: http
              containerPort: 10902
            - name: grpc
              containerPort: 10901
          resources:
            requests:
              cpu: "1"
              memory: "2Gi"
            limits:
              cpu: "2"
              memory: "4Gi"
```

---

## Day-2 Operations

### Cardinality Management

```python
#!/usr/bin/env python3
"""
cardinality_audit.py - Detect and alert on metric cardinality explosion
Run daily via CronJob to identify problematic metrics.
"""

import requests
import json
from datetime import datetime

PROMETHEUS_URL = "http://thanos-query:9090"
CARDINALITY_THRESHOLD = 10000  # Alert if metric has >10K series
GROWTH_RATE_THRESHOLD = 0.2    # Alert if >20% growth per day

def get_tsdb_status():
    """Get TSDB cardinality stats from Prometheus."""
    resp = requests.get(f"{PROMETHEUS_URL}/api/v1/status/tsdb")
    resp.raise_for_status()
    return resp.json()["data"]

def get_metric_cardinality(metric_name: str) -> int:
    """Count active series for a given metric."""
    query = f'count({metric_name})'
    resp = requests.get(
        f"{PROMETHEUS_URL}/api/v1/query",
        params={"query": query}
    )
    resp.raise_for_status()
    result = resp.json()["data"]["result"]
    return int(result[0]["value"][1]) if result else 0

def audit_cardinality():
    """Main audit function."""
    status = get_tsdb_status()
    
    report = {
        "timestamp": datetime.utcnow().isoformat(),
        "total_series": status["headStats"]["numSeries"],
        "high_cardinality_metrics": [],
        "top_label_pairs": status["labelValueCountByLabelName"][:20],
    }
    
    # Check top metrics by cardinality
    for metric_info in status["seriesCountByMetricName"][:50]:
        metric_name = metric_info["name"]
        count = metric_info["value"]
        
        if count > CARDINALITY_THRESHOLD:
            report["high_cardinality_metrics"].append({
                "metric": metric_name,
                "series_count": count,
                "action": "REVIEW - Consider relabeling or dropping"
            })
    
    # Check for unbounded labels
    for label_info in status["labelValueCountByLabelName"][:20]:
        label_name = label_info["name"]
        value_count = label_info["value"]
        
        if value_count > 50000:
            report["high_cardinality_metrics"].append({
                "label": label_name,
                "unique_values": value_count,
                "action": "CRITICAL - Unbounded label detected"
            })
    
    return report

def send_alert(report):
    """Send cardinality alert to Slack."""
    if not report["high_cardinality_metrics"]:
        return
    
    webhook_url = "https://hooks.slack.com/services/XXX/YYY/ZZZ"
    
    message = f"*Cardinality Audit Report*\n"
    message += f"Total series: {report['total_series']:,}\n\n"
    
    for item in report["high_cardinality_metrics"][:10]:
        if "metric" in item:
            message += f"• `{item['metric']}`: {item['series_count']:,} series\n"
        else:
            message += f"• Label `{item['label']}`: {item['unique_values']:,} values\n"
    
    requests.post(webhook_url, json={"text": message})

if __name__ == "__main__":
    report = audit_cardinality()
    print(json.dumps(report, indent=2))
    send_alert(report)
```

### Monitoring Self-Health Checks

```yaml
# self-monitoring-rules.yaml
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: monitoring-self-health
  namespace: monitoring
spec:
  groups:
    - name: monitoring.self.health
      rules:
        # Dead man's switch - always fires, absence means Prometheus is down
        - alert: DeadMansSwitch
          expr: vector(1)
          labels:
            severity: none
          annotations:
            summary: "Dead man's switch - monitoring is alive"

        # Prometheus can't scrape targets
        - alert: PrometheusTargetDown
          expr: up == 0
          for: 5m
          labels:
            severity: warning
          annotations:
            summary: "Target {{ $labels.job }} is down"

        # Prometheus TSDB issues
        - alert: PrometheusTSDBCompactionsFailed
          expr: increase(prometheus_tsdb_compactions_failed_total[1h]) > 0
          for: 5m
          labels:
            severity: critical
          annotations:
            summary: "Prometheus TSDB compaction failures"

        # AlertManager not sending notifications
        - alert: AlertManagerFailedNotifications
          expr: |
            rate(alertmanager_notifications_failed_total[5m]) > 0
          for: 5m
          labels:
            severity: critical
          annotations:
            summary: "AlertManager failing to send notifications"

        # Thanos sidecar unhealthy
        - alert: ThanosSidecarUnhealthy
          expr: |
            time() - max(thanos_sidecar_last_heartbeat_success_time_seconds) > 300
          for: 5m
          labels:
            severity: critical
          annotations:
            summary: "Thanos sidecar not uploading blocks"

        # Storage capacity
        - alert: PrometheusStorageNearFull
          expr: |
            (prometheus_tsdb_storage_blocks_bytes / 
             prometheus_tsdb_retention_limit_bytes) > 0.85
          for: 15m
          labels:
            severity: warning
          annotations:
            summary: "Prometheus storage >85% of retention limit"

        # Query latency degradation
        - alert: PrometheusQueryLatencyHigh
          expr: |
            histogram_quantile(0.99, 
              rate(prometheus_engine_query_duration_seconds_bucket[5m])
            ) > 30
          for: 10m
          labels:
            severity: warning
          annotations:
            summary: "Prometheus query p99 latency >30s"
```

---

## Capacity Planning

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Capacity Planning Formula                         │
│                                                                     │
│  Metrics Storage:                                                   │
│    bytes/day = active_series × scrape_interval_samples × 2 bytes    │
│                                                                     │
│    Example: 500K series × 8640 samples/day × 2B = ~8.6 GB/day     │
│    With compression (~10x): ~860 MB/day                            │
│    15-day local retention: ~13 GB per Prometheus instance           │
│                                                                     │
│  Log Storage:                                                       │
│    bytes/day = log_lines/day × avg_line_size                       │
│                                                                     │
│    Example: 10B lines × 200 bytes = 2 TB/day (raw)                │
│    With Loki compression (~15x): ~133 GB/day                       │
│    30-day retention: ~4 TB                                          │
│                                                                     │
│  Trace Storage:                                                     │
│    bytes/day = spans/day × avg_span_size × sampling_rate           │
│                                                                     │
│    Example: 1B spans × 500 bytes × 1% sample = 5 GB/day           │
│    7-day retention: ~35 GB                                          │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Cost Optimization Strategies

| Strategy | Impact | Implementation Effort |
|----------|--------|----------------------|
| Recording rules for heavy queries | High | Low |
| Metric relabeling (drop unused) | High | Medium |
| Increase scrape interval for non-critical | Medium | Low |
| Thanos downsampling (5m, 1h) | High | Low (automatic) |
| Log filtering at source | High | Medium |
| Trace tail-based sampling | High | High |
| Move to object storage earlier | Medium | Medium |

---

## Summary

Production deployment of monitoring infrastructure requires treating monitoring as a first-class service with its own SLOs, capacity planning, and operational runbooks. The key principles:

1. **GitOps everything** - All config in version control, deployed via ArgoCD
2. **HA by default** - No single points of failure in the monitoring path
3. **Self-monitoring** - Independent health checks and dead man's switches
4. **Graceful degradation** - Monitoring should degrade gracefully under load
5. **Cost awareness** - Monitor the cost of monitoring itself
