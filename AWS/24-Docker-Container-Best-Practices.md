# Docker & Container Best Practices - Complete Guide

---

## 1. Docker Fundamentals

### Container vs VM
| | Container | Virtual Machine |
|--|---|---|
| Isolation | Process-level (shared kernel) | Hardware-level (own kernel) |
| Startup | Seconds | Minutes |
| Size | MBs (10-500 MB typical) | GBs (1-20 GB typical) |
| Density | 100s per host | 10s per host |
| Overhead | Near-zero | Hypervisor + full OS |
| Security | Namespace isolation (weaker) | Full isolation (stronger) |
| Portability | Image = runs anywhere with Docker | Image = runs anywhere with hypervisor |

### Docker Architecture
```
Docker Client (CLI) → Docker Daemon (dockerd) → Container Runtime (containerd → runc)
                                              → Image Registry (ECR, Docker Hub)
                                              → Storage Driver (overlay2)
                                              → Network Driver (bridge, host, overlay)
```

### Image Layers
```
FROM node:18-alpine          ← Base layer (read-only)
WORKDIR /app                 ← Metadata layer
COPY package*.json ./        ← Layer 3
RUN npm ci --production      ← Layer 4 (largest, cached if package.json unchanged)
COPY . .                     ← Layer 5 (changes every build)
CMD ["node", "server.js"]    ← Metadata (entrypoint)

Each instruction = new layer. Layers are cached and shared between images.
Order matters: Frequently changing content LAST (to maximize cache hits).
```

---

## 2. Dockerfile Best Practices

### Multi-Stage Builds
```dockerfile
# Stage 1: Build
FROM node:18 AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

# Stage 2: Production (minimal image)
FROM node:18-alpine AS production
WORKDIR /app
COPY --from=builder /app/dist ./dist
COPY --from=builder /app/node_modules ./node_modules
COPY package*.json ./
USER node
EXPOSE 3000
CMD ["node", "dist/server.js"]
```
- **Build stage:** Has all dev dependencies, build tools (1+ GB)
- **Production stage:** Only runtime artifacts (50-200 MB)
- **Result:** 10× smaller image, fewer vulnerabilities, faster deployment

### Image Size Optimization
| Technique | Impact | How |
|-----------|--------|-----|
| Alpine base | 5 MB vs 100 MB | `node:18-alpine` vs `node:18` |
| Multi-stage | 50-90% smaller | Separate build from runtime |
| .dockerignore | Reduce context size | Exclude node_modules, .git, tests |
| Minimize layers | Reduce overhead | Combine RUN commands with && |
| Copy only needed files | Reduce image size | Don't COPY entire repo |
| Distroless | Ultra-minimal | Google distroless (no shell, no package manager) |
| Slim variants | 60-80% smaller | `python:3.11-slim` vs `python:3.11` |

### .dockerignore
```
node_modules
.git
.gitignore
*.md
docker-compose*.yml
.env*
tests/
coverage/
.nyc_output
dist/
```

### Layer Caching Best Practices
```dockerfile
# BAD: Cache busted every time code changes
COPY . .
RUN npm ci

# GOOD: Dependencies cached unless package.json changes
COPY package*.json ./
RUN npm ci --production
COPY . .
```

### Security in Dockerfile
```dockerfile
# 1. Don't run as root
RUN addgroup -S appgroup && adduser -S appuser -G appgroup
USER appuser

# 2. Use specific version tags (not :latest)
FROM node:18.19.0-alpine3.19

# 3. Don't store secrets in image
# BAD: ENV API_KEY=secret123
# GOOD: Pass at runtime via secrets management

# 4. Use COPY not ADD (ADD can untar and fetch URLs - unexpected behavior)
COPY ./app /app

# 5. Health check
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
  CMD curl -f http://localhost:3000/health || exit 1

# 6. Read-only filesystem
# Set at runtime: docker run --read-only

# 7. No unnecessary packages
RUN apk add --no-cache curl && \
    rm -rf /var/cache/apk/*
```

