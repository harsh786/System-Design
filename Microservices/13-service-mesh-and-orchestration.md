# Service Mesh and Container Orchestration

## Table of Contents
- [Service Mesh Fundamentals](#service-mesh-fundamentals)
- [Istio Deep Dive](#istio-deep-dive)
- [Linkerd](#linkerd)
- [Other Service Meshes](#other-service-meshes)
- [Kubernetes for Microservices](#kubernetes-for-microservices)
- [Container Runtime](#container-runtime)
- [Orchestration Patterns](#orchestration-patterns)
- [Service Discovery](#service-discovery)

---

## Service Mesh Fundamentals

### What is a Service Mesh?

A **service mesh** is a dedicated infrastructure layer for handling service-to-service communication in a microservices architecture. It provides observability, traffic management, and security without requiring changes to application code.

```
┌─────────────────────────────────────────────────────┐
│                   Control Plane                       │
│  (Configuration, Policy, Telemetry Aggregation)      │
└──────────────┬──────────────────────┬───────────────┘
               │                      │
    ┌──────────▼──────────┐  ┌───────▼───────────────┐
    │  Service A          │  │  Service B            │
    │  ┌───────────────┐  │  │  ┌───────────────┐   │
    │  │  Application  │  │  │  │  Application  │   │
    │  └───────┬───────┘  │  │  └───────┬───────┘   │
    │  ┌───────▼───────┐  │  │  ┌───────▼───────┐   │
    │  │ Sidecar Proxy │◄─┼──┼─►│ Sidecar Proxy │   │
    │  └───────────────┘  │  │  └───────────────┘   │
    └─────────────────────┘  └───────────────────────┘
              Data Plane (proxies handle all traffic)
```

### Why You Need a Service Mesh

| Challenge | How Service Mesh Solves It |
|-----------|--------------------------|
| Service-to-service security | Automatic mTLS encryption |
| Observability | Automatic metrics, traces, logs |
| Traffic control | Fine-grained routing, canary, A/B |
| Reliability | Retries, timeouts, circuit breaking |
| Policy enforcement | Authorization policies without app changes |
| Multi-language support | Language-agnostic (proxy handles everything) |

### Data Plane vs Control Plane

```
┌─────────────────────────────────────────────────┐
│              CONTROL PLANE                        │
│                                                   │
│  • Configuration management                      │
│  • Service discovery                             │
│  • Certificate authority (CA)                    │
│  • Policy distribution                           │
│  • Telemetry collection                          │
│                                                   │
│  Examples: Istiod, Linkerd control plane         │
└──────────────────────┬──────────────────────────┘
                       │ pushes config
                       ▼
┌─────────────────────────────────────────────────┐
│              DATA PLANE                           │
│                                                   │
│  • Proxy instances (sidecars)                    │
│  • Intercept all network traffic                 │
│  • Enforce policies                              │
│  • Collect telemetry                             │
│  • Handle retries, circuit breaking              │
│                                                   │
│  Examples: Envoy, linkerd2-proxy                 │
└─────────────────────────────────────────────────┘
```

### Sidecar Proxy Pattern (Envoy)

The sidecar proxy runs alongside each service instance, intercepting all inbound and outbound traffic.

```yaml
# Kubernetes pod with Envoy sidecar (injected by Istio)
apiVersion: v1
kind: Pod
metadata:
  name: my-service
  annotations:
    sidecar.istio.io/inject: "true"
spec:
  containers:
  - name: my-service
    image: my-service:v1
    ports:
    - containerPort: 8080
  # Envoy sidecar is automatically injected
  # - name: istio-proxy
  #   image: envoy
  #   (auto-injected by mutating webhook)
```

**Envoy Proxy Features:**
- L3/L4 filter architecture
- HTTP/2 and gRPC support
- Advanced load balancing (least request, ring hash, maglev)
- Automatic retries with exponential backoff
- Circuit breaking
- Rate limiting
- Health checking
- Observability (stats, logging, tracing)
- Hot restart with zero downtime

### Service Mesh vs API Gateway vs Load Balancer

| Feature | Service Mesh | API Gateway | Load Balancer |
|---------|-------------|-------------|---------------|
| **Scope** | East-West (service-to-service) | North-South (external to internal) | Traffic distribution |
| **Protocol** | Any (L4/L7) | HTTP/gRPC (L7) | L4 or L7 |
| **Security** | mTLS between services | Auth, rate limiting for external | Basic ACLs |
| **Observability** | Full mesh telemetry | API-level metrics | Connection metrics |
| **Deployment** | Sidecar per service | Centralized | Centralized |
| **Example** | Istio, Linkerd | Kong, API Gateway | HAProxy, NLB |

```
External Clients
       │
       ▼
┌─────────────┐
│ API Gateway │  ← North-South traffic (external)
└──────┬──────┘
       │
       ▼
┌─────────────────────────────────────┐
│         Service Mesh                 │
│                                      │
│  Service A ←→ Service B             │  ← East-West traffic (internal)
│       ↕            ↕                 │
│  Service C ←→ Service D             │
│                                      │
└─────────────────────────────────────┘
```

### When to Adopt a Service Mesh (and When NOT to)

**Adopt when:**
- 10+ microservices in production
- Multiple teams deploying independently
- Need consistent security policies across services
- Polyglot environment (multiple languages)
- Compliance requirements for encryption in transit
- Need sophisticated traffic management (canary, A/B)
- Debugging distributed system issues is painful

**Do NOT adopt when:**
- < 5 services (overhead not justified)
- Monolithic application
- Team lacks Kubernetes expertise
- Performance overhead is unacceptable (adds ~1-3ms latency per hop)
- Simple request-response patterns with no complex routing needs
- Resource-constrained environment (sidecars consume memory/CPU)

---

## Istio Deep Dive

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        ISTIOD                                 │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌───────────┐  │
│  │  Pilot   │  │  Citadel │  │  Galley  │  │  Mixer    │  │
│  │(traffic) │  │(security)│  │(config)  │  │(telemetry)│  │
│  └──────────┘  └──────────┘  └──────────┘  └───────────┘  │
└──────────────────────────┬──────────────────────────────────┘
                           │ xDS API
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                      DATA PLANE                              │
│                                                              │
│  ┌─────────┐    ┌─────────┐    ┌─────────┐                │
│  │ Pod A   │    │ Pod B   │    │ Pod C   │                │
│  │┌──────┐ │    │┌──────┐ │    │┌──────┐ │                │
│  ││ App  │ │    ││ App  │ │    ││ App  │ │                │
│  │└──┬───┘ │    │└──┬───┘ │    │└──┬───┘ │                │
│  │┌──▼───┐ │    │┌──▼───┐ │    │┌──▼───┐ │                │
│  ││Envoy │◄├────┤►│Envoy │◄├────┤►│Envoy │ │                │
│  │└──────┘ │    │└──────┘ │    │└──────┘ │                │
│  └─────────┘    └─────────┘    └─────────┘                │
└─────────────────────────────────────────────────────────────┘
```

### Traffic Management

#### VirtualService

Controls how requests are routed to a service.

```yaml
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: reviews
spec:
  hosts:
  - reviews
  http:
  # Route 80% to v1, 20% to v2 (canary)
  - route:
    - destination:
        host: reviews
        subset: v1
      weight: 80
    - destination:
        host: reviews
        subset: v2
      weight: 20
  # Header-based routing
  - match:
    - headers:
        end-user:
          exact: jason
    route:
    - destination:
        host: reviews
        subset: v3
  # Timeout and retries
  - route:
    - destination:
        host: reviews
        subset: v1
    timeout: 10s
    retries:
      attempts: 3
      perTryTimeout: 3s
      retryOn: 5xx,reset,connect-failure
```

#### DestinationRule

Defines policies applied after routing (load balancing, connection pool, outlier detection).

```yaml
apiVersion: networking.istio.io/v1beta1
kind: DestinationRule
metadata:
  name: reviews
spec:
  host: reviews
  trafficPolicy:
    connectionPool:
      tcp:
        maxConnections: 100
      http:
        h2UpgradePolicy: UPGRADE
        http1MaxPendingRequests: 100
        http2MaxRequests: 1000
    loadBalancer:
      simple: LEAST_REQUEST
    outlierDetection:
      consecutive5xxErrors: 5
      interval: 30s
      baseEjectionTime: 30s
      maxEjectionPercent: 50
  subsets:
  - name: v1
    labels:
      version: v1
  - name: v2
    labels:
      version: v2
  - name: v3
    labels:
      version: v3
```

#### Gateway

Entry point for external traffic into the mesh.

```yaml
apiVersion: networking.istio.io/v1beta1
kind: Gateway
metadata:
  name: my-gateway
spec:
  selector:
    istio: ingressgateway
  servers:
  - port:
      number: 443
      name: https
      protocol: HTTPS
    tls:
      mode: SIMPLE
      credentialName: my-tls-secret
    hosts:
    - "api.example.com"
  - port:
      number: 80
      name: http
      protocol: HTTP
    hosts:
    - "api.example.com"
    tls:
      httpsRedirect: true
```

### Security

#### Mutual TLS (mTLS)

```yaml
# Strict mTLS for entire mesh
apiVersion: security.istio.io/v1beta1
kind: PeerAuthentication
metadata:
  name: default
  namespace: istio-system
spec:
  mtls:
    mode: STRICT

# Permissive mode for migration
apiVersion: security.istio.io/v1beta1
kind: PeerAuthentication
metadata:
  name: default
  namespace: my-namespace
spec:
  mtls:
    mode: PERMISSIVE
```

#### AuthorizationPolicy

```yaml
# Allow only specific services to call payment service
apiVersion: security.istio.io/v1beta1
kind: AuthorizationPolicy
metadata:
  name: payment-policy
  namespace: default
spec:
  selector:
    matchLabels:
      app: payment
  action: ALLOW
  rules:
  - from:
    - source:
        principals: ["cluster.local/ns/default/sa/order-service"]
    to:
    - operation:
        methods: ["POST"]
        paths: ["/api/v1/charge"]

# Deny all by default
apiVersion: security.istio.io/v1beta1
kind: AuthorizationPolicy
metadata:
  name: deny-all
  namespace: default
spec:
  {}
```

### Observability

Istio automatically collects:

```
┌──────────────────────────────────────────────────┐
│              Automatic Telemetry                   │
│                                                    │
│  Metrics (Prometheus)                             │
│  • Request count, duration, size                  │
│  • TCP connections opened/closed                  │
│  • istio_requests_total                           │
│  • istio_request_duration_milliseconds            │
│                                                    │
│  Distributed Tracing (Jaeger/Zipkin)             │
│  • Span creation for each proxy hop              │
│  • Headers: x-request-id, x-b3-traceid          │
│                                                    │
│  Access Logs                                      │
│  • Full request/response metadata                │
│  • Configurable format                            │
└──────────────────────────────────────────────────┘
```

```yaml
# Enable access logging
apiVersion: telemetry.istio.io/v1alpha1
kind: Telemetry
metadata:
  name: mesh-default
  namespace: istio-system
spec:
  accessLogging:
  - providers:
    - name: envoy
```

### Fault Injection

```yaml
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: ratings
spec:
  hosts:
  - ratings
  http:
  - fault:
      delay:
        percentage:
          value: 10
        fixedDelay: 5s
      abort:
        percentage:
          value: 5
        httpStatus: 500
    route:
    - destination:
        host: ratings
```

### Traffic Mirroring

```yaml
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: reviews
spec:
  hosts:
  - reviews
  http:
  - route:
    - destination:
        host: reviews
        subset: v1
    mirror:
      host: reviews
      subset: v2
    mirrorPercentage:
      value: 100.0
```

### Circuit Breaking Configuration

```yaml
apiVersion: networking.istio.io/v1beta1
kind: DestinationRule
metadata:
  name: reviews-cb
spec:
  host: reviews
  trafficPolicy:
    connectionPool:
      tcp:
        maxConnections: 100
      http:
        http1MaxPendingRequests: 1
        http2MaxRequests: 50
        maxRequestsPerConnection: 10
    outlierDetection:
      consecutive5xxErrors: 3
      interval: 10s
      baseEjectionTime: 30s
      maxEjectionPercent: 100
      minHealthPercent: 0
```

### Rate Limiting

```yaml
# Using EnvoyFilter for local rate limiting
apiVersion: networking.istio.io/v1alpha3
kind: EnvoyFilter
metadata:
  name: rate-limit
  namespace: istio-system
spec:
  workloadSelector:
    labels:
      app: my-service
  configPatches:
  - applyTo: HTTP_FILTER
    match:
      context: SIDECAR_INBOUND
      listener:
        filterChain:
          filter:
            name: envoy.filters.network.http_connection_manager
    patch:
      operation: INSERT_BEFORE
      value:
        name: envoy.filters.http.local_ratelimit
        typed_config:
          "@type": type.googleapis.com/udpa.type.v1.TypedStruct
          type_url: type.googleapis.com/envoy.extensions.filters.http.local_ratelimit.v3.LocalRateLimit
          value:
            stat_prefix: http_local_rate_limiter
            token_bucket:
              max_tokens: 100
              tokens_per_fill: 100
              fill_interval: 60s
```

### Multi-Cluster Mesh

```
┌──────────────────┐     ┌──────────────────┐
│   Cluster 1      │     │   Cluster 2      │
│  ┌────────────┐  │     │  ┌────────────┐  │
│  │   Istiod   │◄─┼─────┼─►│   Istiod   │  │
│  └────────────┘  │     │  └────────────┘  │
│                   │     │                   │
│  Service A ─────►├─────┤─► Service B      │
│  Service C       │     │   Service D      │
└──────────────────┘     └──────────────────┘
     East-West Gateway connects clusters
```

**Models:**
- **Primary-Remote**: Single control plane, multi-cluster data plane
- **Multi-Primary**: Each cluster has its own control plane
- **External Control Plane**: Control plane outside the mesh clusters

---

## Linkerd

### Architecture

```
┌─────────────────────────────────────────┐
│           Control Plane                   │
│  ┌────────────┐  ┌──────────────────┐   │
│  │ Destination│  │   Identity       │   │
│  │ (discovery)│  │ (certificate CA) │   │
│  └────────────┘  └──────────────────┘   │
│  ┌────────────┐  ┌──────────────────┐   │
│  │   Proxy    │  │     Policy       │   │
│  │  Injector  │  │   Controller     │   │
│  └────────────┘  └──────────────────┘   │
└─────────────────────────┬───────────────┘
                          │
                          ▼
┌─────────────────────────────────────────┐
│           Data Plane                     │
│   linkerd2-proxy (Rust, ultra-light)    │
│   ~10MB memory per sidecar              │
│   Sub-millisecond p99 latency added     │
└─────────────────────────────────────────┘
```

**Key differentiator**: Linkerd uses its own Rust-based proxy (`linkerd2-proxy`) instead of Envoy, resulting in significantly lower resource usage.

### Traffic Splitting

```yaml
apiVersion: split.smi-spec.io/v1alpha2
kind: TrafficSplit
metadata:
  name: backend-split
spec:
  service: backend
  backends:
  - service: backend-v1
    weight: 90
  - service: backend-v2
    weight: 10
```

### Service Profiles

```yaml
apiVersion: linkerd.io/v1alpha2
kind: ServiceProfile
metadata:
  name: orders.default.svc.cluster.local
spec:
  routes:
  - name: GET /orders/{id}
    condition:
      method: GET
      pathRegex: /orders/[^/]+
    responseClasses:
    - condition:
        status:
          min: 500
          max: 599
      isFailure: true
    timeout: 5s
    isRetryable: true
```

### Automatic mTLS

Linkerd enables mTLS by default for all meshed workloads with zero configuration:

```bash
# Inject Linkerd proxy
kubectl get deploy -o yaml | linkerd inject - | kubectl apply -f -

# Verify mTLS
linkerd viz edges pod -n default
# Shows all connections are secured with mTLS
```

### Linkerd vs Istio Comparison

| Feature | Linkerd | Istio |
|---------|---------|-------|
| **Proxy** | linkerd2-proxy (Rust) | Envoy (C++) |
| **Resource usage** | ~10MB per sidecar | ~50-100MB per sidecar |
| **Latency overhead** | <1ms p99 | 2-5ms p99 |
| **Complexity** | Simple, opinionated | Complex, highly configurable |
| **Learning curve** | Low | High |
| **Traffic management** | Basic (traffic split) | Advanced (VirtualService, etc.) |
| **Multi-cluster** | Supported | Advanced support |
| **Extensibility** | Limited | Highly extensible (EnvoyFilter) |
| **CNCF status** | Graduated | Graduated |
| **Best for** | Simplicity-first teams | Complex enterprise requirements |

---

## Other Service Meshes

### Consul Connect (HashiCorp)

```
┌────────────────────────────────────────────┐
│         Consul Connect                      │
│                                             │
│  • Built into HashiCorp Consul             │
│  • Supports both sidecar and native        │
│  • Intentions-based authorization          │
│  • Multi-datacenter by design              │
│  • Works with VMs AND Kubernetes           │
│  • Uses Envoy as sidecar proxy             │
└────────────────────────────────────────────┘
```

```hcl
# Service definition with Connect
service {
  name = "web"
  port = 8080
  connect {
    sidecar_service {}
  }
}

# Intention: allow web -> api
Kind      = "service-intentions"
Name      = "api"
Sources = [
  {
    Name   = "web"
    Action = "allow"
  }
]
```

**Best for**: Organizations already using HashiCorp stack, hybrid VM + K8s environments.

### AWS App Mesh

```
┌────────────────────────────────────────────┐
│         AWS App Mesh                        │
│                                             │
│  • Managed service mesh by AWS             │
│  • Uses Envoy as data plane                │
│  • Integrates with ECS, EKS, EC2          │
│  • Virtual nodes, virtual services         │
│  • Cloud Map integration for discovery     │
│  • No control plane to manage             │
└────────────────────────────────────────────┘
```

**Best for**: AWS-native workloads, teams wanting managed mesh without operational overhead.

### Cilium Service Mesh (eBPF-based)

```
┌────────────────────────────────────────────┐
│       Cilium Service Mesh                   │
│                                             │
│  • NO sidecar proxies needed!              │
│  • Uses eBPF in the Linux kernel           │
│  • Significantly lower latency             │
│  • Lower resource consumption              │
│  • Kernel-level traffic management         │
│  • L3/L4 policies without proxy            │
│  • L7 with optional Envoy (per-node)       │
│  • Network policy + mesh in one            │
└────────────────────────────────────────────┘
```

```yaml
# Cilium L7 policy
apiVersion: cilium.io/v2
kind: CiliumNetworkPolicy
metadata:
  name: rule1
spec:
  endpointSelector:
    matchLabels:
      app: myService
  ingress:
  - fromEndpoints:
    - matchLabels:
        app: frontend
    toPorts:
    - ports:
      - port: "80"
        protocol: TCP
      rules:
        http:
        - method: "GET"
          path: "/api/.*"
```

**Best for**: Performance-sensitive workloads, teams wanting to avoid sidecar overhead.

### Kuma (CNCF)

- Built by Kong, donated to CNCF
- Universal (Kubernetes + VMs)
- Uses Envoy as data plane
- Multi-zone / multi-mesh support
- Simple UI and CLI

### Open Service Mesh (OSM)

- Archived by CNCF (not actively maintained)
- Lightweight, SMI-compliant
- Conceptually relevant for understanding SMI spec
- Teams should choose Linkerd or Istio instead

---

## Kubernetes for Microservices

### Pod Design Patterns

```
┌─────────────────────────────────────────────────────────────┐
│ SIDECAR PATTERN                                              │
│                                                              │
│  ┌─────────────────────────────────────────┐                │
│  │ Pod                                      │                │
│  │  ┌──────────┐    ┌──────────────────┐   │                │
│  │  │ Main App │    │ Sidecar (logging,│   │                │
│  │  │          │◄──►│ proxy, sync)     │   │                │
│  │  └──────────┘    └──────────────────┘   │                │
│  └─────────────────────────────────────────┘                │
│  Use: Log shipping, service mesh proxy, config sync         │
├─────────────────────────────────────────────────────────────┤
│ AMBASSADOR PATTERN                                           │
│                                                              │
│  ┌─────────────────────────────────────────┐                │
│  │ Pod                                      │                │
│  │  ┌──────────┐    ┌───────────────┐      │                │
│  │  │ Main App │───►│ Ambassador    │──────┼──► External   │
│  │  │          │    │ (proxy out)   │      │     Service   │
│  │  └──────────┘    └───────────────┘      │                │
│  └─────────────────────────────────────────┘                │
│  Use: Connecting to external DBs, legacy services           │
├─────────────────────────────────────────────────────────────┤
│ ADAPTER PATTERN                                              │
│                                                              │
│  ┌─────────────────────────────────────────┐                │
│  │ Pod                                      │                │
│  │  ┌──────────┐    ┌───────────────┐      │                │
│  │  │ Main App │───►│ Adapter       │──────┼──► Monitoring │
│  │  │(custom   │    │(transforms to │      │    System     │
│  │  │ format)  │    │ standard fmt) │      │                │
│  │  └──────────┘    └───────────────┘      │                │
│  └─────────────────────────────────────────┘                │
│  Use: Prometheus exporters, log format adapters             │
├─────────────────────────────────────────────────────────────┤
│ INIT CONTAINER PATTERN                                       │
│                                                              │
│  ┌─────────────────────────────────────────┐                │
│  │ Pod                                      │                │
│  │  ┌──────────┐    ┌──────────┐           │                │
│  │  │  Init 1  │───►│  Init 2  │───► Main  │                │
│  │  │(DB migr) │    │(wait dep)│    App     │                │
│  │  └──────────┘    └──────────┘           │                │
│  └─────────────────────────────────────────┘                │
│  Use: DB migrations, dependency waiting, config setup       │
└─────────────────────────────────────────────────────────────┘
```

### Service Types

```yaml
# ClusterIP - internal only (default)
apiVersion: v1
kind: Service
metadata:
  name: my-service
spec:
  type: ClusterIP
  selector:
    app: my-app
  ports:
  - port: 80
    targetPort: 8080

---
# NodePort - exposed on each node's IP
apiVersion: v1
kind: Service
metadata:
  name: my-service
spec:
  type: NodePort
  selector:
    app: my-app
  ports:
  - port: 80
    targetPort: 8080
    nodePort: 30080  # 30000-32767

---
# LoadBalancer - cloud provider LB
apiVersion: v1
kind: Service
metadata:
  name: my-service
  annotations:
    service.beta.kubernetes.io/aws-load-balancer-type: nlb
spec:
  type: LoadBalancer
  selector:
    app: my-app
  ports:
  - port: 443
    targetPort: 8080

---
# ExternalName - CNAME alias to external service
apiVersion: v1
kind: Service
metadata:
  name: external-db
spec:
  type: ExternalName
  externalName: db.example.com
```

### Ingress Controllers

| Controller | Best For | Key Features |
|-----------|----------|-------------|
| **Nginx Ingress** | General purpose | Wide adoption, extensive annotations |
| **Traefik** | Auto-discovery | Automatic Let's Encrypt, middleware |
| **Contour** | Envoy-based ingress | HTTPProxy CRD, delegation |
| **AWS ALB Ingress** | AWS environments | Native ALB integration |
| **Istio Gateway** | Service mesh environments | Full Istio integration |

```yaml
# Nginx Ingress example
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: my-ingress
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
    nginx.ingress.kubernetes.io/rate-limit: "100"
spec:
  ingressClassName: nginx
  tls:
  - hosts:
    - api.example.com
    secretName: tls-secret
  rules:
  - host: api.example.com
    http:
      paths:
      - path: /api/v1
        pathType: Prefix
        backend:
          service:
            name: api-service
            port:
              number: 80
```

### ConfigMaps and Secrets Management

```yaml
# ConfigMap
apiVersion: v1
kind: ConfigMap
metadata:
  name: app-config
data:
  database.host: "postgres.default.svc.cluster.local"
  database.port: "5432"
  application.yml: |
    server:
      port: 8080
    spring:
      profiles:
        active: production

---
# Secret (base64 encoded)
apiVersion: v1
kind: Secret
metadata:
  name: db-credentials
type: Opaque
data:
  username: YWRtaW4=
  password: cGFzc3dvcmQ=

---
# External Secrets Operator (preferred for production)
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: db-credentials
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: aws-secrets-manager
    kind: ClusterSecretStore
  target:
    name: db-credentials
  data:
  - secretKey: password
    remoteRef:
      key: /prod/db/password
```

### StatefulSets

```yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: kafka
spec:
  serviceName: kafka-headless
  replicas: 3
  selector:
    matchLabels:
      app: kafka
  template:
    metadata:
      labels:
        app: kafka
    spec:
      containers:
      - name: kafka
        image: confluentinc/cp-kafka:7.5.0
        ports:
        - containerPort: 9092
        volumeMounts:
        - name: data
          mountPath: /var/lib/kafka
  volumeClaimTemplates:
  - metadata:
      name: data
    spec:
      accessModes: ["ReadWriteOnce"]
      storageClassName: gp3
      resources:
        requests:
          storage: 100Gi
```

### Operators and CRDs

```yaml
# Custom Resource Definition
apiVersion: apiextensions.k8s.io/v1
kind: CustomResourceDefinition
metadata:
  name: databases.example.com
spec:
  group: example.com
  versions:
  - name: v1
    served: true
    storage: true
    schema:
      openAPIV3Schema:
        type: object
        properties:
          spec:
            type: object
            properties:
              engine:
                type: string
                enum: ["postgres", "mysql"]
              version:
                type: string
              replicas:
                type: integer
  scope: Namespaced
  names:
    plural: databases
    singular: database
    kind: Database

---
# Using the CRD
apiVersion: example.com/v1
kind: Database
metadata:
  name: orders-db
spec:
  engine: postgres
  version: "15"
  replicas: 3
```

### Pod Disruption Budgets

```yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: api-pdb
spec:
  minAvailable: 2  # or maxUnavailable: 1
  selector:
    matchLabels:
      app: api-server
```

### Affinity, Taints, and Tolerations

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: web-server
spec:
  template:
    spec:
      affinity:
        # Spread across AZs
        podAntiAffinity:
          requiredDuringSchedulingIgnoredDuringExecution:
          - labelSelector:
              matchExpressions:
              - key: app
                operator: In
                values: ["web-server"]
            topologyKey: topology.kubernetes.io/zone
        # Prefer nodes with SSD
        nodeAffinity:
          preferredDuringSchedulingIgnoredDuringExecution:
          - weight: 1
            preference:
              matchExpressions:
              - key: disk-type
                operator: In
                values: ["ssd"]
      tolerations:
      - key: "dedicated"
        operator: "Equal"
        value: "high-memory"
        effect: "NoSchedule"
      containers:
      - name: web
        resources:
          requests:
            cpu: "500m"
            memory: "512Mi"
          limits:
            cpu: "1000m"
            memory: "1Gi"
```

### Namespace Strategies

| Strategy | Description | Use Case |
|----------|-------------|----------|
| Per-team | `team-payments`, `team-orders` | Team autonomy |
| Per-environment | `dev`, `staging`, `prod` | Environment isolation |
| Per-domain | `checkout`, `inventory`, `shipping` | Domain-driven |
| Hybrid | `team-payments-prod`, `team-payments-dev` | Large organizations |

```yaml
# Resource quotas per namespace
apiVersion: v1
kind: ResourceQuota
metadata:
  name: team-quota
  namespace: team-payments
spec:
  hard:
    requests.cpu: "20"
    requests.memory: 40Gi
    limits.cpu: "40"
    limits.memory: 80Gi
    pods: "50"
    services: "20"
```

---

## Container Runtime

### Docker to containerd Migration

```
Docker (deprecated in K8s 1.24+)
┌──────────────────────────────────┐
│ kubelet → dockershim → docker    │
│                      → containerd│
│                      → runc      │
└──────────────────────────────────┘

containerd (direct)
┌──────────────────────────────────┐
│ kubelet → CRI → containerd      │
│                → runc            │
└──────────────────────────────────┘
```

**Key points:**
- Docker images still work (OCI compliant)
- `docker build` still works for building images
- Only the runtime changed at the node level
- containerd is lighter and more performant

### Container Security Best Practices

```yaml
apiVersion: v1
kind: Pod
spec:
  securityContext:
    runAsNonRoot: true
    runAsUser: 1000
    fsGroup: 2000
    seccompProfile:
      type: RuntimeDefault
  containers:
  - name: app
    image: myapp:v1@sha256:abc123...  # Pin by digest
    securityContext:
      allowPrivilegeEscalation: false
      readOnlyRootFilesystem: true
      capabilities:
        drop: ["ALL"]
    resources:
      limits:
        cpu: "1"
        memory: "512Mi"
```

### Image Optimization

```dockerfile
# Multi-stage build
FROM golang:1.21 AS builder
WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -o /server

# Distroless final image
FROM gcr.io/distroless/static-debian12
COPY --from=builder /server /server
USER nonroot:nonroot
ENTRYPOINT ["/server"]
# Result: ~10MB image vs ~800MB with golang base
```

### Container Registries

| Registry | Type | Best For |
|----------|------|----------|
| **Harbor** | Self-hosted, CNCF | Enterprise, on-prem, vulnerability scanning |
| **ECR** | AWS managed | AWS workloads |
| **GCR/Artifact Registry** | GCP managed | GCP workloads |
| **ACR** | Azure managed | Azure workloads |
| **Docker Hub** | Public/private | Open source, public images |
| **GitHub Container Registry** | GitHub integrated | GitHub-based workflows |

### Image Signing and Verification

```bash
# Sign with Cosign
cosign sign --key cosign.key myregistry.io/myimage:v1

# Verify
cosign verify --key cosign.pub myregistry.io/myimage:v1

# Kubernetes admission policy (Kyverno)
```

```yaml
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: verify-images
spec:
  validationFailureAction: enforce
  rules:
  - name: verify-signature
    match:
      resources:
        kinds: ["Pod"]
    verifyImages:
    - imageReferences: ["myregistry.io/*"]
      attestors:
      - entries:
        - keys:
            publicKeys: |-
              -----BEGIN PUBLIC KEY-----
              ...
              -----END PUBLIC KEY-----
```

---

## Orchestration Patterns

### Choreography vs Orchestration

```
CHOREOGRAPHY (event-driven, decentralized)
┌─────────┐  OrderCreated  ┌─────────┐  PaymentDone  ┌─────────┐
│  Order  │───────────────►│ Payment │───────────────►│Shipping │
│ Service │                │ Service │                │ Service │
└─────────┘                └─────────┘                └─────────┘
     │                          │                          │
     └──────────────────────────┴──────────────────────────┘
                    Event Bus (Kafka)

ORCHESTRATION (centralized coordinator)
                    ┌──────────────┐
                    │ Orchestrator │
                    │  (Temporal)  │
                    └──────┬───────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
        ┌─────────┐  ┌─────────┐  ┌─────────┐
        │  Order  │  │ Payment │  │Shipping │
        │ Service │  │ Service │  │ Service │
        └─────────┘  └─────────┘  └─────────┘
```

| Aspect | Choreography | Orchestration |
|--------|-------------|---------------|
| Coupling | Loose | Tighter to orchestrator |
| Visibility | Harder to trace | Clear workflow view |
| Error handling | Complex (compensating events) | Centralized |
| Scalability | Better | Orchestrator can be bottleneck |
| Best for | Simple flows, high autonomy | Complex workflows, sagas |

### Workflow Engines Comparison

| Engine | Language | Hosting | Best For |
|--------|----------|---------|----------|
| **Temporal** | Any (Go, Java, TS, Python) | Self-hosted / Cloud | Complex workflows, long-running |
| **Cadence** | Any | Self-hosted | Uber's predecessor to Temporal |
| **AWS Step Functions** | JSON/YAML state machine | Managed | AWS-native, simple workflows |
| **Airflow** | Python | Self-hosted / managed | Data pipelines, DAGs |
| **Argo Workflows** | YAML | Kubernetes | CI/CD, K8s-native |

### Temporal Deep Dive

```
┌──────────────────────────────────────────────────────────┐
│                   Temporal Architecture                    │
│                                                           │
│  ┌────────────┐     ┌─────────────────┐                 │
│  │   Client   │────►│  Temporal Server │                 │
│  └────────────┘     │  ┌───────────┐  │                 │
│                      │  │  History  │  │                 │
│  ┌────────────┐     │  │  Service  │  │                 │
│  │   Worker   │◄────│  ├───────────┤  │                 │
│  │(Workflows) │     │  │  Matching │  │                 │
│  └────────────┘     │  │  Service  │  │                 │
│                      │  ├───────────┤  │                 │
│  ┌────────────┐     │  │  Frontend │  │                 │
│  │   Worker   │◄────│  │  Service  │  │                 │
│  │(Activities)│     │  └───────────┘  │                 │
│  └────────────┘     └─────────────────┘                 │
└──────────────────────────────────────────────────────────┘
```

```go
// Temporal Workflow (Go)
func OrderWorkflow(ctx workflow.Context, order Order) error {
    // Activity options with retry
    ao := workflow.ActivityOptions{
        StartToCloseTimeout: 10 * time.Minute,
        RetryPolicy: &temporal.RetryPolicy{
            InitialInterval: time.Second,
            MaximumAttempts: 5,
        },
    }
    ctx = workflow.WithActivityOptions(ctx, ao)

    // Step 1: Reserve inventory
    err := workflow.ExecuteActivity(ctx, ReserveInventory, order).Get(ctx, nil)
    if err != nil {
        return err
    }

    // Step 2: Process payment
    var paymentResult PaymentResult
    err = workflow.ExecuteActivity(ctx, ProcessPayment, order).Get(ctx, &paymentResult)
    if err != nil {
        // Compensate: release inventory
        _ = workflow.ExecuteActivity(ctx, ReleaseInventory, order).Get(ctx, nil)
        return err
    }

    // Step 3: Ship order
    err = workflow.ExecuteActivity(ctx, ShipOrder, order).Get(ctx, nil)
    if err != nil {
        // Compensate: refund payment, release inventory
        _ = workflow.ExecuteActivity(ctx, RefundPayment, paymentResult).Get(ctx, nil)
        _ = workflow.ExecuteActivity(ctx, ReleaseInventory, order).Get(ctx, nil)
        return err
    }

    return nil
}

// Signals - external events into workflow
func OrderWorkflowWithSignal(ctx workflow.Context, order Order) error {
    // Wait for approval signal
    var approved bool
    signalChan := workflow.GetSignalChannel(ctx, "approval")
    signalChan.Receive(ctx, &approved)

    if !approved {
        return errors.New("order rejected")
    }
    // continue...
    return nil
}

// Queries - read workflow state without affecting it
func init() {
    workflow.RegisterQueryHandler(ctx, "getStatus", func() (string, error) {
        return currentStatus, nil
    })
}
```

### Saga Orchestration with Temporal

```
┌─────────────────────────────────────────────────────┐
│            Saga Pattern with Temporal                 │
│                                                      │
│  Forward Actions:        Compensations:             │
│  1. Reserve Inventory    1. Release Inventory       │
│  2. Charge Payment       2. Refund Payment          │
│  3. Book Shipping        3. Cancel Shipping         │
│  4. Send Confirmation    4. Send Cancellation       │
│                                                      │
│  If step 3 fails:                                   │
│  Execute compensations in reverse: 2, 1             │
└─────────────────────────────────────────────────────┘
```

### Long-Running Process Management

Temporal handles:
- **Durable execution**: Survives process crashes, server restarts
- **Infinite retries with backoff**: Never lose progress
- **Timers**: Sleep for days/weeks without consuming resources
- **Heartbeats**: Detect activity worker failures
- **Versioning**: Safely update workflow logic for running workflows
- **Visibility**: Query and search running workflows

---

## Service Discovery

### Client-Side Discovery

```
┌────────────┐     1. Register    ┌──────────────────┐
│ Service A  │───────────────────►│ Service Registry │
│ Instance 1 │                    │   (Eureka)       │
└────────────┘                    └────────┬─────────┘
┌────────────┐     1. Register             │
│ Service A  │───────────────────►         │
│ Instance 2 │                             │
└────────────┘                             │
                                           │
┌────────────┐  2. Query registry          │
│   Client   │◄────────────────────────────┘
│            │  3. Load balance locally
│            │──────────────────────► Service A Instance 1
└────────────┘
```

**Netflix Eureka example (Spring Cloud):**
```yaml
eureka:
  client:
    serviceUrl:
      defaultZone: http://eureka:8761/eureka/
  instance:
    preferIpAddress: true
    leaseRenewalIntervalInSeconds: 10
```

### Server-Side Discovery

```
┌────────────┐                     ┌──────────────┐
│   Client   │────── request ─────►│ Load Balancer│
└────────────┘                     │ / API Gateway│
                                   └──────┬───────┘
                                          │ routes to healthy instance
                              ┌───────────┼───────────┐
                              ▼           ▼           ▼
                        Instance 1   Instance 2   Instance 3
```

### DNS-Based Discovery (Kubernetes)

```
┌──────────────────────────────────────────────────┐
│  Kubernetes DNS (CoreDNS)                         │
│                                                   │
│  Service: my-service.my-namespace.svc.cluster.local
│  Pod:     pod-ip.my-namespace.pod.cluster.local  │
│  Headless: pod-name.my-service.my-namespace.svc. │
│                                                   │
│  SRV records for port discovery                  │
└──────────────────────────────────────────────────┘
```

```yaml
# Headless service for StatefulSet discovery
apiVersion: v1
kind: Service
metadata:
  name: kafka-headless
spec:
  clusterIP: None  # Headless
  selector:
    app: kafka
  ports:
  - port: 9092
# DNS: kafka-0.kafka-headless.default.svc.cluster.local
```

### Consul Service Discovery

```
┌─────────────────────────────────────────────────────────┐
│                    Consul Cluster                         │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐                │
│  │ Server 1│  │ Server 2│  │ Server 3│  (Raft)        │
│  └─────────┘  └─────────┘  └─────────┘                │
└───────────────────────┬─────────────────────────────────┘
                        │
         ┌──────────────┼──────────────┐
         ▼              ▼              ▼
   ┌───────────┐  ┌───────────┐  ┌───────────┐
   │Consul Agent│  │Consul Agent│  │Consul Agent│
   │(on node 1)│  │(on node 2)│  │(on node 3)│
   └───────────┘  └───────────┘  └───────────┘
```

Features:
- Health checking (HTTP, TCP, script, TTL)
- DNS interface (`myservice.service.consul`)
- HTTP API for registration and queries
- Key/Value store for configuration
- Multi-datacenter support
- Prepared queries for failover

### Service Registry Patterns

| Pattern | Implementation | Pros | Cons |
|---------|---------------|------|------|
| Self-registration | Service registers itself | Simple | Coupling to registry |
| Third-party registration | Registrar watches and registers | Decoupled | Extra component |
| Platform-provided | K8s Services, ECS Service Discovery | Zero effort | Platform lock-in |

---

## Best Practices Summary

1. **Start simple**: Don't adopt a service mesh until you have enough services to justify it
2. **Incremental adoption**: Use permissive mTLS mode during migration
3. **Resource budgeting**: Account for sidecar overhead (CPU, memory, latency)
4. **GitOps for mesh config**: Version control all VirtualServices, DestinationRules
5. **Canary everything**: Use traffic splitting for safe rollouts
6. **Observability first**: Ensure metrics, traces, logs before complex routing
7. **Namespace isolation**: Use namespaces with RBAC for multi-team clusters
8. **Pod security**: Always run as non-root, read-only filesystem, drop capabilities
9. **Use operators**: Don't manually manage stateful workloads
10. **Plan for multi-cluster**: Design with cluster federation in mind
