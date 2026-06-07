# Design Patterns for Low-Level Design (LLD) Interviews

## Complete Java Implementations with Runnable Examples

---

## 1. CREATIONAL PATTERNS

---

### 1.1 Singleton Pattern

**Problem:** Ensure a class has only ONE instance globally, with a global access point.

**When to use in LLD:** Database connection pool, Configuration manager, Logger, Cache, Thread pool

#### Way 1: Eager Initialization

```java
public class EagerSingleton {
    // Instance created at class loading time
    private static final EagerSingleton INSTANCE = new EagerSingleton();
    
    private EagerSingleton() {
        // Private constructor prevents instantiation
    }
    
    public static EagerSingleton getInstance() {
        return INSTANCE;
    }
}
// Pros: Simple, thread-safe (JVM handles class loading)
// Cons: Instance created even if never used (wastes memory)
```

#### Way 2: Lazy Initialization (Not Thread-Safe)

```java
public class LazySingleton {
    private static LazySingleton instance;
    
    private LazySingleton() {}
    
    public static LazySingleton getInstance() {
        if (instance == null) {
            instance = new LazySingleton(); // NOT thread-safe!
        }
        return instance;
    }
}
// Cons: Two threads can both see null and create two instances
```

#### Way 3: Double-Checked Locking (Thread-Safe, Lazy)

```java
public class DCLSingleton {
    // volatile prevents instruction reordering
    private static volatile DCLSingleton instance;
    
    private DCLSingleton() {}
    
    public static DCLSingleton getInstance() {
        if (instance == null) {                    // First check (no lock)
            synchronized (DCLSingleton.class) {    // Lock
                if (instance == null) {            // Second check (with lock)
                    instance = new DCLSingleton();
                }
            }
        }
        return instance;
    }
}
// Why volatile? Without it:
// instance = new DCLSingleton() involves:
//   1. Allocate memory
//   2. Initialize object
//   3. Assign reference to instance
// JVM can reorder to 1→3→2, another thread sees non-null but uninitialized!
```

#### Way 4: Bill Pugh Singleton (RECOMMENDED)

```java
public class BillPughSingleton {
    private BillPughSingleton() {}
    
    // Inner static class - loaded only when getInstance() is called
    private static class SingletonHelper {
        private static final BillPughSingleton INSTANCE = new BillPughSingleton();
    }
    
    public static BillPughSingleton getInstance() {
        return SingletonHelper.INSTANCE;
    }
}
// Best of both worlds: Lazy + Thread-safe (JVM guarantees static init is thread-safe)
// No synchronization overhead!
```

#### Way 5: Enum Singleton (BEST - Effective Java)

```java
public enum EnumSingleton {
    INSTANCE;
    
    private int count = 0;
    
    public void doSomething() {
        count++;
        System.out.println("Count: " + count);
    }
    
    public int getCount() {
        return count;
    }
}

// Usage:
// EnumSingleton.INSTANCE.doSomething();

// Why best?
// 1. Thread-safe (enum instantiation is thread-safe by JVM spec)
// 2. Serialization-safe (enum handles it automatically)
// 3. Reflection-safe (can't create enum via reflection)
// 4. Simplest code
```

#### Breaking Singleton (and Prevention)

```java
// 1. Reflection Attack
public class SingletonBreaker {
    public static void main(String[] args) throws Exception {
        BillPughSingleton s1 = BillPughSingleton.getInstance();
        
        Constructor<BillPughSingleton> constructor = 
            BillPughSingleton.class.getDeclaredConstructor();
        constructor.setAccessible(true);
        BillPughSingleton s2 = constructor.newInstance(); // BROKEN!
        
        System.out.println(s1 == s2); // false!
    }
}

// Prevention: Throw exception in constructor
private BillPughSingleton() {
    if (SingletonHelper.INSTANCE != null) {
        throw new RuntimeException("Use getInstance()!");
    }
}

// 2. Serialization Attack
// Prevention: Implement readResolve()
private Object readResolve() {
    return getInstance();
}

// 3. Cloning Attack
// Prevention: Override clone()
@Override
protected Object clone() throws CloneNotSupportedException {
    throw new CloneNotSupportedException("Singleton cannot be cloned");
}
```

---

### 1.2 Factory Method Pattern

**Problem:** Create objects without specifying the exact class. Let subclasses decide which class to instantiate.

**When to use in LLD:** When you have multiple implementations of an interface and want to decouple creation from usage.

```java
// Step 1: Define the product interface
public interface Notification {
    void notifyUser(String message);
}

// Step 2: Concrete products
public class EmailNotification implements Notification {
    @Override
    public void notifyUser(String message) {
        System.out.println("Email: " + message);
    }
}

public class SMSNotification implements Notification {
    @Override
    public void notifyUser(String message) {
        System.out.println("SMS: " + message);
    }
}

public class PushNotification implements Notification {
    @Override
    public void notifyUser(String message) {
        System.out.println("Push: " + message);
    }
}

// Step 3: Factory
public class NotificationFactory {
    
    // Simple Factory Method
    public static Notification createNotification(String type) {
        return switch (type.toUpperCase()) {
            case "EMAIL" -> new EmailNotification();
            case "SMS" -> new SMSNotification();
            case "PUSH" -> new PushNotification();
            default -> throw new IllegalArgumentException("Unknown type: " + type);
        };
    }
}

// Step 4: Usage
public class Main {
    public static void main(String[] args) {
        Notification notification = NotificationFactory.createNotification("EMAIL");
        notification.notifyUser("Hello!"); // "Email: Hello!"
        
        Notification sms = NotificationFactory.createNotification("SMS");
        sms.notifyUser("OTP: 1234"); // "SMS: OTP: 1234"
    }
}
```

**True Factory Method Pattern (with inheritance):**

```java
// Abstract creator
public abstract class NotificationCreator {
    // Factory method - subclasses decide the type
    public abstract Notification createNotification();
    
    // Template method using the factory method
    public void sendNotification(String message) {
        Notification notification = createNotification();
        notification.notifyUser(message);
    }
}

// Concrete creators
public class EmailNotificationCreator extends NotificationCreator {
    @Override
    public Notification createNotification() {
        return new EmailNotification();
    }
}

public class SMSNotificationCreator extends NotificationCreator {
    @Override
    public Notification createNotification() {
        return new SMSNotification();
    }
}

// Usage
NotificationCreator creator = new EmailNotificationCreator();
creator.sendNotification("Welcome!"); // Uses EmailNotification internally
```

---

### 1.3 Abstract Factory Pattern

**Problem:** Create families of related objects without specifying concrete classes.

**When to use in LLD:** When system needs to work with multiple families of products (e.g., cross-platform UI, database providers).

```java
// === Product interfaces (family of related products) ===
public interface Button {
    void render();
    void onClick();
}

public interface TextField {
    void render();
    String getValue();
}

public interface Checkbox {
    void render();
    boolean isChecked();
}

// === Concrete products: Material Design family ===
public class MaterialButton implements Button {
    @Override
    public void render() {
        System.out.println("[Material Raised Button]");
    }
    @Override
    public void onClick() {
        System.out.println("Material ripple effect...");
    }
}

public class MaterialTextField implements TextField {
    @Override
    public void render() {
        System.out.println("[Material Text Field with floating label]");
    }
    @Override
    public String getValue() { return "material-input"; }
}

public class MaterialCheckbox implements Checkbox {
    @Override
    public void render() {
        System.out.println("[Material Checkbox with animation]");
    }
    @Override
    public boolean isChecked() { return false; }
}

// === Concrete products: iOS family ===
public class IOSButton implements Button {
    @Override
    public void render() {
        System.out.println("[iOS Flat Button]");
    }
    @Override
    public void onClick() {
        System.out.println("iOS haptic feedback...");
    }
}

public class IOSTextField implements TextField {
    @Override
    public void render() {
        System.out.println("[iOS Text Field with clear button]");
    }
    @Override
    public String getValue() { return "ios-input"; }
}

public class IOSCheckbox implements Checkbox {
    @Override
    public void render() {
        System.out.println("[iOS Toggle Switch]");
    }
    @Override
    public boolean isChecked() { return false; }
}

// === Abstract Factory ===
public interface UIComponentFactory {
    Button createButton();
    TextField createTextField();
    Checkbox createCheckbox();
}

// === Concrete Factories ===
public class MaterialUIFactory implements UIComponentFactory {
    @Override
    public Button createButton() { return new MaterialButton(); }
    @Override
    public TextField createTextField() { return new MaterialTextField(); }
    @Override
    public Checkbox createCheckbox() { return new MaterialCheckbox(); }
}

public class IOSUIFactory implements UIComponentFactory {
    @Override
    public Button createButton() { return new IOSButton(); }
    @Override
    public TextField createTextField() { return new IOSTextField(); }
    @Override
    public Checkbox createCheckbox() { return new IOSCheckbox(); }
}

// === Client code - works with ANY factory ===
public class LoginForm {
    private final Button submitButton;
    private final TextField usernameField;
    private final TextField passwordField;
    private final Checkbox rememberMe;
    
    public LoginForm(UIComponentFactory factory) {
        this.submitButton = factory.createButton();
        this.usernameField = factory.createTextField();
        this.passwordField = factory.createTextField();
        this.rememberMe = factory.createCheckbox();
    }
    
    public void render() {
        System.out.println("=== Login Form ===");
        usernameField.render();
        passwordField.render();
        rememberMe.render();
        submitButton.render();
    }
}

// === Usage ===
public class Main {
    public static void main(String[] args) {
        // Decide factory based on platform
        String platform = "ANDROID";
        UIComponentFactory factory = switch (platform) {
            case "ANDROID" -> new MaterialUIFactory();
            case "IOS" -> new IOSUIFactory();
            default -> throw new IllegalArgumentException("Unknown platform");
        };
        
        LoginForm form = new LoginForm(factory);
        form.render();
    }
}
```

---

### 1.4 Builder Pattern

**Problem:** Construct complex objects step-by-step. Avoid constructors with many parameters (telescoping constructor anti-pattern).

**When to use in LLD:** User profiles, Orders, Configuration objects, Query builders - any object with many optional fields.

