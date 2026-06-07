# GC Deep Dive & Memory Analysis — Advanced JVM Topics

## 1. Object Allocation Path (TLAB → Eden → Survivor → Old)

### Thread-Local Allocation Buffers (TLAB)

Each thread gets its own private region inside Eden — allocation is just a pointer bump (no synchronization).

```
Thread 1 TLAB: [obj1][obj2][obj3][── free space ──]
                                   ↑ allocation pointer (just increment)

Thread 2 TLAB: [obj1][obj2][── free space ────────]
                            ↑ allocation pointer
```

**Why TLABs matter:**
- Without TLAB: every `new Object()` needs Compare-And-Swap (CAS) → thread contention
- With TLAB: just bump pointer (single CPU instruction, no sync)
- Result: object allocation is essentially free (~10 nanoseconds)

**TLAB lifecycle:**
1. Thread requests TLAB from Eden (CAS once for the whole TLAB)
2. Thread allocates objects by bumping pointer (no sync needed)
3. TLAB full → request new TLAB
4. Object doesn't fit in TLAB remainder → allocate directly in Eden (CAS)

**Sizing:**
```
-XX:TLABSize=512k          # Initial TLAB size (rarely need to set)
-XX:+ResizeTLAB            # Adaptive sizing (default: on)
-XX:TLABWasteTargetPercent=1  # Max wasted TLAB space per refill

# Diagnostic:
-XX:+PrintTLAB             # Print TLAB statistics per GC
```

### Complete Allocation Decision Flow

```
new Object()
    │
    ├─ Fits in current TLAB?
    │    YES → bump pointer (fastest, zero contention)
    │
    ├─ TLAB full, object fits in new TLAB?
    │    YES → allocate new TLAB from Eden (CAS), then bump pointer
    │
    ├─ Object > TLAB waste threshold but fits in Eden?
    │    YES → allocate directly in Eden (CAS)
    │
    ├─ Object > humongous threshold? (G1: >50% region size)
    │    YES → allocate in Old Gen / Humongous region(s)
    │
    └─ Eden full?
         YES → trigger Minor GC → retry allocation
```

### Escape Analysis & Stack Allocation

```java
// JIT detects: this Point NEVER escapes the method
public int distanceFromOrigin(int x, int y) {
    Point p = new Point(x, y);  // allocated on STACK (no GC needed!)
    return (int) Math.sqrt(p.x * p.x + p.y * p.y);
}

// After scalar replacement (JIT optimization):
// Equivalent to:
public int distanceFromOrigin(int x, int y) {
    return (int) Math.sqrt(x * x + y * y);  // no object at all!
}

// Object ESCAPES if:
// - Assigned to a field (this.point = p)
// - Passed to another method that stores it
// - Returned from method
// - Assigned to a static field
// - Stored in array that escapes
```

---

## 2. Reference Types (Strong, Soft, Weak, Phantom)

### Strong Reference (Default)

```java
Object obj = new Object();  // strong reference
// GC will NEVER collect obj while this reference exists
// This is what causes memory leaks: holding references you don't need
obj = null;  // now eligible for GC
```

### Soft Reference

```java
import java.lang.ref.SoftReference;

// Collected ONLY when JVM is about to throw OutOfMemoryError
// JVM guarantees: all soft references cleared before OOM
// Typically collected LRU (least recently accessed first)

SoftReference<byte[]> cache = new SoftReference<>(new byte[10_000_000]);

byte[] data = cache.get();  // returns the byte[] or null if collected
if (data == null) {
    // reload from disk/network
    data = loadFromDisk();
    cache = new SoftReference<>(data);
}
```

**Memory-sensitive cache implementation:**

```java
import java.lang.ref.SoftReference;
import java.util.*;

public class SoftCache<K, V> {
    private final Map<K, SoftReference<V>> map = new HashMap<>();

    public void put(K key, V value) {
        map.put(key, new SoftReference<>(value));
    }

    public V get(K key) {
        SoftReference<V> ref = map.get(key);
        if (ref == null) return null;
        V value = ref.get();
        if (value == null) {
            map.remove(key);  // clean up dead entry
        }
        return value;
    }

    public void cleanup() {
        map.entrySet().removeIf(e -> e.getValue().get() == null);
    }
}
```

**Flag:** `-XX:SoftRefLRUPolicyMSPerMB=1000` (default)
- Soft references survive (freeMB × ms_per_mb) milliseconds after last access
- Lower value → more aggressive collection

### Weak Reference

```java
import java.lang.ref.WeakReference;

// Collected at NEXT GC cycle (regardless of memory)
// Use case: associate metadata with object without preventing its GC

Object key = new Object();
WeakReference<Object> weakRef = new WeakReference<>(key);

System.out.println(weakRef.get());  // Object@...
key = null;  // remove strong reference
System.gc();  // trigger GC
System.out.println(weakRef.get());  // null (collected!)
```

