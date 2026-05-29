# Kubernetes Deep Dive - Advanced Concepts & Operations

## 1. Kubernetes Internals

### API Server Request Flow

```
Client Request → Authentication → Authorization (RBAC) → Admission Control → Validation → Persist to etcd
```

**Authentication Methods:**
- X.509 client certificates
- Bearer tokens (ServiceAccount tokens, OIDC)
- Webhook token authentication
- Authentication proxy

**Authorization (RBAC):**
```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: pod-reader
rules:
- apiGroups: [""]
  resources: ["pods"]
  verbs: ["get", "watch", "list"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: read-pods-global
subjects:
- kind: User
  name: jane
  apiGroup: rbac.authorization.k8s.io
roleRef:
  kind: ClusterRole
  name: pod-reader
  apiGroup: rbac.authorization.k8s.io
```

**Admission Controllers (order matters):**
1. MutatingAdmissionWebhook - modifies objects (inject sidecars, add labels)
2. ValidatingAdmissionWebhook - rejects invalid objects (policy enforcement)
3. Built-in: LimitRanger, ResourceQuota, PodSecurity, DefaultStorageClass

### etcd Deep Dive

- Distributed key-value store using **Raft consensus** (leader election, log replication)
- All K8s state stored here: pods, services, secrets, configmaps, CRDs
- Recommended: 3 or 5 node cluster (tolerates 1 or 2 failures)

**Backup and Restore:**
```bash
# Snapshot backup
ETCDCTL_API=3 etcdctl snapshot save /backup/etcd-snapshot.db \
  --endpoints=https://127.0.0.1:2379 \
  --cacert=/etc/kubernetes/pki/etcd/ca.crt \
  --cert=/etc/kubernetes/pki/etcd/server.crt \
  --key=/etc/kubernetes/pki/etcd/server.key

# Verify snapshot
ETCDCTL_API=3 etcdctl snapshot status /backup/etcd-snapshot.db --write-table

# Restore
ETCDCTL_API=3 etcdctl snapshot restore /backup/etcd-snapshot.db \
  --data-dir=/var/lib/etcd-restored \
  --initial-cluster=master1=https://10.0.0.1:2380 \
  --initial-advertise-peer-urls=https://10.0.0.1:2380
```

**Compaction and Defragmentation:**
```bash
# Compact to revision
etcdctl compact $(etcdctl endpoint status --write-fields="Revision" | cut -d, -f1)

# Defragment (reclaim space after compaction)
etcdctl defrag --endpoints=https://10.0.0.1:2379,https://10.0.0.2:2379
```

### Controller Pattern (Reconciliation Loop)

```
Watch (desired state from API) → Compare (desired vs actual) → Act (make changes) → Report (update status)
```

Every controller follows this pattern:
1. **Informers** watch API server for changes (uses watch + list for efficiency)
2. **Work Queue** buffers events for processing
3. **Reconcile** function compares desired vs actual state
4. **Act** to converge actual → desired

### Scheduler Internals

```
Pod arrives (unscheduled) → Filtering → Scoring → Binding
```

**Filtering (predicates):** eliminate nodes that can't run the pod
- NodeAffinity/NodeSelector match
- Sufficient CPU/memory resources
- Taints/tolerations
- PV topology constraints
- Pod topology spread constraints

**Scoring (priorities):** rank remaining nodes
- LeastRequestedPriority (spread workloads)
- MostRequestedPriority (bin packing for cost)
- NodeAffinityPriority
- InterPodAffinityPriority
- ImageLocalityPriority

**Custom Scheduling:**
```yaml
apiVersion: v1
kind: Pod
metadata:
  name: custom-scheduled
spec:
  schedulerName: my-custom-scheduler
  containers:
  - name: app
    image: nginx
```

### kubelet

- Runs on every node, registers node with API server
- Watches API server for pods assigned to its node
- Manages pod lifecycle via CRI (Container Runtime Interface)
- Reports node status (conditions, capacity, allocatable)
- Health probing: liveness, readiness, startup probes

### kube-proxy Modes

| Mode | Mechanism | Performance | Use Case |
|------|-----------|-------------|----------|
| iptables | NAT rules per service/endpoint | O(n) rule matching | Default, <1000 services |
| IPVS | Hash table in kernel | O(1) lookup | >1000 services, advanced LB |
| nftables | Modern netfilter | Better than iptables | K8s 1.29+, future default |

---

## 2. Pod Advanced Concepts

### Multi-Container Patterns

**Sidecar Pattern - Envoy Proxy:**
```yaml
apiVersion: v1
kind: Pod
metadata:
  name: app-with-sidecar
spec:
  containers:
  - name: app
    image: myapp:v1
    ports:
    - containerPort: 8080
  - name: envoy-sidecar
    image: envoyproxy/envoy:v1.28
    ports:
    - containerPort: 9901  # admin
    - containerPort: 8443  # proxy
    volumeMounts:
    - name: envoy-config
      mountPath: /etc/envoy
  volumes:
  - name: envoy-config
    configMap:
      name: envoy-config
```

**Sidecar Pattern - Log Shipping:**
```yaml
apiVersion: v1
kind: Pod
metadata:
  name: app-with-logging
spec:
  containers:
  - name: app
    image: myapp:v1
    volumeMounts:
    - name: logs
      mountPath: /var/log/app
  - name: log-shipper
    image: fluent/fluent-bit:latest
    volumeMounts:
    - name: logs
      mountPath: /var/log/app
      readOnly: true
    - name: fluent-config
      mountPath: /fluent-bit/etc
  volumes:
  - name: logs
    emptyDir: {}
  - name: fluent-config
    configMap:
      name: fluent-bit-config
```