```java
// === The Product ===
public class User {
    // Required fields
    private final String firstName;
    private final String lastName;
    private final String email;
    
    // Optional fields
    private final int age;
    private final String phone;
    private final String address;
    private final String company;
    private final List<String> roles;
    private final boolean isActive;
    private final LocalDate joinDate;
    
    // Private constructor - only Builder can create User
    private User(Builder builder) {
        this.firstName = builder.firstName;
        this.lastName = builder.lastName;
        this.email = builder.email;
        this.age = builder.age;
        this.phone = builder.phone;
        this.address = builder.address;
        this.company = builder.company;
        this.roles = builder.roles;
        this.isActive = builder.isActive;
        this.joinDate = builder.joinDate;
    }
    
    // Only getters (immutable object)
    public String getFirstName() { return firstName; }
    public String getLastName() { return lastName; }
    public String getEmail() { return email; }
    public int getAge() { return age; }
    public String getPhone() { return phone; }
    public String getAddress() { return address; }
    public String getCompany() { return company; }
    public List<String> getRoles() { return Collections.unmodifiableList(roles); }
    public boolean isActive() { return isActive; }
    public LocalDate getJoinDate() { return joinDate; }
    
    @Override
    public String toString() {
        return "User{name=%s %s, email=%s, age=%d, roles=%s}"
            .formatted(firstName, lastName, email, age, roles);
    }
    
    // === Static Builder class ===
    public static class Builder {
        // Required
        private final String firstName;
        private final String lastName;
        private final String email;
        
        // Optional with defaults
        private int age = 0;
        private String phone = "";
        private String address = "";
        private String company = "";
        private List<String> roles = new ArrayList<>();
        private boolean isActive = true;
        private LocalDate joinDate = LocalDate.now();
        
        // Builder constructor with required fields
        public Builder(String firstName, String lastName, String email) {
            this.firstName = Objects.requireNonNull(firstName);
            this.lastName = Objects.requireNonNull(lastName);
            this.email = Objects.requireNonNull(email);
        }
        
        // Fluent setters (return this)
        public Builder age(int age) {
            if (age < 0 || age > 150) throw new IllegalArgumentException("Invalid age");
            this.age = age;
            return this;
        }
        
        public Builder phone(String phone) {
            this.phone = phone;
            return this;
        }
        
        public Builder address(String address) {
            this.address = address;
            return this;
        }
        
        public Builder company(String company) {
            this.company = company;
            return this;
        }
        
        public Builder roles(List<String> roles) {
            this.roles = new ArrayList<>(roles);
            return this;
        }
        
        public Builder addRole(String role) {
            this.roles.add(role);
            return this;
        }
        
        public Builder isActive(boolean isActive) {
            this.isActive = isActive;
            return this;
        }
        
        public Builder joinDate(LocalDate joinDate) {
            this.joinDate = joinDate;
            return this;
        }
        
        // Build method - validates and creates the object
        public User build() {
            // Validation logic
            if (email != null && !email.contains("@")) {
                throw new IllegalStateException("Invalid email");
            }
            return new User(this);
        }
    }
}

// === Usage ===
public class Main {
    public static void main(String[] args) {
        // Only required fields
        User simpleUser = new User.Builder("John", "Doe", "john@email.com")
            .build();
        
        // All fields
        User fullUser = new User.Builder("Jane", "Smith", "jane@email.com")
            .age(28)
            .phone("+1-555-0100")
            .address("123 Main St, NY")
            .company("Google")
            .addRole("ADMIN")
            .addRole("USER")
            .isActive(true)
            .joinDate(LocalDate.of(2023, 1, 15))
            .build();
        
        System.out.println(fullUser);
        // User{name=Jane Smith, email=jane@email.com, age=28, roles=[ADMIN, USER]}
    }
}
```

**Builder with Director (for complex construction sequences):**

```java
public class PizzaDirector {
    public Pizza buildMargherita(Pizza.Builder builder) {
        return builder
            .size("Medium")
            .crust("Thin")
            .addTopping("Mozzarella")
            .addTopping("Tomato Sauce")
            .addTopping("Basil")
            .build();
    }
    
    public Pizza buildMeatLovers(Pizza.Builder builder) {
        return builder
            .size("Large")
            .crust("Thick")
            .addTopping("Pepperoni")
            .addTopping("Sausage")
            .addTopping("Bacon")
            .addTopping("Ham")
            .addTopping("Mozzarella")
            .build();
    }
}
```

---

### 1.5 Prototype Pattern

**Problem:** Create new objects by cloning existing ones (when creation is expensive or complex).

**When to use in LLD:** Game objects (enemies, bullets), document templates, configuration presets.

```java
// === Prototype interface ===
public interface GameUnit extends Cloneable {
    GameUnit clone();
    void setPosition(int x, int y);
    String getDetails();
}

// === Concrete prototypes ===
public class Soldier implements GameUnit {
    private String name;
    private int health;
    private int attack;
    private int defense;
    private int x, y;
    private List<String> weapons; // Deep copy needed!
    
    public Soldier(String name, int health, int attack, int defense, List<String> weapons) {
        this.name = name;
        this.health = health;
        this.attack = attack;
        this.defense = defense;
        this.weapons = new ArrayList<>(weapons);
        // Simulate expensive initialization
        System.out.println("Heavy initialization for: " + name);
    }
    
    // Copy constructor (used for cloning)
    private Soldier(Soldier other) {
        this.name = other.name;
        this.health = other.health;
        this.attack = other.attack;
        this.defense = other.defense;
        this.weapons = new ArrayList<>(other.weapons); // DEEP copy of list
        this.x = 0;
        this.y = 0;
        // NO expensive initialization!
    }
    
    @Override
    public GameUnit clone() {
        return new Soldier(this); // Uses copy constructor
    }
    
    @Override
    public void setPosition(int x, int y) {
        this.x = x;
        this.y = y;
    }
    
    @Override
    public String getDetails() {
        return "Soldier{name=%s, hp=%d, atk=%d, pos=(%d,%d), weapons=%s}"
            .formatted(name, health, attack, x, y, weapons);
    }
}

// === Prototype Registry ===
public class UnitRegistry {
    private final Map<String, GameUnit> prototypes = new HashMap<>();
    
    public void registerPrototype(String key, GameUnit prototype) {
        prototypes.put(key, prototype);
    }
    
    public GameUnit createUnit(String key) {
        GameUnit prototype = prototypes.get(key);
        if (prototype == null) {
            throw new IllegalArgumentException("Unknown unit type: " + key);
        }
        return prototype.clone();
    }
}

// === Usage ===
public class Main {
    public static void main(String[] args) {
        // Create and register prototypes (expensive - done once)
        UnitRegistry registry = new UnitRegistry();
        registry.registerPrototype("INFANTRY", 
            new Soldier("Infantry", 100, 20, 10, List.of("Rifle", "Grenade")));
        registry.registerPrototype("SNIPER", 
            new Soldier("Sniper", 70, 50, 5, List.of("Sniper Rifle", "Pistol")));
        
        // Clone many units quickly (no expensive init)
        GameUnit soldier1 = registry.createUnit("INFANTRY");
        soldier1.setPosition(10, 20);
        
        GameUnit soldier2 = registry.createUnit("INFANTRY");
        soldier2.setPosition(30, 40);
        
        GameUnit sniper = registry.createUnit("SNIPER");
        sniper.setPosition(100, 50);
        
        System.out.println(soldier1.getDetails());
        System.out.println(soldier2.getDetails());
        System.out.println(sniper.getDetails());
    }
}
```

---

## 2. STRUCTURAL PATTERNS

---

### 2.1 Adapter Pattern

**Problem:** Make incompatible interfaces work together. Convert the interface of one class into what the client expects.

**When to use in LLD:** Integrating third-party libraries, legacy system migration, format converters.

```java
// === Target interface (what client expects) ===
public interface MediaPlayer {
    void play(String fileName);
    void pause();
    void stop();
}

// === Adaptee (incompatible third-party library) ===
public class VLCPlayer {
    public void playVLC(String fileName) {
        System.out.println("VLC playing: " + fileName);
    }
    public void pauseVLC() {
        System.out.println("VLC paused");
    }
    public void stopVLC() {
        System.out.println("VLC stopped");
    }
}

public class FFmpegPlayer {
    public void loadMedia(String path) {
        System.out.println("FFmpeg loading: " + path);
    }
    public void startPlayback() {
        System.out.println("FFmpeg playing...");
    }
    public void pausePlayback() {
        System.out.println("FFmpeg paused");
    }
    public void endPlayback() {
        System.out.println("FFmpeg stopped");
    }
}

// === Adapter for VLC ===
public class VLCAdapter implements MediaPlayer {
    private final VLCPlayer vlcPlayer;
    
    public VLCAdapter(VLCPlayer vlcPlayer) {
        this.vlcPlayer = vlcPlayer;
    }
    
    @Override
    public void play(String fileName) {
        vlcPlayer.playVLC(fileName);
    }
    
    @Override
    public void pause() {
        vlcPlayer.pauseVLC();
    }
    
    @Override
    public void stop() {
        vlcPlayer.stopVLC();
    }
}

// === Adapter for FFmpeg ===
public class FFmpegAdapter implements MediaPlayer {
    private final FFmpegPlayer ffmpegPlayer;
    
    public FFmpegAdapter(FFmpegPlayer ffmpegPlayer) {
        this.ffmpegPlayer = ffmpegPlayer;
    }
    
    @Override
    public void play(String fileName) {
        ffmpegPlayer.loadMedia(fileName);
        ffmpegPlayer.startPlayback();
    }
    
    @Override
    public void pause() {
        ffmpegPlayer.pausePlayback();
    }
    
    @Override
    public void stop() {
        ffmpegPlayer.endPlayback();
    }
}

// === Usage ===
public class MusicApp {
    private MediaPlayer player;
    
    public void setPlayer(MediaPlayer player) {
        this.player = player;
    }
    
    public void playMusic(String file) {
        player.play(file);  // Works with ANY adapter
    }
    
    public static void main(String[] args) {
        MusicApp app = new MusicApp();
        
        // Use VLC backend
        app.setPlayer(new VLCAdapter(new VLCPlayer()));
        app.playMusic("song.mp3");
        
        // Switch to FFmpeg backend - client code unchanged!
        app.setPlayer(new FFmpegAdapter(new FFmpegPlayer()));
        app.playMusic("video.mp4");
    }
}
```

---

### 2.2 Decorator Pattern

**Problem:** Add responsibilities to objects dynamically without modifying their class. Alternative to subclassing for extending functionality.

**When to use in LLD:** Coffee/pizza ordering systems, I/O streams, logging wrappers, caching layers.

