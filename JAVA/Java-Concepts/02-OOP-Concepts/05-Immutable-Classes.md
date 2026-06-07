# Immutable Classes in Java — Complete Reference

---

## 1. Rules for Creating Immutable Classes

1. Declare class as `final` (prevent subclassing that could add mutability)
2. All fields `private final`
3. No setter methods
4. Initialize all fields via constructor
5. Defensive copying for mutable fields (in constructor AND getters)
6. Don't allow `this` to escape during construction

---

## 2. Simple Immutable Class

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

    // No setters! To "modify", return a new instance
    public ImmutablePoint translate(int dx, int dy) {
        return new ImmutablePoint(this.x + dx, this.y + dy);
    }

    @Override
    public String toString() {
        return "(" + x + ", " + y + ")";
    }

    @Override
    public boolean equals(Object o) {
        if (this == o) return true;
        if (!(o instanceof ImmutablePoint)) return false;
        ImmutablePoint that = (ImmutablePoint) o;
        return x == that.x && y == that.y;
    }

    @Override
    public int hashCode() {
        return 31 * x + y;
    }
}
```

---

## 3. WRONG Way — Mutable Field Exposed

```java
import java.util.List;
import java.util.ArrayList;

// THIS IS BROKEN — NOT TRULY IMMUTABLE
public final class BrokenImmutablePerson {
    private final String name;
    private final List<String> hobbies;

    public BrokenImmutablePerson(String name, List<String> hobbies) {
        this.name = name;
        this.hobbies = hobbies; // BUG: stores reference to external mutable list
    }

    public String getName() { return name; }

    public List<String> getHobbies() {
        return hobbies; // BUG: returns internal mutable list
    }
}

// Attack:
// List<String> hobbies = new ArrayList<>(List.of("Reading", "Coding"));
// BrokenImmutablePerson person = new BrokenImmutablePerson("Alice", hobbies);
// hobbies.add("Hacking");          // modifies internal state!
// person.getHobbies().clear();      // also modifies internal state!
```

---

## 4. CORRECT Way — Defensive Copying

```java
import java.util.List;
import java.util.ArrayList;
import java.util.Collections;

public final class ImmutablePerson {
    private final String name;
    private final int age;
    private final List<String> hobbies;

    public ImmutablePerson(String name, int age, List<String> hobbies) {
        this.name = name;
        this.age = age;
        // Defensive copy in constructor — don't trust the caller's list
        this.hobbies = new ArrayList<>(hobbies); // creates a new independent copy
    }

    public String getName() { return name; }
    public int getAge() { return age; }

    public List<String> getHobbies() {
        // Return unmodifiable view — caller can't modify our internal list
        return Collections.unmodifiableList(hobbies);
        // Alternative: return new ArrayList<>(hobbies); // return a copy
    }

    @Override
    public String toString() {
        return "ImmutablePerson{name='" + name + "', age=" + age + ", hobbies=" + hobbies + "}";
    }
}

// Usage:
// List<String> hobbies = new ArrayList<>(List.of("Reading", "Coding"));
// ImmutablePerson person = new ImmutablePerson("Alice", 30, hobbies);
// hobbies.add("Hacking");           // doesn't affect person — we copied it
// person.getHobbies().add("X");     // throws UnsupportedOperationException
```

---

## 5. Deep Defensive Copying with Mutable Fields (Date, Address)

```java
import java.util.Date;
import java.util.Objects;

// Mutable Address class (used inside immutable class)
final class Address {
    private final String street;
    private final String city;

    public Address(String street, String city) {
        this.street = street;
        this.city = city;
    }

    public String getStreet() { return street; }
    public String getCity() { return city; }

    // Address is already immutable (all fields are final Strings)
    // If it were mutable, we'd need to clone it
}

public final class ImmutableEmployee {
    private final String name;
    private final Date joinDate;     // Date is MUTABLE!
    private final Address address;   // Our Address is immutable, but in general...

    public ImmutableEmployee(String name, Date joinDate, Address address) {
        this.name = Objects.requireNonNull(name, "name must not be null");
        // Defensive copy of mutable Date
        this.joinDate = new Date(joinDate.getTime());
        this.address = Objects.requireNonNull(address);
    }

    public String getName() { return name; }

    public Date getJoinDate() {
        // Return defensive copy — never expose the internal Date
        return new Date(joinDate.getTime());
    }

    public Address getAddress() {
        return address; // Address is immutable, safe to return directly
    }

