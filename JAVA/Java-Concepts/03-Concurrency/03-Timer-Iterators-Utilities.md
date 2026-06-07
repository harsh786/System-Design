# Timer, Scheduling, Iterators, and Utility Classes

---

## 1. java.util.Timer and TimerTask

### Overview

`Timer` creates a **single background thread** that executes `TimerTask` objects sequentially.

```java
import java.util.Timer;
import java.util.TimerTask;
import java.util.Date;

// TimerTask is abstract, implements Runnable
// You must override the abstract run() method
```

### 1.1 One-Time Execution After Delay

```java
import java.util.Timer;
import java.util.TimerTask;

public class TimerDelayExample {
    public static void main(String[] args) {
        Timer timer = new Timer();

        TimerTask task = new TimerTask() {
            @Override
            public void run() {
                System.out.println("Task executed after 2 seconds delay");
                System.out.println("Thread: " + Thread.currentThread().getName());
                timer.cancel(); // terminate the timer thread
            }
        };

        System.out.println("Scheduling task...");
        timer.schedule(task, 2000); // execute after 2000ms delay
        System.out.println("Task scheduled. Main thread continues...");
    }
}
// Output:
// Scheduling task...
// Task scheduled. Main thread continues...
// (after 2 seconds)
// Task executed after 2 seconds delay
// Thread: Timer-0
```

### 1.2 One-Time Execution at Specific Date

```java
import java.util.Timer;
import java.util.TimerTask;
import java.util.Date;
import java.util.Calendar;

public class TimerDateExample {
    public static void main(String[] args) {
        Timer timer = new Timer();

        // Schedule for 5 seconds from now
        Calendar cal = Calendar.getInstance();
        cal.add(Calendar.SECOND, 5);
        Date scheduledDate = cal.getTime();

        TimerTask task = new TimerTask() {
            @Override
            public void run() {
                System.out.println("Task executed at: " + new Date());
                timer.cancel();
            }
        };

        System.out.println("Current time: " + new Date());
        System.out.println("Scheduled for: " + scheduledDate);
        timer.schedule(task, scheduledDate);
    }
}
```

### 1.3 Fixed-Delay Repeated Execution

**Fixed-delay**: Each execution is scheduled relative to the **actual** execution time of the previous execution. If an execution is delayed (e.g., GC pause), subsequent executions are also delayed.

```java
import java.util.Timer;
import java.util.TimerTask;
import java.util.Date;

public class FixedDelayExample {
    public static void main(String[] args) throws InterruptedException {
        Timer timer = new Timer();
        final int[] count = {0};

        TimerTask task = new TimerTask() {
            @Override
            public void run() {
                count[0]++;
                System.out.println("Execution #" + count[0] + " at " +
                    System.currentTimeMillis() + " Thread: " + Thread.currentThread().getName());

                // Simulate varying work time
                if (count[0] == 2) {
                    try { Thread.sleep(3000); } catch (InterruptedException e) {}
                }

                if (count[0] >= 5) {
                    timer.cancel();
                    System.out.println("Timer cancelled after 5 executions.");
                }
            }
        };

        // Start after 1 second, repeat every 2 seconds (fixed-delay)
        timer.schedule(task, 1000, 2000);
        System.out.println("Fixed-delay task scheduled.");
    }
}
// With fixed-delay: if execution #2 takes 3 seconds (longer than period),
// execution #3 will happen 2 seconds AFTER #2 finishes (not 2 seconds after #2 started)
```

### 1.4 Fixed-Delay from Specific Date

```java
import java.util.Timer;
import java.util.TimerTask;
import java.util.Date;

public class FixedDelayFromDateExample {
    public static void main(String[] args) {
        Timer timer = new Timer();
        final int[] count = {0};

        TimerTask task = new TimerTask() {
            @Override
            public void run() {
                count[0]++;
                System.out.println("Tick #" + count[0] + " at " + new Date());
                if (count[0] >= 3) timer.cancel();
            }
        };

        Date startTime = new Date(); // start immediately
        timer.schedule(task, startTime, 1000); // every 1 second, fixed-delay
    }
}
```

### 1.5 Fixed-Rate Repeated Execution

**Fixed-rate**: Each execution is scheduled relative to the **scheduled** execution time of the initial execution. Tries to maintain a consistent rate, "catching up" if delayed.

```java
import java.util.Timer;
import java.util.TimerTask;

public class FixedRateExample {
    public static void main(String[] args) {
        Timer timer = new Timer();
        final long startTime = System.currentTimeMillis();
        final int[] count = {0};

        TimerTask task = new TimerTask() {
            @Override
            public void run() {
                count[0]++;
                long elapsed = System.currentTimeMillis() - startTime;
                System.out.println("Execution #" + count[0] +
                    " elapsed: " + elapsed + "ms");

                // Simulate slow execution on #2
                if (count[0] == 2) {
                    try { Thread.sleep(3000); } catch (InterruptedException e) {}
                }

                if (count[0] >= 6) {
                    timer.cancel();
                }
            }
        };

        // Fixed-rate: every 1 second
        timer.scheduleAtFixedRate(task, 0, 1000);
    }
}
// With fixed-rate: after #2 takes 3 seconds, #3, #4, #5 fire rapidly to "catch up"
// Then resumes normal 1-second interval
```

### 1.6 Fixed-Delay vs Fixed-Rate — Key Difference

| Aspect | Fixed-Delay (`schedule`) | Fixed-Rate (`scheduleAtFixedRate`) |
|--------|--------------------------|-------------------------------------|
| Next execution | period after **previous finishes** | period after **previous was supposed to start** |
| When delayed | Subsequent executions shift | Tries to catch up (rapid-fire) |
| Use case | Smoothness matters (animations) | Accuracy over time (clock, heartbeat) |
| Drift | Accumulates drift | Corrects drift |

```java
// VISUAL EXAMPLE:
// Period = 2 sec, task #2 takes 5 seconds

// Fixed-Delay:
// t=0: #1 start (1s work)
// t=3: #2 start (5s work) -- 2s after #1 finished
// t=10: #3 start           -- 2s after #2 finished
// Total drift accumulates

// Fixed-Rate:
// t=0: #1 start (1s work)
// t=2: #2 start (5s work)  -- scheduled at t=2
// t=7: #3 fires immediately -- was scheduled at t=4, catching up
// t=7: #4 fires immediately -- was scheduled at t=6, catching up
// t=8: #5 fires at t=8     -- back on track
```

### 1.7 Timer.cancel() and Timer.purge()

```java
import java.util.Timer;
import java.util.TimerTask;

public class TimerCancelPurgeExample {
    public static void main(String[] args) throws InterruptedException {
        Timer timer = new Timer();

        TimerTask task1 = new TimerTask() {
            @Override
            public void run() { System.out.println("Task 1"); }
        };

        TimerTask task2 = new TimerTask() {
            @Override
            public void run() { System.out.println("Task 2"); }
        };

        timer.schedule(task1, 1000, 1000);
        timer.schedule(task2, 2000, 2000);

        Thread.sleep(5000);

        // Cancel individual task (not the timer)
        task1.cancel(); // task1 won't execute anymore, task2 continues

        // purge() removes cancelled tasks from the timer's internal queue
        // Returns number of tasks removed
        int removed = timer.purge();
        System.out.println("Purged " + removed + " cancelled tasks");

        Thread.sleep(3000);

        // Cancel the entire timer — terminates the timer thread
        // No more tasks can be scheduled on this timer
        timer.cancel();
        System.out.println("Timer cancelled");

        // This will throw IllegalStateException
        try {
            timer.schedule(new TimerTask() {
                @Override
                public void run() {}
            }, 1000);
        } catch (IllegalStateException e) {
            System.out.println("Cannot schedule on cancelled timer: " + e.getMessage());
        }
    }
}
```

### 1.8 TimerTask.scheduledExecutionTime()