**WeakHashMap — the classic use case:**

```java
import java.util.WeakHashMap;
import java.util.Map;

// Keys are held as WeakReferences
// When key has no more strong references → entry is automatically removed
Map<Object, String> metadata = new WeakHashMap<>();

Object widget = new Object();
metadata.put(widget, "some metadata about this widget");
System.out.println(metadata.size());  // 1

widget = null;  // no more strong references to key
System.gc();
// After GC, the entry is removed:
System.out.println(metadata.size());  // 0
```

**Real use case — ClassLoader metadata, listener registries:**
```java
// Framework tracks listeners without preventing their GC:
private final Map<Object, List<Listener>> listenerRegistry = new WeakHashMap<>();

public void addListener(Object source, Listener listener) {
    listenerRegistry.computeIfAbsent(source, k -> new ArrayList<>()).add(listener);
    // When 'source' is no longer used → entry automatically removed
}
```

### Phantom Reference

```java
import java.lang.ref.PhantomReference;
import java.lang.ref.ReferenceQueue;

// get() ALWAYS returns null — you can never access the referent
// Enqueued AFTER object is finalized and ready for reclamation
// Use case: tracking when an object is about to be reclaimed (cleanup native resources)

ReferenceQueue<Object> queue = new ReferenceQueue<>();
Object resource = new Object();
PhantomReference<Object> phantom = new PhantomReference<>(resource, queue);

System.out.println(phantom.get());  // ALWAYS null

resource = null;
System.gc();

// After GC, phantom reference is enqueued:
PhantomReference<?> ref = (PhantomReference<?>) queue.poll();
if (ref != null) {
    // Object has been collected — perform cleanup
    System.out.println("Object was reclaimed, cleaning up native resources");
    // cleanupNativeMemory(associatedPtr);
    ref.clear();
}
```

### Cleaner API (Java 9+ — Modern replacement for finalize())

```java
import java.lang.ref.Cleaner;

public class NativeBuffer implements AutoCloseable {
    private static final Cleaner cleaner = Cleaner.create();

    private final long nativePointer;
    private final Cleaner.Cleanable cleanable;

    public NativeBuffer(int size) {
        this.nativePointer = allocateNative(size);
        // IMPORTANT: cleaning action must NOT reference 'this'!
        // Use a static inner class or separate object
        this.cleanable = cleaner.register(this, new Deallocator(nativePointer));
    }

    // Static! Must not capture 'this' — would prevent GC
    private static class Deallocator implements Runnable {
        private final long ptr;
        Deallocator(long ptr) { this.ptr = ptr; }

        @Override
        public void run() {
            freeNative(ptr);
            System.out.println("Native memory freed by Cleaner");
        }
    }

    @Override
    public void close() {
        cleanable.clean();  // Explicit cleanup (idempotent — safe to call multiple times)
    }

    private static long allocateNative(int size) { return 0; /* native alloc */ }
    private static void freeNative(long ptr) { /* native free */ }
}

// Usage:
// try-with-resources (preferred — deterministic cleanup):
try (NativeBuffer buf = new NativeBuffer(1024)) {
    // use buf
}  // close() called → cleanable.clean() → Deallocator.run()

// If close() not called → Cleaner thread eventually runs Deallocator
// (non-deterministic, but prevents leak)
```

### ReferenceQueue Pattern

```java
import java.lang.ref.*;
import java.util.*;

// Track object lifecycle and cleanup associated resources
public class ResourceTracker {
    private final ReferenceQueue<Object> queue = new ReferenceQueue<>();
    private final Map<PhantomReference<?>, Runnable> cleanupActions = new HashMap<>();

    public <T> void track(T object, Runnable cleanupAction) {
        PhantomReference<T> ref = new PhantomReference<>(object, queue);
        cleanupActions.put(ref, cleanupAction);
    }

    // Call periodically (or in dedicated thread)
    public void processQueue() {
        Reference<?> ref;
        while ((ref = queue.poll()) != null) {
            Runnable action = cleanupActions.remove(ref);
            if (action != null) {
                action.run();
            }
            ref.clear();
        }
    }
}
```

### Comparison Table

| Type | When GC'd | get() returns | ReferenceQueue? | Use Case |
|------|-----------|---------------|-----------------|----------|
| **Strong** | Never (while reachable) | N/A (direct ref) | N/A | Normal usage |
| **Soft** | Before OOM (LRU) | Object or null | Optional | Memory-sensitive caches |
| **Weak** | Next GC cycle | Object or null | Optional | Metadata maps, canonicalization |
| **Phantom** | After finalization | Always null | Required | Resource cleanup tracking |

---

