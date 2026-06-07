# Java List Implementations - Complete Reference for LLD Interviews

---

## 1. Collection Framework Hierarchy

```
                         Iterable<E>
                            |
                        Collection<E>
                       /      |       \
                      /       |        \
                 List<E>    Set<E>    Queue<E>
                /  |  \       |    \       |     \
               /   |   \      |     \      |      \
        ArrayList  |  Vector  |   TreeSet  |    PriorityQueue
                   |      |       |        |
            LinkedList  Stack  HashSet  Deque<E>
                   |                      |
                   |                  ArrayDeque
                   |
           (implements both List & Deque)
```

### Detailed Interface Hierarchy

```
java.lang.Iterable<E>
 └── java.util.Collection<E>
      ├── java.util.List<E>
      │    ├── java.util.ArrayList<E>
      │    ├── java.util.LinkedList<E>  (also implements Deque<E>)
      │    ├── java.util.Vector<E>
      │    │    └── java.util.Stack<E>
      │    ├── java.util.concurrent.CopyOnWriteArrayList<E>
      │    └── java.util.Collections.UnmodifiableList<E>
      │
      ├── java.util.Set<E>
      │    ├── java.util.HashSet<E>
      │    ├── java.util.LinkedHashSet<E>
      │    ├── java.util.TreeSet<E> (implements SortedSet, NavigableSet)
      │    └── java.util.concurrent.CopyOnWriteArraySet<E>
      │
      └── java.util.Queue<E>
           ├── java.util.PriorityQueue<E>
           ├── java.util.concurrent.ConcurrentLinkedQueue<E>
           └── java.util.Deque<E>
                ├── java.util.ArrayDeque<E>
                └── java.util.LinkedList<E>
```

### Key Interfaces

```java
// Iterable - provides iterator() and forEach()
public interface Iterable<T> {
    Iterator<T> iterator();
    default void forEach(Consumer<? super T> action) { }
    default Spliterator<T> spliterator() { }
}

// Collection - adds size, add, remove, contains, stream, etc.
public interface Collection<E> extends Iterable<E> {
    int size();
    boolean isEmpty();
    boolean contains(Object o);
    Iterator<E> iterator();
    Object[] toArray();
    <T> T[] toArray(T[] a);
    boolean add(E e);
    boolean remove(Object o);
    boolean containsAll(Collection<?> c);
    boolean addAll(Collection<? extends E> c);
    boolean removeAll(Collection<?> c);
    boolean retainAll(Collection<?> c);
    void clear();
    default Stream<E> stream() { }
    default Stream<E> parallelStream() { }
}
```

---

## 2. List Interface - All Methods

The `List<E>` interface extends `Collection<E>` and provides ordered, index-based access.

```java
public interface List<E> extends Collection<E> {

    // ─── Positional Access ───────────────────────────────
    E get(int index);
    E set(int index, E element);
    void add(int index, E element);
    E remove(int index);

    // ─── Search ──────────────────────────────────────────
    int indexOf(Object o);
    int lastIndexOf(Object o);

    // ─── Bulk Operations (inherited + additional) ────────
    boolean addAll(int index, Collection<? extends E> c);

    // ─── View ────────────────────────────────────────────
    List<E> subList(int fromIndex, int toIndex);

    // ─── Iterators ───────────────────────────────────────
    ListIterator<E> listIterator();
    ListIterator<E> listIterator(int index);

    // ─── Default Methods (Java 8+) ──────────────────────
    default void replaceAll(UnaryOperator<E> operator) { }
    default void sort(Comparator<? super E> c) { }

    // ─── Static Factory Methods (Java 9+) ───────────────
    static <E> List<E> of() { }
    static <E> List<E> of(E e1) { }
    static <E> List<E> of(E e1, E e2) { }
    // ... up to 10 elements
    static <E> List<E> of(E... elements) { }

    // ─── Java 10+ ───────────────────────────────────────
    static <E> List<E> copyOf(Collection<? extends E> coll) { }
}
```

### ListIterator - Bidirectional Traversal

```java
public interface ListIterator<E> extends Iterator<E> {
    boolean hasNext();
    E next();
    boolean hasPrevious();
    E previous();
    int nextIndex();
    int previousIndex();
    void remove();
    void set(E e);
    void add(E e);
}
```

---

## 3. ArrayList - Complete Coverage

### 3.1 Internal Implementation

```java
/**
 * ArrayList internally uses a resizable array (Object[]).
 *
 * Key internals:
 * - Default initial capacity: 10
 * - Growth factor: 50% (newCapacity = oldCapacity + oldCapacity >> 1)
 * - Backed by: transient Object[] elementData
 * - Uses System.arraycopy() for shifting elements
 * - Allows null elements
 * - NOT synchronized (not thread-safe)
 */
public class ArrayList<E> extends AbstractList<E>
        implements List<E>, RandomAccess, Cloneable, java.io.Serializable {

    private static final int DEFAULT_CAPACITY = 10;
    transient Object[] elementData;  // The actual storage
    private int size;                // Number of elements (not capacity)
}
```

### How Growth Works Internally

```java
// Simplified version of how ArrayList grows
private void grow(int minCapacity) {
    int oldCapacity = elementData.length;
    // New capacity = old + old/2 (50% growth)
    int newCapacity = oldCapacity + (oldCapacity >> 1);
    if (newCapacity < minCapacity)
        newCapacity = minCapacity;
    // Copy old array to new larger array
    elementData = Arrays.copyOf(elementData, newCapacity);
}

// Growth sequence: 10 → 15 → 22 → 33 → 49 → 73 → 109 → ...
```

### 3.2 All ArrayList Methods with Examples

