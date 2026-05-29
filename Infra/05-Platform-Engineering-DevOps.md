# Platform Engineering & Advanced DevOps - Staff/Architect Level

> Internal Developer Platforms, GitOps at scale, Developer Experience, DevOps maturity.

---

## 1. Internal Developer Platform (IDP)

### What is a Platform?
- A curated set of tools, workflows, and services that enable developers to self-serve without needing to understand underlying infrastructure
- **Goal:** Reduce cognitive load. Developer focuses on code, platform handles infrastructure

### Platform Components
```
Developer Interface Layer:
  ├── Service Catalog (Backstage/Port) - "Create new service" wizard
  ├── CLI tools (scaffold, deploy, logs, debug)
  ├── Documentation (ADRs, runbooks, API docs)
  └── Dashboards (SLOs, costs, dependencies)

Orchestration Layer:
  ├── CI/CD (GitHub Actions reusable workflows)
  ├── GitOps (ArgoCD/Flux)
  ├── Infrastructure provisioning (Terraform modules, Crossplane)
  └── Secret management (External Secrets Operator)

Infrastructure Layer:
  ├── Kubernetes clusters (EKS)
  ├── Databases (RDS, DynamoDB)
  ├── Networking (VPC, service mesh)
  ├── Observability (Prometheus, Grafana, OpenTelemetry)
  └── Security (policies, scanning, certificates)
```

### Backstage (Spotify's IDP)
- **Software Catalog:** Registry of all services, owners, dependencies, documentation
- **Templates:** "Create new service" → scaffolds repo, CI/CD, K8s manifests, monitoring
- **TechDocs:** Documentation-as-code (markdown → searchable portal)
- **Plugins:** Kubernetes, ArgoCD, PagerDuty, Cost, Security (extensible)
- **Benefit:** Single pane of glass for entire engineering organization

### Platform as Product
- **Treat platform like a product:** Users = developers. Product discovery, user research, iteration
- **Metrics:**
  - Adoption rate: % teams using platform capabilities
  - Onboarding time: Time from "new service" to "first production deploy"
  - Self-service success rate: % tasks completed without asking platform team
  - Developer satisfaction (quarterly survey, NPS)
  - Cognitive load: Number of tools/steps required for common tasks

---

## 2. GitOps at Scale

### GitOps Principles
1. **Declarative:** Entire system described declaratively (YAML/HCL)
2. **Versioned:** Desired state stored in Git (source of truth)
3. **Automated:** Approved changes automatically applied to system
4. **Continuously reconciled:** Software agents ensure actual state matches desired state

### Multi-Cluster GitOps Architecture
```
Git Repository Structure:
├── clusters/
│   ├── prod-us-east/
│   │   ├── kustomization.yaml
│   │   └── patches/           (environment-specific overrides)
│   ├── prod-eu-west/
│   │   ├── kustomization.yaml
│   │   └── patches/
│   └── staging/
│       ├── kustomization.yaml
│       └── patches/
├── apps/
│   ├── user-service/
│   │   ├── base/              (common manifests)
│   │   └── overlays/          (per-env values)
│   ├── order-service/
│   └── payment-service/
└── infrastructure/
    ├── cert-manager/
    ├── external-secrets/
    └── monitoring/

ArgoCD Management:
  Hub cluster → ApplicationSet CRD
  → Generates Application per cluster per service
  → Each Application syncs specific path to specific cluster
```

### App of Apps Pattern
```yaml
# Root Application (manages all other apps)
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: root-app
spec:
  source:
    repoURL: https://github.com/org/gitops
    path: apps
  destination:
    server: https://kubernetes.default.svc
---
# ApplicationSet (generates apps dynamically)
apiVersion: argoproj.io/v1alpha1
kind: ApplicationSet
metadata:
  name: services
spec:
  generators:
    - git:
        repoURL: https://github.com/org/gitops
        directories:
          - path: apps/*
    - clusters: {}  # all registered clusters
  template:
    spec:
      source:
        repoURL: https://github.com/org/gitops
        path: '{{path}}/overlays/{{name}}'
      destination:
        server: '{{server}}'
        namespace: '{{path.basename}}'
```