## 3. Card Table & Remembered Sets

### The Problem: Cross-Generation References

```
During Minor GC, we only want to scan Young Gen.
But Old Gen objects can point to Young Gen objects!

Old Gen: [ A ] ──reference──→ [ B ] (in Young Gen)

Without tracking:
  To find all references to Young Gen objects, we'd scan entire Old Gen
  → defeats the purpose of generational GC (Young GC would be slow)
```

### Card Table Solution (Serial, Parallel GC)

```
Old Gen divided into 512-byte "cards":
┌────────┬────────┬────────┬────────┬────────┬────────┐
│ Card 0 │ Card 1 │ Card 2 │ Card 3 │ Card 4 │ Card 5 │  (each 512 bytes)
└────────┴────────┴────────┴────────┴────────┴────────┘

Card Table (1 byte per 512-byte card, ~0.2% memory overhead):
┌───┬───┬───┬───┬───┬───┐
│ 0 │ 1 │ 0 │ 0 │ 1 │ 0 │  (0=clean, 1=dirty)
└───┴───┴───┴───┴───┴───┘
      ↑               ↑
   Card 1 contains    Card 4 contains
   a reference to     a reference to
   Young Gen          Young Gen
```

**Write Barrier (injected by JIT at every reference store):**
```java
// When application code does:
oldObject.field = youngObject;

// JVM actually executes (conceptually):
oldObject.field = youngObject;
cardTable[address_of(oldObject) >> 9] = DIRTY;  // mark card dirty
// >> 9 because 512 = 2^9
```

**During Minor GC:**
1. Scan GC roots (stack, static fields)
2. Scan ONLY dirty cards in Old Gen (not entire Old Gen!)
3. This finds all Old→Young references efficiently
4. After GC: clear dirty cards (or re-check)

### Remembered Sets (G1GC — More Fine-Grained)

```
G1 uses per-region Remembered Sets:
Each region tracks: "which OTHER regions point INTO me?"

Region A (Old) ──reference──→ Region B (Young)
  └─ Region B's Remembered Set contains: {Region A, offset}

During Young GC:
- For each Young region, check its Remembered Set
- Scan only the specific locations that have references to this region
- Much more precise than card table (less scanning)

Trade-off:
- More memory: remembered sets use 5-20% of heap
- Less scanning: only look at exact locations, not entire cards
```

### G1 SATB (Snapshot-At-The-Beginning) Write Barrier

```
G1 uses TWO write barriers:

Pre-write barrier (SATB):
  Before overwriting a reference, log the OLD value
  This ensures concurrent marking doesn't miss objects
  (prevents "lost object" during concurrent mark phase)

Post-write barrier:
  After writing a cross-region reference, update remembered set
  Similar to card table but per-region
```

---

## 4. Safe Points & Time-to-Safe-Point (TTSP)

### What is a Safe Point?

A point in the code where:
- Thread state is "well-defined" for GC
- All GC roots (local variables, stack references) are known
- GC can safely inspect and relocate objects

**GC can ONLY happen when ALL application threads are at safe points.**

### Where Are Safe Points?

```
Safe points exist at:
✓ Method returns (ret bytecode)
✓ Loop back-edges (end of each loop iteration) — for non-counted loops
✓ Object allocation (new)
✓ JNI call boundaries
✓ Monitor entry/exit (synchronized)
✓ Thread.sleep(), Object.wait(), LockSupport.park()

Safe points do NOT exist inside:
✗ Counted loops with int counter and no method calls
✗ Arithmetic operations
✗ Array access in tight loops
✗ Native method execution (until return to Java)
```

### The TTSP Problem (Time-to-Safe-Point)

```java
// DANGEROUS: This counted loop has NO safepoint inside!
// JIT optimizes away safepoint checks for "counted" loops
int[] arr = new int[2_000_000_000];
for (int i = 0; i < arr.length; i++) {
    arr[i] = i * 2;  // No safepoint here!
}
// GC must wait for this ENTIRE loop to complete before it can run!
// Can cause multi-second GC pauses!

// WHY: JIT sees int counter + simple body → "counted loop optimization"
// removes safepoint poll to make loop faster

// FIX 1: Use long counter (makes it "uncounted")
for (long i = 0; i < arr.length; i++) {
    arr[(int)i] = (int)i * 2;  // Safepoints now inserted at back-edge
}

// FIX 2: Call a method inside loop (method call is safepoint)
for (int i = 0; i < arr.length; i++) {
    arr[i] = transform(i);  // method call → safepoint
}

// FIX 3: Use flag (Java 17+):
// -XX:+UseCountedLoopSafepoints (inserts safepoints in counted loops)
```

### Diagnosing TTSP issues:

