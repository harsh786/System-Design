# Amazon EKS & Kubernetes - Complete Guide

## 1. Kubernetes Architecture

### Control Plane Components

The control plane manages the overall state of the cluster. In EKS, AWS manages the control plane for you (HA across 3 AZs).

#### API Server (kube-apiserver)
- **Front door** to the Kubernetes cluster
- Exposes RESTful API over HTTPS (port 6443)
- All communication goes through API Server (kubectl, kubelet, controllers)
- Handles authentication, authorization (RBAC), admission control
- Stateless - scales horizontally

#### etcd
- Distributed key-value store for all cluster data
- Stores desired state, actual state, configuration
- Uses Raft consensus protocol (requires odd number of nodes: 3, 5, 7)
- Only API Server communicates with etcd directly
- In EKS: managed by AWS, encrypted at rest, backed up automatically

#### Scheduler (kube-scheduler)
- Assigns pods to nodes based on:
  - Resource requirements (CPU, memory)
  - Node affinity/anti-affinity
  - Taints and tolerations
  - Pod affinity/anti-affinity
  - PriorityClass
- Two phases: **Filtering** (find feasible nodes) → **Scoring** (rank them)

#### Controller Manager (kube-controller-manager)
- Runs controller loops that reconcile desired state vs actual state
- Key controllers:
  - **Node Controller**: detects node failures (40s timeout, 5m eviction)
  - **Replication Controller**: maintains correct number of pods
  - **Endpoints Controller**: populates Endpoints objects (joins Services & Pods)
  - **Service Account Controller**: creates default ServiceAccount in new namespaces
  - **Deployment Controller**: manages ReplicaSets for Deployments
  - **StatefulSet Controller**: ordered pod management
  - **DaemonSet Controller**: ensures one pod per node
  - **Job Controller**: manages pod-to-completion

#### Cloud Controller Manager
- Interfaces with cloud provider APIs
- Node controller (checks if node still exists in cloud)
- Route controller (sets up routes in cloud infrastructure)
- Service controller (creates cloud load balancers)

### Worker Node Components

#### kubelet
- Agent running on every node
- Registers node with API Server
- Watches for pod assignments (via API Server)
- Manages pod lifecycle (start, stop, health checks)
- Reports node and pod status back to API Server
- Executes liveness, readiness, and startup probes

#### kube-proxy
- Network proxy on every node
- Maintains network rules for Service abstraction
- Modes:
  - **iptables** (default): O(n) rules, no load balancing intelligence
  - **IPVS**: O(1) lookup, supports round-robin, least-conn, etc.
  - **nftables**: newer, more efficient than iptables
- Handles ClusterIP, NodePort, LoadBalancer traffic routing

#### Container Runtime
- Executes containers (implements CRI - Container Runtime Interface)
- Options:
  - **containerd**: industry standard, used by EKS
  - **CRI-O**: lightweight, OCI-compliant
  - Docker (deprecated as runtime in K8s 1.24+, images still work)

### Communication Patterns

```
kubectl → API Server (HTTPS, kubeconfig auth)
API Server → etcd (gRPC)
API Server → kubelet (HTTPS, for logs/exec/port-forward)
kubelet → API Server (HTTPS, node/pod status)
Scheduler → API Server (watch for unscheduled pods)
Controllers → API Server (watch/list resources)
```

### Admission Controllers

Intercept requests to API Server after authentication/authorization but before persistence:

- **Mutating Admission**: modifies the request (e.g., inject sidecar, set defaults)
- **Validating Admission**: accepts or rejects (e.g., enforce policies)
- Order: Mutating → Object Schema Validation → Validating

Common admission controllers:
- `NamespaceLifecycle`: prevents operations in terminating namespaces
- `LimitRanger`: enforces LimitRange constraints
- `ServiceAccount`: automounts tokens
- `DefaultStorageClass`: assigns default SC to PVC
- `MutatingAdmissionWebhook` / `ValidatingAdmissionWebhook`: external webhooks

---

## 2. Core Kubernetes Objects

### Pods

Smallest deployable unit. One or more containers sharing network namespace and storage.

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: web-app
  labels:
    app: web
    tier: frontend
spec:
  restartPolicy: Always  # Always | OnFailure | Never
  initContainers:
    - name: init-db-check
      image: busybox:1.36
      command: ['sh', '-c', 'until nslookup db-service; do echo waiting; sleep 2; done']
  containers:
    - name: app
      image: nginx:1.25
      ports:
        - containerPort: 80
      resources:
        requests:
          cpu: "100m"
          memory: "128Mi"
        limits:
          cpu: "500m"
          memory: "256Mi"
      livenessProbe:
        httpGet:
          path: /healthz
          port: 80
        initialDelaySeconds: 15
        periodSeconds: 10
        failureThreshold: 3
      readinessProbe:
        httpGet:
          path: /ready
          port: 80
        initialDelaySeconds: 5
        periodSeconds: 5
      startupProbe:
        httpGet:
          path: /healthz
          port: 80
        failureThreshold: 30
        periodSeconds: 10
      lifecycle:
        postStart:
          exec:
            command: ["/bin/sh", "-c", "echo started > /tmp/started"]
        preStop:
          exec:
            command: ["/bin/sh", "-c", "nginx -s quit && sleep 5"]
      volumeMounts:
        - name: shared-data
          mountPath: /usr/share/nginx/html
    - name: sidecar-logger
      image: busybox:1.36
      command: ['sh', '-c', 'tail -f /var/log/nginx/access.log']
      volumeMounts:
        - name: shared-data
          mountPath: /var/log/nginx
  volumes:
    - name: shared-data
      emptyDir: {}
```

#### Pod Lifecycle
- **Pending**: accepted but not yet scheduled or pulling images
- **Running**: at least one container running
- **Succeeded**: all containers terminated successfully (exit 0)
- **Failed**: all containers terminated, at least one failed
- **Unknown**: cannot communicate with node

#### Multi-Container Patterns
- **Sidecar**: enhances main container (logging, monitoring, proxy)
- **Ambassador**: proxy outbound connections (local connection → ambassador handles routing)
- **Adapter**: transforms output of main container (log format normalization)
- **Init Container**: runs before app containers, must complete successfully

### ReplicaSets

```yaml
apiVersion: apps/v1
kind: ReplicaSet
metadata:
  name: web-rs
spec:
  replicas: 3
  selector:
    matchLabels:
      app: web
    matchExpressions:
      - key: tier
        operator: In
        values: [frontend]
  template:
    metadata:
      labels:
        app: web
        tier: frontend
    spec:
      containers:
        - name: nginx
          image: nginx:1.25
```

- Ensures desired number of pod replicas are running
- Uses label selectors to identify pods it manages
- Rarely created directly - use Deployments instead

### Deployments

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: web-deployment
  annotations:
    kubernetes.io/change-cause: "Update to nginx 1.25"
spec:
  replicas: 5
  revisionHistoryLimit: 10
  strategy:
    type: RollingUpdate  # or Recreate
    rollingUpdate:
      maxSurge: 25%        # max pods above desired during update
      maxUnavailable: 25%  # max pods unavailable during update
  selector:
    matchLabels:
      app: web
  template:
    metadata:
      labels:
        app: web
        version: v2
    spec:
      containers:
        - name: nginx
          image: nginx:1.25
          ports:
            - containerPort: 80
      terminationGracePeriodSeconds: 30
```

#### Deployment Strategies

**RollingUpdate** (default):
- Gradually replaces old pods with new ones
- `maxSurge`: how many extra pods allowed (% or absolute)
- `maxUnavailable`: how many pods can be down (% or absolute)

**Recreate**:
- Kills all old pods, then creates new ones
- Brief downtime, useful when you can't run two versions simultaneously

