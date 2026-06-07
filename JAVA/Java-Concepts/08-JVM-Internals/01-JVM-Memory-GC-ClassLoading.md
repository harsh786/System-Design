# JVM Internals — Memory, GC, ClassLoading, JMM

## 1. JVM Architecture Overview

```
┌──────────────────────────────────────────────────────────────────────────┐
│                         JAVA APPLICATION                                  │
│                    (.java → .class bytecode)                              │
└────────────────────────────────┬─────────────────────────────────────────┘
                                 │
┌────────────────────────────────▼─────────────────────────────────────────┐
│                         JVM (Java Virtual Machine)                         │
│                                                                           │
│  ┌─────────────────────────────────────────────────────────────────────┐ │
│  │                  CLASS LOADER SUBSYSTEM                               │ │
│  │                                                                       │ │
│  │   Loading ──→ Linking ──→ Initialization                             │ │
│  │               (Verify → Prepare → Resolve)                           │ │
│  │                                                                       │ │
│  │   Bootstrap ClassLoader (java.base, rt.jar)                          │ │
│  │       ↑ parent delegation                                            │ │
│  │   Platform/Extension ClassLoader (javax.*)                           │ │
│  │       ↑ parent delegation                                            │ │
│  │   Application ClassLoader (classpath)                                │ │
│  └─────────────────────────────────────────────────────────────────────┘ │
│                                                                           │
│  ┌─────────────────────────────────────────────────────────────────────┐ │
│  │              RUNTIME DATA AREAS (Memory)                              │ │
│  │                                                                       │ │
│  │  ┌──────────────────────────────┐  ┌────────────────────────────┐   │ │
│  │  │          HEAP (shared)        │  │  METASPACE (shared)         │   │ │
│  │  │                              │  │  Class metadata, static     │   │ │
│  │  │  ┌─────────────────────┐    │  │  vars, constant pool,       │   │ │
│  │  │  │ Young Generation    │    │  │  method bytecode            │   │ │
│  │  │  │ ┌─────┬─────┬────┐ │    │  │  (Native memory, not heap)  │   │ │
│  │  │  │ │Eden │ S0  │ S1 │ │    │  └────────────────────────────┘   │ │
│  │  │  │ └─────┴─────┴────┘ │    │                                    │ │
│  │  │  └─────────────────────┘    │  ┌────────────────────────────┐   │ │
│  │  │  ┌─────────────────────┐    │  │  STACK (per thread)         │   │ │
│  │  │  │ Old Generation      │    │  │  [Frame][Frame][Frame]...   │   │ │
│  │  │  │ (Tenured Space)     │    │  │  Each frame:               │   │ │
│  │  │  └─────────────────────┘    │  │   - Local Variables Array  │   │ │
│  │  └──────────────────────────────┘  │   - Operand Stack          │   │ │
│  │                                    │   - Frame Data             │   │ │
│  │  ┌───────────────┐ ┌────────────┐ └────────────────────────────┘   │ │
│  │  │ PC Register   │ │ Native     │                                    │ │
│  │  │ (per thread)  │ │ Method     │                                    │ │
│  │  │               │ │ Stack      │                                    │ │
│  │  └───────────────┘ └────────────┘                                    │ │
│  └─────────────────────────────────────────────────────────────────────┘ │
│                                                                           │
│  ┌─────────────────────────────────────────────────────────────────────┐ │
│  │                    EXECUTION ENGINE                                    │ │
│  │                                                                       │ │
│  │   ┌──────────────┐  ┌─────────────────────┐  ┌──────────────────┐  │ │
│  │   │ Interpreter  │  │ JIT Compiler         │  │ Garbage          │  │ │
│  │   │ (line by     │  │ C1 (Client, fast)    │  │ Collector        │  │ │
│  │   │  line)       │  │ C2 (Server, optimal) │  │ (Serial/G1/ZGC) │  │ │
│  │   └──────────────┘  └─────────────────────┘  └──────────────────┘  │ │
│  └─────────────────────────────────────────────────────────────────────┘ │
│                                                                           │
│  ┌─────────────────────────────────────────────────────────────────────┐ │
│  │              NATIVE METHOD INTERFACE (JNI)                            │ │
│  │              Native Method Libraries (.so/.dll)                       │ │
│  └─────────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Memory Model (Runtime Data Areas)

### 2.1 Heap (Shared Across All Threads)

The heap is where ALL objects live. It's managed by the Garbage Collector.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              HEAP                                         │
│                                                                           │
│  ┌───────────────────────────────────────────┐  ┌───────────────────┐  │
│  │          YOUNG GENERATION (~1/3 heap)      │  │ OLD GENERATION    │  │
│  │                                            │  │ (~2/3 heap)       │  │
│  │  ┌────────────┐  ┌────────┐  ┌────────┐  │  │                   │  │
│  │  │   EDEN     │  │  S0    │  │  S1    │  │  │ Long-lived        │  │
│  │  │  (80%)     │  │ (10%)  │  │ (10%)  │  │  │ objects           │  │
│  │  │            │  │        │  │        │  │  │                   │  │
│  │  │ New objects│  │Survivor│  │Survivor│  │  │ Promoted from     │  │
│  │  │ allocated  │  │ From   │  │  To    │  │  │ Young Gen         │  │
│  │  │ here       │  │        │  │        │  │  │ (age >= 15)       │  │
│  │  └────────────┘  └────────┘  └────────┘  │  │                   │  │
│  └───────────────────────────────────────────┘  └───────────────────┘  │
│                                                                           │
│  Object Flow: Eden → Survivor (age++) → Old Gen (age >= threshold)       │
│                                                                           │
│  Default: -XX:NewRatio=2 (Old:Young = 2:1)                               │
│           -XX:SurvivorRatio=8 (Eden:S0:S1 = 8:1:1)                       │
│           -XX:MaxTenuringThreshold=15                                     │
└─────────────────────────────────────────────────────────────────────────┘
```

