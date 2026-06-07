# Inner Classes, Static Members, Enums, Records, and Sealed Classes

## 1. Static Members

### Static Variables (Class-Level, Shared State)

```java
public class DatabaseConnectionPool {
    // ═══════════════════════════════════════════════════════
    // STATIC VARIABLES - belong to the CLASS, not any instance
    // Shared across ALL instances, stored in Method Area (Metaspace)
    // ═══════════════════════════════════════════════════════

    // Static constant - compile-time constant, inlined by compiler
    private static final int MAX_CONNECTIONS = 10;

    // Static variable - shared mutable state (thread-safety concern!)
    private static int activeConnections = 0;

    // Static reference - single instance shared by all
    private static final List<Connection> pool = new ArrayList<>();

    // Instance variable - each pool tracker has its own
    private final String poolName;

    public DatabaseConnectionPool(String name) {
        this.poolName = name;
    }

    public static int getActiveConnections() {
        return activeConnections;
    }

    public synchronized Connection acquire() {
        if (activeConnections >= MAX_CONNECTIONS) {
            throw new IllegalStateException("Pool exhausted");
        }
        activeConnections++;
        System.out.println(poolName + ": Connection acquired. Active: " + activeConnections);
        return new Connection();
    }

    public synchronized void release(Connection conn) {
        activeConnections--;
        System.out.println(poolName + ": Connection released. Active: " + activeConnections);
    }

    // Nested placeholder
    static class Connection {
        private final String id = UUID.randomUUID().toString().substring(0, 8);
        @Override public String toString() { return "Conn-" + id; }
    }
}

class StaticVariableDemo {
    public static void main(String[] args) {
        // Static variable is shared - both pools affect the SAME counter
        DatabaseConnectionPool pool1 = new DatabaseConnectionPool("Pool-A");
        DatabaseConnectionPool pool2 = new DatabaseConnectionPool("Pool-B");

        var conn1 = pool1.acquire();  // Active: 1
        var conn2 = pool2.acquire();  // Active: 2 (SHARED counter!)

        // Access static via class name (preferred) or instance (discouraged)
        System.out.println("Total active: " + DatabaseConnectionPool.getActiveConnections());  // 2

        pool1.release(conn1);  // Active: 1
    }
}
```

### Static Methods (No `this` Reference)

```java
public class MathUtils {
    // ═══════════════════════════════════════════════════════
    // STATIC METHODS
    // - No 'this' reference (no instance context)
    // - Cannot access instance variables/methods
    // - CAN access other static members
    // - Called via ClassName.method() - no object needed
    // - Cannot be overridden (they are HIDDEN, not polymorphic)
    // ═══════════════════════════════════════════════════════

    // Private constructor - prevent instantiation of utility class
    private MathUtils() {
        throw new AssertionError("Cannot instantiate utility class");
    }

    public static int factorial(int n) {
        if (n < 0) throw new IllegalArgumentException("n must be >= 0");
        if (n <= 1) return 1;
        return n * factorial(n - 1);
    }

    public static boolean isPrime(int n) {
        if (n < 2) return false;
        if (n == 2) return true;
        if (n % 2 == 0) return false;
        for (int i = 3; i <= Math.sqrt(n); i += 2) {
            if (n % i == 0) return false;
        }
        return true;
    }

    public static double clamp(double value, double min, double max) {
        return Math.max(min, Math.min(max, value));
    }

    // Static factory method pattern (alternative to constructors)
    public static MathUtils getInstance() {
        // This is a common pattern but for utility classes,
        // prefer private constructor + static methods
        throw new UnsupportedOperationException();
    }
}

class StaticMethodRules {
    private int instanceVar = 10;
    private static int staticVar = 20;

    public static void staticMethod() {
        // ✅ Can access static members
        System.out.println(staticVar);

        // ❌ COMPILE ERROR: Cannot access instance members from static context
        // System.out.println(instanceVar);   // Error!
        // System.out.println(this);          // Error! No 'this' in static

        // ❌ Cannot call instance methods directly
        // instanceMethod();                  // Error!
    }

    public void instanceMethod() {
        // ✅ Instance methods CAN access both static and instance members
        System.out.println(instanceVar);  // OK
        System.out.println(staticVar);    // OK
        staticMethod();                   // OK (but use ClassName.method() for clarity)
    }
}
```

### Static Blocks (Initialization Order)

```java
public class InitializationOrder {
    // ═══════════════════════════════════════════════════════
    // STATIC BLOCKS - run ONCE when class is first loaded
    // Execute in order they appear, before any constructor
    // ═══════════════════════════════════════════════════════

    // 1. Static variables initialized in declaration order
    private static final Map<String, Integer> COUNTRY_CODES;
    private static final Properties CONFIG;
    private static final Logger LOGGER;

    // 2. Static initialization blocks - complex static setup
    static {
        System.out.println("Static block 1: Initializing country codes");
        COUNTRY_CODES = new HashMap<>();
        COUNTRY_CODES.put("US", 1);
        COUNTRY_CODES.put("UK", 44);
        COUNTRY_CODES.put("IN", 91);
        COUNTRY_CODES.put("JP", 81);
    }

    static {
        System.out.println("Static block 2: Loading configuration");
        CONFIG = new Properties();
        try {
            // Load from classpath
            var stream = InitializationOrder.class.getResourceAsStream("/config.properties");
            if (stream != null) {
                CONFIG.load(stream);
            }
        } catch (IOException e) {
            throw new ExceptionInInitializerError("Failed to load config: " + e.getMessage());
            // Note: ExceptionInInitializerError kills the class loading
        }
    }

    static {
        System.out.println("Static block 3: Setting up logger");
        LOGGER = Logger.getLogger(InitializationOrder.class.getName());
    }

    // 3. Instance variables
    private String name;

    // 4. Instance initializer block (runs before constructor, after static)
    {
        System.out.println("Instance initializer block");
        this.name = "default";
    }

    // 5. Constructor
    public InitializationOrder(String name) {
        System.out.println("Constructor called");
        this.name = name;
    }
}
```

```java
// ═══════════════════════════════════════════════════════
// COMPLETE INITIALIZATION ORDER DEMONSTRATION
// ═══════════════════════════════════════════════════════

class Parent {
    static { System.out.println("1. Parent static block"); }
    { System.out.println("4. Parent instance block"); }
    Parent() { System.out.println("5. Parent constructor"); }
}

class Child extends Parent {
    static { System.out.println("2. Child static block"); }
    { System.out.println("6. Child instance block"); }
    Child() { System.out.println("7. Child constructor"); }
}

class InitOrderDemo {
    public static void main(String[] args) {
        System.out.println("3. main() starts");
        new Child();
        System.out.println("---");
        new Child();  // Static blocks DON'T run again
    }
    /*
     * Output:
     * 1. Parent static block       ← Class loading (once)
     * 2. Child static block        ← Class loading (once)
     * 3. main() starts
     * 4. Parent instance block     ← Object creation
     * 5. Parent constructor
     * 6. Child instance block
     * 7. Child constructor
     * ---
     * 4. Parent instance block     ← Second object
     * 5. Parent constructor
     * 6. Child instance block
     * 7. Child constructor
     */
}
```

### Static Imports

```java
// ═══════════════════════════════════════════════════════
// STATIC IMPORTS - use static members without class prefix
// ═══════════════════════════════════════════════════════

import static java.lang.Math.PI;
import static java.lang.Math.sqrt;
import static java.lang.Math.pow;
import static java.util.Collections.unmodifiableList;
import static java.util.stream.Collectors.toList;
import static org.junit.jupiter.api.Assertions.*;  // Common in tests

class StaticImportDemo {
    public double circleArea(double radius) {
        // Without static import: Math.PI * Math.pow(radius, 2)
        return PI * pow(radius, 2);  // Cleaner with static import
    }

    public double hypotenuse(double a, double b) {
        return sqrt(pow(a, 2) + pow(b, 2));
    }

    // ⚠️ Use sparingly! Too many static imports reduce readability
    // ✅ Good: Math functions, test assertions, Collections utilities
    // ❌ Bad: static importing everything from multiple classes
}
```