```
-XX:+SafepointTimeout -XX:SafepointTimeoutDelay=2000
// Prints threads that take >2 seconds to reach safepoint

-Xlog:safepoint*=info  (Java 9+)
// Logs all safepoint activity including which threads were slow

GC log shows:
[2024-01-15T10:30:45.123][gc] Safepoint "GC", Time since last: 150ms, Reaching safepoint: 3250ms, At safepoint: 15ms
                                                                        ↑ THIS IS THE PROBLEM (TTSP too long)
```

---

## 5. GC Log Analysis

### Enabling GC Logging

```bash
# Java 9+ (Unified Logging):
-Xlog:gc*:file=gc.log:time,uptime,level,tags:filecount=5,filesize=100m

# Breakdown:
# gc*           - all gc-related tags
# file=gc.log   - output file
# time,uptime   - decorators (timestamps)
# filecount=5   - rotating log files
# filesize=100m - max 100MB per file

# More verbose:
-Xlog:gc*,gc+heap=debug,gc+phases=debug:file=gc.log:time,uptime:filecount=10,filesize=200m
```

### Reading G1GC Log Entries

```
[2024-01-15T10:30:45.123+0000][12.456s][info][gc] GC(42) Pause Young (Normal) (G1 Evacuation Pause) 512M->256M(2048M) 23.456ms
│                               │             │    │                     │                            │             │
│                               │             │    │                     │                            │             └ Pause duration
│                               │             │    │                     │                            └ Heap: used_before→used_after(committed)
│                               │             │    │                     └ Trigger reason
│                               │             │    └ GC type (Young / Mixed / Full)
│                               │             └ Log level
│                               └ Uptime
└ Wall clock time

Other entries:
GC(42) Pause Young (Concurrent Start)  → starts concurrent marking
GC(42) Pause Young (Mixed)             → mixed collection (young + old regions)
GC(42) Pause Full (Allocation Failure) → FULL GC (bad! should not happen normally)
```

### Key Metrics to Extract

```
From GC logs, calculate:

1. ALLOCATION RATE:
   = Eden size / time between Minor GCs
   Example: Eden=256MB, Minor GC every 2s → 128 MB/s allocation rate
   High allocation rate → more frequent GC

2. PROMOTION RATE:
   = Old Gen growth per Minor GC
   Example: Old Gen grows 10MB per Minor GC, 30 Minor GCs/min → 300 MB/min
   High promotion rate → objects not dying young (tune tenuring)

3. GC THROUGHPUT:
   = (Total time - Total GC pause time) / Total time × 100%
   Example: 60s total, 2s in GC → 96.7% throughput
   Target: >95% for most apps, >99% for latency-sensitive

4. PAUSE TIME DISTRIBUTION:
   p50, p90, p95, p99 of GC pauses
   Example: p50=10ms, p99=150ms → occasional long pauses to investigate
```

### Red Flags in GC Logs

```
"Pause Full" appearing:
   → Heap too small, or memory leak, or fragmentation
   → G1 couldn't keep up with allocation rate

"to-space exhausted":
   → Survivor/old regions can't hold evacuated objects
   → Need more heap or more regions

"Evacuation Failure":
   → No free regions to copy objects to
   → Triggers Full GC as fallback

Increasing pause times over time:
   → Old Gen filling up, more work each GC
   → Possible memory leak

"Humongous Allocation" frequently:
   → Many objects > 50% region size
   → Consider increasing region size (-XX:G1HeapRegionSize)
   → Or reduce large object allocations (reuse byte arrays)

High "Concurrent Mark" abort rate:
   → Allocation rate too high for concurrent marking
   → Lower InitiatingHeapOccupancyPercent to start marking earlier
```

### GC Log Analysis Tools

| Tool | Type | Features |
|------|------|----------|
| GCeasy.io | Online | Visual, automatic recommendations |
| GCViewer | Desktop (OSS) | Charts, pause statistics |
| Eclipse GC Log Analyzer | IDE Plugin | Integrated with development |
| Censum (jClarity) | Commercial | Advanced pattern detection |

---

## 6. Memory Analysis — Shallow vs Retained Size

### Definitions

```
SHALLOW SIZE: memory consumed by the object ITSELF
- Object header (12 bytes with compressed oops)
- All field values (primitives stored inline, references = 4 bytes)
- Padding to 8-byte boundary
- Does NOT include referenced objects

RETAINED SIZE: memory that would be FREED if this object were GC'd
- Includes all objects EXCLUSIVELY reachable through this object
- The actual "cost" of keeping this object alive
- This is what you care about for memory leaks

DEEP SIZE: total size of object graph (all reachable objects)
- Can double-count shared objects
- Less useful than retained size for leak analysis
```

### Visual Example