**Object Allocation Flow:**
1. New object → Eden Space
2. Eden fills → Minor GC triggered
3. Live objects in Eden → Survivor To (S1), age = 1
4. Live objects in Survivor From (S0) → Survivor To (S1), age++
5. S0 and S1 swap roles
6. Objects with age >= threshold (default 15) → Old Generation
7. Very large objects → Old Generation directly (bypasses Young Gen)

**Key JVM Flags:**
```
-Xms512m        # Initial heap size
-Xmx4g          # Maximum heap size
-Xmn1g          # Young generation size
-XX:NewRatio=2  # Old/Young ratio (Old = 2 * Young)
-XX:SurvivorRatio=8  # Eden/Survivor ratio
-XX:MaxTenuringThreshold=15  # Promotion age
```

---

### 2.2 Stack (Per Thread, NOT GC'd)

Each thread gets its own stack. Each method call creates a **Stack Frame**.

```
┌────────────────────────────────────┐
│     THREAD STACK                    │
│     (per thread, -Xss=512k)        │
│                                    │
│  ┌──────────────────────────────┐  │
│  │  Frame: main()               │  │  ← bottom (first called)
│  │  ┌─────────────────────────┐ │  │
│  │  │ Local Variables Array   │ │  │  [this, arg1, arg2, localVar]
│  │  ├─────────────────────────┤ │  │
│  │  │ Operand Stack           │ │  │  [computation workspace]
│  │  ├─────────────────────────┤ │  │
│  │  │ Frame Data              │ │  │  [constant pool ref, return addr]
│  │  └─────────────────────────┘ │  │
│  └──────────────────────────────┘  │
│  ┌──────────────────────────────┐  │
│  │  Frame: calculateTotal()     │  │
│  │  [locals] [operands] [data]  │  │
│  └──────────────────────────────┘  │
│  ┌──────────────────────────────┐  │
│  │  Frame: applyDiscount()      │  │  ← top (currently executing)
│  │  [locals] [operands] [data]  │  │
│  └──────────────────────────────┘  │
└────────────────────────────────────┘
```

**Stack Frame Components:**
- **Local Variables Array**: stores `this` (for instance methods), method parameters, local variables. Primitives stored directly, objects stored as references (pointer to heap).
- **Operand Stack**: workspace for bytecode operations (like a calculator stack)
- **Frame Data**: reference to constant pool, exception table, return address

**Stack vs Heap:**

| Aspect | Stack | Heap |
|--------|-------|------|
| Scope | Per thread | Shared |
| Stores | Primitives + references | Objects |
| Lifecycle | Method entry → method exit | Until GC collects |
| Speed | Very fast (LIFO pointer) | Slower (GC overhead) |
| Size | Small (-Xss, default 512K-1M) | Large (-Xmx) |
| Error | StackOverflowError | OutOfMemoryError |
| Thread-safe | Yes (thread-confined) | No (shared) |

```java
public void example() {
    int x = 10;              // x is on STACK (primitive)
    String s = "hello";      // reference 's' on STACK, String object on HEAP
    List<Integer> list = new ArrayList<>();  // reference on STACK, ArrayList on HEAP
    list.add(42);            // Integer(42) on HEAP
}
// When method returns: stack frame destroyed, x and references gone
// Objects on heap remain until GC determines they're unreachable
```

---

### 2.3 Metaspace (Java 8+, Replaces PermGen)

```
┌─────────────────────────────────────────┐
│           METASPACE                      │
│        (Native Memory)                   │
│                                          │
│  Stores:                                 │
│  • Class metadata (field/method info)    │
│  • Static variables                      │
│  • Constant pool (string literals, etc.) │
│  • Method bytecode                       │
│  • Annotations                           │
│                                          │
│  Key difference from PermGen:            │
│  • Lives in native memory (not heap)     │
│  • Grows automatically (no fixed max)    │
│  • GC'd when ClassLoader is GC'd        │
│                                          │
│  Flags:                                  │
│  -XX:MetaspaceSize=256m     (initial)    │
│  -XX:MaxMetaspaceSize=512m  (max)        │
└─────────────────────────────────────────┘
```

---

### 2.4 PC Register & Native Method Stack

- **PC Register**: Each thread has one. Points to the current bytecode instruction being executed. If executing native method, PC is undefined.
- **Native Method Stack**: Separate stack for native (C/C++) method calls via JNI.

---

## 3. Object Memory Layout

```
┌───────────────────────────────────────────────────────────────┐
│                    OBJECT IN MEMORY                             │
├───────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │  OBJECT HEADER (12 bytes normal, 16 bytes with array)    │  │
│  │                                                           │  │
│  │  Mark Word (8 bytes / 64 bits):                          │  │
│  │  ┌─────────────────────────────────────────────────────┐ │  │
│  │  │ Bits 0-24: identity hashCode (25 bits)              │ │  │
│  │  │ Bits 25-28: GC age (4 bits, max 15)                 │ │  │
│  │  │ Bit 29: biased lock flag                            │ │  │
│  │  │ Bits 30-31: lock state (00=lightweight, 10=heavy)   │ │  │
│  │  │ Remaining: thread ID (biased) or lock pointer       │ │  │
│  │  └─────────────────────────────────────────────────────┘ │  │
│  │                                                           │  │
│  │  Class Pointer (4 bytes with compressed oops):           │  │
│  │  → Points to class metadata in Metaspace                 │  │
│  │                                                           │  │
│  │  [Array Length (4 bytes) — only for arrays]              │  │
│  └─────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │  INSTANCE DATA (fields in allocation order)              │  │
│  │                                                           │  │
│  │  • Fields are reordered to minimize padding              │  │
│  │  • Order: longs/doubles → ints/floats → shorts/chars     │  │
│  │    → bytes/booleans → references                         │  │
│  │  • Reference: 4 bytes (compressed oops) or 8 bytes       │  │
│  └─────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │  PADDING (0-7 bytes to align to 8-byte boundary)         │  │
│  └─────────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────────┘

Example: new Object() = 16 bytes (12 header + 4 padding)
Example: class Point { int x; int y; } = 24 bytes (12 header + 4+4 data + 4 padding)
```

