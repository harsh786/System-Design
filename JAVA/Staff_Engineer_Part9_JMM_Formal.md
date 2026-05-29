# Staff Engineer - Part 9: Java Memory Model (JMM) Formal Semantics
# Happens-Before, Memory Ordering, Fences, and Correctness Proofs

---

## Q299: What is the Java Memory Model and why does it exist?

**Problem:** Modern CPUs reorder instructions and cache values in registers/L1/L2.
Without JMM, two threads reading/writing shared variables have UNDEFINED behavior.

```
CPU Core 1 (Thread A):        CPU Core 2 (Thread B):
┌────────────────────┐        ┌────────────────────┐
│ Registers          │        │ Registers          │
│ L1 Cache           │        │ L1 Cache           │
│ Store Buffer       │        │ Store Buffer       │
└────────┬───────────┘        └────────┬───────────┘
         │                             │
    ┌────┴─────────────────────────────┴────┐
    │         Shared L2/L3 Cache            │
    └────────────────┬──────────────────────┘
                     │
    ┌────────────────┴──────────────────────┐
    │            Main Memory                 │
    └───────────────────────────────────────┘

Without memory model guarantees:
- Thread A writes x=1 → may stay in Store Buffer (Thread B sees x=0!)
- CPU may reorder: store x=1; store y=1 → executed as store y=1; store x=1
- Compiler may reorder reads/writes for optimization
```

**JMM provides:**
1. Rules for when writes by one thread are GUARANTEED visible to another
2. Defines "happens-before" ordering between actions
3. Allows optimizations while preserving program correctness

---

## Q300: The Happens-Before Rules (Complete List)

**Definition:** If action A happens-before action B, then A's effects are GUARANTEED visible to B.

```java
// RULE 1: Program Order Rule
// Within a single thread, each action happens-before the next action
int x = 1;     // (1)
int y = x + 1; // (2) - guaranteed to see x=1 because (1) hb (2)

// RULE 2: Monitor Lock Rule  
// unlock(m) happens-before every subsequent lock(m)
synchronized (lock) {
    x = 1;  // Write inside lock
}
// ... Thread B ...
synchronized (lock) {
    int r = x;  // Guaranteed to see x=1 (or later writes)
}

// RULE 3: Volatile Variable Rule
// Write to volatile v happens-before every subsequent read of v
volatile boolean ready = false;
// Thread A:
data = 42;        // (1)
ready = true;     // (2) volatile write - PUBLISHES all prior writes

// Thread B:
if (ready) {      // (3) volatile read - ACQUIRES all writes before (2)
    use(data);    // (4) guaranteed to see data=42!
}
// Because: (1) →po (2) →hb (3) →po (4)
// Transitivity: (1) hb (4)

// RULE 4: Thread Start Rule
// thread.start() happens-before any action in the started thread
x = 42;
Thread t = new Thread(() -> {
    // Guaranteed to see x=42
    System.out.println(x);
});
t.start();  // start() hb first action in t

// RULE 5: Thread Termination Rule
// Any action in a thread happens-before thread.join() returns
Thread t = new Thread(() -> {
    x = 42;  // Action in thread t
});
t.start();
t.join();
// Here: guaranteed to see x=42 (t's actions hb join() return)

// RULE 6: Interruption Rule
// thread.interrupt() happens-before the interrupted thread detects interruption

// RULE 7: Finalizer Rule
// Constructor completion happens-before the start of the finalizer

// RULE 8: Transitivity
// If A hb B and B hb C, then A hb C
```

---

## Q301: Volatile - Full Semantics Explained

```java
// Volatile provides TWO guarantees:
// 1. Visibility: write to volatile is immediately visible to all threads
// 2. Ordering: acts as a memory fence (no reordering across volatile)

// volatile write = StoreStore + StoreLoad fence
// volatile read  = LoadLoad + LoadStore fence

// Example: Double-Checked Locking (DCL)
class Singleton {
    private static volatile Singleton instance;  // MUST be volatile!
    
    static Singleton getInstance() {
        if (instance == null) {           // First check (no lock)
            synchronized (Singleton.class) {
                if (instance == null) {   // Second check (with lock)
                    instance = new Singleton();
                }
            }
        }
        return instance;
    }
}

// WHY volatile is needed:
// Without volatile, "instance = new Singleton()" is actually 3 steps:
//   1. Allocate memory
//   2. Call constructor (initialize fields)
//   3. Assign reference to 'instance'
// CPU may reorder to: 1 → 3 → 2
// Another thread sees instance != null, but constructor hasn't run yet!
// volatile prevents this reordering (StoreStore fence before assign)

// Volatile DOES NOT provide atomicity!
volatile int count = 0;
count++;  // NOT atomic! (read + increment + write)
// Two threads: both read 0, both write 1. Lost update!
// Use AtomicInteger for atomic increment.
```