```
    HashMap map (shallow: 48 bytes)
    │
    └─── Entry[] table (shallow: 65,552 bytes for initial 16,384 slots)
         │
         ├── Entry (key="user1", value=UserObj1)
         │   ├── "user1" (48 bytes)
         │   └── UserObj1 (200 bytes)
         │
         ├── Entry (key="user2", value=UserObj2)
         │   ├── "user2" (48 bytes)
         │   └── UserObj2 (200 bytes)
         ...
         └── (10,000 entries)

Shallow size of HashMap: 48 bytes
Retained size of HashMap: 48 + 65,552 + 10,000 × (32 + 48 + 200) = ~2.87 MB
```

### Dominator Tree

```
Object A "dominates" object B if EVERY path from GC root to B goes through A.

If A is garbage-collected → B is also garbage-collected (retained)

GC Root
  └── Service (retained: 500MB) ← DOMINATOR with large retained set = SUSPECT
      ├── Cache (retained: 490MB)
      │   └── HashMap (10M entries)
      │       └── Entry[] ...
      └── Config (retained: 10MB)

In Eclipse MAT: Dominator Tree view sorts by retained size
Top entries = likely leak sources
```

---

## 7. Finalization Problems & Modern Alternatives

### Why finalize() is Dangerous

```java
// 1. RESURRECTION ATTACK:
public class EvilObject {
    static EvilObject zombie;

    @Override
    protected void finalize() {
        zombie = this;  // Object resurrects itself! GC can't collect it!
    }
}

// 2. DELAYED COLLECTION: (2+ GC cycles)
// Normal:      unreachable → collected (1 cycle)
// Finalizable: unreachable → queued → finalize() runs → THEN collected (2+ cycles)

// 3. SINGLE THREAD: Finalizer thread can fall behind
// If finalize() is slow, objects pile up in queue → OOM

// 4. NO GUARANTEE: finalize() might NEVER run (JVM exits before)

// 5. CONSTRUCTION ATTACK:
public class Insecure {
    public Insecure() {
        if (!authorized()) throw new SecurityException("nope");
    }
}
public class Attack extends Insecure {
    @Override protected void finalize() {
        // Even though constructor threw, finalize() still runs!
        // 'this' is partially constructed but accessible
    }
}
```

### Modern Pattern: AutoCloseable + Cleaner (safety net)

```java
public class DatabaseConnection implements AutoCloseable {
    private static final Cleaner cleaner = Cleaner.create();
    private final Connection conn;
    private final Cleaner.Cleanable cleanable;

    public DatabaseConnection(String url) throws SQLException {
        this.conn = DriverManager.getConnection(url);
        this.cleanable = cleaner.register(this, new CloseAction(conn));
    }

    // Static class — MUST NOT reference outer 'this'
    private static class CloseAction implements Runnable {
        private final Connection conn;
        CloseAction(Connection conn) { this.conn = conn; }
        @Override public void run() {
            try { conn.close(); } catch (SQLException e) { /* log */ }
            System.err.println("WARNING: Connection was not explicitly closed!");
        }
    }

    @Override
    public void close() throws SQLException {
        conn.close();
        cleanable.clean();  // Cancel the cleaner action
    }
}

// Preferred: explicit close with try-with-resources
try (var db = new DatabaseConnection("jdbc:...")) {
    db.query("...");
}  // close() called deterministically

// Safety net: if someone forgets close(), Cleaner eventually runs
```

---

## 8. Compressed Oops & Object Layout

### Object Pointer Compression

```
64-bit JVM without compressed oops:
  Every reference = 8 bytes → ~50% more memory than 32-bit JVM

With compressed oops (-XX:+UseCompressedOops):
  Every reference = 4 bytes
  Addresses decoded as: (compressed_oop << 3) + heap_base
  Because all objects are 8-byte aligned, bottom 3 bits are always 000
  So we store (address >> 3) in 4 bytes → addresses 2^35 = 32 GB

  Enabled by default for heaps < 32GB
  Above 32GB → falls back to 8-byte references (significant memory jump!)

Recommendation:
  -Xmx31g is better than -Xmx33g
  (31GB with compressed oops uses LESS memory than 33GB without!)
```

### Detailed Object Layout (JOL)

```java
// Add dependency: org.openjdk.jol:jol-core:0.17
import org.openjdk.jol.info.ClassLayout;
import org.openjdk.jol.info.GraphLayout;

public class ObjectLayoutDemo {
    public static void main(String[] args) {
        // Empty object
        System.out.println(ClassLayout.parseInstance(new Object()).toPrintable());
        // OFFSET  SIZE   TYPE    DESCRIPTION
        //      0    12          (object header: mark + klass)
        //     12     4          (padding)
        // Instance size: 16 bytes

        // String
        System.out.println(ClassLayout.parseInstance("Hello").toPrintable());
        // OFFSET  SIZE   TYPE    DESCRIPTION
        //      0    12          (object header)
        //     12     4   byte[] String.value     (reference to byte array)
        //     16     4   int    String.hash
        //     20     1   byte   String.coder
        //     21     1   byte   String.hashIsZero
        //     22     2          (padding)
        // Instance size: 24 bytes (+ separate byte[] object)

        // Graph size (total reachable):
        System.out.println(GraphLayout.parseInstance("Hello").totalSize());
        // 24 (String) + 16+5+3padding (byte[5]) = 24 + 24 = 48 bytes
    }
}
```