```java
// === Component interface ===
public interface Coffee {
    String getDescription();
    double getCost();
}

// === Concrete component (base coffee) ===
public class Espresso implements Coffee {
    @Override
    public String getDescription() {
        return "Espresso";
    }
    @Override
    public double getCost() {
        return 50.0;
    }
}

public class HouseBlend implements Coffee {
    @Override
    public String getDescription() {
        return "House Blend";
    }
    @Override
    public double getCost() {
        return 40.0;
    }
}

// === Base Decorator (abstract) ===
public abstract class CoffeeDecorator implements Coffee {
    protected final Coffee decoratedCoffee;
    
    public CoffeeDecorator(Coffee coffee) {
        this.decoratedCoffee = coffee;
    }
    
    @Override
    public String getDescription() {
        return decoratedCoffee.getDescription();
    }
    
    @Override
    public double getCost() {
        return decoratedCoffee.getCost();
    }
}

// === Concrete Decorators (toppings/add-ons) ===
public class MilkDecorator extends CoffeeDecorator {
    public MilkDecorator(Coffee coffee) {
        super(coffee);
    }
    
    @Override
    public String getDescription() {
        return decoratedCoffee.getDescription() + " + Milk";
    }
    
    @Override
    public double getCost() {
        return decoratedCoffee.getCost() + 10.0;
    }
}

public class WhipCreamDecorator extends CoffeeDecorator {
    public WhipCreamDecorator(Coffee coffee) {
        super(coffee);
    }
    
    @Override
    public String getDescription() {
        return decoratedCoffee.getDescription() + " + Whip Cream";
    }
    
    @Override
    public double getCost() {
        return decoratedCoffee.getCost() + 15.0;
    }
}

public class CaramelDecorator extends CoffeeDecorator {
    public CaramelDecorator(Coffee coffee) {
        super(coffee);
    }
    
    @Override
    public String getDescription() {
        return decoratedCoffee.getDescription() + " + Caramel";
    }
    
    @Override
    public double getCost() {
        return decoratedCoffee.getCost() + 20.0;
    }
}

public class SizeDecorator extends CoffeeDecorator {
    private final String size;
    private final double multiplier;
    
    public SizeDecorator(Coffee coffee, String size) {
        super(coffee);
        this.size = size;
        this.multiplier = switch (size) {
            case "SMALL" -> 0.8;
            case "MEDIUM" -> 1.0;
            case "LARGE" -> 1.3;
            default -> 1.0;
        };
    }
    
    @Override
    public String getDescription() {
        return size + " " + decoratedCoffee.getDescription();
    }
    
    @Override
    public double getCost() {
        return decoratedCoffee.getCost() * multiplier;
    }
}

// === Usage ===
public class CoffeeShop {
    public static void main(String[] args) {
        // Simple espresso
        Coffee coffee1 = new Espresso();
        System.out.println(coffee1.getDescription() + " : Rs." + coffee1.getCost());
        // "Espresso : Rs.50.0"
        
        // Espresso + Milk + Whip Cream
        Coffee coffee2 = new WhipCreamDecorator(new MilkDecorator(new Espresso()));
        System.out.println(coffee2.getDescription() + " : Rs." + coffee2.getCost());
        // "Espresso + Milk + Whip Cream : Rs.75.0"
        
        // Large House Blend + Caramel + Caramel (double caramel!)
        Coffee coffee3 = new CaramelDecorator(
                            new CaramelDecorator(
                                new SizeDecorator(new HouseBlend(), "LARGE")));
        System.out.println(coffee3.getDescription() + " : Rs." + coffee3.getCost());
        // "LARGE House Blend + Caramel + Caramel : Rs.92.0"
    }
}
```

---

### 2.3 Facade Pattern

**Problem:** Provide a simplified interface to a complex subsystem with many classes.

**When to use in LLD:** E-commerce order placement, payment processing, booking systems.

```java
// === Complex subsystems ===
public class InventoryService {
    public boolean checkStock(String productId, int quantity) {
        System.out.println("Checking stock for " + productId);
        return true; // Simplified
    }
    
    public void reserveStock(String productId, int quantity) {
        System.out.println("Reserved " + quantity + " units of " + productId);
    }
    
    public void releaseStock(String productId, int quantity) {
        System.out.println("Released " + quantity + " units of " + productId);
    }
}

public class PaymentService {
    public boolean validatePaymentMethod(String paymentId) {
        System.out.println("Validating payment method: " + paymentId);
        return true;
    }
    
    public String processPayment(double amount, String paymentId) {
        System.out.println("Processing payment of Rs." + amount);
        return "TXN_" + System.currentTimeMillis();
    }
    
    public void refund(String transactionId) {
        System.out.println("Refunding transaction: " + transactionId);
    }
}

public class ShippingService {
    public double calculateShipping(String address, double weight) {
        System.out.println("Calculating shipping to: " + address);
        return 50.0;
    }
    
    public String createShipment(String orderId, String address) {
        System.out.println("Creating shipment for order: " + orderId);
        return "SHIP_" + System.currentTimeMillis();
    }
}

public class NotificationService {
    public void sendOrderConfirmation(String email, String orderId) {
        System.out.println("Sent confirmation to " + email + " for order " + orderId);
    }
    
    public void sendShippingUpdate(String email, String trackingId) {
        System.out.println("Sent shipping update to " + email);
    }
}

public class DiscountService {
    public double applyDiscount(String couponCode, double total) {
        if ("SAVE10".equals(couponCode)) {
            return total * 0.9;
        }
        return total;
    }
}

// === FACADE - simplifies the complex workflow ===
public class OrderFacade {
    private final InventoryService inventoryService;
    private final PaymentService paymentService;
    private final ShippingService shippingService;
    private final NotificationService notificationService;
    private final DiscountService discountService;
    
    public OrderFacade() {
        this.inventoryService = new InventoryService();
        this.paymentService = new PaymentService();
        this.shippingService = new ShippingService();
        this.notificationService = new NotificationService();
        this.discountService = new DiscountService();
    }
    
    // ONE simple method hides all complexity
    public String placeOrder(String productId, int quantity, double price,
                            String paymentId, String address, String email,
                            String couponCode) {
        
        // Step 1: Check inventory
        if (!inventoryService.checkStock(productId, quantity)) {
            throw new RuntimeException("Out of stock!");
        }
        
        // Step 2: Reserve stock
        inventoryService.reserveStock(productId, quantity);
        
        try {
            // Step 3: Calculate total
            double total = price * quantity;
            double shipping = shippingService.calculateShipping(address, quantity * 0.5);
            total += shipping;
            
            // Step 4: Apply discount
            if (couponCode != null) {
                total = discountService.applyDiscount(couponCode, total);
            }
            
            // Step 5: Validate and process payment
            if (!paymentService.validatePaymentMethod(paymentId)) {
                throw new RuntimeException("Invalid payment method!");
            }
            String txnId = paymentService.processPayment(total, paymentId);
            
            // Step 6: Create shipment
            String orderId = "ORD_" + System.currentTimeMillis();
            String shipmentId = shippingService.createShipment(orderId, address);
            
            // Step 7: Send notification
            notificationService.sendOrderConfirmation(email, orderId);
            
            System.out.println("\nOrder placed successfully! ID: " + orderId);
            return orderId;
            
        } catch (Exception e) {
            // Rollback: release stock
            inventoryService.releaseStock(productId, quantity);
            throw new RuntimeException("Order failed: " + e.getMessage());
        }
    }
}

// === Client - simple interaction ===
public class Main {
    public static void main(String[] args) {
        OrderFacade orderFacade = new OrderFacade();
        
        // Client doesn't need to know about 5 different services!
        String orderId = orderFacade.placeOrder(
            "PROD_001", 2, 500.0,
            "PAY_CARD_123", "Mumbai, India",
            "user@email.com", "SAVE10"
        );
    }
}
```

---

### 2.4 Proxy Pattern

**Problem:** Control access to an object. Provide a surrogate/placeholder for another object.

**Types:** Virtual (lazy loading), Protection (access control), Caching, Logging

```java
// === Subject interface ===
public interface Image {
    void display();
    String getFileName();
}

// === Real subject (expensive to create) ===
public class HighResImage implements Image {
    private final String fileName;
    private byte[] imageData;
    
    public HighResImage(String fileName) {
        this.fileName = fileName;
        loadFromDisk(); // Expensive operation!
    }
    
    private void loadFromDisk() {
        System.out.println("Loading high-res image from disk: " + fileName);
        // Simulate loading 50MB image
        try { Thread.sleep(1000); } catch (InterruptedException e) {}
        imageData = new byte[50_000_000]; // 50MB
        System.out.println("Image loaded: " + fileName);
    }
    
    @Override
    public void display() {
        System.out.println("Displaying: " + fileName);
    }
    
    @Override
    public String getFileName() {
        return fileName;
    }
}

// === Virtual Proxy (lazy loading) ===
public class ImageProxy implements Image {
    private final String fileName;
    private HighResImage realImage; // Created only when needed
    
    public ImageProxy(String fileName) {
        this.fileName = fileName;
        // Does NOT load the image yet!
    }
    
    @Override
    public void display() {
        if (realImage == null) {
            realImage = new HighResImage(fileName); // Load only on first use
        }
        realImage.display();
    }
    
    @Override
    public String getFileName() {
        return fileName; // Doesn't need to load image for this
    }
}

// === Protection Proxy (access control) ===
public class ProtectedImage implements Image {
    private final Image realImage;
    private final String currentUserRole;
    
    public ProtectedImage(Image image, String userRole) {
        this.realImage = image;
        this.currentUserRole = userRole;
    }
    
    @Override
    public void display() {
        if ("ADMIN".equals(currentUserRole) || "VIEWER".equals(currentUserRole)) {
            realImage.display();
        } else {
            System.out.println("ACCESS DENIED: Insufficient permissions to view " + getFileName());
        }
    }
    
    @Override
    public String getFileName() {
        return realImage.getFileName();
    }
}

// === Caching Proxy ===
public class CachingImageProxy implements Image {
    private final String fileName;
    private static final Map<String, HighResImage> cache = new HashMap<>();
    
    public CachingImageProxy(String fileName) {
        this.fileName = fileName;
    }
    
    @Override
    public void display() {
        HighResImage image = cache.computeIfAbsent(fileName, HighResImage::new);
        image.display();
    }
    
    @Override
    public String getFileName() {
        return fileName;
    }
}

// === Usage ===
public class ImageViewer {
    public static void main(String[] args) {
        // Virtual Proxy - images loaded only when displayed
        List<Image> gallery = List.of(
            new ImageProxy("photo1.jpg"),
            new ImageProxy("photo2.jpg"),
            new ImageProxy("photo3.jpg")
        );
        
        System.out.println("Gallery created (no images loaded yet!)");
        System.out.println("File: " + gallery.get(0).getFileName()); // No loading
        
        // Only NOW it loads
        gallery.get(0).display(); // Loads and displays photo1.jpg
        gallery.get(0).display(); // Already loaded, just displays
        
        // Protection Proxy
        System.out.println("\n--- Access Control ---");
        Image adminView = new ProtectedImage(new ImageProxy("secret.jpg"), "ADMIN");
        Image guestView = new ProtectedImage(new ImageProxy("secret.jpg"), "GUEST");
        
        adminView.display(); // Works
        guestView.display(); // ACCESS DENIED
    }
}
```

---

### 2.5 Composite Pattern

**Problem:** Treat individual objects and compositions of objects uniformly. Build tree structures.

