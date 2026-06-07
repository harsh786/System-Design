# Java LLD Study Roadmap

## Goal

For LLD, Java is not just syntax. You need to know how to model objects, choose collections, control mutability, handle errors, and reason about concurrency. A strong LLD answer usually depends on these choices:

- Which objects own which data?
- Which relationships are inheritance, and which are composition?
- Which collection keeps the right order, uniqueness, or lookup speed?
- Which parts are mutable, immutable, thread-safe, or lazily computed?
- Which operations can fail, and how is failure represented?
- Which classes should be extensible, and which should be closed?

## Core Concept Map

```text
Java for LLD
|
+-- OOP
|   +-- class, object, constructor
|   +-- encapsulation, inheritance, abstraction, polymorphism
|   +-- interface, abstract class, composition
|   +-- static fields, static methods, static nested classes
|   +-- inner classes, local classes, anonymous classes
|
+-- Collections
|   +-- Iterable, Collection, List, Set, Queue, Deque
|   +-- Map, SortedMap, NavigableMap
|   +-- ArrayList, LinkedList, HashSet, LinkedHashSet, TreeSet
|   +-- HashMap, LinkedHashMap, TreeMap, ConcurrentHashMap
|   +-- ArrayDeque, PriorityQueue, BlockingQueue
|
+-- Generics And Functional Java
|   +-- type parameters, wildcards, bounds, type erasure
|   +-- lambda, method reference, functional interfaces
|   +-- Stream, Optional, Comparator
|
+-- Exceptions
|   +-- checked, unchecked, Error
|   +-- try/catch/finally, try-with-resources
|   +-- custom domain exceptions
|
+-- Concurrency
|   +-- Thread, Runnable, Callable
|   +-- synchronized, volatile, wait/notify
|   +-- Lock, Atomic classes, ExecutorService
|   +-- Future, CompletableFuture, BlockingQueue
|   +-- ConcurrentHashMap, CopyOnWriteArrayList
|   +-- deadlock, race condition, visibility, happens-before
|
+-- JVM Basics
    +-- heap, stack, metaspace
    +-- garbage collection, class loading
    +-- string pool, memory leaks
```

## How To Study

1. Read a concept note.
2. Compile and run the matching example.
3. Modify the example.
4. Explain the trade-off in one sentence.
5. Apply it to an LLD example.

Example:

- Concept: `HashMap`
- Code: `collections/MapExamples.java`
- Trade-off: "Average O(1) lookup, but no ordering and not thread-safe."
- LLD use: "Use `Map<UserId, User>` when the system frequently fetches a user by ID."

## Interview-Level Checklist

You should be able to answer these without looking:

- Why is `ArrayList` usually better than `LinkedList` for random access?
- Why must `equals()` and `hashCode()` be consistent for `HashMap` keys?
- Why is `TreeMap` useful for range queries?
- What is the difference between `Queue.add()` and `Queue.offer()`?
- Why is `PriorityQueue` not sorted when printed?
- What does `static` mean for a field, method, and nested class?
- Why can Java not have a top-level `static class`?
- What is method overriding versus overloading?
- When should you prefer composition over inheritance?
- What is a race condition?
- What does `volatile` fix, and what does it not fix?
- Why is `ConcurrentHashMap` better than wrapping `HashMap` with `synchronized` for high-concurrency reads?
- What does `CompletableFuture` add over `Future`?
- How do immutable objects help in LLD?