    @Override
    public String toString() {
        return "ImmutableEmployee{name='" + name + "', joinDate=" + joinDate +
               ", address=" + address.getCity() + "}";
    }
}

// Usage:
// Date date = new Date();
// ImmutableEmployee emp = new ImmutableEmployee("Bob", date, new Address("123 St", "NYC"));
// date.setTime(0);            // doesn't affect emp — we copied it
// emp.getJoinDate().setTime(0); // doesn't affect emp — we returned a copy
```

---

## 6. Deep Copy with Mutable Sub-Objects

```java
import java.util.*;

// What if Address was MUTABLE?
class MutableAddress {
    private String street;
    private String city;

    public MutableAddress(String street, String city) {
        this.street = street;
        this.city = city;
    }

    public String getStreet() { return street; }
    public void setStreet(String street) { this.street = street; }
    public String getCity() { return city; }
    public void setCity(String city) { this.city = city; }

    // Copy constructor for deep copy
    public MutableAddress(MutableAddress other) {
        this.street = other.street;
        this.city = other.city;
    }
}

public final class ImmutableStudent {
    private final String name;
    private final MutableAddress address; // mutable field!

    public ImmutableStudent(String name, MutableAddress address) {
        this.name = name;
        // DEEP COPY in constructor — use copy constructor
        this.address = new MutableAddress(address);
    }

    public String getName() { return name; }

    public MutableAddress getAddress() {
        // DEEP COPY in getter — never expose the internal mutable object
        return new MutableAddress(address);
    }
}

// Usage:
// MutableAddress addr = new MutableAddress("123 St", "NYC");
// ImmutableStudent student = new ImmutableStudent("Alice", addr);
// addr.setCity("LA");                     // doesn't affect student
// student.getAddress().setCity("Chicago"); // doesn't affect student (returned a copy)
```

---

## 7. Benefits of Immutability

```java
import java.util.HashMap;
import java.util.Map;

public class ImmutabilityBenefits {
    public static void main(String[] args) {

        // 1. THREAD-SAFETY: No synchronization needed
        // Immutable objects can be shared freely between threads
        ImmutablePoint point = new ImmutablePoint(10, 20);
        // Any thread can read point.getX() without locks

        // 2. SAFE HASHMAP KEYS: hashCode never changes
        Map<ImmutablePoint, String> map = new HashMap<>();
        ImmutablePoint key = new ImmutablePoint(1, 2);
        map.put(key, "origin-adjacent");
        // key can never be mutated, so map.get(key) always works
        System.out.println(map.get(new ImmutablePoint(1, 2))); // "origin-adjacent"

        // 3. CACHING: Can be freely cached without worrying about stale state
        // String interning is possible because String is immutable

        // 4. SECURITY: Parameters can't be changed after validation
        // E.g., file path validated then used — immutable means no TOCTOU attack

        // 5. FAILURE ATOMICITY: If an operation fails, object is still in valid state
        // (because state never changes)
    }
}
```

---

## 8. Collections.unmodifiableList vs List.of (Java 9+)

```java
import java.util.*;

public class UnmodifiableVsOf {
    public static void main(String[] args) {

        // === Collections.unmodifiableList() — view over existing list ===
        List<String> original = new ArrayList<>(List.of("A", "B", "C"));
        List<String> unmodifiable = Collections.unmodifiableList(original);

        // unmodifiable.add("D");  // throws UnsupportedOperationException
        original.add("D");          // modifies the underlying list!
        System.out.println(unmodifiable); // [A, B, C, D] — view reflects change!

        // === List.of() (Java 9+) — truly immutable, no backing list ===
        List<String> immutableList = List.of("X", "Y", "Z");
        // immutableList.add("W");  // throws UnsupportedOperationException
        // No way to modify it through any reference

        // === List.copyOf() (Java 10+) — immutable copy of existing collection ===
        List<String> source = new ArrayList<>(List.of("1", "2", "3"));
        List<String> copied = List.copyOf(source);
        source.add("4");
        System.out.println(copied); // [1, 2, 3] — not affected

        // === Map.of() and Map.copyOf() ===
        Map<String, Integer> immutableMap = Map.of("a", 1, "b", 2, "c", 3);
        // immutableMap.put("d", 4);  // throws UnsupportedOperationException

        // === Set.of() ===
        Set<String> immutableSet = Set.of("alpha", "beta", "gamma");
    }
}
```

### Comparison Table

| Method | Truly Immutable? | Null elements? | Backed by original? |
|--------|-----------------|----------------|---------------------|
| `Collections.unmodifiableList(list)` | No (view only) | Yes | Yes — changes reflect |
| `List.of(...)` (Java 9+) | Yes | No — throws NPE | No |
| `List.copyOf(collection)` (Java 10+) | Yes | No — throws NPE | No |
| `new ArrayList<>(list)` | No (mutable copy) | Yes | No |

---

## 9. Records as Immutable (Java 14+)

```java
import java.util.List;

