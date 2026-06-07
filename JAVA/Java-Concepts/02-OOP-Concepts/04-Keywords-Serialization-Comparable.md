# Java Keywords, Serialization, Cloning & Comparison — Complete Reference

---

## 1. The `volatile` Keyword

### What It Does

`volatile` guarantees **visibility** across threads. When a variable is declared volatile:
- Every **read** goes directly to **main memory** (not CPU cache)
- Every **write** goes directly to **main memory**
- Establishes a **happens-before** relationship

### What It Does NOT Do

`volatile` does **NOT** guarantee **atomicity**. Operations like `i++` (read-modify-write) are still not thread-safe.

### Happens-Before Relationship

A write to a volatile variable **happens-before** every subsequent read of that variable. This means all variables visible to Thread A before writing to volatile are also visible to Thread B after reading that volatile.

### When to Use

- Boolean flags (`volatile boolean running = true`)
- Double-checked locking in Singleton
- Publishing immutable objects
- Status indicators read by multiple threads

### volatile vs synchronized vs Atomic

| Feature | volatile | synchronized | Atomic classes |
|---------|----------|--------------|----------------|
| Visibility | Yes | Yes | Yes |
| Atomicity | No | Yes | Yes (single op) |
| Blocking | No | Yes | No (CAS) |
| Mutual exclusion | No | Yes | No |
| Performance | Fast | Slowest | Fast |

---

### Example: Volatile Flag for Thread Stopping

```java
public class VolatileFlagExample {

    // Without volatile, the thread might cache 'running' and never see the update
    private volatile boolean running = true;

    public void startWorker() {
        Thread worker = new Thread(() -> {
            int count = 0;
            while (running) {
                count++;
                // Do some work
            }
            System.out.println("Worker stopped after count: " + count);
        });
        worker.start();
    }

    public void stopWorker() {
        running = false; // Immediately visible to worker thread
    }

    public static void main(String[] args) throws InterruptedException {
        VolatileFlagExample example = new VolatileFlagExample();
        example.startWorker();
        Thread.sleep(100);
        example.stopWorker();
        System.out.println("Stop signal sent");
    }
}
```

### Example: Double-Checked Locking Singleton with volatile

```java
public class Singleton {

    // volatile prevents instruction reordering during object construction
    private static volatile Singleton instance;

    private Singleton() {
        // Private constructor
    }

    public static Singleton getInstance() {
        if (instance == null) {                  // First check (no locking)
            synchronized (Singleton.class) {
                if (instance == null) {          // Second check (with lock)
                    instance = new Singleton();  // volatile prevents partial construction visibility
                }
            }
        }
        return instance;
    }
}
```

**Why volatile is needed here:** Without volatile, Thread B might see a non-null `instance` reference that points to a partially constructed object (due to instruction reordering: memory allocation happens before constructor finishes).

### Example: Volatile Doesn't Help with Compound Operations

```java
public class VolatileNotAtomic {

    private volatile int counter = 0;

    public void increment() {
        counter++; // NOT atomic! This is: read -> modify -> write (3 steps)
    }

    public static void main(String[] args) throws InterruptedException {
        VolatileNotAtomic example = new VolatileNotAtomic();

        Thread t1 = new Thread(() -> {
            for (int i = 0; i < 10000; i++) example.increment();
        });
        Thread t2 = new Thread(() -> {
            for (int i = 0; i < 10000; i++) example.increment();
        });

        t1.start();
        t2.start();
        t1.join();
        t2.join();

        // Expected: 20000, Actual: less than 20000 (race condition)
        System.out.println("Counter: " + example.counter);
    }
}
```

**Fix:** Use `AtomicInteger` or `synchronized`.

### Memory Barrier Explanation

```
Thread A (Writer)              Thread B (Reader)
─────────────────              ─────────────────
x = 42;                        
y = 10;                        
// STORE BARRIER              
volatile_flag = true; ───────► if (volatile_flag) {
                               // LOAD BARRIER
                               // x is guaranteed to be 42
                               // y is guaranteed to be 10
                               }
```

The volatile write acts as a **store barrier** (flushes all prior writes), and the volatile read acts as a **load barrier** (invalidates cache, reads from main memory).

---

## 2. The `transient` Keyword

### What It Does

Fields marked `transient` are **excluded from serialization**. During deserialization, transient fields receive their default values (null, 0, false).

### Use Cases

- **Passwords** — never persist sensitive data
- **Computed/derived fields** — can be recalculated
- **Logger references** — not meaningful after deserialization
- **Database connections** — cannot be serialized
- **Thread references** — not transferable

### transient vs static

| Modifier | Serialized? | Reason |
|----------|-------------|--------|
| transient | No | Explicitly excluded |
| static | No | Belongs to class, not instance |
| both | No | Redundant but valid |

---

### Example: Transient Field is Null After Deserialization

```java
import java.io.*;

public class User implements Serializable {
    private static final long serialVersionUID = 1L;

    private String username;
    private transient String password;       // NOT serialized
    private transient int loginAttempts;     // NOT serialized
    private String email;

    public User(String username, String password, String email) {
        this.username = username;
        this.password = password;
        this.email = email;
        this.loginAttempts = 3;
    }

    @Override
    public String toString() {
        return "User{username='" + username + "', password='" + password +
               "', email='" + email + "', loginAttempts=" + loginAttempts + "}";
    }

    public static void main(String[] args) throws Exception {
        User user = new User("john", "secret123", "john@email.com");
        System.out.println("Before: " + user);

        // Serialize
        ByteArrayOutputStream baos = new ByteArrayOutputStream();
        ObjectOutputStream oos = new ObjectOutputStream(baos);
        oos.writeObject(user);
        oos.close();

        // Deserialize
        ByteArrayInputStream bais = new ByteArrayInputStream(baos.toByteArray());
        ObjectInputStream ois = new ObjectInputStream(bais);
        User restored = (User) ois.readObject();
        ois.close();

        System.out.println("After:  " + restored);
        // Output: password=null, loginAttempts=0 (defaults)
    }
}
```

### Example: Custom Serialization with writeObject/readObject

