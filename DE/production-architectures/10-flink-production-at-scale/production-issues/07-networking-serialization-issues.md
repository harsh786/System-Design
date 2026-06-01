# Networking & Serialization Issues (#77-86)

> Network and serialization issues manifest as mysterious throughput drops, connection failures, and data corruption at scale.

---

## Issue #77: Network Buffer Exhaustion

**Severity**: 🔴 Critical  
**Frequency**: Medium-High  
**Impact**: Processing stops, severe backpressure

### Symptoms
```
java.io.IOException: Insufficient number of network buffers:
  required 65, but only 32 available
```
- Job fails to start or crashes during rescale
- Backpressure on all operators
- `Shuffle_Netty_AvailableMemorySegments` = 0

### Root Cause
Network buffers are pre-allocated at job start. Required buffers depend on:
- `parallelism × (buffers_per_channel + floating_buffers_per_gate)`
- With high parallelism and many operators, buffer count explodes

Formula: `required = subtasks × channels_per_subtask × buffers_per_channel + gates × floating_buffers`

### Fix
```yaml
# Increase network memory
taskmanager.memory.network.fraction: 0.2       # 20% of Flink memory (default 10%)
taskmanager.memory.network.min: 256m
taskmanager.memory.network.max: 2048m

# Reduce per-channel buffers (trade latency for memory)
taskmanager.network.memory.buffers-per-channel: 2    # Default 2, minimum 0
taskmanager.network.memory.floating-buffers-per-gate: 8  # Default 8

# For very high parallelism: reduce slots per TM
taskmanager.numberOfTaskSlots: 2  # Fewer slots = fewer channels needed
```

### Prevention
- Calculate required buffers before deployment: `parallelism² × buffer_count`
- Use fewer slots per TM for high-parallelism jobs
- Monitor `AvailableMemorySegments` and alert when < 20% available

---

## Issue #78: Connection Refused Between TaskManagers

**Severity**: 🔴 Critical  
**Frequency**: Medium  
**Impact**: Network shuffle fails, job crashes

### Symptoms
```
java.net.ConnectException: Connection refused: tm-host:data-port
ERROR NettyPartitionRequestClient - Connection to [...] failed
```
- Happens during job start or after TM restart
- New TM not yet listening on data port when connections attempted

### Root Cause
1. TM data port not yet bound when connections arrive (race condition)
2. Network policy blocking inter-TM communication
3. Security group/firewall blocking data port range
4. TM crashed and not yet restarted

### Fix
```yaml
# Increase connection retry
taskmanager.network.request-backoff.initial: 100    # Start with 100ms
taskmanager.network.request-backoff.max: 10000      # Max 10s backoff
taskmanager.network.retries: 5

# Ensure network policy allows TM↔TM communication
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: flink-tm-communication
spec:
  podSelector:
    matchLabels:
      component: taskmanager
  ingress:
    - from:
        - podSelector:
            matchLabels:
              component: taskmanager
      ports:
        - port: 6121    # Data port
          protocol: TCP
        - port: 6122    # RPC port
          protocol: TCP
  egress:
    - to:
        - podSelector:
            matchLabels:
              component: taskmanager
```

### Prevention
- Configure appropriate backoff for network connections
- Verify network policies allow all required ports
- Use headless service for TM discovery
- Monitor connection failure rate

---

## Issue #79: SSL/TLS Handshake Failure Between Components

**Severity**: 🔴 Critical  
**Frequency**: Medium  
**Impact**: Components cannot communicate, job fails to start

### Symptoms
```
javax.net.ssl.SSLHandshakeException: PKIX path building failed
ERROR NettyClient - SSL handshake failed
```

### Root Cause
- Certificate expired
- CA not trusted by peer
- Certificate hostname mismatch (using IP instead of DNS name)
- TLS version mismatch

### Fix
```yaml
# Correct SSL configuration
security.ssl.internal.enabled: true
security.ssl.internal.keystore: /opt/flink/certs/keystore.jks
security.ssl.internal.keystore-password: ${SSL_KEYSTORE_PASSWORD}
security.ssl.internal.truststore: /opt/flink/certs/truststore.jks
security.ssl.internal.truststore-password: ${SSL_TRUSTSTORE_PASSWORD}
security.ssl.internal.key-password: ${SSL_KEY_PASSWORD}

# Ensure cert-manager auto-rotates certificates
# Mount from Secret with proper update policy
volumes:
  - name: flink-certs
    secret:
      secretName: flink-internal-tls
```

### Prevention
- Use cert-manager with auto-rotation (90-day certs, rotate at 60)
- Monitor certificate expiry dates
- Use mTLS with SAN entries for both DNS and IP