// Records are SHALLOW-immutable: fields are final, but mutable objects inside can change
public record PersonRecord(String name, int age, List<String> hobbies) {

    // Compact constructor for defensive copying
    public PersonRecord {
        // Validate
        if (age < 0) throw new IllegalArgumentException("Age cannot be negative");
        // Defensive copy — make the record truly immutable
        hobbies = List.copyOf(hobbies); // immutable copy
    }

    // Records auto-generate: constructor, getters (name(), age(), hobbies()),
    //                         equals(), hashCode(), toString()
}

// Usage:
// List<String> list = new ArrayList<>(List.of("A", "B"));
// PersonRecord p = new PersonRecord("Alice", 25, list);
// list.add("C");           // doesn't affect p
// p.hobbies().add("D");    // throws UnsupportedOperationException
//
// WARNING: Without compact constructor, records are shallow-immutable:
// record BadRecord(List<String> items) {}
// BadRecord r = new BadRecord(someList);
// r.items().add("hacked!"); // THIS WORKS — bad!
```

### When Records Are NOT Enough

```java
// Records can't:
// - Extend another class (implicitly extend java.lang.Record)
// - Have mutable state (all fields are final)
// - Have additional instance fields beyond components
//
// Records CAN:
// - Implement interfaces
// - Have static fields and methods
// - Override generated methods (equals, hashCode, toString)
// - Have additional instance methods
// - Have compact constructors for validation/defensive copying

public record Money(double amount, String currency) implements Comparable<Money> {
    public Money {
        if (amount < 0) throw new IllegalArgumentException("Amount cannot be negative");
        currency = currency.toUpperCase();
    }

    public Money add(Money other) {
        if (!this.currency.equals(other.currency))
            throw new IllegalArgumentException("Currency mismatch");
        return new Money(this.amount + other.amount, this.currency);
    }

    @Override
    public int compareTo(Money other) {
        return Double.compare(this.amount, other.amount);
    }
}
```

---

## 10. Builder Pattern for Immutable Objects

```java
import java.util.List;
import java.util.ArrayList;
import java.util.Collections;

public final class ImmutableConfig {
    private final String host;
    private final int port;
    private final boolean ssl;
    private final int timeout;
    private final List<String> allowedOrigins;

    private ImmutableConfig(Builder builder) {
        this.host = builder.host;
        this.port = builder.port;
        this.ssl = builder.ssl;
        this.timeout = builder.timeout;
        this.allowedOrigins = Collections.unmodifiableList(new ArrayList<>(builder.allowedOrigins));
    }

    public String getHost() { return host; }
    public int getPort() { return port; }
    public boolean isSsl() { return ssl; }
    public int getTimeout() { return timeout; }
    public List<String> getAllowedOrigins() { return allowedOrigins; }

    public static class Builder {
        private String host = "localhost";
        private int port = 8080;
        private boolean ssl = false;
        private int timeout = 30000;
        private List<String> allowedOrigins = new ArrayList<>();

        public Builder host(String host) { this.host = host; return this; }
        public Builder port(int port) { this.port = port; return this; }
        public Builder ssl(boolean ssl) { this.ssl = ssl; return this; }
        public Builder timeout(int timeout) { this.timeout = timeout; return this; }
        public Builder addOrigin(String origin) { this.allowedOrigins.add(origin); return this; }

        public ImmutableConfig build() {
            // Validation before creating immutable object
            if (port < 0 || port > 65535) throw new IllegalArgumentException("Invalid port");
            return new ImmutableConfig(this);
        }
    }

    @Override
    public String toString() {
        return "ImmutableConfig{host='" + host + "', port=" + port +
               ", ssl=" + ssl + ", timeout=" + timeout +
               ", origins=" + allowedOrigins + "}";
    }

