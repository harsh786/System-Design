# Java Set and Map — Complete Reference for LLD

## 1. Collection Hierarchy (Sets and Maps)

```
Iterable
 └── Collection
      ├── List (indexed, duplicates allowed)
      └── Set (no duplicates)
           ├── HashSet           — O(1), unordered
           ├── LinkedHashSet     — O(1), insertion order
           └── SortedSet
                └── NavigableSet
                     └── TreeSet — O(log n), sorted

Map (NOT part of Collection interface)
 ├── HashMap                     — O(1), unordered
 ├── LinkedHashMap               — O(1), insertion/access order
 ├── WeakHashMap                 — keys eligible for GC
 ├── IdentityHashMap             — uses == not equals
 ├── EnumMap                     — array-backed for enum keys
 ├── Hashtable (legacy)          — synchronized, no nulls
 ├── ConcurrentHashMap           — segment-level locking
 └── SortedMap
      └── NavigableMap
           └── TreeMap           — O(log n), sorted by key
```

---

## 2. hashCode/equals Contract

### Rules

1. If `a.equals(b)` is `true`, then `a.hashCode() == b.hashCode()` MUST be true.
2. If `a.hashCode() != b.hashCode()`, then `a.equals(b)` MUST be `false`.
3. If `a.hashCode() == b.hashCode()`, `a.equals(b)` MAY or MAY NOT be true (collision).
4. `equals()` must be reflexive, symmetric, transitive, consistent, and `x.equals(null)` returns `false`.

### Correct Implementation

```java
public class Employee {
    private final int id;
    private final String name;

    public Employee(int id, String name) {
        this.id = id;
        this.name = name;
    }

    @Override
    public boolean equals(Object o) {
        if (this == o) return true;
        if (o == null || getClass() != o.getClass()) return false;
        Employee emp = (Employee) o;
        return id == emp.id && Objects.equals(name, emp.name);
    }

    @Override
    public int hashCode() {
        return Objects.hash(id, name); // uses 31 * result + element pattern
    }
}
```

### What Breaks When Violated

```java
// BAD: equals overridden but hashCode not
public class BrokenKey {
    private int id;
    
    public BrokenKey(int id) { this.id = id; }
    
    @Override
    public boolean equals(Object o) {
        if (o instanceof BrokenKey) return this.id == ((BrokenKey) o).id;
        return false;
    }
    // NO hashCode override!
}

public class ContractViolationDemo {
    public static void main(String[] args) {
        Map<BrokenKey, String> map = new HashMap<>();
        map.put(new BrokenKey(1), "Alice");
        
        // Different object instance, same logical value
        System.out.println(map.get(new BrokenKey(1))); // null! Object LOST
        // Because hashCode differs -> different bucket -> never finds it
        
        Set<BrokenKey> set = new HashSet<>();
        set.add(new BrokenKey(1));
        set.add(new BrokenKey(1));
        System.out.println(set.size()); // 2! Duplicate NOT detected
    }
}
```

---

## 3. HashSet

### Internal Implementation

```java
// Inside java.util.HashSet (simplified)
public class HashSet<E> implements Set<E> {
    private transient HashMap<E, Object> map;
    private static final Object PRESENT = new Object(); // dummy value

    public HashSet() {
        map = new HashMap<>();
    }

    public boolean add(E e) {
        return map.put(e, PRESENT) == null; // null means key was new
    }

    public boolean remove(Object o) {
        return map.remove(o) == PRESENT;
    }

    public boolean contains(Object o) {
        return map.containsKey(o);
    }
}
```

### All Operations with Code

```java
import java.util.*;
import java.util.stream.*;

public class HashSetComplete {
    public static void main(String[] args) {
        // --- Creation ---
        Set<String> set = new HashSet<>();
        Set<String> fromList = new HashSet<>(Arrays.asList("A", "B", "C"));
        Set<String> withCapacity = new HashSet<>(32, 0.75f); // capacity, loadFactor

        // --- add: O(1) ---
        set.add("Apple");
        set.add("Banana");
        set.add("Cherry");
        boolean added = set.add("Apple"); // false — duplicate rejected
        System.out.println("Added duplicate: " + added); // false
        System.out.println(set); // [Apple, Banana, Cherry] (order not guaranteed)

        // --- contains: O(1) ---
        System.out.println(set.contains("Banana")); // true
        System.out.println(set.contains("Grape"));  // false

        // --- remove: O(1) ---
        boolean removed = set.remove("Banana"); // true
        boolean removedAgain = set.remove("Banana"); // false — not present

        // --- size and isEmpty ---
        System.out.println("Size: " + set.size());      // 2
        System.out.println("Empty: " + set.isEmpty());  // false

        // --- iterator ---
        Iterator<String> it = set.iterator();
        while (it.hasNext()) {
            String s = it.next();
            if (s.equals("Apple")) {
                it.remove(); // safe removal during iteration
            }
        }

        // --- Bulk Operations ---
        Set<String> setA = new HashSet<>(Arrays.asList("1", "2", "3", "4"));
        Set<String> setB = new HashSet<>(Arrays.asList("3", "4", "5", "6"));

        // Union
        Set<String> union = new HashSet<>(setA);
        union.addAll(setB);
        System.out.println("Union: " + union); // [1, 2, 3, 4, 5, 6]

        // Intersection
        Set<String> intersection = new HashSet<>(setA);
        intersection.retainAll(setB);
        System.out.println("Intersection: " + intersection); // [3, 4]

        // Difference (A - B)
        Set<String> difference = new HashSet<>(setA);
        difference.removeAll(setB);
        System.out.println("Difference: " + difference); // [1, 2]

        // --- clear ---
        set.clear();
        System.out.println("After clear: " + set.size()); // 0

        // --- Stream operations ---
        Set<Integer> numbers = new HashSet<>(Arrays.asList(1, 2, 3, 4, 5, 6));
        Set<Integer> evens = numbers.stream()
                .filter(n -> n % 2 == 0)
                .collect(Collectors.toSet());
        System.out.println("Evens: " + evens); // [2, 4, 6]

        // --- toArray ---
        String[] arr = fromList.toArray(new String[0]);

        // --- Immutable Set (Java 9+) ---
        Set<String> immutable = Set.of("X", "Y", "Z");
        // immutable.add("W"); // UnsupportedOperationException
    }
}
```

---

## 4. LinkedHashSet

### Characteristics
- Extends `HashSet`, backed by `LinkedHashMap`
- Maintains **insertion order** via doubly-linked list through entries
- O(1) for add/remove/contains (same as HashSet)
- Slightly slower than HashSet due to linked-list maintenance
- Iteration is in insertion order (predictable)

### When to Use
- Remove duplicates but preserve original order
- Need deterministic iteration order

```java
import java.util.*;

public class LinkedHashSetDemo {
    public static void main(String[] args) {
        // Preserves insertion order
        Set<String> linked = new LinkedHashSet<>();
        linked.add("Banana");
        linked.add("Apple");
        linked.add("Cherry");
        linked.add("Apple"); // duplicate — rejected but order unchanged
        
        System.out.println(linked); // [Banana, Apple, Cherry] — insertion order!

        // Compare with HashSet
        Set<String> hash = new HashSet<>(linked);
        System.out.println(hash); // [Apple, Banana, Cherry] — no guaranteed order

        // Use case: remove duplicates from list while keeping order
        List<Integer> withDupes = Arrays.asList(5, 3, 1, 3, 5, 7, 1, 9);
        List<Integer> unique = new ArrayList<>(new LinkedHashSet<>(withDupes));
        System.out.println(unique); // [5, 3, 1, 7, 9]
    }
}
```