**Lock State in Mark Word:**

| State | Mark Word Content |
|-------|-------------------|
| Unlocked | hashCode + age + 01 |
| Biased | thread ID + epoch + age + 101 |
| Lightweight locked | pointer to lock record in stack + 00 |
| Heavyweight locked | pointer to monitor object + 10 |
| GC marked | forwarding address + 11 |

---

## 4. Garbage Collection

### 4.1 GC Roots — Starting Points for Reachability Analysis

```java
// These are GC Roots — objects reachable from here are ALIVE:

// 1. Local variables on active thread stacks
void method() {
    Object localVar = new Object();  // localVar is a GC root while method is on stack
}

// 2. Static fields of loaded classes
class Config {
    static Map<String, Object> cache = new HashMap<>();  // GC root
}

// 3. Active threads themselves
Thread t = new Thread(() -> { /* running */ });  // t is a GC root while alive

// 4. JNI references (native code holding Java references)

// 5. Objects used as monitors (synchronized locks)
synchronized(lockObj) { ... }  // lockObj is a GC root during sync block

// 6. System class loader references
```

### 4.2 GC Algorithms

#### Mark-and-Sweep
```
Phase 1 (Mark): Start from GC roots, traverse all reachable objects, mark them as "alive"
Phase 2 (Sweep): Scan entire heap, reclaim unmarked objects

Problem: Memory fragmentation (holes between live objects)

Before: [LIVE][DEAD][LIVE][DEAD][DEAD][LIVE][DEAD]
After:  [LIVE][    ][LIVE][         ][LIVE][    ]
                ^holes — can't allocate large objects
```

#### Mark-and-Compact
```
Phase 1 (Mark): Same as above
Phase 2 (Compact): Slide live objects to one end of heap

Before: [LIVE][DEAD][LIVE][DEAD][DEAD][LIVE][DEAD]
After:  [LIVE][LIVE][LIVE][                       ]
                          ^continuous free space

Pro: No fragmentation
Con: Expensive (must update all references to moved objects)
```

#### Copying Collector (Used in Young Generation)
```
Two equal spaces: FROM and TO

1. Allocate in FROM space
2. When FROM is full, copy LIVE objects to TO space
3. Swap FROM and TO

FROM: [LIVE][DEAD][LIVE][DEAD][DEAD][LIVE]
TO:   [LIVE][LIVE][LIVE][                 ]  ← compact, fast allocation

Pro: Fast (just copy live objects, ignore dead), no fragmentation
Con: Wastes 50% space (but Young Gen objects mostly die → few copies)
```

### 4.3 Generational Hypothesis

> "Most objects die young"

Empirically, 90%+ of objects become garbage shortly after creation. This insight drives generational GC:
- **Young Gen**: collected frequently (Minor GC), uses fast copying collector
- **Old Gen**: collected infrequently (Major GC), uses mark-compact

### 4.4 Minor GC vs Major GC vs Full GC

| Type | Scope | Trigger | Duration | STW |
|------|-------|---------|----------|-----|
| Minor GC | Young Gen only | Eden full | ms (fast) | Yes (short) |
| Major GC | Old Gen only | Old Gen filling up | 100ms-seconds | Depends on collector |
| Full GC | Entire heap + Metaspace | Explicit System.gc(), OOM prevention | Seconds | Yes (long) |

**Minor GC Flow:**
```
1. Eden is full → Minor GC triggered (Stop-The-World)
2. Mark live objects in Eden and Survivor FROM
3. Copy live objects to Survivor TO, increment age
4. If age >= threshold → promote to Old Gen
5. Clear Eden and Survivor FROM
6. Swap Survivor FROM and TO
7. Resume application threads

Duration: typically 10-50ms (only scans Young Gen)
```

### 4.5 GC Implementations

#### Serial GC (`-XX:+UseSerialGC`)
```
Single GC thread. Application stops completely during GC.

App threads:  ─────────||────────────────||──────────
GC thread:            [GC]              [GC]

Use case: Single-core machines, small heaps (<100MB), client apps
Pro: Simple, low overhead
Con: Long pauses on large heaps
```

#### Parallel GC (`-XX:+UseParallelGC`)
```
Multiple GC threads work in parallel. Still Stop-The-World.

App threads:  ─────────||──────────────────||──────────
GC threads:           [GC][GC][GC][GC]    [GC][GC][GC][GC]

Use case: Throughput-focused (batch processing, data pipelines)
Pro: Higher throughput than Serial
Con: Still has STW pauses
Flag: -XX:ParallelGCThreads=N
```

#### G1GC — Garbage First (`-XX:+UseG1GC`, default since Java 9)
```
┌──────────────────────────────────────────────────────────┐
│              G1GC Region-Based Heap Layout                 │
│                                                            │
│  Heap divided into ~2048 equal-sized regions              │
│  Each region can be: Eden, Survivor, Old, or Humongous    │
│                                                            │
│  ┌───┬───┬───┬───┬───┬───┬───┬───┬───┬───┬───┬───┐     │
│  │ E │ E │ S │ O │ O │ O │ H │ H │ E │ O │ O │ S │     │
│  ├───┼───┼───┼───┼───┼───┼───┼───┼───┼───┼───┼───┤     │
│  │ O │ O │ E │ E │ O │ O │ O │ O │ E │ E │ O │ O │     │
│  ├───┼───┼───┼───┼───┼───┼───┼───┼───┼───┼───┼───┤     │
│  │ E │ O │ O │ O │ O │ E │ E │ O │ S │ O │ O │ E │     │
│  └───┴───┴───┴───┴───┴───┴───┴───┴───┴───┴───┴───┘     │
│                                                            │
│  E = Eden, S = Survivor, O = Old, H = Humongous           │
│                                                            │
│  Key Concepts:                                             │
│  • Collects regions with most garbage FIRST (hence name)  │
│  • Mixed collections: Young + selected Old regions         │
│  • Humongous: objects > 50% region size                    │
│  • Concurrent marking (mostly non-STW)                     │
│  • Targets: -XX:MaxGCPauseMillis=200 (default 200ms)      │
│                                                            │
│  Phases:                                                   │
│  1. Young GC (STW): evacuate Eden+Survivor                │
│  2. Concurrent Marking: find garbage in Old regions        │
│  3. Mixed GC (STW): evacuate Young + garbage-heavy Old     │
│  4. Full GC (STW, fallback): if mixed can't keep up       │
└──────────────────────────────────────────────────────────┘
```

