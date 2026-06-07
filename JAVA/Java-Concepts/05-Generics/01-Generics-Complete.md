# Java Generics - Complete Guide

## 1. Why Generics?

### Problems Before Generics (Java < 5)

```java
// Without Generics - NO type safety
List list = new ArrayList();
list.add("Hello");
list.add(42);  // No compile error!

String s = (String) list.get(0);  // Manual casting required
String s2 = (String) list.get(1); // ClassCastException at RUNTIME!
```

### Benefits of Generics

```java
// With Generics - Type safety at compile time
List<String> list = new ArrayList<>();
list.add("Hello");
// list.add(42);  // COMPILE ERROR! Type safety enforced

String s = list.get(0);  // No casting needed
```

**Three key benefits:**
1. **Type Safety** - Errors caught at compile time, not runtime
2. **Elimination of Casts** - No more explicit casting
3. **Code Reusability** - Write once, use with any type

---

## 2. Generic Classes

### Single Type Parameter

```java
public class Box<T> {
    private T content;

    public Box(T content) {
        this.content = content;
    }

    public T getContent() {
        return content;
    }

    public void setContent(T content) {
        this.content = content;
    }
}

// Usage
Box<String> stringBox = new Box<>("Hello");
String value = stringBox.getContent();  // No cast

Box<Integer> intBox = new Box<>(42);
int num = intBox.getContent();  // Auto-unboxing
```

### Multiple Type Parameters

```java
public class Pair<K, V> {
    private K key;
    private V value;

    public Pair(K key, V value) {
        this.key = key;
        this.value = value;
    }

    public K getKey() { return key; }
    public V getValue() { return value; }
}

// Triple with three type parameters
public class Triple<A, B, C> {
    private final A first;
    private final B second;
    private final C third;

    public Triple(A first, B second, C third) {
        this.first = first;
        this.second = second;
        this.third = third;
    }

    public A getFirst() { return first; }
    public B getSecond() { return second; }
    public C getThird() { return third; }
}

// Usage
Pair<String, Integer> entry = new Pair<>("age", 25);
Triple<String, Integer, Boolean> result = new Triple<>("test", 1, true);
```

### Naming Conventions

| Parameter | Convention |
|-----------|-----------|
| `T` | Type (general purpose) |
| `E` | Element (collections) |
| `K` | Key |
| `V` | Value |
| `N` | Number |
| `S, U, V` | 2nd, 3rd, 4th types |
| `R` | Return type |

---

## 3. Generic Methods

### Static Generic Methods

```java
public class GenericUtils {

    // Generic method - type parameter declared BEFORE return type
    public static <T> T getFirst(List<T> list) {
        if (list == null || list.isEmpty()) {
            return null;
        }
        return list.get(0);
    }

    // Multiple type parameters in method
    public static <K, V> Map<V, K> invertMap(Map<K, V> original) {
        Map<V, K> inverted = new HashMap<>();
        for (Map.Entry<K, V> entry : original.entrySet()) {
            inverted.put(entry.getValue(), entry.getKey());
        }
        return inverted;
    }

    // Generic method with bounded type
    public static <T extends Comparable<T>> T max(T a, T b) {
        return a.compareTo(b) >= 0 ? a : b;
    }

    // Generic method returning different type
    public static <T, R> List<R> transform(List<T> input, Function<T, R> mapper) {
        List<R> result = new ArrayList<>();
        for (T item : input) {
            result.add(mapper.apply(item));
        }
        return result;
    }
}
```

### Type Inference in Method Calls

```java
// Explicit type specification (rarely needed)
String first = GenericUtils.<String>getFirst(stringList);

// Type inference - compiler figures out T = String
String first = GenericUtils.getFirst(stringList);  // Preferred

// Type inference with diamond operator
List<String> list = new ArrayList<>();  // Diamond infers String

// Complex inference
Map<Integer, String> inverted = GenericUtils.invertMap(nameMap);
```

