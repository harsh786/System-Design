# SOLID Principles & Clean Code — Complete Java Reference for LLD

---

## 1. Single Responsibility Principle (SRP)

> **A class should have only ONE reason to change.**

A "reason to change" corresponds to one actor or stakeholder. If two different stakeholders
can request changes to the same class, that class has multiple responsibilities.

### How to Identify SRP Violations

Ask: "This class does X **AND** Y." If you can fill in two distinct things, it violates SRP.

---

### BAD Example: God-class UserService

```java
// VIOLATION: This class has 3 reasons to change:
// 1. User CRUD logic changes
// 2. Email format/provider changes
// 3. Report format changes

public class UserService {
    
    // Responsibility 1: User persistence
    public void createUser(String name, String email) {
        // save to database
        Connection conn = DriverManager.getConnection("jdbc:mysql://localhost/db");
        PreparedStatement stmt = conn.prepareStatement(
            "INSERT INTO users (name, email) VALUES (?, ?)"
        );
        stmt.setString(1, name);
        stmt.setString(2, email);
        stmt.executeUpdate();
        
        // Responsibility 2: Send welcome email (mixed in!)
        sendWelcomeEmail(email, name);
    }
    
    // Responsibility 2: Email sending
    private void sendWelcomeEmail(String email, String name) {
        Properties props = new Properties();
        props.put("mail.smtp.host", "smtp.gmail.com");
        Session session = Session.getDefaultInstance(props);
        MimeMessage message = new MimeMessage(session);
        message.setSubject("Welcome " + name);
        message.setText("Thanks for joining!");
        Transport.send(message);
    }
    
    // Responsibility 3: Report generation
    public String generateUserReport(List<User> users) {
        StringBuilder sb = new StringBuilder();
        sb.append("USER REPORT\n");
        sb.append("Generated: ").append(LocalDate.now()).append("\n");
        for (User user : users) {
            sb.append(user.getName()).append(" - ").append(user.getEmail()).append("\n");
        }
        return sb.toString();
    }
    
    public User findUser(int id) { /* ... */ return null; }
    public void deleteUser(int id) { /* ... */ }
}
```

**Problems:**
- Changing email provider requires modifying `UserService`
- Changing report format requires modifying `UserService`
- Testing user CRUD requires mocking email and report dependencies
- Any bug in email logic can break user creation

---

### GOOD Example: Separated Responsibilities

```java
// Each class has exactly ONE reason to change

// --- Responsibility 1: User persistence ---
public class UserRepository {
    private final DataSource dataSource;
    
    public UserRepository(DataSource dataSource) {
        this.dataSource = dataSource;
    }
    
    public void save(User user) {
        try (Connection conn = dataSource.getConnection()) {
            PreparedStatement stmt = conn.prepareStatement(
                "INSERT INTO users (name, email) VALUES (?, ?)"
            );
            stmt.setString(1, user.getName());
            stmt.setString(2, user.getEmail());
            stmt.executeUpdate();
        } catch (SQLException e) {
            throw new PersistenceException("Failed to save user", e);
        }
    }
    
    public Optional<User> findById(int id) {
        try (Connection conn = dataSource.getConnection()) {
            PreparedStatement stmt = conn.prepareStatement(
                "SELECT * FROM users WHERE id = ?"
            );
            stmt.setInt(1, id);
            ResultSet rs = stmt.executeQuery();
            if (rs.next()) {
                return Optional.of(new User(rs.getInt("id"), rs.getString("name"), rs.getString("email")));
            }
            return Optional.empty();
        } catch (SQLException e) {
            throw new PersistenceException("Failed to find user", e);
        }
    }
    
    public void delete(int id) {
        try (Connection conn = dataSource.getConnection()) {
            PreparedStatement stmt = conn.prepareStatement("DELETE FROM users WHERE id = ?");
            stmt.setInt(1, id);
            stmt.executeUpdate();
        } catch (SQLException e) {
            throw new PersistenceException("Failed to delete user", e);
        }
    }
}

// --- Responsibility 2: Email notifications ---
public class EmailService {
    private final String smtpHost;
    private final int smtpPort;
    
    public EmailService(String smtpHost, int smtpPort) {
        this.smtpHost = smtpHost;
        this.smtpPort = smtpPort;
    }
    
    public void sendWelcomeEmail(User user) {
        String subject = "Welcome " + user.getName();
        String body = "Thanks for joining our platform!";
        sendEmail(user.getEmail(), subject, body);
    }
    
    public void sendPasswordResetEmail(User user, String resetToken) {
        String subject = "Password Reset";
        String body = "Use this token to reset: " + resetToken;
        sendEmail(user.getEmail(), subject, body);
    }
    
    private void sendEmail(String to, String subject, String body) {
        // Email sending logic isolated here
        System.out.println("Sending email to " + to + ": " + subject);
    }
}

// --- Responsibility 3: Report generation ---
public class UserReportGenerator {
    
    public String generateReport(List<User> users, ReportFormat format) {
        return switch (format) {
            case CSV -> generateCsv(users);
            case TEXT -> generateText(users);
        };
    }
    
    private String generateText(List<User> users) {
        StringBuilder sb = new StringBuilder();
        sb.append("USER REPORT | Generated: ").append(LocalDate.now()).append("\n");
        sb.append("-".repeat(50)).append("\n");
        for (User user : users) {
            sb.append(String.format("%-20s %s%n", user.getName(), user.getEmail()));
        }
        return sb.toString();
    }
    
    private String generateCsv(List<User> users) {
        StringBuilder sb = new StringBuilder("name,email\n");
        for (User user : users) {
            sb.append(user.getName()).append(",").append(user.getEmail()).append("\n");
        }
        return sb.toString();
    }
}

// --- Orchestrator (thin coordination layer) ---
public class UserRegistrationService {
    private final UserRepository userRepository;
    private final EmailService emailService;
    
    public UserRegistrationService(UserRepository userRepository, EmailService emailService) {
        this.userRepository = userRepository;
        this.emailService = emailService;
    }
    
    public void registerUser(String name, String email) {
        User user = new User(name, email);
        userRepository.save(user);
        emailService.sendWelcomeEmail(user);
    }
}
```

### Real LLD Application: Parking Lot

```java
// SRP applied to Parking Lot Design

public class ParkingLot {
    // Only manages spots and availability
    private final List<ParkingFloor> floors;
    
    public ParkingSpot findAvailableSpot(VehicleType type) { /* ... */ return null; }
    public void occupySpot(ParkingSpot spot) { /* ... */ }
    public void freeSpot(ParkingSpot spot) { /* ... */ }
}

public class TicketService {
    // Only manages ticket lifecycle
    public ParkingTicket issueTicket(Vehicle vehicle, ParkingSpot spot) { /* ... */ return null; }
    public void closeTicket(ParkingTicket ticket) { /* ... */ }
}

public class PaymentService {
    // Only handles payment calculation and processing
    public double calculateFee(ParkingTicket ticket) { /* ... */ return 0; }
    public Payment processPayment(ParkingTicket ticket, PaymentMethod method) { /* ... */ return null; }
}
```

---

## 2. Open/Closed Principle (OCP)

> **Software entities should be open for extension but closed for modification.**

You should be able to add new behavior WITHOUT changing existing, tested code.

---

### BAD Example: If-Else Chain

