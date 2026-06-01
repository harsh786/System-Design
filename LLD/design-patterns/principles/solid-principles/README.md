# SOLID Principles - Comprehensive Guide

## Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        SOLID PRINCIPLES                              │
├─────────────┬─────────────┬─────────────┬──────────────┬───────────┤
│      S      │      O      │      L      │      I       │     D     │
│  Single     │  Open/      │  Liskov     │  Interface   │ Dependency│
│  Responsi-  │  Closed     │  Substitu-  │  Segrega-    │ Inversion │
│  bility     │             │  tion       │  tion        │           │
├─────────────┼─────────────┼─────────────┼──────────────┼───────────┤
│ One class,  │ Extend,     │ Subtypes    │ Small, fo-   │ Depend on │
│ one reason  │ don't       │ replace     │ cused inter- │ abstrac-  │
│ to change   │ modify      │ base types  │ faces        │ tions     │
├─────────────┴─────────────┴─────────────┴──────────────┴───────────┤
│                                                                     │
│  S ──────► reduces coupling ──────► makes O easier                  │
│  O ──────► uses polymorphism ─────► requires L                      │
│  L ──────► proper contracts ──────► enforced by I                   │
│  I ──────► focused abstractions ──► enables D                       │
│  D ──────► loose coupling ────────► supports S                      │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## S - Single Responsibility Principle

**Definition:** A class should have only one reason to change.

**Explanation:** Each class encapsulates exactly one responsibility. If a class handles user registration AND email sending AND logging, changes to email logic force recompilation/redeployment of registration logic. Separate them so each can evolve independently.

**Real-world analogy:** A restaurant has a chef (cooking), waiter (serving), cashier (billing). You don't have one person doing all three - if the billing system changes, you don't retrain the chef.

**Code smell indicators:**
- Class has methods from unrelated domains (save + send + log)
- Class name contains "And" or "Manager" or "Handler" (does too much)
- Changes to one feature require modifying unrelated methods
- Class has 500+ lines
- Difficult to name the class without using generic terms

**Refactoring approach:**
1. List all responsibilities the class handles
2. Group related methods into cohesive sets
3. Extract each group into its own class
4. Use composition to coordinate them

**Connected patterns:** Facade, Mediator, Observer

**When to apply:** When a class has multiple reasons to change.
**Over-engineering:** Don't split a 20-line class into 5 classes with 4 lines each. If responsibilities always change together, they belong together.

---

## O - Open/Closed Principle

**Definition:** Software entities should be open for extension, closed for modification.

**Explanation:** You should be able to add new behavior without changing existing code. Use interfaces/abstract classes so new variants (shapes, discounts, strategies) are added by creating new classes, not editing if-else chains.