### Object Size Examples

```
Object Type                    Shallow Size (compressed oops)
────────────────────────────  ──────────────────────────────
new Object()                   16 bytes (12 header + 4 pad)
new Integer(42)                16 bytes (12 header + 4 int)
new Long(42L)                  24 bytes (12 header + 4 pad + 8 long)
new Double(3.14)               24 bytes (12 header + 4 pad + 8 double)
new byte[0]                    16 bytes (12 header + 4 length)
new byte[1]                    24 bytes (12+4+1+7 padding to 8-boundary)
new byte[8]                    24 bytes (12+4+8)
new byte[9]                    32 bytes (12+4+9+7 padding)
new int[0]                     16 bytes
new int[10]                    56 bytes (12+4+40)
new String("Hello")            48 bytes total (24 String + 24 byte[])
new ArrayList<>()              ~64 bytes (object + empty Object[10])
new HashMap<>()                ~128 bytes (object + empty Node[16])
```

---

## 9. GC Pause Reduction Strategies

### Strategy 1: Reduce Allocation Rate

```java
// BAD: allocates in hot path
public String format(int x, int y) {
    return String.format("(%d, %d)", x, y);  // allocates varargs array, formatter, etc.
}

// GOOD: avoid allocation
private final StringBuilder reusableSb = new StringBuilder(32);  // thread-local or pooled
public String format(int x, int y) {
    reusableSb.setLength(0);
    reusableSb.append('(').append(x).append(", ").append(y).append(')');
    return reusableSb.toString();
}

// Other techniques:
// - Pre-size collections: new ArrayList<>(expectedSize)
// - Use primitives: IntStream not Stream<Integer>
// - Object pooling for expensive objects
// - Avoid autoboxing: use IntToIntFunction not Function<Integer,Integer>
// - Reuse buffers: ThreadLocal<byte[]> for temporary work
```

### Strategy 2: Reduce Live Data Set

```java
// Short-lived objects die in Young Gen (free to collect)
// Problem: objects that live "too long" get promoted to Old Gen

// BAD: large cache in Old Gen
private static Map<String, byte[]> cache = new ConcurrentHashMap<>();  // grows forever

// GOOD: bounded cache (entries evicted, never promotes forever)
private static Cache<String, byte[]> cache = Caffeine.newBuilder()
    .maximumSize(1000)
    .expireAfterAccess(Duration.ofMinutes(5))
    .build();
```

### Strategy 3: Right-Size Heap

```
Too small: frequent GC, thrashing (GC can't free enough → runs again immediately)
Too large: infrequent but LONG pauses (more live data to scan/compact)
Just right: Old Gen = 2-3× live data set after Full GC

How to determine live data set:
1. Run application with typical load
2. Force Full GC: jcmd <pid> GC.run
3. Check Old Gen usage after Full GC (= live data set)
4. Set -Xmx = 3-4× that value
```

### Strategy 4: Collector Selection Decision Tree

```
┌─ Heap < 100MB or single core?
│   └─ Serial GC (-XX:+UseSerialGC)
│
├─ Batch processing, throughput priority?
│   └─ Parallel GC (-XX:+UseParallelGC)
│
├─ General purpose, predictable pauses < 200ms?
│   └─ G1GC (-XX:+UseG1GC)  [DEFAULT since Java 9]
│
├─ Low latency < 1ms, large heap (>4GB)?
│   └─ ZGC (-XX:+UseZGC) or Shenandoah (-XX:+UseShenandoahGC)
│
└─ Embedded / minimal footprint?
    └─ Epsilon GC (-XX:+UseEpsilonGC) [no-op, no collection at all]
```

---

## 10. Metaspace Deep Dive

### What Lives Where

```
METASPACE (native memory):
├── Klass structures (class metadata)
├── Method metadata + bytecode
├── Constant pool (resolved entries)
├── Annotations
├── vtable / itable (virtual dispatch)
└── Field descriptors

HEAP:
├── java.lang.Class objects (mirror of Klass in Metaspace)
├── Static field VALUES (objects referenced by static fields)
├── String Pool (interned strings since Java 7)
└── All instance objects

KEY DISTINCTION:
  static String name = "hello";
  │                      │
  │                      └── "hello" String object → HEAP (String Pool)
  └── reference to "hello" → stored in Klass structure → METASPACE
```

