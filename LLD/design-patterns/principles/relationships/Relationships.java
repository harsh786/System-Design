import java.util.*;

/**
 * Comprehensive demonstration of ALL OOP Relationships in Java.
 * 
 * Strength Hierarchy (weakest to strongest):
 * Dependency < Association < Aggregation < Composition < Inheritance/Realization
 */
public class Relationships {

    // ═══════════════════════════════════════════════════════════════════
    // 1. DEPENDENCY (uses temporarily - weakest relationship)
    //    Method parameter or local variable, NOT stored as field
    // ═══════════════════════════════════════════════════════════════════

    static class EmailService {
        void sendEmail(String to, String subject, String body) {
            System.out.println("    [Email] Sending to " + to + ": " + subject);
        }
    }

    static class Document {
        String content;
        Document(String content) { this.content = content; }
    }

    static class Formatter {
        // Dependency: Document is only used in this method, not stored
        String format(Document doc) {
            return doc.content.toUpperCase();
        }
    }

    static class OrderProcessor {
        // Dependency: EmailService is used temporarily, not a field
        void processOrder(String orderId, EmailService emailService) {
            System.out.println("    Processing order: " + orderId);
            emailService.sendEmail("customer@example.com", "Order Confirmed", orderId);
        }
    }

    // ═══════════════════════════════════════════════════════════════════
    // 2. ASSOCIATION (uses/knows-a - objects know each other)
    //    Both can exist independently. No ownership.
    // ═══════════════════════════════════════════════════════════════════

    // --- Unidirectional Association: Teacher -> Student ---
    static class Student {
        String name;
        Student(String name) { this.name = name; }
        @Override public String toString() { return name; }
    }

    static class Teacher {
        String name;
        List<Student> students = new ArrayList<>(); // Teacher knows students

        Teacher(String name) { this.name = name; }

        void addStudent(Student s) { students.add(s); }

        void showStudents() {
            System.out.println("    " + name + " teaches: " + students);
        }
    }

    // --- Bidirectional Association: Doctor <-> Patient ---
    static class Patient {
        String name;
        List<Doctor> doctors = new ArrayList<>();

        Patient(String name) { this.name = name; }

        void addDoctor(Doctor d) {
            if (!doctors.contains(d)) doctors.add(d);
        }

        @Override public String toString() { return name; }
    }

    static class Doctor {
        String name;
        List<Patient> patients = new ArrayList<>();

        Doctor(String name) { this.name = name; }

        void addPatient(Patient p) {
            if (!patients.contains(p)) {
                patients.add(p);
                p.addDoctor(this); // bidirectional link
            }
        }

        @Override public String toString() { return "Dr." + name; }

        void showPatients() {
            System.out.println("    " + this + " treats: " + patients);
        }
    }

    // --- Association: Driver and Car ---
    static class Car {
        String model;
        Car(String model) { this.model = model; }
        @Override public String toString() { return model; }
    }

    static class Driver {
        String name;
        Car currentCar; // association - can change, car exists independently

        Driver(String name) { this.name = name; }

        void drive(Car car) {
            this.currentCar = car;
            System.out.println("    " + name + " is driving " + car);
        }
    }

    // ═══════════════════════════════════════════════════════════════════
    // 3. AGGREGATION (has-a, weak ownership)
    //    Part can exist independently of the whole.
    //    Objects passed in via constructor/setter (not created inside).
    // ═══════════════════════════════════════════════════════════════════

    static class Professor {
        String name;
        boolean exists = true;

        Professor(String name) { this.name = name; }

        @Override public String toString() { return "Prof." + name; }
    }

    static class Department {
        String name;
        List<Professor> professors = new ArrayList<>(); // aggregation

        Department(String name) { this.name = name; }

        // Professors passed in - not created here
        void addProfessor(Professor p) { professors.add(p); }

        void showProfessors() {
            System.out.println("    " + name + " dept has: " + professors);
        }

        void close() {
            System.out.println("    [!] " + name + " department CLOSED");
            professors.clear(); // remove references, but professors still exist!
        }
    }

    static class Player {
        String name;
        Player(String name) { this.name = name; }
        @Override public String toString() { return name; }
    }