```java
// VIOLATION: Adding a new payment type requires modifying this class
// Every modification risks breaking existing payment logic

public class PaymentProcessor {
    
    public void processPayment(String paymentType, double amount, Map<String, String> details) {
        if (paymentType.equals("CREDIT_CARD")) {
            String cardNumber = details.get("cardNumber");
            String cvv = details.get("cvv");
            String expiry = details.get("expiry");
            // Credit card processing logic
            System.out.println("Processing credit card payment: " + amount);
            // Validate card, charge via gateway...
            
        } else if (paymentType.equals("UPI")) {
            String upiId = details.get("upiId");
            // UPI processing logic
            System.out.println("Processing UPI payment to " + upiId + ": " + amount);
            // Validate UPI ID, initiate transfer...
            
        } else if (paymentType.equals("WALLET")) {
            String walletId = details.get("walletId");
            // Wallet processing logic
            System.out.println("Processing wallet payment: " + amount);
            // Check balance, deduct...
            
        }
        // To add NET_BANKING, you must MODIFY this class!
        // What if the new else-if breaks the credit card flow?
    }
}
```

---

### GOOD Example: Strategy Pattern (OCP-Compliant)

```java
// --- Strategy Interface ---
public interface PaymentStrategy {
    void validate(PaymentDetails details);
    PaymentResult pay(double amount, PaymentDetails details);
    String getPaymentType();
}

// --- Immutable payment details ---
public record PaymentDetails(Map<String, String> attributes) {
    public String get(String key) {
        return attributes.getOrDefault(key, "");
    }
}

public record PaymentResult(boolean success, String transactionId, String message) {}

// --- Concrete strategies (each can be added WITHOUT modifying existing code) ---

public class CreditCardPayment implements PaymentStrategy {
    
    @Override
    public void validate(PaymentDetails details) {
        String cardNumber = details.get("cardNumber");
        if (cardNumber == null || cardNumber.length() != 16) {
            throw new IllegalArgumentException("Invalid card number");
        }
        if (details.get("cvv") == null || details.get("cvv").length() != 3) {
            throw new IllegalArgumentException("Invalid CVV");
        }
    }
    
    @Override
    public PaymentResult pay(double amount, PaymentDetails details) {
        validate(details);
        // Charge via payment gateway
        String txnId = "CC-" + UUID.randomUUID().toString().substring(0, 8);
        System.out.println("Charged " + amount + " to card ending " + 
            details.get("cardNumber").substring(12));
        return new PaymentResult(true, txnId, "Credit card payment successful");
    }
    
    @Override
    public String getPaymentType() { return "CREDIT_CARD"; }
}

public class UPIPayment implements PaymentStrategy {
    
    @Override
    public void validate(PaymentDetails details) {
        String upiId = details.get("upiId");
        if (upiId == null || !upiId.contains("@")) {
            throw new IllegalArgumentException("Invalid UPI ID");
        }
    }
    
    @Override
    public PaymentResult pay(double amount, PaymentDetails details) {
        validate(details);
        String txnId = "UPI-" + UUID.randomUUID().toString().substring(0, 8);
        System.out.println("UPI transfer of " + amount + " to " + details.get("upiId"));
        return new PaymentResult(true, txnId, "UPI payment successful");
    }
    
    @Override
    public String getPaymentType() { return "UPI"; }
}

public class WalletPayment implements PaymentStrategy {
    
    @Override
    public void validate(PaymentDetails details) {
        if (details.get("walletId") == null) {
            throw new IllegalArgumentException("Wallet ID required");
        }
    }
    
    @Override
    public PaymentResult pay(double amount, PaymentDetails details) {
        validate(details);
        String txnId = "WAL-" + UUID.randomUUID().toString().substring(0, 8);
        System.out.println("Deducted " + amount + " from wallet " + details.get("walletId"));
        return new PaymentResult(true, txnId, "Wallet payment successful");
    }
    
    @Override
    public String getPaymentType() { return "WALLET"; }
}

// --- PaymentProcessor is now CLOSED for modification ---
public class PaymentProcessor {
    private final Map<String, PaymentStrategy> strategies = new HashMap<>();
    
    public PaymentProcessor(List<PaymentStrategy> strategyList) {
        for (PaymentStrategy strategy : strategyList) {
            strategies.put(strategy.getPaymentType(), strategy);
        }
    }
    
    public PaymentResult processPayment(String paymentType, double amount, PaymentDetails details) {
        PaymentStrategy strategy = strategies.get(paymentType);
        if (strategy == null) {
            throw new UnsupportedOperationException("Payment type not supported: " + paymentType);
        }
        return strategy.pay(amount, details);
    }
}

// --- Adding NetBanking requires ZERO modification to existing classes ---
public class NetBankingPayment implements PaymentStrategy {
    @Override
    public void validate(PaymentDetails details) {
        if (details.get("bankCode") == null) {
            throw new IllegalArgumentException("Bank code required");
        }
    }
    
    @Override
    public PaymentResult pay(double amount, PaymentDetails details) {
        validate(details);
        String txnId = "NB-" + UUID.randomUUID().toString().substring(0, 8);
        return new PaymentResult(true, txnId, "Net banking payment successful");
    }
    
    @Override
    public String getPaymentType() { return "NET_BANKING"; }
}
```

### Real LLD Application: Notification System

```java
// Adding Slack/Push/WhatsApp notification requires NO modification to NotificationService

public interface NotificationChannel {
    void send(String recipient, String message);
    boolean supports(String channelType);
}

public class EmailNotification implements NotificationChannel {
    public void send(String recipient, String message) {
        System.out.println("Email to " + recipient + ": " + message);
    }
    public boolean supports(String channelType) { return "EMAIL".equals(channelType); }
}

public class SMSNotification implements NotificationChannel {
    public void send(String recipient, String message) {
        System.out.println("SMS to " + recipient + ": " + message);
    }
    public boolean supports(String channelType) { return "SMS".equals(channelType); }
}

// NotificationService never needs modification
public class NotificationService {
    private final List<NotificationChannel> channels;
    
    public NotificationService(List<NotificationChannel> channels) {
        this.channels = channels;
    }
    
    public void notify(String channelType, String recipient, String message) {
        channels.stream()
            .filter(ch -> ch.supports(channelType))
            .findFirst()
            .orElseThrow(() -> new IllegalArgumentException("No channel: " + channelType))
            .send(recipient, message);
    }
}
```

---

## 3. Liskov Substitution Principle (LSP)

> **Subtypes must be substitutable for their base types without altering the correctness of the program.**

If code works with type `T`, it must also work correctly with any subtype `S extends T`.

### Rules:
1. **Preconditions cannot be strengthened** in a subtype
2. **Postconditions cannot be weakened** in a subtype
3. **Invariants of the base type must be preserved**
4. **History constraint**: Subtypes cannot add state changes the base type wouldn't allow

---

### BAD Example: Square extends Rectangle