---

## 3. Container Security

### Image Security Scanning
| Tool | Type | Integration |
|------|------|-------------|
| Amazon ECR scanning | Basic (Clair) + Enhanced (Inspector) | ECR native, scan on push |
| Trivy | Open source, comprehensive | CI/CD, admission controller |
| Snyk Container | CVE + license | GitHub, CI/CD |
| Docker Scout | Docker Desktop integrated | CI/CD, Docker Hub |
| Grype | Open source (Anchore) | CI/CD |

### ECR Image Scanning
```yaml
# Enable in ECR repository
Scan on push: Enabled
Scan type: Enhanced (Inspector - OS + application packages)

# CI/CD integration
- name: Scan Image
  run: |
    aws ecr start-image-scan --repository-name my-app --image-id imageTag=latest
    aws ecr wait image-scan-complete --repository-name my-app --image-id imageTag=latest
    FINDINGS=$(aws ecr describe-image-scan-findings --repository-name my-app --image-id imageTag=latest)
    # Fail pipeline if CRITICAL or HIGH findings
```

### Runtime Security
| Practice | How | Why |
|----------|-----|-----|
| Non-root user | `USER 1000` in Dockerfile | Limit damage if container compromised |
| Read-only rootfs | `readOnlyRootFilesystem: true` | Prevent malware writing to container |
| Drop capabilities | `drop: ALL`, add only needed | Remove unnecessary Linux capabilities |
| No privilege escalation | `allowPrivilegeEscalation: false` | Prevent gaining more permissions |
| Resource limits | CPU/Memory limits | Prevent noisy neighbor, DoS |
| Network policies | Kubernetes NetworkPolicy | Zero-trust between pods |
| Seccomp profiles | Restrict syscalls | Block dangerous system calls |

### Kubernetes Pod Security
```yaml
apiVersion: v1
kind: Pod
spec:
  securityContext:
    runAsNonRoot: true
    runAsUser: 1000
    runAsGroup: 3000
    fsGroup: 2000
    seccompProfile:
      type: RuntimeDefault
  containers:
  - name: app
    securityContext:
      allowPrivilegeEscalation: false
      readOnlyRootFilesystem: true
      capabilities:
        drop: ["ALL"]
    resources:
      limits:
        cpu: "500m"
        memory: "512Mi"
      requests:
        cpu: "250m"
        memory: "256Mi"
```

### Supply Chain Security
| Concern | Solution |
|---------|----------|
| Tampered base images | Use verified/official images, pin digests (not tags) |
| Vulnerable dependencies | Scan images, automated patching (Dependabot, Renovate) |
| Unsigned images | Docker Content Trust, cosign (Sigstore) |
| Untrusted registries | ECR with IAM, private registries only |
| Build reproducibility | Deterministic builds, pinned versions, lock files |

```dockerfile
# Pin by digest (immutable, can't be overwritten)
FROM node@sha256:abcdef1234567890...

# Or at minimum, pin to specific version
FROM node:18.19.0-alpine3.19
```

---

## 4. Container Registry (ECR) Best Practices

### ECR Configuration
```yaml
Repository:
  Image scanning: Enhanced (Inspector)
  Scan on push: Enabled
  Encryption: KMS CMK (customer managed)
  Image tag mutability: IMMUTABLE (prevent tag overwriting)
  
Lifecycle Policy:
  - Rule 1: Expire untagged images after 1 day
  - Rule 2: Keep only last 10 tagged images
  - Rule 3: Expire images older than 90 days (except 'latest' and release tags)
```

### ECR Lifecycle Policy
```json
{
  "rules": [
    {
      "rulePriority": 1,
      "description": "Remove untagged images",
      "selection": {
        "tagStatus": "untagged",
        "countType": "sinceImagePushed",
        "countUnit": "days",
        "countNumber": 1
      },
      "action": { "type": "expire" }
    },
    {
      "rulePriority": 2,
      "description": "Keep last 20 production images",
      "selection": {
        "tagStatus": "tagged",
        "tagPatternList": ["v*"],
        "countType": "imageCountMoreThan",
        "countNumber": 20
      },
      "action": { "type": "expire" }
    }
  ]
}
```

