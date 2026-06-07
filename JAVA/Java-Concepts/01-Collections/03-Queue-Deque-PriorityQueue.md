# Queue, Deque & PriorityQueue - Complete Java Reference for LLD

## Table of Contents
1. [Queue Interface](#1-queue-interface)
2. [LinkedList as Queue](#2-linkedlist-as-queue)
3. [PriorityQueue](#3-priorityqueue)
4. [Deque Interface](#4-deque-interface)
5. [ArrayDeque](#5-arraydeque)
6. [Stack (Legacy)](#6-stack-legacy)
7. [BlockingQueue (Concurrency)](#7-blockingqueue-concurrency)
8. [Comparator and Comparable](#8-comparator-and-comparable)
9. [Time Complexity Summary](#9-time-complexity-summary)
10. [LLD Design Examples](#10-lld-design-examples)

---

## 1. Queue Interface

```java
public interface Queue<E> extends Collection<E> {
    // -------- Throws Exception --------    -------- Returns Special Value --------
    boolean add(E e);        //              boolean offer(E e);        // Insert
    E remove();              //              E poll();                   // Remove
    E element();             //              E peek();                   // Examine
}
```

### Method Comparison Table

| Operation | Throws Exception | Returns null/false | When to Use |
|-----------|-----------------|-------------------|-------------|
| **Insert** | `add(e)` - throws `IllegalStateException` if full | `offer(e)` - returns `false` if full | Use `offer` for bounded queues |
| **Remove** | `remove()` - throws `NoSuchElementException` if empty | `poll()` - returns `null` if empty | Use `poll` in most cases |
| **Examine** | `element()` - throws `NoSuchElementException` if empty | `peek()` - returns `null` if empty | Use `peek` in most cases |

### Complete Example

```java
import java.util.*;

public class QueueInterfaceDemo {
    public static void main(String[] args) {
        Queue<String> queue = new LinkedList<>();

        // ===== INSERT =====
        queue.add("first");       // returns true, throws IllegalStateException if capacity restricted
        queue.offer("second");    // returns true/false (preferred for bounded queues)

        // ===== EXAMINE (without removing) =====
        String head1 = queue.element();  // "first" - throws NoSuchElementException if empty
        String head2 = queue.peek();     // "first" - returns null if empty

        // ===== REMOVE =====
        String removed1 = queue.remove(); // "first" - throws NoSuchElementException if empty
        String removed2 = queue.poll();   // "second" - returns null if empty

        // Empty queue behavior
        Queue<String> empty = new LinkedList<>();
        System.out.println(empty.peek());   // null (safe)
        System.out.println(empty.poll());   // null (safe)
        // empty.element();  // throws NoSuchElementException
        // empty.remove();   // throws NoSuchElementException
    }
}
```

---

## 2. LinkedList as Queue

`LinkedList` implements both `List` and `Deque` (which extends `Queue`).

```java
import java.util.*;

public class LinkedListQueueDemo {
    public static void main(String[] args) {
        // FIFO Queue using LinkedList
        Queue<Integer> queue = new LinkedList<>();

        // Enqueue
        queue.offer(10);
        queue.offer(20);
        queue.offer(30);
        // Queue: [10, 20, 30] - 10 is head (first out)

        // Dequeue (FIFO - First In First Out)
        System.out.println(queue.poll());  // 10 (first inserted, first removed)
        System.out.println(queue.poll());  // 20
        System.out.println(queue.poll());  // 30
        System.out.println(queue.poll());  // null (empty)

        // BFS Example - Classic Queue Usage
        queue.offer(1);
        queue.offer(2);
        queue.offer(3);

        while (!queue.isEmpty()) {
            int current = queue.poll();
            System.out.print(current + " ");  // 1 2 3
        }
    }
}
```

### When to Use LinkedList vs ArrayDeque as Queue

| Feature | LinkedList | ArrayDeque |
|---------|-----------|------------|
| Null elements | Allowed | NOT allowed |
| Memory | More (node objects + pointers) | Less (contiguous array) |
| Cache performance | Poor (scattered memory) | Excellent (contiguous) |
| Thread-safe | No | No |
| Implements List | Yes | No |
| **Recommendation** | Only if you need List interface | **Preferred for Queue/Deque** |

---

## 3. PriorityQueue

### Internal Implementation

PriorityQueue uses a **binary min-heap** stored as a **resizable array**.

```
Heap property: parent <= children (min-heap)

Array representation of heap:
Index:    0    1    2    3    4    5    6
Value:   [1,   3,   2,   7,   5,   4,   6]

Tree visualization:
            1          (index 0)
          /   \
         3     2       (index 1, 2)
        / \   / \
       7   5 4   6    (index 3, 4, 5, 6)

Parent of index i: (i - 1) / 2
Left child of i:   2 * i + 1
Right child of i:  2 * i + 2
```

### All Methods with Examples

```java
import java.util.*;

public class PriorityQueueMethods {
    public static void main(String[] args) {

        // ===== CREATION =====
        PriorityQueue<Integer> pq = new PriorityQueue<>();           // Min-heap (natural ordering)
        PriorityQueue<Integer> maxPQ = new PriorityQueue<>(Collections.reverseOrder()); // Max-heap
        PriorityQueue<Integer> withCapacity = new PriorityQueue<>(20); // Initial capacity 20
        PriorityQueue<Integer> fromCollection = new PriorityQueue<>(Arrays.asList(5, 1, 3)); // From collection

        // ===== OFFER / ADD (Insert) =====
        pq.offer(30);    // returns true - O(log n)
        pq.offer(10);    // returns true
        pq.offer(20);    // returns true
        pq.add(5);       // returns true (throws IllegalStateException if capacity restricted - never for PQ)
        // Internal array: [5, 10, 20, 30] (heap-ordered, NOT sorted)

        // ===== PEEK (Examine head without removing) =====
        System.out.println(pq.peek());    // 5 - O(1) - returns null if empty

        // ===== POLL (Remove and return head) =====
        System.out.println(pq.poll());    // 5 - O(log n) - returns null if empty

        // ===== REMOVE (specific element) =====
        pq.offer(15);
        pq.offer(25);
        pq.offer(10);
        boolean removed = pq.remove(15);  // true - O(n) linear search + O(log n) heapify
        // pq.remove() without arg = same as poll() but throws exception if empty

        // ===== CONTAINS =====
        boolean has20 = pq.contains(20);  // true - O(n) linear search

        // ===== SIZE / isEmpty =====
        int size = pq.size();             // O(1)
        boolean empty = pq.isEmpty();     // O(1)

        // ===== TO ARRAY =====
        Object[] arr = pq.toArray();                     // heap order (NOT sorted!)
        Integer[] typedArr = pq.toArray(new Integer[0]); // typed array

        // ===== ITERATOR =====
        // WARNING: Iterator does NOT guarantee sorted order!
        Iterator<Integer> it = pq.iterator();
        while (it.hasNext()) {
            System.out.print(it.next() + " "); // NOT in priority order!
        }

        // To get sorted order, you MUST poll repeatedly:
        List<Integer> sorted = new ArrayList<>();
        while (!pq.isEmpty()) {
            sorted.add(pq.poll());  // This gives sorted order
        }

        // ===== COMPARATOR =====
        PriorityQueue<Integer> pq2 = new PriorityQueue<>();
        Comparator<? super Integer> comp = pq2.comparator(); // null (natural ordering)

        PriorityQueue<Integer> pq3 = new PriorityQueue<>(Comparator.reverseOrder());
        Comparator<? super Integer> comp2 = pq3.comparator(); // non-null

        // ===== CLEAR =====
        pq2.clear();  // Removes all elements

        // ===== BULK OPERATIONS (inherited from Collection) =====
        PriorityQueue<Integer> pq4 = new PriorityQueue<>();
        pq4.addAll(Arrays.asList(5, 1, 8, 3, 2));  // O(n) heapify
        pq4.removeAll(Arrays.asList(1, 2));          // Removes 1 and 2
        pq4.retainAll(Arrays.asList(5, 8));          // Keeps only 5 and 8
    }
}
```

### Heapify Process (Sift-Up and Sift-Down)

```java
/**
 * Sift-Up (used during offer/add):
 * - Insert at end of array
 * - Compare with parent, swap if smaller
 * - Repeat until heap property restored
 *
 * Sift-Down (used during poll/remove):
 * - Replace root with last element
 * - Compare with children, swap with smaller child
 * - Repeat until heap property restored
 */
public class HeapifyVisualization {
    public static void main(String[] args) {
        PriorityQueue<Integer> pq = new PriorityQueue<>();

        // offer(30): [30]
        pq.offer(30);

        // offer(20): [20, 30]  -- 20 sifts up (20 < 30)
        pq.offer(20);

        // offer(10): [10, 30, 20]  -- 10 sifts up past 20
        pq.offer(10);

        // offer(5):  [5, 10, 20, 30]  -- 5 sifts up to root
        pq.offer(5);

        // poll(): removes 5
        //   Step 1: Replace root with last: [30, 10, 20]
        //   Step 2: Sift down 30: swap with min child (10): [10, 30, 20]
        //   Result: [10, 30, 20]
        pq.poll();

        // Building heap from array (heapify) is O(n), not O(n log n)
        // Because: leaves (n/2 elements) need 0 swaps, level above needs 1 swap, etc.
        PriorityQueue<Integer> bulkPQ = new PriorityQueue<>(Arrays.asList(9, 7, 5, 3, 1, 8, 2));
        // Internally calls heapify - O(n) operation
    }
}
```

### Custom Ordering with Comparator

```java
import java.util.*;

public class PriorityQueueComparators {
    public static void main(String[] args) {

        // ===== MIN-HEAP (default - natural ordering) =====
        PriorityQueue<Integer> minHeap = new PriorityQueue<>();
        minHeap.addAll(Arrays.asList(5, 1, 3, 7, 2));
        System.out.println(minHeap.poll());  // 1 (smallest first)

        // ===== MAX-HEAP =====
        PriorityQueue<Integer> maxHeap = new PriorityQueue<>(Collections.reverseOrder());
        maxHeap.addAll(Arrays.asList(5, 1, 3, 7, 2));
        System.out.println(maxHeap.poll());  // 7 (largest first)

        // Equivalent max-heap definitions:
        PriorityQueue<Integer> maxHeap2 = new PriorityQueue<>((a, b) -> b - a);
        PriorityQueue<Integer> maxHeap3 = new PriorityQueue<>(Comparator.reverseOrder());

        // ===== CUSTOM OBJECTS =====
        // Min-heap by age
        PriorityQueue<Person> byAge = new PriorityQueue<>(
            Comparator.comparingInt(Person::getAge)
        );

        // Max-heap by age
        PriorityQueue<Person> byAgeDesc = new PriorityQueue<>(
            Comparator.comparingInt(Person::getAge).reversed()
        );

        // Sort by name, then by age
        PriorityQueue<Person> byNameThenAge = new PriorityQueue<>(
            Comparator.comparing(Person::getName)
                      .thenComparingInt(Person::getAge)
        );

        // Sort by salary descending, then name ascending
        PriorityQueue<Employee> employeePQ = new PriorityQueue<>(
            Comparator.comparingDouble(Employee::getSalary).reversed()
                      .thenComparing(Employee::getName)
        );
    }
}

class Person {
    private String name;
    private int age;
    Person(String name, int age) { this.name = name; this.age = age; }
    String getName() { return name; }
    int getAge() { return age; }
}

class Employee {
    private String name;
    private double salary;
    Employee(String name, double salary) { this.name = name; this.salary = salary; }
    String getName() { return name; }
    double getSalary() { return salary; }
}
```

### PriorityQueue Time Complexity

| Operation | Time Complexity | Notes |
|-----------|----------------|-------|
| `offer(e)` / `add(e)` | O(log n) | Sift-up |
| `poll()` / `remove()` | O(log n) | Sift-down |
| `peek()` / `element()` | O(1) | Just return index 0 |
| `remove(Object)` | O(n) | Linear search + O(log n) sift |
| `contains(Object)` | O(n) | Linear search |
| `size()` | O(1) | Stored field |
| `toArray()` | O(n) | Copy array |
| Heapify (build from collection) | O(n) | Bottom-up construction |
| Iterator traversal | O(n) | NOT in sorted order |
| Get sorted output | O(n log n) | Must poll() n times |

### Example: Task Scheduling

```java
import java.util.*;

public class TaskScheduler {

    static class Task implements Comparable<Task> {
        String name;
        int priority;    // lower number = higher priority
        long timestamp;  // for FIFO ordering among same priority

        Task(String name, int priority) {
            this.name = name;
            this.priority = priority;
            this.timestamp = System.nanoTime();
        }

        @Override
        public int compareTo(Task other) {
            if (this.priority != other.priority) {
                return Integer.compare(this.priority, other.priority);
            }
            return Long.compare(this.timestamp, other.timestamp); // FIFO for same priority
        }

        @Override
        public String toString() {
            return name + "(p=" + priority + ")";
        }
    }

    public static void main(String[] args) {
        PriorityQueue<Task> scheduler = new PriorityQueue<>();

        scheduler.offer(new Task("Send Email", 3));
        scheduler.offer(new Task("Process Payment", 1));
        scheduler.offer(new Task("Generate Report", 2));
        scheduler.offer(new Task("Update Cache", 1));

        // Process in priority order
        while (!scheduler.isEmpty()) {
            Task task = scheduler.poll();
            System.out.println("Executing: " + task);
        }
        // Output:
        // Executing: Process Payment(p=1)
        // Executing: Update Cache(p=1)
        // Executing: Generate Report(p=2)
        // Executing: Send Email(p=3)
    }
}
```

### Example: Top-K Elements

```java
import java.util.*;

public class TopKElements {

    // ===== Top K Largest - use MIN heap of size K =====
    public static List<Integer> topKLargest(int[] nums, int k) {
        // Min-heap: keeps the K largest. Smallest of the K is at top.
        PriorityQueue<Integer> minHeap = new PriorityQueue<>();

        for (int num : nums) {
            minHeap.offer(num);
            if (minHeap.size() > k) {
                minHeap.poll();  // Remove smallest, keeping only K largest
            }
        }

        List<Integer> result = new ArrayList<>(minHeap);
        Collections.sort(result, Collections.reverseOrder());
        return result;
    }

    // ===== Top K Smallest - use MAX heap of size K =====
    public static List<Integer> topKSmallest(int[] nums, int k) {
        PriorityQueue<Integer> maxHeap = new PriorityQueue<>(Collections.reverseOrder());

        for (int num : nums) {
            maxHeap.offer(num);
            if (maxHeap.size() > k) {
                maxHeap.poll();  // Remove largest, keeping only K smallest
            }
        }

        List<Integer> result = new ArrayList<>(maxHeap);
        Collections.sort(result);
        return result;
    }

    // ===== Top K Frequent Elements =====
    public static List<Integer> topKFrequent(int[] nums, int k) {
        Map<Integer, Integer> freqMap = new HashMap<>();
        for (int num : nums) {
            freqMap.merge(num, 1, Integer::sum);
        }

        // Min-heap by frequency
        PriorityQueue<Map.Entry<Integer, Integer>> pq = new PriorityQueue<>(
            Comparator.comparingInt(Map.Entry::getValue)
        );

        for (Map.Entry<Integer, Integer> entry : freqMap.entrySet()) {
            pq.offer(entry);
            if (pq.size() > k) {
                pq.poll();
            }
        }

        List<Integer> result = new ArrayList<>();
        while (!pq.isEmpty()) {
            result.add(pq.poll().getKey());
        }
        Collections.reverse(result);
        return result;
    }

    // ===== Kth Largest Element =====
    public static int kthLargest(int[] nums, int k) {
        PriorityQueue<Integer> minHeap = new PriorityQueue<>();
        for (int num : nums) {
            minHeap.offer(num);
            if (minHeap.size() > k) {
                minHeap.poll();
            }
        }
        return minHeap.peek(); // The Kth largest is at the top of min-heap of size K
    }

    public static void main(String[] args) {
        int[] nums = {3, 1, 5, 12, 2, 11, 7, 9};

        System.out.println("Top 3 largest: " + topKLargest(nums, 3));   // [12, 11, 9]
        System.out.println("Top 3 smallest: " + topKSmallest(nums, 3)); // [1, 2, 3]
        System.out.println("3rd largest: " + kthLargest(nums, 3));      // 9

        int[] freq = {1, 1, 1, 2, 2, 3};
        System.out.println("Top 2 frequent: " + topKFrequent(freq, 2)); // [1, 2]
    }
}
```

### Example: Merge K Sorted Lists

```java
import java.util.*;

public class MergeKSortedLists {

    // Merge K sorted arrays
    public static List<Integer> mergeKSortedArrays(List<int[]> arrays) {
        // Min-heap: stores [value, arrayIndex, elementIndex]
        PriorityQueue<int[]> pq = new PriorityQueue<>(
            Comparator.comparingInt(a -> a[0])
        );

        // Initialize with first element of each array
        for (int i = 0; i < arrays.size(); i++) {
            if (arrays.get(i).length > 0) {
                pq.offer(new int[]{arrays.get(i)[0], i, 0});
            }
        }

        List<Integer> result = new ArrayList<>();

        while (!pq.isEmpty()) {
            int[] current = pq.poll();
            int value = current[0];
            int arrayIdx = current[1];
            int elemIdx = current[2];

            result.add(value);

            // If there's a next element in the same array, add it
            if (elemIdx + 1 < arrays.get(arrayIdx).length) {
                pq.offer(new int[]{
                    arrays.get(arrayIdx)[elemIdx + 1],
                    arrayIdx,
                    elemIdx + 1
                });
            }
        }

        return result;
    }

    // Merge K sorted LinkedLists (LeetCode #23)
    static class ListNode {
        int val;
        ListNode next;
        ListNode(int val) { this.val = val; }
    }

    public static ListNode mergeKLists(ListNode[] lists) {
        PriorityQueue<ListNode> pq = new PriorityQueue<>(
            Comparator.comparingInt(node -> node.val)
        );

        // Add head of each list
        for (ListNode head : lists) {
            if (head != null) {
                pq.offer(head);
            }
        }

        ListNode dummy = new ListNode(0);
        ListNode current = dummy;

        while (!pq.isEmpty()) {
            ListNode smallest = pq.poll();
            current.next = smallest;
            current = current.next;

            if (smallest.next != null) {
                pq.offer(smallest.next);
            }
        }

        return dummy.next;
    }

    public static void main(String[] args) {
        List<int[]> arrays = Arrays.asList(
            new int[]{1, 4, 7},
            new int[]{2, 5, 8},
            new int[]{3, 6, 9}
        );
        System.out.println(mergeKSortedArrays(arrays));
        // [1, 2, 3, 4, 5, 6, 7, 8, 9]
    }
}
```

### Example: Running Median (Two Heaps)

```java
import java.util.*;

public class RunningMedian {
    // Max-heap for lower half
    private PriorityQueue<Integer> maxHeap = new PriorityQueue<>(Collections.reverseOrder());
    // Min-heap for upper half
    private PriorityQueue<Integer> minHeap = new PriorityQueue<>();

    public void addNum(int num) {
        maxHeap.offer(num);
        minHeap.offer(maxHeap.poll());  // Balance: move max of lower half to upper

        // Ensure maxHeap has equal or one more element
        if (minHeap.size() > maxHeap.size()) {
            maxHeap.offer(minHeap.poll());
        }
    }

    public double findMedian() {
        if (maxHeap.size() > minHeap.size()) {
            return maxHeap.peek();
        }
        return (maxHeap.peek() + minHeap.peek()) / 2.0;
    }

    public static void main(String[] args) {
        RunningMedian rm = new RunningMedian();
        rm.addNum(1);
        System.out.println(rm.findMedian()); // 1.0
        rm.addNum(2);
        System.out.println(rm.findMedian()); // 1.5
        rm.addNum(3);
        System.out.println(rm.findMedian()); // 2.0
        rm.addNum(4);
        System.out.println(rm.findMedian()); // 2.5
    }
}
```

---

## 4. Deque Interface

`Deque` = Double-Ended Queue. Elements can be added/removed from both ends.

```java
public interface Deque<E> extends Queue<E> {
    // ===== HEAD (First Element) =====
    //       Throws Exception          Returns Special Value
    void    addFirst(E e);             boolean offerFirst(E e);    // Insert
    E       removeFirst();             E       pollFirst();        // Remove
    E       getFirst();                E       peekFirst();        // Examine

    // ===== TAIL (Last Element) =====
    //       Throws Exception          Returns Special Value
    void    addLast(E e);              boolean offerLast(E e);     // Insert
    E       removeLast();              E       pollLast();         // Remove
    E       getLast();                 E       peekLast();         // Examine

    // ===== Stack Methods =====
    void    push(E e);    // same as addFirst(e)
    E       pop();        // same as removeFirst()
    E       peek();       // same as peekFirst()

    // ===== Queue Methods (inherited) =====
    boolean offer(E e);   // same as offerLast(e)
    E       poll();       // same as pollFirst()
    // E    peek();       // same as peekFirst()

    // ===== Other =====
    boolean remove(Object o);           // removeFirstOccurrence
    boolean removeFirstOccurrence(Object o);
    boolean removeLastOccurrence(Object o);
    boolean contains(Object o);
    int     size();
    Iterator<E> iterator();             // head to tail
    Iterator<E> descendingIterator();   // tail to head
}
```

### Deque Method Mapping

| Deque as Queue (FIFO) | Deque as Stack (LIFO) |
|------------------------|----------------------|
| `offerLast(e)` - enqueue | `push(e)` / `addFirst(e)` - push |
| `pollFirst()` - dequeue | `pop()` / `removeFirst()` - pop |
| `peekFirst()` - examine | `peek()` / `peekFirst()` - peek |

```java
import java.util.*;

public class DequeInterfaceDemo {
    public static void main(String[] args) {
        Deque<String> deque = new ArrayDeque<>();

        // ===== Add to both ends =====
        deque.addFirst("B");    // [B]
        deque.addFirst("A");    // [A, B]
        deque.addLast("C");     // [A, B, C]
        deque.addLast("D");     // [A, B, C, D]

        // ===== Examine both ends =====
        System.out.println(deque.peekFirst());  // A
        System.out.println(deque.peekLast());   // D

        // ===== Remove from both ends =====
        System.out.println(deque.pollFirst());  // A -> [B, C, D]
        System.out.println(deque.pollLast());   // D -> [B, C]

        // ===== As Queue (FIFO) =====
        Deque<String> queue = new ArrayDeque<>();
        queue.offer("first");       // offerLast
        queue.offer("second");
        queue.poll();               // pollFirst -> "first"

        // ===== As Stack (LIFO) =====
        Deque<String> stack = new ArrayDeque<>();
        stack.push("bottom");       // addFirst
        stack.push("top");
        stack.pop();                // removeFirst -> "top"

        // ===== Descending Iterator =====
        deque.addLast("X");
        deque.addLast("Y");
        Iterator<String> descIt = deque.descendingIterator();
        while (descIt.hasNext()) {
            System.out.print(descIt.next() + " ");  // Y X C B
        }
    }
}
```

---

## 5. ArrayDeque

### Circular Array Implementation

```
ArrayDeque internal structure (circular buffer):
- Uses a resizable array (always power of 2 length)
- head index points to first element
- tail index points to slot AFTER last element
- Wraps around using bitwise AND: index & (array.length - 1)

Example with capacity 8:
  indices: [0] [1] [2] [3] [4] [5] [6] [7]
  values:  [ ] [ ] [A] [B] [C] [D] [ ] [ ]
                    ^head          ^tail

After addFirst("Z"):
  indices: [0] [1] [2] [3] [4] [5] [6] [7]
  values:  [ ] [Z] [A] [B] [C] [D] [ ] [ ]
               ^head               ^tail

Wrap-around example:
  indices: [0] [1] [2] [3] [4] [5] [6] [7]
  values:  [E] [F] [ ] [ ] [ ] [C] [D] [A]
                    ^tail        ^head

When head == tail (full): array doubles in size (new power of 2)
```

### Why ArrayDeque is Better Than Stack and LinkedList

| Aspect | ArrayDeque | Stack | LinkedList |
|--------|-----------|-------|------------|
| Synchronized | No (faster) | Yes (slow) | No |
| Null elements | Not allowed | Allowed | Allowed |
| Random access | No | Yes (Vector) | O(n) |
| Memory overhead | Low (array) | Low (array) | High (nodes) |
| Cache locality | Excellent | Good | Poor |
| Resizing | Doubling (amortized O(1)) | Doubling | N/A |
| Thread safety | Not thread-safe | Thread-safe (unnecessary) | Not thread-safe |
| **Recommended** | **Yes (Queue & Stack)** | No (legacy) | Only if nulls needed |

### All Methods with Examples

```java
import java.util.*;

public class ArrayDequeComplete {
    public static void main(String[] args) {

        // ===== CREATION =====
        ArrayDeque<Integer> deque = new ArrayDeque<>();       // Default capacity 16
        ArrayDeque<Integer> sized = new ArrayDeque<>(32);     // Initial capacity (rounds up to power of 2)
        ArrayDeque<Integer> copy = new ArrayDeque<>(Arrays.asList(1, 2, 3)); // From collection

        // ===== DEQUE OPERATIONS (Both Ends) =====
        deque.addFirst(10);       // [10] - throws IllegalStateException if full (never for ArrayDeque)
        deque.addFirst(5);        // [5, 10]
        deque.addLast(20);        // [5, 10, 20]
        deque.addLast(30);        // [5, 10, 20, 30]

        deque.offerFirst(1);      // [1, 5, 10, 20, 30] - returns true/false
        deque.offerLast(40);      // [1, 5, 10, 20, 30, 40]

        System.out.println(deque.peekFirst()); // 1
        System.out.println(deque.peekLast());  // 40
        System.out.println(deque.getFirst());  // 1 (throws if empty)
        System.out.println(deque.getLast());   // 40 (throws if empty)

        System.out.println(deque.pollFirst()); // 1 -> [5, 10, 20, 30, 40]
        System.out.println(deque.pollLast());  // 40 -> [5, 10, 20, 30]
        System.out.println(deque.removeFirst()); // 5 (throws if empty)
        System.out.println(deque.removeLast());  // 30 (throws if empty)

        // ===== AS STACK (LIFO) =====
        ArrayDeque<String> stack = new ArrayDeque<>();
        stack.push("a");          // addFirst -> [a]
        stack.push("b");          // addFirst -> [b, a]
        stack.push("c");          // addFirst -> [c, b, a]

        System.out.println(stack.peek());  // c (peekFirst)
        System.out.println(stack.pop());   // c (removeFirst) -> [b, a]
        System.out.println(stack.pop());   // b -> [a]

        // ===== AS QUEUE (FIFO) =====
        ArrayDeque<String> queue = new ArrayDeque<>();
        queue.offer("first");     // offerLast -> [first]
        queue.offer("second");    // offerLast -> [first, second]
        queue.offer("third");     // offerLast -> [first, second, third]

        System.out.println(queue.peek());  // first (peekFirst)
        System.out.println(queue.poll());  // first (pollFirst) -> [second, third]
        System.out.println(queue.poll());  // second -> [third]

        // ===== SEARCH / REMOVAL =====
        ArrayDeque<Integer> d = new ArrayDeque<>(Arrays.asList(1, 2, 3, 2, 4));
        d.remove(2);                       // Removes FIRST occurrence of 2 -> [1, 3, 2, 4]
        d.removeFirstOccurrence(2);        // Removes first 2 -> [1, 3, 4]
        d.removeLastOccurrence(3);         // Removes last 3 -> [1, 4]
        boolean has4 = d.contains(4);      // true - O(n)

        // ===== UTILITY =====
        System.out.println(d.size());      // 2
        System.out.println(d.isEmpty());   // false
        d.clear();                         // Empty

        // ===== ITERATION =====
        ArrayDeque<Integer> nums = new ArrayDeque<>(Arrays.asList(10, 20, 30, 40));

        // Forward iterator (head to tail)
        for (int n : nums) {
            System.out.print(n + " ");  // 10 20 30 40
        }

        // Descending iterator (tail to head)
        Iterator<Integer> descIt = nums.descendingIterator();
        while (descIt.hasNext()) {
            System.out.print(descIt.next() + " ");  // 40 30 20 10
        }

        // ===== CONVERSION =====
        Object[] arr = nums.toArray();
        Integer[] typedArr = nums.toArray(new Integer[0]);

        // ===== NOTE: ArrayDeque does NOT allow null =====
        // nums.offer(null);  // throws NullPointerException
    }
}
```

### ArrayDeque as Stack - Complete Patterns

```java
import java.util.*;

public class ArrayDequeAsStack {
    public static void main(String[] args) {

        // ===== Parentheses Matching =====
        System.out.println(isValid("({[]})")); // true
        System.out.println(isValid("({[}])"));  // false

        // ===== Monotonic Stack (Next Greater Element) =====
        int[] nums = {4, 2, 8, 1, 5};
        System.out.println(Arrays.toString(nextGreaterElement(nums)));
        // [8, 8, -1, 5, -1]

        // ===== Expression Evaluation =====
        System.out.println(evaluatePostfix("3 4 + 2 *")); // 14
    }

    static boolean isValid(String s) {
        Deque<Character> stack = new ArrayDeque<>();
        Map<Character, Character> pairs = Map.of(')', '(', '}', '{', ']', '[');

        for (char c : s.toCharArray()) {
            if ("({[".indexOf(c) >= 0) {
                stack.push(c);
            } else {
                if (stack.isEmpty() || stack.pop() != pairs.get(c)) {
                    return false;
                }
            }
        }
        return stack.isEmpty();
    }

    static int[] nextGreaterElement(int[] nums) {
        int n = nums.length;
        int[] result = new int[n];
        Arrays.fill(result, -1);
        Deque<Integer> stack = new ArrayDeque<>(); // stores indices

        for (int i = 0; i < n; i++) {
            while (!stack.isEmpty() && nums[i] > nums[stack.peek()]) {
                result[stack.pop()] = nums[i];
            }
            stack.push(i);
        }
        return result;
    }

    static int evaluatePostfix(String expression) {
        Deque<Integer> stack = new ArrayDeque<>();
        for (String token : expression.split(" ")) {
            switch (token) {
                case "+": stack.push(stack.pop() + stack.pop()); break;
                case "-": int b = stack.pop(); stack.push(stack.pop() - b); break;
                case "*": stack.push(stack.pop() * stack.pop()); break;
                case "/": int d = stack.pop(); stack.push(stack.pop() / d); break;
                default: stack.push(Integer.parseInt(token));
            }
        }
        return stack.pop();
    }
}
```

### ArrayDeque as Queue - BFS Pattern

```java
import java.util.*;

public class ArrayDequeAsQueue {
    public static void main(String[] args) {
        // BFS Traversal
        int[][] grid = {
            {1, 1, 0, 0},
            {1, 1, 0, 1},
            {0, 0, 0, 1},
            {0, 0, 1, 1}
        };
        System.out.println("Islands: " + countIslands(grid)); // 2
    }

    static int countIslands(int[][] grid) {
        int count = 0;
        int rows = grid.length, cols = grid[0].length;
        boolean[][] visited = new boolean[rows][cols];

        for (int i = 0; i < rows; i++) {
            for (int j = 0; j < cols; j++) {
                if (grid[i][j] == 1 && !visited[i][j]) {
                    bfs(grid, visited, i, j);
                    count++;
                }
            }
        }
        return count;
    }

    static void bfs(int[][] grid, boolean[][] visited, int startRow, int startCol) {
        Deque<int[]> queue = new ArrayDeque<>(); // Use ArrayDeque as Queue
        queue.offer(new int[]{startRow, startCol});
        visited[startRow][startCol] = true;
        int[][] dirs = {{0,1},{0,-1},{1,0},{-1,0}};

        while (!queue.isEmpty()) {
            int[] cell = queue.poll();
            for (int[] dir : dirs) {
                int r = cell[0] + dir[0], c = cell[1] + dir[1];
                if (r >= 0 && r < grid.length && c >= 0 && c < grid[0].length
                    && grid[r][c] == 1 && !visited[r][c]) {
                    visited[r][c] = true;
                    queue.offer(new int[]{r, c});
                }
            }
        }
    }
}
```

---

## 6. Stack (Legacy)

### Why Stack is Legacy

```java
import java.util.*;

/**
 * Stack extends Vector (synchronized, thread-safe but slow).
 * Problems:
 * 1. Synchronized on every operation (unnecessary overhead for single-threaded use)
 * 2. Extends Vector which allows index-based access (breaks stack abstraction)
 * 3. You can do stack.get(0), stack.add(1, element) which violates LIFO
 * 4. Legacy class since Java 1.0, never updated
 *
 * Replacement: ArrayDeque (recommended by Java docs)
 */
public class StackLegacy {
    public static void main(String[] args) {

        // ===== Legacy Stack (DO NOT USE in new code) =====
        Stack<Integer> legacyStack = new Stack<>();
        legacyStack.push(1);        // [1]
        legacyStack.push(2);        // [1, 2]
        legacyStack.push(3);        // [1, 2, 3]

        System.out.println(legacyStack.peek());     // 3
        System.out.println(legacyStack.pop());      // 3
        System.out.println(legacyStack.empty());    // false (note: empty() not isEmpty())
        System.out.println(legacyStack.search(1));  // 2 (1-based position from top)

        // BAD: Stack allows non-stack operations (because it extends Vector)
        legacyStack.add(0, 99);     // Insert at index 0 - breaks LIFO!
        legacyStack.get(0);         // Random access - breaks abstraction!
        legacyStack.remove(0);      // Remove by index - breaks LIFO!

        // ===== Replacement: ArrayDeque as Stack =====
        Deque<Integer> stack = new ArrayDeque<>();
        stack.push(1);              // [1]      (addFirst)
        stack.push(2);              // [2, 1]   (addFirst)
        stack.push(3);              // [3, 2, 1](addFirst)

        System.out.println(stack.peek());    // 3 (peekFirst)
        System.out.println(stack.pop());     // 3 (removeFirst)
        System.out.println(stack.isEmpty()); // false

        // ArrayDeque does NOT expose index-based access - proper encapsulation!
        // stack.get(0);  // COMPILE ERROR - not available
    }
}
```

### Migration Guide

| Stack Method | ArrayDeque Equivalent |
|---|---|
| `new Stack<>()` | `new ArrayDeque<>()` |
| `push(e)` | `push(e)` or `addFirst(e)` |
| `pop()` | `pop()` or `removeFirst()` |
| `peek()` | `peek()` or `peekFirst()` |
| `empty()` | `isEmpty()` |
| `search(o)` | No direct equivalent (iterate manually) |

---

## 7. BlockingQueue (Concurrency)

### Interface Overview

```java
// BlockingQueue adds blocking operations to Queue
public interface BlockingQueue<E> extends Queue<E> {
    // ===== Blocking Methods =====
    void put(E e) throws InterruptedException;    // Blocks until space available
    E take() throws InterruptedException;          // Blocks until element available

    // ===== Timed Blocking =====
    boolean offer(E e, long timeout, TimeUnit unit) throws InterruptedException;
    E poll(long timeout, TimeUnit unit) throws InterruptedException;

    // ===== Non-blocking (inherited from Queue) =====
    boolean offer(E e);   // Returns false if full
    E poll();             // Returns null if empty

    int remainingCapacity();
    int drainTo(Collection<? super E> c);
    int drainTo(Collection<? super E> c, int maxElements);
}
```

### Method Behavior Summary

| Method | Blocks? | On Full Queue | On Empty Queue |
|--------|---------|---------------|----------------|
| `add(e)` | No | `IllegalStateException` | N/A |
| `offer(e)` | No | Returns `false` | N/A |
| `put(e)` | **Yes** | Waits for space | N/A |
| `offer(e, time, unit)` | Timed | Waits up to timeout | N/A |
| `remove()` | No | N/A | `NoSuchElementException` |
| `poll()` | No | N/A | Returns `null` |
| `take()` | **Yes** | N/A | Waits for element |
| `poll(time, unit)` | Timed | N/A | Waits up to timeout |

### ArrayBlockingQueue (Bounded)

```java
import java.util.concurrent.*;

/**
 * - Fixed-size array (bounded)
 * - FIFO ordering
 * - Fair/unfair lock option
 * - Backed by ReentrantLock + two Conditions (notEmpty, notFull)
 */
public class ArrayBlockingQueueDemo {
    public static void main(String[] args) throws InterruptedException {
        // Capacity 5, fair ordering (FIFO for waiting threads)
        BlockingQueue<String> queue = new ArrayBlockingQueue<>(5, true);

        queue.put("A");         // Blocks if full
        queue.put("B");
        queue.offer("C");       // Non-blocking, returns true
        queue.offer("D", 1, TimeUnit.SECONDS);  // Waits up to 1 second

        String item = queue.take();   // "A" - blocks if empty
        String item2 = queue.poll();  // "B" - returns null if empty
        String item3 = queue.poll(500, TimeUnit.MILLISECONDS); // Waits up to 500ms

        System.out.println("Remaining capacity: " + queue.remainingCapacity());
    }
}
```

### LinkedBlockingQueue (Optionally Bounded)

```java
import java.util.concurrent.*;

/**
 * - Linked node structure
 * - Optionally bounded (default Integer.MAX_VALUE)
 * - Separate locks for put and take (higher throughput than ArrayBlockingQueue)
 * - Two-lock algorithm: putLock + takeLock
 */
public class LinkedBlockingQueueDemo {
    public static void main(String[] args) throws InterruptedException {
        // Bounded
        BlockingQueue<Integer> bounded = new LinkedBlockingQueue<>(100);

        // Unbounded (capacity = Integer.MAX_VALUE)
        BlockingQueue<Integer> unbounded = new LinkedBlockingQueue<>();

        bounded.put(1);
        bounded.put(2);
        bounded.put(3);

        // Drain elements to collection
        java.util.List<Integer> drained = new java.util.ArrayList<>();
        bounded.drainTo(drained, 2);  // Drain up to 2 elements
        System.out.println(drained);  // [1, 2]
    }
}
```

### PriorityBlockingQueue

```java
import java.util.concurrent.*;
import java.util.*;

/**
 * - Unbounded (grows automatically)
 * - Thread-safe PriorityQueue
 * - Blocking take() but offer() never blocks (unbounded)
 * - Uses binary heap + ReentrantLock
 */
public class PriorityBlockingQueueDemo {
    public static void main(String[] args) throws InterruptedException {
        PriorityBlockingQueue<Task> taskQueue = new PriorityBlockingQueue<>(
            11, Comparator.comparingInt(t -> t.priority)
        );

        taskQueue.put(new Task("Low", 3));
        taskQueue.put(new Task("High", 1));
        taskQueue.put(new Task("Medium", 2));

        // Takes highest priority (lowest number)
        System.out.println(taskQueue.take().name);  // "High"
        System.out.println(taskQueue.take().name);  // "Medium"
        System.out.println(taskQueue.take().name);  // "Low"
    }

    static class Task {
        String name;
        int priority;
        Task(String name, int priority) { this.name = name; this.priority = priority; }
    }
}
```

### DelayQueue

```java
import java.util.concurrent.*;
import java.util.*;

/**
 * - Elements must implement Delayed interface
 * - Elements can only be taken when their delay has expired
 * - Unbounded queue
 * - Uses PriorityQueue internally (ordered by expiration time)
 * - Use cases: scheduled tasks, cache expiration, rate limiting
 */
public class DelayQueueDemo {

    static class DelayedTask implements Delayed {
        private String name;
        private long executeAt;  // absolute time in milliseconds

        DelayedTask(String name, long delayMs) {
            this.name = name;
            this.executeAt = System.currentTimeMillis() + delayMs;
        }

        @Override
        public long getDelay(TimeUnit unit) {
            long diff = executeAt - System.currentTimeMillis();
            return unit.convert(diff, TimeUnit.MILLISECONDS);
        }

        @Override
        public int compareTo(Delayed other) {
            return Long.compare(this.executeAt, ((DelayedTask) other).executeAt);
        }

        @Override
        public String toString() { return name; }
    }

    public static void main(String[] args) throws InterruptedException {
        DelayQueue<DelayedTask> queue = new DelayQueue<>();

        queue.put(new DelayedTask("Task-3s", 3000));
        queue.put(new DelayedTask("Task-1s", 1000));
        queue.put(new DelayedTask("Task-2s", 2000));

        System.out.println("Waiting for tasks...");

        // Tasks come out in delay order
        System.out.println(queue.take()); // Task-1s (after ~1 second)
        System.out.println(queue.take()); // Task-2s (after ~2 seconds)
        System.out.println(queue.take()); // Task-3s (after ~3 seconds)
    }
}
```

### SynchronousQueue

```java
import java.util.concurrent.*;

/**
 * - Zero-capacity queue (no internal storage!)
 * - Every put() must wait for a corresponding take() (and vice versa)
 * - Direct handoff between threads
 * - Fair/unfair modes
 * - Use cases: thread pools (Executors.newCachedThreadPool uses this)
 */
public class SynchronousQueueDemo {
    public static void main(String[] args) {
        SynchronousQueue<String> queue = new SynchronousQueue<>();

        // Producer thread
        new Thread(() -> {
            try {
                System.out.println("Putting message...");
                queue.put("Hello");  // Blocks until consumer takes
                System.out.println("Message delivered!");
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            }
        }).start();

        // Consumer thread
        new Thread(() -> {
            try {
                Thread.sleep(2000);  // Simulate delay
                String msg = queue.take();  // Blocks until producer puts
                System.out.println("Received: " + msg);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            }
        }).start();

        // Note: queue.size() is always 0
        // queue.peek() always returns null
        // queue.offer(e) returns false unless another thread is waiting to take
    }
}
```

### Producer-Consumer Pattern

```java
import java.util.concurrent.*;
import java.util.*;

public class ProducerConsumerPattern {

    // ===== Basic Producer-Consumer =====
    static class MessageQueue<T> {
        private final BlockingQueue<T> queue;
        private volatile boolean running = true;

        MessageQueue(int capacity) {
            this.queue = new ArrayBlockingQueue<>(capacity);
        }

        void produce(T item) throws InterruptedException {
            queue.put(item);  // Blocks if queue is full
        }

        T consume() throws InterruptedException {
            return queue.take();  // Blocks if queue is empty
        }

        void shutdown() { running = false; }
        boolean isRunning() { return running; }
        int size() { return queue.size(); }
    }

    // ===== Multiple Producers, Multiple Consumers =====
    public static void main(String[] args) throws InterruptedException {
        BlockingQueue<Integer> queue = new LinkedBlockingQueue<>(10);
        int NUM_PRODUCERS = 3;
        int NUM_CONSUMERS = 2;
        int POISON_PILL = -1;

        // Producers
        for (int i = 0; i < NUM_PRODUCERS; i++) {
            final int producerId = i;
            new Thread(() -> {
                try {
                    for (int j = 0; j < 5; j++) {
                        int item = producerId * 100 + j;
                        queue.put(item);
                        System.out.printf("Producer-%d produced: %d%n", producerId, item);
                        Thread.sleep((long)(Math.random() * 100));
                    }
                } catch (InterruptedException e) {
                    Thread.currentThread().interrupt();
                }
            }, "Producer-" + i).start();
        }

        // Consumers
        for (int i = 0; i < NUM_CONSUMERS; i++) {
            final int consumerId = i;
            new Thread(() -> {
                try {
                    while (true) {
                        Integer item = queue.poll(2, TimeUnit.SECONDS);
                        if (item == null) break; // Timeout = no more items
                        if (item == POISON_PILL) break;
                        System.out.printf("Consumer-%d consumed: %d%n", consumerId, item);
                        Thread.sleep((long)(Math.random() * 200));
                    }
                } catch (InterruptedException e) {
                    Thread.currentThread().interrupt();
                }
            }, "Consumer-" + i).start();
        }
    }
}
```

### Bounded Buffer with BlockingQueue (Classic LLD)

```java
import java.util.concurrent.*;

/**
 * LLD: Message Broker / Event Queue
 */
public class SimpleMessageBroker<T> {
    private final BlockingQueue<T> queue;
    private final String topic;
    private volatile boolean active = true;

    public SimpleMessageBroker(String topic, int capacity) {
        this.topic = topic;
        this.queue = new ArrayBlockingQueue<>(capacity);
    }

    public boolean publish(T message) {
        if (!active) return false;
        return queue.offer(message);  // Non-blocking
    }

    public boolean publishBlocking(T message, long timeout, TimeUnit unit)
            throws InterruptedException {
        if (!active) return false;
        return queue.offer(message, timeout, unit);  // Bounded wait
    }

    public T subscribe() throws InterruptedException {
        return queue.take();  // Blocking wait for message
    }

    public T subscribe(long timeout, TimeUnit unit) throws InterruptedException {
        return queue.poll(timeout, unit);  // Bounded wait
    }

    public void shutdown() {
        active = false;
    }

    public int pendingMessages() {
        return queue.size();
    }

    public int capacity() {
        return queue.remainingCapacity() + queue.size();
    }

    public static void main(String[] args) throws InterruptedException {
        SimpleMessageBroker<String> broker = new SimpleMessageBroker<>("orders", 100);

        // Publisher thread
        Thread publisher = new Thread(() -> {
            for (int i = 0; i < 10; i++) {
                broker.publish("Order-" + i);
            }
        });

        // Subscriber thread
        Thread subscriber = new Thread(() -> {
            try {
                for (int i = 0; i < 10; i++) {
                    String msg = broker.subscribe(5, TimeUnit.SECONDS);
                    if (msg != null) System.out.println("Processing: " + msg);
                }
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            }
        });

        publisher.start();
        subscriber.start();
        publisher.join();
        subscriber.join();
    }
}
```

---

## 8. Comparator and Comparable

### Comparable Interface (Natural Ordering)

```java
/**
 * Comparable<T> - defines the natural ordering of a class
 * - Implemented BY the class itself
 * - Single ordering only
 * - Used by: TreeSet, TreeMap, PriorityQueue, Collections.sort(), Arrays.sort()
 */
public class Employee implements Comparable<Employee> {
    private String name;
    private int age;
    private double salary;

    public Employee(String name, int age, double salary) {
        this.name = name;
        this.age = age;
        this.salary = salary;
    }

    @Override
    public int compareTo(Employee other) {
        // Returns:
        //   negative -> this < other
        //   zero     -> this == other
        //   positive -> this > other
        return Integer.compare(this.age, other.age);  // Natural order by age
    }

    // Getters
    public String getName() { return name; }
    public int getAge() { return age; }
    public double getSalary() { return salary; }

    @Override
    public String toString() {
        return String.format("%s(age=%d, salary=%.0f)", name, age, salary);
    }
}
```

### Comparator Interface (Custom Ordering)

```java
import java.util.*;

/**
 * Comparator<T> - defines an external ordering strategy
 * - Separate class/lambda, does NOT modify the class
 * - Multiple orderings possible
 * - Preferred in most LLD scenarios (strategy pattern)
 */
public class ComparatorExamples {
    public static void main(String[] args) {
        List<Employee> employees = Arrays.asList(
            new Employee("Alice", 30, 75000),
            new Employee("Bob", 25, 85000),
            new Employee("Charlie", 35, 65000),
            new Employee("Diana", 28, 90000),
            new Employee("Eve", 30, 80000)
        );

        // ===== Anonymous Class =====
        Comparator<Employee> byName = new Comparator<Employee>() {
            @Override
            public int compare(Employee a, Employee b) {
                return a.getName().compareTo(b.getName());
            }
        };

        // ===== Lambda =====
        Comparator<Employee> bySalary = (a, b) -> Double.compare(a.getSalary(), b.getSalary());

        // ===== Method References with Comparator.comparing =====
        Comparator<Employee> byAge = Comparator.comparingInt(Employee::getAge);
        Comparator<Employee> byNameComp = Comparator.comparing(Employee::getName);
        Comparator<Employee> bySalaryComp = Comparator.comparingDouble(Employee::getSalary);

        // ===== Reversed =====
        Comparator<Employee> bySalaryDesc = Comparator.comparingDouble(Employee::getSalary).reversed();

        // ===== Multiple Fields (thenComparing) =====
        Comparator<Employee> byAgeThenName = Comparator
            .comparingInt(Employee::getAge)
            .thenComparing(Employee::getName);

        Comparator<Employee> byAgeThenSalaryDesc = Comparator
            .comparingInt(Employee::getAge)
            .thenComparing(Comparator.comparingDouble(Employee::getSalary).reversed());

        // ===== Null-safe Comparators =====
        Comparator<Employee> nullSafeByName = Comparator.comparing(
            Employee::getName,
            Comparator.nullsFirst(Comparator.naturalOrder())
        );

        Comparator<Employee> nullsLast = Comparator.comparing(
            Employee::getName,
            Comparator.nullsLast(Comparator.naturalOrder())
        );

        // ===== Usage =====
        // Sort list
        employees.sort(byAgeThenName);
        Collections.sort(employees, bySalaryDesc);

        // PriorityQueue with custom comparator
        PriorityQueue<Employee> pq = new PriorityQueue<>(bySalaryDesc);
        pq.addAll(employees);

        // TreeSet with custom comparator
        TreeSet<Employee> sorted = new TreeSet<>(byNameComp);
        sorted.addAll(employees);

        // ===== Printing sorted =====
        System.out.println("By age then name:");
        employees.sort(byAgeThenName);
        employees.forEach(System.out::println);

        System.out.println("\nBy salary descending:");
        employees.sort(bySalaryDesc);
        employees.forEach(System.out::println);
    }
}
```

### Complete Comparator Factory Methods

```java
import java.util.*;

public class ComparatorFactoryMethods {
    public static void main(String[] args) {

        // ===== Comparator.comparing() variants =====
        // comparing(keyExtractor)
        Comparator<String> byLength = Comparator.comparing(String::length);

        // comparing(keyExtractor, keyComparator)
        Comparator<String> byLengthDesc = Comparator.comparing(String::length, Comparator.reverseOrder());

        // comparingInt, comparingLong, comparingDouble (avoids boxing)
        Comparator<String> byLengthPrimitive = Comparator.comparingInt(String::length);

        // ===== Chaining with thenComparing =====
        Comparator<String> byLengthThenAlpha = Comparator
            .comparingInt(String::length)
            .thenComparing(Comparator.naturalOrder());  // alphabetical for same length

        // ===== reversed() =====
        Comparator<String> descLength = Comparator.comparingInt(String::length).reversed();

        // ===== naturalOrder() and reverseOrder() =====
        Comparator<Integer> natural = Comparator.naturalOrder();    // 1, 2, 3...
        Comparator<Integer> reverse = Comparator.reverseOrder();    // 9, 8, 7...

        // ===== nullsFirst() and nullsLast() =====
        List<String> withNulls = Arrays.asList("banana", null, "apple", null, "cherry");
        withNulls.sort(Comparator.nullsFirst(Comparator.naturalOrder()));
        System.out.println(withNulls); // [null, null, apple, banana, cherry]

        withNulls.sort(Comparator.nullsLast(Comparator.naturalOrder()));
        System.out.println(withNulls); // [apple, banana, cherry, null, null]

        // ===== Complex multi-field example =====
        record Student(String name, int grade, double gpa) {}

        List<Student> students = Arrays.asList(
            new Student("Alice", 12, 3.8),
            new Student("Bob", 11, 3.9),
            new Student("Charlie", 12, 3.8),
            new Student("Diana", 11, 3.7),
            new Student("Eve", 12, 3.9)
        );

        // Sort by: grade DESC, then GPA DESC, then name ASC
        Comparator<Student> studentComparator = Comparator
            .comparingInt(Student::grade).reversed()        // grade descending
            .thenComparingDouble(Student::gpa).reversed()   // gpa descending -- WRONG! See below
            .thenComparing(Student::name);                  // name ascending

        // CORRECT way to chain reversed on multiple fields:
        Comparator<Student> correctComparator = Comparator
            .comparingInt(Student::grade).reversed()
            .thenComparing(Comparator.comparingDouble(Student::gpa).reversed())
            .thenComparing(Student::name);

        students.sort(correctComparator);
        students.forEach(s -> System.out.printf("%s: grade=%d, gpa=%.1f%n", s.name(), s.grade(), s.gpa()));
    }
}
```

### Comparable vs Comparator

| Feature | Comparable | Comparator |
|---------|-----------|------------|
| Package | `java.lang` | `java.util` |
| Method | `compareTo(T o)` | `compare(T o1, T o2)` |
| Modifies class | Yes (implements interface) | No (external) |
| Number of orderings | One (natural) | Many (strategies) |
| Null handling | Must handle manually | `nullsFirst`/`nullsLast` |
| Lambda support | No (functional interface but impractical) | Yes |
| Common usage | String, Integer, Date | Collections.sort, PriorityQueue, TreeMap |
| **Best for LLD** | Domain objects with obvious natural order | **Preferred** - strategy pattern, flexibility |

### Advanced: Comparator in PriorityQueue for LLD

```java
import java.util.*;

public class ComparatorInLLD {

    // ===== Example: Order Matching Engine (Stock Exchange) =====
    record Order(String id, double price, long timestamp, int quantity, boolean isBuy) {}

    public static void main(String[] args) {
        // Buy orders: highest price first, then earliest timestamp (price-time priority)
        PriorityQueue<Order> buyOrders = new PriorityQueue<>(
            Comparator.comparingDouble(Order::price).reversed()
                      .thenComparingLong(Order::timestamp)
        );

        // Sell orders: lowest price first, then earliest timestamp
        PriorityQueue<Order> sellOrders = new PriorityQueue<>(
            Comparator.comparingDouble(Order::price)
                      .thenComparingLong(Order::timestamp)
        );

        buyOrders.offer(new Order("B1", 100.5, 1000L, 10, true));
        buyOrders.offer(new Order("B2", 101.0, 1001L, 5, true));
        buyOrders.offer(new Order("B3", 101.0, 999L, 8, true));

        // B3 comes first (same price 101.0 but earlier timestamp)
        System.out.println(buyOrders.poll()); // B3 (101.0, ts=999)
        System.out.println(buyOrders.poll()); // B2 (101.0, ts=1001)
        System.out.println(buyOrders.poll()); // B1 (100.5)
    }
}
```

---

## 9. Time Complexity Summary

### Queue Implementations

| Operation | LinkedList | ArrayDeque | PriorityQueue | ArrayBlockingQueue |
|-----------|-----------|------------|---------------|-------------------|
| offer/add | O(1) | O(1)* | O(log n) | O(1) |
| poll/remove | O(1) | O(1)* | O(log n) | O(1) |
| peek | O(1) | O(1) | O(1) | O(1) |
| contains | O(n) | O(n) | O(n) | O(n) |
| remove(Object) | O(n) | O(n) | O(n) | O(n) |
| size | O(1) | O(1) | O(1) | O(1) |

*Amortized O(1) - occasional O(n) resize

### Stack Implementations

| Operation | ArrayDeque (push/pop) | Stack (legacy) |
|-----------|----------------------|----------------|
| push | O(1)* | O(1)* |
| pop | O(1) | O(1) |
| peek | O(1) | O(1) |
| search | O(n) | O(n) |

### Space Complexity

| Implementation | Space | Notes |
|----------------|-------|-------|
| ArrayDeque | O(n) | Contiguous array, may have unused capacity |
| LinkedList | O(n) | Extra 2 pointers per node (prev + next) |
| PriorityQueue | O(n) | Array-backed, may have unused capacity |
| Stack | O(n) | Backed by Vector |

---

## 10. LLD Design Examples

### Example 1: Task Scheduler with Priority and Delay

```java
import java.util.*;
import java.util.concurrent.*;

/**
 * LLD: Task Scheduler
 * - Tasks have priority and scheduled execution time
 * - Higher priority tasks execute first
 * - Tasks can be cancelled
 * - Thread-safe
 */
public class TaskSchedulerLLD {

    enum TaskStatus { PENDING, RUNNING, COMPLETED, CANCELLED }

    static class ScheduledTask implements Comparable<ScheduledTask> {
        private final String id;
        private final Runnable action;
        private final int priority;         // Lower = higher priority
        private final long scheduledTime;   // When to execute (epoch ms)
        private volatile TaskStatus status;

        ScheduledTask(String id, Runnable action, int priority, long delayMs) {
            this.id = id;
            this.action = action;
            this.priority = priority;
            this.scheduledTime = System.currentTimeMillis() + delayMs;
            this.status = TaskStatus.PENDING;
        }

        @Override
        public int compareTo(ScheduledTask other) {
            // First by scheduled time, then by priority
            int timeCompare = Long.compare(this.scheduledTime, other.scheduledTime);
            if (timeCompare != 0) return timeCompare;
            return Integer.compare(this.priority, other.priority);
        }

        void cancel() { this.status = TaskStatus.CANCELLED; }
        boolean isReady() { return System.currentTimeMillis() >= scheduledTime; }
    }

    private final PriorityBlockingQueue<ScheduledTask> taskQueue;
    private final ExecutorService executor;
    private volatile boolean running;

    public TaskSchedulerLLD(int workerThreads) {
        this.taskQueue = new PriorityBlockingQueue<>();
        this.executor = Executors.newFixedThreadPool(workerThreads);
        this.running = true;
    }

    public String schedule(String id, Runnable action, int priority, long delayMs) {
        ScheduledTask task = new ScheduledTask(id, action, priority, delayMs);
        taskQueue.offer(task);
        return id;
    }

    public void start() {
        new Thread(() -> {
            while (running) {
                try {
                    ScheduledTask task = taskQueue.take();
                    if (task.status == TaskStatus.CANCELLED) continue;

                    if (!task.isReady()) {
                        // Not ready yet, put back and wait
                        taskQueue.offer(task);
                        Thread.sleep(10);
                        continue;
                    }

                    task.status = TaskStatus.RUNNING;
                    executor.submit(() -> {
                        try {
                            task.action.run();
                            task.status = TaskStatus.COMPLETED;
                        } catch (Exception e) {
                            System.err.println("Task " + task.id + " failed: " + e.getMessage());
                        }
                    });
                } catch (InterruptedException e) {
                    Thread.currentThread().interrupt();
                    break;
                }
            }
        }, "scheduler-thread").start();
    }

    public void shutdown() {
        running = false;
        executor.shutdown();
    }
}
```

### Example 2: Undo/Redo System with Deque

```java
import java.util.*;

/**
 * LLD: Undo/Redo using two Deques (Command Pattern)
 */
public class UndoRedoSystem<T> {

    interface Command<T> {
        T execute(T state);
        T undo(T state);
        String description();
    }

    private T currentState;
    private final Deque<Command<T>> undoStack;
    private final Deque<Command<T>> redoStack;
    private final int maxHistory;

    public UndoRedoSystem(T initialState, int maxHistory) {
        this.currentState = initialState;
        this.undoStack = new ArrayDeque<>();
        this.redoStack = new ArrayDeque<>();
        this.maxHistory = maxHistory;
    }

    public T execute(Command<T> command) {
        currentState = command.execute(currentState);
        undoStack.push(command);
        redoStack.clear();  // New action invalidates redo history

        // Limit history size
        if (undoStack.size() > maxHistory) {
            // Remove oldest (bottom of stack = last element)
            ((ArrayDeque<Command<T>>) undoStack).removeLast();
        }

        return currentState;
    }

    public T undo() {
        if (undoStack.isEmpty()) {
            throw new IllegalStateException("Nothing to undo");
        }
        Command<T> command = undoStack.pop();
        currentState = command.undo(currentState);
        redoStack.push(command);
        return currentState;
    }

    public T redo() {
        if (redoStack.isEmpty()) {
            throw new IllegalStateException("Nothing to redo");
        }
        Command<T> command = redoStack.pop();
        currentState = command.execute(currentState);
        undoStack.push(command);
        return currentState;
    }

    public boolean canUndo() { return !undoStack.isEmpty(); }
    public boolean canRedo() { return !redoStack.isEmpty(); }
    public T getState() { return currentState; }

    public List<String> getUndoHistory() {
        List<String> history = new ArrayList<>();
        for (Command<T> cmd : undoStack) {
            history.add(cmd.description());
        }
        return history;
    }

    // ===== Usage Example: Text Editor =====
    public static void main(String[] args) {
        UndoRedoSystem<String> editor = new UndoRedoSystem<>("", 50);

        // Append command
        Command<String> appendHello = new Command<>() {
            public String execute(String state) { return state + "Hello"; }
            public String undo(String state) { return state.substring(0, state.length() - 5); }
            public String description() { return "Append 'Hello'"; }
        };

        Command<String> appendWorld = new Command<>() {
            public String execute(String state) { return state + " World"; }
            public String undo(String state) { return state.substring(0, state.length() - 6); }
            public String description() { return "Append ' World'"; }
        };

        editor.execute(appendHello);  // "Hello"
        editor.execute(appendWorld);  // "Hello World"
        System.out.println(editor.getState());  // "Hello World"

        editor.undo();  // "Hello"
        System.out.println(editor.getState());  // "Hello"

        editor.redo();  // "Hello World"
        System.out.println(editor.getState());  // "Hello World"

        editor.undo();  // "Hello"
        editor.undo();  // ""
        System.out.println(editor.getState());  // ""
    }
}
```

### Example 3: LRU Cache using Deque

```java
import java.util.*;

/**
 * LLD: LRU Cache (simplified version using Deque + HashMap)
 * Real implementation uses doubly-linked list for O(1) move-to-front
 */
public class LRUCache<K, V> {
    private final int capacity;
    private final Map<K, V> map;
    private final Deque<K> accessOrder;  // Most recent at front

    public LRUCache(int capacity) {
        this.capacity = capacity;
        this.map = new HashMap<>();
        this.accessOrder = new ArrayDeque<>();
    }

    public V get(K key) {
        if (!map.containsKey(key)) return null;

        // Move to front (most recently used)
        accessOrder.remove(key);  // O(n) - use LinkedHashMap for O(1)
        accessOrder.addFirst(key);
        return map.get(key);
    }

    public void put(K key, V value) {
        if (map.containsKey(key)) {
            accessOrder.remove(key);
        } else if (map.size() >= capacity) {
            // Evict least recently used (at the tail)
            K evicted = accessOrder.removeLast();
            map.remove(evicted);
        }
        map.put(key, value);
        accessOrder.addFirst(key);
    }

    public int size() { return map.size(); }

    public static void main(String[] args) {
        LRUCache<Integer, String> cache = new LRUCache<>(3);
        cache.put(1, "one");
        cache.put(2, "two");
        cache.put(3, "three");

        cache.get(1);          // Access 1, order: [1, 3, 2]
        cache.put(4, "four");  // Evicts 2 (LRU), order: [4, 1, 3]

        System.out.println(cache.get(2));  // null (evicted)
        System.out.println(cache.get(1));  // "one"
        System.out.println(cache.get(3));  // "three"
    }
}
```

### Example 4: Rate Limiter using Deque (Sliding Window)

```java
import java.util.*;

/**
 * LLD: Sliding Window Rate Limiter
 * Uses ArrayDeque to track timestamps of requests
 */
public class SlidingWindowRateLimiter {
    private final int maxRequests;
    private final long windowSizeMs;
    private final Map<String, Deque<Long>> clientWindows;

    public SlidingWindowRateLimiter(int maxRequests, long windowSizeMs) {
        this.maxRequests = maxRequests;
        this.windowSizeMs = windowSizeMs;
        this.clientWindows = new HashMap<>();
    }

    public synchronized boolean allowRequest(String clientId) {
        long now = System.currentTimeMillis();
        Deque<Long> window = clientWindows.computeIfAbsent(clientId, k -> new ArrayDeque<>());

        // Remove expired timestamps from the front (oldest first)
        while (!window.isEmpty() && now - window.peekFirst() > windowSizeMs) {
            window.pollFirst();
        }

        if (window.size() < maxRequests) {
            window.offerLast(now);
            return true;  // Request allowed
        }

        return false;  // Rate limited
    }

    public static void main(String[] args) throws InterruptedException {
        // Allow 5 requests per 1000ms window
        SlidingWindowRateLimiter limiter = new SlidingWindowRateLimiter(5, 1000);

        for (int i = 0; i < 8; i++) {
            boolean allowed = limiter.allowRequest("user-1");
            System.out.printf("Request %d: %s%n", i + 1, allowed ? "ALLOWED" : "REJECTED");
        }
        // First 5: ALLOWED, next 3: REJECTED

        Thread.sleep(1100);  // Wait for window to expire
        System.out.println("After waiting: " + limiter.allowRequest("user-1")); // ALLOWED
    }
}
```

### Example 5: Event-Driven System with PriorityQueue

```java
import java.util.*;

/**
 * LLD: Event-Driven Simulation (Discrete Event Simulation)
 * Events are processed in chronological order using PriorityQueue
 */
public class EventDrivenSimulation {

    interface Event extends Comparable<Event> {
        long getTimestamp();
        void execute(EventDrivenSimulation sim);
        String getType();
    }

    abstract static class BaseEvent implements Event {
        protected final long timestamp;
        protected final String type;

        BaseEvent(long timestamp, String type) {
            this.timestamp = timestamp;
            this.type = type;
        }

        @Override public long getTimestamp() { return timestamp; }
        @Override public String getType() { return type; }
        @Override public int compareTo(Event other) {
            return Long.compare(this.timestamp, other.getTimestamp());
        }
    }

    private final PriorityQueue<Event> eventQueue = new PriorityQueue<>();
    private long currentTime = 0;

    public void scheduleEvent(Event event) {
        if (event.getTimestamp() < currentTime) {
            throw new IllegalArgumentException("Cannot schedule event in the past");
        }
        eventQueue.offer(event);
    }

    public void run(long maxTime) {
        while (!eventQueue.isEmpty()) {
            Event event = eventQueue.peek();
            if (event.getTimestamp() > maxTime) break;

            eventQueue.poll();
            currentTime = event.getTimestamp();
            System.out.printf("[t=%d] Processing: %s%n", currentTime, event.getType());
            event.execute(this);
        }
    }

    public long getCurrentTime() { return currentTime; }

    public static void main(String[] args) {
        EventDrivenSimulation sim = new EventDrivenSimulation();

        // Schedule events out of order - PQ will process them in order
        sim.scheduleEvent(new BaseEvent(500, "ProcessPayment") {
            public void execute(EventDrivenSimulation s) {
                System.out.println("  Payment processed");
                s.scheduleEvent(new BaseEvent(s.getCurrentTime() + 100, "SendReceipt") {
                    public void execute(EventDrivenSimulation s2) {
                        System.out.println("  Receipt sent");
                    }
                });
            }
        });

        sim.scheduleEvent(new BaseEvent(100, "ReceiveOrder") {
            public void execute(EventDrivenSimulation s) {
                System.out.println("  Order received, scheduling validation");
                s.scheduleEvent(new BaseEvent(s.getCurrentTime() + 200, "ValidateOrder") {
                    public void execute(EventDrivenSimulation s2) {
                        System.out.println("  Order validated");
                    }
                });
            }
        });

        sim.run(1000);
        // Output:
        // [t=100] Processing: ReceiveOrder
        //   Order received, scheduling validation
        // [t=300] Processing: ValidateOrder
        //   Order validated
        // [t=500] Processing: ProcessPayment
        //   Payment processed
        // [t=600] Processing: SendReceipt
        //   Receipt sent
    }
}
```

---

## Quick Reference Card

```
┌─────────────────────────────────────────────────────────────────┐
│                    QUEUE CHEAT SHEET                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Need a Queue (FIFO)?           → ArrayDeque                    │
│  Need a Stack (LIFO)?           → ArrayDeque                    │
│  Need priority ordering?        → PriorityQueue                 │
│  Need thread-safe queue?        → ConcurrentLinkedQueue         │
│  Need blocking queue?           → LinkedBlockingQueue           │
│  Need bounded blocking queue?   → ArrayBlockingQueue            │
│  Need priority + blocking?      → PriorityBlockingQueue         │
│  Need delayed elements?         → DelayQueue                    │
│  Need direct handoff?           → SynchronousQueue              │
│  Need null elements in queue?   → LinkedList                    │
│  Need List + Queue interface?   → LinkedList                    │
│                                                                 │
│  NEVER use Stack class!         → Use ArrayDeque instead        │
│  NEVER use Vector!              → Use ArrayList instead         │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│  PriorityQueue patterns:                                        │
│    Min-heap: new PriorityQueue<>()                              │
│    Max-heap: new PriorityQueue<>(Comparator.reverseOrder())     │
│    Top-K largest:  min-heap of size K                           │
│    Top-K smallest: max-heap of size K                           │
│    Kth largest:    min-heap of size K, peek()                   │
│    Running median: max-heap (lower) + min-heap (upper)          │
│    Merge K sorted: min-heap with [value, listIdx, elemIdx]      │
├─────────────────────────────────────────────────────────────────┤
│  Comparator shortcuts:                                          │
│    Comparator.comparingInt(T::getField)                         │
│    Comparator.comparing(T::getField).reversed()                 │
│    comp1.thenComparing(comp2)                                   │
│    Comparator.nullsFirst(Comparator.naturalOrder())             │
└─────────────────────────────────────────────────────────────────┘
```