```java
// VIOLATION: Square changes the behavior contract of Rectangle

public class Rectangle {
    protected int width;
    protected int height;
    
    public void setWidth(int width) {
        this.width = width;
    }
    
    public void setHeight(int height) {
        this.height = height;
    }
    
    public int getWidth() { return width; }
    public int getHeight() { return height; }
    
    public int area() {
        return width * height;
    }
}

public class Square extends Rectangle {
    // VIOLATION: Strengthens precondition — setting width also changes height
    @Override
    public void setWidth(int width) {
        this.width = width;
        this.height = width;  // Unexpected side effect!
    }
    
    @Override
    public void setHeight(int height) {
        this.width = height;  // Unexpected side effect!
        this.height = height;
    }
}

// This code BREAKS with Square:
public class AreaCalculatorTest {
    public static void main(String[] args) {
        Rectangle rect = new Square();  // Substitution
        rect.setWidth(5);
        rect.setHeight(3);
        
        // Developer expects: 5 * 3 = 15
        // Actual result: 3 * 3 = 9 (BROKEN!)
        assert rect.area() == 15 : "Expected 15 but got " + rect.area();
    }
}
```

---

### GOOD Example: Shape Interface

```java
// Both Rectangle and Square implement Shape independently — no broken contracts

public interface Shape {
    double area();
    double perimeter();
}

public class Rectangle implements Shape {
    private final int width;
    private final int height;
    
    public Rectangle(int width, int height) {
        this.width = width;
        this.height = height;
    }
    
    @Override
    public double area() { return width * height; }
    
    @Override
    public double perimeter() { return 2 * (width + height); }
    
    public int getWidth() { return width; }
    public int getHeight() { return height; }
}

public class Square implements Shape {
    private final int side;
    
    public Square(int side) {
        this.side = side;
    }
    
    @Override
    public double area() { return side * side; }
    
    @Override
    public double perimeter() { return 4 * side; }
    
    public int getSide() { return side; }
}

// Safe substitution — works correctly with any Shape
public class ShapeUtils {
    public static double totalArea(List<Shape> shapes) {
        return shapes.stream().mapToDouble(Shape::area).sum();
    }
    
    public static void main(String[] args) {
        List<Shape> shapes = List.of(
            new Rectangle(5, 3),
            new Square(4),
            new Rectangle(2, 7)
        );
        System.out.println("Total area: " + totalArea(shapes)); // 15 + 16 + 14 = 45
    }
}
```

---

### BAD Example: ReadOnlyList extends ArrayList

```java
// VIOLATION: Breaks the contract of List — add() is supposed to work

public class ReadOnlyList<E> extends ArrayList<E> {
    
    public ReadOnlyList(Collection<E> items) {
        super(items);
    }
    
    @Override
    public boolean add(E e) {
        throw new UnsupportedOperationException("This list is read-only");
    }
    
    @Override
    public E set(int index, E element) {
        throw new UnsupportedOperationException("This list is read-only");
    }
    
    @Override
    public E remove(int index) {
        throw new UnsupportedOperationException("This list is read-only");
    }
}

// Any code that accepts List<E> will BREAK:
public class ListProcessor {
    public static void addDefaults(List<String> list) {
        list.add("default1");  // Throws UnsupportedOperationException!
        list.add("default2");
    }
}
```

**GOOD approach:** Use `Collections.unmodifiableList()` which returns a type that clearly signals immutability, or use a separate `ReadableList` interface that doesn't promise mutability.

---

### Real LLD Application: Vehicle Hierarchy (Parking Lot)

```java
// LSP-compliant vehicle hierarchy

public abstract class Vehicle {
    private final String licensePlate;
    private final VehicleType type;
    
    protected Vehicle(String licensePlate, VehicleType type) {
        this.licensePlate = licensePlate;
        this.type = type;
    }
    
    public String getLicensePlate() { return licensePlate; }
    public VehicleType getType() { return type; }
    
    // Contract: every vehicle can report how many spots it needs
    public abstract int spotsNeeded();
}

public class Motorcycle extends Vehicle {
    public Motorcycle(String plate) { super(plate, VehicleType.MOTORCYCLE); }
    
    @Override
    public int spotsNeeded() { return 1; }  // Honors contract
}

public class Car extends Vehicle {
    public Car(String plate) { super(plate, VehicleType.CAR); }
    
    @Override
    public int spotsNeeded() { return 1; }  // Honors contract
}

public class Truck extends Vehicle {
    public Truck(String plate) { super(plate, VehicleType.TRUCK); }
    
    @Override
    public int spotsNeeded() { return 2; }  // Honors contract (needs more space)
}

// Works correctly with ANY vehicle subtype — LSP satisfied
public class ParkingFloor {
    private final List<ParkingSpot> spots;
    
    public boolean canFit(Vehicle vehicle) {
        long available = spots.stream().filter(ParkingSpot::isAvailable).count();
        return available >= vehicle.spotsNeeded();  // Substitution works!
    }
}
```

---

## 4. Interface Segregation Principle (ISP)

> **Clients should not be forced to depend on interfaces they don't use.**

Prefer many small, focused interfaces over one large "fat" interface.

---

### BAD Example: Fat Worker Interface

```java
// VIOLATION: Robot is forced to implement eat() and sleep()

public interface Worker {
    void work();
    void eat();
    void sleep();
    void attendMeeting();
}

public class HumanWorker implements Worker {
    @Override public void work() { System.out.println("Human working"); }
    @Override public void eat() { System.out.println("Human eating"); }
    @Override public void sleep() { System.out.println("Human sleeping"); }
    @Override public void attendMeeting() { System.out.println("In meeting"); }
}

public class RobotWorker implements Worker {
    @Override public void work() { System.out.println("Robot working"); }
    
    @Override public void eat() {
        // FORCED to implement — makes no sense for a robot!
        throw new UnsupportedOperationException("Robots don't eat");
    }
    
    @Override public void sleep() {
        throw new UnsupportedOperationException("Robots don't sleep");
    }
    
    @Override public void attendMeeting() {
        throw new UnsupportedOperationException("Robots don't attend meetings");
    }
}
```

---

### GOOD Example: Segregated Interfaces

```java
public interface Workable {
    void work();
}

public interface Eatable {
    void eat();
}

public interface Sleepable {
    void sleep();
}

public interface MeetingAttendee {
    void attendMeeting();
}

// Human implements all relevant interfaces
public class HumanWorker implements Workable, Eatable, Sleepable, MeetingAttendee {
    @Override public void work() { System.out.println("Human working"); }
    @Override public void eat() { System.out.println("Human eating lunch"); }
    @Override public void sleep() { System.out.println("Human sleeping"); }
    @Override public void attendMeeting() { System.out.println("In meeting"); }
}

// Robot only implements what makes sense
public class RobotWorker implements Workable {
    @Override public void work() { System.out.println("Robot working 24/7"); }
}

// Intern can work and eat but doesn't attend high-level meetings
public class InternWorker implements Workable, Eatable {
    @Override public void work() { System.out.println("Intern working on tasks"); }
    @Override public void eat() { System.out.println("Intern eating free food"); }
}

// Task scheduler only cares about Workable — doesn't pull in unnecessary dependencies
public class TaskScheduler {
    private final List<Workable> workers;
    
    public TaskScheduler(List<Workable> workers) {
        this.workers = workers;
    }
    
    public void assignWork() {
        workers.forEach(Workable::work);
    }
}
```

---

### BAD Example: MultiFunctionPrinter Interface