**When to use in LLD:** File systems, organizational hierarchies, menu systems, UI component trees.

```java
// === Component (common interface for files and directories) ===
public abstract class FileSystemItem {
    protected String name;
    protected LocalDateTime created;
    
    public FileSystemItem(String name) {
        this.name = name;
        this.created = LocalDateTime.now();
    }
    
    public String getName() { return name; }
    
    public abstract long getSize();
    public abstract void display(String indent);
    public abstract int countFiles();
    
    // Default implementations for leaf nodes
    public void add(FileSystemItem item) {
        throw new UnsupportedOperationException("Cannot add to a file");
    }
    
    public void remove(FileSystemItem item) {
        throw new UnsupportedOperationException("Cannot remove from a file");
    }
    
    public List<FileSystemItem> getChildren() {
        throw new UnsupportedOperationException("Files don't have children");
    }
}

// === Leaf (File) ===
public class File extends FileSystemItem {
    private final long size; // in bytes
    private final String extension;
    
    public File(String name, long size) {
        super(name);
        this.size = size;
        this.extension = name.contains(".") ? 
            name.substring(name.lastIndexOf('.')) : "";
    }
    
    @Override
    public long getSize() {
        return size;
    }
    
    @Override
    public void display(String indent) {
        System.out.printf("%s📄 %s (%s)%n", indent, name, formatSize(size));
    }
    
    @Override
    public int countFiles() {
        return 1;
    }
    
    private String formatSize(long bytes) {
        if (bytes < 1024) return bytes + " B";
        if (bytes < 1024 * 1024) return (bytes / 1024) + " KB";
        return (bytes / (1024 * 1024)) + " MB";
    }
}

// === Composite (Directory) ===
public class Directory extends FileSystemItem {
    private final List<FileSystemItem> children = new ArrayList<>();
    
    public Directory(String name) {
        super(name);
    }
    
    @Override
    public void add(FileSystemItem item) {
        children.add(item);
    }
    
    @Override
    public void remove(FileSystemItem item) {
        children.remove(item);
    }
    
    @Override
    public List<FileSystemItem> getChildren() {
        return Collections.unmodifiableList(children);
    }
    
    @Override
    public long getSize() {
        // Recursively calculate total size
        return children.stream()
            .mapToLong(FileSystemItem::getSize)
            .sum();
    }
    
    @Override
    public void display(String indent) {
        System.out.printf("%s📁 %s/ (%d items, %s)%n", 
            indent, name, children.size(), formatSize(getSize()));
        for (FileSystemItem child : children) {
            child.display(indent + "  ");
        }
    }
    
    @Override
    public int countFiles() {
        return children.stream()
            .mapToInt(FileSystemItem::countFiles)
            .sum();
    }
    
    // Search functionality
    public List<FileSystemItem> search(String keyword) {
        List<FileSystemItem> results = new ArrayList<>();
        for (FileSystemItem child : children) {
            if (child.getName().contains(keyword)) {
                results.add(child);
            }
            if (child instanceof Directory dir) {
                results.addAll(dir.search(keyword));
            }
        }
        return results;
    }
    
    private String formatSize(long bytes) {
        if (bytes < 1024) return bytes + " B";
        if (bytes < 1024 * 1024) return (bytes / 1024) + " KB";
        return (bytes / (1024 * 1024)) + " MB";
    }
}

// === Usage ===
public class Main {
    public static void main(String[] args) {
        // Build file system tree
        Directory root = new Directory("project");
        
        Directory src = new Directory("src");
        src.add(new File("Main.java", 2048));
        src.add(new File("Utils.java", 1024));
        
        Directory test = new Directory("test");
        test.add(new File("MainTest.java", 1536));
        
        Directory resources = new Directory("resources");
        resources.add(new File("config.yml", 512));
        resources.add(new File("logo.png", 50000));
        
        root.add(src);
        root.add(test);
        root.add(resources);
        root.add(new File("README.md", 4096));
        root.add(new File("pom.xml", 3072));
        
        // Uniform interface - works for files AND directories
        root.display("");
        System.out.println("\nTotal files: " + root.countFiles());
        System.out.println("Total size: " + root.getSize() + " bytes");
        
        // Search
        List<FileSystemItem> results = root.search(".java");
        System.out.println("\nJava files found: " + results.size());
    }
}
```

---

## 3. BEHAVIORAL PATTERNS

---

### 3.1 Strategy Pattern

**Problem:** Define a family of algorithms, encapsulate each one, and make them interchangeable at runtime.

**When to use in LLD:** Payment processing, sorting algorithms, compression, validation rules, pricing strategies.

```java
// === Strategy interface ===
public interface PaymentStrategy {
    boolean validate();
    void pay(double amount);
    String getPaymentMethod();
}

// === Concrete strategies ===
public class CreditCardPayment implements PaymentStrategy {
    private final String cardNumber;
    private final String cvv;
    private final String expiryDate;
    
    public CreditCardPayment(String cardNumber, String cvv, String expiryDate) {
        this.cardNumber = cardNumber;
        this.cvv = cvv;
        this.expiryDate = expiryDate;
    }
    
    @Override
    public boolean validate() {
        // Luhn algorithm check (simplified)
        return cardNumber != null && cardNumber.length() == 16 
               && cvv.length() == 3;
    }
    
    @Override
    public void pay(double amount) {
        System.out.printf("Paid Rs.%.2f via Credit Card ending %s%n", 
            amount, cardNumber.substring(12));
    }
    
    @Override
    public String getPaymentMethod() {
        return "CREDIT_CARD";
    }
}

public class UPIPayment implements PaymentStrategy {
    private final String upiId;
    
    public UPIPayment(String upiId) {
        this.upiId = upiId;
    }
    
    @Override
    public boolean validate() {
        return upiId != null && upiId.contains("@");
    }
    
    @Override
    public void pay(double amount) {
        System.out.printf("Paid Rs.%.2f via UPI: %s%n", amount, upiId);
    }
    
    @Override
    public String getPaymentMethod() {
        return "UPI";
    }
}

public class WalletPayment implements PaymentStrategy {
    private final String walletId;
    private double balance;
    
    public WalletPayment(String walletId, double balance) {
        this.walletId = walletId;
        this.balance = balance;
    }
    
    @Override
    public boolean validate() {
        return balance > 0;
    }
    
    @Override
    public void pay(double amount) {
        if (balance >= amount) {
            balance -= amount;
            System.out.printf("Paid Rs.%.2f from Wallet. Remaining: Rs.%.2f%n", 
                amount, balance);
        } else {
            System.out.println("Insufficient wallet balance!");
        }
    }
    
    @Override
    public String getPaymentMethod() {
        return "WALLET";
    }
}

// === Context class ===
public class PaymentProcessor {
    private PaymentStrategy strategy;
    
    public void setPaymentStrategy(PaymentStrategy strategy) {
        this.strategy = strategy;
    }
    
    public boolean processPayment(double amount) {
        if (strategy == null) {
            throw new IllegalStateException("Payment strategy not set!");
        }
        
        System.out.println("Processing payment via: " + strategy.getPaymentMethod());
        
        if (!strategy.validate()) {
            System.out.println("Payment validation failed!");
            return false;
        }
        
        strategy.pay(amount);
        return true;
    }
}

// === Usage ===
public class Main {
    public static void main(String[] args) {
        PaymentProcessor processor = new PaymentProcessor();
        
        // Pay with Credit Card
        processor.setPaymentStrategy(
            new CreditCardPayment("1234567890123456", "123", "12/25"));
        processor.processPayment(1500.00);
        
        // Switch to UPI at runtime
        processor.setPaymentStrategy(new UPIPayment("user@paytm"));
        processor.processPayment(500.00);
        
        // Switch to Wallet
        processor.setPaymentStrategy(new WalletPayment("WALLET_001", 2000.00));
        processor.processPayment(750.00);
    }
}
```

---

### 3.2 Observer Pattern

**Problem:** Define a one-to-many dependency so that when one object changes state, all dependents are notified.

**When to use in LLD:** Event systems, notification services, stock price updates, pub-sub systems.

```java
// === Observer interface ===
public interface EventListener {
    void update(String eventType, Object data);
    String getName();
}

// === Subject (Observable) ===
public class EventManager {
    private final Map<String, List<EventListener>> listeners = new HashMap<>();
    
    public void subscribe(String eventType, EventListener listener) {
        listeners.computeIfAbsent(eventType, k -> new ArrayList<>()).add(listener);
        System.out.println(listener.getName() + " subscribed to: " + eventType);
    }
    
    public void unsubscribe(String eventType, EventListener listener) {
        List<EventListener> eventListeners = listeners.get(eventType);
        if (eventListeners != null) {
            eventListeners.remove(listener);
            System.out.println(listener.getName() + " unsubscribed from: " + eventType);
        }
    }
    
    public void notify(String eventType, Object data) {
        List<EventListener> eventListeners = listeners.getOrDefault(eventType, List.of());
        for (EventListener listener : eventListeners) {
            listener.update(eventType, data);
        }
    }
}

// === Concrete Observers ===
public class EmailNotificationListener implements EventListener {
    private final String email;
    
    public EmailNotificationListener(String email) {
        this.email = email;
    }
    
    @Override
    public void update(String eventType, Object data) {
        System.out.printf("  [EMAIL to %s] Event: %s | Data: %s%n", email, eventType, data);
    }
    
    @Override
    public String getName() {
        return "EmailListener(" + email + ")";
    }
}

public class SMSNotificationListener implements EventListener {
    private final String phone;
    
    public SMSNotificationListener(String phone) {
        this.phone = phone;
    }
    
    @Override
    public void update(String eventType, Object data) {
        System.out.printf("  [SMS to %s] Event: %s | Data: %s%n", phone, eventType, data);
    }
    
    @Override
    public String getName() {
        return "SMSListener(" + phone + ")";
    }
}

public class SlackNotificationListener implements EventListener {
    private final String channel;
    
    public SlackNotificationListener(String channel) {
        this.channel = channel;
    }
    
    @Override
    public void update(String eventType, Object data) {
        System.out.printf("  [SLACK #%s] Event: %s | Data: %s%n", channel, eventType, data);
    }
    
    @Override
    public String getName() {
        return "SlackListener(#" + channel + ")";
    }
}

// === Concrete Subject (uses EventManager) ===
public class OrderService {
    private final EventManager eventManager;
    
    public OrderService() {
        this.eventManager = new EventManager();
    }
    
    public EventManager getEventManager() {
        return eventManager;
    }
    
    public void placeOrder(String orderId, String product, double amount) {
        System.out.println("\nPlacing order: " + orderId);
        // Business logic...
        
        // Notify observers
        Map<String, Object> orderData = Map.of(
            "orderId", orderId,
            "product", product,
            "amount", amount
        );
        eventManager.notify("ORDER_PLACED", orderData);
    }
    
    public void shipOrder(String orderId) {
        System.out.println("\nShipping order: " + orderId);
        eventManager.notify("ORDER_SHIPPED", orderId);
    }
    
    public void cancelOrder(String orderId, String reason) {
        System.out.println("\nCancelling order: " + orderId);
        eventManager.notify("ORDER_CANCELLED", orderId + " - " + reason);
    }
}

// === Usage ===
public class Main {
    public static void main(String[] args) {
        OrderService orderService = new OrderService();
        EventManager events = orderService.getEventManager();
        
        // Subscribe different listeners to different events
        EventListener emailListener = new EmailNotificationListener("user@email.com");
        EventListener smsListener = new SMSNotificationListener("+91-9876543210");
        EventListener slackListener = new SlackNotificationListener("orders");
        
        events.subscribe("ORDER_PLACED", emailListener);
        events.subscribe("ORDER_PLACED", slackListener);
        events.subscribe("ORDER_SHIPPED", emailListener);
        events.subscribe("ORDER_SHIPPED", smsListener);
        events.subscribe("ORDER_CANCELLED", emailListener);
        events.subscribe("ORDER_CANCELLED", smsListener);
        events.subscribe("ORDER_CANCELLED", slackListener);
        
        // Place order - notifies email + slack
        orderService.placeOrder("ORD-001", "MacBook Pro", 150000);
        
        // Ship order - notifies email + sms
        orderService.shipOrder("ORD-001");
        
        // Unsubscribe sms from cancellations
        events.unsubscribe("ORDER_CANCELLED", smsListener);
        
        // Cancel order - notifies email + slack (sms unsubscribed)
        orderService.cancelOrder("ORD-002", "Out of stock");
    }
}
```

