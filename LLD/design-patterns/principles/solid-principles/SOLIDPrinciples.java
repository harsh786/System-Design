import java.util.*;

/**
 * Comprehensive SOLID Principles Demo
 * Demonstrates BEFORE (violation) and AFTER (correct) for all 5 principles.
 */
public class SOLIDPrinciples {

    // ═══════════════════════════════════════════════════════════════════════════
    // S - SINGLE RESPONSIBILITY PRINCIPLE
    // "A class should have only one reason to change"
    // ═══════════════════════════════════════════════════════════════════════════

    static class SRP {

        // ─── BAD: God class doing everything ───
        static class BadUserService {
            public void registerUser(String name, String email) {
                // Validation
                if (email == null || !email.contains("@"))
                    throw new RuntimeException("Invalid email");
                // Database save
                System.out.println("  [DB] INSERT INTO users VALUES('" + name + "', '" + email + "')");
                // Send email
                System.out.println("  [SMTP] Sending welcome email to " + email);
                // Logging
                System.out.println("  [LOG] User registered: " + name + " at " + new Date());
            }
        }

        // ─── GOOD: Each class has one responsibility ───
        static class UserRepository {
            public void save(String name, String email) {
                System.out.println("  [UserRepository] Saved user: " + name);
            }
        }

        static class EmailService {
            public void sendWelcomeEmail(String email) {
                System.out.println("  [EmailService] Welcome email sent to: " + email);
            }
        }

        static class AuditLogger {
            public void log(String message) {
                System.out.println("  [AuditLogger] " + message);
            }
        }

        static class UserRegistration {
            private final UserRepository repo;
            private final EmailService emailService;
            private final AuditLogger logger;

            UserRegistration(UserRepository repo, EmailService emailService, AuditLogger logger) {
                this.repo = repo;
                this.emailService = emailService;
                this.logger = logger;
            }

            public void register(String name, String email) {
                repo.save(name, email);
                emailService.sendWelcomeEmail(email);
                logger.log("User registered: " + name);
            }
        }

        // ─── Real-world: Invoice System ───
        static class Invoice {
            String id;
            double amount;
            double tax;
            Invoice(String id, double amount, double tax) {
                this.id = id; this.amount = amount; this.tax = tax;
            }
        }

        static class InvoiceCalculator {
            public double calculateTotal(Invoice inv) { return inv.amount + inv.tax; }
        }

        static class InvoicePrinter {
            public void print(Invoice inv, double total) {
                System.out.println("  [InvoicePrinter] Invoice " + inv.id + " | Total: $" + total);
            }
        }

        static class InvoiceRepository {
            public void save(Invoice inv) {
                System.out.println("  [InvoiceRepository] Saved invoice " + inv.id);
            }
        }

        static void demo() {
            System.out.println("\n╔══════════════════════════════════════════════════════════════╗");
            System.out.println("║  S - SINGLE RESPONSIBILITY PRINCIPLE                        ║");
            System.out.println("╚══════════════════════════════════════════════════════════════╝");

            System.out.println("\n── BAD: One class does everything ──");
            new BadUserService().registerUser("Alice", "alice@mail.com");

            System.out.println("\n── GOOD: Separated responsibilities ──");
            var registration = new UserRegistration(new UserRepository(), new EmailService(), new AuditLogger());
            registration.register("Alice", "alice@mail.com");

            System.out.println("\n── Real-world: Invoice System ──");
            Invoice inv = new Invoice("INV-001", 100.0, 18.0);
            double total = new InvoiceCalculator().calculateTotal(inv);
            new InvoicePrinter().print(inv, total);
            new InvoiceRepository().save(inv);
        }
    }

    // ═══════════════════════════════════════════════════════════════════════════
    // O - OPEN/CLOSED PRINCIPLE
    // "Open for extension, closed for modification"
    // ═══════════════════════════════════════════════════════════════════════════

    static class OCP {

        // ─── BAD: Must modify class for every new shape ───
        static class BadAreaCalculator {
            public double calculate(String type, double... dims) {
                switch (type) {
                    case "circle": return Math.PI * dims[0] * dims[0];
                    case "rectangle": return dims[0] * dims[1];
                    // Adding triangle means MODIFYING this class!
                    default: throw new RuntimeException("Unknown shape: " + type);
                }
            }
        }

        // ─── GOOD: New shapes don't require modifying existing code ───
        interface Shape {
            double area();
            String name();
        }

