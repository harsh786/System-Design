# Category 7: Cluster & Resource Management Issues (Issues 61-70)

> Multi-tenant clusters with 500+ daily jobs and 1000+ executors require careful resource governance. One runaway job can starve the entire platform.

---

## Issue #61: Dynamic Allocation Not Scaling Up Fast Enough

**Frequency**: High  
**Severity**: Medium-High - jobs starved for resources  
**Spark Component**: ExecutorAllocationManager, DynamicAllocation

### Symptoms
```
# Job needs 200 executors but only gets 20 after 5 minutes
# Tasks queued as "pending" but cluster has available resources
# Slow ramp-up: 5 → 10 → 20 → 40 (exponential backoff too slow)
# Time-sensitive job misses SLA due to resource acquisition delay
```

### Root Cause
- Default scale-up is conservative (exponential increase with backlog)
- `schedulerBacklogTimeout` too long (default 1s but feels slow at scale)
- YARN/K8s takes time to allocate containers/pods
- Other applications holding idle executors
- Max executor limit set too low

### Solution
```python
# 1. Tune dynamic allocation for faster scale-up
spark.conf.set("spark.dynamicAllocation.enabled", "true")
spark.conf.set("spark.dynamicAllocation.minExecutors", "10")     # Start with some
spark.conf.set("spark.dynamicAllocation.maxExecutors", "500")    # Allow large scale
spark.conf.set("spark.dynamicAllocation.initialExecutors", "50") # Start with 50!
spark.conf.set("spark.dynamicAllocation.schedulerBacklogTimeout", "1s")  # Scale up after 1s
spark.conf.set("spark.dynamicAllocation.sustainedSchedulerBacklogTimeout", "1s")  # Keep scaling

# 2. Reduce executor idle timeout (free resources faster for others)
spark.conf.set("spark.dynamicAllocation.executorIdleTimeout", "60s")
spark.conf.set("spark.dynamicAllocation.cachedExecutorIdleTimeout", "300s")

# 3. For time-critical jobs: set higher initial executors
# Rather than ramping up, start with what you need:
spark.conf.set("spark.dynamicAllocation.initialExecutors", "200")
spark.conf.set("spark.dynamicAllocation.minExecutors", "100")

# 4. Pre-warm executors before job starts
# K8s: create executor pods before submitting
# YARN: use node label placement for pre-warmed nodes

# 5. For predictable workloads: use fixed allocation
spark.conf.set("spark.dynamicAllocation.enabled", "false")
spark.conf.set("spark.executor.instances", "200")  # Fixed, no ramp-up delay
# Trade-off: resources held even when idle

# 6. External Shuffle Service (required for dynamic allocation)
spark.conf.set("spark.shuffle.service.enabled", "true")
# Without ESS: Spark can't remove executors that have shuffle data
```

---

## Issue #62: Resource Starvation in Multi-Tenant Clusters

**Frequency**: High  
**Severity**: Critical - entire teams blocked  
**Spark Component**: YARN FairScheduler / K8s ResourceQuota

### Symptoms
```
# Team A's adhoc query uses 500 executors, Team B's production pipeline stuck in queue
# One runaway job consumes entire cluster
# Priority inversion: dev notebook blocks production ETL
# No preemption: first-come-first-served regardless of importance
```

### Root Cause
- No resource pools/queues configured
- No per-user/team resource limits
- No priority system (production vs adhoc vs dev)
- Dynamic allocation maxExecutors not set per application

### Solution
```python
# 1. YARN Fair Scheduler: allocate pools per team/priority
# fair-scheduler.xml:
"""
<queue name="production">
    <weight>4.0</weight>
    <minResources>500 cores, 2000 GB</minResources>
    <maxResources>2000 cores, 8000 GB</maxResources>
    <maxRunningApps>50</maxRunningApps>
    <schedulingPolicy>fair</schedulingPolicy>
</queue>
<queue name="adhoc">
    <weight>1.0</weight>
    <maxResources>500 cores, 2000 GB</maxResources>
    <maxRunningApps>200</maxRunningApps>
</queue>
"""

# 2. Set max executors per application
spark.conf.set("spark.dynamicAllocation.maxExecutors", "100")  # Per app limit
# Production pipelines: maxExecutors=500
# Adhoc queries: maxExecutors=50
# Notebooks: maxExecutors=20

# 3. Kubernetes: ResourceQuota per namespace
# namespace: spark-production → 2000 cores, 8TB memory
# namespace: spark-adhoc → 500 cores, 2TB memory
# namespace: spark-dev → 200 cores, 1TB memory

# 4. Priority-based scheduling
# YARN: application priority
spark.conf.set("spark.yarn.priority", "5")  # Higher = more important
# K8s: PriorityClass
spark.conf.set("spark.kubernetes.driver.podTemplateFile", "priority-pod.yaml")

# 5. Preemption for production jobs
# YARN: enable preemption in fair scheduler
# If production queue starved, preempt adhoc executors
# K8s: PriorityClass with preemption

# 6. Per-user resource accounting
spark.conf.set("spark.yarn.queue", "team_a")  # Route to team's queue
# Monitor: per-queue utilization → chargeback reporting
```

