# Core OOP Principles in Java

## 1. Classes and Objects

### Class Definition and Object Creation

```java
public class Employee {
    // ═══════════════════════════════════════════════════════
    // INSTANCE MEMBERS - each object gets its own copy
    // ═══════════════════════════════════════════════════════
    private String name;
    private int id;
    private double salary;

    // ═══════════════════════════════════════════════════════
    // CLASS (STATIC) MEMBERS - shared across ALL instances
    // ═══════════════════════════════════════════════════════
    private static int employeeCount = 0;
    private static final String COMPANY = "TechCorp";

    // ═══════════════════════════════════════════════════════
    // CONSTRUCTORS
    // ═══════════════════════════════════════════════════════

    // No-arg constructor
    public Employee() {
        this("Unknown", 0.0);  // Constructor chaining using 'this'
    }

    // Parameterized constructor
    public Employee(String name, double salary) {
        this.name = name;           // 'this' distinguishes field from parameter
        this.salary = salary;
        this.id = ++employeeCount;  // Auto-assign ID
    }

    // Copy constructor
    public Employee(Employee other) {
        this(other.name, other.salary);
    }

    // ═══════════════════════════════════════════════════════
    // 'this' keyword uses:
    // 1. this.field    → refer to instance variable
    // 2. this(args)   → call another constructor (must be FIRST statement)
    // 3. return this   → for method chaining (Builder pattern)
    // ═══════════════════════════════════════════════════════

    public Employee withName(String name) {
        this.name = name;
        return this;  // Method chaining
    }

    public Employee withSalary(double salary) {
        this.salary = salary;
        return this;
    }

    // Static method - belongs to class, not instance
    public static int getEmployeeCount() {
        // Cannot use 'this' here - no instance context
        return employeeCount;
    }

    @Override
    public String toString() {
        return String.format("Employee[id=%d, name=%s, salary=%.2f, company=%s]",
                id, name, salary, COMPANY);
    }
}
```

### Object Lifecycle

```java
public class ObjectLifecycleDemo {
    public static void main(String[] args) {
        // 1. CREATION: Memory allocated on HEAP, constructor runs
        Employee emp = new Employee("Alice", 75000);

        // 2. USAGE: Object is reachable via reference 'emp'
        System.out.println(emp);

        // 3. Method chaining example
        Employee emp2 = new Employee()
                .withName("Bob")
                .withSalary(80000);

        // 4. ELIGIBLE FOR GC: When no references point to object
        emp = null;  // Original Employee("Alice",...) now eligible for GC

        // 5. GARBAGE COLLECTION: JVM reclaims memory (non-deterministic)
        System.gc();  // SUGGESTION only - JVM may ignore

        // Note: finalize() is deprecated since Java 9
        // Use try-with-resources or Cleaner API instead
    }
}
```

### Instance vs Class Members Summary

| Feature | Instance Members | Class (Static) Members |
|---------|-----------------|----------------------|
| Memory | Per object on heap | Once in method area |
| Access | Through object reference | Through class name |
| Can access | Both instance + static | Only static members |
| `this` reference | Available | NOT available |
| Use case | Object-specific state | Shared state, utilities |

---

## 2. Encapsulation

### Access Modifiers

| Modifier | Same Class | Same Package | Subclass (diff pkg) | World |
|----------|:----------:|:------------:|:-------------------:|:-----:|
| `private` | ✅ | ❌ | ❌ | ❌ |
| default (no modifier) | ✅ | ✅ | ❌ | ❌ |
| `protected` | ✅ | ✅ | ✅ | ❌ |
| `public` | ✅ | ✅ | ✅ | ✅ |

### Why Direct Field Access Is Bad

```java
// ❌ BAD: No encapsulation
public class BadAccount {
    public double balance;  // Anyone can set this to -9999!
    public String owner;
}

// Problems:
// 1. No validation - balance can be negative
// 2. No audit trail - who changed what?
// 3. Cannot change internal representation without breaking clients
// 4. Thread-unsafe - no synchronization possible
// 5. Cannot add behavior on access (lazy loading, caching)
```

### Complete Example: BankAccount with Proper Encapsulation