---

### 3.3 Command Pattern

**Problem:** Encapsulate a request as an object. Supports undo/redo, queuing, and logging.

**When to use in LLD:** Text editors (undo/redo), remote controls, task schedulers, transaction systems.

```java
// === Command interface ===
public interface Command {
    void execute();
    void undo();
    String getDescription();
}

// === Receiver ===
public class TextEditor {
    private StringBuilder content = new StringBuilder();
    private int cursorPosition = 0;
    
    public void insertText(String text, int position) {
        content.insert(position, text);
        cursorPosition = position + text.length();
    }
    
    public String deleteText(int start, int end) {
        String deleted = content.substring(start, end);
        content.delete(start, end);
        cursorPosition = start;
        return deleted;
    }
    
    public void replaceText(int start, int end, String newText) {
        content.replace(start, end, newText);
        cursorPosition = start + newText.length();
    }
    
    public String getContent() {
        return content.toString();
    }
    
    public int getCursorPosition() {
        return cursorPosition;
    }
    
    public int length() {
        return content.length();
    }
}

// === Concrete Commands ===
public class InsertCommand implements Command {
    private final TextEditor editor;
    private final String text;
    private final int position;
    
    public InsertCommand(TextEditor editor, String text, int position) {
        this.editor = editor;
        this.text = text;
        this.position = position;
    }
    
    @Override
    public void execute() {
        editor.insertText(text, position);
    }
    
    @Override
    public void undo() {
        editor.deleteText(position, position + text.length());
    }
    
    @Override
    public String getDescription() {
        return "Insert '" + text + "' at position " + position;
    }
}

public class DeleteCommand implements Command {
    private final TextEditor editor;
    private final int start;
    private final int end;
    private String deletedText; // Saved for undo
    
    public DeleteCommand(TextEditor editor, int start, int end) {
        this.editor = editor;
        this.start = start;
        this.end = end;
    }
    
    @Override
    public void execute() {
        deletedText = editor.deleteText(start, end);
    }
    
    @Override
    public void undo() {
        editor.insertText(deletedText, start);
    }
    
    @Override
    public String getDescription() {
        return "Delete from " + start + " to " + end;
    }
}

public class ReplaceCommand implements Command {
    private final TextEditor editor;
    private final int start;
    private final int end;
    private final String newText;
    private String oldText; // Saved for undo
    
    public ReplaceCommand(TextEditor editor, int start, int end, String newText) {
        this.editor = editor;
        this.start = start;
        this.end = end;
        this.newText = newText;
    }
    
    @Override
    public void execute() {
        oldText = editor.getContent().substring(start, end);
        editor.replaceText(start, end, newText);
    }
    
    @Override
    public void undo() {
        editor.replaceText(start, start + newText.length(), oldText);
    }
    
    @Override
    public String getDescription() {
        return "Replace '" + oldText + "' with '" + newText + "'";
    }
}

// === Invoker (Command History Manager) ===
public class CommandHistory {
    private final Deque<Command> undoStack = new ArrayDeque<>();
    private final Deque<Command> redoStack = new ArrayDeque<>();
    
    public void executeCommand(Command command) {
        command.execute();
        undoStack.push(command);
        redoStack.clear(); // Clear redo after new command
        System.out.println("Executed: " + command.getDescription());
    }
    
    public void undo() {
        if (undoStack.isEmpty()) {
            System.out.println("Nothing to undo!");
            return;
        }
        Command command = undoStack.pop();
        command.undo();
        redoStack.push(command);
        System.out.println("Undone: " + command.getDescription());
    }
    
    public void redo() {
        if (redoStack.isEmpty()) {
            System.out.println("Nothing to redo!");
            return;
        }
        Command command = redoStack.pop();
        command.execute();
        undoStack.push(command);
        System.out.println("Redone: " + command.getDescription());
    }
    
    public void showHistory() {
        System.out.println("--- Command History ---");
        undoStack.descendingIterator().forEachRemaining(
            cmd -> System.out.println("  " + cmd.getDescription()));
    }
}

// === Usage ===
public class Main {
    public static void main(String[] args) {
        TextEditor editor = new TextEditor();
        CommandHistory history = new CommandHistory();
        
        // Type "Hello World"
        history.executeCommand(new InsertCommand(editor, "Hello World", 0));
        System.out.println("Content: " + editor.getContent()); // "Hello World"
        
        // Type " from Java"
        history.executeCommand(new InsertCommand(editor, " from Java", editor.length()));
        System.out.println("Content: " + editor.getContent()); // "Hello World from Java"
        
        // Replace "World" with "Universe"
        history.executeCommand(new ReplaceCommand(editor, 6, 11, "Universe"));
        System.out.println("Content: " + editor.getContent()); // "Hello Universe from Java"
        
        // Delete " from Java"
        history.executeCommand(new DeleteCommand(editor, 14, 24));
        System.out.println("Content: " + editor.getContent()); // "Hello Universe"
        
        // Undo operations
        System.out.println("\n--- Undo ---");
        history.undo(); // Undo delete
        System.out.println("Content: " + editor.getContent()); // "Hello Universe from Java"
        
        history.undo(); // Undo replace
        System.out.println("Content: " + editor.getContent()); // "Hello World from Java"
        
        // Redo
        System.out.println("\n--- Redo ---");
        history.redo(); // Redo replace
        System.out.println("Content: " + editor.getContent()); // "Hello Universe from Java"
        
        history.showHistory();
    }
}
```

---

### 3.4 State Pattern

**Problem:** Allow an object to alter its behavior when its internal state changes. Object appears to change its class.

**When to use in LLD:** Vending machines, order lifecycles, traffic lights, document workflows, game characters.

```java
// === State interface ===
public interface VendingMachineState {
    void insertCoin(VendingMachine machine, double amount);
    void selectProduct(VendingMachine machine, String product);
    void dispense(VendingMachine machine);
    void cancel(VendingMachine machine);
    String getStateName();
}

// === Context (Vending Machine) ===
public class VendingMachine {
    private VendingMachineState currentState;
    private double balance;
    private String selectedProduct;
    private final Map<String, Double> products;
    private final Map<String, Integer> inventory;
    
    public VendingMachine() {
        this.products = new HashMap<>();
        this.inventory = new HashMap<>();
        this.balance = 0;
        this.currentState = new IdleState();
        
        // Initialize products
        products.put("Coke", 20.0);
        products.put("Pepsi", 20.0);
        products.put("Water", 10.0);
        products.put("Chips", 30.0);
        
        inventory.put("Coke", 5);
        inventory.put("Pepsi", 3);
        inventory.put("Water", 10);
        inventory.put("Chips", 0); // Out of stock
    }
    
    // Delegate to current state
    public void insertCoin(double amount) {
        currentState.insertCoin(this, amount);
    }
    
    public void selectProduct(String product) {
        currentState.selectProduct(this, product);
    }
    
    public void dispense() {
        currentState.dispense(this);
    }
    
    public void cancel() {
        currentState.cancel(this);
    }
    
    // State management
    public void setState(VendingMachineState state) {
        System.out.println("  State: " + currentState.getStateName() + " → " + state.getStateName());
        this.currentState = state;
    }
    
    // Getters/Setters for state classes
    public double getBalance() { return balance; }
    public void addBalance(double amount) { this.balance += amount; }
    public void resetBalance() { this.balance = 0; }
    
    public String getSelectedProduct() { return selectedProduct; }
    public void setSelectedProduct(String product) { this.selectedProduct = product; }
    
    public double getProductPrice(String product) { 
        return products.getOrDefault(product, -1.0); 
    }
    
    public boolean isInStock(String product) { 
        return inventory.getOrDefault(product, 0) > 0; 
    }
    
    public void reduceStock(String product) {
        inventory.merge(product, -1, Integer::sum);
    }
    
    public void showStatus() {
        System.out.printf("  [Status] State: %s | Balance: Rs.%.1f | Selected: %s%n",
            currentState.getStateName(), balance, selectedProduct);
    }
}

// === Concrete States ===
public class IdleState implements VendingMachineState {
    @Override
    public void insertCoin(VendingMachine machine, double amount) {
        machine.addBalance(amount);
        System.out.println("  Inserted Rs." + amount + " | Total: Rs." + machine.getBalance());
        machine.setState(new HasMoneyState());
    }
    
    @Override
    public void selectProduct(VendingMachine machine, String product) {
        System.out.println("  Please insert coins first!");
    }
    
    @Override
    public void dispense(VendingMachine machine) {
        System.out.println("  Please insert coins and select a product!");
    }
    
    @Override
    public void cancel(VendingMachine machine) {
        System.out.println("  Nothing to cancel.");
    }
    
    @Override
    public String getStateName() { return "IDLE"; }
}

public class HasMoneyState implements VendingMachineState {
    @Override
    public void insertCoin(VendingMachine machine, double amount) {
        machine.addBalance(amount);
        System.out.println("  Inserted Rs." + amount + " | Total: Rs." + machine.getBalance());
    }
    
    @Override
    public void selectProduct(VendingMachine machine, String product) {
        double price = machine.getProductPrice(product);
        if (price < 0) {
            System.out.println("  Invalid product: " + product);
            return;
        }
        if (!machine.isInStock(product)) {
            System.out.println("  " + product + " is out of stock!");
            return;
        }
        if (machine.getBalance() < price) {
            System.out.printf("  Insufficient balance! Need Rs.%.1f more%n", 
                price - machine.getBalance());
            return;
        }
        
        machine.setSelectedProduct(product);
        System.out.println("  Selected: " + product + " (Rs." + price + ")");
        machine.setState(new DispensingState());
        machine.dispense(); // Auto-dispense
    }
    
    @Override
    public void dispense(VendingMachine machine) {
        System.out.println("  Please select a product first!");
    }
    
    @Override
    public void cancel(VendingMachine machine) {
        System.out.println("  Returning Rs." + machine.getBalance());
        machine.resetBalance();
        machine.setSelectedProduct(null);
        machine.setState(new IdleState());
    }
    
    @Override
    public String getStateName() { return "HAS_MONEY"; }
}

public class DispensingState implements VendingMachineState {
    @Override
    public void insertCoin(VendingMachine machine, double amount) {
        System.out.println("  Please wait, dispensing in progress...");
    }
    
    @Override
    public void selectProduct(VendingMachine machine, String product) {
        System.out.println("  Please wait, dispensing in progress...");
    }
    
    @Override
    public void dispense(VendingMachine machine) {
        String product = machine.getSelectedProduct();
        double price = machine.getProductPrice(product);
        
        machine.reduceStock(product);
        double change = machine.getBalance() - price;
        
        System.out.println("  🎉 Dispensing: " + product);
        if (change > 0) {
            System.out.println("  Returning change: Rs." + change);
        }
        
        machine.resetBalance();
        machine.setSelectedProduct(null);
        machine.setState(new IdleState());
    }
    
    @Override
    public void cancel(VendingMachine machine) {
        System.out.println("  Cannot cancel during dispensing!");
    }
    
    @Override
    public String getStateName() { return "DISPENSING"; }
}

// === Usage ===
public class Main {
    public static void main(String[] args) {
        VendingMachine vm = new VendingMachine();
        
        System.out.println("=== Scenario 1: Normal purchase ===");
        vm.insertCoin(10);
        vm.insertCoin(10);
        vm.selectProduct("Coke"); // Dispenses!
        
        System.out.println("\n=== Scenario 2: Insufficient funds ===");
        vm.insertCoin(10);
        vm.selectProduct("Chips"); // Chips = 30, only have 10
        vm.insertCoin(20);
        vm.selectProduct("Chips"); // Out of stock!
        vm.selectProduct("Coke");  // Works!
        
        System.out.println("\n=== Scenario 3: Cancel ===");
        vm.insertCoin(50);
        vm.cancel(); // Returns money
        vm.showStatus();
    }
}
```