---

## Q302: Memory Fences / Barriers Explained

```
FENCE TYPES (from CPU architecture, JMM abstracts these):

LoadLoad fence:   Loads BEFORE fence complete before loads AFTER fence
StoreStore fence: Stores BEFORE fence complete before stores AFTER fence
LoadStore fence:  Loads BEFORE fence complete before stores AFTER fence
StoreLoad fence:  Stores BEFORE fence complete before loads AFTER fence
                  (MOST EXPENSIVE - full memory barrier)

How Java constructs map to fences:

volatile read:  [LoadLoad | LoadStore]  (acquire semantics)
                (nothing before this read can be reordered after it)

volatile write: [StoreStore | StoreLoad] (release semantics)
                (nothing after this write can be reordered before it)

synchronized entry (monitorenter): acquire fence
synchronized exit (monitorexit):   release fence + flush store buffer

VarHandle operations:
  getAcquire()    → LoadLoad + LoadStore (like volatile read)
  setRelease()    → StoreStore + LoadStore (like volatile write, cheaper!)
  getOpaque()     → no fence, just prevents compiler reorder
  setOpaque()     → no fence, just prevents compiler reorder
```

---

## Q303: VarHandle - Fine-Grained Memory Ordering (Java 9+)

```java
// VarHandle provides access modes with different memory ordering:
// Plain:       no ordering guarantees (fastest, like normal field access)
// Opaque:      no reordering of THIS access, but no fence
// Acquire/Release: one-directional fence (cheaper than volatile)
// Volatile:    full fence (like volatile field)

class Counter {
    private int value;
    private static final VarHandle VALUE;
    
    static {
        try {
            VALUE = MethodHandles.lookup()
                .findVarHandle(Counter.class, "value", int.class);
        } catch (Exception e) { throw new ExceptionInInitializerError(e); }
    }
    
    // Different access modes:
    int getPlain() { return (int) VALUE.get(this); }            // No ordering
    int getOpaque() { return (int) VALUE.getOpaque(this); }     // No tearing
    int getAcquire() { return (int) VALUE.getAcquire(this); }   // Acquire fence
    int getVolatile() { return (int) VALUE.getVolatile(this); } // Full fence
    
    void setRelease(int v) { VALUE.setRelease(this, v); }      // Release fence
    void setVolatile(int v) { VALUE.setVolatile(this, v); }    // Full fence
    
    // Compare-and-swap with different ordering:
    boolean casRelease(int expected, int newVal) {
        return VALUE.compareAndExchangeRelease(this, expected, newVal) == expected;
    }
    
    // Atomic add (like AtomicInteger.getAndAdd)
    int getAndAdd(int delta) {
        return (int) VALUE.getAndAdd(this, delta);
    }
}

// WHEN TO USE WHAT:
// Plain: single-thread access, or protected by lock
// Opaque: statistics counters (no tearing, no ordering needed)
// Acquire/Release: producer-consumer patterns (cheaper than volatile!)
// Volatile: rarely needed directly (full fence is expensive)
```

---

## Q304: Proving Program Correctness Under JMM

### Example 1: Proving a publication pattern is safe

```java
// Is this safe? (Thread A writes, Thread B reads)
class Holder {
    int x;
    int y;
}

volatile Holder holder = null;

// Thread A:
Holder h = new Holder();
h.x = 1;          // (1)
h.y = 2;          // (2)
holder = h;        // (3) volatile write

// Thread B:
Holder h = holder; // (4) volatile read
if (h != null) {
    assert h.x == 1; // (5) SAFE?
    assert h.y == 2; // (6) SAFE?
}

// PROOF:
// By program order:   (1) →po (2) →po (3)
// By volatile rule:   (3) →hb (4) (volatile write hb volatile read)
// By program order:   (4) →po (5), (4) →po (6)
// By transitivity:    (1) →hb (5), (2) →hb (6)
// Therefore: Thread B is GUARANTEED to see x=1 and y=2. ✓
```