### Metaspace Memory Management

```
Per-ClassLoader allocation:
- Each ClassLoader gets its own arena in Metaspace
- When ClassLoader is GC'd → its entire arena is freed (class unloading)
- This is how app servers redeploy: old classloader GC'd → all its classes unloaded

Metaspace structure:
┌──────────────────────────────────────────┐
│ ClassLoader 1 Arena                       │
│  [Klass A][Klass B][Methods][Constants]  │
├──────────────────────────────────────────┤
│ ClassLoader 2 Arena                       │
│  [Klass C][Klass D][Methods][Constants]  │
├──────────────────────────────────────────┤
│ Free chunks                               │
└──────────────────────────────────────────┘
```

### Metaspace Leak Causes

```java
// 1. Classloader leak — most common
// If any object created by ClassLoader CL is reachable,
// CL itself is reachable → CL's classes can't be unloaded

ThreadLocal<Object> tl = new ThreadLocal<>();
// If Object was loaded by custom ClassLoader, and ThreadLocal is in thread pool thread,
// → ClassLoader leaks (all its classes stay in Metaspace)

// 2. Dynamic proxy explosion
// Frameworks generating unlimited proxy classes:
for (int i = 0; i < 100_000; i++) {
    Proxy.newProxyInstance(...)  // each creates new $Proxy class
}

// 3. Groovy/script compilation
// Each eval creates new class:
for (...) { new GroovyShell().evaluate(script); }  // new class per evaluation

// FIX: reuse GroovyShell, cache compiled scripts
```

---

## 11. Off-Heap Memory

### When to Use Off-Heap

```
- Large data that shouldn't trigger GC (>1GB)
- Memory-mapped files (mmap)
- Network I/O buffers (Netty's ByteBuf)
- Serialization buffers
- External data stores (MapDB, Chronicle Map)
```

### Direct ByteBuffer

```java
import java.nio.ByteBuffer;

// Allocated OUTSIDE Java heap (native memory)
ByteBuffer direct = ByteBuffer.allocateDirect(1024 * 1024);  // 1MB off-heap

// Benefits:
// - No GC pressure (not counted in heap)
// - Zero-copy I/O (kernel can DMA directly to/from this memory)
// - No need to copy between Java heap and native for I/O

// Costs:
// - Slower allocation than heap
// - Harder to debug (not in heap dumps)
// - Must manage lifecycle (Cleaner or explicit free via sun.misc.Unsafe)
// - Limited by: -XX:MaxDirectMemorySize (default = -Xmx)

// Track usage:
// jcmd <pid> VM.native_memory summary
```

### Unsafe Direct Memory (Advanced)

```java
import sun.misc.Unsafe;

// Get Unsafe instance (not public API, use with caution)
Field f = Unsafe.class.getDeclaredField("theUnsafe");
f.setAccessible(true);
Unsafe unsafe = (Unsafe) f.get(null);

// Allocate native memory
long address = unsafe.allocateMemory(1024);

// Write/read directly
unsafe.putInt(address, 42);
int value = unsafe.getInt(address);

// Free memory (MUST do this or leak!)
unsafe.freeMemory(address);

// Java 22+: Use Foreign Function & Memory API (safer replacement)
// MemorySegment segment = Arena.ofConfined().allocate(1024);
```

---

## 12. Interview Questions — Deep JVM/GC

**Q: What is TLAB and why does it matter?**
```
TLAB = Thread-Local Allocation Buffer. Each thread gets a private slice of Eden.
Object allocation is just a pointer bump (no synchronization).
Without TLAB, every new Object() would need CAS → massive contention in multi-threaded apps.
With TLAB, allocation is ~10ns (same as C malloc fast path).
```

**Q: Explain Soft vs Weak vs Phantom references with use cases.**
```
Soft: cleared before OOM. Use for caches that should shrink under memory pressure.
Weak: cleared at next GC. Use for metadata/canonical maps (WeakHashMap).
Phantom: get() always returns null, enqueued after finalization. Use for cleanup tracking
(replacement for finalize). Must use with ReferenceQueue.
```

**Q: How does G1GC handle cross-region references?**
```
Per-region Remembered Sets track: "which other regions point to me?"
Write barrier (post-write) updates remembered set on every reference store.
During Young GC: scan remembered sets of collected regions to find external references.
Trade-off: 5-20% memory overhead for remembered sets, but much faster Young GC.
```

**Q: What is a safe point? What causes long TTSP?**
```
Safe point = location where GC can safely inspect thread state.
All threads must reach safe point before GC starts.
TTSP = Time To Safe Point (how long GC waits for slowest thread).
Counted loops (int counter, no method calls) have NO internal safe points.
A tight loop processing millions of elements can block GC for seconds.
Fix: use long counter, add method calls, or -XX:+UseCountedLoopSafepoints.
```

