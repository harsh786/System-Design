/**
 * Facade Design Pattern - Complete Implementation
 * 
 * Provides a simplified interface to a complex subsystem.
 */

// =============================================================
// EXAMPLE 1: Computer Startup/Shutdown Facade
// =============================================================

class CPU {
    public void freeze() { System.out.println("  CPU: Freezing processor"); }
    public void jump(long position) { System.out.println("  CPU: Jumping to position " + position); }
    public void execute() { System.out.println("  CPU: Executing instructions"); }
    public void shutdown() { System.out.println("  CPU: Shutting down"); }
}

class Memory {
    public void load(long position, byte[] data) {
        System.out.println("  Memory: Loading " + data.length + " bytes at position " + position);
    }
    public void clear() { System.out.println("  Memory: Clearing memory"); }
}

class HardDrive {
    public byte[] read(long lba, int size) {
        System.out.println("  HardDrive: Reading " + size + " bytes from sector " + lba);
        return new byte[size];
    }
    public void spinDown() { System.out.println("  HardDrive: Spinning down"); }
}

class GraphicsCard {
    public void initialize() { System.out.println("  GraphicsCard: Initializing GPU"); }
    public void displaySplash() { System.out.println("  GraphicsCard: Displaying boot splash screen"); }
    public void shutdown() { System.out.println("  GraphicsCard: Powering off display"); }
}

class PowerSupply {
    public void turnOn() { System.out.println("  PowerSupply: Providing power to components"); }
    public void turnOff() { System.out.println("  PowerSupply: Cutting power"); }
}

// FACADE
class ComputerFacade {
    private final CPU cpu;
    private final Memory memory;
    private final HardDrive hardDrive;
    private final GraphicsCard graphicsCard;
    private final PowerSupply powerSupply;

    public ComputerFacade() {
        this.cpu = new CPU();
        this.memory = new Memory();
        this.hardDrive = new HardDrive();
        this.graphicsCard = new GraphicsCard();
        this.powerSupply = new PowerSupply();
    }

    public void start() {
        System.out.println("[ComputerFacade] Starting computer...");
        powerSupply.turnOn();
        graphicsCard.initialize();
        cpu.freeze();
        byte[] bootData = hardDrive.read(0, 1024);
        memory.load(0, bootData);
        cpu.jump(0);
        cpu.execute();
        graphicsCard.displaySplash();
        System.out.println("[ComputerFacade] Computer started successfully!\n");
    }

    public void shutdown() {
        System.out.println("[ComputerFacade] Shutting down computer...");
        cpu.shutdown();
        memory.clear();
        hardDrive.spinDown();
        graphicsCard.shutdown();
        powerSupply.turnOff();
        System.out.println("[ComputerFacade] Computer shut down.\n");
    }
}

// =============================================================
// EXAMPLE 2: Home Theater Facade
// =============================================================

class Amplifier {
    public void on() { System.out.println("  Amplifier: Turning on"); }
    public void setVolume(int level) { System.out.println("  Amplifier: Setting volume to " + level); }
    public void setSurroundSound() { System.out.println("  Amplifier: Surround sound enabled"); }
    public void off() { System.out.println("  Amplifier: Turning off"); }
}

class DVDPlayer {
    public void on() { System.out.println("  DVDPlayer: Turning on"); }
    public void play(String movie) { System.out.println("  DVDPlayer: Playing \"" + movie + "\""); }
    public void stop() { System.out.println("  DVDPlayer: Stopped"); }
    public void off() { System.out.println("  DVDPlayer: Turning off"); }
}

class Projector {
    public void on() { System.out.println("  Projector: Turning on"); }
    public void setWideScreenMode() { System.out.println("  Projector: Widescreen mode (16:9)"); }
    public void off() { System.out.println("  Projector: Turning off"); }
}

class TheaterLights {
    public void dim(int level) { System.out.println("  Lights: Dimming to " + level + "%"); }
    public void on() { System.out.println("  Lights: Full brightness"); }
}

class Screen {
    public void down() { System.out.println("  Screen: Lowering"); }
    public void up() { System.out.println("  Screen: Raising"); }
}

// FACADE
class HomeTheaterFacade {
    private final Amplifier amplifier;
    private final DVDPlayer dvdPlayer;
    private final Projector projector;
    private final TheaterLights lights;
    private final Screen screen;