**G1GC Key Flags:**
```
-XX:+UseG1GC
-XX:MaxGCPauseMillis=200       # Target pause time (ms)
-XX:G1HeapRegionSize=4m        # Region size (1-32MB, power of 2)
-XX:InitiatingHeapOccupancyPercent=45  # When to start concurrent marking
-XX:G1ReservePercent=10        # Reserve for promotion failures
-XX:ConcGCThreads=4            # Concurrent marking threads
```

#### ZGC (`-XX:+UseZGC`, production-ready Java 15+)
```
┌──────────────────────────────────────────────────────────┐
│                     ZGC Design                            │
│                                                            │
│  Goal: Sub-millisecond pauses regardless of heap size     │
│  Tested: up to 16 TB heaps with < 1ms pauses             │
│                                                            │
│  Key Technologies:                                         │
│  1. Colored Pointers: metadata stored IN the pointer      │
│     ┌─────────────────────────────────────────────────┐  │
│     │ 64-bit pointer:                                  │  │
│     │ [unused:16][metadata:4][address:44]              │  │
│     │            ↑                                      │  │
│     │   marked0, marked1, remapped, finalizable        │  │
│     └─────────────────────────────────────────────────┘  │
│                                                            │
│  2. Load Barriers: check pointer metadata on every load   │
│     If pointer is "bad" (not remapped) → fix it in-place │
│     This is how ZGC is concurrent — no STW for relocation│
│                                                            │
│  3. Concurrent everything:                                 │
│     Mark → Relocate → Remap (all concurrent)              │
│     Only brief STW for root scanning (~1ms)               │
│                                                            │
│  Phases:                                                   │
│  1. Pause Mark Start (STW, ~1ms): scan GC roots           │
│  2. Concurrent Mark: traverse object graph                 │
│  3. Pause Mark End (STW, ~1ms): handle reference changes  │
│  4. Concurrent Relocate: move objects, update pointers     │
│  5. Concurrent Remap: fix remaining pointers               │
│                                                            │
│  When to use:                                              │
│  • Large heaps (>4GB)                                      │
│  • Latency-sensitive (p99 < 10ms)                         │
│  • Trading throughput for lower latency                    │
└──────────────────────────────────────────────────────────┘

Flags:
-XX:+UseZGC
-XX:+ZGenerational        # Generational ZGC (Java 21+, even better)
```

#### Shenandoah
- Similar goals to ZGC (sub-ms pauses)
- Uses Brooks pointers (forwarding pointer per object)
- Concurrent compaction
- Available in OpenJDK (not Oracle JDK)

#### Comparison Table

| Collector | Pause Time | Throughput | Heap Size | Use Case |
|-----------|-----------|------------|-----------|----------|
| Serial | High | Low | <100MB | Embedded, single-core |
| Parallel | Medium | Highest | Any | Batch processing, throughput |
| G1 (default) | Predictable (target-based) | Good | >4GB | General purpose, balanced |
| ZGC | <1ms | Good (slightly less) | 8MB-16TB | Latency-critical, large heaps |
| Shenandoah | <1ms | Good | Any | Low-latency (OpenJDK) |

---

### 4.6 Memory Leaks in Java

Even with GC, leaks happen when objects are **reachable but unused**:

```java
// 1. Static collections growing forever
class Cache {
    private static final Map<String, Object> cache = new HashMap<>();
    
    public static void put(String key, Object value) {
        cache.put(key, value);  // Never removed → grows forever
    }
    // Fix: Use bounded cache (Caffeine, Guava) or WeakHashMap
}

// 2. Listeners/callbacks not unregistered
class EventBus {
    private List<EventListener> listeners = new ArrayList<>();
    
    public void register(EventListener listener) {
        listeners.add(listener);
    }
    // If caller forgets to unregister → listener (and everything it references) leaks
    // Fix: Use WeakReference<EventListener> or ensure unregister is called
}

// 3. ThreadLocal not cleaned
class RequestContext {
    private static ThreadLocal<UserSession> session = new ThreadLocal<>();
    
    public static void set(UserSession s) { session.set(s); }
    // In thread pools, threads are REUSED. If you don't call remove(),
    // the value persists for the thread's entire lifetime.
    // Fix: Always call session.remove() in a finally block
}

// 4. Non-static inner class holding outer reference
class Outer {
    private byte[] largeData = new byte[10_000_000]; // 10 MB
    
    class Inner { // Holds implicit reference to Outer.this
        // Even if Outer is "done", Inner keeps Outer (and its 10MB) alive
    }
    // Fix: Make inner class static if it doesn't need outer's instance
}

// 5. Unclosed resources
class ResourceLeak {
    public void readFile() {
        InputStream is = new FileInputStream("data.txt");
        // If exception occurs before close → resource leaks
        // OS file handles are limited!
        // Fix: try-with-resources
    }
}

// 6. String.intern() abuse
class InternLeak {
    public void process(String input) {
        String interned = input.intern(); // Adds to string pool (Metaspace)
        // If input is unique every time → Metaspace grows unbounded
    }
}
```

---

## 5. Class Loading

### 5.1 Three Phases

