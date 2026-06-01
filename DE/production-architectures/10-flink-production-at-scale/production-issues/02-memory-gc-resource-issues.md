# Memory, GC & Resource Issues (#15-26)

> Memory-related issues are the second most common cause of Flink job failures. Understanding Flink's memory model is critical for production stability.

---

## Issue #15: TaskManager OOM Killed by Kubernetes

**Severity**: 🔴 Critical  
**Frequency**: Very High  
**Impact**: Pod killed, job restarts from checkpoint, processing gap

### Symptoms
```
Last State: Terminated
Reason: OOMKilled
Exit Code: 137
```
- Pod repeatedly getting OOMKilled
- `container_memory_working_set_bytes` approaching limit
- No Java OOM in logs (killed at OS level, not JVM level)

### Root Cause
Flink's total memory consumption exceeds Kubernetes memory limit. Common causes:
1. **RocksDB native memory** not accounted for (off-heap, outside JVM tracking)
2. **Direct byte buffers** for network communication growing beyond limits
3. **JVM overhead** underestimated (thread stacks, JNI, code cache)
4. **Memory leak** in user code (cached objects, connection pools)
5. **Managed memory configured but not matching container limits**

```
K8s limit: 8GB
JVM Heap: 4GB + Off-heap: 1GB + Network: 512MB + Framework: 384MB + RocksDB: ??? (uncontrolled!)
Total actual: 8.5GB → OOMKilled!
```

### Diagnosis
```bash
# Check actual memory usage vs limit
kubectl top pod flink-taskmanager-0

# Check memory breakdown
kubectl exec flink-taskmanager-0 -- cat /proc/self/status | grep -i vm

# Check Java NMT (Native Memory Tracking)
kubectl exec flink-taskmanager-0 -- jcmd 1 VM.native_memory summary

# Check RocksDB memory
# Block cache + memtables + table readers
kubectl exec flink-taskmanager-0 -- cat /proc/self/smaps | grep -A 5 "rocksdb"
```

### Fix
```yaml
# Correct memory configuration (Flink managed = K8s limit)
taskmanager.memory.process.size: 8192m    # MUST match K8s memory limit

# Explicit breakdown (prevents overcommit)
taskmanager.memory.task.heap.size: 2048m
taskmanager.memory.managed.size: 3072m    # For RocksDB (block cache + write buffers)
taskmanager.memory.network.min: 512m
taskmanager.memory.network.max: 1024m
taskmanager.memory.framework.heap.size: 256m
taskmanager.memory.framework.off-heap.size: 128m
taskmanager.memory.jvm-overhead.fraction: 0.1
taskmanager.memory.jvm-overhead.min: 384m
taskmanager.memory.jvm-overhead.max: 1024m
taskmanager.memory.jvm-metaspace.size: 256m

# CRITICAL: Tell RocksDB to respect managed memory limit
state.backend.rocksdb.memory.managed: true  # This bounds RocksDB memory!
```

```yaml
# Kubernetes deployment
resources:
  requests:
    memory: "8Gi"
  limits:
    memory: "8Gi"    # MUST equal taskmanager.memory.process.size
```

### Prevention
- **ALWAYS** set `state.backend.rocksdb.memory.managed: true`
- Set K8s memory limit = `taskmanager.memory.process.size` (exactly equal)
- Add 10% overhead buffer with `jvm-overhead.fraction`
- Monitor `container_memory_working_set_bytes / limit` — alert at 85%

---

## Issue #16: Java Heap OOM (java.lang.OutOfMemoryError: Java heap space)

**Severity**: 🔴 Critical  
**Frequency**: High  
**Impact**: TaskManager crashes, job restarts

### Symptoms
```
java.lang.OutOfMemoryError: Java heap space
  at java.util.Arrays.copyOf(Arrays.java:3210)
  at java.util.ArrayList.grow(ArrayList.java:265)
  at com.company.MyOperator.processElement(MyOperator.java:45)
```

### Root Cause
1. **User code accumulating data**: Unbounded collections in operator
2. **Large window state on heap**: Using HashMapStateBackend with large windows
3. **Deserialization explosion**: Single large message deserialized into many objects
4. **Memory leak**: Caching without eviction, connection pool not releasing

### Diagnosis
```bash
# Heap dump on OOM (add to JVM opts)
# -XX:+HeapDumpOnOutOfMemoryError -XX:HeapDumpPath=/tmp/heapdump.hprof

# Analyze heap dump
jmap -histo <pid> | head -30

# Live heap analysis
jcmd <pid> GC.class_histogram | head -20
```