---

## 5. TreeSet

### Characteristics
- Backed by `TreeMap` (Red-Black tree)
- Elements sorted by natural ordering (Comparable) or custom Comparator
- O(log n) for add, remove, contains
- Implements `NavigableSet` — rich navigation methods
- Does NOT use hashCode/equals — uses compareTo or Comparator

### NavigableSet Methods

```java
import java.util.*;

public class TreeSetComplete {
    public static void main(String[] args) {
        TreeSet<Integer> ts = new TreeSet<>(Arrays.asList(10, 20, 30, 40, 50, 60));

        // --- Endpoints ---
        System.out.println("first: " + ts.first());   // 10
        System.out.println("last: " + ts.last());     // 60

        // --- Closest element queries ---
        // ceiling: smallest element >= given (inclusive)
        System.out.println("ceiling(25): " + ts.ceiling(25)); // 30
        System.out.println("ceiling(30): " + ts.ceiling(30)); // 30

        // floor: largest element <= given (inclusive)
        System.out.println("floor(25): " + ts.floor(25)); // 20
        System.out.println("floor(30): " + ts.floor(30)); // 30

        // higher: smallest element > given (exclusive)
        System.out.println("higher(30): " + ts.higher(30)); // 40

        // lower: largest element < given (exclusive)
        System.out.println("lower(30): " + ts.lower(30)); // 20

        // --- Range views (backed by original set) ---
        // headSet: elements < toElement (exclusive by default)
        System.out.println("headSet(30): " + ts.headSet(30));          // [10, 20]
        System.out.println("headSet(30, true): " + ts.headSet(30, true)); // [10, 20, 30]

        // tailSet: elements >= fromElement (inclusive by default)
        System.out.println("tailSet(30): " + ts.tailSet(30));          // [30, 40, 50, 60]
        System.out.println("tailSet(30, false): " + ts.tailSet(30, false)); // [40, 50, 60]

        // subSet: range [from, to)
        System.out.println("subSet(20, 50): " + ts.subSet(20, 50));              // [20, 30, 40]
        System.out.println("subSet(20,true,50,true): " + ts.subSet(20, true, 50, true)); // [20, 30, 40, 50]

        // --- Poll (retrieve and remove) ---
        System.out.println("pollFirst: " + ts.pollFirst()); // 10 (removed)
        System.out.println("pollLast: " + ts.pollLast());   // 60 (removed)
        System.out.println("After poll: " + ts);            // [20, 30, 40, 50]

        // --- Descending ---
        NavigableSet<Integer> desc = ts.descendingSet();
        System.out.println("Descending: " + desc); // [50, 40, 30, 20]
        Iterator<Integer> descIt = ts.descendingIterator();
    }
}
```

### Comparable vs Comparator

```java
// Option 1: Implement Comparable in the class
public class Student implements Comparable<Student> {
    String name;
    int grade;

    public Student(String name, int grade) {
        this.name = name;
        this.grade = grade;
    }

    @Override
    public int compareTo(Student other) {
        return Integer.compare(this.grade, other.grade); // sort by grade
    }

    @Override
    public String toString() { return name + "(" + grade + ")"; }
}

// Option 2: Provide Comparator externally
public class TreeSetWithComparator {
    public static void main(String[] args) {
        // Natural ordering (uses compareTo)
        TreeSet<Student> byGrade = new TreeSet<>();
        byGrade.add(new Student("Alice", 90));
        byGrade.add(new Student("Bob", 85));
        byGrade.add(new Student("Charlie", 92));
        System.out.println(byGrade); // [Bob(85), Alice(90), Charlie(92)]

        // Custom Comparator: sort by name
        TreeSet<Student> byName = new TreeSet<>(Comparator.comparing(s -> s.name));
        byName.addAll(byGrade);
        System.out.println(byName); // [Alice(90), Bob(85), Charlie(92)]

        // Reverse order
        TreeSet<Integer> descending = new TreeSet<>(Comparator.reverseOrder());
        descending.addAll(Arrays.asList(1, 5, 3, 2, 4));
        System.out.println(descending); // [5, 4, 3, 2, 1]

        // Multi-field: grade desc, then name asc
        TreeSet<Student> multi = new TreeSet<>(
            Comparator.comparingInt((Student s) -> s.grade).reversed()
                      .thenComparing(s -> s.name)
        );
    }
}
```

---

## 6. EnumSet

### Characteristics
- Specialized Set for enum types — backed by a **bit vector**
- Fastest Set implementation for enums (single long for <= 64 constants)
- All operations are O(1) bitwise operations
- Maintains natural enum order (declaration order)
- Cannot hold null

```java
import java.util.*;

public enum Permission {
    READ, WRITE, EXECUTE, DELETE, ADMIN
}

public class EnumSetDemo {
    public static void main(String[] args) {
        // --- Factory methods (no public constructor) ---
        EnumSet<Permission> none = EnumSet.noneOf(Permission.class);      // empty
        EnumSet<Permission> all = EnumSet.allOf(Permission.class);        // all values
        EnumSet<Permission> some = EnumSet.of(Permission.READ, Permission.WRITE); // specific
        EnumSet<Permission> range = EnumSet.range(Permission.READ, Permission.EXECUTE); // READ..EXECUTE

        // complement: everything NOT in the given set
        EnumSet<Permission> readOnly = EnumSet.of(Permission.READ);
        EnumSet<Permission> complement = EnumSet.complementOf(readOnly);
        System.out.println(complement); // [WRITE, EXECUTE, DELETE, ADMIN]

        // copy from another collection
        EnumSet<Permission> copy = EnumSet.copyOf(some);

        // --- Standard Set operations work ---
        some.add(Permission.EXECUTE);
        some.remove(Permission.WRITE);
        System.out.println(some.contains(Permission.READ)); // true
        System.out.println(some.size()); // 2

        // --- Practical use: role-based permissions ---
        Map<String, EnumSet<Permission>> rolePermissions = new HashMap<>();
        rolePermissions.put("VIEWER", EnumSet.of(Permission.READ));
        rolePermissions.put("EDITOR", EnumSet.of(Permission.READ, Permission.WRITE));
        rolePermissions.put("ADMIN", EnumSet.allOf(Permission.class));

        // Check permission
        String role = "EDITOR";
        if (rolePermissions.get(role).contains(Permission.WRITE)) {
            System.out.println("Can write!");
        }
    }
}
```

---

## 7. HashMap (DETAILED)

### Internal Structure

```
HashMap internal structure:
┌─────────────────────────────────────────────────────────┐
│  Node<K,V>[] table  (bucket array)                      │
│  Initial capacity: 16, Load factor: 0.75                │
│  Threshold = capacity * loadFactor = 12                 │
├─────────────────────────────────────────────────────────┤
│ Index:  [0]  [1]  [2]  [3]  [4]  ...  [15]            │
│          │         │                                    │
│          ▼         ▼                                    │
│        Node      Node → Node → Node    (LinkedList)    │
│       (K,V)     (K,V)  (K,V)  (K,V)                   │
│                                                         │
│  When bucket size >= 8: LinkedList → Red-Black Tree     │
│  When bucket size <= 6: Tree → LinkedList               │
└─────────────────────────────────────────────────────────┘

Node<K,V> structure:
┌──────────────────────┐
│ int hash             │
│ K key                │
│ V value              │
│ Node<K,V> next       │
└──────────────────────┘
```