```java
import java.util.*;
import java.util.stream.*;

public class ArrayListComplete {
    public static void main(String[] args) {

        // ═══════════════════════════════════════════════════════
        // CONSTRUCTORS
        // ═══════════════════════════════════════════════════════

        // 1. Default constructor (initial capacity 10)
        ArrayList<String> list1 = new ArrayList<>();

        // 2. With initial capacity (use when you know approximate size)
        ArrayList<String> list2 = new ArrayList<>(100);

        // 3. From another collection
        ArrayList<String> list3 = new ArrayList<>(Arrays.asList("A", "B", "C"));

        // ═══════════════════════════════════════════════════════
        // ADD OPERATIONS
        // ═══════════════════════════════════════════════════════

        ArrayList<String> fruits = new ArrayList<>();

        // add(E e) - appends to end, O(1) amortized
        fruits.add("Apple");
        fruits.add("Banana");
        fruits.add("Cherry");
        System.out.println(fruits); // [Apple, Banana, Cherry]

        // add(int index, E element) - inserts at index, O(n)
        fruits.add(1, "Avocado");
        System.out.println(fruits); // [Apple, Avocado, Banana, Cherry]

        // addAll(Collection) - appends all, O(n)
        List<String> moreFruits = Arrays.asList("Date", "Elderberry");
        fruits.addAll(moreFruits);
        System.out.println(fruits); // [Apple, Avocado, Banana, Cherry, Date, Elderberry]

        // addAll(int index, Collection) - inserts all at index, O(n)
        fruits.addAll(2, Arrays.asList("Blueberry", "Blackberry"));
        System.out.println(fruits);
        // [Apple, Avocado, Blueberry, Blackberry, Banana, Cherry, Date, Elderberry]

        // ═══════════════════════════════════════════════════════
        // GET / ACCESS OPERATIONS
        // ═══════════════════════════════════════════════════════

        // get(int index) - O(1) random access
        String first = fruits.get(0);    // "Apple"
        String third = fruits.get(2);    // "Blueberry"

        // getFirst() / getLast() - Java 21+
        // String f = fruits.getFirst();
        // String l = fruits.getLast();

        // ═══════════════════════════════════════════════════════
        // SET / UPDATE OPERATIONS
        // ═══════════════════════════════════════════════════════

        // set(int index, E element) - replaces element, returns old value, O(1)
        String old = fruits.set(0, "Apricot");
        System.out.println("Replaced: " + old);  // Replaced: Apple
        System.out.println(fruits.get(0));        // Apricot

        // ═══════════════════════════════════════════════════════
        // REMOVE OPERATIONS
        // ═══════════════════════════════════════════════════════

        // remove(int index) - removes by index, returns removed element, O(n)
        String removed = fruits.remove(0);
        System.out.println("Removed: " + removed); // Removed: Apricot

        // remove(Object o) - removes first occurrence, returns boolean, O(n)
        boolean wasRemoved = fruits.remove("Banana");
        System.out.println("Was removed: " + wasRemoved); // true

        // removeAll(Collection) - removes all elements found in collection
        fruits.removeAll(Arrays.asList("Date", "Elderberry"));

        // retainAll(Collection) - keeps only elements found in collection
        ArrayList<String> keepList = new ArrayList<>(Arrays.asList("Avocado", "Blueberry", "Blackberry", "Cherry"));
        // fruits.retainAll(Arrays.asList("Avocado", "Cherry"));

        // removeIf(Predicate) - removes elements matching condition, O(n)
        fruits.removeIf(f2 -> f2.startsWith("B"));
        System.out.println(fruits); // Elements not starting with B

        // ═══════════════════════════════════════════════════════
        // SEARCH OPERATIONS
        // ═══════════════════════════════════════════════════════

        ArrayList<String> colors = new ArrayList<>(
            Arrays.asList("Red", "Green", "Blue", "Green", "Yellow")
        );

        // indexOf(Object) - first occurrence index, -1 if not found, O(n)
        int idx = colors.indexOf("Green");
        System.out.println("First Green at: " + idx); // 1

        // lastIndexOf(Object) - last occurrence index, -1 if not found, O(n)
        int lastIdx = colors.lastIndexOf("Green");
        System.out.println("Last Green at: " + lastIdx); // 3

        // contains(Object) - checks existence, O(n)
        boolean hasBlue = colors.contains("Blue");
        System.out.println("Has Blue: " + hasBlue); // true

        // containsAll(Collection) - checks if all elements present
        boolean hasAll = colors.containsAll(Arrays.asList("Red", "Blue"));
        System.out.println("Has Red and Blue: " + hasAll); // true

        // ═══════════════════════════════════════════════════════
        // SIZE AND STATE OPERATIONS
        // ═══════════════════════════════════════════════════════

        // size() - number of elements, O(1)
        int size = colors.size();
        System.out.println("Size: " + size); // 5

        // isEmpty() - checks if size == 0, O(1)
        boolean empty = colors.isEmpty();
        System.out.println("Is empty: " + empty); // false

        // clear() - removes all elements, O(n)
        // colors.clear();

        // ═══════════════════════════════════════════════════════
        // SUBLIST
        // ═══════════════════════════════════════════════════════

        // subList(fromIndex, toIndex) - returns a VIEW (not a copy!), O(1)
        // Changes to subList reflect in original list and vice versa
        List<String> sub = colors.subList(1, 4); // [Green, Blue, Green]
        System.out.println("SubList: " + sub);

        // CAUTION: Structural modification of original list invalidates subList
        // This would throw ConcurrentModificationException:
        // colors.add("Purple");
        // sub.get(0); // THROWS!

        // To get independent copy:
        List<String> safeSub = new ArrayList<>(colors.subList(1, 4));

        // ═══════════════════════════════════════════════════════
        // TOARRAY OPERATIONS
        // ═══════════════════════════════════════════════════════

        // toArray() - returns Object[], O(n)
        Object[] objArray = colors.toArray();

        // toArray(T[]) - returns typed array, O(n)
        String[] strArray = colors.toArray(new String[0]);
        // OR (pre-sized, slightly more efficient in some cases)
        String[] strArray2 = colors.toArray(new String[colors.size()]);

        // toArray(IntFunction) - Java 11+
        // String[] strArray3 = colors.toArray(String[]::new);

        // ═══════════════════════════════════════════════════════
        // SORT OPERATIONS
        // ═══════════════════════════════════════════════════════

        ArrayList<Integer> numbers = new ArrayList<>(Arrays.asList(5, 2, 8, 1, 9, 3));

        // sort(Comparator) - sorts in-place, O(n log n) - uses TimSort
        numbers.sort(null); // natural ordering
        System.out.println("Sorted: " + numbers); // [1, 2, 3, 5, 8, 9]

        numbers.sort(Comparator.reverseOrder());
        System.out.println("Reverse: " + numbers); // [9, 8, 5, 3, 2, 1]

        // Custom sort with Comparator
        ArrayList<String> names = new ArrayList<>(
            Arrays.asList("Charlie", "Alice", "Bob", "Dave")
        );
        names.sort(Comparator.comparingInt(String::length));
        System.out.println("By length: " + names); // [Bob, Dave, Alice, Charlie]

        // Collections.sort() - alternative way
        Collections.sort(names); // natural ordering (alphabetical)

        // ═══════════════════════════════════════════════════════
        // REPLACEALL
        // ═══════════════════════════════════════════════════════

        ArrayList<String> words = new ArrayList<>(
            Arrays.asList("hello", "world", "java")
        );

        // replaceAll(UnaryOperator) - transforms each element in place
        words.replaceAll(String::toUpperCase);
        System.out.println(words); // [HELLO, WORLD, JAVA]

        words.replaceAll(w -> w.substring(0, 1) + w.substring(1).toLowerCase());
        System.out.println(words); // [Hello, World, Java]

        // ═══════════════════════════════════════════════════════
        // FOREACH
        // ═══════════════════════════════════════════════════════

        // forEach(Consumer) - performs action on each element
        colors.forEach(System.out::println);

        colors.forEach(color -> {
            System.out.println("Color: " + color.toUpperCase());
        });

        // ═══════════════════════════════════════════════════════
        // ITERATOR
        // ═══════════════════════════════════════════════════════

        // iterator() - forward-only traversal
        Iterator<String> it = colors.iterator();
        while (it.hasNext()) {
            String color = it.next();
            if (color.equals("Green")) {
                it.remove(); // SAFE removal during iteration
            }
        }

        // Enhanced for-loop (uses iterator internally)
        for (String color : colors) {
            System.out.println(color);
            // colors.remove(color); // UNSAFE! ConcurrentModificationException
        }

        // ═══════════════════════════════════════════════════════
        // LIST ITERATOR
        // ═══════════════════════════════════════════════════════

        ArrayList<String> items = new ArrayList<>(
            Arrays.asList("A", "B", "C", "D", "E")
        );

        // listIterator() - bidirectional traversal
        ListIterator<String> lit = items.listIterator();

        // Forward
        while (lit.hasNext()) {
            int index2 = lit.nextIndex();
            String item = lit.next();
            System.out.println(index2 + ": " + item);
        }

        // Backward
        while (lit.hasPrevious()) {
            int index2 = lit.previousIndex();
            String item = lit.previous();
            System.out.println(index2 + ": " + item);
        }

        // listIterator(int index) - starts at specific position
        ListIterator<String> lit2 = items.listIterator(2); // starts at index 2
        System.out.println(lit2.next()); // "C"

        // ListIterator can add and set during iteration
        ListIterator<String> lit3 = items.listIterator();
        while (lit3.hasNext()) {
            String item = lit3.next();
            if (item.equals("C")) {
                lit3.set("C_MODIFIED");  // Replace current
                lit3.add("C2");          // Add after current
            }
        }
        System.out.println(items); // [A, B, C_MODIFIED, C2, D, E]

        // ═══════════════════════════════════════════════════════
        // STREAM OPERATIONS
        // ═══════════════════════════════════════════════════════

        ArrayList<Integer> nums = new ArrayList<>(
            Arrays.asList(1, 2, 3, 4, 5, 6, 7, 8, 9, 10)
        );

        // stream() - sequential stream
        List<Integer> evens = nums.stream()
            .filter(n -> n % 2 == 0)
            .collect(Collectors.toList());
        System.out.println("Evens: " + evens); // [2, 4, 6, 8, 10]

        // map, reduce, collect
        int sum = nums.stream()
            .mapToInt(Integer::intValue)
            .sum();
        System.out.println("Sum: " + sum); // 55

        String joined = names.stream()
            .collect(Collectors.joining(", "));
        System.out.println("Joined: " + joined);

        // parallelStream() - parallel processing
        long count = nums.parallelStream()
            .filter(n -> n > 5)
            .count();
        System.out.println("Count > 5: " + count); // 5

        // ═══════════════════════════════════════════════════════
        // UTILITY METHODS
        // ═══════════════════════════════════════════════════════

        // ensureCapacity(int) - pre-allocate for performance
        ArrayList<Integer> bigList = new ArrayList<>();
        bigList.ensureCapacity(10000); // avoids multiple resizes

        // trimToSize() - shrinks internal array to current size
        bigList.addAll(Arrays.asList(1, 2, 3));
        bigList.trimToSize(); // internal array now size 3, not 10000

        // clone() - shallow copy
        ArrayList<String> original = new ArrayList<>(Arrays.asList("X", "Y", "Z"));
        @SuppressWarnings("unchecked")
        ArrayList<String> cloned = (ArrayList<String>) original.clone();
        cloned.add("W");
        System.out.println(original); // [X, Y, Z] - unaffected
        System.out.println(cloned);   // [X, Y, Z, W]

        // equals() and hashCode()
        ArrayList<Integer> l1 = new ArrayList<>(Arrays.asList(1, 2, 3));
        ArrayList<Integer> l2 = new ArrayList<>(Arrays.asList(1, 2, 3));
        System.out.println(l1.equals(l2));   // true (same elements, same order)
        System.out.println(l1.hashCode() == l2.hashCode()); // true
    }
}
```

### 3.3 ArrayList Time Complexity

| Operation | Time Complexity | Notes |
|-----------|----------------|-------|
| `get(index)` | O(1) | Direct array access |
| `set(index, element)` | O(1) | Direct array update |
| `add(element)` | O(1) amortized | O(n) when resize needed |
| `add(index, element)` | O(n) | Shifts elements right |
| `remove(index)` | O(n) | Shifts elements left |
| `remove(Object)` | O(n) | Search + shift |
| `contains(Object)` | O(n) | Linear search |
| `indexOf(Object)` | O(n) | Linear search |
| `lastIndexOf(Object)` | O(n) | Linear search from end |
| `size()` | O(1) | Stored field |
| `isEmpty()` | O(1) | Checks size == 0 |
| `clear()` | O(n) | Nulls all references |
| `addAll(Collection)` | O(n + m) | n = size, m = collection size |
| `sort()` | O(n log n) | TimSort |
| `subList()` | O(1) | Returns a view |
| `toArray()` | O(n) | Array copy |
| `iterator().next()` | O(1) | Sequential access |

### 3.4 When to Use ArrayList

```
USE ArrayList when:
  ✓ Frequent random access by index (get/set)
  ✓ Mostly appending to end
  ✓ Iterating through all elements
  ✓ Memory efficiency matters (less overhead per element)
  ✓ Cache-friendly access patterns needed

AVOID ArrayList when:
  ✗ Frequent insertions/deletions at beginning or middle
  ✗ Need constant-time insertions at both ends
  ✗ Implementing a queue or deque
```

---

## 4. LinkedList - Complete Coverage

### 4.1 Internal Implementation

```java
/**
 * LinkedList is a DOUBLY-LINKED list implementation.
 *
 * Key internals:
 * - Each element stored in a Node with prev/next pointers
 * - Maintains references to first AND last nodes
 * - Implements BOTH List<E> and Deque<E>
 * - Can be used as List, Stack, Queue, or Deque
 * - NOT synchronized
 * - Allows null elements
 */
public class LinkedList<E> extends AbstractSequentialList<E>
        implements List<E>, Deque<E>, Cloneable, java.io.Serializable {

    transient int size = 0;
    transient Node<E> first;  // pointer to first node
    transient Node<E> last;   // pointer to last node

    // Internal Node class
    private static class Node<E> {
        E item;
        Node<E> next;
        Node<E> prev;

        Node(Node<E> prev, E element, Node<E> next) {
            this.item = element;
            this.next = next;
            this.prev = prev;
        }
    }
}
```

### 4.2 All LinkedList Methods with Examples