        static class Circle implements Shape {
            private final double radius;
            Circle(double radius) { this.radius = radius; }
            public double area() { return Math.PI * radius * radius; }
            public String name() { return "Circle(r=" + radius + ")"; }
        }

        static class Rectangle implements Shape {
            private final double w, h;
            Rectangle(double w, double h) { this.w = w; this.h = h; }
            public double area() { return w * h; }
            public String name() { return "Rectangle(" + w + "x" + h + ")"; }
        }

        // Adding new shape WITHOUT modifying existing code!
        static class Triangle implements Shape {
            private final double base, height;
            Triangle(double base, double height) { this.base = base; this.height = height; }
            public double area() { return 0.5 * base * height; }
            public String name() { return "Triangle(b=" + base + ",h=" + height + ")"; }
        }

        static class AreaCalculator {
            public double totalArea(List<Shape> shapes) {
                return shapes.stream().mapToDouble(Shape::area).sum();
            }
        }

        // ─── Real-world: Discount System ───
        interface DiscountStrategy {
            double apply(double price);
            String description();
        }

        static class SeasonalDiscount implements DiscountStrategy {
            public double apply(double price) { return price * 0.10; }
            public String description() { return "Seasonal 10%"; }
        }

        static class LoyaltyDiscount implements DiscountStrategy {
            public double apply(double price) { return price * 0.15; }
            public String description() { return "Loyalty 15%"; }
        }

        static class CouponDiscount implements DiscountStrategy {
            private final double percent;
            CouponDiscount(double percent) { this.percent = percent; }
            public double apply(double price) { return price * percent / 100; }
            public String description() { return "Coupon " + percent + "%"; }
        }

        static class PriceCalculator {
            public double applyDiscounts(double price, List<DiscountStrategy> discounts) {
                double totalDiscount = discounts.stream().mapToDouble(d -> d.apply(price)).sum();
                return price - totalDiscount;
            }
        }

        static void demo() {
            System.out.println("\n╔══════════════════════════════════════════════════════════════╗");
            System.out.println("║  O - OPEN/CLOSED PRINCIPLE                                  ║");
            System.out.println("╚══════════════════════════════════════════════════════════════╝");

            System.out.println("\n── BAD: if-else/switch for each shape ──");
            var bad = new BadAreaCalculator();
            System.out.println("  Circle area: " + String.format("%.2f", bad.calculate("circle", 5)));
            System.out.println("  Rectangle area: " + bad.calculate("rectangle", 4, 6));
            System.out.println("  (Adding triangle requires modifying BadAreaCalculator!)");

            System.out.println("\n── GOOD: Shapes implement interface ──");
            List<Shape> shapes = List.of(new Circle(5), new Rectangle(4, 6), new Triangle(3, 8));
            shapes.forEach(s -> System.out.println("  " + s.name() + " area = " + String.format("%.2f", s.area())));
            System.out.println("  Total area: " + String.format("%.2f", new AreaCalculator().totalArea(shapes)));

            System.out.println("\n── Real-world: Discount System ──");
            double price = 200.0;
            List<DiscountStrategy> discounts = List.of(new SeasonalDiscount(), new LoyaltyDiscount(), new CouponDiscount(5));
            double finalPrice = new PriceCalculator().applyDiscounts(price, discounts);
            discounts.forEach(d -> System.out.println("  " + d.description() + " = -$" + String.format("%.2f", d.apply(price))));
            System.out.println("  Final price: $" + String.format("%.2f", finalPrice));
        }
    }

    // ═══════════════════════════════════════════════════════════════════════════
    // L - LISKOV SUBSTITUTION PRINCIPLE
    // "Subtypes must be substitutable for their base types"
    // ═══════════════════════════════════════════════════════════════════════════

    static class LSP {

        // ─── BAD: Square extends Rectangle (classic violation) ───
        static class BadRectangle {
            protected int width, height;
            public void setWidth(int w) { width = w; }
            public void setHeight(int h) { height = h; }
            public int area() { return width * height; }
        }

        static class BadSquare extends BadRectangle {
            // Violates LSP: changing width also changes height!
            public void setWidth(int w) { width = w; height = w; }
            public void setHeight(int h) { width = h; height = h; }
        }

        // ─── GOOD: Separate implementations ───
        interface GoodShape {
            int area();
            String describe();
        }

        static class GoodRectangle implements GoodShape {
            private final int w, h;
            GoodRectangle(int w, int h) { this.w = w; this.h = h; }
            public int area() { return w * h; }
            public String describe() { return "Rectangle " + w + "x" + h; }
        }