### Hash Computation

```java
// Inside HashMap (Java 8+)
static final int hash(Object key) {
    int h;
    // XOR high 16 bits with low 16 bits — spreads hash across buckets
    return (key == null) ? 0 : (h = key.hashCode()) ^ (h >>> 16);
}

// Bucket index calculation (no modulo — bitwise AND)
int index = hash & (n - 1);  // n is always power of 2
// Example: n=16, hash=53
// 53 & 15 = 0b110101 & 0b001111 = 0b000101 = 5
```

### Why Power-of-2 Capacity

```
n = 16 (binary: 10000)
n - 1 = 15 (binary: 01111)

hash & (n-1) is equivalent to hash % n BUT faster (bitwise vs division)
This ONLY works when n is a power of 2.

If user passes non-power-of-2 capacity, HashMap rounds up:
tableSizeFor(10) → 16
tableSizeFor(17) → 32
```

### Collision Handling: LinkedList to Tree

```
TREEIFY_THRESHOLD = 8   → convert list to tree when bucket has >= 8 nodes
UNTREEIFY_THRESHOLD = 6 → convert tree back to list when bucket has <= 6
MIN_TREEIFY_CAPACITY = 64 → won't treeify if table size < 64 (resizes instead)

Put operation in a bucket:
1. If bucket empty: insert new Node
2. If first node matches key: update value
3. If first node is TreeNode: tree insertion O(log n)
4. Else: walk linked list
   - If key found: update value
   - If end reached: append new node
   - If list length >= TREEIFY_THRESHOLD: treeify bucket
```

### Rehashing

```
When size > threshold (capacity * loadFactor):
- New capacity = old capacity * 2
- New threshold = new capacity * loadFactor
- Every entry is re-indexed: hash & (newCap - 1)
  - Either stays at same index, or moves to (index + oldCap)
  - This is because new bit determines which half

Example: oldCap=16, newCap=32
  hash & 15 (old): uses bits 0-3
  hash & 31 (new): uses bits 0-4
  Extra bit (bit 4) determines: stay or move to index + 16
```

### Null Key Handling

```java
// null key ALWAYS goes to bucket 0
// hash(null) returns 0
// Only ONE null key allowed (subsequent puts overwrite value)
HashMap<String, Integer> map = new HashMap<>();
map.put(null, 100);
map.put(null, 200); // overwrites
System.out.println(map.get(null)); // 200
```

### ALL HashMap Methods with Code

```java
import java.util.*;
import java.util.function.*;

public class HashMapComplete {
    public static void main(String[] args) {
        // ========== BASIC OPERATIONS ==========
        Map<String, Integer> map = new HashMap<>();

        // --- put: O(1) average ---
        map.put("Alice", 90);
        map.put("Bob", 85);
        map.put("Charlie", 92);
        Integer oldVal = map.put("Alice", 95); // returns old value: 90
        System.out.println("Old value: " + oldVal); // 90

        // --- get: O(1) average ---
        System.out.println(map.get("Bob"));     // 85
        System.out.println(map.get("Unknown")); // null

        // --- remove: O(1) average ---
        Integer removed = map.remove("Bob"); // returns 85
        boolean removedExact = map.remove("Charlie", 99); // false (value doesn't match)
        boolean removedMatch = map.remove("Charlie", 92); // true

        // --- containsKey / containsValue ---
        System.out.println(map.containsKey("Alice"));   // true
        System.out.println(map.containsValue(95));      // true

        // --- size / isEmpty / clear ---
        System.out.println(map.size());    // 1
        System.out.println(map.isEmpty()); // false

        // ========== VIEWS ==========
        map.put("Alice", 95);
        map.put("Bob", 85);
        map.put("Charlie", 92);

        // --- keySet: returns Set<K> ---
        Set<String> keys = map.keySet();
        System.out.println("Keys: " + keys);

        // --- values: returns Collection<V> ---
        Collection<Integer> vals = map.values();
        System.out.println("Values: " + vals);

        // --- entrySet: returns Set<Map.Entry<K,V>> ---
        for (Map.Entry<String, Integer> entry : map.entrySet()) {
            System.out.println(entry.getKey() + " -> " + entry.getValue());
            entry.setValue(entry.getValue() + 5); // can modify value in place
        }

        // ========== JAVA 8+ METHODS ==========

        // --- getOrDefault ---
        int score = map.getOrDefault("Unknown", 0); // 0 (not present)
        System.out.println("Default: " + score);

        // --- putIfAbsent: only puts if key is absent or mapped to null ---
        map.putIfAbsent("Bob", 100);   // Bob exists → no change, returns 90
        map.putIfAbsent("Dave", 88);   // Dave absent → puts 88, returns null
        System.out.println(map.get("Bob"));  // 90 (unchanged)
        System.out.println(map.get("Dave")); // 88

        // --- compute: apply function to current value ---
        // If key exists: newValue = function(key, oldValue)
        // If key absent: newValue = function(key, null)
        // If function returns null: remove the entry
        map.compute("Alice", (key, val) -> val == null ? 0 : val + 10);
        System.out.println("Alice after compute: " + map.get("Alice")); // 110

        // --- computeIfAbsent: compute only if key is absent ---
        // Great for "get or create" pattern
        map.computeIfAbsent("Eve", key -> key.length() * 10);
        System.out.println("Eve: " + map.get("Eve")); // 30

        // Multi-map pattern: Map<String, List<String>>
        Map<String, List<String>> multiMap = new HashMap<>();
        multiMap.computeIfAbsent("fruits", k -> new ArrayList<>()).add("apple");
        multiMap.computeIfAbsent("fruits", k -> new ArrayList<>()).add("banana");
        System.out.println(multiMap); // {fruits=[apple, banana]}

        // --- computeIfPresent: compute only if key exists and value is non-null ---
        map.computeIfPresent("Bob", (key, val) -> val * 2);
        System.out.println("Bob doubled: " + map.get("Bob")); // 180

        map.computeIfPresent("NoOne", (key, val) -> val * 2); // no-op
        System.out.println(map.get("NoOne")); // null

        // --- merge: combine old value with new value ---
        // merge(key, newValue, remappingFunction)
        // If key absent: put(key, newValue)
        // If key present: put(key, function(oldValue, newValue))
        // If function returns null: remove the entry
        map.merge("Alice", 5, Integer::sum);  // 110 + 5 = 115
        map.merge("Frank", 77, Integer::sum); // absent → puts 77
        System.out.println("Alice merged: " + map.get("Alice")); // 115
        System.out.println("Frank merged: " + map.get("Frank")); // 77

        // Word frequency counter using merge
        String[] words = {"the", "cat", "sat", "on", "the", "mat", "the"};
        Map<String, Integer> freq = new HashMap<>();
        for (String w : words) {
            freq.merge(w, 1, Integer::sum);
        }
        System.out.println("Frequencies: " + freq); // {the=3, cat=1, sat=1, on=1, mat=1}

        // --- forEach ---
        map.forEach((key, val) -> System.out.println(key + " = " + val));

        // --- replaceAll: apply function to every value ---
        map.replaceAll((key, val) -> val + 100);
        System.out.println("After replaceAll: " + map);

        // --- replace ---
        map.replace("Alice", 999);            // replaces value
        map.replace("Alice", 999, 1000);      // conditional: only if value == 999
        System.out.println("Alice: " + map.get("Alice")); // 1000

        // ========== CONSTRUCTION VARIANTS ==========
        // Copy constructor
        Map<String, Integer> copy = new HashMap<>(map);

        // With initial capacity
        Map<String, Integer> sized = new HashMap<>(100); // avoids rehashing for ~75 entries

        // With capacity and load factor
        Map<String, Integer> tuned = new HashMap<>(100, 0.9f);

        // Immutable (Java 9+)
        Map<String, Integer> immut = Map.of("A", 1, "B", 2, "C", 3);
        Map<String, Integer> immut2 = Map.ofEntries(
            Map.entry("A", 1),
            Map.entry("B", 2)
        );
    }
}
```

