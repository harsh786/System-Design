# Factory Method Design Pattern

## What Is It?

The Factory Method pattern defines an interface for creating an object, but lets **subclasses** decide which class to instantiate. It defers instantiation to subclasses, promoting loose coupling between the creator and the concrete products.

## When to Use

- You don't know ahead of time what concrete class you need to instantiate
- You want subclasses to specify the objects they create
- You want to localize object creation logic to avoid scattering `new` calls
- You need to support adding new product types without modifying existing code (Open/Closed Principle)

## Why Use It?

- **Decouples** client code from concrete implementations
- **Single Responsibility**: creation logic lives in one place
- **Open/Closed Principle**: add new products without changing existing factories
- **Testability**: easy to mock factories in unit tests

## Class Diagram (ASCII)

```
         ┌───────────────────────┐
         │   <<interface>>       │
         │     Notification      │
         ├───────────────────────┤
         │ + notifyUser(msg)     │
         │ + getChannel()        │
         └───────────┬───────────┘
                     │ implements
        ┌────────────┼────────────────┐
        │            │                │
┌───────▼──────┐ ┌──▼───────────┐ ┌──▼──────────────┐
│EmailNotific. │ │SMSNotific.   │ │PushNotific.     │
└──────────────┘ └──────────────┘ └─────────────────┘

         ┌───────────────────────┐
         │  <<abstract>>         │
         │ NotificationFactory   │
         ├───────────────────────┤
         │ + createNotification()│  ← factory method
         │ + sendNotification()  │  ← template method
         └───────────┬───────────┘
                     │ extends
        ┌────────────┼────────────────┐
        │            │                │
┌───────▼──────┐ ┌──▼───────────┐ ┌──▼──────────────┐
│EmailNotific. │ │SMSNotific.   │ │PushNotific.     │
│  Factory     │ │  Factory     │ │  Factory        │
└──────────────┘ └──────────────┘ └─────────────────┘
```

## Real-World Use Cases

| Domain | Creator | Product |
|--------|---------|---------|
| Document apps | `DocumentFactory` | `PDFDocument`, `WordDocument` |
| Database drivers | `ConnectionFactory` | `MySQLConnection`, `PostgresConnection` |
| UI frameworks | `DialogFactory` | `WindowsDialog`, `MacDialog` |
| Logging | `LoggerFactory` | `FileLogger`, `ConsoleLogger`, `CloudLogger` |
| Payment processing | `PaymentGatewayFactory` | `StripeGateway`, `PayPalGateway` |

## Pros and Cons

### Pros
- Follows Open/Closed Principle
- Follows Single Responsibility Principle
- Avoids tight coupling between creator and products
- Makes code more testable and maintainable
- Easy to introduce new product variants

### Cons
- Can lead to many subclasses (class explosion)
- Adds indirection / complexity for simple cases
- Requires a new factory subclass for each product type

## When NOT to Use

- Product creation is trivial and unlikely to change
- Only one concrete product exists (no polymorphism needed)
- The added abstraction layer doesn't justify the complexity
- Simple constructor calls are clear enough

## How to Run

```bash
javac FactoryMethodPattern.java
java FactoryMethodPattern
```
