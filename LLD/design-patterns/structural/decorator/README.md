# Decorator Design Pattern

## What Is It?

The Decorator pattern attaches additional responsibilities to an object dynamically. It provides a flexible alternative to subclassing for extending functionality by wrapping objects with decorator objects that share the same interface.

## When to Use

- You need to add behavior to objects at runtime without affecting other objects
- Extension by subclassing is impractical (too many combinations)
- You want to combine multiple behaviors flexibly (stacking)

## Why Use It

- Avoids class explosion from combinatorial subclassing
- Follows Open/Closed Principle (open for extension, closed for modification)
- Single Responsibility: each decorator handles one concern

## Class Diagram (ASCII)

```
        +-------------------+
        |    <<interface>>  |
        |     Component     |
        +-------------------+
        | + operation()     |
        +-------------------+
              ^         ^
              |         |
   +----------+    +-------------------+
   |               |  BaseDecorator    |
   |               +-------------------+
   |               | - wrapped: Comp.  |
   |               | + operation()     |
   |               +-------------------+
   |                    ^          ^
   |                    |          |
+------------------+  +--------+ +--------+
| ConcreteComponent|  |DecorA  | |DecorB  |
+------------------+  +--------+ +--------+
| + operation()    |  |+oper() | |+oper() |
+------------------+  +--------+ +--------+
```

Decorator delegates to the wrapped component, then adds its own behavior.

## Real-World Use Cases

| Use Case | Component | Decorators |
|----------|-----------|------------|
| Java I/O Streams | InputStream | BufferedInputStream, DataInputStream, GZIPInputStream |
| Pizza Ordering | BasePizza | CheeseTopping, OliveTopping, MushroomTopping |
| HTTP Middleware | Handler | AuthMiddleware, LoggingMiddleware, CORSMiddleware |
| Logging | Logger | TimestampDecorator, LevelFilterDecorator |
| Text Formatting | Text | BoldDecorator, ItalicDecorator, UnderlineDecorator |

## Decorator vs Inheritance

| Aspect | Decorator | Inheritance |
|--------|-----------|-------------|
| Timing | Runtime | Compile-time |
| Combinations | Stack freely (N decorators = N classes) | Combinatorial explosion (2^N subclasses) |
| Flexibility | Add/remove dynamically | Fixed hierarchy |
| Complexity | More objects at runtime | Simpler object graph |
| Principle | Composition over inheritance | IS-A relationship |

Example: 4 toppings on a pizza
- Inheritance: 2^4 = 16 subclasses
- Decorator: 4 decorator classes, stack as needed

## Pros

- Open/Closed Principle - extend without modifying existing code
- Single Responsibility - one decorator = one behavior
- Flexible composition at runtime
- Avoids feature-loaded base classes

## Cons

- Many small objects can complicate debugging
- Order of wrapping can matter (and may cause subtle bugs)
- Hard to remove a specific decorator from the middle of a stack
- Initial setup more complex than simple inheritance

## When NOT to Use

- Object identity matters (decorator != original object with `==`)
- You only need one fixed combination (just use inheritance)
- Performance-critical paths where wrapping overhead matters
- The component interface is unstable (every change propagates to all decorators)
