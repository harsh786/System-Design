# Java Concepts Applied To LLD

This section connects Java language features to common LLD design decisions.

## SOLID Quick Map

| Principle | Meaning | Java concept |
|---|---|---|
| Single Responsibility | One reason to change | Small classes, cohesive methods |
| Open/Closed | Extend behavior without modifying stable code | interfaces, polymorphism, strategy |
| Liskov Substitution | Subtypes must behave like parent type | careful inheritance |
| Interface Segregation | Small focused interfaces | role-specific interfaces |
| Dependency Inversion | Depend on abstractions | constructor injection, interfaces |

## Composition Over Inheritance

Inheritance:

```java
class EmailNotification extends Notification {
}
```

Composition:

```java
class NotificationService {
    private final NotificationSender sender;
}
```

Composition is usually better in LLD because you can swap implementations without creating a fragile class hierarchy.

## Strategy Pattern

Use when behavior varies.

```java
interface PricingStrategy {
    Money price(Order order);
}

class RegularPricing implements PricingStrategy {
    public Money price(Order order) {
        return order.total();
    }
}
```

Java concepts used:

- interface
- polymorphism
- composition

## Factory Pattern

Use when object creation has rules.

```java
class PaymentProcessorFactory {
    PaymentProcessor processorFor(PaymentMethod method) {
        return switch (method) {
            case CARD -> new CardProcessor();
            case CASH -> new CashProcessor();
        };
    }
}
```

Java concepts used:

- enum
- interface
- switch expression

## Builder Pattern

Use when an object has many optional fields or needs readable construction.

```java
User user = new User.Builder()
    .id("u1")
    .email("a@example.com")
    .build();
```

Java concepts used:

- static nested class
- private constructor
- fluent methods

## Observer Pattern

Use when one event triggers multiple independent reactions.

```java
interface OrderListener {
    void onOrderPlaced(Order order);
}
```

Java concepts used:

- interface
- `List<OrderListener>`
- lambdas

## State Pattern

Use when behavior depends on current state.

```java
interface OrderState {
    OrderState pay();
    OrderState cancel();
}
```

Java concepts used:

- interface
- polymorphism
- enum or sealed types

## Repository Pattern

Use to hide persistence details.

```java
interface UserRepository {
    Optional<User> findById(UserId id);
    void save(User user);
}
```

Java concepts used:

- interface
- `Optional`
- immutable ID value object
- map-backed fake implementation for tests

## Choosing Collections In LLD

| Problem | Recommended collection |
|---|---|
| Find entity by ID | `Map<Id, Entity>` |
| Preserve creation order | `LinkedHashMap` or `ArrayList` |
| Prevent duplicate members | `Set<MemberId>` |
| Need sorted range lookup | `TreeMap` or `TreeSet` |
| Need next highest priority task | `PriorityQueue` |
| Need FIFO job processing | `Queue` or `BlockingQueue` |
| Need undo/redo | `Deque<Command>` |
| Need thread-safe cache | `ConcurrentHashMap` |
| Need LRU eviction | `LinkedHashMap` with access order |

## Designing A Class For LLD

Ask these questions:

1. What invariant must always be true?
2. Which fields are required at construction?
3. Which fields can change later?
4. Which methods represent domain operations?
5. What should be private?
6. Which dependencies should be interfaces?
7. Which collections match access patterns?
8. Is the class thread-safe, immutable, or not thread-safe?
9. What exceptions can it throw?
10. What tests would prove correctness?

## Example: Parking Lot

Core types:

- `ParkingLot`
- `ParkingFloor`
- `ParkingSpot`
- `Vehicle`
- `Ticket`
- `SpotAssignmentStrategy`

Collection choices:

- `Map<String, ParkingSpot>` for spot lookup
- `Queue<ParkingSpot>` for available spots
- `Map<String, Ticket>` for active tickets
- `EnumMap<VehicleType, Queue<ParkingSpot>>` for available spots by vehicle type

Runnable example: `src/main/java/com/codex/javaconcepts/lld/MiniParkingLotExample.java`