### Example 2: Proving Double-Checked Locking without volatile is BROKEN

```java
class BrokenSingleton {
    private static BrokenSingleton instance;  // NOT volatile!
    private int value;
    
    private BrokenSingleton() { this.value = 42; }
    
    static BrokenSingleton getInstance() {
        if (instance == null) {            // (1) read instance
            synchronized (BrokenSingleton.class) {
                if (instance == null) {    // (2) read instance (under lock)
                    instance = new BrokenSingleton(); // (3) write instance
                }
            }
        }
        return instance;                   // (4) read instance
    }
    
    int getValue() { return value; }       // (5) read value
}

// WHY THIS IS BROKEN:
// Thread A executes (3): instance = new BrokenSingleton()
//   This is: allocate → write value=42 → write instance=ref
//   CPU/compiler may reorder to: allocate → write instance=ref → write value=42
//
// Thread B executes (1): reads instance != null (sees ref from reordered write)
// Thread B executes (5): reads value... gets 0! (constructor not finished!)
//
// There's NO happens-before between (3) and (1):
// - (3) is inside synchronized, but (1) is OUTSIDE synchronized
// - No volatile, no lock → no happens-before → no guarantee!
//
// FIX: Make instance volatile → volatile write(3) hb volatile read(1)
```

### Example 3: Safe Publication Patterns

```java
// SAFE publication methods:
// 1. volatile field
volatile Object published;

// 2. Through synchronized block
synchronized (lock) { published = obj; }  // Writer
synchronized (lock) { use(published); }   // Reader

// 3. Final field in properly constructed object
class ImmutableHolder {
    final int value;  // Final field semantics guarantee visibility!
    
    ImmutableHolder(int v) { 
        this.value = v;
        // Implicit freeze action at end of constructor
        // ANY thread that sees this object will see value = v
    }
}
// Even if reference is published via data race, final fields are safe!

// 4. AtomicReference
AtomicReference<Config> config = new AtomicReference<>(initialConfig);

// 5. static initializer (class loading is synchronized)
class Registry {
    static final Map<String, Object> INSTANCE = buildRegistry();
}
```

---

## Q305: Final Field Semantics (Deep Dive)

```java
// Final fields have special memory model guarantees:
// If an object is "properly constructed" (this doesn't escape constructor),
// then ANY thread that obtains a reference to it will see
// the correct values of its final fields.

class FinalFieldExample {
    final int x;
    int y;  // non-final, no guarantee!
    
    FinalFieldExample() {
        x = 3;
        y = 4;
    }
}

// Thread A:
FinalFieldExample f = new FinalFieldExample();
sharedRef = f;  // publish (even without volatile!)

// Thread B:
FinalFieldExample local = sharedRef;
if (local != null) {
    assert local.x == 3;  // GUARANTEED (final field semantics)
    // local.y may be 0 or 4 (no guarantee for non-final!)
}

// WHY? JMM inserts a "freeze" action after final field write in constructor.
// Any read that sees the object reference must also see writes
// to final fields (and anything reachable through final fields!)

// This means: final fields in constructor create a happens-before edge
// from constructor completion to any reader of the object.

// CAVEAT: "this" must not escape during construction!
class Broken {
    final int x;
    
    Broken() {
        // BAD: publishing 'this' before constructor completes
        GlobalRegistry.register(this);  // Another thread may read x=0!
        x = 42;
    }
}
```

---

## Q306: Data Races and Benign Data Races

```java
// DATA RACE: two threads access same variable, at least one writes, 
// no happens-before ordering between them.

// JMM says: programs with data races have UNDEFINED behavior
// (except for final fields and volatile accesses)

// "BENIGN" DATA RACE examples (technically undefined but commonly used):

// 1. HashMap.size() in ConcurrentHashMap (pre-Java 8)
// Multiple threads update count concurrently
// Readers get approximate count (acceptable for monitoring)

// 2. Double-checked locking for caching
class StringCache {
    private String cachedValue;  // data race on read!
    
    String getValue() {
        String result = cachedValue;  // Racy read
        if (result == null) {
            synchronized (this) {
                result = cachedValue;
                if (result == null) {
                    result = computeExpensiveString();
                    cachedValue = result;
                }
            }
        }
        return result;
    }
    // This is ONLY safe because String is immutable and final fields
    // guarantee its contents are visible once the reference is seen!
}

// 3. Racy single-check idiom (used in JDK for String.hashCode()!)
class HasCachedHash {
    private int hash;  // Default 0, no synchronization!
    
    int hashCode() {
        int h = hash;
        if (h == 0) {
            h = computeHash();
            hash = h;  // Racy write - other threads may recompute, that's OK
        }
        return h;
    }
    // Safe because: int write is atomic on most platforms,
    // and recomputation gives same result (idempotent)
}
```