---

## Issue #80: Kryo Serialization Fallback Performance

**Severity**: 🟡 Warning  
**Frequency**: High  
**Impact**: 3-10x slower serialization, larger state/network usage

### Symptoms
```
WARN TypeExtractor - Class MyComplexEvent is not serializable with Flink's 
  own serializer. Falling back to Kryo.
```
- Throughput 50-70% of expected
- Checkpoint size larger than expected
- Flame graph shows significant time in Kryo

### Root Cause
Flink's efficient POJO serializer requires:
- Public class with public no-arg constructor
- All fields accessible (public or getter/setter)
- No inheritance hierarchy (or properly annotated)
- Fields are Flink-serializable types

If ANY condition fails → Kryo fallback (reflection-based, slow)

### Fix
```java
// Fix 1: Make class POJO-compliant
// Bad:
public class Event {
    private final String id;  // No setter + final = not a POJO!
    Event(String id) { this.id = id; }
}

// Good:
public class Event {
    public String id;       // Public field
    public long timestamp;
    public double amount;
    
    public Event() {}       // Public no-arg constructor
    
    // OR: private fields with getters/setters
    // private String id;
    // public String getId() { return id; }
    // public void setId(String id) { this.id = id; }
}

// Fix 2: Register Kryo serializer (if can't change class)
env.getConfig().registerTypeWithKryoSerializer(
    ThirdPartyEvent.class, ThirdPartyEventSerializer.class);

// Fix 3: Disable generic types to catch issues early
env.getConfig().disableGenericTypes();  // Throws exception instead of Kryo fallback
```

### Prevention
- Call `env.getConfig().disableGenericTypes()` during development
- Follow POJO rules for all data types
- Use Avro/Protobuf generated classes (always efficient)
- Test serialization speed in benchmarks

---

## Issue #81: Large State Access Latency with RocksDB

**Severity**: 🟡 Warning  
**Frequency**: Medium  
**Impact**: Per-record processing latency high (>1ms)

### Symptoms
- Processing latency dominated by state access (not computation)
- RocksDB `get` operations taking 100μs-10ms
- Block cache miss rate high
- State key format unnecessarily complex

### Root Cause
RocksDB access involves:
1. Key serialization → byte[]
2. MemTable lookup (fast, O(log N) per table)
3. Block cache lookup (fast if hit)
4. SST file read from disk (slow, 100μs+ on SSD)
5. Value deserialization ← byte[]

If block cache miss rate is high, every access hits disk.

### Fix
```yaml
# Increase block cache size
state.backend.rocksdb.block.cache-size: 512mb    # Default: managed memory shared

# Enable bloom filters (avoid unnecessary disk reads)
state.backend.rocksdb.bloom-filter.bits-per-key: 10
state.backend.rocksdb.bloom-filter.block-based: false  # Full filter, more memory but faster

# Optimize for point lookups
state.backend.rocksdb.options-factory: org.apache.flink.contrib.streaming.state.PredefinedOptions.SPINNING_DISK_OPTIMIZED_HIGH_MEM
```

```java
// Reduce key/value size
// Bad: Large composite key
MapState<String, ComplexObject> state;  // Key: "user:region:product:timestamp"

// Good: Minimal key, structured value
MapState<Long, CompactResult> state;    // Key: hash, Value: flat struct
```

### Prevention
- Size block cache to hold working set (80%+ hit rate target)
- Use bloom filters for MapState/ValueState
- Keep state keys short (fewer bytes = faster lookup)
- Monitor RocksDB cache hit rate metric

---

## Issue #82: Netty Thread Pool Exhaustion

**Severity**: 🟡 Warning  
**Frequency**: Low-Medium  
**Impact**: Network communication stalls

### Symptoms
- Network shuffle throughput drops to 0
- Netty event loop threads all busy
- Connection establishment takes very long
- Thread dump shows Netty threads stuck

### Root Cause
Netty server/client threads blocked by slow operations:
- Expensive computation in I/O thread (should be in task thread)
- Too many concurrent connections for default thread count
- SSL handshake taking too long

### Fix
```yaml
# Increase Netty threads
taskmanager.network.netty.server.numThreads: 4   # Default: number of slots
taskmanager.network.netty.client.numThreads: 4
taskmanager.network.netty.transport: epoll       # Use epoll on Linux (faster)

# Connection pooling
taskmanager.network.netty.client.connectTimeoutSec: 30
taskmanager.network.netty.sendReceiveBufferSize: 0  # OS default
```

### Prevention
- Use epoll transport on Linux (faster than NIO)
- Monitor Netty thread utilization
- Don't do expensive work in network callbacks

