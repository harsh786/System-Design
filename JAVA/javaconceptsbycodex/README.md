# Java Concepts By Codex

This folder is a Java brush-up pack for LLD preparation. It covers the concepts named in your request, especially collections, static and inner classes, inheritance, and concurrency. It also includes adjacent Java topics that usually appear in LLD interviews: generics, exceptions, streams, immutability, JVM memory, and design-pattern-oriented usage.

The notes are intentionally written as study material, and the examples are plain Java files so you can compile them without Maven or Gradle.

## How To Run The Examples

From this folder:

```bash
javac -d out $(find src/main/java -name "*.java")
java -cp out com.codex.javaconcepts.AllExamplesRunner
```

Run one topic directly:

```bash
java -cp out com.codex.javaconcepts.collections.ListExamples
java -cp out com.codex.javaconcepts.collections.MapExamples
java -cp out com.codex.javaconcepts.concurrency.ConcurrencyExamples
```

## Study Order

1. `00-roadmap/java-lld-study-roadmap.md`
2. `01-oop-static-inheritance/oop-static-inheritance.md`
3. `02-collections/collections-overview.md`
4. `02-collections/list-arraylist-linkedlist.md`
5. `02-collections/set-hashset-treeset.md`
6. `02-collections/map-hashmap-treemap-linkedhashmap.md`
7. `02-collections/queue-deque-priorityqueue.md`
8. `03-generics-functional-streams/generics-functional-streams.md`
9. `04-exceptions/exceptions.md`
10. `05-concurrency/concurrency.md`
11. `06-jvm-memory/jvm-memory.md`
12. `07-immutability-records-enums/immutability-records-enums.md`
13. `08-lld-patterns/lld-java-patterns.md`
14. `09-core-language/core-language-strings-arrays.md`

## Source Note

The local instruction asked to use Context7 for current Java documentation. I used Context7 to resolve and fetch Oracle Java documentation context, then wrote this as an interview-focused learning pack using standard Java SE APIs.