---

## Issue #63: Executor Decommissioning / Spot Instance Termination

**Frequency**: High (when using Spot/Preemptible)  
**Severity**: Medium-High - task failures, data loss  
**Spark Component**: ExecutorDecommission, BlockManagerDecommission

### Symptoms
```
# AWS Spot: "Instance termination notice" → executor lost
# Tasks fail with FetchFailedException (shuffle data gone)
# GCP Preemptible: random executor losses
# Job retries entire stages (expensive recomputation)
```

### Root Cause
- Spot instances terminated with 2-minute notice
- Shuffle data on terminated instance is lost
- Cached data on terminated instance is lost
- No graceful migration of running tasks

### Solution
```python
# 1. Enable graceful decommissioning (Spark 3.1+)
spark.conf.set("spark.decommission.enabled", "true")
spark.conf.set("spark.storage.decommission.enabled", "true")
spark.conf.set("spark.storage.decommission.shuffleBlocks.enabled", "true")
spark.conf.set("spark.storage.decommission.rddBlocks.enabled", "true")

# 2. Migrate shuffle data before termination
spark.conf.set("spark.storage.decommission.shuffleBlocks.maxThreads", "8")
# When spot termination notice received:
# Spark migrates shuffle blocks to other executors before dying

# 3. Use External Shuffle Service (survives executor death)
spark.conf.set("spark.shuffle.service.enabled", "true")
# ESS on on-demand nodes: spot executors write shuffle to stable ESS

# 4. Mix spot + on-demand
# Driver: ALWAYS on-demand (losing driver = lose entire app)
# Executors: 80% spot, 20% on-demand
# On-demand executors hold shuffle service

# 5. Increase task retry budget
spark.conf.set("spark.task.maxFailures", "8")  # Default 4, increase for spot
spark.conf.set("spark.stage.maxConsecutiveAttempts", "10")

# 6. Use instance diversification (multiple spot pools)
# EMR: mix r5.4xlarge, r5a.4xlarge, r6i.4xlarge across AZs
# This reduces chance of simultaneous termination

# 7. For K8s: handle spot signals
# K8s sends SIGTERM 30s before pod deletion
# Spark decommission listener catches this and migrates
spark.conf.set("spark.kubernetes.executor.decommission.signal", "SIGTERM")
```

---

## Issue #64: Driver Single Point of Failure

**Frequency**: Medium  
**Severity**: Critical - entire application lost  
**Spark Component**: SparkDriver, SparkContext

### Symptoms
```
# Driver pod/container OOM → all executors terminated, entire job lost
# Driver network partition → all executors timeout and die
# No way to resume: must restart from beginning
# Loss of 4 hours of work because driver crashed at hour 3.5
```

### Root Cause
- Driver is SPOF (Single Point of Failure) - can't restart without losing state
- Driver collects too much metadata (large plans, many tasks)
- Driver OOM from broadcast, collect, or plan complexity
- No HA for driver in standard deployment

### Solution
```python
# 1. Protect driver memory
spark.conf.set("spark.driver.memory", "16g")  # Generous for driver
spark.conf.set("spark.driver.memoryOverhead", "4g")
spark.conf.set("spark.driver.maxResultSize", "4g")

# 2. Avoid operations that stress driver
# Never: df.collect() on large data
# Never: very large broadcast (> 1GB)
# Never: df.explain() on extremely complex plans
# Limit: number of partitions (each adds driver memory overhead)

# 3. Structured Streaming: checkpoint = driver resilience
# If driver dies, restart from checkpoint → resume from last committed offset
query = df.writeStream \
    .option("checkpointLocation", "s3://checkpoints/pipeline/") \
    .start()
# Restart: automatically resumes from checkpoint

# 4. For batch jobs: idempotent stage design
# Design each stage to be re-runnable:
# Stage 1: raw → bronze (idempotent overwrite)
# Stage 2: bronze → silver (idempotent MERGE)
# Stage 3: silver → gold (idempotent)
# If driver dies at Stage 2: restart from Stage 2, not beginning

# 5. Kubernetes: driver restart with checkpoint
# Configure driver PodRestartPolicy to restart on failure
# Combined with checkpointing for streaming

# 6. Notebook environments: save intermediate results
# After expensive computation:
expensive_result.write.parquet("s3://intermediate/step1/")
# If kernel dies, reload:
expensive_result = spark.read.parquet("s3://intermediate/step1/")
```