```java
import java.util.*;

public class LinkedListComplete {
    public static void main(String[] args) {

        // ═══════════════════════════════════════════════════════
        // CONSTRUCTORS
        // ═══════════════════════════════════════════════════════

        LinkedList<String> ll1 = new LinkedList<>();
        LinkedList<String> ll2 = new LinkedList<>(Arrays.asList("A", "B", "C"));

        // ═══════════════════════════════════════════════════════
        // LIST INTERFACE METHODS (same as ArrayList)
        // ═══════════════════════════════════════════════════════

        LinkedList<String> list = new LinkedList<>();

        // add, get, set, remove, indexOf, contains, size, etc.
        // (all work same as ArrayList but with different performance)
        list.add("One");
        list.add("Two");
        list.add("Three");
        list.add(1, "OneAndHalf");
        String elem = list.get(2);      // O(n) - must traverse!
        list.set(0, "First");           // O(n) - must traverse!
        list.remove(1);                 // O(n) for finding, O(1) for unlinking
        int idx = list.indexOf("Three");

        // ═══════════════════════════════════════════════════════
        // DEQUE-SPECIFIC METHODS (LinkedList as Deque)
        // ═══════════════════════════════════════════════════════

        LinkedList<String> deque = new LinkedList<>();

        // ─── Add Operations ──────────────────────────────────

        // addFirst(E) - inserts at beginning, O(1)
        deque.addFirst("B");
        deque.addFirst("A");
        System.out.println(deque); // [A, B]

        // addLast(E) - inserts at end, O(1) (same as add())
        deque.addLast("C");
        deque.addLast("D");
        System.out.println(deque); // [A, B, C, D]

        // offerFirst(E) - inserts at beginning, returns boolean, O(1)
        boolean added1 = deque.offerFirst("Z");
        System.out.println(deque); // [Z, A, B, C, D]

        // offerLast(E) - inserts at end, returns boolean, O(1)
        boolean added2 = deque.offerLast("E");
        System.out.println(deque); // [Z, A, B, C, D, E]

        // offer(E) - inserts at tail (Queue behavior), O(1)
        deque.offer("F");
        System.out.println(deque); // [Z, A, B, C, D, E, F]

        // ─── Get/Peek Operations ─────────────────────────────

        // getFirst() - returns first, throws NoSuchElementException if empty, O(1)
        String firstElem = deque.getFirst();
        System.out.println("First: " + firstElem); // Z

        // getLast() - returns last, throws NoSuchElementException if empty, O(1)
        String lastElem = deque.getLast();
        System.out.println("Last: " + lastElem); // F

        // peek() - returns first, returns NULL if empty (no exception), O(1)
        String peeked = deque.peek();
        System.out.println("Peek: " + peeked); // Z

        // peekFirst() - same as peek(), O(1)
        String peekedFirst = deque.peekFirst();

        // peekLast() - returns last, returns NULL if empty, O(1)
        String peekedLast = deque.peekLast();

        // element() - returns first, throws NoSuchElementException if empty, O(1)
        String element2 = deque.element(); // same as getFirst()

        // ─── Remove Operations ───────────────────────────────

        // removeFirst() - removes and returns first, throws if empty, O(1)
        String removedFirst = deque.removeFirst();
        System.out.println("Removed first: " + removedFirst); // Z

        // removeLast() - removes and returns last, throws if empty, O(1)
        String removedLast = deque.removeLast();
        System.out.println("Removed last: " + removedLast); // F

        // poll() - removes and returns first, NULL if empty (no exception), O(1)
        String polled = deque.poll();
        System.out.println("Polled: " + polled); // A

        // pollFirst() - same as poll(), O(1)
        String polledFirst = deque.pollFirst();

        // pollLast() - removes and returns last, NULL if empty, O(1)
        String polledLast = deque.pollLast();

        // remove() - removes and returns first (same as removeFirst()), O(1)
        // String rem = deque.remove(); // throws if empty

        // removeFirstOccurrence(Object) - removes first match, O(n)
        deque.addAll(Arrays.asList("X", "Y", "X", "Z"));
        deque.removeFirstOccurrence("X");
        System.out.println(deque); // removed first "X"

        // removeLastOccurrence(Object) - removes last match, O(n)
        deque.removeLastOccurrence("X");

        // ═══════════════════════════════════════════════════════
        // STACK OPERATIONS (LinkedList as Stack)
        // ═══════════════════════════════════════════════════════

        LinkedList<String> stack = new LinkedList<>();

        // push(E) - pushes onto stack (adds at FRONT), O(1)
        stack.push("First");
        stack.push("Second");
        stack.push("Third");
        System.out.println(stack); // [Third, Second, First]

        // pop() - pops from stack (removes from FRONT), O(1)
        String popped = stack.pop();
        System.out.println("Popped: " + popped); // Third
        System.out.println(stack); // [Second, First]

        // peek() - looks at top without removing, O(1)
        String top = stack.peek();
        System.out.println("Top: " + top); // Second

        // ═══════════════════════════════════════════════════════
        // QUEUE OPERATIONS (LinkedList as Queue)
        // ═══════════════════════════════════════════════════════

        Queue<String> queue = new LinkedList<>();

        // offer(E) - enqueue at tail, O(1)
        queue.offer("First");
        queue.offer("Second");
        queue.offer("Third");

        // poll() - dequeue from head, O(1)
        String dequeued = queue.poll();
        System.out.println("Dequeued: " + dequeued); // First

        // peek() - look at head without removing, O(1)
        String head = queue.peek();
        System.out.println("Head: " + head); // Second

        // ═══════════════════════════════════════════════════════
        // DESCENDING ITERATOR
        // ═══════════════════════════════════════════════════════

        LinkedList<Integer> nums = new LinkedList<>(
            Arrays.asList(1, 2, 3, 4, 5)
        );

        // descendingIterator() - iterates from last to first
        Iterator<Integer> descIt = nums.descendingIterator();
        while (descIt.hasNext()) {
            System.out.print(descIt.next() + " "); // 5 4 3 2 1
        }
        System.out.println();
    }
}
```

### 4.3 LinkedList Method Summary Table

| Method | Behavior on Empty | Returns | Position | Complexity |
|--------|-------------------|---------|----------|------------|
| **Add** | | | | |
| `addFirst(e)` | - | void | Head | O(1) |
| `addLast(e)` | - | void | Tail | O(1) |
| `offerFirst(e)` | - | boolean | Head | O(1) |
| `offerLast(e)` | - | boolean | Tail | O(1) |
| `offer(e)` | - | boolean | Tail | O(1) |
| `push(e)` | - | void | Head | O(1) |
| **Examine** | | | | |
| `getFirst()` | Exception | Element | Head | O(1) |
| `getLast()` | Exception | Element | Tail | O(1) |
| `peek()` | null | Element | Head | O(1) |
| `peekFirst()` | null | Element | Head | O(1) |
| `peekLast()` | null | Element | Tail | O(1) |
| `element()` | Exception | Element | Head | O(1) |
| **Remove** | | | | |
| `removeFirst()` | Exception | Element | Head | O(1) |
| `removeLast()` | Exception | Element | Tail | O(1) |
| `poll()` | null | Element | Head | O(1) |
| `pollFirst()` | null | Element | Head | O(1) |
| `pollLast()` | null | Element | Tail | O(1) |
| `pop()` | Exception | Element | Head | O(1) |

### 4.4 LinkedList Time Complexity

| Operation | Time Complexity | Notes |
|-----------|----------------|-------|
| `addFirst(e)` / `addLast(e)` | O(1) | Direct pointer manipulation |
| `add(index, e)` | O(n) | Must traverse to index first |
| `get(index)` | O(n) | Must traverse (optimized: starts from closer end) |
| `set(index, e)` | O(n) | Must traverse first |
| `removeFirst()` / `removeLast()` | O(1) | Direct pointer manipulation |
| `remove(index)` | O(n) | Must traverse |
| `remove(Object)` | O(n) | Linear search + O(1) unlink |
| `contains(Object)` | O(n) | Linear search |
| `indexOf(Object)` | O(n) | Linear search |
| `size()` | O(1) | Stored field |
| `peek()` / `poll()` | O(1) | Head access |

---

## 5. ArrayList vs LinkedList - Complete Comparison

| Aspect | ArrayList | LinkedList |
|--------|-----------|------------|
| **Internal Structure** | Dynamic array | Doubly-linked nodes |
| **Random Access** | O(1) - direct index | O(n) - must traverse |
| **Add at end** | O(1) amortized | O(1) |
| **Add at beginning** | O(n) - shifts all | O(1) |
| **Add at middle** | O(n) - shifts half | O(n) traverse + O(1) insert |
| **Remove from end** | O(1) | O(1) |
| **Remove from beginning** | O(n) - shifts all | O(1) |
| **Memory per element** | ~4 bytes (reference) | ~24 bytes (node + 2 pointers) |
| **Cache Performance** | Excellent (contiguous) | Poor (scattered in heap) |
| **Implements** | List, RandomAccess | List, Deque |
| **Iterator remove** | O(n) - shifts | O(1) - relinks |
| **Memory allocation** | Bulk (array resize) | Per element (new Node) |
| **Null elements** | Yes | Yes |
| **Thread-safe** | No | No |

### Decision Guide

```
┌─────────────────────────────────────────────────────────────┐
│                    WHICH LIST TO USE?                         │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Need random access (get by index)?  ──→  ArrayList          │
│                                                              │
│  Mostly add/remove at ends?  ──→  LinkedList (as Deque)      │
│                                                              │
│  Need a Queue/Stack?  ──→  LinkedList or ArrayDeque          │
│                                                              │
│  Iterating + removing during iteration?  ──→  LinkedList     │
│                                                              │
│  Memory sensitive + large lists?  ──→  ArrayList             │
│                                                              │
│  Thread-safe needed?  ──→  CopyOnWriteArrayList              │
│                           or Collections.synchronizedList()   │
│                                                              │
│  95% of cases?  ──→  ArrayList (default choice)              │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 6. Vector - Legacy Synchronized List

### Why Vector Exists

```java
import java.util.*;