        static class GoodSquare implements GoodShape {
            private final int side;
            GoodSquare(int side) { this.side = side; }
            public int area() { return side * side; }
            public String describe() { return "Square " + side + "x" + side; }
        }

        // ─── BAD: Bird hierarchy with non-flying birds ───
        static abstract class BadBird {
            public abstract void fly();
        }

        static class BadSparrow extends BadBird {
            public void fly() { System.out.println("  Sparrow flying"); }
        }

        static class BadOstrich extends BadBird {
            public void fly() { throw new UnsupportedOperationException("Ostriches can't fly!"); }
        }

        // ─── GOOD: Proper hierarchy ───
        interface Bird {
            void eat();
        }

        interface FlyingBird extends Bird {
            void fly();
        }

        interface NonFlyingBird extends Bird {
            void walk();
        }

        static class Sparrow implements FlyingBird {
            public void eat() { System.out.println("  Sparrow eating seeds"); }
            public void fly() { System.out.println("  Sparrow flying high"); }
        }

        static class Ostrich implements NonFlyingBird {
            public void eat() { System.out.println("  Ostrich eating"); }
            public void walk() { System.out.println("  Ostrich running fast"); }
        }

        // ─── Real-world: Payment Processing ───
        interface PaymentMethod {
            boolean pay(double amount);
            boolean refund(double amount);
        }

        static class CreditCard implements PaymentMethod {
            public boolean pay(double amount) {
                System.out.println("  [CreditCard] Charged $" + amount);
                return true;
            }
            public boolean refund(double amount) {
                System.out.println("  [CreditCard] Refunded $" + amount);
                return true;
            }
        }

        static class PayPal implements PaymentMethod {
            public boolean pay(double amount) {
                System.out.println("  [PayPal] Transferred $" + amount);
                return true;
            }
            public boolean refund(double amount) {
                System.out.println("  [PayPal] Refunded $" + amount);
                return true;
            }
        }

        static void processPayment(PaymentMethod method, double amount) {
            method.pay(amount);
        }

        static void demo() {
            System.out.println("\n╔══════════════════════════════════════════════════════════════╗");
            System.out.println("║  L - LISKOV SUBSTITUTION PRINCIPLE                          ║");
            System.out.println("╚══════════════════════════════════════════════════════════════╝");

            System.out.println("\n── BAD: Square extends Rectangle ──");
            BadRectangle rect = new BadSquare();
            rect.setWidth(5);
            rect.setHeight(3);
            System.out.println("  Set width=5, height=3, expected area=15, got: " + rect.area());
            System.out.println("  (WRONG! Square made both sides 3, area=9)");

            System.out.println("\n── GOOD: Separate Shape implementations ──");
            List<GoodShape> shapes = List.of(new GoodRectangle(5, 3), new GoodSquare(4));
            shapes.forEach(s -> System.out.println("  " + s.describe() + " area = " + s.area()));

            System.out.println("\n── BAD: Ostrich forced to fly ──");
            try {
                new BadOstrich().fly();
            } catch (UnsupportedOperationException e) {
                System.out.println("  Exception: " + e.getMessage());
            }

            System.out.println("\n── GOOD: Proper bird hierarchy ──");
            new Sparrow().fly();
            new Ostrich().walk();

            System.out.println("\n── Real-world: Payment (all methods substitutable) ──");
            processPayment(new CreditCard(), 99.99);
            processPayment(new PayPal(), 49.99);
        }
    }

    // ═══════════════════════════════════════════════════════════════════════════
    // I - INTERFACE SEGREGATION PRINCIPLE
    // "No client should be forced to depend on methods it doesn't use"
    // ═══════════════════════════════════════════════════════════════════════════

    static class ISP {

        // ─── BAD: Fat Worker interface ───
        interface BadWorker {
            void work();
            void eat();
            void sleep();
        }

        static class BadHuman implements BadWorker {
            public void work() { System.out.println("  Human working"); }
            public void eat() { System.out.println("  Human eating"); }
            public void sleep() { System.out.println("  Human sleeping"); }
        }

        static class BadRobot implements BadWorker {
            public void work() { System.out.println("  Robot working"); }
            public void eat() { throw new UnsupportedOperationException("Robots don't eat!"); }
            public void sleep() { throw new UnsupportedOperationException("Robots don't sleep!"); }
        }

        // ─── GOOD: Segregated interfaces ───
        interface Workable { void work(); }
        interface Eatable { void eat(); }
        interface Sleepable { void sleep(); }