### ECR Cross-Region & Cross-Account
- **Replication:** Automatic replication to other regions/accounts
- **Pull-through cache:** Cache public registry images (Docker Hub) in your ECR
- **Use case:** Multi-region deployment (image near compute), DR readiness
- **Cross-account pull:** ECR resource policy allows other accounts to pull

---

## 5. Container Orchestration Patterns

### Health Checks (Kubernetes)
```yaml
livenessProbe:      # Is the container alive? (restart if fails)
  httpGet:
    path: /healthz
    port: 8080
  initialDelaySeconds: 15
  periodSeconds: 10
  failureThreshold: 3

readinessProbe:     # Can the container serve traffic? (remove from LB if fails)
  httpGet:
    path: /ready
    port: 8080
  initialDelaySeconds: 5
  periodSeconds: 5
  failureThreshold: 3

startupProbe:       # Is the container finished starting? (don't check liveness until startup passes)
  httpGet:
    path: /healthz
    port: 8080
  failureThreshold: 30
  periodSeconds: 10
  # Allows up to 5 minutes for slow-starting containers
```

### Graceful Shutdown
```javascript
// Node.js graceful shutdown
process.on('SIGTERM', async () => {
  console.log('SIGTERM received, starting graceful shutdown');
  
  // 1. Stop accepting new connections
  server.close();
  
  // 2. Complete in-flight requests (drain)
  await drainConnections(30000); // 30 second timeout
  
  // 3. Close database connections
  await db.close();
  
  // 4. Exit
  process.exit(0);
});
```
```yaml
# Kubernetes: Give container time to drain
spec:
  terminationGracePeriodSeconds: 60  # Must be > app drain time
  containers:
  - lifecycle:
      preStop:
        exec:
          command: ["sh", "-c", "sleep 10"]  # Wait for LB to deregister
```

### Sidecar Pattern
```yaml
# Common sidecars
spec:
  containers:
  - name: app                  # Main application
    image: my-app:v1
  - name: envoy               # Service mesh proxy (mTLS, observability)
    image: envoyproxy/envoy
  - name: log-shipper         # Ship logs to central system
    image: fluent-bit
  - name: secrets-agent       # Sync secrets from vault
    image: vault-agent
```

### Init Containers
```yaml
# Run before app container starts (sequential, must succeed)
spec:
  initContainers:
  - name: wait-for-db
    image: busybox
    command: ['sh', '-c', 'until nc -z db-service 5432; do sleep 2; done']
  - name: migrate-db
    image: my-app:v1
    command: ['node', 'migrate.js']
  containers:
  - name: app
    image: my-app:v1
```

---

## 6. Container Networking

### Docker Networking Modes
| Mode | Description | Use Case |
|------|-------------|----------|
| bridge (default) | Isolated network, NAT to host | Standard container communication |
| host | Share host network namespace | Performance (no NAT), bind to host ports |
| overlay | Multi-host networking (Swarm) | Multi-host clusters |
| none | No networking | Security-sensitive isolated workloads |
| awsvpc (ECS) | Each task gets own ENI/IP | AWS ECS/Fargate networking |

### Kubernetes Networking
```
Pod-to-Pod: Flat network (every pod can reach every pod, no NAT)
Pod-to-Service: kube-proxy (iptables/IPVS) load balancing
Pod-to-External: NAT through node
External-to-Pod: Service (LoadBalancer/NodePort) or Ingress

CNI plugins (AWS): VPC CNI (each pod gets VPC IP from subnet)
  Benefit: Pods are native VPC citizens (security groups, flow logs work)
  Limitation: IP address exhaustion (prefix delegation helps)
```