/**
 * Vector is the ORIGINAL List implementation from Java 1.0.
 *
 * Key differences from ArrayList:
 * 1. SYNCHRONIZED - all methods are synchronized (thread-safe but SLOW)
 * 2. Growth: doubles capacity (100%) vs ArrayList's 50%
 * 3. Legacy class - prefer ArrayList + external synchronization
 * 4. Has legacy methods: elements(), capacity(), etc.
 */
public class VectorExample {
    public static void main(String[] args) {

        // ═══════════════════════════════════════════════════════
        // CONSTRUCTORS
        // ═══════════════════════════════════════════════════════

        Vector<String> v1 = new Vector<>();            // default capacity 10
        Vector<String> v2 = new Vector<>(20);          // initial capacity 20
        Vector<String> v3 = new Vector<>(20, 5);       // capacity 20, increment by 5
        Vector<String> v4 = new Vector<>(Arrays.asList("A", "B"));

        // ═══════════════════════════════════════════════════════
        // ALL STANDARD LIST METHODS (same as ArrayList, but synchronized)
        // ═══════════════════════════════════════════════════════

        Vector<String> vec = new Vector<>();
        vec.add("One");
        vec.add("Two");
        vec.add(0, "Zero");
        vec.get(1);           // "One"
        vec.set(1, "Uno");
        vec.remove(0);
        vec.size();
        vec.isEmpty();
        vec.contains("Two");
        vec.indexOf("Two");

        // ═══════════════════════════════════════════════════════
        // LEGACY METHODS (unique to Vector)
        // ═══════════════════════════════════════════════════════

        // elements() - legacy Enumeration (predecessor of Iterator)
        Enumeration<String> enumeration = vec.elements();
        while (enumeration.hasMoreElements()) {
            System.out.println(enumeration.nextElement());
        }

        // capacity() - current internal array capacity
        System.out.println("Capacity: " + vec.capacity());

        // elementAt(int) - same as get(int), legacy name
        // String e = vec.elementAt(0);

        // firstElement() / lastElement()
        // String first = vec.firstElement();
        // String last = vec.lastElement();

        // setElementAt(E, int) - legacy set()
        // vec.setElementAt("New", 0);

        // insertElementAt(E, int) - legacy add(int, E)
        // vec.insertElementAt("Inserted", 1);

        // removeElementAt(int) - legacy remove(int)
        // vec.removeElementAt(0);

        // removeAllElements() - legacy clear()
        // vec.removeAllElements();

        // copyInto(Object[]) - copy elements to array
        // String[] arr = new String[vec.size()];
        // vec.copyInto(arr);

        // ═══════════════════════════════════════════════════════
        // WHY NOT TO USE VECTOR
        // ═══════════════════════════════════════════════════════

        /*
         * Problems with Vector:
         *
         * 1. COARSE-GRAINED SYNCHRONIZATION:
         *    - Every single method call acquires a lock
         *    - Even read operations lock the entire vector
         *    - Compound operations (check-then-act) are still NOT atomic
         *
         * 2. PERFORMANCE:
         *    - Lock overhead on EVERY operation, even single-threaded
         *    - Cannot be optimized by JIT as well
         *
         * 3. COMPOUND OPERATIONS ARE STILL UNSAFE:
         */

        // THIS IS NOT THREAD-SAFE even with Vector!
        Vector<String> unsafeVec = new Vector<>();
        unsafeVec.add("item");
        // Thread A: if (!unsafeVec.isEmpty()) {
        // Thread B: unsafeVec.clear();
        // Thread A:     unsafeVec.get(0);  // BOOM! IndexOutOfBoundsException
        // }

        // BETTER ALTERNATIVES:
        // 1. ArrayList + Collections.synchronizedList()
        List<String> syncList = Collections.synchronizedList(new ArrayList<>());

        // 2. CopyOnWriteArrayList (for read-heavy workloads)
        // 3. Concurrent collections from java.util.concurrent
    }
}
```

### Vector vs ArrayList

| Aspect | Vector | ArrayList |
|--------|--------|-----------|
| Synchronization | Every method synchronized | Not synchronized |
| Growth Factor | Doubles (100%) | 50% increase |
| Performance | Slower (lock overhead) | Faster |
| Thread Safety | Method-level only | None |
| Legacy Methods | Yes (elements, etc.) | No |
| Status | Legacy (since Java 1.0) | Preferred (since Java 1.2) |

---

## 7. CopyOnWriteArrayList - Thread-Safe List

```java
import java.util.concurrent.*;
import java.util.*;

/**
 * CopyOnWriteArrayList - Thread-safe variant of ArrayList.
 *
 * Key behavior:
 * - All WRITE operations create a NEW COPY of the internal array
 * - READ operations work on the CURRENT snapshot (no locking needed)
 * - Iterators NEVER throw ConcurrentModificationException
 * - Iterators reflect the state at the time they were created
 * - Best for READ-HEAVY, WRITE-RARE scenarios
 */
public class CopyOnWriteArrayListExample {
    public static void main(String[] args) {

        // ═══════════════════════════════════════════════════════
        // CREATION
        // ═══════════════════════════════════════════════════════

        CopyOnWriteArrayList<String> cowList = new CopyOnWriteArrayList<>();
        CopyOnWriteArrayList<String> cowList2 = new CopyOnWriteArrayList<>(
            Arrays.asList("A", "B", "C")
        );

        // ═══════════════════════════════════════════════════════
        // ALL LIST METHODS WORK (same API as ArrayList)
        // ═══════════════════════════════════════════════════════

        cowList.add("One");
        cowList.add("Two");
        cowList.add("Three");
        cowList.get(0);
        cowList.set(1, "TWO");
        cowList.remove(0);
        cowList.size();

        // ═══════════════════════════════════════════════════════
        // UNIQUE METHODS
        // ═══════════════════════════════════════════════════════

        // addIfAbsent(E) - adds only if not already present
        boolean added = cowList.addIfAbsent("Two"); // false - already exists
        boolean added2 = cowList.addIfAbsent("Four"); // true - added

        // addAllAbsent(Collection) - adds only elements not already present
        int numAdded = cowList.addAllAbsent(Arrays.asList("Five", "Two", "Six"));
        System.out.println("Added: " + numAdded); // 2 (Five and Six)

        // ═══════════════════════════════════════════════════════
        // SAFE ITERATION (never throws ConcurrentModificationException)
        // ═══════════════════════════════════════════════════════

        // This is SAFE - iterator sees snapshot at creation time
        for (String item : cowList) {
            cowList.add("NewItem"); // Modifying during iteration is SAFE
            System.out.println(item); // Won't see "NewItem"
        }

        // Iterator does NOT support remove()
        Iterator<String> it = cowList.iterator();
        while (it.hasNext()) {
            it.next();
            // it.remove(); // THROWS UnsupportedOperationException!
        }

        // ═══════════════════════════════════════════════════════
        // CONCURRENT ACCESS EXAMPLE
        // ═══════════════════════════════════════════════════════

        CopyOnWriteArrayList<String> sharedList = new CopyOnWriteArrayList<>();
        sharedList.addAll(Arrays.asList("Event1", "Event2", "Event3"));

        // Multiple readers - no synchronization needed
        Runnable reader = () -> {
            for (String event : sharedList) {
                System.out.println(Thread.currentThread().getName() + " read: " + event);
            }
        };

        // Writer - creates new internal array copy
        Runnable writer = () -> {
            sharedList.add("Event" + (sharedList.size() + 1));
            System.out.println(Thread.currentThread().getName() + " wrote");
        };

        // Both can run simultaneously without issues
        Thread t1 = new Thread(reader, "Reader-1");
        Thread t2 = new Thread(reader, "Reader-2");
        Thread t3 = new Thread(writer, "Writer-1");
        t1.start(); t2.start(); t3.start();

        // ═══════════════════════════════════════════════════════
        // WHEN TO USE
        // ═══════════════════════════════════════════════════════

        /*
         * USE CopyOnWriteArrayList when:
         *   ✓ Reads vastly outnumber writes
         *   ✓ List is small (copies are cheap)
         *   ✓ Need safe iteration without external locking
         *   ✓ Event listener lists
         *   ✓ Observer pattern (subscribers rarely change)
         *   ✓ Configuration lists that change rarely
         *
         * AVOID when:
         *   ✗ Frequent writes (each write copies entire array)
         *   ✗ Large lists (copy cost is high)
         *   ✗ Need iterator.remove()
         *   ✗ Memory-constrained (keeps multiple copies briefly)
         */
    }
}
```

### CopyOnWriteArrayList Complexity

| Operation | Time | Space |
|-----------|------|-------|
| `get(index)` | O(1) | - |
| `add(element)` | O(n) | O(n) - new array copy |
| `set(index, e)` | O(n) | O(n) - new array copy |
| `remove(index)` | O(n) | O(n) - new array copy |
| `contains(Object)` | O(n) | - |
| `iterator()` | O(1) | Snapshot (no copy) |
| `size()` | O(1) | - |

---

## 8. Immutable Lists

```java
import java.util.*;

