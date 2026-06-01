# Bridge Design Pattern

## What Is It?

The Bridge pattern decouples an **abstraction** from its **implementation** so that the two can vary independently. Instead of using inheritance to bind abstraction and implementation together, it uses composition — the abstraction holds a reference to an implementor object.

## When to Use

- You want to avoid a permanent binding between abstraction and implementation
- Both abstraction and implementation should be extensible via subclassing
- You'd otherwise face a class explosion (e.g., 3 shapes x 4 colors = 12 classes without Bridge)
- You need to switch implementations at runtime

## Why Use It

Without Bridge, combining M abstractions with N implementations requires M×N classes. With Bridge, you only need M + N classes.

## Class Diagram

```
         ┌─────────────────┐          ┌──────────────────┐
         │   Abstraction   │          │   Implementor    │
         │─────────────────│          │  (interface)     │
         │ - impl: Impl ───┼─────────>│──────────────────│
         │ + operation()   │          │ + operationImpl()│
         └────────┬────────┘          └────────┬─────────┘
                  │                             │
         ┌───────┴────────┐          ┌─────────┴─────────┐
         │   Refined       │          │  ConcreteImplA    │
         │   Abstraction   │          ├───────────────────┤
         │─────────────────│          │ + operationImpl() │
         │ + extendedOp()  │          └───────────────────┘
         └─────────────────┘          ┌───────────────────┐
                                      │  ConcreteImplB    │
                                      ├───────────────────┤
                                      │ + operationImpl() │
                                      └───────────────────┘
```

**Shape + Color example:**
```
  Shape (abstract)  ─────────────>  Color (interface)
    │                                  │
    ├── Circle                         ├── Red
    ├── Square                         ├── Blue
    └── Triangle                       └── Green
```

## Real-World Use Cases

### 1. JDBC Drivers
- **Abstraction:** `java.sql.DriverManager` / `Connection` / `Statement`
- **Implementor:** Database-specific drivers (MySQL, PostgreSQL, Oracle)
- Your code uses the JDBC API; the driver implements it for a specific DB

### 2. Remote Controls
- **Abstraction:** Remote (basic, advanced, voice-controlled)
- **Implementor:** Device (TV, Radio, Smart Speaker, AC)
- Any remote type can control any device type

### 3. Cross-Platform Rendering
- **Abstraction:** UI components (Button, Window, TextBox)
- **Implementor:** Platform renderer (Windows, macOS, Linux, Web)
- Java AWT uses this pattern with peer classes

### 4. Messaging Systems
- **Abstraction:** Message types (TextMessage, EmailMessage, PushNotification)
- **Implementor:** Delivery channel (SMS gateway, SMTP server, Firebase)

## Bridge vs Adapter

| Aspect         | Bridge                              | Adapter                         |
|----------------|-------------------------------------|---------------------------------|
| **Intent**     | Design upfront to vary independently| Retrofit incompatible interfaces|
| **When**       | During design                       | After design (legacy code)      |
| **Structure**  | Abstraction + Implementor hierarchy | Wraps existing class            |
| **Goal**       | Prevent class explosion             | Make things work together       |

## Pros and Cons

### Pros
- Open/Closed Principle — extend abstraction and implementation independently
- Single Responsibility — separate high-level logic from platform details
- Runtime switching of implementations
- Hides implementation details from client
- Avoids class explosion (M + N instead of M × N)

### Cons
- Increased complexity for simple cases
- More indirection (harder to debug/trace)
- Requires identifying the two independent dimensions upfront

## When NOT to Use

- Only one implementation exists and won't change
- The abstraction and implementation are tightly coupled by nature
- Simple cases where inheritance is clearer
- When the indirection cost outweighs the flexibility benefit
