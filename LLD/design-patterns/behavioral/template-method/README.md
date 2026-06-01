# Template Method Design Pattern

## What is it?

The Template Method pattern defines the **skeleton of an algorithm** in a base class, letting subclasses override specific steps without changing the overall structure.

> **Hollywood Principle: "Don't call us, we'll call you."**
> The base class calls the subclass methods — not the other way around. The framework is in control.

## When to Use

- You have several classes with nearly identical algorithms, differing only in some steps
- You want to let clients extend only particular steps, not the whole algorithm
- You want to enforce a fixed sequence of operations

## When NOT to Use

- Every step varies across implementations (use Strategy instead)
- The algorithm has very few steps or no fixed structure
- You need runtime algorithm switching (Strategy is better)
- Subclass explosion becomes unmanageable

---

## Class Diagram (ASCII)

```
    ┌─────────────────────────────┐
    │    AbstractClass             │
    ├─────────────────────────────┤
    │ + templateMethod()  [final] │  ← defines skeleton
    │ # step1()          [abstract]│
    │ # step2()          [abstract]│
    │ # step3()          [concrete]│  ← default impl
    │ # hook()           [concrete]│  ← optional override
    └──────────────┬──────────────┘
                   │
         ┌─────────┴─────────┐
         │                     │
┌────────▼────────┐  ┌────────▼────────┐
│  ConcreteClassA  │  │  ConcreteClassB  │
├──────────────────┤  ├──────────────────┤
│ # step1()        │  │ # step1()        │
│ # step2()        │  │ # step2()        │
│ # hook()         │  │                  │
└──────────────────┘  └──────────────────┘
```

---

## Hook Methods

Hooks are methods with a **default (usually empty) implementation** in the abstract class. Subclasses *may* override them but aren't forced to.

Use cases:
- **Boolean hooks** — control whether an optional step runs (`shouldAnalyze()`, `wantsCondiments()`)
- **Notification hooks** — react to events (`beforeClose()`, `afterInit()`)

```java
// In abstract class:
boolean shouldAnalyze() { return true; }   // hook
void beforeClose() { }                      // hook

// In subclass:
@Override
boolean shouldAnalyze() { return false; }   // skip analysis
```

---

## Real-World Use Cases

| Domain | Example |
|--------|---------|
| **Frameworks** | Servlet `doGet()`/`doPost()` called by `service()` template |
| **Data Processing** | ETL pipelines: extract → transform → load with varying sources |
| **Test Frameworks** | JUnit: `setUp()` → `testXxx()` → `tearDown()` |
| **Build Systems** | Maven lifecycle: validate → compile → test → package → deploy |
| **UI Frameworks** | Android Activity: `onCreate()` → `onStart()` → `onResume()` |
| **Java I/O** | `InputStream.read()` — subclasses implement single-byte read |

---

## Template Method vs Strategy

| Aspect | Template Method | Strategy |
|--------|----------------|----------|
| Mechanism | Inheritance | Composition |
| Granularity | Varies some steps | Replaces entire algorithm |
| Binding | Compile-time | Runtime (swappable) |
| Control | Parent controls flow | Client controls which strategy |
| Coupling | Tight (subclass ↔ parent) | Loose (interface-based) |
| Class count | One subclass per variant | One strategy class per variant |

**Rule of thumb:** Use Template Method when the algorithm structure is fixed and only details vary. Use Strategy when you need to swap entire algorithms at runtime.

---

## Pros and Cons

### Pros
- Eliminates code duplication — common logic lives in one place
- Enforces algorithm structure — subclasses can't break the sequence
- Easy to extend — add new variants without modifying existing code
- Hook methods provide flexible extension points without forcing override

### Cons
- Inheritance-based — limited to single inheritance in Java
- Can violate Liskov Substitution if subclasses suppress steps
- Harder to understand — control flow bounces between parent and child
- More steps = more rigid; subclasses may feel overly constrained

---

## Running the Demo

```bash
javac TemplateMethodPattern.java
java TemplateMethodPattern
```
