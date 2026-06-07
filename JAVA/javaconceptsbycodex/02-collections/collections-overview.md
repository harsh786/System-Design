# Java Collections Overview

Collections are reusable data structures from `java.util`. In LLD, collection choice is a design decision. It affects correctness, ordering, lookup speed, duplicate handling, thread-safety, and memory usage.

## Collection Hierarchy

```text
Iterable<E>
  |
  +-- Collection<E>
       |
       +-- List<E>
       |    +-- ArrayList
       |    +-- LinkedList
       |    +-- Vector
       |    +-- Stack
       |
       +-- Set<E>
       |    +-- HashSet
       |    +-- LinkedHashSet
       |    +-- TreeSet
       |    +-- EnumSet
       |
       +-- Queue<E>
            +-- PriorityQueue
            +-- Deque<E>
                 +-- ArrayDeque
                 +-- LinkedList

Map<K,V> is separate from Collection<E>
  |
  +-- HashMap
  +-- LinkedHashMap
  +-- TreeMap
  +-- Hashtable
  +-- ConcurrentHashMap
  +-- WeakHashMap
  +-- IdentityHashMap
  +-- EnumMap
```

`Map` is not a subtype of `Collection` because it stores key-value pairs, not single elements.

## Core Interfaces

| Interface | Meaning | Allows duplicates | Ordering | Common LLD use |
|---|---|---:|---|---|
| `Iterable<E>` | Something you can loop over | Depends on implementation | Depends | `for-each` loops |
| `Collection<E>` | Group of elements | Depends | Depends | Generic APIs accepting any collection |
| `List<E>` | Ordered sequence with indexes | Yes | Insertion/index order | Cart items, timeline rows, ordered rules |
| `Set<E>` | Unique elements | No | Depends | Permissions, tags, visited nodes |
| `Queue<E>` | Process elements in waiting order | Usually yes | Queue-specific | Jobs, notifications, BFS |
| `Deque<E>` | Double-ended queue | Usually yes | Front/back operations | Stack, queue, sliding window |
| `Map<K,V>` | Key-value lookup | Unique keys | Depends | ID lookup, cache, registry |

## Choosing The Right Collection

| Need | Use |
|---|---|
| Fast random access by index | `ArrayList` |
| Frequent add/remove at both ends | `ArrayDeque` |
| Frequent middle insertion with iterator already positioned | `LinkedList` can work, but rarely best |
| Unique unordered values | `HashSet` |
| Unique values in insertion order | `LinkedHashSet` |
| Unique sorted values | `TreeSet` |
| Fast lookup by key | `HashMap` |
| Key lookup plus insertion/access order | `LinkedHashMap` |
| Sorted keys and range operations | `TreeMap` |
| Priority-based retrieval | `PriorityQueue` |
| Thread-safe high-concurrency key-value storage | `ConcurrentHashMap` |
| Producer-consumer queue | `BlockingQueue`, usually `ArrayBlockingQueue` or `LinkedBlockingQueue` |

## Important Base Methods From `Collection`

These methods are available on `List`, `Set`, and most `Queue` implementations.

| Method | Meaning | Example |
|---|---|---|
| `add(E e)` | Adds one element. Returns `true` if collection changed. | `names.add("Asha")` |
| `addAll(Collection<? extends E> c)` | Adds all elements from another collection. | `names.addAll(moreNames)` |
| `remove(Object o)` | Removes one matching element if present. | `names.remove("Asha")` |
| `removeAll(Collection<?> c)` | Removes all elements that are present in another collection. | `users.removeAll(blocked)` |
| `retainAll(Collection<?> c)` | Keeps only elements also present in another collection. | `active.retainAll(verified)` |
| `contains(Object o)` | Checks if an element exists. | `names.contains("Asha")` |
| `containsAll(Collection<?> c)` | Checks if all requested elements exist. | `roles.containsAll(required)` |
| `size()` | Number of elements. | `items.size()` |
| `isEmpty()` | Whether size is zero. | `items.isEmpty()` |
| `clear()` | Removes everything. | `cart.clear()` |
| `iterator()` | Returns an `Iterator` for traversal/removal. | `Iterator<String> it = names.iterator()` |
| `toArray()` | Converts to array. | `names.toArray()` |
| `removeIf(Predicate)` | Removes elements matching a condition. | `users.removeIf(User::isInactive)` |
| `stream()` | Creates a sequential stream. | `users.stream().filter(...)` |
| `parallelStream()` | Creates a parallel stream. Use carefully. | CPU-heavy transformations |

## Iterator Concepts

An `Iterator` gives controlled traversal:

```java
Iterator<String> iterator = names.iterator();
while (iterator.hasNext()) {
    String name = iterator.next();
    if (name.startsWith("test-")) {
        iterator.remove();
    }
}
```

Use `iterator.remove()` when removing during iteration. Removing directly from the collection inside a for-each loop can cause `ConcurrentModificationException` for fail-fast collections like `ArrayList` and `HashSet`.

## Mutability Variants

```java
List<String> mutable = new ArrayList<>();
List<String> fixedSize = Arrays.asList("A", "B");
List<String> immutable = List.of("A", "B");
List<String> defensiveCopy = List.copyOf(mutable);
```

- `new ArrayList<>()`: mutable size and contents.
- `Arrays.asList(...)`: fixed size, but existing elements can be replaced.
- `List.of(...)`: immutable and rejects `null`.
- `List.copyOf(...)`: immutable copy and rejects `null`.

## Thread-Safety

Most collections in `java.util` are not thread-safe. If multiple threads modify a collection, use:

- `ConcurrentHashMap`
- `CopyOnWriteArrayList`
- `BlockingQueue`
- `ConcurrentLinkedQueue`
- `Collections.synchronizedList(...)` for simple cases
- External locking when operations must be atomic across multiple method calls

Example problem:

```java
if (!map.containsKey(id)) {
    map.put(id, value);
}
```

This is not atomic. In concurrent code, prefer:

```java
map.putIfAbsent(id, value);
```

or:

```java
map.computeIfAbsent(id, this::loadValue);
```

## LLD Design Examples

| LLD problem | Collection choice | Reason |
|---|---|---|
| Parking lot spot lookup | `Map<SpotId, ParkingSpot>` | Find spot by ID |
| User permissions | `Set<Permission>` | No duplicates |
| Elevator pending requests | `PriorityQueue<Request>` or `TreeSet<Request>` | Order by floor/direction/time |
| LRU cache | `LinkedHashMap<K,V>` | Maintains access order |
| Chat messages | `List<Message>` | Ordered timeline |
| Rate limiter timestamps | `Deque<Long>` | Remove old timestamps from front |
| Snake game body | `Deque<Cell>` plus `Set<Cell>` | Body order plus collision lookup |

