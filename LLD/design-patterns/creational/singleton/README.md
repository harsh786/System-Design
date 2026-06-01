# Singleton Design Pattern

## What is it?

The Singleton pattern ensures a class has **exactly one instance** and provides a **global point of access** to it. The class itself controls its instantiation, preventing other objects from creating new instances.

## When to Use

- Exactly one instance of a class is needed (database pool, logger, config)
- The single instance must be accessible from a well-known access point
- You need stricter control over global variables

## Why Use It

- Controlled access to a sole instance
- Reduced namespace pollution (vs global variables)
- Permits refinement of operations and representation (subclassing)
- Can be extended to allow a variable number of instances

---

## Class Diagram

```
+------------------------------------------+
|           Singleton                       |
+------------------------------------------+
| - static instance: Singleton             |
| - data: SomeType                         |
+------------------------------------------+
| - Singleton()           [private ctor]   |
| + static getInstance(): Singleton        |
| + operation(): void                      |
+------------------------------------------+

Client ----> getInstance() ----> [single instance]
```

### Three Implementation Variants

```
1. Double-Checked Locking        2. Enum Singleton         3. Static Inner Class
+------------------------+    +-------------------+    +------------------------+
| - volatile instance    |    | enum Config {     |    | class Logger {         |
| + getInstance() {      |    |   INSTANCE;       |    |   private Logger() {}  |
|   if (null) {          |    |   // fields/methods|   |   static class Holder {|
|     synchronized {     |    | }                 |    |     static final INST  |
|       if (null)        |    +-------------------+    |   }                    |
|         new Instance() |                             |   getInstance() ->     |
|     }                  |                             |     Holder.INST        |
|   }                    |                             +------------------------+
| }                      |
+------------------------+
```

---

## Real-World Use Cases

| Use Case | Why Singleton? |
|----------|---------------|
| **Logger** | Single log stream, avoid file contention |
| **Configuration Manager** | One source of truth for app settings |
| **Thread Pool** | Expensive to create, must be shared |
| **Database Connection Pool** | Limited connections, shared resource |
| **Cache Manager** | Single shared cache across application |
| **Hardware Interface Access** | One printer spooler, one file system |

---

## Pros and Cons

### Pros
- Guarantees single instance
- Global access point (better than global variable)
- Lazy initialization possible (created only when needed)
- Thread-safe with proper implementation

### Cons
- Violates Single Responsibility Principle (manages its own lifecycle)
- Can mask bad design (tight coupling, hidden dependencies)
- Difficult to unit test (hard to mock/substitute)
- Problems in multithreaded environments if poorly implemented
- Can become a bottleneck if overused

---

## When NOT to Use

- When you just need a shared object (use Dependency Injection instead)
- In unit-testable code where mocking is important
- When the "single instance" requirement might change later
- For simple utility/helper classes (use static methods instead)
- When it introduces hidden coupling between components

---

## Implementation Comparison

| Approach | Thread-Safe | Lazy | Serialization-Safe | Reflection-Safe |
|----------|:-----------:|:----:|:-----------------:|:---------------:|
| Double-Checked Locking | Yes | Yes | No* | No |
| Enum | Yes | No | Yes | Yes |
| Static Inner Class | Yes | Yes | No* | No |

*Requires custom `readResolve()` for serialization safety.

---

## How to Run

```bash
javac SingletonPattern.java
java SingletonPattern
```
