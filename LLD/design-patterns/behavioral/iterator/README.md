# Iterator Design Pattern

## What is it?
The Iterator pattern provides a way to access elements of a collection sequentially **without exposing its underlying representation** (array, linked list, tree, graph, etc.).

## When to Use
- You need to traverse a collection without exposing its internals
- You need multiple traversal strategies (forward, reverse, BFS, DFS)
- You want a uniform interface for traversing different data structures
- You need multiple simultaneous traversals on the same collection

## Why Use It
- **Encapsulation**: Internal structure stays hidden
- **Single Responsibility**: Traversal logic separated from collection logic
- **Open/Closed**: Add new iterators without changing the collection

---

## ASCII Class Diagram

```
+-------------------+          +-------------------+
|    <<interface>>  |          |    <<interface>>   |
|     Iterator<T>   |          | IterableCollection |
+-------------------+          +-------------------+
| + hasNext(): bool |          | + createIterator() |
| + next(): T       |          +-------------------+
| + reset(): void   |                   |
+-------------------+                   |
        ^                               ^
        |                               |
        |                               |
+--------------------+       +------------------------+
| ConcreteIterator   |<------| ConcreteCollection     |
+--------------------+       +------------------------+
| - position: int    |       | - elements: T[]        |
| - collection: ref  |       | + add(T): void         |
+--------------------+       | + createIterator()     |
| + hasNext(): bool  |       +------------------------+
| + next(): T        |
| + reset(): void    |
+--------------------+

Client --> Iterator (uses interface only, never touches collection internals)
```

---

## Real-World Use Cases

| Use Case | Description |
|----------|-------------|
| **Java Collections** | `java.util.Iterator`, `ListIterator`, `Spliterator` |
| **Database Cursors** | JDBC `ResultSet` iterates rows without loading all into memory |
| **File System Traversal** | `DirectoryStream`, `Files.walk()` iterate files lazily |
| **Tree Traversal** | In-order, pre-order, post-order iterators on same tree |
| **Social Networks** | BFS/DFS traversal of friend graphs |
| **Pagination** | API pagination iterators fetch next page on demand |
| **Stream Processing** | Kafka consumers iterate over message streams |

---

## Internal vs External Iterator

| Aspect | External Iterator | Internal Iterator |
|--------|-------------------|-------------------|
| **Control** | Client controls traversal | Collection controls traversal |
| **Interface** | `hasNext()` / `next()` | `forEach(action)` |
| **Flexibility** | Can pause, compare, interleave | Simpler but less flexible |
| **Example** | `while(iter.hasNext()) iter.next()` | `collection.forEach(e -> ...)` |
| **Java** | `Iterator<T>` | `Iterable.forEach()`, Streams |

**External** = client pulls elements one at a time (more control)  
**Internal** = client passes a callback, collection drives the loop (simpler)

---

## Pros and Cons

### Pros
- Single Responsibility: separates traversal from storage
- Open/Closed: new iterators without modifying collection
- Multiple iterators can traverse same collection simultaneously
- Lazy evaluation possible (don't load everything into memory)
- Uniform traversal interface across different data structures

### Cons
- Overkill for simple collections (just use a for-loop)
- Can be less efficient than direct access for some structures
- Iterator may become invalid if collection is modified during traversal
- Added complexity (more classes/interfaces)

---

## When to Use

- Collection has complex internal structure (tree, graph, composite)
- You need multiple traversal algorithms
- You want to hide collection implementation from clients
- You need lazy/streaming traversal of large datasets

## When NOT to Use

- Simple collections with obvious traversal (small arrays/lists)
- You only ever need one traversal strategy
- Performance-critical tight loops where iterator overhead matters
- Collection is never shared across different client code

---

## Running the Example

```bash
javac IteratorPattern.java && java IteratorPattern
```