---

## Q307: Acquire-Release Semantics Explained

```
ACQUIRE = "everything I read AFTER this point sees up-to-date values"
RELEASE = "everything I wrote BEFORE this point is now visible to acquirers"

Example:
Thread A (Producer):          Thread B (Consumer):
  data = 42;      ← write      
  flag.setRelease(true); ← RELEASE    
                              if (flag.getAcquire()) { ← ACQUIRE
                                  use(data); ← sees 42! 
                              }

The release "pushes" all prior writes to shared memory.
The acquire "pulls" all writes that happened before the matching release.

Compared to volatile (full fence):
- volatile write = release + StoreLoad barrier (heavier!)
- volatile read  = LoadLoad + acquire (slightly heavier)
- Acquire/Release is SUFFICIENT for producer-consumer
- Full volatile needed only when writes must be ordered relative to LATER reads

Performance:
x86: acquire/release are essentially free (x86 has strong memory model)
ARM/RISC-V: acquire = load + dmb ld, release = dmb st + store (real cost!)
```

---

## Q308: Common JMM Interview Traps

### Trap 1: "Can this assertion fail?"

```java
int a = 0, b = 0;

// Thread 1:
a = 1;
int r1 = b;

// Thread 2:
b = 1;
int r2 = a;

// Can r1 == 0 AND r2 == 0?
// Answer: YES! Both reads can see the initial values.
// CPU reordering: Thread 1 executes "read b" before "write a"
//                 Thread 2 executes "read a" before "write b"
// No happens-before between these threads = anything goes!
```

### Trap 2: "Is this initialization safe?"

```java
class Resource {
    int value;
    Resource() { this.value = 42; }
}

Resource resource = null;

// Thread A:
resource = new Resource();

// Thread B:
Resource r = resource;
if (r != null) {
    System.out.println(r.value);  // Can print 0!
}

// WHY: No happens-before between Thread A's write and Thread B's read.
// Thread B may see a partially constructed object!
// FIX: Make 'resource' volatile, or make 'value' final.
```

### Trap 3: "Does volatile on one variable protect others?"

```java
int x = 0;
volatile boolean ready = false;

// Thread A:
x = 42;          // (1) non-volatile write
ready = true;    // (2) volatile write

// Thread B:
if (ready) {     // (3) volatile read
    int r = x;   // (4) Sees 42? YES!
}

// WHY it works:
// (1) →po (2): program order in Thread A
// (2) →hb (3): volatile write happens-before volatile read
// (3) →po (4): program order in Thread B
// By transitivity: (1) →hb (4). Thread B MUST see x=42.

// KEY INSIGHT: Volatile write "publishes" ALL prior writes (not just the volatile!)
// This is the "piggybacking" technique.
```

### Trap 4: "Are 64-bit writes atomic?"

```java
long x = 0;  // NOT volatile

// Thread A:
x = 0xFFFFFFFF_FFFFFFFFL;

// Thread B:
long r = x;
// Can r be 0x00000000_FFFFFFFF or 0xFFFFFFFF_00000000?
// JMM says: YES! (word tearing on 32-bit JVMs)
// Spec says 64-bit non-volatile reads/writes may be treated as two 32-bit ops.
// FIX: Make 'x' volatile (guarantees atomic 64-bit access)
// NOTE: On 64-bit JVMs, tearing doesn't happen in practice, but it's not guaranteed!
```

---

## Q309: Implementing a Lock-Free Queue (Michael-Scott Queue)