    public HomeTheaterFacade() {
        this.amplifier = new Amplifier();
        this.dvdPlayer = new DVDPlayer();
        this.projector = new Projector();
        this.lights = new TheaterLights();
        this.screen = new Screen();
    }

    public void watchMovie(String movie) {
        System.out.println("[HomeTheaterFacade] Preparing to watch: " + movie);
        lights.dim(10);
        screen.down();
        projector.on();
        projector.setWideScreenMode();
        amplifier.on();
        amplifier.setSurroundSound();
        amplifier.setVolume(7);
        dvdPlayer.on();
        dvdPlayer.play(movie);
        System.out.println("[HomeTheaterFacade] Movie started. Enjoy!\n");
    }

    public void endMovie() {
        System.out.println("[HomeTheaterFacade] Ending movie session...");
        dvdPlayer.stop();
        dvdPlayer.off();
        amplifier.off();
        projector.off();
        screen.up();
        lights.on();
        System.out.println("[HomeTheaterFacade] Movie session ended.\n");
    }
}

// =============================================================
// EXAMPLE 3: Order Processing Facade
// =============================================================

class InventoryService {
    public boolean checkStock(String productId) {
        System.out.println("  InventoryService: Checking stock for " + productId);
        return true; // simulated
    }
    public void reserveItem(String productId) {
        System.out.println("  InventoryService: Reserved " + productId);
    }
    public void releaseItem(String productId) {
        System.out.println("  InventoryService: Released reservation for " + productId);
    }
}

class PaymentService {
    public boolean authorize(String cardNumber, double amount) {
        System.out.println("  PaymentService: Authorizing $" + amount + " on card ending " +
            cardNumber.substring(cardNumber.length() - 4));
        return true; // simulated
    }
    public String capture(String cardNumber, double amount) {
        System.out.println("  PaymentService: Captured $" + amount);
        return "TXN-" + System.currentTimeMillis();
    }
    public void refund(String transactionId) {
        System.out.println("  PaymentService: Refunded " + transactionId);
    }
}

class ShippingService {
    public String calculateShipping(String address) {
        System.out.println("  ShippingService: Calculating shipping to " + address);
        return "STANDARD-3-5-DAYS";
    }
    public String createShipment(String productId, String address) {
        System.out.println("  ShippingService: Creating shipment for " + productId + " to " + address);
        return "SHIP-" + System.currentTimeMillis();
    }
}

// FACADE
class OrderFacade {
    private final InventoryService inventory;
    private final PaymentService payment;
    private final ShippingService shipping;

    public OrderFacade() {
        this.inventory = new InventoryService();
        this.payment = new PaymentService();
        this.shipping = new ShippingService();
    }

    public String placeOrder(String productId, String cardNumber, double amount, String address) {
        System.out.println("[OrderFacade] Processing order for " + productId + "...");

        // Step 1: Check inventory
        if (!inventory.checkStock(productId)) {
            System.out.println("[OrderFacade] FAILED - Out of stock\n");
            return null;
        }
        inventory.reserveItem(productId);

        // Step 2: Process payment
        if (!payment.authorize(cardNumber, amount)) {
            inventory.releaseItem(productId);
            System.out.println("[OrderFacade] FAILED - Payment declined\n");
            return null;
        }
        String txnId = payment.capture(cardNumber, amount);

        // Step 3: Ship
        shipping.calculateShipping(address);
        String shipmentId = shipping.createShipment(productId, address);

        System.out.println("[OrderFacade] Order complete! Shipment: " + shipmentId + "\n");
        return shipmentId;
    }
}

// =============================================================
// MAIN
// =============================================================

public class FacadePattern {
    public static void main(String[] args) {
        System.out.println("========================================");
        System.out.println(" FACADE DESIGN PATTERN DEMO");
        System.out.println("========================================\n");

        // Example 1
        System.out.println("--- Example 1: Computer Facade ---\n");
        ComputerFacade computer = new ComputerFacade();
        computer.start();
        computer.shutdown();

        // Example 2
        System.out.println("--- Example 2: Home Theater Facade ---\n");
        HomeTheaterFacade theater = new HomeTheaterFacade();
        theater.watchMovie("Inception");
        theater.endMovie();

        // Example 3
        System.out.println("--- Example 3: Order Processing Facade ---\n");
        OrderFacade orderFacade = new OrderFacade();
        orderFacade.placeOrder("LAPTOP-001", "4111111111111234", 999.99, "123 Main St, NYC");
    }
}
