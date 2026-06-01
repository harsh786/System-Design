import java.util.*;

/**
 * Comprehensive demonstration of all 4 OOP Pillars:
 * 1. Encapsulation
 * 2. Abstraction
 * 3. Inheritance
 * 4. Polymorphism
 */
public class OOPSPrinciples {

    // ==================== ENCAPSULATION ====================

    /**
     * BankAccount: Private fields with controlled access.
     * Internal implementation hidden from outside world.
     */
    static class BankAccount {
        private String accountNumber;
        private double balance;
        private List<String> transactionHistory;

        public BankAccount(String accountNumber, double initialBalance) {
            this.accountNumber = accountNumber;
            this.balance = Math.max(0, initialBalance);
            this.transactionHistory = new ArrayList<>();
            transactionHistory.add("Account opened with balance: " + this.balance);
        }

        public double getBalance() {
            return balance;
        }

        // Validation: cannot set negative balance directly
        public void deposit(double amount) {
            if (amount <= 0) {
                System.out.println("  [ERROR] Deposit amount must be positive");
                return;
            }
            balance += amount;
            transactionHistory.add("Deposited: " + amount);
        }

        public boolean withdraw(double amount) {
            if (amount <= 0) {
                System.out.println("  [ERROR] Withdrawal amount must be positive");
                return false;
            }
            if (amount > balance) {
                System.out.println("  [ERROR] Insufficient funds");
                return false;
            }
            balance -= amount;
            transactionHistory.add("Withdrew: " + amount);
            return true;
        }

        // Masked account number - internal representation hidden
        public String getAccountNumber() {
            return "****" + accountNumber.substring(accountNumber.length() - 4);
        }

        public List<String> getTransactionHistory() {
            return Collections.unmodifiableList(transactionHistory);
        }
    }

    /**
     * UserProfile: Password hashing hidden internally.
     */
    static class UserProfile {
        private String username;
        private String hashedPassword; // Never expose raw password
        private String email;

        public UserProfile(String username, String password, String email) {
            this.username = username;
            this.hashedPassword = hashPassword(password); // Hashing hidden
            this.email = email;
        }

        // Internal implementation - could change algorithm without affecting callers
        private String hashPassword(String password) {
            // Simplified hash for demo (real: bcrypt/argon2)
            return "HASH[" + password.hashCode() + "]";
        }

        public boolean authenticate(String password) {
            return hashedPassword.equals(hashPassword(password));
        }

        public void setEmail(String email) {
            if (email == null || !email.contains("@")) {
                throw new IllegalArgumentException("Invalid email");
            }
            this.email = email;
        }

        public String getUsername() { return username; }
        public String getEmail() { return email; }
        // Note: NO getHashedPassword() - intentionally hidden
    }

    // ==================== ABSTRACTION ====================

    /**
     * Abstract class Vehicle: Defines contract with partial implementation.
     */
    static abstract class Vehicle {
        protected String brand;
        protected boolean isRunning;

        public Vehicle(String brand) {
            this.brand = brand;
            this.isRunning = false;
        }

        // Abstract methods - subclasses MUST implement
        abstract void start();
        abstract void stop();
        abstract void accelerate(int speed);

        // Concrete method - shared by all vehicles
        public String getStatus() {
            return brand + " is " + (isRunning ? "running" : "stopped");
        }
    }

    static class Car extends Vehicle {
        public Car(String brand) { super(brand); }

        void start() {
            isRunning = true;
            System.out.println("  " + brand + " car: Turn key, engine starts");
        }
        void stop() {
            isRunning = false;
            System.out.println("  " + brand + " car: Engine off");
        }
        void accelerate(int speed) {
            System.out.println("  " + brand + " car: Pressing gas pedal to " + speed + " km/h");
        }
    }

    static class ElectricScooter extends Vehicle {
        public ElectricScooter(String brand) { super(brand); }

        void start() {
            isRunning = true;
            System.out.println("  " + brand + " scooter: Press power button, motor hums");
        }
        void stop() {
            isRunning = false;
            System.out.println("  " + brand + " scooter: Motor off");
        }
        void accelerate(int speed) {
            System.out.println("  " + brand + " scooter: Twist throttle to " + speed + " km/h");
        }
    }

