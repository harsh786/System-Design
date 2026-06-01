# Command Design Pattern

## What is it?

The Command pattern encapsulates a request as an object, letting you parameterize clients with different requests, queue or log requests, and support undoable operations. It decouples the object that invokes the operation from the one that knows how to perform it.

## When to Use

- You need undo/redo functionality
- You want to queue, schedule, or log operations
- You need to parameterize objects with operations
- You want to support macro commands (composite commands)
- You need transactional behavior (execute/rollback)

## Why Use It

- **Decoupling**: Invoker doesn't know about receiver implementation
- **Extensibility**: Add new commands without changing existing code (Open/Closed)
- **Composability**: Combine commands into macros
- **History**: Track and reverse executed operations

## Class Diagram (ASCII)

```
    ┌─────────────┐         ┌──────────────────┐
    │   Client    │────────▶│     Invoker      │
    └─────────────┘         │  (RemoteControl) │
           │                │                  │
           │                │ - commands[]     │
           │                │ - history        │
           │                │ + pressOn()      │
           │                │ + pressUndo()    │
           │                └───────┬──────────┘
           │                        │ calls execute()/undo()
           ▼                        ▼
    ┌─────────────────────────────────────┐
    │         <<interface>>               │
    │            Command                  │
    │                                     │
    │  + execute(): void                  │
    │  + undo(): void                     │
    └──────────┬──────────────────────────┘
               │ implements
       ┌───────┼────────┬────────────┐
       ▼       ▼        ▼            ▼
  ┌────────┐┌────────┐┌──────────┐┌────────────┐
  │LightOn ││FanSpeed││Thermostat││MacroCommand│
  │Command ││Command ││Command   ││            │
  └───┬────┘└───┬────┘└────┬─────┘└────────────┘
      │         │          │
      ▼         ▼          ▼
  ┌────────┐┌────────┐┌───────────┐
  │ Light  ││  Fan   ││Thermostat │  ← Receivers
  │        ││        ││           │
  │+ on()  ││+setSpd ││+setTemp() │
  │+ off() ││        ││           │
  └────────┘└────────┘└───────────┘
```

## Real-World Use Cases

| Use Case | Command | Receiver | Invoker |
|----------|---------|----------|---------|
| GUI Buttons | ButtonClickCommand | Application logic | Button/MenuItem |
| Transaction Systems | TransferFundsCommand | BankAccount | TransactionProcessor |
| Task Queues | JobCommand | Worker service | JobScheduler |
| Macro Recording | MacroCommand | Various receivers | Macro player |
| Text Editors | TypeCommand, DeleteCommand | Document/Buffer | Editor UI |
| Game Input | MoveCommand, AttackCommand | Character | InputHandler |
| Database Migrations | MigrateUpCommand | Database | Migration runner |

## Command vs Strategy

| Aspect | Command | Strategy |
|--------|---------|----------|
| Intent | Encapsulate a request with undo | Encapsulate an algorithm |
| Focus | **What** to do (action + receiver) | **How** to do something |
| State | Stores receiver + parameters + prev state | Usually stateless |
| Undo | Core feature | Not applicable |
| History | Commands are often queued/logged | Single active strategy |
| Example | "Turn light on" | "Sort using quicksort" |

## Pros and Cons

### Pros
- Single Responsibility: decouple invocation from execution
- Open/Closed: add new commands without modifying invoker
- Undo/Redo support built-in
- Commands can be composed (macros), queued, serialized
- Supports logging and auditing

### Cons
- Increases number of classes (one per action)
- Can be overkill for simple operations
- Memory overhead if storing large undo histories
- Complexity for very simple request/response flows

## When NOT to Use

- Simple direct method calls with no need for undo/queue/log
- When the overhead of command objects outweighs the benefit
- If operations are trivially simple and never need to be reversed
- When the system has no requirement for decoupling sender/receiver

## Running the Example

```bash
cd command/
javac CommandPattern.java
java CommandPattern
```