```java
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

public class BankAccount {
    // ═══════════════════════════════════════════════════════
    // ALL fields are PRIVATE - information hiding
    // ═══════════════════════════════════════════════════════
    private final String accountNumber;     // Immutable after creation
    private final String owner;
    private double balance;
    private boolean frozen;
    private final List<String> transactions;

    // ═══════════════════════════════════════════════════════
    // Constructor validates invariants
    // ═══════════════════════════════════════════════════════
    public BankAccount(String accountNumber, String owner, double initialDeposit) {
        if (accountNumber == null || accountNumber.isBlank()) {
            throw new IllegalArgumentException("Account number cannot be empty");
        }
        if (owner == null || owner.isBlank()) {
            throw new IllegalArgumentException("Owner cannot be empty");
        }
        if (initialDeposit < 0) {
            throw new IllegalArgumentException("Initial deposit cannot be negative");
        }
        this.accountNumber = accountNumber;
        this.owner = owner;
        this.balance = initialDeposit;
        this.frozen = false;
        this.transactions = new ArrayList<>();
        logTransaction("OPEN", initialDeposit);
    }

    // ═══════════════════════════════════════════════════════
    // GETTERS - controlled read access
    // ═══════════════════════════════════════════════════════

    public String getAccountNumber() {
        return accountNumber;
    }

    public String getOwner() {
        return owner;
    }

    public double getBalance() {
        return balance;
    }

    // Return UNMODIFIABLE view - protects internal list
    public List<String> getTransactions() {
        return Collections.unmodifiableList(transactions);
    }

    // ═══════════════════════════════════════════════════════
    // BUSINESS METHODS - encapsulate behavior + validation
    // ═══════════════════════════════════════════════════════

    public void deposit(double amount) {
        validateNotFrozen();
        if (amount <= 0) {
            throw new IllegalArgumentException("Deposit amount must be positive");
        }
        balance += amount;
        logTransaction("DEPOSIT", amount);
    }

    public void withdraw(double amount) {
        validateNotFrozen();
        if (amount <= 0) {
            throw new IllegalArgumentException("Withdrawal amount must be positive");
        }
        if (amount > balance) {
            throw new IllegalStateException("Insufficient funds. Balance: " + balance);
        }
        balance -= amount;
        logTransaction("WITHDRAW", -amount);
    }

    public void freeze() {
        this.frozen = true;
        logTransaction("FROZEN", 0);
    }

    // ═══════════════════════════════════════════════════════
    // PRIVATE helper methods - internal implementation details
    // ═══════════════════════════════════════════════════════

    private void validateNotFrozen() {
        if (frozen) {
            throw new IllegalStateException("Account is frozen");
        }
    }

    private void logTransaction(String type, double amount) {
        transactions.add(String.format("[%s] %s: %.2f | Balance: %.2f",
                LocalDateTime.now(), type, amount, balance));
    }

    @Override
    public String toString() {
        return String.format("BankAccount[%s, owner=%s, balance=%.2f, frozen=%b]",
                accountNumber, owner, balance, frozen);
    }
}
```

```java
// Usage demonstrating encapsulation benefits
public class EncapsulationDemo {
    public static void main(String[] args) {
        BankAccount account = new BankAccount("ACC-001", "Alice", 1000.0);

        account.deposit(500.0);
        account.withdraw(200.0);

        System.out.println(account);  // BankAccount[ACC-001, owner=Alice, balance=1300.00, frozen=false]
        System.out.println("Transactions: " + account.getTransactions());

        // account.balance = -9999;  ← COMPILE ERROR! Field is private
        // account.getTransactions().clear();  ← RUNTIME ERROR! Unmodifiable list

        // Encapsulation benefits demonstrated:
        // ✅ Validation on every state change
        // ✅ Audit trail (transactions logged)
        // ✅ Cannot set invalid state
        // ✅ Can add thread-safety later without changing API
        // ✅ Internal representation can change freely

        try {
            account.withdraw(99999);  // IllegalStateException: Insufficient funds
        } catch (IllegalStateException e) {
            System.out.println("Caught: " + e.getMessage());
        }

        account.freeze();
        try {
            account.deposit(100);  // IllegalStateException: Account is frozen
        } catch (IllegalStateException e) {
            System.out.println("Caught: " + e.getMessage());
        }
    }
}
```

---

## 3. Inheritance

### Basics: IS-A Relationship

```java
// ═══════════════════════════════════════════════════════
// BASE CLASS (Superclass/Parent)
// ═══════════════════════════════════════════════════════
public class Vehicle {
    private String make;
    private String model;
    private int year;
    private double fuelLevel;  // 0.0 to 1.0

    public Vehicle(String make, String model, int year) {
        this.make = make;
        this.model = model;
        this.year = year;
        this.fuelLevel = 1.0;  // Full tank
        System.out.println("Vehicle constructor called");
    }

    // Protected - accessible by subclasses
    protected void consumeFuel(double amount) {
        this.fuelLevel = Math.max(0, fuelLevel - amount);
    }

    public void start() {
        System.out.println(make + " " + model + " engine starting...");
    }

    public void drive(double km) {
        if (fuelLevel <= 0) {
            System.out.println("Cannot drive - no fuel!");
            return;
        }
        consumeFuel(km * 0.001);  // Base fuel consumption
        System.out.println("Driving " + km + " km. Fuel: " + String.format("%.1f%%", fuelLevel * 100));
    }

    // Final method - CANNOT be overridden by subclasses
    public final String getRegistrationInfo() {
        return year + " " + make + " " + model;
    }

    // Getters
    public String getMake() { return make; }
    public String getModel() { return model; }
    public int getYear() { return year; }
    public double getFuelLevel() { return fuelLevel; }

    protected void setFuelLevel(double level) {
        this.fuelLevel = Math.min(1.0, Math.max(0, level));
    }

    @Override
    public String toString() {
        return getRegistrationInfo();
    }
}
```

```java
// ═══════════════════════════════════════════════════════
// SUBCLASS (Child) - inherits from Vehicle
// Car IS-A Vehicle
// ═══════════════════════════════════════════════════════
public class Car extends Vehicle {
    private int numDoors;
    private boolean trunkOpen;

    public Car(String make, String model, int year, int numDoors) {
        // super() MUST be first statement in constructor
        // Calls parent constructor
        super(make, model, year);
        this.numDoors = numDoors;
        this.trunkOpen = false;
        System.out.println("Car constructor called");
    }

    // ═══════════════════════════════════════════════════════
    // METHOD OVERRIDING - provide specialized behavior
    // ═══════════════════════════════════════════════════════
    @Override  // Annotation - compile-time check that we're actually overriding
    public void start() {
        super.start();  // Call parent's implementation first
        System.out.println("Car systems check... Ready to drive.");
    }

    @Override
    public void drive(double km) {
        System.out.println("Car driving on road...");
        consumeFuel(km * 0.0008);  // Cars are more efficient than base
        System.out.printf("Drove %.1f km. Fuel: %.1f%%%n", km, getFuelLevel() * 100);
    }

    // New method specific to Car
    public void openTrunk() {
        trunkOpen = true;
        System.out.println("Trunk opened");
    }

    public int getNumDoors() { return numDoors; }
}
```

