# Design Patterns in Java - Complete Reference

A comprehensive implementation of all 23 Gang of Four (GoF) design patterns in Java with runnable programs, real-world examples, and detailed explanations.

## Foundations (Start Here)

| Section | Path | What You'll Learn |
|---------|------|-------------------|
| **OOP Principles** | `principles/oops-principles/` | Encapsulation, Abstraction, Inheritance, Polymorphism |
| **SOLID Principles** | `principles/solid-principles/` | SRP, OCP, LSP, ISP, DIP with before/after examples |
| **Relationships** | `principles/relationships/` | Association, Aggregation, Composition, Dependency, Realization |

---

## Overview Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         DESIGN PATTERNS (GoF - 23)                          │
├─────────────────────┬──────────────────────┬────────────────────────────────┤
│                     │                      │                                │
│   CREATIONAL (5)    │   STRUCTURAL (7)     │      BEHAVIORAL (11)           │
│   ─────────────     │   ──────────────     │      ──────────────            │
│                     │                      │                                │
│   • Singleton       │   • Adapter          │   • Strategy                   │
│   • Factory Method  │   • Bridge           │   • Observer                   │
│   • Abstract Factory│   • Composite        │   • Command                    │
│   • Builder         │   • Decorator        │   • State                      │
│   • Prototype       │   • Facade           │   • Template Method            │
│                     │   • Flyweight        │   • Iterator                   │
│                     │   • Proxy            │   • Mediator                   │
│                     │                      │   • Memento                    │
│                     │                      │   • Chain of Responsibility    │
│                     │                      │   • Visitor                    │
│                     │                      │   • Interpreter                │
│                     │                      │                                │
├─────────────────────┼──────────────────────┼────────────────────────────────┤
│ HOW objects are     │ HOW objects are      │ HOW objects communicate        │
│ created             │ composed/structured  │ and distribute responsibility  │
└─────────────────────┴──────────────────────┴────────────────────────────────┘
```

---

## Pattern Relationships Diagram

```
                              ┌──────────────┐
                    ┌────────►│   Abstract   │◄────────┐
                    │         │   Factory    │         │
                    │         └──────────────┘         │
                    │                │                  │
              creates families      │ uses        often implements
                    │               ▼                   │
              ┌─────┴─────┐  ┌──────────┐      ┌──────┴──────┐
              │  Factory   │  │Singleton │      │  Prototype  │
              │  Method    │  └──────────┘      └─────────────┘
              └───────────┘
                    │
                    │ creates objects ──────────► ┌──────────┐
                    │                             │ Builder  │
                    └────────────────────────────►└──────────┘

              ┌──────────┐    ┌───────────┐    ┌──────────────┐
              │ Adapter  │    │  Bridge   │    │  Composite   │
              └────┬─────┘    └─────┬─────┘    └──────┬───────┘
                   │                │                   │
                   │  ┌─────────┐   │  ┌──────────┐    │  ┌──────────┐
                   ├─►│Decorator│   ├─►│  Facade  │    └─►│ Iterator │
                   │  └─────────┘   │  └──────────┘       └──────────┘
                   │                │
                   │  ┌─────────┐   │  ┌──────────┐    ┌──────────────────┐
                   └─►│  Proxy  │   └─►│Flyweight │    │Chain of Resp.    │
                      └─────────┘      └──────────┘    └────────┬─────────┘
                                                                │
              ┌──────────┐    ┌───────────┐    ┌────────┐       │
              │ Command  │    │  State    │    │Strategy│       │
              └────┬─────┘    └─────┬─────┘    └────┬───┘       │
                   │                │               │           │
                   │uses            │ similar       │           │
                   ▼                ▼               ▼           ▼
              ┌──────────┐    ┌───────────┐    ┌──────────────────┐
              │ Memento  │    │ Mediator  │    │    Observer      │
              └──────────┘    └───────────┘    └──────────────────┘

              ┌──────────┐    ┌───────────┐    ┌──────────────────┐
              │ Visitor  │    │ Template  │    │   Interpreter    │
              │          │    │  Method   │    │                  │
              └──────────┘    └───────────┘    └──────────────────┘