```java
import java.util.Timer;
import java.util.TimerTask;
import java.util.Date;

public class ScheduledExecutionTimeExample {
    public static void main(String[] args) throws InterruptedException {
        Timer timer = new Timer();

        TimerTask task = new TimerTask() {
            @Override
            public void run() {
                long scheduled = scheduledExecutionTime();
                long actual = System.currentTimeMillis();
                long drift = actual - scheduled;
                System.out.println("Scheduled: " + new Date(scheduled));
                System.out.println("Actual:    " + new Date(actual));
                System.out.println("Drift:     " + drift + "ms");
                System.out.println("---");
            }
        };

        timer.scheduleAtFixedRate(task, 0, 1000);
        Thread.sleep(5500);
        timer.cancel();
    }
}
```

### 1.9 Daemon Timer

```java
import java.util.Timer;
import java.util.TimerTask;

public class DaemonTimerExample {
    public static void main(String[] args) {
        // Daemon timer: won't prevent JVM shutdown
        Timer daemonTimer = new Timer(true); // isDaemon = true

        // Non-daemon timer: keeps JVM alive until cancel() is called
        // Timer normalTimer = new Timer(); // or Timer(false)

        TimerTask task = new TimerTask() {
            @Override
            public void run() {
                System.out.println("Daemon timer task running...");
            }
        };

        daemonTimer.schedule(task, 0, 500);
        System.out.println("Main thread ending. Daemon timer will stop with JVM.");
        // JVM exits because main thread is done and timer is daemon
        // If timer were non-daemon, JVM would keep running
    }
}
```

### 1.10 Named Timer Thread

```java
import java.util.Timer;
import java.util.TimerTask;

public class NamedTimerExample {
    public static void main(String[] args) throws InterruptedException {
        // Named timer thread for debugging
        Timer timer = new Timer("MyScheduler-Thread");

        timer.schedule(new TimerTask() {
            @Override
            public void run() {
                System.out.println("Running on: " + Thread.currentThread().getName());
                // Output: Running on: MyScheduler-Thread
            }
        }, 100);

        Thread.sleep(500);
        timer.cancel();
    }
}
```

### 1.11 Limitations of Timer

```java
// PROBLEM 1: Single thread — one slow task delays all others
Timer timer = new Timer();
timer.schedule(slowTask, 0, 1000);    // takes 5 seconds
timer.schedule(quickTask, 0, 1000);   // delayed by slowTask!

// PROBLEM 2: No error recovery — exception kills the timer thread
Timer timer2 = new Timer();
timer2.schedule(new TimerTask() {
    @Override
    public void run() {
        throw new RuntimeException("Oops!"); // kills ALL scheduled tasks
    }
}, 1000);
timer2.schedule(anotherTask, 2000); // will NEVER execute

// PROBLEM 3: Based on system clock (Date) — affected by clock changes
// If system clock moves backward, fixed-delay tasks may pause for a long time
```

### 1.12 Migration to ScheduledExecutorService (Modern Replacement)

```java
import java.util.concurrent.*;

public class TimerToExecutorMigration {
    public static void main(String[] args) throws InterruptedException {

        // === OLD WAY: Timer ===
        // Timer timer = new Timer();
        // timer.schedule(task, 2000);                    // one-time delay
        // timer.schedule(task, 1000, 2000);              // fixed-delay
        // timer.scheduleAtFixedRate(task, 1000, 2000);   // fixed-rate

        // === NEW WAY: ScheduledExecutorService ===
        ScheduledExecutorService executor = Executors.newScheduledThreadPool(2);

        // One-time execution after delay
        executor.schedule(() -> {
            System.out.println("One-time task after 2 seconds");
        }, 2, TimeUnit.SECONDS);

        // Fixed-delay repeated execution
        ScheduledFuture<?> fixedDelay = executor.scheduleWithFixedDelay(() -> {
            System.out.println("Fixed-delay: " + System.currentTimeMillis());
        }, 1, 2, TimeUnit.SECONDS);

        // Fixed-rate repeated execution
        ScheduledFuture<?> fixedRate = executor.scheduleAtFixedRate(() -> {
            System.out.println("Fixed-rate: " + System.currentTimeMillis());
        }, 1, 2, TimeUnit.SECONDS);

        Thread.sleep(10000);

        // Cancel individual tasks (like TimerTask.cancel())
        fixedDelay.cancel(false);
        fixedRate.cancel(false);

        // Graceful shutdown (like timer.cancel() but better)
        executor.shutdown();
        executor.awaitTermination(5, TimeUnit.SECONDS);
        System.out.println("Executor shut down.");
    }
}
```

**Advantages of ScheduledExecutorService over Timer:**

| Timer | ScheduledExecutorService |
|-------|--------------------------|
| Single thread | Thread pool (configurable) |
| Exception kills all tasks | Exception only affects that task |
| Uses `Date` (clock-sensitive) | Uses `TimeUnit` (monotonic) |
| No return value | Returns `ScheduledFuture` |
| No shutdown hooks | Supports graceful shutdown |

---
## 2. Fail-Fast vs Fail-Safe Iterators

### 3.1 Fail-Fast Iterators