---

## 7. Container Observability

### Logging Best Practices
| Practice | Details |
|----------|---------|
| Log to stdout/stderr | Container runtime captures and routes logs |
| Structured logging (JSON) | Machine-parseable, queryable |
| Correlation IDs | Trace requests across services |
| Log levels | ERROR/WARN/INFO in prod, DEBUG only for troubleshooting |
| Don't log secrets | Sanitize sensitive data before logging |
| Centralize | Ship to CloudWatch Logs, OpenSearch, Datadog |

```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "level": "ERROR",
  "service": "order-service",
  "traceId": "abc-123-def",
  "message": "Payment processing failed",
  "error": "timeout after 5000ms",
  "orderId": "ORD-456",
  "customerId": "CUST-789"
}
```

### Container Metrics
```
Key metrics to collect:
  Container: CPU %, memory %, network I/O, disk I/O, restart count
  Application: Request rate, error rate, latency (P50/P90/P99)
  Business: Orders/sec, active users, queue depth

Tools:
  AWS: CloudWatch Container Insights (ECS/EKS)
  Open source: Prometheus + Grafana
  APM: X-Ray, Datadog, New Relic
  
EKS monitoring stack:
  Prometheus (metrics collection) → 
  Grafana (visualization) → 
  AlertManager (alerting) →
  Thanos/Cortex (long-term storage)
```

---

## 8. CI/CD for Containers

### Build Pipeline
```yaml
# GitHub Actions - Container CI/CD
name: Container Pipeline
on:
  push:
    branches: [main]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4
    
    - name: Set up Docker Buildx
      uses: docker/setup-buildx-action@v3
    
    - name: Build and test
      run: |
        docker build --target test -t my-app:test .
        docker run my-app:test npm test
    
    - name: Security scan
      uses: aquasecurity/trivy-action@master
      with:
        image-ref: my-app:test
        severity: CRITICAL,HIGH
        exit-code: 1  # Fail pipeline on critical/high CVEs
    
    - name: Build production image
      run: |
        docker build --target production \
          -t $ECR_REGISTRY/my-app:${{ github.sha }} \
          -t $ECR_REGISTRY/my-app:latest .
    
    - name: Push to ECR
      run: |
        aws ecr get-login-password | docker login --username AWS --password-stdin $ECR_REGISTRY
        docker push $ECR_REGISTRY/my-app:${{ github.sha }}
    
    - name: Deploy to ECS
      run: |
        aws ecs update-service --cluster prod --service my-app \
          --force-new-deployment
```

### Image Tagging Strategy
| Strategy | Tag Format | Use Case |
|----------|-----------|----------|
| Git SHA | `abc123def` | Immutable, traceable to exact commit |
| Semantic version | `v1.2.3` | Release versioning |
| Branch + SHA | `main-abc123` | Branch identification |
| Timestamp | `20240115-103000` | Build ordering |
| **Best:** | `v1.2.3` + `abc123def` | Both tags on same image |

### Build Optimization
```dockerfile
# Cache dependencies in BuildKit cache mount
FROM node:18-alpine
WORKDIR /app
RUN --mount=type=cache,target=/root/.npm \
    npm ci --production

# Or use BuildKit inline cache for CI
# docker build --cache-from registry/my-app:cache --build-arg BUILDKIT_INLINE_CACHE=1
```

---

## 9. Container Anti-Patterns

### Common Mistakes
| Anti-Pattern | Problem | Fix |
|-------------|---------|-----|
| Running as root | Full host access if container escapes | `USER non-root` |
| Using :latest tag | Non-deterministic deployments | Pin to specific version/SHA |
| Storing secrets in image | Exposed in layer history | Runtime injection (Secrets Manager) |
| Bloated images (1+ GB) | Slow deploys, more attack surface | Multi-stage, Alpine, distroless |
| One container = multiple processes | Coupling, hard to scale/monitor | One process per container |
| No resource limits | Noisy neighbor, OOM kills | Set CPU/memory requests + limits |
| No health checks | Dead containers keep receiving traffic | Add liveness/readiness probes |
| Logging to files | Logs lost when container dies | Log to stdout/stderr |
| SSH into containers | Security risk, breaks immutability | Use `kubectl exec` or ECS exec for debugging |
| Manual image updates | Missed security patches | Automated pipeline + Dependabot |

