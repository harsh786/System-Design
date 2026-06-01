# Mediator Design Pattern

## What Is It?

The **Mediator** pattern defines an object (the mediator) that encapsulates how a set of objects (colleagues) interact. Instead of colleagues referring to each other directly, they communicate exclusively through the mediator, promoting loose coupling.

## When to Use

- Multiple objects communicate in complex but well-defined ways
- Reusing an object is difficult because it refers to many other objects
- You want to customize behavior distributed between several classes without subclassing all of them

## Why Use It

- Reduces chaotic dependencies between objects (N-to-N becomes N-to-1)
- Centralizes control logic in one place
- Makes individual components simpler and more reusable

---

## ASCII Class Diagram

```
        ┌──────────────────────┐
        │   <<interface>>      │
        │      Mediator        │
        ├──────────────────────┤
        │ + notify(sender,evt) │
        └──────────┬───────────┘
                   │ implements
                   ▼
        ┌──────────────────────┐         ┌───────────────────┐
        │  ConcreteMediator    │────────▶│  <<abstract>>     │
        │                      │ knows    │    Colleague      │
        │ - colleagueA         │         ├───────────────────┤
        │ - colleagueB         │         │ # mediator        │
        │                      │         │ + operation()     │
        │ + notify(sender,evt) │         └─────────┬─────────┘
        └──────────────────────┘                   │
                                          ┌────────┴────────┐
                                          ▼                 ▼
                                ┌─────────────┐   ┌─────────────┐
                                │ ColleagueA  │   │ ColleagueB  │
                                │             │   │             │
                                │ calls       │   │ calls       │
                                │ mediator.   │   │ mediator.   │
                                │  notify()   │   │  notify()   │
                                └─────────────┘   └─────────────┘

  Colleagues NEVER talk to each other directly.
  All communication goes through the Mediator.
```

---

## Real-World Use Cases

| Use Case | Mediator | Colleagues |
|----------|----------|------------|
| **Chat Room** | ChatRoom server | Users/Clients |
| **Air Traffic Control** | ATC tower | Aircraft |
| **UI Frameworks** | Dialog/Form controller | Buttons, TextFields, Checkboxes |
| **Message Brokers** | Kafka/RabbitMQ broker | Producers & Consumers |
| **MVC Controllers** | Controller | Model & View components |
| **Event Bus** | Event dispatcher | Event publishers & subscribers |
| **Middleware** | Express/Koa middleware chain | Request handlers |

---

## Mediator vs Observer

| Aspect | Mediator | Observer |
|--------|----------|----------|
| **Direction** | Bidirectional coordination | One-to-many notification |
| **Awareness** | Mediator knows all colleagues | Subject doesn't know observer details |
| **Purpose** | Reduce complex interconnections | Broadcast state changes |
| **Coupling** | Colleagues coupled to mediator only | Observers coupled to subject interface |
| **Control** | Centralized logic in mediator | Distributed (each observer reacts independently) |
| **Complexity** | Mediator can become a "god object" | Cascading updates can be hard to trace |

They can be combined: a Mediator can use Observer internally to listen to colleague events.

---

## Pros and Cons

### Pros

- **Single Responsibility** - Communication logic extracted into one place
- **Open/Closed** - New colleagues without changing existing ones
- **Reduced coupling** - Colleagues are independent of each other
- **Simplified protocols** - Many-to-many replaced with one-to-many
- **Easier to understand** - Flow of control is explicit in the mediator

### Cons

- **God Object risk** - Mediator can grow overly complex over time
- **Single point of failure** - Mediator becomes critical infrastructure
- **Indirection** - Harder to trace execution flow during debugging
- **Performance** - All communication funnels through one object

---

## When to Use

- Components in a GUI form depend on each other's state
- You notice tight coupling between many objects with complex interactions
- You want to reuse components in different contexts without modification
- A "control tower" metaphor fits your domain

## When NOT to Use

- Only two objects communicate (direct reference is simpler)
- Interactions are simple and unlikely to change
- The mediator would just delegate without adding coordination logic
- You need maximum performance (the extra indirection has overhead)
- The mediator would grow into an unmaintainable god class with hundreds of rules

---

## Running the Example

```bash
cd behavioral/mediator
javac MediatorPattern.java
java MediatorPattern
```