```java
// ═══════════════════════════════════════════════════════
// DEEPER INHERITANCE - ElectricCar IS-A Car IS-A Vehicle
// ═══════════════════════════════════════════════════════
public class ElectricCar extends Car {
    private double batteryCapacity;  // kWh
    private double chargeLevel;       // 0.0 to 1.0

    public ElectricCar(String make, String model, int year, double batteryCapacity) {
        super(make, model, year, 4);  // Electric cars typically have 4 doors
        this.batteryCapacity = batteryCapacity;
        this.chargeLevel = 1.0;
        System.out.println("ElectricCar constructor called");
    }

    @Override
    public void start() {
        // Electric cars don't have engines - completely replace parent behavior
        System.out.println(getMake() + " " + getModel() + " powering up silently...");
        System.out.println("Battery: " + String.format("%.0f%%", chargeLevel * 100));
    }

    @Override
    public void drive(double km) {
        if (chargeLevel <= 0) {
            System.out.println("Cannot drive - battery depleted!");
            return;
        }
        double consumption = km * 0.002;  // kWh per km approximation
        chargeLevel = Math.max(0, chargeLevel - consumption);
        System.out.printf("Silently drove %.1f km. Battery: %.0f%%%n", km, chargeLevel * 100);
    }

    // Covariant return type - can return more specific type than parent
    // (Shown conceptually - parent returns void here, see polymorphism section for real example)

    public void charge(double hours) {
        double chargeRate = 0.2;  // 20% per hour
        chargeLevel = Math.min(1.0, chargeLevel + hours * chargeRate);
        System.out.printf("Charged for %.1f hours. Battery: %.0f%%%n", hours, chargeLevel * 100);
    }

    public double getRange() {
        return chargeLevel * batteryCapacity * 5;  // Approximate range in km
    }
}
```

### Constructor Execution Order

```java
public class ConstructorOrderDemo {
    public static void main(String[] args) {
        System.out.println("Creating ElectricCar...");
        ElectricCar tesla = new ElectricCar("Tesla", "Model 3", 2024, 75.0);
        // Output:
        // Creating ElectricCar...
        // Vehicle constructor called       ← Grandparent FIRST
        // Car constructor called           ← Parent SECOND
        // ElectricCar constructor called   ← Child LAST

        System.out.println("\n--- Driving ---");
        tesla.start();
        tesla.drive(50);
        tesla.charge(2);
        System.out.println("Range: " + tesla.getRange() + " km");
    }
}
```

### Why No Multiple Class Inheritance in Java

```java
// Java does NOT allow:
// class Child extends Parent1, Parent2 { }  ← COMPILE ERROR

// REASON: Diamond Problem
// If Parent1 and Parent2 both have method foo(),
// which one does Child inherit?

// SOLUTION: Java uses interfaces for multiple inheritance of TYPE
// class Child extends Parent1 implements Interface1, Interface2 { }
// Interfaces provide the contract, single parent provides implementation
```

### Method Overriding Rules

```java
public class OverridingRules {
    /*
     * Rules for valid method override:
     *
     * 1. Same method signature (name + parameter types)
     * 2. Return type must be same OR covariant (subtype)
     * 3. Access modifier must be SAME or LESS restrictive
     *    - parent: protected → child can be: protected or public
     *    - parent: public → child MUST be: public
     * 4. Cannot throw BROADER checked exceptions than parent
     * 5. Cannot override: final, static, or private methods
     * 6. static methods are HIDDEN, not overridden
     */
}

class Animal {
    protected Animal create() {        // Returns Animal
        return new Animal();
    }

    public void makeSound() {
        System.out.println("...");
    }
}

class Dog extends Animal {
    @Override
    protected Dog create() {           // ✅ Covariant return: Dog IS-A Animal
        return new Dog();
    }

    @Override
    public void makeSound() {          // ✅ public is less restrictive than protected
        System.out.println("Woof!");
    }

    // @Override
    // private void makeSound() { }    // ❌ COMPILE ERROR: more restrictive
}
```

### Final Class and Final Method

```java
// Final class - CANNOT be extended
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

// class ExtendedPoint extends ImmutablePoint { }  ← COMPILE ERROR!

// Why use final class?
// 1. Security - prevent malicious subclassing (e.g., String is final)
// 2. Immutability guarantee - no subclass can add mutable state
// 3. Performance - JVM can inline final methods
```

---

## 4. Polymorphism

### Compile-Time Polymorphism (Method Overloading)