```java
import java.io.*;
import javax.crypto.Cipher;
import javax.crypto.spec.SecretKeySpec;
import java.util.Base64;

public class SecureUser implements Serializable {
    private static final long serialVersionUID = 1L;

    private String username;
    private transient String password; // transient but we handle it manually

    public SecureUser(String username, String password) {
        this.username = username;
        this.password = password;
    }

    // Custom serialization — encrypt the password before writing
    private void writeObject(ObjectOutputStream oos) throws IOException {
        oos.defaultWriteObject(); // Serialize non-transient fields normally
        // Write encrypted password
        String encrypted = Base64.getEncoder().encodeToString(password.getBytes());
        oos.writeObject(encrypted);
    }

    // Custom deserialization — decrypt the password after reading
    private void readObject(ObjectInputStream ois) throws IOException, ClassNotFoundException {
        ois.defaultReadObject(); // Deserialize non-transient fields normally
        // Read and decrypt password
        String encrypted = (String) ois.readObject();
        this.password = new String(Base64.getDecoder().decode(encrypted));
    }

    @Override
    public String toString() {
        return "SecureUser{username='" + username + "', password='" + password + "'}";
    }

    public static void main(String[] args) throws Exception {
        SecureUser user = new SecureUser("admin", "myP@ssw0rd");
        System.out.println("Before: " + user);

        ByteArrayOutputStream baos = new ByteArrayOutputStream();
        ObjectOutputStream oos = new ObjectOutputStream(baos);
        oos.writeObject(user);
        oos.close();

        ByteArrayInputStream bais = new ByteArrayInputStream(baos.toByteArray());
        ObjectInputStream ois = new ObjectInputStream(bais);
        SecureUser restored = (SecureUser) ois.readObject();
        ois.close();

        System.out.println("After:  " + restored);
        // Password is preserved through custom serialization!
    }
}
```

---

## 3. The `final` Keyword — Complete

### final Variable

Cannot be reassigned after initialization. But object contents CAN still change!

```java
public class FinalVariableDemo {
    public static void main(String[] args) {
        final int x = 10;
        // x = 20; // COMPILE ERROR: cannot assign a value to final variable

        final List<String> list = new ArrayList<>();
        list.add("Hello");     // OK — modifying contents, not reference
        list.add("World");     // OK
        // list = new ArrayList<>(); // COMPILE ERROR — cannot reassign reference

        System.out.println(list); // [Hello, World]
    }
}
```

### final Method

Cannot be overridden by subclasses.

```java
public class Parent {
    public final void criticalMethod() {
        System.out.println("This behavior is locked down");
    }

    public void normalMethod() {
        System.out.println("This can be overridden");
    }
}

public class Child extends Parent {
    // public void criticalMethod() {} // COMPILE ERROR: cannot override final method

    @Override
    public void normalMethod() {
        System.out.println("Overridden in child");
    }
}
```

### final Class

Cannot be extended/subclassed. Examples: `String`, `Integer`, `Math`.

```java
public final class ImmutablePoint {
    private final int x;
    private final int y;

    public ImmutablePoint(int x, int y) {
        this.x = x;
        this.y = y;
    }

    public int getX() { return x; }
    public int getY() { return y; }
}

// public class ExtendedPoint extends ImmutablePoint {} // COMPILE ERROR
```

### final Parameter

Cannot be reassigned inside the method body.

```java
public class FinalParameterDemo {
    public void process(final String input) {
        // input = "modified"; // COMPILE ERROR
        System.out.println(input.toUpperCase()); // Can call methods, just can't reassign
    }

    public int calculate(final int a, final int b) {
        // a = a + 1; // COMPILE ERROR
        return a + b;
    }
}
```

### Effectively Final (Java 8+)

A variable is "effectively final" if it's never reassigned after initialization. Required for lambdas and anonymous classes.

```java
public class EffectivelyFinalDemo {
    public static void main(String[] args) {
        String name = "World"; // effectively final (never reassigned)
        // name = "Java"; // If uncommented, lambda below won't compile

        Runnable r = () -> System.out.println("Hello, " + name);
        r.run();

        int multiplier = 5; // effectively final
        IntUnaryOperator op = x -> x * multiplier;
        System.out.println(op.applyAsInt(3)); // 15
    }
}
```

### Blank Final

Declared without initialization — MUST be assigned exactly once in the constructor.

```java
public class BlankFinalDemo {
    private final String id;           // blank final
    private final LocalDateTime created; // blank final

    public BlankFinalDemo(String id) {
        this.id = id;                        // Assigned here
        this.created = LocalDateTime.now();  // Assigned here
    }

    // Every constructor must assign ALL blank finals
    public BlankFinalDemo() {
        this.id = UUID.randomUUID().toString();
        this.created = LocalDateTime.now();
    }
}
```

### final != immutable

`final` prevents reassigning the **reference**, NOT modification of the **object**.

```java
public class FinalNotImmutable {
    public static void main(String[] args) {
        final StringBuilder sb = new StringBuilder("Hello");
        sb.append(" World"); // Perfectly legal — modifying content
        System.out.println(sb); // "Hello World"
        // sb = new StringBuilder(); // COMPILE ERROR — can't reassign reference

        final int[] arr = {1, 2, 3};
        arr[0] = 99; // Legal — modifying array content
        // arr = new int[5]; // COMPILE ERROR — can't reassign reference
    }
}
```

---

## 4. The `static` Keyword — Complete

### static Variable (Class Variable)

Shared by ALL instances. One copy per class.

```java
public class Employee {
    private static int nextId = 1;  // Shared counter
    private static final String COMPANY = "TechCorp"; // static constant

    private int id;
    private String name;

    public Employee(String name) {
        this.id = nextId++;  // Each new employee gets next id
        this.name = name;
    }

    public static int getTotalEmployees() {
        return nextId - 1;
    }

    public static void main(String[] args) {
        Employee e1 = new Employee("Alice");
        Employee e2 = new Employee("Bob");
        Employee e3 = new Employee("Charlie");

        System.out.println(Employee.getTotalEmployees()); // 3
        System.out.println(e1.id + " " + e2.id + " " + e3.id); // 1 2 3
    }
}
```

### static Method

- No `this` reference
- Cannot access instance members directly
- Called via `ClassName.method()`