---

## 2. Inner Classes (4 Types)

### Type 1: Regular (Non-Static) Inner Class

```java
public class LinkedList<T> {
    private Node<T> head;
    private int size;

    // ═══════════════════════════════════════════════════════
    // REGULAR INNER CLASS
    // - Has implicit reference to enclosing instance (LinkedList.this)
    // - Can access ALL members of outer class (including private)
    // - Cannot have static members (except constants)
    // - Creates memory overhead due to outer reference
    // ═══════════════════════════════════════════════════════
    private class Node<E> {
        E data;
        Node<E> next;

        Node(E data) {
            this.data = data;
            // Can access outer class members!
            size++;  // Accesses LinkedList.this.size
        }
    }

    // Inner class for iterator - needs access to outer list's head
    public class ListIterator {
        private Node<T> current = head;  // Accesses outer's private field!

        public boolean hasNext() {
            return current != null;
        }

        public T next() {
            if (!hasNext()) throw new NoSuchElementException();
            T data = current.data;
            current = current.next;
            return data;
        }

        // Accessing outer class explicitly
        public int getListSize() {
            return LinkedList.this.size;  // Explicit outer reference
        }
    }

    public void addFirst(T data) {
        Node<T> newNode = new Node<>(data);
        newNode.next = head;
        head = newNode;
    }

    public ListIterator iterator() {
        return new ListIterator();  // Inner class needs outer instance
    }

    public int getSize() { return size; }
}

class RegularInnerClassDemo {
    public static void main(String[] args) {
        LinkedList<String> list = new LinkedList<>();
        list.addFirst("C");
        list.addFirst("B");
        list.addFirst("A");

        // Inner class instance is TIED to outer instance
        LinkedList<String>.ListIterator iter = list.iterator();
        // Or with var:
        var iter2 = list.iterator();

        while (iter.hasNext()) {
            System.out.println(iter.next());
        }
        System.out.println("Size: " + iter.getListSize());

        // Creating inner class instance from outside (unusual but possible):
        // LinkedList<String>.ListIterator external = list.new ListIterator();
    }
}
```

### Type 2: Static Nested Class

```java
public class Graph<T> {
    private Map<T, List<Edge<T>>> adjacencyList = new HashMap<>();

    // ═══════════════════════════════════════════════════════
    // STATIC NESTED CLASS
    // - Does NOT have reference to outer instance
    // - Behaves like a top-level class, just namespaced inside outer
    // - CAN have its own static members
    // - Cannot access outer class's instance members
    // - Preferred when inner doesn't need outer reference
    // - NO MEMORY LEAK risk (no hidden outer reference)
    // ═══════════════════════════════════════════════════════

    public static class Edge<T> {
        private final T from;
        private final T to;
        private final double weight;

        public Edge(T from, T to, double weight) {
            this.from = from;
            this.to = to;
            this.weight = weight;
        }

        public T getFrom() { return from; }
        public T getTo() { return to; }
        public double getWeight() { return weight; }

        @Override
        public String toString() {
            return from + " -> " + to + " (weight: " + weight + ")";
        }
    }

    // Builder pattern - commonly uses static nested class
    public static class Builder<T> {
        private final Graph<T> graph = new Graph<>();

        public Builder<T> addEdge(T from, T to, double weight) {
            graph.adjacencyList
                 .computeIfAbsent(from, k -> new ArrayList<>())
                 .add(new Edge<>(from, to, weight));
            return this;
        }

        public Builder<T> addBidirectional(T from, T to, double weight) {
            addEdge(from, to, weight);
            addEdge(to, from, weight);
            return this;
        }

        public Graph<T> build() {
            return graph;
        }
    }

    public List<Edge<T>> getNeighbors(T node) {
        return adjacencyList.getOrDefault(node, Collections.emptyList());
    }

    public void printGraph() {
        adjacencyList.forEach((node, edges) -> {
            System.out.println(node + ": " + edges);
        });
    }
}

class StaticNestedDemo {
    public static void main(String[] args) {
        // Static nested class can be instantiated WITHOUT outer instance
        Graph.Edge<String> edge = new Graph.Edge<>("A", "B", 5.0);
        System.out.println(edge);

        // Builder pattern with static nested class
        Graph<String> graph = new Graph.Builder<String>()
                .addBidirectional("A", "B", 4.0)
                .addBidirectional("B", "C", 3.0)
                .addEdge("A", "C", 7.0)
                .build();

        graph.printGraph();
    }
}
```

### Type 3: Local Inner Class

```java
public class EventProcessor {

    // ═══════════════════════════════════════════════════════
    // LOCAL INNER CLASS - defined inside a method
    // - Scope limited to the enclosing method
    // - Can access outer class members AND effectively final local variables
    // - Cannot have access modifiers (it's local, like a local variable)
    // - Rarely used since Java 8 (lambdas are preferred)
    // ═══════════════════════════════════════════════════════

    public Runnable createTask(String taskName, int priority) {
        // Local variable - must be effectively final to be captured
        final String prefix = "[" + taskName + "]";

        // Local inner class - defined inside method
        class PrioritizedTask implements Runnable, Comparable<PrioritizedTask> {
            @Override
            public void run() {
                // Can access: method parameters (if effectively final)
                //             local variables (if effectively final)
                //             outer class instance members
                System.out.println(prefix + " Running with priority " + priority);
            }

            @Override
            public int compareTo(PrioritizedTask other) {
                return Integer.compare(priority, priority);
            }

            @Override
            public String toString() {
                return prefix + " (priority: " + priority + ")";
            }
        }

        return new PrioritizedTask();
    }

    // Practical use case: complex validation logic
    public boolean validateOrder(Order order) {
        // Local class encapsulates validation steps
        class OrderValidator {
            private final List<String> errors = new ArrayList<>();

            boolean validate() {
                checkItems();
                checkPayment();
                checkShipping();
                if (!errors.isEmpty()) {
                    errors.forEach(e -> System.out.println("VALIDATION ERROR: " + e));
                }
                return errors.isEmpty();
            }

            private void checkItems() {
                if (order.getItems().isEmpty()) errors.add("No items");
            }

            private void checkPayment() {
                if (order.getPaymentMethod() == null) errors.add("No payment");
            }

            private void checkShipping() {
                if (order.getAddress() == null) errors.add("No shipping address");
            }
        }

        return new OrderValidator().validate();
    }
}
```

### Type 4: Anonymous Inner Class