```java
public class Calculator {
    // ═══════════════════════════════════════════════════════
    // METHOD OVERLOADING - same name, different parameters
    // Resolved at COMPILE TIME based on declared types
    // ═══════════════════════════════════════════════════════

    // Different number of parameters
    public int add(int a, int b) {
        System.out.println("add(int, int)");
        return a + b;
    }

    public int add(int a, int b, int c) {
        System.out.println("add(int, int, int)");
        return a + b + c;
    }

    // Different parameter types
    public double add(double a, double b) {
        System.out.println("add(double, double)");
        return a + b;
    }

    // Varargs - must be LAST parameter
    public int add(int... numbers) {
        System.out.println("add(int...)");
        int sum = 0;
        for (int n : numbers) sum += n;
        return sum;
    }

    // ═══════════════════════════════════════════════════════
    // OVERLOADING RESOLUTION RULES (priority order):
    // 1. Exact match
    // 2. Widening primitive (int → long → float → double)
    // 3. Autoboxing (int → Integer)
    // 4. Varargs (least priority)
    // ═══════════════════════════════════════════════════════

    public void process(int x) {
        System.out.println("process(int): " + x);
    }

    public void process(long x) {
        System.out.println("process(long): " + x);
    }

    public void process(Integer x) {
        System.out.println("process(Integer): " + x);
    }

    public void process(int... x) {
        System.out.println("process(int...): " + java.util.Arrays.toString(x));
    }

    // NOTE: Cannot overload by return type alone!
    // public double add(int a, int b) { }  ← COMPILE ERROR: already defined
}

class OverloadingDemo {
    public static void main(String[] args) {
        Calculator calc = new Calculator();

        calc.add(1, 2);           // → add(int, int) - exact match
        calc.add(1, 2, 3);       // → add(int, int, int) - exact match
        calc.add(1.0, 2.0);     // → add(double, double) - exact match
        calc.add(1, 2, 3, 4);   // → add(int...) - varargs

        System.out.println("\n--- Resolution Priority ---");
        calc.process(5);          // → process(int) - exact match
        calc.process(5L);         // → process(long) - exact match for long
        // calc.process(5) tries: int(exact) → long(widening) → Integer(boxing) → int...(varargs)
    }
}
```

### Runtime Polymorphism (Dynamic Dispatch)

```java
// ═══════════════════════════════════════════════════════
// RUNTIME POLYMORPHISM - resolved at runtime via vtable
// The JVM looks at the ACTUAL object type, not reference type
// ═══════════════════════════════════════════════════════

abstract class Shape {
    private String color;

    public Shape(String color) {
        this.color = color;
    }

    // Abstract method - forces subclasses to provide implementation
    public abstract double area();
    public abstract double perimeter();

    // Concrete method using abstract methods (Template pattern)
    public void printInfo() {
        System.out.printf("%s %s - Area: %.2f, Perimeter: %.2f%n",
                color, getClass().getSimpleName(), area(), perimeter());
    }

    public String getColor() { return color; }
}

class Circle extends Shape {
    private double radius;

    public Circle(String color, double radius) {
        super(color);
        this.radius = radius;
    }

    @Override
    public double area() {
        return Math.PI * radius * radius;
    }

    @Override
    public double perimeter() {
        return 2 * Math.PI * radius;
    }
}

class Rectangle extends Shape {
    private double width, height;

    public Rectangle(String color, double width, double height) {
        super(color);
        this.width = width;
        this.height = height;
    }

    @Override
    public double area() {
        return width * height;
    }

    @Override
    public double perimeter() {
        return 2 * (width + height);
    }
}

class Triangle extends Shape {
    private double a, b, c;  // sides

    public Triangle(String color, double a, double b, double c) {
        super(color);
        this.a = a; this.b = b; this.c = c;
    }

    @Override
    public double area() {
        double s = (a + b + c) / 2;  // Heron's formula
        return Math.sqrt(s * (s - a) * (s - b) * (s - c));
    }

    @Override
    public double perimeter() {
        return a + b + c;
    }
}
```

### Upcasting and Downcasting

```java
public class CastingDemo {
    public static void main(String[] args) {
        // ═══════════════════════════════════════════════════════
        // UPCASTING - always safe, implicit
        // Reference type: Shape, Actual object: Circle
        // ═══════════════════════════════════════════════════════
        Shape shape1 = new Circle("Red", 5.0);      // Implicit upcast
        Shape shape2 = new Rectangle("Blue", 3, 4);
        Shape shape3 = new Triangle("Green", 3, 4, 5);

        // Dynamic dispatch - JVM calls the ACTUAL object's method
        // Even though reference type is Shape, Circle.area() is called
        shape1.printInfo();  // Red Circle - Area: 78.54, Perimeter: 31.42
        shape2.printInfo();  // Blue Rectangle - Area: 12.00, Perimeter: 14.00
        shape3.printInfo();  // Green Triangle - Area: 6.00, Perimeter: 12.00

        // Polymorphic collection - different types, same interface
        Shape[] shapes = {shape1, shape2, shape3};
        double totalArea = 0;
        for (Shape s : shapes) {
            totalArea += s.area();  // Each calls its OWN implementation
        }
        System.out.println("Total area: " + totalArea);

        // ═══════════════════════════════════════════════════════
        // DOWNCASTING - potentially unsafe, must be explicit
        // Need to check with instanceof first
        // ═══════════════════════════════════════════════════════

        // Unsafe downcast - compiles but crashes at runtime
        // Circle c = (Circle) shape2;  // ClassCastException! shape2 is Rectangle

        // Safe downcast with instanceof check
        if (shape1 instanceof Circle) {
            Circle circle = (Circle) shape1;  // Now safe
            System.out.println("Circle area: " + circle.area());
        }

        // ═══════════════════════════════════════════════════════
        // PATTERN MATCHING instanceof (Java 16+)
        // Combines check + cast in one expression
        // ═══════════════════════════════════════════════════════
        if (shape1 instanceof Circle c) {   // 'c' is automatically cast
            System.out.println("Radius gives area: " + c.area());
        }

        // Switch pattern matching (Java 21+)
        for (Shape s : shapes) {
            String desc = switch (s) {
                case Circle c    -> "Circle with area " + c.area();
                case Rectangle r -> "Rectangle with area " + r.area();
                case Triangle t  -> "Triangle with area " + t.area();
                default          -> "Unknown shape";
            };
            System.out.println(desc);
        }
    }
}
```

