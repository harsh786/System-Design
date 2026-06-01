# OOP Relationships - Complete Reference

## Master UML Diagram (All Relationships)

```
╔═══════════════════════════════════════════════════════════════════════════╗
║                    UML RELATIONSHIP NOTATION GUIDE                        ║
╠═══════════════════════════════════════════════════════════════════════════╣
║                                                                           ║
║  DEPENDENCY (weakest)                                                     ║
║  A - - - - -> B          (dashed arrow: A uses B temporarily)             ║
║                                                                           ║
║  ASSOCIATION                                                              ║
║  A ──────────> B          (solid arrow: A knows B, unidirectional)        ║
║  A ───────── B            (solid line: A and B know each other)           ║
║                                                                           ║
║  AGGREGATION (weak has-a)                                                 ║
║  A ◇─────────> B          (empty diamond: A has B, B can exist alone)     ║
║                                                                           ║
║  COMPOSITION (strong has-a)                                               ║
║  A ◆─────────> B          (filled diamond: A owns B, B dies with A)      ║
║                                                                           ║
║  INHERITANCE (is-a)                                                       ║
║  B ───────────▷ A         (empty triangle: B is-a A)                     ║
║                                                                           ║
║  REALIZATION (can-do)                                                     ║
║  B - - - - - -▷ A         (dashed + empty triangle: B implements A)      ║
║                                                                           ║
╚═══════════════════════════════════════════════════════════════════════════╝
```

## University System - All Relationships

```
    ┌─────────────────┐
    │   University    │
    └────────┬────────┘
             │ ◆ COMPOSITION (departments die with university)
             │ 1..*
    ┌────────┴────────┐
    │   Department    │
    └────────┬────────┘
             │ ◇ AGGREGATION (professors survive independently)
             │ 0..*
    ┌────────┴────────┐         ASSOCIATION (loose relationship)
    │   Professor     │─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─┐
    └─────────────────┘                        │ 0..*
                                      ┌────────┴────────┐
                                      │    Student      │
                                      └─────────────────┘

    ┌─────────────────┐
    │ OrderProcessor  │- - - -> ┌──────────────┐
    └─────────────────┘         │ EmailService │  DEPENDENCY
                                └──────────────┘

    ┌──────────────────┐              ┌────────────────┐
    │ «interface»      │              │ «interface»    │
    │ PaymentProcessor │              │ Auditable      │
    └───────┬──────────┘              └───────┬────────┘
            │ ▷ REALIZATION                    │ ▷
    ┌───────┴──────────┐                      │
    │ StripeProcessor  │──────────────────────┘
    └──────────────────┘

    ┌──────────┐
    │  Animal  │ ◁─── INHERITANCE
    └────┬─────┘
         │
    ┌────┴────┐
    │         │
  ┌─┴──┐  ┌──┴─┐
  │Dog │  │Cat │
  └────┘  └────┘
```

---

## Detailed Breakdown

### 1. Dependency (Weakest)

| Aspect | Detail |
|--------|--------|
| **UML** | `A - - - -> B` (dashed arrow) |
| **Definition** | A uses B temporarily in a method |
| **Analogy** | You use a taxi — you don't own it, don't store it |
| **Lifecycle** | No impact — A and B are completely independent |
| **Multiplicity** | Typically method-level, no cardinality |
| **Code Indicator** | Method parameter, local variable, static method call |
| **When to use** | When you only need something temporarily in one method |

```java
class OrderProcessor {
    void process(EmailService svc) { // dependency - param only
        svc.sendEmail(...);
    }
}
```

### 2. Association

| Aspect | Detail |
|--------|--------|
| **UML** | `A ────> B` (solid arrow) or `A ──── B` (bidirectional) |
| **Definition** | A knows B, both exist independently |
| **Analogy** | A driver and a car — either can exist without the other |
| **Lifecycle** | No impact on destruction — both survive independently |
| **Multiplicity** | 1:1, 1:*, *:* all possible |
| **Code Indicator** | Field reference, but object created elsewhere |
| **When to use** | Objects need to know each other but don't own each other |