### Image Update Automation
```
Developer pushes code → CI builds image → pushes to ECR (tag: sha-abc123)
  ↓
Image Reflector (Flux) or Argo CD Image Updater detects new tag
  ↓
Automatically commits updated image tag to GitOps repo
  ↓
ArgoCD syncs new image to cluster
  ↓
Canary/progressive rollout begins

Result: Developer merges PR → automatically deployed to prod (with safety gates)
```

---

## 3. Advanced CI/CD Patterns

### Trunk-Based Development at Scale
- **What:** Everyone commits to main (trunk). No long-lived feature branches
- **Feature flags:** Incomplete features hidden behind flags (merge incomplete code safely)
- **Short-lived branches:** 1-2 days max, small PRs (< 400 lines)
- **CI requirements:** Main must always be deployable. Tests pass on every commit
- **Release:** Tag main for release OR continuous deployment (every merge → prod)
- **Benefits:** Eliminates merge conflicts, faster feedback, simpler CI/CD
- **Scale challenge:** With 100+ engineers → need fast CI (< 10 min) and reliable tests

### Monorepo CI Optimization
```
Tools: Nx (JS), Turborepo (JS), Bazel (polyglot), Pants (Python)

Strategies:
1. Affected detection: Only build/test what changed
   nx affected --target=test --base=main~1

2. Remote caching: Share build artifacts across team
   If CI already built this code → reuse cached result

3. Distributed execution: Split large builds across machines
   Nx Cloud / Bazel Remote Execution

4. Path-based triggers: 
   services/user/** → test user-service only
   libs/shared/** → test ALL dependent services
```

### Pipeline Security (Supply Chain)
```
SLSA Level 3 Requirements:
  ✓ Source: Version controlled, verified identity of author
  ✓ Build: Hermetic (isolated, no network), scripted (no manual steps)
  ✓ Provenance: Non-falsifiable record of what was built, from what source, by what build system
  ✓ Dependencies: Pinned, scanned, verified integrity

Implementation:
  Commit → Signed (GPG/SSH) + verified in branch protection
  Build → GitHub Actions (hosted runner, no network in build step)
  Artifacts → Signed with Cosign/Sigstore (OIDC keyless)
  Deploy → Admission controller verifies signature before deploying
  SBOM → Generated per build, stored alongside artifact
```

### Deployment Verification
```yaml
# Post-deployment verification pipeline
post-deploy:
  steps:
    - smoke-tests:
        # Hit critical endpoints, verify 200 responses
        endpoints: [/health, /api/v1/users, /api/v1/orders]
        expected: 200
        timeout: 30s
    
    - synthetic-monitoring:
        # Run synthetic user journeys
        scenarios: [login, search, checkout]
        assertion: all_pass
    
    - metrics-check:
        # Compare metrics before/after deploy
        duration: 5m
        assertions:
          - error_rate < 0.5%
          - latency_p99 < previous + 20%
          - cpu_usage < 80%
    
    - canary-analysis:
        # Statistical comparison canary vs baseline
        metrics: [error_rate, latency_p50, latency_p99]
        threshold: 0.05  # 5% degradation = fail
        duration: 15m
    
    - rollback:
        if: any_check_fails
        action: revert_to_previous_version
        notify: [slack-channel, pagerduty]
```

---

## 4. Infrastructure Automation Patterns

### Crossplane (Kubernetes-native IaC)
- **What:** Manage cloud infrastructure using Kubernetes CRDs (Custom Resources)
- **Why:** Developers use `kubectl apply` for EVERYTHING (apps + infra). Single tool
- **Example:**
  ```yaml
  apiVersion: database.aws.crossplane.io/v1beta1
  kind: RDSInstance
  metadata:
    name: my-database
  spec:
    forProvider:
      region: us-east-1
      dbInstanceClass: db.t3.medium
      engine: postgres
      engineVersion: "14"
      masterUsername: admin
    writeConnectionSecretToRef:
      name: db-credentials
      namespace: my-app
  ```
- **Benefits:** GitOps for infrastructure, Kubernetes-native, composition (combine resources)
- **vs Terraform:** Crossplane = continuous reconciliation (like K8s controller). Terraform = run once per change