**Ambassador Pattern:**
```yaml
apiVersion: v1
kind: Pod
metadata:
  name: app-with-ambassador
spec:
  containers:
  - name: app
    image: myapp:v1
    env:
    - name: DB_HOST
      value: "localhost"  # connects to ambassador
    - name: DB_PORT
      value: "5432"
  - name: db-ambassador
    image: ambassador-proxy:v1
    env:
    - name: UPSTREAM_DB
      value: "primary.db.svc.cluster.local:5432"
    - name: FAILOVER_DB
      value: "replica.db.svc.cluster.local:5432"
    ports:
    - containerPort: 5432
```

**Adapter Pattern:**
```yaml
apiVersion: v1
kind: Pod
metadata:
  name: app-with-adapter
spec:
  containers:
  - name: app
    image: legacy-app:v1
    volumeMounts:
    - name: logs
      mountPath: /var/log/app
  - name: log-adapter
    image: log-adapter:v1  # converts legacy format to JSON
    volumeMounts:
    - name: logs
      mountPath: /var/log/app
      readOnly: true
```

**Init Containers:**
```yaml
apiVersion: v1
kind: Pod
metadata:
  name: app-with-init
spec:
  initContainers:
  - name: wait-for-db
    image: busybox:1.36
    command: ['sh', '-c', 'until nslookup postgres.default.svc.cluster.local; do sleep 2; done']
  - name: run-migrations
    image: myapp-migrations:v1
    command: ['./migrate', 'up']
    env:
    - name: DATABASE_URL
      valueFrom:
        secretKeyRef:
          name: db-credentials
          key: url
  containers:
  - name: app
    image: myapp:v1
```

### Pod Lifecycle Hooks and Graceful Shutdown

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: graceful-app
spec:
  terminationGracePeriodSeconds: 60
  containers:
  - name: app
    image: myapp:v1
    lifecycle:
      postStart:
        exec:
          command: ["/bin/sh", "-c", "echo started > /tmp/started"]
      preStop:
        exec:
          command: ["/bin/sh", "-c", "sleep 5 && /app/shutdown"]
    # OR preStop with HTTP
    # lifecycle:
    #   preStop:
    #     httpGet:
    #       path: /shutdown
    #       port: 8080
```

**Shutdown sequence:**
1. Pod marked as Terminating
2. Endpoints removed (stop receiving traffic) - happens in parallel with step 3
3. `preStop` hook executes
4. `SIGTERM` sent to PID 1
5. Wait for `terminationGracePeriodSeconds`
6. `SIGKILL` if still running

**Why `sleep` in preStop:** Endpoints removal is asynchronous. The sleep ensures kube-proxy/ingress has time to update rules before the app stops.

### Pod Disruption Budgets

```yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: app-pdb
spec:
  minAvailable: 2       # OR use maxUnavailable: 1
  selector:
    matchLabels:
      app: my-app
---
# Percentage-based
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: app-pdb-percent
spec:
  maxUnavailable: "25%"
  selector:
    matchLabels:
      app: my-app
```

PDBs protect against **voluntary disruptions**: node drain, cluster upgrade, scaling down. They do NOT protect against involuntary disruptions (node failure, OOM).

### Ephemeral Containers (Debugging)

```bash
# Debug a running pod (no restart needed)
kubectl debug -it pod/myapp --image=busybox:1.36 --target=app

# Debug with network tools
kubectl debug -it pod/myapp --image=nicolaka/netshoot --target=app

# Copy pod for debugging (new pod with debug container)
kubectl debug pod/myapp -it --copy-to=myapp-debug --container=debug --image=ubuntu

# Debug node
kubectl debug node/worker-1 -it --image=ubuntu
```

---

## 3. Advanced Deployment Strategies

### Rolling Update (Default)

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: myapp
spec:
  replicas: 10
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 25%          # max pods above desired (3 extra)
      maxUnavailable: 25%    # max pods that can be down (2 down)
  progressDeadlineSeconds: 600  # timeout for rollout
  minReadySeconds: 30          # wait before considering pod ready
  revisionHistoryLimit: 10
  selector:
    matchLabels:
      app: myapp
  template:
    metadata:
      labels:
        app: myapp
    spec:
      containers:
      - name: app
        image: myapp:v2
        readinessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 5
          periodSeconds: 5
```

```bash
# Monitor rollout
kubectl rollout status deployment/myapp

# Rollback
kubectl rollout undo deployment/myapp
kubectl rollout undo deployment/myapp --to-revision=3

# History
kubectl rollout history deployment/myapp
```

### Blue/Green Deployment

```yaml
# Blue deployment (current)
apiVersion: apps/v1
kind: Deployment
metadata:
  name: myapp-blue
spec:
  replicas: 3
  selector:
    matchLabels:
      app: myapp
      version: blue
  template:
    metadata:
      labels:
        app: myapp
        version: blue
    spec:
      containers:
      - name: app
        image: myapp:v1
---
# Green deployment (new)
apiVersion: apps/v1
kind: Deployment
metadata:
  name: myapp-green
spec:
  replicas: 3
  selector:
    matchLabels:
      app: myapp
      version: green
  template:
    metadata:
      labels:
        app: myapp
        version: green
    spec:
      containers:
      - name: app
        image: myapp:v2
---
# Service - switch selector to cut over
apiVersion: v1
kind: Service
metadata:
  name: myapp
spec:
  selector:
    app: myapp
    version: blue  # Change to "green" to switch
  ports:
  - port: 80
    targetPort: 8080
```

```bash
# Switch traffic to green
kubectl patch service myapp -p '{"spec":{"selector":{"version":"green"}}}'

# Rollback to blue
kubectl patch service myapp -p '{"spec":{"selector":{"version":"blue"}}}'
```

### Canary Deployment (Native K8s)