---

## 8. LinkedHashMap

### Characteristics
- Extends HashMap, adds doubly-linked list through all entries
- Two ordering modes:
  - **Insertion order** (default): iteration in order of first insertion
  - **Access order** (`accessOrder=true`): most-recently-accessed last (LRU)
- O(1) for get/put (same as HashMap)
- Slightly more memory (prev/next pointers per entry)

### Basic Usage

```java
import java.util.*;

public class LinkedHashMapDemo {
    public static void main(String[] args) {
        // --- Insertion order (default) ---
        Map<String, Integer> lhm = new LinkedHashMap<>();
        lhm.put("Banana", 2);
        lhm.put("Apple", 1);
        lhm.put("Cherry", 3);
        System.out.println(lhm); // {Banana=2, Apple=1, Cherry=3} — insertion order

        // --- Access order ---
        Map<String, Integer> accessOrder = new LinkedHashMap<>(16, 0.75f, true);
        accessOrder.put("A", 1);
        accessOrder.put("B", 2);
        accessOrder.put("C", 3);

        accessOrder.get("A"); // A moves to end (most recently accessed)
        System.out.println(accessOrder); // {B=2, C=3, A=1}

        accessOrder.get("B"); // B moves to end
        System.out.println(accessOrder); // {C=3, A=1, B=2}
    }
}
```

### LRU Cache Implementation (LeetCode 146)

```java
import java.util.*;

/**
 * LRU Cache using LinkedHashMap with access order.
 * removeEldestEntry is called after every put().
 * When size exceeds capacity, the eldest (least recently used) entry is removed.
 */
public class LRUCache<K, V> extends LinkedHashMap<K, V> {
    private final int capacity;

    public LRUCache(int capacity) {
        // accessOrder = true: get() moves entry to end
        super(capacity, 0.75f, true);
        this.capacity = capacity;
    }

    @Override
    protected boolean removeEldestEntry(Map.Entry<K, V> eldest) {
        return size() > capacity; // remove eldest when over capacity
    }

    // --- Usage ---
    public static void main(String[] args) {
        LRUCache<Integer, String> cache = new LRUCache<>(3);
        
        cache.put(1, "one");
        cache.put(2, "two");
        cache.put(3, "three");
        System.out.println(cache); // {1=one, 2=two, 3=three}

        cache.get(1); // access 1 → moves to end
        System.out.println(cache); // {2=two, 3=three, 1=one}

        cache.put(4, "four"); // capacity exceeded → evicts eldest (2)
        System.out.println(cache); // {3=three, 1=one, 4=four}

        System.out.println(cache.get(2)); // null — was evicted
    }
}
```

### Manual LRU Cache (Without Extending LinkedHashMap)

```java
/**
 * LRU Cache — manual implementation with HashMap + Doubly Linked List.
 * This is the classic interview implementation.
 */
public class LRUCacheManual {
    
    private static class Node {
        int key, value;
        Node prev, next;
        Node(int key, int value) {
            this.key = key;
            this.value = value;
        }
    }

    private final int capacity;
    private final Map<Integer, Node> map;
    private final Node head, tail; // sentinels

    public LRUCacheManual(int capacity) {
        this.capacity = capacity;
        this.map = new HashMap<>();
        this.head = new Node(0, 0);
        this.tail = new Node(0, 0);
        head.next = tail;
        tail.prev = head;
    }

    public int get(int key) {
        Node node = map.get(key);
        if (node == null) return -1;
        moveToHead(node);
        return node.value;
    }

    public void put(int key, int value) {
        Node node = map.get(key);
        if (node != null) {
            node.value = value;
            moveToHead(node);
        } else {
            Node newNode = new Node(key, value);
            map.put(key, newNode);
            addToHead(newNode);
            if (map.size() > capacity) {
                Node lru = tail.prev;
                removeNode(lru);
                map.remove(lru.key);
            }
        }
    }

    private void addToHead(Node node) {
        node.next = head.next;
        node.prev = head;
        head.next.prev = node;
        head.next = node;
    }

    private void removeNode(Node node) {
        node.prev.next = node.next;
        node.next.prev = node.prev;
    }

    private void moveToHead(Node node) {
        removeNode(node);
        addToHead(node);
    }
}
```

---

## 9. TreeMap

### Characteristics
- Red-Black tree (self-balancing BST)
- Keys sorted by natural ordering or custom Comparator
- O(log n) for put, get, remove, containsKey
- O(n) for containsValue (must search all values)
- Implements `NavigableMap` — rich range/navigation queries
- NO null keys (throws NullPointerException), null values allowed

### NavigableMap Methods

```java
import java.util.*;

public class TreeMapComplete {
    public static void main(String[] args) {
        TreeMap<Integer, String> tm = new TreeMap<>();
        tm.put(10, "ten");
        tm.put(20, "twenty");
        tm.put(30, "thirty");
        tm.put(40, "forty");
        tm.put(50, "fifty");

        // --- Endpoint access ---
        System.out.println("firstKey: " + tm.firstKey());       // 10
        System.out.println("lastKey: " + tm.lastKey());         // 50
        System.out.println("firstEntry: " + tm.firstEntry());   // 10=ten
        System.out.println("lastEntry: " + tm.lastEntry());     // 50=fifty

        // --- Closest key queries ---
        // ceilingKey: smallest key >= given
        System.out.println("ceilingKey(25): " + tm.ceilingKey(25)); // 30
        System.out.println("ceilingKey(30): " + tm.ceilingKey(30)); // 30

        // floorKey: largest key <= given
        System.out.println("floorKey(25): " + tm.floorKey(25)); // 20
        System.out.println("floorKey(30): " + tm.floorKey(30)); // 30

        // higherKey: smallest key > given (exclusive)
        System.out.println("higherKey(30): " + tm.higherKey(30)); // 40

        // lowerKey: largest key < given (exclusive)
        System.out.println("lowerKey(30): " + tm.lowerKey(30)); // 20

        // Entry variants
        System.out.println("ceilingEntry(25): " + tm.ceilingEntry(25)); // 30=thirty
        System.out.println("floorEntry(25): " + tm.floorEntry(25));     // 20=twenty

        // --- Range views (backed by original map) ---
        // headMap: keys < toKey
        System.out.println("headMap(30): " + tm.headMap(30));          // {10=ten, 20=twenty}
        System.out.println("headMap(30,true): " + tm.headMap(30, true)); // {10=ten, 20=twenty, 30=thirty}

        // tailMap: keys >= fromKey
        System.out.println("tailMap(30): " + tm.tailMap(30));          // {30=thirty, 40=forty, 50=fifty}
        System.out.println("tailMap(30,false): " + tm.tailMap(30, false)); // {40=forty, 50=fifty}

        // subMap: keys in range [from, to)
        System.out.println("subMap(20,40): " + tm.subMap(20, 40));     // {20=twenty, 30=thirty}
        System.out.println("subMap(20,true,40,true): " + tm.subMap(20, true, 40, true)); // {20=twenty, 30=thirty, 40=forty}

        // --- Poll (retrieve and remove) ---
        System.out.println("pollFirstEntry: " + tm.pollFirstEntry()); // 10=ten (removed)
        System.out.println("pollLastEntry: " + tm.pollLastEntry());   // 50=fifty (removed)

        // --- Descending ---
        NavigableMap<Integer, String> desc = tm.descendingMap();
        System.out.println("Descending: " + desc); // {40=forty, 30=thirty, 20=twenty}

        NavigableSet<Integer> descKeys = tm.descendingKeySet();
    }
}
```

