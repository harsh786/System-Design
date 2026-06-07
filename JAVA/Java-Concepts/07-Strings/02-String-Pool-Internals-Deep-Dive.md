# String Pool Internals & Deep Dive

> Advanced String and String Pool topics frequently asked in senior Java interviews.
> Covers: pool implementation, intern() mechanics, String deduplication, concatenation evolution,
> Compact Strings internals, memory forensics, and 15+ deep-dive interview questions.

---

## 1. String Pool Implementation Details

### What is the String Pool, Really?

The String Pool (also called the String Intern Pool or String Constant Pool) is **not** a
`java.util.HashMap`. It is a **native C++ hash table** (`StringTable`) implemented in HotSpot JVM.

```
┌─────────────────────────────────────────────────────────────────┐
│                        JVM HEAP                                  │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │              StringTable (Native C++ Structure)             │ │
│  │                                                            │ │
│  │  Bucket[0] → oop("hello") → oop("world") → null           │ │
│  │  Bucket[1] → oop("java") → null                           │ │
│  │  Bucket[2] → null                                         │ │
│  │  Bucket[3] → oop("foo") → oop("bar") → oop("baz") → null │ │
│  │  ...                                                       │ │
│  │  Bucket[N] → oop("test") → null                           │ │
│  │                                                            │ │
│  │  (oop = Ordinary Object Pointer to String on heap)         │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                      │
│  │ String   │  │ String   │  │ String   │   ← actual objects    │
│  │ "hello"  │  │ "world"  │  │ "java"   │     live on heap      │
│  │ byte[]   │  │ byte[]   │  │ byte[]   │                      │
│  └──────────┘  └──────────┘  └──────────┘                      │
└─────────────────────────────────────────────────────────────────┘
```

### Key Implementation Facts:

| Property | Detail |
|----------|--------|
| Data structure | Fixed-size hash table with linked-list buckets |
| Implementation | Native C++ `StringTable` class in HotSpot |
| Hash function | java_lang_String::hash_code() (same as String.hashCode()) |
| Bucket count | Configurable via -XX:StringTableSize |
| Resizing | **No automatic resizing** — fixed at startup |
| Thread safety | Uses SafepointSynchronize for modifications |
| GC interaction | Entries are weak references (collectable since Java 7) |

### Default StringTableSize Across Java Versions:

```
Java 6:  1009    (extremely small — long bucket chains!)
Java 7:  1009    (same terrible default initially)
Java 7u40+: 60013
Java 8:  60013
Java 11+: 65536
Java 17+: 65536
```

### Why Location Moved from PermGen to Heap:

```
┌──────────────────────────────────────────────────────────────────────┐
│ Java 6 and Earlier:                                                   │
│                                                                       │
│  ┌─────────────────────────┐    ┌─────────────────────────────────┐  │
│  │         HEAP             │    │         PermGen                  │  │
│  │                          │    │  ┌───────────────────────────┐  │  │
│  │  Application objects     │    │  │   String Pool (fixed!)     │  │  │
│  │  String objects (new)    │    │  │   Class metadata           │  │  │
│  │                          │    │  │   Method data              │  │  │
│  │                          │    │  │   Default: 64MB max        │  │  │
│  │                          │    │  └───────────────────────────┘  │  │
│  └─────────────────────────┘    └─────────────────────────────────┘  │
│                                                                       │
│  Problem: intern() too many strings → OutOfMemoryError: PermGen space │
│  Problem: Interned strings NEVER garbage collected!                    │
└──────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────┐
│ Java 7+:                                                              │
│                                                                       │
│  ┌──────────────────────────────────────────────────────────────┐    │
│  │                         HEAP                                   │    │
│  │                                                                │    │
│  │  ┌─────────────────────────────────────────────────────────┐  │    │
│  │  │   String Pool (part of regular heap!)                    │  │    │
│  │  │   - Benefits from regular GC                             │  │    │
│  │  │   - Unreferenced interned strings CAN be collected       │  │    │
│  │  │   - Pool size limited only by heap size                  │  │    │
│  │  └─────────────────────────────────────────────────────────┘  │    │
│  │                                                                │    │
│  │  Application objects                                           │    │
│  └──────────────────────────────────────────────────────────────┘    │
│                                                                       │
│  Java 8: PermGen replaced by Metaspace (for class metadata only)      │
│           String Pool stays in Heap (NOT Metaspace)                    │
└──────────────────────────────────────────────────────────────────────┘
```

### Verifying Pool Statistics at Runtime:

```bash
# Add JVM flag:
java -XX:+PrintStringTableStatistics -XX:StringTableSize=65536 MyApp

# Output at JVM shutdown:
# StringTable statistics:
# Number of buckets       :     65536 =    524288 bytes, each 8
# Number of entries       :     25847 =    413552 bytes, each 16
# Number of literals      :     25847 =   1587304 bytes, avg 61.41
# Total footprint         :           =   2525144 bytes
# Average bucket size     :     0.394
# Variance of bucket size :     0.396
# Std. dev. of bucket size:     0.629
# Maximum bucket size     :         4
```

### Code: Demonstrating Pool Behavior End-to-End

```java
public class StringPoolDemo {
    public static void main(String[] args) {
        // ═══════════════════════════════════════════════════════════════
        // CASE 1: Literals — always interned at class loading time
        // ═══════════════════════════════════════════════════════════════
        String s1 = "hello";  // classfile constant pool → runtime string pool
        String s2 = "hello";  // found in pool → returns same reference
        System.out.println(s1 == s2);  // true (same object)

        // ═══════════════════════════════════════════════════════════════
        // CASE 2: new String() — always creates NEW heap object
        // ═══════════════════════════════════════════════════════════════
        String s3 = new String("hello");
        // "hello" literal → goes to pool (or already there)
        // new String() → creates SEPARATE object on heap
        System.out.println(s1 == s3);      // false (different objects)
        System.out.println(s1.equals(s3)); // true  (same content)

        // ═══════════════════════════════════════════════════════════════
        // CASE 3: intern() — retrieve or store in pool
        // ═══════════════════════════════════════════════════════════════
        String s4 = s3.intern();
        // "hello" already in pool → returns existing pool reference
        System.out.println(s1 == s4);  // true (s4 points to pool's "hello")
        System.out.println(s3 == s4);  // false (s3 is heap copy, s4 is pool)

        // ═══════════════════════════════════════════════════════════════
        // CASE 4: Runtime concatenation — NOT in pool
        // ═══════════════════════════════════════════════════════════════
        String part = "lo";
        String s5 = "hel" + part;  // runtime: StringBuilder or invokedynamic
        System.out.println(s1 == s5);  // false (s5 is new heap object)

        String s6 = s5.intern();       // "hello" exists in pool → returns it
        System.out.println(s1 == s6);  // true

        // ═══════════════════════════════════════════════════════════════
        // CASE 5: Compile-time constants — compiler folds them
        // ═══════════════════════════════════════════════════════════════
        String s7 = "hel" + "lo";  // javac folds to "hello" at compile time
        System.out.println(s1 == s7);  // true (same constant pool entry)

        // ═══════════════════════════════════════════════════════════════
        // CASE 6: final variables are compile-time constants
        // ═══════════════════════════════════════════════════════════════
        final String prefix = "hel";
        String s8 = prefix + "lo";  // final + literal = compile-time constant
        System.out.println(s1 == s8);  // true

        // Without final:
        String prefix2 = "hel";  // NOT final
        String s9 = prefix2 + "lo";  // runtime concat (not constant)
        System.out.println(s1 == s9);  // false

        // ═══════════════════════════════════════════════════════════════
        // CASE 7: intern() on a string NOT yet in pool
        // ═══════════════════════════════════════════════════════════════
        String s10 = new String("unique_xyz_" + System.nanoTime());
        String s11 = s10.intern();  // not in pool → adds s10's reference to pool
        System.out.println(s10 == s11);  // true! (Java 7+: stores reference, no copy)
        // In Java 6, this would be false (PermGen copy)
    }
}
```