### How Dynamic Dispatch Works (Vtable)

```java
/*
 * VIRTUAL METHOD TABLE (vtable) - conceptual view
 *
 * When JVM loads a class, it builds a vtable for that class.
 * Each entry points to the MOST SPECIFIC implementation.
 *
 * Shape vtable:
 * ┌─────────────┬────────────────────────┐
 * │ area()      │ → Shape.area() [abstract] │
 * │ perimeter() │ → Shape.perimeter() [abstract] │
 * │ printInfo() │ → Shape.printInfo()    │
 * │ toString()  │ → Object.toString()    │
 * └─────────────┴────────────────────────┘
 *
 * Circle vtable:
 * ┌─────────────┬────────────────────────┐
 * │ area()      │ → Circle.area()        │  ← overridden
 * │ perimeter() │ → Circle.perimeter()   │  ← overridden
 * │ printInfo() │ → Shape.printInfo()    │  ← inherited
 * │ toString()  │ → Object.toString()    │  ← inherited
 * └─────────────┴────────────────────────┘
 *
 * At runtime:
 *   Shape s = new Circle("Red", 5);
 *   s.area();
 *   // JVM looks at actual object type → Circle
 *   // Finds Circle's vtable → area() points to Circle.area()
 *   // Calls Circle.area()
 */
```

---

## 5. Abstraction

### Abstract Classes vs Interfaces

| Feature | Abstract Class | Interface |
|---------|---------------|-----------|
| Instantiation | Cannot instantiate | Cannot instantiate |
| Constructors | Yes | No |
| Fields | Any (instance + static) | Only `public static final` |
| Methods | Abstract + concrete | Abstract + default + static + private |
| Inheritance | `extends` (single) | `implements` (multiple) |
| Access modifiers | Any | Methods: public (default) |
| Use when | Shared state + partial implementation | Pure contract, multiple inheritance |

### When to Use Which

```java
/*
 * USE ABSTRACT CLASS when:
 * - Subclasses share common STATE (fields)
 * - You want to provide a partial implementation
 * - You need constructors for initialization
 * - You want to enforce initialization logic
 * - Related classes in an IS-A hierarchy
 *
 * USE INTERFACE when:
 * - Defining a CONTRACT/capability (CAN-DO)
 * - Multiple unrelated classes need same behavior
 * - You want multiple inheritance of type
 * - API design for decoupling
 * - Functional programming (single abstract method)
 */
```

### Complete Example: Payment System Abstraction

```java
import java.time.LocalDateTime;
import java.util.UUID;

// ═══════════════════════════════════════════════════════
// ABSTRACT CLASS - provides shared state and template
// ═══════════════════════════════════════════════════════
public abstract class Payment {
    private final String transactionId;
    private final double amount;
    private final LocalDateTime timestamp;
    private PaymentStatus status;

    // Constructor - enforces all payments have these fields
    protected Payment(double amount) {
        if (amount <= 0) {
            throw new IllegalArgumentException("Amount must be positive");
        }
        this.transactionId = UUID.randomUUID().toString();
        this.amount = amount;
        this.timestamp = LocalDateTime.now();
        this.status = PaymentStatus.PENDING;
    }

    // ═══════════════════════════════════════════════════════
    // TEMPLATE METHOD PATTERN
    // Defines the skeleton of the algorithm
    // Subclasses fill in the specific steps
    // ═══════════════════════════════════════════════════════
    public final boolean processPayment() {
        System.out.println("Processing " + getPaymentType() + " payment: $" + amount);

        // Step 1: Validate (each payment type validates differently)
        if (!validate()) {
            this.status = PaymentStatus.FAILED;
            System.out.println("Validation failed!");
            return false;
        }

        // Step 2: Execute the payment (abstract - each type implements)
        boolean success = executePayment();

        // Step 3: Update status
        this.status = success ? PaymentStatus.COMPLETED : PaymentStatus.FAILED;

        // Step 4: Send notification (hook - optional override)
        sendNotification();

        System.out.println("Payment " + status + ": " + transactionId);
        return success;
    }

    // Abstract methods - MUST be implemented by subclasses
    protected abstract boolean validate();
    protected abstract boolean executePayment();
    protected abstract String getPaymentType();

    // Hook method - CAN be overridden, but has default behavior
    protected void sendNotification() {
        System.out.println("Email notification sent for transaction " + transactionId);
    }

    // Concrete methods - shared by all subclasses
    public String getTransactionId() { return transactionId; }
    public double getAmount() { return amount; }
    public PaymentStatus getStatus() { return status; }
    public LocalDateTime getTimestamp() { return timestamp; }
}

enum PaymentStatus {
    PENDING, COMPLETED, FAILED, REFUNDED
}
```