```
┌──────────────────────────────────────────────────────────────────┐
│                    CLASS LOADING PHASES                            │
│                                                                    │
│  ┌──────────┐    ┌───────────────────────────────┐    ┌────────┐│
│  │          │    │          LINKING               │    │        ││
│  │ LOADING  │───▶│                               │───▶│  INIT  ││
│  │          │    │  Verify → Prepare → Resolve   │    │        ││
│  └──────────┘    └───────────────────────────────┘    └────────┘│
│                                                                    │
│  LOADING:                                                          │
│  • Find .class file (classpath, network, generated)               │
│  • Read bytecode into memory                                       │
│  • Create java.lang.Class object in Metaspace                     │
│                                                                    │
│  LINKING - VERIFY:                                                 │
│  • Bytecode structural correctness                                 │
│  • Type safety checks                                              │
│  • Stack map verification                                          │
│  • No illegal access to private fields of other classes           │
│                                                                    │
│  LINKING - PREPARE:                                                │
│  • Allocate memory for static fields                               │
│  • Set DEFAULT values (0, null, false) — NOT assigned values      │
│  • static int x = 42; → at this point x = 0                      │
│                                                                    │
│  LINKING - RESOLVE:                                                │
│  • Symbolic references → direct memory references                  │
│  • e.g., "java/lang/String" → actual Class pointer                │
│  • Can be lazy (resolved on first use)                             │
│                                                                    │
│  INITIALIZATION:                                                   │
│  • Execute static initializers and static blocks                   │
│  • Set static fields to their ASSIGNED values                      │
│  • static int x = 42; → NOW x = 42                               │
│  • Happens once per class, thread-safe (JVM guarantees)           │
│  • Parent class initialized first                                  │
│                                                                    │
└──────────────────────────────────────────────────────────────────┘
```

### 5.2 ClassLoader Hierarchy & Parent Delegation

```java
// ClassLoader hierarchy (parent delegation model)
//
// When asked to load "com.example.MyClass":
// 1. Application CL asks Platform CL: "can you load this?"
// 2. Platform CL asks Bootstrap CL: "can you load this?"
// 3. Bootstrap: "No, not in java.base"
// 4. Platform: "No, not in javax.*"
// 5. Application: "Yes, found on classpath!" → loads it
//
// This prevents:
// - Replacing core classes (security)
// - Loading same class twice (consistency)

public class ClassLoaderDemo {
    public static void main(String[] args) {
        // String is loaded by Bootstrap ClassLoader (returns null in Java)
        System.out.println(String.class.getClassLoader());  // null (Bootstrap)
        
        // Our class is loaded by Application ClassLoader
        System.out.println(ClassLoaderDemo.class.getClassLoader());
        // sun.misc.Launcher$AppClassLoader@...
        
        // Show hierarchy
        ClassLoader cl = ClassLoaderDemo.class.getClassLoader();
        while (cl != null) {
            System.out.println(cl);
            cl = cl.getParent();
        }
        // Output:
        // sun.misc.Launcher$AppClassLoader@...   (Application)
        // sun.misc.Launcher$ExtClassLoader@...   (Platform/Extension)
        // null                                    (Bootstrap - native, returns null)
    }
}
```

### 5.3 Custom ClassLoader

```java
/**
 * Custom ClassLoader - loads classes from encrypted files, databases, or network.
 * Use cases: hot-deploy, plugin systems, class isolation, bytecode manipulation.
 */
public class EncryptedClassLoader extends ClassLoader {
    private final Path classDir;
    private final byte[] decryptionKey;
    
    public EncryptedClassLoader(Path classDir, byte[] key, ClassLoader parent) {
        super(parent);
        this.classDir = classDir;
        this.decryptionKey = key;
    }
    
    @Override
    protected Class<?> findClass(String name) throws ClassNotFoundException {
        try {
            // Convert class name to file path
            String fileName = name.replace('.', '/') + ".class.enc";
            Path classFile = classDir.resolve(fileName);
            
            // Read encrypted bytecode
            byte[] encrypted = Files.readAllBytes(classFile);
            
            // Decrypt
            byte[] bytecode = decrypt(encrypted, decryptionKey);
            
            // Define the class (tells JVM "here's the bytecode for this class")
            return defineClass(name, bytecode, 0, bytecode.length);
            
        } catch (IOException e) {
            throw new ClassNotFoundException("Cannot load " + name, e);
        }
    }
    
    private byte[] decrypt(byte[] data, byte[] key) {
        // AES decryption logic
        return data; // simplified
    }
}

// Usage:
EncryptedClassLoader loader = new EncryptedClassLoader(
    Path.of("/plugins"), secretKey, getClass().getClassLoader()
);
Class<?> pluginClass = loader.loadClass("com.plugin.MyPlugin");
Object plugin = pluginClass.getDeclaredConstructor().newInstance();
```

### 5.4 ClassNotFoundException vs NoClassDefFoundError

| Aspect | ClassNotFoundException | NoClassDefFoundError |
|--------|----------------------|---------------------|
| Type | Checked Exception | Error (unchecked) |
| When | Class.forName(), ClassLoader.loadClass() | Class was available at compile-time but missing at runtime |
| Cause | Class not on classpath | Classpath changed, or static initializer failed |
| Example | `Class.forName("com.mysql.Driver")` — driver JAR missing | Compiled against lib v1, deployed with v2 missing a class |
| Fix | Add JAR to classpath | Fix deployment, check transitive dependencies |

---

## 6. Java Memory Model (JMM)

### 6.1 The Problem