```java
public class MathUtils {
    // Cannot use 'this' or access instance fields
    public static int max(int a, int b) {
        return a > b ? a : b;
    }

    public static double circleArea(double radius) {
        return Math.PI * radius * radius;
    }

    // Factory method pattern
    public static MathUtils create() {
        return new MathUtils();
    }

    // This would be ILLEGAL in a static method:
    // private int x;
    // public static void illegal() { System.out.println(this.x); }
}
```

### static Block (Static Initializer)

Runs ONCE when the class is first loaded. Used for complex static initialization.

```java
public class DatabaseConfig {
    private static final Map<String, String> CONFIG;
    private static final Properties PROPERTIES;

    static {
        // Complex initialization that can't be done in one line
        CONFIG = new HashMap<>();
        CONFIG.put("url", "jdbc:mysql://localhost:3306/mydb");
        CONFIG.put("user", "admin");
        CONFIG.put("pool_size", "10");
        CONFIG = Collections.unmodifiableMap(CONFIG);

        System.out.println("DatabaseConfig class loaded");
    }

    static {
        // Multiple static blocks allowed — run in order
        PROPERTIES = new Properties();
        try (InputStream is = DatabaseConfig.class.getResourceAsStream("/config.properties")) {
            if (is != null) PROPERTIES.load(is);
        } catch (IOException e) {
            throw new ExceptionInInitializerError(e);
        }
    }
}
```

### static Import

Import static members to use them without class name prefix.

```java
import static java.lang.Math.PI;
import static java.lang.Math.sqrt;
import static java.util.Collections.unmodifiableList;
import static java.util.stream.Collectors.toList;

public class StaticImportDemo {
    public double calculateHypotenuse(double a, double b) {
        return sqrt(a * a + b * b); // Instead of Math.sqrt(...)
    }

    public double circleCircumference(double r) {
        return 2 * PI * r; // Instead of Math.PI
    }
}
```

### static Inner Class

Has no implicit reference to the outer class instance.

```java
public class Outer {
    private int instanceVar = 10;
    private static int staticVar = 20;

    // Static nested class — no reference to Outer instance
    public static class StaticNested {
        public void display() {
            // System.out.println(instanceVar); // COMPILE ERROR — no outer instance
            System.out.println(staticVar); // OK — can access static members
        }
    }

    // Non-static inner class — has reference to Outer instance
    public class Inner {
        public void display() {
            System.out.println(instanceVar);  // OK
            System.out.println(staticVar);    // OK
        }
    }

    public static void main(String[] args) {
        // Static nested: no outer instance needed
        StaticNested nested = new StaticNested();

        // Inner: requires outer instance
        Outer outer = new Outer();
        Inner inner = outer.new Inner();
    }
}
```

### Memory: Metaspace (Java 8+)

- Static variables: stored in the **heap** (as part of the Class object in Metaspace)
- Before Java 8: stored in PermGen (fixed size, could cause OutOfMemoryError)
- Java 8+: stored in **Metaspace** (native memory, auto-grows)
- Static variables live for the lifetime of the ClassLoader

---

## 5. Serialization & Deserialization

### Serializable Interface

`Serializable` is a **marker interface** — it has no methods. It signals to the JVM that instances of this class can be converted to a byte stream.

```java
import java.io.*;

// Marker interface — no methods to implement
public class Product implements Serializable {
    private static final long serialVersionUID = 1L; // Version control

    private String name;
    private double price;
    private int quantity;
    private static String storeName = "MyStore"; // NOT serialized (static)
    private transient double discount;           // NOT serialized (transient)

    public Product(String name, double price, int quantity, double discount) {
        this.name = name;
        this.price = price;
        this.quantity = quantity;
        this.discount = discount;
    }

    @Override
    public String toString() {
        return String.format("Product{name='%s', price=%.2f, qty=%d, discount=%.2f, store='%s'}",
                name, price, quantity, discount, storeName);
    }
}
```

### serialVersionUID

- If you don't declare it, JVM generates one based on class structure
- If class changes (add/remove field), auto-generated UID changes
- Deserialization fails with `InvalidClassException` if UIDs don't match
- **Always declare it explicitly** for forward/backward compatibility

### What Gets Serialized

| Field type | Serialized? |
|-----------|-------------|
| Instance fields | Yes |
| static fields | No (belongs to class) |
| transient fields | No (explicitly excluded) |
| Inherited fields (if parent is Serializable) | Yes |
| Inherited fields (if parent is NOT Serializable) | No (defaults) |

### Complete Example: Serialize/Deserialize Complex Object Graph

```java
import java.io.*;
import java.time.LocalDate;
import java.util.*;

class Address implements Serializable {
    private static final long serialVersionUID = 1L;
    private String street;
    private String city;
    private String zipCode;

    public Address(String street, String city, String zipCode) {
        this.street = street;
        this.city = city;
        this.zipCode = zipCode;
    }

    @Override
    public String toString() {
        return street + ", " + city + " " + zipCode;
    }
}

class Order implements Serializable {
    private static final long serialVersionUID = 1L;
    private String orderId;
    private List<String> items;
    private double total;

    public Order(String orderId, List<String> items, double total) {
        this.orderId = orderId;
        this.items = items;
        this.total = total;
    }

    @Override
    public String toString() {
        return "Order{id=" + orderId + ", items=" + items + ", total=" + total + "}";
    }
}

class Customer implements Serializable {
    private static final long serialVersionUID = 1L;
    private String name;
    private Address address;           // Nested object — also serialized
    private List<Order> orders;        // Collection of objects — all serialized
    private transient String sessionId; // Not serialized

    public Customer(String name, Address address) {
        this.name = name;
        this.address = address;
        this.orders = new ArrayList<>();
        this.sessionId = UUID.randomUUID().toString();
    }

    public void addOrder(Order order) { orders.add(order); }

    @Override
    public String toString() {
        return "Customer{name='" + name + "', address=" + address +
               ", orders=" + orders + ", sessionId=" + sessionId + "}";
    }
}

public class SerializationDemo {
    public static void main(String[] args) throws Exception {
        // Build complex object graph
        Address addr = new Address("123 Main St", "Springfield", "62701");
        Customer customer = new Customer("Jane Doe", addr);
        customer.addOrder(new Order("ORD-001", List.of("Laptop", "Mouse"), 1299.99));
        customer.addOrder(new Order("ORD-002", List.of("Keyboard"), 79.99));

        System.out.println("Before serialization:");
        System.out.println(customer);

        // Serialize to file
        try (ObjectOutputStream oos = new ObjectOutputStream(
                new FileOutputStream("customer.ser"))) {
            oos.writeObject(customer);
        }

        // Deserialize from file
        Customer restored;
        try (ObjectInputStream ois = new ObjectInputStream(
                new FileInputStream("customer.ser"))) {
            restored = (Customer) ois.readObject();
        }

        System.out.println("\nAfter deserialization:");
        System.out.println(restored);
        // Note: sessionId will be null (transient)
    }
}
```

