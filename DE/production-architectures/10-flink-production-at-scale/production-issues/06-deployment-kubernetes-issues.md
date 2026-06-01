# Deployment & Kubernetes Issues (#66-76)

> Operating Flink on Kubernetes introduces platform-specific challenges around scheduling, networking, storage, and lifecycle management.

---

## Issue #66: Pod Evicted Due to Resource Limits

**Severity**: 🔴 Critical  
**Frequency**: High  
**Impact**: TaskManager killed, job restarts

### Symptoms
```
Status: Evicted
Reason: The node was low on resource: memory.
```
- Pod evicted by kubelet
- Node memory pressure triggers eviction
- BestEffort/Burstable pods evicted first

### Root Cause
1. Node-level memory pressure (other pods consuming too much)
2. Memory request < actual usage (Burstable QoS → eviction candidate)
3. Ephemeral storage exhaustion (RocksDB temp files filling local disk)

### Fix
```yaml
# Use Guaranteed QoS (request = limit)
resources:
  requests:
    memory: "8Gi"
    cpu: "4"
  limits:
    memory: "8Gi"    # Equal to request = Guaranteed QoS
    cpu: "4"

# Set ephemeral storage limits
  requests:
    ephemeral-storage: "50Gi"
  limits:
    ephemeral-storage: "100Gi"

# Use PodDisruptionBudget to prevent voluntary evictions
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: flink-tm-pdb
spec:
  minAvailable: "90%"
  selector:
    matchLabels:
      component: taskmanager
```

### Prevention
- Always set `requests = limits` for Flink TMs (Guaranteed QoS)
- Monitor node memory pressure events
- Use dedicated node pools for Flink workloads
- Set PodDisruptionBudget for TMs

---

## Issue #67: PVC Provisioning Delay on Rescale

**Severity**: 🟡 Warning  
**Frequency**: Medium  
**Impact**: New TMs stuck in Pending state, delayed recovery

### Symptoms
- New TaskManager pods stuck in `Pending` state
- Events show: `waiting for a volume to be created`
- EBS volume provisioning takes 30-60 seconds
- During rescale, new TMs delayed

### Root Cause
When scaling up or replacing TMs:
- StatefulSet creates new pods → needs new PVCs
- Cloud provider needs time to provision new volumes
- Cross-AZ provisioning may fail (topology constraints)

### Fix
```yaml
# Use volumeBindingMode: WaitForFirstConsumer (default for many CSI drivers)
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: flink-state-ssd
provisioner: ebs.csi.aws.com
parameters:
  type: gp3
  iops: "16000"
  throughput: "1000"
volumeBindingMode: WaitForFirstConsumer
allowVolumeExpansion: true

# Pre-provision PVCs for faster scaling
# OR use emptyDir with memory/SSD for state (if state fits)
volumes:
  - name: state-dir
    emptyDir:
      medium: ""          # Use node disk (fast but lost on pod death)
      sizeLimit: 100Gi
```

### Prevention
- Pre-provision PVCs for expected max scale
- Use `emptyDir` with local SSD for state (rely on checkpoints for durability)
- Consider hostPath with local NVMe for maximum performance
- Set appropriate StorageClass with fast provisioning

---

## Issue #68: DNS Resolution Failure Breaking Inter-TM Communication

**Severity**: 🔴 Critical  
**Frequency**: Medium  
**Impact**: Network shuffle fails, job restarts

### Symptoms
```
java.net.UnknownHostException: flink-taskmanager-5.flink-taskmanager.default.svc.cluster.local
```
- New TM cannot resolve other TM hostnames
- Network shuffle between TMs failing
- CoreDNS pod overloaded or timing out

### Root Cause
1. CoreDNS overwhelmed (Flink generates many DNS lookups)
2. DNS cache TTL too short (re-resolving constantly)
3. Pod hostname not yet registered in DNS when shuffle starts
4. ndots setting causing excessive search domains

### Fix
```yaml
# Add DNS config to Flink pods
spec:
  dnsConfig:
    options:
      - name: ndots
        value: "2"          # Reduce DNS search attempts (default 5)
      - name: single-request-reopen
        value: ""
      - name: timeout
        value: "3"
      - name: attempts
        value: "3"

# Use headless service for TM discovery
apiVersion: v1
kind: Service
metadata:
  name: flink-taskmanager
spec:
  clusterIP: None  # Headless
  selector:
    component: taskmanager
  ports:
    - port: 6122
      name: rpc
```