### Generic Constructors

```java
public class Container<T> {
    private T value;

    // Generic constructor - has its own type parameter separate from class
    public <U> Container(U input, Function<U, T> converter) {
        this.value = converter.apply(input);
    }

    // Regular constructor using class type parameter
    public Container(T value) {
        this.value = value;
    }

    public T getValue() { return value; }
}

// Usage
Container<Integer> c = new Container<>("123", Integer::parseInt);
// Constructor's U = String, Class's T = Integer
```

---

## 4. Bounded Type Parameters

### Upper Bounded Type Parameters

```java
// T MUST be Number or a subclass of Number
public class NumberBox<T extends Number> {
    private T value;

    public NumberBox(T value) {
        this.value = value;
    }

    // Can call Number methods on T
    public double doubleValue() {
        return value.doubleValue();
    }

    public boolean isPositive() {
        return value.doubleValue() > 0;
    }
}

// Usage
NumberBox<Integer> intBox = new NumberBox<>(42);      // OK
NumberBox<Double> doubleBox = new NumberBox<>(3.14);  // OK
// NumberBox<String> strBox = new NumberBox<>("hi"); // COMPILE ERROR!

// Generic method with upper bound
public static <T extends Number> double sum(List<T> numbers) {
    double total = 0;
    for (T num : numbers) {
        total += num.doubleValue();  // Can call Number methods
    }
    return total;
}
```

### Multiple Bounds

```java
// T must extend Number AND implement Comparable AND Serializable
// Class must come FIRST, then interfaces
public class SortableNumber<T extends Number & Comparable<T> & Serializable> {
    private T value;

    public SortableNumber(T value) {
        this.value = value;
    }

    public int compareTo(SortableNumber<T> other) {
        return this.value.compareTo(other.value);  // From Comparable
    }

    public double toDouble() {
        return this.value.doubleValue();  // From Number
    }
}

// RULES for multiple bounds:
// 1. At most ONE class bound (must be listed first)
// 2. Multiple interface bounds allowed
// <T extends ClassA & InterfaceB & InterfaceC>  ✓
// <T extends InterfaceA & ClassB>                ✗ (class not first)
// <T extends ClassA & ClassB>                    ✗ (two classes)
```

### Why `extends` (Not `implements`) for Interface Bounds

```java
// In bounds, ALWAYS use "extends" - even for interfaces
// This is a design choice in Java generics syntax

<T extends Comparable<T>>       // ✓ Correct (even though Comparable is interface)
// <T implements Comparable<T>> // ✗ Does NOT exist in Java syntax

// Rationale: "extends" in bounds means "is a subtype of"
// It encompasses both class inheritance and interface implementation
```

---

## 5. Wildcards

### Unbounded Wildcard: `<?>`

```java
// ? means "unknown type" - use when you don't care about the type
public static void printList(List<?> list) {
    for (Object item : list) {
        System.out.println(item);  // Can only treat as Object
    }
}

// Can call with ANY List
printList(Arrays.asList(1, 2, 3));
printList(Arrays.asList("a", "b", "c"));

// CANNOT add to List<?> (except null)
public static void cannotAdd(List<?> list) {
    // list.add("hello");  // COMPILE ERROR - type unknown
    // list.add(42);       // COMPILE ERROR
    list.add(null);        // OK - null is valid for any reference type
}

// When to use List<?> vs List<Object>:
// List<?>      - read-only, accepts List<String>, List<Integer>, etc.
// List<Object> - read-write, but ONLY accepts List<Object> (not List<String>!)
```

### Upper Bounded Wildcard: `<? extends T>` (PRODUCER - Read Only)