### Fix
```java
// Bad: Accumulating in memory
List<Event> buffer = new ArrayList<>();  // Grows unbounded!
buffer.add(event);

// Good: Use Flink state (backed by RocksDB)
ListState<Event> buffer = getRuntimeContext().getListState(
    new ListStateDescriptor<>("buffer", Event.class));
buffer.add(event);

// Good: Bounded buffer with eviction
if (buffer.get().spliterator().estimateSize() > MAX_SIZE) {
    flush(buffer, out);
    buffer.clear();
}
```

### Prevention
- Use RocksDB state backend (offloads state from heap)
- Never use unbounded Java collections in operators
- Set `-Xmx` appropriately (Flink does this automatically with memory config)
- Profile with `-XX:NativeMemoryTracking=summary`

---

## Issue #17: Metaspace OOM (java.lang.OutOfMemoryError: Metaspace)

**Severity**: 🔴 Critical  
**Frequency**: Medium  
**Impact**: TaskManager crashes, cannot load new classes

### Symptoms
```
java.lang.OutOfMemoryError: Metaspace
  at java.lang.ClassLoader.defineClass1(Native Method)
```
- Happens after many job restarts (classloader leak)
- Happens with many UDFs or complex Flink SQL queries

### Root Cause
1. **Classloader leak**: Job classloader not garbage collected after job cancel
2. **Flink SQL codegen**: Each SQL query generates new classes
3. **Many UDF registrations**: Each UDF loads classes
4. **Groovy/Script compilation**: Dynamic code generation

### Diagnosis
```bash
# Check metaspace usage
jcmd <pid> VM.native_memory summary | grep -i metaspace

# Check loaded class count
jstat -class <pid>

# Check for classloader leaks
jmap -clstats <pid> | sort -k3 -n -r | head -20
```

### Fix
```yaml
# Increase metaspace
taskmanager.memory.jvm-metaspace.size: 512m  # Default 256m

# Enable class unloading
env.java.opts.taskmanager: >-
  -XX:+ClassUnloadingWithConcurrentMark
  -XX:MaxMetaspaceSize=512m
  -XX:MetaspaceSize=256m

# For Flink SQL: limit codegen cache
table.exec.codegen.cache.max-entries: 1000
```

### Prevention
- Set metaspace to 512MB for jobs using Flink SQL
- Monitor `jvm_ClassLoading_LoadedClassCount` metric
- Prefer child-first classloader to reduce shared state

---

## Issue #18: GC Pause Causing Heartbeat Timeout

**Severity**: 🔴 Critical  
**Frequency**: High  
**Impact**: TM considered dead, tasks restarted unnecessarily

### Symptoms
```
WARN  HeartbeatManagerImpl - Heartbeat from TaskManager tm-xxx timed out.
INFO  SlotManagerImpl - TaskManager tm-xxx is not reachable. Releasing slots.
```
- GC log shows Full GC > heartbeat timeout (default 50s)
- Job restarts even though TM is "healthy"
- After restart, same pattern repeats

### Root Cause
Full GC pause (or long young GC) exceeds heartbeat timeout:
- 4GB+ heap with default G1GC settings
- Large young generation causing long minor GC
- Old gen filling up triggering Full GC (minutes for large heaps)
- System GC triggered by `System.gc()` from user code or libraries

### Diagnosis
```bash
# Check GC logs
grep -E "GC pause|Full GC" /opt/flink/log/gc.log | tail -20

# Check GC stats
jstat -gcutil <pid> 1000 10

# Check if pause > heartbeat timeout
# heartbeat.timeout default = 50000ms
# GC pause > 50s = heartbeat timeout!
```

### Fix
```yaml
# 1. Increase heartbeat timeout (immediate relief)
heartbeat.timeout: 180000     # 3 min (allows for GC pauses)
heartbeat.interval: 10000     # 10s probe interval

# 2. Tune GC for low pause (proper fix)
env.java.opts.taskmanager: >-
  -XX:+UseG1GC
  -XX:MaxGCPauseMillis=100
  -XX:G1HeapRegionSize=32m
  -XX:InitiatingHeapOccupancyPercent=45
  -XX:G1ReservePercent=15
  -XX:ConcGCThreads=4
  -XX:ParallelGCThreads=8
  -XX:+ExplicitGCInvokesConcurrent

# 3. Reduce heap size (less to collect)
taskmanager.memory.task.heap.size: 2048m    # Keep small
taskmanager.memory.managed.fraction: 0.5     # Push to off-heap/managed
```

