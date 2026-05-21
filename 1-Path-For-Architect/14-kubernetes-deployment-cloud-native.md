# Kubernetes, Deployment, and Cloud Native Operations

_Split from `../world_class_pro_architect_master_roadmap.md`. The original source file is intentionally untouched._

---

# 15. Kubernetes, Deployment, and Cloud-Native Roadmap

## Kubernetes Core

- Cluster.
- Node.
- Pod.
- Deployment.
- ReplicaSet.
- StatefulSet.
- DaemonSet.
- Job.
- CronJob.
- Service.
- EndpointSlice.
- Ingress.
- Gateway API.
- ConfigMap.
- Secret.
- Volume.
- PersistentVolume.
- PersistentVolumeClaim.
- StorageClass.
- Namespace.
- ServiceAccount.
- RBAC.
- NetworkPolicy.
- Resource requests and limits.
- Probes.
- HPA.
- VPA.
- Cluster Autoscaler.
- PodDisruptionBudget.
- Taints and tolerations.
- Affinity and anti-affinity.
- CRD.
- Operator.

## Deployment

- Dockerfile best practices.
- Multi-stage builds.
- Image scanning.
- SBOM.
- Container registry.
- CI/CD.
- GitOps.
- Argo CD.
- Flux.
- Helm.
- Kustomize.
- Terraform.
- Secrets management.
- Rolling deployment.
- Blue-green deployment.
- Canary deployment.
- Shadow traffic.
- Feature flags.
- Rollback.
- Database migration.
- Expand-contract pattern.

## Kubernetes Troubleshooting

Know how to debug:

- CrashLoopBackOff.
- ImagePullBackOff.
- Pending pods.
- Readiness probe failures.
- Liveness probe failures.
- OOMKilled.
- CPU throttling.
- DNS failure.
- Service routing failure.
- Ingress routing failure.
- Persistent volume mount failure.
- RBAC denied.
- NetworkPolicy blocking traffic.
- HPA not scaling.
- Rollout stuck.

---

# 16. Security and Cloud Architecture Roadmap

## 20.4 Cloud and Deployment Deep Dive

### Cloud Architecture Must-Know

- AWS/Azure/GCP identity and IAM primitives.
- VPC/VNet design, subnets, route tables, NAT, private endpoints.
- DNS, service discovery, private hosted zones.
- Object storage: S3/GCS/Blob durability, consistency behavior, lifecycle, versioning, encryption, access policies.
- Compute choices: VM, container, serverless, managed Kubernetes, batch jobs.
- Managed database trade-offs: operational simplicity vs lock-in and limits.
- Multi-AZ vs multi-region design.
- DR: backup, restore, pilot light, warm standby, active-active.
- FinOps: unit economics, right sizing, storage tiering, data transfer, idle resources.

### Deployment and Release Engineering

- Rolling, blue-green, canary, shadow, dark launch, feature flags.
- Immutable artifacts and environment-specific configuration.
- Expand-contract database migration.
- Backward-compatible API and event changes.
- Rollback vs roll-forward decision.
- GitOps with drift detection.
- Policy as code for deployment guardrails.
- Progressive delivery with metrics gates.
- Release runbooks and incident rollback criteria.

### Kubernetes Production Depth

- Pod scheduling: requests, limits, QoS, affinity, topology spread, taints, tolerations.
- Reliability: readiness, liveness, startup probes, PodDisruptionBudget.
- Networking: Service, EndpointSlice, Ingress, Gateway API, NetworkPolicy, CNI.
- Scaling: HPA, VPA, Cluster Autoscaler, KEDA for event-driven scaling.
- Storage: PV, PVC, StorageClass, CSI, StatefulSet identity.
- Security: RBAC, ServiceAccount, Pod Security Standards, secrets, admission control.
- Operations: Helm, Kustomize, Argo CD, Flux, operators, CRDs.
- Troubleshooting: DNS, image pulls, crash loops, OOM, throttling, routing, RBAC, rollout status.