```java
// "? extends Number" means: Number or any SUBTYPE of Number
// USE FOR: Reading from a collection (the collection PRODUCES values)

public static double sumAll(List<? extends Number> numbers) {
    double sum = 0;
    for (Number n : numbers) {  // Safe to read as Number
        sum += n.doubleValue();
    }
    // numbers.add(42);     // COMPILE ERROR! Cannot write
    // numbers.add(3.14);   // COMPILE ERROR! Cannot write
    return sum;
}

// Why can't we write?
// If list is actually List<Integer>, adding a Double would corrupt it
// Compiler prevents this by disallowing writes

// Accepts all these:
sumAll(Arrays.asList(1, 2, 3));           // List<Integer>
sumAll(Arrays.asList(1.0, 2.0, 3.0));    // List<Double>
sumAll(Arrays.asList(1L, 2L, 3L));       // List<Long>
```

### Lower Bounded Wildcard: `<? super T>` (CONSUMER - Write Only)

```java
// "? super Integer" means: Integer or any SUPERTYPE of Integer
// USE FOR: Writing to a collection (the collection CONSUMES values)

public static void addNumbers(List<? super Integer> list) {
    list.add(1);    // Safe to write Integer
    list.add(2);
    list.add(3);

    // Reading is restricted - can only get Object
    Object obj = list.get(0);  // Only guaranteed to be Object
    // Integer i = list.get(0); // COMPILE ERROR - might be List<Number>
}

// Why can't we read as Integer?
// If list is actually List<Number>, it might contain Doubles
// Only safe to read as Object

// Accepts:
addNumbers(new ArrayList<Integer>());  // List<Integer> - Integer super Integer
addNumbers(new ArrayList<Number>());   // List<Number>  - Number super Integer
addNumbers(new ArrayList<Object>());   // List<Object>  - Object super Integer
```

### PECS Principle (Producer Extends, Consumer Super)

```java
/**
 * PECS: Producer Extends, Consumer Super
 *
 * If you only READ from a structure   → use <? extends T> (Producer)
 * If you only WRITE to a structure    → use <? super T>   (Consumer)
 * If you both READ and WRITE          → use exact type <T> (no wildcard)
 */

// COMPLETE EXAMPLE: Copy elements from source to destination
public static <T> void copy(
        List<? extends T> source,  // PRODUCER: we read FROM source
        List<? super T> dest       // CONSUMER: we write TO dest
) {
    for (T item : source) {
        dest.add(item);
    }
}

// Usage
List<Integer> integers = Arrays.asList(1, 2, 3);
List<Number> numbers = new ArrayList<>();
copy(integers, numbers);  // T=Integer, source produces Integers, dest consumes Integers

// Real-world example from Collections.java:
public static <T> void sort(List<T> list, Comparator<? super T> comparator) {
    // Comparator CONSUMES T values (takes them as input to compare)
    // So we use ? super T
}

// This allows:
List<Integer> list = Arrays.asList(3, 1, 2);
Comparator<Number> numComparator = (a, b) -> Double.compare(a.doubleValue(), b.doubleValue());
Collections.sort(list, numComparator);  // Comparator<Number> works for Integer!

// ANOTHER EXAMPLE: Stack with flexible push/pop
public class Stack<E> {
    private List<E> elements = new ArrayList<>();

    public void push(E item) { elements.add(item); }
    public E pop() { return elements.remove(elements.size() - 1); }

    // Push all from a PRODUCER (read from src)
    public void pushAll(Iterable<? extends E> source) {
        for (E item : source) {
            push(item);
        }
    }

    // Pop all into a CONSUMER (write to dst)
    public void popAll(Collection<? super E> destination) {
        while (!elements.isEmpty()) {
            destination.add(pop());
        }
    }
}

// Usage
Stack<Number> numberStack = new Stack<>();
List<Integer> integers = Arrays.asList(1, 2, 3);
numberStack.pushAll(integers);  // Integer extends Number ✓

List<Object> objects = new ArrayList<>();
numberStack.popAll(objects);    // Object super Number ✓
```

### Wildcard Capture