    public static void main(String[] args) {
        ImmutableConfig config = new ImmutableConfig.Builder()
            .host("api.example.com")
            .port(443)
            .ssl(true)
            .timeout(5000)
            .addOrigin("https://app.example.com")
            .addOrigin("https://admin.example.com")
            .build();

        System.out.println(config);
        // config.getAllowedOrigins().add("hacker.com"); // UnsupportedOperationException
    }
}
```

---

## 11. Immutable Class with Map Field

```java
import java.util.*;

public final class ImmutableMetadata {
    private final String id;
    private final Map<String, String> properties;

    public ImmutableMetadata(String id, Map<String, String> properties) {
        this.id = Objects.requireNonNull(id);
        // Defensive copy of the map
        this.properties = new HashMap<>(properties);
    }

    public String getId() { return id; }

    public Map<String, String> getProperties() {
        // Return unmodifiable view
        return Collections.unmodifiableMap(properties);
    }

    public String getProperty(String key) {
        return properties.get(key);
    }

    // "Wither" method — returns new instance with modification
    public ImmutableMetadata withProperty(String key, String value) {
        Map<String, String> newProps = new HashMap<>(this.properties);
        newProps.put(key, value);
        return new ImmutableMetadata(this.id, newProps);
    }

    public ImmutableMetadata withoutProperty(String key) {
        Map<String, String> newProps = new HashMap<>(this.properties);
        newProps.remove(key);
        return new ImmutableMetadata(this.id, newProps);
    }
}

// Usage:
// Map<String, String> props = new HashMap<>(Map.of("env", "prod", "version", "1.0"));
// ImmutableMetadata meta = new ImmutableMetadata("config-1", props);
// props.put("hacked", "true");                  // doesn't affect meta
// meta.getProperties().put("hacked", "true");   // throws UnsupportedOperationException
//
// ImmutableMetadata updated = meta.withProperty("region", "us-east-1"); // new object
// System.out.println(meta.getProperty("region"));    // null (original unchanged)
// System.out.println(updated.getProperty("region")); // "us-east-1"
```

---

## 12. Immutability in Multi-threaded Context

```java
import java.util.concurrent.*;

public final class ImmutableAccount {
    private final String accountId;
    private final double balance;
    private final long version;

    public ImmutableAccount(String accountId, double balance, long version) {
        this.accountId = accountId;
        this.balance = balance;
        this.version = version;
    }

    public String getAccountId() { return accountId; }
    public double getBalance() { return balance; }
    public long getVersion() { return version; }

    // Returns NEW account — original is unchanged
    public ImmutableAccount credit(double amount) {
        return new ImmutableAccount(accountId, balance + amount, version + 1);
    }

    public ImmutableAccount debit(double amount) {
        if (amount > balance) throw new IllegalArgumentException("Insufficient funds");
        return new ImmutableAccount(accountId, balance - amount, version + 1);
    }
}

// Thread-safe usage with AtomicReference (lock-free CAS)
class AccountService {
    private final AtomicReference<ImmutableAccount> accountRef;

    public AccountService(ImmutableAccount initial) {
        this.accountRef = new AtomicReference<>(initial);
    }

    public ImmutableAccount credit(double amount) {
        while (true) {
            ImmutableAccount current = accountRef.get();
            ImmutableAccount updated = current.credit(amount);
            if (accountRef.compareAndSet(current, updated)) {
                return updated; // successful CAS
            }
            // CAS failed — another thread modified, retry
        }
    }

    public ImmutableAccount debit(double amount) {
        while (true) {
            ImmutableAccount current = accountRef.get();
            ImmutableAccount updated = current.debit(amount);
            if (accountRef.compareAndSet(current, updated)) {
                return updated;
            }
        }
    }

    public ImmutableAccount getAccount() {
        return accountRef.get(); // safe — account is immutable
    }
}
```

---

## 13. Common Pitfalls

### Pitfall 1: Array Fields

```java
// Arrays are ALWAYS mutable — even if the reference is final
public final class BrokenWithArray {
    private final int[] scores;

    public BrokenWithArray(int[] scores) {
        this.scores = scores; // BUG: holds reference to external array
    }

    public int[] getScores() {
        return scores; // BUG: caller can modify internal array
    }
}

// FIX:
public final class ImmutableWithArray {
    private final int[] scores;

    public ImmutableWithArray(int[] scores) {
        this.scores = scores.clone(); // defensive copy
    }

    public int[] getScores() {
        return scores.clone(); // return copy
    }

    public int getScore(int index) {
        return scores[index]; // safe — returns primitive
    }