```java
import java.util.*;
import java.util.concurrent.*;

public class AnonymousClassDemo {

    // ═══════════════════════════════════════════════════════
    // ANONYMOUS INNER CLASS
    // - No name - defined and instantiated in ONE expression
    // - Implements an interface OR extends a class inline
    // - Cannot have explicit constructors (uses instance initializer)
    // - Used for one-off implementations
    // - Largely replaced by lambdas for functional interfaces
    // ═══════════════════════════════════════════════════════

    public static void main(String[] args) {

        // ──── Example 1: Implementing an interface anonymously ────
        Comparator<String> byLength = new Comparator<String>() {
            @Override
            public int compare(String a, String b) {
                return Integer.compare(a.length(), b.length());
            }
        };

        // Same thing with lambda (preferred for functional interfaces):
        Comparator<String> byLengthLambda = (a, b) -> Integer.compare(a.length(), b.length());
        // Or: Comparator.comparingInt(String::length)

        List<String> names = Arrays.asList("Alice", "Bob", "Charlie", "Jo");
        names.sort(byLength);
        System.out.println(names);  // [Jo, Bob, Alice, Charlie]

        // ──── Example 2: Extending a class anonymously ────
        // Useful when you need to override behavior for ONE instance
        Thread worker = new Thread() {
            @Override
            public void run() {
                System.out.println("Anonymous thread running: " + getName());
            }
        };
        worker.start();

        // ──── Example 3: Anonymous class with multiple methods ────
        // (Cannot use lambda - has multiple abstract methods or extends class)
        AbstractAction action = new AbstractAction("Save") {
            {
                // Instance initializer block (acts like constructor)
                System.out.println("Initializing save action");
            }

            @Override
            public void execute() {
                System.out.println("Saving document...");
            }

            @Override
            public void undo() {
                System.out.println("Undoing save...");
            }
        };
        action.execute();

        // ──── Example 4: Anonymous class capturing local variables ────
        final String greeting = "Hello";  // Must be effectively final
        Runnable greeter = new Runnable() {
            @Override
            public void run() {
                System.out.println(greeting + " from anonymous class!");
                // greeting = "Hi";  ← COMPILE ERROR: must be effectively final
            }
        };
        greeter.run();

        // ──── Example 5: Double-brace initialization (anti-pattern!) ────
        // Creates anonymous subclass + instance initializer
        // ⚠️ AVOID - creates unnecessary class, holds outer reference
        Map<String, Integer> scores = new HashMap<>() {{
            put("Alice", 95);
            put("Bob", 87);
            put("Charlie", 92);
        }};
        // Better: Map.of("Alice", 95, "Bob", 87, "Charlie", 92)
    }
}

// Helper class for example
abstract class AbstractAction {
    private final String name;

    public AbstractAction(String name) {
        this.name = name;
    }

    public abstract void execute();
    public abstract void undo();

    public String getName() { return name; }
}
```

### When to Use Each + Memory Leak Implications

```java
/*
 * ════════════════════════════════════════════════════════════
 * CHOOSING THE RIGHT INNER CLASS TYPE
 * ════════════════════════════════════════════════════════════
 *
 * ┌──────────────────────┬────────────────────────────────────────┐
 * │ Type                 │ When to Use                            │
 * ├──────────────────────┼────────────────────────────────────────┤
 * │ Regular inner class  │ Needs access to outer instance state   │
 * │                      │ Logically bound to outer (e.g., Node)  │
 * │                      │ Multiple methods, complex behavior     │
 * ├──────────────────────┼────────────────────────────────────────┤
 * │ Static nested class  │ Doesn't need outer instance            │
 * │                      │ Builder, Entry, Config objects          │
 * │                      │ Should be DEFAULT choice               │
 * ├──────────────────────┼────────────────────────────────────────┤
 * │ Local inner class    │ Used only within one method            │
 * │                      │ Needs to implement interface + extra   │
 * │                      │ Rarely used (prefer lambda/anonymous)  │
 * ├──────────────────────┼────────────────────────────────────────┤
 * │ Anonymous class      │ One-off implementation, no reuse       │
 * │                      │ Multiple methods (can't use lambda)    │
 * │                      │ Event handlers, callbacks              │
 * └──────────────────────┴────────────────────────────────────────┘
 *
 * ════════════════════════════════════════════════════════════
 * ⚠️  MEMORY LEAK: Non-static inner classes
 * ════════════════════════════════════════════════════════════
 *
 * Every non-static inner class instance holds a HIDDEN reference
 * to its enclosing class instance (OuterClass.this).
 *
 * This means the outer instance CANNOT be garbage collected as
 * long as the inner class instance is reachable!
 *
 * DANGEROUS PATTERNS:
 * 1. Returning inner class instance that outlives the outer
 * 2. Registering inner class as listener (never unregistered)
 * 3. Anonymous Runnable/Callable in thread pools
 * 4. Handler in Android (Activity leak)
 */

// ❌ MEMORY LEAK EXAMPLE
class LeakyClass {
    private byte[] largeData = new byte[10_000_000];  // 10MB

    public Runnable createTask() {
        // Anonymous class captures reference to LeakyClass.this
        return new Runnable() {
            @Override
            public void run() {
                System.out.println("Working...");
                // Even though we don't use largeData,
                // this Runnable keeps LeakyClass alive!
            }
        };
    }
}

// ✅ FIX: Use static nested class or lambda
class FixedClass {
    private byte[] largeData = new byte[10_000_000];

    // Option 1: Lambda (no outer reference if not accessing outer members)
    public Runnable createTask() {
        return () -> System.out.println("Working...");
        // Lambda that doesn't capture 'this' won't hold outer reference
    }

    // Option 2: Static nested class (explicitly no outer reference)
    private static class Task implements Runnable {
        @Override
        public void run() {
            System.out.println("Working...");
        }
    }
}
```

---

## 3. Enums

### Enum Basics

```java
// ═══════════════════════════════════════════════════════
// ENUM BASICS
// - Fixed set of named constants
// - Implicitly extends java.lang.Enum (cannot extend another class)
// - Implicitly final (cannot be subclassed)
// - Each constant is a singleton instance
// - Thread-safe by design
// ═══════════════════════════════════════════════════════

public enum Direction {
    NORTH, SOUTH, EAST, WEST;
}

class EnumBasicsDemo {
    public static void main(String[] args) {
        Direction dir = Direction.NORTH;

        // Built-in methods from java.lang.Enum
        System.out.println(dir.name());      // "NORTH" - exact name as declared
        System.out.println(dir.ordinal());   // 0 - position (0-indexed)
        System.out.println(dir.toString());  // "NORTH" (same as name() by default)

        // values() - returns array of all constants (compiler-generated)
        Direction[] allDirs = Direction.values();
        for (Direction d : allDirs) {
            System.out.printf("%s (ordinal: %d)%n", d, d.ordinal());
        }

        // valueOf() - get enum constant by name (case-sensitive!)
        Direction east = Direction.valueOf("EAST");  // OK
        // Direction.valueOf("east");  // IllegalArgumentException!

        // Enum in switch (no need for Direction. prefix inside switch)
        switch (dir) {
            case NORTH -> System.out.println("Going up");
            case SOUTH -> System.out.println("Going down");
            case EAST  -> System.out.println("Going right");
            case WEST  -> System.out.println("Going left");
        }

        // Comparison - use == (not equals) for enums!
        // Enums are singletons, so identity comparison is correct
        if (dir == Direction.NORTH) {
            System.out.println("Pointing north!");
        }
    }
}
```

### Enum with Fields, Constructors, and Methods

```java
public enum Planet {
    // ═══════════════════════════════════════════════════════
    // Each constant calls the constructor with arguments
    // ═══════════════════════════════════════════════════════
    MERCURY(3.303e+23, 2.4397e6),
    VENUS  (4.869e+24, 6.0518e6),
    EARTH  (5.976e+24, 6.37814e6),
    MARS   (6.421e+23, 3.3972e6),
    JUPITER(1.9e+27,   7.1492e7),
    SATURN (5.688e+26, 6.0268e7),
    URANUS (8.686e+25, 2.5559e7),
    NEPTUNE(1.024e+26, 2.4746e7);

    // ═══════════════════════════════════════════════════════
    // FIELDS - each enum constant has its own copy
    // ═══════════════════════════════════════════════════════
    private final double mass;    // in kg
    private final double radius;  // in meters

    // Gravitational constant
    private static final double G = 6.67300E-11;

    // ═══════════════════════════════════════════════════════
    // CONSTRUCTOR - always private (even without keyword)
    // Cannot be called externally - only by enum constants
    // ═══════════════════════════════════════════════════════
    Planet(double mass, double radius) {
        this.mass = mass;
        this.radius = radius;
    }

    // ═══════════════════════════════════════════════════════
    // METHODS - each enum constant responds to these
    // ═══════════════════════════════════════════════════════
    public double getMass() { return mass; }
    public double getRadius() { return radius; }

    public double surfaceGravity() {
        return G * mass / (radius * radius);
    }

    public double surfaceWeight(double otherMass) {
        return otherMass * surfaceGravity();
    }

    @Override
    public String toString() {
        return name() + String.format(" (mass=%.3e kg, radius=%.3e m)", mass, radius);
    }
}

class PlanetDemo {
    public static void main(String[] args) {
        double earthWeight = 75.0;  // kg on Earth
        double mass = earthWeight / Planet.EARTH.surfaceGravity();

        System.out.printf("Weight on different planets (Earth weight: %.1f kg):%n", earthWeight);
        for (Planet p : Planet.values()) {
            System.out.printf("  %-8s: %6.2f kg%n", p.name(), p.surfaceWeight(mass));
        }
    }
}
```