```java
// VIOLATION: SimplePrinter cannot fax or scan

public interface MultiFunctionDevice {
    void print(Document doc);
    void scan(Document doc);
    void fax(Document doc);
    void staple(Document doc);
}

public class SimplePrinter implements MultiFunctionDevice {
    @Override public void print(Document doc) { /* works */ }
    @Override public void scan(Document doc) { throw new UnsupportedOperationException(); }
    @Override public void fax(Document doc) { throw new UnsupportedOperationException(); }
    @Override public void staple(Document doc) { throw new UnsupportedOperationException(); }
}
```

### GOOD Example: Segregated Device Interfaces

```java
public interface Printer {
    void print(Document doc);
}

public interface Scanner {
    void scan(Document doc);
}

public interface Fax {
    void fax(Document doc);
}

// Simple printer only implements what it can do
public class SimplePrinter implements Printer {
    @Override
    public void print(Document doc) {
        System.out.println("Printing: " + doc.getTitle());
    }
}

// Advanced machine implements multiple interfaces
public class AllInOnePrinter implements Printer, Scanner, Fax {
    @Override public void print(Document doc) { System.out.println("Printing: " + doc.getTitle()); }
    @Override public void scan(Document doc) { System.out.println("Scanning: " + doc.getTitle()); }
    @Override public void fax(Document doc) { System.out.println("Faxing: " + doc.getTitle()); }
}

// Client code only depends on what it needs
public class PrintJob {
    private final Printer printer;
    
    public PrintJob(Printer printer) {
        this.printer = printer;  // Works with SimplePrinter OR AllInOnePrinter
    }
    
    public void execute(Document doc) {
        printer.print(doc);
    }
}
```

### Real LLD Application: File System Design

```java
public interface Readable {
    byte[] read();
    String getContent();
}

public interface Writable {
    void write(byte[] data);
    void append(byte[] data);
}

public interface Executable {
    int execute(String[] args);
}

// Regular file: readable and writable
public class TextFile implements Readable, Writable {
    private byte[] content = new byte[0];
    
    @Override public byte[] read() { return content.clone(); }
    @Override public String getContent() { return new String(content); }
    @Override public void write(byte[] data) { this.content = data.clone(); }
    @Override public void append(byte[] data) {
        byte[] newContent = new byte[content.length + data.length];
        System.arraycopy(content, 0, newContent, 0, content.length);
        System.arraycopy(data, 0, newContent, content.length, data.length);
        this.content = newContent;
    }
}

// Script: readable, writable, and executable
public class ScriptFile implements Readable, Writable, Executable {
    private byte[] content = new byte[0];
    
    @Override public byte[] read() { return content.clone(); }
    @Override public String getContent() { return new String(content); }
    @Override public void write(byte[] data) { this.content = data.clone(); }
    @Override public void append(byte[] data) { /* ... */ }
    @Override public int execute(String[] args) {
        System.out.println("Executing script with args: " + Arrays.toString(args));
        return 0;
    }
}

// Read-only system file: only readable
public class SystemConfigFile implements Readable {
    private final byte[] content;
    
    public SystemConfigFile(byte[] content) { this.content = content.clone(); }
    @Override public byte[] read() { return content.clone(); }
    @Override public String getContent() { return new String(content); }
}
```

---

## 5. Dependency Inversion Principle (DIP)

> **High-level modules should not depend on low-level modules. Both should depend on abstractions.**
> **Abstractions should not depend on details. Details should depend on abstractions.**

---

### BAD Example: Direct Dependency on Concrete Class

```java
// VIOLATION: OrderService (high-level) directly depends on MySQLDatabase (low-level)
// Cannot switch to MongoDB, cannot unit test without a real DB

public class MySQLDatabase {
    public void save(String table, Map<String, Object> data) {
        System.out.println("Saving to MySQL table: " + table);
        // Real MySQL connection, queries, etc.
    }
    
    public List<Map<String, Object>> query(String sql) {
        System.out.println("Querying MySQL: " + sql);
        return new ArrayList<>();
    }
}

public class OrderService {
    // DIRECT dependency on concrete implementation
    private final MySQLDatabase database = new MySQLDatabase();
    
    public void placeOrder(Order order) {
        // Business logic...
        Map<String, Object> data = Map.of(
            "id", order.getId(),
            "total", order.getTotal(),
            "status", "PLACED"
        );
        database.save("orders", data);  // Tightly coupled to MySQL!
    }
    
    public List<Order> getOrdersByCustomer(int customerId) {
        // Tightly coupled to SQL syntax!
        List<Map<String, Object>> results = database.query(
            "SELECT * FROM orders WHERE customer_id = " + customerId
        );
        // map results to Order objects...
        return new ArrayList<>();
    }
}
```

**Problems:**
- Cannot switch to MongoDB or in-memory DB without modifying `OrderService`
- Cannot unit test without a running MySQL instance
- Business logic is coupled to persistence details

---

### GOOD Example: Depend on Abstractions

```java
// --- Abstraction (owned by the high-level module) ---
public interface OrderRepository {
    void save(Order order);
    Optional<Order> findById(String orderId);
    List<Order> findByCustomerId(int customerId);
    void updateStatus(String orderId, OrderStatus status);
}

// --- High-level module depends ONLY on the abstraction ---
public class OrderService {
    private final OrderRepository orderRepository;
    private final PaymentStrategy paymentStrategy;
    private final NotificationChannel notificationChannel;
    
    // Constructor Injection — dependencies provided from outside
    public OrderService(OrderRepository orderRepository, 
                        PaymentStrategy paymentStrategy,
                        NotificationChannel notificationChannel) {
        this.orderRepository = orderRepository;
        this.paymentStrategy = paymentStrategy;
        this.notificationChannel = notificationChannel;
    }
    
    public Order placeOrder(int customerId, List<OrderItem> items) {
        Order order = new Order(UUID.randomUUID().toString(), customerId, items);
        order.setStatus(OrderStatus.PLACED);
        
        // Uses abstraction — doesn't know or care about MySQL vs Mongo
        orderRepository.save(order);
        
        PaymentResult result = paymentStrategy.pay(
            order.getTotal(), new PaymentDetails(Map.of())
        );
        
        if (result.success()) {
            order.setStatus(OrderStatus.CONFIRMED);
            orderRepository.updateStatus(order.getId(), OrderStatus.CONFIRMED);
            notificationChannel.send(
                String.valueOf(customerId), "Order " + order.getId() + " confirmed!"
            );
        }
        
        return order;
    }
}

// --- Low-level module 1: MySQL implementation ---
public class MySQLOrderRepository implements OrderRepository {
    private final DataSource dataSource;
    
    public MySQLOrderRepository(DataSource dataSource) {
        this.dataSource = dataSource;
    }
    
    @Override
    public void save(Order order) {
        try (Connection conn = dataSource.getConnection()) {
            PreparedStatement stmt = conn.prepareStatement(
                "INSERT INTO orders (id, customer_id, total, status) VALUES (?, ?, ?, ?)"
            );
            stmt.setString(1, order.getId());
            stmt.setInt(2, order.getCustomerId());
            stmt.setDouble(3, order.getTotal());
            stmt.setString(4, order.getStatus().name());
            stmt.executeUpdate();
        } catch (SQLException e) {
            throw new PersistenceException("Failed to save order", e);
        }
    }
    
    @Override
    public Optional<Order> findById(String orderId) { /* SQL query */ return Optional.empty(); }
    
    @Override
    public List<Order> findByCustomerId(int customerId) { /* SQL query */ return List.of(); }
    
    @Override
    public void updateStatus(String orderId, OrderStatus status) { /* SQL update */ }
}

// --- Low-level module 2: MongoDB implementation ---
public class MongoOrderRepository implements OrderRepository {
    private final MongoCollection<Document> collection;
    
    public MongoOrderRepository(MongoDatabase db) {
        this.collection = db.getCollection("orders");
    }
    
    @Override
    public void save(Order order) {
        Document doc = new Document()
            .append("_id", order.getId())
            .append("customerId", order.getCustomerId())
            .append("total", order.getTotal())
            .append("status", order.getStatus().name());
        collection.insertOne(doc);
    }
    
    @Override
    public Optional<Order> findById(String orderId) { /* Mongo query */ return Optional.empty(); }
    
    @Override
    public List<Order> findByCustomerId(int customerId) { /* Mongo query */ return List.of(); }
    
    @Override
    public void updateStatus(String orderId, OrderStatus status) { /* Mongo update */ }
}

// --- Low-level module 3: In-memory (for testing) ---
public class InMemoryOrderRepository implements OrderRepository {
    private final Map<String, Order> store = new ConcurrentHashMap<>();
    
    @Override
    public void save(Order order) { store.put(order.getId(), order); }
    
    @Override
    public Optional<Order> findById(String orderId) { return Optional.ofNullable(store.get(orderId)); }
    
    @Override
    public List<Order> findByCustomerId(int customerId) {
        return store.values().stream()
            .filter(o -> o.getCustomerId() == customerId)
            .collect(Collectors.toList());
    }
    
    @Override
    public void updateStatus(String orderId, OrderStatus status) {
        store.computeIfPresent(orderId, (id, order) -> { order.setStatus(status); return order; });
    }
}

// --- Wiring (composition root) ---
public class Application {
    public static void main(String[] args) {
        // Swap implementations without changing OrderService
        OrderRepository repo = new InMemoryOrderRepository();
        PaymentStrategy payment = new UPIPayment();
        NotificationChannel notification = new SMSNotification();
        
        OrderService service = new OrderService(repo, payment, notification);
        service.placeOrder(1, List.of(new OrderItem("Widget", 2, 29.99)));
    }
}
```