    public int length() {
        return scores.length;
    }
}
```

### Pitfall 2: Subclassing Breaks Immutability

```java
// If class is NOT final, subclass can add mutable state:
public class AlmostImmutable {  // NOT FINAL — BUG
    private final String value;
    public AlmostImmutable(String value) { this.value = value; }
    public String getValue() { return value; }
}

class MutableSubclass extends AlmostImmutable {
    private String mutableField;
    public MutableSubclass(String value) { super(value); }
    public void setMutableField(String s) { this.mutableField = s; }
}

// Now AlmostImmutable variable can hold a MutableSubclass — not truly immutable
// FIX: Always make immutable classes final
```

### Pitfall 3: Reflection Can Break Immutability

```java
import java.lang.reflect.Field;

// Even "truly immutable" classes can be broken via reflection:
// ImmutablePoint point = new ImmutablePoint(10, 20);
// Field xField = ImmutablePoint.class.getDeclaredField("x");
// xField.setAccessible(true);
// xField.setInt(point, 999); // WORKS in Java 8-16, restricted in Java 17+

// Java 17+ with strong encapsulation: --illegal-access=deny (default)
// Module system protects against casual reflection attacks
// For security-critical code, use SecurityManager (deprecated in 17, removed in future)
```

---

## 14. Interview Questions

**Q: Why is String immutable in Java?**
```
1. String Pool: JVM caches strings in a pool. If "hello" is shared by 10 references,
   mutating it through one would corrupt all others.
2. Security: Strings are used for class loading, network connections, file paths.
   Immutability prevents TOCTOU (time-of-check-to-time-of-use) attacks.
3. Thread-safety: Strings can be shared across threads without synchronization.
4. Hashcode caching: String caches its hashCode (lazy-computed once). Works because
   the value never changes. Critical for HashMap performance.
5. Class loading: Class names are strings. Mutable class names would be a security nightmare.
```

**Q: Can you make a class immutable if it has a mutable field like Date?**
```
Yes — use defensive copying:
- In constructor: this.date = new Date(date.getTime());
- In getter: return new Date(this.date.getTime());
The internal state is never exposed. Callers get copies they can mutate freely.
```

**Q: What's the difference between `final` and immutable?**
```
- final variable: the reference cannot be reassigned, but the object it points to CAN be mutated
  final List<String> list = new ArrayList<>();
  list.add("hello");  // ALLOWED — mutating the object
  list = new ArrayList<>();  // COMPILE ERROR — reassigning reference

- immutable object: the object's state cannot change after construction
  String s = "hello";
  s.toUpperCase();  // returns NEW string, doesn't modify s

- A final reference to a mutable object is NOT immutable:
  final Date d = new Date();
  d.setTime(0);  // ALLOWED — Date is mutable, final only prevents reassignment
```

**Q: How do you handle Collections in immutable classes?**
```
1. Defensive copy in constructor: this.list = new ArrayList<>(list);
2. In getter, return: Collections.unmodifiableList(this.list)
   OR return new ArrayList<>(this.list)
3. Even better (Java 10+): this.list = List.copyOf(list) — already immutable

Never store or return the same reference the caller has access to.
```

**Q: Are Records truly immutable?**
```
Records are SHALLOW-immutable by default:
- All fields are final (can't reassign)
- BUT if a field is a mutable object (like List), it can still be mutated

To make a Record truly immutable, use a compact constructor:
  public record Person(String name, List<String> hobbies) {
      public Person { hobbies = List.copyOf(hobbies); }
  }
```

**Q: How does immutability help with thread-safety?**
```
- Immutable objects have no mutable shared state
- No synchronization, no locks, no race conditions
- Can be freely published and shared between threads
- Combined with AtomicReference, enables lock-free algorithms (CAS)
- Example: java.time API (LocalDate, Instant) vs old Date/Calendar
```

---

## 15. Immutability Checklist for LLD Interviews

```
When designing a class in an LLD interview, ask yourself:

□ Does this class NEED to be mutable?
□ If not → make it immutable (thread-safe for free, safer as HashMap keys)
□ Declare class as final
□ All fields private final
□ Constructor validates and defensively copies mutable inputs
□ Getters return unmodifiable views or defensive copies
□ "Modification" methods return new instances (withX pattern)
□ Consider Builder for classes with many fields
□ Consider Records for simple value objects (Java 14+)

Common LLD classes that SHOULD be immutable:
- Money / Currency
- Address / Location / Coordinates
- Configuration / Settings
- Event payloads / Messages
- Value Objects in DDD (Domain-Driven Design)
```

---