---

## 2. intern() Deep Dive

### How intern() Works (Native Level):

```
┌─────────────────────────────────────────────────────────────────┐
│  String.intern() — Native Method Flow                            │
│                                                                   │
│  1. Compute hash of this String's characters                     │
│  2. hash % StringTableSize → bucket index                        │
│  3. Walk linked list in that bucket                              │
│  4. For each entry: compare length, then content (equals)        │
│  5a. FOUND: return the existing String reference from pool       │
│  5b. NOT FOUND:                                                  │
│      - Java 6: Copy chars to new String in PermGen, add to pool  │
│      - Java 7+: Add THIS String's reference to pool (no copy!)   │
│      - Return the reference                                      │
└─────────────────────────────────────────────────────────────────┘
```

### Critical Difference: Java 6 vs Java 7+ intern():

```java
// Java 6 behavior:
String s = computeExpensiveString();  // lives on heap
String interned = s.intern();
// interned != s (ALWAYS) because intern() COPIES to PermGen
// Original heap string becomes garbage

// Java 7+ behavior:
String s = computeExpensiveString();  // lives on heap
String interned = s.intern();
// If "s" was NOT already in pool:
//   interned == s (TRUE!) because pool stores reference to s
// If "s" WAS already in pool:
//   interned != s (pool has older reference)
```

### intern() — Correct Usage Patterns:

```java
/**
 * PATTERN 1: Deduplicating strings from external data sources
 * Use when: parsing CSV/JSON/XML with known-limited distinct values
 */
public class CityParser {
    public List<Person> parsePeople(InputStream csv) {
        List<Person> people = new ArrayList<>(10_000_000);
        try (BufferedReader reader = new BufferedReader(new InputStreamReader(csv))) {
            String line;
            while ((line = reader.readLine()) != null) {
                String[] parts = line.split(",");
                String name = parts[0];
                String city = parts[1].intern();  // ~100 unique cities
                String country = parts[2].intern();  // ~50 unique countries
                people.add(new Person(name, city, country));
                // name is NOT interned — likely unique per record
            }
        }
        return people;
    }
}
// Memory: instead of 10M city String objects → 100 interned + 10M references
// Savings: (10M - 100) × ~60 bytes = ~600 MB saved

/**
 * PATTERN 2: Map keys that repeat heavily
 */
public class EventProcessor {
    private final Map<String, List<Event>> eventsByType = new HashMap<>();

    public void process(Event event) {
        // Event types: "CLICK", "VIEW", "PURCHASE" (limited set)
        String type = event.getType().intern();
        eventsByType.computeIfAbsent(type, k -> new ArrayList<>()).add(event);
    }
}

/**
 * PATTERN 3: Enum-like strings from database
 */
public class StatusCache {
    // Status column: "ACTIVE", "INACTIVE", "PENDING", "DELETED"
    public User mapRow(ResultSet rs) {
        User u = new User();
        u.setName(rs.getString("name"));
        u.setStatus(rs.getString("status").intern());  // 4 unique values
        return u;
    }
}
```

### intern() — Anti-Patterns (DO NOT DO):

```java
/**
 * ANTI-PATTERN 1: Interning unique strings
 */
public void processLogs(List<String> logLines) {
    for (String line : logLines) {
        String interned = line.intern();  // TERRIBLE!
        // Each log line is unique → pool grows unboundedly
        // StringTable lookup becomes slow (long bucket chains)
        // No deduplication benefit (nothing matches)
    }
}

/**
 * ANTI-PATTERN 2: Interning UUIDs, timestamps, random strings
 */
Map<String, Session> sessions = new HashMap<>();
public void addSession(Session s) {
    sessions.put(s.getId().intern(), s);  // IDs are unique! No benefit!
}

/**
 * ANTI-PATTERN 3: Interning in tight loops without checking
 */
public void benchmark() {
    long start = System.nanoTime();
    for (int i = 0; i < 1_000_000; i++) {
        String s = ("item_" + i).intern();  // 1M unique entries polluting pool
    }
    long elapsed = System.nanoTime() - start;
    // Gets progressively slower as buckets fill up
    // First 1000: ~100ns/intern
    // Last 1000: ~5000ns/intern (50x slower due to long chains)
}
```

### intern() Memory Leak Scenario:

```java
/**
 * How intern() can cause effective memory leak (Java 7+):
 * 
 * Even though interned strings CAN be GC'd, they won't be
 * if anything still references them.
 */
public class InternLeak {
    // This set keeps references alive → strings never GC'd from pool
    private static final Set<String> cache = new HashSet<>();

    public void processInput(String userInput) {
        String interned = userInput.intern();
        cache.add(interned);  // Strong reference prevents GC
        // If userInput is always unique → unbounded growth
    }
}

/**
 * Proper fix: Use bounded cache (LRU) instead of intern()
 */
public class BoundedStringCache {
    private final Map<String, String> cache =
        new LinkedHashMap<>(1000, 0.75f, true) {
            @Override
            protected boolean removeEldestEntry(Map.Entry<String, String> eldest) {
                return size() > 10_000;  // bounded!
            }
        };

    public String deduplicate(String s) {
        return cache.computeIfAbsent(s, Function.identity());
    }
}
```

### Performance Benchmarks (intern() vs alternatives):

```
Operation                          | Time (ns) | Notes
-----------------------------------|-----------|--------------------------------
String.equals() (10 chars, match)  |     15-30 | Baseline comparison
String.equals() (10 chars, miss)   |      5-10 | Quick fail on length/first char
== comparison                      |       1-2 | Just pointer compare
intern() - existing string found   |    50-150 | Hash + bucket walk
intern() - new string inserted     |   200-500 | Hash + allocation + insert
HashMap.get(String key)            |    20-100 | hashCode + equals on collision
HashMap.get(interned key) with ==  |     10-30 | hashCode + pointer compare

Conclusion: intern() only worth it when:
1. Same string compared 100s-1000s of times (amortizes intern cost)
2. OR memory deduplication saving is significant (millions of duplicates)
```