### Real LLD Application: Ride-sharing Pricing

```java
// RideService depends on PricingStrategy abstraction, not SurgePricing concrete

public interface PricingStrategy {
    double calculateFare(Ride ride);
}

public class BasePricing implements PricingStrategy {
    private static final double BASE_FARE = 50.0;
    private static final double PER_KM = 12.0;
    
    @Override
    public double calculateFare(Ride ride) {
        return BASE_FARE + (ride.getDistanceKm() * PER_KM);
    }
}

public class SurgePricing implements PricingStrategy {
    private final PricingStrategy basePricing;
    private final double surgeMultiplier;
    
    public SurgePricing(PricingStrategy basePricing, double surgeMultiplier) {
        this.basePricing = basePricing;
        this.surgeMultiplier = surgeMultiplier;
    }
    
    @Override
    public double calculateFare(Ride ride) {
        return basePricing.calculateFare(ride) * surgeMultiplier;
    }
}

public class RideService {
    private final PricingStrategy pricingStrategy;  // Abstraction, not concrete
    
    public RideService(PricingStrategy pricingStrategy) {
        this.pricingStrategy = pricingStrategy;
    }
    
    public double estimateFare(Ride ride) {
        return pricingStrategy.calculateFare(ride);
    }
}
```

---

## 6. Additional Clean Code Principles for LLD

### DRY (Don't Repeat Yourself)

> Extract common logic into utility or base classes.

```java
// BAD: Duplicated validation in multiple services
public class UserService {
    public void createUser(String email) {
        if (email == null || !email.contains("@") || email.length() > 255) {
            throw new IllegalArgumentException("Invalid email");
        }
        // create user...
    }
}

public class NewsletterService {
    public void subscribe(String email) {
        // SAME validation duplicated!
        if (email == null || !email.contains("@") || email.length() > 255) {
            throw new IllegalArgumentException("Invalid email");
        }
        // subscribe...
    }
}

// GOOD: Extract into reusable validator
public class EmailValidator {
    private static final int MAX_LENGTH = 255;
    private static final Pattern EMAIL_PATTERN = Pattern.compile("^[\\w.-]+@[\\w.-]+\\.[a-zA-Z]{2,}$");
    
    public static void validate(String email) {
        if (email == null || email.isBlank()) {
            throw new IllegalArgumentException("Email cannot be empty");
        }
        if (email.length() > MAX_LENGTH) {
            throw new IllegalArgumentException("Email too long");
        }
        if (!EMAIL_PATTERN.matcher(email).matches()) {
            throw new IllegalArgumentException("Invalid email format: " + email);
        }
    }
}
```

#### Template Method Pattern (DRY for algorithms)

```java
// Common algorithm structure extracted into base class
public abstract class DataExporter {
    
    // Template method — defines the algorithm skeleton
    public final void export(List<Record> records, String destination) {
        List<Record> filtered = filterRecords(records);
        String formatted = formatRecords(filtered);
        writeToDestination(formatted, destination);
        logCompletion(destination, filtered.size());
    }
    
    // Common step
    private List<Record> filterRecords(List<Record> records) {
        return records.stream().filter(Record::isValid).collect(Collectors.toList());
    }
    
    // Vary per subclass
    protected abstract String formatRecords(List<Record> records);
    protected abstract void writeToDestination(String data, String destination);
    
    // Common step
    private void logCompletion(String destination, int count) {
        System.out.println("Exported " + count + " records to " + destination);
    }
}

public class CsvExporter extends DataExporter {
    @Override
    protected String formatRecords(List<Record> records) {
        StringBuilder sb = new StringBuilder("id,name,value\n");
        records.forEach(r -> sb.append(r.id()).append(",").append(r.name())
            .append(",").append(r.value()).append("\n"));
        return sb.toString();
    }
    
    @Override
    protected void writeToDestination(String data, String destination) {
        // Write CSV to file
    }
}

public class JsonExporter extends DataExporter {
    @Override
    protected String formatRecords(List<Record> records) {
        // Format as JSON array
        return "[" + records.stream()
            .map(r -> String.format("{\"id\":%d,\"name\":\"%s\"}", r.id(), r.name()))
            .collect(Collectors.joining(",")) + "]";
    }
    
    @Override
    protected void writeToDestination(String data, String destination) {
        // Write JSON to file or API
    }
}
```

---

### KISS (Keep It Simple, Stupid)

```java
// BAD: Overly "clever" one-liner
public boolean isEligible(User u) {
    return u != null && u.getAge() >= 18 && u.getStatus() != null 
        && !u.getStatus().equals("BANNED") && u.getEmailVerified() 
        && (u.getSubscription() == null || !u.getSubscription().isExpired());
}

// GOOD: Simple, readable, each condition has a clear meaning
public boolean isEligible(User user) {
    if (user == null) return false;
    if (user.getAge() < 18) return false;
    if (user.isBanned()) return false;
    if (!user.isEmailVerified()) return false;
    if (user.hasExpiredSubscription()) return false;
    return true;
}
```

---

### YAGNI (You Ain't Gonna Need It)