```java
// Classic lock-free MPMC queue using CAS
class LockFreeQueue<T> {
    private static class Node<T> {
        final T value;
        final AtomicReference<Node<T>> next = new AtomicReference<>(null);
        
        Node(T value) { this.value = value; }
    }
    
    private final AtomicReference<Node<T>> head;
    private final AtomicReference<Node<T>> tail;
    
    LockFreeQueue() {
        Node<T> sentinel = new Node<>(null);  // Dummy node
        head = new AtomicReference<>(sentinel);
        tail = new AtomicReference<>(sentinel);
    }
    
    void enqueue(T value) {
        Node<T> newNode = new Node<>(value);
        
        while (true) {
            Node<T> curTail = tail.get();
            Node<T> tailNext = curTail.next.get();
            
            if (curTail == tail.get()) {  // Still consistent?
                if (tailNext == null) {
                    // Tail is at the actual last node
                    if (curTail.next.compareAndSet(null, newNode)) {
                        // Successfully linked! Now try to advance tail
                        tail.compareAndSet(curTail, newNode);
                        return;
                    }
                } else {
                    // Tail is lagging, help advance it
                    tail.compareAndSet(curTail, tailNext);
                }
            }
        }
    }
    
    T dequeue() {
        while (true) {
            Node<T> curHead = head.get();
            Node<T> curTail = tail.get();
            Node<T> headNext = curHead.next.get();
            
            if (curHead == head.get()) {  // Still consistent?
                if (curHead == curTail) {
                    // Queue empty or tail lagging
                    if (headNext == null) return null;  // Empty
                    tail.compareAndSet(curTail, headNext);  // Help advance tail
                } else {
                    // Read value before CAS (may be overwritten after)
                    T value = headNext.value;
                    if (head.compareAndSet(curHead, headNext)) {
                        return value;  // Successfully dequeued
                    }
                }
            }
        }
    }
    
    // WHY this is correct:
    // 1. enqueue: CAS on tail.next ensures only one thread links a new node
    // 2. dequeue: CAS on head ensures only one thread advances head
    // 3. "Helping": if tail is lagging, any thread can advance it
    // 4. AtomicReference provides volatile semantics (visibility guaranteed)
    // 5. No ABA problem because we only CAS references (GC prevents reuse)
}
```

---

## Q310: Implementing Seqlock (Read-optimized lock)

```java
// Seqlock: optimistic reads (no lock), only writers lock
// Used in: Linux kernel (jiffies), financial data feeds

class SeqLock {
    private final AtomicInteger sequence = new AtomicInteger(0);
    private final ReentrantLock writeLock = new ReentrantLock();
    
    // Writer: exclusive access
    void write(Runnable writeAction) {
        writeLock.lock();
        try {
            sequence.incrementAndGet();  // Odd = write in progress
            VarHandle.storeStoreFence(); // Ensure increment visible before writes
            
            writeAction.run();
            
            VarHandle.storeStoreFence(); // Ensure writes visible before increment
            sequence.incrementAndGet();  // Even = write complete
        } finally {
            writeLock.unlock();
        }
    }
    
    // Reader: optimistic, retry if writer was active
    <T> T read(Supplier<T> readAction) {
        while (true) {
            int seq1 = sequence.get();
            if ((seq1 & 1) != 0) continue;  // Odd = write in progress, retry
            
            VarHandle.loadLoadFence();  // Ensure we read AFTER getting sequence
            T result = readAction.get();
            VarHandle.loadLoadFence();  // Ensure we read BEFORE checking sequence
            
            int seq2 = sequence.get();
            if (seq1 == seq2) return result;  // No write happened during our read
            // Otherwise: retry
        }
    }
}

// Usage: High-read, low-write scenario (stock prices, config)
class StockPrice {
    private final SeqLock lock = new SeqLock();
    private double bid;
    private double ask;
    private long timestamp;
    
    void update(double bid, double ask, long timestamp) {
        lock.write(() -> {
            this.bid = bid;
            this.ask = ask;
            this.timestamp = timestamp;
        });
    }
    
    Quote read() {
        return lock.read(() -> new Quote(bid, ask, timestamp));
    }
}
```

---

## Q311: Memory Ordering on Different CPU Architectures