    static class Team {
        String name;
        List<Player> players = new ArrayList<>();

        Team(String name) { this.name = name; }

        void addPlayer(Player p) { players.add(p); }

        void disband() {
            System.out.println("    [!] Team " + name + " DISBANDED");
            players.clear(); // players still exist
        }
    }

    // ═══════════════════════════════════════════════════════════════════
    // 4. COMPOSITION (has-a, strong ownership - part-of)
    //    Part CANNOT exist independently. Whole manages lifecycle.
    //    Objects created inside constructor.
    // ═══════════════════════════════════════════════════════════════════

    static class Room {
        String type;
        Room(String type) {
            this.type = type;
            System.out.println("      [+] Room created: " + type);
        }
        void destroy() { System.out.println("      [-] Room destroyed: " + type); }
        @Override public String toString() { return type; }
    }

    static class House {
        String address;
        List<Room> rooms = new ArrayList<>(); // composition - house OWNS rooms

        House(String address) {
            this.address = address;
            // Rooms created INSIDE the house - composition!
            rooms.add(new Room("Living Room"));
            rooms.add(new Room("Bedroom"));
            rooms.add(new Room("Kitchen"));
            System.out.println("    [+] House built at: " + address);
        }

        void demolish() {
            System.out.println("    [!] Demolishing house at: " + address);
            for (Room r : rooms) r.destroy(); // rooms die with house
            rooms.clear();
            System.out.println("    [!] House demolished - ALL rooms destroyed");
        }
    }

    static class Engine {
        String type;
        boolean running = false;

        Engine(String type) { this.type = type; }

        void start() { running = true; System.out.println("      Engine " + type + " started"); }
        void stop() { running = false; }
        void destroy() { System.out.println("      [-] Engine " + type + " scrapped"); }
        @Override public String toString() { return type; }
    }

    static class CarWithEngine {
        String model;
        Engine engine; // composition - engine created with car

        CarWithEngine(String model, String engineType) {
            this.model = model;
            this.engine = new Engine(engineType); // created inside!
            System.out.println("    [+] Car built: " + model + " with engine " + engineType);
        }

        void scrap() {
            System.out.println("    [!] Scrapping car: " + model);
            engine.destroy(); // engine dies with car
        }
    }

    static class OrderLineItem {
        String product;
        int quantity;
        double price;

        OrderLineItem(String product, int qty, double price) {
            this.product = product; this.quantity = qty; this.price = price;
        }

        @Override public String toString() {
            return product + " x" + quantity + " @$" + price;
        }
    }

    static class Order {
        String orderId;
        List<OrderLineItem> items = new ArrayList<>(); // composition

        Order(String orderId) { this.orderId = orderId; }

        void addItem(String product, int qty, double price) {
            items.add(new OrderLineItem(product, qty, price)); // created inside
        }

        void cancel() {
            System.out.println("    [!] Order " + orderId + " CANCELLED - all line items destroyed");
            items.clear(); // line items meaningless without order
        }

        void show() {
            System.out.println("    Order " + orderId + ": " + items);
        }
    }

    // ═══════════════════════════════════════════════════════════════════
    // 5. INHERITANCE (is-a)
    // ═══════════════════════════════════════════════════════════════════

    static abstract class Animal {
        String name;
        Animal(String name) { this.name = name; }

        void eat() { System.out.println("    " + name + " is eating"); }
        abstract void makeSound();
    }

    static class Dog extends Animal {
        Dog(String name) { super(name); }

        @Override
        void makeSound() { System.out.println("    " + name + " says: Woof!"); }

        void fetch() { System.out.println("    " + name + " fetches the ball!"); }
    }

    static class Cat extends Animal {
        Cat(String name) { super(name); }

        @Override
        void makeSound() { System.out.println("    " + name + " says: Meow!"); }
    }

    static abstract class Vehicle {
        String brand;
        int speed;

        Vehicle(String brand) { this.brand = brand; }

        void accelerate(int amount) {
            speed += amount;
            System.out.println("    " + brand + " accelerating to " + speed + " km/h");
        }

        abstract String getType();
    }

    static class Truck extends Vehicle {
        int payload;
        Truck(String brand, int payload) { super(brand); this.payload = payload; }