```java
// BAD: Adding abstractions for hypothetical future needs
public interface MessageBroker { }
public interface MessageSerializer { }
public interface MessageEncryptor { }
public abstract class AbstractMessageProcessor { }
// ... all this when the current requirement is just "log messages to console"

// GOOD: Solve today's problem. Refactor when (if) new requirements arrive.
public class ConsoleLogger {
    public void log(String level, String message) {
        System.out.printf("[%s] %s: %s%n", LocalDateTime.now(), level, message);
    }
}
```

---

### Composition over Inheritance

> Prefer composing objects with behaviors over deep inheritance trees.

```java
// BAD: Deep, rigid inheritance hierarchy
abstract class Bird { }
abstract class FlyingBird extends Bird {
    void fly() { System.out.println("Flying"); }
}
abstract class SwimmingBird extends Bird {
    void swim() { System.out.println("Swimming"); }
}
// Problem: Duck can BOTH fly and swim — can't extend two classes!
// class Duck extends FlyingBird, SwimmingBird {} // IMPOSSIBLE in Java

// GOOD: Compose behaviors using interfaces + strategy
public interface FlyBehavior {
    void fly();
}

public interface SwimBehavior {
    void swim();
}

public interface QuackBehavior {
    void quack();
}

// Concrete behaviors
public class StandardFly implements FlyBehavior {
    @Override public void fly() { System.out.println("Flying with wings"); }
}

public class NoFly implements FlyBehavior {
    @Override public void fly() { System.out.println("Can't fly"); }
}

public class StandardSwim implements SwimBehavior {
    @Override public void swim() { System.out.println("Swimming in water"); }
}

public class NoSwim implements SwimBehavior {
    @Override public void swim() { System.out.println("Can't swim"); }
}

public class LoudQuack implements QuackBehavior {
    @Override public void quack() { System.out.println("QUACK!"); }
}

public class SilentQuack implements QuackBehavior {
    @Override public void quack() { /* silence */ }
}

// Birds are COMPOSED of behaviors
public class Bird {
    private final String name;
    private FlyBehavior flyBehavior;
    private SwimBehavior swimBehavior;
    private QuackBehavior quackBehavior;
    
    public Bird(String name, FlyBehavior fly, SwimBehavior swim, QuackBehavior quack) {
        this.name = name;
        this.flyBehavior = fly;
        this.swimBehavior = swim;
        this.quackBehavior = quack;
    }
    
    public void performFly() { flyBehavior.fly(); }
    public void performSwim() { swimBehavior.swim(); }
    public void performQuack() { quackBehavior.quack(); }
    
    // Can even change behavior at runtime!
    public void setFlyBehavior(FlyBehavior fb) { this.flyBehavior = fb; }
}

// Usage — flexible creation of any bird type
public class BirdSimulator {
    public static void main(String[] args) {
        Bird duck = new Bird("Duck", new StandardFly(), new StandardSwim(), new LoudQuack());
        Bird penguin = new Bird("Penguin", new NoFly(), new StandardSwim(), new SilentQuack());
        Bird sparrow = new Bird("Sparrow", new StandardFly(), new NoSwim(), new LoudQuack());
        
        duck.performFly();    // Flying with wings
        penguin.performFly(); // Can't fly
        penguin.performSwim(); // Swimming in water
    }
}
```

---

### Law of Demeter (Principle of Least Knowledge)

> A method should only talk to its immediate friends, not strangers.

```java
// BAD: Train wreck — reaching deep into object graph
public class OrderProcessor {
    public String getDeliveryCity(Order order) {
        // Violates Law of Demeter: navigating 4 levels deep
        return order.getCustomer().getAddress().getCity().getName();
        // What if any of these returns null? What if Address structure changes?
    }
}

// GOOD: Ask the object directly — it delegates internally
public class Order {
    private final Customer customer;
    private final Address deliveryAddress;
    
    public String getDeliveryCity() {
        return deliveryAddress.getCityName();  // Order knows its own delivery info
    }
    
    public String getDeliveryZipCode() {
        return deliveryAddress.getZipCode();
    }
}

public class Address {
    private final String street;
    private final String cityName;
    private final String zipCode;
    
    public String getCityName() { return cityName; }
    public String getZipCode() { return zipCode; }
}

// Now the processor only talks to its direct collaborator
public class OrderProcessor {
    public String getDeliveryCity(Order order) {
        return order.getDeliveryCity();  // Clean, one level deep
    }
}
```

---

### Tell, Don't Ask

> Don't extract data from an object to make decisions externally. Tell the object what to do.

```java
// BAD: Asking for state, then making decisions externally
public class TransferService {
    public void transfer(Account from, Account to, double amount) {
        // ASKING the object for its internals
        if (from.getBalance() >= amount) {
            from.setBalance(from.getBalance() - amount);
            to.setBalance(to.getBalance() + amount);
        } else {
            throw new InsufficientFundsException("Not enough balance");
        }
    }
}

// GOOD: Tell the object to do its own job
public class Account {
    private double balance;
    private final String accountId;
    
    public Account(String accountId, double initialBalance) {
        this.accountId = accountId;
        this.balance = initialBalance;
    }
    
    // Object manages its own state and rules
    public void withdraw(double amount) {
        if (amount <= 0) throw new IllegalArgumentException("Amount must be positive");
        if (balance < amount) throw new InsufficientFundsException(
            "Account " + accountId + " has insufficient funds"
        );
        balance -= amount;
    }
    
    public void deposit(double amount) {
        if (amount <= 0) throw new IllegalArgumentException("Amount must be positive");
        balance += amount;
    }
    
    public double getBalance() { return balance; }  // Read-only exposure is fine
}

// Transfer service just TELLS the objects what to do
public class TransferService {
    public void transfer(Account from, Account to, double amount) {
        from.withdraw(amount);   // Account handles its own validation
        to.deposit(amount);      // Account handles its own logic
    }
}
```

---

## 7. Applying SOLID in LLD Interview

### Step-by-Step Approach

| Step | Principle | Action |
|------|-----------|--------|
| 1 | - | Identify entities (nouns from requirements) |
| 2 | SRP | Assign one responsibility per class |
| 3 | ISP | Define small, focused interfaces |
| 4 | DIP | High-level modules depend on abstractions |
| 5 | OCP | Use strategy/factory for extensibility |
| 6 | LSP | Verify all subtypes honor contracts |

---

### Complete Mini LLD: Notification System

**Requirements:** Send notifications via Email, SMS, Push, and Slack. Support message templates. Allow retry on failure. Easy to add new channels.