### Custom Comparator with TreeMap

```java
import java.util.*;

public class TreeMapComparatorExample {
    public static void main(String[] args) {
        // Case-insensitive string keys
        TreeMap<String, Integer> caseInsensitive = new TreeMap<>(String.CASE_INSENSITIVE_ORDER);
        caseInsensitive.put("apple", 1);
        caseInsensitive.put("Apple", 2); // overwrites — same key in case-insensitive
        caseInsensitive.put("BANANA", 3);
        System.out.println(caseInsensitive); // {apple=2, BANANA=3}

        // Reverse order
        TreeMap<Integer, String> reverse = new TreeMap<>(Comparator.reverseOrder());
        reverse.put(1, "one");
        reverse.put(3, "three");
        reverse.put(2, "two");
        System.out.println(reverse); // {3=three, 2=two, 1=one}

        // Custom object as key
        TreeMap<int[], String> byArraySum = new TreeMap<>(
            Comparator.comparingInt((int[] a) -> Arrays.stream(a).sum())
        );
        byArraySum.put(new int[]{1, 2}, "three");
        byArraySum.put(new int[]{5, 5}, "ten");
        byArraySum.put(new int[]{2, 2}, "four");
        byArraySum.forEach((k, v) -> System.out.println(Arrays.toString(k) + " -> " + v));
        // [1, 2] -> three
        // [2, 2] -> four
        // [5, 5] -> ten
    }
}
```

---

## 10. ConcurrentHashMap

### Java 8+ Internal Design

```
Java 8 ConcurrentHashMap:
- Uses CAS (Compare-And-Swap) for updates when bucket is empty
- Uses synchronized on FIRST NODE of bucket for collision chains
- No global lock — different threads can write to different buckets concurrently
- Node array is volatile — visibility guaranteed
- Lazy initialization: table allocated on first put

vs Java 7 (segments):
- Java 7 used Segment[] with 16 segments, each with own lock
- Java 8 eliminated segments — finer-grained per-bucket locking
```

### Usage

```java
import java.util.concurrent.*;
import java.util.*;

public class ConcurrentHashMapDemo {
    public static void main(String[] args) throws InterruptedException {
        ConcurrentHashMap<String, Integer> cmap = new ConcurrentHashMap<>();

        // --- Basic operations (same as HashMap) ---
        cmap.put("Alice", 90);
        cmap.put("Bob", 85);
        int val = cmap.get("Alice"); // 90

        // --- NO null keys or values (throws NullPointerException) ---
        // cmap.put(null, 1);     // NPE!
        // cmap.put("key", null); // NPE!

        // --- Atomic compound operations ---

        // putIfAbsent: atomic check-and-put
        cmap.putIfAbsent("Charlie", 88); // only puts if absent
        cmap.putIfAbsent("Charlie", 99); // no-op, Charlie already exists

        // computeIfAbsent: atomic check-and-compute (MOST USEFUL)
        // The entire computation is atomic for the key
        cmap.computeIfAbsent("Dave", key -> key.length() * 10);

        // compute: atomic read-modify-write
        cmap.compute("Alice", (key, oldVal) -> oldVal + 10); // 100

        // merge: atomic merge
        cmap.merge("Alice", 5, Integer::sum); // 105

        // --- Bulk operations (Java 8+) ---
        // These don't lock the entire map — they're weakly consistent
        cmap.forEach(2, (key, v) -> System.out.println(key + "=" + v)); // parallelism threshold = 2

        // search: find first match
        String found = cmap.search(1, (key, v) -> v > 90 ? key : null);
        System.out.println("Score > 90: " + found);

        // reduce
        int total = cmap.reduce(1, (key, v) -> v, Integer::sum);
        System.out.println("Total: " + total);

        // --- Thread-safe word counter pattern ---
        ConcurrentHashMap<String, Long> wordCount = new ConcurrentHashMap<>();
        String[] words = {"the", "cat", "sat", "on", "the", "mat", "the"};

        // Safe concurrent counting
        for (String w : words) {
            wordCount.merge(w, 1L, Long::sum);
        }
        System.out.println(wordCount); // {the=3, cat=1, sat=1, on=1, mat=1}

        // --- Concurrent Set (backed by ConcurrentHashMap) ---
        Set<String> concurrentSet = ConcurrentHashMap.newKeySet();
        concurrentSet.add("A");
        concurrentSet.add("B");
    }
}
```

### Comparison: ConcurrentHashMap vs synchronizedMap vs Hashtable

| Feature | ConcurrentHashMap | synchronizedMap | Hashtable |
|---------|------------------|-----------------|-----------|
| Locking | Per-bucket (CAS + sync on node) | Global mutex (entire map) | Global mutex |
| Null keys | No | Yes | No |
| Null values | No | Yes | No |
| Iterator | Weakly consistent (no CME) | Fail-fast (throws CME) | Fail-fast |
| Atomic ops | putIfAbsent, compute, merge | None (must external sync) | None |
| Performance | High concurrency | Single-thread bottleneck | Single-thread bottleneck |
| Recommended | Yes | Only if nulls needed | Never (legacy) |

```java
// Collections.synchronizedMap wraps any map with mutex
Map<String, Integer> syncMap = Collections.synchronizedMap(new HashMap<>());
// Must manually synchronize during iteration:
synchronized (syncMap) {
    for (Map.Entry<String, Integer> e : syncMap.entrySet()) {
        // safe iteration
    }
}
// ConcurrentHashMap doesn't need this — iterator is weakly consistent
```

---

## 11. Other Maps

### WeakHashMap

```java
import java.util.*;

/**
 * Keys are held via WeakReferences.
 * When a key has no more strong references, GC can collect it,
 * and the entry is automatically removed from the map.
 * 
 * Use case: caches where entries should be GC'd when key is no longer referenced.
 */
public class WeakHashMapDemo {
    public static void main(String[] args) {
        Map<Object, String> weakMap = new WeakHashMap<>();
        
        Object key1 = new Object();
        Object key2 = new Object();
        weakMap.put(key1, "value1");
        weakMap.put(key2, "value2");
        
        System.out.println("Before GC: " + weakMap.size()); // 2
        
        key1 = null; // remove strong reference to key1
        System.gc(); // request GC (not guaranteed)
        
        // After GC, key1's entry MAY be removed
        try { Thread.sleep(100); } catch (InterruptedException e) {}
        System.out.println("After GC: " + weakMap.size()); // likely 1

        // Note: String literals are interned (strong ref in string pool)
        // So WeakHashMap with String literal keys won't be collected!
        Map<String, Integer> bad = new WeakHashMap<>();
        bad.put("hello", 1); // "hello" is interned — never GC'd
        bad.put(new String("world"), 2); // this CAN be GC'd
    }
}
```

### IdentityHashMap