---

## Issue #65: Executor-to-Driver Heartbeat Timeout

**Frequency**: Medium  
**Severity**: High - executors killed, tasks restarted  
**Spark Component**: HeartbeatReceiver, BlockManagerMasterEndpoint

### Symptoms
```
WARN HeartbeatReceiver: Removing executor 7 with no recent heartbeats: 
  130642 ms exceeds timeout 120000 ms
ERROR TaskSchedulerImpl: Lost executor 7: Executor heartbeat timed out
# Executor was alive but too busy (GC, heavy I/O) to send heartbeat
```

### Root Cause
- Long GC pause on executor (>120s) → missed heartbeats
- Network congestion delaying heartbeat packets
- Driver too busy to process heartbeats
- Executor genuinely crashed (OOM, segfault)
- Default timeout (120s) too short for heavy workloads

### Solution
```python
# 1. Increase heartbeat timeout
spark.conf.set("spark.executor.heartbeatInterval", "30s")    # Send every 30s (default 10s)
spark.conf.set("spark.network.timeout", "600s")              # Kill after 600s (default 120s)
spark.conf.set("spark.storage.blockManagerHeartbeatTimeoutMs", "600000")

# 2. Fix root cause: reduce GC pauses
spark.conf.set("spark.executor.extraJavaOptions",
    "-XX:+UseG1GC -XX:G1HeapRegionSize=16m "
    "-XX:InitiatingHeapOccupancyPercent=35 "
    "-XX:MaxGCPauseMillis=200")  # Target 200ms max pause

# 3. Reduce memory pressure (fewer GC pauses)
spark.conf.set("spark.memory.storageFraction", "0.3")  # Less cache pressure
spark.conf.set("spark.executor.cores", "4")             # Fewer concurrent tasks

# 4. Separate heartbeat from data traffic
# Ensure heartbeat port isn't congested by shuffle traffic
# Use dedicated network for control plane if possible

# 5. Monitor heartbeat health
# Track: time since last heartbeat per executor
# Alert: any executor > 60s without heartbeat (before timeout kills it)

# 6. Distinguish genuine death from false positive
# If executor comes back after "timeout": increase timeout
# If executor is truly dead (OOM in container logs): fix memory issue
```

---

## Issue #66: YARN Queue Full / K8s Pending Pods

**Frequency**: High  
**Severity**: High - jobs queued indefinitely  
**Spark Component**: External (YARN RM / K8s Scheduler)

### Symptoms
```
# YARN: Application stuck in ACCEPTED state for 30+ minutes
# K8s: Executor pods in "Pending" state (Insufficient CPU/memory)
# Cluster at capacity: no resources available
# Jobs queuing behind long-running queries
```

### Root Cause
- Cluster fully utilized (no headroom)
- Other applications holding idle resources
- No auto-scaling configured
- Resource fragmentation (enough total but not contiguous)
- Admission control rejecting applications

### Solution
```python
# 1. Cluster auto-scaling
# EMR: managed scaling
# emr-managed-scaling-policy.json:
"""
{
    "ComputeLimits": {
        "UnitType": "InstanceFleetUnits",
        "MinimumCapacityUnits": 50,
        "MaximumCapacityUnits": 500,
        "MaximumOnDemandCapacityUnits": 100,
        "MaximumCoreCapacityUnits": 200
    }
}
"""

# 2. K8s Cluster Autoscaler
# Detects pending pods → provisions new nodes
# Node scale-down: removes underutilized nodes after 10 min idle

# 3. Set application timeouts (don't queue forever)
spark.conf.set("spark.yarn.submit.waitAppCompletion", "false")
spark.conf.set("spark.yarn.maxAppAttempts", "2")
# Fail fast rather than queue for hours

# 4. Priority-based admission
# High-priority production: preempts low-priority adhoc
# Implement timeout: if queued > 10 min, page oncall

# 5. Resource right-sizing (free up waste)
# Audit: identify apps requesting 100 executors but using 10
# Enforce: maxExecutors per priority level
# Monitor: executor CPU utilization < 20% → over-provisioned

# 6. Off-peak scheduling
# Run heavy batch jobs at night (when cluster isn't contended)
# Reserve capacity for daytime adhoc/production
```