        @Override
        String getType() { return "Truck (payload: " + payload + " tons)"; }
    }

    static class Motorcycle extends Vehicle {
        Motorcycle(String brand) { super(brand); }

        @Override
        String getType() { return "Motorcycle"; }
    }

    // ═══════════════════════════════════════════════════════════════════
    // 6. REALIZATION / IMPLEMENTATION (can-do)
    //    Classes fulfill a contract defined by an interface.
    // ═══════════════════════════════════════════════════════════════════

    interface PaymentProcessor {
        boolean processPayment(double amount, String currency);
        void refund(String transactionId);
    }

    interface Auditable {
        String getAuditLog();
    }

    static class StripeProcessor implements PaymentProcessor, Auditable {
        List<String> log = new ArrayList<>();

        @Override
        public boolean processPayment(double amount, String currency) {
            String msg = "Stripe: charged " + amount + " " + currency;
            log.add(msg);
            System.out.println("    " + msg);
            return true;
        }

        @Override
        public void refund(String transactionId) {
            System.out.println("    Stripe: refunded " + transactionId);
        }

        @Override
        public String getAuditLog() { return log.toString(); }
    }

    static class PayPalProcessor implements PaymentProcessor {
        @Override
        public boolean processPayment(double amount, String currency) {
            System.out.println("    PayPal: charged " + amount + " " + currency);
            return true;
        }

        @Override
        public void refund(String transactionId) {
            System.out.println("    PayPal: refunded " + transactionId);
        }
    }

    // Comparable example
    static class Product implements Comparable<Product> {
        String name;
        double price;

        Product(String name, double price) { this.name = name; this.price = price; }

        @Override
        public int compareTo(Product other) { return Double.compare(this.price, other.price); }

        @Override
        public String toString() { return name + "($" + price + ")"; }
    }

    // ═══════════════════════════════════════════════════════════════════
    // 7. COMPREHENSIVE UNIVERSITY SYSTEM
    //    Showing Composition + Aggregation + Association together
    // ═══════════════════════════════════════════════════════════════════

    static class UniversityStudent {
        String name;
        UniversityStudent(String name) { this.name = name; }
        @Override public String toString() { return name; }
    }

    static class UniversityProfessor {
        String name;
        List<UniversityStudent> advisees = new ArrayList<>(); // association with students

        UniversityProfessor(String name) { this.name = name; }

        void advise(UniversityStudent s) { advisees.add(s); }

        @Override public String toString() { return "Prof." + name; }
    }

    static class UniversityDepartment {
        String name;
        List<UniversityProfessor> professors = new ArrayList<>(); // aggregation

        UniversityDepartment(String name) {
            this.name = name;
            System.out.println("      [+] Department created: " + name);
        }

        void addProfessor(UniversityProfessor p) { professors.add(p); }

        void destroy() {
            System.out.println("      [-] Department destroyed: " + name);
            professors.clear();
        }

        @Override public String toString() { return name; }
    }

    static class University {
        String name;
        List<UniversityDepartment> departments = new ArrayList<>(); // COMPOSITION
        List<UniversityProfessor> allProfessors = new ArrayList<>(); // AGGREGATION

        University(String name) {
            this.name = name;
            // Departments created INSIDE - COMPOSITION
            departments.add(new UniversityDepartment("Computer Science"));
            departments.add(new UniversityDepartment("Mathematics"));
            departments.add(new UniversityDepartment("Physics"));
            System.out.println("    [+] University founded: " + name);
        }

        void hireProfessor(UniversityProfessor p, int deptIndex) {
            allProfessors.add(p);
            if (deptIndex < departments.size()) {
                departments.get(deptIndex).addProfessor(p);
            }
        }

        void shutdown() {
            System.out.println("\n    [!!!] SHUTTING DOWN University: " + name);
            System.out.println("    Destroying departments (COMPOSITION - they die):");
            for (UniversityDepartment d : departments) d.destroy();
            departments.clear();

            System.out.println("    Releasing professors (AGGREGATION - they survive):");
            for (UniversityProfessor p : allProfessors) {
                System.out.println("      " + p + " still exists, can join another university");
            }
            allProfessors.clear();
        }
    }