### Enum Implementing Interfaces

```java
// ═══════════════════════════════════════════════════════
// ENUM WITH INTERFACE - each constant provides implementation
// ═══════════════════════════════════════════════════════

interface MathOperation {
    double apply(double a, double b);
    String getSymbol();
}

public enum ArithmeticOp implements MathOperation {
    // Each constant provides its own implementation (constant-specific method)
    ADD {
        @Override
        public double apply(double a, double b) { return a + b; }
        @Override
        public String getSymbol() { return "+"; }
    },
    SUBTRACT {
        @Override
        public double apply(double a, double b) { return a - b; }
        @Override
        public String getSymbol() { return "-"; }
    },
    MULTIPLY {
        @Override
        public double apply(double a, double b) { return a * b; }
        @Override
        public String getSymbol() { return "×"; }
    },
    DIVIDE {
        @Override
        public double apply(double a, double b) {
            if (b == 0) throw new ArithmeticException("Division by zero");
            return a / b;
        }
        @Override
        public String getSymbol() { return "÷"; }
    },
    POWER {
        @Override
        public double apply(double a, double b) { return Math.pow(a, b); }
        @Override
        public String getSymbol() { return "^"; }
    };

    // Shared method for all constants
    public String format(double a, double b) {
        return String.format("%.2f %s %.2f = %.2f", a, getSymbol(), b, apply(a, b));
    }
}

class EnumInterfaceDemo {
    public static void main(String[] args) {
        // Use enum as a strategy
        for (ArithmeticOp op : ArithmeticOp.values()) {
            System.out.println(op.format(10, 3));
        }
        // Output:
        // 10.00 + 3.00 = 13.00
        // 10.00 - 3.00 = 7.00
        // 10.00 × 3.00 = 30.00
        // 10.00 ÷ 3.00 = 3.33
        // 10.00 ^ 3.00 = 1000.00

        // Pass enum as interface type
        MathOperation op = ArithmeticOp.ADD;
        System.out.println(op.apply(5, 3));  // 8.0
    }
}
```

### EnumSet and EnumMap

```java
import java.util.EnumSet;
import java.util.EnumMap;

// ═══════════════════════════════════════════════════════
// EnumSet - high-performance Set implementation for enums
// Internally uses bit vector (long or long[])
// Much faster than HashSet for enum types
// ═══════════════════════════════════════════════════════

enum Permission {
    READ, WRITE, EXECUTE, DELETE, ADMIN
}

class EnumSetDemo {
    public static void main(String[] args) {
        // Factory methods (no constructor)
        EnumSet<Permission> noPerms = EnumSet.noneOf(Permission.class);
        EnumSet<Permission> allPerms = EnumSet.allOf(Permission.class);
        EnumSet<Permission> readWrite = EnumSet.of(Permission.READ, Permission.WRITE);
        EnumSet<Permission> range = EnumSet.range(Permission.READ, Permission.EXECUTE);

        // Operations
        EnumSet<Permission> userPerms = EnumSet.of(Permission.READ, Permission.WRITE);
        userPerms.add(Permission.EXECUTE);
        System.out.println("User permissions: " + userPerms);

        // Check permission
        if (userPerms.contains(Permission.ADMIN)) {
            System.out.println("Has admin access");
        } else {
            System.out.println("No admin access");
        }

        // Complement (all permissions NOT in the set)
        EnumSet<Permission> missing = EnumSet.complementOf(userPerms);
        System.out.println("Missing permissions: " + missing);  // [DELETE, ADMIN]
    }
}

// ═══════════════════════════════════════════════════════
// EnumMap - Map implementation with enum keys
// Internally uses array indexed by ordinal
// Much faster than HashMap for enum keys
// ═══════════════════════════════════════════════════════

enum Day {
    MONDAY, TUESDAY, WEDNESDAY, THURSDAY, FRIDAY, SATURDAY, SUNDAY
}

class EnumMapDemo {
    public static void main(String[] args) {
        EnumMap<Day, String> schedule = new EnumMap<>(Day.class);
        schedule.put(Day.MONDAY, "Team standup, Sprint planning");
        schedule.put(Day.TUESDAY, "Deep work");
        schedule.put(Day.WEDNESDAY, "Code review day");
        schedule.put(Day.THURSDAY, "Deep work");
        schedule.put(Day.FRIDAY, "Retrospective, Demo");
        schedule.put(Day.SATURDAY, "Rest");
        schedule.put(Day.SUNDAY, "Rest");

        // Iteration preserves declaration order of enum constants
        schedule.forEach((day, activity) ->
            System.out.printf("%-10s: %s%n", day, activity));

        // EnumMap with complex values
        EnumMap<Day, List<String>> meetings = new EnumMap<>(Day.class);
        for (Day day : Day.values()) {
            meetings.put(day, new ArrayList<>());
        }
        meetings.get(Day.MONDAY).add("9:00 - Standup");
        meetings.get(Day.MONDAY).add("14:00 - Planning");
    }
}
```

### Enum Singleton Pattern

```java
// ═══════════════════════════════════════════════════════
// ENUM SINGLETON - the BEST singleton implementation in Java
// Advantages:
// 1. Thread-safe (enum initialization is thread-safe by JLS)
// 2. Serialization-safe (no extra instance on deserialization)
// 3. Reflection-safe (cannot create enum via reflection)
// 4. Simple and concise
// ═══════════════════════════════════════════════════════

public enum AppConfig {
    INSTANCE;  // Single enum constant = singleton

    private final Map<String, String> properties = new ConcurrentHashMap<>();
    private final AtomicInteger requestCount = new AtomicInteger(0);

    // Constructor runs once (when enum is loaded)
    AppConfig() {
        // Load default configuration
        properties.put("app.name", "MyApp");
        properties.put("app.version", "1.0.0");
        properties.put("db.url", "jdbc:postgresql://localhost:5432/mydb");
        properties.put("db.pool.size", "10");
    }

    public String get(String key) {
        requestCount.incrementAndGet();
        return properties.get(key);
    }

    public void set(String key, String value) {
        properties.put(key, value);
    }

    public int getRequestCount() {
        return requestCount.get();
    }

    public Map<String, String> getAll() {
        return Collections.unmodifiableMap(properties);
    }
}

class SingletonDemo {
    public static void main(String[] args) {
        // Always returns same instance
        AppConfig config = AppConfig.INSTANCE;
        System.out.println(config.get("app.name"));    // "MyApp"
        System.out.println(config.get("db.url"));      // "jdbc:..."

        config.set("app.env", "production");

        // From anywhere else in the application
        String env = AppConfig.INSTANCE.get("app.env");  // "production"
        System.out.println("Env: " + env);

        // Same reference guaranteed
        System.out.println(config == AppConfig.INSTANCE);  // true
    }
}
```