public class ImmutableListExamples {
    public static void main(String[] args) {

        // ═══════════════════════════════════════════════════════
        // METHOD 1: List.of() - Java 9+ (truly immutable)
        // ═══════════════════════════════════════════════════════

        List<String> immutable1 = List.of("A", "B", "C");

        // immutable1.add("D");     // UnsupportedOperationException
        // immutable1.set(0, "X");  // UnsupportedOperationException
        // immutable1.remove(0);    // UnsupportedOperationException

        // Characteristics:
        // - Null elements NOT allowed: List.of("A", null) → NullPointerException
        // - Duplicate elements ARE allowed: List.of("A", "A") → OK
        // - Serializable
        // - Iteration order matches insertion order
        // - Value-based equality (two lists with same elements are equal)

        // Empty immutable list
        List<String> emptyList = List.of();

        // ═══════════════════════════════════════════════════════
        // METHOD 2: List.copyOf() - Java 10+ (immutable copy)
        // ═══════════════════════════════════════════════════════

        ArrayList<String> mutable = new ArrayList<>(Arrays.asList("X", "Y", "Z"));
        List<String> immutableCopy = List.copyOf(mutable);

        mutable.add("W");  // original modified
        System.out.println(immutableCopy); // [X, Y, Z] - copy unaffected

        // Null elements NOT allowed in source

        // ═══════════════════════════════════════════════════════
        // METHOD 3: Collections.unmodifiableList() - Unmodifiable VIEW
        // ═══════════════════════════════════════════════════════

        ArrayList<String> original = new ArrayList<>(Arrays.asList("1", "2", "3"));
        List<String> unmodifiable = Collections.unmodifiableList(original);

        // unmodifiable.add("4"); // UnsupportedOperationException
        // unmodifiable.set(0, "X"); // UnsupportedOperationException

        // BUT: changes to original ARE reflected!
        original.add("4");
        System.out.println(unmodifiable); // [1, 2, 3, 4] ← CAUTION!

        // To make a truly independent unmodifiable list:
        List<String> trulyUnmodifiable = Collections.unmodifiableList(
            new ArrayList<>(original)
        );

        // Characteristics:
        // - Null elements allowed (if source has them)
        // - Is a VIEW, not a copy
        // - Changes to backing list are visible

        // ═══════════════════════════════════════════════════════
        // METHOD 4: Collections.singletonList() - Single element
        // ═══════════════════════════════════════════════════════

        List<String> single = Collections.singletonList("Only");
        // single.add("Another"); // UnsupportedOperationException

        // ═══════════════════════════════════════════════════════
        // METHOD 5: Collections.emptyList() - Empty immutable
        // ═══════════════════════════════════════════════════════

        List<String> empty = Collections.emptyList();
        // empty.add("X"); // UnsupportedOperationException

        // ═══════════════════════════════════════════════════════
        // METHOD 6: Stream.toUnmodifiableList() - Java 16+
        // ═══════════════════════════════════════════════════════

        List<Integer> nums = Arrays.asList(1, 2, 3, 4, 5);
        List<Integer> immutableFiltered = nums.stream()
            .filter(n -> n > 2)
            .toList(); // Java 16+ (returns unmodifiable list)

        // ═══════════════════════════════════════════════════════
        // COMPARISON TABLE
        // ═══════════════════════════════════════════════════════

        /*
         * ┌──────────────────────────────┬───────────┬───────────┬──────────────┐
         * │ Method                        │ Nulls OK? │ Is Copy?  │ Truly Immut? │
         * ├──────────────────────────────┼───────────┼───────────┼──────────────┤
         * │ List.of()                     │ No        │ N/A       │ Yes          │
         * │ List.copyOf()                 │ No        │ Yes       │ Yes          │
         * │ Collections.unmodifiableList()│ Yes       │ No (view) │ No (view)    │
         * │ Collections.singletonList()   │ Yes       │ N/A       │ Yes          │
         * │ Collections.emptyList()       │ N/A       │ N/A       │ Yes          │
         * │ stream().toList()             │ No        │ Yes       │ Yes          │
         * └──────────────────────────────┴───────────┴───────────┴──────────────┘
         */
    }
}
```

---

## 9. Common Patterns & Utilities

### Converting Between Collection Types

```java
import java.util.*;
import java.util.stream.*;

public class ConversionPatterns {
    public static void main(String[] args) {

        // Array → List
        String[] arr = {"A", "B", "C"};
        List<String> list1 = Arrays.asList(arr);          // Fixed-size (backed by array)
        List<String> list2 = new ArrayList<>(Arrays.asList(arr)); // Mutable copy
        List<String> list3 = List.of(arr);                 // Immutable (Java 9+)

        // List → Array
        List<String> list = new ArrayList<>(Arrays.asList("X", "Y", "Z"));
        String[] array1 = list.toArray(new String[0]);
        // String[] array2 = list.toArray(String[]::new); // Java 11+

        // List → Set (removes duplicates)
        List<String> withDups = Arrays.asList("A", "B", "A", "C", "B");
        Set<String> set = new LinkedHashSet<>(withDups); // preserves order
        List<String> noDups = new ArrayList<>(set);

        // Set → List
        Set<Integer> intSet = new TreeSet<>(Arrays.asList(3, 1, 2));
        List<Integer> fromSet = new ArrayList<>(intSet); // [1, 2, 3]

        // Stream → List
        List<Integer> fromStream = IntStream.rangeClosed(1, 10)
            .boxed()
            .collect(Collectors.toList());

        // List → Map (using streams)
        List<String> names = Arrays.asList("Alice", "Bob", "Charlie");
        Map<Integer, String> nameByLength = names.stream()
            .collect(Collectors.toMap(String::length, s -> s, (a, b) -> a));

        // Primitive array → List
        int[] primitives = {1, 2, 3, 4, 5};
        List<Integer> boxed = Arrays.stream(primitives)
            .boxed()
            .collect(Collectors.toList());
    }
}
```

### Sorting Patterns

```java
import java.util.*;

public class SortingPatterns {

    record Employee(String name, int age, double salary) {}

    public static void main(String[] args) {
        List<Employee> employees = new ArrayList<>(Arrays.asList(
            new Employee("Alice", 30, 75000),
            new Employee("Bob", 25, 65000),
            new Employee("Charlie", 35, 85000),
            new Employee("Dave", 25, 70000)
        ));

        // Sort by single field
        employees.sort(Comparator.comparing(Employee::name));

        // Sort by age descending
        employees.sort(Comparator.comparingInt(Employee::age).reversed());

        // Multi-level sort: by age, then by salary descending
        employees.sort(
            Comparator.comparingInt(Employee::age)
                .thenComparing(Comparator.comparingDouble(Employee::salary).reversed())
        );

        // Null-safe sorting
        List<String> withNulls = new ArrayList<>(Arrays.asList("B", null, "A", null, "C"));
        withNulls.sort(Comparator.nullsFirst(Comparator.naturalOrder()));
        // [null, null, A, B, C]

        withNulls.sort(Comparator.nullsLast(Comparator.naturalOrder()));
        // [A, B, C, null, null]

        // Custom comparator with lambda
        employees.sort((e1, e2) -> Double.compare(e2.salary(), e1.salary()));

        // Binary search (list MUST be sorted first)
        List<Integer> sorted = Arrays.asList(1, 3, 5, 7, 9, 11, 13);
        int index = Collections.binarySearch(sorted, 7); // returns 3
        int notFound = Collections.binarySearch(sorted, 6); // returns -(insertion point) - 1
    }
}
```

---

## 10. LLD Interview Usage Examples

### Example 1: Parking Lot System

```java
import java.util.*;
import java.util.stream.*;

public class ParkingLotSystem {

    enum VehicleType { MOTORCYCLE, CAR, TRUCK }
    enum SpotStatus { AVAILABLE, OCCUPIED }

    static class ParkingSpot {
        private final int spotId;
        private final VehicleType type;
        private SpotStatus status;
        private Vehicle parkedVehicle;

        ParkingSpot(int spotId, VehicleType type) {
            this.spotId = spotId;
            this.type = type;
            this.status = SpotStatus.AVAILABLE;
        }

        // Getters and setters
        int getSpotId() { return spotId; }
        VehicleType getType() { return type; }
        SpotStatus getStatus() { return status; }
        boolean isAvailable() { return status == SpotStatus.AVAILABLE; }

        void park(Vehicle vehicle) {
            this.parkedVehicle = vehicle;
            this.status = SpotStatus.OCCUPIED;
        }

        Vehicle unpark() {
            Vehicle v = this.parkedVehicle;
            this.parkedVehicle = null;
            this.status = SpotStatus.AVAILABLE;
            return v;
        }
    }

    static class Vehicle {
        private final String licensePlate;
        private final VehicleType type;

        Vehicle(String licensePlate, VehicleType type) {
            this.licensePlate = licensePlate;
            this.type = type;
        }

        String getLicensePlate() { return licensePlate; }
        VehicleType getType() { return type; }
    }

    static class ParkingFloor {
        private final int floorNumber;
        // ArrayList for spots - fast random access by index
        private final List<ParkingSpot> spots;

        ParkingFloor(int floorNumber, int numCarSpots, int numBikeSpots) {
            this.floorNumber = floorNumber;
            // Pre-sized ArrayList since we know the count
            this.spots = new ArrayList<>(numCarSpots + numBikeSpots);

            int id = 0;
            for (int i = 0; i < numCarSpots; i++) {
                spots.add(new ParkingSpot(id++, VehicleType.CAR));
            }
            for (int i = 0; i < numBikeSpots; i++) {
                spots.add(new ParkingSpot(id++, VehicleType.MOTORCYCLE));
            }
        }

        // Using streams to find available spot
        Optional<ParkingSpot> findAvailableSpot(VehicleType type) {
            return spots.stream()
                .filter(spot -> spot.getType() == type && spot.isAvailable())
                .findFirst();
        }

        // Count available spots using stream
        long getAvailableCount(VehicleType type) {
            return spots.stream()
                .filter(spot -> spot.getType() == type && spot.isAvailable())
                .count();
        }

        List<ParkingSpot> getSpots() { return Collections.unmodifiableList(spots); }
    }

    static class ParkingLot {
        // ArrayList of floors - indexed access, rarely changes
        private final List<ParkingFloor> floors;
        // Track parked vehicles for O(1) lookup
        private final Map<String, ParkingSpot> vehicleSpotMap;

        ParkingLot(int numFloors, int spotsPerFloor) {
            this.floors = new ArrayList<>(numFloors);
            this.vehicleSpotMap = new HashMap<>();

            for (int i = 0; i < numFloors; i++) {
                floors.add(new ParkingFloor(i, spotsPerFloor / 2, spotsPerFloor / 2));
            }
        }

        public boolean parkVehicle(Vehicle vehicle) {
            // Search each floor for available spot
            for (ParkingFloor floor : floors) {
                Optional<ParkingSpot> spot = floor.findAvailableSpot(vehicle.getType());
                if (spot.isPresent()) {
                    spot.get().park(vehicle);
                    vehicleSpotMap.put(vehicle.getLicensePlate(), spot.get());
                    return true;
                }
            }
            return false; // No spot available
        }