**Q: How would you diagnose a memory leak in production?**
```
1. Monitor: Old Gen usage after each Full GC (should be stable, not growing)
2. Heap dump: -XX:+HeapDumpOnOutOfMemoryError or jmap -dump:live,format=b,file=dump.hprof <pid>
3. Analyze in Eclipse MAT:
   - Dominator Tree → top retained-size objects
   - Leak Suspects report
   - "Path to GC Roots" for suspicious objects
4. Common causes: unbounded caches, listener leaks, ThreadLocal in thread pools
```

**Q: What's the difference between -Xms and -Xmx? Why set them equal?**
```
-Xms = initial heap size
-Xmx = maximum heap size
Set equal to avoid resize pauses (heap growth triggers Full GC to move objects).
Also provides consistent performance (no "warm up" of memory allocation from OS).
```

**Q: How does ZGC achieve sub-millisecond pauses?**
```
1. Colored Pointers: metadata stored in unused bits of 64-bit pointers
2. Load Barriers: every reference load checks if pointer is "good"
   If "bad" (object was moved), barrier fixes it transparently
3. Concurrent everything: mark, relocate, remap all happen while app runs
4. Only brief STW for root scanning (~1ms)
5. No generational structure in classic ZGC (Generational ZGC in Java 21 adds it)
```

**Q: Explain the 32GB compressed oops boundary.**
```
Compressed oops store references in 4 bytes instead of 8.
Since objects are 8-byte aligned, bottom 3 bits are always 0.
We shift right by 3, giving 2^35 = 32GB addressable range in 4 bytes.
Above 32GB: compressed oops disabled, all references become 8 bytes.
A 33GB heap may use MORE memory than a 31GB heap!
Recommendation: stay at 31GB max, or jump to much larger (like 48GB+).
```

**Q: What causes "GC overhead limit exceeded"?**
```
JVM throws this when:
- 98%+ of time is spent in GC, AND
- Less than 2% of heap is recovered each cycle
This means the application is essentially frozen doing useless GC.
Causes: memory leak (growing live data set) or heap far too small.
Fix: increase heap, find and fix leak, or add -XX:-UseGCOverheadLimit (bandaid).
```

**Q: What's the memory overhead of an empty HashMap?**
```
new HashMap<>() (default capacity 16, load factor 0.75):
- HashMap object: ~48 bytes
- Node[] array: 16 + (16 × 4) = 80 bytes (16 null references)
- Total: ~128 bytes for EMPTY HashMap

new HashMap<>(1000):
- Rounds up to 1024 (power of 2)
- Node[] array: 16 + (1024 × 4) = ~4,112 bytes
- Total: ~4,160 bytes before adding any entry

Each Entry (Node): ~32 bytes (header + hash + key_ref + value_ref + next_ref)
```

**Q: When would you use off-heap memory?**
```
- Large datasets (>1GB) that would cause long GC pauses if on-heap
- I/O buffers (zero-copy networking with DirectByteBuffer)
- Memory-mapped files (file-backed, OS manages paging)
- Interop with native libraries (FFI / JNI)
- Real-time systems where GC jitter is unacceptable
Examples: Cassandra (off-heap memtables), Netty (pooled ByteBuf), Spark (Tungsten)
```

**Q: How do you calculate allocation rate from GC logs?**
```
Allocation Rate = Eden Size / Time Between Young GCs

Example from logs:
  [10.000s] GC(1) Young: 256M->32M(2048M) 12ms
  [12.500s] GC(2) Young: 256M->28M(2048M) 14ms

Eden used: 256M - 32M = 224M allocated between GC1 and GC2
Time: 12.500 - 10.000 = 2.5 seconds
Allocation Rate: 224MB / 2.5s = 89.6 MB/s

If rate > 500 MB/s → consider object pooling or reducing allocations
```

---

## 13. Production Checklist

```
□ Set -Xms = -Xmx (avoid resize pauses)
□ Choose GC: G1 (general), ZGC (latency-critical)
□ Set -XX:MaxMetaspaceSize (prevent unbounded native growth)
□ Enable -XX:+HeapDumpOnOutOfMemoryError
□ Enable GC logging: -Xlog:gc*:file=gc.log:time:filecount=5,filesize=100m
□ Monitor: heap after GC, GC pause times, allocation rate, promotion rate
□ Set -XX:+ExitOnOutOfMemoryError (let orchestrator restart)
□ Size heap: 3-4× live data set after Full GC
□ Stay under 32GB (-Xmx31g) for compressed oops, or go much larger
□ Test with production-like load before deploying GC changes
```

---