```yaml
# Stable deployment (90% traffic)
apiVersion: apps/v1
kind: Deployment
metadata:
  name: myapp-stable
spec:
  replicas: 9
  selector:
    matchLabels:
      app: myapp
      track: stable
  template:
    metadata:
      labels:
        app: myapp
        track: stable
    spec:
      containers:
      - name: app
        image: myapp:v1
---
# Canary deployment (10% traffic)
apiVersion: apps/v1
kind: Deployment
metadata:
  name: myapp-canary
spec:
  replicas: 1
  selector:
    matchLabels:
      app: myapp
      track: canary
  template:
    metadata:
      labels:
        app: myapp
        track: canary
    spec:
      containers:
      - name: app
        image: myapp:v2
---
# Service routes to both (weighted by replica count)
apiVersion: v1
kind: Service
metadata:
  name: myapp
spec:
  selector:
    app: myapp   # matches both stable and canary
  ports:
  - port: 80
    targetPort: 8080
```

### Argo Rollouts - Canary with Analysis

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Rollout
metadata:
  name: myapp
spec:
  replicas: 10
  selector:
    matchLabels:
      app: myapp
  strategy:
    canary:
      steps:
      - setWeight: 10
      - pause: {duration: 5m}
      - analysis:
          templates:
          - templateName: success-rate
      - setWeight: 30
      - pause: {duration: 5m}
      - analysis:
          templates:
          - templateName: success-rate
      - setWeight: 50
      - pause: {duration: 10m}
      - setWeight: 100
      canaryService: myapp-canary
      stableService: myapp-stable
      trafficRouting:
        nginx:
          stableIngress: myapp-ingress
  template:
    metadata:
      labels:
        app: myapp
    spec:
      containers:
      - name: app
        image: myapp:v2
---
apiVersion: argoproj.io/v1alpha1
kind: AnalysisTemplate
metadata:
  name: success-rate
spec:
  metrics:
  - name: success-rate
    interval: 30s
    successCondition: result[0] >= 0.95
    provider:
      prometheus:
        address: http://prometheus.monitoring:9090
        query: |
          sum(rate(http_requests_total{status=~"2.*",app="myapp",track="canary"}[5m]))
          /
          sum(rate(http_requests_total{app="myapp",track="canary"}[5m]))
```

---

## 4. Operators and CRDs

### Custom Resource Definition

```yaml
apiVersion: apiextensions.k8s.io/v1
kind: CustomResourceDefinition
metadata:
  name: databases.mycompany.io
spec:
  group: mycompany.io
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
                minimum: 1
                maximum: 5
              storage:
                type: string
            required: ["engine", "version", "replicas"]
          status:
            type: object
            properties:
              phase:
                type: string
              endpoint:
                type: string
    subresources:
      status: {}
    additionalPrinterColumns:
    - name: Engine
      type: string
      jsonPath: .spec.engine
    - name: Phase
      type: string
      jsonPath: .status.phase
  scope: Namespaced
  names:
    plural: databases
    singular: database
    kind: Database
    shortNames:
    - db
```

**Using the CRD:**
```yaml
apiVersion: mycompany.io/v1
kind: Database
metadata:
  name: orders-db
  namespace: production
spec:
  engine: postgres
  version: "15.4"
  replicas: 3
  storage: "100Gi"
```

```bash
kubectl get databases
kubectl get db orders-db -o yaml
kubectl describe db orders-db
```

### Operator Pattern

The operator watches for Database CRs and creates:
- StatefulSet with correct image/config
- PVCs for storage
- Services for connectivity
- ConfigMaps for configuration
- Secrets for credentials
- CronJobs for backups

### Popular Operators

| Operator | Purpose | CRDs |
|----------|---------|------|
| Prometheus Operator | Monitoring stack | Prometheus, ServiceMonitor, AlertmanagerConfig |
| cert-manager | TLS certificates | Certificate, Issuer, ClusterIssuer |
| Strimzi | Kafka | Kafka, KafkaTopic, KafkaUser |
| CloudNativePG | PostgreSQL | Cluster, Backup, ScheduledBackup |
| Crossplane | Infrastructure | various provider CRDs |

---

## 5. Kubernetes Networking Deep Dive

### CNI Plugin Comparison

| CNI | Mechanism | Key Feature | Best For |
|-----|-----------|-------------|----------|
| AWS VPC CNI | Native VPC IPs | Pod gets real VPC IP | EKS, VPC integration |
| Calico | BGP or VXLAN | Network policies, peering | On-prem, advanced policy |
| Cilium | eBPF | L7 policies, no iptables | Performance, observability |
| Flannel | VXLAN | Simple overlay | Development, simple setups |

### AWS VPC CNI Details

- Each pod gets a real VPC IP from the subnet
- ENI attached to node, secondary IPs assigned to pods
- **Max pods per node** = (number of ENIs × IPs per ENI) - 1
  - m5.large: 3 ENIs × 10 IPs = 29 pods max
  - m5.xlarge: 4 ENIs × 15 IPs = 58 pods max
- Prefix delegation mode: assigns /28 prefixes (16 IPs) per slot

```yaml
# Increase max pods with prefix delegation
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: aws-node
  namespace: kube-system
spec:
  template:
    spec:
      containers:
      - name: aws-node
        env:
        - name: ENABLE_PREFIX_DELEGATION
          value: "true"
        - name: WARM_PREFIX_TARGET
          value: "1"