---

## 3. String Deduplication (G1GC / ZGC Feature)

### How G1 String Deduplication Works:

```
┌─────────────────────────────────────────────────────────────────────┐
│  WITHOUT String Deduplication:                                       │
│                                                                      │
│  String obj A ──→ byte[] {'H','e','l','l','o'}    (16 + 5 = 21 B)  │
│  String obj B ──→ byte[] {'H','e','l','l','o'}    (16 + 5 = 21 B)  │
│  String obj C ──→ byte[] {'H','e','l','l','o'}    (16 + 5 = 21 B)  │
│                                                                      │
│  3 String objects + 3 byte[] arrays = waste!                         │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│  WITH String Deduplication:                                          │
│                                                                      │
│  String obj A ──→ byte[] {'H','e','l','l','o'}    (shared!)         │
│  String obj B ──↗                                                   │
│  String obj C ──↗                                                   │
│                                                                      │
│  3 String objects + 1 byte[] array = savings!                        │
│  Note: String objects are DIFFERENT (A != B != C via ==)             │
│  Only the internal byte[] value field is shared                      │
└─────────────────────────────────────────────────────────────────────┘
```

### Deduplication Process (Step by Step):

```
1. G1GC promotes a String to old generation (survived enough young GC cycles)
2. The String is added to deduplication queue (if age >= threshold)
3. Deduplication thread processes queue:
   a. Computes hash of String's byte[] content
   b. Looks up in deduplication hash table
   c. If match found: replaces String.value field with existing byte[]
   d. If no match: inserts this String's byte[] into table
4. Original byte[] (now unreferenced) becomes eligible for GC

Important: This is done by a concurrent background thread
           — minimal impact on application throughput
```

### Configuration Flags:

```bash
# Enable String Deduplication (G1GC or ZGC required)
-XX:+UseStringDeduplication

# Minimum number of GC cycles before String is eligible (default: 3)
-XX:StringDeduplicationAgeThreshold=3

# Print statistics at shutdown
-XX:+PrintStringDeduplicationStatistics

# Example output:
# [GC concurrent-string-deduplication, 12.8ms]
#   Last Coverage: 100.0%
#   Last Coverage: 72.3%
#   Deduplicated:        12543 (  58.7%)
#   Young:                2314 (  18.4%)
#   Old:                 10229 (  81.6%)
#   Total dedup'd:   512.3KB (  58.7%)
#   Exec count/time:   47 / 102.4ms
```

### Comparison Table: intern() vs String Deduplication vs Manual Cache

| Aspect | intern() | G1 String Dedup | Manual Cache (Map) |
|--------|----------|-----------------|-------------------|
| Mechanism | Single reference in pool | Shared byte[] arrays | Application-level dedup |
| == works? | Yes | No | Depends on implementation |
| Code changes? | Yes (call .intern()) | No (JVM flag only) | Yes (cache lookup) |
| GC requirement | Any GC | G1GC or ZGC only | Any GC |
| Memory saved | Reference + byte[] | Only byte[] | Reference + byte[] |
| Control | Full (you choose what) | None (JVM decides) | Full |
| Overhead | Hash table lookup | Background thread + table | Map + lookup |
| Bounded? | No (but GC helps) | Yes (only aged strings) | Can be (LRU) |
| Latency impact | At intern() call site | Minimal (concurrent) | At lookup point |
| Best for | Known-limited values | General dedup, no code change | Custom requirements |

### When to Prefer Each:

```java
// ═══════════════════════════════════════════════════════════════
// USE intern() WHEN:
// ═══════════════════════════════════════════════════════════════
// - You need == comparison (hot path optimization)
// - You know the string domain is small and bounded
// - You want maximum memory savings (eliminates String object too)
// Example: Status codes, country codes, enum-like DB columns

// ═══════════════════════════════════════════════════════════════
// USE G1 String Deduplication WHEN:
// ═══════════════════════════════════════════════════════════════
// - You can't modify code (third-party libraries creating dups)
// - You already use G1GC
// - You want "free" dedup without code changes
// - You don't need == comparison
// Example: Large-scale services with JSON parsing frameworks

// ═══════════════════════════════════════════════════════════════
// USE Manual Cache WHEN:
// ═══════════════════════════════════════════════════════════════
// - You need bounded memory (LRU eviction)
// - You want == comparison but also eviction
// - intern() pool getting too large
// Example: User session data, request-scoped dedup
```

---

## 4. String Concatenation Evolution Across Java Versions

### Timeline and Bytecode Changes:

```
┌─────────┬─────────────────────────────────────────────────────────┐
│ Version │ How "a" + b + "c" compiles                              │
├─────────┼─────────────────────────────────────────────────────────┤
│ Java 1  │ new StringBuffer().append("a").append(b)                │
│         │   .append("c").toString()                               │
├─────────┼─────────────────────────────────────────────────────────┤
│ Java 5  │ new StringBuilder().append("a").append(b)               │
│         │   .append("c").toString()                               │
├─────────┼─────────────────────────────────────────────────────────┤
│ Java 9  │ invokedynamic StringConcatFactory                       │
│         │   .makeConcatWithConstants("a\u0001c")                  │
│         │   bootstrap: (String)String                             │
├─────────┼─────────────────────────────────────────────────────────┤
│ Java 21 │ Same as Java 9 (further JIT optimizations)              │
└─────────┴─────────────────────────────────────────────────────────┘
```

### Java 5-8: StringBuilder Approach (Limitations)

```java
// Source:
String result = "Hello, " + name + "! You are " + age + " years old.";

// Bytecode (decompiled equivalent):
String result = new StringBuilder()
    .append("Hello, ")
    .append(name)
    .append("! You are ")
    .append(age)
    .append(" years old.")
    .toString();

// Problems:
// 1. StringBuilder starts with capacity 16 → may resize multiple times
// 2. toString() copies char[] to new String (extra allocation)
// 3. Compiler doesn't know total length upfront
// 4. In loops: NEW StringBuilder created each iteration!
```

### Java 9+: invokedynamic + StringConcatFactory

```java
// Source (same code, different compilation):
String result = "Hello, " + name + "! You are " + age + " years old.";

// Bytecode: uses invokedynamic
// InvokeDynamic #0:makeConcatWithConstants:
//   (Ljava/lang/String;I)Ljava/lang/String;
//   BootstrapMethod: StringConcatFactory.makeConcatWithConstants
//   Recipe: "Hello, \u0001! You are \u0001 years old."
//   Constants: [] (none — name and age are dynamic args)
```