    // ═══════════════════════════════════════════════════════════════════
    // MAIN - Demonstrate everything
    // ═══════════════════════════════════════════════════════════════════

    public static void main(String[] args) {
        System.out.println("╔══════════════════════════════════════════════════════════════╗");
        System.out.println("║       OOP RELATIONSHIPS - COMPREHENSIVE DEMO                ║");
        System.out.println("╚══════════════════════════════════════════════════════════════╝");

        // --- DEPENDENCY ---
        System.out.println("\n▓▓▓ 1. DEPENDENCY (weakest - uses temporarily) ▓▓▓");
        System.out.println("  OrderProcessor uses EmailService only in processOrder():");
        OrderProcessor op = new OrderProcessor();
        EmailService es = new EmailService();
        op.processOrder("ORD-001", es); // es passed as param, not stored

        System.out.println("\n  Formatter uses Document only in format():");
        Formatter fmt = new Formatter();
        Document doc = new Document("hello world");
        System.out.println("    Formatted: " + fmt.format(doc));

        // --- ASSOCIATION ---
        System.out.println("\n▓▓▓ 2. ASSOCIATION (knows-a, independent existence) ▓▓▓");
        System.out.println("  --- Unidirectional: Teacher -> Student ---");
        Student s1 = new Student("Alice");
        Student s2 = new Student("Bob");
        Teacher t1 = new Teacher("Mr. Smith");
        t1.addStudent(s1);
        t1.addStudent(s2);
        t1.showStudents();
        System.out.println("    (Students don't know about Mr. Smith)");

        System.out.println("\n  --- Bidirectional: Doctor <-> Patient ---");
        Doctor doc1 = new Doctor("House");
        Patient pat1 = new Patient("Wilson");
        Patient pat2 = new Patient("Cuddy");
        doc1.addPatient(pat1);
        doc1.addPatient(pat2);
        doc1.showPatients();
        System.out.println("    " + pat1.name + "'s doctors: " + pat1.doctors);

        System.out.println("\n  --- Driver and Car ---");
        Driver driver = new Driver("John");
        Car car1 = new Car("Tesla Model 3");
        Car car2 = new Car("BMW X5");
        driver.drive(car1);
        driver.drive(car2); // can switch cars
        System.out.println("    Both driver and cars exist independently");

        // --- AGGREGATION ---
        System.out.println("\n▓▓▓ 3. AGGREGATION (has-a, weak ownership) ▓▓▓");
        System.out.println("  Department has Professors (professors survive dept closure):");
        Professor p1 = new Professor("Einstein");
        Professor p2 = new Professor("Feynman");
        Department dept = new Department("Physics");
        dept.addProfessor(p1); // passed in, not created inside
        dept.addProfessor(p2);
        dept.showProfessors();
        dept.close();
        System.out.println("    After dept closed - " + p1 + " still exists: " + p1.exists);
        System.out.println("    After dept closed - " + p2 + " still exists: " + p2.exists);

        System.out.println("\n  Team has Players (players survive disbanding):");
        Player pl1 = new Player("Messi");
        Player pl2 = new Player("Ronaldo");
        Team team = new Team("All Stars");
        team.addPlayer(pl1);
        team.addPlayer(pl2);
        team.disband();
        System.out.println("    " + pl1 + " can join another team!");

        // --- COMPOSITION ---
        System.out.println("\n▓▓▓ 4. COMPOSITION (has-a, strong ownership - part-of) ▓▓▓");
        System.out.println("  House has Rooms (rooms die with house):");
        House house = new House("123 Main St");
        house.demolish();

        System.out.println("\n  Car has Engine (engine dies with car):");
        CarWithEngine myCar = new CarWithEngine("Ford Mustang", "V8 5.0L");
        myCar.engine.start();
        myCar.scrap();

        System.out.println("\n  Order has LineItems (items meaningless without order):");
        Order order = new Order("ORD-100");
        order.addItem("Laptop", 1, 999.99);
        order.addItem("Mouse", 2, 29.99);
        order.show();
        order.cancel();

        // --- INHERITANCE ---
        System.out.println("\n▓▓▓ 5. INHERITANCE (is-a) ▓▓▓");
        System.out.println("  Animal hierarchy:");
        Dog dog = new Dog("Rex");
        Cat cat = new Cat("Whiskers");
        dog.eat();        // inherited
        dog.makeSound();  // overridden
        dog.fetch();      // dog-specific
        cat.makeSound();

        System.out.println("\n  Vehicle hierarchy:");
        Truck truck = new Truck("Volvo", 20);
        Motorcycle moto = new Motorcycle("Harley");
        System.out.println("    " + truck.brand + ": " + truck.getType());
        truck.accelerate(60);
        System.out.println("    " + moto.brand + ": " + moto.getType());
        moto.accelerate(120);

        System.out.println("\n  Why Java uses interfaces (Diamond Problem):");
        System.out.println("    Java doesn't allow: class C extends A, B");
        System.out.println("    But allows: class C implements InterfaceA, InterfaceB");
        System.out.println("    This avoids ambiguity of inherited method implementations");

        // --- REALIZATION ---
        System.out.println("\n▓▓▓ 6. REALIZATION/IMPLEMENTATION (can-do) ▓▓▓");
        System.out.println("  PaymentProcessor interface:");
        PaymentProcessor stripe = new StripeProcessor();
        PaymentProcessor paypal = new PayPalProcessor();
        stripe.processPayment(49.99, "USD");
        paypal.processPayment(29.99, "EUR");
        stripe.refund("TXN-001");

        System.out.println("\n  Multiple interfaces (StripeProcessor is Auditable):");
        System.out.println("    Audit log: " + ((Auditable) stripe).getAuditLog());

        System.out.println("\n  Comparable interface:");
        List<Product> products = new ArrayList<>(Arrays.asList(
            new Product("Phone", 699), new Product("Tablet", 399), new Product("Laptop", 1299)
        ));
        Collections.sort(products);
        System.out.println("    Sorted by price: " + products);

        // --- COMPREHENSIVE EXAMPLE ---
        System.out.println("\n▓▓▓ 7. UNIVERSITY SYSTEM (All relationships together) ▓▓▓");
        System.out.println("  Composition: University -> Departments");
        System.out.println("  Aggregation: Department -> Professors");
        System.out.println("  Association: Professor -> Students\n");

        University uni = new University("MIT");

        UniversityProfessor up1 = new UniversityProfessor("Turing");
        UniversityProfessor up2 = new UniversityProfessor("Knuth");
        UniversityStudent us1 = new UniversityStudent("Alice");
        UniversityStudent us2 = new UniversityStudent("Bob");

        uni.hireProfessor(up1, 0); // CS dept
        uni.hireProfessor(up2, 0); // CS dept
        up1.advise(us1); // association
        up2.advise(us2);

        System.out.println("    " + up1 + " advises: " + up1.advisees);
        System.out.println("    " + up2 + " advises: " + up2.advisees);

        uni.shutdown();

        System.out.println("\n    After university shutdown:");
        System.out.println("    Departments: DESTROYED (composition)");
        System.out.println("    " + up1 + " still exists: true (aggregation)");
        System.out.println("    " + us1 + " still exists: true (association)");
        System.out.println("    " + up1 + " still advises: " + up1.advisees + " (association intact)");

        // --- SUMMARY ---
        System.out.println("\n╔══════════════════════════════════════════════════════════════╗");
        System.out.println("║  RELATIONSHIP STRENGTH (weakest → strongest):               ║");
        System.out.println("║                                                              ║");
        System.out.println("║  Dependency → Association → Aggregation → Composition        ║");
        System.out.println("║  (uses)       (knows)       (has-weak)    (has-strong)       ║");
        System.out.println("║                                                              ║");
        System.out.println("║  Key Differences:                                            ║");
        System.out.println("║  • Dependency:  method param/local var only                  ║");
        System.out.println("║  • Association: field reference, both live independently     ║");
        System.out.println("║  • Aggregation: field, part passed in, survives whole        ║");
        System.out.println("║  • Composition: field, part created inside, dies with whole  ║");
        System.out.println("╚══════════════════════════════════════════════════════════════╝");
    }
}