### Complete Example: State Machine with Enum

```java
// ═══════════════════════════════════════════════════════
// STATE MACHINE - Order processing lifecycle
// Each state defines valid transitions and behavior
// ═══════════════════════════════════════════════════════

public enum OrderState {
    CREATED {
        @Override
        public OrderState next() { return PAID; }

        @Override
        public OrderState cancel() { return CANCELLED; }

        @Override
        public boolean canEdit() { return true; }
    },
    PAID {
        @Override
        public OrderState next() { return PROCESSING; }

        @Override
        public OrderState cancel() { return REFUNDING; }

        @Override
        public boolean canEdit() { return false; }
    },
    PROCESSING {
        @Override
        public OrderState next() { return SHIPPED; }

        @Override
        public OrderState cancel() { return REFUNDING; }

        @Override
        public boolean canEdit() { return false; }
    },
    SHIPPED {
        @Override
        public OrderState next() { return DELIVERED; }

        @Override
        public OrderState cancel() {
            throw new IllegalStateException("Cannot cancel shipped order");
        }

        @Override
        public boolean canEdit() { return false; }
    },
    DELIVERED {
        @Override
        public OrderState next() {
            throw new IllegalStateException("Order already delivered - terminal state");
        }

        @Override
        public OrderState cancel() {
            throw new IllegalStateException("Cannot cancel delivered order");
        }

        @Override
        public boolean canEdit() { return false; }
    },
    CANCELLED {
        @Override
        public OrderState next() {
            throw new IllegalStateException("Cancelled order cannot proceed");
        }

        @Override
        public OrderState cancel() {
            throw new IllegalStateException("Already cancelled");
        }

        @Override
        public boolean canEdit() { return false; }
    },
    REFUNDING {
        @Override
        public OrderState next() { return REFUNDED; }

        @Override
        public OrderState cancel() {
            throw new IllegalStateException("Refund in progress");
        }

        @Override
        public boolean canEdit() { return false; }
    },
    REFUNDED {
        @Override
        public OrderState next() {
            throw new IllegalStateException("Terminal state");
        }

        @Override
        public OrderState cancel() {
            throw new IllegalStateException("Already refunded");
        }

        @Override
        public boolean canEdit() { return false; }
    };

    // Abstract methods - each constant MUST implement
    public abstract OrderState next();
    public abstract OrderState cancel();
    public abstract boolean canEdit();

    // Shared method
    public boolean isTerminal() {
        return this == DELIVERED || this == CANCELLED || this == REFUNDED;
    }
}

// Order class using the state machine
class Order {
    private final String orderId;
    private OrderState state;
    private final List<String> history = new ArrayList<>();

    public Order(String orderId) {
        this.orderId = orderId;
        this.state = OrderState.CREATED;
        log("Order created");
    }

    public void advance() {
        OrderState previous = state;
        state = state.next();
        log(previous + " → " + state);
    }

    public void cancel() {
        OrderState previous = state;
        state = state.cancel();
        log(previous + " → " + state + " (cancelled)");
    }

    public OrderState getState() { return state; }

    public List<String> getHistory() {
        return Collections.unmodifiableList(history);
    }

    private void log(String event) {
        history.add(String.format("[%s] %s", LocalDateTime.now().toLocalTime(), event));
    }

    @Override
    public String toString() {
        return "Order{" + orderId + ", state=" + state + "}";
    }
}

class StateMachineDemo {
    public static void main(String[] args) {
        Order order = new Order("ORD-001");
        System.out.println(order);  // CREATED

        order.advance();  // → PAID
        order.advance();  // → PROCESSING
        order.advance();  // → SHIPPED
        order.advance();  // → DELIVERED
        System.out.println(order);

        System.out.println("\nOrder history:");
        order.getHistory().forEach(System.out::println);

        System.out.println("\n--- Order with cancellation ---");
        Order order2 = new Order("ORD-002");
        order2.advance();  // → PAID
        order2.cancel();   // → REFUNDING
        order2.advance();  // → REFUNDED
        System.out.println(order2);

        System.out.println("\n--- Invalid transition ---");
        try {
            Order order3 = new Order("ORD-003");
            order3.advance();  // PAID
            order3.advance();  // PROCESSING
            order3.advance();  // SHIPPED
            order3.cancel();   // IllegalStateException!
        } catch (IllegalStateException e) {
            System.out.println("Caught: " + e.getMessage());
        }
    }
}
```

---

## 4. Records (Java 14+)

### Immutable Data Carriers

```java
// ═══════════════════════════════════════════════════════
// RECORDS - concise immutable data classes
// Compiler auto-generates:
//   - private final fields
//   - canonical constructor
//   - getters (named same as fields, NOT getXxx())
//   - equals() based on ALL fields
//   - hashCode() based on ALL fields
//   - toString() showing all fields
// ═══════════════════════════════════════════════════════

// Simple record - replaces ~40 lines of boilerplate class
public record Point(double x, double y) {
    // That's it! Fully functional immutable class.
}

// Record with validation using COMPACT CONSTRUCTOR
public record Email(String address) {
    // Compact constructor - no parameter list, validates args
    public Email {
        if (address == null || !address.contains("@")) {
            throw new IllegalArgumentException("Invalid email: " + address);
        }
        // Can reassign parameter (transforms before storing)
        address = address.toLowerCase().trim();
    }
}

// Complex record with multiple components
public record HttpResponse(
    int statusCode,
    Map<String, List<String>> headers,
    String body,
    long responseTimeMs
) {
    // Compact constructor for validation + defensive copy
    public HttpResponse {
        if (statusCode < 100 || statusCode > 599) {
            throw new IllegalArgumentException("Invalid status code: " + statusCode);
        }
        // Defensive copy of mutable parameter
        headers = headers == null
            ? Map.of()
            : Collections.unmodifiableMap(new HashMap<>(headers));
    }

    // Custom methods
    public boolean isSuccess() {
        return statusCode >= 200 && statusCode < 300;
    }

    public boolean isError() {
        return statusCode >= 400;
    }

    public Optional<String> getHeader(String name) {
        List<String> values = headers.get(name.toLowerCase());
        return values != null && !values.isEmpty()
            ? Optional.of(values.get(0))
            : Optional.empty();
    }

    // Static factory methods
    public static HttpResponse ok(String body) {
        return new HttpResponse(200, Map.of(), body, 0);
    }

    public static HttpResponse notFound() {
        return new HttpResponse(404, Map.of(), "Not Found", 0);
    }
}

// Record implementing interface
public record Range(int start, int end) implements Comparable<Range> {
    public Range {
        if (start > end) {
            throw new IllegalArgumentException("start must be <= end");
        }
    }

    public int length() {
        return end - start;
    }

    public boolean contains(int value) {
        return value >= start && value <= end;
    }

    public boolean overlaps(Range other) {
        return this.start <= other.end && other.start <= this.end;
    }

    @Override
    public int compareTo(Range other) {
        int cmp = Integer.compare(this.start, other.start);
        return cmp != 0 ? cmp : Integer.compare(this.end, other.end);
    }
}

class RecordDemo {
    public static void main(String[] args) {
        // Using records
        Point p1 = new Point(3.0, 4.0);
        Point p2 = new Point(3.0, 4.0);

        System.out.println(p1);           // Point[x=3.0, y=4.0]
        System.out.println(p1.x());       // 3.0  (accessor, not getX())
        System.out.println(p1.y());       // 4.0
        System.out.println(p1.equals(p2)); // true  (value equality)
        System.out.println(p1.hashCode() == p2.hashCode());  // true

        // Email with validation
        Email email = new Email("User@Example.COM");
        System.out.println(email.address());  // "user@example.com" (lowercased)

        // try { new Email("invalid"); } catch (IllegalArgumentException e) { ... }

        // HttpResponse
        HttpResponse resp = HttpResponse.ok("{\"status\": \"healthy\"}");
        System.out.println(resp.isSuccess());  // true
        System.out.println(resp.statusCode()); // 200

        // Records in collections (proper equals/hashCode!)
        Set<Point> points = new HashSet<>();
        points.add(new Point(1, 2));
        points.add(new Point(1, 2));  // Duplicate - not added
        System.out.println(points.size());  // 1

        // Decomposition in pattern matching (Java 21+)
        Object obj = new Point(5, 10);
        if (obj instanceof Point(double x, double y)) {
            System.out.println("Point at (" + x + ", " + y + ")");
        }
    }
}
```