```java
class Teacher {
    List<Student> students; // association - students exist independently
}
```

### 3. Aggregation (Weak Has-A)

| Aspect | Detail |
|--------|--------|
| **UML** | `A ◇────> B` (empty diamond at A) |
| **Definition** | A has B, but B can exist without A |
| **Analogy** | A team has players — if team disbands, players still exist |
| **Lifecycle** | Part survives destruction of whole |
| **Multiplicity** | Usually 1:* |
| **Code Indicator** | Object passed via constructor/setter, not created inside |
| **When to use** | Whole-part relationship where parts are shared or independent |

```java
class Department {
    List<Professor> profs;
    void addProfessor(Professor p) { // passed in from outside
        profs.add(p);
    }
}
```

### 4. Composition (Strong Has-A)

| Aspect | Detail |
|--------|--------|
| **UML** | `A ◆────> B` (filled diamond at A) |
| **Definition** | A owns B, B cannot exist without A |
| **Analogy** | A house has rooms — demolish house, rooms are gone |
| **Lifecycle** | Part is destroyed when whole is destroyed |
| **Multiplicity** | 1:1 or 1:* (exclusive ownership) |
| **Code Indicator** | Object created inside constructor, no external reference |
| **When to use** | Part is meaningless without the whole |

```java
class House {
    List<Room> rooms;
    House() {
        rooms.add(new Room("Kitchen")); // created inside - composition!
    }
    void demolish() {
        rooms.forEach(Room::destroy); // rooms die with house
    }
}
```

### 5. Inheritance (Is-A)

| Aspect | Detail |
|--------|--------|
| **UML** | `B ────▷ A` (empty triangle pointing to parent) |
| **Definition** | B is a specialized form of A |
| **Analogy** | A dog is an animal |
| **Lifecycle** | Subclass instance contains superclass state |
| **Multiplicity** | Single inheritance in Java |
| **Code Indicator** | `extends` keyword |
| **When to use** | True "is-a" with Liskov Substitution Principle |

### 6. Realization (Can-Do)

| Aspect | Detail |
|--------|--------|
| **UML** | `B - - -▷ A` (dashed + empty triangle) |
| **Definition** | B fulfills the contract defined by interface A |
| **Analogy** | A person can be a swimmer, a driver, a cook (roles) |
| **Lifecycle** | Interface defines behavior, class provides implementation |
| **Multiplicity** | A class can implement many interfaces |
| **Code Indicator** | `implements` keyword |
| **When to use** | Define capabilities/contracts without prescribing implementation |

---

## Comparison Table

| Criteria | Dependency | Association | Aggregation | Composition |
|----------|-----------|-------------|-------------|-------------|
| **Strength** | Weakest | Weak | Medium | Strong |
| **Ownership** | None | None | Weak | Full |
| **Lifecycle** | Independent | Independent | Independent | Dependent |
| **Part exists alone?** | N/A | Yes | Yes | **No** |
| **Code location** | Method param | Field | Field (passed in) | Field (created in) |
| **UML symbol** | `- - ->` | `────>` | `◇────>` | `◆────>` |
| **Multiplicity** | N/A | Any | 1:many | 1:many (exclusive) |
| **Destruction** | No effect | No effect | Part survives | Part destroyed |

---

## Strength Hierarchy

```
WEAKEST                                                    STRONGEST
   │                                                          │
   ▼                                                          ▼
┌──────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│Dependency│→ │ Association │→ │ Aggregation │→ │ Composition │→ │ Inheritance │
│          │  │             │  │             │  │             │  │             │
│ "uses"   │  │  "knows"   │  │ "has-weak"  │  │"has-strong" │  │   "is-a"    │
│ temporal  │  │ references  │  │ shared parts│  │ owned parts │  │  identity   │
└──────────┘  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘
```

---

## Decision Flowchart