---

### Custom Serialization: Singleton Protection

```java
import java.io.*;

public class SerializableSingleton implements Serializable {
    private static final long serialVersionUID = 1L;

    private static final SerializableSingleton INSTANCE = new SerializableSingleton();

    private String state = "initialized";

    private SerializableSingleton() {
        // Prevent reflection attack
        if (INSTANCE != null) {
            throw new IllegalStateException("Singleton already constructed");
        }
    }

    public static SerializableSingleton getInstance() {
        return INSTANCE;
    }

    public String getState() { return state; }
    public void setState(String state) { this.state = state; }

    // This method is called during deserialization INSTEAD of creating new object
    // It replaces the deserialized object with the existing singleton
    private Object readResolve() throws ObjectStreamException {
        return INSTANCE; // Return the existing singleton instance
    }

    public static void main(String[] args) throws Exception {
        SerializableSingleton original = SerializableSingleton.getInstance();
        original.setState("modified");

        // Serialize
        ByteArrayOutputStream baos = new ByteArrayOutputStream();
        ObjectOutputStream oos = new ObjectOutputStream(baos);
        oos.writeObject(original);
        oos.close();

        // Deserialize
        ByteArrayInputStream bais = new ByteArrayInputStream(baos.toByteArray());
        ObjectInputStream ois = new ObjectInputStream(bais);
        SerializableSingleton deserialized = (SerializableSingleton) ois.readObject();
        ois.close();

        // Verify same instance
        System.out.println("Same instance? " + (original == deserialized)); // true
        System.out.println("State: " + deserialized.getState()); // modified
    }
}
```

---

### Externalizable Interface

Full control over serialization format. You decide exactly what gets written and read.

```java
import java.io.*;
import java.time.LocalDateTime;

public class ExternalizableUser implements Externalizable {
    // MUST have public no-arg constructor (required by Externalizable)
    private String username;
    private String email;
    private int age;
    private LocalDateTime lastLogin;

    // Required: public no-arg constructor
    public ExternalizableUser() {}

    public ExternalizableUser(String username, String email, int age) {
        this.username = username;
        this.email = email;
        this.age = age;
        this.lastLogin = LocalDateTime.now();
    }

    @Override
    public void writeExternal(ObjectOutput out) throws IOException {
        // Full control: choose what to write and in what format
        out.writeUTF(username);
        out.writeUTF(email);
        out.writeInt(age);
        // Deliberately NOT writing lastLogin (ephemeral data)
        out.writeInt(username.length() + email.length()); // Write checksum
    }

    @Override
    public void readExternal(ObjectInput in) throws IOException, ClassNotFoundException {
        // Must read in SAME ORDER as written
        this.username = in.readUTF();
        this.email = in.readUTF();
        this.age = in.readInt();
        int checksum = in.readInt();
        // Validate
        if (checksum != username.length() + email.length()) {
            throw new IOException("Data corruption detected");
        }
        this.lastLogin = LocalDateTime.now(); // Set fresh value
    }

    @Override
    public String toString() {
        return "User{name='" + username + "', email='" + email +
               "', age=" + age + ", lastLogin=" + lastLogin + "}";
    }

    public static void main(String[] args) throws Exception {
        ExternalizableUser user = new ExternalizableUser("alice", "alice@dev.io", 28);
        System.out.println("Before: " + user);

        ByteArrayOutputStream baos = new ByteArrayOutputStream();
        ObjectOutputStream oos = new ObjectOutputStream(baos);
        oos.writeObject(user);
        oos.close();

        ByteArrayInputStream bais = new ByteArrayInputStream(baos.toByteArray());
        ObjectInputStream ois = new ObjectInputStream(bais);
        ExternalizableUser restored = (ExternalizableUser) ois.readObject();
        ois.close();

        System.out.println("After:  " + restored);
    }
}
```

### Serializable vs Externalizable

| Aspect | Serializable | Externalizable |
|--------|-------------|----------------|
| Methods | None (marker) | writeExternal, readExternal |
| Default behavior | Serializes all non-static/non-transient | Nothing — you write everything |
| Constructor | Not called during deserialization | Public no-arg REQUIRED |
| Control | Partial (transient, custom writeObject) | Full |
| Performance | Slower (reflection-based) | Faster (explicit) |

---

### Serialization Gotchas

**1. Inheritance — Parent not Serializable:**
```java
class Animal {  // NOT Serializable
    String species = "Unknown";
    public Animal() { this.species = "Default"; } // Called during deserialization!
}

class Dog extends Animal implements Serializable {
    private static final long serialVersionUID = 1L;
    String name;

    public Dog(String name, String species) {
        this.name = name;
        this.species = species;
    }
}

// After deserialization: name = "Rex", species = "Default" (parent constructor ran!)
```

**2. Version compatibility:**
- Adding a field: old data deserializes fine (new field gets default)
- Removing a field: old data's value is silently ignored
- Changing field type: `InvalidClassException`

**3. Security risks:**
- Deserialization can execute arbitrary code
- Never deserialize untrusted data
- Use serialization filters (Java 9+): `ObjectInputFilter`

---

## 6. Cloneable & clone()

### Object.clone() Basics

- `clone()` is a **protected** method in `Object`
- You must implement `Cloneable` marker interface
- Without `Cloneable`, calling `clone()` throws `CloneNotSupportedException`
- Returns a **shallow copy** by default

### Shallow vs Deep Copy