```java
import java.util.*;
import java.time.LocalDateTime;

// --- Core abstractions (ISP + DIP) ---

public interface NotificationSender {
    void send(String recipient, NotificationMessage message);
    String getChannelType();
}

public record NotificationMessage(String subject, String body, Priority priority) {
    public enum Priority { LOW, MEDIUM, HIGH, CRITICAL }
}

// --- Concrete senders (OCP: add new channels without modifying existing code) ---

public class EmailSender implements NotificationSender {
    @Override
    public void send(String recipient, NotificationMessage message) {
        System.out.printf("[EMAIL] To: %s | Subject: %s | Body: %s%n",
            recipient, message.subject(), message.body());
    }
    @Override public String getChannelType() { return "EMAIL"; }
}

public class SmsSender implements NotificationSender {
    @Override
    public void send(String recipient, NotificationMessage message) {
        System.out.printf("[SMS] To: %s | %s%n", recipient, message.body());
    }
    @Override public String getChannelType() { return "SMS"; }
}

public class PushSender implements NotificationSender {
    @Override
    public void send(String recipient, NotificationMessage message) {
        System.out.printf("[PUSH] Device: %s | Title: %s | Body: %s%n",
            recipient, message.subject(), message.body());
    }
    @Override public String getChannelType() { return "PUSH"; }
}

public class SlackSender implements NotificationSender {
    @Override
    public void send(String recipient, NotificationMessage message) {
        System.out.printf("[SLACK] Channel: %s | %s: %s%n",
            recipient, message.subject(), message.body());
    }
    @Override public String getChannelType() { return "SLACK"; }
}

// --- Template engine (SRP: only handles message formatting) ---

public class MessageTemplateEngine {
    private final Map<String, String> templates = new HashMap<>();
    
    public void registerTemplate(String name, String template) {
        templates.put(name, template);
    }
    
    public String render(String templateName, Map<String, String> variables) {
        String template = templates.getOrDefault(templateName, templateName);
        String result = template;
        for (Map.Entry<String, String> entry : variables.entrySet()) {
            result = result.replace("{{" + entry.getKey() + "}}", entry.getValue());
        }
        return result;
    }
}

// --- Retry logic (SRP: only handles retry) ---

public class RetryHandler {
    private final int maxRetries;
    private final long delayMs;
    
    public RetryHandler(int maxRetries, long delayMs) {
        this.maxRetries = maxRetries;
        this.delayMs = delayMs;
    }
    
    public boolean executeWithRetry(Runnable action) {
        for (int attempt = 1; attempt <= maxRetries; attempt++) {
            try {
                action.run();
                return true;
            } catch (Exception e) {
                System.out.println("Attempt " + attempt + " failed: " + e.getMessage());
                if (attempt < maxRetries) {
                    try { Thread.sleep(delayMs); } catch (InterruptedException ie) { break; }
                }
            }
        }
        return false;
    }
}

// --- Notification Service (orchestrator — DIP: depends on abstractions) ---

public class NotificationService {
    private final Map<String, NotificationSender> senders = new HashMap<>();
    private final RetryHandler retryHandler;
    private final MessageTemplateEngine templateEngine;
    
    public NotificationService(List<NotificationSender> senderList,
                               RetryHandler retryHandler,
                               MessageTemplateEngine templateEngine) {
        for (NotificationSender sender : senderList) {
            senders.put(sender.getChannelType(), sender);
        }
        this.retryHandler = retryHandler;
        this.templateEngine = templateEngine;
    }
    
    public void sendNotification(String channel, String recipient,
                                  String templateName, Map<String, String> vars,
                                  NotificationMessage.Priority priority) {
        NotificationSender sender = senders.get(channel);
        if (sender == null) {
            throw new IllegalArgumentException("Unsupported channel: " + channel);
        }
        
        String body = templateEngine.render(templateName, vars);
        NotificationMessage message = new NotificationMessage(templateName, body, priority);
        
        boolean success = retryHandler.executeWithRetry(() -> sender.send(recipient, message));
        if (!success) {
            System.out.println("FAILED to send notification after retries: " + channel + " -> " + recipient);
        }
    }
}

// --- Main: Wiring everything together ---

public class NotificationApp {
    public static void main(String[] args) {
        // Setup template engine
        MessageTemplateEngine templateEngine = new MessageTemplateEngine();
        templateEngine.registerTemplate("welcome", "Hello {{name}}, welcome to {{platform}}!");
        templateEngine.registerTemplate("order_shipped", "Your order {{orderId}} has been shipped.");
        
        // Setup senders (add new ones here — OCP)
        List<NotificationSender> senders = List.of(
            new EmailSender(),
            new SmsSender(),
            new PushSender(),
            new SlackSender()
        );
        
        // Setup retry
        RetryHandler retryHandler = new RetryHandler(3, 1000);
        
        // Create service
        NotificationService service = new NotificationService(senders, retryHandler, templateEngine);
        
        // Send notifications
        service.sendNotification("EMAIL", "user@example.com", "welcome",
            Map.of("name", "Alice", "platform", "MyApp"),
            NotificationMessage.Priority.MEDIUM);
        
        service.sendNotification("SMS", "+1234567890", "order_shipped",
            Map.of("orderId", "ORD-9876"),
            NotificationMessage.Priority.HIGH);
        
        service.sendNotification("SLACK", "#engineering", "welcome",
            Map.of("name", "Bob", "platform", "Slack"),
            NotificationMessage.Priority.LOW);
    }
}
```

---

### Complete Mini LLD: Logger System

**Requirements:** Log to Console, File, Database. Support log levels (DEBUG, INFO, WARN, ERROR). Filter by level. Easy to add new destinations.

