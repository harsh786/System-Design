# List, ArrayList, LinkedList, Vector, Stack

`List<E>` is an ordered collection. It preserves element order, supports duplicates, and allows index-based access.

## List Properties

- Ordered by position.
- Allows duplicate values.
- Allows `null` in common mutable implementations like `ArrayList` and `LinkedList`.
- Provides index operations like `get(0)`, `set(1, value)`, and `add(2, value)`.
- Equality is order-sensitive: `[A, B]` is not equal to `[B, A]`.

## Main Implementations

| Class | Internal idea | Best for | Avoid when |
|---|---|---|---|
| `ArrayList` | Resizable array | Random access, append-heavy lists | Frequent insertion/removal at front/middle |
| `LinkedList` | Doubly linked nodes | Queue/deque behavior, iterator-positioned insert/remove | Random access by index |
| `Vector` | Synchronized resizable array | Legacy code | New code usually uses `ArrayList` or concurrent collections |
| `Stack` | Legacy synchronized stack extending `Vector` | Legacy code | New stack code should use `ArrayDeque` |

## ArrayList

`ArrayList` stores elements in an internal array. When the array becomes full, Java allocates a larger array and copies elements.

Common complexity:

| Operation | Complexity |
|---|---:|
| `get(index)` | O(1) |
| `set(index, value)` | O(1) |
| `add(value)` at end | Amortized O(1) |
| `add(index, value)` | O(n) |
| `remove(index)` | O(n) |
| `contains(value)` | O(n) |

Use `ArrayList` as the default `List` implementation unless you have a clear reason not to.

## LinkedList

`LinkedList` stores each element in a node with links to previous and next nodes. It implements both `List` and `Deque`.

Common complexity:

| Operation | Complexity |
|---|---:|
| `addFirst`, `addLast` | O(1) |
| `removeFirst`, `removeLast` | O(1) |
| `get(index)` | O(n) |
| `add(index, value)` | O(n) to find index, then O(1) link update |
| `remove(index)` | O(n) to find index, then O(1) link update |

In interviews, many people overuse `LinkedList`. For most normal list use cases, `ArrayList` is faster because arrays are cache-friendly and random access is O(1).

## Important List Methods

| Method | Meaning | Notes |
|---|---|---|
| `add(E e)` | Append at end | Returns `true` for normal lists |
| `add(int index, E e)` | Insert at index | Shifts later elements in `ArrayList` |
| `addAll(Collection<? extends E> c)` | Append all | Useful for merging results |
| `addAll(int index, Collection<? extends E> c)` | Insert all at index | Order of inserted collection is preserved |
| `get(int index)` | Read element by position | O(1) for `ArrayList`, O(n) for `LinkedList` |
| `set(int index, E e)` | Replace element | Returns old value |
| `remove(int index)` | Remove by position | Returns removed element |
| `remove(Object o)` | Remove first matching object | Returns whether removed |
| `contains(Object o)` | Check existence | Uses `equals()` |
| `indexOf(Object o)` | First index of matching object | Returns `-1` if absent |
| `lastIndexOf(Object o)` | Last index of matching object | Useful with duplicates |
| `size()` | Count elements | O(1) |
| `isEmpty()` | `size() == 0` | Prefer for readability |
| `clear()` | Remove all | Leaves list reusable |
| `iterator()` | Forward traversal | Supports `iterator.remove()` |
| `listIterator()` | Forward/backward traversal | Can add/set while iterating |
| `subList(from, to)` | View of a range | Backed by original list |
| `sort(Comparator)` | Sort in place | Stable sort for object lists |
| `replaceAll(UnaryOperator)` | Replace each element | Mutates list |
| `removeIf(Predicate)` | Remove matching elements | Mutates list |
| `toArray()` | Convert to array | Use `toArray(new String[0])` for typed array |
| `equals(Object)` | Same size and pairwise equal elements | Order matters |
| `hashCode()` | Order-sensitive hash | Consistent with `equals()` |

## List Method Examples

```java
List<String> names = new ArrayList<>();
names.add("Asha");
names.add("Ravi");
names.add(1, "Meera");

String first = names.get(0);
String old = names.set(2, "Kabir");

boolean hadAsha = names.remove("Asha");
String removed = names.remove(0);

names.addAll(List.of("Zoya", "Ira"));
names.sort(Comparator.naturalOrder());
names.replaceAll(String::toUpperCase);
names.removeIf(name -> name.startsWith("Z"));
```

## `subList` Pitfall

`subList` returns a view, not a separate copy.

```java
List<String> names = new ArrayList<>(List.of("A", "B", "C", "D"));
List<String> middle = names.subList(1, 3); // [B, C]
middle.clear();
System.out.println(names); // [A, D]
```

If you need an independent list:

```java
List<String> copy = new ArrayList<>(names.subList(1, 3));
```

## `remove` Overload Pitfall

With `List<Integer>`, `remove(1)` removes by index, not by value.

```java
List<Integer> nums = new ArrayList<>(List.of(10, 20, 30));
nums.remove(1); // removes 20
nums.remove(Integer.valueOf(10)); // removes value 10
```

## `Arrays.asList`, `List.of`, And `ArrayList`

```java
List<String> fixed = Arrays.asList("A", "B");
fixed.set(0, "X");      // allowed
// fixed.add("C");      // UnsupportedOperationException

List<String> immutable = List.of("A", "B");
// immutable.set(0, "X"); // UnsupportedOperationException
// immutable.add("C");    // UnsupportedOperationException

List<String> mutable = new ArrayList<>(List.of("A", "B"));
mutable.add("C");       // allowed
```

## LLD Uses

- `List<OrderItem>` in a shopping cart where item order matters.
- `List<Rule>` in a rule engine where rules execute in configured order.
- `List<Message>` in a chat timeline.
- `ArrayList` for read-heavy ordered collections.
- `LinkedList` only when you truly need `Deque` operations or iterator-positioned inserts.

Runnable example: `src/main/java/com/codex/javaconcepts/collections/ListExamples.java`