        static class Human implements Workable, Eatable, Sleepable {
            public void work() { System.out.println("  Human working"); }
            public void eat() { System.out.println("  Human eating"); }
            public void sleep() { System.out.println("  Human sleeping"); }
        }

        static class Robot implements Workable {
            public void work() { System.out.println("  Robot working 24/7"); }
        }

        // ─── BAD: Fat MultiFunctionPrinter ───
        interface BadMFP {
            void print(String doc);
            void scan(String doc);
            void fax(String doc);
            void staple(String doc);
        }

        // SimplePrinter forced to implement scan, fax, staple!
        static class BadSimplePrinter implements BadMFP {
            public void print(String doc) { System.out.println("  Printing: " + doc); }
            public void scan(String doc) { throw new UnsupportedOperationException("No scanner"); }
            public void fax(String doc) { throw new UnsupportedOperationException("No fax"); }
            public void staple(String doc) { throw new UnsupportedOperationException("No stapler"); }
        }

        // ─── GOOD: Separated interfaces ───
        interface Printer { void print(String doc); }
        interface Scanner { void scan(String doc); }
        interface Fax { void fax(String doc); }

        static class SimplePrinter implements Printer {
            public void print(String doc) { System.out.println("  [SimplePrinter] " + doc); }
        }

        static class AllInOnePrinter implements Printer, Scanner, Fax {
            public void print(String doc) { System.out.println("  [AllInOne] Print: " + doc); }
            public void scan(String doc) { System.out.println("  [AllInOne] Scan: " + doc); }
            public void fax(String doc) { System.out.println("  [AllInOne] Fax: " + doc); }
        }

        // ─── Real-world: Repository interfaces ───
        interface ReadRepository<T> {
            T findById(String id);
            List<T> findAll();
        }

        interface WriteRepository<T> {
            void save(T entity);
            void delete(String id);
        }

        interface CRUDRepository<T> extends ReadRepository<T>, WriteRepository<T> {}

        // Read-only view needs only ReadRepository
        static class ReportGenerator {
            private final ReadRepository<String> repo;
            ReportGenerator(ReadRepository<String> repo) { this.repo = repo; }
            public void generate() {
                System.out.println("  [ReportGenerator] Reading all data: " + repo.findAll());
            }
        }

        static void demo() {
            System.out.println("\n╔══════════════════════════════════════════════════════════════╗");
            System.out.println("║  I - INTERFACE SEGREGATION PRINCIPLE                        ║");
            System.out.println("╚══════════════════════════════════════════════════════════════╝");

            System.out.println("\n── BAD: Robot forced to implement eat/sleep ──");
            try {
                new BadRobot().eat();
            } catch (UnsupportedOperationException e) {
                System.out.println("  Exception: " + e.getMessage());
            }

            System.out.println("\n── GOOD: Robot only implements Workable ──");
            new Robot().work();
            Human human = new Human();
            human.work();
            human.eat();

            System.out.println("\n── BAD: SimplePrinter forced to have scan/fax ──");
            try {
                new BadSimplePrinter().scan("doc.pdf");
            } catch (UnsupportedOperationException e) {
                System.out.println("  Exception: " + e.getMessage());
            }

            System.out.println("\n── GOOD: Separate Printer/Scanner/Fax interfaces ──");
            new SimplePrinter().print("report.pdf");
            AllInOnePrinter aio = new AllInOnePrinter();
            aio.print("photo.jpg");
            aio.scan("contract.pdf");

            System.out.println("\n── Real-world: ReadRepository for reports ──");
            ReadRepository<String> readOnly = new ReadRepository<>() {
                public String findById(String id) { return "item-" + id; }
                public List<String> findAll() { return List.of("item1", "item2", "item3"); }
            };
            new ReportGenerator(readOnly).generate();
        }
    }

    // ═══════════════════════════════════════════════════════════════════════════
    // D - DEPENDENCY INVERSION PRINCIPLE
    // "Depend on abstractions, not concretions"
    // ═══════════════════════════════════════════════════════════════════════════

    static class DIP {

        // ─── BAD: Tightly coupled ───
        static class BadEmailSender {
            public void send(String to, String msg) {
                System.out.println("  [Email] To: " + to + " | " + msg);
            }
        }

        static class BadNotificationService {
            private final BadEmailSender sender = new BadEmailSender(); // Hard dependency!

            public void notify(String user, String msg) {
                sender.send(user, msg);
                // Can't switch to SMS or push without modifying this class!
            }
        }