**Canary** (manual with labels):
```yaml
# Stable deployment (90% traffic)
apiVersion: apps/v1
kind: Deployment
metadata:
  name: web-stable
spec:
  replicas: 9
  selector:
    matchLabels:
      app: web
      track: stable
  template:
    metadata:
      labels:
        app: web
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
  name: web-canary
spec:
  replicas: 1
  selector:
    matchLabels:
      app: web
      track: canary
  template:
    metadata:
      labels:
        app: web
        track: canary
    spec:
      containers:
        - name: app
          image: myapp:v2
---
# Service selects both
apiVersion: v1
kind: Service
metadata:
  name: web-svc
spec:
  selector:
    app: web  # matches both stable and canary
  ports:
    - port: 80
```

#### Rollback
```bash
kubectl rollout history deployment/web-deployment
kubectl rollout undo deployment/web-deployment
kubectl rollout undo deployment/web-deployment --to-revision=2
kubectl rollout status deployment/web-deployment
kubectl rollout pause deployment/web-deployment
kubectl rollout resume deployment/web-deployment
```

### StatefulSets

```yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: postgres
spec:
  serviceName: postgres-headless  # required headless service
  replicas: 3
  podManagementPolicy: OrderedReady  # or Parallel
  updateStrategy:
    type: RollingUpdate
    rollingUpdate:
      partition: 0  # only update pods with ordinal >= partition
  selector:
    matchLabels:
      app: postgres
  template:
    metadata:
      labels:
        app: postgres
    spec:
      containers:
        - name: postgres
          image: postgres:15
          ports:
            - containerPort: 5432
          volumeMounts:
            - name: data
              mountPath: /var/lib/postgresql/data
          env:
            - name: POSTGRES_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: postgres-secret
                  key: password
  volumeClaimTemplates:
    - metadata:
        name: data
      spec:
        accessModes: ["ReadWriteOnce"]
        storageClassName: gp3
        resources:
          requests:
            storage: 20Gi
---
apiVersion: v1
kind: Service
metadata:
  name: postgres-headless
spec:
  clusterIP: None  # headless
  selector:
    app: postgres
  ports:
    - port: 5432
```

Key properties:
- **Ordered deployment**: pods created sequentially (postgres-0, postgres-1, postgres-2)
- **Stable network identity**: `postgres-0.postgres-headless.namespace.svc.cluster.local`
- **Persistent storage**: each pod gets its own PVC (not shared)
- **Ordered termination**: deleted in reverse order
- **Ordered rolling updates**: updated from highest ordinal to lowest

### DaemonSets

```yaml
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: fluentbit
  namespace: logging
spec:
  selector:
    matchLabels:
      app: fluentbit
  updateStrategy:
    type: RollingUpdate
    rollingUpdate:
      maxUnavailable: 1
  template:
    metadata:
      labels:
        app: fluentbit
    spec:
      tolerations:
        - operator: Exists  # tolerate all taints (run on all nodes)
      containers:
        - name: fluentbit
          image: fluent/fluent-bit:2.1
          resources:
            requests:
              cpu: 50m
              memory: 64Mi
            limits:
              cpu: 200m
              memory: 128Mi
          volumeMounts:
            - name: varlog
              mountPath: /var/log
            - name: containers
              mountPath: /var/lib/docker/containers
              readOnly: true
      volumes:
        - name: varlog
          hostPath:
            path: /var/log
        - name: containers
          hostPath:
            path: /var/lib/docker/containers
```

Use cases: log collectors, monitoring agents, kube-proxy, CNI plugins, storage daemons

### Jobs

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: data-migration
spec:
  completions: 5       # total successful completions needed
  parallelism: 3       # max pods running concurrently
  backoffLimit: 4      # retries before marking failed
  activeDeadlineSeconds: 600  # timeout for entire job
  ttlSecondsAfterFinished: 300  # cleanup after completion
  template:
    spec:
      restartPolicy: OnFailure  # or Never
      containers:
        - name: migrate
          image: myapp/migrate:v1
          command: ["python", "migrate.py"]
```

### CronJobs

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: db-backup
spec:
  schedule: "0 2 * * *"  # 2 AM daily
  concurrencyPolicy: Forbid  # Allow | Forbid | Replace
  successfulJobsHistoryLimit: 3
  failedJobsHistoryLimit: 3
  startingDeadlineSeconds: 200
  jobTemplate:
    spec:
      template:
        spec:
          restartPolicy: OnFailure
          containers:
            - name: backup
              image: myapp/backup:v1
              command: ["./backup.sh"]
```

---

## 3. Kubernetes Networking

### Pod-to-Pod Communication

Kubernetes networking model rules:
1. Every pod gets a unique IP address
2. Pods can communicate with any other pod without NAT
3. Agents on a node can communicate with all pods on that node

#### CNI Plugins

**AWS VPC CNI** (EKS default):
- Assigns real VPC IPs to pods (no overlay)
- Pods are first-class VPC citizens
- Each ENI has secondary IPs assigned to pods
- Limit: max pods per node depends on instance type (ENIs × IPs per ENI)
- Prefix delegation mode for higher pod density

**Calico**:
- Overlay (VXLAN/IPIP) or native routing
- Powerful NetworkPolicy enforcement
- BGP peering support

**Cilium**:
- eBPF-based (kernel-level, bypasses iptables)
- Superior performance and observability
- L7 network policies
- Transparent encryption (WireGuard)

### Services

#### ClusterIP (default)
```yaml
apiVersion: v1
kind: Service
metadata:
  name: backend-svc
spec:
  type: ClusterIP
  selector:
    app: backend
  ports:
    - port: 80        # service port
      targetPort: 8080 # container port
      protocol: TCP
```
- Internal-only virtual IP
- Accessible within cluster via DNS: `backend-svc.namespace.svc.cluster.local`

#### NodePort
```yaml
apiVersion: v1
kind: Service
metadata:
  name: web-nodeport
spec:
  type: NodePort
  selector:
    app: web
  ports:
    - port: 80
      targetPort: 8080
      nodePort: 30080  # 30000-32767, optional (auto-assigned if omitted)
```
- Exposes service on each node's IP at a static port
- Accessible externally via `<NodeIP>:<NodePort>`

#### LoadBalancer
```yaml
apiVersion: v1
kind: Service
metadata:
  name: web-lb
  annotations:
    service.beta.kubernetes.io/aws-load-balancer-type: "external"
    service.beta.kubernetes.io/aws-load-balancer-nlb-target-type: "ip"
    service.beta.kubernetes.io/aws-load-balancer-scheme: "internet-facing"
spec:
  type: LoadBalancer
  selector:
    app: web
  ports:
    - port: 443
      targetPort: 8080
```
- Provisions a cloud load balancer (NLB on EKS with AWS LB Controller)
- Each LoadBalancer service creates a separate LB (cost consideration)

#### ExternalName
```yaml
apiVersion: v1
kind: Service
metadata:
  name: external-db
spec:
  type: ExternalName
  externalName: mydb.abc123.us-east-1.rds.amazonaws.com
```
- Returns CNAME record, no proxying

#### Headless Service
```yaml
apiVersion: v1
kind: Service
metadata:
  name: db-headless
spec:
  clusterIP: None
  selector:
    app: database
  ports:
    - port: 5432
```
- No cluster IP allocated
- DNS returns individual pod IPs (A records)
- Used with StatefulSets for stable DNS per pod

### Ingress

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: web-ingress
  annotations:
    kubernetes.io/ingress.class: alb
    alb.ingress.kubernetes.io/scheme: internet-facing
    alb.ingress.kubernetes.io/target-type: ip
    alb.ingress.kubernetes.io/certificate-arn: arn:aws:acm:us-east-1:123456:certificate/abc
    alb.ingress.kubernetes.io/listen-ports: '[{"HTTPS":443}]'
    alb.ingress.kubernetes.io/ssl-redirect: "443"
    alb.ingress.kubernetes.io/healthcheck-path: /healthz