    /**
     * Interface PaymentGateway: Hides complex payment processing.
     */
    interface PaymentGateway {
        boolean processPayment(double amount, String currency);
        String getTransactionId();
    }

    static class StripeGateway implements PaymentGateway {
        private String lastTxnId;

        public boolean processPayment(double amount, String currency) {
            // Hides: API calls, tokenization, fraud checks, retry logic
            System.out.println("  [Stripe] Processing " + currency + " " + amount);
            System.out.println("  [Stripe] Tokenizing card... Fraud check... Charging...");
            lastTxnId = "stripe_" + System.nanoTime();
            return true;
        }

        public String getTransactionId() { return lastTxnId; }
    }

    static class PayPalGateway implements PaymentGateway {
        private String lastTxnId;

        public boolean processPayment(double amount, String currency) {
            System.out.println("  [PayPal] Processing " + currency + " " + amount);
            System.out.println("  [PayPal] OAuth... Redirect... Confirm... Capture...");
            lastTxnId = "paypal_" + System.nanoTime();
            return true;
        }

        public String getTransactionId() { return lastTxnId; }
    }

    /**
     * EmailService: Hides SMTP complexity.
     */
    static class EmailService {
        // Simple public interface
        public void sendEmail(String to, String subject, String body) {
            validateEmail(to);
            String formatted = formatMessage(subject, body);
            connectToSmtp();
            transmit(to, formatted);
            disconnect();
            System.out.println("  Email sent to " + to + " successfully!");
        }

        // All complexity hidden below
        private void validateEmail(String email) { /* validate format */ }
        private String formatMessage(String subject, String body) {
            return "Subject: " + subject + "\n\n" + body;
        }
        private void connectToSmtp() { /* TLS handshake, auth */ }
        private void transmit(String to, String msg) { /* SMTP protocol */ }
        private void disconnect() { /* cleanup */ }
    }

    // ==================== INHERITANCE ====================

    /**
     * Shape hierarchy demonstrating is-a relationship.
     */
    static abstract class Shape {
        protected String color;

        public Shape(String color) {
            this.color = color;
        }

        abstract double area();
        abstract double perimeter();

        @Override
        public String toString() {
            return getClass().getSimpleName() + "[color=" + color +
                   ", area=" + String.format("%.2f", area()) + "]";
        }
    }

    static class Circle extends Shape {
        private double radius;

        public Circle(String color, double radius) {
            super(color); // super keyword
            this.radius = radius;
        }

        double area() { return Math.PI * radius * radius; }
        double perimeter() { return 2 * Math.PI * radius; }
    }

    static class Rectangle extends Shape {
        private double width, height;

        public Rectangle(String color, double width, double height) {
            super(color);
            this.width = width;
            this.height = height;
        }

        double area() { return width * height; }
        double perimeter() { return 2 * (width + height); }
    }

    static class Triangle extends Shape {
        private double a, b, c;

        public Triangle(String color, double a, double b, double c) {
            super(color);
            this.a = a; this.b = b; this.c = c;
        }

        double area() {
            double s = (a + b + c) / 2;
            return Math.sqrt(s * (s - a) * (s - b) * (s - c));
        }
        double perimeter() { return a + b + c; }
    }

    /**
     * Employee hierarchy with multi-level inheritance.
     */
    static class Employee {
        protected String name;
        protected double baseSalary;

        public Employee(String name, double baseSalary) {
            this.name = name;
            this.baseSalary = baseSalary;
        }

        public double calculatePay() {
            return baseSalary;
        }

        public String getRole() { return "Employee"; }

        @Override
        public String toString() {
            return getRole() + ": " + name + " ($" + String.format("%.0f", calculatePay()) + ")";
        }
    }

    static class Manager extends Employee {
        private int teamSize;

        public Manager(String name, double baseSalary, int teamSize) {
            super(name, baseSalary);
            this.teamSize = teamSize;
        }

        @Override
        public double calculatePay() {
            return super.calculatePay() + (teamSize * 500); // Bonus per report
        }

        @Override
        public String getRole() { return "Manager"; }
    }

    static class Director extends Manager {
        private double stockOptions;

        public Director(String name, double baseSalary, int teamSize, double stockOptions) {
            super(name, baseSalary, teamSize);
            this.stockOptions = stockOptions;
        }

