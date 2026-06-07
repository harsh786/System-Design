# Queue, Deque, ArrayDeque, PriorityQueue, BlockingQueue

`Queue<E>` models elements waiting to be processed. It is used for jobs, BFS traversal, event handling, rate limiting, scheduling, and producer-consumer systems.

## Queue Method Pairs

`Queue` has two styles of methods: exception-throwing and special-value-returning.

| Operation | Throws exception | Returns special value |
|---|---|---|
| Insert | `add(e)` | `offer(e)` |
| Remove head | `remove()` | `poll()` |
| Read head | `element()` | `peek()` |

Use `offer`, `poll`, and `peek` in most production-style code because they handle full/empty queues without exceptions.

```java
Queue<String> queue = new ArrayDeque<>();
queue.offer("job-1");
queue.offer("job-2");

String next = queue.peek(); // read without removing
String done = queue.poll(); // remove
String missing = queue.poll(); // null if empty
```

## Deque

`Deque<E>` means double-ended queue. It supports operations at both front and back.

| Method | Meaning |
|---|---|
| `addFirst(e)` / `offerFirst(e)` | Insert at front |
| `addLast(e)` / `offerLast(e)` | Insert at back |
| `removeFirst()` / `pollFirst()` | Remove front |
| `removeLast()` / `pollLast()` | Remove back |
| `getFirst()` / `peekFirst()` | Read front |
| `getLast()` / `peekLast()` | Read back |
| `push(e)` | Stack push at front |
| `pop()` | Stack pop from front |
| `descendingIterator()` | Traverse from back to front |

## ArrayDeque

`ArrayDeque` is usually the best implementation for:

- normal queues
- stacks
- double-ended queues
- sliding window algorithms

It is faster than `Stack` and usually faster than `LinkedList`.

```java
Deque<Integer> stack = new ArrayDeque<>();
stack.push(10);
stack.push(20);
System.out.println(stack.pop()); // 20

Deque<String> line = new ArrayDeque<>();
line.offerLast("A");
line.offerLast("B");
System.out.println(line.pollFirst()); // A
```

`ArrayDeque` does not allow `null`.

## LinkedList As Queue/Deque

`LinkedList` implements both `List` and `Deque`, so it can be used as a queue.

```java
Queue<String> q = new LinkedList<>();
```

But for most queue/deque use cases, prefer `ArrayDeque` because it has lower memory overhead and better locality.

## PriorityQueue

`PriorityQueue<E>` returns the smallest element first by natural ordering, or the highest-priority element by a custom comparator.

Important facts:

- It is a heap, not a sorted list.
- `peek()` gives the current best element.
- `poll()` removes the current best element.
- Iterating or printing a `PriorityQueue` does not show sorted order.
- It does not allow `null`.
- It is not thread-safe.

Natural order min-heap:

```java
PriorityQueue<Integer> minHeap = new PriorityQueue<>();
minHeap.offer(5);
minHeap.offer(1);
minHeap.offer(3);
System.out.println(minHeap.poll()); // 1
```

Max-heap:

```java
PriorityQueue<Integer> maxHeap = new PriorityQueue<>(Comparator.reverseOrder());
```

Object priority:

```java
record Task(String name, int priority) {}

PriorityQueue<Task> tasks = new PriorityQueue<>(
    Comparator.comparingInt(Task::priority)
);
```

## PriorityQueue Methods

| Method | Meaning |
|---|---|
| `offer(e)` | Add element |
| `add(e)` | Add element, may throw in capacity-restricted queues |
| `peek()` | Read best element without removing |
| `poll()` | Remove best element, or return `null` if empty |
| `remove()` | Remove best element, or throw if empty |
| `remove(Object)` | Remove one matching element, O(n) |
| `contains(Object)` | Check existence, O(n) |
| `size()` | Number of elements |
| `clear()` | Remove all |

Complexity:

| Operation | Complexity |
|---|---:|
| `offer` | O(log n) |
| `poll` | O(log n) |
| `peek` | O(1) |
| `contains` | O(n) |
| `remove(Object)` | O(n) |

## BlockingQueue

`BlockingQueue` is used in concurrent producer-consumer designs.

Important implementations:

| Class | Meaning |
|---|---|
| `ArrayBlockingQueue` | Bounded array-backed blocking queue |
| `LinkedBlockingQueue` | Optionally bounded linked blocking queue |
| `PriorityBlockingQueue` | Priority-based blocking queue |
| `DelayQueue` | Elements become available after delay |
| `SynchronousQueue` | Direct handoff, no internal capacity |

Important methods:

| Method | Meaning |
|---|---|
| `put(e)` | Wait until space exists, then insert |
| `take()` | Wait until an element exists, then remove |
| `offer(e, timeout, unit)` | Wait up to timeout to insert |
| `poll(timeout, unit)` | Wait up to timeout to remove |

## LLD Uses

- Notification worker queue: `BlockingQueue<NotificationJob>`
- Shortest-job-first scheduler: `PriorityQueue<Job>`
- BFS traversal: `Queue<Node>`
- Undo/redo: two `Deque<Command>` stacks
- Rate limiter: `Deque<Long>` timestamps
- Elevator scheduling: `PriorityQueue<Request>` or `TreeSet<Request>`

Runnable example: `src/main/java/com/codex/javaconcepts/collections/QueueExamples.java`