```java
import java.util.*;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;

// --- Log level enum ---
public enum LogLevel {
    DEBUG(0), INFO(1), WARN(2), ERROR(3);
    
    private final int severity;
    LogLevel(int severity) { this.severity = severity; }
    public int getSeverity() { return severity; }
    
    public boolean isAtLeast(LogLevel minimum) {
        return this.severity >= minimum.severity;
    }
}

// --- Log entry (immutable value object) ---
public record LogEntry(
    LocalDateTime timestamp,
    LogLevel level,
    String source,
    String message,
    Throwable exception
) {
    public LogEntry(LogLevel level, String source, String message) {
        this(LocalDateTime.now(), level, source, message, null);
    }
    
    public LogEntry(LogLevel level, String source, String message, Throwable exception) {
        this(LocalDateTime.now(), level, source, message, exception);
    }
}

// --- Log destination abstraction (ISP: focused interface) ---
public interface LogDestination {
    void write(LogEntry entry);
    void flush();
}

// --- Log formatter abstraction (SRP: only formatting) ---
public interface LogFormatter {
    String format(LogEntry entry);
}

// --- Concrete formatters ---
public class SimpleFormatter implements LogFormatter {
    private static final DateTimeFormatter DTF = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");
    
    @Override
    public String format(LogEntry entry) {
        String base = String.format("[%s] [%s] [%s] %s",
            entry.timestamp().format(DTF),
            entry.level(),
            entry.source(),
            entry.message());
        if (entry.exception() != null) {
            base += " | Exception: " + entry.exception().getMessage();
        }
        return base;
    }
}

public class JsonFormatter implements LogFormatter {
    @Override
    public String format(LogEntry entry) {
        return String.format(
            "{\"timestamp\":\"%s\",\"level\":\"%s\",\"source\":\"%s\",\"message\":\"%s\"}",
            entry.timestamp(), entry.level(), entry.source(),
            entry.message().replace("\"", "\\\""));
    }
}

// --- Concrete destinations (OCP: add new ones without changing Logger) ---

public class ConsoleLogDestination implements LogDestination {
    private final LogFormatter formatter;
    
    public ConsoleLogDestination(LogFormatter formatter) {
        this.formatter = formatter;
    }
    
    @Override
    public void write(LogEntry entry) {
        String formatted = formatter.format(entry);
        if (entry.level() == LogLevel.ERROR) {
            System.err.println(formatted);
        } else {
            System.out.println(formatted);
        }
    }
    
    @Override
    public void flush() { System.out.flush(); }
}

public class FileLogDestination implements LogDestination {
    private final LogFormatter formatter;
    private final String filePath;
    private final List<String> buffer = new ArrayList<>();
    
    public FileLogDestination(LogFormatter formatter, String filePath) {
        this.formatter = formatter;
        this.filePath = filePath;
    }
    
    @Override
    public void write(LogEntry entry) {
        buffer.add(formatter.format(entry));
        if (buffer.size() >= 10) {
            flush();
        }
    }
    
    @Override
    public void flush() {
        // In real code: write buffer to file
        System.out.println("[FILE:" + filePath + "] Flushing " + buffer.size() + " entries");
        buffer.clear();
    }
}

public class DatabaseLogDestination implements LogDestination {
    private final String connectionString;
    
    public DatabaseLogDestination(String connectionString) {
        this.connectionString = connectionString;
    }
    
    @Override
    public void write(LogEntry entry) {
        // In real code: INSERT INTO logs (timestamp, level, source, message) VALUES (...)
        System.out.printf("[DB] INSERT log: level=%s, source=%s, msg=%s%n",
            entry.level(), entry.source(), entry.message());
    }
    
    @Override
    public void flush() { /* commit transaction */ }
}

// --- Logger (DIP: depends on abstractions, SRP: only routing) ---

public class Logger {
    private final String name;
    private final LogLevel minimumLevel;
    private final List<LogDestination> destinations;
    
    public Logger(String name, LogLevel minimumLevel, List<LogDestination> destinations) {
        this.name = name;
        this.minimumLevel = minimumLevel;
        this.destinations = destinations;
    }
    
    public void debug(String message) { log(LogLevel.DEBUG, message); }
    public void info(String message) { log(LogLevel.INFO, message); }
    public void warn(String message) { log(LogLevel.WARN, message); }
    public void error(String message) { log(LogLevel.ERROR, message); }
    public void error(String message, Throwable ex) { log(LogLevel.ERROR, message, ex); }
    
    private void log(LogLevel level, String message) {
        log(level, message, null);
    }
    
    private void log(LogLevel level, String message, Throwable exception) {
        if (!level.isAtLeast(minimumLevel)) return;
        
        LogEntry entry = (exception != null)
            ? new LogEntry(level, name, message, exception)
            : new LogEntry(level, name, message);
        
        for (LogDestination dest : destinations) {
            dest.write(entry);
        }
    }
    
    public void flush() {
        destinations.forEach(LogDestination::flush);
    }
}

// --- Logger factory (creates pre-configured loggers) ---

public class LoggerFactory {
    private static final List<LogDestination> defaultDestinations = new ArrayList<>();
    private static LogLevel defaultLevel = LogLevel.INFO;
    
    public static void configure(LogLevel level, List<LogDestination> destinations) {
        defaultLevel = level;
        defaultDestinations.clear();
        defaultDestinations.addAll(destinations);
    }
    
    public static Logger getLogger(String name) {
        return new Logger(name, defaultLevel, new ArrayList<>(defaultDestinations));
    }
    
    public static Logger getLogger(Class<?> clazz) {
        return getLogger(clazz.getSimpleName());
    }
}

// --- Main ---

public class LoggerApp {
    public static void main(String[] args) {
        // Configure destinations
        LogFormatter simpleFormatter = new SimpleFormatter();
        LogFormatter jsonFormatter = new JsonFormatter();
        
        List<LogDestination> destinations = List.of(
            new ConsoleLogDestination(simpleFormatter),
            new FileLogDestination(jsonFormatter, "/var/log/app.log"),
            new DatabaseLogDestination("jdbc:mysql://localhost/logs")
        );
        
        LoggerFactory.configure(LogLevel.DEBUG, destinations);
        
        // Use logger
        Logger logger = LoggerFactory.getLogger("OrderService");
        
        logger.debug("Processing order #12345");
        logger.info("Order placed successfully");
        logger.warn("Inventory running low for item SKU-001");
        logger.error("Payment gateway timeout", new RuntimeException("Connection refused"));
        
        logger.flush();
    }
}
```

---

## 8. Common Interview Questions

### Q1: Explain each SOLID principle with a real example

| Principle | One-liner | Real Example |
|-----------|-----------|--------------|
| SRP | One class, one reason to change | `UserRepository` (persistence), `EmailService` (notifications) |
| OCP | Extend without modifying | Strategy pattern for payments — add `CryptoPay` without changing `PaymentProcessor` |
| LSP | Subtypes honor base contracts | All `Shape` implementations correctly compute `area()` |
| ISP | Small interfaces, not fat ones | `Printer` + `Scanner` instead of `MultiFunctionDevice` |
| DIP | Depend on abstractions | `OrderService` depends on `OrderRepository` interface, not `MySQLDatabase` |

---

### Q2: How does OCP relate to Strategy pattern?

Strategy pattern is the **primary mechanism** to achieve OCP:
- Define a strategy interface (the abstraction)
- Each concrete strategy is an extension point
- The context class (e.g., `PaymentProcessor`) is closed for modification
- New behaviors are added by creating new strategy implementations

Other patterns that achieve OCP: Decorator, Observer, Factory Method, Template Method.

---

### Q3: Give an example of LSP violation

**Classic:** `Square extends Rectangle`. Calling `setWidth()` on a `Square` also changes height, which violates the `Rectangle` contract that width and height are independent.

**Practical:** `CachedRepository extends DatabaseRepository` where `CachedRepository.save()` doesn't immediately persist (postcondition weakened — caller expects data is saved after `save()` returns).

---

### Q4: When would you violate SRP intentionally?

**Pragmatism over purity:**
- **Microservice context**: In a tiny CRUD microservice, splitting `UserService` into 5 classes adds complexity for no benefit. A single `UserService` with 3 methods is fine.
- **Performance-critical paths**: Sometimes colocating logic avoids serialization/network overhead.
- **Prototype/MVP**: When validating an idea, shipping fast matters more than perfect architecture.

The key judgment: **Will this class realistically change for multiple independent reasons?** If not, don't split prematurely (YAGNI).

---

### Q5: How does DIP differ from DI?

| Aspect | Dependency Inversion (DIP) | Dependency Injection (DI) |
|--------|---------------------------|--------------------------|
| What | Design **principle** | Implementation **technique** |
| Focus | Architecture — which direction dependencies point | Mechanism — how dependencies are provided |
| Example | "OrderService depends on `OrderRepository` interface" | "Pass `MySQLOrderRepository` via constructor" |
| Without DI | You can still achieve DIP by manually creating instances at composition root |
| Without DIP | You can inject concrete classes (DI without inversion — still coupled) |

DIP says **what** to depend on (abstractions). DI says **how** to provide those dependencies (constructor, setter, framework).

Spring/Guice implement DI but the principle of DIP exists independently of any framework.

---

## Summary Cheat Sheet

```
SRP → One class = one responsibility = one reason to change
OCP → Add new behavior via new classes, not modifying old ones  
LSP → Subtype can replace base type without breaking anything
ISP → Many small interfaces > one fat interface
DIP → Depend on interfaces, not implementations

DRY → Extract duplicated logic
KISS → Readable > clever
YAGNI → Don't build for hypothetical futures
Composition > Inheritance → Favor has-a over is-a
Law of Demeter → Don't chain through object graphs
Tell Don't Ask → Let objects manage their own state
```