```
x86/x64 (Intel/AMD): STRONG memory model (Total Store Order - TSO)
├── Loads not reordered with other loads
├── Stores not reordered with other stores
├── Stores not reordered with EARLIER loads
├── BUT: Loads CAN be reordered with EARLIER stores (Store Buffer!)
├── Implication: volatile read = free, volatile write = MFENCE (expensive)
└── Most Java programs "accidentally work" on x86 even without volatile

ARM/AArch64: WEAK memory model
├── ANY reordering possible (load-load, store-store, load-store, store-load)
├── Need explicit barriers (DMB, DSB, ISB)
├── Implication: More bugs caught on ARM than x86!
└── Cloud testing: Always test on ARM (e.g., AWS Graviton) to catch races!

RISC-V: WEAK memory model (similar to ARM)
├── FENCE instruction for ordering
└── RVWMO (RISC-V Weak Memory Ordering)

WHY THIS MATTERS:
- Code that works on x86 may BREAK on ARM (store-store reordering!)
- JMM abstracts this: if you follow JMM rules, it works on ALL platforms
- If you violate JMM (data races), x86 might hide bugs that ARM exposes
```

---

## Q312: AtomicInteger vs LongAdder - When to use which?

```java
// AtomicInteger: single CAS retry loop
class AtomicCounter {
    AtomicInteger count = new AtomicInteger(0);
    
    void increment() {
        count.incrementAndGet();
        // Internally: CAS loop
        // If 100 threads contend: 99 retries per operation!
    }
}

// LongAdder: striped (distributed counters to reduce contention)
class StripedCounter {
    LongAdder count = new LongAdder();
    
    void increment() {
        count.increment();
        // Internally: each thread writes to ITS OWN Cell
        // No contention! (usually)
    }
    
    long get() {
        return count.sum();
        // Sums all Cells (slightly stale, but eventually consistent)
    }
}

// LongAdder internal structure:
// ┌─────────────────────────────────────────────────┐
// │ base (AtomicLong) + Cell[] cells                 │
// │                                                  │
// │ Thread 1 → Cell[0]  (hash(thread) % cells.length)│
// │ Thread 2 → Cell[1]                               │
// │ Thread 3 → Cell[2]                               │
// │ Thread 4 → Cell[0]  (collision → expand array)   │
// │                                                  │
// │ sum() = base + cells[0] + cells[1] + cells[2]    │
// └─────────────────────────────────────────────────┘

// WHEN TO USE:
// AtomicInteger/Long: need exact value immediately (e.g., sequence number)
// LongAdder: high-contention counters where sum() is infrequent
//            (metrics, statistics, hit counters)

// Performance under 16 threads:
// AtomicLong.incrementAndGet():  ~50 million ops/sec
// LongAdder.increment():         ~500 million ops/sec (10x faster!)
```

---

## Q313: False Sharing - The Hidden Performance Killer

```java
// False sharing: two independent variables on SAME cache line
// Updating one invalidates the other (MESI protocol coherence traffic!)

// CACHE LINE = 64 bytes (x86)
// If two AtomicLongs are adjacent, they share a cache line!

// PROBLEM:
class FalseSharing {
    // These are on the SAME cache line (8 bytes each, adjacent)
    volatile long counter1 = 0;  // Thread 1 increments this
    volatile long counter2 = 0;  // Thread 2 increments this
    // Performance: TERRIBLE (constant cache line bouncing between cores)
}

// FIX: Pad to separate cache lines
class NoPadding {
    volatile long counter1 = 0;
    long p1, p2, p3, p4, p5, p6, p7;  // 56 bytes padding
    volatile long counter2 = 0;  // Now on different cache line!
}

// Java 8+ fix: @Contended annotation
@sun.misc.Contended  // JVM adds padding automatically
class PaddedCounter {
    volatile long counter;
}

// Or per-field:
class TwoCounters {
    @jdk.internal.vm.annotation.Contended("group1")
    volatile long counter1;
    
    @jdk.internal.vm.annotation.Contended("group2")
    volatile long counter2;
}
// Need: -XX:-RestrictContended to allow in user code

// Real-world example: Thread.currentThread().threadLocalRandomSeed
// @Contended in Thread class to avoid false sharing between threads!

// Performance impact:
// Without padding: ~100M ops/sec (cache thrashing)
// With padding:    ~800M ops/sec (8x improvement!)
```

---

## Q314: Formal Definition - Sequential Consistency vs JMM