```java
// ═══════════════════════════════════════════════════════
// CONCRETE IMPLEMENTATIONS
// ═══════════════════════════════════════════════════════

class CreditCardPayment extends Payment {
    private final String cardNumber;
    private final String cvv;
    private final String expiryDate;

    public CreditCardPayment(double amount, String cardNumber, String cvv, String expiryDate) {
        super(amount);  // Call abstract class constructor
        this.cardNumber = cardNumber;
        this.cvv = cvv;
        this.expiryDate = expiryDate;
    }

    @Override
    protected boolean validate() {
        // Luhn algorithm check (simplified)
        boolean validNumber = cardNumber != null && cardNumber.length() == 16;
        boolean validCvv = cvv != null && cvv.length() == 3;
        System.out.println("Validating credit card...");
        return validNumber && validCvv;
    }

    @Override
    protected boolean executePayment() {
        System.out.println("Charging credit card ending in " +
                cardNumber.substring(cardNumber.length() - 4));
        // In real app: call payment gateway API
        return true;
    }

    @Override
    protected String getPaymentType() {
        return "Credit Card";
    }
}

class PayPalPayment extends Payment {
    private final String email;

    public PayPalPayment(double amount, String email) {
        super(amount);
        this.email = email;
    }

    @Override
    protected boolean validate() {
        System.out.println("Validating PayPal account...");
        return email != null && email.contains("@");
    }

    @Override
    protected boolean executePayment() {
        System.out.println("Processing PayPal payment for " + email);
        return true;
    }

    @Override
    protected String getPaymentType() {
        return "PayPal";
    }

    @Override
    protected void sendNotification() {
        // Override hook - PayPal sends its own notifications
        System.out.println("PayPal notification sent to " + email);
    }
}

class CryptoPayment extends Payment {
    private final String walletAddress;
    private final String cryptocurrency;

    public CryptoPayment(double amount, String walletAddress, String cryptocurrency) {
        super(amount);
        this.walletAddress = walletAddress;
        this.cryptocurrency = cryptocurrency;
    }

    @Override
    protected boolean validate() {
        System.out.println("Validating " + cryptocurrency + " wallet...");
        return walletAddress != null && walletAddress.length() >= 26;
    }

    @Override
    protected boolean executePayment() {
        System.out.println("Sending " + getAmount() + " USD worth of " +
                cryptocurrency + " to " + walletAddress);
        return true;
    }

    @Override
    protected String getPaymentType() {
        return "Cryptocurrency (" + cryptocurrency + ")";
    }
}
```

```java
// ═══════════════════════════════════════════════════════
// USAGE - polymorphism + abstraction working together
// ═══════════════════════════════════════════════════════
public class PaymentDemo {
    public static void main(String[] args) {
        // Polymorphic reference - code works with ANY payment type
        Payment[] payments = {
            new CreditCardPayment(99.99, "4532015112830366", "123", "12/25"),
            new PayPalPayment(49.99, "user@example.com"),
            new CryptoPayment(199.99, "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa", "BTC")
        };

        for (Payment payment : payments) {
            System.out.println("\n" + "═".repeat(50));
            payment.processPayment();  // Template method - same flow, different details
        }
    }
}
```

---

## 6. Interfaces

### Complete Interface Features (Java 8 through Java 17+)

```java
// ═══════════════════════════════════════════════════════
// INTERFACE DEFINITION - complete feature showcase
// ═══════════════════════════════════════════════════════

public interface Sortable<T> {
    // ─────────────────────────────────────────────────────
    // CONSTANTS - implicitly public static final
    // ─────────────────────────────────────────────────────
    int MAX_ELEMENTS = 1_000_000;  // public static final (implicit)

    // ─────────────────────────────────────────────────────
    // ABSTRACT METHODS - implicitly public abstract
    // ─────────────────────────────────────────────────────
    int compareTo(T other);

    // ─────────────────────────────────────────────────────
    // DEFAULT METHODS (Java 8+)
    // Provide implementation that classes inherit
    // Can be overridden by implementing classes
    // ─────────────────────────────────────────────────────
    default boolean isGreaterThan(T other) {
        return compareTo(other) > 0;
    }

    default boolean isLessThan(T other) {
        return compareTo(other) < 0;
    }

    default boolean isEqualTo(T other) {
        return compareTo(other) == 0;
    }

    // ─────────────────────────────────────────────────────
    // STATIC METHODS (Java 8+)
    // Belong to interface, not implementing class
    // Cannot be overridden
    // ─────────────────────────────────────────────────────
    static <T extends Comparable<T>> T max(T a, T b) {
        return a.compareTo(b) >= 0 ? a : b;
    }

    // ─────────────────────────────────────────────────────
    // PRIVATE METHODS (Java 9+)
    // Helper methods for default methods
    // Avoid code duplication within the interface
    // ─────────────────────────────────────────────────────
    private void validateNotNull(T other) {
        if (other == null) {
            throw new NullPointerException("Cannot compare to null");
        }
    }
}
```

### Functional Interfaces

```java
// ═══════════════════════════════════════════════════════
// FUNCTIONAL INTERFACE - exactly ONE abstract method
// Can be implemented with lambda expressions
// ═══════════════════════════════════════════════════════

@FunctionalInterface  // Compiler enforces single abstract method
public interface Transformer<T, R> {
    R transform(T input);  // The single abstract method

    // Default methods don't count against the "single abstract method" rule
    default <V> Transformer<T, V> andThen(Transformer<R, V> after) {
        return input -> after.transform(this.transform(input));
    }

    // Static factory methods
    static <T> Transformer<T, T> identity() {
        return input -> input;
    }
}

class FunctionalInterfaceDemo {
    public static void main(String[] args) {
        // Lambda implements the single abstract method
        Transformer<String, Integer> stringLength = s -> s.length();
        Transformer<Integer, String> intToString = i -> "Length: " + i;

        // Compose transformers
        Transformer<String, String> combined = stringLength.andThen(intToString);

        System.out.println(combined.transform("Hello"));  // "Length: 5"

        // Method reference - shorthand for lambda
        Transformer<String, Integer> parser = Integer::parseInt;
        System.out.println(parser.transform("42"));  // 42
    }
}
```