spec:
  ingressClassName: alb
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
    - host: admin.example.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: admin-service
                port:
                  number: 80
```

Ingress Controllers:
- **AWS Load Balancer Controller**: creates ALB for Ingress, NLB for LoadBalancer Services
- **NGINX Ingress Controller**: single NLB → NGINX pods → backend routing
- **Traefik**, **HAProxy**, **Istio Gateway**

### Network Policies

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: api-netpol
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
        - podSelector:
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
    - to:  # allow DNS
        - namespaceSelector: {}
          podSelector:
            matchLabels:
              k8s-app: kube-dns
      ports:
        - protocol: UDP
          port: 53
```

- Default: all traffic allowed (no policies = allow all)
- Once any NetworkPolicy selects a pod, all non-matching traffic is denied
- Requires CNI that supports NetworkPolicy (Calico, Cilium - VPC CNI alone does NOT enforce)

### DNS (CoreDNS)

Resolution patterns:
- Service: `<service>.<namespace>.svc.cluster.local`
- Pod: `<pod-ip-dashed>.<namespace>.pod.cluster.local`
- StatefulSet pod: `<pod-name>.<headless-service>.<namespace>.svc.cluster.local`

```yaml
# CoreDNS ConfigMap customization
apiVersion: v1
kind: ConfigMap
metadata:
  name: coredns
  namespace: kube-system
data:
  Corefile: |
    .:53 {
        errors
        health
        kubernetes cluster.local in-addr.arpa ip6.arpa {
            pods insecure
            fallthrough in-addr.arpa ip6.arpa
        }
        forward . /etc/resolv.conf
        cache 30
        loop
        reload
        loadbalance
    }
```

### Service Mesh

#### Istio
- Envoy sidecar proxy injected into every pod
- Traffic management, security (mTLS), observability

```yaml
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: reviews-route
spec:
  hosts:
    - reviews
  http:
    - match:
        - headers:
            end-user:
              exact: jason
      route:
        - destination:
            host: reviews
            subset: v2
    - route:
        - destination:
            host: reviews
            subset: v1
          weight: 90
        - destination:
            host: reviews
            subset: v2
          weight: 10
---
apiVersion: networking.istio.io/v1beta1
kind: DestinationRule
metadata:
  name: reviews-dr
spec:
  host: reviews
  trafficPolicy:
    connectionPool:
      tcp:
        maxConnections: 100
    outlierDetection:
      consecutive5xxErrors: 5
      interval: 30s
      baseEjectionTime: 60s
  subsets:
    - name: v1
      labels:
        version: v1
    - name: v2
      labels:
        version: v2
```

---

## 4. Kubernetes Storage

### Volume Types

#### emptyDir
```yaml
volumes:
  - name: cache
    emptyDir:
      sizeLimit: 500Mi
      medium: Memory  # tmpfs (RAM-backed)
```
- Created when pod starts, deleted when pod dies
- Shared between containers in same pod
- Use cases: scratch space, cache, sidecar communication

#### hostPath
```yaml
volumes:
  - name: docker-sock
    hostPath:
      path: /var/run/docker.sock
      type: Socket
```
- Mounts file/directory from host node
- Dangerous in multi-node (pod sees different data on different nodes)
- Use cases: DaemonSets accessing node-level data

### PersistentVolume & PersistentVolumeClaim

```yaml
apiVersion: v1
kind: PersistentVolume
metadata:
  name: ebs-pv
spec:
  capacity:
    storage: 50Gi
  accessModes:
    - ReadWriteOnce  # RWO | ROX | RWX
  persistentVolumeReclaimPolicy: Retain  # Retain | Delete | Recycle
  storageClassName: gp3
  csi:
    driver: ebs.csi.aws.com
    volumeHandle: vol-0abc123def456
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: app-data
spec:
  accessModes:
    - ReadWriteOnce
  storageClassName: gp3
  resources:
    requests:
      storage: 50Gi
```

### StorageClasses

```yaml
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: gp3
  annotations:
    storageclass.kubernetes.io/is-default-class: "true"
provisioner: ebs.csi.aws.com
parameters:
  type: gp3
  iops: "3000"
  throughput: "125"
  encrypted: "true"
  kmsKeyId: arn:aws:kms:us-east-1:123456:key/abc-123
reclaimPolicy: Delete
volumeBindingMode: WaitForFirstConsumer  # important for topology-aware
allowVolumeExpansion: true
```

- **Immediate**: PV provisioned as soon as PVC is created
- **WaitForFirstConsumer**: waits until pod using PVC is scheduled (ensures same AZ)

### CSI Drivers (EKS)

| Driver | Storage | Access Mode | Use Case |
|--------|---------|-------------|----------|
| EBS CSI | Block | RWO | Databases, single-pod workloads |
| EFS CSI | File (NFS) | RWX | Shared data across pods/nodes |
| FSx for Lustre CSI | File | RWX | HPC, ML training |

```yaml
# EFS StorageClass
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: efs-sc
provisioner: efs.csi.aws.com
parameters:
  provisioningMode: efs-ap
  fileSystemId: fs-0abc123
  directoryPerms: "700"
  basePath: "/dynamic_provisioning"
```

---

## 5. Configuration & Secrets

### ConfigMaps

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: app-config
data:
  APP_ENV: production
  APP_LOG_LEVEL: info
  nginx.conf: |
    server {
      listen 80;
      location / {
        proxy_pass http://backend:8080;
      }
    }
```

Usage in pods:
```yaml
spec:
  containers:
    - name: app
      env:
        # Single value
        - name: APP_ENV
          valueFrom:
            configMapKeyRef:
              name: app-config
              key: APP_ENV
      envFrom:
        # All keys as env vars
        - configMapRef:
            name: app-config
      volumeMounts:
        - name: config-vol
          mountPath: /etc/nginx/conf.d
  volumes:
    - name: config-vol
      configMap:
        name: app-config
        items:
          - key: nginx.conf
            path: default.conf
```

Hot-reload: volume-mounted ConfigMaps update automatically (~1 min), but env vars do NOT update without pod restart.

### Secrets

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: db-credentials
type: Opaque
data:
  username: YWRtaW4=      # base64 encoded (NOT encrypted!)
  password: cEBzc3cwcmQ=
---
# TLS secret
apiVersion: v1
kind: Secret
metadata:
  name: tls-secret
type: kubernetes.io/tls
data:
  tls.crt: <base64-cert>
  tls.key: <base64-key>
---
# Docker registry
apiVersion: v1
kind: Secret
metadata:
  name: regcred
type: kubernetes.io/dockerconfigjson
data:
  .dockerconfigjson: <base64-docker-config>
```

**Important**: base64 is encoding, NOT encryption. Secrets are stored in etcd in plaintext by default.

#### Encryption at Rest
```yaml
# EncryptionConfiguration
apiVersion: apiserver.config.k8s.io/v1
kind: EncryptionConfiguration
resources:
  - resources:
      - secrets
    providers:
      - aescbc:
          keys:
            - name: key1
              secret: <base64-key>
      - identity: {}
```

In EKS: enable envelope encryption with KMS:
```bash
aws eks create-cluster --encryption-config '[{"resources":["secrets"],"provider":{"keyArn":"arn:aws:kms:..."}}]'
```

#### External Secrets Operator
```yaml
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: app-secrets
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: aws-secrets-manager
    kind: ClusterSecretStore
  target:
    name: app-secrets
  data:
    - secretKey: db-password
      remoteRef:
        key: production/database
        property: password
```

---

## 6. Scheduling & Resource Management

### Resource Requests and Limits