```
SEQUENTIAL CONSISTENCY (Lamport, 1979):
"The result of any execution is the same as if the operations of all processors
were executed in some sequential order, and the operations of each individual
processor appear in this sequence in the order specified by its program."

JMM is WEAKER than Sequential Consistency:
- SC: all threads see the same global order of ALL operations
- JMM: only requires happens-before edges to be respected
- JMM allows more optimizations (better performance!)

Example where JMM differs from SC:
// Initially: x = 0, y = 0

Thread 1:      Thread 2:
x = 1;         y = 1;
r1 = y;        r2 = x;

Under SC: r1=0, r2=0 is IMPOSSIBLE
  (either x=1 is visible before r2=x, or y=1 is visible before r1=y)

Under JMM: r1=0, r2=0 IS POSSIBLE!
  (no happens-before between x=1 and r2=x, or y=1 and r1=y)
  Both writes can stay in store buffers!

To get SC in JMM: make x and y volatile
  → volatile write hb volatile read
  → SC is restored for volatile accesses
```

---

## Q315: JMM Cookbook for Staff Engineers

```
PATTERN                          SOLUTION
─────────────────────────────────────────────────────────────
Publish immutable object         final fields (safest, cheapest)
Publish mutable object           volatile reference
Protect shared mutable state     synchronized / Lock
Atomic counter (low contention)  AtomicInteger/Long
Atomic counter (high contention) LongAdder
Status flag                      volatile boolean
One-shot latch                   volatile + final state
Safe singleton                   static holder class (best)
Safe lazy init                   volatile + DCL
Lock-free data structure         CAS loops + VarHandle
Statistics (approx OK)           Opaque access mode
High-perf producer-consumer      Acquire/Release semantics

ORDERING STRENGTH (weakest → strongest):
Plain → Opaque → Acquire/Release → Volatile → Synchronized

DEBUGGING MEMORY ISSUES:
1. -XX:+PrintCompilation (see JIT optimizations)
2. jcmd <pid> Compiler.queue (check what's being compiled)
3. -XX:-TieredCompilation -XX:CompileThreshold=1 (reproduce in C2)
4. Run on ARM instance (exposes races x86 hides!)
5. Java Concurrency Stress tests (jcstress): 
   https://github.com/openjdk/jcstress
```

---

## Q316: jcstress Examples (Proving Memory Model Properties)

```java
// jcstress: OpenJDK framework to empirically test JMM behaviors

@JCStressTest
@State
@Outcome(id = "0, 0", expect = Expect.ACCEPTABLE, desc = "Both read default")
@Outcome(id = "1, 0", expect = Expect.ACCEPTABLE, desc = "T1 write visible to T1 only")
@Outcome(id = "0, 1", expect = Expect.ACCEPTABLE, desc = "T2 write visible to T2 only")  
@Outcome(id = "1, 1", expect = Expect.ACCEPTABLE, desc = "Both writes visible")
public class PlainReorderingTest {
    int x, y;
    
    @Actor
    public void actor1(II_Result r) {
        x = 1;
        r.r1 = y;
    }
    
    @Actor
    public void actor2(II_Result r) {
        y = 1;
        r.r2 = x;
    }
    // Result r1=0, r2=0 IS observed on x86! (store buffer delay)
}

// Volatile version: r1=0, r2=0 becomes FORBIDDEN
@JCStressTest
@State
@Outcome(id = "0, 0", expect = Expect.FORBIDDEN, desc = "Cannot happen with volatile")
@Outcome(id = "1, 0", expect = Expect.ACCEPTABLE)
@Outcome(id = "0, 1", expect = Expect.ACCEPTABLE)
@Outcome(id = "1, 1", expect = Expect.ACCEPTABLE)
public class VolatileOrderingTest {
    volatile int x, y;
    
    @Actor
    public void actor1(II_Result r) { x = 1; r.r1 = y; }
    
    @Actor
    public void actor2(II_Result r) { y = 1; r.r2 = x; }
}
```

---

## Summary: JMM Rules Every Staff Engineer Must Know

```
1. No happens-before = no guarantee (data race = undefined behavior)
2. volatile write "publishes" ALL prior writes (not just the volatile field!)
3. volatile read "acquires" all writes visible at the matching volatile write
4. final fields are safe to read without synchronization (after construction)
5. synchronized provides mutual exclusion AND memory visibility
6. AtomicXxx provides volatile semantics + atomic RMW operations
7. Thread.start()/join() create happens-before edges
8. x86 hides bugs that ARM exposes (always test on ARM!)
9. LongAdder >> AtomicLong under contention
10. @Contended prevents false sharing
11. VarHandle gives fine-grained control (acquire/release cheaper than volatile)
12. DCL requires volatile (without it, partially constructed objects visible!)
```