```java
import java.util.*;

/**
 * Uses == (reference equality) instead of .equals() for key comparison.
 * Uses System.identityHashCode() instead of key.hashCode().
 * 
 * Use case: tracking object identity (serialization frameworks, 
 * object graphs where you need to distinguish instances).
 */
public class IdentityHashMapDemo {
    public static void main(String[] args) {
        Map<String, Integer> identityMap = new IdentityHashMap<>();
        
        String s1 = new String("hello");
        String s2 = new String("hello");
        
        // s1.equals(s2) is true, but s1 != s2
        identityMap.put(s1, 1);
        identityMap.put(s2, 2);
        
        System.out.println(identityMap.size()); // 2! (treats as different keys)
        
        // Compare with HashMap:
        Map<String, Integer> hashMap = new HashMap<>();
        hashMap.put(s1, 1);
        hashMap.put(s2, 2);
        System.out.println(hashMap.size()); // 1 (same key by equals)
        
        // Interned strings share reference
        String s3 = "hello"; // from string pool
        String s4 = "hello"; // same reference from pool
        identityMap.put(s3, 3);
        identityMap.put(s4, 4);
        // s3 == s4, so this overwrites → only one entry for the literal
    }
}
```

### EnumMap

```java
import java.util.*;

/**
 * Specialized Map for enum keys — backed by a simple array.
 * Keys must all be from same enum type.
 * Extremely fast and compact (array index = enum ordinal).
 * Maintains natural enum order (declaration order).
 * Null keys NOT allowed; null values allowed.
 */
public enum Day {
    MONDAY, TUESDAY, WEDNESDAY, THURSDAY, FRIDAY, SATURDAY, SUNDAY
}

public class EnumMapDemo {
    public static void main(String[] args) {
        EnumMap<Day, String> schedule = new EnumMap<>(Day.class);
        
        schedule.put(Day.MONDAY, "Meeting");
        schedule.put(Day.WEDNESDAY, "Gym");
        schedule.put(Day.FRIDAY, "Review");
        schedule.put(Day.SATURDAY, "Rest");
        
        System.out.println(schedule);
        // {MONDAY=Meeting, WEDNESDAY=Gym, FRIDAY=Review, SATURDAY=Rest}
        // Always in declaration order regardless of insertion order
        
        // All Map operations work
        schedule.getOrDefault(Day.TUESDAY, "No plans"); // "No plans"
        schedule.forEach((day, activity) -> System.out.println(day + ": " + activity));
        
        // Use case: state machine transitions
        EnumMap<Day, Day> nextWorkday = new EnumMap<>(Day.class);
        nextWorkday.put(Day.MONDAY, Day.TUESDAY);
        nextWorkday.put(Day.TUESDAY, Day.WEDNESDAY);
        nextWorkday.put(Day.WEDNESDAY, Day.THURSDAY);
        nextWorkday.put(Day.THURSDAY, Day.FRIDAY);
        nextWorkday.put(Day.FRIDAY, Day.MONDAY);
    }
}
```

---

## 12. Time Complexity Comparison Table

### Set Implementations

| Operation | HashSet | LinkedHashSet | TreeSet | EnumSet |
|-----------|---------|---------------|---------|---------|
| add | O(1) | O(1) | O(log n) | O(1) |
| remove | O(1) | O(1) | O(log n) | O(1) |
| contains | O(1) | O(1) | O(log n) | O(1) |
| iterator next | O(h/n)* | O(1) | O(log n) | O(1) |
| first/last | N/A | N/A | O(log n) | N/A |
| ceiling/floor | N/A | N/A | O(log n) | N/A |
| Ordered? | No | Insertion | Sorted | Declaration |
| Null element | Yes (one) | Yes (one) | No** | No |

*h = table capacity, n = size. HashSet iterates over buckets.
**TreeSet allows null only if Comparator handles it.

### Map Implementations

| Operation | HashMap | LinkedHashMap | TreeMap | ConcurrentHashMap | EnumMap |
|-----------|---------|--------------|---------|-------------------|---------|
| put | O(1) | O(1) | O(log n) | O(1) | O(1) |
| get | O(1) | O(1) | O(log n) | O(1) | O(1) |
| remove | O(1) | O(1) | O(log n) | O(1) | O(1) |
| containsKey | O(1) | O(1) | O(log n) | O(1) | O(1) |
| containsValue | O(n) | O(n) | O(n) | O(n) | O(n) |
| firstKey/lastKey | N/A | N/A | O(log n) | N/A | N/A |
| Null key | Yes (one) | Yes (one) | No | No | No |
| Null value | Yes | Yes | Yes | No | Yes |
| Thread-safe | No | No | No | Yes | No |
| Ordered? | No | Insertion/Access | Sorted | No | Declaration |

### Space Complexity

| Structure | Space per Entry |
|-----------|----------------|
| HashMap | ~48 bytes (Node: hash + key + value + next pointer + overhead) |
| LinkedHashMap | ~64 bytes (adds before/after pointers) |
| TreeMap | ~64 bytes (TreeNode: key + value + left + right + parent + color) |
| EnumMap | ~16 bytes (just array slot for value) |
| ConcurrentHashMap | ~56 bytes (similar to HashMap + volatile) |

---

## 13. LLD Usage Examples

### Example 1: HashMap — In-Memory User Registry

```java
import java.util.*;
import java.util.concurrent.atomic.*;

/**
 * Simple in-memory user registry for a system design scenario.
 * Supports registration, lookup, update, and deactivation.
 */
public class UserRegistry {
    
    private static class User {
        private final String userId;
        private String name;
        private String email;
        private boolean active;
        private final long createdAt;

        public User(String userId, String name, String email) {
            this.userId = userId;
            this.name = name;
            this.email = email;
            this.active = true;
            this.createdAt = System.currentTimeMillis();
        }

        @Override
        public String toString() {
            return String.format("User{id=%s, name=%s, email=%s, active=%s}", 
                userId, name, email, active);
        }
    }

    private final Map<String, User> usersById = new HashMap<>();
    private final Map<String, String> emailToUserId = new HashMap<>(); // secondary index
    private final AtomicInteger userCount = new AtomicInteger(0);

    public String register(String name, String email) {
        if (emailToUserId.containsKey(email)) {
            throw new IllegalArgumentException("Email already registered: " + email);
        }
        String userId = "USER_" + userCount.incrementAndGet();
        User user = new User(userId, name, email);
        usersById.put(userId, user);
        emailToUserId.put(email, userId);
        return userId;
    }

    public User findById(String userId) {
        return usersById.get(userId);
    }

    public User findByEmail(String email) {
        String userId = emailToUserId.get(email);
        return userId != null ? usersById.get(userId) : null;
    }

    public boolean deactivate(String userId) {
        User user = usersById.get(userId);
        if (user == null || !user.active) return false;
        user.active = false;
        return true;
    }

    public Map<String, Long> getRegistrationStats() {
        Map<String, Long> stats = new HashMap<>();
        long active = usersById.values().stream().filter(u -> u.active).count();
        stats.put("total", (long) usersById.size());
        stats.put("active", active);
        stats.put("inactive", usersById.size() - active);
        return stats;
    }

    public static void main(String[] args) {
        UserRegistry registry = new UserRegistry();
        String id1 = registry.register("Alice", "alice@example.com");
        String id2 = registry.register("Bob", "bob@example.com");

        System.out.println(registry.findById(id1));
        System.out.println(registry.findByEmail("bob@example.com"));

        registry.deactivate(id1);
        System.out.println(registry.getRegistrationStats()); // {total=2, active=1, inactive=1}
    }
}
```