```yaml
resources:
  requests:
    cpu: "250m"      # 0.25 CPU cores - used for SCHEDULING
    memory: "256Mi"  # used for SCHEDULING
  limits:
    cpu: "1000m"     # 1 CPU core - ENFORCED (throttled)
    memory: "512Mi"  # ENFORCED (OOMKilled if exceeded)
```

- **Requests**: guaranteed minimum, scheduler uses this to place pods
- **Limits**: maximum allowed; CPU = throttled, Memory = OOMKilled

### QoS Classes

| Class | Condition | Eviction Priority |
|-------|-----------|-------------------|
| **Guaranteed** | requests == limits for all containers | Last to be evicted |
| **Burstable** | At least one request/limit set, not equal | Middle |
| **BestEffort** | No requests or limits set | First to be evicted |

### LimitRange

```yaml
apiVersion: v1
kind: LimitRange
metadata:
  name: default-limits
  namespace: development
spec:
  limits:
    - type: Container
      default:
        cpu: "500m"
        memory: "256Mi"
      defaultRequest:
        cpu: "100m"
        memory: "128Mi"
      max:
        cpu: "2"
        memory: "2Gi"
      min:
        cpu: "50m"
        memory: "64Mi"
    - type: Pod
      max:
        cpu: "4"
        memory: "8Gi"
```

### ResourceQuota

```yaml
apiVersion: v1
kind: ResourceQuota
metadata:
  name: team-quota
  namespace: team-a
spec:
  hard:
    requests.cpu: "20"
    requests.memory: "40Gi"
    limits.cpu: "40"
    limits.memory: "80Gi"
    pods: "50"
    services: "10"
    persistentvolumeclaims: "20"
    count/deployments.apps: "10"
```

### Node Affinity

```yaml
spec:
  affinity:
    nodeAffinity:
      requiredDuringSchedulingIgnoredDuringExecution:
        nodeSelectorTerms:
          - matchExpressions:
              - key: topology.kubernetes.io/zone
                operator: In
                values: [us-east-1a, us-east-1b]
      preferredDuringSchedulingIgnoredDuringExecution:
        - weight: 80
          preference:
            matchExpressions:
              - key: node.kubernetes.io/instance-type
                operator: In
                values: [m5.xlarge, m5.2xlarge]
```

### Pod Affinity / Anti-Affinity

```yaml
spec:
  affinity:
    podAffinity:
      requiredDuringSchedulingIgnoredDuringExecution:
        - labelSelector:
            matchLabels:
              app: cache
          topologyKey: topology.kubernetes.io/zone
    podAntiAffinity:
      preferredDuringSchedulingIgnoredDuringExecution:
        - weight: 100
          podAffinityTerm:
            labelSelector:
              matchLabels:
                app: web
            topologyKey: kubernetes.io/hostname
```

### Taints and Tolerations

```bash
# Taint a node
kubectl taint nodes node1 dedicated=gpu:NoSchedule
kubectl taint nodes node1 maintenance=true:NoExecute
```

```yaml
spec:
  tolerations:
    - key: "dedicated"
      operator: "Equal"
      value: "gpu"
      effect: "NoSchedule"
    - key: "maintenance"
      operator: "Exists"
      effect: "NoExecute"
      tolerationSeconds: 3600  # evict after 1 hour
```

Effects:
- **NoSchedule**: new pods won't schedule unless they tolerate
- **PreferNoSchedule**: soft version, scheduler tries to avoid
- **NoExecute**: evicts existing pods that don't tolerate

### PriorityClasses

```yaml
apiVersion: scheduling.k8s.io/v1
kind: PriorityClass
metadata:
  name: critical
value: 1000000
globalDefault: false
preemptionPolicy: PreemptLowerPriority
description: "Critical production workloads"
```

### Pod Disruption Budgets

```yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: web-pdb
spec:
  minAvailable: 2    # or use maxUnavailable: 1
  selector:
    matchLabels:
      app: web
```

- Protects against **voluntary** disruptions (node drain, cluster upgrade)
- Does NOT protect against involuntary (node crash, OOM)

---

## 7. Autoscaling

### Horizontal Pod Autoscaler (HPA)

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: web-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: web
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
          type: AverageValue
          averageValue: 500Mi
    - type: Pods
      pods:
        metric:
          name: requests_per_second
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
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 60
      policies:
        - type: Percent
          value: 100
          periodSeconds: 60
        - type: Pods
          value: 4
          periodSeconds: 60
      selectPolicy: Max
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
        - type: Percent
          value: 10
          periodSeconds: 60
```

### Vertical Pod Autoscaler (VPA)

```yaml
apiVersion: autoscaling.k8s.io/v1
kind: VerticalPodAutoscaler
metadata:
  name: web-vpa
spec:
  targetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: web
  updatePolicy:
    updateMode: "Auto"  # Off | Initial | Auto
  resourcePolicy:
    containerPolicies:
      - containerName: app
        minAllowed:
          cpu: "100m"
          memory: "128Mi"
        maxAllowed:
          cpu: "4"
          memory: "8Gi"
        controlledResources: ["cpu", "memory"]
```

Modes:
- **Off**: only provides recommendations
- **Initial**: sets resources only at pod creation
- **Auto**: evicts and recreates pods with new resources

**Note**: Don't use HPA and VPA on the same metric (e.g., both on CPU).

### Cluster Autoscaler

```yaml
# Deployment configuration flags
--node-group-auto-discovery=asg:tag=k8s.io/cluster-autoscaler/enabled,k8s.io/cluster-autoscaler/my-cluster
--balance-similar-node-groups
--skip-nodes-with-system-pods=false
--scale-down-delay-after-add=10m
--scale-down-unneeded-time=10m
--scale-down-utilization-threshold=0.5
--expander=least-waste  # random | most-pods | least-waste | priority
```

### Karpenter

```yaml
apiVersion: karpenter.sh/v1beta1
kind: NodePool
metadata:
  name: general
spec:
  template:
    spec:
      nodeClassRef:
        name: default
      requirements:
        - key: karpenter.sh/capacity-type
          operator: In
          values: ["spot", "on-demand"]
        - key: kubernetes.io/arch
          operator: In
          values: ["amd64"]
        - key: karpenter.k8s.aws/instance-category
          operator: In
          values: ["c", "m", "r"]
        - key: karpenter.k8s.aws/instance-generation
          operator: Gt
          values: ["4"]
  limits:
    cpu: "1000"
    memory: "1000Gi"
  disruption:
    consolidationPolicy: WhenUnderutilized
    expireAfter: 720h
---
apiVersion: karpenter.k8s.aws/v1beta1
kind: EC2NodeClass
metadata:
  name: default
spec:
  amiFamily: AL2
  subnetSelectorTerms:
    - tags:
        karpenter.sh/discovery: my-cluster
  securityGroupSelectorTerms:
    - tags:
        karpenter.sh/discovery: my-cluster
  instanceProfile: KarpenterNodeInstanceProfile
  blockDeviceMappings:
    - deviceName: /dev/xvda
      ebs:
        volumeSize: 100Gi
        volumeType: gp3
```

Karpenter advantages over Cluster Autoscaler:
- Provisions nodes in seconds (vs minutes)
- Right-sizes instances (doesn't need pre-defined node groups)
- Consolidation: replaces underutilized nodes
- Drift detection: replaces nodes when AMI/config changes
- Native spot instance handling with interruption

### KEDA (Kubernetes Event-Driven Autoscaling)

```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: order-processor
spec:
  scaleTargetRef:
    name: order-processor
  minReplicaCount: 0   # scale to zero!
  maxReplicaCount: 100
  pollingInterval: 15
  cooldownPeriod: 300
  triggers:
    - type: aws-sqs-queue
      metadata:
        queueURL: https://sqs.us-east-1.amazonaws.com/123456/orders
        queueLength: "5"
        awsRegion: us-east-1
        identityOwner: operator
    - type: prometheus
      metadata:
        serverAddress: http://prometheus:9090
        metricName: http_requests_total
        query: sum(rate(http_requests_total{service="api"}[2m]))
        threshold: "100"
    - type: cron
      metadata:
        timezone: America/New_York
        start: 0 8 * * 1-5
        end: 0 18 * * 1-5
        desiredReplicas: "10"