```
SHALLOW COPY:
┌──────────┐          ┌──────────┐
│ original │          │  clone   │
├──────────┤          ├──────────┤
│ name ────┼─────►"John"◄────┼── name   │  ← Same String object
│ address ─┼──┐              ┌┼─ address │  ← Same Address object!
└──────────┘  │  ┌────────┐  │└──────────┘
              └─►│ Address │◄─┘
                 └────────┘

DEEP COPY:
┌──────────┐          ┌──────────┐
│ original │          │  clone   │
├──────────┤          ├──────────┤
│ name ────┼──►"John"  "John"◄──┼── name   │  ← Separate objects
│ address ─┼──►┌────┐  ┌────┐◄──┼── address │  ← Separate objects
└──────────┘   │Addr│  │Addr│   └──────────┘
               └────┘  └────┘
```

### Complete Example: Shallow vs Deep Copy

```java
import java.util.*;

class Address implements Cloneable {
    String city;
    String street;

    public Address(String city, String street) {
        this.city = city;
        this.street = street;
    }

    @Override
    protected Address clone() throws CloneNotSupportedException {
        return (Address) super.clone();
    }

    @Override
    public String toString() {
        return city + ", " + street;
    }
}

class Person implements Cloneable {
    String name;
    int age;
    Address address;          // Mutable reference type
    List<String> hobbies;     // Mutable collection

    public Person(String name, int age, Address address, List<String> hobbies) {
        this.name = name;
        this.age = age;
        this.address = address;
        this.hobbies = hobbies;
    }

    // SHALLOW clone — address and hobbies are shared references
    @Override
    protected Person clone() throws CloneNotSupportedException {
        return (Person) super.clone();
    }

    // DEEP clone — creates independent copies of all mutable fields
    public Person deepClone() throws CloneNotSupportedException {
        Person cloned = (Person) super.clone();
        cloned.address = this.address.clone();              // Clone sub-object
        cloned.hobbies = new ArrayList<>(this.hobbies);    // Copy collection
        return cloned;
    }

    @Override
    public String toString() {
        return "Person{name='" + name + "', age=" + age +
               ", address=" + address + ", hobbies=" + hobbies + "}";
    }
}

public class CloneDemo {
    public static void main(String[] args) throws CloneNotSupportedException {
        Address addr = new Address("NYC", "5th Avenue");
        List<String> hobbies = new ArrayList<>(List.of("Reading", "Coding"));
        Person original = new Person("Alice", 30, addr, hobbies);

        // Shallow clone
        Person shallowClone = original.clone();
        shallowClone.address.city = "LA";      // CHANGES original's address too!
        shallowClone.hobbies.add("Gaming");     // CHANGES original's hobbies too!

        System.out.println("After shallow clone modification:");
        System.out.println("Original: " + original);   // city=LA, hobbies includes Gaming!
        System.out.println("Clone:    " + shallowClone);

        // Reset
        addr = new Address("NYC", "5th Avenue");
        hobbies = new ArrayList<>(List.of("Reading", "Coding"));
        original = new Person("Alice", 30, addr, hobbies);

        // Deep clone
        Person deepClone = original.deepClone();
        deepClone.address.city = "LA";         // Does NOT affect original
        deepClone.hobbies.add("Gaming");        // Does NOT affect original

        System.out.println("\nAfter deep clone modification:");
        System.out.println("Original: " + original);   // city=NYC, no Gaming
        System.out.println("Clone:    " + deepClone);  // city=LA, has Gaming
    }
}
```

### Deep Clone via Serialization

```java
import java.io.*;

public class SerializationCloner {

    @SuppressWarnings("unchecked")
    public static <T extends Serializable> T deepClone(T object) {
        try {
            ByteArrayOutputStream baos = new ByteArrayOutputStream();
            ObjectOutputStream oos = new ObjectOutputStream(baos);
            oos.writeObject(object);
            oos.close();

            ByteArrayInputStream bais = new ByteArrayInputStream(baos.toByteArray());
            ObjectInputStream ois = new ObjectInputStream(bais);
            T clone = (T) ois.readObject();
            ois.close();

            return clone;
        } catch (IOException | ClassNotFoundException e) {
            throw new RuntimeException("Deep clone failed", e);
        }
    }
}
```

### Why clone() is Broken (Effective Java)

1. **Constructor not called** — clone() bypasses constructors, breaking invariants
2. **Final fields can't be set** — clone returns Object, can't reassign final fields
3. **Covariant return types needed** — must cast manually
4. **Checked exception** — CloneNotSupportedException is awkward
5. **Inheritance issues** — subclass clone might not call super.clone()

### Preferred: Copy Constructor Pattern

```java
public class Employee {
    private final String name;
    private final int id;
    private final List<String> skills;
    private final Address address;

    // Regular constructor
    public Employee(String name, int id, List<String> skills, Address address) {
        this.name = name;
        this.id = id;
        this.skills = new ArrayList<>(skills);
        this.address = new Address(address); // Address also has copy constructor
    }

    // Copy constructor — PREFERRED over clone()
    public Employee(Employee other) {
        this.name = other.name;
        this.id = other.id;
        this.skills = new ArrayList<>(other.skills);       // Deep copy of list
        this.address = new Address(other.address);         // Deep copy of address
    }

    // Static factory method alternative
    public static Employee copyOf(Employee other) {
        return new Employee(other);
    }

    @Override
    public String toString() {
        return "Employee{name='" + name + "', id=" + id +
               ", skills=" + skills + ", address=" + address + "}";
    }

    public static void main(String[] args) {
        Employee original = new Employee("Bob", 101,
                new ArrayList<>(List.of("Java", "Python")),
                new Address("Chicago", "Elm St"));

        Employee copy = new Employee(original);  // Deep copy via copy constructor
        // OR: Employee copy = Employee.copyOf(original);

        System.out.println("Original: " + original);
        System.out.println("Copy:     " + copy);
        System.out.println("Same object? " + (original == copy)); // false
    }
}
```

---

## 7. Comparable vs Comparator

### Comparable<T> — Natural Ordering

Defined **inside** the class. Provides ONE natural ordering.

