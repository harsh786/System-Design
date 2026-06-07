# Map, HashMap, LinkedHashMap, TreeMap, ConcurrentHashMap

`Map<K,V>` stores key-value pairs. Keys are unique. Values may be duplicated.

`Map` is one of the most important data structures for LLD because it models identity-based lookup: user by ID, product by SKU, vehicle by plate, session by token, cache entry by key.

## Main Implementations

| Class | Ordering | Thread-safe | Best for |
|---|---|---:|---|
| `HashMap` | No guaranteed order | No | General fast lookup |
| `LinkedHashMap` | Insertion or access order | No | Stable iteration, LRU cache |
| `TreeMap` | Sorted by key | No | Range queries, floor/ceiling by key |
| `ConcurrentHashMap` | No guaranteed order | Yes | Concurrent reads/writes |
| `Hashtable` | No guaranteed order | Yes, legacy synchronized | Legacy only |
| `WeakHashMap` | No guaranteed order | No | Cache keys removable by GC |
| `IdentityHashMap` | Reference equality | No | Rare identity-based internals |
| `EnumMap` | Enum natural order | No | Fast enum-keyed maps |

## HashMap

`HashMap` uses the key's `hashCode()` to pick a bucket, then uses `equals()` to find the exact key.

Important facts:

- Average `get`, `put`, and `remove` are O(1).
- Worst case can degrade, but modern Java can treeify heavily-collided buckets.
- Allows one `null` key and multiple `null` values.
- Does not preserve insertion order.
- Is not thread-safe.

## Important Map Methods

| Method | Meaning | Notes |
|---|---|---|
| `put(K,V)` | Insert or replace value | Returns old value or `null` |
| `putIfAbsent(K,V)` | Insert only if key absent or mapped to null | Useful for caches |
| `get(Object key)` | Return value or `null` | Ambiguous if value itself is null |
| `getOrDefault(K, default)` | Return value or default | Cleaner than null checks |
| `containsKey(Object key)` | Check key existence | Use when `null` value matters |
| `containsValue(Object value)` | Check value existence | Usually O(n) |
| `remove(Object key)` | Remove by key | Returns old value |
| `remove(key, value)` | Remove only if mapped to exact value | Conditional remove |
| `replace(K,V)` | Replace only if key exists | Returns old value |
| `replace(K, old, new)` | Conditional replace | Useful in concurrent-style logic |
| `compute(K, BiFunction)` | Recalculate mapping | Can insert, update, or remove |
| `computeIfAbsent(K, Function)` | Create value lazily if absent | Common for grouping |
| `computeIfPresent(K, BiFunction)` | Update only if present |  |
| `merge(K,V,BiFunction)` | Combine existing and new value | Great for counters |
| `keySet()` | Set view of keys | Backed by map |
| `values()` | Collection view of values | Backed by map |
| `entrySet()` | Set view of entries | Best for iterating key and value |
| `forEach(BiConsumer)` | Iterate entries |  |
| `size()` | Number of mappings |  |
| `isEmpty()` | No mappings |  |
| `clear()` | Remove all mappings |  |

## `get` Versus `containsKey`

```java
Map<String, String> map = new HashMap<>();
map.put("nickname", null);

System.out.println(map.get("nickname"));      // null
System.out.println(map.get("missing"));       // null
System.out.println(map.containsKey("nickname")); // true
```

If `null` values are allowed, use `containsKey` to distinguish "missing key" from "present key with null value".

## Iterating A Map

Prefer `entrySet()` when you need both key and value:

```java
for (Map.Entry<String, Integer> entry : scores.entrySet()) {
    System.out.println(entry.getKey() + " -> " + entry.getValue());
}
```

Avoid:

```java
for (String key : scores.keySet()) {
    System.out.println(scores.get(key));
}
```

It performs an extra lookup for each key.

## `computeIfAbsent` For Grouping

```java
Map<String, List<String>> cityToUsers = new HashMap<>();
cityToUsers.computeIfAbsent("Delhi", city -> new ArrayList<>()).add("Asha");
```

This avoids the old verbose pattern:

```java
if (!cityToUsers.containsKey("Delhi")) {
    cityToUsers.put("Delhi", new ArrayList<>());
}
cityToUsers.get("Delhi").add("Asha");
```

## `merge` For Counters

```java
Map<String, Integer> counts = new HashMap<>();
counts.merge("java", 1, Integer::sum);
counts.merge("java", 1, Integer::sum);
System.out.println(counts.get("java")); // 2
```

## LinkedHashMap

`LinkedHashMap` preserves predictable iteration order.

By default, it uses insertion order:

```java
Map<String, Integer> ordered = new LinkedHashMap<>();
ordered.put("b", 2);
ordered.put("a", 1);
System.out.println(ordered.keySet()); // [b, a]
```

It can also use access order, which is useful for LRU caches:

```java
Map<String, String> lru = new LinkedHashMap<>(16, 0.75f, true) {
    protected boolean removeEldestEntry(Map.Entry<String, String> eldest) {
        return size() > 3;
    }
};
```

## TreeMap

`TreeMap` keeps keys sorted and implements `NavigableMap`.

Important methods:

| Method | Meaning |
|---|---|
| `firstKey()` | Smallest key |
| `lastKey()` | Largest key |
| `lowerKey(k)` | Greatest key strictly less than `k` |
| `floorKey(k)` | Greatest key less than or equal to `k` |
| `ceilingKey(k)` | Smallest key greater than or equal to `k` |
| `higherKey(k)` | Smallest key strictly greater than `k` |
| `pollFirstEntry()` | Remove smallest entry |
| `pollLastEntry()` | Remove largest entry |
| `headMap(k)` | Keys before `k` |
| `tailMap(k)` | Keys from `k` onward |
| `subMap(a, b)` | Range view |
| `descendingMap()` | Reverse-order view |

Use `TreeMap` for calendar slots, price levels, floor/ceiling search, and range queries.

## ConcurrentHashMap

`ConcurrentHashMap` supports high-concurrency access.

Important differences from `HashMap`:

- Thread-safe for concurrent operations.
- Does not allow `null` keys or values.
- Provides atomic methods like `putIfAbsent`, `compute`, and `merge`.
- Iterators are weakly consistent, not fail-fast.

Example:

```java
ConcurrentHashMap<String, Integer> counts = new ConcurrentHashMap<>();
counts.merge("event", 1, Integer::sum);
```

## Key Design Rule

Map keys should be stable and immutable.

Good keys:

- `String`
- `Integer`
- `UUID`
- enum
- record value object like `record UserId(String value) {}`

Risky keys:

- mutable objects whose fields can change after insertion
- arrays, because arrays use reference equality unless wrapped

## LLD Uses

- `HashMap<UserId, User>` for user lookup.
- `LinkedHashMap<Key, Value>` for LRU cache.
- `TreeMap<Instant, Meeting>` for time-ordered meetings.
- `ConcurrentHashMap<SessionId, Session>` for active sessions in a concurrent server.
- `EnumMap<OrderStatus, List<Order>>` for grouping by enum status.

Runnable example: `src/main/java/com/codex/javaconcepts/collections/MapExamples.java`