### Records - Restrictions

```java
/*
 * RECORD RESTRICTIONS:
 * ═══════════════════════════════════════════════════════
 * 1. Cannot extend any class (implicitly extends java.lang.Record)
 * 2. Cannot be extended (implicitly final)
 * 3. All fields are final (immutable)
 * 4. Cannot declare instance fields beyond components
 * 5. CAN implement interfaces
 * 6. CAN have static fields and methods
 * 7. CAN have instance methods
 * 8. CAN override accessors (but must return same type)
 * 9. CAN have compact, custom, or canonical constructors
 *
 * WHEN TO USE RECORDS vs CLASS:
 * ✅ Record: DTOs, value objects, API responses, config, events
 * ❌ Class: Mutable state, JPA entities, inheritance needed
 */
```

---

## 5. Sealed Classes (Java 17+)

### Restricting Inheritance

```java
// ═══════════════════════════════════════════════════════
// SEALED CLASSES - control WHO can extend your class
// Only permitted subclasses can extend a sealed class
// Enables exhaustive pattern matching
// ═══════════════════════════════════════════════════════

// The sealed parent - lists ALL permitted subclasses
public sealed abstract class Expression
    permits NumberExpr, BinaryExpr, UnaryExpr, VariableExpr {

    // Common method for all expressions
    public abstract double evaluate(Map<String, Double> variables);
    public abstract String prettyPrint();
}

// FINAL - cannot be further extended
public final class NumberExpr extends Expression {
    private final double value;

    public NumberExpr(double value) {
        this.value = value;
    }

    @Override
    public double evaluate(Map<String, Double> variables) {
        return value;
    }

    @Override
    public String prettyPrint() {
        return String.valueOf(value);
    }
}

// NON-SEALED - opens up inheritance to anyone
public non-sealed class BinaryExpr extends Expression {
    private final Expression left;
    private final Expression right;
    private final ArithmeticOp operator;

    public BinaryExpr(Expression left, ArithmeticOp operator, Expression right) {
        this.left = left;
        this.right = right;
        this.operator = operator;
    }

    @Override
    public double evaluate(Map<String, Double> variables) {
        return operator.apply(left.evaluate(variables), right.evaluate(variables));
    }

    @Override
    public String prettyPrint() {
        return "(" + left.prettyPrint() + " " + operator.getSymbol() +
               " " + right.prettyPrint() + ")";
    }
}

// SEALED - allows further restricted subclassing
public sealed class UnaryExpr extends Expression
    permits NegateExpr, AbsoluteExpr {

    protected final Expression operand;

    public UnaryExpr(Expression operand) {
        this.operand = operand;
    }

    @Override
    public double evaluate(Map<String, Double> variables) {
        return operand.evaluate(variables);
    }

    @Override
    public String prettyPrint() {
        return operand.prettyPrint();
    }
}

public final class NegateExpr extends UnaryExpr {
    public NegateExpr(Expression operand) { super(operand); }

    @Override
    public double evaluate(Map<String, Double> variables) {
        return -operand.evaluate(variables);
    }

    @Override
    public String prettyPrint() {
        return "-" + operand.prettyPrint();
    }
}

public final class AbsoluteExpr extends UnaryExpr {
    public AbsoluteExpr(Expression operand) { super(operand); }

    @Override
    public double evaluate(Map<String, Double> variables) {
        return Math.abs(operand.evaluate(variables));
    }

    @Override
    public String prettyPrint() {
        return "|" + operand.prettyPrint() + "|";
    }
}

public final class VariableExpr extends Expression {
    private final String name;

    public VariableExpr(String name) { this.name = name; }

    @Override
    public double evaluate(Map<String, Double> variables) {
        Double value = variables.get(name);
        if (value == null) throw new IllegalStateException("Undefined variable: " + name);
        return value;
    }

    @Override
    public String prettyPrint() {
        return name;
    }
}
```

### Pattern Matching with Sealed Classes

```java
class SealedPatternMatchingDemo {
    // ═══════════════════════════════════════════════════════
    // EXHAUSTIVE PATTERN MATCHING
    // Compiler knows ALL possible subtypes of sealed class
    // No 'default' branch needed if all cases covered
    // ═══════════════════════════════════════════════════════

    static String describe(Expression expr) {
        return switch (expr) {
            case NumberExpr n    -> "Number: " + n.prettyPrint();
            case BinaryExpr b   -> "Binary: " + b.prettyPrint();
            case NegateExpr neg -> "Negation: " + neg.prettyPrint();
            case AbsoluteExpr a -> "Absolute: " + a.prettyPrint();
            case VariableExpr v -> "Variable: " + v.prettyPrint();
            // UnaryExpr is sealed with only Negate and Absolute
            // BinaryExpr is non-sealed but still a valid case
            // No default needed! Compiler verifies exhaustiveness
        };
    }

    public static void main(String[] args) {
        // Build expression: (x + 3) * |-5|
        Expression expr = new BinaryExpr(
            new BinaryExpr(
                new VariableExpr("x"),
                ArithmeticOp.ADD,
                new NumberExpr(3)
            ),
            ArithmeticOp.MULTIPLY,
            new AbsoluteExpr(new NegateExpr(new NumberExpr(5)))
        );

        Map<String, Double> vars = Map.of("x", 2.0);
        System.out.println(expr.prettyPrint());         // ((x + 3) × |-5|)
        System.out.println(expr.evaluate(vars));        // 25.0
        System.out.println(describe(expr));             // Binary: ((x + 3) × |-5|)
    }
}
```

### Sealed Interfaces (with Records)

```java
// Sealed interface with record implementations - common pattern
public sealed interface Result<T>
    permits Result.Success, Result.Failure, Result.Loading {

    record Success<T>(T value) implements Result<T> {}
    record Failure<T>(Exception error) implements Result<T> {}
    record Loading<T>() implements Result<T> {}

    // Default methods on sealed interface
    default boolean isSuccess() { return this instanceof Success; }
    default boolean isFailure() { return this instanceof Failure; }

    default T getOrElse(T defaultValue) {
        return switch (this) {
            case Success<T> s -> s.value();
            case Failure<T> f -> defaultValue;
            case Loading<T> l -> defaultValue;
        };
    }

    default <R> Result<R> map(Function<T, R> mapper) {
        return switch (this) {
            case Success<T> s -> new Success<>(mapper.apply(s.value()));
            case Failure<T> f -> new Failure<>(f.error());
            case Loading<T> l -> new Loading<>();
        };
    }
}

class SealedInterfaceDemo {
    public static void main(String[] args) {
        Result<String> result = fetchData();

        String message = switch (result) {
            case Result.Success<String> s -> "Got: " + s.value();
            case Result.Failure<String> f -> "Error: " + f.error().getMessage();
            case Result.Loading<String> l -> "Loading...";
        };
        System.out.println(message);
    }

    static Result<String> fetchData() {
        try {
            return new Result.Success<>("Hello from sealed interface!");
        } catch (Exception e) {
            return new Result.Failure<>(e);
        }
    }
}
```

---

## 6. Object Class Methods

### equals() and hashCode() Contract