        // ─── GOOD: Depends on abstraction ───
        interface MessageSender {
            void send(String to, String message);
        }

        static class EmailSender implements MessageSender {
            public void send(String to, String msg) {
                System.out.println("  [Email] To: " + to + " | " + msg);
            }
        }

        static class SmsSender implements MessageSender {
            public void send(String to, String msg) {
                System.out.println("  [SMS] To: " + to + " | " + msg);
            }
        }

        static class PushSender implements MessageSender {
            public void send(String to, String msg) {
                System.out.println("  [Push] To: " + to + " | " + msg);
            }
        }

        // Constructor Injection
        static class NotificationService {
            private final MessageSender sender;

            NotificationService(MessageSender sender) { // Injected!
                this.sender = sender;
            }

            public void notify(String user, String msg) {
                sender.send(user, msg);
            }
        }

        // Setter Injection
        static class ConfigurableNotifier {
            private MessageSender sender;

            public void setSender(MessageSender sender) { this.sender = sender; }

            public void notify(String user, String msg) {
                if (sender == null) throw new IllegalStateException("No sender configured");
                sender.send(user, msg);
            }
        }

        // ─── Real-world: OrderService with PaymentProcessor ───
        interface PaymentProcessor {
            boolean charge(String orderId, double amount);
        }

        static class StripePayment implements PaymentProcessor {
            public boolean charge(String orderId, double amount) {
                System.out.println("  [Stripe] Charged $" + amount + " for order " + orderId);
                return true;
            }
        }

        static class PayPalPayment implements PaymentProcessor {
            public boolean charge(String orderId, double amount) {
                System.out.println("  [PayPal] Charged $" + amount + " for order " + orderId);
                return true;
            }
        }

        static class OrderService {
            private final PaymentProcessor processor;

            OrderService(PaymentProcessor processor) {
                this.processor = processor;
            }

            public void placeOrder(String orderId, double total) {
                System.out.println("  Placing order " + orderId + "...");
                processor.charge(orderId, total);
                System.out.println("  Order " + orderId + " confirmed!");
            }
        }

        static void demo() {
            System.out.println("\n╔══════════════════════════════════════════════════════════════╗");
            System.out.println("║  D - DEPENDENCY INVERSION PRINCIPLE                         ║");
            System.out.println("╚══════════════════════════════════════════════════════════════╝");

            System.out.println("\n── BAD: Hardcoded dependency ──");
            new BadNotificationService().notify("user@mail.com", "Hello!");
            System.out.println("  (Can't switch to SMS without modifying class)");

            System.out.println("\n── GOOD: Constructor injection ──");
            new NotificationService(new EmailSender()).notify("user@mail.com", "Hello via Email!");
            new NotificationService(new SmsSender()).notify("+1234567890", "Hello via SMS!");
            new NotificationService(new PushSender()).notify("device-token", "Hello via Push!");

            System.out.println("\n── Setter injection ──");
            ConfigurableNotifier notifier = new ConfigurableNotifier();
            notifier.setSender(new EmailSender());
            notifier.notify("admin@co.com", "Alert!");
            notifier.setSender(new SmsSender());
            notifier.notify("+999", "Switched to SMS!");

            System.out.println("\n── Real-world: OrderService with PaymentProcessor ──");
            new OrderService(new StripePayment()).placeOrder("ORD-001", 150.00);
            new OrderService(new PayPalPayment()).placeOrder("ORD-002", 75.50);
        }
    }

    // ═══════════════════════════════════════════════════════════════════════════
    // MAIN
    // ═══════════════════════════════════════════════════════════════════════════

    public static void main(String[] args) {
        System.out.println("╔══════════════════════════════════════════════════════════════╗");
        System.out.println("║           SOLID PRINCIPLES - COMPREHENSIVE DEMO             ║");
        System.out.println("╠══════════════════════════════════════════════════════════════╣");
        System.out.println("║  S - Single Responsibility    O - Open/Closed               ║");
        System.out.println("║  L - Liskov Substitution      I - Interface Segregation     ║");
        System.out.println("║  D - Dependency Inversion                                   ║");
        System.out.println("╚══════════════════════════════════════════════════════════════╝");

        SRP.demo();
        OCP.demo();
        LSP.demo();
        ISP.demo();
        DIP.demo();

        System.out.println("\n══════════════════════════════════════════════════════════════");
        System.out.println("  All SOLID principles demonstrated successfully!");
        System.out.println("══════════════════════════════════════════════════════════════\n");
    }
}