```
┌─────────────────────────────────────────────────────────────────┐
│                  WHY JMM EXISTS                                   │
│                                                                   │
│  CPU 1                         CPU 2                              │
│  ┌─────────┐                  ┌─────────┐                        │
│  │ Thread A│                  │ Thread B│                        │
│  └────┬────┘                  └────┬────┘                        │
│       │                            │                              │
│  ┌────▼────┐                  ┌────▼────┐                        │
│  │L1 Cache │                  │L1 Cache │   ← Each CPU has       │
│  └────┬────┘                  └────┬────┘     its own cache      │
│       │                            │                              │
│  ┌────▼────────────────────────────▼────┐                        │
│  │         L2/L3 Cache (shared)          │                        │
│  └────────────────┬──────────────────────┘                        │
│                   │                                                │
│  ┌────────────────▼──────────────────────┐                        │
│  │            MAIN MEMORY                 │                        │
│  │        (where variables live)          │                        │
│  └────────────────────────────────────────┘                        │
│                                                                   │
│  Problems:                                                        │
│  1. VISIBILITY: Thread A writes x=1, Thread B reads x=0          │
│     (Thread B's cache hasn't been updated)                        │
│                                                                   │
│  2. ORDERING: Compiler/CPU reorders instructions for performance  │
│     Thread A: x=1; flag=true; → CPU might execute as: flag=true; x=1;│
│     Thread B sees flag=true but x=0 (stale)                      │
│                                                                   │
│  3. ATOMICITY: long/double writes are NOT atomic on 32-bit JVMs  │
│     Thread A writes long x = 0xFFFFFFFF_FFFFFFFF                 │
│     Thread B might read x = 0xFFFFFFFF_00000000 (torn read)      │
└─────────────────────────────────────────────────────────────────┘
```

### 6.2 Happens-Before Rules (Complete)

If action A **happens-before** action B, then A's effects are **guaranteed visible** to B.

```java
// Rule 1: PROGRAM ORDER
// Within a single thread, each action happens-before the next
int x = 1;      // (1)
int y = x + 1;  // (2) — guaranteed to see x=1

// Rule 2: MONITOR LOCK
// unlock() happens-before subsequent lock() on same monitor
synchronized(lock) { x = 1; }     // Thread A: unlock happens-before...
synchronized(lock) { print(x); }  // Thread B: ...lock. Guaranteed to see x=1

// Rule 3: VOLATILE
// Write to volatile happens-before subsequent read of same volatile
volatile boolean ready = false;
// Thread A: x = 42; ready = true;   ← volatile write
// Thread B: if (ready) print(x);    ← guaranteed to see x=42
// (volatile write also flushes ALL previous writes, not just the volatile var!)

// Rule 4: THREAD START
// Thread.start() happens-before any action in the started thread
x = 42;
thread.start();  // thread is guaranteed to see x=42

// Rule 5: THREAD JOIN/TERMINATION
// All actions in a thread happen-before join() returns
thread.join();   // after this, guaranteed to see all writes made by thread

// Rule 6: THREAD INTERRUPT
// interrupt() happens-before the interrupted thread detects it

// Rule 7: FINALIZER
// Constructor completion happens-before finalize() starts

// Rule 8: TRANSITIVITY
// If A hb B, and B hb C, then A hb C
```

### 6.3 volatile Keyword

```java
/**
 * volatile guarantees:
 * 1. VISIBILITY: reads always see the latest write (bypasses CPU cache)
 * 2. ORDERING: no reordering across volatile read/write (memory fence)
 * 
 * volatile does NOT guarantee:
 * 3. ATOMICITY: volatile int counter; counter++ is NOT atomic (read-modify-write)
 */

// CORRECT use: flag/status visible across threads
class TaskRunner {
    private volatile boolean running = true;  // volatile needed!
    
    public void run() {
        while (running) {  // Without volatile, JIT might hoist this read out of loop
            doWork();      // Infinite loop even after stop() is called
        }
    }
    
    public void stop() {
        running = false;  // Guaranteed visible to run() thread
    }
}

// INCORRECT use: compound operation
class BrokenCounter {
    private volatile int count = 0;
    
    public void increment() {
        count++;  // NOT ATOMIC! This is: temp = count; temp = temp + 1; count = temp;
        // Two threads can read same value, both increment to same result → lost update
    }
    // Fix: use AtomicInteger or synchronized
}
```

### 6.4 Double-Checked Locking (Classic Interview Question)

```java
/**
 * WHY volatile IS REQUIRED in double-checked locking:
 * 
 * instance = new Singleton() compiles to:
 * 1. memory = allocate()           // allocate memory
 * 2. constructor(memory)           // initialize fields
 * 3. instance = memory             // assign reference
 * 
 * WITHOUT volatile, CPU can reorder to: 1 → 3 → 2
 * Thread B sees instance != null (step 3 done) but fields not initialized (step 2 pending)
 * Thread B uses a PARTIALLY CONSTRUCTED object!
 * 
 * WITH volatile: reordering across volatile write is forbidden.
 * Step 3 (volatile write) cannot happen before step 2.
 */
class Singleton {
    private static volatile Singleton instance;  // MUST be volatile
    
    private Singleton() { }
    
    public static Singleton getInstance() {
        if (instance == null) {                 // First check (no lock, fast path)
            synchronized (Singleton.class) {    // Lock
                if (instance == null) {         // Second check (prevents double creation)
                    instance = new Singleton(); // volatile write → full visibility
                }
            }
        }
        return instance;
    }
}

// Simpler alternative: Bill Pugh (Holder pattern) — no volatile needed
class SingletonHolder {
    private SingletonHolder() { }
    
    private static class Holder {
        static final SingletonHolder INSTANCE = new SingletonHolder();
        // JVM guarantees class initialization is thread-safe
    }
    
    public static SingletonHolder getInstance() {
        return Holder.INSTANCE;  // Lazy, thread-safe, no synchronization overhead
    }
}
```

### 6.5 final Field Semantics

```java
/**
 * final fields have special JMM guarantees:
 * Once constructor completes, final fields are guaranteed visible to ALL threads
 * WITHOUT any synchronization (safe publication of immutable objects).
 */
class ImmutablePoint {
    private final int x;  // Guaranteed visible after construction
    private final int y;
    
    public ImmutablePoint(int x, int y) {
        this.x = x;
        this.y = y;
    }
    // Any thread that sees a reference to this object is guaranteed to see x and y
    // (as long as 'this' doesn't escape during construction)
}

// DANGER: 'this' escaping during construction
class Broken {
    private final int value;
    
    public Broken(int v) {
        registry.add(this);  // BAD! 'this' escapes before constructor finishes
        this.value = v;      // Another thread via registry might see value=0
    }
}
```