```

---

## 8. EKS Specific Features

### Managed Control Plane

- AWS manages: API Server, etcd, scheduler, controller manager
- HA across 3 AZs automatically
- Automatic version upgrades (minor version support ~14 months)
- API server endpoint: public, private, or both
- Envelope encryption for secrets with KMS
- Control plane logging to CloudWatch (API, audit, authenticator, controller manager, scheduler)

### Node Groups

#### Managed Node Groups
```bash
aws eks create-nodegroup \
  --cluster-name my-cluster \
  --nodegroup-name workers \
  --node-role arn:aws:iam::123456:role/EKSNodeRole \
  --subnets subnet-abc subnet-def \
  --instance-types m5.xlarge m5.2xlarge \
  --scaling-config minSize=2,maxSize=20,desiredSize=5 \
  --capacity-type ON_DEMAND \
  --ami-type AL2_x86_64 \
  --update-config maxUnavailable=1
```
- AWS handles AMI updates, node draining, lifecycle management
- Supports custom launch templates

#### Fargate Profiles
```yaml
# Fargate Profile
apiVersion: eks.amazonaws.com/v1
kind: FargateProfile
metadata:
  name: app-fargate
spec:
  selectors:
    - namespace: production
      labels:
        compute: fargate
    - namespace: batch
```
- Serverless: no nodes to manage
- Each pod runs in its own micro-VM (Firecracker)
- Limitations: no DaemonSets, no GPU, no privileged containers, max 4 vCPU / 30GB per pod
- Higher per-pod cost, but no idle capacity waste

### IRSA (IAM Roles for Service Accounts)

```yaml
# 1. Create IAM role with trust policy
# Trust policy allows the OIDC provider to assume the role
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {
      "Federated": "arn:aws:iam::123456:oidc-provider/oidc.eks.us-east-1.amazonaws.com/id/ABCDEF"
    },
    "Action": "sts:AssumeRoleWithWebIdentity",
    "Condition": {
      "StringEquals": {
        "oidc.eks.us-east-1.amazonaws.com/id/ABCDEF:sub": "system:serviceaccount:production:app-sa",
        "oidc.eks.us-east-1.amazonaws.com/id/ABCDEF:aud": "sts.amazonaws.com"
      }
    }
  }]
}
---
# 2. Annotate ServiceAccount
apiVersion: v1
kind: ServiceAccount
metadata:
  name: app-sa
  namespace: production
  annotations:
    eks.amazonaws.com/role-arn: arn:aws:iam::123456:role/AppS3AccessRole
```

How it works: Pod gets a projected service account token (JWT) → AWS SDK calls STS AssumeRoleWithWebIdentity → gets temporary credentials → accesses AWS services.

### EKS Pod Identity (newer, simpler)

```bash
# Create pod identity association
aws eks create-pod-identity-association \
  --cluster-name my-cluster \
  --namespace production \
  --service-account app-sa \
  --role-arn arn:aws:iam::123456:role/AppRole
```

- No OIDC provider setup needed
- No trust policy per service account
- Managed by EKS Pod Identity Agent (DaemonSet)
- Simpler than IRSA, recommended for new setups

### AWS Load Balancer Controller

```bash
# Install via Helm
helm install aws-load-balancer-controller \
  eks/aws-load-balancer-controller \
  -n kube-system \
  --set clusterName=my-cluster \
  --set serviceAccount.create=false \
  --set serviceAccount.name=aws-lb-controller-sa
```

- **Ingress → ALB**: one ALB shared across multiple Ingress resources (IngressGroup)
- **Service type LoadBalancer → NLB**: L4 load balancing
- Supports target type `ip` (direct to pod) or `instance` (to NodePort)

### ExternalDNS

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: external-dns
spec:
  template:
    spec:
      containers:
        - name: external-dns
          image: registry.k8s.io/external-dns/external-dns:v0.14
          args:
            - --source=service
            - --source=ingress
            - --domain-filter=example.com
            - --provider=aws
            - --aws-zone-type=public
            - --registry=txt
            - --txt-owner-id=my-cluster
```

Automatically creates Route 53 records from Ingress/Service annotations:
```yaml
metadata:
  annotations:
    external-dns.alpha.kubernetes.io/hostname: app.example.com
    external-dns.alpha.kubernetes.io/ttl: "300"
```

### EKS Blueprints

Terraform/CDK patterns for opinionated cluster setup:
- VPC, EKS cluster, managed node groups
- Add-ons: metrics-server, cluster-autoscaler, AWS LB controller, ExternalDNS, ArgoCD
- Teams/tenants with namespace isolation and RBAC

### EKS Anywhere

- Run EKS on your own infrastructure (VMware vSphere, bare metal, Nutanix, Snow)
- Same K8s distribution as EKS in AWS
- Cluster lifecycle management via `eksctl anywhere`
- Optional EKS Connector for visibility in AWS console

---

## 9. Security

### RBAC

```yaml
# Role (namespace-scoped)
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: pod-reader
  namespace: production
rules:
  - apiGroups: [""]
    resources: ["pods", "pods/log"]
    verbs: ["get", "list", "watch"]
  - apiGroups: ["apps"]
    resources: ["deployments"]
    verbs: ["get", "list"]
---
# ClusterRole (cluster-wide)
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: node-viewer
rules:
  - apiGroups: [""]
    resources: ["nodes"]
    verbs: ["get", "list", "watch"]
  - apiGroups: ["metrics.k8s.io"]
    resources: ["nodes", "pods"]
    verbs: ["get", "list"]
---
# RoleBinding
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: dev-pod-reader
  namespace: production
subjects:
  - kind: Group
    name: dev-team
    apiGroup: rbac.authorization.k8s.io
  - kind: ServiceAccount
    name: ci-bot
    namespace: ci-cd
roleRef:
  kind: Role
  name: pod-reader
  apiGroup: rbac.authorization.k8s.io
---
# ClusterRoleBinding
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: node-viewer-binding
subjects:
  - kind: Group
    name: platform-team
    apiGroup: rbac.authorization.k8s.io
roleRef:
  kind: ClusterRole
  name: node-viewer
  apiGroup: rbac.authorization.k8s.io
```

Verbs: `get`, `list`, `watch`, `create`, `update`, `patch`, `delete`, `deletecollection`

### EKS Authentication (aws-auth ConfigMap)

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: aws-auth
  namespace: kube-system
data:
  mapRoles: |
    - rolearn: arn:aws:iam::123456:role/EKSNodeRole
      username: system:node:{{EC2PrivateDNSName}}
      groups:
        - system:bootstrappers
        - system:nodes
    - rolearn: arn:aws:iam::123456:role/DevTeamRole
      username: dev-user
      groups:
        - dev-team
  mapUsers: |
    - userarn: arn:aws:iam::123456:user/admin
      username: admin
      groups:
        - system:masters
```

### Pod Security Standards & Admission

```yaml
# Namespace labels for Pod Security Admission
apiVersion: v1
kind: Namespace
metadata:
  name: production
  labels:
    pod-security.kubernetes.io/enforce: restricted
    pod-security.kubernetes.io/audit: restricted
    pod-security.kubernetes.io/warn: restricted
```

Levels:
- **Privileged**: unrestricted (system workloads)
- **Baseline**: prevents known privilege escalations
- **Restricted**: heavily restricted (no root, no hostPath, read-only root filesystem)

### OPA Gatekeeper

```yaml
# Constraint Template
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
# Constraint
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
    labels: ["team", "cost-center"]
