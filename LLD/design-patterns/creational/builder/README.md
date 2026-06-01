# Builder Design Pattern

## What is it?

The Builder pattern separates the **construction** of a complex object from its **representation**. It allows constructing objects step-by-step, producing different types and representations using the same construction code.

## When to Use

- Object has **many parameters** (especially optional ones) - "telescoping constructor" problem
- Object construction requires **multiple steps** that must happen in a specific order
- You need to create **different representations** of the same type of object
- You want **immutable objects** that are complex to construct

## When NOT to Use

- Object is simple (few parameters, no optional fields)
- Only one representation exists - adds unnecessary complexity
- Object can change after construction (mutable) - just use setters
- Performance-critical code where builder overhead matters

## Class Diagram

```
┌─────────────────┐         ┌──────────────────────┐
│    Director     │         │    <<interface>>      │
├─────────────────┤         │     HouseBuilder     │
│                 │ uses    ├──────────────────────┤
│ + construct()───┼────────►│ + buildFoundation()  │
│                 │         │ + buildStructure()   │
└─────────────────┘         │ + buildRoof()        │
                            │ + getResult(): House │
                            └──────────┬───────────┘
                                       │ implements
                         ┌─────────────┴─────────────┐
                         │                           │
              ┌──────────┴────────┐      ┌───────────┴───────────┐
              │ ModernHouseBuilder│      │ VictorianHouseBuilder  │
              ├───────────────────┤      ├───────────────────────┤
              │ - house: House    │      │ - house: House        │
              │ + buildFound...() │      │ + buildFound...()     │
              │ + getResult()     │      │ + getResult()         │
              └───────────────────┘      └───────────────────────┘

  Fluent Builder (inner class):
  ┌─────────────────────────────────────┐
  │           HttpRequest               │
  ├─────────────────────────────────────┤
  │ - final method, url, headers, ...   │
  │ - HttpRequest(Builder)              │
  ├─────────────────────────────────────┤
  │  ┌───────────────────────────────┐  │
  │  │     static class Builder      │  │
  │  ├───────────────────────────────┤  │
  │  │ + header(): Builder           │  │
  │  │ + body(): Builder             │  │
  │  │ + timeout(): Builder          │  │
  │  │ + build(): HttpRequest        │  │
  │  └───────────────────────────────┘  │
  └─────────────────────────────────────┘
```

## Real-World Use Cases

| Use Case | Example |
|----------|---------|
| **StringBuilder** | `new StringBuilder().append("Hello").append(" World").toString()` |
| **HTTP Clients** | OkHttp `Request.Builder`, Java `HttpRequest.newBuilder()` |
| **Query Builders** | JPA CriteriaBuilder, JOOQ, QueryDSL |
| **UI Components** | AlertDialog.Builder in Android |
| **Config Objects** | Retrofit.Builder, Gson/Jackson ObjectMapper |
| **Protocol Buffers** | `Person.newBuilder().setName("John").build()` |

## Pros and Cons

### Pros
- Eliminates telescoping constructors
- Produces **immutable** objects easily
- Same construction process, **different representations**
- Fine control over construction steps
- Single Responsibility: separates construction logic from business logic

### Cons
- Code verbosity (extra Builder class per product)
- Requires creating a separate builder for each product type
- Fields must be duplicated between product and builder
- Mutable builder != thread-safe (the built product can be immutable though)

## Two Flavors

| Classic (GoF) | Fluent (Effective Java) |
|---------------|------------------------|
| Director orchestrates | Client chains methods |
| Multiple builder impls | Single inner Builder class |
| Different representations | One type, many optional params |
| Builder methods return void | Methods return `this` |

## Compile & Run

```bash
javac BuilderPattern.java && java BuilderPattern
```