```yaml
# Flink config: Use IP-based communication (skip DNS for data)
taskmanager.host: <pod-ip>  # Set via downward API
taskmanager.registration.timeout: 60s
```

### Prevention
- Set `ndots: 2` to reduce DNS lookup attempts
- Use NodeLocal DNSCache for faster resolution
- Monitor CoreDNS latency and error rate
- Ensure headless service is created before TMs start

---

## Issue #69: Flink Kubernetes Operator CRD Version Mismatch

**Severity**: 🟡 Warning  
**Frequency**: Medium  
**Impact**: Job deployment fails, operator cannot reconcile

### Symptoms
```
Error: admission webhook "validation.flink.apache.org" denied the request:
  FlinkDeployment.spec.job.upgradeMode: Unsupported value
```
- FlinkDeployment CRD rejected by webhook
- Operator logs show reconciliation errors
- After operator upgrade, old CRDs incompatible

### Fix
```bash
# Update CRDs to match operator version
kubectl apply -f https://github.com/apache/flink-kubernetes-operator/releases/download/release-1.8.0/flink-kubernetes-operator-crds.yaml

# Check operator version
kubectl get pods -n flink-operator -o jsonpath='{.items[0].spec.containers[0].image}'

# Check CRD version
kubectl get crd flinkdeployments.flink.apache.org -o jsonpath='{.spec.versions[*].name}'
```

### Prevention
- Always update CRDs before operator upgrade
- Pin operator version in Helm values
- Test operator upgrades in staging first

---

## Issue #70: Job Upgrade Failing Due to Savepoint Incompatibility

**Severity**: 🔴 Critical  
**Frequency**: Medium  
**Impact**: Cannot upgrade job, stuck on old version

### Symptoms
```
StateMigrationException: The new state serializer for operator 'my-op' 
  is incompatible with the previous one
```
- `upgradeMode: savepoint` fails
- State schema changed between versions
- Operator UIDs changed or removed

### Fix
```yaml
# Option 1: Allow non-restored state (skip incompatible operators)
spec:
  job:
    upgradeMode: savepoint
    allowNonRestoredState: true  # Skip operators that can't restore

# Option 2: Use last-state upgrade mode (uses checkpoint, not savepoint)
spec:
  job:
    upgradeMode: last-state  # Faster, but less portable
```

```java
// In code: Support state schema evolution
@TypeInfo(MyStateTypeInfoFactory.class)
public class MyState {
    public int version;  // Add version field for migration
    public String data;
    
    // Migration logic in custom serializer
}
```

### Prevention
- ALWAYS set `.uid()` on stateful operators
- NEVER remove operator UIDs between versions
- Implement TypeSerializerSnapshot for state evolution
- Test savepoint restore in CI before deploying

---

## Issue #71: Ingress/LoadBalancer Exposing REST API Insecurely

**Severity**: 🔴 Critical  
**Frequency**: Medium  
**Impact**: Security vulnerability, unauthorized job management

### Symptoms
- Flink REST API accessible from internet
- Anyone can cancel/submit jobs
- State/checkpoint data accessible

### Fix
```yaml
# Restrict access with NetworkPolicy
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: flink-jobmanager-access
spec:
  podSelector:
    matchLabels:
      component: jobmanager
  ingress:
    - from:
        - podSelector:
            matchLabels:
              role: flink-operator
        - podSelector:
            matchLabels:
              role: monitoring
      ports:
        - port: 8081
          protocol: TCP

# Disable REST API submission in production
rest.address: 0.0.0.0
web.submit.enable: false
web.cancel.enable: false
```

### Prevention
- Never expose JM REST API to public internet
- Use NetworkPolicies to restrict access
- Disable job submission via REST in production
- Use Flink Kubernetes Operator for job management (not REST API)

---

## Issue #72: ConfigMap Size Limit Exceeded

**Severity**: 🟡 Warning  
**Frequency**: Low-Medium  
**Impact**: Cannot deploy job, configuration rejected

### Symptoms
```
Error: ConfigMap "flink-config" is invalid: 
  []: Too long: must have at most 1048576 bytes
```

### Root Cause
ConfigMap limited to 1MB. Large Flink configurations with:
- Many job-specific properties
- Embedded log4j.properties
- Large custom configurations

### Fix
```yaml
# Split configuration across multiple ConfigMaps
volumes:
  - name: flink-config
    configMap:
      name: flink-config-base
  - name: flink-config-logging
    configMap:
      name: flink-config-logging
  - name: flink-config-metrics
    configMap:
      name: flink-config-metrics

# Or use environment variables for dynamic config
env:
  - name: FLINK_PROPERTIES
    value: |
      state.backend: rocksdb
      state.backend.incremental: true
```