---

### 3.5 Template Method Pattern

**Problem:** Define the skeleton of an algorithm, letting subclasses override specific steps without changing the algorithm's structure.

**When to use in LLD:** Data processing pipelines, game loops, report generators, parsers.

```java
// === Abstract class with template method ===
public abstract class DataProcessor {
    
    // TEMPLATE METHOD - defines the algorithm skeleton (final = can't override)
    public final void process() {
        readData();
        validateData();
        if (requiresTransformation()) { // Hook method
            transformData();
        }
        processData();
        saveResults();
        cleanup(); // Hook method with default implementation
        System.out.println("Processing complete!\n");
    }
    
    // Abstract steps - MUST be implemented by subclasses
    protected abstract void readData();
    protected abstract void validateData();
    protected abstract void processData();
    protected abstract void saveResults();
    
    // Hook - optional override (default implementation)
    protected void transformData() {
        // Default: no transformation
    }
    
    // Hook - subclass can override to control flow
    protected boolean requiresTransformation() {
        return false;
    }
    
    // Hook with default behavior
    protected void cleanup() {
        System.out.println("  [Cleanup] Default cleanup done");
    }
}

// === Concrete implementations ===
public class CSVDataProcessor extends DataProcessor {
    private List<String[]> data;
    private List<String[]> validData;
    
    @Override
    protected void readData() {
        System.out.println("  [CSV] Reading data from CSV file...");
        data = List.of(
            new String[]{"John", "25", "Engineer"},
            new String[]{"Jane", "", "Designer"},   // Invalid - empty age
            new String[]{"Bob", "30", "Manager"}
        );
    }
    
    @Override
    protected void validateData() {
        System.out.println("  [CSV] Validating rows...");
        validData = data.stream()
            .filter(row -> Arrays.stream(row).noneMatch(String::isEmpty))
            .toList();
        System.out.println("  [CSV] Valid rows: " + validData.size() + "/" + data.size());
    }
    
    @Override
    protected void processData() {
        System.out.println("  [CSV] Processing " + validData.size() + " records...");
    }
    
    @Override
    protected void saveResults() {
        System.out.println("  [CSV] Saving to database...");
    }
}

public class JSONDataProcessor extends DataProcessor {
    @Override
    protected void readData() {
        System.out.println("  [JSON] Reading from REST API...");
    }
    
    @Override
    protected void validateData() {
        System.out.println("  [JSON] Validating JSON schema...");
    }
    
    @Override
    protected boolean requiresTransformation() {
        return true; // JSON needs transformation
    }
    
    @Override
    protected void transformData() {
        System.out.println("  [JSON] Transforming nested JSON to flat structure...");
    }
    
    @Override
    protected void processData() {
        System.out.println("  [JSON] Aggregating data...");
    }
    
    @Override
    protected void saveResults() {
        System.out.println("  [JSON] Writing to Elasticsearch...");
    }
    
    @Override
    protected void cleanup() {
        System.out.println("  [JSON] Closing HTTP connections and clearing cache");
    }
}

public class XMLDataProcessor extends DataProcessor {
    @Override
    protected void readData() {
        System.out.println("  [XML] Parsing XML document with SAX parser...");
    }
    
    @Override
    protected void validateData() {
        System.out.println("  [XML] Validating against XSD schema...");
    }
    
    @Override
    protected boolean requiresTransformation() {
        return true;
    }
    
    @Override
    protected void transformData() {
        System.out.println("  [XML] Applying XSLT transformation...");
    }
    
    @Override
    protected void processData() {
        System.out.println("  [XML] Processing nodes...");
    }
    
    @Override
    protected void saveResults() {
        System.out.println("  [XML] Saving to file system...");
    }
}

// === Usage ===
public class Main {
    public static void main(String[] args) {
        System.out.println("=== CSV Processing ===");
        DataProcessor csvProcessor = new CSVDataProcessor();
        csvProcessor.process();
        
        System.out.println("=== JSON Processing ===");
        DataProcessor jsonProcessor = new JSONDataProcessor();
        jsonProcessor.process();
        
        System.out.println("=== XML Processing ===");
        DataProcessor xmlProcessor = new XMLDataProcessor();
        xmlProcessor.process();
    }
}
```

---

### 3.6 Chain of Responsibility Pattern

**Problem:** Pass a request along a chain of handlers. Each handler decides to process the request or pass it to the next handler.

**When to use in LLD:** Logging systems, request validation, middleware (filters), approval workflows.

```java
// === Handler interface ===
public abstract class RequestHandler {
    private RequestHandler nextHandler;
    
    public RequestHandler setNext(RequestHandler handler) {
        this.nextHandler = handler;
        return handler; // For chaining: a.setNext(b).setNext(c)
    }
    
    public void handle(Request request) {
        if (canHandle(request)) {
            processRequest(request);
        } else if (nextHandler != null) {
            nextHandler.handle(request);
        } else {
            System.out.println("  [END OF CHAIN] No handler could process: " + request);
        }
    }
    
    protected abstract boolean canHandle(Request request);
    protected abstract void processRequest(Request request);
}

// === Request object ===
public class Request {
    private final String type;
    private final double amount;
    private final String employeeName;
    private String status = "PENDING";
    
    public Request(String type, double amount, String employeeName) {
        this.type = type;
        this.amount = amount;
        this.employeeName = employeeName;
    }
    
    public String getType() { return type; }
    public double getAmount() { return amount; }
    public String getEmployeeName() { return employeeName; }
    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }
    
    @Override
    public String toString() {
        return "Request{%s by %s, Rs.%.0f, status=%s}".formatted(type, employeeName, amount, status);
    }
}

// === Concrete Handlers (Expense Approval Chain) ===
public class TeamLeadHandler extends RequestHandler {
    private static final double MAX_AMOUNT = 5000;
    
    @Override
    protected boolean canHandle(Request request) {
        return request.getAmount() <= MAX_AMOUNT;
    }
    
    @Override
    protected void processRequest(Request request) {
        request.setStatus("APPROVED by Team Lead");
        System.out.println("  [Team Lead] Approved: " + request);
    }
}

public class ManagerHandler extends RequestHandler {
    private static final double MAX_AMOUNT = 25000;
    
    @Override
    protected boolean canHandle(Request request) {
        return request.getAmount() <= MAX_AMOUNT;
    }
    
    @Override
    protected void processRequest(Request request) {
        request.setStatus("APPROVED by Manager");
        System.out.println("  [Manager] Approved: " + request);
    }
}

public class DirectorHandler extends RequestHandler {
    private static final double MAX_AMOUNT = 100000;
    
    @Override
    protected boolean canHandle(Request request) {
        return request.getAmount() <= MAX_AMOUNT;
    }
    
    @Override
    protected void processRequest(Request request) {
        request.setStatus("APPROVED by Director");
        System.out.println("  [Director] Approved: " + request);
    }
}

public class CEOHandler extends RequestHandler {
    @Override
    protected boolean canHandle(Request request) {
        return true; // CEO can approve anything
    }
    
    @Override
    protected void processRequest(Request request) {
        if (request.getAmount() > 500000) {
            request.setStatus("REJECTED - requires board approval");
            System.out.println("  [CEO] Rejected (too high): " + request);
        } else {
            request.setStatus("APPROVED by CEO");
            System.out.println("  [CEO] Approved: " + request);
        }
    }
}

// === Validation Chain (different use case) ===
public abstract class RequestValidator {
    private RequestValidator next;
    
    public RequestValidator linkWith(RequestValidator next) {
        this.next = next;
        return next;
    }
    
    public boolean validate(Request request) {
        if (!doValidate(request)) {
            return false;
        }
        if (next != null) {
            return next.validate(request);
        }
        return true; // All validations passed
    }
    
    protected abstract boolean doValidate(Request request);
}

public class NotNullValidator extends RequestValidator {
    @Override
    protected boolean doValidate(Request request) {
        if (request.getEmployeeName() == null || request.getType() == null) {
            System.out.println("  Validation FAILED: null fields");
            return false;
        }
        return true;
    }
}

public class AmountValidator extends RequestValidator {
    @Override
    protected boolean doValidate(Request request) {
        if (request.getAmount() <= 0) {
            System.out.println("  Validation FAILED: amount must be positive");
            return false;
        }
        return true;
    }
}

public class DuplicateValidator extends RequestValidator {
    private final Set<String> processedRequests = new HashSet<>();
    
    @Override
    protected boolean doValidate(Request request) {
        String key = request.getEmployeeName() + "_" + request.getAmount();
        if (processedRequests.contains(key)) {
            System.out.println("  Validation FAILED: duplicate request");
            return false;
        }
        processedRequests.add(key);
        return true;
    }
}

// === Usage ===
public class Main {
    public static void main(String[] args) {
        // Build approval chain
        RequestHandler teamLead = new TeamLeadHandler();
        RequestHandler manager = new ManagerHandler();
        RequestHandler director = new DirectorHandler();
        RequestHandler ceo = new CEOHandler();
        
        teamLead.setNext(manager).setNext(director).setNext(ceo);
        
        System.out.println("=== Expense Approval Chain ===");
        teamLead.handle(new Request("EXPENSE", 3000, "Alice"));   // Team Lead
        teamLead.handle(new Request("EXPENSE", 15000, "Bob"));    // Manager
        teamLead.handle(new Request("EXPENSE", 80000, "Charlie")); // Director
        teamLead.handle(new Request("EXPENSE", 200000, "Dave"));  // CEO
        teamLead.handle(new Request("EXPENSE", 1000000, "Eve")); // CEO rejects
        
        // Validation chain
        System.out.println("\n=== Request Validation Chain ===");
        NotNullValidator validator = new NotNullValidator();
        validator.linkWith(new AmountValidator()).linkWith(new DuplicateValidator());
        
        Request r1 = new Request("EXPENSE", 5000, "Alice");
        System.out.println("Valid: " + validator.validate(r1)); // true
        System.out.println("Duplicate: " + validator.validate(r1)); // false - duplicate
    }
}
```

