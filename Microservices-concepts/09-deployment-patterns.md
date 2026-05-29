# Deployment Patterns for Microservices

## Table of Contents
- [Deployment Strategies](#deployment-strategies)
- [Container Patterns](#container-patterns)
- [Orchestration & Infrastructure](#orchestration--infrastructure)
- [CI/CD Patterns](#cicd-patterns)
- [Release Management](#release-management)

---

## Deployment Strategies

### 1. Blue-Green Deployment

**What it is:** Maintain two identical production environments (Blue = current, Green = new). Switch traffic atomically between them.

**How it works:**
1. Blue environment serves all production traffic
2. Deploy new version to Green environment
3. Run smoke tests on Green
4. Switch load balancer/router to point to Green
5. Blue becomes standby (rollback target)

**Architecture:**
```
                    ┌─────────────────┐
                    │   Load Balancer  │
                    │   / Router       │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
              ▼              │              ▼
   ┌──────────────────┐     │   ┌──────────────────┐
   │  BLUE Environment │     │   │ GREEN Environment │
   │  (v1.0 - Active) │◄────┘   │  (v1.1 - Idle)   │
   │                   │  OR     │                   │
   │  Service A v1.0   │────────►│  Service A v1.1   │
   │  Service B v1.0   │         │  Service B v1.0   │
   │  Database (shared)│         │  Database (shared)│
   └──────────────────┘         └──────────────────┘
```

**Steps to implement:**
1. Provision two identical environments (infra-as-code)
2. Deploy new version to inactive environment
3. Run automated health checks and smoke tests
4. Update DNS/LB to switch traffic
5. Monitor for errors; rollback by switching back
6. Decommission old environment or keep as standby

**Pros:**
- Zero downtime deployment
- Instant rollback (switch back to Blue)
- Full environment testing before go-live
- Reduces deployment risk

**Cons:**
- Double infrastructure cost
- Database migrations are complex (shared DB)
- Long-running transactions during switch can fail
- Stateful services need careful handling

**Tools:** AWS Elastic Beanstalk, Kubernetes Services, Nginx, HAProxy, AWS Route53 weighted routing

**When to use:**
- Critical services requiring zero downtime
- When instant rollback is mandatory
- Compliance-heavy environments needing full pre-production validation

---

### 2. Canary Deployment

**What it is:** Gradually roll out changes to a small subset of users/traffic before full deployment.

**How it works:**
1. Deploy new version alongside old version
2. Route small percentage (1-5%) of traffic to new version
3. Monitor error rates, latency, business metrics
4. Gradually increase traffic (5% → 25% → 50% → 100%)
5. Rollback if metrics degrade

**Architecture:**
```
         ┌────────────────────────┐
         │     Ingress / Router    │
         │  (Traffic Splitting)    │
         └─────┬──────────┬───────┘
               │ 95%      │ 5%
               ▼          ▼
    ┌─────────────┐  ┌─────────────┐
    │  Stable v1  │  │  Canary v2  │
    │  (10 pods)  │  │  (1 pod)    │
    └─────────────┘  └─────────────┘
               │          │
               ▼          ▼
    ┌─────────────────────────────┐
    │   Metrics / Monitoring       │
    │   (Prometheus, Datadog)      │
    │   Error Rate < 0.1%?         │
    │   Latency P99 < 200ms?      │
    └─────────────────────────────┘
```

**Steps to implement:**
1. Deploy canary version with minimal replicas
2. Configure traffic splitting (Istio VirtualService, Nginx weight)
3. Define success criteria (SLOs: error rate, latency, saturation)
4. Automate metric analysis (Kayenta, Flagger)
5. Progressive traffic increase on success
6. Auto-rollback on failure

**Pros:**
- Low risk: only small subset affected by bugs
- Real production traffic validation
- Can target specific user segments
- Data-driven deployment decisions

**Cons:**
- More complex infrastructure (traffic splitting)
- Slower deployment cycle
- Need robust monitoring/observability
- Database schema changes still tricky

**Tools:** Istio, Flagger, Argo Rollouts, Spinnaker (Kayenta), AWS App Mesh, Linkerd

**When to use:**
- High-traffic services where bugs have large blast radius
- When you need production validation before full rollout
- Services with complex behavior hard to test in staging

---

### 3. Rolling Deployment

**What it is:** Incrementally replace old version instances with new version instances, one (or a batch) at a time.

**How it works:**
1. Take one instance out of load balancer
2. Deploy new version to that instance
3. Health check the new instance
4. Add it back to load balancer
5. Repeat for all instances

**Architecture:**
```
Time T0:  [v1] [v1] [v1] [v1] [v1]   ← All old
Time T1:  [v2] [v1] [v1] [v1] [v1]   ← 1 updated
Time T2:  [v2] [v2] [v1] [v1] [v1]   ← 2 updated
Time T3:  [v2] [v2] [v2] [v1] [v1]   ← 3 updated
Time T4:  [v2] [v2] [v2] [v2] [v1]   ← 4 updated
Time T5:  [v2] [v2] [v2] [v2] [v2]   ← All new

Kubernetes RollingUpdate:
  maxSurge: 1        (1 extra pod during rollout)
  maxUnavailable: 0  (no downtime)
```

**Steps to implement:**
1. Configure Kubernetes Deployment with `strategy: RollingUpdate`
2. Set `maxSurge` and `maxUnavailable`
3. Define readiness/liveness probes
4. Deploy: `kubectl apply` triggers rolling update
5. Monitor: `kubectl rollout status`
6. Rollback: `kubectl rollout undo`

**Pros:**
- No additional infrastructure needed
- Zero downtime (with proper health checks)
- Built into Kubernetes natively
- Simple to implement

**Cons:**
- Two versions run simultaneously (compatibility needed)
- Slow rollback (must roll forward or undo entire rollout)
- No traffic control granularity
- Hard to test full deployment before commit

**Tools:** Kubernetes Deployment, AWS ECS Rolling Update, Docker Swarm

**When to use:**
- Default strategy for most services
- When backward compatibility is maintained
- Simple services without complex traffic routing needs

---

### 4. A/B Testing Deployment

**What it is:** Route specific user segments to different versions to measure business impact, not just technical health.

**How it works:**
1. Deploy multiple versions simultaneously
2. Route users based on attributes (location, user ID, headers)
3. Measure business metrics (conversion, revenue, engagement)
4. Statistically determine winner
5. Promote winning version

**Architecture:**
```
         ┌────────────────────────────┐
         │      Smart Router           │
         │  (Header/Cookie Based)      │
         └───┬────────────────┬───────┘
             │                │
    User-Agent: mobile   User-Agent: desktop
             │                │
             ▼                ▼
    ┌──────────────┐  ┌──────────────┐
    │  Version A    │  │  Version B    │
    │  (New UI)     │  │  (Old UI)     │
    └──────────────┘  └──────────────┘
             │                │
             ▼                ▼
    ┌─────────────────────────────────┐
    │    Analytics / Experimentation   │
    │    Platform (Optimizely, etc.)   │
    │    - Conversion Rate            │
    │    - Revenue per User            │
    │    - Statistical Significance    │
    └─────────────────────────────────┘
```

**Steps to implement:**
1. Define experiment hypothesis and success metrics
2. Deploy both versions
3. Configure routing rules (Istio, feature flag service)
4. Implement tracking/analytics
5. Run experiment for statistical significance
6. Analyze results and promote winner

**Pros:**
- Data-driven product decisions
- Measure real business impact
- Can run multiple experiments simultaneously
- Users get consistent experience (sticky sessions)

**Cons:**
- Complex routing infrastructure
- Need statistical rigor (sample size, duration)
- Multiple versions to maintain
- Can lead to technical debt

**Tools:** LaunchDarkly, Optimizely, Istio, Split.io, Unleash, Statsig

**When to use:**
- Product feature validation
- UX changes measurement
- Pricing experiments
- When business metrics matter more than technical metrics

---

### 5. Shadow/Dark Deployment (Traffic Mirroring)

**What it is:** Send a copy of production traffic to new version without affecting users. Compare responses without risk.

**How it works:**
1. Deploy new version alongside production
2. Mirror (fork) production traffic to shadow version
3. Shadow processes requests but responses are discarded
4. Compare latency, errors, responses between versions
5. Promote shadow to production when confident

**Architecture:**
```
    ┌───────────┐
    │   Client   │
    └─────┬─────┘
          │
          ▼
    ┌─────────────────┐
    │  Service Mesh /  │
    │  Proxy (Envoy)   │
    └──┬──────────┬───┘
       │          │ (mirror - fire & forget)
       ▼          ▼
  ┌─────────┐  ┌─────────┐
  │ Primary  │  │ Shadow   │
  │ v1.0     │  │ v2.0     │
  │(responds)│  │(discards)│
  └─────────┘  └─────────┘
       │          │
       ▼          ▼
  ┌─────────────────────┐
  │  Diff Comparator     │
  │  Response A vs B     │
  │  Latency comparison  │
  └─────────────────────┘
```

**Steps to implement:**
1. Deploy shadow version with same dependencies
2. Configure traffic mirroring (Istio `mirror:` field)
3. Ensure shadow has no side effects (read-only, or separate DB)
4. Collect and compare responses
5. Analyze differences, fix bugs
6. Promote when response diff is acceptable

**Pros:**
- Zero risk to production users
- Real production traffic patterns
- Can catch issues invisible in staging
- Great for performance testing

**Cons:**
- Double the resource usage
- Side effects must be prevented (writes, external calls)
- Response comparison can be complex
- Doesn't validate user-facing behavior

**Tools:** Istio (traffic mirroring), Envoy, Diffy (Twitter), GoReplay

**When to use:**
- Major refactoring or rewrites
- Database migration validation
- Performance regression testing
- When you can't afford any production impact

---

### 6. Feature Flags / Feature Toggles

**What it is:** Decouple deployment from release. Deploy code with features hidden behind flags, enable/disable without redeployment.

**Types of toggles:**
- **Release Toggles:** Hide incomplete features in production
- **Experiment Toggles:** A/B testing
- **Ops Toggles:** Kill switches for features under load
- **Permission Toggles:** Premium features for specific users

**Architecture:**
```
    ┌──────────────┐     ┌───────────────────┐
    │  Service A    │────►│  Feature Flag      │
    │               │     │  Service           │
    │  if (flag.    │     │  (LaunchDarkly/    │
    │   isEnabled(  │     │   Unleash)         │
    │   "new-algo"))│     │                    │
    │    useNewAlgo │     │  ┌──────────────┐  │
    │  else         │     │  │ Flag Store    │  │
    │    useOldAlgo │     │  │ new-algo: ON  │  │
    │               │     │  │ dark-mode: 50%│  │
    └──────────────┘     │  │ beta-ui: OFF  │  │
                          │  └──────────────┘  │
                          └───────────────────┘
```

**Steps to implement:**
1. Choose feature flag service (or build simple one)
2. Wrap new code in flag checks
3. Deploy with flag OFF
4. Enable flag for internal users → beta → all
5. Remove flag and dead code after full rollout

**Pros:**
- Deploy anytime, release when ready
- Instant kill switch (ops toggles)
- Targeted rollouts (user segments)
- Enables trunk-based development

**Cons:**
- Technical debt (old flags left in code)
- Testing combinatorial explosion
- Flag dependencies create complexity
- Need lifecycle management

**Tools:** LaunchDarkly, Unleash, Flagsmith, Split.io, ConfigCat, AWS AppConfig

**When to use:**
- Trunk-based development workflow
- Gradual feature rollouts
- Kill switches for risky features
- Multi-tenant feature enablement

---

### 7. Immutable Infrastructure

**What it is:** Never modify running infrastructure. Instead, build new images and replace entirely.

**How it works:**
1. Build artifact (Docker image, AMI, VM image)
2. Test artifact in staging
3. Deploy by replacing instances with new image
4. Never SSH in, never patch in-place

**Architecture:**
```
    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
    │   Code       │    │  Build       │    │  Image       │
    │   Commit     │───►│  Pipeline    │───►│  Registry    │
    └─────────────┘    └─────────────┘    └──────┬──────┘
                                                  │
                    ┌─────────────────────────────┘
                    │
                    ▼
    ┌─────────────────────────────────────────────────┐
    │              Orchestrator (K8s)                   │
    │                                                  │
    │  Old Pod [image:v1] ──► Terminated               │
    │  New Pod [image:v2] ──► Running                  │
    │                                                  │
    │  NO: ssh, apt-get, config changes in-place       │
    └─────────────────────────────────────────────────┘
```

**Pros:**
- Reproducible deployments
- No configuration drift
- Easy rollback (use previous image)
- Security: no SSH, reduced attack surface

**Cons:**
- Longer build times
- Larger storage for images
- Debugging harder (can't SSH to inspect)
- Need good logging/observability

**Tools:** Docker, Packer, Kubernetes, Terraform, AWS AMI Builder

**When to use:**
- Always (this is the standard for modern microservices)
- Any containerized workload
- Compliance environments requiring auditability

---

### 8. GitOps (ArgoCD, Flux)

**What it is:** Use Git as the single source of truth for infrastructure and application state. Changes happen through PRs, reconciled by controllers.

**How it works:**
1. Desired state is declared in Git (manifests, Helm charts)
2. GitOps controller watches Git repository
3. Controller continuously reconciles cluster state with Git state
4. Drift is detected and corrected automatically
5. All changes are auditable (Git history)

**Architecture:**
```
    ┌──────────┐  PR/Merge   ┌──────────────┐
    │Developer  │────────────►│  Git Repo     │
    └──────────┘             │  (manifests)  │
                              └───────┬──────┘
                                      │ Watch
                                      ▼
                              ┌──────────────┐
                              │  GitOps       │
                              │  Controller   │
                              │  (ArgoCD/Flux)│
                              └───────┬──────┘
                                      │ Reconcile
                                      ▼
                              ┌──────────────┐
                              │  Kubernetes   │
                              │  Cluster      │
                              │  (Actual      │
                              │   State)      │
                              └──────────────┘

    Git State == Desired State == Actual State
```

**Steps to implement:**
1. Store all manifests in Git (app repo or config repo)
2. Install ArgoCD/Flux in cluster
3. Configure ArgoCD Application pointing to Git repo
4. Set sync policy (auto/manual)
5. Changes: update Git → controller syncs → cluster updates
6. Monitor sync status and health

**Pros:**
- Full audit trail (Git history)
- Declarative: easy to understand desired state
- Self-healing (drift correction)
- Developer-friendly (PR workflow)
- Multi-cluster management

**Cons:**
- Secrets management is challenging (need sealed-secrets/SOPS)
- Learning curve for teams
- Git repo structure decisions
- Debugging sync failures

**Tools:** ArgoCD, Flux, Rancher Fleet, Jenkins X

**When to use:**
- Kubernetes-based deployments
- Multi-environment management
- Teams wanting auditability and compliance
- When you want declarative infrastructure

---

## Container Patterns

### 1. Sidecar Pattern

**What it is:** Attach a helper container alongside the main application container in the same pod. They share network and storage.

**How it works:**
- Main container handles business logic
- Sidecar handles cross-cutting concerns
- Both share localhost network and volumes
- Sidecar lifecycle tied to main container

**Architecture:**
```
    ┌─────────────────────────────────────────┐
    │                 Pod                       │
    │                                          │
    │  ┌──────────────┐  ┌──────────────────┐ │
    │  │  Main App     │  │  Sidecar          │ │
    │  │  Container    │  │  Container        │ │
    │  │               │  │                   │ │
    │  │  Business     │  │  - Envoy Proxy    │ │
    │  │  Logic        │  │  - Log Collector  │ │
    │  │               │  │  - Auth Proxy     │ │
    │  │  :8080        │  │  - Cert Rotator   │ │
    │  └───────┬───────┘  └────────┬──────────┘ │
    │          │  localhost         │            │
    │          └───────────────────┘            │
    │          │                                │
    │    ┌─────┴─────┐                          │
    │    │  Shared    │                          │
    │    │  Volume    │                          │
    │    └───────────┘                          │
    └─────────────────────────────────────────┘
```

**Common sidecars:**
- **Logging:** Fluentd/Filebeat collecting logs from shared volume
- **Proxy:** Envoy/Istio proxy for mTLS, routing, observability
- **Security:** OAuth2 proxy, cert-manager
- **Monitoring:** Prometheus exporter

**Pros:**
- Separation of concerns
- Independent deployment/update of sidecar
- Language-agnostic (sidecar can be different language)
- Reusable across services

**Cons:**
- Increased resource consumption
- Complexity in debugging
- Pod startup ordering issues
- Shared failure domain

**Tools:** Istio (Envoy sidecar), Dapr, Linkerd, Fluentd

**When to use:**
- Service mesh implementations
- Cross-cutting concerns (logging, auth, metrics)
- When you need to add capabilities without modifying app code

---

### 2. Ambassador Pattern

**What it is:** A proxy container that handles communication with external services on behalf of the main container.

**Architecture:**
```
    ┌─────────────────────────────────────────┐
    │                 Pod                       │
    │                                          │
    │  ┌──────────────┐  ┌──────────────────┐ │
    │  │  Main App     │  │  Ambassador       │ │
    │  │               │  │  Container        │ │
    │  │  Calls        │  │                   │ │
    │  │  localhost:    │  │  - Connection     │ │
    │  │  9000 ────────┼──┼──► Pooling        │ │
    │  │               │  │  - Retries        │ │
    │  │               │  │  - Circuit Break  │ │
    │  └──────────────┘  │  - Auth Token      │ │
    │                     └────────┬───────────┘ │
    └──────────────────────────────┼───────────┘
                                   │
                                   ▼
                          ┌──────────────┐
                          │  External     │
                          │  Service      │
                          │  (Database,   │
                          │   3rd Party)  │
                          └──────────────┘
```

**Use cases:**
- Database connection pooling (PgBouncer as ambassador)
- External API authentication (token refresh)
- Protocol translation (REST to gRPC)
- Rate limiting outbound calls

**Pros:**
- App doesn't need client library complexity
- Centralized external communication logic
- Easy to swap external service clients

**Cons:**
- Additional latency (extra hop)
- Resource overhead
- Debugging complexity

---

### 3. Adapter Pattern

**What it is:** A container that transforms the output/interface of the main container to match what external systems expect.

**Architecture:**
```
    ┌─────────────────────────────────────────┐
    │                 Pod                       │
    │                                          │
    │  ┌──────────────┐  ┌──────────────────┐ │
    │  │  Main App     │  │  Adapter          │ │
    │  │               │  │  Container        │ │
    │  │  Logs in      │  │                   │ │
    │  │  custom ──────┼──┼──► Converts to    │ │
    │  │  format       │  │    standard       │ │
    │  │               │  │    format         │ │
    │  │  Metrics in   │  │                   │ │
    │  │  app format ──┼──┼──► Prometheus     │ │
    │  │               │  │    /metrics       │ │
    │  └──────────────┘  └──────────────────┘ │
    └─────────────────────────────────────────┘
```

**Use cases:**
- Converting proprietary log formats to standard (JSON/ELF)
- Exposing app metrics in Prometheus format
- Protocol adaptation for legacy services
- Normalizing health check endpoints

---

### 4. Init Container Pattern

**What it is:** Containers that run to completion before the main container starts. Used for initialization tasks.

**Architecture:**
```
    Pod Startup Sequence:
    
    ┌──────────┐   ┌──────────┐   ┌──────────────┐
    │ Init 1    │──►│ Init 2    │──►│ Main + Sidecar│
    │           │   │           │   │              │
    │ Wait for  │   │ Download  │   │ Application  │
    │ DB ready  │   │ config    │   │ starts       │
    │           │   │ from vault│   │              │
    └──────────┘   └──────────┘   └──────────────┘
     (completes)    (completes)    (runs forever)
```

**Use cases:**
- Wait for dependencies (database, message queue)
- Download configuration/secrets
- Run database migrations
- Set file permissions on shared volumes
- Register service in service discovery

**Pros:**
- Clean separation of initialization from runtime
- Fail fast if prerequisites not met
- Can use different images/tools for init

---

### 5. Multi-container Pod Patterns Summary

```
┌─────────────────────────────────────────────────────────────┐
│  Pattern     │  Relationship        │  Example              │
├─────────────────────────────────────────────────────────────┤
│  Sidecar     │  Extends main app    │  Envoy, log shipper   │
│  Ambassador  │  Proxies outbound    │  PgBouncer, OAuth     │
│  Adapter     │  Normalizes output   │  Prometheus exporter  │
│  Init        │  Runs before main    │  DB migration, config │
└─────────────────────────────────────────────────────────────┘
```

---

## Orchestration & Infrastructure

### Kubernetes Deployment Strategies

#### Deployment (ReplicaSet)
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: order-service
spec:
  replicas: 3
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0
  selector:
    matchLabels:
      app: order-service
  template:
    spec:
      containers:
      - name: order-service
        image: order-service:v2.1
        resources:
          requests:
            cpu: "250m"
            memory: "256Mi"
          limits:
            cpu: "500m"
            memory: "512Mi"
        readinessProbe:
          httpGet:
            path: /health/ready
            port: 8080
          initialDelaySeconds: 10
          periodSeconds: 5
        livenessProbe:
          httpGet:
            path: /health/live
            port: 8080
          initialDelaySeconds: 30
          periodSeconds: 10
```

#### StatefulSet
- For stateful services (databases, caches, message queues)
- Stable network identity (pod-0, pod-1, pod-2)
- Ordered deployment and scaling
- Persistent volume per pod

#### DaemonSet
- One pod per node (log collectors, node monitoring, CNI plugins)
- Automatically added to new nodes

#### Job / CronJob
- One-time tasks (database migration, batch processing)
- Scheduled recurring tasks (reports, cleanup)

---

### Helm Charts for Microservices

```
microservice-chart/
├── Chart.yaml
├── values.yaml              # Default values
├── values-dev.yaml          # Dev overrides
├── values-prod.yaml         # Prod overrides
└── templates/
    ├── deployment.yaml
    ├── service.yaml
    ├── ingress.yaml
    ├── hpa.yaml
    ├── configmap.yaml
    ├── secret.yaml
    └── serviceaccount.yaml
```

**Strategy:** Create a shared base chart, each service provides `values.yaml` overrides.

---

### Kustomize Overlays

```
base/
├── deployment.yaml
├── service.yaml
└── kustomization.yaml

overlays/
├── dev/
│   ├── kustomization.yaml    # patches for dev
│   └── replica-patch.yaml
├── staging/
│   ├── kustomization.yaml
│   └── resource-patch.yaml
└── prod/
    ├── kustomization.yaml
    ├── replica-patch.yaml
    └── hpa.yaml
```

---

### Namespace Strategies

| Strategy | Structure | Use Case |
|----------|-----------|----------|
| Per-environment | `dev`, `staging`, `prod` | Simple, small teams |
| Per-team | `team-payments`, `team-catalog` | Organizational boundaries |
| Per-service | `order-service`, `user-service` | Strong isolation |
| Hybrid | `prod-payments`, `dev-payments` | Large organizations |

---

### Resource Quotas and Limits

```yaml
apiVersion: v1
kind: ResourceQuota
metadata:
  name: team-payments-quota
  namespace: team-payments
spec:
  hard:
    requests.cpu: "20"
    requests.memory: "40Gi"
    limits.cpu: "40"
    limits.memory: "80Gi"
    pods: "50"
    services: "20"
---
apiVersion: v1
kind: LimitRange
metadata:
  name: default-limits
spec:
  limits:
  - default:
      cpu: "500m"
      memory: "512Mi"
    defaultRequest:
      cpu: "250m"
      memory: "256Mi"
    type: Container
```

---

### Horizontal Pod Autoscaler (HPA)

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: order-service-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: order-service
  minReplicas: 3
  maxReplicas: 50
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
  - type: Pods
    pods:
      metric:
        name: http_requests_per_second
      target:
        type: AverageValue
        averageValue: "1000"
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 60
      policies:
      - type: Percent
        value: 100
        periodSeconds: 60
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
      - type: Percent
        value: 10
        periodSeconds: 60
```

---

### Vertical Pod Autoscaler (VPA)

```yaml
apiVersion: autoscaling.k8s.io/v1
kind: VerticalPodAutoscaler
metadata:
  name: order-service-vpa
spec:
  targetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: order-service
  updatePolicy:
    updateMode: "Auto"  # Off, Initial, Auto
  resourcePolicy:
    containerPolicies:
    - containerName: order-service
      minAllowed:
        cpu: "100m"
        memory: "128Mi"
      maxAllowed:
        cpu: "2"
        memory: "4Gi"
```

**Note:** Don't use HPA and VPA on the same metric (e.g., both on CPU). Use VPA for memory, HPA for CPU/custom metrics.

---

### KEDA (Event-Driven Autoscaling)

```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: order-processor
spec:
  scaleTargetRef:
    name: order-processor
  minReplicaCount: 0    # Scale to zero!
  maxReplicaCount: 100
  triggers:
  - type: kafka
    metadata:
      bootstrapServers: kafka:9092
      consumerGroup: order-group
      topic: orders
      lagThreshold: "50"
  - type: prometheus
    metadata:
      serverAddress: http://prometheus:9090
      metricName: http_requests_total
      threshold: "100"
      query: sum(rate(http_requests_total{service="orders"}[2m]))
```

**KEDA vs HPA:**
- KEDA can scale to zero (HPA minimum is 1)
- KEDA supports event sources (Kafka, RabbitMQ, Azure Queue, etc.)
- KEDA builds on top of HPA

---

### Cluster Autoscaler

```
    ┌─────────────────────────────────────────┐
    │         Cluster Autoscaler               │
    │                                          │
    │  Watches: Pending pods (unschedulable)   │
    │  Action:  Add nodes to node group        │
    │                                          │
    │  Watches: Underutilized nodes            │
    │  Action:  Remove nodes (drain first)     │
    │                                          │
    └─────────────────────────────────────────┘
    
    Flow:
    HPA scales pods → Pods pending (no capacity) →
    Cluster Autoscaler adds nodes → Pods scheduled
```

---

## CI/CD Patterns

### Pipeline per Service

```
    ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
    │ order-svc    │     │ user-svc     │     │ payment-svc  │
    │ pipeline     │     │ pipeline     │     │ pipeline     │
    ├─────────────┤     ├─────────────┤     ├─────────────┤
    │ Build        │     │ Build        │     │ Build        │
    │ Unit Test    │     │ Unit Test    │     │ Unit Test    │
    │ Integration  │     │ Integration  │     │ Integration  │
    │ Contract Test│     │ Contract Test│     │ Contract Test│
    │ Image Build  │     │ Image Build  │     │ Image Build  │
    │ Deploy Dev   │     │ Deploy Dev   │     │ Deploy Dev   │
    │ Deploy Stg   │     │ Deploy Stg   │     │ Deploy Stg   │
    │ Deploy Prod  │     │ Deploy Prod  │     │ Deploy Prod  │
    └─────────────┘     └─────────────┘     └─────────────┘
```

Each service has independent pipeline, triggered by changes to its code path.

---

### Mono-repo vs Multi-repo

| Aspect | Mono-repo | Multi-repo |
|--------|-----------|------------|
| Code sharing | Easy (shared libraries) | Need package registry |
| Atomic changes | Cross-service PRs | Multiple PRs |
| Build | Need smart build (affected only) | Simple per-repo builds |
| Ownership | Harder to enforce | Clear boundaries |
| Tooling | Nx, Bazel, Turborepo | Standard Git |
| CI | Complex (path-based triggers) | Simple per-repo |
| Examples | Google, Meta | Netflix, Amazon |

---

### Trunk-Based Development

```
main ─────●────●────●────●────●────●────── (always deployable)
           \       \       \
            ● feat  ● fix   ● feat
            (short-lived, < 1 day)
            
Rules:
- Feature branches live < 1 day
- Feature flags hide incomplete work
- All commits pass CI
- Deploy from main multiple times/day
```

---

### Contract Testing in CI/CD

```
    Consumer (Order Service)        Provider (Inventory Service)
    ┌─────────────────────┐        ┌─────────────────────┐
    │ 1. Write consumer   │        │ 3. Verify provider  │
    │    contract test     │        │    against contracts│
    │                      │        │                     │
    │ 2. Publish contract  │───────►│ 4. Both pass = safe │
    │    to Pact Broker    │        │    to deploy        │
    └─────────────────────┘        └─────────────────────┘
                    │
                    ▼
            ┌──────────────┐
            │  Pact Broker  │
            │  (Contract    │
            │   Repository) │
            └──────────────┘
```

**Tools:** Pact, Spring Cloud Contract

---

### Progressive Delivery (Flagger, Argo Rollouts)

```yaml
# Argo Rollouts - Canary with Analysis
apiVersion: argoproj.io/v1alpha1
kind: Rollout
metadata:
  name: order-service
spec:
  replicas: 10
  strategy:
    canary:
      steps:
      - setWeight: 5
      - pause: {duration: 5m}
      - analysis:
          templates:
          - templateName: success-rate
      - setWeight: 25
      - pause: {duration: 5m}
      - analysis:
          templates:
          - templateName: success-rate
      - setWeight: 50
      - pause: {duration: 10m}
      - setWeight: 100
      canaryService: order-service-canary
      stableService: order-service-stable
      trafficRouting:
        istio:
          virtualService:
            name: order-service-vsvc
```

---

### Environment Promotion Strategies

```
    ┌─────┐     ┌─────────┐     ┌──────────┐     ┌──────┐
    │ Dev  │────►│ Staging  │────►│ Pre-Prod  │────►│ Prod  │
    └─────┘     └─────────┘     └──────────┘     └──────┘
      │              │                │               │
    Auto           Auto           Manual +         Canary +
    deploy        deploy          Approval         Analysis
      │              │                │               │
    Unit +        Integration     Performance      Progressive
    Contract      + E2E           + Security        rollout
    tests         tests           tests
```

---

### Infrastructure as Code

| Tool | Language | State | Cloud |
|------|----------|-------|-------|
| Terraform | HCL | Remote (S3, etc.) | Multi-cloud |
| Pulumi | TypeScript/Python/Go | Pulumi Cloud | Multi-cloud |
| AWS CDK | TypeScript/Python | CloudFormation | AWS |
| Crossplane | YAML (K8s CRDs) | Kubernetes | Multi-cloud |

---

## Release Management

### Semantic Versioning

```
MAJOR.MINOR.PATCH
  │     │     │
  │     │     └── Bug fixes (backward compatible)
  │     └──────── New features (backward compatible)
  └────────────── Breaking changes

Examples:
  1.0.0 → 1.0.1  (bug fix)
  1.0.1 → 1.1.0  (new feature, no breaking change)
  1.1.0 → 2.0.0  (breaking API change)

For microservices:
  - Service image tag: order-service:2.3.1
  - API version: /api/v2/orders
  - Contract version: order-contract:1.5.0
```

---

### Database Migration in CI/CD

```
    ┌────────────────────────────────────────────────────┐
    │  Deployment Pipeline                                │
    │                                                     │
    │  1. Run backward-compatible migration               │
    │     (ADD column, CREATE table - never DROP)         │
    │                                                     │
    │  2. Deploy new application version                  │
    │     (uses new + old schema)                         │
    │                                                     │
    │  3. Verify application health                       │
    │                                                     │
    │  4. Run cleanup migration (next deploy cycle)       │
    │     (DROP old columns after all services updated)   │
    └────────────────────────────────────────────────────┘

    Expand-Contract Pattern:
    
    Step 1 (Expand):  ADD new_column
    Step 2 (Migrate): Backfill new_column from old_column
    Step 3 (Deploy):  App writes to both, reads from new
    Step 4 (Contract): DROP old_column (next release)
```

**Tools:** Flyway, Liquibase, golang-migrate, Alembic

---

### Zero-Downtime Deployment Checklist

1. **Readiness probes** configured (don't receive traffic until ready)
2. **Graceful shutdown** (handle SIGTERM, drain connections)
3. **Pre-stop hook** (wait for LB to deregister)
4. **Backward-compatible API changes**
5. **Database migrations are additive only**
6. **Connection draining** on load balancer
7. **Rolling update with maxUnavailable: 0**
8. **Health check grace period** sufficient for startup

```yaml
spec:
  containers:
  - name: app
    lifecycle:
      preStop:
        exec:
          command: ["sh", "-c", "sleep 15"]  # Wait for LB deregister
    terminationGracePeriodSeconds: 60
```

---

### Rollback Strategies

| Strategy | Speed | Complexity | Data Impact |
|----------|-------|-----------|-------------|
| Kubernetes rollout undo | Fast (seconds) | Low | None |
| GitOps revert commit | Fast (1-2 min) | Low | None |
| Blue-Green switch back | Instant | Medium | None |
| Feature flag disable | Instant | Low | None |
| Database rollback | Slow | HIGH | Risk of data loss |

**Best practice:** Make deployments forward-only. Fix forward with a new deployment rather than rolling back (especially for database changes).

---

### Feature Flag Lifecycle Management

```
    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
    │  Create   │───►│  Ramp Up  │───►│ Full On   │───►│  Remove   │
    │  (OFF)    │    │  (5-100%) │    │  (100%)   │    │  (Cleanup)│
    └──────────┘    └──────────┘    └──────────┘    └──────────┘
    
    Rules:
    - Max flag age: 30 days (release toggles)
    - Ops toggles: permanent (but reviewed quarterly)
    - Experiment toggles: removed after decision
    - Track flag debt in backlog
    - CI check: fail if flag older than threshold
```

---

## Summary: Choosing a Deployment Strategy

| Scenario | Recommended Strategy |
|----------|---------------------|
| Default / simple services | Rolling Deployment |
| Critical services, instant rollback needed | Blue-Green |
| High-traffic, gradual validation | Canary |
| Product experiments | A/B Testing |
| Major refactoring validation | Shadow/Dark |
| Decouple deploy from release | Feature Flags |
| Kubernetes-native GitOps | ArgoCD + Argo Rollouts |
| Event-driven scale-to-zero | KEDA |