```

---

## Quick Reference Table

| Pattern | Category | Purpose | Key Use Case |
|---------|----------|---------|--------------|
| **Singleton** | Creational | Ensure single instance | DB Connection Pool, Logger |
| **Factory Method** | Creational | Delegate instantiation to subclasses | Notification systems |
| **Abstract Factory** | Creational | Create families of related objects | Cross-platform UI |
| **Builder** | Creational | Construct complex objects step by step | HTTP Request builder |
| **Prototype** | Creational | Clone existing objects | Document templates |
| **Adapter** | Structural | Make incompatible interfaces work together | Legacy integration |
| **Bridge** | Structural | Separate abstraction from implementation | JDBC drivers |
| **Composite** | Structural | Treat tree structures uniformly | File systems, Menus |
| **Decorator** | Structural | Add behavior dynamically | Java I/O streams |
| **Facade** | Structural | Simplify complex subsystems | API wrappers |
| **Flyweight** | Structural | Share common state efficiently | String pool, Game sprites |
| **Proxy** | Structural | Control access to objects | Lazy loading, Caching |
| **Strategy** | Behavioral | Swap algorithms at runtime | Payment processing |
| **Observer** | Behavioral | Notify dependents of state changes | Event systems, MVC |
| **Command** | Behavioral | Encapsulate requests as objects | Undo/Redo, Task queues |
| **State** | Behavioral | Alter behavior when state changes | Vending machines, Orders |
| **Template Method** | Behavioral | Define algorithm skeleton | Data processing pipelines |
| **Iterator** | Behavioral | Sequential access without exposing internals | Collection traversal |
| **Mediator** | Behavioral | Centralize complex communication | Chat rooms, ATC |
| **Memento** | Behavioral | Capture and restore state | Game saves, Undo |
| **Chain of Responsibility** | Behavioral | Pass request along handler chain | Middleware, Filters |
| **Visitor** | Behavioral | Add operations without modifying classes | AST processing |
| **Interpreter** | Behavioral | Evaluate language grammar | SQL parsers, Rule engines |

---

## Directory Structure

```
design-patterns/
├── README.md (this file)
├── principles/
│   ├── oops-principles/
│   │   ├── OOPSPrinciples.java
│   │   └── README.md
│   ├── solid-principles/
│   │   ├── SOLIDPrinciples.java
│   │   └── README.md
│   └── relationships/
│       ├── Relationships.java
│       └── README.md
├── creational/
│   ├── singleton/
│   │   ├── SingletonPattern.java
│   │   └── README.md
│   ├── factory-method/
│   │   ├── FactoryMethodPattern.java
│   │   └── README.md
│   ├── abstract-factory/
│   │   ├── AbstractFactoryPattern.java
│   │   └── README.md
│   ├── builder/
│   │   ├── BuilderPattern.java
│   │   └── README.md
│   └── prototype/
│       ├── PrototypePattern.java
│       └── README.md
├── structural/
│   ├── adapter/
│   │   ├── AdapterPattern.java
│   │   └── README.md
│   ├── bridge/
│   │   ├── BridgePattern.java
│   │   └── README.md
│   ├── composite/
│   │   ├── CompositePattern.java
│   │   └── README.md
│   ├── decorator/
│   │   ├── DecoratorPattern.java
│   │   └── README.md
│   ├── facade/
│   │   ├── FacadePattern.java
│   │   └── README.md
│   ├── flyweight/
│   │   ├── FlyweightPattern.java
│   │   └── README.md
│   └── proxy/
│       ├── ProxyPattern.java
│       └── README.md
└── behavioral/
    ├── strategy/
    │   ├── StrategyPattern.java
    │   └── README.md
    ├── observer/
    │   ├── ObserverPattern.java
    │   └── README.md
    ├── command/
    │   ├── CommandPattern.java
    │   └── README.md
    ├── state/
    │   ├── StatePattern.java
    │   └── README.md
    ├── template-method/
    │   ├── TemplateMethodPattern.java
    │   └── README.md
    ├── iterator/
    │   ├── IteratorPattern.java
    │   └── README.md
    ├── mediator/
    │   ├── MediatorPattern.java
    │   └── README.md
    ├── memento/
    │   ├── MementoPattern.java
    │   └── README.md
    ├── chain-of-responsibility/
    │   ├── ChainOfResponsibilityPattern.java
    │   └── README.md
    ├── visitor/
    │   ├── VisitorPattern.java
    │   └── README.md
    └── interpreter/
        ├── InterpreterPattern.java
        └── README.md
