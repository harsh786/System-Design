# Prototype Design Pattern

## What is it?

The Prototype pattern creates new objects by **cloning existing instances** (prototypes) instead of using constructors. The client doesn't need to know the concrete class — it just asks a prototype to copy itself.

## When to Use

- Object creation is **expensive** (DB calls, network requests, heavy computation)
- You need many similar objects with slight variations
- You want to avoid complex class hierarchies of factories
- Runtime configuration determines which objects to create
- You need to preserve object state as a snapshot

## When NOT to Use

- Objects are cheap to create (simple POJOs)
- Objects have circular references (cloning becomes complex)
- Classes have many final fields that prevent copying
- You need only one instance (use Singleton instead)

## Class Diagram (ASCII)

```
    +-------------------+
    |   <<interface>>   |
    |     Prototype     |
    +-------------------+
    | + clone(): Self   |
    +-------------------+
            ^
            |  implements
     +------+------+
     |             |
+----------+  +----------+
| ConcreteA |  | ConcreteB |
+----------+  +----------+
| - state  |  | - state  |
| + clone() |  | + clone() |
+----------+  +----------+

+------------------+
| PrototypeRegistry|
+------------------+
| - cache: Map     |
| + get(key): Proto|
| + register(...)  |
+------------------+
```

## How It Works

1. Define a `clone()` method in a Prototype interface
2. Concrete classes implement deep-copy logic in `clone()`
3. A **Registry** stores pre-built prototypes keyed by name
4. Clients request clones from the registry — never modifying the stored original

## Real-World Use Cases

| Use Case | Why Prototype? |
|----------|---------------|
| **Object caching** | Clone cached objects instead of re-fetching from DB |
| **Game object spawning** | Clone enemy/NPC templates with pre-loaded assets |
| **Document templates** | Clone base documents, customize per user |
| **Cell division simulation** | Clone parent cell, mutate daughter cells |
| **GUI widget libraries** | Clone configured widget prototypes |
| **Undo/snapshot systems** | Clone state for rollback |

## Deep Copy vs Shallow Copy

| Aspect | Shallow Copy | Deep Copy |
|--------|-------------|-----------|
| Primitives | Copied | Copied |
| References | **Shared** | **New independent copies** |
| Safety | Mutations leak between copies | Fully independent |
| Cost | Cheaper | More expensive |

**Always use deep copy** unless you intentionally want shared state.

## Pros and Cons

### Pros
- Avoids expensive object initialization
- Reduces subclass proliferation (vs Abstract Factory)
- Clone complex objects without coupling to their classes
- Pre-build and cache objects for repeated use
- Simpler than re-running complex construction logic

### Cons
- Deep copying complex object graphs is tricky (circular refs)
- Each class must implement its own clone logic
- Clone method can be hard to implement correctly with inheritance
- Mutable shared state bugs if shallow copy is used accidentally

## Running the Code

```bash
cd prototype/
javac PrototypePattern.java
java PrototypePattern
```
