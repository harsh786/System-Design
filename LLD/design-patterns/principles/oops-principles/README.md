# OOP Principles - Comprehensive Guide

## Overview

Object-Oriented Programming is built on 4 fundamental pillars that work together to create maintainable, extensible software.

```
                    ┌─────────────────────────────┐
                    │      OOP PRINCIPLES          │
                    └─────────────┬───────────────┘
                                  │
         ┌────────────┬───────────┼───────────┬────────────┐
         │            │           │           │            │
    ┌────▼────┐ ┌─────▼─────┐ ┌──▼───┐ ┌────▼─────┐     │
    │Encapsu- │ │Abstraction│ │Inher-│ │Polymor-  │     │
    │lation   │ │           │ │itance│ │phism     │     │
    └────┬────┘ └─────┬─────┘ └──┬───┘ └────┬─────┘     │
         │            │           │           │            │
         │   HIDES    │  HIDES    │  REUSES   │  FLEXES    │
         │   data     │  complexity│  code     │  behavior  │
         └────────────┴───────────┴───────────┴────────────┘

    Encapsulation + Abstraction = INFORMATION HIDING (what vs how)
    Inheritance + Polymorphism  = CODE REUSE & FLEXIBILITY
```

---

## 1. Encapsulation

### What
Bundling data (fields) and methods that operate on that data into a single unit (class), restricting direct access to internal state.

### Why It Matters
- Prevents invalid state (balance can't go negative)
- Allows internal changes without breaking external code
- Reduces coupling between components

### Real-World Analogy
**ATM Machine**: You interact via buttons and screen (public interface). You cannot reach into the vault (private fields). The ATM validates your PIN before dispensing cash (setter validation).

### When to Use
- Always. Every class should hide its implementation details by default.
- Make fields private, expose only what's necessary.

### Common Mistakes
| Anti-Pattern | Problem |
|---|---|
| Public fields | Anyone can corrupt state |
| Getter/Setter for everything | Defeats the purpose (anemic domain model) |
| Returning mutable collections | External code can modify internal state |
| Exposing implementation types | Locks you into specific implementation |

---

## 2. Abstraction

### What
Showing only essential features while hiding implementation complexity. Achieved via abstract classes and interfaces.

### Why It Matters
- Reduces cognitive load (use without understanding internals)
- Allows swapping implementations
- Defines contracts between components

### Real-World Analogy
**Car Steering Wheel**: You turn left/right (abstract interface). You don't need to know about rack-and-pinion, hydraulic fluid, or power steering pump (hidden implementation).

### When to Use
- When multiple implementations share a contract (interface)
- When you want to define a template with some steps deferred (abstract class)
- When hiding third-party library details behind your own interface

### Abstract Class vs Interface

| Aspect | Abstract Class | Interface |
|--------|---------------|-----------|
| State | Can have fields | No state (pre-Java 8) |
| Constructors | Yes | No |
| Multiple inheritance | No (single) | Yes (multiple) |
| Access modifiers | Any | Public (default) |
| Use when | Shared code + contract | Pure contract / capability |

### Common Mistakes
- Leaking abstraction (exposing internal details in method signatures)
- Over-abstracting (interfaces with one implementation)
- Wrong level of abstraction (too generic or too specific)

---

## 3. Inheritance

### What
A mechanism where a new class (child) derives properties and behavior from an existing class (parent), establishing an "is-a" relationship.

### Why It Matters
- Code reuse without duplication
- Establishes type hierarchies
- Enables polymorphism

### Real-World Analogy
**Biological Taxonomy**: A Dog IS-A Mammal IS-A Animal. Dog inherits characteristics (warm-blooded, has spine) but adds specifics (barks, fetches).

### When to Use
- True "is-a" relationship (Circle IS-A Shape)
- Shared behavior across a family of types
- Framework extension points (Template Method pattern)

### When NOT to Use (Favor Composition)
- "Has-a" relationship (Car HAS-A Engine, not Car IS-A Engine)
- Multiple unrelated behaviors (use interfaces)
- Deep hierarchies (>3 levels is a code smell)
- When you only need code reuse (use composition/delegation)

### Common Mistakes
- Inheriting for code reuse alone (breaks LSP)
- Deep inheritance hierarchies (fragile base class problem)
- Overriding methods in ways that break parent's contract

---

## 4. Polymorphism

### What
The ability of different objects to respond to the same message/method call in different ways. "One interface, many forms."

### Why It Matters
- Write generic code that works with any type in a hierarchy
- Add new types without changing existing code (Open/Closed Principle)
- Eliminates switch/if-else chains on type

### Real-World Analogy
**Universal Remote Control**: Same "power" button works on TV, AC, Speaker. Each device responds differently, but you use the same interface.

### Types
| Type | Mechanism | Resolved At |
|------|-----------|-------------|
| Compile-time | Method Overloading | Compile time |
| Runtime | Method Overriding | Runtime (vtable) |
| Parametric | Generics | Compile time |
| Coercion | Type casting | Compile time |

### Common Mistakes
- Confusing overloading with overriding
- Using `instanceof` checks (defeats polymorphism)
- Not programming to interfaces

---

## Comparison Table

| Principle | Purpose | Mechanism | Key Benefit |
|-----------|---------|-----------|-------------|
| Encapsulation | Hide data | private + methods | Prevent invalid state |
| Abstraction | Hide complexity | abstract/interface | Reduce cognitive load |
| Inheritance | Reuse code | extends/implements | Avoid duplication |
| Polymorphism | Flex behavior | overriding/overloading | Extensibility |

---

## Connection to SOLID Principles

| OOP Pillar | SOLID Principle | Connection |
|---|---|---|
| Encapsulation | Single Responsibility | Each class encapsulates one concern |
| Abstraction | Dependency Inversion | Depend on abstractions, not concretions |
| Inheritance | Liskov Substitution | Subtypes must be substitutable for parent |
| Polymorphism | Open/Closed | Open for extension via polymorphism |
| Abstraction | Interface Segregation | Small focused interfaces |

## Connection to Design Patterns

| Pattern | OOP Pillars Used |
|---------|-----------------|
| Strategy | Polymorphism + Abstraction |
| Template Method | Inheritance + Abstraction |
| Factory | Polymorphism + Encapsulation |
| Decorator | Inheritance + Polymorphism |
| Observer | Abstraction + Polymorphism |

---

## Interview Questions

### Encapsulation
1. How is encapsulation different from data hiding?
2. Why is returning `this.list` from a getter problematic? How do you fix it?
3. Can encapsulation exist without access modifiers? (Yes - closures in JS)
4. What is the difference between encapsulation and abstraction?

### Abstraction
1. When would you choose an abstract class over an interface?
2. Can you instantiate an abstract class? (No, but you can have constructors)
3. What is a "leaky abstraction"? Give an example.
4. How does abstraction relate to Dependency Inversion?

### Inheritance
1. Why is "favor composition over inheritance" a common guideline?
2. What is the diamond problem? How does Java solve it?
3. Explain the fragile base class problem.
4. Can a constructor be inherited? (No)
5. What's the difference between IS-A and HAS-A?

### Polymorphism
1. Can you achieve polymorphism without inheritance? (Yes - interfaces)
2. Why can't you override static methods?
3. What is method dispatch? Explain early vs late binding.
4. How does the JVM resolve which overridden method to call at runtime?
5. Write code that eliminates a switch statement using polymorphism.

---

## Running the Demo

```bash
cd /path/to/oops-principles
javac OOPSPrinciples.java
java OOPSPrinciples
```