Fail-fast iterators throw `ConcurrentModificationException` if the collection is structurally modified during iteration (except through the iterator's own methods).

**How it works:** Collections maintain an internal `modCount`. The iterator saves `expectedModCount` at creation. On every `next()`, it checks `modCount == expectedModCount`.

```java
import java.util.*;

public class FailFastExample {
    public static void main(String[] args) {

        // === ArrayList: FAIL-FAST ===
        List<String> list = new ArrayList<>(List.of("A", "B", "C", "D", "E"));

        try {
            for (String item : list) {
                System.out.println("Processing: " + item);
                if (item.equals("C")) {
                    list.remove(item); // structural modification during iteration!
                }
            }
        } catch (ConcurrentModificationException e) {
            System.out.println("ConcurrentModificationException caught!");
            System.out.println("Cannot modify ArrayList during iteration.");
        }

        System.out.println("\n--- HashMap: FAIL-FAST ---");

        // === HashMap: FAIL-FAST ===
        Map<String, Integer> map = new HashMap<>();
        map.put("one", 1);
        map.put("two", 2);
        map.put("three", 3);

        try {
            for (Map.Entry<String, Integer> entry : map.entrySet()) {
                System.out.println("Entry: " + entry);
                if (entry.getKey().equals("two")) {
                    map.put("four", 4); // structural modification!
                }
            }
        } catch (ConcurrentModificationException e) {
            System.out.println("ConcurrentModificationException on HashMap!");
        }
    }
}
```

### 3.2 Fail-Safe Iterators

Fail-safe iterators work on a copy/snapshot of the collection, so modifications during iteration don't cause exceptions. They may not reflect changes made after the iterator was created.

```java
import java.util.concurrent.*;
import java.util.*;

public class FailSafeExample {
    public static void main(String[] args) {

        // === CopyOnWriteArrayList: FAIL-SAFE ===
        CopyOnWriteArrayList<String> cowList = new CopyOnWriteArrayList<>(
            List.of("A", "B", "C", "D", "E")
        );

        System.out.println("--- CopyOnWriteArrayList ---");
        for (String item : cowList) {
            System.out.println("Processing: " + item);
            if (item.equals("C")) {
                cowList.add("F");      // No exception! Iterator uses snapshot
                cowList.remove("D");   // No exception!
            }
        }
        System.out.println("After iteration: " + cowList);
        // Iterator saw: A, B, C, D, E (original snapshot)
        // Final list: [A, B, C, E, F]

        System.out.println("\n--- ConcurrentHashMap ---");

        // === ConcurrentHashMap: WEAKLY CONSISTENT (fail-safe) ===
        ConcurrentHashMap<String, Integer> concMap = new ConcurrentHashMap<>();
        concMap.put("one", 1);
        concMap.put("two", 2);
        concMap.put("three", 3);

        for (Map.Entry<String, Integer> entry : concMap.entrySet()) {
            System.out.println("Entry: " + entry);
            if (entry.getKey().equals("two")) {
                concMap.put("four", 4);    // No exception!
                concMap.remove("three");   // No exception!
            }
        }
        System.out.println("After iteration: " + concMap);
        // May or may not see "four" during iteration — weakly consistent
    }
}
```

### 3.3 Safe Ways to Modify During Iteration

```java
import java.util.*;
import java.util.concurrent.CopyOnWriteArrayList;

public class SafeModificationDuringIteration {
    public static void main(String[] args) {

        // === METHOD 1: Iterator.remove() ===
        System.out.println("--- Iterator.remove() ---");
        List<Integer> list1 = new ArrayList<>(List.of(1, 2, 3, 4, 5, 6));
        Iterator<Integer> it = list1.iterator();
        while (it.hasNext()) {
            int val = it.next();
            if (val % 2 == 0) {
                it.remove(); // SAFE — iterator's own method
            }
        }
        System.out.println(list1); // [1, 3, 5]

        // === METHOD 2: Collect and removeAll ===
        System.out.println("\n--- Collect and removeAll ---");
        List<String> list2 = new ArrayList<>(List.of("apple", "banana", "cherry", "date"));
        List<String> toRemove = new ArrayList<>();
        for (String s : list2) {
            if (s.length() > 5) {
                toRemove.add(s);
            }
        }
        list2.removeAll(toRemove);
        System.out.println(list2); // [apple, date]

        // === METHOD 3: removeIf (Java 8+) — cleanest approach ===
        System.out.println("\n--- removeIf ---");
        List<Integer> list3 = new ArrayList<>(List.of(10, 15, 20, 25, 30));
        list3.removeIf(n -> n > 20);
        System.out.println(list3); // [10, 15, 20]

        // === METHOD 4: Use ConcurrentHashMap for maps ===
        System.out.println("\n--- ConcurrentHashMap ---");
        Map<String, Integer> map = new java.util.concurrent.ConcurrentHashMap<>();
        map.put("a", 1);
        map.put("b", 2);
        map.put("c", 3);
        for (Map.Entry<String, Integer> entry : map.entrySet()) {
            if (entry.getValue() < 3) {
                map.remove(entry.getKey()); // safe with ConcurrentHashMap
            }
        }
        System.out.println(map); // {c=3}

        // === METHOD 5: ListIterator for add/set during iteration ===
        System.out.println("\n--- ListIterator ---");
        List<String> list4 = new ArrayList<>(List.of("X", "Y", "Z"));
        ListIterator<String> lit = list4.listIterator();
        while (lit.hasNext()) {
            String s = lit.next();
            if (s.equals("Y")) {
                lit.set("Y-modified"); // replace current
                lit.add("Y2");         // insert after current
            }
        }
        System.out.println(list4); // [X, Y-modified, Y2, Z]
    }
}
```

### 3.4 Summary Table

| Collection | Iterator Type | Behavior on Modification |
|-----------|---------------|-------------------------|
| ArrayList | Fail-Fast | ConcurrentModificationException |
| LinkedList | Fail-Fast | ConcurrentModificationException |
| HashMap | Fail-Fast | ConcurrentModificationException |
| HashSet | Fail-Fast | ConcurrentModificationException |
| TreeMap | Fail-Fast | ConcurrentModificationException |
| CopyOnWriteArrayList | Fail-Safe | Iterates over snapshot |
| CopyOnWriteArraySet | Fail-Safe | Iterates over snapshot |
| ConcurrentHashMap | Weakly Consistent | May reflect some changes |
| ConcurrentSkipListMap | Weakly Consistent | May reflect some changes |

---

## 3. Collections Utility Class (java.util.Collections)

All methods are `static`. The class cannot be instantiated.

### 4.1 Sorting and Ordering

```java
import java.util.*;

public class CollectionsSortingExample {
    public static void main(String[] args) {

        // === sort() — natural ordering or with Comparator ===
        List<Integer> numbers = new ArrayList<>(List.of(5, 2, 8, 1, 9, 3));
        Collections.sort(numbers);
        System.out.println("Sorted: " + numbers); // [1, 2, 3, 5, 8, 9]

        Collections.sort(numbers, Comparator.reverseOrder());
        System.out.println("Reverse sorted: " + numbers); // [9, 8, 5, 3, 2, 1]

        List<String> names = new ArrayList<>(List.of("Charlie", "Alice", "Bob"));
        Collections.sort(names, String.CASE_INSENSITIVE_ORDER);
        System.out.println("Case-insensitive: " + names); // [Alice, Bob, Charlie]

        // === reverse() — reverses element order ===
        List<String> letters = new ArrayList<>(List.of("A", "B", "C", "D"));
        Collections.reverse(letters);
        System.out.println("Reversed: " + letters); // [D, C, B, A]

        // === shuffle() — random permutation ===
        List<Integer> deck = new ArrayList<>(List.of(1, 2, 3, 4, 5, 6, 7, 8, 9, 10));
        Collections.shuffle(deck);
        System.out.println("Shuffled: " + deck); // random order

        Collections.shuffle(deck, new Random(42)); // reproducible shuffle with seed
        System.out.println("Seeded shuffle: " + deck);

        // === swap() — swap two elements ===
        List<String> items = new ArrayList<>(List.of("X", "Y", "Z"));
        Collections.swap(items, 0, 2);
        System.out.println("Swapped: " + items); // [Z, Y, X]

        // === rotate() — rotates elements by distance ===
        List<Integer> rotList = new ArrayList<>(List.of(1, 2, 3, 4, 5));
        Collections.rotate(rotList, 2); // positive = rotate right
        System.out.println("Rotated right 2: " + rotList); // [4, 5, 1, 2, 3]

        Collections.rotate(rotList, -1); // negative = rotate left
        System.out.println("Rotated left 1: " + rotList); // [5, 1, 2, 3, 4]
    }
}
```

### 4.2 Searching

```java
import java.util.*;

public class CollectionsSearchingExample {
    public static void main(String[] args) {

        // === binarySearch() — list MUST be sorted first ===
        List<Integer> sorted = new ArrayList<>(List.of(2, 5, 8, 12, 16, 23, 38, 56, 72, 91));
        int index = Collections.binarySearch(sorted, 23);
        System.out.println("Found 23 at index: " + index); // 5

        int notFound = Collections.binarySearch(sorted, 10);
        System.out.println("10 not found, insertion point: " + notFound);
        // Returns -(insertion point) - 1 = -(3) - 1 = -4

        // With custom comparator
        List<String> words = new ArrayList<>(List.of("apple", "banana", "cherry", "date"));
        int idx = Collections.binarySearch(words, "cherry", Comparator.naturalOrder());
        System.out.println("cherry at: " + idx); // 2

        // === frequency() — count occurrences ===
        List<String> fruits = List.of("apple", "banana", "apple", "cherry", "apple");
        int freq = Collections.frequency(fruits, "apple");
        System.out.println("apple appears: " + freq + " times"); // 3

        // === disjoint() — true if collections have NO elements in common ===
        List<Integer> a = List.of(1, 2, 3);
        List<Integer> b = List.of(4, 5, 6);
        List<Integer> c = List.of(3, 4, 5);
        System.out.println("a & b disjoint: " + Collections.disjoint(a, b)); // true
        System.out.println("a & c disjoint: " + Collections.disjoint(a, c)); // false
    }
}
```

### 4.3 Min and Max

```java
import java.util.*;

public class CollectionsMinMaxExample {
    public static void main(String[] args) {

        List<Integer> numbers = List.of(42, 7, 99, 3, 56);

        // Natural ordering
        System.out.println("Min: " + Collections.min(numbers)); // 3
        System.out.println("Max: " + Collections.max(numbers)); // 99

        // With comparator
        List<String> words = List.of("elephant", "cat", "hippopotamus", "ant");
        String shortest = Collections.min(words, Comparator.comparingInt(String::length));
        String longest = Collections.max(words, Comparator.comparingInt(String::length));
        System.out.println("Shortest: " + shortest); // ant
        System.out.println("Longest: " + longest);   // hippopotamus
    }
}
```

### 4.4 Synchronization Wrappers

```java
import java.util.*;

public class CollectionsSynchronizedExample {
    public static void main(String[] args) {

        // === synchronizedList() ===
        List<String> syncList = Collections.synchronizedList(new ArrayList<>());
        syncList.add("A");
        syncList.add("B");

        // IMPORTANT: Must manually synchronize during iteration!
        synchronized (syncList) {
            for (String item : syncList) {
                System.out.println(item);
            }
        }

        // === synchronizedMap() ===
        Map<String, Integer> syncMap = Collections.synchronizedMap(new HashMap<>());
        syncMap.put("key1", 1);
        syncMap.put("key2", 2);

        synchronized (syncMap) {
            for (Map.Entry<String, Integer> entry : syncMap.entrySet()) {
                System.out.println(entry.getKey() + "=" + entry.getValue());
            }
        }

        // === synchronizedSet() ===
        Set<String> syncSet = Collections.synchronizedSet(new HashSet<>());
        syncSet.add("X");
        syncSet.add("Y");

        // NOTE: For better concurrent performance, prefer:
        // ConcurrentHashMap instead of synchronizedMap
        // CopyOnWriteArrayList instead of synchronizedList
    }
}
```

### 4.5 Unmodifiable Wrappers

```java
import java.util.*;

public class CollectionsUnmodifiableExample {
    public static void main(String[] args) {

        // === unmodifiableList() ===
        List<String> original = new ArrayList<>(List.of("A", "B", "C"));
        List<String> unmodList = Collections.unmodifiableList(original);
        // unmodList.add("D");  // throws UnsupportedOperationException
        original.add("D");      // THIS STILL WORKS — it's just a view!
        System.out.println(unmodList); // [A, B, C, D] — reflects original change

        // === unmodifiableMap() ===
        Map<String, Integer> origMap = new HashMap<>();
        origMap.put("a", 1);
        origMap.put("b", 2);
        Map<String, Integer> unmodMap = Collections.unmodifiableMap(origMap);
        // unmodMap.put("c", 3);  // UnsupportedOperationException

        // === unmodifiableSet() ===
        Set<Integer> origSet = new HashSet<>(Set.of(1, 2, 3));
        Set<Integer> unmodSet = Collections.unmodifiableSet(origSet);
        // unmodSet.add(4);  // UnsupportedOperationException

        // === For truly immutable collections (Java 9+), use: ===
        List<String> immutable = List.of("X", "Y", "Z");
        Map<String, Integer> immutableMap = Map.of("a", 1, "b", 2);
        Set<Integer> immutableSet = Set.of(10, 20, 30);
        // These have no backing collection that can be modified
    }
}
```

### 4.6 Singleton and Empty Collections

```java
import java.util.*;

public class CollectionsSingletonEmptyExample {
    public static void main(String[] args) {

        // === Singleton collections (immutable, single element) ===
        List<String> singleList = Collections.singletonList("only-one");
        Set<Integer> singleSet = Collections.singleton(42);
        Map<String, String> singleMap = Collections.singletonMap("key", "value");

        System.out.println(singleList); // [only-one]
        System.out.println(singleSet);  // [42]
        System.out.println(singleMap);  // {key=value}

        // singleList.add("another"); // UnsupportedOperationException
        // Useful for APIs that expect a collection but you have one element

        // === Empty collections (immutable, zero elements) ===
        List<String> emptyList = Collections.emptyList();
        Map<String, Integer> emptyMap = Collections.emptyMap();
        Set<Double> emptySet = Collections.emptySet();
        Iterator<String> emptyIter = Collections.emptyIterator();

        System.out.println(emptyList.size()); // 0
        // emptyList.add("x"); // UnsupportedOperationException

        // Useful for returning "no results" without null
        // Better than: return null; or return new ArrayList<>(); (avoids allocation)
    }
}
```

### 4.7 Type-Safe (Checked) Wrappers

```java
import java.util.*;

public class CollectionsCheckedExample {
    public static void main(String[] args) {

        // Checked wrappers enforce type safety at runtime (defeats raw type abuse)
        List<String> checkedList = Collections.checkedList(new ArrayList<>(), String.class);
        checkedList.add("Hello");
        checkedList.add("World");

        // Without checked wrapper, raw type abuse is possible:
        // List rawList = checkedList;
        // rawList.add(123);  // With checkedList: throws ClassCastException at add time!
        //                    // Without checked: fails later with confusing ClassCastException

        Map<String, Integer> checkedMap = Collections.checkedMap(
            new HashMap<>(), String.class, Integer.class
        );
        checkedMap.put("age", 25);
        // checkedMap.put("age", "twenty-five"); // ClassCastException immediately

        Set<Integer> checkedSet = Collections.checkedSet(new HashSet<>(), Integer.class);
        checkedSet.add(1);
        checkedSet.add(2);
    }
}
```

### 4.8 Fill, Copy, nCopies, replaceAll

```java
import java.util.*;

public class CollectionsFillCopyExample {
    public static void main(String[] args) {

        // === fill() — replaces all elements with specified value ===
        List<String> list = new ArrayList<>(List.of("A", "B", "C", "D"));
        Collections.fill(list, "X");
        System.out.println("Filled: " + list); // [X, X, X, X]

        // === copy() — copies src into dest (dest must be >= src size) ===
        List<String> src = List.of("1", "2", "3");
        List<String> dest = new ArrayList<>(List.of("A", "B", "C", "D", "E"));
        Collections.copy(dest, src);
        System.out.println("After copy: " + dest); // [1, 2, 3, D, E]
        // Only first 3 elements overwritten

        // === nCopies() — returns immutable list of n copies ===
        List<String> copies = Collections.nCopies(5, "Hello");
        System.out.println("nCopies: " + copies); // [Hello, Hello, Hello, Hello, Hello]
        // copies.set(0, "World"); // UnsupportedOperationException — immutable!

        // Useful for initializing a list:
        List<Integer> zeros = new ArrayList<>(Collections.nCopies(10, 0));
        System.out.println("Zeros: " + zeros); // [0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
        zeros.set(5, 99); // this works because we wrapped in new ArrayList

        // === replaceAll() — replaces all occurrences of one value with another ===
        List<String> colors = new ArrayList<>(List.of("red", "blue", "red", "green", "red"));
        boolean changed = Collections.replaceAll(colors, "red", "orange");
        System.out.println("Replaced: " + colors); // [orange, blue, orange, green, orange]
        System.out.println("Changed: " + changed); // true
    }
}
```

### 4.9 Enumeration Conversion

```java
import java.util.*;

public class CollectionsEnumerationExample {
    public static void main(String[] args) {

        // === list(Enumeration) — converts Enumeration to ArrayList ===
        // Useful when dealing with legacy APIs that return Enumeration
        Vector<String> vector = new Vector<>(List.of("old", "legacy", "code"));
        Enumeration<String> enumeration = vector.elements();

        // Convert to modern ArrayList
        List<String> modernList = Collections.list(enumeration);
        System.out.println("Converted: " + modernList); // [old, legacy, code]

        // === enumeration() — converts Collection to Enumeration ===
        List<String> modern = List.of("new", "modern", "code");
        Enumeration<String> legacyEnum = Collections.enumeration(modern);
        while (legacyEnum.hasMoreElements()) {
            System.out.println(legacyEnum.nextElement());
        }
    }
}
```

---

## 4. Iterable and Iterator Pattern

### 5.1 Iterable<T> Interface

```java
// java.lang.Iterable<T>
public interface Iterable<T> {
    Iterator<T> iterator();                          // required
    default void forEach(Consumer<? super T> action) {} // Java 8
    default Spliterator<T> spliterator() {}           // Java 8
}

// Any class implementing Iterable can be used in enhanced for-loop:
// for (T item : myIterableInstance) { ... }
```

### 5.2 Iterator<T> Interface

```java
// java.util.Iterator<T>
public interface Iterator<T> {
    boolean hasNext();
    T next();
    default void remove() { throw new UnsupportedOperationException(); }
    default void forEachRemaining(Consumer<? super T> action) {} // Java 8
}
```

### 5.3 Basic Iterator Usage

```java
import java.util.*;

public class IteratorBasicsExample {
    public static void main(String[] args) {

        List<String> names = new ArrayList<>(List.of("Alice", "Bob", "Charlie", "David"));

        // === Manual iteration ===
        Iterator<String> it = names.iterator();
        while (it.hasNext()) {
            String name = it.next();
            System.out.println(name);
            if (name.equals("Bob")) {
                it.remove(); // safe removal during iteration
            }
        }
        System.out.println("After removal: " + names); // [Alice, Charlie, David]

        // === forEachRemaining (Java 8) ===
        Iterator<String> it2 = names.iterator();
        it2.next(); // skip first
        it2.forEachRemaining(n -> System.out.println("Remaining: " + n));
        // Remaining: Charlie
        // Remaining: David
    }
}
```

### 5.4 ListIterator<T> — Bidirectional

```java
import java.util.*;

public class ListIteratorExample {
    public static void main(String[] args) {

        List<String> list = new ArrayList<>(List.of("A", "B", "C", "D", "E"));

        // ListIterator can go forward AND backward
        ListIterator<String> lit = list.listIterator();

        // Forward traversal
        System.out.println("--- Forward ---");
        while (lit.hasNext()) {
            int idx = lit.nextIndex(); // index of element that next() will return
            String val = lit.next();
            System.out.println("Index " + idx + ": " + val);
        }

        // Backward traversal (cursor is now at end)
        System.out.println("\n--- Backward ---");
        while (lit.hasPrevious()) {
            int idx = lit.previousIndex(); // index of element that previous() will return
            String val = lit.previous();
            System.out.println("Index " + idx + ": " + val);
        }

        // === set() — replaces last element returned by next()/previous() ===
        System.out.println("\n--- set() ---");
        ListIterator<String> lit2 = list.listIterator();
        while (lit2.hasNext()) {
            String s = lit2.next();
            if (s.equals("C")) {
                lit2.set("C-MODIFIED"); // replace "C" with "C-MODIFIED"
            }
        }
        System.out.println(list); // [A, B, C-MODIFIED, D, E]

        // === add() — inserts element before the element that next() would return ===
        System.out.println("\n--- add() ---");
        ListIterator<String> lit3 = list.listIterator(2); // start at index 2
        lit3.add("INSERTED");
        System.out.println(list); // [A, B, INSERTED, C-MODIFIED, D, E]

        // === Start from specific index ===
        ListIterator<String> fromMiddle = list.listIterator(3); // starts at index 3
        System.out.println("\nFrom index 3: " + fromMiddle.next()); // C-MODIFIED
    }
}
```

### 5.5 Spliterator<T> — Parallel Iteration

```java
import java.util.*;
import java.util.stream.*;

public class SpliteratorExample {
    public static void main(String[] args) {

        List<String> items = List.of("alpha", "beta", "gamma", "delta", "epsilon",
                                     "zeta", "eta", "theta", "iota", "kappa");

        Spliterator<String> spliterator = items.spliterator();

        // === Characteristics ===
        System.out.println("Estimated size: " + spliterator.estimateSize()); // 10
        System.out.println("Has ORDERED: " +
            spliterator.hasCharacteristics(Spliterator.ORDERED));   // true
        System.out.println("Has SIZED: " +
            spliterator.hasCharacteristics(Spliterator.SIZED));     // true

        // === trySplit() — splits for parallel processing ===
        Spliterator<String> firstHalf = spliterator.trySplit();
        // spliterator now has second half, firstHalf has first half

        System.out.println("\nFirst half:");
        firstHalf.forEachRemaining(s -> System.out.println("  " + s));

        System.out.println("\nSecond half:");
        spliterator.forEachRemaining(s -> System.out.println("  " + s));

        // === tryAdvance() — process one element ===
        Spliterator<String> sp = items.spliterator();
        sp.tryAdvance(s -> System.out.println("\nFirst: " + s)); // alpha
        sp.tryAdvance(s -> System.out.println("Second: " + s));  // beta

        // === Used internally by parallel streams ===
        long count = StreamSupport.stream(items.spliterator(), true) // parallel=true
            .filter(s -> s.length() > 4)
            .count();
        System.out.println("\nWords longer than 4 chars: " + count);
    }
}
```

### 5.6 Making a Custom Class Iterable

```java
import java.util.*;

public class NumberRange implements Iterable<Integer> {
    private final int start;
    private final int end; // exclusive

    public NumberRange(int start, int end) {
        if (start > end) throw new IllegalArgumentException("start must be <= end");
        this.start = start;
        this.end = end;
    }

    @Override
    public Iterator<Integer> iterator() {
        return new NumberRangeIterator();
    }

    // Inner class implementing Iterator
    private class NumberRangeIterator implements Iterator<Integer> {
        private int current = start;

        @Override
        public boolean hasNext() {
            return current < end;
        }

        @Override
        public Integer next() {
            if (!hasNext()) throw new NoSuchElementException();
            return current++;
        }

        // remove() not supported — uses default UnsupportedOperationException
    }

    public static void main(String[] args) {
        NumberRange range = new NumberRange(1, 6);

        // Works with enhanced for-loop because we implement Iterable
        System.out.println("For-each loop:");
        for (int n : range) {
            System.out.println("  " + n);
        }
        // 1, 2, 3, 4, 5

        // Works with forEach
        System.out.println("\nforEach:");
        range.forEach(n -> System.out.print(n + " "));
        System.out.println();

        // Can create stream via spliterator
        System.out.println("\nStream sum: " +
            java.util.stream.StreamSupport.stream(range.spliterator(), false)
                .mapToInt(Integer::intValue)
                .sum()); // 15
    }
}
```

### 5.7 Custom Iterable with Generic Type

```java
import java.util.*;

public class CircularBuffer<T> implements Iterable<T> {
    private final Object[] buffer;
    private int head = 0;
    private int size = 0;

    public CircularBuffer(int capacity) {
        buffer = new Object[capacity];
    }

    public void add(T item) {
        int index = (head + size) % buffer.length;
        if (size == buffer.length) {
            head = (head + 1) % buffer.length; // overwrite oldest
        } else {
            size++;
        }
        buffer[index] = item;
    }

    public int size() { return size; }

    @SuppressWarnings("unchecked")
    @Override
    public Iterator<T> iterator() {
        return new Iterator<T>() {
            private int index = 0;

            @Override
            public boolean hasNext() { return index < size; }

            @Override
            public T next() {
                if (!hasNext()) throw new NoSuchElementException();
                int actualIndex = (head + index) % buffer.length;
                index++;
                return (T) buffer[actualIndex];
            }
        };
    }

    public static void main(String[] args) {
        CircularBuffer<String> buf = new CircularBuffer<>(3);
        buf.add("A");
        buf.add("B");
        buf.add("C");
        buf.add("D"); // overwrites A
        buf.add("E"); // overwrites B

        for (String s : buf) {
            System.out.println(s); // C, D, E
        }
    }
}
```

### 5.8 Enhanced For-Loop Under the Hood

```java
// The compiler desugars enhanced for-loop to iterator:

// SOURCE CODE:
List<String> names = List.of("Alice", "Bob", "Charlie");
for (String name : names) {
    System.out.println(name);
}

// COMPILER GENERATES (approximately):
Iterator<String> $iter = names.iterator();
while ($iter.hasNext()) {
    String name = $iter.next();
    System.out.println(name);
}

// For arrays, it uses indexed access:
// SOURCE:
int[] arr = {1, 2, 3};
for (int x : arr) { System.out.println(x); }

// COMPILER GENERATES:
int[] $arr = arr;
for (int $i = 0; $i < $arr.length; $i++) {
    int x = $arr[$i];
    System.out.println(x);
}
```

---

## 5. java.util.Objects Utility Class

### 6.1 Objects.equals() — Null-Safe Equality

```java
import java.util.Objects;

public class ObjectsEqualsExample {
    public static void main(String[] args) {

        String a = "hello";
        String b = null;

        // Without Objects.equals() — need null check
        // b.equals(a);  // NullPointerException!
        // if (a != null && a.equals(b)) {...}  // verbose

        // With Objects.equals() — null-safe
        System.out.println(Objects.equals(a, b));    // false
        System.out.println(Objects.equals(b, a));    // false (no NPE!)
        System.out.println(Objects.equals(null, null)); // true
        System.out.println(Objects.equals("hi", "hi")); // true
    }
}
```

### 6.2 Objects.hash() — For hashCode Implementation

```java
import java.util.Objects;

public class ObjectsHashExample {

    static class Employee {
        private String name;
        private int age;
        private String department;

        Employee(String name, int age, String department) {
            this.name = name;
            this.age = age;
            this.department = department;
        }

        @Override
        public int hashCode() {
            // Convenient multi-field hashCode — handles nulls
            return Objects.hash(name, age, department);
        }

        @Override
        public boolean equals(Object o) {
            if (this == o) return true;
            if (!(o instanceof Employee)) return false;
            Employee e = (Employee) o;
            return age == e.age &&
                   Objects.equals(name, e.name) &&
                   Objects.equals(department, e.department);
        }
    }

    public static void main(String[] args) {
        Employee e1 = new Employee("Alice", 30, "Engineering");
        Employee e2 = new Employee("Alice", 30, "Engineering");
        System.out.println("Same hash: " + (e1.hashCode() == e2.hashCode())); // true
        System.out.println("Equals: " + e1.equals(e2)); // true
    }
}
```

### 6.3 Objects.requireNonNull() — Validation

```java
import java.util.Objects;

public class ObjectsRequireNonNullExample {
    public static void main(String[] args) {

        // === Basic — throws NullPointerException with no message ===
        String name = "Alice";
        String validated = Objects.requireNonNull(name);
        System.out.println(validated); // Alice

        // === With message — throws NPE with descriptive message ===
        try {
            String nullValue = null;
            Objects.requireNonNull(nullValue, "Name must not be null");
        } catch (NullPointerException e) {
            System.out.println("Caught: " + e.getMessage());
            // Caught: Name must not be null
        }

        // === With Supplier (lazy message for expensive message construction) ===
        try {
            String nullVal = null;
            Objects.requireNonNull(nullVal, () -> "Value at index " + 42 + " is null");
        } catch (NullPointerException e) {
            System.out.println("Caught: " + e.getMessage());
        }

        // === Common pattern: validate constructor parameters ===
        // public MyClass(String name, List<String> items) {
        //     this.name = Objects.requireNonNull(name, "name");
        //     this.items = Objects.requireNonNull(items, "items");
        // }
    }
}
```

### 6.4 Objects.toString() — Null-Safe toString

```java
import java.util.Objects;

public class ObjectsToStringExample {
    public static void main(String[] args) {

        Object obj = "Hello";
        Object nullObj = null;

        // toString(obj) — returns "null" string for null
        System.out.println(Objects.toString(obj));      // Hello
        System.out.println(Objects.toString(nullObj));   // "null" (the string)

        // toString(obj, defaultStr) — returns default for null
        System.out.println(Objects.toString(nullObj, "N/A"));  // N/A
        System.out.println(Objects.toString(nullObj, ""));     // (empty string)
        System.out.println(Objects.toString(obj, "N/A"));      // Hello
    }
}
```

### 6.5 Objects.compare()

```java
import java.util.Objects;
import java.util.Comparator;

public class ObjectsCompareExample {
    public static void main(String[] args) {

        // Objects.compare(a, b, comparator) — null-safe comparison
        String s1 = "apple";
        String s2 = "banana";

        int result = Objects.compare(s1, s2, Comparator.naturalOrder());
        System.out.println("apple vs banana: " + result); // negative (apple < banana)

        // If both are same reference, returns 0 without calling comparator
        System.out.println(Objects.compare(s1, s1, Comparator.naturalOrder())); // 0
    }
}
```

### 6.6 Objects.isNull() and Objects.nonNull()

```java
import java.util.Objects;
import java.util.List;
import java.util.stream.Collectors;

public class ObjectsNullChecksExample {
    public static void main(String[] args) {

        // Primarily useful as method references in streams
        List<String> items = List.of("A", "B");
        // Can't have nulls in List.of, so let's use Arrays.asList
        List<String> mixed = java.util.Arrays.asList("hello", null, "world", null, "java");

        // Filter out nulls using method reference
        List<String> nonNulls = mixed.stream()
            .filter(Objects::nonNull)
            .collect(Collectors.toList());
        System.out.println("Non-nulls: " + nonNulls); // [hello, world, java]

        // Find nulls
        long nullCount = mixed.stream()
            .filter(Objects::isNull)
            .count();
        System.out.println("Null count: " + nullCount); // 2

        // Direct usage (less common — just use == null)
        String s = null;
        System.out.println(Objects.isNull(s));    // true
        System.out.println(Objects.nonNull(s));   // false
    }
}
```

### 6.7 Objects.checkIndex() and checkFromToIndex() (Java 9+)

```java
import java.util.Objects;

public class ObjectsBoundsCheckExample {
    public static void main(String[] args) {

        int[] array = {10, 20, 30, 40, 50};

        // === checkIndex(index, length) — validates 0 <= index < length ===
        int validIndex = Objects.checkIndex(2, array.length);
        System.out.println("Valid index: " + validIndex); // 2

        try {
            Objects.checkIndex(5, array.length); // 5 >= 5, invalid!
        } catch (IndexOutOfBoundsException e) {
            System.out.println("checkIndex failed: " + e.getMessage());
        }

        try {
            Objects.checkIndex(-1, array.length);
        } catch (IndexOutOfBoundsException e) {
            System.out.println("Negative index: " + e.getMessage());
        }

        // === checkFromToIndex(fromIndex, toIndex, length) ===
        // Validates: 0 <= fromIndex <= toIndex <= length
        Objects.checkFromToIndex(1, 4, array.length); // valid: subarray [1,4)
        System.out.println("checkFromToIndex(1, 4, 5) passed");

        try {
            Objects.checkFromToIndex(3, 2, array.length); // from > to!
        } catch (IndexOutOfBoundsException e) {
            System.out.println("From > To: " + e.getMessage());
        }

        // === checkFromIndexSize(fromIndex, size, length) ===
        // Validates: 0 <= fromIndex, 0 <= size, fromIndex + size <= length
        Objects.checkFromIndexSize(2, 3, array.length); // valid: 3 elements from index 2
        System.out.println("checkFromIndexSize(2, 3, 5) passed");

        try {
            Objects.checkFromIndexSize(3, 3, array.length); // 3+3=6 > 5
        } catch (IndexOutOfBoundsException e) {
            System.out.println("Size overflow: " + e.getMessage());
        }
    }
}
```

---

## 6. java.util.Arrays Utility Class

### 7.1 Arrays.sort() and Arrays.parallelSort()

```java
import java.util.Arrays;
import java.util.Comparator;

public class ArraysSortExample {
    public static void main(String[] args) {

        // === sort() — uses dual-pivot Quicksort for primitives, TimSort for objects ===
        int[] nums = {5, 2, 8, 1, 9, 3, 7};
        Arrays.sort(nums);
        System.out.println("Sorted: " + Arrays.toString(nums)); // [1, 2, 3, 5, 7, 8, 9]

        // Sort a range
        int[] partial = {9, 7, 5, 3, 1, 8, 6};
        Arrays.sort(partial, 2, 5); // sort indices [2, 5) only
        System.out.println("Partial sort: " + Arrays.toString(partial)); // [9, 7, 1, 3, 5, 8, 6]

        // Sort objects with Comparator
        String[] words = {"banana", "apple", "cherry", "date"};
        Arrays.sort(words);
        System.out.println("Natural: " + Arrays.toString(words));

        Arrays.sort(words, Comparator.comparingInt(String::length));
        System.out.println("By length: " + Arrays.toString(words));

        Arrays.sort(words, Comparator.reverseOrder());
        System.out.println("Reverse: " + Arrays.toString(words));

        // === parallelSort() — uses Fork/Join pool, faster for large arrays ===
        int[] large = new int[1_000_000];
        for (int i = 0; i < large.length; i++) {
            large[i] = (int)(Math.random() * 1_000_000);
        }

        long start = System.nanoTime();
        Arrays.parallelSort(large); // uses multiple threads
        long elapsed = System.nanoTime() - start;
        System.out.println("parallelSort 1M elements: " + elapsed / 1_000_000 + "ms");
        // parallelSort is only faster for large arrays (> ~8192 elements)
    }
}
```

### 7.2 Arrays.binarySearch()

```java
import java.util.Arrays;

public class ArraysBinarySearchExample {
    public static void main(String[] args) {

        // Array MUST be sorted first!
        int[] sorted = {2, 5, 8, 12, 16, 23, 38, 56, 72, 91};

        int index = Arrays.binarySearch(sorted, 23);
        System.out.println("23 found at index: " + index); // 5

        int notFound = Arrays.binarySearch(sorted, 10);
        System.out.println("10 not found: " + notFound);
        // Returns -(insertion point) - 1
        // 10 would be inserted at index 3, so returns -4

        // Search within range
        int rangeResult = Arrays.binarySearch(sorted, 2, 7, 16); // search in [2, 7)
        System.out.println("16 in range [2,7): " + rangeResult); // 4

        // String array
        String[] names = {"Alice", "Bob", "Charlie", "David", "Eve"};
        int idx = Arrays.binarySearch(names, "Charlie");
        System.out.println("Charlie at: " + idx); // 2
    }
}
```

### 7.3 Arrays.fill()

```java
import java.util.Arrays;

public class ArraysFillExample {
    public static void main(String[] args) {

        // Fill entire array
        int[] arr = new int[5];
        Arrays.fill(arr, 42);
        System.out.println(Arrays.toString(arr)); // [42, 42, 42, 42, 42]

        // Fill a range [fromIndex, toIndex)
        int[] partial = new int[8];
        Arrays.fill(partial, 2, 6, 99);
        System.out.println(Arrays.toString(partial)); // [0, 0, 99, 99, 99, 99, 0, 0]

        // Works with all types
        String[] words = new String[3];
        Arrays.fill(words, "default");
        System.out.println(Arrays.toString(words)); // [default, default, default]

        boolean[] flags = new boolean[4];
        Arrays.fill(flags, true);
        System.out.println(Arrays.toString(flags)); // [true, true, true, true]
    }
}
```

### 7.4 Arrays.copyOf() and Arrays.copyOfRange()

```java
import java.util.Arrays;

public class ArraysCopyExample {
    public static void main(String[] args) {

        int[] original = {1, 2, 3, 4, 5};

        // === copyOf(array, newLength) ===
        // If newLength > original.length, pads with zeros (or null for objects)
        int[] copy = Arrays.copyOf(original, 5);
        System.out.println("Exact copy: " + Arrays.toString(copy)); // [1, 2, 3, 4, 5]

        int[] longer = Arrays.copyOf(original, 8);
        System.out.println("Extended: " + Arrays.toString(longer)); // [1, 2, 3, 4, 5, 0, 0, 0]

        int[] shorter = Arrays.copyOf(original, 3);
        System.out.println("Truncated: " + Arrays.toString(shorter)); // [1, 2, 3]

        // === copyOfRange(array, from, to) — [from, to) ===
        int[] range = Arrays.copyOfRange(original, 1, 4);
        System.out.println("Range [1,4): " + Arrays.toString(range)); // [2, 3, 4]

        // Can extend beyond array bounds (pads with zeros)
        int[] extended = Arrays.copyOfRange(original, 3, 8);
        System.out.println("Extended range: " + Arrays.toString(extended)); // [4, 5, 0, 0, 0]

        // Modifying copy doesn't affect original
        copy[0] = 999;
        System.out.println("Original unchanged: " + Arrays.toString(original)); // [1, 2, 3, 4, 5]
    }
}
```

### 7.5 Arrays.equals() and Arrays.deepEquals()

```java
import java.util.Arrays;

public class ArraysEqualsExample {
    public static void main(String[] args) {

        // === equals() — compares 1D arrays element by element ===
        int[] a = {1, 2, 3};
        int[] b = {1, 2, 3};
        int[] c = {1, 2, 4};

        System.out.println("a == b: " + (a == b));           // false (different references)
        System.out.println("Arrays.equals(a,b): " + Arrays.equals(a, b)); // true
        System.out.println("Arrays.equals(a,c): " + Arrays.equals(a, c)); // false

        // === deepEquals() — compares nested/multi-dimensional arrays ===
        int[][] matrix1 = {{1, 2}, {3, 4}};
        int[][] matrix2 = {{1, 2}, {3, 4}};
        int[][] matrix3 = {{1, 2}, {3, 5}};

        // equals() doesn't work for nested arrays (compares inner array references)
        System.out.println("equals (nested): " + Arrays.equals(matrix1, matrix2)); // false!

        // deepEquals() works correctly
        System.out.println("deepEquals: " + Arrays.deepEquals(matrix1, matrix2)); // true
        System.out.println("deepEquals: " + Arrays.deepEquals(matrix1, matrix3)); // false

        // Also works with Object arrays containing other arrays
        Object[] nested1 = {new int[]{1, 2}, "hello", new String[]{"a", "b"}};
        Object[] nested2 = {new int[]{1, 2}, "hello", new String[]{"a", "b"}};
        System.out.println("Deep nested: " + Arrays.deepEquals(nested1, nested2)); // true
    }
}
```

### 7.6 Arrays.toString() and Arrays.deepToString()

```java
import java.util.Arrays;

public class ArraysToStringExample {
    public static void main(String[] args) {

        // === toString() — 1D array to readable string ===
        int[] nums = {1, 2, 3, 4, 5};
        System.out.println(Arrays.toString(nums)); // [1, 2, 3, 4, 5]

        String[] words = {"hello", "world"};
        System.out.println(Arrays.toString(words)); // [hello, world]

        // Without Arrays.toString():
        System.out.println(nums); // [I@7852e922  (useless!)

        // === deepToString() — nested/multi-dimensional arrays ===
        int[][] matrix = {{1, 2, 3}, {4, 5, 6}, {7, 8, 9}};
        System.out.println(Arrays.toString(matrix));     // [[I@..., [I@..., [I@...]  (useless!)
        System.out.println(Arrays.deepToString(matrix)); // [[1, 2, 3], [4, 5, 6], [7, 8, 9]]

        // 3D array
        int[][][] cube = {{{1, 2}, {3, 4}}, {{5, 6}, {7, 8}}};
        System.out.println(Arrays.deepToString(cube));
        // [[[1, 2], [3, 4]], [[5, 6], [7, 8]]]
    }
}
```

### 7.7 Arrays.asList() — IMPORTANT GOTCHA

```java
import java.util.Arrays;
import java.util.List;
import java.util.ArrayList;

public class ArraysAsListExample {
    public static void main(String[] args) {

        // Arrays.asList() returns a FIXED-SIZE list BACKED BY the array!
        String[] array = {"A", "B", "C", "D"};
        List<String> list = Arrays.asList(array);

        System.out.println(list); // [A, B, C, D]
        System.out.println(list.getClass()); // java.util.Arrays$ArrayList (NOT java.util.ArrayList!)

        // === CAN: set/replace elements ===
        list.set(1, "X");
        System.out.println(list);           // [A, X, C, D]
        System.out.println(Arrays.toString(array)); // [A, X, C, D] — array modified too!

        // === CANNOT: add or remove (fixed size!) ===
        try {
            list.add("E"); // UnsupportedOperationException!
        } catch (UnsupportedOperationException e) {
            System.out.println("Cannot add: fixed-size list");
        }

        try {
            list.remove(0); // UnsupportedOperationException!
        } catch (UnsupportedOperationException e) {
            System.out.println("Cannot remove: fixed-size list");
        }

        // === Changes to array reflect in list (and vice versa) ===
        array[0] = "Z";
        System.out.println(list.get(0)); // Z — they share storage!

        // === To get a truly mutable ArrayList, wrap it: ===
        List<String> mutableList = new ArrayList<>(Arrays.asList("X", "Y", "Z"));
        mutableList.add("W");    // works!
        mutableList.remove(0);   // works!
        System.out.println(mutableList); // [Y, Z, W]

        // === GOTCHA with primitives ===
        int[] intArray = {1, 2, 3};
        // This creates a List<int[]> with ONE element (the array itself)!
        List<int[]> badList = Arrays.asList(intArray);
        System.out.println(badList.size()); // 1 (not 3!)

        // Use Integer[] instead:
        Integer[] intObjArray = {1, 2, 3};
        List<Integer> goodList = Arrays.asList(intObjArray);
        System.out.println(goodList.size()); // 3
    }
}
```

### 7.8 Arrays.stream() (Java 8)

```java
import java.util.Arrays;
import java.util.stream.*;

public class ArraysStreamExample {
    public static void main(String[] args) {

        int[] numbers = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10};

        // === Stream from entire array ===
        int sum = Arrays.stream(numbers).sum();
        System.out.println("Sum: " + sum); // 55

        double avg = Arrays.stream(numbers).average().orElse(0);
        System.out.println("Average: " + avg); // 5.5

        // === Stream from range [startInclusive, endExclusive) ===
        int partialSum = Arrays.stream(numbers, 2, 7).sum(); // indices 2,3,4,5,6
        System.out.println("Partial sum [2,7): " + partialSum); // 3+4+5+6+7 = 25

        // === Object arrays ===
        String[] words = {"hello", "world", "java", "streams"};
        String joined = Arrays.stream(words)
            .filter(w -> w.length() > 4)
            .map(String::toUpperCase)
            .collect(Collectors.joining(", "));
        System.out.println("Filtered: " + joined); // HELLO, WORLD, STREAMS

        // === Parallel stream from array ===
        long count = Arrays.stream(numbers)
            .parallel()
            .filter(n -> n % 2 == 0)
            .count();
        System.out.println("Even count: " + count); // 5
    }
}
```

### 7.9 Arrays.mismatch() (Java 9)

```java
import java.util.Arrays;

public class ArraysMismatchExample {
    public static void main(String[] args) {

        // mismatch() returns the index of the first difference between two arrays
        // Returns -1 if arrays are equal

        int[] a = {1, 2, 3, 4, 5};
        int[] b = {1, 2, 3, 7, 8};
        int[] c = {1, 2, 3, 4, 5};

        System.out.println("a vs b mismatch at: " + Arrays.mismatch(a, b)); // 3
        System.out.println("a vs c mismatch at: " + Arrays.mismatch(a, c)); // -1 (equal)

        // Different lengths
        int[] shorter = {1, 2, 3};
        System.out.println("a vs shorter: " + Arrays.mismatch(a, shorter)); // 3 (shorter ends)

        // With range: mismatch(a, aFromIndex, aToIndex, b, bFromIndex, bToIndex)
        int[] x = {0, 0, 1, 2, 3, 0, 0};
        int[] y = {1, 2, 4};
        int result = Arrays.mismatch(x, 2, 5, y, 0, 3); // compare x[2..5) with y[0..3)
        System.out.println("Range mismatch: " + result); // 2 (x[4]=3 vs y[2]=4)

        // String arrays
        String[] s1 = {"apple", "banana", "cherry"};
        String[] s2 = {"apple", "banana", "date"};
        System.out.println("String mismatch: " + Arrays.mismatch(s1, s2)); // 2
    }
}
```

### 7.10 Arrays.compare() (Java 9)

```java
import java.util.Arrays;

public class ArraysCompareExample {
    public static void main(String[] args) {

        // compare() — lexicographic comparison of arrays
        // Returns: negative if a < b, 0 if equal, positive if a > b

        int[] a = {1, 2, 3};
        int[] b = {1, 2, 4};
        int[] c = {1, 2, 3};
        int[] d = {1, 2, 3, 4}; // longer

        System.out.println("a vs b: " + Arrays.compare(a, b)); // negative (3 < 4)
        System.out.println("a vs c: " + Arrays.compare(a, c)); // 0 (equal)
        System.out.println("a vs d: " + Arrays.compare(a, d)); // negative (a is prefix of d, shorter)
        System.out.println("d vs a: " + Arrays.compare(d, a)); // positive

        // === compareUnsigned() — treats elements as unsigned ===
        int[] unsigned1 = {-1};  // as unsigned: 4294967295
        int[] unsigned2 = {1};
        System.out.println("compare: " + Arrays.compare(unsigned1, unsigned2));         // negative (-1 < 1)
        System.out.println("compareUnsigned: " + Arrays.compareUnsigned(unsigned1, unsigned2)); // positive

        // With range
        int[] x = {0, 1, 2, 3, 0};
        int[] y = {0, 1, 2, 4, 0};
        int result = Arrays.compare(x, 1, 4, y, 1, 4); // compare [1,4) ranges
        System.out.println("Range compare: " + result); // negative (3 < 4)
    }
}
```

### 7.11 Complete Example — Arrays in Practice

```java
import java.util.Arrays;
import java.util.Comparator;
import java.util.List;

public class ArraysComprehensiveExample {
    public static void main(String[] args) {

        System.out.println("=== Practical Array Operations ===\n");

        // 1. Create and fill
        int[] scores = new int[10];
        Arrays.fill(scores, -1); // initialize with sentinel value
        scores[0] = 95; scores[1] = 87; scores[2] = 92;
        scores[3] = 78; scores[4] = 88;
        System.out.println("Scores: " + Arrays.toString(scores));

        // 2. Copy only valid scores
        int[] validScores = Arrays.copyOf(scores, 5); // first 5
        System.out.println("Valid: " + Arrays.toString(validScores));

        // 3. Sort and find
        Arrays.sort(validScores);
        System.out.println("Sorted: " + Arrays.toString(validScores));

        int idx = Arrays.binarySearch(validScores, 92);
        System.out.println("92 is at index: " + idx);

        // 4. Statistics via stream
        System.out.println("Sum: " + Arrays.stream(validScores).sum());
        System.out.println("Max: " + Arrays.stream(validScores).max().orElse(0));
        System.out.println("Min: " + Arrays.stream(validScores).min().orElse(0));
        System.out.println("Avg: " + Arrays.stream(validScores).average().orElse(0));

        // 5. 2D array operations
        int[][] matrix = {
            {1, 2, 3},
            {4, 5, 6},
            {7, 8, 9}
        };
        System.out.println("\nMatrix: " + Arrays.deepToString(matrix));

        // 6. Sort array of objects
        String[] cities = {"New York", "London", "Tokyo", "Paris", "Sydney"};
        Arrays.sort(cities, Comparator.comparingInt(String::length));
        System.out.println("\nBy length: " + Arrays.toString(cities));

        // 7. Parallel operations on large arrays
        int[] bigArray = new int[100_000];
        Arrays.parallelSetAll(bigArray, i -> i * i); // set each element to i^2
        System.out.println("\nFirst 10 squares: " +
            Arrays.toString(Arrays.copyOf(bigArray, 10)));

        // parallelPrefix — cumulative operation
        int[] cumulative = {1, 2, 3, 4, 5};
        Arrays.parallelPrefix(cumulative, Integer::sum);
        System.out.println("Running sum: " + Arrays.toString(cumulative)); // [1, 3, 6, 10, 15]

        // 8. setAll (Java 8) — generator function
        double[] sinValues = new double[5];
        Arrays.setAll(sinValues, i -> Math.sin(i * Math.PI / 4));
        System.out.println("Sin values: " + Arrays.toString(sinValues));
    }
}
```

---

## Quick Reference Summary

| Class/Topic | Key Point |
|------------|-----------|
| `Timer` | Single-threaded scheduler, replaced by `ScheduledExecutorService` |
| `TimerTask` | Abstract class, override `run()` |
| `schedule()` | Fixed-delay: period after task finishes |
| `scheduleAtFixedRate()` | Fixed-rate: tries to maintain consistent interval |
| Immutable class | final class + private final fields + defensive copy |
| Defensive copy | Copy in constructor AND in getters for mutable fields |
| `List.of()` (Java 9+) | Truly immutable, no backing list |
| `Collections.unmodifiableList()` | View only, backing list can still change |
| Records | Shallow-immutable; use compact constructor for deep immutability |
| Fail-fast | `ConcurrentModificationException` on structural modification |
| Fail-safe | Snapshot/clone iteration, no exception |
| `removeIf()` | Cleanest way to remove during iteration (Java 8+) |
| `Collections` | Static utility methods for sort, search, wrap, fill |
| `Iterable<T>` | Enables for-each loop |
| `Iterator<T>` | hasNext/next/remove |
| `ListIterator<T>` | Bidirectional, supports set/add |
| `Spliterator<T>` | Parallel-capable iteration for streams |
| `Objects` | Null-safe equals, hash, requireNonNull, toString |
| `Arrays.asList()` | Fixed-size, backed by array — wrap in `new ArrayList<>()` for mutable |
| `Arrays.mismatch()` | First index where arrays differ (Java 9) |
| `Arrays.compare()` | Lexicographic array comparison (Java 9) |
| `Arrays.parallelSort()` | Multi-threaded sort for large arrays |