### GitOps for Infrastructure (Terraform)
```
PR workflow:
  1. Developer opens PR with Terraform changes
  2. CI runs: terraform fmt + validate + tflint + tfsec
  3. CI runs: terraform plan → posts plan as PR comment
  4. Reviewer reviews plan output + code
  5. Merge to main → terraform apply (automated)
  6. State locked during apply → prevents concurrent changes

Advanced:
  - Drift detection: Scheduled terraform plan → alert if drift detected
  - Policy as code: OPA/Sentinel validates plan before apply
  - Blast radius: Separate state files per component (VPC, EKS, Services)
  - Approval gates: Environment protection rules for production changes
```

### Self-Service Infrastructure
```
Developer self-service menu:
  1. "Create new PostgreSQL database"
     → Backstage template → creates Terraform PR → auto-approved (meets policies) → applied
  
  2. "Create new EKS namespace for my team"
     → Backstage template → creates K8s manifests (namespace, RBAC, quota, network policy) → ArgoCD syncs
  
  3. "I need a Redis cache"
     → Backstage form → generates Crossplane resource → K8s applies → Redis ready in 5 min
  
  4. "Create new microservice"
     → Backstage template → scaffolds: repo + Dockerfile + CI/CD + K8s manifests + monitoring + docs
     → Developer writes code → push → automatic deployment

Platform team enables all of this WITHOUT manual intervention
```

---

## 5. Kubernetes Platform Patterns

### Multi-Cluster Management
| Approach | Complexity | Use Case |
|----------|-----------|----------|
| Single cluster + namespaces | Low | Small org, same region |
| Cluster per environment | Medium | Strict env isolation |
| Cluster per team | Medium-High | Strong team autonomy, compliance |
| Cluster per region | Medium | Global availability |
| Federation (KubeFed) | High | True multi-cluster apps |

### Cluster Addons Management
```
Every EKS cluster needs (managed via GitOps):
  Core:
    - CoreDNS (DNS resolution)
    - kube-proxy (networking)
    - AWS VPC CNI (pod networking)
    - AWS EBS CSI Driver (storage)
  
  Networking:
    - AWS Load Balancer Controller (ALB/NLB)
    - ExternalDNS (Route 53 records)
    - cert-manager (TLS certificates)
    - Ingress controller (NGINX or ALB)
  
  Security:
    - External Secrets Operator (sync secrets from AWS)
    - Kyverno/OPA Gatekeeper (policy enforcement)
    - Falco (runtime security)
  
  Observability:
    - Prometheus + Grafana (metrics)
    - Fluent Bit (logging)
    - OpenTelemetry Collector (traces)
    - CloudWatch Container Insights
  
  Scaling:
    - Karpenter (node autoscaler)
    - metrics-server (HPA support)
    - KEDA (event-driven scaling)
  
  Cost:
    - Kubecost (cost visibility)
```

### Developer Experience on Kubernetes
- **Developers should NOT need to know K8s internals**
- **Abstractions:**
  - Helm chart per service type (web-service, worker, cronjob) → developers fill values.yaml
  - Or: CRD-based abstraction (KubeVela, Crossplane composition)
  - Backstage templates generate everything → developer just writes application code
- **Dev environments:**
  - Telepresence: Redirect cluster traffic to local machine (hybrid dev)
  - Tilt/Skaffold: File-watch → rebuild → redeploy (inner loop speed)
  - Preview environments: Per-PR namespace with full stack (expensive, worth it for complex apps)
- **Debugging:**
  - `kubectl debug` for ephemeral containers
  - Port-forward for local testing against remote services
  - ECS Exec / `kubectl exec` for interactive debugging
  - Distributed tracing for finding issues across services

---

## 6. DevOps Maturity Model

### DORA Metrics (Engineering Excellence)
| Metric | Elite | High | Medium | Low |
|--------|-------|------|--------|-----|
| Deployment Frequency | Multiple/day | Weekly-daily | Monthly-weekly | Monthly+ |
| Lead Time for Changes | < 1 hour | 1 day-1 week | 1 week-1 month | 1 month+ |
| Mean Time to Recovery | < 1 hour | < 1 day | 1 day-1 week | 1 week+ |
| Change Failure Rate | < 5% | 5-10% | 10-15% | 15%+ |

