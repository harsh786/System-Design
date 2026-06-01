# State Design Pattern

## What Is It?

The State pattern allows an object to change its behavior when its internal state changes. Instead of using large conditional blocks (`if/else`, `switch`) to handle state-dependent behavior, each state is encapsulated in its own class that implements a common interface.

The object delegates behavior to its current state object, and state transitions happen **inside** the state objects themselves.

## When to Use

- Object behavior depends on its state and must change at runtime
- Operations have large conditional statements based on object state
- State transitions follow well-defined rules
- You want to make state transitions explicit and self-documenting

## Why Use It

- **Eliminates complex conditionals** - No more giant switch statements
- **Single Responsibility** - Each state class handles one state's behavior
- **Open/Closed** - Add new states without modifying existing ones
- **Explicit transitions** - State changes are clearly defined in code

## State Diagram: Vending Machine

```
                    insertCoin()
    ┌─────────┐ ──────────────────> ┌────────────┐
    │  IDLE   │                     │  HAS_COIN  │
    └─────────┘ <────────┐         └────────────┘
         ^               │               │
         │               │               │ selectProduct()
         │          stock > 0            ▼
         │               │         ┌─────────────┐
         │               └──────── │ DISPENSING   │
         │                         └─────────────┘
         │                               │
         │                          stock == 0
         │                               ▼
         │                       ┌──────────────┐
         └────── refill ──────── │ OUT_OF_STOCK │
                                 └──────────────┘
```

## State Diagram: Order Lifecycle

```
    ┌─────────┐  next()  ┌────────────┐  next()  ┌─────────┐  next()  ┌───────────┐
    │   NEW   │ ──────> │ PROCESSING │ ──────> │ SHIPPED │ ──────> │ DELIVERED │
    └─────────┘          └────────────┘          └─────────┘          └───────────┘
         │                     │
         │ cancel()            │ cancel()
         ▼                     ▼
    ┌───────────┐         ┌───────────┐
    │ CANCELLED │ <────── │ CANCELLED │
    └───────────┘         └───────────┘
```

## Real-World Use Cases

| Use Case | States | Transitions |
|----------|--------|-------------|
| **Vending Machine** | Idle, HasCoin, Dispensing, OutOfStock | Coin insert, product select, dispense |
| **TCP Connection** | Closed, Listen, SynSent, Established, CloseWait | Network events |
| **Media Player** | Stopped, Playing, Paused, Buffering | User controls |
| **Order Processing** | New, Processing, Shipped, Delivered, Cancelled | Business events |
| **Traffic Light** | Red, Yellow, Green | Timer-based |

## State vs Strategy Pattern

| Aspect | State | Strategy |
|--------|-------|----------|
| **Intent** | Behavior changes as internal state changes | Choose algorithm at runtime |
| **Who transitions?** | States transition themselves (internally) | Client sets strategy (externally) |
| **Awareness** | States know about each other | Strategies are independent |
| **Lifetime** | State changes throughout object's life | Usually set once or rarely changed |
| **Conditionals** | Replaces state-based conditionals | Replaces algorithm-based conditionals |

Key difference: In State, the **state objects decide** the next state. In Strategy, the **client decides** which strategy to use.

## Pros and Cons

### Pros
- Organizes state-specific code into separate classes
- Makes state transitions explicit
- Eliminates complex conditional logic
- Easy to add new states (Open/Closed Principle)
- Each state is independently testable

### Cons
- Can be overkill for simple state machines (2-3 states)
- Increases number of classes
- State transitions spread across state classes (harder to see full picture)
- Can lead to tight coupling between states if they know about each other

## When NOT to Use

- Only 2-3 simple states with trivial transitions (use enum + switch)
- State transitions are rare or the object's behavior barely changes
- The "states" don't actually change behavior, just data
- A simple boolean or enum flag would suffice
- State machine is better represented as a table/configuration

## Structure

```
┌──────────────┐         ┌─────────────────┐
│   Context    │────────>│   State (I)     │
│              │         ├─────────────────┤
│ -state       │         │ +handle(ctx)    │
│ +request()   │         └─────────────────┘
└──────────────┘                  △
                                  │
                 ┌────────────────┼────────────────┐
                 │                │                 │
        ┌────────────┐  ┌────────────┐   ┌────────────┐
        │  StateA    │  │  StateB    │   │  StateC    │
        │            │  │            │   │            │
        │ +handle()  │  │ +handle()  │   │ +handle()  │
        └────────────┘  └────────────┘   └────────────┘
```

## Running the Example

```bash
javac StatePattern.java
java StatePattern
```