```java
public class Employee implements Comparable<Employee> {
    private int id;
    private String name;
    private double salary;
    private int age;

    public Employee(int id, String name, double salary, int age) {
        this.id = id;
        this.name = name;
        this.salary = salary;
        this.age = age;
    }

    // Natural ordering: by id
    @Override
    public int compareTo(Employee other) {
        return Integer.compare(this.id, other.id);
        // Returns: negative if this < other, 0 if equal, positive if this > other
    }

    // Getters
    public int getId() { return id; }
    public String getName() { return name; }
    public double getSalary() { return salary; }
    public int getAge() { return age; }

    @Override
    public String toString() {
        return String.format("Employee{id=%d, name='%s', salary=%.0f, age=%d}",
                id, name, salary, age);
    }

    public static void main(String[] args) {
        List<Employee> employees = new ArrayList<>(List.of(
                new Employee(3, "Charlie", 75000, 35),
                new Employee(1, "Alice", 90000, 28),
                new Employee(2, "Bob", 85000, 32)
        ));

        Collections.sort(employees); // Uses compareTo (natural ordering by id)
        employees.forEach(System.out::println);
        // Output: sorted by id: 1-Alice, 2-Bob, 3-Charlie

        // Also works with TreeSet
        TreeSet<Employee> sorted = new TreeSet<>(employees);
        System.out.println("TreeSet: " + sorted);
    }
}
```

### Comparable Contract

1. **Antisymmetric:** `sgn(x.compareTo(y)) == -sgn(y.compareTo(x))`
2. **Transitive:** if `x.compareTo(y) > 0` and `y.compareTo(z) > 0`, then `x.compareTo(z) > 0`
3. **Consistent:** if `x.compareTo(y) == 0`, then `sgn(x.compareTo(z)) == sgn(y.compareTo(z))`
4. **Consistent with equals (recommended):** `x.compareTo(y) == 0` should mean `x.equals(y)`

---

### Comparator<T> — External Comparison Strategy

Multiple sort orders without modifying the class.

```java
import java.util.*;
import java.util.stream.*;

public class ComparatorDemo {

    // Traditional anonymous class approach
    static Comparator<Employee> byName = new Comparator<Employee>() {
        @Override
        public int compare(Employee a, Employee b) {
            return a.getName().compareTo(b.getName());
        }
    };

    // Lambda approach
    static Comparator<Employee> bySalary = (a, b) -> Double.compare(a.getSalary(), b.getSalary());

    // Method reference approach (Java 8+)
    static Comparator<Employee> byAge = Comparator.comparingInt(Employee::getAge);

    // Chained comparators: sort by name, then salary (descending), then age
    static Comparator<Employee> complex = Comparator
            .comparing(Employee::getName)
            .thenComparing(Comparator.comparingDouble(Employee::getSalary).reversed())
            .thenComparingInt(Employee::getAge);

    public static void main(String[] args) {
        List<Employee> employees = List.of(
                new Employee(1, "Alice", 90000, 28),
                new Employee(2, "Bob", 85000, 32),
                new Employee(3, "Alice", 75000, 35),
                new Employee(4, "Charlie", 90000, 28),
                new Employee(5, "Bob", 95000, 29)
        );

        // Sort by salary (ascending)
        System.out.println("=== By Salary ===");
        employees.stream()
                .sorted(bySalary)
                .forEach(System.out::println);

        // Sort by salary (descending)
        System.out.println("\n=== By Salary (Descending) ===");
        employees.stream()
                .sorted(bySalary.reversed())
                .forEach(System.out::println);

        // Sort by name, then by salary descending, then by age
        System.out.println("\n=== Complex Sort ===");
        employees.stream()
                .sorted(complex)
                .forEach(System.out::println);
    }
}
```

### Java 8 Comparator Utility Methods — Complete

```java
import java.util.*;

public class ComparatorUtilities {

    record Student(String name, Integer grade, Double gpa) {}

    public static void main(String[] args) {
        List<Student> students = new ArrayList<>(List.of(
                new Student("Alice", 12, 3.9),
                new Student("Bob", null, 3.5),
                new Student("Charlie", 11, null),
                new Student("Diana", 12, 3.7),
                new Student(null, 10, 3.8)
        ));

        // --- Comparator.comparing(keyExtractor) ---
        Comparator<Student> byGrade = Comparator.comparing(
                Student::grade, Comparator.nullsLast(Comparator.naturalOrder()));

        // --- Comparator.comparingInt/Long/Double (avoids boxing) ---
        // Comparator<Student> byGradePrimitive = Comparator.comparingInt(Student::grade);

        // --- .thenComparing() chaining ---
        Comparator<Student> byGradeThenGpa = Comparator
                .comparing(Student::grade, Comparator.nullsLast(Comparator.naturalOrder()))
                .thenComparing(Student::gpa, Comparator.nullsLast(Comparator.reverseOrder()));

        // --- .reversed() ---
        Comparator<Student> byGpaDescending = Comparator
                .comparing(Student::gpa, Comparator.nullsFirst(Comparator.naturalOrder()))
                .reversed();

        // --- Comparator.naturalOrder() & reverseOrder() ---
        List<String> names = List.of("Charlie", "Alice", "Bob");
        List<String> sorted = names.stream()
                .sorted(Comparator.naturalOrder())
                .collect(java.util.stream.Collectors.toList());
        System.out.println("Natural: " + sorted); // [Alice, Bob, Charlie]

        List<String> reversed = names.stream()
                .sorted(Comparator.reverseOrder())
                .collect(java.util.stream.Collectors.toList());
        System.out.println("Reversed: " + reversed); // [Charlie, Bob, Alice]

        // --- Comparator.nullsFirst() & nullsLast() ---
        Comparator<Student> nullSafeName = Comparator.comparing(
                Student::name, Comparator.nullsFirst(Comparator.naturalOrder()));

        students.sort(nullSafeName);
        System.out.println("\nNull-safe name sort (nulls first):");
        students.forEach(s -> System.out.println("  " + s));

        // --- Complete chained example ---
        Comparator<Student> fullComparator = Comparator
                .comparing(Student::grade, Comparator.nullsLast(Comparator.naturalOrder()))
                .thenComparing(Student::gpa, Comparator.nullsFirst(Comparator.reverseOrder()))
                .thenComparing(Student::name, Comparator.nullsLast(Comparator.naturalOrder()));

        students.sort(fullComparator);
        System.out.println("\nFull sort (grade asc, gpa desc, name asc):");
        students.forEach(s -> System.out.println("  " + s));
    }
}
```

### Comparable vs Comparator — Summary Table