```java
// Wildcard capture - the compiler internally assigns a name to ?
public static void swap(List<?> list, int i, int j) {
    // Cannot directly work with ? - need helper method
    swapHelper(list, i, j);
}

// Helper "captures" the wildcard into a named type parameter
private static <T> void swapHelper(List<T> list, int i, int j) {
    T temp = list.get(i);
    list.set(i, list.get(j));
    list.set(j, temp);
}

// Why is this needed?
// With List<?>, the compiler doesn't know the type
// By calling a generic method, the compiler "captures" ? as a concrete T
// This is called "wildcard capture" or "capture conversion"
```

### Summary Table

| Wildcard | Read | Write | Use Case |
|----------|------|-------|----------|
| `<?>` | As Object | Nothing (except null) | Don't care about type |
| `<? extends T>` | As T | Nothing | Producer (read) |
| `<? super T>` | As Object | T and subtypes | Consumer (write) |
| `<T>` (exact) | As T | T | Both read and write |

---

## 6. Type Erasure

### How Generics Work at Runtime

```java
// COMPILE TIME (what you write):
public class Box<T> {
    private T value;
    public T get() { return value; }
    public void set(T value) { this.value = value; }
}

// AFTER ERASURE (what JVM sees) - T erased to Object:
public class Box {
    private Object value;
    public Object get() { return value; }
    public void set(Object value) { this.value = value; }
}

// For bounded types, erasure is to the bound:
public class NumberBox<T extends Number> {
    private T value;  // Erased to: private Number value;
}

// Multiple bounds - erased to FIRST bound:
public class SortBox<T extends Comparable<T> & Serializable> {
    private T value;  // Erased to: private Comparable value;
}
```

### Bridge Methods

```java
// Bridge methods are generated by compiler to maintain polymorphism

public interface Comparable<T> {
    int compareTo(T other);
}

public class IntWrapper implements Comparable<IntWrapper> {
    private int value;

    @Override
    public int compareTo(IntWrapper other) {  // Type-specific
        return Integer.compare(this.value, other.value);
    }
}

// After erasure, JVM sees:
// Interface: int compareTo(Object other)
// Class:     int compareTo(IntWrapper other)  <-- different signature!

// Compiler generates a BRIDGE METHOD:
public class IntWrapper implements Comparable {
    public int compareTo(IntWrapper other) { ... }  // Your code

    // BRIDGE METHOD (synthetic, generated by compiler)
    public int compareTo(Object other) {
        return compareTo((IntWrapper) other);  // Delegates with cast
    }
}

// You can see bridge methods via reflection:
for (Method m : IntWrapper.class.getDeclaredMethods()) {
    if (m.isBridge()) {
        System.out.println("Bridge: " + m);
    }
}
```

### Limitations Due to Type Erasure

```java
// 1. CANNOT create generic arrays
// T[] arr = new T[10];  // COMPILE ERROR
// Why? JVM doesn't know T at runtime, can't allocate correct type

// Workaround:
@SuppressWarnings("unchecked")
T[] arr = (T[]) new Object[10];
// Or better:
T[] arr = (T[]) Array.newInstance(clazz, 10);

// 2. CANNOT use instanceof with parameterized types
// if (obj instanceof List<String>) {}  // COMPILE ERROR
// Why? At runtime, List<String> and List<Integer> are both just List

// Workaround - check raw type only:
if (obj instanceof List<?>) {
    List<?> list = (List<?>) obj;
}

// 3. CANNOT create instances of type parameter
// T obj = new T();  // COMPILE ERROR
// Why? JVM doesn't know what constructor to call

// Workaround - pass Class<T> or Supplier<T>:
public class Factory<T> {
    private final Supplier<T> constructor;

    public Factory(Supplier<T> constructor) {
        this.constructor = constructor;
    }

    public T create() {
        return constructor.get();
    }
}
Factory<ArrayList<String>> factory = new Factory<>(ArrayList::new);

// 4. CANNOT create generic exception classes
// class MyException<T> extends Exception {}  // COMPILE ERROR
// Why? catch clauses need exact types at runtime

// 5. CANNOT overload methods that erase to same signature
public class Example {
    // public void process(List<String> list) {}  // After erasure: process(List)
    // public void process(List<Integer> list) {} // After erasure: process(List)
    // COMPILE ERROR: both erase to same signature!
}

// 6. CANNOT use primitives as type arguments
// List<int> list = new ArrayList<>();  // COMPILE ERROR
List<Integer> list = new ArrayList<>();  // Must use wrapper
```

