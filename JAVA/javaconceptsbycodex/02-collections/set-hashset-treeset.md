# Set, HashSet, LinkedHashSet, TreeSet, EnumSet

`Set<E>` represents unique elements. It models "membership" rather than position.

## Set Properties

- No duplicate elements.
- Uses `equals()` to decide logical equality.
- `HashSet` also depends on `hashCode()`.
- No index-based access.
- Ordering depends on implementation.

## Main Implementations

| Class | Ordering | Internal idea | Best for |
|---|---|---|---|
| `HashSet` | No guaranteed order | Hash table backed by `HashMap` | Fast membership checks |
| `LinkedHashSet` | Insertion order | Hash table plus linked list | Unique values with stable display order |
| `TreeSet` | Sorted order | Red-black tree | Range queries, floor/ceiling, sorted unique values |
| `EnumSet` | Natural enum order | Compact bit vector | Sets of enum constants |
| `CopyOnWriteArraySet` | Snapshot iteration | Copy-on-write array | Small read-heavy listener sets |

## Important Set Methods

Most important methods come from `Collection`.

| Method | Meaning | Notes |
|---|---|---|
| `add(E e)` | Adds if absent | Returns `false` when duplicate |
| `addAll(Collection)` | Adds all absent elements | Useful for union |
| `remove(Object o)` | Removes if present | Uses equality |
| `contains(Object o)` | Membership test | O(1) average in `HashSet`, O(log n) in `TreeSet` |
| `containsAll(Collection)` | Checks subset-like relation | All requested values must exist |
| `retainAll(Collection)` | Intersection | Keeps only common values |
| `removeAll(Collection)` | Difference | Removes all matching values |
| `size()` | Number of unique elements |  |
| `isEmpty()` | Whether no elements exist |  |
| `clear()` | Remove all |  |
| `iterator()` | Traverse elements | Order depends on implementation |
| `stream()` | Stream unique elements |  |

## HashSet And Equality

`HashSet` needs correct `equals()` and `hashCode()`.

Rule:

- If two objects are equal by `equals()`, they must return the same `hashCode()`.
- If two objects have the same `hashCode()`, they are not required to be equal.

Bad key classes break sets and maps.

```java
record UserId(String value) {}

Set<UserId> ids = new HashSet<>();
ids.add(new UserId("u1"));
ids.add(new UserId("u1"));
System.out.println(ids.size()); // 1
```

Records automatically implement value-based `equals()` and `hashCode()`, which makes them useful as IDs and value objects in LLD.

## LinkedHashSet

Use `LinkedHashSet` when you need uniqueness and predictable insertion order.

```java
Set<String> tags = new LinkedHashSet<>();
tags.add("java");
tags.add("lld");
tags.add("java");
System.out.println(tags); // [java, lld]
```

## TreeSet

`TreeSet` keeps elements sorted. Elements must either:

- implement `Comparable`, or
- be supplied with a `Comparator`.

```java
Set<String> sorted = new TreeSet<>();
sorted.add("z");
sorted.add("a");
sorted.add("m");
System.out.println(sorted); // [a, m, z]
```

`TreeSet` also implements `NavigableSet`, which adds methods:

| Method | Meaning |
|---|---|
| `first()` | Smallest element |
| `last()` | Largest element |
| `lower(e)` | Greatest element strictly less than `e` |
| `floor(e)` | Greatest element less than or equal to `e` |
| `ceiling(e)` | Smallest element greater than or equal to `e` |
| `higher(e)` | Smallest element strictly greater than `e` |
| `pollFirst()` | Remove and return smallest |
| `pollLast()` | Remove and return largest |
| `headSet(e)` | Elements before `e` |
| `tailSet(e)` | Elements from `e` onward |
| `subSet(a, b)` | Range view |
| `descendingSet()` | Reverse-order view |

## EnumSet

For enum values, `EnumSet` is faster and more memory-efficient than `HashSet`.

```java
enum Permission { READ, WRITE, DELETE }

Set<Permission> permissions = EnumSet.of(Permission.READ, Permission.WRITE);
```

## Mutable Element Pitfall

Never mutate fields used by `equals()` or `hashCode()` while an object is inside a `HashSet`.

```java
class MutableUser {
    String email;
    MutableUser(String email) { this.email = email; }
    public boolean equals(Object o) {
        return o instanceof MutableUser other && Objects.equals(email, other.email);
    }
    public int hashCode() {
        return Objects.hash(email);
    }
}
```

If `email` changes after insertion, the object may be stored in the wrong hash bucket and become hard to find.

## LLD Uses

- `Set<Permission>` for RBAC permissions.
- `Set<Cell>` for snake body collision checks.
- `Set<UserId>` for group members.
- `TreeSet<BookingSlot>` for sorted time-slot management.
- `EnumSet<OrderStatus>` for allowed states.

Runnable example: `src/main/java/com/codex/javaconcepts/collections/SetExamples.java`