---

### 3.7 Iterator Pattern

**Problem:** Provide a way to access elements of a collection sequentially without exposing its underlying structure.

**When to use in LLD:** Custom collections, tree traversal, paginated results.

```java
// === Custom Iterator interface ===
public interface Iterator<T> {
    boolean hasNext();
    T next();
    void reset();
}

// === Custom collection with multiple iteration strategies ===
public class BookCollection {
    private final List<Book> books = new ArrayList<>();
    
    public void addBook(Book book) {
        books.add(book);
    }
    
    public int size() {
        return books.size();
    }
    
    // Default iterator
    public Iterator<Book> iterator() {
        return new DefaultBookIterator();
    }
    
    // Iterator filtered by genre
    public Iterator<Book> genreIterator(String genre) {
        return new GenreFilterIterator(genre);
    }
    
    // Reverse iterator
    public Iterator<Book> reverseIterator() {
        return new ReverseBookIterator();
    }
    
    // === Inner Iterator classes ===
    private class DefaultBookIterator implements Iterator<Book> {
        private int currentIndex = 0;
        
        @Override
        public boolean hasNext() {
            return currentIndex < books.size();
        }
        
        @Override
        public Book next() {
            if (!hasNext()) throw new NoSuchElementException();
            return books.get(currentIndex++);
        }
        
        @Override
        public void reset() {
            currentIndex = 0;
        }
    }
    
    private class ReverseBookIterator implements Iterator<Book> {
        private int currentIndex = books.size() - 1;
        
        @Override
        public boolean hasNext() {
            return currentIndex >= 0;
        }
        
        @Override
        public Book next() {
            if (!hasNext()) throw new NoSuchElementException();
            return books.get(currentIndex--);
        }
        
        @Override
        public void reset() {
            currentIndex = books.size() - 1;
        }
    }
    
    private class GenreFilterIterator implements Iterator<Book> {
        private final String genre;
        private int currentIndex = 0;
        
        public GenreFilterIterator(String genre) {
            this.genre = genre;
        }
        
        @Override
        public boolean hasNext() {
            while (currentIndex < books.size()) {
                if (books.get(currentIndex).getGenre().equalsIgnoreCase(genre)) {
                    return true;
                }
                currentIndex++;
            }
            return false;
        }
        
        @Override
        public Book next() {
            if (!hasNext()) throw new NoSuchElementException();
            return books.get(currentIndex++);
        }
        
        @Override
        public void reset() {
            currentIndex = 0;
        }
    }
}

// === Book class ===
public class Book {
    private final String title;
    private final String author;
    private final String genre;
    private final int year;
    
    public Book(String title, String author, String genre, int year) {
        this.title = title;
        this.author = author;
        this.genre = genre;
        this.year = year;
    }
    
    public String getTitle() { return title; }
    public String getAuthor() { return author; }
    public String getGenre() { return genre; }
    public int getYear() { return year; }
    
    @Override
    public String toString() {
        return "'%s' by %s (%s, %d)".formatted(title, author, genre, year);
    }
}

// === Usage ===
public class Main {
    public static void main(String[] args) {
        BookCollection library = new BookCollection();
        library.addBook(new Book("Clean Code", "Robert Martin", "Programming", 2008));
        library.addBook(new Book("Design Patterns", "GoF", "Programming", 1994));
        library.addBook(new Book("1984", "George Orwell", "Fiction", 1949));
        library.addBook(new Book("Dune", "Frank Herbert", "Fiction", 1965));
        library.addBook(new Book("CLRS", "Cormen et al.", "Programming", 2009));
        
        // Default iteration
        System.out.println("=== All Books ===");
        Iterator<Book> it = library.iterator();
        while (it.hasNext()) {
            System.out.println("  " + it.next());
        }
        
        // Filtered iteration
        System.out.println("\n=== Fiction Books ===");
        Iterator<Book> fictionIt = library.genreIterator("Fiction");
        while (fictionIt.hasNext()) {
            System.out.println("  " + fictionIt.next());
        }
        
        // Reverse iteration
        System.out.println("\n=== Reverse Order ===");
        Iterator<Book> reverseIt = library.reverseIterator();
        while (reverseIt.hasNext()) {
            System.out.println("  " + reverseIt.next());
        }
    }
}
```

---

## 4. LLD-SPECIFIC PATTERNS

---

### 4.1 Repository Pattern

**Problem:** Abstract the data access layer, providing a collection-like interface for domain entities.

**When to use in LLD:** Every LLD that involves persistence (CRUD operations on entities).

```java
// === Entity ===
public class User {
    private String id;
    private String name;
    private String email;
    private int age;
    private LocalDateTime createdAt;
    
    public User(String id, String name, String email, int age) {
        this.id = id;
        this.name = name;
        this.email = email;
        this.age = age;
        this.createdAt = LocalDateTime.now();
    }
    
    // Getters and setters...
    public String getId() { return id; }
    public String getName() { return name; }
    public void setName(String name) { this.name = name; }
    public String getEmail() { return email; }
    public void setEmail(String email) { this.email = email; }
    public int getAge() { return age; }
    public void setAge(int age) { this.age = age; }
    public LocalDateTime getCreatedAt() { return createdAt; }
    
    @Override
    public String toString() {
        return "User{id=%s, name=%s, email=%s, age=%d}".formatted(id, name, email, age);
    }
}

// === Generic Repository Interface ===
public interface Repository<T, ID> {
    T save(T entity);
    Optional<T> findById(ID id);
    List<T> findAll();
    void deleteById(ID id);
    boolean existsById(ID id);
    long count();
}

// === Specific Repository Interface ===
public interface UserRepository extends Repository<User, String> {
    Optional<User> findByEmail(String email);
    List<User> findByAgeBetween(int min, int max);
    List<User> findByNameContaining(String keyword);
}

// === In-Memory Implementation ===
public class InMemoryUserRepository implements UserRepository {
    private final Map<String, User> store = new ConcurrentHashMap<>();
    
    @Override
    public User save(User user) {
        if (user.getId() == null) {
            // Generate ID for new entities
            user = new User(UUID.randomUUID().toString(), user.getName(), 
                           user.getEmail(), user.getAge());
        }
        store.put(user.getId(), user);
        return user;
    }
    
    @Override
    public Optional<User> findById(String id) {
        return Optional.ofNullable(store.get(id));
    }
    
    @Override
    public List<User> findAll() {
        return new ArrayList<>(store.values());
    }
    
    @Override
    public void deleteById(String id) {
        store.remove(id);
    }
    
    @Override
    public boolean existsById(String id) {
        return store.containsKey(id);
    }
    
    @Override
    public long count() {
        return store.size();
    }
    
    @Override
    public Optional<User> findByEmail(String email) {
        return store.values().stream()
            .filter(u -> u.getEmail().equalsIgnoreCase(email))
            .findFirst();
    }
    
    @Override
    public List<User> findByAgeBetween(int min, int max) {
        return store.values().stream()
            .filter(u -> u.getAge() >= min && u.getAge() <= max)
            .toList();
    }
    
    @Override
    public List<User> findByNameContaining(String keyword) {
        return store.values().stream()
            .filter(u -> u.getName().toLowerCase().contains(keyword.toLowerCase()))
            .toList();
    }
}
```

---

### 4.2 Service-Repository-Controller Layers

**Problem:** Separate concerns into distinct layers for maintainability and testability.

