# Adapter Design Pattern

## What is it?

The Adapter pattern converts the interface of a class into another interface that clients expect. It lets classes work together that couldn't otherwise because of incompatible interfaces. Think of it like a power plug adapter when traveling abroad.

## When to Use

- Integrating with legacy systems that can't be modified
- Wrapping third-party libraries behind a stable interface
- Unifying multiple services with different APIs (e.g., payment gateways)
- Converting data formats between systems

## When NOT to Use

- Interfaces are already compatible (unnecessary complexity)
- You can modify the source code of the adaptee directly
- You need to add new behavior (use Decorator instead)
- The interface mismatch is too large (consider a full rewrite)

---

## Class Diagrams

### Object Adapter (Composition)

```
┌─────────────────┐         ┌─────────────────────┐
│     Client      │         │   <<interface>>      │
│                 │────────▶│      Target          │
│                 │         │─────────────────────│
└─────────────────┘         │ + request()          │
                            └──────────┬──────────┘
                                       │ implements
                            ┌──────────┴──────────┐
                            │      Adapter         │
                            │─────────────────────│
                            │ - adaptee: Adaptee   │──────────┐
                            │─────────────────────│          │
                            │ + request() {        │          │ has-a
                            │   adaptee.specific() │          │
                            │ }                    │          ▼
                            └─────────────────────┘  ┌──────────────┐
                                                     │   Adaptee    │
                                                     │──────────────│
                                                     │+ specificReq()│
                                                     └──────────────┘
```

### Class Adapter (Inheritance)

```
┌──────────────────┐        ┌─────────────────────┐
│     Client       │        │   <<interface>>      │
│                  │───────▶│      Target          │
│                  │        │─────────────────────│
└──────────────────┘        │ + request()          │
                            └──────────┬──────────┘
                                       │ implements
                            ┌──────────┴──────────┐
                            │      Adapter         │
                            │─────────────────────│
         ┌──────────────┐   │ + request() {        │
         │   Adaptee    │   │   this.specificReq() │
         │──────────────│◁──│ }                    │
         │+ specificReq()│   └─────────────────────┘
         └──────────────┘        extends (inherits)
```

---

## Object Adapter vs Class Adapter

| Aspect              | Object Adapter          | Class Adapter             |
|---------------------|-------------------------|---------------------------|
| Mechanism           | Composition (has-a)     | Inheritance (is-a)        |
| Flexibility         | Can adapt subclasses    | Tied to one concrete class|
| Multiple adaptees   | Yes (hold references)   | No (single inheritance)   |
| Override behavior   | Must delegate           | Can override directly     |
| Language support    | All OOP languages       | Needs multiple inheritance|
| **Preferred?**      | **Yes, generally**      | Use when overriding needed|

---

## Real-World Use Cases

1. **Legacy System Integration** - Wrapping a COBOL mainframe behind a REST interface
2. **Third-Party Libraries** - Adapting logging frameworks (SLF4J adapts Log4j, Logback, JUL)
3. **Payment Gateways** - Unified interface over PayPal, Stripe, Square APIs
4. **Data Format Converters** - XML-to-JSON adapters, Protocol Buffers to POJO
5. **Database Drivers** - JDBC adapts different database protocols to one interface
6. **UI Frameworks** - RecyclerView.Adapter in Android adapts data to view

---

## Pros and Cons

### Pros
- **Single Responsibility** - Separates interface conversion from business logic
- **Open/Closed Principle** - Add new adapters without changing existing code
- **Reusability** - Use existing classes despite interface incompatibility
- **Testability** - Easy to mock adapters in unit tests

### Cons
- **Increased complexity** - Extra layer of indirection
- **Many small classes** - One adapter per adaptee can proliferate
- **Performance overhead** - Extra delegation (usually negligible)

---

## How to Run

```bash
javac AdapterPattern.java
java AdapterPattern
```