```

### Service Internals

**ClusterIP flow:**
```
Pod → iptables/IPVS → random endpoint pod IP
```

**NodePort flow:**
```
External → NodeIP:NodePort → iptables → Pod IP
```

**LoadBalancer flow (AWS):**
```
Client → NLB/ALB → NodePort → iptables → Pod IP
(or with target-type: ip)
Client → NLB → Pod IP directly (VPC CNI)
```

### Ingress with NGINX

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: myapp-ingress
  annotations:
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
    nginx.ingress.kubernetes.io/rate-limit: "100"
    nginx.ingress.kubernetes.io/rate-limit-window: "1m"
    nginx.ingress.kubernetes.io/proxy-body-size: "50m"
    nginx.ingress.kubernetes.io/canary: "true"
    nginx.ingress.kubernetes.io/canary-weight: "20"
    cert-manager.io/cluster-issuer: letsencrypt-prod
spec:
  ingressClassName: nginx
  tls:
  - hosts:
    - app.example.com
    secretName: app-tls
  rules:
  - host: app.example.com
    http:
      paths:
      - path: /api
        pathType: Prefix
        backend:
          service:
            name: api-service
            port:
              number: 80
      - path: /
        pathType: Prefix
        backend:
          service:
            name: frontend-service
            port:
              number: 80
```

### DNS (CoreDNS)

Resolution path for a pod:
```
my-svc                    → my-svc.default.svc.cluster.local
my-svc.other-ns           → my-svc.other-ns.svc.cluster.local
external.example.com      → resolved via upstream DNS
```

**ndots issue and fix:**
```yaml
apiVersion: v1
kind: Pod
metadata:
  name: myapp
spec:
  dnsConfig:
    options:
    - name: ndots
      value: "2"    # default is 5, causes extra lookups
    - name: single-request-reopen
      value: ""
  containers:
  - name: app
    image: myapp:v1
```

### Network Policies

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: api-policy
  namespace: production
spec:
  podSelector:
    matchLabels:
      app: api
  policyTypes:
  - Ingress
  - Egress
  ingress:
  - from:
    - namespaceSelector:
        matchLabels:
          name: frontend
      podSelector:
        matchLabels:
          app: web
    ports:
    - protocol: TCP
      port: 8080
  egress:
  - to:
    - podSelector:
        matchLabels:
          app: database
    ports:
    - protocol: TCP
      port: 5432
  - to:  # Allow DNS
    - namespaceSelector: {}
      podSelector:
        matchLabels:
          k8s-app: kube-dns
    ports:
    - protocol: UDP
      port: 53
```

**Default deny all:**
```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-all
  namespace: production
spec:
  podSelector: {}
  policyTypes:
  - Ingress
  - Egress
```

---

## 6. Storage Deep Dive

### EBS CSI Driver

```yaml
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: ebs-gp3
provisioner: ebs.csi.aws.com
parameters:
  type: gp3
  iops: "5000"
  throughput: "250"
  encrypted: "true"
  kmsKeyId: "arn:aws:kms:us-east-1:123456:key/abc-123"
volumeBindingMode: WaitForFirstConsumer  # Important for topology
reclaimPolicy: Delete
allowVolumeExpansion: true
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: data-pvc
spec:
  accessModes:
  - ReadWriteOnce
  storageClassName: ebs-gp3
  resources:
    requests:
      storage: 100Gi
```

### EFS CSI Driver (Shared Storage)

```yaml
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: efs-sc
provisioner: efs.csi.aws.com
parameters:
  provisioningMode: efs-ap
  fileSystemId: fs-abc123
  directoryPerms: "700"
  basePath: "/dynamic_provisioning"
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: shared-data
spec:
  accessModes:
  - ReadWriteMany   # Multiple pods across nodes
  storageClassName: efs-sc
  resources:
    requests:
      storage: 5Gi
```

### Volume Snapshots

```yaml
apiVersion: snapshot.storage.k8s.io/v1
kind: VolumeSnapshotClass
metadata:
  name: ebs-snapshot-class
driver: ebs.csi.aws.com
deletionPolicy: Retain
---
apiVersion: snapshot.storage.k8s.io/v1
kind: VolumeSnapshot
metadata:
  name: data-snapshot
spec:
  volumeSnapshotClassName: ebs-snapshot-class
  source:
    persistentVolumeClaimName: data-pvc
---
# Restore from snapshot
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: data-restored
spec:
  accessModes:
  - ReadWriteOnce
  storageClassName: ebs-gp3
  resources:
    requests:
      storage: 100Gi
  dataSource:
    name: data-snapshot
    kind: VolumeSnapshot
    apiGroup: snapshot.storage.k8s.io
```

---

## 7. Security Deep Dive

### Pod Security (Hardened Pod)

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: secure-app
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
    image: myapp:v1
    securityContext:
      allowPrivilegeEscalation: false
      readOnlyRootFilesystem: true
      capabilities:
        drop:
        - ALL
      # Only add what you absolutely need:
      # capabilities:
      #   add:
      #   - NET_BIND_SERVICE
    volumeMounts:
    - name: tmp
      mountPath: /tmp
    - name: cache
      mountPath: /app/cache
  volumes:
  - name: tmp
    emptyDir: {}
  - name: cache
    emptyDir: {}
```

### External Secrets Operator (AWS)

```yaml
apiVersion: external-secrets.io/v1beta1
kind: SecretStore
metadata:
  name: aws-secrets
  namespace: production
spec:
  provider:
    aws:
      service: SecretsManager
      region: us-east-1
      auth:
        jwt:
          serviceAccountRef:
            name: external-secrets-sa
---
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: db-credentials
  namespace: production
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: aws-secrets
    kind: SecretStore
  target:
    name: db-credentials
    creationPolicy: Owner
  data:
  - secretKey: username
    remoteRef:
      key: production/database
      property: username
  - secretKey: password
    remoteRef:
      key: production/database
      property: password
```

### cert-manager