---

## Issue #83: Record Serialization Size Exceeding Network Buffer

**Severity**: 🟡 Warning  
**Frequency**: Medium  
**Impact**: Single large record blocks network buffer

### Symptoms
```
java.io.IOException: Record is too large to be serialized into a network buffer.
  Record size: 50MB, buffer size: 32KB
```

### Root Cause
Single serialized record larger than network buffer segment (default 32KB):
- Very large strings/blobs in events
- Serialized collection with thousands of elements
- Binary payload embedded in event

### Fix
```yaml
# Increase segment size (affects all buffers - more memory needed)
taskmanager.memory.segment-size: 1mb  # Default 32kb, increase for large records
```

```java
// Better: Don't put large data in stream records
// Store large payloads externally, pass reference
public class EventReference {
    public String eventId;
    public String s3Path;      // Large payload stored in S3
    public long payloadSize;
    // Actual processing only needs metadata
}
```

### Prevention
- Validate max record size at source
- Store large payloads externally (S3/blob store)
- Pass references, not full payloads through Flink
- Set max message size limits in Kafka producer

---

## Issue #84: Checkpoint Data Corruption During Network Transfer

**Severity**: 🔴 Critical  
**Frequency**: Rare  
**Impact**: Checkpoint restore fails, data integrity risk

### Symptoms
```
IOException: Corrupted checkpoint data - checksum mismatch
```
- Happens on unreliable networks
- More common in cross-datacenter setups

### Fix
```yaml
# Enable data transfer verification
state.backend.rocksdb.checkpoint.transfer.thread.num: 4
fs.s3a.multipart.purge: true
fs.s3a.multipart.purge.age: 86400  # Clean failed uploads after 1 day

# Use checksums
execution.checkpointing.data-integrity.enabled: true  # Flink 1.18+
```

### Prevention
- Enable S3 checksum verification
- Use reliable storage (S3, GCS) not local disk for checkpoints
- Monitor checkpoint restore success rate
- Keep multiple checkpoint copies

---

## Issue #85: ClassNotFoundException During Deserialization

**Severity**: 🟡 Warning  
**Frequency**: Medium  
**Impact**: Cannot deserialize state/records, job fails

### Symptoms
```
java.lang.ClassNotFoundException: com.company.events.MyEventV1
```
- Happens after class rename/move
- Happens with classloader issues in YARN/K8s
- State contains serialized objects with old class names

### Root Cause
1. Class renamed/moved but state still contains old class name
2. JAR not properly deployed to all TaskManagers
3. Child-first classloader loading wrong version
4. Serialization UID changed (Kryo or Java serialization)

### Fix
```java
// Register class migration
env.getConfig().addDefaultKryoSerializer(
    OldClassName.class, NewClassSerializer.class);

// Use alias for moved classes
@SerialVersionUID(1L)
public class MyEvent implements Serializable {
    private static final long serialVersionUID = 1L;  // Keep stable!
}
```

```yaml
# Classloader configuration
classloader.resolve-order: parent-first  # Or child-first, be consistent
classloader.parent-first-patterns.additional: com.company.shared
```

### Prevention
- Never rename classes used in state without migration
- Keep `serialVersionUID` stable
- Use Avro/Protobuf for state (schema evolution built-in)
- Test state restore after class changes

---

## Issue #86: High Latency Variance Between Subtasks (Network Jitter)

**Severity**: 🟡 Warning  
**Frequency**: Medium  
**Impact**: Uneven processing, stragglers slow down overall

### Symptoms
- Some subtasks consistently slower than others
- Network round-trip time varies significantly
- Cross-AZ communication causing latency

### Root Cause
- TMs deployed across availability zones (cross-AZ latency: 1-5ms vs same-AZ: 0.1ms)
- Network bandwidth shared with other workloads
- Noisy neighbor on shared network

### Fix
```yaml
# Prefer same-zone scheduling
affinity:
  podAffinity:
    preferredDuringSchedulingIgnoredDuringExecution:
      - weight: 100
        podAffinityTerm:
          topologyKey: topology.kubernetes.io/zone
          labelSelector:
            matchLabels:
              app: flink

# Use topology-aware scheduling
topologySpreadConstraints:
  - maxSkew: 2
    topologyKey: topology.kubernetes.io/zone
    whenUnsatisfiable: ScheduleAnyway
```

### Prevention
- Deploy Flink cluster in single AZ for latency-critical jobs
- Use pod affinity to keep communicating TMs close
- Monitor per-subtask network latency
- Use dedicated network bandwidth (ENA Express, EFA)