        public Vehicle unparkVehicle(String licensePlate) {
            ParkingSpot spot = vehicleSpotMap.remove(licensePlate);
            if (spot != null) {
                return spot.unpark();
            }
            return null;
        }

        // Display availability using forEach
        public void displayAvailability() {
            floors.forEach(floor -> {
                System.out.printf("Floor %d - Cars: %d, Bikes: %d%n",
                    floors.indexOf(floor),
                    floor.getAvailableCount(VehicleType.CAR),
                    floor.getAvailableCount(VehicleType.MOTORCYCLE));
            });
        }
    }

    public static void main(String[] args) {
        ParkingLot lot = new ParkingLot(3, 20);
        lot.parkVehicle(new Vehicle("ABC-123", VehicleType.CAR));
        lot.parkVehicle(new Vehicle("XYZ-789", VehicleType.MOTORCYCLE));
        lot.displayAvailability();
        lot.unparkVehicle("ABC-123");
    }
}
```

### Example 2: Order Management System

```java
import java.util.*;
import java.util.concurrent.*;
import java.util.stream.*;
import java.time.LocalDateTime;

public class OrderManagementSystem {

    enum OrderStatus { CREATED, CONFIRMED, PROCESSING, SHIPPED, DELIVERED, CANCELLED }

    static class OrderItem {
        private final String productId;
        private final String productName;
        private final int quantity;
        private final double price;

        OrderItem(String productId, String productName, int quantity, double price) {
            this.productId = productId;
            this.productName = productName;
            this.quantity = quantity;
            this.price = price;
        }

        double getTotal() { return quantity * price; }
        String getProductId() { return productId; }
        String getProductName() { return productName; }
        int getQuantity() { return quantity; }
        double getPrice() { return price; }
    }

    static class Order {
        private final String orderId;
        private final String customerId;
        // ArrayList for order items - random access, rarely removed
        private final List<OrderItem> items;
        // LinkedList for status history - only appends, iterate all
        private final LinkedList<StatusChange> statusHistory;
        private OrderStatus currentStatus;
        private final LocalDateTime createdAt;

        Order(String orderId, String customerId) {
            this.orderId = orderId;
            this.customerId = customerId;
            this.items = new ArrayList<>();
            this.statusHistory = new LinkedList<>();
            this.currentStatus = OrderStatus.CREATED;
            this.createdAt = LocalDateTime.now();
            addStatusChange(OrderStatus.CREATED, "Order created");
        }

        // Add item - O(1) amortized with ArrayList
        void addItem(OrderItem item) {
            items.add(item);
        }

        // Remove item by productId - O(n) search
        boolean removeItem(String productId) {
            return items.removeIf(item -> item.getProductId().equals(productId));
        }

        // Calculate total using stream
        double getTotal() {
            return items.stream()
                .mapToDouble(OrderItem::getTotal)
                .sum();
        }

        // Status transition - uses LinkedList for efficient append
        void updateStatus(OrderStatus newStatus, String note) {
            this.currentStatus = newStatus;
            addStatusChange(newStatus, note);
        }

        private void addStatusChange(OrderStatus status, String note) {
            statusHistory.addLast(new StatusChange(status, LocalDateTime.now(), note));
        }

        // Get latest status change - O(1) with LinkedList
        StatusChange getLatestStatusChange() {
            return statusHistory.getLast();
        }

        // Get status history as unmodifiable list
        List<StatusChange> getStatusHistory() {
            return Collections.unmodifiableList(statusHistory);
        }

        // Get items as unmodifiable list
        List<OrderItem> getItems() {
            return Collections.unmodifiableList(items);
        }

        String getOrderId() { return orderId; }
        String getCustomerId() { return customerId; }
        OrderStatus getCurrentStatus() { return currentStatus; }
    }

    record StatusChange(OrderStatus status, LocalDateTime timestamp, String note) {}

    static class OrderService {
        // Use CopyOnWriteArrayList for order event listeners
        // (observers rarely change, notified frequently)
        private final CopyOnWriteArrayList<OrderEventListener> listeners;
        private final Map<String, Order> orders;

        OrderService() {
            this.listeners = new CopyOnWriteArrayList<>();
            this.orders = new ConcurrentHashMap<>();
        }

        // Register listener - thread-safe
        void addEventListener(OrderEventListener listener) {
            listeners.addIfAbsent(listener);
        }

        void removeEventListener(OrderEventListener listener) {
            listeners.remove(listener);
        }

        // Create order
        Order createOrder(String customerId, List<OrderItem> items) {
            String orderId = UUID.randomUUID().toString();
            Order order = new Order(orderId, customerId);

            // addAll - bulk operation
            items.forEach(order::addItem);
            orders.put(orderId, order);

            // Notify listeners - safe iteration with CopyOnWriteArrayList
            notifyListeners(order, "ORDER_CREATED");
            return order;
        }

        // Get orders by customer - stream filtering
        List<Order> getOrdersByCustomer(String customerId) {
            return orders.values().stream()
                .filter(o -> o.getCustomerId().equals(customerId))
                .sorted(Comparator.comparing(o -> o.createdAt))
                .collect(Collectors.toList());
        }

        // Get orders by status
        List<Order> getOrdersByStatus(OrderStatus status) {
            return orders.values().stream()
                .filter(o -> o.getCurrentStatus() == status)
                .collect(Collectors.toList());
        }

        // Get top orders by value
        List<Order> getTopOrders(int limit) {
            return orders.values().stream()
                .sorted(Comparator.comparingDouble(Order::getTotal).reversed())
                .limit(limit)
                .collect(Collectors.toList());
        }

        private void notifyListeners(Order order, String event) {
            // CopyOnWriteArrayList makes this safe without synchronization
            for (OrderEventListener listener : listeners) {
                listener.onOrderEvent(order, event);
            }
        }
    }

    interface OrderEventListener {
        void onOrderEvent(Order order, String event);
    }

    public static void main(String[] args) {
        OrderService service = new OrderService();

        // Register listener
        service.addEventListener((order, event) ->
            System.out.println("Event: " + event + " for order: " + order.getOrderId()));

        // Create order with items
        List<OrderItem> items = List.of(
            new OrderItem("P1", "Laptop", 1, 999.99),
            new OrderItem("P2", "Mouse", 2, 29.99),
            new OrderItem("P3", "Keyboard", 1, 79.99)
        );

        Order order = service.createOrder("CUST-001", items);
        System.out.println("Order total: $" + order.getTotal());
        System.out.println("Items: " + order.getItems().size());

        // Update status
        order.updateStatus(OrderStatus.CONFIRMED, "Payment confirmed");
        order.updateStatus(OrderStatus.PROCESSING, "Picking items");

        // Print status history
        order.getStatusHistory().forEach(sc ->
            System.out.println(sc.status() + " at " + sc.timestamp() + ": " + sc.note()));
    }
}
```

### Example 3: LRU Cache using LinkedList

```java
import java.util.*;

/**
 * LRU Cache implementation demonstrating LinkedList usage.
 * LinkedList chosen because:
 * - O(1) removal from any position (given node reference)
 * - O(1) add to front/back
 * - Maintains insertion/access order
 */
public class LRUCache<K, V> {
    private final int capacity;
    private final Map<K, Node<K, V>> map;
    private final LinkedList<Node<K, V>> dll; // Doubly-linked list for ordering

    static class Node<K, V> {
        K key;
        V value;

        Node(K key, V value) {
            this.key = key;
            this.value = value;
        }
    }

    public LRUCache(int capacity) {
        this.capacity = capacity;
        this.map = new HashMap<>();
        this.dll = new LinkedList<>();
    }

    // Get: O(1) map lookup + O(n) list reorder
    // (In production, use custom DLL node for O(1) reorder)
    public V get(K key) {
        if (!map.containsKey(key)) return null;

        Node<K, V> node = map.get(key);
        // Move to front (most recently used)
        dll.remove(node);      // O(n) with Java's LinkedList
        dll.addFirst(node);    // O(1)
        return node.value;
    }

    // Put: O(1) amortized
    public void put(K key, V value) {
        if (map.containsKey(key)) {
            Node<K, V> node = map.get(key);
            node.value = value;
            dll.remove(node);
            dll.addFirst(node);
        } else {
            if (dll.size() >= capacity) {
                // Remove least recently used (last element)
                Node<K, V> lru = dll.removeLast(); // O(1)
                map.remove(lru.key);
            }
            Node<K, V> newNode = new Node<>(key, value);
            dll.addFirst(newNode);  // O(1)
            map.put(key, newNode);
        }
    }

    public int size() { return map.size(); }

    @Override
    public String toString() {
        StringBuilder sb = new StringBuilder("[");
        for (Node<K, V> node : dll) {
            sb.append(node.key).append("=").append(node.value).append(", ");
        }
        if (!dll.isEmpty()) sb.setLength(sb.length() - 2);
        sb.append("]");
        return sb.toString();
    }

    public static void main(String[] args) {
        LRUCache<Integer, String> cache = new LRUCache<>(3);
        cache.put(1, "One");
        cache.put(2, "Two");
        cache.put(3, "Three");
        System.out.println(cache); // [3=Three, 2=Two, 1=One]

        cache.get(1); // Access 1, moves to front
        System.out.println(cache); // [1=One, 3=Three, 2=Two]

        cache.put(4, "Four"); // Evicts 2 (least recently used)
        System.out.println(cache); // [4=Four, 1=One, 3=Three]
    }
}
```

### Example 4: Task Scheduler (Queue behavior with LinkedList)

```java
import java.util.*;
import java.time.LocalDateTime;

public class TaskScheduler {

    enum Priority { HIGH, MEDIUM, LOW }

    static class Task {
        private final String taskId;
        private final String description;
        private final Priority priority;
        private final LocalDateTime scheduledAt;

        Task(String taskId, String description, Priority priority) {
            this.taskId = taskId;
            this.description = description;
            this.priority = priority;
            this.scheduledAt = LocalDateTime.now();
        }

        String getTaskId() { return taskId; }
        Priority getPriority() { return priority; }