### Example 2: TreeMap — Stock Order Book with Price-Time Priority

```java
import java.util.*;

/**
 * Order book for a stock exchange.
 * - Buy orders: highest price first (descending TreeMap)
 * - Sell orders: lowest price first (ascending TreeMap)
 * - Within same price: FIFO (time priority via LinkedList)
 */
public class OrderBook {

    private static class Order {
        final String orderId;
        final double price;
        int quantity;
        final long timestamp;
        final boolean isBuy;

        Order(String orderId, double price, int quantity, boolean isBuy) {
            this.orderId = orderId;
            this.price = price;
            this.quantity = quantity;
            this.timestamp = System.nanoTime();
            this.isBuy = isBuy;
        }

        @Override
        public String toString() {
            return String.format("%s: %.2f x %d", orderId, price, quantity);
        }
    }

    // Buy side: highest price first → reversed TreeMap
    private final TreeMap<Double, LinkedList<Order>> buyOrders = new TreeMap<>(Comparator.reverseOrder());
    // Sell side: lowest price first → natural order TreeMap
    private final TreeMap<Double, LinkedList<Order>> sellOrders = new TreeMap<>();

    public void addOrder(Order order) {
        TreeMap<Double, LinkedList<Order>> book = order.isBuy ? buyOrders : sellOrders;
        book.computeIfAbsent(order.price, k -> new LinkedList<>()).add(order);
        tryMatch();
    }

    private void tryMatch() {
        while (!buyOrders.isEmpty() && !sellOrders.isEmpty()) {
            double bestBid = buyOrders.firstKey();  // highest buy price
            double bestAsk = sellOrders.firstKey(); // lowest sell price

            if (bestBid < bestAsk) break; // no match possible

            LinkedList<Order> buys = buyOrders.get(bestBid);
            LinkedList<Order> sells = sellOrders.get(bestAsk);

            Order buy = buys.peek();
            Order sell = sells.peek();

            int matched = Math.min(buy.quantity, sell.quantity);
            System.out.printf("MATCHED: %d shares @ %.2f (Buy: %s, Sell: %s)%n",
                    matched, bestAsk, buy.orderId, sell.orderId);

            buy.quantity -= matched;
            sell.quantity -= matched;

            if (buy.quantity == 0) {
                buys.poll();
                if (buys.isEmpty()) buyOrders.remove(bestBid);
            }
            if (sell.quantity == 0) {
                sells.poll();
                if (sells.isEmpty()) sellOrders.remove(bestAsk);
            }
        }
    }

    // Get best bid/ask spread
    public String getSpread() {
        Double bestBid = buyOrders.isEmpty() ? null : buyOrders.firstKey();
        Double bestAsk = sellOrders.isEmpty() ? null : sellOrders.firstKey();
        return String.format("Best Bid: %s | Best Ask: %s", bestBid, bestAsk);
    }

    // Get top N price levels
    public List<Map.Entry<Double, Integer>> getTopOfBook(boolean isBuy, int levels) {
        TreeMap<Double, LinkedList<Order>> book = isBuy ? buyOrders : sellOrders;
        List<Map.Entry<Double, Integer>> result = new ArrayList<>();
        int count = 0;
        for (Map.Entry<Double, LinkedList<Order>> entry : book.entrySet()) {
            if (count++ >= levels) break;
            int totalQty = entry.getValue().stream().mapToInt(o -> o.quantity).sum();
            result.add(Map.entry(entry.getKey(), totalQty));
        }
        return result;
    }

    public static void main(String[] args) {
        OrderBook book = new OrderBook();

        book.addOrder(new Order("B1", 100.50, 100, true));
        book.addOrder(new Order("B2", 100.75, 50, true));
        book.addOrder(new Order("B3", 100.50, 75, true));  // same price as B1, queued behind

        book.addOrder(new Order("S1", 101.00, 200, false));
        book.addOrder(new Order("S2", 100.60, 80, false)); // crosses with B2!

        System.out.println(book.getSpread());
        System.out.println("Buy top 3: " + book.getTopOfBook(true, 3));
        System.out.println("Sell top 3: " + book.getTopOfBook(false, 3));
    }
}
```

### Example 3: LinkedHashMap — LRU Cache (Production Style)

```java
import java.util.*;
import java.util.concurrent.locks.*;

/**
 * Thread-safe LRU Cache with TTL (Time-To-Live) support.
 * Uses LinkedHashMap access-order for LRU eviction.
 */
public class TTLLRUCache<K, V> {

    private static class CacheEntry<V> {
        final V value;
        final long expiresAt;

        CacheEntry(V value, long ttlMillis) {
            this.value = value;
            this.expiresAt = System.currentTimeMillis() + ttlMillis;
        }

        boolean isExpired() {
            return System.currentTimeMillis() > expiresAt;
        }
    }

    private final int maxSize;
    private final long defaultTTL;
    private final LinkedHashMap<K, CacheEntry<V>> cache;
    private final ReadWriteLock lock = new ReentrantReadWriteLock();

    private long hits = 0;
    private long misses = 0;

    public TTLLRUCache(int maxSize, long defaultTTLMillis) {
        this.maxSize = maxSize;
        this.defaultTTL = defaultTTLMillis;
        this.cache = new LinkedHashMap<>(maxSize, 0.75f, true) {
            @Override
            protected boolean removeEldestEntry(Map.Entry<K, CacheEntry<V>> eldest) {
                return size() > maxSize || eldest.getValue().isExpired();
            }
        };
    }

    public void put(K key, V value) {
        lock.writeLock().lock();
        try {
            cache.put(key, new CacheEntry<>(value, defaultTTL));
        } finally {
            lock.writeLock().unlock();
        }
    }

    public Optional<V> get(K key) {
        lock.writeLock().lock(); // write lock because access-order modifies list
        try {
            CacheEntry<V> entry = cache.get(key);
            if (entry == null) {
                misses++;
                return Optional.empty();
            }
            if (entry.isExpired()) {
                cache.remove(key);
                misses++;
                return Optional.empty();
            }
            hits++;
            return Optional.of(entry.value);
        } finally {
            lock.writeLock().unlock();
        }
    }

    public void evict(K key) {
        lock.writeLock().lock();
        try {
            cache.remove(key);
        } finally {
            lock.writeLock().unlock();
        }
    }

    public int size() {
        lock.readLock().lock();
        try {
            return cache.size();
        } finally {
            lock.readLock().unlock();
        }
    }

    public double hitRate() {
        long total = hits + misses;
        return total == 0 ? 0.0 : (double) hits / total;
    }

    public static void main(String[] args) throws InterruptedException {
        TTLLRUCache<String, String> cache = new TTLLRUCache<>(3, 5000); // max 3 entries, 5s TTL

        cache.put("A", "Apple");
        cache.put("B", "Banana");
        cache.put("C", "Cherry");

        System.out.println(cache.get("A")); // Optional[Apple]
        System.out.println(cache.get("X")); // Optional.empty

        cache.put("D", "Date"); // evicts LRU (B, since A was just accessed)
        System.out.println(cache.get("B")); // Optional.empty — evicted

        System.out.printf("Hit rate: %.2f%n", cache.hitRate()); // 0.33
    }
}
```

### Example 4: ConcurrentHashMap — Thread-Safe Connection Pool Registry

