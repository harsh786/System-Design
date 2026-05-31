# SOLID Principles & OOP Concepts - Complete LLD Interview Reference

## Table of Contents
1. [Single Responsibility Principle (SRP)](#1-single-responsibility-principle-srp)
2. [Open/Closed Principle (OCP)](#2-openclosed-principle-ocp)
3. [Liskov Substitution Principle (LSP)](#3-liskov-substitution-principle-lsp)
4. [Interface Segregation Principle (ISP)](#4-interface-segregation-principle-isp)
5. [Dependency Inversion Principle (DIP)](#5-dependency-inversion-principle-dip)
6. [Encapsulation](#6-encapsulation)
7. [Abstraction](#7-abstraction)
8. [Inheritance vs Composition](#8-inheritance-vs-composition)
9. [Polymorphism](#9-polymorphism)
10. [DRY](#10-dry-dont-repeat-yourself)
11. [KISS](#11-kiss-keep-it-simple)
12. [YAGNI](#12-yagni-you-arent-gonna-need-it)
13. [Law of Demeter](#13-law-of-demeter)
14. [Composition over Inheritance](#14-composition-over-inheritance)
15. [Program to Interface, not Implementation](#15-program-to-interface-not-implementation)

---

## 1. Single Responsibility Principle (SRP)

> A class should have only one reason to change.

Each class should have exactly one responsibility. If a class has multiple responsibilities, changes to one may break the other.

### Bad Code (Violates SRP)

```java
public class Invoice {
    private List<Item> items;
    private double taxRate;

    public double calculateTotal() {
        double sum = 0;
        for (Item item : items) {
            sum += item.getPrice() * item.getQuantity();
        }
        return sum * (1 + taxRate);
    }

    // VIOLATION: Persistence logic in domain class
    public void saveToDatabase() {
        Connection conn = DriverManager.getConnection("jdbc:mysql://localhost/db");
        PreparedStatement stmt = conn.prepareStatement("INSERT INTO invoices...");
        stmt.execute();
    }

    // VIOLATION: Presentation logic in domain class
    public void printInvoice() {
        System.out.println("=== INVOICE ===");
        for (Item item : items) {
            System.out.println(item.getName() + ": $" + item.getPrice());
        }
        System.out.println("Total: $" + calculateTotal());
    }

    // VIOLATION: Email logic in domain class
    public void sendEmail(String to) {
        EmailClient client = new EmailClient();
        client.send(to, "Invoice", this.toString());
    }
}
```

### Good Code (Follows SRP)

```java
// Responsibility: Invoice domain logic only
public class Invoice {
    private List<Item> items;
    private double taxRate;

    public double calculateTotal() {
        double sum = 0;
        for (Item item : items) {
            sum += item.getPrice() * item.getQuantity();
        }
        return sum * (1 + taxRate);
    }

    public List<Item> getItems() { return Collections.unmodifiableList(items); }
    public double getTaxRate() { return taxRate; }
}

// Responsibility: Persistence
public class InvoiceRepository {
    private final DataSource dataSource;

    public InvoiceRepository(DataSource dataSource) {
        this.dataSource = dataSource;
    }

    public void save(Invoice invoice) {
        // DB logic here
    }

    public Invoice findById(String id) {
        // DB query here
    }
}

// Responsibility: Printing/Formatting
public class InvoicePrinter {
    public String format(Invoice invoice) {
        StringBuilder sb = new StringBuilder("=== INVOICE ===\n");
        for (Item item : invoice.getItems()) {
            sb.append(item.getName()).append(": $").append(item.getPrice()).append("\n");
        }
        sb.append("Total: $").append(invoice.calculateTotal());
        return sb.toString();
    }
}

// Responsibility: Notification
public class InvoiceNotificationService {
    private final EmailClient emailClient;

    public InvoiceNotificationService(EmailClient emailClient) {
        this.emailClient = emailClient;
    }

    public void sendInvoice(Invoice invoice, String to) {
        emailClient.send(to, "Invoice", invoice.toString());
    }
}
```

### LLD Problems Demonstrating SRP
- **Parking Lot**: Separate ParkingLot, ParkingSpot, Ticket, PaymentProcessor, DisplayBoard
- **Library Management**: Separate Book, Member, Librarian, NotificationService, FineCalculator
- **Elevator System**: Separate Elevator, ElevatorController, Request, Scheduler

---

## 2. Open/Closed Principle (OCP)

> Software entities should be open for extension, but closed for modification.

You should be able to add new behavior without changing existing code.

### Bad Code (Violates OCP)

```java
public class NotificationService {
    // Every new notification type requires modifying this method
    public void sendNotification(String type, String message, String recipient) {
        if (type.equals("EMAIL")) {
            // send email
            EmailClient client = new EmailClient();
            client.send(recipient, "Notification", message);
        } else if (type.equals("SMS")) {
            // send SMS
            SmsGateway gateway = new SmsGateway();
            gateway.send(recipient, message);
        } else if (type.equals("PUSH")) {
            // send push notification
            PushService push = new PushService();
            push.notify(recipient, message);
        }
        // Adding SLACK, WEBHOOK, etc. means modifying this class!
    }
}

public class AreaCalculator {
    // Adding new shapes requires modifying this method
    public double calculateArea(Object shape) {
        if (shape instanceof Circle) {
            Circle c = (Circle) shape;
            return Math.PI * c.radius * c.radius;
        } else if (shape instanceof Rectangle) {
            Rectangle r = (Rectangle) shape;
            return r.width * r.height;
        }
        // Triangle? Pentagon? Must modify!
        return 0;
    }
}
```

### Good Code (Follows OCP)

```java
// Strategy pattern - open for extension via new implementations
public interface NotificationChannel {
    void send(String recipient, String message);
    boolean supports(String channelType);
}

public class EmailNotification implements NotificationChannel {
    private final EmailClient emailClient;

    public EmailNotification(EmailClient emailClient) {
        this.emailClient = emailClient;
    }

    @Override
    public void send(String recipient, String message) {
        emailClient.send(recipient, "Notification", message);
    }

    @Override
    public boolean supports(String channelType) {
        return "EMAIL".equals(channelType);
    }
}

public class SmsNotification implements NotificationChannel {
    private final SmsGateway gateway;

    public SmsNotification(SmsGateway gateway) {
        this.gateway = gateway;
    }

    @Override
    public void send(String recipient, String message) {
        gateway.send(recipient, message);
    }

    @Override
    public boolean supports(String channelType) {
        return "SMS".equals(channelType);
    }
}

// Adding Slack? Just create SlackNotification implements NotificationChannel
// No existing code modified!

public class NotificationService {
    private final List<NotificationChannel> channels;

    public NotificationService(List<NotificationChannel> channels) {
        this.channels = channels;
    }

    public void sendNotification(String type, String message, String recipient) {
        channels.stream()
            .filter(ch -> ch.supports(type))
            .findFirst()
            .orElseThrow(() -> new UnsupportedOperationException("No channel for: " + type))
            .send(recipient, message);
    }
}

// Shape example with polymorphism
public interface Shape {
    double calculateArea();
}

public class Circle implements Shape {
    private final double radius;
    public Circle(double radius) { this.radius = radius; }

    @Override
    public double calculateArea() {
        return Math.PI * radius * radius;
    }
}

public class Rectangle implements Shape {
    private final double width, height;
    public Rectangle(double w, double h) { this.width = w; this.height = h; }

    @Override
    public double calculateArea() {
        return width * height;
    }
}

// New shapes just implement the interface - no existing code changes
public class AreaCalculator {
    public double totalArea(List<Shape> shapes) {
        return shapes.stream().mapToDouble(Shape::calculateArea).sum();
    }
}
```

### LLD Problems Demonstrating OCP
- **Payment System**: New payment methods without modifying processor
- **Discount Engine**: New discount strategies without changing checkout
- **File Parser**: New file formats via strategy pattern
- **Notification System**: New channels without modifying sender

---

## 3. Liskov Substitution Principle (LSP)

> Objects of a superclass should be replaceable with objects of its subclasses without breaking the application.

Subtypes must be substitutable for their base types. If S extends T, anywhere T is used, S should work correctly.

### Bad Code (Violates LSP)

```java
public class Rectangle {
    protected int width;
    protected int height;

    public void setWidth(int width) { this.width = width; }
    public void setHeight(int height) { this.height = height; }
    public int getArea() { return width * height; }
}

// VIOLATION: Square changes the contract of Rectangle
public class Square extends Rectangle {
    @Override
    public void setWidth(int width) {
        this.width = width;
        this.height = width; // Surprise! Setting width also changes height
    }

    @Override
    public void setHeight(int height) {
        this.width = height;
        this.height = height;
    }
}

// This code BREAKS with Square
public void resize(Rectangle r) {
    r.setWidth(5);
    r.setHeight(10);
    assert r.getArea() == 50; // FAILS for Square! Area is 100
}

// Another violation: read-only subclass
public class ReadOnlyList<T> extends ArrayList<T> {
    @Override
    public boolean add(T t) {
        throw new UnsupportedOperationException(); // Violates LSP!
    }

    @Override
    public T remove(int index) {
        throw new UnsupportedOperationException();
    }
}
```

### Good Code (Follows LSP)

```java
// Use a common interface instead of inheritance
public interface Shape {
    int getArea();
}

public class Rectangle implements Shape {
    private final int width;
    private final int height;

    public Rectangle(int width, int height) {
        this.width = width;
        this.height = height;
    }

    @Override
    public int getArea() { return width * height; }
    public int getWidth() { return width; }
    public int getHeight() { return height; }
}

public class Square implements Shape {
    private final int side;

    public Square(int side) {
        this.side = side;
    }

    @Override
    public int getArea() { return side * side; }
    public int getSide() { return side; }
}

// For collections, use proper interface hierarchy
public interface ReadableList<T> {
    T get(int index);
    int size();
}

public interface WritableList<T> extends ReadableList<T> {
    void add(T item);
    void remove(int index);
}

// Now ReadOnlyList implements only ReadableList - no violation
public class ReadOnlyList<T> implements ReadableList<T> {
    private final List<T> inner;

    public ReadOnlyList(List<T> items) {
        this.inner = new ArrayList<>(items);
    }

    @Override
    public T get(int index) { return inner.get(index); }

    @Override
    public int size() { return inner.size(); }
}
```

### LSP Rules of Thumb
- **Preconditions**: Subclass cannot strengthen preconditions
- **Postconditions**: Subclass cannot weaken postconditions
- **Invariants**: Subclass must maintain parent's invariants
- **No new exceptions**: Subclass shouldn't throw exceptions parent doesn't

### LLD Problems Demonstrating LSP
- **Vehicle Hierarchy**: ElectricCar shouldn't break Car interface (no refuel())
- **Bird Hierarchy**: Penguin shouldn't extend FlyingBird
- **Account Types**: SavingsAccount shouldn't violate Account contract

---

## 4. Interface Segregation Principle (ISP)

> Clients should not be forced to depend on interfaces they do not use.

Many small, specific interfaces are better than one large general-purpose interface.

### Bad Code (Violates ISP)

```java
// Fat interface - forces all implementations to handle everything
public interface Worker {
    void work();
    void eat();
    void sleep();
    void attendMeeting();
    void writeReport();
    void code();
    void test();
    void deploy();
}

// Robot is forced to implement irrelevant methods
public class Robot implements Worker {
    @Override public void work() { /* OK */ }
    @Override public void eat() { /* IRRELEVANT - throw exception? */ }
    @Override public void sleep() { /* IRRELEVANT */ }
    @Override public void attendMeeting() { /* IRRELEVANT */ }
    @Override public void writeReport() { /* IRRELEVANT */ }
    @Override public void code() { /* OK */ }
    @Override public void test() { /* OK */ }
    @Override public void deploy() { /* OK */ }
}

// Fat interface for a multi-function device
public interface Machine {
    void print(Document doc);
    void scan(Document doc);
    void fax(Document doc);
    void staple(Document doc);
}

// SimplePrinter is forced to implement scan, fax, staple
public class SimplePrinter implements Machine {
    @Override public void print(Document doc) { /* OK */ }
    @Override public void scan(Document doc) { throw new UnsupportedOperationException(); }
    @Override public void fax(Document doc) { throw new UnsupportedOperationException(); }
    @Override public void staple(Document doc) { throw new UnsupportedOperationException(); }
}
```

### Good Code (Follows ISP)

```java
// Segregated interfaces
public interface Workable {
    void work();
}

public interface Feedable {
    void eat();
    void sleep();
}

public interface Meetable {
    void attendMeeting();
    void writeReport();
}

public interface Codeable {
    void code();
    void test();
    void deploy();
}

// Human implements what's relevant
public class Developer implements Workable, Feedable, Meetable, Codeable {
    @Override public void work() { /* ... */ }
    @Override public void eat() { /* ... */ }
    @Override public void sleep() { /* ... */ }
    @Override public void attendMeeting() { /* ... */ }
    @Override public void writeReport() { /* ... */ }
    @Override public void code() { /* ... */ }
    @Override public void test() { /* ... */ }
    @Override public void deploy() { /* ... */ }
}

// Robot implements only what's relevant
public class Robot implements Workable, Codeable {
    @Override public void work() { /* ... */ }
    @Override public void code() { /* ... */ }
    @Override public void test() { /* ... */ }
    @Override public void deploy() { /* ... */ }
}

// Machine interfaces segregated
public interface Printer {
    void print(Document doc);
}

public interface Scanner {
    void scan(Document doc);
}

public interface Fax {
    void fax(Document doc);
}

public class SimplePrinter implements Printer {
    @Override
    public void print(Document doc) { /* works perfectly */ }
}

public class AllInOnePrinter implements Printer, Scanner, Fax {
    @Override public void print(Document doc) { /* ... */ }
    @Override public void scan(Document doc) { /* ... */ }
    @Override public void fax(Document doc) { /* ... */ }
}
```

### LLD Problems Demonstrating ISP
- **Parking Lot**: Separate Parkable, Chargeable, HandicapAccessible interfaces
- **Vehicle Types**: Separate Drivable, Flyable, Sailable interfaces
- **User Roles**: Separate ReadAccess, WriteAccess, AdminAccess interfaces

---

## 5. Dependency Inversion Principle (DIP)

> High-level modules should not depend on low-level modules. Both should depend on abstractions.

### Bad Code (Violates DIP)

```java
// High-level module directly depends on low-level implementations
public class OrderService {
    // Direct dependency on concrete classes
    private MySQLDatabase database = new MySQLDatabase();
    private SmtpEmailSender emailSender = new SmtpEmailSender();
    private StripePaymentGateway paymentGateway = new StripePaymentGateway();

    public void placeOrder(Order order) {
        // Tightly coupled - can't switch to MongoDB, SendGrid, or PayPal
        paymentGateway.charge(order.getTotal());
        database.save(order);
        emailSender.send(order.getCustomerEmail(), "Order confirmed");
    }
}

// Cannot unit test without real DB, email server, and Stripe
// Cannot switch implementations without modifying OrderService
```

### Good Code (Follows DIP)

```java
// Abstractions (interfaces)
public interface OrderRepository {
    void save(Order order);
    Optional<Order> findById(String id);
}

public interface PaymentGateway {
    PaymentResult charge(Money amount, PaymentMethod method);
}

public interface NotificationService {
    void notify(String recipient, String message);
}

// High-level module depends on abstractions
public class OrderService {
    private final OrderRepository repository;
    private final PaymentGateway paymentGateway;
    private final NotificationService notificationService;

    // Dependencies injected via constructor
    public OrderService(OrderRepository repository,
                        PaymentGateway paymentGateway,
                        NotificationService notificationService) {
        this.repository = repository;
        this.paymentGateway = paymentGateway;
        this.notificationService = notificationService;
    }

    public void placeOrder(Order order) {
        PaymentResult result = paymentGateway.charge(order.getTotal(), order.getPaymentMethod());
        if (result.isSuccessful()) {
            repository.save(order);
            notificationService.notify(order.getCustomerEmail(), "Order confirmed");
        }
    }
}

// Low-level modules implement abstractions
public class MySQLOrderRepository implements OrderRepository {
    @Override
    public void save(Order order) { /* MySQL logic */ }

    @Override
    public Optional<Order> findById(String id) { /* MySQL logic */ }
}

public class StripePaymentGateway implements PaymentGateway {
    @Override
    public PaymentResult charge(Money amount, PaymentMethod method) { /* Stripe API */ }
}

public class EmailNotificationService implements NotificationService {
    @Override
    public void notify(String recipient, String message) { /* SMTP logic */ }
}

// Easy to test with mocks
public class OrderServiceTest {
    @Test
    void testPlaceOrder() {
        OrderRepository mockRepo = mock(OrderRepository.class);
        PaymentGateway mockPayment = mock(PaymentGateway.class);
        NotificationService mockNotify = mock(NotificationService.class);

        when(mockPayment.charge(any(), any())).thenReturn(PaymentResult.success());

        OrderService service = new OrderService(mockRepo, mockPayment, mockNotify);
        service.placeOrder(testOrder);

        verify(mockRepo).save(testOrder);
        verify(mockNotify).notify(any(), any());
    }
}
```

### LLD Problems Demonstrating DIP
- **Parking Lot**: ParkingLotService depends on abstract PaymentProcessor
- **Cab Booking**: RideService depends on abstract DriverMatchingStrategy
- **E-commerce**: OrderService depends on abstract payment, inventory, notification

---

## 6. Encapsulation

> Bundle data and methods that operate on that data within a single unit, hiding internal state.

### In LLD Context

```java
// BAD: Exposed internals
public class BankAccount {
    public double balance; // Anyone can directly set negative balance!
    public List<Transaction> transactions; // Can be modified externally
}

// GOOD: Encapsulated
public class BankAccount {
    private double balance;
    private final List<Transaction> transactions;

    public BankAccount(double initialBalance) {
        if (initialBalance < 0) throw new IllegalArgumentException("Cannot start with negative balance");
        this.balance = initialBalance;
        this.transactions = new ArrayList<>();
    }

    public void deposit(double amount) {
        if (amount <= 0) throw new IllegalArgumentException("Deposit must be positive");
        this.balance += amount;
        transactions.add(new Transaction(TransactionType.DEPOSIT, amount, LocalDateTime.now()));
    }

    public void withdraw(double amount) {
        if (amount <= 0) throw new IllegalArgumentException("Withdrawal must be positive");
        if (amount > balance) throw new InsufficientFundsException();
        this.balance -= amount;
        transactions.add(new Transaction(TransactionType.WITHDRAWAL, amount, LocalDateTime.now()));
    }

    public double getBalance() { return balance; }

    public List<Transaction> getTransactionHistory() {
        return Collections.unmodifiableList(transactions);
    }
}
```

### Key Encapsulation Techniques in LLD
- Private fields with controlled access via methods
- Immutable objects (final fields, no setters)
- Defensive copies for mutable objects
- Unmodifiable collection wrappers
- Builder pattern for complex object construction

---

## 7. Abstraction

> Hide complex implementation details and show only necessary features.

### In LLD Context

```java
// Abstraction hides complexity of payment processing
public interface PaymentProcessor {
    PaymentResult process(PaymentRequest request);
}

// Client code doesn't know about HTTP calls, retries, error mapping
public class StripeProcessor implements PaymentProcessor {
    private final StripeClient client;
    private final RetryPolicy retryPolicy;

    @Override
    public PaymentResult process(PaymentRequest request) {
        // Complex implementation hidden:
        // 1. Map to Stripe API format
        // 2. Handle authentication
        // 3. Retry on transient failures
        // 4. Map response back to domain objects
        // 5. Handle various error codes
        return executeWithRetry(() -> {
            StripeCharge charge = client.createCharge(mapToStripeRequest(request));
            return mapToResult(charge);
        });
    }
}

// Usage - simple and clean
public class CheckoutService {
    private final PaymentProcessor processor;

    public OrderResult checkout(Cart cart) {
        PaymentResult result = processor.process(cart.toPaymentRequest());
        // Don't care HOW payment was processed
        return result.isSuccess() ? confirmOrder(cart) : failOrder(cart, result);
    }
}
```

---

## 8. Inheritance vs Composition

### When to Use Inheritance
- True "is-a" relationship
- Subclass is a specialization of parent
- You want to reuse interface (polymorphism)

### When to Use Composition
- "has-a" relationship
- You want to reuse behavior
- Relationship can change at runtime
- Multiple behaviors needed (Java has no multiple inheritance)

### Example: Notification System

```java
// INHERITANCE approach - rigid, limited
public abstract class Notification {
    abstract void send(String message, String recipient);
}

public class EmailNotification extends Notification {
    void send(String message, String recipient) { /* email */ }
}

public class EncryptedEmailNotification extends EmailNotification {
    // What if we want encrypted SMS too? Class explosion!
}

// COMPOSITION approach - flexible
public interface MessageSender {
    void send(String message, String recipient);
}

public interface MessageEncryptor {
    String encrypt(String message);
}

public interface MessageFormatter {
    String format(String message);
}

public class NotificationService {
    private final MessageSender sender;
    private final MessageEncryptor encryptor;   // optional
    private final MessageFormatter formatter;    // optional

    public NotificationService(MessageSender sender,
                               MessageEncryptor encryptor,
                               MessageFormatter formatter) {
        this.sender = sender;
        this.encryptor = encryptor;
        this.formatter = formatter;
    }

    public void sendNotification(String message, String recipient) {
        String processed = message;
        if (formatter != null) processed = formatter.format(processed);
        if (encryptor != null) processed = encryptor.encrypt(processed);
        sender.send(processed, recipient);
    }
}

// Mix and match behaviors freely:
// new NotificationService(emailSender, aesEncryptor, htmlFormatter)
// new NotificationService(smsSender, null, plainTextFormatter)
// new NotificationService(slackSender, aesEncryptor, markdownFormatter)
```

---

## 9. Polymorphism

### Compile-time (Method Overloading)

```java
public class PriceCalculator {
    // Same method name, different parameters
    public double calculate(Item item) {
        return item.getBasePrice();
    }

    public double calculate(Item item, Coupon coupon) {
        return item.getBasePrice() - coupon.getDiscount();
    }

    public double calculate(Item item, Coupon coupon, MembershipLevel level) {
        double price = item.getBasePrice() - coupon.getDiscount();
        return price * (1 - level.getDiscountPercentage());
    }
}
```

### Runtime (Method Overriding) - More important for LLD

```java
public interface PricingStrategy {
    double calculatePrice(Order order);
}

public class RegularPricing implements PricingStrategy {
    @Override
    public double calculatePrice(Order order) {
        return order.getSubtotal();
    }
}

public class HolidayPricing implements PricingStrategy {
    @Override
    public double calculatePrice(Order order) {
        return order.getSubtotal() * 0.8; // 20% holiday discount
    }
}

public class BulkPricing implements PricingStrategy {
    @Override
    public double calculatePrice(Order order) {
        if (order.getItemCount() > 100) return order.getSubtotal() * 0.7;
        if (order.getItemCount() > 50) return order.getSubtotal() * 0.85;
        return order.getSubtotal();
    }
}

// Runtime polymorphism - strategy selected at runtime
public class OrderProcessor {
    private final PricingStrategy strategy;

    public OrderProcessor(PricingStrategy strategy) {
        this.strategy = strategy;
    }

    public Invoice processOrder(Order order) {
        double finalPrice = strategy.calculatePrice(order); // Calls correct implementation at runtime
        return new Invoice(order, finalPrice);
    }
}
```

### LLD Problems Using Polymorphism
- **Parking Lot**: Different vehicle types, different pricing strategies
- **Chess**: Different piece movement via polymorphism
- **Vending Machine**: Different states via State pattern (polymorphism)

---

## 10. DRY (Don't Repeat Yourself)

> Every piece of knowledge must have a single, unambiguous representation in the system.

### Bad Code

```java
public class UserService {
    public boolean isValidEmail(String email) {
        return email != null && email.contains("@") && email.contains(".");
    }
}

public class RegistrationService {
    // DUPLICATED validation logic
    public boolean isValidEmail(String email) {
        return email != null && email.contains("@") && email.contains(".");
    }
}

public class ContactService {
    // DUPLICATED again!
    public boolean isValidEmail(String email) {
        return email != null && email.contains("@") && email.contains(".");
    }
}
```

### Good Code

```java
public class EmailValidator {
    private static final Pattern EMAIL_PATTERN =
        Pattern.compile("^[A-Za-z0-9+_.-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}$");

    public static boolean isValid(String email) {
        return email != null && EMAIL_PATTERN.matcher(email).matches();
    }
}

// All services use the single source of truth
public class UserService {
    public void updateEmail(User user, String email) {
        if (!EmailValidator.isValid(email)) throw new InvalidEmailException(email);
        user.setEmail(email);
    }
}
```

---

## 11. KISS (Keep It Simple)

> Choose the simplest solution that works correctly.

### Bad Code (Over-engineered)

```java
// Over-engineered for a simple flag check
public class FeatureToggleStrategyFactoryProvider {
    private final Map<String, AbstractFeatureToggleStrategyFactory> factoryMap;
    private final FeatureToggleStrategySelector selector;
    private final FeatureToggleConfigurationResolver resolver;

    public boolean isFeatureEnabled(String feature) {
        FeatureToggleConfiguration config = resolver.resolve(feature);
        AbstractFeatureToggleStrategyFactory factory = factoryMap.get(config.getType());
        FeatureToggleStrategy strategy = factory.createStrategy(config);
        return selector.evaluate(strategy, getCurrentContext());
    }
}
```

### Good Code (Simple)

```java
public class FeatureFlags {
    private final Map<String, Boolean> flags;

    public FeatureFlags(Map<String, Boolean> flags) {
        this.flags = new HashMap<>(flags);
    }

    public boolean isEnabled(String feature) {
        return flags.getOrDefault(feature, false);
    }
}
```

---

## 12. YAGNI (You Aren't Gonna Need It)

> Don't add functionality until it's actually needed.

### Bad Code

```java
public class User {
    private String name;
    private String email;
    private String phone;
    private String fax;           // Who uses fax?
    private String pagerNumber;   // Really?
    private String secondaryEmail;
    private String tertiaryEmail;
    private Map<String, Object> metadata;        // "might need it someday"
    private List<String> previousNames;          // "just in case"
    private ZonedDateTime lastFaxSentAt;         // never used
    private String preferredCommunicationProtocol; // over-abstracted
}
```

### Good Code

```java
public class User {
    private final String name;
    private final String email;
    private String phone; // optional, actually used in the app

    public User(String name, String email) {
        this.name = Objects.requireNonNull(name);
        this.email = Objects.requireNonNull(email);
    }
    // Add fields WHEN they're actually needed, not before
}
```

---

## 13. Law of Demeter

> A method should only talk to its immediate friends. Don't reach through objects.

### Bad Code (Train Wreck)

```java
// Reaching deep into object graph
public class OrderProcessor {
    public void processOrder(Order order) {
        // BAD: order -> customer -> address -> city -> taxRate
        double taxRate = order.getCustomer().getAddress().getCity().getTaxRate();

        // BAD: reaching through multiple levels
        String cardNumber = order.getCustomer().getWallet().getCreditCard().getNumber();

        // BAD: deeply coupled to internal structure
        order.getCustomer().getAccount().getBalance().subtract(order.getTotal());
    }
}
```

### Good Code

```java
public class OrderProcessor {
    public void processOrder(Order order) {
        // GOOD: Ask order for what you need
        double taxRate = order.getApplicableTaxRate();
        // Order delegates: return customer.getShippingTaxRate();
        // Customer delegates: return address.getCityTaxRate();

        // GOOD: Tell, don't ask
        order.chargeCustomer();
        // Order handles the payment internally
    }
}

public class Order {
    private final Customer customer;
    private final Money total;

    public double getApplicableTaxRate() {
        return customer.getShippingTaxRate();
    }

    public void chargeCustomer() {
        customer.charge(total);
    }
}

public class Customer {
    private final Address address;
    private final Account account;

    public double getShippingTaxRate() {
        return address.getCityTaxRate();
    }

    public void charge(Money amount) {
        account.debit(amount);
    }
}
```

---

## 14. Composition over Inheritance

> Favor object composition over class inheritance for code reuse.

### Bad Code (Inheritance for reuse)

```java
// Deep inheritance hierarchy - fragile, rigid
public class Animal { }
public class Bird extends Animal { public void fly() { } }
public class Duck extends Bird { public void swim() { } }
public class RubberDuck extends Duck {
    // RubberDuck can't fly! But inherits fly() from Bird
    // RubberDuck isn't alive! But inherits from Animal
    @Override public void fly() { throw new UnsupportedOperationException(); }
}
```

### Good Code (Composition)

```java
public interface FlyBehavior {
    void fly();
}

public interface SwimBehavior {
    void swim();
}

public interface QuackBehavior {
    void quack();
}

public class FlyWithWings implements FlyBehavior {
    @Override public void fly() { System.out.println("Flying with wings!"); }
}

public class NoFly implements FlyBehavior {
    @Override public void fly() { /* do nothing */ }
}

public class Squeak implements QuackBehavior {
    @Override public void quack() { System.out.println("Squeak!"); }
}

public class Duck {
    private final FlyBehavior flyBehavior;
    private final SwimBehavior swimBehavior;
    private final QuackBehavior quackBehavior;

    public Duck(FlyBehavior fb, SwimBehavior sb, QuackBehavior qb) {
        this.flyBehavior = fb;
        this.swimBehavior = sb;
        this.quackBehavior = qb;
    }

    public void performFly() { flyBehavior.fly(); }
    public void performSwim() { swimBehavior.swim(); }
    public void performQuack() { quackBehavior.quack(); }
}

// RubberDuck: new Duck(new NoFly(), new FloatSwim(), new Squeak())
// MallardDuck: new Duck(new FlyWithWings(), new DiveSwim(), new LoudQuack())
```

---

## 15. Program to Interface, not Implementation

> Depend on abstractions (interfaces/abstract classes) rather than concrete implementations.

### Bad Code

```java
public class ReportGenerator {
    // Tied to specific implementation
    private ArrayList<String> data = new ArrayList<>();
    private MySQLConnection connection = new MySQLConnection();
    private PdfWriter writer = new PdfWriter();

    public void generate() {
        // Can't switch to LinkedList, PostgreSQL, or CSV without changing this class
        data = connection.fetchData();
        writer.write(data);
    }
}
```

### Good Code

```java
public class ReportGenerator {
    private final DataSource dataSource;      // Interface
    private final ReportWriter writer;        // Interface

    public ReportGenerator(DataSource dataSource, ReportWriter writer) {
        this.dataSource = dataSource;
        this.writer = writer;
    }

    public void generate() {
        List<String> data = dataSource.fetchData(); // List interface, not ArrayList
        writer.write(data);
    }
}

// Flexibility to use any implementation:
// new ReportGenerator(new DatabaseSource(), new PdfWriter())
// new ReportGenerator(new ApiSource(), new CsvWriter())
// new ReportGenerator(new FileSource(), new ExcelWriter())
```

---

## Quick Reference: Which Principles Apply to Which LLD Problems

| LLD Problem | Key Principles |
|---|---|
| Parking Lot | SRP, OCP, DIP, Strategy Pattern |
| Elevator System | SRP, State Pattern, OCP |
| Chess/Tic-Tac-Toe | LSP, Polymorphism, OCP |
| Library Management | SRP, DIP, ISP |
| Vending Machine | State Pattern, OCP, SRP |
| Hotel Booking | SRP, DIP, Strategy |
| Payment System | OCP, DIP, Strategy |
| Notification System | OCP, ISP, DIP |
| File System | Composite Pattern, LSP |
| Cache (LRU) | SRP, Encapsulation |
| Rate Limiter | Strategy, OCP, DIP |
| Cab Booking (Uber) | SRP, OCP, DIP, Strategy, Observer |

---

## Interview Tips

1. **Start with SRP** - Break your design into classes with single responsibilities first
2. **Use interfaces liberally** - They enable OCP, DIP, and testability
3. **Favor composition** - Use Strategy, Observer, Decorator over inheritance
4. **Apply DIP** - High-level business logic should never import low-level details
5. **Test your LSP** - Ask "can I substitute this subclass everywhere the parent is used?"
6. **Don't over-engineer** - Apply KISS and YAGNI; add complexity only when justified
7. **Name things well** - Good names reveal which SRP a class fulfills