**Real-world analogy:** A power strip is closed for modification (you don't rewire it) but open for extension (you plug in new devices). Adding a new appliance doesn't require modifying the electrical system.

**Code smell indicators:**
- switch/if-else on type codes
- Methods that check `instanceof`
- Adding a feature requires modifying 5+ existing files
- Comments like "add new type here"

**Refactoring approach:**
1. Identify the varying behavior (what changes when you add a new type)
2. Extract an interface for that behavior
3. Create implementations for each variant
4. Replace conditionals with polymorphism

**Connected patterns:** Strategy, Template Method, Decorator, Factory

**When to apply:** When you've already needed to add a 3rd variant.
**Over-engineering:** Don't create interfaces for things that will never vary. YAGNI still applies.

---

## L - Liskov Substitution Principle

**Definition:** Objects of a superclass should be replaceable with objects of a subclass without breaking the program.

**Explanation:** If `S` is a subtype of `T`, then anywhere you use `T`, you should be able to use `S` without surprises. Subtypes must honor the contract: same preconditions (or weaker), same postconditions (or stronger), no new exceptions.

**Real-world analogy:** If a job posting requires "a vehicle that can carry 4 passengers", both a sedan and SUV work. A motorcycle violates the contract even though it's technically a vehicle.

**Code smell indicators:**
- Subclass throws `UnsupportedOperationException`
- Subclass overrides method to do nothing (empty body)
- Code checks `instanceof` before calling methods
- Unit tests for base class fail when run with subclass

**Refactoring approach:**
1. Identify what contract the base type promises
2. Check if all subtypes truly fulfill it
3. If not, restructure: use composition over inheritance, or split the hierarchy
4. Use interfaces to define proper capability groups

**Connected patterns:** Template Method, Strategy, Composite

**When to apply:** Every inheritance relationship must satisfy LSP. Always.
**Over-engineering:** N/A - this isn't something you "apply too much." It's a correctness criterion.

---

## I - Interface Segregation Principle

**Definition:** No client should be forced to depend on methods it does not use.

**Explanation:** Fat interfaces force implementors to provide dummy implementations. Split large interfaces into smaller, role-based ones. Clients depend only on the slice they need.

**Real-world analogy:** A TV remote with 100 buttons where you only use 5. Better to have a simple remote for basic users and an advanced one for power users.

**Code smell indicators:**
- Implementations throw `UnsupportedOperationException`
- Implementations have empty method bodies
- Interface has 10+ methods serving different clients
- Classes implement interfaces but only use half the methods

**Refactoring approach:**
1. Identify which clients use which methods
2. Group methods by client needs
3. Split into role-based interfaces
4. Classes implement multiple small interfaces as needed

**Connected patterns:** Adapter, Facade, Proxy

**When to apply:** When implementations are forced to have empty/throwing methods.
**Over-engineering:** Don't create single-method interfaces for everything. Group cohesive operations.

---

## D - Dependency Inversion Principle

**Definition:** High-level modules should not depend on low-level modules. Both should depend on abstractions.

**Explanation:** Instead of `OrderService` creating `new StripePayment()` internally, it depends on a `PaymentProcessor` interface. The concrete implementation is injected from outside. This makes the system testable, flexible, and loosely coupled.

**Real-world analogy:** A lamp doesn't care what power plant generates electricity. It depends on the "wall socket interface." You can switch from coal to solar power without rewiring the lamp.

**Code smell indicators:**
- `new ConcreteClass()` inside business logic
- Cannot unit test without hitting real database/network
- Changing one low-level class cascades changes upward
- Import statements reference concrete implementations

**Refactoring approach:**
1. Identify where high-level code creates/references concrete low-level code
2. Extract an interface representing what the high-level code needs
3. Make the high-level code depend on the interface
4. Inject the implementation via constructor, setter, or framework

**Connected patterns:** Factory, Abstract Factory, Strategy, Dependency Injection containers

**When to apply:** When you need testability, or when implementations might change.
**Over-engineering:** Simple utilities (String parsing, math) don't need interfaces. Don't abstract everything.

---

## Decision Flowchart

```
Is your class doing too many things?
├── YES → Violating SRP → Split responsibilities
└── NO
    ↓
Do you modify existing code to add new behavior?
├── YES → Violating OCP → Use polymorphism/strategy
└── NO
    ↓
Does a subclass break when substituted for parent?
├── YES → Violating LSP → Fix hierarchy or use composition
└── NO
    ↓
Are classes forced to implement unused methods?
├── YES → Violating ISP → Split the interface
└── NO
    ↓
Does high-level code directly instantiate low-level code?
├── YES → Violating DIP → Inject dependencies via interfaces
└── NO → You're following SOLID!
```

---

## SOLID Mapped to Design Patterns

| Principle | Patterns That Help |
|-----------|-------------------|
| SRP | Facade, Mediator, Observer, Command |
| OCP | Strategy, Decorator, Template Method, Factory Method |
| LSP | Template Method, Strategy, Composite |
| ISP | Adapter, Proxy, Facade |
| DIP | Abstract Factory, Strategy, Bridge, DI Containers |

---

## Anti-Patterns

| Principle | Anti-Pattern |
|-----------|-------------|
| SRP | God Class, Swiss Army Knife class |
| OCP | Shotgun Surgery (one change, many files modified) |
| LSP | Refused Bequest (subclass doesn't honor parent contract) |
| ISP | Fat Interface, Header Interface |
| DIP | Service Locator (hidden dependencies), `new` in constructors |

---

## Common Interview Questions

1. **Explain SRP with an example.** → UserService doing registration + email + logging = 3 reasons to change.
2. **How does OCP relate to Strategy pattern?** → Strategy lets you add new algorithms without modifying the context class.
3. **Why is Square extending Rectangle a violation of LSP?** → Client expects `setWidth(5); setHeight(3); area()==15`, but Square makes it 9.
4. **Give a real example of ISP violation.** → Java's `Serializable` is good ISP (marker). `javax.servlet.Servlet` forcing `init/destroy` on stateless servlets is borderline.
5. **What's the difference between DIP and Dependency Injection?** → DIP is the principle (depend on abstractions). DI is a technique to achieve it (constructor/setter injection).
6. **Which principle does the Factory pattern support?** → OCP (new types without modifying client) and DIP (client depends on interface, factory provides concrete).
7. **Can SOLID be over-applied?** → Yes. Premature abstraction adds complexity. Apply when you see actual need (3rd variant, testing difficulty, painful changes).

---

## Running the Demo

```bash
cd /path/to/solid-principles/
javac SOLIDPrinciples.java
java SOLIDPrinciples
```