---

## 7. JIT Compilation

### 7.1 Tiered Compilation (Java 8+)

```
┌────────────────────────────────────────────────────────────────┐
│                   TIERED COMPILATION                             │
│                                                                  │
│  Execution starts in interpreter, hot methods get compiled:     │
│                                                                  │
│  Level 0: Interpreter                                           │
│    ↓ (method called > 200 times)                                │
│  Level 1-3: C1 Compiler (Client)                                │
│    • Fast compilation                                            │
│    • Basic optimizations (inlining small methods)                │
│    • Adds profiling instrumentation                              │
│    ↓ (method called > 10,000 times, or detected as "hot")       │
│  Level 4: C2 Compiler (Server)                                  │
│    • Slow compilation (but worth it for hot methods)             │
│    • Aggressive optimizations:                                   │
│      - Deep inlining                                             │
│      - Escape analysis                                           │
│      - Loop unrolling                                            │
│      - Dead code elimination                                     │
│      - Vectorization (SIMD)                                      │
│      - Intrinsics (CPU-specific instructions)                    │
│                                                                  │
│  Code can be DEOPTIMIZED:                                       │
│  If assumption is invalidated (e.g., new class loaded that      │
│  changes inheritance hierarchy), compiled code is thrown away     │
│  and method returns to interpreter.                              │
└────────────────────────────────────────────────────────────────┘
```

### 7.2 Key JIT Optimizations

```java
// 1. METHOD INLINING
// Before inlining:
int result = add(a, b);  // method call overhead (push frame, jump, return)

private int add(int x, int y) { return x + y; }

// After inlining (JIT replaces call with body):
int result = a + b;  // No method call overhead!

// JIT inlines aggressively: up to 35 bytes method size, up to 9 levels deep

// ─────────────────────────────────────────────────────────────

// 2. ESCAPE ANALYSIS
// If object does NOT escape the method → allocate on STACK (no GC!)
public int sumPoints() {
    Point p = new Point(3, 4);  // JIT detects: p never escapes this method
    return p.x + p.y;          // After escape analysis:
}
// Compiled as: return 3 + 4; → return 7; (scalar replacement + constant folding)
// No object allocation at all!

// Object escapes if: assigned to field, passed to another method, returned

// ─────────────────────────────────────────────────────────────

// 3. LOOP UNROLLING
// Before:
for (int i = 0; i < 4; i++) { sum += array[i]; }

// After unrolling:
sum += array[0]; sum += array[1]; sum += array[2]; sum += array[3];
// Eliminates loop overhead (increment, compare, branch)

// ─────────────────────────────────────────────────────────────

// 4. DEAD CODE ELIMINATION
if (false) { expensiveOperation(); }  // removed entirely
int x = compute(); // if x is never used → compute() call removed (if no side effects)

// ─────────────────────────────────────────────────────────────

// 5. INTRINSICS
// JIT replaces known methods with CPU-specific instructions:
// Math.min(a, b)     → cmov instruction (no branch)
// System.arraycopy() → rep movsb (memory copy instruction)
// Integer.bitCount() → popcnt instruction
// String.equals()    → SIMD comparison
```

### 7.3 JIT Flags

```
-XX:+PrintCompilation             # Show which methods are compiled
-XX:CompileThreshold=10000        # Invocations before compilation
-XX:+UnlockDiagnosticVMOptions
-XX:+PrintInlining                # Show inlining decisions
-XX:MaxInlineSize=35              # Max bytecode size to inline
-XX:FreqInlineSize=325            # Max size for frequently called methods
-XX:+DoEscapeAnalysis             # Enable escape analysis (default: on)
-XX:-TieredCompilation            # Disable tiered (go straight to C2)
```

---

## 8. Common OOM Scenarios

| Error | Cause | Symptoms | Fix |
|-------|-------|----------|-----|
| `OutOfMemoryError: Java heap space` | Objects accumulate, leak, or burst allocation | GC runs frequently, app slows, then OOM | Increase `-Xmx`, fix memory leak, use heap dump analysis |
| `OutOfMemoryError: Metaspace` | Too many classes loaded (reflection proxies, Groovy scripts, CGLIB) | Metaspace usage grows continuously | Set `-XX:MaxMetaspaceSize`, reduce dynamic class generation |
| `OutOfMemoryError: unable to create new native thread` | Too many threads created, OS limit reached | `ulimit -u` too low, thread pools unbounded | Use bounded thread pools, increase OS limits |
| `OutOfMemoryError: GC overhead limit exceeded` | 98%+ time spent in GC, <2% heap reclaimed | App essentially frozen, GC thrashing | Fix memory leak or increase heap significantly |
| `StackOverflowError` | Deep or infinite recursion | Recursive method without proper base case | Fix recursion, increase `-Xss` (rare) |

### Debugging a Heap Leak

```java
// Step 1: Enable heap dump on OOM
// -XX:+HeapDumpOnOutOfMemoryError -XX:HeapDumpPath=/tmp/heapdump.hprof

// Step 2: Reproduce the OOM

// Step 3: Analyze with Eclipse MAT or VisualVM
// Look for:
// - Dominator tree: which object retains the most memory?
// - Leak suspect report: automatic detection
// - Histogram: which class has the most instances?

// Common findings:
// - HashMap with 10M entries (cache without eviction)
// - ArrayList growing in a static field
// - Thousands of duplicate byte[] from reading files without closing
```

---

## 9. Diagnostic Tools

### Thread Dump (jstack)
```bash
# Get thread dump
jstack <pid> > thread_dump.txt

# Key things to look for:
# - BLOCKED threads waiting for a monitor (deadlock?)
# - WAITING on a condition (stuck forever?)
# - Many threads in same state (thread pool exhaustion?)

# Deadlock detection:
# jstack automatically detects deadlocks and prints:
# "Found 1 deadlock."
# "Thread-1": waiting to lock monitor 0x... held by "Thread-2"
# "Thread-2": waiting to lock monitor 0x... held by "Thread-1"
```