        @Override
        public double calculatePay() {
            return super.calculatePay() + stockOptions;
        }

        @Override
        public String getRole() { return "Director"; }
    }

    /**
     * Composition over Inheritance example.
     * BAD: class FlyingFish extends Fish extends Bird (impossible/wrong)
     * GOOD: Compose behaviors
     */
    interface Flyable {
        void fly();
    }

    interface Swimmable {
        void swim();
    }

    static class Duck implements Flyable, Swimmable {
        public void fly() { System.out.println("  Duck flying with wings"); }
        public void swim() { System.out.println("  Duck swimming on water"); }
    }

    // ==================== POLYMORPHISM ====================

    /**
     * Compile-time Polymorphism: Method Overloading
     */
    static class Calculator {
        int add(int a, int b) {
            return a + b;
        }

        double add(double a, double b) {
            return a + b;
        }

        int add(int a, int b, int c) {
            return a + b + c;
        }

        String add(String a, String b) {
            return a + b; // Concatenation
        }
    }

    /**
     * Runtime Polymorphism: Method Overriding with Animal hierarchy.
     */
    static abstract class Animal {
        protected String name;

        public Animal(String name) { this.name = name; }

        abstract String makeSound();

        public String describe() {
            return name + " says: " + makeSound();
        }
    }

    static class Dog extends Animal {
        public Dog(String name) { super(name); }
        String makeSound() { return "Woof!"; }
    }

    static class Cat extends Animal {
        public Cat(String name) { super(name); }
        String makeSound() { return "Meow!"; }
    }

    static class Cow extends Animal {
        public Cow(String name) { super(name); }
        String makeSound() { return "Moo!"; }
    }

    /**
     * Notification system: Interface polymorphism with real-world use.
     */
    interface NotificationChannel {
        void send(String recipient, String message);
        String getChannelName();
    }

    static class EmailNotification implements NotificationChannel {
        public void send(String recipient, String message) {
            System.out.println("  [EMAIL] To: " + recipient + " | " + message);
        }
        public String getChannelName() { return "Email"; }
    }

    static class SMSNotification implements NotificationChannel {
        public void send(String recipient, String message) {
            System.out.println("  [SMS] To: " + recipient + " | " + message);
        }
        public String getChannelName() { return "SMS"; }
    }

    static class PushNotification implements NotificationChannel {
        public void send(String recipient, String message) {
            System.out.println("  [PUSH] To: " + recipient + " | " + message);
        }
        public String getChannelName() { return "Push"; }
    }

    static class NotificationService {
        private List<NotificationChannel> channels;

        public NotificationService(List<NotificationChannel> channels) {
            this.channels = channels;
        }

        // Polymorphic dispatch - doesn't care about concrete type
        public void notifyAll(String recipient, String message) {
            for (NotificationChannel channel : channels) {
                channel.send(recipient, message);
            }
        }
    }

    // ==================== MAIN ====================