### Prevention
- Keep task heap < 4GB (use RocksDB for state, not heap)
- Use G1GC with 100ms pause target
- Set heartbeat timeout to 3× max expected GC pause
- Disable `System.gc()`: `-XX:+DisableExplicitGC`

---

## Issue #19: Direct Memory OOM (java.lang.OutOfMemoryError: Direct buffer memory)

**Severity**: 🔴 Critical  
**Frequency**: Medium  
**Impact**: TaskManager crashes

### Symptoms
```
java.lang.OutOfMemoryError: Direct buffer memory
  at java.nio.Bits.reserveMemory(Bits.java:694)
  at java.nio.DirectByteBuffer.<init>(DirectByteBuffer.java:123)
```

### Root Cause
1. **Network buffer pool exhausted**: Too many concurrent connections
2. **Netty memory leak**: Unreleased ByteBuf objects
3. **External library using direct memory**: Kafka client, S3 client, Avro
4. **Misconfigured network memory**: Too small for parallelism

### Diagnosis
```bash
# Check direct memory usage
jcmd <pid> VM.native_memory summary | grep -i direct

# Check buffer pool metrics
jcmd <pid> VM.flags | grep MaxDirectMemorySize

# Monitor network buffers
# flink_taskmanager_Status_Shuffle_Netty_UsedMemorySegments
# flink_taskmanager_Status_Shuffle_Netty_AvailableMemorySegments
```

### Fix
```yaml
# Increase network memory
taskmanager.memory.network.fraction: 0.15     # 15% of Flink memory
taskmanager.memory.network.min: 256m
taskmanager.memory.network.max: 2048m

# Increase framework off-heap (for internal buffers)
taskmanager.memory.framework.off-heap.size: 256m

# Increase direct memory explicitly
env.java.opts.taskmanager: "-XX:MaxDirectMemorySize=2g"

# Reduce buffers per channel if many connections
taskmanager.network.memory.buffers-per-channel: 2      # Default 2
taskmanager.network.memory.floating-buffers-per-gate: 8  # Reduce from 256
```

### Prevention
- Calculate network memory: `parallelism × channels × buffer_size`
- Monitor `Shuffle_Netty_UsedMemorySegments` percentage
- Don't create direct ByteBuffers in user code

---

## Issue #20: RocksDB Native Memory Growing Beyond Managed Memory Limit

**Severity**: 🟡 Warning  
**Frequency**: Medium  
**Impact**: Container OOMKilled, checkpoint failure

### Symptoms
- `container_memory_working_set_bytes` grows despite stable Java heap
- Native memory (RSS - heap) keeps increasing
- Eventually OOMKilled without Java OOM in logs

### Root Cause
RocksDB uses native memory for:
- Block cache (LRU cache for data blocks)
- Memtables (write buffers)
- Table readers (index/filter blocks)
- Bloom filters (loaded into memory)

If `state.backend.rocksdb.memory.managed: false`, RocksDB is unbounded!

### Diagnosis
```bash
# Check native memory vs heap
# RSS (total) - Java heap = native memory (RocksDB + other)
cat /proc/<pid>/status | grep -E "VmRSS|VmSize"
jcmd <pid> VM.native_memory summary | grep "Total:"

# Check RocksDB memory estimate (if metrics enabled)
# flink_taskmanager_job_task_operator_rocksdb_estimate_table_readers_mem
# flink_taskmanager_job_task_operator_rocksdb_block_cache_usage
```

### Fix
```yaml
# CRITICAL: Bind RocksDB to managed memory
state.backend.rocksdb.memory.managed: true

# Control memory distribution within managed
state.backend.rocksdb.memory.write-buffer-ratio: 0.5     # 50% for write buffers
state.backend.rocksdb.memory.high-prio-pool-ratio: 0.1   # 10% for index/filter

# Ensure managed memory is large enough
taskmanager.memory.managed.fraction: 0.4  # 40% of Flink memory
```

### Prevention
- **NEVER** run production without `state.backend.rocksdb.memory.managed: true`
- Size managed memory to at least: `num_states × (block_cache + write_buffers)`
- Monitor native memory growth rate

---

## Issue #21: Off-Heap Memory Leak in User Code

