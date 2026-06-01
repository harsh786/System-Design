# Memento Design Pattern

## What Is It?

The Memento pattern captures and externalizes an object's internal state so it can be restored later, **without violating encapsulation**. It provides the ability to "snapshot" an object and roll back to that snapshot.

## When to Use

- You need undo/redo functionality
- You want to save checkpoints (games, transactions)
- You need to restore an object to a previous state
- You want state history without exposing internal implementation

## Why Use It

- Preserves encapsulation boundaries
- Simplifies the originator (no history management burden)
- Clean separation: state capture vs. state management

## Class Diagram

```
+------------------+       saves/restores        +------------------+
|    Originator    |<--------------------------->|     Memento      |
|------------------|                             |------------------|
| - state          |   createMemento()           | - state (final)  |
|------------------|---->  returns Memento        |------------------|
| + save(): Memento|                             | + getState()     |
| + restore(m)     |                             +------------------+
+------------------+                                      ^
                                                          |
                                                          | holds
                                                          |
                                               +------------------+
                                               |    Caretaker     |
                                               |------------------|
                                               | - history: Stack |
                                               |------------------|
                                               | + save(memento)  |
                                               | + undo(): Memento|
                                               | + redo(): Memento|
                                               +------------------+
```

## Real-World Use Cases

| Use Case | Originator | Memento | Caretaker |
|----------|-----------|---------|-----------|
| Text editor undo | Document | DocumentSnapshot | UndoManager |
| Game saves | GameCharacter | SaveData | SaveSlotManager |
| DB transactions | Connection | Savepoint | TransactionManager |
| Version control | WorkingTree | Commit | Repository |
| Form wizard | FormState | StepSnapshot | WizardController |

## Memento vs Command (for Undo)

| Aspect | Memento | Command |
|--------|---------|---------|
| Stores | Full state snapshot | Operation + inverse |
| Memory | Higher (full copies) | Lower (just operations) |
| Complexity | Simple to implement | Needs inverse for each op |
| Reliability | Always correct | Inverse must be exact |
| Best for | Complex state, few saves | Many small reversible ops |

**Rule of thumb:** Use Memento when state is small or inverse operations are hard to define. Use Command when state is large but operations are easily reversible.

## Encapsulation Considerations

- The Memento should be **opaque** to the Caretaker — it stores but never inspects state
- In Java, use package-private access or nested classes to restrict Memento field access
- Make Memento **immutable** (final fields, defensive copies of collections)
- Deep-copy mutable objects (lists, maps) to prevent external modification

## Pros and Cons

### Pros
- Preserves encapsulation
- Simplifies originator code
- Easy to implement undo/redo
- State snapshots are independent and composable

### Cons
- High memory usage if state is large or saves are frequent
- Caretaker must manage lifecycle (delete old mementos)
- Serialization cost for deep copies
- No partial restore (all-or-nothing)

## When NOT to Use

- State is extremely large and changes frequently (use Command instead)
- You only need to track one field change (overkill)
- The object has no meaningful "previous state" concept
- Performance-critical paths where copying is too expensive