### Reifiable vs Non-Reifiable Types

```java
/**
 * REIFIABLE TYPE: Full type info available at runtime
 * - Primitives: int, double, etc.
 * - Non-generic types: String, Integer
 * - Raw types: List, Map
 * - Unbounded wildcards: List<?>, Map<?, ?>
 * - Arrays of reifiable types: String[], int[]
 *
 * NON-REIFIABLE TYPE: Type info partially erased at runtime
 * - Parameterized types: List<String>, Map<String, Integer>
 * - Bounded wildcards: List<? extends Number>
 * - Type parameters: T
 */

// This is why varargs with generics gives warnings:
@SafeVarargs  // Suppress the warning
public static <T> List<T> asList(T... elements) {
    // T[] is non-reifiable - potential heap pollution
    List<T> list = new ArrayList<>();
    for (T e : elements) {
        list.add(e);
    }
    return list;
}

// Heap pollution example:
List<String> strings = new ArrayList<>();
List rawList = strings;        // Raw type - no generics check
rawList.add(42);               // Heap pollution! Integer in List<String>
String s = strings.get(0);     // ClassCastException at runtime!
```

---

## 7. Generic Interfaces

### Comparable<T>

```java
// Natural ordering for objects
public class Employee implements Comparable<Employee> {
    private String name;
    private int salary;

    @Override
    public int compareTo(Employee other) {
        return Integer.compare(this.salary, other.salary);
    }
}

// Usage
List<Employee> employees = new ArrayList<>();
Collections.sort(employees);  // Uses compareTo
```

### Comparator<T>

```java
// Custom ordering (external to the class)
public class EmployeeComparators {

    public static final Comparator<Employee> BY_NAME =
        Comparator.comparing(Employee::getName);

    public static final Comparator<Employee> BY_SALARY =
        Comparator.comparingInt(Employee::getSalary);

    public static final Comparator<Employee> BY_NAME_THEN_SALARY =
        BY_NAME.thenComparingInt(Employee::getSalary);

    // Reverse order
    public static final Comparator<Employee> BY_SALARY_DESC =
        BY_SALARY.reversed();
}

// Usage
employees.sort(EmployeeComparators.BY_SALARY);
employees.sort(Comparator.comparing(Employee::getName).reversed());
```

### Iterable<T> and Iterator<T>

```java
// Making a custom class iterable
public class NumberRange implements Iterable<Integer> {
    private final int start;
    private final int end;

    public NumberRange(int start, int end) {
        this.start = start;
        this.end = end;
    }

    @Override
    public Iterator<Integer> iterator() {
        return new Iterator<Integer>() {
            private int current = start;

            @Override
            public boolean hasNext() {
                return current <= end;
            }

            @Override
            public Integer next() {
                if (!hasNext()) throw new NoSuchElementException();
                return current++;
            }
        };
    }
}

// Usage with for-each
NumberRange range = new NumberRange(1, 10);
for (int num : range) {
    System.out.println(num);
}
```

### Custom Generic Interface

```java
// Generic Repository interface
public interface Repository<T, ID> {
    T findById(ID id);
    List<T> findAll();
    T save(T entity);
    void delete(ID id);
    boolean existsById(ID id);
}

// Generic Mapper interface
public interface Mapper<S, D> {
    D map(S source);
    S reverseMap(D destination);

    default List<D> mapAll(List<S> sources) {
        return sources.stream()
                .map(this::map)
                .collect(Collectors.toList());
    }
}
```

---

## 8. Recursive Type Bounds