```
Does class A need class B?
│
├─ Only in one method? ──────────────────────────→ DEPENDENCY
│
├─ As a field (long-term reference)?
│   │
│   ├─ Does A own B's lifecycle?
│   │   │
│   │   ├─ YES: B meaningless without A? ────────→ COMPOSITION
│   │   │
│   │   └─ NO: B can exist alone? ──────────────→ AGGREGATION
│   │
│   └─ No ownership, just knows B? ─────────────→ ASSOCIATION
│
├─ Is A a specialized type of B? ────────────────→ INHERITANCE
│
└─ Does A fulfill a contract? ───────────────────→ REALIZATION
```

---

## Common Mistakes

| Mistake | Why It's Wrong | Better Approach |
|---------|---------------|-----------------|
| Using inheritance for code reuse | Violates LSP, creates tight coupling | Use composition + delegation |
| Deep inheritance hierarchies | Fragile base class problem | Prefer shallow + interfaces |
| Composition when aggregation needed | Over-controlling lifecycle | Ask: does part exist alone? |
| Association when dependency suffices | Unnecessary coupling | If only used in one method, use dependency |
| God classes that own everything | Single Responsibility violation | Distribute ownership appropriately |

### Inheritance vs Composition Rule of Thumb

```
"Favor composition over inheritance" — Gang of Four

Use INHERITANCE when:
  ✓ True "is-a" relationship (Dog IS an Animal)
  ✓ Liskov Substitution holds (can substitute child for parent)
  ✓ You want polymorphism

Use COMPOSITION when:
  ✓ "has-a" or "uses-a" relationship
  ✓ You want to reuse behavior without being that type
  ✓ You need flexibility to change at runtime
  ✓ Multiple behaviors needed (Java: no multiple inheritance)
```

---

## UML Class Diagram Symbols Reference

```
┌─────────────────────────────┐
│ «stereotype»                │  ← stereotype (interface, abstract, etc.)
│ ClassName                   │  ← class name (bold = concrete, italic = abstract)
├─────────────────────────────┤
│ - privateField: Type        │  ← attributes
│ # protectedField: Type      │     - private
│ + publicField: Type         │     # protected
│ ~ packageField: Type        │     + public
├─────────────────────────────┤
│ + publicMethod(): RetType   │  ← operations
│ - privateMethod(): void     │
│ # abstractMethod(): Type    │  ← italic = abstract
└─────────────────────────────┘

Multiplicity: 1, 0..1, *, 1..*, 0..*
```

---

## Interview Questions

1. **What's the difference between aggregation and composition?**
   - Aggregation: part survives without whole (empty diamond ◇)
   - Composition: part dies with whole (filled diamond ◆)
   - Example: Department-Professor (aggregation) vs House-Room (composition)

2. **When would you choose composition over inheritance?**
   - When you need flexibility, multiple behaviors, or "has-a" relationship
   - Inheritance creates tight coupling; composition allows runtime changes

3. **What is the diamond problem and how does Java solve it?**
   - If class C inherits from A and B, and both have method `foo()`, which one does C get?
   - Java: single inheritance only; uses interfaces for multiple contracts
   - Java 8+ default methods: must override explicitly if conflict exists

4. **How do you identify relationship type from code?**
   - Dependency: parameter/local variable
   - Association: field, object created elsewhere
   - Aggregation: field, object passed via constructor/setter
   - Composition: field, object created inside constructor

5. **Give a real-world system with all relationships.**
   - University COMPOSES departments (die together)
   - Department AGGREGATES professors (survive independently)
   - Professor ASSOCIATES with students (loose connection)
   - GradeCalculator DEPENDS on MathLibrary (uses in method)
   - GradStudent IS-A Student (inheritance)
   - Professor IMPLEMENTS Researcher (realization)

6. **Can aggregation become composition?**
   - Yes, it depends on context. A tire in a factory is aggregation (shared, replaceable).
   - A tire designed specifically for one prototype car is composition (meaningless without it).

7. **What's the relationship between coupling and relationship strength?**
   - Stronger relationship = tighter coupling
   - Dependency (loosest) → Inheritance (tightest)
   - Prefer the weakest relationship that satisfies requirements
