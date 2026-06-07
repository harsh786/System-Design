# Immutability, Records, Enums, And Sealed Types

These concepts make LLD designs safer and easier to reason about.

## Immutability

An immutable object cannot change after construction.

Benefits:

- thread-safe by default
- safe as map keys and set elements
- easier to cache
- easier to reason about
- fewer defensive copies needed by callers

Example:

```java
final class Money {
    private final String currency;
    private final long cents;

    Money(String currency, long cents) {
        this.currency = Objects.requireNonNull(currency);
        this.cents = cents;
    }

    Money add(Money other) {
        if (!currency.equals(other.currency)) {
            throw new IllegalArgumentException("currency mismatch");
        }
        return new Money(currency, cents + other.cents);
    }
}
```

## How To Create An Immutable Class

- Make class `final`, or make inheritance safe.
- Make fields `private final`.
- Do not expose mutable internals.
- Validate constructor arguments.
- Make defensive copies of mutable inputs.
- Return defensive copies of mutable fields.

## Defensive Copy

Bad:

```java
class Team {
    private final List<String> members;

    Team(List<String> members) {
        this.members = members;
    }
}
```

Caller can mutate the original list after passing it.

Better:

```java
class Team {
    private final List<String> members;

    Team(List<String> members) {
        this.members = List.copyOf(members);
    }

    List<String> members() {
        return members;
    }
}
```

## Record

A record is a compact way to create an immutable data carrier.

```java
record UserId(String value) {
    UserId {
        if (value == null || value.isBlank()) {
            throw new IllegalArgumentException("value is required");
        }
    }
}
```

Records automatically provide:

- private final fields
- constructor
- accessors
- `equals`
- `hashCode`
- `toString`

Use records for:

- IDs
- value objects
- DTOs
- events
- command objects

Avoid records when the object has complex lifecycle behavior or identity separate from its values.

## Enum

An enum is a fixed set of constants.

```java
enum OrderStatus {
    CREATED,
    PAID,
    SHIPPED,
    CANCELLED
}
```

Enums can also have fields and methods:

```java
enum PaymentMethod {
    CARD(true),
    CASH(false);

    private final boolean online;

    PaymentMethod(boolean online) {
        this.online = online;
    }

    boolean online() {
        return online;
    }
}
```

Use enums for finite states and categories.

## EnumSet And EnumMap

Use enum-specialized collections when keys/elements are enums.

```java
EnumSet<OrderStatus> terminal = EnumSet.of(OrderStatus.CANCELLED);
EnumMap<OrderStatus, String> labels = new EnumMap<>(OrderStatus.class);
```

They are faster and clearer than generic hash-based collections.

## Sealed Types

Sealed classes/interfaces restrict which classes can extend or implement them.

```java
sealed interface PaymentCommand permits CardPayment, CashPayment {
}

record CardPayment(String cardToken) implements PaymentCommand {
}

record CashPayment() implements PaymentCommand {
}
```

Use sealed types when the set of implementations is intentionally closed.

LLD use:

- payment command variants
- notification channel variants
- domain event variants
- state-machine transitions

## LLD Rules Of Thumb

- Use immutable value objects for IDs, money, coordinates, time ranges, and keys.
- Use records for simple data carriers.
- Use enums for closed finite states.
- Use `EnumSet` and `EnumMap` when working with enum collections.
- Use sealed types when variants are known and controlled.

Runnable example: `src/main/java/com/codex/javaconcepts/lld/ValueObjectExamples.java`

