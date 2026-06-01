# Observer Design Pattern

## What Is It?

The Observer pattern defines a **one-to-many dependency** between objects. When a subject (publisher) changes state, all registered observers (subscribers) are notified automatically.

It decouples the subject from its observers -- the subject doesn't need to know *what* the observers do, only that they implement the observer interface.

## When to Use

- When changes to one object require updating others, and you don't know how many objects need updating
- When an object should notify other objects without making assumptions about who they are
- When you need event-driven architecture with loose coupling

## Why Use It

- **Loose coupling**: Subject and observers can vary independently
- **Open/Closed Principle**: Add new observers without modifying the subject
- **Dynamic relationships**: Subscribe/unsubscribe at runtime

---

## Class Diagram (ASCII)

```
┌─────────────────────┐         ┌──────────────────────┐
│   <<interface>>     │         │    <<interface>>      │
│   Subject           │         │    Observer           │
├─────────────────────┤         ├──────────────────────┤
│ +subscribe(obs)     │         │ +update(data)        │
│ +unsubscribe(obs)   │◇───────▶│                      │
│ +notifyObservers()  │   1..*  └──────────────────────┘
└────────┬────────────┘                    ▲
         │                                 │
         │ implements                      │ implements
         ▼                                 │
┌─────────────────────┐         ┌──────────┴───────────┐
│  ConcreteSubject    │         │  ConcreteObserverA   │
├─────────────────────┤         ├──────────────────────┤
│ -state              │         │ +update(data)        │
│ -observers: List    │         └──────────────────────┘
│ +setState()         │         ┌──────────────────────┐
│ +getState()         │         │  ConcreteObserverB   │
└─────────────────────┘         ├──────────────────────┤
                                │ +update(data)        │
                                └──────────────────────┘
```

---

## Real-World Use Cases

| Use Case | Subject | Observer |
|----------|---------|----------|
| GUI Event Systems | Button/Widget | Event Handlers |
| MVC Architecture | Model | View(s) |
| Message Queues | Topic/Queue | Subscribers |
| Social Media | User/Post | Followers |
| Stock Tickers | Exchange | Trading apps, dashboards |
| Pub/Sub Systems | Event Bus | Microservices |
| DOM Events | Element | addEventListener callbacks |

---

## Push vs Pull Model

### Push Model
Subject sends detailed data in the notification:
```java
observer.update(stockSymbol, price, volume, timestamp);
```
- Observer gets everything immediately
- May send data observers don't need
- Coupling: subject must know what observers need

### Pull Model
Subject sends minimal notification; observer pulls what it needs:
```java
observer.update(subject);  // observer calls subject.getState()
```
- Observer fetches only what it needs
- Extra call back to subject
- Less coupling between subject and observer

---

## Pros and Cons

### Pros
- Open/Closed Principle -- new subscribers without modifying publisher
- Loose coupling between subject and observers
- Dynamic relationships established at runtime
- Supports broadcast communication
- Foundation for event-driven and reactive systems

### Cons
- Observers notified in unpredictable order
- Memory leaks if observers aren't unsubscribed (lapsed listener problem)
- Cascade updates can cause performance issues
- Debugging is harder (indirect communication)
- Can lead to unexpected circular updates

---

## When NOT to Use

- When there's only one observer that never changes (direct reference is simpler)
- When synchronous notification causes performance problems (consider async/event queue)
- When observers need guaranteed ordering (use Chain of Responsibility instead)
- When the update logic is trivial and coupling is acceptable
- In simple applications where the overhead of interfaces adds no value

---

## Running the Code

```bash
javac ObserverPattern.java && java ObserverPattern
```