---

## Issue #73: Anti-Affinity Rules Preventing Scheduling

**Severity**: 🟡 Warning  
**Frequency**: Medium  
**Impact**: Pods stuck in Pending, cannot scale

### Symptoms
- TM pods in `Pending` state
- Events: `0/10 nodes are available: 10 node(s) didn't match pod anti-affinity rules`
- Anti-affinity requires TMs on different nodes but not enough nodes

### Fix
```yaml
# Use preferredDuringScheduling (soft anti-affinity) instead of required
affinity:
  podAntiAffinity:
    preferredDuringSchedulingIgnoredDuringExecution:  # Soft, not hard
      - weight: 100
        podAffinityTerm:
          labelSelector:
            matchExpressions:
              - key: component
                operator: In
                values: ["taskmanager"]
          topologyKey: kubernetes.io/hostname
```

### Prevention
- Use `preferred` anti-affinity for TMs (allow co-location if needed)
- Use `required` anti-affinity only for JM HA (must be on different nodes)
- Ensure node count ≥ desired TM replicas

---

## Issue #74: Rolling Update Causing Job Instability

**Severity**: 🟡 Warning  
**Frequency**: Medium  
**Impact**: Multiple restarts during upgrade window

### Symptoms
- During Kubernetes rolling update, job restarts multiple times
- Each TM replacement triggers task redistribution
- Checkpoint failures during rolling update

### Root Cause
K8s rolling update replaces TMs one by one:
- TM-0 killed → Flink detects failure → restart from checkpoint
- Job recovers on remaining TMs
- TM-1 killed → another restart
- Repeated N times for N TMs

### Fix
```yaml
# Use Flink Kubernetes Operator with proper upgrade strategy
spec:
  job:
    upgradeMode: savepoint  # Stop cleanly, then upgrade all at once
    
  flinkConfiguration:
    kubernetes.operator.job.upgrade.last-state-fallback.enabled: "true"
```

### Prevention
- Use Flink Operator's `savepoint` upgrade mode (atomic upgrade)
- Never use raw K8s rolling update for Flink (it doesn't understand Flink semantics)
- Take savepoint → stop job → update all TMs → restore from savepoint

---

## Issue #75: Insufficient Ephemeral Storage for RocksDB

**Severity**: 🔴 Critical  
**Frequency**: Medium  
**Impact**: Pod evicted, data loss if no PVC

### Symptoms
```
The node was low on resource: ephemeral-storage
```
- RocksDB SST files filling up emptyDir
- Container writable layer growing
- Logs consuming disk space

### Fix
```yaml
# Option 1: Use PVC for state directory
volumeMounts:
  - name: state-volume
    mountPath: /opt/flink/state
volumes:
  - name: state-volume
    persistentVolumeClaim:
      claimName: flink-state-pvc

# Option 2: Properly size ephemeral storage
resources:
  requests:
    ephemeral-storage: "100Gi"
  limits:
    ephemeral-storage: "200Gi"

# Flink config: Use mounted volume for state
state.backend.rocksdb.localdir: /opt/flink/state/rocksdb
io.tmp.dirs: /opt/flink/state/tmp
```

### Prevention
- Always use PVC or properly sized emptyDir for state
- Size storage = 2× expected max state size (for compaction overhead)
- Monitor ephemeral storage usage
- Route logs to stdout (collected by log agent, not stored locally)

---

## Issue #76: Service Account Token Expiry for S3 Access

**Severity**: 🟡 Warning  
**Frequency**: Medium  
**Impact**: Checkpoint writes fail after token expires

### Symptoms
```
com.amazonaws.services.s3.model.AmazonS3Exception: 
  The security token included in the request is expired
```
- Checkpoints start failing after 12 hours
- IRSA token not refreshed

### Fix
```yaml
# Ensure token volume projection with auto-refresh
serviceAccountName: flink-sa
automountServiceAccountToken: true

# For IRSA (IAM Roles for Service Accounts)
annotations:
  eks.amazonaws.com/role-arn: arn:aws:iam::123456789:role/flink-s3-role

# Flink config: Use instance profile provider (auto-refreshes)
fs.s3a.aws.credentials.provider: com.amazonaws.auth.WebIdentityTokenCredentialsProvider
```

### Prevention
- Use IRSA with auto-rotating tokens
- Don't use long-lived static credentials
- Monitor S3 auth failures
- Test with token refresh in staging (run job > 12 hours)