### How StringConcatFactory Works:

```
┌─────────────────────────────────────────────────────────────────────┐
│  StringConcatFactory.makeConcatWithConstants()                        │
│                                                                      │
│  1. FIRST CALL (bootstrap):                                          │
│     - Receives recipe string: "Hello, \u0001! You are \u0001 old."  │
│     - \u0001 marks positions for dynamic arguments                   │
│     - Generates a MethodHandle chain (strategy-dependent)            │
│     - Caches the MethodHandle at call site                           │
│                                                                      │
│  2. SUBSEQUENT CALLS (fast path):                                    │
│     - Uses cached MethodHandle directly                              │
│     - Computes exact size: len("Hello, ") + name.length() +         │
│       len("! You are ") + Integer.stringSize(age) + len(" old.")    │
│     - Allocates single byte[] of exact size                          │
│     - Copies all parts directly into byte[] (no resizing!)           │
│     - Wraps in String object                                         │
│                                                                      │
│  Result: ONE allocation of EXACT size (vs multiple with StringBuilder)│
└─────────────────────────────────────────────────────────────────────┘
```

### Available Strategies (-Djava.lang.invoke.stringConcat):

```bash
# JVM flag to select strategy:
-Djava.lang.invoke.stringConcat=<STRATEGY>

# Strategies:
# BC_SB              — Old-school StringBuilder bytecode (fallback)
# BC_SB_SIZED        — StringBuilder with estimated initial capacity
# BC_SB_SIZED_EXACT  — StringBuilder with exact capacity
# MH_SB_SIZED       — MethodHandle driving StringBuilder (sized)
# MH_SB_SIZED_EXACT — MethodHandle + exact sizing
# MH_INLINE_SIZED_EXACT — (DEFAULT in Java 9+) Direct byte[] construction
```

### Performance Comparison:

```
Benchmark: concatenating firstName + " " + lastName (avg 10 chars each)
Measured on Java 17, JMH, after warmup:

Strategy                    | Throughput (ops/us) | Allocations
----------------------------|--------------------|--------------
Java 8 StringBuilder       |              45    | 2 (SB + String)
BC_SB                      |              44    | 2 (SB + String)
BC_SB_SIZED_EXACT          |              52    | 2 (SB + String)
MH_INLINE_SIZED_EXACT      |              68    | 1 (String only!)

~50% improvement from Java 8 to Java 9+ default strategy!
```

### The Loop Problem (STILL Exists in Java 21):

```java
// ═══════════════════════════════════════════════════════════════
// BAD — O(n²) behavior regardless of Java version
// ═══════════════════════════════════════════════════════════════
String result = "";
for (int i = 0; i < 10_000; i++) {
    result += items[i];  // Each += creates a NEW String!
}
// Java 9+ invokedynamic makes each individual += faster
// BUT it still creates 10,000 intermediate String objects
// Total copies: 1 + 2 + 3 + ... + 10000 = ~50 million chars copied

// ═══════════════════════════════════════════════════════════════
// GOOD — O(n) with StringBuilder
// ═══════════════════════════════════════════════════════════════
StringBuilder sb = new StringBuilder(estimatedTotalLength);
for (int i = 0; i < 10_000; i++) {
    sb.append(items[i]);  // Amortized O(1) per append
}
String result = sb.toString();

// ═══════════════════════════════════════════════════════════════
// BEST — Use built-in joining methods
// ═══════════════════════════════════════════════════════════════
String result = String.join(", ", items);
// or
String result = Arrays.stream(items).collect(Collectors.joining(", "));
// or (Java 8+)
StringJoiner sj = new StringJoiner(", ", "[", "]");
for (String item : items) sj.add(item);
String result = sj.toString();  // produces: [item1, item2, ...]
```

---

## 5. CharSequence Interface Deep Dive

### Interface Definition (Java 17):

```java
public interface CharSequence {
    // Core methods (must implement):
    int length();
    char charAt(int index);
    CharSequence subSequence(int start, int end);

    // Default methods:
    default String toString() { /* ... */ }

    // Java 8+:
    default IntStream chars() {
        // Returns stream of char values (as ints)
    }
    default IntStream codePoints() {
        // Returns stream of Unicode code points (handles surrogates)
    }

    // Java 11+:
    default boolean isEmpty() {
        return this.length() == 0;
    }

    // Java 15+:
    static int compare(CharSequence cs1, CharSequence cs2) {
        // Lexicographic comparison without converting to String
    }
}
```

### Implementation Hierarchy:

```
                    CharSequence (interface)
                         │
         ┌───────────────┼───────────────────┐
         │               │                   │
      String       AbstractStringBuilder   CharBuffer
   (immutable)          │                 (NIO)
                  ┌─────┴──────┐
                  │            │
            StringBuilder  StringBuffer
           (not synced)   (synchronized)
```

### Why APIs Should Use CharSequence:

```java
// Methods accepting CharSequence are more flexible:
public class TextUtils {
    // GOOD: Works with String, StringBuilder, CharBuffer, custom impls
    public static boolean isPalindrome(CharSequence cs) {
        int left = 0, right = cs.length() - 1;
        while (left < right) {
            if (cs.charAt(left++) != cs.charAt(right--)) return false;
        }
        return true;
    }

    // LESS FLEXIBLE: Only works with String
    public static boolean isPalindrome(String s) {
        // Same logic but can't accept StringBuilder directly
    }
}

// Usage:
isPalindrome("racecar");                        // String ✓
isPalindrome(new StringBuilder("racecar"));     // StringBuilder ✓
isPalindrome(CharBuffer.wrap("racecar"));       // CharBuffer ✓
```

### Standard Library Methods That Accept CharSequence:

```java
// String methods:
String.contains(CharSequence s)
String.replace(CharSequence target, CharSequence replacement)
String.contentEquals(CharSequence cs)
String.join(CharSequence delimiter, CharSequence... elements)

// Pattern/Matcher:
Pattern.matcher(CharSequence input)
Matcher.reset(CharSequence input)

// Appendable interface:
Appendable.append(CharSequence csq)
Appendable.append(CharSequence csq, int start, int end)

// PrintStream/PrintWriter:
PrintStream.append(CharSequence csq)
```

---

## 6. Compact Strings (Java 9+) — Internal Implementation

### The Change:

```java
// ═══════════════════════════════════════════════════════════════
// JAVA 8 and earlier:
// ═══════════════════════════════════════════════════════════════
public final class String {
    private final char[] value;  // ALWAYS 2 bytes per character
    private int hash;
    // "Hello" → char[] {0x0048, 0x0065, 0x006C, 0x006C, 0x006F}
    //           Memory: 5 × 2 = 10 bytes (+ 16 byte array header = 26 bytes)
}

// ═══════════════════════════════════════════════════════════════
// JAVA 9+:
// ═══════════════════════════════════════════════════════════════
public final class String {
    private final byte[] value;  // 1 OR 2 bytes per char
    private final byte coder;    // 0 = LATIN1, 1 = UTF16
    private int hash;
    private boolean hashIsZero;  // Java 15+ (cache "hash not computed" vs "hash is 0")

    @Stable
    static final byte LATIN1 = 0;
    @Stable
    static final byte UTF16  = 1;

    // "Hello" → coder=LATIN1, byte[] {0x48, 0x65, 0x6C, 0x6C, 0x6F}
    //           Memory: 5 × 1 = 5 bytes (+ 16 byte array header = 21 bytes)

    // "こんにちは" → coder=UTF16, byte[] stored as UTF-16 (2 bytes per char)
    //             Memory: 5 × 2 = 10 bytes (+ 16 byte header = 26 bytes)
}
```

### Decision Logic (When is LATIN1 vs UTF16 chosen?):

```
┌─────────────────────────────────────────────────────────────────┐
│  String creation → scan all characters                           │
│                                                                  │
│  ALL chars ≤ 0xFF (fit in 1 byte)?                              │
│     YES → coder = LATIN1, store as byte[] (1 byte/char)         │
│     NO  → coder = UTF16,  store as byte[] (2 bytes/char, LE)    │
│                                                                  │
│  LATIN1 covers:                                                  │
│  - ASCII (0x00-0x7F): English, digits, common symbols            │
│  - Latin-1 Supplement (0x80-0xFF): é, ñ, ü, ß, etc.            │
│                                                                  │
│  UTF16 needed for:                                               │
│  - CJK characters (Chinese, Japanese, Korean)                    │
│  - Emoji                                                         │
│  - Arabic, Hebrew, Thai, etc.                                    │
│  - Any char > 0xFF                                               │
└─────────────────────────────────────────────────────────────────┘
```

### Impact on String Operations:

```java
// Internal dispatch based on coder:
public char charAt(int index) {
    if (isLatin1()) {
        return (char)(value[index] & 0xFF);  // fast: single byte read
    } else {
        return StringUTF16.charAt(value, index);  // 2-byte read
    }
}

public int length() {
    return value.length >> coder;  // LATIN1: length/1, UTF16: length/2
}

// Concatenation coercion:
// LATIN1 + LATIN1 = LATIN1 (fast path)
// LATIN1 + UTF16  = UTF16  (must inflate LATIN1 part)
// UTF16  + UTF16  = UTF16
```

### Memory Savings in Practice:

```
Typical English-language Java application:
┌─────────────────────────────────────────────────────────────┐
│  ~95% of Strings are pure ASCII → LATIN1 encoding           │
│  Savings: 50% on byte[] for those strings                    │
│  Overall heap reduction: 30-40% for String-heavy apps        │
└─────────────────────────────────────────────────────────────┘

Specific examples:
"Hello World"    Java 8: 22 bytes  │  Java 9+: 11 bytes  │  Savings: 50%
"status=200"     Java 8: 20 bytes  │  Java 9+: 10 bytes  │  Savings: 50%
"2024-01-15"     Java 8: 20 bytes  │  Java 9+: 10 bytes  │  Savings: 50%
"日本語"         Java 8:  6 bytes  │  Java 9+:  6 bytes  │  Savings:  0%
"café"           Java 8:  8 bytes  │  Java 9+:  8 bytes  │  Savings:  0%*
                                                  * 'é' = 0xE9 ≤ 0xFF → LATIN1!
"café☕"         Java 8: 10 bytes  │  Java 9+: 10 bytes  │  Savings:  0%
                                                  * ☕ > 0xFF → entire string is UTF16

// Disabling (rarely needed):
-XX:-CompactStrings  // forces all strings to UTF16 encoding
```

---

## 7. String Memory Forensics

### Object Layout (Java 17, 64-bit, Compressed Oops):

```
┌──────────────────────────────────────────────────────────────────┐
│  String Object (total: 24 bytes)                                  │
├──────────────────────────────────────────────────────────────────┤
│  Mark Word          │ 8 bytes │ GC age, locks, identity hash     │
│  Klass Pointer      │ 4 bytes │ Compressed pointer to String.class│
│  value (byte[] ref) │ 4 bytes │ Compressed pointer to byte[]      │
│  hash               │ 4 bytes │ Cached hashCode (0 = not computed)│
│  coder              │ 1 byte  │ LATIN1(0) or UTF16(1)            │
│  hashIsZero         │ 1 byte  │ Distinguishes hash=0 from unset  │
│  padding            │ 2 bytes │ Alignment to 8 bytes             │
├──────────────────────────────────────────────────────────────────┤
│  Total String shell │ 24 bytes│                                   │
└──────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│  byte[] for "Hello World" (LATIN1, 11 chars)                      │
├──────────────────────────────────────────────────────────────────┤
│  Mark Word          │ 8 bytes │ Array object header               │
│  Klass Pointer      │ 4 bytes │ Pointer to byte[].class           │
│  Length             │ 4 bytes │ Array length (11)                  │
│  Data              │ 11 bytes│ {72,101,108,108,111,32,87,...}    │
│  Padding           │  5 bytes│ Alignment to 8 bytes              │
├──────────────────────────────────────────────────────────────────┤
│  Total byte[]      │ 32 bytes│                                    │
└──────────────────────────────────────────────────────────────────┘

GRAND TOTAL for "Hello World": 24 + 32 = 56 bytes
Minimum String (empty ""): 24 + 16 = 40 bytes
```

### Using JOL to Inspect Memory:

```java
// Add dependency: org.openjdk.jol:jol-core:0.17
import org.openjdk.jol.info.ClassLayout;
import org.openjdk.jol.info.GraphLayout;

public class StringMemoryInspector {
    public static void main(String[] args) {
        String s = "Hello World";

        // Object layout (shallow):
        System.out.println(ClassLayout.parseInstance(s).toPrintable());
        // Output:
        // java.lang.String object internals:
        //  OFFSET  SIZE     TYPE DESCRIPTION               VALUE
        //       0     4          (object header)           01 00 00 00
        //       4     4          (object header)           00 00 00 00
        //       8     4          (object header)           da 02 00 20
        //      12     4   byte[] String.value              [B@...]
        //      16     4      int String.hash               0
        //      20     1     byte String.coder              0
        //      21     1  boolean String.hashIsZero         false
        //      22     2          (padding)
        // Instance size: 24 bytes

        // Graph layout (deep — includes referenced objects):
        System.out.println(GraphLayout.parseInstance(s).toFootprint());
        // Output:
        // java.lang.String@...d footance:
        //      COUNT       AVG       SUM   DESCRIPTION
        //          1        32        32   [B
        //          1        24        24   java.lang.String
        //          2                  56   (total)
    }
}
```

### Heap Analysis for Strings:

```bash
# Get histogram of objects by class:
jmap -histo <pid> | head -20

# Typical output for a large Java application:
#  num     #instances         #bytes  class name
#    1:       4523847      234567890  [B           (byte arrays — mostly String.value)
#    2:       3845621      123456789  java.lang.String
#    3:        982345       78901234  java.util.HashMap$Node
#    4:        654321       52345678  java.lang.Object[]

# String + byte[] typically = 40-60% of total heap!
```

### Reducing String Memory in Production:

```java
// Strategy 1: intern() for known-limited value sets
// Strategy 2: Enable G1 String Deduplication
// Strategy 3: Use compact data structures

// Instead of Map<String, String> for small fixed key sets:
enum UserField { NAME, EMAIL, CITY, COUNTRY }
EnumMap<UserField, String> userData = new EnumMap<>(UserField.class);
// Saves: HashMap overhead (Node objects, array resizing)

// Strategy 4: Avoid unnecessary String creation
// BAD:
log.debug("Processing user: " + user.getName() + " with id: " + user.getId());
// Creates concatenated String EVEN IF debug logging is off!

// GOOD:
log.debug("Processing user: {} with id: {}", user.getName(), user.getId());
// No String concatenation if debug is disabled

// Strategy 5: substring() behavior (Java 7u6+)
// Since Java 7u6: substring() creates NEW String with new byte[]
// (Before: shared char[] with offset — could cause memory leaks)
String huge = readLargeFile();  // 10MB string
String small = huge.substring(0, 10);  // creates new 10-char String
huge = null;  // 10MB can now be GC'd (wouldn't work pre-7u6 without copy)
```

---

## 8. String Lifecycle: From Source Code to Runtime

### Complete Journey of a String Literal:

```
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 1: Source Code                                                  │
│   String greeting = "Hello";                                         │
└──────────────────────────────────────┬──────────────────────────────┘
                                       │ javac compilation
                                       ▼
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 2: .class File (Constant Pool)                                  │
│   #1 = Utf8               "Hello"                                    │
│   #2 = String             #1          // references the Utf8 entry   │
│   #3 = Methodref          ...                                        │
│   Code: ldc #2  // load constant "Hello" onto operand stack         │
└──────────────────────────────────────┬──────────────────────────────┘
                                       │ ClassLoader.loadClass()
                                       ▼
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 3: Class Loading (Resolution)                                   │
│   - JVM reads .class constant pool                                   │
│   - For each CONSTANT_String entry:                                  │
│     1. Creates java.lang.String object from UTF8 bytes               │
│     2. Calls StringTable::intern() (native)                          │
│     3. If already in StringTable → returns existing reference        │
│     4. If not → adds this String to StringTable                      │
│   - Resolved reference cached in runtime constant pool               │
└──────────────────────────────────────┬──────────────────────────────┘
                                       │ Method execution
                                       ▼
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 4: Runtime (ldc instruction)                                    │
│   - `ldc #2` pushes the resolved String reference onto stack         │
│   - This is the SAME object every time (from pool)                   │
│   - No new allocation at execution time for literals                 │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 9. Interview Deep Dive Questions & Answers

### Q1: How does the String Pool hash table work internally?

**Answer:**
The String Pool is a native C++ `StringTable` in HotSpot JVM — a fixed-size hash table
with open chaining (linked lists per bucket). When `intern()` is called or a literal
is loaded, the JVM computes `String.hashCode()`, mods by table size to find a bucket,
then walks the linked list comparing content. If found, returns existing reference.
If not, inserts a new entry (oop pointer to the String object on heap).

Key points:
- Fixed size at JVM start (no auto-resize)
- Default: 65536 buckets (Java 11+)
- Too small → long chains → slow intern() and literal loading
- Accessed at safepoints for modification (thread-safe)

---

### Q2: What happens when StringTableSize is too small?

**Answer:**
```
With StringTableSize=1009 and 100,000 interned strings:
- Average bucket length: 100,000 / 1009 ≈ 99 entries per bucket
- Each intern() lookup: O(99) string comparisons
- Class loading with many literals becomes extremely slow

With StringTableSize=1000003 (prime):
- Average bucket length: 100,000 / 1000003 ≈ 0.1
- Each intern() lookup: essentially O(1)

Impact: 10-100x difference in intern() performance!
Fix: -XX:StringTableSize=1000003 (use prime number for better distribution)
```

---

### Q3: Why does "a" + "b" go to pool but "a" + variable doesn't?

**Answer:**
The Java Language Specification (JLS 15.28) defines **constant expressions**:
- String literals are constant expressions
- `final` variables initialized with constant expressions are constant expressions
- Concatenation of constant expressions is a constant expression

`javac` evaluates constant expressions at compile time (constant folding):
```java
"a" + "b"          → "ab" in .class constant pool → interned at load time
"a" + nonFinalVar  → compiled as runtime concatenation → heap String
final String x = "a";
x + "b"            → "ab" in .class constant pool → interned (x is constant)
```

---

### Q4: Can the garbage collector collect interned Strings?

**Answer:**
- **Java 6:** NO. Interned strings in PermGen are never collected (unless class unloaded).
- **Java 7+:** YES. StringTable entries are weak-like references. If no strong reference
  to an interned String exists elsewhere in the application, it CAN be collected during GC.

```java
// Example:
String s = new String("temporary").intern();  // added to pool
s = null;  // if no other reference exists, "temporary" eligible for GC from pool
System.gc();  // pool entry may be removed
```

However, string literals referenced from loaded class constant pools are always reachable
(the class itself holds a strong reference), so they're effectively permanent.

---

### Q5: What happens if you call intern() on 10 million unique strings?

**Answer:**
```
Effects:
1. StringTable grows to 10M entries (fixed bucket count!)
2. With default 65536 buckets: avg chain length = 10M/65536 ≈ 152
3. Each subsequent intern() must scan 152 entries on average
4. Performance degrades from ~100ns to ~5000ns per call
5. Memory: 10M entries × 16 bytes (native) = ~160MB native memory
   Plus: 10M String objects × 56 bytes = ~560MB heap
6. GC must scan all 10M entries during full GC (STW pause increases)

Mitigation:
- Increase StringTableSize: -XX:StringTableSize=10000019
- Or don't intern unique strings (use application-level cache instead)
```

---

### Q6: How does intern() differ between Java 6 and Java 7+?

**Answer:**
```java
// Java 6:
String s = new String(new char[]{'h','e','l','l','o'});
String i = s.intern();
System.out.println(s == i);  // false! (intern copied to PermGen)

// Java 7+:
String s = new String(new char[]{'h','e','l','l','o'});
String i = s.intern();
// If "hello" was NOT already in pool:
System.out.println(s == i);  // true! (pool stores reference to s)
// If "hello" WAS already in pool (e.g., from a literal):
System.out.println(s == i);  // false! (i points to the earlier pooled string)
```