```

---

## How to Run

Each pattern has a standalone Java file with a `main` method. To compile and run:

```bash
# Navigate to any pattern directory
cd creational/singleton/

# Compile
javac SingletonPattern.java

# Run
java SingletonPattern
```

---

## Pattern Selection Guide

```
Need to create objects?
├── One instance only? ──────────────────────► Singleton
├── Don't know exact type at compile time? ──► Factory Method
├── Family of related objects? ──────────────► Abstract Factory
├── Complex object, many configurations? ────► Builder
└── Clone existing objects? ─────────────────► Prototype

Need to compose objects?
├── Make incompatible things work together? ─► Adapter
├── Vary abstraction AND implementation? ────► Bridge
├── Tree structure, uniform treatment? ──────► Composite
├── Add behavior without subclassing? ───────► Decorator
├── Simplify a complex subsystem? ───────────► Facade
├── Too many similar objects (memory)? ──────► Flyweight
└── Control access to an object? ────────────► Proxy

Need to manage behavior/communication?
├── Swap algorithms at runtime? ─────────────► Strategy
├── Notify many objects of changes? ─────────► Observer
├── Encapsulate request + undo/redo? ────────► Command
├── Object behavior depends on state? ───────► State
├── Same algorithm, different steps? ────────► Template Method
├── Traverse collection without internals? ──► Iterator
├── Reduce coupling between components? ─────► Mediator
├── Save/restore object state? ──────────────► Memento
├── Pass request through handler chain? ─────► Chain of Responsibility
├── Add operations to stable structures? ────► Visitor
└── Evaluate a grammar/language? ────────────► Interpreter
```

---

## SOLID Principles & Design Patterns Mapping

| SOLID Principle | Related Patterns |
|----------------|-----------------|
| **S**ingle Responsibility | Facade, Mediator, Command |
| **O**pen/Closed | Strategy, Decorator, Observer, Visitor |
| **L**iskov Substitution | Factory Method, Template Method |
| **I**nterface Segregation | Adapter, Proxy, Bridge |
| **D**ependency Inversion | Abstract Factory, Strategy, Observer, Bridge |

---

## When NOT to Use Patterns

- **Don't over-engineer**: If simple code works, keep it simple
- **Don't use patterns for the sake of patterns**: They should solve a real problem
- **Don't force a pattern**: If it doesn't fit naturally, it will add complexity
- **Premature abstraction**: Wait until you see the need (Rule of Three)

> "The best code is no code at all. The second best is code that's so simple it obviously has no bugs."
> — Every senior developer ever

---

## Study Order (Recommended)

### Start Here (Most Common):
1. Strategy → Observer → Factory Method → Decorator → Singleton

### Then (Architecture Patterns):
2. Builder → Adapter → Facade → Template Method → Command

### Then (Advanced):
3. State → Proxy → Composite → Chain of Responsibility → Iterator

### Finally (Specialized):
4. Abstract Factory → Bridge → Flyweight → Mediator → Memento → Visitor → Prototype → Interpreter