```java
// Pattern: <T extends Comparable<T>>
// "T is a type that can compare itself with other T's"

public static <T extends Comparable<T>> T findMax(List<T> list) {
    if (list.isEmpty()) throw new IllegalArgumentException("Empty list");
    T max = list.get(0);
    for (T item : list) {
        if (item.compareTo(max) > 0) {
            max = item;
        }
    }
    return max;
}

// Self-referential generic (Builder pattern, fluent APIs)
public abstract class Builder<T extends Builder<T>> {
    // T refers to the CONCRETE subclass

    protected abstract T self();  // Returns this, but typed as T

    public T withName(String name) {
        // ... set name
        return self();
    }
}

public class UserBuilder extends Builder<UserBuilder> {
    @Override
    protected UserBuilder self() {
        return this;
    }

    public UserBuilder withEmail(String email) {
        // ... set email
        return self();
    }
}

// Method chaining works correctly:
User user = new UserBuilder()
    .withName("Alice")     // Returns UserBuilder (not Builder)
    .withEmail("a@b.com")  // Works! Because withName returned UserBuilder
    .build();

// Enum's recursive bound:
// public abstract class Enum<E extends Enum<E>> implements Comparable<E>
// Every enum like Color implicitly extends Enum<Color>

// Another example: Self-comparable node
public class TreeNode<T extends Comparable<T>> {
    private T value;
    private TreeNode<T> left, right;

    public void insert(T newValue) {
        if (newValue.compareTo(this.value) < 0) {
            if (left == null) left = new TreeNode<>(newValue);
            else left.insert(newValue);
        } else {
            if (right == null) right = new TreeNode<>(newValue);
            else right.insert(newValue);
        }
    }
}
```

---

## 9. Practical Examples for LLD

### Generic Repository Pattern

```java
// Base Entity
public abstract class BaseEntity {
    private String id;
    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;

    public String getId() { return id; }
    public void setId(String id) { this.id = id; }
    public LocalDateTime getCreatedAt() { return createdAt; }
    public LocalDateTime getUpdatedAt() { return updatedAt; }
}

// Generic Repository Interface
public interface Repository<T extends BaseEntity> {
    T findById(String id);
    List<T> findAll();
    List<T> findByPredicate(Predicate<T> predicate);
    T save(T entity);
    T update(T entity);
    void delete(String id);
    boolean exists(String id);
    long count();
}

// In-Memory Generic Implementation
public class InMemoryRepository<T extends BaseEntity> implements Repository<T> {
    private final Map<String, T> store = new ConcurrentHashMap<>();
    private final AtomicLong idGenerator = new AtomicLong(1);

    @Override
    public T findById(String id) {
        T entity = store.get(id);
        if (entity == null) {
            throw new EntityNotFoundException("Entity not found with id: " + id);
        }
        return entity;
    }

    @Override
    public List<T> findAll() {
        return new ArrayList<>(store.values());
    }

    @Override
    public List<T> findByPredicate(Predicate<T> predicate) {
        return store.values().stream()
                .filter(predicate)
                .collect(Collectors.toList());
    }

    @Override
    public T save(T entity) {
        if (entity.getId() == null) {
            entity.setId(String.valueOf(idGenerator.getAndIncrement()));
        }
        store.put(entity.getId(), entity);
        return entity;
    }

    @Override
    public T update(T entity) {
        if (!store.containsKey(entity.getId())) {
            throw new EntityNotFoundException("Cannot update: entity not found");
        }
        store.put(entity.getId(), entity);
        return entity;
    }

    @Override
    public void delete(String id) {
        if (store.remove(id) == null) {
            throw new EntityNotFoundException("Cannot delete: entity not found");
        }
    }

    @Override
    public boolean exists(String id) {
        return store.containsKey(id);
    }

    @Override
    public long count() {
        return store.size();
    }
}

// Concrete Usage
public class User extends BaseEntity {
    private String name;
    private String email;
    // getters, setters
}

public class Product extends BaseEntity {
    private String title;
    private double price;
    // getters, setters
}

// Create repositories - fully type-safe
Repository<User> userRepo = new InMemoryRepository<>();
Repository<Product> productRepo = new InMemoryRepository<>();

User user = new User();
user.setName("Alice");
userRepo.save(user);  // Returns User, not Object

List<User> activeUsers = userRepo.findByPredicate(u -> u.isActive());
```