---

### Q7: What's the total memory cost of a single empty String?

**Answer:**
```
String object:
  Object header (mark + klass): 12 bytes
  value (reference):             4 bytes
  hash (int):                    4 bytes
  coder (byte):                  1 byte
  hashIsZero (boolean):          1 byte
  padding:                       2 bytes
  Subtotal:                     24 bytes

byte[] (empty):
  Object header:                12 bytes
  length (int):                  4 bytes
  data:                          0 bytes
  padding:                       0 bytes
  Subtotal:                     16 bytes

TOTAL for "": 40 bytes (to store zero characters!)
```

---

### Q8: How would you investigate and reduce String memory in production?

**Answer:**
```bash
# Step 1: Get heap dump
jmap -dump:format=b,file=heap.hprof <pid>

# Step 2: Analyze with Eclipse MAT or VisualVM
# Look for:
# - Duplicate Strings (same content, different objects)
# - Retained byte[] sizes
# - String dominator tree

# Step 3: Apply fixes based on findings:
```

```java
// Fix 1: intern() for high-duplication fields
// Fix 2: Enable -XX:+UseStringDeduplication (G1GC)
// Fix 3: Use enum instead of String for fixed sets
// Fix 4: Lazy string creation (don't concat for debug logs)
// Fix 5: Increase -XX:StringTableSize if using intern() heavily
// Fix 6: Use byte[] or char[] directly for raw data processing
// Fix 7: Consider off-heap storage for large string data (DirectByteBuffer)
```

---

### Q9: Explain how G1 String Deduplication interacts with GC cycles

**Answer:**
```
Young GC cycle:
1. Strings in Young Gen are NOT eligible for dedup (too young)
2. Strings promoted to Old Gen increment their age counter

Mixed/Old GC cycle:
1. G1 identifies String objects with age ≥ StringDeduplicationAgeThreshold
2. These Strings are added to dedup queue (concurrent)
3. Dedup thread (runs concurrently with application):
   a. For each String in queue:
      - Compute hash of String.value byte[]
      - Look up in dedup hash table
      - Match found → CAS (Compare-And-Swap) the value field to shared byte[]
      - No match → insert this byte[] into dedup table
   b. Old byte[] (now unreferenced) collected in next GC

Key insight: Dedup only changes the internal byte[] reference,
NOT the String object reference. So == still fails between deduplicated strings.
```

---

### Q10: What's the difference between String constant pool and runtime constant pool?

**Answer:**
```
CLASS FILE Constant Pool:
- Static structure in .class file
- Contains symbolic references: Utf8, String, Class, Method, Field refs
- Each loaded class has its own

RUNTIME Constant Pool:
- JVM representation of class file constant pool (in Metaspace)
- Symbolic refs get resolved to direct pointers
- String entries resolve to references in String Pool (heap)

STRING Pool (String Table):
- JVM-wide (shared across all classes)
- Contains actual String object references
- Lives on heap (Java 7+)
- One entry per unique string content

Flow:
.class Constant Pool → resolved at class loading → 
  Runtime Constant Pool (per class, in Metaspace) → 
    points to String in StringTable (heap-wide)
```

---

### Q11: How does Compact Strings affect `charAt()` performance?

**Answer:**
```java
// With Compact Strings, charAt() has a branch:
public char charAt(int index) {
    if (isLatin1()) {
        // LATIN1 path: single byte read, zero-extend to char
        return (char)(value[index] & 0xFF);
        // Very fast: no multiplication, direct index
    } else {
        // UTF16 path: read 2 bytes, combine
        int offset = index << 1;  // multiply by 2
        return (char)((value[offset] & 0xFF) | (value[offset+1] << 8));
    }
}

// JIT compilation eliminates the branch for hot paths:
// If a method always processes LATIN1 strings, JIT compiles only LATIN1 path
// with an uncommon trap for the UTF16 case (speculative optimization)

// Net effect: LATIN1 charAt() is slightly FASTER than Java 8 char[]
// because byte[] access has better cache utilization (half the size)
```

---

### Q12: How can you prove that String Pool uses weak references (Java 7+)?

**Answer:**
```java
public class StringPoolGCProof {
    public static void main(String[] args) throws Exception {
        // Create and intern a string with no other strong reference
        WeakReference<String> weakRef;
        {
            String temp = new String(new char[]{'x','y','z','1','2','3'});
            String interned = temp.intern();
            weakRef = new WeakReference<>(interned);
            // temp and interned go out of scope here
        }

        // At this point, the only reference to "xyz123" is in StringTable
        // (which uses weak/phantom references internally)

        System.out.println("Before GC: " + weakRef.get());  // "xyz123"

        // Force GC
        System.gc();
        Thread.sleep(100);

        // If pool used strong references, string would survive
        // With weak references, it MAY be collected
        System.out.println("After GC: " + weakRef.get());   // null (possibly)

        // Note: This is non-deterministic. Full GC is more likely to clean.
        // Use -verbose:gc to observe StringTable cleaning.
    }
}
```

---

### Q13: Why is String.hashCode() computed lazily and what's the "0" problem?

**Answer:**
```java
public int hashCode() {
    // Java 8:
    int h = hash;  // read cached value
    if (h == 0 && value.length > 0) {
        for (byte v : value) {
            h = 31 * h + (v & 0xff);
        }
        hash = h;  // cache it
    }
    return h;
    // Problem: If hashCode legitimately equals 0, recomputes EVERY time!
    // Example: String with hash 0 exists (rare but possible)

    // Java 9+ fix:
    int h = hash;
    if (h == 0 && !hashIsZero) {
        h = computeHashCode();
        if (h == 0) {
            hashIsZero = true;  // remember that 0 is the actual hash
        } else {
            hash = h;
        }
    }
    return h;
    // Now correctly caches hash=0 without recomputing
}

// Strings with hashCode = 0 (examples):
// "\0" (single null char) → hash = 0
// Constructed strings like "Aa" ⊕ "BB" patterns that cancel to 0
// Very rare in practice (<0.001% of natural strings)
```

---

### Q14: How does `String.valueOf(int)` avoid creating intermediate Strings?

**Answer:**
```java
// Implementation (simplified from JDK source):
public static String valueOf(int i) {
    if (i == Integer.MIN_VALUE)
        return "-2147483648";  // literal from pool
    int size = (i < 0) ? stringSize(-i) + 1 : stringSize(i);
    if (COMPACT_STRINGS) {
        byte[] buf = new byte[size];
        getChars(i, size, buf);  // writes digits directly into byte[]
        return new String(buf, LATIN1);  // package-private constructor, no copy!
    } else {
        byte[] buf = new byte[size * 2];
        StringUTF16.getChars(i, size, buf);
        return new String(buf, UTF16);
    }
}

// Key optimization: uses package-private String(byte[], byte) constructor
// that does NOT copy the array (trusts the caller since it's same package)
// This avoids: int → String → char[] copy → new char[] (Java 8 path)
```