    public static void main(String[] args) {
        System.out.println("╔══════════════════════════════════════════════════════════╗");
        System.out.println("║          OOP PRINCIPLES - COMPREHENSIVE DEMO            ║");
        System.out.println("╚══════════════════════════════════════════════════════════╝");

        // --- ENCAPSULATION ---
        printHeader("1. ENCAPSULATION");

        System.out.println("\n[BankAccount - Controlled Access]");
        BankAccount account = new BankAccount("1234567890", 1000);
        System.out.println("  Account: " + account.getAccountNumber()); // Masked!
        System.out.println("  Balance: $" + account.getBalance());
        account.deposit(500);
        System.out.println("  After deposit: $" + account.getBalance());
        account.withdraw(2000); // Fails - insufficient funds
        account.withdraw(200);
        System.out.println("  After withdrawal: $" + account.getBalance());
        System.out.println("  History: " + account.getTransactionHistory());

        System.out.println("\n[UserProfile - Hidden Password Hashing]");
        UserProfile user = new UserProfile("john_doe", "secret123", "john@example.com");
        System.out.println("  User: " + user.getUsername());
        System.out.println("  Auth with correct password: " + user.authenticate("secret123"));
        System.out.println("  Auth with wrong password: " + user.authenticate("wrong"));
        // Cannot access: user.hashedPassword (private!)

        // --- ABSTRACTION ---
        printHeader("2. ABSTRACTION");

        System.out.println("\n[Abstract Class - Vehicle]");
        Vehicle car = new Car("Toyota");
        Vehicle scooter = new ElectricScooter("Ola");
        car.start();
        car.accelerate(80);
        car.stop();
        scooter.start();
        scooter.accelerate(40);

        System.out.println("\n[Interface - PaymentGateway]");
        PaymentGateway gateway = new StripeGateway();
        gateway.processPayment(99.99, "USD");
        System.out.println("  Transaction: " + gateway.getTransactionId());

        gateway = new PayPalGateway(); // Same interface, different impl
        gateway.processPayment(49.99, "EUR");
        System.out.println("  Transaction: " + gateway.getTransactionId());

        System.out.println("\n[EmailService - Hiding SMTP Complexity]");
        EmailService emailService = new EmailService();
        emailService.sendEmail("user@example.com", "Welcome!", "Thanks for signing up");

        // --- INHERITANCE ---
        printHeader("3. INHERITANCE");

        System.out.println("\n[Shape Hierarchy]");
        Shape circle = new Circle("Red", 5);
        Shape rect = new Rectangle("Blue", 4, 6);
        Shape triangle = new Triangle("Green", 3, 4, 5);
        System.out.println("  " + circle);
        System.out.println("  " + rect);
        System.out.println("  " + triangle);

        System.out.println("\n[Employee Hierarchy - Multi-level]");
        Employee emp = new Employee("Alice", 50000);
        Manager mgr = new Manager("Bob", 70000, 5);
        Director dir = new Director("Carol", 100000, 20, 50000);
        System.out.println("  " + emp);
        System.out.println("  " + mgr);
        System.out.println("  " + dir);

        System.out.println("\n[Composition over Inheritance]");
        Duck duck = new Duck();
        duck.fly();
        duck.swim();
        System.out.println("  (Duck composes Flyable + Swimmable, no diamond problem)");

        // --- POLYMORPHISM ---
        printHeader("4. POLYMORPHISM");

        System.out.println("\n[Compile-time: Method Overloading]");
        Calculator calc = new Calculator();
        System.out.println("  add(2, 3) = " + calc.add(2, 3));
        System.out.println("  add(2.5, 3.5) = " + calc.add(2.5, 3.5));
        System.out.println("  add(1, 2, 3) = " + calc.add(1, 2, 3));
        System.out.println("  add(\"Hello\", \" World\") = " + calc.add("Hello", " World"));

        System.out.println("\n[Runtime: Method Overriding - Animal Sounds]");
        List<Animal> animals = Arrays.asList(
            new Dog("Rex"), new Cat("Whiskers"), new Cow("Bessie")
        );
        for (Animal animal : animals) {
            System.out.println("  " + animal.describe());
        }

        System.out.println("\n[Polymorphic Collections - Shapes]");
        List<Shape> shapes = Arrays.asList(circle, rect, triangle);
        double totalArea = 0;
        for (Shape s : shapes) {
            totalArea += s.area(); // Same method, different behavior
        }
        System.out.println("  Total area of all shapes: " + String.format("%.2f", totalArea));

        System.out.println("\n[Interface Polymorphism - Notification System]");
        List<NotificationChannel> channels = Arrays.asList(
            new EmailNotification(),
            new SMSNotification(),
            new PushNotification()
        );
        NotificationService notifier = new NotificationService(channels);
        notifier.notifyAll("user@example.com", "Your order has shipped!");

        // --- SUMMARY ---
        printHeader("SUMMARY");
        System.out.println("  Encapsulation  -> Hide data, expose behavior (BankAccount, UserProfile)");
        System.out.println("  Abstraction    -> Hide complexity, show essentials (Vehicle, PaymentGateway)");
        System.out.println("  Inheritance    -> Reuse & extend (Shape, Employee hierarchies)");
        System.out.println("  Polymorphism   -> One interface, many forms (Animals, Notifications)");
        System.out.println();
    }

    private static void printHeader(String title) {
        System.out.println("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
        System.out.println("  " + title);
        System.out.println("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
    }
}