| Aspect | Comparable | Comparator |
|--------|-----------|------------|
| Interface | `java.lang.Comparable<T>` | `java.util.Comparator<T>` |
| Method | `compareTo(T other)` | `compare(T a, T b)` |
| # of orderings | 1 (natural ordering) | Many (unlimited) |
| Modifies class? | Yes (implements interface) | No (external) |
| Package | `java.lang` (auto-imported) | `java.util` (must import) |
| Sorting call | `Collections.sort(list)` | `Collections.sort(list, comp)` |
| Use with | TreeSet, TreeMap directly | Passed as argument |
| Can sort 3rd-party classes? | No (can't modify) | Yes |
| Java 8 support | N/A | Static/default methods |
| Functional interface? | No | Yes (`@FunctionalInterface`) |

---

## 8. The `instanceof` Keyword & Pattern Matching

### Traditional instanceof + Cast

```java
public class TraditionalInstanceof {
    public static void process(Object obj) {
        if (obj instanceof String) {
            String s = (String) obj; // Explicit cast required
            System.out.println("String of length: " + s.length());
        } else if (obj instanceof Integer) {
            Integer i = (Integer) obj;
            System.out.println("Integer value: " + i);
        } else if (obj instanceof List) {
            List<?> list = (List<?>) obj;
            System.out.println("List of size: " + list.size());
        }
    }
}
```

### Pattern Matching instanceof (Java 16+)

Combines type check AND cast in one expression.

```java
public class PatternMatchingInstanceof {
    public static void process(Object obj) {
        // Variable 's' is only in scope where the pattern matches
        if (obj instanceof String s) {
            System.out.println("String of length: " + s.length());
        } else if (obj instanceof Integer i) {
            System.out.println("Integer doubled: " + (i * 2));
        } else if (obj instanceof List<?> list && !list.isEmpty()) {
            // Can combine with conditions using &&
            System.out.println("Non-empty list, first: " + list.get(0));
        } else if (obj instanceof int[] arr && arr.length > 0) {
            System.out.println("Int array, sum: " + java.util.Arrays.stream(arr).sum());
        }
    }

    // Works great in equals() implementations
    @Override
    public boolean equals(Object obj) {
        return obj instanceof PatternMatchingInstanceof other
                && this.hashCode() == other.hashCode();
    }

    public static void main(String[] args) {
        process("Hello");
        process(42);
        process(List.of("a", "b", "c"));
        process(new int[]{1, 2, 3, 4, 5});
        process(3.14); // No match — falls through
    }
}
```

### Sealed Classes + Pattern Matching (Java 17+)

```java
// Sealed hierarchy — compiler knows all subtypes
public sealed interface Shape permits Circle, Rectangle, Triangle {}

public record Circle(double radius) implements Shape {}
public record Rectangle(double width, double height) implements Shape {}
public record Triangle(double base, double height) implements Shape {}

public class SealedPatternMatching {
    public static double area(Shape shape) {
        if (shape instanceof Circle c) {
            return Math.PI * c.radius() * c.radius();
        } else if (shape instanceof Rectangle r) {
            return r.width() * r.height();
        } else if (shape instanceof Triangle t) {
            return 0.5 * t.base() * t.height();
        }
        throw new IllegalArgumentException("Unknown shape"); // Compiler can't verify exhaustiveness here
    }
}
```

### Switch Pattern Matching (Java 21)

```java
public class SwitchPatternMatching {

    // Exhaustive switch with pattern matching (Java 21)
    public static double area(Shape shape) {
        return switch (shape) {
            case Circle c    -> Math.PI * c.radius() * c.radius();
            case Rectangle r -> r.width() * r.height();
            case Triangle t  -> 0.5 * t.base() * t.height();
            // No default needed — sealed interface, all cases covered!
        };
    }

    // Guarded patterns with 'when' clause
    public static String classify(Shape shape) {
        return switch (shape) {
            case Circle c when c.radius() > 100    -> "Large circle";
            case Circle c when c.radius() > 10     -> "Medium circle";
            case Circle c                           -> "Small circle";
            case Rectangle r when r.width() == r.height() -> "Square";
            case Rectangle r                        -> "Rectangle";
            case Triangle t                         -> "Triangle";
        };
    }

    // Pattern matching with null handling
    public static String describe(Object obj) {
        return switch (obj) {
            case null           -> "null value";
            case Integer i      -> "Integer: " + i;
            case String s       -> "String: " + s;
            case int[] arr      -> "Array of length " + arr.length;
            case Long l         -> "Long: " + l;
            default             -> "Unknown: " + obj.getClass().getSimpleName();
        };
    }

    public static void main(String[] args) {
        System.out.println(area(new Circle(5)));        // 78.54
        System.out.println(area(new Rectangle(3, 4))); // 12.0
        System.out.println(area(new Triangle(6, 8)));  // 24.0

        System.out.println(classify(new Circle(150)));       // Large circle
        System.out.println(classify(new Rectangle(5, 5)));   // Square

        System.out.println(describe(null));       // null value
        System.out.println(describe(42));         // Integer: 42
        System.out.println(describe("hi"));       // String: hi
    }
}
```

---

## 9. `equals()` and `hashCode()` Contract

### Why Override Both Together

- `HashMap`, `HashSet`, `Hashtable` use `hashCode()` to find the bucket, then `equals()` to find the exact match
- If two objects are `equals()` but have different `hashCode()`, they'll be in different buckets — HashMap breaks!

### The Contract

1. **Consistent:** Multiple calls to `hashCode()` return same value (if object hasn't changed)
2. **equals → same hashCode:** If `a.equals(b)` is true, then `a.hashCode() == b.hashCode()`
3. **Different hashCode → not equals:** If hashCodes differ, objects MUST not be equal
4. **Same hashCode does NOT mean equals** (collisions are allowed)

```
equals() == true   →   hashCode() MUST be same
equals() == false  →   hashCode() CAN be same (collision) or different
hashCode() same    →   equals() CAN be true or false
hashCode() diff    →   equals() MUST be false
```

### Complete Example: Correct Implementation

```java
import java.util.*;

public class Employee {
    private final int id;
    private final String name;
    private final String department;
    private final double salary;

    public Employee(int id, String name, String department, double salary) {
        this.id = id;
        this.name = name;
        this.department = department;
        this.salary = salary;
    }

    @Override
    public boolean equals(Object obj) {
        // 1. Reference check (same object)
        if (this == obj) return true;

        // 2. Null and type check (pattern matching style, Java 16+)
        if (!(obj instanceof Employee other)) return false;

        // 3. Field-by-field comparison
        return this.id == other.id
                && Double.compare(this.salary, other.salary) == 0
                && Objects.equals(this.name, other.name)
                && Objects.equals(this.department, other.department);
    }

    @Override
    public int hashCode() {
        return Objects.hash(id, name, department, salary);
    }

    @Override
    public String toString() {
        return "Employee{id=" + id + ", name='" + name + "'}";
    }

    // Getters
    public int getId() { return id; }
    public String getName() { return name; }
    public String getDepartment() { return department; }
    public double getSalary() { return salary; }
}
```

### What Happens When Contract is Broken

```java
public class BrokenContractDemo {

    static class BadKey {
        int value;

        BadKey(int value) { this.value = value; }

        @Override
        public boolean equals(Object obj) {
            if (obj instanceof BadKey other) {
                return this.value == other.value;
            }
            return false;
        }

        // DELIBERATELY NOT overriding hashCode() — contract is BROKEN
        // Each object uses Object.hashCode() (memory address based)
    }

    public static void main(String[] args) {
        Map<BadKey, String> map = new HashMap<>();

        BadKey key1 = new BadKey(42);
        map.put(key1, "Hello");

        BadKey key2 = new BadKey(42);  // Same logical value
        System.out.println("key1.equals(key2): " + key1.equals(key2)); // true

        // BUT: HashMap can't find it because hashCodes are different!
        System.out.println("map.get(key2): " + map.get(key2)); // null !!
        System.out.println("map.get(key1): " + map.get(key1)); // "Hello"

        // HashSet also breaks
        Set<BadKey> set = new HashSet<>();
        set.add(new BadKey(1));
        set.add(new BadKey(1)); // Should be duplicate, but...
        System.out.println("Set size: " + set.size()); // 2 (should be 1!)
    }
}
```

### Manual hashCode() vs Objects.hash()

```java
public class ManualHashCode {
    private int id;
    private String name;
    private double salary;
    private boolean active;

    // Manual implementation (slightly faster — no array allocation)
    @Override
    public int hashCode() {
        int result = 17; // Start with non-zero prime
        result = 31 * result + id;
        result = 31 * result + (name != null ? name.hashCode() : 0);
        result = 31 * result + Double.hashCode(salary);
        result = 31 * result + Boolean.hashCode(active);
        return result;
    }

    // Equivalent using Objects.hash (cleaner, slightly slower)
    // @Override
    // public int hashCode() {
    //     return Objects.hash(id, name, salary, active);
    // }
}
```

### Records Auto-Generate equals/hashCode

```java
// Records automatically get correct equals(), hashCode(), and toString()
public record Point(int x, int y) {}

public record Employee(int id, String name, double salary) {}

public class RecordDemo {
    public static void main(String[] args) {
        Point p1 = new Point(3, 4);
        Point p2 = new Point(3, 4);

        System.out.println(p1.equals(p2));          // true
        System.out.println(p1.hashCode() == p2.hashCode()); // true

        // Works correctly with HashMap
        Map<Point, String> map = new HashMap<>();
        map.put(p1, "Origin offset");
        System.out.println(map.get(p2)); // "Origin offset" — works!

        // Works correctly with HashSet
        Set<Employee> employees = new HashSet<>();
        employees.add(new Employee(1, "Alice", 90000));
        employees.add(new Employee(1, "Alice", 90000)); // Duplicate detected
        System.out.println("Set size: " + employees.size()); // 1
    }
}
```

### equals() Best Practices

```java
public class EqualsRules {
    // 1. REFLEXIVE: x.equals(x) must be true
    // 2. SYMMETRIC: x.equals(y) ↔ y.equals(x)
    // 3. TRANSITIVE: x.equals(y) && y.equals(z) → x.equals(z)
    // 4. CONSISTENT: multiple calls return same result
    // 5. NULL: x.equals(null) must be false

    // WRONG: using getClass() — breaks Liskov Substitution Principle
    // @Override
    // public boolean equals(Object obj) {
    //     if (obj == null || getClass() != obj.getClass()) return false;
    //     // This means a subclass instance can NEVER equal a parent instance
    // }

    // RIGHT: using instanceof (allows subclass equality if appropriate)
    // @Override
    // public boolean equals(Object obj) {
    //     if (!(obj instanceof MyClass other)) return false;
    //     return this.field == other.field;
    // }
}
```

---

## Quick Reference: All Keywords Summary

| Keyword | Purpose | Key Point |
|---------|---------|-----------|
| `volatile` | Thread visibility | No atomicity guarantee |
| `transient` | Skip serialization | Default value after deserialization |
| `final` | Prevent reassignment/override/extension | Does NOT mean immutable |
| `static` | Class-level member | No `this`, shared across instances |
| `instanceof` | Type checking | Pattern matching in Java 16+ |
| `synchronized` | Mutual exclusion + visibility | Monitor-based locking |
| `native` | JNI method (implemented in C/C++) | No Java body |
| `strictfp` | Strict floating-point math | Deprecated in Java 17 |

---

## Common Interview Questions — Quick Answers

**Q: Can a volatile variable be used for compound operations like i++?**
A: No. Use `AtomicInteger` or `synchronized` for compound operations.

**Q: What happens if a class has a transient field but also implements Externalizable?**
A: The `transient` modifier is meaningless with Externalizable — you control everything in writeExternal/readExternal.

**Q: Can you make a constructor final?**
A: No. Constructors are not inherited, so `final` is meaningless.

**Q: Can we override a static method?**
A: No. Static methods are hidden (method hiding), not overridden. The call is resolved at compile time based on reference type.

**Q: What's the difference between deep copy via clone() vs serialization vs copy constructor?**
A: Clone is error-prone and legacy. Serialization is slow but automatic. Copy constructor is the modern recommended approach — explicit, type-safe, handles final fields.

**Q: If Comparable's compareTo returns 0, does that mean equals returns true?**
A: Not necessarily, but it's strongly recommended to be consistent with equals. `BigDecimal` violates this (`new BigDecimal("1.0").compareTo(new BigDecimal("1.00")) == 0` but `equals()` is false).

**Q: Can you sort a list that contains null elements?**
A: Use `Comparator.nullsFirst()` or `Comparator.nullsLast()` to handle nulls safely.

---

## End of Reference