**Severity**: 🟡 Warning  
**Frequency**: Medium  
**Impact**: Slow memory growth leading to eventual OOM

### Symptoms
- Memory grows 1-5MB/hour steadily
- No Java heap issue (GC healthy)
- Pod OOMKilled after days/weeks of running
- RSS keeps growing

### Root Cause
Common leak sources in user code:
1. **Unclosed HTTP clients** (Apache HttpClient, OkHttp connection pool)
2. **JDBC connections** not returned to pool
3. **Kryo serializer instances** cached without limit
4. **Thread-local variables** growing with thread pool
5. **gRPC channels** not shut down

### Diagnosis
```bash
# Track RSS growth over time
while true; do
  echo "$(date): $(cat /proc/<pid>/status | grep VmRSS)"
  sleep 60
done

# Use jemalloc for allocation tracking
export MALLOC_CONF="prof:true,prof_prefix:/tmp/heap"
# Analyze with jeprof

# Check thread count growth
jstack <pid> | grep "Thread" | wc -l
```

### Fix
```java
// Always close resources in open/close lifecycle
public class MyFunction extends RichMapFunction<In, Out> {
    private transient HttpClient client;
    
    @Override
    public void open(Configuration params) {
        client = HttpClient.newBuilder()
            .connectTimeout(Duration.ofSeconds(5))
            .build();
    }
    
    @Override
    public void close() {
        // CRITICAL: Close in close() method
        if (client != null) {
            ((AutoCloseable) client).close();
        }
    }
}
```

### Prevention
- Always override `close()` in RichFunctions to release resources
- Use connection pools with max size limits
- Monitor RSS growth rate (alert if > 10MB/hour)
- Use leak detection tools (jemalloc, ASan) in staging

---

## Issue #22: Memory Fragmentation in Long-Running Jobs

**Severity**: 🟡 Warning  
**Frequency**: Medium  
**Impact**: Effective memory reduced, GC overhead increases

### Symptoms
- Job running fine for weeks then starts GC thrashing
- Heap usage shows saw-tooth pattern getting taller
- Full GC happening more frequently
- Old gen filling up despite no state growth

### Root Cause
Long-running JVMs suffer memory fragmentation:
- Objects of various sizes allocated/freed leave holes
- G1GC region fragmentation after weeks
- Humongous objects (> 50% G1 region) not collected efficiently
- Serialization buffers causing old-gen promotion

### Fix
```yaml
env.java.opts.taskmanager: >-
  -XX:+UseG1GC
  -XX:G1HeapRegionSize=16m
  -XX:G1MixedGCLiveThresholdPercent=85
  -XX:G1HeapWastePercent=5
  -XX:G1MixedGCCountTarget=16
  -XX:MaxGCPauseMillis=100
  -XX:+UseStringDeduplication
```