### Multiple Interface Inheritance and Diamond Problem

```java
// ═══════════════════════════════════════════════════════
// DIAMOND PROBLEM RESOLUTION
// ═══════════════════════════════════════════════════════

interface Flyable {
    default String describe() {
        return "I can fly";
    }

    void fly();
}

interface Swimmable {
    default String describe() {
        return "I can swim";
    }

    void swim();
}

interface Runnable {
    default String describe() {
        return "I can run";
    }

    void run();
}

// Duck implements ALL three - must resolve diamond for describe()
class Duck implements Flyable, Swimmable, Runnable {

    @Override
    public void fly() { System.out.println("Duck flying"); }

    @Override
    public void swim() { System.out.println("Duck swimming"); }

    @Override
    public void run() { System.out.println("Duck running"); }

    // ═══════════════════════════════════════════════════════
    // MUST override describe() because multiple interfaces
    // provide conflicting default implementations
    // COMPILE ERROR if not resolved!
    // ═══════════════════════════════════════════════════════
    @Override
    public String describe() {
        // Can call specific interface's default method using:
        // InterfaceName.super.methodName()
        return Flyable.super.describe() + ", " +
               Swimmable.super.describe() + ", " +
               Runnable.super.describe();
    }
}

class DiamondDemo {
    public static void main(String[] args) {
        Duck duck = new Duck();
        System.out.println(duck.describe());
        // Output: I can fly, I can swim, I can run

        // Multiple interface types
        Flyable f = duck;
        Swimmable s = duck;
        f.fly();
        s.swim();
    }
}
```

### Strategy Pattern with Interfaces

```java
// ═══════════════════════════════════════════════════════
// STRATEGY PATTERN - define family of algorithms
// Each algorithm is encapsulated in its own class
// Client can switch algorithms at runtime
// ═══════════════════════════════════════════════════════

// Strategy interface
@FunctionalInterface
interface CompressionStrategy {
    byte[] compress(byte[] data);

    // Default decompression (strategies can override)
    default byte[] decompress(byte[] compressed) {
        throw new UnsupportedOperationException("Decompression not implemented");
    }
}

// Strategy interface for output
@FunctionalInterface
interface OutputStrategy {
    void write(String filename, byte[] data);
}

// Concrete strategies
class ZipCompression implements CompressionStrategy {
    @Override
    public byte[] compress(byte[] data) {
        System.out.println("Compressing with ZIP algorithm...");
        // Simulated compression
        return data;  // In reality, would use java.util.zip
    }
}

class GzipCompression implements CompressionStrategy {
    @Override
    public byte[] compress(byte[] data) {
        System.out.println("Compressing with GZIP algorithm...");
        return data;
    }
}

class RarCompression implements CompressionStrategy {
    @Override
    public byte[] compress(byte[] data) {
        System.out.println("Compressing with RAR algorithm...");
        return data;
    }
}

// Context class - uses strategies
class FileArchiver {
    private CompressionStrategy compressionStrategy;
    private OutputStrategy outputStrategy;

    public FileArchiver(CompressionStrategy compression, OutputStrategy output) {
        this.compressionStrategy = compression;
        this.outputStrategy = output;
    }

    // Strategies can be changed at runtime!
    public void setCompressionStrategy(CompressionStrategy strategy) {
        this.compressionStrategy = strategy;
    }

    public void setOutputStrategy(OutputStrategy strategy) {
        this.outputStrategy = strategy;
    }

    public void archiveFile(String filename, byte[] data) {
        byte[] compressed = compressionStrategy.compress(data);
        outputStrategy.write(filename, compressed);
    }
}

class StrategyPatternDemo {
    public static void main(String[] args) {
        // Using class implementations
        FileArchiver archiver = new FileArchiver(
            new ZipCompression(),
            (filename, data) -> System.out.println("Writing to disk: " + filename)
        );

        byte[] testData = "Hello, World!".getBytes();
        archiver.archiveFile("test.zip", testData);

        // Switch strategy at runtime
        archiver.setCompressionStrategy(new GzipCompression());
        archiver.archiveFile("test.gz", testData);

        // Lambda as strategy (since it's a functional interface)
        archiver.setCompressionStrategy(data -> {
            System.out.println("Custom compression: no-op passthrough");
            return data;
        });
        archiver.archiveFile("test.raw", testData);

        // Different output strategies via lambdas
        archiver.setOutputStrategy((filename, data) ->
            System.out.println("Uploading to cloud: " + filename + " (" + data.length + " bytes)"));
        archiver.archiveFile("test.cloud", testData);
    }
}
```

### Marker Interfaces

