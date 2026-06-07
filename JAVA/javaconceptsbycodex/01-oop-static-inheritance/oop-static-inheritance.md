# OOP, Static, Inner Classes, And Inheritance

LLD is mostly object modeling. Java's OOP features help you express the domain, hide implementation details, and keep behavior close to the data it owns.

## Class And Object

A class is a blueprint. An object is an instance.

```java
class Car {
    private final String numberPlate;

    Car(String numberPlate) {
        this.numberPlate = numberPlate;
    }

    String numberPlate() {
        return numberPlate;
    }
}

Car car = new Car("KA-01-1234");
```

LLD thinking:

- Class: concept in the system.
- Fields: state owned by the object.
- Methods: behavior the object can perform.
- Constructor: valid creation path.

## Access Modifiers

| Modifier | Visible from |
|---|---|
| `private` | Same class only |
| package-private | Same package only |
| `protected` | Same package and subclasses |
| `public` | Everywhere |

LLD rule: keep fields `private` and expose behavior through methods. This preserves invariants.

## Encapsulation

Encapsulation means hiding internal state and exposing controlled operations.

Bad:

```java
class Wallet {
    public int balance;
}
```

Better:

```java
class Wallet {
    private int balance;

    void addMoney(int amount) {
        if (amount <= 0) {
            throw new IllegalArgumentException("amount must be positive");
        }
        balance += amount;
    }

    int balance() {
        return balance;
    }
}
```

Now callers cannot make balance negative without going through domain rules.

## Constructor

A constructor creates a valid object.

```java
class User {
    private final String id;
    private final String email;

    User(String id, String email) {
        if (id == null || id.isBlank()) {
            throw new IllegalArgumentException("id is required");
        }
        if (email == null || !email.contains("@")) {
            throw new IllegalArgumentException("valid email is required");
        }
        this.id = id;
        this.email = email;
    }
}
```

LLD rule: do not allow half-valid objects when you can validate in the constructor or factory.

## `this`

`this` means the current object.

```java
class Counter {
    private int value;

    Counter increment() {
        this.value++;
        return this;
    }
}
```

Common uses:

- distinguish field from parameter: `this.name = name`
- pass current object
- return current object for fluent APIs

## Static Fields

A `static` field belongs to the class, not to one object.

```java
class IdGenerator {
    private static long nextId = 1;

    static long next() {
        return nextId++;
    }
}
```

Use static fields for constants or truly class-level shared state.

```java
class Pricing {
    static final double GST_RATE = 0.18;
}
```

Avoid mutable static state in LLD unless you are modeling a singleton-like shared service. It makes tests harder and can introduce concurrency bugs.

## Static Methods

A `static` method belongs to the class.

```java
class Money {
    static int paiseFromRupees(int rupees) {
        return rupees * 100;
    }
}
```

Good uses:

- utility methods
- factory methods
- pure stateless helpers

Bad use:

- hiding business behavior in utility classes when it should belong to a domain object

## Static Block

A static block runs once when the class is initialized.

```java
class Config {
    static final Map<String, String> DEFAULTS;

    static {
        Map<String, String> map = new HashMap<>();
        map.put("region", "ap-south-1");
        DEFAULTS = Map.copyOf(map);
    }
}
```

Use sparingly. Prefer simple static initialization when possible.

## Static Class In Java

Java does not allow a top-level `static class`.

Allowed:

```java
class Outer {
    static class Nested {
    }
}
```

Not allowed:

```java
static class TopLevel {
}
```

Reason: `static` means "belongs to an enclosing class". A top-level class has no enclosing class.

## Static Nested Class

A static nested class is declared inside another class but does not need an object of the outer class.

```java
class Order {
    private final List<Item> items;

    static class Item {
        private final String sku;
        private final int quantity;

        Item(String sku, int quantity) {
            this.sku = sku;
            this.quantity = quantity;
        }
    }
}
```

Use a static nested class when:

- the nested type is strongly related to the outer type
- it does not need access to a specific outer object
- you want to group types for readability

Builder pattern often uses static nested classes:

```java
class User {
    private final String id;
    private final String email;

    private User(Builder builder) {
        this.id = builder.id;
        this.email = builder.email;
    }

    static class Builder {
        private String id;
        private String email;

        Builder id(String id) {
            this.id = id;
            return this;
        }

        Builder email(String email) {
            this.email = email;
            return this;
        }

        User build() {
            return new User(this);
        }
    }
}
```

## Inner Class

A non-static nested class is an inner class. It belongs to an object of the outer class.

```java
class ShoppingCart {
    private final List<String> items = new ArrayList<>();

    class CartIterator {
        int count() {
            return items.size(); // can access outer object state
        }
    }
}
```

