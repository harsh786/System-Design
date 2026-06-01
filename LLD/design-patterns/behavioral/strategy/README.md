# Strategy Design Pattern

## What is it?

The Strategy pattern defines a family of algorithms, encapsulates each one, and makes them
interchangeable. It lets the algorithm vary independently from the clients that use it.

## When to Use

- You have multiple algorithms for a specific task and want to switch between them at runtime
- You want to avoid conditional statements (if/else, switch) for selecting behaviors
- You have related classes that differ only in their behavior
- You need to isolate business logic from implementation details of algorithms

## Why Use It

- **Open/Closed Principle**: Add new strategies without modifying existing code
- **Runtime flexibility**: Swap algorithms on the fly
- **Testability**: Each strategy is independently testable
- **Eliminates conditionals**: No more bloated switch/if-else blocks

---

## Class Diagram

```
+-------------------+          +---------------------+
|     Context       |          |   <<interface>>     |
|-------------------|          |     Strategy        |
| - strategy: Strategy -------->|---------------------|
|-------------------|          | + execute(data)     |
| + setStrategy()   |          +---------------------+
| + doWork()        |                  ^
+-------------------+                  |
                          +------------+------------+
                          |            |            |
                 +--------+--+ +------+----+ +-----+-------+
                 | ConcreteA  | | ConcreteB | | ConcreteC   |
                 |------------| |-----------| |-------------|
                 | + execute()| | + execute()| | + execute() |
                 +-----------+ +-----------+ +-------------+
```

---

## Real-World Use Cases

### 1. Payment Processing
Different payment methods (Credit Card, PayPal, Crypto, UPI) with a unified checkout interface.
The user selects the method at runtime.

### 2. Compression Algorithms
A file archiver that supports ZIP, RAR, 7z, TAR.GZ. Each format is a strategy.
The context picks the strategy based on user preference or file type.

### 3. Route Planning in Maps
Google Maps offers: fastest route, shortest distance, avoid tolls, public transit.
Each routing algorithm is a strategy applied to the same graph data.

### 4. Authentication Strategies
Passport.js (Node.js) uses strategies for OAuth, JWT, Local, SAML.
Each auth mechanism is pluggable without changing the core auth flow.

---

## Strategy vs State Pattern

| Aspect            | Strategy                          | State                              |
|-------------------|-----------------------------------|------------------------------------|
| **Intent**        | Select an algorithm               | Change behavior based on state     |
| **Who switches**  | Client sets the strategy          | Object transitions itself          |
| **Awareness**     | Strategies don't know each other  | States know about other states     |
| **Replaces**      | if/else for algorithm selection   | if/else for state-based behavior   |
| **Lifetime**      | Usually set once per operation    | Changes throughout object lifetime |
| **Example**       | Sorting algorithm selection       | TCP connection (Listen/Open/Close) |

---

## Pros and Cons

### Pros
- Algorithms are interchangeable at runtime
- Isolates algorithm code from context
- Open/Closed principle - easy to add new strategies
- Eliminates conditional logic
- Each strategy is unit-testable in isolation

### Cons
- Clients must be aware of different strategies to choose one
- Overhead if you only have a few algorithms that rarely change
- Increased number of classes/objects
- Functional languages can achieve the same with lambdas (pattern may be overkill)

---

## When NOT to Use

- You have only 2 algorithms and they won't change - a simple if/else is fine
- The algorithm never changes at runtime - just use the one you need directly
- The strategies need deep access to context internals (consider Template Method instead)
- You're in a functional language where passing functions achieves the same goal trivially

---

## Running the Demo

```bash
cd /path/to/strategy/
javac StrategyPattern.java
java StrategyPattern
```