```java
import java.io.Serializable;
import java.io.Cloneable;

// ═══════════════════════════════════════════════════════
// MARKER INTERFACES - no methods, just "mark" a class
// as having a certain capability
// ═══════════════════════════════════════════════════════

// Serializable - marks class as safe to serialize to byte stream
// Cloneable - marks class as safe to clone via Object.clone()

class Product implements Serializable, Cloneable {
    private static final long serialVersionUID = 1L;  // Version for serialization

    private String name;
    private double price;
    private transient String temporaryData;  // 'transient' = not serialized

    public Product(String name, double price) {
        this.name = name;
        this.price = price;
    }

    @Override
    public Product clone() {
        try {
            return (Product) super.clone();  // Shallow copy
        } catch (CloneNotSupportedException e) {
            throw new AssertionError("Should not happen - we implement Cloneable");
        }
    }

    @Override
    public String toString() {
        return "Product[" + name + ", $" + price + "]";
    }
}

// Custom marker interface
interface Auditable {
    // No methods - just marks classes that should be audited
}

// Usage
class AuditedPayment extends CreditCardPayment implements Auditable {
    public AuditedPayment(double amount, String card, String cvv, String expiry) {
        super(amount, card, cvv, expiry);
    }
}

class MarkerDemo {
    // Can check at runtime if object has marker
    public static void processEntity(Object entity) {
        if (entity instanceof Auditable) {
            System.out.println("AUDIT LOG: Processing auditable entity");
        }
        if (entity instanceof Serializable) {
            System.out.println("Entity can be serialized for storage");
        }
    }
}
```

### Interface Evolution - Java 8, 9, and Beyond

```java
// ═══════════════════════════════════════════════════════
// EVOLVING AN INTERFACE WITHOUT BREAKING EXISTING CODE
// ═══════════════════════════════════════════════════════

// Original interface (pre-Java 8 style)
interface Logger {
    // Abstract methods - must be implemented
    void log(String message);
    void log(String level, String message);

    // ─── Java 8: Default methods ───────────────────────
    // Added WITHOUT breaking existing implementations
    default void info(String message) {
        log("INFO", message);
    }

    default void warn(String message) {
        log("WARN", message);
    }

    default void error(String message) {
        log("ERROR", message);
    }

    default void error(String message, Throwable t) {
        log("ERROR", message + " | Exception: " + t.getMessage());
    }

    // ─── Java 8: Static methods ───────────────────────
    // Factory method on the interface itself
    static Logger console() {
        return new Logger() {
            @Override
            public void log(String message) {
                System.out.println("[LOG] " + message);
            }

            @Override
            public void log(String level, String message) {
                System.out.printf("[%s] %s%n", level, message);
            }
        };
    }

    static Logger nullLogger() {
        return new Logger() {
            @Override public void log(String message) { }
            @Override public void log(String level, String message) { }
        };
    }

    // ─── Java 9: Private methods ───────────────────────
    // Shared helper logic for default methods
    private String formatMessage(String level, String message) {
        return String.format("[%s][%tF %<tT] %s",
                level, java.time.LocalDateTime.now(), message);
    }

    // Private method used by multiple default methods
    private void logFormatted(String level, String message) {
        log(level, formatMessage(level, message));
    }
}

// Existing implementation - UNAFFECTED by new default methods
class FileLogger implements Logger {
    private final String filename;

    public FileLogger(String filename) {
        this.filename = filename;
    }

    @Override
    public void log(String message) {
        log("INFO", message);
    }

    @Override
    public void log(String level, String message) {
        // In reality: write to file
        System.out.println("[FILE:" + filename + "] " + level + ": " + message);
    }

    // Can override default methods if needed
    @Override
    public void error(String message, Throwable t) {
        log("ERROR", message);
        // Also log stack trace to file
        System.out.println("[FILE:" + filename + "] Stack trace: " + t);
    }
}

class InterfaceEvolutionDemo {
    public static void main(String[] args) {
        // Use static factory
        Logger logger = Logger.console();
        logger.info("Application started");
        logger.warn("Low memory");
        logger.error("Connection failed", new RuntimeException("Timeout"));

        // Use implementation
        Logger fileLogger = new FileLogger("app.log");
        fileLogger.info("Saved to file");
    }
}
```

---

## Summary: OOP Principles Working Together

```java
/*
 * ════════════════════════════════════════════════════════════
 *  HOW OOP PRINCIPLES INTERCONNECT
 * ════════════════════════════════════════════════════════════
 *
 *  ENCAPSULATION → Hides complexity, protects state
 *       ↓
 *  ABSTRACTION → Exposes only what matters (interface/abstract class)
 *       ↓
 *  INHERITANCE → Reuses and extends behavior
 *       ↓
 *  POLYMORPHISM → Enables flexibility and extensibility
 *
 * ════════════════════════════════════════════════════════════
 *  DESIGN PRINCIPLES (SOLID):
 *
 *  S - Single Responsibility: Each class has ONE reason to change
 *  O - Open/Closed: Open for extension, closed for modification
 *  L - Liskov Substitution: Subtypes must be substitutable for base types
 *  I - Interface Segregation: Many specific interfaces > one general
 *  D - Dependency Inversion: Depend on abstractions, not concretions
 *
 * ════════════════════════════════════════════════════════════
 *  KEY INTERVIEW ANSWERS:
 *
 *  Q: "Overloading vs Overriding?"
 *  A: Overloading = same name, diff params, compile-time, same class
 *     Overriding = same signature, runtime, parent-child, dynamic dispatch
 *
 *  Q: "Abstract class vs Interface?"
 *  A: Abstract class = IS-A + shared state + partial impl
 *     Interface = CAN-DO + contract + multiple inheritance
 *
 *  Q: "Why composition over inheritance?"
 *  A: Inheritance creates tight coupling, limits to single parent,
 *     breaks encapsulation. Composition is flexible, testable, changeable.
 *
 *  Q: "How does polymorphism work internally?"
 *  A: vtable (virtual method table) per class. Each entry points to
 *     most specific implementation. JVM resolves at runtime by looking
 *     at actual object type, not reference type.
 * ════════════════════════════════════════════════════════════
 */
```