### Maturity Levels
```
Level 1: Manual/Ad-hoc
  - Manual deployments, no CI/CD
  - Snowflake servers, no IaC
  - Monitoring: "Users tell us when it's down"
  
Level 2: Standardized
  - CI/CD exists but not enforced everywhere
  - Some IaC (Terraform), some manual
  - Basic monitoring (CloudWatch alarms)
  
Level 3: Measured
  - CI/CD for all services, automated testing
  - Full IaC, GitOps emerging
  - Observability (metrics + logs + traces)
  - DORA metrics tracked
  
Level 4: Optimized
  - Continuous deployment, feature flags
  - Self-service platform, GitOps everywhere
  - SLO-based alerting, chaos engineering
  - Automated security (SAST, SCA, container scanning)
  
Level 5: Autonomous
  - Self-healing systems, auto-remediation
  - AI-assisted operations (anomaly detection)
  - Zero-touch deployments
  - Platform team enables 100+ engineers with < 5 platform engineers
```

---

## 7. Advanced Terraform Patterns

### Terraform at Enterprise Scale
```
Repository Strategy (50+ engineers, 200+ services):

Option A: Monorepo (all Terraform in one repo)
  Pros: Easy cross-referencing, atomic changes
  Cons: CI pipeline gets slow, merge conflicts, blast radius
  
Option B: Polyrepo (separate repo per component/team)
  Pros: Independent teams, focused CI, clear ownership
  Cons: Cross-component changes harder, module versioning needed
  
Recommended: Hybrid
  - Shared modules: one repo (versioned, published to registry)
  - Per-team infrastructure: team repos
  - Platform foundation: platform team repo (VPC, EKS, networking)
```

### Terraform Module Design Principles (Architect-level)
```hcl
# Good module design:
# 1. Single responsibility (one module = one concern)
# 2. Clear interface (well-documented variables/outputs)
# 3. Sensible defaults (work out of the box, customize when needed)
# 4. Composition over inheritance (combine modules, don't nest deep)

module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.0"
  
  # Minimal required inputs
  name = "production"
  cidr = "10.0.0.0/16"
  
  # Sensible defaults for most, overridable
  azs             = ["us-east-1a", "us-east-1b", "us-east-1c"]
  private_subnets = ["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24"]
  public_subnets  = ["10.0.101.0/24", "10.0.102.0/24", "10.0.103.0/24"]
  
  # Opinionated but overridable
  enable_nat_gateway = true
  single_nat_gateway = false  # one per AZ for HA
  enable_vpn_gateway = false
}
```

### State Management at Scale
- **State per blast radius:** If one `terraform apply` could destroy your whole production → split it
- **Recommended splits:**
  ```
  States:
    network/       (VPC, TGW, Direct Connect) - rarely changes, high impact
    eks-cluster/   (EKS control plane, node groups) - moderate changes
    eks-addons/    (Helm releases, K8s resources) - frequent changes
    databases/     (RDS, DynamoDB) - rarely changes, critical
    services/user/ (per-service ECS/K8s resources) - frequent, team-owned
    services/order/
    monitoring/    (dashboards, alerts) - moderate changes
  ```
- **Cross-state references:** `terraform_remote_state` data source OR Terraform Cloud outputs
- **Locking:** DynamoDB + S3 (always). Terraform Cloud (automatic)

---

## 8. Container Security Deep Dive

### Image Security Pipeline
```
Build Stage:
  1. Base image: Use minimal base (distroless, Alpine, scratch)
  2. Multi-stage build: Don't include build tools in final image
  3. No secrets: Never COPY secrets into image layers
  4. Non-root: USER 1000 in Dockerfile
  5. Read-only filesystem: Don't write to container filesystem

Scan Stage:
  6. Vulnerability scan: Trivy/Grype (fail on Critical/High)
  7. Misconfiguration: Dockerfile best practices (Hadolint)
  8. Secret detection: TruffleHog/GitLeaks on image layers
  9. SBOM: Generate software bill of materials (Syft)

Sign Stage:
  10. Sign image: Cosign with OIDC (keyless signing)
  11. Attestation: Record build provenance (SLSA)

Deploy Stage:
  12. Admission control: Verify signature before allowing in cluster
  13. Pod security: Enforce non-root, read-only, drop capabilities
  14. Runtime: Falco monitors for anomalous behavior
```