---

## Issue #67: Executor Process Running but Not Doing Work

**Frequency**: Medium  
**Severity**: Medium - resource waste  
**Spark Component**: TaskSchedulerImpl, CoarseGrainedExecutorBackend

### Symptoms
```
# Executor allocated (holding resources) but 0 active tasks
# Dynamic allocation should have removed it but hasn't
# Executor "alive" for 2 hours with nothing to do
# Resource waste: paying for idle compute
```

### Root Cause
- Cached data on executor prevents removal (cachedExecutorIdleTimeout not reached)
- Shuffle data blocks executor removal
- Bug in dynamic allocation listener
- Task scheduling starvation (tasks going to other executors)
- Executor in decommission limbo

### Solution
```python
# 1. Configure aggressive idle removal
spark.conf.set("spark.dynamicAllocation.executorIdleTimeout", "60s")
spark.conf.set("spark.dynamicAllocation.cachedExecutorIdleTimeout", "300s")  # 5 min for cached

# 2. Unpersist cached data when no longer needed
df_cached.unpersist()
# This removes the "cached data" hold on executor

# 3. External Shuffle Service allows faster executor removal
spark.conf.set("spark.shuffle.service.enabled", "true")
# Without ESS: executor holds shuffle data until consuming stage finishes
# With ESS: executor can be removed immediately after writing shuffle

# 4. Monitor executor utilization
# Metric: task_time / (executor_uptime * cores)
# If < 10% utilization → too many executors or scheduling issue

# 5. For K8s: set resource requests = limits (no overcommit)
# Prevents "allocated but idle" containers wasting node resources

# 6. Force executor removal for testing
# spark.dynamicAllocation.testing = true (enables manual deallocation)
```

---

## Issue #68: Spark Submit Conflicts with Cluster Spark Version

**Frequency**: Medium  
**Severity**: High - NoSuchMethodError, ClassNotFoundException  
**Spark Component**: SparkSubmit, ClassLoader

### Symptoms
```
java.lang.NoSuchMethodError: org.apache.spark.sql.SparkSession.builder()
java.lang.NoClassDefFoundError: org/apache/spark/sql/connector/read/...
# Application compiled with Spark 3.4 but cluster runs 3.2
# Incompatible Scala versions (2.12 vs 2.13)
# Hadoop/Hive version mismatches
```

### Root Cause
- Application JARs compiled against different Spark version
- Cluster upgraded but applications not recompiled
- Multiple Spark versions on same cluster
- Transitive dependency pulling wrong version

### Solution
```python
# 1. Match compile and runtime versions exactly
# pom.xml / build.sbt: spark-sql_2.12:3.4.1
# Cluster: Spark 3.4.1 (same minor version)

# 2. Use --packages for runtime dependency resolution
# spark-submit --packages org.apache.iceberg:iceberg-spark-runtime-3.4_2.12:1.4.2

# 3. Shade conflicting dependencies
# In build: relocate conflicting packages
# maven-shade-plugin / sbt-assembly with shading rules

# 4. For PySpark: match pyspark package version to cluster
# pip install pyspark==3.4.1  # Must match cluster Spark version

# 5. Multi-version clusters: containerized Spark
# K8s: each app brings its own Spark image
spark.conf.set("spark.kubernetes.container.image", "spark:3.4.1-custom")
# No cluster-level version conflict

# 6. Version check in application startup
import pyspark
print(f"PySpark version: {pyspark.__version__}")
print(f"Spark runtime: {spark.version}")
assert spark.version.startswith("3.4"), f"Expected Spark 3.4, got {spark.version}"
```

---

## Issue #69: Network Partition Between Driver and Executors

**Frequency**: Low-Medium  
**Severity**: Critical - cascading failure  
**Spark Component**: RPC, NettyRpcEnv, BlockManagerMaster

### Symptoms
```
# Half the executors become "unreachable" simultaneously
# Driver can talk to some executors but not others
# Cross-AZ/rack communication fails
# All tasks on affected executors fail
# Job doesn't fail-fast: slowly accumulates timeouts over 10 minutes
```

### Root Cause
- Network switch failure affecting subset of nodes
- Cross-AZ connectivity issue in cloud
- Security group / firewall rule change
- DNS resolution failure
- Load balancer timeout