### Generic Builder Pattern

```java
// Type-safe builder using generics and self-referential bounds
public abstract class AbstractBuilder<T, B extends AbstractBuilder<T, B>> {
    protected final Map<String, Object> properties = new HashMap<>();

    @SuppressWarnings("unchecked")
    protected B self() {
        return (B) this;
    }

    public abstract T build();
}

// Concrete builder for any entity
public class EntityBuilder<T> extends AbstractBuilder<T, EntityBuilder<T>> {
    private final Function<Map<String, Object>, T> constructor;

    public EntityBuilder(Function<Map<String, Object>, T> constructor) {
        this.constructor = constructor;
    }

    public EntityBuilder<T> with(String key, Object value) {
        properties.put(key, value);
        return self();
    }

    @Override
    public T build() {
        return constructor.apply(properties);
    }
}

// Step Builder Pattern with Generics (enforces build order)
public class OrderBuilder {

    public interface NeedsCustomer {
        NeedsProduct forCustomer(String customerId);
    }

    public interface NeedsProduct {
        NeedsQuantity withProduct(String productId);
    }

    public interface NeedsQuantity {
        CanBuild withQuantity(int quantity);
    }

    public interface CanBuild {
        CanBuild withDiscount(double discount);
        Order build();
    }

    public static NeedsCustomer create() {
        return new Steps();
    }

    private static class Steps implements NeedsCustomer, NeedsProduct,
                                          NeedsQuantity, CanBuild {
        private String customerId;
        private String productId;
        private int quantity;
        private double discount = 0;

        @Override
        public NeedsProduct forCustomer(String customerId) {
            this.customerId = customerId;
            return this;
        }

        @Override
        public NeedsQuantity withProduct(String productId) {
            this.productId = productId;
            return this;
        }

        @Override
        public CanBuild withQuantity(int quantity) {
            this.quantity = quantity;
            return this;
        }

        @Override
        public CanBuild withDiscount(double discount) {
            this.discount = discount;
            return this;
        }

        @Override
        public Order build() {
            return new Order(customerId, productId, quantity, discount);
        }
    }
}

// Usage - compile error if steps are out of order
Order order = OrderBuilder.create()
    .forCustomer("C001")
    .withProduct("P001")
    .withQuantity(5)
    .withDiscount(0.1)
    .build();
```

### Type-Safe Heterogeneous Container