---

## 10. Scenario-Based Interview Questions

### Q1: Container image is 2.5GB and deployments take 10+ minutes. Optimize.
**Answer:**
```
Analysis: Why so large?
  - Likely: Full OS base (ubuntu vs alpine), dev dependencies included,
    build tools in production image, .git directory, test files

Optimization plan:
  1. Multi-stage build (biggest win):
     Stage 1: Full build env (node:18 + all dev deps)
     Stage 2: Minimal runtime (node:18-alpine + production deps only)
     Expected: 2.5GB → 200-400MB
     
  2. .dockerignore:
     Exclude: node_modules, .git, tests, docs, coverage
     
  3. Alpine or distroless base:
     node:18 (1.1GB) → node:18-alpine (180MB) → distroless (50MB)
     
  4. Minimize layer count:
     Combine RUN commands: RUN apt-get update && apt-get install -y ... && rm -rf /var/lib/apt/lists/*
     
  5. npm ci --production (don't install devDependencies)
  
  6. Tree-shaking: Only copy dist/ folder to production stage
  
  7. Layer caching: Package.json copied BEFORE source code
  
  Result: 2.5GB → 150-250MB
  Deploy time: 10+ min → 1-2 min (less to pull, faster startup)
```

### Q2: Design container security strategy for regulated environment (PCI-DSS)
**Answer:**
```
Build phase:
  - Base images: Approved hardened base only (maintained by platform team)
  - Vulnerability scanning: Trivy in pipeline (block on CRITICAL/HIGH)
  - Image signing: cosign + verify at admission
  - SBOMs: Generate with syft, store for audit
  - No secrets in build (use build-time secrets only: --secret flag)
  - Immutable tags: ECR immutable tag setting
  
Registry:
  - Private ECR only (no public Docker Hub pulls in production)
  - Pull-through cache for approved public images
  - Lifecycle policies (remove old images, reduce attack surface)
  - Cross-account: Only production account can pull production images
  
Runtime:
  - Pod Security Standards: "restricted" profile (K8s built-in)
  - OPA/Gatekeeper policies:
    - Must run as non-root
    - Must have resource limits
    - No privileged containers
    - No host namespace sharing
    - Must use approved registries only
  - Falco: Runtime threat detection (unexpected shells, network connections)
  - Read-only rootfs + specific volume mounts for write needs
  
Network:
  - Network Policies: Default deny all, explicit allow per service
  - Service mesh (mTLS): Encrypt all pod-to-pod traffic
  - No direct internet access from pods (egress through proxy/NAT)
  
Monitoring:
  - CloudTrail: ECR API calls (who pushed/pulled what)
  - GuardDuty EKS: Runtime threat detection
  - Container Insights: Resource usage, restarts, OOM kills
  - Audit logs: K8s API server audit log (all kubectl actions)
```