        @Override
        public String toString() {
            return String.format("[%s] %s (%s)", taskId, description, priority);
        }
    }

    // Using LinkedList as a Deque for task queues
    private final LinkedList<Task> highPriorityQueue;
    private final LinkedList<Task> mediumPriorityQueue;
    private final LinkedList<Task> lowPriorityQueue;
    // History of completed tasks - only appends
    private final LinkedList<Task> completedTasks;

    public TaskScheduler() {
        this.highPriorityQueue = new LinkedList<>();
        this.mediumPriorityQueue = new LinkedList<>();
        this.lowPriorityQueue = new LinkedList<>();
        this.completedTasks = new LinkedList<>();
    }

    // Enqueue task to appropriate priority queue
    public void submit(Task task) {
        switch (task.getPriority()) {
            case HIGH -> highPriorityQueue.offer(task);    // O(1) - add to tail
            case MEDIUM -> mediumPriorityQueue.offer(task);
            case LOW -> lowPriorityQueue.offer(task);
        }
    }

    // Dequeue next task (highest priority first)
    public Task getNext() {
        Task task = highPriorityQueue.poll();     // O(1) - remove from head
        if (task == null) task = mediumPriorityQueue.poll();
        if (task == null) task = lowPriorityQueue.poll();
        return task;
    }

    // Process next task
    public void processNext() {
        Task task = getNext();
        if (task != null) {
            System.out.println("Processing: " + task);
            completedTasks.addLast(task);  // O(1)
        } else {
            System.out.println("No tasks to process");
        }
    }

    // Peek at next without removing
    public Task peekNext() {
        Task task = highPriorityQueue.peek();    // O(1)
        if (task == null) task = mediumPriorityQueue.peek();
        if (task == null) task = lowPriorityQueue.peek();
        return task;
    }

    // Get total pending count
    public int getPendingCount() {
        return highPriorityQueue.size() +
               mediumPriorityQueue.size() +
               lowPriorityQueue.size();
    }

    // Get last N completed tasks
    public List<Task> getRecentCompleted(int n) {
        // Use descendingIterator for efficient last-N access
        List<Task> recent = new ArrayList<>(n);
        Iterator<Task> descIt = completedTasks.descendingIterator();
        while (descIt.hasNext() && recent.size() < n) {
            recent.add(descIt.next());
        }
        return recent;
    }

    public static void main(String[] args) {
        TaskScheduler scheduler = new TaskScheduler();

        scheduler.submit(new Task("T1", "Fix critical bug", Priority.HIGH));
        scheduler.submit(new Task("T2", "Write docs", Priority.LOW));
        scheduler.submit(new Task("T3", "Code review", Priority.MEDIUM));
        scheduler.submit(new Task("T4", "Deploy hotfix", Priority.HIGH));
        scheduler.submit(new Task("T5", "Update deps", Priority.LOW));

        System.out.println("Pending: " + scheduler.getPendingCount());

        // Process all in priority order
        while (scheduler.getPendingCount() > 0) {
            scheduler.processNext();
        }
        // Output:
        // Processing: [T1] Fix critical bug (HIGH)
        // Processing: [T4] Deploy hotfix (HIGH)
        // Processing: [T3] Code review (MEDIUM)
        // Processing: [T2] Write docs (LOW)
        // Processing: [T5] Update deps (LOW)
    }
}
```

---

## 11. Common Interview Questions

### Q1: How does ArrayList internally grow?

```java
/**
 * When add() is called and internal array is full:
 * 1. Calculate new capacity: oldCapacity + (oldCapacity >> 1)  → 50% growth
 * 2. Create new array of new capacity
 * 3. Copy all elements using Arrays.copyOf() (internally System.arraycopy)
 * 4. Point elementData to new array
 *
 * Growth sequence starting from default 10:
 * 10 → 15 → 22 → 33 → 49 → 73 → 109 → 163 → ...
 *
 * This is why add() is "amortized O(1)" - occasionally O(n) for resize,
 * but averaged over all operations, it's O(1).
 */
```

### Q2: What happens when you call `remove(int)` on ArrayList vs `remove(Object)`?

```java
public class RemoveGotcha {
    public static void main(String[] args) {
        // TRAP with Integer lists!
        ArrayList<Integer> nums = new ArrayList<>(Arrays.asList(10, 20, 30));

        nums.remove(1);           // Removes element at INDEX 1 → removes 20
        System.out.println(nums); // [10, 30]

        nums.remove(Integer.valueOf(10)); // Removes OBJECT 10
        System.out.println(nums);         // [30]

        // If you want to remove by value, use Integer.valueOf() or (Integer) cast
    }
}
```

### Q3: ArrayList vs LinkedList - Memory usage

```java
/**
 * ArrayList memory per element:
 *   - 4 bytes (object reference in array)
 *   - Plus unused capacity slots
 *   - Total per element: ~4 bytes + overhead
 *
 * LinkedList memory per element (each Node):
 *   - 16 bytes (Node object header - depends on JVM/arch)
 *   - 8 bytes (reference to item)
 *   - 8 bytes (reference to next)
 *   - 8 bytes (reference to prev)
 *   - Total per element: ~40 bytes (on 64-bit JVM)
 *
 * LinkedList uses ~10x more memory per element!
 *
 * For 1 million integers:
 *   ArrayList: ~4 MB + some overhead
 *   LinkedList: ~40 MB
 */
```

### Q4: Is ArrayList fail-fast? Explain ConcurrentModificationException

```java
public class FailFastDemo {
    public static void main(String[] args) {
        ArrayList<String> list = new ArrayList<>(Arrays.asList("A", "B", "C", "D"));

        // THIS WILL THROW ConcurrentModificationException
        try {
            for (String item : list) {
                if (item.equals("B")) {
                    list.remove(item); // Structural modification during iteration!
                }
            }
        } catch (ConcurrentModificationException e) {
            System.out.println("ConcurrentModificationException thrown!");
        }

        // CORRECT WAY 1: Use Iterator.remove()
        Iterator<String> it = list.iterator();
        while (it.hasNext()) {
            if (it.next().equals("B")) {
                it.remove(); // Safe!
            }
        }

        // CORRECT WAY 2: Use removeIf()
        list.removeIf(item -> item.equals("C"));

        // CORRECT WAY 3: Iterate over a copy
        for (String item : new ArrayList<>(list)) {
            if (item.equals("D")) {
                list.remove(item); // Safe - iterating over copy
            }
        }

        // CORRECT WAY 4: Use CopyOnWriteArrayList for concurrent access

        // NOTE: fail-fast is "best effort" - not guaranteed in all cases
        // The modCount mechanism may not catch all concurrent modifications
    }
}
```

### Q5: How to make ArrayList thread-safe?

```java
import java.util.*;
import java.util.concurrent.*;

public class ThreadSafeListOptions {
    public static void main(String[] args) {

        // Option 1: Collections.synchronizedList()
        // - Wraps with synchronized blocks
        // - Must manually synchronize iteration
        List<String> syncList = Collections.synchronizedList(new ArrayList<>());
        syncList.add("A"); // Each operation is synchronized

        // MUST synchronize when iterating!
        synchronized (syncList) {
            for (String item : syncList) {
                System.out.println(item);
            }
        }

        // Option 2: CopyOnWriteArrayList
        // - Best for read-heavy, write-rare scenarios
        // - No need to synchronize iteration
        CopyOnWriteArrayList<String> cowList = new CopyOnWriteArrayList<>();
        cowList.add("B");

        // Option 3: Vector (LEGACY - avoid)
        Vector<String> vector = new Vector<>();
        vector.add("C");

        // Option 4: Use concurrent utilities
        // For queue-like behavior: ConcurrentLinkedQueue
        // For deque behavior: ConcurrentLinkedDeque
    }
}
```

### Q6: Difference between `Arrays.asList()` and `List.of()`

```java
public class AsListVsListOf {
    public static void main(String[] args) {

        // Arrays.asList() - FIXED SIZE, but mutable elements
        List<String> asList = Arrays.asList("A", "B", "C");
        asList.set(0, "Z");       // OK - can modify elements
        // asList.add("D");       // UnsupportedOperationException - can't change size
        // asList.remove(0);      // UnsupportedOperationException - can't change size

        // Backed by original array!
        String[] arr = {"X", "Y", "Z"};
        List<String> backed = Arrays.asList(arr);
        arr[0] = "MODIFIED";
        System.out.println(backed.get(0)); // "MODIFIED" - reflected!

        // Allows null
        List<String> withNull = Arrays.asList("A", null, "B"); // OK

        // ──────────────────────────────────────────────────────

        // List.of() - FULLY IMMUTABLE (Java 9+)
        List<String> listOf = List.of("A", "B", "C");
        // listOf.set(0, "Z");    // UnsupportedOperationException
        // listOf.add("D");       // UnsupportedOperationException
        // listOf.remove(0);      // UnsupportedOperationException

        // Does NOT allow null
        // List.of("A", null);    // NullPointerException at creation!

        // Not backed by any array - truly independent

        /*
         * Summary:
         * ┌─────────────────────┬─────────────────────┬──────────────────┐
         * │                     │ Arrays.asList()     │ List.of()        │
         * ├─────────────────────┼─────────────────────┼──────────────────┤
         * │ set() allowed?      │ Yes                 │ No               │
         * │ add()/remove()?     │ No                  │ No               │
         * │ Null elements?      │ Yes                 │ No               │
         * │ Backed by array?    │ Yes                 │ No               │
         * │ Available since     │ Java 1.2            │ Java 9           │
         * │ Serializable?       │ Yes                 │ Yes              │
         * └─────────────────────┴─────────────────────┴──────────────────┘
         */
    }
}
```

### Q7: How does `subList()` work and what are the pitfalls?

```java
public class SubListPitfalls {
    public static void main(String[] args) {
        ArrayList<Integer> original = new ArrayList<>(Arrays.asList(1, 2, 3, 4, 5, 6, 7, 8));

        // subList returns a VIEW, not a copy
        List<Integer> sub = original.subList(2, 6); // [3, 4, 5, 6]
        System.out.println(sub);

        // Modification through subList affects original
        sub.set(0, 30);
        System.out.println(original); // [1, 2, 30, 4, 5, 6, 7, 8]

        sub.remove(Integer.valueOf(4));
        System.out.println(original); // [1, 2, 30, 5, 6, 7, 8]

        // PITFALL: Structural modification of original invalidates subList
        original.add(9); // Structural modification!
        try {
            sub.get(0); // ConcurrentModificationException!
        } catch (ConcurrentModificationException e) {
            System.out.println("SubList invalidated!");
        }

        // SAFE PATTERN: Create independent copy
        List<Integer> safeSub = new ArrayList<>(original.subList(0, 3));
        original.add(10);
        System.out.println(safeSub); // Still works fine

        // USEFUL PATTERN: Clear a range
        ArrayList<Integer> nums = new ArrayList<>(Arrays.asList(1, 2, 3, 4, 5));
        nums.subList(1, 4).clear();
        System.out.println(nums); // [1, 5]
    }
}
```

### Q8: Implement custom ArrayList (simplified)

```java
/**
 * Simplified ArrayList implementation - common interview question.
 */