```yaml
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: admin@example.com
    privateKeySecretRef:
      name: letsencrypt-prod-key
    solvers:
    - http01:
        ingress:
          class: nginx
    - dns01:
        route53:
          region: us-east-1
---
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: app-cert
  namespace: production
spec:
  secretName: app-tls
  issuerRef:
    name: letsencrypt-prod
    kind: ClusterIssuer
  dnsNames:
  - app.example.com
  - "*.app.example.com"
```

### OPA Gatekeeper Policy

```yaml
apiVersion: templates.gatekeeper.sh/v1
kind: ConstraintTemplate
metadata:
  name: k8srequiredlabels
spec:
  crd:
    spec:
      names:
        kind: K8sRequiredLabels
      validation:
        openAPIV3Schema:
          type: object
          properties:
            labels:
              type: array
              items:
                type: string
  targets:
  - target: admission.k8s.gatekeeper.sh
    rego: |
      package k8srequiredlabels
      violation[{"msg": msg}] {
        provided := {label | input.review.object.metadata.labels[label]}
        required := {label | label := input.parameters.labels[_]}
        missing := required - provided
        count(missing) > 0
        msg := sprintf("Missing required labels: %v", [missing])
      }
---
apiVersion: constraints.gatekeeper.sh/v1beta1
kind: K8sRequiredLabels
metadata:
  name: require-team-label
spec:
  match:
    kinds:
    - apiGroups: ["apps"]
      kinds: ["Deployment"]
    namespaces: ["production"]
  parameters:
    labels:
    - "team"
    - "cost-center"
```

### Audit Logging

```yaml
apiVersion: audit.k8s.io/v1
kind: Policy
rules:
- level: None
  resources:
  - group: ""
    resources: ["endpoints", "services/status"]
- level: None
  users: ["system:kube-proxy"]
- level: Metadata
  resources:
  - group: ""
    resources: ["secrets", "configmaps"]
- level: Request
  resources:
  - group: ""
    resources: ["pods"]
  verbs: ["create", "delete", "patch"]
- level: RequestResponse
  resources:
  - group: "rbac.authorization.k8s.io"
  verbs: ["create", "delete", "update"]
- level: Metadata
  omitStages:
  - "RequestReceived"
```

---

## 8. Observability Stack

### Prometheus ServiceMonitor

```yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: myapp-monitor
  namespace: monitoring
  labels:
    release: prometheus
spec:
  namespaceSelector:
    matchNames:
    - production
  selector:
    matchLabels:
      app: myapp
  endpoints:
  - port: metrics
    interval: 15s
    path: /metrics
    scrapeTimeout: 10s
---
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: myapp-alerts
  namespace: monitoring
spec:
  groups:
  - name: myapp.rules
    rules:
    - alert: HighErrorRate
      expr: |
        sum(rate(http_requests_total{status=~"5.*",app="myapp"}[5m]))
        /
        sum(rate(http_requests_total{app="myapp"}[5m])) > 0.05
      for: 5m
      labels:
        severity: critical
      annotations:
        summary: "High error rate on {{ $labels.instance }}"
        description: "Error rate is {{ $value | humanizePercentage }}"
    - alert: PodCrashLooping
      expr: rate(kube_pod_container_status_restarts_total{namespace="production"}[15m]) > 0
      for: 5m
      labels:
        severity: warning
```

### Logging Architecture (Fluent Bit DaemonSet)

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: fluent-bit-config
  namespace: logging
