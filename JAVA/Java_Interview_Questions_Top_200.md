# Top 200+ Java Interview Questions - World Class In-Depth Guide

## Table of Contents
1. [HashMap - Internal Working & Concurrency](#1-hashmap---internal-working--concurrency)
2. [ConcurrentHashMap - Deep Dive](#2-concurrenthashmap---deep-dive)
3. [Java Collections Framework](#3-java-collections-framework)
4. [Java 8+ Features](#4-java-8-features)
5. [Garbage Collection](#5-garbage-collection)
6. [Memory Management & Debugging](#6-memory-management--debugging)
7. [CPU Debugging & Performance](#7-cpu-debugging--performance)
8. [Multithreading & Concurrency (Advanced)](#8-multithreading--concurrency-advanced)
9. [JVM Internals](#9-jvm-internals)
10. [Design Patterns & SOLID](#10-design-patterns--solid)
11. [Spring & Microservices](#11-spring--microservices)

---

## 1. HashMap - Internal Working & Concurrency

### Q1: How does HashMap work internally in Java?

**Answer:**

HashMap uses an **array of Node<K,V>** (called table/buckets) combined with **linked lists** and **red-black trees** (Java 8+).

**Internal Structure:**
```java
// Simplified internal structure
transient Node<K,V>[] table;  // Array of buckets (default size 16)

static class Node<K,V> implements Map.Entry<K,V> {
    final int hash;
    final K key;
    V value;
    Node<K,V> next;  // Linked list pointer
}
```

**Step-by-step PUT operation:**

1. **Calculate hash:** `hash = hash(key.hashCode())` - Spreads higher bits of hashCode to lower bits using XOR
   ```java
   static final int hash(Object key) {
       int h;
       return (key == null) ? 0 : (h = key.hashCode()) ^ (h >>> 16);
   }
   ```

2. **Calculate bucket index:** `index = (n - 1) & hash` where n is table length (always power of 2)

3. **Check bucket:**
   - If bucket is empty → create new Node and place it there
   - If bucket has entries → compare hash and key using `equals()`
     - If key exists → replace value
     - If key doesn't exist → append to linked list (or tree)

4. **Treeification:** If linked list length exceeds **TREEIFY_THRESHOLD (8)** AND table size >= 64, convert linked list to Red-Black Tree (O(log n) lookup instead of O(n))

5. **Resize:** If size > capacity * loadFactor (default 0.75), resize table to double its size and rehash all entries

**GET operation:**
1. Calculate hash of key
2. Find bucket index: `(n-1) & hash`
3. Traverse linked list/tree in that bucket
4. Compare hash first (fast), then equals() to find exact match
5. Return value or null

---

### Q2: Why is the initial capacity always a power of 2?

**Answer:**

Because the bucket index is calculated using `(n-1) & hash` instead of `hash % n`.

- **Bitwise AND is faster** than modulo operation
- When n is a power of 2, `(n-1)` produces all 1s in binary (e.g., 16-1 = 15 = 1111)
- This ensures hash bits are evenly distributed across all buckets
- Example: If n=16, (n-1)=15=0b1111, so `hash & 0b1111` gives values 0-15

If n were not a power of 2, some buckets would never be used, causing poor distribution.

---

### Q3: What happens during HashMap resize (rehashing)?

**Answer:**

When `size > capacity * loadFactor`:

1. **New array created** with double the size (e.g., 16 → 32)
2. **All existing entries are rehashed** and redistributed
3. Each entry either stays at the **same index** OR moves to `oldIndex + oldCapacity`

```java
// Java 8 optimization - no need to recalculate hash
// Because capacity doubles (power of 2), each node either:
// - Stays at index i (if new bit is 0)
// - Moves to index i + oldCap (if new bit is 1)

// Example: oldCap = 16 (10000), newCap = 32 (100000)
// hash & 10000 == 0 → stays at same index
// hash & 10000 == 1 → moves to index + 16
```

**Performance impact:** Resizing is O(n) and causes a **stop-the-world** pause for that HashMap. This is why setting initial capacity properly is important for performance-critical applications.

---

### Q4: Why does HashMap fail in concurrent environments?

**Answer:**

HashMap is **NOT thread-safe**. Concurrent access causes:

**Problem 1: Infinite Loop (Java 7 - Linked List)**
In Java 7, during resize, the linked list was reversed. If two threads resize simultaneously:
```
Thread 1: A → B → C (reading order)
Thread 2: C → B → A (reversed during resize)
// Can create: A → B → A (circular reference = infinite loop)
```
In Java 8, this specific issue is fixed (tail insertion instead of head insertion), but other problems remain.

**Problem 2: Lost Updates**
```java
// Thread 1: map.put("key1", value1) → calculates bucket index 5
// Thread 2: map.put("key2", value2) → calculates same bucket index 5
// Both threads see bucket 5 is empty
// Thread 1 writes Node to bucket 5
// Thread 2 overwrites bucket 5 → Thread 1's entry is LOST
```

**Problem 3: Corrupted Size**
```java
// size++ is not atomic (read-modify-write)
// Thread 1: reads size=10, increments to 11
// Thread 2: reads size=10 (before T1 writes), increments to 11
// Result: size=11 but actually 12 entries exist
// This can delay resize, causing longer chains
```

**Problem 4: Partial Reads During Resize**
```java
// Thread 1 is resizing (creating new table, moving entries)
// Thread 2 is reading → may see partially moved state
// Some entries appear to be "missing" temporarily
```

**Problem 5: Visibility Issues (Memory Model)**
Without synchronization, changes made by one thread may not be visible to others due to CPU cache/register optimizations.

---

### Q5: What is the significance of hashCode() and equals() contract?

**Answer:**

**Contract Rules:**
1. If `a.equals(b)` is true → `a.hashCode() == b.hashCode()` MUST be true
2. If `a.hashCode() == b.hashCode()` → `a.equals(b)` MAY OR MAY NOT be true (collision)
3. `hashCode()` must be consistent during object lifetime (while in map)

**What breaks if violated:**

```java
class BadKey {
    int id;
    String name;
    
    @Override
    public boolean equals(Object o) {
        return this.id == ((BadKey)o).id && this.name.equals(((BadKey)o).name);
    }
    
    // BROKEN: No hashCode override!
    // Default Object.hashCode() uses memory address
}

Map<BadKey, String> map = new HashMap<>();
BadKey key = new BadKey(1, "test");
map.put(key, "value");
map.get(new BadKey(1, "test")); // Returns NULL! Different hashCode → different bucket
```

**Best practices:**
- Always override both hashCode() and equals() together
- Use immutable fields for hashCode calculation
- Use Objects.hash() for clean implementation
- Never use mutable objects as HashMap keys

---

### Q6: What is hash collision and how is it resolved?

**Answer:**

**Hash collision** occurs when two different keys produce the same bucket index.

**Resolution in Java HashMap:**

1. **Separate Chaining (Linked List):** Multiple entries in same bucket form a linked list
2. **Treeification (Java 8+):** When chain length > 8, converts to Red-Black Tree

```
Bucket[5]: Node("key1",v1) → Node("key2",v2) → Node("key3",v3)  [Linked List]

// After 8+ collisions in same bucket:
Bucket[5]: RedBlackTree containing all colliding entries  [O(log n) access]
```

**Untreeify:** When tree size drops below 6 (UNTREEIFY_THRESHOLD), it converts back to linked list.

**Why threshold is 8?**
- Under random hashing, probability of 8+ items in one bucket follows Poisson distribution
- Probability is approximately 0.00000006 (6 in 100 million)
- So treeification is rare and only happens with poor hash functions

---

### Q7: Difference between HashMap, Hashtable, and Collections.synchronizedMap()?

**Answer:**

| Feature | HashMap | Hashtable | synchronizedMap |
|---------|---------|-----------|-----------------|
| Thread-safe | No | Yes (synchronized methods) | Yes (synchronized wrapper) |
| Null keys | 1 null key allowed | No null key/value | 1 null key allowed |
| Performance | Best (no sync overhead) | Slow (entire map locked) | Slow (entire map locked) |
| Iterator | Fail-fast | Fail-safe (Enumerator) | Fail-fast |
| Inheritance | AbstractMap | Dictionary (legacy) | Wrapper around any Map |
| Lock granularity | N/A | Entire map | Entire map |

**Why all three are inferior to ConcurrentHashMap for concurrent use:**
- Hashtable/synchronizedMap lock the ENTIRE map for every operation
- Only one thread can access at a time (even for reads!)
- ConcurrentHashMap uses segment-level/node-level locking

---

### Q8: What is the time complexity of HashMap operations?

**Answer:**

| Operation | Average Case | Worst Case (Java 7) | Worst Case (Java 8+) |
|-----------|-------------|---------------------|----------------------|
| put() | O(1) | O(n) - all in one bucket | O(log n) - tree |
| get() | O(1) | O(n) | O(log n) |
| remove() | O(1) | O(n) | O(log n) |
| containsKey() | O(1) | O(n) | O(log n) |
| containsValue() | O(n) | O(n) | O(n) |

**Space complexity:** O(n) where n is number of entries

---

### Q9: How does Java 8 improve HashMap over Java 7?

**Answer:**

| Aspect | Java 7 | Java 8 |
|--------|--------|--------|
| Collision handling | Only Linked List | Linked List + Red-Black Tree |
| Insertion order in bucket | Head insertion | Tail insertion |
| Resize safety | Infinite loop possible | No infinite loop |
| Worst case lookup | O(n) | O(log n) |
| Hash function | Multiple rounds | Single XOR operation |
| Treeification | N/A | Converts at threshold 8 |

---

### Q10: What happens when you put a null key in HashMap?

**Answer:**

```java
// Null key always goes to bucket 0
static final int hash(Object key) {
    int h;
    return (key == null) ? 0 : (h = key.hashCode()) ^ (h >>> 16);
}
```

- HashMap allows exactly ONE null key (stored at index 0)
- HashMap allows multiple null values
- ConcurrentHashMap does NOT allow null keys or values (ambiguity: is null a value or key-not-found?)

---

## 2. ConcurrentHashMap - Deep Dive

### Q11: How does ConcurrentHashMap work internally?

**Answer:**

**Java 7 Implementation (Segment-based):**
```
ConcurrentHashMap
├── Segment[0] (ReentrantLock) → HashEntry[] table
├── Segment[1] (ReentrantLock) → HashEntry[] table
├── ...
└── Segment[15] (ReentrantLock) → HashEntry[] table

// Default: 16 segments = 16 concurrent writers
// Each segment is independently locked
```

**Java 8+ Implementation (Node-based with CAS):**
```java
// No more segments! Uses:
// 1. CAS (Compare-And-Swap) for empty bucket insertion
// 2. synchronized on first node of bucket for collision handling
// 3. Volatile reads for visibility

transient volatile Node<K,V>[] table;

// PUT operation (simplified):
final V putVal(K key, V value, boolean onlyIfAbsent) {
    int hash = spread(key.hashCode());
    for (Node<K,V>[] tab = table;;) {
        Node<K,V> f; int n, i, fh;
        if (tab == null)
            tab = initTable();  // Lazy initialization with CAS
        else if ((f = tabAt(tab, i = (n-1) & hash)) == null) {
            // Empty bucket → CAS to insert (no lock needed!)
            if (casTabAt(tab, i, null, new Node<K,V>(hash, key, value)))
                break;
        } else if ((fh = f.hash) == MOVED) {
            tab = helpTransfer(tab, f);  // Help with resize
        } else {
            // Bucket has entries → synchronized on head node only
            synchronized (f) {
                // Traverse and insert/update
            }
        }
    }
    addCount(1L, binCount);  // Atomic size update
    return null;
}
```

**Key improvements in Java 8:**
- Lock granularity: Per-bucket (not per-segment)
- Empty bucket: Lock-free CAS operation
- Read operations: Completely lock-free (volatile reads)
- Size tracking: Distributed counters (like LongAdder)
- Cooperative resizing: Multiple threads help with resize

---

### Q12: How does ConcurrentHashMap handle concurrent reads and writes?

**Answer:**

**Reads are NEVER blocked:**
- Node values and next pointers are `volatile`
- Reads use `Unsafe.getObjectVolatile()` for array access
- No locks acquired for get() operation
- Provides happens-before guarantee through volatile semantics

**Writes use fine-grained locking:**
```java
// Case 1: Empty bucket → CAS (lock-free)
if (casTabAt(tab, i, null, newNode))  // Atomic compare-and-swap

// Case 2: Non-empty bucket → synchronized on first node
synchronized (firstNodeInBucket) {
    // Only this specific bucket is locked
    // All other buckets remain accessible
}
```

**Concurrent resize (transfer):**
- Table is divided into chunks
- Multiple threads can help transfer entries
- `ForwardingNode` with hash=MOVED signals ongoing resize
- Threads encountering ForwardingNode help with transfer

---

### Q13: Why doesn't ConcurrentHashMap allow null keys or values?

**Answer:**

**Ambiguity problem:**
```java
ConcurrentHashMap<String, String> map = new ConcurrentHashMap<>();

// If null values were allowed:
String value = map.get("key");
// value is null - but WHY?
// Option A: key exists with null value
// Option B: key doesn't exist

// In HashMap, you can disambiguate:
if (map.containsKey("key")) { ... }

// But in ConcurrentHashMap, between get() and containsKey(),
// another thread might have modified the map!
// This makes it impossible to safely distinguish null-value from absent-key
```

**Doug Lea's reasoning:** In a concurrent map, null introduces unavoidable ambiguity that cannot be resolved without external synchronization, defeating the purpose.

---

### Q14: What is the difference between ConcurrentHashMap's size() and mappingCount()?

**Answer:**

```java
// size() - returns int (can overflow for maps with > Integer.MAX_VALUE entries)
public int size() {
    long n = sumCount();
    return ((n < 0L) ? 0 : (n > Integer.MAX_VALUE) ? Integer.MAX_VALUE : (int)n);
}

// mappingCount() - returns long (Java 8+, preferred)
public long mappingCount() {
    long n = sumCount();
    return (n < 0L) ? 0L : n;
}
```

**Note:** Both return an **estimate** - the map may be concurrently modified during counting. The count is distributed across multiple cells (like LongAdder) for scalability.

---

### Q15: Explain ConcurrentHashMap's compute(), merge(), and putIfAbsent()

**Answer:**

```java
ConcurrentHashMap<String, Integer> map = new ConcurrentHashMap<>();

// putIfAbsent - atomic "put if not exists"
map.putIfAbsent("counter", 0);  // Only inserts if key absent

// computeIfAbsent - atomic "get or compute"
map.computeIfAbsent("list", k -> new ArrayList<>());
// Creates value lazily, only if key absent. ATOMIC!

// computeIfPresent - atomic "update if exists"
map.computeIfPresent("counter", (k, v) -> v + 1);

// compute - atomic "create or update"
map.compute("counter", (k, v) -> v == null ? 1 : v + 1);

// merge - atomic "insert or merge"
map.merge("counter", 1, Integer::sum);
// If absent: put("counter", 1)
// If present: put("counter", oldValue + 1)
```

**Critical:** These operations are ATOMIC within ConcurrentHashMap. The remapping function is executed while holding the bucket lock. However, the function should be short and not modify other map entries (can cause deadlock).

---

### Q16: What is the concurrency level in ConcurrentHashMap?

**Answer:**

**Java 7:** `concurrencyLevel` parameter in constructor determined number of Segments (default 16). This meant max 16 concurrent writers.

**Java 8+:** The `concurrencyLevel` constructor parameter is **only a sizing hint**. It no longer limits concurrency since locking is per-bucket. With millions of buckets, you can have millions of concurrent writers (different buckets).

```java
// Java 8: concurrencyLevel is just a hint for initial sizing
new ConcurrentHashMap<>(initialCapacity, loadFactor, concurrencyLevel);
// concurrencyLevel only affects initial table size estimation
```

---

## 3. Java Collections Framework

### Q17: Explain the Collections hierarchy in Java.

**Answer:**

```
Iterable<E>
└── Collection<E>
    ├── List<E> (ordered, duplicates allowed)
    │   ├── ArrayList (dynamic array, O(1) random access)
    │   ├── LinkedList (doubly-linked list, O(1) insert/delete)
    │   ├── Vector (synchronized ArrayList, legacy)
    │   │   └── Stack (LIFO, legacy)
    │   └── CopyOnWriteArrayList (thread-safe, snapshot reads)
    │
    ├── Set<E> (no duplicates)
    │   ├── HashSet (HashMap-backed, O(1) operations)
    │   ├── LinkedHashSet (insertion-ordered HashSet)
    │   ├── TreeSet (Red-Black tree, sorted, O(log n))
    │   ├── EnumSet (bit-vector for enums, fastest Set)
    │   └── CopyOnWriteArraySet (thread-safe)
    │
    └── Queue<E>
        ├── PriorityQueue (binary heap, O(log n) insert/remove)
        ├── ArrayDeque (resizable array deque, faster than Stack/LinkedList)
        ├── LinkedList (also implements Deque)
        └── BlockingQueue<E>
            ├── ArrayBlockingQueue (bounded, array-backed)
            ├── LinkedBlockingQueue (optionally bounded)
            ├── PriorityBlockingQueue (unbounded, sorted)
            ├── SynchronousQueue (zero-capacity, handoff)
            ├── DelayQueue (delayed elements)
            └── LinkedTransferQueue (transfer semantics)

Map<K,V> (NOT part of Collection interface)
├── HashMap (hash table, O(1) operations)
├── LinkedHashMap (insertion/access-ordered HashMap)
├── TreeMap (Red-Black tree, sorted keys, O(log n))
├── WeakHashMap (weak reference keys, GC-friendly)
├── IdentityHashMap (reference equality, not equals())
├── EnumMap (array-backed for enum keys, fastest Map)
├── ConcurrentHashMap (thread-safe, high concurrency)
└── ConcurrentSkipListMap (thread-safe, sorted, O(log n))
```

---

### Q18: ArrayList vs LinkedList - When to use which?

**Answer:**

| Operation | ArrayList | LinkedList |
|-----------|-----------|------------|
| get(index) | O(1) | O(n) |
| add(end) | O(1) amortized | O(1) |
| add(index) | O(n) - shift elements | O(1) if at iterator position |
| remove(index) | O(n) - shift elements | O(1) if at iterator position |
| Memory per element | 4 bytes (reference) | 24 bytes (prev + next + data + object header) |
| Cache locality | Excellent (contiguous memory) | Poor (scattered memory) |
| Iterator remove | O(n) | O(1) |

**Use ArrayList when:** Random access needed, mostly append operations, memory efficiency matters, cache performance critical (99% of cases).

**Use LinkedList when:** Frequent insertion/deletion at both ends (use as Deque), never need random access, implementing LRU cache (with HashMap).

**Real-world:** ArrayList wins in almost all practical scenarios due to CPU cache effects. LinkedList's theoretical O(1) insert advantage is negated by cache misses and pointer chasing.

---

### Q19: How does ArrayList grow dynamically?

**Answer:**

```java
// Internal array
transient Object[] elementData;

// When array is full:
private void grow(int minCapacity) {
    int oldCapacity = elementData.length;
    int newCapacity = oldCapacity + (oldCapacity >> 1);  // 1.5x growth
    // >> 1 means divide by 2, so new = old + old/2 = 1.5 * old
    elementData = Arrays.copyOf(elementData, newCapacity);
}
```

**Growth strategy:** 50% increase each time (1.5x)
- Initial capacity: 10 (or 0 with empty constructor, grows to 10 on first add)
- Growth: 10 → 15 → 22 → 33 → 49 → ...

**Performance tip:** If you know the size, use `new ArrayList<>(expectedSize)` to avoid resizing.

---

### Q20: What is the difference between fail-fast and fail-safe iterators?

**Answer:**

**Fail-Fast (ArrayList, HashMap, HashSet):**
```java
List<String> list = new ArrayList<>(Arrays.asList("a", "b", "c"));
Iterator<String> it = list.iterator();
list.add("d");  // Structural modification
it.next();       // Throws ConcurrentModificationException!
```
- Uses `modCount` field - incremented on structural changes
- Iterator checks modCount on each operation
- Immediate failure on concurrent modification
- Not guaranteed (best-effort) - don't rely on it for correctness

**Fail-Safe (ConcurrentHashMap, CopyOnWriteArrayList):**
```java
CopyOnWriteArrayList<String> list = new CopyOnWriteArrayList<>(Arrays.asList("a", "b", "c"));
Iterator<String> it = list.iterator();
list.add("d");  // Creates new internal array
it.next();       // Works fine! Iterates over snapshot
```
- Works on a copy/snapshot of the collection
- Never throws ConcurrentModificationException
- May not reflect latest modifications
- Higher memory overhead

**Weakly Consistent (ConcurrentHashMap):**
- Reflects some (but not necessarily all) modifications since iterator creation
- Never throws ConcurrentModificationException
- Guaranteed to traverse elements as they existed upon construction
- May reflect modifications after construction (but not guaranteed)

---

### Q21: TreeMap vs HashMap vs LinkedHashMap?

**Answer:**

| Feature | HashMap | LinkedHashMap | TreeMap |
|---------|---------|---------------|---------|
| Ordering | No order | Insertion order (or access order) | Sorted (natural/comparator) |
| Null keys | 1 allowed | 1 allowed | Not allowed (compareTo throws NPE) |
| get/put | O(1) | O(1) | O(log n) |
| Backing structure | Array + List/Tree | Array + List/Tree + Doubly-Linked List | Red-Black Tree |
| Memory | Lowest | Medium (extra prev/next pointers) | Highest (tree node overhead) |
| Use case | General purpose | LRU cache, ordered iteration | Range queries, sorted data |

**LinkedHashMap for LRU Cache:**
```java
LinkedHashMap<Integer, String> lru = new LinkedHashMap<>(16, 0.75f, true) {
    // accessOrder=true → most recently accessed moves to end
    @Override
    protected boolean removeEldestEntry(Map.Entry<Integer, String> eldest) {
        return size() > MAX_CAPACITY;  // Remove oldest when full
    }
};
```

---

### Q22: How does PriorityQueue work internally?

**Answer:**

```java
// Backed by a binary heap (array representation)
transient Object[] queue;

// Parent of node at index i: (i - 1) >>> 1
// Left child of node at index i: 2*i + 1
// Right child of node at index i: 2*i + 2

// Min-heap property: parent <= children (for natural ordering)
```

**Operations:**
- `offer()/add()`: O(log n) - add at end, sift up
- `poll()/remove()`: O(log n) - remove root, move last to root, sift down
- `peek()`: O(1) - return root
- `remove(Object)`: O(n) - linear search + O(log n) sift

**Note:** PriorityQueue is NOT thread-safe. Use `PriorityBlockingQueue` for concurrent access.

---

### Q23: What is EnumSet and why is it the fastest Set implementation?

**Answer:**

```java
enum Day { MON, TUE, WED, THU, FRI, SAT, SUN }

EnumSet<Day> weekend = EnumSet.of(Day.SAT, Day.SUN);
EnumSet<Day> weekdays = EnumSet.complementOf(weekend);
EnumSet<Day> all = EnumSet.allOf(Day.class);
```

**Why fastest:**
- Internally uses **bit vectors** (long or long[])
- Each enum constant corresponds to a bit position
- Operations are bitwise (AND, OR, XOR) → O(1) for add, remove, contains
- For enums with ≤64 constants: uses a single `long` (RegularEnumSet)
- For enums with >64 constants: uses `long[]` (JumboEnumSet)
- Extremely compact memory: 64 elements fit in 8 bytes!

---

### Q24: Difference between Comparable and Comparator?

**Answer:**

```java
// Comparable - natural ordering, class implements it
class Employee implements Comparable<Employee> {
    int id;
    String name;
    
    @Override
    public int compareTo(Employee other) {
        return Integer.compare(this.id, other.id);  // Single natural order
    }
}

// Comparator - external, multiple strategies
Comparator<Employee> byName = Comparator.comparing(Employee::getName);
Comparator<Employee> bySalaryDesc = Comparator.comparing(Employee::getSalary).reversed();
Comparator<Employee> complex = Comparator.comparing(Employee::getDept)
                                          .thenComparing(Employee::getName)
                                          .thenComparingInt(Employee::getId);
```

| Aspect | Comparable | Comparator |
|--------|-----------|------------|
| Package | java.lang | java.util |
| Method | compareTo(T o) | compare(T o1, T o2) |
| Modifies class | Yes | No (external) |
| Multiple orders | No (one natural order) | Yes (many comparators) |
| Null handling | Must handle carefully | Comparator.nullsFirst/Last |

---

### Q25: What is the difference between Iterator and ListIterator?

**Answer:**

| Feature | Iterator | ListIterator |
|---------|----------|--------------|
| Direction | Forward only | Bidirectional (next/previous) |
| Applicable to | Any Collection | Only List |
| Add elements | No | Yes (add()) |
| Modify elements | No | Yes (set()) |
| Get index | No | Yes (nextIndex/previousIndex) |

```java
ListIterator<String> lit = list.listIterator(list.size()); // Start at end
while (lit.hasPrevious()) {
    String s = lit.previous();  // Reverse iteration
    if (s.equals("old")) {
        lit.set("new");  // Replace current element
    }
}
```

---

### Q26: How does HashSet work internally?

**Answer:**

```java
// HashSet is backed by a HashMap!
private transient HashMap<E, Object> map;
private static final Object PRESENT = new Object();  // Dummy value

public boolean add(E e) {
    return map.put(e, PRESENT) == null;  // Key = element, Value = dummy
}

public boolean contains(Object o) {
    return map.containsKey(o);
}

public boolean remove(Object o) {
    return map.remove(o) == PRESENT;
}
```

- Uses HashMap's key uniqueness property to enforce Set semantics
- All HashSet elements are stored as keys in internal HashMap
- The value is always the same dummy PRESENT object
- Performance characteristics same as HashMap: O(1) add/remove/contains

---


## 4. Java 8+ Features

### Q27: What are the major features introduced in Java 8?

**Answer:**

1. **Lambda Expressions** - Anonymous functions
2. **Functional Interfaces** - Single abstract method interfaces
3. **Stream API** - Declarative data processing
4. **Optional** - Null safety wrapper
5. **Default Methods** - Interface methods with body
6. **Method References** - Shorthand for lambdas
7. **CompletableFuture** - Async programming
8. **Date/Time API** - java.time package (immutable, thread-safe)
9. **Nashorn JavaScript Engine** - JS runtime in JVM
10. **Type Annotations** - Annotations on any type use
11. **Repeating Annotations** - Same annotation multiple times
12. **Stream parallel processing** - Fork/Join based parallelism

---

### Q28: Explain Lambda Expressions and Functional Interfaces in depth.

**Answer:**

**Lambda Expression** = Anonymous function that can be passed as an argument.

```java
// Syntax: (parameters) -> expression  OR  (parameters) -> { statements }

// Before Java 8:
Runnable r = new Runnable() {
    @Override
    public void run() {
        System.out.println("Hello");
    }
};

// Java 8 Lambda:
Runnable r = () -> System.out.println("Hello");

// With parameters:
Comparator<String> comp = (a, b) -> a.length() - b.length();

// Multi-line:
Function<String, Integer> parser = s -> {
    s = s.trim();
    return Integer.parseInt(s);
};
```

**Functional Interface** = Interface with exactly ONE abstract method (SAM - Single Abstract Method).

```java
@FunctionalInterface  // Compiler enforces single abstract method
interface Transformer<T, R> {
    R transform(T input);
    
    // Allowed: default methods
    default Transformer<T, R> andThen(Transformer<R, R> after) {
        return t -> after.transform(this.transform(t));
    }
    
    // Allowed: static methods
    static <T> Transformer<T, T> identity() {
        return t -> t;
    }
    
    // Allowed: java.lang.Object methods
    boolean equals(Object o);
}
```

**Built-in Functional Interfaces (java.util.function):**

| Interface | Method | Input → Output | Example |
|-----------|--------|----------------|---------|
| `Function<T,R>` | apply(T) | T → R | `String::length` |
| `Predicate<T>` | test(T) | T → boolean | `s -> s.isEmpty()` |
| `Consumer<T>` | accept(T) | T → void | `System.out::println` |
| `Supplier<T>` | get() | () → T | `ArrayList::new` |
| `UnaryOperator<T>` | apply(T) | T → T | `s -> s.toUpperCase()` |
| `BinaryOperator<T>` | apply(T,T) | (T,T) → T | `Integer::sum` |
| `BiFunction<T,U,R>` | apply(T,U) | (T,U) → R | `String::concat` |
| `BiPredicate<T,U>` | test(T,U) | (T,U) → boolean | `String::startsWith` |
| `BiConsumer<T,U>` | accept(T,U) | (T,U) → void | `Map::put` |

**Variable Capture:**
```java
int x = 10;  // Effectively final (cannot be reassigned)
Runnable r = () -> System.out.println(x);  // Captures x
// x = 20;  // COMPILE ERROR: x must be effectively final

// WHY? Lambda may execute in a different thread, after the method returns
// The captured value is COPIED into the lambda, not referenced
// Mutability would create race conditions
```

---

### Q29: Explain Stream API in depth with intermediate and terminal operations.

**Answer:**

**Stream** = A sequence of elements supporting sequential and parallel aggregate operations. Streams are NOT data structures - they don't store data.

**Characteristics:**
- **Lazy evaluation** - Intermediate operations are not executed until a terminal operation is invoked
- **Single use** - A stream can only be consumed once
- **Non-interfering** - Should not modify the source
- **Stateless preferred** - Stateless operations parallelize better

**Stream Pipeline:**
```
Source → Intermediate Operations (0 or more) → Terminal Operation (exactly 1)
```

**Intermediate Operations (return Stream, lazy):**
```java
List<Employee> employees = getEmployees();

employees.stream()
    .filter(e -> e.getSalary() > 50000)       // Predicate<T> → keeps matching
    .map(Employee::getName)                     // Function<T,R> → transforms
    .flatMap(name -> Stream.of(name.split(" "))) // Flattens nested streams
    .distinct()                                  // Removes duplicates (uses equals)
    .sorted()                                    // Natural order
    .sorted(Comparator.reverseOrder())           // Custom order
    .peek(System.out::println)                   // Debug/logging (Consumer)
    .limit(10)                                   // Take first N
    .skip(5)                                     // Skip first N
    ...
```

**Terminal Operations (produce result, trigger execution):**
```java
// Collect to collection
List<String> names = stream.collect(Collectors.toList());
Set<String> unique = stream.collect(Collectors.toSet());
Map<Integer, List<Employee>> byDept = stream.collect(Collectors.groupingBy(Employee::getDeptId));

// Reduce
Optional<Integer> sum = numbers.stream().reduce(Integer::sum);
int sum2 = numbers.stream().reduce(0, Integer::sum);  // With identity

// Find
Optional<Employee> any = stream.findAny();   // Non-deterministic in parallel
Optional<Employee> first = stream.findFirst(); // Deterministic

// Match
boolean allRich = stream.allMatch(e -> e.getSalary() > 100000);
boolean anyRich = stream.anyMatch(e -> e.getSalary() > 100000);
boolean noneRich = stream.noneMatch(e -> e.getSalary() > 100000);

// Count, min, max
long count = stream.count();
Optional<Employee> richest = stream.max(Comparator.comparing(Employee::getSalary));

// forEach (terminal! not intermediate)
stream.forEach(System.out::println);

// toArray
Employee[] array = stream.toArray(Employee[]::new);
```

**Advanced Collectors:**
```java
// Grouping
Map<Department, List<Employee>> byDept = employees.stream()
    .collect(Collectors.groupingBy(Employee::getDept));

// Grouping with downstream collector
Map<Department, Double> avgSalaryByDept = employees.stream()
    .collect(Collectors.groupingBy(
        Employee::getDept,
        Collectors.averagingDouble(Employee::getSalary)
    ));

// Partitioning (special case of grouping with boolean key)
Map<Boolean, List<Employee>> partition = employees.stream()
    .collect(Collectors.partitioningBy(e -> e.getSalary() > 50000));

// Joining
String names = employees.stream()
    .map(Employee::getName)
    .collect(Collectors.joining(", ", "[", "]"));  // [Alice, Bob, Charlie]

// Statistics
IntSummaryStatistics stats = employees.stream()
    .collect(Collectors.summarizingInt(Employee::getAge));
// stats.getMax(), stats.getMin(), stats.getAverage(), stats.getSum(), stats.getCount()

// Custom collector
Map<Boolean, List<Employee>> custom = employees.stream()
    .collect(Collectors.collectingAndThen(
        Collectors.toList(),
        Collections::unmodifiableList
    ));
```

---

### Q30: How does parallel stream work? When to use and when to avoid?

**Answer:**

**How it works:**
- Uses **ForkJoinPool.commonPool()** (shared across the JVM)
- Default parallelism = number of CPU cores - 1
- Splits stream source using **Spliterator**
- Each chunk processed independently, results merged

```java
// Create parallel stream
list.parallelStream()
list.stream().parallel()

// Custom pool (avoid common pool contention):
ForkJoinPool customPool = new ForkJoinPool(4);
List<String> result = customPool.submit(() ->
    list.parallelStream()
        .filter(s -> s.length() > 5)
        .collect(Collectors.toList())
).get();
```

**When to USE parallel streams:**
- Large dataset (> 10,000 elements typically)
- CPU-intensive operations (not I/O bound)
- Stateless, non-interfering operations
- Source splits well (ArrayList, arrays, IntRange)
- No shared mutable state
- Operations are independent

**When to AVOID parallel streams:**
- Small datasets (parallelism overhead > benefit)
- I/O operations (threads will block, pool exhaustion)
- Operations with side effects
- Order-dependent operations (findFirst, limit)
- Poor splittable sources (LinkedList, Stream.iterate)
- Shared mutable state (need synchronization)
- Already inside a parallel context

**Sources and their parallel efficiency:**
| Source | Splittability | Notes |
|--------|--------------|-------|
| ArrayList | Excellent | Splits by index |
| IntStream.range() | Excellent | Known size, even splits |
| Arrays | Excellent | Splits by index |
| HashSet | Good | Splits by buckets |
| TreeSet | Good | Splits by subtree |
| LinkedList | Terrible | Must traverse to split |
| Stream.iterate() | Terrible | Cannot predict split points |
| BufferedReader.lines() | Poor | Cannot split efficiently |

---

### Q31: What is Optional and how to use it properly?

**Answer:**

**Optional** = A container that may or may not contain a non-null value. Designed to be a return type, not a field type.

```java
// Creating Optional
Optional<String> empty = Optional.empty();
Optional<String> of = Optional.of("value");        // NPE if null!
Optional<String> nullable = Optional.ofNullable(possiblyNull);  // Safe

// WRONG ways to use Optional:
// 1. Don't use as method parameter
void process(Optional<String> name) { }  // BAD - use overloading or @Nullable

// 2. Don't use as field
class User {
    Optional<Address> address;  // BAD - not serializable, wastes memory
}

// 3. Don't use isPresent() + get() like null check
if (optional.isPresent()) {      // BAD - no better than null check
    return optional.get();
}

// RIGHT ways to use Optional:
// 1. orElse - default value
String name = optional.orElse("default");

// 2. orElseGet - lazy default (computed only if empty)
String name = optional.orElseGet(() -> expensiveComputation());

// 3. orElseThrow - throw if empty
String name = optional.orElseThrow(() -> new NotFoundException("Not found"));
String name = optional.orElseThrow();  // Java 10+, throws NoSuchElementException

// 4. map - transform value
Optional<Integer> length = optional.map(String::length);

// 5. flatMap - when mapper returns Optional
Optional<String> city = user.flatMap(User::getAddress)
                            .flatMap(Address::getCity);

// 6. filter - conditional
Optional<String> longName = optional.filter(s -> s.length() > 5);

// 7. ifPresent - side effect
optional.ifPresent(System.out::println);

// 8. ifPresentOrElse (Java 9+)
optional.ifPresentOrElse(
    value -> process(value),
    () -> handleAbsence()
);

// 9. or (Java 9+) - alternative Optional
Optional<String> result = optional.or(() -> getBackupOptional());

// 10. stream (Java 9+) - convert to stream
Stream<String> stream = optional.stream();  // 0 or 1 element stream
```

---

### Q32: What are Method References and their types?

**Answer:**

Method references are shorthand for lambdas that just call an existing method.

```java
// Type 1: Static method reference
// Lambda: (s) -> Integer.parseInt(s)
Function<String, Integer> parser = Integer::parseInt;

// Type 2: Instance method of a particular object
// Lambda: (s) -> System.out.println(s)
Consumer<String> printer = System.out::println;

// Type 3: Instance method of an arbitrary object of a particular type
// Lambda: (s) -> s.toUpperCase()
Function<String, String> upper = String::toUpperCase;
// Lambda: (s1, s2) -> s1.compareTo(s2)
Comparator<String> comp = String::compareTo;

// Type 4: Constructor reference
// Lambda: () -> new ArrayList<>()
Supplier<List<String>> listFactory = ArrayList::new;
// Lambda: (s) -> new StringBuilder(s)
Function<String, StringBuilder> sbFactory = StringBuilder::new;
// Array constructor: (size) -> new String[size]
Function<Integer, String[]> arrayFactory = String[]::new;
```

---

### Q33: Explain Default Methods in interfaces. Why were they added?

**Answer:**

**Why:** To evolve interfaces without breaking existing implementations. When `Stream` was added to `Collection`, every existing Collection implementation would need updating. Default methods solved this.

```java
public interface Collection<E> {
    // New in Java 8 - existing implementations inherit this
    default Stream<E> stream() {
        return StreamSupport.stream(spliterator(), false);
    }
    
    default Stream<E> parallelStream() {
        return StreamSupport.stream(spliterator(), true);
    }
}
```

**Diamond Problem Resolution:**
```java
interface A {
    default void hello() { System.out.println("A"); }
}

interface B {
    default void hello() { System.out.println("B"); }
}

// Class MUST override to resolve ambiguity
class C implements A, B {
    @Override
    public void hello() {
        A.super.hello();  // Explicitly choose A's implementation
    }
}
```

**Resolution Rules:**
1. Class always wins over interface
2. More specific interface wins (sub-interface over super-interface)
3. If ambiguous → compile error, must override explicitly

---

### Q34: What is the new Date/Time API in Java 8?

**Answer:**

Problems with old API (java.util.Date, Calendar):
- Mutable (not thread-safe)
- Poor design (months 0-indexed, years from 1900)
- No timezone support in Date
- DateFormat not thread-safe

**New API (java.time):**
```java
// Immutable & thread-safe
LocalDate date = LocalDate.of(2024, Month.MARCH, 15);
LocalTime time = LocalTime.of(14, 30, 45);
LocalDateTime dateTime = LocalDateTime.of(date, time);
ZonedDateTime zoned = ZonedDateTime.of(dateTime, ZoneId.of("America/New_York"));
Instant instant = Instant.now();  // Machine timestamp (UTC)

// Duration (time-based) vs Period (date-based)
Duration duration = Duration.between(time1, time2);  // Hours, minutes, seconds
Period period = Period.between(date1, date2);  // Years, months, days

// Formatting
DateTimeFormatter formatter = DateTimeFormatter.ofPattern("dd-MM-yyyy HH:mm");
String formatted = dateTime.format(formatter);
LocalDateTime parsed = LocalDateTime.parse("15-03-2024 14:30", formatter);

// Operations (immutable - returns new instance)
LocalDate tomorrow = today.plusDays(1);
LocalDate lastMonth = today.minusMonths(1);
LocalDate firstDayOfMonth = today.with(TemporalAdjusters.firstDayOfMonth());
```

---

### Q35: What features were added in Java 9, 10, 11, 17, and 21?

**Answer:**

**Java 9:**
- Module System (JPMS - Project Jigsaw)
- JShell (REPL)
- Collection factory methods: `List.of()`, `Set.of()`, `Map.of()`
- Stream: `takeWhile()`, `dropWhile()`, `ofNullable()`
- Optional: `ifPresentOrElse()`, `or()`, `stream()`
- Private methods in interfaces
- Reactive Streams (Flow API)

**Java 10:**
- `var` keyword (local variable type inference)
- `List.copyOf()`, `Set.copyOf()`, `Map.copyOf()`
- `Collectors.toUnmodifiableList()`
- Application Class-Data Sharing

**Java 11 (LTS):**
- `String` methods: `isBlank()`, `lines()`, `strip()`, `repeat()`
- `Files.readString()`, `Files.writeString()`
- `Optional.isEmpty()`
- HTTP Client API (standard)
- Single-file source code launch: `java HelloWorld.java`
- `var` in lambda parameters

**Java 17 (LTS):**
- Sealed Classes (`sealed`, `permits`)
- Pattern Matching for `instanceof`
- Records
- Text Blocks (multi-line strings)
- Switch Expressions (yield)
- Helpful NullPointerExceptions

**Java 21 (LTS):**
- Virtual Threads (Project Loom)
- Structured Concurrency (Preview)
- Scoped Values (Preview)
- Record Patterns
- Pattern Matching for Switch
- Sequenced Collections
- String Templates (Preview)

```java
// Java 17 examples:
// Sealed classes
sealed interface Shape permits Circle, Rectangle, Triangle { }
record Circle(double radius) implements Shape { }
record Rectangle(double w, double h) implements Shape { }
final class Triangle implements Shape { double base, height; }

// Pattern matching instanceof
if (obj instanceof String s && s.length() > 5) {
    System.out.println(s.toUpperCase());
}

// Java 21: Virtual Threads
try (var executor = Executors.newVirtualThreadPerTaskExecutor()) {
    IntStream.range(0, 10_000).forEach(i ->
        executor.submit(() -> {
            Thread.sleep(Duration.ofSeconds(1));
            return i;
        })
    );
}
```

---

## 5. Garbage Collection

### Q36: How does Garbage Collection work in Java?

**Answer:**

**Concept:** Automatic memory management that identifies and reclaims objects no longer reachable from any GC root.

**GC Roots (starting points for reachability analysis):**
1. Local variables on thread stacks
2. Active threads
3. Static fields of loaded classes
4. JNI references
5. Synchronized monitors

**Object Lifecycle:**
```
Allocation → Reachable → Unreachable → Finalized → Collected
                                ↓
                        (eligible for GC)
```

**Generational Hypothesis:** Most objects die young. This drives the heap layout:

```
JVM Heap Memory:
┌─────────────────────────────────────────────────────────────────┐
│                          HEAP                                     │
├──────────────────────┬──────────────────────────────────────────┤
│    Young Generation   │           Old Generation (Tenured)        │
├───────┬──────────────┤                                            │
│ Eden  │  Survivor    │                                            │
│       │ (S0 | S1)    │                                            │
│ (new  │ (objects     │  (long-lived objects promoted from Young)  │
│objects│  that        │                                            │
│created│  survived    │                                            │
│ here) │  minor GC)   │                                            │
└───────┴──────────────┴──────────────────────────────────────────┘

Non-Heap:
┌───────────────────────────────────────┐
│ Metaspace (class metadata, Java 8+)   │
│ (replaced PermGen from Java 7)        │
└───────────────────────────────────────┘
```

**Minor GC (Young Generation):**
1. New objects allocated in Eden
2. When Eden fills → Minor GC triggered
3. Reachable objects copied to Survivor space (S0 or S1)
4. Unreachable objects discarded (Eden cleared)
5. Objects surviving multiple GCs promoted to Old Gen
6. **Stop-the-world** but very fast (most objects are dead)

**Major GC / Full GC (Old Generation):**
1. Triggered when Old Gen fills up
2. Much slower (more objects, more to scan)
3. **Stop-the-world** pause can be significant
4. Different algorithms: Mark-Sweep, Mark-Compact, etc.

---

### Q37: Explain different GC algorithms and collectors.

**Answer:**

**Mark-Sweep:**
1. Mark: Traverse from GC roots, mark all reachable objects
2. Sweep: Scan heap, free unmarked objects
3. Problem: Memory fragmentation

**Mark-Sweep-Compact:**
1. Mark: Same as above
2. Sweep: Free unmarked objects
3. Compact: Move surviving objects together (defragment)
4. Problem: Longer pause (compaction takes time)

**Copying:**
1. Divide memory into two halves
2. Allocate in one half
3. When full: copy live objects to other half
4. Clear first half entirely
5. Used in Young Generation (Eden → Survivor)

**GC Collectors:**

| Collector | Gen | Algorithm | Pause | Throughput | Use Case |
|-----------|-----|-----------|-------|------------|----------|
| Serial | Both | Copy(Young) + Mark-Compact(Old) | High (STW) | Low | Small apps, single CPU |
| Parallel (Throughput) | Both | Parallel Copy + Parallel Mark-Compact | Medium | High | Batch processing |
| CMS | Old | Concurrent Mark-Sweep | Low | Medium | Low-latency (deprecated Java 9) |
| G1 | Both | Region-based, incremental | Low-Medium | Good | Default since Java 9, balanced |
| ZGC | Both | Colored pointers, load barriers | Ultra-low (<10ms) | Good | Large heaps, low latency |
| Shenandoah | Both | Brooks pointers, concurrent compact | Ultra-low | Good | Low latency alternative |

---

### Q38: How does G1 (Garbage-First) Collector work?

**Answer:**

**Key Concept:** Divides heap into equal-sized **regions** (1MB-32MB each), not contiguous generations.

```
┌────┬────┬────┬────┬────┬────┬────┬────┐
│ E  │ E  │ S  │ O  │ O  │ H  │ O  │Free│
├────┼────┼────┼────┼────┼────┼────┼────┤
│Free│ O  │ O  │ E  │Free│ O  │ E  │Free│
├────┼────┼────┼────┼────┼────┼────┼────┤
│ S  │Free│ O  │Free│ O  │Free│ O  │Free│
└────┴────┴────┴────┴────┴────┴────┴────┘
E = Eden, S = Survivor, O = Old, H = Humongous, Free = Unassigned
```

**Phases:**
1. **Young GC:** Collect Eden + Survivor regions (STW, parallel)
2. **Concurrent Marking:** Identify live objects in Old regions (mostly concurrent)
3. **Mixed GC:** Collect Young + some Old regions (those with most garbage first → "Garbage-First")
4. **Full GC (fallback):** If concurrent marking can't keep up

**Key Features:**
- **Predictable pause times:** `-XX:MaxGCPauseMillis=200` (target, not guarantee)
- **Garbage-First:** Prioritizes regions with most garbage for best efficiency
- **Humongous objects:** Objects > 50% of region size stored in contiguous humongous regions
- **Remembered Sets (RSet):** Track cross-region references (avoids full heap scan)
- **SATB (Snapshot-At-The-Beginning):** Concurrent marking algorithm

**Tuning:**
```bash
-XX:+UseG1GC                    # Enable G1 (default Java 9+)
-XX:MaxGCPauseMillis=200        # Target pause time
-XX:G1HeapRegionSize=4m         # Region size
-XX:InitiatingHeapOccupancyPercent=45  # Start concurrent marking
-XX:G1ReservePercent=10         # Reserve for promotion
```

---

### Q39: How does ZGC work and when to use it?

**Answer:**

**ZGC** = Ultra-low latency GC. Pause times < 10ms regardless of heap size (tested up to 16TB).

**Key Innovations:**
1. **Colored Pointers:** Uses unused bits in 64-bit pointers to store GC metadata
   ```
   64-bit pointer:
   [unused bits][color bits: marked0|marked1|remapped|finalizable][42-bit address]
   ```
2. **Load Barriers:** Code injected at every pointer load to handle concurrent relocation
3. **Concurrent relocation:** Moves objects while application runs

**Phases (almost entirely concurrent):**
1. Pause: Mark Start (scan GC roots - microseconds)
2. Concurrent: Mark/Remap (trace object graph)
3. Pause: Mark End (handle reference processing - microseconds)
4. Concurrent: Relocate (move objects, update references)

**When to use:**
- Large heaps (multi-GB to TB)
- Strict latency requirements (< 10ms pauses)
- Java 15+ (production-ready)
- Trade: Slightly lower throughput for much lower latency

```bash
-XX:+UseZGC
-XX:+ZGenerational   # Java 21+: Generational ZGC (better throughput)
-Xmx16g
```

---

### Q40: What are the different types of references in Java?

**Answer:**

```java
// 1. Strong Reference (default)
Object obj = new Object();  // Never GC'd while reference exists

// 2. Soft Reference - collected only when memory is low
SoftReference<byte[]> cache = new SoftReference<>(new byte[1024*1024]);
byte[] data = cache.get();  // May return null if GC'd
// Use case: Memory-sensitive caches

// 3. Weak Reference - collected at next GC cycle
WeakReference<Object> weak = new WeakReference<>(new Object());
Object obj = weak.get();  // May return null anytime after GC
// Use case: WeakHashMap, canonicalized mappings, listener registrations

// 4. Phantom Reference - enqueued after finalization, before memory reclaim
PhantomReference<Object> phantom = new PhantomReference<>(obj, referenceQueue);
phantom.get();  // ALWAYS returns null
// Use case: Cleanup actions (replacement for finalize()), native memory tracking
// Cleaner API (Java 9+) uses phantom references internally
```

**Reference Queue:**
```java
ReferenceQueue<Object> queue = new ReferenceQueue<>();
WeakReference<Object> ref = new WeakReference<>(obj, queue);

obj = null;  // Remove strong reference
System.gc(); // Request GC

// After GC, ref is enqueued in queue
Reference<?> polled = queue.poll();  // Returns ref if object was collected
```

**WeakHashMap use case:**
```java
// Keys are weak references → entries removed when key is GC'd
WeakHashMap<Object, String> map = new WeakHashMap<>();
Object key = new Object();
map.put(key, "value");
key = null;  // Remove strong reference to key
System.gc(); // Key collected → entry removed from map
```

---

### Q41: What are GC tuning parameters and best practices?

**Answer:**

```bash
# Heap sizing
-Xms4g            # Initial heap size
-Xmx4g            # Maximum heap size (set equal to Xms to avoid resize)
-XX:NewRatio=2    # Old/Young ratio (Old = 2x Young)
-XX:SurvivorRatio=8  # Eden/Survivor ratio (Eden = 8x each Survivor)

# GC selection
-XX:+UseG1GC              # G1 (default Java 9+)
-XX:+UseZGC               # ZGC (Java 15+)
-XX:+UseShenandoahGC      # Shenandoah
-XX:+UseParallelGC        # Throughput collector

# G1 tuning
-XX:MaxGCPauseMillis=200  # Target max pause
-XX:G1HeapRegionSize=4m   # Region size (1-32MB, power of 2)
-XX:InitiatingHeapOccupancyPercent=45  # Trigger concurrent cycle

# GC logging (Java 9+)
-Xlog:gc*:file=gc.log:time,uptime,level,tags:filecount=5,filesize=10M

# Metaspace
-XX:MetaspaceSize=256m
-XX:MaxMetaspaceSize=512m

# Direct memory
-XX:MaxDirectMemorySize=1g
```

**Best Practices:**
1. Set -Xms = -Xmx (avoid heap resizing)
2. Monitor GC logs before tuning
3. Aim for: Minor GC < 50ms, Major GC < 200ms
4. Young Gen should be 25-50% of heap
5. Avoid `System.gc()` calls (-XX:+DisableExplicitGC)
6. Use G1 as default, ZGC for low-latency
7. Profile before tuning - premature optimization is evil

---

### Q42: What is the difference between Minor GC, Major GC, and Full GC?

**Answer:**

| Type | Scope | Trigger | Pause | Frequency |
|------|-------|---------|-------|-----------|
| Minor GC | Young Gen only | Eden full | Short (10-100ms) | Frequent |
| Major GC | Old Gen only | Old Gen filling | Long (100ms-seconds) | Less frequent |
| Full GC | Entire heap + Metaspace | Promotion failure, System.gc(), Metaspace full | Longest | Rare (ideally never) |

**Full GC Triggers:**
1. Old Gen cannot accommodate promoted objects
2. Concurrent marking can't keep up (G1 fallback)
3. `System.gc()` called (unless disabled)
4. Metaspace exhausted
5. Heap dump requested

---

## 6. Memory Management & Debugging

### Q43: How is JVM memory structured?

**Answer:**

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           JVM MEMORY                                      │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  ┌─────────────────────────────────────────────────┐                     │
│  │              HEAP (shared across threads)         │                     │
│  │  ┌─────────────┐  ┌────────────────────────┐    │                     │
│  │  │ Young Gen    │  │    Old Gen (Tenured)    │    │                     │
│  │  │┌────┐┌─┐┌─┐│  │                          │    │                     │
│  │  ││Eden││S0││S1││  │  Long-lived objects      │    │                     │
│  │  │└────┘└──┘└──┘│  │                          │    │                     │
│  │  └──────────────┘  └────────────────────────┘    │                     │
│  └─────────────────────────────────────────────────┘                     │
│                                                                           │
│  ┌─────────────────────────────────────────────────┐                     │
│  │           NON-HEAP / OFF-HEAP                     │                     │
│  │  ┌──────────┐ ┌───────────┐ ┌───────────────┐   │                     │
│  │  │Metaspace │ │Code Cache │ │Direct Memory  │   │                     │
│  │  │(classes, │ │(JIT       │ │(NIO buffers,  │   │                     │
│  │  │ methods) │ │ compiled) │ │ off-heap)     │   │                     │
│  │  └──────────┘ └───────────┘ └───────────────┘   │                     │
│  └─────────────────────────────────────────────────┘                     │
│                                                                           │
│  ┌─────────────────────────────────────────────────┐                     │
│  │        PER-THREAD MEMORY                          │                     │
│  │  ┌──────┐ ┌────────────┐ ┌──────────────────┐   │                     │
│  │  │Stack │ │PC Register │ │Native Method     │   │                     │
│  │  │(frames│ │(current    │ │Stack             │   │                     │
│  │  │locals│ │ instruction│ │                   │   │                     │
│  │  │operand│ │ address)   │ │                   │   │                     │
│  │  │stack)│ │            │ │                   │   │                     │
│  │  └──────┘ └────────────┘ └──────────────────┘   │                     │
│  └─────────────────────────────────────────────────┘                     │
│                                                                           │
└─────────────────────────────────────────────────────────────────────────┘
```

**Per Area Details:**

| Area | Content | Thread Safety | Error |
|------|---------|--------------|-------|
| Heap | Objects, arrays | Shared | OutOfMemoryError: Java heap space |
| Metaspace | Class metadata, method bytecode | Shared | OutOfMemoryError: Metaspace |
| Stack | Frames (locals, operand stack, return addr) | Per-thread | StackOverflowError |
| Code Cache | JIT compiled native code | Shared | Performance degradation |
| Direct Memory | NIO ByteBuffers, memory-mapped files | Shared | OutOfMemoryError: Direct buffer memory |

---

### Q44: What is a Memory Leak in Java and how to detect it?

**Answer:**

**Memory Leak in Java** = Objects that are no longer needed but are still referenced, preventing GC from collecting them.

**Common Causes:**

```java
// 1. Static collections growing unbounded
class Cache {
    private static final Map<String, Object> cache = new HashMap<>();
    // Never cleared! Grows forever
    public static void add(String key, Object value) {
        cache.put(key, value);  // LEAK: entries never removed
    }
}

// 2. Unclosed resources
void processFile(String path) {
    InputStream is = new FileInputStream(path);
    // If exception occurs before close() → resource leak
    // Solution: try-with-resources
}

// 3. Inner class holding reference to outer class
class Outer {
    byte[] largeData = new byte[10_000_000];
    
    class Inner {  // Non-static inner class holds reference to Outer.this
        void process() { }
    }
    
    Inner createInner() {
        return new Inner();  // Inner keeps Outer alive!
    }
    // Solution: Make Inner static, or pass only needed data
}

// 4. Listeners/Callbacks not deregistered
button.addActionListener(event -> handleClick());
// If button outlives the listener owner, leak occurs
// Solution: Use WeakReference or explicitly remove listeners

// 5. ThreadLocal not cleaned up
ThreadLocal<byte[]> buffer = ThreadLocal.withInitial(() -> new byte[1024*1024]);
// In thread pools, threads are reused → ThreadLocal values persist
// Solution: Always call threadLocal.remove() in finally block

// 6. String.intern() abuse
for (String s : millionsOfStrings) {
    s.intern();  // Adds to String pool (never collected until class unload)
}

// 7. Custom ClassLoader leaks
// Loaded classes hold reference to ClassLoader
// ClassLoader holds reference to all loaded classes
// Any static in loaded class → entire ClassLoader tree retained
```

**Detection Tools:**

```bash
# 1. Heap Dump Analysis
jmap -dump:format=b,file=heap.hprof <pid>
# Or trigger on OOM:
-XX:+HeapDumpOnOutOfMemoryError -XX:HeapDumpPath=/path/to/dump

# 2. Monitor live objects
jmap -histo:live <pid> | head -30

# 3. GC logging analysis
-Xlog:gc*:file=gc.log:time

# 4. VisualVM / JConsole (live monitoring)
jvisualvm

# 5. Eclipse MAT (Memory Analyzer Tool) for heap dump analysis
# - Leak Suspects Report
# - Dominator Tree
# - Histogram
# - Path to GC Roots

# 6. JFR (Java Flight Recorder)
-XX:+FlightRecorder -XX:StartFlightRecording=duration=60s,filename=recording.jfr
```

**Memory Leak Detection Pattern:**
1. Monitor heap usage over time
2. If heap grows steadily after Full GC → leak likely
3. Take heap dumps at different times
4. Compare histograms (what's growing?)
5. Analyze dominator tree (what's retaining objects?)
6. Find shortest path to GC root (what's the reference chain?)

---

### Q45: How to analyze a heap dump?

**Answer:**

**Step 1: Generate heap dump**
```bash
# On running JVM
jmap -dump:format=b,file=heap.hprof $(pgrep -f MyApp)

# On OOM (add to JVM args)
-XX:+HeapDumpOnOutOfMemoryError
-XX:HeapDumpPath=/var/log/heap-dumps/

# Using jcmd (preferred over jmap)
jcmd <pid> GC.heap_dump /path/to/heap.hprof
```

**Step 2: Open in Eclipse MAT or VisualVM**

**Key Analysis Views:**

1. **Histogram:** All classes sorted by instance count / retained size
   ```
   Class Name                    | Instances | Shallow Size | Retained Size
   byte[]                        | 1,234,567 | 500 MB       | 500 MB
   java.lang.String              | 987,654   | 23 MB        | 523 MB
   com.myapp.CacheEntry          | 500,000   | 12 MB        | 450 MB  ← suspicious!
   ```

2. **Dominator Tree:** Shows which objects retain the most memory
   ```
   com.myapp.GlobalCache (retains 450 MB)
   └── HashMap (retains 445 MB)
       └── 500,000 × CacheEntry (each retains ~900 bytes)
   ```

3. **Leak Suspects:** Automated analysis of likely leaks

4. **Path to GC Roots:**
   ```
   CacheEntry@0x12345
   ← HashMap$Node.value
   ← HashMap.table[42]
   ← GlobalCache.cacheMap (static field)
   ← Class: com.myapp.GlobalCache (GC Root: System Class)
   ```

5. **OQL (Object Query Language):**
   ```sql
   SELECT * FROM com.myapp.CacheEntry WHERE retainedSize > 10000
   SELECT toString(s) FROM java.lang.String s WHERE s.value.length > 1000
   ```

---

### Q46: What is the difference between Shallow Size and Retained Size?

**Answer:**

```
Object A (100 bytes) → Object B (200 bytes) → Object C (300 bytes)
                     → Object D (400 bytes)

Shallow Size of A = 100 bytes (just object A itself)
Retained Size of A = 100 + 200 + 300 + 400 = 1000 bytes
    (everything that would be GC'd if A is collected,
     assuming B, C, D are ONLY reachable through A)

If C is also referenced by another live object E:
Retained Size of A = 100 + 200 + 400 = 700 bytes
    (C won't be GC'd because E still holds it)
```

**Shallow Size:** Memory consumed by the object itself (header + fields)
**Retained Size:** Memory that would be freed if this object is garbage collected (includes all objects exclusively reachable from it)

---

### Q47: How to detect and fix memory leaks in production?

**Answer:**

**Detection Strategy:**

```bash
# 1. Monitor heap usage trend
jstat -gcutil <pid> 1000  # Every 1 second
# Watch: Old Gen (O) column - should stabilize after Full GC
# If O keeps growing after Full GC → leak!

# 2. Monitor GC frequency and duration
jstat -gc <pid> 1000
# Watch: FGC (Full GC count) and FGCT (Full GC time)
# Increasing frequency = heap pressure

# 3. JMX monitoring (programmatic)
MemoryMXBean mem = ManagementFactory.getMemoryMXBean();
MemoryUsage heap = mem.getHeapMemoryUsage();
long used = heap.getUsed();
long max = heap.getMax();
double pct = (double) used / max * 100;

# 4. Enable GC logging and analyze
-Xlog:gc*:file=gc.log:time,uptime:filecount=5,filesize=50m
# Use GCViewer or GCEasy.io to visualize
```

**Common Fixes:**

```java
// Fix 1: Use WeakHashMap for caches
Map<Key, Value> cache = new WeakHashMap<>();  // Entries collected when key is unreachable

// Fix 2: Bounded caches with eviction
LoadingCache<Key, Value> cache = CacheBuilder.newBuilder()
    .maximumSize(1000)
    .expireAfterWrite(10, TimeUnit.MINUTES)
    .build(loader);

// Fix 3: Try-with-resources for all resources
try (Connection conn = dataSource.getConnection();
     PreparedStatement ps = conn.prepareStatement(sql);
     ResultSet rs = ps.executeQuery()) {
    // Process results
}  // All auto-closed, even on exception

// Fix 4: ThreadLocal cleanup
try {
    threadLocal.set(value);
    // ... use value
} finally {
    threadLocal.remove();  // ALWAYS in finally!
}

// Fix 5: Static inner class instead of non-static
class Outer {
    private static class Inner {  // Does NOT hold Outer reference
        // ...
    }
}

// Fix 6: Listener deregistration
@Override
public void onDestroy() {
    eventBus.unregister(this);
    observable.removeObserver(observer);
}
```

---

### Q48: What tools are available for JVM memory analysis?

**Answer:**

| Tool | Type | Use Case |
|------|------|----------|
| **jstat** | CLI | Real-time GC statistics |
| **jmap** | CLI | Heap dump, histogram |
| **jcmd** | CLI | All-in-one diagnostic (preferred) |
| **jinfo** | CLI | View/modify JVM flags |
| **Eclipse MAT** | GUI | Heap dump analysis, leak detection |
| **VisualVM** | GUI | Live monitoring, profiling |
| **JFR** | Built-in | Low-overhead flight recording |
| **JMC** | GUI | Analyze JFR recordings |
| **async-profiler** | Native | CPU/heap profiling, flame graphs |
| **Arthas** | CLI | Online Java diagnostics |
| **YourKit** | Commercial | Full profiler |
| **JProfiler** | Commercial | Full profiler |

```bash
# jcmd - modern replacement for jmap, jstack, jinfo
jcmd <pid> VM.flags                  # Show all JVM flags
jcmd <pid> GC.heap_dump heap.hprof   # Heap dump
jcmd <pid> Thread.print              # Thread dump
jcmd <pid> GC.run                    # Request GC
jcmd <pid> VM.native_memory summary  # Native memory tracking
jcmd <pid> JFR.start duration=60s filename=rec.jfr  # Start recording

# Native Memory Tracking
-XX:NativeMemoryTracking=summary  # or 'detail'
jcmd <pid> VM.native_memory summary
```

---

## 7. CPU Debugging & Performance

### Q49: How to diagnose high CPU usage in a Java application?

**Answer:**

**Step-by-step approach:**

```bash
# Step 1: Find the Java process consuming CPU
top -c  # or: ps aux --sort=-%cpu | head

# Step 2: Find which THREADS are consuming CPU
top -H -p <java_pid>  # Shows individual threads
# Note the thread IDs (LWP/TID) with high CPU

# Step 3: Convert thread ID to hex (for matching with thread dump)
printf "%x\n" <thread_id>  # e.g., 12345 → 0x3039

# Step 4: Take thread dump
jstack <pid> > threaddump.txt
# Or: jcmd <pid> Thread.print > threaddump.txt
# Or: kill -3 <pid>  (prints to stdout/stderr)

# Step 5: Find the hot thread in the dump
grep -A 30 "nid=0x3039" threaddump.txt
# This shows you exactly what code that thread is executing

# Step 6: Take multiple dumps (3-5, 5-10 seconds apart)
for i in 1 2 3 4 5; do
    jstack <pid> > "threaddump_$i.txt"
    sleep 5
done
# Compare dumps - threads consistently in same location = bottleneck
```

**Common CPU issues:**

```java
// 1. Infinite loop
while (true) {
    if (condition) break;  // condition never becomes true
}

// 2. Busy-waiting (spinning)
while (!flag) { }  // Burns CPU! Use wait/notify or BlockingQueue

// 3. Excessive GC (GC threads consuming CPU)
// Check: jstat -gcutil <pid> 1000
// If GC time > 50% → tune GC or fix memory leak

// 4. Regex catastrophic backtracking
Pattern.compile("(a+)+b").matcher("aaaaaaaaaaaaaaaaac");  // Exponential

// 5. Uncontrolled thread creation
while (true) {
    new Thread(() -> process()).start();  // Thousands of threads!
}

// 6. Lock contention (threads spinning for locks)
// Visible in thread dump as: BLOCKED (on object monitor)
```

---

### Q50: How to create and analyze thread dumps?

**Answer:**

**Creating Thread Dumps:**
```bash
# Method 1: jstack (most common)
jstack -l <pid> > threaddump.txt  # -l includes locks

# Method 2: jcmd (preferred, newer)
jcmd <pid> Thread.print > threaddump.txt

# Method 3: kill signal (Unix)
kill -3 <pid>  # Prints to process stdout/stderr

# Method 4: Programmatic
ThreadMXBean bean = ManagementFactory.getThreadMXBean();
ThreadInfo[] infos = bean.dumpAllThreads(true, true);
```

**Reading Thread Dumps:**
```
"http-nio-8080-exec-1" #15 daemon prio=5 os_prio=0 tid=0x00007f... nid=0x3039 
    java.lang.Thread.State: BLOCKED (on object monitor)
        at com.myapp.Service.process(Service.java:42)
        - waiting to lock <0x00000000c0035678> (a java.util.HashMap)
        at com.myapp.Controller.handle(Controller.java:25)
        ...
```

**Key Thread States:**
| State | Meaning | Action |
|-------|---------|--------|
| RUNNABLE | Executing or ready | Check if doing useful work |
| BLOCKED | Waiting for monitor lock | Lock contention issue |
| WAITING | Waiting indefinitely (wait/join/park) | Check what it's waiting for |
| TIMED_WAITING | Waiting with timeout (sleep/wait/park) | Usually OK |
| NEW | Created but not started | Unusual in dumps |
| TERMINATED | Finished execution | Unusual in dumps |

**Deadlock Detection:**
```
Found one Java-level deadlock:
=============================
"Thread-1":
  waiting to lock monitor 0x00007f... (object 0x...a, a java.lang.Object),
  which is held by "Thread-2"
"Thread-2":
  waiting to lock monitor 0x00007f... (object 0x...b, a java.lang.Object),
  which is held by "Thread-1"
```

---

### Q51: What is JIT compilation and how does it affect performance?

**Answer:**

**JIT (Just-In-Time) Compiler** converts hot bytecode to native machine code at runtime.

**Compilation Tiers (Tiered Compilation - default since Java 8):**
```
Level 0: Interpreter (no optimization, immediate execution)
Level 1: C1 with full optimization (simple methods)
Level 2: C1 with limited profiling
Level 3: C1 with full profiling (collects data for C2)
Level 4: C2 with aggressive optimization (peak performance)
```

**How it works:**
1. Method starts interpreted
2. JVM counts invocations (invocation counter) and loop iterations (backedge counter)
3. When threshold reached (default ~10,000 for C2), method is compiled
4. Compiled code replaces interpreted code (on-stack replacement for loops)

**C2 Optimizations:**
- **Inlining:** Replace method call with method body
- **Escape Analysis:** Allocate objects on stack if they don't escape method
- **Loop unrolling:** Reduce loop overhead
- **Dead code elimination:** Remove unreachable code
- **Null check elimination:** Remove redundant null checks
- **Bounds check elimination:** Remove array bounds checks when provably safe
- **Lock elision:** Remove locks on non-escaped objects
- **Vectorization:** SIMD instructions for array operations

```bash
# View JIT compilation
-XX:+PrintCompilation
-XX:+UnlockDiagnosticVMOptions -XX:+PrintInlining
-XX:+PrintAssembly  # Requires hsdis plugin

# Tune JIT
-XX:CompileThreshold=10000     # Invocations before compile
-XX:-TieredCompilation         # Disable tiered (jump to C2)
-XX:+AggressiveOpts            # Aggressive optimizations
```

---

### Q52: How to profile a Java application for performance?

**Answer:**

**1. Java Flight Recorder (JFR) - Zero/Low overhead:**
```bash
# Start recording
jcmd <pid> JFR.start duration=60s filename=recording.jfr

# Or via JVM args:
-XX:+FlightRecorder
-XX:StartFlightRecording=duration=300s,filename=app.jfr

# Analyze with JDK Mission Control (JMC)
jmc  # Opens GUI to analyze .jfr files
```

**2. async-profiler - CPU/Allocation profiling:**
```bash
# CPU profiling (generates flame graph)
./profiler.sh -d 30 -f flamegraph.html <pid>

# Allocation profiling
./profiler.sh -e alloc -d 30 -f alloc.html <pid>

# Lock profiling
./profiler.sh -e lock -d 30 -f locks.html <pid>
```

**3. jstat - GC monitoring:**
```bash
jstat -gcutil <pid> 1000 100  # Every 1s, 100 samples
# S0  S1  E    O    M    CCS  YGC  YGCT  FGC  FGCT  GCT
# 0   50  75   45   98   96   150  1.2   5    0.8   2.0
```

**4. Arthas - Online diagnostics:**
```bash
# Trace method execution time
trace com.myapp.Service processOrder

# Watch method parameters and return value
watch com.myapp.Service processOrder "{params, returnObj}" -x 3

# Profile CPU (flame graph)
profiler start
profiler stop --format html
```

---


## 8. Multithreading & Concurrency (Advanced) - COMPLETE DEEP DIVE

### Q53: Explain the Java Memory Model (JMM).

**Answer:**

The **Java Memory Model** defines how threads interact through memory and what behaviors are allowed.

```
Thread 1 CPU Cache          Thread 2 CPU Cache
┌───────────────┐           ┌───────────────┐
│ Local copy of │           │ Local copy of │
│ shared vars   │           │ shared vars   │
└───────┬───────┘           └───────┬───────┘
        │ flush/load                │ flush/load
        ▼                           ▼
┌─────────────────────────────────────────────┐
│              MAIN MEMORY                      │
│  (shared variables: heap, static fields)     │
└─────────────────────────────────────────────┘
```

**Key Concepts:**

1. **Visibility:** Changes by one thread may NOT be visible to others without synchronization
2. **Atomicity:** Operations that appear indivisible
3. **Ordering:** Instructions may be reordered by compiler/CPU unless restricted

**Happens-Before Relationships (guarantees visibility + ordering):**
- Program order within a thread
- Monitor lock: unlock → subsequent lock
- Volatile write → subsequent volatile read
- Thread.start() → anything in started thread
- Thread termination → Thread.join() returns
- Interrupt → detection of interrupt
- Constructor completion → finalizer start

```java
// BROKEN - no happens-before between threads
class Broken {
    boolean ready = false;
    int value = 0;
    
    void writer() {
        value = 42;       // May be reordered!
        ready = true;     // Other thread may see ready=true but value=0
    }
    
    void reader() {
        if (ready) {
            System.out.println(value);  // May print 0!
        }
    }
}

// FIXED with volatile
class Fixed {
    volatile boolean ready = false;
    int value = 0;
    
    void writer() {
        value = 42;       // Happens-before ready=true (program order)
        ready = true;     // Volatile write flushes all previous writes
    }
    
    void reader() {
        if (ready) {          // Volatile read loads all preceding writes
            System.out.println(value);  // Guaranteed to print 42
        }
    }
}
```

---

### Q54: What is volatile and when to use it?

**Answer:**

`volatile` guarantees:
1. **Visibility:** Writes are immediately visible to all threads
2. **Ordering:** Prevents reordering across volatile access (memory barrier)
3. **NOT Atomicity:** `volatile int count; count++` is NOT atomic (read-modify-write)

```java
// Good use: flags, status indicators
volatile boolean shutdownRequested = false;

void shutdown() { shutdownRequested = true; }

void run() {
    while (!shutdownRequested) {  // Always reads from main memory
        doWork();
    }
}

// Good use: Double-Checked Locking (Singleton)
class Singleton {
    private static volatile Singleton instance;  // MUST be volatile!
    
    static Singleton getInstance() {
        if (instance == null) {                   // First check (no lock)
            synchronized (Singleton.class) {
                if (instance == null) {           // Second check (with lock)
                    instance = new Singleton();   // Without volatile, partially 
                                                  // constructed object visible!
                }
            }
        }
        return instance;
    }
}
// WHY volatile needed: "instance = new Singleton()" is:
// 1. Allocate memory
// 2. Call constructor
// 3. Assign reference to instance
// Without volatile, CPU may reorder to 1→3→2
// Another thread sees non-null instance but uninitialized object!

// BAD use: compound operations
volatile int count = 0;
count++;  // NOT ATOMIC! (read count, add 1, write count)
// Two threads: both read 5, both write 6 → lost update!
// Solution: AtomicInteger or synchronized
```

---

### Q55: Explain synchronized - method level vs block level.

**Answer:**

```java
class Counter {
    private int count = 0;
    
    // Method-level: locks 'this' object
    synchronized void increment() {
        count++;  // Only one thread at a time
    }
    
    // Block-level: locks specified object (finer granularity)
    private final Object lock = new Object();
    void incrementBlock() {
        synchronized (lock) {
            count++;
        }
    }
    
    // Static synchronized: locks Class object
    private static int globalCount = 0;
    static synchronized void globalIncrement() {
        globalCount++;  // Locks Counter.class
    }
}
```

**How synchronized works internally:**

Every Java object has a **monitor** (intrinsic lock):
```
Object Header (Mark Word - 64 bits):
┌──────────────────────────────────────────────────────────┐
│ Biased Thread ID (54) │ Epoch(2) │ Age(4) │ Bias(1) │ Lock(2) │
├──────────────────────────────────────────────────────────┤
│ Lock State:                                               │
│   01 = Unlocked / Biased                                  │
│   00 = Lightweight locked (stack pointer)                 │
│   10 = Heavyweight locked (monitor pointer)               │
│   11 = Marked for GC                                      │
└──────────────────────────────────────────────────────────┘
```

**Lock Escalation (optimization progression):**
1. **Biased Locking** (Java 6-14, removed in 15): Lock biased to first thread, no atomic operations if same thread re-enters
2. **Lightweight Lock (Thin Lock):** CAS operation on mark word (spin-based)
3. **Heavyweight Lock (Fat Lock):** OS mutex, thread parking (expensive)

```
No contention: Biased Lock (zero-cost for same thread)
        ↓ (another thread tries to acquire)
Light contention: Lightweight Lock (CAS spinning)
        ↓ (spinning too long or too many waiters)
Heavy contention: Heavyweight Lock (OS mutex, context switch)
```

---

### Q56: What is ReentrantLock and how does it differ from synchronized?

**Answer:**

```java
import java.util.concurrent.locks.ReentrantLock;

class BankAccount {
    private final ReentrantLock lock = new ReentrantLock(true);  // fair=true
    private double balance;
    
    void transfer(BankAccount to, double amount) {
        lock.lock();  // Acquire lock
        try {
            if (balance >= amount) {
                balance -= amount;
                to.deposit(amount);
            }
        } finally {
            lock.unlock();  // ALWAYS in finally!
        }
    }
    
    // tryLock - non-blocking attempt
    boolean tryTransfer(BankAccount to, double amount, long timeout) throws InterruptedException {
        if (lock.tryLock(timeout, TimeUnit.MILLISECONDS)) {
            try {
                // ... transfer logic
                return true;
            } finally {
                lock.unlock();
            }
        }
        return false;  // Could not acquire lock in time
    }
    
    // lockInterruptibly - can be interrupted while waiting
    void interruptibleTransfer(BankAccount to, double amount) throws InterruptedException {
        lock.lockInterruptibly();  // Throws InterruptedException if interrupted while waiting
        try {
            // ... transfer logic
        } finally {
            lock.unlock();
        }
    }
}
```

**Comparison:**

| Feature | synchronized | ReentrantLock |
|---------|-------------|---------------|
| Lock/unlock | Automatic (block exit) | Manual (lock/unlock) |
| Try lock | No | Yes (tryLock) |
| Timed lock | No | Yes (tryLock with timeout) |
| Interruptible | No | Yes (lockInterruptibly) |
| Fairness | No (unfair) | Configurable (fair/unfair) |
| Multiple conditions | No (one wait set per monitor) | Yes (multiple Condition objects) |
| Lock across methods | Difficult | Easy (lock in one, unlock in another) |
| Performance | Similar (Java 6+) | Similar (Java 6+) |
| Deadlock detection | No | Can check with tryLock |
| Read-write separation | No | Use ReadWriteLock |

**When to use ReentrantLock over synchronized:**
- Need tryLock (avoid deadlock)
- Need timed lock (bounded wait)
- Need interruptible lock
- Need fair ordering
- Need multiple condition variables
- Need to lock/unlock in different scopes

---

### Q57: Explain ReadWriteLock and StampedLock.

**Answer:**

**ReadWriteLock** - Multiple readers OR single writer:
```java
ReadWriteLock rwLock = new ReentrantReadWriteLock();
Lock readLock = rwLock.readLock();
Lock writeLock = rwLock.writeLock();

// Multiple threads can read simultaneously
void read() {
    readLock.lock();
    try {
        // Read shared data (many readers concurrently)
    } finally {
        readLock.unlock();
    }
}

// Only one writer, blocks all readers
void write() {
    writeLock.lock();
    try {
        // Modify shared data (exclusive access)
    } finally {
        writeLock.unlock();
    }
}
```

**StampedLock** (Java 8+) - Optimistic reads for better throughput:
```java
StampedLock sl = new StampedLock();

// Optimistic read (no locking! just get a stamp)
double distanceFromOrigin() {
    long stamp = sl.tryOptimisticRead();  // Non-blocking!
    double currentX = x, currentY = y;    // Read shared vars
    if (!sl.validate(stamp)) {            // Check if write occurred
        // Write happened during read → fall back to read lock
        stamp = sl.readLock();
        try {
            currentX = x;
            currentY = y;
        } finally {
            sl.unlockRead(stamp);
        }
    }
    return Math.sqrt(currentX * currentX + currentY * currentY);
}

// Write lock
void move(double deltaX, double deltaY) {
    long stamp = sl.writeLock();
    try {
        x += deltaX;
        y += deltaY;
    } finally {
        sl.unlockWrite(stamp);
    }
}

// Lock upgrade: read → write
void conditionalUpdate() {
    long stamp = sl.readLock();
    try {
        while (x == 0.0) {
            long ws = sl.tryConvertToWriteLock(stamp);  // Try upgrade
            if (ws != 0L) {
                stamp = ws;
                x = 1.0;  // Now have write lock
                break;
            } else {
                sl.unlockRead(stamp);
                stamp = sl.writeLock();  // Acquire write lock directly
            }
        }
    } finally {
        sl.unlock(stamp);
    }
}
```

**StampedLock vs ReadWriteLock:**
- StampedLock is NOT reentrant (will deadlock if same thread re-acquires)
- StampedLock optimistic read has ZERO contention (best for read-heavy)
- StampedLock does NOT support Condition variables
- Use ReadWriteLock if you need reentrancy or conditions

---

### Q58: Explain all Atomic classes and CAS (Compare-And-Swap).

**Answer:**

**CAS (Compare-And-Swap)** = Hardware-level atomic instruction:
```
CAS(memory_location, expected_value, new_value)
→ If memory_location == expected_value: set to new_value, return true
→ Else: do nothing, return false (another thread modified it)
```

**Java Atomic Classes (java.util.concurrent.atomic):**

```java
// AtomicInteger / AtomicLong
AtomicInteger counter = new AtomicInteger(0);
counter.incrementAndGet();        // ++counter (atomic)
counter.getAndIncrement();        // counter++ (atomic)
counter.addAndGet(5);             // counter += 5 (atomic)
counter.compareAndSet(10, 20);    // if counter==10, set to 20
counter.updateAndGet(x -> x * 2); // atomic arbitrary update (Java 8+)
counter.accumulateAndGet(5, Integer::sum); // atomic accumulate

// AtomicBoolean
AtomicBoolean flag = new AtomicBoolean(false);
flag.compareAndSet(false, true);  // Atomic flag flip

// AtomicReference<V>
AtomicReference<Node> head = new AtomicReference<>(null);
head.compareAndSet(oldHead, newNode);  // Lock-free linked list

// AtomicStampedReference (solves ABA problem)
AtomicStampedReference<Integer> ref = new AtomicStampedReference<>(100, 0);
int[] stampHolder = new int[1];
Integer val = ref.get(stampHolder);
ref.compareAndSet(val, 200, stampHolder[0], stampHolder[0] + 1);
// Only succeeds if BOTH value and stamp match

// AtomicMarkableReference
AtomicMarkableReference<Node> node = new AtomicMarkableReference<>(n, false);
node.compareAndSet(n, newN, false, true);  // CAS with boolean mark

// AtomicIntegerArray / AtomicLongArray / AtomicReferenceArray
AtomicIntegerArray arr = new AtomicIntegerArray(10);
arr.getAndIncrement(5);  // Atomic increment of element at index 5

// AtomicIntegerFieldUpdater (avoid object overhead)
class Account {
    volatile int balance;  // Must be volatile, non-private, non-static
}
AtomicIntegerFieldUpdater<Account> updater = 
    AtomicIntegerFieldUpdater.newUpdater(Account.class, "balance");
updater.addAndGet(account, 100);  // Atomic update without AtomicInteger object
```

**ABA Problem:**
```
Thread 1: reads A
Thread 2: changes A → B → A
Thread 1: CAS(A, A, C) → succeeds! (but value was changed in between)

// Solution: AtomicStampedReference with version counter
// Every update increments stamp: (A,1) → (B,2) → (A,3)
// CAS checks both value AND stamp
```

**LongAdder & LongAccumulator (Java 8+ - high contention):**
```java
// LongAdder: better than AtomicLong under high contention
LongAdder adder = new LongAdder();
adder.increment();     // Distributed across cells
adder.add(10);
long sum = adder.sum(); // Aggregate all cells (eventual consistency)

// WHY better?
// AtomicLong: single CAS → all threads contend on one variable
// LongAdder: multiple cells → threads distributed, less contention
// Trade-off: sum() is slightly slower (aggregates cells)

// LongAccumulator: generalized version
LongAccumulator max = new LongAccumulator(Long::max, Long.MIN_VALUE);
max.accumulate(42);
long result = max.get();
```

---

### Q59: Explain CountDownLatch with real-world use cases.

**Answer:**

**CountDownLatch** = One-time barrier that allows one or more threads to wait until a set of operations in other threads completes.

```java
// Concept: Initialize with count N
// countDown() decrements by 1
// await() blocks until count reaches 0
// CANNOT be reset (one-time use)

// Use Case 1: Wait for multiple services to initialize
class ApplicationStartup {
    private static final int SERVICE_COUNT = 5;
    private final CountDownLatch latch = new CountDownLatch(SERVICE_COUNT);
    
    void startService(String name) {
        new Thread(() -> {
            try {
                initializeService(name);  // Each service initializes
                System.out.println(name + " ready");
            } finally {
                latch.countDown();  // Signal completion
            }
        }).start();
    }
    
    void awaitAllServices() throws InterruptedException {
        System.out.println("Waiting for all services...");
        latch.await();  // Blocks until count == 0
        // Or: latch.await(30, TimeUnit.SECONDS);  // With timeout
        System.out.println("All services ready! Starting application.");
    }
}

// Use Case 2: Coordinate concurrent test (start all threads at same time)
class ConcurrentTest {
    void testConcurrentAccess() throws InterruptedException {
        int threadCount = 100;
        CountDownLatch startGate = new CountDownLatch(1);  // Start signal
        CountDownLatch endGate = new CountDownLatch(threadCount);  // Completion signal
        
        for (int i = 0; i < threadCount; i++) {
            new Thread(() -> {
                try {
                    startGate.await();  // All threads wait here
                    // Perform concurrent operation
                    doOperation();
                } catch (InterruptedException e) {
                    Thread.currentThread().interrupt();
                } finally {
                    endGate.countDown();
                }
            }).start();
        }
        
        startGate.countDown();  // Release all threads simultaneously!
        endGate.await();        // Wait for all to complete
        // Assert results
    }
}

// Use Case 3: Parallel file processing
void processFiles(List<Path> files) throws InterruptedException {
    CountDownLatch latch = new CountDownLatch(files.size());
    ExecutorService executor = Executors.newFixedThreadPool(10);
    
    for (Path file : files) {
        executor.submit(() -> {
            try {
                processFile(file);
            } finally {
                latch.countDown();
            }
        });
    }
    
    latch.await();  // Wait for all files to be processed
    generateReport();
}
```

---

### Q60: Explain CyclicBarrier vs CountDownLatch.

**Answer:**

**CyclicBarrier** = Reusable barrier where N threads wait for each other at a common point.

```java
// All threads must reach barrier before any can proceed
// CAN be reset and reused (cyclic!)

// Use Case: Multi-phase parallel computation
class ParallelSimulation {
    private final CyclicBarrier barrier;
    private final int[][] matrix;
    
    ParallelSimulation(int threadCount, int[][] matrix) {
        this.matrix = matrix;
        // Optional barrier action: runs when all threads arrive
        this.barrier = new CyclicBarrier(threadCount, () -> {
            System.out.println("Phase complete, merging results...");
            mergeResults();
        });
    }
    
    void workerThread(int startRow, int endRow) {
        try {
            for (int phase = 0; phase < 10; phase++) {
                // Phase 1: Compute
                computeRows(startRow, endRow);
                barrier.await();  // Wait for all workers to finish this phase
                
                // Phase 2: Exchange boundaries
                exchangeBoundaries(startRow, endRow);
                barrier.await();  // Barrier reused!
            }
        } catch (InterruptedException | BrokenBarrierException e) {
            Thread.currentThread().interrupt();
        }
    }
}
```

**Key Differences:**

| Feature | CountDownLatch | CyclicBarrier |
|---------|---------------|---------------|
| Reusable | No (one-time) | Yes (cyclic) |
| Who waits | Thread(s) calling await() | All participating threads |
| Who counts down | Any thread (countDown) | The waiting threads themselves |
| Reset | Cannot reset | Automatically resets when barrier tripped |
| Barrier action | No | Yes (optional Runnable on barrier trip) |
| BrokenBarrier | N/A | Yes (if thread interrupted/timeout) |
| Use case | "Wait for N events" | "N threads synchronize at common point" |
| Count direction | Down to 0 | Up to parties count |

---

### Q61: Explain Semaphore and its use cases.

**Answer:**

**Semaphore** = Controls access to a shared resource with a permit count.

```java
// Binary Semaphore (permit=1) = Mutex
// Counting Semaphore (permit=N) = Resource pool limiter

// Use Case 1: Connection pool limiting
class ConnectionPool {
    private final Semaphore semaphore;
    private final Queue<Connection> pool;
    
    ConnectionPool(int maxConnections) {
        this.semaphore = new Semaphore(maxConnections, true);  // fair=true
        this.pool = new ConcurrentLinkedQueue<>();
        // Initialize pool with connections
        for (int i = 0; i < maxConnections; i++) {
            pool.offer(createConnection());
        }
    }
    
    Connection acquire() throws InterruptedException {
        semaphore.acquire();  // Blocks if no permits available
        return pool.poll();
    }
    
    Connection acquire(long timeout, TimeUnit unit) throws InterruptedException {
        if (semaphore.tryAcquire(timeout, unit)) {
            return pool.poll();
        }
        throw new TimeoutException("Cannot acquire connection");
    }
    
    void release(Connection conn) {
        pool.offer(conn);
        semaphore.release();  // Return permit
    }
}

// Use Case 2: Rate limiting (crude)
class RateLimiter {
    private final Semaphore semaphore;
    
    RateLimiter(int maxConcurrent) {
        this.semaphore = new Semaphore(maxConcurrent);
    }
    
    <T> T execute(Callable<T> task) throws Exception {
        semaphore.acquire();
        try {
            return task.call();
        } finally {
            semaphore.release();
        }
    }
}

// Use Case 3: Producer-Consumer with bounded buffer
class BoundedBuffer<T> {
    private final Semaphore empty;  // Tracks empty slots
    private final Semaphore full;   // Tracks full slots
    private final Queue<T> queue = new LinkedList<>();
    
    BoundedBuffer(int capacity) {
        this.empty = new Semaphore(capacity);  // Initially all slots empty
        this.full = new Semaphore(0);          // Initially no items
    }
    
    void put(T item) throws InterruptedException {
        empty.acquire();  // Wait for empty slot
        synchronized (queue) { queue.offer(item); }
        full.release();   // Signal item available
    }
    
    T take() throws InterruptedException {
        full.acquire();   // Wait for item
        T item;
        synchronized (queue) { item = queue.poll(); }
        empty.release();  // Signal slot freed
        return item;
    }
}
```

---

### Q62: Explain LinkedBlockingQueue in depth.

**Answer:**

**LinkedBlockingQueue** = Thread-safe, optionally bounded, FIFO blocking queue backed by linked nodes.

```java
// Internal structure (simplified):
class LinkedBlockingQueue<E> {
    private final int capacity;            // Max elements (Integer.MAX_VALUE if unbounded)
    private final AtomicInteger count;     // Current size
    
    private final ReentrantLock takeLock;  // Lock for take/poll
    private final Condition notEmpty;      // Signals waiting consumers
    
    private final ReentrantLock putLock;   // Lock for put/offer
    private final Condition notFull;       // Signals waiting producers
    
    // TWO SEPARATE LOCKS! (unlike ArrayBlockingQueue which has ONE lock)
    // This allows put and take to execute CONCURRENTLY!
}
```

**Operations:**

```java
BlockingQueue<Task> queue = new LinkedBlockingQueue<>(1000);  // Bounded

// Blocking operations (wait if necessary)
queue.put(task);       // Blocks if queue is full
Task t = queue.take(); // Blocks if queue is empty

// Timed operations
boolean added = queue.offer(task, 5, TimeUnit.SECONDS);  // Wait up to 5s
Task t = queue.poll(5, TimeUnit.SECONDS);                 // Wait up to 5s

// Non-blocking operations
boolean added = queue.offer(task);  // Returns false if full
Task t = queue.poll();              // Returns null if empty

// Examination (non-removing)
Task t = queue.peek();  // Returns null if empty (does not block!)
int size = queue.size();
int remaining = queue.remainingCapacity();
```

**Why LinkedBlockingQueue uses TWO locks:**
```
// Two-lock design enables higher throughput:
// Producer thread: acquires putLock → adds to tail
// Consumer thread: acquires takeLock → removes from head
// They DON'T contend with each other!

// Signaling between them:
// After put: if (count was 0) signal notEmpty → wake consumer
// After take: if (count was full) signal notFull → wake producer
```

**LinkedBlockingQueue vs ArrayBlockingQueue:**

| Feature | LinkedBlockingQueue | ArrayBlockingQueue |
|---------|--------------------|--------------------|
| Backing store | Linked nodes | Array (circular buffer) |
| Locks | Two (put + take) | One (single lock) |
| Concurrent put/take | Yes (higher throughput) | No (mutual exclusion) |
| Bounded | Optional (default unbounded) | Always bounded |
| Memory | More (node objects per element) | Less (pre-allocated array) |
| GC pressure | Higher (node creation/GC) | Lower (reuses array) |
| Fairness | No | Optional |
| Cache performance | Worse (scattered nodes) | Better (contiguous array) |

**Use Case: Producer-Consumer Pattern:**
```java
class ProducerConsumer {
    private final BlockingQueue<Event> queue = new LinkedBlockingQueue<>(10000);
    
    // Producer
    void produce(Event event) {
        try {
            queue.put(event);  // Blocks if queue full (backpressure!)
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
    }
    
    // Consumer
    void consume() {
        while (!Thread.currentThread().isInterrupted()) {
            try {
                Event event = queue.take();  // Blocks if queue empty
                process(event);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                break;
            }
        }
    }
}
```

---

### Q63: Explain all BlockingQueue implementations and when to use each.

**Answer:**

```java
// 1. ArrayBlockingQueue - Bounded, single lock, fair option
BlockingQueue<Task> abq = new ArrayBlockingQueue<>(100, true);  // fair=true
// Use when: Fixed-size buffer, need fairness, memory-efficient
// Example: Fixed-size thread pool work queue

// 2. LinkedBlockingQueue - Optionally bounded, two locks, higher throughput
BlockingQueue<Task> lbq = new LinkedBlockingQueue<>(1000);
// Use when: High throughput needed, put/take from different threads
// Example: Producer-consumer with high throughput requirement

// 3. PriorityBlockingQueue - Unbounded, priority-ordered
BlockingQueue<Task> pbq = new PriorityBlockingQueue<>(11, comparator);
// Use when: Tasks have priority ordering
// Note: UNBOUNDED - put() never blocks! Only take() blocks if empty
// Example: Task scheduler with priority levels

// 4. SynchronousQueue - Zero capacity, direct handoff
BlockingQueue<Task> sq = new SynchronousQueue<>(true);  // fair=true
// Use when: Direct handoff between producer and consumer
// put() blocks until another thread calls take()
// take() blocks until another thread calls put()
// No buffering! Pure synchronization point
// Example: Executors.newCachedThreadPool() uses this

// 5. DelayQueue - Unbounded, elements available after delay
BlockingQueue<DelayedTask> dq = new DelayQueue<>();
class DelayedTask implements Delayed {
    private final long executeAt;
    
    @Override
    public long getDelay(TimeUnit unit) {
        return unit.convert(executeAt - System.currentTimeMillis(), TimeUnit.MILLISECONDS);
    }
    
    @Override
    public int compareTo(Delayed o) {
        return Long.compare(this.getDelay(TimeUnit.MILLISECONDS), 
                           o.getDelay(TimeUnit.MILLISECONDS));
    }
}
// Use when: Scheduled execution, retry with delay
// Example: Cache expiration, scheduled tasks, retry queues

// 6. LinkedTransferQueue - Unbounded, transfer semantics
LinkedTransferQueue<Task> ltq = new LinkedTransferQueue<>();
ltq.transfer(task);        // Blocks until a consumer takes it (like SynchronousQueue)
ltq.tryTransfer(task);     // Non-blocking attempt to hand off
ltq.tryTransfer(task, 1, TimeUnit.SECONDS);  // Timed transfer
ltq.put(task);             // Non-blocking put (like LinkedBlockingQueue)
// Use when: Need both buffering AND direct handoff options
// Example: Actor-style message passing

// 7. LinkedBlockingDeque - Bounded deque (double-ended)
BlockingDeque<Task> lbd = new LinkedBlockingDeque<>(100);
lbd.putFirst(task);   // Add to front
lbd.putLast(task);    // Add to back
lbd.takeFirst();      // Remove from front
lbd.takeLast();       // Remove from back
// Use when: Work-stealing algorithms, undo functionality
// Example: ForkJoinPool work-stealing queues
```

---

### Q64: Explain ExecutorService and ThreadPool in depth.

**Answer:**

```java
// Thread Pool Architecture:
// ┌─────────────────────────────────────────────┐
// │              ExecutorService                   │
// │  ┌────────────────────────────────────────┐  │
// │  │         Task Queue (BlockingQueue)      │  │
// │  │  [Task1] [Task2] [Task3] [Task4] ...   │  │
// │  └───────────────────┬────────────────────┘  │
// │                      │                        │
// │  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐       │
// │  │Thread│ │Thread│ │Thread│ │Thread│       │
// │  │  1   │ │  2   │ │  3   │ │  4   │       │
// │  └──────┘ └──────┘ └──────┘ └──────┘       │
// │        (Worker Pool - takes from queue)       │
// └─────────────────────────────────────────────┘

// Factory methods:
ExecutorService fixed = Executors.newFixedThreadPool(10);
// Core=10, Max=10, Queue=LinkedBlockingQueue(unbounded)
// Use: Known concurrency level, bounded parallelism

ExecutorService cached = Executors.newCachedThreadPool();
// Core=0, Max=Integer.MAX_VALUE, Queue=SynchronousQueue
// Threads expire after 60s idle
// Use: Many short-lived tasks, burst workloads
// DANGER: Can create unlimited threads!

ExecutorService single = Executors.newSingleThreadExecutor();
// Core=1, Max=1, Queue=LinkedBlockingQueue(unbounded)
// Use: Sequential execution, event loop

ScheduledExecutorService scheduled = Executors.newScheduledThreadPool(4);
// Use: Periodic/delayed tasks

// Java 21: Virtual thread executor
ExecutorService virtual = Executors.newVirtualThreadPerTaskExecutor();
// Use: High-concurrency I/O tasks (millions of threads!)

// CUSTOM ThreadPoolExecutor (recommended for production):
ThreadPoolExecutor executor = new ThreadPoolExecutor(
    10,                              // corePoolSize
    50,                              // maximumPoolSize
    60L, TimeUnit.SECONDS,           // keepAliveTime for excess threads
    new LinkedBlockingQueue<>(1000), // work queue (BOUNDED!)
    new ThreadFactory() {            // custom thread factory
        private final AtomicInteger counter = new AtomicInteger(0);
        @Override
        public Thread newThread(Runnable r) {
            Thread t = new Thread(r, "worker-" + counter.incrementAndGet());
            t.setDaemon(false);
            t.setUncaughtExceptionHandler((thread, ex) -> log.error("Uncaught", ex));
            return t;
        }
    },
    new ThreadPoolExecutor.CallerRunsPolicy()  // Rejection handler
);
```

**Thread Pool Behavior:**
```
Submit task:
├── Core pool not full? → Create new core thread
├── Core pool full, queue not full? → Add to queue
├── Queue full, pool < maxSize? → Create new non-core thread
└── Pool at max AND queue full? → Execute rejection policy
```

**Rejection Policies:**
```java
// AbortPolicy (default): Throws RejectedExecutionException
// CallerRunsPolicy: Executes task in the submitting thread (backpressure!)
// DiscardPolicy: Silently drops the task
// DiscardOldestPolicy: Drops oldest queued task, retries submit
// Custom: implement RejectedExecutionHandler
```

**Proper Shutdown:**
```java
executor.shutdown();  // No new tasks, finish queued tasks
if (!executor.awaitTermination(30, TimeUnit.SECONDS)) {
    executor.shutdownNow();  // Interrupt running tasks
    if (!executor.awaitTermination(10, TimeUnit.SECONDS)) {
        log.error("Pool did not terminate!");
    }
}
```

---

### Q65: Explain Future, CompletableFuture, and CompletionStage.

**Answer:**

**Future** (Java 5) - Basic async result handle:
```java
ExecutorService executor = Executors.newFixedThreadPool(4);

Future<Integer> future = executor.submit(() -> {
    Thread.sleep(2000);
    return 42;
});

// Blocking get
Integer result = future.get();                         // Blocks indefinitely
Integer result = future.get(5, TimeUnit.SECONDS);      // Blocks with timeout

// Check status
boolean done = future.isDone();
boolean cancelled = future.isCancelled();
future.cancel(true);  // true = interrupt if running

// LIMITATIONS OF Future:
// 1. Cannot compose futures (chain operations)
// 2. Cannot combine multiple futures
// 3. No callbacks (must block on get())
// 4. No exception handling pipeline
// 5. Cannot manually complete
```

**CompletableFuture** (Java 8) - Full async programming:
```java
// Creation:
CompletableFuture<String> cf1 = CompletableFuture.supplyAsync(() -> fetchData());
CompletableFuture<Void> cf2 = CompletableFuture.runAsync(() -> doWork());
CompletableFuture<String> cf3 = CompletableFuture.completedFuture("immediate");

// With custom executor:
CompletableFuture<String> cf = CompletableFuture.supplyAsync(
    () -> fetchData(), customExecutor);

// CHAINING (thenApply = map, thenCompose = flatMap):
CompletableFuture<Integer> result = CompletableFuture
    .supplyAsync(() -> "Hello")                    // Async computation
    .thenApply(s -> s + " World")                  // Transform result (sync)
    .thenApply(String::length)                     // Chain another transform
    .thenApplyAsync(len -> len * 2, executor);     // Async transform

// thenCompose (flatMap - avoids CompletableFuture<CompletableFuture<T>>)
CompletableFuture<Order> orderFuture = getUserId()
    .thenCompose(userId -> getOrder(userId))        // Returns CF<Order>, not CF<CF<Order>>
    .thenCompose(order -> enrichOrder(order));

// thenAccept (consume result, return void)
cf.thenAccept(result -> System.out.println(result));

// thenRun (run after completion, ignores result)
cf.thenRun(() -> System.out.println("Done!"));

// COMBINING FUTURES:
// thenCombine - combine two futures when both complete
CompletableFuture<String> combined = priceF.thenCombine(quantityF,
    (price, quantity) -> "Total: " + price * quantity);

// allOf - wait for ALL futures to complete
CompletableFuture<Void> allDone = CompletableFuture.allOf(cf1, cf2, cf3);
allDone.thenRun(() -> {
    String r1 = cf1.join();  // Already complete
    String r2 = cf2.join();
    String r3 = cf3.join();
});

// anyOf - complete when ANY future completes
CompletableFuture<Object> fastest = CompletableFuture.anyOf(cf1, cf2, cf3);

// ERROR HANDLING:
CompletableFuture<String> robust = CompletableFuture
    .supplyAsync(() -> riskyOperation())
    .exceptionally(ex -> "Fallback value")          // Recover from exception
    .handle((result, ex) -> {                        // Handle both success/failure
        if (ex != null) return "Error: " + ex.getMessage();
        return "Success: " + result;
    })
    .whenComplete((result, ex) -> {                  // Side effect, doesn't transform
        if (ex != null) log.error("Failed", ex);
        else log.info("Result: {}", result);
    });

// TIMEOUT (Java 9+):
CompletableFuture<String> withTimeout = cf
    .orTimeout(5, TimeUnit.SECONDS)                  // Exception after timeout
    .completeOnTimeout("default", 5, TimeUnit.SECONDS); // Default after timeout

// MANUAL COMPLETION:
CompletableFuture<String> manual = new CompletableFuture<>();
manual.complete("value");                // Complete normally
manual.completeExceptionally(new RuntimeException("fail"));  // Complete with error
```

**Real-world Example - Parallel API Calls:**
```java
CompletableFuture<UserProfile> profileF = CompletableFuture.supplyAsync(
    () -> userService.getProfile(userId), ioExecutor);
CompletableFuture<List<Order>> ordersF = CompletableFuture.supplyAsync(
    () -> orderService.getOrders(userId), ioExecutor);
CompletableFuture<Recommendations> recsF = CompletableFuture.supplyAsync(
    () -> recService.getRecommendations(userId), ioExecutor);

// Combine all results
CompletableFuture<UserDashboard> dashboard = profileF
    .thenCombine(ordersF, (profile, orders) -> new PartialDashboard(profile, orders))
    .thenCombine(recsF, (partial, recs) -> new UserDashboard(partial, recs))
    .orTimeout(3, TimeUnit.SECONDS)
    .exceptionally(ex -> UserDashboard.defaultDashboard());
```

---

### Q66: Explain ScheduledExecutorService and its scheduling methods.

**Answer:**

```java
ScheduledExecutorService scheduler = Executors.newScheduledThreadPool(4);

// 1. schedule() - Execute once after delay
ScheduledFuture<?> future = scheduler.schedule(
    () -> System.out.println("Executed after 5 seconds"),
    5, TimeUnit.SECONDS
);

// With return value:
ScheduledFuture<String> futureResult = scheduler.schedule(
    () -> fetchData(),
    5, TimeUnit.SECONDS
);
String result = futureResult.get();  // Blocks until execution + completion

// 2. scheduleAtFixedRate() - Fixed rate (period between starts)
ScheduledFuture<?> fixedRate = scheduler.scheduleAtFixedRate(
    () -> pollMetrics(),     // Task
    0,                       // Initial delay
    10, TimeUnit.SECONDS     // Period between START of consecutive executions
);
// Timeline: |--exec--|     |--exec--|     |--exec--|
//           0s       3s    10s      13s   20s      23s
// If execution takes longer than period: next execution starts immediately after

// 3. scheduleWithFixedDelay() - Fixed delay (delay between end and start)
ScheduledFuture<?> fixedDelay = scheduler.scheduleWithFixedDelay(
    () -> cleanupCache(),    // Task
    0,                       // Initial delay
    30, TimeUnit.SECONDS     // Delay between END of one and START of next
);
// Timeline: |--exec--|  (30s delay)  |--exec--|  (30s delay)  |--exec--|
//           0s       3s              33s      36s              66s

// Cancelling:
fixedRate.cancel(false);   // false = let current execution finish
fixedRate.cancel(true);    // true = interrupt if running

// Exception handling:
// If task throws exception, future executions are SILENTLY suppressed!
// Always catch exceptions inside the task:
scheduler.scheduleAtFixedRate(() -> {
    try {
        doWork();
    } catch (Exception e) {
        log.error("Scheduled task failed", e);
        // Don't rethrow! Future executions would stop
    }
}, 0, 10, TimeUnit.SECONDS);
```

**scheduleAtFixedRate vs scheduleWithFixedDelay:**
| Aspect | scheduleAtFixedRate | scheduleWithFixedDelay |
|--------|--------------------|-----------------------|
| Timing reference | Start of execution | End of execution |
| Overlap if slow | Immediate restart | Always has delay gap |
| Use case | Polling at exact intervals | Ensuring gap between executions |
| Clock drift | No (fixed wall-clock rate) | Yes (delay accumulates) |
| Example | Metrics every 10s | Cleanup 30s after last run |

---

### Q67: Explain Phaser and its advantages over CyclicBarrier/CountDownLatch.

**Answer:**

**Phaser** = Flexible synchronization barrier supporting dynamic registration/deregistration and multiple phases.

```java
// Phaser combines features of both CountDownLatch AND CyclicBarrier
// PLUS: dynamic party count, per-phase actions, tiered phasers

Phaser phaser = new Phaser(3);  // 3 initial parties

// Dynamic registration:
phaser.register();      // Add a party (now 4)
phaser.bulkRegister(5); // Add 5 parties

// Deregistration:
phaser.arriveAndDeregister();  // Arrive AND remove self from future phases

// Use Case: Tasks with dynamic participants
class DynamicPhaseTask {
    private final Phaser phaser;
    
    void run() {
        for (int phase = 0; phase < 10; phase++) {
            doPhaseWork(phase);
            
            if (shouldContinue(phase)) {
                phaser.arriveAndAwaitAdvance();  // Wait for others
            } else {
                phaser.arriveAndDeregister();    // Drop out of future phases
                return;
            }
        }
    }
}

// Tiered Phasers (for large party counts - reduce contention):
Phaser root = new Phaser();
Phaser child1 = new Phaser(root, 10);  // 10 parties in child1
Phaser child2 = new Phaser(root, 10);  // 10 parties in child2
// When all children complete, root advances
// Reduces sync overhead for hundreds of parties

// Override termination condition:
Phaser phaser = new Phaser() {
    @Override
    protected boolean onAdvance(int phase, int registeredParties) {
        return phase >= 5 || registeredParties == 0;  // Stop after phase 5
    }
};
```

**Phaser vs CountDownLatch vs CyclicBarrier:**
| Feature | CountDownLatch | CyclicBarrier | Phaser |
|---------|---------------|---------------|--------|
| Reusable | No | Yes | Yes |
| Dynamic parties | No | No | Yes (register/deregister) |
| Multiple phases | No | Yes | Yes |
| Termination | At 0 | Manual | Override onAdvance() |
| Party dropout | No | No (broken barrier) | Yes (arriveAndDeregister) |
| Tiering | No | No | Yes (hierarchical) |

---

### Q68: Explain Exchanger and its use cases.

**Answer:**

**Exchanger** = Synchronization point where two threads exchange objects.

```java
Exchanger<DataBuffer> exchanger = new Exchanger<>();

// Thread 1: Producer (fills buffer, exchanges for empty buffer)
void producer() {
    DataBuffer fullBuffer = new DataBuffer();
    while (true) {
        fillBuffer(fullBuffer);
        fullBuffer = exchanger.exchange(fullBuffer);  // Give full, get empty
    }
}

// Thread 2: Consumer (processes buffer, exchanges for full buffer)
void consumer() {
    DataBuffer emptyBuffer = new DataBuffer();
    while (true) {
        emptyBuffer = exchanger.exchange(emptyBuffer);  // Give empty, get full
        processBuffer(emptyBuffer);
        emptyBuffer.clear();
    }
}

// With timeout:
DataBuffer received = exchanger.exchange(myBuffer, 5, TimeUnit.SECONDS);
// Throws TimeoutException if no other thread arrives
```

**Use Cases:**
- Double-buffering (producer fills one while consumer processes other)
- Genetic algorithms (two threads exchange chromosomes)
- Pipeline stages exchanging data
- Paired thread communication

---

### Q69: Explain ForkJoinPool and work-stealing algorithm.

**Answer:**

**ForkJoinPool** = Thread pool designed for divide-and-conquer parallelism with work-stealing.

```java
// Architecture:
// ┌─────────────────────────────────────────────────────────────┐
// │                     ForkJoinPool                              │
// │                                                               │
// │  Thread-0: [Task-A] [Task-B] ←── own deque (LIFO for self)  │
// │  Thread-1: [Task-C]          ←── own deque                   │
// │  Thread-2: []                ←── empty! STEALS from others   │
// │  Thread-3: [Task-D] [Task-E] ←── own deque                   │
// │                                                               │
// │  Work Stealing: Thread-2 steals Task-E from Thread-3's       │
// │  deque FIFO (takes from opposite end = large chunk)           │
// └─────────────────────────────────────────────────────────────┘
```

**RecursiveTask (returns result):**
```java
class SumTask extends RecursiveTask<Long> {
    private static final int THRESHOLD = 10_000;
    private final long[] array;
    private final int start, end;
    
    SumTask(long[] array, int start, int end) {
        this.array = array;
        this.start = start;
        this.end = end;
    }
    
    @Override
    protected Long compute() {
        int length = end - start;
        if (length <= THRESHOLD) {
            // Base case: compute directly
            long sum = 0;
            for (int i = start; i < end; i++) {
                sum += array[i];
            }
            return sum;
        }
        
        // Recursive case: fork and join
        int mid = start + length / 2;
        SumTask left = new SumTask(array, start, mid);
        SumTask right = new SumTask(array, mid, end);
        
        left.fork();    // Submit to pool (async)
        long rightResult = right.compute();  // Compute in current thread
        long leftResult = left.join();       // Wait for forked result
        
        return leftResult + rightResult;
    }
}

// Usage:
ForkJoinPool pool = ForkJoinPool.commonPool();  // Or new ForkJoinPool(parallelism)
long sum = pool.invoke(new SumTask(array, 0, array.length));
```

**RecursiveAction (no return value):**
```java
class SortTask extends RecursiveAction {
    private static final int THRESHOLD = 1000;
    private final int[] array;
    private final int start, end;
    
    @Override
    protected void compute() {
        if (end - start <= THRESHOLD) {
            Arrays.sort(array, start, end);  // Base case
            return;
        }
        int mid = (start + end) / 2;
        invokeAll(
            new SortTask(array, start, mid),
            new SortTask(array, mid, end)
        );
        merge(array, start, mid, end);
    }
}
```

**Work Stealing Algorithm:**
1. Each thread has its own double-ended queue (deque)
2. Thread pushes/pops own tasks from TOP (LIFO - most recent, smallest)
3. Idle threads steal from BOTTOM of other threads' deques (FIFO - oldest, largest)
4. Stealing large tasks means less stealing needed overall
5. This self-balances load across threads dynamically

---

### Q70: Explain ThreadLocal and InheritableThreadLocal.

**Answer:**

**ThreadLocal** = Per-thread storage. Each thread has its own independent copy.

```java
// Each thread gets its own SimpleDateFormat (not thread-safe)
private static final ThreadLocal<SimpleDateFormat> dateFormat = 
    ThreadLocal.withInitial(() -> new SimpleDateFormat("yyyy-MM-dd"));

String format(Date date) {
    return dateFormat.get().format(date);  // Each thread uses its own instance
}

// Use Case 1: Per-request context in web applications
public class RequestContext {
    private static final ThreadLocal<UserSession> sessionHolder = new ThreadLocal<>();
    
    public static void setSession(UserSession session) {
        sessionHolder.set(session);
    }
    
    public static UserSession getSession() {
        return sessionHolder.get();
    }
    
    public static void clear() {
        sessionHolder.remove();  // CRITICAL: prevent memory leak in thread pools!
    }
}

// In servlet filter:
public void doFilter(request, response, chain) {
    try {
        RequestContext.setSession(extractSession(request));
        chain.doFilter(request, response);
    } finally {
        RequestContext.clear();  // ALWAYS CLEAN UP!
    }
}

// Use Case 2: Transaction context
private static final ThreadLocal<Connection> connectionHolder = new ThreadLocal<>();
```

**InheritableThreadLocal** = Child threads inherit parent's ThreadLocal values.

```java
InheritableThreadLocal<String> itl = new InheritableThreadLocal<>();
itl.set("parent-value");

new Thread(() -> {
    System.out.println(itl.get());  // "parent-value" (inherited from parent)
}).start();

// PROBLEM with thread pools: threads are reused, not child of submitting thread
// InheritableThreadLocal only works when thread is CREATED
// For thread pools, use TransmittableThreadLocal (Alibaba library)
// Or Java 21 Scoped Values:
```

**Java 21: ScopedValue (replacement for ThreadLocal in virtual threads):**
```java
final static ScopedValue<UserSession> SESSION = ScopedValue.newInstance();

// Bind value for a scope
ScopedValue.where(SESSION, userSession).run(() -> {
    // SESSION.get() returns userSession here
    processRequest();  // Any code in this scope can access SESSION
});
// After run() completes, binding is automatically removed - no cleanup needed!
```

**ThreadLocal Memory Leak in Thread Pools:**
```
Thread (long-lived in pool)
└── ThreadLocalMap
    └── Entry[WeakReference<ThreadLocal>, Value]
    
If ThreadLocal variable is GC'd (weak ref), the Key becomes null
BUT the Value is still strongly referenced!
→ Memory leak: value never collected until thread dies (never in pool!)

FIX: Always call threadLocal.remove() when done
```

---

### Q71: Explain the Producer-Consumer pattern with all implementations.

**Answer:**

```java
// Implementation 1: Using BlockingQueue (RECOMMENDED)
class ProducerConsumerBlockingQueue {
    private final BlockingQueue<Integer> queue = new LinkedBlockingQueue<>(100);
    private volatile boolean running = true;
    
    class Producer implements Runnable {
        @Override
        public void run() {
            try {
                int value = 0;
                while (running) {
                    queue.put(value++);  // Blocks if full (backpressure)
                }
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            }
        }
    }
    
    class Consumer implements Runnable {
        @Override
        public void run() {
            try {
                while (running || !queue.isEmpty()) {
                    Integer value = queue.poll(1, TimeUnit.SECONDS);
                    if (value != null) {
                        process(value);
                    }
                }
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            }
        }
    }
}

// Implementation 2: Using wait/notify (low-level, educational)
class ProducerConsumerWaitNotify {
    private final Queue<Integer> queue = new LinkedList<>();
    private final int capacity;
    private final Object lock = new Object();
    
    void produce(int value) throws InterruptedException {
        synchronized (lock) {
            while (queue.size() == capacity) {
                lock.wait();  // Release lock, wait for space
            }
            queue.offer(value);
            lock.notifyAll();  // Wake waiting consumers
        }
    }
    
    int consume() throws InterruptedException {
        synchronized (lock) {
            while (queue.isEmpty()) {
                lock.wait();  // Release lock, wait for items
            }
            int value = queue.poll();
            lock.notifyAll();  // Wake waiting producers
            return value;
        }
    }
}

// Implementation 3: Using Lock and Condition (more flexible)
class ProducerConsumerCondition {
    private final Queue<Integer> queue = new LinkedList<>();
    private final int capacity;
    private final ReentrantLock lock = new ReentrantLock();
    private final Condition notFull = lock.newCondition();
    private final Condition notEmpty = lock.newCondition();
    
    void produce(int value) throws InterruptedException {
        lock.lock();
        try {
            while (queue.size() == capacity) {
                notFull.await();  // Wait specifically for "not full" signal
            }
            queue.offer(value);
            notEmpty.signal();   // Signal specifically to consumers
        } finally {
            lock.unlock();
        }
    }
    
    int consume() throws InterruptedException {
        lock.lock();
        try {
            while (queue.isEmpty()) {
                notEmpty.await();  // Wait specifically for "not empty" signal
            }
            int value = queue.poll();
            notFull.signal();    // Signal specifically to producers
            return value;
        } finally {
            lock.unlock();
        }
    }
}

// Implementation 4: Using Disruptor (LMAX - ultra high performance)
// Ring buffer, no locks, cache-line padding, mechanical sympathy
// Used in: financial exchanges, logging frameworks
```

---

### Q72: What is a Deadlock? How to detect and prevent it?

**Answer:**

**Deadlock** = Two or more threads waiting for each other to release resources, creating a circular wait.

```java
// Classic Deadlock Example:
Object lockA = new Object();
Object lockB = new Object();

// Thread 1:
synchronized (lockA) {          // Holds lockA
    Thread.sleep(100);
    synchronized (lockB) {      // Waits for lockB (held by Thread 2)
        // Never reached!
    }
}

// Thread 2:
synchronized (lockB) {          // Holds lockB
    Thread.sleep(100);
    synchronized (lockA) {      // Waits for lockA (held by Thread 1)
        // Never reached!
    }
}
```

**Four Conditions for Deadlock (ALL must be present):**
1. **Mutual Exclusion:** Resources are exclusive
2. **Hold and Wait:** Thread holds one resource while waiting for another
3. **No Preemption:** Resources cannot be forcibly taken
4. **Circular Wait:** Circular chain of threads waiting for each other

**Detection:**
```bash
# Thread dump shows deadlock:
jstack <pid> | grep -A 5 "deadlock"

# Programmatic:
ThreadMXBean bean = ManagementFactory.getThreadMXBean();
long[] deadlockedThreads = bean.findDeadlockedThreads();
if (deadlockedThreads != null) {
    ThreadInfo[] infos = bean.getThreadInfo(deadlockedThreads, true, true);
    // Log thread info
}
```

**Prevention Strategies:**

```java
// 1. Lock Ordering - Always acquire locks in the same global order
void transfer(Account from, Account to, double amount) {
    Account first = from.getId() < to.getId() ? from : to;
    Account second = from.getId() < to.getId() ? to : from;
    synchronized (first) {
        synchronized (second) {
            // Safe! Always locks lower ID first
        }
    }
}

// 2. Lock Timeout - Use tryLock to break deadlock
boolean transferSafe(Account from, Account to, double amount) {
    while (true) {
        if (from.lock.tryLock(1, TimeUnit.SECONDS)) {
            try {
                if (to.lock.tryLock(1, TimeUnit.SECONDS)) {
                    try {
                        doTransfer(from, to, amount);
                        return true;
                    } finally {
                        to.lock.unlock();
                    }
                }
            } finally {
                from.lock.unlock();
            }
        }
        Thread.sleep(random.nextInt(100));  // Back off and retry
    }
}

// 3. Single Lock - Coarse-grained locking (simpler but less concurrent)
private static final Object GLOBAL_LOCK = new Object();
synchronized (GLOBAL_LOCK) { /* all operations */ }

// 4. Lock-free algorithms - Use Atomic classes / CAS
AtomicReference<State> state = new AtomicReference<>(initialState);
// CAS-based updates never block

// 5. Avoid Nested Locks - Design to acquire only one lock at a time
```

---

### Q73: What is a Livelock vs Starvation?

**Answer:**

**Livelock:** Threads are NOT blocked but make no progress because they keep responding to each other's actions.
```java
// Analogy: Two people in a hallway, both step aside the same way repeatedly
class LivelockExample {
    volatile boolean thread1Moving = true;
    volatile boolean thread2Moving = true;
    
    void thread1() {
        while (thread1Moving) {
            if (thread2Moving) {
                System.out.println("T1: Let T2 go first");
                // Thread.sleep(random);  // FIX: Add random backoff
                continue;
            }
            doWork();
            break;
        }
    }
    
    void thread2() {
        while (thread2Moving) {
            if (thread1Moving) {
                System.out.println("T2: Let T1 go first");
                continue;
            }
            doWork();
            break;
        }
    }
    // Both threads politely yield to each other → no progress!
}
```

**Starvation:** A thread cannot access shared resources because other threads monopolize them.
```java
// Example: Unfair lock + low-priority thread
// Thread with LOW priority never gets CPU time because HIGH priority threads dominate

// Fix: Use fair locks
ReentrantLock fairLock = new ReentrantLock(true);  // FIFO ordering

// Fix: Use timeouts
if (!lock.tryLock(10, TimeUnit.SECONDS)) {
    // Handle starvation - escalate, log, alternative path
}
```

---

### Q74: Explain the volatile vs synchronized vs Atomic performance trade-offs.

**Answer:**

```java
// Performance (best to worst for simple counter):
// 1. No synchronization (unsafe, but fastest)
// 2. ThreadLocal (no sharing, each thread has own)
// 3. AtomicInteger/LongAdder (lock-free CAS)
// 4. volatile (visibility only, NOT atomic for read-modify-write)
// 5. synchronized (mutual exclusion, heaviest)

// Benchmark results (approximate, varies by contention):
// Operation: increment counter 100M times with 8 threads

// LongAdder:           ~0.3s (distributed counters, minimal contention)
// AtomicLong:          ~1.5s (single CAS point, moderate contention)
// synchronized block:  ~3.0s (lock/unlock, context switch under contention)
// ReentrantLock:       ~2.8s (similar to synchronized)

// WHEN TO USE WHAT:
// volatile: flags, status fields (single write, multiple reads, no compound operations)
// AtomicInteger: counters, accumulators (CAS-based, lock-free)
// LongAdder: high-contention counters (distributed cells)
// synchronized: compound operations, multiple variables atomically
// ReentrantLock: when you need tryLock/conditions/fairness
```

---

### Q75: Explain CompletionService and its use cases.

**Answer:**

**CompletionService** = Decouples production of tasks from consumption of their results. Results are available in completion order (not submission order).

```java
ExecutorService executor = Executors.newFixedThreadPool(10);
CompletionService<Result> completionService = 
    new ExecutorCompletionService<>(executor);

// Submit multiple tasks
List<Future<Result>> futures = new ArrayList<>();
for (Request request : requests) {
    futures.add(completionService.submit(() -> process(request)));
}

// Process results AS THEY COMPLETE (not in submission order!)
for (int i = 0; i < requests.size(); i++) {
    Future<Result> completedFuture = completionService.take();  // Blocks for next completed
    Result result = completedFuture.get();  // Already done, won't block
    handleResult(result);
}

// Use Case: First successful result (e.g., query multiple replicas)
Result queryFirstAvailable(List<DataSource> sources) throws Exception {
    CompletionService<Result> cs = new ExecutorCompletionService<>(executor);
    int n = sources.size();
    List<Future<Result>> futures = new ArrayList<>(n);
    
    try {
        for (DataSource source : sources) {
            futures.add(cs.submit(() -> source.query()));
        }
        for (int i = 0; i < n; i++) {
            Future<Result> f = cs.take();
            try {
                return f.get();  // Return first successful result
            } catch (ExecutionException e) {
                // This source failed, try next completed one
            }
        }
        throw new Exception("All sources failed");
    } finally {
        // Cancel remaining tasks
        for (Future<Result> f : futures) f.cancel(true);
    }
}
```

---

### Q76: Explain Virtual Threads (Project Loom) in Java 21.

**Answer:**

**Virtual Threads** = Lightweight threads managed by the JVM (not OS). Millions of them can coexist.

```java
// Platform Thread (traditional): 1 Java thread = 1 OS thread
// ~1MB stack per thread, limited by OS (~thousands)
Thread platformThread = new Thread(() -> doWork());

// Virtual Thread: Many virtual threads multiplexed onto few OS threads
// ~few KB per thread, limited by memory (~millions)
Thread virtualThread = Thread.ofVirtual().start(() -> doWork());

// Preferred: Use executor
try (var executor = Executors.newVirtualThreadPerTaskExecutor()) {
    // Submit 1 million tasks!
    IntStream.range(0, 1_000_000).forEach(i ->
        executor.submit(() -> {
            // Each task gets its own virtual thread
            Thread.sleep(Duration.ofSeconds(1));  // Doesn't block OS thread!
            return processRequest(i);
        })
    );
}

// How it works internally:
// Virtual Thread → mounted on → Carrier Thread (platform thread in ForkJoinPool)
// When virtual thread blocks (I/O, sleep, lock):
//   1. Virtual thread is UNMOUNTED from carrier
//   2. Carrier thread picks up another virtual thread
//   3. When I/O completes, virtual thread is REMOUNTED on any available carrier
// Result: Blocking code becomes non-blocking!
```

**When to use Virtual Threads:**
- I/O-bound workloads (HTTP calls, database queries, file I/O)
- High-concurrency servers (handling thousands of concurrent connections)
- Replacing reactive programming (can write blocking code that scales)

**When NOT to use Virtual Threads:**
- CPU-bound computations (no I/O to yield on)
- When using synchronized blocks heavily (pins carrier thread)
- When using ThreadLocal extensively (each virtual thread has its own → memory waste)

```java
// PINNING: Virtual thread stuck on carrier (bad!)
// Occurs with: synchronized blocks, native/JNI calls
synchronized (lock) {
    socket.read();  // Virtual thread PINNED to carrier! Cannot unmount!
}

// FIX: Use ReentrantLock instead of synchronized
lock.lock();
try {
    socket.read();  // Virtual thread CAN unmount here
} finally {
    lock.unlock();
}
```

---

### Q77: Explain Structured Concurrency (Java 21 Preview).

**Answer:**

**Structured Concurrency** = Ensures that concurrent subtasks are treated as a unit. If one fails, others are cancelled. Lifetime of subtasks is bounded by scope.

```java
// Problem with unstructured concurrency:
CompletableFuture<User> userF = CompletableFuture.supplyAsync(() -> fetchUser());
CompletableFuture<Order> orderF = CompletableFuture.supplyAsync(() -> fetchOrder());
// If fetchUser() fails, fetchOrder() continues running (wasted resources)
// If this method throws, both futures may be orphaned

// Structured Concurrency solution:
Response handle() throws Exception {
    try (var scope = new StructuredTaskScope.ShutdownOnFailure()) {
        Subtask<User> user = scope.fork(() -> fetchUser());
        Subtask<Order> order = scope.fork(() -> fetchOrder());
        
        scope.join();            // Wait for both
        scope.throwIfFailed();   // Propagate failure
        
        // Both succeeded
        return new Response(user.get(), order.get());
    }
    // Scope guarantees: if fetchUser() fails, fetchOrder() is cancelled
    // No orphaned threads, no leaked resources
}

// ShutdownOnSuccess - return first successful result, cancel rest
Response handleFirstSuccess() throws Exception {
    try (var scope = new StructuredTaskScope.ShutdownOnSuccess<Response>()) {
        scope.fork(() -> fetchFromPrimary());
        scope.fork(() -> fetchFromSecondary());
        scope.fork(() -> fetchFromCache());
        
        scope.join();
        return scope.result();  // First successful result
    }
}
```

---

### Q78: What is the difference between wait/notify vs Condition?

**Answer:**

```java
// wait/notify (Object monitor):
synchronized (lock) {
    while (!condition) {
        lock.wait();  // Releases lock, waits
    }
    // Condition met, proceed
    lock.notifyAll();  // Wakes ALL waiting threads (even those waiting on different conditions)
}
// Problem: One wait set per object - cannot signal specific waiters

// Condition (Lock-based):
ReentrantLock lock = new ReentrantLock();
Condition notFull = lock.newCondition();   // Separate condition for producers
Condition notEmpty = lock.newCondition();  // Separate condition for consumers

// Producer:
lock.lock();
try {
    while (queue.size() == capacity) {
        notFull.await();  // Only producers wait here
    }
    queue.add(item);
    notEmpty.signal();    // Signal ONLY consumers (efficient!)
} finally {
    lock.unlock();
}

// Consumer:
lock.lock();
try {
    while (queue.isEmpty()) {
        notEmpty.await();  // Only consumers wait here
    }
    item = queue.remove();
    notFull.signal();      // Signal ONLY producers (efficient!)
} finally {
    lock.unlock();
}
```

| Feature | wait/notify | Condition |
|---------|------------|-----------|
| Multiple conditions | No (one wait set) | Yes (multiple per lock) |
| Selective signaling | No (notifyAll wakes all) | Yes (signal specific condition) |
| Timed wait | wait(timeout) | await(time, unit) |
| Deadline wait | No | awaitUntil(Date) |
| Uninterruptible wait | No | awaitUninterruptibly() |
| Fair queuing | No | Depends on lock fairness |

---

### Q79: Explain CopyOnWriteArrayList and CopyOnWriteArraySet.

**Answer:**

**CopyOnWriteArrayList** = Thread-safe List where every mutation creates a new copy of the internal array.

```java
CopyOnWriteArrayList<String> list = new CopyOnWriteArrayList<>();

// WRITE operations: Copy entire array
list.add("item");      // Creates new array, copies existing + new item
list.set(0, "new");    // Creates new array with modification
list.remove(0);        // Creates new array without element
// VERY EXPENSIVE for writes! O(n) copy for each write

// READ operations: No locking, no copying
list.get(0);           // Reads from current snapshot (volatile reference)
list.size();           // No locking needed!
for (String s : list) {
    // Iterates over SNAPSHOT at iteration start
    // NEVER throws ConcurrentModificationException
    // Does NOT reflect writes that happen during iteration
}

// Internal implementation:
private transient volatile Object[] array;  // Volatile reference

public boolean add(E e) {
    synchronized (lock) {
        Object[] current = getArray();
        int len = current.length;
        Object[] newArray = Arrays.copyOf(current, len + 1);  // COPY!
        newArray[len] = e;
        setArray(newArray);  // Atomic swap (volatile write)
        return true;
    }
}

public E get(int index) {
    return (E) getArray()[index];  // Just volatile read, no lock!
}
```

**When to use:**
- Read-heavy, write-rare scenarios
- Event listener lists (add/remove listeners rarely, notify frequently)
- Configuration lists (updated rarely, read constantly)
- Iterator must never throw ConcurrentModificationException

**When NOT to use:**
- Frequent writes (each write copies entire array)
- Large lists (copy cost proportional to size)
- Memory-sensitive applications (temporarily holds two copies)

---

### Q80: Explain the java.util.concurrent.locks package.

**Answer:**

```java
// 1. ReentrantLock - Mutual exclusion (reentrant)
ReentrantLock lock = new ReentrantLock();
lock.lock(); lock.lock();  // Same thread can re-enter (hold count = 2)
lock.unlock(); lock.unlock();  // Must unlock same number of times

// 2. ReentrantReadWriteLock - Multiple readers OR single writer
ReentrantReadWriteLock rwl = new ReentrantReadWriteLock();
rwl.readLock().lock();   // Many readers concurrently
rwl.writeLock().lock();  // Exclusive writer

// 3. StampedLock - Optimistic reads + read/write locks
StampedLock sl = new StampedLock();
long stamp = sl.tryOptimisticRead();  // Non-blocking!
// ...read data...
if (sl.validate(stamp)) { /* data is consistent */ }

// 4. Condition - Fine-grained wait/signal
Condition cond = lock.newCondition();
cond.await();     // Like Object.wait()
cond.signal();    // Like Object.notify()
cond.signalAll(); // Like Object.notifyAll()

// 5. LockSupport - Low-level thread parking
LockSupport.park();        // Suspend current thread
LockSupport.unpark(thread); // Resume specific thread
// Unlike wait/notify: doesn't need to hold a lock
// Unlike sleep: can be unparked by another thread
// Used internally by: AQS, ConcurrentHashMap, ForkJoinPool
```

---

### Q81: What is AbstractQueuedSynchronizer (AQS)?

**Answer:**

**AQS** = Framework for building synchronization primitives. Almost all java.util.concurrent classes are built on it.

```java
// AQS manages:
// 1. An int state (meaning depends on implementation)
// 2. A FIFO queue of waiting threads (CLH queue variant)

// Built on AQS:
// - ReentrantLock: state = hold count (0 = unlocked)
// - Semaphore: state = available permits
// - CountDownLatch: state = count
// - ReentrantReadWriteLock: state split into read count (upper 16 bits) + write count (lower 16 bits)

// Custom Synchronizer Example: SimpleLock (non-reentrant)
class SimpleLock extends AbstractQueuedSynchronizer {
    @Override
    protected boolean tryAcquire(int arg) {
        if (compareAndSetState(0, 1)) {  // CAS: 0 → 1
            setExclusiveOwnerThread(Thread.currentThread());
            return true;
        }
        return false;
    }
    
    @Override
    protected boolean tryRelease(int arg) {
        setExclusiveOwnerThread(null);
        setState(0);  // No CAS needed (only owner can release)
        return true;
    }
    
    public void lock() { acquire(1); }      // Template method: tryAcquire + queue
    public void unlock() { release(1); }    // Template method: tryRelease + signal
}
```

---

### Q82: What are the common concurrency design patterns?

**Answer:**

```java
// 1. Immutability Pattern - Thread-safe by design
final class ImmutablePoint {
    private final int x, y;
    ImmutablePoint(int x, int y) { this.x = x; this.y = y; }
    ImmutablePoint translate(int dx, int dy) { return new ImmutablePoint(x+dx, y+dy); }
}

// 2. Thread Confinement - Data accessible only by one thread
// ThreadLocal, Actor model, single-threaded event loops

// 3. Publication and Escape - Safe publishing of objects
// Safe publication patterns:
// a) Static initializer: static final Holder h = new Holder(42);
// b) Volatile field: volatile Holder h = new Holder(42);
// c) AtomicReference: AtomicReference<Holder> h = new AtomicReference<>(new Holder(42));
// d) Final field of properly constructed object
// e) Synchronized access

// 4. Double-Checked Locking (Singleton)
class Singleton {
    private static volatile Singleton INSTANCE;
    static Singleton getInstance() {
        Singleton local = INSTANCE;
        if (local == null) {
            synchronized (Singleton.class) {
                local = INSTANCE;
                if (local == null) {
                    INSTANCE = local = new Singleton();
                }
            }
        }
        return local;
    }
}

// 5. Thread-Safe Lazy Initialization Holder
class Singleton {
    private static class Holder {
        static final Singleton INSTANCE = new Singleton();
    }
    static Singleton getInstance() { return Holder.INSTANCE; }
    // Class loading guarantees thread-safety!
}

// 6. Balking Pattern - Only do work if in expected state
class WashingMachine {
    private enum State { IDLE, WASHING }
    private volatile State state = State.IDLE;
    
    synchronized void wash() {
        if (state == State.WASHING) return;  // BALK if already washing
        state = State.WASHING;
        // Start washing...
    }
}

// 7. Guarded Suspension - Wait until condition is met
class GuardedQueue<T> {
    private final Queue<T> queue = new LinkedList<>();
    
    synchronized T get() throws InterruptedException {
        while (queue.isEmpty()) {
            wait();  // Guard: wait until not empty
        }
        return queue.poll();
    }
    
    synchronized void put(T item) {
        queue.offer(item);
        notifyAll();  // Signal: condition may be met
    }
}
```

---


## 9. JVM Internals & Advanced Concepts

### Q83: How does the JVM ClassLoader work?

**Answer:**

**ClassLoader Hierarchy (Delegation Model):**
```
Bootstrap ClassLoader (C/C++ code, not a Java class)
│   Loads: java.lang.*, java.util.*, rt.jar (core Java classes)
│   Path: $JAVA_HOME/lib
│
├── Platform/Extension ClassLoader (Java 9+ / ext in Java 8)
│   Loads: javax.*, java.sql.*, ext/*.jar
│   Path: $JAVA_HOME/lib/ext
│
└── Application/System ClassLoader
    Loads: Application classes, -classpath, CLASSPATH
    Path: -cp or CLASSPATH environment variable
    │
    └── Custom ClassLoaders (user-defined)
        Example: Tomcat's WebAppClassLoader, OSGi bundle loaders
```

**Delegation Model (Parent-First):**
```java
// When a class needs to be loaded:
protected Class<?> loadClass(String name, boolean resolve) {
    // 1. Check if already loaded
    Class<?> c = findLoadedClass(name);
    if (c == null) {
        try {
            // 2. Delegate to PARENT first
            c = parent.loadClass(name, false);
        } catch (ClassNotFoundException e) {
            // 3. Parent couldn't load → try loading ourselves
            c = findClass(name);
        }
    }
    return c;
}
```

**Class Loading Phases:**
1. **Loading:** Find .class file bytes, create Class object
2. **Linking:**
   - **Verification:** Verify bytecode is valid (magic number, structure)
   - **Preparation:** Allocate memory for static fields (default values)
   - **Resolution:** Resolve symbolic references to direct references
3. **Initialization:** Execute static initializers and static blocks (thread-safe!)

**Common Issues:**
```java
// ClassNotFoundException: Class not found in classpath
// NoClassDefFoundError: Class was found at compile time but not at runtime
// ClassCastException with different ClassLoaders:
// Same .class file loaded by two different ClassLoaders = TWO DIFFERENT CLASSES!

ClassLoader cl1 = new URLClassLoader(urls);
ClassLoader cl2 = new URLClassLoader(urls);
Class<?> c1 = cl1.loadClass("com.MyClass");
Class<?> c2 = cl2.loadClass("com.MyClass");
c1 == c2;  // FALSE! Different class identity!
c1.cast(c2Instance);  // ClassCastException!
```

---

### Q84: What is the difference between Stack and Heap memory?

**Answer:**

| Feature | Stack | Heap |
|---------|-------|------|
| Storage | Primitives, object references, method frames | Objects, instance variables |
| Scope | Per-thread (private) | Shared across all threads |
| Lifetime | Method execution (LIFO) | Until GC collects |
| Size | Small (~512KB-1MB per thread) | Large (configurable, GB) |
| Speed | Very fast (pointer arithmetic) | Slower (allocation, GC) |
| Overflow | StackOverflowError | OutOfMemoryError |
| Thread-safe | Yes (private per thread) | No (needs synchronization) |
| Allocation | Automatic (frame push/pop) | Dynamic (new keyword) |
| Fragmentation | None (contiguous, LIFO) | Possible (managed by GC) |

```java
void example() {
    int x = 10;              // Stack: primitive value
    String s = "hello";      // Stack: reference 's'; Heap: String object (or String pool)
    Object obj = new Object(); // Stack: reference 'obj'; Heap: Object instance
    int[] arr = new int[5];  // Stack: reference 'arr'; Heap: array object
}
// When method returns: stack frame popped (x, s, obj, arr references gone)
// Heap objects eligible for GC if no other references exist
```

**Escape Analysis (JIT optimization):**
```java
void process() {
    Point p = new Point(1, 2);  // Does not escape method
    int sum = p.x + p.y;
    return sum;
}
// JIT may allocate Point on STACK (or eliminate entirely)
// Called "scalar replacement" - fields become local variables
```

---

### Q85: Explain String Pool and String immutability.

**Answer:**

```java
// String Pool (String Intern Pool):
// Special memory area in Heap (moved from PermGen to Heap in Java 7)
// Stores unique string literals

String s1 = "hello";          // Goes to String Pool
String s2 = "hello";          // Reuses same pool entry
String s3 = new String("hello"); // Creates NEW object on Heap (NOT in pool)
String s4 = s3.intern();      // Returns pool reference

s1 == s2;   // true (same pool reference)
s1 == s3;   // false (s3 is on heap, not pool)
s1 == s4;   // true (intern() returns pool reference)
s1.equals(s3); // true (same content)

// WHY immutable?
// 1. String Pool works because strings won't change after sharing
// 2. Thread-safe (no synchronization needed)
// 3. HashCode caching (computed once, reused)
// 4. Security (class names, URLs, passwords can't be modified)
// 5. Class loading uses strings (must be immutable for safety)

// String vs StringBuilder vs StringBuffer:
String s = "a" + "b" + "c";       // Compiler optimizes to "abc" (literals)
String s = a + b + c;             // Creates StringBuilder internally (Java 5+)

StringBuilder sb = new StringBuilder(); // NOT thread-safe, faster
StringBuffer buf = new StringBuffer();  // Thread-safe (synchronized), slower

// Performance:
// Concatenation in loop: O(n²) with String, O(n) with StringBuilder
for (int i = 0; i < 10000; i++) {
    str += i;  // BAD! Creates new String each iteration
}
StringBuilder sb = new StringBuilder();
for (int i = 0; i < 10000; i++) {
    sb.append(i);  // GOOD! Modifies in-place
}
```

---

### Q86: What is Reflection and when to use it?

**Answer:**

```java
// Reflection = Inspect/modify classes, methods, fields at RUNTIME

// Get class info
Class<?> clazz = Class.forName("com.example.User");
Class<?> clazz = user.getClass();
Class<?> clazz = User.class;

// Create instance
Object instance = clazz.getDeclaredConstructor().newInstance();

// Access private field
Field field = clazz.getDeclaredField("name");
field.setAccessible(true);  // Bypass access control
String name = (String) field.get(instance);
field.set(instance, "newName");  // Modify private field!

// Invoke method
Method method = clazz.getDeclaredMethod("process", String.class, int.class);
method.setAccessible(true);
Object result = method.invoke(instance, "arg1", 42);

// Get all methods/fields
Method[] methods = clazz.getDeclaredMethods();  // Includes private
Method[] methods = clazz.getMethods();           // Only public (including inherited)

// Check annotations
if (method.isAnnotationPresent(Transactional.class)) {
    Transactional ann = method.getAnnotation(Transactional.class);
    int timeout = ann.timeout();
}
```

**Use Cases:**
- Frameworks (Spring DI, Hibernate ORM, JUnit)
- Serialization/Deserialization (Jackson, Gson)
- Dynamic proxies
- Annotation processing at runtime
- Plugin systems

**Performance Impact:**
- 10-100x slower than direct access (no JIT inlining, security checks)
- Mitigations: cache Method/Field objects, use MethodHandle (Java 7+), use LambdaMetafactory

---

### Q87: What is the difference between Checked and Unchecked Exceptions?

**Answer:**

```
Throwable
├── Error (unchecked - JVM problems, don't catch)
│   ├── OutOfMemoryError
│   ├── StackOverflowError
│   └── NoClassDefFoundError
│
└── Exception
    ├── RuntimeException (unchecked - programming errors)
    │   ├── NullPointerException
    │   ├── IllegalArgumentException
    │   ├── IndexOutOfBoundsException
    │   ├── ClassCastException
    │   ├── ConcurrentModificationException
    │   └── UnsupportedOperationException
    │
    └── Checked Exceptions (must handle or declare)
        ├── IOException
        ├── SQLException
        ├── ClassNotFoundException
        ├── InterruptedException
        └── CloneNotSupportedException
```

| Aspect | Checked | Unchecked |
|--------|---------|-----------|
| Compiler enforces | Yes (must catch or throws) | No |
| Recovery expected | Yes (transient failures) | No (programming bugs) |
| Examples | IOException, SQLException | NPE, IllegalArgumentException |
| When to use | External failures (I/O, network) | Logic errors, precondition violations |

**Best Practices:**
```java
// 1. Never catch Throwable/Error (unless cleanup and rethrow)
// 2. Use specific exceptions, not generic Exception
// 3. Don't use exceptions for flow control
// 4. Always include cause: new MyException("msg", cause)
// 5. Use try-with-resources for AutoCloseable resources
// 6. Don't swallow exceptions: catch (Exception e) { /* empty */ }
// 7. Prefer unchecked for programming errors, checked for recoverable conditions
```

---

### Q88: Explain Serialization and its pitfalls.

**Answer:**

```java
// Serialization = Converting object to byte stream
// Deserialization = Reconstructing object from byte stream

class User implements Serializable {
    private static final long serialVersionUID = 1L;  // Version control
    
    private String name;
    private transient String password;  // NOT serialized
    private static String company;     // NOT serialized (belongs to class)
    
    // Custom serialization hooks
    private void writeObject(ObjectOutputStream out) throws IOException {
        out.defaultWriteObject();
        out.writeObject(encrypt(password));  // Custom logic
    }
    
    private void readObject(ObjectInputStream in) throws IOException, ClassNotFoundException {
        in.defaultReadObject();
        this.password = decrypt((String) in.readObject());
    }
    
    // Replace serialized form
    private Object writeReplace() {
        return new UserProxy(this);  // Serialize proxy instead
    }
    
    // Resolve deserialized object
    private Object readResolve() {
        return UserRegistry.get(name);  // Return canonical instance (singleton)
    }
}
```

**Pitfalls:**
1. **Security:** Deserialization of untrusted data = Remote Code Execution vulnerability
2. **Breaking encapsulation:** Private fields accessible after deserialization
3. **Inheritance issues:** Superclass must have no-arg constructor (if not Serializable)
4. **serialVersionUID:** If not declared, auto-generated from class structure → breaks on any change
5. **Singleton breaking:** Deserialization creates new instance → use readResolve()

**Modern alternatives:** JSON (Jackson/Gson), Protocol Buffers, Avro, Kryo

---

### Q89: Explain Generics, Type Erasure, and their limitations.

**Answer:**

```java
// Generics provide compile-time type safety
List<String> strings = new ArrayList<>();
strings.add("hello");
// strings.add(123);  // Compile error!

// Type Erasure: Generics are ERASED at runtime
// List<String> becomes just List at bytecode level
// The JVM has NO knowledge of generic types at runtime!

// Consequences of Type Erasure:
// 1. Cannot create generic array
// T[] array = new T[10];  // COMPILE ERROR
// Workaround: (T[]) new Object[10] or Array.newInstance(clazz, 10)

// 2. Cannot use instanceof with generics
// if (list instanceof List<String>) { }  // COMPILE ERROR
if (list instanceof List<?>) { }  // OK (unbounded wildcard)

// 3. Cannot create instance of type parameter
// T obj = new T();  // COMPILE ERROR
// Workaround: pass Class<T> or Supplier<T>
<T> T create(Class<T> clazz) throws Exception {
    return clazz.getDeclaredConstructor().newInstance();
}

// 4. Static fields cannot use class type parameter
class Box<T> {
    // static T value;  // COMPILE ERROR (T is instance-level)
}

// Bounded Type Parameters:
<T extends Comparable<T>> T max(T a, T b) {
    return a.compareTo(b) >= 0 ? a : b;
}

// Wildcards:
List<?> anything;                        // Unknown type (read-only)
List<? extends Number> numbers;          // Number or subclass (producer - read)
List<? super Integer> integers;          // Integer or superclass (consumer - write)

// PECS: Producer Extends, Consumer Super
<T> void copy(List<? extends T> src, List<? super T> dest) {
    for (T item : src) {     // src produces T items (extends)
        dest.add(item);       // dest consumes T items (super)
    }
}
```

---

### Q90: What are Java Records (Java 16+)?

**Answer:**

```java
// Record = Immutable data carrier (like Lombok @Value)
public record Point(int x, int y) { }
// Automatically generates:
// - private final fields (x, y)
// - Canonical constructor
// - Accessor methods: x(), y() (NOT getX()!)
// - equals() based on all fields
// - hashCode() based on all fields
// - toString() like "Point[x=1, y=2]"

// Custom constructor (validation):
public record Range(int start, int end) {
    public Range {  // Compact canonical constructor
        if (start > end) throw new IllegalArgumentException("start > end");
        // No this.start = start; needed (implicit)
    }
}

// Additional methods:
public record Circle(double radius) {
    public double area() { return Math.PI * radius * radius; }
    
    // Custom constructor
    public static Circle unit() { return new Circle(1.0); }
}

// Records CANNOT:
// - Extend other classes (implicitly extends Record)
// - Be abstract
// - Have mutable instance fields (all are final)
// - Have instance initializers
// Records CAN:
// - Implement interfaces
// - Have static fields/methods
// - Have custom methods
// - Override accessor methods (but should maintain semantics)

// Pattern matching with Records (Java 21):
sealed interface Shape permits Circle, Rectangle {}
record Circle(double r) implements Shape {}
record Rectangle(double w, double h) implements Shape {}

double area(Shape shape) {
    return switch (shape) {
        case Circle(var r) -> Math.PI * r * r;
        case Rectangle(var w, var h) -> w * h;
    };
}
```

---

### Q91: Explain Sealed Classes (Java 17).

**Answer:**

```java
// Sealed class restricts which classes can extend/implement it
// Enables exhaustive pattern matching (compiler knows all subtypes)

public sealed interface Shape 
    permits Circle, Rectangle, Triangle {  // ONLY these can implement
}

public record Circle(double radius) implements Shape { }  // Must be final/sealed/non-sealed

public final class Rectangle implements Shape {  // final = no further extension
    private final double width, height;
    // ...
}

public non-sealed class Triangle implements Shape {  // non-sealed = open for extension
    // Anyone can extend Triangle
}

// sealed class Dog extends Animal { }  // Can also seal classes

// Exhaustive switch (compiler checks all subtypes covered):
double area(Shape shape) {
    return switch (shape) {
        case Circle c -> Math.PI * c.radius() * c.radius();
        case Rectangle r -> r.getWidth() * r.getHeight();
        case Triangle t -> t.getBase() * t.getHeight() / 2;
        // No default needed! Compiler knows these are all cases
    };
}
```

---

### Q92: What is the difference between Interface and Abstract Class?

**Answer:**

| Feature | Interface | Abstract Class |
|---------|-----------|----------------|
| Methods | Abstract, default, static, private (Java 9+) | Abstract + concrete |
| Fields | public static final only | Any access modifier, any type |
| Constructor | No | Yes |
| Multiple inheritance | Yes (implements multiple) | No (extends one only) |
| State | No instance state | Can have instance state |
| Access modifiers | Public only (methods) | Any |
| Default behavior | Java 8+ default methods | Always had concrete methods |
| Use when | Defining a contract/capability | Sharing code among related classes |

**Design Decision:**
- **Interface:** "Can do" relationship (Runnable, Serializable, Comparable)
- **Abstract Class:** "Is a" relationship with shared state/behavior (AbstractList, HttpServlet)

```java
// Java 8+ blurred the line with default methods
// Prefer interfaces when possible (more flexible)
// Use abstract class ONLY when you need:
// 1. Instance fields (state)
// 2. Constructors (initialization)
// 3. Non-public members
// 4. Methods that need to modify object state
```

---

### Q93: Explain the Java Module System (JPMS - Java 9+).

**Answer:**

```java
// module-info.java at root of module
module com.myapp.core {
    requires java.sql;                    // Depends on java.sql module
    requires transitive com.myapp.utils;  // Transitive: consumers also get utils
    
    exports com.myapp.core.api;           // Expose package to other modules
    exports com.myapp.core.spi to com.myapp.plugins;  // Qualified export
    
    opens com.myapp.core.model to com.google.gson;  // Allow reflection access
    
    provides com.myapp.spi.Parser with com.myapp.core.JsonParser;  // Service provider
    uses com.myapp.spi.Formatter;  // Service consumer
}
```

**Benefits:**
- Strong encapsulation (internal packages truly hidden)
- Reliable configuration (missing dependencies detected at compile/startup)
- Smaller runtime (jlink creates custom JRE with only needed modules)
- Performance (JVM can optimize knowing module boundaries)

---

### Q94: What is the difference between Proxy, Dynamic Proxy, and CGLIB?

**Answer:**

```java
// 1. Static Proxy (design pattern):
interface UserService { User findUser(int id); }

class UserServiceProxy implements UserService {
    private final UserService target;
    
    @Override
    public User findUser(int id) {
        log("Before findUser");
        User result = target.findUser(id);  // Delegate
        log("After findUser");
        return result;
    }
}

// 2. JDK Dynamic Proxy (interface-based, runtime):
UserService proxy = (UserService) Proxy.newProxyInstance(
    UserService.class.getClassLoader(),
    new Class<?>[] { UserService.class },
    (proxyObj, method, args) -> {
        log("Before: " + method.getName());
        Object result = method.invoke(target, args);
        log("After: " + method.getName());
        return result;
    }
);
// Limitation: Target MUST implement an interface

// 3. CGLIB Proxy (class-based, runtime):
Enhancer enhancer = new Enhancer();
enhancer.setSuperclass(UserServiceImpl.class);  // Can proxy concrete classes!
enhancer.setCallback((MethodInterceptor) (obj, method, args, proxy) -> {
    log("Before: " + method.getName());
    Object result = proxy.invokeSuper(obj, args);
    log("After: " + method.getName());
    return result;
});
UserServiceImpl proxy = (UserServiceImpl) enhancer.create();
// Works on classes directly (creates subclass)
// Cannot proxy final classes/methods
```

| Feature | JDK Dynamic Proxy | CGLIB |
|---------|-------------------|-------|
| Based on | Interfaces | Subclassing |
| Target requirement | Must implement interface | Any non-final class |
| Performance | Slightly slower | Slightly faster |
| Dependency | JDK built-in | External library |
| Final methods | N/A | Cannot proxy |
| Used by | Spring AOP (interface mode) | Spring AOP (class mode), Hibernate |

---

## 10. Design Patterns & SOLID Principles

### Q95: Explain SOLID Principles with Java examples.

**Answer:**

**S - Single Responsibility Principle:**
```java
// BAD: One class does everything
class UserManager {
    void createUser(User u) { /* DB logic */ }
    void sendEmail(User u) { /* Email logic */ }
    String generateReport() { /* Report logic */ }
}

// GOOD: Each class has one reason to change
class UserRepository { void save(User u) { } }
class EmailService { void sendWelcomeEmail(User u) { } }
class UserReportGenerator { String generate(List<User> users) { } }
```

**O - Open/Closed Principle (open for extension, closed for modification):**
```java
// BAD: Must modify class to add new shape
class AreaCalculator {
    double calculate(Object shape) {
        if (shape instanceof Circle c) return Math.PI * c.r * c.r;
        if (shape instanceof Rectangle r) return r.w * r.h;
        // Must ADD code here for every new shape!
    }
}

// GOOD: Extend without modifying existing code
interface Shape { double area(); }
record Circle(double r) implements Shape { 
    public double area() { return Math.PI * r * r; }
}
record Rectangle(double w, double h) implements Shape {
    public double area() { return w * h; }
}
// New shapes: just implement Shape. No existing code changes!
```

**L - Liskov Substitution Principle (subtypes must be substitutable):**
```java
// BAD: Square violates Rectangle contract
class Rectangle {
    void setWidth(int w) { this.width = w; }
    void setHeight(int h) { this.height = h; }
    int area() { return width * height; }
}
class Square extends Rectangle {
    void setWidth(int w) { this.width = w; this.height = w; }  // Breaks!
    // Client code: rect.setWidth(5); rect.setHeight(3); assert rect.area() == 15;
    // With Square: area == 9 (unexpected!)
}

// GOOD: Separate abstractions
interface Shape { int area(); }
record Rectangle(int w, int h) implements Shape { public int area() { return w*h; } }
record Square(int side) implements Shape { public int area() { return side*side; } }
```

**I - Interface Segregation Principle (no forced unused methods):**
```java
// BAD: Fat interface
interface Worker {
    void work();
    void eat();
    void sleep();
}
class Robot implements Worker {
    void work() { /* OK */ }
    void eat() { /* Robots don't eat! */ throw new UnsupportedOperationException(); }
    void sleep() { /* Robots don't sleep! */ throw new UnsupportedOperationException(); }
}

// GOOD: Segregated interfaces
interface Workable { void work(); }
interface Feedable { void eat(); }
interface Sleepable { void sleep(); }
class Human implements Workable, Feedable, Sleepable { /* all make sense */ }
class Robot implements Workable { /* only what applies */ }
```

**D - Dependency Inversion Principle (depend on abstractions, not concretions):**
```java
// BAD: High-level module depends on low-level module
class OrderService {
    private MySQLDatabase db = new MySQLDatabase();  // Concrete dependency!
    void save(Order o) { db.insert(o); }
}

// GOOD: Both depend on abstraction
interface OrderRepository { void save(Order o); }
class MySQLOrderRepository implements OrderRepository { /* MySQL impl */ }
class MongoOrderRepository implements OrderRepository { /* Mongo impl */ }

class OrderService {
    private final OrderRepository repo;  // Depends on abstraction
    OrderService(OrderRepository repo) { this.repo = repo; }  // Injected
}
```

---

### Q96: Explain Singleton Pattern - All implementations and thread safety.

**Answer:**

```java
// 1. Eager Initialization (simplest, thread-safe)
class EagerSingleton {
    private static final EagerSingleton INSTANCE = new EagerSingleton();
    private EagerSingleton() { }
    public static EagerSingleton getInstance() { return INSTANCE; }
}
// Pro: Thread-safe (class loading is synchronized)
// Con: Instance created even if never used

// 2. Lazy Initialization (not thread-safe!)
class LazySingleton {
    private static LazySingleton instance;
    public static LazySingleton getInstance() {
        if (instance == null) {           // Race condition!
            instance = new LazySingleton();
        }
        return instance;
    }
}

// 3. Synchronized Method (thread-safe but slow)
class SyncSingleton {
    private static SyncSingleton instance;
    public static synchronized SyncSingleton getInstance() {
        if (instance == null) instance = new SyncSingleton();
        return instance;
    }
}
// Con: Every call acquires lock (even after initialization)

// 4. Double-Checked Locking (thread-safe, performant)
class DCLSingleton {
    private static volatile DCLSingleton instance;  // volatile REQUIRED!
    public static DCLSingleton getInstance() {
        if (instance == null) {
            synchronized (DCLSingleton.class) {
                if (instance == null) {
                    instance = new DCLSingleton();
                }
            }
        }
        return instance;
    }
}

// 5. Initialization-on-Demand Holder (BEST for lazy + thread-safe)
class HolderSingleton {
    private HolderSingleton() { }
    private static class Holder {
        static final HolderSingleton INSTANCE = new HolderSingleton();
    }
    public static HolderSingleton getInstance() {
        return Holder.INSTANCE;  // Class loaded only on first call
    }
}
// Pro: Lazy, thread-safe (class loading guarantees), no synchronization

// 6. Enum Singleton (Josh Bloch's recommendation)
enum EnumSingleton {
    INSTANCE;
    
    private final Connection connection;
    EnumSingleton() { connection = createConnection(); }
    public Connection getConnection() { return connection; }
}
// Pro: Thread-safe, serialization-safe, reflection-safe
// Con: Cannot extend other class, eager initialization
```

---

### Q97: Explain Strategy, Observer, and Factory patterns.

**Answer:**

```java
// STRATEGY PATTERN: Encapsulate algorithms, make them interchangeable
interface SortStrategy {
    <T extends Comparable<T>> void sort(List<T> list);
}
class QuickSort implements SortStrategy { /* quicksort impl */ }
class MergeSort implements SortStrategy { /* mergesort impl */ }
class TimSort implements SortStrategy { /* timsort impl */ }

class Sorter {
    private SortStrategy strategy;
    void setStrategy(SortStrategy s) { this.strategy = s; }
    <T extends Comparable<T>> void sort(List<T> list) { strategy.sort(list); }
}
// Java 8: Can use lambdas / method references instead of classes
Sorter sorter = new Sorter();
sorter.setStrategy(Collections::sort);  // Strategy as lambda!

// OBSERVER PATTERN: One-to-many dependency, notify on state change
interface EventListener<T> {
    void onEvent(T event);
}

class EventBus<T> {
    private final List<EventListener<T>> listeners = new CopyOnWriteArrayList<>();
    
    void subscribe(EventListener<T> listener) { listeners.add(listener); }
    void unsubscribe(EventListener<T> listener) { listeners.remove(listener); }
    void publish(T event) {
        listeners.forEach(l -> l.onEvent(event));
    }
}

// FACTORY PATTERN: Create objects without exposing creation logic
interface Notification { void send(String message); }
class EmailNotification implements Notification { /* ... */ }
class SMSNotification implements Notification { /* ... */ }
class PushNotification implements Notification { /* ... */ }

class NotificationFactory {
    static Notification create(String type) {
        return switch (type) {
            case "email" -> new EmailNotification();
            case "sms" -> new SMSNotification();
            case "push" -> new PushNotification();
            default -> throw new IllegalArgumentException("Unknown: " + type);
        };
    }
}

// ABSTRACT FACTORY: Family of related objects
interface UIFactory {
    Button createButton();
    TextField createTextField();
    Menu createMenu();
}
class WindowsUIFactory implements UIFactory { /* Windows widgets */ }
class MacUIFactory implements UIFactory { /* Mac widgets */ }
```

---

### Q98: Explain Builder Pattern and its real-world usage.

**Answer:**

```java
// Builder Pattern: Construct complex objects step by step
// Perfect for objects with many optional parameters

public class HttpRequest {
    private final String url;
    private final String method;
    private final Map<String, String> headers;
    private final String body;
    private final int timeout;
    private final boolean followRedirects;
    
    private HttpRequest(Builder builder) {
        this.url = builder.url;
        this.method = builder.method;
        this.headers = Collections.unmodifiableMap(builder.headers);
        this.body = builder.body;
        this.timeout = builder.timeout;
        this.followRedirects = builder.followRedirects;
    }
    
    public static class Builder {
        private final String url;            // Required
        private String method = "GET";       // Optional with default
        private Map<String, String> headers = new HashMap<>();
        private String body;
        private int timeout = 30000;
        private boolean followRedirects = true;
        
        public Builder(String url) {
            this.url = Objects.requireNonNull(url);
        }
        
        public Builder method(String method) {
            this.method = method;
            return this;  // Fluent API
        }
        
        public Builder header(String key, String value) {
            this.headers.put(key, value);
            return this;
        }
        
        public Builder body(String body) {
            this.body = body;
            return this;
        }
        
        public Builder timeout(int ms) {
            this.timeout = ms;
            return this;
        }
        
        public Builder followRedirects(boolean follow) {
            this.followRedirects = follow;
            return this;
        }
        
        public HttpRequest build() {
            validate();
            return new HttpRequest(this);
        }
        
        private void validate() {
            if (method.equals("POST") && body == null) {
                throw new IllegalStateException("POST requires body");
            }
        }
    }
}

// Usage:
HttpRequest request = new HttpRequest.Builder("https://api.example.com/users")
    .method("POST")
    .header("Content-Type", "application/json")
    .header("Authorization", "Bearer token123")
    .body("{\"name\": \"John\"}")
    .timeout(5000)
    .build();
```

---

## 11. Spring & Microservices Interview Questions

### Q99: How does Spring Dependency Injection work internally?

**Answer:**

```java
// Spring IoC Container creates and manages beans

// 1. Bean Definition: Spring reads @Component, @Service, @Bean, XML config
// 2. BeanFactory/ApplicationContext creates beans
// 3. Dependencies resolved via:
//    - Constructor Injection (RECOMMENDED)
//    - Setter Injection
//    - Field Injection (@Autowired on field - NOT recommended)

@Service
class OrderService {
    private final OrderRepository repo;
    private final PaymentGateway payment;
    
    // Constructor injection (preferred - immutable, testable)
    @Autowired  // Optional in Spring 4.3+ (single constructor)
    OrderService(OrderRepository repo, PaymentGateway payment) {
        this.repo = repo;
        this.payment = payment;
    }
}

// Spring resolution order:
// 1. By type (if unique bean of that type exists)
// 2. By @Qualifier name
// 3. By field/parameter name matching bean name
// 4. @Primary bean (if multiple candidates)

// Bean Scopes:
// singleton (default) - one instance per container
// prototype - new instance per injection/request
// request - one per HTTP request (web)
// session - one per HTTP session (web)
// application - one per ServletContext
```

**Internal Bean Lifecycle:**
```
Constructor → @PostConstruct → afterPropertiesSet() → custom init-method
                        ...bean is used...
@PreDestroy → destroy() → custom destroy-method
```

---

### Q100: Explain Spring AOP (Aspect-Oriented Programming).

**Answer:**

```java
// AOP: Cross-cutting concerns (logging, security, transactions) separated from business logic

@Aspect
@Component
class LoggingAspect {
    
    // Pointcut: WHERE to apply advice
    @Pointcut("execution(* com.myapp.service.*.*(..))")
    void serviceLayer() { }
    
    // Before advice: runs before method
    @Before("serviceLayer()")
    void logBefore(JoinPoint jp) {
        log.info("Calling: {}", jp.getSignature().getName());
    }
    
    // After returning: runs after successful return
    @AfterReturning(pointcut = "serviceLayer()", returning = "result")
    void logAfterReturning(JoinPoint jp, Object result) {
        log.info("Returned: {}", result);
    }
    
    // Around: wraps method (most powerful)
    @Around("serviceLayer()")
    Object measureTime(ProceedingJoinPoint pjp) throws Throwable {
        long start = System.currentTimeMillis();
        try {
            return pjp.proceed();  // Execute actual method
        } finally {
            long duration = System.currentTimeMillis() - start;
            log.info("{} took {}ms", pjp.getSignature(), duration);
        }
    }
    
    // AfterThrowing: exception handling
    @AfterThrowing(pointcut = "serviceLayer()", throwing = "ex")
    void logException(JoinPoint jp, Exception ex) {
        log.error("Exception in {}: {}", jp.getSignature(), ex.getMessage());
    }
}

// How @Transactional works (AOP-based):
// Spring creates a proxy around your bean
// Proxy: begin TX → call actual method → commit/rollback TX
// This is why @Transactional doesn't work on private methods
// or self-invocation (this.method() bypasses proxy!)
```

---

### Q101: What is the difference between @Component, @Service, @Repository, @Controller?

**Answer:**

All are specializations of `@Component` (all register as Spring beans):

| Annotation | Layer | Special Behavior |
|-----------|-------|-----------------|
| @Component | Generic | Basic bean registration |
| @Service | Business | None (semantic only) |
| @Repository | Data | Exception translation (DB exceptions → DataAccessException) |
| @Controller | Web | Request mapping, view resolution |
| @RestController | Web API | @Controller + @ResponseBody (JSON/XML response) |

---

### Q102: Explain Spring Boot Auto-Configuration.

**Answer:**

```java
// @SpringBootApplication = @Configuration + @ComponentScan + @EnableAutoConfiguration

// How Auto-Configuration works:
// 1. Spring Boot reads META-INF/spring/org.springframework.boot.autoconfigure.AutoConfiguration.imports
// 2. Lists auto-configuration classes
// 3. Each class has @Conditional annotations:
//    @ConditionalOnClass - only if class is on classpath
//    @ConditionalOnMissingBean - only if user hasn't defined their own
//    @ConditionalOnProperty - only if property is set

// Example: DataSourceAutoConfiguration
@AutoConfiguration
@ConditionalOnClass(DataSource.class)  // Only if JDBC on classpath
@EnableConfigurationProperties(DataSourceProperties.class)
class DataSourceAutoConfiguration {
    
    @Bean
    @ConditionalOnMissingBean  // Only if user hasn't defined DataSource bean
    DataSource dataSource(DataSourceProperties props) {
        return createDataSource(props);
    }
}

// To override: just define your own @Bean of same type
@Configuration
class MyConfig {
    @Bean  // This takes precedence over auto-configuration
    DataSource dataSource() {
        return myCustomDataSource();
    }
}
```

---

### Q103: What is the difference between Monolithic vs Microservices architecture?

**Answer:**

| Aspect | Monolithic | Microservices |
|--------|-----------|---------------|
| Deployment | Single unit | Independent services |
| Scaling | Scale entire app | Scale individual services |
| Technology | Single tech stack | Polyglot (per service) |
| Database | Single shared DB | Database per service |
| Team structure | Large team on one codebase | Small teams per service |
| Communication | In-process method calls | Network calls (HTTP/gRPC/messaging) |
| Failure isolation | One bug can crash all | Fault isolated per service |
| Complexity | Simple to develop initially | Complex infrastructure (K8s, service mesh) |
| Testing | Easier E2E testing | Complex integration testing |
| Deployment speed | Slow (deploy everything) | Fast (deploy one service) |

**When to use Microservices:**
- Large team (>20 developers)
- Different scaling requirements per component
- Need technology diversity
- Independent deployment cycles
- Clear domain boundaries (DDD bounded contexts)

**When to use Monolith:**
- Small team
- New product (uncertain boundaries)
- Simple domain
- Low traffic
- Start here, extract services when needed ("monolith first")

---

### Q104: Explain Circuit Breaker Pattern.

**Answer:**

```java
// Circuit Breaker: Prevent cascading failures in distributed systems
// States: CLOSED → OPEN → HALF_OPEN

// CLOSED: Requests flow normally, failures counted
// OPEN: Requests fail immediately (fast-fail), no network call
// HALF_OPEN: Allow limited requests to test if service recovered

// Using Resilience4j:
CircuitBreakerConfig config = CircuitBreakerConfig.custom()
    .failureRateThreshold(50)           // Open if 50% failures
    .slowCallRateThreshold(80)          // Open if 80% slow calls
    .waitDurationInOpenState(Duration.ofSeconds(30))  // Wait before half-open
    .slidingWindowSize(10)              // Evaluate last 10 calls
    .minimumNumberOfCalls(5)            // Minimum calls before evaluation
    .permittedNumberOfCallsInHalfOpenState(3)  // Test calls in half-open
    .build();

CircuitBreaker cb = CircuitBreaker.of("userService", config);

// Decorate function:
Supplier<User> decorated = CircuitBreaker.decorateSupplier(cb, () -> userService.getUser(id));
Try<User> result = Try.ofSupplier(decorated)
    .recover(CallNotPermittedException.class, e -> fallbackUser());

// With Spring Boot:
@CircuitBreaker(name = "userService", fallbackMethod = "fallback")
public User getUser(int id) {
    return restTemplate.getForObject("/users/" + id, User.class);
}

public User fallback(int id, Throwable t) {
    return User.defaultUser();  // Graceful degradation
}
```

---

### Q105: What is Event-Driven Architecture and how to implement it in Java?

**Answer:**

```java
// 1. Spring Application Events (in-process)
class OrderCreatedEvent extends ApplicationEvent {
    private final Order order;
    OrderCreatedEvent(Object source, Order order) {
        super(source);
        this.order = order;
    }
}

@Service
class OrderService {
    @Autowired ApplicationEventPublisher publisher;
    
    void createOrder(Order order) {
        orderRepo.save(order);
        publisher.publishEvent(new OrderCreatedEvent(this, order));
    }
}

@Component
class NotificationListener {
    @EventListener
    void handleOrderCreated(OrderCreatedEvent event) {
        sendEmail(event.getOrder());
    }
    
    @TransactionalEventListener(phase = AFTER_COMMIT)  // Only after TX commits
    void handleOrderConfirmed(OrderCreatedEvent event) {
        sendConfirmation(event.getOrder());
    }
}

// 2. Message Broker (Kafka) - distributed events
@Service
class OrderPublisher {
    @Autowired KafkaTemplate<String, OrderEvent> kafka;
    
    void publishOrder(Order order) {
        kafka.send("orders", order.getId(), new OrderEvent(order));
    }
}

@KafkaListener(topics = "orders", groupId = "notification-service")
void consumeOrder(OrderEvent event) {
    processOrder(event);
}
```

---

## 12. Additional Critical Interview Questions

### Q106: What is the difference between == and equals()?

**Answer:**

```java
// == compares REFERENCES (memory address)
// equals() compares CONTENT (if properly overridden)

String s1 = new String("hello");
String s2 = new String("hello");
s1 == s2;      // false (different objects in heap)
s1.equals(s2); // true (same content)

String s3 = "hello";
String s4 = "hello";
s3 == s4;      // true (same String Pool reference)

Integer a = 127;
Integer b = 127;
a == b;  // true (Integer cache: -128 to 127)

Integer c = 128;
Integer d = 128;
c == d;  // false (outside cache, different objects!)
c.equals(d);  // true (same value)
```

---

### Q107: What is Autoboxing/Unboxing and its pitfalls?

**Answer:**

```java
// Autoboxing: primitive → wrapper (int → Integer)
Integer x = 42;  // Compiler: Integer.valueOf(42)

// Unboxing: wrapper → primitive (Integer → int)
int y = x;  // Compiler: x.intValue()

// PITFALLS:

// 1. NullPointerException on unboxing null
Integer wrapper = null;
int primitive = wrapper;  // NPE! (calls null.intValue())

// 2. Performance in loops (unnecessary object creation)
Long sum = 0L;
for (long i = 0; i < 1_000_000; i++) {
    sum += i;  // Creates ~1M Long objects! Use long instead
}

// 3. == comparison with wrapper types
Integer a = 200, b = 200;
a == b;  // false! (not cached, different objects)
a.equals(b);  // true

// 4. Integer cache (-128 to 127)
Integer a = 127, b = 127;
a == b;  // true (cached)
Integer c = 128, d = 128;
c == d;  // false (not cached)
```

---

### Q108: Explain Java I/O vs NIO vs NIO.2.

**Answer:**

```java
// IO (java.io) - Stream-based, blocking
// - Byte streams: InputStream/OutputStream
// - Character streams: Reader/Writer
// - Blocking: thread waits until data is available
InputStream is = new FileInputStream("file.txt");
BufferedReader br = new BufferedReader(new InputStreamReader(is));
String line = br.readLine();  // BLOCKS until data available

// NIO (java.nio) - Buffer/Channel-based, non-blocking possible
// - Buffers: ByteBuffer, CharBuffer (data containers)
// - Channels: FileChannel, SocketChannel (data conduits)
// - Selectors: Monitor multiple channels with one thread
ByteBuffer buffer = ByteBuffer.allocate(1024);
FileChannel channel = FileChannel.open(path, READ);
channel.read(buffer);  // Read into buffer
buffer.flip();  // Prepare for reading from buffer

// Selector (non-blocking I/O multiplexing):
Selector selector = Selector.open();
serverChannel.configureBlocking(false);
serverChannel.register(selector, SelectionKey.OP_ACCEPT);

while (true) {
    selector.select();  // Blocks until at least one channel ready
    Set<SelectionKey> keys = selector.selectedKeys();
    for (SelectionKey key : keys) {
        if (key.isAcceptable()) { /* new connection */ }
        if (key.isReadable()) { /* data available */ }
    }
}

// NIO.2 (Java 7) - Async I/O, Path API, file watching
// Path + Files (better file operations):
Path path = Paths.get("/home/user/file.txt");
List<String> lines = Files.readAllLines(path);
Files.write(path, "content".getBytes());
Files.walk(dir).filter(p -> p.toString().endsWith(".java")).forEach(System.out::println);

// AsynchronousFileChannel:
AsynchronousFileChannel afc = AsynchronousFileChannel.open(path, READ);
Future<Integer> result = afc.read(buffer, 0);  // Non-blocking!
// Or with callback:
afc.read(buffer, 0, null, new CompletionHandler<Integer, Void>() {
    public void completed(Integer bytesRead, Void attachment) { /* success */ }
    public void failed(Throwable exc, Void attachment) { /* failure */ }
});
```

---

### Q109: What is the Happens-Before relationship in detail?

**Answer:**

```java
// Happens-Before: If action A happens-before action B,
// then A's effects are VISIBLE to B and A is ORDERED before B.

// Rule 1: Program Order
x = 1;    // Happens-before
y = 2;    // ...this (within same thread)

// Rule 2: Monitor Lock
synchronized(lock) { x = 1; }  // Happens-before
synchronized(lock) { int r = x; }  // ...this (unlock→lock)

// Rule 3: Volatile
volatile boolean flag;
x = 42;        // Happens-before (piggybacking!)
flag = true;   // Volatile write

// In another thread:
if (flag) {    // Volatile read
    assert x == 42;  // GUARANTEED (happens-before chain)
}

// Rule 4: Thread Start
x = 1;              // Happens-before
thread.start();     // Everything before start() visible to new thread

// Rule 5: Thread Join
// In thread: x = 1;
thread.join();      // Everything in thread visible after join returns
assert x == 1;     // GUARANTEED

// Rule 6: Transitivity
// If A happens-before B, and B happens-before C, then A happens-before C

// Rule 7: Interrupt
thread.interrupt(); // Happens-before detection of interrupt

// Rule 8: Finalizer
// Object constructor completes happens-before start of its finalize()
```

---

### Q110: Explain Memory Barriers and their types.

**Answer:**

```
Memory Barriers (Fences) = CPU instructions that prevent reordering

Types:
1. LoadLoad Barrier:  Loads before barrier complete before loads after
2. StoreStore Barrier: Stores before barrier complete before stores after
3. LoadStore Barrier:  Loads before barrier complete before stores after
4. StoreLoad Barrier:  Stores before barrier complete before loads after
   (Most expensive, provides full fence)

Java volatile:
- Volatile Write = StoreStore + StoreLoad barriers AFTER write
  (Flushes all stores to memory, prevents reordering past write)
- Volatile Read = LoadLoad + LoadStore barriers AFTER read
  (Invalidates cache, prevents reordering past read)

// Java 9+ VarHandle fences:
VarHandle.fullFence();       // StoreLoad (all four barriers)
VarHandle.loadLoadFence();   // LoadLoad
VarHandle.storeStoreFence(); // StoreStore
VarHandle.acquireFence();    // LoadLoad + LoadStore (like volatile read)
VarHandle.releaseFence();    // StoreStore + LoadStore (like volatile write)
```

---

### Q111: What is false sharing and how to avoid it?

**Answer:**

```java
// False Sharing: Two threads modify different variables that share the same
// CPU cache line (typically 64 bytes), causing constant cache line invalidation

// BAD: x and y on same cache line (adjacent in memory)
class Counter {
    volatile long x;  // Thread 1 writes this
    volatile long y;  // Thread 2 writes this
    // Both on same 64-byte cache line!
    // When Thread 1 writes x, Thread 2's cache for y is invalidated
    // Even though y didn't change!
}

// GOOD: Padding to separate cache lines
class PaddedCounter {
    volatile long x;
    long p1, p2, p3, p4, p5, p6, p7;  // Padding (7 * 8 = 56 bytes)
    volatile long y;  // Now on different cache line!
}

// Java 8+ annotation (JVM may apply padding):
@jdk.internal.vm.annotation.Contended
class Counter {
    @Contended volatile long x;  // Padded by JVM
    @Contended volatile long y;  // Padded by JVM
}
// Requires: -XX:-RestrictContended

// Real-world example: LongAdder uses @Contended on Cell class
// Each Cell is on its own cache line → no false sharing between cells
```

---

### Q112: Explain the Disruptor pattern (LMAX).

**Answer:**

```
// High-performance inter-thread messaging (alternative to BlockingQueue)
// Used in financial exchanges for ultra-low latency (< 1 microsecond)

Architecture:
┌──────────────────────────────────────────────┐
│              Ring Buffer (pre-allocated)       │
│  [0] [1] [2] [3] [4] [5] [6] [7]           │
│   ↑                               ↑          │
│   Consumer cursor          Producer cursor    │
└──────────────────────────────────────────────┘

Key features:
1. Ring Buffer: Pre-allocated array (no GC!), power-of-2 size
2. Sequence numbers: Atomic counter (not locks)
3. No locks: CAS-based or single-writer
4. Cache-line padding: No false sharing
5. Batch processing: Consumer can process multiple events at once
6. Mechanical sympathy: Designed for CPU cache behavior

// Performance: ~25M messages/sec single thread
// vs ArrayBlockingQueue: ~5M messages/sec
// vs LinkedBlockingQueue: ~3M messages/sec
```

---

### Q113: What are the common causes of OutOfMemoryError?

**Answer:**

```java
// 1. Java heap space - Heap full
// Cause: Too many objects, memory leak, insufficient heap
// Fix: Increase -Xmx, find leak with MAT
java.lang.OutOfMemoryError: Java heap space

// 2. GC Overhead limit exceeded - GC spending >98% time, recovering <2% heap
// Cause: Heap too small, or nearly-live objects filling heap
// Fix: Increase heap, fix leak, disable with -XX:-UseGCOverheadLimit
java.lang.OutOfMemoryError: GC overhead limit exceeded

// 3. Metaspace - Class metadata area full
// Cause: Too many classes loaded (dynamic proxies, reflection, classloader leak)
// Fix: Increase -XX:MaxMetaspaceSize, fix classloader leak
java.lang.OutOfMemoryError: Metaspace

// 4. Unable to create native thread
// Cause: Too many threads (each thread ~1MB stack)
// Fix: Reduce thread count, reduce -Xss, increase OS thread limit (ulimit -u)
java.lang.OutOfMemoryError: unable to create native thread

// 5. Direct buffer memory - NIO buffers exhausted
// Cause: ByteBuffer.allocateDirect() without cleanup
// Fix: Increase -XX:MaxDirectMemorySize, ensure cleanup
java.lang.OutOfMemoryError: Direct buffer memory

// 6. Map failed - Memory-mapped file failure
// Cause: Insufficient virtual address space
java.lang.OutOfMemoryError: Map failed

// 7. Requested array size exceeds VM limit
// Cause: Trying to allocate array larger than Integer.MAX_VALUE - 8
java.lang.OutOfMemoryError: Requested array size exceeds VM limit
```

---

### Q114: What is the difference between process and thread?

**Answer:**

| Feature | Process | Thread |
|---------|---------|--------|
| Memory | Own address space | Shared address space within process |
| Communication | IPC (pipes, sockets, shared memory) | Shared heap, direct method calls |
| Creation cost | High (fork, new address space) | Low (just new stack) |
| Context switch | Expensive (TLB flush, page table swap) | Cheaper (shared address space) |
| Crash isolation | Independent (one crash doesn't affect others) | One crash kills entire process |
| Resources | Own file descriptors, sockets | Shared with other threads |

---

### Q115: Explain thread states and transitions.

**Answer:**

```
                    ┌──────────────────────────────────────────────┐
                    │                                              │
    Thread.start()  │     ┌──────────────┐                        │
NEW ──────────────→│ ─→ │  RUNNABLE     │ (Running or Ready)     │
                    │    │  (Scheduler   │                        │
                    │    │   picks)      │                        │
                    │    └──────┬────────┘                        │
                    │           │                                  │
                    │     ┌─────┼─────────────────────────┐       │
                    │     │     │                         │       │
                    │     ▼     ▼                         ▼       │
                    │ ┌───────┐ ┌──────────────┐ ┌────────────┐  │
                    │ │BLOCKED│ │WAITING       │ │TIMED_WAIT  │  │
                    │ │(lock) │ │(wait/join/   │ │(sleep/wait │  │
                    │ │       │ │ park)        │ │ timeout)   │  │
                    │ └───┬───┘ └──────┬───────┘ └─────┬──────┘  │
                    │     │            │               │          │
                    │     └────────────┴───────────────┘          │
                    │                  │                           │
                    │                  ▼                           │
                    │           ┌────────────┐                    │
                    │           │ TERMINATED │                    │
                    │           └────────────┘                    │
                    └──────────────────────────────────────────────┘
```

---

### Q116: What is the difference between Callable and Runnable?

**Answer:**

```java
// Runnable: no return value, no checked exception
@FunctionalInterface
interface Runnable {
    void run();
}

// Callable: returns value, can throw checked exception
@FunctionalInterface
interface Callable<V> {
    V call() throws Exception;
}

// Usage:
ExecutorService executor = Executors.newFixedThreadPool(4);

// Runnable - fire and forget
executor.execute(() -> doWork());  
Future<?> f = executor.submit(() -> doWork());  // Future<Void>

// Callable - get result
Future<Integer> future = executor.submit(() -> {
    Thread.sleep(1000);
    return 42;
});
int result = future.get();  // Blocks, returns 42
```

---

### Q117: How does the interrupt mechanism work in Java?

**Answer:**

```java
// Interruption is a COOPERATIVE mechanism
// It REQUESTS a thread to stop, doesn't FORCE it

Thread worker = new Thread(() -> {
    while (!Thread.currentThread().isInterrupted()) {
        try {
            // Blocking operations throw InterruptedException
            Thread.sleep(1000);
            doWork();
        } catch (InterruptedException e) {
            // Interrupt flag is CLEARED by catch!
            // Option 1: Re-interrupt and exit
            Thread.currentThread().interrupt();
            break;
            // Option 2: Just exit
            // break;
        }
    }
    // Cleanup code here
});

worker.start();
// ... later ...
worker.interrupt();  // Sets interrupt flag, wakes from sleep/wait/join

// Methods that respond to interruption:
// Thread.sleep(), Object.wait(), Thread.join()
// BlockingQueue.put/take, Lock.lockInterruptibly()
// Channel.read/write, Selector.select()

// IMPORTANT: If your code calls methods that throw InterruptedException,
// you MUST either:
// 1. Propagate it (throws InterruptedException)
// 2. Catch it and re-set interrupt flag: Thread.currentThread().interrupt()
// NEVER silently swallow InterruptedException!
```

---

### Q118: What is ThreadPool rejection and how to handle it?

**Answer:**

```java
// Rejection happens when:
// - Thread pool is shut down, OR
// - All threads are busy AND queue is full

ThreadPoolExecutor executor = new ThreadPoolExecutor(
    5, 10, 60L, TimeUnit.SECONDS,
    new ArrayBlockingQueue<>(100),  // Bounded queue
    new RejectedExecutionHandler() {
        @Override
        public void rejectedExecution(Runnable r, ThreadPoolExecutor executor) {
            // Custom handling options:
            
            // Option 1: Log and discard
            log.warn("Task rejected: {}", r);
            
            // Option 2: Block caller until space available (backpressure)
            try {
                executor.getQueue().put(r);  // Blocks until queue has space
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            }
            
            // Option 3: Run in caller's thread (backpressure)
            if (!executor.isShutdown()) {
                r.run();
            }
            
            // Option 4: Throw (default AbortPolicy behavior)
            throw new RejectedExecutionException("Queue full");
        }
    }
);

// Built-in policies:
// AbortPolicy: throw RejectedExecutionException (default)
// CallerRunsPolicy: run task in submitter's thread (natural backpressure!)
// DiscardPolicy: silently drop task
// DiscardOldestPolicy: drop oldest queued task, retry
```

---

### Q119: Explain ConcurrentLinkedQueue and ConcurrentLinkedDeque.

**Answer:**

```java
// ConcurrentLinkedQueue: Lock-free, non-blocking, unbounded FIFO queue
// Based on Michael & Scott algorithm (CAS-based)
ConcurrentLinkedQueue<Task> queue = new ConcurrentLinkedQueue<>();
queue.offer(task);     // Never blocks or fails (unbounded)
Task t = queue.poll(); // Returns null if empty (never blocks)
Task t = queue.peek(); // Returns null if empty

// Internal: Linked nodes with CAS-updated pointers
// No locks at all! Pure CAS (Compare-And-Swap) operations
// Wait-free for producers, lock-free for consumers

// ConcurrentLinkedDeque: Lock-free, non-blocking, unbounded double-ended queue
ConcurrentLinkedDeque<Task> deque = new ConcurrentLinkedDeque<>();
deque.offerFirst(task);  // Add to front
deque.offerLast(task);   // Add to back
deque.pollFirst();       // Remove from front
deque.pollLast();        // Remove from back

// When to use vs BlockingQueue:
// ConcurrentLinkedQueue: Non-blocking preferred, polling-based consumers
// BlockingQueue: Need blocking wait semantics (take/put)
```

---

### Q120: What is a Memory-Mapped File and when to use it?

**Answer:**

```java
// Memory-mapped file: Maps a file directly into virtual memory
// OS handles paging (lazy loading, writing back)
// Extremely fast for random access on large files

RandomAccessFile file = new RandomAccessFile("large.dat", "rw");
FileChannel channel = file.getChannel();

// Map entire file (or portion) into memory
MappedByteBuffer buffer = channel.map(
    FileChannel.MapMode.READ_WRITE,  // READ_ONLY, READ_WRITE, PRIVATE
    0,                                // Offset
    channel.size()                    // Length
);

// Direct memory access (no system calls for read/write!)
buffer.putInt(0, 42);        // Write at position 0
int value = buffer.getInt(0); // Read from position 0
buffer.force();               // Flush changes to disk

// Use cases:
// - Large file random access (databases, indexes)
// - Inter-process communication (shared memory)
// - Zero-copy file access
// - Files larger than heap memory (virtual memory handles paging)

// Caveats:
// - Unmapping is tricky (no public API until Java 19+)
// - File size limited to ~2GB per mapping (MappedByteBuffer uses int position)
// - Memory usage not tracked by JVM heap metrics
```

---

### Q121: Explain weak, soft, and phantom references with real use cases.

**Answer:**

```java
// SOFT REFERENCE: Collected only when JVM needs memory
// Perfect for: Memory-sensitive caches
class ImageCache {
    private final Map<String, SoftReference<BufferedImage>> cache = new HashMap<>();
    
    BufferedImage getImage(String path) {
        SoftReference<BufferedImage> ref = cache.get(path);
        BufferedImage img = (ref != null) ? ref.get() : null;
        if (img == null) {
            img = loadImage(path);
            cache.put(path, new SoftReference<>(img));
        }
        return img;
    }
}
// Images stay cached as long as memory is available
// Automatically evicted when GC needs space (before OOM)

// WEAK REFERENCE: Collected at next GC regardless of memory
// Perfect for: Canonicalized mappings, metadata without preventing GC
// WeakHashMap: entries removed when KEY is collected
Map<Socket, Metadata> socketMetadata = new WeakHashMap<>();
// When Socket is closed and GC'd, its metadata is automatically removed

// PHANTOM REFERENCE: Enqueued AFTER finalization, before memory reclaim
// Perfect for: Cleanup actions (native memory, file handles)
class NativeResource {
    private static final ReferenceQueue<NativeResource> queue = new ReferenceQueue<>();
    private static final Set<CleanupRef> refs = ConcurrentHashMap.newKeySet();
    
    static class CleanupRef extends PhantomReference<NativeResource> {
        final long nativePointer;
        CleanupRef(NativeResource obj, long ptr) {
            super(obj, queue);
            this.nativePointer = ptr;
        }
    }
    
    // Cleanup thread
    static {
        Thread cleaner = new Thread(() -> {
            while (true) {
                CleanupRef ref = (CleanupRef) queue.remove();  // Blocks
                freeNativeMemory(ref.nativePointer);  // Cleanup!
                refs.remove(ref);
            }
        });
        cleaner.setDaemon(true);
        cleaner.start();
    }
}

// Java 9+ Cleaner API (official replacement for finalize()):
Cleaner cleaner = Cleaner.create();
class MyResource implements AutoCloseable {
    private final Cleaner.Cleanable cleanable;
    private final long nativePtr;
    
    MyResource() {
        this.nativePtr = allocateNative();
        this.cleanable = cleaner.register(this, () -> freeNative(nativePtr));
    }
    
    @Override
    public void close() {
        cleanable.clean();  // Explicit cleanup
    }
    // If close() not called, Cleaner triggers cleanup via phantom reference
}
```

---

### Q122: What are Java Agents and Instrumentation?

**Answer:**

```java
// Java Agent: Code that runs before main() or attaches to running JVM
// Uses: Profiling, monitoring, AOP, bytecode manipulation

// premain agent (loaded at JVM start with -javaagent):
public class MyAgent {
    public static void premain(String args, Instrumentation inst) {
        inst.addTransformer(new ClassFileTransformer() {
            @Override
            public byte[] transform(ClassLoader loader, String className,
                    Class<?> classBeingRedefined, ProtectionDomain domain, 
                    byte[] classfileBuffer) {
                // Modify bytecode before class is loaded!
                if (className.equals("com/myapp/Service")) {
                    return addTimingToMethods(classfileBuffer);
                }
                return null;  // No modification
            }
        });
    }
}

// MANIFEST.MF:
// Premain-Class: com.myagent.MyAgent
// Can-Retransform-Classes: true

// Launch: java -javaagent:myagent.jar -jar myapp.jar

// agentmain (attach to running JVM):
public static void agentmain(String args, Instrumentation inst) {
    // Same capabilities, but attached to running process
    inst.retransformClasses(TargetClass.class);  // Redefine loaded class!
}

// Real-world uses:
// - APM tools (New Relic, Datadog, AppDynamics)
// - Debugging tools (IntelliJ debugger)
// - Mocking frameworks (Mockito inline mocks)
// - Code coverage (JaCoCo)
// - Profilers (async-profiler)
```

---

### Q123: Explain the difference between deep copy and shallow copy.

**Answer:**

```java
// Shallow Copy: Copies object references (shared nested objects)
class Address { String city; }
class Person implements Cloneable {
    String name;
    Address address;
    
    @Override
    protected Person clone() throws CloneNotSupportedException {
        return (Person) super.clone();  // SHALLOW: address shared!
    }
}

Person p1 = new Person("John", new Address("NYC"));
Person p2 = p1.clone();
p2.address.city = "LA";
System.out.println(p1.address.city);  // "LA" ← p1 affected! (shared reference)

// Deep Copy: Copies everything recursively
class Person implements Cloneable {
    String name;
    Address address;
    
    @Override
    protected Person clone() throws CloneNotSupportedException {
        Person copy = (Person) super.clone();
        copy.address = new Address(this.address.city);  // Deep copy nested
        return copy;
    }
}

// Deep copy strategies:
// 1. Manual clone (above)
// 2. Copy constructor: new Person(original)
// 3. Serialization (slow but handles complex graphs)
// 4. Jackson: objectMapper.readValue(objectMapper.writeValueAsString(obj), Person.class)
```

---

### Q124: What are Annotations and how to create custom ones?

**Answer:**

```java
// Custom annotation definition
@Target({ElementType.METHOD, ElementType.TYPE})  // Where it can be used
@Retention(RetentionPolicy.RUNTIME)              // Available at runtime (reflection)
@Documented                                       // Included in Javadoc
@Inherited                                        // Subclasses inherit it
public @interface Cacheable {
    String key() default "";
    int ttlSeconds() default 300;
    boolean async() default false;
}

// Usage
@Cacheable(key = "users", ttlSeconds = 600)
public List<User> getUsers() { ... }

// Processing at runtime (reflection)
Method method = clazz.getMethod("getUsers");
if (method.isAnnotationPresent(Cacheable.class)) {
    Cacheable ann = method.getAnnotation(Cacheable.class);
    String key = ann.key();        // "users"
    int ttl = ann.ttlSeconds();    // 600
}

// Meta-annotations:
// @Target: TYPE, METHOD, FIELD, PARAMETER, CONSTRUCTOR, LOCAL_VARIABLE, ANNOTATION_TYPE, PACKAGE, TYPE_PARAMETER, TYPE_USE
// @Retention: SOURCE (compile-time only), CLASS (in .class file), RUNTIME (reflection)
// @Documented: Include in Javadoc
// @Inherited: Annotation inherited by subclasses
// @Repeatable: Can be applied multiple times
```

---

### Q125: What are the best practices for Exception Handling?

**Answer:**

```java
// 1. Use specific exceptions
catch (FileNotFoundException e) { /* handle specifically */ }
// NOT: catch (Exception e) { /* too broad */ }

// 2. Never swallow exceptions
catch (Exception e) { 
    // BAD: empty catch block
}
// GOOD:
catch (Exception e) {
    log.error("Operation failed", e);
    throw new ServiceException("Could not process", e);  // Wrap and rethrow
}

// 3. Use try-with-resources (Java 7+)
try (Connection conn = dataSource.getConnection();
     PreparedStatement ps = conn.prepareStatement(sql)) {
    // Auto-closed in reverse order, even on exception
}

// 4. Don't use exceptions for flow control
// BAD:
try {
    int value = Integer.parseInt(input);
} catch (NumberFormatException e) {
    // Using exception as if-else
}
// GOOD:
if (isNumeric(input)) {
    int value = Integer.parseInt(input);
}

// 5. Preserve the cause chain
catch (SQLException e) {
    throw new DataAccessException("Query failed: " + sql, e);  // Include cause!
}

// 6. Clean up resources in finally (or try-with-resources)
Lock lock = new ReentrantLock();
lock.lock();
try {
    // critical section
} finally {
    lock.unlock();  // ALWAYS release lock
}

// 7. Throw early, catch late
void processFile(String path) {
    if (path == null) throw new IllegalArgumentException("path cannot be null");
    // Don't wait until NPE deep in the stack
}

// 8. Use custom exception hierarchy
class BaseException extends RuntimeException { /* error code, context */ }
class ValidationException extends BaseException { /* field, constraint */ }
class NotFoundException extends BaseException { /* entity type, id */ }
```

---


## 13. More Critical Interview Questions (Q126-Q200+)

### Q126: What is the difference between final, finally, and finalize()?

**Answer:**

```java
// final: keyword for immutability/restriction
final int x = 10;              // Variable: cannot reassign
final class Immutable { }      // Class: cannot extend
final void process() { }       // Method: cannot override

// finally: exception handling block (always executes)
try {
    riskyOperation();
} catch (Exception e) {
    handleError(e);
} finally {
    cleanup();  // ALWAYS runs (even if return/throw in try/catch)
    // Exception: System.exit(), JVM crash, infinite loop in try
}

// finalize(): GC callback before collection (DEPRECATED since Java 9)
@Override
protected void finalize() throws Throwable {
    // Called by GC before collecting object
    // PROBLEMS:
    // 1. Non-deterministic (no guarantee when/if called)
    // 2. Performance penalty (objects take 2 GC cycles to collect)
    // 3. Can resurrect object (assign 'this' to static field)
    // 4. No ordering guarantee
    // USE INSTEAD: try-with-resources, Cleaner API, PhantomReference
}
```

---

### Q127: Explain immutability in Java - how to create immutable class?

**Answer:**

```java
// Rules for Immutable Class:
// 1. Class is final (no subclass can break immutability)
// 2. All fields are private and final
// 3. No setters
// 4. Deep copy mutable fields in constructor and getters
// 5. No methods that modify state

public final class ImmutablePerson {
    private final String name;
    private final int age;
    private final List<String> hobbies;
    private final Date birthDate;
    
    public ImmutablePerson(String name, int age, List<String> hobbies, Date birthDate) {
        this.name = name;
        this.age = age;
        this.hobbies = Collections.unmodifiableList(new ArrayList<>(hobbies));  // Deep copy!
        this.birthDate = new Date(birthDate.getTime());  // Defensive copy!
    }
    
    public String getName() { return name; }  // String is immutable, safe
    public int getAge() { return age; }       // Primitive, safe
    
    public List<String> getHobbies() { 
        return hobbies;  // Already unmodifiable
    }
    
    public Date getBirthDate() { 
        return new Date(birthDate.getTime());  // Return copy! Date is mutable
    }
}

// Java 16+ Records are immutable by design:
public record Person(String name, int age, List<String> hobbies) {
    public Person {
        hobbies = List.copyOf(hobbies);  // Unmodifiable copy in compact constructor
    }
}
```

---

### Q128: What is type casting in Java? Upcasting vs Downcasting?

**Answer:**

```java
// Upcasting: Child → Parent (always safe, implicit)
Dog dog = new Dog();
Animal animal = dog;  // Implicit upcast (safe - Dog IS an Animal)

// Downcasting: Parent → Child (may fail, explicit cast required)
Animal animal = new Dog();
Dog dog = (Dog) animal;  // Explicit downcast (works - runtime type is Dog)
Cat cat = (Cat) animal;  // ClassCastException! (runtime type is Dog, not Cat)

// Safe downcasting with instanceof:
if (animal instanceof Dog d) {  // Java 16+ pattern matching
    d.bark();  // d already cast
}

// Generics and casting:
List<Object> objects = new ArrayList<>();
// List<String> strings = (List<String>) objects;  // Unchecked warning!
// At runtime, both are just List (type erasure), no actual check
```

---

### Q129: What is the Diamond Problem and how does Java solve it?

**Answer:**

```java
// Diamond Problem: Ambiguity when a class inherits from two sources 
// that have the same method

// Java PREVENTS diamond problem with classes (single inheritance)
// But interfaces can cause it with default methods:

interface A {
    default void hello() { System.out.println("A"); }
}
interface B extends A {
    default void hello() { System.out.println("B"); }
}
interface C extends A {
    default void hello() { System.out.println("C"); }
}

// Class implementing both B and C:
class D implements B, C {
    @Override
    public void hello() {
        B.super.hello();  // Must explicitly choose (or provide own impl)
    }
}

// Resolution rules:
// 1. Class methods win over interface default methods
// 2. More specific interface wins (sub-interface over super-interface)
// 3. If still ambiguous → compile error, must override
```

---

### Q130: Explain the Object class methods in detail.

**Answer:**

```java
public class Object {
    // Identity hash code (memory address-based, not overridable)
    public native int hashCode();
    
    // Reference equality by default (override for value equality)
    public boolean equals(Object obj) { return (this == obj); }
    
    // Class name + @ + hex hashCode (override for meaningful output)
    public String toString() { return getClass().getName() + "@" + Integer.toHexString(hashCode()); }
    
    // Returns runtime class
    public final native Class<?> getClass();
    
    // Thread communication (must hold monitor)
    public final void wait() throws InterruptedException;
    public final void wait(long timeoutMillis) throws InterruptedException;
    public final native void notify();     // Wake one waiting thread
    public final native void notifyAll();  // Wake all waiting threads
    
    // Shallow copy (must implement Cloneable)
    protected native Object clone() throws CloneNotSupportedException;
    
    // Called by GC before collection (DEPRECATED)
    protected void finalize() throws Throwable { }
}
```

---

### Q131: What is Covariant Return Type?

**Answer:**

```java
// Overriding method can return a more specific type than parent's return type

class Animal {
    Animal create() { return new Animal(); }
}

class Dog extends Animal {
    @Override
    Dog create() { return new Dog(); }  // Returns Dog (subtype of Animal) - VALID!
}

// Works with clone():
class MyClass implements Cloneable {
    @Override
    public MyClass clone() {  // Returns MyClass, not Object
        return (MyClass) super.clone();
    }
}
```

---

### Q132: Explain ConcurrentSkipListMap and ConcurrentSkipListSet.

**Answer:**

```java
// ConcurrentSkipListMap: Thread-safe sorted map (like TreeMap but concurrent)
// Based on Skip List data structure (probabilistic balancing)

ConcurrentSkipListMap<String, Integer> map = new ConcurrentSkipListMap<>();
map.put("banana", 2);
map.put("apple", 5);
map.put("cherry", 3);

// Sorted operations (all thread-safe!):
map.firstKey();              // "apple"
map.lastKey();               // "cherry"
map.headMap("cherry");       // {apple=5, banana=2}
map.tailMap("banana");       // {banana=2, cherry=3}
map.subMap("apple", "cherry"); // {apple=5, banana=2}

// Skip List Structure:
// Level 3: head ──────────────────────────── cherry ── nil
// Level 2: head ────── apple ─────────────── cherry ── nil
// Level 1: head ────── apple ── banana ───── cherry ── nil
// Level 0: head ────── apple ── banana ───── cherry ── nil

// Properties:
// - O(log n) average for get/put/remove
// - Lock-free reads (CAS-based updates)
// - Sorted iteration (unlike ConcurrentHashMap)
// - No need for rebalancing (probabilistic, not deterministic)
// - Range queries efficient

// Use when you need:
// - Thread-safe sorted map
// - Range queries (subMap, headMap, tailMap)
// - NavigableMap operations (floorKey, ceilingKey, etc.)
```

---

### Q133: What is the difference between sleep(), wait(), and yield()?

**Answer:**

| Feature | sleep(ms) | wait() | yield() |
|---------|-----------|--------|---------|
| Class | Thread | Object | Thread |
| Lock release | NO (holds lock) | YES (releases monitor) | NO |
| Wake up | After timeout | notify()/notifyAll()/timeout | Scheduler decision |
| Must hold lock | No | Yes (must be in synchronized) | No |
| Purpose | Pause thread | Inter-thread communication | Hint to scheduler |
| Throws | InterruptedException | InterruptedException | Nothing |

```java
// sleep: "I don't need CPU for this duration"
Thread.sleep(1000);  // Pauses, KEEPS all locks

// wait: "I'm waiting for a condition, others can use the lock"
synchronized (obj) {
    while (!condition) {
        obj.wait();  // RELEASES obj's monitor, waits for notify
    }
}

// yield: "I'm willing to give up CPU, but scheduler may ignore"
Thread.yield();  // Hint only, may have no effect
// Rarely used in practice
```

---

### Q134: Explain Java's type system - Primitives vs Wrappers.

**Answer:**

| Primitive | Wrapper | Size | Default | Range |
|-----------|---------|------|---------|-------|
| byte | Byte | 8 bit | 0 | -128 to 127 |
| short | Short | 16 bit | 0 | -32,768 to 32,767 |
| int | Integer | 32 bit | 0 | -2^31 to 2^31 -1 |
| long | Long | 64 bit | 0L | -2^63 to 2^63 -1 |
| float | Float | 32 bit | 0.0f | ±3.4 × 10^38 |
| double | Double | 64 bit | 0.0d | ±1.8 × 10^308 |
| char | Character | 16 bit | '\u0000' | 0 to 65,535 |
| boolean | Boolean | JVM specific | false | true/false |

```java
// Wrappers needed for:
// 1. Collections (cannot store primitives): List<Integer>
// 2. Generics: Optional<Integer>
// 3. Null representation
// 4. Object methods (toString, equals)

// Memory difference:
// int: 4 bytes
// Integer: 16 bytes (12 byte header + 4 byte int value)
// In array: int[1000] = ~4KB; Integer[1000] = ~16KB + 1000 * 16 = ~20KB
```

---

### Q135: What is try-with-resources and how does it work internally?

**Answer:**

```java
// Any class implementing AutoCloseable can be used
try (FileInputStream fis = new FileInputStream("file.txt");
     BufferedReader br = new BufferedReader(new InputStreamReader(fis))) {
    String line = br.readLine();
}
// br.close() called first, then fis.close() (reverse order!)
// Even if readLine() throws, both are closed

// Compiler transforms to:
FileInputStream fis = new FileInputStream("file.txt");
Throwable primaryException = null;
try {
    BufferedReader br = new BufferedReader(new InputStreamReader(fis));
    Throwable primaryException2 = null;
    try {
        String line = br.readLine();
    } catch (Throwable t) {
        primaryException2 = t;
        throw t;
    } finally {
        if (br != null) {
            if (primaryException2 != null) {
                try { br.close(); } 
                catch (Throwable suppressed) {
                    primaryException2.addSuppressed(suppressed);  // Suppressed!
                }
            } else {
                br.close();
            }
        }
    }
} catch (Throwable t) {
    primaryException = t;
    throw t;
} finally {
    // Same pattern for fis
}

// Suppressed exceptions:
try (Resource r = new Resource()) {
    throw new RuntimeException("primary");
    // r.close() also throws → that exception is SUPPRESSED
} catch (RuntimeException e) {
    Throwable[] suppressed = e.getSuppressed();  // Contains close exception
}

// Java 9+: effectively-final variables in try-with-resources
FileInputStream fis = new FileInputStream("file.txt");
try (fis) {  // No need to redeclare!
    // use fis
}
```

---

### Q136: What is the difference between Comparable and Comparator? When to use each?

**Answer:**

```java
// Comparable: Natural ordering (class implements it)
class Employee implements Comparable<Employee> {
    private int id;
    private String name;
    private double salary;
    
    @Override
    public int compareTo(Employee other) {
        return Integer.compare(this.id, other.id);  // Natural order: by ID
    }
}

// One class can have ONLY ONE natural ordering (Comparable)
// For multiple orderings, use Comparator

// Comparator: External, multiple strategies (Java 8+ functional)
Comparator<Employee> byName = Comparator.comparing(Employee::getName);
Comparator<Employee> bySalaryDesc = Comparator.comparingDouble(Employee::getSalary).reversed();
Comparator<Employee> complex = Comparator
    .comparing(Employee::getDepartment)
    .thenComparing(Employee::getName)
    .thenComparingDouble(Employee::getSalary);

// Null-safe comparators:
Comparator<Employee> nullSafe = Comparator.nullsLast(
    Comparator.comparing(Employee::getName, Comparator.nullsFirst(Comparator.naturalOrder()))
);

// Sorting:
Collections.sort(list);                    // Uses Comparable
Collections.sort(list, bySalaryDesc);      // Uses Comparator
list.sort(byName);                         // List.sort (Java 8+)
list.stream().sorted(complex).collect(...); // Stream sorted
```

---

### Q137: What is the Java Memory Model guarantee for final fields?

**Answer:**

```java
// Final fields have special memory semantics:
// Once constructor completes, final fields are GUARANTEED visible to all threads
// WITHOUT synchronization!

class SafePublication {
    private final int x;
    private final List<String> items;
    
    SafePublication() {
        x = 42;
        items = List.of("a", "b", "c");
        // After constructor completes, ALL threads see x=42 and items correctly
        // This is a JMM guarantee for final fields!
    }
}

// HOWEVER:
// 1. 'this' must NOT escape during construction
class Unsafe {
    final int x;
    Unsafe() {
        listeners.add(this);  // BAD! 'this' escapes before constructor done
        x = 42;              // Other threads via listener may see x=0!
    }
}

// 2. Only the object referenced by final field is safely published
class Container {
    final List<String> list;
    Container() {
        list = new ArrayList<>();
        list.add("hello");
        // After constructor: list reference AND "hello" are visible
    }
}
// But if you modify list AFTER construction without sync → no guarantee
```

---

### Q138: Explain varargs, and its interaction with generics.

**Answer:**

```java
// Varargs: variable-length argument list
void process(String... args) {
    // args is actually String[] internally
    for (String arg : args) { }
}
process("a", "b", "c");  // Compiler creates new String[]{"a","b","c"}
process();                // Empty array

// Generics + Varargs = Heap Pollution Warning
@SafeVarargs  // Suppress warning (only if truly safe!)
static <T> List<T> asList(T... elements) {
    return Arrays.asList(elements);
}

// Why the warning?
static <T> T[] toArray(T... args) {
    return args;  // UNSAFE! Runtime type of args is Object[]
}
String[] result = toArray("a", "b");  // ClassCastException!
// Because: toArray receives Object[] (erasure), not String[]

// @SafeVarargs rules:
// Can only be used on:
// - static methods
// - final methods
// - private methods (Java 9+)
// - constructors
// Developer asserts: "I don't do anything unsafe with the varargs array"
```

---

### Q139: What is the Executor Framework hierarchy?

**Answer:**

```java
// Interface hierarchy:
Executor                    // execute(Runnable)
└── ExecutorService         // submit(), shutdown(), invokeAll()
    └── ScheduledExecutorService  // schedule(), scheduleAtFixedRate()

// Implementation hierarchy:
ThreadPoolExecutor          // Core thread pool implementation
└── ScheduledThreadPoolExecutor  // Adds scheduling capability
ForkJoinPool               // Work-stealing pool for divide-and-conquer

// Factory (Executors class):
Executors.newFixedThreadPool(n)       // ThreadPoolExecutor(n, n, 0, LinkedBlockingQueue)
Executors.newCachedThreadPool()       // ThreadPoolExecutor(0, MAX, 60s, SynchronousQueue)
Executors.newSingleThreadExecutor()   // ThreadPoolExecutor(1, 1, 0, LinkedBlockingQueue)
Executors.newScheduledThreadPool(n)   // ScheduledThreadPoolExecutor(n)
Executors.newWorkStealingPool(n)      // ForkJoinPool(n)
Executors.newVirtualThreadPerTaskExecutor() // Java 21+

// IMPORTANT: Why NOT to use Executors factory methods in production:
// 1. newFixedThreadPool → LinkedBlockingQueue is UNBOUNDED → OOM possible
// 2. newCachedThreadPool → MAX_VALUE threads → thread exhaustion
// 3. No custom rejection handler, thread naming, etc.
// ALWAYS use ThreadPoolExecutor constructor directly in production!
```

---

### Q140: Explain the happens-before guarantees of concurrent collections.

**Answer:**

```java
// ConcurrentHashMap:
// - Actions in a thread prior to placing an object as key/value
//   happen-before actions subsequent to the access/removal of that
//   object from the map in another thread.
map.put("key", value);    // Thread 1: all preceding actions visible
String v = map.get("key"); // Thread 2: sees all actions before put

// BlockingQueue:
// - put() happens-before take() that retrieves the same element
queue.put(item);   // Thread 1
Item i = queue.take(); // Thread 2: sees all actions before put()

// CopyOnWriteArrayList:
// - Modification (add/set/remove) happens-before subsequent iteration
list.add(item);    // Thread 1
for (String s : list) { }  // Thread 2: sees the added item (if iterator created after)

// These guarantees mean: You DON'T need additional synchronization
// when using these collections for their intended purpose!
```

---

### Q141: What is the difference between submit() and execute() in ExecutorService?

**Answer:**

```java
// execute(Runnable): Fire-and-forget, no return value
executor.execute(() -> doWork());
// - Returns void
// - Uncaught exception: handled by UncaughtExceptionHandler
// - Cannot cancel or check completion

// submit(Callable/Runnable): Returns Future for tracking
Future<Integer> future = executor.submit(() -> computeResult());
Future<?> future2 = executor.submit(() -> doWork());  // Future<Void>
// - Returns Future
// - Exception captured in Future (thrown on get())
// - Can cancel, check isDone(), get result

// CRITICAL difference for exceptions:
executor.execute(() -> { throw new RuntimeException("error"); });
// → UncaughtExceptionHandler invoked (or printed to stderr)

Future<?> f = executor.submit(() -> { throw new RuntimeException("error"); });
// → Exception SILENTLY captured! Only thrown when f.get() is called
try {
    f.get();
} catch (ExecutionException e) {
    Throwable cause = e.getCause();  // The RuntimeException
}
```

---

### Q142: How does invokeAll() vs invokeAny() work?

**Answer:**

```java
List<Callable<String>> tasks = List.of(
    () -> fetchFromServer1(),
    () -> fetchFromServer2(),
    () -> fetchFromServer3()
);

// invokeAll: Execute ALL tasks, wait for ALL to complete
List<Future<String>> futures = executor.invokeAll(tasks);
// Returns when ALL tasks are done (completed or failed)
// Results in same order as input tasks
for (Future<String> f : futures) {
    String result = f.get();  // Already complete, won't block
}

// invokeAll with timeout:
List<Future<String>> futures = executor.invokeAll(tasks, 5, TimeUnit.SECONDS);
// Incomplete tasks are CANCELLED after timeout

// invokeAny: Execute all, return FIRST successful result
String fastest = executor.invokeAny(tasks);
// Returns when FIRST task completes successfully
// Other tasks are CANCELLED
// If ALL fail → throws ExecutionException

// invokeAny with timeout:
String result = executor.invokeAny(tasks, 5, TimeUnit.SECONDS);
// TimeoutException if no task completes in time
```

---

### Q143: Explain Java Memory Leak detection step by step.

**Answer:**

```bash
# STEP 1: Confirm memory growth
# Monitor heap usage over time (every 5 seconds)
jstat -gcutil <pid> 5000

# Look for: Old Gen (O column) growing after Full GC
# Healthy: O stabilizes after Full GC
# Leak: O keeps growing, more frequent Full GCs

# STEP 2: Identify the growing objects
# Take histogram at time T1
jmap -histo:live <pid> > histo_t1.txt

# Wait some time, take another
jmap -histo:live <pid> > histo_t2.txt

# Compare: which classes have growing instance counts?
diff histo_t1.txt histo_t2.txt

# STEP 3: Take heap dumps at two different times
jcmd <pid> GC.heap_dump /tmp/dump1.hprof
# Wait for memory to grow more
jcmd <pid> GC.heap_dump /tmp/dump2.hprof

# STEP 4: Analyze with Eclipse MAT
# Open dump2.hprof in MAT
# Run "Leak Suspects" report
# Check "Dominator Tree" for largest retained objects
# Use "Path to GC Roots" (exclude weak references) to find WHY objects are retained

# STEP 5: Common fixes based on findings
# - Static collection growing → add size limit or TTL
# - ThreadLocal not cleaned → add finally { threadLocal.remove(); }
# - Listener registration without deregistration → add cleanup
# - ClassLoader leak → fix class unloading
# - Connection/Stream not closed → add try-with-resources
```

---

### Q144: How does HashMap handle high-concurrency key insertion at the same bucket?

**Answer:**

```java
// HashMap (NOT thread-safe):
// Two threads inserting at same bucket simultaneously:
// Thread A: reads bucket[5] → sees Node(K1,V1) → next=null
// Thread B: reads bucket[5] → sees Node(K1,V1) → next=null
// Thread A: creates Node(K2,V2), sets Node(K1,V1).next = Node(K2,V2)
// Thread B: creates Node(K3,V3), sets Node(K1,V1).next = Node(K3,V3)
// RESULT: Node(K2,V2) is LOST! Only K3 linked.

// ConcurrentHashMap (thread-safe):
// Empty bucket → CAS (lock-free, only one thread wins)
// Non-empty bucket → synchronized(firstNode) {
//     Only ONE thread modifies the chain at a time
//     Other threads accessing DIFFERENT buckets are NOT blocked
// }

// In Java 8 ConcurrentHashMap:
if ((f = tabAt(tab, i = (n - 1) & hash)) == null) {
    if (casTabAt(tab, i, null, new Node<>(hash, key, value)))
        break;  // CAS success → inserted without lock!
} else {
    synchronized (f) {  // Lock on first node of this bucket
        // Traverse chain, insert/update
    }
}
```

---

### Q145: What is a Stamped Lock and how does optimistic locking work?

**Answer:**

```java
// StampedLock provides three modes:
// 1. Write Lock (exclusive)
// 2. Read Lock (shared)
// 3. Optimistic Read (no lock at all!)

StampedLock lock = new StampedLock();

// Optimistic Read Pattern:
double computeDistance() {
    // Phase 1: Optimistic read (NO LOCK! Zero overhead)
    long stamp = lock.tryOptimisticRead();
    double currentX = x;
    double currentY = y;
    
    // Phase 2: Validate (check if write occurred during read)
    if (!lock.validate(stamp)) {
        // A write happened! Fall back to pessimistic read lock
        stamp = lock.readLock();
        try {
            currentX = x;
            currentY = y;
        } finally {
            lock.unlockRead(stamp);
        }
    }
    
    // Phase 3: Use the data (outside any lock)
    return Math.sqrt(currentX * currentX + currentY * currentY);
}

// When optimistic read works well:
// - Reads are MUCH more frequent than writes
// - Read operation is fast (small window for write to interfere)
// - Can tolerate occasional fallback to read lock

// Performance hierarchy (best to worst for read-heavy):
// 1. Optimistic read (no lock, no CAS) - best!
// 2. Read lock (shared, allows concurrent readers)
// 3. synchronized (exclusive, even for reads)
```

---

### Q146: Explain the fork/join parallelism level and common pool configuration.

**Answer:**

```java
// Common pool configuration:
// Default parallelism = Runtime.getRuntime().availableProcessors() - 1

// Configure via system properties:
// -Djava.util.concurrent.ForkJoinPool.common.parallelism=16
// -Djava.util.concurrent.ForkJoinPool.common.threadFactory=...
// -Djava.util.concurrent.ForkJoinPool.common.exceptionHandler=...

// IMPORTANT: The common pool is shared across:
// - Parallel Streams
// - CompletableFuture (default executor)
// - Arrays.parallelSort()
// - Any ForkJoinPool.commonPool() usage

// PROBLEM: I/O task in parallel stream can STARVE other users of common pool!
list.parallelStream().map(item -> {
    return httpClient.get(item.getUrl());  // BLOCKS carrier thread!
    // Other parallel streams in the JVM cannot proceed
}).collect(Collectors.toList());

// SOLUTION 1: Use custom pool for I/O tasks
ForkJoinPool customPool = new ForkJoinPool(32);
List<Result> results = customPool.submit(() ->
    list.parallelStream().map(item -> httpClient.get(item.getUrl()))
        .collect(Collectors.toList())
).get();
customPool.shutdown();

// SOLUTION 2: Use CompletableFuture with custom executor
ExecutorService ioPool = Executors.newFixedThreadPool(32);
List<CompletableFuture<Result>> futures = list.stream()
    .map(item -> CompletableFuture.supplyAsync(
        () -> httpClient.get(item.getUrl()), ioPool))
    .collect(Collectors.toList());
List<Result> results = futures.stream()
    .map(CompletableFuture::join)
    .collect(Collectors.toList());

// SOLUTION 3 (Java 21): Virtual Threads - best for I/O!
try (var executor = Executors.newVirtualThreadPerTaskExecutor()) {
    List<Future<Result>> futures = list.stream()
        .map(item -> executor.submit(() -> httpClient.get(item.getUrl())))
        .toList();
}
```

---

### Q147: What is the difference between Runnable, Callable, and Supplier?

**Answer:**

```java
// Runnable: No input, no output, no checked exception
@FunctionalInterface
interface Runnable { void run(); }
// Use: Thread tasks, fire-and-forget
new Thread(() -> doWork()).start();
executor.execute(() -> doWork());

// Callable: No input, returns output, can throw checked exception
@FunctionalInterface
interface Callable<V> { V call() throws Exception; }
// Use: Tasks that produce a result, used with ExecutorService
Future<Integer> f = executor.submit(() -> computeResult());

// Supplier: No input, returns output, NO checked exception
@FunctionalInterface
interface Supplier<T> { T get(); }
// Use: Lazy value generation, factory, Optional.orElseGet()
Optional<String> opt = Optional.empty();
String value = opt.orElseGet(() -> expensiveComputation());
CompletableFuture.supplyAsync(() -> fetchData());

// Key differences:
// Runnable: execute() accepts it, no return
// Callable: submit() accepts it, returns Future
// Supplier: CompletableFuture.supplyAsync() accepts it, functional composition
```

---

### Q148: Explain ThreadGroup and why it's considered obsolete.

**Answer:**

```java
// ThreadGroup: Logical grouping of threads (hierarchical)
ThreadGroup group = new ThreadGroup("workers");
Thread t1 = new Thread(group, () -> doWork(), "worker-1");

// Mostly obsolete because:
// 1. ThreadGroup.stop() is deprecated (unsafe, can leave inconsistent state)
// 2. interrupt() on group interrupts ALL threads (coarse-grained)
// 3. uncaughtException handling → use Thread.setDefaultUncaughtExceptionHandler instead
// 4. No useful concurrency control → use ExecutorService instead
// 5. Priority management → doesn't work reliably across platforms

// Modern alternatives:
// - ExecutorService: Thread lifecycle management
// - ThreadFactory: Thread creation customization  
// - UncaughtExceptionHandler: Exception handling
// - Virtual Threads (Java 21): Lightweight thread management
```

---

### Q149: What is object finalization and why is it bad?

**Answer:**

```java
// finalize() problems:
// 1. Non-deterministic: No guarantee WHEN it's called (or IF ever!)
// 2. Performance: Objects with finalize() need 2 GC cycles to collect
//    (first GC → put on finalization queue → finalizer thread runs → second GC collects)
// 3. Resurrection: finalize() can make object reachable again!
// 4. Exception swallowing: Exceptions in finalize() are silently ignored
// 5. Security: Attacker can extend your class, override finalize(),
//    and revive partially-constructed objects
// 6. Thread unsafety: Finalizer runs in different thread

// REPLACEMENTS:
// 1. try-with-resources (AutoCloseable)
try (Connection conn = pool.getConnection()) {
    // Use connection
}  // Auto-closed

// 2. Cleaner API (Java 9+) - phantom reference-based
class NativeResource implements AutoCloseable {
    private static final Cleaner CLEANER = Cleaner.create();
    private final Cleaner.Cleanable cleanable;
    private final long nativePtr;
    
    NativeResource() {
        this.nativePtr = allocateNative();
        // Register cleanup action (must not reference 'this'!)
        this.cleanable = CLEANER.register(this, 
            new CleanupAction(nativePtr));  // Static class, no 'this' ref
    }
    
    @Override
    public void close() {
        cleanable.clean();  // Explicit cleanup (idempotent)
    }
    
    private static class CleanupAction implements Runnable {
        private final long ptr;
        CleanupAction(long ptr) { this.ptr = ptr; }
        @Override public void run() { freeNative(ptr); }
    }
}
```

---

### Q150-200: Quick-Fire Critical Questions

### Q150: What is CompletableFuture.allOf() vs join()?

```java
// allOf: returns CompletableFuture<Void> that completes when ALL complete
CompletableFuture<Void> all = CompletableFuture.allOf(cf1, cf2, cf3);
all.join();  // Wait for all
// Then get individual results:
String r1 = cf1.join();
String r2 = cf2.join();

// join() vs get():
// join(): Throws unchecked CompletionException
// get(): Throws checked ExecutionException + InterruptedException
```

### Q151: What is the difference between map() and flatMap() in Streams?

```java
// map: Transform each element (1:1 mapping)
List<String> words = lines.stream()
    .map(String::toUpperCase)  // Stream<String> → Stream<String>
    .collect(toList());

// flatMap: Transform each element to a stream, then flatten (1:many mapping)
List<String> words = lines.stream()
    .flatMap(line -> Arrays.stream(line.split(" ")))  // Stream<String> → Stream<String>
    .collect(toList());
// Without flatMap: map gives Stream<Stream<String>> - nested!
// flatMap flattens it to Stream<String>
```

### Q152: How does LinkedHashMap maintain order?

```java
// Doubly-linked list through all entries (in addition to hash table)
// head ↔ entry1 ↔ entry2 ↔ entry3 ↔ tail

// Insertion order (default):
LinkedHashMap<String, Integer> map = new LinkedHashMap<>();

// Access order (for LRU cache):
LinkedHashMap<String, Integer> lru = new LinkedHashMap<>(16, 0.75f, true);
// true = access order (most recently accessed moves to tail)
// head = least recently used, tail = most recently used
```

### Q153: What is the difference between abstract class with no abstract methods vs interface?

```java
// Abstract class with no abstract methods:
// - Can have state (instance variables)
// - Can have constructors
// - Prevents instantiation
// - Used when you want to provide base behavior but prevent direct use

// Interface:
// - No state (only constants)
// - No constructors
// - Multiple inheritance possible
// - Defines a contract
```

### Q154: What is Double Brace Initialization?

```java
// Double brace initialization (AVOID!):
Map<String, Integer> map = new HashMap<>() {{
    put("key1", 1);
    put("key2", 2);
}};
// Creates anonymous subclass of HashMap with instance initializer
// PROBLEMS: 
// - Creates a new class for each use (classloader pollution)
// - Holds reference to enclosing instance (memory leak)
// - Breaks equals() (different class)
// - Serialization issues

// Better alternatives:
Map<String, Integer> map = Map.of("key1", 1, "key2", 2);  // Java 9+
Map<String, Integer> map = Map.ofEntries(
    Map.entry("key1", 1),
    Map.entry("key2", 2)
);
```

### Q155: What is method hiding vs overriding?

```java
class Parent {
    static void staticMethod() { System.out.println("Parent static"); }
    void instanceMethod() { System.out.println("Parent instance"); }
}

class Child extends Parent {
    static void staticMethod() { System.out.println("Child static"); }  // HIDING
    @Override
    void instanceMethod() { System.out.println("Child instance"); }  // OVERRIDING
}

Parent p = new Child();
p.staticMethod();   // "Parent static" (resolved by reference type - static binding)
p.instanceMethod(); // "Child instance" (resolved by object type - dynamic binding)
```

### Q156: What is the difference between ClassNotFoundException and NoClassDefFoundError?

```java
// ClassNotFoundException (checked exception):
// - Class.forName("com.Missing") when class is not in classpath
// - Explicit loading request failed
// - Usually at runtime when using reflection/dynamic loading

// NoClassDefFoundError (error):
// - Class was available at compile time but not at runtime
// - JVM tried to load a class that existed during compilation
// - Usually: dependency removed, or static initializer failed
//   (class fails to load once → future access throws NoClassDefFoundError)
```

### Q157: What are Functional Interfaces in java.util.function?

```java
// Primitive specializations (avoid boxing):
IntFunction<String> intToString = i -> "Number: " + i;     // int → R
IntPredicate isEven = i -> i % 2 == 0;                      // int → boolean
IntConsumer printer = System.out::println;                   // int → void
IntSupplier random = () -> ThreadLocalRandom.current().nextInt(); // () → int
IntUnaryOperator doubler = i -> i * 2;                      // int → int
IntBinaryOperator sum = Integer::sum;                        // (int,int) → int
ToIntFunction<String> length = String::length;              // T → int
ObjIntConsumer<String> repeater = (s, n) -> { };            // (T,int) → void

// Compose functions:
Function<String, String> trim = String::trim;
Function<String, String> upper = String::toUpperCase;
Function<String, String> trimAndUpper = trim.andThen(upper);  // trim first, then upper
Function<String, String> upperThenTrim = trim.compose(upper); // upper first, then trim

// Predicate composition:
Predicate<String> notEmpty = s -> !s.isEmpty();
Predicate<String> startsWith = s -> s.startsWith("A");
Predicate<String> combined = notEmpty.and(startsWith);
Predicate<String> negated = notEmpty.negate();
```

### Q158: Explain WeakHashMap use cases and behavior.

```java
// WeakHashMap: Keys are WeakReferences
// When key is no longer strongly referenced elsewhere → entry auto-removed

// Use Case 1: Metadata cache (metadata lives only while key object lives)
WeakHashMap<Image, ImageMetadata> metadata = new WeakHashMap<>();
Image img = loadImage("photo.jpg");
metadata.put(img, new ImageMetadata("2024", "NYC"));
// When img becomes unreachable → metadata entry removed automatically

// Use Case 2: Canonical mapping / interning
WeakHashMap<String, String> internPool = new WeakHashMap<>();

// IMPORTANT CAVEATS:
// 1. Never use String literals as keys (they're always strongly referenced from String pool!)
// 2. Never use Integer keys from -128 to 127 (cached, never GC'd)
// 3. Size may change between calls (entries removed by GC)
// 4. NOT thread-safe (use Collections.synchronizedMap or manual sync)
```

### Q159: What is the difference between Collection.stream() and Collection.parallelStream()?

```java
// stream(): Sequential processing
list.stream()
    .filter(x -> x > 5)
    .map(x -> x * 2)
    .collect(toList());
// Single thread processes all elements in encounter order

// parallelStream(): Parallel processing
list.parallelStream()
    .filter(x -> x > 5)
    .map(x -> x * 2)
    .collect(toList());
// ForkJoinPool splits work across multiple threads
// Order maintained for ordered operations (but may be slower)
// Use .unordered() to allow optimizations when order doesn't matter

// Convert between:
stream.parallel();    // Sequential → Parallel
stream.sequential();  // Parallel → Sequential
stream.isParallel();  // Check
```

### Q160: What is Spliterator?

```java
// Spliterator = Splittable Iterator (for parallel stream decomposition)
// Characteristics flags:
// ORDERED - has defined encounter order
// DISTINCT - no duplicate elements
// SORTED - elements sorted
// SIZED - known size (enables splitting)
// NONNULL - no null elements
// IMMUTABLE - source cannot be modified
// CONCURRENT - source can be safely modified concurrently
// SUBSIZED - splits have known sizes

// Custom Spliterator example:
class BatchSpliterator<T> implements Spliterator<T> {
    private final Spliterator<T> source;
    private final int batchSize;
    
    @Override
    public Spliterator<T> trySplit() {
        // Split off a batch for parallel processing
        List<T> batch = new ArrayList<>(batchSize);
        // Fill batch...
        return batch.spliterator();
    }
    
    @Override
    public boolean tryAdvance(Consumer<? super T> action) {
        return source.tryAdvance(action);
    }
    
    @Override
    public long estimateSize() { return source.estimateSize(); }
    
    @Override
    public int characteristics() { return source.characteristics(); }
}
```

### Q161-200: Rapid Fire Concepts

**Q161: What is method overloading vs overriding?**
- Overloading: Same name, different parameters (compile-time polymorphism)
- Overriding: Same signature in subclass (runtime polymorphism)

**Q162: Can you override a static method?**
- No. Static methods are hidden, not overridden (resolved by reference type)

**Q163: What is a marker interface?**
- Interface with no methods (Serializable, Cloneable, Remote)
- Used as a type tag/flag

**Q164: What is the diamond operator <>?**
- Type inference for generics: `List<String> list = new ArrayList<>()`
- Compiler infers type arguments from context

**Q165: What is effectively final?**
- Variable that is never reassigned after initialization
- Required for lambda capture (since Java 8)

**Q166: What is String.intern()?**
- Returns canonical representation from String Pool
- If pool contains equal string, returns that reference; else adds and returns

**Q167: What is the difference between PATH and CLASSPATH?**
- PATH: OS finds executables (java, javac)
- CLASSPATH: JVM finds .class files and JARs

**Q168: What is transient keyword?**
- Marks field to be excluded from serialization
- Deserialized value will be default (null, 0, false)

**Q169: What is the purpose of the native keyword?**
- Declares method implemented in native code (C/C++ via JNI)
- Example: Thread.sleep(), Object.hashCode()

**Q170: What is instanceOf operator and pattern matching?**
```java
// Traditional:
if (obj instanceof String) {
    String s = (String) obj;
    s.length();
}
// Pattern matching (Java 16+):
if (obj instanceof String s) {
    s.length();  // s already cast!
}
```

**Q171: What are Switch Expressions (Java 14+)?**
```java
int numDays = switch (month) {
    case JAN, MAR, MAY, JUL, AUG, OCT, DEC -> 31;
    case APR, JUN, SEP, NOV -> 30;
    case FEB -> isLeapYear ? 29 : 28;
};
```

**Q172: What is a Text Block (Java 15+)?**
```java
String json = """
        {
            "name": "John",
            "age": 30
        }
        """;
```

**Q173: What is the difference between notify() and notifyAll()?**
- notify(): Wakes ONE arbitrary waiting thread
- notifyAll(): Wakes ALL waiting threads (recommended - avoids missed signals)

**Q174: What is thread starvation?**
- Thread cannot access shared resources because others monopolize them
- Fix: Fair locks, priority adjustments, bounded wait times

**Q175: What is a daemon thread?**
- Background thread that doesn't prevent JVM shutdown
- JVM exits when only daemon threads remain
- Set before start(): `thread.setDaemon(true)`

**Q176: What is CAS (Compare-And-Swap) failure?**
- CAS fails when another thread modified the value between read and write attempt
- Solution: Retry in a loop (spin) until CAS succeeds

**Q177: What is lock coarsening?**
- JIT optimization: Merges adjacent synchronized blocks on same lock
- Reduces lock/unlock overhead for sequential synchronization

**Q178: What is lock elision?**
- JIT optimization: Removes synchronization on objects that don't escape the thread
- Detected via escape analysis

**Q179: What is biased locking?**
- Optimization for uncontended locks (removed in Java 15)
- First thread to acquire gets "bias" - subsequent locks are free
- If contention detected, revokes bias and upgrades to standard locking

**Q180: What is spin locking in JVM?**
- Thread spins (busy-waits) briefly instead of immediately parking
- Effective when lock is held for very short time
- Adaptive spinning: JVM adjusts spin count based on history

**Q181: What is thread parking?**
- LockSupport.park(): Suspend thread (more flexible than wait)
- LockSupport.unpark(thread): Resume specific thread
- No need to hold a lock, and works with a permit model

**Q182: What are VarHandle operations (Java 9+)?**
```java
VarHandle vh = MethodHandles.lookup().findVarHandle(MyClass.class, "x", int.class);
vh.get(instance);                    // Plain read
vh.getVolatile(instance);           // Volatile read
vh.getAcquire(instance);            // Acquire semantics
vh.set(instance, 42);               // Plain write
vh.setRelease(instance, 42);        // Release semantics
vh.compareAndSet(instance, 0, 1);   // CAS
vh.getAndAdd(instance, 1);          // Atomic add
```

**Q183: What is the difference between LinkedTransferQueue and SynchronousQueue?**
- SynchronousQueue: Zero capacity, put ALWAYS blocks until take
- LinkedTransferQueue: Has capacity (unbounded), transfer() blocks but put() doesn't

**Q184: What is work stealing in ForkJoinPool?**
- Idle thread steals tasks from busy thread's deque (from opposite end)
- Self-balancing load distribution without central coordination

**Q185: What are fiber-friendly locks (Virtual Threads)?**
- ReentrantLock: Virtual thread unmounts from carrier (GOOD)
- synchronized: Virtual thread pins to carrier (BAD for I/O inside sync block)

**Q186: What is safe publication?**
- Making an object's reference AND state visible to other threads correctly
- Techniques: volatile, final fields, AtomicReference, synchronized

**Q187: What is the initialization-on-demand holder idiom?**
```java
class Singleton {
    private static class Holder {
        static final Singleton INSTANCE = new Singleton();
    }
    static Singleton getInstance() { return Holder.INSTANCE; }
}
// Lazy, thread-safe, no synchronization (class loading guarantees)
```

**Q188: How does ArrayDeque differ from LinkedList as a Deque?**
- ArrayDeque: Circular array, no null elements, faster (cache-friendly), less memory
- LinkedList: Doubly-linked nodes, allows null, node allocation overhead
- ArrayDeque preferred for stack/queue operations (3-4x faster)

**Q189: What is the Spliterator.trySplit() contract?**
- Split off approximately half the elements into a new Spliterator
- Return null if cannot split (too few elements or non-splittable source)
- Both original and split must be valid (non-overlapping, complete coverage)

**Q190: What is terminal vs short-circuit operation?**
- Terminal: Triggers stream pipeline (collect, forEach, reduce)
- Short-circuit: May not process all elements (findFirst, anyMatch, limit)
- Short-circuit terminal: Stops pipeline early (findFirst returns after first match)

**Q191: What happens if you call stream() on a collection twice?**
- Creates two independent stream pipelines
- Both iterate the source independently
- But: stream itself cannot be reused after terminal operation

**Q192: What is peek() vs forEach() in streams?**
- peek(): Intermediate operation (lazy), for debugging/side-effects during pipeline
- forEach(): Terminal operation (triggers execution), final consumption

**Q193: How does Collectors.groupingBy work with downstream collectors?**
```java
// Multi-level grouping:
Map<Dept, Map<String, List<Employee>>> result = employees.stream()
    .collect(groupingBy(Employee::getDept, 
             groupingBy(Employee::getCity)));
```

**Q194: What is a CompletionStage?**
- Interface that CompletableFuture implements
- Defines the contract for async computation stages
- 38 methods for composing, combining, and handling results

**Q195: What is Double-Checked Locking and why does it need volatile?**
```java
// Without volatile: CPU/compiler may reorder constructor and assignment
// Thread B may see non-null reference but uninitialized object!
// volatile prevents this reordering (StoreStore barrier before assignment)
```

**Q196: What is Amdahl's Law in context of Java parallelism?**
```
Speedup = 1 / (S + P/N)
S = serial fraction, P = parallel fraction, N = number of processors
If 10% is serial → max speedup = 10x (even with infinite processors)
// Key insight: Reducing the serial portion matters more than adding processors
```

**Q197: What is a Phaser vs CyclicBarrier?**
- Phaser allows dynamic party registration/deregistration
- CyclicBarrier has fixed party count
- Phaser supports per-phase termination conditions

**Q198: What is the cost of context switching for threads?**
- ~1-10 microseconds per switch (OS dependent)
- Includes: save/restore registers, TLB flush (for processes), cache invalidation
- Virtual threads reduce this (user-space switching, no kernel involvement)

**Q199: What is tail-call optimization? Does Java support it?**
- TCO: Reuse current stack frame for tail-recursive calls
- Java does NOT support TCO (each recursive call adds a frame → StackOverflow)
- Workaround: Convert recursion to iteration, or use trampolining

**Q200: What is Metaspace and how does it differ from PermGen?**
```
PermGen (Java 7 and earlier):
- Fixed max size (default 64MB)
- Part of Java heap
- OutOfMemoryError: PermGen space
- Required tuning (-XX:MaxPermSize)

Metaspace (Java 8+):
- Native memory (outside Java heap)
- Auto-grows (limited by available system memory)
- Can set max: -XX:MaxMetaspaceSize=256m
- Stores: class metadata, method bytecode, constant pool
- Collected when ClassLoader is GC'd (all its classes unloaded)
```

---

## Summary Table: When to Use What (Concurrency)

| Need | Use |
|------|-----|
| Simple counter | AtomicInteger / LongAdder |
| Flag/status | volatile boolean |
| Thread-safe Map | ConcurrentHashMap |
| Thread-safe sorted Map | ConcurrentSkipListMap |
| Thread-safe List (read-heavy) | CopyOnWriteArrayList |
| Producer-Consumer | LinkedBlockingQueue |
| Direct handoff | SynchronousQueue |
| Delayed execution | DelayQueue |
| Priority processing | PriorityBlockingQueue |
| Wait for N events | CountDownLatch |
| N threads sync at point | CyclicBarrier |
| Dynamic barrier | Phaser |
| Resource pool | Semaphore |
| Pair exchange | Exchanger |
| Divide-and-conquer | ForkJoinPool + RecursiveTask |
| Async computation | CompletableFuture |
| Scheduled tasks | ScheduledExecutorService |
| Lock with timeout | ReentrantLock.tryLock() |
| Read-heavy locking | ReadWriteLock / StampedLock |
| Per-thread data | ThreadLocal |
| One-time init | DCL / Holder idiom / enum |
| High-throughput counter | LongAdder |
| Lock-free queue | ConcurrentLinkedQueue |
| Multiple I/O tasks | Virtual Threads (Java 21) |

---

*This guide covers 200+ world-class Java interview questions with in-depth explanations of all major concepts including HashMap internals, ConcurrentHashMap, all concurrency primitives (BlockingQueue, Future, CompletableFuture, Atomic, CountDownLatch, CyclicBarrier, Phaser, Semaphore, Exchanger, ForkJoinPool, ScheduledExecutorService, locks), Java 8+ features, Garbage Collection, Memory Management, CPU debugging, JVM internals, and Design Patterns.*