---

### Q15: Design question: How would you implement a string cache for a high-throughput service?

**Answer:**
```java
/**
 * Requirements:
 * - Millions of strings per second
 * - Known to have ~10,000 unique values
 * - Must be thread-safe
 * - Must not leak memory
 * - Must support == comparison for fast matching
 */
public class HighThroughputStringCache {
    // ConcurrentHashMap for thread safety without global lock
    private final ConcurrentHashMap<String, String> cache;

    // Maximum size to prevent unbounded growth
    private final int maxSize;

    public HighThroughputStringCache(int expectedDistinct) {
        this.maxSize = expectedDistinct * 2;  // some headroom
        // Pre-size to avoid rehashing
        this.cache = new ConcurrentHashMap<>(maxSize, 0.75f, 
            Runtime.getRuntime().availableProcessors());
    }

    /**
     * Deduplicate: returns canonical instance.
     * After this call, == comparison works for all deduplicated strings.
     */
    public String deduplicate(String s) {
        if (s == null) return null;

        // Fast path: already in cache
        String cached = cache.get(s);
        if (cached != null) return cached;

        // Slow path: add to cache
        if (cache.size() >= maxSize) {
            // Bounded: don't add more, just return input
            // (or implement LRU eviction here)
            return s;
        }

        cached = cache.putIfAbsent(s, s);
        return (cached != null) ? cached : s;
    }

    // Advantages over intern():
    // 1. Bounded size (won't pollute global StringTable)
    // 2. Can be GC'd entirely when cache object is discarded
    // 3. No native memory overhead
    // 4. No safepoint pauses from StringTable operations
    // 5. Cache-local (doesn't affect other parts of application)
}
```

---

## 10. Quick Reference: JVM Flags for String Tuning

```bash
# ═══════════════════════════════════════════════════════════════
# STRING POOL / INTERN
# ═══════════════════════════════════════════════════════════════
-XX:StringTableSize=65536          # Number of buckets (use prime)
-XX:+PrintStringTableStatistics    # Print stats at shutdown

# ═══════════════════════════════════════════════════════════════
# STRING DEDUPLICATION
# ═══════════════════════════════════════════════════════════════
-XX:+UseStringDeduplication                  # Enable (G1/ZGC only)
-XX:StringDeduplicationAgeThreshold=3        # Min GC age
-XX:+PrintStringDeduplicationStatistics      # Log dedup stats

# ═══════════════════════════════════════════════════════════════
# COMPACT STRINGS
# ═══════════════════════════════════════════════════════════════
-XX:+CompactStrings               # Enable (default: on since Java 9)
-XX:-CompactStrings               # Disable (force UTF16)

# ═══════════════════════════════════════════════════════════════
# CONCATENATION STRATEGY
# ═══════════════════════════════════════════════════════════════
-Djava.lang.invoke.stringConcat=MH_INLINE_SIZED_EXACT  # (default Java 9+)

# ═══════════════════════════════════════════════════════════════
# DIAGNOSTICS
# ═══════════════════════════════════════════════════════════════
-XX:+PrintCompilation              # See JIT decisions for String ops
-XX:+UnlockDiagnosticVMOptions -XX:+PrintInlining  # Inlining of String methods
```

---

## 11. Common Pitfalls & Gotchas

### Pitfall 1: substring() memory leak (pre-Java 7u6)
```java
// Java 6 / early Java 7: substring() shared the original char[]
String huge = new String(new char[1_000_000]);
String tiny = huge.substring(0, 5);
huge = null;
// char[1_000_000] is NOT collected! tiny holds reference to it.

// Fix (pre-7u6): new String(huge.substring(0, 5)) — forces copy
// Java 7u6+: substring() always creates new String with new byte[] (fixed)
```

### Pitfall 2: == on computed strings
```java
String a = "hello";
String b = "hel";
b += "lo";  // runtime concat
System.out.println(a == b);  // false! b is a new heap object
// Fix: always use .equals() for content comparison
```

### Pitfall 3: String.format() performance
```java
// String.format() is 5-10x slower than concatenation:
String slow = String.format("Hello %s, age %d", name, age);  // ~500ns
String fast = "Hello " + name + ", age " + age;               // ~50ns
// Use format only when formatting matters (locale, padding, etc.)
```

### Pitfall 4: Regex in String methods (hidden compilation)
```java
// These methods compile regex EVERY call:
str.split(",");          // Compiles Pattern for ","
str.replaceAll("\\s+", " ");  // Compiles Pattern for "\\s+"
str.matches("\\d+");    // Compiles Pattern for "\\d+"

// Fix: Pre-compile for repeated use
private static final Pattern COMMA = Pattern.compile(",");
private static final Pattern WHITESPACE = Pattern.compile("\\s+");
String[] parts = COMMA.split(str);
String cleaned = WHITESPACE.matcher(str).replaceAll(" ");

// Exception: single-char split like "," is optimized in Java 8+ to not use regex
```

### Pitfall 5: String concatenation in exceptions
```java
// This concatenation happens even if exception is never thrown:
throw new IllegalArgumentException("Invalid value: " + value + 
    " for field: " + field + " expected: " + expected);
// Usually fine (exceptions are exceptional), but in validation-heavy code,
// consider lazy message construction:
throw new IllegalArgumentException(
    String.format("Invalid value: %s for field: %s expected: %s", 
        value, field, expected));
// Or better: custom exception with fields, format in getMessage()
```

---

## 12. Summary Table: String Memory Across Java Versions

```
┌─────────┬──────────────┬─────────────────┬─────────────────────────────────┐
│ Version │ Internal Rep │ Pool Location   │ Key Characteristics              │
├─────────┼──────────────┼─────────────────┼─────────────────────────────────┤
│ Java 6  │ char[]       │ PermGen         │ Fixed pool, no GC of interned   │
│ Java 7  │ char[]       │ Heap            │ Pool GC'd, intern() stores ref  │
│ Java 8  │ char[]       │ Heap            │ PermGen → Metaspace (pool=heap) │
│ Java 9  │ byte[]+coder │ Heap            │ Compact Strings, invokedynamic  │
│ Java 11 │ byte[]+coder │ Heap            │ StringTableSize=65536 default   │
│ Java 15 │ byte[]+coder │ Heap            │ hashIsZero field added          │
│ Java 17 │ byte[]+coder │ Heap            │ Sealed String class (no subclass)│
│ Java 21 │ byte[]+coder │ Heap            │ Further JIT optimizations       │
└─────────┴──────────────┴─────────────────┴─────────────────────────────────┘
```

---

*End of String Pool Internals & Deep Dive. For basic String operations, methods,
StringBuilder/StringBuffer, Text Blocks, and Regex, see `01-Strings-Complete.md`.*