data:
  fluent-bit.conf: |
    [SERVICE]
        Flush         5
        Daemon        Off
        Log_Level     info
        Parsers_File  parsers.conf

    [INPUT]
        Name              tail
        Tag               kube.*
        Path              /var/log/containers/*.log
        Parser            cri
        DB                /var/log/flb_kube.db
        Mem_Buf_Limit     50MB
        Skip_Long_Lines   On
        Refresh_Interval  10

    [FILTER]
        Name                kubernetes
        Match               kube.*
        Kube_URL            https://kubernetes.default.svc:443
        Kube_Tag_Prefix     kube.var.log.containers.
        Merge_Log           On
        K8S-Logging.Parser  On
        K8S-Logging.Exclude On

    [OUTPUT]
        Name            cloudwatch_logs
        Match           kube.*
        region          us-east-1
        log_group_name  /eks/production
        log_stream_prefix fluent-bit-
        auto_create_group true
```

### OpenTelemetry Collector

```yaml
apiVersion: opentelemetry.io/v1alpha1
kind: OpenTelemetryCollector
metadata:
  name: otel-collector
spec:
  mode: deployment
  config: |
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
        send_batch_size: 1000
      memory_limiter:
        limit_mib: 512
        spike_limit_mib: 128
      tail_sampling:
        policies:
        - name: errors
          type: status_code
          status_code: {status_codes: [ERROR]}
        - name: slow
          type: latency
          latency: {threshold_ms: 1000}
        - name: probabilistic
          type: probabilistic
          probabilistic: {sampling_percentage: 10}
    exporters:
      otlp:
        endpoint: tempo.monitoring:4317
      prometheus:
        endpoint: 0.0.0.0:8889
    service:
      pipelines:
        traces:
          receivers: [otlp]
          processors: [memory_limiter, tail_sampling, batch]
          exporters: [otlp]
        metrics:
          receivers: [otlp]
          processors: [memory_limiter, batch]
          exporters: [prometheus]
```

---

## 9. Cluster Operations

### Upgrade Strategy (Rolling Node Replacement on EKS)

```bash
# 1. Update control plane
aws eks update-cluster-version --name my-cluster --kubernetes-version 1.29

# 2. Update managed node group (rolling replacement)
aws eks update-nodegroup-version \
  --cluster-name my-cluster \
  --nodegroup-name workers \
  --kubernetes-version 1.29

# 3. Or with eksctl
eksctl upgrade cluster --name my-cluster --version 1.29 --approve
eksctl upgrade nodegroup --cluster my-cluster --name workers
```

### Node Maintenance

```bash
# Mark node unschedulable (no new pods)
kubectl cordon node/worker-3

# Drain (evict pods respecting PDBs)
kubectl drain node/worker-3 \
  --ignore-daemonsets \
  --delete-emptydir-data \
  --grace-period=60 \
  --timeout=300s

# Perform maintenance...

# Return node to service
kubectl uncordon node/worker-3
```

### Resource Quotas and Limit Ranges

```yaml
apiVersion: v1
kind: ResourceQuota
metadata:
  name: team-quota
  namespace: team-alpha
spec:
  hard:
    requests.cpu: "20"
    requests.memory: 40Gi
    limits.cpu: "40"
    limits.memory: 80Gi
    persistentvolumeclaims: "10"
    pods: "50"
    services.loadbalancers: "2"
---
apiVersion: v1
kind: LimitRange
metadata:
  name: default-limits
  namespace: team-alpha
spec:
  limits:
  - type: Container
    default:
      cpu: 500m
      memory: 512Mi
    defaultRequest:
      cpu: 100m
      memory: 128Mi
    max:
      cpu: "4"
      memory: 8Gi
    min:
      cpu: 50m
      memory: 64Mi
  - type: Pod
    max:
      cpu: "8"
      memory: 16Gi
```

### Cost Optimization with Spot Instances

```yaml
# EKS managed node group with spot
apiVersion: eksctl.io/v1alpha5
kind: ClusterConfig
metadata:
  name: my-cluster
  region: us-east-1
managedNodeGroups:
- name: spot-workers
  instanceTypes:
  - m5.large
  - m5a.large
  - m5d.large
  - m4.large
  capacityType: SPOT
  minSize: 2
  maxSize: 20
  desiredCapacity: 5
  labels:
    lifecycle: spot
  taints:
  - key: spot
    value: "true"
    effect: PreferNoSchedule
- name: on-demand-critical
  instanceTypes:
  - m5.xlarge
  capacityType: ON_DEMAND
  minSize: 2
  maxSize: 5
  labels:
    lifecycle: on-demand
```

**Schedule workloads on spot:**
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: batch-processor
spec:
  replicas: 10
  template:
    spec:
      tolerations:
      - key: spot
        operator: Equal
        value: "true"
        effect: PreferNoSchedule
      affinity:
        nodeAffinity:
          preferredDuringSchedulingIgnoredDuringExecution:
          - weight: 90
            preference:
              matchExpressions:
              - key: lifecycle
                operator: In
                values:
                - spot
      containers:
      - name: processor
        image: batch:v1
```

---

## 10. Troubleshooting Guide

### Pod States Explained

| State | Meaning | Common Causes |
|-------|---------|---------------|
| Pending | Not scheduled yet | Insufficient resources, node selectors, taints, PVC pending |
| CrashLoopBackOff | Container keeps crashing | App error, missing config, wrong command |
| ImagePullBackOff | Can't pull image | Wrong image name, no auth, registry down |
| OOMKilled | Out of memory | Memory limit too low, memory leak |
| Evicted | Node pressure | Disk/memory pressure on node |
| CreateContainerError | Can't create container | Missing ConfigMap/Secret, security context |

### Debug Commands Cheat Sheet

```bash
# Pod debugging
kubectl describe pod <pod>                    # Events, conditions, scheduling
kubectl logs <pod> -c <container>             # Current logs
kubectl logs <pod> -c <container> --previous  # Previous crash logs
kubectl logs <pod> --all-containers           # All containers
kubectl exec -it <pod> -- sh                  # Shell into pod
kubectl top pod <pod>                         # CPU/memory usage

# Events (sorted)
kubectl get events --sort-by='.lastTimestamp' -n <namespace>
kubectl get events --field-selector reason=OOMKilling

# Node debugging
kubectl describe node <node>                  # Conditions, capacity, pods
kubectl top nodes                             # Resource usage
kubectl get nodes -o wide                     # IPs, versions, OS

# Network debugging from within a pod
kubectl exec -it <pod> -- nslookup kubernetes.default
kubectl exec -it <pod> -- curl -v http://service-name:port/health
kubectl exec -it <pod> -- wget -qO- --timeout=2 http://service-name:port

# Using debug container
kubectl debug -it <pod> --image=nicolaka/netshoot -- bash
# Inside: tcpdump, dig, curl, nmap, iperf, ss, ip
```

### DNS Troubleshooting

```bash
# Check CoreDNS pods
kubectl get pods -n kube-system -l k8s-app=kube-dns

# Test resolution from a pod
kubectl run dnsutils --image=tutum/dnsutils --restart=Never -- sleep 3600
kubectl exec dnsutils -- nslookup my-service.default.svc.cluster.local
kubectl exec dnsutils -- cat /etc/resolv.conf

# Check CoreDNS logs
kubectl logs -n kube-system -l k8s-app=kube-dns

# Common fix: ndots too high causing excessive lookups
# Add to pod spec:
# dnsConfig:
#   options:
#   - name: ndots
#     value: "2"
```

### Node NotReady Runbook

```bash
# 1. Check node conditions
kubectl describe node <node> | grep -A5 Conditions

# 2. SSH to node (or debug)
kubectl debug node/<node> -it --image=ubuntu

# 3. Check kubelet
systemctl status kubelet
journalctl -u kubelet --since "10 minutes ago"

# 4. Check disk
df -h
# If disk full: clean images, logs

# 5. Check memory
free -m
# Check for OOM in dmesg

# 6. Check certificates
openssl x509 -in /var/lib/kubelet/pki/kubelet-client-current.pem -noout -dates

# 7. Check container runtime
crictl ps
crictl info
systemctl status containerd
```

### OOMKilled but Container Shows Low Memory

Possible causes:
1. **Memory limit vs requests**: Container hit its limit but Prometheus shows average (not peak)
2. **JVM/Go off-heap**: Runtime uses memory outside tracked heap
3. **Child processes**: Memory from forked processes counts against cgroup limit
4. **Kernel memory**: tcp buffers, page cache pressure
5. **Sidecar containers**: Total pod memory = sum of all containers

```bash
# Check actual cgroup usage (from node)
cat /sys/fs/cgroup/memory/kubepods/pod<uid>/<container-id>/memory.max_usage_in_bytes
cat /sys/fs/cgroup/memory/kubepods/pod<uid>/<container-id>/memory.oom_control
```

---

## 11. GitOps & Progressive Delivery

### ArgoCD Application

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: myapp
  namespace: argocd
  finalizers:
  - resources-finalizer.argocd.argoproj.io
spec:
  project: default
  source:
    repoURL: https://github.com/org/k8s-manifests.git
    targetRevision: main
    path: apps/myapp/overlays/production
  destination:
    server: https://kubernetes.default.svc
    namespace: production
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
    - CreateNamespace=true
    - PrunePropagationPolicy=foreground
    retry:
      limit: 3
      backoff:
        duration: 5s
        factor: 2
        maxDuration: 3m
```

### ArgoCD App-of-Apps

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: root-app
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/org/k8s-manifests.git
    targetRevision: main
    path: apps
  destination:
    server: https://kubernetes.default.svc
    namespace: argocd
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
```

### ArgoCD ApplicationSet

```yaml
apiVersion: argoproj.io/v1alpha1
kind: ApplicationSet
metadata:
  name: cluster-apps
  namespace: argocd
spec:
  generators:
  - clusters:
      selector:
        matchLabels:
          env: production
  template:
    metadata:
      name: '{{name}}-myapp'
    spec:
      project: default
      source:
        repoURL: https://github.com/org/k8s-manifests.git
        targetRevision: main
        path: 'apps/myapp/overlays/{{metadata.labels.env}}'
      destination:
        server: '{{server}}'
        namespace: myapp
```

### Flux GitOps

```yaml
apiVersion: source.toolkit.fluxcd.io/v1
kind: GitRepository
metadata:
  name: app-repo
  namespace: flux-system
spec:
  interval: 1m
  url: https://github.com/org/k8s-manifests
  ref:
    branch: main
  secretRef:
    name: git-credentials
---
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: myapp
  namespace: flux-system
spec:
  interval: 5m
  sourceRef:
    kind: GitRepository
    name: app-repo
  path: ./apps/myapp/production
  prune: true
  healthChecks:
  - apiVersion: apps/v1
    kind: Deployment
    name: myapp
    namespace: production
  timeout: 3m
```

---

## 12. Scenario-Based Interview Questions

### Q1: Design Zero-Downtime Cluster Upgrade

**Answer:**
1. **Pre-upgrade:** Ensure PDBs on all critical workloads, verify HPA/VPA configs, backup etcd
2. **Control plane:** Upgrade one minor version at a time (1.28→1.29, not 1.27→1.29)
3. **Node groups:** Use rolling replacement with new node group
   - Create new node group with new version
   - Cordon old nodes
   - Drain old nodes (PDBs ensure availability)
   - Delete old node group
4. **Validation:** Run smoke tests, check pod health, verify metrics
5. **Rollback plan:** Keep old node group until validation passes

### Q2: Pod OOMKilled but Container Shows Low Memory

See troubleshooting section above. Key: distinguish between heap memory and total RSS. Use `kubectl top pod` for real-time, and check cgroup metrics. Common in Java apps with off-heap buffers (Netty, memory-mapped files).

### Q3: Namespace-Level Resource Isolation

```yaml
# 1. ResourceQuota per namespace
# 2. LimitRange for defaults
# 3. NetworkPolicy for network isolation
# 4. RBAC: Role + RoleBinding per team
# 5. Pod Security Admission (enforce restricted)
apiVersion: v1
kind: Namespace
metadata:
  name: team-alpha
  labels:
    pod-security.kubernetes.io/enforce: restricted
    pod-security.kubernetes.io/warn: restricted
```

### Q4: Secrets Rotation Without Pod Restart

Options:
1. **Mounted secrets auto-update** (kubelet sync period ~1min) if using volume mount (NOT env vars)
2. **Reloader controller**: watches secrets, triggers rolling restart
3. **External Secrets Operator**: refreshInterval pulls new values, app reads from file
4. **Vault Agent sidecar**: sidecar keeps secrets fresh, app reads from shared volume
5. **Application-level**: app watches file changes and reloads

### Q5: Node NotReady Complete Runbook

See section 10 troubleshooting. Summary:
1. `kubectl describe node` → check conditions
2. Check kubelet status and logs
3. Check container runtime (containerd/CRI-O)
4. Check disk space and inode usage
5. Check certificates expiry
6. Check network connectivity to API server
7. Check system resources (memory, CPU, PID limits)

### Q6: Cost-Effective Spot Instance Strategy

- Use multiple instance types/AZs for availability
- Separate node groups: on-demand (critical) + spot (tolerant workloads)
- Use taints on spot nodes, tolerations on batch workloads
- Handle spot interruptions: 2-minute warning → node termination handler drains node
- AWS Node Termination Handler DaemonSet
- Pod anti-affinity to spread replicas across spot pools

### Q7: Multi-Cluster Disaster Recovery

- **Active-Active:** Deploy to multiple clusters, use Global Accelerator/Route53 failover
- **Active-Passive:** Primary cluster + standby with lower replica count
- **Data:** Cross-region replication for databases (RDS Multi-AZ, DynamoDB Global Tables)
- **GitOps:** Same manifests deployed to both clusters via ArgoCD ApplicationSet
- **Velero:** Backup/restore for cluster state

### Q8: Pod Scheduled but Container Won't Start

Debug process:
```bash
kubectl describe pod <pod>   # Look at Events section
# Common issues:
# - CreateContainerConfigError: missing ConfigMap/Secret
# - RunContainerError: security context violation
# - ImagePullBackOff: registry auth, image doesn't exist
# - CrashLoopBackOff: check logs --previous

kubectl get events --field-selector involvedObject.name=<pod>
kubectl logs <pod> --previous
```

### Q9: Progressive Delivery with Canary Analysis

Use Argo Rollouts (see section 3):
- Define AnalysisTemplate with Prometheus queries
- Set canary steps: 10% → analysis → 30% → analysis → 100%
- Auto-rollback if error rate > threshold or latency > SLO
- Integrate with service mesh for precise traffic splitting

### Q10: Logging Architecture for 1000-Pod Cluster

```
Pods → stdout/stderr → Container runtime log files → Fluent Bit DaemonSet → 
  → Buffer (filesystem) → CloudWatch Logs / OpenSearch / S3

Architecture:
- Fluent Bit DaemonSet (lightweight, per node)
- Log aggregator (Fluentd, optional) for complex routing
- Storage tier: hot (OpenSearch 7d) → warm (S3 30d) → archive (Glacier)
- Structured logging (JSON) enforced via admission webhook
- Log volume: estimate 1KB/req × 10K RPS = ~800GB/day
```

### Q11: etcd Performance Degradation

```bash
# Diagnosis
etcdctl endpoint status --write-table
etcdctl endpoint health
etcdctl alarm list

# Check disk latency (etcd needs <10ms fsync)
fio --name=test --rw=write --fdatasync=1 --size=22m

# Fixes:
# 1. Use SSD/io2 for etcd volumes
# 2. Compact and defragment
# 3. Reduce snapshot count if too many revisions
# 4. Separate etcd to dedicated nodes
# 5. Check network latency between etcd peers (<10ms RTT)
```

### Q12: Cluster Certificate Expiry

```bash
# Check certificate expiration
kubeadm certs check-expiration

# Renew all certificates
kubeadm certs renew all

# Restart control plane components
# (they read certs from disk)
crictl ps | grep -E "kube-apiserver|kube-controller|kube-scheduler"
# Kill and kubelet will restart them

# For kubelet client cert: enable auto-rotation
# --rotate-certificates=true (default in modern K8s)
```

### Q13: RBAC Design for Dev/Staging/Prod

```yaml
# Dev namespace - developers get broad access
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: developer
  namespace: dev
rules:
- apiGroups: ["", "apps", "batch"]
  resources: ["*"]
  verbs: ["*"]
---
# Production - read-only + limited exec
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: developer
  namespace: production
rules:
- apiGroups: ["", "apps"]
  resources: ["pods", "deployments", "services"]
  verbs: ["get", "list", "watch"]
- apiGroups: [""]
  resources: ["pods/log"]
  verbs: ["get"]
# No exec, no delete, no secrets access
---
# SRE - full access everywhere
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: sre-role
rules:
- apiGroups: ["*"]
  resources: ["*"]
  verbs: ["*"]
```

### Q14: Pod Priority and Preemption

```yaml
apiVersion: scheduling.k8s.io/v1
kind: PriorityClass
metadata:
  name: critical
value: 1000000
globalDefault: false
preemptionPolicy: PreemptLowerPriority
description: "Critical production services"
---
apiVersion: scheduling.k8s.io/v1
kind: PriorityClass
metadata:
  name: batch
value: 100
globalDefault: false
preemptionPolicy: Never  # Don't preempt others
description: "Batch/background jobs"
---
# Usage
apiVersion: apps/v1
kind: Deployment
metadata:
  name: payment-service
spec:
  template:
    spec:
      priorityClassName: critical
      containers:
      - name: app
        image: payment:v1
```

### Q15: Design Horizontal Pod Autoscaler with Custom Metrics

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: myapp-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: myapp
  minReplicas: 3
  maxReplicas: 50
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
      - type: Pods
        value: 2
        periodSeconds: 60
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Pods
    pods:
      metric:
        name: http_requests_per_second
      target:
        type: AverageValue
        averageValue: "1000"
  - type: External
    external:
      metric:
        name: sqs_messages_visible
        selector:
          matchLabels:
            queue: orders
      target:
        type: Value
        value: "100"
```

---

## Key Kubectl Productivity Commands

```bash
# Quick resource overview
kubectl get all -n production
kubectl api-resources --verbs=list --namespaced -o name

# JSONPath queries
kubectl get pods -o jsonpath='{.items[*].status.containerStatuses[*].restartCount}'
kubectl get nodes -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.status.allocatable.cpu}{"\n"}{end}'

# Dry run + diff
kubectl apply -f deployment.yaml --dry-run=server
kubectl diff -f deployment.yaml

# Resource usage
kubectl top pods --sort-by=memory -n production
kubectl top nodes

# Force delete stuck pod
kubectl delete pod <pod> --grace-period=0 --force

# Copy files
kubectl cp <pod>:/path/to/file ./local-file
kubectl cp ./local-file <pod>:/path/to/file

# Port forward
kubectl port-forward svc/myapp 8080:80 -n production
kubectl port-forward pod/debug-pod 5432:5432

# Rollout management
kubectl rollout restart deployment/myapp
kubectl rollout pause deployment/myapp
kubectl rollout resume deployment/myapp
```