```

### Kyverno (alternative to OPA)

```yaml
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: disallow-latest-tag
spec:
  validationFailureAction: Enforce
  rules:
    - name: require-image-tag
      match:
        any:
          - resources:
              kinds: ["Pod"]
      validate:
        message: "Image tag 'latest' is not allowed"
        pattern:
          spec:
            containers:
              - image: "!*:latest"
```

---

## 10. Observability

### Metrics

```yaml
# metrics-server (required for kubectl top, HPA)
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml

# Prometheus stack via Helm
helm install prometheus prometheus-community/kube-prometheus-stack \
  --namespace monitoring --create-namespace \
  --set grafana.enabled=true
```

#### CloudWatch Container Insights
```bash
# Install CloudWatch agent + Fluent Bit
aws eks create-addon --cluster-name my-cluster --addon-name amazon-cloudwatch-observability
```

Provides: CPU/memory/network per pod/node/cluster, container restart counts, cluster-level dashboards.

### Logging

```yaml
# Fluent Bit DaemonSet config
apiVersion: v1
kind: ConfigMap
metadata:
  name: fluent-bit-config
  namespace: amazon-cloudwatch
data:
  fluent-bit.conf: |
    [SERVICE]
        Flush         5
        Log_Level     info
        Parsers_File  parsers.conf

    [INPUT]
        Name              tail
        Tag               kube.*
        Path              /var/log/containers/*.log
        Parser            docker
        DB                /var/log/flb_kube.db
        Mem_Buf_Limit     50MB
        Refresh_Interval  10

    [FILTER]
        Name                kubernetes
        Match               kube.*
        Kube_URL            https://kubernetes.default.svc:443
        Merge_Log           On
        K8S-Logging.Parser  On

    [OUTPUT]
        Name                cloudwatch_logs
        Match               kube.*
        region              us-east-1
        log_group_name      /eks/my-cluster/containers
        log_stream_prefix   fluentbit-
        auto_create_group   true
```

### Tracing

```yaml
# OpenTelemetry Collector (ADOT)
apiVersion: opentelemetry.io/v1alpha1
kind: OpenTelemetryCollector
metadata:
  name: adot
spec:
  mode: daemonset
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
        timeout: 30s
    exporters:
      awsxray:
        region: us-east-1
      awsemf:
        region: us-east-1
    service:
      pipelines:
        traces:
          receivers: [otlp]
          processors: [batch]
          exporters: [awsxray]
        metrics:
          receivers: [otlp]
          processors: [batch]
          exporters: [awsemf]
```

---

## 11. Helm & GitOps

### Helm

Chart structure:
```
mychart/
├── Chart.yaml          # metadata (name, version, appVersion)
├── values.yaml         # default configuration values
├── charts/             # dependencies
├── templates/
│   ├── deployment.yaml
│   ├── service.yaml
│   ├── ingress.yaml
│   ├── configmap.yaml
│   ├── _helpers.tpl    # template helpers
│   ├── NOTES.txt       # post-install notes
│   └── tests/
│       └── test-connection.yaml
└── .helmignore
```

```yaml
# Chart.yaml
apiVersion: v2
name: myapp
version: 1.2.0
appVersion: "3.5.1"
dependencies:
  - name: postgresql
    version: "12.x.x"
    repository: https://charts.bitnami.com/bitnami
    condition: postgresql.enabled
```

```yaml
# values.yaml
replicaCount: 3
image:
  repository: myapp
  tag: "3.5.1"
  pullPolicy: IfNotPresent
service:
  type: ClusterIP
  port: 80
ingress:
  enabled: true
  className: alb
  hosts:
    - host: app.example.com
      paths:
        - path: /
          pathType: Prefix
resources:
  requests:
    cpu: 100m
    memory: 128Mi
  limits:
    cpu: 500m
    memory: 256Mi
autoscaling:
  enabled: true
  minReplicas: 3
  maxReplicas: 20
  targetCPUUtilization: 70
```

```bash
helm repo add bitnami https://charts.bitnami.com/bitnami
helm install my-release ./mychart -f custom-values.yaml -n production
helm upgrade my-release ./mychart --set image.tag=3.6.0
helm rollback my-release 1
helm list -n production
helm history my-release
```

### ArgoCD

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: myapp
  namespace: argocd
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
      prune: true       # delete resources removed from git
      selfHeal: true    # revert manual changes
    syncOptions:
      - CreateNamespace=true
      - ApplyOutOfSyncOnly=true
    retry:
      limit: 5
      backoff:
        duration: 5s
        factor: 2
        maxDuration: 3m
```

**App of Apps** pattern:
```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: apps
  namespace: argocd
spec:
  source:
    repoURL: https://github.com/org/k8s-manifests.git
    path: argocd-apps  # contains Application YAMLs for each app
  destination:
    server: https://kubernetes.default.svc
    namespace: argocd
  syncPolicy:
    automated:
      selfHeal: true
```

### Flux

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
---
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: app
  namespace: flux-system
spec:
  interval: 5m
  sourceRef:
    kind: GitRepository
    name: app-repo
  path: ./apps/production
  prune: true
  healthChecks:
    - apiVersion: apps/v1
      kind: Deployment
      name: myapp
      namespace: production
---
apiVersion: helm.toolkit.fluxcd.io/v2beta1
kind: HelmRelease
metadata:
  name: nginx
  namespace: production
spec:
  interval: 10m
  chart:
    spec:
      chart: nginx
      version: ">=1.0.0"
      sourceRef:
        kind: HelmRepository
        name: bitnami
  values:
    replicaCount: 3
```

---

## 12. Scenario-Based Interview Questions

### Q1: Pod in CrashLoopBackOff - Debugging Steps

**Answer:**

1. **Check pod events**: `kubectl describe pod <pod-name>` - look at Events section for OOMKilled, image pull errors, probe failures
2. **Check logs**: `kubectl logs <pod-name> --previous` (previous container instance)
3. **Common causes**:
   - Application crash (segfault, unhandled exception) → check logs
   - OOMKilled → increase memory limits or fix memory leak
   - Liveness probe failing → incorrect path/port, probe too aggressive (low initialDelaySeconds)
   - Missing ConfigMap/Secret/Volume → check mounts exist
   - Permission issues → check securityContext, file permissions
   - Dependency not ready → app can't connect to DB/cache at startup
4. **Debug interactively**: `kubectl exec -it <pod> -- /bin/sh` (if container starts briefly)
5. **Override entrypoint**: Create debug pod with `command: ["sleep", "infinity"]` to inspect filesystem
6. **Check resource limits**: `kubectl top pod` - is it hitting CPU throttle or memory limit?

### Q2: Zero-Downtime Deployments

**Answer:**

1. **Rolling update strategy** with `maxUnavailable: 0` (never reduce below desired)
2. **Readiness probes**: new pods only receive traffic when ready
3. **preStop hook**: `sleep 5` to allow in-flight requests to complete and load balancer deregistration
4. **terminationGracePeriodSeconds**: set high enough for graceful shutdown
5. **PodDisruptionBudget**: protect minimum available during voluntary disruptions
6. **Connection draining**: configure load balancer deregistration delay
7. **Anti-affinity**: spread pods across nodes/AZs

```yaml
spec:
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 25%
      maxUnavailable: 0
  template:
    spec:
      terminationGracePeriodSeconds: 60
      containers:
        - name: app
          readinessProbe:
            httpGet:
              path: /ready
              port: 8080
            initialDelaySeconds: 10
            periodSeconds: 5
          lifecycle:
            preStop:
              exec:
                command: ["sh", "-c", "sleep 10"]
```

### Q3: Design Multi-Tenant K8s Cluster

**Answer:**

1. **Namespace isolation**: one namespace per tenant
2. **RBAC**: Role/RoleBinding per tenant namespace, no ClusterRole access
3. **ResourceQuota**: limit CPU/memory/pods per namespace
4. **LimitRange**: set default requests/limits
5. **NetworkPolicy**: deny all ingress/egress by default, allowlist specific communication
6. **Pod Security Admission**: enforce `restricted` level
7. **Separate node pools**: use taints/nodeSelector for tenant-specific nodes (noisy neighbor)
8. **Separate Ingress**: use IngressClass or host-based routing
9. **Resource separation**: tenant-specific ServiceAccounts, Secrets, ConfigMaps
10. **Cost allocation**: labels for chargeback, Kubecost

### Q4: Cluster Running Out of Resources

**Answer:**

1. **Immediate**: Check with `kubectl top nodes` and `kubectl describe nodes` for allocatable vs allocated
2. **Scale out**: Cluster Autoscaler/Karpenter should add nodes automatically if configured
3. **If autoscaler stuck**: check ASG max size, IAM permissions, availability of instance types in AZ
4. **Find resource hogs**: `kubectl top pods -A --sort-by=memory`
5. **Quick wins**: evict BestEffort pods (they have no requests), scale down non-critical deployments
6. **Medium-term**: Right-size pods with VPA recommendations, set proper requests/limits
7. **Long-term**: Implement ResourceQuotas, review over-provisioned workloads, use spot instances for stateless workloads

### Q5: Migrate Monolith to Kubernetes Microservices

**Answer:**

1. **Strangler Fig pattern**: don't rewrite all at once
2. **Containerize monolith first**: run as single pod, gain deployment benefits
3. **Extract services incrementally**: start with loosely coupled, stateless components
4. **API Gateway/Service mesh**: route traffic to new services or monolith
5. **Shared database → per-service DB**: eventual consistency, event-driven communication
6. **Communication**: synchronous (gRPC/REST) for queries, async (SQS/Kafka) for events
7. **Observability first**: distributed tracing, centralized logging before breaking apart
8. **Feature flags**: gradual traffic shift between monolith and new service
9. **Data migration**: dual-write period, then cut over

### Q6: Implement Canary Deployments in EKS

**Answer:**

Options (simplest to most sophisticated):

1. **Multiple Deployments + shared Service** (basic, weighted by replica count)
2. **AWS ALB weighted target groups** (via Ingress annotations)
3. **Istio VirtualService** (percentage-based traffic split, header-based routing)
4. **Argo Rollouts**:

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Rollout
metadata:
  name: web
spec:
  replicas: 10
  strategy:
    canary:
      canaryService: web-canary
      stableService: web-stable
      trafficRouting:
        alb:
          ingress: web-ingress
          servicePort: 80
      steps:
        - setWeight: 5
        - pause: {duration: 5m}
        - setWeight: 20
        - pause: {duration: 10m}
        - setWeight: 50
        - pause: {duration: 10m}
      analysis:
        templates:
          - templateName: success-rate
        startingStep: 2
```

5. **Flagger** (progressive delivery with metrics-based promotion)

### Q7: Service Not Reachable from Another Namespace

**Answer:**

Debugging steps:
1. **DNS**: use FQDN `service-name.namespace.svc.cluster.local` from other namespace
2. **NetworkPolicy**: check if any NetworkPolicy in target namespace blocks ingress from source namespace
3. **Service selector**: verify labels match pods (`kubectl get endpoints <service>`)
4. **Pod running?**: `kubectl get pods -n <namespace>` - are backend pods Ready?
5. **Port mismatch**: service port vs targetPort vs container port
6. **Test connectivity**: `kubectl exec -it <source-pod> -- curl <service>.<namespace>.svc.cluster.local:<port>`
7. **CoreDNS**: check if DNS resolution works: `kubectl exec -it <pod> -- nslookup <service>.<namespace>`
8. **kube-proxy**: check iptables rules on the node

### Q8: Handle Node Failure Gracefully

**Answer:**

1. **Pod anti-affinity**: spread replicas across nodes
2. **PodDisruptionBudget**: maintain minimum availability
3. **ReplicaSets**: automatically reschedule pods on healthy nodes
4. **Node problem detector**: detects hardware/kernel issues, taints nodes
5. **Pod eviction timeout**: `--pod-eviction-timeout=5m` (default) on controller manager
6. **Liveness probes**: detect application-level failures
7. **Multi-AZ node groups**: survive AZ failures
8. **StatefulSets**: consider `podManagementPolicy: Parallel` for faster recovery
9. **Pre-provisioned nodes**: keep some spare capacity (Cluster Autoscaler over-provisioning)
10. **Persistent volumes**: EBS volumes reattach to pods on new nodes (same AZ)

### Q9: Design RBAC for Multiple Teams

**Answer:**

```
Platform Team:    ClusterRole (full access to all namespaces, node management)
Dev Team A:       Role in namespace-a (full CRUD on deployments, pods, services, configmaps)
Dev Team B:       Role in namespace-b (same as above)
QA Team:          Role in qa-* namespaces (read all, create/delete pods for testing)
On-Call:          ClusterRole (read-only everywhere + exec into pods + view logs)
CI/CD Bot:        Role per namespace (create/update deployments, read secrets)
Auditor:          ClusterRole (get/list/watch everything, no mutations)
```

Best practices:
- Use Groups (not individual users) in RoleBindings
- Map IAM roles to K8s groups via aws-auth ConfigMap
- Audit with `kubectl auth can-i --list --as=dev-user`
- Principle of least privilege
- Separate ClusterRoles for read vs write
- Use `aggregatedClusterRoles` for composable permissions

### Q10: Auto-Scaling for Event-Driven Workloads

**Answer:**

Use **KEDA** for event-driven scaling:
- Scale to zero when no events (cost savings)
- Scale based on queue depth (SQS, Kafka consumer lag)
- Combine with HPA for CPU/memory

Architecture:
```
SQS Queue → KEDA ScaledObject → Deployment (0-100 pods)
                                     ↓
                              Karpenter (provisions nodes as needed)
```

- Set `pollingInterval` based on latency requirements
- Use `cooldownPeriod` to prevent thrashing
- Consider `ScaledJob` instead of `ScaledObject` for batch/job workloads (one pod per message)

### Q11: Pod Stuck in Pending State - Root Causes

**Answer:**

1. **Insufficient resources**: no node has enough CPU/memory for the pod's requests
   - Fix: add nodes, reduce requests, use Cluster Autoscaler/Karpenter
2. **No matching nodes**: nodeSelector/affinity rules can't be satisfied
3. **Taints without tolerations**: all nodes are tainted, pod doesn't tolerate
4. **PVC not bound**: PV not available, wrong StorageClass, wrong AZ (WaitForFirstConsumer)
5. **ResourceQuota exceeded**: namespace quota full
6. **Too many pods on nodes**: max pods per node reached (EKS: ENI limit)
7. **Image pull issues**: won't show as Pending long (transitions to other status)
8. **Scheduler not running**: control plane issue (rare in EKS)

Debug: `kubectl describe pod <name>` → Events section shows why scheduling failed.

### Q12: Rolling Updates Without Downtime

See Q2 above. Additional considerations:
- Database migrations: run as init container or separate Job BEFORE deployment
- Backward-compatible APIs: new version must handle old requests
- Graceful shutdown: handle SIGTERM, finish in-flight requests
- Session persistence: externalize sessions (Redis) or use sticky sessions

### Q13: Secrets Management Best Practices

**Answer:**

1. **Never in Git**: use External Secrets Operator or Sealed Secrets
2. **Encryption at rest**: enable KMS envelope encryption in EKS
3. **Rotate regularly**: External Secrets Operator with `refreshInterval`
4. **Least privilege**: RBAC - restrict who can `get` secrets
5. **Avoid env vars**: prefer volume mounts (env vars visible in `describe pod`, process listing)
6. **Source of truth**: AWS Secrets Manager or HashiCorp Vault
7. **Audit**: enable API audit logging, alert on secret access
8. **Don't log secrets**: sanitize application logs
9. **Short-lived credentials**: use IRSA/Pod Identity instead of long-lived keys
10. **Immutable secrets**: use versioned names, redeploy to rotate

### Q14: Disaster Recovery for EKS Cluster

**Answer:**

**RTO/RPO considerations:**

1. **Infrastructure as Code**: Terraform/CDK for cluster, node groups, add-ons
2. **GitOps**: all workload manifests in Git (ArgoCD/Flux recreates everything)
3. **Persistent data**: 
   - EBS snapshots (cross-region copy)
   - Database: RDS Multi-AZ + cross-region read replicas
   - S3: cross-region replication
4. **Velero**: backup K8s resources + PV snapshots, restore to new cluster
5. **Multi-region**:
   - Active-passive: standby cluster in DR region, Route 53 failover
   - Active-active: both clusters serve traffic, Global Accelerator
6. **etcd**: managed by AWS in EKS (automatic backups)
7. **Test regularly**: practice failover, validate backup restoration
8. **DNS**: Route 53 health checks + failover routing policy

```bash
# Velero backup
velero backup create full-backup --include-namespaces production
velero restore create --from-backup full-backup
```

### Q15: Node Draining and Maintenance

**Answer:**

```bash
# Cordon: prevent new pods from scheduling
kubectl cordon node-1

# Drain: evict all pods (respects PDBs)
kubectl drain node-1 --ignore-daemonsets --delete-emptydir-data --grace-period=60

# After maintenance
kubectl uncordon node-1
```

EKS managed node groups handle this automatically during AMI updates.

### Q16: Debugging DNS Issues

**Answer:**

```bash
# Test DNS from a debug pod
kubectl run dnsutils --image=gcr.io/kubernetes-e2e-test-images/dnsutils -- sleep infinity
kubectl exec dnsutils -- nslookup kubernetes.default
kubectl exec dnsutils -- nslookup myservice.mynamespace.svc.cluster.local
kubectl exec dnsutils -- cat /etc/resolv.conf

# Check CoreDNS
kubectl get pods -n kube-system -l k8s-app=kube-dns
kubectl logs -n kube-system -l k8s-app=kube-dns
```

Common issues: CoreDNS pods not running, ndots configuration causing slow resolution, DNS policy in pod spec.

### Q17: Implementing Rate Limiting

**Answer:**

Options:
1. **Ingress-level**: NGINX ingress annotations (`nginx.ingress.kubernetes.io/limit-rps`)
2. **Service mesh**: Istio `EnvoyFilter` or rate limit service
3. **API Gateway**: AWS API Gateway in front of cluster
4. **Application-level**: middleware in your app
5. **Network policy + custom**: use Cilium L7 policies

### Q18: Cost Optimization in EKS

**Answer:**

1. **Right-size pods**: use VPA recommendations
2. **Spot instances**: for stateless workloads (Karpenter handles interruptions)
3. **Scale to zero**: KEDA for event-driven, cluster-autoscaler scale-down
4. **Fargate**: for bursty workloads (no idle node cost)
5. **Resource quotas**: prevent over-provisioning
6. **Savings Plans/Reserved Instances**: for baseline node capacity
7. **Karpenter consolidation**: automatically bin-packs and replaces underutilized nodes
8. **Namespace cost allocation**: Kubecost, CloudWatch Container Insights cost metrics
9. **Ephemeral environments**: auto-delete preview/dev environments
10. **Shared clusters**: multi-tenant with proper isolation vs one cluster per team

### Q19: Handling ConfigMap/Secret Updates

**Answer:**

- Volume-mounted ConfigMaps auto-update (~60s kubelet sync)
- Env vars from ConfigMaps do NOT update without restart
- Solutions for triggering restart:
  1. **Reloader** (stakater/reloader): watches ConfigMap/Secret changes, triggers rolling restart
  2. **Hash in annotation**: include configmap hash in pod template annotation (Helm: `checksum/config`)
  3. **Immutable ConfigMaps**: create new ConfigMap with version suffix, update Deployment reference

```yaml
# Helm pattern
spec:
  template:
    metadata:
      annotations:
        checksum/config: {{ include (print $.Template.BasePath "/configmap.yaml") . | sha256sum }}
```

### Q20: Implementing Blue-Green Deployments

**Answer:**

```yaml
# Blue (current production)
apiVersion: apps/v1
kind: Deployment
metadata:
  name: app-blue
spec:
  replicas: 5
  selector:
    matchLabels:
      app: myapp
      version: blue
---
# Green (new version)
apiVersion: apps/v1
kind: Deployment
metadata:
  name: app-green
spec:
  replicas: 5
  selector:
    matchLabels:
      app: myapp
      version: green
---
# Service - switch selector to cut over
apiVersion: v1
kind: Service
metadata:
  name: myapp
spec:
  selector:
    app: myapp
    version: blue  # Change to "green" for cutover
  ports:
    - port: 80
```

Cutover: `kubectl patch service myapp -p '{"spec":{"selector":{"version":"green"}}}'`

Rollback: switch selector back to `blue`.

Advantage: instant cutover/rollback. Disadvantage: 2x resources during deployment.

### Q21: Implementing Pod Topology Spread Constraints

**Answer:**

```yaml
spec:
  topologySpreadConstraints:
    - maxSkew: 1
      topologyKey: topology.kubernetes.io/zone
      whenUnsatisfiable: DoNotSchedule
      labelSelector:
        matchLabels:
          app: web
    - maxSkew: 1
      topologyKey: kubernetes.io/hostname
      whenUnsatisfiable: ScheduleAnyway
      labelSelector:
        matchLabels:
          app: web
```

Better than pod anti-affinity for even distribution across zones/nodes.

### Q22: EKS Upgrade Strategy

**Answer:**

1. **Review changelog**: breaking changes, deprecated APIs
2. **Update control plane**: `aws eks update-cluster-version` (managed by AWS, ~25 min)
3. **Update add-ons**: CoreDNS, kube-proxy, VPC CNI (compatible versions)
4. **Update node groups**: rolling update (managed) or blue-green node groups
5. **Test**: validate workloads in staging first
6. **PDBs**: ensure they're set to prevent disruption during node rotation
7. **One minor version at a time**: 1.27 → 1.28 → 1.29 (no skipping)

```bash
# Check deprecated APIs
kubectl get --raw /metrics | grep apiserver_requested_deprecated_apis
# Or use pluto
pluto detect-all-in-cluster
```

---

## Quick Reference Commands

```bash
# Cluster info
kubectl cluster-info
kubectl get nodes -o wide
kubectl top nodes

# Debugging
kubectl describe pod <pod>
kubectl logs <pod> -c <container> --previous
kubectl exec -it <pod> -- /bin/sh
kubectl get events --sort-by='.lastTimestamp' -n <ns>
kubectl auth can-i create deployments --as=dev-user -n production

# Scaling
kubectl scale deployment web --replicas=5
kubectl autoscale deployment web --min=3 --max=20 --cpu-percent=70

# Rolling updates
kubectl set image deployment/web app=myapp:v2
kubectl rollout status deployment/web
kubectl rollout undo deployment/web

# Resource usage
kubectl top pods -A --sort-by=memory
kubectl describe node <node> | grep -A 5 "Allocated resources"

# Network debugging
kubectl run tmp --image=curlimages/curl --rm -it -- curl http://service.namespace:port
kubectl get endpoints <service>
```