```java
import java.util.Objects;

public class Person {
    private final String firstName;
    private final String lastName;
    private final int age;
    private final String email;

    public Person(String firstName, String lastName, int age, String email) {
        this.firstName = firstName;
        this.lastName = lastName;
        this.age = age;
        this.email = email;
    }

    // ═══════════════════════════════════════════════════════
    // equals() CONTRACT:
    // 1. Reflexive:  x.equals(x) == true
    // 2. Symmetric:  x.equals(y) == y.equals(x)
    // 3. Transitive: x.equals(y) && y.equals(z) → x.equals(z)
    // 4. Consistent: multiple calls return same result
    // 5. x.equals(null) == false
    // ═══════════════════════════════════════════════════════
    @Override
    public boolean equals(Object obj) {
        // 1. Same reference? (optimization + reflexive)
        if (this == obj) return true;

        // 2. Null check + type check (handles null case too)
        if (obj == null || getClass() != obj.getClass()) return false;
        // Note: getClass() != instanceof
        // getClass() is STRICT - exact class match only
        // instanceof allows subclasses (breaks symmetry if subclass adds fields)

        // 3. Cast and compare fields
        Person other = (Person) obj;
        return age == other.age
            && Objects.equals(firstName, other.firstName)
            && Objects.equals(lastName, other.lastName)
            && Objects.equals(email, other.email);
    }

    // ═══════════════════════════════════════════════════════
    // hashCode() CONTRACT:
    // 1. If a.equals(b), then a.hashCode() == b.hashCode()
    //    (MUST be true - violating this breaks HashMap/HashSet)
    // 2. If !a.equals(b), hashCode MAY be different (should be for performance)
    // 3. Consistent: same value across multiple calls in same execution
    //
    // RULE: Always override hashCode() when you override equals()!
    // ═══════════════════════════════════════════════════════
    @Override
    public int hashCode() {
        return Objects.hash(firstName, lastName, age, email);
        // Equivalent to manual implementation:
        // int result = 17;
        // result = 31 * result + (firstName != null ? firstName.hashCode() : 0);
        // result = 31 * result + (lastName != null ? lastName.hashCode() : 0);
        // result = 31 * result + age;
        // result = 31 * result + (email != null ? email.hashCode() : 0);
        // return result;
    }

    // ═══════════════════════════════════════════════════════
    // toString() - human-readable representation
    // Used by: System.out.println(), debugger, logging, String concatenation
    // ═══════════════════════════════════════════════════════
    @Override
    public String toString() {
        return String.format("Person{firstName='%s', lastName='%s', age=%d, email='%s'}",
                firstName, lastName, age, email);
    }

    // Getters
    public String getFirstName() { return firstName; }
    public String getLastName() { return lastName; }
    public int getAge() { return age; }
    public String getEmail() { return email; }
}

class EqualsHashCodeDemo {
    public static void main(String[] args) {
        Person p1 = new Person("Alice", "Smith", 30, "alice@example.com");
        Person p2 = new Person("Alice", "Smith", 30, "alice@example.com");
        Person p3 = new Person("Bob", "Jones", 25, "bob@example.com");

        // equals
        System.out.println(p1.equals(p2));  // true  (same values)
        System.out.println(p1.equals(p3));  // false (different values)
        System.out.println(p1 == p2);       // false (different objects!)

        // hashCode consistency with equals
        System.out.println(p1.hashCode() == p2.hashCode());  // true (equals → same hash)

        // Works correctly in HashMap/HashSet
        Map<Person, String> map = new HashMap<>();
        map.put(p1, "Developer");
        System.out.println(map.get(p2));  // "Developer" - works because equals + hashCode

        Set<Person> set = new HashSet<>();
        set.add(p1);
        set.add(p2);  // Not added - duplicate per equals()
        System.out.println(set.size());  // 1
    }
}
```

### clone() - Shallow vs Deep Copy

```java
public class Address implements Cloneable {
    private String street;
    private String city;
    private String country;

    public Address(String street, String city, String country) {
        this.street = street;
        this.city = city;
        this.country = country;
    }

    // Deep clone for Address (all fields are immutable Strings, so shallow is fine here)
    @Override
    public Address clone() {
        try {
            return (Address) super.clone();
        } catch (CloneNotSupportedException e) {
            throw new AssertionError();
        }
    }

    public void setStreet(String street) { this.street = street; }
    public String getStreet() { return street; }
    public String getCity() { return city; }

    @Override
    public String toString() {
        return street + ", " + city + ", " + country;
    }
}

public class Student implements Cloneable {
    private String name;
    private int age;
    private Address address;           // Mutable reference type!
    private List<String> courses;      // Mutable collection!

    public Student(String name, int age, Address address, List<String> courses) {
        this.name = name;
        this.age = age;
        this.address = address;
        this.courses = new ArrayList<>(courses);
    }

    // ═══════════════════════════════════════════════════════
    // SHALLOW CLONE - copies references, not objects
    // Both original and clone share the SAME Address and List objects
    // ═══════════════════════════════════════════════════════
    public Student shallowClone() {
        try {
            return (Student) super.clone();
            // name: shared (but String is immutable, so OK)
            // age: copied (primitive)
            // address: SHARED reference! ⚠️ Modifying affects both!
            // courses: SHARED reference! ⚠️ Modifying affects both!
        } catch (CloneNotSupportedException e) {
            throw new AssertionError();
        }
    }

    // ═══════════════════════════════════════════════════════
    // DEEP CLONE - creates independent copies of all objects
    // Original and clone are completely independent
    // ═══════════════════════════════════════════════════════
    @Override
    public Student clone() {
        try {
            Student cloned = (Student) super.clone();
            // Deep copy mutable fields
            cloned.address = this.address.clone();        // Clone the Address
            cloned.courses = new ArrayList<>(this.courses); // New list with same elements
            return cloned;
        } catch (CloneNotSupportedException e) {
            throw new AssertionError();
        }
    }

    // Alternative: Copy constructor (often preferred over clone)
    public Student(Student other) {
        this.name = other.name;
        this.age = other.age;
        this.address = other.address.clone();
        this.courses = new ArrayList<>(other.courses);
    }

    public Address getAddress() { return address; }
    public List<String> getCourses() { return courses; }
    public String getName() { return name; }

    @Override
    public String toString() {
        return String.format("Student{name='%s', age=%d, address=%s, courses=%s}",
                name, age, address, courses);
    }
}

class CloneDemo {
    public static void main(String[] args) {
        Student original = new Student("Alice", 20,
            new Address("123 Main St", "Boston", "USA"),
            List.of("Math", "CS", "Physics"));

        // ── Shallow Clone Problem ──
        Student shallow = original.shallowClone();
        shallow.getAddress().setStreet("456 Oak Ave");  // ⚠️ Changes BOTH!
        System.out.println("After shallow clone mutation:");
        System.out.println("Original: " + original.getAddress());  // 456 Oak Ave! BUG!
        System.out.println("Shallow:  " + shallow.getAddress());   // 456 Oak Ave

        // ── Deep Clone Solution ──
        Student original2 = new Student("Bob", 22,
            new Address("789 Elm St", "NYC", "USA"),
            List.of("English", "History"));

        Student deep = original2.clone();
        deep.getAddress().setStreet("999 Pine Rd");     // Only affects clone
        deep.getCourses().add("Art");                   // Only affects clone

        System.out.println("\nAfter deep clone mutation:");
        System.out.println("Original: " + original2);   // 789 Elm St, 2 courses
        System.out.println("Deep:     " + deep);        // 999 Pine Rd, 3 courses ✅
    }
}
```

### getClass() and finalize()