### Prevention
- Use G1GC with 16-32MB regions (matches Flink's buffer sizes)
- Schedule periodic savepoint + restart (monthly) to "defragment"
- Avoid humongous allocations in user code (objects > 50% of G1 region)

---

## Issue #23: TaskManager Slot Memory Imbalance

**Severity**: 🟡 Warning  
**Frequency**: Medium  
**Impact**: Some slots OOM while others have spare memory

### Symptoms
- Only specific slots (subtasks) cause OOM
- Memory distribution uneven across slots in same TM
- Hot keys causing one subtask to accumulate more state

### Root Cause
All slots share the same JVM heap. Heavy keys cause:
- One slot's state consuming 80% of heap
- Other slots starved of memory
- No isolation between slots within same TM

### Fix
```yaml
# Reduce slots per TM (more isolation)
taskmanager.numberOfTaskSlots: 1  # 1 slot = 1 TM (full isolation)

# Or increase TM count with fewer slots
taskmanager.numberOfTaskSlots: 2  # Max 2 slots sharing memory

# For hot key: split the key space
# See Issue #30 (Hot Keys)
```

### Prevention
- Use 1-2 slots per TM for production (better isolation)
- Monitor per-operator state size to detect skew
- Pre-shard hot keys before processing

---

## Issue #24: Memory Pressure from Large Messages

**Severity**: 🟡 Warning  
**Frequency**: Medium  
**Impact**: GC spikes, temporary backpressure, latency

### Symptoms
- Sporadic GC pauses when large messages arrive
- Young gen collections spike
- Network buffers temporarily exhausted

### Root Cause
Single large messages (> 1MB) cause:
- Large allocation in young gen → immediate tenuring to old gen
- Multiple network buffers consumed for single record
- Deserialization creating many temporary objects

### Diagnosis
```bash
# Check max record size
# Add custom metric in your operator:
getRuntimeContext().getMetricGroup()
    .histogram("record-size", new DescriptiveStatisticsHistogram(1000));
```

### Fix
```java
// Filter/split large messages before processing
public class LargeMessageSplitter extends FlatMapFunction<byte[], byte[]> {
    private static final int MAX_RECORD_SIZE = 1_000_000; // 1MB
    
    @Override
    public void flatMap(byte[] value, Collector<byte[]> out) {
        if (value.length > MAX_RECORD_SIZE) {
            // Split into chunks or route to side output for special handling
            for (int i = 0; i < value.length; i += MAX_RECORD_SIZE) {
                out.collect(Arrays.copyOfRange(value, i, 
                    Math.min(i + MAX_RECORD_SIZE, value.length)));
            }
        } else {
            out.collect(value);
        }
    }
}
```

```yaml
# Increase network buffer size for large messages
taskmanager.memory.segment-size: 64kb  # Default 32kb, increase for large records
```

### Prevention
- Validate message sizes at source (Kafka max.message.bytes)
- Set Kafka `max.request.size` to reasonable limit
- Monitor record size distribution

---

## Issue #25: Excessive Object Creation Causing GC Thrash

**Severity**: 🟡 Warning  
**Frequency**: Medium  
**Impact**: High GC overhead, reduced throughput

### Symptoms
- GC overhead > 20% of total time
- Young gen collections happening multiple times per second
- Throughput lower than expected for given resources

### Root Cause
User code creating excessive short-lived objects:
- String concatenation in loops
- Boxing/unboxing primitives
- Creating new objects per record instead of reusing
- Logging with string interpolation at DEBUG level

### Fix
```java
// Bad: Creates new objects per record
public void processElement(Event event, Context ctx, Collector<Result> out) {
    String key = event.getUser() + ":" + event.getRegion();  // New String
    Map<String, Object> map = new HashMap<>();               // New Map per record!
    Result result = new Result(key, map);                     // New Result
    out.collect(result);
}

// Good: Reuse objects
private final StringBuilder keyBuilder = new StringBuilder();
private final Result reusableResult = new Result();

public void processElement(Event event, Context ctx, Collector<Result> out) {
    keyBuilder.setLength(0);
    keyBuilder.append(event.getUser()).append(':').append(event.getRegion());
    
    reusableResult.setKey(keyBuilder.toString());
    reusableResult.setData(event.getData());
    out.collect(reusableResult);  // Flink serializes immediately, safe to reuse
}
```

### Prevention
- Profile GC allocation rate in staging
- Use object reuse where safe: `env.getConfig().enableObjectReuse()`
- Avoid String concatenation — use StringBuilder
- Minimize boxing (use primitive arrays where possible)

---

## Issue #26: Container Resource Limits Too Tight for Startup

**Severity**: 🟡 Warning  
**Frequency**: Medium  
**Impact**: Pod fails to start, CrashLoopBackOff

### Symptoms
```
CrashLoopBackOff - Pod killed during state restore
```
- TM OOMKilled during checkpoint restore (needs more memory for loading state)
- Startup requires more resources than steady-state
- Burst of class loading at startup fills metaspace

### Root Cause
During startup/restore, Flink needs extra memory for:
- Loading all state from checkpoint (temporary buffers)
- Initializing RocksDB (bulk loading SST files)
- JIT compilation surge (code cache)
- Class loading (metaspace)
- All operators initializing simultaneously

### Fix
```yaml
# Option 1: K8s burstable QoS (request < limit)
resources:
  requests:
    memory: "6Gi"    # Steady state
    cpu: "2"
  limits:
    memory: "10Gi"   # Burst during startup
    cpu: "4"

# Option 2: Increase base memory to handle startup
taskmanager.memory.process.size: 10240m
taskmanager.memory.jvm-overhead.max: 1536m  # Extra for startup

# Option 3: Tune restore parallelism
state.backend.rocksdb.checkpoint.transfer.thread.num: 2  # Fewer concurrent downloads
```

### Prevention
- Test with largest expected checkpoint restore
- Set limits 20-30% above steady-state usage
- Monitor memory during restart events
- Use Vertical Pod Autoscaler (VPA) to find optimal sizes
