# JVM Memory And Runtime Basics

You do not need to be a JVM engineer for LLD, but you should understand enough to reason about object allocation, references, garbage collection, and memory leaks.

## JVM

The Java Virtual Machine runs bytecode. Java source code becomes `.class` files, and the JVM executes those class files.

Flow:

```text
.java source -> javac -> .class bytecode -> JVM -> machine execution
```

## JDK, JRE, JVM

| Term | Meaning |
|---|---|
| JVM | Runtime engine that executes bytecode |
| JRE | JVM plus runtime libraries |
| JDK | JRE plus development tools like `javac`, `jcmd`, `jstack` |

## Memory Areas

```text
JVM Process
|
+-- Heap
|   +-- objects
|   +-- arrays
|
+-- Thread Stack
|   +-- method frames
|   +-- local variables
|   +-- references
|
+-- Metaspace
|   +-- class metadata
|
+-- Code Cache
    +-- JIT compiled code
```

## Heap

Objects live on the heap.

```java
User user = new User("u1");
```

The `User` object is on the heap. The local variable `user` is a reference stored in the current method frame.

## Stack

Each thread has its own stack. Method calls create stack frames.

```java
void a() {
    int x = 10;
    b();
}
```

Local primitive variables and references live in stack frames. Objects referred to by those references live on the heap.

## Metaspace

Metaspace stores class metadata. Too many dynamically loaded classes can cause metaspace issues.

## Garbage Collection

Garbage collection frees heap objects that are no longer reachable.

An object is reachable if it can be accessed from roots such as:

- active thread stacks
- static fields
- JNI references
- running method references

## Common Memory Leak Patterns

Java has garbage collection, but leaks still happen when objects remain reachable.

Examples:

- static collections that keep growing
- cache without eviction
- listeners not unregistered
- `ThreadLocal` values not cleared in thread pools
- long-lived maps with mutable or never-removed keys
- retaining large object graphs through one reference

## String Pool

String literals are interned.

```java
String a = "java";
String b = "java";
System.out.println(a == b); // true for literals
```

But:

```java
String c = new String("java");
System.out.println(a == c); // false
System.out.println(a.equals(c)); // true
```

Use `.equals()` for string value comparison.

## Class Loading

The JVM loads classes when needed.

Phases:

1. loading
2. linking
3. initialization

Static fields and static blocks run during class initialization.

## JIT

The Just-In-Time compiler compiles hot bytecode paths to optimized machine code while the program runs.

LLD implication: choose clear data structures first. Micro-optimizations are usually less important than correct collection choice and clear object boundaries.

## Useful JVM Tools

| Tool | Use |
|---|---|
| `java -version` | Check Java version |
| `javac` | Compile source |
| `jps` | List Java processes |
| `jstack` | Thread dump |
| `jcmd` | JVM diagnostics |
| `jmap` | Heap information |
| `jstat` | GC statistics |

Runnable example: `src/main/java/com/codex/javaconcepts/jvm/JvmMemoryExamples.java`