```java
public class ObjectMethodsDemo {

    // ═══════════════════════════════════════════════════════
    // getClass() - returns runtime Class object
    // - Final method (cannot override)
    // - Returns actual runtime type, not reference type
    // - Used for reflection, type checking
    // ═══════════════════════════════════════════════════════
    public static void demonstrateGetClass() {
        Object obj = "Hello";

        Class<?> clazz = obj.getClass();
        System.out.println(clazz.getName());          // java.lang.String
        System.out.println(clazz.getSimpleName());    // String
        System.out.println(clazz.getPackageName());   // java.lang
        System.out.println(clazz.getSuperclass());    // class java.lang.Object

        // Useful for logging/debugging
        System.out.println("Type: " + obj.getClass().getSimpleName());

        // Compare types
        System.out.println(obj.getClass() == String.class);  // true
    }

    // ═══════════════════════════════════════════════════════
    // finalize() - DEPRECATED since Java 9, REMOVED in Java 18
    //
    // Problems with finalize():
    // 1. Non-deterministic - GC decides when (or IF) it runs
    // 2. Performance: objects with finalizers take 2 GC cycles to collect
    // 3. Can resurrect objects (bad practice)
    // 4. No ordering guarantees
    // 5. Exceptions are silently swallowed
    //
    // ALTERNATIVES:
    // - try-with-resources (AutoCloseable) for resource cleanup
    // - java.lang.ref.Cleaner (Java 9+) for rare cases needing GC notification
    // ═══════════════════════════════════════════════════════

    // ✅ CORRECT way to handle resources
    static class DatabaseConnection implements AutoCloseable {
        private boolean open = true;

        public DatabaseConnection() {
            System.out.println("Connection opened");
        }

        public void query(String sql) {
            if (!open) throw new IllegalStateException("Connection closed");
            System.out.println("Executing: " + sql);
        }

        @Override
        public void close() {
            if (open) {
                open = false;
                System.out.println("Connection closed properly");
            }
        }
    }

    public static void main(String[] args) {
        demonstrateGetClass();

        // try-with-resources - guaranteed cleanup
        try (var conn = new DatabaseConnection()) {
            conn.query("SELECT * FROM users");
        }  // close() called automatically, even if exception thrown
    }
}
```

### wait(), notify(), notifyAll() - Thread Communication

```java
import java.util.LinkedList;
import java.util.Queue;

// ═══════════════════════════════════════════════════════
// wait(), notify(), notifyAll()
// - Defined in Object class (every object can be a monitor)
// - MUST be called from synchronized context (holding the monitor)
// - Used for inter-thread communication
// - wait(): releases lock, thread sleeps until notified
// - notify(): wakes ONE waiting thread
// - notifyAll(): wakes ALL waiting threads (preferred)
// ═══════════════════════════════════════════════════════

public class BoundedBuffer<T> {
    private final Queue<T> queue = new LinkedList<>();
    private final int capacity;

    public BoundedBuffer(int capacity) {
        this.capacity = capacity;
    }

    // Producer calls this
    public synchronized void put(T item) throws InterruptedException {
        // MUST use while loop (not if) - spurious wakeups!
        while (queue.size() == capacity) {
            System.out.println(Thread.currentThread().getName() + " waiting - buffer full");
            wait();  // Releases lock, suspends thread
            // When woken up, re-acquires lock and re-checks condition
        }
        queue.offer(item);
        System.out.println(Thread.currentThread().getName() + " put: " + item +
                " (size: " + queue.size() + ")");
        notifyAll();  // Wake consumers that might be waiting
    }

    // Consumer calls this
    public synchronized T take() throws InterruptedException {
        while (queue.isEmpty()) {
            System.out.println(Thread.currentThread().getName() + " waiting - buffer empty");
            wait();  // Releases lock, suspends thread
        }
        T item = queue.poll();
        System.out.println(Thread.currentThread().getName() + " took: " + item +
                " (size: " + queue.size() + ")");
        notifyAll();  // Wake producers that might be waiting
        return item;
    }

    public synchronized int size() {
        return queue.size();
    }
}

class WaitNotifyDemo {
    public static void main(String[] args) throws InterruptedException {
        BoundedBuffer<Integer> buffer = new BoundedBuffer<>(3);

        // Producer thread
        Thread producer = new Thread(() -> {
            try {
                for (int i = 1; i <= 8; i++) {
                    buffer.put(i);
                    Thread.sleep(100);  // Simulate work
                }
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            }
        }, "Producer");

        // Consumer thread (slower than producer)
        Thread consumer = new Thread(() -> {
            try {
                for (int i = 0; i < 8; i++) {
                    buffer.take();
                    Thread.sleep(300);  // Slower consumption
                }
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            }
        }, "Consumer");

        producer.start();
        consumer.start();

        producer.join();
        consumer.join();
        System.out.println("Done. Final buffer size: " + buffer.size());
    }
}
```

```java
/*
 * ════════════════════════════════════════════════════════════
 * IMPORTANT RULES FOR wait/notify:
 * ════════════════════════════════════════════════════════════
 *
 * 1. MUST hold the object's monitor (synchronized) when calling
 *    wait()/notify()/notifyAll() - otherwise IllegalMonitorStateException
 *
 * 2. ALWAYS use while loop for wait() condition check:
 *    while (!condition) { wait(); }
 *    NOT: if (!condition) { wait(); }  // BROKEN - spurious wakeups!
 *
 * 3. Prefer notifyAll() over notify():
 *    - notify() wakes only ONE thread (which one is undefined)
 *    - If wrong thread wakes up and can't proceed, deadlock possible
 *    - notifyAll() is safer but slightly less efficient
 *
 * 4. MODERN ALTERNATIVES (preferred in new code):
 *    - java.util.concurrent.locks.Condition (more flexible)
 *    - BlockingQueue (producer-consumer built-in)
 *    - CountDownLatch, CyclicBarrier, Semaphore
 *    - CompletableFuture (async programming)
 *
 * 5. wait() can specify timeout: wait(1000) // wait up to 1 second
 *
 * ════════════════════════════════════════════════════════════
 */
```

---

## Summary: Quick Reference

```java
/*
 * ════════════════════════════════════════════════════════════
 * QUICK REFERENCE TABLE
 * ════════════════════════════════════════════════════════════
 *
 * STATIC:
 * - static field: shared by all instances, class-level
 * - static method: no 'this', utility methods, factories
 * - static block: runs once when class loads, initialization
 * - static import: use without class prefix
 *
 * INNER CLASSES:
 * - Regular inner:  has outer ref, accesses outer's private, memory leak risk
 * - Static nested:  no outer ref, like top-level but namespaced, PREFER THIS
 * - Local inner:    inside method, accesses effectively final locals
 * - Anonymous:      inline impl, one-off use, replaced by lambdas
 *
 * ENUMS:
 * - Type-safe constants with behavior
 * - Can have fields, constructors, methods, implement interfaces
 * - Use EnumSet/EnumMap for collections of enums
 * - Best singleton implementation
 * - Great for state machines
 *
 * RECORDS (Java 14+):
 * - Immutable data carriers, auto-generated equals/hashCode/toString
 * - Compact constructors for validation
 * - Cannot extend classes, implicitly final
 *
 * SEALED CLASSES (Java 17+):
 * - Control inheritance hierarchy
 * - Enable exhaustive pattern matching
 * - Subclasses must be: final, sealed, or non-sealed
 *
 * OBJECT METHODS:
 * - equals/hashCode: always override together, use in HashMap/HashSet
 * - toString: debug/logging, override for meaningful output
 * - clone: prefer copy constructor, deep vs shallow
 * - getClass: runtime type info
 * - wait/notify: inter-thread communication (prefer java.util.concurrent)
 * - finalize: DEPRECATED - use AutoCloseable + try-with-resources
 *
 * ════════════════════════════════════════════════════════════
 */
```