### Solution
```python
# 1. Fail fast on network issues (don't wait 10 minutes)
spark.conf.set("spark.network.timeout", "300s")  # Reasonable timeout
spark.conf.set("spark.rpc.askTimeout", "300s")
spark.conf.set("spark.rpc.lookupTimeout", "120s")

# 2. Deploy across multiple AZs with awareness
# EMR: use multiple subnets across AZs
# K8s: pod anti-affinity spreads executors across AZs
# If one AZ has network issue, others continue

# 3. Reduce blast radius
spark.conf.set("spark.task.maxFailures", "8")  # Tolerate more failures
spark.conf.set("spark.stage.maxConsecutiveAttempts", "10")
# Failed tasks retry on other (healthy) executors

# 4. Health check integration
# Monitor: executor-to-driver ping latency
# Alert: any executor with >5s latency or failed heartbeat
# Auto-remediate: restart executors on unhealthy nodes

# 5. DNS stability
# Use IP addresses in spark.driver.host (not hostname)
# Or ensure DNS TTL is short for recovery

# 6. For cloud: use placement groups or dedicated tenancy
# Reduces chance of shared infrastructure failure
```

---

## Issue #70: Cluster Metrics Missing or Inaccurate (Blind Operations)

**Frequency**: High  
**Severity**: Medium - can't diagnose issues  
**Spark Component**: MetricsSystem, PrometheusServlet

### Symptoms
```
# Prometheus/Grafana dashboard has gaps
# Spark History Server not recording events
# Can't determine WHY a job was slow (no metrics)
# JVM metrics not exposed from executors
# Streaming progress metrics not collected
```

### Root Cause
- Metrics sink not configured (metrics.properties missing)
- Spark event log not enabled or S3 path wrong
- Prometheus scraping interval too long (misses short-lived executors)
- Push-based metrics failing silently
- History server can't read event logs

### Solution
```python
# 1. Enable comprehensive metrics
# metrics.properties:
"""
*.sink.prometheusServlet.class=org.apache.spark.metrics.sink.PrometheusServlet
*.sink.prometheusServlet.path=/metrics/prometheus
driver.source.jvm.class=org.apache.spark.metrics.source.JvmSource
executor.source.jvm.class=org.apache.spark.metrics.source.JvmSource
"""

# 2. Enable event logging for History Server
spark.conf.set("spark.eventLog.enabled", "true")
spark.conf.set("spark.eventLog.dir", "s3://spark-logs/event-logs/")
spark.conf.set("spark.eventLog.rolling.enabled", "true")
spark.conf.set("spark.eventLog.rolling.maxFileSize", "256m")

# 3. For K8s: use Prometheus ServiceMonitor
# Discover executor pods dynamically:
# ServiceMonitor scrapes /metrics/prometheus on all spark-executor pods
# Short scrape interval (15s) to catch short-lived executors

# 4. Push-based metrics for dynamic environments
# Use StatsD or Graphite sink (push instead of scrape):
"""
*.sink.statsd.class=org.apache.spark.metrics.sink.StatsdSink
*.sink.statsd.host=metrics-collector
*.sink.statsd.port=8125
*.sink.statsd.period=10
"""

# 5. Custom application metrics
from pyspark.accumulators import AccumulatorParam
records_processed = spark.sparkContext.accumulator(0)
records_failed = spark.sparkContext.accumulator(0)
# Report these to your metrics system after each batch/stage

# 6. Streaming-specific metrics
# StreamingQueryListener → push to Prometheus/Grafana
# Key metrics: inputRate, processedRate, batchDuration, stateSize
```

---

## Summary: Cluster & Resource Management Decision Tree

```
Cluster/resource problem
├── Job can't get resources?
│   ├── Dynamic allocation too slow → Issue #61 (tune ramp-up, initial executors)
│   ├── Cluster full → Issue #66 (auto-scaling, priority, right-sizing)
│   └── Multi-tenant starvation → Issue #62 (queues, quotas, preemption)
├── Losing executors?
│   ├── Spot termination → Issue #63 (decommission, ESS, diversification)
│   ├── Heartbeat timeout → Issue #65 (increase timeout, reduce GC)
│   └── Network partition → Issue #69 (fail fast, multi-AZ)
├── Wasting resources?
│   ├── Idle executors → Issue #67 (tune idle timeout, unpersist cache)
│   └── No visibility → Issue #70 (metrics, event logging)
├── Application failures?
│   ├── Driver crash = total loss → Issue #64 (protect driver, checkpoint)
│   └── Version mismatch → Issue #68 (containerized Spark, version pinning)
└── Quick wins
    ├── Set maxExecutors per app → Prevents runaway resource consumption
    ├── External Shuffle Service → Enables dynamic allocation + spot resilience
    └── Priority queues → Production never starved by adhoc
```