### Q3: Zero-downtime deployment for stateful container application
**Answer:**
```
Challenge: Stateful app (WebSocket connections, in-memory cache)

Strategy: Blue-Green with connection draining

  1. Deploy new version (Green) alongside old (Blue)
  2. Green passes health checks and startup probe
  3. New connections route to Green (update ALB target group)
  4. Existing connections drain from Blue:
     - terminationGracePeriodSeconds: 300 (5 min drain)
     - preStop hook: Signal app to stop accepting new connections
     - App: Complete in-flight requests, close WebSocket gracefully
  5. After drain timeout: Blue terminated
  
  For WebSocket reconnection:
    - Client SDK: Auto-reconnect on connection close
    - Session state: Store in Redis/DynamoDB (not in-memory)
    - Reconnect: Client reconnects → hits Green → loads session from Redis
    
  For cache warming:
    - Startup probe: Wait until cache populated (read from Redis/source)
    - OR: Lazy cache population (accept slight latency increase on first requests)
    
  ECS configuration:
    deploymentConfiguration:
      minimumHealthyPercent: 100  # Keep all old tasks until new are healthy
      maximumPercent: 200         # Temporarily double capacity
    healthCheckGracePeriodSeconds: 120  # Time for cache warming
    
  EKS configuration:
    strategy:
      type: RollingUpdate
      rollingUpdate:
        maxSurge: 1         # Add 1 new pod at a time
        maxUnavailable: 0   # Never reduce below desired
```

### Q4: Multi-architecture container builds (ARM + x86) for cost optimization
**Answer:**
```
Why: Graviton (ARM) instances are 20% cheaper with same/better performance

Strategy: Build multi-arch images, deploy to Graviton

  Dockerfile (no changes needed if dependencies support ARM):
    FROM --platform=$TARGETPLATFORM node:18-alpine
    ...
    
  Build (GitHub Actions with BuildKit):
    - name: Build multi-arch
      uses: docker/build-push-action@v5
      with:
        platforms: linux/amd64,linux/arm64
        push: true
        tags: ${{ env.ECR_REGISTRY }}/my-app:${{ github.sha }}
        cache-from: type=gha
        cache-to: type=gha,mode=max
  
  ECR: Single tag contains manifest list (both architectures)
  
  ECS/EKS:
    - Graviton task: Runs arm64 image automatically (runtime selects correct arch)
    - Mix: Some services on Graviton (stateless), some on x86 (legacy dependencies)
    
  Considerations:
    - Native dependencies: Some npm/pip packages need ARM compilation
    - Build time: Multi-arch builds take 2× (building for two platforms)
    - Testing: Test on both architectures in CI
    - Gradual migration: Start with stateless services, validate performance
    
  Cost savings:
    - ECS Fargate: 20% cheaper for ARM (0.04048 vs 0.05056 per vCPU/hr)
    - EC2 Graviton3: ~20-40% better price/performance vs comparable x86
```

### Q5: Container observability stack for 500-microservice platform
**Answer:**
```
Architecture:

  Metrics:
    Each pod → Prometheus (scrape /metrics endpoint)
    Prometheus → Thanos (long-term storage in S3, global query)
    Grafana → Dashboards (per-service, golden signals, infrastructure)
    AlertManager → PagerDuty/Slack (based on SLO burn rate)
    
    OR AWS-native:
    Container Insights + CloudWatch → Dashboards + Alarms
    
  Logging:
    Containers → stdout/stderr → Fluent Bit (DaemonSet)
    Fluent Bit → CloudWatch Logs (short-term) → OpenSearch (search/analysis)
    Fluent Bit → S3 (long-term archive, Parquet format)
    
    Key: Structured JSON logs with trace-id, service-name, level
    
  Tracing:
    OpenTelemetry SDK in each service (auto-instrumentation)
    OTEL Collector (DaemonSet) → X-Ray / Jaeger / Tempo
    Service map: Auto-generated from traces
    
  Alerting hierarchy:
    P1: Service SLO burn rate (error budget consuming too fast)
    P2: Individual service health (5XX rate, latency P99)
    P3: Infrastructure (CPU > 80%, memory > 85%, disk > 80%)
    P4: Informational (deployment completed, scaling event)
    
  Cost management (500 services = lots of data):
    - Log sampling: Only log 10% of INFO in high-traffic services
    - Metric cardinality: Limit label combinations (avoid explosion)
    - Trace sampling: 1% of successful requests, 100% of errors
    - Retention: Metrics 30 days hot (Prometheus), 1 year cold (Thanos/S3)
    - Logs: 14 days in OpenSearch, archive to S3 Glacier after
```