```java
/**
 * A container that can hold values of DIFFERENT types
 * but remains completely type-safe.
 *
 * Key insight: Use Class<T> as a type-safe key (type token)
 * Each key knows its own type, so get() returns the correct type.
 */
public class TypeSafeContainer {
    private final Map<Class<?>, Object> store = new HashMap<>();

    // Type token ensures type safety
    public <T> void put(Class<T> type, T instance) {
        store.put(type, type.cast(instance));  // Runtime type check
    }

    public <T> T get(Class<T> type) {
        return type.cast(store.get(type));
    }

    public boolean contains(Class<?> type) {
        return store.containsKey(type);
    }
}

// Usage
TypeSafeContainer container = new TypeSafeContainer();
container.put(String.class, "Hello");
container.put(Integer.class, 42);
container.put(List.class, Arrays.asList(1, 2, 3));

String s = container.get(String.class);   // No cast! Returns String
Integer i = container.get(Integer.class); // No cast! Returns Integer

// Super type token for generic types (Guava TypeToken / Jackson TypeReference)
// Workaround for erasure with parameterized types
public abstract class TypeReference<T> {
    private final Type type;

    protected TypeReference() {
        Type superClass = getClass().getGenericSuperclass();
        this.type = ((ParameterizedType) superClass).getActualTypeArguments()[0];
    }

    public Type getType() { return type; }
}

// Usage - anonymous subclass captures generic type
TypeReference<List<String>> ref = new TypeReference<List<String>>() {};
// ref.getType() == List<String> - preserved at runtime!

// Complete example: Generic Event Bus
public class EventBus {
    private final Map<Class<?>, List<Consumer<?>>> handlers = new ConcurrentHashMap<>();

    public <T> void subscribe(Class<T> eventType, Consumer<T> handler) {
        handlers.computeIfAbsent(eventType, k -> new CopyOnWriteArrayList<>())
                .add(handler);
    }

    @SuppressWarnings("unchecked")
    public <T> void publish(T event) {
        List<Consumer<?>> eventHandlers = handlers.get(event.getClass());
        if (eventHandlers != null) {
            for (Consumer<?> handler : eventHandlers) {
                ((Consumer<T>) handler).accept(event);
            }
        }
    }
}

// Usage
EventBus bus = new EventBus();
bus.subscribe(OrderCreated.class, event -> {
    System.out.println("Order: " + event.getOrderId());
});
bus.publish(new OrderCreated("ORD-001"));
```

### Generic Strategy Pattern

```java
// Generic strategy interface
public interface Strategy<I, O> {
    O execute(I input);
}

// Generic strategy context
public class StrategyContext<I, O> {
    private final Map<String, Strategy<I, O>> strategies = new HashMap<>();
    private Strategy<I, O> defaultStrategy;

    public void register(String name, Strategy<I, O> strategy) {
        strategies.put(name, strategy);
    }

    public void setDefault(Strategy<I, O> strategy) {
        this.defaultStrategy = strategy;
    }

    public O execute(String strategyName, I input) {
        Strategy<I, O> strategy = strategies.getOrDefault(strategyName, defaultStrategy);
        if (strategy == null) {
            throw new IllegalStateException("No strategy found: " + strategyName);
        }
        return strategy.execute(input);
    }
}

// Usage: Pricing strategies
StrategyContext<Order, Double> pricingContext = new StrategyContext<>();
pricingContext.register("regular", order -> order.getTotal());
pricingContext.register("premium", order -> order.getTotal() * 0.9);
pricingContext.register("vip", order -> order.getTotal() * 0.8);

double finalPrice = pricingContext.execute("premium", order);
```

---

## Quick Reference: Common Patterns

```java
// 1. Factory Method with Generics
public static <T> List<T> emptyList()       { return new ArrayList<>(); }
public static <K, V> Map<K, V> emptyMap()   { return new HashMap<>(); }

// 2. Generic Singleton (type-safe)
public class EmptyIterator<T> implements Iterator<T> {
    @SuppressWarnings("rawtypes")
    private static final EmptyIterator INSTANCE = new EmptyIterator();

    @SuppressWarnings("unchecked")
    public static <T> EmptyIterator<T> instance() { return INSTANCE; }

    @Override public boolean hasNext() { return false; }
    @Override public T next() { throw new NoSuchElementException(); }
}

// 3. Bounded wildcard in return type (rare but useful)
public static <E extends Comparable<? super E>> E max(Collection<? extends E> c) {
    // Handles: max(List<Integer>) where Integer implements Comparable<Integer>
    // Also:    max(List<ScheduledFuture>) where ScheduledFuture extends
    //          Comparable<Delayed> (its supertype)
    Iterator<? extends E> iter = c.iterator();
    E result = iter.next();
    while (iter.hasNext()) {
        E next = iter.next();
        if (next.compareTo(result) > 0) result = next;
    }
    return result;
}

// 4. Generic method to create type-safe immutable pair
public static <A, B> Pair<A, B> of(A first, B second) {
    return new Pair<>(first, second);
}
```