```java
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;

/**
 * Thread-safe connection pool registry using ConcurrentHashMap.
 * Manages multiple named pools (e.g., "primary-db", "cache-redis", "analytics-db").
 * 
 * Key patterns demonstrated:
 * - computeIfAbsent for lazy pool creation
 * - AtomicInteger for stats
 * - ConcurrentLinkedQueue for connection pooling
 */
public class ConnectionPoolRegistry {

    private static class Connection {
        final String poolName;
        final String connectionId;
        final long createdAt;
        volatile boolean inUse;

        Connection(String poolName, int id) {
            this.poolName = poolName;
            this.connectionId = poolName + "-conn-" + id;
            this.createdAt = System.currentTimeMillis();
            this.inUse = false;
        }

        @Override
        public String toString() { return connectionId; }
    }

    private static class Pool {
        final String name;
        final int maxSize;
        final ConcurrentLinkedQueue<Connection> available = new ConcurrentLinkedQueue<>();
        final AtomicInteger totalCreated = new AtomicInteger(0);
        final AtomicInteger activeCount = new AtomicInteger(0);
        final AtomicLong totalBorrowCount = new AtomicLong(0);

        Pool(String name, int maxSize) {
            this.name = name;
            this.maxSize = maxSize;
        }
    }

    private final ConcurrentHashMap<String, Pool> pools = new ConcurrentHashMap<>();
    private final int defaultPoolSize;

    public ConnectionPoolRegistry(int defaultPoolSize) {
        this.defaultPoolSize = defaultPoolSize;
    }

    /**
     * Get or create a pool — computeIfAbsent guarantees atomic creation
     */
    public Pool getOrCreatePool(String poolName) {
        return pools.computeIfAbsent(poolName, name -> {
            System.out.println("Creating pool: " + name);
            return new Pool(name, defaultPoolSize);
        });
    }

    /**
     * Borrow a connection from named pool
     */
    public Connection borrow(String poolName) {
        Pool pool = getOrCreatePool(poolName);
        Connection conn = pool.available.poll();

        if (conn != null) {
            conn.inUse = true;
            pool.activeCount.incrementAndGet();
            pool.totalBorrowCount.incrementAndGet();
            return conn;
        }

        // Create new connection if under max
        if (pool.totalCreated.get() < pool.maxSize) {
            int id = pool.totalCreated.incrementAndGet();
            conn = new Connection(poolName, id);
            conn.inUse = true;
            pool.activeCount.incrementAndGet();
            pool.totalBorrowCount.incrementAndGet();
            return conn;
        }

        throw new IllegalStateException("Pool exhausted: " + poolName);
    }

    /**
     * Return connection to pool
     */
    public void release(Connection conn) {
        Pool pool = pools.get(conn.poolName);
        if (pool != null) {
            conn.inUse = false;
            pool.activeCount.decrementAndGet();
            pool.available.offer(conn);
        }
    }

    /**
     * Get stats for all pools — uses forEach for concurrent iteration
     */
    public Map<String, Map<String, Object>> getStats() {
        Map<String, Map<String, Object>> stats = new LinkedHashMap<>();
        pools.forEach((name, pool) -> {
            Map<String, Object> poolStats = new LinkedHashMap<>();
            poolStats.put("maxSize", pool.maxSize);
            poolStats.put("created", pool.totalCreated.get());
            poolStats.put("active", pool.activeCount.get());
            poolStats.put("available", pool.available.size());
            poolStats.put("totalBorrows", pool.totalBorrowCount.get());
            stats.put(name, poolStats);
        });
        return stats;
    }

    /**
     * Shutdown a specific pool
     */
    public void shutdownPool(String poolName) {
        Pool pool = pools.remove(poolName);
        if (pool != null) {
            pool.available.clear();
            System.out.println("Pool shutdown: " + poolName);
        }
    }

    public static void main(String[] args) throws InterruptedException {
        ConnectionPoolRegistry registry = new ConnectionPoolRegistry(5);

        // Simulate concurrent access
        ExecutorService executor = Executors.newFixedThreadPool(10);
        CountDownLatch latch = new CountDownLatch(20);

        for (int i = 0; i < 20; i++) {
            final int taskId = i;
            executor.submit(() -> {
                try {
                    String pool = taskId % 2 == 0 ? "primary-db" : "cache-redis";
                    Connection conn = registry.borrow(pool);
                    System.out.println("Task " + taskId + " got " + conn);
                    Thread.sleep(100); // simulate work
                    registry.release(conn);
                } catch (Exception e) {
                    System.err.println("Task " + taskId + " failed: " + e.getMessage());
                } finally {
                    latch.countDown();
                }
            });
        }

        latch.await();
        executor.shutdown();

        System.out.println("\n--- Pool Stats ---");
        registry.getStats().forEach((name, stats) ->
            System.out.println(name + ": " + stats));
    }
}
```

---

## 14. Quick Decision Guide

```
Need a Set?
├── Enum values only?                      → EnumSet
├── Need sorted / range queries?           → TreeSet
├── Need insertion order preserved?        → LinkedHashSet
├── Thread-safe?                           → ConcurrentHashMap.newKeySet()
└── Default (fastest, no order needed)?    → HashSet

Need a Map?
├── Enum keys only?                        → EnumMap
├── Need sorted keys / range queries?      → TreeMap
├── Need insertion order?                  → LinkedHashMap
├── Need LRU eviction?                     → LinkedHashMap (accessOrder=true)
├── Thread-safe?                           → ConcurrentHashMap
├── Keys should be GC-eligible?            → WeakHashMap
├── Reference equality needed?             → IdentityHashMap
└── Default (fastest, no order needed)?    → HashMap
```

---

## 15. Common Pitfalls

```java
// 1. Mutable keys in HashMap — NEVER do this
Map<List<Integer>, String> badMap = new HashMap<>();
List<Integer> key = new ArrayList<>(Arrays.asList(1, 2, 3));
badMap.put(key, "hello");
key.add(4); // MUTATED! hashCode changed!
System.out.println(badMap.get(key)); // null — lost forever!

// 2. ConcurrentModificationException
Map<String, Integer> map = new HashMap<>();
map.put("a", 1); map.put("b", 2); map.put("c", 3);
// WRONG:
// for (String k : map.keySet()) { map.remove(k); } // CME!
// CORRECT:
map.entrySet().removeIf(e -> e.getValue() < 3);
// or use iterator with iterator.remove()

// 3. TreeMap/TreeSet: compareTo must be consistent with equals
// If compareTo returns 0, TreeMap treats as SAME KEY (overwrites)
TreeSet<String> ts = new TreeSet<>(String.CASE_INSENSITIVE_ORDER);
ts.add("Hello");
ts.add("HELLO"); // NOT added — comparator says equal
System.out.println(ts.size()); // 1

// 4. HashMap initial capacity for known size
// To avoid rehashing when inserting N elements:
int expectedSize = 1000;
Map<String, Integer> optimized = new HashMap<>(expectedSize * 4 / 3 + 1);
// Or simpler: pass expectedSize and let loadFactor handle it
// HashMap will round up to next power of 2 anyway

// 5. Unmodifiable wrappers vs immutable
Map<String, Integer> original = new HashMap<>();
original.put("a", 1);
Map<String, Integer> unmodifiable = Collections.unmodifiableMap(original);
original.put("b", 2); // modifies both! unmodifiable is just a VIEW
System.out.println(unmodifiable.get("b")); // 2!
// Use Map.copyOf() for true immutable copy (Java 10+)
Map<String, Integer> immutable = Map.copyOf(original);
```