public class MyArrayList<E> {
    private Object[] data;
    private int size;
    private static final int DEFAULT_CAPACITY = 10;

    public MyArrayList() {
        data = new Object[DEFAULT_CAPACITY];
        size = 0;
    }

    public MyArrayList(int initialCapacity) {
        if (initialCapacity < 0) throw new IllegalArgumentException();
        data = new Object[initialCapacity];
        size = 0;
    }

    // O(1) amortized
    public void add(E element) {
        ensureCapacity();
        data[size++] = element;
    }

    // O(n) - shifts elements
    public void add(int index, E element) {
        rangeCheckForAdd(index);
        ensureCapacity();
        // Shift elements right
        System.arraycopy(data, index, data, index + 1, size - index);
        data[index] = element;
        size++;
    }

    // O(1)
    @SuppressWarnings("unchecked")
    public E get(int index) {
        rangeCheck(index);
        return (E) data[index];
    }

    // O(1)
    @SuppressWarnings("unchecked")
    public E set(int index, E element) {
        rangeCheck(index);
        E old = (E) data[index];
        data[index] = element;
        return old;
    }

    // O(n) - shifts elements
    @SuppressWarnings("unchecked")
    public E remove(int index) {
        rangeCheck(index);
        E old = (E) data[index];
        int numToMove = size - index - 1;
        if (numToMove > 0) {
            System.arraycopy(data, index + 1, data, index, numToMove);
        }
        data[--size] = null; // Help GC
        return old;
    }

    // O(n)
    public int indexOf(E element) {
        for (int i = 0; i < size; i++) {
            if (element == null ? data[i] == null : element.equals(data[i])) {
                return i;
            }
        }
        return -1;
    }

    public int size() { return size; }
    public boolean isEmpty() { return size == 0; }

    public boolean contains(E element) {
        return indexOf(element) >= 0;
    }

    // Growth: 50% increase
    private void ensureCapacity() {
        if (size == data.length) {
            int newCapacity = data.length + (data.length >> 1); // 1.5x
            if (newCapacity < data.length + 1) newCapacity = data.length + 1;
            data = java.util.Arrays.copyOf(data, newCapacity);
        }
    }

    private void rangeCheck(int index) {
        if (index < 0 || index >= size)
            throw new IndexOutOfBoundsException("Index: " + index + ", Size: " + size);
    }

    private void rangeCheckForAdd(int index) {
        if (index < 0 || index > size)
            throw new IndexOutOfBoundsException("Index: " + index + ", Size: " + size);
    }

    @Override
    public String toString() {
        StringBuilder sb = new StringBuilder("[");
        for (int i = 0; i < size; i++) {
            sb.append(data[i]);
            if (i < size - 1) sb.append(", ");
        }
        return sb.append("]").toString();
    }

    public static void main(String[] args) {
        MyArrayList<String> list = new MyArrayList<>();
        list.add("A");
        list.add("B");
        list.add("C");
        System.out.println(list);        // [A, B, C]
        list.add(1, "X");
        System.out.println(list);        // [A, X, B, C]
        list.remove(2);
        System.out.println(list);        // [A, X, C]
        System.out.println(list.get(1)); // X
        System.out.println(list.size()); // 3
    }
}
```

### Q9: When would you use LinkedList over ArrayList in an LLD interview?

```java
/**
 * Scenarios where LinkedList is the better choice:
 *
 * 1. Implementing Undo/Redo (doubly-linked history):
 *    - Navigate back and forth through states
 *    - Efficient insertion/removal at current position
 *
 * 2. Music Playlist / Browser History:
 *    - Frequently insert/remove at both ends
 *    - Navigate forward/backward
 *
 * 3. Task Queue (Producer-Consumer):
 *    - Producers add at tail: offer() → O(1)
 *    - Consumers remove from head: poll() → O(1)
 *
 * 4. Round-Robin Scheduler:
 *    - Move completed tasks from front to back
 *
 * 5. Implementing LRU Cache eviction list:
 *    - Move accessed items to front
 *    - Remove from back when full
 *
 * HOWEVER: In most real LLD interviews, ArrayList is the default choice.
 * Use LinkedList only when you can clearly justify O(1) end operations
 * are critical and random access is not needed.
 */
```

### Q10: What is the time complexity of `contains()` and how to improve it?

```java
public class ContainsComplexity {
    public static void main(String[] args) {
        // ArrayList.contains() → O(n) linear search
        // LinkedList.contains() → O(n) linear search

        // If you need O(1) contains, use HashSet alongside
        List<String> list = new ArrayList<>();
        Set<String> lookupSet = new HashSet<>();

        // Add to both
        list.add("item");
        lookupSet.add("item");

        // O(1) lookup
        boolean exists = lookupSet.contains("item");

        // Or use LinkedHashSet to maintain insertion order + O(1) lookup
        LinkedHashSet<String> orderedSet = new LinkedHashSet<>();
        orderedSet.add("First");
        orderedSet.add("Second");
        // Maintains order AND O(1) contains

        // In LLD: If you need both index access AND fast lookup,
        // maintain both structures and keep them in sync
    }
}
```

---

## 12. Quick Reference Card

```
╔══════════════════════════════════════════════════════════════════════╗
║                    JAVA LIST QUICK REFERENCE                        ║
╠══════════════════════════════════════════════════════════════════════╣
║                                                                      ║
║  DEFAULT CHOICE: ArrayList                                           ║
║                                                                      ║
║  ┌─────────────────────┬──────────────┬──────────────────────────┐  ║
║  │ Need                │ Use          │ Reason                   │  ║
║  ├─────────────────────┼──────────────┼──────────────────────────┤  ║
║  │ General purpose     │ ArrayList    │ O(1) get, cache-friendly │  ║
║  │ Queue/Deque/Stack   │ ArrayDeque   │ Faster than LinkedList   │  ║
║  │ Both List + Deque   │ LinkedList   │ Only option              │  ║
║  │ Thread-safe reads   │ CopyOnWrite  │ Lock-free reads          │  ║
║  │ Thread-safe general │ syncList()   │ Synchronized wrapper     │  ║
║  │ Immutable           │ List.of()    │ Truly immutable          │  ║
║  │ Fixed elements      │ Arrays.asList│ Array-backed, set OK     │  ║
║  └─────────────────────┴──────────────┴──────────────────────────┘  ║
║                                                                      ║
║  COMMON TRAPS:                                                       ║
║  • remove(int) vs remove(Object) with Integer lists                  ║
║  • Modifying list during enhanced for-loop                           ║
║  • subList() is a view, not a copy                                   ║
║  • Arrays.asList() is backed by the original array                   ║
║  • List.of() does not allow null elements                            ║
║  • Collections.unmodifiableList() is a view, not immutable           ║
║                                                                      ║
╚══════════════════════════════════════════════════════════════════════╝
```

---

## 13. Collections Utility Methods for Lists

```java
import java.util.*;

public class CollectionsUtilities {
    public static void main(String[] args) {
        List<Integer> list = new ArrayList<>(Arrays.asList(3, 1, 4, 1, 5, 9, 2, 6));

        // Sorting
        Collections.sort(list);                           // Natural order
        Collections.sort(list, Comparator.reverseOrder()); // Reverse

        // Searching (list must be sorted!)
        Collections.sort(list);
        int idx = Collections.binarySearch(list, 5);     // O(log n)

        // Min / Max
        int min = Collections.min(list);
        int max = Collections.max(list);
        int maxByComparator = Collections.max(list, Comparator.reverseOrder());

        // Frequency
        int count = Collections.frequency(list, 1); // How many times 1 appears

        // Reverse
        Collections.reverse(list);

        // Shuffle
        Collections.shuffle(list);
        Collections.shuffle(list, new Random(42)); // Reproducible shuffle

        // Swap
        Collections.swap(list, 0, list.size() - 1); // Swap first and last

        // Rotate
        Collections.rotate(list, 2); // Rotate right by 2 positions

        // Fill
        Collections.fill(list, 0); // All elements become 0

        // nCopies - immutable list of n copies
        List<String> fiveHellos = Collections.nCopies(5, "Hello");

        // disjoint - checks if two collections have no common elements
        boolean noCommon = Collections.disjoint(
            Arrays.asList(1, 2, 3),
            Arrays.asList(4, 5, 6)
        ); // true

        // replaceAll (Collections version - replaces value, not lambda)
        List<String> words = new ArrayList<>(Arrays.asList("a", "b", "a", "c"));
        Collections.replaceAll(words, "a", "z"); // [z, b, z, c]

        // unmodifiableList
        List<Integer> readOnly = Collections.unmodifiableList(list);

        // synchronizedList
        List<Integer> threadSafe = Collections.synchronizedList(new ArrayList<>());

        // singletonList
        List<String> single = Collections.singletonList("only");

        // emptyList
        List<Object> empty = Collections.emptyList();

        // checkedList - runtime type safety
        List<String> checked = Collections.checkedList(new ArrayList<>(), String.class);
        // Prevents heap pollution from unchecked casts
    }
}
```
