# Facade Design Pattern

## What is it?

The Facade pattern provides a **simplified, unified interface** to a complex subsystem. It doesn't encapsulate the subsystem — clients can still access subsystem classes directly if needed — but it offers a convenient default path for common operations.

## When to Use

- You need a simple interface to a complex subsystem
- There are many dependencies between clients and implementation classes
- You want to layer your subsystems (facade per layer)
- You want to decouple clients from subsystem internals

## Why Use It

- Reduces complexity for common use cases
- Promotes weak coupling between subsystem and clients
- Doesn't prevent advanced clients from using subsystem directly
- Simplifies porting/refactoring of subsystem internals

---

## Class Diagram (ASCII)

```
┌──────────────────────────────────────────────────┐
│                    Client                         │
└──────────────────────┬───────────────────────────┘
                       │ uses
                       ▼
┌──────────────────────────────────────────────────┐
│              ComputerFacade                       │
│──────────────────────────────────────────────────│
│ - cpu: CPU                                       │
│ - memory: Memory                                 │
│ - hardDrive: HardDrive                           │
│──────────────────────────────────────────────────│
│ + start(): void                                  │
│ + shutdown(): void                               │
└───┬──────────┬──────────┬────────────────────────┘
    │          │          │  delegates to
    ▼          ▼          ▼
┌───────┐ ┌────────┐ ┌───────────┐
│  CPU  │ │ Memory │ │ HardDrive │ ...
└───────┘ └────────┘ └───────────┘
   Complex Subsystem Classes
```

---

## Real-World Use Cases

| Example | Facade | Hides |
|---------|--------|-------|
| **JDBC** | `DriverManager.getConnection()` | Socket creation, protocol handshake, auth |
| **SLF4J** | `LoggerFactory.getLogger()` | Log4j/Logback/JUL binding complexity |
| **Spring Framework** | `JdbcTemplate` | Connection mgmt, statement creation, exception translation |
| **AWS SDK** | High-level `TransferManager` | Multipart upload, retries, threading |
| **Payment Gateways** | Stripe's `Charge.create()` | Tokenization, fraud checks, bank communication |

---

## Facade vs Adapter

| Aspect | Facade | Adapter |
|--------|--------|---------|
| **Intent** | Simplify interface | Make incompatible interfaces compatible |
| **Scope** | Wraps entire subsystem | Wraps single class |
| **Interface** | Defines new simplified API | Conforms to existing target interface |
| **Subsystem awareness** | Knows many classes | Knows one adaptee |

---

## Pros and Cons

### Pros
- Isolates clients from subsystem complexity
- Promotes weak coupling
- Doesn't restrict power users from accessing subsystem
- Single entry point simplifies testing and debugging

### Cons
- Can become a "god object" if too much logic accumulates
- Additional layer of indirection
- May hide important subsystem details that clients should know about
- Needs updating when subsystem changes

---

## When NOT to Use

- When clients genuinely need fine-grained control over every subsystem class
- When the subsystem is already simple (adding a facade adds unnecessary indirection)
- When you'd end up with a facade that just delegates 1:1 to a single class
- When it would prevent clients from handling errors at the appropriate granularity

---

## How to Run

```bash
javac FacadePattern.java
java FacadePattern
```