### Runtime Security
- **Falco:** Detect anomalous container behavior
  - Rules: Unexpected process execution, file access, network connection
  - Example: Alert if container runs `bash` (shouldn't in production)
- **Seccomp profiles:** Restrict system calls available to container
  - RuntimeDefault: Blocks dangerous syscalls (keyctl, ptrace)
  - Custom: Allow only specific syscalls your app needs
- **AppArmor/SELinux:** Mandatory access control at OS level
- **Read-only root filesystem:** Prevent runtime modifications to container
- **Network Policies:** Zero-trust networking (deny all, allow specific)

---

## 9. Cost Engineering

### AWS Cost Optimization Checklist (Architect-level)
```
Compute (40% of typical bill):
  □ Savings Plans purchased for baseline compute (60%+ utilization)
  □ Spot instances for fault-tolerant workloads (CI/CD, batch, dev)
  □ Graviton (ARM) migration where supported (20% savings)
  □ Right-sizing reviewed quarterly (Compute Optimizer)
  □ Non-production environments scheduled (nights/weekends off)
  □ Lambda provisioned concurrency only where needed

Storage (20% of typical bill):
  □ S3 lifecycle policies (IA→Glacier→Deep Archive)
  □ EBS volume type optimization (gp2→gp3, right-size IOPS)
  □ Snapshot lifecycle (delete old snapshots)
  □ EFS: Use IA storage class for infrequent files

Data Transfer (15% of typical bill):
  □ VPC endpoints for S3/DynamoDB/ECR (avoid NAT Gateway charges)
  □ Same-AZ communication where possible ($0 vs $0.01/GB)
  □ CloudFront for origin offload (cheaper than direct)
  □ Compress data in transit

Database (15% of typical bill):
  □ Aurora Serverless v2 for variable workloads
  □ Reserved instances for steady-state databases
  □ Read replicas + caching to reduce primary load
  □ DynamoDB on-demand vs provisioned (analyze usage pattern)
  □ TTL + archival for old data

Monitoring (10% of typical bill):
  □ CloudWatch Logs: Route to S3 instead of CW Logs where possible
  □ Metrics: Reduce custom metric cardinality
  □ Traces: Sample (10% normal traffic)
  □ Retention: Tier from hot→warm→cold
```

### Unit Economics Dashboard
```
Metrics every architect should track:
  - Cost per transaction: Total cost / transaction count
  - Cost per user: Total cost / active users
  - Cost per GB stored: Storage cost / data volume
  - Cost per API call: API infrastructure cost / request count
  - Infrastructure efficiency: Revenue / infrastructure cost (target: > 5:1)
  
Alert when:
  - Cost per transaction increases > 10% week-over-week
  - Any service cost grows > 20% month-over-month without traffic growth
  - Overall infra cost / revenue ratio deteriorates
```

---

## 10. Scenario-Based Questions (Staff/Architect)

### Q1: "You're the architect for a new product. How do you make technology decisions that will last 5 years?"
**Answer:**
- **Principles over products:** Choose boring technology for foundations (PostgreSQL > latest NoSQL). Save innovation budget for differentiators
- **Reversibility:** Prefer reversible decisions (can switch later) over irreversible (data model, API contracts)
- **Minimal viable architecture:** Start simple, add complexity only when forced by actual problems (not predicted ones)
- **Decision records:** ADR for every significant choice. Future engineers understand WHY
- **Escape hatches:** Abstract critical dependencies (database behind repository pattern, cloud behind interface)
- **Review cadence:** Quarterly fitness function review (is our architecture still fit for purpose?)
- **Staff insight:** The best architecture decisions are the ones you DON'T have to make yet. Defer until last responsible moment

### Q2: "Platform team is seen as a blocker by product teams. How do you fix this?"
**Answer:**
- **Diagnose:** What are teams waiting for? Deployments? Environments? Approvals? Infrastructure?
- **Self-service everything:** If teams need platform team involvement → build self-service
  - Need a database? → Click in catalog, get one in 5 minutes
  - Need to deploy? → Push to main, automatic deployment
  - Need access? → Self-service with automated approval
- **Inner source model:** Platform provides golden paths but allows teams to contribute and extend
- **SLA with teams:** "Your service will be deployed within 15 minutes of merge" (measurable)
- **Embed temporarily:** Platform engineer joins product team for 2 weeks to understand pain
- **Metrics:** Track "time blocked waiting for platform" → drive it to zero
- **Culture shift:** Platform as product. Product teams are customers. Their productivity is your success metric

### Q3: "How do you evaluate whether to adopt a new technology (e.g., should we use Rust for our services)?"
**Answer:**
- **Framework:**
  1. What problem does this solve that current tools don't? (Quantify: "2x faster" or "50% less memory")
  2. What's the cost? (Learning curve: months. Hiring market: smaller. Ecosystem: less mature)
  3. Is this a differentiator or commodity? (If commodity → use proven tech. If differentiator → investment justified)
  4. Can we experiment cheaply? (Single non-critical service first, not rewrite everything)
  5. What does success look like? (Measurable criteria after 3 months: team velocity, performance, hiring)
  
- **For Rust specifically:**
  - Good for: Performance-critical paths, infrastructure tools, ML inference, CLI tools
  - Bad for: CRUD microservices (Go/TypeScript faster to develop, good enough performance)
  - Decision: Use for 1-2 performance-critical services. Keep Go/TypeScript for everything else
  - Timeline: 3-month experiment with one service + 2 engineers. Evaluate: dev speed, performance, team satisfaction

### Q4: "Design the developer onboarding experience. New hire should deploy to production in their first week"
**Answer:**
```
Day 1: Environment setup
  - One-click dev environment (Codespaces/DevContainer)
  - All dependencies, tools, access pre-configured
  - "Hello World" service running locally in < 1 hour

Day 2-3: Understanding the system
  - Architecture overview (Backstage system map)
  - Follow a request end-to-end (distributed trace walkthrough)
  - Pair with team member on small task

Day 4: First PR
  - Small, real change (not just docs)
  - CI/CD runs automatically (tests, security, lint)
  - PR deployed to preview environment

Day 5: First production deploy
  - PR merged → auto-deployed via GitOps
  - New hire monitors their change (dashboards, logs)
  - Celebrate! 🎉

Enablers:
  - Golden path templates (clone → modify → deploy)
  - Self-service access provisioning (no waiting for IT)
  - Comprehensive documentation (in Backstage, not random wikis)
  - Preview environments per PR
  - Fast CI/CD (< 10 min from push to production)
  - Buddy/mentor assigned for first month
```

### Q5: "System costs are growing faster than revenue. You need to cut infrastructure cost by 40% without impacting performance or reliability. Strategy?"
**Answer:**
- **Phase 1: Quick wins (Week 1-2, target 15% savings)**
  - Delete unused resources (Lambda: set CloudWatch alarm for 0 invocations, EC2: CPU < 5% for 2 weeks)
  - Schedule non-prod environments (off 7pm-7am + weekends = 65% runtime reduction)
  - Switch gp2 → gp3 (20% cheaper, better performance)
  - Delete old snapshots, unattached EBS volumes, unused Elastic IPs
  
- **Phase 2: Right-sizing (Week 2-4, target 15% savings)**
  - Compute Optimizer recommendations (accept all with < 5% CPU impact)
  - Graviton migration for compatible workloads (20% cheaper)
  - Lambda memory optimization (power tuning for top 20 functions by cost)
  - RDS: Downsize dev/staging, Reserved Instances for production
  
- **Phase 3: Architecture optimization (Month 2-3, target 10% savings)**
  - VPC endpoints (eliminate NAT Gateway data processing charges)
  - Caching layer (reduce database and API calls)
  - Data tiering (S3 lifecycle: IA after 30 days, Glacier after 90)
  - Replace ELBs: Consolidate ALBs (multiple services behind one ALB with path routing)
  - Spot instances for batch processing and CI/CD runners
  
- **Governance:** 
  - Tag enforcement (untagged resources auto-terminated after 7 days)
  - Team-level budget alerts
  - Monthly cost review in sprint planning
  - Cost considered in architecture review (new services require cost estimate)