### Heap Dump (jmap)
```bash
# Take heap dump
jmap -dump:format=b,file=heap.hprof <pid>

# Live objects only (forces GC first)
jmap -dump:live,format=b,file=heap_live.hprof <pid>

# Heap summary
jmap -heap <pid>

# Class histogram (top memory consumers)
jmap -histo <pid> | head -20
```

### GC Stats (jstat)
```bash
# GC statistics every 1 second
jstat -gc <pid> 1000

# Output columns:
# S0C S1C    S0U S1U    EC    EU      OC      OU      MC    MU
# 1024 1024  0.0 512.0  8192  4096.0  20480   15360   ...
#
# C = Capacity, U = Used
# S0/S1 = Survivor, E = Eden, O = Old, M = Metaspace

# GC cause
jstat -gccause <pid> 1000
```

### Java Flight Recorder (JFR)
```bash
# Start recording (low overhead, production-safe)
jcmd <pid> JFR.start duration=60s filename=recording.jfr

# Continuous recording (ring buffer)
jcmd <pid> JFR.start maxsize=500m maxage=5m disk=true name=continuous

# Analyze with JDK Mission Control (jmc) or programmatically
```

---

## 10. GC Tuning Flags Reference

| Flag | Default | Description |
|------|---------|-------------|
| `-Xms` | Platform-dependent | Initial heap size |
| `-Xmx` | 1/4 of RAM | Maximum heap size |
| `-Xmn` | Varies | Young generation size |
| `-Xss` | 512K-1M | Thread stack size |
| `-XX:NewRatio=2` | 2 | Old:Young ratio (Old = 2x Young) |
| `-XX:SurvivorRatio=8` | 8 | Eden:Survivor ratio (Eden = 8x Survivor) |
| `-XX:MaxTenuringThreshold=15` | 15 | Max age before promotion to Old |
| `-XX:+UseG1GC` | Java 9+ | Use G1 collector |
| `-XX:MaxGCPauseMillis=200` | 200 | G1 target pause time (ms) |
| `-XX:G1HeapRegionSize=Nm` | Auto | G1 region size (1-32MB) |
| `-XX:InitiatingHeapOccupancyPercent=45` | 45 | When to start concurrent marking |
| `-XX:+UseZGC` | Off | Use ZGC collector |
| `-XX:+ZGenerational` | Off (Java 21) | Use generational ZGC |
| `-XX:MetaspaceSize=256m` | ~20MB | Initial Metaspace size |
| `-XX:MaxMetaspaceSize=512m` | Unlimited | Maximum Metaspace size |
| `-XX:+HeapDumpOnOutOfMemoryError` | Off | Dump heap on OOM |
| `-XX:HeapDumpPath=/path` | Working dir | Heap dump file location |
| `-XX:+PrintGCDetails` | Off | Detailed GC logging (Java 8) |
| `-Xlog:gc*:file=gc.log` | Off | GC logging (Java 9+) |
| `-XX:ParallelGCThreads=N` | CPU cores | Parallel GC thread count |
| `-XX:ConcGCThreads=N` | ParallelThreads/4 | Concurrent GC threads |
| `-XX:+UseCompressedOops` | On (<32GB heap) | Compress object pointers to 4 bytes |
| `-XX:+DoEscapeAnalysis` | On | Enable escape analysis |
| `-XX:CompileThreshold=10000` | 10000 | Method invocations before JIT |

---

## 11. Production JVM Configuration Example

```bash
# Typical production configuration for a microservice (8GB RAM, 4 cores)
java \
  -Xms4g -Xmx4g \                          # Fixed heap (avoid resize pauses)
  -XX:+UseG1GC \                            # G1 collector
  -XX:MaxGCPauseMillis=100 \                # Target 100ms pauses
  -XX:+UseStringDeduplication \             # G1 string dedup (saves heap)
  -XX:MetaspaceSize=256m \                  # Avoid early Metaspace GC
  -XX:MaxMetaspaceSize=512m \               # Cap Metaspace
  -XX:+HeapDumpOnOutOfMemoryError \         # Auto dump on OOM
  -XX:HeapDumpPath=/var/log/heapdump.hprof \
  -Xlog:gc*:file=/var/log/gc.log:time,level,tags:filecount=5,filesize=100m \
  -XX:+ExitOnOutOfMemoryError \             # Restart on OOM (let orchestrator handle)
  -jar app.jar

# For latency-critical service (Java 21+):
java \
  -Xms8g -Xmx8g \
  -XX:+UseZGC \                             # Sub-ms pauses
  -XX:+ZGenerational \                      # Generational ZGC (Java 21+)
  -XX:+HeapDumpOnOutOfMemoryError \
  -Xlog:gc*:file=/var/log/gc.log:time \
  -jar latency-critical-app.jar
```

---

## Summary: What Gets Asked in Interviews

| Topic | Key Points to Remember |
|-------|----------------------|
| Heap structure | Eden → S0/S1 → Old. Objects age through survivors. |
| Stack vs Heap | Stack: primitives + references, per-thread. Heap: objects, shared. |
| GC Roots | Local vars, static fields, active threads, JNI, monitors |
| G1GC | Region-based, predictable pauses, mixed collections |
| ZGC | Colored pointers, load barriers, <1ms pauses |
| Class Loading | Load → Link (Verify/Prepare/Resolve) → Init. Parent delegation. |
| volatile | Visibility + ordering, NOT atomicity |
| happens-before | synchronized unlock→lock, volatile write→read, start/join |
| Memory leaks | Static collections, listeners, ThreadLocal, inner classes |
| Double-checked locking | Needs volatile to prevent reordering of object construction |
| JIT optimizations | Inlining, escape analysis, loop unrolling |
| Object header | Mark word (hash, age, lock) + class pointer + padding to 8 bytes |