Creating it:

```java
ShoppingCart cart = new ShoppingCart();
ShoppingCart.CartIterator iterator = cart.new CartIterator();
```

Use inner classes when the nested object needs a specific outer object. Otherwise prefer a static nested class.

## Local Class

A local class is declared inside a method.

```java
void process() {
    class Validator {
        boolean valid(String value) {
            return value != null && !value.isBlank();
        }
    }
}
```

Use rarely. Lambdas and private helper methods are usually clearer.

## Anonymous Class

An anonymous class creates a one-time implementation.

```java
Comparator<String> byLength = new Comparator<>() {
    public int compare(String a, String b) {
        return Integer.compare(a.length(), b.length());
    }
};
```

Modern Java usually uses lambdas:

```java
Comparator<String> byLength = (a, b) -> Integer.compare(a.length(), b.length());
```

Anonymous classes are still useful when you need to override multiple methods.

## Inheritance

Inheritance models an `is-a` relationship.

```java
abstract class Vehicle {
    abstract int wheels();
}

class Bike extends Vehicle {
    int wheels() {
        return 2;
    }
}
```

Use inheritance when:

- subclasses truly are specialized forms of the parent
- the parent defines stable shared behavior
- polymorphism is valuable

Avoid inheritance when:

- you only want code reuse
- subclass behavior violates parent expectations
- the hierarchy changes frequently

For LLD, composition is often better.

## Composition

Composition means one object has another object.

```java
class PaymentService {
    private final PaymentGateway gateway;

    PaymentService(PaymentGateway gateway) {
        this.gateway = gateway;
    }
}
```

Use composition when:

- behavior can be swapped
- you want testability
- the relation is `has-a`, not `is-a`

## Method Overloading

Overloading means same method name, different parameter list, decided at compile time.

```java
class Printer {
    void print(String value) {}
    void print(int value) {}
    void print(String value, int copies) {}
}
```

Return type alone cannot overload a method.

## Method Overriding

Overriding means a subclass provides a new implementation of a parent method, decided at runtime.

```java
interface Notification {
    void send(String message);
}

class EmailNotification implements Notification {
    public void send(String message) {
        System.out.println("Email: " + message);
    }
}
```

Use `@Override`. It lets the compiler catch mistakes.

## Polymorphism

Polymorphism lets the caller use a common type while actual behavior depends on the runtime object.

```java
List<Notification> notifications = List.of(
    new EmailNotification(),
    new SmsNotification()
);

for (Notification notification : notifications) {
    notification.send("Order shipped");
}
```

This is central to Strategy, Factory, State, Observer, and Command patterns.

## Abstract Class

An abstract class can hold shared state and partial implementation.

```java
abstract class BasePayment {
    final String paymentId;

    BasePayment(String paymentId) {
        this.paymentId = paymentId;
    }

    abstract void process();
}
```

Use an abstract class when subclasses share implementation and state.

## Interface

An interface defines a contract.

```java
interface PaymentGateway {
    PaymentResult charge(Money amount);
}
```

Use interfaces to decouple high-level logic from concrete implementations.

Modern interfaces can have:

- abstract methods
- `default` methods
- `static` methods
- private helper methods

## `final`

`final` means different things based on where it appears:

| Usage | Meaning |
|---|---|
| `final class` | Cannot be extended |
| `final method` | Cannot be overridden |
| `final variable` | Cannot be reassigned |
| `final field` | Must be assigned once |

`final` does not make an object immutable by itself.

```java
final List<String> names = new ArrayList<>();
names.add("Asha"); // allowed
// names = new ArrayList<>(); // not allowed
```

## Object Methods

Every Java class extends `Object`.

Important methods:

| Method | Purpose |
|---|---|
| `toString()` | Human-readable representation |
| `equals(Object)` | Logical equality |
| `hashCode()` | Hash-based collection compatibility |
| `getClass()` | Runtime class |
| `wait()` / `notify()` / `notifyAll()` | Monitor coordination |

For LLD, implement `equals()` and `hashCode()` for value objects used in sets/maps.

## LLD Rules Of Thumb

- Prefer private fields and public behavior.
- Prefer constructor validation for required fields.
- Prefer interfaces at service boundaries.
- Prefer composition over inheritance unless the `is-a` relationship is stable.
- Prefer immutable value objects for IDs, money, address, date ranges, and keys.
- Prefer static nested classes for builders and helper types scoped to an outer class.
- Avoid mutable static state in interview designs unless you explain thread-safety.

Runnable example: `src/main/java/com/codex/javaconcepts/oop/OopStaticInheritanceExamples.java`

