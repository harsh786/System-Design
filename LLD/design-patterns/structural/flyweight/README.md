# Flyweight Design Pattern

## What is it?

The Flyweight pattern minimizes memory usage by sharing as much data as possible between similar objects. It separates object state into:

- **Intrinsic State** - Shared, immutable data stored in the flyweight (e.g., tree texture, font properties)
- **Extrinsic State** - Unique, context-dependent data stored externally (e.g., position, character value)

## When to Use

- You need a huge number of similar objects (thousands/millions)
- Objects share significant repeating state
- Memory is a constraint
- Extrinsic state can be computed or stored cheaply outside

## When NOT to Use

- Few objects exist (overhead of factory isn't worth it)
- Objects don't share meaningful state
- RAM isn't a concern for your use case
- Shared state is mutable (flyweights must be immutable)

---

## Class Diagram

```
+------------------+         +-------------------+
|   Client         |         |  FlyweightFactory |
|------------------|         |-------------------|
| - flyweights[]---|-------->| - cache: Map      |
|                  |         | + getFlyweight()  |
+------------------+         +--------+----------+
                                      |
                                      | creates/returns
                                      v
                             +-------------------+
                             |   <<interface>>   |
                             |    Flyweight      |
                             |-------------------|
                             | + operation(      |
                             |    extrinsicState)|
                             +--------+----------+
                                      |
                          +-----------+-----------+
                          |                       |
                 +--------+--------+    +---------+-------+
                 | ConcreteFlyweight|    | UnsharedFlyweight|
                 |-----------------|    |-----------------|
                 | - intrinsicState|    | - allState      |
                 | + operation()   |    | + operation()   |
                 +-----------------+    +-----------------+
```

### Applied to Tree Example:

```
+--------+        +------------------+       +-----------+
| Forest |------->| TreeTypeFactory  |       | TreeType  |
|--------|        |------------------|       |-----------|
| trees[]|        | cache: Map<K,V>  |------>| name      |
+--------+        | getTreeType()    |       | color     |  <- INTRINSIC
     |            +------------------+       | texture   |     (shared)
     v                                       | render()  |
 +------+                                    +-----------+
 | Tree  |
 |------|
 | x, y | <- EXTRINSIC (unique per instance)
 | type -|---> (reference to shared TreeType)
 +------+
```

---

## Real-World Use Cases

| Use Case | Intrinsic (Shared) | Extrinsic (Unique) |
|----------|-------------------|-------------------|
| **Java String Pool** | String value | Variable reference |
| **Game Sprites** | Texture, mesh, animations | Position, rotation, health |
| **Text Editor** | Font family, size, style | Character, position |
| **Browser DOM** | CSS styles, shared attributes | Element position, content |
| **Integer Cache** (-128 to 127) | Integer value | Variable reference |
| **Connection Pool** | Connection config | Query, transaction state |

---

## Memory Analysis

### 1 Million Trees - 5 types x 5 colors = 25 unique combinations

| Metric | Without Flyweight | With Flyweight |
|--------|------------------|----------------|
| TreeType objects | 1,000,000 | 25 |
| Texture data copies | 1,000,000 | 25 |
| Memory for types | ~1,000 MB | ~27 KB |
| Memory for positions | ~16 MB | ~24 MB |
| **Total** | **~1,016 MB** | **~24 MB** |
| **Savings** | - | **~97.6%** |

---

## Pros and Cons

### Pros
- Dramatically reduces memory for large object collections
- Separates concerns (shared vs unique state)
- Can improve cache locality
- Immutable flyweights are inherently thread-safe

### Cons
- Increased code complexity (factory, state separation)
- CPU trade-off: lookup cost in factory cache
- Harder to debug (many objects share same reference)
- Extrinsic state management burden on client

---

## How to Run

```bash
javac FlyweightPattern.java
java FlyweightPattern
```

---

## Related Patterns

- **Factory Method** - Used to create/cache flyweights
- **Composite** - Often combined (shared leaf nodes)
- **State/Strategy** - Can be implemented as flyweights if stateless
- **Singleton** - Flyweight factory is often a singleton