```java
// === DTO (Data Transfer Object) ===
public record CreateUserRequest(String name, String email, int age) {
    public CreateUserRequest {
        // Validation in compact constructor
        Objects.requireNonNull(name, "Name cannot be null");
        Objects.requireNonNull(email, "Email cannot be null");
        if (age < 0 || age > 150) throw new IllegalArgumentException("Invalid age");
        if (!email.contains("@")) throw new IllegalArgumentException("Invalid email");
    }
}

public record UpdateUserRequest(String name, String email, Integer age) {}

public record UserResponse(String id, String name, String email, int age, String createdAt) {
    public static UserResponse fromEntity(User user) {
        return new UserResponse(
            user.getId(),
            user.getName(),
            user.getEmail(),
            user.getAge(),
            user.getCreatedAt().toString()
        );
    }
}

public record ApiResponse<T>(boolean success, T data, String error) {
    public static <T> ApiResponse<T> success(T data) {
        return new ApiResponse<>(true, data, null);
    }
    
    public static <T> ApiResponse<T> error(String message) {
        return new ApiResponse<>(false, null, message);
    }
}

// === Service Layer (Business Logic) ===
public class UserService {
    private final UserRepository userRepository;
    
    public UserService(UserRepository userRepository) {
        this.userRepository = userRepository;
    }
    
    public UserResponse createUser(CreateUserRequest request) {
        // Business rule: email must be unique
        if (userRepository.findByEmail(request.email()).isPresent()) {
            throw new BusinessException("Email already registered: " + request.email());
        }
        
        User user = new User(null, request.name(), request.email(), request.age());
        User saved = userRepository.save(user);
        return UserResponse.fromEntity(saved);
    }
    
    public UserResponse getUserById(String id) {
        User user = userRepository.findById(id)
            .orElseThrow(() -> new NotFoundException("User not found: " + id));
        return UserResponse.fromEntity(user);
    }
    
    public List<UserResponse> getAllUsers() {
        return userRepository.findAll().stream()
            .map(UserResponse::fromEntity)
            .toList();
    }
    
    public UserResponse updateUser(String id, UpdateUserRequest request) {
        User user = userRepository.findById(id)
            .orElseThrow(() -> new NotFoundException("User not found: " + id));
        
        if (request.name() != null) user.setName(request.name());
        if (request.email() != null) {
            // Check uniqueness for new email
            userRepository.findByEmail(request.email())
                .filter(u -> !u.getId().equals(id))
                .ifPresent(u -> {
                    throw new BusinessException("Email already in use");
                });
            user.setEmail(request.email());
        }
        if (request.age() != null) user.setAge(request.age());
        
        User saved = userRepository.save(user);
        return UserResponse.fromEntity(saved);
    }
    
    public void deleteUser(String id) {
        if (!userRepository.existsById(id)) {
            throw new NotFoundException("User not found: " + id);
        }
        userRepository.deleteById(id);
    }
    
    public List<UserResponse> searchUsers(String keyword) {
        return userRepository.findByNameContaining(keyword).stream()
            .map(UserResponse::fromEntity)
            .toList();
    }
}

// === Controller Layer (API/Interface) ===
public class UserController {
    private final UserService userService;
    
    public UserController(UserService userService) {
        this.userService = userService;
    }
    
    public ApiResponse<UserResponse> createUser(CreateUserRequest request) {
        try {
            UserResponse response = userService.createUser(request);
            return ApiResponse.success(response);
        } catch (BusinessException e) {
            return ApiResponse.error(e.getMessage());
        }
    }
    
    public ApiResponse<UserResponse> getUser(String id) {
        try {
            return ApiResponse.success(userService.getUserById(id));
        } catch (NotFoundException e) {
            return ApiResponse.error(e.getMessage());
        }
    }
    
    public ApiResponse<List<UserResponse>> listUsers() {
        return ApiResponse.success(userService.getAllUsers());
    }
    
    public ApiResponse<UserResponse> updateUser(String id, UpdateUserRequest request) {
        try {
            return ApiResponse.success(userService.updateUser(id, request));
        } catch (NotFoundException | BusinessException e) {
            return ApiResponse.error(e.getMessage());
        }
    }
    
    public ApiResponse<Void> deleteUser(String id) {
        try {
            userService.deleteUser(id);
            return ApiResponse.success(null);
        } catch (NotFoundException e) {
            return ApiResponse.error(e.getMessage());
        }
    }
}

// === Custom Exceptions ===
public class BusinessException extends RuntimeException {
    public BusinessException(String message) { super(message); }
}

public class NotFoundException extends RuntimeException {
    public NotFoundException(String message) { super(message); }
}

// === Usage (Wiring it all together) ===
public class Application {
    public static void main(String[] args) {
        // Dependency Injection (manual)
        UserRepository repository = new InMemoryUserRepository();
        UserService service = new UserService(repository);
        UserController controller = new UserController(service);
        
        // Create users
        System.out.println("=== Create Users ===");
        var result1 = controller.createUser(new CreateUserRequest("Alice", "alice@email.com", 25));
        System.out.println(result1);
        
        var result2 = controller.createUser(new CreateUserRequest("Bob", "bob@email.com", 30));
        System.out.println(result2);
        
        // Duplicate email
        var result3 = controller.createUser(new CreateUserRequest("Alice2", "alice@email.com", 22));
        System.out.println(result3); // Error: Email already registered
        
        // List all
        System.out.println("\n=== List Users ===");
        System.out.println(controller.listUsers());
        
        // Get by ID
        String userId = result1.data().id();
        System.out.println("\n=== Get User ===");
        System.out.println(controller.getUser(userId));
        
        // Update
        System.out.println("\n=== Update User ===");
        System.out.println(controller.updateUser(userId, new UpdateUserRequest("Alice Smith", null, 26)));
        
        // Delete
        System.out.println("\n=== Delete User ===");
        System.out.println(controller.deleteUser(userId));
        System.out.println(controller.getUser(userId)); // Not found
    }
}
```

---

### 4.3 DTO Pattern (Data Transfer Object)

**Problem:** Transfer data between layers/services without exposing internal entity structure.

```java
// === Why DTOs? ===
// 1. Decouple API contract from internal model
// 2. Control what data is exposed (security)
// 3. Combine data from multiple entities
// 4. Add validation at API boundary
// 5. Version API independently of domain model

// === Entity (internal - has JPA annotations, business logic) ===
public class Order {
    private String id;
    private String userId;
    private List<OrderItem> items;
    private OrderStatus status;
    private double totalAmount;
    private double discount;
    private String paymentId;       // Internal - don't expose
    private String internalNotes;   // Internal - don't expose
    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;
    
    // ... constructors, getters, setters, business methods
    
    public double getNetAmount() {
        return totalAmount - discount;
    }
}

// === Request DTOs (what client SENDS) ===
public record CreateOrderRequest(
    String userId,
    List<OrderItemRequest> items,
    String couponCode   // Optional
) {
    public record OrderItemRequest(String productId, int quantity) {}
}

// === Response DTOs (what client RECEIVES) ===
public record OrderResponse(
    String orderId,
    String status,
    List<OrderItemResponse> items,
    double subtotal,
    double discount,
    double total,
    String createdAt
) {
    public record OrderItemResponse(
        String productName,
        int quantity,
        double unitPrice,
        double totalPrice
    ) {}
    
    // Factory method to create from entity
    public static OrderResponse fromEntity(Order order, List<Product> products) {
        List<OrderItemResponse> itemResponses = order.getItems().stream()
            .map(item -> {
                Product product = products.stream()
                    .filter(p -> p.getId().equals(item.getProductId()))
                    .findFirst().orElseThrow();
                return new OrderItemResponse(
                    product.getName(),
                    item.getQuantity(),
                    item.getUnitPrice(),
                    item.getQuantity() * item.getUnitPrice()
                );
            }).toList();
        
        return new OrderResponse(
            order.getId(),
            order.getStatus().name(),
            itemResponses,
            order.getTotalAmount(),
            order.getDiscount(),
            order.getNetAmount(),
            order.getCreatedAt().toString()
        );
        // Note: paymentId and internalNotes are NOT exposed!
    }
}

// === Summary DTO (for list views - less data) ===
public record OrderSummaryResponse(
    String orderId,
    String status,
    int itemCount,
    double total,
    String createdAt
) {
    public static OrderSummaryResponse fromEntity(Order order) {
        return new OrderSummaryResponse(
            order.getId(),
            order.getStatus().name(),
            order.getItems().size(),
            order.getNetAmount(),
            order.getCreatedAt().toString()
        );
    }
}

// === Mapper class (alternative to factory methods) ===
public class OrderMapper {
    
    public static Order toEntity(CreateOrderRequest request) {
        Order order = new Order();
        order.setUserId(request.userId());
        order.setItems(request.items().stream()
            .map(item -> new OrderItem(item.productId(), item.quantity()))
            .toList());
        order.setStatus(OrderStatus.CREATED);
        order.setCreatedAt(LocalDateTime.now());
        return order;
    }
    
    public static OrderResponse toResponse(Order order, List<Product> products) {
        return OrderResponse.fromEntity(order, products);
    }
    
    public static OrderSummaryResponse toSummary(Order order) {
        return OrderSummaryResponse.fromEntity(order);
    }
}
```

---

## 5. PATTERN SELECTION GUIDE FOR LLD INTERVIEWS

| LLD Problem | Primary Patterns |
|-------------|-----------------|
| Parking Lot | Strategy (pricing), State (spot status), Observer (notifications), Factory (vehicle types) |
| Elevator System | State (elevator states), Strategy (scheduling), Observer (floor requests), Command (button presses) |
| Vending Machine | State (machine states), Strategy (payment), Chain of Responsibility (validation) |
| Library Management | Repository, Service layer, Observer (due date notifications), Strategy (search) |
| Hotel Booking | Builder (reservation), State (room status), Observer (notifications), Strategy (pricing) |
| Food Delivery | State (order lifecycle), Strategy (delivery assignment), Observer (tracking), Facade (order placement) |
| Chess/Card Game | State (game states), Strategy (AI difficulty), Command (moves/undo), Observer (game events) |
| Logger System | Singleton, Chain of Responsibility (log levels), Strategy (output targets), Decorator (formatting) |
| Cache (LRU) | Singleton, Strategy (eviction policy), Decorator (TTL wrapper) |
| Notification Service | Observer, Strategy (channel selection), Factory (notification types), Template Method (formatting) |
| Payment System | Strategy (payment methods), State (transaction states), Chain of Responsibility (validation) |
| File System | Composite (files/folders), Iterator (traversal), Visitor (operations) |
| URL Shortener | Singleton (ID generator), Strategy (encoding), Repository |
| Rate Limiter | Strategy (algorithm), Singleton, Decorator (wrapping services) |
| Task Scheduler | Command (tasks), Strategy (scheduling), Observer (completion), State (task lifecycle) |

---

## 6. KEY PRINCIPLES

### SOLID Applied to Patterns

```java
// S - Single Responsibility
// Each pattern class has ONE job (Strategy handles ONE algorithm, Observer handles ONE type of notification)

// O - Open/Closed
// Strategy, Decorator: Add new behavior without modifying existing code
//   Add new PaymentStrategy without changing PaymentProcessor

// L - Liskov Substitution
// All concrete strategies are substitutable for the strategy interface
//   Any PaymentStrategy works in PaymentProcessor

// I - Interface Segregation
// Small, focused interfaces (Command has execute/undo, not 20 methods)

// D - Dependency Inversion
// High-level modules depend on abstractions (interfaces), not concrete classes
//   PaymentProcessor depends on PaymentStrategy interface, not CreditCardPayment
```

### Common Interview Tips

1. **Always start with interfaces** - Define the contract first
2. **Use composition over inheritance** - Strategy/Decorator vs deep class hierarchies
3. **Identify what varies** - Encapsulate it (Strategy)
4. **Identify state-dependent behavior** - Use State pattern
5. **Need extensibility** - Use Observer/Strategy/Decorator
6. **Complex object creation** - Use Builder/Factory
7. **Need undo/history** - Use Command pattern
8. **Multiple validation steps** - Use Chain of Responsibility
9. **Complex subsystem** - Use Facade
10. **Tree structures** - Use Composite
